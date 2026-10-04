# Kurikulum Enterprise: AI, Data & Autonomous Agents
## BAB 06: Refactoring Skala Besar & Manajemen Perubahan Terdistribusi
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi dengan Claude Code

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Engineer, Lead Architect, dan Senior Developer diharapkan mampu:
- Mengorkestrasi refactoring lintas repositori (*multi-repo/monorepo*) berskala ratusan ribu baris kode (*LoC*) secara deterministik menggunakan mesin inferensi agen Claude Code CLI.
- Mendesain arsitektur *agentic change management* berbasis isolasi `git-worktree`, verifikasi AST (*Abstract Syntax Tree*), dan *contract testing* otomatis.
- Mengonfigurasi *context boundary* dan memori proyek (`CLAUDE.md`, system instructions, memory files) untuk mengeliminasi halusinasi refactoring pada pola arsitektur kritis.
- Mengoperasikan Claude Code dalam mode *headless/non-interactive* (`-p` / pipeline mode) yang terintegrasi penuh ke dalam CI/CD pipeline untuk eksekusi migrasi kode bertahap.
- Mengontrol *token economics*, latensi eksekusi, serta mitigasi risiko regresi menggunakan strategi *rollback checkpointing* berbasis Git SHA dan *automated test-driven feedback loops*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, praktisi wajib menguasai:
- **Claude Code Fundamentals**: Pemahaman CLI `claude`, arsitektur tool-use internal (Read, Write, Edit, Glob, Bash, Grep), serta format instruksi `CLAUDE.md`.
- **Advanced Git Internals**: `git worktree`, `git bisect`, plumbing commands (`rev-parse`, `merge-tree`), *interactive rebasing*, dan *cherry-picking*.
- **Static Code Analysis & AST**: Konsep dasar AST parsing (misal: Babel parser, Tree-sitter, Python `ast`, Rust `syn`).
- **Software Architecture & Enterprise Patterns**: Hexagonal Architecture, Ports & Adapters, Domain-Driven Design (DDD), serta teknik dekomposisi monolitik (Strangler Fig Pattern).
- **Tooling & Shell Scripting**: POSIX Bash tingkat lanjut, `jq`, `ripgrep`, dan container engine (Docker/Podman).

---

### 3. Concept & Internal Architecture (Mendalam)

Refactoring skala besar dengan Claude Code bukan sekadar operasi *search and replace* berbasis regex atau model LLM konvensional. Claude Code beroperasi sebagai **Autonomous State-Machine Agent** yang memiliki siklus eksekusi:

```
[User / Pipeline Intent] 
       │
       ▼
[Context Ingestion Engine] ◄─── (CLAUDE.md, Directory Tree, Memory Bank)
       │
       ▼
[Reasoning & Plan Formulation] 
       │
       ▼
┌────────────────── Agent Execution Loop ──────────────────┐
│                                                          │
│  [Tool Selection] ──> Read / Grep / Glob / Bash          │
│         │                                                │
│         ▼                                                │
│  [File Mutation] ──> AST-aware Patch / Replace Edit      │
│         │                                                │
│         ▼                                                │
│  [Deterministic Verification] ──> Run Linters/Compilers   │
│         │                                                │
│         ▼                                                │
│  [Feedback Evaluation] ──> Error Trace Parsing           │
│         │                                                │
│         └─── (Iterate until 0 errors or Step Limit)      │
└──────────────────────────────────────────────────────────┘
       │
       ▼
[Atomic Git Commit / Checkpoint Creation]
```

#### Komponen Internal Arsitektur:
1. **Context Window Management & Compaction Layer**:
   Claude Code memanfaatkan Claude 3.5 Sonnet dengan context window 200k token. Namun, pada refactoring enterprise ribuan berkas, context window dapat terancam mengalami degradasi *needle-in-a-haystack* jika seluruh berkas dimasukkan sekaligus. Arsitektur produksi mewajibkan pemecahan tugas menggunakan **Dynamic Sub-scoping**: agen mengeksplorasi struktur via AST query (`ast-grep`/`ripgrep`) terlebih dahulu, memetakan *dependency graph*, lalu memproses berkas per cluster ketergantungan.
2. **Deterministic Mutation Engine (`Edit` Tooling)**:
   Claude Code tidak menulis ulang keseluruhan berkas jika hanya mengubah satu fungsi. Agen memanfaatkan alat manipulasi teks berbasis `unique_string_replace` yang memvalidasi *uniqueness* blok kode sumber sebelum menerapkan patch. Ini mengeliminasi risiko rusaknya berkas raksasa akibat truncation batas output token (max 8k token output).
3. **Continuous Execution Feedback Loop**:
   Ketika parameter `-p` (print/headless execution) dipadukan dengan *custom tools* atau skrip verifikasi lokal, Claude Code membaca `stderr`, melakukan parsing *stack trace* kompilator (misal: `tsc`, `cargo check`, `pytest`), mengisolasi offset baris yang rusak, dan meluncurkan *self-healing mutation* secara rekursif sebelum melangkah ke batch berkas berikutnya.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Manual / Regex) | Pendekatan Claude Code Skala Enterprise |
| :--- | :--- | :--- |
| **Kecepatan** | Berminggu-minggu hingga berbulan-bulan per modul. | Selesai dalam hitungan jam menggunakan loop terisolasi. |
| **Akurasi Kontekstual**| Regex buta terhadap *type signature*, *scope*, dan *shadowing*. | Sadar semantik bahasa, mampu mengubah signature dan seluruh call-sites. |
| **Validasi** | Manual compile & test setelah perubahan massal, memicu *merge hell*. | Kompilasi bertahap & perbaikan otomatis (*self-healing*) pada setiap atomic step. |
| **Resiko Regresi** | Sangat tinggi; sering kali edge case terlewat di call-site dinamis. | Rendah; dipagari oleh automated test run langsung di dalam loop eksekusi. |
| **Auditability** | Sulit di-trace karena ribuan baris diubah dalam 1 PR raksasa. | Terbagi rapi ke dalam urutan git commit atomik berbasis fungsionalitas. |

**Kapan Menggunakan Arsitektur Ini:**
- Migrasi runtime/framework: Dari CommonJS ke ECMAScript Modules (ESM), Python 2 ke 3, Java 8 ke 21, atau Express ke Fastify/NestJS.
- Migrasi Data Access Layer: Dari raw SQL/legacy ORM (misal: TypeORM lama / Hibernate 4) ke Prisma/Drizzle/jOOQ modern.
- Adopsi Interface/Contract Baru: Penambahan *tenant context* atau *cancellation token/context.Context* ke seluruh service layer.

---

### 5. How (Workflow Detail)

Alur kerja migrasi skala besar tanpa downtime operasional dev team:

```
[Phase 1: Dependency Mapping]
   │  Gunakan ripgrep/ast-grep untuk identifikasi target migrasi.
   ▼
[Phase 2: Isolation Setup]
   │  Buat isolated git-worktree independen dari branch master aktif.
   ▼
[Phase 3: Context Boundary Injection]
   │  Inisialisasi CLAUDE.md khusus migrasi + rules test runner.
   ▼
[Phase 4: Partitioning & Batch Execution]
   │  Eksekusi Claude Code headless (-p) per batch dependensi bottom-up.
   ▼
[Phase 5: Self-Healing & Verification Loop]
   │  Compiler check -> Test execution -> Claude auto-fix jika failure.
   ▼
[Phase 6: Atomic Commit & Checkpoint Push]
   │  Commit perubahan batch -> Clean context -> Lanjut batch berikutnya.
   ▼
[Phase 7: Merge Synthesis & Final Validation]
      Rebase ke target branch & trigger end-to-end integration tests.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi:
Bayangkan merenovasi sistem perpipaan hidrolik di gedung 50 lantai. 
- **Regex/Search-Replace** seperti mengganti semua pipa dengan diameter baru secara serentak tanpa mematikan pompa air—kebocoran fatal dan banjir tak terhindarkan.
- **Claude Code dengan Worktree Isolation** ibarat tim teknisi robotik berkecepatan tinggi yang membawa cetak biru (AST): mereka mengisolasi pipa lantai per lantai menggunakan katup darurat (*git worktree*), memasang pipa baru, menguji tekanan air lokal (*compiler/linter*), memverifikasi sensor (*unit testing*), mencatat sertifikasi (*atomic commit*), baru membuka katup utama.

```
       ISOLASI REFRACTORING DENGAN CLAUDE CODE DAN GIT WORKTREE

   Main Working Tree (/app)
   [master branch] ───────────── Active Development Team ──────────────────►
          │
          │ git worktree add ../refactor-worktree refactor/v2
          ▼
   Dedicated Worktree (/refactor-worktree)
   ┌───────────────────────────────────────────────────────────────────────┐
   │ Context Injection: CLAUDE.md, tsconfig.refactor.json                  │
   │                                                                       │
   │  [Batch 1: Core Domain Entities]                                      │
   │    └─ Claude CLI Loop ──> Edit ──> tsc --noEmit ──> Git Commit #1     │
   │                                                                       │
   │  [Batch 2: Repositories & Data Mappers]                               │
   │    └─ Claude CLI Loop ──> Edit ──> tsc --noEmit ──> Git Commit #2     │
   │                                                                       │
   │  [Batch 3: Controllers & API Layer]                                   │
   │    └─ Claude CLI Loop ──> Edit ──> tsc --noEmit ──> Git Commit #3     │
   │                                                                       │
   │  [Global Verification: E2E Integration Test Suite]                    │
   └───────────────────────────────────────────────────────────────────────┘
          │
          │ git push origin refactor/v2 & Create PR
          ▼
   GitHub Actions / GitLab CI Engine
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Migrasi Signature Callback ke Async/Await
Eksekusi single-command headless refactoring menggunakan Claude Code untuk memigrasi fungsi legacy berbasis Node.js callback ke Promise/Async-Await.

```bash
# Perintah eksekusi headless dengan batasan aksi ketat
claude -p "Ubah seluruh fungsi readFile callback di src/utils/fileHandler.ts menjadi async/await dengan standard fs/promises. Pastikan return type dan error handling via try/catch dipertahankan. Jalankan npm test tests/fileHandler.test.ts untuk validasi." \
  --dangerously-skip-permissions
```

#### 7.2 Practical Example (Production-Ready Migration Script)
Berikut adalah skrip orchestrator enterprise berbasis Bash yang memecah file codebase besar ke dalam batch, memanggil Claude Code secara terisolasi per file/batch, dan memverifikasi type correctness menggunakan TypeScript Compiler (`tsc`).

**File:** `scripts/orchestrate-refactor.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

# Konfigurasi Direktori & Log
TARGET_DIR="src/services"
CHECKPOINT_BRANCH="refactor/extract-interfaces-$(date +%s)"
LOG_FILE="refactor-execution.log"
FAILED_LOG="refactor-failures.log"

echo "=== Memulai Enterprise Refactoring Orchestrator ===" | tee -a "$LOG_FILE"

# 1. Pastikan working directory bersih
if [[ -n $(git status --porcelain) ]]; then
  echo "Error: Working directory tidak bersih. Commit atau stash perubahan Anda!" >&2
  exit 1
fi

# 2. Setup branch terisolasi
git checkout -b "$CHECKPOINT_BRANCH"
echo "Bekerja pada branch: $CHECKPOINT_BRANCH" | tee -a "$LOG_FILE"

# 3. Cari seluruh target berkas yang perlu direfaktor
TARGET_FILES=$(find "$TARGET_DIR" -type f -name "*.ts" ! -name "*.d.ts" ! -name "*.test.ts")

# 4. Loop batch execution per file
for file in $TARGET_FILES; do
  echo "--- Memproses file: $file ---" | tee -a "$LOG_FILE"
  
  PROMPT=$(cat <<EOF
Kamu bertugas melakukan refactoring enterprise pada file: ${file}.
Instruksi arsitektur:
1. Ekstrak seluruh database query raw inline menjadi methods terpisah di repository pattern yang sesuai.
2. Tambahkan explicit return types pada seluruh public class methods.
3. Pastikan tidak ada type 'any' yang tersisa. Ganti dengan unknown atau generic typing yang ketat.
4. Lakukan modifikasi langsung menggunakan Edit tool.
5. Setelah mengedit, jalankan: npx tsc --noEmit ${file}
6. Jika terjadi error TypeScript, perbaiki secara iteratif sampai exit code 0.
Batasan: Jangan ubah public signature yang dipanggil oleh file eksternal tanpa backward compatibility.
EOF
)

  # Eksekusi Claude Code secara headless tanpa konfirmasi interaktif manual
  # Timeout diset ke 300 detik per batch file untuk mencegah hanging loop
  if timeout 300 claude -p "$PROMPT" --dangerously-skip-permissions >> "$LOG_FILE" 2>&1; then
    # Validasi integrasi lokal file
    if npx tsc --noEmit "$file"; then
      git add "$file"
      git commit -m "refactor(services): migrasi interface & decoupling raw query pada ${file}"
      echo "[SUCCESS] Berhasil memproses: $file" | tee -a "$LOG_FILE"
    else
      echo "[ERROR-TSC] Gagal type check pada $file setelah intervensi Claude." | tee -a "$FAILED_LOG"
      git checkout -- "$file" # Revert perubahan file yang korup
    fi
  else
    echo "[TIMEOUT/FAIL] Claude Code gagal atau timeout pada: $file" | tee -a "$FAILED_LOG"
    git checkout -- "$file" # Revert perubahan
  fi
done

echo "=== Refactoring Selesai. Periksa $LOG_FILE dan $FAILED_LOG ==="
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sebuah platform Core Banking Fintech (`FinPay Global`) memiliki sistem monolitik berbasis TypeScript (950.000 LoC) yang menangani orkestrasi mutasi rekening.
- **Problem**: Layer service secara historis melakukan mutasi database langsung (`knex.raw`) dengan SQL query string, tanpa transaksi idempotency key yang seragam, menyebabkan resiko race condition pada multi-region write.
- **Objective**: Refactoring 480 class service untuk mengimplementasikan *Unit of Work Pattern*, membungkus pemanggilan query ke dalam *IdempotentTransactionalRepository*, dan menerapkan Distributed Tracing via OpenTelemetry spans.

#### Arsitektur Orkestrasi Claude Code:
1. **Dynamic Task Distribution**:
   Sebuah Node.js driver script memetakan dependensi file menggunakan package `dependency-tree`. Mengidentifikasi daun terbawah (*leaf nodes*) dari dependency tree yang tidak memiliki dependensi internal ke service lain.
2. **Context Restriction File (`.claude/refactor-context.md`)**:
   Disediakan kontrak template Unit of Work yang paten. Claude dilarang mengubah file interfaces:
   ```markdown
   # CONTRACT SPECIFICATION:
   Setiap akses database WAJIB melalui:
   `await this.unitOfWork.execute(async (trx) => { ... });`
   Tidak boleh ada instance `knex` langsung diakses di dalam Service.
   ```
3. **Execution Fleet**:
   Dijalankan 4 runner paralel pada instance cloud compute c6i.4xlarge, masing-masing memproses branch worktree terpisah yang diisolasi per domain (Auth, Accounts, Transfers, Settlement).
4. **Hasil**:
   - Total 480 file direfaktor dalam 6 jam eksekusi compute.
   - Manual effort estimate: 12-14 sprint engineer (3 bulan kalender).
   - Realisasi waktu: 2 hari kerja (termasuk validasi QA dan stress testing regression).
   - Defect rate pasca rilis staging: 0.4% (hanya 2 file membutuhkan intervensi manual karena dynamic string interpolation kompleks).

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
           +---------------------------------------+
           |       Trade-off Dimensi Refactor      |
           +---------------------------------------+
                              ▲
                             / \
                            /   \
           Token Cost      /     \    Kecepatan Rilis
          & Rate Limits   /       \   & Automasi Penuh
                         /         \
                        /           \
                       +-------------+
                       Akurasi Semantik
                       & Zero Regression
```

| Parameter | Pendekatan Direct Rewrite (Large Batch) | Pendekatan Chunked Verification (Step-by-Step) | Rekomendasi Enterprise |
| :--- | :--- | :--- | :--- |
| **Token Cost** | Rendah ($0.05 - $0.15/file) karena input prompt dikumpulkan sekaligus. | Tinggi ($0.50 - $1.80/file) karena setiap koreksi compiler mengonsumsi token input baru. | Gunakan **Chunked Verification**. Biaya token minor dibandingkan *cost outage* akibat bug terselubung. |
| **Execution Latency**| Cepat (1-2 menit per 10 file). | Lebih lambat (3-8 menit per file akibat compile-loop). | Eksekusi paralel via `git worktree` multi-core/multi-agent runners. |
| **Scalability** | Buruk; context window cepat saturasi, model mulai melupakan detail awal. | Sangat Tinggi; model beroperasi dengan fresh context per modul target. | Buat batasan scope: 1 batch = 1 module / max 3 interrelated files. |
| **Model Drift** | Sering terjadi halusinasi pada file ke-5 dan seterusnya dalam satu prompt. | Tereliminasi sepenuhnya karena sub-shell agent dibersihkan setiap iterasi. | Jalankan command via `--dangerously-skip-permissions` hanya di sandbox CI/CD. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Memberikan Seluruh Monorepo ke dalam Direct Prompt
- **Gejala**: Claude Code merespons lambat, output terpotong, atau melupakan instruksi khusus di tengah proses (*lost in the middle*).
- **Troubleshooting**: Jangan biarkan Claude membaca root directory secara rekursif tanpa batasan. Definisikan `.claudeignore` yang mengabaikan `node_modules`, `dist`, `vendor`, `.git`, dan folder tes yang tidak relevan. Batasi prompt pada absolute file path tertentu.

#### Kesalahan 2: Hallucinated Import Paths Pasca Refactoring
- **Gejala**: Claude Code berhasil mengubah struktur modul tetapi menghasilkan path import yang salah (misal: `../../domain/user` padahal lokasi ada di `src/core/domain/user`).
- **Solusi**: Wajibkan skrip verifikasi otomatis langsung di dalam prompt:
  ```bash
  claude -p "Refactor Foo.ts. Setelah selesai, jalankan 'npm run build' atau 'tsc --noEmit'. Jika ada error 'Cannot find module', identifikasi lokasi berkas sebenarnya menggunakan find atau glob tool lalu koreksi import statement-nya."
  ```

#### Kesalahan 3: Modifikasi Tak Terduga di Luar Scope (*Scope Creep*)
- **Gejala**: Agen AI mengubah style formatting, mengganti single quote menjadi double quote di 50 berkas lain, atau merevisi komentar copyright.
- **Troubleshooting**: Buat file `CLAUDE.md` di root direktori dengan instruksi pertahanan:
  ```markdown
  ## STRICT REFACTORING BOUNDARIES:
  - DO NOT reformat unedited lines.
  - DO NOT touch files outside the explicit parameters passed in the initial prompt.
  - Maintain the existing prettier/eslint rules.
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist operasional ini sebelum menjalankan batch refactor massal:

- [ ] **Repository Isolation**: Worktree terpisah disiapkan; branch `master`/`main` terkunci dari write access langsung.
- [ ] **Baseline Test Suite Verified**: Seluruh unit & integration test dipastikan passing 100% pada commit HEAD saat ini sebelum Claude Code menyentuh kode.
- [ ] **Linter & Typecheck Fast-Fail**: Tooling static analysis (`tsc`, `mypy`, `cargo check`, `eslint`) dapat dijalankan lokal per berkas dalam sub-detik.
- [ ] **Strict `.claudeignore` In Place**: Memastikan Claude Code tidak mengindeks directory cache, coverage, atau vendor dependencies.
- [ ] **Token Quota & Rate Limit Buffer**: API key yang digunakan memiliki limit spending yang dimonitor (minimum tier 3 atau custom enterprise quota).
- [ ] **Deterministic Git Rollback Hook**: Skrip memiliki trap error POSIX (`trap 'cleanup' ERR INT`) yang otomatis menjalankan `git checkout -- .` jika skrip diinterupsi.
- [ ] **Idempotent Migration Verification**: Setiap migrasi dirancang agar jika Claude Code dijalankan dua kali pada file yang sama, tidak terjadi perubahan kedua (state konvergen).

---

### 12. Hands-on Practice

Latihan terstruktur ini dirancang untuk dieksekusi secara berurutan di dalam folder praktikum:
`hands-on/m02/`

#### Langkah 1: Setup Lingkungan Sandbox
Siapkan workspace simulasi legacy code:

```bash
mkdir -p hands-on/m02/legacy-app/src
cd hands-on/m02/legacy-app

# Inisialisasi npm project
cat << 'EOF' > package.json
{
  "name": "legacy-refactor-lab",
  "version": "1.0.0",
  "scripts": {
    "test": "jest",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "@types/jest": "^29.5.0",
    "@types/node": "^20.0.0",
    "jest": "^29.5.0",
    "ts-jest": "^29.1.0",
    "typescript": "^5.0.0"
  }
}
EOF

# Inisialisasi konfigurasi TypeScript
cat << 'EOF' > tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
EOF

# Inisialisasi konfigurasi Jest
cat << 'EOF' > jest.config.js
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/src/**/*.test.ts'],
};
EOF

# Install dependencies (opsional di sandbox lokal jika ada koneksi, atau pastikan types tersedia)
npm install
git init
git config user.name "Enterprise Architect"
git config user.email "architect@enterprise.internal"
```

#### Langkah 2: Buat Kode Legacy & Unit Test Pengaman
Buat service yang melanggar Clean Architecture (data layer bocor ke domain layer):

**File:** `src/legacyOrderService.ts`
```typescript
// Legacy Order Service: Campuran logika kalkulasi, mutasi database, dan side-effects
export class LegacyOrderService {
  private db: any;

  constructor(dbConnection: any) {
    this.db = dbConnection;
  }

  // Refactor target: Menggunakan any, callback model, dan raw SQL string
  public processOrder(orderData: any, callback: (err: any, res?: any) => void): void {
    if (!orderData.items || orderData.items.length === 0) {
      return callback(new Error("Cart cannot be empty"));
    }

    let total = 0;
    for (let i = 0; i < orderData.items.length; i++) {
      total += orderData.items[i].price * orderData.items[i].quantity;
    }

    if (orderData.discountCode === "DISCOUNT10") {
      total = total * 0.9;
    }

    const query = `INSERT INTO orders (user_id, total, status) VALUES ('${orderData.userId}', ${total}, 'PENDING')`;
    
    this.db.query(query, (err: any, result: any) => {
      if (err) {
        return callback(err);
      }
      return callback(null, { orderId: result.insertId, calculatedTotal: total, status: "PENDING" });
    });
  }
}
```

**File:** `src/legacyOrderService.test.ts`
```typescript
import { LegacyOrderService } from './legacyOrderService';

describe('LegacyOrderService Regression Suite', () => {
  it('harus menghitung total pesanan dengan benar dan menerapkan diskon', (done) => {
    const mockDb = {
      query: (sql: string, cb: Function) => {
        cb(null, { insertId: 999 });
      }
    };

    const service = new LegacyOrderService(mockDb);
    const payload = {
      userId: "usr_123",
      items: [
        { price: 100, quantity: 2 },
        { price: 50, quantity: 1 }
      ],
      discountCode: "DISCOUNT10"
    };

    service.processOrder(payload, (err, res) => {
      expect(err).toBeNull();
      expect(res.calculatedTotal).toBe(225); // (200 + 50) * 0.9 = 225
      expect(res.orderId).toBe(999);
      expect(res.status).toBe("PENDING");
      done();
    });
  });
});
```

Commit base code ke Git:
```bash
git add .
git commit -m "feat(legacy): baseline legacy order service and test harness"
```

#### Langkah 3: Eksekusi Claude Code Migration
Jalankan instruksi refactoring tingkat lanjut via CLI:

```bash
claude -p "Lakukan refactor arsitektural pada src/legacyOrderService.ts:
1. Ganti paradigma callback menjadi async/await murni dengan Promise.
2. Definisikan interface strongly-typed untuk OrderItem, OrderPayload, OrderResult, dan IOrderRepository.
3. Decouple raw database query ke dalam interface IOrderRepository (Dependency Inversion Principle).
4. Update unit test di src/legacyOrderService.test.ts agar sesuai dengan signature async/await baru tanpa merusak skenario verifikasi logikanya.
5. Jalankan 'npm test' dan 'npm run typecheck'. Perbaiki jika ada kegagalan sampai kedua command bernilai exit code 0." \
--dangerously-skip-permissions
```

#### Langkah 4: Verifikasi Status Git & Validasi
Setelah Claude Code selesai bekerja:

```bash
# Verifikasi status pengujian
npm test
npm run typecheck

# Analisis diff perubahan
git diff

# Commit hasil kerja otomatis
git add src/
git commit -m "refactor(order): decouple database access and modernize to async/await"
```

---

### 13. Exercise

#### Level 1 - Easy (Perbaikan Interface & Null-Safety)
- **Problem**: Anda memiliki berkas legacy TypeScript `src/userMapper.ts` yang memetakan response API mentah ke format profil pengguna internal. Saat ini 80% propertinya menggunakan nullable casting tak terkendali (`val as any`).
- **Tugas**: Gunakan Claude Code CLI untuk mendefinisikan validasi runtime menggunakan library skema (atau pure type guards) dan hilangkan semua type casting `any`.
- **Kriteria Keberhasilan**: Script `npm run typecheck` menghasilkan 0 error dengan compiler flag `strict: true`.

#### Level 2 - Medium (De-coupling Monolithic Controller)
- **Problem**: File `src/controllers/paymentController.ts` sepanjang 800 baris mengandung logika orkestrasi HTTP, integrasi Stripe SDK, persistensi PostgreSQL, dan pengiriman notifikasi email SMTP langsung dalam 1 method handler.
- **Tugas**: Instruksikan Claude Code untuk mendekomposisi controller ini menjadi 3 sub-modul terpisah: `PaymentController` (hanya HTTP parsing & response formatting), `PaymentService` (business logic), dan `NotificationService` (email side effect).
- **Kriteria Keberhasilan**: Tidak ada modul yang melanggar batas tanggung jawab (*Single Responsibility Principle*), dan seluruh unit test lama yang di-mock tetap passing.

#### Level 3 - Hard (Multi-File State Machine Migration)
- **Problem**: Sebuah sistem state machine handling reservasi tiket bioskop terdistribusi di 6 file (`BookingWorkflow.ts`, `SeatHoldManager.ts`, `PaymentGatewayBridge.ts`, `TicketIssuer.ts`, `AuditLog.ts`, `Index.ts`). Seluruh state transition saat ini disimpan dalam mutable in-memory variables yang tidak thread-safe.
- **Tugas**: Buat skrip Bash orkestrator yang mengarahkan Claude Code untuk memigrasikan status transition di ke-6 file tersebut agar mengimplementasikan Redis-backed Redlock pattern secara atomik.
- **Kriteria Keberhasilan**: Seluruh proses diselesaikan secara headless (`-p`), kompilasi sukses, dan integrasi test simulasi concurrent race-condition berhasil dilewati tanpa deadlock.

---

### 14. Challenge

#### Skenario: "The Zero-Downtime Microservice Decoupling"
Anda adalah Chief Architect di sebuah platform e-commerce Tier-1. Codebase monolitik Node.js/TypeScript memiliki modul `InventorySyncEngine` yang diakses oleh 72 berkas servis lainnya.
Komponen ini harus dipisahkan menjadi standalone client library yang berkomunikasi melalui gRPC, bukan lagi in-process function call lokal.

**Detail Kondisi Lapangan:**
1. Anda dilarang mengubah logic consumer yang memanggil inventory secara simultan dalam 1 commit besar.
2. Anda harus membuat **Strangler Fig Facade Pattern**: `InventorySyncEngine` dipertahankan signature-nya, tetapi internal implementasinya dialihkan untuk mengecek feature flag. Jika active, ia memanggil gRPC client stub; jika inactive, memanggil legacy SQL query.
3. Claude Code harus melakukan migrasi ini terhadap 72 berkas consumer untuk memastikan konteks tracing (`traceparent` HTTP/W3C header) diteruskan ke invocation `InventorySyncEngine`.

**Tantangan Eksekusi:**
- Buat file orkestrator Bash/Node.js lengkap yang menggunakan Claude Code CLI untuk memigrasi monorepo tersebut.
- Implementasikan mekanisme *checkpointing* otomatis: Jika di tengah pemrosesan 72 berkas terjadi kegagalan typecheck pada berkas ke-37, runner harus melakukan *rollback atomik* pada batch tersebut, menandai (*flag*) berkas ke dalam log JSON, dan melanjutkan pemrosesan sisa berkas lain tanpa *human intervention*.
- Total eksekusi tidak boleh menguras lebih dari $10 API credit budget.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Basic (Pilihan Ganda)

1. **Apa fungsi dari parameter flag `-p` (`--print`) pada Claude Code CLI?**
   - A. Menghasilkan visualisasi diagram arsitektur ke layar terminal.
   - B. Menjalankan Claude Code dalam mode *headless/non-interactive* untuk pipeline automasi dan mencetak respons langsung.
   - C. Mencetak riwayat token yang sudah dikonsumsi selama sesi berjalan.
   - D. Menjalankan skrip dalam mode simulasi (*dry-run*) tanpa memodifikasi berkas apapun.

2. **Mengapa penggunaan tool internal `Edit` lebih diutamakan daripada menimpa keseluruhan file menggunakan write tool standar pada file besar?**
   - A. Karena tool `Edit` menggunakan regex global tanpa verifikasi teks.
   - B. Menulis ulang seluruh file rentan terhadap pemotongan (*truncation*) output token LLM dan mengaburkan git history.
   - C. Tool `Edit` tidak membutuhkan izin akses file sistem operasi.
   - D. Claude Code tidak memiliki kemampuan untuk membuat berkas dari awal.

3. **Berkas standar apa yang dibaca Claude Code secara otomatis di direktori kerja untuk memahami konvensi dan batasan proyek?**
   - A. `.claude_rules.json`
   - B. `AI_PROMPT.yaml`
   - C. `CLAUDE.md`
   - D. `.anthropic/system.env`

4. **Bagaimana cara mencegah Claude Code menyentuh folder sensitif atau directory vendor seperti `node_modules` atau `.venv`?**
   - A. Menghapus folder tersebut sebelum menjalankan perintah refactoring.
   - B. Mengonfigurasi file `.claudeignore` di root repositori.
   - C. Menggunakan flag `--exclude-all-modules` saat pemanggilan CLI.
   - D. Claude Code secara default tidak dapat mengakses direktori lokal selain `src/`.

5. **Apa dampak negatif utama dari menaikkan batas batching file terlalu besar (misal 50 file sekaligus) dalam satu prompt refactor?**
   - A. Biaya komputasi linter lokal menjadi nol.
   - B. API Anthropic akan otomatis menolak request dengan status HTTP 400.
   - C. Terjadinya halusinasi referensi, file truncation, dan degradasi akurasi semantik (*needle-in-a-haystack issue*).
   - D. Git commit hash akan menjadi korup.

---

#### Bagian B: Pertanyaan Intermediate (Pilihan Ganda)

6. **Dalam orkestrasi arsitektur refactoring massal, apa tujuan utama penggunaan `git worktree` dibandingkan bekerja langsung pada clone direktori utama?**
   - A. Mempercepat koneksi network API ke server Anthropic.
   - B. Mengisolasi mutasi kode pada commit pointer terpisah tanpa mengganggu developer lain yang aktif pada branch utama, serta memungkinkan eksekusi multi-agent paralel di direktori lokal berbeda.
   - C. Menghilangkan kebutuhan untuk menjalankan unit test lokal.
   - D. Mengubah compiler target menjadi binary machine code secara langsung.

7. **Ketika Claude Code mengalami error kompilasi TypeScript setelah menerapkan patch, mekanisme apa yang harus diintegrasikan dalam prompt orchestration untuk *self-healing*?**
   - A. Hentikan eksekusi skrip Bash dan kirimkan email peringatan ke DevOps team.
   - B. Langsung jalankan `git checkout --force` untuk membatalkan seluruh repositori.
   - C. Berikan prompt balik yang menyertakan output `stderr` kompilator dan instruksikan agen menganalisis diagnostic code serta mengedit kembali line terkait.
   - D. Matikan opsi `strict: true` di file `tsconfig.json` agar kompilasi dipaksa sukses.

8. **Untuk meminimalkan konsumsi token input/output saat melakukan rename API method lintas modul, pendekatan scoping apa yang paling efisien?**
   - A. Memberikan seluruh isi repositori sebagai context.
   - B. Menjalankan `grep` / `ast-grep` terlebih dahulu untuk menyaring file target spesifik, lalu hanya mengirimkan daftar file target tersebut ke session Claude Code.
   - C. Meminta Claude Code menebak di mana method tersebut digunakan tanpa membaca file.
   - D. Melakukan zip terhadap folder project dan menguploadnya via API binary format.

9. **Parameter apa yang wajib ditambahkan pada eksekusi headless CLI di CI/CD runner agar agen tidak berhenti meminta konfirmasi persetujuan tool-call manual?**
   - A. `--auto-approve-silent`
   - B. `--dangerously-skip-permissions`
   - C. `--allow-all-exec-bash`
   - D. `--force-override-terminal`

10. **Bagaimana cara terbaik menjaga agar Claude Code tidak merusak arsitektur Hexagonal/Clean Architecture saat mengekstrak business logic?**
    - A. Menyediakan *few-shot examples* dan *negative constraints* di dalam `CLAUDE.md` yang melarang ketergantungan layer domain terhadap layer infrastructure.
    - B. Mengandalkan linter standard ESLint tanpa rule tambahan.
    - C. Menghapus layer domain dari project structure.
    - D. Menjalankan model pada temperatur 1.0 agar agen berkreasi mencari pattern baru.

---

#### Bagian C: Skenario Kasus Produksi (Analisis & Essay Singkat)

11. **Skenario Kasus 1: Failure Recovery pada Pipeline CI**
    Pipeline refactor otomatis migrasi ORM dijalankan di GitLab Runner menggunakan Claude Code. Di tengah proses (file 85 dari 200), runner kehabisan memori (OOM) dan mati mendadak, meninggalkan working directory dalam status *uncommitted partial changes*.
    *Pertanyaan*: Rancang strategi *recovery & state persistence* agar ketika pipeline dijalankan ulang, proses tidak mengulang dari file ke-1 dan tidak merusak integritas Git history.

12. **Skenario Kasus 2: Cyclic Dependency Pasca Ekstraksi Interface**
    Setelah Claude Code melakukan ekstraksi interface secara massal pada 30 domain models, compiler melaporkan adanya *Circular Dependency Error* antara `UserEntity -> OrderEntity -> InvoiceEntity -> UserEntity`.
    *Pertanyaan*: Bagaimana Anda memformulasikan prompt instruksi spesifik kepada Claude Code untuk menyelesaikan dependency cycle tersebut dengan teknik arsitektural yang valid (misal: *Mediator pattern* atau *Interface segregation*)?

13. **Skenario Kasus 3: Mitigasi Latensi & Token Budget Burnout**
    Sebuah monorepo perbankan memiliki 5.000 file. Estimasi refactoring menyeluruh berpotensi menelan 150 juta token jika tidak diatur.
    *Pertanyaan*: Uraikan blueprint arsitektur modular yang mempartisi repositori menjadi *bounded context cluster* dan tentukan matriks kriteria untuk menghentikan (*circuit breaker*) eksekusi Claude Code jika rasio keberhasilan compile per batch berada di bawah threshold tertentu.

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Bagian A:
1. **B** — Flag `-p` / `--print` mematikan terminal UI interaktif dan menjalankan agen dalam mode headless streaming, krusial untuk scriptability.
2. **B** — Truncation token output (terbatas pada 8k token pada Claude 3.5 Sonnet) dapat memotong berkas besar jika ditulis ulang secara utuh. Tool `Edit` melakukan text replacement lokal yang aman.
3. **C** — `CLAUDE.md` adalah file konfigurasi standar instruksi proyek yang dibaca oleh Claude Code.
4. **B** — `.claudeignore` adalah mekanisme resmi untuk mencegah agen membaca/mengindeks direktori tertentu.
5. **C** — Context window yang dipenuhi terlalu banyak file yang tidak relevan menurunkan perhatian semantik (*attention degradation*) LLM.

#### Kunci Bagian B:
6. **B** — `git worktree` memberikan filesystem directory nyata yang terisolasi dari branch kerja aktif, memungkinkan isolasi proses agen secara murni.
7. **C** — Memberikan feedback stack trace secara langsung ke prompt agen menutup loop *observation-action-verification* yang membuat sistem bersifat self-healing.
8. **B** — AST/Grep-assisted scoping memotong token input hingga lebih dari 90% karena Claude Code hanya mengonsumsi context yang relevan.
9. **B** — Flag `--dangerously-skip-permissions` membypass prompt konfirmasi y/n pada tool use; wajib di sandbox CI/CD yang terisolasi.
10. **A** — `CLAUDE.md` berfungsi sebagai static system memory yang mempertahankan *architectural invariants* lintas interaksi agen.

#### Panduan Jawaban Bagian C (Kasus Produksi):
11. **Skenario 1**:
    - *Solusi*: Simpan metadata checkpointing pada persistent external store (misal: file `.refactor-progress.json` atau SQLite state database yang di-cache di CI artifact/S3).
    - Pada awal skrip orchestrator:
      1. Baca status file yang sudah sukses dari branch commit (menggunakan tag commit `refactor-batch-*`).
      2. Jalankan `git reset --hard` ke commit terakhir yang valid untuk membersihkan sisa OOM uncommitted artifacts.
      3. Filter out file-file yang SHA-nya sudah tercatat sukses pada commit log.
      4. Lanjutkan batch berikutnya.
12. **Skenario 2**:
    - *Solusi Prompt Arsitektural*:
      1. Arahkan Claude untuk memetakan ketergantungan circular menggunakan tool AST.
      2. Terapkan *Interface Segregation Principle* (ISP): Pisahkan `UserEntity` menjadi `IUserIdentity` (hanya id & auth) dan `IUserProfile` (data detail).
      3. Pindahkan contract referensi silang ke namespace/package `types/contracts/` terisolasi yang tidak memiliki dependency balik ke layer implementasi domain.
      4. Eksekusi `npx madge --circular src/` untuk memverifikasi hilangnya cycle.
13. **Skenario 3**:
    - *Solusi*:
      1. **Clustering**: Kelompokkan 5.000 file menjadi sub-grafik dependensi menggunakan tool analisis dependensi (misal: `dependency-cruiser`). Dapatkan independent clusters.
      2. **Token Optimization**: Gunakan compact diff representation dan batasi output compiler hanya pada baris error via filtering `grep -E "error TS"`.
      3. **Circuit Breaker Policy**: Jika dalam 5 batch berturut-turut rasio compile failure setelah self-healing melebihi 20%, picu kill switch: hentikan eksekusi, revert branch ke checkpoint terakhir, kirim status alert ke Slack/PagerDuty, dan eksport snapshot debug log.

---

### 16. Summary

Refactoring skala enterprise dengan Claude Code merevolusi cara industri menangani *technical debt* dan modernisasi arsitektur monolitik. Kunci keberhasilan dari implementasi ini tidak bertumpu pada "keajaiban prompt tunggal", melainkan pada **disiplin rekayasa sistem di sekitar agen**:
1. **Isolasi Lingkungan**: Memanfaatkan `git worktree` untuk menciptakan ruang kerja mutasi kode yang terlindungi.
2. **Kompensasi Batasan Token**: Menerapkan parsing dependency graph secara bottom-up untuk menyuplai context yang ramping dan terarah.
3. **Automated Verification Loop**: Mengombinasikan compiler feedback, static analysis, dan regression test runner langsung di dalam siklus eksekusi agen (*self-healing loop*).
4. **Governed Automation**: Mengunci batasan arsitektur secara deterministik via `CLAUDE.md` dan `.claudeignore` guna menjamin modifikasi kode tetap konvergen, aman, dan dapat diaudit secara enterprise-grade.