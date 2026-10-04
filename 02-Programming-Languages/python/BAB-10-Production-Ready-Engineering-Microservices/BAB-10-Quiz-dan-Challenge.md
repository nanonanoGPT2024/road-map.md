# BAB 10: Quiz, Challenge, & Knowledge Check
**Production-Ready Engineering & Microservices**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: ASGI vs WSGI Lifecycle & Event Loop Saturation
Jelaskan perbedaan mendasar antara spesifikasi WSGI (PEP 3333) dan ASGI dalam menangani siklus hidup sebuah HTTP *request*! Secara arsitektural, mengapa eksekusi fungsi sinkronus yang melakukan operasi *blocking I/O* (seperti `time.sleep()` atau panggilan SDK basis data lawas tanpa dukungan *non-blocking socket*) di dalam *endpoint* ASGI (misalnya pada FastAPI atau BlackSheep) dapat melumpuhkan seluruh *throughput* satu *worker process*, dan bagaimana runtime Python mengeksekusinya di bawah tenda Uvicorn/uvloop?

### Soal 1.2: Deterministic Graceful Shutdown Sequence
Dalam ekosistem orkestrasi kontainer (seperti Kubernetes), sebuah *pod* yang menerima sinyal `SIGTERM` memiliki batas waktu (*grace period*) sebelum dipaksa mati via `SIGKILL`. Rancang urutan eksekusi (*lifecycle sequence*) deterministik yang wajib diimplementasikan oleh sebuah *microservice* Python berkinerja tinggi dari saat menangani sinyal OS hingga terminasi total! Cakup penanganan *active in-flight HTTP requests*, *background consumers* (Celery/Kafka), *connection pool draining* (SQLAlchemy/Redis), dan registrasi sinyal via `signal` atau *lifecycle events* ASGI.

### Soal 1.3: Health Probes Misconfiguration & Cascading Restarts
Jelaskan perbedaan fungsional dan semantik operasional antara **Startup Probe**, **Liveness Probe**, dan **Readiness Probe** pada Kubernetes! Uraikan sebuah anti-pattern umum di mana seorang perekayasa perangkat lunak mengonfigurasi *Liveness Probe* dengan mengecek ketersediaan dependensi eksternal (misalnya melakukan kueri `SELECT 1` ke basis data PostgreSQL hilir), dan jelaskan bagaimana kesalahan desain ini dapat memicu bencana *cascading failure* (*thundering herd restart loop*) pada seluruh klaster layanan.

### Soal 1.4: 12-Factor App & Dynamic Runtime Configurations
Tinjau kembali metodologi *Twelve-Factor App* pada domain Python *microservices*, khususnya Faktor III (Config) dan Faktor VI (Processes). Mengapa memuat konfigurasi produksi langsung dari file `.env` di dalam *runtime container* dianggap melanggar prinsip *cloud-native*, dan bagaimana arsitektur validasi *type-safe* berbasis *environment variable* (seperti Pydantic `BaseSettings`) mengisolasi kegagalan konfigurasi saat proses *bootstrapping* (*fail-fast*) dibanding pengecekan berbasis `os.environ.get()` yang terlambat (*lazy evaluation*)?

### Soal 1.5: Distributed Tracing & W3C Trace Context Propagation
Bagaimana mekanisme propagasi konteks terdistribusi bekerja pada arsitektur *microservices* berbasis Python menggunakan OpenTelemetry? Jelaskan secara teknis peran header HTTP standar `traceparent` (W3C standard), bagaimana `tracestate` dipertahankan saat melintasi batas proses (*process boundary*), dan mengapa manipulasi *thread-local storage* (`threading.local`) gagal mempertahankan kesinambungan *span* pada arsitektur asinkronus (asyncio), sehingga mewajibkan penggunaan modul `contextvars`!

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Gunicorn Process Models, GIL, & Copy-on-Write (CoW) Degradation
Ketika menjalankan *multi-worker* Gunicorn dengan *pre-fork model* di atas Linux, arsitektur memanfaatkan *system call* `fork()`. 
1. Bagaimana interaksi antara *pre-fork worker* dengan mekanisme *reference counting* pada CPython (`PyObject.ob_refcnt`)?
2. Mengapa modifikasi referensi objek yang konstan oleh CPython Garbage Collector secara perlahan merusak efisiensi *Copy-on-Write* (CoW) memori antar-*worker*, menyebabkan lonjakan alokasi *Resident Set Size* (RSS)?
3. Strategi apa yang dapat diterapkan pada level arsitektur runtime (misalnya pengaturan `max_requests`, `gc.freeze()`, atau *allocator flags*) untuk memitigasi isu fragmentasi dan kebocoran semu ini?

### Soal 2.2: Distributed Circuit Breaker Synchronization vs Local State
Pola *Circuit Breaker* (Closed, Open, Half-Open) krusial untuk mengisolasi kegagalan sistem hilir (*downstream*).
1. Bandingkan kelebihan dan kekurangan (*trade-off*) performa serta konsistensi antara implementasi *Circuit Breaker* dengan status lokal di memori setiap *worker process* versus status terdistribusi yang disimpan di Redis!
2. Jika sebuah *microservice* memiliki 20 *pod*, dan masing-masing *pod* menjalankan 4 *worker process* Uvicorn (total 80 *instances*), bagaimana *failure threshold* lokal dapat membiarkan ribuan panggilan gagal lolos ke sistem hilir yang sedang sekarat sebelum status lokal *tripped* ke *Open*? Bagaimana arsitektur *hybrid* mengatasi paradoks ini tanpa menambah latensi jaringan signifikan pada *hot-path*?

### Soal 2.3: Memory Allocation Profiling: CPython, Arenas, & OS Reclamation
Sebuah *microservice* Python pemroses berkas CSV/Parquet berukuran besar mengalami lonjakan konsumsi RAM hingga 4 GB selama proses parsing. Namun, setelah fungsi pemrosesan selesai dan objek data di-`del` serta `gc.collect()` dieksekusi secara eksplisit, metrik sistem operasi (via `htop` atau `cgroups`) tetap menunjukkan bahwa *container* menahan alokasi memori mendekati 4 GB hingga akhirnya terkena sinyal OOM (Out Of Memory) Killer saat lonjakan berikutnya tiba.
1. Analisis mengapa perilaku ini terjadi dengan merujuk pada arsitektur *memory allocator* CPython (*arenas*, *pools*, dan *blocks*) serta perilaku *glibc* `malloc`/`free`!
2. Bagaimana Anda membuktikan secara diagnostik menggunakan `tracemalloc` atau ekstensi C `jemalloc`/`mimalloc` bahwa kasus ini bukan *true memory leak*, melainkan kegagalan deallokasi memori kembali ke OS (*heap fragmentation*)?

### Soal 2.4: gRPC Internals, HTTP/2 Multiplexing, & Thread Pool Contention
Dalam skenario throughput tinggi, performa gRPC berbasis Python (`grpcio`) sering kali menunjukkan degradasi latensi yang tidak linier dibanding implementasi pada bahasa Go atau C++.
1. Uraikan bagaimana *threading model* dari *core C-extension* `grpcio` berinteraksi dengan Global Interpreter Lock (GIL) Python saat melakukan deserialisasi Protocol Buffers!
2. Mengapa multiplexing koneksi HTTP/2 tunggal pada klien gRPC Python sinkronus dapat menyebabkan antrean tersembunyi (*head-of-line blocking* pada level aplikasi), dan bagaimana perbandingannya jika menggunakan `grpc.aio` dengan integrasi *native event loop*?

### Soal 2.5: Kafka Consumer Rebalancing & Atomic Offset Commits
Pada integrasi Python dengan Apache Kafka menggunakan pustaka seperti `confluent-kafka` atau `aiokafka`:
1. Jelaskan bencana sistemik yang terjadi ketika durasi pemrosesan *batch* pesan melebihi ambang batas `max.poll.interval.ms`!
2. Mengapa *auto-commit* (`enable.auto.commit = True`) sangat diharamkan untuk arsitektur pemrosesan data finansial atau transaksional presisi tinggi?
3. Rancang sebuah alur konsumsi data asinkronus yang menjamin pemrosesan *at-least-once* dengan penanganan *manual commit* asinkronus dan pemanfaatan *idempotency key* di lapisan penyimpanan persisten untuk mencapai semantik *effectively-once*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Cascading Failure & Pool Starvation pada Core Payment Service
**Konteks Insiden:**
Pukul 14:02 WIB, *Core Payment Service* (FastAPI + SQLAlchemy + asyncpg + HTTPX) mengalami lonjakan latensi p99 dari 85ms menjadi 45.000ms dalam kurun waktu 3 menit. Beban *incoming traffic* normal pada kisaran 2.500 RPS. Dalam 5 menit berikutnya, seluruh pod (30 replika) mulai gagal melewati *Kubernetes Liveness Probe* dan mengalami *CrashLoopBackOff* secara massal, memutus layanan transaksi perusahaan seutuhnya.

**Temuan Forensik Awal:**
- Pihak bank mitra (*downstream payment gateway*) mengalami degradasi jaringan internal; latensi respons mereka molor dari 200ms menjadi 60 detik sebelum *drop* (HTTP 504).
- Panggilan keluar dari service Anda ke bank mitra menggunakan `httpx.AsyncClient(timeout=None)`.
- *Database pool* (`asyncpg`) dikonfigurasi dengan: `max_size=20`, `max_queries=50000`, `timeout=30.0`.
- Utilisasi CPU pada pod Python rata-rata hanya 8%, dan utilisasi memori normal (tidak OOM).
- Liveness Probe pod dikonfigurasi menembak endpoint `/healthz` yang secara internal mengeksekusi kueri `SELECT 1` menggunakan database connection pool yang sama dengan transaksi bisnis.

**Pertanyaan Diagnostik:**
1. Bedah rantai kausalitas (*causal chain*) insiden di atas! Jelaskan secara presisi bagaimana kelambatan mitra bank memicu kehabisan koneksi pada *database pool*, dan mengapa hal tersebut akhirnya membunuh pod via Kubernetes Liveness Probe padahal beban CPU hanya 8%!
2. Rancang arsitektur mitigasi (*remediation architecture*) komprehensif untuk mencegah kegagalan fatal serupa terjadi lagi! (Sertakan restrukturisasi Liveness/Readiness probe, konfigurasi HTTP Client timeouts, isolasi thread/connection pool via *bulkheading*, dan strategi degradasi anggun/*graceful degradation*).

---

### Skenario B: Distributed Race Condition & Data Corruption pada Dual-Write Architecture
**Konteks Insiden:**
Sebuah platform e-commerce menerapkan arsitektur *Order Processing Service* berbasis event-driven. Ketika sebuah order dibatalkan (`CancelOrder`), alur bisnis mengharuskan sistem untuk:
1. Memperbarui status pesanan menjadi `CANCELLED` di basis data PostgreSQL.
2. Mempublikasikan event `OrderCancelledEvent` ke Apache Kafka topik `order-events` agar *Inventory Service* mengembalikan stok dan *Ledger Service* melakukan pengembalian dana (*refund*).

**Kode Implementasi Saat Ini:**
```python
async def cancel_order(order_id: str, db: AsyncSession, kafka_producer: AIOKafkaProducer):
    async with db.begin():
        order = await db.get(Order, order_id)
        if order.status != OrderStatus.PENDING:
            raise InvalidStateError("Cannot cancel non-pending order")
        order.status = OrderStatus.CANCELLED
        # Commit database transaction
        await db.commit()
    
    # Send event to broker
    payload = OrderCancelledSchema(order_id=order.id, user_id=order.user_id).model_dump_json()
    await kafka_producer.send_and_wait("order-events", payload.encode('utf-8'))
```

**Temuan Masalah:**
Pada saat beban puncak (*Flash Sale*), ditemukan diskrepansi parah:
- Terdapat 412 order yang berstatus `CANCELLED` di database, tetapi stok barang di *Inventory Service* tidak pernah bertambah kembali, dan dana pengguna tidak pernah di-*refund*.
- Pada insiden terpisah saat Kafka broker mengalami *transient network partition*, klien API menerima HTTP 500 (Internal Server Error) karena panggilan `kafka_producer.send_and_wait` gagal (*timed out*), namun status pesanan di database telah permanen menjadi `CANCELLED`. Pengguna mengira pembatalan gagal dan mencoba menekan tombol berkali-kali, mengunci transaksi.

**Pertanyaan Diagnostik:**
1. Identifikasi dan jelaskan kelemahan fundamental pola *Dual-Write* pada kode di atas dalam kaitannya dengan kegagalan atomisitas lintas-sistem terdistribusi (*distributed transaction boundaries*)!
2. Rancang ulang solusi arsitektural menggunakan **Transactional Outbox Pattern**! Jelaskan bagaimana pola ini menyelesaikan masalah hilangnya event secara atomik, komponen apa yang dibutuhkan untuk membaca outbox table (misalnya Debezium/Kafka Connect vs Custom Poller berbasis Python), dan bagaimana Anda menjamin pemrosesan idempoten pada sisi *Inventory Service*!

---

### Skenario C: The Silent OOM Killer & Multi-Stage Docker Layer Bloat
**Konteks Insiden:**
Sebuah tim AI/ML Engineering memigrasikan microservice inferensi Computer Vision (FastAPI + PyTorch CPU + NumPy) ke cluster Kubernetes produksi. Microservice ini sering mengalami *eviction* dan terminasi mendadak dengan sinyal Kubernetes `OOMKilled` (Exit Code 137). Selain itu, deployment pipeline CI/CD memakan waktu 28 menit hanya untuk fase *docker build & push*, dengan ukuran image kontainer mencapai 9.4 GB.

**Spesifikasi Dockerfile Saat Ini:**
```dockerfile
FROM python:3.11

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y gcc g++ libgl1-mesa-glx
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "8"]
```

**Hasil Monitoring Pod:**
- Pod dialokasikan resource: `limits: { memory: "4Gi" }`, `requests: { memory: "2Gi" }`.
- Saat pod baru saja menyala (*idle*), konsumsi memori langsung berada di angka 3.2 GB (8 worker Uvicorn).
- Begitu menerima *concurrent requests* berupa unggahan berkas gambar (rata-rata 10 MB per berkas), total memori pod menembus 4.1 GB dan langsung terkena `OOMKilled` oleh kernel Linux cgroup OOM killer.

**Pertanyaan Diagnostik:**
1. Bedah penyebab konsumsi memori *idle* yang melonjak drastis hingga 3.2 GB! Berapa alokasi memori aktual yang dikonsumsi per worker Python ketika memuat model PyTorch ke dalam memori pada skenario `--workers 8` di atas, dan bagaimana konsep Linux *Process Memory Virtual Size vs RSS* menjelaskannya?
2. Rekonstruksi arsitektur *containerization* dan runtime service tersebut! Tuliskan perbaikan Dockerfile multi-stage production-grade (terapkan non-root user, optimasi layer caching, pembersihan artifact build) dan tentukan strategi runtime worker yang benar (misalnya kombinasi worker vs thread atau arsitektur single-worker per container pod horizontal autoscaling)!

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Resilient Edge-Gateway Proxy
Rancang dan bangun sebuah modul **Microservice Proxy Core** menggunakan Python 3.11+ yang mengintegrasikan aspek ketahanan industri (*enterprise resilience*), observabilitas (*telemetry*), dan pembersihan proses deterministik (*graceful shutdown*).

#### Requirements:
1. **Engine & Protocols:**
   - Bangun menggunakan framework ASGI murni (FastAPI atau Starlette/Uvicorn).
   - Menggunakan `httpx.AsyncClient` dengan konfigurasi *connection pooling* eksplisit: batas maksimum koneksi (*max connections*), alokasi koneksi *idle* (*max keepalive connections*), dan *fine-grained timeouts* (connect, read, write, pool timeout).

2. **Fault Tolerance & Resilience (Wajib Hand-Crafted / Tanpa Lib Wrapper Magis):**
   - **Circuit Breaker Pattern:** Implementasikan finite-state machine (Closed, Open, Half-Open) thread-safe / task-safe yang memantau tingkat kegagalan (misalnya rasio error 5xx > 50% dalam window rolling 10 detik).
   - **Exponential Backoff with Full Jitter:** Mekanisme *retry* hanya untuk *idempotent HTTP methods* (GET, HEAD, PUT) pada kegagalan berbasis jaringan (jeda waktu adaptif: $T = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$).
   - **Bulkheading:** Batasi jumlah konkurensi panggilan keluar (*outbound concurrent calls*) ke downstream service menggunakan `asyncio.Semaphore` guna mencegah deplesi resource lokal.

3. **Telemetry & Observability:**
   - Ekstrak atau buat W3C Distributed Tracing header (`traceparent`).
   - Logging terstruktur format JSON ke `sys.stdout` (menggunakan library bawaan atau `structlog`) menyertakan: `timestamp`, `log_level`, `trace_id`, `span_id`, `latency_ms`, `http_status`, `client_ip`. Jangan gunakan print statement atau format teks mentah.

4. **Deterministic Graceful Shutdown Engine:**
   - Intersepsi sinyal OS `SIGTERM` dan `SIGINT`.
   - Ketika sinyal diterima, stop menerima request baru, biarkan *in-flight requests* selesai berjalan (dengan limit *grace period timeout* 15 detik), tutup HTTP client connection pool secara asinkronus, dan lakukan terminasi bersih dengan exit code `0`.

5. **Containerization:**
   - Buat file `Dockerfile` multi-stage build yang memisahkan stage kompilasi dependensi (wheel build) dan stage eksekusi final.
   - Stage final wajib berjalan menggunakan *Distroless* image atau minimal *Debian-slim*, dijalankan di bawah akun *unprivileged non-root user* (UID 10001), dan dilengkapi utilitas `tini` / `dumb-init` sebagai PID 1 untuk penanganan *zombie process reaping*.

#### Constraints:
- Kode Python harus lolos analisis tipe statis ketat menggunakan `mypy --strict`.
- Tidak boleh ada kebocoran memory (*zero unhandled task leaks*); semua `asyncio.Task` yang dibuat harus dijamin di-*await* atau di-*cancel* secara bersih saat terminasi.

#### Expected Output:
- Satu berkas kode microservice Python (`gateway.py`) modular yang mencakup implementasi proxy endpoint, Circuit Breaker, tracing middleware, dan shutdown handler.
- Satu berkas `Dockerfile` multi-stage siap produksi.
- Log eksekusi terminal yang memperlihatkan:
  1. Bootstrapping aplikasi dan log JSON terstruktur.
  2. Demonstrasi request lolos dengan trace context.
  3. Demonstrasi simulasi downstream failure memicu status Circuit Breaker berpindah dari `CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF-OPEN` $\rightarrow$ `CLOSED`.
  4. Demonstrasi penerimaan sinyal `SIGTERM` yang memicu pembersihan *in-flight tasks* secara teratur tanpa *dropped connection*.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan rekayasa sistem Anda sebelum melangkah ke domain arsitektur tingkat lanjut.

### Saya harus memahami:
- [ ] Anatomi spesifikasi ASGI, struktur *scope*, *receive*, *send*, dan alur kerja internal *event loop* uvloop/asyncio.
- [ ] Mengapa pencampuran panggilan sinkronus/blocking ke dalam event loop utama merupakan anti-pattern fatal pada Python asinkronus.
- [ ] Perbedaan siklus hidup dan implikasi kegagalan konfigurasi Startup, Liveness, dan Readiness Probes pada Kubernetes.
- [ ] Alur propagasi W3C Trace Context (`traceparent`) lintas batas proses jaringan menggunakan OpenTelemetry SDK.
- [ ] Mekanisme alokasi memori internal CPython (*Arenas, Pools, Blocks*), isu fragmentasi *heap*, dan dampaknya terhadap *Linux Copy-on-Write* pada *pre-fork worker*.
- [ ] Implikasi konkurensi Global Interpreter Lock (GIL) terhadap pemrosesan thread I/O-bound vs CPU-bound pada layanan HTTP dan gRPC.
- [ ] Pola ketahanan arsitektur microservices: Circuit Breaker, Bulkheading, Rate Limiting, dan Exponential Backoff dengan Jitter.
- [ ] Masalah integritas data *Dual-Write* pada sistem terdistribusi dan penyelesaiannya via *Transactional Outbox Pattern*.

### Saya tidak perlu menghafal:
- [ ] Sintaksis baris-per-baris dari konfigurasi gunicorn flags (cukup pahami konsep `--workers`, `--threads`, `--worker-class`, dan kalkulasi kapasitas sistem).
- [ ] Struktur bitwise heksadesimal dari seluruh spesifikasi format W3C Traceparent (cukup pahami versi, trace ID, parent/span ID, dan trace flags).
- [ ] Seluruh tabel parameter konfigurasi socket TCP Linux (seperti `tcp_wmem`, `tcp_rmem`, `SOMAXCONN`), cukup pahami kapan socket pool exhaustion terjadi pada layer aplikasi.

### Saya harus bisa melakukan:
- [ ] Membangun dan mengonfigurasi *microservice* Python berperforma tinggi dengan *zero-blocking execution pattern*.
- [ ] Menuliskan Dockerfile multi-stage berbasis non-root user dengan isolasi build environment yang menghasilkan image minimalis, aman, dan efisien.
- [ ] Mengimplementasikan *Graceful Shutdown* deterministik yang menangani sinyal OS `SIGTERM`/`SIGINT`, menguras *connection pool*, dan mencegah *in-flight request dropped*.
- [ ] Melakukan profiling dan debugging kebocoran memori atau fragmentasi memori pada container pod Python menggunakan `tracemalloc`, `objgraph`, atau alokator kustom (`jemalloc`).
- [ ] Mendesain dan mengimplementasikan mekanisme idempotensi pada pemrosesan pesan asinkronus (Kafka/RabbitMQ) dengan *manual offset commit* yang aman.