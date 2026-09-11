/**
 * Hands-on M01: Testing Fundamentals, Verification vs Validation & Custom Assertion Engine
 * 
 * Demonstrasi prinsip dasar Software Testing:
 * 1. Verification (Static/Structure) vs Validation (Dynamic/Business intent)
 * 2. 7 Prinsip Testing (Defect clustering, Pesticide paradox, dll.)
 * 3. Mini Assertion & Test Runner Engine zero-dependency
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
// 1. MINI ASSERTION ENGINE (Core Testing Primitive)
// ==========================================
class AssertionError extends Error {
  constructor(message, expected, actual) {
    super(message);
    this.name = "AssertionError";
    this.expected = expected;
    this.actual = actual;
  }
}

const assert = {
  strictEqual(actual, expected, message) {
    if (actual !== expected) {
      throw new AssertionError(
        message || `Strict equality failed: Expected [${expected}] but got [${actual}]`,
        expected,
        actual
      );
    }
  },

  deepEqual(actual, expected, message) {
    const actualStr = JSON.stringify(actual);
    const expectedStr = JSON.stringify(expected);
    if (actualStr !== expectedStr) {
      throw new AssertionError(
        message || `Deep equality mismatch:\n  Expected: ${expectedStr}\n  Actual:   ${actualStr}`,
        expected,
        actual
      );
    }
  },

  isTrue(value, message) {
    if (value !== true) {
      throw new AssertionError(message || `Expected true, got [${value}]`, true, value);
    }
  },

  throws(fn, expectedErrorType, message) {
    let threw = false;
    let thrownErr = null;
    try {
      fn();
    } catch (err) {
      threw = true;
      thrownErr = err;
      if (expectedErrorType && !(err instanceof expectedErrorType)) {
        throw new AssertionError(
          message || `Expected error of type ${expectedErrorType.name}, but caught ${err.name}: ${err.message}`,
          expectedErrorType.name,
          err.name
        );
      }
    }
    if (!threw) {
      throw new AssertionError(message || "Expected function to throw an error, but it passed silently", true, false);
    }
  },

  withinRange(actual, min, max, message) {
    if (actual < min || actual > max) {
      throw new AssertionError(
        message || `Value [${actual}] out of acceptable range [${min} - ${max}]`,
        `${min} <= x <= ${max}`,
        actual
      );
    }
  }
};

// ==========================================
// 2. MINI TEST RUNNER
// ==========================================
class TestSuite {
  constructor(name) {
    this.name = name;
    this.tests = [];
    this.passed = 0;
    this.failed = 0;
  }

  test(description, fn) {
    this.tests.push({ description, fn });
  }

  async run() {
    console.log(`\n${ANSI.bold}${ANSI.cyan}=== RUNNING SUITE: ${this.name} ===${ANSI.reset}`);
    const startTime = Date.now();

    for (const t of this.tests) {
      const testStart = Date.now();
      try {
        await t.fn();
        const duration = Date.now() - testStart;
        console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} ${t.description} ${ANSI.dim}(${duration}ms)${ANSI.reset}`);
        this.passed++;
      } catch (err) {
        const duration = Date.now() - testStart;
        console.log(`  ${ANSI.red}✗ FAIL${ANSI.reset} ${t.description} ${ANSI.dim}(${duration}ms)${ANSI.reset}`);
        console.log(`    ${ANSI.red}Error:${ANSI.reset} ${err.message}`);
        if (err.expected !== undefined && err.actual !== undefined) {
          console.log(`    ${ANSI.dim}Expected:${ANSI.reset} ${JSON.stringify(err.expected)}`);
          console.log(`    ${ANSI.dim}Actual:  ${ANSI.reset} ${JSON.stringify(err.actual)}`);
        }
        this.failed++;
      }
    }

    const totalDuration = Date.now() - startTime;
    console.log(`${ANSI.dim}--------------------------------------------------${ANSI.reset}`);
    console.log(
      `Total: ${this.tests.length} | ` +
      `${ANSI.green}Passed: ${this.passed}${ANSI.reset} | ` +
      `${this.failed > 0 ? ANSI.red : ANSI.green}Failed: ${this.failed}${ANSI.reset} | ` +
      `Duration: ${totalDuration}ms\n`
    );

    return { total: this.tests.length, passed: this.passed, failed: this.failed };
  }
}

// ==========================================
// 3. TARGET SYSTEM UNDER TEST (SUT)
// E-Commerce Cart & Discount Calculator
// ==========================================
class OrderService {
  constructor() {
    this.orders = new Map();
  }

  // Pure logic for Verification testing
  calculateSubtotal(items) {
    if (!Array.isArray(items)) throw new TypeError("Items must be an array");
    return items.reduce((sum, item) => {
      if (item.price < 0 || item.qty <= 0) {
        throw new RangeError("Invalid item price or quantity");
      }
      return sum + (item.price * item.qty);
    }, 0);
  }

  // Business logic with validation constraints
  applyVoucher(subtotal, voucherCode) {
    if (!voucherCode) return { discount: 0, finalPrice: subtotal };

    const validVouchers = {
      "DISKON10": { type: "percentage", value: 10, minSpend: 50000, maxCap: 20000 },
      "FLAT50K": { type: "fixed", value: 50000, minSpend: 100000, maxCap: 50000 }
    };

    const voucher = validVouchers[voucherCode.toUpperCase()];
    if (!voucher) {
      throw new Error("VOUCHER_INVALID: Kode voucher tidak ditemukan");
    }

    if (subtotal < voucher.minSpend) {
      throw new Error(`VOUCHER_MIN_SPEND: Belanja minimal Rp ${voucher.minSpend.toLocaleString('id-ID')}`);
    }

    let discount = 0;
    if (voucher.type === "percentage") {
      discount = Math.min((subtotal * voucher.value) / 100, voucher.maxCap);
    } else {
      discount = voucher.value;
    }

    const finalPrice = Math.max(0, subtotal - discount);
    return { discount, finalPrice, voucherCode: voucherCode.toUpperCase() };
  }
}

// ==========================================
// 4. TEST EXECUTION
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║   SOFTWARE TESTING FUNDAMENTALS & ASSERTION LAB RUNNER         ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // SUITE 1: Verification (Are we building the product right? - Math & Specs)
  const verificationSuite = new TestSuite("1. Verification: Order Calculation Spec & Constraints");
  const sut = new OrderService();

  verificationSuite.test("Menghitung subtotal dengan item valid secara tepat", () => {
    const items = [
      { id: "p1", name: "Keyboard Mechanical", price: 500000, qty: 1 },
      { id: "p2", name: "Keycaps Set", price: 150000, qty: 2 }
    ];
    const subtotal = sut.calculateSubtotal(items);
    assert.strictEqual(subtotal, 800000, "Subtotal harus 500k + (150k * 2) = 800k");
  });

  verificationSuite.test("Melempar TypeError bila input items bukan array", () => {
    assert.throws(() => sut.calculateSubtotal("bukan-array"), TypeError);
  });

  verificationSuite.test("Melempar RangeError bila item memiliki harga negatif", () => {
    assert.throws(() => {
      sut.calculateSubtotal([{ id: "p1", price: -10000, qty: 1 }]);
    }, RangeError);
  });

  await verificationSuite.run();

  // SUITE 2: Validation (Are we building the right product? - Business Rules & User Experience)
  const validationSuite = new TestSuite("2. Validation: Business Rules & Voucher Constraints");

  validationSuite.test("Voucher DISKON10 berhasil dipotong dengan batas maksimal (cap)", () => {
    const subtotal = 500000;
    // 10% dari 500.000 = 50.000, tapi maxCap = 20.000
    const result = sut.applyVoucher(subtotal, "DISKON10");
    assert.deepEqual(result, {
      discount: 20000,
      finalPrice: 480000,
      voucherCode: "DISKON10"
    });
  });

  validationSuite.test("Voucher ditolak bila belanja di bawah minimum spend (Business Error)", () => {
    const subtotal = 30000; // Min spend DISKON10 adalah 50.000
    assert.throws(() => {
      sut.applyVoucher(subtotal, "DISKON10");
    }, Error);
  });

  validationSuite.test("Voucher tidak valid melempar error VOUCHER_INVALID", () => {
    assert.throws(() => {
      sut.applyVoucher(100000, "KODE_PALSU");
    }, Error);
  });

  await validationSuite.run();

  // SUITE 3: Demonstrasi Defect Clustering & Pesticide Paradox
  console.log(`${ANSI.bold}${ANSI.cyan}=== 3. ANALISIS 7 PRINSIP TESTING ===${ANSI.reset}`);
  console.log(`${ANSI.yellow}[Prinsip: Defect Clustering]${ANSI.reset} 80% bug biasanya terkonsentrasi pada modul diskon/pricing yang memiliki banyak branch logika.`);
  console.log(`${ANSI.yellow}[Prinsip: Pesticide Paradox]${ANSI.reset} Jika hanya menjalankan 3 tes voucher di atas berulang kali, bug kombinasi 'FLAT50K + Subtotal Rp 49.999' tidak akan pernah terdeteksi tanpa variasi test case baru.`);
  console.log(`${ANSI.yellow}[Prinsip: Absence of Errors Fallacy]${ANSI.reset} Semua tes kalkulasi harga PASS 100%, namun jika pengguna tidak bisa input kode voucher karena tombol UI tertutup keyboard mobile, sistem tetap dianggap GAGAL bagi bisnis.`);
  console.log(`\n${ANSI.green}✓ All Fundamental QA Lab Demonstrations executed successfully!${ANSI.reset}\n`);
}

main().catch(console.error);
