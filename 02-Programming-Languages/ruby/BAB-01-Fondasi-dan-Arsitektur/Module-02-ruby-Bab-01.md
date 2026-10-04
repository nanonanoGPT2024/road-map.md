# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menganalisis siklus hidup eksekusi kode Ruby di dalam YARV (*Yet Another Ruby VM*), mulai dari *tokenization*, *Abstract Syntax Tree* (AST), kompilasi *instruction sequences* (ISeq), hingga eksekusi *bytecode*.
- Membedah arsitektur internal memori Ruby: struktur `RVALUE`, alokasi slot pada heap, *Generational Garbage Collection* (3.x RGenGC), *Compacting GC*, dan integrasi *custom allocator* (`jemalloc`).
- Merancang dan mengimplementasikan metaprogramming tingkat lanjut secara aman melalui eksploitasi *Eigenclass* (*Singleton Class*), manipulasi *Method Lookup Chain*, serta isolasi modifikasi menggunakan *Refinements*.
- Menguasai model konkurensi dan paralelisme Ruby modern: membedah batas mekanis *Global VM Lock* (GVL/GIL), utilisasi *Fiber Scheduler* untuk *non-blocking asynchronous I/O*, dan arsitektur *share-nothing* berbasis *Ractor*.
- Melakukan profil performa, mitigasi *memory fragmentation*, mengoptimalkan *inline method cache*, serta mengonfigurasi *Ruby JIT* (YJIT) untuk beban kerja produksi berskala *enterprise*.

---

## 2. Prerequisite

Untuk menguasai modul ini secara optimal, Anda wajib memahami:
- Sintaksis dasar hingga menengah Ruby (Block, Proc, Lambda, Module, Mixin, Class inheritance).
- Konsep dasar *Computer Systems*: Stack vs. Heap memory, Threading, POSIX signals, I/O multiplexing (`epoll`/`kqueue`).
- Pemahaman dasar arsitektur runtime (interpreter, virtual machine berbasis stack vs. register).
- Terbiasa menggunakan alat bantu baris perintah: `gdb`/`lldb`, `strace`, dan utilitas profiling sistem operasi.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Objek dan Heap Memory: RVALUE & Flags
Di dalam implementasi MRI (CRuby), semua objek direpresentasikan oleh struktur C berukuran tetap sebesar 40 byte (pada arsitektur 64-bit) yang disebut `RVALUE`.

```c
// Representasi konseptual struktur internal RVALUE pada MRI
typedef struct RVALUE {
    union {
        struct RBasic  basic;
        struct RObject object;
        struct RClass  klass;
        struct RString string;
        struct RArray  array;
        // ... tipe data internal lainnya
    } as;
} RVALUE;

struct RBasic {
    VALUE flags; // Menyimpan tipe (T_OBJECT, T_STRING, dsb) & garbage collection flags
    VALUE klass; // Pointer ke Class atau Singleton Class (Eigenclass)
};
```

Setiap objek Ruby di-pass by reference sebagai tipe `VALUE` (pointer selebar register `uintptr_t`). Ruby menerapkan teknik **Pointer Tagging / Immediate Values**:
- Nilai integer kecil (*Fixnum*), `true`, `false`, `nil`, dan `Symbol` tidak mengalokasikan slot memori pada heap Ruby.
- Jika bit LSB bernilai `1`, maka `VALUE` tersebut adalah `Integer` langsung (`value = (raw >> 1)`), menghindari alokasi heap (`0x1` untuk tag).

Untuk objek yang melampaui kapasitas 40 byte (misal: String panjang), slot `RVALUE` hanya menyimpan pointer menuju alokasi *system heap* (`malloc`). Namun, untuk string pendek (≤ 23 byte), Ruby menggunakan optimasi **Embedded String** (RSTRING_NOEMBED flag tidak aktif), di mana data string disimpan langsung di dalam sisa byte struktur `RVALUE` tanpa alokasi heap sekunder.

### 3.2. YARV (Yet Another Ruby VM) Execution Pipeline
Eksekusi kode Ruby melalui 4 fase deterministik:
1. **Tokenize & Lex**: Source code dipecah menjadi stream token oleh parser berbasis Ripper / Prism.
2. **Parsing (LALR-1)**: Token diorganisasikan menjadi *Abstract Syntax Tree* (AST) menggunakan grammar definisi Bison.
3. **Bytecode Compilation**: AST dikompilasi menjadi `RubyVM::InstructionSequence` (YARV Bytecode).
4. **Stack Execution Machine**: YARV mengeksekusi instruksi bytecode berbasis stack. Frame eksekusi dialokasikan pada *machine stack* dan *Ruby internal stack* (`rb_control_frame_t`).

```
+-------------+      +---------+      +-----+      +---------------+      +----------+
| Source Code | ---> | Lexer   | ---> | AST | ---> | Bytecode      | ---> | YARV VM  |
| (*.rb)      |      | (Prism) |      |     |      | (ISeq Arrays) |      | Executor |
+-------------+      +---------+      +-----+      +---------------+      +----------+
                                                                                |
                                                                       +--------v--------+
                                                                       | Machine Stack / |
                                                                       | Control Frames  |
                                                                       +-----------------+
```

### 3.3. Metaprogramming & Method Lookup Path
Resolusi metode pada Ruby mengikuti aturan pencarian traversal pointer linier yang sangat kaku, tetapi dinamis via *Eigenclass*.

Jika metode `.execute()` dipanggil pada objek `obj`, traversal dilakukan sebagai berikut:
1. Masuk ke **Singleton Class** (Eigenclass) dari instance `obj` (jika ada).
2. Periksa modul yang di-`prepend` pada class `obj`.
3. Periksa definisi instan di class `obj`.
4. Periksa modul yang di-`include` pada class `obj` (urutan terbalik dari deklarasi include).
5. Naik ke superclass dan ulangi pencarian modul prepend, include, dan class.
6. Berakhir di `Object`, `Kernel`, dan `BasicObject`.
7. Jika tidak ditemukan, balik kembali ke titik awal untuk mengeksekusi `method_missing`.

**Inline Method Caching:**
Untuk menghindari penelusuran traversal berulang yang memicu latensi tinggi, YARV mengimplementasikan *Inline Method Caching* (Monomorphic, Polymorphic, dan Megamorphic cache). Ketika sebuah metode didefinisikan ulang atau modul baru di-include pada runtime, Ruby menaikkan global serial number (`ruby_vm_global_method_state`), yang memvalidasi atau membatalkan seluruh inline cache di seluruh VM.

### 3.4. Concurrency: GVL, Fiber Scheduler, dan Ractor
- **Global VM Lock (GVL):** Memproteksi struktur data internal VM dan eksekusi C API dari kondisi *race condition*. GVL menjamin hanya ada **satu thread sistem operasi yang mengeksekusi YARV bytecode pada satu waktu per instance VM**. Saat thread melakukan operasi I/O blocking (misal: read socket, sleep), thread melepaskan GVL sehingga thread Ruby lain dapat mengambil alih alokasi CPU.
- **Fiber Scheduler (Ruby 3.0+):** Mengubah *execution loop* asynchronous menggunakan *cooperative light-weight concurrency*. Event loop (seperti `io_uring` atau `epoll`) mengintersepsi blocking I/O dan melakukan *context switch* otomatis antar Fiber tanpa mengunci thread OS.
- **Ractor (Ruby 3.0+):** Mengabstraksi konkurensi berbasis *Actor Model*. Setiap Ractor memiliki GVL-nya sendiri, memori heap terisolasi, dan berkomunikasi secara eksklusif menggunakan pesan *pass-by-value* atau transfer *ownership*, memungkinkan utilisasi multi-core CPU secara paralel penuh di Ruby.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional / Pemula | Pendekatan Enterprise / Lanjutan |
| :--- | :--- | :--- |
| **Object Lifecycle** | Mengandalkan pembuatan objek dinamis secara bebas tanpa memedulikan alokasi heap. | Optimasi *object retention*, utilisasi *in-place mutation*, pemanfaatan frozen string, dan audit `ObjectSpace`. |
| **Metaprogramming** | Eksekusi dinamis menggunakan `eval`, modifikasi *monkey-patching* terbuka di runtime. | *Class-level code generation*, pemanfaatan `Module#prepend`, dan isolasi menggunakan `Refinements`. |
| **Konkurensi I/O** | Multi-threading klasik berbasis OS Threads (`Thread.new`) yang terjegal *contention* GVL. | Implementasi *Fiber Scheduler* (`Async` framework) untuk menangani jutaan concurrent socket. |
| **Paralelisme CPU** | Multi-process tradisional (Fork-Worker) yang boros memori fisik sistem. | *Ractor pipeline* dengan alokasi memori terisolasi dan *zero-copy message passing*. |
| **Memory Management** | Menggunakan allocator default OS (`glibc malloc`) dengan konfigurasi GC standar. | Integrasi `jemalloc` untuk mitigasi fragmentasi heap dan penyesuaian GC Generational/Compacting. |

Mengapa memahami arsitektur internal ini sangat kritikal? Di level enterprise, Ruby tidak hanya melayani skenario prototipe sederhana. Pada skala sistem dengan puluhan ribu *request per second* (RPS), overhead alokasi memori dan invalidasi cache mikro dapat melipatgandakan *bill* infrastruktur komputasi cloud dan memicu latensi P99 yang destruktif.

---

## 5. How (Workflow Detail)

Berikut adalah alur eksekusi internal saat memanggil metode hingga level instruksi mesin YARV:

```
[Pemanggilan Metode: obj.process_data]
                 |
                 v
[Periksa Global Cache & Inline Cache Call-site]
        |                               |
  (Cache Hit)                      (Cache Miss)
        |                               |
        |                  [Telusuri Method Lookup Chain]
        |                  (Eigenclass -> Modules -> Superclass)
        |                               |
        |                  [Catat Method Entry & Perbarui Inline Cache]
        |<------------------------------+
        |
        v
[Evaluasi Jenis Call: C-Extension atau Ruby ISeq?]
        |
        +-----> (Ruby ISeq) ---> [Alokasi rb_control_frame_t pada Ruby Stack]
        |                               |
        |                        [Eksekusi Bytecode YARV via Stack Machine]
        |                               |
        +-----> (C Function) --> [Lepas GVL jika memanggil Blocking I/O]
                                        |
                                 [Eksekusi Native Code]
                                        |
                                 [Akuisisi kembali GVL]
                                        |
                                        v
                            [Kembalikan VALUE Hasil]
```

### Langkah Konfigurasi Memory Allocator Produksi (`jemalloc`):
1. Compile Ruby dengan linking eksplisit terhadap `libjemalloc`:
   ```bash
   ./configure --with-jemalloc --disable-install-doc --enable-yjit
   make && make install
   ```
2. Pastikan binary me-load jemalloc:
   ```bash
   ruby -rrbconfig -e 'puts RbConfig::CONFIG["MAINLIBS"]'
   # Output harus mencakup: -ljemalloc
   ```
3. Set environment variable untuk meminimalkan *dirty pages*:
   ```bash
   export MALLOC_CONF="background_thread:true,metadata_thp:auto,dirty_decay_ms:30000,muzzy_decay_ms:30000"
   ```

---

## 6. Analogy & Diagram ASCII

### 6.1. Diagram Hierarki Eigenclass & Metaprogramming Lookup
Setiap objek Ruby memiliki kelas tersembunyi (*Eigenclass/Singleton Class*). Class itu sendiri adalah objek dari `Class`.

```
                    +--------------------+
                    |    BasicObject     |
                    +--------------------+
                              ^
                              |
                    +--------------------+
                    |       Object       |
                    +--------------------+
                              ^
                              |
                    +--------------------+
                    |       Device       |
                    +--------------------+
                              ^
                              |
                    +--------------------+
                    |     SmartPhone     |
                    +--------------------+
                              ^
                              |
                        (instantiation)
                              |
     #phone_a --------> [ phone_a Instance ]
        |
     (eigenclass)
        |
        v
+-----------------------------+
| #<Class:#<SmartPhone:...>>  | (Tempat singleton method phone_a hidup)
+-----------------------------+
```

### 6.2. YARV: Model Frame Stack Eksekusi
YARV beroperasi menggunakan *Evaluation Stack*:

```
          YARV Evaluation Stack                Operation (Bytecode)
     +------------------------------+
Top  |             20               |   <- Nilai kedua di-push (putobject 20)
     +------------------------------+
     |             10               |   <- Nilai pertama di-push (putobject 10)
     +------------------------------+
                   ||
                   || Instruksi: 'opt_plus'
                   \/
     +------------------------------+
Top  |             30               |   <- Hasil evaluasi penjumlahan
     +------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Verifikasi Bytecode YARV
Melihat representasi instruksi internal Ruby menggunakan modul bawaan `RubyVM::InstructionSequence`.

```ruby
# script/disassemble.rb
code = <<~RUBY
  def calculate(x, y)
    x + y
  end
RUBY

iseq = RubyVM::InstructionSequence.compile(code)
puts iseq.disasm
```
*Output Logika Instruksi YARV:*
```text
== disasm: #<ISeq:<compiled>@<compiled>:1>================================
0000 definemethod                           :calculate, calculate
0003 putspecialobject                       1
0005 leave

== disasm: #<ISeq:calculate@<compiled>:1>=================================
local table (size: 2, argc: 2 [opts: 0, rest: -1, post: 0, block: -1, kw: -1@-1, kwrest: -1])
[ 2] x@0        [ 1] y@1
0000 getlocal_WC_0                          x@0
0002 getlocal_WC_0                          y@1
0004 opt_plus                               <calldata!mid:+, argc:1, ARGS_SIMPLE>
0006 leave
```

### Practical Example: High-Throughput Non-Blocking Event Bus Menggunakan Fiber
Menerapkan konkurensi non-blocking menggunakan Fiber Scheduler untuk memproses pesan tanpa overhead *heavy OS threading*.

```ruby
# lib/event_engine.rb
# frozen_string_literal: true

require 'fiber'
require 'socket'

class AsyncEventEngine
  def initialize
    @queue = Thread::Queue.new
    @running = false
  end

  def start
    @running = true
    # Menggunakan Ruby 3 Fiber scheduler context
    Fiber.new do
      puts "[Engine] Fiber Event Loop dimulai pada Thread: #{Thread.current.object_id}"
      while @running || !@queue.empty?
        if (event = @queue.pop(true) rescue nil)
          process_event(event)
        else
          # Yield kontrol eksekusi ke fiber worker lain
          Fiber.yield
        end
      end
    end.resume
  end

  def publish(event)
    @queue.push(event)
  end

  def stop
    @running = false
  end

  private

  def process_event(event)
    # Operasi terisolasi
    puts "[Process] Event received: #{event[:type]} | Payload: #{event[:data]}"
  end
end

# Simulasi Eksekusi
engine = AsyncEventEngine.new
engine.start

10.times do |i|
  engine.publish({ type: "ORDER_CREATED", data: { id: i + 100 } })
end

engine.stop
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Webhook Ingestion Engine pada Sistem Gateway Pembayaran
- **Volume Trafik:** 45.000 HTTP Webhooks/detik saat jam sibuk.
- **Problem Statement:** Server mengalami lonjakan memori (Memory Bloat) dari 800MB menjadi 14GB dalam waktu kurang dari 2 jam. Karakteristik ini memaksa orkestrator Kubernetes melakukan *OOM Kill* secara periodik. Latensi respons P99 melonjak hingga 4.8 detik akibat *Stop-The-World* (STW) *Major GC Pause*.
- **Root Cause Analysis:**
  1. Penggunaan `ActiveSupport::Notifications` yang tidak tepat menyebabkan jutaan string dynamic symbol terus dibuat, memicu *Object Retention* di luar kontrol pada heap Ruby.
  2. Fragmentasi memori masif pada alokator default C-library (`glibc ptmalloc3`), di mana memori yang dilepaskan Ruby GC tidak dikembalikan ke OS.
  3. Modifikasi dinamis runtime (*Monkey Patching* pada setiap serialisasi payload) mengakibatkan *Inline Method Cache* rusak, memaksa YARV melakukan *method table traversal* penuh pada setiap request.

### Solusi Arsitektural:
1. **Penerapan Custom Memory Allocator & Compacting GC:** Mengganti allocator ke `jemalloc` dan memprogram kompresi memori secara berkala pada worker idle.
2. **Refactoring ke Refinements & Frozen Strings:** Menghapus runtime monkey-patching dan memaksa immutabilitas string di tingkat file (`# frozen_string_literal: true`).
3. **Migrasi I/O Ingestion ke Async/Fiber Architecture:** Mengganti model `Puma` traditional thread pool dengan arsitektur event-driven non-blocking engine.

### Implementasi Solusi (Core Dispatcher Module):

```ruby
# frozen_string_literal: true

module FastPaymentEngine
  # Gunakan Refinements untuk isolasi modifikasi tipe dasar
  refine Hash do
    def symbolize_fast
      transform_keys(&:to_sym)
    end
  end
end

using FastPaymentEngine

class WebhookDispatcher
  # Pre-alokasi buffer untuk mencegah re-alokasi slot RVALUE berulang
  EMPTY_PAYLOAD = {}.freeze

  def initialize
    # Trigger Compacting GC saat startup untuk defragmentasi Heap awal
    GC.compact if GC.respond_to?(:compact)
  end

  def handle_payload(raw_json_stream)
    # Memproses parsing tanpa menciptakan intermediate redundant strings
    parsed_payload = JSON.parse(raw_json_stream, symbolize_names: true)
    
    # Validasi idempotency & Dispatch
    dispatch(parsed_payload)
  end

  private

  def dispatch(payload)
    # Dispatching menggunakan dynamic method lookup yang di-cache via const mapping
    event_type = payload.fetch(:event)
    handler = HANDLER_REGISTRY.fetch(event_type) { DefaultHandler }
    handler.call(payload)
  end

  HANDLER_REGISTRY = {
    "charge.completed" => ->(p) { [:ok, 200, p[:id]] },
    "charge.refunded"  => ->(p) { [:refund, 200, p[:id]] }
  }.freeze

  class DefaultHandler
    def self.call(_payload); [:unhandled, 204, nil]; end
  end
end
```

### Hasil Metrik Produksi:
- Penurunan jejak memori (*RSS footprint*) per worker process hingga **68%** stabil di rentang ~420MB.
- Durasi GC Pause menurun drastis dari **220ms** menjadi rata-rata **14ms**.
- Throughput per node meningkat **3.8 kali lipat**, memangkas kebutuhan cluster pod dari 80 instance menjadi 22 instance.

---

## 9. Trade-offs

Setiap keputusan arsitektur di Ruby runtime memiliki konsekuensi operasional yang signifikan:

| Keputusan Arsitektur | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Fiber Scheduler (Async)** | Membutuhkan alokasi memori sangat kecil per-task; *high density* (ratusan ribu koneksi I/O simultan). | Membutuhkan dependensi library I/O non-blocking murni; *debugging stack trace* lebih kompleks. | Aplikasi dengan dominasi tinggi I/O (Microservices API Gateway, Real-time WebSockets). |
| **Ractor Parallelism** | Utilisasi penuh seluruh core prosesor tanpa proses OS terpisah (*true parallelism*). | Pembatasan ketat *shareable object*; overhead penyalinan data jika pesan berukuran besar. | Komputasi intensif CPU: image processing, hashing, kalkulasi kriptografi/finansial. |
| **GC Compaction (`GC.compact`)** | Mengurangi fragmentasi memori (*heap bloat*); mengoptimalkan performa Copy-on-Write (CoW). | Menimbulkan jeda *Stop-The-World* (STW) saat proses *pointer moving/swizzling*. | Dieksekusi secara periodik pada background worker atau pasca-forking master process web server. |
| **Metaprogramming (send/define_method)** | Sangat fleksibel, *boilerplate code* berkurang secara drastis, arsitektur *extensible*. | Merusak monomorphic inline method cache jika dieksekusi terus menerus; overhead runtime check. | Saat inisialisasi framework/boot, bukan di dalam *critical request execution path*. |
| **YJIT (Yet Another JIT)** | Peningkatan eksekusi CPU murni (15% - 40% throughput speedup pada Rails/Ruby standard). | Konsumsi memori virtual & fisik meningkat sebesar 10-25% untuk alokasi *executable code buffer*. | Server produksi dengan RAM memadai yang mengeksekusi long-running process (web server). |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Memory Leaks Melalui Symbol Creation Dinamis
- **Pola Masalah:** Melakukan parsing parameter user yang tidak dibatasi dan mengonversinya menjadi symbol secara dinamis.
  ```ruby
  # SANGAT BERBAHAYA di lingkungan produksi
  user_input_params.each { |k, v| session[k.to_sym] = v }
  ```
- **Analisis Dampak:** Meskipun Ruby modern dapat melakukan GC pada *dynamic symbols*, retensi symbol dalam hash berumur panjang (seperti Session atau In-Memory Cache) akan mencegah GC membebaskan slot heap, memicu fragmentasi memori tanpa henti.
- **Solusi:** Selalu gunakan *string keys* atau batasi key yang diperbolehkan (*whitelist validation*) sebelum konversi.

### Mistake 2: Merusak YARV Inline Method Cache
- **Pola Masalah:** Menghasilkan metode baru pada saat runtime request berjalan menggunakan `class_eval` atau `define_method`.
  ```ruby
  def track_event(name)
    # Merusak global method serial cache di seluruh thread VM!
    self.class.define_method("log_#{name}") { puts name }
    send("log_#{name}")
  end
  ```
- **Analisis Dampak:** Memanggil `define_method` memicu `ruby_vm_global_method_state++`. Seluruh *call-site* inline method cache di seluruh VM seketika invalid (*cache miss* massal). CPU membuang siklus berharga untuk melakukan pencarian ulang string method name di seluruh pohon *inheritance tree*.
- **Solusi:** Definisikan seluruh antarmuka metode saat inisialisasi aplikasi (boot phase), atau gunakan pola *Strategy Pattern / Hash of Callables*.

### Mistake 3: Kesalahan Blokade I/O di C-Extensions
- **Pola Masalah:** Memanggil fungsi C eksternal atau syscall jaringan tanpa membebaskan GVL via `rb_thread_call_without_gvl`.
- **Analisis Dampak:** Thread lain di aplikasi Ruby tidak dapat dieksekusi sama sekali meskipun prosesor memiliki multi-core idle. Aplikasi mengalami *hang* lokal.
- **Troubleshooting:**
  Gunakan tool `rbspy` atau `gdb` untuk membedah stack trace native process:
  ```bash
  # Rekam stack trace dari proses ruby yang terindikasi deadlock/blocking
  rbspy record --pid <PID>
  
  # Periksa syscall yang sedang menahan thread menggunakan strace
  strace -p <PID> -f -e trace=network,poll,select
  ```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Aktifkan `frozen_string_literal: true` Secara Global:** Sisipkan komentar magic ini di setiap file source code atau pasang flag `--enable=frozen-string-literal` pada runtime untuk mengeliminasi alokasi objek duplikat.
2. [ ] **Link dengan `jemalloc`:** Pastikan distribusi binary Ruby di server/container production ter-link langsung dengan library `jemalloc`.
3. [ ] **Konfigurasi Parameter Garbage Collection:**
   ```bash
   # Rekomendasi setup kontainer produksi (RAM 2GB+)
   export RUBY_GC_HEAP_INIT_SLOTS=1000000
   export RUBY_GC_HEAP_FREE_SLOTS=500000
   export RUBY_GC_HEAP_GROWTH_FACTOR=1.25
   export RUBY_GC_MALLOC_LIMIT=64000000
   export RUBY_GC_MALLOC_LIMIT_MAX=128000000
   export RUBY_GC_OLDMALLOC_LIMIT=64000000
   export RUBY_GC_OLDMALLOC_LIMIT_MAX=128000000
   ```
4. [ ] **Aktifkan YJIT di Lingkungan Produksi:**
   ```bash
   export RUBY_YJIT_ENABLE=1
   ```
5. [ ] **Eliminasi Metaprogramming pada Critical Path:** Hindari `const_get`, `method_missing`, dan modifikasi class dinamis pada path eksekusi per-request.
6. [ ] **Implementasikan Copy-on-Write (CoW) Optimizations:** Jika menggunakan server model preforking (Puma/Unicorn), panggil `GC.compact` sebelum worker di-fork oleh master process.

---

## 12. Hands-on Practice

Buat dan jalankan modul praktikum profiling internal memori di direktori `hands-on/m02/`.

### Langkah 1: Setup Lingkungan & Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat Skrip Eksplorasi Alokasi Memori
Simpan berkas berikut dengan nama `memory_profiler.rb`. Skrip ini melakukan inspeksi mendalam terhadap struktur internal `ObjectSpace` dan dampak modifikasi objek terhadap alokasi memori.

```ruby
# hands-on/m02/memory_profiler.rb
# frozen_string_literal: true

require 'objspace'

class MemoryInspector
  def self.analyze_allocation
    # Matikan GC sementara untuk mengisolasi observasi alokasi murni
    GC.disable

    puts "--- 1. Analisis Immediate Values vs Heap Objects ---"
    fixnum_val = 42
    string_short = "short" # Embedded string (<= 23 byte)
    string_long  = "This string is significantly longer than twenty-three bytes threshold"

    puts "Fixnum VALUE Address      : 0x#{fixnum_val.object_id.to_s(16)} (Immediate Value: No Slot)"
    puts "Short String Mem Size     : #{ObjectSpace.memsize_of(string_short)} bytes"
    puts "Long String Mem Size      : #{ObjectSpace.memsize_of(string_long)} bytes"

    puts "\n--- 2. GC Stats Sebelum Eksperimen ---"
    initial_stat = GC.stat
    puts "Major GC Runs : #{initial_stat[:major_gc_count]}"
    puts "Minor GC Runs : #{initial_stat[:minor_gc_count]}"
    puts "Heap Live Slots: #{initial_stat[:heap_live_slots]}"

    puts "\n--- 3. Membangun 50.000 Objek Transien ---"
    transient_bucket = []
    50_000.times do |i|
      transient_bucket << { id: i, payload: "item_#{i}" }
    end

    mid_stat = GC.stat
    puts "Heap Live Slots (Post-Alokasi): #{mid_stat[:heap_live_slots]}"
    puts "Delta Slot Alokasi             : #{mid_stat[:heap_live_slots] - initial_stat[:heap_live_slots]}"

    # Kosongkan referensi
    transient_bucket = nil

    # Nyalakan kembali GC dan paksa Full Major Sweep
    GC.enable
    GC.start(full_mark: true, immediate_sweep: true)

    final_stat = GC.stat
    puts "\n--- 4. GC Stats Pasca Paksa Full Mark & Sweep ---"
    puts "Major GC Runs : #{final_stat[:major_gc_count]}"
    puts "Heap Live Slots: #{final_stat[:heap_live_slots]}"
    puts "Slot Terbebas : #{mid_stat[:heap_live_slots] - final_stat[:heap_live_slots]}"
  end
end

MemoryInspector.analyze_allocation
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan praktikum melalui terminal Anda:
```bash
ruby memory_profiler.rb
```
Amati selisih live slot dan perhatikan bagaimana *short string* dioptimalkan langsung di dalam struktur slot memori dibandingkan alokasi pointer string panjang.

---

## 13. Exercise

### Level Easy
Tuliskan sebuah skrip Ruby yang mengekstrak dan menampilkan *bytecode instruction* dari sebuah block lambda matematika kompleks (kombinasi operasi aritmatika dan bitwise). Gunakan `RubyVM::InstructionSequence`.
- **Target Capaian:** Mampu mengidentifikasi instruksi dasar VM: `opt_plus`, `opt_mult`, `getlocal`, dan `setlocal`.

### Level Medium
Bangun modul arsitektur *Plugin Engine* yang mengimplementasikan metodologi `Module#prepend` untuk melakukan instrumentasi waktu eksekusi (latency tracing) pada seluruh *public method* dari sebuah target class secara dinamis tanpa menggunakan `alias_method` dan tanpa merusak arsitektur pewarisan asli.
- **Target Capaian:** Pemahaman mutlak mengenai posisi `prepend` di depan target class pada *Method Lookup Chain*.

### Level Hard
Buat implementasi *worker pool* berbasis **Ractor** (minimal 4 parallel workers) yang memproses stream komputasi kalkulasi kriptografi hashing (misal: penemuan *nonce* sha256 sederhana layaknya proof-of-work). Data input dikirimkan melalui saluran `Ractor.send`, dan hasil diekstrak melalui saluran `Ractor.yield`.
- **Target Capaian:** Memastikan tidak ada error `Ractor::IsolationError` atau kebocoran state *mutable objects* antar worker execution.

---

## 14. Challenge

### Studi Kasus: Dynamic Multi-Tenant Rule Engine dengan Zero-Downtime Hot Reload

#### Deskripsi Tantangan:
Anda adalah Principal Architect pada perusahaan platform SaaS keuangan enterprise. Sistem harus mampu mengevaluasi *business rules* yang ditulis secara spesifik oleh ribuan tenant. Aturan bisnis ini dapat diperbarui kapan saja oleh tenant tanpa melakukan *restart* pada web cluster (*hot-reloading*).

#### Spesifikasi dan Batasan:
1. **Isolasi Mutlak (Sandboxing):** Evaluasi rules tiap tenant tidak boleh mencemari tenant lain. Dilarang keras memodifikasi core global scope (`Object`, `Kernel`, atau modul global lainnya).
2. **Method Cache Preservation:** Mekanisme pembaruan rules dilarang menggunakan *Monkey Patching* global yang memicu invalidasi `ruby_vm_global_method_state` secara masif di request loop utama.
3. **Thread Safety & Memory Safety:** Engine harus thread-safe di bawah beban ratusan request serentak, serta menjamin seluruh alokasi memori instance rule lama harus segera eligible untuk dibersihkan oleh Garbage Collector tanpa meninggalkan retensi pointer tak terpakai (*Zero-Leakage Retained Object*).
4. **Metrik & Audit:** Buat arsitektur pemantau yang mampu mengekspor *allocated objects count* dan *heap slot utilization* setiap kali evaluasi rules tenant dieksekusi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. Berapa ukuran memori tetap dari satu slot `RVALUE` pada arsitektur Ruby 64-bit?
2. Mengapa nilai integer kecil (*Fixnum*) tidak memakan kuota alokasi slot pada heap Ruby?
3. Sebutkan urutan traversal *Method Lookup Chain* jika suatu class memiliki deklarasi `include ModA` dan `prepend ModB` secara bersamaan!
4. Apa fungsi dari instruksi magic comment `# frozen_string_literal: true` pada tingkat alokasi memori?
5. Di fase kompilasi manakah kode sumber Ruby diubah menjadi *Instruction Sequences* (ISeq)?

### Bagian 2: Intermediate (Analisis Arsitektur)
6. Bagaimana cara kerja *Inline Method Cache* pada YARV, dan peristiwa apa saja yang dapat menyebabkan cache ini menjadi invalid?
7. Jelaskan perbedaan mendasar antara *Minor GC* dan *Major GC* dalam algoritma Generational GC (RGenGC) milik Ruby!
8. Apa yang dimaksud dengan *Pointer Tagging* dan bagaimana Ruby membedakan antara sebuah pointer referensi memori asli dengan immediate value?
9. Mengapa arsitektur berbasis Fiber (misalnya modul `Async`) mampu menangani puluhan ribu koneksi I/O simultan dengan footprint memori jauh lebih rendah dibandingkan Ruby Thread berbasis OS (`Thread.new`)?
10. Apa kegunaan utama dari fitur `GC.compact` yang diperkenalkan pada Ruby 2.7+, dan apa trade-off latensinya ketika dieksekusi?

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus A:**
    Aplikasi microservice Ruby Anda berjalan pada environment container Kubernetes dengan limit RAM 1GB. Anda mendeteksi bahwa *Resident Set Size* (RSS) proses terus meningkat perlahan setiap hari meskipun metrik `GC.stat[:heap_live_slots]` menunjukkan jumlah slot objek aktif bernilai konstan (~300.000 slots). Apa diagnosis akar permasalahan pada level sistem operasi dan bagaimana langkah solutif konkritnya?
12. **Skenario Kasus B:**
    Sebuah library logging pihak ketiga melakukan instrumentasi performa dengan membungkus metode target menggunakan:
    ```ruby
    target_class.class_eval do
      alias_method :old_exec, :exec
      def exec
        # track execution
        old_exec
      end
    end
    ```
    Library ini mengeksekusi blok kode di atas di dalam background worker secara berkala setiap 5 detik. Akibatnya, latensi P99 dari HTTP request lain di aplikasi mengalami penurunan performa drastis. Jelaskan anomali internal VM yang terjadi!
13. **Skenario Kasus C:**
    Anda memiliki proses background data worker yang mengeksekusi parsing file log berukuran 10GB. Thread mengalami hang tak berujung dan memblokir seluruh eksekusi task worker lain dalam proses yang sama, meskipun worker lain tersebut berada di dalam Thread Ruby yang berbeda. Setelah dicek, task tersebut menggunakan C-extension pihak ketiga untuk melakukan dekripsi data. Mengapa hal ini bisa membekukan seluruh thread pada proses Ruby tersebut?

---

### Kunci Jawaban Singkat & Panduan Solusi Quiz

#### Bagian 1: Basic
1. Tepat **40 byte**.
2. Karena menggunakan teknik **Immediate Values / Pointer Tagging**. Bit LSB diatur bernilai `1`, sehingga nilainya disematkan langsung di dalam pointer variabel itu sendiri (register machine) tanpa melalui dereferensi heap.
3. Urutan resolusi: `ModB` (prepend) -> `TargetClass` -> `ModA` (include) -> `Superclass`.
4. Mencegah alokasi slot `RVALUE` baru untuk string literal yang identik; memaksa string menjadi objek *immutable* yang langsung di-*deduplicate* di internal memory.
5. Pada fase kompilasi ketiga (fase transformasi dari **Abstract Syntax Tree (AST)** menjadi **Bytecode**).

#### Bagian 2: Intermediate
6. Inline cache mencatat target method entry langsung pada call-site instruksi bytecode. Invalidasi terjadi secara global jika nilai `ruby_vm_global_method_state` bertambah akibat pendefinisian metode baru, modifikasi class hierarchy, atau include/prepend modul baru pada runtime.
7. *Minor GC* hanya melakukan scan dan marking pada objek generasi muda (*young generation*), berlangsung sangat cepat. *Major GC* melakukan scanning pada seluruh objek heap termasuk generasi tua (*old generation*), memicu jeda Stop-The-World (STW) lebih panjang.
8. Pointer tagging mengeksploitasi bit-bit terbawah (LSB) dari alamat memori 64-bit yang sejajar (*aligned*). Jika bit terakhir adalah `1`, itu adalah Fixnum. Jika bit-bit penanda cocok dengan konfigurasi khusus, VM menerjemahkannya sebagai `true`, `false`, `nil`, atau `Symbol`.
9. OS Threads memakan overhead alokasi native stack (default biasanya 1MB-8MB per thread) serta context-switch mahal di level kernel CPU. Fiber berjalan di level user-space dengan stack minimal (hanya beberapa kilobyte) dan berganti konteks secara kooperatif murni saat blocking I/O.
10. `GC.compact` melakukan *Memory Compaction* (memindahkan lokasi RVALUE di heap untuk menyatukan ruang kosong/defragmentasi). Trade-off-nya adalah latensi: VM harus menghentikan seluruh proses eksekusi (STW) dan melakukan *pointer swizzling* (memperbarui seluruh referensi alamat memori objek yang berpindah).

#### Bagian 3: Skenario Kasus Produksi
11. **Diagnosis:** Fragmentasi memori eksternal pada alokator default sistem (`glibc malloc`). Slot heap Ruby telah kosong, namun alokator OS tidak dapat mengembalikan halaman memori (*dirty pages*) ke OS kernel karena adanya penguncian alokasi byte terisolasi di halaman tersebut.
    **Solusi:** Ganti alokator runtime container dengan `jemalloc` (`LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2`) dan aktifkan *background threads* untuk proses `decay/purge` memori kotor secara agresif.
12. **Diagnosis:** Penggunaan `class_eval` dan `alias_method` yang berulang secara periodik menaikkan global method state counter VM. Hal ini merusak *Inline Method Cache* di seluruh sistem secara berkesinambungan (*cache thrashing*), memaksa semua HTTP request melakukan method lookup dinamis penuh pada setiap pemanggilan method.
13. **Diagnosis:** C-extension tersebut menjalankan operasi enkripsi intensif CPU pada tataran native code C tanpa melepaskan **Global VM Lock (GVL)** melalui pemanggilan API internal `rb_thread_call_without_gvl()`. Akibatnya, tidak ada thread Ruby lain yang dapat mengambil alih alokasi waktu eksekusi VM.

---

## 16. Summary

- **YARV Stack Architecture:** Pemahaman mendalam siklus eksekusi Ruby dari AST menuju Bytecode memberikan fondasi krusial untuk mengeliminasi inefisiensi komputasi runtime.
- **Efisiensi Heap & RVALUE:** Seluruh manajemen objek Ruby bermuara pada struktur `RVALUE` 40-byte; memahami perbedaan immediate value, alokasi string tersemat (*embedded*), dan lifecycle GC sangat penting untuk memitigasi *memory bloat*.
- **Metaprogramming Terstruktur:** Metaprogramming adalah kapabilitas terkuat Ruby, namun mutasi runtime sembarangan menghancurkan *Inline Method Cache*. Modifikasi arsitektur harus dialokasikan secara aman melalui *prepend* dan *refinements*.
- **Konkurensi Skala Tinggi:** Era modern Ruby (3.x) membuka paradigma skalabilitas baru: **GVL-aware multi-threading**, **Fiber-based non-blocking asynchronous architecture**, dan **Ractor parallel execution**.
- **Standar Skala Enterprise:** Keberhasilan aplikasi Ruby di skala jutaan pengguna sangat bergantung pada pemilihan custom memory allocator (`jemalloc`), defragmentasi rutin via Compacting GC, tuning GC environment variables, serta pemanfaatan kompilasi YJIT.