// ============================================================================
// File: src/engine/TransactionEventPipeline.ts
// ============================================================================

export interface TransactionPayload {
  readonly transactionId: string;
  readonly accountId: string;
  readonly amount: number;
  readonly timestamp: number;
}

export interface AuditLogPayload {
  readonly level: "INFO" | "WARN" | "CRITICAL";
  readonly message: string;
}

// Peta Event ke Tipe Payload Masing-Masing
export interface EventRegistry {
  "transaction:created": TransactionPayload;
  "transaction:committed": TransactionPayload;
  "audit:log": AuditLogPayload;
}

// Tipe callback listener yang dilarang mengakses runtime 'this' context dispatcher
export type SafeEventListener<TData> = (this: void, data: TData) => void | Promise<void>;

export class TransactionPipelineEngine {
  private listeners: {
    [K in keyof EventRegistry]?: Array<SafeEventListener<EventRegistry[K]>>;
  } = {};

  // Register Event Listener
  public on<K extends keyof EventRegistry>(
    event: K,
    listener: SafeEventListener<EventRegistry[K]>
  ): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    // Cast dihindari, tipe terisolasi secara struktural
    const bucket = this.listeners[event] as Array<SafeEventListener<EventRegistry[K]>>;
    bucket.push(listener);
  }

  // FUNCTION OVERLOADING: Emit signature terisolasi berdasarkan kompleksitas data
  public emit(event: "audit:log", message: string, level?: "INFO" | "WARN" | "CRITICAL"): Promise<void>;
  public emit<K extends keyof EventRegistry>(event: K, payload: EventRegistry[K]): Promise<void>;
  public async emit(
    event: keyof EventRegistry,
    payloadOrMessage: unknown,
    maybeLevel?: "INFO" | "WARN" | "CRITICAL"
  ): Promise<void> {
    let resolvedPayload: unknown;

    if (event === "audit:log" && typeof payloadOrMessage === "string") {
      resolvedPayload = {
        message: payloadOrMessage,
        level: maybeLevel ?? "INFO",
      } satisfies AuditLogPayload;
    } else {
      resolvedPayload = payloadOrMessage;
    }

    const currentListeners = this.listeners[event];
    if (!currentListeners || currentListeners.length === 0) {
      return;
    }

    for (const listener of currentListeners) {
      // Pemanggilan aman: konteks 'this' diikat secara eksplisit ke 'undefined' via call
      // Mencegah context hijacking ke instance TransactionPipelineEngine
      await (listener as (this: void, data: unknown) => void | Promise<void>).call(
        undefined,
        resolvedPayload
      );
    }
  }
}

// ============================================================================
// Verifikasi Runtime & Skenario Penggunaan
// ============================================================================
async function runSystem() {
  const engine = new TransactionPipelineEngine();

  // Daftarkan listener tipe aman
  engine.on("transaction:created", function (this: void, data) {
    // Parameter 'data' terinferensi otomatis sebagai TransactionPayload
    console.log(`[Tx Engine] Transaksi ${data.transactionId} sebesar ${data.amount} diterima.`);
    // Mengakses this.listeners di sini akan menyebabkan error kompilasi karena `this: void`
  });

  engine.on("audit:log", (data) => {
    // Parameter 'data' terinferensi otomatis sebagai AuditLogPayload
    console.log(`[Audit] [${data.level}] ${data.message}`);
  });

  // Uji Pemanggilan Overload 1 (Audit Log Shorthand)
  await engine.emit("audit:log", "Service pipeline successfully booted.", "INFO");

  // Uji Pemanggilan Overload 2 (Strict Event Key)
  await engine.emit("transaction:created", {
    transactionId: "TX-998811",
    accountId: "ACC-00129",
    amount: 154000.5,
    timestamp: Date.now(),
  });
}

runSystem().catch(console.error);
