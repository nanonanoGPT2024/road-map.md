import { Type, Static } from "@sinclair/typebox";
import Ajv, { ErrorObject } from "ajv";
import addFormats from "ajv-formats";

// Inisialisasi AJV dengan Hardened Security Options
const ajv = addFormats(
  new Ajv({
    allErrors: true,
    removeAdditional: false, // Jangan biarkan mutasi diam-diam, tolak secara eksplisit!
    useDefaults: false,
    coerceTypes: false, // DILARANG otomatis mengubah tipe, fail-fast pada payload anomali
    strict: true,
  }),
  ["date-time", "uuid"]
);

// 1. Definisikan Nominal Branded Types
declare const AccountIdBrand: unique symbol;
export type AccountId = string & { readonly [AccountIdBrand]: "AccountId" };

// 2. Buat Definisi Skema TypeBox (JSON Schema Specification Compliant)
export const WebhookEventSchema = Type.Object(
  {
    eventId: Type.String({ format: "uuid" }),
    accountId: Type.String({ pattern: "^acc_[a-zA-Z0-9]{16}$" }),
    amountInCents: Type.Integer({
      minimum: 1,
      maximum: 1_000_000_000, // Batas transaksi tunggal $10M
    }),
    currency: Type.Union([
      Type.Literal("IDR"),
      Type.Literal("USD"),
      Type.Literal("SGD"),
    ]),
    timestamp: Type.String({ format: "date-time" }),
    signature: Type.String({ minLength: 64, maxLength: 64 }), // SHA-256 Signature string
  },
  { additionalProperties: false } // Strict mode: cegah parameter injection
);

export type WebhookEventPayload = Static<typeof WebhookEventSchema>;

// 3. Kompilasi Skema menjadi JIT Function
const compileValidator = ajv.compile<WebhookEventPayload>(WebhookEventSchema);

// 4. Boundary Parse Execution Result Container
export type ValidationOutcome<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly errors: ReadonlyArray<string> };

export class PaymentIngressSecurityGate {
  public static validatePayload(rawPayload: unknown): ValidationOutcome<WebhookEventPayload> {
    if (typeof rawPayload !== "object" || rawPayload === null) {
      return {
        ok: false,
        errors: ["Payload root data harus berupa valid JSON non-null Object."],
      };
    }

    const isValid = compileValidator(rawPayload);

    if (!isValid && compileValidator.errors) {
      return {
        ok: false,
        errors: this.normalizeAjvErrors(compileValidator.errors),
      };
    }

    // Return value yang aman dikonsumsi oleh Trusted Domain
    return {
      ok: true,
      value: rawPayload as WebhookEventPayload,
    };
  }

  private static normalizeAjvErrors(errors: ErrorObject[]): string[] {
    return errors.map((err) => {
      const path = err.instancePath ? err.instancePath : "/root";
      return `Security Rule Violation: [${path}] ${err.message} (${JSON.stringify(err.params)})`;
    });
  }
}

// 5. Mock Consumer Execution Demonstration
function simulateWebhookTraffic() {
  const malformedAttackPayload = {
    eventId: "not-a-uuid",
    accountId: "acc_invalidlen",
    amountInCents: 100.5, // Gagal: Bukan Integer
    currency: "EUR", // Gagal: Di luar skema union
    timestamp: "invalid-date",
    signature: "abc",
    injectedProperty: "malicious_script", // Gagal: additionalProperties: false
  };

  const validationResult = PaymentIngressSecurityGate.validatePayload(malformedAttackPayload);

  if (!validationResult.ok) {
    console.error("INGRESS BLOCKED! Ancaman Keamanan / Anomali Data Terdeteksi:");
    validationResult.errors.forEach((err) => console.error(` - ${err}`));
  } else {
    console.log("PAYLOAD VERIFIED! Diteruskan ke Ledger Core:", validationResult.value);
  }
}

simulateWebhookTraffic();
