# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Merancang dan Mengimplementasikan Arsitektur Berlapis Bersih (*Layered/Clean Architecture*)**: Memisahkan *Transport Layer*, *Domain/Service Layer*, dan *Data Access Layer* secara independen guna meningkatkan *testability* dan *maintainability*.
*   **Menganalisis dan Mengelola Siklus Hidup *Connection Pool***: Mengkonfigurasi parameter *connection pool* basis data secara presisi guna mencegah *starvation*, *connection leak*, dan *thundering herd problem*.
*   **Menerapkan Pola Resiliensi Komprehensif**: Mengimplementasikan *Graceful Shutdown*, *Defensive Timeout*, *Circuit Breaker*, dan *Exponential Backoff with Jitter*.
*   **Membangun Sistem *Context Propagation* & Observabilitas Produksi**: Menerapkan *Structured JSON Logging* dan pelacakan *Correlation ID* lintas batas *asynchronous execution context*.
*   **Mengantisipasi Degradasi Performa Sistem**: Mengidentifikasi titik kegagalan (*Single Point of Failure*), memitigasi *memory leaks*, dan mengelola pembagian beban I/O secara deterministik.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib memahami:
*   **Prinsip Protokol HTTP & REST API**: *Status codes*, *headers*, *verbs*, serta siklus hidup request-response standar.
*   **Dasar Basis Data Relasional**: Properti ACID, indeks B-Tree, level isolasi transaksi (*Read Committed*, *Repeatable Read*, *Serializable*).
*   **Runtime Asinkronus (Node.js/TypeScript Runtime Engine)**: Mekanisme *Event Loop*, *Call Stack*, *Microtask/Macrotask Queue*, dan penanganan *Promise*.
*   **Dasar Container & Infrastruktur**: Kemampuan membaca file Docker/konfigurasi runtime lingkungan produksi sederhana.

---

## 3. Concept & Internal Architecture

### 3.1 Transisi dari Arsitektur Monolitik Spaghetti ke *Layered Architecture*

Pada tahap pemula, logika aplikasi kerap dipusatkan di dalam satu pengendali rute (*route handler* / *fat controller*). Kode ini menangani parsing HTTP, validasi, otorisasi, logika bisnis, query SQL langsung, hingga penanganan error. Pendekatan ini gagal total di lingkungan produksi karena menciptakan *tight coupling*.

Arsitektur produksi enterprise menerapkan prinsip **Separation of Concerns (SoC)** dan **Inversion of Control (IoC)** melalui pemisahan lapisan:

```
[ Incoming HTTP Request ]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. Transport Layer (Controller / Handler)               │
│    - Validasi Skema Input (Zod / JSON Schema)          │
│    - Ekstraksi Context (Tracing ID, Auth Claims)       │
│    - Transformasi Domain Output -> HTTP Status/JSON    │
└─────────────────────────┬──────────────────────────────┘
                          │ (DTOs / Domain Entities)
                          ▼
┌────────────────────────────────────────────────────────┐
│ 2. Application / Service Layer (Core Business Logic)   │
│    - Validasi Aturan Bisnis Stateful & Invarian        │
│    - Koordinasi Transaksi Multi-Repository            │
│    - Penerbitan Domain Events & Notifikasi             │
└─────────────────────────┬──────────────────────────────┘
                          │ (Domain Interfaces)
                          ▼
┌────────────────────────────────────────────────────────┐
│ 3. Data Access / Repository Layer (Persistence Adapter)│
│    - Abstraksi Engine SQL / ORM                        │
│    - Pengelolaan Koneksi & Transaksi Lokal             │
│    - Pemetaan Database Row -> Domain Entity            │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│ 4. Infrastructure & External Services                  │
│    - Connection Pool (PostgreSQL / MySQL)              │
│    - In-Memory Cache (Redis)                           │
│    - Message Broker (Kafka / RabbitMQ)                 │
└────────────────────────────────────────────────────────┘
```

### 3.2 Database Connection Pool Internal Mechanics

Koneksi TCP ke database memakan sumber daya besar (*expensive resource*) karena membutuhkan:
1. Alokasi TCP Three-Way Handshake.
2. Negosiasi TLS.
3. Otentikasi dan otorisasi internal database.
4. Alokasi memori per-koneksi pada sisi database backend engine (seperti *backend process* pada PostgreSQL).

Jika backend membuka koneksi baru setiap ada *request*, database akan mengalami *context-switching exhaustion* dan kehabisan *file descriptors*. Oleh karena itu, kita menggunakan **Connection Pool**.

```
Worker Threads / Event Loop
  Req 1 ──┐
  Req 2 ──┼───> [ Pool Manager: Acquire ]
  Req 3 ──┘           │
                      ▼
        ┌───────────────────────────┐
        │   Active Connections      │
        │   [Conn 1] [Conn 2]       │
        └───────────────────────────┘
                      ▲
                      │ (Reuse / Release)
        ┌─────────────┴─────────────┐
        │   Idle Pool (Available)   │
        │   [Conn 3] [Conn 4]       │
        └───────────────────────────┘
                      │
  (Jika Idle kosong & Active < MaxPoolSize) -> Buat TCP Connection Baru
  (Jika Active == MaxPoolSize) -> Masuk ke "Wait Queue" hingga batas Acquire Timeout
```

**Parameter Krusial Connection Pool:**
*   `min`: Jumlah koneksi *idle* yang selalu dipertahankan tetap terbuka.
*   `max`: Batas absolut koneksi simultan yang boleh dibuka oleh pool.
*   `idleTimeoutMillis`: Waktu sebelum koneksi idle ditutup hingga mencapai batas `min`.
*   `acquireTimeoutMillis`: Batas waktu pemanggil menunggu koneksi sebelum dilemparkan *Resource Exhaustion Error*.

### 3.3 Asynchronous Context Propagation (`AsyncLocalStorage`)

Di lingkungan multithreaded murni (seperti Java), data kontekstual transaksi (misal: `X-Request-ID`, `User-ID`) dapat disimpan dalam `ThreadLocal`. Namun, pada runtime single-threaded event loop berbasis non-blocking I/O (seperti Node.js), eksekusi asynchronous melompat antar fungsi callback secara acak di dalam thread yang sama.

Mengoper objek context (`req.context`) ke setiap parameter fungsi dari Controller -> Service -> Repository mengakibatkan **parameter pollution**. Solusi enterprise adalah memanfaatkan **`AsyncLocalStorage`** (atau `context.Context` di Go) yang mengikat konteks eksekusi langsung ke rantai *async continuation chain*.

---

## 4. Why & What

| Dimensi | Mengapa Dibutuhkan (*Why*) | Apa Itu (*What*) |
| :--- | :--- | :--- |
| **Layered Decoupling** | Menghindari rewrite total saat mengganti database engine atau framework HTTP. | Struktur modular di mana Service tidak mengetahui apakah ia dipanggil oleh HTTP, gRPC, atau CLI. |
| **Resilient Connection Pooling** | Mencegah database tumbang akibat lonjakan koneksi mendadak (*connection spike*). | Pengelolaan set koneksi database yang dapat digunakan kembali (*reusable sockets*). |
| **Context Propagation** | Debugging sistem terdistribusi mustahil dilakukan tanpa melacak jejak request individual. | Mekanisme membawa metadata request secara transparan melalui stack eksekusi asynchronous. |
| **Graceful Shutdown** | Mencegah data korup dan request HTTP yang terputus di tengah jalan saat deployment. | Prosedur terminasi teratur yang menyelesaikan pekerjaan aktif sebelum mematikan process OS. |

---

## 5. How (Workflow Detail)

Alur eksekusi request enterprise dari kedatangan paket hingga pelepasan sumber daya:

```
[Client] ──> [Reverse Proxy (Nginx/Traefik)] ──> [Node.js Fastify/Express App]
                                                        │
┌───────────────────────────────────────────────────────┴───────────────────────────────────────┐
│ 1. INCOMING REQUEST & MIDDLEWARE PIPELINE                                                     │
│    a. Baca Header 'x-correlation-id' (atau generate UUID v4 jika absen).                      │
│    b. Inisialisasi AsyncLocalStorage store dengan Trace Context: { traceId, startTime }.      │
│    c. Jalankan Rate Limiter (Token Bucket / Sliding Window via Redis).                        │
└───────────────────────────────────────────────────────┬───────────────────────────────────────┘
                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. CONTROLLER (TRANSPORT DECODING)                                                            │
│    a. Lakukan Payload Validation menggunakan schema parser (Zod). Gagal -> 400 Bad Request.   │
│    b. Panggil Use-Case pada Service Layer. Jangan inject objek HTTP (req, res) ke Service.   │
└───────────────────────────────────────────────────────┬───────────────────────────────────────┘
                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. SERVICE LAYER (DOMAIN ORCHESTRATION)                                                       │
│    a. Ambil data state awal dari Repository.                                                  │
│    b. Validasi invariant bisnis (misal: "Saldo tidak boleh minus", "Item stok mencukupi").    │
│    c. Eksekusi mutasi domain.                                                                 │
│    d. Buka Transaction Context dari Unit of Work jika mutasi multi-entitas.                   │
└───────────────────────────────────────────────────────┬───────────────────────────────────────┘
                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. REPOSITORY LAYER (DATA ACCESS EXECUTION)                                                   │
│    a. Acquire client connection dari Connection Pool (Timeout max: 2000ms).                   │
│    b. Jalankan parameterized SQL queries.                                                     │
│    c. Rilis koneksi kembali ke pool di dalam blok `finally`.                                  │
└───────────────────────────────────────────────────────┬───────────────────────────────────────┘
                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. RESPONSE DISPATCH & OBSERVABILITY AUDIT                                                    │
│    a. Kirim HTTP Status 200/201 beserta payload respons standar.                              │
│    b. Emit Structured Log (JSON) berisi: traceId, path, method, status, responseTimeMs.       │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Analogy & Diagram ASCII

### Analogi Dunia Nyata: Sistem Restoran Bintang Lima

Bayangkan sebuah restoran bintang lima berkapasitas besar:
*   **Controller (Pramusaji):** Menerima pesanan dari tamu, memeriksa apakah tamu berbicara dalam bahasa yang dimengerti dan menu yang dipesan tercatat di kertas menu. Pramusaji tidak pernah memasak.
*   **Service Layer (Koki Eksekutif):** Mengetahui resep, meracik bahan, mengatur urutan masakan, memastikan standar higienitas. Koki tidak melayani tamu secara langsung dan tidak pergi ke pasar membeli beras.
*   **Repository Layer (Manajer Logistik/Pantry):** Bertanggung jawab mengambil bahan mentah dari gudang pendingin atau lemari penyimpanan. Koki hanya meminta: *"Beri saya 2 potong daging Wagyu A5"*.
*   **Connection Pool (Set Pisau Koki):** Pisau dapur mahal tidak dibeli satu per satu untuk setiap pesanan yang masuk lalu dibuang. Ada rak pisau khusus (Pool) berisi 10 pisau yang diasah dan siap dipakai. Koki mengambil pisau dari rak, menggunakannya, mencucinya, dan mengembalikannya ke rak. Jika semua pisau terpakai, juru masak berikutnya harus menunggu pisau selesai dipakai.

### Diagram: Siklus Hidup Eksekusi Transaksional dan Logging

```
[HTTP Request]
     │ (traceId: "abc-123")
     ▼
┌───────────────────────────────────────────────────────────────────────┐
│ AsyncLocalStorage Scope ("abc-123")                                   │
│                                                                       │
│   Controller                                                          │
│       │                                                               │
│       ▼                                                               │
│   Service Layer                                                       │
│       │                                                               │
│       ├── Logger.info("Executing transfer...")                        │
│       │     └── Automatic Output: {"traceId":"abc-123", "msg":"..."}  │
│       │                                                               │
│       ▼                                                               │
│   Database Pool Manager                                               │
│       ├── Acquire Connection (Total Active: 5/10)                     │
│       ├── BEGIN TRANSACTION                                           │
│       │     ├── UPDATE accounts SET balance = balance - 100 WHERE ... │
│       │     └── UPDATE accounts SET balance = balance + 100 WHERE ... │
│       ├── COMMIT                                                      │
│       └── Release Connection to Pool (Active: 4/10)                   │
└───────────────────────────────────────────────────────────────────────┘
     │
     ▼
[HTTP Response: 200 OK] + Structured Metrics Emitted
```

---

## 7. Code Implementation: From Novice to Production Enterprise

Berikut adalah implementasi backend berbasis **Node.js/TypeScript** yang menerapkan clean architecture, dependency injection, pool management, structured logging, dan context propagation secara native tanpa framework bloat.

### 7.1 Bad Implementation (Anti-Pattern: Spaghetti, Unhandled Leaks, Fat Controller)

```typescript
// ANTI-PATTERN: JANGAN DITIRU DI LINGKUNGAN PRODUKSI
import express from 'express';
import { Client } from 'pg';

const app = express();
app.use(express.json());

// Fatal 1: Membuat TCP connection baru untuk setiap request
// Fatal 2: SQL Injection prone (string concatenation)
// Fatal 3: Tidak ada context tracing
// Fatal 4: Logic bisnis tercampur dengan HTTP transport
// Fatal 5: Exception unhandled dapat menyebabkan silent crash / connection leak
app.post('/api/order', async (req, res) => {
  const client = new Client({ connectionString: process.env.DATABASE_URL });
  await client.connect();

  try {
    const { userId, productId, amount } = req.body;
    
    // Logika bisnis telanjang di controller
    const userRes = await client.query(`SELECT balance FROM users WHERE id = '${userId}'`);
    if (userRes.rows[0].balance < amount) {
      return res.status(400).send("Saldo tidak cukup");
    }

    await client.query(`UPDATE users SET balance = balance - ${amount} WHERE id = '${userId}'`);
    await client.query(`INSERT INTO orders (user_id, product_id, amount) VALUES ('${userId}', '${productId}', ${amount})`);

    // Fatal: Jika client.query di atas melempar error, client.end() TIDAK PERNAH DIJALANKAN
    await client.end();
    return res.status(200).json({ success: true });
  } catch (err: any) {
    // Error details terekspos ke publik
    return res.status(500).json({ error: err.message });
  }
});
```

---

### 7.2 Enterprise-Grade Production Implementation

Struktur proyek standar modular enterprise:
```
src/
├── core/
│   ├── context.ts
│   ├── logger.ts
│   └── database.ts
├── modules/
│   └── orders/
│       ├── order.controller.ts
│       ├── order.service.ts
│       ├── order.repository.ts
│       └── order.schema.ts
└── app.ts
```

#### File: `src/core/context.ts` (Tracing Engine)
```typescript
import { AsyncLocalStorage } from 'async_hooks';

export interface RequestContext {
  traceId: string;
  userId?: string;
  startTime: bigint;
}

export const requestContextStore = new AsyncLocalStorage<RequestContext>();

export class ContextProvider {
  static getTraceId(): string {
    return requestContextStore.getStore()?.traceId ?? 'system-core-ctx';
  }

  static getStore(): RequestContext | undefined {
    return requestContextStore.getStore();
  }
}
```

#### File: `src/core/logger.ts` (High-Performance Structured JSON Logger)
```typescript
import { ContextProvider } from './context';

export class Logger {
  private static format(level: string, message: string, meta?: Record<string, unknown>): string {
    return JSON.stringify({
      timestamp: new Date().toISOString(),
      level,
      traceId: ContextProvider.getTraceId(),
      message,
      ...meta,
    });
  }

  static info(message: string, meta?: Record<string, unknown>): void {
    process.stdout.write(this.format('INFO', message, meta) + '\n');
  }

  static warn(message: string, meta?: Record<string, unknown>): void {
    process.stdout.write(this.format('WARN', message, meta) + '\n');
  }

  static error(message: string, error?: Error, meta?: Record<string, unknown>): void {
    process.stderr.write(
      this.format('ERROR', message, {
        errorMessage: error?.message,
        stack: error?.stack,
        ...meta,
      }) + '\n'
    );
  }
}
```

#### File: `src/core/database.ts` (Resilient Connection Pooling)
```typescript
import { Pool, PoolClient, PoolConfig } from 'pg';
import { Logger } from './logger';

export class DatabasePool {
  private static pool: Pool;

  static initialize(config: PoolConfig): void {
    this.pool = new Pool({
      ...config,
      max: config.max ?? 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000, // Fail-fast jika pool jenuh
    });

    this.pool.on('error', (err: Error) => {
      Logger.error('Unexpected idle client error in database pool', err);
    });
  }

  static async getClient(): Promise<PoolClient> {
    return await this.pool.connect();
  }

  static async shutdown(): Promise<void> {
    Logger.info('Closing database pool connections gracefully...');
    await this.pool.end();
    Logger.info('Database pool drained successfully.');
  }

  // Helper untuk mengeksekusi operasi di dalam transaksi yang aman
  static async transaction<T>(callback: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.getClient();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release(); // Menjamin pelepasan koneksi kembali ke pool
    }
  }
}
```

#### File: `src/modules/orders/order.schema.ts` (Defensive Validation Schema)
```typescript
import { z } from 'zod';

export const CreateOrderSchema = z.object({
  userId: z.string().uuid(),
  productId: z.string().uuid(),
  amount: z.number().positive().max(1_000_000_000), // Max limit prevents overflows
});

export type CreateOrderDTO = z.infer<typeof CreateOrderSchema>;

export interface OrderEntity {
  id: string;
  userId: string;
  productId: string;
  amount: number;
  status: 'PENDING' | 'SETTLED' | 'FAILED';
  createdAt: Date;
}
```

#### File: `src/modules/orders/order.repository.ts` (Pure Data Access Object)
```typescript
import { PoolClient } from 'pg';
import { OrderEntity } from './order.schema';

export interface IOrderRepository {
  createOrder(client: PoolClient, order: Omit<OrderEntity, 'id' | 'createdAt'>): Promise<OrderEntity>;
  deductUserBalance(client: PoolClient, userId: string, amount: number): Promise<boolean>;
}

export class OrderRepository implements IOrderRepository {
  async deductUserBalance(client: PoolClient, userId: string, amount: number): Promise<boolean> {
    // Atomic row-level lock: SELECT FOR UPDATE
    const query = `
      UPDATE users 
      SET balance = balance - $1 
      WHERE id = $2 AND balance >= $1
      RETURNING id;
    `;
    const res = await client.query(query, [amount, userId]);
    return (res.rowCount ?? 0) > 0;
  }

  async createOrder(client: PoolClient, order: Omit<OrderEntity, 'id' | 'createdAt'>): Promise<OrderEntity> {
    const query = `
      INSERT INTO orders (user_id, product_id, amount, status)
      VALUES ($1, $2, $3, $4)
      RETURNING id, user_id as "userId", product_id as "productId", amount, status, created_at as "createdAt";
    `;
    const res = await client.query(query, [order.userId, order.productId, order.amount, order.status]);
    return res.rows[0];
  }
}
```

#### File: `src/modules/orders/order.service.ts` (Domain Business Orchestration)
```typescript
import { DatabasePool } from '../../core/database';
import { Logger } from '../../core/logger';
import { CreateOrderDTO, OrderEntity } from './order.schema';
import { IOrderRepository } from './order.repository';

export class InsufficientBalanceException extends Error {
  constructor() {
    super('Domain Invariant Violation: Insufficient account balance.');
    this.name = 'InsufficientBalanceException';
  }
}

export class OrderService {
  constructor(private readonly orderRepo: IOrderRepository) {}

  async processOrder(dto: CreateOrderDTO): Promise<OrderEntity> {
    Logger.info('Initiating order creation workflow', { userId: dto.userId, amount: dto.amount });

    return await DatabasePool.transaction(async (client) => {
      // Step 1: Potong saldo akun pengguna secara atomik
      const balanceDeducted = await this.orderRepo.deductUserBalance(client, dto.userId, dto.amount);
      if (!balanceDeducted) {
        Logger.warn('Order processing halted: Insufficient funds', { userId: dto.userId });
        throw new InsufficientBalanceException();
      }

      // Step 2: Buat entitas order baru
      const order = await this.orderRepo.createOrder(client, {
        userId: dto.userId,
        productId: dto.productId,
        amount: dto.amount,
        status: 'SETTLED',
      });

      Logger.info('Order successfully created and committed', { orderId: order.id });
      return order;
    });
  }
}
```

#### File: `src/modules/orders/order.controller.ts` (HTTP Boundary Translator)
```typescript
import { Request, Response } from 'express';
import { OrderService, InsufficientBalanceException } from './order.service';
import { CreateOrderSchema } from './order.schema';
import { Logger } from '../../core/logger';

export class OrderController {
  constructor(private readonly orderService: OrderService) {}

  handleCreateOrder = async (req: Request, res: Response): Promise<void> => {
    try {
      // 1. Validasi Input Payload
      const parseResult = CreateOrderSchema.safeParse(req.body);
      if (!parseResult.success) {
        res.status(400).json({
          error: 'BAD_REQUEST',
          details: parseResult.error.flatten(),
        });
        return;
      }

      // 2. Delegasi ke Service Layer
      const order = await this.orderService.processOrder(parseResult.data);

      // 3. Serialisasi Output
      res.status(201).json({
        success: true,
        data: order,
      });
    } catch (error: any) {
      if (error instanceof InsufficientBalanceException) {
        res.status(422).json({ error: 'UNPROCESSABLE_ENTITY', message: error.message });
        return;
      }

      Logger.error('Unhandled internal failure in OrderController', error);
      res.status(500).json({ error: 'INTERNAL_SERVER_ERROR', message: 'An unexpected transaction error occurred.' });
    }
  };
}
```

#### File: `src/app.ts` (Production App Bootstrapper & Lifecycle Management)
```typescript
import express, { Request, Response, NextFunction } from 'express';
import crypto from 'crypto';
import http from 'http';
import { requestContextStore } from './core/context';
import { Logger } from './core/logger';
import { DatabasePool } from './core/database';
import { OrderRepository } from './modules/orders/order.repository';
import { OrderService } from './modules/orders/order.service';
import { OrderController } from './modules/orders/order.controller';

const app = express();
app.use(express.json());

// Inisialisasi Database Pool
DatabasePool.initialize({
  connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/enterprise_db',
  max: 25,
});

// Middleware: Tracing Context & Observability Interceptor
app.use((req: Request, res: Response, next: NextFunction) => {
  const traceId = (req.headers['x-correlation-id'] as string) || crypto.randomUUID();
  const startTime = process.hrtime.bigint();

  res.setHeader('x-correlation-id', traceId);

  requestContextStore.run({ traceId, startTime }, () => {
    res.on('finish', () => {
      const endTime = process.hrtime.bigint();
      const elapsedMs = Number(endTime - startTime) / 1_000_000;
      Logger.info('HTTP Request Executed', {
        method: req.method,
        path: req.originalUrl,
        statusCode: res.statusCode,
        durationMs: elapsedMs.toFixed(3),
      });
    });
    next();
  });
});

// Dependency Injection Wiring
const orderRepo = new OrderRepository();
const orderService = new OrderService(orderRepo);
const orderController = new OrderController(orderService);

// Route Mapping
app.post('/api/v1/orders', orderController.handleCreateOrder);

// Health Check API
app.get('/health/liveness', (req, res) => res.status(200).send('OK'));
app.get('/health/readiness', async (req, res) => {
  try {
    const client = await DatabasePool.getClient();
    await client.query('SELECT 1');
    client.release();
    res.status(200).json({ status: 'UP', database: 'CONNECTED' });
  } catch (err) {
    res.status(503).json({ status: 'DOWN', database: 'UNAVAILABLE' });
  }
});

// Server Initialization
const PORT = process.env.PORT || 3000;
const server = http.createServer(app);

server.listen(PORT, () => {
  Logger.info(`Worker server process active on port ${PORT}`);
});

// Enterprise Graceful Shutdown Routine
const initiateShutdown = (signal: string) => {
  Logger.warn(`Received ${signal}. Initiating controlled graceful shutdown...`);

  // Stop accepting new incoming requests
  server.close(async () => {
    Logger.info('HTTP server stopped processing incoming traffic.');
    try {
      // Drain and disconnect database connection pool
      await DatabasePool.shutdown();
      Logger.info('Process termination cleanup finalized. Exiting normally.');
      process.exit(0);
    } catch (err: any) {
      Logger.error('Forced failure during graceful shutdown teardown', err);
      process.exit(1);
    }
  });

  // Forceful termination fallback if shutdown hangs beyond SLA
  setTimeout(() => {
    Logger.error('Graceful shutdown SLA exceeded (10000ms). Forcing hard SIGKILL.');
    process.exit(1);
  }, 10000).unref();
};

process.on('SIGTERM', () => initiateShutdown('SIGTERM'));
process.on('SIGINT', () => initiateShutdown('SIGINT'));
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario: Kasus Black Friday Flash-Sale E-Commerce

*   **Latar Belakang:** Perusahaan fintech-retail meluncurkan promo *Mega Flash Sale*. Sistem disiapkan menangani 15.000 Request Per Second (RPS) menggunakan 30 instance container backend yang berjalan di Kubernetes.
*   **Insiden Pukul 00:01:** Saat promo dimulai, utilisasi CPU pada pod aplikasi hanya 25%, namun p99 latency melonjak dari 45ms ke 12.000ms. Seluruh sistem mulai melempar `HTTP 500 / 504 Gateway Timeout`.
*   **Investigasi Root-Cause:**
    1.  Tiap pod diatur dengan konfigurasi `MaxPoolSize = 100`. Dengan 30 pod, total potensi koneksi adalah `30 * 100 = 3000 koneksi`.
    2.  Database PostgreSQL utama dikonfigurasi dengan `max_connections = 1000`.
    3.  Ketika trafik melonjak, 30 pod secara serentak berebut membuka koneksi baru ke database. Terjadi **Database Connection Thrashing**: PostgreSQL kehabisan memory buffer untuk alokasi thread backend, menyebabkan CPU database mencapai 100% hanya untuk *context switching* dan alokasi koneksi.
    4.  Aplikasi mengalami *Connection Acquisition Timeout* karena antrean permintaan koneksi di sisi client pool membengkak drastis.
*   **Solusi Rekayasa Berkelanjutan:**
    1.  **Downsizing Pool:** Menurunkan batas `MaxPoolSize` dari 100 ke 15 per pod berdasarkan formula:
        $$\text{Pool Size} = (\text{Core Database} \times 2) + \text{Disk Spindle Count}$$
        Total koneksi maksimal: $30 \times 15 = 450$ koneksi (jauh di bawah batas 1000 PG connections).
    2.  **Architectural Offloading:** Mengimplementasikan PgBouncer di layer infrastruktur sebagai *Connection Concentrator/Proxy*.
    3.  **Read-Write Splitting:** Memindahkan query non-transaksional (riwayat order, katalog produk) ke Read-Replica Pool, menyisakan Primary Pool eksklusif untuk mutasi finansial.
    4.  **Hasil:** Latency p99 stabil pada 68ms di beban puncak 22.000 RPS tanpa satu pun request mengalami timeout.

---

## 9. Trade-offs & Engineering Decisions

Dalam mendesain backend tingkat lanjut, tidak ada solusi yang absolut, yang ada hanyalah pertukaran (*trade-offs*):

```
                       [ Complexity ]
                            ▲
                            │       ● Microservices with Saga
                            │
                            │   ● Clean Architecture (Interfaces + DI)
                            │
                            │ ● Active-Record / Fat Controller
                            │
  ──────────────────────────┼──────────────────────────────► [ Scalability &
                            │                                   Maintainability ]
```

| Pendekatan | Kelebihan | Kelemahan | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- |
| **Layered / Clean Architecture** | Testability sangat tinggi (Unit Test bisa 100% tanpa mock DB nyata), isolasi bug tinggi. | *Boilerplate code* banyak, membutuhkan *mental model* tinggi bagi developer baru. | Aplikasi enterprise dengan domain bisnis kompleks dan umur proyek > 1 tahun. |
| **Fat Controller / Inline SQL** | Kecepatan pengembangan sangat cepat (High Time-to-Market). | Menjadi "Spaghetti Code", mustahil dilakukan *isolated testing*, resiko memory/connection leaks tinggi. | Prototype, MVP hackathon, skrip batch skop terbatas. |
| **Koneksi Pool Besar (e.g., 100+)** | Mampu menampung throughput request internal yang sangat banyak secara bersamaan. | Menghabiskan RAM server DB, meningkatkan overhead context-switching pada kernel DB engine. | Server database raksasa dengan resource core & memory yang sangat besar. |
| **Koneksi Pool Kecil (e.g., 10-20)** | Database berjalan pada efisiensi maksimal tanpa degradasi CPU, footprint RAM rendah. | Request HTTP harus mengantre di memory Node.js jika terjadi lonjakan query yang lambat. | Standard arsitektur cloud microservices/containerized backend. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Connection Leaking
*   **Gejala:** Backend berjalan lancar selama 2 jam, kemudian secara mendadak berhenti merespons seluruh request baru (`Connection acquire timeout`).
*   **Penyebab:** Memanggil `client = await pool.connect()` tanpa menaruh `client.release()` di dalam blok `finally`. Bila terjadi exception di tengah eksekusi, koneksi tidak pernah dilepaskan dan tetap dianggap sibuk.
*   **Solusi:** Selalu gunakan *wrapper pattern* (seperti `DatabasePool.transaction()` pada seksi 7) atau pastikan blok `finally` mengeksekusi `.release()`.

### 10.2 Thundering Herd Problem pada Cache Miss
*   **Gejala:** Kunci cache Redis kedaluwarsa (*expired*), seketika database tumbang karena ribuan request secara bersamaan mengeksekusi query lambat yang sama langsung ke database.
*   **Solusi:** Gunakan **Mutex Lock / Single-Flight Pattern** saat cache miss terjadi: hanya request pertama yang diizinkan mengambil data ke DB dan mengisi Redis, sementara request lain menunggu hasil request pertama.

### 10.3 Parameter Pollution & Global State Leaks
*   **Gejala:** User A menerima data pesanan milik User B secara acak pada saat beban sistem tinggi.
*   **Penyebab:** Menyimpan data request (seperti `userId`) pada variabel global atau properti singleton class instance, yang tertimpa oleh request berikutnya sebelum request pertama selesai.
*   **Solusi:** Jangan pernah menyimpan state request pada scope instance. Gunakan parameter passing murni atau `AsyncLocalStorage`.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa (*checklist*) ini sebelum merilis sistem backend ke live production:

- [ ] **Defensive Connection Pool Timeout:** Parameter `connectionTimeoutMillis` tidak boleh default (tak terbatas). Atur ke $\le 3000\text{ ms}$.
- [ ] **Structured Logging Format:** Seluruh log console wajib berformat Single-Line JSON. Dilarang menggunakan `console.log()` polos.
- [ ] **Correlation ID Propagation:** Setiap response wajib mencantumkan header `x-correlation-id`, dan nilai tersebut tertera pada setiap baris log eksekusi.
- [ ] **Graceful Shutdown Interceptor:** Server meng-intercept sinyal `SIGTERM` dan `SIGINT`, memberi tenggat waktu untuk menghabiskan transaksi aktif sebelum keluar.
- [ ] **Health Endpoint Segregation:**
    - `/health/liveness`: Cukup memastikan proses web server menyala (tidak mengecek dependency eksternal).
    - `/health/readiness`: Melakukan ping nyata ke Database dan Redis untuk memastikan sistem siap melayani traffic.
- [ ] **Fail-Safe Exception Handling:** Memasang global handler `process.on('unhandledRejection')` dan `process.on('uncaughtException')` untuk mencegah status server *zombie*.
- [ ] **Query Parameterization:** 100% query database menggunakan placeholder parameter ($1, $2, dst) untuk menutup celah SQL Injection.

---

## 12. Hands-on Practice

Buatlah sistem backend produksi mini pada direktori `hands-on/m02/` dengan langkah berikut:

### Langkah 1: Setup Lingkungan Proyek
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
npm init -y
npm install typescript ts-node @types/node express @types/express pg @types/pg zod
npx tsc --init
```

### Langkah 2: Buat Database Schema di PostgreSQL Lokal/Docker
```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    balance NUMERIC(15, 2) NOT NULL CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    product_id UUID NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed user dummy
INSERT INTO users (id, balance) VALUES ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 500000);
```

### Langkah 3: Strukturkan Kode
Salin kode dari **Seksi 7.2** ke dalam berkas-berkas terkait:
*   `src/core/context.ts`
*   `src/core/logger.ts`
*   `src/core/database.ts`
*   `src/modules/orders/order.schema.ts`
*   `src/modules/orders/order.repository.ts`
*   `src/modules/orders/order.service.ts`
*   `src/modules/orders/order.controller.ts`
*   `src/app.ts`

### Langkah 4: Uji Coba Eksekusi dan Verifikasi Graceful Shutdown
1. Jalankan aplikasi:
   ```bash
   npx ts-node src/app.ts
   ```
2. Lakukan request valid menggunakan `curl`:
   ```bash
   curl -X POST http://localhost:3000/api/v1/orders \
     -H "Content-Type: application/json" \
     -H "x-correlation-id: test-manual-001" \
     -d '{
       "userId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
       "productId": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
       "amount": 25000
     }'
   ```
3. Periksa log terminal: Amati log terstruktur JSON yang membawa `traceId: test-manual-001`.
4. Kirim sinyal `SIGTERM`: Tekan `Ctrl + C` (atau jalankan `kill -15 <PID>`), dan pastikan log menampilkan prosedur graceful shutdown dan penutupan koneksi pool sebelum proses berakhir.

---

## 13. Exercises

### Level: Easy
Implementasikan middleware *Request Timing Profiler* yang memeriksa apabila suatu request memakan waktu lebih dari 500ms, sistem secara otomatis mencetak log dengan level `WARN` bertuliskan `"SLOW_QUERY_OR_PROCESS"`.

### Level: Medium
Buatlah middleware idempotensi (*Idempotency-Key*) untuk rute pemesanan (`POST /api/v1/orders`). Jika klien mengirim header `Idempotency-Key` yang sama dalam kurun waktu 60 detik, server harus mengembalikan respons yang sama tanpa mengeksekusi logika database Service Layer kembali.

### Level: Hard
Kembangkan implementasi *In-Memory Dynamic Connection Pool Manager* kustom sederhana (tanpa menggunakan library pihak ketiga `pg.Pool`) yang mengelola instansiasi koneksi raw TCP, memiliki parameter `min`, `max`, antrean pemanggil (*wait queue*), dan melempar error ketika batas antrean terlampaui atau batas waktu acquire kadaluwarsa.

---

## 14. Challenges

### Sistem Tiketing Konser dengan Proteksi Over-Selling Terdistribusi

**Deskripsi Masalah:**
Sebuah platform penjualan tiket konser akan membuka penjualan untuk artis dunia dengan alokasi 1.000 kursi dalam satu stadion. Diperkirakan terdapat 50.000 pengguna yang akan menekan tombol "Bayar Sekarang" pada detik pertama pembukaan tiket.

**Kriteria & Batasan Teknis:**
1.  **Strict Invariant:** Tiket yang terjual tidak boleh melebihi 1.000 (Nol Over-Selling Tolerance).
2.  **Concurrency Isolation:** Penggunaan penguncian basis data tidak boleh memicu *Deadlock* antar transaksi konkuren.
3.  **High Resilience:** Jika database node utama mengalami restart mendadak di tengah proses, kondisi data transaksi tidak boleh berada dalam status *ghost/inconsistent* (wajib mematuhi prinsip atomisitas rollback penuh).
4.  **Performance Baseline:** Sistem harus mampu mempertahankan p95 latency di bawah 200ms pada pod backend yang dibatasi memory-nya (max 512MB RAM).

**Tugas Anda:**
Rancang dan bangun arsitektur sistem backend lengkap (lapisan kode Service, Repository, konfigurasi Connection Pool, skema SQL transaksi dengan row-level lock atau counter optimistic lock) yang mampu melewati skenario stress test konkuren tanpa satu pun invariant yang terlanggar.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

1. **Apa bahaya utama mengeksekusi koneksi basis data baru (`new DatabaseClient().connect()`) di setiap rute handler HTTP?**
   * A. Query SQL akan selalu gagal dieksekusi.
   * B. Terjadi konsumsi memory dan CPU yang berlebihan akibat overhead pembukaan koneksi TCP secara terus menerus, yang dapat melumpuhkan database.
   * C. Data yang disimpan otomatis terhapus saat koneksi ditutup.
   * D. HTTP Status Code tidak bisa dikembalikan ke client.

2. **Pada arsitektur Clean/Layered, komponen mana yang berhak mengelola status HTTP seperti `res.status(200)`?**
   * A. Domain Model Entity
   * B. Service Layer
   * C. Transport Layer / Controller
   * D. Repository Layer

3. **Apa kegunaan dari pola *Graceful Shutdown* pada backend modern?**
   * A. Mempercepat proses deployment menjadi di bawah 1 detik.
   * B. Memastikan seluruh request yang sedang berjalan diselesaikan dan sumber daya seperti koneksi database ditutup sebelum aplikasi mati.
   * C. Menyimpan state memori server ke dalam hard disk lokal secara instan.
   * D. Menghapus data log yang lama secara otomatis.

4. **Kapan sebaiknya kita menggunakan `SELECT ... FOR UPDATE` dalam query SQL?**
   * A. Saat kita hanya ingin membaca data tanpa mengubahnya.
   * B. Saat kita ingin mempercepat jalannya query indeks.
   * C. Saat kita perlu mengunci baris data tertentu agar tidak diubah oleh transaksi paralel lain hingga transaksi saat ini selesai.
   * D. Saat kita ingin menghapus tabel secara aman.

5. **Apa fungsi utama dari `Correlation ID` (atau `Trace ID`) pada arsitektur backend?**
   * A. Mengenkripsi password user dalam basis data.
   * B. Melacak jejak eksekusi satu request tertentu dari hulu ke hilir lintas berbagai file, log, dan service.
   * C. Menggantikan peran JSON Web Token (JWT).
   * D. Menghitung jumlah baris data dalam tabel SQL.

---

### Bagian 2: Intermediate (5 Soal)

6. **Mengapa parameter `connectionTimeoutMillis` pada Connection Pool wajib didefinisikan secara eksplisit di lingkungan produksi?**
   * A. Agar query database yang salah ketik (typo) otomatis diperbaiki oleh library pool.
   * B. Mencegah request HTTP menunggu tanpa batas (*hanging indefinitely*) saat pool jenuh, sehingga server dapat segera merespons dengan pesan kegagalan (Fail-Fast).
   * C. Mengurangi biaya bandwidth jaringan server.
   * D. Untuk mempercepat proses kompresi payload JSON.

7. **Bagaimana mekanisme `AsyncLocalStorage` dapat mempertahankan referensi konteks pada alur asynchronous di Node.js?**
   * A. Dengan menduplikasi thread OS untuk tiap-tiap Promise yang dibuat.
   * B. Dengan mengikat data state ke siklus hidup *async resource* internal engine via kait *async execution context lifecycle*.
   * C. Dengan menyimpannya ke dalam file temporary di sistem operasi.
   * D. Melalui global variable yang otomatis di-reset oleh Garbage Collector.

8. **Apa perbedaan mendasar antara endpoint `/health/liveness` dan `/health/readiness` pada arsitektur orkestrator kontainer (seperti Kubernetes)?**
   * A. Keduanya identik dan hanya berupa alias penamaan rute.
   * B. *Liveness* memeriksa apakah proses aplikasi hidup (jika gagal, container di-restart); *Readiness* memeriksa apakah aplikasi siap menerima traffic, termasuk dependensi eksternal (jika gagal, traffic dialihkan).
   * C. *Liveness* untuk otentikasi user; *Readiness* untuk otorisasi user.
   * D. *Liveness* dijalankan di browser; *Readiness* dijalankan di backend.

9. **Jika connection pool database diatur dengan ukuran `MaxPool = 100`, namun database PostgreSQL hanya di-host pada mesin dengan 2 vCPU dan 4GB RAM, apa yang kemungkinan besar terjadi saat lonjakan trafik masif?**
   * A. Database memproses data 100x lebih cepat secara instan.
   * B. Database mengalami degradasi performa drastis akibat perebutan CPU (*CPU context thrashing*) dan potensi kehabisan memori (*OOM Kill*).
   * C. PostgreSQL secara otomatis menambah vCPU server secara virtual.
   * D. Seluruh transaksi diubah menjadi asynchronous in-memory.

10. **Mengapa pemanggilan fungsi logging `console.log()` polos dianggap sebagai anti-pattern pada aplikasi backend berskala besar?**
    * A. Karena `console.log()` tidak didukung oleh Docker.
    * B. Bersifat sinkronus/blocking pada beberapa runtime OS stream, mencetak format un-structured text yang sulit di-parse oleh log collector (seperti Fluentd/Elasticsearch), serta tidak memuat context metadata secara konsisten.
    * C. Menyebabkan syntax error saat kode di-compile ke production.
    * D. Membatasi panjang teks yang bisa ditulis hanya sampai 256 karakter.

---

### Bagian 3: Production Case Scenarios (3 Soal Kasus)

11. **Skenario Kasus 1: Insiden Double-Spending Saldo Pengguna**
    Sebuah aplikasi dompet digital mengalami insiden di mana seorang pengguna dengan saldo Rp 100.000 dapat melakukan dua penarikan saldo simultan sebesar Rp 100.000 dalam selang waktu 10 milidetik. Kedua penarikan berhasil, menyisakan saldo akhir pengguna menjadi Rp 0 (bukan gagal di transaksi kedua), mengakibatkan kerugian perusahaan.
    *Pertanyaan:* Berdasarkan konsep data access dan concurrency control yang dipelajari pada bab ini, di manakah letak kelemahan kode aplikasi mereka, dan bagaimana arsitektur transaksi yang benar untuk memitigasinya?

12. **Skenario Kasus 2: The Cascading Connection Drain**
    Pada pukul 14:00, service backend pembayaran mendadak berhenti melayani traffic. Metrik menunjukkan utilisasi koneksi database mencapai batas maksimum (`Active Connections: 50/50`). Tim investigasi menemukan bahwa ada integrasi API pihak ketiga (Payment Gateway) yang mengalami *slowdown* (respons memakan waktu 40 detik dari yang biasanya 200 milidetik).
    *Pertanyaan:* Mengapa kelambatan pada pihak ketiga (HTTP Third Party) dapat menghabiskan koneksi database lokal backend Anda, dan bagaimana strategi decoupling arsitektur yang wajib diterapkan untuk memutus keterikatan ini?

13. **Skenario Kasus 3: Deployment Downtime Misterius**
    Sebuah tim melakukan deployment versi baru aplikasi backend ke cluster produksi menggunakan skema Rolling Update. Meskipun tidak ada error sintaksis pada rilis baru, setiap kali proses rolling deployment berjalan, sekitar 2-3% request pengguna dilaporkan mengembalikan pesan `502 Bad Gateway` atau koneksi terputus tiba-tiba (*Connection reset by peer*).
    *Pertanyaan:* Apa yang menyebabkan kegagalan ini pada siklus hidup process container backend, dan urutan implementasi apa yang harus diterapkan pada aplikasi dan web server reverse proxy untuk mencapai deployment murni tanpa downtime (Zero-Downtime Deployment)?

---

### Kunci Jawaban & Analisis Solusi Kuis

#### Bagian 1 & 2
1. **B** - Membuka koneksi TCP baru membutuhkan TLS handshake dan otentikasi yang membebani CPU database dan backend.
2. **C** - Transport Layer (Controller) bertanggung jawab terhadap adaptasi protokol HTTP (Status Code, Header, JSON Payload).
3. **B** - Graceful shutdown menuntaskan pekerjaan aktif dan melepaskan koneksi resource sebelum OS mematikan process.
4. **C** - `SELECT ... FOR UPDATE` memberikan garansi isolasi konkurensi tingkat baris agar terhindar dari kondisi race condition.
5. **B** - Correlation ID adalah pengenal tunggal untuk menautkan seluruh peristiwa eksekusi satu siklus request.
6. **B** - Mencegah antrean tak berhingga saat database pool jenuh (*fail-fast mechanism*).
7. **B** - `AsyncLocalStorage` bekerja langsung di level engine Node.js untuk melacak konteks asynchronous context continuation.
8. **B** - Liveness mengontrol siklus hidup restart container, sedangkan Readiness mengontrol penyaluran traffic jaringan.
9. **B** - CPU core yang terbatas tidak mampu mengelola thread konkurensi berlebih tanpa menimbulkan thrashing parah.
10. **B** - `console.log` menghasilkan teks mentah tidak berstruktur (*unstructured string*) yang menyulitkan pengindeksan log agregator modern.

#### Bagian 3: Solusi Skenario Produksi

11. **Analisis Solusi Kasus 1:**
    *   *Penyebab:* Sistem mengalami masalah **Race Condition (Check-Then-Act Flaw)**. Service membaca saldo dengan query biasa (`SELECT balance FROM users`), memvalidasinya di memory aplikasi, lalu mengirim `UPDATE users SET balance = balance - 100`. Pada eksekusi simultan, kedua transaksi membaca saldo yang sama (Rp 100.000) sebelum transaksi pertama sempat melakukan update saldo.
    *   *Solusi:* Terapkan operasi atomik di tingkat database. Opsi terbaik adalah menggunakan query atomic bersyarat:
        `UPDATE users SET balance = balance - 100 WHERE id = $1 AND balance >= 100;`
        Lalu periksa `rowCount`. Jika `rowCount === 0`, lemparkan `InsufficientBalanceException`. Alternatif lain adalah melakukan penguncian eksplisit `SELECT balance FROM users WHERE id = $1 FOR UPDATE;` di dalam transaksi database yang terisolasi.

12. **Analisis Solusi Kasus 2:**
    *   *Penyebab:* Developer membuka koneksi database (atau menjalankan transaksi DB) **sebelum** atau **sambil menunggu** panggilan I/O jaringan pihak ketiga selesai. Karena panggilan pihak ketiga tertahan selama 40 detik, koneksi database yang sedang dipegang tidak dilepaskan kembali ke pool. Akibatnya, 50 koneksi pool habis hanya untuk menunggu respons HTTP pihak ketiga.
    *   *Solusi:* Terapkan prinsip **Never Hold DB Connections Over External Network I/O**:
        1. Pisahkan proses: Simpan order dengan status `PENDING` lalu segera commit dan rilis koneksi database.
        2. Lakukan panggilan API pihak ketiga di luar konteks transaksi database, lengkap dengan defensive timeout pendek (misal: max 3000ms).
        3. Setelah ada respons dari pihak ketiga, buka koneksi database baru untuk memperbarui status transaksi menjadi `SETTLED` atau `FAILED`.
        4. Terapkan *Circuit Breaker Pattern* pada pemanggilan payment gateway pihak ketiga tersebut.

13. **Analisis Solusi Kasus 3:**
    *   *Penyebab:* Saat deployment bergulir, orkestrator (seperti Kubernetes) mengirim sinyal `SIGTERM` ke pod lama dan seketika mencabut alamat IP-nya dari Service/Ingress. Namun, ada jeda waktu penyebaran iptables/DNS proxy, sehingga proxy masih sempat meneruskan request baru ke pod lama yang sedang mati. Selain itu, pod lama langsung mematikan proses aplikasinya secara instan tanpa menyelesaikan request HTTP yang sedang berjalan.
    *   *Solusi:*
        1. Pasang handler penanganan sinyal `SIGTERM` di backend untuk menjalankan **Graceful Shutdown** (`server.close()`).
        2. Berikan jeda sleep awal pendek (misal: 2-5 detik) pada script pre-stop container sebelum `server.close()` dipanggil, agar Ingress/Reverse Proxy memiliki waktu untuk menghapus endpoint IP pod tersebut dari routing list.
        3. Pastikan Reverse Proxy (seperti Nginx) dikonfigurasi dengan retry policy otomatis (`proxy_next_upstream error timeout http_502`) ke pod yang masih sehat.

---

## 16. Summary

Membangun backend tingkat produksi menuntut pergeseran paradigma: dari sekadar "kode yang bekerja di komputer lokal" menuju sistem yang **berdaya tahan tinggi (*resilient*)**, **teramati (*observable*)**, dan **aman di bawah tekanan (*defensive under load*)**. 

Pondasi utama yang membedakan engineer pemula dan level enterprise terletak pada pemahaman mendalam atas batas-batas kapasitas sistem: bagaimana sumber daya kritis seperti *Database Connection Pool* dikelola, bagaimana arsitektur dipisahkan agar logika bisnis tidak terikat pada framework transport, serta bagaimana setiap kegagalan dapat dideteksi secara presisi melalui propagasi konteks dan structured logging. Dengan disiplin arsitektur ini, backend yang Anda bangun siap menopang jutaan transaksi secara stabil dan deterministik.