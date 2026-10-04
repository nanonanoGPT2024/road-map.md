+-------------------------------------------------------------------------------------------------------+
| BROWSER / CLIENT ENVIRONMENT                                                                          |
|                                                                                                       |
|  [ User Interactions ]       [ Application State ]         [ Browser Observer APIs ]                  |
|    (Click, Scroll, Inputs)     (Routing, Redux/Zustand)     (PerformanceObserver, IntersectionObs)   |
|            |                              |                                |                          |
|            +------------------------------+--------------------------------+                          |
|                                           |                                                           |
|                                           v                                                           |
|                       +---------------------------------------+                                       |
|                       |  Type-Safe Tracking Pipeline Gateway  |                                       |
|                       +---------------------------------------+                                       |
|                                           |                                                           |
|               +---------------------------+---------------------------+                               |
|               | Data Enrichment & Sanitization Engine                 |                               |
|               |  - User Identity (Anon Hash)                          |                               |
|               |  - Context Injector (OS, Device, App Version)         |                               |
|               |  - PII Masking & Payload Verification                  |                               |
|               +-------------------------------------------------------+                               |
|                                           |                                                           |
|                                           v                                                           |
|                       +---------------------------------------+                                       |
|                       | Continuous Experimentation Engine     |                                       |
|                       |  - Deterministic MurmurHash3 Layer    |                                       |
|                       |  - Layer/Bucketing/Override Rules     |                                       |
|                       +---------------------------------------+                                       |
|                                           |                                                           |
|                                           v                                                           |
|                       +---------------------------------------+                                       |
|                       | Buffer Manager (IndexedDB / Memory)   |                                       |
|                       |  - Ring Buffer Flush Strategy         |                                       |
|                       |  - Offline-first Retry Circuit Breaker|                                       |
|                       +---------------------------------------+                                       |
|                                           |                                                           |
|                 +-------------------------+-------------------------+                                 |
|                 |                                                   |                                 |
|                 v (Batch Flush / Idle)                              v (Page Dismissal / Emergency)   |
|     +-------------------------+                         +-------------------------+                   |
|     | Web Worker Dispatcher   |                         | Navigator.sendBeacon()  |                   |
|     | (Fetch API via Worker)  |                         | (Zero-blocking Exit)    |                   |
|     +-------------------------+                         +-------------------------+                   |
|                 |                                                   |                                 |
+-----------------|---------------------------------------------------|---------------------------------+
                  |                                                   |
                  +-------------------------+-------------------------+
                                            |
                                            | HTTPS POST (JSON / Protobuf Payload)
                                            v
+-------------------------------------------------------------------------------------------------------+
| CLOUD TELEMETRY & EXPERIMENTATION PLATFORM                                                             |
|                                                                                                       |
|     +----------------------------------+                                                              |
|     | Edge Ingestion Proxy / CDN       |                                                              |
|     +----------------------------------+                                                              |
|                       |                                                                               |
|                       v                                                                               |
|     +----------------------------------+          +---------------------------------------------+     |
|     | Event Bus (Kafka / AWS Kinesis)  | -------> | Real-Time Metrics Validator (SRM Detection) |     |
|     +----------------------------------+          +---------------------------------------------+     |
|                       |                                                                               |
|                       v                                                                               |
|     +----------------------------------+          +---------------------------------------------+     |
|     | Data Lake & Columnar Storage     | -------> | Continuous A/B Testing Engine               |     |
|     | (Snowflake, ClickHouse, BigQuery)|          | (Bayesian / Frequentist Inference Engine)   |     |
|     +----------------------------------+          +---------------------------------------------+     |
+-------------------------------------------------------------------------------------------------------+
