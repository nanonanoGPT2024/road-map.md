// lab-single.js
// Simulasi Server Single Process (1 CPU Core Event Loop)
const http = require('http');

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
  res.end(`Single Server running on PID: ${process.pid}\n`);
});

const PORT = 4000;
server.listen(PORT, () => {
  console.log(`[Single Server] Berjalan di http://localhost:${PORT} (PID: ${process.pid})`);
  console.log(`Endpoint uji: http://localhost:${PORT}/cpu`);
});
