'use strict';

/**
 * SISTEM AUDIT & VALIDASI TRANSAKSI FINTECH BERBASIS PARADIGMA FUNGSIONAL
 */

// 1. Primitive Pipeline Orchestrator
const pipe = (...fns) => (initialValue) => 
  fns.reduce((acc, fn) => fn(acc), initialValue);

// 2. Curried Calculation Helpers (Pure Functions)
const applyProcessingFee = (rate) => (transaction) => {
  const fee = transaction.amount * rate;
  return Object.freeze({
    ...transaction,
    fees: transaction.fees + fee,
    netAmount: transaction.netAmount - fee,
    auditTrail: [...transaction.auditTrail, `FeeApplied: ${fee}`]
  });
};

const applyTaxDeduction = (taxPercentage) => (transaction) => {
  const tax = transaction.netAmount * (taxPercentage / 100);
  return Object.freeze({
    ...transaction,
    tax: transaction.tax + tax,
    netAmount: transaction.netAmount - tax,
    auditTrail: [...transaction.auditTrail, `TaxDeducted: ${tax}`]
  });
};

const applyCurrencyConversion = (exchangeRate, targetCurrency) => (transaction) => {
  return Object.freeze({
    ...transaction,
    currency: targetCurrency,
    originalAmount: transaction.amount,
    amount: transaction.amount * exchangeRate,
    netAmount: transaction.netAmount * exchangeRate,
    fees: transaction.fees * exchangeRate,
    tax: transaction.tax * exchangeRate,
    auditTrail: [...transaction.auditTrail, `ConvertedTo: ${targetCurrency} at Rate: ${exchangeRate}`]
  });
};

// 3. Memoized High-Cost Validator using Closures
const createTransactionValidator = () => {
  // Heap-allocated cache via closure
  const validationCache = new Map();

  return (transaction) => {
    const cacheKey = `${transaction.id}_${transaction.amount}_${transaction.currency}`;
    
    if (validationCache.has(cacheKey)) {
      return { ...transaction, validationStatus: validationCache.get(cacheKey) };
    }

    // Simulasi komputasi verifikasi integritas transaksi yang kompleks
    const isValid = transaction.amount > 0 && 
                    transaction.senderAccount !== transaction.receiverAccount &&
                    typeof transaction.amount === 'number';

    const status = isValid ? 'VALIDATED_SUCCESS' : 'FAILED_VALIDATION';
    
    // Simpan ke private closure cache
    validationCache.set(cacheKey, status);

    return Object.freeze({
      ...transaction,
      validationStatus: status,
      auditTrail: [...transaction.auditTrail, `Validated: ${status}`]
    });
  };
};

// 4. Factory Penyusun Pipeline Transaksi FinTech
const createTransactionProcessor = () => {
  const validator = createTransactionValidator();

  // Komposisi proses transformasi bisnis
  const processInternationalUSD = pipe(
    validator,
    applyProcessingFee(0.015),          // Biaya admin 1.5%
    applyCurrencyConversion(0.000064, 'USD'), // IDR -> USD
    applyTaxDeduction(10)                // Pajak 10%
  );

  return {
    execute: (rawTransaction) => {
      // Inisialisasi awal struktur data transaksi yang di-freeze
      const baseTransaction = Object.freeze({
        ...rawTransaction,
        fees: 0,
        tax: 0,
        netAmount: rawTransaction.amount,
        auditTrail: ['TransactionInitialized']
      });

      return processInternationalUSD(baseTransaction);
    }
  };
};

// ==========================================
// SIMULASI EKSEKUSI PRODUKSI
// ==========================================

const processor = createTransactionProcessor();

const incomingWireTransfer = {
  id: "trx-99882103",
  senderAccount: "ACC-IDR-110",
  receiverAccount: "ACC-USD-992",
  amount: 50_000_000, // 50 Juta IDR
  currency: "IDR"
};

// Eksekusi mutasi fungsional (menghasilkan snapshot baru)
const processedResult = processor.execute(incomingWireTransfer);

console.log("--- HASIL EKSEKUSI TRANSAKSI ---");
console.log("Payload Asli (Tidak Mengalami Mutasi):", incomingWireTransfer);
console.log("\nSnapshot Hasil Akhir Pemrosesan:", JSON.stringify(processedResult, null, 2));
console.log("\nApakah Objek Baru Identik Secara Referensi?:", incomingWireTransfer === processedResult); // FALSE
