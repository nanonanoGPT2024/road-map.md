# BAB 02: Quiz, Challenge, & Knowledge Check
**Tipe Data Maju, Polimorfisme, & Abstraksi Nol-Biaya**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Kompilasi: Monomorphization vs Dynamic Dispatch
Jelaskan secara mendalam siklus transformasi kode Rust dari source code hingga binary code saat menggunakan Generic (*Static Dispatch*) dibandingkan dengan Trait Object (`dyn Trait` / *Dynamic Dispatch*). 
* Apa yang terjadi pada fase LLVM IR untuk kedua pendekatan tersebut?
* Analisis trade-off keduanya ditinjau dari *instruction cache (I-cache) locality*, *binary bloat*, dan potensi optimasi kompilator seperti *inlining* serta *dead-code elimination*.

### Soal 1.2: Semantik Associated Types vs Generic Type Parameters
Dalam perancangan Trait, kapan seorang System Architect harus memilih *Associated Types* (misal: `type Item;`) dibandingkan *Generic Parameters* (misal: `Trait<T>`)? 
* Jelaskan bagaimana perbedaan keduanya memengaruhi *trait coherence*, *orphan rules*, dan implikasi terhadap kebutuhan anotasi tipe (*type annotation burden*) pada *call-site*.
* Mengapa `std::ops::Add` menggunakan parameter generik dengan nilai default (`trait Add<Rhs = Self>`), sedangkan `std::iter::Iterator` menggunakan associated type (`type Item`)?

### Soal 1.3: Mekanisme Dynamically Sized Types (DST) dan Bound `?Sized`
Rust menerapkan bound implisit `T: Sized` pada semua fungsi generik secara default.
* Mengapa kompilator membutuhkan ukuran tipe data yang pasti pada waktu kompilasi (*compile-time size guarantee*) untuk variabel lokal?
* Bagaimana Rust mengelola tipe data yang tidak berukuran pasti (*Dynamically Sized Types* seperti `str`, `[T]`, dan `dyn Trait`)? 
* Jelaskan struktur internal representasi memori dari *fat pointer* (pointer ganda) yang digunakan Rust untuk mereferensikan DST tersebut.

### Soal 1.4: Zero-Cost Abstraction pada Idiom Newtype
Konsep *Newtype Pattern* membungkus tipe data primitif atau struktur data lain ke dalam sebuah `struct` tuple tunggal (misal: `struct RawSocket(i32);`).
* Buktikan mengapa idiom ini dikategorikan sebagai *zero-cost abstraction* ditinjau dari *memory layout*, *calling convention*, dan register allocation pada arsitektur x86_64/AArch64.
* Bagaimana idiom ini mencegah cacat logika seperti *unit mismatch* (misal: mencampur Milidetik dan Nanodetik) langsung pada tahap analisis semantik kompilator tanpa overhead CPU runtime?

### Soal 1.5: Niche Value Optimization & Layout Memori Enum
Rust memanfaatkan konsep *undefined bit patterns* untuk melakukan *Niche Value Optimization* (atau *Field Inhabitation Optimization*).
* Jelaskan bagaimana kompilator merepresentasikan `Option<&T>` dan `Option<std::ptr::NonNull<T>>` di dalam memori sehingga menghasilkan `size_of::<Option<&T>>() == size_of::<&T>()`.
* Apa yang terjadi jika tipe data yang dibungkus tidak memiliki *niche* (seperti `Option<u8>`)? Uraikan perhitungan alignment dan padding yang terjadi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Aturan Object Safety (Dyn-Compatibility)
Diberikan kode Rust berikut yang gagal dikompilasi:
```rust
pub trait MetricSink {
    fn record<T: Into<f64>>(&mut self, name: &str, value: T);
    fn snapshot(&self) -> Self;
}

pub fn register_sink(sink: Box<dyn MetricSink>) {
    // ...
}
```
* Identifikasi dua pelanggaran aturan *dyn-compatibility* (dahulu disebut *Object Safety*) pada trait `MetricSink` di atas.
* Jelaskan secara teknis arsitektur vtable mengapa pemanggilan method generic dan pengembalian tipe `Self` secara *by-value* mustahil direpresentasikan secara aman melalui *virtual dispatch pointer*.
* Berikan refactoring kode agar trait tersebut dapat digunakan sebagai Trait Object tanpa mengorbankan fungsionalitas aslinya.

### Soal 2.2: Fully Qualified Syntax & Ambiguity Disambiguation
Dalam sebuah sistem finansial berkinerja tinggi, struktur data `OrderBook` mengimplementasikan dua trait berbeda: `MarketData` dan `AuditLog`. Kedua trait memiliki fungsi dengan signature identik: `fn sequence_id(&self) -> u64;`. Selain itu, `OrderBook` juga memiliki implementasi inheren (`impl OrderBook`) dengan nama method yang sama.
* Tuliskan sintaks *Fully Qualified Syntax* (Universal Method Call Syntax) untuk memanggil ketiga variasi method tersebut secara eksplisit tanpa ambiguitas compiler.
* Bagaimana kompilator Rust mendeteksi dan menyelesaikan hirarki resolusi method (*method resolution order*) sebelum memaksa developer menggunakan sintaks eksplisit?

### Soal 2.3: Variansi dan Subtyping Lifetime (`Covariance`, `Contravariance`, `Invariance`)
Jelaskan interaksi antara *lifetime* dan sistem tipe data lanjut Rust:
* Mengapa `&'a T` bersifat *covariant* terhadap `'a` dan `T`, sedangkan `&'a mut T` bersifat *invariant* terhadap `T` meskipun *covariant* terhadap `'a`?
* Apa bahaya fatal terhadap *memory safety* (tunjukkan contoh konkret mutasi pointer) jika kompilator mengizinkan `&'a mut T` bersifat *covariant* terhadap `T`?

### Soal 2.4: Drop Check & Peran Penanda `PhantomData<T>`
Perhatikan implementasi pointer pintar kustom berikut:
```rust
use std::ptr::NonNull;

pub struct CustomRef<T> {
    ptr: NonNull<T>,
}
```
* Mengapa implementasi di atas dianggap belum aman oleh kompilator jika `CustomRef<T>` mengimplementasikan `Drop` dan memiliki tanggung jawab atas dealokasi data bertipe `T`?
* Bagaimana `std::marker::PhantomData<T>` mengubah perilaku *Drop Checker* (`eyepatch` / RFC 1238) untuk memastikan tidak terjadi *dangling reference* atau *use-after-free* saat struct tersebut didestruksi?

### Soal 2.5: Iterator Pipeline Inlining vs Imperative Loop
Sebuah algoritma pemrosesan data numerik ditulis dengan dua cara:
* Pendekatan A: Loop imperatif manual dengan indexing `for i in 0..slice.len() { ... }`.
* Pendekatan B: Rantai iterator fungsional `slice.iter().copied().map(...).filter(...).fold(...)`.
Jelaskan secara arsitektural mengapa Pendekatan B sering kali menghasilkan assembly yang lebih optimal daripada Pendekatan A pada release build (`-C opt-level=3`). Hubungkan jawaban Anda dengan *bounds checking elimination*, *vectorization auto-loop unrolling (SIMD)*, dan peran internal trait `TrustedLen`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Akibat Monomorphization Bloat
**Konteks:** Sebuah mesin *order-matching* kripto berlatensi ultra-rendah (sub-mikrodetik) mengalami degradasi performa p99.9 yang parah setelah penambahan beberapa generic pipeline untuk menangani berbagai tipe aset (*Crypto*, *FX*, *Equities*, *Derivatives*) dan berbagai variasi protokol jaringan (*FIX*, *Binary WS*, *gRPC*). Profiling hardware menggunakan `perf` menunjukkan metrik `iTLB-load-misses` (Instruction Translation Lookaside Buffer) dan `L1-icache-load-misses` melonjak 400%. Ukuran binary executable membengkak dari 15MB menjadi 180MB.

**Pertanyaan Diagnostik:**
1. Bagaimana arsitektur nested generics (`Pipeline<A, B, C, D>`) memicu fenomena *code bloat* ini pada level machine code?
2. Bagaimana Anda merancang mitigasi menggunakan teknik *Type Erasure* parsial (*hybrid static-dynamic dispatch*), di mana hot-path loop tetap memanfaatkan monomorphization namun cold-path / orchestration path dialihkan ke bounded dynamic dispatch?
3. Rancang sebuah pola refactoring untuk membuktikan penurunan footprint binary tanpa mengorbankan performa eksekusi hot-path per trade event.

---

### Skenario B: Kerusakan Vtable pada Plugin FFI Dinamis
**Konteks:** Perusahaan Anda membangun arsitektur Core Engine yang memuat ekstensi analitik pihak ketiga secara dinamis (*hot-reloading via `libloading` / `.so` files*). Engine membagikan trait object `&mut dyn PluginContext` ke library yang dimuat. Di lingkungan staging, sistem tiba-tiba mengalami crash fatal dengan sinyal `SIGSEGV (Address boundary error)` tepat saat memanggil method kedua dari trait object tersebut, meskipun pemanggilan method pertama berhasil dengan valid.

**Pertanyaan Diagnostik:**
1. Mengapa membagikan `dyn Trait` lintas batas dynamic shared library (*dynamic linking / FFI boundary*) merupakan tindakan berbahaya dalam Rust standar? Jelaskan hubungannya dengan kestabilan ABI Rust dan struktur internal vtable.
2. Apa penyebab method pertama berhasil dipanggil namun method kedua memicu *invalid memory dereference*?
3. Bagaimana Anda merekayasa ulang arsitektur interface plugin ini menggunakan pendekatan `repr(C)` fat-pointer manual atau *stable ABI vtable struct* agar aman dari perbedaan versi kompilator atau flags optimasi?

---

### Skenario C: Dilema Polimorfisme pada Sistem Telemetri Tanpa Alokasi (`no_std`)
**Konteks:** Anda mendesain subsistem agregasi sensor IoT otomotif (Safety-Critical Engine ECU) menggunakan `#![no_std]`. Memori dinamis (heap) dilarang secara absolut (`alloc` crate dinonaktifkan; zero dynamic allocation policy). Sistem menerima aneka variasi frame telemetri: `CanFrame` (8 bytes payload), `CanFdFrame` (64 bytes payload), dan `EthernetDiagnosticFrame` (1518 bytes payload). Semua tipe harus diproses oleh pipeline analitik terpadu yang mematuhi kontrak trait `ProcessableFrame`.

**Pertanyaan Diagnostik:**
1. Evaluasi secara kritis tiga opsi arsitektur berikut dalam batasan ketat *zero heap allocation*:
   * **Opsi 1:** Monomorphization murni (`fn process<T: ProcessableFrame>(frame: T)`).
   * **Opsi 2:** Closed-set Polymorphism menggunakan `enum` tagged union.
   * **Opsi 3:** Dynamic Dispatch berbasis Stack Storage (`&dyn ProcessableFrame` atau custom inline fat pointer storage).
2. Jika memori RAM mikroprosesor sangat terbatas (hanya 128KB SRAM), jelaskan risiko *worst-case stack frame sizing* pada Opsi 2 (Enum) akibat payload `EthernetDiagnosticFrame` yang besar, dan bagaimana Anda mengatasinya tanpa melanggar aturan zero-heap allocation.
3. Arsitektur mana yang paling optimal untuk menjamin *bounded execution time* (WCET - Worst-Case Execution Time) sekaligus efisiensi footprint memori?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Allocation Event Processing Pipeline

#### Problem Statement
Dalam infrastruktur telemetri jaringan berkecepatan 100 Gbps, paket data masuk harus diproses melalui serangkaian filter, transformer, dan agregator. Implementasi generic standard sering kali menyebabkan kompilasi biner yang sangat besar, sementara implementasi Trait Object konvensional (`Box<dyn Filter>`) memicu alokasi heap yang membunuh throughput melalui *heap contention* dan *pointer chasing*. 

Anda ditugaskan merancang sebuah pipeline pemrosesan event polimorfik yang sepenuhnya berjalan di atas **Stack**, mendukung **Abstraksi Nol-Biaya**, dan **Zero Heap Allocation**, serta mampu menggabungkan Static Dispatch dan Bounded Dynamic Dispatch secara mulus.

#### Requirements
1. **Core Trait & Abstraction:**
   * Definisikan trait `Event` yang memiliki associated type `Payload` dan method untuk validasi integritas payload.
   * Definisikan trait `Stage<E: Event>` yang dapat memproses event dan menghasilkan `Result<E, PipelineError>`.
2. **Inline Type Erasure Container (No-Heap Fat Pointer):**
   * Buat sebuah struktur data `InlineStageBox<E, const MAX_SIZE: usize, const ALIGNMENT: usize>` yang mampu menyimpan implementasi `Stage<E>` apapun secara inline pada stack memori lokal (tanpa pernah memanggil global allocator), lengkap dengan vtable manual atau safe invocation wrapper.
   * Implementasikan verifikasi static assertion pada waktu kompilasi untuk memastikan bahwa `size_of::<T>() <= MAX_SIZE` dan `align_of::<T>() <= ALIGNMENT`.
3. **Pipeline Construction:**
   * Bangun abstraction `Pipeline` yang dapat merangkai tahapan statis (monomorphized) dan tahapan dinamis (`InlineStageBox`) secara sekuensial menggunakan *fluent builder pattern*.
4. **Zero-Panic Guarantee & Soundness:**
   * Pipeline tidak boleh memicu panic dalam kondisi runtime apapun (`panic = "abort"` safe). Seluruh error harus didelegasikan melalui varian enum `PipelineError`.
   * Jika ada penggunaan blok `unsafe` pada implementasi `InlineStageBox`, buktikan keamanan memorinya melalui dokumentasi `// SAFETY:` invariants yang ketat (mencakup alignment, drop semantics, dan pointer provenance).

#### Constraints
* Lingkungan harus mendukung kompilasi `#![no_std]` (hanya bergantung pada `core`).
* Dilarang menggunakan alokasi dinamis apapun (`Box`, `Vec`, dsb).
* Kode harus lolos pengujian *Memory Sanitizer* (Miri) tanpa undefined behavior.

#### Expected Output
1. File modul Rust yang mandiri (`pipeline.rs`).
2. Suite unit test yang mencakup:
   * Eksekusi event melalui minimal 3 stage berbeda.
   * Bukti bahwa `size_of_val` dari container dynamic dispatch bersifat konstan.
   * Eksekusi destruktor (`Drop`) terpanggil secara presisi untuk setiap stage yang disimpan di dalam `InlineStageBox` ketika pipeline keluar dari scope.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan representasi level mesin antara *Static Dispatch* (Monomorphization) dan *Dynamic Dispatch* (vtable lookup via fat pointers: data pointer + vtable pointer).
- [ ] Karakteristik dan limitasi *Object Safety* / *Dyn-Compatibility* (RFC 2035) serta alasan teknis di balik restriksi method generik dan pengembalian tipe `Self`.
- [ ] Mekanisme kerja kompilator terhadap DST (*Dynamically Sized Types*) dan peran relaksasi boundary `T: ?Sized`.
- [ ] Aturan resolusi subtyping terhadap *Lifetime Variance* (`Covariant`, `Contravariant`, dan `Invariant`) pada pointer mentah dan referensi terikat.
- [ ] Konsep optimasi internal memori: *Niche Value Optimization*, *Zero-Sized Types (ZST)* layout, *Field Ordering*, dan *Data Alignment/Padding*.
- [ ] Bagaimana iterator abstractions dioptimasi hingga setara atau melampaui raw loop oleh LLVM optimizer melalui inlining dan pengeliminasian bounds-check.

### Saya tidak perlu menghafal:
- [ ] Struktur offset byte biner persis dari vtable yang dihasilkan oleh rustc (karena ABI internal rustc belum distabilkan dan dapat berubah antar-versi kompilator).
- [ ] Urutan tepat algoritma konvergensi monomorphization internal pada compiler driver.
- [ ] Nomor registrasi RFC historis untuk setiap fitur trait system (cukup pahami konsep semantiknya).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan memperbaiki kesalahan kompilasi rumit terkait *Trait Bound Not Satisfied*, *Conflicting Implementations*, dan *Object Safety Violations*.
- [ ] Menggunakan *Fully Qualified Syntax* (`<Type as Trait>::method(...)`) untuk memecahkan trait method collisions.
- [ ] Mendesain arsitektur domain system yang mengeksploitasi *Zero-Cost Abstractions* menggunakan *Newtype Pattern* untuk mencapai *type safety* tanpa penalti throughput.
- [ ] Mengimplementasikan container polimorfik berbasis stack/inline storage yang sound menggunakan `core::mem`, `core::ptr`, dan `core::alloc::Layout` tanpa bergantung pada heap allocator.
- [ ] Menganalisis binary assembly via Godbolt (`rustc -O --emit asm`) untuk memverifikasi apakah sebuah abstraksi tingkat tinggi berhasil di-*inline* secara penuh menjadi instruksi CPU primitif.