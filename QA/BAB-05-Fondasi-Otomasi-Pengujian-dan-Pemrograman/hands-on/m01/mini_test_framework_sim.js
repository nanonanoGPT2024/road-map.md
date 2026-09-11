/**
 * Hands-on M01: Micro Test Framework & Asynchronous Assertion Engine Simulator
 * 
 * Mengimplementasikan arsitektur test runner mandiri mirip Jest/Playwright Test Runner:
 * 1. DSL: describe(), test(), it()
 * 2. Lifecycle Hooks: beforeAll(), beforeEach(), afterEach(), afterAll()
 * 3. Matchers: expect().toBe(), .toEqual(), .toBeGreaterThan(), .toThrow()
 * 4. Eksekusi Asinkron murni (Async / Await support)
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
// 1. ASSERTION ENGINE (Matchers)
// ==========================================
class Expectation {
  constructor(actual) {
    this.actual = actual;
  }

  toBe(expected) {
    if (this.actual !== expected) {
      throw new Error(`Expected [${expected}] (${typeof expected}) but received [${this.actual}] (${typeof this.actual})`);
    }
  }

  toEqual(expected) {
    const actStr = JSON.stringify(this.actual);
    const expStr = JSON.stringify(expected);
    if (actStr !== expStr) {
      throw new Error(`Deep Equality Mismatch:\n    Expected: ${expStr}\n    Actual:   ${actStr}`);
    }
  }

  toBeGreaterThan(min) {
    if (this.actual <= min) {
      throw new Error(`Expected ${this.actual} to be strictly greater than ${min}`);
    }
  }

  async toThrow(expectedErrorMsg) {
    let threw = false;
    let thrownError = null;
    try {
      if (typeof this.actual === "function") {
        const res = this.actual();
        if (res instanceof Promise) await res;
      }
    } catch (err) {
      threw = true;
      thrownError = err;
    }

    if (!threw) {
      throw new Error("Expected function to throw an error, but it completed without error");
    }

    if (expectedErrorMsg && !thrownError.message.includes(expectedErrorMsg)) {
      throw new Error(`Expected error message to include "${expectedErrorMsg}", but got "${thrownError.message}"`);
    }
  }
}

function expect(actual) {
  return new Expectation(actual);
}

// ==========================================
// 2. TEST RUNNER CORE & LIFECYCLE ENGINE
// ==========================================
class TestRunner {
  constructor() {
    this.suites = [];
    this.currentSuite = null;
    this.stats = { total: 0, passed: 0, failed: 0 };
  }

  describe(name, fn) {
    const suite = {
      name,
      tests: [],
      beforeAllHooks: [],
      beforeEachHooks: [],
      afterEachHooks: [],
      afterAllHooks: []
    };
    this.suites.push(suite);
    this.currentSuite = suite;
    fn();
    this.currentSuite = null;
  }

  test(name, fn) {
    if (!this.currentSuite) throw new Error("test() must be called inside describe()");
    this.currentSuite.tests.push({ name, fn });
  }

  beforeAll(fn) {
    this.currentSuite.beforeAllHooks.push(fn);
  }

  beforeEach(fn) {
    this.currentSuite.beforeEachHooks.push(fn);
  }

  afterEach(fn) {
    this.currentSuite.afterEachHooks.push(fn);
  }

  afterAll(fn) {
    this.currentSuite.afterAllHooks.push(fn);
  }

  async run() {
    const globalStart = Date.now();
    console.log(`\n${ANSI.bold}${ANSI.cyan}================================================================${ANSI.reset}`);
    console.log(`${ANSI.bold}${ANSI.cyan}             MINI TEST FRAMEWORK EXECUTION ENGINE               ${ANSI.reset}`);
    console.log(`${ANSI.bold}${ANSI.cyan}================================================================${ANSI.reset}\n`);

    for (const suite of this.suites) {
      console.log(`${ANSI.bold}Suite: ${suite.name}${ANSI.reset}`);

      // Run beforeAll
      for (const hook of suite.beforeAllHooks) await hook();

      for (const testCase of suite.tests) {
        this.stats.total++;
        const testStart = Date.now();

        // Run beforeEach
        for (const hook of suite.beforeEachHooks) await hook();

        try {
          // Execute test (supports async/await)
          await testCase.fn();
          const duration = Date.now() - testStart;
          console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} ${testCase.name} ${ANSI.dim}(${duration}ms)${ANSI.reset}`);
          this.stats.passed++;
        } catch (err) {
          const duration = Date.now() - testStart;
          console.log(`  ${ANSI.red}✗ FAIL${ANSI.reset} ${testCase.name} ${ANSI.dim}(${duration}ms)${ANSI.reset}`);
          console.log(`    ${ANSI.red}Error: ${err.message}${ANSI.reset}`);
          this.stats.failed++;
        }

        // Run afterEach
        for (const hook of suite.afterEachHooks) await hook();
      }

      // Run afterAll
      for (const hook of suite.afterAllHooks) await hook();
      console.log("");
    }

    const totalTime = Date.now() - globalStart;
    console.log(`${ANSI.dim}----------------------------------------------------------------${ANSI.reset}`);
    console.log(
      `Suites: ${this.suites.length} | ` +
      `Tests: ${this.stats.total} | ` +
      `${ANSI.green}Passed: ${this.stats.passed}${ANSI.reset} | ` +
      `${this.stats.failed > 0 ? ANSI.red : ANSI.green}Failed: ${this.stats.failed}${ANSI.reset} | ` +
      `Time: ${totalTime}ms\n`
    );
  }
}

// Global instance
const runner = new TestRunner();
const describe = runner.describe.bind(runner);
const test = runner.test.bind(runner);
const beforeAll = runner.beforeAll.bind(runner);
const beforeEach = runner.beforeEach.bind(runner);
const afterEach = runner.afterEach.bind(runner);
const afterAll = runner.afterAll.bind(runner);

// ==========================================
// 3. SAMPLE SUT & TEST DEFINITIONS
// ==========================================

// Mock async service
const mockUserService = {
  async fetchUser(id) {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (id <= 0) reject(new Error("USER_NOT_FOUND"));
        else resolve({ id, name: "Budi Santoso", points: 150 });
      }, 30);
    });
  }
};

// Suite 1: Sync Assertions
describe("1. Sync Math & Object Assertions", () => {
  test("Menghitung penjumlahan dasar secara akurat", () => {
    expect(5 + 5).toBe(10);
  });

  test("Memverifikasi deep equality objek JSON", () => {
    const objA = { role: "QA", permissions: ["READ", "WRITE"] };
    const objB = { role: "QA", permissions: ["READ", "WRITE"] };
    expect(objA).toEqual(objB);
  });

  test("Menilai batas angka dengan toBeGreaterThan", () => {
    expect(100).toBeGreaterThan(50);
  });
});

// Suite 2: Async Promises with Lifecycle Hooks
describe("2. Asynchronous Flow & Lifecycle State Isolation", () => {
  let activeSession = null;

  beforeAll(() => {
    // console.log("    [Hook] Initializing test DB connection pool...");
  });

  beforeEach(() => {
    // Menjamin setiap test dimulai dari state baru (Isolation)
    activeSession = { user: "Tester", cart: [] };
  });

  afterEach(() => {
    // Cleanup
    activeSession = null;
  });

  test("Berhasil mengambil data pengguna asinkron dengan async/await", async () => {
    const user = await mockUserService.fetchUser(101);
    expect(user.id).toBe(101);
    expect(user.name).toBe("Budi Santoso");
    expect(user.points).toBeGreaterThan(100);
  });

  test("Menangkap penolakan error asinkron pada input ID invalid", async () => {
    await expect(async () => {
      await mockUserService.fetchUser(-1);
    }).toThrow("USER_NOT_FOUND");
  });

  test("Memverifikasi isolasi state: Keranjang belanja kosong di awal test", () => {
    expect(activeSession.cart.length).toBe(0);
    activeSession.cart.push("Item 1"); // Mutasi hanya berlaku di test ini
    expect(activeSession.cart.length).toBe(1);
  });

  test("Memverifikasi isolasi state berlanjut: Keranjang tetap 0 di test berikutnya", () => {
    // Jika beforeEach bekerja benar, cart harus kembali 0 (tidak tercemar dari test sebelumnya)
    expect(activeSession.cart.length).toBe(0);
  });
});

// ==========================================
// 4. MAIN EXECUTION
// ==========================================
async function main() {
  await runner.run();
}

main().catch(console.error);
