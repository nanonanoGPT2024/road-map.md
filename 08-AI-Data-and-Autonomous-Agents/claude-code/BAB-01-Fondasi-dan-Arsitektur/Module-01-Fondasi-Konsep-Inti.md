# Bab 01: Pengenalan & Arsitektur Claude Code
## Module 01: Arsitektur Fondasi, Model Eksekusi, dan Setup Claude Code

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengidentifikasi arsitektur dasar Claude Code sebagai *agentic coding interface* berbasis terminal (CLI).
- Membedakan paradigma *code-completion* statis (Copilot-style) dengan *autonomous agentic execution loop* (Claude Code).
- Mengonfigurasi lingkungan kerja lokal (Node.js runtime, API authorization, environment variables) untuk Claude Code.
- Menganalisis siklus eksekusi internal (*Tool Calling, Context Pruning, Execution Sandbox, Feedback Loop*).
- Menjalankan sesi kerja pertama, menginspeksi alokasi token, dan mengendalikan batasan izin eksekusi tool CLI secara presisi.

---

### 2. Conceptual Overview (Gambaran Konseptual)
Claude Code (`claude-code`) bukan sekadar integrasi antarmuka chat ke dalam terminal, melainkan **agentic runtime CLI** yang menghubungkan model fondasi frontier (Claude 3.7 Sonnet / Claude 3.5 Sonnet) langsung dengan subsistem operasi lokal pengembang (file system, process execution, Git state).

Tidak seperti ekstensi IDE konvensional yang menyisipkan saran teks secara inline, Claude Code mengimplementasikan pola **ReAct (Reasoning + Acting)**. Agent menerima instruksi bahasa alami berorientasi tujuan (*goal-oriented prompt*), memecahnya menjadi serangkaian state peralihan, mengeksekusi operasi deterministik melalui tools (seperti `Bash`, `GlobTool`, `FileEditTool`, `GrepTool`), mengevaluasi keluaran stdout/stderr sistem operasi, dan mengoreksi diri secara rekursif hingga kriteria selesai tercapai.

---

### 3. The "Why" (Mengapa Ini Penting)
Pengembangan perangkat lunak skala besar jarang terselesaikan hanya dengan membuat blok kode terisolasi. Siklus hidup penulisan kode melibatkan:
1. Navigasi dependensi dan penelusuran arsitektur antardirektori.
2. Eksekusi test suite lokal dan analisis kegagalan runtime.
3. Linting, refactoring konsistensi, dan resolusi konflik Git.

Metode copy-paste kontekstual manual antara terminal, browser, dan editor menimbulkan *cognitive fatigue* dan latensi kerja yang tinggi. Claude Code mengotomatisasi jembatan ini dengan memberikan *agentic agency* kepada model langsung di terminal, memangkas siklus debugging dan implementasi dari puluhan manipulasi manual menjadi satu alur dialog terkontrol.

---

### 4. The "What" (Definisi & Komponen Utama)
Claude Code terdiri dari beberapa komponen arsitektural inti:

- **CLI Driver Client:** Komponen runtime berbasis Node.js yang bertindak sebagai orkestrator antarmuka pengguna terminal, penanganan input stream, dan parsing perintah.
- **Agentic Loop Orchestrator:** Mesin status internal yang mengelola transisi:
  $$\text{User Prompt} \rightarrow \text{LLM Inference} \rightarrow \text{Tool Calls} \rightarrow \text{Local OS Execution} \rightarrow \text{LLM Evaluation}$$
- **Tool Sandbox & Permission Engine:** Lapisan keamanan lokal yang mencegat *tool calls* berisiko tinggi (misalnya: modifikasi file kritis, destructive bash commands seperti `rm -rf`, eksekusi git checkout) untuk meminta konfirmasi eksplisit dari pengguna.
- **Context Manager:** Modul kompresi prompt dinamis yang mengelola token window Claude, menghapus output stdout yang redundan, dan memprioritaskan path file yang relevan ke dalam memori kerja (*in-context memory*).
- **Anthropic API Transport Layer:** Komunikasi aman (HTTPS/gRPC) terenkripsi menuju Claude Messages API yang memanfaatkan structured output dan native function calling.

---

### 5. The "How" (Mekanisme Kerja / Implementasi)
Siklus hidup satu giliran interaksi Claude Code berjalan sebagai berikut:

```
[User Input] 
    │
    ▼
1. CLI Context Ingestion (Git state, path, terminal info)
    │
    ▼
2. API Request Construction (System Prompts, Tools Definition, History)
    │
    ▼
3. Model Inference (Claude 3.7 Sonnet) ──► Menghasilkan: Reasoning + Tool Call Intent
    │
    ├─► Jika output teks langsung ──► Print ke terminal ──► Selesai
    │
    └─► Jika Tool Call (e.g., Bash: `npm test`)
          │
          ▼
       4. Local Permission Interceptor (Cek konfigurasi / Konfirmasi user)
          │
          ▼
       5. Tool Execution (Subprocess OS lokal membaca/menulis file/terminal)
          │
          ▼
       6. Result Injection (stdout, stderr, exit code dimasukkan sebagai tool_result)
          │
          ▼
       7. Feedback Iteration ──► Kembali ke Langkah 2 hingga agent memutuskan `stop`
```

---

### 6. Architecture / Workflow Diagram (ASCII Art)

```
+──────────────────────────────────────────────────────────────────────────+
|                              LOCAL MACHINE                               |
|                                                                          |
|  +--------------------+                                                  |
|  | Terminal / Shell   |                                                  |
|  +─────────┬──────────+                                                  |
|            │ stdin/stdout                                                |
|            ▼                                                             |
|  +─────────────────────────────────────────+                             |
|  |           CLAUDE CODE CLI               |                             |
|  |                                         |                             |
|  |  +-----------------------------------+  |                             |
|  |  |     Context & History Buffer      |  |                             |
|  |  +─────────────────┬─────────────────+  |                             |
|  |                    │                    |                             |
|  |  +─────────────────▼─────────────────+  |      HTTPS (Tool Calling)   |
|  |  |      Permission & Security Gate   |  | ◄─────────────────────────► |
|  |  +─────────────────┬─────────────────+  |                             |
|  |                    │ Approved Action    |                             |
|  |  +─────────────────▼─────────────────+  |                             |
|  |  |         Local Tool Suite          |  |                             |
|  |  |  [FileEdit] [Grep] [Bash] [Glob]  |  |                             |
|  |  +─────────────────┬─────────────────+  |                             |
|  +────────────────────┼────────────────────+                             |
|                       │ Subprocess / POSIX IO                            |
|                       ▼                                                  |
|  +─────────────────────────────────────────+                             |
|  | OS Subsystem: File System, Git, Runtime |                             |
|  +─────────────────────────────────────────+                             |
+──────────────────────────────────────────────────────────────────────────+
                                     │
                                     │ HTTPS Encrypted API Calls
                                     ▼
                   +───────────────────────────────────+
                   |       ANTHROPIC CLOUD API         |
                   |                                   |
                   |  +─────────────────────────────+  |
                   |  | Claude 3.7 / 3.5 Sonnet     |  |
                   |  | Inference Engine & Planners |  |
                   |  +─────────────────────────────+  |
                   +───────────────────────────────────+
```

---

### 7. Prerequisite Knowledge (Prasyarat)
Sebelum memasang dan mengoperasikan Claude Code, pastikan environment memenuhi kualifikasi berikut:
- **Node.js**: Versi `18.0.0` LTS atau lebih baru (`node -v`).
- **NPM / NPX**: Paket manajer Node versi `9.x` atau lebih tinggi.
- **Git**: Terinstal secara global (`git --version`) dan project berada dalam git tree initialized (`git init`).
- **Anthropic Console Account**: Memiliki API Key aktif dengan kredit atau subscription valid.
- **Sistem Operasi**: macOS 12+, Ubuntu 20.04+/Debian-based distro, atau Windows Subsystem for Linux 2 (WSL2). Native Windows Command Prompt/PowerShell tidak direkomendasikan secara langsung tanpa adaptasi POSIX.

---

### 8. Minimal Reproducible Example / Simple Example
Instalasi global dan verifikasi instalasi:

```bash
# 1. Instal Claude Code secara global via npm
npm install -g @anthropic-ai/claude-code

# 2. Verifikasi biner terpasang di system PATH
claude --version

# 3. Export API Key Anthropic ke environment shell
export ANTHROPIC_API_KEY="sk-ant-api03-xxxx-LIVE-KEY-HERExxxx"

# 4. Inisiasi sesi interaktif perdana di direktori sementara
mkdir /tmp/claude-test && cd /tmp/claude-test
git init
claude
```

Output terminal saat peluncuran:
```text
╭──────────────────────────────────────────────────────────╮
│ Welcome to Claude Code!                                  │
│ Communicating with Anthropic Claude API...              │
│ Current directory: /tmp/claude-test                     │
╰──────────────────────────────────────────────────────────╯

> Hi Claude, explain what files are in this directory.
```

---

### 9. Real-World / Practical Implementation
Skenario implementasi produksi: Bootstrap proyek TypeScript, konfigurasi dependensi dasar, dan pembuatan struktur file terkontrol secara otonom melalui satu instruksi agen.

#### Langkah 1: Siapkan Environment Variabel Permanen
Tambahkan ke konfigurasi shell (`~/.zshrc` atau `~/.bashrc`):
```bash
# Claude Code Configuration
export ANTHROPIC_API_KEY="sk-ant-api03-production-key..."
# Opsional: Membatasi biaya per request session
export CLAUDE_MAX_THINKING_TOKENS=8192
```
Muat konfigurasi:
```bash
source ~/.zshrc
```

#### Langkah 2: Eksekusi Claude Code dalam Mode Headless / Non-Interactive
Claude Code dapat diintegrasikan ke dalam automasi terminal menggunakan flag `-p` (*print mode / prompt execution*):

```bash
cd ~/projects/payment-service

claude -p "Audit package.json for deprecated dependencies, run npm test, and report results concisely"
```

#### Langkah 3: Interaksi Interaktif Tingkat Lanjut (Refactoring Task)
Buka CLI di dalam root repository kerja:
```bash
claude
```
Ketikkan prompt instruksi terstruktur:
```text
> Analyze src/auth/jwt.ts. Identify potential timing attacks in signature validation.
  If found, implement crypto.timingSafeEqual, write a unit test in src/auth/jwt.test.ts,
  and execute the test suite to confirm it passes.
```

Pada tahap ini, perhatikan terminal saat Claude Code meminta konfirmasi:
1. `Tool: ViewFile (src/auth/jwt.ts)` $\rightarrow$ *Diizinkan otomatis*.
2. `Tool: FileEdit (src/auth/jwt.ts)` $\rightarrow$ *Memerlukan konfirmasi Diff `[Y/n]`*.
3. `Tool: Bash ("npm test -- src/auth/jwt.test.ts")` $\rightarrow$ *Memerlukan konfirmasi eksekusi `[Y/n]`*.

---

### 10. Edge Cases & Error Handling

#### Kasus 1: API Rate Limit HTTP 429
Ketika berinteraksi dalam project sangat besar, token exhaustion dapat memicu:
```text
Error: 429 Rate limit exceeded. anthropic-ratelimit-tokens-remaining: 0
```
*Mitigasi:* Claude Code CLI secara internal menerapkan *exponential backoff*. Jika berhenti, tunggu jeda reset window atau batasi cakupan konteks dengan menambahkan path spesifik pada instruksi prompt daripada menginstruksikan "scan all directory".

#### Kasus 2: Perintah Bash Terkunci / Infinite Loop
Jika Claude Code mengeksekusi instruksi seperti `npm start` atau server dev yang blocking:
*Mitigasi:* Tekan `Ctrl + C` sekali untuk mengirimkan sinyal `SIGINT` ke subprocess tool tanpa mematikan sesi agen Claude. Agen akan menangkap output interrupt dan beralih ke state prompt berikutnya.

#### Kasus 3: Broken Symlinks / Circular Directory Reference
Model dapat terjebak dalam pembacaan glob file tak terbatas jika folder `node_modules` atau symlink looping tidak diabaikan.
*Mitigasi:* Pastikan file `.gitignore` berada di root repository. Claude Code secara bawaan menghormati aturan `.gitignore`.

---

### 11. Security, Performance & Scalability Considerations

#### Security (Keamanan)
- **Arbitrary Command Execution:** Claude Code memiliki akses terhadap command processor host. Jangan pernah menjalankan prompt yang bersumber dari untrusted untracked issues/webhooks tanpa meninjau *diff command* pada prompt konfirmasi keamanan.
- **Credential Scraping:** Hindari menyimpan file `.env` berisi credentials produksi di folder kerja tanpa mendaftarkannya pada `.gitignore`. Agent dapat membaca file teks polos jika diinstruksikan memeriksa konfigurasi.

#### Performance (Performa)
- **Token Ingestion Latency:** Membaca file binary besar (gambar, database SQLite, bundel `.min.js`) membebani context window dan meningkatkan *Time to First Token* (TTFT). Gunakan `.ignore` atau `.claudeignore` jika tersedia untuk membatasi file yang dibaca.

#### Scalability (Skalabilitas)
- Untuk repositori monorepo skala puluhan gigabyte, hindari menjalankan Claude Code di root. Navigasikan shell ke direktori sub-package target (misal: `apps/web` atau `services/auth`) sebelum memanggil biner `claude`.

---

### 12. Trade-offs & Limitations (Kompromi & Batasan)

| Aspek | Claude Code (Agentic CLI) | IDE Extension (e.g., GitHub Copilot) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Autonomous Agent (Bisa jalankan command, edit file, run test) | Passive Assistant (Autocomplete inline / Sidebar chat) |
| **Kebutuhan Izin** | Tinggi (Memerlukan akses OS/Subprocess/Bash) | Rendah (Hanya beroperasi di dalam editor memory buffer) |
| **Konsumsi Token** | Tinggi (Full prompt + tool calls output loop) | Rendah (Hanya baris aktif + proximate context) |
| **Kecepatan Tindakan**| Menengah (Multi-turn planning & evaluation) | Real-time (Sub-detik untuk autocompletion) |
| **Konteks Project** | Penuh (Mampu membaca seluruh file system via tool grep/glob)| Terbatas pada file yang terbuka di IDE tab |

---

### 13. Anti-Patterns to Avoid
- **"God Prompting" Tanpa Batasan:** Memberikan instruksi: *"Modernize this legacy project to Next.js 14"* pada repo ribuan baris. Pola ini akan menguras context window dan mengakibatkan halusinasi parsial. Pecah instruksi menjadi tahapan atomik modular.
- **Auto-Approving Segala Command Bash:** Menyetujui semua konfirmasi eksekusi bash tanpa membaca parameter flag. Berbahaya untuk command database migration, git reset, atau file removal.
- **Mengabaikan Git Dirty Working Directory:** Menjalankan Claude Code ketika git working tree kotor tanpa commit. Jika Claude melakukan modifikasi salah langkah (*destructive edit*), Anda kehilangan baseline untuk melakukan `git checkout -- .` rollback.

---

### 14. Best Practices & Operational Rules
1. **Aturan "Clean Working Tree":** Selalu commit atau stash perubahan file lokal sebelum memanggil `claude`.
2. **Atomic Context Specification:** Sertakan path spesifik dalam prompt:
   *Buruk:* "Fix the bug in the login page."
   *Baik:* "Inspect `src/modules/auth/login.controller.ts` and resolve the undefined redirect URI error."
3. **Validasi Test Loop Deterministic:** Selalu instruksikan Claude untuk memverifikasi perubahannya sendiri dengan menyertakan instruksi: *"Run tests after making changes to verify you haven't introduced regressions."*
4. **Gunakan Branch Khusus Agen:** Buat branch seperti `feat/claude-refactor-auth` untuk mengisolasi seluruh interaksi kode agentic sebelum digabungkan ke `main` via manual code review.

---

### 15. Verification & Testing Steps
Uji apakah instalasi dan setup arsitektur Claude Code telah valid di mesin Anda:

1. **Uji Resolusi Biner:**
   ```bash
   which claude
   # Menghasilkan path absolut, misal: /usr/local/bin/claude atau ~/.nvm/...
   ```

2. **Uji Otentikasi API:**
   ```bash
   claude -p "Respond with 'AUTH_SUCCESS' and nothing else"
   ```
   *Ekspektasi Output:*
   ```text
   AUTH_SUCCESS
   ```

3. **Uji Tool Execution Integrity:**
   Jalankan sub-perintah untuk menguji akses filesystem:
   ```bash
   claude -p "Create a file named .test-probe.txt with content 'OK', read it back, then delete it."
   ```
   Pastikan tidak ada error permission OS level saat operasi read/write.

---

### 16. Comparison / Alternatives

| Fitur / Parameter | Claude Code | Aider (`aider-chat`) | Cursor (Agent Mode) |
| :--- | :--- | :--- | :--- |
| **Interface** | Terminal CLI Murni | Terminal CLI Murni | GUI IDE (Forked VS Code) |
| **Backend Model** | Claude Exclusive (Optimized) | Multi-vendor (Claude, OpenAI, Local) | Multi-vendor Proprietary Engine |
| **Tool Execution** | Bash Native + Dynamic Internal Tools | Git diff patches + Repo map parsing | Integrated IDE Terminal + File virtual system |
| **Setup Overhead** | Minimum (`npm -g`) | Menengah (Python pip + Git requirements)| Tinggi (Perlu install & konfigurasi IDE baru) |

---

### 17. Troubleshooting Guide (Panduan Debugging Masalah Umum)

#### Masalah: "Node version incompatible"
*Penyebab:* Node.js sistem berada di bawah v18.0.0.
*Solusi:*
```bash
# Gunakan NVM untuk beralih versi
nvm install 20
nvm use 20
nvm alias default 20
npm install -g @anthropic-ai/claude-code
```

#### Masalah: "Anthropic API Key Missing / Unauthorized 401"
*Penyebab:* Envar `ANTHROPIC_API_KEY` tidak diekspor dengan benar atau nilai string tidak valid.
*Solusi:*
```bash
# Periksa apakah variabel terdaftar
printenv ANTHROPIC_API_KEY

# Jika kosong, daftarkan ulang
export ANTHROPIC_API_KEY="sk-ant-api..."
```

#### Masalah: "File editing failed: Hunk rejected"
*Penyebab:* File lokal diubah oleh editor eksternal secara simultan saat Claude Code sedang mencoba menulis patch.
*Solusi:* Tutup autosave/format-on-save pada IDE saat Claude sedang mengeksekusi stream patch, atau minta Claude membaca ulang file via prompt: *"Re-read the file state and attempt the edit again."*

---

### 18. Real-World Scenarios / Case Studies

#### Skenario: Hotfix Insiden Tengah Malam pada Repositori Legacy
**Kondisi:** Terjadi error `UnhandledPromiseRejection` pada service Node.js legacy tanpa dokumentasi menyeluruh.
**Tindakan Engineer:**
1. Masuk ke environment staging melalui SSH:
   ```bash
   cd /srv/legacy-service
   claude
   ```
2. Memberikan context output log error:
   ```text
   > A crash happened with log: "TypeError: Cannot read properties of undefined (reading 'tenantId') at Object.processOrder (dist/orders.js:142)".
     Trace back the source code in `src/`, identify the route missing null-checks, 
     implement defensive chaining, build the project with `npm run build`, and verify.
   ```
3. Claude Code menavigasi `src/orders/processor.ts`, menemukan unhandled optional chain, menulis perbaikan, mengeksekusi TypeScript compiler, dan menyelesaikan issue dalam waktu < 2 menit tanpa mengharuskan engineer men-download repositori ke mesin lokal.

---

### 19. Review Questions / Quizzes

1. **Bagaimana arsitektur Claude Code menangani perintah destruktif seperti `rm -rf` di shell lokal?**
   - A. Mengeksekusi secara instan di background tanpa logging.
   - B. Melempar error kompilasi dan keluar dari sesi.
   - C. Mencegat aksi melalui *Permission Interceptor* dan meminta otorisasi eksplisit via prompt pengguna `[Y/n]`.
   - D. Mengubah perintah menjadi `ls`.

2. **Komponen apa yang bertindak sebagai jembatan eksekusi antara penalaran Claude dan sistem operasi mesin pengembang?**
   - A. Virtual Machine Hypervisor terisolasi di Anthropic Cloud.
   - B. Local Tool Suite (seperti Bash, FileEdit, Glob, Grep) yang berjalan di subproses lokal.
   - C. WebAssembly sandbox di browser.
   - D. Docker container default tanpa izin network.

3. **Mengapa repositori Git sebaiknya berada dalam status "clean" (tanpa uncommitted changes) sebelum menjalankan sesi interaktif Claude Code?**
   - A. Agar token limit tidak habis.
   - B. Karena Claude Code menolak berjalan jika ada file `.gitignore`.
   - C. Untuk memungkinkan rollback instan (`git restore`/`git checkout`) jika Claude menghasilkan patch logika yang keliru.
   - D. Claude Code mewajibkan commit otomatis setiap 10 detik.

---

### 20. Next Steps & Recommended References
- **Modul Berikutnya:** Bab 01 Module 02: *Tool Calling Deep-Dive: File Operations, Grep/Glob Context Search, and POSIX Process Execution*.
- **Referensi Resmi:**
  - Dokumentasi Resmi Anthropic Claude Code: [https://docs.anthropic.com/en/docs/agents-and-tools/claude-code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code)
  - Anthropic API Tool Use Protocol Specification: [https://docs.anthropic.com/en/docs/build-with-claude/tool-use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
  - Node.js Child Process Execution Architecture Reference (POSIX interaction model).