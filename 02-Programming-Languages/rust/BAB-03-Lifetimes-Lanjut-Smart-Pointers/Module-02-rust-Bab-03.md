# Kurikulum Enterprise Rust: Sistem & Rekayasa Perangkat Lunak
## Kategori: 02-Programming-Languages
### BAB-03: Lifetimes Lanjut & Smart Pointers
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada tingkat *Staff/Principal Engineer* diharapkan mampu:
- **Menganalisis dan Memanipulasi Variance**: Mengidentifikasi dan membuktikan sifat *covariance*, *contravariance*, dan *invariance* pada tipe generik dan pointer referensi untuk mencegah celah eksploitasi memori (*aliasing bugs*).
- **Mengimplementasikan Higher-Rank Trait Bounds (HRTB)**: Merancang abstraksi *zero-copy callback pipeline* menggunakan sintaks `for<'a>` guna memproses data dengan masa hidup dinamis tanpa mengorbankan keamanan kompilasi (*lifetime elision escape*).
- **Membangun Custom Smart Pointer Tingkat Produksi**: Mengembangkan struktur *smart pointer* kustom yang memiliki semantik thread-safe, manajemen memori manual melalui `UnsafeCell`, serta mematuhi aturan *Drop Check* (`dropck`) dan *Nominal Variance* menggunakan `PhantomData`.
- **Menyelesaikan Masalah Self-Referential Structs**: Mengimplementasikan arsitektur *buffer-parsing* tanpa alokasi menggunakan `Pin`, serta memahami batasan *compiler* dalam meng-invalidasi alamat memori internal (*movable memory guarantees*).
- **Mendeteksi dan Memitigasi *Undefined Behavior* (UB)**: Memanfaatkan *toolchain* verifikasi formal seperti `cargo miri` dan *sanitizer* (ASan/TSan) pada kode unsafe yang melibatkan manipulasi pointer mentah dan transmutasi lifetime.

---

### 2. Prerequisite
Sebelum mempelajari materi ini, peserta diwajibkan telah menguasai:
- Konsep dasar kepemilikan (*Ownership*), peminjaman (*Borrowing*), dan *Lifetimes* dasar (`'a`).
- Semantik alokasi Heap vs Stack pada tipe `Box<T>`, `Rc<T>`, `Arc<T>`, `Cell<T>`, dan `RefCell<T>`.
- Fungsionalitas konkurensi dasar: Trait `Send` dan `Sync`.
- Konstruksi blok `unsafe` dasar serta manipulasi pointer mentah (`*const T`, `*mut T`).
- Pemahaman perakitan memori (*Memory Layouts*): Alignment, Padding, dan Sized vs Dynamically Sized Types (`?Sized`).

---

### 3. Concept & Internal Architecture

#### 3.1 Subtyping dan Variance
Rust tidak memiliki pewarisan kelas (*class inheritance*), namun memiliki mekanisme *subtyping* yang secara eksklusif berbasis pada relasi masa hidup (*lifetime relations*). Relasi `'a: 'b` dibaca: "*'a outlives 'b*" (lifetime `'a` hidup minimal sama panjangnya dengan atau lebih lama dari `'b'`). Dalam relasi ini, `'a` adalah *subtype* dari `'b` (ditulis `'a <: 'b`).

Variance mendeskripsikan bagaimana relasi *subtyping* antara dua tipe argumen ditransmisikan ke tipe komposit pembungkusnya:

1. **Covariant**: Jika `'a <: 'b`, maka `F<'a> <: F<'b>`.
   - Contoh: `&'a T`, `Box<T>`. Anda dapat memberikan referensi dengan umur panjang ke fungsi yang hanya membutuhkan umur pendek.
2. **Invariant**: Jika `'a <: 'b`, tidak ada relasi subtyping antara `F<'a>` dan `F<'b>`. Keduanya adalah tipe yang sama sekali berbeda bagi compiler.
   - Contoh: `&mut T`, `UnsafeCell<T>`. Jika `&mut &'a T` bersifat covariant, kita dapat menukar referensi `'a` dengan referensi `'b` yang lebih pendek, meninggalkan dangling pointer saat `'b` mati tetapi `'a` masih diakses.
3. **Contravariant**: Jika `'a <: 'b`, maka `F<'b> <: F<'a>`.
   - Terjadi hampir secara eksklusif pada argumen fungsi tingkat tinggi: `Fn(T)`. Jika suatu fungsi membutuhkan input yang hanya hidup sepanjang `'b`, fungsi yang mampu menerima input sepanjang `'a` dapat menggantikannya secara aman.

```
Relasi Variance Ringkas:
-----------------------------------------------------------
Tipe                  Variance terhadap 'a     Variance terhadap T
-----------------------------------------------------------
&'a T                 Covariant                Covariant
&'a mut T             Covariant                Invariant
*const T              -                        Covariant
*mut T                -                        Invariant
fn(T) -> U            -                        Contravariant (T), Covariant (U)
UnsafeCell<T>         -                        Invariant
PhantomData<T>        -                        Sama dengan T
-----------------------------------------------------------
```

#### 3.2 Higher-Rank Trait Bounds (HRTB)
Secara standar, parameter generik seumur hidup terikat pada tingkat item/fungsi saat pemanggilan (*call site*). Namun, ketika sebuah fungsi menerima *closure* atau parser yang harus meminjam data dari scope lokal di dalam fungsi itu sendiri (yang umurnya tidak bisa diketahui oleh pemanggil), compiler membutuhkan HRTB:

$$\forall 'a : \text{Trait}('a)$$

Sintaks: `for<'a> F: Fn(&'a Context) -> Output`.
Ini menjamin bahwa tipe `F` dapat beroperasi secara valid terhadap lifetime `'a` *apapun* yang dihasilkan di masa mendatang oleh runtime fungsi internal, bukan terikat pada lifetime statis luar.

#### 3.3 Anatomi Drop Check (`dropck`) dan Soundness
Ketika sebuah instance struct keluar dari scope, fungsi `Drop::drop(&mut self)` dieksekusi, diikuti oleh destruksi rekursif terhadap field-fieldnya. Masalah fatal terjadi jika implementasi *custom drop* mengakses data via pointer mentah yang sudah lebih dulu di-drop oleh borrow checker.

Untuk mencegah *use-after-free* saat proses drop:
- Compiler menerapkan aturan **Drop Check**: Tipe generik `T` atau lifetime `'a` harus hidup *strictly outlive* struct yang memilikinya jika struct tersebut mengimplementasikan `Drop`.
- Atribut `#[may_dangle]` (khusus internal compiler/nightly) mengesampingkan batasan ini dengan menyatakan bahwa implementasi `Drop` dari tipe tersebut menjamin tidak akan menyentuh atau menderiferensiasi data yang ditunjuk oleh parameter generik terkait.

#### 3.4 UnsafeCell: Fondasi Interior Mutability
Satu-satunya konstruksi legal dalam model kompilasi rustc/LLVM untuk menghasilkan pointer mutabel (`*mut T`) dari sebuah referensi *shared* immutable (`&T`) adalah melalui `std::cell::UnsafeCell<T>`. 

Di mata LLVM:
- Referensi biasa `&T` dioptimasi dengan atribut `noalias readonly`.
- Melewati casting langsung `&T` menjadi `*mut T` tanpa `UnsafeCell` adalah tindakan yang menghasilkan status **Immediate Undefined Behavior** karena melanggar optimasi pass LLVM.
- `UnsafeCell<T>` menonaktifkan emisi metadata `readonly` pada representasi intermediate (LLVM IR).

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan di Skala Produksi? | Apa yang Terjadi Jika Salah Desain? |
| :--- | :--- | :--- |
| **Variance Control** | Menjaga integritas pointer saat bekerja dengan buffer memory mentah (*ring buffers*, *arena allocators*). | Terjadi *data race* atau *use-after-free* akibat *lifetime widening* yang tidak terdeteksi oleh compiler. |
| **HRTB (`for<'a>`)** | Memungkinkan abstraksi streaming data biner dan deserialisasi zero-copy terdistribusi. | Kode terjebak dalam error `lifetime may not live long enough` dan memaksa alokasi memori berlebih (`clone()`). |
| **Custom Smart Pointer** | Mengurangi beban sinkronisasi thread (*atomic contention*) dengan custom reference counting pool. | Terjadinya *memory leak* (kebocoran siklik) atau dereferensi segfault pada edge cases di traffic tinggi. |
| **Drop Check Rigidity** | Menjamin destruksi thread, memory mapping, dan file descriptor tertutup secara tertib. | Akses *dangling pointer* secara silent saat shutdown aplikasi mikro (*crash-on-exit*). |

---

### 5. How (Workflow Detail)

Berikut adalah alur eksekusi Rust Compiler (khususnya borrow checker engine / NLL & Polonius) dalam memvalidasi Lifetime dan Drop Invariants:

```
[Tahap 1: AST -> HIR -> THIR Transformation]
                     │
                     ▼
[Tahap 2: MIR Construction & Type Inference]
   - Pembacaan deklarasi lifetime dan generik
   - Deteksi variance via relasi field dan PhantomData
                     │
                     ▼
[Tahap 3: NLL (Non-Lexical Lifetimes) Constraint Generation]
   - Transformasi scope referensi menjadi kumpulan titik CFG (Control Flow Graph)
   - Evaluasi subtyping: Cek apakah relasi 'a: 'b konsisten pada seluruh flow
   - Penegakan Invariance pada &mut T (kedua arah subtyping harus identik)
                     │
                     ▼
[Tahap 4: Drop Check Verification (dropck)]
   - Cek apakah struct mengimplementasikan Trait `Drop`
   - Jika YA: Periksa apakah Tipe Parameter 'a / T diakses di dalam `drop()`
   - Validasi liveness invariants saat destruksi scope
                     │
                     ▼
[Tahap 5: LLVM IR Code Generation]
   - Strip informasi lifetime (Lifetime Erasure)
   - Penempatan atribut `noalias` / `dereferenceable` sesuai rules variance
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Variance
Bayangkan sebuah **Wadah Minuman**:
- Air Mineral dingin adalah *subtype* dari Minuman Segar (`'a <: 'b`). Semua Air Mineral adalah Minuman, tapi tidak semua Minuman adalah Air Mineral dingin.
- **Covariant (`&'a T`)**: Anda memesan *Wadah Transparan Minuman Segar*. Jika pelayan memberikan *Wadah Transparan Air Mineral*, Anda aman meminumnya.
- **Invariant (`&mut T`)**: Anda memberikan *Dispenser Minuman* ke pihak lain untuk diisi ulang. Dispenser ini **harus** secara spesifik hanya diisi Air Mineral. Jika diisi kopi manis panas, dispenser rusak dan peminum berikutnya yang mengharapkan air murni akan keracunan data (*undefined behavior*). Dispenser tidak boleh disubtitusi secara leluasa.

#### Diagram Drop Check & Dangling Pointer
```
Scope Induk (Outer Scope)
┌─────────────────────────────────────────────────────────────┐
│ let target: String = String::from("KRITIS");                │
│                                                             │
│ Scope Anak (Inner Scope)                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ let holder: CustomPointer<&String>;                     │ │
│ │ holder = CustomPointer::new(&target);                   │ │
│ │                                                         │ │
│ │ // ... Eksekusi Logika ...                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│  ◄── `holder` mulai di-drop di sini!                      │
│      Drop Check memverifikasi: Apakah `target` masih hidup? │
│      - Jika 'target' di-drop sebelum 'holder': DITOLAK.     │
│      - Menghindari pembacaan invalid memory saat dropck.    │
└─────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengamati Invariance Violation pada `&mut T`
Kode berikut mendemonstrasikan mengapa `&mut T` wajib bersifat *invariant* terhadap `T`.

```rust
// Kode ini sengaja dirancang untuk mendemonstrasikan pencegahan compiler.
// Jika rustc membiarkan invariance ini dilanggar, eksploitasi memori terjadi.

fn main() {
    let mut outer_str: &'static str = "GLOBAL PERMANEN";
    {
        let local_str = String::from("LOCAL DATA SEMENTARA");
        
        // Memaksa subtyping pada invariant context:
        // overwrite_ref membutuhkan &mut &'a str
        overwrite_ref(&mut outer_str, &local_str);
    } 
    // local_str keluar dari scope dan MEMORI DIBEBASKAN (Dropped)

    // Jika baris di atas dikompilasi, baris di bawah ini akan membaca freed memory!
    println!("Dangling access: {}", outer_str);
}

fn overwrite_ref<'a, 'b>(slot: &mut &'a str, val: &'b str) 
where 
    'b: 'a // Meminta 'b outlive 'a, tetapi &mut bersifat INVARIANT
{
    // COMPILE ERROR: lifetime mismatch
    // *slot = val; 
}
```

#### Practical Example: High-Performance Arena-Allocated Smart Pointer dengan Variance Soundness
Implementasi pointer referensi terkontrol untuk streaming ingestion system.

```rust
use std::marker::PhantomData;
use std::ptr::NonNull;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Kontrak: Memegang alokasi memori internal yang safe.
/// Bersifat COVARIANT terhadap T karena menggunakan NonNull<T>
/// dan memiliki proteksi drop-safety eksplisit via PhantomData.
pub struct SharedArenaRef<'a, T: 'a> {
    ptr: NonNull<T>,
    ref_count: NonNull<AtomicUsize>,
    // PhantomData<&'a T> menyatakan kepada compiler bahwa struct ini 
    // meminjam T dengan lifetime 'a (Covariant over 'a dan T).
    _marker: PhantomData<&'a T>,
}

impl<'a, T: 'a> SharedArenaRef<'a, T> {
    pub fn new(val: &'a mut T, rc_alloc: &'a AtomicUsize) -> Self {
        rc_alloc.fetch_add(1, Ordering::Relaxed);
        Self {
            ptr: NonNull::from(val),
            ref_count: NonNull::from(rc_alloc),
            _marker: PhantomData,
        }
    }

    #[inline(always)]
    pub fn get(&self) -> &'a T {
        // SAFETY: Pointer dijamin valid selama lifetime 'a masih aktif,
        // dan pointer tidak dapat dimutasi secara langsung selama dereferensi ini.
        unsafe { self.ptr.as_ref() }
    }
}

impl<'a, T: 'a> Clone for SharedArenaRef<'a, T> {
    fn clone(&self) -> Self {
        // SAFETY: ref_count dijamin merupakan pointer valid ke AtomicUsize
        unsafe {
            self.ref_count.as_ref().fetch_add(1, Ordering::Relaxed);
        }
        Self {
            ptr: self.ptr,
            ref_count: self.ref_count,
            _marker: PhantomData,
        }
    }
}

impl<'a, T: 'a> Drop for SharedArenaRef<'a, T> {
    fn drop(&mut self) {
        // SAFETY: Atomic decrement untuk pelacakan lifetime peminjaman arena
        unsafe {
            if self.ref_count.as_ref().fetch_sub(1, Ordering::Release) == 1 {
                std::sync::atomic::fence(Ordering::Acquire);
                // Hook pembersihan arena custom bila diperlukan
            }
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Arsitektur Gateway Deserialisasi Pasar Modal (Ultra-Low-Latency Order Book Engine). Memproses 2.000.000 paket/detik binary order streams dari LSE (London Stock Exchange) / NASDAQ via UDP Multicast.

#### Masalah Arsitektural
Sistem tidak dapat menggunakan alokasi dinamis standar (`Arc<Vec<u8>>` atau `Box`) karena menyebabkan alokasi heap berlebih dan *GC pauses* internal melalui alloc/dealloc overhead. Kami membutuhkan *Zero-Copy Decoding Pipeline* di mana event parser menerima *sliced network packet*, memecahnya menjadi struktur order transaksi, dan mengeksekusi callback multithreading menggunakan **Higher-Rank Trait Bounds (HRTB)** tanpa runtime pointer indirection.

#### Solusi Arsitektur
Menerapkan struct zero-copy state machine yang diikat oleh batasan `for<'de>` HRTB, dipadukan dengan arena buffer internal yang menjamin non-aliased memory melalui subtyping yang valid.

```rust
use std::fmt::Debug;

#[derive(Debug, PartialEq, Eq)]
pub enum OrderSide {
    Buy,
    Sell,
}

#[derive(Debug)]
pub struct MarketOrder<'a> {
    pub symbol: &'a str,
    pub price: u64,
    pub volume: u32,
    pub side: OrderSide,
}

/// Zero-Copy Frame Ingestion Pipeline
pub struct IngestionEngine<F> {
    processor: F,
}

impl<F> IngestionEngine<F>
where
    // HRTB: Processor wajib mampu memproses MarketOrder dengan lifetime APAPUN
    // yang dihasilkan dari buffer lokal transient selama siklus baca.
    for<'packet> F: Fn(MarketOrder<'packet>) -> Result<(), &'static str>,
{
    pub fn new(processor: F) -> Self {
        Self { processor }
    }

    /// Membaca raw byte array langsung dari kernel ring buffer (e.g. via io_uring / DPDK)
    pub fn process_raw_frame(&self, frame_buffer: &[u8]) -> Result<(), &'static str> {
        if frame_buffer.len() < 17 {
            return Err("ERR_PACKET_MALFORMED: Ukuran buffer tidak mencukupi");
        }

        // Dekoding binary stream tanpa alokasi string heap
        let symbol_slice = std::str::from_utf8(&frame_buffer[0..4])
            .map_err(|_| "ERR_INVALID_TICKER_ENCODING")?;
        
        let price = u64::from_be_bytes(
            frame_buffer[4..12]
                .try_into()
                .map_err(|_| "ERR_BYTE_CONVERSION")?,
        );
        let volume = u32::from_be_bytes(
            frame_buffer[12..16]
                .try_into()
                .map_err(|_| "ERR_BYTE_CONVERSION")?,
        );
        let side = match frame_buffer[16] {
            0x01 => OrderSide::Buy,
            0x02 => OrderSide::Sell,
            _ => return Err("ERR_INVALID_SIDE_FLAG"),
        };

        let order = MarketOrder {
            symbol: symbol_slice,
            price,
            volume,
            side,
        };

        // Memanggil callback ber-kontrak HRTB
        (self.processor)(order)
    }
}

// Simulasi Pipeline Eksekusi
fn main() {
    let mut total_volume_ingested: u64 = 0;

    // Inisialisasi engine dengan closure yang meminjam state secara aman
    let engine = IngestionEngine::new(|order: MarketOrder<'_>| {
        // Zero-copy print: symbol hanya referensi langsung ke array transient
        if order.price > 100_000 {
            // Simulasi eksekusi match order berkecepatan tinggi
            println!("HIGH VALUE ORDER: {} x {}", order.symbol, order.volume);
        }
        Ok(())
    });

    // Simulasi paket masuk dari socket kernel
    let raw_packet: [u8; 17] = [
        b'N', b'V', b'D', b'A',             // Symbol (4 Bytes)
        0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x86, 0xA0, // Price: 100,000 (8 Bytes)
        0x00, 0x00, 0x01, 0xF4,             // Volume: 500 (4 Bytes)
        0x01                                // Side: Buy (1 Byte)
    ];

    engine.process_raw_frame(&raw_packet).expect("Engine Processing Failed");
}
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Strict Lifetimes & Zero-Copy** | Latensi pemrosesan p99 mendekati wire-speed. Zero GC overhead, memory safety tanpa runtime check. | Struktur data viral: Lifetime annotations merambat ke seluruh layer abstraksi codebase. | Bungkus struktur lifetime ke dalam layer facade domain yang terisolasi. |
| **Higher-Rank Trait Bounds (HRTB)** | Abstraksi interface generic sempurna untuk event-driven parser tanpa memory leak. | Tingkat kesulitan pembacaan kode (*cognitive load*) tinggi. Diagnosa compiler error kompleks. | Standardisasi signature via type alias: `type MessageHandler = dyn for<'a> ...`. |
| **Custom Smart Pointer via `UnsafeCell`** | Kendali mutlak atas memory layout, cache alignment, dan mekanisme atomik. | Resiko UB tinggi: Aliasing violation, thread-safety hazard, memory leaks bila `dropck` luput. | Uji menyeluruh dengan `cargo miri run` dan *fuzz testing* sebelum rilis ke production. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengasumsikan `&mut T` Bersifat Covariant
*Problem*: Mengirim `&mut Derived` ke context yang meminta `&mut Base` lalu melakukan mutasi tipe pointer yang lebih pendek.
*Diagnosa Error*:
```text
error[E0621]: explicit lifetime required in the type of `val`
   |
12 | fn inject(dest: &mut &'a str, val: &str) {
   |                                    ^^^^ lifetime `'a` required
```
*Solusi*: Sadari bahwa `&mut T` adalah **invariant** terhadap `T`. Jangan gunakan referensi ganda termutasi jika ingin memperluas kompatibilitas lifetime; gunakan owned wrapper atau readonly access (`&T`).

#### 2. Dangling Pointer Akibat Pola Self-Referential Struct Naif
*Problem*: Membuat struct yang menyimpan buffer `Vec<u8>` dan referensi `&[u8]` yang menunjuk ke buffer tersebut sendiri.
```rust
// ANTI-PATTERN: AKAN DITOLAK COMPILER SECARA TOTAL
struct SelfReferential {
    data: Vec<u8>,
    cached_slice: &'??? [u8], // Tidak ada lifetime yang valid di Rust untuk pola ini!
}
```
*Troubleshooting*: Selesaikan masalah ini secara deterministik menggunakan `Pin<Box<T>>` bersama pointer mentah, atau gunakan crate standar industri yang telah diaudit secara formal seperti `ouroboros` atau ubah arsitektur menggunakan *Index-based referencing* (menyimpan `std::ops::Range<usize>`).

#### 3. Melanggar Subtyping Invariants via `std::mem::transmute`
*Problem*: Menggunakan `transmute` untuk memanjangkan lifetime referensi agar lolos dari borrow checker.
```rust
// MEMORY EXPLOIT HAZARD
unsafe fn force_static<'a, T>(input: &'a T) -> &'static T {
    std::mem::transmute(input) // SANGAT DILARANG DI LEVEL ENTERPRISE
}
```
*Penanganan*: Jika borrow checker menolak lifetime, masalah sebenarnya berada pada desain siklus hidup memori Anda, bukan batasan compiler. Refactor pipeline untuk menggunakan owned values (`Arc<T>`) jika umur data benar-benar dinamis.

---

### 11. Best Practices (Production Checklist)

- [ ] **Miri Automation Validation**: Eksekusi perintah `cargo miri test` wajib lolos tanpa peringatan *Stacked Borrows* atau *Tree Borrows* di pipeline CI/CD.
- [ ] **Explicit Variance Tracking**: Seluruh smart pointer unsafe yang membungkus `NonNull<T>` atau raw pointer harus menggunakan `PhantomData` untuk merefleksikan kepemilikan dan variansi yang benar (`PhantomData<T>`, `PhantomData<&'a T>`, atau `PhantomData<Cell<T>>`).
- [ ] **Drop Soundness Defense**: Jika struktur mengimplementasikan destruktor custom (`Drop`), pastikan tidak ada dereferensi pointer ke lifetime generik tanpa penjaminan invariants atau drop-order yang ketat.
- [ ] **Enforce Thread-Safety Bounds**: Deklarasikan implementasi `Send` dan `Sync` secara manual pada smart pointer hanya jika tipe data internalnya valid dan thread-safe.
- [ ] **Zero Unsound Transmutes**: Larang sepenuhnya penggunaan `transmute` untuk mengubah batasan lifetime dalam code-review enterprise. Gunakan `reborrowing` eksplisit.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
cargo init --name advanced_lifetimes_pt
```

#### Langkah 2: Tambahkan Konfigurasi Toolchain dan Manifest (`Cargo.toml`)
```toml
[package]
name = "advanced_lifetimes_pt"
version = "0.1.0"
edition = "2021"

[dependencies]

[dev-dependencies]
```

Pastikan Miri terinstall:
```bash
rustup component add miri
```

#### Langkah 3: Implementasi Smart Pointer Thread-Safe Lock-Free `AtomicRefBox<T>`
Tulis kode berikut pada `hands-on/m02/src/main.rs`:

```rust
use std::fmt;
use std::marker::PhantomData;
use std::ops::Deref;
use std::ptr::NonNull;
use std::sync::atomic::{AtomicUsize, Ordering};

pub struct AtomicRefBox<T: ?Sized> {
    ptr: NonNull<T>,
    ctrl_block: NonNull<ControlBlock>,
    _marker: PhantomData<T>,
}

struct ControlBlock {
    strong_count: AtomicUsize,
}

// Safety Invariant: AtomicRefBox aman ditransfer lintas thread jika T: Send + Sync
unsafe impl<T: ?Sized + Send + Sync> Send for AtomicRefBox<T> {}
unsafe impl<T: ?Sized + Send + Sync> Sync for AtomicRefBox<T> {}

impl<T> AtomicRefBox<T> {
    pub fn new(value: T) -> Self {
        let boxed_val = Box::new(value);
        let boxed_ctrl = Box::new(ControlBlock {
            strong_count: AtomicUsize::new(1),
        });

        Self {
            ptr: NonNull::new(Box::into_raw(boxed_val)).expect("Allocation failure"),
            ctrl_block: NonNull::new(Box::into_raw(boxed_ctrl)).expect("Allocation failure"),
            _marker: PhantomData,
        }
    }
}

impl<T: ?Sized> Deref for AtomicRefBox<T> {
    type Target = T;

    #[inline(always)]
    fn deref(&self) -> &Self::Target {
        // SAFETY: Pointer dijamin selalu valid selama strong_count > 0
        unsafe { self.ptr.as_ref() }
    }
}

impl<T: ?Sized> Clone for AtomicRefBox<T> {
    fn clone(&self) -> Self {
        unsafe {
            let ctrl = self.ctrl_block.as_ref();
            let old_count = ctrl.strong_count.fetch_add(1, Ordering::Relaxed);
            
            // Abort jika mendeteksi overflow counter untuk mencegah security exploit
            if old_count > (usize::MAX / 2) {
                std::process::abort();
            }
        }

        Self {
            ptr: self.ptr,
            ctrl_block: self.ctrl_block,
            _marker: PhantomData,
        }
    }
}

impl<T: ?Sized> Drop for AtomicRefBox<T> {
    fn drop(&mut self) {
        unsafe {
            let ctrl = self.ctrl_block.as_ref();
            // Sinkronisasi memori: Release-Acquire barrier
            if ctrl.strong_count.fetch_sub(1, Ordering::Release) == 1 {
                std::sync::atomic::fence(Ordering::Acquire);
                
                // Reconstruct box untuk mendestruksi value dan control block secara valid
                drop(Box::from_raw(self.ptr.as_ptr()));
                drop(Box::from_raw(self.ctrl_block.as_ptr()));
            }
        }
    }
}

impl<T: ?Sized + fmt::Debug> fmt::Debug for AtomicRefBox<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Debug::fmt(&**self, f)
    }
}

fn main() {
    println!("[Enterprise Smart Pointer Runtime Test]");
    let resource = AtomicRefBox::new(String::from("DATA_FRAME_PAYLOAD_001"));
    
    let worker_ref = resource.clone();
    let handle = std::thread::spawn(move || {
        println!("Worker thread reading: {:?}", worker_ref);
    });

    handle.join().expect("Worker thread panicked");
    println!("Main thread reading: {:?}", resource);
}
```

#### Langkah 4: Validasi Integritas Memori
Jalankan validasi formal untuk membuktikan tidak ada UB:
```bash
cargo miri run
```
Output harus bersih dari laporan kesalahan alokasi memori atau pelanggaran data race.

---

### 13. Exercise

#### Tingkat: Easy
Buat generic struct `CovariantCursor<'a, T>` yang membungkus slice referensi `&'a [T]`. Buktikan melalui kode unit test bahwa compiler memperbolehkan subtyping covariance di mana cursor dengan lifetime panjang dapat disubstitusikan ke context fungsi yang membutuhkan lifetime lebih pendek.

#### Tingkat: Medium
Rancang sebuah generic event pipeline menggunakan HRTB `for<'req> Fn(&'req Request) -> Response` yang mengimplementasikan middleware logging terisolasi. Middleware ini harus memproses `Request` yang dialokasikan di dalam stack lokal fungsi runner tanpa menyebabkan kompilator menuntut lifetime parameter pada struct runtime engine.

#### Tingkat: Hard
Rancang custom smart pointer `PinnedArenaBox<'a, T>` yang memiliki sifat **Invariant** terhadap tipe `T` menggunakan `PhantomData<fn(T) -> T>`. Pointer ini harus mencegah pemindahan memori internal (`Pin`-like semantics) dan mengimplementasikan trait `Drop` manual yang menjamin pembebasan memori aman ke buffer arena statis tanpa dereferensi dangling saat shutdown sistem.

---

### 14. Challenge

**Studi Kasus Enterprise**: Anda ditugaskan membangun komponen zero-copy Inter-Process Communication (IPC) Ring-Buffer Reader untuk platform perdagangan berfrekuensi tinggi (High-Frequency Trading).

**Kebutuhan Spesifikasi Teknis**:
1. Reader membaca shared-memory file (`mmap`) biner yang ukurannya tidak terbatas (continuous circular stream).
2. Data paket yang dibaca berformat TLV (Type-Length-Value) dengan payload biner yang harus dideferensiasi langsung di tempat (zero-copy deserialization).
3. Anda **dilarang** mengalokasikan memori heap per paket data (`Vec`, `String`, atau `Box` baru selama pemrosesan data dilarang keras).
4. Komponen parser wajib mengekspos public API berbasis Higher-Rank Trait Bounds (HRTB) sehingga consumer callback dapat menerima payload yang terikat secara presisi hanya pada lifetime pembacaan frame lokal.
5. Anda harus membuktikan bahwa arsitektur parser Anda **kebal terhadap eksploitasi Lifetime Subtyping Extension** (invariance enforcement) sehingga consumer tidak dapat menyimpan referensi ke paket melebihi batas siklus frame kernel ring buffer.

*Deliverable*: Berikan kode arsitektural lengkap beserta safety documentation komprehensif, implementasi `PhantomData`, dan skema verifikasi static analysis.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Jika `'long: 'short`, mengapa `&'long T` dapat digunakan pada fungsi yang menerima `&'short T`?
   - *Jawaban*: Karena tipe referensi immutable `&'a T` bersifat *covariant* terhadap `'a`. Subtyping memperbolehkan tipe yang hidup lebih lama menggantikan tipe yang hidup lebih pendek.
2. Apa variance dari tipe `&mut T` terhadap tipe generik `T`?
   - *Jawaban*: Bersifat *Invariant*. `T` tidak boleh disubstitusikan ke subtype maupun supertype untuk mencegah aliasing mutation invalid.
3. Apa fungsi utama sintaks Higher-Rank Trait Bounds (HRTB) `for<'a>` pada Rust?
   - *Jawaban*: Menyatakan bahwa sebuah trait bound (seperti closure) harus terpenuhi untuk *seluruh* kemungkinan lifetime `'a`, bukan hanya satu lifetime spesifik yang ditentukan di call site pemanggilan generic.
4. Mengapa `PhantomData<T>` diperlukan pada struct yang mengelola alokasi memori manual melalui pointer mentah `*const T`?
   - *Jawaban*: Karena pointer mentah tidak membawa informasi lifetime dan ownership untuk borrow checker. `PhantomData<T>` memberi instruksi deterministik kepada compiler mengenai kepemilikan, variance, dan drop-check requirements.
5. Mengapa mengubah `&T` langsung menjadi `*mut T` lalu memutasinya tanpa membungkusnya dalam `UnsafeCell<T>` dikategorikan sebagai *Undefined Behavior* instan?
   - *Jawaban*: Karena compiler mengoptimasi `&T` sebagai pointer dengan atribut LLVM `noalias readonly`. Memutasinya secara langsung melanggar kontrak compiler dan merusak optimasi CPU register/caching.

#### 5 Pertanyaan Intermediate
1. Mengapa compiler Rust menolak jika `&mut &'a T` diperlakukan secara covariant terhadap `'a`?
   - *Jawaban*: Jika covariant, referensi `'a` yang hidup lama dapat dimutasi untuk menunjuk ke referensi lokal `'b` yang hidup singkat. Ketika scope `'b` berakhir, referensi `'a` akan mengalami kondisi *dangling reference* (use-after-free).
2. Jelaskan interaksi antara trait `Drop` dan borrow checker pada Drop Check (`dropck`) RFC!
   - *Jawaban*: Drop check memastikan bahwa data apapun yang dirujuk oleh struct tidak boleh didekonstruksi sebelum method `drop(&mut self)` dari struct tersebut selesai dieksekusi secara utuh.
3. Bagaimana cara membuat sebuah parameter tipe generik `T` pada custom pointer menjadi *Contravariant*?
   - *Jawaban*: Dengan menyematkan marker `PhantomData<fn(T)>` ke dalam struktur data tersebut.
4. Kapan kita wajib menggunakan `std::pin::Pin` pada smart pointer yang memegang data self-referential?
   - *Jawaban*: Saat tipe data memiliki pointer internal yang menunjuk ke dirinya sendiri di stack/heap, sehingga relokasi memori (move semantic) akan mematahkan validitas alamat memori internal tersebut.
5. Apa perbedaan semantik mendasar antara `Ordering::Release` / `Ordering::Acquire` dibandingkan `Ordering::SeqCst` pada implementasi `Drop` custom reference-counted smart pointer?
   - *Jawaban*: Release-Acquire mengoordinasikan sinkronisasi visibilitas modifikasi memori antar thread spesifik tanpa memaksa global bus synchronization lock total di level CPU, sehingga memberikan latensi destruksi alokasi jauh lebih rendah dibandingkan `SeqCst`.

#### 3 Skenario Kasus Produksi

##### Skenario 1:
Sebuah engine trading crash dengan status memory corruption saat traffic pasar sedang mengalami lonjakan volume tinggi. Diagnosa log menemukan bahwa seorang engineer menggunakan:
```rust
struct CacheEntry<'a> {
    data: UnsafeCell<&'a [u8]>,
}
```
*Evaluasi*: Apa yang salah dengan arsitektur tipe di atas?
*Solusi*: `UnsafeCell` mematikan optimasi safety compiler dan memberikan akses mutasi interior. Karena `&'a [u8]` di dalamnya memiliki lifetime, mutasi melalui UnsafeCell dapat secara diam-diam menimpa referensi slice dengan data yang sudah di-free di thread lain, memicu data race dan peminjaman invalid. Solusinya adalah membungkus underlying memory dengan safe memory handle (`Bytes` atau `Arc<[u8]>`) atau memberlakukan strict sync locking via mutex/rwlock.

##### Skenario 2:
Compiler mengeluarkan error `borrowed data escapes outside of closure` pada routing framework web performa tinggi yang Anda rancang.
*Evaluasi*: Mengapa error ini muncul pada zero-copy HTTP middleware?
*Solusi*: Middleware callback mencoba mengembalikan referensi dari body request yang dipinjam secara lokal ke luar context fungsi request. Borrow checker menolak karena lifetime referensi terbatas pada frame eksekusi HTTP dispatcher. Solusinya: Ubah middleware trait bound agar menggunakan HRTB `for<'req> Fn(&'req Context) -> Pin<Box<dyn Future<Output = ()> + 'req>>`.

##### Skenario 3:
Pada sistem pemrosesan grafik terdistribusi, Anda mendeteksi memory leak masif ketika ribuan node grafik cyclic dialokasikan menggunakan `Arc<RefCell<Node>>`.
*Evaluasi*: Bagaimana strategi mitigasi arsitektur tanpa mengorbankan performa traversal?
*Solusi*: Patahkan siklus referensi (*reference cycle*) dengan memisahkan *parent-to-child ownership* menggunakan `Arc<RefCell<Node>>` dan *child-to-parent / neighbor back-references* menggunakan `std::sync::Weak<RefCell<Node>>`. Alternatif performa yang lebih tinggi pada skala enterprise: tinggalkan Arc-in-Arc tree dan beralih ke **Arena Memory Architecture** (flat vector index-based graph: `SlotMap` / `Petgraph`).

---

### 16. Summary

- **Variance** adalah aturan formal sistem tipe Rust yang mendikte bagaimana relasi masa hidup (*lifetimes*) dapat disubstitusikan secara aman; ketidaktahuan atas sifat invariant pada referensi mutabel adalah sumber utama celah keamanan memori pada kode unsafe.
- **Higher-Rank Trait Bounds (HRTB)** memungkinkan penulisan pustaka tingkat enterprise yang beroperasi pada batas peminjaman zero-copy dinamis, membebaskan sistem dari alokasi memori yang tidak esensial.
- **Custom Smart Pointers** menuntut kepatuhan mutlak terhadap Drop Check, Memory Ordering, dan `PhantomData` variance typing untuk menjamin soundness kode tingkat produksi.
- Kematangan arsitektur Rust tingkat lanjut diukur dari kemampuan merekayasa sistem yang meminimalkan alokasi heap via zero-copy pipeline, namun tetap sepenuhnya diverifikasi aman secara formal oleh borrow checker dan tool verifikasi runtime seperti Miri.