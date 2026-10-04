# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Kategori:** 02-Programming-Languages | **Topik:** Rust | **Bab 01:** Fondasi dan Arsitektur

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memetakan Memory Layout Tingkat Rendah:** Membedah representasi biner dari tipe data Rust, kalkulasi *data alignment*, *struct padding*, serta eksploitasi *Niche-Filling Optimization* pada *enum/discriminant*.
- **Menguasai Semantik Dynamic Sizing & Fat Pointers:** Memahami struktur internal *Dynamically Sized Types* (DSTs), implementasi vtable pada Trait Objects (`dyn Trait`), serta representasi memori *slices* (`&[T]`, `&str`).
- **Menerapkan Lifetime Subtyping & Variance:** Mengidentifikasi dan memecahkan limitasi *borrow checker* menggunakan konsep *Covariance*, *Invariance*, dan *Contravariance* dengan `std::marker::PhantomData`.
- **Membangun Komponen Zero-Copy Berkinerja Tinggi:** Mengimplementasikan protokol parser biner enterprise tanpa alokasi heap (*zero-allocation*) yang aman secara memori (*memory-safe*) menggunakan *lifetimes* tingkat lanjut.
- **Mengaudit & Memitigasi Risiko Safety:** Menjalankan verifikasi formal memori dengan Miri, meminimalkan dampak *Monomorphization Code Bloat*, dan menyusun arsitektur sistem berbasis Resource Acquisition Is Initialization (RAII).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
1. **Fondasi Dasar Rust:** Ownership, Move semantics, Borrowing (`&` dan `&mut`), serta generic types dasar.
2. **Arsitektur Sistem Operasi & Memori:** Konsep Virtual Memory, Page Boundaries, Pointers, Stack vs Heap, CPU Cache Lines (L1/L2/L3), dan False Sharing.
3. **Representasi Data Tingkat Rendah:** Representasi biner (Little/Big Endian), Word Size arsitektur 64-bit, serta ABI (Application Binary Interface).
4. **Toolchain Rust:** Menggunakan `cargo`, `rustc`, `rustup`, serta minimal Rust edisi 2021 (v1.75+ disarankan).

---

## 3. Concept & Internal Architecture

### 3.1 Memory Layout, Alignment, dan Struct Packing

Di Rust, kompilator secara default menggunakan representasi memori `repr(Rust)`. Berbeda dengan C (`repr(C)`), `repr(Rust)` tidak menjamin urutan field yang didefinisikan dalam kode sumber akan berurutan secara linier di memori. Rustc melakukan reorder field untuk meminimalkan *padding byte* yang disebabkan oleh *data alignment*.

Alignment mensyaratkan alamat memori suatu tipe data merupakan kelipatan dari ukuran alignment-nya:
$$\text{Address} \pmod{\text{Alignment}} = 0$$

```
Ukuran Primitif & Alignment (Arsitektur 64-bit):
- u8, i8      : Size = 1 byte,  Align = 1 byte
- u16, i16    : Size = 2 bytes, Align = 2 bytes
- u32, i32, f32: Size = 4 bytes, Align = 4 bytes
- u64, i64, f64, usize: Size = 8 bytes, Align = 8 bytes
```

Jika Rust mendeteksi field yang berantakan:
```rust
struct Unoptimized {
    a: u8,   // 1 byte
    b: u64,  // 8 bytes
    c: u16,  // 2 bytes
}
```
Pada `repr(C)`, memori yang dibutuhkan adalah:
- `a`: Offset 0 (1 byte) + 7 bytes padding
- `b`: Offset 8 (8 bytes)
- `c`: Offset 16 (2 bytes) + 6 bytes padding
- **Total: 24 bytes**

Sedangkan pada `repr(Rust)`, kompilator menyusun ulang menjadi `b` (offset 0), `c` (offset 8), `a` (offset 10), ditambah 5 bytes padding akhir untuk menjaga alignment struct (kelipatan 8) = **16 bytes**. Efisiensi memori meningkat 33%.

### 3.2 Niche Value Optimization

Rust memanfaatkan bit pattern yang tidak valid dari suatu tipe data (dikenal sebagai *niche*) untuk menyimpan metadata enum (*discriminant*) tanpa memperbesar alokasi memori.

Contoh konkret: `Option<NonNull<T>>` atau `Option<std::num::NonZeroU64>`.
Tipe data pointer (`&T`, `NonNull<T>`) dijamin oleh compiler tidak boleh bernilai null (`0x0`). Oleh karena itu, Rust menggunakan nilai `0x0` sebagai penanda varian `None`.
- `std::mem::size_of::<&u32>()` = 8 bytes.
- `std::mem::size_of::<Option<&u32>>()` = 8 bytes (Zero Overhead Optimization).

### 3.3 Dynamic Sizing & Fat Pointers (DSTs)

Tipe data berukuran tetap mengimplementasikan marker trait `Sized` secara implisit. Tipe data yang ukurannya hanya diketahui saat runtime disebut *Dynamically Sized Types* (DSTs), seperti `[T]` dan `str`, atau trait object `dyn Trait`.

DST tidak dapat disimpan langsung di stack. DST harus diakses melalui pointer khusus yang disebut **Fat Pointer** (berukuran 16 bytes pada sistem 64-bit):

1. **Slice Fat Pointer (`&[T]` / `&str`):**
   - Pointer alamat memori data (8 bytes)
   - Panjang elemen / *length* (8 bytes)
2. **Trait Object Fat Pointer (`&dyn Trait`):**
   - Pointer alamat instance data (8 bytes)
   - Pointer alamat *Virtual Method Table* (vtable) (8 bytes)

```
Trait Object Fat Pointer Layout:
+-------------------+-------------------+
|  Data Pointer     |  vtable Pointer   |
|     (8 Bytes)     |     (8 Bytes)     |
+-------------------+-------------------+
        |                     |
        v                     v
   [Data Heap/Stack]     [vtable in .rodata]
                         - Type size & align
                         - Drop glue function pointer
                         - Method pointers...
```

### 3.4 Lifetimes, Subtyping, dan Variance

Variance mendefinisikan bagaimana relasi subtipe antara dua tipe data mempengaruhi relasi subtipe dari tipe kompleks yang membungkusnya. Dalam Rust, subtyping hampir seluruhnya terbatas pada *lifetimes*, di mana `'a: 'b` dibaca: "*Lifetime `'a` meng-outlive lifetime `'b`*", yang berarti `'a` adalah subtipe dari `'b` (bisa dipakai di manapun `'b` diminta).

| Tipe Pembungkus | Variance terhadap `T` | Implikasi Keamanan |
| :--- | :--- | :--- |
| `&'a T` | **Covariant** thd `'a` & `T` | Boleh memberikan referensi dengan lifetime yang lebih panjang |
| `&'a mut T` | **Covariant** thd `'a`, **Invariant** thd `T` | Mencegah aliasing mutasi tipe yang tidak kompatibel |
| `fn(T) -> U` | **Contravariant** thd `T`, **Covariant** thd `U` | Argumen fungsi dapat menerima tipe yang lebih umum |
| `Cell<T>` / `UnsafeCell<T>` | **Invariant** thd `T` | Tidak ada subtyping; tipe harus cocok secara absolut |

### 3.5 Drop Check and Drop Flags

Rust menerapkan determinisme alokasi melalui RAII. Saat nilai keluar dari scope, kompilator memasukkan pemanggilan `Drop::drop`. Jika sebuah struct memiliki alokasi kondisionil (misal, variabel dipindahkan/move di dalam branch `if`), Rust menggunakan *Drop Flag* (biasanya 1 bit yang disimpan di stack frame) untuk melacak apakah *destructor* harus dieksekusi atau dilewati saat scope berakhir.

---

## 4. Why & What

### Mengapa Memahami Internals Sangat Krusial?
Dalam skala enterprise (seperti *High-Frequency Trading*, gateway perbankan, *database engine*, atau telemetri IoT masif), abstraksi tingkat tinggi tanpa pemahaman *underlying engine* memicu degradasi performa:
1. **Cache Misses:** Layout struct yang tidak teratur membuang ruang di L1/L2 cache line (biasanya 64 bytes). Mengoptimalkan padding dapat melipatgandakan throughput pemrosesan data.
2. **Monomorphization Code Bloat:** Penggunaan *generics* berlebihan tanpa teknik *dynamic dispatch* atau *thin-wrapper* memicu ukuran binary membengkak hingga ratusan megabyte, mengotori *Instruction Cache* (I-Cache).
3. **Alokasi Heap yang Tidak Diperlukan:** Menggunakan `String` atau `Vec` untuk membedah paket jaringan mengintroduksi syscall `malloc`/`mmap` yang meningkatkan p99 latency secara dramatis.

---

## 5. How (Workflow Detail)

Alur kompilasi Rust dari kode sumber menjadi eksekusi memori tingkat rendah:

```
[Rust Source Code (.rs)]
          │
          ▼
    [AST Generation]
          │
          ▼
   [HIR (High-Level IR)] ──> Desugaring (for, async/await, closures)
          │
          ▼
   [THIR (Typed HIR)]   ──> Type Checking, Variance Inference
          │
          ▼
   [MIR (Mid-Level IR)]  ──> Borrow Checker (Polonius/NLL), Drop Elaboration
          │
          ▼
      [LLVM IR]         ──> Inlining, Loop Vectorization, Dead Code Elimination
          │
          ▼
     [Target ASM]       ──> Machine Code (.o, executable)
```

Proses optimasi arsitektur enterprise:
1. Menentukan representasi struct (`repr(C)` vs `repr(Rust)`).
2. Memverifikasi ukuran dan alignment tipe menggunakan `std::mem::size_of` dan `std::mem::align_of`.
3. Menghindari alokasi dinamis dengan membangun parser zero-copy menggunakan referensi borrow ber-lifetime terikat.
4. Melakukan stress testing integritas pointer menggunakan `cargo miri test`.

---

## 6. Analogy & Diagram ASCII

### Analogi: Packing Kontainer Kargo Terstandarisasi

Bayangkan Anda memuat barang ke dalam kontainer berukuran tetap (Cache Line = 64 bytes):
- **C-Style Struct (repr(C)):** Anda menaikkan barang sesuai manifes kedatangan. Jika barang kecil 1 ton (1 byte) diikuti mesin berat 8 ton (8 bytes), Anda harus memasukkan bantalan kayu seberat 7 ton (7 bytes padding) agar posisi mesin seimbang di sumbu kargo (Alignment 8). Anda membuang ruang kargo berharga.
- **Rust-Style Struct (repr(Rust)):** Petugas kargo pintar menyusun ulang barang: mesin berat ditaruh terlebih dahulu, lalu celah-celah kosong diisi oleh barang-barang kecil. Ruang kargo terisi maksimal, meminimalkan jumlah kontainer yang dikirim ke jaringan.

### Diagram: Layout Memori Slice vs Trait Object vs Option Niche

```
1. Fat Pointer untuk Slices (&[u8]):
   Address: [ 0x7FFE0010 ] -> Pointer ke data buffer [ 'H', 'E', 'L', 'L', 'O' ]
   Length : [ 5          ] -> Panjang elemen (usize)

2. Fat Pointer untuk Trait Objects (&dyn ProtocolHandler):
   Data Pointer  : [ 0x7FFE0050 ] -> Alamat struct konkret di heap/stack
   vtable Pointer: [ 0x555500A0 ] -> Pointer ke tabel metadata & method
                                       ├── size: 32
                                       ├── align: 8
                                       ├── drop_fn: (*const ())
                                       └── parse_fn: (*const ())

3. Niche Optimization (Option<NonNull<T>>):
   Normal Enum:   [ Tag: 1 byte ] + [ Padding: 7 bytes ] + [ Pointer: 8 bytes ] = 16 bytes
   Niche-Enabled: [ Pointer: 8 bytes ] (Jika bernilai 0x0 => None, Jika != 0x0 => Some) = 8 bytes
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Analisis Layout dan Niche Optimization

```rust
use std::mem::{align_of, size_of};
use std::ptr::NonNull;

#[repr(C)]
struct CRepresentation {
    flag: u8,
    value: u64,
    counter: u16,
}

struct RustRepresentation {
    flag: u8,
    value: u64,
    counter: u16,
}

fn main() {
    println!("=== DEMO MEMORY LAYOUT ===");
    println!("CRepresentation Size: {} bytes, Align: {} bytes", 
        size_of::<CRepresentation>(), align_of::<CRepresentation>());
    println!("RustRepresentation Size: {} bytes, Align: {} bytes", 
        size_of::<RustRepresentation>(), align_of::<RustRepresentation>());

    // Validasi Niche Optimization
    println!("\n=== DEMO NICHE OPTIMIZATION ===");
    println!("*const u8 Size: {} bytes", size_of::<*const u8>());
    println!("Option<*const u8> Size: {} bytes (No niche for raw pointer)", 
        size_of::<Option<*const u8>>());
    
    println!("NonNull<u8> Size: {} bytes", size_of::<NonNull<u8>>());
    println!("Option<NonNull<u8>> Size: {} bytes (Niche optimization applied!)", 
        size_of::<Option<NonNull<u8>>>());
}
```

### 7.2 Practical Example: Zero-Copy Binary Telemetry Frame Parser

Sistem pemrosesan telemetri industri dengan throughput jutaan event/detik tanpa alokasi heap.

```rust
use std::convert::TryInto;
use std::fmt;

#[derive(Debug, PartialEq, Eq)]
pub enum ParseError {
    BufferTooShort,
    InvalidMagicNumber,
    PayloadLengthMismatch,
    CorruptedData,
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}", self)
    }
}

impl std::error::Error for ParseError {}

/// Header protokol biner enterprise (16 bytes fixed size)
/// [0..2]  Magic Number: 0xCAFE
/// [2]     Version
/// [3]     Flags
/// [4..8]  Message ID (u32, Big-Endian)
/// [8..12] Payload Length (u32, Big-Endian)
/// [12..16] Checksum CRC32 sederhana (u32)
#[repr(C, packed)]
#[derive(Debug, Clone, Copy)]
pub struct RawPacketHeader {
    pub magic: [u8; 2],
    pub version: u8,
    pub flags: u8,
    pub message_id: [u8; 4],
    pub payload_len: [u8; 4],
    pub checksum: [u8; 4],
}

pub struct TelemetryFrame<'a> {
    pub version: u8,
    pub message_id: u32,
    pub payload: &'a [u8],
}

pub struct ZeroCopyTelemetryParser;

impl ZeroCopyTelemetryParser {
    pub const MAGIC_BYTES: [u8; 2] = [0xCA, 0xFE];
    pub const HEADER_SIZE: usize = std::mem::size_of::<RawPacketHeader>();

    #[inline(always)]
    pub fn parse_frame<'a>(raw_buffer: &'a [u8]) -> Result<TelemetryFrame<'a>, ParseError> {
        if raw_buffer.len() < Self::HEADER_SIZE {
            return Err(ParseError::BufferTooShort);
        }

        // Parsing header zero-copy dengan bound checking terkalkulasi
        let (header_bytes, payload_and_rest) = raw_buffer.split_at(Self::HEADER_SIZE);

        if header_bytes[0..2] != Self::MAGIC_BYTES {
            return Err(ParseError::InvalidMagicNumber);
        }

        let version = header_bytes[2];
        let message_id = u32::from_be_bytes(
            header_bytes[4..8].try_into().map_err(|_| ParseError::CorruptedData)?
        );
        let payload_len = u32::from_be_bytes(
            header_bytes[8..12].try_into().map_err(|_| ParseError::CorruptedData)?
        ) as usize;

        if payload_and_rest.len() < payload_len {
            return Err(ParseError::PayloadLengthMismatch);
        }

        let payload = &payload_and_rest[..payload_len];

        Ok(TelemetryFrame {
            version,
            message_id,
            payload,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_packet_zero_copy() {
        let mut buffer = Vec::new();
        buffer.extend_from_slice(&[0xCA, 0xFE]); // Magic
        buffer.push(1);                         // Version
        buffer.push(0);                         // Flags
        buffer.extend_from_slice(&1001u32.to_be_bytes()); // Message ID
        buffer.extend_from_slice(&5u32.to_be_bytes());    // Payload Length: 5 bytes
        buffer.extend_from_slice(&[0, 0, 0, 0]);          // Checksum Dummy
        buffer.extend_from_slice(b"HELLO");               // Payload Content

        let parsed = ZeroCopyTelemetryParser::parse_frame(&buffer).expect("Should parse");
        assert_eq!(parsed.version, 1);
        assert_eq!(parsed.message_id, 1001);
        assert_eq!(parsed.payload, b"HELLO");
        
        // Verifikasi alokasi: Pointer payload harus merujuk langsung ke buffer input
        assert_eq!(parsed.payload.as_ptr(), unsafe { buffer.as_ptr().add(16) });
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low Latency Market Data Engine (L2 Order Book)
- **Problem Statement:** Sebuah bursa komoditas memproses 2.500.000 order/detik melalui multicast UDP. Implementasi lama menggunakan Java mengalami latency spikes (hingga 18ms) pada persentil p99.9 akibat Garbage Collection (Stop-The-World) dan heap allocation overhead ketika mendeserialisasi data biner.
- **Architectural Solution:**
  1. Rust Gateway dirancang menggunakan model arsitektur thread-per-core (Affinity Binding).
  2. Jaringan dibaca ke dalam memory ring-buffer statis berukuran 2MB yang disejajarkan dengan ukuran Huge Pages kernel.
  3. Frame didekodekan menggunakan slice zero-copy dan subtyping lifetime. Tidak ada struktur data yang menggunakan heap allocation (`Vec`, `String`, atau `Box`) pada jalur kritis (*hot-path*).
  4. Penggunaan `repr(align(64))` pada entitas order book mencegah *false sharing* antar core prosesor pada L3 cache.

```
       [Raw Multicast Socket]
                 │
                 ▼
       [DMA Ring Buffer (Huge Pages, Align 64)]
                 │  (Zero-Copy In-Place Borrow)
                 ▼
       [Fast Parser Engine] ──(Lifetimes: Frame<'static_ring>)
                 │
                 ▼
    [L2 Order Book State Machine]
                 │
                 ▼
       [Zero-Allocation Dispatcher]
```

- **Metrics & Impact:**
  - Latency Rata-rata: Turun dari $820\,\mu\text{s}$ ke $1.8\,\mu\text{s}$.
  - p99.9 Latency: Turun dari $18\,\text{ms}$ ke $4.2\,\mu\text{s}$ (Eliminasi Garbage Collection secara penuh).
  - CPU Utilization berkurang 65% karena penghematan instruksi memori dan pemanfaatan CPU cache line yang optimal.

---

## 9. Trade-offs

| Dimensi Arsitektur | Strategi: Zero-Copy & Lifetimes | Strategi: Owned Heap Allocations (`Clone`, `Vec`) |
| :--- | :--- | :--- |
| **Throughput & Latency** | **Maksimal.** Hampir tanpa syscalls alokasi memori; latency p99 deterministik. | **Sub-optimal.** Overhead `malloc`, memory fragmentation, dan cache-invalidation. |
| **Ergonomi Kode** | **Rendah.** Developer terbebani parameter lifetime (`'a`), borrow checker, dan aturan variance. | **Tinggi.** Kode sangat mudah disusun, dibaca, dan dimutasi tanpa restriksi borrow. |
| **Monomorphization** | **Beresiko.** Generic static dispatch masif mempercepat eksekusi namun memperbesar binary. | Menggunakan trait objects (`dyn Trait`) menekan binary bloat namun menambah vtable lookup. |
| **Refactoring Cost** | **Tinggi.** Perubahan struktur data merambat ke seluruh lifetime kontrak API. | **Rendah.** Modifikasi internal struct terisolasi dengan baik. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Struktur Data Self-Referential (Memegang Pointer ke Diri Sendiri)
*Gejala:* Error kompilasi `cannot borrow *self as mutable because it is also borrowed as immutable`. Developer pemula mencoba menyimpan data mentah (`Vec<u8>`) dan slice hasil parser (`&[u8]`) di dalam struct yang sama.
*Root Cause:* Ketika struct berpindah posisi di stack (move), pointer internal pada slice menjadi *dangling pointer* ke alamat memori yang lama.
*Solusi Arsitektur:* Pisahkan ownership penyimpanan buffer dengan parsing engine. Gunakan library eksternal berstandar industri seperti `ouroboros` atau restrukturisasi desain agar buffer dimiliki scope pemanggil (*caller-owned buffer*).

### 2. Accidental False Sharing pada Concurrency Berkinerja Tinggi
*Gejala:* Performa multi-threaded menurun drastis saat jumlah core CPU ditingkatkan.
*Root Cause:* Dua variabel independen yang dimutasi oleh dua thread berbeda berada pada satu CPU Cache Line yang sama (64 bytes). CPU terpaksa melakukan koordinasi cache coherency bus secara konstan.
*Solusi:*
```rust
#[repr(align(64))]
struct CacheAlignedAtomicCounter {
    counter: std::sync::atomic::AtomicU64,
}
```

### 3. Misleading `PhantomData` Variance Bugs
*Gejala:* Compiler menolak kode dengan error subtyping lifetime yang membingungkan saat membuat wrapper zero-cost abstraction.
*Root Cause:* Salah memilih marker `PhantomData`. Misalnya, menggunakan `PhantomData<*const T>` (yang invariant) padahal menginginkan sifat covariant.
*Solusi:* Gunakan mapping standar:
- `PhantomData<fn() -> T>` untuk memodelkan **Covariance**.
- `PhantomData<fn(T)>` untuk memodelkan **Contravariance**.
- `PhantomData<*mut T>` atau `PhantomData<Cell<T>>` untuk memodelkan **Invariance**.

---

## 11. Best Practices (Production Checklist)

- [ ] **Data Alignment Audit:** Jalankan cargo inspect atau audit struct packing menggunakan flag `-Zprint-type-sizes` pada toolchain nightly untuk meneliti ukuran padding.
- [ ] **Miri Sanity Check:** Eksekusi `cargo miri test` pada test suite untuk mendeteksi *Undefined Behavior*, *Out-Of-Bounds pointer arithmetic*, dan pelanggaran model *Stacked Borrows*.
- [ ] **Gunakan `#[repr(transparent)]`:** Pastikan tipe data Newtype (wrapper 1 field) menggunakan representasi ini jika akan di-cast atau diteruskan melintasi FFI/Boundary ABI.
- [ ] **Eliminasi Bounds Checking pada Loop Kritis:** Gunakan iterator chaining (`chunks`, `windows`) alih-alih indexing manual `buffer[i]` agar LLVM dapat mengeksekusi autovectorization (SIMD).
- [ ] **Panic Profiling:** Pastikan `panic = "abort"` dikonfigurasi pada profil release microservice kargo biner berperforma tinggi untuk memangkas ukuran biner dan drop-table unwinding overhead.
- [ ] **Deny Unsafe:** Pasang `#![deny(unsafe_code)]` pada level root crate; jika terpaksa menggunakan `unsafe`, isolasi ke dalam modul privat minimal dengan dokumentasi invariant *SAFETY:* yang lengkap.

---

## 12. Hands-on Practice

Buatlah workspace untuk menguji performa zero-copy packet parser secara modular.

### Struktur Direktori
```
hands-on/m02/
├── Cargo.toml
└── src/
    ├── arena.rs
    ├── lib.rs
    └── main.rs
```

### Langkah 1: Inisialisasi Project (`hands-on/m02/Cargo.toml`)
```toml
[package]
name = "packet_engine"
version = "0.1.0"
edition = "2021"

[dependencies]

[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
panic = "abort"
```

### Langkah 2: Arena Allocation Pattern (`hands-on/m02/src/arena.rs`)
Implementasikan ringkas stack arena memory allocator untuk mengeliminasi alokasi heap saat pemrosesan batch data:

```rust
pub struct BumpArena {
    storage: Vec<u8>,
    offset: usize,
}

impl BumpArena {
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            storage: vec![0u8; capacity],
            offset: 0,
        }
    }

    pub fn alloc(&mut self, size: usize, align: usize) -> Option<&mut [u8]> {
        let current_ptr = self.storage.as_ptr() as usize + self.offset;
        let padding = (align - (current_ptr % align)) % align;

        if self.offset + padding + size > self.storage.len() {
            return None; // Out of memory di arena
        }

        let start = self.offset + padding;
        self.offset = start + size;

        Some(&mut self.storage[start..self.offset])
    }

    pub fn reset(&mut self) {
        self.offset = 0;
    }
}
```

### Langkah 3: Modul Library Integrasi (`hands-on/m02/src/lib.rs`)
```rust
pub mod arena;

#[derive(Debug, PartialEq)]
pub struct TransactionMessage<'a> {
    pub account_id: u64,
    pub amount_cents: i64,
    pub reference_code: &'a str,
}

pub fn parse_transaction<'a>(input: &'a [u8]) -> Result<TransactionMessage<'a>, &'static str> {
    if input.len() < 20 {
        return Err("Payload insufficient");
    }

    let account_id = u64::from_le_bytes(input[0..8].try_into().unwrap());
    let amount_cents = i64::from_le_bytes(input[8..16].try_into().unwrap());
    let ref_len = u32::from_le_bytes(input[16..20].try_into().unwrap()) as usize;

    if input.len() < 20 + ref_len {
        return Err("Reference code length mismatch");
    }

    let reference_code = std::str::from_utf8(&input[20..20 + ref_len])
        .map_err(|_| "Invalid UTF-8 string")?;

    Ok(TransactionMessage {
        account_id,
        amount_cents,
        reference_code,
    })
}
```

### Langkah 4: Runtime Execution (`hands-on/m02/src/main.rs`)
```rust
use packet_engine::arena::BumpArena;
use packet_engine::parse_transaction;

fn main() {
    let mut arena = BumpArena::with_capacity(1024);
    
    // Alokasikan buffer pada arena (bukan heap baru)
    let buffer = arena.alloc(128, 8).expect("Allocation failed");
    
    // Bangun raw frame
    buffer[0..8].copy_from_slice(&99991234u64.to_le_bytes());
    buffer[8..16].copy_from_slice(&(-50000i64).to_le_bytes()); // Debet $500.00
    let message = b"INVOICE-TRX-001";
    buffer[16..20].copy_from_slice(&(message.len() as u32).to_le_bytes());
    buffer[20..20 + message.len()].copy_from_slice(message);

    match parse_transaction(&buffer[..20 + message.len()]) {
        Ok(tx) => {
            println!("Berhasil parsing transaksi:");
            println!("Account ID : {}", tx.account_id);
            println!("Amount     : {} cents", tx.amount_cents);
            println!("Reference  : {}", tx.reference_code);
        }
        Err(e) => eprintln!("Error parsing: {}", e),
    }

    arena.reset(); // Direset tanpa memory deallocation syscall
}
```

Eksekusi dengan:
```bash
cargo run --release
```

---

## 13. Exercises

### Level Easy: Optimal Struct Repacking
Diberikan struct C-legacy berikut:
```rust
#[repr(C)]
struct NetworkMetric {
    is_active: bool,     // 1 byte
    packet_count: u64,   // 8 bytes
    error_code: u8,      // 1 byte
    latency_ms: u32,     // 4 bytes
    interface_id: u16,   // 2 bytes
}
```
**Tugas:** Hitung ukuran `size_of::<NetworkMetric>()`. Rancang ulang susunan field struct tersebut menggunakan `repr(C)` agar ukurannya mengecil ke ukuran teoretis paling optimal tanpa menghilangkan field.

### Level Medium: Safe Slice Chunk Processing
Buat sebuah fungsi parsing yang membaca streaming byte array berukuran dinamis yang merepresentasikan daftar pasangan `(u16, u16)` (Key-Value array). Fungsi tidak boleh mengalokasikan heap (`Vec`), harus mengembalikan custom iterator yang mengevaluasi record on-demand (*lazy zero-copy iterator*), serta memvalidasi jika byte ganjil/terpotong.

### Level Hard: Dynamic Trait Object Registry Tanpa Alokasi Box
Rancang sebuah registry penanganan event jaringan (`EventHandler`) yang menyimpan maksimal 16 trait object berbeda di dalam fixed-size stack buffer. Implementasikan vtable wrapper manual atau gunakan referensi trait DST (`&dyn EventHandler`) tanpa menggunakan alokasi heap (`Box<dyn EventHandler>` dilarang). Pastikan lifetime dari masing-masing handler divalidasi dengan benar oleh compiler.

---

## 14. Challenges

### High-Performance Shared Ring-Buffer dengan Off-Heap Memory Mapped File
**Skenario Bisnis:** Anda ditugaskan membangun engine logging audit forensik dengan performa throughput 10 juta event/detik yang dapat bertahan dari crash aplikasi (*crash-resilient*).

**Spesifikasi Persyaratan:**
1. Alokasikan file memori menggunakan `mmap` kernel berukuran 1GB.
2. Definisikan struktur biner log ring-buffer yang memanfaatkan `AtomicU64` untuk *head* dan *tail* pointer (Lock-free single producer, single consumer).
3. Implementasikan *tombstone compaction* dan *crash recovery verification* saat gateway di-booting ulang: baca integritas binary header dan perbaiki *tail pointer* yang korup jika aplikasi mati mendadak saat operasi write sedang berlangsung.
4. **Restriksi Arsitektur:** 
   - Strict Zero-Copy: Dilarang menggunakan alokasi heap di dalam hot-path tulis/baca log.
   - Semua struct harus beralign 64-byte untuk sinkronisasi CPU cache line.
   - Wajib diverifikasi dengan model `miri`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Berapakah ukuran dari `Option<Box<u64>>` pada sistem operasi 64-bit? Jelaskan alasannya.**
   - A. 8 bytes
   - B. 9 bytes
   - C. 16 bytes
   - D. 24 bytes
   *Kunci Jawaban & Penjelasan:* **A. 8 bytes.** Tipe `Box<T>` dijamin tidak pernah null (`NonNull`), sehingga compiler Rust menerapkan *Niche-Filling Optimization*. Nilai null pointer (`0x0`) digunakan untuk merepresentasikan varian `None`, sehingga ukuran memori sama persis dengan raw pointer (8 bytes).

2. **Apa yang dimaksud dengan Dynamic Sized Types (DST) di Rust?**
   - A. Tipe data yang ukuran memorinya membesar otomatis di heap seperti `Vec<T>`.
   - B. Tipe data yang ukurannya tidak diketahui pada saat fase kompilasi (*compile-time*).
   - C. Tipe data yang hanya dialokasikan jika kondisi if-branch terpenuhi.
   - D. Tipe data yang dibuat menggunakan keyword `dynamic`.
   *Kunci Jawaban & Penjelasan:* **B.** DST (seperti `[T]` dan `str`) adalah tipe yang ukuran memorinya tidak dapat dipastikan saat kompilasi, sehingga harus diakses melalui pointer khusus (*fat pointer*).

3. **Berapa ukuran Fat Pointer untuk sebuah slice `&[u32]` pada arsitektur 64-bit?**
   - A. 4 bytes
   - B. 8 bytes
   - C. 16 bytes
   - D. 32 bytes
   *Kunci Jawaban & Penjelasan:* **C. 16 bytes.** Slice fat pointer terdiri dari dua komponen integer 64-bit: pointer data (8 bytes) dan panjang slice/length (8 bytes).

4. **Kapan compiler Rust mengeksekusi implementasi trait `Drop`?**
   - A. Ketika garbage collector mendeteksi variabel tidak lagi direferensikan.
   - B. Tepat saat variabel pemilik (*owner*) keluar dari lexical scope secara deterministik.
   - C. Hanya jika program memanggil fungsi `drop(x)` secara eksplisit.
   - D. Pada saat akhir eksekusi fungsi `main()`.
   *Kunci Jawaban & Penjelasan:* **B.** Rust menerapkan determinisme RAII; *destructor* (`Drop`) otomatis dipanggil tepat saat pemilik resource keluar dari scope.

5. **Apa fungsi utama dari atribut `#[repr(C)]` pada definisi struct di Rust?**
   - A. Menginstruksikan compiler untuk mengonversi kode Rust menjadi bahasa C.
   - B. Menjamin penataan layout memori dan padding field mengikuti standar ABI bahasa C.
   - C. Membuat struct hanya bisa dialokasikan di stack memori.
   - D. Mematikan semua fitur type safety pada struct tersebut.
   *Kunci Jawaban & Penjelasan:* **B.** `#[repr(C)]` memaksa Rust menyusun field sesuai deklarasi kode sumber dan mematuhi aturan platform C ABI untuk interoperabilitas.

---

### Bagian 2: Intermediate (5 Pertanyaan)

6. **Mengapa tipe data `&mut T` bersifat Invariant terhadap `T`?**
   - A. Agar compiler dapat melakukan inline fungsi mutasi lebih cepat.
   - B. Untuk mencegah kita menuliskan tipe dengan lifetime yang lebih pendek ke dalam referensi yang diekspektasikan hidup lebih panjang, yang memicu *use-after-free*.
   - C. Karena Rust tidak mengizinkan referensi mutable memiliki subtipe.
   - D. Agar kompatibel dengan pointer C++ `void*`.
   *Kunci Jawaban & Penjelasan:* **B.** Jika `&mut T` covariant terhadap `T`, kita bisa menukar referensi data yang hidup sebentar ke dalam pointer data yang hidup panjang, menghasilkan dangling references. Invariance mematikan subtyping pada target mutasi demi keamanan memori.

7. **Perhatikan kode berikut: `let x: Option<&u32> = None;` Berapakah alokasi memori heap yang digunakan?**
   - A. 4 bytes
   - B. 8 bytes
   - C. 16 bytes
   - D. 0 bytes
   *Kunci Jawaban & Penjelasan:* **D. 0 bytes.** Referensi dan `Option` di stack tidak melakukan alokasi heap apa pun (`malloc`). Semua berada di stack lokal frame sebesar 8 bytes.

8. **Apa perbedaan mendasar vtable pada Rust (`dyn Trait`) dibanding virtual table pada bahasa C++?**
   - A. Di C++, pointer vtable disimpan di dalam instance objek. Di Rust, pointer vtable disimpan bersama referensi di fat pointer.
   - B. Rust tidak memiliki vtable nyata, hanya switch conditional.
   - C. vtable Rust disimpan di stack, sedangkan C++ di heap.
   - D. vtable Rust dibuat setiap kali method dipanggil saat runtime.
   *Kunci Jawaban & Penjelasan:* **A.** Rust memisahkan layout memori data murni dari dispatch table. Objek struct Rust tidak memiliki overhead pointer vtable jika tidak dibungkus dalam fat pointer `&dyn Trait`.

9. **Jika sebuah struct memiliki field `PhantomData<*mut T>`, bagaimanakah sifat variansinya terhadap `T`?**
   - A. Covariant
   - B. Contravariant
   - C. Invariant
   - D. Bivariant
   *Kunci Jawaban & Penjelasan:* **C. Invariant.** Raw pointer mutable `*mut T` bersifat invariant di Rust. Penggunaan `PhantomData<*mut T>` menurunkan sifat invariansi tersebut kepada struct pembungkusnya.

10. **Apa dampak negatif dari fenomena *Monomorphization Code Bloat* dalam sistem skala enterprise?**
    - A. Memperlambat eksekusi instruksi aritmatika CPU.
    - B. Meningkatkan ukuran binary secara masif yang dapat menyebabkan kerapuhan instruksi cache (*I-Cache misses*) dan latensi kompilasi tinggi.
    - C. Menyebabkan kebocoran memori stack secara kumulatif.
    - D. Memaksa compiler menonaktifkan borrow checker.
    *Kunci Jawaban & Penjelasan:* **B.** Monomorphization menduplikasi kode mesin untuk setiap tipe konkret dari fungsi generic. Ukuran binary yang membesar drastis mengotori cache L1I (Instruction Cache) CPU dan menurunkan throughput throughput eksekusi.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario:** Anda mendeteksi bahwa microservice Rust gateway Anda mengalami lonjakan penggunaan memori secara drastis saat memproses koneksi WebSocket yang *idle*. Struct koneksi didefinisikan sebagai berikut:
    ```rust
    struct ClientSession {
        id: u64,
        is_authenticated: bool,
        last_ping: u64,
        drop_reason: Option<u8>,
        tls_fingerprint: [u8; 32],
        is_admin: bool,
    }
    ```
    Bagaimana Anda merestrukturisasi layout memori ini untuk menghemat memori sebanyak mungkin tanpa mengubah tipe fungsional data?
    *Analisis Solusi:*
    Analisis layout saat ini (tergantung padding): Field bool dan Option<u8> tersebar di antara field bernilai integer 64-bit (`u64`). Rustc dapat menyusun ulang, namun jika dipaksa serialisasi atau C-repr, padding akan membesar. 
    Langkah arsitektur:
    1. Kelompokkan field alignment besar (8 bytes: `id`, `last_ping`) secara berurutan.
    2. Posisikan slice/array `tls_fingerprint` (32 bytes).
    3. Gabungkan field boolean dan flag kecil: `is_authenticated`, `is_admin`, dan `drop_reason` di bagian akhir.
    4. Lebih jauh lagi: Gabungkan flag boolean menjadi bitflags (`u8`) menggunakan crate `bitflags` untuk menghemat 2 byte menjadi 1 byte, memangkas ukuran struct secara signifikan jika ada jutaan sesi websocket konkuren.

12. **Skenario:** Tim Anda membangun zero-copy JSON parser berkecepatan tinggi. Compiler menolak kode saat Anda mencoba memetakan string JSON ke dalam field struct:
    ```rust
    struct ConfigHolder {
        raw_string: String,
        parsed_key: &'??? str,
    }
    ```
    Mengapa compiler menolak desain ini dan apa alternatif arsitektur terbaik untuk memecahkannya?
    *Analisis Solusi:*
    Ini adalah masalah klasik **Self-Referential Struct**. Field `parsed_key` meminjam data dari `raw_string` yang berada di dalam struct yang sama. Jika struct `ConfigHolder` dipindahkan (misal di-return dari fungsi), memori `raw_string` berpindah alamat stack-nya, menyebabkan `parsed_key` berpotensi menjadi dangling reference.
    *Solusi Terbaik Enterprise:*
    Pisahkan model kepemilikan data:
    - Opsi A: Buat Caller-Owned Pattern: caller memegang ownership `String`, sedangkan struct parser hanya memegang referensi `ConfigParser<'a> { parsed_key: &'a str }`.
    - Opsi B: Simpan offset biner: `struct ConfigHolder { raw_string: String, key_offset: (usize, usize) }`. Slicing string hanya dilakukan on-demand melalui method accessor `holder.key()`.

13. **Skenario:** Engine komputasi terdistribusi Anda mengalami error kompilasi yang menyatakan bahwa sebuah tipe `Context<'a>` tidak dapat dikirim antar-thread (`cannot be shared between threads safely`), padahal data di dalamnya dijamin read-only. Setelah diperiksa, struct tersebut memiliki field `PhantomData<*const ()>`.
    Mengapa hal tersebut terjadi dan bagaimana memperbaikinya secara aman?
    *Analisis Solusi:*
    Raw pointer (`*const T`, `*mut T`) secara implisit **tidak** mengimplementasikan trait `Send` dan `Sync` karena Rust tidak dapat menjamin keamanan thread pada bare pointer. Akibatnya, keberadaan `PhantomData<*const ()>` mencabut otomatis implementasi `Send` dan `Sync` dari struct `Context`.
    *Solusi Perbaikan:*
    1. Ganti `PhantomData<*const ()>` dengan tipe marker yang aman secara thread jika intensinya hanya menandai ownership/lifetime, misalnya `PhantomData<&'a ()>`. Tipe referensi immutable `&'a ()` mengimplementasikan `Send` dan `Sync`.
    2. Jika memang membutuhkan representasi pointer mentah namun aman melintasi thread, deklarasikan secara eksplisit:
    `unsafe impl<'a> Send for Context<'a> {}`
    `unsafe impl<'a> Sync for Context<'a> {}`
    dengan melampirkan dokumentasi invariant audit thread-safety.

---

## 16. Summary

1. **Memori dan Alignment:** Rust menyusun layout memori melalui `repr(Rust)` secara otomatis guna meminimalkan ruang akibat padding, namun developer harus memahami batasan alignment arsitektur CPU target untuk performa p99 yang deterministik.
2. **Niche Optimization:** Kemampuan compiler Rust memetakan state ilegal (seperti null pointer) menjadi varian enum menghilangkan overhead discriminant pada tipe seperti `Option<NonNull<T>>`.
3. **Fat Pointers:** Abstraksi tanpa alokasi heap pada DSTs (`[T]`, `str`, `dyn Trait`) dicapai melalui pointer ganda (Data + Length, atau Data + Vtable).
4. **Variance & Safety:** Subtyping di Rust dikelola secara ketat melalui aturan variance pada *lifetimes*. Memahami invariant dan covariant mutlak diperlukan saat mengabstraksi pointer tingkat rendah dengan `PhantomData`.
5. **Arsitektur Produksi:** Skalabilitas enterprise diraih bukan hanya dengan menghindari runtime panics, melainkan dengan meminimalkan cache-line invalidation, mereduksi dynamic dispatch, dan memprioritaskan parser berbasis *Zero-Copy Borrowing*.