/**
 * Hands-on M01: Latency Percentile Calculator, Flaw of Averages & Little's Law Simulator
 * 
 * Demonstrasi:
 * 1. Kalkulator Persentil Presisi (Mean, p50, p90, p95, p99) dari ribuan sampel latensi riil.
 * 2. Pembuktian "The Flaw of Averages": Mengapa rata-rata menyembunyikan ekor latensi buruk.
 * 3. Kalkulator Kapasitas Hukum Little (Little's Law: L = λ * W).
 * 4. Simulator Deteksi Knee Point & Saturation Cliff.
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
// 1. LATENCY PERCENTILE CALCULATOR ENGINE
// ==========================================
class LatencyAnalyzer {
  constructor(samples) {
    this.samples = [...samples].sort((a, b) => a - b);
    this.total = this.samples.length;
  }

  getMean() {
    const sum = this.samples.reduce((acc, val) => acc + val, 0);
    return Number((sum / this.total).toFixed(2));
  }

  getPercentile(p) {
    if (this.total === 0) return 0;
    const rank = Math.ceil((p / 100) * this.total) - 1;
    const index = Math.max(0, Math.min(rank, this.total - 1));
    return this.samples[index];
  }

  getMetricsSummary() {
    return {
      totalRequests: this.total,
      min: this.samples[0],
      max: this.samples[this.total - 1],
      mean: this.getMean(),
      p50: this.getPercentile(50),
      p90: this.getPercentile(90),
      p95: this.getPercentile(95),
      p99: this.getPercentile(99)
    };
  }
}

// ==========================================
// 2. LITTLE'S LAW CALCULATOR
// ==========================================
class LittlesLawEngine {
  // L = lambda * W
  static calculateThroughput(concurrencyVUs, responseTimeSeconds) {
    if (responseTimeSeconds <= 0) return 0;
    const rps = concurrencyVUs / responseTimeSeconds;
    return Number(rps.toFixed(2));
  }

  static calculateRequiredConcurrency(targetRps, responseTimeSeconds) {
    const vus = targetRps * responseTimeSeconds;
    return Math.ceil(vus);
  }
}

// ==========================================
// 3. KNEE POINT & SATURATION SIMULATOR
// ==========================================
function simulateRampingLoad() {
  const steps = [
    { vus: 10,  latencyMs: 40,  maxCapacityRps: 1000 },
    { vus: 50,  latencyMs: 45,  maxCapacityRps: 1000 },
    { vus: 100, latencyMs: 60,  maxCapacityRps: 1000 },
    { vus: 200, latencyMs: 120, maxCapacityRps: 1000 }, // KNEE POINT
    { vus: 300, latencyMs: 450, maxCapacityRps: 1000 }, // QUEUEING
    { vus: 500, latencyMs: 2500, maxCapacityRps: 1000 } // SATURATION CLIFF
  ];

  const results = [];
  for (const s of steps) {
    const theoreticalRps = (s.vus / (s.latencyMs / 1000));
    const actualRps = Math.min(Math.round(theoreticalRps), s.maxCapacityRps);
    let phase = "Linier (Sehat)";
    if (s.vus === 200) phase = "KNEE POINT (Kapasitas Puncak)";
    else if (s.vus > 200 && s.vus < 500) phase = "Queueing (Mengantre)";
    else if (s.vus >= 500) phase = "SATURATION CLIFF (Sistem Kolaps)";

    results.push({
      "Beban (VUs)": s.vus,
      "Throughput (RPS)": actualRps,
      "Latensi (ms)": s.latencyMs,
      "Fase Performa": phase
    });
  }
  return results;
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║     PERFORMANCE METRICS, PERCENTILES & LITTLE'S LAW LAB       ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. GENERATE SAMPLE DATA DENGAN LONG-TAIL DISTRIBUTION
  // 950 request sangat cepat (30-60ms), 40 request sedang (150-300ms), 10 request ekstrem (2000-5000ms)
  const samples = [];
  for (let i = 0; i < 950; i++) samples.push(Math.floor(30 + Math.random() * 30));
  for (let i = 0; i < 40; i++) samples.push(Math.floor(150 + Math.random() * 150));
  for (let i = 0; i < 10; i++) samples.push(Math.floor(2000 + Math.random() * 3000));

  const analyzer = new LatencyAnalyzer(samples);
  const metrics = analyzer.getMetricsSummary();

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. ANALISIS PERSENTIL LATENSI (TOTAL 1.000 REQUESTS) ===${ANSI.reset}`);
  console.log(`  Min Latency     : ${metrics.min} ms`);
  console.log(`  Max Latency     : ${ANSI.red}${metrics.max} ms${ANSI.reset}`);
  console.log(`  Rata-rata (Mean): ${ANSI.yellow}${metrics.mean} ms${ANSI.reset}  <-- Terdistorsi oleh ekor data!`);
  console.log(`  Median (p50)    : ${ANSI.green}${metrics.p50} ms${ANSI.reset}   <-- Pengalaman 50% pengguna`);
  console.log(`  90th Percentile : ${metrics.p90} ms`);
  console.log(`  95th Percentile : ${ANSI.bold}${metrics.p95} ms${ANSI.reset}   <-- Standar SLA`);
  console.log(`  99th Percentile : ${ANSI.bold}${ANSI.red}${metrics.p99} ms${ANSI.reset}   <-- Ekor Panjang (Long-Tail)`);

  console.log(`\n  ${ANSI.bold}Pelajaran Kritis (The Flaw of Averages):${ANSI.reset}`);
  console.log(`  Jika Anda hanya melihat Mean (${metrics.mean}ms), Anda mengira sistem cukup aman.`);
  console.log(`  Padahal p99 (${metrics.p99}ms) menunjukkan 10 pengguna penting mengalami freeze selama > 2 detik!`);

  // 2. LITTLE'S LAW CALCULATOR DEMO
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. KALKULASI HUKUM LITTLE (LITTLE'S LAW: L = λ * W) ===${ANSI.reset}`);
  const targetThroughput = 2500; // 2.500 RPS
  const expectedLatencySec = 0.08; // 80 ms = 0.08 detik
  const requiredVUs = LittlesLawEngine.calculateRequiredConcurrency(targetThroughput, expectedLatencySec);

  console.log(`  Target Throughput  : ${targetThroughput} Requests/Second`);
  console.log(`  Expected Latency   : ${expectedLatencySec * 1000} ms (${expectedLatencySec} detik)`);
  console.log(`  Kebutuhan Konkurensi: ${ANSI.bold}${ANSI.green}${requiredVUs} Virtual Users (VUs)${ANSI.reset} aktif bersamaan.`);

  // 3. KNEE POINT & SATURATION CLIFF SIMULATION
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. DETEKSI KNEE POINT & SATURATION CLIFF (RAMPING TEST) ===${ANSI.reset}`);
  const curveData = simulateRampingLoad();
  console.table(curveData);

  console.log(`\n${ANSI.green}✓ Performance Metrics & Little's Law Lab executed successfully!${ANSI.reset}\n`);
}

main();
