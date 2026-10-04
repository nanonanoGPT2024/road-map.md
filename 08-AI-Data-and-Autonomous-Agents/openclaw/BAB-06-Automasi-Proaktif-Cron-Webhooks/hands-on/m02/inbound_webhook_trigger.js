/**
 * Hands-on M02: OpenClaw Inbound Webhook Listener & Action Trigger Simulator
 * Mengilustrasikan penerimaan webhook eksternal (misal: GitHub/Stripe),
 * verifikasi HMAC-SHA256, deduplikasi idempotency, dan eksekusi aksi asinkron.
 *
 * Jalankan: node inbound_webhook_trigger.js
 */

const http = require('http');
const crypto = require('crypto');

// ANSI Colors
const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

const WEBHOOK_SECRET = 'my_super_secret_openclaw_token_2026';
const PORT = 18790;

class OpenClawWebhookGateway {
  constructor(port, secret) {
    this.port = port;
    this.secret = secret;
    this.processedEventIds = new Set();
    this.server = null;
  }

  // Verifikasi HMAC-SHA256 (timing-safe)
  verifySignature(rawBody, signatureHeader) {
    if (!signatureHeader) return false;
    const parts = signatureHeader.split('=');
    if (parts.length !== 2 || parts[0] !== 'sha256') return false;

    const receivedHash = parts[1];
    const expectedHash = crypto
      .createHmac('sha256', this.secret)
      .update(rawBody, 'utf8')
      .digest('hex');

    try {
      return crypto.timingSafeEqual(
        Buffer.from(receivedHash, 'utf8'),
        Buffer.from(expectedHash, 'utf8')
      );
    } catch {
      return false;
    }
  }

  // Simulasi reasoning LLM & eksekusi tindakan secara asinkron
  async processEventAsync(eventData) {
    console.log(`${colors.magenta}[AI AGENT REASONING] Memproses event: "${eventData.eventType}" (ID: ${eventData.id})...${colors.reset}`);
    
    // Simulasi jeda AI reasoning 300ms
    await new Promise(r => setTimeout(r, 300));

    if (eventData.eventType === 'github:pull_request') {
      const { repo, prNumber, author, title, changes } = eventData.payload;
      console.log(`  -> Evaluasi PR #${prNumber} di repo "${repo}" oleh @${author}: "${title}"`);
      console.log(`  -> Analisis Diff: ${changes.additions} baris ditambah, ${changes.deletions} baris dihapus.`);
      
      // Simulasi tindakan proaktif mengirim ringkasan ke Telegram
      console.log(`\n${colors.green}[TELEGRAM NOTIFICATION PROAKTIF DIKIRIM]${colors.reset}`);
      console.log(`  Penerima: @tech_lead`);
      console.log(`  Pesan   : 🔔 PR Baru #${prNumber} (${title}) diajukan oleh @${author}. Analisis bot: Siap di-review, tidak ada breaking changes.\n`);
    } else if (eventData.eventType === 'server:crash_alert') {
      console.log(`\n${colors.red}[URGENT INCIDENT DETECTED] Server: ${eventData.payload.serverIp}${colors.reset}`);
      console.log(`  Tindakan Otonom: Membuka SSH diagnostic session... Service di-restart otomatis.`);
    }
  }

  start() {
    return new Promise((resolve) => {
      this.server = http.createServer((req, res) => {
        if (req.method === 'POST' && req.url === '/api/v1/webhooks/github') {
          let bodyChunks = [];

          req.on('data', chunk => bodyChunks.push(chunk));
          req.on('end', () => {
            const rawBody = Buffer.concat(bodyChunks).toString('utf8');
            const signatureHeader = req.headers['x-hub-signature-256'];

            // 1. Verifikasi Keamanan HMAC
            const isValid = this.verifySignature(rawBody, signatureHeader);
            if (!isValid) {
              console.log(`${colors.red}[SECURITY REJECT] Webhook ditolak: Signature HMAC tidak cocok!${colors.reset}`);
              res.writeHead(401, { 'Content-Type': 'application/json' });
              return res.end(JSON.stringify({ error: 'Unauthorized: Invalid signature' }));
            }

            // 2. Parse JSON Payload
            let eventData;
            try {
              eventData = JSON.parse(rawBody);
            } catch {
              res.writeHead(400, { 'Content-Type': 'application/json' });
              return res.end(JSON.stringify({ error: 'Bad Request: Malformed JSON' }));
            }

            // 3. Deduplikasi Idempotency
            if (eventData.id && this.processedEventIds.has(eventData.id)) {
              console.log(`${colors.yellow}[IDEMPOTENCY DUPLICATE] Event ID "${eventData.id}" sudah pernah diproses. Lewati.${colors.reset}`);
              res.writeHead(200, { 'Content-Type': 'application/json' });
              return res.end(JSON.stringify({ status: 'Ignored: Duplicate event' }));
            }

            if (eventData.id) {
              this.processedEventIds.add(eventData.id);
            }

            // 4. Segera kembalikan respons HTTP 202 Accepted (Non-blocking)
            res.writeHead(202, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'Accepted', eventId: eventData.id }));

            // 5. Jalankan pemrosesan background
            setImmediate(() => {
              this.processEventAsync(eventData);
            });
          });
        } else {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Not Found' }));
        }
      });

      this.server.listen(this.port, () => {
        console.log(`${colors.cyan}[WEBHOOK GATEWAY STARTED] Mendengarkan pada http://localhost:${this.port}/api/v1/webhooks/github${colors.reset}`);
        resolve();
      });
    });
  }

  stop() {
    if (this.server) {
      this.server.close();
      console.log(`${colors.yellow}[WEBHOOK GATEWAY STOPPED]${colors.reset}`);
    }
  }
}

// Fungsi helper untuk client pengirim HTTP request
function sendWebhookRequest(port, secret, eventData, customSignature = null) {
  return new Promise((resolve, reject) => {
    const payloadStr = JSON.stringify(eventData);
    
    // Hitung signature valid jika tidak disediakan custom signature
    const signature = customSignature !== null
      ? customSignature
      : 'sha256=' + crypto.createHmac('sha256', secret).update(payloadStr, 'utf8').digest('hex');

    const options = {
      hostname: 'localhost',
      port: port,
      path: '/api/v1/webhooks/github',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payloadStr),
        'X-Hub-Signature-256': signature
      }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ statusCode: res.statusCode, body: JSON.parse(data) }));
    });

    req.on('error', reject);
    req.write(payloadStr);
    req.end();
  });
}

// ==========================================
// TEST SCENARIO
// ==========================================
async function runLab() {
  const gateway = new OpenClawWebhookGateway(PORT, WEBHOOK_SECRET);
  await gateway.start();

  console.log('\n--- Uji Coba 1: Mengirim Webhook Valid (GitHub PR Event) ---');
  const validEvent = {
    id: 'evt_gh_98234710',
    eventType: 'github:pull_request',
    payload: {
      repo: 'acme-corp/payment-gateway',
      prNumber: 42,
      author: 'dev_andi',
      title: 'feat: add QRIS support with instant settlement',
      changes: { additions: 140, deletions: 12 }
    }
  };

  const res1 = await sendWebhookRequest(PORT, WEBHOOK_SECRET, validEvent);
  console.log(`Respons Server: HTTP ${res1.statusCode}`, res1.body);

  // Tunggu sejenak agar background async reasoning selesai
  await new Promise(r => setTimeout(r, 600));

  console.log('\n--- Uji Coba 2: Mengirim Payload yang Sama (Uji Deduplikasi Idempotency) ---');
  const res2 = await sendWebhookRequest(PORT, WEBHOOK_SECRET, validEvent);
  console.log(`Respons Server: HTTP ${res2.statusCode}`, res2.body);

  console.log('\n--- Uji Coba 3: Mengirim Webhook dengan Signature Palsu / Invalid ---');
  const invalidSignatureEvent = {
    id: 'evt_fake_1111',
    eventType: 'github:pull_request',
    payload: { title: 'Hack attempt' }
  };
  const res3 = await sendWebhookRequest(PORT, WEBHOOK_SECRET, invalidSignatureEvent, 'sha256=invalid_hash_abc123');
  console.log(`Respons Server: HTTP ${res3.statusCode}`, res3.body);

  console.log(`\n${colors.bold}${colors.green}=== SEMUA PENGUJIAN LAB WEBHOOK SELESAI DENGAN SUKSES ===${colors.reset}`);
  gateway.stop();
  process.exit(0);
}

runLab();
