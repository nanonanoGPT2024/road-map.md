# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Mendesain Arsitektur Backend Berlapis (*Clean / Layered Architecture*)**: Memisahkan *concern* antara Controller (Transport), Service (Domain Logic), Repository (Data Access), dan Data Transfer Object (DTO) secara terisolasi.
2. **Mengelola Transaksi Database Enterprise (*ACID & Isolation Levels*)**: Mengimplementasikan transaksi atomik multi-tabel menggunakan *Unit of Work* atau *Database Client Transaction Context* tanpa membocorkan koneksi (*connection leak*).
3. **Mengoptimalkan *Connection Pooling* & *Lifecycle***: Mengonfigurasi parameter *connection pool* (min, max, idle timeout, connection timeout) dan mengantisipasi *pool exhaustion* di bawah beban tinggi.
4. **Menerapkan *Zero-Downtime & Graceful Lifecycle Management***: Menulis mekanisme penanganan sinyal sistem operasi (`SIGTERM`, `SIGINT`) untuk menyelesaikan *in-flight requests*, menutup koneksi database, dan mematikan server secara terkendali.
5. **Membangun *Observability Baseline***: Mengintegrasikan *Structured JSON Logging* dengan propagasi konteks (*Correlation ID / Request ID* tracing) untuk memfasilitasi audit dan *distributed debugging*.
6. **Menerapkan Standardisasi Keamanan Produksi & *Resilience***: Mengonfigurasi *Rate Limiting*, proteksi *HTTP Headers* (Helmet), validasi payload berbasis skema ketat, serta pemeriksaan kesehatan (*Liveness & Readiness Probes*).

---

## 2. Prerequisite

Sebelum memulai modul ini, peserta wajib memahami:

- **Protokol HTTP/1.1 & HTTP/2**: Siklus *Request-Response*, *Status Codes*, *Headers*, dan *Keep-Alive*.
- **Dasar-dasar RDBMS**: Sintaks SQL standar (SELECT, INSERT, UPDATE, DELETE, JOIN), pembuatan indeks (*B-Tree*), serta konsep konkurensi data.
- **Runtime Asynchronous**: Konsep Event Loop, Promises, `async/await`, Thread Pool, dan manajemen *non-blocking I/O* pada backend runtime (khususnya Node.js/TypeScript atau Go).
- **TypeScript Intermediate**: Generics, Interfaces, Dependency Injection sederhana, Union Types, dan Type Narrowing.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Layered / Clean Architecture Internals

Pada aplikasi *monolithic* tingkat pemula, logika aplikasi sering kali dicampuradukkan di dalam *route handler* (*fat controller*). Pendekatan ini menyebabkan *coupling* yang tinggi, kesulitan pengujian (*unit testing*), serta risiko kebocoran logika basis data ke lapisan presentasi.

Arsitektur produksi membagi sistem ke dalam 4 lapisan independen:

```
[ HTTP / Client Layer ]
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Presentation / Controller Layer                         │
│    - Validasi payload (Schema Parsing)                      │
│    - Ekstraksi Headers, Query, Params, Context (Trace ID)   │
│    - Transformasi Domain Output -> HTTP Response Code       │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Calls Interfaces)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Domain / Business Service Layer                          │
│    - Pure Business Logic & State Transition Rules           │
│    - Orchestration antar entity                             │
│    - Transaction Boundaries (Unit of Work)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Calls Interfaces)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Data Access / Repository Layer                           │
│    - Abstraksi Query SQL / Engine Database                  │
│    - Mapping Raw Database Rows -> Domain Entity             │
│    - Menggunakan Database Connection / Transaction Client   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (SQL Driver over TCP)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Infrastructure / Database Storage Engine (RDBMS)         │
│    - WAL (Write-Ahead Logging), Buffer Pool, Locks, MVCC    │
└─────────────────────────────────────────────────────────────┘
```

Prinsip utama: **Arah dependensi selalu mengarah ke dalam (Inward Dependency Rule)**. Lapisan *Domain Service* tidak boleh bergantung pada objek `Request` atau `Response` dari *framework* HTTP (seperti Express, Fastify, atau Gin).

### 3.2. Database Connection Pool: Mekanisme & Bottlenecks

Membuat koneksi TCP baru ke database adalah operasi yang mahal (*costly*):
1. Three-way handshake TCP (SYN, SYN-ACK, ACK).
2. Negosiasi TLS/SSL jika diaktifkan.
3. Otentikasi dan alokasi memori proses backend di database (misalnya, Postgres mengalokasikan satu proses terpisah untuk setiap koneksi via `fork()`).

*Connection Pool* mengelola sekumpulan koneksi yang persisten dan siap pakai.

```
Incoming Request -> [ Acquire Connection ] -> [ Execute Query ] -> [ Release Connection ]
                           │                                               │
               Pool Available?                                  Kembalikan ke Queue Pool
             ├── Yes: Ambil koneksi
             └── No: Masuk Wait Queue (Jika timeout tercapai -> ErrPoolTimeout)
```

**Komponen Kritis Pool:**
- **Max Connections**: Batas atas jumlah soket koneksi yang dibuka ke database. Jika diatur terlalu tinggi, memori PostgreSQL/MySQL akan habis (*OOM Killer*). Jika terlalu rendah, *throughput* aplikasi terhambat.
- **Idle Timeout**: Waktu maksimum koneksi menganggur sebelum ditutup oleh pool untuk menghemat sumber daya.
- **Connection Timeout**: Waktu tunggu maksimum bagi *thread/task* untuk memperoleh koneksi dari pool sebelum melempar galat (*throw exception*).

### 3.3. Transaksi ACID, MVCC, dan Lock Contention

Ketika operasi bisnis melibatkan mutasi lebih dari satu tabel (contoh: Mengurangi saldo pengguna dan membuat entri mutasi rekening), kita wajib menggunakan transaksi database (`BEGIN ... COMMIT / ROLLBACK`).

- **Atomicity**: Seluruh mutasi berhasil, atau seluruh mutasi dibatalkan tanpa jejak parsial.
- **Consistency**: Data berpindah dari satu kondisi valid ke kondisi valid lainnya sesuai *constraints*.
- **Isolation**: Perubahan data oleh transaksi yang sedang berjalan tidak terlihat oleh transaksi konkuren lainnya hingga di-*commit*.
- **Durability**: Sekali transaksi berhasil di-*commit*, perubahan tersimpan permanen di *non-volatile storage* via WAL (*Write-Ahead Logging*).

**Isolation Levels & Gejala Anomali:**

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read | Serialization Anomaly |
| :--- | :---: | :---: | :---: | :---: |
| **Read Uncommitted** | Ya | Ya | Ya | Ya |
| **Read Committed** (Default PG) | Tidak | Ya | Ya | Ya |
| **Repeatable Read** | Tidak | Tidak | Ya (Bervariasi) | Ya |
| **Serializable** | Tidak | Tidak | Tidak | Tidak |

*Catatan: Semakin tinggi isolation level, semakin tinggi kemungkinan terjadinya Deadlock dan Serialization Failure yang menuntut mekanisme Retry.*

### 3.4. Graceful Shutdown Internals

Ketika *orchestrator* kontainer (seperti Kubernetes atau Docker Swarm) menghentikan sebuah Pod/Kontainer:
1. Kubernetes mengirimkan sinyal `SIGTERM` ke proses aplikasi PID 1.
2. Endpoint service Kubernetes secara bersamaan memperbarui iptables/IPVS untuk mencabut Pod dari daftar *load balancer endpoints*.
3. Aplikasi **harus**:
   - Berhenti menerima request HTTP baru (`server.close()`).
   - Menyelesaikan semua *in-flight requests* yang sedang diproses dalam batas toleransi waktu (*Grace Period*, misal: 10-30 detik).
   - Menutup transaksi yang belum selesai dan melepaskan koneksi database pool (`pool.end()`).
   - Keluar (*exit*) dengan status code 0.
4. Jika proses melewati ambang batas waktu (*terminationGracePeriodSeconds*), OS akan mengirimkan `SIGKILL` yang memaksa proses berhenti secara instan, memicu *dangling state* jika graceful shutdown gagal diimplementasikan.

---

## 4. Why & What

### Mengapa Ini Penting?
Aplikasi backend tingkat pemula sering kali berfungsi baik di lingkungan lokal (*localhost*) dengan pengguna tunggal, namun langsung mengalami kegagalan sistematis saat di-*deploy* ke produksi:
- **Crash Tak Terduga**: Kegagalan unhandled promise rejection yang mematikan *node process*.
- **Data Corruption**: Mutasi ganda atau pemotongan saldo tanpa pencatatan mutasi akibat ketiadaan transaksi basis data.
- **Connection Spikes / DB Crashes**: Setiap request membuka koneksi database baru tanpa pooling hingga batas `max_connections` database terlampaui.
- **Downtime Saat Deployment**: Penghentian proses secara paksa memutuskan koneksi klien yang sedang melakukan pembayaran di tengah jalan.

### Apa yang Dibangun?
Modul ini mentransformasikan arsitektur dasar menjadi arsitektur backend standar produksi yang mencakup:
1. Pemisahan tanggung jawab berbasis antarmuka (*Interface Segregation*).
2. Manajemen transaksi database yang terisolasi dalam konteks eksekusi.
3. Middleware observabilitas untuk melacak rantai pemanggilan (*Tracing via Correlation ID*).
4. Penanganan sinyal OS untuk pematian aplikasi nir-henti (*Zero-Downtime Graceful Shutdown*).
5. Standardisasi respon galat operasional versus galat sistem (*Operational vs Programmer Errors*).

---

## 5. How (Workflow Detail)

Berikut alur kerja siklus hidup sebuah request pada arsitektur produksi:

```
[Incoming HTTP Request]
          │
          ▼
[1. Request Tracking Middleware]
   ├── Ekstraksi 'X-Correlation-ID' atau generate UUIDv4 baru
   ├── Attach ID ke Async Context / Request Scope
   └── Inisialisasi High-Resolution Timer
          │
          ▼
[2. Security & Hardening Middleware]
   ├── Helmet (HSTS, CSP, X-Frame-Options)
   ├── CORS Validation
   └── IP/Token Rate Limiter (Token Bucket Algorithm)
          │
          ▼
[3. Presentation Controller]
   ├── Parsing payload dengan skema (Zod) -> Gagal: Return 400 Bad Request
   └── Memanggil Service Method dengan DTO yang bersih
          │
          ▼
[4. Domain Service (Business Logic)]
   ├── Menginisialisasi Transaction Context (Pool Client Reservation)
   ├── BEGIN Transaction
   ├── Memanggil Repo A (misal: Kurangi Saldo Akun Pengirim)
   ├── Memanggil Repo B (misal: Tambah Saldo Akun Penerima)
   ├── Memanggil Repo C (misal: Tulis Riwayat Audit Log)
   ├── COMMIT Transaction
   └── Menangkap Galat: ROLLBACK Transaction (Jika ada operasi gagal)
          │
          ▼
[5. Release Resources]
   └── Mengembalikan Pool Client ke Database Pool
          │
          ▼
[6. Structured Logging & Response Formatter]
   ├── Catat log HTTP: Method, Path, Status, Latency (ms), Correlation ID
   └── Kirim Response JSON yang seragam ke Klien
```

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran Bintang Lima

Bayangkan sebuah restoran berskala besar:
- **Client**: Pelanggan yang datang lapar.
- **Controller (Pelayan)**: Menerima pesanan, memeriksa apakah menu tersedia dan formatnya benar, menyajikan makanan kembali ke meja. Pelayan **tidak memasak**.
- **Service (Kepala Koki / Chef)**: Menentukan resep, alur memasak, memastikan urutan pembuatan hidangan sesuai standar gizi dan prosedur restoran.
- **Repository (Staf Gudang Bahan Baku)**: Hanya bertugas mengambil bahan mentah (daging, sayur) dari lemari pendingin atau rak penyimpanan. Staf gudang **tidak tahu** untuk menu apa bahan tersebut dimasak.
- **Connection Pool (Armada Troli Pengantar Gudang)**: Hanya ada 10 troli. Staf gudang harus meminjam troli, mengambil barang, dan langsung mengembalikannya agar staf lain bisa memakai. Jangan sampai troli dibawa pulang!
- **ACID Transaction**: Menyiapkan menu paket. Jika ayam goreng gosong, kentang dan minuman yang sudah disiapkan ditarik kembali; seluruh paket diganti baru atau dibatalkan total.

### Diagram Arsitektur Runtime & Graceful Interception

```
+-----------------------------------------------------------------------------------+
| RUNTIME PROCESS (Node.js Engine)                                                  |
|                                                                                   |
|  [ SIGTERM Signal ] ──> Intercepted by Process Signal Handler                     |
|                              │                                                    |
|                              ├─> 1. Set App State: isShuttingDown = true          |
|                              │      (/health/readiness returns HTTP 503)          |
|                              │                                                    |
|                              ├─> 2. server.close()                                |
|                              │      Stop accepting NEW TCP connections            |
|                              │                                                    |
|                              ├─> 3. Drain Existing HTTP Connections               |
|                              │      Wait for pending requests to finish           |
|                              │                                                    |
|                              ├─> 4. dbPool.end()                                  |
|                              │      Wait for active queries, close DB TCP sockets |
|                              │                                                    |
|                              └─> 5. process.exit(0)                               |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Graceful Shutdown Minimalist

Contoh dasar menangani pematian server secara bersih menggunakan pustaka inti Node.js.

```typescript
import http from 'node:http';

const server = http.createServer((req, res) => {
  if (req.url === '/work') {
    // Simulasi pekerjaan lambat selama 3 detik
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'completed' }));
    }, 3000);
    return;
  }

  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('OK\n');
});

const PORT = 3000;
server.listen(PORT, () => {
  console.log(`[HTTP] Server aktif pada port ${PORT}`);
});

function handleShutdown(signal: string) {
  console.log(`\n[SIGNAL] Menerima ${signal}. Memulai proses pematian bersih...`);

  // Menolak request baru, menunggu request aktif selesai
  server.close((err) => {
    if (err) {
      console.error('[SHUTDOWN] Terjadi kesalahan saat menutup server:', err);
      process.exit(1);
    }
    console.log('[SHUTDOWN] Seluruh request aktif telah selesai. Aplikasi berhenti dengan aman.');
    process.exit(0);
  });

  // Force close jika proses memakan waktu lebih dari 10 detik
  setTimeout(() => {
    console.error('[SHUTDOWN] Batas waktu 10 detik terlampaui. Memaksa pematian aplikasi!');
    process.exit(1);
  }, 10000).unref(); // unref agar timer ini tidak menahan event loop jika server.close selesai lebih awal
}

process.on('SIGTERM', () => handleShutdown('SIGTERM'));
process.on('SIGINT', () => handleShutdown('SIGINT'));
```

---

### 7.2. Practical Example: Enterprise Production Pattern (TypeScript + PostgreSQL Driver)

Berikut adalah implementasi sistem transfer saldo finansial yang menerapkan:
- Arsitektur Berlapis (Controller, Service, Repository)
- Transaksi Database Terisolasi (*Unit of Work / Transaction Client*)
- Validasi Input Berbasis Skema (Zod)
- Structured Logging dengan Correlation ID
- Graceful Shutdown

#### 7.2.1. Inisialisasi Database Pool (`src/infrastructure/database.ts`)

```typescript
import { Pool, PoolClient } from 'pg';

export const dbPool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT) || 5432,
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_NAME || 'fintech_db',
  max: 20, // Kapasitas maksimum koneksi bersamaan
  idleTimeoutMillis: 30000, // Tutup koneksi nganggur setelah 30 detik
  connectionTimeoutMillis: 5000, // Timeout akuisisi koneksi jika pool penuh
});

dbPool.on('error', (err) => {
  console.error('[DB_POOL_ERROR] Anomali pada koneksi idle database:', err);
});
```

#### 7.2.2. Repository Layer (`src/repositories/account.repository.ts`)

Repository menerima `PoolClient` agar dapat dieksekusi di dalam transaksi yang sama.

```typescript
import { PoolClient } from 'pg';

export interface AccountEntity {
  id: string;
  owner_name: string;
  balance: number;
  created_at: Date;
}

export class AccountRepository {
  /**
   * Mengambil data akun dengan row-level lock (FOR UPDATE)
   * Mencegah race-condition/lost update pada transaksi konkuren
   */
  async findByIdForUpdate(client: PoolClient, accountId: string): Promise<AccountEntity | null> {
    const query = `
      SELECT id, owner_name, balance, created_at
      FROM accounts
      WHERE id = $1
      FOR UPDATE;
    `;
    const result = await client.query<AccountEntity>(query, [accountId]);
    return result.rows[0] || null;
  }

  async updateBalance(client: PoolClient, accountId: string, newBalance: number): Promise<void> {
    const query = `
      UPDATE accounts
      SET balance = $1
      WHERE id = $2;
    `;
    await client.query(query, [newBalance, accountId]);
  }

  async recordLedger(
    client: PoolClient,
    entry: { fromAccountId: string; toAccountId: string; amount: number; referenceId: string }
  ): Promise<void> {
    const query = `
      INSERT INTO transfer_ledgers (from_account_id, to_account_id, amount, reference_id, created_at)
      VALUES ($1, $2, $3, $4, NOW());
    `;
    await client.query(query, [
      entry.fromAccountId,
      entry.toAccountId,
      entry.amount,
      entry.referenceId
    ]);
  }
}
```

#### 7.2.3. Service Layer (`src/services/transfer.service.ts`)

Mengendalikan *transaction boundary* dan *business rules*. Lapisan ini tidak mengetahui adanya Express `req` atau `res`.

```typescript
import { Pool } from 'pg';
import { AccountRepository } from '../repositories/account.repository';

export class AppError extends Error {
  constructor(public statusCode: number, message: string) {
    super(message);
    this.name = 'AppError';
  }
}

export interface TransferDTO {
  fromAccountId: string;
  toAccountId: string;
  amount: number;
  referenceId: string;
}

export class TransferService {
  constructor(
    private readonly pool: Pool,
    private readonly accountRepo: AccountRepository
  ) {}

  async executeTransfer(dto: TransferDTO, correlationId: string): Promise<{ success: boolean; txId: string }> {
    if (dto.fromAccountId === dto.toAccountId) {
      throw new AppError(400, 'Rekening asal dan tujuan transfer tidak boleh sama.');
    }

    if (dto.amount <= 0) {
      throw new AppError(400, 'Nominal transfer harus lebih besar dari 0.');
    }

    // Mengambil koneksi eksklusif dari pool untuk transaksi
    const client = await this.pool.connect();

    try {
      await client.query('BEGIN;');

      // Deadlock Prevention: Urutkan penguncian akun berdasarkan ID secara deterministik
      const accountsToLock = [dto.fromAccountId, dto.toAccountId].sort();
      
      const firstAccount = await this.accountRepo.findByIdForUpdate(client, accountsToLock[0]);
      const secondAccount = await this.accountRepo.findByIdForUpdate(client, accountsToLock[1]);

      if (!firstAccount || !secondAccount) {
        throw new AppError(404, 'Satu atau kedua entitas rekening tidak ditemukan.');
      }

      const sender = dto.fromAccountId === firstAccount.id ? firstAccount : secondAccount;
      const receiver = dto.toAccountId === firstAccount.id ? firstAccount : secondAccount;

      // Verifikasi Kecukupan Saldo
      if (sender.balance < dto.amount) {
        throw new AppError(422, `Saldo rekening asal (${sender.id}) tidak mencukupi untuk transfer.`);
      }

      // Kalkulasi Saldo Baru
      const newSenderBalance = sender.balance - dto.amount;
      const newReceiverBalance = receiver.balance + dto.amount;

      // Eksekusi Pembaruan State
      await this.accountRepo.updateBalance(client, sender.id, newSenderBalance);
      await this.accountRepo.updateBalance(client, receiver.id, newReceiverBalance);

      // Audit Log Finansial
      await this.accountRepo.recordLedger(client, {
        fromAccountId: sender.id,
        toAccountId: receiver.id,
        amount: dto.amount,
        referenceId: dto.referenceId,
      });

      await client.query('COMMIT;');

      console.log(JSON.stringify({
        level: 'INFO',
        correlationId,
        message: 'Transfer saldo berhasil diproses',
        details: { from: sender.id, to: receiver.id, amount: dto.amount }
      }));

      return { success: true, txId: dto.referenceId };
    } catch (error) {
      await client.query('ROLLBACK;');
      console.error(JSON.stringify({
        level: 'ERROR',
        correlationId,
        message: 'Transaksi gagal dan telah di-rollback',
        error: error instanceof Error ? error.message : String(error)
      }));
      throw error;
    } finally {
      // Sangat Kritis: Selalu kembalikan client ke pool!
      client.release();
    }
  }
}
```

#### 7.2.4. Presentation Controller & Schema Validation (`src/controllers/transfer.controller.ts`)

```typescript
import { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { TransferService, AppError } from '../services/transfer.service';

export const TransferRequestSchema = z.object({
  fromAccountId: z.string().uuid({ message: 'fromAccountId harus berformat UUID v4' }),
  toAccountId: z.string().uuid({ message: 'toAccountId harus berformat UUID v4' }),
  amount: z.number().positive({ message: 'amount harus berupa angka positif' }),
  referenceId: z.string().min(8, { message: 'referenceId minimal 8 karakter' }),
});

export class TransferController {
  constructor(private readonly transferService: TransferService) {}

  transfer = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const correlationId = (req.headers['x-correlation-id'] as string) || 'UNKNOWN_CID';
      
      // Validasi Skema Payload Ketat
      const parsedBody = TransferRequestSchema.parse(req.body);

      const result = await this.transferService.executeTransfer(parsedBody, correlationId);

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (err) {
      if (err instanceof z.ZodError) {
        res.status(400).json({
          success: false,
          error: {
            code: 'VALIDATION_ERROR',
            details: err.issues.map((i) => ({ field: i.path.join('.'), message: i.message })),
          },
        });
        return;
      }
      next(err);
    }
  };
}
```

#### 7.2.5. Centralized Error Handler & App Bootstrap (`src/server.ts`)

```typescript
import express, { Request, Response, NextFunction } from 'express';
import crypto from 'node:crypto';
import helmet from 'helmet';
import { dbPool } from './infrastructure/database';
import { AccountRepository } from './repositories/account.repository';
import { TransferService, AppError } from './services/transfer.service';
import { TransferController } from './controllers/transfer.controller';

const app = express();

// Security Headers & Body Parser
app.use(helmet());
app.use(express.json({ limit: '10kb' })); // Mencegah memory attack via oversized JSON payload

// Correlation ID & Context Middleware
app.use((req: Request, res: Response, next: NextFunction) => {
  const correlationId = (req.headers['x-correlation-id'] as string) || crypto.randomUUID();
  req.headers['x-correlation-id'] = correlationId;
  res.setHeader('X-Correlation-ID', correlationId);

  const start = process.hrtime.bigint();
  res.on('finish', () => {
    const end = process.hrtime.bigint();
    const durationMs = Number(end - start) / 1_000_000;
    console.log(JSON.stringify({
      level: 'INFO',
      correlationId,
      method: req.method,
      url: req.originalUrl,
      status: res.statusCode,
      latencyMs: durationMs.toFixed(2),
    }));
  });

  next();
});

// Wiring Dependencies (Dependency Injection Composition Root)
const accountRepo = new AccountRepository();
const transferService = new TransferService(dbPool, accountRepo);
const transferController = new TransferController(transferService);

// Health Check Endpoints untuk Kubernetes Probes
app.get('/health/live', (_req, res) => res.status(200).json({ status: 'ALIVE' }));
app.get('/health/ready', async (_req, res) => {
  try {
    await dbPool.query('SELECT 1;');
    res.status(200).json({ status: 'READY', database: 'CONNECTED' });
  } catch {
    res.status(503).json({ status: 'NOT_READY', database: 'UNREACHABLE' });
  }
});

// Domain Routes
app.post('/api/v1/transfers', transferController.transfer);

// Centralized Error Handling Middleware
app.use((err: Error, req: Request, res: Response, _next: NextFunction) => {
  const correlationId = req.headers['x-correlation-id'] as string;

  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      success: false,
      error: { code: 'OPERATIONAL_ERROR', message: err.message },
    });
    return;
  }

  // Programmer Error atau Unhandled Exception
  console.error(JSON.stringify({
    level: 'FATAL',
    correlationId,
    message: 'Unhandled Internal Server Error',
    stack: err.stack,
  }));

  res.status(500).json({
    success: false,
    error: { code: 'INTERNAL_SERVER_ERROR', message: 'Terjadi kesalahan sistem internal.' },
  });
});

// Server Initialization & Graceful Shutdown
const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => {
  console.log(`[SYSTEM] Microservice aktif pada port ${PORT}`);
});

let isShuttingDown = false;

function gracefulShutdown(signal: string) {
  if (isShuttingDown) return;
  isShuttingDown = true;

  console.log(`\n[SYSTEM] Sinyal ${signal} diterima. Menutup HTTP Listener...`);

  server.close(async (err) => {
    if (err) {
      console.error('[SYSTEM] Error saat menutup server HTTP:', err);
      process.exit(1);
    }

    console.log('[SYSTEM] HTTP Listener ditutup. Menutup Database Pool Connections...');
    try {
      await dbPool.end();
      console.log('[SYSTEM] Seluruh database connections telah dibersihkan.');
      process.exit(0);
    } catch (poolErr) {
      console.error('[SYSTEM] Gagal menutup database connection pool:', poolErr);
      process.exit(1);
    }
  });

  // Force Exit Safety Timeout
  setTimeout(() => {
    console.error('[SYSTEM] Graceful shutdown timeout (15s). Memaksa terminasi proses.');
    process.exit(1);
  }, 15000).unref();
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Kasus Flash Sale E-Commerce Skala Asia Tenggara

**Latar Belakang:**
Sebuah platform *e-commerce* menyelenggarakan kampanye kilat (*flash sale*) untuk produk smartphone diskon 90% dengan ketersediaan unit terbatas (hanya 50 unit). 250.000 pengguna secara serentak mengklik tombol "Checkout" pada detik yang sama (00:00:00 WIB).

**Titik Kegagalan Desain Awal:**
1. **Overselling (Anomali Concurrency)**: Sistem awal membaca stok (`SELECT stock FROM products WHERE id = 1`) di Service A, memeriksa apakah `stock > 0`, lalu menjalankan `UPDATE products SET stock = stock - 1`. Akibat ketiadaan *pessimistic lock* (`FOR UPDATE`) atau *atomic update*, 12.000 transaksi konkuren membaca nilai `stock = 50` yang sama secara bersamaan. Produk berhasil dibeli oleh 8.420 pengguna (terjadi *overselling* masif sebanyak 8.370 unit).
2. **Database Cascading Failure (Pool Saturation)**: Setiap *instance* Node.js (ada 20 kontainer) membuka *connection pool* dengan `max: 100`. Database Postgres yang hanya mampu melayani 500 koneksi bersamaan mengalami *exhaustion* (2.000 koneksi mencoba masuk). PostgreSQL kehabisan memori (*OOM Panic*), menyebabkan seluruh platform lumpuh total selama 45 menit.
3. **Ghost Transactions**: Kontainer yang kelebihan beban dimatikan paksa oleh Kubernetes *Liveness Probe Timeout*. Karena tidak memiliki *Graceful Shutdown*, transaksi saldo dompet terpotong, namun pesanan barang tidak tercatat di database karena koneksi terputus di tengah jalan.

**Solusi Arsitektur Enterprise yang Diterapkan:**
1. **Penerapan Atomic Conditional Update / Pessimistic Locking**:
   ```sql
   UPDATE products 
   SET stock = stock - 1 
   WHERE id = $1 AND stock > 0 
   RETURNING id, stock;
   ```
   Jika jumlah *row affected* adalah 0, lempar *domain exception* `OUT_OF_STOCK` tanpa membebani IO lanjutan.
2. **Database Pooling & Proxying**:
   - Memasang layer **PgBouncer** di depan PostgreSQL dengan mode *transaction pooling*, mengonsolidasikan ribuan koneksi aplikasi menjadi hanya 80 koneksi fisik ke Postgres engine.
   - Membatasi pool di aplikasi menjadi `max: 10` per kontainer.
3. **Queue-Based Decoupling**:
   - Alih-alih langsung memukul database transaksional, *traffic burst* diserap ke dalam Redis Queue/Apache Kafka. Worker terkelola mengeksekusi pesanan pada kecepatan yang stabil (*traffic shaping*).
4. **Resilient Shutdown Handling**:
   - Menerapkan *terminationGracePeriodSeconds: 30* di manifest Kubernetes Pod.
   - Pematian aplikasi mengeksekusi *draining* pesan dari queue sebelum memutuskan *pool client*.

---

## 9. Trade-offs

Setiap keputusan arsitektur memiliki konsekuensi struktural:

```
           [ Kecepatan Pengembangan ]
                     ▲
                    / \
                   /   \
                  /     \
  [ Konsistensi Data ]───[ Throughput / Skalabilitas ]
```

| Pendekatan | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Pessimistic Locking (`SELECT ... FOR UPDATE`)** | Mencegah inkonsistensi data secara absolut pada sistem keuangan. | Menurunkan konkurensi secara drastis (*high latency*), memicu *lock wait timeouts*, dan rentan *deadlock* jika urutan tabel tidak diatur rapi. |
| **Optimistic Locking (`version` column check)** | Konkurensi sangat tinggi, *non-blocking read*, tidak membebani database lock engine. | Menuntut logika *retry* kompleks di sisi aplikasi. Jika tingkat konflik sangat tinggi (flash sale), 95% request akan *retry* berulang kali dan membuang siklus CPU. |
| **Large Connection Pool (e.g., max: 100 per pod)** | Menghindari antrean `Connection acquire timeout` pada beban sesaat. | Pemborosan RAM di PostgreSQL (setiap worker process mengonsumsi ~5-10MB basis memori). Menghancurkan performa CPU akibat *context switching* di OS database. |
| **Small Connection Pool (e.g., max: 5-10 per pod)** | PostgreSQL beroperasi pada *sweet spot* optimal (efisiensi CPU cache tinggi, memori aman). | Request yang membludak akan mengalami antrean tunggu di memori aplikasi; jika melewati *timeout*, aplikasi mengembalikan HTTP 500/503 ke klien. |
| **Layered Architecture (Controller-Service-Repo)** | Kode terisolasi rapi, *unit testing* mudah menggunakan mock, *maintainability* tinggi untuk tim besar. | *Boilerplate* tinggi, waktu pengembangan awal lebih lambat, *cognitive overhead* bagi pemula dibandingkan pola *active record/fat controller*. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal Terpopuler

1. **Lupa Melepaskan Pool Client (`client.release()`)**:
   - *Penyebab*: Memanggil `const client = await pool.connect()` tanpa blok `try ... finally { client.release(); }`.
   - *Dampak*: Terjadi kebocoran koneksi (*connection leak*). Setelah beberapa puluh pemanggilan, pool macet selamanya (*freeze*).
2. **Deadlock Akibat Penguncian Multi-Row Acak**:
   - *Penyebab*: Transaksi A mengunci Rekening 1 lalu Rekening 2. Transaksi B (berjalan simultan) mengunci Rekening 2 lalu Rekening 1.
   - *Dampak*: PostgreSQL mendeteksi *Deadlock* dan membatalkan salah satu transaksi dengan error `40P01: deadlock detected`.
   - *Solusi*: Selalu urutkan ID sumber daya secara leksikografis/numerik sebelum melakukan penguncian (`sort()`).
3. **Mencampur Konteks Transaksi Antar-Request**:
   - *Penyebab*: Menyimpan instance `PoolClient` di dalam variabel *singleton* atau *class property* bersama.
   - *Dampak*: Request dari Pengguna B bisa mengeksekusi `COMMIT` yang memvalidasi mutasi dari Pengguna A secara tidak sengaja.
4. **Unhandled Promise Rejections di Middleware**:
   - *Penyebab*: Tidak meneruskan `err` ke `next(err)` pada Express routing handler atau lupa blok `try/catch`.
   - *Dampak*: Pada runtime Node.js modern, *unhandled rejection* memicu *process crash* instan.

### 10.2. Troubleshooting Playbook

| Gejala Sistem | Analisis Akar Masalah (Root Cause) | Prosedur Remediasi |
| :--- | :--- | :--- |
| Error: `remaining connection slots are reserved for non-replication superuser connections` | Aplikasi membuka koneksi melebihi nilai `max_connections` di `postgresql.conf`. | 1. Turunkan nilai `max` pada pool di backend.<br>2. Pasang koneksi proxy (PgBouncer).<br>3. Identifikasi pod yang mengalami *dangling connection*. |
| Latensi API meroket secara bertahap, request menggantung hingga 30s timeout | Terjadi kebocoran koneksi (`client.release()` terlewati karena unhandled error). | 1. Pasang metrik `pool.totalCount`, `pool.idleCount`, dan `pool.waitingCount`.<br>2. Audit seluruh blok kode `pool.connect()` dan pastikan `finally` selalu ada. |
| Database Error: `current transaction is aborted, commands ignored until end of transaction block` | Query di dalam blok transaksi mengalami error (misal syntax error/constraint violation), namun aplikasi mencoba mengeksekusi query berikutnya tanpa melakukan `ROLLBACK`. | Tangkap error pertama, segera eksekusi `ROLLBACK`, dan hentikan eksekusi runtutan query berikutnya. |

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa (*checklist*) ini sebelum mempromosikan kode backend ke lingkungan produksi:

- [ ] **Data Access Layer**: Seluruh koneksi transaksi wajib dilepaskan di dalam blok `finally`.
- [ ] **Deadlock Prevention**: Penguncian multi-row wajib diurutkan (`Array.prototype.sort()`).
- [ ] **Validation Layer**: Seluruh `req.body`, `req.query`, dan `req.params` telah divalidasi dan di-*sanitize* menggunakan pustaka berbasis tipe (Zod/Valibot/Typebox) sebelum menyentuh Service.
- [ ] **Zero Trust Input**: Batasan ukuran payload JSON telah ditetapkan secara eksplisit (`limit: '10kb'`).
- [ ] **Correlation ID**: Setiap log keluaran mengandung `correlationId` untuk penelusuran terdistribusi (*distributed tracing*).
- [ ] **Security Headers**: Middleware keamanan (Helmet) aktif dengan proteksi CSP dan pencegahan MIME-sniffing.
- [ ] **Graceful Shutdown**: Signal handler `SIGTERM` dan `SIGINT` terpasang, menghentikan server HTTP, menghabiskan *in-flight requests*, dan menutup pool database.
- [ ] **Container Probes**: Tersedia endpoint `/health/live` (status runtime mandiri) dan `/health/ready` (status dependensi database).
- [ ] **Environment Separation**: Parameter sensitif (koneksi DB, rahasia API) diinjeksi via *environment variables*, bukan *hardcoded*.
- [ ] **Isolation**: Service Layer bersifat *framework-agnostic* (tidak memiliki dependensi terhadap library HTTP apa pun).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

### Langkah 1: Persiapan Lingkungan

Inisialisasi proyek dan pasang dependensi yang dibutuhkan:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node tsx -D
npx tsc --init
npm install express @types/express pg @types/pg zod helmet
```

### Langkah 2: Persiapan Skema Database PostgreSQL

Jalankan skrip SQL berikut pada instance PostgreSQL lokal atau kontainer Docker Anda:

```sql
-- hands-on/m02/init.sql
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_name VARCHAR(100) NOT NULL,
    balance BIGINT NOT NULL CHECK (balance >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE transfer_ledgers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_account_id UUID NOT NULL REFERENCES accounts(id),
    to_account_id UUID NOT NULL REFERENCES accounts(id),
    amount BIGINT NOT NULL CHECK (amount > 0),
    reference_id VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seeding data awal untuk testing
INSERT INTO accounts (id, owner_name, balance) VALUES
('a0000000-0000-0000-0000-000000000001', 'Alice Finansial', 1000000),
('b0000000-0000-0000-0000-000000000002', 'Bob Merchant', 250000);
```

### Langkah 3: Struktur Direktori Proyek

Pastikan struktur file Anda tersusun rapi seperti berikut:

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── init.sql
└── src/
    ├── infrastructure/
    │   └── database.ts
    ├── repositories/
    │   └── account.repository.ts
    ├── services/
    │   └── transfer.service.ts
    ├── controllers/
    │   └── transfer.controller.ts
    └── server.ts
```

*(Gunakan implementasi kode yang tertera pada Seksi 7.2 untuk mengisi file-file di atas)*.

### Langkah 4: Menjalankan dan Memverifikasi Sistem

Jalankan server aplikasi:
```bash
npx tsx src/server.ts
```

Uji Transaksi Valid via `curl`:
```bash
curl -X POST http://localhost:3000/api/v1/transfers \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-trace-001" \
  -d '{
    "fromAccountId": "a0000000-0000-0000-0000-000000000001",
    "toAccountId": "b0000000-0000-0000-0000-000000000002",
    "amount": 150000,
    "referenceId": "REF-TX-2026-0001"
  }'
```

Uji Transaksi Gagal (Insufficient Balance):
```bash
curl -X POST http://localhost:3000/api/v1/transfers \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-trace-002" \
  -d '{
    "fromAccountId": "b0000000-0000-0000-0000-000000000002",
    "toAccountId": "a0000000-0000-0000-0000-000000000001",
    "amount": 999999999,
    "referenceId": "REF-TX-2026-0002"
  }'
```

Uji Graceful Shutdown:
Kirim sinyal terminasi saat server sedang aktif:
```bash
kill -SIGTERM $(pgrep -f "tsx src/server.ts")
```
Perhatikan log terminal: Server akan berhenti menerima koneksi, menutup database pool secara teratur, dan keluar dengan exit code 0.

---

## 13. Exercise

### Level Easy
Modifikasi skema validasi Zod pada `TransferRequestSchema` di `src/controllers/transfer.controller.ts`:
- Tambahkan properti opsional `description` dengan batasan maksimal 255 karakter.
- Tambahkan sanitasi agar `description` tidak mengandung tag HTML (`<script>` atau elemen tag lainnya).

### Level Medium
Tambahkan *Idempotency Check Middleware* pada rute `/api/v1/transfers`:
- Jika klien mengirimkan header `X-Idempotency-Key`, periksa apakah kunci tersebut telah diproses sebelumnya di tabel database terpisah (`idempotency_keys`).
- Jika kunci sudah ada dan statusnya `SUCCESS`, kembalikan *cached response* tanpa memicu kembali pemanggilan `TransferService`.
- Jika kunci belum ada, kunci resource tersebut, eksekusi transfer, dan simpan hasilnya.

### Level Hard
Implementasikan skema **Deadlock Stress Tester & Automatic Retry Mechanism**:
1. Buat skrip simulasi menggunakan worker threads atau `Promise.all` yang mengeksekusi 100 transfer silang paralel antara Akun A dan Akun B secara acak tanpa pengurutan ID.
2. Modifikasi `TransferService` dengan mekanisme *exponential backoff retry* (maksimal 3 kali percobaan ulang) jika menangkap error kode PostgreSQL `40P01` (*deadlock detected*).
3. Buktikan melalui log bahwa transaksi yang sempat terkena deadlock berhasil pulih dan saldo akhir tetap konsisten secara matematis.

---

## 14. Challenge

### Studi Kasus: High-Contention Flash Inventory Reservation System

**Konteks Bisnis:**
Sebuah platform penjualan tiket konser internasional menjual 5.000 kursi kategori VIP. Terdapat 100.000 pengguna yang berebut memesan tiket pada menit yang sama.

**Aturan Main:**
1. Tiket yang diklik pengguna akan "dipesan sementara" (*reserved*) selama 10 menit.
2. Jika dalam 10 menit pembayaran tidak diselesaikan, status reservasi otomatis kedaluwarsa (*expired*) dan tiket kembali berstatus *available*.
3. Sistem tidak boleh menjual tiket melebihi kuota (*zero overselling*).
4. Tidak boleh terjadi *table lock* yang menyebabkan endpoint pembacaan denah konser menjadi *unresponsive* (*read throughput* harus tetap di atas 2.000 RPS).

**Tantangan Arsitektur:**
Rancang dan bangun prototipe backend enterprise yang memecahkan masalah ini dengan kriteria:
- Menggunakan arsitektur berlapis (Clean/Layered Architecture) yang telah dipelajari.
- Desain skema data transaksional yang memitigasi *hotspot row contention*.
- Implementasikan *background cleanup worker* atau mekanisme non-blocking untuk membebaskan reservasi kedaluwarsa tanpa mengunci operasional pemesanan baru.
- Sertakan implementasi Graceful Lifecycle agar saat proses *re-deploy*, pengguna yang sedang melakukan *hold inventory* tidak terputus secara anomalik.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic (5 Soal)

1. **Apa tujuan utama pemisahan kode ke dalam Service Layer dan Repository Layer?**
   - A. Agar penulisan query SQL dapat digabungkan langsung dengan logika Express `req` dan `res`.
   - B. Mengisolasi aturan bisnis dari detail implementasi protokol HTTP dan pustaka persistensi data.
   - C. Mempercepat waktu startup Node.js saat pertama kali dijalankan.
   - D. Menghilangkan kebutuhan untuk menulis unit test.

2. **Apa yang terjadi secara internal jika aplikasi memanggil `pool.connect()` namun tidak pernah memanggil `client.release()`?**
   - A. PostgreSQL secara otomatis menutup koneksi setelah 1 detik.
   - B. Pool akan terus membuka koneksi baru tanpa batas hingga database crash.
   - C. Koneksi tertahan di status aktif, menyebabkan antrean permintaan kehabisan koneksi (*pool exhaustion*).
   - D. Runtime Node.js langsung melemparkan error `OutOfMemoryError`.

3. **Mengapa penggunaan `FOR UPDATE` diperlukan saat membaca saldo pada transaksi transfer finansial?**
   - A. Untuk mengonversi tipe data numerik menjadi floating point.
   - B. Menghindari race condition (lost update) dengan mengunci baris data hingga transaksi selesai.
   - C. Mempercepat eksekusi query dengan mengabaikan indexing.
   - D. Mengizinkan transaksi lain membaca data yang belum di-commit (*dirty read*).

4. **Sinyal sistem operasi default yang dikirimkan oleh orchestrator (Docker/Kubernetes) untuk meminta proses berhenti secara normal adalah:**
   - A. `SIGKILL`
   - B. `SIGINT`
   - C. `SIGTERM`
   - D. `SIGHUP`

5. **Apa fungsi dari header HTTP `X-Correlation-ID` pada arsitektur microservices?**
   - A. Mengenkripsi payload request agar tidak terbaca oleh Man-in-the-Middle.
   - B. Menandai identifier unik sebuah alur request untuk pelacakan (*tracing*) log lintas service.
   - C. Menggantikan peran JSON Web Token (JWT) dalam otentikasi.
   - D. Mengompresi payload response agar latensi jaringan berkurang.

---

### 15.2. Pertanyaan Intermediate (5 Soal)

6. **Dua transaksi konkuren mengeksekusi transfer secara bersamaan: Transaksi 1 mentransfer dari Akun A ke B, sedangkan Transaksi 2 mentransfer dari Akun B ke A. Apa potensi bahaya jika urutan penguncian row tidak distandarisasi?**
   - A. Non-Repeatable Read.
   - B. Phantom Read.
   - C. Deadlock (*Circular Lock Dependency*).
   - D. Corrupted Write-Ahead Log.

7. **Bagaimana cara mencegah kebocoran informasi internal sistem ketika terjadi kesalahan fatal yang tidak tertangani (*unhandled programmer error*)?**
   - A. Menampilkan full error stack trace langsung ke response JSON klien.
   - B. Menangkap error di Centralized Error Middleware, mencatat stack trace di private logger, dan mengembalikan generic message HTTP 500 ke klien.
   - C. Mematikan fitur logging agar performa server tetap maksimal.
   - D. Mengabaikan error dan membiarkan request menggantung hingga timeout.

8. **Perbedaan mendasar antara *Liveness Probe* dan *Readiness Probe* pada arsitektur orkestrasi kontainer adalah:**
   - A. Liveness memeriksa apakah pod masih hidup (jika gagal, pod direstart); Readiness memeriksa apakah pod siap menerima traffic (jika gagal, traffic dihentikan sementara).
   - B. Liveness digunakan untuk database, Readiness digunakan untuk web server.
   - C. Liveness Probe berjalan setiap milidetik, Readiness Probe hanya berjalan sekali saat build.
   - D. Keduanya memiliki fungsi yang identik dan hanya berbeda nama konvensi.

9. **Mengapa ukuran Connection Pool Database pada satu instance backend tidak disarankan diatur terlalu besar (misal `max: 500`)?**
   - A. Node.js tidak mendukung soket TCP lebih dari 100.
   - B. Database engine (seperti PostgreSQL) mengalokasikan proses/thread dan memori tersendiri per koneksi; terlalu banyak koneksi konkuren memicu lonjakan *context switching* CPU dan risiko *OOM crash*.
   - C. Protokol HTTP/2 melarang pool lebih dari 50 koneksi.
   - D. Akan menurunkan keamanan jaringan internal aplikasi.

10. **Apa tujuan penambahan parameter `limit: '10kb'` pada `express.json()` middleware?**
    - A. Mempercepat koneksi internet pengguna.
    - B. Mencegah serangan *Denial of Service (DoS)* akibat pengiriman payload raksasa yang membebani alokasi memori heap runtime.
    - C. Memaksa seluruh teks string di database berukuran di bawah 10 kilobyte.
    - D. Mengharuskan klien menggunakan kompresi Gzip.

---

### 15.3. Skenario Kasus Produksi (3 Soal)

11. **Skenario:**
    Aplikasi pembayaran Anda mencatat lonjakan traffic tajam saat peluncuran promo akhir bulan. Pengguna mengeluhkan bahwa aplikasi sesekali mengembalikan HTTP 500 dengan pesan error `timeout exceeded when trying to connect to the database pool`. Namun, pemantauan utilisasi CPU dan RAM database PostgreSQL menunjukkan angka normal di kisaran 35%. 
    
    **Pertanyaan:** Apa penyebab paling logis dari fenomena ini dan tindakan korektif apa yang paling tepat?
    - A. Database mengalami kebocoran memori hard disk; solusinya adalah me-restart instance database.
    - B. Nilai `connectionTimeoutMillis` aplikasi terlalu rendah atau pool size backend terlalu kecil relatif terhadap volume concurrent request, atau terdapat *connection leak* pada blok kode yang tidak melepaskan koneksi saat exception terjadi.
    - C. PostgreSQL menolak koneksi karena indeks tabel korup; solusinya adalah menjalankan `REINDEX DATABASE`.
    - D. Framework Express kehabisan thread pool asynchronous; solusinya meningkatkan `UV_THREADPOOL_SIZE`.

12. **Skenario:**
    Saat proses deployment versi baru menggunakan Kubernetes rolling update, sekitar 0.05% request pembayaran dari mobile app selalu menghasilkan error `502 Bad Gateway` atau koneksi terputus tiba-tiba (*TCP connection reset by peer*).
    
    **Pertanyaan:** Langkah arsitektural apa yang belum diterapkan dengan benar pada aplikasi?
    - A. Aplikasi tidak menerapkan autentikasi Bearer Token.
    - B. Aplikasi langsung berhenti saat menerima `SIGTERM` tanpa menolak request baru secara halus dan tanpa menunggu *in-flight requests* yang sedang diproses selesai (*Graceful Shutdown*).
    - C. Kubernetes worker node kehabisan storage disk epik.
    - D. Database client tidak menggunakan driver berbasis WebSockets.

13. **Skenario:**
    Sebuah endpoint menerima transfer dana massal: satu akun mendebit saldo untuk dikirimkan ke 50 akun vendor sekaligus. Di tengah iterasi looping transfer pada akun ke-42, terjadi kegagalan validasi akun tujuan yang tidak valid. Pengembang melaporkan bahwa saldo pengirim sudah berkurang untuk 41 vendor pertama, tetapi sistem crash sebelum menyelesaikan sisanya.
    
    **Pertanyaan:** Pelanggaran prinsip ACID manakah yang terjadi, dan bagaimana solusinya?
    - A. Pelanggaran *Durability*; solusinya adalah meningkatkan interval Write-Ahead Log.
    - B. Pelanggaran *Isolation*; solusinya adalah menaikkan isolation level ke `READ UNCOMMITTED`.
    - C. Pelanggaran *Atomicity*; solusinya adalah membungkus seluruh rangkaian 50 iterasi mutasi dalam satu transaksi database tunggal yang di-`ROLLBACK` secara utuh jika ada satu saja iterasi yang gagal.
    - D. Pelanggaran *Consistency*; solusinya adalah menghapus foreign key check pada tabel vendor.

---

### Kunci Jawaban Quiz

#### Pertanyaan Basic
1. **B** - Memisahkan aturan bisnis dari detail protokol dan database adalah esensi Clean/Layered Architecture.
2. **C** - Koneksi yang tidak di-release akan menjadi *dangling connection* dan menghabiskan slot pool hingga sistem macet.
3. **B** - `FOR UPDATE` mengunci baris data di level database engine agar tidak terjadi modifikasi konkuren (*lost update*).
4. **C** - `SIGTERM` adalah sinyal standar untuk meminta proses terminasi secara elegan.
5. **B** - `Correlation ID` menyatukan seluruh log terdistribusi dalam satu kesatuan alur penelusuran.

#### Pertanyaan Intermediate
6. **C** - Mengunci resource yang sama dengan urutan berlawanan secara konkuren merupakan kondisi klasik penyebab *deadlock*.
7. **B** - Menyembunyikan stack trace internal dari publik dan mencatatnya di internal log adalah standar keamanan baku.
8. **A** - Liveness mengatur siklus hidup container (restart), sedangkan Readiness mengatur distribusi traffic jaringan.
9. **B** - Pool yang terlalu besar membebani CPU database dengan context switching dan alokasi memori berlebih.
10. **B** - Membatasi ukuran body parser melindungi server dari exhaustion memory akibat serangan payload besar.

#### Skenario Kasus Produksi
11. **B** - Ketika DB CPU rendah namun pool timeout, masalah berada pada alokasi antrean koneksi di layer aplikasi atau adanya koneksi yang bocor (*leak*).
12. **B** - Error 502/TCP reset saat rolling update terjadi karena proses aplikasi lama mati seketika sebelum menuntaskan koneksi aktif yang masih berjalan.
13. **C** - Kegagalan parsial (*sebagian berhasil, sebagian gagal*) adalah pelanggaran sifat Atomis (*all-or-nothing*); solusinya adalah memanfaatkan transaksi database.

---

## 16. Summary

Pada modul ini, kita telah mentransisikan kapabilitas rekayasa perangkat lunak backend dari sekadar "membuat kode yang berjalan" (*functional prototype*) menuju standar "sistem siap produksi berskala enterprise" (*production-grade engineering*):

1. **Layered Decoupling**: Menjaga integritas domain dengan memisahkan *Transport/Presentation*, *Business Logic*, dan *Data Access Layer*. Service Layer tidak boleh tercemar objek HTTP framework.
2. **ACID Concurrency Guarantee**: Mengoperasikan transaksi atomik dengan *row-level locking* yang deterministik untuk mengeliminasi anomali *race condition* dan *deadlock*.
3. **Resource Lifecycle Discipline**: Memperlakukan koneksi database sebagai sumber daya berharga melalui *Connection Pool management* yang ketat (selalu melepaskan koneksi dalam blok `finally`).
4. **Resilience & Zero-Downtime**: Menangani sinyal sistem operasi (`SIGTERM`/`SIGINT`) secara proaktif guna menjamin *graceful shutdown* tanpa pemutusan paksa pada request pengguna.
5. **Production Hardening**: Menerapkan observabilitas berbasis *Correlation ID*, validasi skema runtime yang ketat (Zod), serta pemisahan tegas antara *Operational Error* dan *Programmer Error*.