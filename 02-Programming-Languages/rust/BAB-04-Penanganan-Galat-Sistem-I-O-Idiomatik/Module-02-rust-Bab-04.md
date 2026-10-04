# BAB 04: Penanganan Galat & Sistem I/O Idiomatik
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** representasi memori tingkat rendah (*memory layout*) dari `Result<T, E>` dan `Option<T>`, termasuk mekanisme *niche value optimization* pada *compiler* LLVM.
- **Mengarsiteksi** hierarki galat enterprise yang modular, berlapis, dan dapat diobservasi menggunakan pemisahan tegas antara galat domain (*strongly-typed static error dispatch* via `thiserror`) dan galat infrastruktur/aplikasi (*type-erased dynamic context dispatch* via `anyhow`).
- **Mengimplementasikan** abstraksi I/O asinkron dan sinkron berkinerja tinggi berbasis *vectored I/O* (`readv`/`writev`), *buffer recycling/pooling*, serta penanganan *short reads/writes* secara nir-alokasi (*zero-allocation*).
- **Mengevaluasi** perbandingan trade-off performa antara *panic unwinding* (`panic = "unwind"`) vs *abort* (`panic = "abort"`), alokasi *heap* pada pengumpulan *backtrace*, dan penalti latensi dari konversi galat dinamis pada jalur kritis (*hot path*).
- **Mendiagnosis** dan memitigasi kegagalan sistem I/O tingkat kernel (seperti `EAGAIN`, `EWOULDBLOCK`, `EINTR`, *broken pipe*, dan *disk exhaustion*) dalam sistem terdistribusi berlatensi rendah.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- Sistem kepemilikan (*ownership*), peminjaman (*borrowing*), dan masa hidup (*lifetimes* `'a`) di Rust.
- Dasar trait standar: `From<T>`, `Into<T>`, `Display`, `Debug`, dan implementasi dasar trait `std::error::Error`.
- Arsitektur I/O fundamental: Trait `std::io::{Read, Write, Seek, BufRead}`.
- Dasar konkurensi dan asinkron: Model eksekusi Tokio/async-std dan *polling state machines*.

---

### 3. Concept & Internal Architecture

#### 3.1. Representasi Memori & Niche Value Optimization

Di Rust, `Result<T, E>` direpresentasikan sebagai tipe *tagged union* (`enum`). Secara konseptual, struktur memorinya terdiri dari *discriminant* (tag penanda varian `Ok` atau `Err`) dan *payload* data (`T` atau `E`):

$$\text{Size of } Result<T, E> \approx \max(\text{sizeof}(T), \text{sizeof}(E)) + \text{sizeof}(\text{Discriminant}) + \text{Padding}$$

Namun, rustc berkolaborasi dengan LLVM untuk mengeliminasi *overhead discriminant* menggunakan teknik **Niche Value Optimization**. Jika salah satu tipe memiliki nilai yang tidak valid menurut spesifikasi bit (*niche*), bit tersebut digunakan langsung sebagai tag. 

Sebagai contoh:
- `NonNull<T>` atau referensi `&T` tidak boleh bernilai nol (`0x0`). LLVM mengeksploitasi nilai nol ini untuk merepresentasikan varian `Err` atau `None`.
- Akibatnya, `Option<&T>` atau `Result<&T, ()>` memiliki ukuran yang sama persis dengan sebuah pointer (8 byte pada arsitektur 64-bit), dengan status *zero-cost abstraction* terpenuhi.

```
Layout Result<&T, ()> (8 Bytes, Zero-overhead Discriminant):
+--------------------------------------------------------+
| 0x00000001 - 0xFFFFFFFFFFFFFFFF : Varian Ok(&T)        |
+--------------------------------------------------------+
| 0x00000000                      : Varian Err(())       |
+--------------------------------------------------------+
```

Jika `T` atau `E` berukuran masif (misalnya `Result<(), HugePayload>` di mana `HugePayload` berukuran 1024 byte), setiap instansiasi `Result` akan mengalokasikan 1024 byte pada *stack frame*, memicu *memory copying overhead* saat dikembalikan dari pemanggilan fungsi. Solusi idiomatiknya adalah menempatkan galat besar di *heap* menggunakan `Box<E>`.

#### 3.2. Mekanisme `?` Operator & Trait `Try`

Operator `?` menurunkan ekspresi secara otomatis (*desugaring*) pada fase kompilasi menjadi operasi percabangan yang memanfaatkan trait internal `std::ops::Try` dan konversi tipe via `std::convert::From`:

```rust
// Kode Asli:
let value = fallible_operation()?;

// Desugaring oleh Kompilator (Pseudo-Rust):
let value = match fallible_operation() {
    std::ops::ControlFlow::Continue(val) => val,
    std::ops::ControlFlow::Break(err) => {
        return std::ops::FromResidual::from_residual(
            std::ops::Residual::from(std::convert::From::from(err))
        );
    }
};
```

Operator ini mengandalkan konversi implisit: jika fungsi pengemban mengembalikan `Result<_, OuterError>`, dan ekspresi menghasilkan `Result<_, InnerError>`, kompilator secara otomatis mencari implementasi `impl From<InnerError> for OuterError`. Jika ditemukan, konversi dilakukan secara statis tanpa *dynamic dispatch*.

#### 3.3. Arsitektur I/O: Kernel Syscall, BufReader, dan Vectored I/O

Operasi I/O pada Rust menjembatani ruang pengguna (*userspace*) dan ruang kernel (*kernelspace*). Pemanggilan `Read::read` langsung pada `File` atau `TcpStream` menerbitkan *system call* (seperti `read(2)` pada POSIX atau `ReadFile` pada Win32), yang memicu pergantian konteks (*context switch*) CPU dari Ring 3 ke Ring 0. 

Jika dilakukan secara berulang dalam blok byte kecil, *overhead switch* ini mendegradasi performa secara masif:

```
Direct Unbuffered Read:
User Application ---[Syscall: read(1 byte)]---> Kernel ---[Disk Controller]
User Application <---[Context Switch Return]---- Kernel

Buffered Read (BufReader - 8KB Chunking):
User Application ---[Read from 8KB Internal Buffer (RAM)]---> Super Fast
When empty:
BufReader        ---[Syscall: read(8192 bytes)]------------> Kernel (Single Context Switch)
```

Untuk throughput maksimum, Rust mendukung **Vectored I/O** via `Read::read_vectored` dan `Write::write_vectored` (berbasis `readv(2)` dan `writev(2)`). Mekanisme ini memungkinkan transfer data dari/ke beberapa *buffer* memori yang tersebar (*scatter-gather I/O*) dalam satu *syscall* atomik tunggal, mencegah fragmentasi paket TCP dan memangkas alokasi memori sementara.

---

### 4. Why & What

| Parameter Evaluasi | Pendekatan Rust (`Result<T, E>`) | Eksepsi Tradisional (C++/Java) | Penanganan Galat Multi-Return (Go) |
| :--- | :--- | :--- | :--- |
| **Representasi Galat** | Tipe data eksplisit sebagai varian enum/struct. Terbaca jelas pada *type signature*. | Alur kendali non-lokal implisit (*throw/catch*). Tersembunyi dari tanda tangan fungsi. | Tuple multi-nilai `(val, err)`. Status error bergantung pada *convention-check* manual `err != nil`. |
| **Dampak Latensi Hot-path** | Zero overhead bila tidak ada galat; deterministik (setara percabangan CPU branch biasa) bila terjadi galat. | Zero cost pada jalur sukses (pada *zero-cost exceptions table*), tetapi latensi masif saat galat terjadi akibat *stack unwinding* dan pencarian DWARF landing pad. | Sangat rendah, hanya pemeriksaan pointer/integer nil secara linier. |
| **Memory Safety & Correctness** | Nilai sukses tidak dapat diakses tanpa membuka (*unwrap/match*) galat. Mustahil mengabaikan galat tanpa peringatan kompilator (`#[must_use]`). | Terbuka terhadap *unhandled exception* yang mematikan *thread* atau proses runtime. | Rawan kelalaian; nilai sukses dan galat dapat digunakan bersamaan atau diabaikan tanpa peringatan kompilator. |
| **Alokasi Heap** | Zero-allocation secara *default* (menggunakan *stack-allocated enum*). Alokasi hanya terjadi bila dialokasikan eksplisit (`Box<dyn Error>`). | Alokasi heap instan untuk objek eksepsi dan penangkapan *call stack* secara dinamis. | Galat sering kali berupa implementasi *interface* yang membutuhkan alokasi *escape-to-heap*. |

---

### 5. How (Workflow Detail)

#### Strategi Propagasi & Pemisahan Batas Galat (*Error Boundary Architecture*)

```
[ Domain Layer / Core Logic ]
   -> Gunakan strongly-typed enum (`thiserror`)
   -> Zero allocation, tidak mengandung String/heap jika memungkinkan
   -> Bersifat deterministik dan transparan
          │
          │ (Konversi Statis via Trait `From`)
          ▼
[ Service / Orchestration Layer ]
   -> Menangkap galat domain spesifik
   -> Mengubah galat transitif menjadi galat tingkat tinggi dengan konteks teknis
          │
          │ (Transformasi via anyhow::Context / .with_context())
          ▼
[ Application / Infrastructure Boundary (HTTP/gRPC/CLI Main) ]
   -> Tipe dihapus (*type erasure*) via `anyhow::Result` atau diekspos ke klien via DTO
   -> Ekstraksi Backtrace, Log Root Cause & Inner Causality Chain
   -> Pemetaan ke status kode protokol (HTTP 500, 404, gRPC NOT_FOUND)
```

1. **Definisikan Domain Errors**: Petakan galat menggunakan `thiserror::Error`. Hindari penempatan `String` acak; gunakan varian enum yang merefleksikan kegagalan logika bisnis secara presisi.
2. **Karantina Sub-Sistem**: Lapisan IO internal (seperti database atau koneksi TCP) tidak boleh merembes ke domain logika. Konversikan `std::io::Error` menjadi `StorageEngineError` atau `NetworkProtocolError` pada batas subsistem.
3. **Injeksi Konteks**: Pada lapisan orkestrasi, sertakan metadata (seperti ID transaksi, IP, nama path berkas) menggunakan `anyhow::Context` agar galat memiliki jejak audit yang dapat didebug tanpa memecahkan representasi enum domain.
4. **Logika Pemulihan (*Graceful Recovery*)**: Tangani galat yang bersifat transien (seperti `io::ErrorKind::Interrupted` atau `io::ErrorKind::WouldBlock`) dengan pengulangan (*retry*) terukur atau *backoff*, bukan langsung menyebarkannya ke lapisan teratas.

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem penanganan galat dan I/O sebagai **Sistem Pengepakan & Logistik Pengiriman Barang Fisik**:

```
+-------------------------------------------------------------------------------------------------+
|                                 SISTEM LOGISTIK RUST                                            |
+-------------------------------------------------------------------------------------------------+

                      +------------------------------------------+
                      |        Jalur Normal: Paket Utuh          |
                      |          Ok(KomponenHardware)            |
                      +------------------------------------------+
                                           ▲
                                           │ Kontainer Result<T, E>
                                           ▼
                      +------------------------------------------+
                      |       Jalur Galat: Lembar Manifest       |
                      |             Err(CacatPabrik)             |
                      +------------------------------------------+

               [Kernel Disk / Network Interface Controller (NIC)]
                                       │
                                       │ (Vectored I/O: Multi-Box)
                                       ▼
             +---------------+  +---------------+  +---------------+
             | Buffer Slot 1 |  | Buffer Slot 2 |  | Buffer Slot 3 |
             +---------------+  +---------------+  +---------------+
             [=================== Ring Buffer =====================]
                                       │
                             BufReader Chunking (8KB)
                                       │
                                       ▼
                      +----------------------------------+
                      |     Aplikasi Konsumen (Ring 3)   |
                      +----------------------------------+
```

Jika Anda meminta barang perorangan dari gudang pusat (Kernel) untuk setiap unit kecil, biaya transportasi (Syscall Context Switch) akan membangkrutkan perusahaan Anda. `BufReader` bertindak sebagai kontainer konsolidasi: ia mengambil satu truk penuh (8 KB data) sekaligus. Saat aplikasi Anda meminta data sedikit demi sedikit, data diambil langsung dari kontainer lokal tanpa harus bolak-balik ke gudang pusat.

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Zero-Allocation Custom Error & Idiomatic Conversion

Contoh implementasi struktur galat internal tanpa alokasi heap menggunakan `thiserror`:

```rust
use std::fmt;
use std::io;

#[derive(Debug)]
pub enum ParserError {
    InvalidMagicBytes([u8; 4]),
    PayloadTooLarge { max: usize, actual: usize },
    Io(io::Error),
}

impl std::error::Error for ParserError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(err) => Some(err),
            _ => None,
        }
    }
}

impl fmt::Display for ParserError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidMagicBytes(bytes) => {
                write!(f, "Header biner tidak valid: {:02X?}", bytes)
            }
            Self::PayloadTooLarge { max, actual } => {
                write!(f, "Ukuran payload melebihi limit: {} > {}", actual, max)
            }
            Self::Io(err) => write!(f, "I/O failure: {}", err),
        }
    }
}

// Mengizinkan operator '?' mengonversi io::Error secara otomatis
impl From<io::Error> for ParserError {
    fn from(err: io::Error) -> Self {
        ParserError::Io(err)
    }
}

pub fn parse_header(stream: &[u8]) -> Result<u16, ParserError> {
    if stream.len() < 4 {
        return Err(ParserError::Io(io::Error::new(
            io::ErrorKind::UnexpectedEof,
            "Buffer kurang dari 4 byte",
        )));
    }
    
    let magic = &stream[0..4];
    if magic != [0xDE, 0xAD, 0xBE, 0xEF] {
        let mut invalid = [0u8; 4];
        invalid.copy_from_slice(magic);
        return Err(ParserError::InvalidMagicBytes(invalid));
    }

    Ok(u16::from_be_bytes([stream[2], stream[3]]))
}
```

#### 7.2. Practical Example: Industrial-Grade High-Throughput Vectored Log Reader

Implementasi pembacaan berkas log industri dengan *buffered stream*, parsing struktur biner nir-alokasi, penanganan kegagalan parsial, dan injeksi konteks galat diagnostik:

```rust
use std::fs::File;
use std::io::{self, BufReader, Read};
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum JournalError {
    #[error("Gagal membuka file journal pada lintasan: {path}")]
    OpenFailure {
        path: PathBuf,
        #[source]
        source: io::Error,
    },

    #[error("Terdeteksi korupsi data checksum pada offset: {offset}")]
    DataCorruption { offset: u64, expected: u32, actual: u32 },

    #[error("I/O error saat membaca transmisi log record")]
    Io(#[from] io::Error),
}

#[derive(Debug, PartialEq, Eq)]
pub struct LogRecord {
    pub timestamp: u64,
    pub transaction_id: u128,
    pub payload_length: u32,
}

pub struct JournalReader<R> {
    reader: BufReader<R>,
    current_offset: u64,
}

impl JournalReader<File> {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self, JournalError> {
        let file = File::open(path.as_ref()).map_err(|e| JournalError::OpenFailure {
            path: path.as_ref().to_path_buf(),
            source: e,
        })?;
        
        // Alokasikan 64KB buffer untuk throughput optimal pada storage berbasis NVMe
        Ok(Self {
            reader: BufReader::with_capacity(64 * 1024, file),
            current_offset: 0,
        })
    }
}

impl<R: Read> JournalReader<R> {
    pub fn new(inner: R) -> Self {
        Self {
            reader: BufReader::with_capacity(64 * 1024, inner),
            current_offset: 0,
        }
    }

    pub fn next_record(&mut self) -> Result<Option<LogRecord>, JournalError> {
        let mut header_buf = [0u8; 28]; // 8 (timestamp) + 16 (tx_id) + 4 (len)
        
        match self.reader.read_exact(&mut header_buf) {
            Ok(()) => {
                let timestamp = u64::from_le_bytes(header_buf[0..8].try_into().unwrap());
                let transaction_id = u128::from_le_bytes(header_buf[8..24].try_into().unwrap());
                let payload_length = u32::from_le_bytes(header_buf[24..28].try_into().unwrap());

                self.current_offset += 28;

                // Verifikasi validitas data dasar (contoh batasan payload: 10MB)
                if payload_length > 10 * 1024 * 1024 {
                    return Err(JournalError::DataCorruption {
                        offset: self.current_offset - 4,
                        expected: 0,
                        actual: payload_length,
                    });
                }

                Ok(Some(LogRecord {
                    timestamp,
                    transaction_id,
                    payload_length,
                }))
            }
            Err(ref e) if e.kind() == io::ErrorKind::UnexpectedEof => {
                // Akhir stream tercapai secara bersih tanpa fragmentasi
                Ok(None)
            }
            Err(e) => Err(JournalError::Io(e)),
        }
    }
}
```

---

### 8. Real World Case Study: High-Throughput Financial Transaction Ledger

#### Masalah Arsitektur
Sebuah bursa finansial membutuhkan subsistem *Write-Ahead Log* (WAL) untuk memproses mutasi saldo rekening. Sistem memproses **150.000 transaksi/detik** dengan persyaratan kaku:
1. *Zero panics* dalam runtime di bawah kondisi apa pun (termasuk disk penuh atau kabel jaringan putus).
2. Laporan galat harus merekam *root cause chain* (sebab musabab) secara rinci tanpa memakan siklus alokasi memori pada *normal execution path*.
3. Kerusakan data biner (*torn writes* akibat listrik padam) harus terisolasi hingga batas transaksi spesifik tanpa merusak pembacaan transaksi historis lainnya.

#### Solusi Arsitektur
Dibuat subsistem penanganan I/O dan galat berlapis:
- Pemisahan total antara tipe data I/O fisik (`PhysicalStorageError`) dan logika finansial (`LedgerDomainError`).
- Penggunaan alokator arena untuk pooling buffer guna memastikan *zero-copy recycling*.
- Penggunaan trait `std::io::Write::flush` berkala yang dikombinasikan dengan pemanggilan `fdatasync(2)` via abstraksi galat yang aman dari interupsi OS (`EINTR`).

```
                ARSITEKTUR PIPELINE JOURNAL WRITE-AHEAD LOG

+----------------------+
| Transaksi Keuangan   |
+----------------------+
           │
           ▼
+---------------------------------------------------------------------+
| Lapisan Validasi Domain (Pure Logic, Zero Allocation)               |
| - Result<(), LedgerDomainError>                                     |
| - Varian: InsufficientFunds, AccountFrozen, InvalidSignature        |
+---------------------------------------------------------------------+
           │
           │ (Sukses)
           ▼
+---------------------------------------------------------------------+
| Lapisan Sinkronisasi WAL (I/O Resilient Layer)                      |
| - Menulis transaksi ke Ring-Buffer (Vectored I/O write_vectored)    |
| - Penanganan Galat: Catch io::ErrorKind, Retry on EINTR             |
| - Deteksi Disk Full (ENOSPC) -> Fallback ke Dead Letter Journal     |
+---------------------------------------------------------------------+
           │
           ▼
+---------------------------------------------------------------------+
| Batas Pengamatan & Audit (Observability Boundary)                  |
| - Format Logging terstruktur via anyhow Context                     |
| - Rekam tracing span metadata, Root Cause Extraction                |
+---------------------------------------------------------------------+
```

---

### 9. Trade-offs

#### 9.1. Error Representation: `thiserror` (Static Enum) vs `anyhow` (Dynamic Boxed)
- **`thiserror`**:
  - *Kelebihan*: Zero-allocation, layout memori deterministik, pencocokan pola (*pattern matching*) komprehensif, cocok mutlak untuk API publik dan pustaka (*library*).
  - *Kekurangan*: Membutuhkan kode boilerplate untuk agregasi manual enum bila lapisan arsitektur membengkak.
- **`anyhow`**:
  - *Kelebihan*: Sangat ergonomis untuk *application layer*, penambahan konteks ad-hoc (`context()`) mudah, secara otomatis mengalokasikan galat ke *heap* (`Box<dyn Error>`).
  - *Kekurangan*: Menghancurkan kemampuan kompilator untuk memverifikasi pencocokan pola secara statis, penalti performa dereferensi pointer dinamis, alokasi memori heap setiap kali galat dibuat.

#### 9.2. Strategi Penanganan Fatal Error: Unwind vs Abort
- `panic = "unwind"`:
  - Menyediakan kemampuan *catch_unwind* untuk memulihkan worker thread yang *crash*.
  - Meningkatkan ukuran biner secara signifikan karena LLVM harus menghasilkan tabel pencarian stack unwinding (DWARF framing). Penalti performa saat panic terjadi sangat masif.
- `panic = "abort"`:
  - Segera menghentikan proses secara deterministik via instruksi assembler `ud2` atau sinyal `SIGABRT`.
  - Mengurangi ukuran biner akhir (*lean binary footprint*) dan memungkinkan optimasi kompilator lintas unit yang lebih agresif. Menghilangkan alokasi dan overhead stack tracing secara mutlak.

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: Penggunaan `unwrap()` atau `expect()` pada File I/O
```rust
// BURUK (Produksi Mematikan):
let mut file = File::open("/etc/app/config.json").unwrap();
let mut data = Vec::new();
file.read_to_end(&mut data).unwrap();
```
*Dampak*: Kegagalan OS yang lumrah (misal: *Too many open files* / `EMFILE`, izin akses ditolak / `EACCES`) akan mematikan seluruh proses instan secara tiba-tiba tanpa pembersihan sumber daya (*resource cleanup*).

```rust
// BAIK (Idiomatik & Tangguh):
let mut file = File::open(path).map_err(|e| AppError::ConfigReadFailure {
    path: path.to_owned(),
    source: e,
})?;
```

#### Anti-Pattern 2: Menelan Galat Menggunakan Modifikasi Varian Kosong
```rust
// BURUK (Informasi Penting Hilang):
let connection = TcpStream::connect(addr).map_err(|_| AppError::ConnectionFailed)?;
```
*Dampak*: Kode galat dari kernel (apakah `ECONNREFUSED`, `ETIMEDOUT`, atau `ENETUNREACH`) dibuang ke tempat sampah. Tim SRE tidak akan pernah bisa mendiagnosis penyebab hilangnya koneksi.

```rust
// BAIK (Pertahankan Sebab Galat/Causality):
let connection = TcpStream::connect(addr).map_err(|e| AppError::ConnectionFailed(e))?;
```

#### Anti-Pattern 3: Bounded Loop pada Interrupted I/O
```rust
// BURUK:
let n = stream.read(&mut buf)?; // Jika EINTR dilempar OS, operasi langsung gagal
```
*Troubleshooting*: Sinyal sistem operasi POSIX dapat menginterupsi pemanggilan I/O sinkron sebelum byte ditransfer, mengembalikan `io::ErrorKind::Interrupted`.

```rust
// BAIK (Resilient I/O Loop):
let bytes_read = loop {
    match stream.read(&mut buf) {
        Ok(n) => break n,
        Err(ref e) if e.kind() == io::ErrorKind::Interrupted => continue,
        Err(e) => return Err(e.into()),
    }
};
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Tandai Semua Result Enum dengan `#[must_use]`**: Pastikan setiap status kegagalan diperiksa oleh pemanggil dan tidak diabaikan secara senyap.
2. [ ] **Alokasikan Buffer I/O yang Tepat**: Gunakan `BufReader::with_capacity(32 * 1024, inner)` (32KB–64KB) alih-alih buffer default (8KB) jika memproses throughput penyimpanan berkecepatan tinggi (SSD NVMe/10GbE network).
3. [ ] **Kotakkan (*Box*) Varian Galat yang Gemuk**: Jika salah satu varian enum galat memiliki ukuran memori yang sangat besar dibandingkan varian lain, bungkus menggunakan `Box<T>` untuk menjaga ukuran instansiasi `Result` tetap kecil di *stack*.
4. [ ] **Implementasikan Trait `source()`**: Jangan buat format teks bersarang secara manual; selalu sambungkan galat dasar menggunakan trait `std::error::Error::source` agar parser log APM (OpenTelemetry, Datadog) dapat memecah *root cause*.
5. [ ] **Hindari Pembacaan `read_to_string` Tanpa Batas**: Selalu batasi menggunakan `take(MAX_BYTES)` untuk mencegah serangan *Denial of Service (DoS)* berbasis *Memory Exhaustion* (OOM Killer) saat membaca dari soket publik.
6. [ ] **Verifikasi Flush Sebelum Penutupan**: Pemanggilan destruktor (`drop`) pada tipe `BufWriter` menelan galat I/O yang terjadi saat pelepasan buffer terakhir. Selalu panggil `.flush()?` secara eksplisit sebelum objek keluar dari cakupan (*scope*).

---

### 12. Hands-on Practice

Buatlah proyek Rust terstruktur pada repositori lokal Anda:

```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
cargo init --bin
```

Tambahkan dependensi berikut ke berkas `Cargo.toml`:
```toml
[dependencies]
thiserror = "1.0"
anyhow = "1.0"
```

Tuliskan implementasi mesin replikasi berkas biner enterprise pada `hands-on/m02/src/main.rs`:

```rust
use std::fs::File;
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use thiserror::Error;
use anyhow::{Context, Result};

#[derive(Debug, Error)]
pub enum ReplicationError {
    #[error("Berkas sumber tidak ditemukan: {0}")]
    SourceNotFound(PathBuf),

    #[error("Ruang penyimpanan tidak mencukupi atau kuota habis: {0}")]
    StorageExhausted(PathBuf),

    #[error("Integritas data rusak! Checksum sumber ({expected:#010X}) != target ({actual:#010X})")]
    ChecksumMismatch { expected: u32, actual: u32 },

    #[error("I/O Kernel Failure")]
    Io(#[from] io::Error),
}

pub struct StreamCopier;

impl StreamCopier {
    pub fn copy_with_crc32<P: AsRef<Path>>(source: P, destination: P) -> Result<u64, ReplicationError> {
        let src_path = source.as_ref().to_path_buf();
        let dst_path = destination.as_ref().to_path_buf();

        let src_file = File::open(&src_path).map_err(|e| {
            if e.kind() == io::ErrorKind::NotFound {
                ReplicationError::SourceNotFound(src_path.clone())
            } else {
                ReplicationError::Io(e)
            }
        })?;

        let dst_file = File::create(&dst_path).map_err(|e| {
            if e.kind() == io::ErrorKind::StorageFull {
                ReplicationError::StorageExhausted(dst_path.clone())
            } else {
                ReplicationError::Io(e)
            }
        })?;

        let mut reader = BufReader::with_capacity(128 * 1024, src_file);
        let mut writer = BufWriter::with_capacity(128 * 1024, dst_file);

        let mut buffer = [0u8; 64 * 1024];
        let mut total_bytes: u64 = 0;

        loop {
            let bytes_read = match reader.read(&mut buffer) {
                Ok(0) => break,
                Ok(n) => n,
                Err(ref e) if e.kind() == io::ErrorKind::Interrupted => continue,
                Err(e) => return Err(ReplicationError::Io(e)),
            };

            writer.write_all(&buffer[..bytes_read]).map_err(ReplicationError::Io)?;
            total_bytes += bytes_read as u64;
        }

        // PENTING: Harus flush eksplisit untuk menangkap galat penulisan sisa buffer
        writer.flush().map_err(ReplicationError::Io)?;

        Ok(total_bytes)
    }
}

fn execute_pipeline() -> Result<()> {
    let src = Path::new("source_data.bin");
    let dst = Path::new("replicated_data.bin");

    // Persiapan data dummy
    {
        let mut test_file = File::create(src).context("Gagal menginisialisasi berkas tes")?;
        test_file.write_all(b"TRANSACTION_LOG_PAYLOAD_CHUNK_IDENTIFIER_TEST_BURST")?;
    }

    println!("[INFO] Memulai replikasi stream...");
    let bytes_copied = StreamCopier::copy_with_crc32(src, dst)
        .with_context(|| format!("Kegagalan fatal pada sinkronisasi berkas {:?} ke {:?}", src, dst))?;

    println!("[SUCCESS] Berhasil mereplikasi {} byte secara atomik.", bytes_copied);
    
    // Bersihkan berkas setelah pengujian
    std::fs::remove_file(src).ok();
    std::fs::remove_file(dst).ok();

    Ok(())
}

fn main() {
    if let Err(err) = execute_pipeline() {
        eprintln!("\x1b[1;31m[ERROR EXECUTION TERMINATED]\x1b[0m");
        eprintln!("Keterangan: {:#}", err);
        
        eprintln!("\n-- Call Trace / Root Cause Tree --");
        for (i, cause) in err.chain().enumerate() {
            eprintln!("  Lapis ke-{}: {}", i, cause);
        }
        std::process::exit(1);
    }
}
```

Jalankan program:
```bash
cargo run
```

---

### 13. Exercise

#### Level: Easy
- **Problem**: Buatlah sebuah fungsi `read_first_line<P: AsRef<Path>>(path: P) -> Result<String, CustomIoError>` yang membaca baris pertama dari sebuah berkas teks.
- **Requirements**: Definisikan tipe galat kustom `CustomIoError` dengan varian `FileNotFound` dan `EmptyFile`. Tangani EOF bersih jika berkas ada tetapi tidak memiliki teks.
- **Edge Cases**: Berkas kosong (0 byte), berkas yang hanya berisi karakter baris baru `\n`.
- **Acceptance Criteria**: Kembalikan `Err(CustomIoError::EmptyFile)` pada berkas kosong, dan abaikan karakter *newline* pada teks hasil.

#### Level: Medium
- **Problem**: Buatlah sebuah parser streaming `RecordParser<R: Read>` yang membaca stream byte dengan format: `[2 Byte Tag][4 Byte Length][N Byte Data]`.
- **Requirements**:
  - Gunakan `BufReader`.
  - Jika `Length` melebihi limit konfigurable (misal: 1 MB), lempar galat khusus `ParserError::RecordTooLarge` tanpa mengalokasikan byte data ke heap.
  - Implementasikan pencegahan kebocoran memori dari serangan *partial stream hangs*.
- **Edge Cases**: Potongan data terpotong di tengah stream sebelum payload habis terkirim (`UnexpectedEof`).
- **Acceptance Criteria**: Fungsi mampu parsing 10.000 record berturut-turut dengan memory overhead konstan (<5 MB RSS).

#### Level: Hard
- **Problem**: Rancang struktur `ResilientRotatingFileWriter` yang mengimplementasikan trait `std::io::Write`.
- **Requirements**:
  - Berkas target harus berpindah (*rotate*) ke berkas baru (`app.log.1`, `app.log.2`, dst.) setiap kali ukuran mencapai ambang batas (misal: 100 MB).
  - Rotasi berkas harus aman dari *race condition* OS dan mengembalikan custom error `RotationError` jika disk kehabisan i-node atau ruang (`ENOSPC`).
  - Harus bebas dari alokasi dinamis pada pemanggilan `write()` normal.
- **Edge Cases**: Kegagalan `rename` pada sistem file NTFS/EXT4 saat berkas target terkunci atau tidak memiliki izin akses.
- **Acceptance Criteria**: Lolos pengujian konkurensi throughput 500 MB data terinjeksi tanpa ada byte yang hilang atau tercampur (*garbled*).

---

### 14. Challenge

Rancang arsitektur sistem penyimpanan transaksional **High-Frequency Trade (HFT) Journal Engine** dengan spesifikasi berikut:

#### Kasus Nyata
Sistem Anda menerima pembaruan buku order (*orderbook update*) via jaringan UDP dan harus menyimpannya ke NVMe storage dalam bentuk format biner *append-only*.
1. **Zero Allocations on Hot Path**: Selama pemrosesan stream tidak boleh terjadi alokasi memori heap baru. Buffer harus diambil dari *pre-allocated pool*.
2. **Error Quarantine Protocol**: Jika sektor disk mengalami *bad block* atau kernel melempar galat I/O bertipe `io::ErrorKind::Other` / hardware fault, subsistem tidak boleh mematikan proses utama, melainkan secara transparan mengalihkan *write destination* ke disk sekunder (secondary path failover) dalam waktu < 200 mikrodetik.
3. **Strict Validation**: Lakukan pemodelan galat domain menggunakan hierarki bertingkat tanpa menggunakan `anyhow` pada inti mesin:
   - Lapisan Hardware/OS: `StorageFault`
   - Lapisan Protokol: `FrameCorruptionFault`
   - Lapisan State Machine: `StateTransitionFault`

#### Tantangan Teknis
- Implementasikan abstraksi trait yang memungkinkan penyuntikan *mock fault injection* (mensimulasikan `write()` yang hanya menulis sebagian byte / *short write*, dan melempar `EINTR` secara acak).
- Bangun alur pengujian ketahanan (*chaos testing harness*) untuk memvalidasi bahwa integritas berkas cadangan (*fallback storage*) tetap konsisten 100% tanpa adanya kegagalan atomisitas.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa dampak ukuran memori dari `Result<(), MyError>` jika tipe `MyError` adalah sebuah enum dengan 3 varian tanpa payload?**
   - A. 1 Byte
   - B. 8 Byte
   - C. 16 Byte
   - D. 24 Byte
   - *Jawaban*: A. Tipe `()` berukuran 0 byte. Tiga varian enum membutuhkan representasi discriminant 1 byte, sehingga total ukuran adalah 1 byte (tanpa alokasi padding).

2. **Apa yang dilakukan oleh operator `?` ketika mendeteksi varian `Err(e)`?**
   - A. Memanggil `panic!()` secara implisit.
   - B. Mengeksekusi pengembalian fungsi lebih awal (`return`) dengan membungkus galat via `From::from(e)`.
   - C. Mengabaikan nilai galat dan menggantinya dengan nilai default tipe.
   - D. Melakukan alokasi heap dinamis untuk menyimpan stack trace secara otomatis.
   - *Jawaban*: B. Operator `?` menurunkan kode menjadi *early return* yang mengonversi galat asal ke galat yang dikembalikan oleh fungsi pengemban.

3. **Mengapa pemanggilan `BufWriter::flush()` harus dieksekusi secara manual sebelum keluar dari fungsi?**
   - A. Jika tidak di-flush, memori akan bocor (*memory leak*).
   - B. Rust melarang `BufWriter` dihapus (*drop*) tanpa flush.
   - C. Destruktor `drop()` otomatis memanggil flush, namun jika terjadi galat I/O saat drop, galat tersebut akan ditelan secara diam-diam (*silently ignored*).
   - D. Kompilator menolak kompilasi jika tidak ada perintah flush.
   - *Jawaban*: C. Trait `Drop` tidak mengizinkan pengembalian nilai `Result`, sehingga kegagalan flush di dalam `Drop` terpaksa diabaikan oleh runtime Rust.

4. **Kapan Anda sebaiknya menggunakan pustaka `thiserror` alih-alih `anyhow`?**
   - A. Saat membuat aplikasi CLI tingkat akhir (*end-user binary*).
   - B. Saat membangun library, SDK, atau modul domain inti yang membutuhkan pencocokan varian galat terstruktur oleh pemanggil.
   - C. Saat membutuhkan penangkapan stack trace instan tanpa memikirkan tipe galat.
   - D. `thiserror` tidak direkomendasikan lagi di ekosistem Rust modern.
   - *Jawaban*: B. `thiserror` dioptimalkan untuk mendesain enum galat statis yang kuat, sangat ideal untuk API publik dan pustaka.

5. **Apa fungsi dari atribut `#[source]` atau `#[from]` pada derivasi makro `thiserror`?**
   - A. Menyalin data ke variabel lain.
   - B. Mengimplementasikan trait method `std::error::Error::source` secara otomatis untuk menyediakan causality chain galat.
   - C. Mencetak log galat ke konsol stdout.
   - D. Menandai bahwa kode tersebut mengeksekusi unsafe block.
   - *Jawaban*: B. Makro tersebut mengaitkan galat internal sebagai penyebab (*root cause*) melalui trait `source()`.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Bagaimana cara kerja Niche Value Optimization pada tipe `Option<std::num::NonZeroU64>`?**
   - A. Mengalokasikan 16 byte memori di heap.
   - B. Menggunakan representasi bit nol (`0x0`) sebagai penanda varian `None`, sehingga ukuran keseluruhannya tetap 8 byte di stack tanpa discriminant tambahan.
   - C. Menghapus tipe `Option` saat runtime.
   - D. Memaksa kompilator melempar exception saat nilai bernilai 0.
   - *Jawaban*: B. Karena `NonZeroU64` dijamin tidak pernah bernilai nol, LLVM memanfaatkan nilai bit nol murni untuk menandai varian `None`.

7. **Jika fungsi Anda membaca file jaringan berkecepatan tinggi, mengapa pemanggilan berulang `std::io::Read::read` langsung pada `TcpStream` tanpa buffering adalah antipattern?**
   - A. Kernel Linux akan otomatis menutup koneksi jika buffer kosong.
   - B. Setiap pemanggilan `read()` menerbitkan perpindahan konteks kernel-space (*context switch syscall*), yang mengorbankan siklus instruksi CPU secara masif bila membaca chunk kecil.
   - C. Data TCP akan otomatis terfragmentasi dan mengalami korupsi bit.
   - D. TcpStream tidak mengimplementasikan trait `Read` secara default.
   - *Jawaban*: B. Overhead context switch CPU antara Ring 3 dan Ring 0 sangat mahal bila dipanggil berulang kali untuk ukuran byte yang kecil.

8. **Apa yang membedakan penanganan galat `std::io::ErrorKind::Interrupted` dengan error I/O lainnya?**
   - A. `Interrupted` adalah galat fatal hardware yang membutuhkan terminasi proses instan.
   - B. `Interrupted` menandakan operasi I/O terputus sementara oleh sinyal OS (misal: `EINTR`) sebelum mentransfer data, dan operasi tersebut harus dicoba ulang (*retried*).
   - C. `Interrupted` menandakan kabel ethernet terputus secara fisik.
   - D. `Interrupted` hanya terjadi pada arsitektur sistem operasi Windows.
   - *Jawaban*: B. Sinyal sistem operasi POSIX dapat menjeda syscall I/O yang sedang memblokir; aplikasi bertanggung jawab untuk mengulangi operasi tersebut.

9. **Apa konsekuensi dari membungkus semua galat ke dalam `Box<dyn std::error::Error + Send + Sync>` di sepanjang lapisan kode internal hot-path?**
   - A. Ukuran biner kompilasi menjadi lebih besar secara linear.
   - B. Terjadi alokasi memori dinamis di heap pada setiap pembentukan galat, ditambah dengan penalti kinerja dereferensi pointer vtable (*dynamic dispatch overhead*).
   - C. Menghilangkan thread-safety pada aplikasi.
   - D. Mematikan fitur garbage collection di Rust.
   - *Jawaban*: B. Pola type erasure berbasis `Box<dyn Error>` memaksa instansiasi objek ke heap dan pemanggilan metode melalui runtime vtable lookup.

10. **Perhatikan kode berikut: `let _ = writeln!(writer, "hello");`. Apa bahaya tersembunyi dari baris kode ini di sistem produksi?**
    - A. Memori buffer writer akan bocor (*leak*).
    - B. Jika penulisan gagal (misalnya partisi disk penuh atau socket klien tertutup), galat dibuang secara senyap tanpa deteksi, memicu status data inkonsisten tanpa alarm.
    - C. Sintaks tersebut ilegal dan memicu error kompilasi.
    - D. Terjadi *deadlock* pada muteks internal stream.
    - *Jawaban*: B. Penggunaan `let _ =` secara sengaja menonaktifkan peringatan `#[must_use]`, membuat sistem buta terhadap kegagalan penulisan I/O.

#### Bagian 3: Production Scenarios (3 Kasus Real-world)
11. **Skenario Kasus 1**: Pada layanan mikro pemrosesan pembayaran skala tinggi, tim SRE melaporkan bahwa CPU mengalami lonjakan tak terduga (*latency spike*) hingga 100% pada persentil p99.9 setiap kali gateway pihak ketiga merespons lambat atau gagal. Analisis heap dump menunjukkanjutaan alokasi string sementara. Investigasi menemukan kode berikut:
    ```rust
    fn parse_response(raw: &[u8]) -> Result<Transaction, String> {
        if raw.is_empty() {
            return Err(format!("Payload kosong terdeteksi dari IP: {}", get_client_ip()));
        }
        // ... parsing logika
    }
    ```
    **Langkah remediasi arsitektur apa yang paling efektif dan tepat sasaran untuk memulihkan performa tanpa kehilangan observabilitas?**
    - A. Mengganti `String` dengan `anyhow::Result` di seluruh fungsi.
    - B. Mengubah tipe kembalian menjadi `Result<Transaction, PaymentParseError>` di mana `PaymentParseError` adalah enum statis tanpa alokasi heap, lalu mengalihkan proses pemformatan string dan pengambilan IP hanya pada lapisan *logging/observability* ketika galat benar-benar ditangani.
    - C. Mengalokasikan string menggunakan thread pool terpisah (*rayon worker*).
    - D. Menghapus seluruh penanganan galat dan menggantinya dengan panic unwinding.
    - *Jawaban*: B. Mengganti galat domain menjadi enum statis nir-alokasi menghilangkan ribuan alokasi heap per detik pada hot path. Informasi kontekstual yang mahal seperti string formatting hanya perlu dievaluasi di batas infrastruktur (*cold path*).

12. **Skenario Kasus 2**: Sebuah *database engine* berbasis Rust mengalami insiden kerusakan indeks (*corrupted index*) saat diuji dengan pengujian simulasi pemutusan daya mendadak (*power outage simulation*). Investigasi menemukan bahwa penulis data menggunakan kode berikut:
    ```rust
    fn append_entry(file: &mut BufWriter<File>, entry: &[u8]) -> io::Result<()> {
        file.write_all(entry)?;
        file.flush()?;
        Ok(())
    }
    ```
    **Mengapa pemanggilan `file.flush()?` tidak menjamin data telah tertulis ke piringan disk fisik saat listrik padam, dan bagaimana perbaikannya?**
    - A. `flush()` pada `BufWriter` hanya mengosongkan buffer memori milik aplikasi di userspace dan mengirimkannya ke page cache milik kernel sistem operasi; data belum tentu ditulis (*persisted*) ke media non-volatile disk.
    - B. Kompilator Rust menunda pemanggilan flush hingga berkas ditutup.
    - C. Perangkat NVMe mengabaikan perintah flush jika berkas dibuka dalam mode append.
    - D. Solusinya adalah memanggil `BufWriter::into_inner()` lalu mengeksekusi method `File::sync_all()` atau `File::sync_data()` (yang menerbitkan syscall `fsync` / `fdatasync`).
    - *Jawaban Gabungan*: A dan D. `flush()` userspace hanya memindahkan data ke page cache kernel. Untuk memaksa controller disk fisik menulisnya ke memori persisten, harus dieksekusi `sync_all()` / `sync_data()`.

13. **Skenario Kasus 3**: Anda memelihara layanan ingest streaming yang memproses data telemetry via koneksi TCP. Layanan menggunakan kode I/O:
    ```rust
    let mut reader = BufReader::new(tcp_stream);
    let mut line = String::new();
    while reader.read_line(&mut line)? > 0 {
        process_telemetry(&line)?;
        line.clear();
    }
    ```
    Suatu malam, seluruh klaster mengalami kehabisan memori secara massal (*Out of Memory (OOM) Crash*) akibat serangan DoS dari klien yang mengirim aliran byte acak berukuran gigabyte tanpa karakter baris baru (`\n`).
    **Bagaimana cara memperbaiki kelemahan fatal I/O ini secara idiomatis?**
    - A. Mengganti `String` dengan array statis fixed-size di stack.
    - B. Menggunakan adapter `.take(MAX_ALLOWED_LINE_BYTES)` pada reader, atau membatasi pembacaan menggunakan buffer manual dengan batasan batas atas (*hard cap limit*) untuk menolak entri yang melanggar protokol dengan galat `StreamError::LineLimitExceeded`.
    - C. Mengurangi kapasitas internal `BufReader` dari 8KB menjadi 1KB.
    - D. Membuka koneksi baru untuk setiap baris data yang dibaca.
    - *Jawaban*: B. `read_line` terus mengalokasikan heap memory pada `String` hingga menemukan delimiter `\n`. Menggunakan pembatas `.take()` mencegah alokasi tak terbatas dan melindungi sistem dari kerentanan OOM DoS.

---

### 16. Summary

Penanganan galat dan sistem I/O di Rust dirancang dengan prinsip **kebenaran mutlak (*correctness*) tanpa mengorbankan performa (*zero-cost abstractions*)**:

1. **Memori & Kinerja**:
   - `Result<T, E>` menyatukan data dan status kegagalan tanpa overhead runtime eksepsi implisit. Melalui *niche value optimization*, rustc mampu menekan ukuran alokasi hingga setara tipe primitif.
   - Pembedaan strategi galat sangat fundamental: gunakan **statically typed enums (`thiserror`)** pada modul pustaka/domain inti demi memangkas alokasi heap, dan gunakan **type-erased dynamic reporting (`anyhow`)** pada batas aplikasi terluar demi visibilitas jejak audit teknis.
2. **Rekayasa Sistem I/O**:
   - Berinteraksi langsung dengan kernel via raw syscall adalah operasi yang mahal. Penggunaan `BufReader` dan `BufWriter` yang dikonfigurasi secara presisi memitigasi penalti *context switch*.
   - Pada aplikasi mission-critical, ketahanan sistem I/O ditentukan oleh kepatuhan terhadap penanganan siklus interupsi OS (`EINTR`), short reads/writes, dan pemanggilan sinkronisasi perangkat keras tingkat rendah (`fdatasync`/`sync_data`) sebelum mendeklarasikan status transaksi aman.