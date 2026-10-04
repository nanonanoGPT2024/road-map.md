# Kurikulum Enterprise: Rust Systems Engineering
## Bab 09: Pengujian Komprehensif, Profiling, dan Optimasi
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineer/Systems Architect diharapkan mampu:
*   Mendesain strategi verifikasi perangkat lunak deterministik menggunakan kombinasi *Property-Based Testing* (`proptest`) dan *Coverage-Guided Fuzzing* (`cargo-fuzz`/`libfuzzer`).
*   Menguasai metodologi instrumentasi performa tingkat lanjut: menganalisis siklus instruksi CPU, *cache misses* (L1/L2/LLC), dan *branch mispredictions* via Linux `perf`, `dhat`, serta *flamegraph*.
*   Menerapkan *statistical microbenchmarking* dengan `criterion.rs` yang tahan terhadap intervensi CPU throttling, compiler dead-code elimination, dan cache state drift.
*   Menerapkan pipeline optimasi pasca-kompilasi tingkat lanjut: *Profile-Guided Optimization* (PGO), *Link-Time Optimization* (LTO: Thin vs Fat), dan manipulasi codegen LLVM melalui *target-cpu intrinsics*.
*   Mendiagnosis dan mengeliminasi overhead alokasi memori pada hot-path menggunakan *custom global allocators* (`jemalloc`, `mimalloc`) serta zero-cost memory layout optimization.

---

### 2. Prerequisites
*   Pemahaman mendalam tentang Rust Memory Model (Ownership, Borrowing, Lifetimes, Unsafe Rust, dan Invariants).
*   Keahlian praktis dalam struktur data kernel dasar: Virtual Memory, Page Faults, CPU Registers, dan TLB (Translation Lookaside Buffer).
*   Familiaritas dengan *tooling* sistem Linux: `perf`, `objdump`, `readelf`, dan POSIX signal handling.
*   Telah menyelesaikan *Bab 09 - Modul 01: Dasar-Dasar Unit Testing, Mocking, dan Benchmark Naif di Rust*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. LLVM Compilation Pipeline & Profiling Hook-Points
Kompilasi Rust tidak berhenti pada transformasi *Abstract Syntax Tree* (AST) ke *High-Level Intermediate Representation* (HIR) dan *Mid-Level IR* (MIR). Optimasi kritis dieksekusi ketika MIR diubah menjadi *LLVM Intermediate Representation* (LLVM-IR).

```
[Rust Source: .rs] 
       │
       ▼
   [HIR / MIR] ─── (Borrow Check, Type Inference, Monomorphization)
       │
       ▼
   [LLVM-IR] ◄─── Instrumentation Pass (-C profile-generate)
       │
       ├─► Optimization Passes (Inlining, Loop Vectorize, Dead Code Elimination)
       │
       ▼
  [Machine Code] ─── Output Instrumentation (.profraw)
       │
       ▼ (Merge into .profdata via llvm-profdata)
       │
  [Re-compilation] ◄─── PGO Applied (-C profile-use)
```

1.  **Monomorphization Phase**: Generic functions digandakan untuk setiap tipe konkret. Dampaknya: performa runtime meningkat drastis (zero-cost abstraction), namun menghasilkan *code bloat* pada instruksi *instruction cache* (I-Cache).
2.  **Instrumentation Pass**: Saat flag `-C profile-generate` aktif, LLVM menyisipkan probe counter pada setiap *Basic Block* graf kontrol aliran (CFG). Eksekusi binary menghasilkan file `.profraw` yang merekam frekuensi eksekusi cabang (*branch frequency*).
3.  **Profile-Use Optimization**: LLVM memanfaatkan data profil tersebut untuk:
    *   Menata ulang *Basic Blocks*: Blok yang sering dieksekusi diposisikan berdekatan secara linier dalam memori untuk memaksimalkan *instruction prefetcher*.
    *   Inlining selektif: Fungsi yang berada di *hot-path* di-inline secara agresif, sementara *cold-path* (misal: penanganan error) dipindahkan ke segmen memori terpisah (cold section).

#### B. Coverage-Guided Fuzzing Internal Architecture
Fuzzing modern berbasis `libfuzzer` atau `AFL++` tidak melakukan input brute-force secara acak. Rust menggunakan LLVM *SanitizerCoverage*:

```
[Fuzzer Engine] ──(Input Corpus)──► [Target Binary (libfuzzer instrumentation)]
      ▲                                        │
      │                                        ▼
      │                                [Execute Basic Blocks]
      │                                        │
      │                                        ▼
      └──(Update Corpus if new edge hit)── [Coverage Bitmap]
                                           (8-bit counter per edge)
```

Setiap edge transisi antara dua *Basic Block* ($A \to B$) diinstrumentasi dengan operasi atomik ekuivalen:
$$\text{Index} = (\text{Hash}(A) \oplus \text{Hash}(B)) \pmod{\text{CoverageMapSize}}$$
$$\text{CoverageMap}[\text{Index}] += 1$$

Fuzzer engine memantau mutasi bitmap ini. Jika sebuah input acak memicu eksekusi edge yang belum pernah terjamah sebelumnya, input tersebut dimasukkan ke dalam *Corpus* sebagai basis mutasi generasi berikutnya.

#### C. Statistical Rigor pada Microbenchmarking (Criterion.rs)
Criterion memitigasi anomali OS scheduling, memory page allocation randomness, dan CPU frequency scaling melalui:
1.  **Kernel Density Estimation (KDE)**: Menghitung fungsi densitas probabilitas non-parametrik dari sampel waktu eksekusi tanpa mengasumsikan distribusi Gaussian murni.
2.  **Bootstrap Resampling**: Melakukan 100,000 kali resampling acak dengan penggantian (with replacement) untuk menghitung *Confidence Intervals* (biasanya 95%) untuk mean dan median.
3.  **T-Test & Mann-Whitney U Test**: Mendeteksi regresi performa statistik nyata vs noise pengukuran lingkungan virtualisasi/CI.

---

### 4. Why & What

| Dimensi Optimasi | Pendekatan Konvensional | Pendekatan Enterprise Rust |
| :--- | :--- | :--- |
| **Pengujian Input** | Unit test berbasis manual edge-case (*hardcoded boundary*). | *Property-Based Testing* state-space reduction + *Differential Fuzzing*. |
| **Benchmarking** | Pengukuran `std::time::Instant` manual dalam iterasi loop. | *Statistical Rigorous Benchmarking* (Criterion) dengan *CPU Cache warming* & `black_box`. |
| **Alokasi Memori** | Default System Allocator (`glibc ptmalloc`). | `jemalloc` / `mimalloc` dengan tuning arena per-thread & sampling profiling runtime. |
| **Binary Optimization**| `cargo build --release` default (`opt-level = 3`). | PGO + ThinLTO + Native Target CPU Tuning + Assembly Audit via `cargo-asm`. |
| **Observabilitas** | Logging teks struktural di level aplikasi. | Zero-overhead distributed tracing (`tracing-subscriber`), CPU flamegraphs, dan eBPF probes. |

---

### 5. How (Workflow Detail)

#### Pipeline Optimasi Produksi: Siklus Iteratif

```
  1. Microbenchmarking (Base Metric)
                 │
                 ▼
  2. Profiling (Linux perf, Flamegraph, DHAT)
                 │
                 ▼
  3. Identifikasi Hotspot & Memory Churn
                 │
                 ▼
  4. Algorithmic & Zero-Copy Refactoring
                 │
                 ▼
  5. Verification via Property Test & Fuzzing
                 │
                 ▼
  6. Compiler-Level Tuning (PGO, LTO, CPU Target)
                 │
                 ▼
  7. Regression Detection (Criterion CI Gate)
```

1.  **Fase 1: Deterministic Invariant Checking**: Validasi state invariants sistem diuji dengan jutaan kombinasi pseudorandom menggunakan `proptest`.
2.  **Fase 2: Profiling Alokasi dan Siklus**: Identifikasi *cache miss* dan alokasi heap tak perlu menggunakan `cargo-dhat` dan `perf stat`.
3.  **Fase 3: Zero-Copy & Vectorization Refactor**: Konversi slice allocations ke borrowing pattern, implementasikan `#[inline(always)]` selektif, dan izinkan auto-vectorization SIMD.
4.  **Fase 4: Codegen Inspection**: Analisis emisi assembly LLVM via `cargo-asm` untuk memastikan fungsi tidak menghasilkan *unnecessary bounds checking* atau *stack spilling*.
5.  **Fase 5: PGO Pipeline Injection**: Build binary berinstrumen, jalankan production-like synthetic workload, dump profile data, dan kompilasi ulang dengan flag `-C profile-use`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Terowongan Angin Formula 1
Menulis kode Rust seperti merakit mobil balap F1:
*   **Unit Testing** memastikan mur dan baut terpasang kencang (fungsionalitas komponen terisolasi).
*   **Property-Based Testing & Fuzzing** adalah simulasi guncangan ekstrem dan jalanan berlubang tanpa henti untuk menemukan skenario patahnya suspensi yang tidak terbayangkan oleh engineer.
*   **Flamegraph & Profiling** adalah sensor telemetri termal yang memetakan komponen mana yang mengalami *overheating* (CPU hotspots).
*   **PGO (Profile-Guided Optimization)** adalah uji terowongan angin: sayap aerodinamis (instruksi assembly) disesuaikan secara mikroskopis berdasarkan jalur aliran udara nyata saat mobil melaju di sirkuit tertentu, bukan asumsi teoritis.

```
       CPU CACHE HIERARCHY LATENCY GAP
┌──────────────────────────────────────────────┐
│ L1 D-Cache: ~1 ns (Instruksi Hot-path)       │
├──────────────────────────────────────────────┤
│ L2 Cache:   ~3 - 4 ns                        │
├──────────────────────────────────────────────┤
│ L3 Cache:   ~10 - 15 ns                      │
├──────────────────────────────────────────────┤
│ Main Memory (DRAM): ~60 - 80 ns (Cold Miss)  │ ◄─── Cache Miss Penalty
└──────────────────────────────────────────────┘      (Menghancurkan Throughput)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Menghindari Compiler Dead-Code Elimination dengan `std::hint::black_box`

```rust
// benches/naive_vs_rigorous.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn compute_heavy_hash(input: &[u8]) -> u64 {
    let mut state: u64 = 0xcbf29ce484222325;
    for &byte in input {
        state ^= byte as u64;
        state = state.wrapping_mul(0x100000001b3);
    }
    state
}

fn bench_bad(c: &mut Criterion) {
    let payload = vec![0xABu8; 4096];
    // ANTI-PATTERN: Compiler tahu hasil compute_heavy_hash tidak digunakan.
    // Seluruh pemanggilan fungsi ini berisiko dihapus total (Optimized Away)!
    c.bench_function("hash_unoptimized_measurement", |b| {
        b.iter(|| {
            let _ = compute_heavy_hash(&payload);
        })
    });
}

fn bench_good(c: &mut Criterion) {
    let payload = vec![0xABu8; 4096];
    // ENTERPRISE PATTERN: black_box memaksa compiler memperlakukan parameter 
    // dan output seolah-olah terjadi I/O volatile eksternal yang tidak dapat diprediksi.
    c.bench_function("hash_rigorous_measurement", |b| {
        b.iter(|| {
            let result = compute_heavy_hash(black_box(&payload));
            black_box(result);
        })
    });
}

criterion_group!(benches, bench_bad, bench_good);
criterion_main!(benches);
```

#### B. Practical Example: Custom Invariant Testing dengan `proptest` dan Zero-Copy Token Deserializer

```rust
// Cargo.toml dependencies:
// proptest = "1.4"
// byteorder = "1.5"

use std::fmt;

#[derive(Debug, PartialEq, Eq, Clone)]
pub struct WireProtocolFrame {
    pub stream_id: u32,
    pub flag: u8,
    pub payload: Vec<u8>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum DecodeError {
    BufferUnderflow,
    InvalidPayloadLength,
    ReservedFlagViolation,
}

impl fmt::Display for DecodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}", self)
    }
}

impl std::error::Error for DecodeError {}

pub struct FrameCodec;

impl FrameCodec {
    pub const HEADER_SIZE: usize = 9; // 4 bytes stream_id + 1 byte flag + 4 bytes len

    #[inline]
    pub fn encode(frame: &WireProtocolFrame, buf: &mut Vec<u8>) {
        buf.extend_from_slice(&frame.stream_id.to_be_bytes());
        buf.push(frame.flag);
        buf.extend_from_slice(&(frame.payload.len() as u32).to_be_bytes());
        buf.extend_from_slice(&frame.payload);
    }

    #[inline]
    pub fn decode(src: &[u8]) -> Result<WireProtocolFrame, DecodeError> {
        if src.len() < Self::HEADER_SIZE {
            return Err(DecodeError::BufferUnderflow);
        }

        let stream_id = u32::from_be_bytes(src[0..4].try_into().unwrap());
        let flag = src[4];

        // System invariant: Bit ke-7 harus 0 (reserved flag)
        if (flag & 0x80) != 0 {
            return Err(DecodeError::ReservedFlagViolation);
        }

        let payload_len = u32::from_be_bytes(src[5..9].try_into().unwrap()) as usize;

        if src.len() < Self::HEADER_SIZE + payload_len {
            return Err(DecodeError::BufferUnderflow);
        }

        let payload = src[Self::HEADER_SIZE..Self::HEADER_SIZE + payload_len].to_vec();

        Ok(WireProtocolFrame {
            stream_id,
            flag,
            payload,
        })
    }
}

// =========================================================================
// PROPERTY-BASED TESTS MENGUJI STATE-SPACE INVARIANT SECARA KOMPREHENSIF
// =========================================================================
#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Arbitrary generator generator payload frame
    fn arb_valid_frame() -> impl Strategy<Value = WireProtocolFrame> {
        (
            any::<u32>(),
            0x00u8..=0x7Fu8, // Bit 7 selalu 0 untuk valid flag
            prop::collection::vec(any::<u8>(), 0..2048),
        )
            .prop_map(|(stream_id, flag, payload)| WireProtocolFrame {
                stream_id,
                flag,
                payload,
            })
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(5000))]

        #[test]
        fn roundtrip_encode_decode_invariant(frame in arb_valid_frame()) {
            let mut buffer = Vec::with_capacity(FrameCodec::HEADER_SIZE + frame.payload.len());
            FrameCodec::encode(&frame, &mut buffer);

            let decoded = FrameCodec::decode(&buffer).expect("Decoding harus sukses untuk serialisasi valid");
            prop_assert_eq!(frame, decoded);
        }

        #[test]
        fn fuzz_arbitrary_byte_stream_never_panics(data in prop::collection::vec(any::<u8>(), 0..4096)) {
            // Invariant mutlak sistem parsers: Apapun input byte array-nya,
            // decode() TIDAK BOLEH PANIC melainkan harus mengembalikan Result::Err.
            let _ = FrameCodec::decode(&data);
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Domain: Ultra-Low Latency Order Matching Engine Execution Path

```
                    MARKET DATA TICK PACKET
                              │
                              ▼
            ┌──────────────────────────────────┐
            │ Direct Memory Buffer (Zero-Copy) │
            └──────────────────────────────────┘
                              │
                    Raw Pointer Decoding
                              │
                              ▼
                 MATCHING ENGINE CORE (PGO)
            ┌──────────────────────────────────┐
            │ L1 Cache Hot: Dense Order Book   │
            │ Loop Vectorized SIMD Depth Cross │
            └──────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       Engine Execution               Audited Cold-Path
     (Sub-Microsecond)             (OutOfMemory/SysCall)
```

#### Konteks Masalah
Sebuah platform pertukaran aset keuangan teregulasi menghadapi bottleneck tail-latency ($p99.9$) sebesar $4.2\ \mu\text{s}$ per eksekusi limit order. Analisis `perf record -e cache-misses,cycles` mengungkap:
1.  Terjadi alokasi memori berlebih (`malloc` overhead melalui glibc default allocator) di dalam critical matching loop.
2.  LLVM memecah loop pencocokan harga karena gagal melakukan auto-vectorization akibat aliasing pointer dan dynamic dispatching.
3.  Branch mispredictions pada parsial cancel order logika mencapai 14.8%.

#### Solusi Arsitektural & Implementasi Produksi

1.  **Global Allocator Swap**: Mengganti memory allocator ke `jemalloc` dengan *background threads* diaktifkan guna meredam stop-the-world latency spikes akibat arena purging.
2.  **Memory Layout Packing**: Memanfaatkan memory layout `#[repr(C, packed)]` atau `#[repr(align(64))]` untuk menyelaraskan struktur data order ke CPU Cache Line (64 bytes), mencegah terjadinya *False Sharing* antar thread.
3.  **Profile-Guided Optimization (PGO)**: Menerapkan skrip otomatisasi build dua tahap pada CI/CD.

```rust
// src/lib.rs
// Integrasi jemallocator untuk lingkungan Linux
#[cfg(not(target_env = "msvc"))]
use tikv_jemallocator::Jemalloc;

#[cfg(not(target_env = "msvc"))]
#[global_allocator]
static GLOBAL: Jemalloc = Jemalloc;

#[repr(align(64))] // Cache line alignment meminimalkan false-sharing
#[derive(Clone, Copy, Debug)]
pub struct Order {
    pub order_id: u64,
    pub price: u64,
    pub quantity: u32,
    pub side: u8, // 0 = Buy, 1 = Sell
    pub _padding: [u8; 11], // Pad secara eksplisit ke 32 atau 64 bytes
}

pub struct OrderBookHotPath {
    pub bid_prices: [u64; 8],
    pub bid_quantities: [u32; 8],
}

impl OrderBookHotPath {
    pub fn new() -> Self {
        Self {
            bid_prices: [0; 8],
            bid_quantities: [0; 8],
        }
    }

    /// Autovectorized via AVX2/AVX-512 target flags:
    /// Mengurangi kuantitas serentak menggunakan operasi SIMD
    #[inline(always)]
    pub fn match_market_order(&mut self, incoming_price: u64, mut qty: u32) -> u32 {
        // Rust Compiler akan mentransformasikan iterasi ini menjadi instruksi SIMD
        // jika target-cpu diatur ke 'native' / 'haswell' ke atas.
        for i in 0..8 {
            if self.bid_prices[i] >= incoming_price && qty > 0 {
                let available = self.bid_quantities[i];
                if available <= qty {
                    qty -= available;
                    self.bid_quantities[i] = 0;
                } else {
                    self.bid_quantities[i] -= qty;
                    qty = 0;
                    break;
                }
            }
        }
        qty
    }
}
```

#### Workflow PGO Bash Pipeline
```bash
#!/usr/bin/env bash
set -xeuo pipefail

export RUSTFLAGS="-C target-cpu=native -C lto=thin"

# Langkah 1: Compile instrumented binary
RUSTFLAGS="$RUSTFLAGS -C profile-generate=$(pwd)/target/pgo-data" \
    cargo build --release --bin matching_engine

# Langkah 2: Eksekusi workload realistis menggunakan replay production dataset
./target/release/matching_engine --replay-data ./fixtures/production_order_ticks.bin

# Langkah 3: Merge hasil profile raw LLVM
cargo profdata -- merge \
    -output $(pwd)/target/pgo-data/merged.profdata \
    $(pwd)/target/pgo-data

# Langkah 4: Final compilation menggunakan profil data
RUSTFLAGS="$RUSTFLAGS -C profile-use=$(pwd)/target/pgo-data/merged.profdata" \
    cargo build --release --bin matching_engine
```

#### Hasil Metrik Terverifikasi
*   **Throughput**: Meningkat dari $240,000\ \text{orders/sec}$ menjadi $610,000\ \text{orders/sec}$ ($+154\%$).
*   **P99.9 Tail Latency**: Turun dari $4,200\ \text{ns}$ ke $890\ \text{ns}$ (Drop signifikan sub-microsecond).
*   **Branch Misprediction Rate**: Turun dari $14.8\%$ menjadi $2.1\%$ berkat reorganisasi basic-block via PGO.

---

### 9. Trade-offs Analysis

```
       OPTIMIZATION COMPLEXITY vs DEVELOPER VELOCITY
   ▲
   │                              [PGO + BOLT + SIMD Intrinsics]
   │                               - Maximum Throughput
   │                               - High Build Times (15m+)
   │                               - Complex Deployment Pipeline
C  │
O  │                [LTO=thin + Jemalloc]
M  │                 - Balanced Optimization
P  │                 - Moderate CI Overhead
L  │
E  │  [Default Release]
X  │   - Fast Compilation
I  │   - Sub-optimal Cache & Tail-Latency
T  │
Y  └────────────────────────────────────────────────────────►
                         PERFORMANCE GAIN
```

| Strategi / Tooling | Keuntungan Utama | Kerugian / Konsekuensi Negatif | Skala Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Fat LTO** (`lto = "fat"`) | Inlining antar-crate maksimal, eliminasi total dead-code lintas modularitas. | Waktu kompilasi CI sangat lambat; kebutuhan RAM build machine melonjak dramatis ($>16\text{GB}$). | Hanya aktif pada release tag production build. |
| **Thin LTO** (`lto = "thin"`) | 80-90% efisiensi Fat LTO dengan kompilasi paralel multi-threaded. | Analisis batas optimasi sedikit lebih terbatas dibanding Fat LTO. | Standar default microservice enterprise. |
| **Profile-Guided Opt (PGO)** | Cache locality optimal, layout instruksi tailored untuk hot path real. | Pipeline deployment menjadi 2 tahap; jika workload profiling melenceng, performa regresi. | Layanan high-load dengan pola traffic homogen. |
| **Coverage Fuzzing** | Menemukan silent panics, memory bounds issue tersembunyi, state corruptions. | Resource-intensive (membutuhkan core CPU dedicated berhari-hari). | Komponen parsing protokol, kriptografi, decode buffer. |
| **Target CPU Native** | Mengaktifkan AVX2, AVX-512, FMA tanpa overhead manual runtime dispatching. | Binary tidak portabel; *Illegal Instruction SIGILL* jika di-deploy ke arsitektur berbeda. | Internal private cloud/bare-metal fleet homogen. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Memory Alignment Padding Trap Menyebabkan Cache Pollution
*   **Penyebab**: Menata field struct secara acak, menyebabkan compiler menyisipkan padding byte secara implisit untuk memenuhi alignment CPU word boundary.
*   **Gejala**: Cache misses tinggi (`L1-dcache-load-misses` melonjak signifikan pada `perf`).
*   **Solusi**: Urutkan deklarasi field struct dari ukuran terbesar ke terkecil atau gunakan audit memory via tools eksternal.

```rust
// BURUK: Ukuran struct menjadi 24 byte karena padding 7 bytes + 4 bytes
struct BadLayout {
    a: u8,   // 1 byte
             // PADDING 7 BYTES DI SINI
    b: u64,  // 8 bytes (alignment 8)
    c: u32,  // 4 bytes
             // PADDING 4 BYTES DI SINI
}

// OPTIMAL: Ukuran struct hanya 16 byte (Menghemat L1/L2 cache space)
struct OptimalLayout {
    b: u64,  // 8 bytes
    c: u32,  // 4 bytes
    a: u8,   // 1 byte
             // PADDING 3 BYTES DI AKHIR (Total 16 bytes kelipatan 8)
}
```

#### Kesalahan 2: Fuzzing Target Mengandung Internal Non-Determinism
*   **Penyebab**: Menjalankan harness `cargo-fuzz` pada kode yang memanggil generator bilangan acak (`rand::thread_rng()`), interaksi jam sistem (`Instant::now()`), atau network I/O.
*   **Gejala**: Fuzzer crash reproduction gagal (Non-reproducible crash corpus), fuzzer engine crash, coverage graph macet (*plateau*).
*   **Solusi**: Suntikkan deterministic PRNG (seperti `ChaCha8Rng` dengan seed statis) atau abstraksikan seluruh external time dependencies menggunakan trait mock injection.

#### Kesalahan 3: Iterasi Benchmark Mengikutsertakan Alokasi Setup
*   **Penyebab**: Melakukan inisialisasi collection berat di dalam blok sampling criterion loop `b.iter(|| ...)`.
*   **Solusi**: Gunakan `b.iter_batched` atau `b.iter_with_setup` untuk memisahkan fase setup dengan fase pengukuran throughput.

```rust
// SALAH: Waktu alokasi Vector dihitung ke dalam benchmark operasi komputasi
c.bench_function("vector_sort_leaked_setup", |b| {
    b.iter(|| {
        let mut data = vec![9, 5, 2, 8, 1, 4, 3, 7]; // SETUP INI TERHITUNG
        data.sort_unstable();
        black_box(data);
    })
});

// BENAR: Memisahkan tahap inisialisasi dari pengukuran eksekusi
c.bench_function("vector_sort_isolated", |b| {
    b.iter_batched(
        || vec![9, 5, 2, 8, 1, 4, 3, 7], // Setup phase (Alloc)
        |mut data| {                      // Measurement phase
            data.sort_unstable();
            black_box(data);
        },
        criterion::BatchSize::SmallInput,
    )
});
```

---

### 11. Best Practices (Production Checklist)

#### Production Profiling & Benchmark Gate
*   [ ] **Compiler Flags Profile**: Profil release dikonfigurasi eksplisit pada `Cargo.toml`:
    ```toml
    [profile.release]
    opt-level = 3
    lto = "thin"
    codegen-units = 1
    panic = "abort"
    debug = 1 # Menghasilkan line-table symbol untuk Linux perf tanpa runtime hit
    ```
*   [ ] **Zero Panic Guarantees**: Target deserializer dan parser protokol publik terverifikasi bebas *panic* via minimum 24 jam coverage-guided fuzzing (`cargo-fuzz`).
*   [ ] **Allocator Verification**: Microservice dengan I/O intensif mengikat `jemalloc` atau `mimalloc` sebagai `#[global_allocator]` untuk meredam fragmentasi virtual memory (VMA fragmentation).
*   [ ] **Benchmark Baselines Locked**: File benchmark `criterion` terintegrasi dengan baseline CI (`--save-baseline base`) untuk menolak PR yang memicu degradasi statistik $> 3\%$.
*   [ ] **Assembly Hot-Path Audit**: Lakukan sanity check via `cargo-asm` untuk memastikan invariant checks di dalam loop kritis telah di-hoist keluar atau dieleminasi via slice pattern-matching.
*   [ ] **Memory Profiling Clean**: Binary bebas dari leak yang tumbuh tak terhingga, diverifikasi lewat trace `dhat::Profiler`.

---

### 12. Hands-on Practice

Buatlah environment praktikum profiling dan benchmarking mandiri.

#### Langkah 1: Persiapan Workspace
```bash
mkdir -p hands-on/m02/engine-optimization
cd hands-on/m02/engine-optimization
cargo init --lib
```

Tambahkan dependensi berikut ke `Cargo.toml`:
```toml
[package]
name = "engine-optimization"
version = "0.1.0"
edition = "2021"

[lib]
bench = false

[dependencies]
tikv-jemallocator = { version = "0.5", optional = true }

[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }
proptest = "1.4"
dhat = "0.3"

[[bench]]
name = "engine_bench"
harness = false

[profile.release]
debug = true # Esensial untuk profiling
lto = "thin"
```

#### Langkah 2: Kode Algoritma Agregasi Data
Tuliskan logika komputasi agregasi ke dalam `src/lib.rs`:

```rust
// src/lib.rs
pub struct MetricAggregator;

impl MetricAggregator {
    /// Versi Naif: Banyak alokasi heap intermediate
    pub fn process_metrics_naive(values: &[f64]) -> Vec<f64> {
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let mut variance_deviations = Vec::new();
        
        for v in values {
            variance_deviations.push((v - mean).powi(2));
        }

        variance_deviations.sort_by(|a, b| a.partial_cmp(b).unwrap());
        variance_deviations
    }

    /// Versi Optimal: Zero-copy, reuse memory buffer, single allocation pass
    pub fn process_metrics_optimized(values: &[f64], out_buf: &mut Vec<f64>) {
        if values.is_empty() {
            return;
        }

        out_buf.clear();
        out_buf.reserve(values.len());

        let sum: f64 = values.iter().sum();
        let inv_len = 1.0 / (values.len() as f64);
        let mean = sum * inv_len;

        // Auto-vectorization friendly iteration
        for &v in values {
            let diff = v - mean;
            out_buf.push(diff * diff);
        }

        out_buf.sort_unstable_by(|a, b| a.total_cmp(b));
    }
}
```

#### Langkah 3: Menulis Rigorous Benchmark
Buat file `benches/engine_bench.rs`:

```rust
// benches/engine_bench.rs
use criterion::{black_box, criterion_group, criterion_main, BatchSize, Criterion};
use engine_optimization::MetricAggregator;

fn bench_aggregation(c: &mut Criterion) {
    let mut group = c.benchmark_group("MetricAggregation");
    
    // Dataset simulasi: 10,000 float samples
    let dataset: Vec<f64> = (0..10_000).map(|x| (x as f64) * 0.123).collect();

    group.bench_function("Naive_HeapAlloc", |b| {
        b.iter(|| {
            let res = MetricAggregator::process_metrics_naive(black_box(&dataset));
            black_box(res);
        })
    });

    group.bench_function("Optimized_ZeroCopyReuse", |b| {
        let mut reusable_buffer = Vec::with_capacity(10_000);
        b.iter_batched(
            || (),
            |_| {
                MetricAggregator::process_metrics_optimized(
                    black_box(&dataset),
                    black_box(&mut reusable_buffer),
                );
                black_box(&reusable_buffer);
            },
            BatchSize::SmallInput,
        )
    });

    group.finish();
}

criterion_group!(benches, bench_aggregation);
criterion_main!(benches);
```

#### Langkah 4: Eksekusi Profiling Memory Menggunakan DHAT
Tambahkan test heap profiling di `tests/dhat_memory_test.rs`:

```rust
// tests/dhat_memory_test.rs
use engine_optimization::MetricAggregator;

#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

#[test]
fn profile_memory_usage() {
    let _profiler = dhat::Profiler::new_heap();

    let dataset: Vec<f64> = (0..50_000).map(|x| x as f64).collect();
    
    // Eksekusi varian naif
    let _ = MetricAggregator::process_metrics_naive(&dataset);

    // Amati heap footprint via stats
    let stats = dhat::HeapStats::get();
    println!("Total bytes allocated (Naive): {}", stats.total_bytes);
}
```

Jalankan test dan benchmark:
```bash
# Jalankan criterion benchmark dan analisis HTML report di target/criterion/report/index.html
cargo bench

# Jalankan memory profiling analysis
cargo test --test dhat_memory_test -- --nocapture
```

---

### 13. Exercise

#### Level Easy
*   **Soal**: Diberikan sebuah fungsi kalkulasi moving average `fn moving_average(stream: &[f32], window_size: usize) -> Vec<f32>`. Identifikasi dan mitigasi compiler dead-code elimination pada unit testing benchmark naif. Ubah agar menggunakan benchmark harness `criterion` yang membungkus input dan output dengan `std::hint::black_box`.
*   **Petunjuk**: Pastikan slice input tidak dialokasikan di dalam closure `b.iter`.

#### Level Medium
*   **Soal**: Buat Property-Based Test menggunakan `proptest` untuk struktur data `RingBuffer<T, const CAP: usize>`. Uji invarian: Jumlah elemen yang berhasil di-push tidak boleh melebihi `CAP`. Jika kapasitas penuh, penambahan data baru harus mereplace elemen tertua, dan traversal FIFO harus selalu mengembalikan urutan insertion yang valid.
*   **Petunjuk**: Definisikan `enum Action { Push(u32), Pop }` lalu generate sequence of actions via `prop::collection::vec(any::<Action>(), 1..500)`.

#### Level Hard
*   **Soal**: Diberikan parser network packet `struct PacketParser`. Parser ini memproses payload biner tidak terpercaya (untrusted network bytes). 
    1. Konfigurasikan setup `cargo-fuzz` dengan harness `fuzz_target!`.
    2. Implementasikan parsing biner yang mencakup pengecekan boundary eksplisit tanpa panicking code path (hilangkan semua implicit slice index panics `&data[start..end]`, ganti dengan validasi `.get(...)`).
    3. Deteksi memory allocation exhaust vulnerability (fuzzer input dapat memicu `vec.reserve(malicious_large_size)`). Tambahkan hard ceiling boundary allocation.
*   **Petunjuk**: Harness fuzzing harus dijalankan menggunakan `cargo +nightly fuzz run fuzz_target_1`.

---

### 14. Challenge

**Skenario**: Anda adalah Performance Infrastructure Engineer di sebuah perusahaan IoT global. Sistem menerima $1.000.000$ event telemetry per detik berupa payload compact biner 32-byte dari sensor industri.

**Tugas Tantangan**:
1.  **Arsitektur Parser**: Rancang parser biner zero-alloc menggunakan zero-copy decoding (`#[repr(C, packed)]` atau transmutasi pointer aman via `bytemuck` / direct slice viewing).
2.  **Property & Differential Fuzzing**: Implementasikan differential fuzzer: Bandingkan output parser zero-copy kencang Anda dengan output *reference implementation* yang berbasis `nom` atau `serde`. Buktikan kedua parser menghasilkan data field yang identik untuk seluruh domain byte input.
3.  **Advanced Codegen Inspection**: Pastikan tidak ada fungsi alokasi heap (`__rust_alloc`) pada disassembly output hot-path menggunakan `cargo-asm`.
4.  **Full PGO Deployment**: Setup scripts kompilasi PGO end-to-end yang mengintegrasikan synthetic stress simulation sebagai profile data emitter dan buktikan reduksi p99.9 latency minimal $30\%$ dibandingkan build release standar.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1.  **Mengapa penggunaan `std::time::Instant` secara langsung dalam loop sering kali menghasilkan kesimpulan benchmark yang keliru?**
    *   *Jawaban*: Karena rentan terhadap gangguan interupsi context-switch thread sistem operasi, fluktuasi CPU clock governor (DVFS), cold CPU caches, dan penghapusan seluruh loop oleh compiler melalui *Dead-Code Elimination*.
2.  **Apa fungsi fundamental dari macro `criterion::black_box`?**
    *   *Jawaban*: Memberi instruksi kepada backend compiler (LLVM) untuk mengasumsikan nilai tersebut dapat dibaca/diubah secara tak terduga, melarang compiler melakukan optimasi agresif seperti folding konstan atau mengeliminasi operasi komputasi yang dianggap tidak memiliki *side-effect*.
3.  **Apa perbedaan mendasar antara *Fuzz Testing* berbasis coverage (`libfuzzer`) dengan *Property-Based Testing* (`proptest`)?**
    *   *Jawaban*: *Property-based testing* menghasilkan variasi input berbasis schema tipe data yang terstruktur untuk menguji properti invarian logis, sedangkan coverage-guided fuzzing memutasi deretan *raw bytes* di level terendah dengan memantau edge branch instruction yang dieksekusi di LLVM bitmap untuk menembus cabang kode yang dalam.
4.  **Mengapa ThinLTO sering dipilih sebagai opsi standar produksi enterprise dibanding Full/Fat LTO?**
    *   *Jawaban*: ThinLTO mengeksekusi optimasi inlining lintas modul kompilasi secara paralel sehingga memangkas waktu build hingga $70-80\%$ dibanding Fat LTO, dengan tetap mempertahankan sebagian besar keuntungan performa runtime Fat LTO ($>90\%$).
5.  **Kapan atribut `#[inline(always)]` justru berpotensi merusak performa throughput aplikasi?**
    *   *Jawaban*: Ketika disematkan pada fungsi yang besar dan sering dipanggil di banyak lokasi. Hal ini memicu pembengkakan ukuran machine code (*code bloat*), sehingga melampaui kapasitas CPU Instruction Cache (L1 I-Cache), memicu tingginya I-Cache misses.

#### Intermediate (5 Soal)
6.  **Bagaimana Profile-Guided Optimization (PGO) membantu CPU Branch Predictor bekerja lebih akurat?**
    *   *Jawaban*: PGO merekam data eksekusi riil sehingga LLVM dapat menata ulang *Basic Blocks* biner; cabang yang sering bernilai `true` disusun secara sequensial (fallthrough path), mengurangi penalty pipeline stall saat prediksi branch salah dieksekusi oleh hardware.
7.  **Mengapa `jemalloc` atau `mimalloc` cenderung mengungguli default allocator bawaan Linux glibc pada arsitektur server multi-core berkepadatan tinggi?**
    *   *Jawaban*: Glibc memicu contention lock thread global pada saat konkurensi alokasi tinggi. `jemalloc` dan `mimalloc` memisahkan arena memori independen untuk setiap thread (*thread-local caching*), meminimalkan contention mutex antar-core CPU.
8.  **Apa risiko keamanan/stabilitas penggunaan compiler flag `-C target-cpu=native` pada build binary Docker/Kubernetes container?**
    *   *Jawaban*: Binary yang dikompilasi pada host dengan dukungan instruksi modern (misal: AVX-512) akan mengalami crash fatal seketika (`SIGILL: Illegal Instruction`) saat Pod di-deploy atau di-migrate ke node worker Kubernetes yang memiliki generasi prosesor CPU lebih lama.
9.  **Pada metrik Linux `perf`, apakah yang diindikasikan oleh nilai IPC (*Instructions Per Cycle*) di bawah 1.0 pada kode komputasi intensif?**
    *   *Jawaban*: Mengindikasikan CPU execution pipeline sering mengalami *stall*, kemungkinan besar akibat menunggu data dari RAM (*LLC Cache Misses*), pipeline pipeline flush karena *Branch Mispredictions*, atau latency memori NUMA node.
10. **Bagaimana mekanisme *Shrinking* pada Property-Based Testing bekerja saat menemukan kasus kegagalan (test failure)?**
    *   *Jawaban*: Saat input kompleks memicu kegagalan invarian, engine testing secara deterministik memotong ukuran payload atau memperkecil nilai variabel (misal: memotong vector dari 1000 item menjadi 2 item, atau menurunkan angka integer ke batas terkecil) hingga menemukan *minimal reproducible sample* yang tetap memicu kegagalan tersebut.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Layanan Rust HTTP API gateway mengalami lonjakan latency $p99$ secara berkala dari $2\ \text{ms}$ ke $150\ \text{ms}$ setiap beberapa menit sekali, namun CPU utilization rata-rata berada di bawah $30\%$. Tidak ada bottleneck I/O disk. Bagaimana metodologi investigasi profiling Anda untuk menemukan akar masalah di level sistem?
    *   *Solusi Diagnostik*:
        1. Terapkan memory allocation profiling via `dhat` atau `jemalloc profiling` (`MALLOC_CONF="prof:true"`). Fenomena latency spikes berkala pada CPU rendah umumnya diakibatkan oleh fragmentasi memori heap ekstrem yang memicu OS memory page compaction, atau alokasi buffer sesekali yang sangat masif memicu translasi TLB page-fault.
        2. Jalankan `perf record -e page-faults,context-switches -p <PID>` untuk mendeteksi apakah terjadi minor/major page faults saat spike terjadi.
        3. Tinjau alokasi internal allocator metadata purging. Konfigurasi `jemalloc` background threads untuk meratakan biaya reclaiming memory agar tidak terjadi stop-the-world behavior.

12. **Skenario 2**: CI pipeline perusahaan Anda memakan waktu 45 menit untuk menjalankan `cargo test` dan `cargo-fuzz`. Tim engineer mulai mengabaikan hasil testing lokal. Rekomendasikan arsitektur testing pipeline terdistribusi yang efisien tanpa mengorbankan kualitas jaminan mutu.
    *   *Solusi Diagnostik*:
        1. Pisahkan pipeline: Unit test dan fast regression test dijalankan pada commit stage ($<3\ \text{menit}$) menggunakan mold/lld linker dan `cargo-nextest`.
        2. Property-based testing dikonfigurasi dengan limit iterasi kecil (`cases = 100`) di PR commit stage, dan mode komprehensif (`cases = 10000`) di nightly build.
        3. Fuzz testing diisolasi sepenuhnya dari synchronous CI: Fuzzing dijalankan secara terus-menerus (*Continuous Fuzzing*) pada dedicated infrastructure (seperti ClusterFuzz atau container spot instance) di luar alur merge PR. Temuan corpus crash baru otomatis dilaporkan sebagai issue blocker.

13. **Skenario 3**: Sebuah fungsi encoding data biner streaming di-refactor untuk memanfaatkan auto-vectorization SIMD via compiler flag `-C opt-level=3`. Namun, benchmark Criterion menunjukkan performanya justru turun $15\%$ dibandingkan versi scalar sederhana. Apa yang terjadi pada level microarchitecture?
    *   *Solusi Diagnostik*:
        1. Analisis disassembly via `cargo-asm`: Kemungkinan alignment data pointer memory tidak simetris terhadap batas 32-byte atau 64-byte. Ketika compiler menghasilkan instruksi unaligned vector load (misal: `VMOVUPD`), CPU mengeksekusi penalti cross-cache-line boundary access.
        2. Periksa loop overhead: Jika panjang rata-rata slice yang diproses relatif pendek (misal: $<64$ bytes), biaya loop prologue/epilogue untuk menangani sisa elemen scalar (*peeling/remainder loops*) lebih mahal dibanding keuntungan komputasi vector pack itu sendiri.
        3. Mitigasi: Pastikan alokasi memory memiliki memory alignment explicit (`#[repr(align(32))]`) dan sertakan instruksi percabangan cepat untuk fallback ke loop scalar sederhana jika ukuran slice data kecil.

---

### 16. Summary
*   Verifikasi perangkat lunak modern level mission-critical menuntut integrasi pengujian matematis terarah (*Property-Based Testing*) dan simulasi mutasi asinkron (*Coverage-Guided Fuzzing*) guna menjamin invariant sistem di luar imajinasi skenario pengujian manual.
*   Microbenchmarking yang valid mensyaratkan rigorous statistical analysis (KDE, Confidence Interval Bootstrap) dan pencegahan compiler dead-code elimination via `std::hint::black_box`.
*   Optimasi performa bukan sekadar memilih tipe data primitif, melainkan mengontrol bagaimana LLVM menyusun *instruction layout* ke dalam level microarchitectural CPU via LTO, PGO, Memory Alignment packing, dan pemilihan thread-caching custom allocator (`jemalloc`).
*   Profil sebelum mengoptimasi: Penggunaan Linux `perf`, flamegraph visualizer, dan diagnostic profiler (`dhat`) adalah prasyarat mutlak sebelum mengubah arsitektur kode menjadi Unsafe atau mengimplementasikan custom assembly/SIMD primitives.