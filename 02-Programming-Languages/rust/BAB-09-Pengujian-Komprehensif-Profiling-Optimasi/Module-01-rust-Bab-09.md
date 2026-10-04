# Bab 09 Module 01: Pengujian Komprehensif, Profiling, & Optimasi

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran**: Pemrograman Sistem Tingkat Lanjut (*Systems Programming Track*)
*   **Kategori**: `02-Programming-Languages`
*   **Bahasa Pemrograman**: Rust (Edisi 2021 / Standar Kompilator v1.75+)
*   **Modul**: Bab 09 Module 01
*   **Topik**: Pengujian Komprehensif, Profiling, & Optimasi
*   **Tingkat Kesulitan**: *Intermediate to Advanced*
*   **Prasyarat**:
    *   Pemahaman mendalam tentang *Ownership*, *Borrowing*, dan *Lifetimes*.
    *   Penguasaan *Traits*, *Generics*, *Trait Objects*, dan *Dynamic Dispatch*.
    *   Pemahaman struktur memori: *Stack*, *Heap*, *Pointer dereferencing*, dan *Alignment*.
    *   Familiaritas dasar dengan Cargo, modul internal, dan ekosistem *crates*.
*   **Estimasi Waktu Selesai**: 6–8 Jam Belajar Mandiri & Hands-on Lab

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1.  **Membangun Arsitektur Pengujian Berlapis**: Mengimplementasikan kombinasi *Unit Tests*, *Integration Tests*, *Doc-Tests*, *Property-Based Testing* (`proptest`), serta *Coverage Analysis* (`cargo-llvm-cov`).
2.  **Mendeteksi Mutasi dan Kerentanan Edge-Case**: Menerapkan *Fuzz Testing* menggunakan `cargo-fuzz` (*libFuzzer backend*) dan verifikasi *Undefined Behavior* (UB) menggunakan `Miri`.
3.  **Melakukan Benchmarking Presisi Tinggi**: Merancang pengujian tolok ukur deterministik berbasis statistik menggunakan `criterion.rs` dengan memanfaatkan pencegahan *Dead Code Elimination* melalui `std::hint::black_box`.
4.  **Melakukan Profiling Kinerja CPU dan Memori**: Mengisolasi *bottleneck* instruksi CPU menggunakan *Flamegraph* (`perf`/`cargo-flamegraph`) dan menganalisis alokasi *heap* menggunakan `dhat`.
5.  **Mengeksekusi Strategi Optimasi Tingkat Lanjut**: Menerapkan konfigurasi kompilator (*Fat LTO*, *Profile-Guided Optimization / PGO*, alinyemen CPU natif), transformasi struktur data berorientasi *cache* (*Data-Oriented Design*), serta teknik *Zero-Allocation*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. *Measure, Don't Guess* (Prinsip Verifikasi Empiris)
Optimasi tanpa data profil adalah sumber utama regresi sistem dan kompleksitas kode yang tidak berfaedah. Kompilator modern (`rustc` dengan backend `LLVM`) melakukan transformasi canggih seperti *auto-vectorization*, *loop unrolling*, *function inlining*, dan *dead-code elimination*. Model mental pengembang harus berakar pada data empiris: ukur *baseline*, temukan *bottleneck* via *sampling profiler*, uji hipotesis, dan validasi ulang hasil dengan *statistical benchmarking*.

### 2. *Mechanical Sympathy* (Simpati Mekanikal)
Rust memberikan abstraksi tanpa biaya tambahan (*zero-cost abstractions*), tetapi perangkat keras fisik tetap beroperasi di bawah hukum fisika yang kaku:
*   Akses L1 *Cache*: ~1–1.5 ns.
*   Akses L3 *Cache*: ~10–20 ns.
*   Akses DRAM Utama: ~60–100 ns.
Kode yang cepat adalah kode yang ramah terhadap *CPU instruction cache* (I-Cache) dan *data cache* (D-Cache). Memilih struktur data yang padat (*cache locality*) sering kali mengungguli struktur data berbasis *node pointer* seperti linked-list, meskipun notasi Big-O asimtotiknya terlihat sama atau lebih rendah.

### 3. *The Testing Continuum*
Pengujian dalam Rust bukan sekadar memvalidasi `assert_eq!`. Pengujian membentuk kontinum deterministik:
*   *Unit Testing*: Verifikasi kebenaran logika diskret.
*   *Property-Based Testing*: Eksplorasi domain input tak terhingga untuk menemukan asumsi batas (*invariants*) yang salah.
*   *Fuzz Testing*: Penetrasi input anomali berbasis coverage untuk membongkar kemungkinan *panic*, *hang*, atau *memory safety violation*.
*   *Miri Verification*: Pembuktian formal ketiadaan *Undefined Behavior* pada blok `unsafe`.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Optimasi dan Profiling Berbasis Bukti

```
                  +--------------------------------+
                  |  Implementasi Logika Awal &    |
                  |     Arsitektur Fungsional      |
                  +---------------+----------------+
                                  |
                                  v
                  +--------------------------------+
                  | Pengujian Komprehensif:        |
                  | - Unit, Integration, Doc Tests |
                  | - Property Tests (proptest)    |
                  | - Miri (Verifikasi Unsafe)     |
                  +---------------+----------------+
                                  |
                                  v
                  +--------------------------------+
                  |     Benchmarking Awal          |
                  |   (Criterion.rs Baseline)      |
                  +---------------+----------------+
                                  |
                                  v
                  +--------------------------------+
                  | Profiling CPU & Heap Memory:   |
                  | - cargo-flamegraph / perf      |
                  | - DHAT (Heap Allocation Trace) |
                  +---------------+----------------+
                                  |
                        Apakah Bottleneck Terdeteksi?
                         /                       \
                      Tidak                      Ya
                       /                           \
                      v                             v
           +--------------------+         +--------------------+
           | Kinerja Sesuai SLA |         | Diagnosa Domain:   |
           | Siap Rilis         |         | - Alokasi Memori?  |
           +--------------------+         | - Cache Miss?      |
                                          | - Algoritmik O(n)? |
                                          +---------+----------+
                                                    |
                                                    v
                                          +--------------------+
                                          | Rekayasa Optimasi: |
                                          | - Zero-Alloc Slices|
                                          | - AoS -> SoA       |
                                          | - LTO & SIMD       |
                                          +---------+----------+
                                                    |
                                                    v
                                          +--------------------+
                                          | Regresi Testing:   |
                                          | Criterion vs Base  |
                                          +--------------------+
                                                    |
                                                    +---> (Kembali ke Profiling)
```

### Piramida Strategi Pengujian Rust

```
                    / \
                   /   \
                  / Fuzz \         <- cargo-fuzz (libFuzzer: input acak berbasis coverage)
                 /  Test  \
                /----------\
               /  Property  \      <- proptest / quickcheck (Validasi invarian matematika)
              /   Testing    \
             /----------------\
            /   Integration    \   <- tests/*.rs (Black-box API boundary validation)
           /      Testing       \
          /----------------------\
         /      Unit Testing      \ <- src/**/*.rs (White-box, doc-tests, per-fungsi)
        +--------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Cargo Test Runner Internal
Ketika perintah `cargo test` dijalankan:
*   Kompilator mengompilasi kode sumber dengan menambahkan parameter flag `--test`.
*   Semua fungsi yang ditandai atribut `#[test]` dikumpulkan ke dalam sebuah larik deskriptor uji berstruktur internal `test::TestDescAndFn`.
*   *Test Harness* bawaan (`libtest`) mengeksekusi deskriptor-deskriptor tersebut secara multi-threaded (default: jumlah core logika CPU) di dalam thread pool khusus.
*   Jika terjadi *panic* di dalam fungsi uji, *harness* menangkap *unwinding panic* tersebut menggunakan `std::panic::catch_unwind`, menandai status uji sebagai `FAILED`, dan melanjutkan eksekusi ke pengujian berikutnya tanpa menghentikan *main thread runner*.

### 2. Criterion.rs: Mesin Analisis Statistik
Benchmarking naif menggunakan loop waktu sederhana sering kali invalid akibat *CPU throttle*, *OS context switching*, dan variasi *power states* (Intel SpeedStep / AMD Cool'n'Quiet). `criterion.rs` menyelesaikan persoalan ini melalui:
*   **Warming-up Phase**: Mengeksekusi kode target selama durasi tertentu untuk memanaskan CPU instruction cache dan data cache.
*   **Bootstrap Resampling**: Menggunakan komputasi statistik *non-parametric bootstrap* (100.000 iterasi) guna mengestimasi *confidence interval* (umumnya 95%) untuk *mean* dan *median*.
*   **Kernel Density Estimation (KDE)**: Memetakan distribusi waktu eksekusi untuk mendeteksi *outlier* dan kondisi multimodal (indikasi interferensi thread sistem latar belakang).

### 3. LLVM Optimizer & Pencegahan Eliminasi Kode (*Black Box*)
Kompilator Rust memancarkan LLVM IR. Pada profil rilis (`--release` / `opt-level = 3`), LLVM menjalankan rangkaian optimasi agresif:
*   *Dead Code Elimination (DCE)*: Menghapus komputasi yang nilainya tidak pernah dibaca lagi oleh program.
*   *Constant Folding*: Mengalkulasi ekspresi deterministik pada saat kompilasi.
Untuk mencegah fungsi uji benchmarking dihilangkan sepenuhnya oleh DCE, `std::hint::black_box` menyisipkan *inline assembly barrier* nol-biaya (*empty inline-asm constraint* `"r"` atau memory clobber). Instruksi ini memaksa LLVM berasumsi bahwa variabel tersebut dibaca dan dimodifikasi secara arbitrer oleh perangkat luar, sehingga jalur komputasinya dipertahankan secara utuh.

### 4. Mekanisme Profile-Guided Optimization (PGO)
PGO menjembatani celah antara kompilasi statis dan perilaku *runtime*:
1.  **Instrumentasi**: Kompilator menyisipkan *counters* di setiap percabangan alur kontrol (BB - *Basic Blocks*).
2.  **Profiling Run**: Eksekusi program di bawah beban kerja produksi yang realistis; file `.profraw` ditulis ke disk, mencatat cabang mana yang paling sering dieksekusi (*hot paths*) dan yang jarang diakses (*cold paths*).
3.  **Rekompilasi Terpandu**: File profil dikonversi menjadi format `.profdata`. LLVM mengompilasi ulang kode sumber, mengalokasikan registri dan mengoptimalkan penempatan instruksi assembly secara lokal khusus untuk *hot paths*, meminimalkan lompatan instruksi (*instruction branch misses*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Property-Based Testing vs Example-Based Testing
*Example-based testing* (pengujian berbasis contoh) hanya menguji subset diskret dari ruang keadaan: misalnya memastikan fungsi `tambah(2, 3) == 5`. Model ini rentan meloloskan kasus-kasus batas seperti integer overflow, pembagian dengan nol, string non-UTF-8, atau *state transitions* yang tidak terduga.

*Property-based testing* mendefinisikan hubungan invarian aksiomatik yang harus selalu bernilai benar untuk setiap anggota himpunan domain input.
Sebagai contoh, pada sistem serialisasi/deserialisasi:
$$\forall x \in \text{Domain}, \quad \text{deserialize}(\text{serialize}(x)) == x$$
Framework `proptest` menghasilkan ribuan input pseudorandom secara deterministik. Ketika suatu kegagalan ditemukan, framework secara otomatis melakukan proses **shrinking**: mengurangi input kompleks yang gagal menjadi varian input terkecil yang tetap mereproduksi kegagalan tersebut (misalnya, memotong vektor 1000 elemen menjadi vektor 1 elemen atau string kosong).

### 2. Teori Alokasi Memori dan Dampaknya Terhadap Latensi
Alokator umum (*general-purpose memory allocator*) seperti `glibc malloc` atau `mimalloc` harus menangani konkurensi dan mencegah fragmentasi. Permintaan alokasi dinamis (`heap`) memerlukan:
*   Traversal *freelist* atau *thread-local caching bins*.
*   Potensi *syscall* (`brk` atau `mmap`) jika arena memori habis.
*   Peningkatan kemungkinan *page fault* dan *cache invalidation*.

Dalam konteks komputasi sistem berlatensi rendah, struktur alokasi harus ditransformasikan dari pendekatan berbasis alokasi individual per-objek (`Box<T>`, `Rc<T>`) ke:
*   *Contiguous Memory Arrays* (`Vec<T>` teralokasi di awal dengan `with_capacity`).
*   *Small-buffer optimization* (`SmallVec<[T; N]>` yang menyimpan elemen di *stack* jika $N \le \text{threshold}$, dan beralih ke *heap* hanya jika meluap).
*   *Monotonic Arena Allocation* (`bumpalo`), di mana deallokasi dilakukan secara serentak (*batch*), mereduksi kompleksitas deallokasi individual menjadi nol instruksi per objek.

### 3. Transformasi Struktur Memori: AoS vs SoA
Representasi data tradisional menggunakan **Array of Structures (AoS)**:
```rust
struct Particle {
    x: f32, // 4 bytes
    y: f32, // 4 bytes
    z: f32, // 4 bytes
    mass: f32, // 4 bytes
    id: u64, // 8 bytes
    flag: bool, // 1 byte + 7 bytes padding
}
// Array of Structures: [P1, P2, P3, P4, ...]
```
Jika algoritma hanya perlu memperbarui posisi (`x`, `y`, `z`), satu *cache line* (64 byte) yang ditarik dari DRAM hanya memuat 2 objek `Particle` (32 byte per partikel). Sisanya (50% dari *cache line bandwidth*) terbuang sia-sia memuat `id` dan `flag`.

Dengan **Structure of Arrays (SoA)**:
```rust
struct Particles {
    x: Vec<f32>,
    y: Vec<f32>,
    z: Vec<f32>,
    mass: Vec<f32>,
    id: Vec<u64>,
    flag: Vec<bool>,
}
```
Ketika mengiterasi array `x`, sebuah *cache line* 64 byte memuat persis 16 nilai `f32` secara berurutan. Tidak ada bandwidth bus memori yang terbuang, *hardware prefetcher* CPU bekerja optimal, dan LLVM mampu mengeksekusi instruksi *Single Instruction Multiple Data* (SIMD) secara otomatis (*auto-vectorization*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode sumber yang mendemonstrasikan integrasi Unit Testing, Property-Based Testing, dan Tolok Ukur Criterion di dalam modul parsing dan perhitungan metrik numerik.

### 1. Struktur Modul Logika Inti & Unit Testing (`src/lib.rs`)

```rust
use std::hint::black_box;

#[derive(Debug, PartialEq, Clone)]
pub struct FinancialRecord {
    pub id: u64,
    pub amount: i64,
    pub fee: u32,
}

#[derive(Debug, PartialEq, Eq)]
pub enum FinancialError {
    InvalidFormat,
    ArithmeticOverflow,
}

pub fn parse_and_accumulate(raw_records: &[&str]) -> Result<i64, FinancialError> {
    let mut total: i64 = 0;

    for record_str in raw_records {
        let parts: Vec<&str> = record_str.split(',').collect();
        if parts.len() != 3 {
            return Err(FinancialError::InvalidFormat);
        }

        let amount: i64 = parts[1]
            .parse::<i64>()
            .map_err(|_| FinancialError::InvalidFormat)?;
        
        let fee: u32 = parts[2]
            .parse::<u32>()
            .map_err(|_| FinancialError::InvalidFormat)?;

        let net = amount
            .checked_sub(fee as i64)
            .ok_or(FinancialError::ArithmeticOverflow)?;

        total = total
            .checked_add(net)
            .ok_or(FinancialError::ArithmeticOverflow)?;
    }

    Ok(total)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_and_accumulate_valid() {
        let input = ["1,1000,50", "2,2000,100"];
        let result = parse_and_accumulate(&input);
        assert_eq!(result, Ok(2850));
    }

    #[test]
    fn test_parse_and_accumulate_invalid_format() {
        let input = ["1,1000"];
        let result = parse_and_accumulate(&input);
        assert_eq!(result, Err(FinancialError::InvalidFormat));
    }

    #[test]
    fn test_parse_and_accumulate_overflow() {
        let input = [format!("1,{},0", i64::MAX).as_str(), "2,1,0"];
        let slice = [input[0], input[1]];
        let result = parse_and_accumulate(&slice);
        assert_eq!(result, Err(FinancialError::ArithmeticOverflow));
    }
}
```

### 2. Pengujian Berbasis Properti (`tests/property_tests.rs`)

Pastikan ketergantungan `proptest = "1.4"` terpasang di `Cargo.toml`.

```rust
use proptest::prelude::*;

// Invarian sistem: Net amount dari sebuah transaksi tidak pernah boleh 
// melebihi nilai awal amount jika fee >= 0.
proptest! {
    #[test]
    fn test_net_amount_invariant(
        amount in 0i64..=i64::MAX / 2,
        fee in 0u32..=u32::MAX
    ) {
        let record_str = format!("1,{},{}", amount, fee);
        let result = financial_engine::parse_and_accumulate(&[&record_str]);

        if let Ok(net) = result {
            prop_assert!(net <= amount);
        } else {
            // Error overflow ditoleransi jika parameter berada di batas ekstrem
            prop_assert!(amount - (fee as i64) < 0 || (amount as i128 - fee as i128) < i64::MIN as i128);
        }
    }
}
```

### 3. Harness Tolok Ukur Criterion (`benches/engine_bench.rs`)

Tambahkan `criterion = { version = "0.5", features = ["html_reports"] }` ke `[dev-dependencies]` dan entri `[[bench]]` pada `Cargo.toml`.

```rust
use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use financial_engine::parse_and_accumulate;

fn bench_parse_and_accumulate(c: &mut Criterion) {
    let mut group = c.benchmark_group("FinancialParsing");
    
    // Dataset deterministik sintetis
    let sample_small: Vec<String> = (0..100)
        .map(|i| format!("{i},1000,50"))
        .collect();
    let sample_small_refs: Vec<&str> = sample_small.iter().map(AsRef::as_ref).collect();

    group.throughput(Throughput::Elements(sample_small_refs.len() as u64));

    group.bench_function(BenchmarkId::new("parse_and_accumulate", "100_records"), |b| {
        b.iter(|| {
            // Mencegah LLVM menghapus loop komputasi melalui DCE
            let input = black_box(&sample_small_refs[..]);
            let _ = parse_and_accumulate(input);
        });
    });

    group.finish();
}

criterion_group!(benches, bench_parse_and_accumulate);
criterion_main!(benches);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Implementasi Modul Inti (`src/lib.rs`)

*   **Baris 24**: `pub fn parse_and_accumulate(raw_records: &[&str]) -> Result<i64, FinancialError>`
    *   Menerima irisan referensi string `&[&str]` untuk mencegah kepemilikan string secara langsung pada caller, memungkinkan fungsi beroperasi tanpa perlu mengalokasikan memori baru di pemanggil.
*   **Baris 28**: `let parts: Vec<&str> = record_str.split(',').collect();`
    *   *Bottleneck Tersembunyi*: Mengalokasikan vektor baru di heap pada setiap iterasi baris string. Operasi ini menyebabkan overhead malloc/free yang substansial pada pemrosesan throughput tinggi.
*   **Baris 38–40**:
    ```rust
    let net = amount
        .checked_sub(fee as i64)
        .ok_or(FinancialError::ArithmeticOverflow)?;
    ```
    *   Operasi aritmatika aman. Mode rilis (`--release`) Rust secara default membungkus integer overflow (*two's complement wrap*), bukan *panic*. Penggunaan `.checked_sub()` secara eksplisit memaksakan verifikasi runtime tanpa bergantung pada konfigurasi profile kompilasi.
*   **Baris 42–44**:
    ```rust
    total = total
        .checked_add(net)
        .ok_or(FinancialError::ArithmeticOverflow)?;
    ```
    *   Akumulasi defensif. Mencegah status overflow diam-diam pada total metrik keuangan, memvalidasi integritas data numerik.

### Analisis Modul Benchmark (`benches/engine_bench.rs`)

*   **Baris 13**: `group.throughput(Throughput::Elements(sample_small_refs.len() as u64));`
    *   Mengonfigurasi Criterion untuk mengukur dan menampilkan metrik performa dalam satuan unit pemrosesan per detik (elemen/detik), bukan sekadar durasi mentah.
*   **Baris 17**: `let input = black_box(&sample_small_refs[..]);`
    *   Memasukkan pointer data ke dalam instruksi penghalang kompilator (*compiler barrier*). Tanpa instruksi ini, LLVM dapat mendeteksi bahwa data `sample_small_refs` bersifat konstan dan mengabaikan seluruh siklus kalkulasi iteratif.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Mesin Filter Log Transaksi Latensi Rendah (*Gateway Trading*)
Sebuah gateway sistem perdagangan elektronik memproses aliran log transaksi finansial berupa teks semi-terstruktur dengan volume transaksi $5.000.000$ pesan/detik. Service awal mengalami masalah berupa:
1.  Peningkatan latensi P99 hingga mencapai 12 milidetik (target SLA: $\le 500$ mikrodetik).
2.  Penggunaan memori yang melonjak drastis (*heap thrashing*) akibat jutaan alokasi sementara berukuran kecil.
3.  Tingginya *CPU Cache Misses* yang terdeteksi via Linux hardware counters.

### Sasaran Teknis
1.  Mengeliminasi seluruh alokasi memori dinamis (*Zero-Allocation*) pada jalur kritis pemrosesan (*hot path*).
2.  Mengganti pembacaan berbasis pemisahan string dinamis (`split().collect::<Vec<_>>()`) menggunakan iterator non-alokasi berukuran tetap.
3.  Memverifikasi invarian transformasi data menggunakan Property-Based Testing dan membuktikan penurunan latensi melalui benchmarking statistik Criterion.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah refaktorisasi arsitektur mesin pemrosesan log menjadi implementasi *zero-allocation* yang memanfaatkan *stack-based array views*, parsing in-place, dan algoritma *cache-friendly*.

### Kode Produksi Teroptimasi (`src/optimized_engine.rs`)

```rust
use std::fmt;

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum EngineError {
    MalformedPayload,
    CapacityExceeded,
    CalculationOverflow,
}

impl fmt::Display for EngineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EngineError::MalformedPayload => write!(f, "Format log tidak valid"),
            EngineError::CapacityExceeded => write!(f, "Kapasitas array internal terlampaui"),
            EngineError::CalculationOverflow => write!(f, "Integer overflow pada agregasi nilai"),
        }
    }
}

impl std::error::Error for EngineError {}

/// Struktur data padat berorientasi cache (Ukuran pas 16 byte, cache-line aligned friendly)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(C)]
pub struct TransactionRecord {
    pub transaction_id: u32,
    pub symbol_id: u16,
    pub flag: u8,
    pub _reserved: u8, // Alinyemen manual eksplisit
    pub net_value: i64,
}

/// Zero-Allocation Parser: Mem-parsing string ASCII byte secara in-place tanpa alokasi Heap
#[inline(always)]
pub fn parse_log_line_zero_alloc(raw_line: &str) -> Result<TransactionRecord, EngineError> {
    let bytes = raw_line.as_bytes();
    let mut fields = [0usize; 4]; // Menyimpan indeks pemisah koma
    let mut field_idx = 0;

    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b',' {
            if field_idx >= fields.len() {
                return Err(EngineError::MalformedPayload);
            }
            fields[field_idx] = i;
            field_idx += 1;
        }
        i += 1;
    }

    // Format yang valid harus memiliki tepat 3 pemisah koma: ID,SymbolID,Flag,NetValue
    if field_idx != 3 {
        return Err(EngineError::MalformedPayload);
    }

    let id_bytes = &bytes[0..fields[0]];
    let symbol_bytes = &bytes[fields[0] + 1..fields[1]];
    let flag_bytes = &bytes[fields[1] + 1..fields[2]];
    let net_val_bytes = &bytes[fields[2] + 1..];

    let transaction_id = parse_u32_fast(id_bytes)?;
    let symbol_id = parse_u16_fast(symbol_bytes)?;
    let flag = parse_u8_fast(flag_bytes)?;
    let net_value = parse_i64_fast(net_val_bytes)?;

    Ok(TransactionRecord {
        transaction_id,
        symbol_id,
        flag,
        _reserved: 0,
        net_value,
    })
}

// Parser konversi ASCII integer kencang tanpa overhead abstraksi format library umum
#[inline(always)]
fn parse_u32_fast(bytes: &[u8]) -> Result<u32, EngineError> {
    if bytes.is_empty() {
        return Err(EngineError::MalformedPayload);
    }
    let mut acc: u32 = 0;
    for &b in bytes {
        if !b.is_ascii_digit() {
            return Err(EngineError::MalformedPayload);
        }
        acc = acc
            .checked_mul(10)
            .and_then(|v| v.checked_add((b - b'0') as u32))
            .ok_or(EngineError::CalculationOverflow)?;
    }
    Ok(acc)
}

#[inline(always)]
fn parse_u16_fast(bytes: &[u8]) -> Result<u16, EngineError> {
    parse_u32_fast(bytes).and_then(|v| {
        if v <= u16::MAX as u32 {
            Ok(v as u16)
        } else {
            Err(EngineError::CalculationOverflow)
        }
    })
}

#[inline(always)]
fn parse_u8_fast(bytes: &[u8]) -> Result<u8, EngineError> {
    parse_u32_fast(bytes).and_then(|v| {
        if v <= u8::MAX as u32 {
            Ok(v as u8)
        } else {
            Err(EngineError::CalculationOverflow)
        }
    })
}

#[inline(always)]
fn parse_i64_fast(bytes: &[u8]) -> Result<i64, EngineError> {
    if bytes.is_empty() {
        return Err(EngineError::MalformedPayload);
    }
    let (is_negative, slice) = match bytes[0] {
        b'-' => (true, &bytes[1..]),
        b'+' => (false, &bytes[1..]),
        _ => (false, bytes),
    };

    if slice.is_empty() {
        return Err(EngineError::MalformedPayload);
    }

    let mut acc: i64 = 0;
    for &b in slice {
        if !b.is_ascii_digit() {
            return Err(EngineError::MalformedPayload);
        }
        let digit = (b - b'0') as i64;
        acc = acc
            .checked_mul(10)
            .and_then(|v| v.checked_add(digit))
            .ok_or(EngineError::CalculationOverflow)?;
    }

    if is_negative {
        acc = acc.checked_neg().ok_or(EngineError::CalculationOverflow)?;
    }

    Ok(acc)
}

/// Pemrosesan batch tanpa alokasi heap: Buffer keluaran dialokasikan di awal (Caller-Provided)
pub fn process_batch_zero_alloc(
    lines: &[&str],
    out_records: &mut [TransactionRecord],
) -> Result<usize, EngineError> {
    if out_records.len() < lines.len() {
        return Err(EngineError::CapacityExceeded);
    }

    let mut count = 0;
    for &line in lines {
        let rec = parse_log_line_zero_alloc(line)?;
        // Penulisan contiguous memory secara sequential (Cache write friendly)
        out_records[count] = rec;
        count += 1;
    }

    Ok(count)
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Mengoptimalkan sistem perangkat lunak selalu melibatkan kompromi teknis. Tabel berikut menguraikan trade-off struktural dalam pengujian, optimasi kompilator, dan arsitektur data.

### 1. Perbandingan Paradigma Pengujian

| Karakteristik | Unit Testing (Example-Based) | Property-Based Testing (`proptest`) | Fuzz Testing (`cargo-fuzz`) |
| :--- | :--- | :--- | :--- |
| **Cakupan Ruang Input** | Rendah (Hanya kasus diskret yang ditulis developer) | Luas (Ribuan input deterministik dengan sampling acak) | Ekstrem (Mutasi berbasis feedback cakupan LLVM) |
| **Waktu Eksekusi CI** | Milidetik (Sangat Cepat) | Detik (Menengah, tergantung jumlah skenario) | Jam / Terus menerus (*Continuous Fuzzing*) |
| **Kemudahan Debug** | Tinggi (Input tetap dan terprediksi) | Tinggi (Fitur *Automated Shrinking* ke kasus minimal) | Sedang–Rendah (Menghasilkan binary reproducer raw) |
| **Sasaran Temuan Utama** | *Regresi fungsional dasar* | *Pelanggaran invarian logika bisnis* | *Crash, Hang, OOM, Undefined Behavior* |

### 2. Konfigurasi Link-Time Optimization (LTO)

| Tipe LTO | Waktu Kompilasi | Ukuran Binary Output | Efisiensi Runtime (Optimasi Cross-Crate) |
| :--- | :--- | :--- | :--- |
| `lto = "off"` | Paling Cepat | Paling Besar | Terbatas dalam satu compilation unit (*no cross-crate inlining*) |
| `lto = "thin"` | Menengah (Dukungan Paralelisme) | Terkompresi Secara Substansial | Sangat Bagus (~90-95% potensi performa Fat LTO) |
| `lto = "fat"` | Sangat Lambat (Single-Threaded Bottleneck) | Minimal / Sangat Ringkas | Maksimum (Analisis global seluruh dependency graph) |

### 3. Representasi Memori: AoS vs SoA

```
Array of Structures (AoS):
[ (Pos, Vel, Mass), (Pos, Vel, Mass), (Pos, Vel, Mass) ]
- Pro: Mempertahankan enkapsulasi objek secara natural.
- Con: Polusi CPU cache line jika kalkulasi hanya membutuhkan 'Pos'.

Structure of Arrays (SoA):
Pos:  [ Pos1, Pos2, Pos3, ... ]
Vel:  [ Vel1, Vel2, Vel3, ... ]
Mass: [ Mass1, Mass2, Mass3, ... ]
- Pro: Menjamin pemanfaatan L1 Data Cache hingga 100%, memudahkan SIMD Vectorization.
- Con: Kompleksitas penulisan kode meningkat; dereferensi indeks majemuk.
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. *Dead Code Elimination* dalam Benchmarking Mikro
Jika hasil keluaran fungsi tidak digunakan, kompilator LLVM dapat menghapus seluruh loop eksekusi.
*   **Dampak Negatif**: Benchmark melaporkan durasi 0.3 ns (eksekusi kosong), menciptakan ilusi peningkatan performa palsu.
*   **Solusi**: Bungkus argumen input dan output dengan `std::hint::black_box`.

### 2. Flaky Tests Akibat Eksekusi Paralel `libtest`
Secara default, `cargo test` mengeksekusi semua fungsi test secara paralel pada thread pool.
*   **Pitfall**: Tes yang memodifikasi *Current Working Directory* (`std::env::set_current_dir`), variabel lingkungan (`std::env::set_var`), atau mengakses port database/jaringan yang sama akan menghasilkan error *intermittent*.
*   **Solusi**: Jalankan tes bermasalah secara berurutan menggunakan `cargo test -- --test-threads=1`, atau gunakan isolasi state via locking (`parking_lot::Mutex`).

### 3. Perilaku Integer Overflow di Debug vs Release
*   Pada mode **Debug**: Rust menyisipkan instruksi pemeriksaan overflow integer; kondisi luapan memicu *panic*.
*   Pada mode **Release**: Rust mengabaikan pemeriksaan tersebut demi efisiensi instruksi, menghasilkan perilaku *two's complement wrap-around*.
*   **Pitfall**: Bug korupsi data baru muncul saat aplikasi dideploy ke lingkungan produksi karena testing hanya dijalankan pada mode Debug tanpa pengujian kalkulasi batas.

### 4. *False Sharing* pada Arsitektur Multi-Thread
Ketika dua thread pada core CPU yang berbeda memodifikasi variabel atomic yang letaknya berdampingan di memori (di dalam cache line 64 byte yang sama):
*   Core 1 dan Core 2 akan saling membatalkan (*invalidate*) cache line satu sama lain secara terus menerus melalui protokol *cache coherency* (MESI).
*   **Solusi**: Gunakan atribut alinyemen eksplisit `#[repr(align(64))]` untuk memisahkan data atomic antar-thread.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Kesalahan Alokasi String Berulang di Jalur Panas

#### Buruk (BAD): Alokasi Heap Dinamis Berulang
```rust
// MENGALOKASIKAN HEAP PADA SETIAP ITERASI
fn process_keys(keys: &[u32]) -> Vec<String> {
    let mut results = Vec::new();
    for &k in keys {
        // format! memanggil dynamic memory allocator internal
        results.push(format!("KEY-{}", k)); 
    }
    results
}
```

#### Benar (GOOD): Zero-Allocation via Buffer Reuse
```rust
use std::fmt::Write;

// MEMANFAATKAN ULANG SINGLE BUFFER TANPA DEALLOCATION
fn process_keys_optimized(keys: &[u32], callback: impl Fn(&str)) {
    let mut buffer = String::with_capacity(32);
    for &k in keys {
        buffer.clear(); // Panjang direset ke 0, kapasitas heap tetap bertahan
        let _ = write!(&mut buffer, "KEY-{}", k);
        callback(&buffer);
    }
}
```

---

### 2. Kesalahan Naif Melakukan Assertion dalam Benchmark

#### Buruk (BAD): Menyertakan Assert Berat di Dalam Bench Loop
```rust
use criterion::{Criterion, black_box};

fn bad_benchmark(c: &mut Criterion) {
    c.bench_function("expensive_op", |b| {
        b.iter(|| {
            let res = expensive_computation(black_box(42));
            // Assert menyuntikkan instruksi percabangan yang merusak statistik cache & pipeline CPU
            assert_eq!(res, 1764); 
        });
    });
}
```

#### Benar (GOOD): Menjaga Iteration Loop Tetap Steril
```rust
use criterion::{Criterion, black_box};

fn good_benchmark(c: &mut Criterion) {
    // Validasi kebenaran dilakukan di luar loop benchmarking
    assert_eq!(expensive_computation(42), 1764);

    c.bench_function("expensive_op", |b| {
        b.iter(|| {
            // Hanya operasi yang diuji dan black_box sink yang berada dalam hot loop
            black_box(expensive_computation(black_box(42)))
        });
    });
}
```

---

### 3. Ketidakmampuan Mendeteksi Undefined Behavior pada Unsafe Pointer Casts

#### Buruk (BAD): Melakukan Casting Pointer Mengabaikan Persyaratan Alinyemen
```rust
// MEMBACA BYTE ARRAY SEBAGAI U64 DENGAN UNALIGNED MEMORY ACCESS
pub fn read_u64_bad(data: &[u8]) -> u64 {
    assert!(data.len() >= 8);
    // UNDEFINED BEHAVIOR: data.as_ptr() mungkin tidak teralinyemen ke batas kelipatan 8-byte!
    unsafe { *(data.as_ptr() as *const u64) }
}
```

#### Benar (GOOD): Menggunakan Pointer Read Bertoleransi Unaligned Access
```rust
pub fn read_u64_good(data: &[u8]) -> u64 {
    assert!(data.len() >= 8);
    // AMAN DARI UB: read_unaligned menangani alignment perangkat keras secara internal
    unsafe { std::ptr::read_unaligned(data.as_ptr() as *const u64) }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### 1. Standardisasi Profil Kompilasi (`Cargo.toml`)
Pada aplikasi skala industri dengan target performa tinggi, konfigurasi profile kompilasi harus diatur secara presisi:

```toml
[profile.release]
opt-level = 3            # Optimasi agresif maksimum
lto = "thin"             # Cross-crate inlining dengan waktu link seimbang
codegen-units = 1        # Mengurangi fragmentasi unit kompilasi, maksimalkan optimasi LLVM
panic = "abort"          # Mengeliminasi biaya unwinding tables runtime stack
strip = "symbols"        # Membuang simbol debug untuk memperkecil binary footprint

[profile.bench]
opt-level = 3
lto = "thin"
codegen-units = 1
debug = true             # Simbol debug dipertahankan agar profiling CPU/Flamegraph akurat
```

### 2. Standar Matriks Sanitasi & Verifikasi CI
Pipeline Continuous Integration (CI) sistem Rust modern wajib menjalankan tingkatan analisis berikut sebelum proses merge:
1.  **Unit & Integration Test**: `cargo test --workspace --all-targets`
2.  **Miri UB Sanitizer**: `cargo miri test` (Mendeteksi memory safety violation dan *aliasing rules violation* pada unsafe code).
3.  **Address & Leak Sanitizer**: `RUSTFLAGS="-Zsanitizer=address" cargo test --target x86_64-unknown-linux-gnu` (Khusus arsitektur x86_64 pada toolchain Nightly).
4.  **Coverage Guard**: `cargo llvm-cov --fail-under-lines 85` (Menolak integrasi kode dengan cakupan pengujian di bawah ambang batas minimal).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Vectorization (SIMD) Eksplisit
Kompilator tidak selalu berhasil melakukan *auto-vectorization* jika terdapat percabangan kompleks di dalam loop. Penggunaan operasi irisan *chunk* memungkinkan instruksi memproses banyak data sekaligus dalam satu siklus clock CPU.

```rust
/// Akumulasi data integer 32-bit menggunakan teknik Chunking Unrolling
/// Memudahkan compiler memancarkan instruksi register vektor AVX2 / NEON
pub fn sum_slice_unrolled(data: &[i32]) -> i64 {
    let mut total = 0i64;
    let chunks = data.chunks_exact(4);
    let remainder = chunks.remainder();

    for chunk in chunks {
        // Kompilator memetakan unrolled accumulation ini langsung ke SIMD registers
        total += (chunk[0] as i64)
            + (chunk[1] as i64)
            + (chunk[2] as i64)
            + (chunk[3] as i64);
    }

    for &val in remainder {
        total += val as i64;
    }

    total
}
```

### 2. Optimasi Alokasi Berpola Monotonik Menggunakan Arena
Jika ribuan objek dialokasikan untuk memproses satu siklus request web lalu dibuang secara bersamaan, alokasi individual ke OS heap merupakan pemborosan. Arena allocator (`bumpalo`) mengalokasikan memori dalam satu blok contiguous besar:

```rust
use bumpalo::Bump;

pub fn execute_transaction_lifecycle() {
    // Alokasi awal arena buffer 64KB di heap
    let bump = Bump::with_capacity(65536);

    // Alokasi instan: hanya menggeser offset pointer (Zero syscall overhead)
    let record1 = bump.alloc(1024u32);
    let record2 = bump.alloc_str("payload transaksi finansial");

    assert_eq!(*record1, 1024);
    assert_eq!(record2, &"payload transaksi finansial");

    // Seluruh alokasi dibersihkan serentak dalam 1 instruksi pointer reset
    bump.reset();
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mencegah Denial of Service (DoS) Melalui Fuzz Testing
Algoritma parsing string yang rentan terhadap *quadratic complexity* $O(N^2)$ dapat mengekspos aplikasi ke serangan komputasi CPU exhaustion. `cargo-fuzz` mengotomatisasi penemuan kasus input patologis tersebut.

Contoh harness fuzzing (`fuzz/fuzz_targets/fuzz_parser.rs`):

```rust
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // Fuzzing hanya menerima byte slice arbitrer
    if let Ok(utf8_str) = std::str::from_utf8(data) {
        // Memastikan parser tidak pernah mengalami panik tak terkendali atau loop tak terbatas
        let _ = financial_engine::parse_log_line_zero_alloc(utf8_str);
    }
});
```

Perintah eksekusi fuzzer:
```bash
cargo install cargo-fuzz
cargo +nightly fuzz run fuzz_parser -- -max_len=2048 -timeout=2
```

### 2. Eliminasi Undefined Behavior dengan Miri
`Miri` adalah interpreter yang mengeksekusi Rust Mid-level Intermediate Representation (MIR). Miri mendeteksi:
*   Pelanggaran model aliasing (*Stacked Borrows* / *Tree Borrows*).
*   Akses memori yang melampaui batas (*Out-of-bounds pointer arithmetic*).
*   Penggunaan memori yang telah di-deallokasi (*Use-After-Free*).
*   Inisialisasi memori yang tidak valid (misalnya membuat instance `bool` dengan nilai byte `3`).

Jalankan pengujian menggunakan interpreter Miri:
```bash
rustup component add miri
cargo miri test
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Panduan Menghasilkan Profil CPU Menggunakan Flamegraph
Flamegraph memetakan jejak stack trace CPU, di mana sumbu X menunjukkan persentase waktu eksekusi yang dihabiskan pada setiap frame fungsi, dan sumbu Y menunjukkan kedalaman tumpukan pemanggilan (*stack depth*).

```bash
# 1. Pastikan perf (Linux) atau DTrace (macOS) dan cargo-flamegraph terpasang
cargo install cargo-flamegraph

# 2. Bangun binary benchmark/aplikasi dengan simbol debug pada optimasi rilis
# Flag: RUSTFLAGS="-C force-frame-pointers=yes" menjamin stack unwinding akurat
RUSTFLAGS="-C force-frame-pointers=yes" cargo flamegraph --bench engine_bench -- --bench
```
Hasil visualisasi interaktif disimpan ke dalam file format vektor: `flamegraph.svg`.

### 2. Profiling Alokasi Heap Menggunakan DHAT (*Dynamic Heap Analysis Tool*)
DHAT mengidentifikasi titik alokasi yang menyebabkan *memory bloat* dan mengukur durasi hidup memori heap.

```rust
// src/bin/dhat_profile.rs
#[cfg(feature = "dhat-heap")]
#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

fn main() {
    #[cfg(feature = "dhat-heap")]
    let _profiler = dhat::Profiler::new_heap();

    // Jalankan beban kerja intensif
    let mut storage = Vec::new();
    for i in 0..100_000 {
        storage.push(Box::new(i));
    }

    // Profiler mencetak laporan statistik alokasi saat di-drop di akhir main scope
}
```

Jalankan dengan perintah:
```bash
cargo run --release --features dhat-heap
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Kompilasi Perintah Penting (*Command Line Cheatsheet*)

| Operasi | Perintah Cargo | Fungsi & Konteks Penggunaan |
| :--- | :--- | :--- |
| **Benchmarking** | `cargo bench` | Menjalankan seluruh harness benchmarking Criterion |
| **Coverage Testing** | `cargo llvm-cov --html` | Menghasilkan laporan baris cakupan kode dalam format HTML |
| **Flamegraph** | `cargo flamegraph --bin app` | Membuat diagram profil konsumsi CPU berbasis interupsi |
| **Miri Verification** | `cargo miri test` | Menjalankan suite pengujian di bawah interpreter pendeteksi UB |
| **Assembly Inspection** | `cargo asm crate::module::func` | Menginspeksi instruksi mesin LLVM/ASM akhir yang dihasilkan |

### 2. Matriks Keputusan Optimasi Kode

```
               Apakah Latensi Kode Anda Melebihi Batas SLA?
                                    |
                                    v
                    Jalankan Profiler (Flamegraph / DHAT)
                                    |
        +---------------------------+---------------------------+
        |                                                       |
Bottleneck: CPU Time                                    Bottleneck: Memory Allocation
        |                                                       |
        v                                                       v
- Apakah loop di-inlining?                             - Ganti format!/String dengan Stack String
- Gunakan Chunks/SIMD Unrolling                        - Gunakan Vec::with_capacity
- Hindari Dynamic Dispatch (Box<dyn T>)                - Ganti Box individual dengan Arena (bumpalo)
- Transformasi AoS -> SoA                              - Gunakan SmallVec untuk buffer berukuran kecil
- Set codegen-units = 1 & lto = "thin"                 - Parsing byte-level in-place (&[u8])
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian 1: Soal Konsep Dasar (5 Soal)

#### Soal 1
Mengapa penggunaan `std::hint::black_box` sangat krusial di dalam loop iterasi benchmarking Criterion?
*   A. Untuk menghentikan proses eksekusi thread lain di sistem operasi.
*   B. Untuk memaksa alokasi memori heap pada variabel benchmark.
*   C. Untuk mencegah kompilator LLVM mengoptimasi atau menghilangkan komputasi melalui *Dead Code Elimination*.
*   D. Untuk mengonversi semua komputasi floating-point menjadi integer.

#### Soal 2
Perilaku standar pengujian unit bawaan Cargo (`libtest`) saat menjalankan pengujian adalah:
*   A. Menjalankan setiap fungsi tes secara berurutan dalam satu thread utama.
*   B. Mengeksekusi tes secara paralel di beberapa thread terpisah.
*   C. Menghentikan seluruh proses tes jika satu tes mengalami kegagalan.
*   D. Memeriksa ketiadaan undefined behavior secara langsung melalui Miri.

#### Soal 3
Apa keunggulan struktural utama pendekatan *Property-Based Testing* (`proptest`) dibandingkan *Unit Testing* konvensional?
*   A. Menjamin binary hasil kompilasi menjadi lebih kecil.
*   B. Mengeksplorasi ribuan kombinasi input otomatis dan memperkecil input gagal (*shrinking*) secara deterministik.
*   C. Menghilangkan kebutuhan untuk menulis modul pengujian integrasi terpisah.
*   D. Mempercepat waktu kompilasi kode pengujian.

#### Soal 4
Apa perbedaan mendasar antara alokasi memori berorientasi **Array of Structures (AoS)** versus **Structure of Arrays (SoA)** terhadap performa CPU?
*   A. AoS selalu memakan memori lebih sedikit dibanding SoA.
*   B. SoA memaksimalkan penggunaan *cache-line* CPU ketika komputasi hanya mengakses subset field tertentu dari banyak entitas.
*   C. SoA mempermudah pemanggilan fungsi via pointer dinamis.
*   D. AoS mengaktifkan otomatisasi SIMD vektor pada semua arsitektur.

#### Soal 5
Konfigurasi Cargo `panic = "abort"` pada profil rilis memberikan optimasi kinerja karena:
*   A. Mencegah seluruh kemungkinan terjadinya panic di dalam kode sumber.
*   B. Menghapus tabel data penanganan *unwinding stack*, mereduksi ukuran binary dan menyederhanakan kode assembly.
*   C. Mengubah alokasi heap menjadi stack secara otomatis.
*   D. Mengabaikan komputasi invariant matematika yang salah.

---

### Bagian 2: Skenario & Analisis Kasus (5 Soal)

#### Soal 6
Perhatikan potongan kode berikut:
```rust
pub fn parse_pair(input: &str) -> Option<(u32, u32)> {
    let parts: Vec<&str> = input.split(':').collect();
    if parts.len() == 2 {
        let a = parts[0].parse().ok()?;
        let b = parts[1].parse().ok()?;
        Some((a, b))
    } else {
        None
    }
}
```
Jika fungsi ini dipanggil 10.000.000 kali per detik di hot path, apa penyebab utama penurunan performa CPU?
*   A. Penggunaan tipe data pengembalian `Option`.
*   B. Penggunaan operator `?` yang memicu unwinding.
*   C. Alokasi dynamic memory heap pada setiap pemanggilan akibat `.collect::<Vec<_>>()`.
*   D. Percabangan `if parts.len() == 2` memicu branch misprediction tak terhindarkan.

#### Soal 7
Sebuah fungsi benchmark menghasilkan metrik waktu eksekusi yang identik: `1.2 ns` terlepas dari apakah ukuran array input yang diproses berukuran 10 elemen atau 1.000.000 elemen. Apa diagnosa paling logis dari fenomena ini?
*   A. Arsitektur CPU sangat cepat sehingga mampu memproses 1 juta elemen dalam 1.2 ns.
*   B. Kompilator mendeteksi hasil operasi tidak pernah digunakan dan mengeliminasi seluruh komputasi melalui DCE.
*   C. Criterion mengalami deadlock interupsi thread.
*   D. RAM komputer beroperasi pada kecepatan bus cache L1.

#### Soal 8
Anda menjalankan `cargo miri test` pada modul unsafe Rust dan mendapatkan pesan error:
`Memory access failed: attempting to write through dangling pointer`.
Langkah korektif apa yang wajib diambil?
*   A. Menambahkan `#[inline(always)]` pada fungsi tersebut.
*   B. Menghapus seluruh blok `unsafe` dan menggantinya dengan `std::mem::transmute`.
*   C. Memperbaiki siklus hidup alokasi pointer agar tidak mengakses memori yang sudah di-drop / dialokasikan ulang.
*   D. Menambahkan `std::hint::black_box` di sekitar pointer.

#### Soal 9
Kapan teknik **Profile-Guided Optimization (PGO)** memberikan dampak performa yang paling signifikan?
*   A. Pada kode yang didominasi oleh operasi I/O network blocking murni.
*   B. Pada aplikasi dengan alur cabang logika (*branching*) kompleks yang memiliki jalur eksekusi dominan (*hot paths*) yang stabil.
*   C. Pada aplikasi statis tanpa ekspresi algoritma perulangan.
*   D. Pada kode yang dikompilasi menggunakan target arsitektur WebAssembly murni.

#### Soal 10
Mengapa pengujian properti (*property testing*) pada sistem enkripsi atau serialisasi sering menggunakan teknik pengujian *round-trip*?
*   A. Untuk memverifikasi invarian aksiomatik bahwa `f_inverse(f(x)) == x` untuk setiap input acak yang valid.
*   B. Karena kompilator Rust mewajibkan setiap trait mengimplementasikan operasi dua arah.
*   C. Untuk mencegah pemanggilan rekursif tak berhingga pada stack memory.
*   D. Demi memenuhi kepatuhan sanitasi kebocoran memori AddressSanitizer.

---

### Kunci Jawaban & Pembahasan Evaluasi

1.  **Jawaban: C** — `black_box` menyisipkan *inline assembly barrier* yang memaksa kompilator memperlakukan variabel seolah-olah dibaca/ditulis secara eksternal, mencegah *Dead Code Elimination*.
2.  **Jawaban: B** — Runner bawaan mengeksekusi tes secara paralel multi-thread secara default sesuai kapasitas core CPU.
3.  **Jawaban: B** — `proptest` memvalidasi ruang invarian dengan generator pseudorandom dan melakukan *shrinking* otomatis untuk menemukan input kegagalan terkecil.
4.  **Jawaban: B** — SoA menyusun field sejenis secara kontinu, menjamin tidak ada byte tidak relevan yang ikut ditarik ke dalam L1/L2 cache line.
5.  **Jawaban: B** — `panic = "abort"` meniadakan overhead landing pads dan metadata tabel unwinding unwinding stack, menghasilkan binary lebih ramping dan eksekusi lebih efisien.
6.  **Jawaban: C** — `.collect()` mengalokasikan memori baru di heap pada setiap pemanggilan, menyebabkan heap thrashing masif pada iterasi tinggi. Refaktorisasi dengan iterator langsung mengeliminasi masalah ini.
7.  **Jawaban: B** — Jika durasi tetap flat pada skala 1 ns terlepas dari volume data, fungsi tersebut dioptimasi habis (dihapus) oleh optimizer LLVM karena nilainya tidak dibaca.
8.  **Jawaban: C** — Error tersebut menandakan adanya Use-After-Free atau alokasi yang telah mati; pointer harus dipastikan merujuk ke blok memori yang masih aktif dan valid.
9.  **Jawaban: B** — PGO mengoptimalkan penempatan basic blocks dan prediksi percabangan berdasarkan profil eksekusi nyata pada hot paths.
10. **Jawaban: A** — Pengujian round-trip adalah cara paling ampuh membuktikan simetri operasional data tanpa perlu menulis ratusan fixture data statis secara manual.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Mini Project: *High-Performance Zero-Allocation Metrics Aggregator*

Anda ditugaskan merancang modul mesin penagregasi metrik telemetri server jaringan (*Network Metric Telemetry Engine*). Modul ini harus mampu memproses jutaan string log metrik per detik tanpa menyebabkan alokasi heap baru setelah fase inisialisasi.

### Spesifikasi Teknis yang Wajib Dipenuhi

1.  **Parsing & Validasi Format**:
    *   Menerima baris input berformat: `"<timestamp_u64>,<node_id_u16>,<latency_us_u32>,<status_code_u16>"`.
    *   Contoh data: `"1700000000,101,450,200"`.
    *   Tidak boleh ada satupun pemanggilan alokator (`format!`, `Vec::push`, `String::new`, dll) di dalam loop pemrosesan baris.
2.  **Struktur Data & Agregasi**:
    *   Gunakan struktur data padat berorientasi cache (*aligned*).
    *   Fungsi agregator harus menghitung: total transaksi, jumlah status error ($kode \ge 400$), rata-rata latensi, dan latensi maksimum.
3.  **Suite Pengujian Komprehensif**:
    *   Minimal 5 *Unit Tests* yang memvalidasi kasus batas (string kosong, angka cacat, delimiter salah, integer overflow).
    *   Satu pengujian berbasis properti (*Property Test* via `proptest`) yang memverifikasi bahwa `rata-rata latensi` tidak pernah melebihi `latensi maksimum`.
4.  **Tolok Ukur Performa (Criterion)**:
    *   Buat harness benchmark di folder `benches/metric_bench.rs` yang menguji performa pemrosesan batch minimal $10.000$ baris data.
    *   Target SLA Kinerja: Batch 10.000 log harus diproses dalam waktu di bawah $1.5 \text{ milidetik}$ pada CPU modern standar ($> 6.500.000\text{ log/detik}$).
5.  **Verifikasi Sanitasi Memori**:
    *   Uji binary menggunakan `cargo test` dan pastikan seluruh test lolos 100%.
    *   (Opsional/Ekstra) Jalankan `cargo flamegraph` untuk membuktikan bahwa tidak ada bottleneck waktu CPU pada pemanggilan `malloc`/`free`.

### Kerangka Awal Proyek (*Starter Template*)

```rust
// File: src/lib.rs

#[derive(Debug, Default, PartialEq, Eq)]
pub struct AggregatedSummary {
    pub total_records: u64,
    pub error_count: u64,
    pub max_latency: u32,
    pub average_latency: u32,
}

#[derive(Debug, PartialEq, Eq)]
pub enum MetricError {
    InvalidSyntax,
    NumericParseError,
    BufferOverflow,
}

/// Implementasikan fungsi pengolah batch tanpa alokasi heap berikut ini
pub fn process_metrics_batch(raw_logs: &[&str]) -> Result<AggregatedSummary, MetricError> {
    // TULIS IMPLEMENTASI ANDA DI SINI
    todo!()
}
```

Terapkan metodologi pengujian, profiling, dan optimasi yang telah dipelajari dalam modul ini untuk membangun implementasi tercepat, teraman, dan terandal. Buktikan peningkatan performa Anda melalui data benchmark empiris!