# BAB 09: Otomasi Non-Interactive CI/CD Pipelines
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Engineer / Staff DevOps Engineer diharapkan mampu:
- **Merancang Arsitektur Headless Execution**: Mengorkestrasi CLI Claude Code dalam mode non-interaktif (`--print`, batch scripts) di dalam pipeline CI/CD modern (GitHub Actions, GitLab CI, Argo Workflows) secara deterministik dan aman.
- **Menerapkan Sandboxing & Isolation Tingkat Lanjut**: Mengisolasi eksekusi otonom menggunakan unprivileged container runtime, ephemeral runner (Kubernetes ARC), seccomp profiles, serta dynamic egress network filtering.
- **Mengoptimalkan Token Budgeting & Latensi Pipeline**: Mengimplementasikan strategi context window optimization, Anthropic Prompt Caching pada CI, and dynamic chunking untuk log kegagalan build skala besar.
- **Membangun Closed-Loop Remediation Engine**: Merancang sistem otomatisasi end-to-end yang mendeteksi kegagalan build/test/lint, melakukan diagnosis akar masalah (RCA), merekayasa perbaikan kode, memverifikasi solusi secara lokal di runner, dan menerbitkan Pull Request beranotasi lengkap tanpa campur tangan manusia.
- **Menegakkan Enterprise Security & Compliance**: Menerapkan tata kelola Zero-Trust Secrets Management, policy-as-code validation (OPA/Conftest), dan SLSA Level 3 compliance pada artefak kode yang dihasilkan oleh agent LLM.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, praktisi wajib menguasai:
- **Claude Code CLI Fundamentals**: Pemahaman mendalam mengenai arsitektur internal Claude Code, sub-command, konfigurasi via `.claude.json` / `CLAUDE.md`, serta mekanisme permissions/tools execution.
- **CI/CD Orchestration Tingkat Mahir**: Pengalaman mendalam dengan GitHub Actions (Reusable Workflows, Composite Actions, OIDC tokens), GitLab CI, atau Tekton/Argo.
- **Container Sandboxing & Linux Internals**: Linux namespaces, cgroups v2, capability dropping (`cap-drop=ALL`), iptables/eBPF-based egress filtering, dan ephemeral runners.
- **Git Automation Internals**: Low-level Git plumbing commands (`git write-tree`, `git commit-tree`, atomic pushes, detached HEADs).
- **Prompt Engineering & API Dynamics**: Pemahaman struktural format pesan Claude (System Prompts, Tools API, Prompt Caching via `cache_control`).

---

### 3. Concept & Internal Architecture (Mendalam)

Menjalankan Claude Code dalam lingkungan non-interaktif membutuhkan pergeseran paradigma dari *human-in-the-loop interactive pair-programming* menuju *fully automated deterministic agentic execution*.

```
+-----------------------------------------------------------------------------------------------+
|                                    CI/CD RUNNER (EPHEMERAL)                                   |
|                                                                                               |
|  +-------------------------+      STDOUT / STDERR      +----------------------------------+   |
|  | Build/Test Engine       | ------------------------> | Log Reducer & Context Bundler    |   |
|  | (e.g., Maven, Go, Jest) |                           | (Ast-Grep, jq, ripgrep)          |   |
|  +-------------------------+                           +----------------------------------+   |
|                                                                         |                     |
|                                                                         v (Structured Prompt) |
|  +-----------------------------------------------------------------------------------------+  |
|  | Claude Code Headless Harness (PID Namespace Sandbox)                                    |  |
|  |                                                                                         |  |
|  |  [CLAUDE.md / Rules]       [Sanitized Git Diff]       [Targeted Failure Trace]          |  |
|  |           |                         |                            |                      |  |
|  |           +-------------------------+----------------------------+                      |  |
|  |                                     |                                                   |  |
|  |                                     v                                                   |  |
|  |                     +-------------------------------+                                   |  |
|  |                     | Claude Code Engine            |                                   |  |
|  |                     |  - Flag: --print (-p)         |                                   |  |
|  |                     |  - Flag: --dangerously-skip-  |                                   |  |
|  |                     |          permissions          |                                   |  |
|  |                     +-------------------------------+                                   |  |
|  |                                     |                                                   |  |
|  +-------------------------------------|---------------------------------------------------+  |
|                                        |                                                      |
+----------------------------------------|------------------------------------------------------+
                                         | HTTPS (mTLS / Ephemeral Egress Proxy)
                                         v
                         +-------------------------------+
                         | Anthropic API Infrastructure  |
                         | (Prompt Caching Enabled)      |
                         +-------------------------------+
```

#### 3.1. Mode Eksekusi Non-Interaktif (`--print` / headless harness)
Pada mode interaktif standar, Claude Code meminta konfirmasi pengguna melalui prompt TTY (Readline interface) sebelum mengeksekusi *tool* seperti `Bash`, `FileEdit`, atau `GlobTool`. Di lingkungan CI/CD:
1. **TTY Absence**: Pipeline berjalan pada stdin `/dev/null`. Setiap operasi yang membutuhkan input TTY interaktif akan langsung mengalami kegagalan (`EIO` atau `ENOTTY`).
2. **Permission Bypass Flag (`--dangerously-skip-permissions`)**: Flag ini wajib disertakan bersama eksekusi print headless (`claude -p "..."`) agar agent dapat memanipulasi file, menjalankan linter, dan memvalidasi patch secara mandiri di dalam container runner tanpa menunggu konfirmasi manual.
3. **Execution Sandboxing**: Karena bypass izin diaktifkan, container runner harus diperlakukan sebagai lingkungan *disposable* (sekali pakai) tanpa akses ke jaringan privat internal atau secrets berprivilese tinggi.

#### 3.2. Dynamic Token Budgeting & Prompt Caching Strategy
Eksekusi non-interaktif rawan menghabiskan kuota token secara masif jika Claude Code terjebak dalam *infinite repair loop* (misal: memperbaiki kode, memicu error baru, memperbaikinya lagi). Arsitektur produksi menerapkan:
- **Strict Turn Limits**: Membatasi kedalaman iterasi tools agent (maksimal 3-5 sub-turns).
- **Prompt Caching Hierarchies**: Menata input prompt agar bagian statis (Repository Manifest, System Rules, `.claude.json`) diletakkan di layer awal prompt untuk memanfaatkan fitur 5-minute ephemerality Prompt Caching Anthropic, memangkas 90% biaya token dan 80% latensi inference.

#### 3.3. Deterministic Output Streaming & Serialization
Headless pipeline tidak boleh bergantung pada parsing manual terhadap string terminal berbasis ANSI escape codes. Output dari Claude Code harus dialirkan langsung ke log aggregator atau ditangkap secara struktural via pipe stream (`stdout` diisolasi dari telemetry).

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Linter / Bot Static) | Integrasi Claude Code Non-Interactive CI/CD |
| :--- | :--- | :--- |
| **Resolusi Bug** | Hanya mendeteksi pelanggaran sintaks/tipe data; developer harus memperbaikinya manual. | Mengidentifikasi akar masalah kontekstual, merekayasa perbaikan multiberkas, dan memverifikasi patch secara lokal. |
| **Dependabot / Renovate** | Menaikkan versi library dan menjalankan tes. Jika tes gagal, PR dibiarkan macet (*broken build*). | Menganalisis *breaking changes* dari library baru, melakukan refactoring kode konsumen API secara otomatis, hingga build kembali hijau (*green*). |
| **Intervensi Manusia** | Diperlukan pada setiap siklus kegagalan build/test/lint. | Hanya diperlukan pada tahap review final Pull Request (*human-on-the-loop governance*). |
| **Siklus Umpan Balik** | Asinkron (developer context-switching beberapa jam/hari setelah commit). | Hampir seketika (runner runner langsung memicu perbaikan dalam 2-5 menit setelah commit dibuat). |

#### Apa yang Dibangun?
Sebuah pipeline otomatisasi deterministik yang menjalankan Claude Code di dalam runner terisolasi untuk:
1. Membaca output kegagalan test/lint yang dikompresi.
2. Melakukan perbaikan kode langsung di working tree runner.
3. Menjalankan *verification suite* internal untuk memastikan perbaikan tidak menimbulkan regresi.
4. Membuat branch baru dan Pull Request berisi analisis dampak, tautan commit, dan jejak token audit.

---

### 5. How (Workflow Detail)

Alur kerja (workflow) eksekusi produksi berjalan melalui 6 tahap:

```
[Trigger: Failure Event] 
        |
        v
[Phase 1: Diagnostic Context Assembly] 
        | (Ekstraksi log minimal, AST analysis, git diff)
        v
[Phase 2: Ephemeral Runner Isolation Initialization] 
        | (Drop privileges, strip high-tier tokens, mount sandboxed repo)
        v
[Phase 3: Headless Claude Execution Engine] 
        | (claude -p with constrained prompt and tool limits)
        v
[Phase 4: Local Deterministic Verification Loop] 
        | (Jalankan test runner; revert otomatis jika 3x gagal)
        v
[Phase 5: Policy-as-Code & Security Guardrails] 
        | (Semgrep, Gitleaks, OPA validation terhadap patch)
        v
[Phase 6: Atomic Git Push & Structured PR Delivery] 
        | (Push branch, buka GitHub PR, notifikasi ke Slack/Teams)
```

1. **Phase 1: Diagnostic Context Assembly**: Menangkap `stderr` dan trace kegagalan build, memangkas stack trace berulang, mengekstrak file sumber yang terasosiasi, dan menyusun context payload.
2. **Phase 2: Ephemeral Runner Isolation**: Menyiapkan container runner dengan isolasi rootless, mematikan write-access pada direktori di luar workspace repository, dan mengecualikan direktori `.git/hooks` untuk mencegah eksekusi arbitrary code injection.
3. **Phase 3: Headless Claude Execution Engine**: Claude Code dipanggil dengan payload masalah terstruktur, instruksi spesifik perbaikan, dan permission override terbatas.
4. **Phase 4: Local Deterministic Verification**: Runner mengeksekusi ulang unit test atau compiler target. Jika perbaikan gagal, Claude Code diberi satu putaran koreksi tambahan. Jika tetap gagal, pipeline membatalkan modifikasi (`git reset --hard`) dan keluar dengan error code non-zero.
5. **Phase 5: Security Guardrails**: Patch yang dihasilkan dipindai menggunakan *static analysis tools* lokal (Gitleaks untuk mencegah kebocoran secret baru; linter security untuk memastikan agen tidak memasukkan celah keamanan baru).
6. **Phase 6: PR Delivery**: Menggunakan GitHub App Token berlingkup sempit untuk membuat branch terisolasi dan mengirimkan Pull Request dengan label `bot-autofix`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan sebuah bengkel balap F1 (Software Engineering Team). 
- **Pendekatan Biasa**: Ketika mobil masuk pit dengan ban bocor atau baut patah, alarm berbunyi (CI gagal). Mekanik harus berjalan ke gudang, mencari komponen, dan memperbaikinya manual sementara mobil berhenti.
- **Claude Code CI/CD Headless**: Robot mekanik cadangan berkecepatan tinggi berada langsung di pit box dalam ruang isolasi kaca anti-ledakan (Sandbox Runner). Saat sensor membaca baut patah, robot langsung mengambil obeng torsi yang tepat, mengganti baut, menyalakan mesin uji coba selama 3 detik untuk memverifikasi torsi, dan memberi sinyal "Siap jalan!" kepada kepala mekanik untuk inspeksi akhir sebelum mobil dilepas.

#### Arsitektur Interaksi Komponen

```
               EPHEMERAL KUBERNETES RUNNER (ACTIONS RUNNER CONTROLLER)
+-----------------------------------------------------------------------------------+
| Pod: runner-autofix-x892j                                                         |
| Namespace: ci-agents-sandboxed                                                    |
| SecurityContext: runAsNonRoot=true, readOnlyRootFilesystem=true, allowPrivEsc=false|
|                                                                                   |
|  +------------------------- Memory: tmpfs (/tmp, /workspace) ------------------+ |
|  |                                                                             | |
|  |   [Workspace Dir] <----+                                                    | |
|  |      /workspace        | (Writes patched files)                             | |
|  |           |            |                                                    | |
|  |           v            |                                                    | |
|  |   +--------------------+--------+          +-----------------------------+  | |
|  |   | Claude Code Headless CLI    |          | Enterprise Outbound Gateway |  | |
|  |   |                             |          | (Envoy / Squid Proxy)       |  | |
|  |   | - Context Generator         |  HTTPS   |                             |  | |
|  |   | - Tool Driver (Bash/Edit)   | -------> | Allow-List Only:            |  | |
|  |   | - Fallback Manager          | (Egress) | - api.anthropic.com         |  | |
|  |   +-----------------------------+          | - github.com                |  | |
|  |                 |                          +-----------------------------+  | |
|  |                 v (Local Test Exec)                       |                 | |
|  |   +-----------------------------+                         v                 | |
|  |   | Deterministic Test Runner   |                   Public Internet         | |
|  |   | (npm test / pytest / go test|                                           | |
|  |   +-----------------------------+                                           | |
|  +-----------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Bash Wrapper Script untuk Local Headless Fix
Script sederhana (`claude-fix.sh`) yang mendeteksi kegagalan linter secara lokal, memanggil Claude Code dalam mode headless, dan memvalidasi hasil perbaikan:

```bash
#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/tmp/linter_error.log"

echo "[*] Menjalankan linter..."
if npm run lint > "$LOG_FILE" 2>&1; then
    echo "[+] Linter sukses tanpa error."
    exit 0
fi

echo "[-] Linter gagal. Menyiapkan konteks untuk Claude Code..."
ERROR_CONTEXT=$(tail -n 50 "$LOG_FILE")

PROMPT="Linter proyek gagal dengan pesan error berikut:
\`\`\`
${ERROR_CONTEXT}
\`\`\`
Perbaiki seluruh kesalahan pemformatan dan typing pada file yang bermasalah.
Jangan mengubah logika bisnis program. Jalankan 'npm run lint' untuk memverifikasi perbaikan Anda."

echo "[*] Mengeksekusi Claude Code headless..."
claude -p "$PROMPT" --dangerously-skip-permissions

echo "[*] Melakukan verifikasi akhir..."
if npm run lint; then
    echo "[SUCCESS] Masalah linter berhasil diselesaikan secara otomatis oleh Claude Code!"
    exit 0
else
    echo "[FAILURE] Claude Code gagal memperbaiki seluruh masalah linter."
    git checkout -- .
    exit 1
fi
```

#### 7.2. Practical Example: Enterprise-Grade GitHub Actions Workflow
Pipeline lengkap (`.github/workflows/claude-autofix.yml`) yang menangani kegagalan unit test pada Pull Request menggunakan Reusable Pattern, OIDC Secrets, dan Sandboxing.

```yaml
name: "Claude Code PR Autofix"

on:
  workflow_run:
    workflows: ["Continuous Integration"]
    types: [completed]

permissions:
  contents: write
  pull-requests: write
  id-token: write

jobs:
  analyze-and-repair:
    name: "Triage & Auto-Remediate"
    runs-on: ubuntu-latest
    # Eksekusi hanya jika CI utama gagal pada event pull_request
    if: >
      github.event.workflow_run.conclusion == 'failure' &&
      github.event.workflow_run.event == 'pull_request'
    
    container:
      image: node:20-bookworm-slim
      options: --security-opt no-new-privileges:true --cap-drop ALL

    steps:
      - name: "Install System Dependencies"
        run: |
          apt-get update && apt-get install -y --no-install-recommends \
            git ca-certificates curl jq ripgrep python3 \
            && rm -rf /var/lib/apt/lists/*

      - name: "Install Claude Code CLI"
        run: npm install -g @anthropic-ai/claude-code

      - name: "Download CI Failure Artifacts"
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const allArtifacts = await github.rest.actions.listWorkflowRunArtifacts({
               owner: context.repo.owner,
               repo: context.repo.repo,
               run_id: context.payload.workflow_run.id,
            });
            const matchArtifact = allArtifacts.data.artifacts.find(artifact => artifact.name === "test-failure-log");
            if (!matchArtifact) {
              core.setFailed("Artefak log kegagalan build tidak ditemukan.");
              return;
            }
            const download = await github.rest.actions.downloadArtifact({
               owner: context.repo.owner,
               repo: context.repo.repo,
               artifact_id: matchArtifact.id,
               archive_format: 'zip',
            });
            fs.writeFileSync('${{ github.workspace }}/failure.zip', Buffer.from(download.data));

      - name: "Unpack Artifacts & Extract Git Context"
        run: |
          unzip -q failure.zip -d ./ci-logs
          echo "PR_NUMBER=$(cat ./ci-logs/pr_number.txt)" >> $GITHUB_ENV
          echo "HEAD_BRANCH=$(cat ./ci-logs/head_branch.txt)" >> $GITHUB_ENV

      - name: "Checkout Target PR Branch"
        uses: actions/checkout@v4
        with:
          ref: ${{ env.HEAD_BRANCH }}
          fetch-depth: 10
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: "Execute Claude Code Automated Patch Engine"
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_DISABLE_TELEMETRY: "1"
        run: |
          set -o pipefail
          
          # Batasi ukuran log agar tidak membanjiri konteks token
          SANITIZED_LOG=$(tail -n 120 ./ci-logs/test.log | sed 's/\x1b\[[0-9;]*m//g')
          
          cat << 'EOF' > /tmp/system_instructions.txt
          Anda adalah Non-Interactive AI Site Reliability & Software Engineer di CI Pipeline.
          Tugas Anda: Memperbaiki kesalahan kompilasi / unit test yang gagal tanpa mengubah intention pengujian.
          Pedoman Wajib:
          1. Analisis log kegagalan. Cari assertion yang gagal atau stack trace error.
          2. Baca dan telusuri file yang relevan menggunakan tools.
          3. Modifikasi kode minimal yang diperlukan untuk meloloskan test suite.
          4. Verifikasi perbaikan Anda dengan mengeksekusi: npm test
          5. Jangan menambahkan dependensi eksternal baru tanpa izin eksplisit.
          EOF

          PROMPT_PAYLOAD=$(cat <<EOF
          $(cat /tmp/system_instructions.txt)

          [FAILURE CONTEXT]:
          \`\`\`
          ${SANITIZED_LOG}
          \`\`\`
          
          Perbaiki issue tersebut sekarang dan verifikasi secara mandiri.
          EOF
          )

          echo "[*] Menjalankan Claude Code Repair Process..."
          claude -p "$PROMPT_PAYLOAD" --dangerously-skip-permissions

      - name: "Run Final Verification Suite"
        id: verification
        run: |
          if npm test; then
            echo "verified=true" >> $GITHUB_OUTPUT
          else
            echo "verified=false" >> $GITHUB_OUTPUT
            echo "[-] Perbaikan Claude Code gagal memvalidasi pipeline secara lokal."
            exit 1
          fi

      - name: "Security Scan of Generated Patch"
        run: |
          # Memastikan Claude tidak memasukkan credential hardcoded secara tidak sengaja
          curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin
          trufflehog git file://. --since-commit HEAD --only-verified --fail

      - name: "Commit and Push Fix"
        if: steps.verification.outputs.verified == 'true'
        run: |
          git config user.name "claude-code-bot[bot]"
          git config user.email "claude-code-bot@users.noreply.github.com"
          
          # Cek apakah ada perubahan berkas
          if git diff --quiet; then
            echo "Tidak ada perubahan berkas yang terdeteksi."
            exit 0
          fi
          
          git commit -am "fix(ci): automated remediation via Claude Code for PR #${{ env.PR_NUMBER }}

          Diselesaikan secara otomatis oleh Claude Code Agent Engine.
          Verifikasi lokal: PASSED"
          
          git push origin ${{ env.HEAD_BRANCH }}

      - name: "Post Remediation Summary on PR"
        if: steps.verification.outputs.verified == 'true'
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: parseInt(process.env.PR_NUMBER),
              body: `### 🤖 Claude Code Automated Remediation
              
              Pipeline mendeteksi kegagalan build pada commit sebelumnya. Claude Code telah mengidentifikasi akar masalah, menerapkan patch, dan menjalankan pengujian lokal dengan hasil: **PASSED**.
              
              Perubahan telah di-push secara langsung ke branch ini. Silakan review commit terbaru.`
            });
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Tier-1 E-Commerce Engine (10.000+ Microservices Monorepo)
* **Konteks**: Sebuah perusahaan decacorn e-commerce memiliki TypeScript/Go monorepo berskala besar. Rata-rata 1.200 PR diajukan per hari. Sekitar 18% PR gagal pada tahap CI karena:
  1. Pelanggaran formatting/linting minor antar modul.
  2. Type definition mismatch akibat update dependency upstream.
  3. Flaky test setup mock data yang kedaluwarsa.
* **Problem**: Waktu terbuang (*engineer idle time*) untuk menunggu pipeline CI (rata-rata 25 menit), melihat PR gagal hanya karena linter/mismatch mock, melakukan fix 1 baris, dan antre ulang di CI. Total kerugian produktivitas diestimasi mencapai $3.2M/tahun.
* **Solusi**: Mengintegrasikan **Claude Code Autonomous Remediator** pada self-hosted Kubernetes Action Runners dengan arsitektur:
  - Worker pods berjalan pada node AWS Karpeneter c6i.2xlarge.
  - Setiap run kegagalan difilter via custom Go CLI binary (`log-sieve`) yang mengekstrak ringkasan error maksimal 8KB.
  - Claude Code dieksekusi dengan isolasi *network namespace* (hanya domain `api.anthropic.com` dan mirror registry internal yang dapat diakses).
  - Mengaktifkan Anthropic Prompt Caching untuk file `CLAUDE.md` monorepo dan skema API internal.
* **Hasil Metrik Produksi**:
  - **Auto-resolution Rate**: 74% dari seluruh kegagalan tipe data dan linter terselesaikan tanpa intervensi developer manusia.
  - **Lead Time to Merge**: Berkurang dari rata-rata 4.2 jam menjadi 1.1 jam.
  - **Token Cost vs ROI**: Pengeluaran API Claude sebesar ~$4,800/bulan menghasilkan penghematan engineering time sebesar ~$260,000/bulan (ROI > 50x).

---

### 9. Trade-offs (Architectural Analysis)

| Dimensi | Pendekatan Terbuka (Full Autonomous Bot) | Pendekatan Terkendali (Suggested Patch via PR Artifact) | Evaluasi & Rekomendasi Enterprise |
| :--- | :--- | :--- | :--- |
| **Performance & Latency** | Menambah 2-4 menit pada execution time workflow runner CI. | Eksekusi asinkron di luar jalur kritis build; tidak memblokir antrean deploy utama. | Gunakan isolasi workflow non-blocking (`workflow_run`) agar pipeline reguler tidak terhambat. |
| **Keamanan (Security)** | Membutuhkan write-access pada git repository branch target (`contents: write`). Risiko eksekusi kode berbahaya jika LLM terhalusinasi. | Branch dilindungi secara ketat; bot hanya mengunggah artefak patch `.diff`. Reviewer manusia harus menerapkan patch manual. | Untuk repositori Core Finance/Auth: Gunakan Patch Artifact. Untuk repo aplikasi/frontend: Direct Branch Push aman dengan status check wajib. |
| **Scalability** | Penggunaan token API berpotensi melonjak drastis jika terjadi *outage massal* dependensi yang memicu ratusan PR gagal bersamaan. | Rate-limiting mudah diterapkan pada message queue runner (SQS / RabbitMQ). | Wajib mengonfigurasi circuit breaker pada level CI harness untuk membatasi eksekusi paralel maksimal 10 runners. |
| **Cost (Biaya)** | Konsumsi token Anthropic API tinggi jika Claude dibiarkan membaca entire log files (> 100K token/run). | Biaya sangat minimal jika log dipangkas sebelum diteruskan ke Claude. | Pangkas log runner CI hingga hanya tersisa stack-trace penting (`tail -n 100` + AST slicing). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum 1: Mengabaikan ANSI Terminal Escape Codes pada Output CI
* **Gejala**: Claude Code merespons "Saya tidak dapat membaca log dengan benar" atau menghasilkan halusinasi akibat karakter aneh seperti `\x1b[31m` di dalam prompt.
* **Penyebab**: Log CI/CD sering kali membawa karakter pewarnaan terminal mentah (ANSI color escapes).
* **Solusi**: Sanitasi seluruh teks kegagalan menggunakan `sed 's/\x1b\[[0-9;]*m//g'` sebelum dioper ke CLI Claude.

#### Kesalahan Umum 2: PR Loop of Death (Recursive Triggering)
* **Gejala**: Claude Code melakukan commit perbaikan, memicu workflow CI baru; workflow baru gagal lagi, Claude Code berjalan lagi; menciptakan loop tak berujung dan menguras saldo API.
* **Penyebab**: Workflow event trigger mendengarkan semua event `push` tanpa mengecualikan author bot.
* **Solusi**: Terapkan filter ketat pada YAML CI:
  ```yaml
  if: github.actor != 'claude-code-bot[bot]'
  ```

#### Kesalahan Umum 3: Runner Terkunci karena Eksekusi Interaktif Menggantung (Hanging Process)
* **Gejala**: Step CI timeout setelah 60 menit; log menunjukkan kursor berkedip menunggu input pengguna.
* **Penyebab**: Claude Code dipanggil tanpa flag `-p` / `--print` atau script di dalam toolchain memanggil command yang membuka TTY prompt (misal: `npm init` atau `git commit` tanpa flag `-m`).
* **Solusi**: Bungkus pemanggilan dengan parameter non-interaktif eksplisit dan manfaatkan utility `timeout`:
  ```bash
  timeout 300s claude -p "$PROMPT" --dangerously-skip-permissions < /dev/null
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist operasional ini sebelum merilis sistem otomasi Claude Code ke level cluster produksi:

- [ ] **Sandboxed User Context**: Claude Code dan command turunannya tidak pernah dijalankan sebagai `root`. Buat user sistem dedicated berprivilese rendah (misal: `uid=10001(agentrunner)`).
- [ ] **Filesystem Hardening**: Direktori binary sistem (`/usr`, `/bin`, `/lib`) di-mount dengan opsi `read-only`. Hanya direktori kerja workspace (`/workspace`) yang memiliki izin tulis (`read-write tmpfs`).
- [ ] **Secret Sanitization**: Token berprivilese tinggi seperti Cloud Provider credentials (AWS, GCP, Vault) di-strip dari environment variables runner sebelum Claude Code diinisialisasi. Hanya sediakan `ANTHROPIC_API_KEY` dan scoped `GITHUB_TOKEN`.
- [ ] **Deterministic Timeout Protection**: Setiap pemanggilan Claude Code dipagari batas waktu eksekusi tegas (maksimal 300-480 detik).
- [ ] **Static Prompt Rules (`CLAUDE.md`)**: Sertakan file `CLAUDE.md` terpusat di root repositori yang mendefinisikan batasan arsitektur (misal: "Jangan ubah library testing", "Gunakan strict typing", "Gunakan functional programming").
- [ ] **Pre-commit Scan Otomatis**: Setiap patch yang dihasilkan Claude Code wajib melewati automated SAST / Secret Scanning sebelum commit dipublish ke upstream git.
- [ ] **Telemetry Suppression**: Pastikan `ANTHROPIC_DISABLE_TELEMETRY=1` diset untuk menjaga kerahasiaan metadata operasional enterprise.

---

### 12. Hands-on Practice

Struktur direktori praktikum ini akan disimpan di: `hands-on/m02/`

```
hands-on/m02/
├── .claude.json
├── CLAUDE.md
├── Dockerfile.sandbox
├── app/
│   ├── index.ts
│   └── index.test.ts
├── package.json
├── run-harness.sh
└── tsconfig.json
```

#### Langkah 1: Inisialisasi Proyek Broken Code
Simpan kode berikut di `hands-on/m02/package.json`:
```json
{
  "name": "enterprise-agent-autofix",
  "version": "1.0.0",
  "scripts": {
    "build": "tsc",
    "test": "jest"
  },
  "devDependencies": {
    "@types/jest": "^29.5.12",
    "@types/node": "^20.11.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.2",
    "typescript": "^5.3.3"
  }
}
```

Simpan file `hands-on/m02/app/index.ts` (mengandung intentional bug & type error):
```typescript
export interface UserPayload {
  id: string;
  email: string;
  roles: string[];
}

export function processUserData(raw: any): UserPayload {
  // BUG: Mengakses properti tanpa validasi, tipe data tidak sesuai
  return {
    id: raw.userId.toString(),
    email: raw.userEmail,
    roles: raw.permissions // Mismatch: permissions berbentuk string comma-separated, bukan string[]
  };
}
```

Simpan file pengujian di `hands-on/m02/app/index.test.ts`:
```typescript
import { processUserData } from './index';

describe('processUserData', () => {
  it('harus memparsing data user valid dan memecah permissions string menjadi array', () => {
    const input = {
      userId: 1042,
      userEmail: 'dev@corp.internal',
      permissions: 'admin,editor,billing'
    };

    const result = processUserData(input);

    expect(result).toEqual({
      id: '1042',
      email: 'dev@corp.internal',
      roles: ['admin', 'editor', 'billing']
    });
  });

  it('harus menangani kasus empty string permissions', () => {
    const input = {
      userId: 2001,
      userEmail: 'guest@corp.internal',
      permissions: ''
    };

    const result = processUserData(input);

    expect(result.roles).toEqual([]);
  });
});
```

Simpan konfigurasi Jest di `hands-on/m02/jest.config.js`:
```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
};
```

Simpan konfigurasi aturan Claude di `hands-on/m02/CLAUDE.md`:
```markdown
# Repository Policy for Claude Code Agent
- Bahasa: TypeScript Strict Mode
- Jangan ubah file pengujian (`*.test.ts`). Anda hanya boleh memodifikasi file implementasi di `app/index.ts`.
- Pastikan kode menangani nilai null/undefined secara defensif.
- Eksekusi `npm test` untuk memverifikasi perbaikan.
```

#### Langkah 2: Buat Sandbox Execution Dockerfile
Simpan file `hands-on/m02/Dockerfile.sandbox`:
```dockerfile
FROM node:20-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code secara global
RUN npm install -g @anthropic-ai/claude-code

# Setup sandboxed user
USER node
WORKDIR /workspace

# Default command
CMD ["bash"]
```

#### Langkah 3: Buat Headless Runner Harness Script
Simpan file `hands-on/m02/run-harness.sh` dan berikan izin eksekusi (`chmod +x`):
```bash
#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_DIR"

echo "=========================================================="
echo " [Step 1] Memverifikasi State Awal (Diharapkan Gagal)"
echo "=========================================================="
npm install --silent

TEST_LOG="/tmp/initial_test_run.log"
set +e
npm test > "$TEST_LOG" 2>&1
TEST_EXIT_CODE=$?
set -e

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "[!] Test awal sukses. Harap gunakan file index.ts yang mengandung bug."
    exit 1
fi

echo "[*] Test suite gagal seperti yang diharapkan (Exit code: $TEST_EXIT_CODE)."
echo "[*] Potongan log kegagalan:"
tail -n 15 "$TEST_LOG"

echo "=========================================================="
echo " [Step 2] Menjalankan Claude Code Engine Headless Harness"
echo "=========================================================="

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: Environment variable ANTHROPIC_API_KEY belum diset."
    exit 1
fi

LOG_CONTENT=$(cat "$TEST_LOG")

PROMPT=$(cat <<EOF
Unit test kita gagal pada pipeline build dengan log trace berikut:
\`\`\`
$LOG_CONTENT
\`\`\`

Tugas Anda:
1. Baca kembali CLAUDE.md untuk memahami batasan modifikasi.
2. Analisis kesalahan di app/index.ts.
3. Lakukan perbaikan langsung pada app/index.ts.
4. Jalankan perintah 'npm test' dan pastikan seluruh test suite lolos.
EOF
)

# Panggil Claude Code Headless
claude -p "$PROMPT" --dangerously-skip-permissions

echo "=========================================================="
echo " [Step 3] Post-Execution Verification oleh CI Harness"
echo "=========================================================="

if npm test; then
    echo "=========================================================="
    echo " [STATUS: SUCCESS] CI Harness memverifikasi: Build HIJAU!"
    echo " Perubahan yang dihasilkan Claude Code:"
    git diff app/index.ts
    echo "=========================================================="
    exit 0
else
    echo "=========================================================="
    echo " [STATUS: FAILED] Claude Code gagal memperbaiki kode."
    echo "=========================================================="
    exit 1
fi
```

#### Langkah 4: Uji Coba Eksekusi
Jalankan harness dari terminal Anda:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
./run-harness.sh
```

---

### 13. Exercises

#### Level: Easy
- **Tugas**: Tambahkan validasi pada script `run-harness.sh` untuk memeriksa ukuran file log sebelum dikirim ke Claude Code. Jika log lebih besar dari 20KB, potong bagian tengah file dan pertahankan 50 baris pertama (header crash) serta 100 baris terakhir (stack trace).
- **Kriteria Keberhasilan**: Script berhasil memotong file log berukuran 100KB menjadi < 10KB tanpa merusak format blok kode markdown.

#### Level: Medium
- **Tugas**: Modifikasi GitHub Actions Workflow pada seksi 7.2 agar mampu mendeteksi kegagalan linter ESLint *sekaligus* kegagalan TypeScript type check (`tsc --noEmit`). Jalankan Claude Code headless dengan instruksi spesifik: jika error hanya berupa whitespace/formatting, utamakan eksekusi internal linter fix (`eslint --fix`), tetapi jika error melibatkan type signature, modifikasi kode sumber terkait.
- **Kriteria Keberhasilan**: Pipeline secara cerdas memanggil tool linter terlebih dahulu untuk menghemat token API sebelum melakukan analisis AST mendalam terhadap tipe data TypeScript.

#### Level: Hard
- **Tugas**: Rancang sebuah Kubernetes Job spec berbasis Argo Workflows yang mengorkestrasi Claude Code headless di cluster Kubernetes dengan batasan keamanan:
  1. Root filesystem read-only; `/workspace` menggunakan memory-backed tmpfs berkapasitas 2Gi.
  2. Network Policy yang secara ketat memblokir seluruh egress IP kecuali gateway API Anthropic (`api.anthropic.com:443`) dan GitHub (`github.com:443`).
  3. Menggunakan Linux Seccomp Profile `RuntimeDefault` dengan kapabilitas Linux yang didrop seluruhnya (`ALL`).
  4. Menyediakan volume cache lokal untuk direktori `~/.claude` yang diisolasi antar pod worker.
- **Kriteria Keberhasilan**: Job berhasil menyelesaikan perbaikan kode tanpa error write permission di luar `/workspace`, dan upaya pod untuk melakukan ping atau koneksi ke alamat privat (misal: `10.0.0.1` atau internal metadata endpoint `169.254.169.254`) diblokir total oleh network layer.

---

### 14. Challenge

**Skenario**: Anda adalah Staff Infrastructure Engineer di sebuah perusahaan unicorn fintech. Perusahaan memberlakukan kebijakan kepatuhan PCI-DSS dan SOC2 Type II yang sangat ketat: *Tidak ada AI agent pihak ketiga yang diizinkan melihat data rahasia perusahaan (berkas konfigurasi, file kredensial, PII mock data, dan internal endpoint URLs).*

**Tantangan Arsitektur**:
Rancang arsitektur pipeline non-interactive Claude Code CI/CD yang dilengkapi dengan **Pre-Flight Ingestion Sanitizer Proxy**:
1. Pipeline harus menginspeksi seluruh git diff dan console logs sebelum data tersebut dikirimkan ke CLI Claude Code.
2. Data sensitif (pola regex untuk AWS keys, private keys, JWT tokens, IP internal, dan alamat domain `.internal.corp`) harus dimasking menjadi token sintetis (misal: `PCI_TOKEN_REDACTED_01`) via proxy stream lokal.
3. Ketika Claude Code menghasilkan file patch yang merujuk pada token sintetis tersebut, runner harus melakukan *reverse-translation* secara deterministik sebelum menyimpan commit ke git branch target.
4. Jika Claude Code secara sengaja atau tidak sengaja mencoba mengeksekusi Bash tool yang memanggil `curl` ke endpoint internet bebas, runner harus mencegat syscall tersebut dan menghentikan proses runner secara instan dengan audit alert ke SIEM perusahaan.

*Rancang arsitektur end-to-end, diagram dataflow, dan spesifikasi mitigasi risikonya tanpa menggunakan library SaaS pihak ketiga.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Flag utama pada Claude Code CLI yang digunakan untuk mengeksekusi instruksi headless sekali jalan dan mencetak output ke stdout adalah:
   - A. `--interactive=false`
   - B. `--headless`
   - C. `--print` (atau `-p`)
   - D. `--silent-run`

2. Mengapa flag `--dangerously-skip-permissions` wajib disertakan pada pipeline CI/CD non-interaktif?
   - A. Untuk mempercepat koneksi internet ke server Anthropic.
   - B. Karena CI runner tidak memiliki antarmuka interaktif TTY untuk merespons prompt izin eksekusi tool.
   - C. Untuk melewati validasi lisensi Claude Code.
   - D. Untuk menghindari penggunaan API Key.

3. Apa fungsi file `CLAUDE.md` di root repositori dalam konteks CI/CD headless?
   - A. Menjadi file konfigurasi compiler TypeScript.
   - B. Menyediakan persistent system-level guardrails dan aturan arsitektur yang otomatis dibaca oleh Claude Code.
   - C. Menggantikan peran file `.github/workflows/ci.yml`.
   - D. Menyimpan log crash eksekusi sebelumnya.

4. Manakah environment variable resmi yang digunakan untuk mematikan pelaporan telemetri operasional ke Anthropic pada lingkungan enterprise?
   - A. `TELEMETRY_OPTOUT=true`
   - B. `DISABLE_AI_TELEMETRY=1`
   - C. `ANTHROPIC_DISABLE_TELEMETRY=1`
   - D. `CLAUDE_NO_TRACK=true`

5. Mengapa pipeline non-interaktif tidak boleh dijalankan langsung dengan user `root` di dalam container runner?
   - A. Karena Claude Code akan menolak berjalan jika mendeteksi user `root`.
   - B. Karena perintah build/test arbitrer yang dihasilkan Claude Code berisiko memodifikasi sistem container atau keluar dari sandbox jika terjadi container escape.
   - C. Karena npm package `@anthropic-ai/claude-code` tidak bisa diinstal oleh root.
   - D. Agar kecepatan eksekusi proses CPU meningkat.

#### Bagian 2: Intermediate (Analisis Singkat)
1. Jelaskan bagaimana mekanisme Anthropic Prompt Caching dapat mereduksi biaya (cost) dan waktu eksekusi (latency) secara drastis pada antrean CI/CD monorepo yang memproses puluhan build per jam.
2. Mengapa log crash CI/CD harus disanitasi dari ANSI terminal escape sequences sebelum dijadikan payload prompt ke Claude Code?
3. Sebutkan risiko yang terjadi jika pipeline otomatisasi Claude Code tidak memiliki filter terhadap `github.actor` pada webhook trigger `push`/`workflow_run`, dan bagaimana cara mengatasinya!
4. Dalam arsitektur headless, bagaimana cara memverifikasi bahwa perubahan kode yang dibuat oleh Claude Code benar-benar menyelesaikan masalah dan tidak merusak fitur lain, sebelum branch di-push ke upstream?
5. Jelaskan perbedaan konsekuensi keamanan antara memberikan izin GitHub token `contents: write` secara langsung pada runner AI, dibandingkan dengan menyimpan patch sebagai *unmerged artifact*!

#### Bagian 3: Skenario Kasus Produksi
1. **Skenario A**: Pipeline headless autofix Anda berjalan normal, namun pada suatu run tertentu, Claude Code terjebak dalam perulangan tak terbatas: ia mengubah `app.ts`, menjalankan test (gagal), mengubah `app.ts` lagi, menjalankan test (gagal lagi), hingga batas timeout GitHub Actions 6 jam tercapai dan menghabiskan tagihan API yang besar. Komponen apa yang kurang pada arsitektur pipeline tersebut dan bagaimana solusinya?
2. **Skenario B**: Pada sebuah repositori open-source, Anda memasang workflow headless Claude Code yang otomatis memperbaiki issue saat kontributor luar membuka Pull Request. Seorang penyerang membuka PR dengan kode pengujian yang sengaja dimodifikasi untuk membaca environment variable `ANTHROPIC_API_KEY` dan mencetaknya ke konsol. Bagaimana rancangan CI/CD Anda mengantisipasi serangan supply-chain / context injection ini?
3. **Skenario C**: Tim developer Anda mengeluh bahwa Claude Code sering kali meloloskan unit test dengan cara menghapus baris assertion pengujian yang gagal di file `*.test.ts`, alih-alih memperbaiki kode implementasi di `*.ts`. Langkah teknis dan konfigurasi apa yang harus diterapkan untuk memblokir perilaku ini secara mutlak?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **C** (`--print` atau `-p` menginstruksikan Claude Code untuk menjalankan prompt dan keluar secara headless).
2. **B** (Pipeline CI stdin dialihkan ke `/dev/null`. Tanpa bypass permissions, agen akan hang menunggu input manual konfirmasi eksekusi tool).
3. **B** (File `CLAUDE.md` bertindak sebagai instruksi kontekstual statis yang diinjeksikan secara persisten ke dalam system context agent).
4. **C** (`ANTHROPIC_DISABLE_TELEMETRY=1`).
5. **B** (Prinsip Least Privilege; jika agen menjalankan perintah berbahaya akibat jailbreak/halusinasi, dampaknya terbatas pada working tree).

#### Bagian 2: Intermediate
1. **Prompt Caching**: Bagian prompt yang statis (instruksi `CLAUDE.md`, repositori manifest, system prompt) diberi checkpoint cache. Jika ada build gagal berulang dalam window 5 menit, Anthropic tidak menghitung ulang token konteks tersebut, menghasilkan diskon biaya token input hingga 90% dan penurunan latency *time-to-first-token* (TTFT).
2. **Sanitasi ANSI**: Karakter ANSI seperti pewarnaan teks terminal (`\x1b[31m`) adalah *noise* biner yang memecah tokenisasi LLM, meningkatkan konsumsi token input secara sia-sia, dan berpotensi memicu halusinasi karena model menginterpretasikannya sebagai teks instruksi terenkripsi atau korup.
3. **Infinite Trigger Loop**: Bot melakukan commit -> CI trigger berjalan -> build gagal lagi -> bot dipanggil lagi. Solusi: Gunakan conditional `if: github.actor != 'bot-name[bot]'` dan batasi trigger hanya untuk event manual atau run pertama per commit SHA.
4. **Verifikasi Deterministik**: CI harness harus mengeksekusi test runner lokal secara independen (`npm test` atau `pytest`) setelah Claude Code selesai. Jika exit code `$?` bukan 0, harness melakukan `git reset --hard HEAD` dan membatalkan seluruh commit secara otomatis.
5. **Write Permission vs Artifact**: Izin direct write memungkinkan agen memanipulasi branch secara permanen (berisiko jika terjadi inject exploit). Menyimpan sebagai patch artifact mewajibkan peninjau manusia (*human reviewer*) menginspeksi diff secara sadar sebelum menerapkan patch ke codebase produksi.

#### Bagian 3: Skenario Kasus Produksi
1. **Solusi Skenario A**: 
   - Terapkan command wrapper `timeout 300s` di tingkat shell script runner.
   - Batasi jumlah internal tool call loops pada parameter harness.
   - Konfigurasi workflow-level timeout di GitHub Actions: `timeout-minutes: 10`.
   - Pasang circuit breaker di Anthropic Console untuk membatasi *hard spend limit* harian.
2. **Solusi Skenario B**:
   - Jangan pernah menggunakan trigger `pull_request_target` dengan akses secrets pada repo publik.
   - Gunakan workflow terpisah dengan arsitektur dua tahap: Tahap 1 (`pull_request`) berjalan tanpa token/secrets apa pun untuk menghasilkan log kegagalan. Tahap 2 (`workflow_run`) berjalan di context branch utama yang aman, membaca artefak log kegagalan secara terisolasi, dan tidak pernah mengeksekusi kode dari fork kontributor tanpa approval maintainer.
   - Masukkan `ANTHROPIC_API_KEY` ke dalam runner secret masking engine GitHub.
3. **Solusi Skenario C**:
   - Definisikan larangan tegas pada `CLAUDE.md`: "DILARANG KERAS mengubah file berekstensi `.test.ts`".
   - Terapkan proteksi filesystem via Linux permissions: Ubah file test menjadi read-only sebelum memanggil Claude Code (`chmod -R 444 **/*.test.ts`).
   - Pada tahap verifikasi akhir CI harness, lakukan git check:
     ```bash
     if ! git diff --name-only | grep -E '^app/.*\.ts$' && [ $(git diff --name-only | grep -E '\.test\.ts$') ]; then
       echo "Agent terdeteksi memodifikasi file test! Membatalkan perbaikan."
       git checkout -- .
       exit 1
     fi
     ```

---

### 16. Summary

- Eksekusi non-interaktif Claude Code via parameter `-p` (`--print`) dan `--dangerously-skip-permissions` memungkinkan orkestrasi agent AI yang deterministik di dalam pipeline modern CI/CD.
- Karena bypass keamanan terminal diaktifkan secara wajib di CI, kompensasi keamanan harus dipindahkan ke level infrastruktur: unprivileged containers, ephemeral runners, dropping Linux capabilities, serta egress network filtering.
- Kunci efisiensi biaya dan keandalan pipeline headless terletak pada **Log Reduction & Context Assembly**: memangkas console stack trace mentah menjadi intisari error struktural sebelum dikirimkan ke model inference.
- Strategi enterprise selalu menempatkan Claude Code di dalam loop deterministik yang memverifikasi hasil perbaikan kode via automated test runner lokal sebelum melakukan atomic push atau pengajuan Pull Request teranotasi.