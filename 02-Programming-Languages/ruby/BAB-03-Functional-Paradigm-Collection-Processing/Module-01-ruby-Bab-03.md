# Kurikulum Rekayasa Perangkat Lunak Ruby: Tingkat Lanjut
## Bab 03: Arsitektur Objek & Metaprogramming Tingkat Sistem
### Modul 01: Anatomi Ruby Object Model: Ancestor Chain, Singleton Class (Eigenclass), dan Dynamic Method Lookup

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah representasi internal objek di memori Matz's Ruby Interpreter (MRI) termasuk struktur `RClass`, `klass` pointer, dan method tables.
- Menganalisis dan memprediksi urutan resolusi method (*method lookup path*) pada hierarki pewarisan kompleks yang melibatkan `prepend`, `include`, `extend`, dan *singleton class* (eigenclass).
- Mengimplementasikan pola interceptor dan modifikasi perilaku runtime secara aman tanpa merusak integritas *Inline Method Cache* (IMC) pada Virtual Machine (YARV).
- Mendiagnosis degradasi performa dan *memory leak* akibat polusi class hierarki dan mutasi method table global di lingkungan produksi.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- Konsep dasar OOP di Ruby: Definisi Class, Instance, Module, Inheritance (`<`), serta enkapsulasi (`public`, `protected`, `private`).
- Eksekusi closure dasar di Ruby: `Block`, `Proc`, dan `Lambda`.
- Penggunaan dasar CLI Ruby (`irb`, `ruby`) dan pemahaman alur eksekusi script Ruby secara umum.

---

### 3. Concept
Dalam Ruby, semboyan *"Everything is an Object"* bukan sekadar filosofi desain, melainkan realitas arsitektur memori. Setiap entitas—mulai dari integer primitif, string, hingga class itu sendiri—merupakan instansiasi dari suatu class struktural.

Secara internal pada C-source Ruby (MRI), sebuah objek direpresentasikan oleh struktur data `RObject`, sedangkan class direpresentasikan oleh `RClass`. Setiap objek memiliki *header* yang memuat pointer bernama `klass`. Pointer `klass` merujuk langsung ke class yang mencetak objek tersebut dan bertanggung jawab menyimpan daftar method (disebut *method table* atau `m_tbl`).

```text
[ Instance: obj ] 
       │
       └──(klass pointer)──> [ RClass: User ]
                                   │
                                   ├── m_tbl (Method Table: #name, #email)
                                   └──(super pointer)──> [ RClass: Object ]
```

Namun, Ruby memungkinkan penambahan method ke satu objek individual secara eksklusif tanpa memengaruhi instansi lain dari class yang sama. Arsitektur Ruby memfasilitasi hal ini tanpa melanggar prinsip OOP murni melalui abstraksi bernama **Singleton Class** (secara historis disebut *Eigenclass* atau *Metaclass*). Ketika method didefinisikan secara khusus pada sebuah objek (`def obj.custom_method`), Ruby menyisipkan class anonim (*ghost class*) tepat di antara objek tersebut dan class aslinya.

Konsekuensi arsitektur ini:
1. **Class adalah Objek:** Class seperti `String` atau `User` sebenarnya adalah *instance* dari class `Class`.
2. **Class Method adalah Singleton Method:** Class method hanyalah method biasa yang terdaftar pada *singleton class* milik class object tersebut.
3. **Lookup Linier:** Eksekusi method selalu menelusuri satu rantai linier tunggal (*ancestor chain*) melalui pointer internal `klass` dan `super`.

---

### 4. Why
Memahami Ruby Object Model hingga tingkat internal adalah pembeda mutlak antara developer tingkat pemula dan *Staff/Principal Engineer*:

- **Transparansi Framework:** Framework berskala besar seperti Ruby on Rails, dry-rb, atau Hanami bertumpu sepenuhnya pada metaprogramming dan modifikasi *ancestor chain* (`ActiveSupport::Concern`, dynamic finder, callbacks). Tanpa pemahaman ini, framework bertindak sebagai *black box* yang mustahil di-debug ketika terjadi anomali.
- **Dampak Performa VM:** Setiap kali method ditambahkan, dimodifikasi, atau dihapus pada runtime, Ruby VM menaikkan counter internal `ruby_vm_global_method_state`. Hal ini membatalkan (*invalidates*) seluruh *Inline Method Cache* (IMC) di YARV, yang memaksa VM melakukan lookup ulang berbasis hash table yang lambat pada setiap pemanggilan method di thread manapun.
- **Debugging Konflik Gem:** Tabrakan method (*monkey patching collision*) antardependensi vendor hanya dapat diselesaikan jika Anda mampu melacak rute resolusi via `#ancestors` dan singleton hierarchy.

---

### 5. What
Komponen inti penyusun Ruby Object Model:

- **`BasicObject`**: Akar mutlak dari hierarki objek Ruby. Memiliki method minimal (hanya operasi fundamental seperti `!`, `==`, `__send__`, `__id__`).
- **`Object`**: Subclass dari `BasicObject`. Mengikutsertakan modul `Kernel`. Merupakan default root untuk semua class kustom yang dibuat pengguna.
- **`Module`**: Kumpulan method, konstanta, dan variabel modul. Tidak dapat diinstansiasi langsung via `.new`.
- **`Class`**: Spesialisasi dari `Module` yang menambahkan kemampuan instansiasi objek (`.new`) dan pewarisan tunggal struktural (`<`).
- **`Singleton Class`**: Class turunan khusus yang disisipkan oleh VM secara transparan untuk memuat method spesifik milik satu objek tertentu.
- **Ancestor Chain**: Urutan pencarian method yang dibentuk oleh kombinasi superclass dan modul yang diintegrasikan (`prepend`, `include`).

---

### 6. How
Alur resolusi method saat ekspresi `receiver.message(args)` dieksekusi:

```text
Alur Resolusi:
[receiver]
   │
   ▼
[Singleton Class milik receiver?] ──(Ya)──> Ditemukan di m_tbl? ──(Ya)──> Eksekusi
   │ (Tidak)                                     │ (Tidak)
   ▼                                             ▼
[Modul Prepend pada Class] ───────(Ada)───> Ditemukan di m_tbl? ──(Ya)──> Eksekusi
   │ (Tidak)                                     │ (Tidak)
   ▼                                             ▼
[Class dari receiver] ────────────────────> Ditemukan di m_tbl? ──(Ya)──> Eksekusi
   │ (Tidak)                                     │ (Tidak)
   ▼                                             ▼
[Modul Include pada Class] ───────(Ada)───> Ditemukan di m_tbl? ──(Ya)──> Eksekusi
   │ (Tidak)                                     │ (Tidak)
   ▼                                             ▼
[Superclass & Modul-modulnya] ────(Ada)───> [Ulangi siklus hingga BasicObject]
   │ (Tidak Ditemukan)
   ▼
[Kirim :method_missing ke receiver]
```

1. **Inisiasi Pencarian:** VM memeriksa pointer `klass` dari `receiver`. Jika receiver memiliki singleton class, lookup dimulai dari singleton class tersebut.
2. **Prepend Lookup:** Memeriksa modul-modul yang di-*prepend* ke class aktif. Modul prepend disisipkan *sebelum* class itu sendiri di dalam ancestor chain.
3. **Class Level Lookup:** Memeriksa `m_tbl` milik class saat ini.
4. **Include Lookup:** Memeriksa modul-modul yang di-*include* ke class aktif. Modul include disisipkan *setelah* class dan *sebelum* superclass.
5. **Superclass Escalation:** Menelusuri pointer `super` ke superclass dan mengulangi langkah 2-4 secara rekursif hingga mencapai `BasicObject`.
6. **Fallback `method_missing`:** Jika pointer `super` bernilai `NULL` (ujung `BasicObject`) dan method tidak ditemukan, VM mengulang pencarian dari awal untuk memanggil method `#method_missing`.

---

### 7. Analogy
Bayangkan proses permohonan visa dinas internasional:

1. Anda (**Instance**) mengajukan visa khusus.
2. Pertama, petugas memeriksa map khusus Anda sendiri (**Singleton Class**). Jika ada stempel izin langsung di sana, proses selesai.
3. Jika tidak, petugas memeriksa SOP Pengawas Lapangan (**Prepend Module**) yang dapat menganulir regulasi umum.
4. Jika tidak ada, petugas memeriksa SOP Divisi Standar Anda (**Class**).
5. Jika tidak ada, petugas memeriksa SOP Panduan Vendor Eksternal (**Include Module**) yang disisipkan ke divisi Anda.
6. Jika tidak ada, berkas diteruskan ke Divisi Pusat / Kementerian (**Superclass**), yang juga memiliki pengawas dan panduannya sendiri.
7. Jika berkas sampai ke Meja Presiden Tertinggi (**BasicObject**) dan izin tetap tidak ditemukan, barulah berkas dilempar ke Protokol Penanganan Kegagalan Khusus (**`method_missing`**).

---

### 8. Diagram
Berikut adalah peta hubungan pointer internal memori antara Objek, Class, Singleton Class, dan Superclass di MRI:

```text
                +---------------------+
                |     BasicObject     |
                +---------------------+
                           ^
                           | (super)
                +---------------------+
                |       Object        |
                +---------------------+
                           ^
                           | (super)
                +---------------------+             +---------------------------+
                |       Animal        | <---------- |  #<Class:Animal> (Eigen)  |
                +---------------------+   (klass)   +---------------------------+
                           ^                                      ^
                           | (super)                              | (super)
                +---------------------+             +---------------------------+
                |        Lion         | <---------- |   #<Class:Lion> (Eigen)   |
                +---------------------+   (klass)   +---------------------------+
                           ^                                      ^
                           |                                      |
                           | (klass)                              | (klass)
                +---------------------+             +---------------------------+
                |    simba (Object)   | ----------> |   #<Class:#<Lion:...>>    |
                +---------------------+  (klass)    |  (Singleton Class Simba)  |
                                                    +---------------------------+

Keterangan:
───> Pointer klass (tipe objek / penyimpan method langsung)
───> Pointer super (jalur resolusi warisan saat method tidak ditemukan di m_tbl lokal)
```

---

### 9. Simple Example
Kode demonstrasi untuk memvalidasi posisi Singleton Class dan urutan ancestor:

```ruby
# frozen_string_literal: true

module SecurityCheck
  def validate!
    "SecurityCheck: Validating..."
  end
end

module AuditLogging
  def validate!
    "AuditLogging: Pre-run -> #{super}"
  end
end

class PaymentGateway
  include SecurityCheck
  prepend AuditLogging

  def validate!
    "PaymentGateway: Core Logic"
  end
end

# 1. Inspeksi Ancestor Chain
puts "--- Ancestor Chain PaymentGateway ---"
puts PaymentGateway.ancestors
# Output:
# AuditLogging   (karena prepend)
# PaymentGateway (class asal)
# SecurityCheck  (karena include)
# Object
# Kernel
# BasicObject

gateway = PaymentGateway.new

# 2. Sisipkan Singleton Method pada instansi gateway
def gateway.validate!
  "Singleton: VIP Bypass -> #{super}"
end

puts "\n--- Hasil Pemanggilan ---"
puts gateway.validate!
# Output:
# Singleton: VIP Bypass -> AuditLogging: Pre-run -> PaymentGateway: Core Logic

puts "\n--- Status Singleton Class ---"
puts gateway.singleton_class #=> #<Class:#<PaymentGateway:0x000...>>
puts gateway.singleton_class.ancestors.first(4)
# Output:
# #<Class:#<PaymentGateway:0x00...>>
# AuditLogging
# PaymentGateway
# SecurityCheck
```

---

### 10. Practical Example
Implementasi sistem telemetri performa (*Dynamic Performance Tracer*) kelas produksi yang menginjeksi instrumentasi runtime menggunakan `Module#prepend` tanpa merusak `super` chain dan menjaga stabilitas IMC.

```ruby
# frozen_string_literal: true

require 'json'
require 'time'

module Telemetry
  class MetricsCollector
    class << self
      def record(payload)
        # Menulis metrik terstruktur ke standard output
        $stdout.puts("[METRICS] #{JSON.generate(payload)}")
      end
    end
  end

  module Traceable
    def self.instrument(target_klass, *methods)
      interceptor = Module.new do
        methods.each do |method_name|
          define_method(method_name) do |*args, **kwargs, &block|
            start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
            begin
              super(*args, **kwargs, &block)
            ensure
              duration_ms = (Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time) * 1000.0
              MetricsCollector.record(
                class: self.class.name,
                method: method_name,
                duration_ms: duration_ms.round(4),
                timestamp: Time.now.utc.iso8601
              )
            end
          end
        end
      end

      # Gunakan prepend agar interceptor berada di urutan teratas sebelum class target
      target_klass.prepend(interceptor)
    end
  end
end

# Implementasi Domain Bisnis
class OrderProcessor
  def process_order(order_id)
    sleep(0.05) # Simulasi operasi I/O intensif
    { order_id: order_id, status: :processed }
  end

  def refund_order(order_id)
    sleep(0.02) # Simulasi operasi DB
    { order_id: order_id, status: :refunded }
  end
end

# Injeksi instrumentasi pada saat fase bootstrapping aplikasi
Telemetry::Traceable.instrument(OrderProcessor, :process_order, :refund_order)

# Verifikasi Eksekusi
processor = OrderProcessor.new
processor.process_order("ORD-98213")
processor.refund_order("ORD-98213")

# Bukti Ancestor Chain
puts "\nAncestor Chain Pasca Instrumentasi:"
puts OrderProcessor.ancestors.first(3)
```

---

### 11. Real World Example
**Studi Kasus: Sistem Safe Database Query Patching Shopify**

Pada infrastruktur skala global seperti Shopify, ribuan instance worker memproses query database secara paralel. Di masa lalu, tracing dilakukan menggunakan *alias method chaining*:

```ruby
# POLA DEPRECATED (Berisiko tinggi)
class ActiveRecord::Base
  alias_method :execute_without_profiler, :execute
  def execute(sql, *args)
    # profiling
    execute_without_profiler(sql, *args)
  end
end
```

**Masalah di Skala Produksi:**
Jika dua gem berbeda mencoba me-*monkey patch* method yang sama dengan `alias_method_chain`, urutan pemuatan library yang salah akan memicu siklus referensi melingkar (*infinite recursion loop*) yang menyebabkan crash `SystemStackError: stack level too deep`.

**Solusi Berbasis Module Prepend:**
Shopify mengganti pendekatan tersebut dengan memanfaatkan arsitektur ancestor chain:

```ruby
# ARSITEKTUR MODERN
module QueryProfilerPatch
  def execute(sql, *args)
    AppSignal.instrument("db.query", sql: sql) do
      super(sql, *args) # Menjamin eksekusi aman menyusuri rantai super alami
    end
  end
end

ActiveRecord::ConnectionAdapters::AbstractAdapter.prepend(QueryProfilerPatch)
```
Dengan menyisipkan `QueryProfilerPatch` di posisi sebelum target class pada hierarki `ancestors`, method `super` secara deterministik menunjuk ke implementasi asli tanpa mengubah method table secara destruktif dan tanpa risiko referensi sirkular.

---

### 12. Trade-offs

| Dimensi | Module `prepend` | Module `include` | Singleton Class (`def obj.method`) | Metaprogramming `method_missing` |
| :--- | :--- | :--- | :--- | :--- |
| **Keuntungan** | Intersepsi method bersih; preservasi delegasi via `super`. | Komposisi modular horizontal (*mixins*) yang terstandarisasi. | Modifikasi atomik per objek; isolasi ketat instansi lain. | Menangani antarmuka dinamis tak terbatas (Dynamic Proxies). |
| **Kekurangan** | Memperpanjang ancestor chain; mengubah titik masuk asli. | Tidak bisa memotong/mengintersepsi method lokal class itu sendiri. | Menghasilkan objek asimetris; sulit di-cache oleh compiler JIT. | Eksekusi lambat (pencarian penuh hingga `BasicObject`). |
| **Kompleksitas** | Rendah-Sedang. | Rendah. | Sedang. | Sangat Tinggi (wajib sinkronisasi `respond_to_missing?`). |
| **Performa VM** | Sedikit overhead pointer traversal saat cache miss. | Overhead traversal standar jika hirarki terlalu dalam (>15 module). | Memecah polimorfisme monomorfik (*monomorphic call site* deopt). | Lambat; membypass Inline Method Cache secara default. |
| **Dampak Memori**| Alokasi 1 `iclass` proxy node di Ruby heap per target. | Alokasi 1 `iclass` per class target. | Alokasi instan satu `RClass` baru per objek singleton. | Minimum alokasi awal, tapi boros siklus CPU runtime. |

---

### 13. When To Use
- Gunakan **`prepend`** saat Anda merancang library audit, APM (Application Performance Monitoring), profiler, atau middleware yang membutuhkan wrapping/intersepsi logika method inti.
- Gunakan **`include`** untuk memecah fungsionalitas domain (*cross-cutting concerns*) menjadi modul-modul modular terpisah.
- Gunakan **Singleton Class** ketika membangun implementasi State Machine yang membutuhkan variasi perilaku method drastis pada instansi tertentu, atau saat merancang DSL deklaratif tingkat class.

---

### 14. When NOT To Use
- Jangan gunakan modifikasi method runtime di dalam *tight loops* atau *critical paths* (misal: parsing JSON jutaan record). Pemanggilan `define_method` atau modifikasi modul di tengah loop akan memicu *global method cache invalidation*.
- Hindari penggunaan **`method_missing`** jika jumlah method yang ditangani sudah diketahui atau dapat diprediksi. Selalu prioritaskan `define_method` secara deklaratif saat class didefinisikan.
- Hindari memodifikasi class bawaan Ruby core (`String`, `Array`, `Hash`) secara terbuka via singleton atau monkey patching di library publik untuk mencegah *gem contention*.

---

### 15. Common Mistakes
1. **Mengabaikan `respond_to_missing?` saat meng-override `method_missing`:**
   ```ruby
   # SALAH: Objek merespons pesan secara dinamis, tapi inspeksi reflektif gagal
   class DynamicProxy
     def method_missing(name, *args)
       return "Processed #{name}" if name.start_with?("find_")
       super
     end
   end
   proxy = DynamicProxy.new
   proxy.respond_to?(:find_user) #=> false (Bug tersembunyi!)
   
   # BENAR:
   class DynamicProxy
     def method_missing(name, *args, &block)
       if name.start_with?("find_")
         "Processed #{name}"
       else
         super
       end
     end

     def respond_to_missing?(method_name, include_private = false)
       method_name.start_with?("find_") || super
     end
   end
   ```

2. **Kesalahan Urutan Ancestor antara `include` dan `prepend`:**
   Mendefinisikan method pada class utama, lalu meng-`include` modul dengan method bernama sama, berekspektasi method modul akan dijalankan. Padahal, class lokal selalu dieksekusi lebih dulu daripada modul yang di-`include`. Gunakan `prepend` jika ingin modul menjadi prioritas utama.

---

### 16. Best Practices (Production Checklist)
- [ ] Aktifkan pragma pembeku string `# frozen_string_literal: true` di setiap file untuk mengurangi alokasi memori saat manipulasi nama method/simbol dinamis.
- [ ] Hindari mutasi class dinamis setelah fase aplikasi *booting* selesai. Ruby on Rails menjalankan mode `config.eager_load = true` di produksi untuk menstabilkan method cache sebelum menerima request HTTP.
- [ ] Jangan pernah menggunakan method kustom `class_eval` dengan string interpolasi tanpa sanitasi ketat untuk menghindari celah keamanan injeksi kode arbitrer (*Remote Code Execution*).
- [ ] Validasi integritas ancestor chain menggunakan `TargetClass.ancestors` dalam *integration test suite* untuk memverifikasi modul interceptor terpasang di layer yang tepat.

---

### 17. Troubleshooting
- **Masalah: `SystemStackError: stack level too deep`**
  - *Akar Masalah:* Rekursi tanpa akhir saat interceptor memanggil `super`, tetapi method terdaftar merujuk kembali ke dirinya sendiri akibat tabrakan patch legacy (`alias_method`).
  - *Diagnosa:* Eksekusi `caller` atau periksa `Method#source_location`:
    ```ruby
    target_instance.method(:problematic_method).source_location
    ```
  - *Solusi:* Bersihkan alias ganda dan ganti seluruh pipeline intersepsi menggunakan urutan `prepend` eksplisit.

- **Masalah: Penurunan Drastis Throughput / CPU Spikes di Ruby YARV**
  - *Akar Masalah:* Pemanggilan `define_singleton_method` atau `extend` di dalam block per-request controller web, menyebabkan cache invalidation konstan (`ruby_vm_global_method_state`).
  - *Diagnosa:* Periksa kode menggunakan gem `allocation_tracer` atau gunakan probe DTrace/eBPF untuk melacak invalidasi method cache.
  - *Solusi:* Pindahkan metaprogramming ke level class initialization saat startup, gunakan polymorphic delegation standar daripada singleton patching runtime.

---

### 18. Exercise
**Skenario:**
Bangun sebuah modul otorisasi fungsional bernama `RoleGate`. Modul ini harus:
1. Memotong eksekusi method apapun yang didaftarkan.
2. Memeriksa keberadaan instance variable `@current_role`.
3. Mengizinkan pemanggilan `super` jika `@current_role == :admin`.
4. Melemparkan exception `SecurityError: "Access Denied"` jika bukan admin.

**Instruksi Step-by-Step:**
1. Buat class `DataVault` dengan method `destroy_records!`.
2. Implementasikan `RoleGate.protect(klass, *methods)` yang menyusun anonymous module menggunakan `prepend`.
3. Injeksi modul tersebut ke `DataVault`.
4. Uji eksekusi dengan state instansi berbeda (`@current_role = :viewer` vs `@current_role = :admin`).

---

### 19. Challenge
Rancang sebuah class proxy bernama `HermeticSandbox` yang bertindak sebagai *Object Boundary*:
- Sandbox ini membungkus sembarang objek target.
- Objek ini mengisolasi akses langsung dan memvalidasi bahwa hanya method yang didefinisikan secara eksplisit pada class target asli yang boleh diakses (menolak akses method dari `Object` umum seperti `dup`, `clone`, `instance_variable_set`, dsb).
- Sandbox wajib mempertahankan lookup asli untuk method target dengan overhead resolusi minimal.
- Implementasi tidak boleh mewarisi dari `Object`, melainkan wajib dari `BasicObject`.
- Sandbox wajib mendukung interceptor chaining dan tetap bekerja dengan `Kernel#binding`.

**Kriteria Penilaian:**
- Tidak boleh memicu alokasi memori berlebih saat resolusi cache miss.
- Penanganan `__send__` dan `__id__` tetap aman.
- Mendukung dynamic method inspection tanpa mengorbankan isolasi sandbox.

---

### 20. Summary
- **Ruby Object Model** didasarkan pada grafik pointer internal (`klass` dan `super`) yang dikonversi menjadi lintasan linier bernama **Ancestor Chain**.
- **Singleton Class (Eigenclass)** adalah class turunan anonim yang otomatis disisipkan Ruby untuk menampung method yang didefinisikan eksklusif pada objek/class individual.
- **`prepend` vs `include`**: `prepend` menyisipkan modul *sebelum* class pada rantai ancestor, ideal untuk intersepsi, sedangkan `include` menyisipkan modul *setelah* class target.
- **Stabilitas Virtual Machine**: Hindari mutasi method table dinamis pada fase eksekusi runtime produksi agar mekanisme *Inline Method Cache* (IMC) YARV dapat beroperasi optimal pada efisiensi puncak.