# BAB 06: Quiz, Challenge, & Knowledge Check
**Asynchronous Programming & Tokio Runtime**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pull-based (Polling) vs Push-based Asynchronous Model
Jelaskan perbedaan mendasar antara model *pull-based* (Rust `Future`) dan model *push-based* (seperti JavaScript/Node.js `Promise` atau Go runtime `goroutine`). Mengapa Rust mengadopsi model *pull-based*, dan bagaimana model ini mewujudkan prinsip *zero-cost abstraction* serta mengeliminasi alokasi heap implisit dalam rantai eksekusi *future*?

### Soal 1.2: Anatomi `Future`, `Context`, dan `Waker`
Ditinjau dari tanda tangan metode:
```rust
fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
```
Uraikan alur kerja interaksi antara *executor*, *reactor*, dan *waker*. Apa yang terjadi secara mekanistik pada CPU dan thread pool jika sebuah implementasi `poll` mengembalikan `Poll::Pending` tetapi gagal mendaftarkan atau mengkloning `cx.waker()` ke sumber event (I/O event source)?

### Soal 1.3: Mekanika `Pin` dan Self-Referential Structs
Ketika compiler mentransformasikan blok `async fn` menjadi *state machine* anonim, mengapa struktur data internal tersebut rentan menjadi *self-referential*? Jelaskan mengapa tipe penunjuk `Pin<&mut T>` mutlak dibutuhkan untuk menjamin keamanan memori (*memory safety*) dan mencegah *undefined behavior* saat data tersebut dipindahkan (*moved*) di memori.

### Soal 1.4: Batasan `'static` dan `Send` pada `tokio::spawn`
Mengapa fungsi `tokio::spawn` memberlakukan *trait bound* `T: Future + Send + 'static` dan `T::Output: Send + 'static` pada *multi-threaded runtime*? Jelaskan skenario di mana Anda dapat mengeksekusi *future* yang **tidak** mengimplementasikan `Send` atau tidak memiliki masa hidup `'static` tanpa melanggar batasan arsitektural Tokio.

### Soal 1.5: Perbedaan Operasional `std::thread` vs `tokio::task`
Bandingkan `std::thread` (OS thread) dengan `tokio::task` (green thread/cooperative task) dalam aspek:
1. Ukuran alokasi memori awal (*stack allocation overhead*).
2. Biaya *context switching* (kernel transition vs user-space state preservation).
3. Skalabilitas konkurensi (ribuan thread vs jutaan tasks).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Thread Pool Starvation dan Penanganan Blocking Code
Perhatikan potongan kode berikut:
```rust
async fn process_user_data(id: u64) -> Result<Data, Error> {
    let raw = fetch_from_db(id).await?;
    // Komputasi intensif enkripsi atau I/O sinkronus legacy:
    std::thread::sleep(std::time::Duration::from_millis(100)); 
    let processed = heavy_cpu_decrypt(&raw);
    Ok(processed)
}
```
Jika fungsi ini dipanggil di bawah beban 5.000 concurrent requests pada runtime Tokio multi-thread default (misal: 8 worker threads), jelaskan fenomena yang terjadi pada runtime tersebut. Mengapa *cooperative multitasking* gagal berfungsi di sini, dan bagaimana cara memperbaikinya secara idiomatik menggunakan `tokio::task::spawn_blocking` atau kanal inter-thread?

### Soal 2.2: Cancellation Safety pada Makro `tokio::select!`
Jelaskan konsep *cancellation safety* dalam ekosistem asinkronus Rust. Analisis potongan kode berikut dan tunjukkan di mana letak potensi *data loss* atau *bug* korupsi buffer ketika cabang timeout terpicu:
```rust
tokio::select! {
    res = socket.read_exact(&mut buffer) => {
        process_payload(&buffer[..res?]);
    }
    _ = tokio::time::sleep(Duration::from_millis(50)) => {
        eprintln!("Socket read timed out!");
    }
}
```
Bagaimana strategi mitigasi untuk membuat operasi I/O tersebut aman terhadap pembatalan (*cancel-safe*)?

### Soal 2.3: Work-Stealing Algorithm Internal Tokio
Bagaimana Tokio runtime mengorganisasi antrean tugas (*task queues*) untuk meminimalkan *thread contention* pada arsitektur *multi-core*? Jelaskan hierarki antara *global queue*, *local run queue* (berkapasitas tetap), dan *LIFO slot*. Bagaimana mekanisme *work-stealing* dieksekusi ketika sebuah *worker thread* kehabisan tugas di antrean lokalnya?

### Soal 2.4: Pemilihan Sinkronisasi: `std::sync::Mutex` vs `tokio::sync::Mutex`
Dua engineer berdebat mengenai proteksi status bersama (*shared state*). Engineer A bersikeras selalu menggunakan `tokio::sync::Mutex`. Engineer B berpendapat bahwa `std::sync::Mutex` hampir selalu lebih unggul kecuali dalam satu kondisi spesifik. 
Evaluasi argumen tersebut berdasarkan biaya alokasi memori, latensi OS syscall, dan skenario mempertahankan lock menyeberangi titik suspensi (`.await point`). Kapan penggunaan `tokio::sync::Mutex` justru memicu degradasi performa (*antipattern*)?

### Soal 2.5: Siklus Referensi Asinkronus dan Task Leakage
Dalam runtime asinkronus yang berjalan terus-menerus (*long-running daemon*), apa yang terjadi pada *task* yang di-spawn melalui `tokio::spawn` jika *future*-nya menunggu pesan dari sebuah `tokio::sync::mpsc::channel`, namun semua instance `Sender` terikat dalam siklus sirkular di dalam heap (misal melalui `Arc<T>`)? Bagaimana cara melakukan profiling atau mendeteksi *task leak* semacam ini di lingkungan produksi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Tail Latency Explosion pada Ingestion API
**Konteks Insiden:**
Sebuah microservice HTTP ingest berbasis `axum` dan `tokio` (dikonfigurasi dengan 16 worker threads pada instans AWS c6i.4xlarge) mencatat metrik latensi p50 stabil pada angka 4ms. Namun, metrik p99 dan p99.9 meledak secara intermiten hingga mencapai 8.000ms setiap kali beban mencapai lebih dari 20.000 requests per second. Metrik CPU utilization server hanya menunjukkan 28%, memori aman, dan tidak ditemukan *packet drop* pada layer network OS.

**Investigasi:**
Setelah dilakukan *stack tracing* menggunakan `tokio-console`, tim menemukan sejumlah besar worker thread berstatus *blocked* pada pemanggilan pustaka third-party client analitik yang melakukan sinkronisasi logging ke disk lokal menggunakan `std::fs::OpenOptions`.

**Pertanyaan Diagnostik:**
1. Mengapa utilisasi CPU rendah (28%) tetapi p99 tail latency meledak hingga 8 detik? Uraikan interaksi antara syscall OS blocking dengan *event loop* worker thread Tokio.
2. Rancang arsitektur refaktorisasi untuk sistem logging disk tersebut menggunakan kombinasi antrean *asynchronous bounded channel* dan dedicated background processing thread agar worker thread Tokio terbebas dari blocking I/O. Sertakan diagram alur aliran data atau pseudo-code Rust yang menerapkan prinsip *backpressure*.

---

### Skenario B: Distributed Event Ordering & Out-of-Sequence Cancellation
**Konteks Masalah:**
Sebuah *consumer service* membaca data transaksi keuangan dari Apache Kafka dan mengeksekusi pipeline: 
1. Validasi saldo via REST API external.
2. Update saldo lokal di database PostgreSQL.
3. Emit konfirmasi transaksi ke queue berikutnya.

Kode ditulis menggunakan `tokio::select!` dengan pola *heartbeat cancellation*:
```rust
loop {
    tokio::select! {
        msg = consumer.recv() => {
            if let Some(event) = msg {
                tokio::spawn(async move {
                    process_transaction(event).await;
                });
            }
        }
        _ = shutdown_signal.recv() => {
            tracing::info!("Graceful shutdown triggered.");
            break;
        }
    }
}
```

**Anomali di Produksi:**
Saat service menerima sinyal shutdown (SIGTERM via Kubernetes pod rescheduling), puluhan transaksi dilaporkan berstatus inkonsisten: saldo external terpotong, tetapi PostgreSQL lokal tidak ter-update, atau transaksi ganda (*duplicate execution*) diproses saat pod baru hidup.

**Pertanyaan Diagnostik:**
1. Tunjukkan kelemahan fatal pada penggunaan `tokio::spawn` di dalam blok `select!` di atas terkait masa hidup task (*task lifecycle*) saat shutdown signal diterima.
2. Rancang solusi implementasi *graceful shutdown* yang benar menggunakan `tokio_util::sync::CancellationToken` dan `tokio::sync::mpsc::channel` atau `tokio::task::JoinSet` untuk memastikan semua in-flight transactions selesai secara deterministik sebelum proses utama berhenti (terminasi).

---

### Skenario C: High-Throughput Engine: Work-Stealing vs Thread-per-Core
**Konteks Arsitektur:**
Perusahaan Anda sedang membangun *low-latency trading engine gateway* yang harus menangani *inbound streaming market data* dari puluhan bursa via WebSocket dengan throughput target 1.000.000 pesan/detik dan variansi latensi jitter < 50 mikrodetik.

Dua arsitektur diusulkan:
- **Opsi 1:** Multi-threaded Tokio Runtime default (Work-stealing scheduler) dengan komunikasi via `tokio::sync::broadcast` dan mutex terproteksi.
- **Opsi 2:** Thread-per-Core Architecture menggunakan Tokio `current_thread` runtime yang di-pin ke masing-masing core CPU fisik via CPU affinity (`core_affinity` crate), berkomunikasi murni melalui lock-free SPSC channels (Single-Producer Single-Consumer) tanpa cross-thread shared memory locks.

**Pertanyaan Diagnostik:**
1. Mengapa Tokio multi-threaded work-stealing scheduler dapat menghasilkan *latency jitter* yang tidak dapat diterima pada skala mikrodetik untuk kasus ini? Analisis dari perspektif *cache coherency*, *cross-core memory bus traffic*, dan *lock contention*.
2. Evaluasi trade-off dari Opsi 2 (Thread-per-Core): Apa kompleksitas implementasi yang harus dibayar tim engineer (misal: penanganan *load balancing*, isolasi state, ketiadaan trait bound `Send`), dan mengapa pendekatan ini mampu memberikan latensi deterministik?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Async Priority Worker Pool dengan Bounded Concurrency, Rate Limiting, dan Resilient Graceful Shutdown

#### Problem Statement
Dalam ekosistem microservice berkinerja tinggi, Anda ditugaskan membangun komponen internal bernama `PriorityExecutionEngine`. Engine ini bertugas mengeksekusi jobs asinkronus pihak ketiga yang memiliki variasi tingkat prioritas (`High`, `Normal`, `Low`), membatasi konkurensi maksimum secara simultan, menerapkan *rate-limiting* terpusat, dan menjamin *zero data loss* saat sinyal shutdown diaktifkan.

#### Requirements
1. **Prioritas Tugas:** Engine harus menerima task dengan tingkat prioritas:
   ```rust
   #[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
   pub enum Priority {
       High = 2,
       Normal = 1,
       Low = 0,
   }
   ```
   Tugas dengan prioritas `High` harus selalu dieksekusi lebih dulu daripada `Normal` atau `Low` jika terdapat antrean tugas tertunda.
2. **Concurrency Limiter:** Tidak boleh lebih dari $N$ tugas berjalan bersamaan (dikonfigurasi menggunakan `tokio::sync::Semaphore`).
3. **Rate Limiting:** Engine tidak boleh mengeksekusi lebih dari $R$ operasi per detik secara agregat (gunakan algoritma token bucket atau sliding window via Tokio primitives/sleep).
4. **Resilient Graceful Shutdown:**
   - Menyediakan metode `shutdown(timeout: Duration) -> Result<(), EngineError>`.
   - Ketika shutdown dipanggil, engine berhenti menerima tugas baru (mengembalikan error `EngineError::ShuttingDown`).
   - Engine wajib menyelesaikan semua tugas yang sedang berjalan (*in-flight*) dan tugas yang masih tersisa di antrean hingga batas `timeout` tercapai.
   - Jika timeout terlampaui, paksa abort tugas yang tersisa dan kembalikan metrik berapa tugas yang berhasil diselesaikan dan berapa yang dibatalkan.
5. **Observabilitas:** Melaporkan metrik menggunakan tipe data atomik (`AtomicUsize`): total diproses, total gagal, dan total terbatalkan.

#### Constraints
- Wajib menggunakan ekosistem `tokio` (1.x).
- **Dilarang** menggunakan `unsafe` code.
- **Dilarang** memblokir thread worker dengan I/O sinkronus atau fungsi pemblokir CPU.
- Seluruh tipe publik harus aman terhadap thread boundary (`Send + Sync + 'static`).
- Kode harus terhindar dari *memory leak* akibat penumpukan tugas tak terbatas (antrean harus *bounded*).

#### Expected Output (Test Scenario Execution)
Program pengujian (`main.rs` atau unit test) harus mensimulasikan injeksi 100 tugas campuran (`High`, `Normal`, `Low`) secara acak, memicu shutdown di tengah jalan (misal setelah 200ms), dan mencetak output verifikasi deterministik:
```text
[Engine] Initialized with 4 worker slots, rate-limit: 20 tasks/sec.
[Engine] Injected: 100 tasks (30 High, 40 Normal, 30 Low).
[Engine] Worker pool executing...
[Signal] SIGINT/Shutdown received. Halting task intake.
[Drain] Processing remaining 14 queued tasks within 2000ms grace period...
[Complete] Shutdown complete in 680ms.
[Report] Metrics Summary:
  - Processed: 45
  - High Priority Processed: 28/30
  - Normal Priority Processed: 15/40
  - Low Priority Processed: 2/30
  - Dropped/Aborted: 55
Zero dangling tasks detected. Memory clean.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan model eksekusi *pull-based* Rust vs *push-based* asynchronous engines lainnya.
- [ ] Siklus hidup polling: bagaimana `Context`, `Waker`, dan `Poll<T>` bekerja sama membangunkan worker thread.
- [ ] Alasan matematis dan arsitektural mengapa *self-referential structs* memerlukan `Pin<&mut T>`.
- [ ] Konsekuensi operasi pemblokir (*blocking call*) pada Tokio worker threads dan perbedaan fungsional antara `tokio::task::spawn_blocking` vs `tokio::task::spawn`.
- [ ] Mekanisme dan risiko *Cancellation Safety* pada pemanggilan makro `tokio::select!`.
- [ ] Arsitektur internal Tokio work-stealing scheduler: local queue, global queue, LIFO slot, dan inter-thread task stealing.
- [ ] Karakteristik dan trade-off antara `std::sync::Mutex` vs `tokio::sync::Mutex`.
- [ ] Cara mendesain arsitektur *graceful shutdown* end-to-end tanpa risiko data loss menggunakan `CancellationToken` dan `JoinSet`.

### Saya tidak perlu menghafal:
- [ ] Struktur byte-level memory layout dari vtable `RawWaker` (cukup pahami fungsi virtualnya).
- [ ] Konstanta internal bitwise scheduling flags pada implementasi source code internal Tokio.
- [ ] Seluruh variasi API method I/O pada `tokio::io::AsyncReadExt` dan `tokio::io::AsyncWriteExt`.
- [ ] Algoritma internal sistem operasi terkait epoll/kqueue/IOCP di level kernel C.

### Saya harus bisa melakukan:
- [ ] Mengonstruksi manual tipe data yang mengimplementasikan trait `Future` dengan penanganan state machine dan waker registration yang aman.
- [ ] Menulis unit test untuk asynchronous code menggunakan atribut `#[tokio::test]`.
- [ ] Melakukan isolasi beban komputasi CPU intensif atau library sinkronus agar tidak merusak ekosistem Tokio event loop.
- [ ] Mengidentifikasi dan memitigasi kebocoran memori (*task leaks*) dan kondisi balapan (*data races/race conditions*) dalam aplikasi terdistribusi.
- [ ] Memilih primitive sinkronisasi yang tepat (`mpsc`, `broadcast`, `watch`, `oneshot`, `Semaphore`, `Barrier`) berdasarkan use-case arsitektural.
- [ ] Menganalisis latensi sistem menggunakan alat diagnostik seperti `tokio-console` dan distributed tracing (`tracing` crate).