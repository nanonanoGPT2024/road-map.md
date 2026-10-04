/**
 * Hands-on M01: Testing Pyramid Runner & Smoke/Sanity Gatekeeper Simulator
 * 
 * Demonstrasi:
 * 1. Unit Testing Layer (Cepat, terisolasi, ratusan test dalam milidetik)
 * 2. Integration Testing Layer (Service + Mock Database + Stubs)
 * 3. System / E2E Testing Layer (Simulasi alur pengguna lengkap)
 * 4. Smoke Test Gatekeeper (Build rejection jika health check kritis gagal)
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
// 1. APPLICATION LOGIC & LAYERS
// ==========================================

// Layer 1: Pure Functions (Unit Target)
const MathUtils = {
  calculateTax(amount, ratePercentage) {
    if (amount < 0 || ratePercentage < 0) throw new RangeError("Nilai tidak boleh negatif");
    return Math.round((amount * ratePercentage) / 100);
  },
  validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }
};

// Layer 2: Integration Components with Stubs
class MockDatabase {
  constructor() {
    this.users = new Map();
    this.wallets = new Map();
  }
  async findUser(id) {
    return this.users.get(id) || null;
  }
  async saveUser(user) {
    this.users.set(user.id, user);
  }
  async updateBalance(userId, delta) {
    const current = this.wallets.get(userId) || 0;
    if (current + delta < 0) throw new Error("INSUFFICIENT_BALANCE");
    this.wallets.set(userId, current + delta);
    return this.wallets.get(userId);
  }
}

// Payment Gateway Stub
class PaymentGatewayStub {
  constructor() {
    this.shouldFail = false;
  }
  async charge(amount, token) {
    if (this.shouldFail) throw new Error("GATEWAY_TIMEOUT");
    return { status: "SUCCESS", txId: "TX_" + Math.random().toString(36).substring(2, 9), amount };
  }
}

// Service Layer
class BillingService {
  constructor(db, paymentGateway) {
    this.db = db;
    this.gateway = paymentGateway;
  }

  async topUpAndPay(userId, topUpAmount, payAmount) {
    // 1. Topup via gateway
    const chargeResult = await this.gateway.charge(topUpAmount, "tok_valid");
    if (chargeResult.status !== "SUCCESS") throw new Error("Top up failed");

    // 2. Update DB
    await this.db.updateBalance(userId, topUpAmount);

    // 3. Deduct payment
    const remaining = await this.db.updateBalance(userId, -payAmount);
    return { success: true, remainingBalance: remaining };
  }
}

// ==========================================
// 2. TEST EXECUTION RUNNERS
// ==========================================
async function runUnitTests() {
  console.log(`\n${ANSI.bold}${ANSI.cyan}[1/3] UNIT TESTING LAYER (Mike Cohn Base: Fast & Isolated)${ANSI.reset}`);
  const start = Date.now();
  let passed = 0;

  // Test 1: Math calculation
  if (MathUtils.calculateTax(100000, 11) === 11000) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} MathUtils.calculateTax(100000, 11) === 11000`);
    passed++;
  }

  // Test 2: Negative check
  try {
    MathUtils.calculateTax(-500, 10);
  } catch (e) {
    if (e instanceof RangeError) {
      console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} MathUtils.calculateTax throws RangeError on negative input`);
      passed++;
    }
  }

  // Test 3: Email regex
  if (MathUtils.validateEmail("user@corp.co.id") && !MathUtils.validateEmail("user-tanpa-domain")) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} MathUtils.validateEmail correctly distinguishes valid emails`);
    passed++;
  }

  const duration = Date.now() - start;
  console.log(`  ${ANSI.dim}Unit tests completed: ${passed}/3 passed in ${duration}ms${ANSI.reset}`);
}

async function runIntegrationTests() {
  console.log(`\n${ANSI.bold}${ANSI.cyan}[2/3] INTEGRATION TESTING LAYER (Service + DB + Gateway Stub)${ANSI.reset}`);
  const start = Date.now();
  let passed = 0;

  const db = new MockDatabase();
  const gateway = new PaymentGatewayStub();
  const service = new BillingService(db, gateway);

  // Test 1: Successful top-up and deduction
  const result = await service.topUpAndPay("user_1", 100000, 40000);
  if (result.success && result.remainingBalance === 60000) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} TopUp & Pay transaction coordinated correctly across DB and Stub`);
    passed++;
  }

  // Test 2: Gateway failure handling
  gateway.shouldFail = true;
  try {
    await service.topUpAndPay("user_1", 50000, 20000);
  } catch (e) {
    if (e.message === "GATEWAY_TIMEOUT") {
      console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Service gracefully rolls back when Payment Gateway Stub throws TIMEOUT`);
      passed++;
    }
  }

  const duration = Date.now() - start;
  console.log(`  ${ANSI.dim}Integration tests completed: ${passed}/2 passed in ${duration}ms${ANSI.reset}`);
}

async function runSystemE2ETests() {
  console.log(`\n${ANSI.bold}${ANSI.cyan}[3/3] SYSTEM / E2E TESTING LAYER (Full Customer Journey Simulation)${ANSI.reset}`);
  const start = Date.now();

  console.log(`  ${ANSI.dim}→ Step 1: User navigates to web portal... OK${ANSI.reset}`);
  console.log(`  ${ANSI.dim}→ Step 2: User authenticates with MFA token... OK${ANSI.reset}`);
  console.log(`  ${ANSI.dim}→ Step 3: User initiates checkout and generates receipt... OK${ANSI.reset}`);
  console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} E2E User Journey: Onboarding -> Payment -> Order Receipt Complete`);

  const duration = Date.now() - start;
  console.log(`  ${ANSI.dim}System E2E tests completed in ${duration}ms${ANSI.reset}`);
}

async function runSmokeTestGatekeeper(simulateFailure = false) {
  console.log(`\n${ANSI.bold}${ANSI.yellow}=== SMOKE TEST GATEKEEPER (Build Verification) ===${ANSI.reset}`);
  console.log("Memeriksa 3 titik kritis kesehatan build:");

  const check1 = true; // API Health
  const check2 = !simulateFailure; // DB Connection
  const check3 = true; // Auth Service

  console.log(`  1. API Gateway /healthz         : ${check1 ? ANSI.green + "OK" : ANSI.red + "FAIL"}${ANSI.reset}`);
  console.log(`  2. Core Database Pool Connection: ${check2 ? ANSI.green + "OK" : ANSI.red + "FAIL"}${ANSI.reset}`);
  console.log(`  3. Identity Provider (IdP) Ping : ${check3 ? ANSI.green + "OK" : ANSI.red + "FAIL"}${ANSI.reset}`);

  if (!check1 || !check2 || !check3) {
    console.log(`\n${ANSI.red}${ANSI.bold}🚨 SMOKE TEST FAILED! BUILD REJECTED BY QA GATEKEEPER.${ANSI.reset}`);
    console.log(`${ANSI.red}Menghentikan eksekusi test suite regresi untuk menghemat resource CI.${ANSI.reset}\n`);
    return false;
  }

  console.log(`\n${ANSI.green}${ANSI.bold}✓ SMOKE TEST PASSED! BUILD ACCEPTED FOR DEEP REGRESSION TESTING.${ANSI.reset}`);
  return true;
}

// ==========================================
// 3. MAIN RUNNER
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║       TESTING PYRAMID & QUALITY GATEWAY LAB SIMULATOR         ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. Smoke test gatekeeper
  const isHealthy = await runSmokeTestGatekeeper(false);
  if (!isHealthy) return;

  // 2. Testing Pyramid Execution
  await runUnitTests();
  await runIntegrationTests();
  await runSystemE2ETests();

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== DISTRIBUSI EFISIENSI PIRAMIDA PENGUJIAN ===${ANSI.reset}`);
  console.log(`Unit Tests        : Terbanyak, Kecepatan ~1ms, Biaya Rendah (Pondasi Kokoh)`);
  console.log(`Integration Tests : Sedang, Menguji Kontrak Data & Service Stubs`);
  console.log(`System E2E Tests  : Paling Sedikit, Menguji Golden User Journey`);
  console.log(`\n${ANSI.green}✓ Testing Pyramid Lab executed successfully!${ANSI.reset}\n`);
}

main().catch(console.error);
