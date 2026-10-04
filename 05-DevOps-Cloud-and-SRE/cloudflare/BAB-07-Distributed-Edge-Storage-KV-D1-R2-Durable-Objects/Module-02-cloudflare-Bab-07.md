# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: Distributed Edge Storage (KV, D1, R2, Durable Objects)**
**Kategori: 05-DevOps-Cloud-and-SRE**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Karakteristik Konsistensi & Latensi**: Menguraikan perbedaan mendasar antara model konsistensi *eventual* (KV), *read-replicated relational* (D1), *blob object store* (R2), dan *strictly linearizable actor-based state* (Durable Objects).
- **Merancang Arsitektur Penyimpanan Multi-Tier di Edge**: Mengombinasikan keempat pilar penyimpanan Cloudflare untuk membangun sistem terdistribusi skala enterprise yang tahan terhadap latensi tinggi dan lonjakan lalu lintas (*flash crowd*).
- **Mengimplementasikan Durable Objects dengan Storage SQLite Terintegrasi**: Menggunakan Durable Objects modern berbasis SQLite untuk konkurensi atomik, stateful coordination, dan sistem transaksi terisolasi.
- **Mengoptimasi Read/Write Throughput & Cost**: Mereduksi write-amplification, mengeliminasi biaya *egress* dengan R2, dan mengeksploitasi *read replication* D1 serta *tiered cache* Workers KV.
- **Mengeksekusi Mitigasi Kegagalan & Disaster Recovery**: Menerapkan pola Point-in-Time Recovery (PITR) pada D1, versioning & lifecycle pada R2, serta snapshotting state pada Durable Objects.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Cloudflare Workers Runtime Core**: Lifecycle eksekusi V8 Isolates, Fetch API, Environment Bindings, dan Event Context.
- **Sistem Terdistribusi Dasar**: Pemahaman CAP Theorem, PACELC Theorem, model konsistensi data (*Linearizable, Sequential, Eventual Consistency*).
- **TypeScript Tingkat Lanjut**: Generic types, Async/Await concurrency, buffer manipulation (`ArrayBuffer`, `ReadableStream`).
- **SQL & Relational Modeling**: Normalisasi database, index profiling, isolasi transaksi ACID.
- **Wrangler CLI**: Konfigurasi multi-environment via `wrangler.jsonc` / `wrangler.toml` dan eksekusi deployment migrasi skema.

---

## 3. Concept & Internal Architecture (Mendalam)

Penyimpanan data di edge bukan merupakan satu sistem universal, melainkan spektrum trade-off antara latensi, kapasitas, dan konsistensi data. Cloudflare menyediakan empat lapisan penyimpanan komplementer:

```
+-----------------------------------------------------------------------------------+
|                        CLOUDFLARE GLOBAL ANYCAST NETWORK                          |
|                                                                                   |
|  +-------------------+  +--------------------+  +------------------------------+  |
|  |    Workers KV     |  |         D1         |  |       Durable Objects        |  |
|  | (Global Read Rep) |  | (Distributed R-DB) |  |   (Linearizable Actor/RAM)   |  |
|  +-------------------+  +--------------------+  +------------------------------+  |
|            |                      |                            |                  |
|            v                      v                            v                  |
|  +-----------------------------------------------------------------------------+  |
|  |                                  R2                                         |  |
|  |                 (Zero-Egress Object Storage / Blob Engine)                  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### A. Workers KV (Distributed Key-Value Engine)
- **Topologi Penyimpanan**: KV didesain untuk pola *high-read, low-write*. Data disimpan secara terpusat di kluster storage utama Cloudflare, namun metadata dan data hot di-cache secara agresif di ribuan PoP (*Points of Presence*) menggunakan arsitektur *two-tier caching*: Local PoP RAM/NVMe dan Regional Tiered Cache.
- **Model Konsistensi**: *Eventual Consistency*. Perubahan data yang ditulis via API atau Worker memerlukan waktu propagasi secara global hingga 60 detik. Pembacaan di edge yang sama sesaat setelah penulisan mungkin masih menerima data stale jika cache lokal belum terinvalidasi.
- **Internal Mechanics**: Penyimpanan berbasis key-value sederhana dengan batas ukuran data 25 MiB per value, mendukung auto-expiration (TTL) native dan metadata terkompresi tanpa perlu deserialisasi payload utama.

### B. Cloudflare D1 (Serverless Relational SQLite)
- **Topologi Penyimpanan**: D1 mengabstraksikan SQLite murni di atas arsitektur serverless. Secara fisik, primary instance SQLite berada pada satu region (misal: Western Europe atau North America), sedangkan replika baca (*Read Replicas*) didistribusikan ke region lain secara transparan.
- **Model Konsistensi**: *Sequential Consistency for Writes*, *Read-Your-Own-Writes within a Session*, dan *Snapshot Isolation* untuk transaksi baca.
- **Replikasi & Transaksi**: Replikasi memanfaatkan streaming write-ahead log (WAL). Operasi penulisan dialihkan (*routed*) ke Primary D1 instance, sedangkan operasi pembacaan dialokasikan ke replica terdekat menggunakan session bookmarks untuk mencegah regresi data baca (*monotonic read guarantee*).

### C. Cloudflare R2 (S3-Compatible Object Store)
- **Topologi Penyimpanan**: R2 dibangun di atas infrastruktur penyimpanan multi-tenant terdistribusi global yang dioptimalkan untuk objek biner besar (unstructured data). Berbeda dari AWS S3, R2 tidak membebankan biaya *egress bandwidth*.
- **Model Konsistensi**: *Strong Read-After-Write Consistency* untuk operasi `PUT`, `GET`, `DELETE`, dan `LIST`.
- **Integrasi Engine**: R2 terintegrasi langsung dengan pipeline cache Cloudflare. Pengambilan file dari R2 melalui Worker dapat di-stream secara langsung tanpa perlu buffer penuh di memori V8 Isolate, menjaga jejak memori tetap di bawah batas 128 MiB runtime worker.

### D. Durable Objects (Distributed Actor Model with SQLite Engine)
- **Topologi Penyimpanan**: Durable Objects (DO) menjamin konsep **Single Point of Coordination**. Tiap instans ID dari DO dijalankan di tepat **satu** lokasi PoP global pada satu waktu (menggunakan algoritma routing internal terkoordinasi Cloudflare).
- **Model Konsistensi**: *Strict Serializability / Linearizability*. Seluruh request menuju ID DO yang sama akan diantrekan dan diproses secara terurut pada isolate yang sama.
- **Storage Subsystem**: Tiap instance DO memiliki private persistence engine berbasis SQLite. Karena isolate dan database lokal berjalan berdekatan di server yang sama, latensi operasi SQL berada pada sub-millisecond, memungkinkan transaksi ACID murni di edge tanpa penalti round-trip network.

---

## 4. Why & What

| Fitur / Parameter | Workers KV | Cloudflare D1 | Cloudflare R2 | Durable Objects (SQLite) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Data** | Key-Value Pairs | Relasional (SQL/Tables) | Unstructured Blob / Files | Stateful Actor + SQLite Tables |
| **Model Konsistensi**| Eventual (hingga 60s) | Read Replicas (Snapshot) | Strong Read-After-Write | Linearizable (ACID murni) |
| **Pola Akses Utama** | Ultra-high read, low write | Complex query, JOINs | File streaming, bulk asset | Real-time state, concurrency control |
| **Throughput Penulisan** | Max 1 write/sec per key | Terbatas kapasitas Primary | Skala tinggi secara horizontal| Terbatas CPU/disk 1 instance actor |
| **Kapasitas Maksimal** | Tak terbatas (25MB/val) | ~10 GB per database | Tak terbatas (5TB/objek) | Unlimited objects (10GB/instance) |
| **Zero Egress Fee** | Ya | Ya | Ya | Ya |

### Mengapa Mengombinasikan Keempatnya?
Tidak ada satupun engine edge storage yang mampu menangani semua pola akses. Sebuah aplikasi enterprise kelas global membutuhkan:
1. **Durable Objects**: Untuk mengunci stok inventaris flash sale, lelang real-time, atau status sinkronisasi kolaboratif multi-user (*high-contention state*).
2. **D1**: Untuk agregasi query SQL, filtering transaksi inventaris, dan audit trail relasional.
3. **Workers KV**: Untuk melayani katalog produk statis/semi-dinamis secara global dengan latensi sub-10ms tanpa membebani database utama.
4. **R2**: Untuk menyimpan gambar produk beresolusi tinggi, invoice PDF, dan snapshot backup state harian.

---

## 5. How (Workflow detail)

Berikut alur kerja integrasi multi-tier antara KV, D1, R2, dan Durable Objects dalam menangani transaksi e-commerce skala enterprise:

```
[Client Request]
       |
       v
+---------------+      Cache Hit
| Edge Worker   | ---------------------> [ Return KV Cache ] (sub-10ms)
| (Entrypoint)  |
+---------------+
       | Cache Miss
       v
+-----------------------------+
| Route via Routing Rule      |
+-----------------------------+
       |
       +---> [ Read Data ] --------> Query to [ D1 Read Replica ] (SQL query)
       |
       +---> [ Heavy Asset ] ------> Stream from [ R2 Storage Engine ] (No Egress)
       |
       +---> [ Write Transaction ]-> Forward to [ Durable Object Instance ]
                                          |
                                          +---> Execute In-Memory + SQLite Storage
                                          +---> Emit Audit Event to [ D1 Primary ]
                                          +---> Invalidate [ Workers KV Cache ]
```

1. **Routing Layer**: Worker entrypoint menerima request HTTPS di PoP terdekat dari klien.
2. **Read Phase (KV & D1)**:
   - Worker memeriksa Workers KV untuk mengambil metadata JSON produk.
   - Jika cache miss, Worker query ke D1. D1 Smart Routing secara otomatis mengarahkan query SELECT ke D1 Read Replica terdekat.
3. **Execution Phase (Durable Objects)**:
   - Operasi yang memerlukan proteksi konkurensi (misal: checkout stok terbatas) membuat stub ke Durable Object terdistribusi berdasarkan `productId`.
   - Durable Object memproses request secara serial/linearizable di SQLite lokalnya, mengeliminasi masalah *race condition* (over-selling).
4. **Storage & Eviction Phase**:
   - Durable Object memperbarui state lokal, mencatat riwayat transaksi ke D1 secara asinkron, meng-upload bukti transaksi ke R2, dan menginvalidasi KV cache produk terkait.

---

## 6. Analogy & Diagram ASCII

### Analogi Operasional
Bayangkan sebuah Bank Global:
- **Workers KV** adalah **Papan Pengumuman Suku Bunga di Cabang Bank**: Dilihat ribuan orang setiap detik, jarang diubah, dan jika kantor pusat menaikkan suku bunga, butuh sedikit waktu bagi kurir untuk mengganti papan di seluruh dunia.
- **Cloudflare D1** adalah **Buku Besar Akuntansi Pusat**: Memiliki banyak salinan cetak di setiap kantor cabang untuk audit dan pencarian laporan keuangan yang kompleks tanpa mengganggu kasir.
- **Cloudflare R2** adalah **Gudang Brankas Fisik**: Tempat dokumen fisik, arsip tebal, dan rekaman CCTV disimpan dengan kapasitas nyaris tanpa batas tanpa biaya tambahan saat keluar-masuk barang.
- **Durable Objects** adalah **Teller Kasir Khusus Nomor Antrean Unik**: Hanya ada satu meja spesifik di dunia untuk memvalidasi pemindahan rekening individual Anda. Tidak peduli berapa banyak orang berusaha mentransfer ke rekening Anda secara bersamaan, mereka harus mengantre di kasir yang satu ini, menjamin tidak ada uang yang dobel keluar.

### Diagram Alur Konkurensi Durable Objects vs D1 vs KV
```
KLIEN TOKYO        KLIEN LONDON        KLIEN NEW YORK
    |                   |                    |
    +---------\         |         /----------+
               \        |        /
                v   v   v   v   v
        +-------------------------------+
        |    Cloudflare Global Edge     |
        |        (Anycast PoP)          |
        +-------------------------------+
                        |
            Route to Target DO ID (e.g. "prod-4091")
                        |
                        v
        +-------------------------------+
        |   DURABLE OBJECT INSTANCE     | <--- Hosted at Single Region Isolates
        |  (Single-threaded Execution)  |
        |                               |
        |   +-----------------------+   |
        |   | Actor Mutex Execution |   | <--- Zero Race Condition
        |   +-----------------------+   |
        |               |               |
        |   +-----------------------+   |
        |   | SQLite Private Engine |   | <--- Sub-ms Atomic Transaction
        |   +-----------------------+   |
        +-------------------------------+
            |                       |
     (Async Flush)             (Asset Push)
            |                       |
            v                       v
    +---------------+       +---------------+
    |  D1 Database  |       |   R2 Bucket   |
    | (Audit Trail) |       | (Asset/Receipt|
    +---------------+       +---------------+
```

---

## 7. Simple Example & Practical Example

### A. Konfigurasi Terpusat (`wrangler.jsonc`)
File konfigurasi mendefinisikan binding untuk KV, D1, R2, dan Durable Objects modern (menggunakan SQLite in-DO).

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "enterprise-edge-storage",
  "main": "src/index.ts",
  "compatibility_date": "2024-11-01",
  "compatibility_flags": ["nodejs_compat"],
  "kv_namespaces": [
    {
      "binding": "CATALOG_KV",
      "id": "7b0b6c6b8c8d4e9ab1234567890abcdef"
    }
  ],
  "d1_databases": [
    {
      "binding": "AUDIT_DB",
      "database_name": "prod-audit-db",
      "database_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      "migrations_dir": "migrations"
    }
  ],
  "r2_buckets": [
    {
      "binding": "RECEIPTS_BUCKET",
      "bucket_name": "prod-financial-receipts"
    }
  ],
  "durable_objects": {
    "bindings": [
      {
        "name": "INVENTORY_COORDINATOR",
        "class_name": "InventoryCoordinator"
      }
    ]
  },
  "migrations": [
    {
      "tag": "v1",
      "new_sqlite_classes": ["InventoryCoordinator"]
    }
  ]
}
```

### B. Schema Migrasi D1 (`migrations/0001_init_audit.sql`)
```sql
CREATE TABLE IF NOT EXISTS inventory_audit_log (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    delta INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_audit_product ON inventory_audit_log(product_id, created_at DESC);
```

### C. Implementasi Kode Produksi (`src/index.ts`)
Mengintegrasikan Workers KV, D1, R2, dan Durable Object (SQLite) dalam TypeScript ketat.

```typescript
import { DurableObject } from "cloudflare:workers";

export interface Env {
  CATALOG_KV: KVNamespace;
  AUDIT_DB: D1Database;
  RECEIPTS_BUCKET: R2Bucket;
  INVENTORY_COORDINATOR: DurableObjectNamespace<InventoryCoordinator>;
}

interface OrderRequest {
  productId: string;
  quantity: number;
  userId: string;
}

// ============================================================================
// DURABLE OBJECT: CONCURRENCY CONTROLLER & IN-MEMORY/SQLITE STATE ENGINE
// ============================================================================
export class InventoryCoordinator extends DurableObject<Env> {
  private sql: SqlStorage;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.sql = this.ctx.storage.sql;
    
    // Inisialisasi skema SQLite privat di dalam Durable Object
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS stock (
        id TEXT PRIMARY KEY,
        quantity INTEGER NOT NULL,
        reserved INTEGER NOT NULL
      );
    `);
  }

  async initializeStock(productId: string, initialQuantity: number): Promise<void> {
    this.sql.exec(
      `INSERT INTO stock (id, quantity, reserved) 
       VALUES (?, ?, 0)
       ON CONFLICT(id) DO UPDATE SET quantity = excluded.quantity;`,
      productId,
      initialQuantity
    );
  }

  async reserveStock(productId: string, amount: number, userId: string): Promise<{ success: boolean; remaining: number }> {
    // Transaksi internal SQLite DO bersifat instan, atomik, dan sepenuhnya terisolasi
    const cursor = this.sql.exec<{ quantity: number; reserved: number }>(
      `SELECT quantity, reserved FROM stock WHERE id = ?;`,
      productId
    );
    const row = cursor.toArray()[0];

    if (!row) {
      throw new Error("PRODUCT_NOT_INITIALIZED");
    }

    const available = row.quantity - row.reserved;
    if (available < amount) {
      return { success: false, remaining: available };
    }

    const newReserved = row.reserved + amount;
    this.sql.exec(
      `UPDATE stock SET reserved = ? WHERE id = ?;`,
      newReserved,
      productId
    );

    // Asynchronously log audit trail ke D1 tanpa memblokir critical path DO
    this.ctx.waitUntil(this.logAudit(productId, -amount, row.quantity - newReserved, userId));

    return { success: true, remaining: row.quantity - newReserved };
  }

  private async logAudit(productId: string, delta: number, balance: number, userId: string): Promise<void> {
    const auditId = crypto.randomUUID();
    await this.env.AUDIT_DB.prepare(
      `INSERT INTO inventory_audit_log (id, product_id, operation, delta, balance_after, actor_id)
       VALUES (?, ?, 'RESERVATION', ?, ?, ?)`
    ).bind(auditId, productId, delta, balance, userId).run();
  }
}

// ============================================================================
// WORKER ENTRYPOINT: ROUTING, KV CACHING & BLOB HANDLING
// ============================================================================
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // 1. GET: Ambil detail produk (KV Read Layer dengan Fallback)
    if (request.method === "GET" && url.pathname.startsWith("/product/")) {
      const productId = url.pathname.split("/")[2];
      
      // Check Cache di Workers KV
      const cached = await env.CATALOG_KV.get(`catalog:${productId}`, { type: "json" });
      if (cached) {
        return Response.json({ source: "kv_cache", data: cached });
      }

      // Query D1 jika cache miss
      const product = await env.AUDIT_DB.prepare(
        `SELECT * FROM inventory_audit_log WHERE product_id = ? ORDER BY created_at DESC LIMIT 1`
      ).bind(productId).first();

      if (!product) {
        return new Response("Product Not Found", { status: 404 });
      }

      // Write-back ke KV Cache (TTL 60 detik)
      ctx.waitUntil(
        env.CATALOG_KV.put(`catalog:${productId}`, JSON.stringify(product), { expirationTtl: 60 })
      );

      return Response.json({ source: "d1_fallback", data: product });
    }

    // 2. POST: Inisialisasi Stok Produk (DO Mutasi)
    if (request.method === "POST" && url.pathname === "/product/init") {
      const body = await request.json<{ productId: string; stock: number }>();
      const doId = env.INVENTORY_COORDINATOR.idFromName(body.productId);
      const stub = env.INVENTORY_COORDINATOR.get(doId);

      await stub.initializeStock(body.productId, body.stock);
      return Response.json({ status: "INITIALIZED", productId: body.productId });
    }

    // 3. POST: Checkout Atomik Stok (DO Serial Execution)
    if (request.method === "POST" && url.pathname === "/order/checkout") {
      const order = await request.json<OrderRequest>();
      
      const doId = env.INVENTORY_COORDINATOR.idFromName(order.productId);
      const stub = env.INVENTORY_COORDINATOR.get(doId);

      const result = await stub.reserveStock(order.productId, order.quantity, order.userId);
      
      if (!result.success) {
        return Response.json(
          { error: "INSUFFICIENT_STOCK", remaining: result.remaining },
          { status: 409 }
        );
      }

      // 4. Generate Order Receipt langsung ke R2 Storage
      const receiptId = `receipt-${crypto.randomUUID()}.json`;
      const receiptData = JSON.stringify({
        receiptId,
        order,
        timestamp: new Date().toISOString(),
        allocatedStock: order.quantity
      });

      ctx.waitUntil(
        env.RECEIPTS_BUCKET.put(receiptId, receiptData, {
          httpMetadata: { contentType: "application/json" }
        })
      );

      return Response.json({
        status: "RESERVED",
        receiptId,
        remainingStock: result.remaining
      });
    }

    // 5. GET: Download Receipt dari R2 (Streaming Object Delivery)
    if (request.method === "GET" && url.pathname.startsWith("/receipt/")) {
      const receiptId = url.pathname.split("/")[2];
      const object = await env.RECEIPTS_BUCKET.get(receiptId);

      if (!object) {
        return new Response("Receipt Not Found", { status: 404 });
      }

      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set("etag", object.httpEtag);

      return new Response(object.body, { headers });
    }

    return new Response("Method/Path Not Allowed", { status: 405 });
  }
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Global Flash Sale & Ticketing System (Ticketing Platform)
- **Tantangan**: Penjualan 10.000 tiket konser secara global dalam kurun waktu 30 detik. Lonjakan trafik mencapai 150.000 request per detik (*req/sec*). Database relasional terpusat tradisional (e.g., Aurora PostgreSQL) selalu mengalami *lock contention*, koneksi jenuh, dan lonjakan latensi hingga 8000ms.
- **Solusi Arsitektur**:
  1. **Workers KV Layer**: Melayani detail acara, denah venue, dan metadata artis dari KV cache dengan hit-ratio 99.4%, menyerap 149.000 req/sec di edge tanpa membebani backend.
  2. **Durable Objects Sharding**: Alokasi tempat duduk dibagi per section (misal: Section-A, Section-B). Tiap section diatur oleh satu ID Durable Object tersendiri (`idFromName("concert-101-sec-A")`). Concurrency locking terjadi murni di memori RAM dan SQLite lokal instance DO tersebut.
  3. **R2 Invoicing**: Saat tiket sukses di-reserve, event Worker mem-publish stream pembuatan tiket/invoice PDF langsung ke R2 menggunakan presigned metadata. Zero egress cost menghemat biaya bandwidth hingga puluhan ribu dolar saat unduhan masal.
  4. **D1 Read Analysis**: Semua status final dipompa (*asynchronously batched*) dari Durable Objects ke D1 untuk kebutuhan dashboard analitik real-time panitia konser.
- **Hasil Metrik**:
  - P95 Latency: Turun dari 4.200ms ke **28ms**.
  - Over-selling incident: **0 tiket**.
  - Infrastruktur server crash: **0 downtime**.

---

## 9. Trade-offs (Analisis Komparatif)

| Aspek | Workers KV | Cloudflare D1 | Cloudflare R2 | Durable Objects |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput / Scale**| Sangat Tinggi (Global Edge Replication) | Tinggi untuk Read; Terbatas pada Primary Write | Sangat Tinggi (Auto-partitioning Blob) | Terbatas per Actor; Tak terbatas via Dynamic Sharding |
| **Write Latency** | Rendah di edge awal, lambat secara global | Menengah (~100-250ms via roundtrip ke Primary) | Menengah (~100-300ms tergantung region) | Ekstrem Rendah (<5ms jika isolate sudah aktif) |
| **Read Latency** | Ultra Rendah (<10ms via Local PoP Cache) | Rendah (<30ms via Read Replicas) | Menengah (~50-150ms First Byte) | Ekstrem Rendah (<2ms In-Memory Access) |
| **Cost Vector** | $0.50 / juta read, $5.00 / juta write | $0.75 / juta row write, $0.001 / juta row read | $0.015 / GB-month, Class A/B request, **$0 Egress** | CPU time duration + DO storage ($0.20 / GB-month) |
| **CAP Classification** | **AP** (Availability / Partition Tolerance) | **CP** dengan Session Read Guarantees | **CP** (Strong Consistency pada objek individual) | **CP** (Linearizable Consistency) |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Read-Your-Own-Writes Hazard pada Workers KV
- **Anti-pattern**: Worker menulis data ke KV (`await KV.put("user:123", data)`), kemudian langsung melakukan redirect atau fetch ulang dari KV dengan asumsi data baru sudah tersedia di seluruh PoP.
- **Dampak**: Inkonsistensi data tampilan. Pengguna mendapati profil lama karena PoP lokal masih memegang cache lama.
- **Solusi**: Jika alur kerja membutuhkan konsistensi instan, gunakan Durable Objects atau simpan write acknowledgement di cookie/session client sebelum terpropagasi.

### Mistake 2: DO Actor Bottleneck (Over-centralization)
- **Anti-pattern**: Menggunakan satu Durable Object ID tunggal (e.g., `idFromName("GLOBAL_STATE")`) untuk mencatat counter hit seluruh pengunjung website global.
- **Dampak**: Seluruh request global antre di satu V8 isolate single-threaded. CPU DO melonjak 100%, latensi membengkak, dan terjadi error `Worker exceeded CPU limit`.
- **Solusi**: Gunakan teknik **Actor Sharding / Partitioning**. Pecah counter ke 32 shard DO (`idFromName("counter_" + Math.floor(Math.random() * 32))`), lalu agregasikan di D1 atau read query saat dibutuhkan.

### Mistake 3: SQL N+1 Query Loops pada D1
- **Anti-pattern**: Melakukan query SELECT berulang dalam loop `for` via `await env.AUDIT_DB.prepare(...).run()`.
- **Dampak**: Setiap query non-batch memicu round-trip eksekusi statement internal SQLite, menyebabkan penalti latensi masif.
- **Solusi**: Gunakan `env.AUDIT_DB.batch([stmt1, stmt2, stmt3])` untuk mengeksekusi multiple prepared statements dalam satu siklus round-trip transaksional.

### Mistake 4: Unbuffered R2 Object Memory Exhaustion
- **Anti-pattern**: Membaca seluruh file R2 ke dalam memori via `await object.arrayBuffer()` sebelum mengirimkannya ke client.
- **Dampak**: Out of Memory (OOM) crash ketika ukuran file melebihi memory limit isolate (128 MiB).
- **Solusi**: Stream langsung body objek menggunakan `new Response(object.body, ...)`.

---

## 11. Best Practices (Production Checklist)

- [ ] **Data Partitioning**: Shard Durable Objects berdasarkan entity ID granular (misal: `orderId`, `tenantId`, `roomId`), jangan gunakan entity global.
- [ ] **D1 Prepared Statements**: Selalu gunakan parameterized queries (`.bind()`) untuk mencegah SQL Injection dan memanfaatkan query plan caching.
- [ ] **D1 Batching Operations**: Gunakan `D1Database.batch()` untuk operasi bulk insert/update guna meminimalkan latency overhead.
- [ ] **KV Metadata Utilization**: Simpan data ringkas (flags, timestamps) di parameter `metadata` saat `KV.put()`, sehingga dapat dibaca pada `KV.list()` tanpa memanggil `KV.get()` untuk setiap key.
- [ ] **R2 Cache API Wrapping**: Bungkus pengambilan file R2 publik dengan `caches.default` Cloudflare untuk mencegah request berulang ke storage engine R2, mengurangi latensi dan biaya Class B operations.
- [ ] **DO Alarm System**: Manfaatkan `ctx.storage.setAlarm()` untuk scheduled cleanup in-memory state atau write-back batch data ke D1/R2 secara periodik.
- [ ] **Tail Workers & Observability**: Aktifkan Tail Workers atau Cloudflare Logpush untuk menangkap uncaught exceptions dan trace performance metrik antar-storage layer.

---

## 12. Hands-on Practice

Buat dan uji arsitektur edge storage terintegrasi dalam direktori praktikum.

### Struktur Proyek
```
hands-on/m02/
├── migrations/
│   └── 0001_schema.sql
├── src/
│   └── index.ts
├── package.json
├── tsconfig.json
└── wrangler.jsonc
```

### Langkah 1: Setup Lingkungan
Eksekusi di terminal Anda:
```bash
mkdir -p hands-on/m02/migrations hands-on/m02/src
cd hands-on/m02
npm init -y
npm install --save-dev typescript wrangler @cloudflare/workers-types
```

### Langkah 2: Buat Storage Binding via CLI
Jalankan perintah berikut untuk mengalokasikan resource lokal/remote:
```bash
# Buat D1 Database
npx wrangler d1 create prod-audit-db

# Buat KV Namespace
npx wrangler kv:namespace create CATALOG_KV

# Buat R2 Bucket
npx wrangler r2 bucket create prod-financial-receipts
```
*Salin output database ID dan KV namespace ID ke dalam `wrangler.jsonc` Anda.*

### Langkah 3: Eksekusi Migrasi D1 Lokal
```bash
# Isi migrations/0001_schema.sql dengan skema pada Seksi 7B
npx wrangler d1 execute prod-audit-db --local --file=./migrations/0001_schema.sql
```

### Langkah 4: Development & Uji Konkurensi
Jalankan local edge development environment:
```bash
npx wrangler dev
```

Uji reservasi paralel menggunakan `curl`:
```bash
# 1. Inisialisasi Stok Produk
curl -X POST http://localhost:8787/product/init \
  -H "Content-Type: application/json" \
  -d '{"productId": "LAPTOP-01", "stock": 5}'

# 2. Lakukan Pembelian Stok
curl -X POST http://localhost:8787/order/checkout \
  -H "Content-Type: application/json" \
  -d '{"productId": "LAPTOP-01", "quantity": 2, "userId": "usr_alpha"}'

# 3. Validasi Fallback & KV Cache
curl -X GET http://localhost:8787/product/LAPTOP-01
```

---

## 13. Exercise

### Level Easy
Modifikasi endpoint `GET /product/:id` pada Seksi 7C agar memeriksa metadata KV sebelum mengambil data. Jika metadata menunjukkan flag `is_discontinued: true`, kembalikan HTTP status `410 Gone` tanpa mengeksekusi fallback query ke D1.

### Level Medium
Tambahkan mekanisme pagination berbasis cursor pada D1 audit log table via endpoint `GET /audit/:productId?cursor=<timestamp>&limit=10`. Pastikan query memanfaatkan index komposit `(product_id, created_at DESC)` yang telah didefinisikan pada skema migrasi.

### Level Hard
Implementasikan sistem **Distributed Rate Limiter** berbasis Durable Objects dengan algoritma **Sliding Window Log**:
- Durable Object menyimpan daftar timestamp request dalam SQLite lokal per `clientIp`.
- Hapus entri yang berada di luar jendela waktu (60 detik terakhir).
- Tolak request (HTTP 429) jika jumlah data dalam jendela waktu melebihi 100 request.
- Pasang alarm DO (`storage.setAlarm()`) untuk membersihkan record client yang tidak lagi aktif setiap 10 menit guna menghemat ruang memori.

---

## 14. Challenge

### Skenario Kasus: Real-Time Collaborative Whiteboard Engine
Rancang sistem penyimpanan edge untuk canvas kolaboratif mirip Miro/Figma dengan ketentuan:
1. **Zero Data Loss pada Room State**: Objek gambar (vektor/shapes) harus tersinkronisasi secara real-time antar pengguna dengan latensi broadcast < 30ms secara global.
2. **Snapshotting Engine**: Tiap 100 mutasi canvas atau minimal 5 menit sekali, Durable Object harus mem-bundle canvas state menjadi file binary terkompresi dan menyimpannya ke **R2 Storage** secara background tanpa membekukan thread manipulasi canvas WebSocket.
3. **Audit History & Rollback**: Setiap perubahan aksi (Add Shape, Move, Delete) dicatat ke **D1** untuk keperluan time-travel undo/redo log.
4. **Thumbnailing**: Sediakan endpoint yang menyajikan raster thumbnail JSON dari canvas yang di-cache di **Workers KV** dengan invalidasi cache otomatis setiap kali room disimpan ke R2.

**Tugas Arsitektur Anda**:
- Susun diagram alur sinkronisasi antara WebSocket, SQLite di dalam DO, D1 WAL stream, dan R2 background commit.
- Identifikasi titik rawan kegagalan (*point of failure*) serta mitigasi strategi penanganan *backpressure* jika user mengirim perubahan vektor melebihi kapasitas flush SQLite DO.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pertanyaan Basic

1. **Berapa batas waktu propagasi default untuk perubahan data pada Workers KV agar konsisten secara global?**
   - A. Sub-millisecond murni
   - B. Hingga 60 detik
   - C. Tepat 5 menit
   - D. 12 jam

2. **Fitur utama apa yang membedakan Cloudflare R2 secara drastis dari AWS S3 dalam hal struktur pembiayaan?**
   - A. Gratis biaya simpan penyimpanan data
   - B. Tidak ada batasan ukuran objek maksimum
   - C. Eliminasi biaya transfer data keluar (*Zero Egress Fees*)
   - D. Tidak menggunakan otorisasi API key

3. **Engine SQL apa yang digunakan secara native di balik Cloudflare D1?**
   - A. PostgreSQL
   - B. SQLite
   - C. MySQL
   - D. MariaDB

4. **Bagaimana Durable Objects memastikan tidak terjadinya race condition pada penulisan state concurrent?**
   - A. Melalui two-phase locking terdistribusi antar seluruh region
   - B. Memastikan seluruh traffic untuk satu instance ID diarahkan ke satu thread V8 isolate yang dieksekusi secara serial
   - C. Menolak seluruh penulisan paralel menggunakan HTTP 503
   - D. Menyimpan data di memory redis terpusat di San Francisco

5. **Apa batas ukuran maksimum value individual yang dapat disimpan dalam Workers KV?**
   - A. 1 MiB
   - B. 25 MiB
   - C. 100 MiB
   - D. 5 GiB

---

### Bagian B: Pertanyaan Intermediate

6. **Kapan Anda sebaiknya TIDAK menggunakan Workers KV sebagai lapisan database utama?**
   - A. Saat aplikasi memerlukan pembacaan konfigurasi global berulang kali
   - B. Saat aplikasi membutuhkan pembacaan instan tepat setelah penulisan (*Read-Your-Own-Writes consistency*)
   - C. Saat menyimpan file statis CSS/JS di edge
   - D. Saat data jarang diubah tetapi diakses dari jutaan klien

7. **Bagaimana arsitektur D1 menangani beban query SELECT yang sangat tinggi di berbagai belahan dunia?**
   - A. Mengirim seluruh query SELECT ke single instance primary
   - B. Membuat replika baca (*Read Replicas*) terdistribusi secara global dan merutekan query menggunakan smart session bookmarks
   - C. Mengonversi query SQL menjadi static flat JSON file di R2 secara otomatis
   - D. Membatasi pembacaan maksimal 50 req/sec

8. **Untuk Durable Objects modern yang dideklarasikan dengan SQLite Storage, di mana lokasi file database SQLite tersebut berada?**
   - A. Di network share AWS EBS yang di-mount via SMB
   - B. Tersimpan lokal di disk/NVMe server host fisik tempat isolate Durable Object tersebut aktif berjalan
   - C. Di dalam bucket R2 internal
   - D. Di Workers KV namespace tersembunyi

9. **Jika Worker perlu mengembalikan file berukuran 500 MB dari R2 ke client browser, pendekatan apa yang benar untuk mencegah memory limit crash?**
   - A. Menggunakan `await object.arrayBuffer()` lalu di-slice menjadi chunks
   - B. Memasukkan objek ke D1 terlebih dahulu sebagai base64 string
   - C. Mengalirkan stream secara langsung: `new Response(object.body, { headers })`
   - D. Memecah file menjadi 20 bagian terpisah via KV namespace

10. **Apa fungsi dari method `ctx.waitUntil()` dalam konteks persistensi data edge storage?**
    - A. Memaksa client menunggu hingga proses I/O selesai sebelum menerima respons HTTP
    - B. Memperpanjang masa hidup isolasi Worker setelah respons HTTP dikirim ke client guna menyelesaikan pekerjaan asinkron di latar belakang
    - C. Menghentikan seluruh eksekusi isolate lain yang ada pada PoP yang sama
    - D. Menjadwalkan cron job untuk dieksekusi keesokan harinya

---

### Bagian C: Skenario Kasus Produksi

11. **Skenario 1**: Aplikasi voting skala nasional mengalami anomali: total vote yang tercatat di database D1 berkurang 30% dari total klik yang masuk saat jutaan pemilih menekan tombol vote secara serentak. Kode Worker Anda melakukan:
    `await env.D1.prepare("UPDATE votes SET count = count + 1 WHERE id = ?").bind(candidateId).run();`
    **Apa akar masalah teknis arsitektur ini dan bagaimana solusinya?**

12. **Skenario 2**: Sistem e-learning menyimpan file video tutorial di R2. Ketika pengguna di Australia mengakses video yang bucket primernya diatur pada region North America, waktu buffering awal (*Time to First Byte*) mencapai 1200ms. Bandwidth egress memang gratis, tetapi latensinya tidak dapat diterima secara SLA.
    **Langkah arsitektur apa yang harus dipasang untuk memangkas latensi streaming ini tanpa memindahkan bucket utama?**

13. **Skenario 3**: Sebuah Durable Object digunakan untuk mencatat koordinat kursor mouse dalam ruang presentasi virtual yang dihadiri 5.000 peserta. Begitu peserta mencapai 1.000 orang, peserta mengalami disconnect massal dan log Worker mencatat error `Script execution timed out (CPU limit exceeded)`.
    **Uraikan audit failure pada implementasi DO tersebut dan rekomendasikan pola refactoring stateful yang tepat.**

---

### Kunci Jawaban & Evaluasi

#### Kunci Bagian A
1. **B** — Propagasi global KV bersifat eventual, memakan waktu hingga 60 detik untuk mencapai seluruh PoP global.
2. **C** — R2 mengeliminasi biaya *egress bandwidth*, salah satu pain-point biaya terbesar pada penyedia cloud konvensional seperti AWS S3.
3. **B** — D1 menggunakan engine SQLite yang dioptimasi untuk eksekusi serverless edge.
4. **B** — Durable Objects menggunakan routing berbasis Anycast terkoordinasi untuk memetakan ID unik ke satu V8 isolate single-threaded, mengeliminasi concurrency race condition.
5. **B** — Batas ukuran file/value tunggal pada Cloudflare KV adalah 25 MiB.

#### Kunci Bagian B
6. **B** — KV adalah eventual consistency (AP); tidak menjamin data yang baru ditulis langsung terbaca oleh request berikutnya di edge yang berbeda.
7. **B** — D1 menggunakan distributed read replicas dan mekanisme tracking session commit untuk memastikan pembacaan lokal tetap konsisten secara kausal (*sequential*).
8. **B** — SQLite terintegrasi langsung pada physical storage host instance DO, memberikan latensi I/O sub-millisecond.
9. **C** — Mengalirkan `ReadableStream` via `object.body` tidak memakan kuota heap memory isolate V8 (zero-buffering memory allocation).
10. **B** — `ctx.waitUntil()` mengizinkan runtime mengeksekusi operasi I/O (seperti audit logging atau upload storage) di background tanpa menahan response delivery ke client.

#### Evaluasi Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    - *Root Cause*: Operasi write ke Primary D1 mengalami *concurrency lock saturation* dan *statement queuing drops* karena database relasional single-primary SQLite tidak dirancang untuk menangani puluhan ribu concurrent incremental writes per detik secara langsung.
    - *Solusi Enterprise*: Pasang **Durable Objects Sharded Counter** di depan D1. Klien mengirim vote ke pool DO yang di-shard (misal: 64 shard per kandidat). Mutasi `+1` diproses instan di memory/SQLite DO. Gunakan interval DO Alarm setiap 5 detik untuk melakukan *flush batch count* ke database D1 (`UPDATE votes SET count = count + ?`).
12. **Analisis Skenario 2**:
    - *Root Cause*: Request harus melakukan round-trip menyeberangi Samudra Pasifik ke region origin bucket R2 di North America untuk mengambil chunk pertama stream video.
    - *Solusi Enterprise*: Integrasikan R2 dengan **Cloudflare Workers Cache API** (`caches.default`) atau ekspos bucket R2 melalui Custom Domain dengan caching enabled (*Tiered Caching & Argo Smart Routing*). Edge PoP di Australia akan meng-cache segmen media video pada POP lokal, sehingga request berikutnya dilayani secara instan dari cache edge Sydney/Melbourne (<15ms TTFB).
13. **Analisis Skenario 3**:
    - *Root Cause*: Mengirim update koordinat mouse individual (tingkat frekuensi 60fps per klien) dari 5.000 peserta ke satu instance DO membebani event-loop V8 single-threaded dengan 300.000 pesan/detik. Terjadi *Head-of-Line Blocking* dan kehabisan alokasi CPU Time per tick.
    - *Solusi Enterprise*:
      1. Terapkan **Client-side Throttling**: Klien hanya mengirimkan koordinat dengan rate 10-20Hz.
      2. Terapkan arsitektur **Tree-based Pub/Sub Fan-out**: Gunakan Durable Objects tingkat kedua sebagai *Edge Broadcasters*. DO Utama hanya menerima input dari presenter/moderator, lalu meneruskannya ke beberapa Edge DO Relay, yang masing-masing melayani subset WebSockets (misal: 250 koneksi per child DO).

---

## 16. Summary

Menguasai ekosistem Cloudflare Edge Storage menuntut pemahaman mendalam tentang PACELC theorem dalam praktik rekayasa nyata:
1. **Workers KV** unggul mutlak dalam kecepatan baca global (*sub-10ms latency*), tetapi dikompromikan oleh *eventual consistency* yang lambat merambat.
2. **Cloudflare D1** membawa fleksibilitas relasional SQL standar dengan jaminan *read-replication*, cocok untuk entitas terstruktur dan query relasional.
3. **Cloudflare R2** mendobrak batasan ekonomi cloud dengan *zero egress costs*, menjadikannya fondasi utama penyimpanan artefak, aset media, dan cold-tier snapshots.
4. **Durable Objects** menambal keterbatasan sistem terdistribusi edge konvensional dengan menghadirkan model *actor linearizable* dan private storage SQLite, memberikan kontrol konkurensi mutlak terhadap state kritis.

Arsitektur enterprise yang tangguh tidak memilih salah satu, melainkan merangkai keempat pilar ini secara harmonis: menyerap traffic dengan KV, mengoordinasi transaksi dengan Durable Objects, mengekstrak data relasional via D1, dan mengalirkan blob masif melalui R2.