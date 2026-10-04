import React, { useReducer, useEffect, useCallback, useRef, memo } from 'react';

// ==========================================
// 1. DATA CONTRACTS & IMMUTABLE TYPES
// ==========================================

export interface OrderLevel {
  price: number;
  quantity: number;
  total: number;
}

export interface OrderBookState {
  bids: Map<number, number>; // price -> quantity
  asks: Map<number, number>; // price -> quantity
  lastUpdateId: number;
  sequenceMismatch: boolean;
}

export type OrderBookAction =
  | {
      type: 'BATCH_TICK';
      payload: {
        updates: Array<{ side: 'bid' | 'ask'; price: number; quantity: number }>;
        updateId: number;
      };
    }
  | { type: 'RESET_STREAM' };

// ==========================================
// 2. DETERMINISTIC ENGINE (REDUCER)
// ==========================================

const INITIAL_ORDER_STATE: OrderBookState = {
  bids: new Map(),
  asks: new Map(),
  lastUpdateId: 0,
  sequenceMismatch: false,
};

function orderBookReducer(state: OrderBookState, action: OrderBookAction): OrderBookState {
  switch (action.type) {
    case 'BATCH_TICK': {
      const { updates, updateId } = action.payload;

      // Proteksi urutan paket data jaringan (Sequence Consistency Check)
      if (state.lastUpdateId !== 0 && updateId !== state.lastUpdateId + 1) {
        return {
          ...state,
          sequenceMismatch: true,
        };
      }

      // Clone map secara struktural untuk mematuhi immutability invariant React
      const nextBids = new Map(state.bids);
      const nextAsks = new Map(state.asks);

      for (let i = 0; i < updates.length; i++) {
        const { side, price, quantity } = updates[i];
        const targetMap = side === 'bid' ? nextBids : nextAsks;

        if (quantity === 0) {
          targetMap.delete(price);
        } else {
          targetMap.set(price, quantity);
        }
      }

      return {
        bids: nextBids,
        asks: nextAsks,
        lastUpdateId: updateId,
        sequenceMismatch: false,
      };
    }

    case 'RESET_STREAM':
      return INITIAL_ORDER_STATE;

    default:
      return state;
  }
}

// ==========================================
// 3. OPTIMIZED UI ROW (LEAF COMPONENT)
// ==========================================

interface OrderRowProps {
  price: number;
  quantity: number;
  side: 'bid' | 'ask';
}

const OrderRow = memo<OrderRowProps>(({ price, quantity, side }) => {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '2px 8px',
        color: side === 'bid' ? '#00c087' : '#ff3b30',
        fontFamily: 'monospace',
      }}
    >
      <span>{price.toFixed(2)}</span>
      <span>{quantity.toFixed(4)}</span>
    </div>
  );
});

OrderRow.displayName = 'OrderRow';

// ==========================================
// 4. MAIN ENGINE COMPONENT
// ==========================================

export const InstitutionalOrderBook: React.FC = () => {
  const [state, dispatch] = useReducer(orderBookReducer, INITIAL_ORDER_STATE);

  // Queue buffer internal untuk menyatukan ticks frekuensi tinggi dari WebSocket
  const incomingBufferRef = useRef<Array<{ side: 'bid' | 'ask'; price: number; quantity: number }>>([]);
  const sequenceTrackerRef = useRef<number>(0);
  const frameRequestRef = useRef<number | null>(null);

  // Mekanisme scheduler internal berbasis AnimationFrame untuk throttling render
  const flushUpdates = useCallback(() => {
    if (incomingBufferRef.current.length > 0) {
      const currentBatch = [...incomingBufferRef.current];
      incomingBufferRef.current = [];

      sequenceTrackerRef.current += 1;
      
      dispatch({
        type: 'BATCH_TICK',
        payload: {
          updates: currentBatch,
          updateId: sequenceTrackerRef.current,
        },
      });
    }

    frameRequestRef.current = requestAnimationFrame(flushUpdates);
  }, []);

  useEffect(() => {
    // Mulai render-loop engine
    frameRequestRef.current = requestAnimationFrame(flushUpdates);

    // Simulasi Stream WebSocket Jaringan Frekuensi Tinggi (50 events / detik)
    const intervalId = setInterval(() => {
      const mockSide: 'bid' | 'ask' = Math.random() > 0.5 ? 'bid' : 'ask';
      const mockPrice = mockSide === 'bid' ? 100 - Math.random() * 2 : 100 + Math.random() * 2;
      const mockQty = Math.floor(Math.random() * 10) === 0 ? 0 : Math.random() * 5; // Probabilitas likuidasi (0)

      incomingBufferRef.current.push({
        side: mockSide,
        price: parseFloat(mockPrice.toFixed(2)),
        quantity: parseFloat(mockQty.toFixed(4)),
      });
    }, 20);

    return () => {
      clearInterval(intervalId);
      if (frameRequestRef.current !== null) {
        cancelAnimationFrame(frameRequestRef.current);
      }
    };
  }, [flushUpdates]);

  // Derived state calculations (Dilakukan saat fase render secara deterministik)
  const sortedBids = Array.from(state.bids.entries())
    .map(([price, quantity]) => ({ price, quantity }))
    .sort((a, b) => b.price - a.price)
    .slice(0, 10);

  const sortedAsks = Array.from(state.asks.entries())
    .map(([price, quantity]) => ({ price, quantity }))
    .sort((a, b) => a.price - b.price)
    .slice(0, 10);

  return (
    <div style={{ width: '400px', backgroundColor: '#121212', color: '#ffffff', padding: '16px' }}>
      <header style={{ borderBottom: '1px solid #333', paddingBottom: '8px', marginBottom: '8px' }}>
        <h4 style={{ margin: 0 }}>High-Frequency Order Book</h4>
        <small style={{ color: state.sequenceMismatch ? '#ff3b30' : '#888' }}>
          Sequence ID: {state.lastUpdateId} {state.sequenceMismatch && '(ERR: DESYNC DETECTED)'}
        </small>
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div>
          <span style={{ fontSize: '11px', color: '#666' }}>ASKS (SELL ORDERS)</span>
          {sortedAsks.map(ask => (
            <OrderRow key={`ask-${ask.price}`} price={ask.price} quantity={ask.quantity} side="ask" />
          ))}
        </div>

        <div style={{ borderTop: '1px dashed #333', margin: '4px 0' }} />

        <div>
          <span style={{ fontSize: '11px', color: '#666' }}>BIDS (BUY ORDERS)</span>
          {sortedBids.map(bid => (
            <OrderRow key={`bid-${bid.price}`} price={bid.price} quantity={bid.quantity} side="bid" />
          ))}
        </div>
      </div>
    </div>
  );
};
