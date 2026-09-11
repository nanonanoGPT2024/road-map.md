/**
 * SIMULATOR: ADVANCED TYPE-LEVEL VERIFICATION & DISCRIMINATED UNIONS ENGINE
 * Modul 01: Advanced TypeScript: Generics, Conditional Types, Template Literals, & Mapped Types
 *
 * Mendemonstrasikan:
 * 1. Validasi Discriminated Unions dengan Exhaustive Checking (Pola 'never').
 * 2. Mapped Types: Rekursif Deep Freeze (Simulasi DeepReadonly<T>).
 * 3. Template Literal Types Route Matcher (Validasi Format Rute API Compile-Time).
 * 4. Runtime Type Guard Predicates (Simulasi value is T Narrowing).
 *
 * Jalankan: node advanced_typescript_meta_types_sim.js
 */

// =========================================================================
// BAGIAN 1: DISCRIMINATED UNIONS DENGAN EXHAUSTIVE CHECKING
// =========================================================================

class ExhaustiveCheckError extends Error {
  constructor(unhandledValue) {
    super(`Peringatan Tipe 'never': Variasi status tidak tertangani: ${JSON.stringify(unhandledValue)}`);
    this.name = 'ExhaustiveCheckError';
  }
}

class PaymentStateEvaluator {
  // Simulasi penanganan Discriminated Union:
  // type PaymentState =
  //   | { status: 'PENDING'; qrCodeUrl: string }
  //   | { status: 'SETTLED'; paidAmount: number; txRef: string }
  //   | { status: 'FAILED'; errorCode: string; reason: string }
  static processPaymentState(state) {
    console.log(`\nMenilai Status Transaksi: [${state.status}]...`);

    switch (state.status) {
      case 'PENDING':
        console.log(`  ⏳ [MENUNGGU PEMBAYARAN] Tampilkan QRIS: ${state.qrCodeUrl}`);
        return { ui: 'RENDER_QR', data: state.qrCodeUrl };

      case 'SETTLED':
        console.log(`  ✅ [LUNAS / BERHASIL] Ref: ${state.txRef} | Nominal: Rp ${state.paidAmount.toLocaleString('id-ID')}`);
        return { ui: 'RENDER_RECEIPT', data: state.txRef };

      case 'FAILED':
        console.log(`  ❌ [GAGAL] Kode: ${state.errorCode} | Alasan: "${state.reason}"`);
        return { ui: 'RENDER_ERROR', data: state.reason };

      default:
        // Simulasi Exhaustive Check TypeScript (assertNever(state))
        // Jika ada penambahan status baru (misal 'EXPIRED') yang belum ditangani,
        // compiler akan langsung melempar error saat kompilasi!
        throw new ExhaustiveCheckError(state);
    }
  }
}

// =========================================================================
// BAGIAN 2: MAPPED TYPES: DEEP READONLY (REKURSIF IMMUTABILITY)
// =========================================================================

class DeepReadonlyEngine {
  // Simulasi Mapped Type: type DeepReadonly<T> = { readonly [K in keyof T]: DeepReadonly<T[K]> }
  static deepFreeze(obj) {
    if (obj === null || typeof obj !== 'object') return obj;

    // Bekukan semua properti anak terlebih dahulu
    Object.keys(obj).forEach(prop => {
      const value = obj[prop];
      if (typeof value === 'object' && value !== null && !Object.isFrozen(value)) {
        this.deepFreeze(value);
      }
    });

    return Object.freeze(obj);
  }
}

// =========================================================================
// BAGIAN 3: TEMPLATE LITERAL ROUTE MATCHER SIMULATOR
// =========================================================================

class TemplateLiteralRouteValidator {
  // Simulasi tipe: `${HttpMethod} /api/${ApiVersion}/${Resource}`
  static validateEndpoint(endpointString) {
    const validMethods = ['GET', 'POST', 'PUT', 'DELETE'];
    const validVersions = ['v1', 'v2'];
    const validResources = ['users', 'orders', 'products', 'invoices'];

    // Regex mencerminkan aturan Template Literal Types
    const match = endpointString.match(/^([A-Z]+)\s\/api\/(v\d+)\/([a-z]+)$/);
    if (!match) {
      return { isValid: false, error: `Format tidak valid! Butuh '${validMethods.join('|')} /api/${validVersions.join('|')}/${validResources.join('|')}'` };
    }

    const [_, method, version, resource] = match;
    if (!validMethods.includes(method)) return { isValid: false, error: `Metode HTTP tidak diizinkan: ${method}` };
    if (!validVersions.includes(version)) return { isValid: false, error: `Versi API tidak terdaftar: ${version}` };
    if (!validResources.includes(resource)) return { isValid: false, error: `Resource tidak dikenali: ${resource}` };

    return { isValid: true, method, version, resource };
  }
}

// =========================================================================
// BAGIAN 4: RUNTIME TYPE GUARD NARROWING
// =========================================================================

class TypeNarrowingGuards {
  // Simulasi: function isApiSuccess(res: unknown): res is ApiSuccessResponse
  static isApiSuccess(res) {
    return (
      typeof res === 'object' &&
      res !== null &&
      res.success === true &&
      Array.isArray(res.data)
    );
  }
}

// =========================================================================
// BAGIAN 5: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: ADVANCED TYPESCRIPT META-TYPES & SAFETY ENGINE');
  console.log('='.repeat(75));

  // --- BAGIAN A: DISCRIMINATED UNIONS & EXHAUSTIVE CHECK ---
  console.log('\nA. Pengujian Discriminated Unions & Exhaustive Type Check:');
  console.log('-'.repeat(75));

  PaymentStateEvaluator.processPaymentState({
    status: 'PENDING',
    qrCodeUrl: 'https://qris.id/pay/TX-9988'
  });

  PaymentStateEvaluator.processPaymentState({
    status: 'SETTLED',
    paidAmount: 500000,
    txRef: 'REF-BCA-102948'
  });

  PaymentStateEvaluator.processPaymentState({
    status: 'FAILED',
    errorCode: 'INSUFFICIENT_FUNDS',
    reason: 'Saldo rekening tidak mencukupi'
  });

  // Uji kasus status tak tertangani (Exhaustive Check Trap)
  try {
    console.log('\nMenguji status asing yang tidak tertangani (Pola never):');
    PaymentStateEvaluator.processPaymentState({ status: 'REFUNDED_PARTIAL', refundAmount: 100000 });
  } catch (err) {
    console.log(`  🛡️ [EXHAUSTIVE CHECK DETECTED] ${err.message}`);
  }

  // --- BAGIAN B: DEEP READONLY MAPPED TYPE ---
  console.log('\n' + '-'.repeat(75));
  console.log('B. Pengujian DeepReadonly (Mapped Types Immutability):');
  console.log('-'.repeat(75));

  const enterpriseConfig = DeepReadonlyEngine.deepFreeze({
    appName: 'PayPulse Gateway',
    version: '3.4.0',
    security: {
      encryption: {
        algorithm: 'AES-256-GCM',
        keyRotationDays: 90
      }
    }
  });

  console.log('Mencoba memodifikasi properti bersarang enterpriseConfig.security.encryption.keyRotationDays = 30...');
  try {
    enterpriseConfig.security.encryption.keyRotationDays = 30; // Akan ditolak oleh freeze
    console.log('  Nilai saat ini: ', enterpriseConfig.security.encryption.keyRotationDays);
  } catch (e) {
    console.log('  Pengecualian mutasi tertangkap.');
  }
  console.log(`  Nilai Kunci Tetap Aman: ${enterpriseConfig.security.encryption.keyRotationDays} hari (Immutable! ✅)`);

  // --- BAGIAN C: TEMPLATE LITERAL TYPES ---
  console.log('\n' + '-'.repeat(75));
  console.log('C. Pengujian Template Literal Types Route Matcher:');
  console.log('-'.repeat(75));

  const testRoutes = [
    'GET /api/v1/orders',
    'POST /api/v2/users',
    'PATCH /api/v3/orders', // Versi v3 belum ada
    'DELETE /api/v1/unknownResource' // Resource tidak ada
  ];

  testRoutes.forEach(route => {
    const res = TemplateLiteralRouteValidator.validateEndpoint(route);
    if (res.isValid) {
      console.log(`  ✅ [VALID TYPE] "${route}" -> Method: ${res.method}, Resource: ${res.resource}`);
    } else {
      console.log(`  ❌ [TYPE ERROR] "${route}" -> ${res.error}`);
    }
  });

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Seluruh pilar Advanced TypeScript berjalan sempurna!');
  console.log('='.repeat(75));
}

main();
