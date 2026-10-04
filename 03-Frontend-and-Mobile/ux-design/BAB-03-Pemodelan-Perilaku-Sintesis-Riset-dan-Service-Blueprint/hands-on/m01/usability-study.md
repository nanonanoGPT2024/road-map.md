+====================================================================================================+
|                                    SERVICE BLUEPRINT ARCHITECTURE                                  |
+====================================================================================================+
| LAYER 1: PHYSICAL EVIDENCE (Bukti Fisik / Artefak UI)                                              |
|  [ Push Notification ]       [ Push-to-Pay Form Modal ]        [ Animated Skeleton / Optimistic UI]|
+----------------------------------------------------------------------------------------------------+
                                               │ (Melihat/Merespons)
                                               ▼
+----------------------------------------------------------------------------------------------------+
| LAYER 2: CUSTOMER ACTIONS (Alur Perilaku Pengguna / Client FSM)                                    |
|  [ Terima Notifikasi Tagihan ] ──► [ Klik Tombol "Bayar Cepat" ] ──► [ Konfirmasi Biometrik ]      |
+====================================================================================================+
| ---------------------------------- LINE OF INTERACTION ------------------------------------------- |
+====================================================================================================+
| LAYER 3: FRONTSTAGE ACTIONS (Komponen Frontend / Web Client Engine)                                |
|  - Render Biometric Prompt WebAuthn API                                                            |
|  - Validasi Payload Klien (Zod Schema Validation)                                                  |
|  - Dispatch Telemetry Interaction Event: `PAYMENT_SUBMITTED`                                       |
+====================================================================================================+
| ---------------------------------- LINE OF VISIBILITY -------------------------------------------- |
+====================================================================================================+
| LAYER 4: BACKSTAGE ACTIONS (API Gateway & Backend For Frontend / BFF)                              |
|  - API Gateway: Rate Limiting & Auth Token Decryption                                              |
|  - BFF: Orkestrasi Payload Transaksi                                                               |
|  - Idempotency Key Validation Engine (Redis Lock)                                                  |
+====================================================================================================+
| ------------------------------ LINE OF INTERNAL INTERACTION -------------------------------------- |
+====================================================================================================+
| LAYER 5: SUPPORT PROCESSES (Layanan Inti Terdistribusi & Database)                                 |
|  - Core Banking Transaction Engine (Distributed Ledger)                                            |
|  - Fraud Detection System (ML Event Stream via Apache Kafka)                                       |
|  - SMS/WhatsApp Notification Gateway (Third-Party Provider)                                        |
+====================================================================================================+
| LAYER 6: OBSERVABILITY & TELEMETRY STREAM                                                          |
|  - Web Vitals Tracking (INP, LCP)                                                                  |
|  - Sentry Distributed Tracing (Span ID Propagation)                                                |
|  - OpenTelemetry Collector ──► ClickHouse / Datadog Dashboard                                      |
+====================================================================================================+
