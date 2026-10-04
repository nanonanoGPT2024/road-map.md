# Kurikulum Rekayasa Perangkat Lunak Enterprise: Rust
## Kategori: 02-Programming-Languages
### BAB 06: Asynchronous Programming & Tokio Runtime
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Principal/Staff Engineer diharapkan mampu:
1. **Menganalisis dan Membedah Internal Tokio Engine**: Memahami alur eksekusi internal Tokio multi-threaded work-stealing runtime, interaksi epoll/kqueue/IOCP via Mio reactor, serta mekanisme *cooperative budgeting* dan *waker registration*.
2. **Menguasai Mekanika Pinning & Memory Layout Future**: Menjelaskan siklus hidup `Pin<&mut T>`, proyeksi struktural via `pin-project-lite`, serta pencegahan *undefined behavior* pada *self-referential structs* saat kompilasi async.
3. **Mendesain Arsitektur Asinkron Skala Enterprise**: Mengimplementasikan *Graceful Shutdown coordination*, *Actor Pattern* murni berbasis message passing, *Backpressure Control* via bounded channels & distributed semaphores, serta *Structured Concurrency*.
4. **Mencegah Anti-Pattern Runtime Degradation**: Menghindari *worker thread starvation*, *priority inversion*, async memory leaks akibat *cancellation safety violation*, dan *unbounded channel buffer bloat*.
5. **Membangun Observabilitas Produksi**: Menerapkan *distributed tracing*, metrik runtime interaktif (`tokio-metrics`), dan profiling *cooperative budget yield* pada beban kerja I/O intensif (100k+ RPS).

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib memiliki penguasaan mutlak pada materi:
- **Rust Memory Model**: Ownership, Borrowing, Lifetimes (`'a`), dan implementasi trait fundamental (`Send`, `Sync`, `Unpin`, `Drop`).
- **Bab 06 Modul 01**: Dasar-dasar async/await, pembuatan `Future` sederhana, pemanggilan `tokio::spawn`, dan penggunaan dasar macro `tokio::select!`.
- **System Programming Fundamentals**: System calls OS (`epoll_create1`, `epoll_ctl`, `epoll_wait`, `kqueue`, non-blocking socket flag `O_NONBLOCK`), kernel space vs user space context switching.
- **Concurrent Primitives**: Atomic types (`AtomicUsize`, `AtomicBool`), `Arc`, mutex lock contention, dan channel topologies (MPSC, broadcast, watch).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur Tokio multi-threaded runtime dibangun di atas tiga pilar utama: **Reactor (Mio)**, **Scheduler (Work-Stealing Engine)**, dan **Timer Wheel**.

```
+-----------------------------------------------------------------------------------+
|                               TOKIO RUNTIME INSTANCE                              |
|                                                                                   |
|  +------------------------+  +-------------------------------------------------+  |
|  |     GLOBAL QUEUE       |  |                 IO / TIME DRIVERS               |  |
|  |  (Lock-free Injector)  |  |  +---------------------+  +------------------+  |  |
|  +------------------------+  |  |     Mio Reactor     |  |   Timer Wheel    |  |  |
|              |               |  | (epoll/kqueue/IOCP) |  | (Hashed Wheels)  |  |  |
|              v               |  +---------------------+  +------------------+  |  |
|  +------------------------+  +-------------------------------------------------+  |
|  | Worker Thread 0        |              ^                       ^                |
|  |  [LIFO Slot]           |              | (Read/Write Ready)    | (Tick)         |
|  |  [Local Run Queue:256] |              |                       |                |
|  +------------------------+              |                       |                |
|       ^              | Steal Half        |                       |                |
|       |              v                   |                       |                |
|  +------------------------+              |                       |                |
|  | Worker Thread 1        |--------------+                       |                |
|  |  [LIFO Slot]           |                                      |                |
|  |  [Local Run Queue:256] |--------------------------------------+                |
|  +------------------------+                                                       |
+-----------------------------------------------------------------------------------+
```

#### 3.1. Scheduler Architecture & The Work-Stealing Algorithm
Tokio Runtime (`rt-multi-thread`) mengalokasikan sejumlah *worker threads* yang setara dengan core CPU logis (dapat dikustomisasi via `WorkerThreads`). Setiap worker thread memiliki:
1. **LIFO Slot**: Satu slot khusus yang menampung task terakhir yang dijadwalkan. Slot ini memberikan optimasi *CPU cache locality*, mengasumsikan task yang baru saja dibuat/dibangunkan memiliki dependensi data langsung terhadap task saat ini.
2. **Local Run Queue**: Sebuah ring-buffer *lock-free* berkapasitas tetap (256 task). Eksekusi task lokal bebas dari *contention lock*.
3. **Global Injector Queue**: Antrean bersama yang dilindungi algoritma lock-free berbasis Michael-Scott Queue / epoch-based memory reclamation. Task yang di-spawn dari luar context Tokio worker (misalnya thread OS murni) masuk ke queue ini.

**Mekanisme Work-Stealing Workflow:**
- Ketika worker thread mengeksekusi task, ia memeriksa LIFO slot terlebih dahulu.
- Jika LIFO kosong, ia mengambil task dari Local Run Queue.
- Setiap **61 tick**, worker thread dipaksa memeriksa Global Queue untuk mencegah *starvation* pada task yang di-spawn dari luar worker.
- Jika Local Run Queue kosong, worker beralih menjadi *thief* (pencuri):
  - Mengambil separuh (half) kapasitas dari Local Run Queue milik worker thread lain secara acak (*work stealing*).
  - Jika seluruh worker kosong, ia memeriksa Global Injector Queue.
  - Jika tetap kosong, worker memeriksa kesiapan I/O via Reactor (`epoll_wait`).

#### 3.2. Reactor Driver & Non-blocking I/O
Tokio mengabstraksi I/O non-blocking via `mio` (Metal IO). Saat Anda mendaftarkan `tokio::net::TcpStream`:
1. Socket disetel ke mode non-blocking (`O_NONBLOCK`).
2. File Descriptor (FD) didaftarkan ke Mio Reactor via `epoll_ctl` (Linux) dengan bendera `EPOLLET` (Edge-Triggered) dan mask `EPOLLIN | EPOLLOUT`.
3. Ketika I/O belum siap (mengembalikan `WouldBlock` atau `EAGAIN` pada tingkat OS), Tokio membuat `Waker` yang mengikat `Task ID` ke driver I/O.
4. Future mengembalikan `Poll::Pending`.
5. Worker thread melepaskan eksekusi task tersebut dan mengambil task lain dari run queue.
6. Ketika kernel mengirimkan notifikasi readiness melalui `epoll_wait`, Mio Driver mengekstrak token yang diasosiasikan dengan FD, mengambil `Waker`, lalu memanggil `waker.wake()`.
7. Task dimasukkan kembali ke Local Run Queue worker thread untuk di-poll ulang.

#### 3.3. Cooperative Scheduling & Task Budget
Di sistem runtime non-preemptive seperti async Rust, task yang menjalankan loop komputasi tanpa batas dapat memonopoli thread worker (*monopolization*). Tokio memperkenalkan **Cooperative Scheduling Budget**:
- Setiap task dialokasikan budget operasi sebesar **128 unit**.
- Setiap operasi resource internal Tokio (misal read/write channel, I/O socket read) mengonsumsi 1 unit budget.
- Ketika budget habis (mencapai 0), Tokio runtime secara otomatis mengembalikan status `Poll::Pending` dari resource tersebut, memotong eksekusi task, menyetel `Waker` task tersebut agar segera dijadwalkan ulang di antrean belakang (*self-yielding*), dan menyerahkan eksekusi thread ke task lain.
- Fitur ini dapat dipicu secara eksplisit oleh developer menggunakan `tokio::task::yield_now().await`.

#### 3.4. Pinning, Unpin, dan Memory Safety pada Self-Referential Futures
Kompiler Rust mentransformasikan blok `async fn` menjadi sebuah *State Machine enum* anonim. Jika future menyimpan variabel lokal yang direferensikan melintasi titik `.await`, struct tersebut menjadi **self-referential**:

```
+------------------------------------+
| State Machine Task                 |
|  data: [u8; 1024] <------------+   |
|  ptr: *const u8 ---------------|---+  (Menunjuk ke field internal sendiri)
|  state: State2                     |
+------------------------------------+
```

Jika struct ini dipindahkan (*moved*) dalam memori via memcpy, pointer internal (`ptr`) akan mengarah ke alamat memori lama yang kini tidak valid (Dangling Pointer / Undefined Behavior).
- `Pin<P<T>>`: Sebuah wrapper pointer yang menjamin bahwa data bertipe `T` di balik pointer `P` tidak akan pernah dipindahkan posisinya dalam memori sampai objek tersebut di-drop (jika `T` tidak mengimplementasikan auto-trait `Unpin`).
- Trait `Unpin`: Auto-trait yang menandakan bahwa suatu tipe aman untuk dipindahkan meskipun dibungkus `Pin`. Kompiler mengimplementasikannya secara otomatis kecuali struct mengandung penanda khusus (`PhantomPinned`) atau future asinkron yang memegang referensi cross-await.

---

### 4. Why & What

| Paradigma / Arsitektur | Thread-per-Core (Blocking OS Thread) | Asynchronous Engine (Tokio Runtime) |
| :--- | :--- | :--- |
| **Model Konkurensi** | 1 Native Thread OS per koneksi klien. | M:N Scheduler (M task asinkron dijadwalkan di atas N worker thread OS). |
| **Konsumsi Memori** | Overhead stack OS default 2MB s/d 8MB per thread. 10.000 koneksi = ~20-80 GB RAM. | Overhead State Machine future ~ beberapa ratus byte s/d kilobyte. 10.000 koneksi = ~20-50 MB RAM. |
| **Context Switching** | Kernel-space context switch (mahal, invalidasi register CPU, TLB cache flush). | User-space function call via `poll()` (murah, optimasi inline compiler LLVM). |
| **Mekanisme I/O** | Thread diblokir oleh kernel syscall (`read`/`write`) hingga data tersedia. | Non-blocking syscall (`EWOULDBLOCK`), kernel event multiplexing (`epoll`/`kqueue`). |
| **Skalabilitas Limit** | Terbatas oleh resource batas thread OS kernel (`/proc/sys/kernel/threads-max`). | Dibatasi murni oleh ketersediaan RAM dan kapasitas open file descriptors (`ulimit -n`). |

**Mengapa Tokio Menjadi Pilihan Standar Enterprise?**
1. **Zero-Cost Abstractions**: Abstraksi `Future` di Rust tidak memerlukan dynamic memory allocation (heap) wajib untuk chaining, tidak membutuhkan Garbage Collector, dan runtime state machine dioptimalkan langsung oleh LLVM.
2. **Kestabilan dan Ekosistem**: Tokio menyediakan ekosistem teruji (`tonic` untuk gRPC, `hyper` untuk HTTP, `axum` untuk web framework, `tracing` untuk telemetri terdistribusi).
3. **Fault-Isolation**: Dukungan komprehensif terhadap pembatalan aman (*structured cancellation*) dan pemisahan blocking pool (`spawn_blocking`) untuk mencegah degradasi low-latency thread.

---

### 5. How (Workflow Detail)

Berikut adalah tahapan siklus hidup eksekusi task di dalam Tokio runtime:

```
[tokio::spawn(async move { ... })]
                │
                ▼
  [Bungkus Future ke dalam Task]
                │
                ▼
  [Push Task ke Local Run Queue Worker] ──(Penuh?)──► [Push ke Global Queue]
                │
                ▼
  [Worker Loop: Eksekusi Task.poll()]
                │
         ┌──────┴──────────────────────┐
         ▼                             ▼
  [Poll::Ready(val)]            [Poll::Pending]
         │                             │
   [Task Selesai]         [Daftarkan Waker ke Reactor/Timer]
   [Jalankan Drop]                     │
                                [Thread Beralih ke Task Lain]
                                       │
                        (Event Ready via epoll / Timer Expire)
                                       │
                                [waker.wake()]
                                       │
                                       ▼
                       [Re-enqueue Task ke Local Run Queue]
```

1. **Task Instantiation**: Pengembang memanggil `tokio::spawn(future)`. Tokio mengalokasikan task header di heap dan membungkus future ke dalam struct internal `Task`.
2. **Enqueueing**: Runtime memasukkan task ke LIFO slot thread saat ini. Jika LIFO terisi, item sebelumnya didorong ke Local Run Queue (kapasitas 256). Jika Local Run Queue penuh, separuh isi queue dipindahkan secara batch ke Global Injector Queue untuk mereduksi overhead lock.
3. **Polling Loop**: Worker thread mengambil task dan mengeksekusi method `Future::poll(Pin<&mut Self>, &mut Context<'_>)`. Context menyediakan akses ke `&Waker`.
4. **I/O Subscription**: Jika future membaca TCP socket yang belum memiliki buffer:
   - Method `poll_read` pada socket mengembalikan `Poll::Pending`.
   - Driver I/O mendaftarkan token FD socket dan mengikat `Waker` task tersebut ke table internal Mio.
5. **Execution Suspension**: Worker thread menyimpan status state-machine task, keluar dari `poll()`, dan segera memproses task berikutnya dari queue. Tidak ada worker thread yang tidur (sleep) selama antrean masih memiliki pekerjaan.
6. **Kernel Notification**: Kernel mendeteksi paket masuk pada socket, memicu `epoll_wait` mengembalikan readiness event.
7. **Wake-up Trigger**: Driver reactor mengidentifikasi FD yang siap, mengambil `Waker`, dan memanggil fungsi `wake()`.
8. **Rescheduling**: Task dialihkan kembali ke status Runnable dan didorong ke antrean run queue worker untuk dipoll kembali hingga mencapai `Poll::Ready`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Bintang Lima
- **OS Threads (Thread-per-core)**: Restoran mempekerjakan 1 koki untuk 1 meja pelanggan. Koki berdiri diam di depan kompor menunggu air mendidih selama 10 menit tanpa melakukan apa pun. Ketika ada 1.000 pelanggan, restoran harus menggaji 1.000 koki. Restoran bangkrut karena kehabisan ruang dan biaya (*Thread exhaustion*).
- **Tokio Runtime Multi-thread**: Restoran modern hanya mempekerjakan sejumlah koki terlatih sesuai jumlah kompor fisik (misal 8 koki untuk 8 core CPU).
  - Setiap koki memiliki papan pesanan pribadi berkapasitas 256 tiket (**Local Run Queue**).
  - Koki meletakkan panci berisi air di atas kompor otomatis (**Mio Reactor**), menyetel alarm sensor (**Waker**), lalu langsung beralih memotong daging pesanan lain.
  - Jika koki 1 kehabisan pekerjaan di papannya, ia melirik papan koki 2 dan mengambil separuh dari tiket koki 2 (**Work Stealing**).
  - Ketika air mendidih, sensor berbunyi (**epoll event notification**), tiket air mendidih dikembalikan ke papan koki untuk diseduh dengan pasta (**waker.wake()**).

#### Diagram Status Task dan Work-Stealing Mechanics

```
Worker Thread A                              Worker Thread B
+------------------------------------+       +------------------------------------+
| Local Run Queue (256 slots)        |       | Local Run Queue (256 slots)        |
| [Task 1][Task 2][Task 3]           |       | [KOSONG]                           |
+------------------------------------+       +------------------------------------+
| LIFO Slot: [Task 0]                |       | LIFO Slot: [KOSONG]                |
+------------------------------------+       +------------------------------------+
  │                                            │
  │ Sedang mengeksekusi Task 0                 │ Mencari pekerjaan...
  │                                            │
  │                                            ├──► 1. Cek LIFO Slot (Kosong)
  │                                            ├──► 2. Cek Local Queue (Kosong)
  │                                            └──► 3. STEAL ATTEMPT!
  │                                                    │
  │                Steal 50% Task                      │
  │ ◄──────────────────────────────────────────────────┘
  ▼
Mengirim [Task 2, Task 3] ───────────────────► Disalin ke Local Queue Worker B
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Pinning Struktural dan Manual Future
Contoh implementasi `Future` manual dengan pelacakan timer dan implementasi `Pin` struktural menggunakan pustaka standar.

```rust
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use std::time::{Duration, Instant};

pub struct AsyncDelay {
    deadline: Instant,
}

impl AsyncDelay {
    pub fn new(duration: Duration) -> Self {
        Self {
            deadline: Instant::now() + duration,
        }
    }
}

impl Future for AsyncDelay {
    type Output = &'static str;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        if Instant::now() >= self.deadline {
            Poll::Ready("Delay selesai: Deadline tercapai")
        } else {
            // Dapatkan waker untuk menjadwalkan polling kembali
            let waker = cx.waker().clone();
            let remaining = self.deadline - Instant::now();

            // Mensimulasikan notifikasi timer eksternal menggunakan OS thread sementara
            // Dalam engine Tokio murni, ini ditangani langsung oleh internal Timer Wheel
            std::thread::spawn(move || {
                std::thread::sleep(remaining);
                waker.wake();
            });

            Poll::Pending
        }
    }
}

#[tokio::main]
async fn main() {
    println!("[Main] Memulai timer asinkron manual...");
    let delay = AsyncDelay::new(Duration::from_millis(500));
    let result = delay.await;
    println!("[Main] Hasil: {}", result);
}
```

#### 7.2. Practical Example: Enterprise Actor Pattern dengan Backpressure & Structured Concurrency
Implementasi actor stateful untuk sistem pemrosesan pesanan finansial dengan backpressure channel, cancellation token, dan penanganan graceful shutdown yang aman.

```rust
use std::collections::HashMap;
use std::time::Duration;
use tokio::sync::{mpsc, oneshot};
use tokio_util::sync::CancellationToken;
use tracing::{error, info, warn};

#[derive(Debug)]
pub struct Order {
    pub id: String,
    pub symbol: String,
    pub amount: f64,
}

#[derive(Debug)]
pub enum OrderCommand {
    ProcessOrder {
        order: Order,
        responder: oneshot::Sender<Result<String, String>>,
    },
    GetMetrics {
        responder: oneshot::Sender<HashMap<String, u64>>,
    },
}

pub struct OrderActor {
    receiver: mpsc::Receiver<OrderCommand>,
    order_counts: HashMap<String, u64>,
    cancel_token: CancellationToken,
}

impl OrderActor {
    pub fn new(
        receiver: mpsc::Receiver<OrderCommand>,
        cancel_token: CancellationToken,
    ) -> Self {
        Self {
            receiver,
            order_counts: HashMap::new(),
            cancel_token,
        }
    }

    pub async fn run(mut self) {
        info!("Actor: Menjalankan loop worker actor");
        loop {
            tokio::select! {
                biased; // Memastikan evaluasi pembatalan prioritas utama

                _ = self.cancel_token.cancelled() => {
                    info!("Actor: Sinyal pembatalan diterima, memulai proses drain queue...");
                    self.drain().await;
                    break;
                }
                maybe_cmd = self.receiver.recv() => {
                    match maybe_cmd {
                        Some(cmd) => self.handle_command(cmd).await,
                        None => {
                            info!("Actor: Channel ditutup oleh produser. Menghentikan loop.");
                            break;
                        }
                    }
                }
            }
        }
        info!("Actor: Loop runtime actor resmi ditutup.");
    }

    async fn handle_command(&mut self, cmd: OrderCommand) {
        match cmd {
            OrderCommand::ProcessOrder { order, responder } => {
                // Simulasi validasi pesanan
                if order.amount <= 0.0 {
                    let _ = responder.send(Err("Nilai transaksi tidak valid".to_string()));
                    return;
                }

                *self.order_counts.entry(order.symbol.clone()).or_insert(0) += 1;
                let tx_hash = format!("TX-{}-OK", order.id);

                // Simulasi pemrosesan I/O non-blocking
                tokio::time::sleep(Duration::from_millis(5)).await;

                let _ = responder.send(Ok(tx_hash));
            }
            OrderCommand::GetMetrics { responder } => {
                let _ = responder.send(self.order_counts.clone());
            }
        }
    }

    async fn drain(&mut self) {
        self.receiver.close();
        while let Some(cmd) = self.receiver.recv().await {
            match cmd {
                OrderCommand::ProcessOrder { responder, .. } => {
                    let _ = responder.send(Err("Sistem shutdown: Transaksi dibatalkan".to_string()));
                }
                OrderCommand::GetMetrics { responder } => {
                    let _ = responder.send(self.order_counts.clone());
                }
            }
        }
        info!("Actor: Seluruh buffer antrean berhasil di-drain.");
    }
}

// Actor Handle Wrapper untuk Client Abstraction
#[derive(Clone)]
pub struct OrderActorHandle {
    sender: mpsc::Sender<OrderCommand>,
}

impl OrderActorHandle {
    pub fn new(sender: mpsc::Sender<OrderCommand>) -> Self {
        Self { sender }
    }

    pub async fn submit_order(&self, order: Order) -> Result<String, String> {
        let (tx, rx) = oneshot::channel();
        let cmd = OrderCommand::ProcessOrder {
            order,
            responder: tx,
        };

        self.sender
            .send(cmd)
            .await
            .map_err(|_| "Gagal mengirim command ke Actor: Queue ditutup".to_string())?;

        rx.await
            .map_err(|_| "Actor drop response channel secara prematur".to_string())?
    }

    pub async fn get_metrics(&self) -> Result<HashMap<String, u64>, String> {
        let (tx, rx) = oneshot::channel();
        self.sender
            .send(OrderCommand::GetMetrics { responder: tx })
            .await
            .map_err(|_| "Gagal mengirim command metrics".to_string())?;

        rx.await
            .map_err(|_| "Actor drop response metrics".to_string())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    // Channel berukuran pasti (bounded) untuk mencegah OOM via backpressure
    let (tx, rx) = mpsc::channel::<OrderCommand>(100);
    let cancel_token = CancellationToken::new();

    let actor = OrderActor::new(rx, cancel_token.clone());
    let handle = OrderActorHandle::new(tx);

    let actor_task = tokio::spawn(async move {
        actor.run().await;
    });

    // Simulasi traffic konkuren dari multi-task
    let mut client_tasks = Vec::new();
    for i in 1..=5 {
        let h = handle.clone();
        let task = tokio::spawn(async move {
            let res = h
                .submit_order(Order {
                    id: format!("ORD-{:04}", i),
                    symbol: "BTCUSDT".to_string(),
                    amount: 1.5 * (i as f64),
                })
                .await;
            info!("[Client {}] Response: {:?}", i, res);
        });
        client_tasks.push(task);
    }

    for task in client_tasks {
        let _ = task.await;
    }

    let metrics = handle.get_metrics().await?;
    info!("Snapshot Metrik: {:?}", metrics);

    // Memicu Graceful Shutdown
    info!("Memicu Graceful Shutdown Actor...");
    cancel_token.cancel();

    // Menunggu actor selesai sepenuhnya
    actor_task.await?;
    info!("Sistem integrasi berhasil dihentikan secara bersih.");

    Ok(())
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform broker valuta asing memproses *tick data* transaksi real-time dengan target throughput **150.000 events/detik**. Arsitektur lama berbasis blocking threads mengalami masalah:
1. **Thread Pool Saturation & Latency Spikes**: Latensi p99 melonjak dari 4ms menjadi 1.200ms ketika volume transaksi pasar melonjak tajam (*high market volatility*).
2. **Memory Overhead**: Setiap thread OS mengonsumsi 2MB stack space. 25.000 koneksi WebSocket konkuren menghabiskan >50GB RAM hanya untuk alokasi thread stack.
3. **Cascading Failure**: Terjadi blocking pada worker database relational yang menyeret seluruh thread I/O pool menjadi starvation.

#### Solusi Arsitektur Menggunakan Tokio Runtime
Tim Core Infrastructure merombak total ingestion gateway menggunakan Tokio dengan arsitektur multi-layer terisolasi:

```
[Koneksi Klien (150K WS)] 
           │
           ▼
+-------------------------------------------------------------------+
|  FRONTEDGE TIER: Tokio Multi-Thread Runtime (IO & WebSocket)      |
|  - Thread Worker = Jumlah Core CPU (misal 32 Core)                |
|  - Frame Parsing: Zero-copy menggunakan bytes::BytesMut           |
|  - Rate-Limiting: TokenBucket per connection                      |
+-------------------------------------------------------------------+
           │
           │ (Bounded Channel mpsc: 50.000 buffer)
           ▼
+-------------------------------------------------------------------+
|  ROUTER TIER: Ring-Buffer Sharded Pipeline                        |
|  - Sharding key: AccountID / Pair Symbol Hash                     |
|  - Tidak ada Cross-Thread Lock Contention                         |
+-------------------------------------------------------------------+
           │
           │ (Flume / Crossbeam Bounded Ring Buffer)
           ▼
+-------------------------------------------------------------------+
|  PERSISTENCE TIER: Dedicated Blocking Pool                        |
|  - Dijalankan di tokio::task::spawn_blocking terisolasi           |
|  - Connection pooling (bb8/deadpool) khusus DB writer             |
+-------------------------------------------------------------------+
```

#### Hasil Metrik Produksi (Benchmark Hasil Migrasi)

| Metrik Operasional | Sistem Lama (Thread-per-core) | Arsitektur Baru (Tokio Engine) | Efisiensi |
| :--- | :--- | :--- | :--- |
| **Max Throughput** | 22.000 events/detik | 185.000 events/detik | **8.4x Peningkatan** |
| **P99.9 Latency** | 1.450 ms | 6.2 ms | **Pangkas latensi 99.5%** |
| **Memory Utilization** | 64 GB RAM | 3.8 GB RAM | **Reduksi memori ~94%** |
| **CPU Context Switches**| ~450.000 / detik | ~12.000 / detik | **Penurunan beban OS drastis** |

---

### 9. Trade-offs

| Dimensi | Menggunakan Tokio Multi-Threaded | Menggunakan Single-Thread / Local Set | Menggunakan Pure Sync Threads (`std::thread`) |
| :--- | :--- | :--- | :--- |
| **Throughput Konkuren** | Ekstrem Tinggi (optimal untuk ratusan ribu I/O connection). | Sedang-Tinggi (hanya memanfaatkan 1 core CPU). | Rendah-Sedang (dibatasi overhead memory stack dan context switch kernel). |
| **Predictable P99 Latency**| Sedang (kemungkinan fluktuasi akibat work-stealing & yield budgeting). | Sangat Tinggi (tidak ada contention antar-core, tidak ada lock thread). | Sangat Tinggi (jika thread dipin ke CPU core via affinity mask). |
| **Kompleksitas Kode** | Kompleks (harus menangani `Send`, `Sync`, lifetimes `'static`, dan safe pinning). | Sedang (tipe tidak wajib `Send`, aman menggunakan `Rc` dan `RefCell`). | Sederhana (alur prosedural linier, minim boilerplate async). |
| **Debugging & Profiling** | Sulit (stack trace terpecah di berbagai poll cycle dan thread worker). | Mudah-Sedang (eksekusi terlokalisasi di satu thread). | Sangat Mudah (standard gdb, lldb, pprof stack trace utuh). |
| **CPU-Bound Processing** | Buruk jika dicampur dalam worker async (membutuhkan `spawn_blocking`). | Sangat Buruk (memblokir seluruh reactor event loop). | Sangat Baik (arsitektur komputasi paralel intensif native). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal 1: Menjalankan Blocking Code di Thread Worker Tokio
*Gejala*: Seluruh server berhenti merespons permintaan baru. Metrik CPU worker tiba-tiba 100% pada satu core sementara throughput I/O jatuh ke 0.
*Penyebab*: Memanggil fungsi tersinkronisasi (blocking) seperti `std::thread::sleep`, query database blocking (`diesel` sync), atau parsing JSON berukuran raksasa di dalam async fn.

```rust
// ❌ ANTI-PATTERN: Menghancurkan throughput worker Tokio
async fn process_data_bad() {
    // Memblokir worker thread OS! 256 task lain di queue worker ini akan starve!
    std::thread::sleep(Duration::from_secs(2)); 
}

// ✅ PRODUCTION FIX: Alihkan ke dedicated blocking thread pool
async fn process_data_good() {
    tokio::task::spawn_blocking(|| {
        // Dijalankan di thread pool khusus non-async, aman dari starvation Tokio worker
        std::thread::sleep(Duration::from_secs(2));
    }).await.expect("Task blocking panic");
}
```

#### 10.2. Kesalahan Fatal 2: Memory Leak akibat Unbounded Channel
*Gejala*: Memory RSS proses naik secara konstan tanpa batas (*Out of Memory* / OOM crash) saat downstream lambat.
*Penyebab*: Penggunaan `tokio::sync::mpsc::unbounded_channel()`.

```rust
// ❌ ANTI-PATTERN: Rentan OOM Crash saat load spike
let (tx, mut rx) = mpsc::unbounded_channel();

// ✅ PRODUCTION FIX: Gunakan Bounded Channel dan terapkan Backpressure eksplisit
let (tx, mut rx) = mpsc::channel(10_000); // Batas aman kapasitas buffer
// Saat buffer penuh, pemanggilan `tx.send(val).await` akan menahan pengirim (backpressure)
```

#### 10.3. Kesalahan Fatal 3: Cancellation Safety Violation pada `tokio::select!`
*Gejala*: Data transaksi korup sebagian (misal: 4 byte pertama dari frame protokol 8 byte terbaca, sisanya hilang).
*Penyebab*: Menggunakan future yang tidak aman terhadap pembatalan (*not cancellation safe*) di dalam cabang `tokio::select!`.

```rust
// ❌ ANTI-PATTERN: `AsyncReadExt::read_exact` TIDAK cancellation safe!
tokio::select! {
    res = socket.read_exact(&mut buf) => {
        // Jika cabang timeout di bawah menang saat `read_exact` baru membaca sebagian data,
        // sisa byte yang telah dibaca dari buffer kernel HILANG PERMANEN!
    }
    _ = tokio::time::sleep(Duration::from_millis(100)) => {
        println!("Timeout terpicu, state socket kini korup!");
    }
}

// ✅ PRODUCTION FIX: Gunakan struktur framing yang persisten seperti FramedRead / BytesMut
```

#### 10.4. Kesalahan Fatal 4: Menahan Mutex Guard Melintasi Titik `.await`
*Gejala*: Compiler error: `the trait 'Send' is not implemented for 'std::sync::MutexGuard'`.
*Penyebab*: Memegang lock standard library `std::sync::Mutex` melintasi suspension point `.await`. Tokio worker thread lain tidak dapat mencuri task tersebut karena pointer guard thread-bound.

```rust
// ❌ ANTI-PATTERN:
use std::sync::Mutex;
async fn bad_mutex_use(lock: &Mutex<u64>) {
    let mut guard = lock.lock().unwrap();
    tokio::time::sleep(Duration::from_millis(10)).await; // ERROR KOMPILASI
    *guard += 1;
}

// ✅ PRODUCTION FIX: Batasi scope lock sinkron ATAU gunakan tokio::sync::Mutex
async fn good_mutex_use(lock: &std::sync::Mutex<u64>) {
    {
        let mut guard = lock.lock().unwrap();
        *guard += 1;
    } // Guard di-drop sebelum titik suspensi .await
    tokio::time::sleep(Duration::from_millis(10)).await;
}
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Channel Allocation Rule**: Dilarang menggunakan `mpsc::unbounded_channel` pada seluruh jalur transmisi data produksi. Tetapkan buffer limit berbasis throughput p99.
2. [ ] **Cancellation Safety Audit**: Setiap pemanggilan future di dalam macro `tokio::select!` harus diaudit melalui dokumentasi resmi Tokio untuk memastikan sifat *cancellation safe*.
3. [ ] **Blocking Isolation**: Semua operasi komputasi berat (> 10-100 mikrodetik) atau syscall I/O sinkron wajib diisolasi menggunakan `tokio::task::spawn_blocking`.
4. [ ] **Structured Graceful Shutdown**: Selalu gunakan hierarchical `tokio_util::sync::CancellationToken` atau `tokio::sync::broadcast` untuk koordinasi shutdown. Hindari pemanggilan `std::process::exit` mendadak yang membatalkan eksekusi destructor (`Drop`).
5. [ ] **Runtime Thread Sizing**: Konfigurasikan worker pool thread secara eksplisit menggunakan builder pattern:
   ```rust
   tokio::runtime::Builder::new_multi_thread()
       .worker_threads(num_cpus::get())
       .enable_all()
       .max_blocking_threads(512)
       .build()?;
   ```
6. [ ] **Observability Instrumentation**: Seluruh spawn task level atas wajib diinstrumentasi dengan macro `tracing::instrument` untuk pelacakan context span asinkron melintasi thread boundary.

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum berstandar produksi berikut pada direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Project dan Dependency Tree
Buat folder dan file konfigurasi `hands-on/m02/Cargo.toml`:

```toml
[package]
name = "tokio-advanced-production"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.38", features = ["full", "tracing"] }
tokio-util = { version = "0.7", features = ["sync"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["fmt", "env-filter"] }
thiserror = "1.0"
bytes = "1.6"
```

#### Langkah 2: Implementasi Production Engine
Tuliskan source code berikut pada `hands-on/m02/src/main.rs`:

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{mpsc, oneshot};
use tokio::time::{sleep, timeout};
use tokio_util::sync::CancellationToken;
use tracing::{error, info, warn, Instrument};

#[derive(Debug, thiserror::Error)]
pub enum PipelineError {
    #[error("Kapasitas antrean overload (Backpressure limit reached)")]
    QueueOverload,
    #[error("Operasi task timeout: {0}")]
    Timeout(String),
    #[error("Internal worker error: {0}")]
    Internal(String),
}

#[derive(Debug)]
pub struct WorkItem {
    pub id: usize,
    pub payload: String,
    pub response: oneshot::Sender<Result<String, PipelineError>>,
}

pub struct MetricsTracker {
    pub total_processed: AtomicUsize,
    pub dropped_jobs: AtomicUsize,
}

pub struct ProductionIngestionEngine {
    tx: mpsc::Sender<WorkItem>,
    cancel_token: CancellationToken,
    metrics: Arc<MetricsTracker>,
}

impl ProductionIngestionEngine {
    pub fn new(capacity: usize, num_workers: usize) -> (Self, tokio::task::JoinHandle<()>) {
        let (tx, rx) = mpsc::channel::<WorkItem>(capacity);
        let cancel_token = CancellationToken::new();
        let metrics = Arc::new(MetricsTracker {
            total_processed: AtomicUsize::new(0),
            dropped_jobs: AtomicUsize::new(0),
        });

        let rx = Arc::new(tokio::sync::Mutex::new(rx));
        let engine_metrics = Arc::clone(&metrics);
        let engine_token = cancel_token.clone();

        // Supervisor task yang mengelola worker threads
        let supervisor = tokio::spawn(async move {
            info!("Supervisor: Menginisialisasi {} worker pool...", num_workers);
            let mut worker_handles = Vec::with_capacity(num_workers);

            for worker_id in 0..num_workers {
                let rx_clone = Arc::clone(&rx);
                let token_clone = engine_token.clone();
                let metrics_clone = Arc::clone(&engine_metrics);

                let handle = tokio::spawn(
                    async move {
                        info!("Worker-{}: Aktif dan siap menerima beban kerja", worker_id);
                        loop {
                            tokio::select! {
                                biased;
                                _ = token_clone.cancelled() => {
                                    info!("Worker-{}: Menerima shutdown signal. Mengakhiri loop.", worker_id);
                                    break;
                                }
                                maybe_job = async {
                                    let mut locked_rx = rx_clone.lock().await;
                                    locked_rx.recv().await
                                } => {
                                    match maybe_job {
                                        Some(item) => {
                                            Self::process_job(worker_id, item, &metrics_clone).await;
                                        }
                                        None => {
                                            info!("Worker-{}: Antrean closed. Keluar.", worker_id);
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    .instrument(tracing::info_span!("Worker", id = worker_id)),
                );
                worker_handles.push(handle);
            }

            // Menunggu seluruh worker selesai memproses shutdown
            for h in worker_handles {
                let _ = h.await;
            }
            info!("Supervisor: Seluruh worker pool telah berhenti secara aman.");
        });

        (
            Self {
                tx,
                cancel_token,
                metrics,
            },
            supervisor,
        )
    }

    async fn process_job(worker_id: usize, item: WorkItem, metrics: &MetricsTracker) {
        // Simulasi beban pemrosesan I/O non-blocking
        sleep(Duration::from_millis(50)).await;

        metrics.total_processed.fetch_add(1, Ordering::Relaxed);
        let result = Ok(format!("Worker-{}: Data {} berhasil diproses", worker_id, item.id));
        let _ = item.response.send(result);
    }

    pub async fn submit(
        &self,
        id: usize,
        payload: String,
        req_timeout: Duration,
    ) -> Result<String, PipelineError> {
        let (resp_tx, resp_rx) = oneshot::channel();
        let item = WorkItem {
            id,
            payload,
            response: resp_tx,
        };

        // Menerapkan non-blocking check atau timeout pada proses enqueueing (Backpressure)
        self.tx
            .try_send(item)
            .map_err(|_| PipelineError::QueueOverload)?;

        match timeout(req_timeout, resp_rx).await {
            Ok(Ok(inner_res)) => inner_res,
            Ok(Err(_)) => Err(PipelineError::Internal("Worker dropped channel".into())),
            Err(_) => {
                self.metrics.dropped_jobs.fetch_add(1, Ordering::Relaxed);
                Err(PipelineError::Timeout("Permintaan SLA terlampaui".into()))
            }
        }
    }

    pub fn shutdown(&self) {
        info!("Engine: Mengirimkan shutdown signal ke seluruh komponen...");
        self.cancel_token.cancel();
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    info!("=== Memulai Sistem Produksi Tokio Engine ===");

    // Inisialisasi engine: kapasitas antrean 20 item, 4 worker tasks
    let (engine, supervisor_handle) = ProductionIngestionEngine::new(20, 4);

    let mut client_handles = Vec::new();

    // Spawn 30 request konkuren untuk memvalidasi kapasitas backpressure queue (kapasitas 20)
    for i in 1..=30 {
        let eng = &engine;
        let job = async move {
            match eng
                .submit(i, format!("Payload Data {}", i), Duration::from_millis(300))
                .await
            {
                Ok(resp) => info!("[Request Success] ID: {} -> {}", i, resp),
                Err(e) => warn!("[Request Failed] ID: {} -> Alasan: {}", i, e),
            }
        };
        client_handles.push(job);
    }

    // Eksekusi seluruh client requests secara paralel
    futures::future::join_all(client_handles).await;

    // Evaluasi Metrik Sementara
    info!(
        "Status Metrik: Berhasil Diproses = {}, Drop/Overload = {}",
        engine.metrics.total_processed.load(Ordering::SeqCst),
        engine.metrics.dropped_jobs.load(Ordering::SeqCst)
    );

    // Memicu Graceful Shutdown
    sleep(Duration::from_millis(100)).await;
    engine.shutdown();

    // Tunggu supervisor selesai
    let _ = supervisor_handle.await;
    info!("=== Seluruh Siklus Hidup Engine Berhasil Diselesaikan ===");

    Ok(())
}
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan di shell:
```bash
cargo run
```

---

### 13. Exercise

#### Level Easy
**Tugas**: Buat fungsi `async fn fetch_with_retry<F, Fut, T, E>(mut f: F, max_retries: usize, base_delay: Duration) -> Result<T, E>` yang mengeksekusi future factory `f` dengan algoritma *exponential backoff delay* jika terjadi error.
**Kriteria**: Harus menggunakan `tokio::time::sleep` dan melipatgandakan nilai delay pada setiap kegagalan hingga iterasi `max_retries` habis.

#### Level Medium
**Tugas**: Implementasikan pembatas laju konkurensi (Concurrency Limiter) menggunakan `Arc<tokio::sync::Semaphore>`.
**Kriteria**: Buat 50 task dummy yang melakukan I/O simulasi selama 100ms, namun batasi konkurensi maksimum yang dapat berjalan bersamaan hanya 5 task. Task ke-6 dan seterusnya harus menunggu (*wait non-blockingly*) hingga permit semaphore dirilis.

#### Level Hard
**Tugas**: Bangun Custom Dynamic Priority Queue Channel.
**Kriteria**:
1. Buat tipe data channel asinkron yang mendukung dua tingkat prioritas: `High` dan `Normal`.
2. Jika ada item pada antrean `High`, task worker penerima (`recv().await`) wajib memproses seluruh pesan `High` terlebih dahulu sebelum mengonsumsi pesan `Normal`.
3. Implementasikan menggunakan primitive `tokio::sync::Notify` dan standard library collections yang dilindungi mutex asinkron atau lock-free atomic queues secara murni tanpa polling loop sibuk (*busy-wait*).

---

### 14. Challenge

**Skenario**: Anda adalah Lead Architect pada sistem Multi-Exchange Arbitrage Engine. Engine menerima stream book ticker dari 10 cryptocurrency exchange melalui koneksi WebSocket terpisah secara simultan.

**Persyaratan Sistem**:
1. **Zero Message Loss pada Network Hiccup**: Jika koneksi salah satu exchange terputus, komponen reader exchange tersebut harus melakukan reconnect otomatis dengan jittered exponential backoff tanpa memblokir pembacaan 9 exchange lainnya.
2. **Aggregated Tick Window**: Buat modul komparasi harga yang menerima stream dari seluruh connection workers, lalu memancarkan (*broadcast*) peluang arbitrase jika terdapat spread harga > 0.15% antar-exchange dalam window interval 10ms.
3. **Structured Shutdown via Signal Handler**: Sistem harus mendengarkan signal OS `SIGINT` (Ctrl+C) atau `SIGTERM`. Saat signal diterima, gateway dilarang menerima event baru, menyelesaikan kalkulasi event yang sudah berada di ring buffer, lalu menutup seluruh koneksi TCP socket secara rapi dengan timeout maksimal 2.0 detik.
4. **No-Alloc Hot-path**: Optimalkan pipeline pemrosesan tick agar tidak mengalokasikan memori baru di heap pada hot-path per-tick (gunakan byte-buffer static/pre-allocated pools atau stack allocation).

*Waktu Penyelesaian*: 4-6 Jam.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa perbedaan mendasar antara `tokio::spawn` dan pemanggilan method `.await` secara langsung?**
   - *Jawaban*: `tokio::spawn` mendaftarkan future sebagai task independen baru ke scheduler Tokio runtime untuk dieksekusi secara konkuren di atas worker pool (mengembalikan `JoinHandle`), sedangkan `.await` mengeksekusi future di dalam konteks task pemanggil saat ini secara berurutan (*in-line*).
2. **Mengapa auto-trait `Send` wajib diimplementasikan oleh sebuah future yang dipass ke `tokio::spawn` pada multi-threaded runtime?**
   - *Jawaban*: Karena scheduler Tokio menerapkan algoritma *work-stealing*. Task yang dimulai di Worker Thread A dapat dipindahkan dan dieksekusi kelanjutannya di Worker Thread B setelah suspensi I/O. Seluruh data yang ditampung oleh future state machine harus aman dipindahkan antar-thread OS (`Send`).
3. **Apa fungsi utama dari `Pin` pada async Rust?**
   - *Jawaban*: Untuk mengunci alamat memori dari sebuah nilai agar tidak berpindah posisi (*immovable*), mencegah invalidasi internal pointer pada struktur data self-referential yang di-generate oleh compiler saat mengompilasi blok async state machine.
4. **Apa yang terjadi secara internal ketika method `poll()` mengembalikan nilai `Poll::Pending`?**
   - *Jawaban*: Runtime worker thread mengetahui bahwa resource belum siap. Worker melepaskan task tersebut dari LIFO/thread stack, beralih mengerjakan task lain, dan mengandalkan `Waker` yang telah didaftarkan ke reactor untuk menjadwalkan ulang task tersebut ketika data tersedia.
5. **Mengapa `std::thread::sleep` dilarang keras digunakan di dalam fungsi `async` pada Tokio?**
   - *Jawaban*: Karena `std::thread::sleep` memblokir seluruh native thread OS worker yang sedang mengeksekusinya. Seluruh task asinkron lain (hingga 256 task) yang berada di antrean local run queue worker tersebut akan membeku (*starvation*).

#### Bagian 2: Intermediate (5 Soal)
6. **Bagaimana Tokio mencegah starvation pada Global Injector Queue di tengah tingginya beban Local Run Queue?**
   - *Jawaban*: Tokio menerapkan counter berbasis tick. Setiap 61 iterasi (tick) polling task lokal, worker thread dipaksa memeriksa dan memprioritaskan pengambilan task dari Global Queue terlebih dahulu sebelum melanjutkan mengonsumsi Local Run Queue.
7. **Apa konsep "Cooperative Budget" (Budget 128) di Tokio dan bagaimana cara kerjanya?**
   - *Jawaban*: Setiap task diberi jatah 128 unit komputasi. Setiap kali task berinteraksi dengan resource internal Tokio (seperti read/write socket), budget berkurang 1 unit. Ketika budget 0, resource mengembalikan `Poll::Pending` semu dan memanggil `waker.wake()`, memaksa task melepaskan CPU thread secara sukarela (*yield*) untuk task lain.
8. **Jelaskan risiko penggunaan macro `tokio::select!` terhadap operasi buffer I/O yang tidak cancellation safe!**
   - *Jawaban*: Jika sebuah future di-drop di tengah jalan karena cabang lain pada `select!` selesai lebih dulu, proses I/O yang baru membaca sebagian byte akan terhenti dan sisa byte yang telah dibaca dari kernel buffer akan musnah, menyebabkan stream data berikutnya korup secara permanen.
9. **Apa perbedaan struktural dan penggunaan antara `tokio::sync::oneshot` dan `tokio::sync::mpsc`?**
   - *Jawaban*: `oneshot` dioptimalkan secara presisi untuk transmisi satu nilai tunggal dari satu producer ke satu consumer (biasa untuk pola request-response), sedangkan `mpsc` (*Multi-Producer Single-Consumer*) dirancang untuk aliran data (*stream*) berkelanjutan dari banyak pengirim ke satu antrean pemroses.
10. **Bagaimana cara kerja integrasi Mio dengan kernel multiplexing OS (seperti Linux `epoll`)?**
    - *Jawaban*: Mio menyetel socket ke mode non-blocking (`O_NONBLOCK`) dan mendaftarkan file descriptor ke epoll instance melalui `epoll_ctl` dengan mode Edge-Triggered (`EPOLLET`). Ketika event ready diterima melalui `epoll_wait`, Mio mengekstrak token yang sesuai dan memanggil callback waker Tokio untuk mengembalikan task ke runnable state.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Sebuah microservice gateway mengalami peningkatan memori (RAM leak) secara berkala setiap kali upstream database mengalami latensi tinggi, hingga akhirnya proses dihentikan oleh OS Linux OOM Killer. Setelah kode diaudit, komunikasi antar modul menggunakan channel asinkron.
    - *Identifikasi Akar Masalah*: Layanan menggunakan `tokio::sync::mpsc::unbounded_channel()`. Saat database lambat, consumer channel memproses pesan lebih lambat daripada laju request masuk, menyebabkan jutaan objek tertimbun di buffer memori channel tanpa batas.
    - *Solusi Remediasi*: Ubah channel menjadi `tokio::sync::mpsc::channel(N)` dengan kapasitas N yang terukur, dan terapkan backpressure (misalnya mengembalikan status HTTP 429 Too Many Requests jika `try_send()` gagal atau menahan socket incoming read menggunakan `send().await`).

12. **Skenario 2**: Sebuah aplikasi finansial memiliki latency P99 sebesar 2 milidetik pada beban normal. Namun, setiap 10 menit sekali, latensi melonjak menjadi 3.500 milidetik selama 5 detik, padahal volume request stabil. Investigasi menemukan ada proses dumping cache ke disk via `std::fs::write` di dalam salah satu async function.
    - *Identifikasi Akar Masalah*: Pemanggilan syscall `std::fs::write` adalah operasi blocking synchronous. Operasi ini memonopoli thread worker Tokio selama beberapa detik saat OS melakukan disk write flush, membekukan eksekusi seluruh network packet processing task yang terjebak di antrean worker tersebut.
    - *Solusi Remediasi*: Ganti operasi disk I/O menggunakan `tokio::fs::write` yang non-blocking, atau bungkus operasi synchronous tersebut di dalam `tokio::task::spawn_blocking(move || std::fs::write(...))`.

13. **Skenario 3**: Anda mengimplementasikan graceful shutdown pada server TCP menggunakan `CancellationToken`. Namun, saat container Kubernetes mengirim sinyal `SIGTERM`, proses aplikasi tetap hidup selama 30 detik hingga terkena `SIGKILL` paksa.
    - *Identifikasi Akar Masalah*: Kemungkinan besar terdapat infinite loop pada salah satu background worker yang mengabaikan pengecekan cancellation token, atau ada listener client socket yang terblokir pada operasi read synchronous tanpa timeout/select, atau channel sender clone masih dipegang oleh komponen yang tidak di-drop sehingga consumer `recv()` menunggu data selamanya.
    - *Solusi Remediasi*: Pastikan seluruh child loop menyertakan `tokio::select!` dengan cabang `cancel_token.cancelled()`, close receiver atau drop seluruh instance sender secara eksplisit, dan pasang guard timeout global menggunakan `tokio::time::timeout` saat menunggu `JoinHandle` worker selesai di fungsi shutdown utama.

---

### 16. Summary

- **Tokio Multi-Threaded Engine** mengandalkan arsitektur M:N scheduler berbasis **Work-Stealing Algorithm**, di mana setiap worker thread memiliki Local Run Queue 256 slot, LIFO slot cache-friendly, dan akses terkoordinasi ke Global Injector Queue serta Mio Reactor.
- **Pinning & Safety**: Penulisan Future manual membutuhkan pemahaman mendalam tentang `Pin<&mut T>`, invariant memori, dan auto-trait `Send`/`Sync` guna menjamin keamanan state machine yang self-referential saat context switching antar-worker thread.
- **Enterprise Concurrency Patterns**: Arsitektur asinkron yang tangguh di tingkat industri wajib menerapkan **Backpressure Eksplisit** (Bounded Channels), **Structured Graceful Shutdown** (`CancellationToken`), isolasi **Blocking Thread Pool** (`spawn_blocking`), serta audit **Cancellation Safety** pada seluruh blok `tokio::select!`.
- **Ekosistem Observabilitas**: Operasional skala produksi menuntut instrumentasi tracing kontekstual dan metrik runtime untuk mendeteksi resource starvation, task lock contention, dan anomali latensi p99 secara dini.