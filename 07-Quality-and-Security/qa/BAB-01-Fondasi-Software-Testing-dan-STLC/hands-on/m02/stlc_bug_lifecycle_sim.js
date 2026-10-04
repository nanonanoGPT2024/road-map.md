/**
 * Hands-on M02: STLC Bug / Defect Lifecycle State Machine & QA Metrics Engine
 * 
 * Fitur:
 * 1. State Machine Defect Lifecycle dengan validasi aturan transisi ketat (Role-Based State Transition).
 * 2. Generator dan Validator Tiket Bug Berstandar Industri.
 * 3. Kalkulator Metrik Kualitas Perangkat Lunak: Defect Removal Efficiency (DRE), Defect Density, & Severity Breakdown.
 */

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  magenta: "\x1b[35m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. DEFECT STATE MACHINE DEFINITION
// ==========================================
const DEFECT_STATUS = {
  NEW: "NEW",
  ASSIGNED: "ASSIGNED",
  OPEN: "OPEN",
  FIXED: "FIXED",
  PENDING_RETEST: "PENDING_RETEST",
  RETEST: "RETEST",
  VERIFIED: "VERIFIED",
  CLOSED: "CLOSED",
  REOPENED: "REOPENED",
  REJECTED: "REJECTED",
  DEFERRED: "DEFERRED",
  DUPLICATE: "DUPLICATE"
};

const VALID_TRANSITIONS = {
  [DEFECT_STATUS.NEW]: [DEFECT_STATUS.ASSIGNED, DEFECT_STATUS.REJECTED],
  [DEFECT_STATUS.ASSIGNED]: [DEFECT_STATUS.OPEN, DEFECT_STATUS.DEFERRED, DEFECT_STATUS.DUPLICATE, DEFECT_STATUS.REJECTED],
  [DEFECT_STATUS.OPEN]: [DEFECT_STATUS.FIXED, DEFECT_STATUS.DEFERRED, DEFECT_STATUS.REJECTED],
  [DEFECT_STATUS.FIXED]: [DEFECT_STATUS.PENDING_RETEST],
  [DEFECT_STATUS.PENDING_RETEST]: [DEFECT_STATUS.RETEST],
  [DEFECT_STATUS.RETEST]: [DEFECT_STATUS.VERIFIED, DEFECT_STATUS.REOPENED],
  [DEFECT_STATUS.REOPENED]: [DEFECT_STATUS.OPEN, DEFECT_STATUS.ASSIGNED],
  [DEFECT_STATUS.VERIFIED]: [DEFECT_STATUS.CLOSED],
  [DEFECT_STATUS.REJECTED]: [DEFECT_STATUS.CLOSED, DEFECT_STATUS.REOPENED],
  [DEFECT_STATUS.DEFERRED]: [DEFECT_STATUS.ASSIGNED],
  [DEFECT_STATUS.DUPLICATE]: [DEFECT_STATUS.CLOSED],
  [DEFECT_STATUS.CLOSED]: [DEFECT_STATUS.REOPENED] // Jika regresi kambuh di masa depan
};

class Defect {
  constructor({ id, title, severity, priority, stepsToReproduce, environment, reporter }) {
    this.id = id;
    this.title = title;
    this.severity = severity; // S1-Critical, S2-Major, S3-Minor, S4-Trivial
    this.priority = priority; // P1-Blocker, P2-High, P3-Medium, P4-Low
    this.stepsToReproduce = stepsToReproduce || [];
    this.environment = environment;
    this.reporter = reporter;
    this.assignee = null;
    this.status = DEFECT_STATUS.NEW;
    this.history = [
      { timestamp: new Date().toISOString(), from: null, to: DEFECT_STATUS.NEW, actor: reporter, note: "Bug created" }
    ];
  }

  transition(toStatus, actor, role, note = "") {
    // Validasi aturan transisi
    const allowedTargets = VALID_TRANSITIONS[this.status] || [];
    if (!allowedTargets.includes(toStatus)) {
      throw new Error(
        `[ILLEGAL_STATE_TRANSITION] Tidak dapat mengubah status bug ${this.id} dari [${this.status}] ke [${toStatus}]. Alur yang diizinkan: [${allowedTargets.join(", ")}]`
      );
    }

    // Role-based authorization check
    if (toStatus === DEFECT_STATUS.CLOSED && role !== "QA") {
      throw new Error(`[UNAUTHORIZED] Hanya role QA yang berhak menutup (CLOSE) tiket bug.`);
    }

    if (toStatus === DEFECT_STATUS.FIXED && role !== "DEVELOPER") {
      throw new Error(`[UNAUTHORIZED] Hanya role DEVELOPER yang dapat menandai bug sebagai FIXED.`);
    }

    const previousStatus = this.status;
    this.status = toStatus;
    this.history.push({
      timestamp: new Date().toISOString(),
      from: previousStatus,
      to: toStatus,
      actor,
      role,
      note
    });

    console.log(
      `  ${ANSI.cyan}[DEFECT ${this.id}]${ANSI.reset} ${previousStatus} ➔ ${ANSI.bold}${toStatus}${ANSI.reset} (By: ${actor} [${role}]) ${note ? `"${note}"` : ""}`
    );
  }
}

// ==========================================
// 2. DEFECT REGISTRY & METRICS CALCULATOR
// ==========================================
class DefectRegistry {
  constructor() {
    this.defects = new Map();
  }

  addDefect(defect) {
    this.defects.set(defect.id, defect);
  }

  getDefect(id) {
    return this.defects.get(id);
  }

  calculateDRE(internalBugsCount, externalProductionLeaksCount) {
    const totalBugs = internalBugsCount + externalProductionLeaksCount;
    if (totalBugs === 0) return 100;
    const dre = (internalBugsCount / totalBugs) * 100;
    return Number(dre.toFixed(2));
  }

  calculateDefectDensity(defectCount, totalKLOC) {
    if (totalKLOC <= 0) return 0;
    return Number((defectCount / totalKLOC).toFixed(2));
  }

  getSummary() {
    const total = this.defects.size;
    const byStatus = {};
    const bySeverity = { S1: 0, S2: 0, S3: 0, S4: 0 };

    for (const defect of this.defects.values()) {
      byStatus[defect.status] = (byStatus[defect.status] || 0) + 1;
      const sevCode = defect.severity.substring(0, 2);
      if (bySeverity[sevCode] !== undefined) bySeverity[sevCode]++;
    }

    return { total, byStatus, bySeverity };
  }
}

// ==========================================
// 3. SIMULASI DAN DEMO HANDS-ON
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║      STLC BUG LIFECYCLE & QA METRICS SIMULATION RUNNER        ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  const registry = new DefectRegistry();

  console.log(`\n${ANSI.bold}${ANSI.yellow}1. SIMULASI NORMAL FLOW: Bug Lolos Uji Perbaikan (Happy Path)${ANSI.reset}`);
  const bug1 = new Defect({
    id: "BUG-101",
    title: "Checkout 500 saat memilih metode transfer BCA Virtual Account",
    severity: "S1-Critical",
    priority: "P1-Blocker",
    stepsToReproduce: [
      "1. Tambah item ke cart",
      "2. Pilih opsi checkout BCA VA",
      "3. Klik Bayar Sekarang"
    ],
    environment: "Staging v2.4.1",
    reporter: "Sarah (QA)"
  });
  registry.addDefect(bug1);

  // Alur transisi status
  bug1.transition(DEFECT_STATUS.ASSIGNED, "Alex (Tech Lead)", "LEAD", "Ditugaskan ke Dimas Backend");
  bug1.transition(DEFECT_STATUS.OPEN, "Dimas (Dev)", "DEVELOPER", "Mereproduksi di branch local fix/bca-va");
  bug1.transition(DEFECT_STATUS.FIXED, "Dimas (Dev)", "DEVELOPER", "PR #412 di-merge: null-check pada va_number");
  bug1.transition(DEFECT_STATUS.PENDING_RETEST, "CI/CD Pipeline", "DEVOPS", "Deploy build v2.4.2-rc1 ke Staging");
  bug1.transition(DEFECT_STATUS.RETEST, "Sarah (QA)", "QA", "Menguji kembali pembayaran BCA VA di Staging");
  bug1.transition(DEFECT_STATUS.VERIFIED, "Sarah (QA)", "QA", "Transaksi sukses, nomor VA ter-generate normal");
  bug1.transition(DEFECT_STATUS.CLOSED, "Sarah (QA)", "QA", "Tiket ditutup dengan sukses");

  console.log(`\n${ANSI.bold}${ANSI.yellow}2. SIMULASI RE-OPEN FLOW: Perbaikan Gagal Saat Retest (Reopen Path)${ANSI.reset}`);
  const bug2 = new Defect({
    id: "BUG-102",
    title: "Saldo voucher diskon tidak terpotong saat multi-item",
    severity: "S2-Major",
    priority: "P2-High",
    stepsToReproduce: ["1. Cart 2 item", "2. Masukkan voucher DISKON10"],
    environment: "Staging v2.4.1",
    reporter: "Andi (QA)"
  });
  registry.addDefect(bug2);

  bug2.transition(DEFECT_STATUS.ASSIGNED, "Alex (Tech Lead)", "LEAD");
  bug2.transition(DEFECT_STATUS.OPEN, "Rian (Dev)", "DEVELOPER");
  bug2.transition(DEFECT_STATUS.FIXED, "Rian (Dev)", "DEVELOPER", "Mengubah logika subtotal");
  bug2.transition(DEFECT_STATUS.PENDING_RETEST, "CI/CD Pipeline", "DEVOPS");
  bug2.transition(DEFECT_STATUS.RETEST, "Andi (QA)", "QA", "Retest skenario diskon multi-item");
  bug2.transition(DEFECT_STATUS.REOPENED, "Andi (QA)", "QA", "Perhitungan masih salah jika item berjumlah genap!");
  bug2.transition(DEFECT_STATUS.OPEN, "Rian (Dev)", "DEVELOPER", "Membongkar ulang perbaikan");

  console.log(`\n${ANSI.bold}${ANSI.yellow}3. SIMULASI ATURAN KEAMANAN STATE TRANSITION (Negative Test)${ANSI.reset}`);
  try {
    console.log("  [Attempt] Developer mencoba langsung memindahkan status dari FIXED ke CLOSED:");
    bug2.transition(DEFECT_STATUS.CLOSED, "Rian (Dev)", "DEVELOPER", "Tutup saja, di laptop saya aman");
  } catch (err) {
    console.log(`  ${ANSI.red}✓ DITANGKAP (Expected Security Block): ${err.message}${ANSI.reset}`);
  }

  console.log(`\n${ANSI.bold}${ANSI.yellow}4. KALKULATOR METRIK KUALITAS QA (Defect Metrics)${ANSI.reset}`);
  const internalBugs = 45;      // Bug ditemukan selama fase STLC internal
  const prodLeaks = 3;          // Bug yang dilaporkan oleh user di production
  const codebaseKLOC = 25.5;    // 25.500 baris kode

  const dre = registry.calculateDRE(internalBugs, prodLeaks);
  const density = registry.calculateDefectDensity(internalBugs + prodLeaks, codebaseKLOC);

  console.log(`  Internal QA Defects  : ${ANSI.bold}${internalBugs}${ANSI.reset}`);
  console.log(`  Production Leakage   : ${ANSI.bold}${prodLeaks}${ANSI.reset}`);
  console.log(`  Defect Removal Eff.  : ${ANSI.bold}${dre >= 90 ? ANSI.green : ANSI.red}${dre}%${ANSI.reset} (Standard: >= 90%)`);
  console.log(`  Total Codebase Size  : ${codebaseKLOC} KLOC`);
  console.log(`  Defect Density       : ${ANSI.bold}${density} defects/KLOC${ANSI.reset}`);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== SUMMARY DEFECT REGISTRY ===${ANSI.reset}`);
  console.log(JSON.stringify(registry.getSummary(), null, 2));
  console.log(`\n${ANSI.green}✓ Defect State Machine & QA Metrics Lab executed successfully!${ANSI.reset}\n`);
}

main();
