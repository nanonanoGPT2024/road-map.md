# Kurikulum Enterprise: Claude Code & Autonomous Agents
## BAB 04: Konfigurasi Proyek & Memory Protocol
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik pada level Principal Engineer / Enterprise Architect diharapkan mampu:

1. **Menganalisis Mekanisme Resolusi Konteks:** Membedah siklus hidup *context ingestion* Claude Code dari filesystem traversal, evaluasi `.claudeignore`, resolusi bertingkat `CLAUDE.md`, hingga serialisasi *system prompt*.
2. **Merancang Protokol Memori Berjenjang:** Mengembangkan arsitektur memori multi-tingkat (Global, Project, Workspace Subtree, Session, Ephemeral) yang memitigasi degradasi *attention span* pada Large Language Model (LLM).
3. **Mengoptimalkan Token Budget & Compaction:** Mengonfigurasi strategi komparasi context window, *lossless vs. lossy compaction*, dan memori eksternal melalui Model Context Protocol (MCP) Memory Server untuk menekan latensi hingga 45% dan biaya API hingga 60%.
4. **Mengimplementasikan Dynamic Memory Injection:** Membangun *lifecycle hooks* berbasis script shell dan AST-aware dynamic context injector guna menyuplai metadata proyek secara deterministik sebelum komputasi LLM dimulai.
5. **Menegakkan Tata Kelola Keamanan Konteks:** Mengaudit serta memblokir kebocoran kredensial, PII, dan secret dari *context window* Claude Code menggunakan sanitasi deterministik berbasis regex dan AST scanner pada pipeline CI/CD.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib memiliki penguasaan mendalam pada domain berikut:

* **Sistem Operasi & Shell Internals:** Mahir menggunakan Bash/Zsh, POSIX system calls, I/O redirection, process isolation, dan filesystem permissions.
* **LLM Architecture & Tokenomics:** Memahami mekanisme self-attention, context window limits, tokenization (BPE/Tiktoken), context drift, serta degradasi *needle-in-a-haystack* pada dokumen panjang.
* **Claude Code CLI Fundamentals:** Memahami sintaks dasar Claude Code CLI, instalasi binary, dan integrasi API key Anthropic.
* **Format Serialisasi & Protokol:** Penguasaan tingkat lanjut atas JSON, YAML, Markdown AST, dan Model Context Protocol (MCP) berbasis JSON-RPC 2.0 via STDIO.
* **Software Engineering Practice:** Pengalaman mengelola arsitektur monorepo skala enterprise (Nx, Turborepo, atau Bazel) dan integrasi pipeline CI/CD.

---

### 3. Concept & Internal Architecture

Claude Code tidak beroperasi sebagai script prompt tunggal, melainkan sebuah orkestrator agen otonom berbasis loop *ReAct* (Reasoning + Acting) yang sangat bergantung pada efisiensi context window. Arsitektur memori internal Claude Code dirancang untuk menyelesaikan dilema dasar AI-assisted engineering: **Keterbatasan Token Budget vs. Kebutuhan Konteks Monorepo**.

```
+-----------------------------------------------------------------------------+
|                           CLAUDE CODE CONTEXT ENGINE                        |
+-----------------------------------------------------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
     [ DETERMINISTIC INGESTION ]              [ RUNTIME MEMORY PROTOCOL ]
                   |                                       |
     +-------------+-------------+             +-----------+-----------+
     |             |             |             |           |           |
     v             v             v             v           v           v
 Global Config  Project AST  Workspace Tree   Session    Dynamic MCP   Compaction
 ~/.claude/     CLAUDE.md    Sub-CLAUDE.md    History   Memory Server  Engine
+-----------------------------------------------------------------------------+
```

#### A. Mekanisme Resolusi Hirarki Konteks (Deterministic Path Resolution)
Saat Claude Code diinisialisasi dalam suatu path direktori, *Context Resolver Engine* menjalankan algoritma *Deterministic Breadth-First-Search (BFS) Bottom-Up Traversal*:

1. **Global Base Layer (`~/.claude/CLAUDE.md` & `~/.claude.json`):** Memuat preferensi developer global, token limits, default tools, dan telemetry opt-outs.
2. **Enterprise / Root Policy (`<repo-root>/CLAUDE.md`):** Mendefinisikan arsitektur sistem level makro, standar coding absolut, command test universal, dan boundaries operasional.
3. **Workspace Subtree Policy (`<repo-root>/apps/service-a/CLAUDE.md`):** Melakukan *override* atau memperkaya direktif root dengan aturan lokal (misal: Service A menggunakan Go murni dengan target latensi p99 < 10ms, sementara Service B menggunakan Node.js/TypeScript).
4. **Rule Merging & Precedence Engine:** Menggabungkan array konfigurasi dengan aturan resolusi: *Local scoped rules supersedes parent/global rules unless tagged with `[IMMUTABLE]`*.

#### B. Context Window Lifecycle & Compaction Mechanism
Kapasitas token Claude (misal: 200,000 tokens pada Claude 3.5 Sonnet) dialokasikan dengan strategi partisi statis dan dinamis:

* **Reserved System & Tools Space (~20%):** Skema JSON tool calling (Bash, Glob, Grep, Edit, Read), baseline system prompt, dan context guardrails.
* **Active Working Memory / Turn Buffer (~50%):** File contents yang dibaca, AST search results, command execution stdout/stderr, dan percakapan terkini.
* **Dynamic Ephemeral Memory (~30%):** Memori sementara yang dapat dikompresi ketika token limit menyentuh *High-Water Mark* (biasanya 75% dari total context window).

Ketika ambang batas token terlampaui, Claude Code memicu **Memory Compaction Subsystem**:
1. **Pruning Non-Essential AST:** Trace error historis yang sudah diselesaikan dipangkas (*pruned*).
2. **Semantic Summarization:** Ringkasan percakapan sebelumnya dibuat secara rekursif, menggantikan ratusan baris log mentah menjadi format deklaratif: `[STATE]: Service-A auth middleware refactored to JWT RS256; Test PASSING`.
3. **External State Offloading:** State yang jarang diakses dialihkan ke MCP Memory Server berbasis vector database lokal atau key-value SQLite (`~/.claude/memory.db`).

---

### 4. Why & What

#### Problem Statement (The "Why")
Pada proyek enterprise monorepo (berisi puluhan microservices dan jutaan baris kode):
* Memasukkan seluruh basis kode ke dalam context window secara naif adalah mustahil (terbentur batas *context length* dan biaya token berlipat ganda).
* LLM mengalami fenomena **Context Rot / Attention Degradation**: Semakin banyak informasi tidak relevan dalam prompt, akurasi penalaran kode Claude turun drastis (halusinasi sintaksis, pemanggilan tool yang salah sasaran).
* Pengembang yang berbeda dalam satu organisasi memproduksi kode yang tidak konsisten jika panduan arsitektur (*architectural boundaries*) tidak diinjeksikan secara deterministik ke dalam setiap sesi kerja agen.

#### Solution Architecture (The "What")
* **CLAUDE.md Memory Protocol:** Pendekatan *Infrastructure-as-Code* untuk konteks LLM. Format terstandarisasi yang mendefinisikan *Behavioral Directives*, *Build Commands*, *Architectural Invariants*, dan *Anti-Patterns*.
* **Dynamic Lifecycle Hooks:** Skrip deterministik yang dieksekusi sebelum prompt diproses (*pre-prompt*) untuk menyuntikkan status git, konfigurasi dependensi runtime, dan metadata commit terbaru.
* **Scoped Memory Isolation:** Isolasi konteks sub-aplikasi guna memastikan instruksi domain frontend (misal: React/Next.js) tidak mengontaminasi instruksi backend (misal: Rust/gRPC).

---

### 5. How: Alur Kerja Implementasi Detail

Implementasi arsitektur memori Claude Code tingkat enterprise dieksekusi melalui 5 fase:

```
[ Fase 1: Discovery ]
       |
       v
[ Fase 2: Filtering (.claudeignore Engine) ]
       |
       v
[ Fase 3: Resolusi Hirarki Konteks (Hierarchical Merging) ]
       |
       v
[ Fase 4: Dynamic Pre-prompt Hook Execution ]
       |
       v
[ Fase 5: Execution & Compaction Loop ]
```

1. **Fase 1 - Workspace Ingestion:** Claude Code memindai root directory proyek menggunakan traversal native binary berkinerja tinggi.
2. **Fase 2 - Security & Token Filtering:** Engine menerapkan `.claudeignore` untuk membuang artefak biner, cache, file credentials, dan direktori data masif (misal: `node_modules/`, `target/`, `.git/`, `.env*`).
3. **Fase 3 - Hierarchical Memory Stitching:** Engine membaca `~/.claude/CLAUDE.md`, melewatinya ke root `CLAUDE.md`, kemudian membaca nested `CLAUDE.md` di level sub-direktori aktif. Engine memetakan rule tree menggunakan inheritance model.
4. **Fase 4 - Dynamic Hook Context Generation:** Skrip eksternal (misal: `.claude/hooks/pre-prompt.sh`) dijalankan. Output stdout dari skrip ini ditambahkan sebagai context payload bertipe `System-Dynamic`.
5. **Fase 5 - Conversational Execution & Compaction:** Agen mengeksekusi perintah. Ketika *Context Gauge* menyentuh threshold kritis, compaction algorithm mentransformasikan context state dan menyimpannya ke session memory cache.

---

### 6. Analogy & Architecture Diagrams

#### Analogi Sistem
Bayangkan Claude Code sebagai **Kepala Arsitek Software Kontrak**:
* **System Prompt Asli:** Lisensi profesional dan kemampuan fundamental arsitek (tahu cara membaca dan menulis kode).
* **Global `~/.claude/CLAUDE.md`:** Manual kerja personal arsitek (kebiasaan kerja pribadi, editor tools yang disukai).
* **Root `CLAUDE.md`:** Buku biru (*Blueprint*) proyek gedung berskala besar (aturan keselamatan gedung, material standar monorepo).
* **Sub-module `CLAUDE.md`:** Spesifikasi teknis ruangan khusus, misal: ruang server/radiologi (aturan isolasi ketat untuk service tertentu).
* **Memory Compaction:** Buku log arsitek; alih-alih menyimpan setiap struk pembelian baut, arsitek hanya mencatat: *"Baut baja grade 8 telah dibeli dan dipasang pada kolom B3"*.

#### Diagram Arsitektur Memory Ingestion Pipeline

```
+-----------------------------------------------------------------------------------+
| FILESYSTEM ROOT: /workspace/enterprise-monorepo                                  |
+-----------------------------------------------------------------------------------+
  |
  +-- .claudeignore       ---> [ Ignored: build/, dist/, *.pem, secrets/, .git/ ]
  |
  +-- CLAUDE.md           ---> [ Global Repo Invariants: Conventional Commits,      ]
  |                            [ Zero Unhandled Errors, Mandatory Unit Tests       ]
  |
  +-- apps/
  |    +-- auth-service/
  |    |    +-- CLAUDE.md ---> [ Auth-Specific: Go 1.23, OAuth2/OIDC, FIPS-crypto   ]
  |    |    +-- src/
  |    +-- billing-core/
  |         +-- CLAUDE.md ---> [ Billing-Specific: Rust, Strict Decimal Math, Paxos]
  |         +-- src/
  |
  +-- .claude/
       +-- hooks/
       |    +-- pre-prompt.sh -> [ Emits: Git SHA, Active Branch, Vuln Scan Status ]
       +-- settings.json      -> [ Tool configurations, MCP connection strings      ]

                                     |
                                     v
+-----------------------------------------------------------------------------------+
| CONTEXT SERIALIZER ENGINE                                                         |
|                                                                                   |
| 1. Evaluasi .claudeignore                                                         |
| 2. Concatenate Hierarchical Memory:                                               |
|    Prompt = Root(CLAUDE.md) + Scoped(apps/billing-core/CLAUDE.md) + Dynamic(Hook) |
| 3. Budget Validation: Ensure Total Ingested Tokens < Reserved System Cap         |
+-----------------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------------+
| CLAUDE COMPUTE ENGINE (LLM Context Window)                                         |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Baseline Project Configuration
Konfigurasi minimal yang valid untuk microservice backend berbasis Node.js/TypeScript.

##### File: `CLAUDE.md` (Project Root)
```markdown
# Project: Payment Gateway Adapter

## Core Stack
- Runtime: Node.js v20 LTS (Node engine enforce: strict)
- Language: TypeScript 5.4 (Strict mode: enabled, noImplicitAny: true)
- Framework: Fastify v4
- Testing: Vitest

## Build & Test Commands
- Install: `pnpm install --frozen-lockfile`
- Build: `pnpm build`
- Typecheck: `pnpm typecheck`
- Unit Test: `pnpm test:unit`
- Integration Test: `pnpm test:integration`
- Single Test: `pnpm test -- tests/unit/{filename}.test.ts`

## Invariant Rules
- Do NOT use `any` under any circumstances.
- All monetary operations must use `bigint` representing minor currency units (cents).
- Never log headers containing `Authorization` or `X-Api-Key`.
```

---

#### B. Practical Enterprise Example: Multi-Tier Monorepo Architecture

Berikut adalah implementasi konfigurasi arsitektur monorepo skala enterprise untuk klaster backend perbankan.

##### 1. Master Configuration: `/CLAUDE.md` (Root Monorepo)
```markdown
# Enterprise Banking Engine Monorepo Guidelines
[POLICY-VERSION: 3.4.1]
[ENFORCEMENT: STRICT]

## Immutable Directives
1. **Zero Hallucinated Dependencies**: Do not import external packages not present in the respective package.json / go.mod / Cargo.toml.
2. **Defensive Programming**: All external IO calls must be bounded by explicit timeouts (Context with Timeout / AbortSignal).
3. **Audit Trail**: Every domain state mutation must emit an OpenTelemetry event.

## Repository Layout
- `services/fiat-engine`: Go-based settlement engine.
- `services/ledger-core`: Rust-based immutability ledger.
- `libs/telemetry`: Shared enterprise instrumentation.

## Commit Protocol
Conventional Commits format: `<type>(<scope>): <short-description>`
Types: feat, fix, refactor, perf, test, chore.
Breaking changes must contain `BREAKING CHANGE:` in the footer.
```

##### 2. Scoped Configuration: `/services/ledger-core/CLAUDE.md`
```markdown
# Ledger Core Domain Configuration
[SCOPE: services/ledger-core]
[PARENT: //CLAUDE.md]

## Technology Stack
- Language: Rust 1.78.0 edition 2021
- Storage: RocksDB via custom binding
- Concurrency: Tokio async runtime

## Scoped Commands
- Build: `cargo build --release --manifest-path services/ledger-core/Cargo.toml`
- Test Unit: `cargo test --bin ledger-core --lib`
- Test Integration: `cargo test --test integration_tests -- --nocapture`
- Clippy (Lint): `cargo clippy -- -D warnings`
- Format Check: `cargo fmt --check`

## Architectural Invariants
- Integer overflow: Must use `checked_*`, `overflowing_*`, or `saturating_*` arithmetic. Unchecked math operators (`+`, `-`, `*`) will fail CI.
- No `unwrap()` or `expect()` in production paths. All errors must map into `LedgerEngineError` via `thiserror`.
- Thread safety: State must be wrapped in `Arc<RwLock<T>>` or use lock-free channels.
```

##### 3. Dynamic Context Injector Hook: `/.claude/hooks/pre-prompt.sh`
Skrip deterministik untuk menginjeksi runtime metrics dan status repository langsung ke *context baseline* Claude Code sebelum LLM menjalankan evaluasi.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Output format must be clean text or markdown for context insertion
echo "=== DYNAMIC RUNTIME CONTEXT INJECTION ==="
echo "Timestamp (UTC): $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Active Git Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "Latest Commit SHA: $(git rev-parse --short HEAD)"

# Verify if workspace is clean
if ! git diff-index --quiet HEAD --; then
    echo "Workspace Status: DIRTY (Uncommitted modifications present)"
    echo "Modified Files:"
    git status --porcelain | head -n 10
else
    echo "Workspace Status: CLEAN"
fi

# Detect active container / toolchain environment
if command -v rustc &> /dev/null; then
    echo "Rust Toolchain: $(rustc --version)"
fi

if command -v go &> /dev/null; then
    echo "Go Toolchain: $(go version)"
fi

echo "========================================="
exit 0
```

##### 4. Filtering Configuration: `/.claudeignore`
```gitignore
# VCS & System
.git/
.github/
.idea/
.vscode/

# Build Artifacts & Binaries
target/
dist/
build/
bin/
*.o
*.a
*.so
*.dylib
*.exe

# Dependencies
node_modules/
vendor/

# Secrets, Credentials, and Environment Files
.env*
!*.env.example
*.pem
*.key
*.pkcs12
*.pfx
secrets/
credentials/
vault-token

# Massive Data & Logs
*.log
*.sqlite
*.sqlite-wal
*.dump
coverage/
.nyc_output/
```

---

### 8. Real World Case Study

#### Skenario: Financial Monorepo Migration di Global FinTech Core
* **Konteks:** Perusahaan fintech mengelola monorepo berbasis 80+ microservices yang ditulis dalam kombinasi Go dan TypeScript.
* **Insiden/Masalah Awal:** 
  Claude Code digunakan tanpa protokol memori terstruktur. LLM membaca file `.env` lokal yang berisi API secret staging, mengalami degradasi token karena parsing folder `coverage/` berukuran 1.2 GB, dan secara konsisten merekomendasikan `jest` padahal monorepo telah migrasi ke `vitest`.
  * Rata-rata token terpakai per sesi: 185,000 tokens (mendekati batas maksimal).
  * Latensi time-to-first-token (TTFT): 14.8 detik.
  * Sering terjadi kegagalan pemanggilan tools (*tool call hallucinations*).

#### Implementasi Solusi
1. **Penerapan Multi-Tier Memory Hierarchy:**
   * Dibuat root `CLAUDE.md` yang mengunci standard tooling organisasi (Package Manager: `pnpm`, Test Runner: `vitest`).
   * Setiap service mengimplementasikan `CLAUDE.md` terisolasi dengan daftar script test deterministik.
2. **Pembersihan Jalur Konteks via `.claudeignore` Agresif:**
   * Mengabaikan file coverage, cache builds, auto-generated OpenAPI client SDK, dan file kredensial.
3. **Integrasi Dynamic Pre-Prompt Script:**
   * Menginjeksi service name target dan status CI lokal secara real-time.
4. **Penerapan MCP Persistent Memory Server:**
   * Menggunakan local SQLite memory protocol untuk menyimpan arsitektur database schema, menghindarkan Claude Code dari membaca file `schema.sql` (15,000 baris) secara berulang-ulang.

#### Hasil Metrik Komparatif

| Metrik Evaluasi | Pra-Implementasi | Pasca-Implementasi | Tingkat Peningkatan |
| :--- | :--- | :--- | :--- |
| **Rata-rata Konsumsi Token / Turn** | 185,400 tokens | 34,200 tokens | **-81.5% token consumption** |
| **Latensi Respon (p95 TTFT)** | 14.8 detik | 3.1 detik | **79% latency reduction** |
| **Biaya API per Developer/Bulan** | $480.00 USD | $88.50 USD | **-81.5% cost reduction** |
| **Tingkat Halusinasi Tool Test** | 42.5% | 0.8% | **98% reliability gain** |
| **Insiden Secret Leakage** | 3 insiden | 0 insiden | **100% compliance** |

---

### 9. Trade-offs: Architectural Decision Matrix

Implementasi arsitektur konfigurasi memori Claude Code melibatkan kompromi teknis:

| Parameter Arsitektur | Low-Budget / Minimal Memory | Monolithic Centralized Memory | Multi-Tier Scoped Protocol (Modul Ini) |
| :--- | :--- | :--- | :--- |
| **Context Latency** | **Sangat Rendah** (<2s TTFT) | **Sangat Tinggi** (>12s TTFT) | **Moderat - Rendah** (2.5 - 4s TTFT) |
| **Operational Cost (Token)** | **Sangat Rendah** | **Sangat Tinggi** (Cepat kena rate-limit) | **Optimal** (Hanya context relevan) |
| **Domain Awareness Depth** | **Rendah** (Sering halusinasi domain) | **Moderat** (Tergelincir noise data) | **Sangat Tinggi** (AST & scoped rules) |
| **Maintenance Complexity** | **Zero Maintenance** | **Rendah** (Hanya 1 file root) | **Tinggi** (Perlu audit hierarki berjenjang) |
| **Security Risk (Context Leak)**| **Tinggi** (Tidak ada filter terstruktur)| **Kritis** (Semua file berpotensi termuat)| **Minimal** (Sanitasi berlapis via ignore/hooks)|

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: Menggunakan CLAUDE.md Sebagai Dokumentasi Lengkap (Data Dumping)
* **Pola Buruk:** Menempelkan (*pasting*) seluruh dokumentasi spesifikasi API REST setebal 4,000 baris langsung ke dalam root `CLAUDE.md`.
* **Dampak Negatif:** Mengonsumsi 40k+ tokens secara statis pada setiap turn percakapan, memicu attention drift, dan memangkas sisa token untuk komputasi working memory.
* **Solusi Perbaikan:** Simpan spesifikasi dalam file `docs/api.json` dan letakkan *pointer* di `CLAUDE.md`: 
  `API Specs located at docs/api.json. Use 'Read' tool on demand; DO NOT read proactively.`

#### Anti-Pattern 2: Ambiguitas Perintah Eksekusi Test
* **Pola Buruk:** Menuliskan `Test: run npm test or yarn test`.
* **Dampak Negatif:** Agen LLM akan mencoba menebak environment, menjalankan `npm test`, lalu jika gagal mencoba `yarn`, menghabiskan waktu eksekusi dan memicu state diskontinuitas pada lockfile.
* **Solusi Perbaikan:** Gunakan instruksi deterministik: 
  `Test: pnpm --filter @services/auth test:unit`

#### Anti-Pattern 3: Kebocoran `.env` Akibat Aturan `.claudeignore` Kurang Komprehensif
* **Pola Buruk:** Menambahkan `.env` ke `.claudeignore` namun lupa pada file seperti `.env.local`, `.env.production`, atau `.env.vault`.
* **Dampak Negatif:** Secret terkirim ke context LLM, berpotensi masuk ke log caching eksternal atau melanggar kepatuhan SOC2/PCI-DSS.
* **Solusi Perbaikan:** Gunakan wildcard pattern ketat:
  ```gitignore
  .env*
  !*.env.example
  ```

#### Panduan Troubleshooting Diagnostik

```
[Problem: Claude Code Mengabaikan Aturan Lokal di Subdirektori]
   |
   +---> Periksa: Apakah format tagging scope valid?
   |     Format: [SCOPE: path/to/dir] pada baris pertama nested CLAUDE.md.
   |
   +---> Periksa: Apakah ada syntax error Markdown (unclosed code fences)?
   |     Markdown parsing failure menyebabkan engine menolak block konfigurasi.
   |
   +---> Jalankan Validasi Ingestion CLI:
         claude config print-context --target apps/my-app
         (Memastikan merged context tree sesuai ekspektasi)
```

---

### 11. Best Practices & Production Checklist

#### Production Checklist

- [ ] **Security Boundaries:** File `.claudeignore` ditempatkan di root dan memblokir seluruh pola file secret (`.env*`, `*.pem`, `*.key`, `credentials/`).
- [ ] **Strict Immutability:** Flag `[IMMUTABLE]` disematkan pada aturan root `CLAUDE.md` yang mengatur aspek hukum, lisensi, atau keamanan organisasi.
- [ ] **Token Budget Constraint:** Ukuran akumulasi seluruh file `CLAUDE.md` dalam satu path resolusi tidak melebihi 2,500 token (kira-kira ~10,000 karakter).
- [ ] **Deterministic Commands:** Tidak ada perintah ambigu pada blok *Build & Test Commands*. Seluruh package manager, target directory, dan script flags dideklarasikan secara eksplisit.
- [ ] **Lifecycle Pre-Prompt Hooks:** Skrip validasi integritas pre-prompt memiliki timeout eksekusi ketat (< 1.5 detik) agar tidak memicu TTFT latency overhead.
- [ ] **Version Controlled Context:** Konfigurasi `.claude/`, `CLAUDE.md`, dan `.claudeignore` wajib masuk ke version control (Git) dan dievaluasi via review pull request.

---

### 12. Hands-on Practice

Praktikum ini mensimulasikan setup arsitektur memori enterprise di direktori `hands-on/m02/`.

#### Langkah 1: Setup Workspace dan Struktur Direktori
Buka terminal dan jalankan urutan command berikut:

```bash
mkdir -p hands-on/m02/enterprise-architecture
cd hands-on/m02/enterprise-architecture

# Inisialisasi struktur direktori microservices
mkdir -p apps/auth-service/src
mkdir -p apps/payment-service/src
mkdir -p .claude/hooks
mkdir -p secrets
```

#### Langkah 2: Buat File `.claudeignore`
```bash
cat << 'EOF' > .claudeignore
# Keamanan & Secrets
secrets/
.env*
!*.env.example
*.key
*.pem

# Build Artefak
dist/
build/
node_modules/

# Logs
*.log
EOF
```

#### Langkah 3: Konfigurasi Root Policy `CLAUDE.md`
```bash
cat << 'EOF' > CLAUDE.md
# Enterprise System Invariants
[ORGANIZATION: Global Financial Corp]
[LEVEL: ROOT-STRICT]

## Mandatory Architectural Rules
1. Every async function must implement structured error handling via Result pattern.
2. Under no circumstance should sensitive PII (PAN, CVV, SSN) be passed unencrypted.
3. Tests must be deterministic: no external network dependency permitted during execution.

## Package Orchestration
- Monorepo Engine: Turborepo
- Execution Command: `pnpm turbo run <task> --filter=<scope>`
EOF
```

#### Langkah 4: Konfigurasi Scoped Memory untuk Sub-Service
```bash
cat << 'EOF' > apps/auth-service/CLAUDE.md
# Auth Service Context Protocol
[SCOPE: apps/auth-service]
[ENGINEERING-TIER: CRITICAL-SECURITY]

## Domain Toolchain
- Runtime: Node.js 20 LTS
- Target Framework: Fastify with @fastify/jwt

## Local Validation Commands
- Lint & Style: `pnpm --filter auth-service lint`
- Unit Testing: `pnpm --filter auth-service test:unit`
- Cryptographic Audit: `pnpm --filter auth-service audit:crypto`
EOF
```

#### Langkah 5: Implementasikan Dynamic Context Injection Hook
```bash
cat << 'EOF' > .claude/hooks/pre-prompt.sh
#!/usr/bin/env bash
set -euo pipefail

echo "### HOOK CONTEXT: REALTIME METRICS ###"
echo "Machine Architecture: $(uname -m)"
echo "Git Worktree State: $(git status --porcelain | wc -l | tr -d ' ') uncommitted files"
echo "Security Quarantine Status: SECURE"
echo "######################################"
EOF

chmod +x .claude/hooks/pre-prompt.sh
```

#### Langkah 6: Validasi Parsing Memori
Uji eksekusi skrip hook lokal dan validasi context injection:

```bash
# Eksekusi hook secara manual untuk memastikan zero non-zero exit code
./.claude/hooks/pre-prompt.sh

# Verifikasi proteksi secret
touch secrets/vault.key
# Pastikan git status mengabaikan direktori secrets jika dimasukkan juga ke .gitignore
```

---

### 13. Exercises

#### Level Easy
Ubah konfigurasi root `CLAUDE.md` pada folder praktikum agar Claude Code selalu menggunakan format log JSON terstruktur (`{"level": "...", "msg": "..."}`) saat menyarankan modifikasi kode logging.
* **Kriteria Keberhasilan:** Aturan tertera jelas di bawah section `## Coding Standards` dan terdeteksi saat simulasi pembuatan middleware logging.

#### Level Medium
Buat sebuah file konfigurasi scoped `apps/payment-service/CLAUDE.md` yang mendefinisikan aturan penanganan angka desimal uang menggunakan pustaka `dinero.js`. Claude Code harus memunculkan error instruksi apabila ada file di service tersebut yang menggunakan tipe data native `number` untuk operasi kalkulasi billing.
* **Kriteria Keberhasilan:** Terdapat aturan sintaksis eksplisit di scoped `CLAUDE.md` dan testing command yang memetakan ke target filter payment-service secara spesifik.

#### Level Hard
Kembangkan script bash lifecycle hook `.claude/hooks/pre-prompt.sh` yang secara dinamis memeriksa apakah ada file *staged* di Git yang ukurannya melebihi 100KB. Jika ada, hook tersebut harus mengeluarkan output peringatan ke context Claude: `[WARNING: Large file detected in staging: <file_name>. Avoid reading entire content to prevent context window explosion]`.
* **Kriteria Keberhasilan:** Skrip berjalan dalam waktu < 200ms, menangani skenario zero staged files tanpa error (`set -euo pipefail`), dan menyuplai context warning secara presisi.

---

### 14. Enterprise Architectural Challenge

**Konteks Tantangan:**
Sebuah platform perbankan multinasional sedang mengonsolidasikan 15 legacy monorepo ke dalam 1 unified monorepo berbasis Bazel. Monorepo baru ini berisi modul C++ (High Frequency Trading core), Java (Payment clearance), dan TypeScript (Customer Dashboard). 

**Masalah Arsitektural:**
1. Developer mengeluhkan bahwa Claude Code sering menggunakan compiler flags Java ketika menganalisis modul C++.
2. Sesi chat Claude Code mengalami latensi hingga 30 detik karena traversal Bazel symlinks (`bazel-*`) yang menciptakan infinite loop directory scanning.
3. Tim audit keamanan menemukan bahwa Claude Code membaca file dump database pengujian (`test_fixtures/*.sql`) yang secara tidak sengaja memuat 50,000 data PII nasabah.

**Tugas Anda (Sebagai Principal System Architect):**
Rancang dan implementasikan blue print memory architecture yang mencakup:
1. Skema file `.claudeignore` universal yang mengeliminasi masalah Bazel symlink recursion dan data dump leakage tanpa mengabaikan integration test fixtures yang valid.
2. Hirarki `CLAUDE.md` multi-tier yang memisahkan instruksi build Bazel universal di level root dari spesifikasi unik compiler flag C++ (Clang 18) dan Java (JDK 21 via Bazel toolchains).
3. Strategi integrasi MCP Memory Server eksternal untuk menyimpan definisi protobuf monorepo yang sangat besar (>500 proto files), sehingga Claude Code dapat melakukan *semantic search* schema tanpa menaruh semua file `.proto` ke dalam working context.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa fungsi utama file `.claudeignore` dalam arsitektur eksekusi Claude Code?
   - A. Menghapus file dari disk lokal secara otomatis saat agent berjalan.
   - B. Mencegah file atau direktori tertentu dibaca dan diunggah ke context window LLM.
   - C. Mengabaikan eksekusi testing yang gagal pada pipeline CI/CD.
   - D. Menyembunyikan file dari git commit history.
   *Jawaban:* **B** | *Rasional:* `.claudeignore` membatasi context ingestion engine agar tidak menyerap file sensitif, artefak binary, atau direktori besar ke dalam payload LLM.

2. Di lokasi mana file konfigurasi memori global Claude Code disimpan secara default pada sistem operasi berbasis POSIX?
   - A. `/etc/claude/CLAUDE.md`
   - B. `~/.claude/CLAUDE.md`
   - C. `/var/log/claude.conf`
   - D. `~/.config/claude/settings.env`
   *Jawaban:* **B** | *Rasional:* Baseline preferensi developer global berada di home directory user: `~/.claude/CLAUDE.md`.

3. Mengapa format perintah eksekusi test pada `CLAUDE.md` harus dideklarasikan secara deterministik?
   - A. Karena Claude Code tidak memiliki izin Bash.
   - B. Untuk mencegah halusinasi tool di mana LLM mencoba berbagai package runner berbeda yang membuang kuota token dan merusak environment.
   - C. Agar file `package.json` tidak perlu dibaca oleh compiler OS.
   - D. Wajib secara hukum lisensi open source.
   *Jawaban:* **B** | *Rasional:* Deklarasi deterministik (misal: `pnpm test`) mengarahkan tool runner secara langsung tanpa trial-and-error yang boros token.

4. Apa dampak negatif langsung jika `CLAUDE.md` berukuran terlalu besar (>50,000 token)?
   - A. Claude Code akan crash seketika dengan pesan `Segmentation Fault`.
   - B. Menghabiskan token budget, memperlambat TTFT (latency), dan memicu context degradation (attention drift).
   - C. Git status repository akan otomatis terkunci (*read-only*).
   - D. Menghapus konfigurasi global `~/.claude.json`.
   *Jawaban:* **B** | *Rasional:* Ingestion token yang masif pada system prompt mengurangi kapasitas context reasoning aktif dan memperlambat pemrosesan model attention.

5. Tag apa yang digunakan pada root `CLAUDE.md` enterprise untuk mencegah instruksi di dalamnya di-override oleh sub-directory configuration?
   - A. `[SCOPED]`
   - B. `[DYNAMIC]`
   - C. `[IMMUTABLE]`
   - D. `[TEMPORARY]`
   *Jawaban:* **C** | *Rasional:* Tag konvensional `[IMMUTABLE]` digunakan oleh context resolver engine sebagai penanda aturan absolut yang mengabaikan downstream overrides.

---

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Dalam resolusi hirarki konteks, jika file root `/CLAUDE.md` menetapkan `Node: v20`, namun sub-service file `/services/legacy/CLAUDE.md` menetapkan `Node: v18`, bagaimana Context Resolver menyelesaikan ambiguitas ketika Claude Code beroperasi di dalam `/services/legacy`?
   - A. Error inkonsistensi dilempar dan eksekusi dihentikan.
   - B. Aturan root `/CLAUDE.md` selalu menang tanpa pengecualian.
   - C. Aturan scoped terdekat `/services/legacy/CLAUDE.md` melakukan override lokal, kecuali jika aturan root ditandai `[IMMUTABLE]`.
   - D. Kedua versi digabungkan menjadi array `Node: [v18, v20]`.
   *Jawaban:* **C** | *Rasional:* Resolusi konteks menggunakan prinsip scope inheritance bertingkat; aturan lokal terdekat menimpa aturan parent kecuali terkunci secara immutable.

7. Kapan proses *Memory Compaction* secara otomatis dipicu dalam sesi Claude Code?
   - A. Setiap 5 menit sekali berdasarkan cron runtime internal.
   - B. Ketika total akumulasi context window mendekati high-water mark token capacity.
   - C. Hanya saat pengguna mengetik perintah `/compact` atau `/clear`.
   - D. Setiap kali pengguna melakukan git commit baru.
   *Jawaban:* **B** | *Rasional:* Compaction subsystem secara otomatis memangkas dan meringkas state ketika token working memory mencapai ambang batas saturasi kapasitas model.

8. Apa keuntungan utama arsitektur eksekusi skrip dinamis via `.claude/hooks/pre-prompt.sh` dibanding menuliskannya secara statis di `CLAUDE.md`?
   - A. Hook dapat mengakses private network tanpa internet.
   - B. Menyediakan data real-time lingkungan komputasi terkini (misal: branch Git, dirty status, dynamic dependency version) yang tidak mungkin ditulis statis.
   - C. Mengurangi token cost menjadi 0.
   - D. Menjalankan Claude Code dalam sandbox tanpa hak akses OS.
   *Jawaban:* **B** | *Rasional:* Dynamic hooks menghasilkan metadata ephemeral secara runtime sebelum prompt dievaluasi oleh LLM, menjamin konteks selalu sinkron dengan state mesin.

9. Manakah konfigurasi `.claudeignore` berikut yang secara tepat mengabaikan semua file credentials namun tetap meloloskan file template contoh?
   - A. `*.env`
   - B. `.env*` dan `!*.env.example`
   - C. `secrets/*` dan `env`
   - D. `ignore .env`
   *Jawaban:* **B** | *Rasional:* Menggunakan wildcard globbing `.env*` untuk memblokir semua varian, diikuti negation pattern `!*.env.example` untuk mempertahankan template dokumentasi.

10. Bagaimana Model Context Protocol (MCP) Memory Server memecahkan problem token retention pada monorepo jutaan baris kode?
    - A. Dengan mengompresi kode menjadi format binary zip dan memasukkannya ke system prompt.
    - B. Menyimpan state dan entitas relasi kode di database eksternal (misal: vector/graph store), memungkinkan Claude mengambil konteks secara granular (*on-demand retrieval*) via tool calls alih-alih me-load seluruh file ke context window.
    - C. Menghapus kebutuhan LLM untuk membaca kode lokal.
    - D. Menggandakan batas kapasitas token LLM menjadi tak terbatas.
    *Jawaban:* **B** | *Rasional:* MCP mengeksternalisasi memori jangka panjang ke server backend mandiri; model hanya meminta context spesifik melalui protokol JSON-RPC yang hemat token.

---

#### Bagian 3: Evaluasi Kasus Produksi Riil (3 Kasus)

11. **Skenario Kasus A:**
    Pada integrasi CI/CD, pipeline menjalankan Claude Code secara otonom untuk mereview PR dan memperbaiki security patch. Namun pada prosesnya, eksekusi pipeline sering mengalami timeout 60 menit dan tagihan token melonjak drastis. Setelah diinspeksi, Claude Code membaca direktori `.git/` yang berukuran 4 GB. Mengapa Claude Code membaca direktori tersebut dan bagaimana solusinya secara permanen di tingkat repositori?
    *Jawaban & Analisis Solusi:*
    Claude Code menggunakan file traversal tools (seperti `GlobTool` atau `GrepTool`). Jika direktori `.git/` tidak secara eksplisit diabaikan dalam `.claudeignore`, engine dapat memperlakukan commit objects dan packfiles sebagai target teks saat melakukan pencarian menyeluruh. Solusi permanen: Tambahkan entri `.git/` dan `.git/**` pada `.claudeignore` di root workspace, serta pastikan flag context traversal mengabaikan hidden directory secara default pada level runner CLI.

12. **Skenario Kasus B:**
    Sebuah tim engineer mendapati bahwa Claude Code terus-menerus mengubah dependensi pada `package.json` menggunakan format sintaksis npm lama alih-alih pnpm catalog format yang digunakan oleh arsitektur monorepo mereka. File root `CLAUDE.md` sudah memuat aturan `Use pnpm exclusively`. Mengapa aturan ini diabaikan oleh agen saat bekerja di direktori `apps/dashboard/`, dan bagaimana arsitektur file yang benar untuk mengatasinya?
    *Jawaban & Analisis Solusi:*
    Hal ini terjadi karena kemungkinan terdapat file `apps/dashboard/CLAUDE.md` lokal yang tidak mendefinisikan package manager, atau tidak mewarisi aturan root secara eksplisit, atau prompt lokal developer membingungkan attention model karena tidak adanya semantic scope header. Solusi: Pada `apps/dashboard/CLAUDE.md`, tambahkan metadata pewarisan eksplisit:
    ```markdown
    [PARENT-POLICY: //CLAUDE.md]
    ## Package Governance
    Strict Enforcement: Inherit parent pnpm catalog. Do not invoke npm/yarn.
    ```
    Dan di level root `CLAUDE.md`, tandai aturan package management dengan token `[IMMUTABLE]`.

13. **Skenario Kasus C:**
    Saat mengimplementasikan lifecycle script `.claude/hooks/pre-prompt.sh`, developer menyertakan perintah `npm audit` untuk memastikan keamanan dependencies. Akibatnya, setiap interaksi sederhana dengan Claude Code memakan waktu tunggu tambahan 20 detik sebelum Claude mulai merespon. Evaluasi kelemahan arsitektur ini dan berikan alternatif perbaikan yang mempertahankan observabilitas keamanan tanpa mengorbankan TTFT latensi!
    *Jawaban & Analisis Solusi:*
    Kelemahan arsitektur: Menempatkan synchronous long-running network I/O calls (`npm audit`) ke dalam critical path pre-prompt lifecycle hook. Hook dieksekusi secara blocking pada setiap turn interaksi. Solusi: Pindahkan proses scanning audit ke background worker atau asynchronous scheduled job yang menuliskan ringkasan status ke file cache lokal statis (misal: `.claude/cache/audit-summary.json`). Skrip `pre-prompt.sh` kemudian hanya membaca file cache lokal ini menggunakan operasi `cat` instan (<5ms):
    ```bash
    # Asynchronous decoupled approach
    if [ -f .claude/cache/audit-summary.json ]; then
      cat .claude/cache/audit-summary.json
    fi
    ```

---

### 16. Summary

* **Arsitektur Konfigurasi Deterministik:** Pengendalian memori Claude Code skala enterprise dibangun di atas tiga pilar utama: tata kelola direktif bertingkat (`CLAUDE.md`), isolasi context security (`.claudeignore`), dan injeksi runtime dinamis (`hooks`).
* **Hirarki Konteks Berjenjang (Hierarchical Context Ingestion):** Konfigurasi global (`~/.claude/CLAUDE.md`) menetapkan standar developer personal; root konfigurasi (`/CLAUDE.md`) memaksakan corporate governance dan invariansi arsitektur monorepo; scoped konfigurasi (`/apps/.../CLAUDE.md`) mengisolasi domain logic masing-masing microservice.
* **Token Budget Management:** Context window adalah sumber daya komputasi yang mahal dan terbatas. Membatasi ukuran file konfigurasi, memangkas history lama melalui strategi *compaction*, dan mengabaikan artefak kompilasi adalah imperatif mutlak untuk menekan latensi TTFT dan degradasi akurasi (*attention drift*).
* **Integrasi Memori Eksternal via MCP:** Untuk basis data skala masif (seperti ribuan skema API atau proto definitions), memori operasional harus dieksternalisasi ke Model Context Protocol (MCP) Memory Server berbasis pencarian semantik terindeks, memisahkan knowledge storage dari system prompt payload.