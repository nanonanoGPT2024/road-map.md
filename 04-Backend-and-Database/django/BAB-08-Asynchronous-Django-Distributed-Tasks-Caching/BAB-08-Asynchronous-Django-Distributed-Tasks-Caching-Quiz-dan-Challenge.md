# BAB-08-Asynchronous-Django-Distributed-Tasks-Caching: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan konsep, arsitektur, dan implementasi praktis terkait Asynchronous Django (ASGI), Distributed Task Queue (Celery & Message Broker), serta Advanced Caching Strategy (Redis & Django Cache Framework).

---

## Bagian 1: Basic Questions (5 Pertanyaan)

### Pertanyaan 1: Perbedaan Mendasar WSGI vs ASGI di Django
Jelaskan perbedaan struktural antara WSGI (`wsgi.py`) dan ASGI (`asgi.py`) dalam konteks siklus hidup request Django serta penanganan koneksi I/O-bound!

#### Jawaban:
- **WSGI (Web Server Gateway Interface):** Beroperasi secara sinkron (*synchronous*) berbasis paradigma *one thread/process per request*. WSGI memblokir worker thread ketika terjadi operasi I/O (seperti query database lambat atau panggilan HTTP pihak ketiga), sehingga membatasi konkurensi server pada jumlah worker/thread yang tersedia (Gunicorn worker pool).
- **ASGI (Asynchronous Server Gateway Interface):** Standar modern yang dibangun di atas Python `asyncio`. ASGI mendukung penanganan asynchronous request secara native, WebSockets, Server-Sent Events (SSE), dan background coroutines dalam satu event loop. ASGI memungkinkan ribuan koneksi I/O-bound idle/menunggu dipertahankan secara bersamaan tanpa mengalokasikan satu thread fisik penuh untuk setiap koneksi (misalnya menggunakan Daphne atau Uvicorn).

---

### Pertanyaan 2: Fungsi Adaptor `sync_to_async` dan `async_to_sync` dari `asgiref`
Mengapa kita tidak boleh memanggil Django ORM query langsung di dalam `async def` view tanpa pembungkus, dan apa peran `sync_to_async`?

#### Jawaban:
Sebagian besar engine Django ORM secara historis bersifat sinkron dan melakukan pemblokiran soket database secara langsung. Jika dipanggil langsung di dalam loop async (`async def`), eksekusi ORM sinkron akan memblokir thread event loop utama, menggagalkan konkurensi non-blocking. Django menyediakan `SynchronousOnlyOperation` exception guard untuk mencegah hal ini.
- **`sync_to_async`:** Menjalankan operasi sinkron (seperti ORM klasik atau library Python blocking) di dalam thread pool terpisah (`ThreadPoolExecutor`), lalu mengembalikan hasilnya ke coroutine async tanpa memblokir event loop utama.
- **`async_to_sync`:** Memungkinkan kode sinkron (misalnya Celery task sinkron atau sinyal Django standar) memanggil fungsi async dengan membungkus eksekusi ke dalam event loop lokal sementara.

---

### Pertanyaan 3: Peran Message Broker dan Result Backend pada Celery
Dalam arsitektur distributed task processing Celery, jelaskan fungsi Message Broker (contoh: RabbitMQ/Redis) dan Result Backend!

#### Jawaban:
- **Message Broker:** Bertindak sebagai antrean perantara (*message queue buffer*) yang menerima serialisasi payload task dari Django application (producer) dan mendistribusikannya ke Celery worker pool (consumer). Broker menjamin persistensi antrean dan decoupling waktu eksekusi.
- **Result Backend:** Tempat penyimpanan sementara status dan return value dari task yang telah dieksekusi (contoh: status `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`, dan return payload). Jika aplikasi Django tidak membutuhkan pengecekan `AsyncResult.get()`, Result Backend dapat dimatikan (`result_backend = None`) untuk menghemat resource dan I/O broker.

---

### Pertanyaan 4: Perbedaan Cache Backend `DummyCache`, `LocMemCache`, dan `RedisCache`
Sebutkan karakteristik dan skenario penggunaan yang tepat untuk `DummyCache`, `LocMemCache`, dan `RedisCache` pada Django!

#### Jawaban:
- **`DummyCache`:** Implementasi interface cache tanpa penyimpanan nyata (semua get return `None`). Digunakan untuk environment development/testing guna menonaktifkan caching tanpa mengubah kode aplikasi.
- **`LocMemCache`:** Caching di memori lokal proses Python yang sedang berjalan. Cepat dan thread-safe, namun tidak terbagi antar proses (multi-worker Gunicorn memiliki cache independen) dan hilang jika proses restart. Cocok untuk pengujian lokal single-process.
- **`RedisCache`:** Distributed memory cache eksternal. Mendukung multi-process, multi-server instance, persistent memory management, evictions LRU/LFU, serta data structures native. Standar industri untuk production environment.

---

### Pertanyaan 5: Risiko `transaction.on_commit` saat Memanggil Celery Tasks
Mengapa memanggil `task.delay(instance.id)` langsung di dalam blok `transaction.atomic()` sebelum commit selesai merupakan anti-pattern berbahaya?

#### Jawaban:
Kondisi ini memicu race condition: Celery worker dapat mengambil task dari message broker dan mengeksekusinya lebih cepat daripada database commit transaksi Django selesai di connection thread utama. Akibatnya, worker mencoba query `Model.objects.get(id=instance.id)` dan mendapati `DoesNotExist` exception karena record belum benar-benar ada di database (uncommitted data). Solusi tepatnya adalah membungkus pemicu task dengan `transaction.on_commit(lambda: task.delay(instance.id))`.

---

## Bagian 2: Intermediate Questions (5 Pertanyaan)

### Pertanyaan 6: Cache Stampede (Thundering Herd Problem) & Solusinya
Jelaskan fenomena *Cache Stampede* yang terjadi saat key cache dengan traffic tinggi mengalami *expiration*, serta jelaskan 2 strategi mitigasinya di Django!

#### Jawaban:
- **Fenomena:** Terjadi ketika cache key yang sangat sering diakses kedaluwarsa secara tiba-tiba di saat beban traffic tinggi. Ratusan atau ribuan concurrent request secara serentak mendapati *cache miss* dan bersamaan mengeksekusi query database kalkulasi berat yang sama, memicu lonjakan CPU 100% dan connection pool exhaustion pada database.
- **Strategi Mitigasi:**
  1. **Distributed Mutex Lock (Redis Lock):** Saat cache miss, request pertama mengakuisisi lock (`redis.lock("lock:key", timeout=5)`). Hanya pemegang lock yang menjalankan query database dan mengisi ulang cache; request lain menunggu sebentar atau membaca *stale data*.
  2. **Probabilistic Early Expiration (XFetch algorithm) / Background Warming:** Memperbarui cache di latar belakang menggunakan task Celery terjadwal sebelum TTL habis secara natural, atau mengevaluasi probabilitas refresh beberapa detik sebelum expiration.

---

### Pertanyaan 7: Idempotency pada Celery Tasks
Mengapa distributed task harus dirancang secara *idempotent*? Berikan contoh implementasi penanganan retries yang aman!

#### Jawaban:
Dalam jaringan terdistribusi, kegagalan acknowledge (ACK lost), restart worker, atau network partition dapat menyebabkan task yang sama dikirim atau dieksekusi lebih dari satu kali (*at-least-once delivery*). Jika task melakukan mutasi finansial atau pengiriman notifikasi tanpa idempotensi, akan terjadi duplikasi pembayaran atau spam email.

**Contoh Implementasi Idempotensi:**
```python
from celery import shared_task
from django.db import transaction
from myapp.models import Payment, IdempotencyLog

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_payment_task(self, payment_id, idempotency_key):
    try:
        with transaction.atomic():
            log, created = IdempotencyLog.objects.select_for_update().get_or_create(
                key=idempotency_key,
                defaults={'status': 'PROCESSING'}
            )
            if not created and log.status in ['PROCESSING', 'COMPLETED']:
                return f"Task skipped, duplicate key: {idempotency_key}"
            
            payment = Payment.objects.select_for_update().get(id=payment_id)
            if payment.status != 'PENDING':
                return "Already processed"
            
            payment.charge_gateway()
            payment.status = 'SUCCESS'
            payment.save()
            
            log.status = 'COMPLETED'
            log.save()
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

### Pertanyaan 8: Async Database Querying di Django 4.2+ & Django 5.x
Bagaimana Django menangani ORM async secara native pada versi modern (seperti `aaggregate`, `afirst`, `aget_object_or_404`), dan apa batasannya?

#### Jawaban:
Django 4.1+ dan 5.x memperkenalkan async interface native pada QuerySet dengan prefiks `a` (seperti `afirst()`, `acount()`, `aexists()`, `aget()`, `asave()`, `adelete()`, dan asynchronous iteration `async for item in queryset`).
- **Mekanisme:** Di bawah permukaan, Django membungkus operasi database driver blocking ke thread pool khusus database connection secara otomatis tanpa mengharuskan developer menulis `sync_to_async` manual pada setiap query tunggal.
- **Batasan:** Lazy evaluation tetap membutuhkan perhatian. Mengakses foreign key relasi secara lazy (misal `book.author.name` tanpa `select_related`) di async context akan memicu exception sinkron `SynchronousOnlyOperation`. Prefetching dan foreign key traversal harus diselesaikan secara eksplisit di awal query.

---

### Pertanyaan 9: Cache Invalidation Pattern (Cache-Aside vs Event-Driven Invalidation)
Bandingkan pola *Cache-Aside* dengan *Event-Driven Invalidation* menggunakan Django Signals! Apa potensi jebakan (*pitfall*) jika sinyal `post_save` digunakan sembarangan untuk menghapus cache?

#### Jawaban:
- **Cache-Aside (Lazy Loading):** Aplikasi mencari data di cache. Jika miss, aplikasi membaca DB, menulis ke cache, dan mengembalikan data. Invalidation dilakukan saat terjadi mutasi data.
- **Event-Driven Invalidation (Django Signals):** Sinyal `post_save` dan `post_delete` mendengarkan perubahan model dan menghapus key terkait (`cache.delete(key)`).
- **Pitfall:**
  1. **Race Condition Transaksi:** Jika `post_save` menghapus cache sebelum transaksi database selesai di-commit ke disk, concurrent request lain bisa membaca database yang belum ter-commit atau membaca data lama dan mengisi ulang cache dengan nilai kadaluwarsa.
  2. **Signal Cascading / Invalidation Storm:** Update massal via `QuerySet.update()` atau bulk operation tidak memicu sinyal `post_save`, menyebabkan data cache menjadi basi (*desynchronization*). Sebaliknya, bulk save yang memicu loop individual signal akan membanjiri Redis dengan ribuan request delete.

---

### Pertanyaan 10: Routing Task dan Prioritas Antrean di Celery
Bagaimana cara memisahkan worker untuk task dengan prioritas tinggi (*critical payments/OTP*) dan task komputasi berat (*batch PDF report generation*) di Django Celery?

#### Jawaban:
Pemisahan dilakukan menggunakan **Task Routing** pada konfigurasi Celery:
```python
# settings.py
CELERY_TASK_ROUTES = {
    'myapp.tasks.send_urgent_otp': {'queue': 'high_priority'},
    'myapp.tasks.generate_heavy_pdf_report': {'queue': 'batch_low_priority'},
}
```
Worker dijalankan pada instance atau container terpisah dengan binding antrean spesifik:
- Worker 1 (Dedicated High Priority):
  `celery -A myproject worker -Q high_priority -c 8`
- Worker 2 (Dedicated Low Priority/Background):
  `celery -A myproject worker -Q batch_low_priority -c 2`
Dengan isolasi ini, antrean laporan PDF yang menumpuk tidak akan menghalangi atau memperlambat pengiriman OTP critical.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Worker OOM (Out Of Memory) dan Memory Leak pada Celery Batch Processing
**Konteks Masalah:**
Sebuah e-commerce besar menggunakan Celery untuk memproses sinkronisasi stok jutaan produk setiap tengah malam. Setelah berjalan selama 45 menit, container worker Celery mati secara mendadak dengan sinyal Linux `SIGKILL (OOM Killer)`. Log menunjukkan penggunaan RAM terus meningkat secara linier seiring jumlah task yang dieksekusi.

**Tugas Anda:**
1. Analisis akar penyebab kebocoran memori ini di level proses Python dan Django!
2. Berikan konfigurasi operasional Celery dan kode perbaikan untuk menjamin worker tetap stabil!

#### Solusi Rekomendasi:
1. **Akar Masalah:**
   - Python memory allocator (`glibc malloc`) tidak langsung mengembalikan *fragmented memory* ke sistem operasi setelah alokasi objek masif dalam satu proses jangka panjang.
   - Jika `DEBUG = True` aktif di production, Django menyimpan seluruh history query SQL di `django.db.connection.queries`, yang menyebabkan akumulasi memori tak terbatas.
   - Penggunaan ORM `Model.objects.all()` tanpa iterator membaca seluruh jutaan record ke dalam memori Python sekaligus.
2. **Langkah Perbaikan:**
   - Gunakan `iterator(chunk_size=2000)` dan `only()` / `values()` untuk membatasi objek instance di memori.
   - Pastikan `settings.DEBUG = False` di environment worker.
   - Konfigurasikan Celery Worker Recycling di `settings.py`:
     ```python
     # Memaksa worker child process restart setelah memproses 500 task
     CELERY_WORKER_MAX_TASKS_PER_CHILD = 500
     # Membatasi konsumsi memori fisik worker (misal: 300MB) sebelum digantikan worker baru
     CELERY_WORKER_MAX_MEMORY_PER_CHILD = 307200  # in KB
     ```

---

### Skenario 2: Deadlock & Spike CPU Redis Akibat Pattern Invalidation yang Buruk
**Konteks Masalah:**
Sebuah platform media daring menggunakan Redis sebagai cache backend. Setiap kali seorang editor mempublikasikan artikel baru, fungsi berikut dijalankan:
```python
# Anti-pattern di production
keys = redis_client.keys("cache:article:*")
for k in keys:
    redis_client.delete(k)
```
Saat traffic situs melonjak, server Redis mengalami spike CPU 100%, latency melonjak dari 1ms ke 8000ms, dan request HTTP Django timeout secara masif (*Cascading Failure*).

**Tugas Anda:**
1. Jelaskan mengapa perintah `keys()` melumpuhkan Redis!
2. Rancang ulang skema caching dan teknik invalidation yang efisien dan aman untuk production!

#### Solusi Rekomendasi:
1. **Analisis Kegagalan:**
   - Redis adalah arsitektur *single-threaded event loop* untuk eksekusi perintah data. Perintah `KEYS` memiliki kompleksitas waktu $O(N)$ di mana $N$ adalah seluruh key di database Redis. Jika terdapat jutaan key, Redis akan terblokir sepenuhnya selama beberapa detik, tidak dapat memproses read/write lain, memicu timeout berantai di seluruh aplikasi.
2. **Solusi Arsitektural:**
   - **Gunakan Cache Versioning (Key Prefix Increment):**
     Daripada menghapus jutaan key secara fisik, gunakan versi global yang disimpan di satu key kecil:
     ```python
     def get_article_cache_version():
         return cache.get_or_set("article_version_tracker", 1)

     def invalidate_all_article_caches():
         cache.incr("article_version_tracker")
     ```
     Setiap key artikel dibentuk dengan prefix versi: `f"article:{version}:{article_id}"`. Ketika versi di-increment, seluruh key lama secara otomatis menjadi *unreachable* (akan dibersihkan oleh kebijakan LRU Redis `maxmemory-policy volatile-lru` secara alami) dengan biaya eksekusi hanya $O(1)$.
   - Jika harus scanning manual, gunakan iterator non-blocking `SCAN` / `SSCAN` dengan parameter `COUNT` terukur, bukan `KEYS`.

---

### Skenario 3: WebSocket Connection Drop dan Connection Exhaustion pada ASGI Channels
**Konteks Masalah:**
Aplikasi live auction Django menggunakan Django Channels dan Daphne untuk melayani 50.000 concurrent WebSockets. Ketika pelelangan barang unggulan dimulai, koneksi WebSocket massal mengalami disconnection mendadak, log Daphne dipenuhi pesan `asyncio.TimeoutError`, dan database PostgreSQL menolak koneksi baru dengan error `FATAL: remaining connection slots are reserved for non-replication superuser connections`.

**Tugas Anda:**
1. Mengapa koneksi WebSocket persisten menyebabkan connection pool database jebol?
2. Bagaimana arsitektur yang benar untuk memisahkan lifecycle WebSocket dan database I/O?

#### Solusi Rekomendasi:
1. **Akar Masalah:**
   - Consumer WebSocket mempertahankan koneksi socket terbuka selama berjam-jam. Jika consumer membuka koneksi database saat `connect()` dan tidak menutupnya atau menyimpannya di instance scope, setiap socket yang terhubung akan menahan satu slot koneksi database. PostgreSQL umumnya dibatasi 100–500 koneksi fisik. Menampung 50.000 koneksi langsung ke DB pasti menyebabkan *connection exhaustion*.
2. **Arsitektur Solusi:**
   - **Tutup Koneksi Database Segera (Connection Pooling & Ephemeral I/O):**
     Implementasikan PgBouncer di depan PostgreSQL dengan mode *transaction pooling*.
     Pastikan consumer tidak menahan status DB. Panggil DB query secara ad-hoc menggunakan `database_sync_to_async` dan tutup koneksi setelah pembacaan:
     ```python
     from channels.db import database_sync_to_async
     from django.db import close_old_connections

     class AuctionConsumer(AsyncWebsocketConsumer):
         async def connect(self):
             await self.accept()

         @database_sync_to_async
         def get_bid_data(self, auction_id):
             close_old_connections()
             try:
                 return Auction.objects.values('current_price').get(id=auction_id)
             finally:
                 close_old_connections()
     ```
   - **Channel Layer Terisolasi di Redis:**
     Gunakan Redis Channel Layer (`channels_redis`) dengan cluster terpisah dari general cache untuk broadcast event secara terdistribusi tanpa menyentuh database sama sekali saat event harga di-broadcast ke room group.

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Sistem Resilient Async Rate-Limiting & Offloaded Job Processing
Bangun arsitektur mini backend di Django yang mengintegrasikan Django Cache, Async Views, dan Celery Task dengan kriteria ketat berikut:

#### Spesifikasi Kebutuhan:
1. **Endpoint Async Non-Blocking (`POST /api/v1/export-report/`):**
   - Menerima payload JSON: `{"report_type": "sales", "start_date": "2026-01-01", "end_date": "2026-01-31"}`.
   - View harus diimplementasikan secara async (`async def export_report_view(request)`).
2. **Rate Limiting Terdistribusi berbasis Redis:**
   - Setiap `user_id` dibatasi maksimal **5 kali permintaan export per menit**.
   - Gunakan atomic counter Redis via Django cache (`cache.incr` atau atomic Lua script). Jika kuota habis, kembalikan HTTP `429 Too Many Requests`.
3. **Offloading ke Celery dengan Idempotency Key:**
   - Generate hash SHA-256 dari `(user_id, report_type, start_date, end_date)`.
   - Cek ke cache apakah hash tersebut sedang dalam status `PROCESSING`. Jika ya, kembalikan status `409 Conflict` atau return task ID yang sedang berjalan.
   - Panggil Celery task `generate_export_file` menggunakan `transaction.on_commit`.
4. **Celery Worker & Notification Simulation:**
   - Task melakukan kalkulasi komputasi (simulasi dengan progress tracking).
   - Simpan status penyelesaian di Redis cache selama 1 jam (`EXPIRE 3600`).

#### Kriteria Keberhasilan:
- Tidak ada operasi blocking di dalam thread async view.
- Rate limiting bebas race condition di lingkungan concurrent.
- File code terstruktur rapi, lengkap dengan error handling, types hint, dan clean logging.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk memverifikasi kesiapan operasional Anda sebelum melangkah ke modul berikutnya:

- [ ] Memahami perbedaan arsitektur event loop ASGI (`uvicorn`/`daphne`) dibanding WSGI pre-fork model (`gunicorn`).
- [ ] Mampu mengidentifikasi kapan harus menggunakan `sync_to_async` vs `async_to_sync` serta bahaya pemanggilan ORM blocking di async context.
- [ ] Memahami lifecycle Celery task, prefetch multiplier, acknowledgement modes (`acks_late`), dan penanganan worker recycling (`max_tasks_per_child`).
- [ ] Menguasai integrasi `transaction.on_commit` untuk mencegah race condition antara RDBMS commit dan Task consumption di broker.
- [ ] Mampu merancang skema caching berlapis (Cache-Aside, Write-Through, Versioned Keys) di atas Redis.
- [ ] Mampu mendiagnosis dan memitigasi Thundering Herd Problem (Cache Stampede) menggunakan distributed locking.
- [ ] Memahami strategi isolasi queue Celery (High Priority vs Low Priority/Batch).
- [ ] Mengetahui cara memonitor Celery dan Redis di lingkungan production (Celery Flower, Prometheus metrics, Redis INFO command).
