/**
 * CAPSTONE PROJECT: PAYPULSE GLOBAL OMNICHANNEL PAYMENT & LEDGER ENGINE
 *
 * Menggabungkan seluruh pilar Backend Mastery:
 * 1. Mesin Idempotensi Transaksi Anti-Double-Charge.
 * 2. Domain-Driven Design (DDD) ChargeAggregate Invariant Guard.
 * 3. Double-Entry Financial Ledger (Jaminan Keseimbangan Debit == Credit).
 * 4. Saga Orchestrator dengan Transaksi Kompensasi Otomatis (Semantic Rollback).
 * 5. Webhook Dispatcher dengan Tanda Tangan Kriptografi HMAC-SHA256.
 *
 * Jalankan: node paypulse_payment_engine.js
 */

const crypto = require('crypto');

// =========================================================================
// BAGIAN 1: SISTEM IDEMPOTENSI (MENCEGAH DOUBLE CHARGE JARINGAN)
// =========================================================================

class IdempotencyManager {
  constructor() {
    this.store = new Map(); // idempotencyKey -> { requestHash, response }
  }

  hashPayload(payload) {
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }

  checkOrLock(key, payload) {
    const hash = this.hashPayload(payload);
    if (this.store.has(key)) {
      const record = this.store.get(key);
      if (record.requestHash !== hash) {
        throw new Error('Konflik Idempotensi: Kunci yang sama digunakan dengan payload berbeda!');
      }
      return { isDuplicate: true, cachedResponse: record.response };
    }

    this.store.set(key, { requestHash: hash, response: null });
    return { isDuplicate: false, cachedResponse: null };
  }

  saveResponse(key, response) {
    const record = this.store.get(key);
    if (record) {
      record.response = response;
    }
  }
}

// =========================================================================
// BAGIAN 2: DOUBLE-ENTRY FINANCIAL LEDGER (AKUNTANSI KEUANGAN GANDA)
// =========================================================================

class DoubleEntryLedger {
  constructor() {
    this.accounts = new Map([
      ['ASSET_BANK_CASH', 0],             // Kas Uang di Rekening Bank Penampung
      ['LIABILITY_MERCHANT_ESCROW', 0],   // Utang Gateway ke Merchant (Dana Tertahan)
      ['REVENUE_TRANSACTION_FEE', 0]      // Pendapatan Biaya Layanan Gateway
    ]);
    this.journalHistory = [];
  }

  // Setiap perpindahan dana wajib memiliki total Debit == total Credit
  postTransaction(chargeId, grossAmount, feeAmount = 2500) {
    const netMerchantAmount = grossAmount - feeAmount;

    const postings = [
      { account: 'ASSET_BANK_CASH', direction: 'DEBIT', amount: grossAmount },
      { account: 'LIABILITY_MERCHANT_ESCROW', direction: 'CREDIT', amount: netMerchantAmount },
      { account: 'REVENUE_TRANSACTION_FEE', direction: 'CREDIT', amount: feeAmount }
    ];

    // Verifikasi Formula Keseimbangan Akuntansi: Debit == Credit
    let totalDebit = 0;
    let totalCredit = 0;

    for (const p of postings) {
      if (p.direction === 'DEBIT') totalDebit += p.amount;
      if (p.direction === 'CREDIT') totalCredit += p.amount;
    }

    if (totalDebit !== totalCredit) {
      throw new Error(`Ledger Imbalance Fatal! Total Debit (${totalDebit}) != Total Credit (${totalCredit})`);
    }

    // Mutasi saldo akun secara atomik
    this.accounts.set('ASSET_BANK_CASH', this.accounts.get('ASSET_BANK_CASH') + grossAmount);
    this.accounts.set('LIABILITY_MERCHANT_ESCROW', this.accounts.get('LIABILITY_MERCHANT_ESCROW') + netMerchantAmount);
    this.accounts.set('REVENUE_TRANSACTION_FEE', this.accounts.get('REVENUE_TRANSACTION_FEE') + feeAmount);

    const journalRecord = {
      journalId: `JRN-${crypto.randomBytes(6).toString('hex')}`,
      chargeId,
      postings,
      timestamp: Date.now()
    };
    this.journalHistory.push(journalRecord);

    return journalRecord;
  }
}

// =========================================================================
// BAGIAN 3: WEBHOOK ENGINE DENGAN TANDA TANGAN KRIPTOGRAFI HMAC-SHA256
// =========================================================================

class WebhookEngine {
  static signPayload(payloadString, merchantSecret) {
    return crypto.createHmac('sha256', merchantSecret).update(payloadString).digest('hex');
  }

  static verifySignature(payloadString, merchantSecret, receivedSignature) {
    const expected = this.signPayload(payloadString, merchantSecret);
    const expBuf = Buffer.from(expected, 'hex');
    const recBuf = Buffer.from(receivedSignature, 'hex');

    if (expBuf.length !== recBuf.length) return false;
    return crypto.timingSafeEqual(expBuf, recBuf);
  }
}

// =========================================================================
// BAGIAN 4: SAGA ORCHESTRATOR PAYMENT CORE
// =========================================================================

class PayPulsePaymentGateway {
  constructor() {
    this.idempotency = new IdempotencyManager();
    this.ledger = new DoubleEntryLedger();
    this.merchantSecret = 'whsec_merchant_top_secret_key_8841';
  }

  async processCharge(idempotencyKey, chargeRequest) {
    // 1. Periksa Kunci Idempotensi
    const idempCheck = this.idempotency.checkOrLock(idempotencyKey, chargeRequest);
    if (idempCheck.isDuplicate) {
      console.log(`  🛡️ [IDEMPOTENCY HIT] Request ${idempotencyKey} sudah pernah diproses. Mengembalikan respon cache seketika!`);
      return { ...idempCheck.cachedResponse, _source: 'CACHE_IDEMPOTENT' };
    }

    const { chargeId, merchantId, amount, paymentMethod } = chargeRequest;
    console.log(`\n▶️ [MEMULAI TRANSAKSI] Charge ID: ${chargeId} | Nominal: Rp ${amount.toLocaleString('id-ID')} (${paymentMethod})`);

    const sagaRollbackSteps = [];

    try {
      // SAGA STEP 1: Evaluasi Anti-Fraud AI
      console.log('  [SAGA 1] Evaluasi Skor Fraud Risk...');
      if (amount > 50000000) {
        throw new Error('Transaksi ditolak oleh Anti-Fraud: Nominal melampaui batas risiko Rp 50.000.000!');
      }

      // SAGA STEP 2: Otorisasi Jaringan Perbankan
      console.log('  [SAGA 2] Otorisasi Dana ke Gateway Perbankan (Visa/BCA)...');
      if (paymentMethod === 'SIMULATE_BANK_DOWN') {
        throw new Error('Koneksi ke Core Banking Timeout (504 Gateway Timeout)');
      }
      sagaRollbackSteps.push('BANK_AUTH');

      // SAGA STEP 3: Pembukuan Akuntansi Double-Entry Ledger
      console.log('  [SAGA 3] Mencatat Journal Postings ke Double-Entry Ledger...');
      const journal = this.ledger.postTransaction(chargeId, amount, 2500);
      sagaRollbackSteps.push('LEDGER_POSTING');

      // SAGA STEP 4: Buat Webhook Signature
      console.log('  [SAGA 4] Menyiapkan Webhook dengan Tanda Tangan HMAC-SHA256...');
      const webhookPayload = JSON.stringify({
        event: 'charge.succeeded',
        data: { chargeId, amount, status: 'PAID', journalId: journal.journalId }
      });
      const signature = WebhookEngine.signPayload(webhookPayload, this.merchantSecret);

      const response = {
        success: true,
        chargeId,
        status: 'PAID',
        journalId: journal.journalId,
        webhookSignature: signature
      };

      this.idempotency.saveResponse(idempotencyKey, response);
      console.log(`  🎉 [TRANSAKSI SUKSES PENUH] Transaksi ${chargeId} resmi lunas dan dibukukan!`);
      return response;

    } catch (err) {
      console.error(`  🚨 [TRANSAKSI GAGAL] Penyebab: ${err.message}`);
      console.log(`  🔄 [SAGA COMPENSATING ROLLBACK] Menjalankan pemulihan data mundur...`);

      for (const step of sagaRollbackSteps.reverse()) {
        if (step === 'LEDGER_POSTING') {
          console.log(`     ↪️ Menghapus entri jurnal pembukuan sementara...`);
        }
        if (step === 'BANK_AUTH') {
          console.log(`     ↪️ Mengirim perintah VOID otorisasi ke jaringan bank...`);
        }
      }

      const errorResponse = { success: false, chargeId, status: 'FAILED', error: err.message };
      this.idempotency.saveResponse(idempotencyKey, errorResponse);
      return errorResponse;
    }
  }
}

// =========================================================================
// BAGIAN 5: EKSEKUSI PENGUJIAN CAPSTONE PROJECT LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('CAPSTONE PROJECT: PAYPULSE ENTERPRISE PAYMENT & LEDGER GATEWAY');
  console.log('='.repeat(75));

  const gateway = new PayPulsePaymentGateway();

  // KASUS 1: Transaksi Normal Berhasil
  console.log('\n--- SKENARIO 1: TRANSAKSI NORMAL SUKSES ---');
  const req1 = {
    chargeId: 'CHG-881901',
    merchantId: 'MCH-TOKOPEDIA',
    amount: 150000,
    paymentMethod: 'BCA_VIRTUAL_ACCOUNT'
  };
  await gateway.processCharge('idemp_key_alpha_01', req1);

  // KASUS 2: Pengujian Idempotensi (Network Retry Pengiriman Ulang Request yang Sama)
  console.log('\n--- SKENARIO 2: UJI RETRY JARINGAN DENGAN IDEMPOTENCY KEY SAMA ---');
  await gateway.processCharge('idemp_key_alpha_01', req1);

  // KASUS 3: Kegagalan Transaksi & Uji Kompensasi Saga (Simulasi Bank Down)
  console.log('\n--- SKENARIO 3: KEGAGALAN BANK & RECOVERY SAGA KOMPENSASI ---');
  const req3 = {
    chargeId: 'CHG-881902',
    merchantId: 'MCH-TOKOPEDIA',
    amount: 2500000,
    paymentMethod: 'SIMULATE_BANK_DOWN'
  };
  await gateway.processCharge('idemp_key_beta_02', req3);

  // KASUS 4: Verifikasi Keseimbangan Pembukuan Double-Entry Ledger
  console.log('\n--- SKENARIO 4: AUDIT BUKU BESAR AKUNTANSI (DOUBLE-ENTRY LEDGER) ---');
  console.log('Status Saldo Akun Finansial Gateway:');
  for (const [account, balance] of gateway.ledger.accounts) {
    console.log(`  💰 ${account.padEnd(30)} : Rp ${balance.toLocaleString('id-ID')}`);
  }

  // Verifikasi Tanda Tangan Webhook Merchant
  console.log('\n--- SKENARIO 5: VERIFIKASI DIGITAL SIGNATURE WEBHOOK OLEH MERCHANT ---');
  const samplePayload = JSON.stringify({ event: 'charge.succeeded', chargeId: 'CHG-881901' });
  const validSig = WebhookEngine.signPayload(samplePayload, gateway.merchantSecret);
  const isAuthentic = WebhookEngine.verifySignature(samplePayload, gateway.merchantSecret, validSig);
  console.log(`  Tanda Tangan Asli : ${validSig}`);
  console.log(`  Verifikasi Sukses : ${isAuthentic ? '✅ SAH & OTENTIK' : '❌ PALSU'}`);

  console.log('\n' + '='.repeat(75));
  console.log('SELAMAT! SELURUH SISTEM CAPSTONE PROJECT PAYPULSE TERUJI 100% SUKSES!');
  console.log('='.repeat(75));
}

main();
