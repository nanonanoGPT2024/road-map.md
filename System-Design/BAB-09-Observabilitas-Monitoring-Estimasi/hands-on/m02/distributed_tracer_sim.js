/**
 * LAB SIMULATION: Distributed Tracing & W3C Trace Context Propagation
 * 
 * Mensimulasikan arsitektur OpenTelemetry:
 * 1. Menghasilkan TraceID & SpanID unik.
 * 2. Propagasi header W3C 'traceparent' antar microservices virtual.
 * 3. Membentuk relasi hierarkis Parent-Child Spans.
 * 4. Merender visualisasi Waterfall / Flame Graph ASCII untuk mendeteksi bottleneck!
 */

const crypto = require("crypto");

class DistributedTracer {
  constructor() {
    this.completedSpans = [];
  }

  generateHex(bytes) {
    return crypto.randomBytes(bytes).toString("hex");
  }

  createRootTrace(name, serviceName) {
    const traceId = this.generateHex(16); // 128-bit
    const spanId = this.generateHex(8);   // 64-bit
    const span = {
      traceId,
      spanId,
      parentSpanId: null,
      name,
      serviceName,
      startTime: Date.now(),
      endTime: null,
      durationMs: 0,
      tags: {}
    };
    return span;
  }

  createChildSpan(name, serviceName, parentTraceparent) {
    // Parse W3C traceparent: version-trace_id-parent_id-trace_flags
    const parts = parentTraceparent.split("-");
    const traceId = parts[1];
    const parentSpanId = parts[2];
    const spanId = this.generateHex(8);

    const span = {
      traceId,
      spanId,
      parentSpanId,
      name,
      serviceName,
      startTime: Date.now(),
      endTime: null,
      durationMs: 0,
      tags: {}
    };
    return span;
  }

  serializeTraceparent(span) {
    return `00-${span.traceId}-${span.spanId}-01`;
  }

  endSpan(span, durationMs, tags = {}) {
    span.endTime = span.startTime + durationMs;
    span.durationMs = durationMs;
    span.tags = tags;
    this.completedSpans.push(span);
  }

  renderWaterfall() {
    console.log("\n===================================================================");
    console.log("📊 DISTRIBUTED TRACE FLAME GRAPH / WATERFALL TIMELINE");
    console.log("===================================================================");
    
    if (this.completedSpans.length === 0) return;
    const rootSpan = this.completedSpans.find(s => s.parentSpanId === null);
    const traceId = rootSpan ? rootSpan.traceId : this.completedSpans[0].traceId;
    const totalDuration = rootSpan ? rootSpan.durationMs : 1;

    console.log(`Trace ID : ${traceId}`);
    console.log(`Total Dur: ${totalDuration} ms\n`);

    for (const span of this.completedSpans) {
      const barLength = Math.max(1, Math.round((span.durationMs / totalDuration) * 40));
      const bar = "█".repeat(barLength);
      const isBottleneck = span.durationMs > totalDuration * 0.4 ? " 🔥 [BOTTLENECK!]" : "";
      const status = span.tags.error ? " ❌ (ERROR)" : " ✅ (OK)";
      
      const indent = span.parentSpanId ? "  └─ " : "";
      console.log(`${(indent + "[" + span.serviceName + ": " + span.name + "]").padEnd(38)} | ${bar} ${span.durationMs}ms${status}${isBottleneck}`);
    }
    console.log("===================================================================\n");
  }
}

// ======================= SIMULASI RANTAI PANGGILAN =======================
const tracer = new DistributedTracer();

async function simulateDistributedCheckout() {
  console.log("🚀 User menekan tombol 'BAYAR SEKARANG' (POST /api/v1/checkout)...");

  // 1. API GATEWAY (Root Span)
  const rootSpan = tracer.createRootTrace("HTTP POST /checkout", "api-gateway");
  const gwTraceparent = tracer.serializeTraceparent(rootSpan);
  console.log(`[API Gateway] Menerbitkan W3C traceparent: ${gwTraceparent}`);

  // 2. ORDER SERVICE
  const orderSpan = tracer.createChildSpan("CreateOrderRecord", "order-service", gwTraceparent);
  const orderTraceparent = tracer.serializeTraceparent(orderSpan);

  // 3. INVENTORY SERVICE (Cek Stok)
  const inventorySpan = tracer.createChildSpan("ReserveInventoryItem", "inventory-service", orderTraceparent);
  tracer.endSpan(inventorySpan, 45, { item_id: "SKU-990", reserved: true });

  // 4. PAYMENT SERVICE (Panggilan ke Bank / Core Ledger)
  const paymentSpan = tracer.createChildSpan("ChargeCreditCard", "payment-service", orderTraceparent);
  const paymentTraceparent = tracer.serializeTraceparent(paymentSpan);

  // 5. DATABASE QUERY DI PAYMENT SERVICE (Simulasi Bottleneck Disk I/O!)
  const dbSpan = tracer.createChildSpan("SQL: UPDATE accounts SET balance...", "postgres-db", paymentTraceparent);
  tracer.endSpan(dbSpan, 520, { query: "UPDATE accounts", rows_affected: 1 }); // 520ms! Lambat!

  // Akhiri Payment Span
  tracer.endSpan(paymentSpan, 580, { payment_status: "SUCCESS" });

  // Akhiri Order Span
  tracer.endSpan(orderSpan, 650, { order_id: "ORD-2026-9081" });

  // Akhiri Root Gateway Span
  tracer.endSpan(rootSpan, 720, { http_status: 200 });

  // Render Visualisasi Waterfall
  tracer.renderWaterfall();

  console.log(" Diagnosa Otomatis Tracing:");
  console.log("1. Dari total latensi 720ms, sebesar 520ms (72%) dihabiskan pada Postgres DB di Payment Service.");
  console.log("2. Tindakan Solusi Arsitektur: Pasang connection pool pgbouncer atau optimasi disk lock contention pada row akun!");
}

simulateDistributedCheckout();
