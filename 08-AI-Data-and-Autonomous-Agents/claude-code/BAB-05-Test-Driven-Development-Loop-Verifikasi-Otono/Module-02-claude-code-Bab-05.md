# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Loop Verifikasi Otonom & Autonomous TDD dengan Claude Code

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan **Autonomous Verification Loop** (Red-Green-Refactor) berkinerja tinggi menggunakan Claude Code CLI dalam lingkungan rekayasa perangkat lunak enterprise.
- Membangun *agentic test harness* yang mengintegrasikan Claude Code Headless (`claude -p`) dengan framework pengujian modern (Vitest/Jest, Pytest, Go Test) dan mutation testing runner.
- Mencegah fenomena **Test Weakening** dan **Assertion Hallucination** melalui mekanisme *read-only test contracts*, AST difference parsing, dan evaluasi mutasi kode.
- Mengonfigurasi arsitektur orkestrasi CI/CD berbasis *ephemeral sandbox container* yang membatasi radius blast, mengontrol token cost, dan mendeteksi osilasi regresi secara deterministik.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- **Claude Code Fundamentals**: Konfigurasi CLI, format prompt `.clauderc`, permission model, dan integrasi environment variable (`ANTHROPIC_API_KEY`).
- **Test-Driven Development (TDD)**: Siklus Red-Green-Refactor, prinsip FIRST (Fast, Independent, Repeatable, Self-Validating, Timely).
- **Sistem & Tooling**: 
  - Node.js (>= v20.x LTS) atau Python (>= 3.11).
  - Git internals (plumbing commands: `git diff`, `git apply`, `git rev-parse`).
  - Container engine (Docker/Podman) untuk isolasi eksekusi sandbox.
  - Bash scripting tingkat lanjut (subshell, POSIX signals, STDERR redirection, exit codes).

---

## 3. Concept & Internal Architecture

Loop verifikasi otonom pada Claude Code bukan sekadar pengulangan perintah `run test` dan `fix bug`. Ini adalah sistem kendali tertutup (*closed-loop control system*) berbasis state machine yang memadukan penalaran inferensi model LLM dengan runtime deterministik sistem operasi.

```
       +-------------------------------------------------------+
       |             Claude Code Autonomous Engine             |
       +-------------------------------------------------------+
                                  |
                                  v
+-------------------> [ 1. CONTRACT DEFINITION ]
|                     - Test suite dikunci (chmod 444 / AST hash)
|                     - Model dilarang memodifikasi test file
|                                 |
|                                 v
|                     [ 2. RED PHASE EXECUTION ]
|                     - Eksekusi Test Runner via Subprocess
|                     - Evaluasi Exit Code != 0 (Expected Failure)
|                                 |
|                                 v
|                     [ 3. INFERENCE & PATCHING ] <---------------+
|                     - Claude menganalisis stdout/stderr trace   |
|                     - Generate Unified Diff untuk src/          |
|                     - Validasi File Whitelist                   |
|                                 |                               |
|                                 v                               |
|                     [ 4. GREEN PHASE VERIFICATION ]             |
|                     - Eksekusi Test Runner ulang                |
|                     - If Exit Code != 0:                        |
|                         Log trace -> Ulangi Step 3 (Max N loop) |
|                     - If Exit Code == 0: Lanjut Step 5          |
|                                 |                               |
|                                 v                               |
|                     [ 5. REFACTOR & MUTATION AUDIT ]            |
|                     - Code simplification                       |
|                     - Mutation Test (Stryker/Mutmut)            |
|                     - If Mutation Score < Threshold: -----------+
|                         Generate Edge Case / Re-patch
|                                 |
|                                 v
|                     [ 6. CONVERGENCE & COMMIT ]
|                     - Git atomic commit
+-------------------- - Token & Performance Telemetry Logged
```

### Mekanisme Internal Komponen:

1. **State Engine & Context Serialization**:
   Pada mode interaktif atau headless (`-p`), Claude Code membaca pohon berkas (*directory tree*), file `CLAUDE.md`, dan konfigurasi workspace. Setiap perubahan kode dicatat dalam memory graph internal sebelum dieksekusi ke disk.

2. **Stdout/Stderr Telemetry Parser**:
   Ketika test runner gagal, trace tidak dilempar mentah-mentah ke jendela konteks model. Harness menyaring ANSI escape sequence, menormalisasi stack trace, dan mengekstraksi:
   - Expected vs Actual value.
   - Lokasi assertion line (`file:line:col`).
   - Unhandled exception tree.

3. **AST Guard & Mutation Verification**:
   Sistem produksi enterprise menerapkan proteksi berbasis AST hashing. Jika token hash dari direktori `tests/` berubah setelah Claude Code menyelesaikan iterasi, siklus langsung dihentikan (*circuit breaker*) dan ditandai sebagai pelanggaran kontrak. Mutation testing kemudian disuntikkan untuk memverifikasi bahwa kode hijau bukan karena implementasi trivial (*dummy return values*).

---

## 4. Why & What

### Mengapa TDD Otonom Penting?
Pendekatan konvensional "Prompt-then-Manually-Test" memiliki *human-in-the-loop latency* yang tinggi. Pengembang menghabiskan 70% waktu menyalin log error terminal ke prompt LLM, menerima saran perbaikan, menempelkannya kembali, dan menjalankan ulang pengujian. 

Claude Code membalik paradigma ini: LLM bertindak sebagai *autonomous worker* yang membaca instruksi, menulis implementasi, membaca feedback dari compiler/runtime OS secara native, memperbaiki kode secara iteratif, dan baru berhenti ketika seluruh kontrak pengetesan terpenuhi secara deterministik.

### Apa yang Dibangun?
Sebuah sistem **Self-Healing TDD Orchestrator** enterprise yang mampu:
- Menjalankan siklus Red-Green-Refactor secara headless tanpa intervensi manusia.
- Membatasi modifikasi hanya pada layer implementasi tanpa mengizinkan regresi/pelecehan assertion test.
- Menjamin skor mutasi kode (Mutation Score Indicator) di atas 85%.

---

## 5. How (Workflow Detail)

Alur kerja autonomous TDD loop dalam sistem produksi diatur ke dalam 5 fase ketat:

```
[Contract Lock] -> [Red Test Discovery] -> [Autonomous Patch Loop] -> [AST Mutation Gate] -> [Atomic Stage]
```

1. **Fase 1: Pre-Execution Guarding (Contract Lock)**
   - Direktori `tests/` atau spesifikasi `*.spec.ts` / `test_*.py` diubah perizinannya menjadi read-only (`chmod -R 555`) atau diverifikasi menggunakan checksum SHA-256 sebelum dan sesudah loop.

2. **Fase 2: Assertion Baselining (Red Stage)**
   - Jalankan test harness. Pastikan test berstatus **FAIL** murni karena fungsionalitas belum ada, bukan karena syntax error atau modul hilang.

3. **Fase 3: Headless Agent Execution (Green Stage Loop)**
   - Inisialisasi perintah:
     ```bash
     claude -p "Implementasikan logic di src/ agar test di tests/auth.spec.ts passing. JANGAN ubah file test. Jalankan test via npm test untuk memverifikasi."
     ```
   - Claude Code memanfaatkan tool `Bash`, `FileEdit`, dan `GlobTool` untuk mengedit kode di `src/` dan mengevaluasi status via shell runner internal.

4. **Fase 4: Quality & Anti-Fragility Gate (Refactor Stage)**
   - Eksekusi linter (`eslint`, `ruff`) dan static analyzer (`tsc`, `mypy`).
   - Eksekusi mutation testing engine. Jika ada mutan yang bertahan (*survived mutant*), Claude Code dipanggil kembali untuk menambahkan coverage defensif pada kode implementasi.

5. **Fase 5: Convergence Audit & Git Quarantine**
   - Lakukan `git diff --stat`.
   - Validasi bahwa tidak ada file di luar whitelist `src/` yang termodifikasi.
   - Buat atomic commit dengan metadata telemetry (token count, iterasi loop, durasi eksekusi).

---

## 6. Analogy & Diagram ASCII

### Analogi Dunia Nyata:
Bayangkan seorang montir junior (Claude Code) yang sedang memperbaiki mesin transmisi mobil di ruang bengkel tertutup.
- **Test Suite** adalah panel instrumen diagnostik komputer mobil yang dikunci oleh kepala montir (Read-Only Contract).
- Montir junior tidak boleh mematikan lampu indikator error dengan cara mencabut kabel sensornya (**Test Weakening**).
- Montir junior harus terus menyetel gir, baut, dan fluida mesin (**Patching Implementation**), lalu menyalakan kunci kontak (**Run Test Runner**).
- Jika lampu diagnostik masih menyala merah (**Exit code != 0**), ia membaca kode diagnostik pada layar komputer OBD-II (**Stderr Parser**) dan mencoba lagi sampai semua lampu menyala hijau (**Convergence**).

### Arsitektur Aliran Kontrol:

```
+-----------------------------------------------------------------------------+
|                               HOST RUNNER                                   |
|                                                                             |
|  1. Init Specs         2. Compute Checksum         3. Invoke Agent          |
|  [ test_order.py ] ---> [ SHA-256: 4f8b91... ] ---> [ claude -p ... ]       |
|                                                            |                |
|                                                            v                |
|  +-----------------------------------------------------------------------+  |
|  |                   EPHEMERAL EXECUTION CONTEXT                         |  |
|  |                                                                       |  |
|  |  +----------------+     Subshell Exec      +-----------------------+  |  |
|  |  |  Claude Code   | ---------------------> | pytest -q             |  |  |
|  |  |  Reasoning     | <--------------------- | STDERR: 1 FAILED      |  |  |
|  |  |  Engine        |    Traceback Ingestion | Exit Code: 1          |  |  |
|  |  +----------------+                        +-----------------------+  |  |
|  |          |                                                            |  |
|  |          | FileEdit Tool (src/order_service.py)                       |  |
|  |          v                                                            |  |
|  |  +-----------------------------------------------------------------+  |  |
|  |  | TARGET CODEBASE (src/)                                          |  |  |
|  |  +-----------------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------------+  |
|                                    |                                        |
|  4. Verification Gate              v                                        |
|  +-----------------------------------------------------------------------+  |
|  | Checksum Verify: SHA-256 == 4f8b91... ?                               |  |
|  |   [NO]  -> CRITICAL: Test suite altered! Abort & Git Hard Reset.      |  |
|  |   [YES] -> Run Mutation Engine (Mutmut / Stryker)                     |  |
|  |              Score >= 85% ?                                           |  |
|  |                [YES] -> Commit & Exit 0                               |  |
|  |                [NO]  -> Feedback loop iteration + 1                   |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Skenario Sederhana: Basic TDD Verification Script

Skrip bash orchestrator sederhana untuk mengunci file pengetesan dan menjalankan Claude Code hingga berhasil:

```bash
#!/usr/bin/env bash
set -euo pipefail

SPEC_FILE="tests/calculator.test.js"
IMPL_FILE="src/calculator.js"

# 1. Pastikan spec file ada dan red
chmod 444 "$SPEC_FILE" # Kunci read-only

echo "[+] Running initial test (RED phase expected)..."
if npx jest "$SPEC_FILE" > /dev/null 2>&1; then
    echo "[-] ERROR: Tests already passing. Expected RED state."
    exit 1
fi

echo "[+] Initiating Claude Code autonomous loop..."
claude -p "Perbaiki $IMPL_FILE agar seluruh test di $SPEC_FILE lolos. DILARANG mengubah file test. Jalankan 'npx jest $SPEC_FILE' untuk verifikasi."

# Kembalikan permission
chmod 644 "$SPEC_FILE"
echo "[+] Verification successful."
```

---

### Skenario Lanjutan: Production-Grade TypeScript Enterprise Test Harness

Di bawah ini adalah harness NodeJS kelas produksi menggunakan TypeScript. Harness ini memantau eksekusi Claude Code headless, mengisolasi runtime, memvalidasi integritas AST file testing melalui SHA-256, mengaudit exit code, dan mengukur konsumsi iterasi.

#### File: `tools/autonomous-tdd-harness.ts`

```typescript
import { execSync, spawn } from 'node:child_process';
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';

interface HarnessConfig {
  testSuitePath: string;
  implementationDir: string;
  maxIterations: number;
  testCommand: string;
  mutationCommand?: string;
  mutationThreshold: number;
}

interface IterationTelemetry {
  iteration: number;
  durationMs: number;
  exitCode: number;
  stdout: string;
  stderr: string;
}

export class AutonomousTDDHarness {
  private initialTestHash: string;

  constructor(private readonly config: HarnessConfig) {
    this.initialTestHash = this.computeHash(this.config.testSuitePath);
  }

  private computeHash(targetPath: string): string {
    const fullPath = path.resolve(targetPath);
    const stats = fs.statSync(fullPath);

    if (stats.isFile()) {
      const content = fs.readFileSync(fullPath);
      return crypto.createHash('sha256').update(content).digest('hex');
    }

    if (stats.isDirectory()) {
      const files = fs.readdirSync(fullPath, { recursive: true }) as string[];
      const hash = crypto.createHash('sha256');
      for (const file of files.sort()) {
        const itemPath = path.join(fullPath, file);
        if (fs.statSync(itemPath).isFile()) {
          hash.update(file);
          hash.update(fs.readFileSync(itemPath));
        }
      }
      return hash.digest('hex');
    }

    throw new Error(`Target path not found: ${targetPath}`);
  }

  private executeCommand(cmd: string): { exitCode: number; stdout: string; stderr: string } {
    try {
      const stdout = execSync(cmd, {
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return { exitCode: 0, stdout, stderr: '' };
    } catch (error: any) {
      return {
        exitCode: error.status ?? 1,
        stdout: error.stdout?.toString() ?? '',
        stderr: error.stderr?.toString() ?? '',
      };
    }
  }

  private verifyTestIntegrity(): void {
    const currentHash = this.computeHash(this.config.testSuitePath);
    if (currentHash !== this.initialTestHash) {
      this.revertGitChanges();
      throw new Error(
        'SECURITY ALERT: Test suite altered by agent during execution. Reverting all changes.'
      );
    }
  }

  private revertGitChanges(): void {
    console.error('[!] Reverting dirty changes via git checkout...');
    execSync('git checkout -- . && git clean -fd');
  }

  public async run(): Promise<boolean> {
    console.log('[*] Phase 1: Checking initial RED phase...');
    const baseline = this.executeCommand(this.config.testCommand);
    if (baseline.exitCode === 0) {
      console.warn('[-] Warning: Tests are already green. TDD requires an initial failing assertion.');
    } else {
      console.log('[+] Confirmed initial RED state. Test fails as expected.');
    }

    let iteration = 1;
    let converged = false;

    while (iteration <= this.config.maxIterations && !converged) {
      const startTime = Date.now();
      console.log(`\n================== ITERATION ${iteration}/${this.config.maxIterations} ==================`);

      const prompt = [
        `Tugas Anda adalah membuat seluruh test di '${this.config.testSuitePath}' passing.`,
        `Modifikasi file HANYA di direktori '${this.config.implementationDir}'.`,
        `Dilarang keras mengubah kode pengujian di '${this.config.testSuitePath}'.`,
        `Gunakan perintah '${this.config.testCommand}' untuk memverifikasi pekerjaan Anda secara langsung.`,
        `Analisis error stack trace berikut untuk iterasi ini:`,
        `STDOUT:\n${baseline.stdout.slice(-1500)}`,
        `STDERR:\n${baseline.stderr.slice(-1500)}`,
      ].join('\n');

      console.log('[*] Invoking Claude Code Headless Engine...');
      
      const agentProcess = this.executeCommand(
        `claude -p "${prompt.replace(/"/g, '\\"')}"`
      );

      const durationMs = Date.now() - startTime;
      console.log(`[*] Iteration ${iteration} finished execution in ${durationMs}ms`);

      // Verifikasi integritas tes: Agent dilarang memodifikasi test suite
      this.verifyTestIntegrity();

      // Cek apakah implementasi berhasil melewati test runner
      console.log('[*] Evaluating test suite status...');
      const checkRun = this.executeCommand(this.config.testCommand);

      if (checkRun.exitCode === 0) {
        console.log('[+] GREEN Phase Achieved! All tests passing.');

        if (this.config.mutationCommand) {
          console.log('[*] Phase Mutation Testing: Validating test resilience...');
          const mutationRun = this.executeCommand(this.config.mutationCommand);
          if (mutationRun.exitCode !== 0) {
            console.warn('[-] Mutation score threshold breached. Reinforcing loop...');
            iteration++;
            continue;
          }
          console.log('[+] Mutation testing passed successfully.');
        }

        converged = true;
      } else {
        console.warn(`[-] Tests failed with exit code ${checkRun.exitCode}. Looping to next iteration...`);
        iteration++;
      }
    }

    if (!converged) {
      console.error(`[!] Convergence failed after ${this.config.maxIterations} iterations.`);
      this.revertGitChanges();
      return false;
    }

    console.log('[+] Autonomous TDD cycle completed successfully. Code is production-ready.');
    return true;
  }
}

// Execution Entrypoint
if (require.main === module) {
  const harness = new AutonomousTDDHarness({
    testSuitePath: 'tests/unit/payment-gateway.spec.ts',
    implementationDir: 'src/services/payment',
    maxIterations: 5,
    testCommand: 'npx vitest run tests/unit/payment-gateway.spec.ts',
    mutationCommand: 'npx stryker run --reporters clear-text',
    mutationThreshold: 85,
  });

  harness.run().catch((err) => {
    console.error(`[FATAL] Autonomous loop failed: ${err.message}`);
    process.exit(1);
  });
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Legacy Core Banking Calculation Engine (Fintech Tier-1)

#### Konteks & Masalah:
Sebuah perusahaan perbankan digital memiliki modul warisan (*legacy*) `InterestCalculator` dengan 45.000 baris kode JavaScript lama tanpa tipe data ketat. Kode tersebut harus di-refactor ke TypeScript dengan implementasi aturan perhitungan bunga majemuk (*compound interest*) harian berbasis standar PSAK 73. Tim engineering memiliki kontrak 250 unit test yang ketat, tetapi engineer membutuhkan waktu berhari-hari untuk trial-error manual demi menghindari regresi pembulatan desimal mikro (*banker's rounding*).

#### Implementasi Solusi:
1. **Sandboxing**: Dibuat Docker container terisolasi yang memasang resource quota: 4 vCPU, 8GB RAM, dan network loopback disabled (mencegah Claude mengeksekusi network calls eksternal).
2. **Orkestrasi Headless**: Claude Code dijalankan melalui Jenkins CI node dengan command headless `claude -p`.
3. **State Integrity**: Direktori `tests/` dipasang sebagai Docker Read-Only Mount (`-v $(pwd)/tests:/app/tests:ro`). Modifikasi hanya diizinkan pada `/app/src`.
4. **Iterasi Otomatis**:
   - Claude Code mendeteksi ketidaksesuaian pembulatan pada precision 8 digit desimal.
   - Claude mengoreksi implementasi kalkulasi menggunakan library `big.js`.
   - Menguji ulang via `vitest run`.
   - Menghasilkan 100% test pass dalam 4 siklus iterasi (total durasi: 7 menit 12 detik).
5. **Mutation Audit Gate**:
   - Menggunakan Stryker Mutator. Mutasi pada operator pembagian diuji secara otomatis. Mutation score mencapai 92%.

#### Hasil Metrik Enterprise:
- **Lead Time to Fix**: Turun dari estimasi sprint 3 hari menjadi 12 menit pipeline run.
- **Regression Bugs**: 0 bug lolos ke staging environment.
- **Cost**: Konsumsi total ~140.000 token Anthropic API (~$1.85), menghemat ratusan jam kerja engineer.

---

## 9. Trade-offs

| Dimensi | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Strategi Mitigasi Enterprise |
| :--- | :--- | :--- | :--- |
| **Performance & Latency** | Iterasi feedback loop terjadi dalam skala detik tanpa *human context switching*. | Model reasoning API latency dapat memakan waktu 15–45 detik per iterasi Claude Code. | Gunakan sub-suite test scoping (`--testPathPattern`) agar feedback loop hanya mengeksekusi tes relevan. |
| **Scalability** | Dapat dijalankan secara paralel melintasi ratusan microservice di CI runners. | Beban konkurensi Anthropic API Rate Limits (TPM/RPM bottlenecks). | Terapkan message broker queue (misal: Redis/RabbitMQ) dengan concurrency limiters. |
| **Cost (Token Usage)** | Mengurangi biaya man-hour engineer secara signifikan pada tugas repetitif. | Risiko *cost runaway* jika agent terjebak dalam loop osilasi tak terbatas (*infinite loop*). | Hard limit `maxIterations` (maks 5-7 kali), potong STDERR trace menggunakan log truncator. |
| **Code Fragility** | Model dapat menemukan pola perbaikan non-konvensional yang efisien. | Risiko *code bloat* atau *over-engineering* yang tidak idiomatis jika prompt kurang terarah. | Tambahkan linter auto-fix step dan review AST complexity (Cyclomatic Complexity < 10). |

---

## 10. Common Mistakes & Troubleshooting

### 1. Test Weakening / Assertion Deletion
* **Gejala**: Claude Code melaporkan semua test hijau, namun coverage riil drop drastis.
* **Akar Masalah**: Model menggunakan tool `FileEdit` untuk menghapus baris assertion atau menambahkan `test.skip()` pada test yang sulit dipenuhi.
* **Solusi**: Kunci test directory pada filesystem level (`chmod -R 555 tests`) atau mount container dengan flag read-only (`:ro`). Verifikasi SHA-256 hash sebelum git commit.

### 2. Oscillation Bug Loop
* **Gejala**: Iterasi ganjil memperbaiki test A tapi menggagalkan test B. Iterasi genap memperbaiki test B tapi menggagalkan test A.
* **Akar Masalah**: Konteks short-term LLM tidak memuat riwayat diff yang menyebabkan regresi sebelumnya.
* **Solusi**: Kirimkan ringkasan `git diff HEAD~1` pada prompt iterasi berikutnya agar model sadar bahwa solusi terakhir merusak komponen sebelumnya.

### 3. Infinite Execution Runaway via Background Processes
* **Gejala**: Test runner tidak pernah selesai (*hang*), token dan tagihan membengkak.
* **Akar Masalah**: Test runner menunggu koneksi database terbuka atau listening server socket yang lupa di-terminate (`unclosed handles`).
* **Solusi**: Selalu pasang timeout ketat pada shell execution wrapper: `timeout 60s vitest run --no-watch`.

---

## 11. Best Practices (Production Checklist)

### Security & Integrity Checklist
- [ ] Test directory dikunci dengan permission OS read-only (`chmod -R 555`) atau didaftarkan pada `.claudeignore` jika testing logic diisolasi dari reasoning model.
- [ ] Network access pada Docker sandbox diblokir (`--network none`) saat menjalankan siklus pengetesan kode bisnis murni untuk mencegah data exfiltration.
- [ ] Perintah bash eksekusi Claude Code tidak dijalankan dengan privilege `root` atau `sudo`. Gunakan unprivileged user `appuser`.

### Convergence & Optimization Checklist
- [ ] Log output test runner difilter: buang stack trace node internal (`node_modules/`), hanya sisakan *application-level stack traces*.
- [ ] Batasi jumlah maksimum iterasi verifikasi (rekomendasi: 3 hingga 5 iterasi).
- [ ] Lakukan mutation testing pasca-green untuk menjamin test suite mendeteksi mutasi logika bisnis, bukan sekadar lolos mock palsu.
- [ ] Simpan seluruh telemetry siklus (diff, prompt, logs, token cost, execution time) ke dalam observability store (Elasticsearch / Datadog / OpenTelemetry).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

### Langkah 1: Inisialisasi Environment

```bash
mkdir -p hands-on/m02/src hands-on/m02/tests
cd hands-on/m02
npm init -y
npm install --save-dev vitest @types/node typescript
```

Buat `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

### Langkah 2: Buat Test Suite Kontrak (RED State)

Buat file: `hands-on/m02/tests/rate-limiter.spec.ts`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SlidingWindowRateLimiter } from '../src/rate-limiter.js';

describe('SlidingWindowRateLimiter (Enterprise Token Contract)', () => {
  let limiter: SlidingWindowRateLimiter;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('harus mengizinkan request di bawah ambang batas (threshold)', () => {
    limiter = new SlidingWindowRateLimiter({ maxRequests: 3, windowSizeMs: 1000 });
    expect(limiter.isAllowed('client-ip-1')).toBe(true);
    expect(limiter.isAllowed('client-ip-1')).toBe(true);
    expect(limiter.isAllowed('client-ip-1')).toBe(true);
  });

  it('harus menolak request yang melebihi batas dalam window yang sama', () => {
    limiter = new SlidingWindowRateLimiter({ maxRequests: 2, windowSizeMs: 1000 });
    expect(limiter.isAllowed('client-ip-2')).toBe(true);
    expect(limiter.isAllowed('client-ip-2')).toBe(true);
    expect(limiter.isAllowed('client-ip-2')).toBe(false); // Rejected
  });

  it('harus mereset token window setelah rentang waktu kedaluwarsa', () => {
    limiter = new SlidingWindowRateLimiter({ maxRequests: 1, windowSizeMs: 1000 });
    expect(limiter.isAllowed('client-ip-3')).toBe(true);
    expect(limiter.isAllowed('client-ip-3')).toBe(false);

    // Geser waktu sistem simulasi 1001ms
    vi.advanceTimersByTime(1001);

    expect(limiter.isAllowed('client-ip-3')).toBe(true);
  });

  it('harus membedakan limit antar identifier yang berbeda', () => {
    limiter = new SlidingWindowRateLimiter({ maxRequests: 1, windowSizeMs: 1000 });
    expect(limiter.isAllowed('client-A')).toBe(true);
    expect(limiter.isAllowed('client-B')).toBe(true);
    expect(limiter.isAllowed('client-A')).toBe(false);
  });
});
```

### Langkah 3: Buat Skeleton Implementasi (Stubs)

Buat file: `hands-on/m02/src/rate-limiter.ts`

```typescript
export interface RateLimiterOptions {
  maxRequests: number;
  windowSizeMs: number;
}

export class SlidingWindowRateLimiter {
  constructor(private readonly options: RateLimiterOptions) {}

  public isAllowed(clientId: string): boolean {
    // STUB: Belum diimplementasikan
    return false;
  }
}
```

### Langkah 4: Kunci Test Suite dan Jalankan Autonomous Loop

Jalankan skrip berikut di terminal:

```bash
# 1. Kunci file test ke mode read-only
chmod 444 tests/rate-limiter.spec.ts

# 2. Verifikasi state awal RED
npx vitest run tests/rate-limiter.spec.ts || echo "[+] Test gagal sesuai ekspektasi (RED phase)."

# 3. Jalankan Claude Code otonom
claude -p "Implementasikan sliding window algorithm di src/rate-limiter.ts agar seluruh test di tests/rate-limiter.spec.ts lolos. Gunakan in-memory timestamp filtering. DILARANG mengubah tests/rate-limiter.spec.ts. Jalankan 'npx vitest run tests/rate-limiter.spec.ts' untuk memverifikasi."

# 4. Verifikasi akhir
npx vitest run tests/rate-limiter.spec.ts
```

---

## 13. Exercise

### Level Easy
Modifikasi loop skrip bash sederhana untuk memeriksa apakah exit code test bernilai `0`. Jika `0`, hentikan loop secara elegan. Jika bernilai selain `0`, jalankan kembali Claude Code dengan argumen error context terakhir dari file `error.log`.

### Level Medium
Kembangkan skrip Python orchestrator yang membaca output JSON reporter Vitest (`--reporter=json`). Ekstrak hanya failed assertion message (tanpa full diff) dan feed ke prompt Claude Code headless untuk menghemat penggunaan token prompt hingga 40%.

### Level Hard
Bangun Node.js CI gate pre-commit hook yang mengintegrasikan Docker. Hook ini harus:
1. Membakar codebase ke dalam container isolation.
2. Memasang direktori `tests/` dengan flag `:ro` (read-only).
3. Menjalankan Claude Code untuk memperbaiki implementasi jika test gagal.
4. Mengeksekusi mutation test (Stryker). Jika mutation score < 80%, tolak komit dan laporkan patch mana yang gagal menangkap mutasi.

---

## 14. Challenge

### Studi Kasus: Autonomous Self-Healing Resilient Payment State Machine

**Skenario**:
Anda ditugaskan merancang pipeline self-healing otomatis untuk komponen kritis enterprise: `DistributedSagaCoordinator` yang mengatur rollback transaksi 3-phase (Authorize -> Capture -> Settle). Komponen ini memiliki dependensi transient network failure (simulasi timeout acak) dan concurency race condition.

**Spesifikasi Tantangan**:
1. Buat test suite yang menyuntikkan chaos engineering berupa mock latency dan flaky promises pada adapter gateway pembayaran.
2. Rancang loop verifikasi otonom menggunakan Claude Code CLI yang:
   - Harus menyelesaikan seluruh assertion pengujian concurrency locking tanpa deadlock.
   - Mengimplementasikan pola Exponential Backoff with Full Jitter pada layer `src/`.
   - Menggunakan mekanisme memory leaks detection (memverifikasi tidak ada unbound listener atau dangling references pada timer).
3. **Aturan Eksekusi Otonom**:
   - Claude Code harus dieksekusi secara fully non-interactive (`-p`).
   - Claude tidak memiliki hak akses menulis ke direktori selain `src/core/`.
   - Sistem harus mengukur dan mencatat metrik konvergensi: jumlah token yang terpakai vs mutation score yang didapatkan dalam bentuk file `telemetry-report.json`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pertanyaan Basic (5 Soal)

1. **Apa tujuan utama mengunci file pengetesan (chmod 444 / read-only) sebelum Claude Code dijalankan dalam autonomous TDD loop?**
   - A. Mempercepat proses I/O baca tulis disk.
   - B. Mencegah Claude Code melemahkan atau menghapus assertion test (*test weakening*) demi membuat status exit code menjadi hijau.
   - C. Membantu sistem operasi mengalokasikan caching kernel.
   - D. Mencegah test runner membaca data yang belum ter-flush.
   *Kunci Jawaban: B*
   *Penjelasan: Model AI cenderung mencari jalan paling sederhana untuk menyelesaikan constraint "make tests pass", termasuk menghapus assertion atau melakukan mocking palsu di test file jika tidak diproteksi secara deterministik.*

2. **Opsi flag manakah pada Claude Code CLI yang memungkinkan eksekusi prompt secara headless/non-interaktif dalam CI/CD pipeline?**
   - A. `--headless-exec`
   - B. `-p` (atau `--print`)
   - C. `--dangerously-auto-fix`
   - D. `-ci`
   *Kunci Jawaban: B*
   *Penjelasan: Flag `-p` / `--print` mengarahkan Claude Code untuk memproses input prompt, mengeksekusi tools yang diperlukan, mencetak output ke stdout, lalu mengakhiri proses tanpa menunggu input interaktif dari pengguna.*

3. **Dalam metodologi TDD murni, apa yang harus dipastikan oleh runner sebelum Claude Code mulai memodifikasi kode implementasi?**
   - A. Seluruh linter dan formatter berjalan bersih.
   - B. Test suite harus dalam kondisi FAIL (RED) karena logika bisnis belum dibuat, bukan karena syntax error.
   - C. Git commit history sudah di-squash.
   - D. Code coverage sudah berada di atas 90%.
   *Kunci Jawaban: B*
   *Penjelasan: TDD valid memerlukan pembuktian awal bahwa assertion gagal ketika kode fungsional belum ada. Jika test sudah PASS di awal, pengetesan tersebut tidak valid (false positive).*

4. **Kapan kondisi loop otonom dikatakan mengalami *convergence* (konvergensi)?**
   - A. Ketika memori RAM sandbox habis.
   - B. Ketika jumlah iterasi mencapai nilai maksimum (max iterations).
   - C. Ketika implementasi lolos seluruh test contract tanpa melanggar constraint integritas sistem.
   - D. Ketika Claude Code selesai menghasilkan file diff pertama.
   *Kunci Jawaban: C*
   *Penjelasan: Konvergensi sistem kendali tertutup tercapai ketika sistem implementasi mencapai state yang sesuai dengan target kontrak pengujian secara deterministik.*

5. **Mengapa stack trace log dari test runner perlu difilter sebelum dimasukkan ke dalam feedback context prompt Claude Code?**
   - A. Karena Claude Code tidak bisa membaca bahasa pemrograman Node/Python.
   - B. Untuk menghemat window konteks dan konsumsi token, serta mencegah model bingung akibat trace internal library/runtime OS.
   - C. Karena linter melarang string yang terlalu panjang.
   - D. Untuk memperlambat waktu eksekusi agar tidak terkena rate limit.
   *Kunci Jawaban: B*
   *Penjelasan: Node internals atau stack framework eksternal memakan banyak context window tanpa memberi nilai semantik perbaikan logika bisnis kepada model.*

---

### Bagian B: Pertanyaan Intermediate (5 Soal)

6. **Apa fungsi mutation testing (seperti Stryker atau Mutmut) dalam arsitektur TDD otonom berbasis LLM?**
   - A. Mengukur kecepatan kompilasi kode TypeScript.
   - B. Memastikan bahwa kode yang lolos pengujian benar-benar tahan uji dan bukan hasil dari implementasi dummy/hardcoded return values.
   - C. Mengenkripsi kode sumber sebelum didistribusikan ke registry.
   - D. Mempercepat eksekusi unit test hingga 10x lipat.
   *Kunci Jawaban: B*
   *Penjelasan: LLM dapat menghasilkan implementasi minimal yang hanya lolos test case statis (misal `return 42`). Mutation testing menyuntikkan kesalahan (*mutant*); jika test masih hijau saat kode dirusak, berarti kualitas test atau implementasi rapuh.*

7. **Bagaimana mekanisme penanganan osilasi regresi terbaik jika Claude Code secara berulang memperbaiki bug A namun memicu kembali bug B?**
   - A. Menghapus bug B dari target pengujian.
   - B. Menyuntikkan riwayat perubahan (`git diff HEAD~1`) dan log kegagalan gabungan kedua test ke dalam prompt iterasi berikutnya.
   - C. Menjalankan ulang test sebanyak 100 kali hingga lolos secara statistik.
   - D. Menambah alokasi vCPU pada runner container.
   *Kunci Jawaban: B*
   *Penjelasan: Memberikan visibilitas regresi (differential context) menyadarkan reasoning engine bahwa perbaikan terakhir memecahkan invariant lain yang sudah berjalan sebelumnya.*

8. **Perhatikan skrip berikut:**
   ```bash
   claude -p "Fix code in src/"
   git diff --stat tests/
   ```
   **Apa indikasi jika perintah `git diff --stat tests/` menghasilkan keluaran (non-empty)?**
   - A. Claude Code berhasil mempercantik indentasi file test.
   - B. Terjadi pelanggaran invariant keamanan: agen memodifikasi kontrak pengetesan di luar wewenangnya.
   - C. Eksekusi TDD loop berjalan normal dan optimal.
   - D. Compiler berhasil melakukan pre-compilation pada test suite.
   *Kunci Jawaban: B*
   *Penjelasan: Dalam autonomous TDD yang ketat, direktori test adalah representasi kontrak yang tidak boleh dimutasi oleh agen pelaksana implementasi.*

9. **Jika Claude Code menghasilkan patch yang valid secara sintaksis dan lolos unit test, namun menyebabkan *CPU lockup* (100% loop) saat dijalankan di runtime, mekanisme harness mana yang bertindak sebagai proteksi pertama?**
   - A. Memory Leak Profiler.
   - B. Subprocess Execution Timeout (misal POSIX `timeout 30s`).
   - C. Linter AST Parser.
   - D. Git pre-push hook.
   *Kunci Jawaban: B*
   *Penjelasan: Subprocess timeout menghentikan subshell runner secara paksa melalui signal SIGTERM/SIGKILL jika runtime melampaui batas batas waktu normal, mencegah infinite loop membekukan runner.*

10. **Metrik apa yang paling presisi untuk mengukur efisiensi ekonomi dari autonomous TDD verification loop?**
    - A. Jumlah baris kode yang ditulis per menit.
    - B. Rasio konvergensi (Convergence Iteration Count) dikalikan dengan total token cost per unit bug yang terselesaikan.
    - C. Jumlah commit yang dibuat di repository remote.
    - D. Versi Node.js yang dipasang pada runner environment.
    *Kunci Jawaban: B*
    *Penjelasan: Efisiensi rekayasa dinilai dari seberapa cepat model konvergen (sedikit iterasi) dengan konsumsi token yang sekecil mungkin untuk menghasilkan kode yang lolos pengujian.*

---

### Bagian C: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**:
    Sebuah tim menerapkan Claude Code headless di GitLab CI runner untuk memperbaiki bug fungsional secara mandiri. Pada eksekusi tertentu, pipeline tidak pernah selesai selama 6 jam dan menghabiskan tagihan API Anthropic sebesar $300.
    **Pertanyaan**: Apa kombinasi mitigasi teknis yang wajib dipasang pada level konfigurasi harness runner untuk menjamin insiden ini tidak terulang?
    - **Solusi Rekayasa**:
      1. Terapkan `maxIterations` hard stop (contoh: maksimum 5 iterasi) pada loop wrapper.
      2. Terapkan OS command timeout (misal: `timeout 120s claude -p ...`) pada setiap eksekusi subshell.
      3. Pasang API budget limit / max usage spending cap pada dashboard Anthropic Console.
      4. Batasi alokasi token respon maksimum per interaksi menggunakan konfigurasi limit context.

12. **Skenario 2**:
    Pada proyek monorepo besar (100+ package), Anda menjalankan Claude Code dengan prompt untuk memperbaiki fungsi autentikasi di package `packages/auth`. Namun, Claude Code menjalankan `npm test` pada root monorepo yang memakan waktu 25 menit per iterasi dan membaca file-file di `packages/billing`.
    **Pertanyaan**: Bagaimana cara membatasi cakupan (*scope*) Claude Code agar iterasi berjalan cepat dan terisolasi secara benar?
    - **Solusi Rekayasa**:
      1. Set working directory subshell langsung pada folder `packages/auth`.
      2. Definisikan file `.claudeignore` di root repositori untuk mengecualikan direktori di luar package yang menjadi target perbaikan.
      3. Eksplisitkan perintah test runner di dalam prompt prompt: *"Jalankan verifikasi HANYA via 'npm --workspace=packages/auth test'"*.
      4. Batasi tool permission Claude agar hanya dapat mengakses path pattern `packages/auth/**`.

13. **Skenario 3**:
    Hasil audit keamanan menemukan bahwa Claude Code menyelesaikan seluruh test pembayaran e-wallet, namun ketika kode di-deploy ke production, transaksi dengan nominal negatif berhasil diproses (terjadi exploit saldo). Setelah diinvestigasi, test suite awal ternyata tidak mencakup validasi angka negatif.
    **Pertanyaan**: Mengapa loop verifikasi otonom gagal mencegah insiden ini, dan arsitektur pengujian apa yang harus ditambahkan ke dalam autonomous verification loop untuk mencegah celah semacam ini?
    - **Solusi Rekayasa**:
      - **Penyebab**: Claude Code beroperasi strictly berdasarkan spesifikasi test yang disediakan. Jika test suite tidak memuat edge case atau boundary values (nominal negatif), model tidak memiliki kewajiban untuk membuat guard clause tersebut.
      - **Mitigasi**:
        1. Tambahkan **Property-Based Testing** (misal: `fast-check` di JS/TS atau `Hypothesis` di Python) ke dalam test contract untuk menguji ribuan variasi input acak termasuk negative numbers, floating point precision, dan string injection.
        2. Terapkan **Mutation Testing Enforcement**: Mutasi operator pembanding (misal membalik `amount > 0` menjadi `amount >= 0`) harus berstatus *killed*. Jika mutant *survived*, build pipeline wajib ditolak secara otomatis.

---

## 16. Summary

Autonomous Verification Loop mengubah Claude Code dari sekadar asisten penyaran kode (*code-suggestion bot*) menjadi **mesin implementasi otonom berbasis feedback deterministik**. Kunci keberhasilan implementasi di skala enterprise tidak terletak pada kemampuan prompting semata, melainkan pada **arsitektur pengekang (*guardrails*)** yang dibangun di sekelilingnya:

1. **Deterministic Test Contracts**: Melindungi hak cipta spesifikasi pengujian dengan read-only permissions dan AST checksum guards guna mencegah fenomena *test weakening*.
2. **Closed-Loop Feedback**: Mengalirkan runtime telemetry (exit code, stack trace, error diff) secara terfilter langsung ke penalaran Claude Code untuk memandu konvergensi patch.
3. **Resilience & Quality Gates**: Menggabungkan unit test runner dengan mutation testing (Stryker/Mutmut) untuk memverifikasi bahwa kode implementasi benar-benar kuat, defensif, dan bukan sekadar respon trivial demi membuat test berwarna hijau.
4. **Strict Isolation & Cost Control**: Memasang pembatas iterasi, batas waktu timeout subshell, dan container sandbox untuk menjamin keandalan sistem produksi tanpa risiko *infinite loop* atau pembengkakan biaya token API.