# Enterprise Claude Code Engineering: Panduan Penguasaan Agentic Terminal DevTools

Selamat datang di kurikulum teknis **Claude Code** (`claude-code`). Kurikulum ini dirancang untuk mengubah paradigma rekayasa perangkat lunak Anda dari *AI-assisted autocompletion* (model Copilot konvensional) menjadi **Agentic Software Engineering** yang beroperasi langsung di tingkat terminal, file system, dan execution sandbox.

---

## 1. Course Overview & Mindset

### Pergeseran Paradigma: Dari Text Generator ke Terminal Agent
Claude Code bukan sekadar asisten percakapan (chat UI) atau ekstensi autokompresi kode di IDE. Claude Code adalah **agen berbasis perintah terminal (CLI)** yang dilengkapi kapabilitas eksekusi sistem operasi, manipulasi pohon direktori, refactoring multi-file, dan loop verifikasi deterministik mandiri.

```
+-----------------------------------------------------------------------+
|                         PARADIGMA TRADISIONAL                         |
|  Developer <---> Chat UI / IDE Autocomplete (Copy-Paste / Tab Accept) |
+-----------------------------------------------------------------------+
                                  VS
+-----------------------------------------------------------------------+
|                       AGENTIC CLI PARADIGM                            |
|  Developer (Intent & Constraints)                                     |
|       |                                                               |
|       v                                                               |
|  [ Claude Code Agent Engine ]                                         |
|       |                                                               |
|       +---> Tool 1: File Search & Semantic Grep (Codebase Discovery)  |
|       +---> Tool 2: Direct AST/Pattern Patching (Edit & Refactor)     |
|       +---> Tool 3: Shell Execution (Test, Lint, Build Loop)          |
|       +---> Tool 4: Model Context Protocol (MCP External Systems)     |
|       |                                                               |
|       v                                                               |
|  Verified Code Artifact + Deterministic Test Pass                     |
+-----------------------------------------------------------------------+
```

### Prinsip Inti Rekayasa
1. **Deterministik Mengontrol Probabilistik**: Model LLM bersifat stokastik. Pengembang enterprise wajib membangun pagar pengaman (*guardrails*) berupa *automated unit testing*, *linter*, *type checker*, dan *static analysis* agar agen Claude Code beroperasi dalam siklus umpan balik (*feedback loop*) yang terverifikasi.
2. **Context Window Hygiene**: Kualitas *reasoning* agen menurun drastis ketika context window dipenuhi artifak sampah. Kemampuan menyusun `.claudeignore`, merancang `CLAUDE.md`, dan memanfaatkan sub-tool penelusuran file secara hemat token adalah pembeda antara insinyur amatir dan arsitek agen.
3. **Least Privilege vs Autonomous Flow**: Menyeimbangkan keamanan eksekusi instruksi shell (mencegah *destructive write*, data leakage, atau unintended network calls) dengan kecepatan iterasi mandiri tanpa interupsi manual berlebih.

---

## 2. Learning Roadmap

```text
Claude Code Mastery Curriculum
│
├── BAB 01: Arsitektur & Paradigma Agentic CLI Claude Code
├── BAB 02: Indexing, Konteks Codebase, & Navigation Engine
├── BAB 03: Tool Use, Execution Sandbox, & Permission Model
├── BAB 04: Konfigurasi Proyek & Memory Protocol (CLAUDE.md)
├── BAB 05: Test-Driven Development (TDD) & Loop Verifikasi Otonom
├── BAB 06: Refactoring Skala Besar & Manajemen Perubahan Multi-File
├── BAB 07: Integrasi Ekosistem Model Context Protocol (MCP)
├── BAB 08: Token Budgeting, Cost Control, & Context Compaction
├── BAB 09: Otomasi Non-Interactive (Headless) & CI/CD Pipelines
└── BAB 10: Enterprise Capstone Project
```

---

## 3. Navigasi Detail Kurikulum

### [BAB 01: Arsitektur & Paradigma Agentic CLI Claude Code](01-arsitektur-dan-paradigma-agentic-cli/README.md)
Membedah arsitektur internal Claude Code CLI, runtime execution model, dan pemisahan tugas antara LLM reasoning core dengan terminal environment.
* [Modul 01: Paradigma Agentic CLI vs Extension IDE](01-arsitektur-dan-paradigma-agentic-cli/01-paradigma-agentic-cli-vs-extension-ide.md)
* [Modul 02: Instalasi Enterprise, Autentikasi API Key, & Otorisasi OAuth](01-arsitektur-dan-paradigma-agentic-cli/02-instalasi-autentikasi-otorisasi.md)
* [Modul 03: Siklus Hidup Agen: Reasoning, Action, Observation Loop](01-arsitektur-dan-paradigma-agentic-cli/03-siklus-hidup-agen-loop.md)

### [BAB 02: Indexing, Konteks Codebase, & Navigation Engine](02-indexing-konteks-codebase-navigation/README.md)
Mempelajari cara Claude Code membedah repo puluhan ribu baris kode tanpa meledakkan context window melalui mekanisme penelusuran cerdas.
* [Modul 01: Mekanisme File Discovery: Globbing, Regex Grep, & AST Search](02-indexing-konteks-codebase-navigation/01-file-discovery-globbing-grep.md)
* [Modul 02: Konfigurasi `.claudeignore` & Pengendalian Context Pollution](02-indexing-konteks-codebase-navigation/02-claudeignore-context-pollution.md)
* [Modul 03: Dynamic Context Injection & On-the-Fly File Loading](02-indexing-konteks-codebase-navigation/03-dynamic-context-injection.md)

### [BAB 03: Tool Use, Execution Sandbox, & Permission Model](03-tool-use-execution-sandbox-permission/README.md)
Menguasai kapabilitas aksi Claude Code dalam membaca, menulis, merevisi file, dan menjalankan sub-process shell dengan model keamanan ketat.
* [Modul 01: Terminal Execution Engine: Bash Tools & Subprocess Management](03-tool-use-execution-sandbox-permission/01-terminal-execution-bash-tools.md)
* [Modul 02: File System Mutation: View, Edit, Patch, & Overwrite Strategies](03-tool-use-execution-sandbox-permission/02-file-system-mutation-strategies.md)
* [Modul 03: Security Boundary: Approval Modes, Blacklisted Commands, & Isolation](03-tool-use-execution-sandbox-permission/03-security-boundary-approval-modes.md)

### [BAB 04: Konfigurasi Proyek & Memory Protocol (CLAUDE.md)](04-konfigurasi-proyek-memory-protocol/README.md)
Membangun ingatan permanen proyek, panduan arsitektur, dan *operational rules* yang dipatuhi oleh Claude Code di setiap iterasi.
* [Modul 01: Anatomi `CLAUDE.md`: Hierarchy, Precedence, & Struktur Standar](04-konfigurasi-proyek-memory-protocol/01-anatomi-claude-md-hierarchy.md)
* [Modul 02: Standardisasi Perintah Build, Test, Lint, & Runtime Commands](04-konfigurasi-proyek-memory-protocol/02-standardisasi-perintah-ops.md)
* [Modul 03: Penanaman Architectural Rules & Enforcing Code Conventions](04-konfigurasi-proyek-memory-protocol/03-architectural-rules-code-conventions.md)

### [BAB 05: Test-Driven Development (TDD) & Loop Verifikasi Otonom](05-tdd-loop-verifikasi-otonom/README.md)
Menerapkan siklus perbaikan kode otonom di mana agen memvalidasi kinerjanya sendiri menggunakan automated feedback loop.
* [Modul 01: Red-Green-Refactor Loop di Terminal CLI](05-tdd-loop-verifikasi-otonom/01-red-green-refactor-loop.md)
* [Modul 02: Self-Healing Pipeline: Menguraikan Stack Traces & Error Logs](05-tdd-loop-verifikasi-otonom/02-self-healing-stack-trace-logs.md)
* [Modul 03: Deterministic Quality Gates: Integrasi Linter & Type-Checker](05-tdd-loop-verifikasi-otonom/03-deterministic-quality-gates.md)

### [BAB 06: Refactoring Skala Besar & Manajemen Perubahan Multi-File](06-refactoring-skala-besar-multi-file/README.md)
Teknik orkestrasi perombakan kode yang melintasi puluhan file dan modul dependensi secara terstruktur tanpa menyebabkan regresi.
* [Modul 01: Dependency Graph Analysis & Blast Radius Mapping](06-refactoring-skala-besar-multi-file/01-dependency-blast-radius-mapping.md)
* [Modul 02: Atomic Changesets: Pembagian Tugas Refactoring Modular](06-refactoring-skala-besar-multi-file/02-atomic-changesets-modular.md)
* [Modul 03: Git Hygiene Otomatis: Granular Commits, Branches, & Diffs](06-refactoring-skala-besar-multi-file/03-git-hygiene-commits-diffs.md)

### [BAB 07: Integrasi Ekosistem Model Context Protocol (MCP)](07-integrasi-ekosistem-mcp/README.md)
Memperluas kekuatan Claude Code ke sistem luar repo menggunakan Model Context Protocol: database, browser sandbox, issue tracker, dan custom server.
* [Modul 01: Menghubungkan MCP Server ke Claude Code (`claude mcp add`)](07-integrasi-ekosistem-mcp/01-menghubungkan-mcp-server-cli.md)
* [Modul 02: Integrasi External Data: PostgreSQL/MySQL & REST API Explorer](07-integrasi-ekosistem-mcp/02-integrasi-external-data-db-api.md)
* [Modul 03: Custom In-House MCP Tooling untuk Keperluan Internal Perusahaan](07-integrasi-ekosistem-mcp/03-custom-in-house-mcp-tooling.md)

### [BAB 08: Token Budgeting, Cost Control, & Context Compaction](08-token-budgeting-cost-context/README.md)
Strategi manajemen operasional tingkat enterprise: optimasi pengeluaran token API, context pruning, dan pencegahan degradasi memori.
* [Modul 01: Analisis Konsumsi Token & Penetapan Budget Cap Operasional](08-token-budgeting-cost-context/01-analisis-konsumsi-token-budget.md)
* [Modul 02: Mekanisme Context Pruning, Summarization, & Compact Session](08-token-budgeting-cost-context/02-context-pruning-compact-session.md)
* [Modul 03: Model Selection Trade-offs: Sonnet vs Haiku vs Opus untuk Tugas CLI](08-token-budgeting-cost-context/03-model-selection-tradeoffs.md)

### [BAB 09: Otomasi Non-Interactive (Headless) & CI/CD Pipelines](09-otomasi-non-interactive-ci-cd/README.md)
Menjalankan Claude Code dalam mode tanpa antarmuka manusia (`headless mode`) di pipeline otomatis untuk triage tiket, PR reviews, dan migrasi batch.
* [Modul 01: Headless Execution Engine: Flag `--print`, `-p`, & Scripting Pipes](09-otomasi-non-interactive-ci-cd/01-headless-execution-scripting.md)
* [Modul 02: GitHub Actions & GitLab CI Integrasi Mandiri](09-otomasi-non-interactive-ci-cd/02-github-actions-gitlab-ci.md)
* [Modul 03: Threat Modeling, Secret Shielding, & Anti-Injection Guardrails](09-otomasi-non-interactive-ci-cd/03-threat-modeling-secret-shielding.md)

### [BAB 10: Enterprise Capstone Project](10-enterprise-capstone-project/README.md)
Proyek akhir komprehensif mengintegrasikan seluruh materi yang dipelajari: migrasi arsitektur monolit warisan (*legacy codebase*) secara otonom dengan Claude Code.
* [Modul 01: Spesifikasi Sistem & Arsitektur Monolith Target](10-enterprise-capstone-project/01-spesifikasi-arsitektur-target.md)
* [Modul 02: Eksekusi Autonomous Refactor, Migration, & Testing Pipeline](10-enterprise-capstone-project/02-eksekusi-autonomous-migration.md)
* [Modul 03: Audit Keamanan, Observabilitas, & Laporan Pasca-Migrasi](10-enterprise-capstone-project/03-audit-keamanan-laporan.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Capstone
**Autonomous Modernization Engine: Migrasi Monolith Node.js/CommonJS ke Modular TypeScript Microservice dengan Deterministic Testing & MCP Verification**

### Deskripsi Masalah
Sebuah sistem enterprise memiliki repositori *legacy* Node.js (CommonJS, Express, raw SQL queries tanpa ORM, tanpa unit test coverage, modul saling bergantung ketat). Tim engineering tidak memiliki alokasi waktu manual untuk menulis ulang sistem ke modern standard. 

### Tanggung Jawab Peserta
Peserta dituntut untuk memandu Claude Code (melalui CLI interaktif dan skrip non-interaktif headless) guna mengotomatisasi migrasi penuh dengan instruksi terstruktur tanpa merusak fungsionalitas bisnis yang ada.

### Arsitektur Alur Kerja Capstone

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LEGACY CODEBASE REPO                            │
│           (Node.js CommonJS + Raw SQL + Zero Test Coverage)            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               TAHAP 1: PREPARATION & REPO HARNESSING                   │
│   • Pembuatan `CLAUDE.md` terstruktur & penentuan rule ketat           │
│   • Claude Code menganalisis blast radius & menghasilkan dependency map │
│   • Pembuatan contract integration tests otomatis (Baseline)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Baseline Tests PASS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  TAHAP 2: ATOMIC REFACTORING LOOP                      │
│   • Claude Code mengonversi CJS -> ESM + TypeScript Strict Mode        │
│   • Isolasi routing ke Clean Architecture (Controller - Service - Repo)│
│   • Integrasi MCP SQLite/Postgres Server untuk schema validation        │
│   • Eksekusi loop `npm run build && npm test` secara mandiri           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ TDD Feedback Green
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 TAHAP 3: CI/CD HEADLESS AUTOMATION                     │
│   • Claude Code dijalankan via GitHub Actions / bash non-interaktif    │
│   • Menghasilkan ringkasan changelog, semantic commit history          │
│   • Security audit: scanning credential leaks & sandbox evaluation     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION-READY REPOSITORY                         │
│       (100% Typed, Modular, Full Coverage, Deterministic Pass)         │
└────────────────────────────────────────────────────────────────────────┘
```

### Kriteria Kelulusan Teknis (Acceptance Criteria)
1. **Zero Regressions**: Seluruh *contract testing* baseline yang dibuat di awal harus tetap berstatus **PASSED** setelah seluruh kode dimigrasikan ke TypeScript.
2. **TypeScript Strictness**: Konfigurasi `tsconfig.json` memiliki flag `"strict": true`, `"noImplicitAny": true`, dan kompilasi terminal menghasilkan exit code 0 (`tsc --noEmit`).
3. **CLAUDE.md Efficiency**: Proyek wajib menyertakan file `CLAUDE.md` modular yang membuat Claude Code dapat mengeksekusi *test*, *lint*, dan *format* tanpa instruksi berulang dari operator manusia.
4. **Tool Use & MCP**: Wajib menggunakan sedikitnya satu MCP Server lokal (misal: database connector atau local mock server) yang dipanggil oleh Claude Code untuk memverifikasi keabsahan skema data.
5. **Headless Execution Log**: Menyerahkan log eksekusi terminal di mana setidaknya satu modul/layanan berhasil direfaktor menggunakan mode *headless non-interactive* (`claude -p "..."`).

---

## 5. Cara Menggunakan Silabus Ini

1. Mulailah secara berurutan dari **BAB 01** untuk membongkar kebiasaan lama penggunaan chat UI dan membangun intuisi *terminal-first agent*.
2. Jangan melompati pembuatan konfigurasi `CLAUDE.md` (BAB 04) karena file ini merupakan fondasi operasional dari seluruh bab berikutnya.
3. Kerjakan setiap latihan langsung pada terminal mesin lokal Anda atau cloud development environment (seperti Dev Containers atau GitHub Codespaces).
4. Pastikan Anda memiliki saldo API Anthropic aktif atau token Claude Code yang terotorisasi sebelum memulai BAB 02.