# BAB 09: Quiz, Challenge, & Knowledge Check
**Pengujian Komprehensif, Profiling, & Optimasi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik dan Arsitektur Kompilasi Pengujian Rust
Bandingkan secara arsitektural eksekusi pengujian unit (*Unit Tests*) yang berada di dalam modul internal (`#[cfg(test)] mod tests { ... }`) dengan pengujian integrasi (*Integration Tests*) yang berada di direktori root `tests/`. Jelaskan perbedaannya dari segi visibilitas enkapsulasi (`pub(crate)` vs `pub`), model kompilasi crate (*compilation unit boundary*), dan dampaknya terhadap waktu kompilasi (*incremental compilation & linking overhead*).

### Soal 1.2: Mekanisme Pencegahan Dead Code Elimination pada Benchmarking
Ketika melakukan micro-benchmarking algoritma berkinerja tinggi menggunakan framework seperti `criterion`, kompilator LLVM sering kali mengoptimasi loop benchmark secara agresif melalui *dead code elimination* (DCE) atau *constant folding*, sehingga menghasilkan runtime fiktif 0.00 ns. Jelaskan bagaimana fungsi `std::hint::black_box` bekerja di level assembly/compiler barrier untuk mencegah optimasi tersebut tanpa menambahkan overhead instruksi runtime yang signifikan.

### Soal 1.3: Filosofi Property-Based Testing vs Fuzzing Berbasis Cakupan
Jelaskan perbedaan mendasar antara *Property-Based Testing* (menggunakan crate seperti `proptest`) dan *Coverage-Guided Fuzzing* (menggunakan `cargo-fuzz` / `libFuzzer`). Ditinjau dari cara input state space dieksplorasi, bagaimana instrumentasi biner (seperti LLVM SanitizerCoverage) membedakan efektivitas fuzzer dibanding generator pseudorandom terdistribusi saat memvalidasi parser biner yang kompleks?

### Soal 1.4: Konfigurasi Profil Rilis dan Link-Time Optimization (LTO)
Dalam berkas `Cargo.toml`, terdapat opsi profil kompilasi seperti `opt-level = 3`, `lto = "fat"`, `codegen-units = 1`, dan `panic = "abort"`. Uraikan secara teknis bagaimana kombinasi keempat parameter ini mengubah representasi intermediate LLVM (LLVM IR), proses penggabungan modul biner di level linker, serta pengaruhnya terhadap inlining *cross-crate* dan degradasi waktu kompilasi.

### Soal 1.5: Taksonomi Profiling: Sampling vs Instrumentation
Uraikan perbedaan fundamental antara *Sampling Profiler* (seperti Linux `perf` atau `samply`) dengan *Instrumentation/Allocation Profiler* (seperti Valgrind `Callgrind` atau `dhat`). Bagaimana fenomena *observer effect* atau *profiling overhead* dari masing-masing metode dapat mendistorsi representasi bottleneck, terutama pada sistem yang memiliki karakteristik *CPU-bound* berfrekuensi tinggi dibanding sistem *allocation-heavy*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Deterministik Runtime Testing pada Ekosistem Asynchronous
Pada pengujian kode asynchronous menggunakan `#[tokio::test]`, kegagalan *concurrency* seperti race condition transien atau starvation sering tidak terdeteksi pada *multi-threaded runtime*. Jelaskan bagaimana fitur *mocking time* (`tokio::time::pause()`) memanipulasi task scheduler secara internal. Bagaimana arsitek dapat menguji kebocoran task (*task leak*) atau mendeteksi *task starvation* yang dipicu oleh eksekusi operasi CPU-bound di dalam thread pool asynchronous Tokio?

### Soal 2.2: Intervensi Dynamic Memory Allocator pada Multi-Threaded Contention
Secara default, Rust pada Linux menggunakan allocator bawaan `glibc` (`ptmalloc`). Pada aplikasi HTTP server multi-threaded dengan throughput tinggi, terjadi bottleneck signifikan pada lock contention alokasi memori heap. Jelaskan mengapa mengganti allocator global menjadi `jemalloc` (`jemallocator`) atau `mimalloc` dapat menurunkan latensi p99 secara drastis. Analisis mekanisme *thread-local caching* (tcache) dan strategi penanganan fragmentasi memori (*radix tree arena mapping*) pada arsitektur allocator tersebut.

### Soal 2.3: Hambatan Auto-Vectorization (SIMD) dan Eliminasi Bounds Checking
Perhatikan fragmen iterasi komputasi numerik berikut:
```rust
pub fn compute_sum(a: &[f32], b: &[f32], out: &mut [f32]) {
    for i in 0..a.len() {
        out[i] = a[i] * 2.0 + b[i];
    }
}
```
Mengapa LLVM sering kali gagal melakukan *auto-vectorization* (AVX2/AVX-512) secara optimal pada kode di atas jika parameter `out` berpotensi tumpang tindih (*pointer aliasing*) dengan `a` atau `b`? Tunjukkan bagaimana rekursi *bounds checking* pada setiap iterasi dapat dieliminasi secara deterministik menggunakan *idiomatic chunking/iterators* atau instruksi assert ukuran slice di awal fungsi.

### Soal 2.4: Diagnostik Undefined Behavior dan Memory Leak Menggunakan Sanitizers
Rust menjamin ketiadaan data race dan memory safety pada safe code, namun interoperabilitas FFI atau implementasi struktur data berbasis `unsafe` (misalnya raw pointer manipulation) rentan terhadap *undefined behavior* dan *memory leak*. Jelaskan bagaimana cara mengonfigurasi dan menjalankan *AddressSanitizer* (ASan), *LeakSanitizer* (LSan), dan *Miri*. Apa perbedaan ranah kerja antara interpretasi tingkat AST/MIR oleh Miri dibandingkan instrumentasi biner level machine code oleh ASan/LSan?

### Soal 2.5: CPU Cache Misses, False Sharing, dan Intervensi Layout Memori
Ketika beberapa thread mengeksekusi operasi penulisan (*atomic write*) secara independen pada elemen-elemen array struct yang berdekatan:
```rust
struct WorkerStat {
    processed: std::sync::atomic::AtomicU64,
}
```
Terjadi degradasi performa throughput drastis akibat fenomena *Cache Line Bouncing / False Sharing*. Jelaskan bagaimana protokol koherensi cache CPU (seperti MESI/MOESI) memicu invalidasi cache level L1/L2 dalam skenario ini. Bagaimana cara menyelesaikan masalah ini di Rust menggunakan atribut `#[repr(align(64))]` atau tipe wrapper seperti `crossbeam::utils::CachePadded`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Degradation pada Pipeline Ingesti Telemetri (CPU & Allocation Bottleneck)
Sebuah microservice analitik memproses stream 150.000 events/detik JSON payload berukuran variatif (1 KB - 8 KB). Metrik APM menunjukkan latensi p99 membengkak dari 5 ms menjadi 180 ms ketika traffic melonjak 20%, disertai lonjakan utilisasi CPU hingga 100% pada semua core. Analisis *Flamegraph* awal menunjukkan bahwa 65% CPU time dihabiskan pada:
- `core::str::validations`
- `alloc::string::String::clone`
- `serde_json::de::from_slice`
- `glibc::free` dan `glibc::malloc`

```
+-----------------------------------------------------------------------+
| Flamegraph Snapshot:                                                  |
| [================== serde_json::from_slice (65%) ===================] |
|   [=== str::validations (25%) ===] [=== alloc/free (30%) ===] [...]   |
+-----------------------------------------------------------------------+
```

**Pertanyaan Diagnostik:**
1. Bagaimana Anda merestrukturisasi model domain serialisasi menggunakan fitur zero-copy deserialization (`&'a str` / `Cow<'a, str>`) untuk memangkas alokasi heap hingga 0 byte pada hot-path parsing?
2. Jika payload JSON mengandung field string yang memerlukan unescaping (misal karakter `\"` atau `\n`), bagaimana strategi alokasi memori hybrid (arena allocator atau *small-string optimization* via crate seperti `smallvec` / `compact_str`) diterapkan agar tetap menghindari dynamic allocation global?
3. Evaluasi kelayakan penggantian backend parser ke `simd-json`. Apa prasyarat arsitektur CPU dan trade-off konsumsi buffer memory (*mutable slice padding requirements*) yang harus dipertimbangkan sebelum mengadopsinya ke lingkungan containerized Kubernetes?

---

### Skenario B: Asynchronous Contention dan Lock Inversion pada High-Scale Order Engine
Sebuah engine *order execution* berbasis `tokio` multi-threaded memproses transaksi finansial. Pada stress test throughput tinggi (50.000 order/detik), p99.9 latensi melonjak menjadi 1,2 detik, dan sistem mengalami pembekuan parsial (*hang*) di mana sejumlah worker thread berhenti memproses event baru.

Struktur state saat ini:
```rust
pub struct MatchingEngine {
    // Shared state diakses oleh puluhan async tasks
    orderbooks: Arc<tokio::sync::Mutex<HashMap<Symbol, OrderBook>>>,
    account_balances: Arc<tokio::sync::RwLock<HashMap<UserId, Balance>>>,
}
```

Alur eksekusi saat ini:
1. Task memvalidasi saldo dengan mengakuisisi `account_balances.write().await`.
2. Di dalam scope guard yang sama, task mengakuisisi `orderbooks.lock().await` untuk menempatkan order.
3. Task lain (pembatalan order) mengakuisisi `orderbooks.lock().await`, lalu memanggil refund yang mengakuisisi `account_balances.write().await`.

**Pertanyaan Diagnostik:**
1. Tunjukkan bagaimana skenario di atas memicu deadlock / lock inversion di lingkungan async, dan mengapa detektor deadlock konvensional thread OS gagal mendeteksi kebuntuan async task Tokio ini.
2. Rancang ulang arsitektur sinkronisasi state tersebut menggunakan strategi *Message Passing Actor Pattern* atau *Sharded/Partitioned State Architecture* (misal: partitioning per-Symbol dan per-UserId shard) sehingga shared mutable state locks dapat dieliminasi secara total.
3. Tuliskan blueprint arsitektur concurrency baru menggunakan lock-free unbounded/bounded primitive (seperti `crossbeam_channel` atau LMAX Disruptor-pattern berbasis ring-buffer via bounded channels) untuk memisahkan thread pool pengeksekusi pencocokan order (single-writer principle) dari network IO tasks.

---

### Skenario C: Footprint Constraints & Latency Bounds pada Edge IoT Gateway
Sebuah biner Rust yang bertindak sebagai gateway protokol industri harus dideploy ke embedded Linux device dengan spesifikasi restriktif:
- RAM Total: 64 MB (RSS alokasi maksimal untuk biner: 16 MB).
- Flash Storage: 16 MB (Ukuran biner maksimal di disk: 4 MB).
- Jaminan latensi pemrosesan frame CAN-bus: < 200 mikrodetik (hard real-time/near real-time, zero page-fault tolerance di hot path).

Saat dikompilasi default menggunakan `cargo build --release`, ukuran biner mencapai 22 MB dan *Resident Set Size* (RSS) memori mencapai 38 MB saat idle, akibat monomorphization masif dari generic traits, runtime unwinding tables, dan inclusion jemalloc.

**Pertanyaan Diagnostik:**
1. Rinci pipeline modifikasi `Cargo.toml` dan build flags (meliputi `codegen-units`, `panic`, `strip`, `opt-level`, dan custom allocator target) yang secara teknis memampukan biner menyusut hingga di bawah 4 MB.
2. Analisis bagaimana trade-off antara *Static Dispatch* (Monomorphization via Generics) dan *Dynamic Dispatch* (`dyn Trait` fat pointers) mempengaruhi ukuran biner (code bloat di instruction cache) vs latensi eksekusi (indirect function call overhead / vtable dispatch). Pada komponen mana dynamic dispatch harus dipilih dalam kasus ini?
3. Rancang strategi alokasi memori runtime untuk menjamin zero-allocation di hot-path processing. Bagaimana Anda memanfaatkan `heapless` data structures, memory pre-allocation, dan deteksi otomatis runtime allocation (misal: menggunakan hook `std::alloc::set_alloc_error_hook` atau override global allocator wrapper) untuk menggagalkan automated test jika terjadi alokasi memori di hot-path?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance, Zero-Copy, Fuzzed Network Protocol Frame Processor

#### Problem Statement
Anda ditugaskan merancang komponen core parser dan routing engine untuk protokol biner internal telemetri IoT bernama **"FastFrame"**. Engine ini harus mampu memvalidasi, mem-parse, dan mengagregasi jutaan frame payload per detik pada server relay tanpa menyebabkan panic, alokasi memori dinamis di hot-path, ataupun kebocoran resource.

#### Struktur Protokol FastFrame
Format biner paket network (Big-Endian):
- **Magic Bytes** (2 bytes): `0xFA 0x7E`
- **Stream ID** (4 bytes): `u32`
- **Timestamp** (8 bytes): `u64` (Epoch nanoseconds)
- **Flags** (1 byte): Bit 0: Is Compressed, Bit 1: Is Encrypted, Bit 2-7: Reserved
- **Payload Length** (2 bytes): `u16` (N bytes)
- **Payload**: N bytes (Zero-copy slice reference)
- **Checksum** (4 bytes): CRC32 (IEEE) dari header + payload

#### Technical Requirements
1. **Zero-Copy Parser Implementation:**
   - Parse slice byte mentah `&'a [u8]` menjadi struct `FastFrame<'a>`.
   - Tidak boleh ada alokasi heap (`String`, `Vec`, `Box`) sama sekali selama proses validasi dan ekstraksi payload.
   - Return custom error enum bertipe komprehensif (`InvalidMagic`, `PayloadLengthMismatch`, `ChecksumError`, `IncompleteBuffer`).
2. **Deterministic Bounds Checking Elimination:**
   - Implementasikan parser dengan struktur parsing yang meminimalkan/mengeliminasi bounds check assembly LLVM pada pembacaan slice (manfaatkan split pattern matching atau fixed-size array conversion via `TryFrom`).
3. **Comprehensive Benchmarking Suite (`criterion`):**
   - Buat benchmark micro-level untuk mengukur:
     - Throughput parsing (Target: $\ge 1.5\text{ GB/detik}$ per core).
     - Latensi decoding per frame (Target: p99 $\le 150\text{ ns}$).
   - Lindungi pipeline benchmark dari Dead Code Elimination via `std::hint::black_box`.
4. **Coverage-Guided Fuzz Target:**
   - Buat harness `fuzz/fuzz_targets/fuzz_fastframe.rs` menggunakan `cargo-fuzz` / `libfuzzer-sys`.
   - Fuzzer harus memvalidasi bahwa input byte acak apapun **tidak akan pernah memicu panics / crash / index out of bounds exception**, melainkan selalu mengembalikan nilai gracefully dalam bentuk `Result<FastFrame, FrameError>`.
5. **Memory Allocation Audit Test:**
   - Buat integration test dengan *Custom Allocator Tracker* yang menghitung jumlah pemanggilan `alloc` dan `dealloc`. Pastikan ketika parsing frame 10.000 kali dalam loop, allocation counter bernilai persis **0**.

#### Constraints
- **Strict Safe Rust:** Hot path decoding tidak boleh menggunakan blok `unsafe` kecuali untuk SIMD intrinsics yang terdokumentasi rapi invariant-nya.
- **Dependency Restrictions:** Hanya diperbolehkan menggunakan crate: `criterion`, `crc32fast`, `proptest`, `cargo-fuzz`, dan komponen internal standard library.
- **Target Metrics Verification:** Seluruh kode harus lolos Clippy pedantic (`#![warn(clippy::all, clippy::pedantic)]`) tanpa error.

#### Expected Output Deliverables
1. Berkas implementasi `src/frame.rs` (Struktur struct, enum error, parsing zero-copy, dan zero bounds-checking implementation).
2. Berkas benchmarking `benches/parser_benchmark.rs` dengan skenario berbagai variasi ukuran payload (32 bytes, 512 bytes, 4 KB).
3. Berkas fuzz target `fuzz/fuzz_targets/fuzz_fastframe.rs`.
4. Laporan analisis singkat: Hasil disassembly assembly LLVM (`cargo asm` atau Godbolt inspection) pada blok parsing loop yang membuktikan hilangnya bounds checking.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan model kompilasi dan visibilitas enkapsulasi antara *Unit Tests* dan *Integration Tests* (`tests/`).
- [ ] Peran `std::hint::black_box` dalam mematikan optimasi compiler (DCE dan constant propagation) saat mikro-benchmarking.
- [ ] Keunggulan dan batas arsitektur antara *Property-Based Testing* (`proptest`) vs *Coverage-Guided Fuzzing* (`cargo-fuzz`/LLVM SanitizerCoverage).
- [ ] Mekanisme kerja compiler flags: `lto = "fat"`, `codegen-units = 1`, `opt-level = 3`, dan `panic = "abort"` terhadap inlining cross-crate dan binary footprint.
- [ ] Dampak perbedaan *Sampling Profiler* (`perf`, `samply`) vs *Instrumentation/Allocation Profiler* (`dhat`, `valgrind`) terhadap latency overhead dan analisis bottleneck.
- [ ] Pengaruh dynamic global allocator (`jemalloc`, `mimalloc`) terhadap thread-local arena allocation, meminimalisasi lock contention di multicore servers.
- [ ] Hubungan antara *Pointer Aliasing*, Slice Bounds Checking, dan kegagalan Auto-Vectorization (SIMD) pada LLVM.
- [ ] Mekanisme terjadinya *False Sharing* pada multicore CPU cache lines (L1/L2) dan pencegahannya via cache padding (`#[repr(align(64))]`).
- [ ] Perbedaan runtime sanitizers (ASan, LSan, TSan) pada level machine code biner vs abstract interpretation oleh Miri pada MIR.

### Saya tidak perlu menghafal:
- [ ] Konfigurasi syntax parameter visualisasi spesifik pada berkas HTML output Criterion.
- [ ] Nilai hex opcode assembly individual untuk instruksi SIMD AVX2/AVX-512 (cukup memahami pola vectorization pada register SIMD).
- [ ] Struktur internal low-level implementasi arena tree Jemalloc secara rinci.
- [ ] Opsi CLI flag internal `llvm-args` yang tidak stabil (*unstable `-Z` flags*) di luar standar profiling resmi.

### Saya harus bisa melakukan:
- [ ] Merancang dan mengeksekusi suite benchmark performa kuantitatif menggunakan `criterion` dengan eliminasi bias optimasi compiler via `black_box`.
- [ ] Mengonfigurasi, menulis harness, dan menjalankan *Coverage-Guided Fuzzing* menggunakan `cargo-fuzz` untuk membongkar edge-case parser biner.
- [ ] Menghasilkan, membaca, dan menganalisis visualisasi CPU/Memory *Flamegraph* menggunakan `perf` / `samply` / `cargo-flamegraph` guna mengidentifikasi hotspot sistem.
- [ ] Melakukan refactoring arsitektur dari *allocating model* menjadi *zero-copy processing* berbasis slice lifetimes (`&'a [u8]` / `Cow<'a, str>`).
- [ ] Mengisolasi alokasi dinamis heap dengan mengimplementasikan allocator tracking test harness untuk memverifikasi jalur kode *zero-allocation*.
- [ ] Melakukan tuning konfigurasi `Cargo.toml` profil release secara spesifik untuk memangkas ukuran biner dan memaksimalkan throughput sesuai batasan platform target.