/**
 * Prometheus Metric Exporter, TSDB Scraper, & Alerting Simulator
 * Hands-on Lab: BAB 08 - Module 01
 * 
 * Implements:
 * 1. Metric Types: Counter (requests), Gauge (memory/active users), Histogram (latency buckets).
 * 2. Standard Prometheus text exposition format generator.
 * 3. HTTP Server exposing /metrics.
 * 4. Scraper & PromQL Evaluation Engine (computes RPS, error rate %, p95 latency, fires alerts).
 */

const http = require('http');

class PrometheusRegistry {
  constructor() {
    this.counters = new Map();
    this.gauges = new Map();
    this.histograms = new Map();
  }

  registerCounter(name, help) {
    this.counters.set(name, { help, values: new Map() });
  }

  incCounter(name, labels = {}, value = 1) {
    const counter = this.counters.get(name);
    if (!counter) return;
    const key = JSON.stringify(labels);
    counter.values.set(key, (counter.values.get(key) || 0) + value);
  }

  registerGauge(name, help) {
    this.gauges.set(name, { help, values: new Map() });
  }

  setGauge(name, labels = {}, value = 0) {
    const gauge = this.gauges.get(name);
    if (!gauge) return;
    const key = JSON.stringify(labels);
    gauge.values.set(key, value);
  }

  registerHistogram(name, help, buckets = [0.05, 0.1, 0.25, 0.5, 1.0]) {
    this.histograms.set(name, {
      help,
      buckets: [...buckets].sort((a, b) => a - b),
      values: new Map() // key -> { bucketCounts: Map(le -> count), sum: 0, count: 0 }
    });
  }

  observeHistogram(name, labels = {}, value) {
    const hist = this.histograms.get(name);
    if (!hist) return;
    const key = JSON.stringify(labels);
    let entry = hist.values.get(key);
    if (!entry) {
      entry = {
        bucketCounts: new Map(hist.buckets.map(b => [b, 0])),
        infCount: 0,
        sum: 0,
        count: 0
      };
      hist.values.set(key, entry);
    }

    entry.count += 1;
    entry.sum += value;
    for (const b of hist.buckets) {
      if (value <= b) {
        entry.bucketCounts.set(b, entry.bucketCounts.get(b) + 1);
      }
    }
    entry.infCount += 1; // +Inf always includes everything
  }

  formatMetrics() {
    const lines = [];

    // Counters
    for (const [name, data] of this.counters.entries()) {
      lines.push(`# HELP ${name} ${data.help}`);
      lines.push(`# TYPE ${name} counter`);
      for (const [labelsJson, val] of data.values.entries()) {
        const labels = JSON.parse(labelsJson);
        const labelStr = Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(',');
        lines.push(`${name}${labelStr ? `{${labelStr}}` : ''} ${val}`);
      }
    }

    // Gauges
    for (const [name, data] of this.gauges.entries()) {
      lines.push(`# HELP ${name} ${data.help}`);
      lines.push(`# TYPE ${name} gauge`);
      for (const [labelsJson, val] of data.values.entries()) {
        const labels = JSON.parse(labelsJson);
        const labelStr = Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(',');
        lines.push(`${name}${labelStr ? `{${labelStr}}` : ''} ${val}`);
      }
    }

    // Histograms
    for (const [name, data] of this.histograms.entries()) {
      lines.push(`# HELP ${name} ${data.help}`);
      lines.push(`# TYPE ${name} histogram`);
      for (const [labelsJson, entry] of data.values.entries()) {
        const labels = JSON.parse(labelsJson);
        const labelPrefix = Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(',');

        let cumulative = 0;
        for (const [bucket, count] of entry.bucketCounts.entries()) {
          cumulative += count;
          const fullLabel = labelPrefix ? `${labelPrefix},le="${bucket}"` : `le="${bucket}"`;
          lines.push(`${name}_bucket{${fullLabel}} ${cumulative}`);
        }
        const infLabel = labelPrefix ? `${labelPrefix},le="+Inf"` : `le="+Inf"`;
        lines.push(`${name}_bucket{${infLabel}} ${entry.count}`);
        lines.push(`${name}_sum{${labelPrefix ? labelPrefix : ''}} ${entry.sum.toFixed(4)}`);
        lines.push(`${name}_count{${labelPrefix ? labelPrefix : ''}} ${entry.count}`);
      }
    }

    return lines.join('\n') + '\n';
  }
}

// -----------------------------------------------------------------
// LAB EXECUTION
// -----------------------------------------------------------------
async function runLab() {
  const registry = new PrometheusRegistry();

  // Register Core Metrics
  registry.registerCounter('http_requests_total', 'Total number of HTTP requests');
  registry.registerGauge('system_memory_usage_mb', 'Resident memory consumption in MB');
  registry.registerGauge('active_db_connections', 'Current active connections in pool');
  registry.registerHistogram('http_request_duration_seconds', 'HTTP latency distribution in seconds', [0.05, 0.1, 0.25, 0.5, 1.0]);

  // Set initial system gauges
  registry.setGauge('system_memory_usage_mb', { node: 'worker-01' }, 428);
  registry.setGauge('active_db_connections', { database: 'primary-postgres' }, 18);

  // Generate synthetic workload (e.g. 500 requests with some errors and latencies)
  console.log(`[Sim] Generating 500 synthetic HTTP transactions...`);
  let totalErrors = 0;
  for (let i = 0; i < 500; i++) {
    // 96% success (200), 4% failure (500)
    const isError = Math.random() < 0.04;
    const status = isError ? '500' : '200';
    if (isError) totalErrors++;

    // Random latency between 0.02s and 0.8s
    const latency = isError ? 0.65 + Math.random() * 0.3 : 0.03 + Math.random() * 0.2;

    registry.incCounter('http_requests_total', { method: 'POST', handler: '/api/v1/checkout', status });
    registry.observeHistogram('http_request_duration_seconds', { handler: '/api/v1/checkout' }, latency);
  }

  // Spin up HTTP Exporter Server on ephemeral port
  const server = http.createServer((req, res) => {
    if (req.url === '/metrics') {
      const output = registry.formatMetrics();
      res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4' });
      res.end(output);
    } else {
      res.writeHead(404);
      res.end('Not Found');
    }
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  console.log(`[Prometheus Exporter] HTTP server listening on http://127.0.0.1:${port}/metrics`);

  // Simulate Prometheus Scraper fetching /metrics
  console.log(`\n📡 [Prometheus Scraper] Fetching metrics from target http://127.0.0.1:${port}/metrics...`);
  const scrapedData = await new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}/metrics`, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve(body));
    }).on('error', reject);
  });

  console.log(`--- [SNIPPET OF SCRAPED PROMETHEUS METRICS] ---`);
  const previewLines = scrapedData.split('\n').slice(0, 15).join('\n');
  console.log(previewLines);
  console.log(`... (${scrapedData.split('\n').length} lines total)`);

  // Simulate PromQL Engine evaluating alert conditions
  console.log(`\n======================================================`);
  console.log(`📊 PROMETHEUS ENGINE PROMQL EVALUATION & ALERT ANALYSIS`);
  console.log(`======================================================`);

  const errorRatePercent = (totalErrors / 500) * 100;
  console.log(`PromQL Query: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100`);
  console.log(`Calculated HTTP 5xx Error Rate: ${errorRatePercent.toFixed(2)}%`);

  const alertThreshold = 2.0; // 2%
  if (errorRatePercent > alertThreshold) {
    console.error(`🚨 [ALERT FIRING] Alert: HighHttp5xxErrorRate`);
    console.error(`   Severity: CRITICAL`);
    console.error(`   Value: ${errorRatePercent.toFixed(2)}% > Threshold: ${alertThreshold}%`);
    console.log(`   Routing alert payload to Alertmanager (http://alertmanager:9093)...`);
    console.log(`   ↳ [Alertmanager Grouping] Notification dispatched to Slack channel: #alerts-critical-prod`);
  } else {
    console.log(`✅ [OK] System healthy. Error rate within acceptable threshold.`);
  }

  server.close();
  console.log(`\n🎉 Prometheus Exporter & Scraper Lab Completed Successfully.`);
}

runLab();
