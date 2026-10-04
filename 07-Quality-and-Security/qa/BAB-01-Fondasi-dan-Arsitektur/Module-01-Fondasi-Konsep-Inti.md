# Bab 01 Module 01: Fondasi Software Quality Assurance, Testing Pyramid, dan Test Execution Lifecycle

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** arsitektur pengujian perangkat lunak menggunakan model *Testing Pyramid* dan *Testing Trophy* untuk mengoptimalkan alokasi *test budget* (waktu eksekusi, biaya komputasi, dan *maintenance overhead*).
- **Mengidentifikasi** perbedaan mendasar antara verifikasi (*Verification*) dan validasi (*Validation*), serta dampaknya terhadap siklus hidup cacat piranti lunak (*defect life cycle*).
- **Mengimplementasikan** *custom assertion engine* dan *test harness* deterministik dari prinsip dasar (*first principles*) tanpa ketergantungan pada *framework* eksternal.
- **Mengevaluasi** metrik kualitas perangkat lunak secara kritis, membedakan antara *Line/Branch Coverage* dan *Mutation Testing Score*.
- **Merancang** strategi mitigasi terhadap *flaky tests*, *state pollution*, dan *test interdependency* pada *Continuous Integration* (CI) *pipeline*.

---

### 2. Introduction & Conceptual Mental Model
Software Quality Assurance (SQA) bukanlah aktivitas pasca-pengembangan (*afterthought*) yang bertugas mencari *bug* secara manual sebelum rilis. SQA adalah rekayasa sistemik (*systemic engineering discipline*) yang dirancang untuk membuktikan atau menyangkal hipotesis tentang kebenaran (*correctness*), ketahanan (*resilience*), dan performa perangkat lunak dalam batasan operasional tertentu.

Mental model yang tepat untuk memandang SQA adalah **Filter Probabilistik Multi-Lapisan (Swiss Cheese Model)**. 

```
[ Spesifikasi & Desain ] 
       │
       ▼
 ┌───────────┐  Lapisan 1: Static Analysis & Type Checking (Linting, Typings)
 │ ░░ █ ░░░░ │  ---> Menangkap cacat sintaksis & tipe data pada compile-time
 └─────┬─────┘
       │
 ┌─────▼─────┐  Lapisan 2: Unit Testing & Contract Tests
 │ ░░░░ █ ░░ │  ---> Menangkap kegagalan logika algoritma & domain logic
 └─────┬─────┘
       │
 ┌─────▼─────┐  Lapisan 3: Integration & Component Testing
 │ ░█ ░░░░░░ │  ---> Menangkap *misalignment* protokol I/O, DB, & side-effects
 └─────┬─────┘
       │
 ┌─────▼─────┐  Lapisan 4: End-to-End (E2E) & Smoke Testing
 │ ░░░░░ █ ░ │  ---> Memvalidasi *critical user journeys* dan *system wiring*
 └─────┬─────┘
       ▼
 [ Production Release ]
```

Setiap lapisan pengujian memiliki "lubang" (keterbatasan deteksi dan *blind spots*). Cacat sistemik (*systemic defects*) terjadi di *production* hanya ketika lubang pada setiap lapisan berada pada satu garis lurus yang sama. Tugas seorang QA Architect adalah memperkecil diameter lubang tersebut dan memastikan lapisan-lapisan ini disusun secara optimal dari segi latensi umpan balik (*feedback loop latency*) dan determinisme eksekusi.

---

### 3. Why This Matters
Dalam sistem terdistribusi modern dan arsitektur *microservices*, kesalahan logika atau asumsi integrasi yang salah memiliki dampak eksponensial.

1. **Biaya Deteksi Cacat (Rule of Ten / Boehm's Law):**
   Cacat yang lolos dari fase pengujian unit lokal dan baru terdeteksi pada fase E2E atau *Production* membutuhkan biaya mitigasi hingga $100\times$ lebih tinggi. Hal ini mencakup waktu *debugging*, *rollback*, kerusakan reputasi, hingga kompensasi *Service Level Agreement* (SLA).

2. **Anti-pattern "Ice Cream Cone" (Inverted Pyramid):**
   Banyak organisasi bergantung secara berlebihan pada pengujian manual dan E2E UI testing otomatis, sementara pengujian unit dan integrasinya sangat minim.
   - **Dampak:** Eksekusi CI lambat (berjam-jam), tingkat *flakiness* tinggi (>15%), sulit melokalisasi akar masalah saat terjadi kegagalan (*high mean-time-to-detect*), dan *developer velocity* lumpuh.

3. **Ilusi 100% Code Coverage:**
   Organisasi yang mengejar 100% *code coverage* secara buta sering kali menghasilkan ribuan *test assertions* yang tidak bernilai (*tautological tests*), yang hanya mengeksekusi baris kode tanpa memvalidasi *invariants* dan *boundary conditions*. Saat kode di-refactor, pengujian ini justru menghambat perubahan (*brittle tests*).

---

### 4. What It Is Under the Hood
Di balik antarmuka *test runner* populer (seperti Jest, Vitest, Pytest, atau Go `testing`), sebuah proses pengujian beroperasi melalui tahapan deterministik pada tingkat *runtime*:

1. **Test Discovery & AST Parsing:**
   Test runner memindai sistem berkas menggunakan *glob pattern*, membaca file uji, dan membangun *Abstract Syntax Tree* (AST) untuk mengekstrak blok `describe`, `it`, atau `test`.

2. **Isolasi Konteks Runtime (Sandboxing):**
   Setiap berkas uji umumnya diisolasi dalam *worker process* atau *thread* terpisah (misalnya menggunakan V8 `Worker Threads` pada Node.js atau `fork()` pada Unix) guna mencegah kontaminasi memori global (`globalThis`, `window`, mutable singletons).

3. **Lifecycle Hooks Pipeline:**
   Runner mengeksekusi hook dengan urutan hierarkis:
   $$\text{Global Setup} \to \text{BeforeAll} \to (\text{BeforeEach} \to \text{Test Execution} \to \text{AfterEach})^N \to \text{AfterAll} \to \text{Global Teardown}$$

4. **Assertion Evaluation & Error Capture:**
   Sebuah *assertion* adalah ekspresi Boolean yang dievaluasi saat runtime. Jika kondisi bernilai `false`, assertion library akan melempar sebuah *exception* khusus (misalnya `AssertionError`) yang membawa *stack trace*, nilai aktual (*actual*), dan nilai yang diharapkan (*expected*). Runner menangkap (*catch*) exception ini, menandai tes sebagai `FAILED`, merekam *diff*, lalu melanjutkan eksekusi ke tes berikutnya tanpa menghentikan keseluruhan proses runner (kecuali jika flag `fail-fast` aktif).

---

### 5. How to Think About It
Pikirkan pengujian perangkat lunak seperti **Sistem Inspeksi Pabrik Perakitan Otomotif**:

- **Unit Test (Inspeksi Baut & Piston):** Anda menguji komponen terkecil secara terisolasi di meja laboratorium. Apakah ulir baut sesuai spesifikasi toleransi mikrometer? (Cepat, murah, jutaan komponen diuji per detik).
- **Integration Test (Inspeksi Blok Mesin):** Piston, poros engkol (*crankshaft*), dan busi dirakit. Apakah percikan api busi memicu pembakaran di dalam silinder yang memutar poros? Anda tidak menguji seluruh mobil, hanya subsistem mekanik yang saling terhubung.
- **E2E Test (Uji Jalan di Sirkuit / Crash Test):** Mobil utuh diturunkan ke lintasan beraspal dengan pengemudi uji. Apakah mobil melaju lurus saat pedal gas diinjak, AC menyala, dan sistem navigasi bekerja? (Sangat mahal, lambat, melibatkan semua subsistem).

Melakukan uji jalan di sirkuit hanya untuk memastikan apakah baut alternator longgar adalah tindakan yang membuang waktu dan sumber daya komputasi.

---

### 6. Architecture / Execution Flow Diagram
Berikut adalah siklus hidup eksekusi tes (*Test Execution Lifecycle*) dari inisiasi CLI hingga pembuatan laporan hasil pengujian.

```
       CLI Invocation (e.g., `npm test` / `pytest`)
                         │
                         ▼
             ┌───────────────────────┐
             │ Global Config & Setup │
             └───────────┬───────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  Test Discovery & Graph Building │
        └────────────────┬─────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
 ┌───────────────┐               ┌───────────────┐
 │ Worker Node 1 │ (Parallel)    │ Worker Node 2 │
 └───────┬───────┘               └───────┬───────┘
         │                               │
         ├─► BeforeAll Hook              ├─► BeforeAll Hook
         │                               │
         │   ┌─► BeforeEach Hook         │   ┌─► BeforeEach Hook
         │   │                           │   │
         │   ├─► Test Execution          │   ├─► Test Execution
         │   │   ├── Assertions          │   │   ├── Assertions
         │   │   └── State Validations   │   │   └── State Validations
         │   │                           │   │
         │   └─► AfterEach Hook          │   └─► AfterEach Hook
         │       (Loop for N tests)      │       (Loop for N tests)
         │                               │
         ├─► AfterAll Hook               ├─► AfterAll Hook
         │                               │
         └───────────────┬───────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │   Result Aggregator & Reporter   │
        └────────────────┬─────────────────┘
                         │
     ┌───────────────────┴───────────────────┐
     ▼                                       ▼
[Exit Code 0: SUCCESS]               [Exit Code 1: FAILURE]
                                     (Output Diff & Stack Trace)
```

---

### 7. Minimal Viable Code Example
Berikut adalah implementasi *bare-metal* sebuah *Test Runner* dan *Assertion Library* dalam TypeScript tanpa dependensi eksternal, untuk memahami cara kerja fundamental dari runner pengujian.

```typescript
// mini-test-runner.ts

// 1. Error Domain Spesifik untuk Asersi
class AssertionError extends Error {
  constructor(public actual: unknown, public expected: unknown, message: string) {
    super(message);
    this.name = 'AssertionError';
  }
}

// 2. Core Assertion Engine
export function expect<T>(actual: T) {
  return {
    toBe(expected: T): void {
      if (actual !== expected) {
        throw new AssertionError(
          actual,
          expected,
          `Expected ${JSON.stringify(expected)}, but received ${JSON.stringify(actual)}`
        );
      }
    },
    toThrow(expectedErrorSubstring?: string): void {
      if (typeof actual !== 'function') {
        throw new AssertionError(actual, 'Function', 'Target must be a function to test exceptions');
      }
      let threw = false;
      let errorThrown: unknown;
      try {
        actual();
      } catch (err) {
        threw = true;
        errorThrown = err;
      }
      if (!threw) {
        throw new AssertionError('NO_EXCEPTION', 'Exception', 'Expected function to throw, but it did not.');
      }
      if (expectedErrorSubstring && errorThrown instanceof Error) {
        if (!errorThrown.message.includes(expectedErrorSubstring)) {
          throw new AssertionError(
            errorThrown.message,
            expectedErrorSubstring,
            `Expected error message to contain "${expectedErrorSubstring}", but got "${errorThrown.message}"`
          );
        }
      }
    }
  };
}

// 3. Test Registry & Lifecycle Manager
type TestFn = () => void | Promise<void>;

interface TestCase {
  description: string;
  fn: TestFn;
}

const testQueue: TestCase[] = [];

export function test(description: string, fn: TestFn): void {
  testQueue.push({ description, fn });
}

// 4. Test Execution Runner
export async function runTests(): Promise<void> {
  console.log(`\n=== Running ${testQueue.length} registered test(s) ===\n`);
  let passed = 0;
  let failed = 0;

  for (const { description, fn } of testQueue) {
    const startTime = performance.now();
    try {
      await fn();
      const duration = (performance.now() - startTime).toFixed(2);
      console.log(`\x1b[32m✔ PASS\x1b[0m ${description} (${duration}ms)`);
      passed++;
    } catch (error) {
      const duration = (performance.now() - startTime).toFixed(2);
      console.error(`\x1b[31m✖ FAIL\x1b[0m ${description} (${duration}ms)`);
      if (error instanceof AssertionError) {
        console.error(`  ${error.message}`);
        console.error(`  Expected: \x1b[32m${JSON.stringify(error.expected)}\x1b[0m`);
        console.error(`  Actual:   \x1b[31m${JSON.stringify(error.actual)}\x1b[0m`);
      } else {
        console.error(`  Unexpected Error:`, error);
      }
      failed++;
    }
  }

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${testQueue.length} total.`);
  if (failed > 0) {
    process.exit(1);
  }
}

// --- Contoh Penggunaan Langsung ---
function add(a: number, b: number): number {
  return a + b;
}

test('Fungsi add() harus menjumlahkan dua bilangan dengan presisi benar', () => {
  expect(add(2, 3)).toBe(5);
});

test('Fungsi add() menangani skenario batas angka negatif', () => {
  expect(add(-1, -1)).toBe(-2);
});

// Menjalankan runner jika file ini dieksekusi langsung
if (require.main === module) {
  runTests();
}
```

---

### 8. Deep Dive: How the Code Works
Mari kita telaah mekanisme internal dari implementasi minimal di atas:

1. **Kelas `AssertionError` (Baris 3–9):**
   Kelas ini mewarisi objek dasar `Error` di JavaScript. Nilai `actual` dan `expected` disimpan secara eksplisit pada instance objek. Hal ini memungkinkan *reporter* mengekstrak metadata perbandingan secara terstruktur untuk kalkulasi representasi perbedaan (*diff visual*), bukan sekadar mencetak *string* mentah.

2. **DSL `expect()` (Baris 11–43):**
   Fungsi ini memanfaatkan teknik *fluent API pattern* (*method chaining*). Ketika `expect(actual)` dipanggil, ia mengembalikan kumpulan matcher (`toBe`, `toThrow`). 
   - Metode `toBe` mengevaluasi identitas nilai menggunakan operator perbandingan ketat `===`.
   - Metode `toThrow` mengeksekusi fungsi di dalam blok `try...catch` internal untuk membuktikan apakah invokasi fungsi memicu pelemparan *runtime exception* atau tidak.

3. **Mekanisme Antrean `test()` (Baris 53–56):**
   Pemanggilan fungsi `test()` bersifat non-blocking terhadap eksekusi tes itu sendiri. Fungsi ini hanya mendaftarkan fungsi lambda ke dalam array `testQueue`. Pemisahan fase deklarasi dari fase eksekusi memungkinkan runner untuk menyusun ulang tes, menjalankan pengujian secara paralel, atau menerapkan filter (*pattern matching*) sebelum eksekusi dimulai.

4. **Mesin Eksekusi `runTests()` (Baris 58–92):**
   Runner mengiterasi antrean pengujian secara sekuensial dengan dukungan `async/await`. 
   - `performance.now()` digunakan untuk menangkap *high-resolution timestamp* guna mengukur durasi eksekusi per tes.
   - Blok `try...catch` menangkap setiap kegagalan asersi, mencegah program berhenti seketika (*crashing*), mencatat format teks ANSI berwarna pada konsol, dan menaikkan *counter* `failed`.
   - Di akhir eksekusi, jika `failed > 0`, proses mengeluarkan *exit code* `1` via `process.exit(1)`. Sinyal ini merupakan protokol standar sistem operasi untuk memberi tahu *pipeline* CI/CD bahwa *build* gagal.

---

### 9. Production-Ready Implementation
Pada skenario produksi nyata, sebuah modul pengujian harus mencakup arsitektur berlapis yang menguji *Domain Logic*, *Error Boundaries*, serta penanganan *State* dan *Mocking*.

Berikut adalah studi kasus implementasi **Sistem Pemrosesan Transaksi Finansial (Payment Ledger)** yang mencakup Domain Entities, State Machine, dan *TestSuite* komprehensif menggunakan TypeScript murni dengan arsitektur modular.

```typescript
// ==========================================
// 1. DOMAIN LAYER (System Under Test / SUT)
// ==========================================

export enum TransactionStatus {
  PENDING = 'PENDING',
  SETTLED = 'SETTLED',
  FAILED = 'FAILED'
}

export interface Transaction {
  id: string;
  sourceAccountId: string;
  targetAccountId: string;
  amount: number;
  status: TransactionStatus;
  createdAt: Date;
}

export interface AccountRepository {
  getBalance(accountId: string): Promise<number>;
  updateBalance(accountId: string, newBalance: number): Promise<void>;
}

export interface AuditLogger {
  log(event: string, payload: Record<string, unknown>): Promise<void>;
}

export class PaymentLedgerService {
  constructor(
    private readonly accountRepo: AccountRepository,
    private readonly auditLogger: AuditLogger
  ) {}

  public async executeTransfer(
    transactionId: string,
    sourceId: string,
    targetId: string,
    amount: number
  ): Promise<Transaction> {
    if (amount <= 0) {
      throw new Error(`Transfer amount must be strictly positive. Received: ${amount}`);
    }
    if (sourceId === targetId) {
      throw new Error('Source and destination accounts must be distinct.');
    }

    const sourceBalance = await this.accountRepo.getBalance(sourceId);
    if (sourceBalance < amount) {
      await this.auditLogger.log('TRANSFER_REJECTED_INSUFFICIENT_FUNDS', {
        transactionId,
        sourceId,
        amount,
        sourceBalance
      });
      throw new Error(`Insufficient funds: Account ${sourceId} has ${sourceBalance}, required ${amount}`);
    }

    const targetBalance = await this.accountRepo.getBalance(targetId);

    // Atomic State Updates
    await this.accountRepo.updateBalance(sourceId, sourceBalance - amount);
    await this.accountRepo.updateBalance(targetId, targetBalance + amount);

    const transactionRecord: Transaction = {
      id: transactionId,
      sourceAccountId: sourceId,
      targetAccountId: targetId,
      amount,
      status: TransactionStatus.SETTLED,
      createdAt: new Date()
    };

    await this.auditLogger.log('TRANSFER_COMPLETED', { transactionId, amount });

    return transactionRecord;
  }
}

// ==========================================
// 2. PRODUCTION TEST HARNESS (Isolation & Mocks)
// ==========================================

export class InMemoryAccountRepository implements AccountRepository {
  private accounts: Map<string, number> = new Map();

  public seedBalance(accountId: string, balance: number): void {
    this.accounts.set(accountId, balance);
  }

  public async getBalance(accountId: string): Promise<number> {
    const balance = this.accounts.get(accountId);
    if (balance === undefined) {
      throw new Error(`Account not found: ${accountId}`);
    }
    return balance;
  }

  public async updateBalance(accountId: string, newBalance: number): Promise<void> {
    this.accounts.set(accountId, newBalance);
  }
}

export class SpyAuditLogger implements AuditLogger {
  public loggedEvents: Array<{ event: string; payload: Record<string, unknown> }> = [];

  public async log(event: string, payload: Record<string, unknown>): Promise<void> {
    this.loggedEvents.push({ event, payload });
  }

  public verifyEventEmitted(eventName: string): boolean {
    return this.loggedEvents.some((entry) => entry.event === eventName);
  }
}

// ==========================================
// 3. ROBUST SPECIFICATION SUITE
// ==========================================

import { strict as assert } from 'assert';

export async function runProductionTestSuite(): Promise<void> {
  console.log('Starting PaymentLedgerService Production Test Suite...');

  // Setup Test Context (State Isolation Factory)
  const createTestContext = () => {
    const repo = new InMemoryAccountRepository();
    const logger = new SpyAuditLogger();
    const service = new PaymentLedgerService(repo, logger);
    return { repo, logger, service };
  };

  // Test Case 1: Normal Path (Happy Path)
  {
    const { repo, logger, service } = createTestContext();
    repo.seedBalance('ACC_SRC', 1000);
    repo.seedBalance('ACC_DST', 500);

    const tx = await service.executeTransfer('TX_001', 'ACC_SRC', 'ACC_DST', 300);

    assert.equal(tx.status, TransactionStatus.SETTLED);
    assert.equal(await repo.getBalance('ACC_SRC'), 700);
    assert.equal(await repo.getBalance('ACC_DST'), 800);
    assert.equal(logger.verifyEventEmitted('TRANSFER_COMPLETED'), true);
    console.log('✔ Case 1: Happy path transfer executed deterministically');
  }

  // Test Case 2: Boundary Value Check (Zero & Negative Amounts)
  {
    const { service } = createTestContext();

    await assert.rejects(
      async () => service.executeTransfer('TX_002', 'ACC_A', 'ACC_B', 0),
      /Transfer amount must be strictly positive/,
      'Should reject transfer with zero value'
    );

    await assert.rejects(
      async () => service.executeTransfer('TX_003', 'ACC_A', 'ACC_B', -50),
      /Transfer amount must be strictly positive/,
      'Should reject transfer with negative value'
    );
    console.log('✔ Case 2: Invariant enforced on non-positive amounts');
  }

  // Test Case 3: Error Isolation & Side-Effect Prevention (Insufficient Funds)
  {
    const { repo, logger, service } = createTestContext();
    repo.seedBalance('ACC_SRC_EMPTY', 50);
    repo.seedBalance('ACC_DST_STATIC', 100);

    await assert.rejects(
      async () => service.executeTransfer('TX_004', 'ACC_SRC_EMPTY', 'ACC_DST_STATIC', 100),
      /Insufficient funds/,
      'Should abort transaction upon overdraft attempt'
    );

    // Verifikasi State Invariance (Tidak ada saldo yang termutasi parsial)
    assert.equal(await repo.getBalance('ACC_SRC_EMPTY'), 50);
    assert.equal(await repo.getBalance('ACC_DST_STATIC'), 100);
    assert.equal(logger.verifyEventEmitted('TRANSFER_REJECTED_INSUFFICIENT_FUNDS'), true);
    console.log('✔ Case 3: State invariance maintained upon transactional failure');
  }

  console.log('All Production Test Scenarios Validated Successfully.\n');
}

if (require.main === module) {
  runProductionTestSuite().catch((err) => {
    console.error('Test Suite Failed With Unhandled Exception:', err);
    process.exit(1);
  });
}
```

---

### 10. Step-by-Step Implementation Walkthrough
1. **Pemisahan Abstraksi dan Implementasi Melalui Inversi Dependensi:**
   Class `PaymentLedgerService` tidak melakukan instansiasi langsung koneksi database atau logger eksternal. Semua dependensi disuntikkan (*injected*) melalui constructor (`AccountRepository`, `AuditLogger`). Hal ini memungkinkan substitusi repositori asli dengan *In-Memory Fake* atau *Spy* saat pengujian tanpa memodifikasi kode produksi.

2. **Penggunaan Test Doubles (Fakes vs. Spies):**
   - `InMemoryAccountRepository` adalah sebuah **Fake**: Menyediakan implementasi stateful fungsional penuh menggunakan `Map<string, number>` dalam memori, menjadikannya cepat, bebas IO jaringan, dan deterministik.
   - `SpyAuditLogger` adalah sebuah **Spy**: Merekam pemanggilan fungsi dan parameter payload yang diterima, memungkinkan kita memverifikasi perilaku internal (*indirect outputs*) tanpa memerlukan mocking library eksternal yang rumit.

3. **Pemberian Test Context Terisolasi (Factory Pattern):**
   Fungsi `createTestContext()` bertindak sebagai factory yang mengembalikan instance bersih untuk setiap skenario uji. Hal ini menjamin **Isolasi Mutlak**: tidak ada mutasi state dari *Test Case 1* yang dapat bocor atau mempengaruhi *Test Case 2* atau *Test Case 3*.

4. **Verifikasi Asersi Menggunakan Node.js Native `assert`:**
   Implementasi menggunakan `node:assert/strict` yang menggunakan algoritma deep equality mutakhir. Pemanggilan `assert.rejects()` menangkap Promise yang gagal secara tepat dan memvalidasi tipe error menggunakan ekspresi reguler (*regex*).

---

### 11. Real-World Scenarios & Failure Modes

#### Skenario 1: Bencana "State Leaks Between Tests" pada CI Pipeline
- **Insiden:** Pada sebuah sistem pemrosesan pesanan, sebuah tes unit memodifikasi property global `process.env.NODE_ENV = 'production'`. Pengujian tersebut lolos secara independen saat dijalankan secara lokal via `--testPathPattern=order`. Namun, saat dijalankan di CI bersama ratusan suite lainnya secara acak, tes otentikasi pembayaran gagal secara berkala (*flaky failure*).
- **Akar Masalah:** Berbagi mutable global state tanpa proses teardown yang bersih.
- **Solusi Rekayasa:** Penggunaan hook `afterEach` atau struktur sandbox ketat untuk memulihkan state lingkungan ke konfigurasi awal:
  ```typescript
  const ORIGINAL_ENV = { ...process.env };
  afterEach(() => {
    process.env = { ...ORIGINAL_ENV };
  });
  ```

#### Skenario 2: Phantom Assertions pada Asynchronous Code
- **Insiden:** Pengembang menulis tes untuk memastikan bahwa fungsi asynchronous melempar exception:
  ```typescript
  // ANTI-PATTERN
  test('harus gagal saat file tidak ditemukan', () => {
    readFileAsync('invalid-path').catch((err) => {
      expect(err.code).toBe('ENOENT');
    });
  });
  ```
- **Akar Masalah:** Karena `readFileAsync` mengembalikan sebuah `Promise` dan tidak di-`await` di dalam tes, test runner menandai tes ini sebagai `PASS` seketika sebelum Promise selesai dievaluasi atau di-reject. Ketika fungsi diubah hingga tidak lagi melempar error, tes tersebut **tetap berstatus PASS**.
- **Solusi Rekayasa:** Selalu gunakan `await` eksplisit dan kombinasikan dengan matcher error native runner:
  ```typescript
  await expect(readFileAsync('invalid-path')).rejects.toThrow('ENOENT');
  ```

---

### 12. Edge Cases & Boundary Conditions
Saat merancang arsitektur pengujian untuk sistem berkualitas tinggi, evaluasi edge case matematis dan sistemik berikut:

1. **Numeric Boundary Extremes:**
   - Evaluasi nilai $0$, $-0$, integer negatif, nilai maksimum/minimum integer (`Number.MAX_SAFE_INTEGER`, `Number.MIN_SAFE_INTEGER`), desimal presisi pecahan IEEE-754 ($0.1 + 0.2 \neq 0.3$), `NaN`, serta `Infinity`.
2. **Karakter String Eksotik & Payload Berukuran Ekstrem:**
   - String kosong (`""`), string yang hanya berisi spasi/whitespace (`"   "`), Unicode karakter non-BMP (misal: Emoji $\text{U+1F600}$ yang memakan 4 byte), Null byte (`\0`), serta string dengan ukuran payload sangat besar (10MB+) untuk menguji batasan *buffer memory*.
3. **Temporal Invariance (Waktu dan Zona Waktu):**
   - Menghindari ketergantungan pada `new Date()` langsung di dalam kode. Selalu injeksikan abstraksi waktu (*Clock Provider*). Pastikan sistem bekerja dengan benar saat melintasi batas pergantian tahun kabisat (*Leap Year*), detik kabisat (*Leap Second*), dan pergeseran zona waktu (*Daylight Saving Time*).
4. **Kondisi Balapan Konkurensi (Race Conditions):**
   - Pengujian simultan di mana dua thread/event-loop loop worker mencoba mendebit akun yang sama secara bersamaan untuk mendeteksi *double-spend anomaly*.

---

### 13. Trade-Off Analysis

| Pendekatan / Tingkat Pengujian | Cakupan Keyakinan (*Confidence*) | Biaya Eksekusi (*Execution Cost*) | Pemeliharaan (*Maintenance Overhead*) | Lokalisasi Akar Masalah (*Root-Cause Pinpointing*) | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Unit Testing (Isolated)** | Rendah–Sedang (Hanya unit internal) | Sangat Murah (~1-10 ms per test) | Rendah (Kecuali jika terlalu banyak mock internal) | Sangat Tinggi (Langsung menunjuk fungsi & baris) | Logika algoritma murni, entity domain, utilitas parsial. |
| **Contract / Integration Testing** | Tinggi (Untuk batas subsistem) | Menengah (~100-500 ms per test) | Menengah (Memerlukan docker testcontainers/in-memory DB) | Menengah (Mengidentifikasi antarmuka yang rusak) | Komunikasi API, query repository database, integrasi cache. |
| **End-to-End (E2E) Browser Testing** | Sangat Tinggi (Sistem nyata menyeluruh) | Sangat Mahal (~5-60 detik per test) | Sangat Tinggi (*Brittle* terhadap perubahan UI) | Sangat Rendah (Sulit melacak kegagalan apakah dari FE, BE, Network, atau DB) | Validasi critical path (misal: alur registrasi pengguna, checkout transaksi). |

---

### 14. Modern Best Practices
1. **Struktur Pengujian AAA (Arrange-Act-Assert):**
   Bagi setiap blok pengujian menjadi tiga segmen yang terlihat jelas dengan batas spasi vertikal:
   - **Arrange:** Inisialisasi dependensi, siapkan mock, seed data.
   - **Act:** Eksekusi metode tunggal yang sedang diuji (*System Under Test / SUT*).
   - **Assert:** Evaluasi mutasi state atau output nilai kembalian.
2. **Prinsip DAMP di atas DRY untuk Pengujian:**
   Di dalam kode produksi, *Don't Repeat Yourself* (DRY) adalah aturan utama. Namun di dalam kode pengujian, utamakan **Descriptive And Meaningful Phrases (DAMP)**. Tes harus mudah dibaca secara linier dari atas ke bawah tanpa harus menelusuri abstraksi helper test yang terlalu dalam dan berbelit.
3. **Pengujian Berbasis Status, Bukan Pengujian Interaksi Internal:**
   Uji nilai keluaran (*State Verification*) alih-alih menguji metode privat apa saja yang dipanggil di balik layar (*Interaction Verification*). Terlalu banyak verifikasi seperti `expect(service.privateMethod).toHaveBeenCalledTimes(1)` membuat pengujian menjadi rapuh (*brittle*) terhadap proses refactoring.

---

### 15. Antipatterns to Avoid

#### 1. The Liar Test (Asersi Kosong / False Positive)
```typescript
// BURUK: Lolos meskipun implementasi melempar error tak terduga atau tidak melakukan apapun
test('validasi data user', async () => {
  try {
    await processUserData({ id: 'invalid' });
  } catch (err) {
    // Tidak ada asersi di sini!
  }
});

// BENAR: Pastikan error secara eksplisit ditangkap dan divalidasi kodenya
test('validasi data user', async () => {
  await expect(processUserData({ id: 'invalid' }))
    .rejects
    .toThrow(ValidationError);
});
```

#### 2. The Shared State Polluter
```typescript
// BURUK: State mutable berada di scope modul, test bergantung pada urutan eksekusi
let sharedUserId = '';

test('membuat user', async () => {
  const user = await createUser();
  sharedUserId = user.id; // Mencemari scope luar
});

test('menghapus user', async () => {
  // Akan gagal jika dijalankan secara independen tanpa tes di atas
  await deleteUser(sharedUserId);
});

// BENAR: Setiap tes mandiri secara mutlak (Hermetic Test)
test('menghapus user', async () => {
  const user = await createUser();
  await deleteUser(user.id);
  const fetched = await findUser(user.id);
  expect(fetched).toBeNull();
});
```

---

### 16. Verification & Testing
Untuk memverifikasi modul `PaymentLedgerService` yang telah kita bangun, simpan kode implementasi pada seksi 9 ke dalam berkas `ledger.ts`, lalu jalankan serangkaian verifikasi menggunakan baris perintah berikut:

```bash
# 1. Jalankan kompilasi TypeScript untuk validasi static types
npx tsc --noEmit ledger.ts

# 2. Eksekusi pengujian secara langsung menggunakan runtime Node.js (v18+)
node -r ts-node/register ledger.ts
```

Output terminal yang diharapkan:
```text
Starting PaymentLedgerService Production Test Suite...
✔ Case 1: Happy path transfer executed deterministically
✔ Case 2: Invariant enforced on non-positive amounts
✔ Case 3: State invariance maintained upon transactional failure
All Production Test Scenarios Validated Successfully.
```

Untuk memverifikasi ketahanan pengujian, lakukan teknik **Manual Mutation Verification**:
- Buka `ledger.ts`, ubah baris validasi saldo:
  ```typescript
  // Ubah dari:
  if (sourceBalance < amount)
  // Menjadi:
  if (sourceBalance <= amount)
  ```
- Jalankan kembali runner pengujian. Test harness **wajib** gagal dan menghasilkan pesan kegagalan (*assert error*). Jika tes tetap berstatus hijau (lolos), pengujian Anda memiliki celah (*test blind spot*).

---

### 17. Performance & Scalability Considerations
1. **Parallel Execution Architecture:**
   Jalankan tes dengan memisahkan *file-level tasks* ke dalam multi-process pool (misalnya memanfaatkan jumlah core CPU: `os.cpus().length - 1`). Hindari eksekusi paralel pada level test case individual di dalam file yang sama jika mereka mengakses sumber daya bersama (*shared resource*).
2. **I/O Overhead Mitigation:**
   - Gunakan memori virtual (`tmpfs` atau SQLite in-memory `:memory:`) daripada menulis data sementara ke piringan *hard drive* atau database jaringan fisik pada level pengujian integrasi subsistem.
3. **Database Reset Strategy:**
   Daripada menjalankan *Database Migration Up/Down* penuh pada setiap pengujian (yang membutuhkan ratusan milidetik), gunakan strategi **Database Transaction Rollback**:
   Buka transaksi database pada `beforeEach`, jalankan tes, lalu panggil `ROLLBACK` pada `afterEach`. Dengan demikian, integritas disk tidak pernah termutasi permanen, menghemat hingga 90% waktu eksekusi.

---

### 18. Security Considerations
1. **Pembersihan Log pada Test Artifacts:**
   Pengujian yang gagal sering kali mencetak *request/response payload* ke dalam output konsol CI. Pastikan kredensial, token autentikasi, API secret, dan informasi sensitif pengguna (PII) disanitasi (*redacted*) dari output log pengujian sebelum diunggah ke *CI storage artifacts*.
2. **Vulnerabilitas pada Test Dependencies:**
   Dependensi pengujian (seperti faker library, mock frameworks, test runners) dijalankan dengan hak akses penuh (*arbitrary code execution*) pada mesin pengembang dan server CI. Lakukan audit keamanan rutin menggunakan `npm audit` atau Snyk untuk memastikan test-tooling tidak menjadi pintu masuk eksploitasi rantai pasok (*software supply chain attack*).
3. **Data Masking pada Mock Data:**
   Jangan pernah menggunakan data dump produksi mentah (*raw production database dump*) sebagai fixture lokal. Gunakan generator data sintetis untuk mematuhi regulasi privasi data (GDPR/UU PDP).

---

### 19. Tooling, Observability & Debugging
- **Analisis Debugging Interaktif:**
  Untuk mendeteksi kegagalan tes secara mendalam, gunakan inspektor protokol Node.js:
  ```bash
  node --inspect-brk ./node_modules/.bin/jest --runInBand
  ```
  Buka `chrome://inspect` pada browser Chromium untuk memasang breakpoint visual pada logika SUT Anda.
- **Coverage Analysis Tools:**
  Gunakan **c8** atau **Istanbul** untuk memetakan jalur eksekusi kode:
  ```bash
  npx c8 --reporter=html --reporter=text node -r ts-node/register ledger.ts
  ```
- **Mutation Testing Frameworks:**
  Jangan hanya mengandalkan code coverage. Gunakan **Stryker Mutator** (untuk TypeScript/JavaScript) atau **Mutmut** (untuk Python). Framework mutasi akan secara sengaja mengubah kode produksi Anda (membalik operator logika boolean, menghapus baris kode) untuk membuktikan apakah suite pengujian Anda mampu menangkap perubahan liar tersebut.

---

### 20. Summary & Key Takeaways
- **Testing Pyramid** adalah pedoman distribusi pengujian: investasikan porsi terbesar pada pengujian berkecepatan tinggi, deterministik, dan terisolasi (*Unit Tests*), lapisi dengan pengujian batas integrasi subsistem (*Integration Tests*), dan lindungi skenario bisnis paling krusial dengan pengujian ujung-ke-ujung (*E2E Tests*) dalam jumlah terukur.
- **Verifikasi** memastikan perangkat lunak dibangun sesuai spesifikasi teknis (*"Are we building the product right?"*), sedangkan **Validasi** memastikan bahwa perangkat lunak tersebut menyelesaikan kebutuhan riil pengguna (*"Are we building the right product?"*).
- **Hermetic Tests** adalah prinsip absolut: setiap unit tes harus berdiri sendiri secara mandiri (*self-contained*), tidak boleh bergantung pada status dari pengujian sebelumnya, dan membersihkan semua mutasi efek samping (*side-effects*) setelah selesai dieksekusi.
- **Tingkat Coverage Tinggi $\neq$ Kualitas Pengujian Tinggi**: Metrik cakupan baris hanya membuktikan bahwa sebuah baris instruksi sempat dieksekusi oleh runtime engine, bukan membuktikan bahwa asersi bisnis dievaluasi dengan benar saat kondisi ekstrem terjadi. Gunakan *Mutation Testing* untuk memvalidasi ketajaman pengujian Anda secara empiris.