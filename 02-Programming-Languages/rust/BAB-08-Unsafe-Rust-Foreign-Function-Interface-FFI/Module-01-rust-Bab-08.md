# MODUL PEMBELAJARAN: UNSAFE RUST & FOREIGN FUNCTION INTERFACE (FFI)
**Kategori:** 02-Programming-Languages | **Kurikulum:** Rust | **Bab 08 — Modul 01**

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** RUST-08-01
* **Judul Modul:** Unsafe Rust & Foreign Function Interface (FFI)
* **Tingkat Kesulitan:** Advanced / Systems-Level
* **Prasyarat Teknis:** 
  * Pemahaman mendalam tentang *Ownership*, *Borrowing*, dan *Lifetimes* (Bab 03).
  * Pemahaman tentang tata letak memori (*Stack*, *Heap*, representasi *Struct*).
  * Pengalaman dasar dengan bahasa pemrograman C (pointer, header file, alokasi dinamis).
* **Alokasi Waktu Pembelajaran:** 8 - 10 Jam (Teori, Bedah Kode, dan Praktikum Mandiri).
* **Target Ekosistem Tooling:** Rust 2021 Edition (stable), `cargo`, `rustc`, `miri`, `clang` / GCC, `bindgen`, `cbindgen`.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mengisolasi 5 Unsafe Superpowers:** Mengidentifikasi batasan yang dilonggarkan oleh *compiler* di dalam blok `unsafe` tanpa mengorbankan keamanan sistem secara keseluruhan.
2. **Mengelola Raw Pointers Secara Deterministik:** Membedakan semantik `*const T` dan `*mut T` dari referensi aman (`&T` dan `&mut T`), serta melakukan dereferensi pointer secara aman dengan mematuhi aturan perataan memori (*alignment*) dan *nullability*.
3. **Merancang Antarmuka FFI Dua Arah (Bidirectional):** Mengimpor fungsi C ke dalam Rust secara aman dan mengekspor fungsi Rust ke pustaka C dengan mematuhi *Calling Convention* dan *Application Binary Interface* (ABI) yang stabil.
4. **Menerapkan Kontrak Safety Invariant:** Merancang abstraksi API aman (*safe abstraction boundary*) di atas kode `unsafe`, mendokumentasikan klausa `# Safety`, dan menegakkan pra-kondisi matematis untuk mencegah *Undefined Behavior* (UB).
5. **Mendeteksi Memory Bugs dengan Tooling Modern:** Mengidentifikasi pelanggaran *Aliasing Rules* (Stacked Borrows), *Use-After-Free*, *Double Free*, dan *Data Races* menggunakan **Miri** dan **AddressSanitizer (ASan)**.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Unsafe Rust Bukanlah Pintu Belakang untuk Menulis Kode C di Rust
Salah satu miskonsepsi terbesar pengembang sistem adalah menganggap `unsafe` sebagai instruksi untuk menonaktifkan *type checker* atau *borrow checker*. Realitanya:

> **Hukum Konservasi Safety Rust:**
> Blok `unsafe` tidak mematikan *borrow checker*, tidak menonaktifkan pengecekan tipe statis, dan tidak membatalkan analisis *lifetime*. Blok `unsafe` hanya memberikan Anda **5 kapabilitas tambahan (Superpowers)** yang kebenarannya tidak dapat dibuktikan secara matematis oleh kompilator pada waktu kompilasi (*compile-time*).

Mental model yang benar:
1. **Pergeseran Tanggung Jawab Pembuktian Formal:** Di safe Rust, *compiler* bertanggung jawab membuktikan bahwa kode Anda bebas dari *Undefined Behavior*. Di unsafe Rust, **Anda (manusia)** bertindak sebagai verifikator formal yang menjamin kepada *compiler* bahwa kode tersebut tidak melanggar aturan sistem.
2. **The Safe Boundary Capsule:** Unsafe Rust harus dibungkus dalam kapsul yang rapat. Pengguna kode Anda di safe Rust tidak boleh dapat memicu *Undefined Behavior*, tidak peduli argumen apa pun yang mereka teruskan ke fungsi publik Anda. Jika safe Rust bisa memicu *crash* memori (UB) melalui API Anda, maka API Anda mengalami cacat desain (*unsound*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Batas Kapsulasi Safe vs Unsafe vs FFI

```text
+-------------------------------------------------------------------------------+
| SAFE RUST APPLICATION SPACE                                                   |
| - Garansi Compile-time: No UB, Borrow Checking, Strict Lifetimes             |
|                                                                               |
|   let mut ring_buffer = SafeRingBuffer::new(1024);                            |
|   ring_buffer.push(data); // Safe API Boundary                                |
+---------------------------------------+---------------------------------------+
                                        |  (Safe Invariants Maintained)
                                        v
+-------------------------------------------------------------------------------+
| SAFE ABSTRACTION WRAPPER (Rust Internal)                                      |
|                                                                               |
|   pub fn push(&mut self, val: T) {                                            |
|       unsafe {                                                                |
|           // UNSAFE SUPERPOWERS APPLIED HERE                                  |
|           // 1. Raw Pointer Dereference                                       |
|           // 2. FFI Call to C Library                                         |
|           self.raw_push_internal(val);                                        |
|       }                                                                       |
|   }                                                                           |
+---------------------------------------+---------------------------------------+
                                        |  (C ABI / Unsafe FFI Boundary)
                                        v
+-------------------------------------------------------------------------------+
| FOREIGN FUNCTION INTERFACE (C Native ABI / Shared Library)                   |
| - Layout: #[repr(C)]                                                          |
| - Calling Convention: extern "C" (System V AMD64 / MS ABI)                   |
|                                                                               |
|   int ring_buffer_push_c(void* ctx, const uint8_t* ptr, size_t len);          |
+-------------------------------------------------------------------------------+
```

### 2. Alur Transisi Data: Safe Rust -> FFI -> C Library

```text
[Rust Memory Space]                             [C Library Space]
  Vec<u8> (Pointer, Capacity, Length)
       |
       | .as_ptr() / .len()
       v
  *const u8 (Raw Pointer) ---------------------> void* buffer (Memory Address)
  usize     (Length)      ---------------------> size_t len  (Word Size Integer)
       |                                                |
       | Calling Convention (Registers: RDI, RSI)       | Eksekusi C native
       +===============================================>+ Manipulasi Pointer C
                                                        | Ret: 0 (OK) / -1 (ERR)
       +<===============================================+
       |
  Kembalian int dipetakan ke Result<(), FfiError>
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Lima Unsafe Superpowers
Di dalam blok `unsafe { ... }`, Rust hanya mengizinkan 5 hal yang dilarang di safe Rust:
1. **Melakukan dereferensi *Raw Pointers*** (`*const T`, `*mut T`).
2. **Memanggil fungsi atau method yang berstatus `unsafe`** (termasuk fungsi FFI).
3. **Mengimplementasikan `unsafe trait`** (seperti `Send` dan `Sync` secara manual).
4. **Mengubah (*mutate*) atau mengakses variabel statis yang dapat berubah (`static mut`)**.
5. **Mengakses field dari tipe `union`** (karena kompilator tidak tahu varian aktif mana yang valid).

> **PENTING:** Membaca atau membuat *raw pointer* **TIDAK** membutuhkan blok `unsafe`. Hanya operasi **dereferensi** pointer (`*raw_ptr`) yang memerlukan blok `unsafe`.

### 2. Anatomi Pointer: Referensi vs Raw Pointer

| Parameter | Referensi Aman (`&T`, `&mut T`) | Raw Pointer (`*const T`, `*mut T`) |
| :--- | :--- | :--- |
| **Nullability** | Dijamin tidak pernah `null` (Non-null optimization). | Bisa bernilai `null` (`0x0`). |
| **Alignment** | Harus selalu *aligned* sesuai dengan `align_of::<T>()`. | Bisa *unaligned* (bisa menyebabkan CPU trap pada arsitektur tertentu). |
| **Aliasing Rules** | Ketat: Multiple `&T` XOR Single `&mut T`. | Bebas: Bisa memiliki multiple `*mut T` ke alamat yang sama. |
| **Lifetimes** | Dilacak oleh *Borrow Checker* sepanjang waktu. | Tidak memiliki *lifetime*; risiko *dangling pointer* tinggi. |
| **Ukuran** | 1 Word (Thin) atau 2 Words (Fat/DST: Slice/Trait Object). | 1 Word (Thin) atau 2 Words (Fat/DST). |

### 3. Application Binary Interface (ABI) & Name Mangling
Secara default, Rust menggunakan representasi memori `#[repr(Rust)]` yang tidak stabil (*unspecified layout*). Kompilator berhak mengubah urutan field struct untuk optimasi memori dan *padding*. 

Untuk berkomunikasi dengan C:
* **`#[repr(C)]`**: Menginstruksikan `rustc` untuk menggunakan aturan tata letak memori standar platform C (C-compatible struct alignment and padding).
* **`extern "C"`**: Mengatur konvensi pemanggilan fungsi (*calling convention*) mengikuti standar platform C ABI (misalnya System V ABI pada Linux x86_64 atau Microsoft x64 pada Windows).
* **`#[no_mangle]`**: Mematikan algoritma pengacakan nama simbol (*name mangling*) Rust sehingga simbol biner dapat ditemukan oleh *linker* C dengan nama aslinya.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Undefined Behavior (UB) dalam Rust
*Undefined Behavior* bukan sekadar "program akan *crash*". UB berarti kompilator LLVM diasumsikan bekerja di bawah premis bahwa kondisi tertentu **tidak akan pernah terjadi**. Jika premis tersebut dilanggar, LLVM dapat membuang cabang logika (*dead code elimination* yang salah), menghasilkan instruksi liar, atau memicu kerentanan eksekusi arbitrer.

Operasi yang secara eksplisit menyebabkan UB di Rust:
1. Mendereferensikan pointer yang *dangling*, *null*, atau *unaligned*.
2. Melanggar aturan **Stacked Borrows / Tree Borrows** (membuat referensi `&mut T` sementara ada referensi lain yang aktif menunjuk data yang sama).
3. Menginstansiasi tipe data dengan representasi ilegal:
   * Mengisi `bool` dengan nilai selain `0` atau `1`.
   * Mengisi `char` dengan nilai di luar batas Unicode scalar value (`0x0..=0xD7FF` dan `0xE000..=0x10FFFF`).
   * Mengisi referensi `&T` dengan pointer `null`.
   * Mengisi nilai *enum* dengan diskriminan yang tidak terdefinisi.
4. *Unwinding panic* melintasi batas FFI (melalui fungsi `extern "C"` tanpa atribut `extern "C-unwind"`).
5. Terjadinya *Data Race* pada memori tanpa sinkronisasi atomik.

### 2. Model Memori Stacked Borrows
Rust mengadopsi model *Stacked Borrows* untuk memvalidasi semantik pointer. Setiap alokasi memori memiliki tumpukan izin (*permission stack*):
* `SharedReadOnly`
* `SharedReadWrite`
* `Unique`

Ketika Anda menurunkan sebuah referensi dari pointer, item baru didorong ke atas tumpukan. Jika pointer di bagian bawah tumpukan digunakan saat item di atasnya masih mengklaim akses eksklusif (`Unique`), item di atas tumpukan akan dianggap gugur (*popped/invalidated*). Mengakses kembali referensi yang sudah gugur adalah UB!

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh berikut menunjukkan:
1. Pembuatan *raw pointer* dari nilai lokal.
2. Operasi aritmatika pointer secara aman vs dereferensi unsafe.
3. Deklarasi FFI fungsi standar C (`puts` & `abs`).
4. Ekspor fungsi Rust ke C ABI dengan `#[no_mangle]`.

```rust
use std::os::raw::{c_char, c_int};

// 1. Ekspor fungsi Rust ke C dengan ABI yang stabil
#[no_mangle]
pub extern "C" fn rust_multiply(a: c_int, b: c_int) -> c_int {
    a * b
}

// 2. Deklarasi fungsi eksternal dari Standard C Library
extern "C" {
    fn puts(s: *const c_char) -> c_int;
    fn abs(i: c_int) -> c_int;
}

fn main() {
    // === A. RAW POINTERS FUNDAMENTALS ===
    let mut value: i32 = 42;

    // Pembuatan raw pointer adalah SAFE
    let raw_const: *const i32 = &value as *const i32;
    let raw_mut: *mut i32 = &mut value as *mut i32;

    println!("Alamat raw_const: {:p}", raw_const);
    println!("Alamat raw_mut:   {:p}", raw_mut);

    // Dereferensi raw pointer adalah UNSAFE
    unsafe {
        *raw_mut += 10;
        println!("Nilai baru via raw_const: {}", *raw_const);
    }

    // === B. POINTER ARITHMETIC ===
    let numbers: [u32; 3] = [100, 200, 300];
    let ptr: *const u32 = numbers.as_ptr();

    unsafe {
        // Melakukan offset pointer (menggeser pointer sebesar 1 * sizeof(u32))
        let second_ptr = ptr.add(1);
        println!("Elemen kedua: {}", *second_ptr);

        let third_ptr = ptr.offset(2);
        println!("Elemen ketiga: {}", *third_ptr);
    }

    // === C. CALLING EXTERNAL C FUNCTIONS ===
    unsafe {
        let negative_num: c_int = -99;
        let absolute = abs(negative_num);
        println!("C abs(-99) = {}", absolute);

        // Mengirimkan C-String berakhiran Null ('\0')
        let message = b"Hello from Rust through C puts!\0";
        puts(message.as_ptr() as *const c_char);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode fundamental di Seksi 07:

1. **`#[no_mangle]` (Baris 4):** Menginstruksikan kompilator untuk mempertahankan nama fungsi persis `rust_multiply` pada tabel simbol ELF/Mach-O/PE, mencegah transformasi nama seperti `_ZN4core3ptr...`.
2. **`pub extern "C" fn rust_multiply(...)` (Baris 5):** Menetapkan calling convention ke C standard ABI. Argumen diteruskan melalui register CPU yang sesuai spesifikasi arsitektur target (misalnya: register `RDI`, `RSI` pada Linux x86_64).
3. **`extern "C" { ... }` (Baris 10-13):** Blok *foreign function declaration*. Menjelaskan dependensi eksternal kepada *linker*. Fungsi di dalam blok ini otomatis diperlakukan sebagai fungsi `unsafe` karena Rust tidak dapat memvalidasi implementasi aslinya.
4. **`let raw_const: *const i32 = &value as *const i32;` (Baris 20):** *Cast* dari referensi aman ke raw pointer. Operasi ini legal di safe code karena tidak membaca isi alamat memori, hanya menyalin nilai integer alamat 64-bit/32-bit.
5. **`unsafe { *raw_mut += 10; }` (Baris 27-30):** Operasi dereferensi raw pointer. Di sinilah tanggung jawab pengembang diuji: pengembang harus menjamin `raw_mut` tidak bernilai *null*, sejajar (*aligned* terhadap kelipatan 4-byte untuk `i32`), dan tidak melanggar aturan aliasing.
6. **`ptr.add(1)` (Baris 37):** Melakukan komputasi alamat: $\text{BaseAddress} + (1 \times \text{size\_of::<u32>}())$. Fungsi `.add()` secara implisit memiliki pra-kondisi bahwa pergeseran memori tidak boleh melampaui alokasi objek buffer yang sama.
7. **`let message = b"...\0";` (Baris 49):** Array *byte string literal*. Karakter `\0` (*null terminator*) mutlak disertakan karena fungsi `puts` dalam bahasa C membaca *stream* byte hingga menemukan byte bernilai `0`. Kegagalan menyertakan `\0` akan memicu *out-of-bounds read* (buffer over-read).

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Skenario: Native Ring-Buffer Driver Integration
Anda sedang membangun sistem telemetri berkecepatan tinggi yang harus membaca paket data biner dari pustaka C warisan (*legacy C dynamic shared library*) milik vendor perangkat keras jaringan.

### Masalah Teknis
1. Vendor C mengekspos struct internal berbasis pointer buram (*opaque pointer* pattern) bernama `ring_buffer_t`.
2. Alokasi dan dealokasi memori buffer sepenuhnya dikelola oleh C (`malloc`/`free`).
3. C API mengembalikan kode galat berupa bilangan bulat bertanda (`int`), di mana `0` berarti sukses dan `< 0` menandakan kegagalan.
4. Rust harus menjamin tidak terjadi kebocoran memori (*memory leak*) ketika struct Rust keluar dari *scope*, tidak terjadi *double-free*, serta menyediakan antarmuka aman berbasis `Result<T, E>` yang sepenuhnya bebas dari kode `unsafe` bagi tim aplikasi tingkat atas.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi *Safe Abstraction Layer* untuk Ring Buffer C, menggunakan pola **RAII (Resource Acquisition Is Initialization)**:

```rust
use std::ffi::CStr;
use std::fmt;
use std::os::raw::{c_char, c_int, c_void};
use std::ptr::NonNull;

// ============================================================================
// 1. SIMULASI C ABI NATIVE LIBRARY (Secara nyata di-link via build.rs)
// ============================================================================
#[repr(C)]
pub struct CRingBuffer {
    _private: [u8; 0], // Mencegah inisialisasi langsung oleh safe Rust
}

extern "C" {
    fn c_rb_create(capacity: usize) -> *mut CRingBuffer;
    fn c_rb_destroy(rb: *mut CRingBuffer);
    fn c_rb_write(rb: *mut CRingBuffer, data: *const u8, len: usize) -> c_int;
    fn c_rb_read(rb: *mut CRingBuffer, out_buf: *mut u8, max_len: usize) -> c_int;
    fn c_rb_last_error() -> *const c_char;
}

// ============================================================================
// 2. ERROR HANDLING DOMAIN
// ============================================================================
#[derive(Debug, PartialEq, Eq)]
pub enum RingBufferError {
    AllocationFailed,
    WriteError(String),
    ReadError(String),
    InvalidBufferSize,
}

impl fmt::Display for RingBufferError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AllocationFailed => write!(f, "Gagal mengalokasikan Native RingBuffer"),
            Self::WriteError(msg) => write!(f, "Gagal menulis ke buffer: {}", msg),
            Self::ReadError(msg) => write!(f, "Gagal membaca dari buffer: {}", msg),
            Self::InvalidBufferSize => write!(f, "Ukuran buffer tidak valid"),
        }
    }
}

impl std::error::Error for RingBufferError {}

// Helper untuk membaca pesan galat dari C string
unsafe fn fetch_c_error() -> String {
    let err_ptr = c_rb_last_error();
    if err_ptr.is_null() {
        "Kesalahan tidak diketahui".to_string()
    } else {
        CStr::from_ptr(err_ptr)
            .to_string_lossy()
            .into_owned()
    }
}

// ============================================================================
// 3. SAFE RUST WRAPPER STRUCT (RAII)
// ============================================================================
pub struct SafeRingBuffer {
    // NonNull menjamin pointer tidak pernah 0x0 dan mengaktifkan
    // Null Pointer Optimization pada memori Rust.
    handle: NonNull<CRingBuffer>,
}

// Mengimplementasikan Send dan Sync dengan validasi ketat
// SAFETY: CRingBuffer di sisi native thread-safe jika dilindungi lock internal
unsafe impl Send for SafeRingBuffer {}

impl SafeRingBuffer {
    /// Membuat instance baru SafeRingBuffer.
    /// 
    /// # Errors
    /// Mengembalikan `RingBufferError::AllocationFailed` jika alokasi native gagal.
    pub fn new(capacity: usize) -> Result<Self, RingBufferError> {
        if capacity == 0 {
            return Err(RingBufferError::InvalidBufferSize);
        }

        let raw_ptr = unsafe { c_rb_create(capacity) };
        let handle = NonNull::new(raw_ptr).ok_or(RingBufferError::AllocationFailed)?;

        Ok(Self { handle })
    }

    /// Menulis slice byte aman ke buffer native C.
    pub fn write(&mut self, data: &[u8]) -> Result<usize, RingBufferError> {
        if data.is_empty() {
            return Ok(0);
        }

        let bytes_written = unsafe {
            c_rb_write(
                self.handle.as_ptr(),
                data.as_ptr(),
                data.len(),
            )
        };

        if bytes_written < 0 {
            let err_msg = unsafe { fetch_c_error() };
            Err(RingBufferError::WriteError(err_msg))
        } else {
            Ok(bytes_written as usize)
        }
    }

    /// Membaca data ke dalam slice buffer mutabel Rust.
    pub fn read(&mut self, output: &mut [u8]) -> Result<usize, RingBufferError> {
        if output.is_empty() {
            return Ok(0);
        }

        let bytes_read = unsafe {
            c_rb_read(
                self.handle.as_ptr(),
                output.as_mut_ptr(),
                output.len(),
            )
        };

        if bytes_read < 0 {
            let err_msg = unsafe { fetch_c_error() };
            Err(RingBufferError::ReadError(err_msg))
        } else {
            Ok(bytes_read as usize)
        }
    }
}

// ============================================================================
// 4. DETERMINISTIC CLEANUP (RAII)
// ============================================================================
impl Drop for SafeRingBuffer {
    fn drop(&mut self) {
        // SAFETY: self.handle dijamin non-null oleh tipe NonNull.
        // Drop dipanggil tepat sekali saat instance keluar dari scope.
        unsafe {
            c_rb_destroy(self.handle.as_ptr());
        }
    }
}

// ============================================================================
// 5. IMPLEMENTASI DUMMY STUB C AGAR KODE DAPAT DIKOMPILASI MANDIRI
// ============================================================================
#[no_mangle]
pub unsafe extern "C" fn c_rb_create(capacity: usize) -> *mut CRingBuffer {
    let layout = std::alloc::Layout::from_size_align(capacity + 8, 8).unwrap();
    let mem = std::alloc::alloc(layout);
    mem as *mut CRingBuffer
}

#[no_mangle]
pub unsafe extern "C" fn c_rb_destroy(rb: *mut CRingBuffer) {
    if !rb.is_null() {
        let layout = std::alloc::Layout::from_size_align(1024 + 8, 8).unwrap();
        std::alloc::dealloc(rb as *mut u8, layout);
    }
}

#[no_mangle]
pub unsafe extern "C" fn c_rb_write(_rb: *mut CRingBuffer, _data: *const u8, len: usize) -> c_int {
    len as c_int
}

#[no_mangle]
pub unsafe extern "C" fn c_rb_read(_rb: *mut CRingBuffer, out_buf: *mut u8, max_len: usize) -> c_int {
    if !out_buf.is_null() && max_len > 0 {
        *out_buf = 0xAA; // Isi dummy data
        1
    } else {
        -1
    }
}

#[no_mangle]
pub extern "C" fn c_rb_last_error() -> *const c_char {
    b"Buffer Out of Bounds\0".as_ptr() as *const c_char
}

// ============================================================================
// 6. SAFE CONSUMER CODE
// ============================================================================
fn main() {
    println!("Menginisialisasi Safe Ring Buffer...");
    let mut ring_buffer = SafeRingBuffer::new(1024).expect("Inisialisasi gagal");

    let payload = b"SYSTEM_TELEMETRY_PACKET_#001";
    let written = ring_buffer.write(payload).expect("Write gagal");
    println!("Berhasil menulis {} byte ke C RingBuffer.", written);

    let mut recv_buf = vec![0u8; 16];
    let read_count = ring_buffer.read(&mut recv_buf).expect("Read gagal");
    println!("Berhasil membaca {} byte: {:x?}", read_count, &recv_buf[..read_count]);

    // Ring buffer dibersihkan secara deterministik di sini via Drop!
    println!("SafeRingBuffer keluar dari scope, memory otomatis didealokasi.");
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pendekatan Arsitektur | Keuntungan | Kerugian / Risiko | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Pure Rust Rewrite** | Memory safe penuh, integrasi toolchain sempurna, inlining lintas modul optimal. | Biaya waktu dan investasi engineer sangat tinggi; risiko memperkenalkan bug logika baru. | Algoritma yang berdiri sendiri tanpa dependensi hardware spesifik. |
| **FFI dengan Raw Pointer Tipis** | Performa maksimal (nol overhead abstraksi), pemetaan langsung 1:1 ke C. | Sangat rentan UB jika dikonsumsi langsung oleh safe code; memicu duplikasi logika *safety*. | Implementasi *driver* internal tingkat rendah yang tidak diekspos keluar *crate*. |
| **Safe RAII Wrapper (Dipilih)** | Memisahkan kode unsafe dari safe API, menjamin alokasi/dealokasi dengan pola `Drop`, idiomatik. | Sedikit beban kompilasi tambahan, abstraksi tipis membutuhkan desain arsitektur yang cermat. | Integrasi pustaka pihak ketiga (C/C++), shared SDK, antarmuka driver produksi. |
| **Auto-generated via Bindgen** | Cepat, otomatisasi sinkronisasi terhadap header C (`.h`) yang terus berubah. | Menghasilkan kode wrapper mentah (`unsafe`) yang tetap membutuhkan safe layer buatan manusia. | Pustaka C dengan ratusan hingga ribuan deklarasi fungsi (misal: Vulkan, OpenSSL). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Pointer Aliasing Violation dengan `from_raw_parts_mut`
Membuat slice mutabel dari *raw pointer* adalah area rawan UB terbesar:
```rust
// PITFALL MEMATIKAN:
let mut val: u64 = 100;
let ptr = &mut val as *mut u64;

unsafe {
    // MEMBUAT DUA MUTABLE SLICE DARI POINTER YANG SAMA = INSTANT UB!
    let slice1 = std::slice::from_raw_parts_mut(ptr, 1);
    let slice2 = std::slice::from_raw_parts_mut(ptr, 1);
    slice1[0] = 10;
    slice2[0] = 20; // UB: Melanggar aturan noalias LLVM
}
```
*Aturan Emas:* Jangan pernah mengizinkan dua referensi aktif menunjuk ke memori yang tumpang tindih jika salah satunya berstatus *mutable*.

### 2. Unwinding Melintasi FFI Boundary
Jika kode Rust Anda mengalami `panic!` di dalam fungsi `extern "C"` yang dipanggil oleh lingkungan C:
* Rust runtime mencoba melakukan *stack unwinding*.
* C runtime tidak memahami frame metadata tabel unwinding milik Rust.
* **Hasil:** *Abort* seketika (*Process Terminated*) atau korupsi memori tumpukan eksekusi (*stack corruption*).
* **Solusi:** Selalu tangkap panic di batas antarmuka menggunakan `std::panic::catch_unwind`:
```rust
#[no_mangle]
pub extern "C" fn safe_c_boundary() -> i32 {
    let result = std::panic::catch_unwind(|| {
        // Logika internal Rust yang berisiko panic
        42
    });
    result.unwrap_or(-1) // Kembalikan error code ke C
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Kesalahan: Mengabaikan String Null-Terminator
```rust
// SALAH:
let c_str = "Hello".as_ptr() as *const std::os::raw::c_char;
unsafe { libc_fn(c_str); } // Akan membaca memory tak hingga sampai ketemu byte 0x00

// BENAR:
use std::ffi::CString;
let c_string = CString::new("Hello").expect("CString::new failed");
unsafe { libc_fn(c_string.as_ptr()); }
```

### 2. Kesalahan: Dangling Reference dari Pointer Transmute
```rust
// SALAH:
fn get_dangling<'a>() -> &'a i32 {
    let x = 42;
    let ptr = &x as *const i32;
    unsafe { &*ptr } // UB: x dibuang dari stack saat fungsi kembali!
}

// BENAR:
// Jangan memutus rantai lifetime analizer Rust kecuali memori dialokasikan di Heap via Box::into_raw.
```

### 3. Kesalahan: Membaca Memori yang Tidak Diinisialisasi Menggunakan `mem::uninitialized`
Metode `std::mem::uninitialized()` sudah di-*deprecate* karena instansiasi tipe seperti referensi atau struct pointer dengan nilai sampah langsung memicu UB kompilator.
```rust
// SALAH:
// let x: i32 = unsafe { std::mem::uninitialized() }; // UB!

// BENAR:
use std::mem::MaybeUninit;
let mut x: MaybeUninit<i32> = MaybeUninit::uninit();
// Inisialisasi melalui pointer
unsafe {
    x.as_mut_ptr().write(100);
    let initialized: i32 = x.assume_init();
    println!("{}", initialized);
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Dokumentasikan Prekondisi Safety Menggunakan Klausa `# Safety`:**
   Setiap fungsi yang diberi penanda `unsafe fn` **wajib** menyertakan seksi dokumentasi `# Safety` yang merinci secara matematis persyaratan yang harus dipenuhi oleh pemanggil.
   ```rust
   /// Dereferensi pointer dan menambahkan offset.
   ///
   /// # Safety
   /// 1. `ptr` tidak boleh bernilai null dan harus sejajar (aligned).
   /// 2. `ptr` harus menunjuk ke elemen valid yang dialokasikan sebesar minimal `len * sizeof(T)`.
   /// 3. Tidak boleh ada mutasi lain terhadap buffer ini selama operasi pembacaan.
   pub unsafe fn read_buffer(ptr: *const u8, len: usize) { /* ... */ }
   ```
2. **Minimalkan Cakupan Blok `unsafe`:**
   Jangan bungkus seluruh fungsi dalam blok `unsafe`. Hanya bungkus satu atau dua baris instruksi dereferensi atau pemanggilan fungsi eksternal. Ini membuat proses audit keamanan kode menjadi jelas dan terlokalisir.
3. **Gunakan Tipe Wrapper Pointer Canggih:**
   * Gunakan `std::ptr::NonNull<T>` alih-alih `*mut T` jika Anda tahu pointer tersebut tidak boleh null.
   * Gunakan `std::ffi::CStr` untuk meminjam C-string dan `std::ffi::CString` untuk memiliki alokasi C-string di Heap.
4. **Wajibkan Validasi CI Menggunakan Miri:**
   Integrasikan eksekusi Miri ke dalam pipeline CI/CD untuk mendeteksi pelanggaran izin memori tak kasat mata:
   ```bash
   cargo miri test
   ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Zero-Copy Memory Bridging dengan `MaybeUninit`
Saat mengambil blok data besar dari FFI C, jangan lakukan inisialisasi ganda (*zeroing buffer*) dengan mengalokasikan vektor berisi angka nol `vec![0u8; 1048576]`. Alokasi tersebut membebani bus memori dengan penulisan byte `0` yang sia-sia sebelum ditimpa data asli oleh fungsi C.

Gunakan `Vec::with_capacity` dan `MaybeUninit` untuk passing buffer:

```rust
use std::mem::MaybeUninit;

pub fn read_direct_from_c(capacity: usize) -> Vec<u8> {
    let mut buffer: Vec<MaybeUninit<u8>> = Vec::with_capacity(capacity);

    unsafe {
        // Pass uninitialized raw buffer ke C
        let bytes_read = c_external_reader(buffer.as_mut_ptr() as *mut u8, capacity);
        
        if bytes_read > 0 {
            // Set ukuran vector secara manual HANYA setelah dijamin
            // bahwa byte sejumlah bytes_read telah diinisialisasi oleh C
            let mut initialized_vec = std::mem::transmute::<Vec<MaybeUninit<u8>>, Vec<u8>>(buffer);
            initialized_vec.set_len(bytes_read as usize);
            initialized_vec
        } else {
            Vec::new()
        }
    }
}

// Dummy fungsi FFI simulasi
unsafe fn c_external_reader(buf: *mut u8, _cap: usize) -> isize {
    *buf = 42;
    1
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **AddressSanitizer (ASan) & LeakSanitizer:**
   Kompilasi pustaka Rust dan kode C dengan AddressSanitizer untuk mendeteksi buffer overrun dan kebocoran memori secara dinamis saat runtime:
   ```bash
   RUSTFLAGS="-Zsanitizer=address" cargo test --target x86_64-unknown-linux-gnu
   ```
2. **Defensive Boundary Validation:**
   Selalu periksa batas (*bounds checking*) sebelum melakukan konversi dari representasi pointer primitif C ke slice Rust. Validasi ukuran integer (`usize` vs `uint32_t`) untuk mencegah serangan *integer overflow* atau pemotongan nilai ukuran (*truncation bug*).
3. **C-ABI Data Alignment Hardening:**
   Selalu beri atribut `#[repr(C)]` pada setiap struct Rust yang akan dipertukarkan melintasi batas FFI. Jangan berasumsi bahwa kompilator Rust akan menata letak field sama dengan GCC atau Clang jika atribut ini tidak dipasang.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Menjalankan Interpretasi Memori Dinamis dengan Miri
Miri adalah interpreter level IR (Intermediate Representation) Rust yang mampu melacak jejak eksekusi setiap pointer terhadap model matematika *Stacked Borrows*:
```bash
# Menjalankan test case di bawah pengawasan Miri
cargo miri test
```
Jika Anda melanggar pointer aliasing, Miri akan mencetak laporan detail seperti:
```text
error: Undefined Behavior: trying to reborrow <1042> for Unique permission at alloc523, 
       but that tag does not exist in the borrow stack for this location
```

### 2. Inspeksi Simbol Biner Menggunakan `nm` dan `objdump`
Untuk memverifikasi apakah ekspor simbol ABI Anda berhasil tanpa *name mangling*:
```bash
# Periksa apakah simbol rust_multiply ada tanpa mangled prefix
nm -g target/release/libmy_library.so | grep rust_multiply
# Output:
# 0000000000005120 T rust_multiply
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Tabel Konversi Tipe C dan Rust ABI

| C Type (`stdint.h` / C standard) | Rust Equivalent (`std::os::raw` / Primitives) | Keterangan |
| :--- | :--- | :--- |
| `void*` | `*mut c_void` atau `NonNull<c_void>` | Opaque/raw pointer |
| `const char*` | `*const c_char` (Gunakan `CStr` di Rust) | String berakhiran `\0` |
| `uint8_t` | `u8` | Tipe data 8-bit unsigned |
| `int32_t` / `int` | `i32` / `c_int` | Integer bertanda 32-bit |
| `size_t` | `usize` | Ukuran pointer platform |
| `ssize_t` | `isize` | Nilai signed pointer platform |
| `typedef struct X X;` | `#[repr(C)] struct X { _priv: [u8; 0] }` | Opaque handle type |

### Ringkasan Aksi Safety
* **Pikirkan 10 kali** sebelum menulis `unsafe`. Bisakah masalah ini diselesaikan dengan `std::sync`, tipe `Arc`, `Mutex`, atau manipulasi *slice* standar?
* Kunci utama penggunaan unsafe: **Semua kode `unsafe` harus berada di balik antarmuka publik yang 100% `safe`**.
* Segala interaksi FFI dianggap `unsafe` oleh kompilator.
* Jangan pernah biarkan `panic!` merambat keluar melalui batas fungsi `extern "C"`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman Anda terhadap konsep yang telah dipelajari.

### Soal Tingkat Dasar (Basic)
1. **Sebutkan lima unsafe superpowers dalam Rust!**
2. **Apakah membuat raw pointer seperti `let ptr = &x as *const i32;` memerlukan blok `unsafe`? Jelaskan alasannya.**
3. **Mengapa penambahan atribut `#[no_mangle]` mutlak diperlukan saat mengekspor fungsi Rust ke C?**
4. **Apa fungsi dari atribut `#[repr(C)]` pada struktur data Rust?**
5. **Apa perbedaan antara tipe `*const T` dan `&T` terkait garansi nilai `null`?**

### Soal Tingkat Menengah (Intermediate)
6. **Jelaskan apa yang terjadi jika fungsi Rust yang diekspor melalui `extern "C"` memicu operasi `panic!` saat dipanggil oleh aplikasi C.**
7. **Bagaimana model *Stacked Borrows* memandang kode yang membuat referensi `&mut T` kedua dari `*mut T` sementara referensi `&mut T` pertama masih hidup?**
8. **Mengapa kita menggunakan `std::mem::MaybeUninit<T>` alih-alih fungsi lawas `std::mem::uninitialized<T>()`?**
9. **Kapan implementasi manual dari `unsafe trait Send` untuk suatu struct dibenarkan secara hukum arsitektur Rust?**
10. **Apa perbedaan fungsional antara `std::ffi::CStr` dan `std::ffi::CString`?**

---

### KUNCI JAWABAN & PENJELASAN KUIS

1. **5 Superpowers:** (1) Mendereferensikan raw pointers, (2) Memanggil unsafe functions/FFI, (3) Mengimplementasikan unsafe traits, (4) Mengubah/mengakses `static mut`, (5) Mengakses field dari `union`.
2. **Tidak.** Membuat raw pointer adalah operasi aman (*safe*). Yang berbahaya dan membutuhkan blok `unsafe` adalah operasi **dereferensi**-nya (membaca/menulis ke alamat yang ditunjuk oleh pointer tersebut), karena kompilator tidak dapat menjamin validitas alamat tersebut pada saat eksekusi.
3. **Alasan `#[no_mangle]`:** Secara default, kompilator Rust mengacak (*mangle*) nama fungsi menjadi simbol internal (misal: `_ZN7my_code13rust_multiply...`) untuk mendukung namespacing. `#[no_mangle]` memaksa *linker* menggunakan nama literal fungsi sehingga dapat ditemukan dan dipanggil oleh runtime C.
4. **Fungsi `#[repr(C)]`:** Menginstruksikan kompilator Rust untuk menata urutan memori, alignment, dan padding struct agar sama persis dengan spesifikasi compiler C di platform target. Tanpa atribut ini, layout memori struct Rust tidak terdefinisi dan dapat berubah sewaktu-waktu antar-versi kompilasi.
5. **Perbedaan Nullability:** Referensi aman `&T` dijamin secara arsitektural oleh kompilator tidak pernah bernilai `null` (memungkinkan optimasi pointer non-null). Sebaliknya, raw pointer `*const T` dapat bernilai `0x0` (*null pointer*).
6. **Akibat Panic lintas FFI:** Runtime Rust akan mencoba melakukan proses stack unwinding melewati frame stack fungsi C. Karena C ABI tidak memahami metadata *unwind* Rust, ini mengakibatkan *Undefined Behavior* atau terminasi instan (*process crash / abort*).
7. **Pandangan Stacked Borrows:** Begitu referensi mutable kedua dibuat, hak akses eksklusif referensi pertama dicabut (*popped from borrow stack*). Mencoba menulis kembali melalui referensi pertama setelah referensi kedua dibuat akan dianggap sebagai pelanggaran peminjaman dan memicu *Undefined Behavior*.
8. **Keunggulan `MaybeUninit`:** Kompilator LLVM menganggap instansiasi tipe data tertentu dengan nilai yang belum terinisialisasi sebagai status UB instan (misalnya representasi bit acak untuk pointer atau boolean). `MaybeUninit` memberi sinyal eksplisit pada kompilator bahwa memori tersebut sengaja dibiarkan belum diinisialisasi sehingga optimasi LLVM tidak membatalkannya.
9. **Kapan implementasi `Send` dibenarkan:** Ketika struct Rust membungkus raw pointer yang secara default tidak mengimplementasikan `Send`, namun kita sebagai perancang arsitektur telah memastikan dan membuktikan secara formal bahwa kepemilikan struktur tersebut aman untuk dipindahkan antar-*thread* (misalnya pointer C tersebut memiliki isolasi memori penuh dan tidak menggunakan state lokal thread).
10. **`CStr` vs `CString`:** `CString` memiliki dan mengalokasikan memori berbasis Heap sendiri yang diakhiri byte null (mirip `String`). `CStr` adalah representasi pinjaman (*borrowed slice*) dari C-string yang sudah ada di memori dan tidak mengalokasikan data baru (mirip `&str`).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Implementasi Memory Arena Allocator Kustom dengan Safe FFI Bridge

### Deskripsi Proyek
Anda diminta untuk membangun sebuah pustaka **Memory Arena Allocator** tingkat rendah. Proyek ini menggabungkan alokasi mentah, pointer arithmetic, dan pembungkusan aman (*safe encapsulation*).

### Spesifikasi Teknis:
1. **Struktur Data Native:**
   Buat struct `RawArena` yang mengalokasikan satu blok memori mentah kontinu berukuran besar menggunakan `std::alloc::alloc`.
2. **Pointer Arithmetic:**
   Implementasikan fungsi `alloc<T>(&mut self, value: T) -> *mut T` yang:
   * Menghitung alignment yang tepat untuk tipe data `T` pada posisi penunjuk arena saat ini.
   * Menempatkan `value` ke memori arena menggunakan pointer arithmetic (`std::ptr::write`).
   * Menolak alokasi dan mengembalikan null/error jika kapasitas arena terlampaui.
3. **Safe RAII Layer:**
   Bungkus `RawArena` di dalam struct aman `SafeArena` yang:
   * Mencegah alokasi melebihi kapasitas arena.
   * Menjamin semua objek yang dialokasikan di dalam arena didealokasikan secara massal saat struct `SafeArena` keluar dari *scope* (`Drop`).
4. **Verifikasi Miri:**
   Tuliskan unit test yang memvalidasi integritas pengalokasian beberapa tipe data berbeda (`u8`, `u32`, `u64`), dan pastikan seluruh test **LULUS** pengujian sanitasi memori menggunakan:
   ```bash
   cargo miri test
   ```

### Acceptance Criteria:
* Tidak ada memory leak yang terdeteksi oleh LeakSanitizer / Miri.
* Tidak ada pelanggaran *unaligned memory access* saat menyimpan struct berukuran non-standar.
* API publik dari `SafeArena` sama sekali tidak memiliki keyword `unsafe`. Semua logika manipulasi memori terisolasi sempurna di dalam implementasi internal.