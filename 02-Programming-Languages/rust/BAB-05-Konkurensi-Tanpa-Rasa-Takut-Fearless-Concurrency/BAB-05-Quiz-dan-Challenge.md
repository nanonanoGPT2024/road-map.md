# BAB 05: Quiz, Challenge, & Knowledge Check
**Konkurensi Tanpa Rasa Takut (Fearless Concurrency)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Model OS Threads vs. Asynchronous Tasks
Jelaskan perbedaan mendasar antara model konkurensi berbasis *native OS threads* (`std::thread`) dan model konkurensi *cooperative asynchronous tasks* (seperti `tokio` / `async-std`) di Rust. Fokuskan jawaban Anda pada:
1. Ukuran *call stack* default dan overhead memori per unit eksekusi.
2. Mekanisme scheduling (*preemptive* vs *cooperative*) beserta konsekuensinya terhadap komputasi CPU-bound versus operasi I/O-bound.

### Soal 1.2: Anatomi Marker Traits `Send` dan `Sync`
Secara formal, `T: Send` berarti kepemilikan nilai `T` dapat ditransfer lintas thread, sedangkan `T: Sync` berarti referensi `&T` aman diakses secara simultan dari beberapa thread.
1. Buktikan secara matematis/logika tipe mengapa aturan `T: Sync <=> &T: Send` berlaku di Rust.
2. Mengapa tipe raw pointer `*const T` dan `*mut T` secara default diimplementasikan sebagai `!Send` dan `!Sync` oleh compiler?
3. Jelaskan mengapa `Rc<T>` tidak memenuhi trait `Send` maupun `Sync`, sedangkan `Arc<T>` memenuhinya (dengan batasan tertentu pada `T`).

### Soal 1.3: Sinergi dan Mekanisme `Arc<Mutex<T>>`
Mengapa pemula sering mendapati compiler menolak kompilasi ketika hanya menggunakan `Mutex<T>` tanpa `Arc<T>` di dalam closure `thread::spawn`?
1. Analisis interaksi *ownership transfer* yang terjadi saat instance dipindahkan ke dalam beberapa thread.
2. Mengapa `RefCell<T>` tidak dapat dipadukan dengan `Arc<T>` untuk mencapai mutasi data lintas thread secara aman? Jelaskan batasan internal borrow flag pada `RefCell<T>`.

### Soal 1.4: Semantik Closure Captures dan Lifetime `'static` pada `thread::spawn`
Signature standar dari `std::thread::spawn` menuntut tipe closure:
```rust
F: FnOnce() -> T + Send + 'static, T: Send + 'static
```
1. Mengapa compiler Rust mewajibkan lifetime constraint `'static` pada data yang ditransfer ke thread baru?
2. Bagaimana keyword `move` memengaruhi transfer kepemilikan variabel dari scope lokal fungsi luar ke dalam closure thread? Apa yang terjadi jika keyword `move` dihilangkan saat closure mengakses referensi lokal?

### Soal 1.5: Batasan Jaminan "Fearless Concurrency" terhadap Deadlock
Slogan "Fearless Concurrency" sering disalahartikan bahwa Rust mencegah seluruh bug konkurensi di compile-time.
1. Mengapa compiler Rust secara inheren **tidak dapat** mendeteksi atau mencegah *deadlock* (misalnya: Thread A mengunci `Mutex 1` lalu meminta `Mutex 2`, sementara Thread B mengunci `Mutex 2` lalu meminta `Mutex 1`)?
2. Kategori cacat konkurensi apa saja yang **dijamin 100% bebas** oleh Rust pada level kompilasi, dan cacat apa saja yang tetap menjadi tanggung jawab desainer arsitektur?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik dan Recovery Mutex Poisoning
Ketika sebuah thread mengalami `panic!` saat sedang memegang kepemilikan `MutexGuard<T>`, mutex tersebut akan berada dalam kondisi *poisoned*.
1. Jelaskan mekanisme runtime Rust yang menandai status *poisoned* tersebut pada metadata internal `Mutex`.
2. Mengapa method `lock()` mengembalikan `Result<MutexGuard<T>, PoisonError<MutexGuard<T>>>` alih-alih melempar panic langsung?
3. Berikan contoh kasus produksi di mana pemulihan data (`into_inner()` atau `clear_poison()`) dari sebuah poisoned mutex aman dilakukan, dan kapan tindakan tersebut justru berisiko merusak *data invariant* aplikasi.

### Soal 2.2: Karakteristik Internal Channel: Bounded vs Unbounded
Dalam modul `std::sync::mpsc`:
1. Analisis perbedaan arsitektur internal antara `channel()` (*asynchronous / unbounded*) dan `sync_channel(bound)` (*synchronous / bounded*).
2. Di lingkungan produksi dengan beban traffic spikes ekstrem, mengapa penggunaan *unbounded channel* dikategorikan sebagai anti-pattern yang dapat memicu *Silent Out-Of-Memory (OOM)*?
3. Jelaskan fenomena *thread unparking / context switching* yang terjadi ketika worker mencoba mengirim data ke bounded channel yang telah penuh (`bound == 0` atau *rendezvous channel*).

### Soal 2.3: Memory Ordering pada Atomics: Bahaya `Ordering::Relaxed`
Diberikan cuplikan kode synchronizer sederhana berikut:
```rust
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

static DATA: AtomicU64 = AtomicU64::new(0);
static READY: AtomicBool = AtomicBool::new(false);

// Thread Producer
fn producer() {
    DATA.store(42, Ordering::Relaxed);
    READY.store(true, Ordering::Relaxed);
}

// Thread Consumer
fn consumer() {
    while !READY.load(Ordering::Relaxed) {}
    println!("Data: {}", DATA.load(Ordering::Relaxed));
}
```
1. Jelaskan mengapa program di atas dapat menghasilkan output `Data: 0` atau memicu *undefined logical behavior* pada arsitektur CPU non-x86 (seperti ARM64 atau RISC-V) akibat *CPU instruction reordering* dan *memory pipeline effects*.
2. Modifikasi memory ordering pada masing-masing operasi load dan store (`Acquire` / `Release` semantics) agar sinkronisasi data antar-thread terjamin secara deterministik tanpa membayar penalti performa dari `Ordering::SeqCst`.

### Soal 2.4: Mekanisme Zero-Cost Abstraction pada `std::thread::scope`
Fitur Scoped Threads (`std::thread::scope`) distabilkan pada Rust 1.63.
1. Bagaimana desainer standard library merancang *lifetime invariance* pada `Scope<'scope, 'env>` sehingga borrow checker mengizinkan thread anak meminjam referensi lokal stack frame tanpa alokasi `Arc` dan tanpa constraint `'static`?
2. Bagaimana implementasi internal `scope` memastikan bahwa seluruh thread anak pasti selesai dieksekusi (*guaranteed join*) sebelum fungsi `scope` kembali, bahkan jika salah satu thread mengalami panic?

### Soal 2.5: Cache Line Bouncing dan False Sharing
Perhatikan struct metrik berikut yang diakses secara paralel oleh 8 core CPU:
```rust
#[repr(C)]
struct WorkerStats {
    jobs_processed: AtomicU64, // Diakses konstan oleh Worker 1..8
    errors_count: AtomicU64,   // Diakses konstan oleh Worker 1..8
}
```
1. Jelaskan konsep arsitektur hardware terkait *Cache Line* (umumnya 64 byte pada arsitektur modern) dan fenomena *False Sharing* / *Cache Invalidation protocol* (misal: MESI protocol) yang menurunkan performa kode di atas.
2. Bagaimana teknik mitigasi masalah ini di Rust menggunakan atribut `#[repr(align(...))]`? Tuliskan deklarasi struct yang dioptimalkan untuk performa CPU multi-core.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Lock Contention pada Engine Transaksi Skala Besar
Sebuah platform High-Frequency Trading mencatat latensi P99 yang melonjak drastis dari 200 mikrodetik menjadi 85 milidetik saat pasar mengalami lonjakan volatilitas. Profiling performa menunjukkan bahwa 92% waktu CPU pada worker threads habis dalam status kernel wait (*futex syscalls*). 

Investigasi kode menemukan struktur data state portofolio global berikut:
```rust
pub struct EngineState {
    pub order_book: Mutex<HashMap<Symbol, Book>>,
    pub account_balances: Mutex<HashMap<AccountId, Balance>>,
    pub global_metrics: Mutex<Metrics>,
}
```
Setiap kali ada order baru masuk (bisa mencapai 200.000 order/detik), worker thread harus mengunci ketiga mutex tersebut secara berurutan.

**Pertanyaan Diagnostik & Arsitektural:**
1. Mengapa granularitas penguncian (*locking granularity*) di atas menghancurkan skalabilitas paralelisme thread, dan bagaimana model lock-ordering dapat memicu resiko *deadlock* laten di bawah beban tinggi?
2. Rancang ulang arsitektur state management tersebut. Jelaskan trade-off antara penggunaan:
   - Partisi data (*Sharded / Striped Mutex*).
   - Penggantian `Mutex` dengan `parking_lot::RwLock` atau *Atomic Cell*.
   - Transisi ke model *Share-nothing / Message Passing (Actor Pattern)* menggunakan kanal mpsc/crossbeam.

---

### Skenario B: Race Condition Non-Atomic Check-Then-Act pada Sistem Reservasi
Sebuah sistem tiket flash sale mengalami insiden over-selling (kursi yang sama terjual ke dua pengguna berbeda). Tim pengembang berargumen bahwa mereka telah menggunakan tipe data Atomic bawaan Rust dan tidak ada `unsafe` block:

```rust
use std::sync::atomic::{AtomicU32, Ordering};

pub struct InventoryManager {
    available_seats: AtomicU32,
}

impl InventoryManager {
    pub fn reserve_ticket(&self) -> Result<(), &'static str> {
        let current = self.available_seats.load(Ordering::Acquire);
        if current > 0 {
            // Jendela kerentanan (Race Window)
            std::thread::yield_now(); // Simulasi jeda context-switch mikro
            self.available_seats.fetch_sub(1, Ordering::Release);
            Ok(())
        } else {
            Err("Sold out")
        }
    }
}
```

**Pertanyaan Diagnostik & Arsitektural:**
1. Mengapa penggunaan operasi atomik terpisah (`load` lalu `fetch_sub`) menghasilkan cacat logika *Time-of-Check to Time-of-Use (TOCTOU)* meskipun masing-masing operasi bersifat aman secara thread (*thread-safe*)?
2. Perbaiki implementasi method `reserve_ticket` di atas menggunakan idiom lock-free *Compare-And-Swap (CAS)* loop dengan method `compare_exchange` atau `compare_exchange_weak`. Jelaskan perbedaan kedua method tersebut dan mengapa salah satunya lebih optimal pada arsitektur CPU tertentu.

---

### Skenario C: Backpressure Collapse pada Pipeline Ingesti Log
Sebuah service *Log Telemetry Ingestion* membaca jutaan metrik dari jaringan UDP dan meneruskannya ke worker threads untuk diproses dan ditulis ke disk. Arsitektur awal menggunakan model:

```
[UDP Listener Thread] 
         │
         ▼ (std::sync::mpsc::channel)
   [Worker Thread] ───► [Batch Disk Writer]
```

Ketika IO disk melambat selama backup harian, service mengalami crash seketika karena dibunuh oleh kernel Linux (*OOM-Killer*), dengan log sistem kehilangan data sebesar puluhan gigabyte.

**Pertanyaan Diagnostik & Arsitektural:**
1. Bedah rantai kegagalan (*failure chain*) yang berujung pada OOM-Killer. Mengapa memory limit process terlampaui padahal listener hanya membaca payload berukuran kecil?
2. Bagaimana Anda mendesain ulang arsitektur pipeline tersebut agar memiliki ketahanan terhadap degradasi downstream menggunakan mekanisme *Backpressure* eksplisit?
3. Bandingkan strategi penanganan ketika antrean penuh: *Blocking producer*, *Drop latest*, *Drop oldest*, atau *Shed load with HTTP 429/Circuit Breaking*. Bagaimana Rust type-system membantu memodelkan state antrean ini?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Lock-Free In-Memory Metric Aggregator

#### Problem Statement
Anda diminta untuk membangun komponen inti telemetry agent di edge proxy: **`ThreadMetricAggregator`**. Modul ini harus mampu menerima data *metric counters* berkecepatan tinggi dari puluhan worker thread secara paralel tanpa mengalami degradasi performa akibat lock contention, kemudian secara periodik melakukan flush data teragregasi ke output writer secara sinkron dan aman.

#### Technical Requirements
1. **Zero Global Mutex on Ingest:** Ingesti metrik (pemanggilan `.increment(metric_id, value)`) tidak boleh menggunakan `std::sync::Mutex` atau `RwLock` global yang melingkupi seluruh registry metrik. Anda wajib menggunakan teknik *Thread-Local Storage (TLS)* digabung dengan *atomic striping*, atau array atomic berukuran tetap.
2. **Deterministic Periodic Flush:** Implementasikan thread monitor khusus yang terbangun setiap interval waktu tertentu ($T$), mengumpulkan (*harvest*) total agregasi dari seluruh worker, dan mengosongkan/mereset counter worker secara atomik tanpa menghentikan worker yang sedang aktif menulis metrik.
3. **Graceful Shutdown:** Implementasikan trait `Drop` atau method eksplisit `shutdown()` yang menjamin seluruh data yang tersisa di-flush ke buffer output sebelum program berhenti. Tidak boleh ada data yang hilang (*zero dropped metrics*) saat proses terminasi normal.
4. **Panic Safety:** Jika salah satu worker thread mengalami panic, thread worker lain dan thread aggregator tidak boleh mengalami panic lanjutan atau terjebak dalam deadlock.

#### Constraints
- Gunakan hanya `std` (Standard Library) Rust. Tidak diperbolehkan menggunakan external crates (`crossbeam`, `parking_lot`, `tokio`, dsb).
- Gunakan memory ordering seminimal mungkin yang masih menjamin kebenaran program (hindari pemborosan menggunakan `Ordering::SeqCst` di semua tempat; justifikasi penggunaan `Relaxed`, `Release`, atau `Acquire`).
- Zero memory-leaks.

#### Expected Deliverables
1. Definisi struct `Aggregator` dan implementasi token worker-nya.
2. Kode lengkap pipeline yang menunjukkan sinkronisasi antara minimal 4 thread produsen dan 1 thread flusher.
3. Unit test yang memvalidasi integritas data: Jumlah total metrik yang ditulis oleh 4 thread (misal: masing-masing 100.000 iterasi) harus tepat sama dengan hasil kalkulasi flusher saat program selesai di-shutdown.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan teknis Anda sebelum melangkah ke topik sistem pemrograman lanjutan.

### Saya harus memahami:
- [ ] Perbedaan model memori hardware CPU multi-core (Cache coherency, Store buffers, Memory reordering) dan bagaimana Rust memetakannya via `std::sync::atomic`.
- [ ] Perbedaan formal antara *data race* (undefined behavior yang dicegah Rust) dan *race condition* (logical bug yang tetap bisa terjadi).
- [ ] Implementasi internal `Arc<T>` (mengapa menggunakan dua atomic counter terpisah: `strong_count` dan `weak_count`).
- [ ] Cara kerja *Futex* (Fast Userspace Mutex) di level OS saat `Mutex<T>` mengalami kontensi tinggi.
- [ ] Mengapa Rust melarang penggunaan `std::mem::forget` pada `MutexGuard` tanpa konsekuensi keamanan memori (Safe Leak Amplification).
- [ ] Konsep `Sync` untuk tipe data yang membungkus tipe interior mutability (`Atomic*`, `Mutex`, `RwLock` vs `RefCell`, `Cell`).

### Saya tidak perlu menghafal:
- [ ] Nilai bitmask heksadesimal implementasi futex pada platform-specific sys-call (`SYS_futex` di kernel Linux).
- [ ] Seluruh tabel kombinasi Memory Ordering x86-TSO (cukup pahami model abstrak Acquire-Release semantics).
- [ ] Kode implementasi assembly intrinsik CPU untuk instruksi CAS (`lock cmpxchg` pada x86 atau `ldrex`/`strex` pada ARM).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memperbaiki masalah compile-time error yang disebabkan oleh pelanggaran trait bounds `Send` / `Sync`.
- [ ] Memilih dengan tepat kapan harus menggunakan *Message Passing* (`mpsc`) vs *Shared State* (`Arc<Mutex<T>>` / `Atomic*`) berdasarkan karakteristik beban sistem.
- [ ] Menggunakan `std::thread::scope` untuk memproses referensi array/slice secara paralel tanpa alokasi heap `Arc`.
- [ ] Melakukan dekonstruksi dan pemulihan data dari `PoisonError` pada `MutexGuard`.
- [ ] Menggunakan profiling tool (seperti `perf`, `flamegraph`, atau Valgrind/Helgrind) untuk mendeteksi *lock contention* dan *false sharing* pada biner Rust.