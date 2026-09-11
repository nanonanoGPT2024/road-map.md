/**
 * Hands-on M01: CI/CD Test Sharding Matrix & Pipeline Orchestrator Simulator
 * 
 * Demonstrasi:
 * 1. Algoritma Pembagian Beban Sharding Deterministik (--shard=X/Y).
 * 2. Eksekusi Matriks Paralel Multi-Runner di Cloud (Simulasi 3 Shard Runner).
 * 3. Perhitungan Efisiensi Waktu: Sekuensial vs Paralel Sharding.
 * 4. Generator & Bundler Artefak Kegagalan (Failure Traces & Screenshots).
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
// 1. SHARDING ALGORITHM ENGINE
// ==========================================
class TestSharder {
  static partition(testSuites, shardIndex, totalShards) {
    if (shardIndex < 1 || shardIndex > totalShards) {
      throw new Error(`Invalid shard configuration: ${shardIndex}/${totalShards}`);
    }
    // Urutkan file untuk menjamin determinisme antar-mesin
    const sorted = [...testSuites].sort((a, b) => a.name.localeCompare(b.name));
    return sorted.filter((_, idx) => idx % totalShards === shardIndex - 1);
  }
}

// ==========================================
// 2. PARALLEL RUNNER SIMULATOR
// ==========================================
class VirtualCiRunner {
  constructor(shardId, totalShards) {
    this.shardId = shardId;
    this.totalShards = totalShards;
    this.results = [];
    this.artifacts = [];
  }

  async runShard(assignedSuites) {
    const start = Date.now();
    for (const suite of assignedSuites) {
      // Simulasi eksekusi pengujian (durasi 50-100ms per suite)
      const suiteDuration = Math.floor(60 + Math.random() * 40);
      await new Promise(r => setTimeout(r, suiteDuration));

      const isFailed = suite.shouldFail || false;
      this.results.push({
        name: suite.name,
        durationMs: suiteDuration,
        passed: !isFailed
      });

      if (isFailed) {
        // Hasilkan artefak failure trace
        this.artifacts.push({
          suiteName: suite.name,
          artifactName: `trace-${suite.name.replace(/\s+/g, "-")}.zip`,
          screenshot: `failure-${suite.name.replace(/\s+/g, "-")}.png`
        });
      }
    }

    const totalDuration = Date.now() - start;
    return {
      shardId: this.shardId,
      durationMs: totalDuration,
      results: this.results,
      artifacts: this.artifacts
    };
  }
}

// ==========================================
// 3. MAIN CI/CD ORCHESTRATOR SIMULATION
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║     CI/CD PARALLEL TEST SHARDING & MATRIX PIPELINE LAB        ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 12 Test Suites yang akan dieksekusi di CI/CD
  const allSuites = [
    { name: "01. Auth & Login", shouldFail: false },
    { name: "02. User Profile", shouldFail: false },
    { name: "03. Product Catalog", shouldFail: false },
    { name: "04. Search & Filters", shouldFail: false },
    { name: "05. Cart Operations", shouldFail: false },
    { name: "06. Voucher Discounts", shouldFail: true }, // Sengaja dibuat gagal untuk demonstrasi artefak
    { name: "07. Shipping Calculator", shouldFail: false },
    { name: "08. Payment Gateway", shouldFail: false },
    { name: "09. Order History", shouldFail: false },
    { name: "10. Notifications", shouldFail: false },
    { name: "11. Admin Dashboard", shouldFail: false },
    { name: "12. Audit Logs", shouldFail: false }
  ];

  const totalShards = 3;
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. PARTISI SHARDING (TOTAL: ${allSuites.length} SUITES / ${totalShards} SHARDS) ===${ANSI.reset}`);

  const shardAssignments = [];
  for (let s = 1; s <= totalShards; s++) {
    const assigned = TestSharder.partition(allSuites, s, totalShards);
    shardAssignments.push(assigned);
    console.log(`  ${ANSI.bold}Shard ${s}/${totalShards}${ANSI.reset} (${assigned.length} suites): ${assigned.map(x => x.name).join(", ")}`);
  }

  // 2. EKSEKUSI PARALEL (SIMULTANEOUS RUNNERS IN CLOUD)
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. MENJALANKAN PIPELINE SHARDING SECARA PARALEL ===${ANSI.reset}`);
  const overallStart = Date.now();

  const runnerPromises = shardAssignments.map((assignedSuites, idx) => {
    const runner = new VirtualCiRunner(idx + 1, totalShards);
    return runner.runShard(assignedSuites);
  });

  const shardOutputs = await Promise.all(runnerPromises);
  const parallelExecutionTime = Date.now() - overallStart;

  // Hitung estimasi waktu sekuensial jika dijalankan di 1 mesin
  const sequentialTime = shardOutputs.reduce((acc, out) => acc + out.durationMs, 0);

  // 3. TAMPILKAN HASIL DARI MASING-MASING RUNNER
  for (const out of shardOutputs) {
    console.log(`\n  ${ANSI.bold}Hasil Runner Shard #${out.shardId} (Waktu: ${out.durationMs}ms):${ANSI.reset}`);
    for (const res of out.results) {
      const statusText = res.passed ? `${ANSI.green}✓ PASS${ANSI.reset}` : `${ANSI.red}✗ FAIL${ANSI.reset}`;
      console.log(`    ${statusText} ${res.name} (${res.durationMs}ms)`);
    }

    if (out.artifacts.length > 0) {
      console.log(`    ${ANSI.yellow}📦 ARTEFAK KEGAGALAN TERUNGGAH (GITHUB ACTIONS ARTIFACTS):${ANSI.reset}`);
      for (const art of out.artifacts) {
        console.log(`      → Uploaded Trace : ${art.artifactName}`);
        console.log(`      → Uploaded Screen: ${art.screenshot}`);
      }
    }
  }

  // 4. ANALISIS EFISIENSI & RINGKASAN
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. ANALISIS EFISIENSI PIPELINE SHARDING ===${ANSI.reset}`);
  console.log(`  Estimasi Waktu Sekuensial (1 Mesin) : ${ANSI.yellow}${sequentialTime} ms${ANSI.reset}`);
  console.log(`  Waktu Aktual Paralel Sharding (${totalShards} Mesin) : ${ANSI.bold}${ANSI.green}${parallelExecutionTime} ms${ANSI.reset}`);
  const speedupPercentage = (((sequentialTime - parallelExecutionTime) / sequentialTime) * 100).toFixed(1);
  console.log(`  Peningkatan Kecepatan Pipeline     : ${ANSI.bold}${ANSI.green}+${speedupPercentage}% Lebih Cepat!${ANSI.reset}`);

  console.log(`\n${ANSI.green}✓ CI/CD Test Sharding Matrix Lab executed successfully!${ANSI.reset}\n`);
}

main().catch(console.error);
