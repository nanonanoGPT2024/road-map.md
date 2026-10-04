/**
 * SIMULATOR: BACKEND TESTING ENGINE, TESTCONTAINERS LIFECYCLE & PACT CONTRACT VERIFIER
 * Modul 01: Piramida Testing, Testcontainers, & Contract Testing (Pact)
 *
 * Mendemonstrasikan:
 * 1. Framework Test Runner murni dengan siklus hidup describe, test, dan assertion engine.
 * 2. Unit Testing domain bisnis (kalkulasi diskon & pajak).
 * 3. Integration Testing mensimulasikan Testcontainers dengan isolasi transaksi rollback.
 * 4. Consumer-Driven Contract Testing (Pact): Verifikasi kompatibilitas schema API.
 *
 * Jalankan: node backend_testing_framework_sim.js
 */

// =========================================================================
// BAGIAN 1: TEST RUNNER & ASSERTION ENGINE MURNI
// =========================================================================

class TestRunner {
  constructor() {
    this.suites = [];
    this.totalPassed = 0;
    this.totalFailed = 0;
  }

  describe(suiteName, fn) {
    const currentSuite = { name: suiteName, tests: [] };
    this.suites.push(currentSuite);
    fn(currentSuite);
  }

  test(suite, testName, testFn) {
    suite.tests.push({ name: testName, fn: testFn });
  }

  async runAll() {
    console.log('='.repeat(75));
    console.log('MEMULAI EKSEKUSI PENGUJIAN BACKEND (TEST RUNNER ENGINE)');
    console.log('='.repeat(75));

    for (const suite of this.suites) {
      console.log(`\n📦 SUITE: ${suite.name}`);
      for (const t of suite.tests) {
        try {
          await t.fn();
          this.totalPassed++;
          console.log(`  ✅ PASSED : ${t.name}`);
        } catch (err) {
          this.totalFailed++;
          console.log(`  ❌ FAILED : ${t.name}`);
          console.log(`     Error   : ${err.message}`);
        }
      }
    }

    console.log('\n' + '='.repeat(75));
    console.log(`HASIL AKHIR: ${this.totalPassed} Passed | ${this.totalFailed} Failed`);
    console.log('='.repeat(75));
  }
}

function expect(actual) {
  return {
    toBe: (expected) => {
      if (actual !== expected) {
        throw new Error(`Ekspektasi ${expected}, namun didapatkan ${actual}`);
      }
    },
    toEqual: (expected) => {
      const a = JSON.stringify(actual);
      const b = JSON.stringify(expected);
      if (a !== b) {
        throw new Error(`Ekspektasi objek ${b}, namun didapatkan ${a}`);
      }
    },
    toThrow: (errorPattern) => {
      let threw = false;
      let thrownError = null;
      try {
        actual();
      } catch (e) {
        threw = true;
        thrownError = e;
      }
      if (!threw) {
        throw new Error('Fungsi diekspektasikan melempar error, namun tidak terjadi error.');
      }
      if (errorPattern && !thrownError.message.includes(errorPattern)) {
        throw new Error(`Pesan error "${thrownError.message}" tidak memuat pola "${errorPattern}"`);
      }
    }
  };
}

// =========================================================================
// BAGIAN 2: UNIT TESTING SUITE (DOMAIN BISNIS)
// =========================================================================

class PriceCalculator {
  static calculateFinalPrice(basePrice, discountPercent, taxRate = 0.11) {
    if (basePrice < 0) throw new Error('Harga dasar tidak boleh negatif');
    if (discountPercent < 0 || discountPercent > 100) throw new Error('Persentase diskon tidak valid');

    const discountedPrice = basePrice * (1 - discountPercent / 100);
    const taxAmount = discountedPrice * taxRate;
    return Math.round(discountedPrice + taxAmount);
  }
}

// =========================================================================
// BAGIAN 3: INTEGRATION TESTING (SIMULASI TESTCONTAINERS DB DENGAN ROLLBACK)
// =========================================================================

class EphemeralTestDatabase {
  constructor() {
    this.users = new Map(); // id -> user
  }

  // Simulasi query INSERT dengan UNIQUE constraint check
  insertUser(id, email, balance) {
    for (const [_, user] of this.users) {
      if (user.email === email) {
        throw new Error(`duplicate key value violates unique constraint "users_email_key"`);
      }
    }
    this.users.set(id, { id, email, balance });
    return this.users.get(id);
  }

  // Simulasi pembersihan data antar test case (Transaction Rollback)
  clear() {
    this.users.clear();
  }
}

// =========================================================================
// BAGIAN 4: CONTRACT TESTING (SIMULASI PACT CONSUMER-PROVIDER VERIFICATION)
// =========================================================================

class ContractVerifier {
  static verifyContract(contract, providerApi) {
    const { request, expectedResponse } = contract;
    const actualResponse = providerApi(request);

    // 1. Verifikasi HTTP Status Code
    if (actualResponse.status !== expectedResponse.status) {
      throw new Error(`Contract Violation: Ekspektasi status ${expectedResponse.status}, dapat ${actualResponse.status}`);
    }

    // 2. Verifikasi Keberadaan dan Tipe Field Skema JSON
    for (const [field, expectedType] of Object.entries(expectedResponse.bodySchema)) {
      if (!(field in actualResponse.body)) {
        throw new Error(`Contract Violation: Provider tidak menyediakan field wajib "${field}"`);
      }
      if (typeof actualResponse.body[field] !== expectedType) {
        throw new Error(`Contract Violation: Field "${field}" bertipe ${typeof actualResponse.body[field]}, butuh ${expectedType}`);
      }
    }

    return true;
  }
}

// =========================================================================
// BAGIAN 5: DEFINISI & EKSEKUSI SELURUH TEST SUITES
// =========================================================================

const runner = new TestRunner();

// SUITE 1: UNIT TESTS
runner.describe('Unit Tests: PriceCalculator Domain Logic', (suite) => {
  runner.test(suite, 'Harus menghitung harga akhir dengan PPN 11% secara presisi', () => {
    // 100.000 diskon 10% = 90.000 + PPN 11% (9.900) = 99.900
    const finalPrice = PriceCalculator.calculateFinalPrice(100000, 10, 0.11);
    expect(finalPrice).toBe(99900);
  });

  runner.test(suite, 'Harus melempar error jika nilai dasar harga negatif', () => {
    expect(() => {
      PriceCalculator.calculateFinalPrice(-5000, 10);
    }).toThrow('Harga dasar tidak boleh negatif');
  });

  runner.test(suite, 'Harus melempar error jika diskon melampaui 100%', () => {
    expect(() => {
      PriceCalculator.calculateFinalPrice(100000, 150);
    }).toThrow('Persentase diskon tidak valid');
  });
});

// SUITE 2: INTEGRATION TESTS DENGAN DB EPHEMERAL
runner.describe('Integration Tests: Ephemeral Database Isolation & Constraints', (suite) => {
  const db = new EphemeralTestDatabase();

  runner.test(suite, 'Harus berhasil menyimpan user baru ke database', () => {
    db.clear();
    const user = db.insertUser(1, 'budi@corp.com', 500000);
    expect(user.email).toBe('budi@corp.com');
  });

  runner.test(suite, 'Harus menolak duplikasi email sesuai UNIQUE constraint database', () => {
    db.clear();
    db.insertUser(1, 'andi@corp.com', 100000);

    expect(() => {
      db.insertUser(2, 'andi@corp.com', 200000);
    }).toThrow('violates unique constraint');
  });
});

// SUITE 3: CONSUMER-DRIVEN CONTRACT TESTING (PACT)
runner.describe('Contract Testing: OrderService (Consumer) vs PaymentService (Provider)', (suite) => {
  // Kontrak yang didefinisikan oleh OrderService:
  const paymentContract = {
    consumer: 'OrderService',
    provider: 'PaymentService',
    request: { endpoint: '/api/v1/charges', method: 'POST', amount: 50000 },
    expectedResponse: {
      status: 200,
      bodySchema: {
        chargeId: 'string',
        status: 'string',
        authorizedAmount: 'number'
      }
    }
  };

  runner.test(suite, 'Provider Sah (Sesuai Kontrak) harus lulus verifikasi Pact', () => {
    const validProviderApi = (req) => ({
      status: 200,
      body: {
        chargeId: 'CHG-998812',
        status: 'SUCCESS',
        authorizedAmount: req.amount
      }
    });

    const isConformant = ContractVerifier.verifyContract(paymentContract, validProviderApi);
    expect(isConformant).toBe(true);
  });

  runner.test(suite, 'Provider Cacat (Breaking Change: field diubah menjadi "id") harus terdeteksi gagal!', () => {
    // Provider mengganti field "chargeId" menjadi "id" tanpa koordinasi (Breaking Change!)
    const breakingProviderApi = (req) => ({
      status: 200,
      body: {
        id: 'CHG-998812', // Cacat: seharusnya "chargeId"
        status: 'SUCCESS',
        authorizedAmount: req.amount
      }
    });

    expect(() => {
      ContractVerifier.verifyContract(paymentContract, breakingProviderApi);
    }).toThrow('Provider tidak menyediakan field wajib "chargeId"');
  });
});

runner.runAll();
