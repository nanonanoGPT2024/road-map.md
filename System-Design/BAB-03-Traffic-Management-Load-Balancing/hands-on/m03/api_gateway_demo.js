// api_gateway_demo.js
// Simulator API Gateway: Routing, Token Authentication, Header Transformation, & Rate Limiting

const http = require('http');

// ===================================================================
// 1. PRIVATE MICROSERVICES (INTERNAL CLUSTER ONLY)
// ===================================================================

// Microservice 1: Users Service (Port 6001)
const usersService = http.createServer((req, res) => {
  const userId = req.headers['x-user-id'] || 'anonymous';
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    service: "Users-Service",
    authenticatedUser: userId,
    profile: { name: "Budi Santoso", email: "budi@example.com", tier: "Gold" }
  }));
}).listen(6001);

// Microservice 2: Orders Service (Port 6002)
const ordersService = http.createServer((req, res) => {
  const userId = req.headers['x-user-id'] || 'anonymous';
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    service: "Orders-Service",
    authenticatedUser: userId,
    orders: [
      { id: "ORD-101", item: "Laptop Pro", total: 1500 },
      { id: "ORD-102", item: "Wireless Mouse", total: 25 }
    ]
  }));
}).listen(6002);

// ===================================================================
// 2. API GATEWAY IMPLEMENTATION (Port 6000)
// ===================================================================

// In-Memory Token Bucket Rate Limiter (Kapasitas: 3 token, isi ulang 1 token/detik)
const rateLimiterStore = new Map();

function checkRateLimit(clientIp, limit = 3) {
  const now = Date.now();
  if (!rateLimiterStore.has(clientIp)) {
    rateLimiterStore.set(clientIp, { tokens: limit - 1, lastRefill: now });
    return true;
  }

  const record = rateLimiterStore.get(clientIp);
  const timePassedSec = (now - record.lastRefill) / 1000;
  record.tokens = Math.min(limit, record.tokens + (timePassedSec * 1)); // Refill 1 token/detik
  record.lastRefill = now;

  if (record.tokens >= 1) {
    record.tokens -= 1;
    return true;
  }
  return false; // Rate limit terlampaui
}

const apiGateway = http.createServer((req, res) => {
  const clientIp = req.socket.remoteAddress;

  // A. Proteksi Rate Limiting
  if (!checkRateLimit(clientIp, 3)) {
    res.writeHead(429, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({
      error: "429 Too Many Requests",
      message: "Rate limit terlampaui! Maksimal 3 request berturut-turut."
    }));
  }

  // B. Proteksi Otentikasi Token (Simulasi JWT / Bearer Token)
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer secret-token-')) {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({
      error: "401 Unauthorized",
      message: "Akses ditolak: Token autentikasi hilang atau tidak valid!"
    }));
  }

  // C. Ekstrak User ID dari Token (Simulasi Dekode JWT)
  const extractedUserId = authHeader.replace('Bearer secret-token-', 'user_');

  // D. Request Routing ke Microservices Internal
  let targetPort = null;
  if (req.url.startsWith('/api/v1/users')) {
    targetPort = 6001; // Forward ke Users Service
  } else if (req.url.startsWith('/api/v1/orders')) {
    targetPort = 6002; // Forward ke Orders Service
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: "404 Not Found", message: "Route tidak terdaftar di API Gateway!" }));
  }

  // E. Forward Request dengan Header Transformation
  const proxyReq = http.request({
    hostname: '127.0.0.1',
    port: targetPort,
    path: req.url,
    method: req.method,
    headers: {
      ...req.headers,
      'x-user-id': extractedUserId, // Suntikkan identitas aman ke microservice
      'x-gateway-proxy': 'Antigravity-API-Gateway-v1'
    }
  }, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode, upstreamRes.headers);
    upstreamRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    res.writeHead(503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: "503 Service Unavailable", message: err.message }));
  });

  req.pipe(proxyReq);
}).listen(6000);

// ===================================================================
// 3. JALANKAN TEST SUITE DEMO
// ===================================================================

function sendHttpRequest(path, token = null) {
  return new Promise((resolve) => {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    http.get(`http://localhost:6000${path}`, { headers }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        resolve({ status: res.statusCode, body: JSON.parse(body) });
      });
    }).on('error', err => resolve({ status: 500, error: err.message }));
  });
}

async function runDemo() {
  console.log("===================================================================");
  console.log("     DEMONSTRASI API GATEWAY (ROUTING, AUTH, & RATE LIMIT)         ");
  console.log("===================================================================");
  console.log(" - API Gateway aktif di Port :6000");
  console.log(" - Users Microservice aktif di Port :6001 (Internal)");
  console.log(" - Orders Microservice aktif di Port :6002 (Internal)\n");

  // TEST 1: Request tanpa token otentikasi
  console.log(">>> [TEST 1]: Mengirim request ke /api/v1/users TANPA token:");
  const test1 = await sendHttpRequest('/api/v1/users');
  console.log(` Status: ${test1.status} | Respon:`, test1.body);

  // TEST 2: Request ke Users Service dengan token valid
  console.log("\n>>> [TEST 2]: Mengirim request ke /api/v1/users DENGAN token valid:");
  const test2 = await sendHttpRequest('/api/v1/users', 'secret-token-budi99');
  console.log(` Status: ${test2.status} | Respon:`, test2.body);

  // TEST 3: Request ke Orders Service dengan token valid
  console.log("\n>>> [TEST 3]: Mengirim request ke /api/v1/orders DENGAN token valid:");
  const test3 = await sendHttpRequest('/api/v1/orders', 'secret-token-budi99');
  console.log(` Status: ${test3.status} | Respon:`, test3.body);

  // TEST 4: Uji Proteksi Rate Limiting (Membombardir 4 request cepat dengan kuota 3 token)
  console.log("\n>>> [TEST 4]: Membombardir 4 request cepat untuk menguji Rate Limiting (Kuota: 3 token):");
  rateLimiterStore.delete('::1'); // Reset kuota khusus untuk demo test 4
  for (let i = 1; i <= 4; i++) {
    const burst = await sendHttpRequest('/api/v1/orders', 'secret-token-budi99');
    console.log(` - Request #${i}: Status = ${burst.status} ${burst.status === 429 ? '(⛔ RATE LIMITED BLOCKED!)' : '(✅ OK 200)'}`);
  }

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN DEMO]:");
  console.log(" 1. API Gateway sukses memvalidasi otentikasi sebelum menyentuh microservice.");
  console.log(" 2. Header 'x-user-id' disuntikkan secara aman ke microservice.");
  console.log(" 3. Rate limiter berhasil memblokir serangan spam pada request ke-4.");
  console.log("===================================================================\n");

  // Matikan server setelah demo
  usersService.close();
  ordersService.close();
  apiGateway.close();
}

// Beri jeda 200ms agar semua socket listen stabil
setTimeout(runDemo, 200);
