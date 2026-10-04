# KURIKULUM: SOFTWARE DESIGN & ARCHITECTURE
## KATEGORI: 06-Architecture-and-System-Design
### BAB 10: Dokumentasi Arsitektur, Tata Kelola (Governance), & Evolusi

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: ARC-10-01
* **Nama Modul**: Dokumentasi Arsitektur, Tata Kelola (Governance), & Evolusi: C4 Model, ADR, Evolutionary Architecture, dan Architecture Fitness Functions
* **Tingkat Kesulitan**: Advanced / Senior
* **Estimasi Waktu Belajar**: 8 Jam Pembelajaran (3 Jam Teori, 5 Jam Praktik/Lab)
* **Prasyarat**: 
  * Pemahaman mendalam tentang prinsip desain perangkat lunak (SOLID, Hexagonal/Clean Architecture).
  * Pemahaman siklus CI/CD pipeline (*Automated Testing*, *Linters*, *Static Code Analysis*).
  * Pengalaman memelihara sistem skala menengah-besar (*distributed systems* atau *modular monolith*).
* **Target Role**: Senior Software Engineer, Lead Developer, Software Architect, Engineering Manager.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1. **Menganalisis dan Memodelkan Topologi Sistem Menggunakan C4 Model**: Menerapkan 4 level abstraksi C4 (*Context*, *Container*, *Component*, *Code*) secara formal menggunakan pendekatan *Diagrams-as-Code* (Structurizr DSL / PlantUML).
2. **Menyusun Keputusan Arsitektur Berstandar Industri (ADR)**: Merumuskan rekaman keputusan arsitektur (*Architecture Decision Records*) yang presisi dengan format Michael Nygard / MADR untuk mendokumentasikan konteks, trade-off, dan konsekuensi sistem.
3. **Mendesain Strategi Evolutionary Architecture**: Mengidentifikasi dimensi perubahan sistem secara inkremental tanpa memicu degradasi struktural (*architectural drift*).
4. **Mengimplementasikan Architecture Fitness Functions**: Mengonfigurasi dan mengotomatisasi pengujian kepatuhan arsitektur (*automated architectural testing*) dalam *pipeline* integrasi berkelanjutan (CI/CD) menggunakan *tools* seperti ArchUnit atau Dependency-Cruiser.
5. **Menegakkan Tata Kelola Arsitektur (Governance)**: Mengintegrasikan mekanisme mitigasi pembusukan perangkat lunak (*software rot*) ke dalam alur kerja rekayasa perangkat lunak harian tim.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Software Architecture Governance & Evolution]
         │
         ├──► 1. VISUALISASI SISTEM (Living Visual Documentation)
         │       └── C4 Model (Simon Brown)
         │           ├── Level 1: System Context (People & Software Systems)
         │           ├── Level 2: Container (Applications, Databases, Message Queues)
         │           ├── Level 3: Component (Modules, Controllers, Repositories)
         │           └── Level 4: Code (UML Class / Implementation Details - Opsional)
         │
         ├──► 2. PENYIMPANAN KEPUTUSAN HISTORIS (Intent & Rationale)
         │       └── Architecture Decision Records (ADR)
         │           ├── Context & Problem Statement
         │           ├── Considered Options & Trade-offs
         │           ├── Decision Outcome & State (Accepted, Superseded)
         │           └── Consequences (Positive & Negative Implications)
         │
         ├──► 3. STRATEGI PERUBAHAN BERKELANJUTAN (Paradigma)
         │       └── Evolutionary Architecture (Neal Ford et al.)
         │           ├── Guided Change (Diarahkan oleh Metrik Terukur)
         │           ├── Incremental Change (Dapat Diluncurkan Bertahap)
         │           └── Multiple Architectural Dimensions (Scalability, Security, Maintainability)
         │
         └──► 4. PENGUJIAN OTOMATIS ARSITEKTUR (Automated Safeguards)
                 └── Architecture Fitness Functions
                     ├── Atomic Functions (Linting, Modularity, Layer Enforcements)
                     ├── Holistic Functions (E2E Latency, Scalability Stress Testing)
                     └── CI/CD Gating (Menolak Merge Request Pelanggar Aturan)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem perangkat lunak mengalami *architectural entropy* atau degradasi struktural seiring waktu. Dokumen arsitektur tradisional berupa Word/Wiki statis hampir selalu usang (*stale*) sejak hari pertama dibuat karena tidak sinkron dengan *source code*. Ketidakmampuan memvisualisasikan dan mengomunikasikan batasan sistem menyebabkan developer baru membuat asumsi keliru, menciptakan dependensi sirkular, dan merusak isolasi domain.

Selain visualisasi, hilangnya konteks historis—*mengapa sebuah teknologi atau pola tertentu dipilih*—memicu fenomena "Chesterton's Fence": developer mengubah atau menghapus arsitektur kritis tanpa memahami alasan awal pembuatan keputusan tersebut, berujung pada regresi sistemik. ADR memitigasi masalah ini dengan menyimpan *rationale* bersama kode.

Terakhir, dokumentasi dan ADR tidak memiliki daya eksekusi tanpa *governance* otomatis. Dalam *Evolutionary Architecture*, kelangsungan hidup suatu sistem bergantung pada *Architecture Fitness Functions*. Tanpa pengujian otomatis ini, aturan pemisahan modular (*misal: modul pembayaran dilarang memanggil modul inventaris secara langsung*) akan dilanggar secara diam-diam melalui *code review* manusia yang rentan luput. Fitness functions mengubah aturan arsitektur pasif menjadi assertions aktif yang dijalankan di setiap *pull request*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. C4 Model (Visualizing Software Architecture)
Diciptakan oleh Simon Brown, C4 Model adalah pendekatan hierarkis untuk memetakan arsitektur perangkat lunak berbasis peta zoom (seperti Google Maps):
*   **System Context (L1)**: Menampilkan sistem yang sedang dibangun, siapa penggunanya (aktor), dan sistem eksternal apa yang berinteraksi dengannya. Level ini berfokus pada audiens non-teknis dan teknis secara makro.
*   **Container (L2)**: Memperbesar batas System Context. "Container" didefinisikan sebagai unit perangkat lunak yang dapat dieksekusi atau menyimpan data secara terpisah (misalnya: Single Page Application, API Backend, Basis Data, Message Broker). Audiens: Software Engineer, DevOps/SRE, Arsitek.
*   **Component (L3)**: Memperbesar satu Container untuk melihat komponen internalnya (misalnya modul otentikasi, service layer, repository layer) beserta dependensi antarkomponen. Audiens: Software Engineer yang bekerja langsung di repositori tersebut.
*   **Code (L4)**: Menampilkan detail implementasi komponen (misal: UML Class Diagram). Jarang digambar manual; umumnya digenerate otomatis dari IDE saat dibutuhkan untuk mereduksi beban pemeliharaan.

### 2. Architecture Decision Records (ADR)
ADR adalah artefak teks sederhana berbasis format Markdown/Asciidoc yang disimpan langsung di repositori kode (*version-controlled*). Satu file ADR merepresentasikan satu keputusan arsitektural yang signifikan.
*   Struktur umum mencakup: Judul, Status (*Proposed, Accepted, Deprecated, Superseded*), Konteks Masalah, Keputusan yang Diambil, serta Konsekuensi (*Trade-offs*, risiko, utang teknis yang disengaja).

### 3. Evolutionary Architecture
Didefinisikan oleh Neal Ford, Rebecca Parsons, dan Patrick Kua sebagai:
> *"An evolutionary architecture supports guided, incremental change across multiple dimensions."*
*   **Guided**: Perubahan dipandu oleh kriteria evaluasi yang objektif.
*   **Incremental**: Sistem dirancang agar dapat dirilis dan diubah per bagian tanpa *big-bang release*.
*   **Multiple Dimensions**: Mempertahankan berbagai atribut kualitas sistem secara simultan (keamanan, keandalan, skalabilitas, konformitas hukum).

### 4. Architecture Fitness Functions
Sebuah mekanisme objektif yang memvalidasi apakah karakteristik arsitektur sistem tetap terjaga seiring evolusi kode. Fitness functions bisa berupa:
*   *Static code analysis* (misal: memvalidasi bahwa Controller tidak boleh memanggil Database Driver secara langsung).
*   *Unit/Integration test-driven architectural fitness* (menggunakan ArchUnit, Dependency-Cruiser, dsb).
*   *Performance/Security synthetic tests* (misal: memverifikasi bahwa p99 response time microservice tidak melebihi 200ms di staging environment).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Alur kerja tata kelola arsitektur berbasis *Evolutionary Architecture* dan *Living Documentation* dioperasikan melalui siklus hidup berikut:

```
[Identifikasi Masalah/Kebutuhan Baru]
                 │
                 ▼
     [Penyusunan RFC / Draf ADR]
                 │
                 ▼
[Diskusi Tim & Persetujuan (Accepted)]
                 │
                 ▼
    [Implementasi Kode & Fitness Function]
         ├── 1. Perbarui C4 Model (Docs-as-Code)
         ├── 2. Tulis Aturan Fitness Function (Assertion Test)
         └── 3. Implementasi Fitur Bisnis
                 │
                 ▼
    [CI/CD Pipeline Execution]
         ├── Menjalankan Unit/Integration Tests
         ├── Menjalankan Architecture Fitness Function
         │     ├── Jika Gagal ──► Tolak PR (Build Failed)
         │     └── Jika Lolos ──► Izinkan Merge
         └── Render Dokumen C4 ke Internal Portal (Docs Site)
```

### Prosedur Implementasi Fitness Function
1. **Definisikan Boundary Modul**: Gunakan konvensi penamaan folder atau package struktur (misal: `domain`, `application`, `infrastructure`, `interfaces`).
2. **Formulasikan Aturan Akses**: Tentukan matriks dependensi antar-layer yang legal dan ilegal.
3. **Terjemahkan ke Assertion**: Tuliskan skrip assertion menggunakan framework fitness function (misal: `dependency-cruiser` untuk Node/TS, `ArchUnit` untuk Java).
4. **Pasang di Pre-commit/CI**: Gagal-kan tahap verifikasi CI (*fail fast*) jika ada developer yang mengimpor modul di luar aturan yang disepakati.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Dekonstruksi C4 Model Hierarchy

```
+-----------------------------------------------------------------------------------+
| LEVEL 1: SYSTEM CONTEXT                                                           |
|                                                                                   |
|  [Customer] ────(HTTPS)────► [E-Commerce Platform] ────(AMQP)────► [Payment Gate] |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Zoom-in Container)
+-----------------------------------------------------------------------------------+
| LEVEL 2: CONTAINER                                                                |
|                                                                                   |
|  [React SPA] ──(JSON/HTTPS)──► [API Gateway / Go] ──(gRPC)──► [Order Service / TS]|
|                                                                       │           |
|                                                          (TCP SQL)    ▼           |
|                                                                 [PostgreSQL DB]   |
+-----------------------------------------------------------------------------------+
                                                                        │
                                                                        ▼ (Zoom-in)
+-----------------------------------------------------------------------------------+
| LEVEL 3: COMPONENT (Inside Order Service)                                         |
|                                                                                   |
|  [Order Controller] ──► [Order Service (App Logic)] ──► [Order Repository]        |
|                                     │                          │                  |
|                                     ▼                          ▼                  |
|                             [Order Domain Model]      [Postgres Adapter]          |
+-----------------------------------------------------------------------------------+
                                                                        │
                                                                        ▼ (Zoom-in)
+-----------------------------------------------------------------------------------+
| LEVEL 4: CODE (Class Level - Seringkali Generated)                               |
|                                                                                   |
|  +-------------------------+             +-------------------------+              |
|  |     OrderRepository     |◄────────────|   PostgresOrderAdapter  |              |
|  +-------------------------+             +-------------------------+              |
|  | +findById(id: UUID)     |             | -dbClient: PoolClient   |              |
|  +-------------------------+             | +findById(id: UUID)     |              |
|                                          +-------------------------+              |
+-----------------------------------------------------------------------------------+
```

### 2. Mekanisme Architecture Fitness Function dalam Pipeline CI/CD

```
+----------------------------------------------------------------------------------------+
| PULL REQUEST TRIGGERED: PR #1042 ("Add Payment Notification")                         |
+----------------------------------------------------------------------------------------+
       │
       ▼
 [Static Analysis & Linters] ──► PASSED
       │
       ▼
 [Architecture Fitness Functions]
       │
       ├── Assertion 1: Domain Layer Cleanliness
       │   └── Check: `import * from 'domain/..'` DOES NOT IMPORT `infra/..`?
       │   └── Result: OK
       │
       ├── Assertion 2: Bounded Context Isolation
       │   └── Check: `modules/billing` DOES NOT DIRECTLY IMPORT `modules/warehouse`?
       │   └── Result: FAILED!
       │       └── VIOLATION: `modules/billing/invoice.ts:14` 
       │                      imports `modules/warehouse/stock_manager.ts`
       │
       ▼
+----------------------------------------------------------------------------------------+
| GITHUB ACTIONS / CI RESULT: FAILED (Exit Code 1)                                       |
| "PR Rejected: Direct boundary crossover detected. Communicate via Domain Events."    |
+----------------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh artefak ADR sederhana dengan format Michael Nygard standar untuk mencatat pemilihan sistem penyimpanan transaksi.

### File: `docs/adr/0004-use-postgresql-for-ledger.md`

```markdown
# 4. Penggunaan PostgreSQL dengan Serializable Isolation Level untuk Distributed Ledger

* Status: accepted
* Tanggal: 2026-03-30
* Penulis: Tim Arsitektur & Core Banking

## Konteks
Sistem pembukuan saldo (ledger) membutuhkan persistensi data transaksi dengan konsistensi 
tinggi (*strict serializability*) guna menghindari fenomena *double-spending* atau *lost updates*. 
Kami sebelumnya mempertimbangkan DynamoDB (NoSQL) untuk skalabilitas throughput tinggi 
dan PostgreSQL (RDBMS) untuk kapabilitas jaminan kepatuhan ACID.

## Keputusan
Kami memutuskan untuk menggunakan PostgreSQL (RDS Aurora) sebagai sistem persistensi utama 
komponen Ledger dengan default isolation level `SERIALIZABLE`. 

Komunikasi lintas modul dibatasi: modul lain dilarang membaca tabel transaksi secara langsung. 
Setiap pembacaan riwayat transaksi wajib melalui GraphQL Query internal.

## Konsekuensi

### Positif:
* Jaminan ACID terverifikasi secara bawaan oleh database engine.
* Pengurangan kompleksitas penulisan distributed lock di tingkat aplikasi.
* Audit trial mudah dibuat melalui immutable append-only pattern menggunakan foreign-key constraints.

### Negatif / Risiko:
* Throughput transaksi maksimal terbatas pada kapabilitas penulisan satu node master (vertically scaled).
* Terjadinya transaksi gagal akibat *serialization failure (40001)* yang mengharuskan 
  komponen aplikasi memiliki mekanisme otomatisasi *retry with exponential backoff*.
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kita akan mengimplementasikan skema tata kelola arsitektur berbasis TypeScript untuk layanan `Order Management System` bergaya Hexagonal Architecture.

### Struktur Direktori Proyek

```text
order-service/
├── docs/
│   └── adr/
│       └── 0001-enforce-hexagonal-boundaries.md
├── src/
│   ├── domain/               <-- Inti domain (tidak boleh ada dependensi eksternal)
│   │   ├── model/
│   │   │   └── order.ts
│   │   └── ports/
│   │       └── order-repository.port.ts
│   ├── application/          <-- Application use-cases (hanya impor domain)
│   │   └── create-order.usecase.ts
│   └── infrastructure/       <-- DB adapters, HTTP handlers (boleh impor application & domain)
│       ├── database/
│       │   └── pg-order.repository.ts
│       └── http/
│           └── order.controller.ts
├── .dependency-cruiser.js    <-- Definisi Fitness Function
├── package.json
└── tsconfig.json
```

### 1. Definisi Model & Port (src/domain)

```typescript
// src/domain/model/order.ts
export interface OrderItem {
  sku: string;
  quantity: number;
  unitPrice: number;
}

export class Order {
  constructor(
    public readonly id: string,
    public readonly customerId: string,
    public readonly items: OrderItem[],
    public status: 'PENDING' | 'PAID' | 'CANCELLED'
  ) {
    if (items.length === 0) {
      throw new Error("Order harus memiliki minimal satu item.");
    }
  }

  public calculateTotal(): number {
    return this.items.reduce((acc, item) => acc + item.quantity * item.unitPrice, 0);
  }
}

// src/domain/ports/order-repository.port.ts
import { Order } from "../model/order";

export interface OrderRepositoryPort {
  save(order: Order): Promise<void>;
  findById(id: string): Promise<Order | null>;
}
```

### 2. Implementasi Use Case (src/application)

```typescript
// src/application/create-order.usecase.ts
import { Order, OrderItem } from "../domain/model/order";
import { OrderRepositoryPort } from "../domain/ports/order-repository.port";

export interface CreateOrderDTO {
  orderId: string;
  customerId: string;
  items: OrderItem[];
}

export class CreateOrderUseCase {
  constructor(private readonly orderRepo: OrderRepositoryPort) {}

  async execute(dto: CreateOrderDTO): Promise<void> {
    const order = new Order(dto.orderId, dto.customerId, dto.items, 'PENDING');
    await this.orderRepo.save(order);
  }
}
```

### 3. File Definisi Fitness Function (.dependency-cruiser.js)

File konfigurasi ini adalah **Architecture Fitness Function** yang bertindak sebagai satpam dependensi otomatis saat build pipeline berjalan:

```javascript
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'domain-must-not-depend-on-outer-layers',
      comment: 'Fitness Function: Domain layer must be pure and independent of Application or Infrastructure.',
      severity: 'error',
      from: {
        path: '^src/domain'
      },
      to: {
        path: '^src/(application|infrastructure)'
      }
    },
    {
      name: 'application-must-not-depend-on-infrastructure',
      comment: 'Fitness Function: Application use-cases must not directly depend on Infrastructure (Inversion of Control).',
      severity: 'error',
      from: {
        path: '^src/application'
      },
      to: {
        path: '^src/infrastructure'
      }
    },
    {
      name: 'no-circular-dependencies',
      comment: 'Fitness Function: Circular dependencies erode maintainability and create tight coupling.',
      severity: 'error',
      from: {},
      to: {
        circular: true
      }
    }
  ],
  options: {
    doNotFollow: {
      path: 'node_modules'
    },
    tsPreCompilationDeps: true,
    tsConfig: {
      fileName: 'tsconfig.json'
    }
  }
};
```

### 4. Demonstrasi Pelanggaran Arsitektur (Anti-Pattern)

Katakanlah ada pengembang baru yang secara keliru mengimpor adapter database ke dalam Domain Model:

```typescript
// src/domain/model/bad-order-extension.ts
import { PostgresOrderRepository } from "../../infrastructure/database/pg-order.repository"; // <-- PELANGGARAN ATURAN

export class BadOrderExtension {
  // Melanggar prinsip Dependency Inversion dan Hexagonal Architecture
  private repo = new PostgresOrderRepository();
}
```

### 5. Eksekusi Assertion dalam CI Pipeline

Tambahkan skrip ini pada `package.json`:

```json
{
  "scripts": {
    "test:fitness": "depcruise --config .dependency-cruiser.js src"
  }
}
```

Saat dieksekusi di terminal:
```bash
$ npm run test:fitness
```

**Output Terminal:**
```text
  error domain-must-not-depend-on-outer-layers: src/domain/model/bad-order-extension.ts -> src/infrastructure/database/pg-order.repository.ts

✖ 1 dependency violations (1 errors, 0 warnings). 14 modules, 19 dependencies cruised.
npm ERR! Lifecycle script failed with error: code 1
```
Build pipeline langsung berhenti, mencegah kode tersebut di-merge ke branch utama. Arsitektur terjaga secara objektif dan matematis.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek | Pilihan A (Dokumentasi Statis & Review Manual) | Pilihan B (Docs-as-Code, ADR & Automated Fitness Functions) |
|---|---|---|
| **Upfront Effort** | Rendah. Siapa saja dapat langsung menulis di Wiki / Confluence tanpa setup tooling. | Sedang-Tinggi. Memerlukan integrasi tooling di CI/CD, setup linters, dan kurva adaptasi tim. |
| **Akurasi Berkelanjutan** | Rendah. Dokumentasi basi dalam hitungan minggu seiring iterasi fitur. | Sangat Tinggi. Dokumentasi dan ruleset berada di satu repositori bersama kode (*version-matched*). |
| **Governance Enforcement** | Subjektif & Rentan Eror. Kepatuhan bergantung sepenuhnya pada ketelitian manusia saat PR review. | Objektif & Deterministik. Pipeline CI langsung memblokir PR jika aturan dependensi dilanggar. |
| **Maintainability** | Beban kognitif tinggi saat orientasi developer baru (*tribal knowledge* dominan). | Beban terukur; sistem secara eksplisit menolak evolusi kode yang merusak struktur. |
| **Fleksibilitas Desain** | Sangat fleksibel (cenderung longgar hingga timbul arsitektur bola lumpur / *spaghetti*). | Butuh proses eksplisit untuk memperbarui batasan arsitektur (harus mengubah ADR & ruleset). |

---

## SEKSI 11 — BEST PRACTICES

1. **Jadikan ADR Sebagai Dokumen Immutable Pasca-Merge**: Jangan pernah mengedit *decision outcome* ADR yang sudah berstatus `Accepted`. Jika keputusan diubah di masa depan karena perubahan konteks, buat ADR baru dengan status `Supersedes ADR-XXXX` dan ubah status ADR lama menjadi `Superseded`.
2. **Docs-as-Code di Folder yang Sama**: Tempatkan direktori `docs/adr` dan file diagram DSL (misal: Structurizr DSL atau PlantUML) tepat di repositori kode terkait, bukan di portal eksternal yang terisolasi.
3. **Fitness Functions Harus Masuk `PR-Gating` Pipeline**: Jangan jadikan fitness function sebagai "rekomendasi". Setiap kegagalan ruleset arsitektur harus menggagalkan build CI (*hard failure*).
4. **Hindari Level 4 C4 Model Secara Manual**: Diagram Level 4 (Code) sangat cepat usang. Cukup petakan L1 hingga L3. L4 hanya digambar sementara (*on-the-fly*) saat mendiskusikan algoritma atau pola perilaku kelas yang sangat rumit.
5. **Kategorisasikan ADR Sesuai Urgensi**: Gunakan ADR untuk keputusan arsitektural yang mahal dibatalkan (*one-way door decisions*), seperti pemilihan database, framework inti, atau batas Bounded Context. Jangan buat ADR untuk detail sepele seperti konvensi indentasi tab vs space.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Menjadikan C4 Model Seperti Data Flow Diagram (DFD)**: Memasukkan logika bisnis percabangan (*if-else logic*) ke dalam diagram C4 Level 2 atau Level 3. Diagram arsitektur memetakan struktur statis dan boundary tanggung jawab, bukan *sequence flow* eksekusi runtut.
2. **ADR Tanpa Konsekuensi Negatif (*Wishful Thinking*)**: Menulis ADR hanya dengan daftar keuntungan tanpa mengeksplorasi trade-off kerugian. Setiap keputusan arsitektur pasti mengorbankan atribut lain (misal: "Memilih microservices demi otonomi tim, namun mengorbankan kesederhanaan operasional dan konsistensi transaksi").
3. **Fitness Function yang Terlalu Kaku (*Brittle Constraints*)**: Menulis assertion yang memvalidasi detail implementasi internal alih-alih boundary sistem. Hal ini membuat refaktorisasi internal yang sah memicu error palsu (*false positive*), sehingga tim cenderung mendisabilitas fungsi pengecekan tersebut.
4. **Dokumentasi Terpusat di Confluence/Notion yang Tidak Terawat**: Membiarkan dokumen terpisah dari siklus hidup Git branch, menghasilkan jurang pemisah antara representasi visual dan realitas kode produksi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Kasus
Sebuah aplikasi e-commerce monolitik modular memiliki modul `Billing` dan `Warehouse`. Arsitektur tim melarang modul `Billing` memanggil modul `Warehouse` secara langsung via *function/method call* internal karena modul `Warehouse` sedang disiapkan untuk diekstrak menjadi microservice tersendiri di kuartal berikutnya. Semua komunikasi lintas modul harus melalui Event Bus.

### Tugas:
1. **Tuliskan Dokumen ADR**:
   * Buat file `docs/adr/0012-decouple-billing-and-warehouse-via-events.md`.
   * Cantumkan minimal: Konteks, Keputusan, dan 2 Konsekuensi Positif serta 1 Konsekuensi Negatif.
2. **Desain C4 Level 3 Component DSL**:
   * Tuliskan deklarasi Structurizr DSL ringkas yang memodelkan komponen `BillingService`, `WarehouseService`, dan `EventBus`.
3. **Tulis Architecture Fitness Function**:
   * Buat aturan `forbidden` pada `.dependency-cruiser.js` yang menggagalkan eksekusi build jika file di dalam direktori `src/billing/**` mengimpor file dari `src/warehouse/**`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pada level C4 Model yang manakah sebuah "PostgreSQL Database" atau "RabbitMQ Broker" pertama kali dimodelkan?**
   * A. System Context (Level 1)
   * B. Container (Level 2)
   * C. Component (Level 3)
   * D. Code (Level 4)
   * *Jawaban*: **B**. Container adalah unit perangkat lunak independen yang dapat berjalan sendiri (aplikasi web, basis data, worker queue, file system).

2. **Apa yang harus dilakukan ketika keputusan arsitektur yang didokumentasikan pada ADR 0005 tidak lagi relevan akibat migrasi cloud provider baru?**
   * A. Menghapus file `0005-xxx.md` dari riwayat commit Git.
   * B. Mengedit teks di dalam `0005-xxx.md` secara langsung dan menimpa riwayat lama.
   * C. Membuat ADR baru (misal `0015-xxx.md`), menandainya sebagai `Supersedes 0005`, dan memperbarui status ADR 0005 menjadi `Superseded`.
   * D. Membiarkannya begitu saja tanpa pencatatan baru.
   * *Jawaban*: **C**. ADR bersifat immutable logbook historis. Pembaruan dilakukan dengan membuat ADR baru yang mengabstraksi atau menganulir ADR lama.

3. **Manakah dari pernyataan berikut yang merupakan contoh valid dari Architecture Fitness Function?**
   * A. Unit test untuk memastikan fungsi `calculateDiscount()` mengembalikan angka positif.
   * B. Tes integrasi yang memeriksa apakah database mengembalikan status HTTP 200.
   * C. Automated static test yang memvalidasi bahwa tidak ada layer `Infrastructure` yang diimpor oleh layer `Domain`.
   * D. User Acceptance Test (UAT) manual yang dilakukan oleh Product Owner.
   * *Jawaban*: **C**. Fitness function memvalidasi atribut integritas struktural arsitektur sistem secara otomatis, bukan semata logika bisnis unit individual.

4. **Menurut prinsip Evolutionary Architecture oleh Neal Ford, apa tujuan utama penggunaan fitness functions?**
   * A. Menjamin kode bebas dari bug 100%.
   * B. Memberikan panduan (*guided change*) yang terukur agar karakteristik struktural arsitektur tidak terdegradasi saat sistem berevolusi.
   * C. Menghapus kebutuhan peran Software Architect di dalam tim.
   * D. Mempercepat waktu kompilasi kode pada pipeline CI.
   * *Jawaban*: **B**. Arsitektur evolusioner berlandaskan *guided, incremental change*, di mana fitness functions menjadi panduannya.

5. **Mengapa pemetaan C4 Model Level 4 (Code) secara manual umumnya dianggap sebagai anti-pattern dalam dokumentasi skala besar?**
   * A. Karena C4 Model tidak mendukung representasi class diagram.
   * B. Karena biaya pemeliharaan manual (*maintenance overhead*) sangat tinggi dan diagram akan langsung usang begitu baris kode diperbarui.
   * C. Karena pengembang junior dilarang melihat struktur kelas sistem.
   * D. Karena diagram Level 4 hanya boleh digambar menggunakan format SVG statis.
   * *Jawaban*: **B**. Volatilitas kode sangat tinggi; menggambar L4 secara manual adalah pemborosan waktu. L4 sebaiknya di-generate otomatis oleh IDE bila perlu.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku**:
  * *Building Evolutionary Architectures: Automated Software Governance (2nd Edition)* oleh Neal Ford, Rebecca Parsons, Patrick Kua, & Pramod Sadalage (O'Reilly Media).
  * *Software Architecture for Developers* (Vol. 1 & 2) oleh Simon Brown (Pencipta C4 Model).
  * *Release It!: Design and Deploy Production-Ready Software* oleh Michael Nygard (Pencetus format ADR awal).
* **Standar & Dokumentasi Web**:
  * [The C4 Model for Visualizing Software Architecture](https://c4model.com/) — Simon Brown.
  * [MADR (Markdown Architectural Decision Records)](https://adr.github.io/madr/) — Template & Tooling ADR terbuka.
  * [Dependency-Cruiser Documentation](https://github.com/sverweij/dependency-cruiser) — Tooling automated fitness validation untuk JS/TS.
  * [ArchUnit.org](https://www.archunit.org/) — Unit testing Java architecture rules.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

| Pilar Tata Kelola Arsitektur | Instrumen | Manfaat Utama | Titik Penegakan (Enforcement Point) |
|---|---|---|---|
| **Visualisasi** | C4 Model (L1 - L4) | Menyediakan peta hierarkis sistem dari perspektif makro ke mikro tanpa ambiguitas UML klasik. | Docs-as-Code repository, auto-rendered pada internal portal. |
| **Histori & Konteks** | ADR (Architecture Decision Records) | Mengawetkan pertimbangan trade-off, konteks masalah, dan alasan pemilihan teknologi masa lampau. | Code review, commit history pada Git repository. |
| **Strategi Evolusi** | Evolutionary Architecture | Memungkinkan arsitektur beradaptasi dengan kebutuhan bisnis baru secara inkremental. | Desain decoupled, modul batas terisolasi (*Bounded Contexts*). |
| **Validasi Otomatis** | Architecture Fitness Functions | Mengubah aturan arsitektur menjadi unit assertions otomatis yang menjaga batas layer. | Continuous Integration (CI) test execution. |

---

## SEKSI 17 — GLOSARIUM

* **Architectural Drift (Pembusukan Arsitektur)**: Kondisi saat implementasi kode nyata menyimpang jauh dari model arsitektur yang direncanakan akibat modifikasi tanpa kontrol ketat.
* **C4 Model**: Framework visualisasi arsitektur yang membagi perangkat lunak ke dalam 4 skala zoom: Context, Container, Component, dan Code.
* **Architecture Decision Record (ADR)**: Berkas teks pendek yang mendokumentasikan keputusan arsitektur penting beserta konteks dan konsekuensinya.
* **Evolutionary Architecture**: Pola arsitektur yang memfasilitasi perubahan bertahap dan terarah pada beberapa dimensi atribut sistem sekaligus seiring waktu.
* **Architecture Fitness Function**: Setiap mekanisme objektif (skrip pengujian otomatis, metrik, monitor) yang memverifikasi integritas karakteristik arsitektur.
* **Bounded Context**: Pola Domain-Driven Design (DDD) yang menetapkan batas eksplisit di mana model domain tertentu berlaku sepenuhnya.
* **Docs-as-Code**: Filosofi penulisan dokumentasi teknis menggunakan alat, format (Markdown/AsciiDoc), dan workflow yang sama dengan penulisan kode (Git, Review, CI/CD).
* **Structural Coupling**: Tingkat ketergantungan antar-modul secara langsung yang jika tidak dibatasi akan menghasilkan arsitektur monolit tak terurai (*Big Ball of Mud*).

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Kritis Pedagogis**: Peserta didik sering kali keliru menyamakan Container pada C4 Model dengan "Docker Container". Jelaskan dengan tegas bahwa *Container* pada C4 adalah batas proses/eksekusi runtime perangkat lunak (misalnya: API Service berbasis Node.js yang berjalan langsung di VM tanpa Docker tetap berstatus "Container" dalam C4).
* **Saran Simulasi Lab**: Saat mengajarkan modul ini, sengajakan memasukkan file baru yang melanggar *hexagonal layers* (misal: layer domain memanggil ORM Entity). Minta peserta didik menjalankan fitness function dan melihat bagaimana pipeline CI memblokir pelanggaran tersebut secara visual. Ini memvalidasi konsep *automated governance* lebih kuat daripada teori ceramah.
* **Fokus Diskusi ADR**: Arahkan diskusi ke seputar bagian *Consequences*. Tekankan bahwa ADR yang tidak menuliskan konsekuensi negatif (*downside*) adalah ADR yang cacat analisis teknisnya.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 2026-03-30
* **Perubahan Terakhir**:
  * Rilis modul inisial lengkap untuk Bab 10 Module 01.
  * Penambahan konfigurasi praktis `.dependency-cruiser.js` untuk demonstrasi langsung *fitness functions*.
  * Integrasi contoh ADR berstandar Michael Nygard / MADR.
* **Penyusun**: Senior Technical Curriculum Architect (Core Architecture Group).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `<-` [ARC-09-03: Distributed Tracing, Telemetry, and Observability Patterns](../09-observability/03-distributed-tracing-telemetry.md)
* **Modul Saat Ini**: [ARC-10-01: Dokumentasi Arsitektur, Tata Kelola (Governance), & Evolusi]
* **Modul Berikutnya**: `->` [ARC-10-02: Microservices Migration Strategies: Strangler Fig, Anti-Corruption Layer, and CDC Patterns](./02-migration-strangler-cdc.md)