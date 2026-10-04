# Bab 01: Fundamental Rust & Arsitektur Toolchain
## Modul 01: Filosofi Safety, Toolchain (rustup/cargo/rustc), dan Program Pertama

---

### 1. Learning Objectives (Tujuan Pembelajaran)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** filosofi rekayasa di balik Rust, terutama eliminasi *Undefined Behavior* tanpa ketergantungan pada *Garbage Collector* (GC).
- **Mengonfigurasi** dan mengelola siklus hidup *toolchain* Rust secara mandiri menggunakan `rustup`, `cargo`, dan `rustc`.
- **Mengidentifikasi** tahapan *compilation pipeline* Rust dari kode sumber hingga *machine code* (AST, HIR, MIR, LLVM IR).
- **Mengimplementasikan** program CLI idiomatik pertama yang menerapkan struktur proyek modular, *type safety*, dan penanganan galat (*error handling*) dasar.
- **Mengonfigurasi** profil kompilasi (*dev* vs *release*) serta mengukur implikasinya terhadap performa biner dan ukuran *footprint*.

---

### 2. Concept Overview (Gambaran Konsep)

Rust adalah bahasa pemrograman sistem yang dirancang untuk memecahkan dikotomi klasik rekayasa perangkat lunak: pilihan antara performa tingkat rendah dengan manipulasi memori langsung (C/C++) atau keamanan memori berbasis *managed runtime* dengan beban komputasi tambahan (Java, Go, C#). 

Rust mencapai tujuan ini melalui kombinasi tiga pilar arsitektur:
1. **Safety without Garbage Collection:** Menegakkan invarian keamanan memori (*memory safety*) dan konkurensi (*data-race freedom*) sepenuhnya pada waktu kompilasi (*compile-time*) via *Affine Type System* dan *Borrow Checker*.
2. **Zero-Cost Abstractions:** Memastikan bahwa abstraksi tingkat tinggi (seperti iterator, penutupan/closures, dan polimorfisme statis) dikompilasi menjadi representasi instruksi mesin yang setara atau lebih efisien daripada kode imperatif manual tingkat rendah.
3. **First-Class Tooling:** Mengintegrasikan manajemen dependensi, sistem kompilasi, *linter*, dan pengujian unit ke dalam satu standar ekosistem tunggal (`cargo`).

---

### 3. Why It Matters (Latar Belakang Masalah)

Dalam perangkat lunak sistem, kerentanan keamanan kritis secara historis didominasi oleh galat manajemen memori. Laporan keamanan dari vendor besar seperti Microsoft dan Google Chromium secara konsisten menunjukkan bahwa sekitar **70% dari seluruh kerentanan kritis (CVE)** disebabkan oleh *memory safety bugs*, di antaranya:
- *Use-after-free*
- *Double-free*
- *Buffer overflow / Out-of-bounds access*
- *Null pointer dereference*
- *Data races* dalam konkurensi *multithreaded*

Pendekatan konvensional untuk mencegah galat ini adalah menggunakan *Garbage Collector* (GC). Namun, GC memperkenalkan jeda waktu eksekusi non-deterministik (*stop-the-world pauses*), konsumsi memori dasar (*baseline overhead*) yang besar, dan ketidakmampuan untuk berjalan pada lingkungan *bare-metal* atau *hard real-time*. 

Rust hadir untuk memberikan jaminan keamanan absolut terhadap seluruh kelas *bug* tersebut tanpa mengorbankan kendali deterministik atas perangkat keras dan alokasi memori.

---

### 4. What It Is (Definisi Teknis & Arsitektur)

Ekosistem inti Rust dibangun di atas kumpulan komponen perangkat lunak terintegrasi:

```
+-----------------------------------------------------------------------+
|                           RUST ECOSYSTEM                              |
+-----------------------------------------------------------------------+
|  +--------------------+  Manages   +-------------------------------+  |
|  |       rustup       | ---------> | Toolchains (stable/beta/night)|  |
|  +--------------------+            +-------------------------------+  |
|            |                                                          |
|            v Drives                                                   |
|  +--------------------+  Invokes   +-------------------------------+  |
|  |       cargo        | ---------> | rustc (Compiler Frontend)     |  |
|  | (Build & Packages) |            +-------------------------------+  |
|  +--------------------+                            |                  |
|                                                    v Emits            |
|                                    +-------------------------------+  |
|                                    | LLVM (Compiler Backend)       |  |
|                                    +-------------------------------+  |
|                                                    |                  |
|                                                    v Generates        |
|                                    +-------------------------------+  |
|                                    | Native Binary / Assembly      |  |
|                                    +-------------------------------+  |
+-----------------------------------------------------------------------+
```

- **`rustup`**: Manajer *toolchain* dan *multiplexer*. Bertugas mengunduh, memperbarui, dan mengisolasi versi kompilator Rust (*stable*, *beta*, *nightly*), serta pustaka standar untuk target *cross-compilation*.
- **`cargo`**: Manajer paket (*package manager*) dan sistem orkestrasi *build*. Mengelola pengunduhan pustaka (*crates*), kompilasi dependensi, eksekusi tes terotomatisasi, *benchmarking*, dan dokumentasi.
- **`rustc`**: Kompilator utama. Mengonversi teks kode sumber Rust menjadi representasi perantara internal hingga akhirnya menghasilkan representasi LLVM IR.
- **LLVM**: *Backend* kompilator industri yang bertanggung jawab atas analisis optimasi instruksi mesin tingkat rendah (*vectorization*, *inlining*, *dead-code elimination*) dan menghasilkan kode mesin target (ELF, Mach-O, PE).

---

### 5. How It Works (Mekanisme Internal & Alur Eksekusi)

Proses transformasi dari berkas `.rs` hingga biner yang dapat dieksekusi melalui beberapa tahapan validasi yang ketat:

1. **Parsing & Macro Expansion:** Mengubah karakter mentah kode menjadi *Abstract Syntax Tree* (AST). Pada tahap ini, ekspansi makro deklaratif (`macro_rules!`) dan prosedural dieksekusi.
2. **Name Resolution & Type Checking:** Memvalidasi keberadaan simbol, cakupan modul (*scope*), dan inferensi tipe data awal. Menghasilkan *High-Level Intermediate Representation* (HIR).
3. **Borrow Checking (NLL - Non-Lexical Lifetimes):** HIR dikonversi menjadi *Mid-Level Intermediate Representation* (MIR). MIR merepresentasikan alur kendali (*Control Flow Graph* / CFG). Di sinilah analisis kepemilikan (*ownership*), masa hidup (*lifetimes*), dan mutabilitas dievaluasi secara matematis. Jika terjadi konflik pinjaman (*borrow conflict*), kompilasi digagalkan di sini.
4. **Monomorphization:** Kode generik (*generics*) digandakan dan dikonversi menjadi implementasi konkret spesifik untuk setiap tipe yang digunakan, menghilangkan *runtime dynamic dispatch overhead*.
5. **LLVM Codegen:** MIR diterjemahkan ke dalam *LLVM Intermediate Representation* (LLVM IR).
6. **Optimizations & Machine Code Generation:** LLVM menjalankan *passes* optimasi sesuai profil (O0 hingga O3, LTO), kemudian *assembler* dan *linker* mengikat dependensi statis/dinamis untuk menghasilkan berkas biner final.

---

### 6. ASCII Diagram: Compilation Pipeline

```
 Source Code (*.rs)
        |
        v
+------------------+
| Lexer & Parser   |
+------------------+
        |
        v
       AST (Abstract Syntax Tree)
        |
        v
+------------------+
| Expansion &      | <-- Macro expansion, conditional compilation (#[cfg])
| Early Resolution |
+------------------+
        |
        v
       HIR (High-Level Intermediate Representation)
        |
        v
+------------------+
| Type Inference & |
| Trait Solving    |
+------------------+
        |
        v
       MIR (Mid-Level Intermediate Representation)
        |
  [ BORROW CHECK ]  <-- Validasi Ownership, Lifetimes, Mutability
        |
        v
+------------------+
| Monomorphization | <-- Polimorfisme statis diubah menjadi tipe konkret
+------------------+
        |
        v
     LLVM IR
        |
        v
+------------------+
| LLVM Optimizer   | <-- Dead code elimination, Loop unrolling, Vectorization
| & Code Generator |
+------------------+
        |
        v
Target Native Binary (x86_64, AArch64, RISC-V, WASM)
```

---

### 7. Simple Code Example (Contoh Kode Fundamental)

Berikut adalah struktur kode dasar Rust yang mendemonstrasikan fungsi utama, inferensi tipe eksplisit, penanganan I/O dasar, dan manipulasi memori pada *stack*.

```rust
// File: src/main.rs

use std::io::{self, Write};

fn main() {
    // Immutability secara default
    let application_name: &'static str = "Engine Telemetry";
    let version: (u8, u8, u8) = (0, 1, 0);

    // Mutabilitas harus dinyatakan secara eksplisit via `mut`
    let mut execution_count: u32 = 0;

    println!("=== {} v{}.{}.{} ===", 
        application_name, version.0, version.1, version.2
    );

    print!("Masukkan identitas operator: ");
    // Flush stdout agar prompt muncul sebelum membaca stdin
    io::stdout().flush().expect("Gagal melakukan flush pada stdout");

    let mut operator_input = String::new();
    
    // Penanganan error eksplisit menggunakan match pada Result enum
    match io::stdin().read_line(&mut operator_input) {
        Ok(bytes_read) => {
            let sanitized_operator = operator_input.trim();
            execution_count += 1;
            
            println!(
                "Operator aktif: '{}' (Input size: {} bytes, Exec ID: {})", 
                sanitized_operator, bytes_read, execution_count
            );
        }
        Err(error) => {
            eprintln!("Kesalahan fatal saat membaca STDIN: {error}");
            std::process::exit(1);
        }
    }
}
```

---

### 8. Detailed Code Walkthrough (Analisis Baris per Baris Kode Sederhana)

- **`use std::io::{self, Write};`**: Mengimpor modul `io` dari pustaka standar (`std`) serta *trait* `Write` ke dalam cakupan lokal. *Trait* `Write` diperlukan agar metode `.flush()` dapat dipanggil pada instans `Stdout`.
- **`fn main()`**: Titik masuk (*entry point*) dari setiap program biner Rust. Fungsi ini tidak mengembalikan nilai secara eksplisit (mengembalikan unit type `()`).
- **`let application_name: &'static str = "Engine Telemetry";`**: Deklarasi variabel *immutable* (tidak dapat diubah). Tipe datanya adalah *string slice* yang dialokasikan di segmen data statis berkas biner (`'static lifetime`).
- **`let mut execution_count: u32 = 0;`**: Di Rust, semua variabel bersifat *immutable* secara *default*. Kata kunci `mut` menginstruksikan kompilator bahwa lokasi memori variabel ini diizinkan untuk dimodifikasi nilainya di kemudian waktu.
- **`io::stdout().flush().expect(...)`**: `stdout` di-buffer secara baris demi baris (*line-buffered*). Pemanggilan `print!` tanpa karakter *newline* (`\n`) menuntut pemanggilan `.flush()` manual agar teks langsung dirender ke terminal. `.expect()` memicu `panic` dan mematikan proses jika operasi I/O gagal.
- **`let mut operator_input = String::new();`**: Mengalokasikan instans `String` kosong baru pada *heap*. `operator_input` memegang *pointer* ke *heap*, panjang (*len*), dan kapasitas (*capacity*) di *stack*.
- **`io::stdin().read_line(&mut operator_input)`**: Membaca *stream* dari terminal ke dalam alokasi `String`. Simbol `&mut` mendefinisikan *mutable reference*—memberi izin fungsi `read_line` untuk mengubah isi *buffer* tanpa memindahkan kepemilikan (*ownership*) dari variabel tersebut.
- **`match ... { Ok(bytes_read) => ..., Err(error) => ... }`**: Pola pencocokan (*pattern matching*) terhadap tipe data `Result<T, E>`. Rust tidak memiliki representasi `null` atau mekanisme eksepsi (*exception handling*) bergaya `try-catch`. Kegagalan operasi direpresentasikan secara aman melalui varian `Result`.

---

### 9. Practical/Production Code Example (Kasus Penggunaan Dunia Nyata)

Program berikut adalah alat pemantau telemetri memori sistem berbasis Linux (membaca pseudo-filesystem `/proc/meminfo`) yang dirancang dengan standar produksi: pemisahan logika struktural, *custom error types*, alokasi memori deterministik, dan *zero unhandled errors*.

```rust
// File: src/main.rs

use std::fs::File;
use std::io::{self, BufRead, BufReader};
use std::path::Path;
use std::fmt;

#[derive(Debug)]
pub enum TelemetryError {
    IoFailure(io::Error),
    InvalidFormat(String),
    MissingField(&'static str),
}

impl fmt::Display for TelemetryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TelemetryError::IoFailure(err) => write!(f, "Sistem I/O gagal: {}", err),
            TelemetryError::InvalidFormat(msg) => write!(f, "Format metrik korup: {}", msg),
            TelemetryError::MissingField(field) => write!(f, "Bidang wajib tidak ditemukan: {}", field),
        }
    }
}

impl std::error::Error for TelemetryError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            TelemetryError::IoFailure(err) => Some(err),
            _ => None,
        }
    }
}

impl From<io::Error> for TelemetryError {
    fn from(err: io::Error) -> Self {
        TelemetryError::IoFailure(err)
    }
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct SystemMemoryMetrics {
    pub total_kb: u64,
    pub free_kb: u64,
    pub available_kb: u64,
    pub buffers_kb: u64,
    pub cached_kb: u64,
}

impl SystemMemoryMetrics {
    pub fn used_kb(&self) -> u64 {
        self.total_kb.saturating_sub(self.available_kb)
    }

    pub fn usage_percentage(&self) -> f64 {
        if self.total_kb == 0 {
            return 0.0;
        }
        (self.used_kb() as f64 / self.total_kb as f64) * 100.0
    }
}

pub struct TelemetryCollector;

impl TelemetryCollector {
    pub fn parse_meminfo<P: AsRef<Path>>(path: P) -> Result<SystemMemoryMetrics, TelemetryError> {
        let file = File::open(path)?;
        let reader = BufReader::new(file);

        let mut metrics = SystemMemoryMetrics::default();
        let mut fields_found: u8 = 0;

        for line_result in reader.lines() {
            let line = line_result?;
            
            if let Some((key, value_str)) = line.split_once(':') {
                let trimmed_key = key.trim();
                let parse_value = || -> Result<u64, TelemetryError> {
                    value_str
                        .split_whitespace()
                        .next()
                        .ok_or_else(|| TelemetryError::InvalidFormat(line.clone()))?
                        .parse::<u64>()
                        .map_err(|_| TelemetryError::InvalidFormat(line.clone()))
                };

                match trimmed_key {
                    "MemTotal" => {
                        metrics.total_kb = parse_value()?;
                        fields_found += 1;
                    }
                    "MemFree" => {
                        metrics.free_kb = parse_value()?;
                        fields_found += 1;
                    }
                    "MemAvailable" => {
                        metrics.available_kb = parse_value()?;
                        fields_found += 1;
                    }
                    "Buffers" => {
                        metrics.buffers_kb = parse_value()?;
                    }
                    "Cached" => {
                        metrics.cached_kb = parse_value()?;
                    }
                    _ => {}
                }
            }

            if fields_found >= 3 {
                break;
            }
        }

        if metrics.total_kb == 0 {
            return Err(TelemetryError::MissingField("MemTotal"));
        }

        Ok(metrics)
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    const MEMINFO_PATH: &str = "/proc/meminfo";

    println!("[INIT] Mengambil telemetri kernel...");

    // Simulasi fallback jika dijalankan di luar platform Linux non-procfs
    if !Path::new(MEMINFO_PATH).exists() {
        eprintln!("[WARN] Sistem target tidak mengekspos {}; telemetri diabaikan.", MEMINFO_PATH);
        return Ok(());
    }

    let metrics = TelemetryCollector::parse_meminfo(MEMINFO_PATH)?;

    println!("--------------------------------------------------");
    println!("Statistik Memori Host:");
    println!("Total Kapasitas: {:>10} KB", metrics.total_kb);
    println!("Tersedia       : {:>10} KB", metrics.available_kb);
    println!("Terpakai       : {:>10} KB ({:.2}%)", metrics.used_kb(), metrics.usage_percentage());
    println!("--------------------------------------------------");

    Ok(())
}
```

---

### 10. Production Code Walkthrough (Analisis Mendalam Kode Produksi)

- **`pub enum TelemetryError`**: Mendefinisikan *domain error* tersendiri menggunakan enum. Ini mengabstraksi kegagalan I/O dan kesalahan *parsing* teks menjadi tipe terpadu yang dapat diprediksi secara ketat.
- **`impl From<io::Error> for TelemetryError`**: Implementasi konversi tipe otomatis. Hal ini memungkinkan operator `?` (early return) untuk langsung mentransformasikan instans `std::io::Error` menjadi `TelemetryError::IoFailure` tanpa memerlukan kode *boilerplate* konversi manual.
- **`pub fn parse_meminfo<P: AsRef<Path>>(path: P)`**: Menggunakan generic dengan *trait bound* `AsRef<Path>`. Pola idiomatik ini memungkinkan fungsi menerima tipe `&str`, `String`, atau `&Path` secara fleksibel tanpa alokasi memori tambahan.
- **`BufReader::new(file)`**: Membungkus berkas dalam *buffer stream*. Membaca baris langsung dari *system call* `read()` mentah berkas dapat memperlambat kinerja sistem akibat *context switching* yang berlebihan; `BufReader` meminimalkan pemanggilan *syscall* kernel melalui *chunk caching* di *heap*.
- **`line.split_once(':')`**: Menghindari alokasi vektor dinamis yang biasanya dipicu oleh pemanggilan fungsi `.split()`. Metode ini hanya mengembalikan tuple opsional dari *string slices* yang langsung meminjam memori dari `line`.
- **`self.total_kb.saturating_sub(...)`**: Mencegah *integer underflow*. Jika representasi nilai sistem menghasilkan inkonsistensi sementara di mana `available_kb` lebih besar dari `total_kb`, operasi matematika ini akan terkunci di angka nol dan tidak memicu *runtime panic*.

---

### 11. Edge Cases & Gotchas (Kasus Batas & Jebakan Pemula)

1. **Unbuffered Output:** Menggunakan makro `print!` tanpa `io::stdout().flush()` dapat menyebabkan terminal tampak macet (*freezing*) karena buffer I/O internal belum mencapai kapasitas *flush* atau belum mendeteksi karakter *newline*.
2. **Debug vs Release Performance:** Kompilasi via `cargo build` secara baku menyematkan metadata debu yang besar dan menonaktifkan optimasi (`opt-level = 0`). Jangan pernah melakukan *benchmarking* atau uji performa pada biner hasil profil `debug`.
3. **Target Triple & libc Linking:** Mengompilasi kode Rust secara *default* akan melakukan *dynamically linking* terhadap `glibc` target sistem host. Mendistribusikan biner ini ke distribusi Linux lain yang memiliki versi `glibc` lebih tua akan memicu galat eksekusi fatal (`version GLIBC_x.xx not found`). Gunakan target musl (`x86_64-unknown-linux-musl`) untuk membuat biner yang benar-benar independen (*fully statically linked*).

---

### 12. Trade-offs & Limitations (Kompromi Arsitektur & Batasan)

| Aspek | Rust | C / C++ | Go |
| :--- | :--- | :--- | :--- |
| **Keamanan Memori** | Statis (Compile-time via Borrow Checker) | Manual (Raw Pointers, Rawan UB) | Dinamis (Managed Garbage Collector) |
| **Kecepatan Kompilasi** | Lambat (Analisis borrow checking & monomorphization) | Cepat hingga Sedang | Sangat Cepat |
| **Runtime Overhead** | Minimum (Zero-cost abstraction, tanpa GC) | Minimum (Beban manual allocation) | Moderat (GC latency, Stack resizing) |
| **Learning Curve** | Curam (Konsep ownership, borrow checker) | Moderat (Sintaks), Tinggi (Safety) | Landai |
| **Binary Determinism** | Deterministik penuh | Deterministik penuh | Non-deterministik (GC background cycles) |

---

### 13. Performance Implications (Analisis Performa)

- **Monomorphization Cost vs Benefit:** Rust mengekspansi tipe generik menjadi kode perakitan spesifik. Implikasinya: kecepatan eksekusi setara dengan kode yang ditulis tangan secara langsung (*direct branch calls*, CPU dapat melakukan *inlining*), namun berdampak pada potensi pembengkakan ukuran berkas biner final (*code bloat*) dan lamanya waktu kompilasi.
- **Link-Time Optimization (LTO):** Melalui konfigurasi `lto = true` di berkas konfigurasi `Cargo.toml`, LLVM dapat melakukan optimasi lintas-modul dan lintas-*crate*, memangkas pemanggilan fungsi redundan hingga mengurangi ukuran biner hingga 20-40%.

---

### 14. Security Considerations (Aspek Keamanan)

- **Eliminasi Undefined Behavior:** Rust membagi dunia menjadi dua domain: *Safe Rust* dan *Unsafe Rust*. Pada *Safe Rust*, mustahil menghasilkan *memory corruption*, *dangling pointer*, atau *data race*.
- **Compiler Panics vs Memory Leak:** Ketika sebuah invarian gagal (misal: *out-of-bounds array access*), Rust akan memicu *unwinding panic* atau *abort*. Program akan berhenti secara terkendali tanpa mengekspos segmen memori yang dapat dieksploitasi oleh penyerang melalui *memory dump*.
- **Supply Chain Security:** Manfaatkan *subcommand* `cargo audit` dalam integrasi CI/CD untuk memindai berkas `Cargo.lock` secara otomatis terhadap kerentanan basis data *RustSec Advisory*.

---

### 15. Antipatterns (Pola Buruk & Solusinya)

#### Antipattern: Menggunakan `.unwrap()` di Lingkungan Produksi
```rust
// BURUK: Menyebabkan panic dan terminasi seketika jika berkas tidak ditemukan
let file = File::open("config.json").unwrap();
```

#### Solusi: Propagasi Galat Terstruktur via Operator `?`
```rust
// BAIK: Mengembalikan error ke konteks pemanggil secara elegan
let file = File::open("config.json")?;
```

---

#### Antipattern: Alokasi String Berlebihan untuk Akses Baca-Saja
```rust
// BURUK: Mengalokasikan heap memory baru padahal hanya membutuhkan akses inspeksi data
fn validate(token: String) -> bool {
    token.len() > 10
}
```

#### Solusi: Gunakan Borrowed Slices
```rust
// BAIK: Zero-allocation, hanya meneruskan pointer dan panjang memori yang ada
fn validate(token: &str) -> bool {
    token.len() > 10
}
```

---

### 16. Best Practices & Guidelines (Panduan Desain & Konvensi)

1. **Gunakan Profil Kompilasi yang Tepat:** Definisikan konfigurasi rilis pada `Cargo.toml` untuk biner produksi:
   ```toml
   [profile.release]
   opt-level = 3
   lto = true
   codegen-units = 1
   panic = "abort"
   strip = true
   ```
2. **Gunakan Linter Secara Rutin:** Jalankan `cargo clippy --all-targets -- -D warnings` sebelum menggabungkan kode baru ke repositori utama. *Clippy* menegakkan idiom penulisan kode Rust yang optimal dan aman.
3. **Format Kode Terstandarisasi:** Gunakan `cargo fmt --check` untuk mematuhi konvensi resmi penulisan arsitektur berkas Rust.

---

### 17. Real-world Case Study (Studi Kasus Dunia Nyata)

**Konteks:** Perusahaan infrastruktur jaringan perlu mengganti *daemon telemetry logger* berbasis Python pada gerbang IoT industri dengan spesifikasi perangkat keras terbatas (128 MB RAM, CPU Single Core ARMv7).

**Masalah:** Program lawas mengalami *memory thrashing* akibat lonjakan siklus *Garbage Collection* Python setiap kali beban lalu lintas jaringan meningkat, yang berujung pada hilangnya paket log metrik kritis (*packet drop*).

**Solusi dengan Rust:**
- Menulis ulang *agent daemon* menggunakan *Safe Rust* murni dengan dependensi minimal.
- Pustaka I/O menggunakan `BufReader` statis dengan ukuran alokasi tetap (*fixed buffer*).
- Kompilasi menggunakan profil *release*, target *cross-compilation* `armv7-unknown-linux-musleabihf`, dengan konfigurasi `panic = "abort"` dan `strip = true`.

**Hasil:** Ukuran biner final turun menjadi 1.8 MB (dari sebelumnya >35 MB bersama *runtime* interpreter). Jejak memori RAM stabil pada tingkat konstan **1.2 MB** tanpa ada fluktuasi *Garbage Collection*, serta risiko hilangnya data tereduksi menjadi 0%.

---

### 18. Verification & Debugging (Verifikasi & Debugging)

Untuk memvalidasi sintaksis, mengompilasi, dan menganalisis biner Rust yang telah dibuat, gunakan panduan perintah berikut:

```bash
# 1. Validasi sintaks dan type-check secepat kilat tanpa menghasilkan biner (efisien selama dev)
cargo check

# 2. Kompilasi profil debug (termasuk symbol debug, tanpa optimasi)
cargo build

# 3. Jalankan linter Clippy dengan penegakan error penuh
cargo clippy -- -D warnings

# 4. Kompilasi untuk kebutuhan pengujian produksi dengan optimasi penuh
cargo build --release

# 5. Menjalankan biner dengan jejak backtrace aktif saat terjadi panic
RUST_BACKTRACE=1 ./target/release/telemetry_app

# 6. Analisis ukuran dan simbol biner menggunakan tool llvm bawaan (opsional)
size ./target/release/telemetry_app
```

---

### 19. Key Takeaways (Rangkuman Inti)

- **Ownership adalah Inti:** Rust menjamin keamanan memori tanpa *Garbage Collector* dengan menerapkan aturan kepemilikan dan peminjaman (*ownership & borrowing*) yang diverifikasi saat kompilasi (*compile-time*).
- **Tooling Terpadu:** `rustup` bertindak sebagai pengelola versi bahasa, sementara `cargo` memfasilitasi pembangunan dependensi, pengujian, dan manajemen proyek dalam satu standar baku.
- **Handling Galat Deterministik:** Tidak ada eksepsi tersembunyi; seluruh galat sistem dipetakan secara terstruktur melalui tipe `Result<T, E>`.
- **Efisien Secara Baku:** Semua variabel dan referensi bersifat *immutable* secara *default*, meminimalkan efek samping (*side effects*) komputasi yang tidak diinginkan.

---

### 20. Challenge Exercises (Latihan Praktik Berjenjang)

#### Level 1: Pemula
Modifikasi program sederhana pada Seksi 7 agar program dapat menghitung jumlah karakter (bukan byte) dan jumlah kata dari teks yang dimasukkan oleh operator sebelum terminasi. Terapkan pemisahan logika ke fungsi mandiri: `fn count_words(input: &str) -> usize`.

#### Level 2: Menengah
Perluas implementasi produksi telemetri pada Seksi 9. Buat fungsi baru yang membaca metrik beban CPU dari pseudo-file `/proc/loadavg`. Ekstrak nilai beban rata-rata sistem (1 menit, 5 menit, dan 15 menit) dan petakan ke dalam struktur data baru:
```rust
pub struct CpuLoadAverage {
    pub one_min: f64,
    pub five_min: f64,
    pub fifteen_min: f64,
}
```
Lengkapi pemetaan ini dengan implementasi *error handling* menggunakan `TelemetryError` yang telah ada.

#### Level 3: Mahir
Rancang sebuah CLI utilitas pengukur waktu eksekusi (*stopwatch micro-benchmarking tool*). Utilitas ini menerima sebuah perintah shell eksternal beserta argumen-argumennya, mengeksekusinya sebagai *child process* menggunakan `std::process::Command`, membaca keluaran *stdout* dan *stderr*-nya secara *asynchronous* atau *buffered*, kemudian mencatat waktu dinding (*wall-clock time*) serta konsumsi memori puncak (*peak resident set size* / RSS) proses tersebut sebelum prosesor terminasi. Laporkan hasilnya dalam format JSON ke *stdout*. Pastikan biner akhir dikompilasi secara *fully static* menggunakan target `musl`.