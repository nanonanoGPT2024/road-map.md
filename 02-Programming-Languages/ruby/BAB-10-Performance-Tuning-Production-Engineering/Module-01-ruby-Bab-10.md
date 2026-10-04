# Bab 10 Module 01: YARV Execution Model, Instruction Sequences (ISeq), dan Runtime Optimization YJIT

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta mampu:
* Membedah alur eksekusi internal CRuby (MRI) mulai dari kode sumber, Abstract Syntax Tree (AST), hingga kompilasi Instruction Sequence (ISeq).
* Menginspeksi, menganalisis, dan memanipulasi bytecode YARV (*Yet Another Ruby VM*) secara terprogram menggunakan modul `RubyVM::InstructionSequence`.
* Mendiagnosis degradasi performa yang diakibatkan oleh *inline cache invalidation* dan kegagalan *monomorphic call-site dispatch*.
* Mengonfigurasi, memantau, dan mengoptimalkan runtime Ruby menggunakan arsitektur *Lazy Basic Block Versioning* (LBBV) pada YJIT (*Yet Another JIT*) untuk layanan produksi berbasis web throughput tinggi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* **Ruby Object Model**: Hirarki `Class`, `Module`, *eigenclass*, serta alur resolusi *method lookup path*.
* **Memory Management Dasar**: Operasi Ruby Garbage Collector (Generational GC / compaction) dan struktur `RVALUE`.
* **Arsitektur CPU Dasar**: Konsep eksekusi berbasis *Stack* vs *Register*, mekanisme *Instruction Cache* (I-Cache), dan *Branch Prediction*.
* **Lingkungan Runtime**: CRuby versi 3.2+ (disarankan Ruby 3.3.x) yang dikompilasi dengan dukungan YJIT.

---

### 3. Concept

CRuby (MRI) bukan interpreter murni yang mengevaluasi teks kode sumber baris demi baris, melainkan sebuah *Virtual Machine* berbasis *stack* dua tahap:

```
[ Ruby Source Code ]
        │
        ▼ (Lexer & LALR(1) Parser via Bison)
[ Abstract Syntax Tree (AST) ]
        │
        ▼ (YARV Compiler)
[ Instruction Sequences (ISeq) ]
        │
   ┌────┴──────────────────────────┐
   ▼ (Interpreter Loop)            ▼ (Hot-path compilation via YJIT)
[ YARV Stack-based Execution ]    [ Native Machine Code (x86_64 / ARM64) ]
```

1. **Kompilasi ke ISeq (Instruction Sequence)**: Kode sumber diurai menjadi *tokens*, dibentuk menjadi AST, lalu dikompilasi menjadi bytecode biner internal berupa instruksi YARV. Bytecode ini disimpan di dalam objek `RubyVM::InstructionSequence`.
2. **YARV Evaluation Loop**: YARV memelihara *control frame* (`rb_control_frame_t`), penunjuk instruksi (`PC` / *Program Counter*), dan penunjuk tumpukan (*Stack Pointer* / `SP`). Setiap operasi (seperti pemanggilan metode, penambahan integer, alokasi lokal) memanipulasi *operand stack*.
3. **Inline Caching (IC)**: YARV menerapkan optimasi *inline caching* pada *call-site* instruksi seperti `opt_send_without_block`. VM mencatat kelas penerima (*receiver class*) dan *method table pointer* langsung pada instruksi untuk menghindari proses resolusi metode traversal penuh di setiap pemanggilan.
4. **Lazy Basic Block Versioning (LBBV) - YJIT**: Mulai Ruby 3.1+, YJIT mengompilasi bytecode YARV ke kode mesin asli secara *lazy*. YJIT tidak mengompilasi seluruh metode sekaligus, melainkan mengompilasi *basic block* ketika jalur eksekusi tersebut aktif dan menghasilkan versi spesifik dari blok kode berdasarkan tipe data aktual runtime (*runtime type specialisation*).

---

### 4. Why

Dalam arsitektur backend berskala masif (seperti e-commerce, *payment gateway*, dan agregator API), beban kerja Ruby umumnya mengalami dua hambatan: *I/O latency* dan *interpreter overhead* pada layer orkestrasi CPU-bound (seperti serialisasi JSON, evaluasi *policy/rules engine*, dan ORM *hydration*).

Memahami YARV dan YJIT memberikan keunggulan teknis fundamental:
* **Eliminasi Polymorphic Dispatch**: Menulis kode yang secara tidak sengaja memicu *polymorphic* atau *megamorphic call sites* menyebabkan *Inline Cache thrashing*, menurunkan efisiensi instruksi YARV hingga puluhan persen.
* **Tuning Alokasi Memori YJIT**: YJIT mengalokasikan memori *executable* di luar tumpukan Ruby heap konvensional. Tanpa pemahaman mendalam tentang *code cache size* dan *deoptimization limit*, performa produksi dapat mengalami penurunan tajam (*performance cliff*) ketika memori instruksi penuh atau *bailout* terus-menerus terjadi.
* **Analisis Profiling Presisi**: Kemampuan membaca bytecode memungkinkan rekayasawan mendiagnosis apakah sebuah konstruksi sintaksis (misalnya meta-programming vs deklarasi eksplisit) dioptimasi oleh VM melalui instruksi khusus seperti `opt_plus` atau jatuh ke alur lambat via *generic method dispatch*.

---

### 5. What

Komponen-komponen kritis dalam subsistem eksekusi Ruby mencakup:

* **Instruction Sequence (`RubyVM::InstructionSequence`)**: Representasi objek dari rangkaian instruksi YARV yang berisi opcodes, metadata tabel lokal, penanganan exception, dan catch-table.
* **Control Frame Pointer (`CFP`)**: Struktur internal C yang mengisolasi *context frame* dari sebuah eksekusi metode, blok, atau rescue boundary.
* **Inline Cache (IC)**: Entri memori yang berpasangan dengan instruksi pemanggilan untuk menyimpan cache:
  * *Global Method State* serial number.
  * Tipe kelas receiver (*Class Pointer*).
  * Pointer langsung menuju definisi metode (`rb_callable_method_entry_t`).
* **Basic Block (YJIT)**: Urutan instruksi linier tanpa percabangan (kecuali di akhir blok).
* **Deoptimization (Bailout)**: Proses darurat ketika asumsi tipe data yang dibuat oleh YJIT tidak lagi terpenuhi di runtime (misalnya, variabel yang diasumsikan `Integer` tiba-tiba menerima `NilClass`). VM membatalkan eksekusi kode mesin dan mengalihkan konteks kembali ke interpreter YARV stack.

---

### 6. How

Proses transisi dari penulisan kode hingga eksekusi mesin tingkat rendah berlangsung melalui fase deterministik berikut:

```
[ Kode Ruby: a + b ]
        │
        ▼ Tokenizer & Bison Parser
[ NODE_OPCALL (call: +) ]
        │
        ▼ YARV Compiler
[ ISeq: opt_plus (Inline Cache) ]
        │
        ├── Evaluasi Berulang (Hot Path Terdeteksi)
        ▼
[ YJIT Engine: Menginspeksi Tipe Operand ]
        │
        ├── Asumsi: Operand kiri dan kanan adalah Fixnum/Integer
        ▼
[ Generate Native Code: add RAX, RBX; jno valid ]
        │
        ├── Terjadi Overflow / Tipe Berubah ke Float
        ▼ (Bailout / Deopt)
[ Kembalikan Frame ke YARV Interpreter ]
```

1. **Parsing & AST Construction**: Ruby membaca *stream* karakter, menghasilkan representasi AST internal berupa node-node ekspresi (`NODE_IF`, `NODE_CALL`, dll).
2. **Kompilasi ISeq**: AST ditransformasikan menjadi instruksi linear berbasis tumpukan. Konstruksi operasi dasar sering kali diganti dengan instruksi khusus yang dioptimalkan (*specialized instructions*), misalnya operator `+` menjadi opcode `opt_plus`.
3. **Execution Loop Entry**: Interpreter mengambil *frame* pertama, meletakkan referensi lokal ke dalam *local table*, dan memanipulasi *stack*.
4. **YJIT Basic Block Generation**: Jika YJIT diaktifkan (`--yjit`), saat pemanggilan instruksi melampaui ambang batas tertentu (*call threshold*), blok tersebut dikompilasi ke kode mesin dengan memasukkan *type assertion checks* (misalnya memastikan *value* tidak mengalami *tag bit shifting*).
5. **Runtime Invalidation**: Jika kelas target memodifikasi metodenya, atau jika *global class serial* berubah secara global, *Inline Cache* di-invalidasi dan YJIT membatalkan kompilasi blok terkait (*code invalidation*).

---

### 7. Analogy

Bayangkan Anda mengoperasikan sistem dapur restoran modern:
* **YARV Interpreter** adalah koki pemula yang membaca instruksi resep langkah-demi-langkah dari selembar kertas memo (*stack*). Setiap langkah mengharuskannya memeriksa rak bumbu, membaca label, dan memindahkan bahan satu per satu. Cara ini fleksibel untuk semua jenis menu, tetapi lambat karena pembacaan konstan dan perpindahan fisik.
* **Inline Cache (IC)** adalah catatan tempel kecil di samping wajan penggorengan yang bertuliskan: *"Garam selalu ada di laci kanan atas."* Koki tidak perlu lagi membaca peta dapur selama tata letak bumbu tidak diganti oleh manajer.
* **YJIT (LBBV)** adalah asisten robot presisi tinggi. Begitu ia melihat koki memasak menu yang sama berulang kali (misalnya, memotong bawang dengan ukuran seragam), robot tersebut merakit jalur konveyor khusus (*native assembly*) untuk memotong bawang dalam satu siklus mesin. 
* **Deoptimization (Bailout)** terjadi ketika keranjang bawang tiba-tiba berisi apel. Sensor robot memicu alarm darurat, seketika menghentikan konveyor, dan menyerahkan pisau kembali ke koki manual untuk melanjutkan persiapan tanpa membuat dapur terbakar.

---

### 8. Diagram

```
+-------------------------------------------------------------------------+
|                           RUBY PROCESS MEMORY                           |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | Ruby Source Code                                                  |  |
|  | def calculate_tax(subtotal); subtotal * 0.11; end                 |  |
|  +-------------------------------------------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  | YARV ISeq (Instruction Sequence)                                  |  |
|  | 0000 getlocal_WC_0    subtotal (read local variable)              |  |
|  | 0002 putobject        0.11     (push float onto stack)            |  |
|  | 0004 opt_mult         <calldata:flags, ic:0x7fa890>               |  |
|  | 0006 leave                     (pop frame, return result)         |  |
|  +-------------------------------------------------------------------+  |
|               |                                       ^                 |
|               | (If Hot Path via Call Counter)       | (Deopt/Bailout) |
|               v                                       |                 |
|  +----------------------------------------------------+--------------+  |
|  | YJIT Subsystem (Lazy Basic Block Versioning)                      |  |
|  |                                                                   |  |
|  |  +------------------------+      +-----------------------------+  |  |
|  |  | Type Analysis Context  |      | Executable Code Cache       |  |  |
|  |  | subtotal: Float        | ---> | (Native Machine Code)       |  |  |
|  |  | multiplier: Float      |      | movq, mulsd, test, jnz      |  |  |
|  |  +------------------------+      +-----------------------------+  |  |
|  +-------------------------------------------------+-----------------+  |
|                                                    |                    |
+----------------------------------------------------|--------------------+
                                                     |
                                                     v
                                          +---------------------+
                                          | Hardware CPU Core   |
                                          | Registers & SSE/AVX |
                                          +---------------------+
```

---

### 9. Simple Example

Menginspeksi bytecode mentah YARV dan membaca alur manipulasi tumpukan (*stack manipulation*):

```ruby
# Simpan kode berikut sebagai iseq_inspector.rb
code = <<~RUBY
  def calculate_discount(price, voucher)
    if voucher
      price - (price * 0.20)
    else
      price
    end
  end
RUBY

# Kompilasi kode sumber langsung ke InstructionSequence
iseq = RubyVM::InstructionSequence.compile(code)

# Disassemble untuk melihat representasi bytecode YARV manusiawi
puts iseq.disasm
```

Output representatif:

```text
== disasm: #<ISeq:<compiled>@<compiled>:1 (0,0)-(8,3)> (catch: false)
0000 definemethod          :calculate_discount, calculate_discount
0003 putspecialobject      3
0005 leave

== disasm: #<ISeq:calculate_discount@<compiled>:1 (1,0)-(7,5)> (catch: false)
local table (size: 2, argc: 2 [opts: 0, rest: -1, post: 0, block: -1, kw: -1@-1, kwrest: -1])
[ 2] price@0    [ 1] voucher@1
0000 getlocal_WC_0        voucher@1
0002 branchunless         16
0004 getlocal_WC_0        price@0
0006 getlocal_WC_0        price@0
0008 putobject            0.2
0010 opt_mult             <calldata!argc:1, flags:ARGS_SIMPLE>
0012 opt_minus            <calldata!argc:1, flags:ARGS_SIMPLE>
0014 leave
0016 getlocal_WC_0        price@0
0018 leave
```

**Analisis Alur Eksekusi**:
* `getlocal_WC_0 voucher@1`: Mengambil argumen `voucher` dari *control frame* kedalaman nol (*Window Counter 0*) dan mendorongnya ke tumpukan.
* `branchunless 16`: Melompat langsung ke alamat offset `0016` jika nilai di tumpukan adalah `false` atau `nil`.
* `opt_mult` dan `opt_minus`: Merupakan instruksi operasional teroptimasi YARV yang dilengkapi *inline cache slot* untuk operasi matematika dasar.

---

### 10. Practical Example

Pola implementasi monomorphic design vs polymorphic design untuk mencegah *Inline Cache Thrashing* dan memaksimalkan *JIT compilation stability*:

```ruby
# frozen_string_literal: true
require 'benchmark'

# SKENARIO A: Megamorphic Call-Site (Menghancurkan Inline Cache)
class EmailNotification
  def notify(recipient)
    "EMAIL:#{recipient}"
  end
end

class SMSNotification
  def notify(recipient)
    "SMS:#{recipient}"
  end
end

class PushNotification
  def notify(recipient)
    "PUSH:#{recipient}"
  end
end

class WebhookNotification
  def notify(recipient)
    "HOOK:#{recipient}"
  end
end

# SKENARIO B: Monomorphic Call-Site (Ramah YARV & YJIT)
class UnifiedNotification
  attr_reader :channel

  def initialize(channel)
    @channel = channel
  end

  def notify(recipient)
    case @channel
    when :email then "EMAIL:#{recipient}"
    when :sms   then "SMS:#{recipient}"
    when :push  then "PUSH:#{recipient}"
    else             "HOOK:#{recipient}"
    end
  end
end

# Setup workload
ITERATIONS = 5_000_000

polymorphic_handlers = [
  EmailNotification.new,
  SMSNotification.new,
  PushNotification.new,
  WebhookNotification.new
]

monomorphic_handlers = [
  UnifiedNotification.new(:email),
  UnifiedNotification.new(:sms),
  UnifiedNotification.new(:push),
  UnifiedNotification.new(:webhook)
]

recipient = "ops@enterprise.internal"

Benchmark.bm(24) do |x|
  x.report("Polymorphic Dispatch:") do
    i = 0
    while i < ITERATIONS
      # Receiver berganti tipe di setiap iterasi -> Inline Cache selalu gagal (miss)
      handler = polymorphic_handlers[i & 3]
      handler.notify(recipient)
      i += 1
    end
  end

  x.report("Monomorphic Dispatch:") do
    i = 0
    while i < ITERATIONS
      # Receiver selalu berkelas UnifiedNotification -> Inline Cache stabil (hit)
      handler = monomorphic_handlers[i & 3]
      handler.notify(recipient)
      i += 1
    end
  end
end
```

---

### 11. Real World Example

**Studi Kasus: Optimalisasi Throughput Engine Validasi Finansial High-Volume**

Sebuah platform pemrosesan klaim asuransi memproses 35.000 transaksi/detik via kluster Ruby on Rails. Engine evaluasi aturan (*rules engine*) mereka mengalami lonjakan latensi P99 akibat kompilasi dinamis dengan `eval` dan fragmentasi alokasi instruksi.

#### Arsitektur Evaluasi Aturan Lama (Penyebab Bottleneck)
Metode evaluasi lama mengevaluasi aturan berbasis string secara dinamis:
```ruby
# PROBLEM: Menyebabkan re-parsing ISeq konstan & mematikan fungsi YJIT
def evaluate_risk(payload, rule_expression)
  eval(rule_expression) # Mengompilasi ISeq baru pada setiap pemanggilan!
end
```

#### Solusi Arsitektur Baru (YARV Pre-compiled + YJIT Tuned)
Aturan dikompilasi satu kali ke ISeq terisolasi di memori, disimpan dalam registry terstruktur, dan dieksekusi secara native melalui method definition terisolasi:

```ruby
# frozen_string_literal: true

class CompiledRulesEngine
  RuleContext = Struct.new(:amount, :country, :risk_score, keyword_init: true)

  def initialize
    @registry = {}
  end

  def register_rule(rule_id, expression_string)
    method_name = :"eval_rule_#{rule_id}"
    
    # Kompilasi expression ke dalam metode terisolasi pada modul dinamis
    # Memungkinkan YARV mengunci Inline Cache dan YJIT mengompilasinya ke Machine Code
    code = <<~RUBY
      def #{method_name}(ctx)
        #{expression_string}
      end
    RUBY

    iseq = RubyVM::InstructionSequence.compile(code, "(rule_#{rule_id})", nil, 1, {
      inline_const_cache: true,
      peephole_optimization: true,
      specialized_instruction: true,
      operands_unification: true
    })
    
    iseq.eval
    @registry[rule_id] = method_name
  end

  def execute_rule(rule_id, context)
    method_name = @registry.fetch(rule_id)
    send(method_name, context)
  end
end

# Inisialisasi Engine
engine = CompiledRulesEngine.new
engine.register_rule("HIGH_RISK_TX", "ctx.amount > 10_000 && ctx.country == 'ID' && ctx.risk_score >= 80")

context = CompiledRulesEngine::RuleContext.new(amount: 15_000, country: 'ID', risk_score: 95)

# Eksekusi teroptimasi
puts "Hasil Validasi: #{engine.execute_rule("HIGH_RISK_TX", context)}"
```

#### Metrik Hasil Produksi
* **Throughput**: Naik dari 2.100 req/sec per node menjadi 4.850 req/sec per node.
* **P99 Latency**: Turun dari 82ms ke 14ms.
* **CPU Saturation**: Menurun rata-rata 38% berkat stabilitas *Instruction Cache* CPU dan eliminasi alokasi parser Bison di setiap eksekusi transaksi.

---

### 12. Trade-offs

| Aspek | YARV Interpreter Murni | YJIT Enabled (`--yjit`) |
| :--- | :--- | :--- |
| **Throughput (RPS)** | Baseline (1.0x). | Meningkat signifikan (1.15x s/d 1.40x) pada beban kerja CPU-bound. |
| **Warmup Latency** | Instan (tanpa fase adaptasi kompilasi). | Memerlukan fase pemanasan (beberapa ribu pemanggilan metode). |
| **Memory Footprint**| Sangat efisien, deterministik. | Membutuhkan memori ekstra untuk *Executable Code Cache* (+20% s/d +40% RSS). |
| **Debugging Complexity**| Sederhana; stacktrace mencerminkan baris kode langsung. | Rumit ketika terjadi *crash* di level kode assembly/JIT frame. |
| **Cold Starts (Serverless/CLI)**| Unggul; sangat cepat untuk proses berdurasi pendek. | Tidak disarankan; latensi kompilasi memperlambat waktu eksekusi total. |

---

### 13. When To Use

* **Layanan Web Long-Running**: Aplikasi Rails, Sinatra, atau Roda yang berjalan menggunakan server web berbasis proses/fork (Puma, Falcon).
* **High-Throughput Microservices**: Servis perutean data, validasi skema, transformator payload JSON masif.
* **Batch Processing Jobs**: Pekerjaan Sidekiq yang memproses jutaan item komputasional murni (matematika, evaluasi string, filtering).

---

### 14. When NOT To Use

* **CLI Tools & Scripting Otomasi**: Perintah baris perintah (CLI) yang berjalan kurang dari 1 detik (misalnya utilitas terminal harian). YJIT akan menambah overhead tanpa sempat mengompilasi *hot code*.
* **Memory-Constrained Containers**: Container edge computing atau embedded environment dengan alokasi RAM ketat (< 128MB).
* **Workload yang Dominan I/O (Pure Database/Network Wait)**: Jika 95% latensi berasal dari kueri PostgreSQL atau panggilan API pihak ketiga, optimalisasi bytecode tidak akan menghasilkan peningkatan performa yang dapat diukur secara signifikan.

---

### 15. Common Mistakes

#### 1. Melakukan Dynamic Invalidation pada Hot Paths
Memodifikasi struktur kelas secara dinamis merusak cache global YARV:
```ruby
# BURUK: Merusak Global Method State Serial, menghapus cache metode seluruh VM!
def handle_request(klass)
  klass.include(AuditLogging) # Mutasi kelas saat runtime membatalkan SEMUA inline cache!
  klass.new.process
end

# BAIK: Komposisi statis
def handle_request(service)
  AuditLogger.wrap(service).process
end
```

#### 2. Menjalankan YJIT Tanpa Menyesuaikan Executable Memory Size
Membiarkan parameter ukuran memori YJIT pada nilai default di sistem dengan throughput tinggi dapat menyebabkan YJIT kehabisan memori kompilasi (*code cache exhausted*) dan beralih permanen ke mode interpreter lambat.

#### 3. Menggunakan Polymorphic Block Callbacks di Loop Intensif
Mengirim tipe receiver yang berbeda-beda secara acak ke dalam satu blok pemanggilan method yang sama, menyebabkan pembatalan optimasi YJIT LBBV.

---

### 16. Best Practices (Production Checklist)

- [ ] **Alokasi Code Cache Terkalibrasi**: Tentukan `--yjit-exec-mem-size=64` (default 64MB) atau lebih besar (misal 128MB) jika ukuran basis kode Anda sangat besar.
- [ ] **Gunakan Jemalloc**: Selalu gunakan allocator `jemalloc` (`LD_PRELOAD=/usr/lib/libjemalloc.so`) saat mengaktifkan YJIT guna mencegah fragmentasi memori RSS akibat alokasi native memory bersamaan.
- [ ] **Frozen String Literal**: Terapkan `# frozen_string_literal: true` di seluruh file untuk mengubah instruksi `putstring` (alokasi objek baru) menjadi `putobject` (pengambilan objek yang dibekukan dari ISeq literal table).
- [ ] **Monitor Deoptimasi**: Ekspor metrik `RubyVM::YJIT.runtime_stats` secara berkala ke APM (Datadog/Prometheus) untuk mendeteksi lonjakan rasio `ratio_in_yjit` vs `invalidated_page_count`.
- [ ] **Hindari Metaprogramming Runtime**: Hindari `define_method` atau `class_eval` yang dieksekusi terus-menerus di dalam alur permintaan HTTP aktif.

---

### 17. Troubleshooting

#### 1. Deteksi Deoptimasi Berlebih (JIT Bailouts)
Ketika throughput menurun padahal YJIT aktif, evaluasi status metrik internal:

```ruby
# diagnosis_yjit.rb
if defined?(RubyVM::YJIT) && RubyVM::YJIT.enabled?
  stats = RubyVM::YJIT.runtime_stats
  
  compiled = stats[:compiled_iseq_count]
  invalidation = stats[:invalidation_count]
  yjit_ratio = stats[:ratio_in_yjit]

  puts "Compiled ISeqs    : #{compiled}"
  puts "Invalidations     : #{invalidation}"
  puts "Executions in JIT : #{yjit_ratio.round(2)}%"

  if yjit_ratio < 20.0
    warn "[WARNING] YJIT code coverage sangat rendah. Periksa polymorphic call-sites atau code cache limits."
  end
else
  puts "YJIT tidak aktif. Jalankan dengan: ruby --yjit"
end
```

#### 2. Bytecode Inspection untuk Memory Leak pada Closures
Jika sebuah blok mempertahankan referensi objek yang seharusnya di-collect GC, periksa tabel lokal ISeq:

```ruby
def leak_generator
  large_payload = "X" * 100_000_000
  -> { puts "ping" } # Apakah large_payload tertahan di control frame?
end

closure = leak_generator
iseq = RubyVM::InstructionSequence.of(closure)
puts iseq.disasm # Amati apakah 'large_payload' terdaftar di tabel variabel lokal ISeq
```

---

### 18. Exercise

#### Instruksi Pengerjaan:
1. Buat file bernama `exercise_iseq.rb`.
2. Tulis sebuah metode `math_ops(x, y)` yang menerima dua parameter dan mengembalikan hasil operasi `(x * y) + (x - y)`.
3. Gunakan `RubyVM::InstructionSequence` untuk mengekstrak struktur instruksi dari metode tersebut ke dalam array terstruktur.
4. Filter dan cetak seluruh instruksi yang berawalan `opt_` (optimised instructions).
5. Buktikan secara empiris bahwa mengganti operator aritmatika dengan *dynamic send* (`x.public_send(:*, y)`) mengubah opcode YARV dari `opt_mult` menjadi `opt_send_without_block`.

---

### 19. Challenge

Rancang sebuah class Ruby bernama `BytecodeGuard` yang menerima sebuah blok kode. `BytecodeGuard` harus:
1. Menganalisis ISeq dari blok yang diberikan sebelum dieksekusi.
2. Memeriksa apakah di dalam ISeq tersebut terdapat pemanggilan metode terlarang (misalnya: tidak boleh memuat instruksi `opt_send_without_block` dengan target metode `:eval`, `:send`, atau mutasi global).
3. Jika blok dinyatakan *bersih* (safe pure computational instructions), eksekusi blok tersebut. Jika terdeteksi instruksi terlarang, lempar exception `SecurityError` sebelum kode sempat dijalankan.

#### Solusi Implementasi Challenge:

```ruby
# frozen_string_literal: true

class BytecodeGuard
  class ExecutionForbiddenError < StandardError; end

  DISALLOWED_CALLS = [:eval, :send, :__send__, :public_send, :instance_eval].freeze

  def self.execute_safe(proc_target)
    raise ArgumentError, "Harus menyediakan Proc" unless proc_target.is_a?(Proc)

    iseq = RubyVM::InstructionSequence.of(proc_target)
    validate_iseq!(iseq)

    # Eksekusi aman setelah verifikasi lolos
    proc_target.call
  end

  private_class_method def self.validate_iseq!(iseq)
    # Dekonstruksi ISeq menjadi format array data mentah
    # Format array: [magic, major_version, minor_version, format_type, misc, label, path, absolute_path, first_lineno, type, locals, args, catch_table, bytecode]
    raw_data = iseq.to_a
    instructions = raw_data[13]

    instructions.each do |instruction|
      # Lewati label trace atau baris penanda (non-array elements)
      next unless instruction.is_a?(Array)

      opcode = instruction[0]

      # Periksa pemanggilan method via send
      if opcode.to_s.start_with?("opt_send_without_block", "send")
        call_data = instruction[1]
        method_name = call_data[:mid]

        if DISALLOWED_CALLS.include?(method_name)
          raise ExecutionForbiddenError, "Pelanggaran Keamanan: Terdeteksi instruksi opcode '#{opcode}' memanggil '#{method_name}'"
        end
      end

      # Rekursi jika terdapat nested closure (anak ISeq)
      instruction.each do |operand|
        if operand.is_a?(Array) && operand[0] == "YARVInstructionSequence/SimpleDataFormat"
          nested_iseq = RubyVM::InstructionSequence.load_from_binary(
            RubyVM::InstructionSequence.compile(operand.to_s).to_binary
          )
          validate_iseq!(nested_iseq)
        end
      end
    end
  end
end

# --- Verifikasi Proteksi Keamanan ---

safe_task = -> {
  a = 10
  b = 20
  a * b + 100
}

malicious_task = -> {
  target = "pwned"
  Kernel.send(:puts, target)
}

puts "1. Menjalankan Safe Task:"
result = BytecodeGuard.execute_safe(safe_task)
puts "Hasil: #{result}" # Berhasil berjalan

puts "\n2. Menjalankan Malicious Task:"
begin
  BytecodeGuard.execute_safe(malicious_task)
rescue BytecodeGuard::ExecutionForbiddenError => e
  puts "Berhasil Dihentikan: #{e.message}"
end
```

---

### 20. Summary

1. **YARV Execution Model**: CRuby mentransformasikan kode Ruby menjadi format perantara berbasis tumpukan (*stack-based Intermediate Representation*) yang disebut Instruction Sequence (ISeq). Eksekusi dilakukan melalui loop kontrol VM yang sangat bergantung pada efisiensi manipulasi tumpukan (*push/pop*).
2. **Inline Caching**: Performa tinggi pada YARV bersandar pada kemampuan *Inline Cache* (IC) untuk merekam tipe kelas receiver pada *call-site*. Penulisan kode yang mempertahankan konsistensi tipe (*monomorphic dispatch*) menjamin efisiensi eksekusi dan mencegah pencarian tabel metode berulang.
3. **YJIT & LBBV**: YJIT mengakselerasi Ruby secara signifikan dengan memanfaatkan *Lazy Basic Block Versioning*. Kompilasi ke kode assembly dilakukan tepat pada saat blok kode dieksekusi, dengan mengasumsikan stabilitas tipe data runtime.
4. **Production Engineering**: Untuk beban kerja komputasional tinggi, aktifkan YJIT (`--yjit`), pasangkan dengan alokator memori `jemalloc`, atur alokasi `--yjit-exec-mem-size` sesuai kapasitas beban, dan hindari mutasi struktur kelas secara dinamis (*runtime monkey patching*) yang membatalkan cache instruksi secara global.