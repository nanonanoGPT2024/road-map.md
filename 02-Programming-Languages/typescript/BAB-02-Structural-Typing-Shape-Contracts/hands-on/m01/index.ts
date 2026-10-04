// ==========================================
// 1. DOMAIN LAYER: BRANDED TYPES (NOMINAL EMULATION)
// ==========================================

declare const TransactionIdBrand: unique symbol;
declare const MerchantIdBrand: unique symbol;

export type TransactionId = string & { readonly [TransactionIdBrand]: true };
export type MerchantId = string & { readonly [MerchantIdBrand]: true };

// Constructor helper (Smart Casts)
export function toTransactionId(id: string): TransactionId {
  if (!id.startsWith("txn_")) {
    throw new Error(`Format ID Transaksi tidak valid: ${id}`);
  }
  return id as TransactionId;
}

export function toMerchantId(id: string): MerchantId {
  if (!id.startsWith("mch_")) {
    throw new Error(`Format ID Merchant tidak valid: ${id}`);
  }
  return id as MerchantId;
}

// Canonical Structural Contract
export interface CanonicalPaymentRequest {
  readonly transactionId: TransactionId;
  readonly merchantId: MerchantId;
  readonly amountInCents: bigint;
  readonly currency: "IDR" | "USD";
}

// ==========================================
// 2. GATEWAY ADAPTER SHAPES (EXTERNAL)
// ==========================================

export interface VendorAPayload {
  vendor_txn_id: string;
  vendor_merchant_code: string;
  total_gross_cents: number;
  currency_code: string;
  extra_tracking_pixel: string; // Ekses
  client_ip: string;            // Ekses
}

export interface VendorBPayload {
  transaction_reference: string;
  partner_id: string;
  amount: {
    value: number;
    iso_currency: string;
  };
  debug_trace_id: string;       // Ekses
}

// ==========================================
// 3. CORE SERVICE DISPATCHER
// ==========================================

export class PaymentProcessingEngine {
  public static execute(request: CanonicalPaymentRequest): void {
    // Mengeksekusi pembayaran secara strictly typed
    console.log(
      `[PROSES] ID: ${request.transactionId} | Merchant: ${request.merchantId} | ` +
      `Nominal: ${request.amountInCents.toString()} ${request.currency}`
    );
  }
}

// ==========================================
// 4. NORMALIZER PIPELINE DENGAN STRIP EKSPOR EKSES
// ==========================================

export class PaymentNormalizer {
  // Mengonversi Vendor A ke Canonical Shape (Menghilangkan Ekses)
  public static normalizeVendorA(raw: VendorAPayload): CanonicalPaymentRequest {
    return {
      transactionId: toTransactionId(raw.vendor_txn_id),
      merchantId: toMerchantId(raw.vendor_merchant_code),
      amountInCents: BigInt(raw.total_gross_cents),
      currency: raw.currency_code === "IDR" ? "IDR" : "USD"
    };
  }

  // Mengonversi Vendor B ke Canonical Shape
  public static normalizeVendorB(raw: VendorBPayload): CanonicalPaymentRequest {
    return {
      transactionId: toTransactionId(raw.transaction_reference),
      merchantId: toMerchantId(raw.partner_id),
      amountInCents: BigInt(raw.amount.value),
      currency: raw.amount.iso_currency === "IDR" ? "IDR" : "USD"
    };
  }
}

// ==========================================
// 5. RUNTIME EXECUTION TEST
// ==========================================

function bootstrap() {
  const incomingVendorA: VendorAPayload = {
    vendor_txn_id: "txn_01HZ89ABCD",
    vendor_merchant_code: "mch_tokopedia",
    total_gross_cents: 25000000,
    currency_code: "IDR",
    extra_tracking_pixel: "https://tracking.com/pixel.gif",
    client_ip: "103.20.10.1"
  };

  // Normalisasi & Eksekusi
  const canonicalA = PaymentNormalizer.normalizeVendorA(incomingVendorA);
  PaymentProcessingEngine.execute(canonicalA);

  // Mencegah Type Confusion Bug berkat Branded Types:
  const fakeTxnId = "txn_9999" as TransactionId;
  const fakeMchId = "mch_8888" as MerchantId;

  // Kode di bawah ini jika posisinya dibalik akan gagal kompilasi:
  // const invalidPayload: CanonicalPaymentRequest = {
  //   transactionId: fakeMchId, // COMPILE ERROR: Type 'MerchantId' is not assignable to type 'TransactionId'
  //   merchantId: fakeTxnId,
  //   amountInCents: 1000n,
  //   currency: "USD"
  // };
}

bootstrap();
