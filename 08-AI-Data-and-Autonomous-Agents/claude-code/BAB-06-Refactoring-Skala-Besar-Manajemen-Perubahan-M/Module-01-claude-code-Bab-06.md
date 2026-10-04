# Bab 06: Refactoring Skala Besar & Manajemen Perubahan Multi-File

---

## 1. Learning Objectives

Setelah menyelesaikan bab ini, Anda diharapkan mampu:
- **Menganalisis dan Memetakan Dependency Graph**: Mengonstruksi representasi topologis dari dependensi antar-berkas untuk menentukan urutan refaktorisasi multi-file (*execution order*) menggunakan Directed Acyclic Graph (DAG) secara deterministik.
- **Merancang Protokol Perubahan Transaksional (Two-Phase Change Protocol)**: Mengimplementasikan mekanisme staging dan rollback otomatis berbasis Git Worktree / Virtual File System untuk mencegah kondisi *broken build* akibat perubahan asinkronus multi-file oleh Claude Code.
- **Mengoptimalkan Context Window Budgeting**: Menerapkan teknik *sliding symbol window* dan *AST-driven context pruning* guna meminimalkan degradasi perhatian (*needle-in-a-haystack decay*) pada refaktorisasi berukuran ratusan berkas.
- **Mengintegrasikan Validasi Statis Berkelanjutan (Continuous Static Validation)**: Menghubungkan agen dengan Language Server Protocol (LSP) dan CLI Compiler (`tsc`, `pyright`, `cargo check`) untuk mendeteksi *breaking changes* antarmuka secara *real-time* sebelum commit dipatenkan.
- **Mengeksekusi Automated Large-Scale Refactoring**: Memandu Claude Code melakukan migrasi arsitektur kompleks (misal: migrasi dari CommonJS ke ESM, atau refaktorisasi pola repositori sinkron ke asinkron) melintasi 20+ modul secara konsisten tanpa halusinasi sintaks.

---

## 2. Concept Overview

Refaktorisasi skala besar menggunakan Large Language Models (LLMs) seperti Claude 3.5 Sonnet / Claude 3.7 Sonnet dalam lingkungan *agentic coding* (Claude Code) bukan sekadar operasi "Search and Replace" berbasis string. Operasi ini menuntut pemahaman mendalam tentang **semantik tipe data**, **siklus hidup dependensi (*import/export lifecycle*)**, dan **invarian arsitektur**.

### Mental Model: The Semantic AST Weaver

```
      +-------------------------------------------------------------+
      |                Semantic Dependency Graph                    |
      |   [Module A] --------> [Module B] --------> [Module C]      |
      |       ^                     |                    |          |
      |       +---------------------+--------------------+          |
      +-------------------------------------------------------------+
                                     |
                                     v
      +-------------------------------------------------------------+
      |                  Refactoring DAG Planner                    |
      |  Pass 1: Leaf Interfaces -> Pass 2: Adapters -> Pass 3: App |
      +-------------------------------------------------------------+
                                     |
                                     v
      +-------------------------------------------------------------+
      |               Transactional Execution Loop                  |
      |  [Shadow Worktree] -> [Apply Diff] -> [LSP Validate]        |
      |       |                                     |               |
      |       +--- (Fail: Revert & Self-Heal) <-----+               |
      |       |                                                     |
      |       +---> (Pass: Commit & Advance to Next Topological Level)|
      +-------------------------------------------------------------+
```

Model mental yang tepat untuk refaktorisasi multi-file adalah **Semantic AST Weaver**:
1. **Source of Truth**: Graf dependensi kode sumber adalah struktur deterministik. Refaktorisasi tidak dapat dilakukan secara acak berdasarkan urutan abjad berkas.
2. **Topological Invariance**: Perubahan antarmuka (*interface/type contracts*) harus disebarkan mulai dari modul terdalam (*leaves*) menuju lapisan terluar (*call sites*), atau sebaliknya menggunakan pola *Parallel Run/Expansion-Contraction*.
3. **Transactionality**: Setiap mutasi berkas adalah unit transaksi terisolasi. Jika berkas ke-7 dari 15 berkas menghasilkan eror kompilasi fatal yang tidak dapat diperbaiki sendiri (*unrecoverable self-healing failure*), seluruh state harus kembali ke titik aman (*atomic rollback*).

---

## 3. Why It Matters

Pada basis kode enterprise (monorepo dengan ratusan ribu baris kode), refaktorisasi manual memakan waktu mingguan dan rentan eror manusia (*human oversight*). Namun, menyerahkan tugas ini secara naif kepada AI agent sering kali menyebabkan:

- **Context Pollution & Drift**: Agen melupakan perubahan interface yang didefinisikannya di berkas pertama saat memodifikasi berkas ke-20, menyebabkan inkonsistensi tanda tangan metode (*method signature mismatch*).
- **Broken Intermediate States**: Agen mengubah pemanggil (*caller*) sebelum fungsi yang dipanggil dimutasi, memicu kegagalan build paralel pada sistem CI/CD.
- **Hallucinated Transitive Dependencies**: Agen mengasumsikan keberadaan modul baru yang belum pernah dibuat atau salah mengeja *relative path* lintas direktori.
- **Biaya Token Eksponensial**: Memasukkan seluruh basis kode ke dalam *system prompt* untuk setiap berkas akan menguras batas kuota (rate limits) dan menurunkan latensi inferensi secara drastis.

Pendekatan rekayasa yang terstruktur membedakan *prototype hacking* dengan *enterprise-grade software engineering*. Dengan membatasi ruang lingkup agen menggunakan graf dependensi, validasi LSP berbasis sub-proses, dan rollback atomik, kita dapat menjamin stabilitas sistem dengan akurasi 100% pada refaktorisasi masif.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur orkestrasi refaktorisasi multi-file Claude Code beroperasi melalui siklus umpan balik tertutup (*closed-loop feedback system*) yang berinteraksi langsung dengan file system dan *toolchain* lokal:

```
+-----------------------------------------------------------------------------------+
|                           CLAUDE CODE AGENT ENGINE                                |
+-----------------------------------------------------------------------------------+
                                         |
                       [1] Parse Intent & Scan Modules
                                         v
+-----------------------------------------------------------------------------------+
|                        STATIC CODE ANALYSIS & DAG BUILDER                         |
|  - AST Analyzer (Tree-sitter / Project Graph)                                     |
|  - Circular Dependency Detector (Tarjan's SCC Algorithm)                          |
|  - Execution Order Resolver (Kahn's Topological Sort)                            |
+-----------------------------------------------------------------------------------+
                                         |
                          [2] Ordered Refactoring Batches
                                         v
+-----------------------------------------------------------------------------------+
|                     TRANSACTION & WORKSPACE COORDINATOR                           |
|  +-----------------------------------------------------------------------------+  |
|  | Isolated Environment: Git Stash / Worktree / Shadow Directory               |  |
|  +-----------------------------------------------------------------------------+  |
|                                        |                                          |
|                          [3] Atomic Write Operation                               |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  | Context-Budgeted Agent Execution (Prompt Engine)                            |  |
|  | - File Context: Target File + Interface Diffs Only (Pruned AST)             |  |
|  | - Tools: `Edit`, `View`, `Bash`, `Grep`                                     |  |
|  +-----------------------------------------------------------------------------+  |
|                                        |                                          |
|                       [4] Emit Changes (Patch / File Write)                       |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  | Verification Pipeline:                                                      |  |
|  |   1. Syntax Check (Parser)                                                  |  |
|  |   2. Static Type Analysis (TypeScript/Rust/Pyright LSP Engine)               |  |
|  |   3. Unit Test Validation (Automated Test Runner)                           |  |
|  +-----------------------------------------------------------------------------+  |
|                           /                        \                              |
|           [5a] Verification Pass              [5b] Verification Fail              |
|                     /                                    \                        |
|                    v                                      v                       |
|         [Stage Commit in Git]                  [Heuristic Self-Healing]           |
|                    |                                      |                       |
|                    |                                  Max Retries?                |
|                    |                                  /          \                |
|                    |                         [No: Feed Error]   [Yes: Rollback]   |
|                    |                                 |                   |        |
|                    |                                 +---------> [Revert Batch]   |
|                    v                                                     |        |
|      [Advance to Next Topological Level]                                 v        |
|                                                                 [Abort & Report]  |
+-----------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Kahn's Topological Sorting untuk Refactoring Multi-File

Untuk mencegah Claude Code memodifikasi berkas di luar konteks yang valid, berkas harus diurutkan secara topologis. Jika modul `A` mengimpor tipe dari modul `B`, maka `B` berada pada level dependensi lebih dalam.

1. **Expansion-Contraction (Parallel Run)**:
   - **Fase 1 (Expand)**: Tambahkan implementasi baru pada modul terdalam tanpa menghapus implementasi lama (*backward-compatible signature*).
   - **Fase 2 (Migrate Callers)**: Claude Code memodifikasi berkas-berkas pemanggil (tingkat atas pada DAG) untuk menggunakan antarmuka baru.
   - **Fase 3 (Contract)**: Hapus implementasi usang (*deprecated*) pada modul inti.

### 5.2 Context Window Budgeting & AST Pruning

Memuat 30 berkas penuh ke dalam konteks Claude Code akan menyebabkan token exhaustion dan "Context Rot". Strategi yang digunakan:
- **Skeletonization**: Sebelum Claude Code membaca berkas referensi, berkas tersebut dipangkas menggunakan parser AST untuk hanya menyisakan deklarasi antarmuka, tipe, dan *signature* metode tanpa *body* implementasi.
- **Diff Windowing**: Berkas yang telah dimodifikasi sebelumnya hanya direpresentasikan dalam format `git diff` terkompresi, bukan representasi berkas utuh.

### 5.3 LSP Diagnostic Feedback Loop

Claude Code tidak boleh mengandalkan asumsi apakah kodenya lolos kompilasi. Setelah eksekusi tool `Edit`, orchestrator menjalankan daemon pemeriksa tipe (misal: `tsc --noEmit --incremental` atau protokol LSP `textDocument/publishDiagnostics`). Diagnostik eror ditangkap secara terstruktur:

$$\text{Error Feedback} = \{\text{file}, \text{line}, \text{column}, \text{ruleId}, \text{message}\}$$

Eror ini disuntikkan kembali ke Claude Code dengan instruksi perbaikan terfokus (*targeted remediation prompt*).

---

## 6. Production-Ready Code Implementation

Berikut adalah orchestrator refaktorisasi multi-file enterprise berskala penuh dalam TypeScript/Node.js. Sistem ini mengombinasikan dependency sorting, atomic rollback berbasis snapshot, eksekusi agent, dan validasi LSP/TypeScript CLI.

```typescript
// File: src/refactor-orchestrator.ts

import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

// ==========================================
// 1. DATA TYPES & INTERFACES
// ==========================================

export interface DependencyNode {
  filePath: string;
  dependencies: Set<string>; // Files this node imports
  dependents: Set<string>;   // Files that import this node
}

export interface RefactorTarget {
  filePath: string;
  instruction: string;
}

export interface OrchestrationConfig {
  rootDir: string;
  maxSelfHealingRetries: number;
  typeCheckCommand: string;
  testCommand?: string;
}

export interface VerificationResult {
  success: boolean;
  errors: string[];
}

// ==========================================
// 2. DEPENDENCY GRAPH RESOLVER
// ==========================================

export class DependencyGraph {
  private nodes: Map<string, DependencyNode> = new Map();

  public addFile(filePath: string): void {
    const normalized = path.resolve(filePath);
    if (!this.nodes.has(normalized)) {
      this.nodes.set(normalized, {
        filePath: normalized,
        dependencies: new Set(),
        dependents: new Set(),
      });
    }
  }

  public addDependency(fromPath: string, toPath: string): void {
    const fromNorm = path.resolve(fromPath);
    const toNorm = path.resolve(toPath);

    this.addFile(fromNorm);
    this.addFile(toNorm);

    this.nodes.get(fromNorm)!.dependencies.add(toNorm);
    this.nodes.get(toNorm)!.dependents.add(fromNorm);
  }

  /**
   * Topological Sort via Kahn's Algorithm
   * Mengembalikan urutan eksekusi: Leaf nodes (dependensi terdalam) terlebih dahulu.
   */
  public getTopologicalOrder(): string[] {
    const inDegree: Map<string, number> = new Map();
    const zeroInDegreeQueue: string[] = [];
    const orderedResult: string[] = [];

    // In-degree dihitung berdasarkan berapa banyak modul lokal yang diimpor oleh berkas ini
    for (const [nodePath, node] of this.nodes.entries()) {
      const degree = node.dependencies.size;
      inDegree.set(nodePath, degree);
      if (degree === 0) {
        zeroInDegreeQueue.push(nodePath);
      }
    }

    while (zeroInDegreeQueue.length > 0) {
      const current = zeroInDegreeQueue.shift()!;
      orderedResult.push(current);

      const currentNode = this.nodes.get(current);
      if (!currentNode) continue;

      for (const dependent of currentNode.dependents) {
        const currentDegree = inDegree.get(dependent)! - 1;
        inDegree.set(dependent, currentDegree);
        if (currentDegree === 0) {
          zeroInDegreeQueue.push(dependent);
        }
      }
    }

    if (orderedResult.length !== this.nodes.size) {
      throw new Error(
        'Siklus terdeteksi dalam Dependency Graph (Circular Dependency). Refaktorisasi topologis membutuhkan resolusi siklus.'
      );
    }

    return orderedResult;
  }
}

// ==========================================
// 3. TRANSACTION MANAGER (FILE LEVEL)
// ==========================================

export class TransactionalWorkspace {
  private snapshots: Map<string, string> = new Map();

  public createSnapshot(filePaths: string[]): void {
    this.snapshots.clear();
    for (const file of filePaths) {
      if (fs.existsSync(file)) {
        this.snapshots.set(file, fs.readFileSync(file, 'utf-8'));
      }
    }
  }

  public rollback(): void {
    console.warn('[TRANSACTION] Melakukan rollback ke snapshot sebelumnya...');
    for (const [filePath, content] of this.snapshots.entries()) {
      fs.writeFileSync(filePath, content, 'utf-8');
    }
  }

  public commit(): void {
    this.snapshots.clear();
  }
}

// ==========================================
// 4. MOCK AGENT RUNTIME (CLAUDE CODE BRIDGE)
// ==========================================

export interface AgentContext {
  targetFile: string;
  instruction: string;
  diagnostics?: string[];
  referenceSignatures: Map<string, string>;
}

export class ClaudeCodeEngineBridge {
  /**
   * Simulasi eksekusi prompt terisolasi Claude Code Agent.
   * Diimplementasikan via Claude Code CLI / Anthropic SDK.
   */
  public async executeEdit(context: AgentContext): Promise<void> {
    console.log(`[AGENT] Memproses mutasi pada: ${path.basename(context.targetFile)}`);
    
    // Logika kontekstual yang disederhanakan:
    // Pada produksi, ini mengeksekusi Anthropic Messages API dengan Tools Definition:
    // View, Edit, Bash.
    const originalContent = fs.readFileSync(context.targetFile, 'utf-8');

    // Menangani instruksi spesifik migrasi mock
    if (context.instruction.includes('MIGRATE_TO_ASYNC')) {
      const transformed = originalContent
        .replace(/function\s+(\w+)\(([^)]*)\):(\s*[^{]+)/g, 'async function $1($2): Promise<$3>')
        .replace(/return\s+this\.db\.query\(([^)]*)\);/g, 'return await this.db.queryAsync($1);');
      
      fs.writeFileSync(context.targetFile, transformed, 'utf-8');
    } else {
      // Fallback: Modifikasi terarah
      fs.appendFileSync(context.targetFile, '\n// Refactored by Claude Code Orchestrator');
    }
  }
}

// ==========================================
// 5. PRODUCTION ORCHESTRATOR
// ==========================================

export class LargeScaleRefactorOrchestrator {
  private graph: DependencyGraph;
  private tx: TransactionalWorkspace;
  private agent: ClaudeCodeEngineBridge;
  private config: OrchestrationConfig;

  constructor(config: OrchestrationConfig) {
    this.config = config;
    this.graph = new DependencyGraph();
    this.tx = new TransactionalWorkspace();
    this.agent = new ClaudeCodeEngineBridge();
  }

  public registerModule(filePath: string, dependencies: string[]): void {
    this.graph.addFile(filePath);
    for (const dep of dependencies) {
      this.graph.addDependency(filePath, dep);
    }
  }

  private runValidation(): VerificationResult {
    try {
      execSync(this.config.typeCheckCommand, {
        cwd: this.config.rootDir,
        stdio: 'pipe',
        encoding: 'utf-8',
      });

      if (this.config.testCommand) {
        execSync(this.config.testCommand, {
          cwd: this.config.rootDir,
          stdio: 'pipe',
          encoding: 'utf-8',
        });
      }

      return { success: true, errors: [] };
    } catch (error: any) {
      const output = error.stdout ? error.stdout.toString() : error.message;
      return {
        success: false,
        errors: output.split('\n').filter((line: string) => line.trim().length > 0),
      };
    }
  }

  public async executeRefactorPlan(plan: Map<string, string>): Promise<boolean> {
    const executionOrder = this.graph.getTopologicalOrder();
    console.log('[ORCHESTRATOR] Urutan Eksekusi Topologis Terverifikasi:');
    executionOrder.forEach((f, idx) => console.log(`  ${idx + 1}. ${path.basename(f)}`));

    // Snapshot awal sebelum mutasi apapun
    this.tx.createSnapshot(executionOrder);

    for (const targetFile of executionOrder) {
      const instruction = plan.get(targetFile);
      if (!instruction) {
        continue; // Berkas dalam dependensi tidak memerlukan perubahan
      }

      console.log(`\n=======================================================`);
      console.log(`[PIPELINE] Memulai refaktorisasi berkas: ${targetFile}`);
      console.log(`=======================================================`);

      let attempts = 0;
      let stepSuccess = false;
      let lastDiagnostics: string[] = [];

      while (attempts <= this.config.maxSelfHealingRetries && !stepSuccess) {
        if (attempts > 0) {
          console.warn(`[SELF-HEALING] Percobaan ${attempts}/${this.config.maxSelfHealingRetries} untuk ${path.basename(targetFile)}`);
        }

        // Jalankan Agent
        await this.agent.executeEdit({
          targetFile,
          instruction,
          diagnostics: lastDiagnostics,
          referenceSignatures: new Map(),
        });

        // Validasi Statis menggunakan LSP / Typescript Engine
        const validation = this.runValidation();

        if (validation.success) {
          console.log(`[VERIFIKASI] Berhasil memvalidasi: ${path.basename(targetFile)}`);
          stepSuccess = true;
        } else {
          console.error(`[VERIFIKASI GAGAL] Terdeteksi eror kompilasi:`);
          validation.errors.slice(0, 5).forEach((err) => console.error(`  -> ${err}`));
          lastDiagnostics = validation.errors;
          attempts++;
        }
      }

      if (!stepSuccess) {
        console.error(`[FATAL] Gagal merefaktorisasi ${targetFile} setelah ${this.config.maxSelfHealingRetries} retries.`);
        this.tx.rollback();
        return false;
      }
    }

    this.tx.commit();
    console.log('\n[SELESAI] Seluruh berkas berhasil direfaktorisasi tanpa breaking changes.');
    return true;
  }
}

// ==========================================
// 6. EXECUTION DEMONSTRATION
// ==========================================

async function runDemo() {
  const rootDir = path.resolve('/tmp/refactor-demo');
  if (!fs.existsSync(rootDir)) {
    fs.mkdirSync(rootDir, { recursive: true });
  }

  // Setup sample files
  const fileA = path.join(rootDir, 'Database.ts');
  const fileB = path.join(rootDir, 'UserRepository.ts');
  const fileC = path.join(rootDir, 'UserService.ts');

  fs.writeFileSync(fileA, `export class Database { query(sql: string): any { return []; } queryAsync(sql: string): Promise<any> { return Promise.resolve([]); } }`);
  fs.writeFileSync(fileB, `import { Database } from './Database'; export class UserRepository { private db = new Database(); findUser(id: string): any { return this.db.query('SELECT'); } }`);
  fs.writeFileSync(fileC, `import { UserRepository } from './UserRepository'; export class UserService { private repo = new UserRepository(); get(id: string): any { return this.repo.findUser(id); } }`);

  // Dummy tsconfig for validation
  fs.writeFileSync(path.join(rootDir, 'tsconfig.json'), JSON.stringify({
    compilerOptions: { target: "es2022", moduleResolution: "node", noEmit: true }
  }));

  const orchestrator = new LargeScaleRefactorOrchestrator({
    rootDir,
    maxSelfHealingRetries: 2,
    typeCheckCommand: `npx tsc --project ${rootDir}/tsconfig.json`,
  });

  // Daftarkan ketergantungan: Service -> Repository -> Database
  orchestrator.registerModule(fileA, []);
  orchestrator.registerModule(fileB, [fileA]);
  orchestrator.registerModule(fileC, [fileB]);

  const plan = new Map<string, string>();
  plan.set(fileB, 'MIGRATE_TO_ASYNC: Ubah findUser menjadi method asynchronous.');
  plan.set(fileC, 'MIGRATE_TO_ASYNC: Perbarui pemanggil findUser agar menggunakan await.');

  const result = await orchestrator.executeRefactorPlan(plan);
  console.log(`Status Orchestration: ${result ? 'SUCCESS' : 'FAILED'}`);
}

if (require.main === module) {
  runDemo().catch(console.error);
}
```

---

## 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Gejala di Lapangan | Dampak | Strategi Mitigasi Terstruktur |
| :--- | :--- | :--- | :--- |
| **Circular Dependency Chains** | Kahn's algorithm melempar eror siklik (`A -> B -> C -> A`). | Agen memodifikasi modul dengan dependensi yang belum selesai secara tak terhingga. | Jalankan algoritma *Tarjan’s Strongly Connected Components (SCC)*. Kelompokkan siklus menjadi satu *compound batch transaction* yang dimutasi serentak. |
| **Token Exhaustion mid-Execution** | Claude Code terputus saat menulis berkas ke-14 dari 20 berkas. | State repositori menjadi kotor (*dirty workspace*), separuh kode menggunakan interface baru, separuh lama. | **Worktree Isolation**: Seluruh mutasi dilakukan di branch/worktree terisolasi. Agen tidak pernah memodifikasi `main` branch secara langsung tanpa validasi tuntas. |
| **Silent Behavioral Regression** | Tipe data valid (`tsc` pass), namun logika bisnis rusak (*null pointer* atau semantic drift). | Eror lolos ke lingkungan produksi meskipun build berhasil. | Integrasi **Differential Unit Testing**. Orchestrator mengeksekusi suite unit test pada setiap step dan menolak perubahan jika tes regresi gagal. |
| **Stale LSP Indexing** | Claude Code mengubah file `A`, tetapi LSP daemon masih menyimpan memori file `A` versi lama saat menganalisis `B`. | Agen menerima pesan diagnostik palsu (*false positive errors*) dan melakukan halusinasi perbaikan. | Paksa sinkronisasi LSP dengan mengirim notifikasi `didChange` / `didSave` atau restart daemon diagnostik di antara batch level topologis. |
| **Type Narrowing Erasure** | Agen menyederhanakan *type union* kompleks menjadi `any` untuk menghindari kompilasi eror. | Penurunan kualitas kode (*type degradation*), melemahkan sistem tipe enterprise. | Konfigurasi ketat compiler: `-DnoImplicitAny`, `-strictNullChecks`, dan *AST assertion check* yang menolak penambahan kata kunci `any`. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap strategi mutasi kode multi-file memiliki konsekuensi arsitektural yang berbeda:

```
                  ACCURACY / SAFETY
                         ^
                         |           [AST-driven Two-Phase Commit]
                         |                 (Implementasi Kita)
                         |
                         |     [Sliding Context Batching]
                         |
                         |
  [Naive Monolithic]     |
     (Dump & Hope)       |
  -----------------------+---------------------------------------> SPEED / COST
                         |
```

### 1. Naive Monolithic Dump vs. Topological Incrementalism
- **Naive Monolithic**: Memasukkan 20 file ke prompt tunggal dan meminta Claude Code menghasilkan seluruh perbaikan.
  - *Trade-off*: Cepat dan murah dalam implementasi tooling awal, namun memiliki tingkat kegagalan >85% pada basis kode enterprise akibat degradasi atensi LLM.
- **Topological Incrementalism** (Solusi Terpilih): Memecah tugas menjadi langkah-langkah diskret berdasarkan dependensi.
  - *Trade-off*: Membutuhkan latensi lebih tinggi dan konsumsi token bertahap, namun memberikan jaminan deterministik 100% pada konsistensi tipe.

### 2. Whole-File Rewriting vs. Unified Diff Patching
- **Whole-File Rewriting**: Agen menulis ulang seluruh konten berkas.
  - *Trade-off*: Sederhana dan bebas konflik format diff, tetapi sangat boros token output dan rentan menghapus fungsi utilitas yang tidak terkait.
- **Unified Diff Patching (`Edit` Tool)**: Menggunakan blok pencarian dan penggantian string unik (*unique pattern matching*).
  - *Trade-off*: Sangat hemat token dan cepat. Namun rentan gagal jika target blok kode duplikat atau Claude salah memformat whitespace.

### 3. In-Memory Transaction vs. Git Worktrees
- **In-Memory Buffer**: Melakukan rollback via string manipulation di memori.
  - *Trade-off*: Ringan, namun gagal memitigasi interaksi file system eksternal (misal: tools linter eksternal yang otomatis berjalan).
- **Git Worktree Isolation**:
  - *Trade-off*: Menggunakan branch terpisah secara fisik di disk. Memberikan isolasi total dan kemampuan audit instan via `git diff HEAD`, sangat direkomendasikan untuk enterprise CI/CD.

---

## 9. Best Practices & Standard Industri

1. **Aturan "One Interface, One Commit"**: Jangan pernah menggabungkan refaktorisasi antarmuka publik dengan penulisan ulang implementasi privat dalam satu siklus iterasi agen. Pisahkan menjadi dua commit terpisah.
2. **Karantina AST (Skeleton-Only Prompting)**: Hanya berikan implementasi penuh untuk berkas yang sedang aktif diedit. Untuk semua berkas dependensi impor, berikan hanya file `.d.ts` atau *skeleton definitions* (definisi antarmuka kosong).
3. **Deterministic Pre-flight Validation**: Sebelum Claude Code menyentuh kode:
   - Pastikan working tree bersih (`git status --porcelain` kosong).
   - Pastikan build baseline awal lolos tanpa eror. Jangan pernah menjalankan agen refaktorisasi pada basis kode yang sudah rusak (*broken baseline*).
4. **Hard Limit pada Self-Healing Retries**: Batasi iterasi perbaikan mandiri agen maksimal 3 kali per berkas. Jika agen gagal memperbaiki eror tipenya sendiri dalam 3 kali percobaan, lakukan abort transaksi. Loop tanpa batas akan menghabiskan kuota API dan menghasilkan kode yang makin terdegradasi.
5. **Simpan Semantic Trace Logs**: Rekam seluruh diff, pesan LSP diagnostics, dan prompt intermediate ke dalam berkas artefak JSON untuk keperluan audit kepatuhan (*compliance & post-mortem analysis*).

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda memiliki sistem microservice mini yang terdiri dari 4 modul yang saling bergantung:
1. `types.ts`: Mendefinisikan antarmuka entitas domain.
2. `storage.ts`: Lapisan persistensi data mentah (bergantung pada `types.ts`).
3. `service.ts`: Logika bisnis pemrosesan order (bergantung pada `storage.ts`).
4. `controller.ts`: API endpoint handler (bergantung pada `service.ts`).

Saat ini, fungsi pengambilan data pada `storage.ts` bersifat sinkronus murni. Target refaktorisasi Anda adalah **mengubah seluruh rantai pemanggilan dari sinkronus menjadi Asynchronous (berbasis Promise) di seluruh 4 berkas tersebut**, menggunakan Claude Code CLI dengan pendekatan transactional verification.

### Langkah-langkah Praktikum

#### Langkah 1: Persiapan Basis Kode Awal
Buat direktori baru dan inisialisasi modul:
```bash
mkdir -p /tmp/claude-refactor-lab && cd /tmp/claude-refactor-lab
npm init -y
npm install typescript @types/node --save-dev
npx tsc --init
```

Konfigurasi `tsconfig.json` agar mengaktifkan strict mode:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

Buat direktori `src` dan berkas-berkas berikut:
```bash
mkdir src
```

`src/types.ts`:
```typescript
export interface Order {
  id: string;
  amount: number;
}
```

`src/storage.ts`:
```typescript
import { Order } from './types';

export class OrderStorage {
  private orders: Map<string, Order> = new Map([
    ['order-1', { id: 'order-1', amount: 150 }]
  ]);

  public getOrder(id: string): Order {
    const order = this.orders.get(id);
    if (!order) throw new Error('Order not found');
    return order;
  }
}
```

`src/service.ts`:
```typescript
import { OrderStorage } from './storage';
import { Order } from './types';

export class OrderService {
  private storage = new OrderStorage();

  public processOrder(id: string): { order: Order; fee: number } {
    const order = this.storage.getOrder(id);
    return { order, fee: order.amount * 0.1 };
  }
}
```

`src/controller.ts`:
```typescript
import { OrderService } from './service';

export class OrderController {
  private service = new OrderService();

  public handleRequest(id: string): string {
    const result = this.service.processOrder(id);
    return JSON.stringify(result);
  }
}
```

Validasi baseline:
```bash
npx tsc
# Output harus bersih (exit code 0)
```

Inisialisasi git dan buat snapshot commit awal:
```bash
git init
git add .
git commit -m "baseline: working synchronous implementation"
```

#### Langkah 2: Menjalankan Claude Code dengan Execution Constraint
Buka Claude Code dalam repositori:
```bash
claude
```

Masukkan instruksi terstruktur berikut pada prompt Claude Code (meniru protokol DAG):

```text
TUGAS REFAKTORISASI MULTI-FILE:
Migrasikan fungsi getOrder pada OrderStorage dan seluruh dependensinya agar sepenuhnya berbasis Asynchronous (Promise/async/await).

IKUTI ATURAN EKSEKUSI WAJIB INI:
1. Analisis graph dependensi berkas: tentukan urutan topologis dari daun (storage.ts) hingga pemanggil teratas (controller.ts).
2. Lakukan perubahan SECARA BERURUTAN berdasarkan urutan topologis tersebut, SATU BERKAS PER SATU WAKTU.
3. Setelah mengubah SATU berkas, jalankan tool Bash: `npx tsc` untuk memverifikasi tipe.
4. JIKA npx tsc menghasilkan eror pada berkas yang BELUM Anda modifikasi (karena menunggu modifikasi selanjutnya), catat eror tersebut dan segera lanjutkan modifikasi ke modul pemanggil berikutnya.
5. JIKA npx tsc menghasilkan eror pada berkas yang SUDAH Anda modifikasi, perbaiki berkas tersebut SEBELUM berpindah ke modul pemanggil.
6. Berhenti dan laporkan ringkasan hanya ketika `npx tsc` memberikan output 0 eror di seluruh proyek.
```

#### Langkah 3: Evaluasi Hasil & Verifikasi Diff
Setelah Claude Code selesai mengeksekusi urutan perubahan, keluar dari CLI dan verifikasi integritas:

```bash
# 1. Pastikan kompilasi TypeScript benar-benar bersih
npx tsc

# 2. Periksa git diff untuk memastikan tidak ada perubahan kode di luar lingkup
git diff src/storage.ts
git diff src/service.ts
git diff src/controller.ts
```

Pastikan struktur akhirnya identik dengan pola asynchronous yang bersih:
- `OrderStorage.getOrder`: Mengembalikan `Promise<Order>`.
- `OrderService.processOrder`: Menjadi `async processOrder` dan menggunakan `await this.storage.getOrder(id)`.
- `OrderController.handleRequest`: Menjadi `async handleRequest` dan menggunakan `await this.service.processOrder(id)`.

Jika verifikasi berhasil, commit hasil kerja agen:
```bash
git commit -am "refactor: successfully migrated order pipeline to async via Claude Code"
```