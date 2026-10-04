# Bab 10: Enterprise Capstone Project
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (claude-code)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Internal Claude Code**: Memahami mekanisme eksekusi agen otonom, *tool-use loop*, pengelolaan state pohon konteks (*context tree*), serta integrasi *Model Context Protocol* (MCP).
2. **Merancang Pipeline Produksi Headless/Automated**: Mengintegrasikan Claude Code ke dalam ekosistem CI/CD enterprise untuk operasi refactoring otomatis, analisis kerentanan (CVE remediation), dan migrasi arsitektur berskala ribuan repositori.
3. **Mengimplementasikan Guardrails dan Sandboxing Ketat**: Mengamankan eksekusi Claude Code menggunakan *ephemeral container isolation*, kontrol hak akses berbasis prinsip *least privilege*, serta validasi deterministik berbasis AST (*Abstract Syntax Tree*).
4. **Mengelola Biaya, Token, dan Observabilitas**: Mengonfigurasi telemetri terdistribusi (OpenTelemetry), rate-limiting adaptif, caching semantik, dan audit trail operasional untuk penggunaan model Claude 3.5 Sonnet / Opus di skala enterprise.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Claude Code Fundamentals**: Pemahaman dasar CLI `claude`, autentikasi API Anthropic, dan konfigurasi berkas `.claudeignore`.
- **Software Engineering & Tooling**: Pemahaman mendalam mengenai Git plumbing (`git rev-parse`, `git diff`, `git apply`), Containerization (Docker, Rootless Podman), dan POSIX Shell scripting.
- **Protocol & Interfaces**: Pemahaman mendalam mengenai *Model Context Protocol* (MCP) berbasis JSON-RPC via stdio/SSE.
- **Language Runtimes**: Node.js v20+ LTS runtime, Python 3.11+, dan pemahaman parsing AST (misalnya via `tree-sitter` atau Babel).

---

### 3. Concept & Internal Architecture (Mendalam)

Claude Code (`@anthropic-ai/claude-code`) bukan sekadar *wrapper* CLI di atas API LLM standar. Claude Code adalah sebuah *Agentic Coding Runtime Engine* yang dirancang untuk beroperasi langsung di atas *working tree* proyek perangkat lunak.

```
+-----------------------------------------------------------------------------------+
|                            Claude Code Runtime Engine                             |
+-----------------------------------------------------------------------------------+
|  [ CLI / Headless Controller ]                                                    |
|           │                                                                       |
|           ▼                                                                       |
|  [ Agentic Core Loop (ReAct / Task Planner) ] ◄───► [ Context Window Manager ]    |
|           │                                         - Dynamic Pruning             |
|           │                                         - Token Budget Estimator      |
|           ▼                                         - System Prompt Assembly      |
|  [ Tool Execution Dispatcher ]                                                    |
|     ├── Local File Tools (View, Edit, Replace, Glob, Grep)                        |
|     ├── Execution Tools (Bash Runner, Subprocess Sandbox)                         |
|     └── MCP Protocol Host (Custom DB, Enterprise APIs, Issue Trackers)            |
|           │                                                                       |
|           ▼                                                                       |
|  [ Verification & Safety Layer ]                                                  |
|     - Dangerous Command Interceptor (rm -rf, git push --force)                    |
|     - Syntax & Type Verification Engine                                           |
|     - Diff Engine (AST/Line-based patch generation)                               |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kunci Arsitektur Internal:

1. **Context Window Manager & Token Budgeting**:
   - Claude Code secara dinamis merakit prompt dengan menyuntikkan: *System Instructions*, riwayat percakapan terkini, status `git status`, dan representasi direktori yang dipangkas (*pruned tree*).
   - Menggunakan mekanisme *dynamic sliding window* dan pemangkasan riwayat perintah CLI jika penggunaan token mendekati ambang batas context window (200k token), memprioritaskan pemeliharaan instruksi sistem dan output tes terbaru.

2. **The ReAct / Tool-Use Lifecycle**:
   - Model mengevaluasi instruksi pengguna dan menghasilkan *tool call* (misal: `GrepTool`, `FileReadTool`).
   - Claude Code mengeksekusi *tool* tersebut secara lokal, menangkap `stdout`/`stderr`, memvalidasi panjang *output*, lalu mengirimkannya kembali ke model sebagai *ToolResult*.
   - Loop ini berulang secara otonom hingga model merasa tugas telah tuntas dan memanggil aksi terminasi atau memberikan respons final.

3. **Subprocess Isolation & Security Policy**:
   - Claude Code mengeksekusi perintah shell menggunakan abstraksi subprocess yang diawasi. Di lingkungan enterprise, *execution engine* ini harus di-*jail* di dalam cgroup terisolasi untuk mencegah eksfiltrasi variabel lingkungan runtime atau modifikasi file di luar *repository boundary*.

4. **MCP (Model Context Protocol) Integration**:
   - Bertindak sebagai MCP *client* yang membuka saluran `stdio` terhadap MCP *server*. Hal ini memungkinkan Claude Code mengakses konteks eksternal (misal: skema database internal, arsitektur Confluence, log Datadog) tanpa hardcoding skrip langsung ke dalam codebase target.

---

### 4. Why & What

| Dimensi | Chat Web / Copilot Standar | Claude Code CLI Standar | Claude Code Enterprise Automated Architecture |
| :--- | :--- | :--- | :--- |
| **Operasional** | Interaktif manusia tunggal via GUI | Interaktif pengembang via Terminal | Headless, Non-interaktif, Terorkestrasi di CI/CD |
| **Cakupan Konteks** | Potongan kode / file aktif saja | Seluruh working directory lokal | Monorepo + Graph Dependensi + Konteks MCP Eksternal |
| **Aksi & Eksekusi**| Read-only / Suggestion saja | Menulis file & eksekusi shell lokal | Menulis, Memvalidasi (Test/Lint), Self-healing, PR Creation |
| **Keamanan** | Konteks dikirim tanpa filter terpusat | Bergantung izin manual prompt CLI | Sandboxed ephemeral container, OIDC token, Guardrail AST |
| **Skalabilitas** | 1 developer = 1 tugas | 1 developer = 1 terminal session | Batch parallel execution di 500+ repositori sekaligus |

**Mengapa ini penting bagi Enterprise?**
Pendekatan pengkodean berbasis AI tradisional mengalami kendala fragmentasi: developer menghabiskan waktu menyalin kode dari antarmuka web atau menerima saran sebaris (*inline completion*) yang sering kali memecah dependensi modul lain. Arsitektur Enterprise Claude Code mengubah paradigma ini menjadi **Autonomous Software Maintenance Pipelines**, di mana agen AI bertindak seperti Software Engineer junior-menengah yang mengeksekusi tugas terisolasi, menguji kodenya sendiri, memperbaiki error kompilasi, dan membuka Pull Request secara mandiri dengan transparansi audit penuh.

---

### 5. How (Workflow Detail)

Alur kerja integrasi tingkat produksi mengikuti siklus *Orchestrated Headless Agentic Loop*:

```
[Trigger: Event CI / Cron / Webhook]
                 │
                 ▼
[Provisioning: Ephemeral Container with Rootless Sandbox]
                 │
                 ▼
[Context Assembly & Sanitization (.claudeignore, Token Boundary)]
                 │
                 ▼
[Headless Claude Code Execution Engine] ◄───────────────┐
  │                                                     │
  ├── 1. Read Task & Inspect Files                      │
  ├── 2. Generate Edits (Patches)                       │
  ├── 3. Execute Linter / Test Runner (Feedback Loop)   │ (Self-Correction Loop:
  └── 4. Analyze Failures (if any) ─────────────────────┘  Max 3-5 Iterations)
                 │
           (Tests Pass)
                 │
                 ▼
[Static Security & AST Deterministic Verifier]
                 │
                 ▼
[Git Commit, Signed Tree, Push Branch & Open Pull Request]
                 │
                 ▼
[Telemetry Export: OpenTelemetry Metrics, Audit Log & Cost Attribution]
```

#### Tahapan Alur Kerja:
1. **Provisioning**: Worker CI/CD (GitHub Actions / GitLab Runner) memicu container instan (Docker-in-Docker atau gVisor sandbox). Environment variable dibersihkan dari token produksi sensitif.
2. **Context Assembly**: Berkas repositori disiapkan. File `.claudeignore` diverifikasi untuk mencegah pembacaan file `.env`, certs, atau log internal.
3. **Execution**: CLI dijalankan menggunakan mode non-interaktif (`--print` atau scripting wrapper) dengan *system prompt override* yang mewajibkan model untuk memvalidasi perubahan menggunakan test runner lokal.
4. **Self-Correction Loop**: Claude Code mengeksekusi suite unit test (misal `npm test` atau `pytest`). Jika terjadi error, ia membaca stack trace dari `stderr`, memodifikasi ulang kodenya, dan menguji kembali hingga berhasil.
5. **Deterministic Verifier**: Mesin eksternal (di luar agen) memverifikasi bahwa perubahan AST tidak menghapus kontrol keamanan atau melanggar aturan arsitektur SonarQube/Linter.
6. **Telemetry & Pull Request**: Token usage diekstrak dan dikirim ke sistem billing enterprise; branch di-*push* dengan metadata audit lengkap.

---

### 6. Analogy & Diagram ASCII

#### Analogi:
Bayangkan Claude Code Enterprise sebagai **Mekanik Khusus di Ruang Bersih Pabrik**:
- **Chat Copilot** adalah buku manual yang Anda baca sendiri sambil memperbaiki mobil.
- **Claude Code CLI Lokal** adalah mekanik yang berdiri di sebelah Anda; Anda harus terus mengawasinya dan memberikannya kunci inggris saat ia meminta izin.
- **Claude Code Enterprise Architecture** adalah memasukkan mobil ke dalam stasiun perbaikan robotik otomatis: pintu ditutup rapat (Sandboxed Container), robot membaca tiket kerja, mengambil alat yang telah disetujui (MCP), membongkar mesin, mengganti suku cadang, menyalakan mesin untuk menguji emisi dan suara (Test Runner), dan jika ada suara ketukan aneh, ia memperbaikinya sendiri sebelum mobil dikeluarkan dari stasiun dengan laporan uji lengkap terlampir.

#### Diagram Interaksi Runtime Detail:

```
+--------------------------------------------------------------------------------+
|                             CONTAINER RUNTIME                                  |
|                                                                                |
|  +---------------------+        UNIX Socket/IPC        +--------------------+  |
|  | Enterprise Runner   | ────────────────────────────► | Claude Code Engine |  |
|  | (Bash / Node Host)  | ◄──────────────────────────── | (CLI headless)     |  |
|  +----------┬----------+                               +---------┬----------+  |
|             │                                                    │             |
|             │ (Spawns)                                           │ (Tool Call) |
|             ▼                                                    ▼             |
|  +---------------------+                               +--------------------+  |
|  | Mock / Sandboxed FS |                               | Tool Execution     |  |
|  | Worktree Workspace  | ◄──────────────────────────── | Subprocess Manager |  |
|  +---------------------+      Applies Diff/Patch       +---------┬----------+  |
|                                                                  │             |
|                                                      Executes    ▼             |
|                                                        +--------------------+  |
|                                                        | Local Shell/Linter |  |
|                                                        | (pytest / npm test)|  |
|                                                        +--------------------+  |
+----------------------------------------------------------------──┼-------------+
                                                                   │ (stdio)
                                                                   ▼
                                                         +--------------------+
                                                         | Custom MCP Server  |
                                                         | (Secure Schema API)|
                                                         +--------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Headless Execution Wrapper
Contoh dasar menjalankan Claude Code via subproses non-interaktif dengan pembatasan anggaran token:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Skrip runner Claude Code sederhana untuk otomatisasi tugas tunggal
PROMPT="Refactor semua fungsi pada src/utils.ts agar menggunakan ES2022 syntax dan tambahkan JSDoc lengkap."

export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"

# Menjalankan claude code secara non-interaktif menggunakan flag print/headless
echo "==> Memulai Claude Code execution..."
claude -p "$PROMPT" \
  --dangerously-skip-permissions \
  --no-auto-updater

echo "==> Mengecek status git diff..."
git diff --stat
```

#### Practical Example: Production-Grade Enterprise Refactoring Pipeline
Arsitektur runner Node.js enterprise yang membungkus Claude Code CLI, mengeksekusi validasi AST pasca-eksekusi, membatasi waktu eksekusi (*timeout*), mengekstraksi metrik, dan menolak modifikasi berbahaya.

```typescript
// file: scripts/enterprise-claude-runner.ts
import { exec, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';

const execAsync = promisify(exec);

interface PipelineConfig {
  taskPrompt: string;
  allowedDirectories: string[];
  maxExecutionTimeMs: number;
  testCommand: string;
}

interface RunMetrics {
  durationMs: number;
  filesChanged: number;
  testPassed: boolean;
  rawDiff: string;
}

export class EnterpriseClaudeAgent {
  private config: PipelineConfig;

  constructor(config: PipelineConfig) {
    this.config = config;
  }

  private async enforceSecurityBoundary(): Promise<void> {
    // 1. Verifikasi eksistensi .claudeignore
    const ignorePath = path.resolve(process.cwd(), '.claudeignore');
    try {
      await fs.access(ignorePath);
    } catch {
      throw new Error("Security Violation: Berkas .claudeignore wajib ada di root repositori.");
    }

    // 2. Pastikan working directory bersih
    const { stdout: gitStatus } = await execAsync('git status --porcelain');
    if (gitStatus.trim().length > 0) {
      throw new Error("Pre-condition Failed: Git working tree harus bersih sebelum agen berjalan.");
    }
  }

  public async execute(): Promise<RunMetrics> {
    await this.enforceSecurityBoundary();
    const startTime = Date.now();

    console.log(`[AGENT] Memulai eksekusi Claude Code untuk task: "${this.config.taskPrompt}"`);

    // Injeksi instruksi sistem yang kaku untuk mode autonomous
    const augmentedPrompt = `
SYSTEM DIRECTIVE: Anda berjalan dalam Enterprise Autonomous Sandbox.
Tugas Anda: ${this.config.taskPrompt}
Batas Operasi: Anda HANYA boleh mengubah file di dalam: ${this.config.allowedDirectories.join(', ')}.
Wajib: Jalankan perintah '${this.config.testCommand}' menggunakan tool Bash untuk verifikasi sebelum menyatakan selesai.
Dilarang keras memodifikasi file konfigurasi CI/CD (.github, .gitlab-ci.yml) atau dependencies (package.json).
`;

    // Eksekusi Claude Code CLI dengan subprocess terisolasi
    const claudeProcess = spawn('claude', [
      '-p', augmentedPrompt,
      '--dangerously-skip-permissions' // Diizinkan HANYA karena berada di sandboxed ephemeral container
    ], {
      env: {
        ...process.env,
        CI: 'true',
        NODE_ENV: 'test'
      },
      timeout: this.config.maxExecutionTimeMs
    });

    let stdoutBuffer = '';
    let stderrBuffer = '';

    claudeProcess.stdout.on('data', (chunk) => {
      stdoutBuffer += chunk.toString();
      process.stdout.write(`[CLAUDE STDOUT] ${chunk.toString()}`);
    });

    claudeProcess.stderr.on('data', (chunk) => {
      stderrBuffer += chunk.toString();
      process.stderr.write(`[CLAUDE STDERR] ${chunk.toString()}`);
    });

    const exitCode = await new Promise<number>((resolve, reject) => {
      claudeProcess.on('close', resolve);
      claudeProcess.on('error', reject);
    });

    if (exitCode !== 0) {
      throw new Error(`Claude Code gagal dieksekusi dengan exit code: ${exitCode}\nStderr: ${stderrBuffer}`);
    }

    // Verifikasi Keamanan Pasca-Eksekusi: Path Violation Check
    const { stdout: changedFilesRaw } = await execAsync('git diff --name-only');
    const changedFiles = changedFilesRaw.split('\n').filter(Boolean);

    for (const file of changedFiles) {
      const isAllowed = this.config.allowedDirectories.some(dir => file.startsWith(dir));
      if (!isAllowed) {
        // Rollback otomatis
        await execAsync('git reset --hard HEAD');
        throw new Error(`Security Violation: Agen mengubah file di luar area yang diizinkan: ${file}. Seluruh perubahan dibatalkan.`);
      }
    }

    // Verifikasi Fungsional: Menjalankan Test Suite Eksternal secara independen
    let testPassed = false;
    try {
      console.log(`[VERIFIER] Menjalankan test suite independen: ${this.config.testCommand}`);
      await execAsync(this.config.testCommand);
      testPassed = true;
    } catch (testError: any) {
      console.error(`[VERIFIER] Test suite gagal pasca modifikasi: ${testError.message}`);
      testPassed = false;
    }

    const { stdout: rawDiff } = await execAsync('git diff');
    const durationMs = Date.now() - startTime;

    return {
      durationMs,
      filesChanged: changedFiles.length,
      testPassed,
      rawDiff
    };
  }
}

// Eksekusi Contoh
(async () => {
  const runner = new EnterpriseClaudeAgent({
    taskPrompt: "Migrasikan semua interface legacy di src/models/ ke generic TypeScript types baru.",
    allowedDirectories: ["src/models/"],
    maxExecutionTimeMs: 300000, // 5 menit
    testCommand: "npm run test:models"
  });

  try {
    const result = await runner.execute();
    console.log("[PIPELINE SUCCEEDED]", JSON.stringify({
      durationMs: result.durationMs,
      filesChanged: result.filesChanged,
      testPassed: result.testPassed
    }, null, 2));

    if (!result.testPassed) {
      process.exit(1);
    }
  } catch (err: any) {
    console.error("[PIPELINE FAILED]", err.message);
    process.exit(1);
  }
})();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Remediasi Kerentanan Log4j & Modernisasi Spring Boot di Global FinTech (Bank Mantap Digital)
- **Kondisi Awal**: 
  - Repositori: 1.200 microservices Java.
  - Masalah: Kerentanan zero-day dependensi usang serta target migrasi dari Java 11 / Spring Boot 2.4 ke Java 17 / Spring Boot 3.2.
  - Estimasi Manual: 1.200 repo × 3 hari engineer = 3.600 man-days (biaya ~$1.8M USD dan waktu rilis 9 bulan).
- **Arsitektur Solusi Menggunakan Claude Code**:
  1. **Worker Pool Orchestration**: Dibuat klaster Kubernetes yang menjalankan 30 pods paralel. Setiap pod merupakan ephemeral container berisikan Claude Code CLI + OpenJDK 17 + Maven.
  2. **MCP Enterprise Registry Server**: Dibuat MCP server internal yang mengekspos aturan mapping library internal bank, corporate proxy settings, dan panduan deprecation API perusahaan.
  3. **Self-Healing Loop**:
     - Claude Code membaca `pom.xml`.
     - Claude Code memperbarui dependensi, mengubah paket `javax.*` menjadi `jakarta.*`.
     - Claude Code menjalankan `mvn clean test-compile` dan `mvn test`.
     - Apabila test gagal karena breaking change pada method signature, Claude Code mengurai stack trace, membaca class caller, merefaktor method signature, lalu menjalankan test kembali.
  4. **Strict Guardrails**: Jika Claude Code mencoba menyentuh folder deployment (`k8s/`, `helm/`, `.github/`), eksekutor langsung men-terminate pod dan mengibarkan flag anomali.
- **Hasil**:
  - 1.050 repositori (87,5%) berhasil dimigrasikan secara penuh tanpa intervensi manusia dan lulus 100% integrasi test suite.
  - 150 repositori membutuhkan intervensi manual developer karena ketiadaan unit test yang memadai (*low test coverage*).
  - Durasi penyelesaian terpangkas dari 9 bulan menjadi **6 hari kerja**.
  - Total pengeluaran token API Anthropic: ~$4.800 USD (dibandingkan estimasi biaya developer manual $1.8M USD).

---

### 9. Trade-offs

| Aspek | Pilihan A: Mode Otonom Penuh (Full Headless Auto-PR) | Pilihan B: Human-in-the-Loop (Interactive CLI Tool) | Implikasi Teknis |
| :--- | :--- | :--- | :--- |
| **Throughput & Speed** | Sangat Tinggi (Bisa memproses ratusan repo via pipeline terdistribusi). | Rendah hingga Sedang (Dibatasi oleh kecepatan review dan interaksi developer). | Full Headless membutuhkan resource orchestrator (K8s/Docker runner pools). |
| **Security Risk** | Tinggi (Risiko eksfiltrasi data atau injeksi kode berbahaya jika sandbox jebol). | Sangat Rendah (Developer melihat setiap diff dan menyetujui setiap perintah CLI secara manual). | Full Headless mutlak memerlukan read-only host mounts, rootless isolation, dan git commit signing. |
| **Token Cost Efficiency**| Berpotensi Rendah / Boros (Model dapat terjebak dalam *retry loop* perbaikan bug). | Tinggi (Developer dapat memotong percakapan segera jika arah refactoring salah). | Wajib dipasang limit maksimum *turn/iteration* (misal max 5 retries) dan *cost circuit breaker*. |
| **Code Consistency** | Sangat Tinggi terhadap standarisasi linter yang telah terpasang. | Bervariasi (Tergantung preferensi developer lokal). | Full Headless memaksa repositori memiliki test suite dan static analysis yang deterministik. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: *Infinite Repair Loop* (Token Exhaustion)
- **Gejala**: Claude Code terus memodifikasi file, menjalankan testing, gagal, memodifikasi file lain, dan berulang hingga kuota token API habis atau *timeout* container tercapai.
- **Root Cause**: Unit test memiliki assertion yang rapuh (*flaky test*) atau dependensi eksternal (mocking database) tidak tersedia di sandbox.
- **Solusi**: Batasi jumlah interaksi maksimal dengan memonitor cycle execution pada orchestration script. Injeksi environment variable `MOCK_EXTERNAL_SERVICES=true` dan tambahkan timeout timeout tegas pada execution runner.

#### 2. Masalah: `.claudeignore` Bocor atau Tidak Dihormati
- **Gejala**: Token pemanggilan API melonjak tajam karena Claude Code membaca direktori `node_modules`, `build/`, `.git/`, atau data fixtures besar.
- **Root Cause**: `.claudeignore` tidak diletakkan di root eksekusi CLI atau direktori diabaikan oleh `.gitignore` namun diakses eksplisit oleh Claude Code.
- **Solusi**: Selalu lakukan validasi eksistensi dan integritas file `.claudeignore` sebelum CLI dipanggil. Contoh template wajib:
  ```text
  # .claudeignore WAJIB ENTERPRISE
  .git/
  node_modules/
  dist/
  build/
  target/
  *.log
  .env*
  certs/
  secrets/
  coverage/
  ```

#### 3. Masalah: MCP Server Zombie Process & Deadlock
- **Gejala**: Eksekusi Claude Code menggantung (*hang*) secara tak terbatas saat inisialisasi tool eksternal.
- **Root Cause**: MCP Server berbasis stdio tidak menangani sinyal `SIGTERM` / `SIGINT` atau menulis log non-JSON ke saluran `stdout` yang merusak parsing JSON-RPC oleh Claude Code.
- **Solusi**: Pastikan seluruh log MCP server dialihkan ke `stderr` (`console.error` alih-alih `console.log`), dan tambahkan wrapper timeout pada koneksi stdio MCP host.

---

### 11. Best Practices (Production Checklist)

#### Sandbox & Isolation:
- [ ] Eksekusi Claude Code di dalam rootless container (misal Podman atau Docker Rootless).
- [ ] Mount workspace code secara spesifik; mount file sistem sistem operasi sebagai Read-Only (`--read-only`).
- [ ] Matikan akses jaringan publik jika tugasnya murni refactoring internal (hanya izinkan akses ke domain API Anthropic dan package repository internal/Artifactory).

#### Token & Cost Governance:
- [ ] Terapkan workspace spending limit pada Anthropic Organization dashboard.
- [ ] Implementasikan caching lokal untuk AST dan static dependency graph.
- [ ] Atur `--dangerously-skip-permissions` HANYA jika dipadukan dengan isolasi container OS yang ketat. Dilarang keras menggunakan flag ini pada mesin lokal/laptop developer tanpa supervisi.

#### Validation & Quality Gates:
- [ ] Linter (ESLint, Prettier, Checkstyle) dijalankan oleh runner eksternal pasca agen selesai bekerja.
- [ ] Test coverage tidak boleh turun setelah patch diaplikasikan (`coverage diff verification`).
- [ ] Pull Request yang dibuat secara otomatis wajib dilabeli `bot:claude-code` dan membutuhkan persetujuan minimal satu Senior Staff Engineer.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah automated headless runner berstandar enterprise yang mengisolasi eksekusi Claude Code dan memvalidasi hasilnya secara deterministik.

Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

#### Struktur Direktori:
```text
hands-on/m02/
├── .claudeignore
├── Dockerfile.sandbox
├── package.json
├── run-agent.sh
├── src/
│   ├── calculator.ts
│   └── calculator.test.ts
└── tsconfig.json
```

#### Langkah 1: Inisialisasi Workspace & Target Code
Masuk ke direktori `hands-on/m02/` dan buat target kode TypeScript legacy yang memiliki bug performa:

```typescript
// hands-on/m02/src/calculator.ts
export class FinancialCalculator {
  // Legacy method: Menghitung bunga majemuk dengan iterasi lambat
  public calculateCompoundInterest(principal: number, rate: number, years: number): number {
    let total = principal;
    for (let i = 0; i < years; i++) {
      // Simpan trace
      for (let j = 0; j < 12; j++) {
        total = total + (total * (rate / 12));
      }
    }
    return Math.round(total * 100) / 100;
  }
}
```

```typescript
// hands-on/m02/src/calculator.test.ts
import { FinancialCalculator } from './calculator';

describe('FinancialCalculator', () => {
  it('harus menghitung bunga majemuk bulanan dengan benar', () => {
    const calc = new FinancialCalculator();
    // 1000 modal, bunga 5% (0.05), selama 10 tahun
    const result = calc.calculateCompoundInterest(1000, 0.05, 10);
    expect(result).toBe(1647.01);
  });
});
```

#### Langkah 2: Konfigurasi Sandbox Container
Buat Dockerfile yang membatasi hak istimewa pengguna dan mematikan perutean tak penting:

```dockerfile
# hands-on/m02/Dockerfile.sandbox
FROM node:20-alpine

# Install bash, git, dan tools dependensi
RUN apk add --no-cache bash git

# Install Claude Code secara global
RUN npm install -g @anthropic-ai/claude-code

# Buat non-root user 'agent'
RUN adduser -D -u 10001 agent

WORKDIR /app
RUN chown -R agent:agent /app

USER agent

# Default entrypoint
CMD ["bash"]
```

#### Langkah 3: Membuat Runner Automation Script
Buat skrip `run-agent.sh`:

```bash
#!/usr/bin/env bash
# hands-on/m02/run-agent.sh
set -euo pipefail

echo "========================================================="
echo "   ENTERPRISE CLAUDE-CODE HEADLESS ORCHESTRATOR         "
echo "========================================================="

# 1. Pastikan ANTHROPIC_API_KEY terdeteksi
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: Environment variable ANTHROPIC_API_KEY belum diset."
    exit 1
fi

# 2. Build sandbox image jika belum ada
echo "[1/4] Membangun image Docker Sandbox..."
docker build -t claude-code-sandbox -f Dockerfile.sandbox .

# 3. Jalankan container dengan restriksi keamanan
echo "[2/4] Menjalankan Claude Code dalam sandbox terisolasi..."

PROMPT="Optimalkan algoritma calculateCompoundInterest di src/calculator.ts menggunakan rumus matematika langsung A = P(1 + r/n)^(nt) tanpa loop bersarang. Pastikan hasil pembulatan sama dan jalankan 'npm test' untuk memverifikasi."

docker run --rm \
  --name claude-sandbox-execution \
  --network host \
  --memory="2g" \
  --cpus="2" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -v "$(pwd)":/app \
  -w /app \
  claude-code-sandbox \
  claude -p "$PROMPT" --dangerously-skip-permissions

# 4. Verifikasi Deterministik Host-Side
echo "[3/4] Melakukan audit keamanan lokal..."
if git status --porcelain | grep -q "Dockerfile.sandbox"; then
    echo "SECURITY ALERT: Claude Code mencoba mengubah Dockerfile!"
    git checkout -- Dockerfile.sandbox
    exit 1
fi

echo "[4/4] Menjalankan smoke test akhir pasca eksekusi..."
npm test

echo "========================================================="
echo "SUCCESS: Kode berhasil dioptimalkan dan divalidasi!"
echo "========================================================="
```

Pastikan skrip dapat dieksekusi: `chmod +x hands-on/m02/run-agent.sh`.

---

### 13. Exercise

#### Level 1 - Easy:
Tambahkan berkas konfigurasi `.claudeignore` di `hands-on/m02/` yang mengabaikan direktori `.git`, file biner, file laporan testing (`coverage/`), dan variabel lingkungan. Uji apakah Claude Code mematuhi aturan ini ketika diminta: *"Tampilkan isi semua file di root direktori."*

#### Level 2 - Medium:
Modifikasi `scripts/enterprise-claude-runner.ts` agar menangkap metrik penggunaan token dari output terminal Claude Code, lalu simpan metrik tersebut (eksekusi timestamp, duration, error rate) ke dalam berkas `audit-metrics.json`.

#### Level 3 - Hard:
Buat sebuah custom MCP Server sederhana berbasis stdio menggunakan Node.js/TypeScript (`@modelcontextprotocol/sdk`). MCP Server ini harus mengekspos satu buah tool: `get_coding_standards(language: string)`. Konfigurasikan Claude Code agar menggunakan MCP Server ini, lalu jalankan tugas headless di mana Claude Code secara otomatis merefaktor kode sesuai aturan coding standard perusahaan yang dikembalikan oleh MCP Server tersebut.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Architect di perusahaan e-Commerce berskala Tier-1. Perusahaan memutuskan untuk bermigrasi dari REST API monolitik ke arsitektur Event-Driven (Apache Kafka). Terdapat 200 endpoint controller yang harus dikonversi menjadi Kafka Event Producers.

**Tugas Tantangan Arsitektural**:
Rancang dan implementasikan blue-print orkestrator automasi berbasis Claude Code yang memenuhi kriteria ketat berikut:
1. **Concurrency Control**: Mampu menjalankan hingga 10 agen Claude Code secara paralel di Node Kubernetes yang berbeda tanpa konflik Git concurrency.
2. **Circuit Breaker Biaya Token**: Jika biaya API kumulatif untuk satu repositori melebihi $15 USD atau durasi perbaikan mencapai lebih dari 15 iterasi lint/test failure, agen harus otomatis melakukan `git abort`, mengembalikan state ke branch awal, dan menandai tiket Jira terkait sebagai `MIGRATION_FAILED_NEEDS_MANUAL`.
3. **Double-Blind Verification**: Perubahan yang dihasilkan oleh Claude Code harus diuji oleh test-harness yang tidak terlihat oleh Claude Code selama proses *edit loop* (untuk mencegah model memodifikasi test case agar assertions selalu pass).
4. **Deliverable**: Serahkan diagram arsitektur teknis, Dockerfile production runner, serta skrip orkestrasi lengkap dengan sistem *automated rollback*.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions:
1. **Pertanyaan**: Apa fungsi utama flag `--dangerously-skip-permissions` pada CLI Claude Code?
   - *Jawaban*: Mengabaikan konfirmasi manual berbasis antarmuka terminal untuk setiap pemanggilan tool (seperti eksekusi bash atau penulisan file), memungkinkan CLI beroperasi sepenuhnya non-interaktif dalam alur kerja automasi headless.
2. **Pertanyaan**: Mengapa flag `--dangerously-skip-permissions` sangat berbahaya jika dijalankan di laptop developer tanpa kontainerisasi?
   - *Jawaban*: Karena Claude Code memiliki kapabilitas menjalankan perintah shell arbitrary; jika model mengalami halusinasi atau prompt injection, ia dapat mengeksekusi perintah destruktif (misal `rm -rf /` atau eksfiltrasi SSH keys).
3. **Pertanyaan**: Apa perbedaan utama antara berkas `.gitignore` dan `.claudeignore`?
   - *Jawaban*: `.gitignore` menginstruksikan Git untuk tidak melacak perubahan file tertentu, sedangkan `.claudeignore` menginstruksikan Claude Code runtime untuk sama sekali tidak membaca atau menyertakan file tersebut ke dalam context window prompt.
4. **Pertanyaan**: Protokol standar apa yang digunakan Claude Code untuk berkomunikasi dengan tool atau sumber data eksternal?
   - *Jawaban*: *Model Context Protocol* (MCP) yang dioperasikan melalui protokol transportasi JSON-RPC via stdio atau SSE (Server-Sent Events).
5. **Pertanyaan**: Bagaimana Claude Code mengetahui apakah kode yang dimodifikasinya menyebabkan error sintaksis?
   - *Jawaban*: Melalui *tool-use loop* (ReAct cycle), di mana Claude Code mengeksekusi linter, compiler, atau test runner melalui tool Bash, menangkap error output dari `stderr`, dan menganalisisnya di iterasi berikutnya.

#### Intermediate Questions:
6. **Pertanyaan**: Bagaimana arsitektur Claude Code menangani potensi context window overflow ketika memproses repositori dengan jutaan baris kode?
   - *Jawaban*: Menggunakan *selective dynamic context loading*. Claude Code tidak memasukkan seluruh kode ke prompt, melainkan hanya pohon direktori parsial (*tree skeleton*), lalu membaca isi file spesifik secara lazy menggunakan tool `View`/`FileRead`, serta memanfaatkan pencarian berbasis `Grep` dan `Glob`.
7. **Pertanyaan**: Mengapa output logging dari kustom MCP Server harus selalu dialihkan ke `stderr` dan dilarang keras ditulis ke `stdout`?
   - *Jawaban*: Saluran `stdout` dipesan secara eksklusif untuk framed messages JSON-RPC antara MCP Host dan MCP Client. Menulis plain text ke `stdout` akan merusak parser JSON-RPC Claude Code dan memicu fatal crash.
8. **Pertanyaan**: Dalam implementasi CI/CD automated refactoring, mengapa validasi test pasca-eksekusi harus dilakukan secara independen di luar subprocess Claude Code?
   - *Jawaban*: Untuk mencegah manipulasi hasil uji (seperti model memodifikasi unit test agar assertions dibuat selalu return `true` demi menyelesaikan tugasnya). Runner eksternal menjamin verifikasi deterministik yang independen.
9. **Pertanyaan**: Apa implikasi penggunaan ephemeral container terhadap caching performa Claude Code?
   - *Jawaban*: Ephemeral container yang dihancurkan setiap akhir run akan menghilangkan cache lokal Claude Code (seperti token cache dan file hash indexing). Hal ini dapat diatasi dengan me-mount persistent volume cache khusus untuk cache direktori Claude Code.
10. **Pertanyaan**: Apa strategi mitigasi terbaik untuk mencegah Claude Code memodifikasi file konfigurasi infrastruktur CI/CD saat melakukan refactoring kode aplikasi?
    - *Jawaban*: Mengombinasikan proteksi *defense-in-depth*: mendaftarkan direktori `.github/`, `.gitlab-ci.yml`, `Dockerfile` ke dalam `.claudeignore`, membatasi path akses di system prompt, dan memberlakukan *path boundary check* pasca-eksekusi via `git diff --name-only`.

#### Production Scenario Questions:
11. **Skenario 1**: Agen Claude Code Anda yang berjalan di pipeline CI/CD sering mengalami kegagalan dengan error `Agent reached max iteration limit without completing task`. Saat dianalisa, agen terus berputar memperbaiki unit test yang sama. Langkah mitigasi arsitektur apa yang harus diambil?
    - *Solusi*: 
      1. Tambahkan analyzer pra-eksekusi untuk mendeteksi *flaky tests*.
      2. Berikan instruksi eksplisit di system prompt: jika tes gagal lebih dari 2 kali dengan stack trace yang identik, agen diwajibkan melakukan *revert* modifikasi file terakhir dan mencoba pendekatan algoritma alternatif alih-alih melakukan patching minor berulang.
      3. Pasang circuit breaker maksimal 3 kali retry untuk berkas test yang sama.
12. **Skenario 2**: Perusahaan Anda memproses repositori monorepo yang berisi kode komersial tertutup bernilai tinggi (*proprietary trading algorithms*). Tim Keamanan Informasi melarang kode tersebut dikirim ke API pihak ketiga tanpa audit ketat. Bagaimana Anda mendesain arsitektur Claude Code agar patuh regulasi ini?
    - *Solusi*:
      1. Konfigurasikan Claude Code untuk menggunakan Anthropic API via endpoint privat (misal AWS Bedrock atau GCP Vertex AI dengan Private Link) sehingga trafik data tidak melintasi jaringan internet publik.
      2. Pasang proxy filter data (DLP - Data Loss Prevention) lokal di antara runtime container dan endpoint API yang secara otomatis melakukan masking / redaksi terhadap nama algoritma atau koefisien numerik matematis sensitif sebelum payload JSON dikirim ke LLM.
13. **Skenario 3**: Sebuah batch job yang menjalankan 50 instance Claude Code secara paralel mendadak mengalami error masif `429 Too Many Requests (Rate Limit Exceeded)` dari penyedia LLM setelah berjalan selama 3 menit. Bagaimana arsitektur antrean dan *backoff* yang harus dibangun untuk menangani ini?
    - *Solusi*:
      1. Jangan biarkan runner worker memanggil API secara sporadis tanpa koordinasi. Pasang centralized Token Bucket Rate Limiter (misal menggunakan Redis) di depan runner cluster.
      2. Terapkan strategi *Jittered Exponential Backoff* pada level wrapper orchestrator.
      3. Atur *concurrency slot* berdasarkan kalkulasi konsumsi TPM (Tokens Per Minute) dan RPM (Requests Per Minute) yang dialokasikan tier akun Anthropic, sehingga pemanggilan dibatasi maksimal $N$ runner aktif pada satu window menit.

---

### 16. Summary

Implementasi Claude Code di tingkat enterprise mentransformasi alat bantu CLI interaktif individual menjadi **mesin otonom pemeliharaan perangkat lunak berskala masif**. Fondasi utama arsitektur produksi terletak pada:
1. **Isolasi Sandboxing yang Ketat**: Mengasumsikan eksekusi kode oleh model adalah *untrusted execution* yang wajib dikurung dalam rootless container dengan restriksi I/O dan jaringan.
2. **Kontrol Konteks & Sanitasi**: Penggunaan disiplin file `.claudeignore`, token budgeting, dan integrasi MCP Server untuk memasok konteks enterprise secara terstruktur.
3. **Deterministik Validation Loop**: Menolak hasil kerja agen AI semata-mata berdasarkan klaimnya sendiri; mengintegrasikan test runner independen, AST linting, dan path boundaries verification sebelum perubahan kode dapat diajukan sebagai Pull Request resmi.
4. **Governansi Skala Penuh**: Pemantauan metrik secara terdistribusi, kontrol rate-limiting terpusat, dan pembatasan biaya token via circuit breaker untuk menjamin efisiensi investasi AI.