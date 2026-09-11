// lab-cluster.js
// Simulasi Horizontal Scaling Lokal (Multi-Process Cluster menggunakan beberapa CPU Cores)
const cluster = require('cluster');
const http = require('http');
const os = require('os');

// Gunakan 4 worker (atau jumlah core CPU komputer)
const numWorkers = Math.min(os.cpus().length, 4);

if (cluster.isPrimary) {
  console.log(`[Primary Master PID: ${process.pid}] Menjalankan ${numWorkers} worker process...`);

  for (let i = 0; i < numWorkers; i++) {
    cluster.fork();
  }

  cluster.on('exit', (worker, code, signal) => {
    console.log(`[Worker PID: ${worker.process.pid}] berhenti. Membuat worker pengganti...`);
    cluster.fork();
  });
} else {
  // Setiap worker adalah proses Node.js independen
  function cpuIntensiveTask() {
    let count = 0;
    for (let i = 0; i < 4e7; i++) {
      count += i;
    }
    return count;
  }

  const server = http.createServer((req, res) => {
    if (req.url === '/cpu') {
      const start = Date.now();
      const result = cpuIntensiveTask();
      const duration = Date.now() - start;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        workerPid: process.pid,
        durationMs: duration,
        result: result
      }));
    }

    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(`Cluster Worker Handled by PID: ${process.pid}\n`);
  });

  const PORT = 4000;
  server.listen(PORT, () => {
    console.log(`  -> Worker PID: ${process.pid} siap menerima request di port ${PORT}`);
  });
}
