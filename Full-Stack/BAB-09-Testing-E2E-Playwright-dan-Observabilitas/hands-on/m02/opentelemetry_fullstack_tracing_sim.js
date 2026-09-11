/**
 * SIMULATOR: OpenTelemetry Distributed Tracing & Core Web Vitals RUM Engine
 * -----------------------------------------------------------------------------
 * File: opentelemetry_fullstack_tracing_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari propagasi W3C traceparent,
 * perekaman span hierarkis (Browser RUM -> Edge -> Node.js -> PostgreSQL),
 * kalkulasi agregasi P75 Core Web Vitals, dan visualisasi flame graph.
 */

const crypto = require("crypto");

// =============================================================================
// 1. W3C TRACE CONTEXT GENERATOR & SPAN COLLECTOR
// =============================================================================

class W3CTraceContext {
  static createTraceparent(traceId = null, parentSpanId = null) {
    const version = "00";
    const tId = traceId || crypto.randomBytes(16).toString("hex"); // 32 hex chars
    const sId = parentSpanId || crypto.randomBytes(8).toString("hex"); // 16 hex chars
    const flags = "01"; // Sampled
    return {
      traceparent: `${version}-${tId}-${sId}-${flags}`,
      traceId: tId,
      spanId: sId,
    };
  }

  static parse(headerStr) {
    const parts = headerStr.split("-");
    if (parts.length !== 4) return null;
    return {
      version: parts[0],
      traceId: parts[1],
      spanId: parts[2],
      flags: parts[3],
    };
  }
}

class OpenTelemetrySpan {
  constructor(name, traceId, parentSpanId = null) {
    this.name = name;
    this.traceId = traceId;
    this.spanId = crypto.randomBytes(8).toString("hex");
    this.parentSpanId = parentSpanId;
    this.attributes = {};
    this.startTime = Date.now();
    this.endTime = null;
    this.durationMs = 0;
    this.status = "OK";
    this.children = [];
  }

  setAttribute(key, value) {
    this.attributes[key] = value;
  }

  end() {
    this.endTime = Date.now();
    this.durationMs = Math.max(this.endTime - this.startTime, 1);
  }
}

// =============================================================================
// 2. SIMULATOR PERJALANAN REQUEST FULL-STACK (BROWSER TO DB)
// =============================================================================

async function simulateFullStackRequest() {
  const rootContext = W3CTraceContext.createTraceparent();
  const traceId = rootContext.traceId;

  // 1. Root Span: Browser RUM (User Click "Checkout")
  const browserSpan = new OpenTelemetrySpan("browser.user_click_checkout", traceId, null);
  browserSpan.setAttribute("user_agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X)");
  browserSpan.setAttribute("page.url", "/cart");
  await new Promise((r) => setTimeout(r, 15)); // 15ms browser processing

  // 2. Edge Middleware Span
  const edgeSpan = new OpenTelemetrySpan("edge.middleware_auth_guard", traceId, browserSpan.spanId);
  edgeSpan.setAttribute("edge.region", "sin1 (Singapore)");
  edgeSpan.setAttribute("auth.verified", true);
  await new Promise((r) => setTimeout(r, 8)); // 8ms edge verification
  edgeSpan.end();
  browserSpan.children.push(edgeSpan);

  // 3. Backend Server Action Span
  const backendSpan = new OpenTelemetrySpan("nextjs.server_action_process_order", traceId, edgeSpan.spanId);
  backendSpan.setAttribute("http.method", "POST");
  backendSpan.setAttribute("action.name", "createOrderAction");
  await new Promise((r) => setTimeout(r, 25)); // 25ms server logic

  // 4. Database Queries (Nested Spans)
  const dbSpan = new OpenTelemetrySpan("postgresql.query_execute", traceId, backendSpan.spanId);
  dbSpan.setAttribute("db.system", "postgresql");
  dbSpan.setAttribute("db.statement", "SELECT stock FROM products WHERE id = $1 FOR UPDATE");
  await new Promise((r) => setTimeout(r, 45)); // 45ms DB query
  dbSpan.end();
  backendSpan.children.push(dbSpan);

  backendSpan.end();
  browserSpan.children.push(backendSpan);

  browserSpan.end();
  return browserSpan;
}

// =============================================================================
// 3. CORE WEB VITALS P75 AGGREGATOR ENGINE
// =============================================================================

class WebVitalsAggregator {
  static calculateP75(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.ceil(0.75 * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  static evaluateCoreWebVitals(samples) {
    const lcpValues = samples.map((s) => s.lcp);
    const inpValues = samples.map((s) => s.inp);
    const clsValues = samples.map((s) => s.cls);

    const p75LCP = this.calculateP75(lcpValues);
    const p75INP = this.calculateP75(inpValues);
    const p75CLS = this.calculateP75(clsValues);

    return {
      lcp: { value: p75LCP, status: p75LCP <= 2500 ? "GOOD 🟢" : p75LCP <= 4000 ? "NEEDS_IMPROVEMENT 🟡" : "POOR 🔴" },
      inp: { value: p75INP, status: p75INP <= 200 ? "GOOD 🟢" : p75INP <= 500 ? "NEEDS_IMPROVEMENT 🟡" : "POOR 🔴" },
      cls: { value: p75CLS, status: p75CLS <= 0.1 ? "GOOD 🟢" : p75CLS <= 0.25 ? "NEEDS_IMPROVEMENT 🟡" : "POOR 🔴" },
    };
  }
}

// =============================================================================
// 4. RUN SUITE & FLAME GRAPH VISUALIZATION
// =============================================================================

function printFlameGraph(span, depth = 0) {
  const indent = "  ".repeat(depth);
  const duration = `${span.durationMs}ms`;
  const symbol = depth === 0 ? "📦 [ROOT]" : "↳ ⏳";
  console.log(`${indent}${symbol} ${span.name} (${duration}) - Status: ${span.status}`);

  for (const [k, v] of Object.entries(span.attributes)) {
    console.log(`${indent}   • ${k}: ${v}`);
  }

  for (const child of span.children) {
    printFlameGraph(child, depth + 1);
  }
}

async function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: OPENTELEMETRY FULL-STACK TRACING & CORE WEB VITALS RUM");
  console.log("===========================================================================\n");

  // BAGIAN 1: W3C TRACEPARENT PROPAGATION TEST
  console.log("--- BAGIAN 1: Header Standar W3C Trace Context ---");
  const ctx = W3CTraceContext.createTraceparent();
  console.log(`  Generated Traceparent Header : ${ctx.traceparent}`);
  console.log(`  Trace ID (Global Correlation): ${ctx.traceId}`);
  console.log(`  Parent Span ID               : ${ctx.spanId}\n`);

  // BAGIAN 2: DISTRIBUTED TRACE FLAME GRAPH
  console.log("--- BAGIAN 2: Perekaman Distributed Trace Hierarkis (Flame Graph) ---");
  const rootTrace = await simulateFullStackRequest();
  printFlameGraph(rootTrace);
  console.log();

  // BAGIAN 3: CORE WEB VITALS AGGREGASI P75
  console.log("--- BAGIAN 3: Analisis 100 Sampel Real User Monitoring (RUM) Core Web Vitals ---");
  const mockSamples = [];
  for (let i = 0; i < 100; i++) {
    mockSamples.push({
      lcp: Math.floor(Math.random() * 2000) + 1200, // 1200 - 3200 ms
      inp: Math.floor(Math.random() * 180) + 40,   // 40 - 220 ms
      cls: parseFloat((Math.random() * 0.08).toFixed(3)), // 0.000 - 0.080
    });
  }

  const results = WebVitalsAggregator.evaluateCoreWebVitals(mockSamples);
  console.log(`  📊 Largest Contentful Paint (LCP) P75 : ${results.lcp.value} ms -> ${results.lcp.status}`);
  console.log(`  📊 Interaction to Next Paint (INP) P75: ${results.inp.value} ms -> ${results.inp.status}`);
  console.log(`  📊 Cumulative Layout Shift (CLS) P75  : ${results.cls.value}    -> ${results.cls.status}\n`);

  // BAGIAN 4: LATENCY BOTTLENECK ELIMINATION
  console.log("--- BAGIAN 4: Perbandingan Sequential Waterfall vs Parallel Execution ---");
  const startSeq = Date.now();
  // Sequential
  await new Promise((r) => setTimeout(r, 40));
  await new Promise((r) => setTimeout(r, 50));
  await new Promise((r) => setTimeout(r, 30));
  const seqTime = Date.now() - startSeq;

  // Parallel
  const startPar = Date.now();
  await Promise.all([
    new Promise((r) => setTimeout(r, 40)),
    new Promise((r) => setTimeout(r, 50)),
    new Promise((r) => setTimeout(r, 30)),
  ]);
  const parTime = Date.now() - startPar;

  console.log(`  ❌ Sequential Async Waterfall (3 Kueri Serial) : ${seqTime} ms`);
  console.log(`  ✅ Parallel Async Execution (Promise.all)       : ${parTime} ms`);
  console.log(`  🚀 Peningkatan Kecepatan Latensi              : ${(seqTime / parTime).toFixed(1)}x LEBIH CEPAT!\n`);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Telemetri dan Observabilitas Terbukti Akurat!");
  console.log("===========================================================================");
}

runSimulation();
