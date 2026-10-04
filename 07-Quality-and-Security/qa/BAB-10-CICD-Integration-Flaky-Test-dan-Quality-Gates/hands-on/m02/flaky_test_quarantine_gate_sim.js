/**
 * Hands-on M02: Flaky Test Detection, Quarantine Pattern, & Release Quality Gates Simulator
 * 
 * Demonstrasi:
 * 1. Engine Deteksi Flaky Tests dengan Mekanisme Retry Otomatis (Pass on Retry Detection).
 * 2. Kalkulator Metrik Flaky Rate & Algoritma Karantina Otomatis.
 * 3. Evaluator Gerbang Kualitas Rilis (Go/No-Go Release Decision Framework):
 *    - Zero S1/S2 Defects
 *    - 100% Smoke Suite Pass
 *    - Flaky Rate Threshold (<= 2.0%)
 *    - Latency p95 SLA (<= 300ms)
 *    - Minimum Code Coverage (>= 80%)
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
// 1. FLAKY TEST RUNNER & RETRY ENGINE
// ==========================================
class TestExecutionEngine {
  constructor() {
    this.results = [];
    this.quarantinedTests = new Set();
  }

  quarantine(testName) {
    this.quarantinedTests.add(testName);
  }

  async runTest(testSpec, maxRetries = 2) {
    let attempts = 0;
    let passed = false;
    const isQuarantined = this.quarantinedTests.has(testSpec.name);

    while (attempts <= maxRetries && !passed) {
      attempts++;
      // Simulasi eksekusi: tes flaky memiliki 50% probabilitas gagal pada attempt 1
      if (testSpec.isFlaky && attempts === 1) {
        passed = false;
      } else if (testSpec.isBroken) {
        passed = false;
      } else {
        passed = true;
      }
    }

    let status = "PASSED";
    if (!passed) {
      status = "FAILED";
    } else if (attempts > 1) {
      status = "FLAKY"; // Lulus setelah retry
    }

    const record = {
      name: testSpec.name,
      status,
      attempts,
      isQuarantined,
      blocksRelease: !isQuarantined && status === "FAILED"
    };

    this.results.push(record);
    return record;
  }

  getMetrics() {
    const total = this.results.length;
    const passedFirstTry = this.results.filter(r => r.status === "PASSED").length;
    const flaky = this.results.filter(r => r.status === "FLAKY").length;
    const failed = this.results.filter(r => r.status === "FAILED").length;
    const flakyRate = Number(((flaky / total) * 100).toFixed(2));

    return { total, passedFirstTry, flaky, failed, flakyRate };
  }
}

// ==========================================
// 2. RELEASE QUALITY GATE EVALUATOR
// ==========================================
class ReleaseQualityGate {
  static evaluate({ openDefects, smokePassed, p95Latency, codeCoverage, flakyRate }) {
    const checks = [
      {
        name: "Zero S1 Critical & S2 Major Defects",
        passed: openDefects.filter(d => d.severity === "S1" || d.severity === "S2").length === 0,
        actual: `${openDefects.length} open bugs`,
        threshold: "0 critical/major bugs"
      },
      {
        name: "Smoke Test Suite Status",
        passed: smokePassed === true,
        actual: smokePassed ? "100% Passed" : "Failed",
        threshold: "100% Pass Required"
      },
      {
        name: "Flaky Test Rate SLA",
        passed: flakyRate <= 2.0,
        actual: `${flakyRate}%`,
        threshold: "<= 2.0%"
      },
      {
        name: "Performance Latency p95 SLA",
        passed: p95Latency <= 300,
        actual: `${p95Latency} ms`,
        threshold: "<= 300 ms"
      },
      {
        name: "Core Branch Code Coverage",
        passed: codeCoverage >= 80,
        actual: `${codeCoverage}%`,
        threshold: ">= 80%"
      }
    ];

    const isGo = checks.every(c => c.passed);
    return { isGo, checks };
  }
}

// ==========================================
// 3. MAIN SIMULATION EXECUTION
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║     FLAKY TEST DETECTION, QUARANTINE & QUALITY GATES LAB       ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  const engine = new TestExecutionEngine();

  // Test Suite Simulasi
  const testSuite = [
    { name: "TC-01: Login dengan Kredensial Valid", isFlaky: false, isBroken: false },
    { name: "TC-02: Keranjang Belanja Sinkronisasi Multi-Tab", isFlaky: true, isBroken: false }, // FLAKY!
    { name: "TC-03: Kalkulasi Diskon Promo Tanggal Kembar", isFlaky: false, isBroken: false },
    { name: "TC-04: Notifikasi SMS Gateway Timeout", isFlaky: true, isBroken: false }, // FLAKY!
    { name: "TC-05: Checkout Kartu Kredit 3D Secure", isFlaky: false, isBroken: false },
    { name: "TC-06: Riwayat Pesanan Legacy Format", isFlaky: false, isBroken: true } // BROKEN!
  ];

  // Karantina tes lama yang diketahui bermasalah
  engine.quarantine("TC-06: Riwayat Pesanan Legacy Format");

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. MENJALANKAN TEST SUITE DENGAN AUTO-RETRY (MAX RETRIES: 2) ===${ANSI.reset}`);
  for (const t of testSuite) {
    const res = await engine.runTest(t);
    let color = ANSI.green;
    if (res.status === "FLAKY") color = ANSI.yellow;
    if (res.status === "FAILED") color = ANSI.red;

    const quarantineBadge = res.isQuarantined ? ` ${ANSI.cyan}[QUARANTINED]${ANSI.reset}` : "";
    console.log(
      `  ${color}[${res.status}]${ANSI.reset} ${res.name} ` +
      `${ANSI.dim}(Attempts: ${res.attempts})${ANSI.reset}${quarantineBadge}`
    );
  }

  const metrics = engine.getMetrics();
  console.log(`\n${ANSI.bold}METRIK KESEHATAN TEST SUITE:${ANSI.reset}`);
  console.log(`  Total Test Cases    : ${metrics.total}`);
  console.log(`  Passed First Try    : ${ANSI.green}${metrics.passedFirstTry}${ANSI.reset}`);
  console.log(`  Flaky (Pass on Retry): ${ANSI.yellow}${metrics.flaky}${ANSI.reset}`);
  console.log(`  Failed Definitif    : ${ANSI.red}${metrics.failed}${ANSI.reset}`);
  console.log(`  Flaky Rate          : ${ANSI.bold}${metrics.flakyRate}%${ANSI.reset} (Standard Industri: <= 2.0%)\n`);

  // 2. EVALUASI RELEASE QUALITY GATE (GO / NO-GO DECISION)
  console.log(`${ANSI.bold}${ANSI.cyan}=== 2. EVALUASI GERBANG KUALITAS RILIS (GO / NO-GO QUALITY GATE) ===${ANSI.reset}`);

  // Skenario Audit Rilis
  const releaseContext = {
    openDefects: [
      { id: "BUG-881", title: "Minor font color di FAQ", severity: "S4" }
    ],
    smokePassed: true,
    p95Latency: 210, // 210ms (SLA <= 300ms)
    codeCoverage: 84.5, // 84.5% (SLA >= 80%)
    flakyRate: metrics.flakyRate // 33.33% (Melebihi batas 2%!)
  };

  const gateResult = ReleaseQualityGate.evaluate(releaseContext);

  for (const check of gateResult.checks) {
    const symbol = check.passed ? `${ANSI.green}✓ PASS${ANSI.reset}` : `${ANSI.red}✗ FAIL${ANSI.reset}`;
    console.log(`  ${symbol} ${check.name.padEnd(36)}: Actual: ${check.actual.padEnd(12)} | Req: ${check.threshold}`);
  }

  console.log(`\n${ANSI.dim}--------------------------------------------------------------------------------${ANSI.reset}`);
  if (gateResult.isGo) {
    console.log(`${ANSI.bold}${ANSI.green}🎉 GO DECISION: Seluruh kriteria gerbang kualitas terpenuhi. Siap rilis ke Produksi!${ANSI.reset}\n`);
  } else {
    console.log(`${ANSI.bold}${ANSI.red}🛑 NO-GO DECISION: Rilis DIBLOKIR oleh Quality Gate! Flaky Rate terlalu tinggi (${metrics.flakyRate}% > 2.0%).${ANSI.reset}`);
    console.log(`   ${ANSI.yellow}Tindakan: Stabilkan atau karantina tes flaky sebelum rilis dilanjutkan.${ANSI.reset}\n`);
  }

  console.log(`${ANSI.green}✓ Flaky Test & Quality Gates Lab executed successfully!${ANSI.reset}\n`);
}

main();
