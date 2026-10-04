+---------------------------------------------------------------------------------------------------+
| CLIENT LAYER (React / React Native Application)                                                   |
|                                                                                                   |
|  [ User Interacting with UI ]                                                                     |
|            |                                                                                      |
|            v                                                                                      |
|  +---------------------------------------------------------------------------------------------+  |
|  | Event Interceptor & Interaction Observer                                                    |  |
|  |  - MutationObserver (DOM Mutations)                                                         |  |
|  |  - Pointer / Touch Event Listeners (Passive)                                                |  |
|  |  - Navigation / Route Transitions                                                           |  |
|  +---------------------------------------------------------------------------------------------+  |
|            |                                                                                      |
|            |-- (Event Detection: e.g., Rapid Sequential Clicks in < 500ms)                        |
|            v                                                                                      |
|  +-------------------------------------+        +----------------------------------------------+  |
|  | Heuristic Engine (In-Memory)        |        | Masking & Sanitization Engine                |  |
|  | Detects:                            |        | Strips:                                      |  |
|  |  - Rage Click (Target Friction)     |------->|  - PII (Email, Phone, Credit Card, Passwords)|  |
|  |  - Dead Click (Unresponsive Element)|        |  - Input element textual values              |  |
|  |  - Error Loop (Retry loop pattern)  |        |  - Cryptographic Hash on Unique Identifiers  |  |
|  +-------------------------------------+        +----------------------------------------------+  |
|            |                                                              |                       |
|            | Contextual Trigger Hit?                                      | Sanitized Events      |
|            v                                                              v                       |
|  +-------------------------------------+        +----------------------------------------------+  |
|  | Dynamic Micro-Survey Trigger Hook   |        | Telemetry Queue Manager                      |  |
|  | (e.g., Mount prompt after 3 rage    |        | (RingBuffer / IndexedDB Persistence)         |  |
|  |  clicks without state change)       |        +----------------------------------------------+  |
|  +-------------------------------------+                                  |                       |
|            |                                                              | Batch Sync            |
+------------|--------------------------------------------------------------|-----------------------+
             | Trigger UI (Modal/Toast)                                     | Web Worker / Beacon
             v                                                              v
+----------------------------------------+        +-------------------------------------------------+
| CLIENT SCREEN / USER PROMPT            |        | HTTP INGESTION GATEWAY                          |
| "Kami mendeteksi kendala pada tombol   |        | (Edge Ingestion Worker / Kafka Producer)        |
| ini. Apa yang Anda harapkan terjadi?"  |        +-------------------------------------------------+
+----------------------------------------+                                  |
             | User Response Data                                           v
             |                                    +-------------------------------------------------+
             +----------------------------------->| ANALYTICS & TELEMETRY AGGREGATOR ENGINE         |
                                                  | - Elasticsearch / ClickHouse (Logs/Metrics)     |
                                                  | - Data Lakehouse (S3 / Parquet)                 |
                                                  | - NLP & Theme Extraction Cluster                |
                                                  +-------------------------------------------------+
                                                                            |
                                                                            v
                                                  +-------------------------------------------------+
                                                  | PROBLEM DISCOVERY DASHBOARD                     |
                                                  | - Correlated "Rage Clicks" vs User Frustration  |
                                                  | - JTBD Opportunity Scoring Matrix               |
                                                  +-------------------------------------------------+
