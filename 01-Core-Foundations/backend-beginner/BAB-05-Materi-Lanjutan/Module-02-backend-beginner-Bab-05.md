# BAB 05: Materi Lanjutan
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Menerapkan** arsitektur *Clean Layered Architecture* (Controller-Service-Repository-Domain) untuk memisahkan *concern* bisnis dari infrastruktur transport dan persistensi data.
2. **Mengelola Siklus Hidup Koneksi & Sumber Daya** (*Resource Lifecycle Management*), mencakup *Connection Pooling* database, *OS File Descriptors*, serta mekanisme *Graceful Shutdown* (`SIGTERM`/`SIGINT`) tanpa menyebabkan *downtime* atau *data corruption*.
3. **Mengimplementasikan Transaksi Database Lanjutan** dengan kontrol konkurensi eksplisit (*Pessimistic Locking* dan *Optimistic Locking*) guna mencegah anomali *Lost Updates* dan *Write Skew*.
4. **Membangun Sistem Observabilitas Terintegrasi** menggunakan *Structured Logging* (JSON) berbasis *Correlation/Trace ID* dan *Context Propagation* lintas lapisan aplikasi.
5. **Menerapkan Pola Ketahanan Sistem** (*System Resiliency Patterns*), seperti *Circuit Breaker*, *Idempotency Keys*, dan *Exponential Backoff with Jitter*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Fondasi protokol HTTP/1.1 dan HTTP/2 (Metode, Status Code, Header, Connection Keep-Alive).
* Dasar-dasar asynchronous runtime (Event Loop, Thread Pool, Promises/Goroutine/Async-Await).
* Sintaks dasar SQL dan operasi CRUD standar (DML dan DDL).
* Konsep RESTful API tingkat dasar (Routing, Request/Response payload parsing).

---

### 3. Concept & Internal Architecture

Ketika aplikasi backend beralih dari lingkungan pengujian lokal (*hobbyist/development*) ke lingkungan produksi berskala enterprise, kompleksitas sistem tidak lagi berpusat pada penulisan logika `if-else`, melainkan pada **pengelolaan konkurensi, keandalan state, dan batasan sumber daya fisik mesin (I/O, Memory, CPU)**.

```
+-----------------------------------------------------------------------------------+
| LINUX KERNEL SPACE                                                                |
|  [Network Interface Card (NIC)] ---> [TCP Socket Backlog (SYN/ACCEPT Queue)]      |
+------------------------------------------|----------------------------------------+
                                           | File Descriptor Notification (epoll/kqueue)
+------------------------------------------v----------------------------------------+
| APPLICATION RUNTIME (USER SPACE)                                                  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | [1. Ingress Layer: Reverse Proxy / HTTP Server Engine]                     |  |
|  | - TLS Termination & TCP Handshake                                          |  |
|  | - Context Initialization (Trace ID, Timeout context.Context / AbortSignal) |  |
|  +---------------------------------------|-------------------------------------+  |
|                                          v                                        |
|  +-----------------------------------------------------------------------------+  |
|  | [2. Transport / Controller Layer]                                           |  |
|  | - Schema Validation & Serialization                                         |  |
|  | - HTTP Code Mapping (Domain Error -> RFC 7807 Problem Details)             |  |
|  +---------------------------------------|-------------------------------------+  |
|                                          v                                        |
|  +-----------------------------------------------------------------------------+  |
|  | [3. Domain / Service Layer]                                                 |  |
|  | - Pure Business Logic Execution                                             |  |
|  | - Unit of Work / Transaction Boundary Coordinator                           |  |
|  | - Idempotency Validation Engine                                             |  |
|  +---------------------------------------|-------------------------------------+  |
|                                          v                                        |
|  +-----------------------------------------------------------------------------+  |
|  | [4. Infrastructure / Repository Layer]                                      |  |
|  | - SQL Query Composition & Object Relational Mapping                         |  |
|  | - Connection Pool Manager (Acquire Lock -> Execute -> Release)             |  |
|  +---------------------------------------|-------------------------------------+  |
+------------------------------------------|----------------------------------------+
                                           | TCP Sockets Pool (Keep-Alive)
+------------------------------------------v----------------------------------------+
| DATABASE ENGINE (PostgreSQL/MySQL)                                                |
|  [Lock Manager] ---> [WAL (Write-Ahead Log)] ---> [Buffer Pool / Shared Memory]   |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kritis Arsitektur Produksi:

1. **OS Socket & File Descriptors:**
   Setiap koneksi HTTP masuk dialokasikan sebagai satu *File Descriptor* (FD) oleh OS kernel. Jika kernel mencapai limit `ulimit -n`, aplikasi akan melempar galat `EMFILE: too many open files`. Arsitektur produksi harus membatasi ukuran backlog antrean TCP dan menerapkan *backpressure*.

2. **Connection Pool Internal State:**
   Membuka koneksi database membutuhkan proses *three-way TCP handshake*, negosiasi TLS, dan autentikasi kredensial (rata-rata 30–100ms latency overhead). Connection pool mempertahankan status koneksi tetap *warm*:
   * `Idle Connections`: Koneksi siap pakai yang berada di pool.
   * `Active/Leased Connections`: Koneksi yang sedang memproses query.
   * `Wait Queue`: Antrean thread/rutin yang menunggu koneksi kosong saat kapasitas maksimum (`max_connections`) tercapai. Jika waktu tunggu melampaui `connectionTimeout`, query dibatalkan (*pool exhaustion*).

3. **Transaction Context & Isolation Boundary:**
   Transaksi database enterprise (`BEGIN ... COMMIT`) harus terisolasi dari lapisan presentasi. Penggunaan context propagation memastikan koneksi fisik yang sama di-*pin* untuk seluruh operasi di dalam sebuah *Unit of Work* sebelum dikembalikan ke pool.

---

### 4. Why & What

| Paradigma Pemula (*Naive Scripting*) | Paradigma Produksi Enterprise | Mengapa Berbeda? (*Impact & Risk*) |
| :--- | :--- | :--- |
| Membuka dan menutup koneksi database di setiap request (`connect()` lalu `close()`). | Menggunakan *Persistent Thread-Safe Connection Pool* dengan ukuran minimum dan maksimum terukur. | Mencegah lonjakan TCP Handshake & kehabisan port lokal (*ephemeral port exhaustion* / TIME_WAIT saturation). |
| Logika validasi, domain bisnis, dan query SQL digabung dalam satu handler endpoint. | *Clean Layered Architecture* (Separation of Concerns). | Kode dapat diuji secara terisolasi via *mocking/stubbing* tanpa menyentuh database fisik. |
| Server langsung dimatikan paksa via kill command saat proses deployment. | Implementasi *Graceful Shutdown* (`SIGINT`/`SIGTERM` interception). | Mencegah transaksi database terputus di tengah jalan (*in-flight request drop*) dan merusak konsistensi data. |
| Penggunaan log sederhana: `console.log("Error here")` atau `print()`. | *Structured JSON Logging* dilengkapi `trace_id`, `span_id`, dan contextual metadata. | Menjamin log dapat diurai secara terpusat (*ingested*) oleh Log Aggregator (Elasticsearch/Loki) untuk audit forensik. |
| Update data tanpa proteksi konkurensi (Fetch -> Modify in Memory -> Save). | Penerapan *Pessimistic Locking* (`SELECT FOR UPDATE`) atau *Optimistic Locking* (`version column`). | Menghilangkan celah *Race Condition* (*Double Spending*, *Inventory Overselling*). |

---

### 5. How (Workflow Detail)

Alur penanganan satu siklus request produksi berdaya tahan tinggi:

```
[Client] 
   |
   | 1. HTTP Request + Traceparent Header
   v
[HTTP Ingress Engine]
   |
   | 2. Ekstrak Trace Context / Generate Correlation ID
   | 3. Pasang Timeout Context (ct = 5000ms)
   v
[Middleware Pipeline]
   |
   |-- A. Global Error Boundary / Panic Recoverer
   |-- B. Structured Audit Logger (Log: request_started)
   |-- C. Rate Limiting (Token Bucket per IP/Identity)
   v
[Controller / Route Handler]
   |
   | 4. Deserialisasi payload & Validasi Skema Ketat
   | 5. Transformasi DTO -> Domain Entity
   v
[Service Layer (Domain Engine)]
   |
   | 6. Inisiasi Unit of Work (Transaction Manager)
   | 7. Verifikasi Idempotency Key
   | 8. Eksekusi Core Business Rules
   v
[Repository Layer]
   |
   | 9. Acquire DB Connection dari Pool (Locking)
   | 10. Eksekusi SQL State Changes
   v
[Database Engine]
   |
   | 11. Write-Ahead Logging & Engine Commit
   v
[Service Layer]
   |
   | 12. Commit Transaction
   v
[Controller / Route Handler]
   |
   | 13. Map Entity -> Response DTO
   v
[HTTP Ingress Engine]
   |
   | 14. Serialize JSON + Set Response Headers
   | 15. Kirim HTTP 200/201
   v
[Middleware Pipeline]
   |
   | 16. Log: request_completed (duration_ms, status_code)
   v
[Client]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan backend enterprise sebagai sebuah **Restoran Mewah Bintang Lima**:

* **Client**: Pelanggan yang datang memesan makanan.
* **Controller (Pramusaji)**: Menerima pesanan pelanggan, memeriksa apakah menu tersedia di buku menu (validasi schema), dan menolak pesanan jika formatnya salah tanpa repot-repot bertanya ke koki.
* **Service Layer (Kepala Koki)**: Memegang resep rahasia (Business Logic). Tahu persis kapan daging harus dibalik dan bumbu apa yang harus diracik. Tidak peduli daging dibeli dari pasar mana.
* **Repository Layer (Manajer Gudang Bahan Makanan)**: Hanya bertugas mengambil atau menyimpan bahan makanan ke tempat penyimpanan fisik.
* **Database Connection Pool (Kunci Masuk Ruang Pendingin)**: Hanya ada 10 kunci lemari es (Max Pool Size). Koki tidak boleh membuat kunci baru sendiri. Koki harus mengantre mengambil kunci, mengambil bahan secepat mungkin, dan segera mengembalikan kunci tersebut ke rak.

```
       CLIENT (Pelanggan)
               |
               v
    +----------------------+
    |      CONTROLLER      |  <- Validasi: "Format pesanan valid?"
    +----------------------+
               |
               v
    +----------------------+
    |       SERVICE        |  <- Logika Bisnis: "Apakah saldo cukup? Terapkan diskon."
    +----------------------+
               |
               v
    +----------------------+
    |      REPOSITORY      |  <- Data Access: "Jalankan SQL Query ke Table"
    +----------------------+
               |
        [Pinjam Kunci]
               v
    +----------------------+
    |   CONNECTION POOL    |  <- Pool Slot: [K1] [K2] [..] [K10]
    +----------------------+
               |
               v
    +----------------------+
    |       DATABASE       |  <- Persistensi Fisik
    +----------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Naïve Implementation vs. Production Pooling

##### Anti-Pattern (Naïve: Rentan Pool Starvation & Memory Leak)
```typescript
// JANGAN LAKUKAN INI DI PRODUKSI:
// Membuka Client baru setiap request = Menghancurkan performa OS & DB
import { Client } from 'pg';

export async function naiveGetUser(userId: string) {
  const client = new Client({ connectionString: process.env.DATABASE_URL });
  await client.connect(); // Handshake berulang-ulang
  try {
    const result = await client.query('SELECT * FROM users WHERE id = $1', [userId]);
    return result.rows[0];
  } finally {
    await client.end(); // Socket teardown berulang
  }
}
```

##### Production Implementation: Thread-safe Connection Pool Manager
```typescript
// pool.ts - Singleton Enterprise Pool Management
import { Pool, PoolConfig } from 'pg';

const poolConfig: PoolConfig = {
  connectionString: process.env.DATABASE_URL,
  max: 20,                      // Maksimum koneksi aktif simultan
  min: 5,                       // Minimum koneksi idle yang selalu ready
  idleTimeoutMillis: 30000,     // Putus koneksi jika idle selama 30 detik
  connectionTimeoutMillis: 2000 // Gagal cepat jika pool penuh dalam 2 detik
};

export const dbPool = new Pool(poolConfig);

dbPool.on('error', (err) => {
  // Tangkap anomali fatal pada idle client (misal: DB restart)
  console.error(JSON.stringify({
    level: 'FATAL',
    message: 'Unexpected error on idle database client',
    error: err.stack
  }));
});
```

---

#### B. Practical Enterprise Example: Layered Architecture with Unit of Work, Concurrency Lock, & Structured Telemetry

Implementasi modul transfer saldo enterprise menggunakan TypeScript/Node.js standard:

##### 1. Domain Entities & Errors
```typescript
// domain/errors.ts
export class DomainError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message);
    this.name = 'DomainError';
  }
}

export class InsufficientFundsError extends DomainError {
  constructor() {
    super('Insufficient account balance for this transaction', 'INSUFFICIENT_FUNDS');
  }
}

export class AccountNotFoundError extends DomainError {
  constructor(accountId: string) {
    super(`Account with ID ${accountId} was not found`, 'ACCOUNT_NOT_FOUND');
  }
}
```

##### 2. Repository Layer (Data Access with Transaction Context)
```typescript
// repository/account.repository.ts
import { PoolClient } from 'pg';

export interface AccountEntity {
  id: string;
  balance: number;
  version: number;
}

export class AccountRepository {
  /**
   * Mengambil akun dengan Pessimistic Locking (FOR UPDATE)
   * Menjamin baris data dikunci di level DB hingga transaksi selesai.
   */
  async getByIdForUpdate(client: PoolClient, accountId: string): Promise<AccountEntity | null> {
    const query = `
      SELECT id, balance, version 
      FROM accounts 
      WHERE id = $1 
      FOR UPDATE;
    `;
    const res = await client.query(query, [accountId]);
    if (res.rows.length === 0) return null;
    
    return {
      id: res.rows[0].id,
      balance: parseFloat(res.rows[0].balance),
      version: res.rows[0].version
    };
  }

  async updateBalance(client: PoolClient, accountId: string, newBalance: number): Promise<void> {
    const query = `
      UPDATE accounts 
      SET balance = $1, version = version + 1, updated_at = NOW() 
      WHERE id = $2;
    `;
    await client.query(query, [newBalance, accountId]);
  }
}
```

##### 3. Service Layer (Business Engine & Unit of Work)
```typescript
// service/transfer.service.ts
import { Pool } from 'pg';
import { AccountRepository } from '../repository/account.repository';
import { InsufficientFundsError, AccountNotFoundError } from '../domain/errors';

export interface TransferCommand {
  fromAccountId: string;
  toAccountId: string;
  amount: number;
  traceId: string;
}

export class TransferService {
  constructor(
    private readonly dbPool: Pool,
    private readonly accountRepo: AccountRepository
  ) {}

  async executeTransfer(cmd: TransferCommand): Promise<{ txId: string }> {
    if (cmd.amount <= 0) {
      throw new Error('Transfer amount must be strictly positive');
    }

    // Acquire dedicated connection for transactional boundary
    const client = await this.dbPool.connect();
    
    try {
      await client.query('BEGIN');

      // Ambil akun pengirim dengan Pessimistic Lock
      const sender = await this.accountRepo.getByIdForUpdate(client, cmd.fromAccountId);
      if (!sender) throw new AccountNotFoundError(cmd.fromAccountId);

      // Ambil akun penerima dengan Pessimistic Lock
      const recipient = await this.accountRepo.getByIdForUpdate(client, cmd.toAccountId);
      if (!recipient) throw new AccountNotFoundError(cmd.toAccountId);

      // Evaluasi Domain Rule
      if (sender.balance < cmd.amount) {
        throw new InsufficientFundsError();
      }

      // Mutasi State
      await this.accountRepo.updateBalance(client, sender.id, sender.balance - cmd.amount);
      await this.accountRepo.updateBalance(client, recipient.id, recipient.balance + cmd.amount);

      // Commit State Atomic
      await client.query('COMMIT');
      
      return { txId: cmd.traceId };
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      // WAJIB: Kembalikan koneksi ke pool dalam keadaan apa pun
      client.release();
    }
  }
}
```

##### 4. Controller Layer (Transport, Telemetry & HTTP Mapping)
```typescript
// controller/transfer.controller.ts
import { IncomingMessage, ServerResponse } from 'http';
import { TransferService } from '../service/transfer.service';
import { DomainError } from '../domain/errors';

export class TransferController {
  constructor(private readonly transferService: TransferService) {}

  async handleTransfer(req: IncomingMessage, res: ServerResponse, body: any, traceId: string) {
    const startTime = process.hrtime.bigint();

    try {
      // 1. Validasi Input Dasar
      if (!body.fromAccountId || !body.toAccountId || typeof body.amount !== 'number') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          type: 'https://api.domain.com/errors/invalid-payload',
          title: 'Bad Request',
          status: 400,
          detail: 'Payload does not meet contractual specifications.',
          traceId
        }));
        return;
      }

      // 2. Delegasi ke Service
      const result = await this.transferService.executeTransfer({
        fromAccountId: body.fromAccountId,
        toAccountId: body.toAccountId,
        amount: body.amount,
        traceId
      });

      // 3. Response Berhasil
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', data: result }));

    } catch (error: any) {
      this.handleError(error, res, traceId);
    } finally {
      const endTime = process.hrtime.bigint();
      const durationMs = Number(endTime - startTime) / 1_000_000;
      
      // Structured Access Log
      process.stdout.write(JSON.stringify({
        level: 'INFO',
        type: 'ACCESS_LOG',
        traceId,
        method: req.method,
        url: req.url,
        statusCode: res.statusCode,
        durationMs
      }) + '\n');
    }
  }

  private handleError(error: any, res: ServerResponse, traceId: string) {
    if (error instanceof DomainError) {
      const statusCode = error.code === 'INSUFFICIENT_FUNDS' ? 422 : 404;
      res.writeHead(statusCode, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        type: `https://api.domain.com/errors/${error.code.toLowerCase()}`,
        title: error.name,
        status: statusCode,
        detail: error.message,
        traceId
      }));
      return;
    }

    // Unexpected Internal Failure (500)
    process.stderr.write(JSON.stringify({
      level: 'ERROR',
      traceId,
      message: 'Unhandled internal system anomaly',
      stack: error.stack
    }) + '\n');

    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      type: 'https://api.domain.com/errors/internal-server-error',
      title: 'Internal Server Error',
      status: 500,
      detail: 'An unhandled infrastructure error occurred.',
      traceId
    }));
  }
}
```

##### 5. Bootstrap & Graceful Shutdown Engine
```typescript
// server.ts
import http from 'http';
import crypto from 'crypto';
import { dbPool } from './pool';
import { AccountRepository } from './repository/account.repository';
import { TransferService } from './service/transfer.service';
import { TransferController } from './controller/transfer.controller';

const accountRepo = new AccountRepository();
const transferService = new TransferService(dbPool, accountRepo);
const transferController = new TransferController(transferService);

const server = http.createServer((req, res) => {
  // Tracing Context Propagation
  const traceId = (req.headers['x-trace-id'] as string) || crypto.randomUUID();
  res.setHeader('X-Trace-Id', traceId);

  if (req.method === 'POST' && req.url === '/transfers') {
    let bodyData = '';
    req.on('data', chunk => { bodyData += chunk; });
    req.on('end', () => {
      try {
        const parsed = JSON.parse(bodyData || '{}');
        transferController.handleTransfer(req, res, parsed, traceId);
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Malformed JSON payload' }));
      }
    });
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Endpoint Not Found' }));
  }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(JSON.stringify({ level: 'INFO', message: `Server listening on port ${PORT}` }));
});

// Production Graceful Termination Engine
function shutdown(signal: string) {
  console.log(JSON.stringify({ level: 'WARN', message: `Received ${signal}. Starting graceful drain...` }));

  // 1. Berhenti menerima koneksi baru dari load balancer
  server.close(async () => {
    console.log(JSON.stringify({ level: 'INFO', message: 'HTTP server closed. In-flight requests completed.' }));
    
    // 2. Drain Database Pool
    try {
      await dbPool.end();
      console.log(JSON.stringify({ level: 'INFO', message: 'Database connection pool completely drained.' }));
      process.exit(0);
    } catch (err) {
      console.error(JSON.stringify({ level: 'FATAL', message: 'Error draining database pool', error: err }));
      process.exit(1);
    }
  });

  // Fail-safe: Paksa kill jika graceful drain macet lebih dari 10 detik
  setTimeout(() => {
    console.error(JSON.stringify({ level: 'FATAL', message: 'Graceful shutdown timed out. Forcing process kill.' }));
    process.exit(1);
  }, 10000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Flash Sale "Double Spending" & Database Pool Starvation pada Ticketing Skala Masif

* **Konteks:** Perusahaan tiket konser internasional mengalami lonjakan 80.000 RPS dalam 3 detik pertama saat penjualan tiket dibuka.
* **Insiden:**
  1. Server database utama mengalami kehabisan koneksi (*Connection Pool Exhaustion*). Latensi melonjak dari 15ms menjadi 12.000ms.
  2. Terjadi penjualan tiket melebihi kapasitas (*overselling*): 500 tiket terjual kepada 612 pengguna secara simultan.
  3. Load Balancer mendeteksi server tidak responsif (karena thread terkunci menunggu DB), lalu me-restart instance container secara serentak. Akibatnya, ribuan transaksi terputus saat proses penulisan saldo berlangsung.

#### Akar Masalah (*Root Cause Analysis*):
1. **Overselling:** Kode aplikasi membaca sisa kuota dengan query `SELECT stock FROM events WHERE id = 1` lalu melakukan `UPDATE events SET stock = stock - 1` secara terpisah di memori aplikasi tanpa *Pessimistic Row-Level Lock* atau *Atomic Decrement*.
2. **Resource Exhaustion:** Parameter `max_connections` aplikasi disetel ke 100 per container dengan 30 replica container ($100 \times 30 = 3000$ koneksi simultan), melebihi batas PostgreSQL server (500 koneksi), memicu *Denial of Service* internal.
3. **Cascading Failure:** Tidak ada mekanisme *Circuit Breaker* atau *Reverse Proxy Rate Limiting*.

#### Solusi Rekayasa Sistem:
1. **Penerapan Row-Level Lock dengan Atomic Decrement:**
   ```sql
   UPDATE inventory 
   SET available_stock = available_stock - 1 
   WHERE event_id = $1 AND available_stock > 0 
   RETURNING id;
   ```
2. **Arsitektur Connection Pooling Berlapis (Proxy-Tier Pooling):**
   * Memasang **PgBouncer** di depan PostgreSQL sebagai *Transaction Pooler*. Container aplikasi dibatasi maksimal 10 koneksi saja, sementara PgBouncer mengantre ribuan kueri masuk ke 50 koneksi fisik database yang stabil.
3. **Idempotency Engine dengan Redis Token Bucket:**
   * Setiap request checkout wajib menyertakan `Idempotency-Key` (UUIDv4) yang diverifikasi di distributed cache via atomic script (`SET key value NX PX 10000`).

---

### 9. Trade-offs

Setiap keputusan arsitektur memiliki konsekuensi struktural:

```
                  KONSISTENSI & KEAMANAN
                         /\
                        /  \
                       /    \
  Pessimistic Locking /      \ Optimistic Locking
  (Low Thruput,      /        \ (High Thruput, High Conflict
   Zero Conflict)   /          \ Aborts on Hotspot)
                   /            \
                  /______________\
LATENSI TINGGI                      LATENSI RENDAH &
(Menunggu Antrean Lock)             OVERHEAD KOMPUTASI RETRY
```

1. **Pessimistic Locking (`SELECT FOR UPDATE`) vs. Optimistic Locking (`version column`):**
   * *Pessimistic:*
     * **Kelebihan:** Mencegah modifikasi konkuren sejak awal; aman untuk data yang sangat diperebutkan (*high contention*).
     * **Kekurangan:** Terjadinya database lock contention, latensi query melonjak drastis, berisiko *Deadlock*.
   * *Optimistic:*
     * **Kelebihan:** Sangat cepat untuk sistem dengan konkurensi rendah hingga menengah (*read-heavy*).
     * **Kekurangan:** Jika terjadi benturan, transaksi digagalkan dan klien harus melakukan retry. Pada kondisi *high contention*, throughput justru anjlok akibat badai retry.

2. **Connection Pool Sizing:**
   * Formula Heuristik PostgreSQL: $\text{connections} = ((\text{CPU cores} \times 2) + \text{effective disk count})$.
   * *Pool Terlalu Besar:* Konteks switching pada CPU database meningkat, memori habis (*Out of Memory*), latensi rata-rata memburuk.
   * *Pool Terlalu Kecil:* Waktu antre (*queue wait time*) pada aplikasi meningkat, memicu `ConnectionTimeoutError`.

3. **Structured Logging (JSON) vs. Raw Text:**
   * JSON Logging mengonsumsi I/O memori dan disk throughput hingga 25% lebih besar, namun wajib digunakan di enterprise agar log dapat di-ingest, di-filter, dan di-alert oleh mesin otomatis (SIEM/Datadog/Elastic).

---

### 10. Common Mistakes & Troubleshooting

#### 1. Connection Leak (Lupa Melepaskan Koneksi)
* **Gejala:** Aplikasi berjalan normal selama 2 jam, kemudian tiba-tiba semua request timeout secara konsisten (`Timeout waiting for connection from pool`).
* **Penyebab:** Eksekusi kode keluar melalui blok `if` atau melempar error sebelum fungsi `client.release()` sempat dipanggil.
* **Troubleshooting:** Selalu gunakan blok `try ... finally { client.release(); }`. Di PostgreSQL, jalankan query diagnostik:
  ```sql
  SELECT pid, state, query, age(clock_timestamp(), query_start) 
  FROM pg_stat_activity 
  WHERE state = 'idle in transaction';
  ```

#### 2. The N+1 Query Problem di Lapisan Repository
* **Gejala:** Latensi endpoint memanjang linier mengikuti jumlah entitas yang diambil ($10 \text{ item} = 11 \text{ query}; 1000 \text{ item} = 1001 \text{ query}$).
* **Solusi:** Gunakan teknik SQL `JOIN` eksplisit atau polakan dengan *Batch Fetching* (menggunakan klausa `WHERE id IN (...)`).

#### 3. Unhandled Promise Rejection Membunuh Node.js Event Loop
* **Gejala:** Worker container sering restart mendadak dengan exit code 1.
* **Solusi:**
  ```typescript
  process.on('unhandledRejection', (reason: any) => {
    console.error(JSON.stringify({
      level: 'FATAL',
      message: 'Unhandled Promise Rejection detected',
      reason: reason?.stack || reason
    }));
    // Jangan biarkan aplikasi dalam status undefined; exit dan biarkan orchestrator (K8s) me-restart
    process.exit(1);
  });
  ```

#### 4. Deadlock Akibat Urutan Lock yang Berbeda
* **Penyebab:** Transaksi A mengunci Akun 1 lalu meminta Akun 2. Transaksi B mengunci Akun 2 lalu meminta Akun 1 secara bersamaan. Keduanya saling menunggu selamanya hingga dibatalkan oleh *deadlock detector*.
* **Solusi:** Tetapkan urutan penguncian universal (*Deterministic Lock Ordering*). Urutkan ID sebelum melakukan query lock:
  ```typescript
  const [firstLock, secondLock] = [accountIdA, accountIdB].sort();
  await repo.getByIdForUpdate(client, firstLock);
  await repo.getByIdForUpdate(client, secondLock);
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum men-deploy kode backend ke lingkungan produksi:

- [ ] **Deterministic Lock Ordering:** Seluruh penguncian resource ganda diurutkan berdasarkan identifier unik (menghindari mutual deadlock).
- [ ] **Explicit Resource Cleanup:** Semua *stream*, *file handle*, dan *database client lease* dibungkus dalam blok `finally` atau mekanisme auto-disposable.
- [ ] **Structured Telemetry Invariant:** Semua respons JSON non-2xx mengandung `traceId` yang sama persis dengan yang tercatat di log server.
- [ ] **Liveness & Readiness Probes:**
  * Endpoint `/healthz/live`: Mengembalikan 200 jika event loop tidak macet.
  * Endpoint `/healthz/ready`: Mengembalikan 200 hanya jika pool database dapat melakukan `SELECT 1` dan dependency kritikal terhubung.
- [ ] **Signal Handling:** Menangani minimal sinyal `SIGTERM` (sinyal shutdown default Kubernetes) dan `SIGINT` (Ctrl+C).
- [ ] **Bounded Queueing & Timeout Enforcement:** Setiap panggilan dependensi eksternal (DB, Redis, Third-party HTTP) wajib memiliki parameter timeout eksplisit.

---

### 12. Hands-on Practice

Buat skenario pembuktian kebocoran koneksi (*Connection Starvation*) dan implementasikan perbaikannya.

#### Langkah 1: Inisialisasi Environment
Buat direktori baru dan inisialisasi:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install pg dotenv
npm install --save-dev typescript @types/node @types/pg tsx
npx tsc --init
```

#### Langkah 2: Setup Database Lokal
Jalankan PostgreSQL via Docker:
```bash
docker run -d --name enterprise-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=enterprise_db \
  -p 5432:5432 \
  postgres:15-alpine
```

Jalankan skrip migrasi sederhana:
```sql
-- Dijalankan pada database enterprise_db
CREATE TABLE accounts (
  id VARCHAR(64) PRIMARY KEY,
  balance NUMERIC(12, 2) NOT NULL,
  version INT DEFAULT 1,
  updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO accounts (id, balance) VALUES ('ACC-001', 5000.00), ('ACC-002', 1000.00);
```

#### Langkah 3: Reproduksi Masalah Pool Starvation
Buat file `reproduce_starvation.ts`:
```typescript
import { Pool } from 'pg';

const pool = new Pool({
  host: 'localhost',
  user: 'postgres',
  password: 'postgres',
  database: 'enterprise_db',
  max: 2, // Batasi pool hanya 2 koneksi
  connectionTimeoutMillis: 2000
});

async function leakyOperation(id: number) {
  console.log(`[Task ${id}] Mencoba meminjam koneksi...`);
  const client = await pool.connect();
  console.log(`[Task ${id}] Koneksi didapat.`);
  
  // SIMULASI KEBOCORAN:
  // Melempar error sebelum client.release() dipanggil
  if (id === 1 || id === 2) {
    throw new Error(`[Task ${id}] Kegagalan sistem fatal tanpa blok finally!`);
  }
  
  client.release();
}

async function run() {
  try { await leakyOperation(1); } catch (e: any) { console.error(e.message); }
  try { await leakyOperation(2); } catch (e: any) { console.error(e.message); }

  console.log('\n[Task 3] Mencoba meminjam koneksi saat pool habis...');
  try {
    // Task 3 akan mengalami timeout karena 2 koneksi sebelumnya tidak pernah di-release
    await leakyOperation(3);
  } catch (e: any) {
    console.error(`HASIL: Task 3 gagal total: ${e.message}`);
  } finally {
    await pool.end();
  }
}

run();
```
Jalankan dan amati:
```bash
npx tsx reproduce_starvation.ts
```

#### Langkah 4: Terapkan Perbaikan Defensif (Fix)
Ubah implementasi `leakyOperation` dengan idiomatic cleanup:
```typescript
async function safeOperation(pool: Pool, id: number) {
  const client = await pool.connect();
  try {
    console.log(`[SafeTask ${id}] Melakukan eksekusi query...`);
    // Simulasi pekerjaan
    if (id === 1) throw new Error(`[SafeTask ${id}] Error berhasil ditangani.`);
  } finally {
    // JAMINAN MUTLAK: Selalu dilepaskan ke pool
    client.release();
    console.log(`[SafeTask ${id}] Koneksi sukses dikembalikan ke pool.`);
  }
}
```

---

### 13. Exercise

#### Level: Easy
1. Ubah controller pada modul Practical Example untuk menerima header opsional `X-Request-Timeout`. Jika ada, batalkan query DB jika waktu pemrosesan melebihi batas waktu tersebut menggunakan `AbortController`.
2. Tulis query raw SQL yang mengunci baris data akun hanya jika status akunnya `ACTIVE`.

#### Level: Medium
1. Bangun middleware Node.js murni (*pure HTTP*) yang menangkap event `res.on('finish')` untuk menghitung konsumsi memori runtime saat request tersebut selesai menggunakan `process.memoryUsage()`, lalu cetak hasilnya sebagai JSON structured log.
2. Implementasikan pola *Optimistic Locking* murni pada `AccountRepository`. Ganti statement `SELECT FOR UPDATE` dengan update berbasis conditional query:
   ```sql
   UPDATE accounts 
   SET balance = $1, version = version + 1 
   WHERE id = $2 AND version = $3;
   ```
   Lemparkan galat `ConcurrencyConflictError` jika baris yang terpengaruh (*affected rows*) sama dengan 0.

#### Level: Hard
1. Buat arsitektur *Distributed Transaction Coordinator* mini di layer Service yang menangani pola **Saga Pattern (Choreography/Orchestration)**:
   * Jika pemotongan saldo di database lokal berhasil, namun pemanggilan HTTP mock gateway eksternal mengembalikan error `500 Internal Error`, jalankan transaksi kompensasi (*compensating transaction*) untuk mengembalikan saldo pengguna ke kondisi semula secara konsisten.

---

### 14. Challenge

**Skenario Sistem Ticketing Flash-Sale Bebas Rekayasa:**

Sebuah event olahraga besar menjual 1.000 tiket VIP dengan sistem siapa cepat dia dapat. Terdapat batasan arsitektur sebagai berikut:
* Database PostgreSQL hanya boleh menerima maksimal 10 koneksi langsung dari backend service untuk menghindari server *crash*.
* Backend diproyeksikan menerima 50.000 request checkout masuk dalam kurun waktu 5 detik pertama.
* **Tantangan Arsitektur:**
  Rancang dan implementasikan struktur kode backend lengkap (dalam TypeScript atau Go) yang:
  1. Menghalau *thundering herd* tanpa membebani pool database.
  2. Menjamin **tepat 1.000 tiket** yang terjual—tidak boleh terjadi *overselling* (tiket terjual 1.001) dan tidak boleh terjadi *underselling* (tiket tersisa padahal antrean masih ada).
  3. Mampu menolak request berlebih secara elegan dengan status HTTP `429 Too Many Requests` disertai data estimasi waktu tunggu tanpa membuat proses Node.js kehabisan RAM (*OOM Crash*).
  4. Menyediakan sistem graceful recovery jika di tengah penjualan tiket berlangsung, proses menerima sinyal `SIGTERM`.

*Petunjuk: Anda tidak diizinkan menggunakan library antrean berbasis broker terpisah (seperti RabbitMQ/Kafka). Anda harus menyelesaikannya secara murni memanfaatkan arsitektur in-memory queueing terisolasi, backpressure, dan transaksi DB ACID.*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic Concepts (5 Soal)
1. **Mengapa membuka koneksi database baru di setiap request HTTP dianggap sebagai anti-pattern fatal pada backend skala enterprise?**
   * *Jawaban:* Karena membuka koneksi baru mengharuskan proses TCP 3-way handshake, inisiasi TLS, dan autentikasi kredensial yang memakan latensi tinggi (30-100ms) serta dapat menyebabkan kehabisan OS File Descriptors dan kehabisan port TCP lokal (*ephemeral port starvation*).
2. **Apa fungsi utama dari signal `SIGTERM` dalam konteks orchestrator kontainer seperti Kubernetes?**
   * *Jawaban:* Sebagai sinyal peringatan resmi bahwa pod/kontainer akan dihentikan, memberikan jeda waktu bagi aplikasi untuk menyelesaikan in-flight request, mengembalikan koneksi pool, dan menutup resource sebelum dikirimkan sinyal paksa `SIGKILL`.
3. **Apa perbedaan mendasar antara transport DTO (Data Transfer Object) dan Domain Entity?**
   * *Jawaban:* DTO merepresentasikan kontrak data yang masuk atau keluar melalui antarmuka transport (misal: JSON body), sedangkan Domain Entity merepresentasikan aturan bisnis murni, identitas sistem, dan state internal yang steril dari pengaruh protokol HTTP maupun skema database fisik.
4. **Apa yang dimaksud dengan Connection Pool Exhaustion?**
   * *Jawaban:* Kondisi di mana seluruh slot koneksi yang tersedia di pool sedang digunakan oleh worker thread/task lain, sehingga request baru yang membutuhkan koneksi terpaksa mengantre hingga batas waktu timeout terlampaui.
5. **Mengapa penanganan structured logging wajib menggunakan format JSON pada sistem produksi terdistribusi?**
   * *Jawaban:* Agar metadata (seperti trace ID, user ID, status code, latency) dapat diparse dan diindeks secara otomatis oleh Log Collector tanpa memerlukan parsing regex yang lambat dan rentan galat.

#### B. Intermediate Scenarios (5 Soal)
6. **Pada kondisi apa teknik Optimistic Locking lebih diunggulkan dibandingkan Pessimistic Locking?**
   * *Jawaban:* Ketika rasio pembacaan jauh lebih tinggi daripada penulisan (*read-heavy*) dan tingkat benturan konkurensi antar-transaksi diprediksi rendah, sehingga tidak membebani database dengan lock baris yang mematikan performa throughput.
7. **Bagaimana mekanisme `FOR UPDATE` pada SQL mencegah bug Double Spending?**
   * *Jawaban:* Query mengunci baris data target secara eksklusif di level database engine. Transaksi lain yang mencoba membaca atau mengubah baris yang sama dengan klausa locking akan dipaksa menunggu hingga transaksi pertama melakukan `COMMIT` atau `ROLLBACK`.
8. **Jika server menerima sinyal `SIGTERM`, langkah mana yang harus dieksekusi terlebih dahulu: menutup HTTP server listener atau menutup Database Connection Pool? Berikan alasannya.**
   * *Jawaban:* Menutup HTTP server listener terlebih dahulu agar tidak ada request baru yang diterima, membiarkan in-flight request yang sedang berjalan selesai menggunakan pool database yang ada, baru kemudian connection pool database dapat ditutup dengan aman.
9. **Apa bahaya terbesar membiarkan unhandled rejection pada aplikasi backend berbasis Node.js modern?**
   * *Jawaban:* Aplikasi dapat masuk ke dalam state yang tidak terdefinisi (*corrupted memory/leaked state*), dan pada konfigurasi default modern Node.js, unhandled rejection akan mematikan proses server seketika (*crash*).
10. **Bagaimana `Correlation ID` (atau `Trace ID`) disebarkan lintas sistem dalam arsitektur microservices?**
    * *Jawaban:* Disuntikkan ke dalam HTTP request header standar (seperti `traceparent` atau `X-Correlation-ID`) di gerbang ingress, lalu diteruskan oleh HTTP client internal ke setiap downstream services yang dipanggil.

#### C. Production Problem Scenarios (3 Soal Analisis)
11. **Skenario Kasus 1: Memory Leak Perlahan tapi Pasti**
    * *Kasus:* Sebuah backend service mengalami peningkatan penggunaan RAM 50MB setiap harinya hingga Kubernetes melakukan OOMKilled seminggu sekali. Analisis heap dump menunjukkan terdapat ribuan event listener dan database client references yang tertahan. Apa kemungkinan besar kesalahan kodenya?
    * *Analisis & Solusi:* Terdapat pembentukan event listener atau closure callback di dalam siklus penanganan request yang tidak dibersihkan setelah request selesai (misal: mendaftarkan event listener baru ke singleton emitter secara berulang di dalam handler endpoint), atau client database tidak di-release dari koneksi pool saat terjadi exception cabang kondisional tertentu.
12. **Skenario Kasus 2: Transaksi Menggantung (*Idle in Transaction*)**
    * *Kasus:* Database CPU melonjak hingga 100%, dan query sederhana mengalami blocking. Di tabel `pg_stat_activity` terlihat banyak kueri berstatus `<IDLE> in transaction`. Apa yang terjadi pada kode aplikasi backend?
    * *Analisis & Solusi:* Aplikasi telah membuka transaksi database via `BEGIN`, mengeksekusi sebagian operasi, namun kemudian menjalankan pemanggilan I/O non-database yang lambat (misalnya: memanggil third-party Payment Gateway via HTTP tanpa timeout) sebelum sempat memanggil `COMMIT` atau `ROLLBACK`. Koneksi database tertahan dalam status terkunci. Solusi: Jangan pernah memanggil external network I/O di dalam lingkup transaksi database aktif.
13. **Skenario Kasus 3: Cascading Failure Akibat Database Restart**
    * *Kasus:* Database database di-restart selama 10 detik untuk pemeliharaan minor. Namun, setelah database kembali aktif, aplikasi backend tetap gagal merespons request dan melempar galat koneksi ke ribuan user, menuntut dilakukannya restart backend service secara manual. Mengapa ini terjadi dan bagaimana solusinya?
    * *Analisis & Solusi:* Connection pool pada backend tidak memiliki listener error handling untuk menangani putusnya koneksi idle (*stale sockets*), dan tidak memiliki mekanisme automated health check (*validation query* / keep-alive) untuk meregenerasi koneksi rusak di dalam pool. Solusinya: Konfigurasi parameter `testOnBorrow` atau validasi `evictionRunIntervalMillis`, serta tambahkan global handler `pool.on('error', ...)` agar pool secara proaktif membuang socket yang sudah terminated.

---

### 16. Summary

1. **Separation of Concerns:** Memisahkan lapisan Controller, Service, Repository, dan Domain bukan sekadar persoalan kerapian penulisan kode, melainkan syarat mutlak untuk membangun sistem enterprise yang modular, terisolasi dari kegagalan infrastruktur, dan dapat diuji secara independen.
2. **Resource Management:** Database connection adalah sumber daya fisik yang terbatas dan mahal. Pengelolaan koneksi wajib diserahkan kepada *Connection Pool Manager* dengan batas ambang yang disesuaikan secara matematis terhadap kapabilitas CPU dan disk I/O server.
3. **Concurrency Control:** Di lingkungan skala tinggi, anomali data seperti *double-spending* atau *race conditions* tidak dapat diselesaikan hanya dengan logika memori backend. Wajib menggunakan primitives concurrency engine database seperti *Pessimistic Locking* (`FOR UPDATE`) atau *Optimistic Locking* (`versioning`).
4. **Lifecycle & Resilience:** Arsitektur produksi harus mampu menerima kegagalan secara anggun. Penerapan *Graceful Shutdown* (`SIGTERM`/`SIGINT`), context timeouts, bounded retry, dan structured contextual logging memastikan bahwa sistem dapat dideploy dan diskalakan secara berkelanjutan tanpa mengorbankan integritas data pengguna.