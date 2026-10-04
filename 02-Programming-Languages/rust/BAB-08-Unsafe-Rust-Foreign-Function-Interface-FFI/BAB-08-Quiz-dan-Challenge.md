# BAB 08: Quiz, Challenge, & Knowledge Check
**Unsafe Rust & Foreign Function Interface (FFI)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Lima Unsafe Superpowers dan Pemisahan Tanggung Jawab
Dalam Rust, blok `unsafe` tidak mematikan *borrow checker* ataupun sistem tipe, melainkan memberikan akses ke tepat lima kapabilitas spesifik (*unsafe superpowers*). Sebutkan kelima kapabilitas tersebut. Jelaskan secara teknis perbedaan fundamental antara *Soundness Invariant* (yang harus dijaga oleh engineer) dan *Validity Invariant* (yang diasumsikan secara mutlak oleh compiler untuk optimasi LLVM).

### Soal 1.2: Anatomi Raw Pointers vs References
Jelaskan perbedaan representasi memori, semantik kompilasi, dan aturan aliasing antara raw pointer (`*const T`, `*mut T`) dengan Rust reference (`&T`, `&mut T`). Mengapa pembuatan raw pointer dari sebuah reference yang tidak valid diperbolehkan dalam Safe Rust, namun operasi dereferensinya mutlak membutuhkan blok `unsafe`? Apa implikasi dari *fat pointer* saat raw pointer menunjuk ke sebuah *dynamically sized type* (DST) seperti slice atau trait object?

### Soal 1.3: Hakikat Undefined Behavior (UB) dan Optimasi Kompiler
Definisikan *Undefined Behavior* (UB) menurut standar model kompilasi Rust/LLVM. Mengapa menganggap UB hanya sebatas "program akan crash atau melempar *segmentation fault*" merupakan pemahaman yang keliru dan berbahaya dalam rekayasa sistem? Berikan contoh konkret bagaimana compiler dapat memanfaatkan asumsi ketiadaan UB untuk mengeliminasi cabang kode (*dead code elimination*) yang justru memicu kerentanan keamanan (*security vulnerability*).

### Soal 1.4: Application Binary Interface (ABI) dan Calling Conventions
Ketika mendeklarasikan fungsi FFI menggunakan sintaks `extern "C"`, operasi apa yang terjadi di level assembler dan linker? Jelaskan perbedaan mendasar antara *Calling Convention* standar Rust (`extern "Rust"`) dengan *C Calling Convention* (`extern "C"` atau `cdecl`/`System V AMD64 ABI`) dalam hal penempatan argumen (register vs stack), arah pembersihan stack (*cleanup responsibility*), dan *symbol name mangling*.

### Soal 1.5: Tata Letak Memori (Memory Layout) dan `#[repr(C)]`
Secara default, Rust menerapkan representasi tipe `#[repr(Rust)]` yang memungkinkan compiler melakukan *field reordering*. Mengapa *field reordering* ini berbahaya saat data struct dilewatkan melintasi *FFI boundary* ke program C/C++? Jelaskan bagaimana atribut `#[repr(C)]` mengontrol struktur data terkait aturan *padding*, *data alignment*, dan *field offset* agar kompatibel dengan arsitektur C.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Model Memori Stacked Borrows dan Pointer Provenance
Model operasional Rust (yang diverifikasi oleh Miri) menerapkan konsep *Stacked Borrows* (dan varian barunya, *Tree Borrows*) untuk melacak validitas akses memori. Jelaskan apa yang dimaksud dengan *Pointer Provenance*. Analisis kode berikut dan tentukan di baris mana terjadi pelanggaran aliasing model (*aliasing violation*) yang menyebabkan UB, meskipun kode berhasil dikompilasi tanpa error:

```rust
fn illegal_aliasing() -> i32 {
    let mut val: i32 = 42;
    let ptr1: *mut i32 = &mut val;
    let ref1: &mut i32 = unsafe { &mut *ptr1 };
    let ptr2: *mut i32 = &mut *ref1;
    
    // Mutasi via ptr1 setelah derivasi ptr2/ref1
    unsafe {
        *ptr1 = 100;
        *ptr2 = 200;
    }
    val
}
```

### Soal 2.2: Manajemen Kepemilikan Lintas Boundary: `Box::into_raw` vs `Box::from_raw`
Dalam perancangan library FFI, memori yang dialokasikan oleh allocator Rust tidak boleh dibebaskan oleh `free()` milik runtime C, dan sebaliknya. Jelaskan siklus hidup transmisi kepemilikan pointer Rust ke C menggunakan `Box::into_raw` dan pengembaliannya ke Rust menggunakan `Box::from_raw`. Apa konsekuensi fatal jika terjadi *double-free*, pembebasan memori dengan *allocator mismatch*, atau kegagalan penanganan *drop semantics* pada objek yang dibungkus oleh `ManuallyDrop<T>`?

### Soal 2.3: Unwinding Panics Lintas ABI Boundary
Apa yang terjadi jika sebuah fungsi Rust yang diekspos sebagai `extern "C"` memicu operasi `panic!` yang melakukan stack unwinding melintasi *foreign frame* (C stack frame)? Mengapa perilaku ini secara historis didefinisikan sebagai UB dan bagaimana Rust versi modern (via RFC 2945 `c-unwind`) menangani situasi ini? Bagaimana strategi defensif terbaik menggunakan `std::panic::catch_unwind` untuk menjamin keamanan program pemanggil?

### Soal 2.4: String Boundary: `CString`, `CStr`, dan Invariant UTF-8
Jelaskan perbedaan arsitektur tipe antara `String`/`&str` (Rust) dengan `CString`/`&CStr` (FFI). Mengapa konversi dari string Rust ke C dapat gagal dengan error `NulError`, sedangkan konversi dari C raw pointer (`*const c_char`) ke Rust `&str` berisiko memicu UB jika tidak divalidasi? Analisis kompleksitas waktu dan alokasi memori saat Anda harus membaca buffer string berukuran gigabyte dari C tanpa melakukan *allocation copy*.

### Soal 2.5: Transmute, Type Punning, dan Soundness Boundaries
Fungsi `std::mem::transmute<T, U>` adalah salah satu fungsi paling berbahaya dalam Rust. Jelaskan mengapa pemeriksaan ukuran tipe (`size_of::<T>() == size_of::<U>()`) pada saat kompilasi *tidak cukup* untuk menjamin bahwa operasi transmute aman (*sound*). Sebutkan tiga skenario spesifik di mana `transmute` menghasilkan *instant Undefined Behavior*, khususnya terkait penanganan tipe referensi, boolean yang tidak valid, dan alalignment boundary.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kebocoran Memori (Unbounded Memory Growth) pada High-Throughput C-Binding
Sebuah mesin pemrosesan data real-time berbasis Rust mengintegrasikan engine kompresi C berperforma tinggi melalui FFI. Sistem memproses rata-rata 100.000 pesan per detik. Setelah berjalan selama 6 jam di lingkungan produksi, penggunaan RAM kontainer melonjak dari 500 MB ke 32 GB hingga akhirnya dihentikan oleh OS (*OOM Killer*). 

Tim menemukan kode integrasi berikut:

```rust
#[repr(C)]
pub struct NativeBuffer {
    pub data: *mut u8,
    pub len: usize,
}

extern "C" {
    fn decompress_frame(input: *const u8, len: usize) -> NativeBuffer;
    fn free_native_buffer(buf: NativeBuffer);
}

pub fn process_message(payload: &[u8]) -> Vec<u8> {
    unsafe {
        let native_buf = decompress_frame(payload.as_ptr(), payload.len());
        let slice = std::slice::from_raw_parts(native_buf.data, native_buf.len);
        let result = slice.to_vec();
        // free_native_buffer(native_buf); // Ditemukan terkomentari oleh developer
        result
    }
}
```

*   **Pertanyaan Diagnostik 1:** Mengapa pola pengembalian `Vec<u8>` dari `std::slice::from_raw_parts` di atas menimbulkan overhead alokasi ganda (*double allocation*), dan bagaimana mendesain abstraksi RAII berbasis tipe *wrapper struct* yang mengimplementasikan `Drop` untuk mencegah kebocoran memori secara otomatis (*zero-cost RAII leak prevention*)?
*   **Pertanyaan Diagnostik 2:** Jika fungsi `decompress_frame` sewaktu-waktu mengembalikan `NativeBuffer` dengan `data` bernilai `null` dan `len` bernilai `0`, jelaskan potensi UB yang terjadi pada pemanggilan `std::slice::from_raw_parts` dan bagaimana cara memitigasinya secara absolut?

---

### Skenario B: Race Condition dan Korupsi Memori Akibat Salah Implementasi `Send` / `Sync`
Sebuah arsitektur microservice Rust menggunakan wrapper FFI di atas library database C berpemilik (*proprietary legacy C library*). Developer membungkus pointer C context ke dalam struct Rust agar dapat digunakan di lingkungan multi-threaded async Tokio:

```rust
struct NativeDbContext {
    ctx: *mut c_void,
}

// Developer menambahkan deklarasi ini agar struct bisa dilewatkan ke Tokio task
unsafe impl Send for NativeDbContext {}
unsafe impl Sync for NativeDbContext {}

impl NativeDbContext {
    pub fn query(&self, sql: &str) -> QueryResult {
        unsafe {
            // Memanggil fungsi native C yang memutasi internal cache connection
            c_db_execute(self.ctx, sql.as_ptr() as *const c_char)
        }
    }
}
```

Setelah di-deploy, database mengalami korupsi data acak, *double-free segfaults*, dan kebocoran data antar thread pengguna yang berbeda.

*   **Pertanyaan Diagnostik 1:** Berdasarkan model threading Rust, jelaskan secara mendalam mengapa menandai `NativeDbContext` sebagai `Sync` merupakan pelanggaran fatal (*unsound abstraction*) jika library native C di bawahnya tidak *thread-safe* (menggunakan *interior mutability* tanpa lock internal)?
*   **Pertanyaan Diagnostik 2:** Rekonstruksi rancangan struct `NativeDbContext` tersebut agar *sound*. Tentukan kapan struct tersebut valid mengimplementasikan `Send`, kapan valid mengimplementasikan `Sync`, dan bagaimana mekanisme sinkronisasi Rust (`Arc`, `Mutex`, atau generic wrapper) harus diintegrasikan untuk menjamin konkurensi aman tanpa mengorbankan performa sistem secara ekstrem.

---

### Skenario C: Integrasi Ring Buffer Zero-Copy antara Kernel/Hardware Driver dan Rust Runtime
Perusahaan Anda sedang membangun sistem telemetri jaringan ultra-rendah latensi (*high-frequency networking*) menggunakan antarmuka DPDK/AF_XDP. Driver C mengalokasikan *shared memory ring buffer* raksasa di *huge pages*. Rust runtime bertindak sebagai consumer berkecepatan tinggi yang membaca paket network langsung dari buffer tersebut secara *lock-free*.

Tantangan arsitektur yang dihadapi:
1. Ruang memori dialokasikan dan dikendalikan oleh hardware C DMA driver.
2. Data paket di dalam buffer bersifat volatil; hardware sewaktu-waktu dapat menimpa slot buffer jika consumer tertinggal (*overrun condition*).
3. Rust async framework membutuhkan buffer dengan *stable lifetime* untuk dilewatkan ke berbagai task worker tanpa memicu UB akibat pembacaan *torn read* atau pelanggaran aliasing `&mut [u8]`.

*   **Pertanyaan Diagnostik 1:** Jelaskan mengapa memetakan buffer memori DMA volatil langsung ke slice Rust `&[u8]` atau `&mut [u8]` adalah *Undefined Behavior* instan menurut Rust Memory Model, terlepas dari apakah hardware sedang melakukan penulisan saat itu atau tidak. Mengapa Anda wajib menggunakan `*const UnsafeCell<T>` atau raw pointer dengan operasi pembacaan `std::ptr::read_volatile`?
*   **Pertanyaan Diagnostik 2:** Rancanglah arsitektur *sound API boundary* (antarmuka Rust yang aman) yang menjembatani buffer DMA raw tersebut ke safe Rust code. Bagaimana mekanisme kepemilikan (*lease/loan pattern*) dirancang untuk memastikan memory slot tidak ditimpa hardware selama worker Rust memproses payload paket tersebut?

---

## 4. Chapter Challenge
**Tantangan Praktis: Implementasi Sound, Zero-Copy C-Compatible Circular Ring Buffer (`libringbuf_ffi`)**

### Deskripsi Masalah
Dalam sistem pertukaran pesan antar-proses (IPC) atau akselerator perangkat keras, penggunaan antarmuka memori sirkular (*circular ring buffer*) adalah standar industri untuk throughput maksimal. Anda diminta mengimplementasikan sebuah Circular Ring Buffer yang aman (*sound*), berkinerja tinggi, beroperasi secara *zero-copy*, dan mengekspos C-ABI yang stabil agar dapat dikonsumsi oleh aplikasi berbasis C atau C++, sekaligus menyediakan Safe Wrapper ergonomis bagi konsumen Rust.

### Spesifikasi Teknis & Requirements
1. **Representasi Struktur Data (`#[repr(C)]`):**
   * Buat struktur data `RingBuffer` yang mengelola alokasi heap kontinu dari elemen bertipe `u8` (byte-oriented buffer) dengan kapasitas yang ditentukan saat inisialisasi.
   * Representasikan posisi `head`, `tail`, dan `capacity` menggunakan alignment yang tepat untuk menghindari *false sharing* antar core prosesor.
2. **C-Exported FFI Interface:**
   * Ekspor fungsi C-ABI yang stabil menggunakan konvensi `extern "C"`:
     * `ringbuf_create(capacity: usize) -> *mut RingBuffer` (Alokasi buffer).
     * `ringbuf_destroy(rb: *mut RingBuffer)` (Deallokasi buffer dengan validasi null).
     * `ringbuf_write(rb: *mut RingBuffer, data: *const u8, len: usize) -> usize` (Tulis bytes, kembalikan jumlah bytes yang berhasil ditulis).
     * `ringbuf_read(rb: *mut RingBuffer, dest: *mut u8, max_len: usize) -> usize` (Baca bytes ke target, kembalikan jumlah bytes terbaca).
3. **Safety & Robustness Boundary:**
   * Tidak ada kepanikan (`panic!`) yang boleh merembes (*unwind*) melintasi batas FFI. Semua fungsi FFI wajib menggunakan `std::panic::catch_unwind` atau jaminan non-panicking code path.
   * Fungsi harus tahan banting terhadap *null pointer*, pointer tidak selaras (*misaligned pointer*), dan operasi *out-of-bounds*.
4. **Rust Safe Wrapper:**
   * Sediakan Rust struct `SafeRingBuffer` yang membungkus pointer FFI tersebut dengan implementasi trait `Drop`, `Send` (jika memenuhi syarat), dan metode yang sepenuhnya aman (*safe methods*) tanpa menuntut pemanggil menulis blok `unsafe`.

### Constraints (Batasan Implementasi)
* Dilarang menggunakan alokasi dinamis baru (`Vec`, alokator sekunder) saat operasi baca/tulis berlangsung (*Zero-Allocation guarantee during I/O*).
* Kode Rust harus lolos verifikasi tool inspeksi memori **Miri** (`cargo miri test`) tanpa memicu satupun pelanggaran *Stacked Borrows*, *unaligned memory access*, ataupun *memory leak*.
* Gunakan dokumentasi standar `/// # Safety` pada setiap unsafe function yang dibuat, merinci prekondisi, invarian, dan pascakondisi secara ketat.

### Expected Output
1. Implementasi kode lengkap dalam satu file atau modul Rust terstruktur (`ring_buffer.rs`).
2. Implementasi unit test yang mengecek skenario:
   * Wraparound write dan read (ketika head/tail mencapai akhir buffer fisik dan berputar ke indeks 0).
   * Buffer full dan buffer empty edge cases.
   * Verifikasi handling null pointer pada FFI boundary tanpa runtime crash.
3. Test suite yang dapat dieksekusi langsung dengan perintah:
   ```bash
   cargo test
   cargo miri test
   ```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda dalam menangani Unsafe Rust dan integrasi FFI skala industri.

### Saya harus memahami:
- [ ] Batasan pasti dari lima *Unsafe Superpowers* dan mengapa safe Rust tetap aktif di dalam blok `unsafe`.
- [ ] Definisi teknis *Undefined Behavior* (UB) menurut Rust Memory Model dan cara LLVM mengeksploitasi UB untuk optimasi agresif.
- [ ] Aturan model *Stacked Borrows* / *Tree Borrows* terkait *pointer provenance*, aktivasi referensi, dan *aliasing rules*.
- [ ] Perbedaan antara *Validity Invariants* (tipe data yang tidak valid = instant UB) dan *Safety Invariants* (kondisi logika safe code).
- [ ] Mekanisme kerja C Calling Convention (`extern "C"`), pembersihan stack, dan penghapusan *symbol name mangling* (`#[no_mangle]`).
- [ ] Perbedaan tata letak memori (*struct alignment*, *field padding*, *size*) antara `#[repr(Rust)]`, `#[repr(C)]`, dan `#[repr(packed)]`.
- [ ] Dampak katastropik stack unwinding akibat Rust `panic!` melintasi batas ABI bahasa C dan solusinya.
- [ ] Semantik transfer kepemilikan FFI melalui `Box::into_raw`, `Box::from_raw`, `ManuallyDrop`, dan raw pointer dereferencing.
- [ ] Aturan transmute memori (`std::mem::transmute`), validitas representasi tipe target, serta alternatif berbasis pointer cast.
- [ ] Kriteria soundness ketika mengimplementasikan trait `Send` dan `Sync` secara manual pada tipe data berbasis raw pointer.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik pasti dari *system call numbers* atau platform-specific struct layout di setiap arsitektur OS (gunakan crate `libc`).
- [ ] Nama algoritma spesifik optimasi register allocation pada LLVM backend backend saat FFI call dieksekusi.
- [ ] Definisi header C dari ratusan ribu fungsi POSIX library (cukup gunakan tooling generator otomatis seperti `bindgen`).
- [ ] Tabel heksadesimal representasi mangling symbol internal dari compiler `rustc`.

### Saya harus bisa melakukan:
- [ ] Menggunakan tool **Miri** (`cargo miri`) untuk mendeteksi *pointer aliasing bugs*, *memory leaks*, dan *use-after-free* pada kode unsafe.
- [ ] Menulis deklarasi `extern "C"` yang tepat untuk mengimpor pustaka native C dan mengekspor pustaka Rust ke bahasa lain.
- [ ] Mengonversi C strings (`char*`) ke Rust string slice (`&str`) dan sebaliknya menggunakan `CString` dan `CStr` secara *zero-copy* dan *safe*.
- [ ] Merancang arsitektur Safe Abstraction Layer (pembungkus safe) di atas sistem native yang fundamentally unsafe dengan mematuhi prinsip RAII.
- [ ] Melakukan debugging terhadap *segmentation fault*, *memory corruptions*, dan *alignment faults* menggunakan debugger sistem tingkat rendah (`gdb`, `lldb`, atau AddressSanitizer/ASan).
- [ ] Mengonfigurasi build pipeline hybrid (`build.rs`, `cc` crate, atau tool `bindgen`/`cbindgen`) untuk mengotomasi integrasi library C/C++ ke dalam project cargo.