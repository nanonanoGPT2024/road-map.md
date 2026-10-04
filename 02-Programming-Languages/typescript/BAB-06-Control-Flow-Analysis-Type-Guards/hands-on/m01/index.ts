// ============================================================================
// 1. Data Contracts (Vendors Domain Specifications)
// ============================================================================

export interface StripeEvent {
  readonly provider: "STRIPE";
  readonly id: string;
  readonly data: {
    readonly object: {
      readonly chargeId: string;
      readonly amountInCents: number;
    };
  };
}

export interface PayPalEvent {
  readonly provider: "PAYPAL";
  readonly txnId: string;
  readonly purchase_units: ReadonlyArray<{
    readonly amount: {
      readonly currency_code: string;
      readonly value: string; // PayPal merepresentasikan uang dalam string desimal
    };
  }>;
}

export interface MidtransEvent {
  readonly provider: "MIDTRANS";
  readonly order_id: string;
  readonly gross_amount: string;
  readonly transaction_status: "capture" | "settlement" | "deny" | "pending";
}

// Sum Type seluruh event pembayaran yang sah
export type NormalizedWebhookEvent = StripeEvent | PayPalEvent | MidtransEvent;

// Objek Internal Terpadu (Unified Internal Ledger Entry)
export interface LedgerTransaction {
  readonly vendorReferenceId: string;
  readonly providerName: "STRIPE" | "PAYPAL" | "MIDTRANS";
  readonly normalizedAmount: number;
  readonly timestamp: number;
}

// ============================================================================
// 2. Custom Type Predicates & Assertion Infrastructures
// ============================================================================

function isObject(val: unknown): val is Record<string, unknown> {
  return typeof val === "object" && val !== null && !Array.isArray(val);
}

export function isStripeEvent(val: unknown): val is StripeEvent {
  if (!isObject(val) || val.provider !== "STRIPE" || typeof val.id !== "string") {
    return false;
  }
  if (!isObject(val.data) || !isObject(val.data.object)) {
    return false;
  }
  const obj = val.data.object;
  return typeof obj.chargeId === "string" && typeof obj.amountInCents === "number";
}

export function isPayPalEvent(val: unknown): val is PayPalEvent {
  if (!isObject(val) || val.provider !== "PAYPAL" || typeof val.txnId !== "string") {
    return false;
  }
  if (!Array.isArray(val.purchase_units) || val.purchase_units.length === 0) {
    return false;
  }
  const firstUnit = val.purchase_units[0];
  if (!isObject(firstUnit) || !isObject(firstUnit.amount)) {
    return false;
  }
  return (
    typeof firstUnit.amount.currency_code === "string" &&
    typeof firstUnit.amount.value === "string"
  );
}

export function isMidtransEvent(val: unknown): val is MidtransEvent {
  if (!isObject(val) || val.provider !== "MIDTRANS" || typeof val.order_id !== "string") {
    return false;
  }
  if (typeof val.gross_amount !== "string") {
    return false;
  }
  const validStatuses = ["capture", "settlement", "deny", "pending"];
  return (
    typeof val.transaction_status === "string" &&
    validStatuses.includes(val.transaction_status)
  );
}

// Top-Level Assertion Function
export function assertWebhookEvent(payload: unknown): asserts payload is NormalizedWebhookEvent {
  if (isStripeEvent(payload) || isPayPalEvent(payload) || isMidtransEvent(payload)) {
    return;
  }
  throw new Error("Security Violation: Malformed or untrusted payload format rejected.");
}

// ============================================================================
// 3. Execution Pipeline & Exhaustive Router
// ============================================================================

export class PaymentIngestionPipeline {
  public static ingest(rawPayload: unknown): LedgerTransaction {
    // 1. Tipe rawPayload awalnya unknown. Lakukan validasi ketat via assertion.
    assertWebhookEvent(rawPayload);

    // 2. Sekarang rawPayload telah dipersempit menjadi NormalizedWebhookEvent.
    // Lakukan pemrosesan menggunakan Control Flow Analysis berbasis diskriminan 'provider'.
    switch (rawPayload.provider) {
      case "STRIPE": {
        // Otomatis tersempitkan ke StripeEvent
        return {
          vendorReferenceId: rawPayload.data.object.chargeId,
          providerName: rawPayload.provider,
          normalizedAmount: rawPayload.data.object.amountInCents / 100,
          timestamp: Date.now(),
        };
      }

      case "PAYPAL": {
        // Otomatis tersempitkan ke PayPalEvent
        const parsedAmount = parseFloat(rawPayload.purchase_units[0].amount.value);
        if (Number.isNaN(parsedAmount)) {
          throw new Error("Invalid decimal currency parsing on PayPal payload");
        }
        return {
          vendorReferenceId: rawPayload.txnId,
          providerName: rawPayload.provider,
          normalizedAmount: parsedAmount,
          timestamp: Date.now(),
        };
      }

      case "MIDTRANS": {
        // Otomatis tersempitkan ke MidtransEvent
        const amount = parseFloat(rawPayload.gross_amount);
        return {
          vendorReferenceId: rawPayload.order_id,
          providerName: rawPayload.provider,
          normalizedAmount: amount,
          timestamp: Date.now(),
        };
      }

      default: {
        // 3. Exhaustiveness checking mutlak
        const exhaustiveCheck: never = rawPayload;
        throw new Error(`CRITICAL: Unhandled payment provider: ${JSON.stringify(exhaustiveCheck)}`);
      }
    }
  }
}
