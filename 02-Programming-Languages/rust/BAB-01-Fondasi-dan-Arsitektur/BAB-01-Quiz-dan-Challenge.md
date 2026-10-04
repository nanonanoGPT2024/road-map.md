# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Bahasa & Sistem Kepemilikan (Ownership & Memory Model)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Invarian Kepemilikan & Deallokasi Deterministik**  
   Jelaskan secara mendalam tiga aturan absolut sistem kepemilikan (*ownership*) di Rust. Mengapa sistem ini meniadakan kebutuhan akan *Tracing Garbage Collector* (GC) sekaligus memitigasi *manual memory management bugs* seperti *use-after-free* dan *double-free* pada saat kompilasi? Hubungkan penjelasan Anda dengan konsep RAII (*Resource Acquisition Is Initialization*).

2. **Diferensiasi Semantik: *Move* vs *Copy* vs *Clone***  
   Secara representasi bit di memori (Level ABI), apa perbedaan mendasar antara tipe data yang mengimplementasikan trait `Copy` dan tipe data yang hanya mengimplementasikan trait `Clone`? Mengapa tipe data yang mengalokasikan memori di heap (seperti `String` atau `Vec<T>`) tidak diizinkan oleh compiler untuk mengimplementasikan trait `Copy`?

3. **Prinsip Eksklusivitas Mutabilitas (*Aliasing XOR Mutability*)**  
   Analisis aturan peminjaman (*borrowing rules*): Anda dapat memiliki $N$ referensi *immutable* (`&T`) **ATAU** tepat satu referensi *mutable* (`&mut T`), tetapi tidak keduanya secara bersamaan. Mengapa pelanggaran terhadap aturan ini pada level arsitektur CPU dan compiler optimization dapat memicu *data race* atau *iterator invalidation*?

4. **Anatomi Memori: *Stack Frame* vs *Heap Layout***  
   Gambarkan dan jelaskan model tata letak memori ketika sebuah variabel `let s = String::from("production");` dideklarasikan di dalam sebuah fungsi. Uraikan komponen data apa saja yang berada di *stack frame* (termasuk *pointer*, *length*, *capacity*) dan apa yang dialokasikan di *heap segment*, serta apa yang dieksekusi oleh compiler ketika variabel tersebut keluar dari *scope* (*Drop flag* dan `drop` glue).

5. **Prinsip Dasar Lifetime: Validitas Referensi Tanpa Overhead**  
   Banyak pengembang keliru menganggap bahwa *lifetime annotation* (seperti `'a`) memperpanjang masa hidup suatu data. Jelaskan apa sebenarnya fungsi generik *lifetime* bagi compiler (*borrow checker*), bagaimana compiler melakukan analisis kesesuaian wilayah (*region inference*), dan buktikan mengapa *lifetime* adalah abstraksi tanpa biaya runtime (*zero-cost abstraction*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme *Reborrowing* vs *Moving* pada Mutable References**  
   Perhatikan potongan kode berikut:
   ```rust
   fn process_data(r: &mut Vec<u8>) {
       r.push(1);
   }

   fn main() {
       let mut data = vec![0u8; 1024];
       let ref_mut = &mut data;
       process_data(ref_mut);
       ref_mut.push(2); // Mengapa baris ini valid?
   }
   ```
   Jelaskan konsep internal *reborrowing* pada `&mut T`. Mengapa mengirimkan `ref_mut` ke fungsi `process_data` tidak memindahkan (*move*) kepemilikan referensi tersebut secara permanen, dan dalam kondisi apa *move semantics* justru terjadi pada referensi?

2. **Evolusi *Non-Lexical Lifetimes* (NLL) & *Drop Elaboration***  
   Sebelum diperkenalkannya NLL di compiler Rust (MIR-based borrow checker), masa hidup sebuah referensi terikat kaku pada akhir kurung kurawal scope leksikalnya (`}`). Jelaskan bagaimana NLL menganalisis *Control Flow Graph* (CFG) dan *Liveness Analysis* untuk memperpendek masa hidup referensi hingga titik terakhir ia digunakan (*point of last use*). Apa dampaknya terhadap fleksibilitas kode?

3. **Anatomi dan Overhead Representasi *Fat Pointers***  
   Bandingkan ukuran memori (`std::mem::size_of`) dan struktur internal antara referensi skalar (`&u64`), referensi *dynamically sized type* / slice (`&[u8]`), dan referensi trait object (`&dyn Any`). Mengapa `&[u8]` dan `&str` membutuhkan 2 *machine words* (16 byte pada arsitektur 64-bit), dan informasi apa saja yang dimuat di dalamnya?

4. **Kasus Khusus: *Partial Move* dalam Struct**  
   Jika sebuah struct tersusun dari beberapa field yang tidak mengimplementasikan `Copy`, seperti:
   ```rust
   struct Session {
       token: String,
       buffer: Vec<u8>,
   }
   ```
   Bagaimana mekanisme *borrow checker* menangani operasi ketika kita memindahkan salah satu field (`let t = session.token;`)? Apa yang terjadi jika setelah operasi tersebut kita mencoba memanggil method yang mengonsumsi `self` secara utuh versus method yang hanya mengakses `&session.buffer`? Bagaimana *drop flag tracking* internal compiler mencatat status deallokasi struct tersebut?

5. **Diagnostik Compiler: Membedah *Dangling Pointer Mitigation***  
   Analisis kode di bawah ini:
   ```rust
   fn get_longest<'a>(x: &'a str, y: &'a str) -> &'a str {
       if x.len() > y.len() { x } else { y }
   }

   fn run() -> &'static str {
       let local_string = String::from("ephemeral");
       let static_str = "constant";
       get_longest(local_string.as_str(), static_str)
   }
   ```
   Sebutkan secara persis pesan error yang dihasilkan oleh borrow checker pada fungsi `run()`. Jelaskan proses penalaran compiler: mengapa relasi subtyping *lifetime* (`'static: 'a`) menolak kompilasi ini meskipun salah satu cabangnya mengembalikan string bertipe `'static`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Akibat Memory Thrashing pada High-Throughput Ingestion
Anda bertindak sebagai *Systems Architect* untuk pipeline pemrosesan log telemetri finansial yang memproses 500.000 events/detik. Metrik APM menunjukkan latensi *p99* membengkak secara eksponensial di bawah beban puncak, dan CPU profiling mendeteksi bahwa thread menghabiskan 35% waktu eksekusi di dalam kernel allocator (`jemalloc` / `glibc malloc` via `pthread_mutex_lock`). Investigasi kode menemukan implementasi parser JSON internal mengekstrak payload teks menggunakan tipe `String` melalui *heap allocation* baru untuk setiap event:
```rust
struct LogEvent {
    trace_id: String,
    payload: String,
    timestamp: u64,
}
```
* **Pertanyaan Diagnostik:**  
  1. Bagaimana Anda merestrukturisasi tipe data `LogEvent` menggunakan referensi slice bersyarat (`&str`) atau `Cow<'a, str>` agar proses deserialisasi dapat beroperasi secara *Zero-Copy* langsung dari buffer jaringan mentah (`&[u8]`)?  
  2. Apa konsekuensi perambatan parameter *lifetime* (`'a`) pada struct `LogEvent` terhadap arsitektur thread pool/pipeline pengiriman data ke worker thread berikutnya, dan bagaimana Anda menyelesaikan batasan `'static` yang dituntut oleh `std::thread::spawn`?

### Skenario B: Refaktorisasi Cyclic Graph Engine Menghindari Data Hazard
Tim Anda sedang membangun *Distributed Dependency Graph Engine* untuk pipeline komputasi terdistribusi. Seorang software engineer senior dari latar belakang C++ mencoba mereplikasi struktur data graf konvensional dengan *bidirectional references* (node induk memegang referensi mutable ke sekumpulan anak, dan setiap anak memegang referensi mutable kembali ke induk):
```rust
struct Node<'a> {
    id: u64,
    parent: Option<&'a mut Node<'a>>,
    children: Vec<&'a mut Node<'a>>,
}
```
Kode ini menghasilkan gelombang kompilasi error borrow checker (*"cannot borrow as mutable more than once at a time"*). Engineer tersebut berargumen ingin menggunakan *raw pointers* (`*mut Node`) dan blok `unsafe` untuk mem-bypass borrow checker demi performa.
* **Pertanyaan Diagnostik:**  
  1. Buktikan potensi bahaya *memory corruption* / *undefined behavior* apa yang diabaikan oleh engineer tersebut jika pendekatan `unsafe` diterapkan tanpa sinkronisasi yang valid pada struktur siklik (misal: modifikasi topologi graf saat rekursi sedang berjalan).  
  2. Berikan solusi arsitektural Rust murni yang aman secara memori (*idiomatic Rust*). Kapan Anda memilih pola *Arena Allocation* berbasis indeks (`SlotMap`/`id-based indexing`) dibandingkan dengan smart pointers (`Rc<RefCell<T>>` / `Arc<RwLock<T>>`) untuk kasus throughput tinggi?

### Skenario C: Cache Layer Arsitektur Zero-Allocation pada Lingkungan Resource-Constrained
Anda sedang merancang modul ring-buffer in-memory caching untuk gateway IoT berarsitektur embedded Linux (memory budget ketat < 16MB). Kebutuhan sistem mengharuskan cache menyimpan pesan-pesan telemetri berukuran variabel tanpa menyebabkan fragmentasi heap dalam jangka panjang. Tim menolak penggunaan `Box`, `Vec`, atau dynamic heap sizing apa pun pada *hot path*.
* **Pertanyaan Diagnostik:**  
  1. Bagaimana Anda merancang struktur data penyimpanan berbasis *contiguous byte array* statis pada stack atau BSS segment yang mengembalikan data dalam bentuk slice bertipe `&'a [u8]`?  
  2. Bagaimana Anda merancang kontrak API dari struktur ring-buffer ini agar borrow checker secara otomatis mencegah buffer tertimpa (*overwritten*) selama pembaca (*reader*) masih memegang referensi pinjaman (`&'a [u8]`) ke segmen data tersebut? Uraikan mekanismenya pada level tipe data (*phantom data / lifetime token pattern*).

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Copy Streaming Packet Frame Decoder

#### Problem
Anda diminta untuk membangun mesin decoding paket biner (*Network Packet Frame Parser*) berkinerja tinggi untuk protokol biner proprietary tanpa melakukan **satu pun alokasi memori di heap** (`alloc` / `free`) selama parsing payload berlangsung.

#### Requirements
1. **Definisi Protokol Biner:**
   Format paket terdiri dari urutan byte berikut:
   - `Magic Bytes` (2 byte): Harus bernilai `[0xAA, 0x55]`.
   - `Packet ID` (2 byte): Big-endian integer (`u16`).
   - `Flags` (1 byte): Bitmask flag status paket.
   - `Payload Length` (2 byte): Big-endian integer (`u16`) yang menentukan panjang segmen data.
   - `Payload Data`: Rentang byte dinamis sesuai nilai `Payload Length`.
   - `Checksum` (1 byte): Operasi bitwise XOR dari semua byte sebelumnya (dari `Magic` hingga akhir `Payload`).

2. **Implementasi Komponen:**
   - Buat struct `PacketFrame<'a>` yang meminjam segmen payload langsung dari buffer input:
     ```rust
     pub struct PacketFrame<'a> {
         pub id: u16,
         pub flags: u8,
         pub payload: &'a [u8],
     }
     ```
   - Buat struct `PacketStreamDecoder` yang menerima stream byte secara bertahap (chunked byte stream), mendeteksi frame yang valid, memverifikasi integritas checksum, dan mengekstrak struct `PacketFrame<'a>`.

3. **Constraints:**
   - **Zero Heap Allocations:** Tidak boleh menggunakan `String`, `Vec`, `Box`, atau tipe data dinamis lain dari modul `alloc`. Kode harus kompatibel dengan lingkungan `#![no_std]`.
   - **Zero Copy:** Data payload pada `PacketFrame<'a>` harus berupa sub-slice langsung dari buffer internal parser.
   - **Partial Read Handling:** Jika buffer input hanya memuat sebagian paket, parser tidak boleh crash atau panik. Parser harus mampu mempertahankan status internal dan menunggu byte berikutnya diumpankan.
   - **Corrupted Frame Handling:** Jika `Magic Bytes` salah atau checksum tidak valid, parser harus mencari frame berikutnya (*resync mechanism*) dengan membuang data corrupt hingga magic sequence berikutnya ditemukan.

4. **Expected Output:**
   Program demonstrasi harus menguji skenario:
   - Decoding satu paket valid utuh.
   - Stream terpecah menjadi beberapa chunk (simulasi fragmentasi paket TCP) dan didecode secara sempurna.
   - Deteksi dan pembuangan paket rusak tanpa panik, dengan stream parsing berlanjut normal ke paket berikutnya.
   - Tolok ukur verifikasi: Alokasi heap = 0 byte (dapat dibuktikan dengan custom memory allocator hook atau pengujian kompatibilitas `#![no_std]`).

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman teknis Anda sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Mekanisme deterministic memory deallocation melalui RAII dan penurunan kode (*drop elaboration*) oleh compiler Rust.
- [ ] Aturan eksklusivitas peminjaman (*Aliasing XOR Mutability*) dan korelasinya dengan pencegahan *data race* di arsitektur multi-thread.
- [ ] Perbedaan representasi level mesin (*ABI layout*) antara tipe skalar, referensi biasa, fat pointer slice (`&[T]`), dan trait object (`&dyn Trait`).
- [ ] Perbedaan semantik mendasar antara *Move*, *Copy*, dan *Clone*, serta dampaknya terhadap overhead instruksi memori (`memcpy`).
- [ ] Bahwa generic lifetime `'a` adalah mekanisme pembuktian statis kompilator (*static theorem prover*) untuk memvalidasi scope relasional referensi, tanpa overhead instruksi runtime apa pun.
- [ ] Prinsip kerja *Non-Lexical Lifetimes* (NLL) berbasis CFG (*Control Flow Graph*) dan pengaruhnya terhadap *point of last use*.

### Saya tidak perlu menghafal:
- [ ] Penamaan spesifik algoritma internal borrow checker di dalam compiler rustc (misal: Polonius internals / MIR edge indices).
- [ ] Variasi pesan error mentah dari rustc untuk setiap edge case lifetime (fokuslah pada logika *why*-nya, bukan redaksi teks error).
- [ ] Lokasi offset byte spesifik dari metadata vtable pada fat pointer (karena ini adalah implementasi compiler detail yang tidak dijamin stabil oleh Rust ABI).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memitigasi isu *compile-time borrow error* tanpa secara membabi buta menambahkan `.clone()` pada struktur data.
- [ ] Merancang antarmuka struct dan fungsi yang mengekspos *Zero-Copy API* menggunakan slice (`&[u8]`, `&str`) dengan anotasi generic lifetime yang benar.
- [ ] Mendiagnosis dan mengonversi desain arsitektur yang rentan alokasi berlebih (*heap thrashing*) menjadi arsitektur yang aman dan berkinerja tinggi berbasis borrow rules.
- [ ] Mengimplementasikan state machine parsing biner berbasis *lifetimes bounded to stack buffers* tanpa ketergantungan pada dynamic heap allocation.