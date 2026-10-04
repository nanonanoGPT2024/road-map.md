# Kurikulum Enterprise: Vibe Coding (AI-Assisted Software Engineering)

Selamat datang di silabus kurikulum komprehensif **Vibe Coding**. Kurikulum ini dirancang berdasarkan standar roadmap rekayasa perangkat lunak modern untuk mentransformasikan insinyur perangkat lunak konvensional menjadi **AI-Augmented Systems Architect**.

---

## 1. Course Overview & Mindset

### Pergeseran Paradigma: Dari Sintaks ke Orkestrasi Intent
**Vibe Coding** bukan sekadar "mengetik kode dengan bantuan autocompletion", melainkan perubahan fundamental dalam cara perangkat lunak dikonseptualisasikan, diarsitekturi, dan dieksekusi:

1. **Mindset Shift: Architect over Typist**
   * *Legacy Mindset*: Menghafal API signature, mengetik boilerplate sintaks manual, dan menghabiskan 80% waktu pada implementasi mekanis.
   * *Vibe Coding Mindset*: Bertindak sebagai orchestrator tingkat tinggi (*intent architect*). Fokus dialihkan ke *domain modeling*, *invariants validation*, *system boundaries*, dan *context curation*.
2. **Context Engineering as a First-Class Citizen**
   * Keberhasilan generasi kode oleh Model Bahasa Besar (LLM) bergantung pada presisi konteks runtime, batasan arsitektural (*guardrails*), dan representasi pohon repositori (*repository topology*).
3. **Deterministic Verification over Blind Trust**
   * Menyeimbangkan kecepatan probabilistik model AI dengan loop validasi deterministik: *Automated Testing*, *Type Safety*, *Static Analysis (AST)*, dan *Runtime Observability*.
4. **Iterative Refinement Loops**
   * Pendekatan berbasis umpan balik berkelanjutan (*feedback-driven scaffolding*): Generate $\to$ Compile $\to$ Lint $\to$ Test $\to$ Heal $\to$ Commit.

---

## 2. Learning Roadmap

Diagram pohon ASCII berikut memetakan perjalanan instruksional dari level fundamental hingga orkestrasi otonom skala enterprise:

```text
VIBE CODING: ZERO TO PRODUCTION ARCHITECT
│
├── BAB 01: Paradigma Vibe Coding & Arsitektur AI-Assisted Development
│   ├── Modul 01: Mental Model Shift: Dari Coder ke Orchestrator
│   ├── Modul 02: Taksonomi Model AI (LLM, SLM, Diffusion, Reasoning Models)
│   └── Modul 03: Siklus Hidup Software Engineering Berbasis Intent
│
├── BAB 02: Tooling Landscape & Agentic Workspaces
│   ├── Modul 01: Deep-Dive Workspace: Cursor, Windsurf, & Claude Dev
│   ├── Modul 02: Headless & Terminal-First Agents (Aider, Mentat, Ollama)
│   └── Modul 03: Konfigurasi Lingkungan Runtime Terisolasi & Sandboxing
│
├── BAB 03: Context Engineering & Repository Knowledge Injection
│   ├── Modul 01: Arsitektur .cursorrules, System Prompts, & Memory Files
│   ├── Modul 02: AST Parsing, Repo Maps, & Multi-File Dependency Injection
│   └── Modul 03: Retrieval-Augmented Generation (RAG) untuk Dokumentasi Privat
│
├── BAB 04: Specification-Driven Development (SDD) & Prompt Architecture
│   ├── Modul 01: Transformasi PRD Menjadi Executable Technical Spec
│   ├── Modul 02: Structural Prompting: Few-Shot, Chain-of-Thought, & Invariants
│   └── Modul 03: Dynamic Task Decomposition & Milestones Breakdown
│
├── BAB 05: Multimodal Prototyping & Visual-to-Code Workflows
│   ├── Modul 01: Screenshot-to-Code & Design System Alignment (Figma to Code)
│   ├── Modul 02: Reverse Engineering Legacy UI ke Modern Stack
│   └── Modul 03: Iterasi Komponen UI Berbasis Accessibility & Performance
│
├── BAB 06: Test-Driven Vibe Coding & Automated Verification Loops
│   ├── Modul 01: AI-Generated Test Suites (Unit, Integration, & Contract Tests)
│   ├── Modul 02: Self-Healing Code Loops via Compiler & Test Failures
│   └── Modul 03: Property-Based & Mutation Testing Dipandu AI
│
├── BAB 07: Debugging, Hallucination Mitigation, & Telemetry
│   ├── Modul 01: Analisis Root-Cause Terbimbing Agen & Runtime Tracing
│   ├── Modul 02: Mitigasi Halusinasi API & Silent Degradation
│   └── Modul 03: Post-Mortem Logging & Session Memory Rollback
│
├── BAB 08: Refactoring, Tech Debt, & Architectural Guardrails
│   ├── Modul 01: Legacy Modernization & Migrasi Bahasa Skala Besar
│   ├── Modul 02: Enforcing Clean Architecture, SOLID, & Domain Boundaries
│   └── Modul 03: Continuous Static Analysis & Custom Linter Rules for AI
│
├── BAB 09: Enterprise Security, Secrets Management, & Compliance
│   ├── Modul 01: Zero-Trust Prompting: Pencegahan Leaks Kredensial & PII
│   ├── Modul 02: Automated SAST/DAST Triage & Dependency Poisoning Checks
│   └── Modul 03: Intellectual Property, Licensing, & Audit Trails
│
└── BAB 10: Autonomous Multi-Agent Swarms & Continuous Delivery
    ├── Modul 01: Desain SWE-Agent: Autonomous Issue-to-PR Pipelines
    ├── Modul 02: Orchestrating Agent Swarms (Planner, Coder, Reviewer, QA)
    └── Modul 03: Masa Depan SDLC: Fully Autonomous Engineering Loops
```

---

## 3. Navigasi Detail Modul (Bab 01 s/d Bab 10)

### [BAB 01: Paradigma Vibe Coding & Arsitektur AI-Assisted Development](./bab-01-paradigma-vibe-coding/README.md)
*Fokus: Mengubah kerangka berpikir rekayasa sistem menuju arsitektur intent dan probabilistic execution.*
* [Modul 01: Mental Model Shift: Dari Coder ke Orchestrator](./bab-01-paradigma-vibe-coding/01-mental-model-shift.md)
  * Menyelami dekonstruksi beban kerja developer: dari sintaksis mekanis ke orkestrator sistemik.
* [Modul 02: Taksonomi Model AI (LLM, SLM, Reasoning Models)](./bab-01-paradigma-vibe-coding/02-taksonomi-model-ai.md)
  * Analisis karakteristik model (Claude 3.5 Sonnet, GPT-4o, DeepSeek-Coder, o1/o3-series) dan trade-off latensi vs kedalaman penalaran (*reasoning*).
* [Modul 03: Siklus Hidup Software Engineering Berbasis Intent](./bab-01-paradigma-vibe-coding/03-lifecycle-intent-engineering.md)
  * Blueprint pipeline SDLC baru: Intent Framing $\to$ Spec Generation $\to$ Synthesis $\to$ Verification $\to$ Deployment.

### [BAB 02: Tooling Landscape & Agentic Workspaces](./bab-02-tooling-landscape/README.md)
*Fokus: Menguasai platform, editor AI-native, headless agent, dan runtime sandbox.*
* [Modul 01: Deep-Dive Workspace: Cursor, Windsurf, & Claude Dev](./bab-02-tooling-landscape/01-cursor-windsurf-claude-dev.md)
  * Fitur unggulan editor AI-native: Composer, multi-file agentic editing, cascade context, dan tab-completion engine.
* [Modul 02: Headless & Terminal-First Agents (Aider, Mentat, Local SLM)](./bab-02-tooling-landscape/02-headless-terminal-agents.md)
  * Otomasi CLI berbasis git, integrasi Aider dalam terminal, dan orkestrasi model lokal via Ollama/vLLM.
* [Modul 03: Konfigurasi Lingkungan Runtime Terisolasi & Sandboxing](./bab-02-tooling-landscape/03-runtime-isolation-sandboxing.md)
  * Eksekusi aman kode berbasis AI menggunakan Docker sandboxes, DevContainers, dan e2b runtime virtualization.

### [BAB 03: Context Engineering & Repository Knowledge Injection](./bab-03-context-engineering/README.md)
*Fokus: Mengoptimalkan context window melalui repositori modeling, semantic routing, dan RAG.*
* [Modul 01: Arsitektur .cursorrules, System Prompts, & Memory Files](./bab-03-context-engineering/01-cursorrules-system-prompts.md)
  * Standardisasi aturan repositori, batasan gaya kode deklaratif, dan persistensi memori konteks proyek.
* [Modul 02: AST Parsing, Repo Maps, & Multi-File Dependency Injection](./bab-03-context-engineering/02-ast-repo-maps-dependency-injection.md)
  * Bagaimana agen memetakan hierarki dependensi menggunakan Abstract Syntax Trees (Tree-sitter) dan ctags.
* [Modul 03: Retrieval-Augmented Generation (RAG) untuk Dokumentasi Privat](./bab-03-context-engineering/03-rag-internal-docs.md)
  * Menghubungkan dokumentasi internal, API endpoints OpenAPI, dan SDK enterprise ke dalam knowledge agent.

### [BAB 04: Specification-Driven Development (SDD) & Prompt Architecture](./bab-04-specification-driven-development/README.md)
*Fokus: Menyusun spesifikasi deterministik dan prompt terstruktur untuk meminimalisir deviasi generasi kode.*
* [Modul 01: Transformasi PRD Menjadi Executable Technical Spec](./bab-04-specification-driven-development/01-prd-to-technical-spec.md)
  * Mengonversi User Story dan dokumen produk menjadi skema data tipe ketat, kontrak API, dan dependensi modular.
* [Modul 02: Structural Prompting: Few-Shot, Chain-of-Thought, & Invariants](./bab-04-specification-driven-development/02-structural-prompting.md)
  * Teknik rekayasa prompt tingkat lanjut untuk memaksakan invariansi logika bisnis dan format respon.
* [Modul 03: Dynamic Task Decomposition & Milestones Breakdown](./bab-04-specification-driven-development/03-task-decomposition.md)
  * Memecah fitur enterprise menjadi atom-atom subtugas independen yang dapat diselesaikan AI tanpa kehilangan konteks global.

### [BAB 05: Multimodal Prototyping & Visual-to-Code Workflows](./bab-05-multimodal-prototyping/README.md)
*Fokus: Akselerasi antarmuka pengguna dari wireframe, Figma token, dan visual artifacts menjadi kode fungsional.*
* [Modul 01: Screenshot-to-Code & Design System Alignment](./bab-05-multimodal-prototyping/01-screenshot-to-code-design-tokens.md)
  * Menerjemahkan visual mockups langsung ke Tailwind/CSS Modules dengan pemetaan design system token enterprise.
* [Modul 02: Reverse Engineering Legacy UI ke Modern Stack](./bab-05-multimodal-prototyping/02-reverse-engineering-legacy-ui.md)
  * Mengurai legacy dashboard (misal: JSP/PHP monolitik) menjadi arsitektur micro-frontend berbasis React/Next.js.
* [Modul 03: Iterasi Komponen UI Berbasis Accessibility & Performance](./bab-05-multimodal-prototyping/03-a11y-performance-optimization.md)
  * Prompting untuk standardisasi WCAG 2.1 AA, reduksi Cumulative Layout Shift (CLS), dan audit Core Web Vitals otomatis.

### [BAB 06: Test-Driven Vibe Coding & Automated Verification Loops](./bab-06-test-driven-vibe-coding/README.md)
*Fokus: Mengunci integritas kode melalui pipeline pengujian otomatis dan perbaikan swakelola (self-healing).*
* [Modul 01: AI-Generated Test Suites (Unit, Integration, Contract Tests)](./bab-06-test-driven-vibe-coding/01-ai-generated-test-suites.md)
  * Sintesis pengujian otomatis menggunakan Vitest/Jest, Playwright, dan Pact framework sebelum implementasi fungsi.
* [Modul 02: Self-Healing Code Loops via Compiler & Test Failures](./bab-06-test-driven-vibe-coding/02-self-healing-feedback-loops.md)
  * Membangun loop otonom: `Test Runner Failure Output` $\to$ `Agent Parsing` $\to$ `Patching` $\to$ `Green Status`.
* [Modul 03: Property-Based & Mutation Testing Dipandu AI](./bab-06-test-driven-vibe-coding/03-property-mutation-testing.md)
  * Menemukan edge-cases tersembunyi dengan mengombinasikan fast-check/hypothesis dan audit mutasi kode otomatis.

### [BAB 07: Debugging, Hallucination Mitigation, & Telemetry](./bab-07-debugging-and-hallucinations/README.md)
*Fokus: Mengidentifikasi bug tersembunyi, halusinasi logika, dan degradasi performa dari kode sintesis AI.*
* [Modul 01: Analisis Root-Cause Terbimbing Agen & Runtime Tracing](./bab-07-debugging-and-hallucinations/01-root-cause-analysis-tracing.md)
  * Memanfaatkan OpenTelemetry traces dan stack traces kompleks untuk mengarahkan context debugging agen.
* [Modul 02: Mitigasi Halusinasi API & Silent Degradation](./bab-07-debugging-and-hallucinations/02-mitigasi-halusinasi-api.md)
  * Mekanisme validasi skema runtime (Zod/TypeBox) dan pembatas dependensi eksternal terhadap library non-eksisten.
* [Modul 03: Post-Mortem Logging & Session Memory Rollback](./bab-07-debugging-and-hallucinations/03-post-mortem-session-rollback.md)
  * Strategi branch rollback git otomatis dan analisis kegagalan agen untuk penyempurnaan instruksi repositori.

### [BAB 08: Refactoring, Tech Debt, & Architectural Guardrails](./bab-08-refactoring-and-guardrails/README.md)
*Fokus: Menghindari akumulasi "AI-generated technical debt" dengan menegakkan arsitektur bersih secara otomatis.*
* [Modul 01: Legacy Modernization & Migrasi Bahasa Skala Besar](./bab-08-refactoring-and-guardrails/01-legacy-modernization-migration.md)
  * Pola migrasi bertahap (Strangler Fig Pattern) berbantuan AI dari JavaScript ke TypeScript atau Python ke Rust/Go.
* [Modul 02: Enforcing Clean Architecture, SOLID, & Domain Boundaries](./bab-08-refactoring-and-guardrails/02-clean-architecture-enforcement.md)
  * Memprogram guardrails arsitektur berbasis rulebook kaku agar AI tidak merusak pemisahan lapisan (separation of concerns).
* [Modul 03: Continuous Static Analysis & Custom Linter Rules for AI](./bab-08-refactoring-and-guardrails/03-static-analysis-ai-linters.md)
  * Mengintegrasikan SonarQube, Biome, dan ESLint custom AST rules khusus mengevaluasi kode yang dihasilkan LLM.

### [BAB 09: Enterprise Security, Secrets Management, & Compliance](./bab-09-security-and-compliance/README.md)
*Fokus: Proteksi data enterprise, pencegahan injeksi prompt, dan pematuhan lisensi perangkat lunak.*
* [Modul 01: Zero-Trust Prompting: Pencegahan Leaks Kredensial & PII](./bab-09-security-and-compliance/01-zero-trust-prompting-pii-leaks.md)
  * Penerapan pre-commit scanner (TruffleHog, Gitleaks) dan sanitasi prompt otomatis terhadap data kredensial/PII.
* [Modul 02: Automated SAST/DAST Triage & Dependency Poisoning Checks](./bab-09-security-and-compliance/02-sast-dast-triage.md)
  * Triaging otomatis temuan kerentanan (Snyk, Semgrep) dan proteksi terhadap serangan *hallucinated package injection*.
* [Modul 03: Intellectual Property, Licensing, & Audit Trails](./bab-09-security-and-compliance/03-ip-licensing-audit-trails.md)
  * Kepatuhan hukum lisensi open-source (GPL vs Apache vs MIT) dan jejak audit asal kode buatan AI dalam enterprise.

### [BAB 10: Autonomous Multi-Agent Swarms & Continuous Delivery](./bab-10-autonomous-agent-swarms/README.md)
*Fokus: Mengonfigurasi agen otonom end-to-end dari GitHub Issues hingga produksi tanpa supervisi mikro.*
* [Modul 01: Desain SWE-Agent: Autonomous Issue-to-PR Pipelines](./bab-10-autonomous-agent-swarms/01-swe-agent-issue-to-pr.md)
  * Arsitektur agen yang membaca issue, mereproduksi bug via test, menulis patch, dan membuka Pull Request secara mandiri.
* [Modul 02: Orchestrating Agent Swarms (Planner, Coder, Reviewer, QA)](./bab-10-autonomous-agent-swarms/02-agent-swarms-orchestration.md)
  * Topologi multi-agen kolaboratif dengan peran terisolasi dan protokol konsensus untuk validasi silang kode.
* [Modul 03: Masa Depan SDLC: Fully Autonomous Engineering Loops](./bab-10-autonomous-agent-swarms/03-autonomous-engineering-future.md)
  * Evaluasi metrik SWE-bench, continuous deployment tanpa intervensi manual, dan model tata kelola tim engineering masa depan.

---

## 4. Enterprise Capstone Project Specification

### Judul Proyek
**Autonomous Omnichannel Financial Reconciliation Engine with Self-Healing Multi-Agent Pipelines**

### Deskripsi Proyek
Membangun platform rekonsiliasi transaksi keuangan terdistribusi berlatensi rendah yang memproses jutaan transaksi multi-vendor (Stripe, Xendit, Midtrans, Core Banking ISO 8583). Seluruh platform dirancang, diimplementasikan, diuji, dan di-deploy menggunakan metodologi **Vibe Coding end-to-end** dengan pengawasan arsitektur tingkat tinggi.

### Arsitektur & Tech Stack
```text
[Incoming Heterogeneous Ledgers] 
               │
               ▼
   [Ingestion Service (Go)] 
               │
         (Kafka Queue)
               │
               ▼
[Reconciliation Core Service (Rust / TypeScript)] 
   ├── Schema Extraction (Dynamic Struct Validator)
   ├── Discrepancy Detector (AI Self-Correcting Engine)
   └── Ledger Imbalance Resolver
               │
   ┌───────────┴───────────┐
   ▼                       ▼
[Postgres (TimescaleDB)] [Audit S3 Vault]
   │
   ▼
[Operational Agent Backoffice (Next.js 15 App Router)]
   └── Autonomous Multi-Agent Incident Commander (LangGraph / SWE-Agent Loop)
```

1. **Ingestion & Processing Core**:
   * *High-Throughput Gateway*: Go/Rust untuk intake webhook finansial dengan throughput $\ge 5,000\text{ RPS}$.
   * *Stream Processing*: Apache Kafka / Redpanda untuk pipeline pengantrean transaksi asinkron.
2. **Deterministic & Agentic Healing Engine**:
   * *Engine Type-Safety*: Rust core engine dengan jaminan `zero-cost abstractions` dan pemodelan status transaksi invarian.
   * *AI Discrepancy Triaging Agent*: Worker headless berbasis Python/TypeScript yang menganalisis ketidakcocokan data transaksi (*discrepancies*), memprediksi mapping yang hilang, dan mengajukan PR perbaikan mapping secara otonom ke repositori.
3. **Observability & Guardrails**:
   * *OpenTelemetry + Prometheus + Grafana* untuk tracing deterministik.
   * *Static Analysis Gate*: SonarQube + Semgrep policy ketat (Coverage $\ge 90\%$, Zero High/Critical CVEs).

### Metrik Keberhasilan & Verifikasi
Proyek dinyatakan memenuhi standar enterprise jika memenuhi indikator kinerja berikut:
* **Generative Efficiency Ratio**: $\ge 80\%$ kode dasar dan pengujian disintesis via prompt terstruktur dan diverifikasi oleh human architect.
* **Deterministic Test Coverage**: Pengujian unit, integrasi, dan e2e mencapai cakupan minimal $90\%$ dengan property-based edge checking.
* **Autonomous Healing Rate**: Agen mampu menyelesaikan minimal 3 skenario *breaking schema mismatch* secara mandiri via PR otomatis yang lulus CI/CD.
* **Zero Secret Leakage & License Compliance**: Lulus audit TruffleHog dan FOSSA tanpa pelanggaran lisensi copyleft pada third-party dependencies.

---
*Silabus ini disusun untuk pembelajaran tingkat lanjut. Mulai pembelajaran dari [BAB 01: Paradigma Vibe Coding & Arsitektur AI-Assisted Development](./bab-01-paradigma-vibe-coding/README.md).*