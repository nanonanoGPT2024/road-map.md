# Bab 07 Module 01: Ruby Object Model & Dynamic Method Resolution Architecture

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengurai representasi internal memori dari objek Ruby (`RBasic` dan `RClass`) pada level implementasi CRuby (YARV).
- Memetakan dan merekayasa jalur *Method Lookup Path* secara deterministik menggunakan modul (`include`, `prepend`, `extend`) dan *Singleton Classes* (*Eigenclasses*).
- Mengimplementasikan pola interceptor berbasis `Module#prepend` untuk instrumentasi performa tingkat produksi tanpa menimbulkan *aliasing collision*.
- Mengidentifikasi dan memitigasi degradasi performa akibat *Inline Method Cache (IMC) invalidation* pada sistem throughput tinggi.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Sintaksis dasar Object-Oriented Ruby (definisi class, module, dan inheritance konvensional via `<`).
- Konsep dasar pointer, alokasi heap vs stack, dan struktur data pointer-chasing di runtime.
- Ekosistem Ruby CLI (`irb`, `ruby`) dan kemampuan membaca kode sumber C dasar (untuk konteks C API CRuby).

---

### 3. Concept
Dalam Ruby, **segala hal adalah objek**, dan setiap pemanggilan method (`receiver.message(args)`) pada dasarnya adalah proses pengiriman pesan (*message passing*) yang dievaluasi secara dinamis pada saat runtime. 

Secara internal pada CRuby (MRI), sebuah objek direpresentasikan oleh struct C bernama `RBasic`, yang memiliki dua pointer fundamental:
1. `flags`: Bitmask metadata (status garbage collection, tipe data internal `T_OBJECT`, pembekuan objek/frozen status).
2. `klass`: Pointer ke kelas instansiasi langsung yang bertanggung jawab mendefinisikan method objek tersebut.

```
       +-----------------------+
       |     RBasic Struct     |
       +-----------------------+
       | flags : VALUE (bits)  |
       | klass : VALUE* (ptr)  |-----> Menunjuk ke RClass
       +-----------------------+
```

Kelas di Ruby sendiri merupakan objek dari kelas `Class` (turunan dari `Module`). Ketika pemanggilan method terjadi:
1. Runtime mengecek pointer `klass` dari receiver.
2. Jika objek memiliki modifikasi unik (singleton methods), `klass` akan menunjuk ke **Singleton Class** (*Eigenclass* atau *metaclass*), kelas anonim yang disisipkan secara transparan di antara objek dan kelas aslinya.
3. Runtime menelusuri rantai **`super` pointer** dari struct `RClass` yang saling terhubung membentuk **Ancestors Chain**.
4. Pencarian method berlanjut ke atas hingga method ditemukan pada `m_tbl` (method table) di salah satu `RClass`, atau rantai berakhir di `BasicObject`.
5. Jika tidak ditemukan pada seluruh rantai, runtime memutar balik pencarian dari awal untuk mengeksekusi pesan `method_missing`.

---

### 4. Why
Memahami Ruby Object Model bukan sekadar teori akademis; ini adalah persyaratan rekayasa perangkat lunak untuk:
- **Zero-Downtime Instrumentation**: Membangun APM (*Application Performance Monitoring*), profiler, dan logging wrapper menggunakan `Module#prepend` yang bersih tanpa merusak kompatibilitas pustaka pihak ketiga.
- **Menghindari Perilaku Flaky Monkey-Patching**: Mencegah tabrakan namespace method (*method collision*) antar-gem dependensi.
- **Optimasi Performa Mesin Virtual (YARV)**: Menjaga stabilitas *Global Method Cache* (GMC) dan *Inline Method Cache* (IMC). Modifikasi dinamis pada class hierarchy runtime yang tidak terkontrol membatalkan cache metode mesin virtual, menyebabkan de-optimasi eksekusi bytecode Ruby.

---

### 5. What
Komponen inti dalam Method Lookup Path meliputi:

| Komponen | Tipe Entitas | Fungsi Utama |
| :--- | :--- | :--- |
| **`RClass`** | C Struct | Menyimpan `m_tbl` (tabel metode), `iv_tbl` (tabel variabel instan), dan pointer `super`. |
| **Singleton Class (`#<Class:obj>`)** | Anonymous `RClass` | Menampung method khusus milik satu instansi spesifik atau class methods. |
| **`include` (IClass)** | Inclusion Node | Menyisipkan modul **tepat di atas** kelas target pada rantai leluhur (*super-chain*). |
| **`prepend` (PClass)** | Proxy Class | Menyisipkan modul **tepat di bawah** kelas target (menjadi penerima prioritas sebelum kelas itu sendiri). |
| **`extend`** | Macro | Menjalankan `include` ke dalam **Singleton Class** dari receiver. |
| **`method_missing`** | Fallback Handler | Kait (*hook*) pemanggilan dinamis saat method resolution mencapai `BasicObject` tanpa kecocokan. |

---

### 6. How
Alur kerja resolusi pemanggilan method (`receiver.execute`) dieksekusi melalui algoritma deterministik berikut:

```
[Mulai Resolusi: receiver.execute]
                   │
                   ▼
       Cek Singleton Class receiver?
        ├── Ada: Mulai traversal dari Singleton Class
        └── Tidak: Mulai traversal dari Class receiver
                   │
                   ▼
        ┌────────────────────────────────────────────────────────┐
        │ LOOP TRAVERSAL ANCESTORS                               │
        │ 1. Periksa `prepend` modules dari node saat ini       │
        │ 2. Periksa definisi method pada node (`m_tbl`)         │
        │ 3. Periksa `include` modules dari node saat ini       │
        │ 4. Geser pointer ke node `super`                       │
        └────────────────────────────────────────────────────────┘
                   │
         Method ditemukan?
        ├── YA: Eksekusi bytecode method (Terminasi sukses)
        └── TIDAK: Pointer mencapai ujung (Nil / BasicObject)
                   │
                   ▼
     Resolusi fallback: receiver.method_missing(:execute)
                   │
    Ulangi traversal lookup untuk method_missing
        ├── Ditemukan: Eksekusi handler fallback
        └── Gagal: Naikkan exception (NoMethodError)
```

---

### 7. Analogy
Bayangkan proses eskalasi hukum dalam sebuah korporasi:
- **Objek:** Karyawan operasional.
- **Singleton Class:** Pengacara pribadi berdedikasi tinggi yang berdiri langsung di depan karyawan; semua panggilan verifikasi dokumen diperiksa oleh pengacara ini terlebih dahulu.
- **Prepend Module:** Tim audit eksternal yang diwajibkan memeriksa berkas **sebelum** manajer divisi sempat membacanya.
- **Class Utama:** Manajer divisi internal karyawan.
- **Include Module:** Konsultan pihak ketiga yang dihubungi jika manajer divisi tidak memiliki keahlian terkait.
- **Superclass:** Direktur Eksekutif (atasan manajer).
- **`method_missing`:** Meja penanganan masalah darurat umum (*Public Relations Crisis Management*) ketika tidak ada satupun manajer atau konsultan yang mengenali masalah tersebut.

---

### 8. Diagram

```
+-------------------------------------------------------------------------+
|                  METHOD RESOLUTION VISUALIZATION CHAIN                  |
+-------------------------------------------------------------------------+

              Instansiasi Objek:  worker = Worker.new
                                     |
                                     | (klass pointer)
                                     v
                           +-------------------+
                           | #<Class:worker>   | (Singleton Class - jika ada)
                           +-------------------+
                                     | super
                                     v
                           +-------------------+
                           |  AuditInterceptor | (Prepend Module)
                           +-------------------+
                                     | super
                                     v
                           +-------------------+
                           |      Worker       | (Target Class)
                           +-------------------+
                                     | super
                                     v
                           +-------------------+
                           |     Helpable      | (Include Module)
                           +-------------------+
                                     | super
                                     v
                           +-------------------+
                           |   BaseEmployee    | (Superclass)
                           +-------------------+
                                     | super
                                     v
                           +-------------------+
                           |      Object       |
                           +-------------------+
                                     | super
                                     v
                           +-------------------+
                           |    BasicObject    |
                           +-------------------+
                                     |
                                    NIL
```

---

### 9. Simple Example
Kode berikut menunjukkan bagaimana `prepend`, kelas asal, dan `include` menentukan urutan eksekusi method.

```ruby
module IncludeModule
  def execute
    "3. Dari IncludeModule -> #{super rescue 'END'}"
  end
end

module PrependModule
  def execute
    "1. Dari PrependModule -> #{super}"
  end
end

class BaseProcessor
  include IncludeModule

  def execute
    "2. Dari BaseProcessor -> #{super}"
  end
end

class PaymentProcessor < BaseProcessor
  prepend PrependModule
end

processor = PaymentProcessor.new
puts processor.execute
# Output:
# 1. Dari PrependModule -> 2. Dari BaseProcessor -> 3. Dari IncludeModule -> END

puts "\nAncestors Chain PaymentProcessor:"
puts PaymentProcessor.ancestors.inspect
# Output:
# [PrependModule, PaymentProcessor, BaseProcessor, IncludeModule, Object, Kernel, BasicObject]
```

---

### 10. Practical Example
Pola tingkat produksi untuk Instrumentasi Metrik Latensi menggunakan `Module#prepend` yang bersih tanpa merusak call hierarchy dari dependensi lain.

```ruby
# frozen_string_literal: true

require 'benchmark'
require 'logger'

module Observability
  # Interceptor modular menggunakan prepend
  module LatencyTracer
    def perform_transaction(payload)
      start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      
      # Memanggil implementasi asli pada target class
      result = super(payload)
      
      duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
      log_metric(:success, duration)
      result
    rescue StandardError => e
      duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
      log_metric(:failure, duration, e.message)
      raise e
    end

    private

    def log_metric(status, duration, error_msg = nil)
      logger = Logger.new($stdout)
      logger.info(
        {
          event: 'transaction_performance',
          status: status,
          duration_ms: (duration * 1000).round(4),
          caller_class: self.class.name,
          error: error_msg
        }.to_s
      )
    end
  end
end

class CoreBankingGateway
  def perform_transaction(payload)
    # Simulasi latency I/O transaksi perbankan
    sleep(0.05)
    raise ArgumentError, 'Invalid settlement routing' if payload[:amount] <= 0

    { status: 200, transaction_id: "TX-#{SecureRandom.hex(6).upcase}" }
  end
end

# Injeksi instrumentasi secara deklaratif tanpa mengubah kode inti gateway
CoreBankingGateway.prepend(Observability::LatencyTracer)

# Inisialisasi dan pengujian transaksi
gateway = CoreBankingGateway.new

# 1. Jalur Sukses
puts 'Executing valid transaction:'
gateway.perform_transaction({ amount: 15_000_000, account: 'ACC-98124' })

# 2. Jalur Gagal
puts "\nExecuting invalid transaction:"
begin
  gateway.perform_transaction({ amount: -500, account: 'ACC-98124' })
rescue ArgumentError => e
  puts "Caught expected error: #{e.message}"
end
```

---

### 11. Real World Example
Pada arsitektur monolit berskala besar seperti Shopify (`shopify/shopify-core`) atau sistem caching kompleks berbasis framework Ruby on Rails, arsitektur `ActiveSupport::Concern` dan resolusi method lookup dimanfaatkan untuk mengimplementasikan *Multi-Store Database Sharding*.

Ketika query database dilakukan:
1. `ActiveRecord::Base` memiliki modul *sharding router* yang disuntikkan via `prepend`.
2. Modul ini mencegat pemanggilan method koneksi basis data: `connection`.
3. Sebelum query dikirimkan ke pool ActiveRecord, interceptor memeriksa `Current.shard_env`.
4. Rantai `super` dipanggil untuk mengambil koneksi database yang terisolasi khusus shard tersebut.
5. Jika pengembang menggunakan `alias_method` konvensional di banyak plugin, rantai wrapper berpotensi menyebabkan *circular dependency bug* jika urutan pemuatan berkas gem (`require`) berubah saat boot. Penggunaan arsitektur `prepend` pada layer framework level bawah mencegah siklus rekursi tak berhingga (*stack level too deep*) di ribuan proses worker Puma yang berjalan secara simultan.

---

### 12. Trade-offs

| Dimensi | Module Prepend / Ancestor Injection | Dynamic Method Definition (`define_method`) | Fallback Method (`method_missing`) |
| :--- | :--- | :--- | :--- |
| **Keuntungan** | Alur linear, kompatibel dengan `super`, terstruktur dalam debugging stack trace. | Menghemat penulisan method repetitif secara statis di runtime class. | Sangat fleksibel untuk routing dinamis (misal: JSON-RPC, OpenStruct). |
| **Kerugian** | Memanjangkan ancestors chain; butuh pemahaman mendalam tentang OOP Ruby. | Menghasilkan method objek permanen di heap, menambah konsumsi memori. | Signifikan menurunkan performa; stack trace rumit dibaca. |
| **Kompleksitas** | Moderat (berada di level arsitektur kelas). | Rendah hingga Sedang (berada di level metaprogramming). | Sangat Tinggi (wajib mengimplementasikan `respond_to_missing?`). |
| **Performa YARV** | Cepat (dapat dioptimalkan oleh Inline Method Cache). | Cepat setelah definisi selesai dikompilasi ke bytecode. | Lambat (pemeriksaan linear seluruh rantai + pembatalan cache). |
| **Cost Debugging** | Rendah: terlihat via `Module#ancestors` dan `Method#source_location`. | Moderat: lokasi kode merujuk ke blok definisi closure. | Tinggi: tidak dapat diinspeksi secara langsung via `methods`. |

---

### 13. When To Use
Gunakan manipulasi Method Lookup Path dan Singleton Class saat:
- Merancang library atau framework middleware yang membutuhkan interceptor transparan (misal: APM Tracers, Audit Trails, Policy Enforcement).
- Memerlukan kustomisasi perilaku instans individual tanpa memengaruhi instans lain dari kelas yang sama via *Singleton Class*.
- Mengisolasi monkey-patching terhadap pustaka pihak ketiga secara aman dan dapat dilacak (*traceable*).

---

### 14. When NOT To Use
Hindari pendekatan ini jika:
- Masalah dapat diselesaikan secara sederhana menggunakan pola desain konvensional seperti **Decorator** atau **Strategy Pattern** murni via komposisi objek.
- Berada di dalam loop komputasi kritis (*hot-path math-heavy computation*) di mana modifikasi rantai method lookup terus-menerus membatalkan *Inline Method Cache* YARV.
- Tim rekayasa software belum memiliki standar konvensi metaprogramming yang matang; penggunaan tanpa regulasi akan memicu kebingungan debugging (*spaghetti architecture*).

---

### 15. Common Mistakes
1. **Mengabaikan `super` saat memvalidasi `respond_to_missing?`:**
   ```ruby
   # FATAL: Merusak mekanisme pengecekan bawaan Ruby
   def respond_to_missing?(method_name, include_private = false)
     method_name.to_s.start_with?('find_by_') || false # SALAH: Harusnya memanggil super
   end

   # BENAR:
   def respond_to_missing?(method_name, include_private = false)
     method_name.to_s.start_with?('find_by_') || super
   end
   ```

2. **Menggunakan `alias_method` ganda yang menyebabkan Infinite Recursion:**
   Saat dua modul saling menimpa method yang sama menggunakan `alias_method :old_m, :m`, referensi `old_m` akan saling menunjuk jika modul di-load ulang (*hot-reloading* di lingkungan development). Solusi: gunakan `Module#prepend`.

3. **Membuat Singleton Class secara tidak sengaja (*Metaclass Explosion*):**
   Memanggil `obj.singleton_class` pada ribuan objek seumur hidup pendek (*short-lived objects*) memaksa Ruby membuat struct `RClass` baru di heap untuk masing-masing objek tersebut, membebani alokasi memori dan Garbage Collector.

---

### 16. Best Practices
- [ ] **Prioritaskan `Module#prepend`** dibanding `alias_method` untuk modifikasi method lintas layer arsitektur.
- [ ] **Selalu pasangkan `method_missing` dengan `respond_to_missing?`** untuk menjamin konsistensi saat instans diperiksa menggunakan `Object#respond_to?`.
- [ ] **Batasi kedalaman Ancestors Chain**: Usahakan rantai `.ancestors` tidak melebihi kedalaman wajar (umumnya < 15 layer) demi menjaga efisiensi resolusi traversal method.
- [ ] **Gunakan `Method#owner` dan `Method#source_location`** saat logging atau debugging untuk melacak modul persis tempat implementasi method berada.
- [ ] **Bekukan (*freeze*) modul interceptor** setelah dimuat untuk mencegah modifikasi runtime yang menginvalidasi cache metode global YARV.

---

### 17. Troubleshooting

#### Identifikasi Asal Usul Method
Jika method menghasilkan nilai tak terduga, periksa pemilik asli method tersebut dengan kode berikut:
```ruby
method_object = instance.method(:disputed_method)
puts "Owner: #{method_object.owner}"
puts "File: #{method_object.source_location[0]}"
puts "Line: #{method_object.source_location[1]}"
```

#### Melacak Perubahan Global Method Cache (GMC)
Jika performa aplikasi turun drastis setelah injeksi modul, periksa invalidasi cache method menggunakan flag internal Ruby:
```ruby
# Hanya pada lingkungan debugging lokal:
puts RubyVM.stat(:global_method_state) # Angka ini akan bertambah setiap kali ada modifikasi class/ancestor
```
Jika angka `global_method_state` melonjak drastis selama runtime produksi bekerja, ada komponen yang terus mendefinisikan kelas atau modul secara dinamis di dalam alur transaksi request-response.

---

### 18. Exercise
Implementasikan skenario berikut:
1. Buat class bernama `DataPipeline` yang memiliki method `process(data)` yang membalik string `data`.
2. Buat module `SanitizerInterceptor` yang menggunakan `Module#prepend` untuk menghapus semua karakter spasi putih berlebih dari `data` sebelum `DataPipeline#process` dieksekusi.
3. Cetak array `DataPipeline.ancestors` untuk memverifikasi urutan penempatan modul pada hierarchy chain.

---

### 19. Challenge
Rancang sebuah micro-framework plugin bernama `SafeFilterChain`:
- Memiliki satu target engine: `OrderService` dengan method `checkout(order_context)`.
- Sediakan mekanisme registrasi plugin berbasis dynamic module injection.
- Plugin yang terdaftar harus diurutkan berdasarkan `priority` (integer). Modul dengan prioritas tertinggi harus mengeksekusi logikanya paling awal di ancestors chain.
- Interceptor wajib memvalidasi isi `order_context`. Jika kunci `:authenticated` bernilai false, interceptor harus memutus siklus pemanggilan (tidak memanggil `super`) dan langsung mengembalikan payload error, tanpa memicu uncaught exception.
- Seluruh pipeline eksekusi harus aman dari *infinite loop* saat modul didaftarkan ulang berkali-kali.

---

### 20. Summary
- **Ruby Object Model** dibangun di atas struct C level rendah (`RBasic` dan `RClass`), di mana pemanggilan method diselesaikan melalui penelusuran pointer `super` sepanjang rantai `ancestors`.
- **Singleton Class** adalah kelas anonim berprioritas tinggi yang disisipkan tepat sebelum kelas asli objek ketika method instans individual didefinisikan.
- **`Module#prepend`** merevolusi cara interceptor bekerja di Ruby dengan menyisipkan modul di depan kelas target, mempertahankan integritas traversal `super` secara alami tanpa risiko *aliasing loops*.
- Mengelola method resolution path secara sadar meminimalkan mutasi struktur kelas runtime, menjaga kestabilan **Inline Method Cache** mesin virtual CRuby, serta memastikan stabilitas performa sistem berskala besar.