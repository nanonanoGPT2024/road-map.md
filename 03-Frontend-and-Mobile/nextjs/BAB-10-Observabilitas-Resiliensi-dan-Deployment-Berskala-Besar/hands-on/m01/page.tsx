+----------------------------------------------------------------------------------------------------+
|                                    INCOMING TRAFFIC / USERS                                        |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
                        +───────────────────────────────────────────────────+
                        |      Global Edge / Cloud Ingress (Cloudflare)     |
                        |      Injects: traceparent, x-request-id           |
                        +───────────────────────────────────────────────────+
                                                  │
                                                  ▼
+────────────────────────────────────────────────────────────────────────────────────────────────────+
| KUBERNETES CLUSTER (INGRESS-NGINX / TRAEFIK)                                                       |
|                                                                                                    |
| Routing: Round-Robin / Canary Weight                                                               |
+────────────────────────────────────────────────────────────────────────────────────────────────────+
         │                                                           │
         ▼ (Stable Pods - 90%)                                       ▼ (Canary Pods - 10%)
+───────────────────────────────────+                       +───────────────────────────────────+
| Pod: nextjs-app-stable            |                       | Pod: nextjs-app-canary            |
| +───────────────────────────────+ |                       | +───────────────────────────────+ |
| | Middleware (Edge/Node Runtime)| |                       | | Middleware (Edge/Node Runtime)| |
| | - Context Propagation         | |                       | | - Context Propagation         | |
| +───────────────┬───────────────+ |                       +───────────────┬───────────────+ |
|                 ▼                 |                       |                 ▼                 |
| | Server Components Engine      | |                       | | Server Components Engine      | |
| | - Custom Tracing Spans        | |                       | | - Custom Tracing Spans        | |
| | - Winston/Pino Logger         | |                       | | - Winston/Pino Logger         | |
| +───────────────┬───────────────+ |                       +───────────────┬───────────────+ |
|                 ▼                 |                       |                 ▼                 |
| | Resilience Layer              | |                       | | Resilience Layer              | |
| | - Opossum Circuit Breakers    | |                       | | - Opossum Circuit Breakers    | |
| | - Exponential Backoff         | |                       | | - Exponential Backoff         | |
| +───────────────┬───────────────+ |                       +───────────────┬───────────────+ |
|                 │                 |                       |                 │                 |
| Probes:         │                 |                       | Probes:         │                 |
| - /api/health/liveness            |                       | - /api/health/liveness            |
| - /api/health/readiness           |                       | - /api/health/readiness           |
| - /metrics (Prometheus Exporter)  |                       | - /metrics (Prometheus Exporter)  |
+─────────────────┼─────────────────+                       +─────────────────┼─────────────────+
                  │                                                           │
                  └─────────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                     +─────────────────────────────────────────────────────+
                     | OpenTelemetry OTLP Exporter (gRPC / HTTP/Protobuf)  |
                     +─────────────────────────────────────────────────────+
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
+───────────────────────────────────+                         +───────────────────────────────────+
|   OTel Collector DaemonSet / Pod  |                         |    Prometheus Server (Scrape)     |
|   - Tail-based Sampling Processor |                         |    - Scraping /metrics endpoint   |
|   - Redaction & Transformation    |                         |    - Alerts via Alertmanager      |
+─────────────────┬─────────────────+                         +───────────────────────────────────+
                  │
     ┌────────────┴────────────┐
     ▼                         ▼
+───────────────+      +────────────────+
| Datadog /     |      | ElasticSearch/ |
| Jaeger / Tempo|      | Loki (Logs)    |
+───────────────+      +────────────────+
