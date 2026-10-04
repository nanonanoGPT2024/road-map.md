# Bab 03 Module 01: Ownership Fundamentals, Stack vs Heap, Move Semantics, dan RAII

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:
*   Menganalisis dan memetakan alokasi data memori ke dalam segmen *Stack* atau *Heap* berdasarkan tipe data dan *lifetime*-nya.
*   Mengimplementasikan aturan formal *Ownership* Rust untuk mengeliminasi kerentanan memori (*memory safety bugs*) seperti *use-after-free* dan *double-free* pada level kompilasi.
*   Mengidentifikasi perbedaan mekanis antara operasi *Move* dan *Copy* pada representasi biner memori.
*   Merancang komponen perangkat lunak yang mengelola sumber daya eksternal (berkas, soket jaringan, memori dinamis) secara otomatis menggunakan paradigma *Resource Acquisition Is Initialization* (RAII) dan trait `Drop`.
*   Mendiagnosis dan menyelesaikan eror kompilator terkait pemindahan kepemilikan (*value moved errors*) tanpa melakukan alokasi redundan (`.clone()`).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta didik wajib menguasai:
*   Pondasi sintaksis Rust: Deklarasi variabel (`let`, `mut`), fungsi, blok kode (`{}`), dan visibilitas cakupan (*scope*).
*   Sistem tipe primitif: Integers (`i32`, `u64`), Floating-point (`f64`), Booleans, Karakter, serta Tuples dan Arrays berukuran tetap.
*   Konsep dasar arsitektur komputer: Pointer, alamat memori virtual, dereferensi, serta cara kerja *Call Stack* pada eksekusi biner.

---

## 3. Concept

Sistem *Ownership* (Kepemilikan) adalah fondasi arsitektur Rust yang membedakannya dari bahasa pemrograman ber-pemberat *Garbage Collector* (seperti Go, Java) maupun manajemen manual (seperti C, C++). Sistem ini mengimplementasikan teori *Affine Type System*, di mana suatu nilai hanya dapat digunakan maksimum satu kali sebelum dipindahkan atau dihancurkan.

### Fondasi Arsitektur Memori: Stack vs Heap
*   **Stack**: Menyimpan data dengan ukuran yang diketahui secara pasti pada saat kompilasi (*fixed-size*) dan berumur pendek sesuai *stack frame* fungsi. Alokasi dan dealokasi terjadi secara otomatis via manipulasi *Stack Pointer* (instruksi CPU berbiaya sangat rendah, $O(1)$).
*   **Heap**: Digunakan untuk data dengan ukuran dinamis (*dynamically-sized*) atau data yang masa hidupnya melampaui masa hidup fungsi pembentuknya. Alokasi memerlukan pencarian blok memori kosong oleh *memory allocator* OS/jemalloc/mimalloc ($O(\log n)$ atau operasi kompleks), menghasilkan *pointer* beralamat 64-bit yang kemudian disimpan di dalam *Stack*.

```
         STACK                            HEAP
+-----------------------+        +---------------------+
| Variable: s1          |        | Index | Val (ASCII) |
| - ptr: 0x1000 --------+------->| 0     | 'H'         |
| - len: 5              |        | 1     | 'e'         |
| - cap: 5              |        | 2     | 'l'         |
+-----------------------+        | 3     | 'l'         |
                                 | 4     | 'o'         |
                                 +---------------------+
```

### Tiga Aturan Mutlak Ownership
1.  Setiap nilai (*value*) di Rust memiliki variabel yang disebut sebagai pemiliknya (*owner*).
2.  Hanya boleh ada **satu** pemilik pada satu waktu (*single ownership*).
3.  Ketika pemilik keluar dari cakupan (*scope*), nilai tersebut akan langsung dibebaskan dari memori secara deterministik.

### Move Semantics vs Copy Semantics
*   **Copy Semantics**: Berlaku untuk tipe data yang mengimplementasikan trait `Copy` (umumnya bertempat penuh di *Stack* tanpa referensi alokasi eksternal, seperti `i32`, `bool`, `f64`, array bertipe `Copy`). Operasi penugasan (`let y = x`) menduplikasi representasi biner secara *bitwise* (*shallow bitwise memcpy*). Variabel sumber (`x`) tetap valid.
*   **Move Semantics**: Berlaku untuk tipe data yang mengelola sumber daya heap atau tidak mengimplementasikan `Copy` (seperti `String`, `Vec<T>`, `File`). Penugasan (`let y = x`) menyalin metadata *stack* (pointer, length, capacity) dari `x` ke `y`, namun kompilator secara instan menandai variabel `x` sebagai *uninitialized* (invalid). Variabel sumber tidak lagi dapat diakses.

### Deterministic Destruction (RAII) dan Drop Flag
Rust mengimplementasikan RAII: alokasi sumber daya diikat dengan masa inisialisasi objek, dan pelepasan sumber daya diikat dengan penghancuran objek melalui pemanggilan fungsi internal `std::ops::Drop::drop`. Kompilator melacak status kepemilikan variabel menggunakan *Static Drop Analysis* pada *Control Flow Graph* (CFG). Jika suatu alokasi memiliki cabang kondisional (`if/else`), kompilator menyisipkan *Drop Flag* tersembunyi berukuran 1-byte pada *stack frame* untuk memastikan pembebasan memori terjadi tepat satu kali.

---

## 4. Why

Dalam rekayasa sistem berkinerja tinggi, ada dilema historis antara efisiensi eksekusi dan keamanan memori:

1.  **Kegagalan Pendekatan Manual (C/C++)**:
    *   *Dangling Pointers*: Mengakses memori yang telah dibebaskan.
    *   *Double Free*: Memanggil pembebasan dua kali pada blok memori yang sama, merusak tabel alokasi memori internal OS dan membuka celah eksploitasi keamanan (*arbitrary code execution*).
    *   *Memory Leaks*: Lupa membebaskan memori yang dialokasikan, menyebabkan degradasi performa progresif hingga terjadinya *Out-Of-Memory* (OOM) panic di lingkungan produksi.
2.  **Trade-off Pendekatan Tracing Garbage Collection (Go, Java, .NET)**:
    *   GC mengatasi masalah keamanan memori di atas, namun memperkenalkan *Stop-The-World latency pauses*, alokasi memori tambahan (*memory footprint* 1.5x - 2x dari data aktual), dan pemakaian CPU non-deterministik untuk *sweeping/compacting*.

Rust menyelesaikan masalah ini dengan memeriksa siklus hidup memori secara statis saat kompilasi (*compile-time enforcement*). Hasilnya: keamanan memori 100% tanpa adanya *runtime overhead* atau jeda latensi akibat GC.

---

## 5. What

Komponen teknis fundamental dalam sistem kepemilikan Rust:

| Komponen | Penjelasan Teknis | Perilaku Memori |
| :--- | :--- | :--- |
| **Owner** | Pengikat unik antara identifier variabel dengan alamat memori data. | Menyimpan representasi metadata di Stack. |
| **Move** | Transfer hak kepemilikan dari variabel lama ke variabel baru. | *Bitwise shallow copy* metadata di Stack; penonaktifan identitas lama. |
| **Copy Trait** | Marker trait penanda tipe data yang dapat diduplikasi penuh via `memcpy`. | Replikasi *bitwise* murni di Stack; variabel lama tetap aktif. |
| **Clone Trait** | Trait untuk menduplikasi data secara eksplisit (*deep copy*). | Alokasi ulang memori di Heap dan replikasi data isi. |
| **Drop Trait** | Destruktor otomatis yang dieksekusi ketika variabel keluar cakupan. | Dealokasi Heap dan pelepasan *handle* OS via `sys_free`. |
| **Drop Flag** | Boolean tersembunyi di Stack jika alokasi bersifat kondisional. | Memastikan pembebasan Heap tidak dieksekusi dobel atau terlewat. |

---

## 6. How

Berikut alur kerja transfer kepemilikan (*Move*) dan pembersihan deterministik (*Drop*):

```
+-------------------------------------------------------------+
|                     1. Inisialisasi                         |
|   let s1 = String::from("Rust");                            |
|   - Stack: s1 [ptr: 0x5000, len: 4, cap: 4]                 |
|   - Heap (0x5000): ['R', 'u', 's', 't']                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                     2. Operasi Move                         |
|   let s2 = s1;                                              |
|   - Stack: s2 [ptr: 0x5000, len: 4, cap: 4]                 |
|   - Stack: s1 DITANDAI TIDAK VALID (TIDAK AKTIF DI CFG)     |
|   - Tidak ada alokasi Heap baru.                            |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                     3. Akhir Cakupan Scope                  |
|   } // Scope berakhir                                       |
|   - Kompilator melihat hanya s2 yang aktif.                 |
|   - Drop::drop(s2) dieksekusi.                              |
|   - Memori Heap 0x5000 dibebaskan.                          |
|   - Stack frame dibersihkan (SP bergeser kembali).          |
+-------------------------------------------------------------+
```

1.  **Inisialisasi**: Alokator mengalokasikan 4 byte di heap, mengembalikan pointer mentah. Variabel `s1` diinisialisasi pada stack memuat pointer, panjang (4), dan kapasitas (4).
2.  **Operasi Move**: Perintah `let s2 = s1;` menyalin 24-byte metadata (pada arsitektur 64-bit: 8 byte pointer, 8 byte len, 8 byte cap) ke `s2`. Kompilator secara statis menganulir eksistensi `s1`. Upaya membaca `s1` akan ditolak saat kompilasi.
3.  **Destruksi**: Pada kurung kurawal tutup `}`, rutin pembersih hanya memanggil fungsi destruksi pada `s2`. Memori heap di alamat `0x5000` dibebaskan tepat satu kali.

---

## 7. Analogy

Bayangkan sertifikat fisik Buku Pemilik Kendaraan Bermotor (BPKB) untuk sebuah mobil:

*   **Mobil di Garasi = Data di Heap**. Mobil memiliki bobot fisik besar, tidak efisien dipindah-pindah.
*   **Sertifikat BPKB = Metadata di Stack**. Dokumen berukuran ringkas yang memuat nomor rangka (pointer) menuju mobil fisik di garasi.
*   **Move Semantics**: Ketika Anda menjual mobil ke pihak kedua, Anda menyerahkan BPKB fisik secara mutlak. Anda tidak lagi memiliki hak atas mobil itu. Mencoba mengendarai mobil menggunakan hak kepemilikan lama adalah tindakan ilegal (*compile-time error: use of moved value*). Mobilnya tidak pernah diduplikasi; hanya hak penguasaan yang berpindah tangan.
*   **Clone (Deep Copy)**: Anda memesan mobil baru dari pabrik dengan spesifikasi identik, lalu mencetak BPKB baru. Ini memerlukan alokasi finansial dan waktu tunggu yang besar (alokasi Heap baru).
*   **Drop**: Ketika pemilik terakhir sertifikat BPKB menyatakan mobil tersebut *scrapped* (besi tua), fasilitas pembongkaran menghancurkan mobil fisik di garasi tepat satu kali.

---

## 8. Diagram

### Arsitektur Memori: String Move vs i32 Copy

```
=====================================================================
KASUS 1: MOVE SEMANTICS (Tipe Heap: String)
=====================================================================

Kondisi Awal: let s1 = String::from("DATA");
STACK FRAME                                 HEAP STORAGE
+--------------------------+               +---------------+
| s1                       |               | 0x7FFE0010    |
|   ptr: 0x7FFE0010 -------+-------------> | ['D','A','T','A']
|   len: 4                 |               +---------------+
|   cap: 4                 |
+--------------------------+

Kondisi Pasca Eksekusi: let s2 = s1;
STACK FRAME                                 HEAP STORAGE
+--------------------------+
| s1 [INVALID / MOVED]     |
|   ptr: 0x7FFE0010 (mati) |
+--------------------------+
| s2                       |               +---------------+
|   ptr: 0x7FFE0010 -------+-------------> | ['D','A','T','A']
|   len: 4                 |               +---------------+
|   cap: 4                 |               (Tidak ada realokasi)
+--------------------------+

=====================================================================
KASUS 2: COPY SEMANTICS (Tipe Primitif Stack: i32)
=====================================================================

Kondisi: let a = 42; let b = a;
STACK FRAME
+--------------------------+
| a: 42 (Masih Valid)      |
+--------------------------+
| b: 42 (Duplikasi Bitwise)|
+--------------------------+
(Tidak ada keterlibatan Heap)
```

---

## 9. Simple Example

Kode di bawah ini mendemonstrasikan perbedaan mekanis antara transfer nilai primitif bertipe `Copy` vs tipe alokasi dinamis bertipe non-`Copy`:

```rust
fn main() {
    // ----------------------------------------------------
    // Bagian 1: Tipe Stack Mengimplementasikan Trait Copy
    // ----------------------------------------------------
    let x: i32 = 100;
    let y = x; // Operasi Copy bitwise secara implisit.
    
    // x dan y sama-sama valid dan independen di Stack.
    println!("Nilai x: {}, Nilai y: {}", x, y);

    // ----------------------------------------------------
    // Bagian 2: Tipe Heap Menerapkan Move Semantics
    // ----------------------------------------------------
    let s1 = String::from("Sistem Terdistribusi");
    
    // Kepemilikan (ownership) pointer berpindah secara mutlak ke s2.
    let s2 = s1; 

    // BARIS DI BAWAH INI AKAN GAGAL DIKOMPILASI JIKA TIDAK DIKOMENTARI:
    // println!("Nilai s1: {}", s1);
    // Compiler Error: borrow of moved value: `s1`
    
    println!("Nilai s2: {}", s2); // s2 adalah pemilik sah saat ini.

    // ----------------------------------------------------
    // Bagian 3: Duplikasi Eksplisit via Trait Clone
    // ----------------------------------------------------
    let s3 = s2.clone(); // Alokasi Heap baru terjadi di sini.
    
    // Baik s2 dan s3 memiliki alokasi Heap mandiri yang setara.
    println!("s2: {}, s3: {}", s2, s3);
} // Di sini, s3 keluar cakupan (drop), lalu s2 keluar cakupan (drop).
  // s1 tidak di-drop karena sudah dinonaktifkan status kepemilikannya.
```

---

## 10. Practical Example

Contoh berikut menunjukkan implementasi pembungkus *Low-Level Linux File Descriptor* berbasis RAII murni. Ketika kepemilikan objek berpindah (*moved*), deskriptor tidak akan ditutup secara prematur, namun saat pemilik aktif terakhir keluar dari *scope*, berkas akan ditutup secara aman via sistem panggilan kernel `libc::close`.

```rust
use std::ffi::CString;
use std::os::raw::c_int;

// Representasi aman terhadap Raw File Descriptor tingkat OS
pub struct SafeFileDescriptor {
    fd: c_int,
    path: String,
}

impl SafeFileDescriptor {
    // Membuka berkas dan mengambil kepemilikan handle OS (Resource Acquisition)
    pub fn open_read(path: &str) -> Result<Self, String> {
        let c_path = CString::new(path).map_err(|e| e.to_string())?;
        
        // Memanggil syscall open(2) mode Read-Only via FFI
        let fd = unsafe { libc::open(c_path.as_ptr(), libc::O_RDONLY) };
        
        if fd < 0 {
            return Err(format!("Gagal membuka berkas: {}", path));
        }

        println!("[SYS] File Descriptor {} berhasil dibuka untuk '{}'", fd, path);
        Ok(SafeFileDescriptor {
            fd,
            path: path.to_string(),
        })
    }

    pub fn read_bytes(&self, buffer: &mut [u8]) -> Result<usize, String> {
        let bytes_read = unsafe {
            libc::read(
                self.fd,
                buffer.as_mut_ptr() as *mut libc::c_void,
                buffer.len(),
            )
        };

        if bytes_read < 0 {
            Err("Eror operasi read(2) pada kernel".to_string())
        } else {
            Ok(bytes_read as usize)
        }
    }
}

// Implementasi RAII via Trait Drop
impl Drop for SafeFileDescriptor {
    fn drop(&mut self) {
        // Pembersihan deterministik: Tidak akan ada file descriptor leak
        if self.fd >= 0 {
            unsafe {
                libc::close(self.fd);
            }
            println!("[SYS] Berkas '{}' (FD {}) otomatis ditutup via Drop.", self.path, self.fd);
        }
    }
}

// Simulasi Pipeline Pemrosesan dengan Perpindahan Kepemilikan (Ownership Pipeline)
fn process_telemetry_pipeline(worker_id: u32, descriptor: SafeFileDescriptor) {
    println!("Worker {} mengambil alih kepemilikan SafeFileDescriptor!", worker_id);
    let mut buffer = [0u8; 16];
    
    match descriptor.read_bytes(&mut buffer) {
        Ok(bytes) => println!("Worker {} membaca {} bytes data.", worker_id, bytes),
        Err(err) => eprintln!("Worker {} gagal membaca data: {}", worker_id, err),
    }
    // `descriptor` keluar dari cakupan di akhir fungsi ini.
    // Drop::drop otomatis dipanggil di sini, menutup fd di kernel OS.
}

fn main() {
    // Asumsi berkas /dev/null selalu tersedia di platform UNIX
    let path = "/dev/null";

    let descriptor = match SafeFileDescriptor::open_read(path) {
        Ok(desc) => desc,
        Err(e) => {
            eprintln!("Inisialisasi gagal: {}", e);
            return;
        }
    };

    // MOVE SEMANTICS DITERAPKAN:
    // Kepemilikan `descriptor` berpindah ke dalam fungsi `process_telemetry_pipeline`.
    process_telemetry_pipeline(1, descriptor);

    // KODE DI BAWAH INI AKAN MENYEBABKAN COMPILE ERROR:
    // descriptor.read_bytes(&mut buffer);
    //
    // Penjelasan Arsitektural: Rust melindungi pengembang dari potensi
    // Use-After-Free/Bad File Descriptor karena fungsi `process_telemetry_pipeline`
    // telah membebaskan sumber daya tersebut saat fungsinya selesai.
}
```

---

## 11. Real World Example

### Studi Kasus: Discord Architecture Transition (Go ke Rust)

**Konteks Masalah**: Layanan "Read States" di Discord bertugas memantau pesan mana saja yang telah dibaca oleh jutaan pengguna secara *real-time*. Awalnya komponen ini diimplementasikan menggunakan Go.

**Akar Masalah Teknis**:
Meskipun arsitektur Go efisien secara konkurensi (Goroutines), sistem *Garbage Collector* secara konstan memindai memori cache berukuran gigabyte yang berisi map entitas pengguna. Setiap 2 menit, Discord mengalami lonjakan latensi (*latency spike*) yang signifikan akibat GC CPU *spikes*. GC Go terpaksa melintasi pointer heap raksasa untuk memvalidasi objek mati (*live object scanning*), menghasilkan lonjakan tail latency ($p99$) hingga di atas 500 milidetik.

**Solusi Berbasis Ownership Rust**:
Discord merancang ulang arsitektur layanan tersebut ke Rust. Dengan sistem *Ownership* dan *Move Semantics*:
1.  **Struktur In-Memory Terkendali Tanpa GC**: Status pesan diikat langsung dalam struktur data beralamat deterministik. Pembaruan state cache langsung menggantikan (*drop*) state memori lama secara instan tanpa perlu menandai (*marking*) dan menyapu (*sweeping*).
2.  **Eliminasi Latensi**: Penghapusan data lama terjadi di tingkat microsecond persis saat data dikeluarkan dari hashmap. Tidak ada proses latar belakang sistem yang menghentikan alur aplikasi.

**Hasil Pengukuran Produksi**:
Latensi $p99$ Discord turun secara dramatis dari **500ms** (Go) menjadi **kurang dari 5ms** (Rust) secara konstan, dengan konsumsi CPU turun drastis meski volume pertukaran pesan meningkat jutaan per detik.

---

## 12. Trade-offs

| Aspek | Sisi Positif (*Advantages*) | Sisi Negatif (*Disadvantages*) |
| :--- | :--- | :--- |
| **Performa Eksekusi** | Tanpa jeda GC (*zero-pause*), jejak memori (*footprint*) minimal, kecepatan setara C/C++. | Kode biner berpotensi membesar jika terjadi *inlining* pemanggilan `drop` secara masif. |
| **Keamanan Memori** | Menghilangkan mutlak: *Dangling Pointer*, *Double Free*, *Use-After-Free*. | Struktur data siklik (seperti *Doubly Linked List*, *Cyclic Graphs*) sangat sulit dibuat secara aman. |
| **Produktivitas Tim** | *Data race* & korupsi memori tertangkap saat *build* lokal, bukan di produksi. | Kurva belajar (*steep learning curve*) tinggi; *Borrow Checker* memperlambat iterasi prototipe awal. |
| **Prediktabilitas** | Waktu dealokasi deterministik (cocok untuk *embedded*, audio DSP, dan real-time HFT). | Alokasi dinamis manual yang ceroboh via `.clone()` berlebihan justru memperburuk throughput. |

*Kompleksitas*: Tinggi di awal (beban kognitif bergeser ke fase perancangan sistem dan kompilasi), tetapi Rendah pada fase pemeliharaan produksi (*maintenance*).

---

## 13. When To Use

*   Pengembangan infrastruktur sistem tingkat rendah: Mesin basis data (*database storage engines*), sistem operasi, *hypervisor*, dan *browser engines*.
*   Layanan backend mikro (*microservices*) skala raksasa yang menuntut kestabilan nilai $p99$ tail latency ketat tanpa toleransi terhadap interupsi GC.
*   Pemrograman terdistribusi berskala besar dengan batasan alokasi memori ketat (*low-footprint environment* seperti AWS Lambda atau IoT / edge computing).
*   Komponen kriptografi dan pemrosesan keamanan jaringan di mana kebocoran memori dari variabel sensitif harus dibersihkan secara instan (*zeroing out memory on drop*).

---

## 14. When NOT To Use

*   **Prototipe Cepat MVP (*Proof of Concept*)**: Ketika arsitektur perangkat lunak masih berubah secara drastis setiap beberapa jam, fleksibilitas bahasa dinamis bergulir cepat (seperti Python, Ruby) lebih efisien secara biaya bisnis.
*   **Aplikasi Berbasis Graf Kompleks Tanpa Pola Jelas**: Sistem dengan entitas yang saling memiliki secara melingkar (*cyclical object references*) tanpa batasan hierarki hierarkis lebih mudah ditangani oleh bahasa dengan *Tracing Garbage Collector*.
*   **Aplikasi Skrip Sederhana Berdurasi Pendek (*One-off Scripts*)**: CLI sekali pakai atau automasi build reguler tidak memperoleh manfaat signifikan dari efisiensi deterministik ownership.

---

## 15. Common Mistakes

### 1. Mencoba Menggunakan Kembali Variabel yang Telah Di-Move
```rust
let data = vec![1, 2, 3];
process_data(data); // Move terjadi ke dalam fungsi.
println!("Ukuran data: {}", data.len()); // ERROR: borrow of moved value `data`
```

### 2. Mengatasi Kompiler Secara Naif Menggunakan `.clone()`
Pemula sering melakukan `.clone()` secara membabi-buta untuk memuaskan kompilator Rust saat variabel hendak dipindahkan:
```rust
// ANTI-PATTERN: Menggandakan alokasi heap secara masif dan memperlambat throughput
let config = read_large_config();
start_worker_one(config.clone());
start_worker_two(config.clone());
start_worker_three(config);
```
*Solusi*: Gunakan teknik *Borrowing/References* (dibahas pada Module berikutnya) daripada menyalin isi memori seutuhnya.

### 3. Partial Move pada Struktur Data
```rust
struct UserSession {
    session_id: String,
    token: String,
}

let session = UserSession {
    session_id: "s1029".to_string(),
    token: "jwt.token.here".to_string(),
};

let sid = session.session_id; // Partial move terjadi pada field `session_id`!
// ERROR: session tidak lagi bisa digunakan sebagai struktur data utuh:
// println!("{:?}", session);
```

---

## 16. Best Practices

*   [ ] **Utamakan Pass-By-Value untuk Operasi Konsumtif**: Jika suatu fungsi membutuhkan kepemilikan mutlak atas suatu resource (misal: serialisasi ke storage), ambil argumen sebagai nilai konkrit (*by value*), bukan referensi.
*   [ ] **Gunakan `#[derive(Clone, Copy)]` Khusus untuk Skalar dan Tipe Berukuran Kecil**: Jangan implementasikan `Copy` jika ukuran struktur data melampaui ukuran beberapa register CPU (lebih dari ~128 bytes) untuk menghindari degradasi throughput memori pada stack.
*   [ ] **Manfaatkan RAII untuk Semua Handle Eksternal**: Pastikan resource non-memori (Mutex lock, DB Connection Pool, File Descriptor) selalu dibungkus dalam *struct* dengan implementasi `Drop`.
*   [ ] **Aktifkan Linter Clippy di Jalur CI/CD**:
    Gunakan `cargo clippy -- -D clippy::redundant_clone` untuk mendeteksi operasi kloning data tak berfaedah yang bisa digantikan dengan *move semantics*.
*   [ ] **Hindari Logika Kompleks di dalam Implementasi Trait `Drop`**:
    Fungsi `drop` dilarang memicu `panic!`. Panik ganda (*double panic*) saat *stack unwinding* akan langsung memaksa runtime program melakukan `abort` mendadak tanpa pembersihan resource lanjutan.

---

## 17. Troubleshooting

### Mendiagnosis Eror Kompilator E0382

**Pesan Eror Kompilator**:
```text
error[E0382]: use of moved value: `packet_payload`
  --> src/main.rs:18:28
   |
14 |     let packet_payload = String::from("PAYLOAD_TCP_9082");
   |         -------------- move occurs because `packet_payload` has type `String`,
   |                        which does not implement the `Copy` trait
15 |     send_over_network(packet_payload);
   |                       -------------- value moved here
...
18 |     audit_log(packet_payload);
   |               ^^^^^^^^^^^^^^ value used here after move
```

**Langkah Penanganan Terstruktur**:
1.  **Telusuri Alur Transfer (*Trace Path*)**: Identifikasi titik pertama variabel diserahkan (baris 15). Kompilator memberi tahu tipe data tidak mengimplementasikan trait `Copy`.
2.  **Tentukan Kebutuhan Sejati Fungsi Penerima**:
    *   Apakah `send_over_network` benar-benar perlu mengonsumsi kepemilikan data?
    *   Jika fungsi tersebut hanya perlu membaca data tanpa memilikinya secara permanen, ubah tanda tangan fungsi tersebut untuk menerima referensi pinjaman (contoh: `&str` atau `&String`).
3.  **Terapkan Refactoring Berdasarkan Alur Kontrol**:
    Jika *move* memang mutlak di kedua fungsi (misal: kedua fungsi menyalurkannya ke thread berbeda), tentukan apakah kloning eksplisit (`.clone()`) diperbolehkan secara arsitektur, atau jika pemanggilan fungsi log audit harus dipindahkan sebelum fungsi pengiriman jaringan dilakukan:
    ```rust
    // Solusi Alur: Log sebelum dikonsumsi
    audit_log(&packet_payload); // Baca tanpa mengambil alih
    send_over_network(packet_payload); // Konsumsi kepemilikan
    ```

---

## 18. Exercise

Selesaikan kasus di bawah ini untuk menguji pemahaman operasional *Ownership*.

### Skenario Masalah
Perusahaan Anda memiliki sistem pemroses tugas terdistribusi. Kode di bawah ini mengalami kegagalan kompilasi karena pelanggaran aturan *Ownership*:

```rust
// SOAL LATIHAN: Perbaiki kode di bawah ini agar lolos kompilasi Rust
// dengan aturan: DILARANG MENGGUNAKAN `.clone()` pada data Payload.

struct Job {
    id: u64,
    payload: String,
}

fn validate_job(job: Job) -> bool {
    !job.payload.is_empty()
}

fn dispatch_job(job: Job) {
    println!("Dispatching job {} with payload: {}", job.id, job.payload);
}

fn main() {
    let job = Job {
        id: 101,
        payload: String::from("DATA_ENCRYPTED_STREAM"),
    };

    if validate_job(job) {
        dispatch_job(job);
    }
}
```

### Panduan Penyelesaian
Analisis bagaimana kepemilikan variabel `job` dipindahkan ke fungsi `validate_job`. Rancang ulang tanda tangan (*signature*) atau nilai kembali (*return value*) fungsi tersebut sehingga hak kepemilikan dikembalikan, atau ubah urutan kontrol alokasi.

---

## 19. Challenge

### Misi Rekayasa: Custom Zero-Allocation Safe Arena Buffer Pool

Rancang sebuah *Ring Buffer* memori berskala tetap yang mengelola siklus hidup data menggunakan pola *RAII* dan *Move Semantics* murni, dengan spesifikasi teknis berikut:

1.  Buat struktur data bernama `MemoryBlock` yang membungkus alokasi mentah: `Vec<u8>`. Implementasikan trait `Drop` yang mencetak status pembebasan blok memori ke konsol, termasuk total kapasitas byte yang dibebaskan.
2.  Rancang struktur `BufferPool` yang memuat antrean blok memori (`Vec<MemoryBlock>`).
3.  Implementasikan fungsi `acquire(&mut self) -> Option<MemoryBlock>`: Mengeluarkan satu blok memori dari antrean dan memindahkan kepemilikannya ke luar (*move to caller*).
4.  Implementasikan fungsi `release(&mut self, block: MemoryBlock)`: Mengambil alih kepemilikan kembali dari pemanggil, membersihkan isi byte tanpa membatalkan alokasi kapasitas Heap (`block.buffer.clear()`), dan memasukkannya kembali ke dalam antrean pool.
5.  Uji skenario:
    *   Ambil blok dari pool, isi data 1KB, lalu kirim kepemilikan blok tersebut ke fungsi worker lain.
    *   Kembalikan blok ke pool via `release`.
    *   Biarkan program berakhir dan amati bahwa *Drop* hanya dieksekusi secara otomatis ketika seluruh `BufferPool` keluar dari scope pemanggilan di akhir aplikasi.

---

## 20. Summary

1.  **Manajemen Memori Deterministik**: Rust menyatukan kecepatan runtime pembebasan manual (ala C/C++) dengan proteksi mutlak *Garbage Collector* melalui analisis statis saat kompilasi.
2.  **Aturan Tunggal Kepemilikan**: Setiap nilai hanya dimiliki oleh satu variabel. Ketika variabel pemilik keluar dari batas cakupan (*scope*), nilainya dibersihkan seketika via destruktor `Drop`.
3.  **Mekanisme Move Default**: Untuk semua tipe data yang mengelola alokasi memori dinamis di Heap, transfer assignment menandai variabel asal sebagai non-aktif tanpa menyalin data di Heap (*zero heap copy overhead*).
4.  **Tipe Primitif Ber-Copy**: Tipe data yang berukuran tetap dan seluruhnya hidup di Stack mengimplementasikan trait `Copy`, memicu operasi duplikasi representasi biner secara *bitwise* tanpa membatalkan variabel sumber.
5.  **Prinsip RAII Terintegrasi**: Mengikat siklus hidup sumber daya sistem (memori, soket, file descriptor, lock) langsung ke dalam masa hidup variabel lokal menjamin tidak adanya kebocoran sumber daya di lingkungan produksi.