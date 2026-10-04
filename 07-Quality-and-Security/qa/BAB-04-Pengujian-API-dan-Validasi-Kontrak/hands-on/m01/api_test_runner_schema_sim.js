/**
 * Hands-on M01: API Test Runner, HTTP Status Code & Idempotency Simulator
 * 
 * Fitur:
 * 1. Mock HTTP Server Mandiri (Node.js native http module - Zero Dependencies).
 * 2. Client Test Runner dengan Otomasi Pengujian:
 *    - Status Code Verification (200, 201, 400, 401, 422).
 *    - Header Validation (Content-Type, Bearer Token).
 *    - Idempotency Key Handling (Mencegah duplikasi pembayaran pada retry).
 *    - Latency SLA Assertion (< 200ms).
 */

const http = require("http");

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. MOCK API SERVER (Target SUT)
// ==========================================
const PORT = 8991;
const idempotencyStore = new Map();
let server;

function startMockServer() {
  return new Promise((resolve) => {
    server = http.createServer((req, res) => {
      let body = "";
      req.on("data", chunk => body += chunk);
      req.on("end", () => {
        const url = req.url;
        const method = req.method;
        const auth = req.headers["authorization"];
        const idempotencyKey = req.headers["idempotency-key"];

        // Response helper
        const sendJson = (status, data) => {
          res.writeHead(status, { "Content-Type": "application/json" });
          res.end(JSON.stringify(data));
        };

        // Route: GET /health
        if (url === "/health" && method === "GET") {
          return sendJson(200, { status: "UP", timestamp: Date.now() });
        }

        // Route: POST /api/v1/auth/login
        if (url === "/api/v1/auth/login" && method === "POST") {
          try {
            const parsed = JSON.parse(body || "{}");
            if (!parsed.email || !parsed.password) {
              return sendJson(400, { error: "BAD_REQUEST", message: "Email dan password wajib diisi" });
            }
            if (parsed.email === "qa@testing.com" && parsed.password === "Pass1234!") {
              return sendJson(200, { token: "tok_secret_jwt_qa_valid_2026", expiresIn: 3600 });
            }
            return sendJson(401, { error: "UNAUTHORIZED", message: "Kredensial email atau password salah" });
          } catch {
            return sendJson(400, { error: "INVALID_JSON" });
          }
        }

        // Route: POST /api/v1/payments (Protected & Idempotent)
        if (url === "/api/v1/payments" && method === "POST") {
          // 1. Auth check
          if (auth !== "Bearer tok_secret_jwt_qa_valid_2026") {
            return sendJson(401, { error: "UNAUTHORIZED", message: "Bearer token tidak valid atau tidak ada" });
          }

          // 2. Idempotency check
          if (idempotencyKey && idempotencyStore.has(idempotencyKey)) {
            const cachedResponse = idempotencyStore.get(idempotencyKey);
            return sendJson(200, { ...cachedResponse, isReplayed: true });
          }

          // 3. Payload validation
          try {
            const payload = JSON.parse(body || "{}");
            if (typeof payload.amount !== "number" || payload.amount <= 0) {
              return sendJson(422, { error: "UNPROCESSABLE_ENTITY", message: "Nominal pembayaran harus lebih dari 0" });
            }

            // Sukses
            const txResult = {
              txId: "TX-" + Math.floor(100000 + Math.random() * 900000),
              amount: payload.amount,
              status: "COMPLETED",
              isReplayed: false
            };

            if (idempotencyKey) {
              idempotencyStore.set(idempotencyKey, txResult);
            }

            return sendJson(201, txResult);
          } catch {
            return sendJson(400, { error: "INVALID_JSON" });
          }
        }

        // Route: 404 fallback
        sendJson(404, { error: "NOT_FOUND", message: `Endpoint ${method} ${url} tidak ditemukan` });
      });
    });

    server.listen(PORT, () => {
      resolve();
    });
  });
}

// ==========================================
// 2. HTTP CLIENT HELPER (Node.js Native)
// ==========================================
function sendRequest(method, path, headers = {}, body = null) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const req = http.request({
      hostname: "localhost",
      port: PORT,
      path,
      method,
      headers
    }, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => {
        const duration = Date.now() - start;
        let parsed = null;
        try { parsed = JSON.parse(data); } catch { parsed = data; }
        resolve({
          status: res.statusCode,
          headers: res.headers,
          data: parsed,
          duration
        });
      });
    });

    req.on("error", reject);
    if (body) req.write(typeof body === "string" ? body : JSON.stringify(body));
    req.end();
  });
}

// ==========================================
// 3. API TEST SUITE RUNNER
// ==========================================
async function runApiTestSuite() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║          AUTOMATED API TEST RUNNER & STATUS LAB               ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  let passed = 0;
  let total = 0;

  async function assertCase(name, fn) {
    total++;
    try {
      await fn();
      console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} ${name}`);
      passed++;
    } catch (err) {
      console.log(`  ${ANSI.red}✗ FAIL${ANSI.reset} ${name} ➔ ${err.message}`);
    }
  }

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== SUITE 1: STATUS CODE & AUTHENTICATION ===${ANSI.reset}`);
  
  // Test 1: Healthcheck 200 OK
  await assertCase("GET /health mengembalikan status HTTP 200 OK", async () => {
    const res = await sendRequest("GET", "/health");
    if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
    if (res.data.status !== "UP") throw new Error("Body status bukan UP");
  });

  // Test 2: Login Success 200 OK
  let authToken = "";
  await assertCase("POST /api/v1/auth/login dengan kredensial valid menghasilkan JWT", async () => {
    const res = await sendRequest("POST", "/api/v1/auth/login", { "Content-Type": "application/json" }, {
      email: "qa@testing.com",
      password: "Pass1234!"
    });
    if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
    if (!res.data.token) throw new Error("Token tidak ditemukan dalam respon");
    authToken = res.data.token;
  });

  // Test 3: Login Invalid Password 401 Unauthorized
  await assertCase("POST /api/v1/auth/login password salah menghasilkan 401 Unauthorized", async () => {
    const res = await sendRequest("POST", "/api/v1/auth/login", { "Content-Type": "application/json" }, {
      email: "qa@testing.com",
      password: "WrongPassword"
    });
    if (res.status !== 401) throw new Error(`Expected 401, got ${res.status}`);
  });

  // Test 4: Missing Fields 400 Bad Request
  await assertCase("POST /api/v1/auth/login payload kosong menghasilkan 400 Bad Request", async () => {
    const res = await sendRequest("POST", "/api/v1/auth/login", { "Content-Type": "application/json" }, {});
    if (res.status !== 400) throw new Error(`Expected 400, got ${res.status}`);
  });

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== SUITE 2: BUSINESS VALIDATION & IDEMPOTENCY ===${ANSI.reset}`);

  // Test 5: Payment tanpa Auth Token 401 Unauthorized
  await assertCase("POST /api/v1/payments tanpa Bearer token ditolak 401", async () => {
    const res = await sendRequest("POST", "/api/v1/payments", {}, { amount: 50000 });
    if (res.status !== 401) throw new Error(`Expected 401, got ${res.status}`);
  });

  // Test 6: Payment nominal negatif 422 Unprocessable Entity
  await assertCase("POST /api/v1/payments nominal negatif ditolak 422 Unprocessable", async () => {
    const res = await sendRequest("POST", "/api/v1/payments", {
      "Authorization": `Bearer ${authToken}`,
      "Content-Type": "application/json"
    }, { amount: -10000 });
    if (res.status !== 422) throw new Error(`Expected 422, got ${res.status}`);
  });

  // Test 7: Idempotent Payment Check (Double Submit Mitigation)
  await assertCase("Idempotency-Key mencegah transaksi ganda saat koneksi retry", async () => {
    const idempotencyId = "idemp_order_uuid_" + Date.now();
    const headers = {
      "Authorization": `Bearer ${authToken}`,
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyId
    };

    // Request 1: Initial creation
    const req1 = await sendRequest("POST", "/api/v1/payments", headers, { amount: 75000 });
    if (req1.status !== 201) throw new Error(`Request 1 expected 201, got ${req1.status}`);
    const firstTxId = req1.data.txId;

    // Request 2: Retry with SAME idempotency key
    const req2 = await sendRequest("POST", "/api/v1/payments", headers, { amount: 75000 });
    if (req2.status !== 200) throw new Error(`Request 2 expected 200 (Replayed), got ${req2.status}`);
    if (req2.data.txId !== firstTxId) throw new Error("Duplikasi pembayaran terjadi! TxID berbeda!");
    if (!req2.data.isReplayed) throw new Error("Flag isReplayed tidak terdeteksi");
  });

  // Test 8: Response Time Latency SLA Check (< 200ms)
  await assertCase("Response time endpoint API memenuhi SLA latency (< 200ms)", async () => {
    const res = await sendRequest("GET", "/health");
    if (res.duration > 200) throw new Error(`Latency SLA breached: ${res.duration}ms > 200ms`);
  });

  console.log(`\n${ANSI.bold}--------------------------------------------------${ANSI.reset}`);
  console.log(`Test Execution Summary: ${ANSI.green}${passed}/${total} Tests Passed${ANSI.reset}`);
  console.log(`\n${ANSI.green}✓ API Test Runner Lab executed successfully!${ANSI.reset}\n`);
}

// ==========================================
// 4. MAIN ENTRY POINT
// ==========================================
async function main() {
  await startMockServer();
  try {
    await runApiTestSuite();
  } finally {
    server.close();
  }
}

main().catch(console.error);
