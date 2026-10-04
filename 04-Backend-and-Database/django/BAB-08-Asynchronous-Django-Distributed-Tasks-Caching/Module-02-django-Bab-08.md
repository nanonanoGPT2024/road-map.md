# BAB 08: Asynchronous Django, Distributed Tasks & Caching
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Distributed Workflows Tingkat Lanjut**: Menguasai orkestrasi task kompleks menggunakan Celery Canvas primitives (`chain`, `group`, `chord`, `map`, `starmap`) dengan penanganan kegagalan parsial (*partial failure handling*).
2. **Membangun Sistem Task Idempoten & Resilien**: Mengimplementasikan idempotensi berbasis *distributed state machine*, deduplikasi pesan, serta mekanisme *exponential backoff retry* dengan *jitter* terdistribusi.
3. **Mengoptimalkan Concurrency & Worker Topology**: Mengonfigurasi worker pools (`prefork`, `gevent`, `solo`), memisahkan antrean berdasarkan SLA (*priority queues*, *workload isolation*), serta mengatur *prefetch limits* untuk mencegah *worker starvation*.
4. **Menguasai Integrasi ASGI & Sync/Async Boundary**: Mengelola interaksi antara *native async views* (`async def`) dan *Django ORM* melalui `sync_to_async` dan connection lifecycle management guna mengeliminasi risiko *thread exhaustion* dan *context leakage*.
5. **Menerapkan Pola Caching Skala Enterprise**: Mencegah *Cache Stampede* menggunakan algoritma probabilistik (*XFetch / Early Probabilistic Expiration*) dan *Distributed Locking* (Redlock pattern) pada Redis Cluster.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Dasar-dasar asynchronous Python (`asyncio`, `event loop`, `coroutines`, `awaitables`).
* Arsitektur dasar Celery (Producer-Broker-Consumer pattern, Result Backend).
* Protokol komunikasi pesan (AMQP framing, Redis primitives: Streams, Hashes, Lists).
* Django internals dasar (Request/Response lifecycle pada WSGI vs. ASGI, ORM query evaluation engine).

---

### 3. Concept & Internal Architecture

Arsitektur asynchronous dan pemrosesan terdistribusi modern pada Django berpusat pada pemisahan beban kerja I/O-bound dan CPU-bound dari siklus hidup request-response HTTP utama, serta sinkronisasi konkurensi di luar context memory tunggal.

```
                           +-------------------------------------------------+
                           |               NGINX / Edge Proxy               |
                           +-------------------------------------------------+
                                      |                           |
                               (HTTP Requests)             (WebSockets/SSE)
                                      v                           v
                           +--------------------+      +--------------------+
                           |  Gunicorn (WSGI)   |      |  Uvicorn/Daphne    |
                           |  Django Core Views |      |  (ASGI Async Loop) |
                           +--------------------+      +--------------------+
                                      |                           |
                                      +-------------+-------------+
                                                    |
                         +--------------------------+--------------------------+
                         |                                                     |
                         v                                                     v
          +-----------------------------+                       +-----------------------------+
          |     Redis Cache Cluster     |                       |    RabbitMQ (AMQP Broker)   |
          |  - Multi-tier Caching       |                       |  - Direct / Topic Exchanges |
          |  - Distributed Locks        |                       |  - Dead Letter Exchanges    |
          |  - Session Store            |                       |  - Priority Queues          |
          +-----------------------------+                       +-----------------------------+
                         ^                                                     |
                         | (Locking / State)                        (Task Ingestion via AMQP)
                         |                                                     v
          +-----------------------------------------------------------------------------------+
          |                               Celery Worker Fleet                                 |
          |  +--------------------+   +--------------------+   +---------------------------+  |
          |  | Queue: "critical"  |   |   Queue: "default" |   | Queue: "batch_io"         |  |
          |  | Pool: prefork      |   |   Pool: prefork    |   | Pool: gevent (Concurrency |  |
          |  | Prefetch: 1        |   |   Prefetch: 4      |   |       = 500)              |  |
          |  +--------------------+   +--------------------+   +---------------------------+  |
          +-----------------------------------------------------------------------------------+
                         |                                                     |
                         v                                                     v
          +-----------------------------------------------------------------------------------+
          |                        PostgreSQL Primary / Replica Cluster                       |
          +-----------------------------------------------------------------------------------+
```

#### A. Internal Celery Execution Engine & AMQP Protocol
1. **AMQP Channels & Multiplexing**: Celery berkomunikasi dengan broker (misal: RabbitMQ) melalui satu koneksi TCP tunggal yang dibagi ke dalam beberapa *channels*. Setiap worker thread atau subproses menggunakan channel unik untuk menghindari contention lock pada level socket TCP.
2. **Prefetch Multiplier & Ingestion**:
   $$\text{Actual Prefetch Count} = \text{worker\_concurrency} \times \text{worker\_prefetch\_multiplier}$$
   Jika `worker_prefetch_multiplier=4` dan worker memiliki 8 prosesor (`concurrency=8`), worker akan menarik 32 task ke memory buffer internal. Pada task yang memakan waktu lama (*long-running tasks*), nilai default (`4`) menyebabkan *queue starvation*, di mana satu worker menimbun task berat sementara worker lain idle. Pada skenario enterprise, `worker_prefetch_multiplier=1` dikombinasikan dengan `acks_late=True` adalah standar wajib untuk task komputasi berat.
3. **Message Acknowledgement Semantics**:
   * *Early Ack (`acks_late=False`)*: Pesan di-ACK ke broker seketika sebelum dieksekusi. Jika proses mati mendadak (OOM kill, hardware failure), task hilang permanen (*at-most-once*).
   * *Late Ack (`acks_late=True`)*: Pesan tetap berada di broker dengan status `unacknowledged` sampai fungsi task selesai dieksekusi. Jika worker crash, broker mengembalikan pesan ke antrean (*at-least-once*). Model ini mengharuskan task berifat **idempoten**.

#### B. Django ASGI & The `sync_to_async` Boundary
Ketika Django mengeksekusi view asinkron (`async def view(request)`):
* Event loop utama (biasanya dijalankan oleh Uvicorn/Daphne) menangani *event socket* non-blocking.
* Django ORM hingga saat ini sebagian besar masih synchronous blocking secara internal. Pemanggilan query ORM pada context async membutuhkan jembatan: `sync_to_async` dari library `asgiref`.
* `sync_to_async` mengeksekusi kode blocking di dalam worker pool thread terpisah (`ThreadPoolExecutor`). Jika alokasi thread pool ini jenuh (*thread exhaustion*), seluruh throughput server akan terdegradasi.
* `contextvars` disalin secara eksplisit dari thread ASGI utama ke thread pool ORM untuk memastikan isolasi konteks (seperti thread-local storage, security context, database routing context) tidak bocor atau hilang.

#### C. Cache Stampede Dynamics (Dogpiling Effect)
Saat key cache bernilai tinggi kedaluwarsa (*expires*) pada sistem ber-QPS tinggi, ribuan request bersamaan akan mendapati *cache miss*. Semua request tersebut secara paralel mengeksekusi query database yang identik dan mencoba menulis ulang cache. Beban komputasi mendadak ini (*stampede*) dapat melumpuhkan database relational.

Solusi mitigasi tingkat arsitektur:
1. **Distributed Mutex (Redlock / Single-Flight Lock)**: Hanya satu thread/proses yang diizinkan mengambil lock untuk komputasi ulang cache; thread lain menunggu atau menerima *stale data*.
2. **Probabilistic Early Expiration (Algoritma XFetch)**:
   Algoritma membaca sisa waktu hidup (*TTL*) cache. Semakin dekat dengan waktu kedaluwarsa dan semakin lama waktu komputasi yang dibutuhkan, semakin tinggi probabilitas acak bahwa satu request akan menghitung ulang data **sebelum** cache benar-benar mati.

   $$\text{compute} \iff -\beta \times \delta \times \ln(\text{rand}()) > \text{expiry} - \text{now}$$
   *Dimana $\beta > 0$ adalah agresivitas, $\delta$ adalah waktu komputasi sebelumnya, dan $\text{rand}() \in (0, 1]$.*

---

### 4. Why & What

| Pendekatan / Komponen | What (Apa fungsinya) | Why (Mengapa krusial di Enterprise) |
| :--- | :--- | :--- |
| **Celery Canvas (Chords/Chains)** | Abstraksi Directed Acyclic Graph (DAG) untuk tugas paralel dan sekuensial. | Menghilangkan callback hell terdistribusi; memungkinkan agregasi data paralel dengan barrier sinkronisasi atomik. |
| **Late Acknowledgement (`acks_late=True`)** | Menunda ACK broker hingga task selesai dijalankan. | Menjamin keandalan data (*zero message loss*) saat terjadi node failure atau autoscaling scale-down. |
| **Redis Distributed Lock (Redlock)** | Mutex berbasis lease time pada Redis terdistribusi. | Menghindari *race condition* lintas container/pod; mengamankan mutasi saldo atau pembaruan inventaris. |
| **Probabilistic Cache Invalidation** | Algoritma background recompute data sebelum TTL habis. | Menghilangkan latency spike dan database crash yang disebabkan oleh lonjakan *cache miss* masif. |
| **ASGI Engine + `sync_to_async`** | Event-loop request handling berdampingan dengan ThreadPool ORM. | Efisiensi I/O untuk Long-Polling, WebSockets, dan third-party API integration dengan konkurensi masif. |

---

### 5. How (Workflow Detail)

Alur orkestrasi pemrosesan terdistribusi enterprise (misal: settlement transaksi):

```
Client             Django ASGI View         Redis Cache            RabbitMQ             Celery Worker
  |                       |                      |                     |                      |
  |--- POST /checkout --->|                      |                     |                      |
  |                       |--- Acquire Lock ---->|                     |                      |
  |                       |<-- Lock Granted -----|                     |                      |
  |                       |                                            |                      |
  |                       |--- Dispatch Task Signature (idempotent) -->|                      |
  |                       |    (Message with routing_key='critical')   |                      |
  |                       |                                            |                      |
  |<-- 202 Accepted ------|                                            |                      |
  |   (with Task ID)      |                                            |                      |
  |                       |                                            |--- Deliver Message ->|
  |                       |                                            |    (Unacked state)   |
  |                       |                                            |                      |
  |                       |                                            |    [Execute Task]    |
  |                       |                                            |    1. Verify Token   |
  |                       |                                            |    2. Mutate DB      |
  |                       |                                            |    3. Emit Outbox    |
  |                       |                                            |                      |
  |                       |                                            |<--- ACK Message -----|
  |                       |                                            |     (Drop from Q)    |
  |                       |                      +---------------------+                      |
  |                       |                      | Save Task Result (Optional)                |
  |                       |                      v                                            |
  |                       |             +-----------------+                                   |
  |                       |             |  Redis Backend  |                                   |
  |                       |             +-----------------+                                   |
```

1. **Ingress**: Request masuk ke Django ASGI View. Validasi payload dilakukan seketika secara sinkron.
2. **Locking & Task Injection**: System membuat token idempotensi unik, memverifikasi ketiadaan duplikasi di Redis, dan mempublikasikan task ke RabbitMQ Exchange dengan routing key spesifik.
3. **Immediate Response**: Django mengembalikan respons `202 Accepted` bersama `task_id` dan tracking URI ke client tanpa menunggu eksekusi backend.
4. **Broker Ingestion**: RabbitMQ mendistribusikan task ke antrean bertarget (`critical_queue`). Pesan ditandai sebagai `unacknowledged`.
5. **Worker Execution**: Celery worker pool mengambil pesan, memvalidasi state lock idempotensi pada Redis, lalu mengeksekusi operasi database di dalam transaksi atomik.
6. **Settlement & ACK**: Begitu commit DB berhasil, worker mengirimkan frame `basic_ack` ke RabbitMQ. Jika eksekusi gagal atau worker mati, RabbitMQ mendeteksi hilangnya channel koneksi dan mengembalikan pesan ke antrean (*re-queue*) atau mengarahkannya ke Dead Letter Exchange (DLX).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Dapur Restoran Bintang Lima
* **Django Request Loop**: Pelayan di depan restoran. Kerjanya harus super cepat: mencatat pesanan, menyapa pelanggan, dan mengantarkan nota. Pelayan tidak boleh memasak di dapur karena meja lain akan terbengkalai.
* **RabbitMQ Broker**: Papan selip pesanan (*order board*) di dapur. Tiket pesanan ditempel di sini, terurut rapi berdasarkan prioritas (VIP vs. Reguler).
* **Celery Worker**: Tim koki di dapur.
    * *Prefork Pool*: Beberapa master chef independen yang memasak makanan berat (steak, kalkun).
    * *Gevent/Eventlet Pool*: Asisten koki yang menangani ratusan pengatur waktu (merebus telur, menyeduh teh—banyak menunggu air mendidih/IO bound).
* **Redis Caching**: Rak bumbu racikan siap pakai. Koki tidak perlu memeras santan dari kelapa setiap saat; jika racikan tersedia di rak, langsung ambil.
* **Cache Stampede (Dogpile)**: Rak bumbu racikan tiba-tiba kosong saat jam makan malam puncak. Seratus koki berlari serentak memperebutkan satu blender untuk membuat bumbu yang sama, menyebabkan blender meledak (Database crash).

```
[ HTTP Traffic ]
       |
       v
+------------------+     Cache Hit      +--------------------+
|  Django Handlers |------------------->| Redis Key-Value    |
|  (The Waiters)   |<-------------------| (Prepped Seasoning)|
+------------------+    Data Returned   +--------------------+
       |
  Async Task Needed
       |
       v
+------------------------------------------------------------+
| RabbitMQ AMQP Broker (The Order Board)                     |
|                                                            |
|  [ Exchange: tasks_core ]                                  |
|         |                                                  |
|         +---> Queue: payments.fifo  (Priority HIGH)        |
|         |                                                  |
|         +---> Queue: emails.bulk    (Priority LOW)         |
|         |                                                  |
|         +---> Queue: dead_letter    (Failed poison pills)  |
+------------------------------------------------------------+
       |                                      |
       v                                      v
+------------------------------+  +------------------------------+
| Worker Group A               |  | Worker Group B               |
| Concurrency: 8 (prefork)     |  | Concurrency: 1000 (gevent)   |
| Workload: Financial Ledger   |  | Workload: Webhooks, Push Notif|
| acks_late=True, prefetch=1   |  | acks_late=False, prefetch=100|
+------------------------------+  +------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Async View dengan Safe ORM Execution & Celery Delay
Contoh fundamental memanggil task asynchronous dari dalam Django ASGI view menggunakan context boundary aman.

*File: `myapp/tasks.py`*
```python
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3}
)
def send_activation_email(self, user_id: int) -> str:
    logger.info(f"Processing activation email for user {user_id}. Attempt {self.request.retries}")
    # Simulasi I/O pengiriman email
    return f"Email sent successfully to user {user_id}"
```

*File: `myapp/views.py`*
```python
from django.http import JsonResponse, HttpRequest
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from .tasks import send_activation_email

User = get_user_model()

async def register_user_async_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    username = request.POST.get("username", "developer")
    email = request.POST.get("email", "dev@enterprise.internal")

    # DATABASE IO: Wajib dibungkus sync_to_async agar tidak memblokir event loop
    create_user_fn = sync_to_async(User.objects.create_user, thread_sensitive=True)
    user = await create_user_fn(username=username, email=email)

    # Celery task dispatch non-blocking
    task = send_activation_email.delay(user.id)

    return JsonResponse({
        "status": "created",
        "user_id": user.id,
        "task_id": task.id
    }, status=201)
```

---

#### B. Practical Enterprise Example: Financial Reconciliation Workflow
Penerapan Celery Canvas (`chord`), Distributed Locking dengan Redis, State Tracking, dan Idempotensi penuh untuk sistem rekonsiliasi data.

*File: `settlement/tasks.py`*
```python
import time
import math
import random
from typing import List, Dict, Any
from celery import shared_task, chord, group
from django.db import transaction
from django.core.cache import cache
import redis
from django.conf import settings

# Inisialisasi dedicated low-level Redis client untuk locking
redis_client = redis.Redis.from_url(settings.REDIS_LOCK_URL)

class DistributedLockError(Exception):
    """Exception dilempar jika lock gagal diakuisisi."""
    pass

class DistributedLock:
    def __init__(self, key: str, timeout: int = 60):
        self.key = f"lock:distributed:{key}"
        self.timeout = timeout
        self.identifier = None

    def __enter__(self):
        import uuid
        self.identifier = str(uuid.uuid4())
        # NX: Set if Not Exists, PX: Expire time dalam millisecond
        acquired = redis_client.set(self.key, self.identifier, nx=True, ex=self.timeout)
        if not acquired:
            raise DistributedLockError(f"Resource is locked: {self.key}")
        return self.identifier

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Lua script untuk memastikan release lock bersifat atomik (hanya owner yang bisa release)
        lua_release_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
        """
        redis_client.eval(lua_release_script, 1, self.key, self.identifier)

@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=5
)
def extract_single_merchant_batch(self, merchant_id: int, batch_window: str) -> Dict[str, Any]:
    """Task mikro untuk memproses batch merchant secara terisolasi."""
    try:
        # Idempotency lock per merchant batch
        lock_name = f"merchant_reconcile:{merchant_id}:{batch_window}"
        with DistributedLock(lock_name, timeout=120):
            # Simulasi pengolahan ledger kompleks
            time.sleep(0.5)
            total_amount = round(random.uniform(1000.0, 50000.0), 2)
            processed_transactions = random.randint(10, 500)
            
            return {
                "merchant_id": merchant_id,
                "total_amount": total_amount,
                "transaction_count": processed_transactions,
                "status": "PROCESSED"
            }
    except DistributedLockError as exc:
        # Retry dengan exponential backoff dan jitter
        countdown = int((2 ** self.request.retries) + random.uniform(0.5, 3.0))
        raise self.retry(exc=exc, countdown=countdown)

@shared_task(acks_late=True)
def aggregate_reconciliation_settlement(results: List[Dict[str, Any]], settlement_date: str) -> Dict[str, Any]:
    """Callback Chord: Dijalankan HANYA SETELAH semua tasks dalam group selesai."""
    total_volume = sum(item["total_amount"] for item in results)
    total_tx_count = sum(item["transaction_count"] for item in results)
    merchants_processed = [item["merchant_id"] for item in results]

    # Simpan hasil agregasi atomik ke database via transaksi Django
    with transaction.atomic():
        # Simulasi update ledger database internal
        pass

    return {
        "settlement_date": settlement_date,
        "merchants_count": len(merchants_processed),
        "total_volume": float(total_volume),
        "total_tx_count": total_tx_count,
        "status": "FINALIZED"
    }

def trigger_enterprise_settlement_workflow(merchant_ids: List[int], settlement_date: str):
    """
    Entry point: Membangun Directed Acyclic Graph (DAG) menggunakan Chord.
    Struktur: Parallel Header Tasks (Group) -> Synchronization Barrier -> Finalizer Callback.
    """
    header = group(
        extract_single_merchant_batch.s(m_id, settlement_date)
        for m_id in merchant_ids
    )
    callback = aggregate_reconciliation_settlement.s(settlement_date=settlement_date)
    
    # Eksekusi chord
    async_chord = chord(header)(callback)
    return async_chord.id
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Flash Sale SuperApp – 15,000 Checkout Request per Detik
* **Permasalahan**: Saat kampanye *flash sale*, 15.000 transaksi checkout masuk secara konkuren ke sistem Django. Layanan payment gateway pihak ketiga memiliki batas throughput (rate-limit) 500 req/sec. Database PostgreSQL crash akibat *connection pool exhaustion*, dan pembacaan katalog produk mengalami *cache stampede* ketika TTL cache habis.
* **Solusi Arsitektural**:
    1. **Probabilistic Early Invalidation (XFetch)**: Katalog flash sale dikonsumsi melalui layer cache Redis dengan algoritma XFetch.
    2. **Rate-Controlled Task Ingestion**: Django ASGI menerima pesanan, mengalokasikan token pesanan ke Redis, lalu melemparkan task pembayaran ke antrean RabbitMQ bertingkat (`flash_sale_high_prio`).
    3. **Worker Throttling & Token Bucket**: Worker Celery dikonfigurasi menggunakan pool `gevent` dengan isolasi antrean dan token-bucket rate limiter internal untuk membatasi pemanggilan API payment gateway tepat 450 req/sec.

#### Implementasi Algoritma XFetch Caching (Zero-Stampede):
```python
import math
import time
import random
import json
from typing import Callable, Any
from django.core.cache import cache

def get_or_compute_xfetch(key: str, compute_func: Callable[[], Any], ttl_seconds: int, beta: float = 1.0) -> Any:
    """
    Implementasi algoritma probabilistik XFetch untuk meniadakan Cache Stampede.
    Ref: Vattani, A., Chierichetti, F., & Lowenstein, K. (Optimal Probabilistic Cache Invalidation).
    """
    cached_payload = cache.get(key)
    now = time.time()

    if cached_payload:
        data = cached_payload.get("data")
        delta = cached_payload.get("delta")        # Waktu komputasi dalam detik
        expiry = cached_payload.get("expiry")      # Timestamp absolut epoch

        # Logika Inti XFetch: -beta * delta * ln(random())
        # random.random() menghasilkan float dalam rentang (0.0, 1.0)
        random_factor = -beta * delta * math.log(random.random())
        if (now - random_factor) < expiry:
            # Belum melewati threshold komputasi probabilistik; return stale/valid cache
            return data

    # Terjadi cache miss atau terpicu early expiration probabilistik
    start_time = time.time()
    computed_data = compute_func()
    compute_duration = time.time() - start_time

    payload_to_cache = {
        "data": computed_data,
        "delta": compute_duration,
        "expiry": now + ttl_seconds
    }
    
    # Simpan di cache backend dengan TTL sebenarnya ditambah margin toleransi
    cache.set(key, payload_to_cache, timeout=ttl_seconds + 300)
    return computed_data
```

---

### 9. Trade-offs

| Parameter | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Worker Concurrency Pool** | `prefork` (Multiprocessing) | `gevent` / `eventlet` (Greenlet Coroutines) | `prefork` aman untuk pemrosesan berbasis CPU, C-extensions, dan isolasi memori mutlak, namun memakan RAM masif (~100MB per proses). `gevent` dapat menangani ribuan task I/O-bound ringan per node, tetapi **tidak aman** untuk CPU-heavy task dan library eksternal C yang tidak dipatch secara kooperatif. |
| **Broker Selection** | RabbitMQ (AMQP) | Redis (In-Memory PubSub/Streams) | RabbitMQ menawarkan per-message routing fleksibel, acknowledgement channel yang tangguh, DLX native, dan delivery guarantee kuat; namun menuntut overhead operasional cluster yang kompleks. Redis jauh lebih kencang dan simpel dioperasikan, namun jika RAM habis tanpa setup persistensi (AOF/fsync) yang tepat, risiko hilangnya pesan task menjadi tinggi. |
| **Task Message Durability** | `acks_late=False` | `acks_late=True` | `acks_late=False` mencegah pesan ganda dieksekusi (*at-most-once*), ideal untuk task non-kritis (e.g. log audit), namun rentan data hilang jika node OOM. `acks_late=True` menjamin task tidak hilang (*at-least-once*), namun **mewajibkan arsitektur idempoten** secara ketat karena resiko re-run task parsial saat worker crash. |
| **ORM Access in ASGI** | Synchronous Block via `sync_to_async` | Native Async Querysets (`aenter`, `afirst`) | Native async querysets efisien dan tidak mengonsumsi threadpool terpisah, namun fitur Django ORM async belum mencakup 100% API (e.g., related object lazy loading). `sync_to_async` kompatibel dengan seluruh fitur legacy, namun memicu beban context switching dan limitasi alokasi `ThreadPoolExecutor`. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mengirim Object Django Model Instansiasi Langsung ke Parameter Task
* **Kesalahan**:
  ```python
  # SALAH
  user = User.objects.create(...)
  my_task.delay(user) # Serialisasi crash / Mengirim state stale
  ```
* **Akar Masalah**: Objek model tidak aman diserialisasi ke JSON (menuntut format Pickle yang berisiko celah keamanan RCE). Selain itu, terjadi race condition: task mungkin berjalan di worker sebelum transaksi database di Django view selesai di-commit (`READ UNCOMMITTED`/`READ COMMITTED` barrier).
* **Solusi**: Kirim hanya Primary Key (`user.id`) dan gunakan `transaction.on_commit`:
  ```python
  # BENAR
  user = User.objects.create(...)
  transaction.on_commit(lambda: my_task.delay(user.id))
  ```

#### 2. Worker Memory Leak Akibat Stateful Global Variables atau C-Extensions
* **Gejala**: RAM worker naik konstan setiap jam hingga terkena signal `SIGKILL (OOM Killer)`.
* **Troubleshooting & Solusi**: Batasi jumlah eksekusi task per worker process sebelum subproses di-recycle otomatis:
  ```python
  # celery.py
  app.conf.update(
      worker_max_tasks_per_child=1000,      # Daur ulang proses setelah 1000 task
      worker_max_memory_per_child=200000,   # 200MB max per proses child
  )
  ```

#### 3. Thread-Pool Saturation pada `sync_to_async`
* **Gejala**: HTTP response time di Django ASGI views melonjak tinggi padahal CPU dan RAM server sangat rendah.
* **Investigasi**: Jalankan introspeksi pool environment:
  ```bash
  py-spy dump --pid <django_pid>
  ```
  Akan terlihat ratusan coroutine tertahan antre di lock threadpool `asgiref.sync.sync_to_async`.
* **Solusi**: Tingkatkan kapasitas threadpool default `asgiref` via environment variable:
  ```bash
  export ASGI_THREADS=100
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Serializer JSON Eksklusif**: Nonaktifkan `pickle` untuk menutup celah Remote Code Execution (RCE).
  ```python
  app.conf.task_serializer = 'json'
  app.conf.result_serializer = 'json'
  app.conf.accept_content = ['json']
  ```
- [ ] **Pisahkan Queues Berdasarkan Karakteristik Task**:
  Pisahkan antrean menjadi minimal 3 kategori: `high_priority` (latency-critical), `default` (general operational), dan `bulk_io` (long-running batch).
- [ ] **Terapkan Limits Secara Global**:
  Wajib mengonfigurasi batas waktu timeout agar tidak ada task *zombie* yang memblokir worker selamanya.
  ```python
  app.conf.task_soft_time_limit = 300  # Melempar SoftTimeLimitExceeded exception
  app.conf.task_time_limit = 360       # Hard SIGKILL jika worker mengabaikan soft limit
  ```
- [ ] **Konfigurasikan Prefetch Multiplier Secara Sadar**:
  Gunakan `worker_prefetch_multiplier = 1` bila durasi eksekusi antar task bervariasi signifikan.
- [ ] **Sanitasi Database Connections Pasca-Task**:
  Untuk mencegah *stale database connections* di worker yang idle:
  ```python
  from django.db import close_old_connections
  from celery.signals import task_postrun

  @task_postrun.connect
  def close_connections(**kwargs):
      close_old_connections()
  ```
- [ ] **Gunakan Cache Compression**:
  Aktifkan kompresi Zstandard atau LZ4 pada Redis jika menyimpan payload string JSON berukuran di atas 10KB.

---

### 12. Hands-on Practice

Buat implementasi sistem distributed task lengkap pada direktori `hands-on/m02/`.

#### Struktur Direktori:
```text
hands-on/m02/
├── docker-compose.yml
├── enterprise_async/
│   ├── __init__.py
│   ├── asgi.py
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── requirements.txt
└── tasks_infra/
    ├── __init__.py
    ├── apps.py
    ├── tasks.py
    └── views.py
```

#### Langkah 1: Siapkan Konfigurasi Ekosistem Docker
*File: `hands-on/m02/docker-compose.yml`*
```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: m02-rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: enterprise
      RABBITMQ_DEFAULT_PASS: securepassword

  redis:
    image: redis:7.2-alpine
    container_name: m02-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
```

#### Langkah 2: Setup Dependency
*File: `hands-on/m02/requirements.txt`*
```text
Django>=5.0,<5.1
celery[redis]>=5.3.6
amqp>=5.2.0
redis>=5.0.1
asgiref>=3.7.2
uvicorn>=0.28.0
```

#### Langkah 3: Setup Celery Initialization
*File: `hands-on/m02/enterprise_async/celery.py`*
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_async.settings')

app = Celery('enterprise_async')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Routing Declarations
app.conf.task_routes = {
    'tasks_infra.tasks.critical_transaction_task': {'queue': 'critical'},
    'tasks_infra.tasks.batch_export_task': {'queue': 'bulk'},
}

# Worker Settings
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

app.autodiscover_tasks()
```

#### Langkah 4: Hubungkan ke Django Settings
*File: `hands-on/m02/enterprise_async/settings.py`* (Tambahkan di bagian bawah)
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'secret-production-test-key-replace-in-env'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tasks_infra.apps.TasksInfraConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'enterprise_async.urls'
WSGI_APPLICATION = 'enterprise_async.wsgi.application'
ASGI_APPLICATION = 'enterprise_async.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# BROKER & CACHE TOPOLOGY
CELERY_BROKER_URL = 'amqp://enterprise:securepassword@localhost:5672//'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
REDIS_LOCK_URL = 'redis://localhost:6379/2'

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/0",
    }
}
```

#### Langkah 5: Implementasikan Task Resilien
*File: `hands-on/m02/tasks_infra/tasks.py`*
```python
import time
import logging
from celery import shared_task
from django.db import close_old_connections

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3
)
def critical_transaction_task(self, tracking_id: str, amount: float):
    close_old_connections()
    logger.info(f"Processing critical transaction: {tracking_id} | Attempt: {self.request.retries}")
    
    # Simulasi I/O
    time.sleep(1)
    
    if amount < 0:
        raise ValueError("Invalid negative settlement value")
        
    return {"status": "SUCCESS", "tracking_id": tracking_id}

@shared_task
def batch_export_task(batch_id: str):
    logger.info(f"Starting long export for batch: {batch_id}")
    time.sleep(5)
    return {"status": "COMPLETED", "batch_id": batch_id}
```

#### Langkah 6: Eksekusi & Pengujian
1. Jalankan infrastructure dependencies:
   ```bash
   cd hands-on/m02/
   docker-compose up -d
   ```
2. Jalankan dua worker pool terpisah secara paralel di terminal berbeda:
   ```bash
   # Terminal 1: Worker spesifik menangani antrean 'critical'
   celery -A enterprise_async worker -Q critical -n worker_critical@%h --concurrency=4 -l info
   
   # Terminal 2: Worker spesifik menangani antrean 'bulk'
   celery -A enterprise_async worker -Q bulk -n worker_bulk@%h --concurrency=2 -l info
   ```
3. Uji pengiriman task via Django Shell:
   ```python
   python manage.py shell
   >>> from tasks_infra.tasks import critical_transaction_task, batch_export_task
   >>> t1 = critical_transaction_task.apply_async(args=["TXN-10001", 250.0], queue="critical")
   >>> t2 = batch_export_task.apply_async(args=["BATCH-99"], queue="bulk")
   >>> t1.get()
   {'status': 'SUCCESS', 'tracking_id': 'TXN-10001'}
   ```

---

### 13. Exercise

#### Tingkat Easy:
* **Tugas**: Tambahkan middleware profiling yang memantau durasi eksekusi ASGI view dan simpan log metrik eksekusi tersebut ke Redis List bernama `metrics:http:latency`.
* **Kriteria Keberhasilan**: Setiap HTTP request yang masuk memicu operasi non-blocking `rpush` ke Redis tanpa mendegradasi waktu respon request utama lebih dari 2ms.

#### Tingkat Medium:
* **Tugas**: Konfigurasikan sistem Dead Letter Queue (DLQ) pada Celery dengan RabbitMQ. Buat skenario di mana task `critical_transaction_task` sengaja dibuat error hingga melampaui `max_retries=3`. Pastikan task yang gagal tersebut otomatis masuk ke antrean `critical.dead_letter`.
* **Kriteria Keberhasilan**: Pesan yang gagal tidak dibuang (*dropped*), melainkan berpindah ke antrean DLQ dan dapat diinspeksi melalui antarmuka web RabbitMQ Management (`http://localhost:15672`).

#### Tingkat Hard:
* **Tugas**: Bangun pipeline Celery Canvas dinamis yang memproses file CSV berisi 50.000 transaksi pembayaran:
  1. *Task 1 (Master)*: Membaca file CSV secara streaming dan membuat *chunk* per 1.000 baris.
  2. *Header (Group Tasks)*: Memvalidasi dan mengenkripsi setiap *chunk* secara paralel.
  3. *Barrier / Reducer (Chord Finalizer)*: Menggabungkan status, menyimpan metadata batch ke database, dan mengirim webhook notifikasi hasil pemrosesan.
  4. Seluruh flow harus tahan terhadap matinya salah satu worker di tengah proses (*fault-tolerant*).
* **Kriteria Keberhasilan**: Memory consumption worker master tidak melebihi 50MB RAM saat membaca dataset besar, dan seluruh sub-task terdistribusi merata ke worker pool.

---

### 14. Challenge

Rancang arsitektur sistem **Distributed Real-Time Leaderboard** untuk turnamen e-sports dengan volume 50.000 events/detik berbasis Django:
1. **Spesifikasi Kebutuhan**:
   * Event skor dikirim oleh client via HTTP POST ke endpoint Django ASGI.
   * Skor harus ter-update pada Redis Sorted Set (`ZADD`) secara near-real-time (sub-100ms).
   * Data tidak boleh hilang jika cluster Redis failover: gunakan mekanisme buffering asynchronous via RabbitMQ/Celery sebagai buffer persistensi ke PostgreSQL (Write-Behind Pattern).
   * Batasi hit ke PostgreSQL agar mutasi database dilakukan secara batch per 5 detik, bukan per single event.
2. **Kondisi Batasan**:
   * Tidak boleh menggunakan blocking ORM calls di main request loop.
   * Harus menangani kegagalan jaringan sementara antara Django dan Redis tanpa menyebabkan request pengguna timeout (graceful degradation ke memory queue).
3. **Output Yang Diharapkan**:
   * Dokumen arsitektur data flow (ASCII Diagram).
   * File implementasi code pipeline (`views.py`, `tasks.py`, `buffers.py`).
   * Rancangan strategi pemulihan bencana (*Disaster Recovery*) jika worker penampung antrean batch down.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan arsitektural utama antara `worker_prefetch_multiplier=1` dan default-nya (`4`) pada Celery?
   * *Jawaban*: Prefetch menentukan berapa banyak task yang ditarik broker dan dicadangkan di memori lokal worker per proses konkurensi. Nilai `1` memastikan worker hanya mengambil task baru seketika setelah task saat ini selesai, menghindari kondisi di mana task komputasi berat tertahan di worker yang sibuk (*starvation*) sementara worker lain idle.
2. Mengapa tidak diperbolehkan melewatkan instansi Django Model Object sebagai argumen fungsi task Celery?
   * *Jawaban*: Karena serialisasi model object menuntut format tidak aman (seperti Pickle), rentan membawa state data usang (*stale*), dan dapat memicu race condition database jika transaksi di view yang memanggil task belum selesai di-*commit*.
3. Apa perbedaan siklus eksekusi antara worker pool `prefork` dan `gevent`?
   * *Jawaban*: `prefork` menggunakan proses sistem operasi independen dengan isolasi memori penuh (ideal untuk CPU-bound task), sedangkan `gevent` menggunakan greenlet (coroutine kooperatif berbasis event loop non-blocking di tingkat user-space) yang mampu meng-handle ribuan koneksi I/O-bound secara bersamaan dalam satu proses.
4. Apa fungsi atribut `thread_sensitive=True` saat membungkus fungsi sinkron menggunakan `sync_to_async` pada Django?
   * *Jawaban*: Menjamin bahwa kode sinkronus (terutama Django ORM) dieksekusi di dalam thread utama yang konsisten bagi thread-sensitive subsystem, mencegah inkonsistensi konteks thread-local, connection handle DB, atau transactional states.
5. Bagaimana Redis mengeksekusi script Lua untuk locking secara atomik?
   * *Jawaban*: Redis mengeksekusi script Lua dalam satu event loop single-threaded secara atomik tanpa interupsi, memastikan tidak ada perintah Redis lain yang bisa berjalan di antara operasi pengecekan (`GET`) dan penghapusan (`DEL`).

#### B. Pertanyaan Intermediate
6. Mengapa kombinasi `acks_late=True` tanpa penanganan task idempoten dianggap berbahaya di sistem finansial?
   * *Jawaban*: Karena jika worker mati secara mendadak setelah operasi bisnis selesai namun sebelum sinyal ACK sampai ke broker, broker akan mengirim ulang (*re-queue*) pesan tersebut ke worker lain, memicu eksekusi ganda seperti pemotongan saldo atau pengiriman dana berulang (*double spend*).
7. Bagaimana algoritma probabilistik XFetch menyelesaikan masalah Cache Stampede dibandingkan Distributed Mutex Lock?
   * *Jawaban*: Distributed Mutex menahan request lain hingga satu proses selesai mengomputasi data baru (dapat memicu antrean thread/koneksi), sedangkan XFetch memicu komputasi ulang secara asinkron di background secara probabilistik sebelum TTL habis, sehingga pengguna selalu mendapatkan cache data tanpa pernah mengalami latency freeze.
8. Apa yang terjadi jika eksekusi task Celery melampaui `task_time_limit` yang dikonfigurasi?
   * *Jawaban*: Celery worker supervisor akan secara paksa menghentikan subproses yang mengeksekusi task tersebut menggunakan sinyal kernel `SIGKILL`, menghentikan eksekusi seketika tanpa eksekusi blok `finally` atau cleanup handler.
9. Jelaskan peran `reject_on_worker_lost=True` dalam Celery configuration!
   * *Jawaban*: Menginstruksikan broker untuk menolak (*reject*) dan mengembalikan pesan ke antrean (*re-queue*) atau mengirimkannya ke Dead Letter Exchange apabila worker proses mendadak crash (misal: akibat OOM atau node crash fisik) saat sedang mengeksekusi task dengan late acknowledgement.
10. Dalam kondisi apa kita harus mengisolasi task ke dalam antrean (*queue*) yang berbeda secara fisik?
    * *Jawaban*: Saat terdapat perbedaan karakteristik workload yang drastis (misal: task I/O cepat 50ms vs export PDF yang memakan waktu 3 menit), task dengan SLA berbeda (pembayaran real-time vs batch email digest mingguan), atau task yang membutuhkan pool type berbeda (`gevent` vs `prefork`).

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah sistem settlement memproses batch ribuan order menggunakan Celery `chord`. Tiba-tiba task callback aggregasi akhir tidak pernah tereksekusi, meskipun seluruh task di header berstatus `SUCCESS`. Apa kemungkinan penyebabnya pada sisi Result Backend dan bagaimana mitigasinya?
    * *Analisis & Solusi*:
      Penyebab paling umum adalah *eviction* atau hilangnya metadata tracking chord pada result backend (Redis). Celery chord melacak jumlah task yang tersisa menggunakan set/counter di Redis. Jika Redis kehabisan memori (*out of memory*) dan kebijakan eviction diset ke `allkeys-lru`, atau jika TTL task header kedaluwarsa sebelum seluruh task paralel selesai, state koordinasi chord akan terhapus. Solusinya: Pisahkan instance Redis Result Backend dari Cache instance biasa, gunakan kebijakan memory `noeviction`, dan pastikan `result_expires` diset lebih lama dari estimasi durasi terpanjang seluruh subtask di header.
12. **Skenario 2**: Node produksi Django ASGI mengalami peningkatan tajam pada *CPU Context Switching* dan response latency drop drastis ketika beban request naik dari 500 menjadi 4.000 QPS. Server memiliki 16 core CPU. Konfigurasi `ASGI_THREADS` diatur ke 1.000. Analisis apa yang terjadi dan bagaimana formula optimalnya?
    * *Analisis & Solusi*:
      Pengaturan `ASGI_THREADS=1000` memicu *thread thrashing*. Dengan 16 core CPU fisik, mengalokasikan ribuan OS thread aktif memaksa kernel melakukan time-slicing context switching yang membuang siklus CPU hanya untuk overhead switching register alih-alih komputasi riil. Formula tuning: batasi `ASGI_THREADS` pada kisaran $4 \times \text{Core CPU}$ hingga $8 \times \text{Core CPU}$ (e.g., 64–128 threads), dan pastikan bottleneck database diatasi melalui connection pooling terpusat (seperti PgBouncer) daripada menimbun thread di app layer.
13. **Skenario 3**: Worker pool Celery yang menangani notifikasi push berbasis library HTTP client sinkron tiba-tiba berhenti memproses antrean pesan baru (*hung* total) tanpa crash log, CPU worker 0%, dan status queue RabbitMQ terus bertumpuk (*unacked*). Apa penyebab utama masalah ini dan bagaimana memperbaikinya?
    * *Analisis & Solusi*:
      Worker mengalami *Socket Hang-up / Infinite Blocking I/O*. Library HTTP sinkron melakukan panggilan network ke server pihak ketiga tanpa konfigurasi timeout eksplisit di tingkat socket. Koneksi TCP menggantung selamanya tanpa diputus oleh OS. Karena seluruh worker processes/threads tertahan menunggu socket read, antrean tidak bergerak. Solusinya: Selalu konfigurasikan `timeout=(connect_timeout, read_timeout)` secara eksplisit di seluruh client HTTP/socket, dan aktifkan `task_soft_time_limit` serta Celery socket timeouts secara sistemik.

---

### 16. Summary

* Pemrosesan terdistribusi modern di Django menuntut isolasi mutlak antara **I/O Synchronous/Asynchronous** pada web tier dan **Background Workload** pada worker tier.
* Penggunaan `sync_to_async` adalah mekanisme jembatan sementara untuk ORM blocking call; kapasitas thread-pool harus dikontrol ketat untuk mencegah thrashing OS resource.
* **Celery Execution Semantics** yang resilien mewajibkan implementasi `acks_late=True`, `reject_on_worker_lost=True`, penanganan *idempotensi* mutlak (state locks), serta isolasi antrean berbasis karakteristik beban task (*workload segregation*).
* Caching di level enterprise tidak sekadar menggunakan operasi `get`/`set` standar, melainkan memerlukan perlindungan struktural terhadap fenomena konkurensi ekstrem seperti *Cache Stampede* menggunakan algoritma probabilistik (*XFetch*) atau *Distributed Mutual Exclusion* (Redlock).