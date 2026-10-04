// production-gateway.js
import http from 'node:http';
import { performance, eventLoopUtilization } from 'node:perf_hooks';
import opentelemetry from '@opentelemetry/api';
import { BasicTracerProvider, SimpleSpanProcessor } from '@opentelemetry/sdk-trace-base';

// -----------------------------------------------------------------------------
// 1. TELEMETRY INITIALIZATION (OPENTELEMETRY TRACER)
// -----------------------------------------------------------------------------
class ProductionTraceExporter {
  export(spans, resultCallback) {
    for (const span of spans) {
      // In-line micro-footprint: Hindari alokasi JSON raksasa di hot-path
      if (span.duration[0] > 0 || span.duration[1] > 50_000_000) { // Log spans > 50ms
        process._rawDebug(`[SLOW SPAN DETECTED] ${span.name} - Duration: ${(span.duration[1] / 1e6).toFixed(2)}ms`);
      }
    }
    resultCallback({ code: 0 });
  }
  shutdown() { return Promise.resolve(); }
}

const provider = new BasicTracerProvider();
provider.addSpanProcessor(new SimpleSpanProcessor(new ProductionTraceExporter()));
provider.register();

const tracer = opentelemetry.trace.getTracer('payment-gateway-core', '2.4.0');

// -----------------------------------------------------------------------------
// 2. MONOMORPHIC ENGINE STRUCT SHAPE
// Mengunci urutan deklarasi hidden classes agar tidak memicu Megamorphic Transitions
// -----------------------------------------------------------------------------
class FastPaymentContext {
  // Properti dideklarasikan secara deterministik pada constructor
  constructor(transactionId, amount, currency) {
    this.transactionId = transactionId;
    this.amount = amount;
    this.currency = currency;
    this.isFlagged = false;
    this.processingLatencyMs = 0;
    this.metadata = null; // Selalu diinisialisasi, bukan undefined atau dynamic key
  }
}

// -----------------------------------------------------------------------------
// 3. BACKPRESSURE CONTROLLER VIA EVENT LOOP UTILIZATION (ELU)
// -----------------------------------------------------------------------------
class BackpressureEngine {
  #lastEluSample;
  #threshold;

  constructor(threshold = 0.85) {
    this.#threshold = threshold; // Reject / Shed load jika thread > 85% saturasi
    this.#lastEluSample = eventLoopUtilization();
  }

  isSaturated() {
    const currentElu = eventLoopUtilization();
    const utilization = eventLoopUtilization(currentElu, this.#lastEluSample).utilization;
    this.#lastEluSample = currentElu;
    return utilization > this.#threshold;
  }
}

const backpressure = new BackpressureEngine(0.85);

// -----------------------------------------------------------------------------
// 4. MEMORY-SAFE PAYLOAD PROCESSOR
// -----------------------------------------------------------------------------
function parseSafePayload(buffer) {
  // Parsing payload deterministik tanpa retain buffer ref
  const rawString = buffer.toString('utf8');
  const parsed = JSON.parse(rawString);
  
  // Konstruksi instance dengan struktur monomorphic stabil
  const context = new FastPaymentContext(
    parsed.id || 'N/A',
    typeof parsed.amount === 'number' ? parsed.amount : 0,
    parsed.currency || 'USD'
  );

  if (parsed.audit) {
    context.metadata = parsed.audit; // Tidak mengubah hidden-class struct root
  }
  return context;
}

// -----------------------------------------------------------------------------
// 5. HTTP SERVER DENGAN DISTRIBUTED TELEMETRY & ADAPTIVE SHEDDING
// -----------------------------------------------------------------------------
const server = http.createServer((req, res) => {
  // A. Backpressure Check
  if (backpressure.isSaturated()) {
    res.writeHead(503, { 'Content-Type': 'application/json', 'Retry-After': '1' });
    res.end(JSON.stringify({ error: 'System Capacity Saturated: ELU Exhaustion' }));
    return;
  }

  // B. Span Creation & Context Tracking
  const span = tracer.startSpan('process_payment_request', {
    attributes: {
      'http.method': req.method,
      'http.url': req.url
    }
  });

  const startTime = performance.now();
  const chunks = [];

  req.on('data', (chunk) => {
    chunks.push(chunk);
  });

  req.on('end', () => {
    try {
      const bodyBuffer = Buffer.concat(chunks);
      const paymentCtx = parseSafePayload(bodyBuffer);

      // Core Business Logic (High Speed Math)
      if (paymentCtx.amount > 10_000) {
        paymentCtx.isFlagged = true;
      }

      paymentCtx.processingLatencyMs = performance.now() - startTime;

      // Kirim Respon
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'SUCCESS',
        txId: paymentCtx.transactionId,
        flagged: paymentCtx.isFlagged,
        latency: paymentCtx.processingLatencyMs
      }));

      span.setStatus({ code: opentelemetry.SpanStatusCode.OK });
    } catch (err) {
      span.recordException(err);
      span.setStatus({
        code: opentelemetry.SpanStatusCode.ERROR,
        message: err.message
      });
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid Payload' }));
    } finally {
      span.end();
    }
  });
});

server.listen(3000, () => {
  console.log('[Payment Gateway] Engine running on :3000 under V8 profiling instrumentation');
});
