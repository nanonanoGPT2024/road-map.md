## SEKSI 01 — IDENTITAS MODUL

*   **Kurikulum**: API Design & Architecture
*   **Kategori**: 06-Architecture-and-System-Design
*   **Bab**: 05 — Distributed Mutability, Concurrency, & Idempotency
*   **Modul**: 01 — Idempotency Keys Pattern, Distributed Locks, Optimistic Locking (ETag & If-Match), dan Saga Compensation Patterns
*   **Tingkat Kesulitan**: Advanced / Principal Level
*   **Prasyarat**: Pemahaman mendalam tentang HTTP/1.1 & HTTP/2 specs (RFC 9110), ACID vs BASE properties, Relational Database isolation levels (Read Committed, Repeatable Read, Serializable), Message Broker fundamentals, dan Redis/Key-Value store primitives.
*   **Estimasi Waktu Belajar**: 120 Menit (Teori & Implementasi Mandiri)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1. **Merancang dan Mengimplementasikan** *Idempotency Key Pattern* tingkat produksi yang tahan terhadap race conditions, network retries, dan server crash dengan hashing payload deterministik.
2. **Mengevaluasi dan Menerapkan** *Distributed Locks* (seperti algoritma Redlock atau Redis Lease) lengkap dengan *fencing tokens* untuk mencegah anomali *split-brain* akibat garbage collection pause atau network latency.
3. **Menerapkan** *Optimistic Concurrency Control* (OCC) standar HTTP menggunakan header `ETag`, `If-Match`, dan `If-None-Match` untuk mengatasi anomali *lost update* pada mutasi resource konkuren.
4. **Membangun** alur transaksi terdistribusi menggunakan *Saga Pattern* (Orchestration & Choreography) dengan *forward recovery* dan *backward compensating actions* yang idempoten secara matematis.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [ Distributed Mutability ]
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
[ Network Failures ]         [ Concurrent Mutex ]          [ Distributed State ]
         │                             │                             │
         ▼                             ▼                             ▼
  Idempotency Keys             Concurrency Control              Saga Pattern
  - Client-generated UUID      - Distributed Lock             - Orchestration
  - SHA-256 Payload Hash         (Redis/Redlock + Fencing)    - Choreography
  - Atomic State Lock          - Optimistic Locking           - Compensating Tx
  - Cached Response Body         (ETag + If-Match)            - Pivot Transactions
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam sistem monolitik dengan basis data tunggal, integritas data mutasi dijaga melalui transaksi ACID lokal (`BEGIN ... COMMIT/ROLLBACK`). Namun, dalam arsitektur modern berbasis microservices dan *distributed edge*, batas-batas transaksional lokal tersebut runtuh akibat tiga fenomena fisik sistem terdistribusi:

1. **Jaringan Bersifat Tidak Andal (Unreliable Network)**: Sebuah request `POST /v1/payments` dapat dieksekusi di database server tujuan, namun koneksi TCP terputus sebelum client menerima respons `200 OK`. Jika client melakukan *retry*, terjadi risiko fatal: *double charging* (penarikan dana ganda).
2. **Anomali *Lost Updates* pada Mutasi Konkuren**: Dua user mencoba mengubah metadata dokumen atau saldo inventaris secara bersamaan. Tanpa mekanisme sinkronisasi data yang ketat, mutasi user B akan menimpa mutasi user A tanpa jejak audit (*race condition*).
3. **Absennya *Two-Phase Commit* (2PC) yang Terukur**: Mengunci tabel database lintas beberapa microservices menggunakan XA/2PC menyebabkan performa kolaps, latensi tinggi, dan *single point of failure*.

Kegagalan menangani konkurensi dan mutabilitas terdistribusi tidak hanya berakibat pada kegagalan teknis, melainkan langsung berujung pada kerugian finansial, inkonsistensi saldo ledger, dan kerusakan integritas data permanen.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Idempotency Key Pattern
Metode di mana client menyematkan pengenal unik (lazimnya UUID v4) pada header HTTP mutatif (`POST`, `PATCH`). Server mencatat status lifecycle request tersebut di storage terdistribusi. Jika request dengan key yang sama dikirimkan berulang kali, server tidak mengeksekusi logika bisnis ulang, melainkan mengembalikan respons yang sama persis seperti eksekusi pertama.

### 2. Distributed Locks & Fencing Tokens
Mekanisme koordinasi terdistribusi untuk menjamin bahwa hanya satu node di seluruh cluster yang dapat mengeksekusi *critical section* pada waktu tertentu. Penggunaan *Distributed Lock* naif (hanya `SETNX`) rentan terhadap anomali pause proses (GC, page faults). Untuk mengatasinya, digunakan *fencing token*—sebuah counter strictly monotonic yang diteruskan ke layer persistensi guna memblokir proses yang kepemilikan lock-nya sudah kedaluwarsa.

### 3. Optimistic Concurrency Control (OCC) via HTTP ETag & If-Match
Standar IETF (RFC 9110) untuk validasi bersyarat. Server memproduksi fingerprint kriptografis atau token versi dari resource state (`ETag`). Client yang ingin memodifikasi data harus mengirimkan kembali token tersebut melalui header `If-Match`. Mutasi ditolak dengan kode `412 Precondition Failed` jika data telah berubah di server.

### 4. Saga Compensation Pattern
Pola desain untuk mengelola transaksi bisnis berjangka panjang lintas beberapa service independen tanpa lock global. Saga memecah transaksi menjadi serangkaian transaksi lokal. Jika salah satu transaksi lokal gagal, Saga memicu rantai *compensating transactions* untuk membatalkan perubahan yang terlanjur di-commit sebelumnya (backward recovery).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### A. Lifecycle Idempotency Key
1. **Client Request**: Mengirim `POST /v1/orders` dengan header `Idempotency-Key: <UUID>` dan body payload.
2. **Locking & Validation**: Server menghitung hash SHA-256 dari request body + URL path. Server melakukan operasi atomic `SET key lock:order:<UUID> <payload_hash> NX EX 120` di Redis.
   * *Jika lock gagal didapat (Key sudah ada)*:
     * Cek status: Jika status masih `IN_PROGRESS`, kembalikan `409 Conflict` (atau hold connection dengan timeout).
     * Jika status `RESOLVED` dan hash payload cocok, kembalikan respons tersimpan dari cache.
     * Jika status `RESOLVED` tetapi hash payload **berbeda**, tolak dengan `422 Unprocessable Entity` (Idempotency Key di-reuse dengan payload berbeda).
3. **Execution**: Server menjalankan domain logic dalam transaksi database lokal.
4. **Persist State**: Simpan HTTP response status code, header, dan body ke idempotency record dengan TTL definitif (misalnya 24 jam).
5. **Release Lock**: Ubah status dari `IN_PROGRESS` menjadi `RESOLVED`.

### B. Optimistic Locking dengan ETag (RFC 9110)
1. **Client Fetch**: `GET /v1/products/sku-99` -> Server merespons `200 OK` dengan header `ETag: "v1_hash_abc123"`.
2. **Client Mutation**: Client mengubah harga, lalu mengirim `PUT /v1/products/sku-99` dengan header `If-Match: "v1_hash_abc123"`.
3. **Validation**:
   * Server menjalankan query:
     ```sql
     UPDATE products 
     SET price = 150000, version = version + 1 
     WHERE sku = 'sku-99' AND version = 1;
     ```
   * Jika rows affected == 0, artinya data telah dimutasi oleh transaksi lain. Server langsung abort dan membalas `412 Precondition Failed`.
   * Jika rows affected == 1, generate ETag baru `"v2_hash_def456"`, lalu kirim `200 OK`.

### C. Distributed Lock dengan Fencing Token
1. Client A meminta lock ke Redis cluster.
2. Redis mengeksekusi script Lua yang atomic: jika key belum ada, assign lock dan naikkan global monotonic counter:
   * Token $N = 42$.
3. Client A mengalami stop-the-world GC pause selama 30 detik (melebihi lock TTL 10 detik).
4. Lock milik Client A kedaluwarsa (expired).
5. Client B meminta lock, sukses, dan mendapatkan Token $N = 43$.
6. Client B menulis ke Database dengan token 43. DB mencatat `highest_token = 43`.
7. Client A terbangun dari GC pause, mengira masih memegang lock, mencoba menulis ke DB dengan token 42.
8. Database menolak write Client A karena $42 < 43$. Data integrity selamat.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Sequence Diagram: Idempotency Key Handling Engine

```
Client                  API Gateway / Service              Redis Storage             Database
  │                               │                              │                      │
  │── POST /transfers ───────────>│                              │                      │
  │   Idempotency-Key: UUID-1     │                              │                      │
  │   Body: {amount: 500}         │── HASH(Payload) ────────────>│                      │
  │                               │── SET key:UUID-1 NX EX 60 ──>│                      │
  │                               │<── OK (Lock Acquired) ───────│                      │
  │                               │                                                     │
  │                               │── BEGIN TRANSACTION ───────────────────────────────>│
  │                               │   INSERT INTO transfers ...                         │
  │                               │── COMMIT ──────────────────────────────────────────>│
  │                               │<── Transaction Success ─────────────────────────────│
  │                               │                                                     │
  │                               │── SET key:UUID-1 [RESOLVED, Body] TTL 86400 ───────>│
  │<── 201 Created (Transfer OK) ─│                                                     │
  │                               │                                                     │
  │   [ NETWORK TIMEOUT / RETRY ] │                                                     │
  │                               │                                                     │
  │── POST /transfers ───────────>│                                                     │
  │   Idempotency-Key: UUID-1     │                                                     │
  │   Body: {amount: 500}         │── SET key:UUID-1 NX EX 60 ──>│                      │
  │                               │<── NIL (Key Exists!) ────────│                      │
  │                               │── GET key:UUID-1 ───────────>│                      │
  │                               │<── Return [RESOLVED, Body] ──│                      │
  │                               │                                                     │
  │                               │── Verify SHA256 Hash Match                           │
  │<── 201 Created (Cached Body) ─│                                                     │
  │   (No DB Execution!)          │                                                     │
```

### 2. Sequence Diagram: Optimistic Concurrency Control (ETag / If-Match)

```
Client 1                        Client 2                        API Server / DB
   │                               │                                   │
   │── GET /resources/10 ──────────┼──────────────────────────────────>│
   │<── 200 OK [ETag: "v1"] ───────┼───────────────────────────────────│
   │                               │                                   │
   │                               │── GET /resources/10 ─────────────>│
   │                               │<── 200 OK [ETag: "v1"] ───────────│
   │                               │                                   │
   │── PUT /resources/10 ──────────┼──────────────────────────────────>│
   │   If-Match: "v1"              │                                   │
   │   Body: {data: "C1 Update"}   │                                   │
   │                               │                                   │── Check version == 1 (OK)
   │                               │                                   │── Update version = 2
   │<── 200 OK [ETag: "v2"] ───────┼───────────────────────────────────│
   │                               │                                   │
   │                               │── PUT /resources/10 ─────────────>│
   │                               │   If-Match: "v1"                  │
   │                               │   Body: {data: "C2 Update"}       │
   │                               │                                   │── Check version == 1
   │                               │                                   │   (FAILED! Current: 2)
   │                               │<── 412 Precondition Failed ───────│
   │                               │                                   │
```

### 3. Saga Orchestration vs Compensation

```
Order Service                Payment Service             Inventory Service
   │                               │                             │
   │── Execute: Create Order ─────>│                             │
   │   [Order: PENDING]            │                             │
   │                               │                             │
   │── Execute: Deduct Balance ───>│                             │
   │                               │ (Balance Deducted)          │
   │<── Payment OK ────────────────│                             │
   │                               │                             │
   │── Execute: Reserve Stock ──────────────────────────────────>│
   │                                                             │ (Stock Out of Range!)
   │<── Stock Failed ────────────────────────────────────────────│
   │                                                             │
   │================ ROLLBACK TRIGGERED (COMPENSATION) ==========│
   │                                                             │
   │── Compensate: Refund Balance >│                             │
   │                               │ (Balance Credited Back)     │
   │<── Refund Acknowledged ───────│                             │
   │                                                             │
   │   [Order: CANCELLED]          │                             │
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi pengecekan HTTP `ETag` dan `If-Match` sederhana menggunakan Express.js dan modul hashing Node.js native:

```typescript
import express, { Request, Response } from 'express';
import crypto from 'crypto';

const app = express();
app.use(express.json());

interface DocumentResource {
  id: string;
  content: string;
  version: number;
}

// Simulasi in-memory DB
let documentStore: DocumentResource = {
  id: 'doc-42',
  content: 'Initial Enterprise Contract',
  version: 1,
};

function generateETag(doc: DocumentResource): string {
  return `"${crypto.createHash('sha256').update(`${doc.id}-${doc.version}-${doc.content}`).digest('hex')}"`;
}

// GET Endpoint dengan Header ETag
app.get('/v1/documents/:id', (req: Request, res: Response) => {
  const etag = generateETag(documentStore);
  res.setHeader('ETag', etag);
  res.status(200).json(documentStore);
});

// PUT Endpoint dilindungi If-Match
app.put('/v1/documents/:id', (req: Request, res: Response) => {
  const clientETag = req.headers['if-match'];
  
  if (!clientETag) {
    return res.status(428).json({ 
      error: 'Precondition Required: Header "If-Match" wajib disertakan.' 
    });
  }

  const currentETag = generateETag(documentStore);

  // Verifikasi kondisi ETag
  if (clientETag !== currentETag) {
    return res.status(412).json({ 
      error: 'Precondition Failed: Resource telah dimutasi oleh proses lain. Silakan fetch data terbaru.' 
    });
  }

  // Mutasi resource
  documentStore.content = req.body.content;
  documentStore.version += 1;

  const newETag = generateETag(documentStore);
  res.setHeader('ETag', newETag);
  return res.status(200).json(documentStore);
});

app.listen(3000, () => console.log('Server running on port 3000'));
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Di bawah ini adalah implementasi *Production-Grade Idempotency Middleware* menggunakan Node.js/TypeScript, Redis (ioredis), dan hashing SHA-256 untuk payload integrity validation.

```typescript
import { Request, Response, NextFunction } from 'express';
import Redis from 'ioredis';
import crypto from 'crypto';

const redis = new Redis({
  host: process.env.REDIS_HOST || '127.0.0.1',
  port: 6379,
});

enum IdempotencyStatus {
  IN_PROGRESS = 'IN_PROGRESS',
  RESOLVED = 'RESOLVED',
}

interface IdempotencyRecord {
  status: IdempotencyStatus;
  payloadHash: string;
  statusCode?: number;
  responseBody?: string;
  responseHeaders?: Record<string, string>;
}

export function idempotencyMiddleware(ttlSeconds = 86400) {
  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    // 1. Validasi keberadaan idempotency key
    const idempotencyKey = req.headers['idempotency-key'] as string;
    if (!idempotencyKey) {
      // Lewatkan jika bukan mutasi (hanya tangani POST, PUT, PATCH)
      if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
        res.status(400).json({ error: 'Missing Idempotency-Key header' });
        return;
      }
      return next();
    }

    // 2. Generate Hash deterministik dari request body + URL
    const payloadHash = crypto
      .createHash('sha256')
      .update(req.originalUrl + JSON.stringify(req.body || {}))
      .digest('hex');

    const cacheKey = `idempotency:${idempotencyKey}`;
    const lockKey = `lock:${cacheKey}`;

    try {
      // 3. Cek apakah record sudah ada
      const existingData = await redis.get(cacheKey);

      if (existingData) {
        const record: IdempotencyRecord = JSON.parse(existingData);

        // Validasi kesesuaian payload: cegah fraud reuse key
        if (record.payloadHash !== payloadHash) {
          res.status(422).json({
            error: 'Unprocessable Entity: Idempotency-Key telah digunakan dengan payload berbeda.',
          });
          return;
        }

        if (record.status === IdempotencyStatus.IN_PROGRESS) {
          res.status(409).json({
            error: 'Conflict: Transaksi sedang berjalan. Jangan lakukan pengulangan bersamaan.',
          });
          return;
        }

        // Return cached response jika status RESOLVED
        if (record.status === IdempotencyStatus.RESOLVED && record.responseBody) {
          if (record.responseHeaders) {
            for (const [headerKey, headerVal] of Object.entries(record.responseHeaders)) {
              res.setHeader(headerKey, headerVal);
            }
          }
          res.setHeader('X-Cache-Lookup', 'HIT - Idempotent Replay');
          res.status(record.statusCode || 200).send(JSON.parse(record.responseBody));
          return;
        }
      }

      // 4. Peroleh Lock menggunakan atomic SET NX
      const lockAcquired = await redis.set(lockKey, 'LOCKED', 'EX', 30, 'NX');
      if (!lockAcquired) {
        res.status(409).json({
          error: 'Conflict: Transaksi concurrent terdeteksi pada key yang sama.',
        });
        return;
      }

      // Tandai status awal sebagai IN_PROGRESS
      const initialRecord: IdempotencyRecord = {
        status: IdempotencyStatus.IN_PROGRESS,
        payloadHash,
      };
      await redis.set(cacheKey, JSON.stringify(initialRecord), 'EX', ttlSeconds);

      // 5. Intercept res.send untuk menangkap response body & status
      const originalSend = res.send.bind(res);

      res.send = (body: any): Response => {
        // Jalankan operasi cleanup dan caching secara asinkron
        (async () => {
          try {
            const finalRecord: IdempotencyRecord = {
              status: IdempotencyStatus.RESOLVED,
              payloadHash,
              statusCode: res.statusCode,
              responseBody: typeof body === 'string' ? body : JSON.stringify(body),
              responseHeaders: {
                'content-type': res.getHeader('content-type') as string,
              },
            };

            await redis.set(cacheKey, JSON.stringify(finalRecord), 'EX', ttlSeconds);
            await redis.del(lockKey); // Lepaskan distributed lock
          } catch (err) {
            console.error('Failed to commit idempotency record to Redis', err);
          }
        })();

        return originalSend(body);
      };

      next();
    } catch (error) {
      await redis.del(lockKey);
      next(error);
    }
  };
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Optimistic Concurrency Control (OCC) | Distributed Locking (Pessimistic) | Saga Orchestration |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Implementasi** | **Rendah**: Hanya butuh version/ETag check di query DB. | **Tinggi**: Membutuhkan distributed coordinator (Redis/Zookeeper) & fencing token. | **Sangat Tinggi**: State machine terdistribusi, compensations, outbox pattern. |
| **Throughput / Latensi** | Sangat Tinggi di bawah kondisi *low contention*. | Sedang: Terbatas pada TTL lock, contention serializing requests. | Tinggi secara agregat, namun latensi *eventual consistency* signifikan. |
| **Toleransi Kontensi Tinggi** | Buruk: Klien sering terkena `412 Precondition Failed` & harus retry manual. | Baik: Mengantre transaksi dan mencegah kegagalan eksekusi serentak. | Sangat Baik: Mengisolasi step mutasi per domain secara asinkron. |
| **Blast Radius Kegagalan** | Terisolir pada query lokal database instance tersebut. | Global: Jika Redis mati/split-brain, seluruh cluster API gagal mutasi. | Parsial: Service hilir down memicu *compensating rollback*, data kembali stabil. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan SHA-256 Request Body Hash Binding**: Jangan hanya mencocokkan `Idempotency-Key` secara string murni. Simpan hash dari URL + Body. Jika ada bad actor atau bug client yang mengirim payload berbeda menggunakan key lama, tolak langsung dengan `422 Unprocessable Entity`.
2. **Implementasikan Fencing Token pada Distributed Lock**: Jangan pernah mengandalkan lock expiration time secara naif. Database storage engine harus menolak write jika transaksi membawa token monotonic yang lebih rendah dari token transaksi yang telah commit sebelumnya.
3. **Standarisasi Conditional Headers**: Gunakan `ETag` kuat (*strong validator* diawali tanpa `W/`) untuk operasi mutasi finansial/inventaris, dan wajibkan header `If-Match` dengan membalas `428 Precondition Required` jika header tidak dikirim client.
4. **Desain Compensating Transaction yang Idempoten**: Dalam pola Saga, transaksi kompensasi (pembatalan) dapat dipanggil berulang kali akibat jaringan yang *flaky*. Pastikan fungsi *refund* atau *restock* aman dieksekusi berkali-kali (*idempotent compensation*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Membiarkan State Lock Menggantung (*Orphaned Lock*)**: Tidak membungkus eksekusi handler dalam blok `finally` atau tidak memberikan TTL ketat pada Redis lock, sehingga saat server app crash, endpoint terkunci permanen.
2. **Tidak Menangani Replay Concurrent Request**: Mengembalikan response kosong saat status masih `IN_PROGRESS`. Seharusnya API mengembalikan `409 Conflict` dengan header `Retry-After: N` agar client menunggu thread pertama selesai.
3. **Mengabaikan Semantic Response HTTP**: Mengembalikan `200 OK` saat validasi `If-Match` gagal, padahal RFC 9110 secara eksplisit mewajibkan `412 Precondition Failed`.
4. **Saga Compensating Failure Blindness**: Mengasumsikan bahwa *compensating transaction* pasti selalu sukses. Tanpa Dead Letter Queue (DLQ) dan Human-in-the-loop Reconciliation Dashboard, kegagalan kompensasi menyebabkan data corrupt permanen di sistem keuangan.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: OCC Bank Account Balance
Rancang tabel PostgreSQL dan endpoint Express.js untuk mendebit saldo rekening bank. 
* Persyaratan: Gunakan column `version INT`. Jika dua thread melakukan debit Rp10.000 serentak pada akun yang bersaldo Rp50.000, satu request harus berhasil dan request lainnya harus menerima `412 Precondition Failed` tanpa anomali *negative balance*.

### Latihan 2: Saga Choreography Compensation Engine
Bangun simulasi alur checkout:
1. `OrderCreatedEvent` dipublish.
2. `PaymentService` memproses pembayaran namun gagal akibat `INSUFFICIENT_FUNDS`.
3. `PaymentFailedEvent` dipublish.
4. `InventoryService` menangkap event kegagalan dan melepas kembali alokasi item yang sempat di-reserve.
* Persyaratan: Semua handler event harus bersifat idempoten menggunakan tracking ID unik.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Mengapa algoritma Redlock murni tanpa fencing token dianggap tidak aman untuk skenario critical data storage oleh Martin Kleppmann?**
   * *Jawaban*: Karena di lingkungan nyata, proses dapat mengalami Garbage Collection (GC) pause yang tidak terprediksi, paging memory stalls, atau network delay yang melampaui masa berlaku (lease/TTL) lock di Redis. Ketika client terbangun dari pause, lock telah diakuisisi client lain, sehingga kedua client mengakses shared resource secara serentak (*split-brain*).

2. **Kapan HTTP Status Code 428 Precondition Required harus digunakan?**
   * *Jawaban*: Ketika server mewajibkan request mutatif (seperti `PUT` atau `PATCH`) menyertakan conditional header (`If-Match`), untuk mencegah insiden *lost updates* di mana client memutasi state tanpa mengetahui baseline state terakhir.

3. **Apa perbedaan mendasar antara Backward Recovery dan Forward Recovery pada Saga Pattern?**
   * *Jawaban*: Backward Recovery mengeksekusi *compensating transactions* untuk membatalkan semua step yang telah sukses jika salah satu step di tengah jalan gagal. Sedangkan Forward Recovery tidak membatalkan, melainkan terus mencoba (retry) atau beralih ke state alternatif hingga seluruh alur transaksi berhasil diselesaikan.

4. **Apa bahaya mengembalikan HTTP 200 dengan payload cached jika client mengirimkan Idempotency Key yang sama namun dengan nilai Body amount yang berbeda?**
   * *Jawaban*: Bahaya fraud dan ambiguitas state. Klien mengira mutasi baru dengan nilai berbeda telah berhasil dieksekusi, padahal server hanya mengembalikan respons dari transaksi lama. Harus dibalas dengan status `422 Unprocessable Entity`.

5. **Apa fungsi weak ETag (`W/"..."`) dibandingkan strong ETag? Bisakah weak ETag digunakan pada header If-Match untuk operasi PUT?**
   * *Jawaban*: Weak ETag hanya menjamin kesetaraan semantik data, bukan representasi byte-per-byte yang identik. Berdasarkan RFC 9110, weak ETag *tidak boleh* digunakan untuk validator pada header `If-Match` dalam operasi mutasi ketat kecuali server secara eksplisit mengizinkannya untuk full-overwrite semantics.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **IETF RFC 9110**: *HTTP Semantics (Conditional Requests & ETag Evaluation)*.
* **IETF Draft**: *The Idempotency-Key HTTP Header Field* (`draft-ietf-httpapi-idempotency-key-header-04`).
* **Martin Kleppmann**: *How to do distributed locking* (Debat analisis Redlock vs Fencing Tokens).
* **Chris Richardson**: *Microservices Patterns: With examples in Java (Saga Pattern chapters)*. Manning Publications.
* **Stripe Engineering Blog**: *Designing robust and predictable APIs with idempotency*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Mutasi data dalam sistem terdistribusi tidak dapat diselesaikan hanya dengan database locking lokal karena adanya latensi jaringan, retry storms, dan konkurensi multi-node.
2. **Idempotency Keys** melindungi API dari duplikasi transaksi akibat kegagalan transmisi jaringan; implementasinya wajib memvalidasi hash payload deterministik.
3. **ETag dan If-Match** adalah mekanisme standar Web HTTP untuk mengimplementasikan *Optimistic Concurrency Control* tanpa overhead stateful session.
4. **Distributed Locks** memerlukan mekanisme sewa (*lease/TTL*) dan *fencing tokens* untuk menjamin konsistensi mutlak saat terjadi anomali runtime engine.
5. **Saga Pattern** menggantikan ACID transaksional lintas batas microservice menggunakan orkestrasi terstruktur dan aksi kompensasi yang idempoten.

---

## SEKSI 17 — GLOSARIUM

* **Idempotency**: Sifat operasi di mana eksekusi berkali-kali menghasilkan efek samping (*side-effect*) yang identik dengan eksekusi pertama kali.
* **Fencing Token**: Angka urutan (monotonic counter) yang disertakan pada setiap penulisan resource untuk memvalidasi bahwa pemegang lock saat ini masih sah.
* **Optimistic Concurrency Control (OCC)**: Metode kontrol konkurensi yang mengizinkan banyak transaksi membaca dan memvalidasi sebelum commit, lalu membatalkan transaksi jika ada konflik versi data.
* **Compensating Transaction**: Operasi semantik terdistribusi yang membatalkan efek dari transaksi lokal yang sebelumnya telah sukses di-commit.
* **Split-Brain**: Anomali sistem terdistribusi di mana dua atau lebih node mengira diri mereka sebagai pemilik sah sebuah lock/state secara bersamaan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* Tekankan kepada siswa bahwa **Idempotency Key tidak boleh dibuat oleh server**, melainkan *harus* digenerate oleh client (initiator) sebelum paket dikirim ke jaringan.
* Siapkan lab Redis cluster lokal (misal menggunakan Docker Compose) untuk mendemonstrasikan latency injection dengan tools seperti `tc` (Linux Traffic Control) agar siswa melihat langsung bagaimana fencing token menggugurkan request yang *stale*.
* Tunjukkan perbedaan nyata antara status `409 Conflict` (saat request concurrent sedang diproses) vs `422 Unprocessable Entity` (saat key dipakai ulang untuk payload berbeda).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal**: 2025-01-15
* **Author**: Senior Technical Curriculum Architect
* **Perubahan**:
  * Inisialisasi rilis kurikulum Distributed Systems API Design.
  * Penambahan kode implementasi TypeScript Redis Idempotency Middleware lengkap.
  * Penyempurnaan sequence diagrams ASCII untuk ETag evaluation dan Saga Compensation.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `06-Architecture-and-System-Design/04-Event-Driven-APIs-Webhooks-SSE-WebSockets`
* **Modul Berikutnya**: `06-Architecture-and-System-Design/06-Resilience-Patterns-RateLimiting-CircuitBreakers-Bulkheads`
* **Root Index**: `API-Design-Advanced-Curriculum-Master-Index`