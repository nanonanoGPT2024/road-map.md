# Kurikulum Enterprise Rust: Konkurensi Tingkat Lanjut & Arsitektur Produksi
**Kategori:** 02-Programming-Languages  
**Bab 05:** Konkurensi Tanpa Rasa Takut (Fearless Concurrency)  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** arsitektur memori perangkat keras (*Hardware Memory Models*: x86-64 TSO vs. ARM/AArch64 Weak Ordering) dan implikasinya terhadap *atomic operations* di Rust.
- **Menguasai dan Menerapkan** model konsistensi memori Rust (`Ordering::Relaxed`, `Acquire`, `Release`, `AcqRel`, `SeqCst`) untuk merancang struktur data bebas-kunci (*lock-free*).
- **Mengevaluasi dan Mengimplementasikan** primitif sinkronisasi tingkat lanjut (`RwLock`, `Condvar`, `Barrier`, `crossbeam::channel`) untuk menghilangkan *contention bottleneck*.
- **Membangun Arsitektur Pipeline Konkurensi Produksi** dengan mitigasi *lock poisoning*, penjadwalan *work-stealing*, pembatasan kapasitas antrean (*backpressure*), dan penanganan terminasi anggun (*graceful shutdown*).
- **Mendeteksi dan Memitigasi** anomali performa mikro-arsitektur seperti *cache line bouncing*, *false sharing*, dan *deadlock* laten menggunakan instrumentasi dan Miri.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda harus memahami:
1. **Ownership, Borrowing, dan Lifetimes** Rust (Bab 02 & 03).
2. **Karakteristik Send & Sync Traits**:
   - Tipe $T$ adalah `Send` jika kepemilikannya dapat ditransfer lintas batas *thread*.
   - Tipe $T$ adalah `Sync` jika referensinya `&T` aman diakses secara konkuren lintas batas *thread* ($T: \text{Sync} \iff \&T: \text{Send}$).
3. **Dasar Konkurensi Rust** (Module 01): `std::thread::spawn`, `Arc<T>`, `Mutex<T>`, dan `std::sync::mpsc`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Model Memori Perangkat Keras vs. Rust Memory Model

Rust mengadopsi model memori formal C++11. Konkurensi pada tingkat perangkat keras tidak berjalan di atas model eksekusi sekuensial sederhana. Kompiler dan CPU melakukan *instruction reordering*, *speculative execution*, dan pemanfaatan *Store Buffer* serta *Invalidation Queue* untuk memaksimalkan throughput instruksi per siklus (*IPC*).

```
+-------------------------------------------------------------------+
|                        CPU Core 0                                 |
|  +--------------+    +------------------+    +-----------------+  |
|  | Out-of-Order | -> |   Store Buffer   | -> |  L1 Data Cache  |  |
|  | Execution    |    | (Write coalesc.) |    |  (MESI State)   |  |
|  +--------------+    +------------------+    +-----------------+  |
+-------------------------------------------------------|-----------+
                                                        | Interconnect Bus
+-------------------------------------------------------| (Cache Coherency)
|                        CPU Core 1                     |
|  +--------------+    +------------------+    +-----------------+  |
|  | Out-of-Order | <- | Invalidate Queue | <- |  L1 Data Cache  |  |
|  | Execution    |    +------------------+    +-----------------+  |
+-------------------------------------------------------------------+
```

- **x86-64 (Total Store Order / TSO):** Arsitektur perangkat keras ini memiliki konsistensi relatif ketat. Pembacaan (*load*) tidak dapat di-reorder melompati pembacaan lain, dan penulisan (*store*) tidak dapat di-reorder melompati penulisan lain. Namun, *Store-Load reordering* dapat terjadi jika instruksi menulis ke alamat $A$ dan membaca dari alamat $B$.
- **ARM / AArch64 (Weakly Ordered):** CPU diizinkan mereorder hampir semua operasi membaca dan menulis selama dependensi data lokal dipertahankan. Tanpa instruksi *memory barrier* eksplisit (`dmb`, `dsb`), *thread* lain dapat mengamati operasi mutasi memori dalam urutan yang berbeda total dari urutan kode sumber.

### 3.2 Semantik Memory Ordering pada Atomics

Rust menyediakan modul `std::sync::atomic::Ordering` untuk mengendalikan batas optimasi kompiler (*compiler fence*) dan instruksi barier CPU (*CPU memory fence*):

1. **`Ordering::Relaxed`**:
   - Menjamin sifat atomik (baca/tulis tidak terpotong / *no torn reads/writes*).
   - **Tidak memberikan jaminan sinkronisasi atau pengurutan** terhadap operasi memori lain di sekitarnya.
   - Cocok untuk: Metrik, pencacah statistik (misal: *request counter*).
2. **`Ordering::Release`**:
   - Digunakan pada operasi **Store/Write**.
   - Menjamin bahwa semua operasi memori (baik *atomic* maupun non-*atomic*) yang ditulis **sebelum** operasi *Release* dalam urutan program, tidak dapat dipindahkan melewati operasi ini.
   - Mempublikasikan perubahan ke *thread* lain yang melakukan *Acquire*.
3. **`Ordering::Acquire`**:
   - Digunakan pada operasi **Load/Read**.
   - Menjamin bahwa operasi baca/tulis memori yang dijadwalkan **setelah** operasi *Acquire* tidak dapat dipindahkan mendahului operasi ini.
   - Mensinkronisasi status dengan *thread* yang melakukan operasi *Release*.
4. **`Ordering::AcqRel` (Acquire-Release)**:
   - Digunakan pada operasi modifikasi gabungan (*Read-Modify-Write* / RMW), seperti `compare_exchange` atau `fetch_add`.
   - Menggabungkan semantik *Acquire* untuk fase baca dan *Release* untuk fase tulis.
5. **`Ordering::SeqCst` (Sequentially Consistent)**:
   - Tingkat konsistensi paling ketat. Menerapkan semantik *AcqRel* ditambah jaminan bahwa seluruh *core* dalam sistem menyepakati **satu urutan global tunggal** (*globally consistent total order*) atas semua operasi `SeqCst`.
   - Memiliki *overhead* performa tertinggi karena memaksa pengosongan *store buffer* penuh pada arsitektur perangkat keras tertentu.

### 3.3 Anatomi Primitif Sinkronisasi Tingkat Lanjut

- **`RwLock<T>` (Reader-Writer Lock):** Mengizinkan konkurensi banyak pembaca (*shared access* `&T`) secara paralel, atau tepat satu penulis (*exclusive access* `&mut T`). Di Linux, implementasi modern menggunakan *futex* (*fast userspace mutex*) untuk menghindari transisi *context switch* kernel jika tidak terjadi kontensi.
- **`Condvar` (Condition Variable):** Memungkinkan sebuah *thread* untuk diblokir (*sleep without burning CPU cycles*) hingga menerima sinyal notifikasi bahwa invarian data tertentu telah terpenuhi. Harus selalu dipasangkan dengan `MutexGuard` dalam loop evaluasi predikat.
- **Lock Poisoning:** Di Rust, jika sebuah *thread* mengalami *panic* saat memegang `MutexGuard` atau `RwLockWriteGuard`, *lock* tersebut dinyatakan "teracuni" (*poisoned*). Hal ini untuk mencegah *thread* lain membaca data yang berpotensi berada dalam status korup atau setengah ter-mutasi (*inconsistent state*).

---

## 4. Why & What

| Pendekatan Sinkronisasi | Kapan Digunakan | Kelebihan | Kelemahan & Risiko |
| :--- | :--- | :--- | :--- |
| **`Arc<Mutex<T>>`** | Akses mutasi eksklusif data kompleks multi-field. | Sederhana, aman dari data race, compiler-enforced. | *High contention overhead*, *priority inversion*, rawan *deadlock*. |
| **`Arc<RwLock<T>>`** | Workload dengan rasio baca >> tulis (e.g., Cache, Routing Table). | Read throughput sangat tinggi secara paralel. | *Write-starvation* (tergantung OS/fairness policy), write latency lebih tinggi. |
| **Atomics (`AtomicUsize`, dll)** | Status flag, state-machine ringkas, pencacah metrik. | Zero system-call overhead, sangat cepat, tidak memblokir thread. | Terbatas pada tipe data primitif seukuran *word*, logika reasoning rumit. |
| **Crossbeam Channel** | Arsitektur streaming pipeline, message-driven, actor model. | Pemisahan state bersih (*share-nothing*), bounded queue, dynamic `select!`. | Alokasi heap per pesan (kecuali dioptimalkan), copy latency untuk payload besar. |

---

## 5. How (Workflow Detail)

Alur kerja perancangan sistem konkurensi bebas-data-race dengan primitif lanjutan:

```
[Mulai Desain State]
        |
        v
Apakah state hanya primitif skalar (u32/u64/bool)?
        |-- Ya  --> Gunakan Atomic primitives + Relaxed/Acq/Rel
        |
        +-- Tidak -> Apakah rasio baca jauh lebih tinggi dari tulis?
                          |-- Ya  --> Gunakan std::sync::RwLock
                          |
                          +-- Tidak -> Apakah ada kebutuhan orkestrasi/sleep-wake?
                                            |-- Ya  --> Gunakan Mutex + Condvar
                                            |
                                            +-- Tidak -> Gunakan MPMC Channel Pipeline
```

### Prosedur Implementasi Compare-And-Swap (CAS) Loop
1. Baca status saat ini menggunakan operasi *atomic load* dengan `Ordering::Acquire` atau `Ordering::Relaxed`.
2. Hitung status baru yang diinginkan berdasarkan nilai yang dibaca.
3. Eksekusi `compare_exchange` atau `compare_exchange_weak`:
   - Jika berhasil: Transisi status sukses dengan semantik `Release`.
   - Jika gagal: Nilai telah dimutasi oleh *thread* lain. Ulangi loop tanpa *blocking* (*busy-wait* terkontrol atau `std::hint::spin_loop()`).

---

## 6. Analogi & Diagram ASCII

### 6.1 Analogi Operasi Memori
- **`Ordering::Release`** seperti seorang arsitek yang membungkus semua cetak biru yang sudah selesai ke dalam sebuah brankas, lalu menempelkan segel: *"Dokumen sebelum segel ini sudah valid."*
- **`Ordering::Acquire`** seperti inspektur lapangan yang memeriksa segel brankas tersebut: *"Begitu saya membuka segel ini, saya dijamin membaca cetak biru terbaru yang sah dari arsitek."*
- **`Ordering::Relaxed`** seperti menghitung jumlah mobil yang lewat di jalan tol menggunakan alat hitung cetak-cetek (*tally counter*). Urutan mobil tidak penting, yang penting jumlah akhirnya akurat tanpa ada mobil yang terlewat.

### 6.2 Visualisasi Memory Barrier & Acquire-Release Synchronization

```
THREAD A (Writer)                           THREAD B (Reader)
-----------------                           -----------------
data.store(42, Relaxed);
metadata.store(99, Relaxed);
                                             
[RELEASE BARRIER] - - - - - - - - - - - - - 
ready.store(true, Release);                 
        \                                           
         \ Synchronizes-With (via Cache/Bus)         
          \                                         
           +-------------------------------------> while !ready.load(Acquire) {}
                                                   [ACQUIRE BARRIER] - - - - - - -
                                                   assert_eq!(data.load(Relaxed), 42);
                                                   assert_eq!(metadata.load(Relaxed), 99);
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Spinlock Bebas-Kunci dengan Memory Ordering Presisi

Contoh ini menunjukkan pembuatan *mutual exclusion primitive* sederhana berbasis atomic `bool` untuk memahami mekanisme `Acquire` dan `Release`.

```rust
use std::sync::atomic::{AtomicBool, Ordering};
use std::cell::UnsafeCell;
use std::ops::{Deref, DerefMut};
use std::hint::spin_loop;

pub struct CustomSpinlock<T> {
    locked: AtomicBool,
    data: UnsafeCell<T>,
}

unsafe impl<T: Send> Sync for CustomSpinlock<T> {}
unsafe impl<T: Send> Send for CustomSpinlock<T> {}

pub struct CustomSpinlockGuard<'a, T> {
    lock: &'a CustomSpinlock<T>,
}

impl<T> CustomSpinlock<T> {
    pub const fn new(data: T) -> Self {
        Self {
            locked: AtomicBool::new(false),
            data: UnsafeCell::new(data),
        }
    }

    pub fn lock(&self) -> CustomSpinlockGuard<'_, T> {
        // Acquire ordering memastikan pembacaan data di dalam Guard 
        // tidak dapat di-reorder mendahului keberhasilan penguncian ini.
        while self.locked.swap(true, Ordering::Acquire) {
            // Memberikan petunjuk kepada CPU bahwa core sedang dalam spin-wait loop
            // Mengurangi konsumsi daya dan mencegah pipeline stall
            spin_loop();
        }
        CustomSpinlockGuard { lock: self }
    }
}

impl<'a, T> Deref for CustomSpinlockGuard<'a, T> {
    type Target = T;
    fn deref(&self) -> &Self::Target {
        unsafe { &*self.lock.data.get() }
    }
}

impl<'a, T> DerefMut for CustomSpinlockGuard<'a, T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        unsafe { &mut *self.lock.data.get() }
    }
}

impl<'a, T> Drop for CustomSpinlockGuard<'a, T> {
    fn drop(&mut self) {
        // Release ordering memastikan semua mutasi data selesai 
        // dan dipublikasikan sebelum status lock disetel kembali ke false.
        self.lock.locked.store(false, Ordering::Release);
    }
}

fn main() {
    use std::sync::Arc;
    use std::thread;

    let lock = Arc::new(CustomSpinlock::new(0));
    let mut handles = vec![];

    for _ in 0..8 {
        let lock_clone = Arc::clone(&lock);
        handles.push(thread::spawn(move || {
            for _ in 0..10_000 {
                let mut guard = lock_clone.lock();
                *guard += 1;
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(*lock.lock(), 80_000);
    println!("Spinlock test passed. Counter = {}", *lock.lock());
}
```

### 7.2 Practical Example: Enterprise Production Thread Pool

Implementasi thread pool siap produksi dengan arsitektur bounded job queue, penanganan sinyal terminasi anggun (*graceful shutdown*), pemulihan *lock poisoning*, serta metrik performa terintegrasi.

```rust
use std::sync::{Arc, Mutex, Condvar};
use std::thread::{self, JoinHandle};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

type Job = Box<dyn FnOnce() + Send + 'static>;

struct SharedPoolState {
    queue: Mutex<VecDeque<Job>>,
    has_work: Condvar,
    shutdown: AtomicBool,
    active_threads: AtomicUsize,
    queued_jobs: AtomicUsize,
    capacity: usize,
}

pub struct EnterpriseThreadPool {
    workers: Vec<Worker>,
    state: Arc<SharedPoolState>,
}

struct Worker {
    id: usize,
    thread: Option<JoinHandle<()>>,
}

#[derive(Debug)]
pub enum ThreadPoolError {
    QueueFull,
    PoolShuttingDown,
}

impl EnterpriseThreadPool {
    pub fn new(capacity: usize, max_workers: usize) -> Self {
        assert!(capacity > 0 && max_workers > 0);

        let state = Arc::new(SharedPoolState {
            queue: Mutex::new(VecDeque::with_capacity(capacity)),
            has_work: Condvar::new(),
            shutdown: AtomicBool::new(false),
            active_threads: AtomicUsize::new(0),
            queued_jobs: AtomicUsize::new(0),
            capacity,
        });

        let mut workers = Vec::with_capacity(max_workers);
        for id in 0..max_workers {
            workers.push(Worker::new(id, Arc::clone(&state)));
        }

        Self { workers, state }
    }

    pub fn execute<F>(&self, f: F) -> Result<(), ThreadPoolError>
    where
        F: FnOnce() + Send + 'static,
    {
        if self.state.shutdown.load(Ordering::Relaxed) {
            return Err(ThreadPoolError::PoolShuttingDown);
        }

        let mut queue = match self.state.queue.lock() {
            Ok(guard) => guard,
            Err(poisoned) => {
                // Recovery strategy: ambil alih poisoned guard untuk mencegah deadlock total
                eprintln!("[WARN] Queue lock was poisoned. Recovering state...");
                poisoned.into_inner()
            }
        };

        if queue.len() >= self.state.capacity {
            return Err(ThreadPoolError::QueueFull);
        }

        queue.push_back(Box::new(f));
        self.state.queued_jobs.fetch_add(1, Ordering::Relaxed);
        self.state.has_work.notify_one();
        Ok(())
    }

    pub fn shutdown(&self) {
        self.state.shutdown.store(true, Ordering::SeqCst);
        self.state.has_work.notify_all();
    }
}

impl Drop for EnterpriseThreadPool {
    fn drop(&mut self) {
        self.shutdown();
        for worker in &mut self.workers {
            if let Some(thread) = worker.thread.take() {
                if let Err(e) = thread.join() {
                    eprintln!("[ERROR] Worker thread {} panicked during join: {:?}", worker.id, e);
                }
            }
        }
    }
}

impl Worker {
    fn new(id: usize, state: Arc<SharedPoolState>) -> Self {
        let thread = thread::Builder::new()
            .name(format!("worker-pool-{}", id))
            .spawn(move || {
                loop {
                    let job = {
                        let mut queue = match state.queue.lock() {
                            Ok(guard) => guard,
                            Err(poisoned) => poisoned.into_inner(),
                        };

                        while queue.is_empty() && !state.shutdown.load(Ordering::Relaxed) {
                            queue = match state.has_work.wait(queue) {
                                Ok(guard) => guard,
                                Err(poisoned) => poisoned.into_inner(),
                            };
                        }

                        if state.shutdown.load(Ordering::Relaxed) && queue.is_empty() {
                            break;
                        }

                        let item = queue.pop_front();
                        if item.is_some() {
                            state.queued_jobs.fetch_sub(1, Ordering::Relaxed);
                        }
                        item
                    };

                    if let Some(job) = job {
                        state.active_threads.fetch_add(1, Ordering::Relaxed);
                        
                        // Menjalankan eksekusi job di dalam assertion boundaries
                        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(job));
                        if let Err(err) = result {
                            eprintln!("[ERROR] Worker {} encountered a panic in task: {:?}", id, err);
                        }

                        state.active_threads.fetch_sub(1, Ordering::Relaxed);
                    }
                }
            })
            .expect("Failed to spawn OS worker thread");

        Self {
            id,
            thread: Some(thread),
        }
    }
}
```

---

## 8. Real World Case Study: High-Frequency Trading (HFT) Order Book Aggregator

### Konteks Bisnis & Beban Kerja
Pada bursa derivatif terdistribusi, mesin *Order Matching Engine* harus memproses aliran transaksi hingga **500.000 pesanan per detik** dengan batas latensi p99 di bawah 50 mikrodetik. Penggunaan `Mutex` biasa menyebabkan lonjakan latensi (*latency jitter*) karena *syscall overhead* dan *thread preemption*.

### Desain Arsitektur
Sistem menggunakan pola arsitektur **LMAX Disruptor Pattern** yang disesuaikan untuk Rust:
1. **Core-Pinning (Affinity):** Setiap *thread* dipatok ke core fisik CPU tertentu menggunakan dependensi platform-level.
2. **Lock-Free Ring Buffer (Bounded):** Komunikasi antar *ingestion network thread* dan *matching engine thread* dilakukan melalui *atomic sequence numbers* tanpa kunci (`Mutex`).
3. **Cache Line Padding:** Struktur state dipisahkan sebesar 64-byte (panjang standar arsitektur x86/ARM L1 Cache Line) untuk mengeliminasi *False Sharing*.

```
   [ Network Ingestion Thread ]  <--- Core 0 (Pinned)
               |
         Writes Sequence
               |
               v
    +--------------------+  <--- 64-byte Cache Aligned Struct
    | Sequence (Atomic)  |
    +--------------------+
    | Cache Line Padding |  <--- Mencegah Core 0 & Core 1 bersaing di bus L1
    +--------------------+
    | Data Payload Array |
    +--------------------+
               |
         Reads Sequence
               v
   [ Matching Engine Thread ]   <--- Core 1 (Pinned)
```

```rust
use std::sync::atomic::{AtomicU64, Ordering};

// Representasi alokasi yang dilindungi dari False Sharing
#[repr(align(64))]
pub struct CachePaddedSequence {
    pub value: AtomicU64,
}

pub struct OrderEvent {
    pub order_id: u64,
    pub price: u64,
    pub quantity: u32,
}

pub struct LockFreeRingBuffer {
    buffer: Vec<OrderEvent>,
    capacity: usize,
    mask: usize,
    // Head dan Tail ditempatkan pada cache-line yang terisolasi total
    head: CachePaddedSequence,
    tail: CachePaddedSequence,
}

impl LockFreeRingBuffer {
    pub fn new(capacity_power_of_two: usize) -> Self {
        assert!(capacity_power_of_two.is_power_of_two());
        let mut buffer = Vec::with_capacity(capacity_power_of_two);
        for i in 0..capacity_power_of_two {
            buffer.push(OrderEvent { order_id: i as u64, price: 0, quantity: 0 });
        }

        Self {
            buffer,
            capacity: capacity_power_of_two,
            mask: capacity_power_of_two - 1,
            head: CachePaddedSequence { value: AtomicU64::new(0) },
            tail: CachePaddedSequence { value: AtomicU64::new(0) },
        }
    }

    // Dipanggil eksklusif oleh Single Producer
    pub fn try_push(&mut self, event: OrderEvent) -> Result<(), ()> {
        let current_tail = self.tail.value.load(Ordering::Relaxed);
        let current_head = self.head.value.load(Ordering::Acquire);

        if (current_tail - current_head) as usize >= self.capacity {
            return Err(()); // Buffer Penuh (Backpressure)
        }

        let index = (current_tail as usize) & self.mask;
        self.buffer[index] = event;

        // Mempublikasikan entry ke consumer
        self.tail.value.store(current_tail + 1, Ordering::Release);
        Ok(())
    }

    // Dipanggil eksklusif oleh Single Consumer
    pub fn try_pop(&self) -> Option<&OrderEvent> {
        let current_head = self.head.value.load(Ordering::Relaxed);
        let current_tail = self.tail.value.load(Ordering::Acquire);

        if current_head >= current_tail {
            return None; // Buffer Kosong
        }

        let index = (current_head as usize) & self.mask;
        let item = &self.buffer[index];

        self.head.value.store(current_head + 1, Ordering::Release);
        Some(item)
    }
}
```

---

## 9. Trade-offs

| Dimensi Rekayasa | Pendekatan Mutex/Lock | Pendekatan Lock-Free / Atomics |
| :--- | :--- | :--- |
| **Throughput (Low Contention)** | Setara (sangat cepat melalui optimasi Futex). | Setara (satu atau dua instruksi mesin). |
| **Throughput (High Contention)** | Menurun drastis akibat *Kernel Context Switching*. | Stabil dan tinggi, beban beralih ke saturasi CPU cache interconnect. |
| **Latency Jitter (p99.9)** | Buruk: *Thread preemption* tak menentu dari OS scheduler. | Sangat deterministic: Tidak pernah memanggil *blocking system call*. |
| **Kompleksitas Verifikasi Kode** | Rendah: Dijamin compiler melalui `MutexGuard`. | Ekstrem: Rentan bug *reordering* subtil pada ARM. Membutuhkan verifikasi Miri & Loom. |
| **Konsumsi Daya / Baterai** | Efisien saat idle: Thread langsung dialihkan ke status sleep. | Berpotensi boros jika spin loop tidak dikendalikan dengan *backoff* adaptif. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 False Sharing (Penurunan Performa Siluman)
- **Gejala:** Menambah *thread* justru menurunkan total *throughput* secara drastis, padahal tidak ada *Mutex* yang saling berebut antar *thread*.
- **Penyebab:** Dua variabel independen yang dimutasi oleh core berbeda berada dalam rentang memori 64-byte yang sama (*same cache line*). Protokol MESI memaksa cache line di-invalidasi bolak-balik antar core (*cache line bouncing*).
- **Solusi:** Gunakan `#[repr(align(64))]` atau struktur pembungkus seperti `crossbeam_utils::CachePadded`.

### 10.2 Lock Poisoning Melumpuhkan Seluruh Aplikasi
- **Gejala:** Satu *thread panic* menyebabkan semua *thread* lain ikut tumbang secara beruntun (*cascading failure*) pada pemanggilan `.lock().unwrap()`.
- **Solusi:** Tangani status `PoisonError` secara eksplisit alih-alih menggunakan `.unwrap()`. Panggil `.into_inner()` jika invariants state data dapat dijamin atau di-reset.

### 10.3 Asumsi Memory Ordering x86-64 yang Gagal di ARM64
- **Gejala:** Aplikasi berjalan sempurna pada mesin dev (Intel/AMD), namun memicu data race atau pembacaan pointer null saat di-deploy ke AWS Graviton atau Apple Silicon.
- **Penyebab:** Pengembang menggunakan `Ordering::Relaxed` pada publikasi pointer/data. Di x86, hardware memaksakan ordering baca-tulis, sehingga bug tidak tampak. Di ARM, hardware mereorder operasi tersebut secara bebas.
- **Solusi:** Selalu pasangkan penulisan status publikasi dengan `Ordering::Release` dan pembacaan dengan `Ordering::Acquire`.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Verifikasi Formal Loom & Miri:** Semua modul yang memuat `unsafe` dan `atomic` wajib lolos uji `cargo miri test` dan integrasi crate `loom`.
2. [ ] **Penamaan Thread Eksplisit:** Selalu gunakan `std::thread::Builder::new().name("service-worker".into()).spawn(...)` untuk memudahkan analisis *stack trace* dan *profiling* produksi (misal via `htop` atau `perf`).
3. [ ] **Bounded Channels Only:** Jangan gunakan kanal memori tak terbatas (*unbounded*) pada pipeline produksi. Aliran data tanpa backpressure pasti berujung pada kondisi OOM (*Out Of Memory*).
4. [ ] **Strategi Panic Isolation:** Pasang `std::panic::catch_unwind` pada *thread boundary* pekerjaan jangka panjang agar kegagalan satu request tidak mematikan *daemon host thread*.
5. [ ] **Backoff Adaptif:** Jika menggunakan *spin-loop*, terapkan eksponensial backoff: `spin_loop()` $\to$ `thread::yield_now()` $\to$ `thread::park_timeout()`.

---

## 12. Hands-on Practice: Membangun Event Ingestion Pipeline

Buat direktori baru untuk praktikum ini: `hands-on/m02/`

### File: `hands-on/m02/Cargo.toml`
```toml
[package]
name = "concurrent_telemetry_pipeline"
version = "0.1.0"
edition = "2021"

[dependencies]
crossbeam-channel = "0.5"
```

### File: `hands-on/m02/src/main.rs`
```rust
use crossbeam_channel::{bounded, Receiver, Sender};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct MetricPayload {
    pub device_id: u32,
    pub temperature: f32,
    pub timestamp_ms: u64,
}

pub struct TelemetryPipeline {
    tx: Sender<MetricPayload>,
    shutdown: Arc<AtomicBool>,
    processed_count: Arc<AtomicUsize>,
    workers: Vec<thread::JoinHandle<()>>,
}

impl TelemetryPipeline {
    pub fn new(worker_count: usize, queue_bound: usize) -> Self {
        let (tx, rx) = bounded::<MetricPayload>(queue_bound);
        let shutdown = Arc::new(AtomicBool::new(false));
        let processed_count = Arc::new(AtomicUsize::new(0));
        let mut workers = Vec::with_capacity(worker_count);

        for id in 0..worker_count {
            let rx_worker = rx.clone();
            let shutdown_worker = Arc::clone(&shutdown);
            let count_worker = Arc::clone(&processed_count);

            let handle = thread::Builder::new()
                .name(format!("telemetry-processor-{}", id))
                .spawn(move || {
                    while !shutdown_worker.load(Ordering::Relaxed) || !rx_worker.is_empty() {
                        // Menggunakan timeout agar thread rutin memeriksa sinyal shutdown
                        if let Ok(metric) = rx_worker.recv_timeout(Duration::from_millis(50)) {
                            Self::process_metric(&metric);
                            count_worker.fetch_add(1, Ordering::Relaxed);
                        }
                    }
                })
                .expect("Failed to spawn ingestion thread");

            workers.push(handle);
        }

        Self {
            tx,
            shutdown,
            processed_count,
            workers,
        }
    }

    pub fn submit(&self, metric: MetricPayload) -> Result<(), crossbeam_channel::TrySendError<MetricPayload>> {
        self.tx.try_send(metric)
    }

    fn process_metric(metric: &MetricPayload) {
        // Simulasi kalkulasi analitik ringan
        let _ = metric.temperature * 1.8 + 32.0;
    }

    pub fn stop(self) -> usize {
        self.shutdown.store(true, Ordering::Release);
        drop(self.tx); // Tutup channel untuk memberi sinyal drain ke worker

        for handle in self.workers {
            handle.join().unwrap();
        }

        self.processed_count.load(Ordering::Acquire)
    }
}

fn main() {
    println!("[SYSTEM] Inisialisasi Telemetry Pipeline High-Throughput...");
    let pipeline = TelemetryPipeline::new(4, 10_000);
    let start_time = Instant::now();

    // Simulasi producer traffic
    let mut sent = 0;
    for i in 0..100_000 {
        let payload = MetricPayload {
            device_id: i % 500,
            temperature: 24.5 + (i as f32 * 0.001),
            timestamp_ms: 1717000000 + i as u64,
        };

        if pipeline.submit(payload).is_ok() {
            sent += 1;
        }
    }

    println!("[SYSTEM] Berhasil mengirim {} paket data. Memulai Graceful Shutdown...", sent);
    let total_processed = pipeline.stop();
    let duration = start_time.elapsed();

    println!("================ HASIL PRODUKSI ================");
    println!("Total Metrik Diproses : {}", total_processed);
    println!("Durasi Eksekusi       : {:?}", duration);
    println!("Throughput Aktual     : {:.2} events/sec", (total_processed as f64) / duration.as_secs_f64());
    println!("================================================");
}
```

---

## 13. Exercises

### Tingkat: Easy
Rancang koordinasi *barrier* menggunakan `std::sync::Barrier` di mana terdapat 5 *worker thread*. Setiap thread memproses data batch parsial, berhenti di *barrier*, lalu secara bersamaan mencetak pesan bahwa seluruh *worker* siap untuk fase berikutnya.

### Tingkat: Medium
Modifikasi `CustomSpinlock<T>` pada Subbab 7.1 untuk menyertakan batas waktu percobaan penguncian: `fn try_lock_for(&self, timeout: Duration) -> Option<CustomSpinlockGuard<'_, T>>`. Jika kunci gagal didapatkan dalam interval tersebut, fungsi harus mengembalikan `None`.

### Tingkat: Hard
Implementasikan struktur data antrean bebas-kunci *Single-Producer Single-Consumer* (SPSC) *Bounded Ring Buffer* tanpa alokasi dinamis baru saat *runtime*, hanya menggunakan `AtomicUsize` dengan skema `Ordering::Acquire` dan `Ordering::Release`. Buktikan implementasi bebas dari *race condition* dengan menguji 1.000.000 mutasi integer antar 2 thread.

---

## 14. Challenges

### Deskripsi Masalah: Resilient Multi-Stage Pipeline with Backpressure & Dynamic Autoscaling
Sebuah sistem pemrosesan log telemetri enterprise menerima lonjakan volume data acak (antara 10.000 hingga 1.000.000 event/detik). 

### Ketentuan Teknis:
1. Bangun sistem arsitektur pipeline 3-tahap:
   - **Tahap 1 (Ingestor):** Menerima string mentah dan memvalidasi formatnya.
   - **Tahap 2 (Transformer):** Mem-parsing string ke format JSON terstruktur dan melakukan hashing data sensitif.
   - **Tahap 3 (Sink):** Mengumpulkan data dalam batch sebesar 100 entri atau *window timeout* 10ms dan menulisnya ke media persistensi tiruan (*in-memory mocked storage*).
2. Terapkan mekanisme **Dynamic Worker Autoscaling** pada Tahap 2:
   - Pantau kapasitas channel antara Tahap 1 dan Tahap 2.
   - Jika kapasitas antrean terisi > 80%, spawn worker baru secara dinamis (maksimal 16 core).
   - Jika kapasitas antrean menyusut < 20% selama 3 detik berturut-turut, terminasi worker cadangan hingga batas minimum 2 worker.
3. Seluruh channel wajib menerapkan kapasitas berbatas (*strictly bounded*). Jika Tahap 1 mendeteksi antrean penuh, berikan *backpressure signal* langsung ke producer.
4. **Zero Tolerance:** Dilarang menggunakan `unwrap()` pada seluruh primitif sinkronisasi. Penanganan *Lock Poisoning* dan *Graceful Flush* wajib diimplementasikan saat sinyal SIGINT/shutdown dikirimkan.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda / Konseptual)

1. **Apa perbedaan struktural utama antara `Sync` dan `Send` pada sistem tipe Rust?**
   - A. `Send` memperbolehkan mutasi paralel, sedangkan `Sync` hanya baca.
   - B. Tipe `T: Send` aman ditransfer antar-thread; tipe `T: Sync` aman direferensikan bersama (`&T`) lintas thread.
   - C. `Sync` selalu diimplementasikan secara otomatis jika tipe mengimplementasikan `Clone`.
   - D. `Send` hanya berlaku untuk pointer mentah (`*const T`).

2. **Apa yang terjadi ketika sebuah thread mengalami *panic* saat sedang memegang *guard* dari sebuah `std::sync::Mutex`?**
   - A. Mutex otomatis dilepaskan dan data direset ke nilai `Default::default()`.
   - B. Mutex mengalami *deadlock* permanen tanpa bisa dibuka kembali.
   - C. Mutex masuk ke status *poisoned*; panggilan `.lock()` selanjutnya pada thread lain akan menghasilkan `Result::Err(PoisonError)`.
   - D. Kompiler Rust menolak program tersebut saat proses kompilasi.

3. **Mengapa `Ordering::Relaxed` tidak cukup untuk mengimplementasikan *flag signaling* publikasi data antar-thread?**
   - A. Karena `Relaxed` mengubah data menjadi read-only.
   - B. Karena `Relaxed` mengizinkan kompilator dan prosesor mereorder operasi memori non-atomik di sekitarnya melompati instruksi atomic tersebut.
   - C. Karena operasi `Relaxed` tidak bersifat atomik pada arsitektur 64-bit.
   - D. Karena `Relaxed` membutuhkan alokasi memori heap tambahan.

4. **Kapan Anda harus memilih `std::sync::RwLock` dibandingkan `std::sync::Mutex`?**
   - A. Ketika data berukuran di bawah 8 byte.
   - B. Ketika terdapat sangat banyak operasi penulisan dan sedikit operasi pembacaan.
   - C. Ketika rasio operasi pembacaan jauh melampaui operasi penulisan (*read-heavy*), dan konkurensi pembaca harus dimaksimalkan.
   - D. Ketika operasi pembacaan membutuhkan akses mutasi eksklusif.

5. **Apa fungsi utama dari fungsi intrinsik `std::hint::spin_loop()` dalam implementasi antrean berbasis spin?**
   - A. Memaksa thread tertidur (*sleep*) selama 1 milidetik.
   - B. Memberi tahu prosesor bahwa thread sedang berada dalam *busy-wait*, membantu optimasi konsumsi pipeline dan daya CPU.
   - C. Menginstruksikan kernel OS untuk langsung melakukan *context switch*.
   - D. Menghapus status *lock poisoning*.

---

### 15.2 Pertanyaan Intermediate

6. **Mengapa dua variabel atomic independen yang diakses secara simultan oleh dua thread berbeda dapat menyebabkan penurunan performa ekstrem jika dialokasikan berdampingan di memori?**
   - A. Fenomena ini disebut *ABA Problem*.
   - B. Fenomena ini disebut *False Sharing*, di mana kedua variabel berada dalam satu *Cache Line* (64-byte) yang sama, memicu invalidasi bus berulang kali.
   - C. Operasi atomik hanya dapat dieksekusi oleh satu core CPU di seluruh soket motherboard.
   - D. Rust mendeteksi data race pada level alokator memori runtime.

7. **Perhatikan urutan operasi berikut. Apakah operasi assert di Thread 2 dijamin berhasil? Jelaskan alasannya.**
   ```rust
   // Thread 1
   DATA.store(100, Ordering::Relaxed);
   FLAG.store(true, Ordering::Release);

   // Thread 2
   while !FLAG.load(Ordering::Relaxed) {}
   assert_eq!(DATA.load(Ordering::Relaxed), 100);
   ```
   - A. Pasti berhasil di semua arsitektur CPU karena `FLAG` menggunakan `Ordering::Release`.
   - B. Tidak dijamin di arsitektur *weakly-ordered* (misal: ARM), karena pembacaan `FLAG` di Thread 2 menggunakan `Relaxed`, bukan `Acquire`, sehingga sinkronisasi *Acquire-Release* tidak terbentuk.
   - C. Pasti gagal di compiler level karena `Ordering::Relaxed` menolak tipe data integer.
   - D. Berhasil hanya jika program dikompilasi dalam mode `--release`.

8. **Apa bahaya terbesar menggunakan kanal tak terbatas (*unbounded channel*) pada sistem pesan produksi?**
   - A. Latensi kompilasi bertambah secara eksponensial.
   - B. Kapasitas tak terbatas menyebabkan kegagalan sistem total akibat *Out of Memory* (OOM) jika laju *producer* melampaui kapasitas serap *consumer*.
   - C. Pesan yang dikirimkan dapat terbaca dua kali oleh consumer yang berbeda.
   - D. Kanal tak terbatas tidak dapat diintegrasikan dengan thread pool.

9. **Bagaimana mekanisme `crossbeam_channel::select!` bekerja di bawah kap mesin?**
   - A. Melakukan polling aktif berbasis spin tanpa jeda hingga ada pesan yang masuk.
   - B. Mengunci semua antrean kanal secara acak tanpa algoritma proteksi deadlock.
   - C. Mendaftarkan listener pada semua kanal terkait, mengurutkan lock internal berdasarkan alamat memori kanal untuk mencegah *deadlock*, lalu menidurkan thread hingga salah satu kanal siap.
   - D. Membuat thread baru untuk setiap ekspresi `select!`.

10. **Apa perbedaan antara `compare_exchange` dan `compare_exchange_weak`?**
    - A. `compare_exchange_weak` hanya bekerja pada tipe data boolean.
    - B. `compare_exchange_weak` diizinkan mengalami *spurious failure* (gagal meskipun nilai lama cocok), namun menghasilkan instruksi mesin yang lebih efisien pada arsitektur tertentu dalam loop CAS.
    - C. `compare_exchange` tidak memerlukan penentuan parameter memory ordering.
    - D. `compare_exchange_weak` tidak memodifikasi memori fisik.

---

### 15.3 Skenario Kasus Produksi

11. **Skenario Kasus 1: Deadlock Laten pada Arsitektur Transaksi Finansial**
    Sebuah modul pembayaran bank mentransfer saldo antar dua akun menggunakan struktur berikut:
    ```rust
    struct Account {
        balance: Mutex<u64>,
    }
    fn transfer(from: &Account, to: &Account, amount: u64) {
        let mut guard_from = from.balance.lock().unwrap();
        let mut guard_to = to.balance.lock().unwrap();
        *guard_from -= amount;
        *guard_to += amount;
    }
    ```
    Sistem mengalami *hang* total saat dua pengguna mentransfer uang secara bersamaan: Pengguna A mentransfer ke Pengguna B, dan Pengguna B mentransfer ke Pengguna A.
    - **Tugas Anda:** Analisis penyebab kegagalan dan berikan solusi implementasi arsitektur Rust yang deterministik untuk mencegah insiden tersebut.

12. **Skenario Kasus 2: Degradasi Latensi P99.9 Akibat Mutex Contention pada Telemetri**
    Layanan HTTP microservice Anda memproses 80.000 req/sec. Setiap request melakukan logging metrik latensi ke dalam sebuah `Arc<Mutex<Histogram>>`. Tim SRE melaporkan bahwa latensi p99.9 melesat dari 2ms ke 450ms selama jam sibuk, meskipun utilisasi CPU keseluruhan baru mencapai 35%.
    - **Tugas Anda:** Diagnosis anomali bottleneck ini dan jelaskan arsitektur pengganti yang harus dibangun untuk mengeliminasi latensi spike tersebut tanpa kehilangan akurasi data.

13. **Skenario Kasus 3: Cascading Failure Pasca Panic pada Worker**
    Dalam sistem pemrosesan antrean batch enterprise berbasis `Arc<Mutex<SharedTaskQueue>>`, salah satu payload JSON dari klien memiliki format malformasi ekstrim yang memicu *panic* di dalam salah satu worker thread. Beberapa detik kemudian, seluruh 32 worker thread lainnya dalam pool mati serentak dan sistem berhenti memproses antrean.
    - **Tugas Anda:** Jelaskan rantai peristiwa internal Rust yang memicu matinya seluruh worker thread tersebut, dan tuliskan pola mitigasi arsitektur untuk memastikan *panic* pada satu data item tidak merusak operasional sisa thread lainnya.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### 15.1 Basic
1. **B** — Tipe `Send` mengizinkan transfer kepemilikan nilai lintas thread. Tipe `Sync` mengizinkan referensi bersama yang aman dibagikan lintas thread (`&T: Send`).
2. **C** — Mutex di Rust menerapkan status *poisoning* jika thread pemegang guard mengalami unwinding panic, menghasilkan `PoisonError` pada pemanggilan selanjutnya.
3. **B** — `Ordering::Relaxed` hanya menjamin sifat atomic dari variabel itu sendiri tanpa menerapkan batasan instruksi *reordering* pada instruksi di sekitarnya.
4. **C** — `RwLock` didesain untuk workload yang didominasi oleh operasi pembacaan konkuren, mengizinkan banyak pembaca berjalan paralel selama tidak ada operasi tulis.
5. **B** — `spin_loop` mengeksekusi instruksi tingkat rendah CPU (seperti `PAUSE` di x86) yang mencegah keausan daya dan stalls pada out-of-order execution core.

#### 15.2 Intermediate
6. **B** — Dua data pada cache line 64-byte yang sama memicu siklus invalidasi status MESI bolak-balik antar core CPU (*False Sharing*).
7. **B** — Sinkronisasi *synchronizes-with* membutuhkan pasangan yang valid: operasi tulis dengan `Release` dan operasi baca dengan `Acquire`. Karena Thread 2 membaca dengan `Relaxed`, CPU diizinkan membaca data lama yang di-reorder.
8. **B** — Tanpa backpressure, channel unbounded akan terus menyerap alokasi memori heap hingga OS membunuh proses via OOM Killer (*Out-Of-Memory*).
9. **C** — Mekanisme internal `select!` mengurutkan penguncian berdasarkan alamat memori (lock hierarchy ordering) untuk menghindari circular lock acquisition sebelum menidurkan thread.
10. **B** — `compare_exchange_weak` dapat gagal secara semu karena interupsi mikroarsitektur, namun lebih optimal diimplementasikan dalam loop di arsitektur ARM/LL/SC.

#### 15.3 Skenario Kasus Produksi
11. **Solusi Deadlock Finansial:**
    - *Penyebab:* Terjadi kondisi penguncian melingkar (*circular wait* / Coffman conditions) saat `transfer(A, B)` mengunci A lalu menunggu B, sementara secara bersamaan `transfer(B, A)` mengunci B lalu menunggu A.
    - *Solusi Rekayasa:* Terapkan penentuan urutan penguncian global yang deterministik (*Deterministic Lock Ordering*). Setiap akun wajib memiliki ID unik. Lakukan penguncian selalu dari ID terkecil ke ID terbesar:
      ```rust
      fn transfer(from: &Account, to: &Account, amount: u64) {
          if from.id == to.id { return; }
          // Urutkan penguncian berdasarkan id akun
          let (first, second) = if from.id < to.id {
              (&from.balance, &to.balance)
          } else {
              (&to.balance, &from.balance)
          };
          let _g1 = first.lock().unwrap();
          let _g2 = second.lock().unwrap();
          // Mutasi balance aman dari deadlock
      }
      ```
12. **Solusi Contention Telemetri:**
    - *Penyebab:* 80.000 req/sec memaksa thread berebut satu kunci `Mutex` global. Meskipun pekerjaan di dalam mutex sangat singkat, kontensi pada OS-level Futex menyebabkan ratusan thread di-preempt ke status suspend oleh scheduler kernel, memicu latency spike masif.
    - *Solusi Rekayasa:* Terapkan arsitektur **Thread-Local Aggregation** atau **Striped/Sharded Histogram**:
      1. Berikan buffer lokal pada masing-masing thread (*thread-local storage* via `thread_local!`). Metrik diakumulasi tanpa ada penguncian sama sekali.
      2. Jalankan background reporter thread independen setiap 1 detik yang bertugas mengumpulkan data agregat dari seluruh thread-local buffers.
      3. Alternatif lain: Gunakan struktur data bebas-kunci berbasis *Atomic Bucket Array*.
13. **Solusi Cascading Panic Worker:**
    - *Penyebab:* Saat satu worker panic ketika memproses JSON korup di dalam loop penarikan antrean, worker tersebut mati meninggalkan `Mutex<SharedTaskQueue>` dalam status teracuni (*poisoned*). Ketika worker berikutnya memanggil `.lock().unwrap()`, pemanggilan `.unwrap()` tersebut memicu *panic* kedua karena mendeteksi `PoisonError`. Rantai ini terus berulang (*cascading failure*) hingga seluruh worker thread mati.
    - *Solusi Rekayasa:*
      1. Tangkap status racun menggunakan `match queue.lock() { Ok(g) => g, Err(p) => p.into_inner() }` sehingga sisa antrean tetap dapat diproses.
      2. Isolasi eksekusi unit tugas di dalam boundary `std::panic::catch_unwind(AssertUnwindSafe(...))` agar panic pada task tidak membunuh host worker thread.
      3. Catat payload penyebab panic ke dead-letter-queue (DLQ) untuk analisis lanjutan.

---

## 16. Summary

- **Fearless Concurrency Tingkat Lanjut** di Rust dibangun di atas pemahaman batas perangkat keras: Model memori Rust menjamin ketiadaan *Data Races*, namun *Race Conditions* logis, *Deadlock*, dan degradasi performa mikro-arsitektur (*False Sharing*) tetap merupakan tanggung jawab perancang perangkat lunak.
- **Model Konsistensi Memori:** `Ordering::Relaxed` memberikan performa tertinggi untuk counter skalar; pasangan `Acquire` dan `Release` membentuk relasi *happens-before* formal yang menjamin publikasi data aman tanpa overhead berat; `SeqCst` memberlakukan keterurutan global tunggal dengan kompensasi throughput.
- **Ketahanan Sistem Produksi:** Kode produksi menuntut penghapusan asumsi optimis. Setiap saluran komunikasi harus berbatas (*bounded backpressure*), *lock poisoning* harus dapat dipulihkan, dan eksekusi instruksi di batas *thread* wajib dilindungi isolasi *panic* dan *graceful termination*.