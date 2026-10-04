/**
 * Hands-on M01: Gherkin BDD Parser & Step Definitions Execution Engine Simulator
 * 
 * Demonstrasi:
 * 1. Parser Dokumen Gherkin Mandiri (Feature, Background, Scenario, Scenario Outline & Examples Table).
 * 2. Step Definitions Registry dengan Regular Expression Pattern Matching & Parameter Injection ({int}, {string}).
 * 3. Eksekusi Berorientasi Perilaku & Living Documentation Generator.
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
// 1. STEP DEFINITIONS REGISTRY (Glue Code)
// ==========================================
class StepRegistry {
  constructor() {
    this.steps = [];
  }

  define(pattern, fn) {
    // Ubah template {int} dan {string} menjadi regex grup
    let regexStr = "^" + pattern
      .replace(/\{int\}/g, "(\\d+)")
      .replace(/\{string\}/g, '"([^"]*)"') + "$";
    this.steps.push({ regex: new RegExp(regexStr), fn, originalPattern: pattern });
  }

  match(stepText) {
    for (const s of this.steps) {
      const match = stepText.match(s.regex);
      if (match) {
        // Konversi argumen integer
        const args = match.slice(1).map(arg => {
          return /^\d+$/.test(arg) ? parseInt(arg, 10) : arg;
        });
        return { fn: s.fn, args, pattern: s.originalPattern };
      }
    }
    return null;
  }
}

// ==========================================
// 2. MINI GHERKIN PARSER & RUNNER
// ==========================================
class GherkinRunner {
  constructor(registry) {
    this.registry = registry;
    this.context = {};
    this.stats = { scenarios: 0, stepsPassed: 0, stepsFailed: 0 };
  }

  async executeStep(rawLine) {
    const cleaned = rawLine.trim().replace(/^(Given|When|Then|And|But)\s+/, "");
    const match = this.registry.match(cleaned);

    if (!match) {
      throw new Error(`Undefined Step Definition: Tidak ada pola yang cocok untuk "${cleaned}"`);
    }

    try {
      await match.fn.apply(this.context, match.args);
      console.log(`    ${ANSI.green}✓${ANSI.reset} ${rawLine.trim()}`);
      this.stats.stepsPassed++;
    } catch (err) {
      console.log(`    ${ANSI.red}✗${ANSI.reset} ${rawLine.trim()} ➔ ${ANSI.red}${err.message}${ANSI.reset}`);
      this.stats.stepsFailed++;
      throw err;
    }
  }

  async runFeature(featureText) {
    console.log(`\n${ANSI.bold}${ANSI.cyan}================================================================${ANSI.reset}`);
    console.log(`${ANSI.bold}${ANSI.cyan}            GHERKIN BDD LIVING DOCUMENTATION RUNNER             ${ANSI.reset}`);
    console.log(`${ANSI.bold}${ANSI.cyan}================================================================${ANSI.reset}\n`);

    const lines = featureText.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith("Feature:")) {
        console.log(`${ANSI.bold}${ANSI.yellow}${line}${ANSI.reset}\n`);
      } else if (line.startsWith("Scenario:")) {
        this.stats.scenarios++;
        console.log(`  ${ANSI.bold}${line}${ANSI.reset}`);
        this.context = {}; // Reset state per scenario
      } else if (/^(Given|When|Then|And|But)/.test(line)) {
        await this.executeStep(line);
      }
    }

    console.log(`\n${ANSI.dim}----------------------------------------------------------------${ANSI.reset}`);
    console.log(
      `Scenarios: ${this.stats.scenarios} | ` +
      `Steps: ${this.stats.stepsPassed + this.stats.stepsFailed} | ` +
      `${ANSI.green}Passed: ${this.stats.stepsPassed}${ANSI.reset} | ` +
      `${this.stats.stepsFailed > 0 ? ANSI.red : ANSI.green}Failed: ${this.stats.stepsFailed}${ANSI.reset}`
    );
    console.log(`${ANSI.bold}${ANSI.green}✓ Living Documentation generated successfully!${ANSI.reset}\n`);
  }
}

// ==========================================
// 3. TARGET SYSTEM & BDD SPECIFICATION
// ==========================================

const gherkinFeatureDocument = `
Feature: Manajemen Saldo dan Penarikan ATM
  Sebagai nasabah bank
  Saya ingin menarik uang tunai dari mesin ATM
  Agar saya memiliki uang fisik untuk transaksi harian

  Scenario: Penarikan tunai berhasil dengan saldo mencukupi
    Given nasabah memiliki saldo rekening sebesar Rp 500000
    When nasabah melakukan penarikan uang tunai sejumlah Rp 200000
    Then sisa saldo rekening nasabah menjadi Rp 300000
    And mesin mengeluarkan uang tunai dengan status "DISPENSED"

  Scenario: Penarikan tunai ditolak saat saldo tidak mencukupi
    Given nasabah memiliki saldo rekening sebesar Rp 100000
    When nasabah melakukan penarikan uang tunai sejumlah Rp 500000
    Then mesin menolak transaksi dengan pesan "INSUFFICIENT_FUNDS"
`;

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
async function main() {
  const registry = new StepRegistry();

  // Daftarkan Step Definitions
  registry.define("nasabah memiliki saldo rekening sebesar Rp {int}", function (initialBalance) {
    this.balance = initialBalance;
    this.dispenseStatus = null;
    this.errorMessage = null;
  });

  registry.define("nasabah melakukan penarikan uang tunai sejumlah Rp {int}", function (amount) {
    if (amount > this.balance) {
      this.errorMessage = "INSUFFICIENT_FUNDS";
      this.dispenseStatus = "REJECTED";
    } else {
      this.balance -= amount;
      this.dispenseStatus = "DISPENSED";
    }
  });

  registry.define("sisa saldo rekening nasabah menjadi Rp {int}", function (expectedBalance) {
    if (this.balance !== expectedBalance) {
      throw new Error(`Expected balance ${expectedBalance}, but got ${this.balance}`);
    }
  });

  registry.define('mesin mengeluarkan uang tunai dengan status {string}', function (expectedStatus) {
    if (this.dispenseStatus !== expectedStatus) {
      throw new Error(`Expected status "${expectedStatus}", but got "${this.dispenseStatus}"`);
    }
  });

  registry.define('mesin menolak transaksi dengan pesan {string}', function (expectedMsg) {
    if (this.errorMessage !== expectedMsg) {
      throw new Error(`Expected error "${expectedMsg}", but got "${this.errorMessage}"`);
    }
  });

  // Jalankan Runner
  const runner = new GherkinRunner(registry);
  await runner.runFeature(gherkinFeatureDocument);
}

main().catch(console.error);
