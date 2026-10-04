// ============================================================================
// SYSTEM TYPE ENGINE: TYPE-SAFE EVENT BUS & OBJECT PATH ACCESSOR
// ============================================================================

/** Tipe dasar untuk mencegah rekursi tak berhingga */
type Prev = [never, 0, 1, 2, 3, 4, 5, ...never[]];

/**
 * Mengonversi struktur objek berlapis menjadi union string path yang dipisahkan titik (.)
 * Dilengkapi pembatas kedalaman rekursi hingga 4 lapis.
 */
export type NestedPaths<T, Depth extends number = 4> = [Depth] extends [never]
  ? never
  : T extends object
  ? {
      [K in keyof T]-?: K extends string | number
        ? `${K}` | (NestedPaths<T[K], Prev[Depth]> extends infer SubPath
            ? SubPath extends string
              ? `${K}.${SubPath}`
              : never
            : never)
        : never;
    }[keyof T]
  : never;

/**
 * Mengekstrak tipe data dari target path berbasis string eksplisit
 */
export type PathValue<T, P extends string> = P extends `${infer Head}.${infer Tail}`
  ? Head extends keyof T
    ? PathValue<T[Head], Tail>
    : never
  : P extends keyof T
  ? T[P]
  : never;

// ============================================================================
// DOMAIN IMPLEMENTATION: EVENT CONTRACT & EVENT BUS
// ============================================================================

export interface SystemEventContracts {
  "auth:login": {
    userId: string;
    session: { token: string; expiresAt: number };
  };
  "auth:logout": {
    userId: string;
    timestamp: number;
  };
  "billing:payment-processed": {
    transactionId: string;
    metadata: {
      amount: number;
      currency: "USD" | "IDR" | "EUR";
      payer: {
        address: {
          country: string;
          city: string;
        };
      };
    };
  };
}

export type EventCallback<T> = (payload: T) => void | Promise<void>;

export class StronglyTypedEventBus<TEvents extends Record<string, any>> {
  private listeners: {
    [K in keyof TEvents]?: Set<EventCallback<TEvents[K]>>;
  } = {};

  public subscribe<E extends keyof TEvents>(
    event: E,
    callback: EventCallback<TEvents[E]>
  ): () => void {
    if (!this.listeners[event]) {
      this.listeners[event] = new Set();
    }
    this.listeners[event]!.add(callback);

    return () => {
      this.listeners[event]?.delete(callback);
    };
  }

  public publish<E extends keyof TEvents>(
    event: E,
    payload: TEvents[E]
  ): void {
    const handlers = this.listeners[event];
    if (handlers) {
      handlers.forEach((callback) => {
        try {
          void callback(payload);
        } catch (error) {
          console.error(`[EventBus] Uncaught exception on event: ${String(event)}`, error);
        }
      });
    }
  }

  /**
   * Mengambil mutasi nested value dari event payload secara aman
   */
  public extractDeepProperty<
    E extends keyof TEvents,
    P extends NestedPaths<TEvents[E]>
  >(
    payload: TEvents[E],
    path: P
  ): PathValue<TEvents[E], P> {
    const segments = (path as string).split(".");
    let current: any = payload;

    for (const segment of segments) {
      if (current === null || current === undefined) {
        return undefined as PathValue<TEvents[E], P>;
      }
      current = current[segment];
    }

    return current as PathValue<TEvents[E], P>;
  }
}

// ============================================================================
// VERIFIKASI PENGGUNAAN TIPE SECARA PRAKTIS
// ============================================================================

const bus = new StronglyTypedEventBus<SystemEventContracts>();

// 1. Validasi Subscribe Type
bus.subscribe("billing:payment-processed", (payload) => {
  console.log(`Payment processed: ${payload.transactionId}`);
  
  // Mengambil tipe deep path dengan autocompletion dan validasi ketat
  const country = bus.extractDeepProperty(
    payload,
    "metadata.payer.address.country" // Type checked!
  );
  console.log(`Payer Country: ${country}`);
});

// 2. Validasi Publish Type
bus.publish("auth:login", {
  userId: "usr_9921",
  session: {
    token: "jwt.secret.payload",
    expiresAt: Date.now() + 3600000,
  },
});

// @ts-expect-error Kompilator menggagalkan jika ada properti hilang
bus.publish("auth:logout", {
  userId: "usr_9921",
  // Error: Property 'timestamp' is missing in type '{ userId: string; }'
});

// @ts-expect-error Kompilator menggagalkan jika path tidak valid
bus.extractDeepProperty(
  {} as SystemEventContracts["billing:payment-processed"],
  "metadata.invalid_property.address"
);
