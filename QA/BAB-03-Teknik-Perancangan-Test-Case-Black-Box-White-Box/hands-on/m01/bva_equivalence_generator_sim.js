/**
 * Hands-on M01: BVA, Equivalence Partitioning, & Decision Table Testing Simulator
 * 
 * Fitur:
 * 1. Generator Otomatis Titik Uji BVA (2-value & 3-value boundary).
 * 2. Generator Partisi Ekuivalensi (Valid & Invalid partitions).
 * 3. Evaluator Matriks Decision Table Logika Bisnis Kompleks.
 * 4. Pembuktian penemuan bug batas tepi (Off-by-One Detection).
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
// 1. GENERATOR BVA & EQUIVALENCE PARTITIONING
// ==========================================
class RangeBoundaryGenerator {
  constructor(field, min, max) {
    this.field = field;
    this.min = min;
    this.max = max;
  }

  generatePartitions() {
    return [
      { type: "INVALID_LOW", range: `< ${this.min}`, sample: this.min - 5, expected: false },
      { type: "VALID", range: `${this.min} - ${this.max}`, sample: Math.floor((this.min + this.max) / 2), expected: true },
      { type: "INVALID_HIGH", range: `> ${this.max}`, sample: this.max + 5, expected: false }
    ];
  }

  generate3ValueBVA() {
    return [
      { name: "Min - 1 (Just Below)", value: this.min - 1, expected: false, category: "Boundary Invalid" },
      { name: "Min (Exact Lower Bound)", value: this.min, expected: true, category: "Boundary Valid" },
      { name: "Min + 1 (Just Above)", value: this.min + 1, expected: true, category: "Boundary Valid" },
      { name: "Nominal (Center)", value: Math.floor((this.min + this.max) / 2), expected: true, category: "Normal Valid" },
      { name: "Max - 1 (Just Below)", value: this.max - 1, expected: true, category: "Boundary Valid" },
      { name: "Max (Exact Upper Bound)", value: this.max, expected: true, category: "Boundary Valid" },
      { name: "Max + 1 (Just Above)", value: this.max + 1, expected: false, category: "Boundary Invalid" }
    ];
  }
}

// ==========================================
// 2. DECISION TABLE EVALUATOR
// ==========================================
class DecisionTableEngine {
  constructor() {
    this.rules = [];
  }

  addRule({ ruleId, conditions, expectedAction }) {
    this.rules.push({ ruleId, conditions, expectedAction });
  }

  evaluate(actualConditions) {
    for (const rule of this.rules) {
      const match = Object.keys(rule.conditions).every(
        key => rule.conditions[key] === actualConditions[key]
      );
      if (match) return rule.expectedAction;
    }
    return "UNKNOWN_RULE";
  }
}

// ==========================================
// 3. TARGET SYSTEM UNDER TEST (SUT)
// ==========================================

// Fungsi dengan bug: sengaja menggunakan '>' bukan '>=' pada batas bawah
function faultyAgeValidator(age) {
  if (typeof age !== "number" || isNaN(age)) return false;
  // BUG: age > 21 menyebabkan pemohon usia 21 tahun tertolak!
  if (age > 21 && age <= 65) {
    return true;
  }
  return false;
}

// Fungsi diskon bisnis e-commerce
function calculateCheckoutDiscount({ isVip, spendAbove500k, hasCoupon }) {
  if (isVip && spendAbove500k) return "DISCOUNT_25_PERCENT";
  if (isVip || spendAbove500k) return "DISCOUNT_10_PERCENT";
  if (hasCoupon) return "DISCOUNT_5_PERCENT";
  return "NO_DISCOUNT";
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║     BLACK-BOX DESIGN: BVA, EP & DECISION TABLE SIMULATOR      ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. GENERATE EP & BVA FOR AGE RANGE [21, 65]
  const generator = new RangeBoundaryGenerator("Usia Pengajuan Kredit", 21, 65);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. HASIL ANALISIS EQUIVALENCE PARTITIONING (EP) ===${ANSI.reset}`);
  const partitions = generator.generatePartitions();
  console.table(partitions);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. HASIL GENERASI TITIK UJI 3-VALUE BVA ===${ANSI.reset}`);
  const bvaCases = generator.generate3ValueBVA();
  console.table(bvaCases);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. EKSEKUSI BVA PADA SYSTEM UNDER TEST (OFF-BY-ONE BUG DETECTION) ===${ANSI.reset}`);
  let detectedBugs = 0;
  for (const tc of bvaCases) {
    const actual = faultyAgeValidator(tc.value);
    const passed = actual === tc.expected;

    if (passed) {
      console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} [Input: ${tc.value.toString().padStart(2)}] Expected: ${tc.expected.toString().padEnd(5)} | Actual: ${actual}`);
    } else {
      console.log(
        `  ${ANSI.red}✗ FAIL (BUG FOUND!)${ANSI.reset} [Input: ${tc.value.toString().padStart(2)}] ` +
        `Expected: ${tc.expected} | Actual: ${actual} (${ANSI.yellow}${tc.name}${ANSI.reset})`
      );
      detectedBugs++;
    }
  }

  console.log(
    `\n  ${ANSI.bold}Analisis QA:${ANSI.reset} Pengujian acak (misal umur 30) memberikan false sense of security (PASS 100%). ` +
    `Namun teknik BVA berhasil menangkap ${ANSI.red}${detectedBugs} bug off-by-one${ANSI.reset} tepat pada batas tepi umur 21!`
  );

  // 2. DECISION TABLE TESTING
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 4. DECISION TABLE EVALUATION (COMBINATORIAL RULES) ===${ANSI.reset}`);
  const dt = new DecisionTableEngine();

  // Daftarkan aturan bisnis
  dt.addRule({ ruleId: "R1", conditions: { isVip: true, spendAbove500k: true, hasCoupon: true }, expectedAction: "DISCOUNT_25_PERCENT" });
  dt.addRule({ ruleId: "R2", conditions: { isVip: true, spendAbove500k: true, hasCoupon: false }, expectedAction: "DISCOUNT_25_PERCENT" });
  dt.addRule({ ruleId: "R3", conditions: { isVip: true, spendAbove500k: false, hasCoupon: true }, expectedAction: "DISCOUNT_10_PERCENT" });
  dt.addRule({ ruleId: "R4", conditions: { isVip: true, spendAbove500k: false, hasCoupon: false }, expectedAction: "DISCOUNT_10_PERCENT" });
  dt.addRule({ ruleId: "R5", conditions: { isVip: false, spendAbove500k: true, hasCoupon: true }, expectedAction: "DISCOUNT_10_PERCENT" });
  dt.addRule({ ruleId: "R6", conditions: { isVip: false, spendAbove500k: true, hasCoupon: false }, expectedAction: "DISCOUNT_10_PERCENT" });
  dt.addRule({ ruleId: "R7", conditions: { isVip: false, spendAbove500k: false, hasCoupon: true }, expectedAction: "DISCOUNT_5_PERCENT" });
  dt.addRule({ ruleId: "R8", conditions: { isVip: false, spendAbove500k: false, hasCoupon: false }, expectedAction: "NO_DISCOUNT" });

  let dtPassed = 0;
  for (const rule of dt.rules) {
    const actualResult = calculateCheckoutDiscount(rule.conditions);
    const isMatch = actualResult === rule.expectedAction;
    if (isMatch) dtPassed++;

    console.log(
      `  ${isMatch ? ANSI.green + "✓" : ANSI.red + "✗"}${ANSI.reset} Rule ${rule.ruleId}: ` +
      `VIP=${rule.conditions.isVip ? "Y" : "N"}, Spend>500k=${rule.conditions.spendAbove500k ? "Y" : "N"}, Coupon=${rule.conditions.hasCoupon ? "Y" : "N"} ` +
      `➔ Expected: ${rule.expectedAction} | Actual: ${actualResult}`
    );
  }

  console.log(`\n${ANSI.bold}--------------------------------------------------${ANSI.reset}`);
  console.log(`Decision Table Result: ${ANSI.green}${dtPassed}/${dt.rules.length} Rules Passed${ANSI.reset}`);
  console.log(`\n${ANSI.green}✓ BVA, EP, and Decision Table Lab executed successfully!${ANSI.reset}\n`);
}

main();
