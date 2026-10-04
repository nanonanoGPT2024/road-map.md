# SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** `02-Programming-Languages`
* **Track:** Ruby Enterprise Systems & Language Engineering
* **Bab:** 02 — Advanced Object-Oriented System Architecture
* **Modul:** 01 — Deep-Dive Object-Oriented Design & Metaprogramming
* **Tingkat Kesulitan:** Advanced / L4-L5
* **Prasyarat:** Pemahaman sintaksis Ruby dasar, struktur OOP konvensional (Class, Module, Inheritance), manipulasi Collection, dan pemahaman dasar *concurrency* serta *memory model* pada CRuby.
* **Estimasi Waktu Belajar:** 8 Jam (Teori, Bedah Source Code Internal, & Praktik Laboratorium)

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, software engineer diharapkan mampu:

1. **Menganalisis dan Membedah Object Model CRuby:** Menguraikan representasi memori internal dari objek, *eigenclass* (singleton class), modul, dan rantai pewarisan (*method lookup path*) pada tingkat mesin virtual MRI.
2. **Merancang Domain-Specific Language (DSL) yang Ergonomis:** Mengimplementasikan DSL deklaratif yang aman menggunakan teknik evaluasi blok (`instance_eval`, `class_eval`, dan `module_exec`) tanpa merusak lexical scoping atau mencemari *global state*.
3. **Menguasai Mekanisme Dynamic Method Generation:** Memilih dan mengimplementasikan teknik generasi metode yang tepat antara `define_method`, `method_missing` (berpasangan dengan `respond_to_missing?`), dan evaluasi runtime string/AST dengan proteksi keamanan penuh.
4. **Menerapkan Lifecycle Meta-Hooks secara Defensif:** Menggunakan hook sistem Ruby (`inherited`, `included`, `prepended`, `extended`, `method_added`) untuk membangun arsitektur plugin dan registry yang decoupled.
5. **Mengoptimalkan Performa & Memitigasi Risiko Metaprogramming:** Mengidentifikasi dan memitigasi *method cache invalidation*, kebocoran memori tabel simbol (*symbol table exhaustion*), serta celah injeksi kode pada lingkungan produksi Ruby 3.x ber-YJIT.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman berbasis Ruby tingkat lanjut, batasan statis antara "waktu kompilasi" (*compile-time*) dan "waktu eksekusi" (*runtime*) hampir sepenuhnya lebur. Paradigma yang harus diinternalisasi adalah:

> **"Di dalam Ruby, definisi sebuah class bukanlah deklarasi statis; eksekusi definisi class adalah kode aktif yang dapat bermutasi secara deterministik pada runtime."**

### Prinsip Utama Metaprogramming Ruby:
1. **Objek Menampung Data, Class Menampung Metode:** Objek hanyalah wadah untuk instance variables (`@ivars`) dan sebuah pointer ke class-nya. Objek tidak menyimpan salinan metodenya sendiri.
2. **Class adalah Objek Tingkat Pertama (First-Class Object):** Setiap class merupakan instance dari class `Class`. Artinya, class dapat dimutasi, dipassing sebagai parameter, dan didekorasi sebagaimana objek lainnya.
3. **Konsep Singleton Class (Eigenclass):** Setiap entitas objek di Ruby memiliki "bayangan class privat" (disebut *singleton class*, *eigenclass*, atau *metaclass*). Tempat inilah di mana singleton method atau per-instance behavior benar-benar hidup.
4. **Disiplin di Atas Fleksibilitas:** Kemampuan merekayasa AST dan memanipulasi method dispatch secara runtime adalah pedang bermata dua. Kode metaprogramming yang baik harus bersifat *self-documenting*, mempertahankan *stack trace* yang bersih, serta sebisa mungkin menjaga *Inline Method Cache* mesin virtual tetap optimal.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Rantai Resolusi Metode (*Method Lookup Path*)

Ketika sebuah metode dipanggil via `receiver.method_name(args)`, MRI melakukan penelusuran hierarki linier melalui struktur `RClass` berikut:

```text
[ Pemanggilan: object.do_action ]
                |
                v
       +------------------+
       | Singleton Class  | (Apakah ada def object.do_action?)
       | (Eigenclass)     |
       +------------------+
         | Tidak
         v
       +------------------+
       | Prepended Modules| (Modul-modul prepend ditelusuri dari yang terakhir)
       +------------------+
         | Tidak
         v
       +------------------+
       |  Receiver Class  | (Definisi method di dalam class penerima)
       +------------------+
         | Tidak
         v
       +------------------+
       | Included Modules | (Modul-modul include ditelusuri secara LIFO)
       +------------------+
         | Tidak
         v
       +------------------+
       |    Superclass    | (Mengulangi pola prepend -> class -> include)
       +------------------+
         | Tidak
         v
       +------------------+
       |      Object      |
       +------------------+
         | Tidak
         v
       +------------------+
       |      Kernel      |
       +------------------+
         | Tidak
         v
       +------------------+
       |   BasicObject    |
       +------------------+
         | Tidak
         v
       [ method_missing ] ---> Mengulangi seluruh rantai pencarian di atas
                                untuk mencari implementasi method_missing
```

### Diagram 2: Hubungan Pointer Objek, Class, dan Eigenclass

```text
+---------------------+
| instance = Foo.new  |
+---------------------+
  | klass pointer
  v
+---------------------+      klass pointer      +-----------------------+
|  Class: Foo         | ----------------------> | SingletonClass: #<Foo>|
+---------------------+                         +-----------------------+
  | superclass                                    | superclass
  v                                               v
+---------------------+      klass pointer      +-----------------------+
|  Class: Object      | ----------------------> | SingletonClass:       |
+---------------------+                         | #<Object>             |
  | superclass                                  +-----------------------+
  v                                               | superclass
+---------------------+      klass pointer        v
|  Class: BasicObject | ----------------------> +-----------------------+
+---------------------+                         | SingletonClass:       |
  | superclass: nil                             | #<BasicObject>        |
  v                                             +-----------------------+
(NULL)                                            | superclass
                                                  v
                                                +-----------------------+
                                                | Class: Class          |
                                                +-----------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Representasi C-Level MRI: `RBasic`, `RObject`, dan `RClass`
Pada layer C dari CRuby (MRI), seluruh entitas adalah pointer `VALUE`. Struktur data utamanya adalah:

* **`RBasic`**: Struktur terendah yang dimiliki semua objek Ruby:
  ```c
  struct RBasic {
      VALUE flags; // Menyimpan type tag, GC flags, frozen state
      const VALUE klass; // Pointer langsung ke Class atau Singleton Class
  };
  ```
* **`RObject`**: Mengalokasikan array instance variable baik secara inline (*embedded*) atau via external buffer:
  ```c
  struct RObject {
      struct RBasic basic;
      union {
          struct {
              uint32_t numiv;
              VALUE *ivptr;
              void *iv_index_tbl;
          } heap;
          VALUE ary[ROBJECT_EMBED_LEN_MAX];
      } as;
  };
  ```
* **`RClass`**: Ekstensi `RBasic` untuk entitas yang bisa menyimpan metode:
  ```c
  struct RClass {
      struct RBasic basic;
      VALUE super; // Pointer ke superclass
      rb_id_table_t *m_tbl; // Tabel metode (Symbol ID -> Method Entry)
      rb_id_table_t *const_tbl; // Tabel konstanta
      struct rb_classext_struct *ptr;
  };
  ```

### 2. Method Invalidation & Inline Cache (IC)
MRI menggunakan *Global Method Cache* dan *Inline Caches* di tingkat Virtual Machine (YARV). Ketika YARV mengeksekusi bytecode `opt_send_without_block`, ia menyimpan pointer langsung ke instruksi metode yang ditemukan sebelumnya:

* **Serial Number Invalidation:** Setiap class memiliki nomor seri internal (`class_serial_t`). 
* Mengubah kelas secara dinamis (misalnya mendefinisikan metode baru via `define_method`, memodifikasi class yang sudah ada, atau melakukan `prepend`) akan menaikkan nomor serial kelas tersebut secara global atau lokal.
* Hal ini memaksa CPU membersihkan cache VM (*cache bust*), menyebabkan pemanggilan metode berikutnya harus mengulang pencarian linear traversal melintasi rantai class hierarchy (`m_tbl`).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. `instance_eval`, `class_eval`, dan `module_exec`
Perbedaan mendasar dari metode evaluasi dinamis ini terletak pada apa yang menjadi `self` dan di mana posisi *singleton class* dalam lexical scope:

* **`instance_eval`**:
  * Mengubah `self` menjadi receiver tersebut.
  * Membuat singleton class dari receiver menjadi scope di mana metode baru didaftarkan.
  * Cocok untuk membaca instance variable internal atau membangun receiver-based DSL.
* **`class_eval` / `module_eval`**:
  * Hanya dapat dieksekusi pada receiver berupa `Module` atau `Class`.
  * Mengubah `self` menjadi class tersebut, namun pendefinisian metode reguler (`def nama_metode`) akan menempatkan metode di dalam `m_tbl` class penerima (menjadi *instance method*), bukan menjadi singleton method.
* **`module_exec` / `class_exec`**:
  * Mirip dengan `class_eval`, namun memungkinkan developer untuk meneruskan argumen dari luar closure tanpa terhalang *flat scope variable capture*.

### 2. Dynamic Dispatch: `send` vs `public_send`
* `send` mengeksekusi metode terlepas dari kontrol akses (*visibility*) metode tersebut (`public`, `protected`, maupun `private`). Hal ini berisiko melanggar enkapsulasi secara tidak sengaja.
* `public_send` menegakkan aturan enkapsulasi. Jika metode berstatus `private`, `public_send` akan memicu `NoMethodError`. Standar arsitektur mewajibkan penggunaan `public_send` kecuali jika terdapat alasan kuat untuk membypass visibilitas.

### 3. Dynamic Definition: `define_method` vs `method_missing`
* **`define_method`**:
  * Mengeksekusi pembuatan metode secara langsung pada tabel metode (`m_tbl`).
  * Menggunakan closure (`Proc`), yang berarti mengikat lingkup variabel di sekitarnya (*lexical scope closure*).
  * Menghasilkan pemanggilan metode yang sangat cepat karena terdaftar secara deterministik dan mendukung inline caching setelah initial call.
* **`method_missing`**:
  * Merupakan *fallback hook* ketika pencarian metode di seluruh rantai resolusi kelas gagal.
  * Overhead komputasi lebih tinggi karena harus melintasi seluruh tree inheritance hingga `BasicObject`.
  * **Hukum Wajib:** Setiap kali meng-override `method_missing`, developer **wajib** meng-override `respond_to_missing?` untuk menjaga konsistensi refleksi dan kompatibilitas dengan `Object#method`.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental konstruksi objek model, isolasi singleton class, dynamic method dispatching, dan runtime lifecycle hooks secara murni (*pure Ruby*):

```ruby
# frozen_string_literal: true

# Modul dekorasi tracing internal
module Traceable
  def self.prepended(base)
    # Lifecycle hook ketika modul di-prepend ke sebuah class
    puts "[HOOK: prepended] #{self} disisipkan di depan #{base}"
  end

  def execute(action)
    puts "[PREPEND TRACE] Memulai eksekusi: #{action}"
    start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    
    result = super(action) # Memanggil metode asli di receiver class
    
    duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
    puts "[PREPEND TRACE] Selesai: #{action} dalam #{duration.round(6)} detik"
    result
  end
end

class BaseJob
  # Lifecycle hook ketika class diturunkan
  def self.inherited(subclass)
    super
    puts "[HOOK: inherited] #{subclass} mewarisi #{self}"
    subclass.instance_variable_set(:@registry, {})
  end

  class << self
    attr_reader :registry

    def register_command(name, &block)
      # Dynamic method creation pada tingkat class
      @registry[name.to_sym] = block
      
      # Generasi instance method secara dinamis
      define_method("execute_#{name}") do |*args|
        handler = self.class.registry[name.to_sym]
        raise ArgumentError, "Handler tidak terdaftar" unless handler
        
        # Mengeksekusi blok dalam konteks instance saat ini
        instance_exec(*args, &handler)
      end
    end
  end

  prepend Traceable

  def execute(action)
    method_target = "execute_#{action}".to_sym
    if respond_to?(method_target)
      public_send(method_target)
    else
      super rescue method_missing(method_target)
    end
  end

  def respond_to_missing?(method_name, include_private = false)
    method_name.start_with?("execute_") || super
  end

  def method_missing(method_name, *args, &block)
    if method_name.start_with?("execute_")
      action_name = method_name.to_s.sub("execute_", "")
      raise NotImplementedError, "Perintah #{action_name} tidak diimplementasikan pada #{self.class}"
    end
    super
  end
end

class BackupJob < BaseJob
  # Menggunakan DSL yang dibuat dinamis via register_command
  register_command(:database) do
    "Menyalin cluster PostgreSQL ke S3 Storage: [SUKSES]"
  end

  register_command(:files) do
    "Mengarsipkan /var/data ke cold storage: [SUKSES]"
  end
end

# Eksekusi Fundamental Test
if __FILE__ == $PROGRAM_NAME
  job = BackupJob.new
  puts "\n--- Memulai Pengujian Dynamic Dispatch ---"
  puts job.execute(:database)
  puts "\n--- Memanggil Dynamic Direct Method ---"
  puts job.execute_files
  
  puts "\n--- Verifikasi Method Lookup Path ---"
  puts "Ancestors: #{BackupJob.ancestors.inspect}"
  
  puts "\n--- Menguji Fallback Error Handling ---"
  begin
    job.execute(:invalid_task)
  rescue NotImplementedError => e
    puts "Tertangkap error yang diharapkan: #{e.message}"
  end
end
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode implementasi Seksi 07:

1. **`module Traceable; def self.prepended(base)`**: Menangkap hook ketika module di-prepend. Berbeda dengan `included`, `prepended` menempatkan modul **sebelum** class penerima dalam rantai ancestors.
2. **`result = super(action)`**: Karena `Traceable` diprepend, pemanggilan `super` di dalam metode `execute` memicu eksekusi metode `execute` pada kelas `BaseJob`.
3. **`def self.inherited(subclass)`**: Menerima referensi instance `subclass` tepat pada saat parser mengeksekusi token `class Subclass < BaseJob`. Inisialisasi `@registry = {}` dilakukan sebelum isi kelas anak dievaluasi.
4. **`class << self`**: Membuka konteks *eigenclass* (singleton class) dari `BaseJob`. Properti atau metode yang didefinisikan di sini menjadi method class.
5. **`define_method("execute_#{name}")`**: Mengalokasikan node method entry baru pada `m_tbl` milik class. Menghindari evaluasi string yang rentan (`eval`), dan mengikat block closure.
6. **`instance_exec(*args, &handler)`**: Mengeksekusi blok kode yang didaftarkan di dalam *runtime scope* instance dari subclass. Ini memberi blok tersebut akses penuh ke `@ivars` dan private method dari objek yang bersangkutan.
7. **`prepend Traceable`**: Menyisipkan `Traceable` ke index 0 pada ancestor chain `BaseJob`.
8. **`public_send(method_target)`**: Menjalankan method routing secara aman tanpa bypass enkapsulasi Ruby.
9. **`respond_to_missing?(method_name, include_private = false)`**: Mengembalikan nilai `true` untuk format nama metode yang didukung oleh dynamic fallback handler. Menjamin konsistensi refleksi runtime (misalnya `job.respond_to?(:execute_unknown)` bernilai `true`).
10. **`method_missing(method_name, *args, &block)`**: Bertindak sebagai catch-all fallback jika perintah tidak didefinisikan secara spesifik oleh DSL, lalu meneruskan ke `super` jika kriteria namespace tidak sesuai.

---

# SEKSI 09 — STUDI KASUS NYATA

### Konteks Skenario: Arsitektur Enterprise Query Builder & Audit Engine
Pada aplikasi enterprise dengan throughput tinggi, sebuah sistem seringkali membutuhkan parser data entitas dinamis (Dynamic Schema & Policy Enforcement) tanpa menggunakan ORM eksternal yang lambat.

### Masalah Arsitektur:
1. Skema entitas terus bertambah dan membutuhkan validasi tipe data runtime, koersi (*coercion*), proteksi sanitasi, dan pelacakan jejak mutasi (*dirty tracking*).
2. Pustaka konvensional (seperti `OpenStruct`) memiliki overhead alokasi memori yang tinggi dan menyebabkan *method cache invalidation* secara konstan karena memodifikasi singleton class pada setiap instance.
3. Arsitektur harus mengekspos API deklaratif yang ringkas namun menghasilkan eksekusi deterministik dengan memori seminimal mungkin.

### Desain Solusi:
Membangun sebuah framework metamodel mikro: **`CoreEntity::Model`**. Menggunakan deklarasi macro (`attribute :name, Type`), meng-compile reader dan writer ke dalam method table class secara otomatis, mengisolasi data dalam storage array, dan menyematkan dynamic dirty tracking tanpa overhead `method_missing` pada hot-path eksekusi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi skala enterprise untuk Dynamic Metamodel Engine yang fungsional, tahan kesalahan, dan efisien:

```ruby
# frozen_string_literal: true

require 'time'
require 'securerandom'

module CoreEntity
  # Error hierarchy untuk domain model
  class Error < StandardError; end
  class ValidationError < Error; end
  class ImmutableAttributeError < Error; end

  # Type System & Coercion Engine
  module Types
    class BaseType
      def coerce(val)
        val
      end

      def valid?(_val)
        true
      end
    end

    class StringType < BaseType
      def coerce(val)
        val&.to_s
      end

      def valid?(val)
        val.is_a?(String)
      end
    end

    class IntegerType < BaseType
      def coerce(val)
        return nil if val.nil?
        Integer(val)
      rescue ArgumentError, TypeError
        raise ValidationError, "Nilai '#{val}' tidak valid untuk Integer"
      end

      def valid?(val)
        val.is_a?(Integer)
      end
    end

    class BooleanType < BaseType
      def coerce(val)
        return nil if val.nil?
        [true, 1, '1', 't', 'true'].include?(val.is_a?(String) ? val.downcase : val)
      end

      def valid?(val)
        val.is_a?(TrueClass) || val.is_a?(FalseClass)
      end
    end

    STRING = StringType.new
    INTEGER = IntegerType.new
    BOOLEAN = BooleanType.new
  end

  # Modul Inti Metamodel
  module Model
    def self.included(base)
      base.extend(ClassMethods)
      base.include(InstanceMethods)
      
      # Inisialisasi metadata pada class yang menyematkan modul ini
      base.instance_variable_set(:@attributes_schema, {})
      base.instance_variable_set(:@primary_key_attr, nil)
    end

    module ClassMethods
      attr_reader :attributes_schema, :primary_key_attr

      # Macro DSL untuk registrasi atribut
      def attribute(name, type, default: nil, readonly: false)
        attr_name = name.to_sym
        
        # Validasi duplikasi
        if @attributes_schema.key?(attr_name)
          raise ArgumentError, "Atribut '#{attr_name}' sudah terdaftar pada #{self}."
        end

        # Registrasi ke skema
        @attributes_schema[attr_name] = {
          type: type,
          default: default,
          readonly: readonly
        }.freeze

        # Compile accessors secara dinamis (Zero runtime lookup overhead)
        compile_reader(attr_name)
        compile_writer(attr_name, readonly)
      end

      def primary_key(name)
        @primary_key_attr = name.to_sym
        attribute(name, Types::STRING, default: -> { SecureRandom.uuid }, readonly: true)
      end

      private

      def compile_reader(name)
        define_method(name) do
          @attributes[name]
        end
      end

      def compile_writer(name, readonly)
        if readonly
          define_method("#{name}=") do |_value|
            raise ImmutableAttributeError, "Atribut readonly '#{name}' tidak dapat dimutasi setelah inisialisasi"
          end
        else
          define_method("#{name}=") do |value|
            write_attribute(name, value)
          end
        end
      end
    end

    module InstanceMethods
      attr_reader :mutations

      def initialize(initial_attributes = {})
        @attributes = {}
        @mutations = {}
        @initialized = false

        apply_defaults
        hydrate(initial_attributes)
        @initialized = true
      end

      def dirty?
        !@mutations.empty?
      end

      def changed_attributes
        @mutations.dup.freeze
      end

      def to_h
        @attributes.dup.freeze
      end

      def inspect
        attrs = @attributes.map { |k, v| "#{k}: #{v.inspect}" }.join(', ')
        "#<#{self.class.name} #{attrs} [dirty: #{dirty?}]>"
      end

      private

      def apply_defaults
        self.class.attributes_schema.each do |name, config|
          default_val = config[:default]
          resolved_val = default_val.is_a?(Proc) ? default_val.call : default_val
          @attributes[name] = resolved_val unless resolved_val.nil?
        end
      end

      def hydrate(hash)
        hash.each do |key, raw_value|
          attr_sym = key.to_sym
          schema = self.class.attributes_schema[attr_sym]
          
          next unless schema # Abaikan atribut yang tidak didefinisikan

          coerced_value = schema[:type].coerce(raw_value)
          @attributes[attr_sym] = coerced_value
        end
      end

      def write_attribute(name, value)
        schema = self.class.attributes_schema.fetch(name) do
          raise ArgumentError, "Atribut '#{name}' tidak dikenal."
        end

        coerced = schema[:type].coerce(value)
        return if @attributes[name] == coerced

        # Catat original value untuk dirty tracking
        @mutations[name] = @attributes[name] unless @mutations.key?(name)
        @attributes[name] = coerced
      end
    end
  end
end

# -------------------------------------------------------------
# Domain Implementation: Enterprise Ledger & Account System
# -------------------------------------------------------------

class LedgerTransaction
  include CoreEntity::Model

  primary_key :transaction_id
  attribute :reference_number, CoreEntity::Types::STRING
  attribute :amount_cents,      CoreEntity::Types::INTEGER
  attribute :is_settled,       CoreEntity::Types::BOOLEAN, default: false
  attribute :cleared_at,       CoreEntity::Types::STRING,  default: nil
end

# Verification & Test Suite
if __FILE__ == $PROGRAM_NAME
  puts "================================================="
  puts "SISTEM PRODUCTION LEDGER TRANSACTION ENGINE"
  puts "================================================="

  # 1. Inisialisasi Objek dengan Defaults dan Primary Key Generasi
  tx = LedgerTransaction.new(
    reference_number: "TRX-PAY-2026-9901",
    amount_cents: "500000" # Coercion dari String ke Integer
  )

  puts "\n[STEP 1: Instansiasi]"
  puts tx.inspect
  puts "Transaction ID (Auto-generated UUID): #{tx.transaction_id}"
  puts "Settled status (Default): #{tx.is_settled}"
  puts "Amount Cents (Coerced): #{tx.amount_cents} (Class: #{tx.amount_cents.class})"
  puts "Is Dirty?: #{tx.dirty?}"

  # 2. Mutasi State (Dirty Tracking)
  puts "\n[STEP 2: Mutasi Atribut]"
  tx.amount_cents = 750000
  tx.is_settled = "true" # Coercion dari string ke boolean

  puts tx.inspect
  puts "Is Dirty?: #{tx.dirty?}"
  puts "Mutations Tracked: #{tx.changed_attributes.inspect}"

  # 3. Pengujian Proteksi Read-Only (Enkapsulasi)
  puts "\n[STEP 3: Proteksi Enkapsulasi Readonly]"
  begin
    tx.transaction_id = "MANUAL-OVERRIDE-ATTEMPT"
  rescue CoreEntity::ImmutableAttributeError => e
    puts "BERHASIL: Proteksi Immutable Attribute memblokir aksi! Pesan: #{e.message}"
  end

  # 4. Pengujian Validasi Tipe
  puts "\n[STEP 4: Type Coercion Safety Boundary]"
  begin
    tx.amount_cents = "INI_BUKAN_ANGKA"
  rescue CoreEntity::ValidationError => e
    puts "BERHASIL: Type enforcement menggagalkan data invalid! Pesan: #{e.message}"
  end
end
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Saat mendesain dynamic behavior, arsitek perangkat lunak dihadapkan pada beberapa pendekatan. Tabel berikut menyajikan analisis komparatif sistematis:

| Dimensi Parameter | Dynamic Class Definition (`define_method`) | Trap Hook (`method_missing`) | Dynamic String Evaluation (`class_eval "code"`) | Static Generator (Code Generation Script / Rake) |
| :--- | :--- | :--- | :--- | :--- |
| **Kecepatan Eksekusi (Hot-Path)** | **Sangat Tinggi**: Menggunakan *YARV Inline Method Cache*. | **Rendah**: Memaksa penelusuran traversal penuh hingga `BasicObject`. | **Tinggi**: Identik dengan metode biasa setelah dicompile. | **Tertinggi**: Tidak ada overhead runtime; deterministik sejak awal. |
| **Konsumsi Alokasi Memori** | **Rendah-Sedang**: Alokasi `Proc` capture pada definisi scope awal. | **Nol / Sangat Rendah**: Tidak ada penambahan method entry pada `m_tbl`. | **Tinggi**: String harus di-parse ulang oleh lexer/parser Ruby. | **Nol Overhead Runtime**: Selesai pada saat build step. |
| **Keterbacaan Stack Trace** | **Jelas**: Muncul nama metode eksplisit di dalam error backtrace. | **Kabur**: Sering mengaburkan lokasi baris asli kegagalan kode. | **Sangat Buruk**: Baris galat menunjuk ke `(eval):Line` tanpa konteks file. | **Sangat Jelas**: Setiap instruksi memiliki representasi baris fisik. |
| **Keamanan Input (Security)** | **Sangat Aman**: Tidak ada evaluasi parsing string mentah. | **Aman**: Hanya beroperasi pada level Symbol / ID. | **Sangat Berbahaya**: Rawan *Arbitrary Code Execution* jika ada input eksternal. | **Aman**: Dapat diperiksa secara statis (*linters/SAST*). |
| **Dukungan YJIT (Ruby 3+)** | **Dioptimalkan Secara Penuh**. | **Bypass JIT Compiler Optimization**. | **Merusak Method JIT Invalidation**. | **Paling Ramah YJIT Optimizer**. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Symbol Exhaustion (Denial of Service Memori)
Sebelum Ruby 2.2, Symbol tidak pernah dibersihkan oleh Garbage Collector (GC). Walaupun Ruby 3.x memiliki *Mortal Symbols* yang dapat di-GC, membuat jutaan simbol secara dinamis dari input pengguna via `to_sym` tetap memicu pressure GC yang masif dan fragmentasi memori heap CRuby.
* **Solusi**: Jangan pernah melakukan `params[:attr].to_sym` tanpa whitelist validasi skema berbasis Set atau Hash string.

### 2. Bypass Metode Inti Akibat `method_missing` yang Tidak Disaring
Jika receiver mewarisi dari `Object`, pemanggilan metode default sistem seperti `hash`, `class`, `object_id`, atau `nil?` tidak akan memicu `method_missing` karena metode-metode ini sudah ada di `Kernel` atau `Object`.
* **Solusi**: Jika Anda sedang membangun proxy builder atau delegate murni, turunkan class Anda secara langsung dari `BasicObject`, bukan dari `Object`.

### 3. Kebocoran Variabel Scope (*Closure Variable Retain*)
Menggunakan `define_method` yang merujuk pada objek besar di sekitarnya akan menahan objek tersebut dari pengumpulan Garbage Collector karena closure menyimpan seluruh *binding context*.
```ruby
# ANTI-PATTERN: Menahan memory leak
large_data = File.read("huge_data.bin")
MyClass.class_eval do
  define_method(:process) { puts large_data.size } # large_data tidak akan pernah di-GC!
end
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan `respond_to_missing?`
Banyak developer meng-override `method_missing` tetapi melupakan `respond_to_missing?`.

```ruby
# SALAH: Objek merespons pemanggilan, tetapi berbohong pada introspeksi
class Greeter
  def method_missing(name, *args)
    return "Hello!" if name.start_with?("say_")
    super
  end
end

g = Greeter.new
g.say_hi # => "Hello!"
g.respond_to?(:say_hi) # => FALSE! (Menyebabkan bug pada framework serializer)
```

```ruby
# BENAR: Menjaga integritas method contract
class Greeter
  def respond_to_missing?(name, include_private = false)
    name.start_with?("say_") || super
  end

  def method_missing(name, *args, &block)
    return "Hello!" if name.start_with?("say_")
    super
  end
end
```

### Kesalahan 2: Menggunakan `class_eval` dengan String Mengandung Nilai Tidak Tervalidasi

```ruby
# SANGAT BERBAHAYA (Code Injection):
def create_method(klass, name, logic)
  klass.class_eval "def #{name}; #{logic}; end"
end
# Jika 'logic' berasal dari params HTTP: logic = "system('rm -rf /')" -> Bencana!

# BENAR: Gunakan define_method dengan blok
def create_method(klass, name, &block)
  klass.define_method(name, &block)
end
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan `public_send` Secara Eksklusif:** Jangan membiasakan diri menggunakan `send` kecuali jika Anda sedang menulis pustaka pengujian (testing framework) yang memang membutuhkan introspeksi internal/private.
2. **Kompilasi Dinamis Sekali Saja (Warm-up Phasing):** Lakukan eksekusi pembuatan metode dinamis (`define_method`) pada fase *boot application* (misal: initializer, loading class), hindari menjalankan metaprogramming di dalam hot loops pemrosesan request HTTP.
3. **Bekukan Skema Metamodel (`freeze`):** Selalu bekukan konfigurasi arsitektur DSL Anda setelah inisialisasi class guna mencegah *thread race condition* di multithreaded server seperti Puma:
   ```ruby
   @attributes_schema.freeze
   ```
4. **Patuh pada RuboCop Rules:**
   * `Style/MissingRespondToMissing`: Wajib menyertakan `respond_to_missing?`.
   * `Security/Eval`: Blokir pemanggilan string `eval`.
   * `Style/Send`: Utamakan penggunaan `public_send`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Benchmarking: Dynamic Execution Types
Mari bandingkan kinerja: Direct Static Call vs `define_method` Call vs `method_missing` Call.

```ruby
# benchmark_meta.rb
require 'benchmark/ips'

class BenchTarget
  def static_method
    42
  end

  define_method(:dynamic_method) do
    42
  end

  def respond_to_missing?(name, _)
    name == :missing_target || super
  end

  def method_missing(name, *args)
    name == :missing_target ? 42 : super
  end
end

target = BenchTarget.new

Benchmark.ips do |x|
  x.report("Static Method")   { target.static_method }
  x.report("define_method")   { target.dynamic_method }
  x.report("method_missing")  { target.missing_target }
  x.compare!
end
```

**Hasil Ekspektasi pada Ruby 3.x YJIT:**
* `static_method`: ~25-30 juta i/s (Basis referensi tercepat, fully inlined oleh YJIT).
* `define_method`: ~20-25 juta i/s (Nyaris mendekati static method berkat inline method cache).
* `method_missing`: ~4-6 juta i/s (**5x hingga 7x lebih lambat** karena pencarian rantai ancestor yang konstan dan alokasi array argument).

### 2. Strategi YJIT-Friendly:
* **Hindari re-opening class di runtime:** Hal ini menginvalidasi `vm_global_method_state` yang menyebabkan YJIT mendereferensikan native machine code yang sudah dikompilasi.
* **Gunakan Symbol statis untuk keys:** Jangan mengubah string menjadi simbol di hot loop. Definisikan konstanta simbol.

---

# SEKSI 16 — KEAMANAN & HARDENING

### Metaprogramming Vulnerability Vector & Mitigasi:

1. **Arbitrary Method Execution (Mass Assignment RCE):**
   * *Vektor Serangan:* Client mengirim payload JSON: `{"method_to_call": "destroy_all"}`. Kode backend mengeksekusi `target.public_send(params[:method_to_call])`.
   * *Mitigasi:* Gunakan konsep *Allowlist Filtering*:
     ```ruby
     ALLOWED_ACTIONS = Set[:create, :update, :archive].freeze

     def safe_dispatch(action_param)
       action = action_param.to_s.to_sym
       raise SecurityError, "Aksi dilarang" unless ALLOWED_ACTIONS.include?(action)
       public_send(action)
     end
     ```

2. **Constant Lookup Infiltration:**
   * Menemukan nama class secara dinamis via `Object.const_get(user_string)` dapat dimanipulasi penyerang untuk mengakses kelas internal (`File`, `Process`).
   * *Hardening Pattern:*
     ```ruby
     def safe_resolve_class(class_name)
       # Pastikan hanya mencari di dalam namespace modul domain Anda
       MyDomainNamespace.const_get(class_name, false) # 'false' mencegah fallback ke Object / root scope
     rescue NameError
       raise SecurityError, "Tipe tidak sah"
     end
     ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging kode metaprogramming membutuhkan teknik pelacakan khusus karena metode seringkali tidak eksis secara fisik di file source code.

### 1. Menemukan Asal-Usul Metode Runtime
Gunakan `Method#source_location` untuk mengetahui lokasi fisik pendefinisian suatu metode:
```ruby
handler = target.method(:execute_database)
file, line = handler.source_location
puts "Metode didefinisikan pada File: #{file}, Baris: #{line}"
# Output: File: /path/to/my_script.rb, Baris: 37
```

### 2. Tracing Method Dispatch Menggunakan `TracePoint`
Jika Anda menghadapi *ghost methods* yang tidak terlacak, aktifkan `TracePoint` untuk merekam dispatch flow:
```ruby
tracer = TracePoint.new(:call, :c_call) do |tp|
  next unless tp.path.include?("my_project") # Filter hanya aplikasi kita
  puts "[TRACE] #{tp.defined_class}##{tp.method_id} dipanggil pada #{tp.path}:#{tp.lineno}"
end

tracer.enable do
  # Jalankan blok kode metaprogramming Anda
  job.execute(:database)
end
```

### 3. Backtrace Sanitization
Ketika mendesain pustaka DSL, format backtrace agar pengguna tidak disajikan baris internal framework:
```ruby
begin
  # Internal meta dispatch logic
rescue => e
  cleaned_backtrace = e.backtrace.reject { |line| line.include?("/lib/framework/internal/") }
  e.set_backtrace(cleaned_backtrace)
  raise e
end
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

| Operasi | Sintaksis Inti | Konteks `self` | Tujuan Utama |
| :--- | :--- | :--- | :--- |
| **Buka Eigenclass** | `class << obj; self; end` | Singleton class dari `obj` | Mendefinisikan singleton methods / class methods. |
| **Instance Evaluation** | `obj.instance_eval { ... }` | `obj` (Instance) | DSL per-instance, manipulasi langsung instance variable. |
| **Class Evaluation** | `Class.class_eval { ... }` | `Class` (Definisi tipe) | Menambahkan instance method baru ke dalam class secara dinamis. |
| **Dynamic Method Def** | `define_method(:name) { ... }`| Receiver Class saat ini | Membuat method teroptimasi cache tanpa string parsing. |
| **Safe Dispatch** | `obj.public_send(:name, *args)` | `obj` | Memanggil metode dinamis sesuai aturan visibilitas OOP. |
| **Lifecycle Hooks** | `self.inherited(subclass)` | Class induk | Registrasi otomatis, validasi skema modular, setup arsitektur. |
| **Lookup Priority** | `prepend` > Class > `include` | Sesuai hierarchy | Intersepsi / dekorasi method via `prepend`. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Kuis Tingkat Dasar (Basic)

**Soal 1:** Di manakah singleton method dari sebuah instance objek disimpan di dalam memori CRuby?  
A. Di dalam struktur `RObject` milik instance itu sendiri.  
B. Di dalam method table (`m_tbl`) milik Singleton Class (Eigenclass) dari objek tersebut.  
C. Di dalam class global `Object`.  
D. Di dalam thread memory context.  
*Jawaban:* **B**. Objek tidak pernah menyimpan metode; metode privat/singleton selalu ditempatkan pada Singleton Class (Eigenclass) yang bertindak sebagai bayangan dari objek tersebut.

---

**Soal 2:** Manakah pernyataan yang BENAR mengenai perbedaan `include` dan `prepend`?  
A. `include` menyisipkan modul di depan class penerima pada rantai ancestors.  
B. `prepend` menyisipkan modul di depan class penerima, sehingga implementasi metode pada modul dapat mencegat pemanggilan dan mengeksekusi `super` ke class penerima.  
C. Tidak ada perbedaan fungsi, hanya penamaan alias.  
D. `prepend` hanya dapat digunakan pada objek tunggal, sedangkan `include` pada class.  
*Jawaban:* **B**. `prepend` menempatkan modul tepat di depan (*higher priority*) dari class penerima di dalam rantai ancestors.

---

**Soal 3:** Mengapa developer harus selalu mendefinisikan `respond_to_missing?` setiap kali meng-override `method_missing`?  
A. Agar metode tidak memakan alokasi memori heap.  
B. Untuk memastikan metode `respond_to?` dan refleksi runtime seperti `Object#method` mengembalikan hasil yang akurat.  
C. Tanpa `respond_to_missing?`, Ruby akan langsung melempar error sintaksis saat boot.  
D. Untuk membersihkan YARV method cache secara otomatis.  
*Jawaban:* **B**. Tanpa `respond_to_missing?`, metode dinamis yang ditangani oleh `method_missing` akan dianggap tidak eksis ketika dicek menggunakan `respond_to?`.

---

**Soal 4:** Apa perbedaan fungsional antara `send` dan `public_send`?  
A. `send` dapat memanggil metode private/protected, sedangkan `public_send` menghormati visibilitas metode.  
B. `public_send` berjalan lebih cepat daripada `send`.  
C. `send` hanya menerima tipe parameter String.  
D. `public_send` adalah modul keamanan dari Rails, bukan bawaan Ruby core.  
*Jawaban:* **A**. `public_send` menegakkan enkapsulasi Ruby dan menolak eksekusi jika metode berstatus private.

---

**Soal 5:** Apa bahaya utama menggunakan evaluasi string `eval` pada runtime Ruby?  
A. `eval` selalu mematikan Garbage Collector.  
B. Kerentanan Arbitrary Code Execution (RCE) jika string tersebut terkontaminasi oleh input pengguna yang tidak disanitasi.  
C. `eval` tidak dapat membaca variabel lokal.  
D. `eval` diblokir sepenuhnya sejak peluncuran Ruby versi 3.0.  
*Jawaban:* **B**. Injeksi kode adalah risiko keamanan paling fatal dari evaluasi string mentah pada runtime.

---

### Kuis Tingkat Menengah (Intermediate)

**Soal 6:** Perhatikan potongan kode berikut:
```ruby
class Animal; end
cat = Animal.new

class << cat
  def speak; "Meow"; end
end
```
Apa yang sebenarnya terjadi pada struktur internal `cat`?  
A. Kelas `Animal` secara global mendapatkan metode `speak`.  
B. Ruby mengalokasikan singleton class baru untuk `cat`, menyisipkannya sebagai pointer `klass` dari `cat`, dan meletakkan `speak` di sana.  
C. Ruby membuat instance baru dari class `Class`.  
D. Terjadi error kompilasi karena sintaksis `class <<` tidak diizinkan untuk instance.  
*Jawaban:* **B**. Sintaksis `class << cat` membuka singleton class (eigenclass) milik instance `cat`, mengintersepsi struktur `RBasic` untuk mengalokasikan method table khusus instance tersebut.

---

**Soal 7:** Apa dampak dari memodifikasi struktur class secara runtime (re-opening class dan menambah metode baru) pada aplikasi Ruby 3 dengan YJIT yang sedang melayani traffic tinggi?  
A. Tidak ada dampak sama sekali; YJIT menangani modifikasi secara asinkron.  
B. Menaikkan nomor seri kelas secara global/lokal, membatalkan *Inline Cache*, dan memicu deoptimasi native code pada YJIT.  
C. Memaksa server memicu *Restart* instan (*Kernel Panic*).  
D. GC akan segera menghapus seluruh instance dari class tersebut.  
*Jawaban:* **B**. Modifikasi dinamis memicu *Method Cache Invalidation* yang membatalkan optimasi native machine code yang telah disusun YJIT.

---

**Soal 8:** Di dalam `class_eval`, metode yang dideklarasikan dengan sintaksis `def method_name; end` akan terdaftar sebagai:  
A. Class method dari class tersebut.  
B. Instance method dari class tersebut.  
C. Singleton method dari `Module`.  
D. Global method di dalam `Kernel`.  
*Jawaban:* **B**. `class_eval` memindahkan konteks evaluasi ke dalam tubuh class, sehingga deklarasi `def` standar mendaftarkannya sebagai instance method untuk objek-objek turunan class tersebut.

---

**Soal 9:** Mengapa penggunaan `define_method` umumnya lebih diutamakan daripada `method_missing` untuk implementasi API dinamis yang sering dipanggil?  
A. `define_method` tidak memerlukan argumen nama.  
B. `define_method` menambahkan entri ke `m_tbl` sehingga kompatibel dengan YARV Inline Caching dan berjalan jauh lebih cepat di hot-path.  
C. `method_missing` tidak dapat menerima blok parameter.  
D. `method_missing` sudah usang (*deprecated*) di Ruby 3.3.  
*Jawaban:* **B**. `define_method` menjamin metode terindeks secara pasti di tabel metode, sehingga VM tidak perlu melakukan linear lookup yang lambat pada setiap pemanggilan.

---

**Soal 10:** Kapan lifecycle hook `self.included(base)` dieksekusi oleh interpreter?  
A. Saat objek pertama dari class `base` diinstansiasi.  
B. Seketika saat baris `include ModuleName` dieksekusi di dalam class `base`.  
C. Saat proses kompilasi YARV selesai di akhir file.  
D. Hanya jika class `base` mewarisi dari `BasicObject`.  
*Jawaban:* **B**. Hook `included` bersifat imperatif dan langsung dieksekusi seketika pernyataan `include` diproses oleh parser/interpreter pada runtime.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Declarative State Machine Engine dengan Zero-Dependencies

### Deskripsi Tugas:
Rancang dan bangun sebuah modul DSL murni (**`StateMachine`**) dari nol tanpa bantuan library/gem eksternal. Modul ini harus dapat disertakan (*included*) ke kelas bisnis apa pun untuk menyediakan manajemen siklus hidup state berbasis deklarasi macro.

### Spesifikasi Kebutuhan:
1. **Macro Deklaratif:**
   * Harus menyediakan macro `state :state_name, initial: true/false`.
   * Harus menyediakan macro `event :event_name do transitions from: :state_a, to: :state_b end`.
2. **Generasi Metode Dinamis:**
   * Setiap state harus secara otomatis mengompilasi metode predikat (misal: jika state `:draft`, buat metode `#draft?`).
   * Setiap event harus mengompilasi metode transisi imperatif (misal: event `:publish` menghasilkan metode `#publish!`).
3. **Guard Clause & Callback Metaprogramming:**
   * Mendukung hook deklaratif: `before_transition` dan `after_transition`.
   * Jika transisi dilakukan dari state yang tidak sah (tidak cocok dengan deklarasi `from:`), sistem wajib melempar custom exception: `InvalidTransitionError` dan membatalkan mutasi state.
4. **Zero Cache Busting pada Hot-Path:**
   * Semua method generation harus terjadi saat pendefinisian class berlangsung (*class load time*), bukan saat objek memproses data (*runtime instance invocation*).

### Skelet Dasar untuk Memulai Praktikum:

```ruby
# frozen_string_literal: true

module StateMachine
  class InvalidTransitionError < StandardError; end

  def self.included(base)
    base.extend(ClassMethods)
  end

  module ClassMethods
    # IMPLEMENTASIKAN DI SINI:
    # 1. State registration macro
    # 2. Event transition DSL
    # 3. Dynamic method compilation untuk predicates (draft?, active?)
    # 4. Compilation untuk event bang methods (submit!, approve!)
  end

  # IMPLEMENTASIKAN DI SINI:
  # Instance methods internal untuk state storage, transisi aman, dan eksekusi callback
end

# Contoh Target Penggunaan yang Diharapkan:
class OrderWorkflow
  include StateMachine

  # Definisikan skema state machine di sini
  # state :draft, initial: true
  # state :paid
  # state :shipped

  # event :pay do
  #   transitions from: :draft, to: :paid
  # end
end

# Uji Verifikasi Mandiri:
# order = OrderWorkflow.new
# order.draft? # => true
# order.pay!
# order.paid?  # => true
# order.pay!   # => Raises StateMachine::InvalidTransitionError!
```

### Tolok Ukur Keberhasilan:
* Tidak ada pemanggilan string `eval`.
* Penanganan error transisi mempertahankan integritas data state sebelumnya (*state does not mutate on failure*).
* Refleksi berjalan sempurna: `order.respond_to?(:paid?)` menghasilkan nilai `true`.
* Menjalankan suite tanpa peringatan memori (*clean memory profile*).