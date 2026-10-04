/**
 * SIMULATOR: LOAD TESTING ENGINE & PERSENTIL LATENSI (p50, p95, p99 TAIL LATENCY)
 * Modul 02: Static Analysis, CI/CD Automation, & Load Testing (p99 Latency)
 *
 * Mendemonstrasikan:
 * 1. Pembangkit beban konkuren sintetis (Virtual Users).
 * 2. Distribusi latensi realistis (Bimodal: 95% cepat, 1% tail latency akibat I/O & GC).
 * 3. Kalkulasi matematis metrik Mean vs Persentil (p50, p90, p95, p99, p99.9).
 * 4. Evaluasi otomatis ambang batas kualitas (Quality Gate / SLA Thresholds).
 *
 * Jalankan: node load_testing_latency_p99_sim.js
 */

// =========================================================================
// BAGIAN 1: SIMULATOR ENDPOINT BACKEND DENGAN ANOMALI TAIL LATENCY
// =========================================================================

class MockBackendEndpoint {
  // Simulasi endpoint yang memproses request dengan variasi latensi realistis
  static async handleRequest(reqId) {
    const rand = Math.random();
    let latencyMs;

    if (rand < 0.95) {
      // 95% Kasus Cepat (Cache Hit / Index Scan Cepat): 5 - 25 ms
      latencyMs = Math.floor(5 + Math.random() * 20);
    } else if (rand < 0.99) {
      // 4% Kasus Sedang (Query DB Kompleks): 30 - 80 ms
      latencyMs = Math.floor(30 + Math.random() * 50);
    } else {
      // 1% Kasus Ekstrem Tail (GC Pause / Connection Pool Contention): 350 - 600 ms!
      latencyMs = Math.floor(350 + Math.random() * 250);
    }

    // Simulasi delay eksekusi
    await new Promise(resolve => setTimeout(resolve, Math.min(latencyMs, 10))); // Scaled down for speed
    return { reqId, latencyMs, status: 200 };
  }
}

// =========================================================================
// BAGIAN 2: MESIN KALKULASI PERSENTIL & METRIK BEBAN
// =========================================================================

class LoadTestMetricsEngine {
  static calculatePercentiles(latencies) {
    if (latencies.length === 0) return null;

    // 1. Urutkan latensi dari terkecil ke terbesar
    const sorted = [...latencies].sort((a, b) => a - b);
    const count = sorted.length;

    // 2. Hitung nilai persentil berdasarkan indeks array
    const getPercentile = (p) => {
      const index = Math.ceil((p / 100) * count) - 1;
      return sorted[Math.max(0, Math.min(index, count - 1))];
    };

    // 3. Hitung rata-rata (Mean)
    const sum = sorted.reduce((acc, val) => acc + val, 0);
    const mean = (sum / count).toFixed(2);

    return {
      totalRequests: count,
      min: sorted[0],
      max: sorted[count - 1],
      mean: Number(mean),
      p50: getPercentile(50),  // Median
      p90: getPercentile(90),
      p95: getPercentile(95),
      p99: getPercentile(99),  // Tail Latency
      p99_9: getPercentile(99.9)
    };
  }

  static renderVisualDistribution(latencies) {
    const buckets = [
      { label: '< 25 ms  (Sangat Cepat)', min: 0, max: 25, count: 0 },
      { label: '25-80 ms (Normal)',        min: 25, max: 80, count: 0 },
      { label: '80-300 ms(Lambat)',        min: 80, max: 300, count: 0 },
      { label: '> 300 ms (Tail Spikes)',   min: 300, max: Infinity, count: 0 }
    ];

    latencies.forEach(lat => {
      for (const b of buckets) {
        if (lat >= b.min && lat < b.max) {
          b.count++;
          break;
        }
      }
    });

    console.log('\nHistogram Distribusi Latensi:');
    buckets.forEach(b => {
      const pct = ((b.count / latencies.length) * 100).toFixed(1);
      const bar = '█'.repeat(Math.round(pct / 2));
      console.log(`  ${b.label.padEnd(25)}: ${String(b.count).padStart(4)} req (${pct.padStart(5)}%) ${bar}`);
    });
  }
}

// =========================================================================
// BAGIAN 3: EKSEKUSI PENGUJIAN BEBAN BEBAN BERULANG
// =========================================================================

async function runLoadTest(totalRequests = 1000) {
  console.log('='.repeat(75));
  console.log(`MEMULAI SIMULASI LOAD TESTING (${totalRequests} REQUEST KONKUREN)`);
  console.log('='.repeat(75));

  const latencies = [];
  const startTime = Date.now();

  for (let i = 1; i <= totalRequests; i++) {
    const result = await MockBackendEndpoint.handleRequest(i);
    latencies.push(result.latencyMs);
  }

  const durationMs = Date.now() - startTime;
  const metrics = LoadTestMetricsEngine.calculatePercentiles(latencies);

  console.log('\nHASIL METRIK PENGUJIAN BEBAN:');
  console.log(`- Total Request Berhasil : ${metrics.totalRequests}`);
  console.log(`- Waktu Eksekusi Uji     : ${durationMs} ms`);
  console.log(`- Throughput Sintetis    : ${((metrics.totalRequests / (durationMs / 1000))).toFixed(1)} req/detik`);
  console.log(`- Minimum Latency        : ${metrics.min} ms`);
  console.log(`- Maximum Latency (Peak) : ${metrics.max} ms`);
  console.log(`\nPERBANDINGAN RATA-RATA VS PERSENTIL:`);
  console.log(`  📊 Average (Mean)   : ${metrics.mean} ms  <-- Tampak bagus dan normal!`);
  console.log(`  🟢 p50 (Median)     : ${metrics.p50} ms   <-- 50% pengguna menikmati kecepatan ini`);
  console.log(`  🟡 p90 Percentile   : ${metrics.p90} ms`);
  console.log(`  🟠 p95 Percentile   : ${metrics.p95} ms`);
  console.log(`  🔴 p99 Percentile   : ${metrics.p99} ms  <-- 1% pengguna mengalami kelambatan fatal!`);
  console.log(`  🔥 p99.9 Percentile : ${metrics.p99_9} ms`);

  LoadTestMetricsEngine.renderVisualDistribution(latencies);

  // EVALUASI QUALITY GATE / SLA THRESHOLDS
  console.log('\n' + '-'.repeat(75));
  console.log('EVALUASI SERVICE LEVEL AGREEMENT (SLA QUALITY GATE):');
  console.log('-'.repeat(75));

  const slaThresholds = {
    meanMax: 100, // Mean harus < 100 ms
    p95Max: 90,   // p95 harus < 90 ms
    p99Max: 300   // p99 harus < 300 ms
  };

  const meanPassed = metrics.mean < slaThresholds.meanMax;
  const p95Passed = metrics.p95 < slaThresholds.p95Max;
  const p99Passed = metrics.p99 < slaThresholds.p99Max;

  console.log(`  [SLA 1] Mean < ${slaThresholds.meanMax}ms : ${metrics.mean} ms -> ${meanPassed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`  [SLA 2] p95  < ${slaThresholds.p95Max}ms  : ${metrics.p95} ms  -> ${p95Passed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`  [SLA 3] p99  < ${slaThresholds.p99Max}ms : ${metrics.p99} ms -> ${p99Passed ? '✅ PASSED' : '❌ FAILED (TAIL LATENCY VIOLATION!)'}`);

  console.log('\n' + '='.repeat(75));
  if (meanPassed && !p99Passed) {
    console.log('⚠️ BUKTI NYATA: Rata-rata (Mean) LULUS, tetapi Tail Latency p99 GAGAL!');
    console.log('   Inilah alasan mengapa engineer backend profesional WAJIB mengukur p99!');
  } else {
    console.log('SIMULASI BERHASIL: Evaluasi seluruh persentil terekam akurat!');
  }
  console.log('='.repeat(75));
}

runLoadTest(1000);
