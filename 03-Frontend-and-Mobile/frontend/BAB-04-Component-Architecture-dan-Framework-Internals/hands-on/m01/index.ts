// TradingGrid.tsx
import React, {
  createContext,
  useContext,
  useReducer,
  useMemo,
  useCallback,
  useRef,
  memo,
  ReactNode,
  Dispatch
} from "react";

// --- DOMAIN TYPES ---
export interface OrderItem {
  id: string;
  symbol: string;
  price: number;
  volume: number;
}

interface GridState {
  orders: Record<string, OrderItem>;
  orderIds: string[];
}

type GridAction =
  | { type: "UPDATE_TICK"; payload: { id: string; price: number; volume: number } }
  | { type: "BATCH_UPDATE"; payload: OrderItem[] };

// --- STATE MANAGEMENT INTERNALS ---
function gridReducer(state: GridState, action: GridAction): GridState {
  switch (action.type) {
    case "UPDATE_TICK": {
      const { id, price, volume } = action.payload;
      const target = state.orders[id];
      if (!target || (target.price === price && target.volume === volume)) {
        return state; // Bailout: Hindari alokasi referensi baru jika data identik
      }
      return {
        ...state,
        orders: {
          ...state.orders,
          [id]: { ...target, price, volume }
        }
      };
    }
    case "BATCH_UPDATE": {
      const newOrders = { ...state.orders };
      let hasChanged = false;

      for (const item of action.payload) {
        const existing = newOrders[item.id];
        if (!existing || existing.price !== item.price || existing.volume !== item.volume) {
          newOrders[item.id] = item;
          hasChanged = true;
        }
      }

      if (!hasChanged) return state;

      return {
        orderIds: Object.keys(newOrders),
        orders: newOrders
      };
    }
    default:
      return state;
  }
}

// --- SEPARATED CONTEXT ARCHITECTURE (Mencegah Render Cascade) ---
const GridDataStateContext = createContext<GridState | null>(null);
const GridDispatchContext = createContext<Dispatch<GridAction> | null>(null);

// --- ROOT COMPONENT (Provider Compound Pattern) ---
export interface TradingGridProps {
  initialOrders: OrderItem[];
  children: ReactNode;
}

export function TradingGrid({ initialOrders, children }: TradingGridProps) {
  const [state, dispatch] = useReducer(gridReducer, {
    orders: initialOrders.reduce((acc, curr) => ({ ...acc, [curr.id]: curr }), {}),
    orderIds: initialOrders.map((o) => o.id)
  });

  return (
    <GridDispatchContext.Provider value={dispatch}>
      <GridDataStateContext.Provider value={state}>
        <div className="trading-grid-container" role="table">
          {children}
        </div>
      </GridDataStateContext.Provider>
    </GridDispatchContext.Provider>
  );
}

// --- CONSUMPTION HOOKS DENGAN INVARIANT ASSERTION ---
export function useGridDispatch(): Dispatch<GridAction> {
  const context = useContext(GridDispatchContext);
  if (!context) {
    throw new Error("useGridDispatch harus digunakan di dalam komponen <TradingGrid />");
  }
  return context;
}

function useOrderItem(id: string): OrderItem | undefined {
  const state = useContext(GridDataStateContext);
  if (!state) {
    throw new Error("useOrderItem harus digunakan di dalam komponen <TradingGrid />");
  }
  return state.orders[id];
}

export function useGridOrderIds(): string[] {
  const state = useContext(GridDataStateContext);
  if (!state) {
    throw new Error("useGridOrderIds harus digunakan di dalam komponen <TradingGrid />");
  }
  return state.orderIds;
}

// --- LEAF COMPONENT: OPTIMIZED ROW ---
interface OrderRowProps {
  id: string;
  onExecuteTrade: (id: string, price: number) => void;
}

export const OrderRow = memo(function OrderRow({ id, onExecuteTrade }: OrderRowProps) {
  const item = useOrderItem(id);
  // Ref stabil untuk callback aksi guna menghindari regenerasi fungsi anonim
  const tradeHandlerRef = useRef(onExecuteTrade);
  tradeHandlerRef.current = onExecuteTrade;

  const handleAction = useCallback(() => {
    if (item) {
      tradeHandlerRef.current(item.id, item.price);
    }
  }, [item?.id, item?.price]);

  if (!item) return null;

  return (
    <div className="order-row" role="row" style={{ display: "flex", gap: "1rem" }}>
      <span role="cell" className="font-mono">{item.symbol}</span>
      <span role="cell" className="font-mono">{item.price.toFixed(2)}</span>
      <span role="cell" className="font-mono">{item.volume}</span>
      <button role="cell" onClick={handleAction}>
        Execute
      </button>
    </div>
  );
});

// --- COMPOSABLE SUB-COMPONENTS EXPORTS ---
TradingGrid.Row = OrderRow;
