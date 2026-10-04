# Bab 04 Module 01: Semantik Kepemilikan (Ownership), Move Semantics, dan RAII dalam Rust

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
*   Menganalisis representasi memori runtime (*stack* vs *heap*) pada struktur data dinamis di Rust.
*   Mengimplementasikan mekanisme transfer kepemilikan (*Move Semantics*) untuk mengeliminasi *double-free* dan *dangling pointers* pada waktu kompilasi (*compile-time*).
*   Mengontrol daur hidup sumber daya sistem (file descriptor, socket, allocated memory) secara deterministik menggunakan pola *Resource Acquisition Is Initialization* (RAII) dan trait `Drop`.
*   Mendiagnosis dan memperbaiki kesalahan borrow checker umum seperti compiler error `E0382` (*use of moved value*) dan `E0507` (*cannot move out of borrowed content*).
*   Mendesain arsitektur perangkat lunak berbasis *Affine Type System* untuk menegakkan validitas status (*typestate pattern*) tanpa *runtime overhead*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta didik wajib memahami:
*   Sistem alokasi memori dasar: perbedaan mendasar antara *Stack Frame* (alokasi LIFO cepat terikat fungsi) dan *Heap* (alokasi dinamis manual via syscall seperti `brk`/`mmap` atau `malloc`).
*   Pointer dan indirection pada level arsitektur komputer (alamat memori, dereferensi, data alignment).
*   Sintaks dasar Rust: Deklarasi variabel (`let`, `let mut`), tipe data primitif (*integers*, *floats*, *booleans*), fungsi, serta struktur dasar (`struct`, `enum`).

---

### 3. Concept
Rust memecahkan masalah manajemen memori menggunakan paradigma baru: **Ownership System**. Sistem ini dikontrol oleh tiga aturan deterministik pada level kompilator:

1. Setiap nilai (*value*) di Rust memiliki variabel yang disebut sebagai pemiliknya (*owner*).
2. Hanya boleh ada **satu** pemilik pada satu waktu (*single ownership*).
3. Ketika pemilik keluar dari cakupan (*scope*), nilai tersebut akan dibersihkan (*dropped*) secara otomatis dari memori.

Secara formal, Rust mengimplementasikan variasi dari **Affine Type System**, sub-sistem dari *Substructural Type Systems*, di mana suatu nilai hanya dapat digunakan *paling banyak satu kali* (*at most once*). 

Ketika suatu tipe yang tidak mengimplementasikan trait `Copy` ditugaskan ke variabel lain, dilewatkan ke fungsi melalui nilai (*by-value*), atau dikembalikan dari fungsi, hak kepemilikan atas nilai tersebut berpindah (**Move Semantics**). Di balik layar, operasi ini hanyalah *shallow bitwise copy* (menyalin data pada stack, seperti pointer, panjang, dan kapasitas), diikuti dengan invalidasi variabel sumber pada level abstraksi kompilator. Tidak ada deep-copy runtime yang dilakukan secara implisit.

```
+-------------------------------------------------------------+
|                     Ownership Mechanics                     |
+-------------------------------------------------------------+
| Affine Types -> Value can be used AT MOST ONCE              |
| Assignment   -> Bitwise copy on stack + invalidate source   |
| Scope Exit   -> Invocations of Drop::drop automatically     |
+-------------------------------------------------------------+
```

---

### 4. Why
Dalam rekayasa sistem berkinerja tinggi, manajemen memori konvensional menghadapi trade-off biner:

1. **Manual Memory Management (C/C++):** Memberikan latensi ultra-rendah dan kontrol penuh melalui `malloc`/`free` atau `new`/`delete`. Namun, rawan terhadap kerentanan keamanan memori:
   * *Use-After-Free (UAF)*: Mengakses memori yang telah didealokasi.
   * *Double-Free*: Mencegah crash atau eksploitasi korupsi heap akibat dealokasi ganda.
   * *Memory Leaks*: Alokasi yang tidak pernah dibebaskan.
   * *Dangling Pointers*: Pointer yang menunjuk ke memori yang sudah di-reallocate oleh stack frame lain.
2. **Garbage Collection (Java, Go, C#, Node.js):** Menjamin keamanan memori melalui pelacakan runtime tracing atau reference counting. Namun, menimbulkan trade-off:
   * Non-deterministic pauses (*Stop-The-World latency spikes*).
   * Footprint memori runtime membengkak (overhead metadata object header dan heap sizing).
   * Ketidakcocokan untuk *embedded systems*, kernel development, dan real-time computing.

**Rust mengeliminasi trade-off ini.** Sistem Ownership menjamin *Memory Safety without Garbage Collection*. Kompilator (melalui *Borrow Checker* dan analisis *Mid-level Intermediate Representation / MIR*) membuktikan keabsahan semua akses memori sebelum kode dikompilasi menjadi machine code. Akibatnya, zero runtime cost tercapai: aplikasi memiliki performa setara C/C++ tanpa risiko eksploitasi memori.

---

### 5. What
Komponen inti sistem kepemilikan mencakup:

* **Stack vs Heap Representation:**
  Tipe dinamis seperti `String` atau `Vec<T>` terdiri dari dua komponen:
  1. *Stack component* (Fat pointer): Pointer ke heap buffer (8 byte), Kapasitas/capacity (8 byte), dan Panjang/length (8 byte) = total 24 byte pada arsitektur 64-bit.
  2. *Heap buffer*: Alokasi memori berukuran dinamis tempat elemen aktual disimpan secara kontigu.
* **Move Semantics:** Proses transfer kepemilikan nilai dari satu binding variabel ke binding variabel lain. Memori heap tidak diduplikasi; kepemilikan atas pointer dialihkan, dan variabel asal ditandai sebagai *uninitialized*.
* **Trait `Copy`:** Marker trait untuk tipe data primitif murni stack (seperti `i32`, `f64`, `bool`, array primitif `[T; N]`). Ketika di-assign, data disalin secara bitwise (`memcpy`), dan variabel sumber tetap valid (*Implicit Copy*).
* **Trait `Clone`:** Trait untuk duplikasi eksplisit dari suatu nilai, biasanya mencakup alokasi heap baru secara mendalam (*Deep Copy*).
* **RAII & Trait `Drop`:** Pola konstruksi di mana akuisisi resource terjadi saat inisialisasi dan dealokasi resource terjadi secara otomatis via fungsi `drop(&mut self)` saat variabel keluar dari kurung kurawal penutup scope (`}`).

---

### 6. How
Berikut adalah alur eksekusi internal kompilator Rust saat menangani Ownership dan Move:

```
[Source Code: let b = a;]
           │
           ▼
[AST Construction] ──► Parse representasi sintaksis dasar
           │
           ▼
[HIR & Type Checking] ──► Validasi trait implementasi (Apakah `a` tipe Copy?)
           │
           ▼
[MIR Generation]
    ├─ Deteksi Type: Jika Non-Copy, tandai sebagai Affine Move
    ├─ Set Stack Flag (Drop Flag) untuk tracking status inisialisasi runtime
    └─ Invalidate binding `a` dari Symbol Table aktif
           │
           ▼
[Borrow Checker (NLL: Non-Lexical Lifetimes)]
    ├─ Analisis liveness: Apakah `a` dibaca setelah instruksi ini?
    ├─ JIKA YA ──► Tolak kompilasi: Emit Compile Error (E0382)
    └─ JIKA TIDAK ──► Lolos validasi
           │
           ▼
[LLVM Bytecode Generation]
    └─ Emisi shallow `memcpy` 24-byte untuk fat pointer, bypass alloc call
```

Saat program dieksekusi:
1. Alokasi dilakukan di heap via alloc API.
2. Saat `let b = a;` dieksekusi, 24 byte disalin dari stack frame slot `a` ke slot `b`.
3. Kompilator menolak kode berikutnya yang merujuk pada slot `a`.
4. Saat scope berakhir, kompilator mengeksekusi instruksi `Drop::drop` khusus untuk slot `b`, memanggil allocator deallocate untuk heap buffer. Slot `a` diabaikan sepenuhnya, mencegah *double-free*.

---

### 7. Analogy
Bayangkan **Sertifikat Asli Hak Milik Tanah (SHM Fisik)**:
* Anda memegang SHM fisik atas sebidang tanah (Tanah = Memori di Heap, Dokumen SHM = Variabel/Fat Pointer di Stack).
* **Move Semantics:** Jika Anda menjual properti tersebut kepada Budi, Anda menyerahkan SHM fisik asli ke tangannya. Sekarang Budi adalah satu-satunya pemilik sah. Anda tidak lagi memiliki hak atas tanah tersebut. Jika Anda mencoba bertransaksi menggunakan dokumen fotokopi tak sah, Anda akan ditangkap oleh penegak hukum (Kompilator Rust memblokir kode dengan error `E0382`).
* **Garbage Collection Model:** Menyerupai sistem di mana Anda, Budi, dan lima orang lain memegang duplikat sertifikat. Sebuah badan audit sensus keliling kota setiap jam untuk mengecek apakah tanah tersebut masih dihuni atau tidak. Jika tidak berpenghuni, audit menyita tanah tersebut (menimbulkan delay dan latensi administratif).
* **Rust RAII:** Menjamin bahwa tepat pada saat pemilik terakhir meninggal dunia (*keluar dari scope*), tanah tersebut secara instan dan otomatis diserahkan kembali kepada negara tanpa perlu birokrasi audit sensus.

---

### 8. Diagram
Visualisasi alokasi memori dan transisi status saat operasi *Move* berlangsung:

#### Langkah 1: Inisialisasi `s1`
```
STACK FRAME                             HEAP MEMORY
+-----------------------+              +-------------------+
| Variable: s1          |              | Index | Character |
| - ptr: 0x55AA10 ------|------------->|  0    |    'H'    |
| - len: 5              |              |  1    |    'e'    |
| - cap: 5              |              |  2    |    'l'    |
+-----------------------+              |  3    |    'l'    |
                                       |  4    |    'o'    |
                                       +-------------------+
```

#### Langkah 2: Eksekusi `let s2 = s1;` (Move Semantics)
```
STACK FRAME                             HEAP MEMORY
+-----------------------+
| Variable: s1          |
| [INVALIDATED/MOVED]   |
| (Compiler forbids     |
|  any access here)     |
+-----------------------+
| Variable: s2          |              +-------------------+
| - ptr: 0x55AA10 ------|------------->|  0    |    'H'    |
| - len: 5              |              |  1    |    'e'    |
| - cap: 5              |              |  2    |    'l'    |
+-----------------------+              |  3    |    'l'    |
                                       |  4    |    'o'    |
                                       +-------------------+
```
*Catatan: Pointer heap `0x55AA10` TIDAK diduplikasi di heap. Hanya struct stack yang disalin secara shallow. Variabel `s1` dianulir dari pemeriksaan kompilator selanjutnya.*

---

### 9. Simple Example
Kode berikut mendemonstrasikan perbedaan perilaku antara tipe data yang mengimplementasikan `Copy` versus tipe data heap yang menggunakan `Move`.

```rust
fn main() {
    // 1. Tipe Data Primitif (Mengimplementasikan trait Copy)
    let x: i32 = 42;
    let y = x; // Bitwise copy terjadi secara implisit
    println!("Nilai x: {}, Nilai y: {}", x, y); // Valid: Keduanya dapat diakses

    // 2. Tipe Data Alokasi Dinamis (Non-Copy, Menerapkan Move Semantics)
    let s1 = String::from("Rust Engine");
    
    // Kepemilikan (ownership) buffer heap dipindahkan ke s2
    let s2 = s1; 

    // BARIS DI BAWAH AKAN MENYEBABKAN COMPILE-TIME ERROR:
    // println!("Nilai s1: {}", s1); 
    // error[E0382]: borrow of moved value: `s1`

    println!("Nilai s2: {}", s2); // Valid: s2 adalah pemilik sah saat ini

    // 3. Melewatkan kepemilikan ke dalam fungsi
    take_ownership(s2);

    // BARIS DI BAWAH INI ERROR KARENA s2 SUDAH DI-MOVE KE DALAM FUNGSI:
    // println!("Nilai s2: {}", s2);
}

fn take_ownership(received_string: String) {
    println!("Data diterima: {}", received_string);
    // Destructor String dipanggil otomatis di sini saat `received_string` keluar dari scope
}
```

---

### 10. Practical Example
Implementasi penanganan resource tingkat rendah: Pengelolaan manual *POSIX File Descriptor* menggunakan pola RAII untuk mencegah kebocoran resource (*resource leak*) tanpa menggunakan garbage collector runtime.

```rust
use std::ffi::CString;
use std::os::raw::c_int;

// Deklarasi unsafe FFI sistem POSIX
extern "C" {
    fn open(path: *const i8, oflag: c_int, mode: c_int) -> c_int;
    fn close(fd: c_int) -> c_int;
    fn write(fd: c_int, buf: *const u8, count: usize) -> isize;
}

const O_WRONLY: c_int = 0x0001;
const O_CREAT: c_int = 0x0040;
const O_TRUNC: c_int = 0x0200;
const S_IRUSR: c_int = 0o400;
const S_IWUSR: c_int = 0o200;

#[derive(Debug)]
pub struct SafeFileDescriptor {
    fd: c_int,
}

impl SafeFileDescriptor {
    /// Membuka file dan mengambil kepemilikan file descriptor mentah
    pub fn create_or_truncate(path: &str) -> Result<Self, String> {
        let c_path = CString::new(path).map_err(|e| e.to_string())?;
        
        let fd = unsafe {
            open(
                c_path.as_ptr(),
                O_WRONLY | O_CREAT | O_TRUNC,
                S_IRUSR | S_IWUSR,
            )
        };

        if fd < 0 {
            return Err("Gagal membuka file descriptor: kode error sistem".into());
        }

        Ok(SafeFileDescriptor { fd })
    }

    /// Menulis byte array ke file descriptor
    pub fn write_payload(&self, data: &[u8]) -> Result<usize, String> {
        let bytes_written = unsafe {
            write(self.fd, data.as_ptr(), data.len())
        };

        if bytes_written < 0 {
            Err("Kesalahan I/O sistem terdeteksi".into())
        } else {
            Ok(bytes_written as usize)
        }
    }
}

// Implementasi RAII via trait Drop
impl Drop for SafeFileDescriptor {
    fn drop(&mut self) {
        println!("[RAII Audit] Membersihkan resource fd: {}", self.fd);
        let result = unsafe { close(self.fd) };
        if result != 0 {
            eprintln!("[Kernel Alert] Gagal menutup file descriptor {}", self.fd);
        }
    }
}

fn process_worker_pipeline(descriptor: SafeFileDescriptor) {
    let payload = b"SYSTEM LOG ENTRY: Critical Transaction Commited\n";
    let _ = descriptor.write_payload(payload);
    // `descriptor` keluar dari scope di sini, Drop::drop dieksekusi deterministik
    println!("[Pipeline] Selesai memproses descriptor.");
}

fn main() {
    let file = SafeFileDescriptor::create_or_truncate("./production_log.txt")
        .expect("Inisialisasi file descriptor gagal");

    println!("[Main] File descriptor dialokasikan dengan ID: {:?}", file);

    // Kepemilikan file descriptor dipindahkan ke worker pipeline
    process_worker_pipeline(file);

    // KETENTUAN KOMPILATOR:
    // Mencoba memanggil file.write_payload(...) di sini ditolak secara absolut.
    // Menghilangkan bug Use-After-Free pada tingkat kernel/OS handler.
    println!("[Main] Program berhenti dengan aman.");
}
```

---

### 11. Real World Example
#### Kasus Nyata: Migrasi Gateway Discord dari Go ke Rust
Discord memigrasikan arsitektur *Read States Gateway Service* mereka dari Go ke Rust. 

**Konteks Masalah:**
Layanan ini mengelola jutaan koneksi live WebSocket klien dan menyimpan cache pesan kanal. Pada implementasi Go, alokasi buffer pesan yang masif dan transient menyebabkan *Garbage Collection (GC) Mark-and-Sweep spikes*. Setiap 2 menit, GC Go memicu latency spike sebesar ratusan milidetik (*CPU thrashing* saat memindai pointer heap), menyebabkan disrupsi *Real-Time Voice and Messaging*.

**Solusi Arsitektural Rust:**
Dengan memodelkan pipeline pemrosesan paket jaringan melalui *Ownership Move Semantics*:
1. Byte buffer diterima dari socket UDP/TCP, dibungkus dalam struct `Vec<u8>`.
2. Kepemilikan buffer dipindahkan (*Moved*) secara langsung dari modul *Ingress Reader*, masuk ke *Worker Thread*, dan diteruskan ke *Parser Engine* tanpa alokasi ulang dan tanpa *deep copy*.
3. Begitu paket selesai diparsing dan dikirimkan ke message bus, buffer keluar dari scope dan didistribusikan kembali ke *Memory Pool* atau didealokasi seketika melalui destructor RAII.

**Dampak Produksi:**
* Menghilangkan GC pause spikes sepenuhnya (menurunkan latensi 99th percentile dari puluhan milidetik menjadi sub-milidetik konstan).
* Reduksi penggunaan CPU sebesar 80% pada kapasitas throughput yang identik.

---

### 12. Trade-offs

| Dimensi | Pendekatan Rust Ownership | Pendekatan Manual (C/C++) | Pendekatan Garbage Collection (Go/Java) |
| :--- | :--- | :--- | :--- |
| **Keamanan Memori (Safety)** | **Total**: Divalidasi sepenuhnya saat *compile-time*. | **Rendah**: Bergantung pada disiplin programmer (*human error*). | **Tinggi**: Runtime memverifikasi akses via heap scanning. |
| **Latensi & Determinisme** | **Tinggi**: Destruktor deterministik, 0 pause GC. | **Tinggi**: Eksekusi instan deterministik. | **Rendah - Sedang**: Variasi latensi akibat Stop-the-World/GC scan. |
| **Overhead Runtime** | **Nol**: Beban komputasi berada pada tahap analisis kompilasi. | **Nol**: Metadata runtime minimal. | **Signifikan**: Runtime engine, background threads, heap overhead. |
| **Kompleksitas Kode** | **Tinggi**: Programmer harus bernegosiasi dengan borrow checker. | **Sangat Tinggi**: Kompleksitas pelacakan manual & audit leak. | **Rendah**: Developer tidak memikirkan deallokasi eksplisit. |
| **Waktu Kompilasi** | **Panjang**: Analisis MIR & borrow checking intensif. | **Cepat**: Kompilasi langsung tanpa static life analysis. | **Cepat - Sedang**: Pengecekan tipe tanpa static memory validation. |

---

### 13. When To Use
Gunakan arsitektur berbasis Ownership dan Move Semantics ketika:
* Membangun sistem berlatensi rendah (*low-latency trading platforms*, *game engines*, *network proxies*).
* Mengelola resource sistem operasi yang terbatas (*socket file descriptors*, *GPU memory handles*, *database transactional locks*).
* Menulis software kritis di mana kebocoran memori atau race condition berakibat fatal (*medical software*, *aerospace telemetry*, *kernel modules*).
* Membutuhkan konkurensi aman (*fearless concurrency*): data yang di-move ke thread lain terjamin tidak dapat diakses lagi oleh thread pembuatnya.

---

### 14. When NOT To Use
Pertimbangkan paradigma lain jika menghadapi skenario berikut:
* **Prototyping Cepat dengan Graf Kompleks:** Struktur data seperti *cyclic graphs*, doubly-linked lists saling silang yang rumit tanpa batasan siklus ownership yang jelas. Menggunakan Rust murni tanpa *unsafe* atau smart pointer overhead (`Rc`/`RefCell`) dapat memperlambat kecepatan rilis produk.
* **Aplikasi Berorientasi Scripting Sederhana:** Script ETL sekali pakai atau tool otomatisasi CLI internal yang siklus hidupnya hanya 1-2 detik. Overhead kognitif borrow checker tidak sebanding dengan manfaat optimasi memori yang didapatkan dibandingkan Python atau Go.

---

### 15. Common Mistakes

#### 1. Melakukan Move pada Data di Balik Indexing Collection
```rust
let items = vec![String::from("data1"), String::from("data2")];
// ERROR: cannot move out of index of `Vec<String>`
// let first = items[0]; 

// PERBAIKAN: Gunakan reference atau ambil kepemilikan eksplisit
let first_ref = &items[0]; // Meminjam (Borrowing)
let first_owned = items.get(0).cloned(); // Deep copy jika benar-benar butuh kepemilikan
```

#### 2. Ketergantungan Berlebihan pada `.clone()`
Menyelesaikan error `E0382` dengan menduplikasi seluruh heap via `.clone()` secara membabi buta. Hal ini menghancurkan profil performa sistem dan memicu alokasi memori berulang tanpa disadari.

#### 3. Mengasumsikan `Drop` Berjalan Saat `std::mem::forget` Digunakan
Programmer berasumsi destructor RAII selalu berjalan 100% aman dalam semua kondisi. Fungsi seperti `std::mem::forget` atau referensi siklik via `Rc`/`Arc` dapat membocorkan alokasi heap karena pemanggilan `Drop` di-bypass secara sengaja/tidak sengaja.

---

### 16. Best Practices (Production Checklist)
- [ ] **Desain API Menggunakan By-Value untuk Konsumsi Akhir:** Buat fungsi menerima parameter *by-value* (`fn process(buffer: Buffer)`) jika fungsi tersebut adalah pemilik akhir resource, memperjelas batasan daur hidup variabel.
- [ ] **Gunakan `std::mem::take` atau `std::mem::replace`:** Hindari error partial move saat Anda harus mengambil kepemilikan field dari struct yang berada di balik mutable reference tanpa mendestruktur seluruh struct.
- [ ] **Implementasikan `Copy` Hanya untuk Struct Berukuran Kecil:** Terapkan derive `#[derive(Copy, Clone)]` hanya pada struct Plain Old Data (POD) yang berukuran sama atau lebih kecil dari 2 pointer mesin (<= 16 byte pada x86_64) dan bebas alokasi heap.
- [ ] **Validasi Custom `Drop`:** Pastikan pemanggilan `Drop::drop` bersifat *idempotent* dan tidak pernah memicu panik (*never panic inside a destructor*). Panic saat proses *unwinding* berlangsung akan seketika menghentikan program via `abort`.
- [ ] **Jalankan `cargo clippy`:** Pastikan pipeline linting mendeteksi pola kloning yang redundan (`clippy::redundant_clone`).

---

### 17. Troubleshooting

#### Masalah 1: Error `E0382` (Use of Moved Value)
*Penyebab:* Mengakses variabel yang kepemilikannya telah diserahkan ke fungsi lain atau binding lain.
```rust
// Kode Bermasalah
let config = String::from("DEBUG_MODE=true");
std::thread::spawn(move || {
    println!("{}", config);
});
println!("{}", config); // Error E0382

// Solusi: Pinjam jika memungkinkan, atau jika harus dipindah ke thread lain,
// lakukan cloning secara terencana menggunakan pointer berhitung referensi (Arc).
use std::sync::Arc;
let config = Arc::new(String::from("DEBUG_MODE=true"));
let config_clone = Arc::clone(&config);
std::thread::spawn(move || {
    println!("{}", config_clone);
});
println!("{}", config); // Valid: Akses via immutable shared pointer
```

#### Masalah 2: Error `E0507` (Cannot Move out of Borrowed Content)
*Penyebab:* Mencoba menarik kepemilikan dari nilai yang sedang dipinjam (`&T` atau `&mut T`).
```rust
// Kode Bermasalah
struct Context { data: String }
fn extract_data(ctx: &Context) -> String {
    // ctx.data // Error: cannot move out of `ctx.data` which is behind a shared reference
    ctx.data.clone() // Solusi A: Clone jika membutuhkan salinan independen
}

// Solusi B: Jika mutasi diizinkan, ganti nilai asalnya
fn extract_data_mut(ctx: &mut Context) -> String {
    std::mem::take(&mut ctx.data) // Meninggalkan String kosong pada ctx.data
}
```

---

### 18. Exercise
**Instruksi:** Buat modul rust bernama `memory_vault`. Anda diminta merekayasa struktur data `SecureVault` yang menampung secret byte array (`Vec<u8>`).

Spesifikasi Teknis:
1. `SecureVault` harus memiliki method konstruktor `new(secret: Vec<u8>) -> Self`.
2. `SecureVault` harus mengonsumsi (*consume/move*) dirinya sendiri saat menjalankan method `burn_and_read(self) -> Vec<u8>`. Variabel vault asal tidak boleh dapat digunakan kembali setelah method ini dipanggil.
3. Implementasikan trait `Drop` pada `SecureVault` sehingga jika objek vault keluar dari scope tanpa memanggil `burn_and_read`, struct tersebut akan melakukan zeroization (mengisi array dengan angka `0`) sebelum membebaskan memori heap, dan mencetak pesan audit ke stdout: `"[AUDIT] Vault dropped safely. Buffer zeroized."`.

---

### 19. Challenge
**Studi Kasus: Zero-Overhead Transaction Typestate Pattern**

Rancanglah state machine transaksi perbankan menggunakan konsep *Ownership Move Semantics* pada level kompilasi. Sistem harus memverifikasi bahwa:
1. Sebuah transaksi dimulai dalam status `Draft`.
2. Dari `Draft`, transaksi hanya bisa di-move ke status `PendingApproval`.
3. Dari `PendingApproval`, transaksi bisa di-move ke `Executed` atau `Rejected`.
4. Anda dilarang keras menggunakan `enum` dengan branching runtime (`match`/`if`) di dalam method eksekusi.
5. Setiap transisi status **harus mengonsumsi struct status sebelumnya (`self`)** sehingga instansiasi status lama hancur pada waktu kompilasi (*compile-time impossibility of state reuse*).
6. State `Executed` harus mengeksekusi trait `Drop` yang menerbitkan checksum payload transaksi ke sistem logging.

*Tolok Ukur Keberhasilan:* Jika klien mencoba mengeksekusi transaksi yang masih berstatus `Draft`, kode **harus gagal pada tahap kompilasi**, bukan panic pada saat runtime!

---

### 20. Summary
* **Ownership** adalah pondasi utama Rust yang memberikan jaminan *memory safety* tanpa memerlukan overhead Garbage Collector.
* Model **Stack vs Heap** Rust membedakan data ukuran statis (disalin melalui bitwise copy jika bertipe `Copy`) dan data alokasi dinamis yang dikontrol via *fat pointers*.
* **Move Semantics** mentransfer kepemilikan nilai non-`Copy` secara shallow pada stack dan menginvalidasi variabel sumber secara statis melalui analisis borrow checker/MIR.
* **RAII (Resource Acquisition Is Initialization)** melalui trait `Drop` menjamin pembersihan resource deterministik instan pada saat variabel keluar dari kurung kurawal scope.
* Pendekatan kepemilikan ini tidak hanya menyelesaikan kerentanan klasik seperti *Use-After-Free* dan *Double-Free*, tetapi juga membentuk pola desain berkinerja tinggi seperti *Typestate Pattern* dan konkurensi thread yang aman.