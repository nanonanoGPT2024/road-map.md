/**
 * OpenTelemetry Distributed Tracing & Correlated Structured Logging Simulator
 * Hands-on Lab: BAB 08 - Module 02
 * 
 * Demonstrates:
 * 1. W3C Trace Context Propagation across microservices.
 * 2. Span creation, parent-child nesting, and duration profiling.
 * 3. Structured JSON Logging with correlated trace_id and span_id.
 * 4. Waterfall Gantt Chart visualization and Root-Cause Analysis.
 */

const crypto = require('crypto');

// Generate standard 32-hex trace ID and 16-hex span ID
const genTraceId = () => crypto.randomBytes(16).toString('hex');
const genSpanId = () => crypto.randomBytes(8).toString('hex');

class Span {
  constructor(name, traceId, parentSpanId = null, serviceName = 'unknown') {
    this.name = name;
    this.traceId = traceId;
    this.spanId = genSpanId();
    this.parentSpanId = parentSpanId;
    this.serviceName = serviceName;
    this.startTime = Date.now();
    this.endTime = null;
    this.durationMs = 0;
    this.status = 'OK'; // OK or ERROR
    this.attributes = {};
    this.events = [];
  }

  setAttributes(attrs) {
    Object.assign(this.attributes, attrs);
  }

  recordError(errorMsg) {
    this.status = 'ERROR';
    this.attributes['error.message'] = errorMsg;
  }

  end() {
    this.endTime = Date.now();
    this.durationMs = Math.max(1, this.endTime - this.startTime);
  }
}

class TelemetryCollector {
  constructor() {
    this.spans = [];
    this.logs = [];
  }

  recordSpan(span) {
    this.spans.push(span);
  }

  recordLog(level, message, span, extra = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level: level.toUpperCase(),
      service: span.serviceName,
      trace_id: span.traceId,
      span_id: span.spanId,
      message,
      ...extra
    };
    this.logs.push(logEntry);
  }

  renderWaterfall(traceId) {
    const traceSpans = this.spans.filter(s => s.traceId === traceId);
    if (traceSpans.length === 0) {
      console.log(`No spans found for trace: ${traceId}`);
      return;
    }

    const minStart = Math.min(...traceSpans.map(s => s.startTime));
    const maxEnd = Math.max(...traceSpans.map(s => s.endTime));
    const totalTraceDuration = maxEnd - minStart;

    console.log(`\n======================================================`);
    console.log(`📊 DISTRIBUTED TRACE WATERFALL: ${traceId}`);
    console.log(`Total Duration: ${totalTraceDuration}ms | Total Spans: ${traceSpans.length}`);
    console.log(`======================================================`);

    traceSpans.forEach(span => {
      const offset = span.startTime - minStart;
      const barLength = Math.max(1, Math.round((span.durationMs / totalTraceDuration) * 35));
      const offsetPadding = ' '.repeat(Math.round((offset / totalTraceDuration) * 35));
      const bar = '█'.repeat(barLength);
      const statusIcon = span.status === 'OK' ? '🟢' : '🔴';

      const parentInfo = span.parentSpanId ? `(child of ${span.parentSpanId.slice(0, 6)})` : '(ROOT)';
      console.log(`${statusIcon} [${span.serviceName.padEnd(16)}] ${span.name.padEnd(25)} ${span.durationMs.toString().padStart(4)}ms`);
      console.log(`   ${offsetPadding}${bar} ${parentInfo}`);
    });

    console.log(`======================================================\n`);
  }

  showCorrelatedLogs(traceId) {
    const correlated = this.logs.filter(l => l.trace_id === traceId);
    console.log(`🔎 CORRELATED STRUCTURED JSON LOGS FOR TRACE: ${traceId}`);
    console.log(`Found ${correlated.length} log lines across all microservices:\n`);
    correlated.forEach(l => {
      const color = l.level === 'ERROR' ? '\x1b[31m' : l.level === 'WARN' ? '\x1b[33m' : '\x1b[32m';
      console.log(`${color}${JSON.stringify(l)}\x1b[0m`);
    });
    console.log(`\n------------------------------------------------------`);
  }
}

// -----------------------------------------------------------------
// MICROSERVICES SIMULATION
// -----------------------------------------------------------------
const collector = new TelemetryCollector();

async function simulateTransaction(shouldFail = false) {
  const traceId = genTraceId();

  // 1. API Gateway (Root Span)
  const rootSpan = new Span('HTTP POST /checkout', traceId, null, 'api-gateway');
  collector.recordLog('info', 'Incoming checkout request from client', rootSpan, { client_ip: '203.0.113.19' });
  await new Promise(r => setTimeout(r, 40));

  // W3C Context Injection Header: traceparent: 00-{traceId}-{spanId}-01
  const traceparentHeader = `00-${traceId}-${rootSpan.spanId}-01`;

  // 2. Order Service (Child of API Gateway)
  const orderSpan = new Span('process_order', traceId, rootSpan.spanId, 'order-service');
  collector.recordLog('info', `Order validated. Parsing traceparent: ${traceparentHeader}`, orderSpan);
  await new Promise(r => setTimeout(r, 60));

  // 2a. Database Insert Span
  const dbSpan = new Span('SQL INSERT INTO orders', traceId, orderSpan.spanId, 'order-service');
  dbSpan.setAttributes({ 'db.system': 'postgresql', 'db.statement': 'INSERT INTO orders ...' });
  await new Promise(r => setTimeout(r, 30));
  dbSpan.end();
  collector.recordSpan(dbSpan);

  // 3. Payment Service (Child of Order Service)
  const paymentSpan = new Span('execute_payment_gateway', traceId, orderSpan.spanId, 'payment-service');
  collector.recordLog('info', 'Contacting external Payment Gateway API...', paymentSpan, { amount: 150.00 });

  if (shouldFail) {
    await new Promise(r => setTimeout(r, 120)); // Simulate slow timeout
    paymentSpan.recordError('Payment Provider ETIMEDOUT: Stripe endpoint unreachable after 100ms');
    collector.recordLog('error', 'Critical Payment Failure: Provider timed out', paymentSpan, {
      error_code: 'ETIMEDOUT',
      retry_count: 3
    });
    orderSpan.recordError('Order processing aborted due to upstream payment timeout');
    rootSpan.recordError('HTTP 504 Gateway Timeout');
  } else {
    await new Promise(r => setTimeout(r, 70));
    collector.recordLog('info', 'Payment authorized successfully: TX_992144', paymentSpan);
  }

  paymentSpan.end();
  collector.recordSpan(paymentSpan);

  orderSpan.end();
  collector.recordSpan(orderSpan);

  rootSpan.end();
  collector.recordSpan(rootSpan);

  // Render Telemetry
  collector.renderWaterfall(traceId);
  collector.showCorrelatedLogs(traceId);
}

async function runLab() {
  console.log(`🚀 TEST CASE 1: SUCCESSFUL MULTI-SERVICE DISTRIBUTED TRACE`);
  await simulateTransaction(false);

  console.log(`\n🚀 TEST CASE 2: FAILED DISTRIBUTED TRACE WITH ERROR CORRELATION`);
  await simulateTransaction(true);

  console.log(`🎉 OpenTelemetry Distributed Tracing & Correlated Logging Lab Complete!`);
}

runLab();
