# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** backend-beginner | **Bab:** 04-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengonstruksi Arsitektur Berlapis (Layered/Clean Architecture):** Memisahkan *concern* antara Controller, Service/Use Case, Repository, dan Data Source secara modular dan dapat diuji (*testable*).
2. **Mengelola Siklus Koneksi Database Tingkat Lanjut:** Mengonfigurasi dan menganalisis metrik *Connection Pooling*, mencegah *connection leak*, serta memahami *TCP Handshake overhead*.
3. **Menerapkan Manajemen Transaksi Atomik (ACID):** Mengimplementasikan transaksi multi-tabel dengan *rollback* otomatis dan memilih *Transaction Isolation Level* yang tepat untuk mencegah *concurrency anomalies*.
4. **Membangun Mekanisme Graceful Shutdown:** Menangani *POSIX Signals* (`SIGTERM`, `SIGINT`) untuk *zero-downtime deployment*, melakukan *drain* koneksi HTTP dan soket database.
5. **Menghadirkan Observabilitas Tingkat Produksi:** Mengintegrasikan *Structured Logging* dengan korelasi ID (`X-Request-ID`) dan mendesain probe *Liveness* & *Readiness*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta diasumsikan telah menguasai:
* Dasar protokol HTTP/1.1 (Metode, Status Code, Header, Body).
* Dasar pemrograman asinkronus TypeScript/Node.js (*Event Loop*, *Promises*, `async`/`await`).
* Sintaks dasar SQL Relasional (DDL, DML, `SELECT ... JOIN`, `GROUP BY`).
* Pemahaman dasar Docker untuk menjalankan *database engine* lokal.

---

## 3. Concept & Internal Architecture

Peralihan dari kode backend eksperimental menuju sistem siap produksi (*production-ready*) membutuhkan pemahaman mendalam tentang bagaimana proses aplikasi berinteraksi dengan kernel sistem operasi, memori, dan *database engine*.

```
+---------------------------------------------------------------------------------------+
|                                    KONTINER APLIKASI                                  |
|                                                                                       |
|   [ Ingress HTTP Request ]                                                            |
|              │                                                                        |
|              ▼                                                                        |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ 1. HTTP Server Layer (Kestrel / Fastify / Express / Go Net/HTTP)              │   |
|   │    - Parsing TCP Stream -> HTTP Context                                      │   |
|   │    - Injeksi Context: Request-ID, Trace-ID, Timeout Cancellation              │   |
|   └──────────────────────────────────────┬────────────────────────────────────────┘   |
|                                          │                                            |
|                                          ▼                                            |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ 2. Presentation / Controller Layer                                            │   |
|   │    - Validasi Skema Payload (Zod / Joi / Class-Validator)                     │   |
|   │    - Serialisasi & Pemetaan HTTP Status Code                                  │   |
|   └──────────────────────────────────────┬────────────────────────────────────────┘   |
|                                          │                                            |
|                                          ▼                                            |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ 3. Domain / Service Layer                                                     │   |
|   │    - Business Logic Execution                                                 │   |
|   │    - Atomic Transaction Boundary (Unit of Work Orchestration)                 │   |
|   └──────────────────────────────────────┬────────────────────────────────────────┘   |
|                                          │                                            |
|                                          ▼                                            |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ 4. Data Access / Repository Layer                                             │   |
|   │    - Abstraksi Query SQL                                                      │   |
|   │    - Interaksi dengan Connection Pool                                         │   |
|   └──────────────────────────────────────┬────────────────────────────────────────┘   |
|                                          │                                            |
+------------------------------------------┼--------------------------------------------+
                                           │
                        Acquire Connection │ Release Connection
                                           ▼
+---------------------------------------------------------------------------------------+
|                                DATABASE ENGINE (PostgreSQL)                           |
|                                                                                       |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ Database Connection Pool Worker                                               │   |
|   │  [ Active Conn 1 ]   [ Active Conn 2 ]   [ Idle Conn ]   ... [ Wait Queue ]   │   |
|   └──────────────────────────────────────┬────────────────────────────────────────┘   |
|                                          ▼                                            |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ Engine Core: Query Engine -> Write-Ahead Log (WAL) -> Buffer Pool -> Disk     │   |
|   └───────────────────────────────────────────────────────────────────────────────┘   |
+---------------------------------------------------------------------------------------+
```

### 3.1. Internal Database Connection Pooling
Membuat koneksi TCP baru membutuhkan *three-way handshake*, alokasi memori proses pada server database (misalnya proses `postgres` backend di PostgreSQL memakan ~5-10MB RAM per koneksi), serta inisialisasi TLS dan autentikasi.

*Connection Pool* mengelola sekumpulan koneksi soket TCP persisten:
1. **Acquire:** Aplikasi meminta koneksi dari pool. Jika ada *idle connection*, soket langsung dialokasikan. Jika pool penuh (`max`), request mengantre di memori (*Wait Queue*) hingga batas *timeout* (`connectionTimeoutMillis`).
2. **Execute:** Aplikasi mengirimkan teks kueri dan parameter melalui soket tersebut.
3. **Release:** Aplikasi mengembalikan koneksi ke pool, bukan menutup soket TCP. Jika ada transaksi yang belum di-*commit* atau di-*rollback*, koneksi harus di-*reset* statusnya sebelum digunakan oleh request lain.

### 3.2. ACID & Transaction Isolation Levels
Transaksi adalah batas logis eksekusi SQL yang memenuhi prinsip:
* **Atomicity:** Seluruh operasi sukses di-*commit*, atau seluruhnya di-*rollback* via *Write-Ahead Log* (WAL).
* **Consistency:** Memastikan integritas skema (foreign key, unique, check constraints) tidak dilanggar.
* **Isolation:** Menentukan visibilitas perubahan data antar-transaksi yang berjalan bersamaan (*concurrent*).
* **Durability:** Data yang sudah di-*commit* tersimpan di *non-volatile storage* meskipun sistem *crash*.

Standar ANSI SQL mendefinisikan 4 tingkat isolasi untuk mengatasi fenomena konkurensi:

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read | Serialization Anomaly |
| :--- | :--- | :--- | :--- | :--- |
| **Read Uncommitted** | Mungkin | Mungkin | Mungkin | Mungkin |
| **Read Committed** *(Default PG)* | **Dicegah** | Mungkin | Mungkin | Mungkin |
| **Repeatable Read** | **Dicegah** | **Dicegah** | Dicegah di PG* | Mungkin |
| **Serializable** | **Dicegah** | **Dicegah** | **Dicegah** | **Dicegah** |

*\*Catatan PostgreSQL: Level Repeatable Read menggunakan Snapshot Isolation yang sekaligus memitigasi phantom read standar.*

### 3.3. POSIX Signals & Graceful Teardown
Dalam orkestrasi kontiner (Kubernetes/Docker), proses aplikasi dihentikan melalui pengiriman sinyal `SIGTERM`. Kegagalan menangani sinyal ini menyebabkan:
* Pemutusan koneksi HTTP klien secara mendadak (*connection reset by peer / 502 Bad Gateway* pada Reverse Proxy).
* Transaksi database terputus di tengah jalan, memaksa DB melakukan *recovery rollback* yang lambat.
* Kebocoran *background job* yang sedang dieksekusi.

---

## 4. Why & What

### Mengapa Kode Arsitektur Naif Gagal di Produksi?
Pada fase pemula, arsitektur sering kali memusatkan logika routing, manipulasi basis data, validasi, dan penanganan kesalahan dalam satu fungsi handler (metode monolitik kotor). 

```ts
// CONTOH KODE BURUK (Anti-Pattern: Spaghetti Execution)
app.post('/checkout', async (req, res) => {
  const db = new Client(); // MEMBUKA KONEKSI BARU SETIAP REQUEST!
  await db.connect();
  const user = await db.query('SELECT * FROM users WHERE id = ' + req.body.userId); // SQL INJECTION!
  await db.query('UPDATE accounts SET balance = balance - ' + req.body.amount); // RACE CONDITION & LEAK
  // Jika server crash di sini, uang berkurang tapi order tidak terbuat!
  await db.query('INSERT INTO orders ...');
  res.send('Success');
});
```

Konsekuensi dari kode di atas pada beban 500 RPS:
1. **Socket Exhaustion:** Database kehabisan *file descriptors* karena membuka koneksi TCP baru per request.
2. **Inkonsistensi Finansial:** Kegagalan parsial tanpa mekanisme transaksi atomik.
3. **Database Crash:** Beban CPU database melonjak hingga 100% hanya untuk melakukan autentikasi koneksi baru.

### Apa yang Dibangun pada Arsitektur Produksi?
1. **Layered Decoupling:** Memisahkan lapisan transportasi (HTTP) dari domain bisnis murni. Lapisan bisnis tidak boleh tahu apakah request datang dari HTTP REST, gRPC, CLI, atau message broker.
2. **Transaction Demarcation:** Lapisan Service menentukan batas transaksi, sedangkan Lapisan Repository mengeksekusi instruksi kueri menggunakan koneksi transaksional yang sama.
3. **Graceful Signal Trapping:** Server menyelesaikan request yang sedang berjalan sebelum mematikan proses, serta menutup seluruh pool secara tertib.

---

## 5. How (Workflow Detail)

Alur eksekusi request tingkat produksi:

```
[Klien HTTP]
     │
     ▼
[Middleware: Request ID & Logger Context]
     │ (Menerbitkan X-Request-ID dan memulai latency timer)
     ▼
[Controller Layer]
     │ (Validasi payload DTO via Zod Schema)
     ▼
[Service Layer]
     │ ── 1. Acquire Dedicated Client dari Connection Pool
     │ ── 2. Kirim perintah: BEGIN
     │
     ├───► [Repository A: Potong Saldo User] (Eksekusi query via Dedicated Client)
     │
     ├───► [Repository B: Kurangi Stok Item]  (Eksekusi query via Dedicated Client)
     │
     ├───► [Repository C: Terbitkan Order]    (Eksekusi query via Dedicated Client)
     │
     │ ── 3a. Jika Seluruh Step Sukses: Kirim COMMIT
     │ ── 3b. Jika Salah Satu Step Gagal: Kirim ROLLBACK
     │ ── 4. Kembalikan Dedicated Client ke Connection Pool (Finally Block)
     ▼
[Response Formatter]
     │ (Serialisasi output standar)
     ▼
[Klien HTTP Menerima 200 OK atau Error Terstruktur]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Connection Pool
Bayangkan sebuah **Pelabuhan Kapal Feri**:
* **Tanpa Pool:** Setiap penumpang yang ingin menyeberang harus membangun perahu baru dari kayu gelondongan, menyeberang, lalu membakar perahu tersebut di seberang sungai. Ini sangat lambat dan menghabiskan sumber daya.
* **Dengan Pool:** Pelabuhan menyediakan 10 kapal feri siap pakai (*fixed size*). Penumpang naik kapal yang sedang bersandar (*acquire*), berlayar (*execute*), turun di dermaga tujuan, dan kapal tersebut dibersihkan untuk digunakan oleh penumpang berikutnya dalam antrean (*release*).

### Graceful Teardown Flow

```
[ SIGTERM Signal Dikirim oleh OS / Kubernetes ]
                         │
                         ▼
        [ Matikan HTTP Server Listener ] 
         (Stop menerima koneksi baru, tolak dengan 503)
                         │
                         ▼
       [ Tunggu In-Flight Request Selesai ]
         (Beri grace period, misal: max 15 detik)
                         │
                         ▼
          [ Commit / Rollback Aktif DB ]
                         │
                         ▼
          [ Close Database Pool (pg.end) ]
         (Kirim instruksi TCP FIN ke DB Server)
                         │
                         ▼
               [ Exit Process (code 0) ]
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Bahaya Tersembunyi Connection Leak
Contoh bagaimana kueri sederhana dapat menghancurkan aplikasi akibat kegagalan pengembalian koneksi pada skenario error.

```ts
// bad-pool-leak.ts
import { Pool } from 'pg';

const pool = new Pool({ max: 2 }); // Konfigurasi pool sangat kecil untuk demonstrasi

async function leakConnection() {
  const client = await pool.connect();
  // BUG: Jika baris di bawah melempar error, client.release() TIDAK AKAN PERNAH DIPANGGIL!
  const res = await client.query('SELECT * FROM non_existent_table');
  client.release();
  return res;
}

async function run() {
  try { await leakConnection(); } catch (e) { console.log('Call 1 failed'); }
  try { await leakConnection(); } catch (e) { console.log('Call 2 failed'); }
  
  console.log('Mencoba call 3...');
  // APLIKASI AKAN HANG SELAMANYA DI SINI KARENA POOL EXHAUSTION!
  try { await leakConnection(); } catch (e) { console.log('Call 3 failed'); }
}

run();
```

---

### 7.2. Practical Example: Production-Grade Layered Architecture

Implementasi penuh arsitektur modular TypeScript dengan *Transaction Management*, *Dependency Injection*, dan *Graceful Shutdown*.

#### Struktur Direktori
```text
src/
├── infrastructure/
│   ├── database.ts
│   └── logger.ts
├── modules/
│   └── order/
│       ├── order.controller.ts
│       ├── order.dto.ts
│       ├── order.repository.ts
│       └── order.service.ts
└── app.ts
```

#### File: `src/infrastructure/database.ts`
```ts
import { Pool, PoolClient } from 'pg';

export class Database {
  private static pool: Pool;

  public static initialize(): Pool {
    this.pool = new Pool({
      host: process.env.DB_HOST || 'localhost',
      port: Number(process.env.DB_PORT) || 5432,
      user: process.env.DB_USER || 'postgres',
      password: process.env.DB_PASSWORD || 'postgres',
      database: process.env.DB_NAME || 'enterprise_db',
      max: 20, // Maksimum koneksi simultan
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000, // Timeout jika pool penuh
    });

    this.pool.on('error', (err) => {
      console.error('Unexpected error on idle database client', err);
    });

    return this.pool;
  }

  public static getPool(): Pool {
    if (!this.pool) {
      throw new Error('Database pool belum diinisialisasi.');
    }
    return this.pool;
  }

  public static async close(): Promise<void> {
    if (this.pool) {
      await this.pool.end();
      console.log('Database connection pool berhasil ditutup.');
    }
  }
}
```

#### File: `src/modules/order/order.dto.ts`
```ts
import { z } from 'zod';

export const CreateOrderSchema = z.object({
  userId: z.string().uuid(),
  amount: z.number().positive(),
  itemId: z.string().uuid(),
  quantity: z.number().int().positive(),
});

export type CreateOrderDTO = z.infer<typeof CreateOrderSchema>;
```

#### File: `src/modules/order/order.repository.ts`
```ts
import { Pool, PoolClient } from 'pg';

export interface IOrderRepository {
  deductUserBalance(client: PoolClient, userId: string, amount: number): Promise<void>;
  deductInventory(client: PoolClient, itemId: string, quantity: number): Promise<void>;
  createOrder(client: PoolClient, orderData: { userId: string; itemId: string; amount: number }): Promise<string>;
}

export class OrderRepository implements IOrderRepository {
  async deductUserBalance(client: PoolClient, userId: string, amount: number): Promise<void> {
    // SELECT FOR UPDATE mengunci baris data untuk mencegah race condition (pembelian ganda)
    const res = await client.query(
      `UPDATE users 
       SET balance = balance - $1 
       WHERE id = $2 AND balance >= $1 
       RETURNING id`,
      [amount, userId]
    );

    if (res.rowCount === 0) {
      throw new Error('Saldo tidak mencukupi atau user tidak ditemukan.');
    }
  }

  async deductInventory(client: PoolClient, itemId: string, quantity: number): Promise<void> {
    const res = await client.query(
      `UPDATE inventory 
       SET stock = stock - $1 
       WHERE item_id = $2 AND stock >= $1 
       RETURNING item_id`,
      [quantity, itemId]
    );

    if (res.rowCount === 0) {
      throw new Error('Stok barang habis.');
    }
  }

  async createOrder(
    client: PoolClient, 
    orderData: { userId: string; itemId: string; amount: number }
  ): Promise<string> {
    const res = await client.query(
      `INSERT INTO orders (user_id, item_id, total_amount, status, created_at) 
       VALUES ($1, $2, $3, 'COMPLETED', NOW()) 
       RETURNING id`,
      [orderData.userId, orderData.itemId, orderData.amount]
    );
    return res.rows[0].id;
  }
}
```

#### File: `src/modules/order/order.service.ts`
```ts
import { Pool } from 'pg';
import { IOrderRepository } from './order.repository';
import { CreateOrderDTO } from './order.dto';

export class OrderService {
  constructor(
    private readonly pool: Pool,
    private readonly orderRepo: IOrderRepository
  ) {}

  async checkoutAtomic(dto: CreateOrderDTO): Promise<{ orderId: string }> {
    // Acquire dedicated connection for transaction
    const client = await this.pool.connect();

    try {
      // Set Isolation Level & Begin Transaction
      await client.query('BEGIN ISOLATION LEVEL READ COMMITTED');

      // 1. Eksekusi pemotongan saldo
      await this.orderRepo.deductUserBalance(client, dto.userId, dto.amount);

      // 2. Eksekusi alokasi stok gudang
      await this.orderRepo.deductInventory(client, dto.itemId, dto.quantity);

      // 3. Simpan entitas order
      const orderId = await this.orderRepo.createOrder(client, {
        userId: dto.userId,
        itemId: dto.itemId,
        amount: dto.amount,
      });

      // 4. Commit transaksi jika semua langkah berhasil
      await client.query('COMMIT');
      return { orderId };

    } catch (error) {
      // Rollback mutlak untuk mencegah dirty write / state inkonsisten
      await client.query('ROLLBACK');
      throw error;
    } finally {
      // WAJIB: Selalu kembalikan client ke pool terlepas dari hasil transaksi
      client.release();
    }
  }
}
```

#### File: `src/modules/order/order.controller.ts`
```ts
import { Request, Response } from 'express';
import { OrderService } from './order.service';
import { CreateOrderSchema } from './order.dto';

export class OrderController {
  constructor(private readonly orderService: OrderService) {}

  public handleCheckout = async (req: Request, res: Response): Promise<void> => {
    try {
      // Validasi Payload
      const parseResult = CreateOrderSchema.safeParse(req.body);
      if (!parseResult.success) {
        res.status(400).json({
          status: 'FAIL',
          errors: parseResult.error.flatten().fieldErrors,
        });
        return;
      }

      const result = await this.orderService.checkoutAtomic(parseResult.data);
      res.status(201).json({
        status: 'SUCCESS',
        data: result,
      });
    } catch (error: any) {
      // Mapping business exception ke HTTP status code
      res.status(422).json({
        status: 'ERROR',
        message: error.message || 'Terjadi kesalahan internal pada proses pemesanan.',
      });
    }
  };
}
```

#### File: `src/app.ts` (Entrypoint & Graceful Shutdown)
```ts
import express, { Express } from 'express';
import { Server } from 'http';
import { Database } from './infrastructure/database';
import { OrderRepository } from './modules/order/order.repository';
import { OrderService } from './modules/order/order.service';
import { OrderController } from './modules/order/order.controller';

const app: Express = express();
app.use(express.json());

// Inisialisasi Database Pool
const pool = Database.initialize();

// Wiring Dependencies (Dependency Injection manual)
const orderRepo = new OrderRepository();
const orderService = new OrderService(pool, orderRepo);
const orderController = new OrderController(orderService);

// Health check endpoints
app.get('/health/live', (req, res) => res.status(200).send('OK'));
app.get('/health/ready', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.status(200).send('READY');
  } catch {
    res.status(503).send('DB_UNAVAILABLE');
  }
});

// Routes
app.post('/api/v1/orders/checkout', orderController.handleCheckout);

const PORT = process.env.PORT || 3000;
const server: Server = app.listen(PORT, () => {
  console.log(`Application worker running on port ${PORT}`);
});

// ============================================================================
// GRACEFUL SHUTDOWN LIFECYCLE
// ============================================================================
let isShuttingDown = false;

async function terminateProcess(signal: string) {
  if (isShuttingDown) return;
  isShuttingDown = true;
  console.log(`\nSignal ${signal} diterima. Memulai proses graceful shutdown...`);

  // Force close jika proses melebihi timeout yang ditentukan (misal: 10 detik)
  const forceExitTimer = setTimeout(() => {
    console.error('Graceful shutdown timeout tercapai. Menghentikan paksa!');
    process.exit(1);
  }, 10000);

  // Jangan tahan event loop dengan timer ini jika semua operasi lain sudah selesai
  forceExitTimer.unref();

  // 1. Hentikan penerimaan request HTTP baru
  server.close(async (err) => {
    if (err) {
      console.error('Error saat menutup HTTP server:', err);
      process.exit(1);
    }
    console.log('HTTP Server berhenti menerima koneksi baru.');

    try {
      // 2. Tutup koneksi Database Pool (menunggu query aktif selesai)
      await Database.close();
      console.log('Graceful teardown selesai tanpa insiden.');
      process.exit(0);
    } catch (dbErr) {
      console.error('Gagal menutup database connection pool:', dbErr);
      process.exit(1);
    }
  });
}

// Trap Sinyal Terminasi OS
process.on('SIGTERM', () => terminateProcess('SIGTERM'));
process.on('SIGINT', () => terminateProcess('SIGINT'));
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale "Double-Spending" & Connection Starvation
* **Profil Sistem:** Platform e-commerce menjual 1.000 unit smartphone dengan harga promosi. Trafik mencapai 12.000 requests per detik pada detik pertama peluncuran.
* **Gejala:** 
  1. Terjual 1.142 unit smartphone padahal stok fisik hanya 1.000 (Overselling / Data Corruption).
  2. Latensi API melonjak dari 45ms ke 18.000ms, diikuti kegagalan massal *HTTP 504 Gateway Timeout*.
  3. Database PostgreSQL mengalami status *OutOfMemory (OOM)* dan dihentikan oleh kernel Linux.

### Root Cause Analysis (RCA)
1. **Overselling:** Query validasi dan eksekusi dipisah tanpa baris penguncian atomik:
   ```sql
   -- DUA SESI BERBEDA MEMBACA STOK 1 PADA WAKTU BERSAMAAN
   SELECT stock FROM inventory WHERE item_id = 10; -- Mengembalikan 1
   -- Sesi A dan Sesi B keduanya melihat stok = 1, sehingga keduanya menjalankan:
   UPDATE inventory SET stock = stock - 1 WHERE item_id = 10;
   -- Hasil: Stok menjadi -1!
   ```
2. **Koneksi Membengkak:** Aplikasi menggunakan *default connection pool size* 100 per instance. Karena ada 30 kontiner aplikasi yang dijalankan di bawah Kubernetes, total koneksi potensial mencapai 3.000. PostgreSQL hanya dikonfigurasi menerima 500 koneksi (`max_connections = 500`). Akibatnya, koneksi DB habis, request tertahan di antrean memori aplikasi, dan seluruh worker Node.js kehabisan RAM.

### Solusi Arsitektural yang Diterapkan
1. **Atomic Guarding & Row-Level Locking:** Mengubah alur update menggunakan kondisional langsung:
   ```sql
   UPDATE inventory SET stock = stock - $1 WHERE item_id = $2 AND stock >= $1;
   ```
   Atau menggunakan sintaks `SELECT ... FOR UPDATE` dalam transaksi.
2. **Kapasitas Pool yang Dikalibrasi:** Menggunakan rumus koneksi PostgreSQL:
   $$\text{Pool Size} = ((\text{Core CPU DB} \times 2) + \text{Disk Spindle Count})$$
   Jika server DB memiliki 8 Core SSD: $Pool \approx (8 \times 2) + 1 = 17$ koneksi per instance backend. Jika ada 10 instance, masing-masing instance dialokasikan pool sebesar 5 hingga 10 koneksi.
3. **Database Proxy:** Memasang **PgBouncer** di depan PostgreSQL sebagai *Transaction-Level Connection Pooler* independen.

---

## 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya & Kompensasi (Trade-offs) |
| :--- | :--- | :--- |
| **Layered Clean Architecture** | Kode modular, decoupled, pengujian unit mudah via mock, maintainability tinggi. | *Boilerplate* tinggi, kurva belajar tim pemula meningkat, over-engineering untuk CRUD sederhana. |
| **Tingkat Isolasi: Serializable** | Integritas data sempurna, mencegah segala bentuk anomali konkurensi. | *Throughput* drop signifikan. Sering terjadi kegagalan transaksi (*serialization failure* 40001) yang menuntut logika *retry* otomatis di level aplikasi. |
| **Tingkat Isolasi: Read Committed** | Performa sangat tinggi, penguncian minimal, default aman untuk mayoritas kasus web. | Rentan terhadap *Non-Repeatable Reads* dan *Phantom Reads* jika tidak ditangani dengan manual row-level lock (`FOR UPDATE`). |
| **Ukuran Connection Pool Besar** | Mengurangi antrean request saat terjadi lonjakan trafik jangka pendek. | Mengonsumsi RAM server DB secara masif, meningkatkan *context switching* CPU PostgreSQL, berisiko melampaui `max_connections`. |
| **Ukuran Connection Pool Kecil** | DB stabil, penggunaan memori terkontrol, cache CPU bekerja optimal. | Latensi HTTP meningkat drastis (*queuing delay*) jika throughput aplikasi melebihi kapasitas pemrosesan query. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The "Orphaned Client" Leak
* **Gejala:** Aplikasi berjalan lancar selama 2 jam, lalu tiba-tiba seluruh API timeout serentak. Metrik database menunjukkan `active connections` mencapai limit maksimal tanpa aktivitas kueri aktif.
* **Penyebab:** Lupa memanggil `client.release()` di dalam blok `finally`.
* **Solusi/Deteksi:** Audit kode untuk memastikan setiap pemanggilan `pool.connect()` selalu dibungkus pola:
  ```ts
  const client = await pool.connect();
  try {
    // operations
  } finally {
    client.release(); // Jaminan mutlak eksekusi
  }
  ```

### 2. Nesting Transactions
* **Gejala:** Query error: `WARNING: there is already a transaction in progress`.
* **Penyebab:** Service A memanggil Service B. Service A membuka `BEGIN`, dan Service B juga mengeksekusi `BEGIN` pada koneksi yang sama. SQL standar tidak mendukung nested transaction secara langsung (membutuhkan `SAVEPOINT`).
* **Solusi:** Gunakan pola *Unit of Work* atau teruskan objek `client` yang ada tanpa memicu perintah `BEGIN` ulang jika konteks transaksi sudah aktif.

### 3. Docker Container Kill Timeout (Zombie Processes)
* **Gejala:** Saat deploy rilis baru, klien mengalami error `502 Bad Gateway` selama 5-10 detik.
* **Penyebab:** Aplikasi berjalan sebagai PID 1 di dalam kontiner tanpa *init process* (seperti `tini` atau `dumb-init`) dan tidak menangani `SIGTERM`, sehingga Docker menunggu 10 detik sebelum mengirimkan `SIGKILL` (pembunuhan paksa proses).
* **Solusi:** Tambahkan handler `process.on('SIGTERM')` seperti pada bab 7.2 dan gunakan dumb-init pada Dockerfile.

---

## 11. Best Practices (Production Checklist)

- [ ] **Pool Sizing Math:** Pool size dihitung berdasarkan kapasitas core database, bukan tebakan acak.
- [ ] **Mandatory Acquire Timeouts:** Nilai `connectionTimeoutMillis` tidak boleh dibiarkan tak terhingga (default aman: 3000ms - 5000ms).
- [ ] **Explicit Releases:** Setiap pengambilan klien transaksional harus berada dalam blok `try ... finally`.
- [ ] **Graceful Termination Handlers:** Menangani sinyal `SIGINT` dan `SIGTERM` secara eksplisit.
- [ ] **Contextual Logging:** Setiap baris log kueri lambat mencantumkan `userId`, `requestId`, dan `duration_ms`.
- [ ] **Segregated Health Probes:** 
  - Liveness Probe (`/health/live`): Hanya memeriksa apakah proses Node.js masih merespons event loop (tidak boleh query ke database).
  - Readiness Probe (`/health/ready`): Memeriksa konektivitas jaringan ke pool database (`SELECT 1`).
- [ ] **Defensive Row Updates:** Gunakan klausa `AND balance >= amount` pada query `UPDATE` untuk validasi konkurensi di tingkat database engine.

---

## 12. Hands-on Practice

Target path praktikum: `hands-on/m02/`

### Langkah 1: Setup Workspace & Dependencies
Jalankan instruksi berikut pada terminal Anda:

```bash
mkdir -p hands-on/m02 && cd hands-on/m02
npm init -y
npm install express pg dotenv zod
npm install --save-dev typescript @types/express @types/pg @types/node ts-node
npx tsc --init
```

### Langkah 2: Setup Database via Docker Compose
Buat file `docker-compose.yml`:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    container_name: m02-postgres
    environment:
      POSTGRES_USER: enterprise_user
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: core_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

Jalankan container:
```bash
docker compose up -d
```

### Langkah 3: Inisialisasi Skema Database (DDL)
Jalankan skrip SQL berikut untuk membuat skema yang aman:

```bash
docker exec -i m02-postgres psql -U enterprise_user -d core_db << 'EOF'
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    balance NUMERIC(15, 2) NOT NULL CHECK (balance >= 0)
);

CREATE TABLE inventory (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(50) UNIQUE NOT NULL,
    stock INT NOT NULL CHECK (stock >= 0)
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    item_id UUID REFERENCES inventory(item_id),
    total_amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed Data Awal
INSERT INTO users (id, name, balance) VALUES 
('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Budi Santoso', 500000.00);

INSERT INTO inventory (item_id, sku, stock) VALUES 
('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'PHONE-X', 5);
EOF
```

### Langkah 4: Tulis Kode Aplikasi
Salin implementasi kode dari Bagian **7.2 Practical Example** ke dalam sub-folder `src/` di dalam direktori `hands-on/m02/`.

### Langkah 5: Eksekusi dan Verifikasi
Jalankan aplikasi:
```bash
npx ts-node src/app.ts
```

Uji transaksi berhasil via curl (Terminal lain):
```bash
curl -X POST http://localhost:3000/api/v1/orders/checkout \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "itemId": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
    "amount": 100000,
    "quantity": 1
  }'
```

Uji kegagalan atomik (Rollback validation) dengan meminta quantity melampaui stok:
```bash
curl -X POST http://localhost:3000/api/v1/orders/checkout \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "itemId": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
    "amount": 100000,
    "quantity": 999
  }'
```

Periksa integritas data di DB: Pastikan saldo user **TIDAK TERPOTONG** akibat kegagalan stok.
```bash
docker exec -i m02-postgres psql -U enterprise_user -d core_db -c "SELECT * FROM users;"
```

---

## 13. Exercise

### Level Easy
Ubah file `src/infrastructure/database.ts` agar membaca konfigurasi database dari environment variables menggunakan pustaka `dotenv`. Tambahkan penanganan error jika variabel `DB_HOST` atau `DB_PASSWORD` tidak terdefinisi di runtime.
* **Kriteria Penerimaan:** Aplikasi langsung melempar exception deskriptif saat booting jika konfigurasi env wajib tidak tersedia.

### Level Medium
Tambahkan *Request Logging Middleware* yang mencatat setiap request HTTP yang masuk dengan:
1. Menghasilkan identifier unik (`X-Request-ID` berbasis UUIDv4) jika klien tidak menyediakannya.
2. Mencatat waktu eksekusi request dalam satuan milidetik (`duration_ms`).
3. Mencegah logging untuk path `/health/live` agar log file tidak penuh (*log flooding*).
* **Kriteria Penerimaan:** Header `X-Request-ID` berhasil terkirim balik ke response header klien, dan baris log tercetak rapi dalam format JSON terstruktur.

### Level Hard
Implementasikan skenario *Deadlock Detection & Retry Mechanism* pada `OrderService`.
1. Simulasikan skenario di mana dua transaksi berjalan bersamaan dan saling menunggu kunci tabel/baris yang berlawanan.
2. Tangkap error berkode `40P01` (deadlock detected) dari PostgreSQL.
3. Buat wrapper fungsi yang secara otomatis mencoba ulang (*retry*) transaksi tersebut hingga maksimal 3 kali percobaan dengan interval waktu acak (*exponential backoff + jitter*).
* **Kriteria Penerimaan:** Jika terjadi deadlock, transaksi tidak langsung melempar 500/422 ke klien, melainkan berhasil dieksekusi pada iterasi retry berikutnya.

---

## 14. Challenge

### High-Concurrency Wallet Transfer Engine

**Skenario Sistem:**
Anda ditugaskan mendesain mesin transfer saldo antar-pengguna (P2P Transfer) untuk bank digital berskala nasional. 

**Spesifikasi Persyaratan:**
1. Endpoint: `POST /api/v1/wallets/transfer`
2. Parameter: `sourceWalletId`, `targetWalletId`, `amount`.
3. Keamanan Tingkat Konkurensi: Sistem harus mampu menerima dua request transfer silang yang terjadi pada waktu bersamaan:
   * **Request 1:** Dompet A mentransfer Rp 50.000 ke Dompet B.
   * **Request 2:** Dompet B mentransfer Rp 50.000 ke Dompet A.
4. Tantangan Teknis: Jika kedua transaksi melakukan penguncian baris (`SELECT ... FOR UPDATE`) dengan urutan yang berbeda (A lalu B, sementara transaksi lain B lalu A), PostgreSQL akan mengalami kebuntuan fatal (*Deadlock Exception*).

**Tugas Anda:**
Rancang strategi urutan alokasi kunci (*deterministic locking order* / *resource sorting*) dan implementasikan modul transfer tersebut tanpa pernah memicu deadlock sama sekali pada beban 500 permintaan konkuren paralel. Validasi bahwa tidak ada saldo yang tercipta dari ketiadaan atau menghilang di tengah jalan. Solusi tidak disediakan secara langsung—lakukan eksperimen dan evaluasi performa kode Anda.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic

#### Q1: Apa perbedaan utama antara `pool.query()` dan `client.query()` pada pustaka Node.js `pg`?
* **Jawaban:** `pool.query()` secara otomatis mengambil satu koneksi bebas dari pool, menjalankan kueri, dan langsung mengembalikannya kembali ke pool dalam satu pemanggilan terisolasi. Sedangkan `client.query()` dieksekusi pada instans koneksi spesifik yang diambil secara manual via `pool.connect()`. `client.query()` wajib digunakan saat mengeksekusi multi-query transaksional (`BEGIN ... COMMIT`) agar seluruh operasi terikat pada satu koneksi fisik yang sama.

#### Q2: Mengapa kita tidak boleh membuka koneksi database baru (`new Client()`) pada setiap request HTTP masuk?
* **Jawaban:** Membuka koneksi database baru membutuhkan proses inisialisasi jaringan TCP three-way handshake, TLS negotiation, alokasi memori proses backend pada server database, dan autentikasi. Di bawah beban trafik tinggi, ini akan membebani CPU database hingga 100%, menghabiskan *file descriptors*, dan menyebabkan latensi masif akibat *connection storm*.

#### Q3: Apa fungsi dari blok `finally` dalam manajemen transaksi database?
* **Jawaban:** Memastikan instruksi pembersihan—khususnya `client.release()`—selalu dieksekusi dalam kondisi apapun, baik saat transaksi sukses di-*commit* maupun ketika terjadi error fatal yang memicu *rollback*. Tanpa blok `finally`, aplikasi akan mengalami kebocoran koneksi (*connection leak*).

#### Q4: Apa perbedaan antara sinyal sistem operasi `SIGTERM` dan `SIGKILL`?
* **Jawaban:** `SIGTERM` adalah sinyal terminasi sopan yang meminta proses berhenti, memberikan kesempatan bagi aplikasi untuk menyelesaikan request aktif, menutup file, dan membereskan koneksi database. `SIGKILL` adalah penghentian paksa oleh kernel OS yang langsung mematikan proses seketika tanpa memberi kesempatan pembersihan resource sama sekali.

#### Q5: Mengapa probe Liveness (`/health/live`) TIDAK boleh mengecek konektivitas database?
* **Jawaban:** Karena jika database mengalami lonjakan beban atau down sementara, seluruh probe Liveness kontiner aplikasi akan gagal. Akibatnya, orkestrator seperti Kubernetes akan me-restart seluruh kontiner aplikasi secara serentak. Ini memicu *cascading failure* (thundering herd problem) yang memperparah beban database alih-alih memberinya waktu pemulihan. Liveness hanya bertugas mengecek apakah runtime aplikasi masih berjalan hidup.

---

### 5 Pertanyaan Intermediate

#### Q6: Kapan fenomena *Non-Repeatable Read* terjadi, dan pada tingkat isolasi mana fenomena tersebut mulai dicegah?
* **Jawaban:** Terjadi ketika Transaksi A membaca sebuah baris data, kemudian Transaksi B mengubah (UPDATE) baris data tersebut dan melakukan COMMIT. Saat Transaksi A membaca kembali baris yang sama, nilainya telah berubah. Fenomena ini diizinkan pada level *Read Committed*, dan mulai dicegah secara mutlak pada level isolasi *Repeatable Read*.

#### Q7: Mengapa query update berikut lebih aman terhadap race condition dibanding pendekatan `SELECT` lalu `UPDATE` di level aplikasi?
```sql
UPDATE inventory SET stock = stock - 1 WHERE item_id = $1 AND stock >= 1;
```
* **Jawaban:** Karena PostgreSQL mengeksekusi kueri tersebut secara atomik di dalam engine. Kueri tersebut mengambil row-level lock pada baris item target selama durasi update, mengevaluasi klausa `stock >= 1` secara langsung di engine DB pada data paling mutakhir, sehingga tidak ada thread/request lain yang bisa menyela di antara pengecekan stok dan modifikasi nilai.

#### Q8: Apa yang dimaksud dengan *Connection Pool Starvation*, dan bagaimana cara mendeteksinya melalui metrik aplikasi?
* **Jawaban:** Kondisi di mana seluruh koneksi di dalam pool sedang berstatus sibuk (*active*), dan antrean request yang menunggu koneksi (*waiting queue*) terus menumpuk hingga melebihi nilai `connectionTimeoutMillis`. Metrik deteksinya: grafik *Pool Waiting Requests Count* melonjak tinggi, *Active Connections* mentok di batas maksimum, dan latensi API melonjak drastis disertai lonjakan error *Timeout acquiring connection*.

#### Q9: Pada arsitektur berlapis, mengapa Layer Repository tidak boleh mengetahui objek `Request` atau `Response` dari Express/Fastify?
* **Jawaban:** Untuk menjaga prinsip *Separation of Concerns* (pemisahan tanggung jawab). Lapisan Repository bertugas murni mengabstraksi akses basis data. Jika ia bergantung pada HTTP Context (`Request`/`Response`), kode tersebut tidak akan bisa digunakan kembali pada konteks non-HTTP seperti Message Queue Worker, background CLI script, atau unit test.

#### Q10: Bagaimana mekanisme *Readiness Probe* melindungi sistem dari kegagalan berantai saat database restart?
* **Jawaban:** Ketika database sedang restart, endpoint *Readiness Probe* (`/health/ready`) akan merespons dengan HTTP 503 (Unhealthy). Load balancer atau Ingress Controller akan secara otomatis mencabut kontiner aplikasi tersebut dari daftar routing trafik aktif. Request dari klien luar tidak akan diteruskan ke instance tersebut hingga database kembali sehat dan probe kembali mengembalikan status 200 OK.

---

### 3 Skenario Kasus Produksi

#### Kasus 1: "The Silent Pool Exhaustion"
* **Insiden:** Sebuah sistem portal berita mengalami downtime setiap kali ada artikel viral. Analisis log menunjukkan CPU aplikasi dan database berada di bawah 20%, memori aman, namun seluruh request API baru mengalami *error 500 (Timeout: could not acquire client from pool)*.
* **Pemeriksaan Kode:**
  ```ts
  async function trackAnalytics(articleId: string) {
    const client = await pool.connect();
    const metric = await client.query('SELECT views FROM analytics WHERE article_id = $1', [articleId]);
    if (metric.rowCount === 0) {
      // Artikel belum ada, batalkan pencatatan
      return; 
    }
    await client.query('UPDATE analytics SET views = views + 1 WHERE article_id = $1', [articleId]);
    client.release();
  }
  ```
* **Analisis & Mitigasi:**
  1. *Akar Masalah:* Pada baris `if (metric.rowCount === 0) return;`, fungsi keluar tanpa memanggil `client.release()`. Setiap kali ada artikel yang belum memiliki metrik, satu koneksi terbuang secara permanen (*leaked*). Pada artikel viral baru, ribuan request masuk dan menghabiskan seluruh pool dalam hitungan detik.
  2. *Solusi:* Pindahkan pelepasan koneksi ke dalam blok `finally`, atau hapus penggunaan `pool.connect()` manual dan ganti menggunakan satu perintah kueri atomik `pool.query('INSERT ... ON CONFLICT DO UPDATE ...')`.

#### Kasus 2: "The Ghost Inventory Bug"
* **Insiden:** Flash sale produk edisi terbatas menyebabkan inventaris barang di database mencatat angka `-12`. Pengguna yang memesan di akhir menuntut kompensasi karena pesanan mereka dibatalkan sepihak secara manual oleh tim operasional.
* **Pemeriksaan Kode:**
  Aplikasi menggunakan isolation level default *Read Committed*. Transaksi checkout membaca stok:
  ```ts
  const item = await client.query('SELECT stock FROM items WHERE id = $1', [itemId]);
  if (item.rows[0].stock > 0) {
    await sleep(50); // Simulasi pemanggilan Payment Gateway pihak ketiga
    await client.query('UPDATE items SET stock = stock - 1 WHERE id = $1', [itemId]);
  }
  ```
* **Analisis & Mitigasi:**
  1. *Akar Masalah:* Waktu tunggu eksternal (`sleep 50`) berada di dalam blok pengecekan. Puluhan request masuk secara paralel pada saat stok tersisa 1. Seluruh request membaca nilai stok yang sama (yaitu 1), melewati percabangan `if`, lalu masing-masing menjalankan perintah pemotongan stok.
  2. *Solusi:*
     - Jangan pernah melakukan panggilan API pihak ketiga (jaringan lambat) di dalam transaksi database aktif.
     - Tambahkan batasan integritas skema database: `ALTER TABLE items ADD CONSTRAINT stock_non_negative CHECK (stock >= 0);`. Database akan secara mutlak menolak angka di bawah 0.
     - Gunakan mekanisme pemotongan berbasis conditional update atau lock baris dengan `SELECT ... FOR UPDATE` sebelum verifikasi dilakukan.

#### Kasus 3: "Deployment 502 Spikes"
* **Insiden:** Tim DevOps melakukan deployment versi baru aplikasi menggunakan strategi Kubernetes Rolling Update. Setiap kali pods lama dihentikan, pengguna melaporkan lonjakan insiden *502 Bad Gateway* selama sekitar 2 hingga 5 detik.
* **Pemeriksaan Setup:**
  Aplikasi Express dijalankan langsung via node tanpa menangani POSIX signal:
  ```ts
  app.listen(3000);
  ```
* **Analisis & Mitigasi:**
  1. *Akar Masalah:* Saat Kubernetes menghentikan Pod lama, Kubernetes mengirim sinyal `SIGTERM` ke kontiner. Karena aplikasi Node.js tidak memasang listener sinyal, runtime menggunakan tindakan bawaan (langsung keluar seketika / abrupt exit). Koneksi HTTP yang sedang melayani request aktif klien langsung putus di tengah transmisi data, sehingga reverse proxy (Nginx/Ingress) mencatat status `502 Bad Gateway`.
  2. *Solusi:*
     - Terapkan mekanisme *Graceful Shutdown* menggunakan `server.close()` untuk menuntaskan request yang sedang terbang (*in-flight requests*).
     - Tambahkan delay pra-terminasi (*preStop hook* di Kubernetes manifests) selama 3-5 detik untuk memberi waktu Ingress Controller menghapus IP pod dari daftar endpoint upstream sebelum proses aplikasi mulai ditutup.

---

## 16. Summary

1. **Arsitektur Berlapis (Layered Architecture)** memisahkan logika antarmuka (Controller), aturan bisnis (Service), dan penyimpanan data (Repository) untuk menjamin kode dapat dirawat, diuji, dan dievolusi tanpa saling merusak.
2. **Koneksi Database adalah Sumber Daya Terbatas.** Penggunaan *Connection Pooling* wajib dikalibrasi sesuai daya komputasi fisik server basis data. Kegagalan membebaskan koneksi di dalam blok `finally` adalah penyebab utama downtime akibat kelaparan koneksi (*pool exhaustion*).
3. **Integritas Data Transaksional** tidak boleh diserahkan pada asumsi eksekusi sekuensial kode aplikasi. Pemanfaatan transaksi atomik (`BEGIN ... COMMIT / ROLLBACK`), penanganan batas isolasi ACID, serta penguncian baris (`FOR UPDATE` / conditional update) adalah benteng pertahanan mutlak terhadap anomali konkurensi.
4. **Keandalan Sistem Produksi** menuntut aplikasi yang paham siklus hidupnya sendiri: mampu memberikan diagnosis status kesehatan internal via *Liveness/Readiness probes* dan mampu mati secara teratur (*Graceful Teardown*) tanpa merusak request klien yang sedang berjalan.