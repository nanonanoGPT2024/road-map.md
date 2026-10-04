## SEKSI 01 — IDENTITAS MODUL

* **Mata Kuliah / Kurikulum:** Software Design & Architecture
* **Kategori:** 06-Architecture-and-System-Design
* **Kode Modul:** SDA-06-01
* **Bab:** 06 — Pola Arsitektur Sistem Terdistribusi & Microservices
* **Topik Bahasan:** Service Decomposition Strategies, API Gateway, Backends for Frontends (BFF), Distributed Transactions & Sagas
* **Prasyarat:** 
  * Pemahaman mendalam terkait Pemrograman Berorientasi Objek & Prinsip SOLID.
  * Pengetahuan arsitektur monolitik, protokol jaringan (HTTP/2, gRPC, TCP/IP), dan *message broker* (AMQP/Kafka).
  * Pengalaman dasar dengan basis data relasional (ACID) dan non-relasional (BASE).
* **Target Tingkat Kemahiran:** Advanced / Senior Software Engineer / Solutions Architect
* **Perkiraan Waktu Penyelesaian:** 180–240 menit (teori mendalam, analisis kasus, dan implementasi kode)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mengeksekusi Strategi Dekomposisi Sistem:** Memecah arsitektur monolitik menjadi layanan independen berbasis *Business Capabilities* dan *Bounded Contexts* (Domain-Driven Design) tanpa memicu *distributed anti-patterns* seperti *Distributed Monolith*.
2. **Merancang Boundary Lapisan Akses Klien:** Membedakan peran teknis, merancang, dan mengimplementasikan arsitektur *Edge Layer* menggunakan **API Gateway** terpusat serta variasi **Backends for Frontends (BFF)** untuk multi-platform clients.
3. **Mengatasi Batasan Transaksi Klasik Terdistribusi:** Mengidentifikasi limitasi Two-Phase Commit (2PC) / XA Transactions dalam sistem cloud-native dan membuktikan relevansi Teorema CAP dan model konsistensi eventual (BASE).
4. **Mengimplementasikan Saga Pattern:** Merancang alur transaksi terdistribusi multi-layanan menggunakan *Choreography* dan *Orchestration*, lengkap dengan *forward transactions*, *compensating transactions*, dan mekanisme penanganan *pivot transactions*.
5. **Membangun Resiliensi Transaksional:** Mengintegrasikan pola pendukung transaksi terdistribusi seperti *Transactional Outbox Pattern*, *Idempotent Consumer*, dan *Dead-Letter Queues (DLQ)*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    ARARSITEKTUR SISTEM TERDISTRIBUSI
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
STRATEGI DEKOMPOSISI LAYANAN                         EDGE ROUTING & INTEGRASI
  ├─ Business Capability                              ├─ API Gateway Pattern
  │    (Value Stream Mapping)                         │    (Cross-Cutting Concerns)
  ├─ Domain-Driven Design                             └─ Backends for Frontends (BFF)
  │    (Bounded Context & Subdomains)                      (Per-Client Optimizations)
  └─ Strangler Fig Pattern                                    │
       (Migrasi Monolith ke Microservices)                    │
                                                              ▼
                                                   KONSISTENSI TERDISTRIBUSI
                                                              │
                    ┌─────────────────────────────────────────┴───────────────────────┐
                    ▼                                                                 ▼
         TWO-PHASE COMMIT (2PC)                                                  SAGA PATTERN
       (Blokir sinkron, Single Point of                               (Asinkron, Eventual Consistency,
        Failure, Anti-Cloud Native)                                    Kompensasi Transaksi Manual)
                                                                                      │
                                                           ┌──────────────────────────┴───────────────┐
                                                           ▼                                          ▼
                                                     CHOREOGRAPHY                               ORCHESTRATION
                                             (Event-driven, desentralisasi,           (State Machine terpusat,
                                              risiko cyclic dependency)                visibilitas alur tinggi)
                                                           │                                          │
                                                           └──────────────────────────┬───────────────┘
                                                                                      ▼
                                                                           POLA RESILIENSI DASAR
                                                                             ├─ Transactional Outbox
                                                                             ├─ Idempotent Consumer
                                                                             └─ Semantic Lock / Pivot Step
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Runtuhnya Asumsi ACID Konvensional:**  
   Pada basis data tunggal, integritas data dijamin penuh oleh *engine* basis data menggunakan transaksi lokal (Atomicity, Consistency, Isolation, Durability). Begitu batas layanan dipecah menjadi *database-per-service*, batasan fisik jaringan masuk ke dalam persamaan. Jaringan bersifat *unreliable*, memiliki latensi non-nol, dan rentan terhadap *network partitioning*. Mempertahankan transaksi lintas batas jaringan via protokol sinkron koordinatif seperti Two-Phase Commit (2PC) menyebabkan pemblokiran sumber daya (*lock holding*), degradasi latensi eksponensial, dan penurunan reliabilitas secara sistemik.

2. **Kutukan Monolith Terdistribusi (Distributed Monolith):**  
   Banyak organisasi gagal melakukan migrasi *microservices* karena sekadar memisahkan kode tanpa memisahkan data atau memotong batas domain secara keliru. Hasilnya adalah *distributed monolith*: sistem dengan semua kompleksitas operasional microservices (latensi jaringan, kegagalan parsial, deployment berbelit), namun dengan semua kelemahan monolitik (keterikatan rilis, ketergantungan skema data bersama, eskalasi *blast radius* kegagalan).

3. **Kebutuhan Pengalaman Klien yang Terdiferensiasi:**  
   Konsumen data sistem modern bukan lagi sekadar browser desktop. Perangkat mobile dengan latensi jaringan tinggi, jam pintar dengan bandwidth terbatas, integrasi B2B pihak ketiga, dan aplikasi Single Page (SPA) membutuhkan payload data yang berbeda, protokol komunikasi yang berbeda (misalnya HTTP/REST vs GraphQL vs WebSockets), dan frekuensi pemanggilan API yang berbeda. Tanpa pola perantara yang solid (API Gateway & BFF), backend internal akan terekspos langsung, membocorkan domain internal, dan memaksa klien melakukan *over-fetching* atau *under-fetching*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Service Decomposition Strategies
Pendekatan sistematis untuk mendefinisikan batasan antarlayanan (*service boundaries*) agar setiap microservice memiliki kohesi tinggi (*high cohesion*) dan ketergantungan rendah (*low coupling*).
* **Decomposition by Business Capability:** Membagi sistem berdasarkan fungsi bisnis yang menghasilkan nilai (misal: *Order Management*, *Billing*, *Shipping*).
* **Decomposition by Subdomain (DDD):** Menggunakan teknik pemodelan domain strategis untuk mengidentifikasi *Core Subdomains*, *Supporting Subdomains*, dan *Generic Subdomains*, yang masing-masing dipetakan ke dalam satu *Bounded Context*.
* **Strangler Fig Pattern:** Strategi migrasi inkremental di mana fungsionalitas baru atau refaktor dari monolit dialihkan secara bertahap ke microservice baru menggunakan lapisan proksi penengah, hingga sistem monolitik lama dapat dimatikan sepenuhnya.

### 2. API Gateway Pattern
Komponen arsitektural yang bertindak sebagai gerbang tunggal (*single entry point*) bagi seluruh trafik eksternal yang masuk ke ekosistem sistem terdistribusi. Gateway menangani aspek-aspek *cross-cutting concerns* seperti:
* Autentikasi dan otorisasi perimeter
* *Rate limiting* dan *throttling*
* Terminasi SSL/TLS
* *Dynamic request routing* dan *load balancing*
* *Telemetry collection* (metrik, jejak terdistribusi, dan pencatatan log)

### 3. Backends for Frontends (BFF) Pattern
Varian arsitektur dari lapisan gateway di mana *layer* perantara dibuat spesifik untuk jenis klien antarmuka tertentu. Alih-alih satu API Gateway raksasa (*One-Size-Fits-All*) yang melayani semua klien:
* Satu BFF didekasikan untuk aplikasi Mobile (fokus pada payload minimalis, kompresi data tinggi, agregasi panggilan).
* Satu BFF didekasikan untuk Web Desktop (fokus pada data kaya, kompatibilitas browser, integrasi sesi berbasis cookie aman).
* Satu BFF didekasikan untuk Integrasi Mitra Eksternal (fokus pada audit ketat, pembatasan kuota spesifik, transformasi protokol).

### 4. Distributed Transactions & Saga Pattern
Saga adalah rangkaian transaksi lokal yang dieksekusi secara berurutan pada sekumpulan microservices. Setiap langkah memperbarui basis data lokal dari satu layanan dan memicu langkah berikutnya melalui pesan/event asinkron.
* Jika salah satu transaksi lokal mengalami kegagalan bisnis, Saga mengeksekusi serangkaian **Compensating Transactions** secara mundur untuk membatalkan perubahan yang telah dilakukan oleh langkah-langkah sebelumnya, memastikan integritas data tetap konsisten secara *eventual* (BASE - Basically Available, Soft state, Eventual consistency).
* **Choreography:** Desentralisasi; setiap layanan mendengar event dan menentukan tindakan serta mempublikasikan event lanjutan sendiri tanpa pengatur pusat.
* **Orchestration:** Sentralisasi; satu koordinator (*Saga Execution Coordinator* / SEC) memberitahu setiap layanan apa yang harus dieksekusi melalui pesan perintah (*command messages*), melacak state alur kerja, dan memicu kompensasi jika terjadi anomali.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme 1: Dekomposisi Berbasis Domain-Driven Design (DDD)
1. **Event Storming:** Lakukan lokakarya lintas fungsi untuk mengidentifikasi seluruh domain event yang terjadi dalam bisnis (misal: `OrderPlaced`, `PaymentReceived`, `InventoryReserved`).
2. **Identifikasi Agregat & Bounded Contexts:** Kelompokkan entitas dan aturan bisnis (invarian) ke dalam agregat tertutup. Tentukan batas linguistik eksplisit (*Ubiquitous Language*) di mana satu istilah memiliki arti tunggal yang tidak ambigu.
3. **Analisis Konteks Data (Database-per-Service):** Pastikan basis data dibagi secara ketat. Tidak boleh ada kueri lintas basis data (*cross-database joins*) via SQL. Semua pertukaran data antarlayanan harus melalui kontrak antarmuka API yang stabil atau *event streams*.

### Mekanisme 2: API Gateway & BFF Pipeline
1. Klien mengirim permintaan (misal: HTTPS/HTTP2) ke Edge Gateway.
2. Gateway mengeksekusi *pre-routing filters*:
   * Memvalidasi JWT token (kriptografi tanda tangan, masa berlaku).
   * Memeriksa kuota token bucket untuk mitigasi serangan DoS (*Rate Limiting*).
3. Gateway/BFF melakukan routing:
   * **BFF Aggregation:** Menembak Layanan Pesanan, Layanan Pembayaran, dan Layanan Pengguna secara paralel via gRPC.
   * Melakukan transformasi data: membuang field yang tidak dibutuhkan aplikasi klien, menyatukan respon ke dalam payload tunggal.
4. Gateway mengeksekusi *post-routing filters* (misal: injeksi header keamanan CORS, pencatatan log akses metrik).

### Mekanisme 3: Alur Saga Orchestration dan Kompensasi
Saga membagi langkah transaksi menjadi tiga jenis:
1. **Compensable Transactions:** Transaksi yang memiliki potensi dibatalkan menggunakan kompensasi logis.
2. **Pivot Transaction:** Titik penentu tanpa jalan kembali (*point of no return*). Jika langkah ini sukses, Saga dijamin akan selesai hingga ujung akhir. Jika gagal, langkah sebelumnya dikompensasi.
3. **Retryable Transactions:** Transaksi yang dieksekusi setelah langkah pivot, dijamin tidak boleh gagal secara bisnis dan hanya boleh mengalami kegagalan teknis (harus di-*retry* hingga sukses menggunakan prinsip idempoten).

```
[Mulai] 
   │
   ▼
[Langkah 1: Compensable - Create Pending Order] ──── Gagal ──► [Batalkan Transaksi / Abort]
   │ Sukses
   ▼
[Langkah 2: Compensable - Reserve Credit Card]  ──── Gagal ──► [Kompensasi Langkah 1]
   │ Sukses                                                         ▲
   ▼                                                                │
[Langkah 3: Pivot - Reserve Inventory Warehouse] ── Gagal ──► [Kompensasi Langkah 2]
   │ Sukses
   ▼
[Langkah 4: Retryable - Approve Order] (Retry loop sampai sukses)
   │
   ▼
[Selesai - Sifat State: Sukses Akhir]
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Topology Arsitektur: Multi-Client, BFF, Gateway & Microservices

```
+----------------+      +----------------+      +--------------------+
|  Mobile Client |      |   Web Client   |      | Third-Party Partner|
+--------+-------+      +--------+-------+      +---------+----------+
         |                       |                        |
         | HTTP/2 JSON           | HTTP/2 JSON            | Mutual TLS / REST
         v                       v                        v
+------------------+    +------------------+    +--------------------+
|    Mobile BFF    |    |     Web BFF      |    |  Partner B2B GW    |
| (Aggregator,     |    | (Server-Side Rend|    | (Strict Rate Limit,|
|  Image Resizing) |    |  Cookie Handling)|    |  Payload Audit)    |
+--------+---------+    +--------+---------+    +---------+----------+
         |                       |                        |
         +-----------------------+------------------------+
                                 | Internal RPC / Private Network
                                 v
                +---------------------------------+
                |      Core API Gateway / Mesh    |
                |   (mTLS, Tracing, Discovery)    |
                +----------------+----------------+
                                 |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
+-----------------+     +-----------------+     +-----------------+
|  Order Service  |     | Payment Service |     |Inventory Service|
|  (Order DB)     |     |  (Payment DB)   |     |  (Inventory DB) |
+-----------------+     +-----------------+     +-----------------+
```

---

### Sequence Diagram: Saga Orchestration dengan Kompensasi (Rollback Logis)

```
Klien       Saga Orchestrator       Order Svc          Payment Svc        Inventory Svc
  │                 │                   │                   │                   │
  │── Buat Order ──►│                   │                   │                   │
  │   (Checkout)    │── 1. CreatePendingOrder ─────────────►│                   │
  │                 │◄── Pending Created ───────────────────│                   │
  │                 │                                       │                   │
  │                 │── 2. AuthorizePayment ───────────────────────────────────►│
  │                 │◄── Payment Authorized ────────────────────────────────────│
  │                 │                                                           │
  │                 │── 3. ReserveStock ───────────────────────────────────────────────────────────────►│
  │                 │◄── OutOfStock (FAILURE) ──────────────────────────────────────────────────────────│
  │                 │                                                           │                       │
  │                 │════════════════ INITIATE COMPENSATION ════════════════════│                       │
  │                 │                                                           │                       │
  │                 │── 4. Refund/VoidPayment ─────────────────────────────────►│                       │
  │                 │◄── Payment Voided ACK ────────────────────────────────────│                       │
  │                 │                                       │                                           │
  │                 │── 5. RejectOrder (Cancel) ───────────►│                                           │
  │                 │◄── Order Marked Rejected ─────────────│                                           │
  │                 │                                                                                   │
  │◄── Order Gagal ─│                                                                                   │
       (Out of Stock)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi minimalis konsep **BFF Pattern** di Node.js menggunakan TypeScript yang mengagregasi data dari dua layanan downstream (User Profile & Account Settings) untuk kebutuhan tampilan layar profil Mobile:

```typescript
// mobile-bff-aggregator.ts
import http from 'http';

interface UserProfile {
  id: string;
  name: string;
  avatarUrl: string;
}

interface AccountBalance {
  currency: string;
  amount: number;
}

// Simulasi downstream service
async function fetchUserProfile(userId: string): Promise<UserProfile> {
  // Simulasi HTTP GET http://user-service/users/:id
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ id: userId, name: "Budi Santoso", avatarUrl: "https://cdn.contoh.id/p/123.jpg" });
    }, 50);
  });
}

async function fetchAccountBalance(userId: string): Promise<AccountBalance> {
  // Simulasi HTTP GET http://balance-service/accounts/:userId/balance
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ currency: "IDR", amount: 15750000 });
    }, 70);
  });
}

// Handler BFF untuk Mobile: Kompres data, ambil hanya field relevan
async function handleMobileProfileRequest(userId: string) {
  // Eksekusi paralel via Promise.all untuk meminimalisasi total latensi
  const [profile, balance] = await Promise.all([
    fetchUserProfile(userId),
    fetchAccountBalance(userId),
  ]);

  // Payload diformat khusus untuk optimasi konsumsi memori mobile
  return {
    displayName: profile.name,
    avatar: profile.avatarUrl,
    balanceFormatted: `${balance.currency} ${balance.amount.toLocaleString('id-ID')}`
  };
}

const server = http.createServer(async (req, res) => {
  if (req.url?.startsWith('/mobile/v1/profile/') && req.method === 'GET') {
    const userId = req.url.split('/').pop() || '';
    try {
      const responsePayload = await handleMobileProfileRequest(userId);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(responsePayload));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Internal Server Error' }));
    }
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(3000, () => {
  console.log("Mobile BFF running on http://localhost:3000");
});
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi produksi tingkat lanjut dari **Saga Orchestrator** dalam TypeScript. Menggunakan pola *State Machine*, *Command Execution*, *Compensation Pipeline*, penanganan batas waktu (*timeout*), serta pencatatan log idempotensi.

```typescript
// saga-orchestration-engine.ts

export type SagaStepStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'COMPENSATED';

export interface SagaStep<TContext> {
  name: string;
  execute: (context: TContext) => Promise<TContext>;
  compensate: (context: TContext) => Promise<TContext>;
}

export enum SagaState {
  NOT_STARTED = 'NOT_STARTED',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  COMPENSATING = 'COMPENSATING',
  FAILED = 'FAILED',
}

export interface OrderCheckoutContext {
  orderId: string;
  userId: string;
  amount: number;
  inventoryReserved: boolean;
  paymentAuthorized: boolean;
  orderStatus: 'CREATED' | 'CONFIRMED' | 'REJECTED';
  failureReason?: string;
  idempotencyKey: string;
}

export class OrderSagaOrchestrator {
  private steps: SagaStep<OrderCheckoutContext>[] = [];
  private state: SagaState = SagaState.NOT_STARTED;
  private executedSteps: SagaStep<OrderCheckoutContext>[] = [];

  public addStep(step: SagaStep<OrderCheckoutContext>): this {
    this.steps.push(step);
    return this;
  }

  public async execute(initialContext: OrderCheckoutContext): Promise<{ success: boolean; context: OrderCheckoutContext }> {
    let currentContext = { ...initialContext };
    this.state = SagaState.IN_PROGRESS;
    this.executedSteps = [];

    console.log(`[SAGA] Memulai Order Checkout Saga [ID: ${currentContext.orderId}] | Key: ${currentContext.idempotencyKey}`);

    for (const step of this.steps) {
      console.log(`[SAGA] [FORWARD] Mengeksekusi langkah: ${step.name}`);
      try {
        currentContext = await step.execute(currentContext);
        this.executedSteps.push(step);
      } catch (error: any) {
        console.error(`[SAGA] [ERROR] Eksekusi ${step.name} gagal. Error: ${error.message}`);
        currentContext.failureReason = error.message;
        
        // Pemicu kompensasi rollback otomatis
        await this.rollback(currentContext);
        return { success: false, context: currentContext };
      }
    }

    this.state = SagaState.COMPLETED;
    currentContext.orderStatus = 'CONFIRMED';
    console.log(`[SAGA] Transaksi terdistribusi SUKSES untuk Order ID: ${currentContext.orderId}`);
    return { success: true, context: currentContext };
  }

  private async rollback(context: OrderCheckoutContext): Promise<void> {
    this.state = SagaState.COMPENSATING;
    console.warn(`[SAGA] [ROLLBACK] Memulai transaksi kompensasi. Total langkah yang harus dibatalkan: ${this.executedSteps.length}`);

    // Iterasi mundur terhadap langkah yang telah sukses dieksekusi (LIFO order)
    while (this.executedSteps.length > 0) {
      const step = this.executedSteps.pop();
      if (!step) continue;

      console.warn(`[SAGA] [COMPENSATION] Membatalkan langkah: ${step.name}`);
      let retryCount = 0;
      const MAX_RETRIES = 3;
      let compensated = false;

      while (!compensated && retryCount < MAX_RETRIES) {
        try {
          await step.compensate(context);
          compensated = true;
          console.log(`[SAGA] [COMPENSATION] Langkah ${step.name} berhasil dibatalkan.`);
        } catch (compError: any) {
          retryCount++;
          console.error(`[SAGA] [COMPENSATION CRITICAL] Gagal kompensasi ${step.name} (Percobaan ${retryCount}/${MAX_RETRIES}): ${compError.message}`);
          if (retryCount >= MAX_RETRIES) {
            console.error(`[FATAL] Kompensasi gagal total untuk ${step.name}. Mengirim alert ke DLQ / Operasional Manusia.`);
            // Dalam sistem riil, lempar event ke Alerting Engine (PagerDuty/Slack/DLQ)
          }
        }
      }
    }

    this.state = SagaState.FAILED;
    context.orderStatus = 'REJECTED';
    console.log(`[SAGA] Rollback selesai. Status order: REJECTED.`);
  }
}

// ==========================================
// DEFINISI CONCRETE STEPS / LAYANAN DOWNSTREAM
// ==========================================

const reserveInventoryStep: SagaStep<OrderCheckoutContext> = {
  name: 'ReserveInventory',
  execute: async (ctx) => {
    // Simulasi pemanggilan API Inventory Service
    console.log(` -> Melakukan reservasi stok untuk Order: ${ctx.orderId}`);
    // Simulasi kondisi jika kuota gudang habis
    if (ctx.amount > 5000000) {
      throw new Error("Stok produk tidak mencukupi untuk item dengan nilai ini");
    }
    ctx.inventoryReserved = true;
    return ctx;
  },
  compensate: async (ctx) => {
    if (ctx.inventoryReserved) {
      console.log(` -> [KOMPENSASI] Mengembalikan kuota stok gudang untuk Order: ${ctx.orderId}`);
      ctx.inventoryReserved = false;
    }
    return ctx;
  }
};

const processPaymentStep: SagaStep<OrderCheckoutContext> = {
  name: 'ProcessPayment',
  execute: async (ctx) => {
    // Simulasi otorisasi kartu kredit / debit
    console.log(` -> Memotong saldo sebesar: ${ctx.amount} untuk Order: ${ctx.orderId}`);
    ctx.paymentAuthorized = true;
    return ctx;
  },
  compensate: async (ctx) => {
    if (ctx.paymentAuthorized) {
      console.log(` -> [KOMPENSASI] Melakukan refund transaksi pembayaran ke Payment Gateway: ${ctx.orderId}`);
      ctx.paymentAuthorized = false;
    }
    return ctx;
  }
};

const finalizeOrderStep: SagaStep<OrderCheckoutContext> = {
  name: 'FinalizeOrder',
  execute: async (ctx) => {
    console.log(` -> Mengubah status Order ${ctx.orderId} menjadi COMPLETED di DB`);
    return ctx;
  },
  compensate: async (ctx) => {
    console.log(` -> [KOMPENSASI] Menandai Order ${ctx.orderId} sebagai CANCELLED/VOID`);
    return ctx;
  }
};

// ==========================================
// RUNNER & VERIFIKASI EKSEKUSI
// ==========================================
async function runDemos() {
  const orchestrator = new OrderSagaOrchestrator();
  orchestrator
    .addStep(processPaymentStep)
    .addStep(reserveInventoryStep)
    .addStep(finalizeOrderStep);

  // KASUS 1: Alur Sukses
  console.log("\n================ KASUS 1: TRANSAKSI VALID ================");
  const validContext: OrderCheckoutContext = {
    orderId: "ORD-001",
    userId: "USER-99",
    amount: 1500000,
    inventoryReserved: false,
    paymentAuthorized: false,
    orderStatus: 'CREATED',
    idempotencyKey: "uuid-step-key-1"
  };
  await orchestrator.execute(validContext);

  // KASUS 2: Alur Gagal (Inventory Gagal -> Trigger Kompensasi Pembayaran)
  console.log("\n================ KASUS 2: TRANSAKSI GAGAL (MEMICU ROLLBACK) ================");
  const failingContext: OrderCheckoutContext = {
    orderId: "ORD-002",
    userId: "USER-100",
    amount: 9000000, // Nilai melebihi batas, memicu simulasi Out of Stock
    inventoryReserved: false,
    paymentAuthorized: false,
    orderStatus: 'CREATED',
    idempotencyKey: "uuid-step-key-2"
  };
  await orchestrator.execute(failingContext);
}

runDemos();
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih arsitektur microservices dan transaksi terdistribusi bukanlah keputusan tanpa biaya (*no free lunch*). Di bawah ini adalah matriks trade-offs teknis yang wajib dievaluasi:

| Dimensi Arsitektural | Two-Phase Commit (2PC) / XA | Saga Pattern (Orchestration) | Saga Pattern (Choreography) | Monolitik Klasik (ACID) |
| :--- | :--- | :--- | :--- | :--- |
| **Konsistensi Data** | *Immediate / Strong* | *Eventual Consistency* | *Eventual Consistency* | *Immediate / Strong* |
| **Throughput & Latensi** | Rendah (Terkendala *distributed lock*) | Sangat Tinggi (Non-blocking I/O) | Sangat Tinggi (Non-blocking I/O) | Tinggi (Tergantung kapasitas database) |
| **Isolasi Anomali** | Dijamin oleh DB Engine | Tidak ada isolasi (*Dirty Reads/Writes*) | Tidak ada isolasi (*Dirty Reads/Writes*) | Penuh (Serializable / Read Committed) |
| **Kompleksitas Kode** | Rendah (Dikelola oleh driver middleware) | Tinggi (Perlu State Engine & Kompensasi) | Sangat Tinggi (*Spaghetti events*, sulit di-debug) | Sangat Rendah |
| **Kopling Dependensi** | Sangat Tinggi (Semua simpul harus daring) | Rendah (Asinkron berbasis antrean/HTTP) | Ekstrem Rendah (Decoupled total via bus) | N/A (Tunggal) |
| **Audit & Visibilitas** | Terfragmentasi di transaction manager | Terpusat (Orchestrator tahu posisi alur) | Buruk (Perlu distributed tracing canggih) | Terpusat pada satu database audit log |

### Tantangan Kurangnya Fitur 'Isolation' pada Saga:
Karena transaksi lokal pada Saga langsung melakukan *commit* ke basis data masing-masing sebelum seluruh Saga selesai, data dapat dibaca atau dimodifikasi oleh transaksi eksternal lain (*dirty reads* atau *lost updates*). Cara menanggulangi:
1. **Semantic Lock:** Menandai state entitas sebagai `PENDING_*` (misal: `Order.Status = PENDING_PAYMENT`), mencegah eksekusi mutasi lain pada rekaman tersebut.
2. **Commutative Updates:** Merancang operasi matematika yang urutan eksekusinya tidak mengubah hasil akhir (misal: debit/kredit tanpa batasan urutan mutlak).
3. **Pessimistic Read-View:** Klien hanya diizinkan membaca data yang telah berstatus `CONFIRMED`.

---

## SEKSI 11 — BEST PRACTICES

1. **Wajib Menggunakan Idempotency Keys:**  
   Dalam jaringan terdistribusi, komunikasi bersifat *at-least-once*. Permintaan retry dapat tiba lebih dari satu kali. Setiap endpoint forward transaction dan compensating transaction wajib menerima `Idempotency-Key` pada header dan mencatatnya ke basis data dalam transaksi atomik untuk mencegah eksekusi ganda.

2. **Implementasikan Transactional Outbox Pattern:**  
   Hindari menerbitkan pesan/event ke message broker secara langsung di tengah-tengah kode aplikasi setelah mengeksekusi perintah SQL database. Jika broker sedang down, transaksi DB terlanjur committed namun event tidak pernah terkirim (*dual-write problem*). Simpan event di tabel internal `outbox` dalam database yang sama, lalu gunakan *worker* terpisah (CDC / Debezium) untuk membacanya ke broker.

3. **Gunakan Korelasi & Tracing Kontekstual (Trace Context):**  
   Semua panggilan via API Gateway/BFF wajib menginjeksi header W3C Trace Context (`traceparent`, `tracestate`) atau header khusus (`X-Correlation-ID`). Setiap log yang dikeluarkan orchestrator dan downstream service harus memuat ID ini untuk keperluan penelusuran kegagalan terdistribusi.

4. **Jangan Membocorkan Kontrak Database ke API:**  
   API publik yang diekspos oleh API Gateway/BFF tidak boleh sekadar melakukan translasi 1:1 dari skema tabel database. Rancang *Data Transfer Object* (DTO) yang stabil agar perubahan internal tabel tidak merusak kompatibilitas klien (*breaking changes*).

5. **Definisikan Batas Waktu Eksplisit (Timeouts) dan Circuit Breakers:**  
   Setiap interaksi antar-layanan (baik di level Gateway maupun Orchestrator) harus memiliki *timeout* yang terukur. Terapkan pola *Circuit Breaker* (misal: via Resilience4j atau Envoy) agar kaskade kegagalan (*cascading failure*) downstream service tidak melumpuhkan seluruh sistem.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **The Distributed Monolith Trap (Shared Database):**  
   Membagi kode menjadi puluhan repositori microservice terpisah, namun semuanya terhubung ke basis data tunggal yang sama. Ini adalah anti-pattern terburuk: membuang performa transaksi ACID lokal, menambah latensi jaringan, tetapi tetap rentan benturan skema data dan ketiadaan otonomi tim.
   *Solusi:* Terapkan aturan *Database-per-Service* secara kaku. Jika butuh data lain, gunakan agregasi asinkron atau pemanggilan API.

2. **Mengasumsikan Kompensasi Selalu Berhasil:**  
   Membuat logika kompensasi tanpa penanganan kegagalan. Kompensasi transaksi juga berjalan di atas jaringan fisik; API refund pembayaran bisa saja mengembalikan status `500 Internal Server Error` atau mengalami kegagalan koneksi.
   *Solusi:* Langkah kompensasi wajib idempoten dan dijalankan dalam loop retry tanpa henti (*infinite retry*) hingga berhasil, atau masuk ke sistem intervensi manual/DLQ.

3. **Kebocoran Domain Klien ke Backend Inti (Tercampurnya Logika Presentasi):**  
   Menambahkan modifikasi pada Core Service hanya untuk mengakomodasi kebutuhan satu layar di aplikasi iOS atau Android (misal: menambahkan boolean `isAndroidNotificationEnabled` pada skema basis data Order Service).
   *Solusi:* Serahkan transformasi data presentasi ke lapisan **BFF (Backends for Frontends)**. Biarkan Core Microservices tetap berfokus pada aturan bisnis domain murni.

4. **Ketergantungan Sirkular pada Choreographed Saga:**  
   Service A merilis Event A -> Service B mendengar dan merilis Event B -> Service C mendengar dan merilis Event C -> Service A kembali bereaksi terhadap Event C. Hal ini menghasilkan siklus tak berujung (*infinite event loop*) yang sulit dideteksi hingga kuota sistem habis.
   *Solusi:* Jika alur transaksi melibatkan lebih dari 3–4 langkah bisnis yang saling berinteraksi, tinggalkan Choreography dan beralihlah ke **Orchestration Saga**.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Guided Exercise (Panduan Penuh)
**Tujuan:** Mengimplementasikan penanganan Idempotensi pada Compensating Action dalam node worker transaksi.
* **Instruksi:** Buat class `PaymentServiceSimulator` yang menyimpan tabel internal `processed_transactions` dan `processed_compensations`. Simulasikan pemanggilan ganda terhadap fungsi `refund(transactionId, idempotencyKey)`. Pastikan saldo akun hanya dikembalikan tepat satu kali meskipun fungsi dipanggil sebanyak tiga kali secara berturut-turut.
* **Kriteria Keberhasilan:** Eksekusi ganda menghasilkan respon idempotency `ALREADY_REFUNDED` tanpa melakukan mutasi saldo tambahan.

### Latihan 2: Semi-Guided Exercise (Tantangan Bertahap)
**Tujuan:** Merancang Strangler Fig Facade.
* **Skenario:** Sebuah aplikasi E-Commerce monolitik memiliki endpoint `/api/v1/orders` dan `/api/v1/users`. Tim ingin memindahkan domain *Orders* ke microservice baru yang berjalan di port 5001, sementara *Users* tetap berada pada Monolith di port 4000.
* **Tugas:** Buat reverse proxy sederhana menggunakan Node.js `http-proxy` atau pustaka gateway sejenis. Proxy harus membaca rute masuk:
  * Semua path `/api/v1/orders/*` dialihkan (*forward*) ke microservice baru (Port 5001).
  * Semua path lainnya dialihkan ke Monolith (Port 4000).
  * Injeksi header kustom `X-Strangler-Routing: Microservice-Orders` untuk memverifikasi jalur perutean yang diambil.

### Latihan 3: Open-Ended Architectural Challenge (Studi Kasus Desain)
**Tujuan:** Merancang Desain End-to-End Sistem Distribusi Logistik & Pemesanan Tiket Bioskop.
* **Skenario:** Anda adalah Lead Architect di platform pemesanan tiket bioskop nasional. Sistem mengalami *spike* trafik luar biasa pada 5 menit pertama pembukaan penjualan tiket film blockbuster.
* **Kebutuhan Sistem:**
  1. Pemilihan kursi bersifat eksklusif (tidak boleh ada *double-booking* kursi yang sama).
  2. Batas waktu pembayaran adalah 10 menit. Jika kadaluarsa, kursi harus otomatis dilepaskan kembali ke publik.
  3. Aplikasi diakses oleh Mobile Apps (iOS/Android), Web Portal, dan Mesin Tiket Fisik (Kiosk) di bioskop.
* **Deliverables:**
  * Diagram Arsitektur (BFF layer, Gateway, Services, Message Broker).
  * State Machine lengkap alur transaksi Saga (Orchestrator vs Choreography) mencakup langkah-langkah kompensasi jika gateway pembayaran pihak ketiga *timed out*.
  * Solusi mitigasi hilangnya isolasi (*Isolation anomaly*) saat kursi sedang ditahan (*reserved*) dalam periode 10 menit.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan.

**1. Mengapa Two-Phase Commit (2PC) umumnya dihindari pada arsitektur microservices berbasis cloud?**
* A. Karena 2PC tidak mendukung basis data relasional.
* B. Karena 2PC adalah protokol yang memblokir (*blocking protocol*), meningkatkan latensi secara eksponensial, dan rentan terhadap kegagalan ketersediaan jika koordinator mati.
* C. Karena 2PC tidak mengizinkan enkripsi data saat transit.
* D. Karena 2PC mewajibkan seluruh basis data menggunakan vendor yang sama.

**2. Apa perbedaan fungsional utama antara API Gateway generik dan pola Backends for Frontends (BFF)?**
* A. API Gateway hanya menangani HTTP/1.1, sedangkan BFF hanya menangani WebSocket.
* B. API Gateway berada di sisi klien (in-browser), sedangkan BFF berada di jaringan penyedia internet.
* C. API Gateway umumnya menyediakan titik masuk global tunggal untuk seluruh sistem, sedangkan BFF adalah gateway khusus yang dirancang dan dioptimalkan untuk kebutuhan antarmuka klien tertentu.
* D. Tidak ada perbedaan fungsional, keduanya merupakan sinonim penamaan dagang.

**3. Dalam Saga Pattern, apa yang dimaksud dengan "Compensating Transaction"?**
* A. Transaksi yang mengembalikan (*rollback*) basis data secara fisik menggunakan snapshot redo-log engine DB.
* B. Transaksi baru yang melakukan tindakan semantik logis untuk membatalkan efek nyata dari transaksi forward yang telah di-commit sebelumnya.
* C. Pembayaran denda biaya transfer bank antar-layanan terdistribusi.
* D. Transaksi khusus yang otomatis dijalankan ketika database mengalami crash media fisik.

**4. Kapan sebaiknya Anda memilih Saga Orchestration dibandingkan Saga Choreography?**
* A. Ketika alur transaksi sangat sederhana dan hanya melibatkan maksimal dua layanan.
* B. Ketika kita ingin menghindari penambahan dependensi baru pada sistem.
* C. Ketika transaksi terdistribusi memiliki banyak tahapan kompleks, memerlukan pemantauan status terpusat, dan tim ingin meminimalisasi risiko kopling event sirkular.
* D. Ketika seluruh tim tidak memahami konsep antrean pesan (message queues).

**5. Manakah teknik terbaik untuk menyelesaikan permasalahan "Dual-Write" saat menyimpan data transaksi lokal ke database dan mengirimkan event ke Kafka?**
* A. Membungkus kedua pemanggilan fungsi di dalam block try-catch.
* B. Mengabaikan kegagalan pengiriman ke Kafka karena jaringan lokal cloud selalu reliabel.
* C. Transactional Outbox Pattern, di mana event disimpan ke tabel lokal terlebih dahulu dalam satu transaksi DB yang sama, lalu di-stream ke Kafka oleh worker eksternal.
* D. Mengirim pesan ke Kafka terlebih dahulu, baru kemudian menyimpan data ke basis data.

---

### Kunci Jawaban & Pembahasan Singkat

1. **Jawaban: B** — Protokol 2PC memegang kunci (*locks*) pada baris data di semua partisipan selama fase persiapan (*prepare phase*) hingga fase komit (*commit phase*). Jika salah satu simpul lambat atau koordinator mengalami kegagalan jaringan, sumber daya terkunci tanpa batas waktu, merusak ketersediaan (*availability*) sistem.
2. **Jawaban: C** — API Gateway generik mengonsolidasikan routing dan keamanan global, sedangkan BFF membagi lapisan agregasi tersebut agar sesuai dengan karakteristik UI masing-masing platform (mobile, web desktop, IoT).
3. **Jawaban: B** — Karena transaksi lokal pada Saga telah melakukan komit permanen (*commit* fisik) pada langkah sebelumnya, sistem tidak dapat melakukan rollback bawaan DB. Sistem harus mengaplikasikan transaksi penyeimbang logis (misal: jika langkah awal adalah memotong saldo, transaksi kompensasi adalah menambahkan kredit saldo kembali).
4. **Jawaban: C** — Pada alur proses bisnis yang rumit (lebih dari 4 langkah), Choreography menjadi *anti-pattern* ("event soup") yang sulit dilacak alurnya. Orchestration menyediakan State Machine eksplisit yang memudahkan pelacakan posisi kegagalan.
5. **Jawaban: C** — Memanggil database dan message broker secara berurutan adalah dua operasi terdistribusi yang tidak atomik. Pendekatan Transactional Outbox Pattern menjamin keandalan *at-least-once publishing* secara deterministik memanfaatkan kapabilitas ACID database lokal.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku Rujukan Utama:**
   * Newman, Sam. (2021). *Building Microservices: Designing Fine-Grained Systems (2nd Edition)*. O'Reilly Media.
   * Richardson, Chris. (2018). *Microservices Patterns: With examples in Java*. Manning Publications.
   * Evans, Eric. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley.
   * Kleppmann, Martin. (2017). *Designing Data-Intensive Applications*. O'Reilly Media.

2. **Whitepapers & Makalah Akademis:**
   * Garcia-Molina, H., & Salem, K. (1987). *Sagas*. ACM SIGMOD Record, 16(3), 249-259. (Makalah asli penemu konsep Saga).
   * Vogels, Werner. (2009). *Eventually Consistent*. Communications of the ACM.

3. **Dokumentasi & Arsitektur Referensi Terbuka:**
   * Microsoft Cloud Design Patterns: *Saga distributed transactions pattern* & *Backends for Frontends pattern*.
   * Temporal.io Documentation: *Concepts of Durable Execution & Orchestration Engine*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Dekomposisi Berbatas Domain:** Pembagian microservices yang sukses didasarkan pada *Bounded Contexts* (DDD) dan *Business Capabilities*, bukan didasarkan pada layer teknis (Controller-Service-Repository) atau kenyamanan pembagian tabel database semata.
* **Separation of Concerns pada Edge Layer:** API Gateway bertindak sebagai benteng perimeter untuk mengonsolidasikan kebijakan *cross-cutting* (autentikasi, kuota, metrik), sementara Backends for Frontends (BFF) bertindak sebagai layer agregasi dan transformasi representasi data yang dispesifikasikan untuk kebutuhan unik setiap antarmuka klien.
* **BASE Menggantikan ACID pada Skala Terdistribusi:** Upaya menerapkan transaksi ACID terdistribusi secara kaku melalui 2PC menghasilkan sistem yang rapuh (*fragile*) dan lambat. Sistem modern merangkul model *Eventual Consistency* (BASE).
* **Saga Pattern sebagai Tulang Punggung Konsistensi:** Saga memecah transaksi global menjadi rangkaian transaksi lokal. Ketiadaan *Isolation* ACID diatasi dengan *Semantic Locks*, sementara kegagalan bisnis ditanggulangi melalui eksekusi *Compensating Transactions* yang dijamin idempoten.
* **Orchestration vs Choreography:** Gunakan *Choreography* untuk alur mikro yang sangat sederhana dan decoupling total; gunakan *Orchestration* untuk alur proses bisnis inti yang kritis, berfase banyak, dan memerlukan visibilitas audit serta kontrol terpusat.

---

## SEKSI 17 — GLOSARIUM

* **Bounded Context:** Batas eksplisit di dalam model domain tempat istilah teknis dan model bisnis tertentu diterapkan secara konsisten dan eksklusif.
* **Compensating Transaction:** Operasi bisnis eksplisit yang memulihkan efek dari transaksi yang telah selesai sebelumnya jika terjadi kegagalan pada langkah berikutnya dalam sebuah Saga.
* **Idempotency:** Karakteristik operasi di mana pemanggilan fungsi satu kali maupun berulang kali dengan parameter input yang sama akan menghasilkan status akhir sistem yang identik tanpa efek samping tambahan.
* **Pivot Transaction:** Langkah transaksional dalam Saga di mana jika operasi ini berhasil diselesaikan, Saga dipastikan tidak akan dibatalkan (*cannot be compensated*) dan harus diselesaikan hingga akhir melalui transaksi-transaksi yang dapat diulang (*retryable*).
* **Strangler Fig Pattern:** Pola refaktor arsitektur dengan cara menempatkan lapisan perantara di depan sistem warisan (*legacy*) dan secara bertahap memigrasikan endpoint/fitur ke layanan baru hingga sistem lama habis tergantikan.
* **Transactional Outbox:** Pola arsitektur di mana pesan yang akan dikirim ke broker disimpan terlebih dahulu di dalam tabel basis data lokal di bawah payung transaksi atomik lokal yang sama dengan pembaruan entitas bisnis.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Pengajaran:** Siswa tingkat lanjut sering kali terlalu cepat melompat ke alat (*tools*) seperti Kafka atau Temporal tanpa memahami masalah fundamental konkurensi data. Tekankan pada konsep **Hilangnya Sifat Isolasi (Isolation Anomaly)** dalam sistem eventual consistency. Bahas studi kasus nyata: apa yang terjadi jika pengguna melihat saldo sudah terpotong tetapi pesanan akhirnya berstatus gagal 2 detik kemudian?
* **Poin Penekanan Demo Kode:** Pada implementasi Seksi 09, instruksikan peserta didik untuk mencoba skenario *infinite retry failure* pada fungsi kompensasi. Minta mereka memikirkan mengapa alerting dan DLQ (*Dead-Letter Queue*) mutlak diperlukan dalam transaksi terdistribusi ketika otomasi kompensasi menemui jalan buntu teknis.
* **Mitigasi Miskonsepsi:** Tekankan bahwa membagi monolit menjadi microservice bukanlah tujuan akhir arsitektur (*not the goal, but a trade-off*). Dekomposisi hanya bernilai jika kecepatan rilis tim (*organizational velocity*) dan skala beban domain memerlukan otonomi independen.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2025-01-15
* **Author:** Tim Kurikulum Software Design & Architecture
* **Perubahan Terakhir:**
  * Inisialisasi rilis modul 06-01: Service Decomposition, API Gateway, BFF, Distributed Transactions & Sagas.
  * Penambahan skema implementasi Saga Orchestrator berbasis TypeScript pada Seksi 09.
  * Standarisasi 20 Seksi Panduan Pedagogis GEMINI.md.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `05-Architectural-Styles/05-Module-04-Event-Driven-Architecture` (Event Sourcing & CQRS Deep Dive)
* **Modul Saat Ini:** `06-Architecture-and-System-Design/06-Module-01-Distributed-Systems-Patterns` (Decomposition, API Gateway, BFF, & Sagas)
* **Modul Berikutnya:** `06-Architecture-and-System-Design/06-Module-02-Fault-Tolerance-and-Resilience` (Circuit Breakers, Bulkheads, Rate Limiting, Backpressure & Chaos Engineering)