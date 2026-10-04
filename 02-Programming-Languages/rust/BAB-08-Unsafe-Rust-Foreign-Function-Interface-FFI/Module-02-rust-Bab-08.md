# BAB 08: Unsafe Rust & Foreign Function Interface (FFI)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengarsiteksi Abstraksi FFI Dua Arah (Bi-directional FFI)**: Mengintegrasikan runtime Rust dengan runtime C/C++ secara mulus, baik mengekspor pustaka Rust ke host C/C++ (*Rust as a library*) maupun mengonsumsi dependensi C native (*C-sys wrappers*).
2. **Menegakkan Invarian ABI dan Memory Layout**: Mengontrol tata letak memori tingkat rendah menggunakan `#[repr(C)]`, `#[repr(transparent)]`, zero-sized types (`PhantomData`), dan optimasi niche layout pointer (`Option<NonNull<T>>`).
3. **Mencegah Undefined Behavior (UB) Lintas Batas**: Mengimplementasikan dinding pengaman kepanikan (*panic firewall*) menggunakan `std::panic::catch_unwind` guna menghindari *unwinding* melintasi batas ABI C.
4. **Mengelola Siklus Hidup Alokasi Memori Heterogen**: Menerapkan pola kepemilikan eksplisit (*opaque handle pattern*) dengan `Box::into_raw` dan `Box::from_raw`, memastikan tidak terjadi *allocator mismatch* antara *Rust Global Allocator* dan *system allocator* (`libc::malloc`/`free`).
5. **Menjalankan Validasi Formal dan Sanitasi Memori**: Mengintegrasikan **Miri**, **AddressSanitizer (ASan)**, dan **ThreadSanitizer (TSan)** ke dalam pipeline CI/CD untuk mendeteksi *pointer aliasing violation*, kebocoran memori, dan *data races* pada kode unsafe.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Mekanisme dereferensi raw pointer (`*const T`, `*mut T`) dan konstruksi blok `unsafe` dasar (Bab 08 - Modul 01).
* Rust Memory Model: Aturan aliasing mutabel unik (*Stacked Borrows* / *Tree Borrows* model), *lifetimes*, serta subtipe variansi (*covariance, contravariance, invariance*).
* C Memory Management: Pemahaman mendalam mengenai pointer aritmetika, struct alignment/padding, calling convention (`cdecl`, `stdcall`, `fastcall`), dan pemanggilan library dinamis/statis (`dlopen`, `ld`).

---

### 3. Concept & Internal Architecture

#### 3.1. Binary Compatibility & Calling Conventions
Ketika dua bahasa yang berbeda berinteraksi, keduanya harus menyepakati Application Binary Interface (ABI). Rust secara bawaan menggunakan ABI internal (`extern "Rust"`) yang **tidak stabil** dan dapat berubah antar-versi compiler demi optimasi field reordering.

Untuk berkomunikasi dengan dunia luar, Rust harus menurunkan calling convention-nya ke standar platform C:
* `extern "C"`: Mengikuti spesifikasi platform C calling convention (misalnya System V AMD64 ABI pada Linux/macOS, atau Microsoft x64 calling convention pada Windows). Register CPU dialokasikan secara ketat untuk parameter dan return values.
* Stack Frame Preservation: Pemanggil (*caller*) dan yang dipanggil (*callee*) harus menyepakati siapa yang bertanggung jawab membersihkan frame stack (*caller-cleaned* vs *callee-cleaned*).

#### 3.2. Data Layout: Padding, Alignment, dan Niche Optimization
Rust secara default mengacak urutan field dalam struct (`repr(Rust)`) untuk meminimalkan padding akibat alignment data. Untuk kompatibilitas C, tata letak harus dipaksa:

```rust
// Memory representation C-compatible
#[repr(C)]
pub struct PacketHeader {
    pub magic: u16,     // 2 bytes, offset 0
    // [Padding 2 bytes] // Disisipkan compiler untuk memenuhi alignment 4-byte pada field berikutnya
    pub length: u32,    // 4 bytes, offset 4
    pub payload_ptr: *const u8, // 8 bytes (pada x86_64), offset 8
}
```

**Niche Value Optimization pada FFI:**
Tipe pointer seperti `&T`, `&mut T`, dan `core::ptr::NonNull<T>` dijamin tidak boleh null. Rust memanfaatkan bit pattern null (`0x0`) sebagai "niche" untuk merepresentasikan varian `None` pada tipe `Option`. 
Oleh karena itu, tata letak memori dari:
`Option<std::ptr::NonNull<T>>` secara biner **100% identik** dengan raw pointer `*mut T` pada C, yang dapat bernilai null. Ini memungkinkan abstraksi zero-cost yang aman.

#### 3.3. Panic Boundary & Stack Unwinding
Panic pada Rust secara default menggunakan mekanisme stack unwinding (`libunwind` pada Unix-like systems). Apabila sebuah panik melintasi batas fungsi `extern "C"` menuju runtime C:
1. Mesin unwinding Rust mencoba membongkar frame stack milik C yang tidak memiliki metadata unwinding DWARF yang kompatibel.
2. Runtime mendeteksi pelanggaran batas ABI C.
3. Terjadi **Undefined Behavior langsung**: Proses runtime akan mengalami crash seketika (*abnormal process termination* / `abort`) atau lebih buruk, merusak memory stack host C.

Oleh karena itu, setiap batas fungsi yang diekspor ke C **wajib** menangkap kepanikan di perimeter terluar:

```
[ C / Host Process ] 
       │ 
       ▼ Calling FFI function
[ Rust extern "C" Boundary ]
       │ 
       ├─► [ std::panic::catch_unwind ] ──(Boundary Firewall)
       │         │
       │         ▼ Runs Safe Rust Code
       │         [ Business Logic ] ──► (Panic Occurs!)
       │         ▲
       │         └─ Caught by Firewall (Converted to FFI Error Code)
       ▼ Return Result / Error Code (NO UNWIND CROSSES HERE)
[ C / Host Process ]
```

#### 3.4. Dual Allocator Hazard (Cross-boundary Deallocation)
Alokator memori yang digunakan oleh binary Rust runtime (misalnya `jemalloc` atau `System Allocator` Rust) belum tentu sama dengan alokator yang dipanggil oleh host executable (misalnya glibc `malloc`).
* Memori yang dialokasikan oleh Rust (`Box`, `Vec`) **hanya boleh** didealokasikan oleh Rust.
* Memori yang dialokasikan oleh C (`malloc`) **hanya boleh** didealokasikan oleh C (`free`).
Pelanggaran atas aturan ini memicu *heap corruption*, *segmentation fault*, atau *exploitable double-free vulnerabilities*.

---

### 4. Why & What

| Dimensi | Pendekatan FFI Konvensional (Naive) | Pendekatan Rust Enterprise Production |
| :--- | :--- | :--- |
| **Integrasi Kepemilikan** | Melempar raw pointer secara bebas; manual tracking status kepemilikan. | Menggunakan *Opaque Pointer Idiom* dibungkus tipe Rust `Box<T>` / `Arc<T>` yang dilindungi RAII. |
| **Penanganan Error** | Mengembalikan pointer `NULL` tanpa konteks error mendalam. | Mengembalikan enum tagged `C-compatible status codes` dipadu fungsi pengambilan status error berbasis TLS (*Thread-Local Storage*). |
| **Keamanan Thread** | Mengasumsikan host thread-safe secara implisit tanpa validasi compiler. | Menegakkan trait `Send` dan `Sync` pada batas FFI; data yang tidak aman untuk dibagi antar-thread dicegah pada compile time. |
| **Panic Handling** | Membiarkan panik terjadi, memicu segment violation dan memory dump tak terkendali. | Isolasi total menggunakan `std::panic::catch_unwind`, mengonversi *panic payload* menjadi kode kesalahan terstruktur. |
| **Validasi Kode** | Bergantung pada pengujian Black-box integration testing semata. | Pengujian bertingkat: Unit testing standar, verifikasi *Stacked Borrows* via **Miri**, dan sanitasi runtime via **AddressSanitizer**. |

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup pengembangan sistem hybrid Rust-C/C++ melibatkan lima tahap pipeline produksi:

```
[ Phase 1: Interface Definition ]
       │  Definisikan C Header (.h) atau Rust FFI API surface.
       ▼
[ Phase 2: ABI Stabilization ]
       │  Bungkus struct dengan #[repr(C)], gunakan opaque type handles.
       │  Pastikan semua parameter mematuhi C types (c_char, c_int, uint64_t).
       ▼
[ Phase 3: Defensive Wrapper Construction ]
       │  1. Tangkap pointer null via NonNull / pointer check.
       │  2. Pasang firewall catch_unwind.
       │  3. Kelola alokasi via Box::into_raw / Box::from_raw.
       ▼
[ Phase 4: Ergonomic Safe API Layer ]
       │  Buat wrapper Rust yang menerapkan Drop, Deref, Clone, Send, Sync.
       │  Sembunyikan seluruh blok unsafe dari modul publik aplikasi.
       ▼
[ Phase 5: Verification & Audit Pipeline ]
       │  cargo miri test (Verifikasi UB & aliasing)
       │  RUSTFLAGS="-Zsanitizer=address" cargo test (Validasi memory leak)
```

---

### 6. Analogy & Diagram ASCII

Bayangkan FFI seperti **Kedutaan Besar Antara Dua Negara Berdaulat**.

* **Negara Rust**: Wilayah dengan undang-undang keselamatan ketat, polisi kepemilikan (Borrow Checker) mengawasi setiap pergerakan warga (data), dan melarang membawa senjata berbahaya secara bebas.
* **Negara C**: Wilayah tanpa aturan hukum terpusat (Wild West); siapa saja bisa memegang senjata (raw pointer) dan mengarahkannya ke mana saja.
* **Pos Perbatasan (FFI Boundary)**: 
  * Rust tidak boleh membiarkan warga C masuk begitu saja tanpa pemeriksaan paspor (*null pointer check* & *alignment check*).
  * Masalah internal negara Rust (kerusuhan/panic) tidak boleh tumpah melintasi perbatasan ke negara C; harus diselesaikan di pos keamanan (*panic firewall* via `catch_unwind`).
  * Uang/Barang yang dipinjam dari perbatasan (alokasi memori) harus dikembalikan ke pos yang sama untuk dimusnahkan (*allocator separation*).

```
                      BOUNDARY DESK (extern "C")
      RUST RUNTIME                                    C RUNTIME
┌──────────────────────────┐               ┌──────────────────────────┐
│   Safe Domain Logic      │               │     Host C Executable    │
│  (Borrow Checker rules)  │               │    (Direct memory ops)   │
└────────────┬─────────────┘               └─────────────┬────────────┘
             │                                           │
             ▼                                           │
┌──────────────────────────┐                             │
│   Box<NativeState>       │                             │
│   (Owned allocation)     │                             │
└────────────┬─────────────┘                             │
             │ Box::into_raw()                           │
             ▼                                           │
┌──────────────────────────┐                             │
│   Opaque Handle Token    │ ─── Export Handle Value ──► │ Receives:  │
│   (Raw pointer *mut T)   │     via C-Compatible API    │ native_handle_t
└──────────────────────────┘                             │ (void*)
             ▲                                           │
             │ Box::from_raw()                           │
             │ (Reclaim Ownership)                       │
┌────────────┴─────────────┐                             │
│   Destructor Invocation  │ ◄── Trigger Free Handle ────┘ Calls:
│   (Drop implementation)  │     via C-Compatible API      engine_destroy()
└──────────────────────────┘
```

---

### 7. Implementation: Simple vs Practical Example

#### 7.1. Simple Example: Safe Opaque Handle & Panic Boundary
Contoh dasar bagaimana mengekspor state Rust ke C secara aman menggunakan pola opaque pointer dan *catch_unwind*.

```rust
use std::ffi::c_int;
use std::panic::catch_unwind;
use std::ptr;

// Struct internal yang tidak diketahui layout-nya oleh C (Opaque)
pub struct SecureEngine {
    counter: u64,
}

#[repr(C)]
pub enum FfiResult {
    Ok = 0,
    NullPointerPassed = -1,
    ExecutionPanicked = -2,
}

/// Mengalokasikan instance SecureEngine baru dan mengembalikan raw pointer sebagai handle opaque
#[no_mangle]
pub extern "C" fn secure_engine_new(out_engine: *mut *mut SecureEngine) -> FfiResult {
    let result = catch_unwind(|| {
        if out_engine.is_null() {
            return FfiResult::NullPointerPassed;
        }

        let engine = Box::new(SecureEngine { counter: 0 });
        // Lepas kepemilikan memory ke C sebagai raw pointer
        unsafe {
            *out_engine = Box::into_raw(engine);
        }
        FfiResult::Ok
    });

    result.unwrap_or(FfiResult::ExecutionPanicked)
}

/// Menjalankan mutasi internal state secara aman
#[no_mangle]
pub extern "C" fn secure_engine_increment(engine: *mut SecureEngine) -> FfiResult {
    let result = catch_unwind(|| {
        if engine.is_null() {
            return FfiResult::NullPointerPassed;
        }

        // SAFETY: Memastikan pointer tidak null dan valid sebelum didereferensikan.
        // Rust menjamin pointer ini eksklusif selama eksekusi fungsi ini.
        unsafe {
            let engine_ref = &mut *engine;
            engine_ref.counter += 1;
        }

        FfiResult::Ok
    });

    result.unwrap_or(FfiResult::ExecutionPanicked)
}

/// Membebaskan memori yang dialokasikan oleh Rust
#[no_mangle]
pub extern "C" fn secure_engine_destroy(engine: *mut SecureEngine) -> FfiResult {
    let result = catch_unwind(|| {
        if engine.is_null() {
            return FfiResult::NullPointerPassed;
        }

        // SAFETY: Rekonstruksi Box untuk memicu deallocation menggunakan Rust Global Allocator.
        unsafe {
            drop(Box::from_raw(engine));
        }

        FfiResult::Ok
    });

    result.unwrap_or(FfiResult::ExecutionPanicked)
}
```

---

#### 7.2. Practical Example: Zero-Copy Ring Buffer Consumer Wrapper (Safe Enterprise Layer)
Kasus riil: Mengonsumsi library C native performa tinggi (misal driver hardware/ring buffer jaringan) ke dalam abstraksi idiomatis Rust yang zero-cost, thread-safe, dan mengeksploitasi RAII.

##### File: `native_ring_buffer.h` (Representasi C)
```c
typedef struct ring_buffer_t ring_buffer_t;

typedef struct {
    uint64_t sequence;
    const uint8_t* data;
    size_t len;
} ring_packet_t;

ring_buffer_t* ring_buffer_init(size_t capacity);
int ring_buffer_poll(ring_buffer_t* rb, ring_packet_t* out_pkt);
void ring_buffer_release_packet(ring_buffer_t* rb, uint64_t sequence);
void ring_buffer_free(ring_buffer_t* rb);
```

##### File: `src/ffi.rs` (Deklarasi Bindings Tingkat Rendah)
```rust
use std::ffi::c_int;

#[repr(C)]
pub struct CRingBuffer {
    _private: [u8; 0], // Mencegah inisialisasi langsung oleh pengguna Rust
}

#[repr(C)]
pub struct CPacket {
    pub sequence: u64,
    pub data: *const u8,
    pub len: usize,
}

extern "C" {
    pub fn ring_buffer_init(capacity: usize) -> *mut CRingBuffer;
    pub fn ring_buffer_poll(rb: *mut CRingBuffer, out_pkt: *mut CPacket) -> c_int;
    pub fn ring_buffer_release_packet(rb: *mut CRingBuffer, sequence: u64);
    pub fn ring_buffer_free(rb: *mut CRingBuffer);
}
```

##### File: `src/safe_engine.rs` (Arsitektur Wrapper Produksi)
```rust
use crate::ffi;
use std::marker::PhantomData;
use std::ptr::NonNull;
use std::slice;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum RingBufferError {
    #[error("Inisialisasi buffer native gagal (alokasi memori habis)")]
    InitializationFailed,
    #[error("Tidak ada paket baru pada antrean (ring buffer empty)")]
    BufferEmpty,
    #[error("Kegagalan I/O internal driver C: kode {0}")]
    DriverError(i32),
}

/// Paket yang dipinjam langsung dari memori C tanpa alokasi / penyalinan data (Zero-Copy)
pub struct LeasedPacket<'a> {
    buffer_ptr: NonNull<ffi::CRingBuffer>,
    sequence: u64,
    payload: &'a [u8],
    _marker: PhantomData<&'a ()>, // Mengikat masa hidup paket ke buffer induk
}

impl<'a> LeasedPacket<'a> {
    #[inline(always)]
    pub fn payload(&self) -> &[u8] {
        self.payload
    }

    #[inline(always)]
    pub fn sequence(&self) -> u64 {
        self.sequence
    }
}

impl<'a> Drop for LeasedPacket<'a> {
    fn drop(&mut self) {
        // Otomatis mengembalikan slot packet ke ring buffer C ketika struct keluar dari scope
        unsafe {
            ffi::ring_buffer_release_packet(self.buffer_ptr.as_ptr(), self.sequence);
        }
    }
}

/// Wrapper tingkat tinggi thread-safe di atas C Ring Buffer
pub struct NativeRingConsumer {
    handle: NonNull<ffi::CRingBuffer>,
}

// Menegaskan properti thread-safety.
// SAFETY: Handle internal C terisolasi dan driver C yang mendasarinya aman
// untuk dipindahkan antar-thread (Send), namun tidak aman diakses bersamaan secara mutabel (tidak Sync).
unsafe impl Send for NativeRingConsumer {}

impl NativeRingConsumer {
    pub fn new(capacity: usize) -> Result<Self, RingBufferError> {
        let raw_ptr = unsafe { ffi::ring_buffer_init(capacity) };
        let handle = NonNull::new(raw_ptr).ok_or(RingBufferError::InitializationFailed)?;

        Ok(Self { handle })
    }

    /// Mengambil paket berikutnya dengan jaminan zero-copy lifetime
    pub fn poll_next(&mut self) -> Result<LeasedPacket<'_>, RingBufferError> {
        let mut raw_packet = ffi::CPacket {
            sequence: 0,
            data: std::ptr::null(),
            len: 0,
        };

        let status = unsafe {
            ffi::ring_buffer_poll(self.handle.as_ptr(), &mut raw_packet)
        };

        match status {
            0 => {
                if raw_packet.data.is_null() && raw_packet.len > 0 {
                    return Err(RingBufferError::DriverError(-99)); // Guard corrupt pointer
                }

                // SAFETY: C driver menjamin bahwa pointer `data` valid sepanjang
                // masa hidup hingga `ring_buffer_release_packet` dipanggil oleh RAII drop.
                let slice = unsafe {
                    if raw_packet.len == 0 {
                        &[]
                    } else {
                        slice::from_raw_parts(raw_packet.data, raw_packet.len)
                    }
                };

                Ok(LeasedPacket {
                    buffer_ptr: self.handle,
                    sequence: raw_packet.sequence,
                    payload: slice,
                    _marker: PhantomData,
                })
            }
            1 => Err(RingBufferError::BufferEmpty),
            err_code => Err(RingBufferError::DriverError(err_code)),
        }
    }
}

impl Drop for NativeRingConsumer {
    fn drop(&mut self) {
        // SAFETY: Membebaskan buffer C secara pasti saat engine Rust di-drop
        unsafe {
            ffi::ring_buffer_free(self.handle.as_ptr());
        }
    }
}
```

---

### 8. Real World Case Study: Ultra-Low Latency Order Matching Integration

#### Latar Belakang & Masalah
Sebuah institusi bursa finansial memiliki legacy C/C++ Engine yang berjalan langsung di atas kernel-bypass Network Card (Solarflare OpenOnload). Sistem ini memproses order limit buku pasar (LOB). 
Perusahaan perlu memodernisasi modul **Risk & Compliance Pre-Trade Checks** menggunakan Rust guna menjamin konkurensi data race-free tanpa menaikkan *tick-to-trade latency*.

#### Arsitektur Solusi
Modul Rust dikompilasi menjadi C-Dynamic Library (`.so`) dan di-link secara native ke runtime C++:
1. **Zero-Allocation Interface**: Modul C++ mengalokasikan struct input pada CPU cache-line (64 bytes aligned). Rust melakukan komputasi murni tanpa heap allocation sama sekali.
2. **Panic Containment**: Segala kemungkinan panik dibendung di level ABI untuk mencegah matinya matching engine pusat.
3. **Thread Safety Guarantees**: Melindungi Shared Risk Context menggunakan Lock-Free Atomic Sync primitive lintas FFI.

```
       C++ Matching Engine Thread (Core pinned)
                        │
                        ▼ (Zero-copy in-register call)
            rust_evaluate_order_risk(...)
                        │
         ┌──────────────┴──────────────┐
         │ std::panic::catch_unwind    │
         │                             │
         │ Verify Limits               │
         │ (SIMD Array Check)          │
         │                             │
         │ Atomic CAS State Update     │
         └──────────────┬──────────────┘
                        │
                        ▼ Returns uint32_t RiskBitmask (Latency < 80ns)
       C++ Matching Engine Resumes Execution
```

#### Kode Implementasi Inti

```rust
use std::sync::atomic::{AtomicU64, Ordering};
use std::panic::catch_unwind;

#[repr(C, align(64))] // Dipaksa sejajar dengan CPU Cache Line
pub struct OrderDetails {
    pub account_id: u64,
    pub symbol_id: u32,
    pub price: u64,
    pub quantity: u32,
    pub side: u8, // 1 = Buy, 2 = Sell
    pub _reserved: [u8; 39], // Mengisi tepat 64 bytes
}

#[repr(C)]
pub struct AccountRiskState {
    pub max_notional_limit: u64,
    pub current_allocated_exposure: AtomicU64,
}

#[repr(u32)]
pub enum RiskDecision {
    Approved = 0,
    ExposureLimitExceeded = 1,
    InvalidOrderParameters = 2,
    PanicCatastrophe = 99,
}

#[no_mangle]
pub extern "C" fn rust_evaluate_order_risk(
    order: *const OrderDetails,
    risk_state: *const AccountRiskState,
) -> RiskDecision {
    // Penanganan panic wajib ada di level boundary
    let result = catch_unwind(|| {
        if order.is_null() || risk_state.is_null() {
            return RiskDecision::InvalidOrderParameters;
        }

        // SAFETY: Pointer telah divalidasi non-null, data di-pass oleh C++ engine
        // yang menjamin masa hidup objek selama durasi synchronous function call.
        let order = unsafe { &*order };
        let risk = unsafe { &*risk_state };

        let order_notional = match order.price.checked_mul(order.quantity as u64) {
            Some(val) => val,
            None => return RiskDecision::InvalidOrderParameters,
        };

        // Lock-free optimistic CAS concurrency check
        let mut current_exp = risk.current_allocated_exposure.load(Ordering::Relaxed);
        loop {
            let new_exp = current_exp.saturating_add(order_notional);
            if new_exp > risk.max_notional_limit {
                return RiskDecision::ExposureLimitExceeded;
            }

            match risk.current_allocated_exposure.compare_exchange_weak(
                current_exp,
                new_exp,
                Ordering::AcqRel,
                Ordering::Relaxed,
            ) {
                Ok(_) => break,
                Err(actual) => current_exp = actual,
            }
        }

        RiskDecision::Approved
    });

    result.unwrap_or(RiskDecision::PanicCatastrophe)
}
```

---

### 9. Trade-offs

| Pendekatan / Keputusan Arsitektur | Keuntungan | Biaya / Trade-off | Dampak Terhadap Skalabilitas & Biaya |
| :--- | :--- | :--- | :--- |
| **Zero-Copy Borrows (`&'a [u8]`) vs Cloning (`Vec<u8>`)** | Latensi mikroskopik; nol alokasi heap di hot-path; eliminasi GC/allocator overhead. | Kompleksitas *lifetime analysis*; risiko dangling pointer jika host C membebaskan memori sebelum Rust selesai. | Mengurangi konsumsi memori dan menaikkan throughput data transfer secara linier terhadap beban core CPU. |
| **`std::panic::catch_unwind` pada Setiap Ekspor ABI** | Mencegah hard crash pada host C++ engine; sistem resilient terhadap edge-case bug Rust. | Overhead runtime sekitar 20-40 CPU cycles per pemanggilan fungsi untuk menyiapkan frame unwind tables. | Trade-off latensi minor (nanodetik) untuk mencegah *downtime* fatal pada sistem finansial mission-critical. |
| **Opaque Pointer Pattern (`Box::into_raw`)** | Isolasi total internal Rust struct; pemecahan ABI break tanpa perlu rekompilasi binary C. | Setiap pembuatan instance objek membutuhkan 1x heap allocation di sisi Rust allocator. | Menambah beban allocator saat object churning tinggi; mitigasi dengan pooling allocator (arena). |
| **Penggunaan Bindgen Otomatis vs Penulisan FFI Manual** | Mempercepat integrasi ribuan fungsi dan struct dari C header library besar. | Dapat menghasilkan tipe wrapper mentah yang tidak ergonomis, memunculkan unsafe secara luas di aplikasi jika tidak ditapis. | Biaya engineering awal rendah, namun meningkatkan hutang teknis jika tidak segera dibuatkan safe idiomatic layer. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Mismatched Allocator Free (Undefined Behavior)
```rust
// KESALAHAN FATAL:
#[no_mangle]
pub extern "C" fn allocate_rust_buffer(size: usize) -> *mut u8 {
    let mut vec = Vec::with_capacity(size);
    let ptr = vec.as_mut_ptr();
    std::mem::forget(vec); // Mengabaikan kapasitas dan deallokasi
    ptr
}
// Host C memanggil: free(ptr); 
// AKIBAT: HEAP CORRUPTION! glibc free() membebaskan pointer yang dialokasikan oleh jemalloc milik Rust.

// SOLUSI BENAR:
#[no_mangle]
pub extern "C" fn free_rust_buffer(ptr: *mut u8, size: usize) {
    if !ptr.is_null() {
        unsafe {
            // Rekonstruksi Vec dengan panjang dan kapasitas identik
            let _ = Vec::from_raw_parts(ptr, size, size);
        } // Drop membersihkan memori menggunakan alokator Rust yang sama
    }
}
```

#### 10.2. Aliasing Invariant Violation (Stacked Borrows Violations)
```rust
// KESALAHAN FATAL:
pub unsafe fn process_bad(ptr: *mut u32) {
    let ref1 = &mut *ptr;
    let ref2 = &mut *ptr; // KESALAHAN BESAR! Dua &mut aktif secara bersamaan pada lokasi yang sama.
    *ref1 = 10;
    *ref2 = 20; // Compiler Rust berasumsi ref1 tidak berubah, memicu optimasi liar / miskompilasi.
}

// TROUBLESHOOTING DENGAN MIRI:
// Jalankan: cargo miri test
// Output Miri:
// error: Undefined Behavior: trying to reborrow <tag> for Unique permission at AllocId(...), but that tag does not exist in the borrow stack
```

#### 10.3. Meneruskan Rust Slice `&[T]` Langsung ke C Calling Convention
```rust
// KESALAHAN:
#[no_mangle]
pub extern "C" fn bad_slice_pass(data: &[u8]) { ... }
// &[u8] pada Rust adalah fat-pointer (pointer 8 byte + panjang 8 byte). 
// C tidak mengerti tata letak fat-pointer ini dan memetakan register CPU secara keliru!

// SOLUSI BENAR:
#[no_mangle]
pub extern "C" fn good_slice_pass(data: *const u8, len: usize) { ... }
```

---

### 11. Best Practices & Production Checklist

- [ ] **ABI Stability Checklist:**
  - [ ] Setiap struct yang dikirimkan/diterima melintasi batas FFI didekorasi dengan atribut `#[repr(C)]` atau `#[repr(transparent)]`.
  - [ ] Tidak ada tipe `extern "Rust"` (seperti `String`, `Vec`, tuple mentah, atau `&str`) yang terekspos langsung di fungsi `extern "C"`.
- [ ] **Safety & Invariant Checklist:**
  - [ ] Semua fungsi ekspor Rust mengimplementasikan `std::panic::catch_unwind` pada blok perimeter pertama.
  - [ ] Pointer input diperiksa validitasnya terhadap null (`ptr.is_null()`) sebelum dikonversi menjadi reference Rust (`&*ptr` atau `&mut *ptr`).
  - [ ] Data raw pointer dipetakan ke struct opaque dengan wrapping `NonNull<T>`.
  - [ ] Trait `Drop` diimplementasikan secara eksplisit untuk setiap wrapper alokasi C demi mengeliminasi *resource leak*.
- [ ] **Tooling & CI/CD Verification:**
  - [ ] Skrip validasi pipeline mengeksekusi `cargo miri test` untuk memvalidasi ketiadaan *Undefined Behavior* pada seluruh test suite unsafe.
  - [ ] Integrasikan AddressSanitizer pada job pipeline: `RUSTFLAGS="-Zsanitizer=address" cargo test --target x86_64-unknown-linux-gnu`.

---

### 12. Hands-on Practice

Buat dan uji safe wrapper di atas sistem call C POSIX `clock_gettime`.

#### Struktur Direktori
```text
hands-on/m02/
├── Cargo.toml
└── src/
    ├── ffi.rs
    ├── lib.rs
    └── safe_clock.rs
```

#### Langkah 1: Siapkan `hands-on/m02/Cargo.toml`
```toml
[package]
name = "enterprise-ffi-posix"
version = "0.1.0"
edition = "2021"

[dependencies]
thiserror = "1.0"

[dev-dependencies]
```

#### Langkah 2: Definisikan Pemetaan C POSIX pada `hands-on/m02/src/ffi.rs`
```rust
use std::ffi::c_int;

pub const CLOCK_MONOTONIC: c_int = 1;
pub const CLOCK_REALTIME: c_int = 0;

#[repr(C)]
#[derive(Debug, Copy, Clone, Default)]
pub struct Timespec {
    pub tv_sec: i64,
    pub tv_nsec: i64,
}

extern "C" {
    pub fn clock_gettime(clk_id: c_int, tp: *mut Timespec) -> c_int;
}
```

#### Langkah 3: Bangun Safe Wrapper Terisolasi pada `hands-on/m02/src/safe_clock.rs`
```rust
use crate::ffi::{self, Timespec};
use std::time::Duration;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ClockError {
    #[error("Gagal membaca timer sistem: POSIX return code {0}")]
    SystemTimeFailure(i32),
    #[error("Waktu terdeteksi mundur secara anomalik")]
    NegativeTimeDetected,
}

pub enum ClockSource {
    Monotonic,
    Realtime,
}

pub struct SystemPreciseClock;

impl SystemPreciseClock {
    pub fn now(source: ClockSource) -> Result<Duration, ClockError> {
        let clock_id = match source {
            ClockSource::Monotonic => ffi::CLOCK_MONOTONIC,
            ClockSource::Realtime => ffi::CLOCK_REALTIME,
        };

        let mut ts = Timespec::default();

        // SAFETY: Pointer ke stack memory lokal valid dan berukuran tepat sesuai spesifikasi POSIX timespec.
        let result = unsafe { ffi::clock_gettime(clock_id, &mut ts) };

        if result != 0 {
            return Err(ClockError::SystemTimeFailure(result));
        }

        if ts.tv_sec < 0 || ts.tv_nsec < 0 {
            return Err(ClockError::NegativeTimeDetected);
        }

        Ok(Duration::new(ts.tv_sec as u64, ts.tv_nsec as u32))
    }
}
```

#### Langkah 4: Tulis Unit Test pada `hands-on/m02/src/lib.rs`
```rust
pub mod ffi;
pub mod safe_clock;

#[cfg(test)]
mod tests {
    use super::safe_clock::*;
    use std::thread::sleep;
    use std::time::Duration;

    #[test]
    fn test_monotonic_clock_progression() {
        let t1 = SystemPreciseClock::now(ClockSource::Monotonic).expect("Pembacaan clock 1 harus berhasil");
        sleep(Duration::from_millis(10));
        let t2 = SystemPreciseClock::now(ClockSource::Monotonic).expect("Pembacaan clock 2 harus berhasil");

        assert!(t2 > t1, "Monotonic clock harus selalu bergerak maju");
    }
}
```

#### Langkah 5: Eksekusi Uji Coba Formal
Jalankan pengujian menggunakan Cargo standar dan validasi via Miri:
```bash
cargo test
cargo miri test
```

---

### 13. Exercises

#### Level Easy
Buat safe wrapper idiomatic Rust untuk fungsi C POSIX `getpid` dan `getppid` (`extern "C" { fn getpid() -> i32; fn getppid() -> i32; }`). Pastikan fungsi mengembalikan tipe bentukan baru (`struct ProcessId(pub u32)`) yang aman dan tidak dapat bernilai negatif.

#### Level Medium
Kembangkan library C-FFI yang mengekspos struktur data **Thread-Safe Key-Value Store** sederhana (berbasis `std::sync::RwLock<HashMap<String, String>>`). Sediakan fungsi ekspor C:
1. `kv_store_create() -> *mut KvStore`
2. `kv_store_set(store: *mut KvStore, key: *const c_char, val: *const c_char) -> c_int`
3. `kv_store_get(store: *mut KvStore, key: *const c_char, out_buf: *mut c_char, max_len: usize) -> c_int`
4. `kv_store_destroy(store: *mut KvStore)`
Pastikan konversi `CStr` aman dari input `NULL` dan pasang proteksi `catch_unwind`.

#### Level Hard
Rancang arsitektur integrasi inter-process communication (IPC) menggunakan **Shared Memory POSIX (`shm_open`, `mmap`)** antara Rust dan C++. Bangun safe wrapper zero-copy yang mampu mengabstraksikan shared memory region tersebut menjadi struct bertipe safe Rust `SharedRingBuffer<T: Copy>` yang menyinkronkan write dan read index menggunakan CPU atomics (`AtomicU64`) tanpa lock (lock-free queue). Buktikan tidak ada memory aliasing violation menggunakan tool Miri.

---

### 14. Challenge

**Skenario Tantangan:**
Sebuah gateway telekomunikasi generasi baru menuntut modul parser protokol berkecepatan tinggi yang ditulis dalam Rust untuk disematkan ke dalam arsitektur server multithreaded C legacy (*event-driven architecture* berbasis Linux `epoll`). 

**Spesifikasi Kebutuhan:**
1. Rust mengekspor satu set fungsi C untuk parsing stream data berukuran besar secara asinkronus berbasis *chunk processing*.
2. State parser harus disimpan dalam instance opaque handle berukuran kompak (`ContextToken`).
3. Parser membutuhkan pemanggilan fungsi C callback (`callback_on_frame(context, frame_ptr, frame_len)`) setiap kali frame data berhasil didekode.
4. Host C sewaktu-waktu dapat membatalkan eksekusi dari thread berbeda, yang mengharuskan Rust menangani atomic cancellation flag secara aman.
5. Anda **dilarang keras** memicu alokasi heap (`0 alloc`) di hot loop parser; parser harus bekerja secara inplace di atas memori buffer mentah yang di-pass oleh socket C.

**Deliverable Kritis:**
* Berikan kode sumber implementasi Rust (`lib.rs`) yang mengimplementasikan callback trampoline, context pointer retention, SIMD tokenization scanning, zero-copy safety verification, dan proteksi unwinding absolut.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa alasan utama compiler Rust mengacak urutan memory offset field dalam struct bawaan (`repr(Rust)`), dan mengapa ini berbahaya untuk FFI C?
2. Mengapa raw pointer `*const T` dan `*mut T` diizinkan tidak valid, null, atau melanggar aturan alignment, sedangkan reference `&T` dan `&mut T` tidak boleh?
3. Sebutkan apa yang terjadi menurut Rust Reference jika fungsi `extern "C"` di dalam library Rust memicu panik dan panik tersebut mencapai host caller C tanpa ditangkap!
4. Jelaskan perbedaan perilaku antara `Box::into_raw` dan `Box::leak`!
5. Mengapa tipe `core::ptr::NonNull<T>` sering lebih disukai daripada `*mut T` saat mendesain safe wrapper tingkat tinggi?

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Bagaimana cara compiler mengoptimalkan tipe `Option<NonNull<T>>` sehingga memiliki ukuran memori yang sama persis dengan raw pointer `*mut T` biasa? Sebutkan nama mekanismenya!
7. Kapan kita wajib menyertakan tipe zero-sized `PhantomData<&'a T>` di dalam struct wrapper FFI?
8. Misalkan Anda menerima string C dari luar (`*const c_char`). Sebutkan tahapan lengkap yang aman untuk mengubahnya menjadi `&str` Rust yang valid!
9. Apa perbedaan esensial dari calling convention `extern "C"` dibandingkan dengan `extern "system"`?
10. Mengapa pemanggilan `libc::free()` terhadap pointer yang dialokasikan via `Box::into_raw()` berpotensi memicu Heap Corruption meskipun nilai pointernya valid?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Analitis)
11. **Skenario A:** Tim Anda menemukan service sering mengalami segfault sporadis saat integrasi Rust-C++. Debugger menunjukkan crash terjadi tepat pada instruksi movaps (SIMD alignment check). Di mana letak potensi kesalahan definisinya pada batas FFI?
12. **Skenario B:** Sebuah library C memanggil callback Rust melalui multiple OS thread secara konkruen. Pengembang menandai pointer engine sebagai `Send`, namun crash tetap terjadi di produksi saat pembacaan context. Audit arsitektural apa yang terlewatkan?
13. **Skenario C:** Tool Miri mengeluarkan peringatan: *"trying to retag from BorrowStack for Unique permission"*. Kode terlihat normal dan berjalan lancar di mesin pengembang. Mengapa Anda tidak boleh mengabaikan peringatan ini sebelum merge ke main branch?

---

### Jawaban Quiz

#### Bagian 1: Basic
1. Rust mengoptimalkan layout struct untuk meminimalkan padding akibat alignment boundary antar tipe data yang berbeda. Jika tata letak yang diacak ini dibaca oleh host C (yang mengasumsikan urutan sequential deklarasi field), host C akan salah membaca alamat memori masing-masing atribut, memicu pembacaan data sampah atau memory fault.
2. Reference (`&T`/`&mut T`) dijamin oleh compiler selalu terdefinisi (*well-defined*), menunjuk ke memori valid beralignment benar, dan mematuhi invariant aliasing Rust (no aliasing XOR no mutability). Raw pointer adalah tipe primitif mesin tanpa jaminan kontrak semantik compiler, sehingga dapat bernilai dangling, unaligned, atau null.
3. Terjadi **Undefined Behavior (UB)** secara langsung. Mekanisme stack unwinding Rust melintasi frame C ABI yang tidak kompatibel akan merusak *stack unwinding tables*, biasanya berujung pada *process aborted* seketika atau memori stack yang korup.
4. `Box::into_raw` mengonsumsi `Box` dan mengembalikan pointer mentah `*mut T`, namun kepemilikan memori tetap dapat direkonstruksi kembali sewaktu-waktu menggunakan `Box::from_raw`. Sementara `Box::leak` secara eksplisit memperpanjang masa hidup reference menjadi statis (`'static`), meminjamkan reference mutabel langsung ke heap yang dialokasikan tanpa maksud merekonstruksi kembali Box aslinya.
5. `NonNull<T>` secara inheren menjamin bahwa pointer tidak pernah null pada type system, bersifat *covariant* terhadap `T`, serta mengizinkan compiler memanfaatkan *niche value optimization* pada enum (seperti `Option<NonNull<T>>`).

#### Bagian 2: Intermediate
6. **Niche Value Optimization**. Karena `NonNull<T>` dijamin tidak pernah memiliki representasi bit nol (`0x0`), compiler Rust menggunakan pola bit nol tersebut untuk merepresentasikan varian `Option::None`. Akibatnya, `Option<NonNull<T>>` berukuran tepat 1 word (8 bytes pada arsitektur 64-bit), setara dengan `*mut T`.
7. Saat struct wrapper Rust menyimpan raw pointer (yang tidak memiliki masa hidup/lifetime bawaan), namun secara logis struktur tersebut meminjam data dari objek lain selama durasi waktu tertentu (`'a`). `PhantomData<&'a T>` menginstruksikan borrow checker untuk memberlakukan aturan siklus hidup yang ketat seolah-olah data tersebut benar-benar tersimpan di dalam struct.
8. (1) Pastikan pointer tidak null (`ptr.is_null()`). (2) Bungkus dengan `CStr::from_ptr(ptr)` dalam blok unsafe (ini akan membaca hingga byte null terminator `\0`). (3) Panggil method `.to_str()` pada objek `CStr` tersebut untuk memverifikasi validitas encoding UTF-8 string sebelum diproses sebagai `&str`.
9. `extern "C"` selalu mengikuti platform C calling convention standar. Sedangkan `extern "system"` adalah konvensi dinamis: pada platform Windows 32-bit ia berubah menjadi `extern "stdcall"` (biasa digunakan pada Win32 API), sedangkan pada sistem POSIX/Unix (dan Windows 64-bit) ia otomatis menjadi `extern "C"`.
10. Rust dapat menggunakan global custom allocator (seperti *jemalloc*, *mimalloc*, atau alokator kustom internal) yang memiliki metadata header dan bucket heap yang berbeda total dari alokator bawaan sistem C library runtime (`malloc`/`free`). Memanggil `free` dari sistem C pada blok memori milik jemalloc akan merusak struktur heap metadata alokator tersebut.

#### Bagian 3: Skenario Kasus Produksi
11. **Penyebab:** Instruksi SIMD (seperti AVX/SSE yang menggunakan register XMM/YMM) menuntut data ter-align pada kelipatan 16, 32, atau 64 bytes. Crash `movaps` mengindikasikan bahwa struct yang dipassing melintasi FFI tidak memenuhi spesifikasi alignment prosesor. Solusinya: Pastikan struct didekorasi dengan atribut keselarasan eksplisit, misal `#[repr(C, align(64))]`, dan sisi C/C++ dialokasikan menggunakan `posix_memalign` atau `aligned_alloc`.
12. **Penyebab:** Pengembang hanya menandai struct sebagai `Send` (aman dipindahkan kepemilikannya antar-thread). Namun, karena callback dipanggil dari beberapa thread C secara bersamaan terhadap satu instance context pointer yang sama, context pointer tersebut diakses secara paralel (*concurrent read/write*). Struct tersebut secara logis wajib memenuhi kontrak `Sync` dan setiap akses internal mutabel wajib diproteksi menggunakan sinkronisasi internal (seperti `Mutex`, `RwLock`, atau `Atomics`).
13. **Penyebab:** Peringatan Miri tersebut menandakan pelanggaran **Aliasing Model (Stacked Borrows)**. Meskipun kode tampak "berfungsi" normal pada level optimasi compiler rendah (`debug`), pada level optimasi rilis (`release / opt-level=3`), compiler LLVM akan mengasumsikan pointer `&mut` eksklusif tidak memiliki alias lain. Asumsi ini menyebabkan LLVM melakukan reordering instruksi baca/tulis yang memicu korupsi data non-deterministik dan *silent bugs* yang sangat sulit dilacak di lingkungan produksi.

---

### 16. Summary

Mengembangkan antarmuka tingkat rendah (*Foreign Function Interface*) dan kode *unsafe* pada standar industri enterprise bukan sekadar mematikan borrow checker via blok `unsafe { ... }`. Pendekatan ini merupakan arsitektur pembangunan sistem defensif yang menuntut:
1. **Disiplin ABI yang Ketat:** Penerapan konsisten `#[repr(C)]`, pemahaman stack frame preservation, serta pemanfaatan *niche optimization* untuk menjamin keselarasan representasi biner tanpa kompromi.
2. **Karantina Sumber Daya & Kesalahan:** Menghalau stack unwinding melintasi batas pemanggilan fungsi via perimeter `catch_unwind`, serta isolasi siklus alokasi/deallokasi memori antara runtime Rust dan host C.
3. **Ergonomic Safe Enkapsulasi:** Menelan kerumitan unsafe raw pointer di dalam safe wrapper abstraction yang mengeksploitasi idiom Rust modern seperti RAII (`Drop`), `NonNull<T>`, dan zero-sized lifetime markers (`PhantomData`).
4. **Verifikasi Statis & Dinamis Lanjutan:** Validasi absolut ketiadaan *Undefined Behavior* sebelum fase deployment produksi dengan memanfaatkan compiler sanitizer dan model verifikasi borrow-stacking formal via **Miri**.