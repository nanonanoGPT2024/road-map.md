// latency_benchmark.js
// Praktik Pengukuran Percentiles (p50, p95, p99) & Trade-off Batching Throughput

function calculatePercentile(sortedArray, percentile) {
  if (sortedArray.length === 0) return 0;
  const index = Math.ceil((percentile / 100) * sortedArray.length) - 1;
  return sortedArray[Math.max(0, Math.min(index, sortedArray.length - 1))];
}

// Simulasi operasi I/O database (misal disk write + network trip: 2-8ms bervariasi dengan occasional spike)
function simulateDatabaseWrite(itemCount = 1) {
  return new Promise((resolve) => {
    // Latensi dasar: 3ms. Tiap batch hanya menambah sedikit overhead (0.05ms per item tambahan)
    const baseLatency = 3 + (itemCount * 0.05);
    // Simulasi occasional tail latency spike (jitter 1% kemungkinan spike hingga 35ms)
    const isSpike = Math.random() < 0.015;
    const jitter = isSpike ? (20 + Math.random() * 25) : (Math.random() * 2);
    const totalDelay = baseLatency + jitter;

    setTimeout(() => {
      resolve(totalDelay);
    }, totalDelay);
  });
}

async function runScenarioIndividual(totalItems = 500) {
  console.log(`\n>>> [SKENARIO A: NON-BATCHED / IMMEDIATE WRITE]`);
  console.log(`Mengirim ${totalItems} item satu per satu...`);
  
  const latencies = [];
  const startGlobal = Date.now();

  for (let i = 0; i < totalItems; i++) {
    const itemStart = Date.now();
    await simulateDatabaseWrite(1);
    const duration = Date.now() - itemStart;
    latencies.push(duration);
  }

  const totalWallClock = Date.now() - startGlobal;
  latencies.sort((a, b) => a - b);

  return {
    name: 'Non-Batched (1 item/write)',
    totalItems,
    wallClockMs: totalWallClock,
    throughput: (totalItems / (totalWallClock / 1000)).toFixed(2),
    min: latencies[0],
    p50: calculatePercentile(latencies, 50),
    p90: calculatePercentile(latencies, 90),
    p95: calculatePercentile(latencies, 95),
    p99: calculatePercentile(latencies, 99),
    max: latencies[latencies.length - 1],
    mean: (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(2)
  };
}

async function runScenarioBatched(totalItems = 500, batchSize = 25) {
  console.log(`\n>>> [SKENARIO B: MICRO-BATCHING (Batch Size: ${batchSize})]`);
  console.log(`Mengirim ${totalItems} item dalam kelompok ${batchSize} item...`);

  const itemLatencies = [];
  const startGlobal = Date.now();

  for (let i = 0; i < totalItems; i += batchSize) {
    const currentBatchCount = Math.min(batchSize, totalItems - i);
    const batchStart = Date.now();
    await simulateDatabaseWrite(currentBatchCount);
    const batchDuration = Date.now() - batchStart;

    // Setiap item dalam batch merasakan durasi batch tersebut
    for (let k = 0; k < currentBatchCount; k++) {
      itemLatencies.push(batchDuration);
    }
  }

  const totalWallClock = Date.now() - startGlobal;
  itemLatencies.sort((a, b) => a - b);

  return {
    name: `Micro-Batched (${batchSize} items/batch)`,
    totalItems,
    wallClockMs: totalWallClock,
    throughput: (totalItems / (totalWallClock / 1000)).toFixed(2),
    min: itemLatencies[0],
    p50: calculatePercentile(itemLatencies, 50),
    p90: calculatePercentile(itemLatencies, 90),
    p95: calculatePercentile(itemLatencies, 95),
    p99: calculatePercentile(itemLatencies, 99),
    max: itemLatencies[itemLatencies.length - 1],
    mean: (itemLatencies.reduce((a, b) => a + b, 0) / itemLatencies.length).toFixed(2)
  };
}

async function main() {
  console.log("===================================================================");
  console.log(" BENCHMARK: PENGUKURAN LATENSI PERCENTILES & TRADE-OFF BATCHING");
  console.log("===================================================================");

  const resA = await runScenarioIndividual(300);
  const resB = await runScenarioBatched(300, 25);

  console.log("\n===================================================================");
  console.log("                     TABEL HASIL PERBANDINGAN                      ");
  console.log("===================================================================");
  console.table([resA, resB]);

  console.log("\n[KESIMPULAN ANALISIS ARSITEK]:");
  console.log(`1. Throughput Skenario B melonjak hingga ${(resB.throughput / resA.throughput).toFixed(1)}x lipat lebih tinggi!`);
  console.log(`2. Total waktu pemrosesan terpangkas dari ${resA.wallClockMs}ms menjadi ${resB.wallClockMs}ms.`);
  console.log(`3. Trade-off: Latensi per batch sedikit naik, namun kapasitas sistem melayani volume raksasa meningkat drastis.\n`);
}

main();
