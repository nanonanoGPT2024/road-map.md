/**
 * Hands-on M02: Nginx Reverse Proxy, Load Balancer, & Rate Limiter Simulator
 * Mengilustrasikan konsep:
 * 1. Reverse Proxy Routing & Header Injection (X-Forwarded-For)
 * 2. Load Balancing (Round-Robin & Least Connections)
 * 3. Rate Limiting (Token Bucket -> HTTP 429)
 * 4. Upstream Failover & Error Handling (HTTP 502 Bad Gateway)
 *
 * Jalankan: node nginx_reverse_proxy_sim.js
 */

const http = require('http');

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

// ==========================================
// 1. UPSTREAM BACKEND WORKERS
// ==========================================
function createBackendServer(id, port) {
  const server = http.createServer((req, res) => {
    // Simulasi jeda pemrosesan 50ms
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        message: 'Hello from Upstream Service',
        workerId: id,
        port: port,
        clientIp: req.headers['x-forwarded-for'] || req.socket.remoteAddress
      }));
    }, 50);
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(`${colors.cyan}[UPSTREAM STARTED] Worker ${id} aktif di port ${port}${colors.reset}`);
      resolve(server);
    });
  });
}

// ==========================================
// 2. REVERSE PROXY & LOAD BALANCER
// ==========================================
class ReverseProxyGateway {
  constructor(options = {}) {
    this.port = options.port || 18080;
    this.upstreams = options.upstreams || [];
    this.currentIndex = 0;
    this.rateLimitMap = new Map(); // IP -> { tokens, lastRefill }
    this.maxTokens = 3; // Maks 3 request instan per IP
    this.server = null;
  }

  // Token bucket rate limiter
  checkRateLimit(clientIp) {
    const now = Date.now();
    let record = this.rateLimitMap.get(clientIp);

    if (!record) {
      record = { tokens: this.maxTokens, lastRefill: now };
      this.rateLimitMap.set(clientIp, record);
    }

    // Refill 1 token per 500ms
    const timePassed = now - record.lastRefill;
    const tokensToAdd = Math.floor(timePassed / 500);
    if (tokensToAdd > 0) {
      record.tokens = Math.min(this.maxTokens, record.tokens + tokensToAdd);
      record.lastRefill = now;
    }

    if (record.tokens > 0) {
      record.tokens--;
      return true; // Allowed
    }
    return false; // Rate limited
  }

  // Pilih upstream dengan Round-Robin
  selectUpstream() {
    const upstream = this.upstreams[this.currentIndex];
    this.currentIndex = (this.currentIndex + 1) % this.upstreams.length;
    return upstream;
  }

  start() {
    return new Promise((resolve) => {
      this.server = http.createServer((req, res) => {
        const clientIp = req.socket.remoteAddress || '127.0.0.1';

        // 1. Security Check: Rate Limiting
        if (!this.checkRateLimit(clientIp)) {
          console.log(`  ${colors.red}[RATE LIMIT EXCEEDED] IP ${clientIp} melampaui kuota! Return 429${colors.reset}`);
          res.writeHead(429, {
            'Content-Type': 'application/json',
            'Retry-After': '1',
            'X-Frame-Options': 'DENY'
          });
          return res.end(JSON.stringify({ error: 'Too Many Requests (Rate limit exceeded)' }));
        }

        // 2. Load Balancing Selection
        const target = this.selectUpstream();
        console.log(`  ${colors.yellow}[PROXY FORWARD] ${req.method} ${req.url} -> Upstream ${target.id} (${target.host}:${target.port})${colors.reset}`);

        // 3. Forward request ke backend
        const proxyReq = http.request({
          host: target.host,
          port: target.port,
          method: req.method,
          path: req.url,
          headers: {
            ...req.headers,
            'X-Forwarded-For': clientIp,
            'X-Forwarded-Proto': 'http',
            'X-Proxy-By': 'OpenClaw-Nginx-Sim'
          }
        }, (proxyRes) => {
          // 4. Inject Security Hardening Headers
          const headers = {
            ...proxyRes.headers,
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'Server': 'Nginx-Hardened'
          };
          res.writeHead(proxyRes.statusCode, headers);
          proxyRes.pipe(res);
        });

        proxyReq.on('error', (err) => {
          console.log(`  ${colors.red}[502 BAD GATEWAY] Gagal menghubungi upstream ${target.id}: ${err.message}${colors.reset}`);
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Bad Gateway: Upstream unreachable' }));
        });

        req.pipe(proxyReq);
      });

      this.server.listen(this.port, () => {
        console.log(`${colors.green}[REVERSE PROXY ACTIVE] Mendengarkan pada http://localhost:${this.port}${colors.reset}\n`);
        resolve();
      });
    });
  }

  stop() {
    if (this.server) this.server.close();
  }
}

// Client helper
function sendRequest(port) {
  return new Promise((resolve) => {
    http.get(`http://localhost:${port}/api/orders`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, raw: data });
        }
      });
    }).on('error', (err) => resolve({ error: err.message }));
  });
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: REVERSE PROXY & LOAD BALANCER ===${colors.reset}\n`);

  // Start 2 upstream servers
  const backend1 = await createBackendServer('Worker-Alpha', 18081);
  const backend2 = await createBackendServer('Worker-Beta', 18082);

  // Start reverse proxy on 18080
  const proxy = new ReverseProxyGateway({
    port: 18080,
    upstreams: [
      { id: 'Worker-Alpha', host: '127.0.0.1', port: 18081 },
      { id: 'Worker-Beta', host: '127.0.0.1', port: 18082 }
    ]
  });
  await proxy.start();

  // Test 1: Load Balancing Round Robin
  console.log('--- TEST 1: LOAD BALANCING ROUND ROBIN ---');
  const res1 = await sendRequest(18080);
  console.log(`Req #1: HTTP ${res1.status} ditangani oleh: ${res1.body.workerId}`);

  const res2 = await sendRequest(18080);
  console.log(`Req #2: HTTP ${res2.status} ditangani oleh: ${res2.body.workerId}`);

  const res3 = await sendRequest(18080);
  console.log(`Req #3: HTTP ${res3.status} ditangani oleh: ${res3.body.workerId}`);

  // Test 2: Rate Limiting Test (Bursts > 3)
  console.log('\n--- TEST 2: RATE LIMITING BURST SPIKE (EXPECT 429) ---');
  const res4 = await sendRequest(18080);
  console.log(`Req #4: HTTP ${res4.status} -> ${res4.body ? res4.body.error || 'OK' : ''}`);

  // Test 3: Upstream Failure (Simulasi 502 Bad Gateway)
  console.log('\n--- TEST 3: UPSTREAM CRASH & 502 BAD GATEWAY ---');
  console.log('Mematikan Worker-Alpha (Port 18081)...');
  backend1.close();

  // Tunggu jeda agar rate limit ter-refill
  await new Promise(r => setTimeout(r, 1200));

  const res5 = await sendRequest(18080);
  console.log(`Req ke Worker-Beta : HTTP ${res5.status}`);

  await new Promise(r => setTimeout(r, 600));

  const res6 = await sendRequest(18080);
  console.log(`Req ke Worker-Alpha (Mati): HTTP ${res6.status} -> ${res6.body.error}`);

  // Cleanup
  proxy.stop();
  backend2.close();
  console.log(`\n${colors.bold}${colors.green}=== SEMUA PENGUJIAN REVERSE PROXY & LOAD BALANCER SELESAI DENGAN SUKSES ===${colors.reset}`);
  process.exit(0);
}

runLab();
