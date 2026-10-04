/**
 * Hands-on M02: Grafana k6 Load Testing Engine & Threshold Quality Gates Simulator
 * 
 * Demonstrasi:
 * 1. Virtual User (VU) Execution Engine dengan tahapan Ramping & Spike.
 * 2. Metrik Performa Real-Time (Throughput, Latency Persentil p50/p90/p95/p99, Error Rate).
 * 3. Evaluator Quality Gates (Thresholds): Memblokir rilis jika SLA performa terlanggar.
 * 4. Tampilan Format Laporan Standar CLI Grafana k6.
 */

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. k6 SIMULATED LOAD GENERATOR CORE
// ==========================================
class K6LoadGenerator {
  constructor(options) {
    this.options = options;
    this.latencies = [];
    this.failedRequests = 0;
    this.totalRequests = 0;
    this.customCounters = { successful_orders: 0 };
  }

  // Simulasi pemanggilan HTTP oleh VU individual
  async executeVuIteration(vuId, isSpike = false) {
    this.totalRequests++;
    
    // Latensi dasar 30-70ms, jika saat spike naik menjadi 120-450ms
    let latency = isSpike 
      ? Math.floor(120 + Math.random() * 330)
      : Math.floor(30 + Math.random() * 40);

    // 1% probabilitas error acak
    const isError = Math.random() < 0.01;

    if (isError) {
      this.failedRequests++;
      latency += 500; // Timeouts
    } else {
      this.customCounters.successful_orders++;
    }

    this.latencies.push(latency);
    // Think time acak
    await new Promise(r => setTimeout(r, Math.floor(10 + Math.random() * 20)));
  }

  // Menjalankan skenario bertahap (Stages)
  async run() {
    console.log(`\n${ANSI.bold}${ANSI.cyan}================================================================${ANSI.reset}`);
    console.log(`${ANSI.bold}${ANSI.cyan}             GRAFANA k6 LOAD TESTING EXECUTION ENGINE           ${ANSI.reset}`);
    console.log(`${ANSI.bold}${ANSI.cyan}================================================================${ANSI.reset}\n`);

    const stages = this.options.stages || [{ durationMs: 200, targetVus: 20 }];
    const startTime = Date.now();

    for (let sIdx = 0; sIdx < stages.length; sIdx++) {
      const stage = stages[sIdx];
      const isSpike = stage.isSpike || false;
      console.log(
        `  ${ANSI.yellow}→ Stage ${sIdx + 1}/${stages.length}:${ANSI.reset} ` +
        `Ramping to ${ANSI.bold}${stage.targetVus} VUs${ANSI.reset} ` +
        `[${stage.name || "Normal Load"}]`
      );

      // Jalankan kumpulan VUs paralel
      const vuPromises = [];
      for (let vu = 1; vu <= stage.targetVus; vu++) {
        vuPromises.push(this.executeVuIteration(vu, isSpike));
      }
      await Promise.all(vuPromises);
    }

    const durationSeconds = Number(((Date.now() - startTime) / 1000).toFixed(2));
    return this.evaluateResults(durationSeconds);
  }

  evaluateResults(durationSeconds) {
    this.latencies.sort((a, b) => a - b);
    const count = this.latencies.length;
    const sum = this.latencies.reduce((a, b) => a + b, 0);

    const getP = (p) => {
      const idx = Math.min(count - 1, Math.max(0, Math.ceil((p / 100) * count) - 1));
      return this.latencies[idx];
    };

    const metrics = {
      totalRequests: count,
      durationSec: durationSeconds,
      rps: Number((count / durationSeconds).toFixed(1)),
      errorRate: Number((this.failedRequests / count).toFixed(4)),
      min: this.latencies[0],
      max: this.latencies[count - 1],
      avg: Number((sum / count).toFixed(1)),
      med: getP(50),
      p90: getP(90),
      p95: getP(95),
      p99: getP(99),
      successfulOrders: this.customCounters.successful_orders
    };

    // Evaluasi Quality Gates (Thresholds)
    const thresholdResults = [];
    let allPassed = true;

    if (this.options.thresholds) {
      for (const [metricKey, rules] of Object.entries(this.options.thresholds)) {
        for (const rule of rules) {
          let passed = false;
          let actualVal = 0;

          if (metricKey === "http_req_duration") {
            const maxAllowed = parseInt(rule.replace("p(95)<", "").replace("p(99)<", ""));
            if (rule.startsWith("p(95)<")) {
              actualVal = metrics.p95;
              passed = actualVal < maxAllowed;
            } else if (rule.startsWith("p(99)<")) {
              actualVal = metrics.p99;
              passed = actualVal < maxAllowed;
            }
          } else if (metricKey === "http_req_failed") {
            const maxRate = parseFloat(rule.replace("rate<", ""));
            actualVal = metrics.errorRate;
            passed = actualVal < maxRate;
          }

          if (!passed) allPassed = false;
          thresholdResults.push({ metricKey, rule, actualVal, passed });
        }
      }
    }

    return { metrics, thresholdResults, allPassed };
  }
}

// ==========================================
// 2. MAIN SIMULATION EXECUTION
// ==========================================
async function main() {
  const k6Config = {
    stages: [
      { name: "Warm-up Phase", targetVus: 15, isSpike: false },
      { name: "FLASH SALE SPIKE!", targetVus: 80, isSpike: true },
      { name: "Recovery Cooldown", targetVus: 10, isSpike: false }
    ],
    thresholds: {
      "http_req_duration": ["p(95)<400"], // 95% request harus di bawah 400ms
      "http_req_failed": ["rate<0.05"]     // Error rate harus di bawah 5%
    }
  };

  const engine = new K6LoadGenerator(k6Config);
  const { metrics, thresholdResults, allPassed } = await engine.run();

  // Print k6-Style CLI Summary Report
  console.log(`\n${ANSI.bold}========================== SUMMARY PERFORMANCE REPORT ==========================${ANSI.reset}`);
  console.log(`  Execution Duration       : ${metrics.durationSec}s`);
  console.log(`  Total Iterations (Reqs)  : ${metrics.totalRequests} requests`);
  console.log(`  Throughput               : ${ANSI.bold}${ANSI.cyan}${metrics.rps} reqs/s${ANSI.reset}`);
  console.log(`  Successful Orders        : ${ANSI.green}${metrics.successfulOrders}${ANSI.reset}`);
  console.log(`  Failed Requests Rate     : ${(metrics.errorRate * 100).toFixed(2)}% (${engine.failedRequests} errors)\n`);

  console.log(`${ANSI.bold}  HTTP Request Duration (ms):${ANSI.reset}`);
  console.log(`    avg = ${metrics.avg}ms    min = ${metrics.min}ms    med = ${metrics.med}ms    max = ${metrics.max}ms`);
  console.log(`    ${ANSI.bold}p(90) = ${metrics.p90}ms    p(95) = ${metrics.p95}ms    p(99) = ${metrics.p99}ms${ANSI.reset}\n`);

  console.log(`${ANSI.bold}  Quality Gates (Thresholds Status):${ANSI.reset}`);
  for (const t of thresholdResults) {
    const symbol = t.passed ? `${ANSI.green}✓ PASS${ANSI.reset}` : `${ANSI.red}✗ FAIL${ANSI.reset}`;
    console.log(`    ${symbol} [${t.metricKey}] threshold '${t.rule}' (Actual: ${t.actualVal})`);
  }

  console.log(`\n${ANSI.dim}--------------------------------------------------------------------------------${ANSI.reset}`);
  if (allPassed) {
    console.log(`${ANSI.bold}${ANSI.green}🎉 ALL PERFORMANCE QUALITY GATES PASSED! READY FOR PRODUCTION DEPLOYMENT.${ANSI.reset}\n`);
  } else {
    console.log(`${ANSI.bold}${ANSI.red}🚨 PERFORMANCE SLA BREACHED! CI/CD PIPELINE BLOCKED (EXIT CODE 1).${ANSI.reset}\n`);
  }
}

main().catch(console.error);
