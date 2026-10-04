+----------------------------------------------------------------------------------------------------+
|                                    QUALITY GATES & DEPLOY PIPELINE                                 |
+----------------------------------------------------------------------------------------------------+
       |
       v
+------------------+     Static Checks      +------------------+     Unit & Integration
| Developer Commit | ---------------------> | TypeCheck & Lint | ------------------------+
+------------------+  (ESLint, TS compiler) +------------------+   (Vitest + MSW DOM)    |
                                                                                         v
+---------------------------------------------------------------------------------------------+
| CI Quality Gate Phase 1: Fail Fast                                                          |
|  - Types: 0 Errors       - Bundle Size: < Threshold      - Mutation Score: > 80% (Stryker)  |
+---------------------------------------------------------------------------------------------+
       |
       | Passed
       v
+---------------------------------------------------------------------------------------------+
| CI Quality Gate Phase 2: Hermetic Dynamic Testing                                           |
|  - Playwright E2E Containers (Mocked Identity Provider, Production Build Preview)           |
|  - Visual Regression Testing (Pixelmatch / Lost-Pixel screenshot diffing)                   |
+---------------------------------------------------------------------------------------------+
       |
       | Deployed to Production
       v
+----------------------------------------------------------------------------------------------------+
|                          CLIENT RUNTIME: DISTRIBUTED OBSERVABILITY ARCHITECTURE                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Browser DOM Window ]                                                                            |
|        |                                                                                           |
|        |-- (User Clicks Button)                                                                    |
|        v                                                                                           |
|  [ OpenTelemetry Tracer ] === (Context Propagation) =============================================+ |
|        |                                                                                         | |
|        |-- Generates Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736                                  | |
|        |-- Injects Header: 'traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'| |
|        v                                                                                         | |
|  [ Fetch / XHR Hook ] -----------------------------------------------> [ Backend Gateway API ]   | |
|        |                                                                     |                   | |
|        |-- Logs RUM Metrics                                                  v                   | |
|        |   - INP (Interaction to Next Paint)                   [ Backend Distributed Spans ]     | |
|        |   - Long Animation Frames (LoAF)                                    |                   | |
|        v                                                                     |                   | |
|  [ OTLP Batch Span Processor ]                                               |                   | |
|        |                                                                     |                   | |
|        +---- Export JSON over HTTP/Protobuf ------------------------+        |                   | |
|                                                                     |        |                   | |
+---------------------------------------------------------------------|--------|---------------------+
                                                                      v        v
                                                       +-------------------------------+
                                                       | APM Telemetry Collector (OTel)|
                                                       | (Jaeger / Grafana / Datadog)  |
                                                       +-------------------------------+
