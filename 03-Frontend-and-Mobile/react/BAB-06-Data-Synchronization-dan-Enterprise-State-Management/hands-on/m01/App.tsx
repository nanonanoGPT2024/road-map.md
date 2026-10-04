// ==========================================
// 1. DOMAIN MODELS & TYPES
// ==========================================

export interface LedgerItem {
  readonly id: string;
  readonly symbol: string;
  readonly amount: number;
  readonly status: "PENDING" | "CONFIRMED" | "FAILED";
  readonly version: number;
}

export interface LedgerState {
  readonly items: Readonly<Record<string, LedgerItem>>;
  readonly order: readonly string[];
}

export type BroadcastSyncMessage = 
  | { type: "SYNC_CONFIRMED"; payload: LedgerItem }
  | { type: "INVALIDATE_ALL" };

// ==========================================
// 2. PRODUCTION MULTI-TAB SYNC ENGINE
// ==========================================

export class EnterpriseLedgerEngine {
  private state: LedgerState = { items: {}, order: [] };
  private listeners: Set<() => void> = new Set();
  private rollbackBuffer: Map<string, LedgerItem | null> = new Map();
  private broadcastChannel: BroadcastChannel;

  constructor() {
    this.broadcastChannel = new BroadcastChannel("fincorp_ledger_sync_bus");
    this.broadcastChannel.onmessage = this.handleCrossTabBroadcast;
  }

  public getSnapshot = (): LedgerState => {
    return this.state;
  };

  public subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private notify(): void {
    this.listeners.forEach((listener) => listener());
  }

  // Cross-Tab Message Receiver
  private handleCrossTabBroadcast = (event: MessageEvent<BroadcastSyncMessage>) => {
    const data = event.data;
    if (data.type === "SYNC_CONFIRMED") {
      this.applyServerUpdate(data.payload, false);
    }
  };

  // Direct Cache Update
  public applyServerUpdate(item: LedgerItem, shouldBroadcast = true): void {
    const existing = this.state.items[item.id];
    
    // Concurrency check via Lamport/Version field
    if (existing && existing.version > item.version) {
      console.warn(`[SyncEngine] Ignored stale update for ${item.id}. Version: ${item.version} < ${existing.version}`);
      return;
    }

    const nextItems = { ...this.state.items, [item.id]: Object.freeze(item) };
    const nextOrder = this.state.items[item.id] 
      ? this.state.order 
      : [...this.state.order, item.id];

    this.state = {
      items: Object.freeze(nextItems),
      order: Object.freeze(nextOrder),
    };

    this.notify();

    if (shouldBroadcast) {
      this.broadcastChannel.postMessage({
        type: "SYNC_CONFIRMED",
        payload: item,
      });
    }
  }

  // ==========================================
  // 3. OPTIMISTIC MUTATION & ROLLBACK CORE
  // ==========================================

  public async executeOptimisticUpdate(
    itemId: string,
    deltaAmount: number,
    networkMutationFn: (id: string, amount: number, idempotencyKey: string) => Promise<LedgerItem>
  ): Promise<void> {
    const originalItem = this.state.items[itemId];
    if (!originalItem) {
      throw new Error(`Target ledger item [${itemId}] does not exist in store.`);
    }

    const transactionId = crypto.randomUUID();
    const idempotencyKey = `idemp-${itemId}-${Date.now()}-${transactionId}`;

    // Snapshot buffer untuk deterministic rollback
    this.rollbackBuffer.set(transactionId, { ...originalItem });

    // Step 1: Aplikasikan patch optimistik instan
    const optimisticItem: LedgerItem = {
      ...originalItem,
      amount: originalItem.amount + deltaAmount,
      status: "PENDING",
      version: originalItem.version + 1,
    };

    this.state = {
      ...this.state,
      items: Object.freeze({
        ...this.state.items,
        [itemId]: Object.freeze(optimisticItem),
      }),
    };
    this.notify();

    // Step 2: Kirim Network Request
    try {
      const serverConfirmedItem = await networkMutationFn(itemId, optimisticItem.amount, idempotencyKey);
      
      // Mutasi Sukses: Bersihkan rollback snapshot
      this.rollbackBuffer.delete(transactionId);
      
      // Terapkan data terotorisasi resmi dari server
      this.applyServerUpdate(serverConfirmedItem, true);
    } catch (networkError) {
      // Step 3: Failure Execution -> Lakukan Rollback
      console.error(`[SyncEngine] Mutation failed for ${itemId}. Rolling back changes. Error:`, networkError);

      const rollbackSnapshot = this.rollbackBuffer.get(transactionId);
      this.rollbackBuffer.delete(transactionId);

      if (rollbackSnapshot) {
        this.state = {
          ...this.state,
          items: Object.freeze({
            ...this.state.items,
            [itemId]: Object.freeze(rollbackSnapshot),
          }),
        };
      } else {
        // Fallback jika tidak ada snapshot: Hapus item dari dictionary
        const filteredItems = { ...this.state.items };
        delete filteredItems[itemId];
        this.state = {
          items: Object.freeze(filteredItems),
          order: this.state.order.filter((id) => id !== itemId),
        };
      }

      this.notify();
      throw networkError; // Re-throw ke React Component Boundary
    }
  }

  public destroy(): void {
    this.broadcastChannel.close();
    this.listeners.clear();
    this.rollbackBuffer.clear();
  }
}

// Global Singleton Instance
export const globalLedgerEngine = new EnterpriseLedgerEngine();
