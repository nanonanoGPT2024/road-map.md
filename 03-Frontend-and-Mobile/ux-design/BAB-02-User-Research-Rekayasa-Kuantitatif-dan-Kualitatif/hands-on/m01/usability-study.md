+---------------------------------------------------------------------------------------+
| SISI KLIEN (PERAMBAN PENGGUNA)                                                        |
|                                                                                       |
|   +-----------------------+        +----------------------------------------------+   |
|   |   Interaksi User      |        | Performance Observer API                     |   |
|   | (Pointer, Input, Nav) |        | (Long Tasks, INP, FID, CLS)                  |   |
|   +-----------+-----------+        +----------------------+-----------------------+   |
|               |                                           |                           |
|               | (DOM Events: click, input, scroll)        | (Layout Shift & Latency)  |
|               v                                           v                           |
|   +-------------------------------------------------------------------------------+   |
|   | Rekayasa Sensor: UX Telemetry Engine (Custom React Hook / Vanilla Wrapper)     |   |
|   | - Debounced Event Normalizer                                                  |   |
|   | - Heuristic Micro-Behavior Detectors (Rage Click, Dead Click, Thrashing)      |   |
|   +-------------------+-----------------------------------+-----------------------+   |
|                       |                                   |                           |
|      (Anomali Terdeteksi: Threshold Breach)               | (Batching Metrik)         |
|                       v                                   v                           |
|   +-----------------------------------+   +---------------------------------------+   |
|   | Micro-Survey Controller           |   | Telemetry Event Queue (IndexedDB/RAM) |   |
|   | Trigger Form Kualitatif Interaktif|   +-------------------+-------------------+   |
|   | (Contextual Think-Aloud Probe)    |                       |                       |
|   +-------------------+---------------+                       | navigator.sendBeacon  |
+-----------------------|---------------------------------------|-----------------------+
                        |                                       | Web Worker Async Sync
                        | Respon Kualitatif                     | Payload Kuantitatif
                        v                                       v
+---------------------------------------------------------------------------------------+
| BACKEND & PIPELINE ANALITIK                                                           |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   | Edge Ingestion Gateway (HTTP API / Cloudflare Workers / Kafka Producer)       |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|                                           v                                           |
|   +-------------------------------------------------------------------------------+   |
|   | Streaming Analytics Core & ETL Pipeline                                       |   |
|   | - Parser Skema Event & Metadata Session                                       |   |
|   | - Korelator: ID Sesi Kuantitatif <---> Log Respon Kualitatif                  |   |
|   +-------------------+-----------------------------------+-----------------------+   |
|                       |                                   |                           |
|                       v                                   v                           |
|   +-----------------------------------+   +---------------------------------------+   |
|   | ClickHouse / TimescaleDB          |   | Elasticsearch / Vector DB             |   |
|   | (Data Deret Waktu & Metrik UX)    |   | (Transkrip Kualitatif & Analisis Teks)|   |
|   +-------------------+---------------+   +-------------------+-------------------+   |
|                       \                                   /                           |
|                        \                                 /                            |
|                         v                               v                             |
|   +-------------------------------------------------------------------------------+   |
|   | Automated Usability Evaluation Dashboard & Statistical Processing Engine      |   |
|   | - Uji Korelasi Mann-Whitney U, Perhitungan Skor SUS, Deteksi Regresi UI       |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
