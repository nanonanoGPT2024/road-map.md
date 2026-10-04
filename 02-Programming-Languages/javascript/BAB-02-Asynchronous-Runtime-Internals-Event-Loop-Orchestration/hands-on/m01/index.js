// resilient-batch-processor.mjs
import { createServer } from 'node:http';
import { createHmac } from 'node:crypto';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);

// ==========================================
// WORKER THREAD POOL EXECUTION (CPU-BOUND)
// ==========================================
if (!isMainThread) {
  const { batch, secret } = workerData;
  
  // Memproses komputasi CPU intensif di thread terisolasi
  const processed = batch.map((item) => {
    const hash = createHmac('sha256', secret)
      .update(JSON.stringify(item))
      .digest('hex');
    return { ...item, signature: hash, processedAt: Date.now() };
  });

  // Kirim hasil kembali ke thread utama
  parentPort.postMessage(processed);
  process.exit(0);
}

// ==========================================
// MAIN EVENT LOOP THREAD
// ==========================================
function executeInWorker(batch, secret) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(__filename, {
      workerData: { batch, secret },
    });

    worker.on('message', resolve);
    worker.on('error', reject);
    worker.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(`Worker stopped with exit code ${code}`));
      }
    });
  });
}

/**
 * Teknik Interleaving: Memecah array besar ke potongan kecil
 * dan mengembalikan kontrol ke Event Loop via setImmediate
 */
async function* processChunked(items, chunkSize = 500) {
  for (let i = 0; i < items.length; i += chunkSize) {
    const chunk = items.slice(i, i + chunkSize);
    // Yield chunk untuk diproses
    yield chunk;
    // CRITICAL: Melepaskan kendali ke Check Phase Event Loop
    await new Promise((resolve) => setImmediate(resolve));
  }
}

// HTTP Server
const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/healthz') {
    // Health check harus selalu dijawab seketika
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ status: 'UP', timestamp: Date.now() }));
  }

  if (req.method === 'POST' && req.url === '/ingest') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body); // Asumsi: payload adalah array of items
        
        if (!Array.isArray(payload)) {
          res.writeHead(400);
          return res.end('Payload must be an array');
        }

        const totalItems = payload.length;
        let processedResults = [];

        // Jika ukuran batch kecil, gunakan chunking kooperatif di main thread
        // Jika sangat masif, delegasikan ke Worker Thread
        if (totalItems > 5000) {
          processedResults = await executeInWorker(payload, 'production-salt-secret');
        } else {
          for await (const chunk of processChunked(payload, 200)) {
            const transformed = chunk.map((item) => ({
              ...item,
              checksum: createHmac('sha256', 'salt').update(JSON.stringify(item)).digest('hex'),
            }));
            processedResults.push(...transformed);
          }
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          status: 'SUCCESS', 
          count: processedResults.length 
        }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(3000, () => {
  console.log('Ingestion engine active on :3000. PID:', process.pid);
});
