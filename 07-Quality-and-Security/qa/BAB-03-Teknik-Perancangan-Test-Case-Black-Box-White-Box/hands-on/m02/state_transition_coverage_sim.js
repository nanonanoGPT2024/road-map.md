/**
 * Hands-on M02: State Transition Testing & White-Box Coverage Simulator
 * 
 * Demonstrasi:
 * 1. Finite State Machine (FSM) Transaksi E-Commerce dengan Validasi Transisi Terlarang.
 * 2. Control Flow Graph & Cyclomatic Complexity Calculator (V(G) = P + 1).
 * 3. Instrumentasi Kode untuk Melacak Statement Coverage dan Branch Coverage secara Nyata.
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
// 1. STATE TRANSITION ENGINE (FSM)
// ==========================================
const ORDER_STATES = {
  CART: "CART",
  PENDING_PAYMENT: "PENDING_PAYMENT",
  PAID: "PAID",
  SHIPPED: "SHIPPED",
  DELIVERED: "DELIVERED",
  CANCELLED: "CANCELLED"
};

const LEGAL_TRANSITIONS = {
  [ORDER_STATES.CART]: [ORDER_STATES.PENDING_PAYMENT, ORDER_STATES.CANCELLED],
  [ORDER_STATES.PENDING_PAYMENT]: [ORDER_STATES.PAID, ORDER_STATES.CANCELLED],
  [ORDER_STATES.PAID]: [ORDER_STATES.SHIPPED, ORDER_STATES.CANCELLED], // Cancelled with refund
  [ORDER_STATES.SHIPPED]: [ORDER_STATES.DELIVERED],
  [ORDER_STATES.DELIVERED]: [], // Terminal state
  [ORDER_STATES.CANCELLED]: []  // Terminal state
};

class OrderFSM {
  constructor(orderId) {
    this.orderId = orderId;
    this.state = ORDER_STATES.CART;
    this.transitionHistory = [];
  }

  transitionTo(nextState) {
    const allowed = LEGAL_TRANSITIONS[this.state] || [];
    if (!allowed.includes(nextState)) {
      throw new Error(
        `[ILLEGAL_TRANSITION] Pesanan ${this.orderId} dilarang berpindah dari state [${this.state}] langsung ke [${nextState}]. Target sah: [${allowed.join(", ") || "None"}]`
      );
    }
    const previous = this.state;
    this.state = nextState;
    this.transitionHistory.push({ from: previous, to: nextState });
    console.log(`    State: ${previous} ➔ ${ANSI.bold}${nextState}${ANSI.reset}`);
  }
}

// ==========================================
// 2. WHITE-BOX INSTRUMENTATION ENGINE
// Target Function: Loan Risk Assessment
// ==========================================
class CoverageTracker {
  constructor() {
    this.statements = new Set();
    this.branches = {
      "B1_TRUE": 0, "B1_FALSE": 0,
      "B2_TRUE": 0, "B2_FALSE": 0,
      "B3_TRUE": 0, "B3_FALSE": 0
    };
    this.totalStatements = 7;
    this.totalBranches = 6;
  }

  trackStatement(id) {
    this.statements.add(id);
  }

  trackBranch(branchKey) {
    this.branches[branchKey]++;
  }

  getCoverage() {
    const statementPercent = ((this.statements.size / this.totalStatements) * 100).toFixed(1);
    const hitBranches = Object.values(this.branches).filter(count => count > 0).length;
    const branchPercent = ((hitBranches / this.totalBranches) * 100).toFixed(1);
    return { statementPercent, branchPercent, hitBranches, totalBranches: this.totalBranches };
  }
}

const tracker = new CoverageTracker();

// Instrumented Target Function
function evaluateLoanInstrumented(income, creditScore, hasCollateral) {
  tracker.trackStatement("STMT_1"); // Entry

  // Predikat 1: income >= 10jt
  if (income >= 10000000) {
    tracker.trackStatement("STMT_2");
    tracker.trackBranch("B1_TRUE");

    // Predikat 2: creditScore >= 700
    if (creditScore >= 700) {
      tracker.trackStatement("STMT_3");
      tracker.trackBranch("B2_TRUE");
      return "APPROVED_PREMIUM";
    } else {
      tracker.trackStatement("STMT_4");
      tracker.trackBranch("B2_FALSE");
      return "APPROVED_STANDARD";
    }
  } else {
    tracker.trackStatement("STMT_5");
    tracker.trackBranch("B1_FALSE");

    // Predikat 3: hasCollateral
    if (hasCollateral) {
      tracker.trackStatement("STMT_6");
      tracker.trackBranch("B3_TRUE");
      return "APPROVED_WITH_COLLATERAL";
    } else {
      tracker.trackStatement("STMT_7");
      tracker.trackBranch("B3_FALSE");
      return "REJECTED";
    }
  }
}

// ==========================================
// 3. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║   STATE TRANSITION & WHITE-BOX CODE COVERAGE LAB RUNNER       ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. DEMONSTRASI STATE TRANSITION TESTING
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. STATE TRANSITION: HAPPY PATH (0-SWITCH COVERAGE) ===${ANSI.reset}`);
  const order = new OrderFSM("ORD-9901");
  order.transitionTo(ORDER_STATES.PENDING_PAYMENT);
  order.transitionTo(ORDER_STATES.PAID);
  order.transitionTo(ORDER_STATES.SHIPPED);
  order.transitionTo(ORDER_STATES.DELIVERED);
  console.log(`  ${ANSI.green}✓ Happy path alur hidup pesanan berhasil diverifikasi.${ANSI.reset}`);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. STATE TRANSITION: NEGATIVE / ILLEGAL JUMP DETECTION ===${ANSI.reset}`);
  const hackerOrder = new OrderFSM("ORD-6666");
  try {
    console.log("  [Attempt] Pengguna mencoba melompat langsung dari CART ke SHIPPED (Bypass Bayar):");
    hackerOrder.transitionTo(ORDER_STATES.SHIPPED);
  } catch (err) {
    console.log(`  ${ANSI.red}✓ DITOLAK (State Protection Active): ${err.message}${ANSI.reset}`);
  }

  // 2. DEMONSTRASI WHITE-BOX COVERAGE & CYCLOMATIC COMPLEXITY
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. CYCLOMATIC COMPLEXITY (THOMAS MCCABE) ===${ANSI.reset}`);
  const predicateDecisions = 3; // (income >= 10jt), (creditScore >= 700), (hasCollateral)
  const cyclomaticComplexity = predicateDecisions + 1;
  console.log(`  Titik Predikat Keputusan (P): ${predicateDecisions}`);
  console.log(`  Cyclomatic Complexity V(G)  : ${ANSI.bold}${cyclomaticComplexity}${ANSI.reset} (Minimal ${cyclomaticComplexity} test cases untuk 100% Branch Coverage)`);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 4. MENJALANKAN BASIS PATH TEST SUITE ===${ANSI.reset}`);
  const testCases = [
    { id: "TC-01", income: 15000000, creditScore: 750, collateral: false, expected: "APPROVED_PREMIUM" },
    { id: "TC-02", income: 15000000, creditScore: 600, collateral: false, expected: "APPROVED_STANDARD" },
    { id: "TC-03", income: 5000000,  creditScore: 0,   collateral: true,  expected: "APPROVED_WITH_COLLATERAL" },
    { id: "TC-04", income: 5000000,  creditScore: 0,   collateral: false, expected: "REJECTED" }
  ];

  for (const tc of testCases) {
    const res = evaluateLoanInstrumented(tc.income, tc.creditScore, tc.collateral);
    const pass = res === tc.expected;
    console.log(
      `  ${pass ? ANSI.green + "✓" : ANSI.red + "✗"}${ANSI.reset} ${tc.id}: ` +
      `Income=${tc.income.toLocaleString("id-ID")}, Score=${tc.creditScore}, Collateral=${tc.collateral} ➔ ${res}`
    );
  }

  // 3. COVERAGE REPORT
  const coverage = tracker.getCoverage();
  console.log(`\n${ANSI.bold}HASIL METRIK CAKUPAN STRUKTURAL KODE (WHITE-BOX):${ANSI.reset}`);
  console.log(`  Statement Coverage: ${ANSI.bold}${ANSI.green}${coverage.statementPercent}%${ANSI.reset} (${tracker.statements.size}/${tracker.totalStatements} baris instruksi)`);
  console.log(`  Branch Coverage   : ${ANSI.bold}${ANSI.green}${coverage.branchPercent}%${ANSI.reset} (${coverage.hitBranches}/${coverage.totalBranches} cabang boolean)`);
  console.log(`\n${ANSI.green}✓ State Transition & White-Box Lab executed successfully!${ANSI.reset}\n`);
}

main();
