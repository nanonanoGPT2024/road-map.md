// benchmark.js
// Script untuk mengirimkan request konkuren guna mengukur efek bottleneck vs horizontal scaling
const http = require('http');

const TOTAL_REQUESTS = 12;
const TARGET_URL = 'http://localhost:4000/cpu';

function sendRequest(requestId) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const req = http.get(TARGET_URL, (res) => {
      let rawData = '';
      res.on('data', (chunk) => { rawData += chunk; });
      res.on('end', () => {
        const duration = Date.now() - startTime;
        try {
          const parsed = JSON.parse(rawData);
          resolve({
            id: requestId,
            success: true,
            duration,
            workerPid: parsed.workerPid
          });
        } catch (e) {
          resolve({ id: requestId, success: true, duration, workerPid: 'unknown' });
        }
      });
    });

    req.on('error', (err) => {
      resolve({ id: requestId, success: false, duration: Date.now() - startTime, error: err.message });
    });
  });
}

async function runBenchmark() {
  console.log(`=======================================================`);
  console.log(` Memulai Benchmark: Mengirim ${TOTAL_REQUESTS} request konkuren ke:`);
  console.log(` ${TARGET_URL}`);
  console.log(`=======================================================`);

  const globalStart = Date.now();
  const requestPromises = [];

  for (let i = 1; i <= TOTAL_REQUESTS; i++) {
    requestPromises.push(sendRequest(i));
  }

  const results = await Promise.all(requestPromises);
  const totalWallClockTime = Date.now() - globalStart;

  console.log(`\nDetail Hasil Tiap Request:`);
  results.forEach(r => {
    if (r.success) {
      console.log(` - Request #${r.id.toString().padStart(2, '0')} | Selesai dlm: ${r.duration.toString().padStart(4, ' ')} ms | Diproses oleh Worker PID: ${r.workerPid}`);
    } else {
      console.log(` - Request #${r.id.toString().padStart(2, '0')} | GAGAL: ${r.error}`);
    }
  });

  console.log(`\n-------------------------------------------------------`);
  console.log(` TOTAL WAKTU PENYELESAIAN (Wall-clock Time): ${totalWallClockTime} ms`);
  console.log(` Rata-rata Throughput: ${(TOTAL_REQUESTS / (totalWallClockTime / 1000)).toFixed(2)} req/sec`);
  console.log(`=======================================================\n`);
}

runBenchmark();
