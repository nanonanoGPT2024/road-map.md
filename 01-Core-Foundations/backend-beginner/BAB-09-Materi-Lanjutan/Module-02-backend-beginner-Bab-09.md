# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Mengimplementasikan Arsitektur Heksagonal (Ports & Adapters)** untuk memisahkan logika bisnis murni (*core domain*) dari dependensi eksternal (*framework*, database, HTTP transport).
2. **Membangun Mekanisme Ketahanan Sistem (*System Resiliency*)** menggunakan pola *Circuit Breaker*, *Exponential Backoff with Jitter*, dan *Distributed Rate Limiting*.
3. **Mengelola Siklus Hidup Aplikasi & Sumber Daya Produksi** melalui *Graceful Shutdown*, manajemen sinyal OS (`SIGTERM`/`SIGINT`), serta tuning *Database Connection Pooling* untuk mencegah *resource exhaustion*.
4. **Menerapkan Standar Observabilitas Enterprise** mencakup *Structured JSON Logging* berkonteks correlation/trace ID, metrik *RED (Rate, Errors, Duration)*, dan *Health Check probes* (`/live`, `/ready`).
5. **Merancang Strategi Migrasi Skema Basis Data Non-Destruktif** menggunakan pola *Expand and Contract* (Parallel Run) untuk mendukung *Zero-Downtime Deployment*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

* **Dasar Backend & HTTP Engine**: Siklus request-response, middleware, HTTP status codes, parsing payload, dan routing.
* **Database Relasional & Transaksi**: Konsep ACID, isolasi transaksi, query optimization dasar, dan penggunaan indeks.
* **Concurrency & Asynchronous Programming**: Event Loop, Promises/Async-Await (Node.js/TypeScript) atau Goroutines/Channels (Go).
* **Kontainerisasi Dasar**: Menjalankan aplikasi dan database PostgreSQL menggunakan Docker dan Docker Compose.

---

## 3. Concept & Internal Architecture

### 3.1 Transisi Paradigma: Dari Scripting Monolitik ke Arsitektur Heksagonal

Aplikasi pemula umumnya memusatkan logika rute, validasi, query SQL, dan panggilan API pihak ketiga dalam satu handler controller (*Spaghetti Code*). Pada arsitektur produksi berskala enterprise, arsitektur yang digunakan adalah **Ports & Adapters (Hexagonal Architecture)**.

```
       +-------------------------------------------------------+
       |                  INFRASTRUCTURE LAYER                 |
       |  +--------------------+        +-------------------+  |
       |  |   HTTP Controllers |        | Message Consumers |  |
       |  +---------+----------+        +---------+---------+  |
       +------------|-----------------------------|------------+
                    | (Inbound Adapter)           |
                    v                             v
       +------------+-----------------------------+------------+
       |                  APPLICATION CORE                     |
       |             [ Input Port / Use Case Interface ]       |
       |                            |                          |
       |                            v                          |
       |                   +-----------------+                 |
       |                   |  Business Logic |                 |
       |                   |  & Domain Model |                 |
       |                   +-----------------+                 |
       |                            |                          |
       |             [ Output Port / SPI Interface ]           |
       +----------------------------+--------------------------+
                                    |
                    +---------------+---------------+
                    | (Outbound Adapter)            | (Outbound Adapter)
                    v                               v
       +------------+----------+        +-----------+----------+
       |  PostgreSQL Repository|        |  Third-Party Payment |
       |  Adapter (pg/knex)    |        |  HTTP Client Adapter |
       +-----------------------+        +----------------------+
       |                  INFRASTRUCTURE LAYER                 |
       +-------------------------------------------------------+
```

* **Domain Core**: Berisi entitas dan *business invariants*. Lapisan ini tidak boleh mengimpor modul dari Express, Fastify, TypeORM, atau database driver apa pun. Murni bahasa pemrograman standar.
* **Ports (Interfaces)**: Kontrak abstrak yang mendefinisikan apa yang dibutuhkan oleh Core (*Output Ports*) atau apa yang disediakan oleh Core untuk dunia luar (*Input Ports*).
* **Adapters**: Implementasi konkret dari Ports. 
  * *Inbound Adapter*: Menerjemahkan HTTP request, CLI command, atau event Kafka menjadi panggilan ke Core Use Case.
  * *Outbound Adapter*: Menerjemahkan instruksi persistensi domain menjadi query SQL (`pg`), pemanggilan cache (`ioredis`), atau HTTP request ke payment gateway.

### 3.2 Internal Resilience: Circuit Breaker State Machine

Kondisi kegagalan pada distributed system bersifat menular (*cascading failure*). Ketika service eksternal (misal: Bank Payment Gateway) mengalami penurunan performa (latensi tinggi atau timeout), aplikasi backend yang terus membombardir request akan mengalami penumpukan request, kehabisan worker thread/event loop ticks, dan akhirnya kehabisan connection socket.

Circuit Breaker mencegah cascading failure dengan memonitor kegagalan downstream menggunakan state machine berikut:

```
          [ Normal Requests ]
     +--------------------------+
     |                          |
     v      Success             |
+--------+ ----------> +----------------+
|        |             |                | Failure Threshold Exceeded
| CLOSED |             |   HALF-OPEN    | <---------------------------+
|        | <---------- |                |                             |
+--------+   Success   +----------------+                             |
    |      Threshold                            Reset Timeout         |
    |       Reached                                Expired            |
    |                                                                 |
    | Failure Threshold Exceeded                                      |
    v                                                                 |
+------------------------------------------------------------------+  |
|                                                                  |  |
|                              OPEN                                | -+
|   (Fast-fail all requests immediately without hitting downstream)|
+------------------------------------------------------------------+
```

* **State CLOSED**: Semua request diteruskan ke downstream. Tingkat kegagalan (*error rate*) dipantau dalam sebuah *sliding time window*.
* **State OPEN**: Jika rasio kegagalan melewati batas ambang (*failure threshold*, misal: 50% dari 20 request terakhir timeout/error), circuit berubah menjadi OPEN. Semua request berikutnya akan langsung di-*fail-fast* (mengembalikan HTTP 503 Service Unavailable atau response fallback) tanpa mengirim trafik ke downstream. Hal ini memberi waktu bagi downstream untuk memulihkan diri.
* **State HALF-OPEN**: Setelah durasi *sleep window* (misal: 15 detik) tercapai, circuit beralih ke HALF-OPEN. Sistem mengizinkan sebagian kecil trafik percobaan (*canary request*) masuk ke downstream. Jika berhasil, state kembali ke CLOSED. Jika gagal, state kembali ke OPEN.

---

## 4. Why & What

| Dimensi | Kode Kelas Pemula (*Localhost Mindset*) | Arsitektur Produksi (*Enterprise Mindset*) |
| :--- | :--- | :--- |
| **Kopling Komponen** | Database query ditulis langsung di dalam route handler Express. | Arsitektur Heksagonal; Core Domain terisolasi dari database melalui Interfaces (*Dependency Inversion*). |
| **Penanganan Error** | Menangkap error via `try/catch` lokal, mengembalikan string error mentah ke client (`res.send(err.message)`). | *Centralized Error Handling* dengan klasifikasi error (Domain Error, Operational Error, Bug), masking detail sensitif, dan log terstruktur. |
| **Downstream Outage** | Aplikasi hang menunggu timeout default (bisa sampai 2 menit), menghabiskan resources memori dan socket. | Penerapan *Circuit Breaker*, *Timeouts* ketat (misal: 2000ms), dan *Exponential Backoff with Full Jitter*. |
| **Manajemen Koneksi** | Membuka koneksi baru per request atau pooling tanpa limitasi, menyebabkan `FATAL: too many connections`. | Tuning koneksi pool berbasis formula matematis beban kerja, auto-reaping koneksi *idle*, dan *liveness validation*. |
| **Siklus Hidup (Lifecycle)**| Mematikan proses langsung dengan `kill -9` atau `Ctrl+C`. Request yang sedang berjalan langsung terputus corrupt. | *Graceful Shutdown* (`SIGTERM`/`SIGINT`), menolak request baru, menuntaskan request yang *in-flight*, flush logs, dan menutup pool secara bersih. |
| **Visibilitas Sistem** | `console.log("Error disini")` yang tidak terindeks dan sulit dilacak pada skala banyak server. | *Structured JSON Logging* berkorelasi dengan `trace_id` OpenTelemetry, metrik Prometheus (RED), dan Distributed Tracing. |

---

## 5. How (Workflow Detail)

Alur penanganan HTTP Request enterprise-grade dirancang berlapis dari perimeter network hingga ke persistensi:

```
[Client Request]
       |
       v
[1. Reverse Proxy / Gateway] -> (Rate Limiting Perimeter, SSL Termination, Correlation ID Injection)
       |
       v
[2. Transport Layer (HTTP Adapter)]
       |---> Parsing headers, inject Tracing Context (traceparent / x-correlation-id)
       |---> Route matching & Inbound schema validation (Zod / Joi)
       |
       v
[3. Security & Operational Middleware]
       |---> Authentication token parsing & RBAC authorization
       |---> Application Rate Limiter (Token Bucket per IP/User)
       |
       v
[4. Application Service / Use Case (Input Port)]
       |---> Start database unit-of-work / transaction
       |---> Load domain state via Outbound Ports
       |
       v
[5. Resilient Outbound Adapter]
       |---> Circuit Breaker Check (OPEN -> Fast Fail)
       |---> HTTP Call / Query Execution (Timeout context applied)
       |---> Failure Retry (Exponential Backoff with Full Jitter)
       |
       v
[6. Domain Mutation & Business Logic Evaluation]
       |---> Invariant validation (Pure business rules)
       |
       v
[7. Persistence & Event Dispatch]
       |---> Commit Database Transaction
       |---> Emit Domain Events (Transactional Outbox Pattern)
       |
       v
[8. Inbound Response Transformer]
       |---> Transform Domain Result to DTO
       |---> Record RED Metrics (Duration, Status Code, Path)
       |---> Emit Structured Access Log (JSON)
       |
       v
[HTTP Response Delivered]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Kapal Selam Modern (*Watertight Bulkhead Compartments*)
Aplikasi backend produksi diibaratkan seperti lambung kapal selam modern. Ketika terjadi kebocoran (downstream API error atau database spike), kapal selam tidak boleh langsung tenggelam seluruhnya. Pintu sekat kedap air (*watertight bulkheads* = **Circuit Breakers**) akan tertutup secara otomatis untuk mengisolasi kompartemen yang bocor, menjaga kapal tetap terapung dan sistem kemudi utama tetap berfungsi normal.

### Diagram Arsitektur Runtime & Isolation Boundary

```
+------------------------------------------------------------------------------------+
| OS / CONTAINER POD (KUBERNETES / DOCKER)                                           |
|                                                                                    |
|  Signals: [SIGTERM] -------------------------------> Graceful Shutdown Coordinator |
|                                                              |                     |
|  +-----------------------------------------------------------|------------------+  |
|  | BACKEND APPLICATION INSTANCE                              |                  |  |
|  |                                                           v                  |  |
|  |  +------------------------------------------------------------------------+  |  |
|  |  | HTTP Server Engine (Fastify / Express / Native HTTP)                   |  |  |
|  |  |                                                                        |  |  |
|  |  |  [Incoming HTTP]                                                       |  |  |
|  |  |         |                                                              |  |  |
|  |  |         v                                                              |  |  |
|  |  |  [Correlation Middleware] (Injects Correlation ID & Request Timer)    |  |  |
|  |  |         |                                                              |  |  |
|  |  |         v                                                              |  |  |
|  |  |  [Rate Limiter (Token Bucket)]                                         |  |  |
|  |  |         |                                                              |  |  |
|  |  |         +--- Allowed? --- NO ---> [HTTP 429 Too Many Requests]         |  |  |
|  |  |         | YES                                                          |  |  |
|  |  |         v                                                              |  |  |
|  |  |  +------------------------------------------------------------------+  |  |  |
|  |  |  | Use Case Execution (Application Layer)                          |  |  |  |
|  |  |  |                                                                  |  |  |  |
|  |  |  |  +------------------------------------------------------------+  |  |  |  |
|  |  |  |  | Outbound Resilience Boundary (Circuit Breaker)            |  |  |  |  |
|  |  |  |  |                                                            |  |  |  |  |
|  |  |  |  |  [Postgres Pool]                   [External HTTP Client]  |  |  |  |  |
|  |  |  |  |   Max: 20 | Idle: 5                 Timeout: 2000ms        |  |  |  |  |
|  |  |  |  |   Acquire Timeout: 3000ms           Retry: Exp. Backoff    |  |  |  |  |
|  |  |  |  +------------------------------------------------------------+  |  |  |  |
|  |  |  +------------------------------------------------------------------+  |  |  |
|  |  |         |                                                              |  |  |
|  |  |         v                                                              |  |  |
|  |  |  [Global Error Boundary] (Masking DB errors, Format RFC 7807)          |  |  |
|  |  |         |                                                              |  |  |
|  |  |         v                                                              |  |  |
|  |  |  [Metrics & Structured Logging] (Emit Prometheus & JSON logs)         |  |  |
|  |  +------------------------------------------------------------------------+  |  |
|  +------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Graceful Shutdown Pattern (Node.js)

Contoh dasar implementasi intersepsi sinyal OS untuk mencegah *socket dropping* saat proses dihentikan:

```typescript
// simple-graceful-shutdown.ts
import http from 'http';

const server = http.createServer((req, res) => {
  if (req.url === '/work') {
    // Simulasi pekerjaan komputasi/database selama 3 detik
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'completed' }));
    }, 3000);
    return;
  }
  res.writeHead(404);
  res.end();
});

server.listen(3000, () => {
  console.log('Server berjalan pada port 3000. PID:', process.pid);
});

function shutdown(signal: string) {
  console.log(`Menerima sinyal ${signal}. Memulai proses graceful shutdown...`);

  // 1. Berhenti menerima koneksi baru
  server.close((err) => {
    if (err) {
      console.error('Terjadi error saat menutup server HTTP:', err);
      process.exit(1);
    }
    console.log('Semua in-flight request telah selesai. Server HTTP ditutup.');
    process.exit(0);
  });

  // 2. Force termination jika proses terhambat melampaui ambang batas waktu (Deadlock safety)
  setTimeout(() => {
    console.error('Shutdown melebihi batas waktu 10 detik. Memaksa penghentian proses.');
    process.exit(1);
  }, 10000).unref(); // unref agar timer ini tidak menahan Node.js event loop
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
```

---

### 7.2 Practical Enterprise Example: Complete Production-Grade Resilient Service

Implementasi arsitektur produksi menggunakan **TypeScript** yang mencakup:
1. Port & Adapter Isolation.
2. Production-tuned PostgreSQL Connection Pool (`pg`).
3. Resilient HTTP Client dengan Exponential Backoff + Jitter & Circuit Breaker.
4. Structured Logger dengan Contextual Tracing.
5. Production Graceful Shutdown Coordinator.

#### Dependensi yang Dibutuhkan (`package.json`):
```json
{
  "name": "resilient-production-service",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "pg": "^8.11.3",
    "uuid": "^9.0.1"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/pg": "^8.11.0",
    "@types/uuid": "^9.0.8",
    "typescript": "^5.3.3"
  }
}
```

#### Struktur Proyek:
```text
src/
├── domain/
│   └── payment.ts
├── infrastructure/
│   ├── database/
│   │   └── postgres-pool.ts
│   ├── external/
│   │   └── circuit-breaker.ts
│   │   └── payment-gateway-client.ts
│   └── logging/
│       └── logger.ts
└── app.ts
```

#### A. Domain Core (Zero External Dependencies)
```typescript
// src/domain/payment.ts

export interface PaymentRequest {
  readonly id: string;
  readonly orderId: string;
  readonly amountInCents: number;
  readonly currency: 'IDR' | 'USD';
  readonly customerId: string;
}

export interface PaymentResult {
  readonly transactionId: string;
  readonly status: 'SETTLED' | 'DECLINED' | 'FAILED';
  readonly processedAt: Date;
}

// Inbound Port
export interface ProcessPaymentUseCase {
  execute(command: PaymentRequest, traceId: string): Promise<PaymentResult>;
}

// Outbound Port (SPI)
export interface PaymentGatewayPort {
  charge(payment: PaymentRequest, traceId: string): Promise<{ gatewayRefId: string; success: boolean }>;
}

// Outbound Port (Repository)
export interface PaymentRepositoryPort {
  saveTransaction(payment: PaymentRequest, result: PaymentResult, traceId: string): Promise<void>;
}
```

#### B. Observability: Structured Logger
```typescript
// src/infrastructure/logging/logger.ts

export interface LogContext {
  traceId?: string;
  [key: string]: unknown;
}

export class StructuredLogger {
  private formatLog(level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG', message: string, context?: LogContext): string {
    return JSON.stringify({
      timestamp: new Date().toISOString(),
      level,
      message,
      environment: process.env.NODE_ENV || 'production',
      ...context,
    });
  }

  info(message: string, context?: LogContext): void {
    process.stdout.write(this.formatLog('INFO', message, context) + '\n');
  }

  warn(message: string, context?: LogContext): void {
    process.stdout.write(this.formatLog('WARN', message, context) + '\n');
  }

  error(message: string, error?: Error, context?: LogContext): void {
    const errorDetails = error
      ? {
          errorName: error.name,
          errorMessage: error.message,
          stackTrace: error.stack,
        }
      : {};

    process.stderr.write(
      this.formatLog('ERROR', message, { ...context, ...errorDetails }) + '\n'
    );
  }
}

export const logger = new StructuredLogger();
```

#### C. Resiliency: Circuit Breaker Pattern
```typescript
// src/infrastructure/external/circuit-breaker.ts

import { logger } from '../logging/logger';

export enum CircuitState {
  CLOSED = 'CLOSED',
  OPEN = 'OPEN',
  HALF_OPEN = 'HALF_OPEN',
}

interface CircuitBreakerOptions {
  failureThreshold: number; // Jumlah kegagalan berturut-turut untuk trigger OPEN
  resetTimeoutMs: number;    // Durasi cooldown saat OPEN sebelum uji HALF-OPEN
  monitorTimeoutMs: number;  // Request timeout internal
}

export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;

  constructor(
    private readonly name: string,
    private readonly options: CircuitBreakerOptions = {
      failureThreshold: 5,
      resetTimeoutMs: 10000,
      monitorTimeoutMs: 3000,
    }
  ) {}

  public async execute<T>(action: () => Promise<T>, traceId: string): Promise<T> {
    this.evaluateState();

    if (this.state === CircuitState.OPEN) {
      logger.warn(`Circuit [${this.name}] is OPEN. Fast-failing request immediately.`, { traceId });
      throw new Error(`CircuitBreaker '${this.name}' is OPEN. Remote service temporarily unavailable.`);
    }

    try {
      const result = await this.executeWithTimeout(action, this.options.monitorTimeoutMs);
      this.onSuccess();
      return result;
    } catch (err: unknown) {
      this.onFailure(err as Error, traceId);
      throw err;
    }
  }

  private evaluateState(): void {
    if (this.state === CircuitState.OPEN) {
      const elapsed = Date.now() - this.lastFailureTime;
      if (elapsed >= this.options.resetTimeoutMs) {
        this.state = CircuitState.HALF_OPEN;
        logger.info(`Circuit [${this.name}] shifted to HALF-OPEN. Testing downstream availability.`);
      }
    }
  }

  private onSuccess(): void {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  private onFailure(err: Error, traceId: string): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    logger.error(`Circuit [${this.name}] registered failure (${this.failureCount}/${this.options.failureThreshold})`, err, { traceId });

    if (this.failureCount >= this.options.failureThreshold || this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
      logger.error(`Circuit [${this.name}] TRIPPED TO OPEN! Incoming requests will be blocked.`, undefined, { traceId });
    }
  }

  private executeWithTimeout<T>(action: () => Promise<T>, timeoutMs: number): Promise<T> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`Operation timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      action()
        .then((result) => {
          clearTimeout(timer);
          resolve(result);
        })
        .catch((err) => {
          clearTimeout(timer);
          reject(err);
        });
    });
  }

  public getState(): CircuitState {
    return this.state;
  }
}
```

#### D. Outbound Infrastructure: PostgreSQL Connection Pool dengan Tuning
```typescript
// src/infrastructure/database/postgres-pool.ts

import { Pool, PoolConfig } from 'pg';
import { logger } from '../logging/logger';

const poolConfig: PoolConfig = {
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432', 10),
  database: process.env.DB_NAME || 'enterprise_db',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  
  // Enterprise Sizing Configuration
  max: 20,                       // Batas maksimal koneksi aktif dalam pool
  min: 4,                        // Jumlah minimum koneksi idle yang selalu dijaga
  idleTimeoutMillis: 30000,      // Waktu koneksi idle sebelum di-reap oleh pool
  connectionTimeoutMillis: 3000, // Durasi maksimal menunggu koneksi tersedia (mencegah thread hanging)
  maxUses: 7500,                 // Menutup dan merefresh koneksi setelah dipakai 7500 kali (mencegah memory leak DB driver)
};

export const pgPool = new Pool(poolConfig);

pgPool.on('error', (err) => {
  logger.error('Unexpected idle client error in PostgreSQL pool', err);
});

pgPool.on('connect', () => {
  logger.info('Database client connection established');
});
```

#### E. Resilient HTTP Gateway Client dengan Exponential Backoff + Jitter
```typescript
// src/infrastructure/external/payment-gateway-client.ts

import { PaymentGatewayPort, PaymentRequest } from '../../domain/payment';
import { CircuitBreaker } from './circuit-breaker';
import { logger } from '../logging/logger';

export class ResilientPaymentGatewayAdapter implements PaymentGatewayPort {
  private circuitBreaker: CircuitBreaker;

  constructor() {
    this.circuitBreaker = new CircuitBreaker('ExternalPaymentGateway', {
      failureThreshold: 3,
      resetTimeoutMs: 5000,
      monitorTimeoutMs: 2000,
    });
  }

  public async charge(payment: PaymentRequest, traceId: string): Promise<{ gatewayRefId: string; success: boolean }> {
    return this.circuitBreaker.execute(async () => {
      return await this.callWithBackoffAndJitter(payment, 3, traceId);
    }, traceId);
  }

  private async callWithBackoffAndJitter(
    payment: PaymentRequest,
    retriesLeft: number,
    traceId: string
  ): Promise<{ gatewayRefId: string; success: boolean }> {
    try {
      return await this.mockNetworkPaymentCall(payment);
    } catch (err: unknown) {
      const error = err as Error;
      if (retriesLeft <= 0) {
        throw error;
      }

      // Algoritma: Full Jitter Exponential Backoff
      // Base backoff = 200ms, Multiplier = 2^attempt
      const attempt = 3 - retriesLeft;
      const baseDelay = 200 * Math.pow(2, attempt);
      // Full jitter: Random interval antara 0 dan baseDelay
      const jitteredDelay = Math.floor(Math.random() * baseDelay);

      logger.warn(`Gateway call failed. Retrying in ${jitteredDelay}ms. Retries left: ${retriesLeft}`, {
        traceId,
        attempt,
        error: error.message,
      });

      await new Promise((resolve) => setTimeout(resolve, jitteredDelay));
      return this.callWithBackoffAndJitter(payment, retriesLeft - 1, traceId);
    }
  }

  private async mockNetworkPaymentCall(payment: PaymentRequest): Promise<{ gatewayRefId: string; success: boolean }> {
    // Simulasi kegagalan acak jaringan downstream (30% kegagalan)
    if (Math.random() < 0.3) {
      throw new Error('Downstream Network Gateway ECONNRESET');
    }

    return {
      gatewayRefId: `GW-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      success: true,
    };
  }
}
```

#### F. Outbound Adapter: PostgreSQL Repository
```typescript
// src/infrastructure/database/payment-repository.ts

import { PaymentRepositoryPort, PaymentRequest, PaymentResult } from '../../domain/payment';
import { Pool } from 'pg';
import { logger } from '../logging/logger';

export class PostgresPaymentRepository implements PaymentRepositoryPort {
  constructor(private readonly pool: Pool) {}

  async saveTransaction(payment: PaymentRequest, result: PaymentResult, traceId: string): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      const queryText = `
        INSERT INTO payment_transactions (
          id, order_id, customer_id, amount_cents, currency, status, processed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      `;

      await client.query(queryText, [
        result.transactionId,
        payment.orderId,
        payment.customerId,
        payment.amountInCents,
        payment.currency,
        result.status,
        result.processedAt,
      ]);

      await client.query('COMMIT');
      logger.info('Payment transaction persisted successfully', { traceId, txId: result.transactionId });
    } catch (error) {
      await client.query('ROLLBACK');
      logger.error('Failed to persist payment transaction. Transaction rolled back.', error as Error, { traceId });
      throw error;
    } finally {
      client.release(); // Sangat krusial untuk mencegah pool exhaustion!
    }
  }
}
```

#### G. Core Use Case (Application Orchestrator)
```typescript
// src/domain/process-payment-use-case.ts

import { PaymentRequest, PaymentResult, ProcessPaymentUseCase, PaymentGatewayPort, PaymentRepositoryPort } from './payment';
import { logger } from '../infrastructure/logging/logger';

export class PaymentService implements ProcessPaymentUseCase {
  constructor(
    private readonly gateway: PaymentGatewayPort,
    private readonly repository: PaymentRepositoryPort
  ) {}

  async execute(command: PaymentRequest, traceId: string): Promise<PaymentResult> {
    logger.info('Processing payment command in domain core', { traceId, orderId: command.orderId });

    // Business Invariant Validation
    if (command.amountInCents <= 0) {
      throw new Error('Business Invariant Violated: Payment amount must be strictly positive.');
    }

    // Call Outbound Port (Resilient Gateway Adapter)
    const gatewayResponse = await this.gateway.charge(command, traceId);

    const result: PaymentResult = {
      transactionId: gatewayResponse.gatewayRefId,
      status: gatewayResponse.success ? 'SETTLED' : 'DECLINED',
      processedAt: new Date(),
    };

    // Save transaction state
    await this.repository.saveTransaction(command, result, traceId);

    return result;
  }
}
```

#### H. Transport & Entrypoint Runtime dengan Graceful Shutdown
```typescript
// src/app.ts

import http from 'http';
import { v4 as uuidv4 } from 'uuid';
import { pgPool } from './infrastructure/database/postgres-pool';
import { ResilientPaymentGatewayAdapter } from './infrastructure/external/payment-gateway-client';
import { PostgresPaymentRepository } from './infrastructure/database/payment-repository';
import { PaymentService } from './domain/process-payment-use-case';
import { logger } from './infrastructure/logging/logger';
import { PaymentRequest } from './domain/payment';

// Composition Root (Wiring dependencies manually - Inversion of Control)
const gatewayAdapter = new ResilientPaymentGatewayAdapter();
const repoAdapter = new PostgresPaymentRepository(pgPool);
const paymentUseCase = new PaymentService(gatewayAdapter, repoAdapter);

let isShuttingDown = false;

const server = http.createServer(async (req, res) => {
  const traceId = (req.headers['x-trace-id'] as string) || uuidv4();

  // Rejection barrier during shutdown phase
  if (isShuttingDown) {
    res.writeHead(503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Server is shutting down. Request rejected.' }));
    return;
  }

  // Health check probes for Kubernetes / Load Balancer
  if (req.url === '/health/ready' && req.method === 'GET') {
    try {
      // Validasi koneksi database masih hidup
      await pgPool.query('SELECT 1');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'READY' }));
    } catch {
      res.writeHead(503, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'UNREADY_DB_DOWN' }));
    }
    return;
  }

  if (req.url === '/api/v1/payments' && req.method === 'POST') {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body) as PaymentRequest;
        const result = await paymentUseCase.execute(payload, traceId);

        res.writeHead(201, {
          'Content-Type': 'application/json',
          'X-Trace-Id': traceId,
        });
        res.end(JSON.stringify(result));
      } catch (err: unknown) {
        const error = err as Error;
        logger.error('Unhandled request execution error', error, { traceId });

        res.writeHead(500, {
          'Content-Type': 'application/json',
          'X-Trace-Id': traceId,
        });
        res.end(JSON.stringify({ error: 'Internal Server Error', message: error.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end();
});

const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  logger.info(`Enterprise Resilient Application listening on port ${PORT}`);
});

// Production Graceful Shutdown Coordinator
async function handleGracefulShutdown(signal: string) {
  if (isShuttingDown) return;
  isShuttingDown = true;

  logger.warn(`Termination signal [${signal}] received. Initiating zero-downtime shutdown sequence.`);

  // 1. Matikan listeners HTTP untuk memutus aliran traffic baru
  server.close(async (httpErr) => {
    if (httpErr) {
      logger.error('Error occurred during HTTP server closure', httpErr);
    } else {
      logger.info('HTTP server stopped receiving incoming connections.');
    }

    try {
      // 2. Tutup Database Pool secara tertib (menunggu query yang sedang berjalan)
      logger.info('Draining database connection pool...');
      await pgPool.end();
      logger.info('Database pool drained successfully.');

      logger.info('Graceful shutdown completed. Exiting process safely.');
      process.exit(0);
    } catch (drainErr) {
      logger.error('Error during resource teardown', drainErr as Error);
      process.exit(1);
    }
  });

  // 3. Failsafe Hard-Timeout (Apabila query atau koneksi menggantung)
  setTimeout(() => {
    logger.error('Graceful shutdown timeout exceeded (15s limit). Forcing immediate termination!');
    process.exit(1);
  }, 15000).unref();
}

process.on('SIGTERM', () => handleGracefulShutdown('SIGTERM'));
process.on('SIGINT', () => handleGracefulShutdown('SIGINT'));
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: "KilatPay" Payment Engine & Flash Sale Downstream Collapse

#### Profil Beban
* **Event**: Flash Sale Harbolnas 12.12.
* **Volume**: 25.000 transaksi pembayaran per detik (Peak RPS).
* **Dependensi Eksternal**: API Bank Swasta Nasional (Third-party Core Banking).

#### Insiden (Root Cause Failure)
Pada menit ke-3 Flash Sale, database backend bank mitra mengalami konkurensi deadlock. Response time API Bank membengkak dari 150ms menjadi 18.000ms (18 detik), sebelum akhirnya mengembalikan HTTP 504 Gateway Timeout.

#### Efek Domino Kegagalan (*Cascading Meltdown*)
Aplikasi backend internal KilatPay yang belum menerapkan arsitektur resilient mengalami hal berikut:
1. Ribuan request pengguna tertahan di lapisan HTTP handler selama 18 detik menunggu downstream.
2. Connection pool backend habis terkuras (*Pool Exhaustion*) karena koneksi database dipegang terlalu lama menunggu response API Bank sebelum transaksi di-commit.
3. Event loop thread pool Node.js kehabisan *file descriptors* untuk membuka koneksi soket baru.
4. Kubernetes mendeteksi server backend tidak merespons *Liveness Probe*, lalu me-restart seluruh Pod backend secara massal (*CrashLoopBackOff*).
5. Seluruh ekosistem payment down total selama 90 menit dengan kerugian estimasi mencapai miliaran rupiah.

#### Solusi Arsitektur Produksi yang Diimplementasikan
1. **Pemisahan Boundary Database & External API**:
   API call ke pihak luar tidak boleh dieksekusi di dalam blok transaksi database aktif (`BEGIN ... COMMIT`). Transaksi dibuka hanya untuk mencatat status `PENDING`, koneksi pool segera dilepas, baru API bank dipanggil di luar transaksi.
2. **Circuit Breaker Integration**:
   Menerapkan Circuit Breaker pada level adapter bank dengan ambang batas: Jika 20 request berturut-turut mengalami response time > 2000ms atau HTTP 5xx, sirkuit langsung OPEN.
3. **Graceful Fallback & Queuing**:
   Ketika sirkuit OPEN, backend tidak mengembalikan error 500 ke pembeli, melainkan status `TRANSACTION_QUEUED` dan melempar pesan ke Apache Kafka dengan Retry Topic terisolasi.
4. **Exponential Backoff with Full Jitter**:
   Mekanisme retry background worker tidak membombardir bank secara bersamaan (*anti-thundering-herd*).

---

## 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Arsitektur Kode** | *Active Record / Anemic MVC* (Query di Controller/Model) | *Hexagonal Architecture* (Ports & Adapters) | Opsi A sangat cepat dikembangkan pada tahap awal (*rapid prototyping*), namun menghasilkan *technical debt* masif dan mustahil di-unit test secara terisolasi. Opsi B membutuhkan *boilerplate code* tinggi, namun memberikan kemudahan pengujian (*testability*), modularitas, dan proteksi domain core jangka panjang. |
| **Circuit Breaker** | Agresif (*Threshold Rendah, misal: 3 kegagalan*) | Konservatif (*Threshold Tinggi, misal: 25 kegagalan*) | Ambang batas agresif mencegah downstream kelebihan beban dan melindungi latensi aplikasi, namun rentan mengalami *false positive* (sirkuit trip akibat fluktuasi minor). Ambang konservatif mencegah salah deteksi, namun memperbesar risiko kehabisan pool connection lokal saat downstream melambat. |
| **Log Granularity** | *Verbose Debug Logging* (Mencatat seluruh request/response payload) | *Structured Contextual Log* (Trace ID, Error Stack, Metadata esensial) | Verbose logging mempermudah investigasi bug edge-case, namun menyebabkan disk I/O bottleneck masif, lonjakan biaya platform logging (Datadog/Elastic), serta risiko kebocoran data sensitif (PII/PCI-DSS). Structured Contextual jauh lebih efisien dan aman. |
| **Database Connection Pool** | *Large Pool Size* (misal: 100 per container instance) | *Calculated Sized Pool* (misal: 15–25 per container instance) | Menambah connection pool melebihi batas kemampuan core CPU database host tidak menaikkan throughput, melainkan menghabiskan resource pada *context switching* PostgreSQL backend processes dan memicu konkurensi lock overhead. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Database Connection Leak (*Hanging Connection*)
* **Gejala**: Aplikasi berjalan mulus selama 20 menit, lalu tiba-tiba seluruh endpoint timeout dengan error `error: timeout exceeded when trying to connect`.
* **Akar Masalah**: Mengambil koneksi secara manual via `pool.connect()` tanpa blok `finally { client.release(); }`. Ketika terjadi error di tengah query, koneksi tidak dikembalikan ke pool.
* **Solusi**: Selalu bungkus eksekusi query client dalam blok `try ... finally` atau gunakan abstraction helper wrapper yang menangani release secara otomatis.

### 2. The Thundering Herd Problem (Retry Storm)
* **Gejala**: Ketika service downstream pulih dari gangguan, service tersebut langsung down kembali dalam hitungan detik.
* **Akar Masalah**: Pola retry menggunakan interval statis (misal: semua client retry tepat pada detik ke-5). Ribuan worker membombardir downstream secara simultan pada milidetik yang sama.
* **Solusi**: Wajib menambahkan **Jitter** (variasi acak acak) pada perhitungan durasi backoff:
  $$\text{Delay} = \text{Random}(0, \text{Base} \times 2^{\text{Attempt}})$$

### 3. Sinyal SIGTERM Diabaikan di Docker Container
* **Gejala**: Saat deployment baru di-rollout, perintah restart memakan waktu tepat 10 atau 30 detik (*Docker kill timeout*) dan request yang sedang berjalan putus secara paksa dengan error `502 Bad Gateway`.
* **Akar Masalah**: Entrypoint Dockerfile ditulis menggunakan shell syntax: `ENTRYPOINT npm start`. Shell (`/bin/sh`) bertindak sebagai PID 1 dan secara default **tidak meneruskan sinyal POSIX** (`SIGTERM`) ke *child process* (Node.js/Go).
* **Solusi**: Gunakan format exec array langsung di Dockerfile: `ENTRYPOINT ["node", "dist/app.js"]` atau gunakan lightweight init manager seperti `tini`.

---

## 11. Best Practices (Production Checklist)

### Checklist Arsitektur & Resiliency
- [ ] Logika domain core sama sekali tidak memiliki impor dependensi pihak ketiga atau framework HTTP.
- [ ] Semua panggilan eksternal jaringan (HTTP/gRPC/Third-party) memiliki batas timeout ketat (maksimal 2000–3000ms, bukan default OS 120s).
- [ ] Circuit Breaker membungkus seluruh dependensi eksternal yang bersifat I/O intensif dan rentan mengalami cascading failures.
- [ ] Pola Exponential Backoff selalu diimplementasikan dengan **Full Jitter**.

### Checklist Database & Pooling
- [ ] Formula Pool Size dihitung berdasar kapasitas CPU server database:
  $$\text{MaxConnectionsPerInstance} \approx \frac{((\text{Core DB} \times 2) + \text{Effective Spindle Count})}{\text{Total Instance App}}$$
- [ ] Database client timeout diatur pada driver level: `statement_timeout`, `query_timeout`, dan `connectionTimeoutMillis`.
- [ ] Koneksi idle dibersihkan secara otomatis (`idleTimeoutMillis`).

### Checklist Observabilitas & Lifecycle
- [ ] Server mengimplementasikan endpoint `/health/live` (cek alokasi memori proses) dan `/health/ready` (cek status konektivitas pool database).
- [ ] Setiap incoming request diberikan `X-Correlation-ID` atau mengadopsi standar W3C `traceparent`.
- [ ] Log ditulis ke `stdout`/`stderr` dalam format JSON standar satu baris (*NDJSON*) untuk diindeks oleh Log Collector (FluentBit/Vector).
- [ ] Mekanisme Graceful Shutdown diuji secara nyata dengan pengiriman sinyal `SIGTERM`, memastikan tidak ada *dropped connection*.

---

## 12. Hands-on Practice

Buat dan simpan seluruh latihan praktikum ini di direktori: `hands-on/m02/`

### Langkah 1: Setup Proyek & Lingkungan Sandbox
Buka terminal dan eksekusi instruksi berikut:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node pg @types/pg uuid @types/uuid
npx tsc --init
```

### Langkah 2: Menjalankan Database PostgreSQL via Docker
Buat file `docker-compose.yml` di folder `hands-on/m02/`:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    container_name: m02-postgres
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
Jalankan kontainer:
```bash
docker compose up -d
```

### Langkah 3: Inisialisasi Skema Database
Buat file `init.sql`:
```sql
CREATE TABLE IF NOT EXISTS payment_transactions (
    id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    customer_id VARCHAR(64) NOT NULL,
    amount_cents BIGINT NOT NULL,
    currency VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```
Eksekusi ke dalam kontainer database:
```bash
docker exec -i m02-postgres psql -U enterprise_user -d enterprise_db < init.sql
```

### Langkah 4: Eksekusi Kode Praktikum
Salin seluruh implementasi dari bagian **7.2 Practical Enterprise Example** ke dalam file `hands-on/m02/server.ts`. 

Sesuaikan konfigurasi environment variable koneksi database:
```typescript
const poolConfig: PoolConfig = {
  host: 'localhost',
  port: 5432,
  database: 'enterprise_db',
  user: 'enterprise_user',
  password: 'enterprise_password',
  max: 10,
  min: 2,
  idleTimeoutMillis: 10000,
  connectionTimeoutMillis: 2000,
};
```

Jalankan server menggunakan `ts-node`:
```bash
npx ts-node server.ts
```

### Langkah 5: Menguji Resiliency & Circuit Breaker
Buka terminal baru, jalankan pengujian pembayaran:
```bash
curl -X POST http://localhost:8080/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: trace-abc-123" \
  -d '{
    "id": "pay-1",
    "orderId": "ord-999",
    "amountInCents": 150000,
    "currency": "IDR",
    "customerId": "cust-888"
  }'
```
Amati output log di terminal server. Perhatikan log retry ber-jitter dan amati bagaimana sirkuit berubah status ketika error tiruan downstream tercapai.

---

## 13. Exercise

### Level Easy
Modifikasi file `hands-on/m02/server.ts` untuk menambahkan endpoint `/health/live`. Endpoint ini harus memverifikasi penggunaan alokasi heap memori Node.js (`process.memoryUsage().heapUsed`). Jika alokasi heap melebihi 500MB, kembalikan HTTP 500; jika di bawah ambang tersebut, kembalikan HTTP 200.

### Level Medium
Tambahkan *sliding window log* pada implementasi `CircuitBreaker`. Alih-alih menghitung *consecutive failures* secara statis, sirkuit harus mengkalkulasi rasio persentase kegagalan: Jika dalam rentang waktu **60 detik terakhir**, terdapat **minimal 10 request** dan **rasio kegagalan mencapai $\ge 50\%$**, ubah status sirkuit menjadi OPEN.

### Level Hard
Implementasikan **Token Bucket Rate Limiting Middleware** murni tanpa modul pihak ketiga (in-memory) dengan ketentuan:
* Mampu menyimpan bucket per unique IP address.
* Kapasitas bucket = 10 token, laju pengisian ulang (*refill rate*) = 2 token per detik.
* Request yang melebihi kuota wajib di-reject dengan HTTP `429 Too Many Requests` disertai header standar `Retry-After`.
* Wajib memiliki mekanisme pembersihan (*eviction cleaner*) periodik untuk menghapus IP yang sudah tidak aktif lebih dari 10 menit agar tidak memicu memory leak.

---

## 14. Challenge

### Studi Kasus: "Zero Data-Loss Outbox Pattern Implementation"

Rancang arsitektur implementasi pola **Transactional Outbox Pattern** untuk mengatasi distributed dual-write problem.

#### Deskripsi Masalah:
Sistem Anda harus menyimpan data transaksi pembayaran ke PostgreSQL dan menerbitkan event `PaymentProcessed` ke Message Broker (misal: Apache Kafka / RabbitMQ). 
Jika DB commit berhasil tetapi broker jaringan putus saat publish event, data menjadi tidak sinkron (*ghost state*). Jika dibalik (publish event duluan sebelum DB commit), aplikasi bisa crash dan broker terlanjur menerima event dari data yang tidak pernah tersimpan di database.

#### Persyaratan Arsitektur Challenge:
1. Desain skema tabel `outbox_events` di database PostgreSQL yang sama dengan domain model, memastikan entitas transaksi dan event disimpan dalam satu transaksi atomik ACID (`BEGIN ... COMMIT`).
2. Rancang background worker (Relay Service) independen yang secara periodik mengekstrak data dari `outbox_events`, menerbitkannya ke broker eksternal, dan mengupdate status event menjadi `PROCESSED`.
3. Terapkan strategi konkurensi database locking (`SELECT ... FOR UPDATE SKIP LOCKED`) pada query worker agar worker dapat di-scale horizontal menjadi banyak pod tanpa mengalami race condition perebutan data event yang sama.
4. Buat dokumen arsitektur dan diagram sekuens (*Sequence Diagram*) yang membedah bagaimana sistem menangani kegagalan downstream message broker tanpa menghilangkan data satu kali pun (*At-least-once delivery guarantee*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Apa tujuan utama dari pemisahan Ports dan Adapters pada Arsitektur Heksagonal?**
   * A. Membuat framework mengeksekusi kode lebih cepat.
   * B. Mengisolasi core domain business rules agar tidak bergantung pada teknologi eksternal dan framework.
   * C. Menghilangkan kebutuhan untuk menulis unit test.
   * D. Mengizinkan koneksi database langsung tanpa driver.

2. **Sinyal POSIX standar yang dikirim oleh Kubernetes/Docker untuk memerintahkan container bersiap mati secara tertib adalah...**
   * A. `SIGKILL`
   * B. `SIGTERM`
   * C. `SIGSTOP`
   * D. `SIGHUP`

3. **Status Circuit Breaker yang mengizinkan sejumlah kecil traffic percobaan masuk setelah masa reset timeout berakhir disebut...**
   * A. CLOSED
   * B. TRIPPED
   * C. HALF-OPEN
   * D. ISOLATED

4. **Tujuan penambahan "Jitter" pada mekanisme Exponential Backoff adalah...**
   * A. Mengurangi jumlah memori heap aplikasi.
   * B. Mengacak waktu tunggu retry guna mencegah terjadinya Thundering Herd Problem pada downstream.
   * C. Memastikan koneksi database ditutup seketika.
   * D. Menjamin response HTTP diterima di bawah 100ms.

5. **Apa bahaya terbesar membiarkan koneksi database tidak dirilis (`client.release()`) setelah query selesai dieksekusi?**
   * A. Pool mengalami connection exhaustion sehingga seluruh request berikutnya hang dan timeout.
   * B. Data di tabel terhapus secara otomatis.
   * C. Kecepatan clock CPU server turun drastis.
   * D. Node.js otomatis melakukan compile ulang ke C++.

---

### Bagian 2: Intermediate (Pilihan Ganda)

6. **Mengapa pemanggilan API eksternal yang lambat TIDAK BOLEH diletakkan di dalam blok transaksi database aktif (`BEGIN ... COMMIT`)?**
   * A. Karena API eksternal secara otomatis membatalkan sintaks SQL.
   * B. Karena koneksi database dari pool ditahan selama proses tunggu jaringan eksternal, menghabiskan pool capacity dan memicu pool exhaustion massal.
   * C. Karena driver database tidak mendukung protokol HTTP.
   * D. Karena API eksternal akan membaca dirty data dari database secara otomatis.

7. **Bagaimana format logging yang wajib digunakan pada arsitektur backend cloud-native skala enterprise?**
   * A. Log teks mentah dengan format bebas menggunakan spasi bertingkat.
   * B. Structured JSON single-line (NDJSON) yang memuat metadata standar seperti timestamp ISO, level, trace_id, dan message.
   * C. Ditulis langsung ke file `.txt` lokal di dalam container container pod.
   * D. Format XML biner terkompresi.

8. **Pada strategi migrasi skema database Zero-Downtime "Expand and Contract", apa yang dilakukan pada fase "Expand"?**
   * A. Menghapus tabel lama dan menggantinya langsung dengan nama tabel baru.
   * B. Menambah kolom/tabel baru tanpa menghapus atau mengubah struktur lama, sehingga versi aplikasi lama dan baru dapat berjalan berdampingan secara simultan.
   * C. Melakukan kompresi hard disk storage engine database.
   * D. Menghentikan operasional database selama 3 jam untuk proses rebuild index.

9. **Jika Kubernetes mengirimkan sinyal `SIGTERM`, urutan aksi Graceful Shutdown yang benar pada backend API adalah...**
   * A. Bunuh proses seketika (`process.exit(0)`) -> flush logs -> tutup database.
   * B. Set status server unhealthy -> Stop accepting incoming traffic (`server.close()`) -> Tunggu in-flight requests selesai -> Tutup pool koneksi database -> Exit process.
   * C. Tutup database seketika -> Kirim HTTP 500 ke semua in-flight request -> Exit process.
   * D. Biarkan koneksi menggantung hingga Kubernetes mengirim `SIGKILL`.

10. **Metrik RED dalam observabilitas arsitektur backend modern merepresentasikan...**
    * A. Readability, Execution, Debugging.
    * B. Rate (throughput), Errors (jumlah request gagal), Duration (latensi/waktu eksekusi).
    * C. Relational, Enterprise, Deployment.
    * D. Resilience, Elasticity, Durability.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: The Zombie Socket Leak
* **Kasus**: Sebuah microservice berbasis Express dan PostgreSQL mengalami crash setiap 6 jam di environment staging dengan indikator error `Error: Connection terminated unexpectedly`. CPU dan memori terpantau normal. Setelah diteliti, jumlah koneksi di Postgres mencapai batas `max_connections = 100`.
* **Tugas Anda**: Identifikasi akar masalahnya, sebutkan dua query/command Postgres yang dapat digunakan untuk menganalisis connection state yang menggantung tersebut, dan jelaskan langkah perbaikan pada connection pool layer!

#### Skenario 2: The Cascading Timeout Disaster
* **Kasus**: Service A memanggil Service B via HTTP dengan timeout 10 detik. Service B memanggil Service C dengan timeout 10 detik. Service C mengalami degradasi (latensi rata-rata naik menjadi 9.5 detik). Pengguna di frontend mengeluhkan layar loading berputar sangat lama dan transaksi sering gagal.
* **Tugas Anda**: Analisis kesalahan desain distributed timeout di atas (*Timeout Budgeting*) dan tentukan rancangan deadline propagation yang benar agar Service A dan B tidak membuang resource secara sia-sia!

#### Skenario 3: Zero-Downtime Breaking Schema Change
* **Kasus**: Anda memiliki tabel `users` dengan kolom `full_name VARCHAR(255)`. Kebutuhan bisnis baru mewajibkan pemisahan data menjadi `first_name VARCHAR(100)` dan `last_name VARCHAR(150)`. Sistem melayani 5.000 query per detik tanpa toleransi downtime sama sekali.
* **Tugas Anda**: Uraikan 4 tahapan rinci menggunakan pola **Expand and Contract** untuk mengeksekusi migrasi skema ini tanpa kegagalan query pada aplikasi yang sedang berjalan!

---

### Kunci Jawaban Evaluasi

#### Kunci Jawaban Bagian 1: Basic
1. **B** — Mengisolasi core domain business rules agar tidak bergantung pada teknologi eksternal dan framework.
2. **B** — `SIGTERM`.
3. **C** — HALF-OPEN.
4. **B** — Mengacak waktu tunggu retry guna mencegah terjadinya Thundering Herd Problem pada downstream.
5. **A** — Pool mengalami connection exhaustion sehingga seluruh request berikutnya hang dan timeout.

#### Kunci Jawaban Bagian 2: Intermediate
6. **B** — Karena koneksi database dari pool ditahan selama proses tunggu jaringan eksternal, menghabiskan pool capacity dan memicu pool exhaustion massal.
7. **B** — Structured JSON single-line (NDJSON) yang memuat metadata standar seperti timestamp ISO, level, trace_id, dan message.
8. **B** — Menambah kolom/tabel baru tanpa menghapus atau mengubah struktur lama, sehingga versi aplikasi lama dan baru dapat berjalan berdampingan secara simultan.
9. **B** — Set status server unhealthy -> Stop accepting incoming traffic (`server.close()`) -> Tunggu in-flight requests selesai -> Tutup pool koneksi database -> Exit process.
10. **B** — Rate (throughput), Errors (jumlah request gagal), Duration (latensi/waktu eksekusi).

#### Kunci Jawaban Bagian 3: Skenario Kasus Produksi
* **Skenario 1**:
  * *Akar Masalah*: Koneksi pool bocor karena pemanggilan `pool.connect()` tanpa penutupan/pelepasan pada blok `finally { client.release(); }`, atau tidak diatur timeout batas tunggu koneksi idle.
  * *Query Analisis*: `SELECT pid, state, query_start, query FROM pg_stat_activity WHERE state = 'idle in transaction';` dan `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`.
  * *Solusi*: Atur parameter pool `idleTimeoutMillis` dan `connectionTimeoutMillis`, serta pastikan penggunaan abstraction library yang menjamin auto-release (atau wajib gunakan `try/finally`).
* **Skenario 2**:
  * *Akar Masalah*: Anti-pattern *Uniform Static Timeouts*. Total akumulasi latensi downstream mendekati atau melampaui timeout hulu, menyebabkan *wasted computation* (Service C masih bekerja keras memproses request padahal Service A sudah timeout duluan).
  * *Solusi*: Menerapkan **Timeout Budgeting & Context Propagation** (misal: Header `X-Request-Timeout` atau gRPC deadline). Jika Service A memiliki batas SLA 3 detik, ia mengirim batas waktu tersebut. Service B mengalokasikan hanya 1.5 detik ke Service C. Jika downstream melebihi budget, segera batalkan eksekusi downstream (*Cancel propagation*).
* **Skenario 3**:
  1. *Fase 1 (Expand)*: Tambahkan kolom baru `first_name` dan `last_name` yang bersifat *nullable* tanpa menghapus kolom `full_name`.
  2. *Fase 2 (Parallel Write)*: Deploy versi backend baru yang menulis ke dua sisi (*Dual Write*): menulis ke `first_name`, `last_name`, sekaligus tetap mengupdate `full_name`. Sistem membaca dari kolom baru dengan fallback ke kolom lama.
  3. *Fase 3 (Backfill)*: Jalankan background script data migrasi untuk memecah data lama dari `full_name` ke `first_name` & `last_name` pada seluruh baris data historis.
  4. *Fase 4 (Contract)*: Ubah constraint kolom baru menjadi `NOT NULL`, ubah aplikasi untuk 100% membaca/menulis hanya ke kolom baru, lalu hapus (*Drop*) kolom lama `full_name`.

---

## 16. Summary

1. **Clean/Hexagonal Architecture** menjamin keberlanjutan kode perangkat lunak jangka panjang dengan menjadikan logika bisnis sebagai pusat sistem, terisolasi penuh dari fluktuasi dependensi eksternal melalui abstraksi antarmuka (*Inversion of Control*).
2. **Resilience Engineering** bukan opsional dalam sistem terdistribusi. Penerapan **Circuit Breaker** membatasi *blast radius* kegagalan, sementara **Exponential Backoff dengan Full Jitter** mencegah kolapsnya downstream akibat *retry storms*.
3. **Database Connection Pool** merupakan sumber daya berharga yang terbatas secara fisik. Mengisolasi panggilan I/O jaringan eksternal dari blok transaksi database adalah aturan mutlak pencegahan *pool exhaustion*.
4. **Lifecycle Management** yang matang memastikan sistem beradaptasi dengan orkestrator kontainer modern. Penanganan sinyal OS `SIGTERM` secara tertib melalui **Graceful Shutdown** melindungi data dari korupsi dan menjamin nol koneksi terputus (*zero-downtime deployment*).
5. **Observabilitas Terstruktur** (*Structured Logging*, Contextual Tracing via `trace_id`, dan Metrik RED) adalah fondasi visibilitas yang membedakan aplikasi mainan lokal dengan sistem backend enterprise berdaya tahan tinggi.