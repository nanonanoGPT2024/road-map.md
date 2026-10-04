# Bab 06 Module 01: Smart Pointers — Fondasi `Box<T>`, Deref Coercion, dan Manajemen Destruksi `Drop`

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
* Merancang tipe data rekursif dan struktur data berukuran dinamis menggunakan alokasi heap via `Box<T>` tanpa memicu kompilasi gagal akibat ukuran tak tentu (*indefinite size*).
* Mengimplementasikan *trait* `Deref` dan `DerefMut` secara tepat untuk memanfaatkan *deref coercion* transparan tanpa menambah *runtime overhead*.
* Mengendalikan determinisme pembersihan sumber daya (*resource cleanup*) sistem melalui implementasi *trait* `Drop` dan mengidentifikasi mekanika *drop flags* serta *drop glue* pada level LLVM IR/MIR.
* Mengukur dan menganalisis penalti performa dereferensiasi (*pointer chasing*) dan fragmentasi memori heap dibandingkan alokasi stack.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
* **Ownership, Borrowing, dan Lifetimes**: Aturan kepemilikan tunggal, referensi eksklusif (`&mut T`), dan referensi bersama (`&T`).
* **Stack vs. Heap Memory Layout**: Cara alokasi *stack frame*, *pointer size* ($usize$), dan *heap fragmentation*.
* **Generics & Traits**: Sintaks dasar definisi *trait*, implementasi *trait*, dan parameter generik.
* **Layout Memori Dasar**: Memahami konsep *size* dan *alignment* (`std::mem::size_of`, `std::mem::align_of`).

---

### 3. Concept
Secara fundamental, Rust membagi memori menjadi *stack* (cepat, alokasi berurutan LIFO, ukuran wajib diketahui saat kompilasi/`Sized`) dan *heap* (dinamis, dikelola oleh alokator global seperti `jemalloc` atau `System Allocator`, ukuran fleksibel).

```
+-------------------------------------------------------------+
| RUST TYPE SYSTEM: SIZED VS DST (DYNAMICALLY SIZED TYPES)    |
|                                                             |
| T: Sized     --> Diketahui saat kompilasi (misal: i32, [u8; 4])|
| T: ?Sized    --> DST, ukuran dinamis (misal: [u8], str, Trait)|
|                                                             |
| Solusi DST pada Stack: Pointer Indirection (Box<T>, &T)      |
+-------------------------------------------------------------+
```

Smart Pointer adalah struktur data yang membungkus *pointer* mentah (*raw pointer*), tetapi dilengkapi dengan metadata dan kapabilitas tambahan melalui implementasi dua *trait* fundamental:
1. `std::ops::Deref` (dan `DerefMut`): Memungkinkan *instance* dari *smart pointer* diperlakukan seperti referensi biasa, memicu mekanisme kompilator bernama **Deref Coercion**.
2. `std::ops::Drop`: Mengizinkan kustomisasi kode yang dieksekusi saat data keluar dari *scope* (*Resource Acquisition Is Initialization* / RAII).

Struktur internal `Box<T>` tidak lebih dari pembungkus nol biaya (*zero-cost wrapper*) di atas pointer mentah `NonNull<T>` yang merepresentasikan kepemilikan tunggal (*unique ownership*) atas suatu blok memori di heap:
```rust
pub struct Box<
    T: ?Sized,
    A: Allocator = Global,
>(Unique<T>, A);
```
Di mana `Unique<T>` menjamin invariansi berikut:
* Penunjuk tidak pernah bernilai *null*.
* Penunjuk memiliki kepemilikan penuh atas data `T`.
* Tipe bersifat *covariant* terhadap `T`.

---

### 4. Why
1. **Penyelesaian Ukuran Tipe Kompilasi (*Compile-Time Layout Resolution*)**: Rust membutuhkan ukuran eksak setiap tipe data lokal pada *stack frame*. Tanpa *pointer indirection*, tipe data rekursif seperti *linked list* atau *abstract syntax tree* (AST) akan memiliki ukuran tak terhingga ($\infty$ bytes), sehingga ditolak oleh `rustc` (*Error E0072*).
2. **Mitigasi Stack Overflow**: Menempatkan struktur data masif (misal: *array* matriks 10 MB) langsung pada *stack* akan melampaui limit *stack* sistem operasi (standar Linux umumnya 8 MB), menyebabkan *segmentation fault*. `Box<T>` memindahkan muatan tersebut ke heap dan hanya menyimpan *pointer* 8-byte pada *stack*.
3. **Deterministik Tanpa Garbage Collector**: Bahasa seperti Java/Go mendelegasikan manajemen heap ke Garbage Collector (GC) yang menimbulkan *stop-the-world latency*. Rust memanfaatkan `Box<T>` dengan kontrak RAII: kompilator menginjeksi fungsi `drop_in_place` tepat saat variabel `Box` keluar dari *scope*, membebaskan heap secara deterministik dengan latensi $\mathcal{O}(1)$.

---

### 5. What
Komponen arsitektural utama dalam ekosistem Smart Pointer:

* **`Box<T>`**: Pengalokasi heap unik. Mengambil data di stack, menyalinnya ke heap via alokator global, dan mengembalikan handle kepemilikan.
* **`trait Deref`**:
  ```rust
  pub trait Deref {
      type Target: ?Sized;
      fn deref(&self) -> &Self::Target;
  }
  ```
* **`trait DerefMut`**:
  ```rust
  pub trait DerefMut: Deref {
      fn deref_mut(&mut self) -> &mut Self::Target;
  }
  ```
* **Deref Coercion**: Konversi implisit dari referensi tipe yang mengimplementasikan `Deref` menjadi referensi target aslinya (misal: `&Box<String>` dapat langsung dipassing ke fungsi yang menerima `&str`).
* **`trait Drop`**:
  ```rust
  pub trait Drop {
      fn drop(&mut self);
  }
  ```
* **Drop Flags**: Nilai boolean tak terlihat yang disematkan oleh kompilator pada *stack frame* untuk melacak status suatu variabel (sudah di-*move* atau belum) guna memastikan destruksi tidak terjadi ganda (*double-free*) atau terlewat (*resource leak*).

---

### 6. How
Alur kerja kompilator saat memproses `Box<T>`, `Deref`, dan `Drop`:

1. **Alokasi Heap**:
   Saat `Box::new(val)` dipanggil:
   * Kompilator menghitung `Layout::new::<T>()` (ukuran dan perataan/alignment).
   * Alokator mengalokasikan memori virtual via libc (`malloc`) atau jemalloc.
   * Nilai `val` disalin dari stack ke alamat heap yang baru diperoleh.
   * Alamat memori disimpan dalam pointer internal `Box`.

2. **Resolusi Dereferensiasi**:
   Saat mengeksekusi `*b` di mana `b: Box<T>`:
   * Kompilator memeriksa apakah `Box<T>` mengimplementasikan `Deref`.
   * Kompilator mendesugarisasi ekspresi `*b` menjadi `*(b.deref())`.
   * Jika tipe hasil dereferensiasi belum cocok dengan tanda tangan (*signature*) yang diminta, kompilator menerapkan deref chain secara rekursif (`T -> U -> V`).

3. **Mekanika Deallokasi (*Drop Glue*)**:
   Saat variabel `b` keluar dari *scope*:
   * Kompilator memeriksa *drop flag* variabel. Jika aktif:
   * Eksekusi blok `Drop::drop(&mut b)` spesifik untuk pembersihan sumber daya internal.
   * Kompilator secara otomatis memanggil deallokator heap (`alloc::alloc::dealloc`) untuk membebaskan blok memori target pointer.
   * Nilai variabel dihapus dari *stack frame*.

---

### 7. Analogy
Bayangkan **Stack** seperti meja kerja Anda yang sempit dan terorganisir rapi. Setiap benda yang diletakkan di sana harus memiliki ukuran cetak yang pas dan terdefinisi agar tidak menghalangi benda lain. 

Jika Anda ingin menyimpan sebuah **buku ensiklopedia tebal 5.000 halaman yang bisa bertambah halamannya kapan saja (data dinamis/rekursif)**, meletakkannya langsung di meja kerja akan membuat meja penuh atau runtuh (*Stack Overflow*). 

Solusinya: Anda menyimpan ensiklopedia tersebut di **Gudang Logistik Pusat (Heap)**. Gudang memberi Anda selembar **Kupon Pengambilan/Kunci Loker (Smart Pointer `Box`)**. Kupon berukuran kecil dan seragam, pas disimpan di meja kerja Anda (Stack). 

* **Deref**: Ketika Anda perlu membaca ensiklopedia, Anda menunjukkan kupon itu dan petugas gudang langsung membuka akses ke isi buku tanpa Anda harus repot memindahkan buku ke meja kerja.
* **Drop**: Ketika Anda merobek dan membuang kupon tersebut (keluar dari *scope*), petugas gudang secara otomatis membakar ensiklopedia di gudang tersebut dan mengosongkan raknya, sehingga tidak ada ruang gudang yang terbuang percuma (*No Memory Leak*).

---

### 8. Diagram
Struktur memori `Box<T>` dan hierarki dereferensiasi:

```
STACK FRAME                                          HEAP ALLOCATION
+-----------------------------+                     +-----------------------------+
| Variabel: my_box            |                     | Alamat: 0x7FFF_0040         |
| Type: Box<CustomNode>       |                     | Type: CustomNode            |
| +-------------------------+ |                     | +-------------------------+ |
| | ptr: 0x7FFF_0040        | |-------------------->| | id: 101                 | |
| +-------------------------+ |                     | | payload: "Core Engine"  | |
| (Ukuran pointer: 8-byte)    |                     | +-------------------------+ |
+-----------------------------+                     +-----------------------------+
               |
               | Eksekusi Deref (*my_box / my_box.method())
               v
Desugaring: `*(my_box.deref())`
Akses langsung ke nilai field di 0x7FFF_0040 tanpa menyalin data ke stack.

SAAT KELUAR SCOPE (RAII DROP CYCLE):
+-------------------------------------------------------------------------+
| 1. Evaluasi Drop::drop(&mut my_box)                                     |
| 2. Panggil alloc::alloc::dealloc(0x7FFF_0040, Layout::of::<CustomNode>) |
| 3. Invalidate my_box pada stack frame                                    |
+-------------------------------------------------------------------------+
```

---

### 9. Simple Example
Implementasi struktur data rekursif Cons-List menggunakan `Box<T>`:

```rust
// Tanpa Box, definisi ini memicu: error[E0072]: recursive type has infinite size
#[derive(Debug)]
enum List {
    Cons(i32, Box<List>),
    Nil,
}

use List::{Cons, Nil};

fn main() {
    // Alokasi memori berantai di heap
    let list = Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))));
    
    println!("Daftar rekursif berhasil dialokasikan: {:?}", list);
    // Seluruh simpul heap dibebaskan secara rekursif saat `list` keluar dari scope di sini.
}
```

---

### 10. Practical Example
Implementasi *smart pointer* kustom `LoggedBox<T>` yang mengemulasi alokasi memori manual, instrumentasi akses memori via `Deref`/`DerefMut`, dan pembersihan deterministik via `Drop`.

```rust
use std::alloc::{alloc, dealloc, Layout};
use std::fmt::{self, Display};
use std::ops::{Deref, DerefMut};
use std::ptr::{self, NonNull};

pub struct LoggedBox<T> {
    ptr: NonNull<T>,
}

impl<T> LoggedBox<T> {
    pub fn new(value: T) -> Self {
        let layout = Layout::new::<T>();
        
        // Memastikan tipe data bukan Zero-Sized Type (ZST) untuk penyederhanaan alokator
        assert!(layout.size() > 0, "Alokasi ZST tidak didukung pada pointer ini");

        unsafe {
            let raw_ptr = alloc(layout) as *mut T;
            let non_null = NonNull::new(raw_ptr).expect("Alokasi heap kehabisan memori (OOM)");
            
            // Tulis nilai ke memori heap tanpa membaca memori yang belum diinisialisasi
            ptr::write(non_null.as_ptr(), value);
            
            println!("[ALLOC] Dialokasikan {} bytes pada {:p}", layout.size(), non_null.as_ptr());
            LoggedBox { ptr: non_null }
        }
    }
}

impl<T> Deref for LoggedBox<T> {
    type Target = T;

    fn deref(&self) -> &Self::Target {
        println!("[DEREF] Akses read-only ke pointer {:p}", self.ptr.as_ptr());
        unsafe { self.ptr.as_ref() }
    }
}

impl<T> DerefMut for LoggedBox<T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        println!("[DEREF_MUT] Akses mutable ke pointer {:p}", self.ptr.as_ptr());
        unsafe { self.ptr.as_mut() }
    }
}

impl<T> Drop for LoggedBox<T> {
    fn drop(&mut self) {
        let layout = Layout::new::<T>();
        unsafe {
            println!("[DROP] Menjalankan destruktor dan deallokasi {:p}", self.ptr.as_ptr());
            // 1. Jalankan destruktor nilai T (jika T mengimplementasikan Drop)
            ptr::drop_in_place(self.ptr.as_ptr());
            // 2. Bebaskan memori fisik pada alokator heap
            dealloc(self.ptr.as_ptr() as *mut u8, layout);
        }
    }
}

// Demonstrasi Deref Coercion
fn cetak_teks(teks: &str) {
    println!("[PRINT CONSUMER] Value: {}", teks);
}

#[derive(Debug)]
struct SessionSession {
    user_id: u64,
    token: String,
}

fn main() {
    {
        println!("--- Inisialisasi Smart Pointer ---");
        let mut session = LoggedBox::new(SessionSession {
            user_id: 42,
            token: String::from("secret_auth_token_999"),
        });

        // Mutasi via DerefMut
        session.user_id = 84;

        // Deref Coercion: &LoggedBox<SessionSession> -> &SessionSession -> &str
        // Mengakses subfield via deref transparan
        println!("User ID aktif: {}", session.user_id);

        println!("--- Demonstrasi String Deref Coercion ---");
        let boxed_string = LoggedBox::new(String::from("Payload Data Transaksi"));
        // Coercion dari &LoggedBox<String> ke &str
        cetak_teks(&boxed_string);

        println!("--- Meninggalkan Scope ---");
    } // Drop dieksekusi secara otomatis dan aman di sini
    println!("--- Scope Berakhir Sepenuhnya ---");
}
```

---

### 11. Real World Example
**Studi Kasus: Engine Parsing Abstract Syntax Tree (AST) pada Sistem Kompilator Skala Besar (mirip `rustc` atau Babel/SWC).**

Dalam arsitektur *parser* produksi, ukuran ekspresi bahasa tidak dapat diprediksi saat waktu kompilasi. Setiap modul kode dievaluasi ke dalam simpul AST. Jika ekspresi biner didefinisikan secara langsung:
```rust
// AKAN GAGAL KOMPILASI
enum BadExpr {
    Literal(i64),
    Binary {
        op: char,
        left: BadExpr,  // Ukuran tidak terbatas!
        right: BadExpr, // Ukuran tidak terbatas!
    },
}
```
Arsitek perangkat lunak menggunakan alokasi heap via `Box` untuk memastikan ukuran enum `Expr` konstan (hanya seukuran tag diskriminan + pointer metadata):

```rust
#[derive(Debug, PartialEq)]
pub enum BinaryOp {
    Add, Sub, Mul, Div
}

#[derive(Debug, PartialEq)]
pub enum Expr {
    Number(f64),
    Binary {
        op: BinaryOp,
        left: Box<Expr>,
        right: Box<Expr>,
    },
}

impl Expr {
    // Evaluasi rekursif melintasi heap pointers
    pub fn eval(&self) -> f64 {
        match self {
            Expr::Number(n) => *n,
            Expr::Binary { op, left, right } => {
                let l = left.eval();
                let r = right.eval();
                match op {
                    BinaryOp::Add => l + r,
                    BinaryOp::Sub => l - r,
                    BinaryOp::Mul => l * r,
                    BinaryOp::Div => {
                        if r == 0.0 {
                            panic!("Floating point division by zero");
                        }
                        l / r
                    }
                }
            }
        }
    }
}

// Simulasi pembuatan node AST oleh Lexer & Parser
fn main() {
    // Representasi: (10.0 + 20.0) * 2.0
    let ast = Expr::Binary {
        op: BinaryOp::Mul,
        left: Box::new(Expr::Binary {
            op: BinaryOp::Add,
            left: Box::new(Expr::Number(10.0)),
            right: Box::new(Expr::Number(20.0)),
        }),
        right: Box::new(Expr::Number(2.0)),
    };

    assert_eq!(ast.eval(), 60.0);
    println!("AST Evaluation Result: {}", ast.eval());
}
```
Pendekatan ini memisahkan konsumsi memori stack (yang seragam dan flat) dari variansi kedalaman rantai token yang dievaluasi di heap.

---

### 12. Trade-offs

| Dimensi | Alokasi Stack (Nilai Mentah) | Alokasi Heap via `Box<T>` |
| :--- | :--- | :--- |
| **Kecepatan Akses (Latency)** | Sangat Cepat (Akses lokal register / L1 Cache). | Terdapat penalti *pointer indirection* (potensial *L1/L2 Cache Miss*). |
| **Biaya Alokasi** | $\mathcal{O}(1)$ instan (cuma geser pointer `RSP`). | Melibatkan *system call* / algoritma pencarian blok allocator. |
| **Batas Kapasitas** | Terbatas (umumnya 2MB - 8MB). Bahaya *stack overflow*. | Dibatasi oleh kapasitas total Virtual Memory OS. |
| **Fleksibilitas Ukuran** | Harus `Sized` saat kompilasi. | Mampu menampung tipe *Dynamic Sized* (`dyn Trait`, slices). |
| **Fragmentasi Memori** | Nol fragmentasi (LIFO cleaning). | Membuka celah fragmentasi heap jika alokasi/dealokasi sporadis. |
| **Kompleksitas Kode** | Sangat Rendah. | Sedang (Perlu manajemen *ownership move* dan *borrowing*). |

---

### 13. When To Use
* **Tipe Data Rekursif**: Wajib digunakan saat merancang struktur data rekursif (misal: Trees, Graphs, Linked Lists) untuk memberikan batas ukuran tipe yang terdefinisi pada fase kompilasi.
* **Transfer Objek Berukuran Raksasa Tanpa Salin Data**: Memindahkan *ownership* struktur data berukuran gigantik (misal: *buffer* gambar 50MB). Memindahkan `Box` hanya menyalin pointer 8-byte pada stack, alih-alih menyalin keseluruhan 50MB byte-per-byte (*deep copy*).
* **Trait Objects (Dynamic Dispatch)**: Ketika Anda membutuhkan polimorfisme murni di mana ukuran tipe konkret tidak diketahui pada waktu kompilasi, Anda harus menggunakan tipe terbungkus seperti `Box<dyn Error>` atau `Box<dyn Handler>`.

---

### 14. When NOT To Use
* **Tipe Primitif Berukuran Kecil**: Membungkus tipe primitif seperti `i32`, `bool`, atau `(f32, f32)` ke dalam `Box` adalah anti-pattern berat. Biaya alokasi heap dan *cache miss* jauh melampaui ukuran data itu sendiri.
* **Operasi Matriks pada *Hot Paths***: Dalam komputasi numerik performa tinggi (*Game Loops*, *HFT Engine*), alokasi `Box` berantai menyebabkan fragmentasi memori cache. Gunakan struktur data *flat contiguous array* seperti `Vec<T>` teralokasi di muka (*pre-allocated*) daripada graf berisi pointer `Box`.

---

### 15. Common Mistakes
1. **Mencoba Mengimplementasikan `Drop` dan `Copy` Bersamaan**:
   ```rust
   // INVALID: Kompilator menolak implementasi Drop jika Copy aktif
   struct InvalidStruct;
   impl Copy for InvalidStruct {}
   impl Clone for InvalidStruct { fn clone(&self) -> Self { *self } }
   impl Drop for InvalidStruct {
       fn drop(&mut self) {}
   }
   // Error: E0184: the trait `Copy` may not be implemented for this type; the type has a destructor
   ```
2. **Rekursif Drop Stack Overflow**:
   Menghapus *linked list* berbasis `Box` yang memiliki jutaan elemen secara default akan menyebabkan *stack overflow* karena destruktor `Drop::drop` dieksekusi secara rekursif hingga ke simpul terbawah.
   *Solusi*: Implementasikan `Drop` manual dengan iterasi manual (`while let`) untuk membongkar node satu per satu secara linear.
3. **Mengekstrak Nilai di Balik Deref Pointer Tanpa Move yang Sah**:
   Mencoba mengambil nilai `T` dari `&Box<T>` via `*box_ref` akan memicu kompilator memprotes perpindahan kepemilikan dari referensi yang dipinjam (*Error E0507*).

---

### 16. Best Practices (Production Checklist)
- [ ] **Gunakan `Box::pin` untuk Self-Referential Types**: Jika data yang dialokasikan di heap tidak boleh bergeser alamat memorinya (misalnya saat bekerja dengan `Future` atau pointer FFI), bungkus menggunakan `Box::pin(data)`.
- [ ] **Minimalisir Tingkat Indirection**: Hindari pola anti-pattern `Box<Vec<T>>` atau `Box<String>`. Baik `Vec` maupun `String` sudah merupakan smart pointer heap secara internal. Melakukannya akan menghasilkan *double indirection* (`Pointer -> Pointer -> Buffer`).
- [ ] **Hindari Rekursi Destruksi Tak Terbatas**: Definisikan pembersihan loop iteratif untuk struktur data rantai panjang yang mengandalkan `Box<T>`.
- [ ] **Manfaatkan Deref Coercion pada Parameter Fungsi**: Jangan membuat fungsi menerima `&Box<Path>`. Definisikan parameter sebagai `&Path` agar fungsi dapat menerima referensi langsung tanpa memaksa pemanggil mengalokasikan data ke dalam `Box`.

---

### 17. Troubleshooting

#### Masalah 1: Error `E0072` (Recursive type has infinite size)
*Pesan Error*:
```text
error[E0072]: recursive type `Node` has infinite size
 --> src/main.rs:1:1
  |
1 | struct Node {
  | ^^^^^^^^^^^ recursive type has infinite size
2 |     next: Option<Node>,
  |                  ---- recursive without indirection
  |
help: insert some indirection (e.g., a `Box`, `Rc`, or `&`) to break the cycle
  |
2 |     next: Option<Box<Node>>,
  |                  ++++    +
```
*Solusi*: Bungkus rekursi menggunakan `Box<T>` untuk membatasi ukuran field menjadi $usize$ (8 bytes pada arsitektur 64-bit).

#### Masalah 2: Error `E0507` (Cannot move out of dereference)
*Pesan Error*:
```text
error[E0507]: cannot move out of `*my_box` which is behind a shared reference
```
*Penyebab*: Anda mencoba memindahkan kepemilikan nilai di dalam heap sementara Anda hanya memegang referensi ke `Box`.
*Solusi*: Ambil referensi ke isinya (`&*my_box`), implementasikan `Clone`, atau gunakan metode pengambilalihan eksplisit seperti `std::mem::take` / `std::mem::replace` jika tipe target mengimplementasikan `Default`.

---

### 18. Exercise
1. **Analisis Kompilator AST Ukuran**:
   Buat sebuah `enum BinaryTree` yang memiliki dua varian: `Leaf(i32)` dan `Branch { left: Box<BinaryTree>, right: Box<BinaryTree> }`.
   Cetak ukuran dari `std::mem::size_of::<BinaryTree>()` dan bandingkan dengan ukuran referensi mentah `std::mem::size_of::<&BinaryTree>()`.
2. **Implementasi Safe Iterative Dropper**:
   Kembangkan struktur data *Singly Linked List* sederhana yang menampung 500.000 elemen numerik di heap menggunakan `Box`. Implementasikan *trait* `Drop` khusus secara manual yang membersihkan memori secara iteratif untuk mencegah *stack overflow* saat keluar dari *scope*.

---

### 19. Challenge
Rancanglah sebuah struktur data kustom bernama **`AlignedBox<T, const ALIGN: usize>`** yang memenuhi kriteria berikut:
1. Mampu mengalokasikan tipe generik `T` pada heap dengan perataan (*memory alignment*) khusus yang ditentukan melalui konstanta `ALIGN` (misal: 64-byte untuk SIMD *cache-line boundary* alignment), memanfaatkan `std::alloc::alloc` dan `std::alloc::Layout::from_size_align`.
2. Mengimplementasikan `Deref` dan `DerefMut` secara sempurna sehingga data di dalamnya dapat diakses layaknya variabel reguler.
3. Mengimplementasikan `Drop` yang menjamin pelepasan memori dengan tata letak (*layout*) yang presisi sama saat memori dialokasikan.
4. **Safety Constraint**: Konstruktor wajib melakukan verifikasi waktu kompilasi (*compile-time assertion*) atau validasi eksplisit bahwa `ALIGN` adalah bilangan pangkat dua (*power of two*) dan lebih besar atau sama dengan `std::mem::align_of::<T>()`. Seluruh operasi `unsafe` harus didokumentasikan dengan klausul `// SAFETY:` yang valid.

---

### 20. Summary
* `Box<T>` adalah abstraksi fundamental Rust untuk alokasi memori tunggal pada heap dengan determinisme waktu pembersihan via RAII.
* Implementasi `Deref` dan `DerefMut` mentransformasikan *smart pointer* menjadi referensi target secara ergonomis melalui *Deref Coercion* tanpa biaya performa *runtime*.
* Mekanisme `Drop` menjamin pencegahan *memory leak* dan pembebasan sumber daya sistem secara aman, di mana urutan eksekusi dikelola oleh *compiler-generated drop glue*.
* Memahami batasan *indirection* dan tata letak memori stack-heap merupakan fondasi kritikal untuk menulis kode Rust tingkat lanjut yang efisien, aman, dan siap diproduksi.