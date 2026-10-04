# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (BAB-06: Gem Development, Native Extensions & Typing)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengimplementasikan C Native Extensions menggunakan Ruby C-API (`ruby.h`) dan Rust Native Extensions menggunakan `magnus` dengan performa optimal.
- Menguasai manajemen memori lintas runtime (CRuby Garbage Collector vs C/Rust allocators), mitigasi memori bocor (*memory leak*), serta penanganan konkurensi melalui pelepasan Global VM Lock (GVL) via `rb_thread_call_without_gvl`.
- Membangun dan mengotomatisasi pipeline kompilasi multi-platform cross-compilation (Linux x86_64/aarch64, macOS arm64/x86_64, Windows) memanfaatkan `rake-compiler` dan `rake-compiler-dock`.
- Menerapkan sistem pengetikan statis tingkat lanjut (*progressive typing*) berbasis RBS, TypeProf, dan Steep pada gem berskala enterprise untuk menjamin keandalan tipe saat kompilasi tanpa mengorbankan fleksibilitas dinamis Ruby.

---

## 2. Prerequisite
- Pemahaman mendalam tentang siklus hidup Ruby VM (YARV), struktur data internal C (pointer, heap, stack, `malloc`/`free`), dan ekosistem Rust (Cargo, *ownership*, *borrow checker*, FFI).
- Terbiasa dengan perkakas dasar Gem: Bundler, Rake, dan gemspec standard.
- Lingkungan pengembangan lokal: GCC/Clang, Make, Rust Toolchain (`cargo`, `rustc`), Ruby 3.2+ terpasang via rbenv/asdf dengan header development (`ruby-dev` atau instalasi dari source).

---

## 3. Concept & Internal Architecture

### 3.1 Ruby C-API & VALUE Architecture
Di dalam CRuby (YARV), semua variabel Ruby direpresentasikan sebagai tipe pointer C tunggal: `VALUE`. Struktur `VALUE` adalah representasi `uintptr_t` yang menggunakan teknik *pointer tagging*.

```
Bit layout pada 64-bit architecture:
=============================================================
| Pointer Address (Heap-allocated Object)             | 0 0 | -> T_OBJECT, T_STRING, dll.
| 62-bit Signed Integer (Fixnum)                      |   1 | -> RUBY_FIXNUM_FLAG
| 62-bit Flonum (Floating point numbers)              | 1 0 | -> RUBY_FLONUM_MASK
| Special Constants (false, true, nil, undef)         | 0 0 | -> Khusus diatur via masks
=============================================================
Contoh Konstanta:
RUBY_Qfalse = 0x00
RUBY_Qtrue  = 0x14
RUBY_Qnil   = 0x08
RUBY_Qundef = 0x34
```

Jika dua bit terbawah bernilai non-zero, data tersebut disimpan *inline* di dalam `VALUE` tanpa alokasi heap (*immediate values*). Jika bernilai `0x00`, `VALUE` adalah sebuah pointer yang merujuk pada `struct RObject` di dalam Ruby Heap Pages.

### 3.2 Ruby Garbage Collector (Compacting GC) & TypedData
Penggunaan struktur legasi `Data_Wrap_Struct` telah ditinggalkan karena tidak aman terhadap *Object Compaction* (GC Compaction). CRuby modern mewajibkan implementasi `TypedData_Wrap_Struct` dengan struktur pendukung `rb_data_type_t`.

```c
static const rb_data_type_t custom_buffer_data_type = {
    .wrap_struct_name = "CustomBuffer",
    .function = {
        .dmark = custom_buffer_mark,     /* Menandai Ruby object di dalam C struct */
        .dfree = custom_buffer_free,     /* Deallokasi memory C non-Ruby */
        .dsize = custom_buffer_memsize,  /* Profiling GC: melaporkan footprint memori */
        .dcompact = custom_buffer_compact /* Hook untuk Compacting GC (re-pin pointer) */
    },
    .parent = NULL,
    .data = NULL,
    .flags = RUBY_TYPED_FREE_IMMEDIATELY | RUBY_TYPED_WB_PROTECTED
};
```

- **`dmark`**: Wajib didefinisikan jika C *struct* menyimpan referensi `VALUE` lain. Tanpa *marking*, Ruby GC akan menganggap objek tersebut *unreachable* dan membersihkannya, mengakibatkan *dangling pointer* atau *Segmentation Fault*.
- **`dfree`**: Dipanggil saat Garbage Collector menyapu (*sweeps*) objek. Wajib memanggil fungsi deallokasi native yang bersesuaian (`free`, `rust_dealloc`).
- **`dcompact`**: Mengizinkan GC untuk memindahkan objek di memori demi mengurangi fragmentasi. C struct yang menyimpan pointer `VALUE` harus mengupdate pointernya di callback ini menggunakan `rb_gc_location()`.

### 3.3 The GVL and Blocking Operations
Ruby mengeksekusi instruksi Ruby di bawah kontrol *Global VM Lock* (GVL). Satu thread OS hanya dapat mengeksekusi instruksi Ruby pada satu waktu per Ruby VM.
Jika ekstensi native menjalankan komputasi intensif atau operasi I/O yang memakan waktu:
1. GVL akan menahan semua *Ruby-level Threads* lainnya.
2. Solusi: Lepaskan GVL menggunakan `rb_thread_call_without_gvl()`.
3. **Peringatan Mutlak:** Di dalam fungsi yang dijalankan tanpa GVL, Anda **DILARANG KERAS** memanggil fungsi Ruby C-API apa pun yang dapat menyentuh Ruby heap atau memicu alokasi/GC (misalnya `rb_str_new`, `rb_ary_push`). Pelanggaran terhadap aturan ini menghasilkan *race condition* internal dan crash seketika (*SEGV*).

```c
void *heavy_computation(void *data) {
    // AMAN: Raw C code, SIMD, standard C math, libcrypto, OS syscalls
    // HARAM: rb_funcall, rb_str_new, VALUE manipulation
    return result;
}

VALUE rb_heavy_wrapper(VALUE self) {
    // Lepaskan GVL
    void *result = rb_thread_call_without_gvl(heavy_computation, arg, rb_nogvl_cancel_func, NULL);
    // GVL diakuisisi kembali secara otomatis di sini
    return transform_to_ruby_value(result);
}
```

### 3.4 Rust Magnus Architecture
`magnus` membungkus Ruby C-API ke dalam ekosistem Rust yang aman (*type-safe* & *memory-safe*). Magnus memanfaatkan sistem kepemilikan (*ownership*) Rust untuk memastikan referensi objek Ruby tidak bertahan lebih lama dari siklus hidup yang diizinkan GC, serta memetakan eksepsi Ruby menjadi tipe `Result<T, magnus::Error>`. Magnus menghilangkan overhead boilerplate C sekaligus mengeliminasi *undefined behavior* secara deterministik.

---

## 4. Why & What

| Dimensi | Standard Ruby Gem | C Native Extension | Rust (`magnus`) Native Extension |
| :--- | :--- | :--- | :--- |
| **Kecepatan Komputasi** | Baseline (Interpreted/YARV JIT) | Ekstrem (10x - 100x lebih cepat) | Ekstrem (Setara C, auto-vektorisasi LLVM) |
| **Keamanan Memori** | Tinggi (Managed Runtime) | Sangat Rendah (*Buffer Overflow, SEGV*) | Sangat Tinggi (Diverifikasi Kompiler) |
| **Portabilitas** | Murni (Tinggi, universal) | Rendah (Butuh Toolchain C di host/precompiled) | Menengah-Rendah (Butuh Rust LLVM toolchain) |
| **Paralelisme** | Terikat GVL (Concurrency, bukan Parallel) | Sejati (Bebaskan GVL via pthreads) | Sejati (Bebaskan GVL via Rayon/Crossbeam) |
| **Maintenance Cost** | Rendah | Tinggi (Beban alokasi memori manual) | Menengah (Dukungan *type safety* Rust) |

---

## 5. How (Workflow Detail)

Alur kerja pengembangan dan rilis enterprise native gem:

```
[Gem Directory Structuring]
         │
         ├── Implementasi Native Code (ext/my_gem/...)
         │      ├── C: extconf.rb + *.c + *.h
         │      └── Rust: Cargo.toml + extconf.rb + lib.rs
         │
         ├── Implementasi Strict Typing (sig/my_gem/...)
         │      └── *.rbs files & Steepfile configuration
         │
         ▼
[Local Compilation & Testing]
         │ ──> compile: rake compile (via rake-compiler / rb-sys)
         │ ──> test: bundle exec rspec
         │ ──> typecheck: bundle exec steep check
         │
         ▼
[Cross-Compilation Matrix (CI/CD)]
         │ ──> Menggunakan rake-compiler-dock (Docker containers)
         │ ──> Build artifacts:
         │        ├── x86_64-linux, aarch64-linux
         │        ├── x86_64-darwin, arm64-darwin (Universal macOS)
         │        └── x64-mingw-ucrt (Windows)
         │
         ▼
[Package & Attestation]
         └── Gem Release: gem push my_gem-<version>-<platform>.gem
```

---

## 6. Analogy & Diagram ASCII

Bayangkan Ruby VM adalah sebuah **Pusat Logistik Perkantoran Ber-AC (Managed Sandbox)**.
Semua barang (Objek) didaftarkan dan dipindahkan oleh kurir khusus (Garbage Collector). Tidak ada kecelakaan; semua aman, tapi ada aturan birokrasi yang membatasi kecepatan angkut barang (GVL).

Menjalankan **C/Rust Native Extension** seperti membuka pintu rahasia ke **Gudang Kontainer Otomatis di Luar Gedung (Bare-Metal Platform)**:
- Pekerja dapat memindahkan muatan dengan *crane* berkecepatan tinggi tanpa aturan birokrasi perkantoran (Bypass GVL).
- **Bahaya:** Jika pekerja gudang membawa material ke dalam kantor tanpa lapor ke sistem administrasi (lupa fungsi `dmark`), kurir kantor akan membuang barang tersebut karena dianggap sampah, meruntuhkan seluruh operasional kantor (**Segmentation Fault / Core Dump**).

```
                      RUBY PROCESS BOUNDARY
┌─────────────────────────────────────────────────────────────┐
│                        YARV Runtime                         │
│  Thread 1 (Ruby)      Thread 2 (Ruby)       GC Controller   │
│         │                    │                     │        │
│         └───────────┬────────┘                     │        │
│                     ▼                              ▼        │
│                [  GVL  ]                    [ Ruby Heap ]   │
│                     │                       (VALUE Objects) │
│      ═══════════════╪══════════════════════════════╪════════│
│                     │ rb_thread_call_without_gvl() │        │
│                     ▼                              │        │
│          ┌──────────────────────┐                  │ dmark  │
│          │   Native Execution   │                  │ checks │
│          │  (C Lib / Rust SIMD) │                  ▼        │
│          │                      │ ──dangling?──> [CRASH]    │
│          │ (No Ruby Allocations)│                           │
│          └──────────────────────┘                           │
│                     │                                       │
│             Raw System Malloc                               │
│                     ▼                                       │
│             [ Native Memory ]                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: C Extension Mini-Parser
Implementasi kalkulasi representasi hash biner cepat dengan `extconf.rb` dan C.

**`ext/fast_hasher/extconf.rb`**
```ruby
require "mkmf"

abort "Clang or GCC required" unless have_devel()
$CFLAGS << " -O3 -Wall -Wextra"
create_makefile("fast_hasher/fast_hasher")
```

**`ext/fast_hasher/fast_hasher.c`**
```c
#include <ruby.h>

static VALUE rb_fast_checksum(VALUE self, VALUE rb_str) {
    Check_Type(rb_str, T_STRING);

    const char *data = RSTRING_PTR(rb_str);
    long len = RSTRING_LEN(rb_str);
    
    uint64_t hash = 14695981039346656037ULL; // FNV-1a offset
    for (long i = 0; i < len; i++) {
        hash ^= (uint8_t)data[i];
        hash *= 1099511628211ULL; // FNV prime
    }

    return ULL2NUM(hash);
}

void Init_fast_hasher(void) {
    VALUE mFastHasher = rb_define_module("FastHasher");
    rb_define_singleton_method(mFastHasher, "compute_fnv1a", rb_fast_checksum, 1);
}
```

### 7.2 Practical Example: Rust Extension via Magnus with RBS Typing
Membangun high-performance JSON Payload Sanitizer yang berjalan multithreaded melepaskan GVL, dipadukan secara ketat dengan RBS dan Steep.

**`Cargo.toml`**
```toml
[package]
name = "payload_sanitizer"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
magnus = { version = "0.6", features = ["rb-sys"] }
rayon = "1.8"
serde_json = "1.0"
```

**`ext/payload_sanitizer/src/lib.rs`**
```rust
use magnus::{define_module, function, prelude::*, Error, Ruby};
use rayon::prelude::*;

fn sanitize_string(input: String) -> String {
    // Operasi CPU intensif: Strip karakter berbahaya & masking
    input
        .chars()
        .filter(|c| !c.is_control())
        .collect::<String>()
}

fn parallel_sanitize(rb: &Ruby, payloads: Vec<String>) -> Result<Vec<String>, Error> {
    // Lepaskan GVL secara implisit via magnus thread batch handling
    rb.thread_yield_splat(move || {
        payloads
            .into_par_iter()
            .map(sanitize_string)
            .collect::<Vec<String>>()
    })
}

#[magnus::init]
fn init(rb: &Ruby) -> Result<(), Error> {
    let module = define_module("PayloadSanitizer")?;
    module.define_singleton_method("sanitize_batch", function!(parallel_sanitize, 1))?;
    Ok(())
}
```

**`sig/payload_sanitizer.rbs`**
```rbs
module PayloadSanitizer
  VERSION: String
  def self.sanitize_batch: (Array[String] payloads) -> Array[String]
end
```

**`Steepfile`**
```ruby
D = Steep::DiagnosticDirs

target :lib do
  signature "sig"
  check "lib"

  configure_code_diagnostics(D::Ruby.strict)
end
```

---

## 8. Real World Case Study: High-Throughput Token Invalidation Engine

### 8.1 Arsitektur Masalah
Perusahaan FinTech memproses 40.000 request/detik. Setiap request membawa JWT terenkripsi yang harus divalidasi keamanannya terhadap revocation blacklists (menggunakan BitSet terkompresi berukuran 512MB). 
- **Implementasi Murni Ruby:** GC overhead melonjak drastis saat mengurai byte streams; waktu pemrosesan mencapai 8.2ms per transaksi; GVL terkunci penuh di multi-threaded Puma workers.
- **Kebutuhan:** Komputasi bitwise lookup < 0.2ms, GC Compaction safe, zero memory leak, and static type safety verification di continuous deployment.

### 8.2 Solusi Arsitektural (C TypedData + RBS)
Ekstensi C menggunakan `TypedData_Wrap_Struct` dengan zero-allocation internal state, melepas GVL saat decoding bitmask array, dan ditutup dengan interface Ruby yang divalidasi Steep.

**`ext/token_engine/token_engine.c`**
```c
#include <ruby.h>
#include <ruby/thread.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *bitset;
    size_t size_in_bytes;
} InvalidationState;

static void invalidation_state_free(void *ptr) {
    InvalidationState *state = (InvalidationState *)ptr;
    if (state) {
        if (state->bitset) free(state->bitset);
        xfree(state);
    }
}

static size_t invalidation_state_memsize(const void *ptr) {
    const InvalidationState *state = (const InvalidationState *)ptr;
    return sizeof(InvalidationState) + (state ? state->size_in_bytes : 0);
}

static const rb_data_type_t invalidation_state_type = {
    .wrap_struct_name = "TokenEngine::Bitmap",
    .function = {
        .dmark = NULL, // Tidak menyimpan objek VALUE Ruby
        .dfree = invalidation_state_free,
        .dsize = invalidation_state_memsize,
    },
    .flags = RUBY_TYPED_FREE_IMMEDIATELY | RUBY_TYPED_WB_PROTECTED,
};

static VALUE engine_alloc(VALUE klass) {
    InvalidationState *state = ALLOC(InvalidationState);
    state->bitset = NULL;
    state->size_in_bytes = 0;
    return TypedData_Wrap_Struct(klass, &invalidation_state_type, state);
}

static VALUE engine_init(VALUE self, VALUE rb_capacity) {
    size_t cap = (size_t)NUM2ULL(rb_capacity);
    InvalidationState *state;
    TypedData_Get_Struct(self, InvalidationState, &invalidation_state_type, state);

    state->size_in_bytes = (cap / 8) + 1;
    state->bitset = (uint8_t *)calloc(state->size_in_bytes, sizeof(uint8_t));
    if (!state->bitset) {
        rb_memerror(); // Memicu NoMemoryError Ruby
    }
    return self;
}

struct lookup_args {
    InvalidationState *state;
    uint64_t token_id;
    int result;
};

static void *raw_is_revoked(void *ptr) {
    struct lookup_args *args = (struct lookup_args *)ptr;
    uint64_t byte_idx = args->token_id / 8;
    uint8_t bit_idx = args->token_id % 8;

    if (byte_idx >= args->state->size_in_bytes) {
        args->result = 0;
        return NULL;
    }

    args->result = (args->state->bitset[byte_idx] & (1 << bit_idx)) != 0;
    return NULL;
}

static VALUE engine_is_revoked(VALUE self, VALUE rb_token_id) {
    InvalidationState *state;
    TypedData_Get_Struct(self, InvalidationState, &invalidation_state_type, state);

    struct lookup_args args;
    args.state = state;
    args.token_id = NUM2ULL(rb_token_id);
    args.result = 0;

    // Komputasi aman tanpa GVL
    rb_thread_call_without_gvl(raw_is_revoked, &args, RUBY_UBF_PROCESS, NULL);

    return args.result ? Qtrue : Qfalse;
}

void Init_token_engine(void) {
    VALUE mTokenEngine = rb_define_module("TokenEngine");
    VALUE cBitmap = rb_define_class_under(mTokenEngine, "Bitmap", rb_cObject);
    
    rb_define_alloc_func(cBitmap, engine_alloc);
    rb_define_method(cBitmap, "initialize", engine_init, 1);
    rb_define_method(cBitmap, "revoked?", engine_is_revoked, 1);
}
```

### 8.3 RBS Interface & Static Verification
**`sig/token_engine.rbs`**
```rbs
module TokenEngine
  class Bitmap
    def initialize: (Integer capacity) -> void
    def revoked?: (Integer token_id) -> bool
  end
end
```

---

## 9. Trade-offs

| Dimensi | C Extension (`ruby.h`) | Rust Extension (`magnus`) | Pure Ruby |
| :--- | :--- | :--- | :--- |
| **P99 Latency** | **Optimal (< 0.1ms)**: Zero abstraction layer. | **Optimal (< 0.12ms)**: Mendekati C murni. | **Variabel (1ms - 15ms)**: Terkena dampak jeda GC. |
| **Throughput & Skalabilitas** | Maksimal: Skala multithreading penuh via GVL bypass. | Maksimal: Ekosistem paralel Rayon yang aman tanpa data races. | Terbatas oleh beban Single Core per proses (karena GVL). |
| **Crash Blast Radius** | **Bencana (Process Fatal)**: Segfault mematikan seluruh instance Puma. | **Terisolasi**: Panic dapat ditangkap menjadi `Result::Err` Ruby exception. | **Terkendali**: Exception tertangkap standard error handler. |
| **CI/CD Build Time** | Cepat (Detik via GCC). | Lambat (Menit karena optimasi borrow checker & LLVM). | Instan (Tanpa tahap kompilasi). |
| **Development Cost** | Sangat Tinggi: Alokasi manual, audit pointer. | Menengah: Kurva belajar Rust tinggi tapi tooling sangat solid. | Sangat Rendah: Kecepatan iterasi tim Ruby standar. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Memory Leak Melalui `rb_raise` dan `malloc`
*Kesalahan:* Memanggil fungsi Ruby C-API yang dapat melempar exception (seperti `rb_raise`, `Check_Type`) setelah menggunakan C standard `malloc`.
```c
// FATAL CODE:
void leak_memory() {
    char *buf = malloc(1024 * 1024); // Alokasi di native heap
    rb_check_type(some_param, T_FIXNUM); // Jika ini GAGAL, Ruby melakukan longjmp()!
    // malloc TIDAK AKAN PERNAH DIBEBASKAN. Memory leak seketika.
    free(buf);
}
```
*Solusi:* Gunakan alokator internal Ruby `ruby_xmalloc()` / `ALLOC()` yang terdaftar pada Garbage Collector, atau gunakan pemanggilan yang diproteksi `rb_protect()` / `rb_ensure()`.

### 10.2 Menyimpan Raw `VALUE` di Native Pointer tanpa `dmark`
*Kesalahan:* Menyimpan array atau hash Ruby di dalam C struct tanpa mendaftarkannya pada callback `dmark`.
*Gejala:* Objek hilang secara misterius saat traffic tinggi, menghasilkan nilai acak atau fatal `[BUG] Segmentation fault at 0x...`.
*Solusi:* Wajib panggil `rb_gc_mark_movable(ptr->ruby_value)` di fungsi callback `dmark`.

### 10.3 Steep / RBS Type Mismatches pada Untyped C-Extensions
*Kesalahan:* Mengabaikan definisi RBS untuk methods yang diexport dari C extensions. Steep tidak bisa membaca file C/Rust, sehingga membiarkan objek menjadi `untyped`.
*Solusi:* Jalankan `steep check` di CI/CD dengan mode `--strict`. Jika extension method belum memiliki type mapping di RBS, build pipeline wajib ditolak (*fail-fast*).

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan `TypedData_Wrap_Struct` eksklusif:** Hindari `Data_Wrap_Struct` yang sudah usang (*deprecated*).
- [ ] **Audit Alokasi GC:** Laporkan setiap memori non-Ruby di callback `dsize` agar GC dapat memicu major GC secara adaptif.
- [ ] **Lepaskan GVL pada Operasi I/O atau Komputasi > 1ms:** Pakai `rb_thread_call_without_gvl()` dan pastikan blok tersebut bebas dari pemanggilan API Ruby.
- [ ] **Gunakan `rb-sys` dan `magnus` untuk native baru:** Prioritaskan Rust untuk mengeliminasi kerentanan keamanan memori secara matematis.
- [ ] **Distribusikan Precompiled Binaries:** Gunakan `rake-compiler-dock` untuk menyediakan pre-built gem artifacts untuk `x86_64-linux-gnu`, `aarch64-linux-gnu`, `arm64-darwin`, sehingga server produksi tidak memerlukan Clang/Rust saat deploy.
- [ ] **Strict Typing Compliance:** Setiap method native wajib memiliki padanan RBS yang lolos validasi statis `steep check`.

---

## 12. Hands-on Practice: Membangun Enterprise-Grade High-Performance Native Gem

Langkah-langkah instruksional langsung untuk diimplementasikan ke folder `hands-on/m02/`.

### Langkah 1: Inisialisasi Struktur Gem
```bash
mkdir -p hands-on/m02/enterprise_crypto
cd hands-on/m02/enterprise_crypto
mkdir -p ext/enterprise_crypto sig lib/enterprise_crypto
```

### Langkah 2: Buat Gemspec Terstruktur
**`enterprise_crypto.gemspec`**
```ruby
Gem::Specification.new do |spec|
  spec.name          = "enterprise_crypto"
  spec.version       = "0.1.0"
  spec.authors       = ["Enterprise Team"]
  spec.summary       = "High-throughput native cryptographic acceleration gem"
  spec.files         = Dir["lib/**/*.rb", "ext/**/*.{c,h,rb}", "sig/**/*.rbs"]
  spec.extensions    = ["ext/enterprise_crypto/extconf.rb"]
  spec.require_paths = ["lib"]

  spec.add_development_dependency "rake", "~> 13.0"
  spec.add_development_dependency "rake-compiler", "~> 1.2"
  spec.add_development_dependency "rspec", "~> 3.12"
  spec.add_development_dependency "steep", "~> 1.6"
  spec.add_development_dependency "rbs", "~> 3.4"
end
```

### Langkah 3: Konfigurasi Extconf
**`ext/enterprise_crypto/extconf.rb`**
```ruby
require "mkmf"

abort "Missing pthreads" unless have_header("pthread.h")
$CFLAGS << " -O3 -Wall -Wextra -std=c11"
create_makefile("enterprise_crypto/enterprise_crypto")
```

### Langkah 4: Tulis C Native Extension dengan Safe TypedData
**`ext/enterprise_crypto/enterprise_crypto.c`**
```c
#include <ruby.h>
#include <ruby/thread.h>
#include <stdint.h>

typedef struct {
    uint8_t xor_key;
} CipherContext;

static void cipher_free(void *ptr) {
    xfree(ptr);
}

static size_t cipher_memsize(const void *ptr) {
    return sizeof(CipherContext);
}

static const rb_data_type_t cipher_data_type = {
    .wrap_struct_name = "EnterpriseCrypto::Cipher",
    .function = {
        .dmark = NULL,
        .dfree = cipher_free,
        .dsize = cipher_memsize,
    },
    .flags = RUBY_TYPED_FREE_IMMEDIATELY | RUBY_TYPED_WB_PROTECTED,
};

static VALUE cipher_alloc(VALUE klass) {
    CipherContext *ctx = ALLOC(CipherContext);
    ctx->xor_key = 0xAA;
    return TypedData_Wrap_Struct(klass, &cipher_data_type, ctx);
}

static VALUE cipher_init(VALUE self, VALUE rb_key) {
    Check_Type(rb_key, T_FIXNUM);
    CipherContext *ctx;
    TypedData_Get_Struct(self, CipherContext, &cipher_data_type, ctx);
    ctx->xor_key = (uint8_t)NUM2INT(rb_key);
    return self;
}

struct cipher_transform_args {
    const char *src;
    char *dst;
    long len;
    uint8_t key;
};

static void *cipher_transform_raw(void *data) {
    struct cipher_transform_args *args = (struct cipher_transform_args *)data;
    for (long i = 0; i < args->len; i++) {
        args->dst[i] = args->src[i] ^ args->key;
    }
    return NULL;
}

static VALUE cipher_transform(VALUE self, VALUE rb_str) {
    Check_Type(rb_str, T_STRING);
    CipherContext *ctx;
    TypedData_Get_Struct(self, CipherContext, &cipher_data_type, ctx);

    long len = RSTRING_LEN(rb_str);
    const char *src = RSTRING_PTR(rb_str);

    // Alokasi String penampung hasil di Ruby Heap
    VALUE rb_out = rb_str_new(NULL, len);
    char *dst = RSTRING_PTR(rb_out);

    struct cipher_transform_args args = {
        .src = src,
        .dst = dst,
        .len = len,
        .key = ctx->xor_key
    };

    // Bebaskan GVL selama proses transformasi
    rb_thread_call_without_gvl(cipher_transform_raw, &args, RUBY_UBF_PROCESS, NULL);

    return rb_out;
}

void Init_enterprise_crypto(void) {
    VALUE mEnterprise = rb_define_module("EnterpriseCrypto");
    VALUE cCipher = rb_define_class_under(mEnterprise, "Cipher", rb_cObject);

    rb_define_alloc_func(cCipher, cipher_alloc);
    rb_define_method(cCipher, "initialize", cipher_init, 1);
    rb_define_method(cCipher, "transform", cipher_transform, 1);
}
```

### Langkah 5: Wrapper Ruby dan Signature RBS
**`lib/enterprise_crypto.rb`**
```ruby
# frozen_string_literal: true

require "enterprise_crypto/enterprise_crypto"

module EnterpriseCrypto
  class Cipher
    # Pure Ruby fallback atau method decorator tingkat tinggi bisa diletakkan di sini
  end
end
```

**`sig/enterprise_crypto.rbs`**
```rbs
module EnterpriseCrypto
  class Cipher
    def initialize: (Integer key) -> void
    def transform: (String data) -> String
  end
end
```

### Langkah 6: Kompilasi dan Type Check
```bash
bundle exec rake compile
bundle exec steep check
```

---

## 13. Exercise

### Level Easy
Ubah method `transform` pada `EnterpriseCrypto::Cipher` di hands-on di atas untuk menambahkan method `key` yang mengembalikan nilai numeric `xor_key` yang sedang aktif ke layer Ruby. Lengkapi dengan RBS definition yang sesuai.

### Level Medium
Tambahkan custom callback `dmark` dan `dcompact` pada sebuah C struct yang menyimpan referensi ke Ruby `VALUE` array log history (`VALUE rb_history`). Pastikan objek aman dari relokasi GC Compacting via `rb_gc_location()`.

### Level Hard
Bangun Native Rust extension (`magnus`) bernama `FastJsonValidator` yang menerima Ruby Array of Strings (berisi ribuan JSON payload). Parsing dan validasi syntax JSON dilakukan secara paralel memanfaatkan `rayon` dan `serde_json` dengan melepaskan GVL. Return array of booleans `[true, false, ...]`. Tulis validasi Steep RBS secara komprehensif tanpa boleh menghasilkan tipe `untyped`.

---

## 14. Challenge: Zero-Copy Network Ring-Buffer Engine
Rancang sistem streaming log processing berkinerja ekstrem di Ruby.

### Spesifikasi Skenario Kasus:
1. **Engine Core:** Bangun extension native (C atau Rust) yang mengalokasikan **Circular Ring-Buffer** statis di luar heap Ruby sebesar 64MB menggunakan `mmap`.
2. **Ingress (GVL Free):** Buat worker thread native mandiri di level OS (menggunakan `pthread` atau Rust native thread) yang mendengarkan UDP Syslog traffic pada port 5140 tanpa memblokir thread YARV Ruby.
3. **Ruby Access (Zero-Copy):** Ruby consumer thread mengambil frame data dari Ring-Buffer menggunakan `TypedData`. Data string yang dibaca ke layer Ruby sebisa mungkin tidak menduplikasi memori heap melalui pemanfaatan zero-copy string primitives (`rb_str_new_frozen` atau shared strings).
4. **Resiliency:** Tangani mitigasi *buffer overflow* saat Ruby consumer lambat memproses data tanpa menyebabkan memory leak atau core dump.
5. **Type Assurance:** Lapisi dengan strict type signatures (`.rbs`) dan arsitektur Gem yang dapat didistribusikan via matrix cross-compilation `rake-compiler-dock`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa tipe data C dari semua representasi objek pada arsitektur internal CRuby?**
   - A. `VALUE`
   - B. `RObject*`
   - C. `VALUE*`
   - D. `ruby_obj_t`
2. **Flag pointer apa yang menentukan bahwa `VALUE` adalah sebuah immediate Integer (Fixnum) pada 64-bit platform?**
   - A. Bit paling belakang bernilai `1`
   - B. Dua bit paling belakang bernilai `00`
   - C. Bit paling belakang bernilai `0`
   - D. Bit ke-63 bernilai `1`
3. **Struktur data modern apa yang diwajibkan untuk membungkus C Struct di Ruby 3.x agar aman terhadap GC Compaction?**
   - A. `Data_Wrap_Struct`
   - B. `Data_Make_Struct`
   - C. `TypedData_Wrap_Struct`
   - D. `rb_struct_alloc`
4. **Perintah CLI apa yang digunakan untuk memverifikasi kesesuaian type signature RBS terhadap kode Ruby?**
   - A. `rbs compile`
   - B. `steep check`
   - C. `bundle exec typeprof --verify`
   - D. `rake typecheck`
5. **Mengapa pemanggilan `rb_funcall` di dalam blok `rb_thread_call_without_gvl` dilarang keras?**
   - A. Karena lambat
   - B. Karena menyebabkan syntax error saat kompilasi C
   - C. Karena mengakses state Ruby VM tanpa proteksi thread safety GVL, berisiko memory corruption / SEGV
   - D. Karena YARV bytecode tidak mendukung C dynamic invocation

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Kapan fungsi callback `dmark` pada `rb_data_type_t` mutlak harus didefinisikan?**
   - A. Setiap kali C struct dialokasikan menggunakan `malloc`
   - B. Jika C struct menyimpan referensi ke tipe `VALUE` (Ruby Object)
   - C. Jika ekstensi dijalankan pada sistem operasi 32-bit
   - D. Hanya jika class diturunkan dari `ActiveSupport`
7. **Apa perbedaan mendasar antara `ruby_xmalloc` dengan C standard library `malloc`?**
   - A. `ruby_xmalloc` tidak pernah me-return pointer NULL melainkan langsung mentrigger Ruby GC jika kekurangan memori
   - B. `ruby_xmalloc` bekerja 2x lebih cepat karena menggunakan SIMD
   - C. `malloc` otomatis membersihkan memori saat program Ruby crash
   - D. `ruby_xmalloc` mengalokasikan data di level cache L1 CPU
8. **Framework cross-compilation standar yang menggunakan pre-built Docker containers untuk membangun C extensions lintas OS adalah:**
   - A. `cargo-cross`
   - B. `rake-compiler-dock`
   - C. `dock-gem-builder`
   - D. `ruby-build-box`
9. **Pada Magnus (Rust), bagaimana error atau Rust panic ditransformasikan saat kembali ke Ruby layer?**
   - A. Selalu memicu `abort()` pada proses Linux
   - B. Menghasilkan Segmentation Fault
   - C. Ditransformasikan menjadi `Result<T, magnus::Error>` yang diterjemahkan menjadi Ruby Exception standar
   - D. Memerlukan wrapper unsafe C-pointer secara eksplisit
10. **Apa kegunaan flag `RUBY_TYPED_WB_PROTECTED` pada deklarasi `rb_data_type_t`?**
    - A. Memproteksi hard disk dari Write-Buffering
    - B. Mengindikasikan bahwa data structure mendukung Write Barrier untuk Generational GC
    - C. Mencegah modifikasi data struct oleh thread OS lain
    - D. Menghindari race condition secara hardware

### Bagian 3: Skenario Kasus Produksi (3 Skenario)
11. **Skenario:** Aplikasi Anda menggunakan C extension untuk merotasi gambar. Di environment produksi, proses Puma pekerja mendadak mati seketika dengan pesan `[BUG] Segmentation fault at 0x0000000000000008` secara intermiten setiap 4-6 jam di bawah beban load tinggi. Core dump menunjukkan crash terjadi di fungsi `gc_marks_rest()`. Apa akar masalah yang paling mungkin dan bagaimana cara membuktikannya?
12. **Skenario:** Tim backend menulis C native extension yang membaca data besar dari socket menggunakan syscall blocking `recv()`. Meskipun instance dijalankan dengan 16 threads Puma, throughput HTTP response aplikasi secara total anjlok menjadi sekuensial (hanya memproses 1 request dalam 1 waktu) saat network latency lambat. Di mana letak kesalahannya?
13. **Skenario:** Perusahaan mewajibkan seluruh core library menggunakan RBS typing. Anda memiliki Rust native gem via `magnus`. Tim QA mengeluh bahwa Type Check `steep check` lolos 100%, tetapi di tahap runtime kerap terjadi `TypeError (no implicit conversion of nil into String)`. Bagaimana ini bisa terjadi dan apa mitigasi arsitekturnya?

---

### Kunci Jawaban Evaluasi

#### Bagian 1 & 2
1. **A** - `VALUE` adalah representasi type pointer/immediate CRuby.
2. **A** - Bit terkecil `1` menandai Fixnum (Pointer Tagging).
3. **C** - `TypedData_Wrap_Struct` wajib digunakan untuk GC safety modern.
4. **B** - `steep check` memvalidasi signature RBS terhadap konteks implementasi.
5. **C** - Modifikasi state VM tanpa GVL merusak integritas heap memory YARV.
6. **B** - Wajib menandai (*mark*) seluruh objek `VALUE` internal agar GC tidak membebaskannya secara prematur.
7. **A** - `ruby_xmalloc` terintegrasi dengan siklus deteksi GC CRuby.
8. **B** - `rake-compiler-dock` adalah standar de-facto isolasi kompilasi binary.
9. **C** - Magnus secara elegan memetakan tipe Rust `Result` menjadi representasi *Ruby Exception*.
10. **B** - Write Barrier Protection memungkinkan efisiensi tinggi pada Generational Garbage Collector.

#### Bagian 3 (Skenario Kasus Produksi)
11. **Akar Masalah:** Kemungkinan besar terdapat `VALUE` pointer Ruby (misalnya String buffer dari data gambar) yang disimpan di dalam context C struct tanpa didaftarkan di fungsi `dmark` dari `TypedData`, ATAU ekstensi native tidak mengimplementasikan fungsi `dcompact` sementara GC Compaction aktif di Ruby 3.x. Saat major compaction berjalan, GC memindahkan objek Ruby ke alamat memori baru, meninggalkan pointer lama mengarah ke memori sampah/mati (`0x00000008`). **Cara Pembuktian:** Jalankan test suite dengan mematikan GC Compaction (`GC.auto_compact = false`) vs mengaktifkannya secara agresif (`GC.verify_compaction_references(double_heap: true)`); pasang tool Valgrind atau Clang AddressSanitizer (ASan) pada compilation flags.
12. **Akar Masalah:** Syscall `recv()` dijalankan tanpa melepaskan Global VM Lock (GVL). Meskipun menggunakan 16 thread OS di Puma, thread yang tertahan di `recv()` native masih memegang GVL, memblokir eksekusi 15 Ruby thread lainnya. **Solusi:** Bungkus panggilan `recv()` di dalam `rb_thread_call_without_gvl()` dan sediakan *unblocking function* (UBF) agar proses I/O dapat diinterupsi oleh runtime jika request di-cancel.
13. **Akar Masalah:** Terjadi divergensi antara interface signature RBS dengan tipe input di layer Rust. Pada layer Rust Magnus, method parameter mungkin ditandai sebagai opsional atau fungsi C-API mengizinkan nilai `nil` (`Qnil`), sementara signature di RBS dideklarasikan sebagai non-nullable (`String` alih-alih `String?`). Karena method diimplementasikan di native code, Steep tidak dapat menganalisis ke dalam binary native dan mengasumsikan signature RBS sebagai kebenaran mutlak. **Mitigasi:** Tambahkan unit test validasi kontrak runtime (`rbs/test` runner) untuk memverifikasi kesesuaian type signature dengan pemanggilan aktual, serta perketat validasi argumen di layer Rust dengan menolak `Value::is_nil()` secara tegas melempar `magnus::Error::new(magnus::exception::type_error())`.

---

## 16. Summary

1. **CRuby Internal & Memory Safety:** Fondasi native extension bergantung pada pemahaman `VALUE` tagging dan lifecycle Ruby Garbage Collector. Modern gem development mewajibkan penggunaan `TypedData_Wrap_Struct` dengan lifecycle hooks (`dmark`, `dfree`, `dsize`, `dcompact`) guna memastikan kompatibilitas penuh dengan GC Compaction.
2. **GVL Control:** Keuntungan performa terbesar dari C/Rust native extension berasal dari pelepasan Global VM Lock melalui `rb_thread_call_without_gvl()`. Hal ini memungkinkan paralelisasi thread komputasi atau I/O intensif tanpa memblokir siklus kerja Ruby VM. Kode yang berjalan di luar proteksi GVL dilarang menyentuh Ruby heap secara langsung.
3. **Rust Renaissance (`magnus` & `rb-sys`):** Menggunakan Rust sebagai ganti C murni memitigasi sebagian besar risiko keamanan memori klasik (*buffer overflow, use-after-free*) sekaligus menyajikan performa bare-metal.
4. **Static Typing Cohesion (RBS & Steep):** Performa tinggi di level native harus diimbangi oleh reliabilitas di layer Ruby. Integrasi RBS dan validasi Steep memastikan interface native yang dinamis dapat diaudit secara statis saat CI/CD, menutup celah terjadinya runtime crash pada aplikasi enterprise berskala besar.