# Bab 09: Otomasi Non-Interactive & CI/CD Pipelines
## Module 01: Headless Claude Code Execution, Sandboxing, dan Pipeline Integration

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mengonfigurasi dan Mengoperasikan Claude Code dalam Mode Headless (Non-Interactive)**: Menguasai penggunaan flag CLI (`-p`, `--output-format json`, `--dangerously-skip-permissions`) dan streaming I/O terprogram tanpa intervensi manual (Human-in-the-loop).
2. **Merancang Sandboxing dan Isolasi Runtime Enterprise**: Mengimplementasikan boundary eksekusi yang aman menggunakan container ephemeral berbasis rootless Docker/Podman, network policy terbatas, dan least-privilege token access untuk mencegah eksfiltrasi data atau modifikasi filesystem destruktif.
3. **Membangun CI/CD Orchestrator Wrapper**: Menulis sistem wrapper production-grade dengan TypeScript/Node.js untuk mengeksekusi Claude Code, memvalidasi diff Git secara deterministik, memitigasi *infinite reasoning loops*, dan menangani exit codes secara presisi.
4. **Menerapkan Guardrail Anggaran & Token Throttling**: Mengendalikan konsumsi kuota Anthropic API secara programmatic di dalam pipeline CI/CD guna mencegah lonjakan biaya tak terduga (*runaway cost*).
5. **Mengintegrasikan Automated Code Review & Auto-Remediation Workflow**: Membangun pipeline GitHub Actions end-to-end yang menerima payload issue/PR, menjalankan diagnosis berbasis agent, memvalidasi hasil uji unit, dan menghasilkan Pull Request perbaikan secara otonom.

---

### 2. Concept Overview

Secara default, Claude Code beroperasi sebagai CLI interaktif yang mengandalkan siklus *Read-Eval-Print Loop* (REPL) bersama engineer manusia. Setiap kali agent hendak memanggil tool manipulasi sistem (seperti `FileEdit`, `Bash`, atau `GlobTool`), sistem meminta konfirmasi persetujuan dari operator melalui antarmuka terminal (TTY).

```
[Mode Interaktif]
User Input ---> Claude Agent ---> Tool Proposed ---> Prompt Approval [y/N] ---> Execution
                                                            ^
                                                     Human Bottleneck

[Mode Non-Interactive / Headless]
Payload/Event ---> Claude Runner ---> Policy Validation Engine ---> Auto-Execution ---> Structured Diff
                                               |
                                     (Deterministic Sandbox)
```

Dalam skenario automasi pipeline CI/CD, ketiadaan TTY fisik menuntut pergeseran arsitektur ke **Headless Agentic Execution**. Pada model ini:
- Interaksi dialihkan ke *Single-Shot Prompting* atau *Structured Event Ingestion* melalui standard input (`stdin`) atau flag non-interaktif (`-p` / `--print`).
- Ijin eksekusi bypass (`--dangerously-skip-permissions`) diaktifkan, namun **wajib dipagari secara eksternal** oleh sandbox isolasi berbasis container OS-level.
- Keluaran agent diarahkan ke standard output (`stdout`) dalam format terstruktur (JSON stream) untuk di-parse oleh sistem orchestration downstream.
- Loop deterministik dikunci oleh batas waktu (*execution timeout*), batas langkah (*step limit*), dan kuota anggaran (*cost/token ceiling*).

---

### 3. Why It Matters

Menerapkan Claude Code secara langsung ke infrastruktur otomatisasi bukan sekadar menyalin binary ke pipeline server; ini melibatkan mitigasi risiko keamanan kritis dan efisiensi biaya skala enterprise:

*   **Pemberantasan Bottleneck Triage & Bug Fixing**: Masalah-masalah berulang seperti dependency drift, perbaikan linting yang kompleks, migrasi API signature, atau kegagalan unit test deterministik dapat diselesaikan secara otonom pada level branch feature sebelum masuk tahap review manusia.
*   **Mitigasi Blast Radius Eksekusi Otonom**: Memberikan akses eksekusi shell tanpa pengawasan kepada LLM agent membuka celah eksekusi arbitrary command injection (RCE), modifikasi file di luar dependensi modul, hingga pengurasan secret env variable. Sandbox yang ketat mengisolasi blast radius hanya pada context directory terkait.
*   **Eliminasi Flakiness dalam Pipeline Deterministic**: Pipeline CI/CD menuntut status biner: sukses (`0`) atau gagal (`non-zero`). LLM secara alami bersifat probabilistik. Diperlukan abstraksi wrapper untuk memaksakan determinisme: output diff harus lolos validasi sintaksis, linter, dan test runner deterministik konvensional sebelum di-commit kembali ke repository.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur eksekusi Claude Code di dalam GitHub Actions Runner dengan isolasi container dan validasi gerbang berlapis.

```
+-----------------------------------------------------------------------------------------+
|                              CI/CD Runner Host (Ephemeral)                              |
|                                                                                         |
|  [GitHub Actions / GitLab CI Job Trigger]                                               |
|         │                                                                               |
|         ▼                                                                               |
|  +───────────────────────────────────────────────────────────────────────────────────+  |
|  |                 Orchestrator Wrapper (TypeScript Engine / Node.js)                |  |
|  |  - Ingestion Context (Issue, PR Metadata, Error Logs)                             |  |
|  |  - Token & Budget Allocator ($ Limit Monitor)                                     |  |
|  |  - Secret Masker & Env Filter                                                     |  |
|  +─────────────────────────────────────────┬─────────────────────────────────────────+  |
|                                            │ Spawns isolated process                    |
|                                            ▼                                            |
|  +───────────────────────────────────────────────────────────────────────────────────+  |
|  |               Docker Sandbox Container (Rootless, Network-Constrained)            |  |
|  |                                                                                   |  |
|  |   Environment Constraints:                                                        |  |
|  |   - Cap-drop: ALL (kecuali hak akses baca/tulis workspace)                        |  |
|  |   - Read-only Root FS, Temporary Writable /tmp & /workspace                       |  |
|  |                                                                                   |  |
|  |   +───────────────────────────────────────────────────────────────────────────+   |  |
|  |   | Claude Code Agent Engine CLI (`claude -p ...`)                            |   |  |
|  |   |                                                                           |   |  |
|  |   | [Memory Context] <──> [Anthropic API Client] <──(Outbound HTTPS 443 Only)─+---|--+-> Claude 3.7 Sonnet
|  |   |       │                                                                   |   |  |
|  |   |       ▼                                                                   |   |  |
|  |   | [Tool Executor]                                                           |   |  |
|  |   |   ├─ FileEdit / Read / Glob (Restricted to /workspace)                    |   |  |
|  |   |   └─ Bash (Local build commands: npm test, pytest, go test)               |   |  |
|  |   +─────────────────────────────────────┬─────────────────────────────────────+   |  |
|  +─────────────────────────────────────────┼─────────────────────────────────────────+  |
|                                            │ Stderr / Stdout (JSON Stream)              |
|                                            ▼                                            |
|  +───────────────────────────────────────────────────────────────────────────────────+  |
|  |                             Deterministic Verification Gate                       |  |
|  |  1. Git Diff Scope Analysis (Pastikan tidak ada modifikasi file sensitif / .github)|  |
|  |  2. Hard Linter & Static Analysis Pass (ESLint / Ruff / GolangCI-Lint)           |  |
|  |  3. Regression Test Verification Suite (Unit tests must pass 100%)                |  |
|  +─────────────────────────────────────────┬─────────────────────────────────────────+  |
|                                            │                                            |
|                    ┌───────────────────────┴───────────────────────┐                    |
|                    ▼                                               ▼                    |
|           [Pass: Create PR]                             [Fail: Pipeline Error]          |
|      git push origin agent-fix-xxxx                     Publish Diagnostics to CI       |
|      gh pr create --body "..."                          Exit Status: 1                  |
+-----------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Headless Invocation Parameter Matrix
Claude Code CLI dirancang dengan parameter internal untuk memutus ketergantungan pada interface TTY:

*   `--print` atau `-p "<prompt>"`: Mengalihkan CLI ke mode headless batch. Claude mengeksekusi instruksi hingga selesai, mencetak output akhir ke standard output, lalu segera keluar (*terminate*).
*   `--dangerously-skip-permissions`: Mematikan dialog konfirmasi tool invocation secara total. Parameter ini **hanya boleh** dieksekusi di dalam container sekali pakai (*disposable container*). Menggunakannya langsung di server host telanjang (*bare-metal runner*) merupakan pelanggaran fatal arsitektur keamanan.
*   `--output-format json`: Menghasilkan stream structured output berformat NDJSON (Newline Delimited JSON). Setiap baris mewakili lifecycle event: `init`, `message`, `tool_use`, `tool_result`, dan `completion`.

#### B. Isolasi dan Sandboxing Filesystem
Saat beroperasi secara otomatis, agen AI berpotensi memanggil subshell `Bash` yang merusak. Oleh karena itu, runtime container harus memenuhi kriteria pengerasan (*hardening*) berikut:
1. **Network Namespace Sandboxing**: Membatasi domain yang dapat diakses hanya ke API Anthropic (`api.anthropic.com`), package registry internal (misalnya NPM/PyPI mirror), dan API hosting repo (GitHub/GitLab).
2. **Filesystem Mount Isolation**: Root filesystem (`/`) dimount secara *read-only*. Direktori repositori dimount pada path terisolasi (misal `/workspace`) dengan batas *inode* dan *storage quota* yang ketat.
3. **Restricted Shell Environment**: Env vars yang diekspos ke Claude Code **tidak boleh** memuat token CI privilege tinggi. Token `GITHUB_TOKEN` yang disuplai hanya memiliki scope `contents: write` dan `pull-requests: write`.

#### C. Deterministic Feedback Loop
Model agentik non-interaktif menerapkan pendekatan *Plan -> Act -> Verify*:
1. Agen menganalisis error traceback dari log pipeline.
2. Agen memodifikasi file kode sumber.
3. Wrapper memicu eksekusi ulang suite pengujian secara mandiri.
4. Jika pengujian gagal, output pengujian dimasukkan kembali ke context Claude Code untuk siklus iterasi berikutnya hingga batas maksimal iterasi (*loop guard*) tercapai.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Claude CI Orchestrator Wrapper** production-ready menggunakan **TypeScript/Node.js** yang bertugas mengelola siklus hidup headless agent, parsing NDJSON, monitoring resource/budget, serta eksekusi sandboxed child process.

#### File Structure
```
ci-orchestrator/
├── package.json
├── tsconfig.json
└── src/
    ├── types.ts
    ├── sanitizer.ts
    └── runner.ts
```

#### `src/types.ts`
```typescript
export interface OrchestratorConfig {
  workspaceDir: string;
  maxCostUsd: number;
  timeoutMs: number;
  maxRetries: number;
  targetBranch: string;
  anthropicApiKey: string;
}

export interface ExecutionResult {
  success: boolean;
  totalCostUsd: number;
  rawOutput: string;
  filesModified: string[];
  errorMessage?: string;
}

export interface ClaudeEventPayload {
  type: 'init' | 'message' | 'tool_use' | 'tool_result' | 'cost' | 'completion';
  content?: string;
  tool?: string;
  cost?: number;
  timestamp: string;
}
```

#### `src/sanitizer.ts`
```typescript
export class SecuritySanitizer {
  private static readonly BLOCKED_PATTERNS: RegExp[] = [
    /ghp_[a-zA-Z0-9]{36}/,               // GitHub Personal Access Token
    /github_pat_[a-zA-Z0-9_]{82}/,       // GitHub Fine-grained PAT
    /sk-ant-api[a-zA-Z0-9-_]{80,}/,      // Anthropic API Key
    /BEGIN (RSA|OPENSSH|EC) PRIVATE KEY/ // Private Keys
  ];

  private static readonly PROTECTED_PATHS: RegExp[] = [
    /^\.github\//,
    /^\.git\//,
    /^\.env/,
    /^package-lock\.json$/,
    /^yarn\.lock$/,
    /^pnpm-lock\.yaml$/
  ];

  public static sanitizeString(input: string): string {
    let sanitized = input;
    for (const pattern of this.BLOCKED_PATTERNS) {
      sanitized = sanitized.replace(pattern, '[REDACTED_SECRET]');
    }
    return sanitized;
  }

  public static validatePathMutation(path: string): boolean {
    const normalized = path.replace(/^\.\//, '');
    for (const pattern of this.PROTECTED_PATHS) {
      if (pattern.test(normalized)) {
        return false;
      }
    }
    return true;
  }
}
```

#### `src/runner.ts`
```typescript
import { spawn } from 'child_process';
import * as path from 'path';
import { simpleGit, SimpleGit } from 'simple-git';
import { OrchestratorConfig, ExecutionResult, ClaudeEventPayload } from './types';
import { SecuritySanitizer } from './sanitizer';

export class ClaudeCIOrchestrator {
  private git: SimpleGit;
  private currentCostUsd = 0;

  constructor(private config: OrchestratorConfig) {
    this.git = simpleGit({ baseDir: config.workspaceDir });
  }

  public async runAutoRemediation(prompt: string): Promise<ExecutionResult> {
    const modifiedFilesBefore = await this.getChangedFiles();
    if (modifiedFilesBefore.length > 0) {
      throw new Error("Workspace tidak bersih: Terdapat unstaged changes sebelum eksekusi agent.");
    }

    const startTime = Date.now();
    let accumulatedOutput = '';
    const modifiedFiles: Set<string> = new Set();

    try {
      await this.executeHeadlessClaude(prompt, (line: string) => {
        accumulatedOutput += line + '\n';
        this.processStreamEvent(line, modifiedFiles);
      });

      const filesAfter = await this.getChangedFiles();
      
      // Verifikasi integritas: pastikan file terlindungi tidak disentuh
      for (const file of filesAfter) {
        if (!SecuritySanitizer.validatePathMutation(file)) {
          throw new Error(`Security Policy Violation: Agent memodifikasi file terproteksi: ${file}`);
        }
      }

      return {
        success: true,
        totalCostUsd: this.currentCostUsd,
        rawOutput: SecuritySanitizer.sanitizeString(accumulatedOutput),
        filesModified: filesAfter
      };
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      return {
        success: false,
        totalCostUsd: this.currentCostUsd,
        rawOutput: SecuritySanitizer.sanitizeString(accumulatedOutput),
        filesModified: Array.from(modifiedFiles),
        errorMessage
      };
    }
  }

  private executeHeadlessClaude(
    prompt: string,
    onLineReceived: (line: string) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      // Perintah CLI Claude non-interaktif
      const args = [
        '-p', prompt,
        '--dangerously-skip-permissions',
        '--output-format', 'json'
      ];

      const env = {
        ...process.env,
        ANTHROPIC_API_KEY: this.config.anthropicApiKey,
        CI: 'true',
        NODE_ENV: 'test'
      };

      const child = spawn('claude', args, {
        cwd: this.config.workspaceDir,
        env,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      const timer = setTimeout(() => {
        child.kill('SIGTERM');
        reject(new Error(`Timeout eksekusi terlampaui (${this.config.timeoutMs} ms)`));
      }, this.config.timeoutMs);

      let stderrBuffer = '';

      child.stdout.on('data', (chunk: Buffer) => {
        const lines = chunk.toString('utf-8').split('\n');
        for (const line of lines) {
          if (line.trim().length > 0) {
            onLineReceived(line);
          }
        }
      });

      child.stderr.on('data', (chunk: Buffer) => {
        stderrBuffer += chunk.toString('utf-8');
      });

      child.on('error', (error: Error) => {
        clearTimeout(timer);
        reject(new Error(`Gagal melakukan bootstrap Claude binary: ${error.message}`));
      });

      child.on('close', (code: number | null) => {
        clearTimeout(timer);
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Claude process exit code ${code}. Stderr: ${stderrBuffer}`));
        }
      });
    });
  }

  private processStreamEvent(rawLine: string, modifiedTracker: Set<string>): void {
    try {
      const payload: ClaudeEventPayload = JSON.parse(rawLine);
      
      if (payload.type === 'cost' && typeof payload.cost === 'number') {
        this.currentCostUsd += payload.cost;
        if (this.currentCostUsd > this.config.maxCostUsd) {
          throw new Error(`Budget Exceeded: Pengeluaran $${this.currentCostUsd.toFixed(4)} melampaui limit $${this.config.maxCostUsd}`);
        }
      }

      if (payload.type === 'tool_use' && payload.tool === 'FileEdit' && payload.content) {
        // Ekstraksi metadata file yang diubah
        try {
          const parsed = JSON.parse(payload.content);
          if (parsed.path) {
            modifiedTracker.add(parsed.path);
          }
        } catch {
          // Abaikan kesalahan deserialisasi konten internal tools
        }
      }
    } catch (e: unknown) {
      // Bila bukan JSON valid, baris tersebut merupakan logging stdout standard
    }
  }

  private async getChangedFiles(): Promise<string[]> {
    const status = await this.git.status();
    return [...status.modified, ...status.not_added, ...status.deleted, ...status.created];
  }
}
```

#### GitHub Actions Workflow Definisi
File: `.github/workflows/claude-auto-fix.yml`
```yaml
name: Claude Code Autonomous CI Healer

on:
  workflow_dispatch:
    inputs:
      issue_id:
        description: 'Issue/Ticket ID for context'
        required: true
      target_branch:
        description: 'Branch to apply fix on'
        required: true
        default: 'main'

permissions:
  contents: write
  pull-requests: write

jobs:
  heal-and-patch:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    
    # Menjalankan workflow di dalam container sandbox terkontrol
    container:
      image: node:20-bookworm-slim
      options: --cap-drop=ALL --cap-add=CHOWN --cap-add=SETUID --cap-add=SETGID
      
    steps:
      - name: Hardening & Base Utilities Installation
        run: |
          apt-get update && apt-get install -y --no-install-recommends \
            git \
            ca-certificates \
            curl \
            bubblewrap
          npm install -g @anthropic-ai/claude-code
          rm -rf /var/lib/apt/lists/*

      - name: Checkout Target Repository
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.inputs.target_branch }}
          fetch-depth: 0

      - name: Setup Safe Workspace Directory
        run: |
          git config --global --add safe.directory "$GITHUB_WORKSPACE"
          git config --global user.name "claude-ci-bot[bot]"
          git config --global user.email "claude-ci-bot@users.noreply.github.com"

      - name: Execute Non-Interactive Orchestration
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          npx ts-node --transpile-only ./ci-orchestrator/src/runner-cli.ts \
            --prompt "Analisa kegagalan pengujian pada suite test. Identifikasi bug logic, edit file yang bermasalah, pastikan semua unit test passing lewat 'npm test'. Jangan ubah file konfigurasi pipeline atau .env." \
            --max-cost 2.50 \
            --timeout 600000

      - name: Deterministic Verification Gate
        run: |
          echo "=== Menjalankan Verifikasi Deterministik ==="
          npm ci
          npm run lint
          npm test

      - name: Push Remediation & Create Pull Request
        if: success()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          BRANCH_NAME="claude-fix/issue-${{ github.event.inputs.issue_id }}-${{ github.run_id }}"
          git checkout -b "$BRANCH_NAME"
          git add -A
          git commit -m "fix(autofix): automated remediation for issue #${{ github.event.inputs.issue_id }}"
          git push origin "$BRANCH_NAME"
          
          curl -s -X POST \
            -H "Authorization: Bearer $GH_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            https://api.github.com/repos/${{ github.repository }}/pulls \
            -d '{
              "title": "fix(auto): remediated logic failure for issue #'${{ github.event.inputs.issue_id }}'",
              "head": "'"$BRANCH_NAME"'",
              "base": "'"${{ github.event.inputs.target_branch }}"'",
              "body": "Pull request ini dibuat secara otonom oleh Claude Code Headless Pipeline Runner.\n\n### Verifikasi Deterministik:\n- Unit Tests: Passed\n- Linting: Passed\n- Security Validation: Enforced"
            }'
```

---

### 7. Edge Cases & Failure Modes

Mengoperasikan agen coding otonom dalam CI/CD melibatkan skenario kegagalan kompleks berikut:

| Failure Mode | Mekanisme Deteksi | Tindakan Mitigasi & Error Recovery |
| :--- | :--- | :--- |
| **Runaway Reasoning / Token Loop** | Event parsing mendeteksi pengulangan tool invocation yang identik lebih dari 3 kali berturut-turut tanpa perubahan state git. | Wrapper mengirimkan sinyal `SIGTERM` ke child process; mengeksekusi *fallback teardown*, mencatat log stack trace, lalu keluar dengan code `124`. |
| **Secret Exfiltration Attempt** | Parser output/prompt memindai pola teks terhadap database ekspresi reguler token/kunci (*regex pattern database*). | Sanitizer mengganti pola token dengan tag `[REDACTED_SECRET]`. Jika agen memicu shell command berbasis curl/wget ke domain eksternal tak dikenal, firewall network container memutus koneksi (socket hang up). |
| **Protected File Drift** | `git status --porcelain` mendeteksi mutasi pada direktori `.github/`, file dependency lockfiles, atau secrets. | Wrapper membatalkan seluruh perubahan (`git reset --hard HEAD`), menghapus artefak yang tidak terlacak (`git clean -fd`), dan pipeline gagal (*hard failure*). |
| **Anthropic API Rate Limiting (HTTP 429)** | Deteksi status exit code non-zero beserta log spesifik rate limit (`rate_limit_error`). | Mengimplementasikan strategi *Exponential Backoff dengan Full Jitter* pada level wrapper sebelum re-instansiasi runner process. |
| **Partial Fix / Flaky Tests** | Claude Code melaporkan tugas selesai, namun langkah deterministik pipeline (`npm test`) mengembalikan exit code non-zero. | Pipeline memblokir pembuatan Pull Request secara absolut. State commit di-drop; ringkasan error diposting ke Issue dashboard sebagai konteks kegagalan. |

---

### 8. Trade-offs & Alternatif Solusi

Memilih Claude Code headless via CLI wrapper dibandingkan alternatif agen lain dalam ekosistem CI/CD memerlukan pertimbangan matang:

```
                  FLEKSIBILITAS INTEGRASI
                            ▲
                            │       [Direct Anthropic API / Custom Agent]
                            │       (Tinggi kontrol, tinggi overhead maintenance)
                            │
                            │   [Claude Code CLI Wrapper]
                            │   (Keseimbangan out-of-the-box tools & CI isolation)
                            │
                            │ [Aider / Sweep.dev]
                            │ (Terikat workflow Git opini mereka)
                            │
  ──────────────────────────┼────────────────────────────────────────►
  RENDAH                    │                                TINGGI
                            │                        OUT-OF-THE-BOX POLISH
```

#### Analisis Perbandingan

1. **Claude Code CLI Wrapper (Metode Modul Ini)**:
   * *Kelebihan*: Memanfaatkan ekosistem tools internal Claude Code yang matang (syntax highlighter, context-aware grep/glob, specialized patch edit). Menjaga keselarasan prompt antarmuka CLI yang sama antara developer workstation dan CI runner.
   * *Kekurangan*: Sedikit lebih berat dalam konsumsi memory karena Node.js runtime CLI; parsing NDJSON memerlukan custom wrapper untuk abstraksi kontrol yang presisi.

2. **Custom Agentic Harness (Direct Anthropic SDK via LangChain/LlamaIndex)**:
   * *Kelebihan*: Kontrol 100% atas pemanggilan function calling, parameter temperature, context compression, dan token usage.
   * *Kekurangan*: Mengharuskan developer membangun kembali tools file search, fuzzy diff patcher, bash sandboxing, dan error-recovery mechanism dari nol (*reinventing the wheel*).

3. **Dedicated PR Agents (e.g., Sweep, Copilot Workspace, Aider)**:
   * *Kelebihan*: Antarmuka SaaS siap pakai, integrasi web-hook GitHub instan.
   * *Kekurangan*: Vendor lock-in; batasan kustomisasi sandbox pada level network; model pricing premium SaaS di atas biaya token API dasar.

---

### 9. Best Practices & Standard Industri

Untuk mengoperasikan pipeline ini pada skala enterprise dengan standar industri tertinggi:

*   **Principle of Least Privilege (PoLP) pada Token CI**:
    Jangan pernah memberikan izin administrative (`admin:repo_hook`, `repo:all`) pada ephemeral runner. Batasi token GitHub hanya ke read access untuk commit dan write access terisolasi ke pull-requests.
*   **Budget Ceiling Hard Limits**:
    Terapkan batas pengeluaran finansial *per-job* yang tidak bisa di-override (misal, batas maksimum $2.00 per proses auto-fix). Jika batas tercapai, wrapper wajib mematikan proses via kill-switch internal.
*   **Enforce Ephemeral and Rootless Runner Runtimes**:
    Container build harus beroperasi dalam model *rootless execution*. Jangan pernah menjalankan subshell Claude Code dengan hak akses `root` host. Gunakan security context drop flags: `--cap-drop=ALL`.
*   **Mandatory Human Sign-off Policy**:
    Hasil otomasi Claude Code harus dialirkan **hanya** ke bentuk draft Pull Request. Larang keras otomasi auto-commit langsung (*direct commit*) ke branch utama (`main`/`master`) tanpa review manusia dan status check approval.
*   **Cryptographic Audit Trails**:
    Simpan seluruh rekaman event log (prompts, tool calls, sanitization drops) sebagai file artifak terkompresi dan terenkripsi dalam retensi CI selama 30-90 hari guna keperluan audit security compliance (SOC2 / ISO 27001).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas membangun pipeline auto-remediation yang mendeteksi kerusakan fungsi validasi email pada service login, memperbaikinya via Claude Code headless, dan memverifikasi hasilnya hingga lulus test suite.

#### Langkah 1: Persiapan Repositori & Aplikasi Target
Buat direktori proyek lokal dan inisialisasi modul:

```bash
mkdir claude-ci-lab && cd claude-ci-lab
npm init -y
npm install --save-dev jest typescript ts-node @types/jest simple-git
```

Buat file implementasi buggy di `src/auth.ts`:
```typescript
export function validateEmail(email: string): boolean {
  // BUG: Menggunakan regex yang salah; memperbolehkan format email tanpa domain valid
  return email.includes("@");
}
```

Buat suite pengujian di `src/auth.test.ts`:
```typescript
import { validateEmail } from './auth';

describe('validateEmail', () => {
  it('should return true for valid emails', () => {
    expect(validateEmail('eng@enterprise.com')).toBe(true);
    expect(validateEmail('security.officer@domain.co.id')).toBe(true);
  });

  it('should return false for invalid emails', () => {
    expect(validateEmail('invalid-email-without-at')).toBe(false);
    expect(validateEmail('broken@')).toBe(false);
    expect(validateEmail('@nodomain.com')).toBe(false);
  });
});
```

Tambahkan target test pada `package.json`:
```json
"scripts": {
  "test": "jest"
}
```

Pastikan test saat ini **gagal**:
```bash
npx jest
# OUTPUT: FAILED (Expected false, received true pada test broken@)
```

#### Langkah 2: Konfigurasi Entrypoint Orchestrator
Salin implementasi TypeScript dari **Bagian 6** ke dalam `ci-orchestrator/src/types.ts`, `sanitizer.ts`, dan `runner.ts`. Kemudian buat entrypoint eksekutor `ci-orchestrator/src/runner-cli.ts`:

```typescript
import { ClaudeCIOrchestrator } from './runner';
import * as path from 'path';

async function main() {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    console.error("FATAL: ANTHROPIC_API_KEY environment variable is required.");
    process.exit(1);
  }

  const orchestrator = new ClaudeCIOrchestrator({
    workspaceDir: path.resolve(__dirname, '../../'),
    maxCostUsd: 1.50,
    timeoutMs: 180000,
    maxRetries: 1,
    targetBranch: 'main',
    anthropicApiKey: apiKey
  });

  const prompt = `
    Jalankan test suite menggunakan npm test. Analisa output failure di src/auth.test.ts.
    Perbaiki bug logic pada src/auth.ts agar seluruh test case passes.
    Pastikan regex email mengikuti standar RFC dasar.
    Dilarang mengubah file test (src/auth.test.ts).
  `;

  console.log("Memulai eksekusi Claude Code CI Runner...");
  const result = await orchestrator.runAutoRemediation(prompt);

  if (result.success) {
    console.log(`[SUCCESS] Eksekusi berhasil!`);
    console.log(`Biaya: $${result.totalCostUsd.toFixed(4)}`);
    console.log(`File diubah:`, result.filesModified);
    process.exit(0);
  } else {
    console.error(`[FAILURE] Eksekusi gagal: ${result.errorMessage}`);
    process.exit(1);
  }
}

main();
```

#### Langkah 3: Eksekusi Headless Remediation
Jalankan runner script di environment terminal:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-xxxx-YOUR-KEY"
npx ts-node --transpile-only ./ci-orchestrator/src/runner-cli.ts
```

#### Langkah 4: Verifikasi Hasil
Setelah runner selesai dengan output exit code `0`:
1. Periksa `git status` dan pastikan file `src/auth.ts` telah diperbarui dengan validasi regex yang presisi.
2. Jalankan unit test deterministik:
   ```bash
   npm test
   # OUTPUT: PASS src/auth.test.ts (2 passed, 2 total)
   ```
3. Lakukan verifikasi riwayat perubahan (*git diff*):
   ```bash
   git diff src/auth.ts
   ```
Anda telah berhasil membangun ekosistem otomasi non-interaktif terisolasi yang mengeksekusi self-healing bug fix menggunakan Claude Code.