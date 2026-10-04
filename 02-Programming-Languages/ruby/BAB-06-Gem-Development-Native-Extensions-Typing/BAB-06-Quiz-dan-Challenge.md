# BAB 06: Quiz, Challenge, & Knowledge Check
**Gem Development, Native Extensions, & Typing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Mekanisme Resolusi Gem:**
   Bagaimana Rubygems dan Bundler memanipulasi `$LOAD_PATH` (atau `$:`) saat sebuah gem diaktifkan via `Bundler.require`? Jelaskan perbedaan mendasar antara direktori `lib/` yang otomatis di-*append* ke `$LOAD_PATH` dengan dependensi biner berarsitektur spesifik (seperti platform-dependent gems `x86_64-linux` vs `arm64-darwin`).

2. **Primitive Object Representation (`VALUE`) pada C Extensions:**
   Dalam `ruby.h`, tipe data `VALUE` merepresentasikan pointer atau *immediate value* (fixnum, symbol, boolean, nil) melalui teknik *pointer tagging*. Jelaskan bagaimana CRuby membedakan antara *immediate value* dan pointer heap riil hanya dengan memeriksa bit-bit terbawah (LSB) dari sebuah `VALUE`.

3. **Paradigma TypedData API vs Data API Klasik:**
   Mengapa penggunaan API legasi `Data_Wrap_Struct` dinyatakan *deprecated* dan digantikan oleh `TypedData_Wrap_Struct` bersama struct `rb_data_type_t`? Jelaskan peran spesifik dari *callback* `dmark`, `dfree`, dan `dsize` dalam siklus hidup CRuby Garbage Collector (GC), khususnya kaitannya dengan fitur *GC Compaction* (`rb_gc_register_address` / `RUBY_TYPED_WB_PROTECTED`).

4. **Karakteristik Tipifikasi: Sorbet vs. RBS/Steep:**
   Bandingkan filosofi desain tipe antara **Sorbet** dan **RBS/Steep**. Mengapa Sorbet memilih pendekatan hibrida (*runtime assertion* via `sig` decorator + *static analysis* via file `.rbi`), sedangkan core team Ruby memilih memisahkan metadata tipe ke dalam berkas `.rbs` independen tanpa modifikasi sintaksis Ruby di runtime?

5. **Interaksi C Native Extension dengan Global VM Lock (GVL):**
   Apa konsekuensi fatal jika sebuah fungsi komputasi berat (*CPU-bound*) atau operasi I/O pemblokir (*blocking I/O*) dieksekusi di dalam C Native Extension tanpa memanggil `rb_thread_call_without_gvl`? Sebaliknya, batasan memori apa yang mutlak dilarang ketika eksekusi kode berada di luar GVL (*unlocked state*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **GC Compaction & Object Movement Hazarding:**
   Anda memiliki fungsi C extension yang menerima argumen Ruby `String` berukuran besar. Di dalam fungsi tersebut, Anda mengambil raw pointer via `RSTRING_PTR(str)` dan menyimpannya ke dalam struct C lokal. Selama eksekusi, terjadi alokasi objek Ruby baru via `rb_str_new(...)`. Mengapa skenario ini berpotensi memicu *Undefined Behavior* (UB) atau *Segmentation Fault* pada Ruby 3.x dengan GC Compaction aktif, dan bagaimana cara memitigasinya secara deterministik?

2. **Dangling Pointers pada Rust FFI via Magnus / rb-sys:**
   Saat menulis native extension menggunakan Rust dengan *crate* `magnus`, sebuah referensi Rust (`&str` atau `&[u8]`) diikat ke objek `RString` milik Ruby. Jika kode Rust mengeksekusi operasi paralel menggunakan *rayon* di thread terpisah di luar konteks GVL, bagaimana `magnus` mencegah *use-after-free* apabila Ruby GC sewaktu-waktu berjalan di main thread dan mereklamasi memori string tersebut?

3. **Analisis Profiling Overhead: Sorbet Runtime Checks:**
   Sebuah *hot-path method* dieksekusi 5.000.000 kali per detik dalam *event-loop processing*. Developer menambahkan signature Sorbet `sig { params(payload: T::Hash[Symbol, T.untyped]).returns(T::Boolean) }`. Jelaskan secara mendalam dampak *CPU cycle overhead* yang diintroduksi oleh evaluasi runtime wrapper Sorbet, alokasi memori internalnya, dan bagaimana teknik `T::Sig::WithoutRuntime.sig` mengatasi degradasi tersebut.

4. **ABI Incompatibility dan Dynamic Linking Trap:**
   Sebuah gem native extension dikompilasi pada Ruby versi `3.2.2`. Ketika aplikasi di-*upgrade* ke Ruby `3.3.0` di lingkungan container tanpa menjalankan `gem pristine --all` atau kompilasi ulang bundle, terjadi error *symbol lookup error* atau VM crash instan saat proses *booting*. Jelaskan mengapa CRuby tidak menjamin kestabilan ABI antar minor release pada level ekstensi C internal dan struktur `rb_execution_context_t`.

5. **RBS Type Refinement & Subtyping Edge Cases:**
   Diberikan struktur tipe RBS berikut:
   ```rbs
   interface _Serializable
     def to_json: (*untyped) -> String
   end

   class Pipeline[out T < _Serializable]
     def process: () -> T
   end
   ```
   Jelaskan implikasi dari anotasi *variance* `out` (kovarian) pada parameter generik `T`. Masalah soundness apa yang akan dideteksi oleh *type checker* (Steep) jika Anda mencoba menambahkan method `def consume: (T data) -> void` ke dalam kelas `Pipeline` tersebut?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Crash Skala Besar Akibat Memori Bocor pada Image Processing Extension
* **Konteks:** Sebuah layanan e-commerce memproses jutaan transformasi gambar per jam menggunakan gem wrapper kustom berbasis pustaka C `libvips`/`libvips-magick`. Worker Puma mengalami degradasi performa: RSS (Resident Set Size) memori melonjak drastis hingga menyentuh OOM Killer Linux setiap 45 menit. Anehnya, metrik `GC.stat[:heap_live_slots]` menunjukkan jumlah objek Ruby relatif konstan dan stabil di angka 400.000 slot.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar penyebab ketidaksinkronan antara metrik `GC.stat` CRuby dan kenaikan *system RSS*. Mengapa GC Ruby tidak memicu siklus pembersihan secara proporsional terhadap alokasi memori di level C?
  2. Fungsi C API spesifik apa (`rb_gc_adjust_memory_usage` atau `ruby_xmalloc`) yang absen di dalam implementasi *wrapper* native tersebut?
  3. Bagaimana arsitektur *memory accounting* harus direkonstruksi agar CRuby mengetahui tekanan memori native (*malloc memory pressure*) yang terjadi di luar Ruby heap?

### Skenario B: Deadlock dan Race Condition pada Native Concurrency Extension
* **Konteks:** Tim infrastruktur membangun sebuah gem komputasi kriptografi multi-thread. Algoritma enkripsi dijalankan dengan melepaskan GVL menggunakan `rb_thread_call_without_gvl`. Namun, untuk kebutuhan metrik, fungsi C yang berjalan di worker thread background tersebut memanggil `rb_funcall(rb_mKernel, rb_intern("puts"), 1, rb_str_new_cstr("Chunk encrypted"))` atau memodifikasi Hash Ruby global secara langsung. Aplikasi mengalami hang permanen (*deadlock*) atau seketika crash dengan log `[BUG] Segmentation fault at 0x00000... Segmentation fault on non-Ruby thread`.
* **Pertanyaan Diagnostik:**
  1. Mengapa memanggil fungsi Ruby API atau mengalokasikan objek Ruby (`rb_str_new_cstr`, `rb_funcall`) dari thread non-Ruby / thread C tanpa GVL mengakibatkan kerusakan fatal pada VM heap?
  2. Desain ulang alur eksekusi tersebut: Bagaimana cara yang benar untuk mengembalikan hasil komputasi atau mengeksekusi *callback* ke Ruby context setelah fungsi C non-GVL selesai bekerja?
  3. Mekanisme sinkronisasi apa (`rb_thread_call_with_gvl` vs *asynchronous queue*) yang wajib diimplementasikan untuk mencegah *race condition* pada state VM?

### Skenario C: Dilema Arsitektur Transisi Core Engine: Sorbet vs. Rust Native Extension
* **Konteks:** Sebuah sistem *fraud detection engine* berbasis Ruby monolitik memproses transaksi finansial dengan throughput 25.000 RPS. Terjadi dua masalah kritis: (1) Tim engineering sering meloloskan *regression bug* akibat tipe data dinamis (*TypeError / NoMethodError* pada payload terorisasi/edge-cases), dan (2) Utilisasi CPU mencapai 90% karena serialisasi/deserialisasi payload dan validasi logika aturan matematika yang lambat.
* **Pertanyaan Diagnostik:**
  1. Jika diputuskan untuk menambahkan *static typing* (Sorbet vs RBS) untuk mengatasi masalah (1), analisis trade-off keduanya terkait performa kompilasi, CI runtime, kebersihan basis kode (*code ergonomics*), dan integrasi dengan metaprogramming Ruby yang dinamis.
  2. Untuk menyelesaikan masalah (2), arsitek mengusulkan penulisan ulang modul evaluasi menggunakan native extension. Evaluasi perbandingan risiko teknis antara mengimplementasikan C Extension murni vs Rust Native Extension via `magnus` / `rb-sys` (tinjau dari sisi *memory safety*, *fearless concurrency*, *toolchain maintenance*, dan portabilitas cross-compilation via `rake-compiler-dock`).
  3. Rumuskan rekomendasi arsitektur final: Kombinasi apa yang paling optimal untuk mengatasi masalah correctness dan throughput tanpa mengorbankan kecepatan iterasi developer?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Token Bucket Rate Limiter Gem dengan Native Backing dan RBS Type Definitions

#### Problem:
Infrastruktur API gateway internal membutuhkan sebuah Rate Limiter berbasis algoritma **Token Bucket** yang mampu menangani ratusan ribu pengecekan limit per detik per worker tanpa terhambat oleh GC overhead Ruby dan GVL contention, namun tetap aman digunakan di multi-threaded Puma workers.

#### Requirements:
1. **Core Logic Engine (C atau Rust Native Extension):**
   * Buat struktur data native `TokenBucket` yang menyimpan: `rate` (tokens/detik), `capacity` (maksimum tokens), `last_leak_time` (uint64 timestamp dalam nanodetik), dan `current_tokens` (double).
   * Implementasikan method C/Rust `#consume(tokens_to_take)` yang menghitung kalkulasi matematika secara akurat, mengembalikan `true` jika tokens mencukupi dan `false` jika tidak.
   * Operasi kalkulasi internal mutlak bebas dari alokasi objek Ruby di jalur panas (*zero Ruby heap allocation on hot path*).
   * Pastikan integrasi GC menggunakan `rb_data_type_t` modern dengan proteksi compaction (`RUBY_TYPED_FREE_IMMEDIATELY`).
2. **GVL & Thread Safety:**
   * Jika method `#consume_batch(array_of_weights)` dipanggil, ekstensi harus memvalidasi data dan mengeksekusi komputasi menggunakan mutex C native tanpa menahan GVL (`rb_thread_call_without_gvl`), memastikan thread Ruby lain tetap dapat memproses request.
3. **Type Safety & RBS Definitions:**
   * Tulis berkas antarmuka `sig/token_bucket.rbs` secara lengkap dan ketat. Definisikan modul, kelas, konstruktor, serta signature method `#consume`, `#consume_batch`, dan `#current_state`.
   * Lakukan validasi tipe menggunakan CLI `steep check` tanpa menghasilkan error atau `untyped` leakage yang tidak diinginkan.
4. **Standard Gem Structure:**
   * Proyek harus terstruktur sesuai kaidah Bundler: memuat `.gemspec` yang valid, `ext/token_bucket/extconf.rb` (atau `Cargo.toml` jika menggunakan Rust), `lib/token_bucket.rb` sebagai *entry point*, dan test suite berbasis `RSpec` atau `Minitest`.

#### Constraints:
* **Ruby Version:** Ruby 3.2.0+.
* **Memory Constraints:** Tidak ada *memory leak* (RSS stabil saat dibombardir 10.000.000 iterasi).
* **Fail-Safe:** Ekstensi C dilarang menggunakan macro lama `Data_Wrap_Struct`.
* **Zero Untyped in Interface:** File RBS harus lolos audit `steep check` dengan level konfigurasi ketat (`strict`).

#### Expected Output:
* Repositori struktur gem yang fungsional:
  ```text
  ├── Gemfile
  ├── Rakefile
  ├── token_bucket.gemspec
  ├── ext/token_bucket/
  │   ├── extconf.rb (atau Cargo.toml)
  │   └── token_bucket.c (atau src/lib.rs)
  ├── lib/
  │   └── token_bucket/
  │       ├── version.rb
  │       └── token_bucket.rb
  ├── sig/
  │   └── token_bucket.rbs
  ├── Steepfile
  └── spec/
      └── token_bucket_spec.rb
  ```
* Log benchmark yang mendemonstrasikan throughput: Native implementation harus mencapai minimal **5x throughput** dibandingkan implementasi algoritma yang sama dalam *Pure Ruby*, serta terbukti *thread-safe* saat diuji dengan 16 concurrent threads di Ruby.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi memori CRuby: Mekanisme *Pointer Tagging* pada tipe `VALUE` (`RUBY_T_FIXNUM`, `RUBY_Qnil`, `RUBY_Qfalse`, `RUBY_Qtrue`, `RUBY_T_SYMBOL`).
- [ ] Siklus hidup `TypedData_Wrap_Struct`, pembuatan struct `rb_data_type_t`, fungsi *callback* GC (`dmark`, `dfree`, `dsize`, `dcompact`), dan implikasi *GC compaction*.
- [ ] Aturan interaksi Global VM Lock (GVL): Kapan dan bagaimana melepaskan GVL (`rb_thread_call_without_gvl`) serta larangan mutlak menyentuh Ruby heap / Ruby API saat GVL dilepas.
- [ ] Arsitektur tipifikasi Sorbet: Metaprogramming runtime layer, abstraksi RBI, performa static execution via Sorbet C++ compiler (`sorbet-orig`).
- [ ] Arsitektur tipifikasi RBS: Sistem tipe terpisah, AST RBS, integrasi Steep, dynamic duck-typing interfaces, subtyping, dan variance (`out` / `in`).
- [ ] Proses kompilasi native gem: Pipeline `mkmf`, generasi Makefile melalui `extconf.rb`, integrasi cross-platform via `rake-compiler` dan cross-compilation docker containers.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor ID internal enum tipe CRuby (`T_OBJECT`, `T_STRING`, `T_ARRAY`, dll.) di header `ruby/intern.h`. Cukup gunakan macro tipe publik seperti `RB_TYPE_P` atau `Check_Type`.
- [ ] Semua konfigurasi flags kompiler C/Rust (`-fPIC`, `-shared`, `cargo flags`). Konfigurasi ini ditangani secara otomatis oleh `mkmf`, `rb-sys`, atau `rake-compiler`.
- [ ] Daftar lengkap signature library standar di dalam RBS repository (`gem 'rbs'`). Gunakan CLI command `rbs collection` atau lookup dokumentasi tipe RBS bawaan.

### Saya harus bisa melakukan:
- [ ] Menulis, melakukan *build*, dan melakukan *linking* ekstensi native CRuby (C atau Rust) yang terintegrasi secara aman dengan Garbage Collector.
- [ ] Mengidentifikasi dan membasmi *memory leaks* serta *segmentation faults* pada Native Extension menggunakan debugger sistem (`gdb`, `lldb`, atau `valgrind`).
- [ ] Menghubungkan library C pihak ketiga eksternal ke dalam sebuah Ruby Gem melalui mekanisme deklarasi `have_library` / `have_header` pada `extconf.rb`.
- [ ] Mendesain dan mengimplementasikan sistem pengetikan ketat pada Ruby gem menggunakan **RBS** dan mengaudit kebenaran tipe menggunakan **Steep**.
- [ ] Mengonfigurasi automated build pipeline untuk merilis gem binary multi-platform (`x86_64-linux`, `aarch64-linux`, `arm64-darwin`, `x64-mingw32`) menggunakan `rake-compiler-dock` dan GitHub Actions.