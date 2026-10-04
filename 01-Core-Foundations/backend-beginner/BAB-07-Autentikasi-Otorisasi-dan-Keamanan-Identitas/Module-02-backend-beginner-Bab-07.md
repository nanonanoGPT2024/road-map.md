# BAB 07: Materi Lanjutan
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus hidup proses backend pada level sistem operasi (OS signals, memory footprint, socket descriptors, dan event loop/thread execution).
- **Merancang dan mengimplementasikan** arsitektur backend modular berbasis *Clean/Hexagonal Architecture* dengan batasan domain yang tegas, pemisahan dependensi (*Dependency Inversion*), dan *Unit of Work Pattern*.
- **Mengelola** persistensi data tingkat lanjut mencakup *Database Connection Pooling*, *Transaction Isolation Levels*, penanganan *deadlock*, dan implementasi proteksi *race condition* melalui mekanisme locking (*Pessimistic* vs *Optimistic*).
- **Membangun** sistem penanganan kesalahan (*resilience patterns*) produksi meliputi *Graceful Shutdown*, *Circuit Breaker*, *Exponential Backoff with Jitter*, dan validasi mutlak berbasis skema (*Schema Enforcement*).
- **Mengembangkan** kode backend enterprise menggunakan TypeScript/Node.js yang siap di-*deploy* ke lingkungan containerized orchestration (Kubernetes/ECS) dengan metrik *observability* (Structured Logging, Health Checks, dan Readiness/Liveness Probes).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
1. **Dasar Jaringan & Protokol**: Handshake TCP, TLS termination, spesifikasi HTTP/1.1 vs HTTP/2, DNS resolution, dan mekanisme socket.
2. **Dasar Concurrency & Runtime**: Pemahaman mendalam mengenai Event Loop Node.js (Call Stack, Libuv Thread Pool, Microtask/Macrotask Queues) atau Go Goroutines scheduler.
3. **Database Relasional Dasar**: Query SQL DDL/DML, Foreign Key constraints, Basic Indexing (B-Tree), dan transaksi dasar (`BEGIN`, `COMMIT`, `ROLLBACK`).
4. **Clean Code & OOP/FP Basics**: Prinsip SOLID dasar, Interfaces, Types, High-Order Functions, dan Promises/Async-Await.

---

### 3. Concept & Internal Architecture

Memindahkan aplikasi dari status "berjalan di local machine" ke "lingkungan produksi misi-kritis" memerlukan pemahaman mendalam tentang bagaimana kernel sistem operasi, runtime bahasa, dan database berinteraksi.

```
                              ARSITEKTUR LAYER PRODUKSI
+-----------------------------------------------------------------------+
| INGRESS / REVERSE PROXY (Nginx / Cloudflare / ALB)                    |
| - TLS Termination, Rate Limiting, DDoS Shield, HTTP/2 to HTTP/1.1     |
+-----------------------------------+-----------------------------------+
                                    | (TCP Keep-Alive Connection)
                                    v
+-----------------------------------------------------------------------+
| RUNTIME ENVIRONMENT (Node.js Process / OS Container Boundary)         |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | KERNEL SPACE                                                    |  |
|  | Sockets Listen Queue (SYN Backlog) -> epoll/kqueue -> TCP Buffers|  |
|  +--------------------------------+--------------------------------+  |
|                                   | (File Descriptor Notifications)   |
|  +--------------------------------v--------------------------------+  |
|  | USER SPACE (Libuv / Node.js Engine)                             |  |
|  |                                                                 |  |
|  | [Event Loop] <---> [Libuv Threadpool (FS, Crypto, DNS Lookup)]  |  |
|  |      |                                                          |  |
|  |      v                                                          |  |
|  | [HTTP Parsing & Protocol Buffering]                             |  |
|  |      |                                                          |  |
|  |      v                                                          |  |
|  | [Middleware Pipeline] (Tracing ID, Security Headers, CORS)       |  |
|  |      |                                                          |  |
|  |      v                                                          |  |
|  | [Controller / Ingress Adapter] (Schema Validation via Zod)      |  |
|  |      |                                                          |  |
|  |      v                                                          |  |
|  | [Domain Service Layer] (Pure Business Logic)                    |  |
|  |      |                                                          |  |
|  |      v                                                          |  |
|  | [Unit of Work / Repository Interface]                           |  |
|  +--------------------------------+--------------------------------+  |
+-----------------------------------|-----------------------------------+
                                    |
          +-------------------------+-------------------------+
          | (SQL Client / TCP Pool)                           | (HTTP/gRPC Client)
          v                                                   v
+----------------------------------+        +----------------------------------+
| DATABASE CLUSTER (PostgreSQL)    |        | DOWNSTREAM MICROSERVICES         |
| - Connection Pool (Max/Min Idle) |        | - Circuit Breaker Protected      |
| - Wal Engine (Write-Ahead Log)   |        | - Retries with Jitter            |
| - Shared Buffer Cache            |        | - Timeout Budgets                |
| - MVCC Isolation & Locks         |        +----------------------------------+
+----------------------------------+
```

#### A. Kernel Socket Backlog & Event-Loop Saturation
Ketika sebuah request masuk:
1. Kernel Linux menerima segmen TCP SYN, menempatkannya pada *SYN Backlog*.
2. Setelah three-way handshake selesai, koneksi dipindahkan ke *Listen Backlog* (Accept Queue).
3. Runtime Node.js memanggil *system call* `accept4()` via `epoll` untuk mendapatkan socket File Descriptor (FD).
4. Jika event-loop terblokir oleh komputasi sinkronus (misalnya: parsing payload JSON raksasa atau enkripsi CPU-intensive), *Accept Queue* akan penuh. Ketika batas `somaxconn` tercapai, kernel mulai mengabaikan SYN baru, menghasilkan error `ECONNREFUSED` atau *request timeout* di sisi klien tanpa ada log yang tercatat di backend.

#### B. Database Connection Pool Starvation & Saturation
Database relasional seperti PostgreSQL menggunakan model proses *process-per-connection* (atau *thread-per-connection* di MySQL). Membuka koneksi TCP baru membutuhkan:
- Three-way handshake TCP + TLS Negotiation (100–300 ms).
- Backend process forking di sisi PostgreSQL (mengonsumsi 5–10 MB memori per proses).
- Otentikasi dan alokasi *catalog cache*.

Oleh karena itu, aplikasi produksi menggunakan **Connection Pooling**. Parameter kritis:
- **`max` (Maximum connections)**: Jumlah pool soket maksimum yang dibuka ke DB.
- **`idleTimeoutMillis`**: Waktu soket dibiarkan menganggur sebelum dihancurkan.
- **`connectionTimeoutMillis`**: Durasi maksimum aplikasi menunggu giliran mendapatkan koneksi dari pool sebelum melempar error.

Jika *Service Layer* menahan koneksi pool saat memanggil API pihak ketiga (eksternal I/O) yang lambat, seluruh pool akan mengalami *starvation* (kelaparan koneksi). Seluruh request lain akan terhenti di antrean pool hingga mengalami timeout sistemik.

#### C. Isolasi Transaksi & State Machine
Pada arsitektur enterprise, modifikasi multi-tabel harus tunduk pada kaidah ACID (*Atomicity, Consistency, Isolation, Durability*). Pemilihan tingkat isolasi transaksi (*Transaction Isolation Levels*) menentukan proteksi terhadap anomali data:
1. **Read Committed** (Default PG): Menghindari *Dirty Reads*. Namun rentan terhadap *Non-Repeatable Reads* dan *Phantom Reads*.
2. **Repeatable Read**: Menjamin bahwa snapshot query yang dibaca pada awal transaksi tetap konsisten. Menggunakan *Multi-Version Concurrency Control (MVCC)*. Mencegah *Lost Updates* secara otomatis dengan melempar error serialisasi jika dua transaksi mengubah baris yang sama.
3. **Serializable**: Isolasi total. Transaksi dieksekusi seolah-olah berjalan strictly serial. Menimbulkan biaya performa tinggi akibat tingginya tingkat *serialization failure retry*.

---

### 4. Why & What

| Dimensi | Kode Pemula / Skala Hobi | Arsitektur Produksi Skala Enterprise |
| :--- | :--- | :--- |
| **Error Handling** | Menggunakan `try/catch` sporadis, melempar pesan string mentah, membiarkan *uncaught exceptions* mematikan proses, atau mengembalikan `500 Internal Server Error` tanpa konteks. | Penanganan error hierarkis berbasis *Result Object Pattern* atau *Domain Errors*. Logging terstruktur dengan metadata unik (*Trace/Span ID*), sanitasi data sensitif, dan pemetaan status HTTP otomatis yang deterministik. |
| **Lifecycle** | Menghentikan proses secara brutal via `SIGKILL` atau `Ctrl+C`. Request yang sedang berjalan langsung terputus di tengah penulisan database. | Mengimplementasikan **Graceful Shutdown**: menangkap sinyal `SIGINT`/`SIGTERM`, menolak request masuk baru (Healthcheck berubah jadi *Not Ready*), menyelesaikan inflight requests, membersihkan resource I/O (menutup pool DB, flush buffer log), baru keluar dengan exit code `0`. |
| **Koneksi Database** | Membuat koneksi baru per HTTP request atau memakai satu koneksi global tanpa mekanisme pemulihan saat koneksi terputus. | Mengelola *Connection Pool* dengan monitoring metrik (*active, idle, waiting queries*), timeouts yang disesuaikan secara presisi, serta penanganan koneksi zombie via *TCP Keepalive* dan *Health Pings*. |
| **Validasi Data** | Validasi manual menggunakan `if (!req.body.x)` di dalam Controller. Mutasi data mentah tidak terkontrol. | Validasi ketat menggunakan skema deterministik (*fail-fast runtime typing*) di perbatasan sistem (*system boundaries*) menggunakan pustaka seperti Zod/TypeBox. *Parsing*, bukan sekadar *validating*. |
| **Konsistensi Mutasi** | Eksekusi serangkaian query modifikasi data tanpa dibungkus *Transaction Boundary*. Jika langkah ketiga gagal, langkah pertama dan kedua tetap tersimpan (inkonsistensi data korup). | Menggunakan *Unit of Work Pattern* atau *Transactional Context*. Seluruh mutasi terkait diperlakukan sebagai satu kesatuan atomik: *all-or-nothing* dengan penanganan rollback deterministik. |

---

### 5. How (Workflow Detail)

Berikut adalah alur eksekusi request pada level produksi:

```
[Client]
   │ HTTP POST /api/v1/orders (Payload + Idempotency-Key + Bearer Token)
   ▼
[Reverse Proxy / Ingress Controller]
   │ Set X-Request-ID, Forward TCP socket
   ▼
[Application Entrypoint: Node.js Runtime]
   │
   ├─► 1. Middleware: Request Tracing & Correlation ID Injection
   │
   ├─► 2. Middleware: Global Timeout Interceptor (AbortController, misal: 5000ms)
   │
   ├─► 3. Middleware: Security Context & JWT Verification
   │
   ├─► 4. Controller: Schema Validation (Zod) -> Transform to Type-Safe Command DTO
   │
   ├─► 5. Service Layer: Orchestration
   │      │
   │      ├─► Membuka Database Transaction via Unit of Work (acquire client from pool)
   │      │
   │      ├─► Repository: Cek Idempotency Key (Locking row jika sedang diproses)
   │      │
   │      ├─► Domain Engine: Eksekusi Invariant & Aturan Bisnis (Cek Stok & Saldo)
   │      │
   │      ├─► Repository: Simpan State Baru (Order CREATED, Potong Stok)
   │      │
   │      ├─► External Gateway (Payment): Proteksi Circuit Breaker & Timeout Khusus
   │      │
   │      ├─► Outbox Pattern: Tulis event ke tabel `outbox_events` (Atomik dengan order)
   │      │
   │      └─► Commit Transaction (Release DB Client kembali ke pool)
   │
   ├─► 6. Controller: Serialisasi Response DTO (Sanitasi atribut internal/rahasia)
   │
   ▼
[Client Menerima HTTP 201 Created]
```

#### Mekanisme Penanganan Kegagalan (Failure Paths):
1. **Validation Error**: Langsung ditolak di Layer 4 (Status `400 Bad Request` / `422 Unprocessable Entity`), tidak pernah menyentuh Database Pool.
2. **Deadlock Terdeteksi**: Database melempar error code PostgreSQL `40P01` (*deadlock_detected*). Lapisan Service menangkap error ini dan mengeksekusi *Retry Policy* hingga 3 kali dengan *Exponential Jitter* sebelum menyerah ke klien.
3. **Application Crash / OOM**: Proses menangkap `unhandledRejection`, mencatat pesan error fatal ke *stderr* dalam format JSON terstruktur, lalu memicu proses *Graceful Shutdown* secara mandiri agar Orchestrator (seperti Kubernetes) dapat me-restart pod secara bersih.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Restoran Bintang Lima vs Warung Kaki Lima Darurat
- **Aplikasi Tanpa Arsitektur (Warung Kaki Lima Darurat)**:
  Satu pelayan (Event Loop) merangkap kasir, juru masak, dan pencuci piring. Ketika ada pelanggan memesan daging khusus yang harus diambil dari pasar seberang (External API), pelayan diam menunggu di seberang jalan. Semua pelanggan di restoran terlantar. Ketika gempa bumi terjadi (Sinyal SIGTERM), pelayan langsung lari kabur, meninggalkan wajan menyala yang membakar dapur (Data korup).
- **Arsitektur Produksi Enterprise (Restoran Bintang Lima)**:
  Pelayan (Event Loop) hanya menerima order dan mendelegasikannya ke tim spesialis. Ada sejumlah panci/kompor terbatas yang sudah siap pakai (Connection Pool). Jika seorang juru masak membutuhkan bahan baku dari vendor luar, proses pesanan tersebut diberi batas waktu tegas (Timeout). Ketika sirine kebakaran berbunyi (SIGTERM), manajer melarang tamu baru masuk (Readiness Probe `FAIL`), menunggu pesanan di meja yang sedang dimakan diselesaikan dalam 10 detik (Graceful Draining), mematikan seluruh kompor gas secara aman (Pool Release), lalu mengunci pintu restoran secara teratur.

#### Diagram Transisi State Transaksi dan Koneksi Pool

```
 [Pool: 10 Koneksi Bebas]
            │
      acquire()
            │
            ▼
 ┌──────────────────────┐
 │ State: IN_USE        │ ──(Timeout tercapai: > 3s)──► [Kill Query / Force Release]
 └──────────┬───────────┘
            │
      BEGIN TRANSACTION
            │
            ├───► Query 1: Mutasi Data (Success)
            │
            ├───► Query 2: External Dependent Query
            │        │
            │        ├───(Error / Invariant Violation)
            │        │          │
            │        │          ▼
            │        │      ROLLBACK
            │        │          │
            │        │          v
            │        │    [Release to Pool] ──► Lempar DomainException
            │        │
            │        └───(Success)
            │                   │
            v                   v
         COMMIT ◄───────────────┘
            │
            ▼
    [Release to Pool] ──► Return DTO ke Caller
```

---

### 7. Practical Implementation (Production-Grade Code)

Implementasi berikut menggunakan Node.js dengan TypeScript, mengadopsi standar produksi modern: *Separation of Concerns*, *Database Connection Resiliency*, *Unit of Work Transaction*, *Structured Logging*, dan *Deterministic Graceful Shutdown*.

#### Struktur Proyek:
```text
src/
├── config/
│   └── database.ts
├── domain/
│   ├── errors.ts
│   └── order.ts
├── infrastructure/
│   ├── logger.ts
│   └── unit-of-work.ts
├── interfaces/
│   └── http/
│       └── server.ts
└── index.ts
```

#### File: `src/infrastructure/logger.ts`
```typescript
export interface LogContext {
  [key: string]: unknown;
}

export class Logger {
  private format(level: string, message: string, context?: LogContext): string {
    return JSON.stringify({
      timestamp: new Date().toISOString(),
      level,
      message,
      ...context,
    });
  }

  info(message: string, context?: LogContext): void {
    process.stdout.write(this.format('INFO', message, context) + '\n');
  }

  warn(message: string, context?: LogContext): void {
    process.stdout.write(this.format('WARN', message, context) + '\n');
  }

  error(message: string, context?: LogContext): void {
    process.stderr.write(this.format('ERROR', message, context) + '\n');
  }
}

export const logger = new Logger();
```

#### File: `src/domain/errors.ts`
```typescript
export abstract class DomainError extends Error {
  abstract readonly statusCode: number;
  constructor(message: string) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class InsufficientStockError extends DomainError {
  readonly statusCode = 422;
  constructor(sku: string, requested: number, available: number) {
    super(`Stok tidak mencukupi untuk item [${sku}]. Diminta: ${requested}, Tersedia: ${available}`);
  }
}

export class ConcurrentModificationError extends DomainError {
  readonly statusCode = 409;
  constructor(resource: string, id: string) {
    super(`Konflik konkurensi pada ${resource} ID [${id}]. Silakan coba lagi.`);
  }
}

export class ResourceNotFoundError extends DomainError {
  readonly statusCode = 404;
  constructor(resource: string, id: string) {
    super(`Resource ${resource} dengan ID [${id}] tidak ditemukan.`);
  }
}
```

#### File: `src/config/database.ts`
```typescript
import { Pool, PoolConfig } from 'pg';
import { logger } from '../infrastructure/logger';

const poolConfig: PoolConfig = {
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432', 10),
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_NAME || 'enterprise_db',
  max: 20,                          // Batas koneksi maksimal
  idleTimeoutMillis: 30000,         // Menutup idle clients setelah 30 detik
  connectionTimeoutMillis: 2000,    // Melempar error jika koneksi pool tidak tersedia dalam 2 detik
  statement_timeout: 5000,          // Abort query yang berjalan lebih dari 5 detik
};

export const dbPool = new Pool(poolConfig);

dbPool.on('error', (err: Error) => {
  logger.error('Error tidak terduga pada database idle client', { error: err.message, stack: err.stack });
});
```

#### File: `src/infrastructure/unit-of-work.ts`
```typescript
import { Pool, PoolClient } from 'pg';
import { logger } from './logger';

export interface IUnitOfWork {
  getClient(): PoolClient;
  startTransaction(): Promise<void>;
  commit(): Promise<void>;
  rollback(): Promise<void>;
  execute<T>(fn: (uow: IUnitOfWork) => Promise<T>): Promise<T>;
}

export class UnitOfWork implements IUnitOfWork {
  private client: PoolClient | null = null;
  private isTransactionActive = false;

  constructor(private readonly pool: Pool) {}

  async startTransaction(): Promise<void> {
    if (!this.client) {
      this.client = await this.pool.connect();
    }
    // Menggunakan isolasi Read Committed dengan Transaction Guard
    await this.client.query('BEGIN ISOLATION LEVEL READ COMMITTED;');
    this.isTransactionActive = true;
  }

  getClient(): PoolClient {
    if (!this.client) {
      throw new Error('Database client belum diinisialisasi. Panggil startTransaction terlebih dahulu.');
    }
    return this.client;
  }

  async commit(): Promise<void> {
    if (!this.client || !this.isTransactionActive) {
      throw new Error('Tidak ada transaksi aktif yang dapat di-commit.');
    }
    try {
      await this.client.query('COMMIT;');
    } finally {
      this.release();
    }
  }

  async rollback(): Promise<void> {
    if (!this.client || !this.isTransactionActive) {
      return;
    }
    try {
      await this.client.query('ROLLBACK;');
    } catch (err) {
      logger.error('Error saat melakukan transaksi rollback', { error: (err as Error).message });
    } finally {
      this.release();
    }
  }

  private release(): void {
    if (this.client) {
      this.client.release();
      this.client = null;
      this.isTransactionActive = false;
    }
  }

  async execute<T>(fn: (uow: IUnitOfWork) => Promise<T>): Promise<T> {
    await this.startTransaction();
    try {
      const result = await fn(this);
      await this.commit();
      return result;
    } catch (error) {
      await this.rollback();
      throw error;
    }
  }
}
```

#### File: `src/domain/order.ts`
```typescript
import { IUnitOfWork } from '../infrastructure/unit-of-work';
import { InsufficientStockError } from './errors';

export interface OrderItem {
  sku: string;
  quantity: number;
  unitPrice: number;
}

export interface CreateOrderCommand {
  orderId: string;
  customerId: string;
  items: OrderItem[];
}

export class OrderService {
  constructor(private readonly uow: IUnitOfWork) {}

  async createOrder(command: CreateOrderCommand): Promise<{ orderId: string; totalAmount: number }> {
    return this.uow.execute(async (activeUow) => {
      const client = activeUow.getClient();
      let totalAmount = 0;

      for (const item of command.items) {
        // 1. Pessimistic Locking untuk mencegah race condition (FOR UPDATE)
        const checkStockQuery = `
          SELECT sku, stock, price 
          FROM inventories 
          WHERE sku = $1 
          FOR UPDATE;
        `;
        const inventoryResult = await client.query(checkStockQuery, [item.sku]);

        if (inventoryResult.rows.length === 0) {
          throw new InsufficientStockError(item.sku, item.quantity, 0);
        }

        const currentStock = inventoryResult.rows[0].stock;
        if (currentStock < item.quantity) {
          throw new InsufficientStockError(item.sku, item.quantity, currentStock);
        }

        // 2. Deduct inventory
        const deductStockQuery = `
          UPDATE inventories 
          SET stock = stock - $1, updated_at = NOW() 
          WHERE sku = $2;
        `;
        await client.query(deductStockQuery, [item.quantity, item.sku]);

        totalAmount += item.quantity * item.unitPrice;
      }

      // 3. Simpan entitas Order
      const insertOrderQuery = `
        INSERT INTO orders (id, customer_id, total_amount, status, created_at) 
        VALUES ($1, $2, $3, 'CONFIRMED', NOW());
      `;
      await client.query(insertOrderQuery, [command.orderId, command.customerId, totalAmount]);

      // 4. Implementasi Transactional Outbox Pattern
      const outboxPayload = JSON.stringify({
        orderId: command.orderId,
        customerId: command.customerId,
        totalAmount,
        event: 'ORDER_CREATED',
      });
      const insertOutboxQuery = `
        INSERT INTO outbox_events (id, aggregate_type, payload, status, created_at)
        VALUES (gen_random_uuid(), 'ORDER', $1, 'PENDING', NOW());
      `;
      await client.query(insertOutboxQuery, [outboxPayload]);

      return {
        orderId: command.orderId,
        totalAmount,
      };
    });
  }
}
```

#### File: `src/interfaces/http/server.ts` (Graceful Shutdown Engine)
```typescript
import http from 'http';
import { dbPool } from '../../config/database';
import { logger } from '../../infrastructure/logger';
import { UnitOfWork } from '../../infrastructure/unit-of-work';
import { OrderService } from '../../domain/order';
import { DomainError } from '../../domain/errors';

export class ApplicationServer {
  private server: http.Server;
  private isShuttingDown = false;
  private connections = new Set<import('net').Socket>();

  constructor() {
    this.server = http.createServer(this.handleRequest.bind(this));
    this.trackConnections();
  }

  private trackConnections(): void {
    this.server.on('connection', (socket) => {
      this.connections.add(socket);
      socket.on('close', () => {
        this.connections.delete(socket);
      });
    });
  }

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const correlationId = (req.headers['x-correlation-id'] as string) || `req-${Date.now()}-${Math.random().toString(36).substring(7)}`;
    res.setHeader('X-Correlation-ID', correlationId);

    // Health Checks
    if (req.url === '/healthz/liveness' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'UP' }));
      return;
    }

    if (req.url === '/healthz/readiness' && req.method === 'GET') {
      if (this.isShuttingDown) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'DRAINING' }));
        return;
      }
      try {
        await dbPool.query('SELECT 1;');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'READY' }));
      } catch (err) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'DATABASE_DOWN' }));
      }
      return;
    }

    if (this.isShuttingDown) {
      res.writeHead(503, { 'Connection': 'close', 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Server sedang dalam proses shutdown. Silakan coba ke instance lain.' }));
      return;
    }

    // Endpoint Order Execution
    if (req.url === '/api/v1/orders' && req.method === 'POST') {
      let body = '';
      req.on('data', (chunk) => { body += chunk; });
      req.on('end', async () => {
        try {
          const payload = JSON.parse(body);
          
          // Dependency Injection
          const uow = new UnitOfWork(dbPool);
          const orderService = new OrderService(uow);

          const result = await orderService.createOrder({
            orderId: payload.orderId || `ord-${Date.now()}`,
            customerId: payload.customerId,
            items: payload.items || [],
          });

          res.writeHead(201, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: true, data: result }));
        } catch (error) {
          if (error instanceof DomainError) {
            res.writeHead(error.statusCode, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message }));
          } else {
            logger.error('Unhandled Internal Server Error', {
              correlationId,
              error: (error as Error).message,
              stack: (error as Error).stack,
            });
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: 'Internal Server Error' }));
          }
        }
      });
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not Found' }));
  }

  public listen(port: number, callback?: () => void): void {
    this.server.listen(port, callback);
  }

  public async shutdown(signal: string): Promise<void> {
    logger.info(`Sinyal ${signal} diterima. Memulai prosedur Graceful Shutdown...`);
    this.isShuttingDown = true;

    // 1. Berhenti menerima request baru pada level listener
    this.server.close(async (err) => {
      if (err) {
        logger.error('Error saat menutup HTTP server listener', { error: err.message });
        process.exit(1);
      }
      logger.info('HTTP server listener berhasil ditutup. Tidak menerima request baru.');

      try {
        // 2. Tutup Database Pool
        logger.info('Menutup seluruh koneksi Database Pool...');
        await dbPool.end();
        logger.info('Database Pool berhasil dibersihkan dan ditutup.');

        logger.info('Proses Graceful Shutdown selesai sempurna.');
        process.exit(0);
      } catch (poolErr) {
        logger.error('Error saat menutup Database Pool', { error: (poolErr as Error).message });
        process.exit(1);
      }
    });

    // 3. Force Close sockets yang idle / keep-alive
    for (const socket of this.connections) {
      // Menutup socket yang tidak sedang memproses query aktif
      socket.end();
    }

    // 4. Fallback Timeout: Paksa bunuh proses jika inflight request macet melebihi 10 detik
    setTimeout(() => {
      logger.error('Graceful shutdown melebihi ambang batas (10 detik). Memaksa exit secara darurat.');
      process.exit(1);
    }, 10000).unref();
  }
}
```

#### File: `src/index.ts`
```typescript
import { ApplicationServer } from './interfaces/http/server';
import { logger } from './infrastructure/logger';

const PORT = parseInt(process.env.PORT || '3000', 10);
const app = new ApplicationServer();

app.listen(PORT, () => {
  logger.info(`Enterprise Application Server aktif berjalan pada port ${PORT}`);
});

// Registrasi Tangkapan Sinyal Sistem Operasi
const terminateSignals: NodeJS.Signals[] = ['SIGTERM', 'SIGINT'];

for (const signal of terminateSignals) {
  process.on(signal, () => {
    app.shutdown(signal).catch((err) => {
      logger.error(`Kegagalan fatal saat graceful shutdown pada sinyal ${signal}`, { error: err.message });
      process.exit(1);
    });
  });
}

process.on('uncaughtException', (err: Error) => {
  logger.error('FATAL: Uncaught Exception terdeteksi!', { error: err.message, stack: err.stack });
  app.shutdown('UNCAUGHT_EXCEPTION').finally(() => process.exit(1));
});

process.on('unhandledRejection', (reason: unknown) => {
  logger.error('FATAL: Unhandled Promise Rejection terdeteksi!', { reason: String(reason) });
  app.shutdown('UNHANDLED_REJECTION').finally(() => process.exit(1));
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Flash Sale Double-Spending & Database Freezing pada E-Commerce Nasional
- **Konteks**: Sistem backend menerima lonjakan traffic dari rata-rata 800 RPS melonjak menjadi 45.000 RPS dalam 3 detik saat jam flash-sale produk edisi terbatas (stok hanya 100 unit).
- **Insiden**:
  1. Penggunaan query tanpa proteksi locking: `SELECT stock FROM products WHERE id = 1`. Di runtime, 500 thread paralel membaca nilai stok yang sama (`stock = 100`).
  2. Masing-masing thread mengeksekusi `UPDATE products SET stock = stock - 1 WHERE id = 1`.
  3. Terjadi *Overselling*: 1.450 order terkonfirmasi berhasil dibuat padahal stok aktual hanya 100.
  4. Node.js backend membuka koneksi baru tanpa batasan pool per container. Sebanyak 80 instance pod membuka masing-masing 100 koneksi ke PostgreSQL primer ($80 \times 100 = 8.000$ koneksi).
  5. PostgreSQL crash akibat *Kernel Out of Memory (OOM Killer)* karena alokasi memori buffer proses koneksi melebihi batas RAM server basis data (64 GB).
  6. Ketika pod di-restart oleh Kubernetes, pod lama dibunuh secara paksa (`SIGKILL`), memutus transaksi data secara tidak teratur dan mengunci baris (*orphaned transaction locks*).

#### Solusi Arsitektural yang Diterapkan:
1. **Pessimistic Locking & Atomic Decrement**:
   Mengubah validasi stok menjadi mutasi atomik langsung di database engine:
   ```sql
   UPDATE inventories 
   SET stock = stock - $quantity 
   WHERE sku = $sku AND stock >= $quantity 
   RETURNING stock;
   ```
   Jika row count yang dikembalikan adalah 0, aplikasi langsung melempar `InsufficientStockError` tanpa menahan transaksi lebih lanjut.
2. **Pool Sizing & PgBouncer Proxy**:
   Membatasi connection pool aplikasi Node.js menjadi maksimal 10 per instance. Menginstalasi lapisan *PgBouncer* di depan PostgreSQL cluster menggunakan mode *Transaction Pooling*, menyusutkan kebutuhan koneksi server dari 8.000 ke 150 koneksi aktif permanen.
3. **Penerapan Graceful Draining**:
   Mengonfigurasi lifecycle hook Kubernetes `preStop` dengan sleep 5 detik untuk memberi jeda DNS propagation, diikuti penanganan sinyal `SIGTERM` terstruktur seperti kode pada Bagian 7.

---

### 9. Trade-offs

Setiap keputusan rekayasa dalam arsitektur produksi memiliki konsekuensi yang saling bertentangan:

| Pendekatan / Teknik | Keuntungan | Kerugian & Konsekuensi Biaya | Latency & Scalability Impact |
| :--- | :--- | :--- | :--- |
| **Pessimistic Locking (`SELECT FOR UPDATE`)** | Menjamin integritas absolut dan konsistensi kuat (*Strong Consistency*). Mencegah *race condition* dan anomali overselling secara mutlak. | Mengakibatkan antrean lock (*lock contention*). Transaksi lain yang mengakses baris yang sama harus antre, meningkatkan risiko *database deadlock*. | Latensi meningkat drastis pada titik data panas (*hot-spot items*). *Throughput* skalar terbatas pada kapasitas single-row lock DB. |
| **Optimistic Concurrency Control (OCC via Versioning)** | Tidak ada antrean kunci fisik pada DB engine. *Throughput* pembacaan dan penulisan sangat tinggi pada konkurensi rendah-menengah. | Membutuhkan mekanisme *retry* pada level aplikasi ketika terjadi modifikasi konkuren (*version mismatch*). Biaya komputasi CPU aplikasi meningkat. | Sangat optimal untuk skenario *Read-Heavy*. Latensi memburuk secara signifikan jika tingkat persaingan data (*contention rate*) sangat tinggi (>30%). |
| **Ukuran Connection Pool Sangat Besar (e.g. Max 100 per pod)** | Mengurangi antrean request pada antrean internal pool aplikasi saat terjadi *burst traffic*. | Pemborosan memori DB server yang masif. Mengakibatkan *Context Switching Thrashing* pada CPU database, yang justru menurunkan kapasitas total database. | Peningkatan latensi query secara keseluruhan (*degraded throughput*) akibat kehabisan *CPU Cache* di level server database. |
| **Ukuran Connection Pool Terbatas/Kecil (e.g. Max 10-15 per pod)** | Menjaga stabilitas performa database server dalam batas *sweet-spot* throughput CPU core. Utilisasi memori DB terprediksi. | Memerlukan antrean di sisi aplikasi. Jika query lambat terjadi, pool cepat habis dan request baru langsung terkena *Connection Timeout*. | Latensi di aplikasi dapat melonjak jika arsitek tidak mengontrol eksekusi query lambat (*Slow Query Saturation*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Pool Starvation" Akibat I/O Liar di Dalam Blok Transaksi
- **Penyebab**: Memanggil API pihak ketiga (misalnya: gateway pembayaran Stripe, verifikasi KYC, atau pengiriman email) di dalam blok transaksi database.
  ```typescript
  // ANTI-PATTERN FATAL
  await uow.execute(async (client) => {
    await client.query("UPDATE accounts SET balance = balance - 100 WHERE id = $1", [id]);
    await axios.post("https://payment-gateway.com/charge"); // <--- JIKA INI HANG 10 DETIK, DB LOCK & KONEKSI TAHAN 10 DETIK!
    await client.query("INSERT INTO transactions ...");
  });
  ```
- **Solusi**: Pisahkan dependensi eksternal dari batas transaksi SQL menggunakan *Two-Phase Orchestration* atau *Transactional Outbox Pattern*. Simpan status `PENDING` di DB dalam hitungan milidetik, lepaskan koneksi database kembali ke pool, lalu hubungi payment gateway di luar blok transaksi.

#### 2. Unhandled Rejection Menggantungkan Socket
- **Penyebab**: Error asinkronus yang tidak ditangkap di dalam event listener atau callback stream mengakibatkan Promise tidak pernah diselesaikan (*unresolved*), sehingga socket HTTP tidak pernah ditutup dan memori bocor secara diam-diam.
- **Deteksi**: Periksa pertumbuhan *Heap Memory* secara bertahap (*sawtooth pattern failure*) dan monitor metrik Node.js `process._getActiveHandles()`.
- **Troubleshooting**: Pasang linter rule `@typescript-eslint/no-floating-promises` dan `@typescript-eslint/no-misused-promises` pada pipeline CI/CD untuk menggagalkan kompilasi jika ada Promise yang tidak ditangani dengan `await` atau `.catch()`.

#### 3. Menggunakan "Zero-Downtime Deployment" Tanpa Graceful Shutdown
- **Penyebab**: Aplikasi dimatikan seketika oleh Kubernetes saat rolling deployment. Client mendapati lonjakan error `502 Bad Gateway` atau koneksi terputus tiba-tiba (*TCP RST*).
- **Troubleshooting**: Periksa diagram transisi pod. Tambahkan waktu henti sementara (*sleep delay*) pada `preStop` hook untuk memberi kesempatan iptables/kube-proxy mencabut IP pod dari Service Endpoints sebelum runtime menerima sinyal `SIGTERM`.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai *gatekeeper* sebelum merilis backend service ke lingkungan produksi:

- [ ] **Deterministic Timeouts**: Setiap panggilan jaringan I/O (Database, Redis, Internal HTTP, Third-party SDK) memiliki konfigurasi batas waktu tegas (*strict timeout*). Tidak ada koneksi yang dibiarkan menunggu tanpa batas waktu.
- [ ] **Standard Graceful Exit**: Menangani sinyal `SIGTERM` dan `SIGINT` dengan mengeksekusi penutupan koneksi secara berurutan: Listener $\to$ Database Pools/Brokers $\to$ Force Exit Fallback Timer.
- [ ] **Structured JSON Logging**: Seluruh output stdout/stderr menggunakan format JSON satu baris (*single-line JSON*) yang dilengkapi field standar: `timestamp`, `level`, `correlation_id`, `service_name`, dan `error_details`.
- [ ] **Liveness & Readiness Separation**:
  - Endpoint `/healthz/liveness` hanya mengecek apakah proses backend hidup (tidak mengecek database).
  - Endpoint `/healthz/readiness` memverifikasi kesiapan seluruh dependensi kritis (Database, Cache) untuk melayani traffic.
- [ ] **Fail-Fast Schema Validation**: Tidak memproses payload JSON mentah langsung ke domain logic tanpa validasi skema runtime (misal: validasi Zod pada Ingress Controller).
- [ ] **Penyisipan Correlation-ID**: Meneruskan atau men-generate `X-Correlation-ID` pada setiap lapisan log untuk memfasilitasi penelusuran terdistribusi (*distributed tracing*).
- [ ] **Resource Limits Configuration**: Container memiliki batas *CPU Request/Limit* dan *Memory Request/Limit* yang disesuaikan dengan konfigurasi pool thread Libuv (`UV_THREADPOOL_SIZE`) dan V8 Max Old Space (`--max-old-space-size`).

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum ini pada direktori terisolasi `hands-on/m02/`.

#### Langkah 1: Persiapan Direktori & File Konfigurasi Docker
Buat struktur direktori praktikum:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node pg @types/pg dotenv
npx tsc --init
```

Buat file `docker-compose.yml` di dalam direktori `hands-on/m02/`:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: enterprise_user
      POSTGRES_PASSWORD: enterprise_password
      POSTGRES_DB: enterprise_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Jalankan container database:
```bash
docker compose up -d
```

#### Langkah 2: Inisialisasi Skema Database Migrasi
Buat file `init.sql` di root direktori praktikum:
```sql
CREATE TABLE IF NOT EXISTS inventories (
    sku VARCHAR(64) PRIMARY KEY,
    stock INT NOT NULL CHECK (stock >= 0),
    price NUMERIC(12, 2) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed data awal
INSERT INTO inventories (sku, stock, price) 
VALUES ('IPHONE-15-PRO', 10, 15000000.00)
ON CONFLICT (sku) DO NOTHING;
```

Eksekusi skema ke PostgreSQL:
```bash
docker compose exec -T postgres psql -U enterprise_user -d enterprise_db < init.sql
```

#### Langkah 3: Konfigurasi Kode
Salin kode dari **Bagian 7 (Practical Implementation)** ke direktori `src/` masing-masing sesuai hierarki file. Sesuaikan environment variable pada file `.env`:
```env
PORT=3000
DB_HOST=localhost
DB_PORT=5432
DB_USER=enterprise_user
DB_PASSWORD=enterprise_password
DB_NAME=enterprise_db
```

Kompilasi TypeScript dan jalankan aplikasi:
```bash
npx tsc
node dist/index.js
```

#### Langkah 4: Uji Coba Transaksi Sukses & Penipisan Stok
Buka terminal baru, lakukan request pembuatan order via `curl`:
```bash
curl -X POST http://localhost:3000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "orderId": "ORD-001",
    "customerId": "CUST-99",
    "items": [
      { "sku": "IPHONE-15-PRO", "quantity": 2, "unitPrice": 15000000.00 }
    ]
  }'
```
*Expected Output:* Status `201 Created` dengan payload JSON konfirmasi.

Verifikasi penurunan stok pada database:
```bash
docker compose exec -T postgres psql -U enterprise_user -d enterprise_db -c "SELECT * FROM inventories WHERE sku = 'IPHONE-15-PRO';"
```
Nilai kolom `stock` harus berubah menjadi `8`.

#### Langkah 5: Uji Coba Graceful Shutdown
Jalankan tes ketahanan saat server sedang aktif:
1. Jalankan request ke endpoint Readiness Probe:
   ```bash
   curl -i http://localhost:3000/healthz/readiness
   ```
   *Expected Output:* HTTP 200 OK (`{"status":"READY"}`).
2. Kirim sinyal `SIGTERM` ke proses Node.js:
   ```bash
   kill -15 $(pgrep -f "node dist/index.js")
   ```
3. Amati log di terminal aplikasi. Output JSON terstruktur akan menampilkan urutan penutupan HTTP server, pelepasan pool database, hingga pemutusan proses yang bersih dengan kode keluar `0`.

---

### 13. Exercise

#### Level Easy
- **Tugas**: Tambahkan middleware *Global Request Duration Profiler* pada server HTTP murni (`server.ts`).
- **Spesifikasi**: Rekam waktu awal request masuk menggunakan `process.hrtime.bigint()`. Ketika event `res.on('finish')` dipicu, hitung durasi dalam milidetik dan cetak log terstruktur level `INFO` yang memuat field `method`, `url`, `statusCode`, dan `duration_ms`.
- **Kriteria Verifikasi**: Tidak boleh memodifikasi payload data; durasi harus tercatat akurat dengan presisi sub-milidetik.

#### Level Medium
- **Tugas**: Implementasikan proteksi idempotensi (*Idempotency Key Enforcement*) pada `OrderService`.
- **Spesifikasi**:
  1. Buat tabel `idempotency_keys` (`key VARCHAR PRIMARY KEY`, `response_payload JSONB`, `created_at TIMESTAMP`).
  2. Modifikasi alur `createOrder`: Cek apakah key sudah pernah digunakan di dalam unit of work yang sama.
  3. Jika key sudah ada, batalkan mutasi stok dan kembalikan langsung snapshot payload yang tersimpan sebelumnya tanpa melempar error.
- **Kriteria Verifikasi**: Mengirim request kedua dengan `orderId` yang sama persis tidak boleh mengurangi stok di tabel `inventories` dua kali.

#### Level Hard
- **Tugas**: Rancang mekanisme *Automatic Transaction Retry with Exponential Jitter* khusus untuk menangani error PostgreSQL Concurrency Conflict (`code: 40001` - *serialization_failure* atau `code: 40P01` - *deadlock_detected*).
- **Spesifikasi**:
  1. Modifikasi method `UnitOfWork.execute()` untuk menerima parameter konfigurasi retry: `{ maxRetries: 3, baseDelayMs: 50 }`.
  2. Gunakan rumus *Full Jitter Backoff*: $\text{delay} = \text{random}(0, \min(\text{maxDelay}, \text{baseDelay} \times 2^{\text{attempt}}))$.
  3. Pastikan koneksi yang mengalami error di-rollback secara bersih dan dilepaskan kembali ke pool sebelum proses *retry* mencoba mengambil koneksi baru.
- **Kriteria Verifikasi**: Simulasikan dua transaksi paralel yang saling bertabrakan (*deadlock simulation script*). Aplikasi harus secara transparan menyelesaikan transaksi yang sempat gagal tanpa melemparkan error 500 ke pengguna.

---

### 14. Challenge

Rancang arsitektur dan bangun implementasi backend untuk **Sistem Ledger Finansial Multi-Akun** yang tahan terhadap kegagalan infrastruktur ekstrem dengan spesifikasi:

1. **Kasus Mutasi Finansial Ganda (Double-Entry Bookkeeping)**:
   Setiap transfer dana antar akun harus terdiri dari minimal 2 baris mutasi di tabel `journal_entries`: satu sisi Debet dan satu sisi Kredit. Total nominal Debet harus presisi sama dengan Kredit sampai digit sen terakhir (`NUMERIC(18, 4)`).
2. **High Contention Account**:
   Akun sistem (misalnya: *Escrow Account Perusahaan*) menerima ribuan transaksi kredit/debet per detik dari ribuan user yang berbeda secara bersamaan. Penggunaan satu baris locking primitif `SELECT FOR UPDATE` pada akun escrow akan menyebabkan *system-wide bottleneck*. Terapkan teknik **Distributed Split Ledger Accumulator** atau **Hot-Spot Sharding** untuk mengatasi masalah penumpukan antrean kunci baris.
3. **Simulasi Kegagalan Listrik / Kernel Crash**:
   Lakukan pengujian *Chaos Engineering sederhana*: Jalankan script stress testing paralel sebanyak 100 concurrent workers yang mentransfer saldo secara acak antar 50 akun. Tembakkan perintah `kill -9` pada database PostgreSQL atau aplikasi Node.js di tengah proses mutasi.
4. **Kriteria Keberhasilan Absolute**:
   Setelah sistem dinyalakan kembali (*recovery*), buat sebuah skrip audit rekonsiliasi independen. Skrip harus membuktikan secara matematis:
   - Tidak ada satu pun transaksi yang statusnya menggantung (*orphaned split legs*).
   - Jumlah total seluruh saldo akun di sistem sebelum crash sama dengan jumlah total saldo akun setelah crash.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Konseptual Dasar (Basic)
1. Apa perbedaan mendasar antara sinyal sistem operasi `SIGINT`, `SIGTERM`, dan `SIGKILL` terkait kemampuan aplikasi backend dalam mengeksekusi *cleanup hooks*?
2. Mengapa membuka koneksi TCP baru secara langsung pada setiap incoming HTTP request (tanpa pool) sangat membebani server database relasional?
3. Pada level arsitektur jaringan, apa perbedaan fungsi antara HTTP endpoint `/healthz/liveness` dan `/healthz/readiness` saat digunakan oleh container orchestrator?
4. Apa yang dimaksud dengan anomali *Non-Repeatable Read* pada transaksi SQL dan pada level isolasi apa anomali ini mulai dieliminasi?
5. Mengapa penanganan error menggunakan `process.on('uncaughtException')` harus selalu diakhiri dengan mematikan proses (`process.exit(1)`)?

#### Bagian B: Pertanyaan Analisis & Mekanisme (Intermediate)
6. Jelaskan skenario bagaimana sebuah query `SELECT ... FOR UPDATE` dapat memicu kondisi *Deadlock* antara dua transaksi yang berjalan paralel!
7. Apa dampak dari konfigurasi ukuran database connection pool yang diset terlalu besar (misalnya: 500 koneksi per instance pod) terhadap kinerja PostgreSQL CPU core?
8. Mengapa operasi manipulasi kriptografi intensif (seperti `bcrypt.hash` dengan cost salt tinggi) dapat menyebabkan *socket backlog queue* kernel Linux menjadi penuh pada aplikasi Node.js?
9. Jelaskan konsep *Transactional Outbox Pattern* dan masalah inkonsistensi apa yang diselesaikannya saat mengintegrasikan Database Relasional dengan Message Broker (misal: Kafka/RabbitMQ)!
10. Bagaimana algoritma *Exponential Backoff with Jitter* membantu mencegah fenomena *Thundering Herd Problem* pada sistem backend terdistribusi yang sedang pulih dari gangguan?

#### Bagian C: Skenario Kasus Produksi (Advanced)
11. **Skenario 1**:
    Tim SRE melaporkan bahwa aplikasi backend Node.js sering tiba-tiba di-restart oleh Kubernetes dengan status error `OOMKilled` (Exit Code 137). Log stdout tidak mencatat stack trace error sama sekali. Analisis parameter konfigurasi runtime dan OS apa saja yang harus Anda investigasi untuk melacak akar masalah kebocoran memori ini?
12. **Skenario 2**:
    Sebuah transaksi mutasi saldo akun yang lambat (membutuhkan waktu 4 detik karena kalkulasi kompleks) sering mengalami kegagalan dengan error PostgreSQL: `statement timeout exceeded`. Namun ketika dijalankan secara terisolasi pada database staging dengan data yang sama, query hanya membutuhkan waktu 8 milidetik. Identifikasi penyebab laten fenomena ini di lingkungan produksi!
13. **Skenario 3**:
    Saat melakukan rolling update versi baru di Kubernetes, log pada API Gateway mencatat kemunculan sekumpulan error `502 Bad Gateway` selama rentang waktu 3–5 detik pertama saat proses deployment dimulai, meskipun Anda telah menerapkan *Graceful Shutdown* pada container backend. Di lapisan infrastruktur manakah kebocoran request ini terjadi, dan bagaimana konfigurasi mitigasinya?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A (Basic)
1. `SIGINT` (interupsi terminal/Ctrl+C) dan `SIGTERM` (permintaan terminasi standar) dapat ditangkap (*catchable*) oleh proses aplikasi untuk menjalankan kode pembersihan (*cleanup hooks*). `SIGKILL` (sinyal paksa) langsung dieksekusi oleh Kernel OS dan **tidak dapat ditangkap, diblokir, atau diabaikan** oleh proses, sehingga mematikan aplikasi seketika tanpa ada pelepasan resource.
2. Membuka koneksi TCP baru membutuhkan *three-way handshake*, negosiasi enkripsi TLS, alokasi memori process/thread baru di database, dan negosiasi otentikasi. Melakukan ini per-request mengakibatkan latensi tinggi dan kehabisan alokasi memori (*OOM*) pada server database.
3. `/healthz/liveness` digunakan orchestrator untuk mengetahui apakah runtime proses masih merespons; jika gagal, orchestrator akan me-restart container. `/healthz/readiness` mengecek apakah aplikasi siap melayani traffic pengguna (dependensi DB/Cache terhubung); jika gagal, traffic dialihkan menjauhi container tersebut tanpa me-restartnya.
4. *Non-Repeatable Read* terjadi ketika sebuah transaksi membaca baris data yang sama dua kali, tetapi mendapatkan nilai yang berbeda karena transaksi lain telah meng-*commit* pembaruan pada baris tersebut di antara pembacaan pertama dan kedua. Anomali ini dieliminasi pada level isolasi **Repeatable Read** dan **Serializable**.
5. Karena saat `uncaughtException` terpicu, integritas internal state dan alokasi memori V8 runtime sudah berada dalam kondisi yang tidak terprediksi (*corrupted state*). Melanjutkan eksekusi aplikasi dapat menyebabkan data korup, memory leak liar, dan perilaku tak terdefinisi. Aplikasi harus mencatat log error lalu keluar untuk dihidupkan ulang oleh orchestrator.

#### Bagian B (Intermediate)
6. Deadlock terjadi jika Transaksi A mengunci Baris 1 (`FOR UPDATE`) dan mencoba mengunci Baris 2, sementara pada saat yang bersamaan Transaksi B telah mengunci Baris 2 dan mencoba mengunci Baris 1. Keduanya saling menunggu kunci dilepaskan, membentuk siklus tunggu tak berujung (*circular dependency*) hingga engine DB mendeteksi dan mengorbankan salah satu transaksi via error `deadlock_detected`.
7. Pool yang terlalu besar menyebabkan jumlah proses worker PostgreSQL melampaui jumlah core CPU fisik. Akibatnya terjadi lonjakan *CPU Context Switching* yang ekstrem, degradasi *CPU L1/L2/L3 Cache lines*, dan kehabisan ruang *Shared Buffers*, yang justru menyebabkan penurunan drastis *throughput* transaksi total sistem (*thrashing*).
8. Operasi enkripsi sinkronus memblokir single thread Event Loop Node.js. Ketika event loop terblokir, runtime tidak dapat mengeksekusi system call `accept()` untuk mengambil koneksi dari antrean TCP listen socket kernel. Jika antrean *SYN/Listen Backlog* kernel penuh, kernel akan menolak koneksi baru (`ECONNREFUSED`).
9. Mengatasi masalah *Dual-Write Inconsistency* (kegagalan penulisan parsial antara DB dan Message Broker). Outbox Pattern menulis pesan event langsung ke dalam tabel database menggunakan transaksi atomik SQL yang sama dengan data bisnis. Worker independen kemudian membaca tabel tersebut dan meneruskannya ke Message Broker secara asinkronus dengan jaminan *at-least-once delivery*.
10. Jika downstream service pulih setelah mengalami down, puluhan ribu worker/client yang mencoba *retry* di waktu interval yang sama persis (misal: persis tiap 2 detik) akan menghantam downstream service secara sinkron (*Thundering Herd*). *Jitter* menambahkan faktor acak pada interval backoff sehingga sebaran request terdistribusi merata sepanjang waktu.

#### Bagian C (Kasus Produksi)
11. **Akar Masalah**: Alokasi memori proses Node.js melampaui limit container cgroup yang ditetapkan Kubernetes.
    **Investigasi**:
    - Periksa apakah konfigurasi flag V8 `--max-old-space-size` diset lebih tinggi daripada memory limit container Kubernetes.
    - Cek pemanggilan memori di luar V8 Heap: alokasi Node.js `Buffer`, C++ Addons, atau thread Libuv pool yang memakan memori native.
    - Pasang monitoring metrik resident set size (`process.memoryUsage.rss()`) untuk mengisolasi titik memory leak.
12. **Akar Masalah**: Terjadi *Lock Waiting Contention*, bukan query execution time yang lambat.
    **Investigasi**: Query 8 ms menjadi 4000 ms karena transaksi terblokir menunggu baris data yang sedang dikunci oleh transaksi lain yang berjalan lama (*long-running transaction*). Timeout `statement_timeout` terpicu karena durasi penungguan antrean gembok (*lock acquisition time*) dihitung sebagai bagian dari durasi total eksekusi query.
13. **Akar Masalah**: Kegagalan propagasi status IP pod pada layer jaringan (*Iptables / IPVS / Service Endpoints*).
    **Mitigasi**: Saat sinyal pembunuhan pod dikirim, Kubernetes membutuhkan waktu beberapa detik untuk menghapus IP pod dari daftar endpoint routing di semua node. Solusinya: tambahkan konfigurasi `preStop` hook pada pod spec:
    ```yaml
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 5"]
    ```
    Perintah ini menunda pengiriman sinyal `SIGTERM` selama 5 detik, memastikan load balancer dan iptables telah selesai mengalihkan routing traffic baru sebelum container mematikan server HTTP listener-nya.

---

### 16. Summary

Membangun arsitektur backend kelas produksi menuntut pergeseran paradigma dari sekadar "kode yang berjalan" menuju "sistem yang resilien terhadap kegagalan yang tak terelakkan". Fondasi rekayasa backend modern bertumpu pada lima pilar utama:

1. **Boundary Validation & Type Integrity**: Mencegah data kotor masuk ke dalam domain aplikasi dengan validasi skema runtime deterministik di Ingress Controller.
2. **Atomic Consistency Boundaries**: Penggunaan *Unit of Work Pattern* dan pemahaman tingkat isolasi transaksi SQL mencegah anomali data, *race condition*, dan data korup saat terjadi kegagalan parsial.
3. **Resource Lifecycle Governance**: Koneksi database, memory heap, dan socket descriptor sistem operasi adalah sumber daya terbatas. Manajemen *Connection Pooling* yang presisi serta pemisahan I/O liar dari transaksi adalah harga mati.
4. **Deterministic Graceful Teardown**: Layanan enterprise harus siap menerima kematian proses kapan saja tanpa memutus transaksi pengguna yang sedang berjalan, melalui koordinasi sinyal OS (`SIGTERM`), pengurasan koneksi (*draining*), dan pembatasan timeout sistematis.
5. **Observability as a First-Class Citizen**: Logging terstruktur berbasis JSON dan pemetaan *Correlation ID* terdistribusi adalah satu-satunya cara merekonstruksi state sistem saat terjadi insiden pada skala produksi tinggi.