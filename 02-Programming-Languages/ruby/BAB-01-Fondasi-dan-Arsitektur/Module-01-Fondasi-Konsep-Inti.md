# Bab 01 Module 01: Arsitektur Ruby Runtime, Object Model, dan Dynamic Execution

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis** siklus hidup eksekusi kode Ruby mulai dari Tokenization, Parsing (Ripper/Bison), Kompilasi AST ke YARV (*Yet Another Ruby VM*) Bytecode, hingga eksekusi instruksi pada Virtual Machine stack.
- **Mendekonstruksi** arsitektur *Ruby Object Model*, termasuk hierarki pewarisan `BasicObject`, `Object`, `Module`, `Class`, representasi memori `RValue`, serta resolusi *Singleton Class* (*Eigenclass*).
- **Mengimplementasikan** pola meta-programming berbasis *dynamic dispatch*, *method lookup*, dan modifikasi ancestor chain secara deterministik tanpa merusak performa *Inline Cache* YARV.
- **Mendiagnosis** dan memitigasi memory leak serta alokasi berlebih akibat retensi objek pada heap Ruby menggunakan profiler (`objspace`, `stackprof`).

---

### 2. Concept Primer
Dalam ekosistem Ruby, *“Everything is an Object”* bukan sekadar jargon pemasaran desain bahasa, melainkan hukum arsitektur fundamental runtime. Berbeda dari runtime berbasis JVM atau CLR yang memisahkan tipe data primitif (`int`, `boolean`) dari tipe referensi berbasis heap (`java.lang.Object`), Ruby merepresentasikan seluruh entitas—termasuk bilangan bulat (`Integer`), status logika (`TrueClass`, `NilClass`), hingga blok fungsional (`Proc`, `Method`)—sebagai instansiasi objek penuh yang memiliki class, method table, dan kapabilitas introspeksi.

Secara mental model, bayangkan runtime Ruby sebagai jaringan pointer dinamis yang terhubung ke tabel metode:
- **Literal dan Skalar:** Nilai `1` bukan sekadar 64-bit integer mentah di CPU register saat dievaluasi dalam konteks OOP; ia adalah instansi dari class `Integer`. Pemanggilan `1 + 2` diterjemahkan secara semantik sebagai pengiriman pesan (*message dispatch*) `:send(:+, 2)` ke receiver `1`.
- **Class adalah Objek:** Class bukanlah deklarasi tipe statis kompilator; class adalah objek hidup (*first-class object*) yang merupakan instansiasi langsung dari class `Class`. Karena class adalah objek, ia dialokasikan pada runtime heap, dapat dimutasi kapan saja (*open classes*), dan memiliki singleton class tersendiri untuk mengelola method tingkat class (*class methods*).
- **Execution Context:** Di setiap titik eksekusi, runtime selalu mempertahankan konteks `self` (receiver saat ini) dan namespace resolusi konstanta.

---

### 3. Why This Matters
Dalam rekayasa sistem terdistribusi dan backend skala besar berbasis Ruby (misalnya core banking system, checkout engine e-commerce, atau payment gateway Stripe-like), kegagalan memahami Ruby Object Model dan YARV runtime akan langsung memicu degradasi performa dan stabilitas sistem:
- **Degradasi Inline Caching (IC):** YARV mengoptimalkan pemanggilan metode dinamis menggunakan *Inline Method Cache*. Manipulasi runtime yang buruk—seperti memanggil `def` di dalam loop, melakukan monkey-patching saat runtime production, atau penyalahgunaan `class_eval`—akan menyebabkan invalidasi *Global Method Cache* (GMC). Akibatnya, eksekusi kode beralih dari O(1) cache-hit ke O(N) linear ancestor traversal. Latensi P99 API dapat melonjak drastis dari 15ms menjadi 300ms+.
- **Memory Bloat dan Fragmentation:** Pemahaman yang salah terhadap struktur `RValue` (40 bytes per slot) dan alokasi `String` yang tidak di-freeze dapat memicu *Garbage Collection (GC) thrashing*. Pada throughput 5.000 RPS, pembuatan string dinamis tanpa kontrol dapat menimbun jutaan objek pada Ruby Heap, memicu *stop-the-world* GC pause berkepanjangan.

---

### 4. What: Technical Breakdown
Arsitektur eksekusi MRI (*Matz's Ruby Interpreter*) terbagi ke dalam dua pilar utama: **Compilation Pipeline** dan **Object/Memory Subsystem**.

#### A. The YARV Execution Pipeline
1. **Tokenization (Lexing):** Kode sumber ASCII/UTF-8 diubah menjadi token menggunakan lexical scanner internal (mirip Lex/Flex).
2. **Parsing:** Token dianalisis oleh parser berbasis LALR(1) (GNU Bison) untuk membangun *Abstract Syntax Tree* (AST).
3. **Bytecode Compilation:** AST dikompilasi menjadi instruksi YARV bytecode (`iseq` atau *Instruction Sequence*).
4. **Virtual Machine Execution:** YARV bertindak sebagai *stack-based virtual machine*. Nilai di-push ke stack, dimanipulasi oleh instruksi (misalnya `opt_plus`, `putobject`), dan di-pop sebagai hasil evaluasi.

#### B. Anatomi Memory: RValue & Immediate Values
Di level implementasi C (`include/ruby/ruby.h`), setiap objek Ruby direpresentasikan oleh struct `RValue` dengan ukuran tepat 40 bytes (pada arsitektur 64-bit).
- **Immediate Values (VALUE tagging):** Untuk menghindari alokasi heap 40 bytes bagi tipe dasar kecil, Ruby menggunakan teknik *pointer tagging*. Pointer `VALUE` adalah integer seukuran CPU word (64-bit). Bit terendah (*least significant bits*) bertindak sebagai flag:
  - `Fixnum (Integer kecil)`: Flag `0x01` (`VALUE = (n << 1) | 1`). Operasi integer murni tidak menyentuh heap.
  - `Symbol`: Flag `0x0c` (pada Ruby modern, static symbols).
  - `Special Constants`: `false` (0x00), `nil` (0x08), `true` (0x14).
- **Heap Allocated Objects:** Jika bit penanda bernilai `0x00`, `VALUE` adalah pointer langsung ke struct `RValue` pada heap. Struct ini memiliki:
  - `flags`: Menyimpan class pointer internal, bit flags GC (white/grey/black), tipe struct (`T_STRING`, `T_ARRAY`, `T_OBJECT`, dll.).
  - `as`: Union memori C yang memetakan data spesifik objek (misal: embedded array data atau pointer ke malloc external buffer jika payload > 24 bytes).

#### C. Method Lookup Path & Singleton Classes (Eigenclass)
Ketika metode dieksekusi pada receiver `obj.payment_process()`:
1. Runtime memeriksa keberadaan *Singleton Class* (Eigenclass) dari `obj`.
2. Mencari di tabel metode (*m_tbl*) milik Singleton Class.
3. Menelusuri rantai modul yang di-`prepend` ke Singleton Class.
4. Menelusuri rantai modul yang di-`include` ke Singleton Class.
5. Bergerak ke `obj.class` (Class instansiasi).
6. Menelusuri modul yang di-`prepend` ke `Class`.
7. Menelusuri tabel metode `Class`.
8. Menelusuri modul yang di-`include` ke `Class`.
9. Menelusuri superclass hingga `Object`, `Kernel`, dan berakhir di `BasicObject`.
10. Jika tidak ditemukan, runtime memulai traversal kedua dari receiver awal untuk memanggil `method_missing(:payment_process)`.

---

### 5. Visual Architecture Diagram

```text
                  +-----------------------------------+
                  |           Ruby Source             |
                  +-----------------------------------+
                                    |
                            [Lexer / Ripper]
                                    v
                  +-----------------------------------+
                  |          Token Stream             |
                  +-----------------------------------+
                                    |
                           [Bison Parser (LALR)]
                                    v
                  +-----------------------------------+
                  |      AST (Abstract Syntax Tree)   |
                  +-----------------------------------+
                                    |
                              [YARV Compiler]
                                    v
                  +-----------------------------------+
                  | YARV Instruction Sequence (iseq)  |
                  +-----------------------------------+
                                    |
                                    v
                  +===================================+
                  |         YARV Stack VM             |
                  +===================================+
                    /                               \
    [Immediate Value Execution]              [Heap Memory Layout]
       - Fixnum ((val << 1) | 1)            +--------------------------+
       - true/false/nil                     | Ruby Heap Page (16KB)    |
       - Static Symbols                     | +----------------------+ |
                                            | | Slot 0: RValue (40B) | |
                                            | +----------------------+ |
                                            | | Slot 1: RValue (40B) | |
                                            | +----------------------+ |
                                            | | ...                  | |
                                            | +----------------------+ |
                                            +--------------------------+

================================================================================
                    OBJECT MODEL & ANCESTOR HIERARCHY
================================================================================

   [BasicObject] ------------------------> [Singleton Class: BasicObject]
        ^                                                 ^
        |                                                 |
    [Object] (includes Kernel) ----------> [Singleton Class: Object]
        ^                                                 ^
        |                                                 |
     [Module] ---------------------------> [Singleton Class: Module]
        ^                                                 ^
        |                                                 |
     [Class] ----------------------------> [Singleton Class: Class]
        ^                                                 ^
        | (inherits)                                      | (inherits)
+---------------+                                 +-----------------------+
|  User Engine  | -- (has eigenclass link) -----> |  #<Class:UserEngine>  |
+---------------+                                 +-----------------------+
        ^
        | (instance_of)
+---------------+
| engine_inst   | -- (singleton_class) ---------> #<Class:#<UserEngine:...>>
+---------------+
```

---

### 6. How-To Implementation Guide
Untuk memanfaatkan YARV dan Object Model secara optimal, ikuti tahapan perancangan komponen dinamis berikut:

#### Langkah 1: Eksplorasi Bytecode
Gunakan module standar `RubyVM::InstructionSequence` untuk membedah apakah sintaks yang Anda buat menghasilkan bytecode yang ringkas dan memanfaatkan *peephole optimization*.

```ruby
code = "1 + 2"
iseq = RubyVM::InstructionSequence.compile(code)
puts iseq.disasm
```

#### Langkah 2: Hindari Polusi Method Table
Gunakan module composition (`Module#prepend` atau `Module#include`) alih-alih melakukan *re-opening class* mentah secara langsung.

#### Langkah 3: Optimasi Penggunaan String Literal
Terapkan magic comment `# frozen_string_literal: true` di seluruh file production. Ini menginstruksikan YARV untuk mengalokasikan string satu kali di memori dan me-reuse pointer `RValue` yang sama secara deterministik.

---

### 7. Minimal Working Example

Script berikut menunjukkan dekonstruksi immediate values, validasi alokasi RValue heap, dan inspeksi bytecode:

```ruby
# frozen_string_literal: true

require 'objspace'

# 1. Dekonstruksi Immediate Value vs Heap Allocation
fixnum_val = 42
string_val = +"Transaction_Payload" # Mutable string di heap

puts "=== 1. Memory Address & Pointer Tagging ==="
puts format("Fixnum VALUE (raw id): 0x%x", fixnum_val.object_id)
# Fixnum object_id di Ruby adalah (value << 1), bit tagging = 1
puts format("Expected tagged pointer value: 0x%x", (fixnum_val << 1) | 1)
puts format("String VALUE (heap pointer): 0x%x", string_val.object_id)
puts "String byte size in memory: #{ObjectSpace.memsize_of(string_val)} bytes"

# 2. Dekonstruksi Ancestor Lookup
module TelemetryTracing
  def trace_id
    "TRC-#{object_id}"
  end
end

class PaymentProcessor
  prepend TelemetryTracing
end

processor = PaymentProcessor.new
puts "\n=== 2. Ancestor Chain Verification ==="
puts "Ancestor chain: #{PaymentProcessor.ancestors.join(' -> ')}"
puts "Trace output: #{processor.trace_id}"

# 3. YARV Bytecode Disassembly
puts "\n=== 3. YARV Bytecode Output ==="
iseq = RubyVM::InstructionSequence.compile('processor.trace_id')
puts iseq.disasm
```

---

### 8. Production-Grade Example

Implementasi production dynamic RPC router performa tinggi. Modul ini membendung overhead `method_missing` konvensional dengan cara me-registrasi dan me-resolve metode langsung ke dalam dynamic dispatcher via `define_singleton_method`, mempertahankan *Inline Caching* YARV dan menyertakan metrics telemetry error handling.

```ruby
# frozen_string_literal: true

require 'logger'
require 'benchmark'

module CoreBanking
  class DynamicRpcRouter
    ExecutionError = Class.new(StandardError)
    RouteNotFoundError = Class.new(ExecutionError)

    RouteDefinition = Struct.new(:target_klass, :target_method, :frozen)

    def initialize(logger: Logger.new($stdout))
      @logger = logger
      @registry = {}
      @registry_mutex = Thread::Mutex.new
    end

    def register_route(endpoint_name, target_klass, target_method)
      sym_endpoint = endpoint_name.to_sym

      @registry_mutex.synchronize do
        raise ArgumentError, "Route :#{sym_endpoint} already exists" if @registry.key?(sym_endpoint)

        @registry[sym_endpoint] = RouteDefinition.new(target_klass, target_method, true)

        # Kompilasi metode langsung pada instance singleton class
        # Mencegah fallback linear method_missing pada runtime berikutnya
        define_singleton_method(sym_endpoint) do |payload|
          invoke_route(sym_endpoint, payload)
        end
      end

      @logger.info("Route successfully compiled to bytecode: #{sym_endpoint}")
    end

    def method_missing(method_name, *args, &block)
      # Fallback defensif untuk handling rute yang tidak terdaftar
      @logger.warn("RPC invocation missed inline cache: #{method_name}")
      raise RouteNotFoundError, "RPC endpoint :#{method_name} is not registered on this node"
    end

    def respond_to_missing?(method_name, include_private = false)
      @registry.key?(method_name.to_sym) || super
    end

    private

    def invoke_route(endpoint_name, payload)
      route = @registry.fetch(endpoint_name) do
        raise RouteNotFoundError, "Route #{endpoint_name} disappeared from registry"
      end

      target_instance = route.target_klass.new
      start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

      begin
        result = target_instance.public_send(route.target_method, payload)
        duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
        
        @logger.debug do
          format("Endpoint %<name>s executed in %<ms>.3f ms", name: endpoint_name, ms: duration * 1000)
        end

        result
      rescue StandardError => e
        @logger.error("Execution failure on #{endpoint_name}: #{e.class} - #{e.message}")
        raise ExecutionError, "Failed to execute RPC: #{e.message}"
      end
    end
  end

  # Dummy Service Implementation
  class SettlementService
    def settle_funds(payload)
      amount = payload.fetch(:amount)
      account = payload.fetch(:account_id)
      { status: 'SUCCESS', transaction_ref: "TX-#{account}-#{amount}" }
    end
  end
end

# Verification Script
router = CoreBanking::DynamicRpcRouter.new
router.register_route(:settle, CoreBanking::SettlementService, :settle_funds)

payload = { account_id: 'ACC-88901', amount: 50_000_000 }
response = router.settle(payload)
puts "Execution Response: #{response.inspect}"
```

---

### 9. Anti-Patterns & Common Pitfalls

#### Anti-Pattern 1: Menggunakan `method_missing` Tanpa Menyediakan `respond_to_missing?`
*Dampak Buruk:* Merusak protokol introspeksi Ruby, mematahkan fungsi gems metaprogramming lain (seperti serializer, mock test suites, dan rspec spies).

```ruby
# BAD
class Proxy
  def method_missing(name, *args)
    "Handled #{name}"
  end
end
p = Proxy.new
p.respond_to?(:execute) # => false, inkonsistensi internal!

# GOOD
class Proxy
  def method_missing(name, *args)
    return "Handled #{name}" if name.start_with?('do_')
    super
  end

  def respond_to_missing?(name, include_private = false)
    name.start_with?('do_') || super
  end
end
```

#### Anti-Pattern 2: Evaluasi String Dinamis Berulang (`eval`, `class_eval`)
*Dampak Buruk:* Mengompilasi string baru pada runtime memaksa YARV memanggil bison parser dan compiler berulang kali, merusak *Global Method Cache*, memicu memory fragmentation, dan membuka celah arbitrary code execution.

```ruby
# CRITICAL ANTI-PATTERN
def define_accessor(field_name)
  eval("def #{field_name}; @#{field_name}; end") # Parser dipanggil berulang di production!
end

# PRODUCTION-GRADE IDIOMATIC
def define_accessor(field_name)
  define_method(field_name) do
    instance_variable_get(:"@#{field_name}")
  end
end
```

---

### 10. Edge Cases, Failure Modes & Mitigations

| Failure Mode / Edge Case | Akar Masalah Arsitektural | Mitigasi Teruji (Production-Ready) |
| :--- | :--- | :--- |
| **Global Method Cache (GMC) Thrashing** | Memanggil `def` baru, `alias_method`, atau `include` di dalam execution loop/request worker. | Bekukan class definitions setelah tahap bootloader/initialization. Gunakan `Module#freeze`. |
| **Object Allocation Exhaustion (GC Stall)** | Penggunaan dynamic symbol (`"payload_#{i}".to_sym`). Simbol tidak dibersihkan secara agresif oleh GC (tergantung implementasi dynamic symbols). | Gunakan String yang di-freeze (`-str` atau `# frozen_string_literal: true`) sebagai hash keys alih-alih unbounded dynamic symbols. |
| **Ancestor Loop Resolution (`ArgumentError: cyclic include detected`)** | Modul A meng-include Modul B, dan pada runtime Modul B mencoba meng-include Modul A. | Terapkan dependency injection strictly bertingkat. Hindari *circular require/include*. |
| **Recursion Stack Overflow** | Pemanggilan `super` pada monkey-patched method tanpa dasar ancestor chain yang jelas. | Selalu gunakan `Module#prepend` untuk dekorasi method, sehingga rantai pemanggilan `super` memiliki target deterministik. |

---

### 11. Security Considerations
1. **Unbounded Symbol Generation DoS:** Hindari parsing payload JSON eksternal menggunakan `JSON.parse(payload, symbolize_names: true)` jika keys berasal dari user input yang tidak dibatasi. Meskipun Ruby modern memiliki *Immortal* vs *Mortal* symbols, pembuatan mortal symbol berlebih tetap memberikan pressure tinggi pada heap metadata allocator.
2. **Arbitrary Code Execution via Object Deserialization:** Dilarang keras menggunakan `Marshal.load` pada raw data dari jaringan publik. Struktur `Marshal` menyimpan dump internal class dan instance variables. Attacker dapat mengirim serialized payload gadget chain yang mengeksekusi shellcode saat YARV merekonstruksi objek. Gunakan strict deserializer seperti `JSON.parse(data, symbolize_names: false)` dengan schema validator (misal: `dry-schema`).
3. **Constant Lookup Hijacking:** Ruby menyelesaikan konstanta secara hierarkis (lexical scope lebih diprioritaskan dibanding ancestor chain). Jangan merujuk kelas sensitif menggunakan relative path (misal: `User`). Selalu gunakan root namespace anchoring: `::User` atau `::Security::Cipher` untuk mencegah class injection dari modul luar.

---

### 12. Performance & Resource Optimization

- **Alokasi String & F-Strings:** 
  Pada Ruby, penulisan `"hello"` membuat objek `RValue` baru setiap evaluasi. Dengan `# frozen_string_literal: true`, string tersebut di-deduplikasi menjadi objek frozen statis di memory table.
- **Peephole Optimization Analysis:**
  Instruksi YARV memiliki operasi khusus untuk method primitif matematika (`opt_plus`, `opt_minus`, `opt_lt`). Jika Anda me-redefine operator `+` pada class `Integer`, YARV terpaksa men-deoptimasi jalur assembly native ini ke dynamic method lookup standar, meruntuhkan performa perhitungan matematika di aplikasi.
- **Brenchmarking Alokasi Objek:**

```ruby
require 'benchmark/memory'

# Verifikasi efisiensi memori antara Mutable vs Frozen Object
Benchmark.memory do |x|
  x.report('Mutable String') do
    10_000.times { "transaction_hash_key" }
  end

  x.report('Frozen String') do
    10_000.times { -"transaction_hash_key" }
  end

  x.compare!
end
# Hasil: Frozen String mengalokasikan 0 bytes baru setelah inisialisasi awal.
```

---

### 13. Observability & Debugging

Gunakan API internal `RubyVM` dan `ObjectSpace` untuk mendiagnosis crash dan memory leak secara live di level low-level:

```ruby
# 1. Melacak kebocoran RValue per class
require 'objspace'

def audit_heap_instances(target_class)
  count = ObjectSpace.each_object(target_class) { |inst| nil }
  puts "Total live heap instances of #{target_class}: #{count}"
end

# 2. Trace Method Execution dengan TracePoint (Zero External Dependencies)
trace = TracePoint.new(:call, :c_call) do |tp|
  next unless tp.path&.start_with?(Dir.pwd)
  puts "[Trace] #{tp.event} -> #{tp.defined_class}##{tp.method_id} [#{tp.path}:#{tp.lineno}]"
end

trace.enable
# Panggil operasi bisnis Anda
# ...
trace.disable

# 3. Dump YARV Inline Cache Status (Gunakan pada tahap profiling/investigasi dev)
puts RubyVM.stat
```

---

### 14. Testing & Verification Strategies

Strategi pengujian arsitektural wajib memastikan bahwa implementasi OOP tidak merusak ancestor table dan aman dari alokasi memori berlebih.

```ruby
# frozen_string_literal: true

require 'minitest/autorun'
require 'objspace'

class SettlementEngine
  def process_batch(items)
    items.map { |i| "TXN-#{i}".freeze }
  end
end

class SettlementEngineTest < Minitest::Test
  def setup
    @engine = SettlementEngine.new
  end

  def test_ancestor_integrity
    # Memastikan tidak ada rogue module yang merusak hierarki
    expected_ancestors = [SettlementEngine, Object, Kernel, BasicObject]
    assert_equal expected_ancestors, SettlementEngine.ancestors
  end

  def test_zero_allocation_overhead_on_frozen_strings
    GC.start # Bersihkan state awal
    before_allocs = ObjectSpace.each_object(String).count

    # Eksekusi fungsi
    @engine.process_batch([1, 2, 3])

    after_allocs = ObjectSpace.each_object(String).count
    allocated = after_allocs - before_allocs

    # Maksimal alokasi baru harus terukur dan bounded (hanya 3 string unik)
    assert_operator allocated, :<=, 3, "Terjadi alokasi string tak terduga!"
  end

  def test_method_resolution_behavior
    assert_respond_to @engine, :process_batch
    refute_respond_to @engine, :undefined_ghost_method
  end
end
```

---

### 15. Operational Runbook

#### Skenario: Lonjakan Latensi API P99 dan GC Stalls Akibat Method Cache Invalidation
1. **Deteksi Awal:** Metrik Prometheus/Datadog menunjukkan lonjakan `ruby.gc.time` dan peningkatan runtime CPU utilization tanpa adanya lonjakan RPS yang signifikan.
2. **Inspeksi Live Process via GDB / rbtrace:**
   Sambungkan ke worker process MRI yang bermasalah:
   ```bash
   rbtrace -p <PID> --firehose
   ```
   Cari log yang mencatat evaluasi dinamis berulang seperti `eval`, `class_eval`, atau `extend`.
3. **Analisis Profiling Dump:**
   Jalankan signal snapshot ke worker process untuk mendapatkan profile memori (gunakan gems seperti `sigdump` yang memanggil `ObjectSpace.dump_all`).
4. **Tindakan Mitigasi Darurat:**
   - Restart worker processes secara *rolling update* untuk memulihkan alokasi memori heap yang terfragmentasi.
   - Aktifkan environment variable `RUBY_GC_HEAP_GROWTH_FACTOR=1.1` (default 1.8) sementara waktu untuk mengurangi sudden memory allocation spike.
5. **Permanen:** Temukan kode library atau aplikasi yang memanggil `.extend(SomeModule)` pada payload request loop. Ganti dengan method composition via wrapper/decorator object murni.

---

### 16. Alternatives & Trade-offs

| Paradigma / Pendekatan | Latensi Eksekusi | Overhead Alokasi Heap | Maintainability | Kapan Harus Digunakan? |
| :--- | :--- | :--- | :--- | :--- |
| **Dynamic Method Dispatch (`method_missing`)** | **Tinggi (Buruk)**: Memerlukan traversal ancestor penuh dari receiver ke `BasicObject`. | Rendah (tidak membuat method metadata baru di Class). | Rendah: Sulit di-debug, tracepoints tersamarkan. | Wrapper/proxy umum di mana ratusan method tidak diketahui secara spesifik di awal. |
| **Metaprogramming Awal (`define_method` saat Booting)** | **Sangat Rendah (O(1))**: Memanfaatkan YARV Inline Method Cache secara sempurna. | Moderat: Memakan slot memori di Method Table class. | Tinggi: Terlihat eksplisit pada introspeksi `methods`. | DSL deklaratif, API client SDK, RPC routers, dynamic schema models. |
| **Direct Evaluated Code (`eval(str)`)** | **Kritis (Terburuk)**: Compiles AST & Bytecode pada setiap pemanggilan. | Sangat Tinggi: Memicu alokasi string dan node bytecode baru. | Buruk: Risiko security tinggi (RCE). | **Hindari sepenuhnya di level production**. |

---

### 17. Ecosystem Context
- **Standard Library:**
  - `ObjectSpace`: API inti interaksi dengan GC dan alokasi heap C-struct.
  - `RubyVM`: Introspeksi internal YARV (Instruction Sequence, register configuration).
  - `Ripper`: Parser generator bawaan Ruby untuk membedah kode menjadi S-expressions.
- **Production Gems Wajib:**
  - `stackprof`: Sampling call-stack profiler native berbasis C untuk YARV (menganalisis CPU dan object allocations).
  - `memory_profiler`: Menganalisis alokasi string dan objek secara granular per baris file ruby.
  - `bootsnap`: Mengoptimalkan boot time dengan menyimpan cache YARV compilation (`iseq`) langsung ke disk/SSD.

---

### 18. Deep Dive / Under the Hood

Mari kita bedah source code MRI C (`vm_insnhelper.c` dan `method.h`).

Ketika YARV mengeksekusi instruksi `send` (dispatching method), VM tidak serta-merta membaca tabel hash method milik receiver. MRI mengimplementasikan **Inline Method Cache (IC)** yang disimpan langsung di dalam argumen operand bytecode:

```c
// Representasi konseptual struct cache pemanggilan method pada YARV
struct rb_call_cache {
    VALUE class_serial;      // Serial number global milik class receiver
    const rb_callable_method_entry_t *cme; // Pointer langsung ke fungsi C/Bytecode
    unsigned int call_tag;   // Metrik validasi
};
```

1. Setiap `Class` di Ruby memiliki penghitung internal monotonic yang disebut `class_serial`.
2. Di level VM global, terdapat counter `ruby_vm_global_method_state`. Setiap kali sebuah class di-reopen dan method ditambahkan/dimutasi (misal: `def calculate; ... end`), nilai serial ini di-inkremen secara global atau lokal.
3. Saat method dipanggil pertama kali:
   - YARV melakukan slow lookup menelusuri ancestor pointer (`klass = klass->super`).
   - YARV mendapatkan pointer fungsi C atau `rb_iseq_t` (bytecode) method tersebut.
   - YARV menyimpan class serial receiver dan target method pointer di cache struct `rb_call_cache` tepat pada baris bytecode tersebut.
4. Pada pemanggilan berikutnya:
   - YARV mengecek: `if (receiver->klass->class_serial == cc->class_serial)`.
   - Jika `true` (Cache Hit): VM langsung melompat ke method pointer tanpa resolusi hash table sama sekali. Eksekusi bernilai O(1).
   - Jika `false` (Cache Miss): Terjadi *Invalidasi Cache*. VM terlempar ke jalur lambat, membuang data cache, dan mengulang ancestor traversal dari awal.

Inilah sebabnya mengapa arsitektur dynamic Ruby melarang mutasi class saat aplikasi sudah aktif melayani traffic: satu mutasi method pada class basis (`Object` atau `Array`) dapat menghancurkan performa jutaan inline cache di seluruh runtime server.

---

### 19. Enterprise Scenario

#### Masalah Produksi:
Sebuah perusahaan Unicorn Fintech memproses 12.000 transaksi pembayaran per detik pada cluster berkapasitas 200 pod container Ruby on Rails/Puma. Pasca-deployment versi terbaru, penggunaan RAM pod melonjak dari rata-rata 600MB menjadi 2.8GB hanya dalam 30 menit. Hal ini memicu OOM (*Out of Memory*) Killer dari kernel Linux dan me-restart worker Puma secara konstan, menyebabkan error `502 Bad Gateway` pada 4.2% transaksi masuk.

#### Investigasi Teknis:
Engineer mengambil heap snapshot menggunakan `ObjectSpace.dump_all(output: File.open('heap.json', 'w'))` pada satu pod yang mengalami memory bloat. Analisis menunjukkan terdapat 3.500.000 instansi objek anonim dari `Module` dan `Class`. 

Ditemukan kode pada middleware autentikasi:
```ruby
# CRITICAL BUG DALAM MIDDLEWARE:
def call(env)
  request = Rack::Request.new(env)
  # Dynamic module inclusion pada singleton class request di setiap HTTP Call:
  request.singleton_class.include(Class.new(SecurityPolicyModule))
  @app.call(env)
end
```

#### Solusi Arsitektural:
1. `Class.new` membuat objek kelas anonim di heap Ruby yang **tidak dapat di-reclaim oleh GC secara efisien** karena keterikatan dengan Global Method Tables dan singleton class chain.
2. Kode tersebut dihapus. Digantikan oleh implementasi static composition berbasis *Strategy Pattern* sederhana:

```ruby
# FIX IMPLEMENTASI:
class SecurityPolicyApplier
  # Modul dikompilasi statis sekali saat bootup
  POLICIES = {
    standard: StandardSecurityPolicy.new,
    elevated: ElevatedSecurityPolicy.new
  }.freeze

  def self.apply(request)
    policy_type = request.headers['X-Policy-Tier'] || :standard
    POLICIES.fetch(policy_type.to_sym).enforce!(request)
  end
end
```
3. Dampak: Alokasi memory per pod stabil kembali di 520MB, CPU GC pause turun dari 28% runtime total menjadi 1.2%, dan lonjakan 502 HTTP errors berhasil dieliminasi sepenuhnya.

---

### 20. Hands-on Challenge & Exercises

#### Deskripsi Tantangan:
Rancang sebuah micro-framework ORM lightweight bernama `FastRecord::Base` yang memiliki fungsionalitas auto-mapping attributes dari Hash database, namun **tidak boleh** menggunakan `method_missing` konvensional untuk getter/setter data, demi menjaga kestabilan *YARV Inline Caching*.

#### Spesifikasi dan Acceptance Criteria:
1. Class turunan dari `FastRecord::Base` harus dapat mendeklarasikan attributes secara deklaratif:
   ```ruby
   class Account < FastRecord::Base
     define_attributes :account_number, :balance
   end
   ```
2. Dynamic getter dan setter (`account_number`, `account_number=`) harus dikompilasi ke method table `Account` saat kelas didefinisikan, bukan dievaluasi saat runtime request.
3. Mutasi nilai melalui setter harus memanipulasi `@attributes` hash internal secara privat.
4. Akses ke attribute yang belum dideklarasikan harus melempar error standard `NoMethodError` native bawaan Ruby tanpa penangkapan artifisial.
5. Jalankan stress test: Inisialisasi 100.000 objek dan pemanggilan getter harus selesai dalam waktu kurang dari 0.15 detik tanpa kebocoran alokasi class baru.

#### Solution Hint:
Gunakan `Module.new` yang menyimpan method-method atribut via `attr_accessor` atau `define_method`, lalu lakukan `include` modul tersebut ke class turunan di dalam block deklarasi class (`self.inherited`). Hal ini memisahkan layer data dari root class dan memberikan hak pada subclass untuk melakukan `super` jika ingin meng-override getter/setter.