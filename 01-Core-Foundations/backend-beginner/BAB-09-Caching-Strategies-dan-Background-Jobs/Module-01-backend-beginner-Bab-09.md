# KURIKULUM BACKEND-BEGINNER
## KATEGORI: 01-CORE-FOUNDATIONS

---

## SEKSI 01 — IDENTITAS MODUL

| Atribut | Rincian |
| :--- | :--- |
| **Track** | Backend Engineering |
| **Tingkat Kesulitan** | Beginner to Early-Intermediate |
| **Kategori** | 01-Core-Foundations |
| **Nomor Bab** | 09 |
| **Nomor Modul** | 01 |
| **Judul Modul** | Caching Strategies & Background Job Basics |
| **Prasyarat Pengetahuan** | HTTP Lifecycle, Relational/NoSQL Database Basics, RESTful API Fundamentals, Asynchronous Programming (Promises/Async-Await) |
| **Estimasi Waktu Penyelesaian** | 6 - 8 Jam Pembelajaran Mandiri / Workshop |
| **Target Teknologi** | Node.js (TypeScript/JavaScript), Redis, Message Queue/Worker Architecture |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendiagnosis Bottleneck Kinerja (Cognitive Level: C4 - Analyzing)**: Mengidentifikasi kapan suatu operasi I/O (Database Read, External API) memerlukan caching dan kapan operasi berat (PDF generation, Email sending) harus dipindahkan ke background job.
2. **Mengimplementasikan Pola Caching (Cognitive Level: C3 - Applying)**: Membangun pola *Cache-Aside* (*Lazy Loading*) menggunakan Redis dengan konfigurasi *Time-To-Live* (TTL) yang tepat serta mekanisme *Cache Invalidation*.
3. **Membangun Sistem Pemrosesan Asinkron (Cognitive Level: C3 - Applying)**: Mengonstruksi pola arsitektur *Producer-Consumer* menggunakan antrean pesan (*Message Queue*) untuk memisahkan siklus HTTP Request-Response dari eksekusi tugas intensif.
4. **Mengevaluasi Trade-Offs Desain Sistem (Cognitive Level: C5 - Evaluating)**: Mengukur konsistensi data (*Eventual Consistency* vs *Strong Consistency*) dan menerapkan strategi penanganan kegagalan antrean seperti *Retry Strategy*, *Exponential Backoff*, dan *Dead-Letter Queue* (DLQ).
5. **Menerapkan Idempotensi Worker (Cognitive Level: C3 - Applying)**: Merancang eksekusi *background job* yang tahan terhadap duplikasi data melalui penggunaan *Idempotency Keys*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Permintaan Klien (HTTP Request)]
               │
               ▼
    ┌───────────────────────┐
    │  Web Server / API GW  │
    └──────────┬────────────┘
               │
      ┌────────┴───────────────────────────┐
      │                                    │
[Operasi Baca / Query]            [Operasi Intensif / Tulis]
      │                                    │
      ▼                                    ▼
┌──────────────┐                  ┌──────────────────┐
│ Caching Layer│                  │ Message Producer │
│ (e.g., Redis)│                  └────────┬─────────┘
└──────┬───────┘                           │ (Enqueue Job)
       │                                   ▼
 [Cache Hit / Miss]               ┌──────────────────┐
       │                          │  Message Broker  │
       ▼                          │ (Queue Storage)  │
┌──────────────┐                  └────────┬─────────┘
│ Primary DB   │                           │ (Dequeue Job)
│ (Read / Sync)│                           ▼
└──────────────┘                  ┌──────────────────┐
                                  │ Background Worker│
                                  │  (Consumer Pool) │
                                  └────────┬─────────┘
                                           │
                                  ┌────────┴─────────┐
                                  │                  │
                                  ▼                  ▼
                           ┌──────────────┐   ┌──────────────┐
                           │ External API │   │  Primary DB  │
                           │(SMTP, Payment│   │ (Heavy Write)│
                           └──────────────┘   └──────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem backend monolitik tahap awal, hampir seluruh logika bisnis dijalankan secara **sinkron (*synchronous*)**. Saat sebuah permintaan HTTP datang, server memanggil basis data, melakukan pengolahan data, menghubungi integrasi pihak ketiga, dan baru memberikan respons kepada klien.

Pola sinkron ini memicu dua masalah kritikal pada skala produksi:

1. **Database Exhaustion**: Permintaan pembacaan (*read queries*) yang berulang pada data yang jarang berubah (seperti profil produk, katalog, atau konfigurasi aplikasi) membebani pool koneksi basis data. Hal ini menyebabkan peningkatan latency (p99) dan pemborosan komputasi database.
2. **HTTP Latency Blockage**: Ketika pengguna melakukan pendaftaran akun, aplikasi sering kali perlu mengeksekusi operasi sekunder: mengirim email verifikasi, membuat folder di cloud storage, dan memicu webhook analitik. Jika server mengeksekusi seluruh rantai ini di dalam siklus HTTP, waktu respons pengguna dapat melonjak dari 50ms menjadi 3-5 detik. Lebih fatal lagi, jika penyedia layanan email (*third-party*) sedang *down* atau mengalami latensi tinggi, permintaan pendaftaran pengguna akan mengalami *timeout* atau gagal (*cascade failure*).

Penerapan **Caching** membebaskan basis data dari beban kueri repetitif dengan menyimpan *state* sementara di media penyimpanan berkecepatan tinggi (RAM). Sementara itu, **Background Jobs** memutus keterikatan siklus hidup HTTP dari tugas-tugas berat melalui pendekatan *fire-and-forget* atau *asynchronous processing*, memastikan aplikasi tetap responsif dengan SLA ketersediaan yang tinggi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Caching

Caching adalah teknik menyimpan salinan data sementara di media akses cepat (biasanya *in-memory* seperti RAM) sehingga permintaan berikutnya terhadap data yang sama dapat dilayani lebih cepat daripada mengambilnya kembali dari media penyimpanan utama (Disk/SSD Database).

* **In-Memory Cache (Local)**: Cache disimpan langsung di memori aplikasi berjalan (misal: objek internal di Node.js memory). Cepat, namun tidak dapat dibagi antar multiple instances aplikasi (*node instance*).
* **Distributed Cache**: Cache disimpan di klaster terpisah (contoh: Redis, KeyDB, Memcached). Dapat diakses bersama oleh ratusan instance server aplikasi tanpa data inkonsistensi antar-node.

#### Strategi Caching Populer:
* **Cache-Aside (Lazy Loading)**: Aplikasi membaca data ke cache terlebih dahulu. Jika tidak ada (*Cache Miss*), aplikasi mengambil dari database, menyimpannya di cache, lalu mengembalikannya ke pengguna.
* **Write-Through**: Aplikasi menulis data ke cache dan database secara bersamaan sebelum mengembalikan respons sukses.
* **Write-Back (Write-Behind)**: Aplikasi menulis data ke cache terlebih dahulu dan langsung merespons klien. Worker terpisah kemudian menyinkronkan data tersebut ke database secara asinkron.

### 2. Background Jobs & Message Queues

Background Job adalah eksekusi instruksi komputasi di luar alur utama siklus hidup HTTP Request-Response. Sistem ini dibangun di atas konsep **Producer-Consumer**:

* **Producer**: Server API yang menerima permintaan HTTP, membungkus tugas tersebut menjadi sebuah objek data (*Payload/Job*), lalu memasukkannya ke dalam antrean (*Enqueue*).
* **Message Broker / Queue**: Komponen yang bertindak sebagai buffer antrean sementara berbasis FIFO (*First-In, First-Out*), seperti Redis Streams/Lists, RabbitMQ, atau AWS SQS.
* **Consumer / Worker**: Proses terpisah (dapat berjalan di server atau kontainer berbeda) yang secara konsisten memonitor antrean, mengambil tugas (*Dequeue*), dan mengeksekusinya hingga selesai.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Alur Operasional 1: Cache-Aside Pattern

```
Klien -> (1) Request Data -> API Server
API Server -> (2) Check Key in Redis
  ├─ [KONDISI: CACHE HIT]
  │     └─ Redis -> (3a) Return Cached Data -> API Server
  │
  └─ [KONDISI: CACHE MISS]
        ├─ API Server -> (3b) Query Primary DB
        ├─ Primary DB -> (4b) Return Raw Row
        ├─ API Server -> (5b) SET Key in Redis with TTL
        └─ API Server -> (6b) Return Data to Client
```

1. **TTL (Time-To-Live)**: Setiap kunci yang dimasukkan ke cache wajib memiliki batas waktu kedaluwarsa. Jika data tidak pernah diakses melampaui rentang TTL, sistem cache otomatis menghapusnya melalui mekanisme *eviction policy* (misal: LRU - *Least Recently Used*).
2. **Cache Invalidation**: Jika terjadi pembaruan (*Update/Delete*) data di Primary DB, aplikasi wajib menghapus atau memperbarui kunci terkait di Redis (*Evict/Purge*).

### Alur Operasional 2: Asynchronous Job Processing

```
Klien -> (1) POST /api/v1/reports -> API Server
API Server -> (2) Insert Pending Record to DB
API Server -> (3) Enqueue Job Payload to Queue (Redis/RabbitMQ)
API Server -> (4) Return 202 Accepted (Job ID: "xyz") -> Klien
                                                      [HTTP Connection Closed]

                      [BACKGROUND EXECUTION]
Worker Engine -> (5) Polling / Dequeue Job "xyz" from Queue
Worker Engine -> (6) Process Heavy Aggregation Query & Compile File
Worker Engine -> (7) Upload to Object Storage
Worker Engine -> (8) Update Job Status to "Completed" in DB
```

1. **Status Polling / Webhook**: Klien menerima status `202 Accepted` bersama dengan `job_id`. Klien dapat memeriksa status pekerjaan secara berkala (*polling*) atau menunggu notifikasi via WebSocket/Webhook.
2. **Failure & Retry Policy**: Jika Worker gagal mengeksekusi tugas (misalnya karena gangguan jaringan eksternal), pesan akan dikembalikan ke antrean dengan jeda waktu terukur (*Exponential Backoff*). Jika batas percobaan maksimal terlampaui, pesan dialihkan ke **Dead-Letter Queue (DLQ)** untuk investigasi manual.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Komparasi Pola Caching & Eksekusi Asinkron

```
========================================================================================
1. CACHE-ASIDE (READ PIPELINE)
========================================================================================
[Client]                [API Gateway]               [Redis Cache]            [PostgreSQL]
   │                          │                           │                        │
   │─── GET /products/123 ───>│                           │                        │
   │                          │─── GET "product:123" ────>│                        │
   │                          │<── [Cache Miss / Nil] ────│                        │
   │                          │                                                    │
   │                          │─────────────── SELECT * WHERE id=123 ─────────────>│
   │                          │<────────────── Row data: {id: 123, ...} ───────────│
   │                          │                                                    │
   │                          │─── SETEX "product:123" 3600 {data} ───>│           │
   │                          │<── OK ─────────────────────────────────│           │
   │                          │                                                    │
   │<── HTTP 200 (JSON) ──────│                                                    │
   
========================================================================================
2. ASYNC BACKGROUND WORKER (WRITE PIPELINE)
========================================================================================
[Client]                [API Gateway]            [Redis Queue]            [Worker Node]
   │                          │                         │                       │
   │── POST /users/register ─>│                         │                       │
   │                          │─ (Insert DB: User)      │                       │
   │                          │─ LPUSH "queue:email" ──>│                       │
   │                          │   payload: {userId: 4}  │                       │
   │<── HTTP 201 Created ─────│                         │                       │
  [Req Terminated]                                      │                       │
                                                        │<── BRPOP "queue:email"│
                                                        │    (Blocks until job) │
                                                        │                       │
                                                        │─── Return Payload ───>│
                                                        │                       │─ Send SMTP
                                                        │                       │─ Update DB
                                                        │                       │─ Ack / Done
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh konseptual minimalis implementasi Cache dan Background Task menggunakan Node.js murni (tanpa dependensi eksternal) untuk membedah mekanisme internalnya:

```javascript
// simple-foundation.js

// 1. In-Memory Cache Sederhana dengan TTL
class SimpleMemoryCache {
  constructor() {
    this.storage = new Map();
  }

  set(key, value, ttlSeconds) {
    const expiresAt = Date.now() + (ttlSeconds * 1000);
    this.storage.set(key, { value, expiresAt });
  }

  get(key) {
    const item = this.storage.get(key);
    if (!item) return null;

    if (Date.now() > item.expiresAt) {
      this.storage.delete(key); // Eviction manual saat expired
      return null;
    }
    return item.value;
  }
}

// 2. In-Memory Background Job Queue Sederhana
class SimpleQueue {
  constructor() {
    this.queue = [];
    this.isProcessing = false;
  }

  enqueue(taskName, payload) {
    this.queue.push({ taskName, payload, timestamp: new Date() });
    this.processNext();
  }

  async processNext() {
    if (this.isProcessing || this.queue.length === 0) return;

    this.isProcessing = true;
    const currentJob = this.queue.shift();

    try {
      console.log(`[Worker] Memulai job: ${currentJob.taskName}`);
      // Simulasi eksekusi operasi berat secara asinkron
      await new Promise((resolve) => setTimeout(resolve, 2000));
      console.log(`[Worker] Selesai job: ${currentJob.taskName} untuk payload:`, currentJob.payload);
    } catch (err) {
      console.error(`[Worker] Gagal memproses job:`, err);
    } finally {
      this.isProcessing = false;
      this.processNext(); // Lanjut ke item berikutnya dalam antrean
    }
  }
}

// Simulasi Penggunaan
const cache = new SimpleMemoryCache();
const jobQueue = new SimpleQueue();

// Caching Scenario
cache.set('config:rate_limit', 100, 2); // TTL 2 detik
console.log('Cache Hit Instant:', cache.get('config:rate_limit')); // Output: 100

setTimeout(() => {
  console.log('Cache Hit After 3s:', cache.get('config:rate_limit')); // Output: null (Expired)
}, 3000);

// Background Job Scenario
console.log('[HTTP] Menerima request registrasi...');
jobQueue.enqueue('SEND_WELCOME_EMAIL', { email: 'user@domain.id', userId: 99 });
console.log('[HTTP] Respons HTTP 201 terkirim segera tanpa menunggu email selesai dikirim.');
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Pada skenario dunia nyata, kita menggunakan **Redis** sebagai sistem *Distributed Cache* dan *Message Broker* untuk antrean pekerjaan (*Background Queue*). Contoh ini menggunakan Node.js dengan driver `ioredis`.

### Prasyarat Proyek
```bash
npm install ioredis
```

Pastikan Redis server berjalan secara lokal via Docker:
```bash
docker run -d --name local-redis -p 6379:6379 redis:7-alpine
```

### Implementasi Lengkap

```javascript
// app.js
const Redis = require('ioredis');

// Client Redis untuk koneksi normal
const redisClient = new Redis({
  host: '127.0.0.1',
  port: 6379,
  maxRetriesPerRequest: 3,
});

// Client Redis khusus untuk worker (karena pemanggilan BRPOP bersifat blocking)
const redisSubscriber = new Redis({
  host: '127.0.0.1',
  port: 6379,
});

// Mock Database Operasional (Simulasi Latensi Tinggi)
const MockDatabase = {
  async findUserById(id) {
    console.log(`[Postgres DB] Menjalankan query berat: SELECT * FROM users WHERE id = ${id}`);
    await new Promise((resolve) => setTimeout(resolve, 1500)); // Latensi 1.5 detik
    if (id === "101") {
      return { id: "101", username: "alex_dev", role: "Software Engineer", active: true };
    }
    return null;
  }
};

// ==========================================
// 1. IMPLEMENTASI CACHE-ASIDE PATTERN
// ==========================================
async function getUserProfile(userId) {
  const cacheKey = `users:${userId}:profile`;

  try {
    // Langkah 1: Cek ketersediaan di cache
    const cachedData = await redisClient.get(cacheKey);
    if (cachedData) {
      console.log(`[Cache] HIT untuk key: ${cacheKey}`);
      return JSON.parse(cachedData);
    }

    console.log(`[Cache] MISS untuk key: ${cacheKey}`);

    // Langkah 2: Ambil dari basis data utama jika Cache Miss
    const userFromDb = await MockDatabase.findUserById(userId);
    if (!userFromDb) {
      return null;
    }

    // Langkah 3: Simpan kembali ke cache dengan batas waktu (TTL) 60 Detik
    // SETEX: SET with EXpiration
    await redisClient.setex(cacheKey, 60, JSON.stringify(userFromDb));

    return userFromDb;
  } catch (error) {
    // FALLBACK PATTERN: Jika redis bermasalah, jangan biarkan aplikasi crash.
    // Lanjutkan kueri langsung ke database utama (Circuit Resilience).
    console.error(`[Cache Error] Gagal mengakses Redis, bypass ke DB:`, error.message);
    return await MockDatabase.findUserById(userId);
  }
}

// Invalidation Helper
async function invalidateUserCache(userId) {
  const cacheKey = `users:${userId}:profile`;
  await redisClient.del(cacheKey);
  console.log(`[Cache Invalidation] Kunci ${cacheKey} berhasil dihapus.`);
}

// ==========================================
// 2. IMPLEMENTASI BACKGROUND QUEUE (PRODUCER)
// ==========================================
const QUEUE_NAME = 'queue:transactional_emails';

async function dispatchEmailJob(payload) {
  const jobEnvelope = {
    id: `job_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
    data: payload,
    retryCount: 0,
    maxRetries: 3,
    createdAt: new Date().toISOString(),
  };

  // LPUSH menaruh pesan ke sisi kiri antrean list Redis
  await redisClient.lpush(QUEUE_NAME, JSON.stringify(jobEnvelope));
  console.log(`[Producer] Job ${jobEnvelope.id} dimasukkan ke dalam antrean [${QUEUE_NAME}]`);
  return jobEnvelope.id;
}

// ==========================================
// 3. IMPLEMENTASI BACKGROUND WORKER (CONSUMER)
// ==========================================
async function startWorker() {
  console.log('[Worker Service] Consumer Worker berjalan. Menunggu data antrean...');

  // Worker loop tanpa henti
  while (true) {
    try {
      // BRPOP: Blocking Right POP. 
      // Menunggu hingga elemen tersedia di antrean dengan batas timeout (misal 5 detik).
      // Angka '0' berarti blocking tanpa batas waktu (selamanya hingga ada item).
      const response = await redisSubscriber.brpop(QUEUE_NAME, 0);
      
      // response bernilai array: [nama_queue, item_data]
      const rawJobData = response[1];
      const job = JSON.parse(rawJobData);

      console.log(`\n[Worker Engine] Mulai mengeksekusi Job ID: ${job.id}`);
      
      // Eksekusi Logika Inti Worker
      await processEmailExecution(job.data);

      console.log(`[Worker Engine] Job ID: ${job.id} SELESAI diproses secara aman.\n`);
    } catch (workerError) {
      console.error(`[Worker Engine Fatal] Error saat parsing / eksekusi antrean:`, workerError.message);
    }
  }
}

async function processEmailExecution(data) {
  // Simulasi koneksi lambat ke vendor eksternal (SendGrid/Mailgun)
  await new Promise((resolve, reject) => {
    setTimeout(() => {
      if (data.email.includes('error')) {
        reject(new Error("SMTP Relay Provider Timeout"));
      } else {
        console.log(`[Worker Task] Email konfirmasi berhasil dikirimkan ke: ${data.email}`);
        resolve();
      }
    }, 1200);
  });
}

// ==========================================
// 4. SIMULASI ORKESTRASI APLIKASI
// ==========================================
async function main() {
  // Menjalankan Worker di proses terpisah secara non-blocking
  startWorker();

  console.log('--- TEST 1: Request Pertama (Cache Miss) ---');
  console.time('Request-1-Latency');
  const user1 = await getUserProfile("101");
  console.timeEnd('Request-1-Latency');

  console.log('\n--- TEST 2: Request Kedua (Cache Hit) ---');
  console.time('Request-2-Latency');
  const user2 = await getUserProfile("101");
  console.timeEnd('Request-2-Latency');

  console.log('\n--- TEST 3: Pemicu Background Job ---');
  console.time('HTTP-Registration-Response');
  // API Controller mendaftarkan user dan langsung mengembalikan response
  const jobId = await dispatchEmailJob({
    email: 'engineer@corp.com',
    subject: 'Selamat Datang di Platform!',
    templateId: 'welcome_v1'
  });
  console.timeEnd('HTTP-Registration-Response');
  console.log(`[HTTP Controller] Respon 202 Accepted dikembalikan dengan Job ID: ${jobId}`);

  // Simulasi Invalidation setelah beberapa saat
  setTimeout(async () => {
    console.log('\n--- TEST 4: Data Diperbarui, Cache Di-Invalidasi ---');
    await invalidateUserCache("101");
    
    console.log('\n--- TEST 5: Request Ketiga Pasca-Invalidasi (Cache Miss Kembali) ---');
    console.time('Request-3-Latency');
    await getUserProfile("101");
    console.timeEnd('Request-3-Latency');

    // Clean-up koneksi
    setTimeout(() => {
      redisClient.quit();
      redisSubscriber.quit();
      process.exit(0);
    }, 3000);
  }, 4000);
}

main().catch(console.error);
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Opsi A | Opsi B | Analisis Trade-Off |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Cache** | **In-Memory (Local Map / Node Cache)** | **Distributed Cache (Redis / KeyDB)** | Local Cache memiliki *latency* sub-milidetik tercepat karena tanpa alur *network hop*. Namun, jika aplikasi di-*scale-out* menjadi beberapa server, memory antar-node akan mengalami *data drift* (inkonsistensi data). Redis menambah dependensi infrastruktur dan overhead latensi jaringan kecil (~1ms), namun konsisten di seluruh instance. |
| **Strategi Invalidation** | **Short-Lived TTL Only (Passive Invalidation)** | **Event-Driven Purge (Active Invalidation)** | Mengandalkan TTL murni membuat kode sangat bersih tanpa logika eviksi manual, namun pengguna berisiko melihat data kedaluwarsa (*stale data*) hingga TTL habis. Active Invalidation menjamin data segar seketika ada mutasi, tetapi menambah kompleksitas basis kode dan rawan *race conditions*. |
| **Model Eksekusi** | **Synchronous Request-Response** | **Asynchronous Job Processing** | Sinkron jauh lebih mudah diuji, tidak butuh broker antrean, dan alur kode linier. Namun, kegagalan pihak ketiga (SMTP/Payment) akan langsung menggagalkan request klien. Pendekatan Asinkron meningkatkan reliabilitas dan throughput drastis, tetapi menuntut desain arsitektur *eventual consistency*. |
| **Worker Queue Architecture** | **Simple Redis List (`LPUSH`/`BRPOP`)** | **Enterprise Broker (RabbitMQ / Kafka)** | Pola Redis List sangat mudah dibuat tanpa setup kompleks untuk kebutuhan antrean dasar. Namun, tidak memiliki jaminan *delivery ack* bawaan yang rumit, partition routing, atau replay log history berkapasitas tinggi seperti yang disediakan oleh RabbitMQ atau Apache Kafka. |

---

## SEKSI 11 — BEST PRACTICES

1. **Selalu Terapkan TTL (Time-To-Live)**: Jangan pernah menyimpan data ke cache tanpa batas kedaluwarsa (*infinite cache*). Hal ini mencegah konsumsi memori tak terhingga (*memory leak*) dan membatasi dampak dari kegagalan logika invalidasi data.
2. **Standardisasi Naming Convention Kunci Cache**: Gunakan struktur namespace hierarkis menggunakan pembatas titik dua (`:`), contoh:
   * Format: `<domain>:<subdomain>:<id>:<atribut>`
   * Implementasi: `ecommerce:products:984712:inventory`
3. **Desain Job Worker yang Idempoten (*Idempotent Workers*)**: Worker dapat mengeksekusi payload yang sama lebih dari satu kali (*at-least-once delivery*). Pastikan operasi yang dijalankan aman terhadap duplikasi menggunakan database lock atau idempotency key.
4. **Implementasikan Exponential Backoff pada Retry**: Jangan me-retry job yang gagal secara langsung dalam milidetik yang sama. Terapkan jeda bertingkat:
   $$\text{Delay} = 2^{\text{attempt}} \times 1000\text{ ms}$$
   Langkah ini melindungi downstream service yang sedang *down* dari serangan DoS (*Denial of Service*) oleh worker internal sendiri.
5. **Gunakan Dead-Letter Queue (DLQ)**: Jika sebuah job gagal setelah batas repetisi maksimal (misal: 3-5 kali), pindahkan payload ke antrean DLQ. Pasang pemantauan (*alerting*) agar tim teknis dapat memeriksa *root-cause* tanpa kehilangan payload data pengguna.
6. **Graceful Degradation pada Cache Failures**: Kegagalan cache layer (misal: Redis crash atau network timeout) tidak boleh mengakibatkan crash fatal pada aplikasi utama. Tangkap *exception* dan alihkan kueri secara elegan ke primary database.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The "Thundering Herd" / Cache Stampede Problem
* **Kesalahan**: Menyimpan data populer dengan TTL yang singkat secara serentak tanpa proteksi. Ketika kunci tersebut kedaluwarsa pada detik yang sama, ratusan request klien yang datang bersamaan akan mengalami *Cache Miss* serempak dan membombardir database utama dengan ratusan kueri berat yang identik.
* **Solusi**: Gunakan mekanisme *Mutual Exclusion (Mutex)* lock menggunakan `SETNX` di Redis saat kueri DB dijalankan, atau tambahkan *random jitter* (misal: `TTL = 3600 + Math.random() * 300`) sehingga ribuan cache key tidak kedaluwarsa di detik yang sama.

### 2. Mengirimkan Kompleksitas Objek Utuh ke Message Queue
* **Kesalahan**: Memasukkan objek besar, koneksi basis data aktif, atau instance memori yang besar ke dalam antrean:
  ```javascript
  // SALAH: Memasukkan objek ORM/Model utuh yang mengandung internal state
  await queue.enqueue('SEND_EMAIL', userModelInstance);
  ```
* **Solusi**: Hanya kirimkan data primitif minimal atau identifier (*Data Hydration Pattern*):
  ```javascript
  // BENAR: Mengirimkan pointer ID saja
  await queue.enqueue('SEND_EMAIL', { userId: "101" });
  ```
  Worker kemudian bertugas mengambil status data terbaru dari database utama menggunakan ID tersebut saat eksekusi dimulai.

### 3. Mengabaikan Status Out-of-Memory (OOM) pada Redis
* **Kesalahan**: Memperlakukan Redis layaknya Primary Database tanpa memantau kapasitas RAM server hosting.
* **Solusi**: Konfigurasikan kebijakan `maxmemory` dan `maxmemory-policy` di konfigurasi Redis (misal: `allkeys-lru` atau `volatile-lru`) untuk memastikan server tidak crash saat memori fisik mendekati 100%.

### 4. Stateful Worker Process
* **Kesalahan**: Menyimpan state transaksi sementara di variabel lokal memori Worker engine. Jika instance worker me-restart (*crash* atau di-*reschedule* oleh Kubernetes/Docker), context data transaksi tersebut hilang.
* **Solusi**: Semua worker harus stateless. State mutasi harus disimpan di persistent store (Database/Redis).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Proyek
Anda ditugaskan merombak sistem backend e-commerce yang sering mengalami *downtime* saat peluncuran produk terbatas (*Flash Sale*).

### Task 1: Level Dasar (Warm-up)
* Buat modul caching independen bernama `CacheService` dengan menggunakan struktur `Map` native Node.js.
* Sediakan antarmuka:
  * `set(key: string, value: any, ttlSeconds: number): void`
  * `get(key: string): any | null`
  * `del(key: string): void`
* Tambahkan interval otomatis (garbage collector internal) yang berjalan setiap 10 detik untuk membersihkan data yang telah expired secara pasif di background tanpa menunggu fungsi `get()` dipanggil.

### Task 2: Level Menengah (Implementation)
* Rancang fungsi `getOrSetCache(key, ttl, fetchFunction)`:
  * Fungsi ini menerima `fetchFunction` (suatu fungsi asinkron ke DB).
  * Jika cache hit: langsung kembalikan data.
  * Jika cache miss: eksekusi `fetchFunction`, simpan hasilnya ke Redis, lalu kembalikan output-nya.
* Buat simulasi endpoint express `GET /api/v1/leaderboard` yang memanfaatkan fungsi tersebut.

### Task 3: Level Lanjut (Failure Handling & Retries)
* Rancang sistem Worker sederhana menggunakan Redis List (`LPUSH` dan `RPOP`).
* Tambahkan mekanisme:
  1. Jika eksekusi task gagal (simulasikan kegagalan via `Math.random() < 0.5`), jangan langsung buang task.
  2. Naikkan field `retryCount` pada payload.
  3. Jika `retryCount <= 3`, masukkan kembali ke antrean dengan jeda waktu buatan.
  4. Jika `retryCount > 3`, pindahkan payload secara otomatis ke queue lain bernama `queue:dead_letter`.
* Tulis laporan log terstruktur pada setiap tahapan state: `[DISPATCHED]`, `[RETRYING]`, `[FAILED]`, `[DLQ_MOVED]`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

#### 1. Pada pola arsitektur Cache-Aside, apa yang dilakukan oleh server aplikasi ketika mendeteksi adanya data mutation (misalnya operasi HTTP `PUT /products/1`)?
* A. Langsung mengabaikan cache dan membiarkan data terupdate alami lewat masa kedaluwarsa TTL.
* B. Memperbarui data di primary database dan menghapus (invalidate) cache key terkait di Redis.
* C. Menghentikan semua proses request yang sedang membaca data produk tersebut.
* D. Mengubah status Redis menjadi read-only sampai proses mutasi database selesai sepenuhnya.

#### 2. Kapan sebaiknya sebuah pemrosesan komputasi dialihkan dari alur sinkron HTTP request ke background job worker?
* A. Saat operasi tersebut menghasilkan data JSON di bawah 1 Kilobyte.
* B. Saat komputasi tersebut memakan waktu I/O yang tidak dapat diprediksi dan respons instan tidak diwajibkan oleh pengguna secara real-time.
* C. Saat kita tidak ingin menggunakan basis data relasional.
* D. Saat klien menggunakan protokol HTTP/1.1 dan bukan HTTP/2.

#### 3. Apa yang dimaksud dengan konsep Idempotensi pada konteks Background Worker?
* A. Sifat di mana worker berjalan tanpa membutuhkan memori RAM sama sekali.
* B. Jaminan bahwa task background akan selalu diproses secara tepat waktu di bawah rentang 1 detik.
* C. Kemampuan worker untuk menghasilkan efek samping state akhir yang sama meskipun payload tugas yang identik dieksekusi berkali-kali.
* D. Mekanisme antrean yang memprioritaskan job dengan payload data terkecil terlebih dahulu.

#### 4. Apa tujuan utama dari penambahan "Random Jitter" pada penetapan durasi TTL cache?
* A. Menghemat kapasitas penyimpanan disk Redis.
* B. Mengenkripsi isi cache dari serangan cyber injection.
* C. Mencegah fenomena *Cache Stampede* dengan memvariasikan waktu kedaluwarsa kumpulan data yang diisi secara bersamaan.
* D. Menjamin pengurutan eksekusi antrean FIFO di Redis.

#### 5. Fungsi utama dari Dead-Letter Queue (DLQ) adalah...
* A. Menyimpan log user authentication yang telah kedaluwarsa.
* B. Menampung job yang telah gagal berulang kali melebihi kuota retry agar tidak menyumbat antrean utama dan tidak hilang.
* C. Menghapus data sampah pada hard disk server backend secara otomatis.
* D. Menggandakan tugas worker agar berjalan paralel di banyak instance sekaligus.

---

### Kunci Jawaban & Rasionalisasi

* **1. Jawaban: B**
  * *Rasionalisasi*: Menghapus kunci (*evict*) dari cache setelah melakukan pembaruan di primary database adalah praktik standar Cache-Aside untuk menjaga konsistensi data tanpa memicu race condition yang sering terjadi pada pola *cache overwrite*.
* **2. Jawaban: B**
  * *Rasionalisasi*: Operasi berat seperti generate PDF, pengiriman batch email, pemrosesan video, atau pemanggilan API pihak ketiga berlatensi fluktuatif wajib dipindahkan ke background worker untuk menjaga response time API server tetap konsisten rendah.
* **3. Jawaban: C**
  * *Rasionalisasi*: Jaringan dan antrean pesan memiliki karakteristik *at-least-once delivery*, di mana kegagalan jaringan sementara dapat memicu worker menerima job yang sama dua kali. Worker yang idempoten menjamin data tidak terduplikasi (misal: kartu kredit pengguna tidak tertagih dua kali).
* **4. Jawaban: C**
  * *Rasionalisasi*: *Random Jitter* mengacak nilai TTL secara variatif (misal: 60 detik $\pm$ rentang acak 1-10 detik), sehingga jutaan keys yang masuk secara simultan tidak mati pada detik yang persis bersamaan, mencegah beban kejut ke database utama.
* **5. Jawaban: B**
  * *Rasionalisasi*: DLQ bertindak sebagai tempat karantina tugas yang rusak (*poison pill messages*) agar tim engineer dapat mengaudit kesalahan logika atau payload tanpa menghambat job lain yang valid di antrean utama.

---

### Checklist Kemandirian Pemahaman

Beri tanda centang $(\checkmark)$ jika Anda telah memahami poin-poin berikut:

- [ ] Saya memahami perbedaan mendasar latensi akses memori (RAM) vs akses storage (Disk/Network DB).
- [ ] Saya dapat memetakan kapan harus menggunakan pola Cache-Aside dibanding Write-Through.
- [ ] Saya mampu mendemonstrasikan implementasi TTL pada Redis CLI menggunakan perintah `SETEX` atau `EXPIRE`.
- [ ] Saya paham mengapa HTTP 202 Accepted lebih tepat digunakan daripada HTTP 200 OK untuk operasi asynchronous background jobs.
- [ ] Saya mengerti struktur perancangan arsitektur worker yang tahan banting melalui Retry Policy, Exponential Backoff, dan Dead-Letter Queue.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku & Standar Industri**:
   * *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) — Bab 3: *Storage and Retrieval*, Bab 11: *Stream Processing*.
   * *System Design Interview – An Insider's Guide* oleh Alex Xu — Bab: *Design a Key-Value Store* & *Design a Message Queue*.
2. **Dokumentasi Resmi**:
   * [Redis Documentation: Keyspace Expiration & Eviction Policies](https://redis.io/docs/manual/eviction/)
   * [BullMQ Documentation (Node.js Enterprise-grade Queue on top of Redis)](https://docs.bullmq.io/)
   * [RFC 7231 Hypertext Transfer Protocol: 202 Accepted Semantics](https://datatracker.ietf.org/doc/html/rfc7231#section-6.3.3)
3. **Pustaka Produksi Populer**:
   * Node.js: `ioredis` (Redis client), `bullmq` / `bee-queue` (Message Queues).
   * Python: `celery` / `rq` (Redis Queue).
   * Go: `asynq` (Simple, reliable, efficient distributed task queue in Go).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Pada modul ini, kita telah membongkar dua pilar arsitektur fundamental dalam rekayasa backend modern: **Caching Strategies** dan **Background Job Basics**.

Caching berfokus pada efisiensi pemanggilan data dengan memanfaatkan kecepatan memori RAM untuk memangkas *read latency* dan memitigasi *database load*. Melalui pola **Cache-Aside**, aplikasi memperlakukan cache sebagai penyimpan sekunder yang diakses sebelum membebani primary storage, didukung konfigurasi batas kedaluwarsa (**TTL**) dan logika pembersihan data aktif (**Cache Invalidation**).

Di sisi lain, Background Processing berfokus pada pelepasan beban *write operations* atau kalkulasi berat dari siklus hidup sinkron HTTP. Memanfaatkan mekanisme antrean (**Message Queue**) dengan arsitektur **Producer-Consumer**, API dapat langsung merespons klien dengan status `202 Accepted`, sementara pekerjaan berat didelegasikan kepada sekumpulan **Worker Node** terisolasi. Arsitektur ini menuntut penanganan kesalahan yang tangguh melalui **Retry Mechanisms**, **Exponential Backoff**, **Dead-Letter Queues (DLQ)**, dan penerapan logika pemrosesan yang **Idempoten**.

---

## SEKSI 17 — GLOSARIUM

* **Cache Hit**: Kondisi di mana data yang diminta oleh aplikasi berhasil ditemukan di dalam cache layer.
* **Cache Miss**: Kondisi di mana data yang dicari tidak ditemukan di cache layer, memaksa aplikasi melakukan query ke sumber data primer (database).
* **TTL (Time-To-Live)**: Rentang waktu hidup suatu data di dalam cache sebelum data tersebut otomatis ditandai kedaluwarsa dan dihapus.
* **Cache Stampede (Thundering Herd)**: Kejadian di mana kunci cache bernilai tinggi kedaluwarsa dan ratusan hingga ribuan kueri masuk secara paralel menuju database utama dalam jendela waktu yang sama.
* **Producer**: Komponen aplikasi yang bertugas menciptakan pekerjaan (*job/message*) dan menyuntikkannya ke dalam antrean antarmuka.
* **Consumer / Worker**: Proses komputasi terpisah yang mengambil pesan dari antrean dan mengeksekusi logika bisnis instruksi tersebut.
* **Dead-Letter Queue (DLQ)**: Antrean cadangan khusus yang menampung pesan atau tugas yang gagal diproses meskipun telah melewati batas percobaan ulang (*max retries*).
* **Idempotency**: Properti dari suatu operasi di mana eksekusi berulang kali dengan parameter input yang sama tidak akan menghasilkan perubahan status aplikasi di luar hasil dari eksekusi pertamanya.
* **Eviction Policy**: Algoritma yang digunakan oleh sistem cache (seperti LRU/LFU) untuk memutuskan data mana yang harus dibuang saat memori penyimpanan telah penuh.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi
* Tekankan kepada peserta didik bahwa **Redis bukanlah pengganti database utama**, melainkan pelengkap arsitektur. Data di Redis bersifat volatil secara *default* kecuali dikonfigurasi dengan persistensi disk yang ketat (AOF/RDB), yang mana memiliki trade-off performa tersendiri.
* Saat mengajarkan Background Jobs, hindari langsung melompat ke library abstraksi tingkat tinggi seperti BullMQ sebelum siswa memahami konsep dasar raw queue: struktur data List Redis (`LPUSH` dan `BRPOP`) atau Producer-Consumer loop manual.

### Jebakan Konseptual Siswa (Common Pitfalls)
* Siswa sering beranggapan bahwa setiap endpoint harus diberi cache. Jelaskan bahwa menaruh cache pada data yang rasio perubahannya sangat tinggi (*highly dynamic mutable data*) hanya akan membuang memori dan menambah overhead invalidasi.
* Siswa kerap lupa menangani *Network Partition* antara Node API dan Redis instance. Wajibkan siswa selalu membungkus pemanggilan cache dalam blok `try/catch` agar aplikasi memiliki sistem *fallback* ke database saat cache mengalami *down*.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2025-01-15 | Curriculum Architecture Team | Perilisan perdana modul komprehensif Bab 09 Modul 01: Caching & Background Jobs standar 20 seksi GEMINI.md. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

```
┌─────────────────────────────────┐
│     MODUL SEBELUMNYA            │
│ Bab 08 Modul 02:                │
│ Database Indexing & Query Tuning│
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│       MODUL SAAT INI            │
│ Bab 09 Modul 01:                │
│ Caching Strategies & Background │
│ Job Basics                      │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     MODUL BERIKUTNYA            │
│ Bab 09 Modul 02:                │
│ Message Queues with BullMQ &    │
│ Advanced Redis Patterns         │
└─────────────────────────────────┘
```