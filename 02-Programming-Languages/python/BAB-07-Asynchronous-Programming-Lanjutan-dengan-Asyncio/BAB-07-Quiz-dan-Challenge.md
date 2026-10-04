# BAB 07: Quiz, Challenge, & Knowledge Check
**Asynchronous Programming Lanjutan dengan Asyncio**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Coroutine dan Mekanisme Event Loop**  
   Jelaskan transformasi arsitektural dari *generator-based coroutines* (`yield` / `yield from` via PEP 342 & PEP 380) menuju *native coroutines* (`async` / `await` via PEP 492). Bagaimana Python Runtime membedakan fungsi generator biasa dengan native coroutine, dan bagaimana Event Loop memanfaatkan struktur frame eksekusi coroutine untuk memfasilitasi *cooperative multitasking*?

2. **Concurrency vs Parallelism dalam Ekosistem CPython**  
   Secara default, kode yang berjalan di dalam Event Loop `asyncio` bersifat *single-threaded*. Mengapa sistem asynchronous I/O ini tetap dibatasi oleh Global Interpreter Lock (GIL) ketika mengeksekusi operasi CPU-bound, namun mampu memberikan throughput konkurensi yang sangat tinggi pada I/O-bound tasks dibandingkan threading konvensional?

3. **Anatomi dan Siklus Hidup: Coroutine, Future, dan Task**  
   Bedakan secara hierarkis dan operasional antara objek `Coroutine`, `asyncio.Future`, dan `asyncio.Task`. Pada momen apa sebuah `Future` bertransisi dari status `PENDING` ke `FINISHED` atau `CANCELLED`, dan bagaimana mekanisme *callback chaining* internal (`add_done_callback`) menggerakkan kelanjutan eksekusi coroutine yang sedang di-`await`?

4. **Semantik Cancellation dan Injeksi Exception**  
   Ketika sebuah `Task.cancel()` dipanggil, bagaimana Event Loop menginterupsi eksekusi coroutine yang sedang ditangguhkan (*suspended*)? Jelaskan siklus hidup `asyncio.CancelledError`, dan mengapa menangkap exception ini menggunakan blok `except Exception:` tanpa melakukan re-raise dianggap sebagai *anti-pattern* fatal yang merusak integritas *cancellation protocol*?

5. **Protokol Asynchronous Context Manager dan Iterator**  
   Uraikan spesifikasi internal dari metode `__aenter__` / `__aexit__` serta `__aiter__` / `__anext__`. Apa yang terjadi di balik layar ketika exception dilemparkan di dalam blok `async with`, dan bagaimana nilai kembalian boolean dari `__aexit__` menentukan apakah exception tersebut akan ditekan (*suppressed*) atau dipropagasi ke atas call stack?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Deteksi dan Mitigasi Blocking Calls pada Event Loop**  
   Jika seorang pengembang secara tidak sengaja memanggil fungsi synchronous blocking (seperti `requests.get()` atau `time.sleep()`) di dalam coroutine, apa dampak langsungnya terhadap task-task lain yang terdaftar di Event Loop? Bagaimana cara mengonfigurasi `asyncio` debug mode (`loop.slow_callback_duration`) untuk mendeteksi latensi ini, dan bagaimana `loop.run_in_executor()` bekerja secara internal untuk mengisolasi panggilan tersebut?

2. **Structured Concurrency: `asyncio.gather` vs `asyncio.TaskGroup`**  
   Evaluasi kelemahan desain `asyncio.gather(..., return_exceptions=False)` dalam hal penanganan kegagalan parsial (*orphan tasks* dan *unhandled exceptions*). Mengapa `asyncio.TaskGroup` (diperkenalkan pada Python 3.11) dikategorikan sebagai paradigma *Structured Concurrency*, dan bagaimana `ExceptionGroup` digunakan untuk mengonsolidasi kegagalan konkuren yang terjadi secara simultan?

3. **Isolasi State Menggunakan `contextvars`**  
   Mengapa modul `threading.local()` tidak memadai dan berbahaya jika digunakan untuk menyimpan metadata request (seperti `Trace-ID` atau `Tenant-ID`) di dalam aplikasi asynchronous berbasis `asyncio`? Jelaskan bagaimana mekanisme internal `contextvars` (PEP 567) menyalin context tree saat pembentukan objek `Task` baru (`asyncio.create_task`).

4. **Lifecycle Hazard: Garbage Collection pada "Fire-and-Forget" Tasks**  
   Perhatikan pola: `asyncio.create_task(background_work())` tanpa menyimpan referensi variabel ke objek task tersebut. Mengapa pola ini berisiko memicu bug hening (*silent failure*) di mana task tiba-tiba berhenti dieksekusi di tengah jalan sebelum selesai? Jelaskan keterkaitan antara CPython Reference Counting/Cyclic Garbage Collector dengan lifecycle `Task`.

5. **Anatomi Graceful Shutdown pada Produksi**  
   Saat aplikasi asynchronous menerima sinyal terminasi OS (`SIGINT` atau `SIGTERM`), jelaskan urutan pembongkaran (*teardown sequence*) yang deterministik untuk memastikan tidak ada data in-flight yang korup. Mengapa pemanggilan `loop.close()` secara prematur tanpa melakukan drain pada `asyncio.all_tasks()` dan pembatalan asynchronous generator (`loop.shutdown_asyncgens()`) dapat memicu memory leak atau *dangling socket connections*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike Ekstrem pada High-Throughput API Gateway
Sebuah API Gateway berbasis FastAPI/Asyncio memproses 8.000 req/sec. Tiba-tiba metrik APM menunjukkan P99 latency melonjak dari 12ms menjadi 9.500ms, sementara utilisasi CPU sistem hanya berada di angka 35% dan memory utilization normal. Tidak ada error rate yang meningkat pada upstream microservices.
* **Pertanyaan Diagnostik:**
  1. Hipotesis apa saja yang berpotensi menjadi akar masalah (*root cause*), ditinjau dari interaksi Event Loop dengan CPU-bound serialization (misal: parsing payload JSON berukuran besar) atau I/O blocking tersembunyi?
  2. Langkah telemetri spesifik apa (menggunakan *profiler* async seperti `yappi` atau metrik Event Loop lag) yang harus Anda ambil untuk mengisolasi coroutine yang menahan (*starving*) Event Loop thread?

### Skenario B: Race Condition dan Double-Spending pada Dompet Digital
Layanan pemrosesan transaksi async mengalami insiden di mana sebuah akun dengan saldo Rp 100.000 dapat melakukan dua penarikan dana sebesar Rp 100.000 secara bersamaan (hanya berselisih 5 milidetik), menghasilkan saldo akhir negatif tanpa memicu validasi error. Potongan logika kode:
```python
balance = await db.get_balance(user_id)
if balance >= amount:
    # Terjadi context switch di sini karena operasi I/O latency
    await external_payment_gateway.charge(user_id, amount)
    await db.deduct_balance(user_id, amount)
```
* **Pertanyaan Diagnostik:**
  1. Mengapa sifat *single-threaded* dari `asyncio` sama sekali **tidak menjamin** atomisitas data antar *await points*? Jelaskan konsep *interleaving execution*.
  2. Rancang dua strategi mitigasi: satu di tingkat aplikasi menggunakan primitives `asyncio` (`asyncio.Lock` terdistribusi atau per-key), dan satu di tingkat persistensi data (optimistic/pessimistic locking pada database). Apa trade-off throughput dari masing-masing pendekatan?

### Skenario C: File Descriptor Exhaustion dan OOM pada Mass Web Scraper
Sebuah distributed worker async ditugaskan melakukan scraping terhadap 200.000 URL e-commerce. Pengembang mengimplementasikan task distribution dengan membuat 200.000 coroutine sekaligus dan mengeksekusinya via:
`await asyncio.gather(*[scrape(url) for url in urls])`
Dalam waktu kurang dari 60 detik, worker crash dengan pesan error: `OSError: [Errno 24] Too many open files`, diikuti dengan Linux OOM Killer yang mematikan container.
* **Pertanyaan Diagnostik:**
  1. Jelaskan mekanisme kegagalan sistem terkait konsumsi memori untuk frame coroutine yang tertahan dan saturasi connection socket/file descriptors di level OS kernel.
  2. Rancang ulang arsitektur sistem pipeline ini menggunakan pola *Producer-Consumer* berbasis `asyncio.Queue` dengan *bounded size*, pembatasan konkurensi via `asyncio.Semaphore`, dan implementasi pooling HTTP client sessions.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient Event Dispatcher dengan Backpressure dan Graceful Teardown

#### Problem Statement
Anda diminta merancang komponen inti pemrosesan event stream asynchronous (*in-memory event bus/dispatcher*) untuk platform perbankan. Dispatcher harus menerima event transaksi dari message stream, mendistribusikannya ke beberapa downstream consumer dengan rate-limit tertentu, menangani transient failure menggunakan retry mechanism, dan mampu melakukan shutdown secara elegan tanpa kehilangan event yang sedang diproses saat OS mengirimkan sinyal `SIGINT`.

#### Requirements
1. **Concurrency Control:** Batasi eksekusi downstream request maksimal $N$ worker aktif secara bersamaan menggunakan `asyncio.Semaphore` atau worker pool pattern berbasis `asyncio.Queue`.
2. **Structured Concurrency:** Seluruh worker pool harus dikelola menggunakan `asyncio.TaskGroup` (Python 3.11+) untuk memastikan jika terjadi unhandled crash kritikal, seluruh task saudara (*sibling tasks*) dihentikan secara aman.
3. **Resilience & Backoff:** Implementasikan consumer call yang mensimulasikan I/O latency dengan mekanisme transient failure. Terapkan strategi *exponential backoff with jitter* jika consumer mengembalikan error, dengan batas maksimal 3 kali retry sebelum dimasukkan ke Dead-Letter-Queue (DLQ).
4. **Graceful Teardown Lifecycle:**
   - Tangkap sinyal OS `SIGINT` / `SIGTERM` secara native via `loop.add_signal_handler`.
   - Hentikan penerimaan event baru.
   - Selesaikan pemrosesan event yang sudah berada di dalam buffer/queue (*drain phase*).
   - Batalkan worker yang idling/menggantung dan rilis semua shared resources.

#### Constraints
* Tidak boleh menggunakan library third-party (hanya modul standar library: `asyncio`, `signal`, `random`, `time`, `contextvars`).
* Strict asynchronous non-blocking: Dilarang menggunakan `time.sleep()`, synchronous file I/O, atau pemanggilan library blocking lainnya.
* Gunakan type hinting lengkap (`typing`) sesuai standar production-grade code.

#### Expected Output
Program demonstrasi mandiri (*self-contained script*) yang:
1. Memulai dispatcher dan memproses stream berisi 50 event simulasi.
2. Menampilkan log terstruktur dengan timestamp dan ID task yang mengindikasikan proses konsumsi, retry handling saat downstream failure, serta pemindahan ke DLQ.
3. Menunjukkan eksekusi *graceful shutdown* yang sukses ketika tombol `Ctrl+C` ditekan di tengah eksekusi, dengan log verifikasi bahwa sisa queue telah di-drain dan tidak ada status *Task was destroyed but it was pending!*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan mendasar antara *cooperative multitasking* (`asyncio`) dan *preemptive multitasking* (`threading`).
- [ ] Mekanisme kerja internal Event Loop dalam mengelola I/O Multiplexing primitives (`epoll`, `kqueue`, atau `select`).
- [ ] Peran status `PENDING`, `FINISHED`, dan `CANCELLED` pada objek `asyncio.Future` dan `asyncio.Task`.
- [ ] Bahwa titik `await` (*await point*) adalah satu-satunya tempat di mana eksekusi coroutine dapat ditangguhkan (*yield*) ke coroutine lain.
- [ ] Mengapa penanganan exception di dalam `asyncio.gather` dapat meninggalkan *dangling/orphan tasks* jika salah satu task mengalami failure.
- [ ] Konsep *Structured Concurrency* dan keunggulan deterministik dari `asyncio.TaskGroup` dalam manajemen siklus hidup konkurensi.
- [ ] Mengapa race condition tetap dapat terjadi pada arsitektur asynchronous single-threaded jika shared state dimodifikasi melintasi *await points*.
- [ ] Mekanisme isolasi konteks eksekusi berbasis `contextvars` lintas coroutine task branches.

### Saya tidak perlu menghafal:
- [ ] Detail implementasi C-level internal dari selector polling syscalls pada berbagai kernel OS (`epoll_ctl` vs `kevent`).
- [ ] Nilai numerik konstan internal untuk event loop flags atau low-level opcode CPython (`YIELD_VALUE`, `RETURN_VALUE`).
- [ ] API signature dari fungsi-fungsi `asyncio` lawas yang telah didepresiasi (misal: generator-based `@asyncio.coroutine` atau parameter `loop=` eksplisit di setiap method).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi, mengisolasi, dan memindahkan operasi CPU-bound atau I/O synchronous blocking ke thread/process pool menggunakan `loop.run_in_executor()`.
- [ ] Menerapkan mekanisme rate-limiting dan backpressure menggunakan kombinasi `asyncio.Semaphore` dan `asyncio.Queue(maxsize=...)`.
- [ ] Merancang arsitektur concurrent batch processing yang tangguh menggunakan `asyncio.TaskGroup` dengan penanganan `ExceptionGroup`.
- [ ] Menulis pipeline *graceful shutdown* yang komprehensif untuk menangani OS signal, meng-drain pending tasks, dan membersihkan asynchronous context managers tanpa error leak.
- [ ] Mencegah terjadinya race condition pada shared state menggunakan koordinasi konkurensi yang tepat seperti `asyncio.Lock` atau arsitektur *actor-like state machine*.