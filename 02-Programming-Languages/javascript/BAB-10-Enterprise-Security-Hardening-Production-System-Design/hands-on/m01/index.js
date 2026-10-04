// server-hardened.mjs
import http from 'node:http';
import { timingSafeEqual, createHmac } from 'node:crypto';

// 1. Immutable Secret Management
const SHARED_SECRET = Buffer.from(process.env.WEBHOOK_SECRET || 'insecure-secret-change-in-production-immediately', 'utf-8');
const MAX_PAYLOAD_BYTES = 1024 * 64; // Batas kaku: 64 KB
const PORT = parseInt(process.env.PORT || '8443', 10);

// Mencegah parsing berbahaya ke Prototype bawaan
function sanitizePayload(rawStr) {
  return JSON.parse(rawStr, (key, value) => {
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      return undefined; // Hapus kunci secara otomatis saat deserialisasi
    }
    return value;
  });
}

// Constant-Time HMAC Signature Check
function validateAuth(rawBodyBuffer, signatureHeader) {
  if (!signatureHeader || typeof signatureHeader !== 'string') {
    return false;
  }

  const computedHmac = createHmac('sha256', SHARED_SECRET).update(rawBodyBuffer).digest();
  const providedHmac = Buffer.from(signatureHeader, 'hex');

  if (computedHmac.length !== providedHmac.length) {
    timingSafeEqual(computedHmac, computedHmac);
    return false;
  }

  return timingSafeEqual(computedHmac, providedHmac);
}

// Inisialisasi Server HTTP Terproteksi
const server = http.createServer({
  keepAlive: true,
  keepAliveTimeout: 5000,
  maxRequestsPerSocket: 1000,
  insecureHTTPParser: false // Wajib false: Tolak malformed HTTP headers
}, (req, res) => {
  // Hardened Security Headers (OWASP Recommended Defaults)
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
  res.setHeader('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');

  if (req.method !== 'POST' || req.url !== '/api/v1/secure-webhook') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Route not found' }));
    return;
  }

  // Enforcement: Content-Type Restriction
  if (req.headers['content-type'] !== 'application/json') {
    res.writeHead(415, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Unsupported Media Type: Must be application/json' }));
    return;
  }

  const chunks = [];
  let receivedBytes = 0;

  req.on('data', (chunk) => {
    receivedBytes += chunk.length;

    // Buffer Overflow & Exhaustion Guard
    if (receivedBytes > MAX_PAYLOAD_BYTES) {
      req.destroy(new Error('Payload Too Large: Max limit exceeded'));
    } else {
      chunks.push(chunk);
    }
  });

  req.on('end', () => {
    const rawBodyBuffer = Buffer.concat(chunks);
    const signature = req.headers['x-hub-signature-256'];

    // Validasi Signature Kriptografis
    if (!validateAuth(rawBodyBuffer, signature)) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Unauthorized: Invalid Cryptographic Signature' }));
      return;
    }

    try {
      // Deserialisasi Aman (Sanitized)
      const sanitizedData = sanitizePayload(rawBodyBuffer.toString('utf-8'));

      // Pemrosesan Payload Bisnis (Simulasi Eksekusi Aman)
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'Accepted', traceId: req.headers['x-request-id'] || null }));
    } catch (parseErr) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Malformed JSON payload' }));
    }
  });

  req.on('error', (err) => {
    if (!res.headersSent) {
      res.writeHead(413, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  });
});

// Kernel Hardening: Melepaskan Linux Privileges setelah Bind Port Rendah
server.listen(PORT, '0.0.0.0', () => {
  console.log(`[RUNTIME SECURE] Listening on port ${PORT}`);

  // Drop Privileges jika proses dijalankan sebagai root/sudo secara tidak sengaja
  if (process.getuid && process.setgid && process.setuid) {
    try {
      const TARGET_UID = 'node'; // Atau UID non-root, misal: 10001
      const TARGET_GID = 'node';
      
      process.setgid(TARGET_GID);
      process.setuid(TARGET_UID);
      console.log(`[PRIVILEGE DROPPED] Successfully switched process user to UID: ${TARGET_UID}`);
    } catch (err) {
      console.error('[SECURITY FATAL] Failed to drop root privileges:', err);
      process.exit(1); // Fail-Closed: Tolak berjalan sebagai root!
    }
  }
});

// Graceful Termination
function shutdown(signal) {
  console.log(`[SHUTDOWN] Signal ${signal} received. Closing HTTP listener...`);
  server.close(() => {
    console.log('[SHUTDOWN] Safe cleanup completed. Terminating.');
    process.exit(0);
  });

  setTimeout(() => {
    console.error('[SHUTDOWN TIMEOUT] Forced shutdown initiated.');
    process.exit(1);
  }, 10000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
