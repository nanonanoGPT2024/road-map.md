# BAB 03: Quiz, Challenge, & Knowledge Check
**Lifetimes Lanjut & Smart Pointers**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Subtyping dan Variance pada Lifetimes
Jelaskan konsep **Variance** dalam Rust terkait *lifetimes*, khususnya perbedaan mendasar antara sifat **Covariant**, **Invariant**, dan **Contravariant**. Mengapa tipe referensi eksklusif `&'a mut T` bersifat **invariant** terhadap `T`, sementara referensi bersama `&'a T` bersifat **covariant** terhadap `T`? Analisislah konsekuensi keamanan memori (*memory safety*) jika compiler mengizinkan `&'a mut T` menjadi *covariant* terhadap `T`.

### Soal 1.2: Anatomi dan Mekanisme Deref Coercion
Bagaimana cara kerja kompilator Rust saat mengevaluasi dereferensiasi implisit (*Deref Coercion*) melalui *trait* `Deref` dan `DerefMut`? Jelaskan algoritma resolusi tipe yang digunakan compiler ketika memetakan rantai referensi bertingkat (misal: `&&&&T` ke `&U` atau `Arc<Mutex<Vec<T>>>` ke `&[T]`), serta mengapa *Deref Coercion* tidak dikenakan biaya (*zero-runtime-overhead*) pada fase eksekusi.

### Soal 1.3: Alokasi Memori dan Layout: Box<T> vs Rc<T> / Arc<T>
Gambarkan representasi memori visual dan perbedaan struktural pada level *heap metadata* antara `Box<T>`, `Rc<T>`, dan `Arc<T>`. Terangkan komponen-komponen apa saja yang menyusun *control block* pada `Rc<T>` dan `Arc<T>`, serta jelaskan dampak dari *atomic instructions* (seperti `fetch_add` / `fetch_sub` dengan memory ordering tertentu) pada `Arc<T>` terhadap performa cache CPU (*cache-line bouncing*) dibandingkan alokasi pointer biasa.

### Soal 1.4: Interior Mutability dan Batas Invarian Rust
Konsep dasar borrow checker Rust menegaskan prinsip aliasing XOR mutability (`&T` vs `&mut T`). Jelaskan bagaimana *interior mutability* dapat melanggar aturan ini secara aman di tingkat abstraksi compiler. Apa peran fundamental `UnsafeCell<T>` sebagai satu-satunya *primitive core* legal untuk interior mutability, dan mengapa `Cell<T>` aman tanpa overhead alokasi/runtime check sementara `RefCell<T>` membutuhkan overhead *borrow flag*?

### Soal 1.5: Siklus Hidup Alokasi Memori dan Drop Check
Jelaskan urutan deterministik pemanggilan `Drop::drop` pada tipe data komposit (*struct*, *tuple*, *enum*). Bagaimana compiler menentukan urutan penghancuran *field* di dalam sebuah *struct*? Jelaskan pula mengapa pemanggilan fungsi manual `std::mem::drop(x)` secara teknis bukan merupakan pemanggilan langsung ke metode *trait* `Drop`, melainkan fungsi kosong (*no-op*) yang memicu perpindahan kepemilikan (*move*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Higher-Rank Trait Bounds (HRTB)
Diberikan sebuah arsitektur *event handler* atau *deserializer* fungsional dengan closure:
```rust
fn process_payload<F>(handler: F) 
where 
    F: for<'a> Fn(&'a [u8]) -> &'a str 
{
    // ...
}
```
Jelaskan mengapa signature biasa seperti `fn process_payload<'a, F: Fn(&'a [u8]) -> &'a str>(handler: F)` akan memicu kesalahan kompilasi (*borrowed value does not live long enough*) ketika closure menerima referensi ke buffer lokal di dalam *stack frame* fungsi tersebut. Bagaimana HRTB (`for<'a>`) menyelesaikan batas ekspresivitas ini pada level inferensi tipe compiler?

### Soal 2.2: PhantomData, Drop Checker, dan Soundness
Ketika mengimplementasikan custom pointer cerdas atau representasi data FFI:
```rust
struct CustomPtr<T> {
    ptr: *const T,
    _marker: std::marker::PhantomData<T>,
}
```
Jelaskan secara presisi apa konsekuensi semantik bagi compiler Rust jika `_marker: std::marker::PhantomData<T>` dihilangkan (hanya menyisakan `ptr: *const T`). Analisislah kaitannya dengan aturan *variance* (invariance vs covariance), *auto-traits* (`Send`/`Sync`), dan algoritma *Drop Check* (`#[may_dangle]`).

### Soal 2.3: Memory Leak Analysis: Reference Cycles dan Weak Counts
Pada struktur data graf yang dibangun menggunakan `Arc<RefCell<Node>>`, sebuah siklus referensi (*reference cycle*) terbentuk. 
1. Mengapa destruktor `drop` tidak akan pernah dieksekusi meskipun seluruh instansi referensi terluar keluar dari *scope*?
2. Bagaimana mekanisme internal `Arc::downgrade` ke `std::sync::Weak<T>` memecah siklus ini?
3. Jelaskan kondisi di mana memori *heap* untuk alokasi `T` sudah di-drop (melalui `drop_in_place`), namun blok memori heap fisik untuk *control block* `Arc` belum dapat di-dealokasikan (*free*).

### Soal 2.4: Mekanika Pinning dan Address Stability (Pin & Unpin)
Mengapa tipe *self-referential struct* (seperti *state machine* yang di-generate oleh async/await) berbahaya jika dipindahkan (*moved*) dalam memori? Jelaskan bagaimana wrapper pointer `std::pin::Pin<P<T>>` menjamin bahwa nilai di balik pointer tidak akan berpindah alamat sampai memori tersebut di-drop, serta jelaskan peran penandaan *marker trait* `Unpin` dalam meniadakan proteksi pinning tersebut.

### Soal 2.5: Zero-Copy Optimization menggunakan Cow<'a, B>
Tinjau tipe `std::borrow::Cow<'a, B>`. Dalam skenario pemrosesan teks berkecepatan tinggi (*string sanitization* atau *unescaping*):
1. Bagaimana representasi internal enum `Cow` bekerja menghemat alokasi memori?
2. Kapan mutasi memicu pemanggilan `to_owned()`?
3. Debugging: Bagaimana cara membuktikan secara terukur (*via benchmark & memory profile*) bahwa penggantian alokasi langsung `String` menjadi `Cow<'a, str>` mereduksi alokasi heap dan meningkatkan throughput L1/L2 cache?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Skala Besar (Fintech / High-Throughput Engine)
Sebuah sistem *matching engine* perdagangan kripto memproses 250.000 order per detik. Order disimpan dan dibagikan ke beberapa thread analitik menggunakan `Arc<Mutex<OrderBook>>`. 
* **Masalah:** Pada profil metrik CPU (profiling menggunakan `perf`), utilisasi CPU mencapai 100% pada 64 core, namun throughput riil anjlok drastis ke 15.000 order per detik. Analisis mendalam menunjukkan latensi p99 membengkak akibat *cache-line bouncing*, *atomic counter contention* saat cloning `Arc`, dan thread *context switching* masif akibat *lock contention* pada `Mutex`.
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi secara presisi tiga akar penyebab degradasi performa pada level CPU cache coherence protocol (MESI/MOESI) akibat penggunaan `Arc<Mutex<T>>`.
  2. Rancang arsitektur refaktorisasi pengiriman data tanpa shared-state locks (misal: *single-writer lock-free ring buffer*, *crossbeam-channel*, atau teknik *Read-Copy-Update / arc-swap*). Struktur data dan smart pointer mana yang harus dihilangkan atau diganti?
  3. Bagaimana strategi pinning core CPU (*core affinity*) dan modifikasi lifetime data order dapat mengubah kebutuhan data dari alokasi heap dinamis menjadi zero-copy stack/arena reference?

### Skenario B: Race Condition dan Deadlock Siluman (Distributed Event-Driven Service)
Sebuah microservice telemetri IoT menggunakan thread-safe subscriber registry berbasis `Arc<RwLock<HashMap<DeviceId, Vec<Arc<dyn Subscriber + Send + Sync>>>>>`.
* **Masalah:** Di bawah beban konkurensi tinggi, sistem mengalami *deadlock* deterministik yang melumpuhkan microservice tanpa ada log panic (*thread hanging*). Melalui investigasi memori (*core dump analysis*), ditemukan bahwa subscriber tertentu, saat menerima event, mencoba memanggil metode deregister ke registry yang sama melalui interface yang berbeda, memicu re-entrant locking pada `RwLock`. Di sisi lain, sebuah thread background mencoba melakukan iterasi `read()` yang terblokir secara permanen oleh antrean `write()` yang macet.
* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa implementasi default `std::sync::RwLock` pada platform Linux (pthread) rentan terhadap *writer starvation* atau *re-entrant deadlock* ketika thread yang sama memegang lock `read` lalu memicu flow yang membutuhkan `write`, atau memegang nested read di tengah antrean write pending?
  2. Buat skema pencegahan runtime deadlock menggunakan smart pointer dan pemisahan arsitektural. Mengapa memisahkan mutasi status menggunakan sistem antrean pesan (*MPSC/Broadcast channel*) lebih aman dibandingkan mengizinkan manipulasi registry secara direct lewat pointer bersama?
  3. Jika interior mutability tetap diwajibkan, bagaimana memanfaatkan tipe seperti `parking_lot::RwLock` atau memetakan ulang kepemilikan data menggunakan snapshot atomic (`Arc::clone` dari immutable map seperti `im::HashMap`) untuk menjamin keselamatan re-entrancy?

### Skenario C: Arsitektur & Trade-off: Parsing Zero-Copy vs Async Boundaries
Sebuah tim sedang membangun gateway HTTP/2 & gRPC edge proxy berperforma tinggi menggunakan `Tokio`.
* **Masalah:** Arsitek utama menginginkan arsitektur zero-copy murni: seluruh parser HTTP/2 frame mengembalikan referensi `&'a [u8]` yang langsung meminjam dari *network buffer ring*. Namun, ketika data frame tersebut harus dilemparkan ke background processing worker pool menggunakan `tokio::spawn`, compiler melempar rentetan error:
  `error[E0759]: `buffer` has lifetime `'a` but it needs to satisfy a `'static` lifetime requirement`.
  Untuk memintas error ini, tim junior mengubah seluruh field referensi menjadi `Vec<u8>` dan memanggil `.to_vec()` di mana-mana, yang menyebabkan degradasi throughput sebesar 45% dan memicu lonjakan fragmentasi heap alokator jemalloc.
* **Pertanyaan Diagnostik & Solusi:**
  1. Analisislah batasan fundamental sistem *borrow checker* Rust yang mewajibkan boundary `tokio::spawn` memiliki trait bound `'static`. Mengapa referensi ber-lifetime non-`'static` tidak dapat secara aman melintasi batasan thread pooling asynchronous standar?
  2. Jelaskan bagaimana smart pointer `bytes::Bytes` memecahkan masalah ini dengan konsep *shared slice ownership*. Bagaimana representasi internal `Bytes` memungkinkan slicing zero-copy sekaligus tetap memenuhi trait bound `'static` dan `Send`?
  3. Bandingkan trade-off performa, kompleksitas kode, dan fragmentasi memori antara:
     * Pendekatan A: `Bytes` (Reference-counted buffer slices).
     * Pendekatan B: Custom Arena Allocator ber-lifetime scoped (menggunakan thread-scoped libraries seperti `scoped-tls` atau crossbeam scoped threads).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent LRU Cache dengan Custom Eviction Hook dan Zero-Leak Protection

#### Problem Statement
Anda ditugaskan merancang modul inti *Thread-Safe Concurrent In-Memory Cache* (LRU - Least Recently Used) untuk sistem proxy basis data berlatensi ultra-rendah (<50 mikrodetik per operasi). Cache harus mengizinkan pembacaan bersama secara masif (*concurrent read-heavy*), mutasi frekuensi akses data (*recency updates*), dan pelepasan sumber daya deterministik tanpa memicu kebocoran memori siklis ataupun *stop-the-world lock contention*.

#### Functional & Technical Requirements
1. **Struktur Data Core:**
   * Implementasikan struktur data gabungan: *Hash Map* terindeks untuk pencarian $O(1)$ dan *Doubly Linked List* untuk pelacakan urutan LRU $O(1)$.
   * Jangan gunakan pointer kotor (*raw pointers*) tanpa enkapsulasi aman. Anda diwajibkan menggunakan abstraksi pointer cerdas yang tepat (`Arc`, `Weak`, `Mutex`/`RwLock`, atau implementasi atomik `UnsafeCell` dengan audit invariants yang ketat).
2. **Konektivitas dan Manajemen Siklis:**
   * Node dalam *doubly-linked list* memiliki pointer ke elemen `prev` dan `next`. Anda wajib membuktikan bahwa desain pointer Anda tidak menimbulkan *reference count cycle* yang memicu *memory leak*.
   * Gunakan kombinasi `Option<Arc<...>>` dan `Option<Weak<...>>` secara tepat untuk menjaga siklus hidup node.
3. **Smart Dereferencing & Pinning:**
   * Nilai cache yang dikembalikan ke pemanggil fungsi tidak boleh berbentuk *cloned value* dari payload jika payload berukuran besar. Nilai harus dibungkus dalam *custom smart pointer RAII guard* (misal: `CachedRef<V>`) yang mengimplementasikan `Deref<Target = V>`.
   * Selama `CachedRef<V>` aktif dipegang oleh pemanggil di thread mana pun, node terkait di dalam cache **tidak boleh di-dealokasikan dari memori heap** meskipun terjadi eviksi LRU serentak oleh worker thread lain.
4. **Thread Safety & Concurrent Mutability:**
   * Cache harus mengimplementasikan trait `Send` dan `Sync`.
   * Operasi `get(&self, key: &K) -> Option<CachedRef<V>>` harus dapat diakses secara bersamaan oleh banyak thread pembaca, namun mutasi internal penandaan posisi LRU (node dipindah ke *head*) harus ditangani dengan sinkronisasi minimal yang terisolasi (*fine-grained locking* atau lock-free interior mutability).

#### Constraints
* **No `unsafe` code** diperbolehkan untuk manipulasi relasi graf/linked-list, **KECUALI** jika dibungkus rapi dalam modul interior mutability terisolasi dengan dokumentasi `// SAFETY:` komprehensif yang membuktikan ketiadaan *undefined behavior* (data races, dangling pointers, invalid alignment).
* Tidak boleh terjadi *panic* di runtime akibat penolakan peminjaman dinamis (misal: hindari `RefCell::borrow_mut()` yang dapat dipanggil saat borrow aktif masih ada pada alur concurrent).
* Wajib menerapkan `Drop` implementation yang deterministik untuk mendekomposisi *doubly linked list* secara linear (*iterative drop*) guna mencegah stack overflow saat membersihkan jutaan node yang saling terhubung.

#### Expected Output & Verification
Sediakan implementasi minimal terverifikasi beserta *unit tests* dan *stress-test*:
```rust
// Interface minimum yang diharapkan:
pub struct LruCache<K, V> { /* ... */ }

impl<K: Hash + Eq + Clone, V> LruCache<K, V> {
    pub fn new(capacity: usize) -> Self { /* ... */ }
    pub fn get(&self, key: &K) -> Option<CachedRef<V>> { /* ... */ }
    pub fn put(&self, key: K, value: V) { /* ... */ }
    pub fn len(&self) -> usize { /* ... */ }
}
```
* **Test Case 1 (Cycle-Free Validation):** Masukkan 100.000 data melampaui batas kapasitas, validasi bahwa memori tidak membengkak dan seluruh nilai yang ter-eviksi benar-benar menjalankan operasi `Drop`.
* **Test Case 2 (Concurrent Read & Eviction Safety):** Thread A memegang `CachedRef<V>` dari item terlama (kandidat eviksi pertama), Thread B memanggil `put()` dengan entri baru yang memicu eviksi item tersebut. Buktikan bahwa Thread A tetap dapat membaca data secara valid tanpa *crash* atau *data race*, dan payload baru di-dealokasi secara aman saat `CachedRef<V>` milik Thread A keluar dari scope.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengaudit penguasaan materi teknis Lifetimes Lanjut & Smart Pointers Anda.

### Saya harus memahami:
- [ ] Aturan formal *Variance*: Mengapa `&'a T` covariant terhadap `'a` dan `T`, namun `&'a mut T` covariant terhadap `'a` tetapi invariant terhadap `T`.
- [ ] Hubungan antara *Higher-Rank Trait Bounds* (HRTB / `for<'a>`) dan siklus hidup peminjaman pada parameter closure / function pointers.
- [ ] Anatomi internal `UnsafeCell<T>` sebagai fondasi seluruh tipe interior mutability dan batas-batas legalitas optimasi kompilator LLVM (*alias analysis* & `noalias` flag).
- [ ] Perbedaan esensial *Drop Flags* di stack vs heap serta pengaruh atribut `#[may_dangle]` pada custom smart pointer drop checker.
- [ ] Mekanisme koordinasi *atomic operations* (`Acquire`, `Release`, `SeqCst`) pada `Arc<T>` dalam menjamin sinkronisasi visibilitas data lintas core prosesor saat pelepasan reference counter.
- [ ] Mengapa `Pin` bukanlah tipe pointer mandiri, melainkan contract wrapper yang menonaktifkan perpindahan alamat memori untuk tipe yang `!Unpin`.

### Saya tidak perlu menghafal:
- [ ] Representasi biner eksak dari bitwise drop-flag pada frame kompilasi spesifik LLVM.
- [ ] Formula matematis assembly di balik algoritma hashing spesifik default Rust (`SipHash 1-3`).
- [ ] Detail implementasi *platform-specific syscall* (futex di Linux vs WaitOnAddress di Windows) pada internal primitive sync parking_lot/standard library.

### Saya harus bisa melakukan:
- [ ] Melakukan isolasi dan eliminasi kebocoran memori siklis (*memory leak*) pada struktur data berbasis graf menggunakan kombinasi `Arc<T>` dan `Weak<T>`.
- [ ] Mengimplementasikan *custom smart pointer* yang aman dan zero-cost dengan memanfaatkan trait `Deref`, `DerefMut`, dan `Drop`.
- [ ] Memecahkan compiler error kompleks seputar lifetime seperti `borrowed value does not live long enough`, `lifetime may not live long enough`, atau ketidakcocokan trait bound `'static` pada multithreading.
- [ ] Merancang pipeline pemrosesan data bebas alokasi memanfaatkan `Cow<'a, B>` untuk beralih secara dinamis antara data pinjaman (*borrowed*) dan data pemilik (*owned*).
- [ ] Melakukan analisis trade-off performa secara terukur antara alokasi stack, alokasi heap via `Box`, shared pointers ber-lock (`Arc<Mutex<T>>`), dan pemisahan arsitektur zero-copy asynchronous.