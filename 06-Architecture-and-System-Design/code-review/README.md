Berikut adalah silabus lengkap dan kurikulum kurasi enterprise untuk repositori **Code Review** (`code-review`) yang disusun sesuai standar `GEMINI.md`.

---

# README.md

```markdown
# 🏛️ Enterprise Engineering Curriculum: Modern Code Review & Engineering Governance

Selamat datang di kurikulum teknis mendalam **Code Review Enterprise-Grade**. Kurikulum ini dirancang khusus bagi Software Engineer, Tech Lead, dan Engineering Manager untuk mentransformasikan proses peninjauan kode dari sekadar formalitas sintaksis atau "nitpicking" menjadi instrumen strategis rekayasa perangkat lunak: menjaga integritas arsitektur, mempercepat *delivery cycle*, meminimalisasi risiko keamanan/regresi, serta membangun budaya *psychological safety* yang memfasilitasi transfer pengetahuan tingkat tinggi.

---

## 🧭 Course Overview & Mindset

Code Review di tingkat enterprise bukan sekadar mencari kesalahan titik-koma (*typo hunting*) atau memaksakan preferensi gaya personal (*style wars*). Segala hal yang deterministik dan dapat diotomasi **wajib** diserahkan ke mesin (linter, formatter, type-checker, SAST/DAST pipeline). 

Tanggung jawab kognitif *human reviewer* difokuskan pada:
1. **System & Architectural Integrity:** Apakah perubahan ini melanggar batasan bounded context, menciptakan siklus dependensi tersembunyi, atau merusak kontrak API publik?
2. **Correctness, Invariants, & Concurrency:** Apakah ada *race conditions*, *deadlocks*, kebocoran memori, atau skenario *edge case* pada sistem terdistribusi yang tidak terabstraksi dalam unit test?
3. **Security by Design:** Bagaimana *trust boundary* diperlakukan? Apakah ada potensi eksploitasi otorisasi (BOLA/IDOR), injeksi, atau *sensitive data exposure*?
4. **Maintainability & Cognitive Load:** Apakah kode ini mudah di-debug pada jam 3 pagi saat insiden P0 terjadi tanpa dokumentasi eksternal?
5. **Human Dynamics & Socio-Technical Safety:** Bagaimana memberikan kritik objektif tanpa menyerang identitas individu, menjaga momentum *pull request* tetap bergerak cepat, dan mendistribusikan konteks domain secara inklusif.

```
       [Developer Push]
              │
              ▼
   ┌──────────────────────┐
   │ Automated CI Gates   │ ──(Fails)──> [Auto-Reject & Instant Feedback]
   │ (SAST, Tests, Lint)  │
   └──────────────────────┘
              │ (Passes)
              ▼
   ┌──────────────────────┐
   │ Human Code Review    │
   │ - Architectural Fit  │
   │ - Concurrency/Race   │ ──(Changes Requested)──> [Async Collaboration & RFC]
   │ - Business Invariants│
   │ - Empathy & Clarity  │
   └──────────────────────┘
              │ (Approved)
              ▼
   ┌──────────────────────┐
   │ Continuous Merge &   │
   │ Production Telemetry │
   └──────────────────────┘
```

---

## 🗺️ Learning Roadmap

```text
Code Review Mastery (Enterprise Track)
├── 01. Fondasi & Psikologi Code Review
│   ├── Mindset & Psychological Safety
│   └── Etiket Reviewer vs Author
├── 02. Taksonomi & Checklist Review Standar Industri
│   ├── Hierarchy of Review Concerns
│   └── Verification Checklist & Critical Paths
├── 03. Arsitektur Pull Request & Git Workflows
│   ├── Trunk-Based Development & Stacked PRs
│   └── Pull Request Anatomy & Atomic Commits
├── 04. Otomasi: Linting, SAST, & Pre-Review Pipelines
│   ├── Static Analysis & Zero-Nit Automation
│   └── DangerJS, Bot Guardrails, & CI Gates
├── 05. Review Khusus: Keamanan & Sanitasi Data
│   ├── OWASP Top 10 & Business Logic Exploits
│   └── Authn/Authz, Data Leaks, & Cryptography
├── 06. Review Khusus: Performa, Konkurensi, & Skalabilitas
│   ├── Database Queries, N+1, & Lockings
│   └── Thread Safety, Race Conditions, & Memory Leaks
├── 07. Review Khusus: Maintainability, Clean Architecture, & Testing
│   ├── Clean Architecture & Domain Boundaries
│   └── Test Coverage Efficacy vs Code Tautology
├── 08. Metrik, SLA, & Mengelola Review Fatigue
│   ├── PR Velocity, Turnaround Time, & WIP Limits
│   └── Mitigasi Burnout & Cognitive Overload
├── 09. Komunikasi Asinkron, Resolusi Konflik, & Mentoring
│   ├── Conventional Comments & Explicit Intent
│   └── Handling Deadlocks & De-escalation
└── 10. Enterprise Governance, Compliance, & AI-Assisted Reviews
    ├── Regulatory Compliance (SOC2, PCI-DSS, HIPAA)
    └── LLM-Assisted Reviews: Limits & Guardrails
```

---

## 📚 Navigasi Silabus Detail

### [Bab 01: Fondasi & Psikologi Code Review](./01-fondasi-dan-psikologi/)
Membedah dinamika sosio-teknikal, bias kognitif, dan fondasi psikologis yang menentukan keberhasilan atau kegagalan *engineering culture* dalam proses review.
* [Modul 01: Cultural Pillars & Psychological Safety](./01-fondasi-dan-psikologi/01-cultural-pillars-and-psychological-safety.md) - Membangun kultur *blameless feedback*, memisahkan ego dari kode, dan membangun rasa kepemilikan kolektif (*collective code ownership*).
* [Modul 02: Reviewer vs Author Dynamic & Cognitive Empathy](./01-fondasi-dan-psikologi/02-reviewer-author-dynamic.md) - Kewajiban author dalam menyediakan konteks, ekspektasi reviewer, dan bagaimana empati kognitif mempercepat *consensus building*.

### [Bab 02: Taksonomi & Checklist Review Standar Industri](./02-taksonomi-dan-checklist/)
Membangun hierarki inspeksi untuk membedakan antara *architectural defects*, *correctness bugs*, dan *superficial styling*.
* [Modul 01: Hierarchy of Review Concerns](./02-taksonomi-dan-checklist/01-hierarchy-of-concerns.md) - Model piramida tinjauan: Arsitektur > Ketepatan Fungsional > Keamanan > Performa > Konvensi.
* [Modul 02: Pragmatic Review Checklists & Anti-Patterns](./02-taksonomi-dan-checklist/02-pragmatic-checklists.md) - Menyusun *mental checklist* terstandarisasi untuk production code path tanpa memperlambat *throughput*.

### [Bab 03: Arsitektur Pull Request & Git Workflows](./03-arsitektur-pr-dan-git/)
Strategi pemotongan kode (*slicing*) dan pengelolaan *branching* modern yang meminimalisir ukuran PR dan mencegah *merge queue blockage*.
* [Modul 01: Trunk-Based Development & Stacked PRs](./03-arsitektur-pr-dan-git/01-trunk-based-and-stacked-prs.md) - Penerapan Stacked Diffs/PRs (menggunakan tools seperti Graphite/Sprig), *feature flag driven development*, dan eliminasi PR raksasa (*mega-PRs*).
* [Modul 02: Anatomy of an Exemplary Pull Request](./03-arsitektur-pr-dan-git/02-anatomy-of-exemplary-pr.md) - Standarisasi deskripsi PR, artefak pembuktian (benchmarks, logs, UI recordings), *atomic commits*, dan *traceability* tiket.

### [Bab 04: Otomasi: Linting, SAST, & Pre-Review Pipelines](./04-otomasi-pre-review/)
Mendelegasikan inspeksi mekanis ke mesin secara mutlak sebelum mata manusia melihat baris kode.
* [Modul 01: Eliminating Nitpicks with Linters & Formatters](./04-otomasi-pre-review/01-linters-formatters-git-hooks.md) - Pre-commit hooks, zero-tolerance compiler warnings, linters kustom, dan deterministik auto-formatting.
* [Modul 02: DangerJS, Static Analysis (SAST), & Automated Guardrails](./04-otomasi-pre-review/02-dangerjs-and-sast-gates.md) - Otomasi validasi ukuran PR, verifikasi label, *contract drift detection*, dan eksekusi SonarQube/Semgrep pada pipeline CI.

### [Bab 05: Review Khusus: Keamanan & Sanitasi Data](./05-review-keamanan-data/)
Metodologi inspeksi terarah untuk mencegah vulnerabilitas sistem, kebocoran data, dan manipulasi otorisasi.
* [Modul 01: Application Security & OWASP Top 10 Review](./05-review-keamanan-data/01-appsec-owasp-inspection.md) - Mendeteksi BOLA/BFLA, SQL/Command Injection tersembunyi, SSRF, dan sanitasi input/output.
* [Modul 02: Sensitive Data Exposure & Cryptographic Hygeine](./05-review-keamanan-data/02-sensitive-data-crypto-review.md) - Meninjau implementasi enkripsi, pengelolaan *secrets*, token masking pada logs, dan validasi izin akses tenant (multi-tenancy isolation).

### [Bab 06: Review Khusus: Performa, Konkurensi, & Skalabilitas](./06-review-performa-konkurensi/)
Mengidentifikasi *bottlenecks*, masalah algoritma, kebocoran sumber daya, dan cacat konkurensi sebelum mencapai skala produksi.
* [Modul 01: Database Interactions, Locking, & N+1 Queries](./06-review-performa-konkurensi/01-database-queries-locking.md) - Menganalisis *execution plans*, pemodelan indeks, transaksi panjang, bahaya N+1 ORM, dan *isolation level anomalies*.
* [Modul 02: Concurrency, Thread Safety, & Resource Leaks](./06-review-performa-konkurensi/02-concurrency-memory-leaks.md) - Mendeteksi *deadlocks*, *race conditions*, *unbounded queues*, kebocoran koneksi, goroutine/thread leakage, dan starvation.

### [Bab 07: Review Khusus: Maintainability, Clean Architecture, & Testing](./07-review-arsitektur-testing/)
Menjaga batas modul, memvalidasi dependensi struktural, dan memastikan strategi testing yang bermakna.
* [Modul 01: Clean Architecture & Domain Boundaries Verification](./07-review-arsitektur-testing/01-architecture-boundaries.md) - Mencegah *leaky abstractions*, percampuran kode infrastruktur di domain core, dan evaluasi *coupling/cohesion*.
* [Modul 02: Evaluating Test Efficacy vs Tautological Tests](./07-review-arsitektur-testing/02-evaluating-test-efficacy.md) - Memeriksa mutu unit/integration tests: mengidentifikasi *tautological tests* (hanya mengetes mock), *flaky tests*, dan verifikasi *failure modes*.

### [Bab 08: Metrik, SLA, & Mengelola Review Fatigue](./08-metrik-dan-review-fatigue/)
Pendekatan kuantitatif untuk memantau efisiensi tinjauan tim tanpa merusak kualitas kognitif reviewer.
* [Modul 01: Engineering Metrics: Review Velocity & Queue Health](./08-metrik-dan-review-fatigue/01-engineering-review-metrics.md) - Melacak *Time to First Review*, *PR Cycle Time*, *Review Queue Length*, dan penerapan SLA internal.
* [Modul 02: Mitigating Review Fatigue & Cognitive Burnout](./08-metrik-dan-review-fatigue/02-mitigating-review-fatigue.md) - Mengontrol batasan *Work In Progress* (WIP), alokasi fokus waktu review, dan mitigasi sindrom "LGTM" pada PR berukuran besar.

### [Bab 09: Komunikasi Asinkron, Resolusi Konflik, & Mentoring](./09-komunikasi-resolusi-konflik/)
Seni menyampaikan feedback teknis secara presisi, mengelola perdebatan teknis, dan memanfaatkan PR untuk pembinaan teknis.
* [Modul 01: Conventional Comments & Explicit Intent](./09-komunikasi-resolusi-konflik/01-conventional-comments.md) - Penerapan label komentar terstandarisasi (`suggestion`, `issue`, `question`, `thought`, `nitpick`) untuk menghilangkan ambiguitas urgensi.
* [Modul 02: Constructive Conflict Resolution & Technical Mentorship](./09-komunikasi-resolusi-konflik/02-conflict-resolution-mentoring.md) - Mengatasi *stalemates* arsitektur (prinsip disagree-and-commit vs escalation ke RFC), serta teknik mentoring insinyur junior melalui PR.

### [Bab 10: Enterprise Governance, Compliance, & AI-Assisted Reviews](./10-governance-compliance-ai/)
Implementasi kepatuhan audit regulasi dan akselerasi modern menggunakan Large Language Models (LLM) dengan pembatasan yang aman.
* [Modul 01: Regulatory Compliance & Four-Eyes Principle](./10-governance-compliance-ai/01-compliance-four-eyes-principle.md) - Otomasi kepatuhan audit SOC2, ISO 27001, PCI-DSS, segregasi tugas (SoD), dan audit trail immutability.
* [Modul 02: AI-Assisted Reviews: Tooling, Limits, & Guardrails](./10-governance-compliance-ai/02-ai-assisted-code-reviews.md) - Mengintegrasikan GitHub Copilot/LLM bot untuk ringkasan dan initial check, bahaya halusinasi logika, serta etika dan kerahasiaan kode (*data privacy*).

---

## 🎯 Capstone Project Enterprise

### Skenario Proyek: Multi-Service Financial Ledger & High-Throughput Checkout

Capstone Project ini adalah simulasi dunia nyata berisiko tinggi. Anda akan berperan sebagai **Staff/Lead Software Engineer** di sebuah platform *fintech-as-a-service*. Anda akan diberikan sebuah repositori tiruan (*mock enterprise monorepo*) yang berisi serangkaian PR bermasalah yang diajukan oleh tim engineering fiktif.

### Spesifikasi Penugasan:

1. **Audit & Review 3 Pull Request Kritis:**
   * **PR #101 (The Architectural Drift):** Migrasi endpoint checkout monolitik ke microservice baru. Mengandung *leaky domain*, sirkular dependensi gRPC tersembunyi, dan pemecahan bounded context yang salah.
   * **PR #102 (The Silent Security Disaster):** Implementasi endpoint multi-tenancy custom ledger report. Mengandung kerentanan BOLA/IDOR level tinggi, *unvalidated redirect*, dan kebocoran token PII ke dalam payload log terpusat.
   * **PR #103 (The Scalability & Concurrency Bomb):** Optimasi batch processing transaksi finansial. Mengandung *distributed race condition*, mutasi memory state tak aman (*data race*), dan potensi *database deadlock* akibat query locking yang inkonsisten (`SELECT ... FOR UPDATE` tanpa pengurutan deterministik).

2. **Artifact Delivery Requirements:**
   * **In-Line Review Interventions:** Terapkan standar *Conventional Comments* untuk memberikan umpan balik mendalam, alternatif solusi kode modular, dan referensi spesifikasi teknis pada masing-masing PR.
   * **Automated Governance Setup:** Bangun pipeline validasi otomatis menggunakan **DangerJS / GitHub Actions** yang memverifikasi ketiadaan *breaking changes* pada schema Protobuf/OpenAPI, melarang PR > 400 LOC (kecuali generated code), dan memvalidasi kelengkapan tiket Jira/Linear.
   * **Architectural Decision Record (ADR):** Tulis 1 buah ADR formal yang menyelesaikan sengketa desain arsitektur pada PR #101 yang memandu tim keluar dari kebuntuan teknis.
   * **Post-Mortem & Team SLA Playbook:** Susun dokumen tata kelola tim yang menetapkan metrik review (SLA review maksimal 4 jam kerja, pembatasan reviewer maksimal 2 orang per tahap, dan *blameless dispute escalation path*).

3. **Kriteria Kelulusan (Enterprise Rubric):**
   * Review mengidentifikasi 100% cacat keamanan (P0) dan cacat konkurensi (P0) tanpa lolos satu pun ke status "Approved".
   * Tidak ada komentar bernada toksik atau menyerang personal; seluruh feedback berorientasi pada *code correctness*, *resilience*, dan edukasi teknis.
   * Pipeline CI/CD guardrail dapat mengeksekusi pemeriksaan metadata PR dan SAST secara mandiri.
```

---

## Catatan Implementasi Direktori Silabus

Struktur direktori repositori ini dirancang secara modular dan deterministik:

```bash
.
├── README.md
├── 01-fondasi-dan-psikologi/
│   ├── 01-cultural-pillars-and-psychological-safety.md
│   └── 02-reviewer-author-dynamic.md
├── 02-taksonomi-dan-checklist/
│   ├── 01-hierarchy-of-concerns.md
│   └── 02-pragmatic-checklists.md
├── 03-arsitektur-pr-dan-git/
│   ├── 01-trunk-based-and-stacked-prs.md
│   └── 02-anatomy-of-exemplary-pr.md
├── 04-otomasi-pre-review/
│   ├── 01-linters-formatters-git-hooks.md
│   └── 02-dangerjs-and-sast-gates.md
├── 05-review-keamanan-data/
│   ├── 01-appsec-owasp-inspection.md
│   └── 02-sensitive-data-crypto-review.md
├── 06-review-performa-konkurensi/
│   ├── 01-database-queries-locking.md
│   └── 02-concurrency-memory-leaks.md
├── 07-review-arsitektur-testing/
│   ├── 01-architecture-boundaries.md
│   └── 02-evaluating-test-efficacy.md
├── 08-metrik-dan-review-fatigue/
│   ├── 01-engineering-review-metrics.md
│   └── 02-mitigating-review-fatigue.md
├── 09-komunikasi-resolusi-konflik/
│   ├── 01-conventional-comments.md
│   └── 02-conflict-resolution-mentoring.md
├── 10-governance-compliance-ai/
│   ├── 01-compliance-four-eyes-principle.md
│   └── 02-ai-assisted-code-reviews.md
└── capstone/
    ├── instructions.md
    └── mock-prs/
```