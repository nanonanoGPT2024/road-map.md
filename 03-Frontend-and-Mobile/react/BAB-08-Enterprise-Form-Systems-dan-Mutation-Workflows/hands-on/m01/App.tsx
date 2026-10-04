// features/trading/OrderFormTransactionEngine.tsx
import React, { useRef, useTransition, useState, useId } from 'react';
import { z } from 'zod';
import { FormEngine, useFormField } from './EnterpriseFormEngine';

// 1. Zod Schema Definition
const allocationLegSchema = z.object({
  brokerId: z.string().min(1, 'Broker identifier is mandatory'),
  percentage: z.number().min(1, 'Min 1%').max(100, 'Max 100%'),
});

export const FXTradeOrderSchema = z.object({
  instrument: z.string().min(6, 'Invalid ISO FX Pair (e.g. EURUSD)'),
  notionalAmount: z.number().positive('Notional must be greater than 0'),
  legs: z.array(allocationLegSchema).min(1, 'Must have at least one execution leg'),
}).refine((data) => {
  const totalAlloc = data.legs.reduce((acc, leg) => acc + leg.percentage, 0);
  return totalAlloc === 100;
}, {
  message: 'Cumulative allocation of all execution legs must equal precisely 100%',
  path: ['legs'],
});

export type FXTradeOrderType = z.infer<typeof FXTradeOrderSchema>;

// Mock External API dengan Idempotency
interface TransactionResult {
  orderId: string;
  status: 'SETTLED' | 'REJECTED';
  reason?: string;
}

async function executeFxTrade(
  order: FXTradeOrderType,
  idempotencyKey: string,
  signal: AbortSignal
): Promise<TransactionResult> {
  const response = await fetch('/api/v3/fx/orders', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(order),
    signal,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || 'Execution Gateway Protocol Error');
  }

  return response.json();
}

// 2. Sub-Component: Atomic Field Input
interface TextInputProps {
  engine: FormEngine<any>;
  name: string;
  label: string;
  type?: string;
}

export const AtomicTextInput: React.FC<TextInputProps> = React.memo(({ engine, name, label, type = 'text' }) => {
  const inputId = useId();
  const { value, error, onChange, onBlur } = useFormField(engine, name);

  return (
    <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column' }}>
      <label htmlFor={inputId} style={{ fontWeight: 600, fontSize: '0.85rem' }}>
        {label}
      </label>
      <input
        id={inputId}
        type={type}
        value={value ?? ''}
        onChange={onChange}
        onBlur={onBlur}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : undefined}
        style={{
          border: error ? '1px solid #e53e3e' : '1px solid #cbd5e0',
          padding: '8px 12px',
          borderRadius: '4px',
          marginTop: '4px',
        }}
      />
      {error && (
        <span id={`${inputId}-error`} role="alert" style={{ color: '#e53e3e', fontSize: '0.75rem', marginTop: '2px' }}>
          {error}
        </span>
      )}
    </div>
  );
});

AtomicTextInput.displayName = 'AtomicTextInput';

// 3. Parent Form Orchestrator
const INITIAL_ORDER_STATE: FXTradeOrderType = {
  instrument: 'EURUSD',
  notionalAmount: 1000000,
  legs: [
    { brokerId: 'BARCLAYS-LON', percentage: 60 },
    { brokerId: 'CITI-NY', percentage: 40 },
  ],
};

export const FXOrderTransactionManager: React.FC = () => {
  const [engine] = useState(() => new FormEngine<FXTradeOrderType>(INITIAL_ORDER_STATE, FXTradeOrderSchema));
  const [isPending, startTransition] = useTransition();
  const [executionStatus, setExecutionStatus] = useState<string>('IDLE');
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Jalankan validasi skema menyeluruh
    const isValid = engine.validateAll();
    if (!isValid) {
      setExecutionStatus('VALIDATION_FAILED: Check high-risk fields.');
      return;
    }

    // Buat AbortController untuk race-condition elimination
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const payload = engine.getSnapshot();
    const idempotencyKey = crypto.randomUUID();

    startTransition(async () => {
      setExecutionStatus('TRANSMITTING_TO_MATCHING_ENGINE');
      try {
        const result = await executeFxTrade(payload, idempotencyKey, abortControllerRef.current!.signal);
        setExecutionStatus(`SUCCESS: Order ${result.orderId} Settled.`);
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setExecutionStatus('ABORTED: Superseded by new transaction attempt.');
          return;
        }
        // Rollback state & notify UI
        setExecutionStatus(`TRANSACTION_FAILED: ${err.message}. State retained for recovery.`);
      }
    });
  };

  return (
    <div style={{ maxWidth: '600px', margin: '2rem auto', padding: '1.5rem', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
      <h2 style={{ borderBottom: '1px solid #edf2f7', paddingBottom: '0.5rem' }}>
        Institutional FX Settlement Terminal
      </h2>

      <form onSubmit={handleSubmit} noValidate>
        <AtomicTextInput engine={engine} name="instrument" label="Currency Pair Code (ISO)" />
        <AtomicTextInput engine={engine} name="notionalAmount" label="Notional Volume" type="number" />

        {/* Display Status */}
        <div style={{ padding: '0.75rem', backgroundColor: '#edf2f7', borderRadius: '4px', margin: '1rem 0' }}>
          <strong>Execution Node Status:</strong> {executionStatus}
        </div>

        <button
          type="submit"
          disabled={isPending}
          style={{
            backgroundColor: isPending ? '#a0aec0' : '#3182ce',
            color: '#fff',
            padding: '10px 24px',
            border: 'none',
            borderRadius: '4px',
            cursor: isPending ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
          }}
        >
          {isPending ? 'Committing Allocation...' : 'Execute Order Allocation'}
        </button>
      </form>
    </div>
  );
};
