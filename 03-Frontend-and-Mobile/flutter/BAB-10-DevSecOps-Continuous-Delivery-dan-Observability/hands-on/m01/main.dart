PIPELINE DEVSECOPS & CONTINUOUS DELIVERY
                                      
  [Developer Machine]
          │
          ├─► git push origin feature/fintech-core
          ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GITHUB ACTIONS / CI RUNNER (ISOLATED EPHEMERAL CONTAINER)                                     │
│                                                                                                │
│  PHASE 1: SECURE LINT & STATIC ANALYSIS (PARALLEL EXECUTION)                                   │
│  ┌────────────────────────┐  ┌────────────────────────┐  ┌──────────────────────────────────┐  │
│  │ Gitleaks / TruffleHog  │  │ Flutter Analyze        │  │ OSV-Scanner / Nancy              │  │
│  │ (Zero-Trust Scan Token)│  │ (Custom Strict Rules)  │  │ (pubspec.lock CVE Audit)         │  │
│  └───────────┬────────────┘  └───────────┬────────────┘  └────────────────┬─────────────────┘  │
│              └───────────────────────────┼────────────────────────────────┘                    │
│                                          ▼                                                     │
│  PHASE 2: DETERMINISTIC TESTING & INTEGRATION COVERAGE                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ - Unit, Widget & Golden Contract Tests (flutter test --coverage)                         │  │
│  │ - Enforcement: Minimum Line Coverage >= 85%, Zero Floating-point Golden Pixel Diff      │  │
│  └───────────────────────────────────────┬──────────────────────────────────────────────────┘  │
│                                          ▼                                                     │
│  PHASE 3: SECURE BUILD, HARDENING, & SBOM GENERATION                                           │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ - Inject Keystore / Apple App Store Provisioning via Vault / Match                       │  │
│  │ - ProGuard / R8 Rule Optimization + NDK Strip Symbols                                    │  │
│  │ - Obfuscation Flag: --obfuscate --split-debug-info=./v1.0.0-symbols                      │  │
│  │ - CycloneDX: Generasi SBOM (Software Bill of Materials)                                  │  │
│  └───────────────────────────────────────┬──────────────────────────────────────────────────┘  │
│                                          │                                                     │
│                  ┌───────────────────────┴───────────────────────┐                             │
│                  ▼                                               ▼                             │
│  [Android Target: AAB]                           [iOS Target: IPA]                             │
│  - Keystore Signer (v2/v3 scheme)                - Fastlane Match (Enterprise Keychain)       │
│  - Upload Mapping File ke Sentry                 - Upload dSYM Symbols ke Sentry               │
└──────────────────┬───────────────────────────────────────────────┬─────────────────────────────┘
                   │                                               │
                   ▼                                               ▼
┌──────────────────────────────────────┐       ┌─────────────────────────────────────────────────┐
│ Google Play Console                  │       │ Apple App Store Connect                         │
│ (Internal Testing Track)             │       │ (TestFlight Distribution Track)                 │
└──────────────────┬───────────────────┘       └───────────────────┬─────────────────────────────┘
                   │                                               │
                   └───────────────────────┬───────────────────────┘
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ RUNTIME OBSERVABILITY & TELEMETRY MESH (END-USER RUNTIME)                                      │
│                                                                                                │
│   Flutter App (Dart Engine) ───[Zone / Platform Channel]───► Native Layer (C++ / ObjC / Kotlin)│
│              │                                                                │                │
│              ├─► Structured Logger (PII Masking Filter Engine)               │                │
│              ├─► OpenTelemetry Trace Exporter (W3C Header Traceparent)        │                │
│              └─► Sentry SDK Hub ──(Crash, ANR, Native Signal, Memory Dump)────┘                │
│                         │                                                                      │
│                         ▼ (Encrypted HTTPS Pipeline)                                           │
│          ┌─────────────────────────────┐                                                       │
│          │ Sentry / Datadog / OTel APM │                                                       │
│          └─────────────────────────────┘                                                       │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
