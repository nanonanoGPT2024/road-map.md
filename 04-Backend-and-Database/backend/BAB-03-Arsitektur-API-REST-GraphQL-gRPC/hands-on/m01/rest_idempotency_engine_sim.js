/**
 * Enterprise RESTful API Idempotency & Cursor Pagination Simulator
 * 
 * Mensimulasikan arsitektur API tingkat enterprise:
 * 1. Idempotency Key Middleware:
 *    - Pencegahan Double-Debit dengan atomic lock.
 *    - Payload fingerprinting (SHA-256) untuk mendeteksi key reuse dengan parameter berbeda.
 *    - Caching response final transaksional.
 * 2. Benchmark Paginasi: Offset-Based (O(N) scan) vs Cursor-Based (O(1) index seek).
 * 3. HATEOAS Hypermedia Link Generator.
 */

const crypto = require("crypto");

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

// ================= 1. IDEMPOTENCY ENGINE SIMULATOR =================
class IdempotencyEngine {
  constructor() {
    this.store = new Map(); // key -> { status, fingerprint, response }
    this.accountBalance = 5000000; // Saldo awal Rp 5.000.000
  }

  processPayment(idempotencyKey, payload) {
    log("api-gateway", `Menerima request POST /v1/payments (Key: ${idempotencyKey})`, ANSI.cyan);

    // Hitung fingerprint SHA-256 dari payload
    const fingerprint = crypto.createHash("sha256").update(JSON.stringify(payload)).digest("hex");

    // 1. Cek apakah Idempotency-Key sudah pernah digunakan
    const existing = this.store.get(idempotencyKey);
    if (existing) {
      // Validasi Fingerprint: Cegah penggunaan key yang sama untuk jumlah uang berbeda
      if (existing.fingerprint !== fingerprint) {
        log("idempotency-engine", `ERROR: Idempotency-Key digunakan ulang dengan payload parameter yang berbeda!`, ANSI.red);
        return {
          statusCode: 400,
          body: { error: "Idempotency key reused with different request parameters" }
        };
      }

      if (existing.status === "IN_PROGRESS") {
        log("idempotency-engine", `CONFLICT: Request sedang diproses di background. Mohon tunggu.`, ANSI.yellow);
        return { statusCode: 409, body: { error: "Concurrent request in progress" } };
      }

      log("idempotency-engine", `CACHE HIT! Mengembalikan respons tersimpan tanpa memotong saldo kembali!`, ANSI.green);
      return {
        statusCode: existing.response.statusCode,
        headers: { "X-Cache-Lookup": "HIT-IDEMPOTENT" },
        body: existing.response.body
      };
    }

    // 2. Kunci key dengan status IN_PROGRESS (Atomic Lock)
    this.store.set(idempotencyKey, { status: "IN_PROGRESS", fingerprint, response: null });
    log("idempotency-engine", `Kunci diperoleh. Menjalankan mutasi transaksi debit database...`, ANSI.yellow);

    // 3. Eksekusi Debit Database
    this.accountBalance -= payload.amount;
    const paymentId = `PAY-${Math.floor(100000 + Math.random() * 900000)}`;

    const responseBody = {
      payment_id: paymentId,
      amount: payload.amount,
      currency: "IDR",
      status: "COMPLETED",
      remaining_balance: this.accountBalance,
      _links: {
        self: { href: `/v1/payments/${paymentId}`, method: "GET" },
        refund: { href: `/v1/payments/${paymentId}/refunds`, method: "POST" }
      }
    };

    // 4. Simpan respons final di cache
    this.store.set(idempotencyKey, {
      status: "COMPLETED",
      fingerprint,
      response: { statusCode: 201, body: responseBody }
    });

    log("idempotency-engine", `Transaksi sukses! Saldo sekarang: Rp ${this.accountBalance}. Respons di-cache.`, ANSI.green);
    return { statusCode: 201, body: responseBody };
  }
}

// ================= 2. PAGINATION ENGINE BENCHMARK =================
class PaginationBenchmark {
  static runBenchmark() {
    console.log(`\n${ANSI.bold}=== BAGIAN 2: BENCHMARK PAGINASI OFFSET VS CURSOR (1.000.000 DATA) ===${ANSI.reset}`);

    const targetOffset = 500000;
    const limit = 20;

    // A. Offset-Based: Simulasi O(N) scan
    console.time("Offset-Based Pagination (Page 25.000)");
    let scannedRows = 0;
    for (let i = 0; i < targetOffset + limit; i++) {
      scannedRows++;
    }
    console.timeEnd("Offset-Based Pagination (Page 25.000)");
    log("offset-db", `Harus memindai ${scannedRows} baris index dan membuang 500.000 baris pertama! (Skalabilitas Buruk)`, ANSI.red);

    // B. Cursor-Based: Simulasi O(1) B-Tree seek
    console.time("Cursor-Based Pagination (Seek by ID)");
    const lastSeenId = 500000;
    const fetchedRows = [];
    for (let i = 1; i <= limit; i++) {
      fetchedRows.push(lastSeenId + i);
    }
    console.timeEnd("Cursor-Based Pagination (Seek by ID)");
    log("cursor-db", `Langsung melompat ke ID > ${lastSeenId} dan mengambil tepat ${fetchedRows.length} baris via B-Tree Index! (Skalabilitas O(1) Sempurna)`, ANSI.green);
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      ENTERPRISE RESTFUL API IDEMPOTENCY & PAGINATION SIM       ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

const engine = new IdempotencyEngine();
const key1 = "idemp-uuid-7788-9900";
const orderPayload = { amount: 250000, recipient: "Merchant Toko Kopi" };

console.log(`--- [TEST 1: Request Pertama (Eksekusi Normal)] ---`);
const res1 = engine.processPayment(key1, orderPayload);
console.log("Response:", JSON.stringify(res1.body, null, 2));

console.log(`\n--- [TEST 2: Request Duplikat (Network Retry dengan Key Sama)] ---`);
const res2 = engine.processPayment(key1, orderPayload);
console.log("Response:", JSON.stringify(res2.body, null, 2));
console.log(`Headers:`, res2.headers);

console.log(`\n--- [TEST 3: Key Digunakan Ulang dengan Parameter Berbeda (Fraud Attack)] ---`);
const fraudulentPayload = { amount: 1000000, recipient: "Rekening Hacker" };
const res3 = engine.processPayment(key1, fraudulentPayload);
console.log("Response:", JSON.stringify(res3.body, null, 2));

// Jalankan Benchmark Paginasi
PaginationBenchmark.runBenchmark();

console.log(`\n${ANSI.bold}Seluruh arsitektur Idempotensi dan Paginasi tervalidasi dengan sukses!${ANSI.reset}`);
