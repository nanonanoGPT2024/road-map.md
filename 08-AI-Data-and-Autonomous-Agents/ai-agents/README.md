# Enterprise AI Agents Engineering: Dari Fondasi Teoretis Hingga Produksi Skala Besar

Selamat datang di kurikulum teknis definitif **AI Agents** (berdasarkan roadmap resmi `roadmap.sh/ai-agents`). Kurikulum ini dirancang untuk insinyur perangkat lunak senior, arsitek sistem, dan peneliti AI yang ingin beralih dari sekadar memanggil API model bahasa (LLM wrappers) ke pembangunan sistem otonom adaptif (*agentic systems*) yang deterministik, aman, dan siap produksi.

---

## 1. Course Overview & Mindset

### Paradigma: Software 3.0 & Pergeseran Agentik
Pembangunan AI Agent bukan sekadar rekayasa prompt (*prompt engineering*), melainkan rekayasa sistem perangkat lunak terdistribusi. LLM berfungsi sebagai Unit Pemroses Penalaran (*Reasoning Engine*), bukan basis data penyimpanan pengetahuan absolut. 

Pergeseran mendasar dalam kursus ini mencakup:
* **Dari Determinisme Statis ke Probabilistik Terkendali**: Mengendalikan model stokastik menggunakan *finite state machines*, *cyclic graphs*, dan validasi skema berbasis kontrak ketat.
* **Dari Komputasi Sekuensial ke Eksekusi Otonom**: Memberikan kapabilitas persepsi, pemecahan masalah dekomposisi (*planning*), pemilihan alat (*tool execution*), dan evaluasi mandiri (*self-reflection*).
* **Engineering Over Voodoo**: Mengeliminasi ketergantungan pada prompt rapuh dengan menerapkan *Structured Outputs*, isolasi *sandbox* eksekusi kode, sistem evaluasi berbasis metrik (*LLM-as-a-Judge*), serta observabilitas tingkat rendah (*distributed tracing*).

---

## 2. Learning Roadmap

```text
AI Agents Engineering Mastery
│
├── BAB 01: Fondasi Arsitektur AI Agent & Pola Kognitif
│   ├── Modul 01: Primitif Agentik & Siklus Persepsi-Aksi
│   ├── Modul 02: Pola Penalaran: ReAct, Plan-and-Solve, & Reflexion
│   └── Modul 03: Dekomposisi Tugas & Self-Correction Loops
│
├── BAB 02: Structured Outputs & Advanced Schema Engineering
│   ├── Modul 01: Native Function Calling vs Schema Constrained Decoding
│   ├── Modul 02: Validasi Tipe Keras dengan Pydantic & Instructor
│   └── Modul 03: Handling Streaming JSON, Reparasi Skema, & Fallback
│
├── BAB 03: Tool Use, Actions, & Model Context Protocol (MCP)
│   ├── Modul 01: Tool Binding & Deterministic Execution Sandboxing
│   ├── Modul 02: Model Context Protocol (MCP) Architecture
│   └── Modul 03: Dynamic Tool Discovery & Semantic Routing
│
├── BAB 04: Sistem Memori Agentik: State, Context, & Vector-Graph RAG
│   ├── Modul 01: Memori Jangka Pendek & Context Window Management
│   ├── Modul 02: Memori Episodik & Semantik Berbasis Vektor
│   └── Modul 03: GraphRAG & Entity Memory Networks
│
├── BAB 05: Arsitektur Multi-Agent & Sistem Orkestrasi Kolaboratif
│   ├── Modul 01: Pola Topologi: Hierarkis, Supervisor, & Swarm (P2P)
│   ├── Modul 02: Protokol Komunikasi Antar-Agent (A2A) & Negosiasi
│   └── Modul 03: Debat Multi-Agent, Konsensus, & Red Teaming
│
├── BAB 06: Deterministic Control Flow & State Graphs
│   ├── Modul 01: Directed Acyclic Graph (DAG) vs Cyclical State Machines
│   ├── Modul 02: Human-in-the-Loop (HITL), Interupsi, & Persistensi State
│   └── Modul 03: Time-Travel Debugging & Checkpointing Architecture
│
├── BAB 07: Eksekusi Otonom: Code Interpreters & Web Browsing Agents
│   ├── Modul 01: Isolated Sandbox Runtime (gVisor/Wasm/Firecracker)
│   ├── Modul 02: Web Navigation via Chrome DevTools Protocol & Playwright
│   └── Modul 03: Grounding Multimodal: Visual Parsing & Action Grounding
│
├── BAB 08: Observabilitas, Evaluasi, & Tracing Sistem Agentik
│   ├── Modul 01: Distributed Tracing & Instrumentation (OpenInference)
│   ├── Modul 02: Metrik Evaluasi: Trajectory, RAG Triad, & Tool-Use Accuracy
│   └── Modul 03: Evaluasi Otomatis Skala Besar Menggunakan LLM-as-a-Judge
│
├── BAB 09: Keamanan Agentik, Sandboxing, & Guardrails Pertahanan
│   ├── Modul 01: Prompt Injection, Jailbreaking, & Tool Privilege Escalation
│   ├── Modul 02: Input/Output Guardrails Dinamis (NeMo, Llama Guard)
│   └── Modul 03: Prinsip Zero-Trust, Least Privilege, & Policy Enforcement
│
└── BAB 10: Produksi Skala Besar, Serving, & Event-Driven Agentic System
    ├── Modul 01: Asynchronous Agent Loops & Concurrency Engineering
    ├── Modul 02: Arsitektur Event-Driven Menggunakan Kafka/Redis Streams
    └── Modul 03: Strategi Deployment, Rate-Limiting, Caching, & Fault Tolerance
```

---

## 3. Navigasi Detail Kurikulum

### [BAB 01: Fondasi Arsitektur AI Agent & Pola Kognitif](./bab-01-fondasi-arsitektur-ai-agent/)
Membedah arsitektur dasar agen otonom dari sudut pandang rekayasa kognitif dan ilmu komputer.
* [Modul 01: Primitif Agentik & Siklus Persepsi-Aksi](./bab-01-fondasi-arsitektur-ai-agent/01-primitif-agentik-siklus-persepsi-aksi.md)
* [Modul 02: Pola Penalaran: ReAct, Plan-and-Solve, & Reflexion](./bab-01-fondasi-arsitektur-ai-agent/02-pola-penalaran-react-plan-and-solve-reflexion.md)
* [Modul 03: Dekomposisi Tugas & Self-Correction Loops](./bab-01-fondasi-arsitektur-ai-agent/03-dekomposisi-tugas-self-correction-loops.md)

### [BAB 02: Structured Outputs & Advanced Schema Engineering](./bab-02-structured-outputs-schema-engineering/)
Teknik memaksa model stokastik menghasilkan representasi data yang deterministik, kompatibel dengan API, dan terverifikasi secara matematis.
* [Modul 01: Native Function Calling vs Schema Constrained Decoding](./bab-02-structured-outputs-schema-engineering/01-native-function-calling-constrained-decoding.md)
* [Modul 02: Validasi Tipe Keras dengan Pydantic & Instructor](./bab-02-structured-outputs-schema-engineering/02-validasi-tipe-keras-pydantic-instructor.md)
* [Modul 03: Handling Streaming JSON, Reparasi Skema, & Fallback](./bab-02-structured-outputs-schema-engineering/03-streaming-json-reparasi-skema-fallback.md)

### [BAB 03: Tool Use, Actions, & Model Context Protocol (MCP)](./bab-03-tool-use-actions-mcp/)
Membangun antarmuka interaksi agen dengan ekosistem luar menggunakan standar protokol modern.
* [Modul 01: Tool Binding & Deterministic Execution Sandboxing](./bab-03-tool-use-actions-mcp/01-tool-binding-deterministic-sandboxing.md)
* [Modul 02: Model Context Protocol (MCP) Architecture](./bab-03-tool-use-actions-mcp/02-model-context-protocol-mcp-architecture.md)
* [Modul 03: Dynamic Tool Discovery & Semantic Routing](./bab-03-tool-use-actions-mcp/03-dynamic-tool-discovery-semantic-routing.md)

### [BAB 04: Sistem Memori Agentik: State, Context, & Vector-Graph RAG](./bab-04-sistem-memori-agentik/)
Rekayasa penyimpanan data kontekstual: memisahkan memori kerja jangka pendek dan memori jangka panjang terstruktur.
* [Modul 01: Memori Jangka Pendek & Context Window Management](./bab-04-sistem-memori-agentik/01-memori-jangka-pendek-context-management.md)
* [Modul 02: Memori Episodik & Semantik Berbasis Vektor](./bab-04-sistem-memori-agentik/02-memori-episodik-semantik-vektor.md)
* [Modul 03: GraphRAG & Entity Memory Networks](./bab-04-sistem-memori-agentik/03-graphrag-entity-memory-networks.md)

### [BAB 05: Arsitektur Multi-Agent & Sistem Orkestrasi Kolaboratif](./bab-05-arsitektur-multi-agent-orkestrasi/)
Desain sistem terdistribusi multi-entitas di mana spesialisasi dan pembagian tugas menghasilkan resolusi masalah kompleks.
* [Modul 01: Pola Topologi: Hierarkis, Supervisor, & Swarm (P2P)](./bab-05-arsitektur-multi-agent-orkestrasi/01-pola-topologi-hierarkis-supervisor-swarm.md)
* [Modul 02: Protokol Komunikasi Antar-Agent (A2A) & Negosiasi](./bab-05-arsitektur-multi-agent-orkestrasi/02-protokol-komunikasi-a2a-negosiasi.md)
* [Modul 03: Debat Multi-Agent, Konsensus, & Red Teaming](./bab-05-arsitektur-multi-agent-orkestrasi/03-debat-multi-agent-konsensus-red-teaming.md)

### [BAB 06: Deterministic Control Flow & State Graphs](./bab-06-deterministic-control-flow-state-graphs/)
Mengimplementasikan grafik komputasi siklis untuk mengeliminasi kelemahan rantai linier standar (Linear Chains).
* [Modul 01: Directed Acyclic Graph (DAG) vs Cyclical State Machines](./bab-06-deterministic-control-flow-state-graphs/01-dag-vs-cyclical-state-machines.md)
* [Modul 02: Human-in-the-Loop (HITL), Interupsi, & Persistensi State](./bab-06-deterministic-control-flow-state-graphs/02-human-in-the-loop-interupsi-persistensi.md)
* [Modul 03: Time-Travel Debugging & Checkpointing Architecture](./bab-06-deterministic-control-flow-state-graphs/03-time-travel-debugging-checkpointing.md)

### [BAB 07: Eksekusi Otonom: Code Interpreters & Web Browsing Agents](./bab-07-eksekusi-otonom-interpreters-browsers/)
Membangun kapabilitas aksi tingkat lanjut yang mampu bernavigasi di lingkungan web kompleks dan mengeksekusi kode secara dinamis.
* [Modul 01: Isolated Sandbox Runtime (gVisor/Wasm/Firecracker)](./bab-07-eksekusi-otonom-interpreters-browsers/01-isolated-sandbox-runtime-security.md)
* [Modul 02: Web Navigation via Chrome DevTools Protocol & Playwright](./bab-07-eksekusi-otonom-interpreters-browsers/02-web-navigation-cdp-playwright.md)
* [Modul 03: Grounding Multimodal: Visual Parsing & Action Grounding](./bab-07-eksekusi-otonom-interpreters-browsers/03-grounding-multimodal-visual-parsing.md)

### [BAB 08: Observabilitas, Evaluasi, & Tracing Sistem Agentik](./bab-08-observabilitas-evaluasi-tracing/)
Menerapkan metrik performa objektif untuk mengatasi ketidakpastian (*non-determinism*) pada sistem produksi.
* [Modul 01: Distributed Tracing & Instrumentation (OpenInference)](./bab-08-observabilitas-evaluasi-tracing/01-distributed-tracing-openinference.md)
* [Modul 02: Metrik Evaluasi: Trajectory, RAG Triad, & Tool-Use Accuracy](./bab-08-observabilitas-evaluasi-tracing/02-metrik-evaluasi-trajectory-rag-triad.md)
* [Modul 03: Evaluasi Otomatis Skala Besar Menggunakan LLM-as-a-Judge](./bab-08-observabilitas-evaluasi-tracing/03-evaluasi-otomatis-llm-as-a-judge.md)

### [BAB 09: Keamanan Agentik, Sandboxing, & Guardrails Pertahanan](./bab-09-keamanan-agentik-guardrails/)
Pertahanan proaktif dari vektor serangan adversarial seperti *indirect prompt injection*, manipulasi alat, dan kebocoran data.
* [Modul 01: Prompt Injection, Jailbreaking, & Tool Privilege Escalation](./bab-09-keamanan-agentik-guardrails/01-prompt-injection-privilege-escalation.md)
* [Modul 02: Input/Output Guardrails Dinamis (NeMo, Llama Guard)](./bab-09-keamanan-agentik-guardrails/02-input-output-guardrails-nemo-llamaguard.md)
* [Modul 03: Prinsip Zero-Trust, Least Privilege, & Policy Enforcement](./bab-09-keamanan-agentik-guardrails/03-zero-trust-least-privilege-policy.md)

### [BAB 10: Produksi Skala Besar, Serving, & Event-Driven Agentic System](./bab-10-produksi-skala-besar-event-driven/)
Arsitektur skalabilitas tinggi: melayani jutaan eksekusi langkah (*steps*) secara bersamaan dengan SLA ketat.
* [Modul 01: Asynchronous Agent Loops & Concurrency Engineering](./bab-10-produksi-skala-besar-event-driven/01-async-agent-loops-concurrency.md)
* [Modul 02: Arsitektur Event-Driven Menggunakan Kafka/Redis Streams](./bab-10-produksi-skala-besar-event-driven/02-event-driven-kafka-redis-streams.md)
* [Modul 03: Strategi Deployment, Rate-Limiting, Caching, & Fault Tolerance](./bab-10-produksi-skala-besar-event-driven/03-deployment-rate-limiting-caching-resilience.md)

---

## 4. Enterprise Capstone Project

### Judul: **AegisOps — Autonomous Incident Triaging & Self-Healing Platform**

#### Deskripsi Sistem
AegisOps adalah platform multi-agent otonom tingkat *enterprise* yang dirancang untuk memantau, mendiagnosis, mengisolasi, dan memulihkan insiden infrastruktur cloud secara *real-time*. Sistem ini mengintegrasikan pemantauan metrik Prometheus, log terdistribusi, eksekusi kode terisolasi via Docker/Firecracker, analisis GraphRAG untuk dependensi layanan, serta interupsi *Human-in-the-Loop* (HITL) untuk tindakan perbaikan berdampak tinggi (*destructive actions*).

```text
[Incoming Alert Webhook] (Datadog/PagerDuty)
          │
          ▼
   ┌──────────────┐
   │ Triage Agent │ ◄── [GraphRAG Service Map & Topology]
   └──────┬───────┘
          │ (Classification & Root Cause Hypothesis)
          ▼
   ┌──────────────┐
   │ Debug Agent  │ ◄── [Tool: Query Logs, Run Sandbox Shell, Fetch Metrics]
   └──────┬───────┘
          │ (Remediation Plan Construction)
          ▼
   ┌──────────────────────────────────────────────┐
   │ Guardrail & Human-in-the-Loop (HITL) Router  │
   └──────┬────────────────────────────────┬──────┘
          │ [Risk Level: HIGH]             │ [Risk Level: LOW]
          ▼                                ▼
   [Wait Admin Approval via Slack]   [Direct Auto-Execution]
          │ (Approved)                     │
          └─────────────────┬──────────────┘
                            ▼
                   ┌─────────────────┐
                   │ Execution Agent │ ◄── [Kubernetes API / Cloud Provider]
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Post-Mortem Scribe │ ◄── Generate Post-Mortem & Incident Summary
                   └─────────────────┘
```

#### Spesifikasi Arsitektur & Persyaratan Teknis
1. **State Machine Core**:
   * Dibangun menggunakan pola *Cyclic Graph State Machine* (misal: LangGraph / Native Custom Graph Engine).
   * Persistensi state menggunakan PostgreSQL / Redis Checkpointer untuk mendukung proses *resumption* pasca-kegagalan dan interupsi manual HITL.
2. **Multi-Agent Specialization**:
   * **Triage Agent**: Menguraikan payload insiden, memprioritaskan tingkat keparahan (SEV 1 - SEV 4), dan menavigasi topologi arsitektur via GraphRAG.
   * **Diagnostic/Debug Agent**: Mengumpulkan metrik, membaca *stack traces*, dan mengeksekusi perintah CLI *read-only* dalam lingkungan kontainer terisolasi (*sandbox*).
   * **Remediation Agent**: Merumuskan dan mengeksekusi skrip mitigasi (contoh: *pod restart*, konfigurasi ulang HPA, *rollback deployment*).
   * **Auditor/Scribe Agent**: Menyusun laporan *post-mortem* deterministik dengan skema JSON/Markdown yang divalidasi Pydantic.
3. **Tool Execution & Protokol Standar**:
   * Integrasi fungsional menggunakan **Model Context Protocol (MCP)**.
   * Seluruh eksekusi shell/Python diisolasi di dalam *Docker/gVisor MicroVM Sandbox* dengan pembatasan jaringan ketat (*Zero-Trust egress*).
4. **Safety & Guardrails**:
   * Implementasi NeMo / Llama Guard untuk mencegah manipulasi instruksi (*Prompt Injection*) yang masuk melalui log infrastruktur eksternal.
   * RBAC ketat pada level fungsi: operasi destruktif (misal: penulisan/penghapusan) wajib dialihkan ke mekanisme *state interrupt* untuk persetujuan manual administrator via interaksi terotentikasi (Slack Block Kit / Web Dashboard).
5. **Observabilitas & Tracing**:
   * Penerapan *full distributed tracing* menggunakan standar OpenInference / OpenTelemetry yang terhubung ke platform observabilitas (seperti Langfuse / Phoenix).
   * Evaluasi metrik akurasi lintasan keputusan (*trajectory evaluation*) dan konsumsi token secara granular.
6. **Delivery & Deployment**:
   * Arsitektur backend berbasis *asynchronous event-driven* memanfaatkan FastAPI, Celery/Redis Streams, dan WebSocket untuk komunikasi streaming *thought process* ke antarmuka pengguna.
   * Kontainerisasi penuh menggunakan Docker Compose & Helm Charts untuk deployment Kubernetes yang dapat diuji ulang secara deterministik.