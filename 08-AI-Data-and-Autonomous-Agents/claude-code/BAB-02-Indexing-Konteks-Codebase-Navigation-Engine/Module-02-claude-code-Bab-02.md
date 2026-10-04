# BAB 02: Indexing Konteks & Codebase Navigation Engine
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Internal Code Navigation Engine**: Memahami cara kerja mesin indexing berbasis *Abstract Syntax Tree* (AST), *Source Code Intelligence Protocol* (SCIP), dan *Language Server Protocol* (LSP) yang digunakan agent otonom seperti Claude Code untuk memetakan dependensi kode lintas direktori.
2. **Merancang Hybrid Retrieval Pipeline untuk Codebase Skala Besar**: Menggabungkan pencarian leksikal berkecepatan tinggi (*sub-millisecond ripgrep/BM25*), *Symbol Graph Traversal*, dan *Dense Vector Embeddings* menggunakan *Reciprocal Rank Fusion* (RRF).
3. **Mengimplementasikan Token Budget Allocation Engine**: Membangun mekanisme pemotongan, kompresi konteks, dan *sliding-window relevance filtering* guna memastikan agent tidak mengalami *context overflow* maupun *attention degradation* saat membaca monorepo jutaan baris kode.
4. **Membangun Sistem Inkremental Indexing & Cache Invalidation**: Mengintegrasikan *file-system watchers* (FSEvents/inotify) berbasis hashing kriptografis pohon direktori (Merkle Tree / Inode-based tracking) untuk pembaruan indeks *real-time* dengan overhead CPU < 2%.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **Pemrograman TypeScript/Node.js Lanjutan & Native Addons**: Konkurensi (`Worker Threads`, `Atomics`), Streams, dan interoperabilitas C/Rust via Node-API.
* **Teori Kompiler & Parsing**: Konsep dasar *lexer*, *parser*, *grammar rules*, dan *Concrete/Abstract Syntax Tree* (AST).
* **Information Retrieval**: BM25 scoring, *Vector Cosine Similarity*, metrik evaluasi perolehan (MRR, nDCG@k).
* **Agentic Workflows**: Pola Tool Calling (ReAct, Function Calling), Context Injection, dan manajemen token LLM (Claude 3.5 Sonnet context window mechanics).

---

### 3. Concept & Internal Architecture (Mendalam)

Claude Code dan agent rekayasa perangkat lunak modern tidak membaca seluruh codebase ke dalam *context window* secara mentah. Memasukkan jutaan baris kode secara naif akan mengakibatkan latensi inferensi membengkak, biaya API meledak, dan model mengalami fenomena *Lost in the Middle* (kegagalan memproses instruksi yang tertimbun di tengah token stream).

Sebaliknya, arsitektur Codebase Navigation Engine bekerja melalui tiga lapisan abstraksi terkoordinasi:

```
+-----------------------------------------------------------------------------------+
|                           CLAUDE CODE CONTEXT ENGINE                              |
+-----------------------------------------------------------------------------------+
|  [Layer 1: Structural Indexing]    Tree-sitter Parsing -> AST -> Symbol Extractor |
|  [Layer 2: Relational Graph]       SCIP / LSP Daemon -> Def/Ref Dependency Graph  |
|  [Layer 3: Hybrid Retrieval Engine] Lexical (BM25) + Dense Embeddings + RRF Rerank |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                           DYNAMIC CONTEXT HYDRATOR                                |
+-----------------------------------------------------------------------------------+
|  - Token Budget Allocator (e.g., 32k reserve for context, 8k for scratchpad)      |
|  - AST Skeletization (Stubs, Interface outlines, stripping private method bodies) |
|  - Topological Sort Context Slicing (Caller -> Callee call chains)                |
+-----------------------------------------------------------------------------------+
```

#### A. Structural Extraction Menggunakan Tree-sitter
Engine mengekstrak struktur kode deterministik tanpa mengeksekusi runtime language. Tree-sitter menghasilkan AST inkremental yang toleran terhadap sintaks error (*error-tolerant parser*). Struktur ini mengekspos:
* **Definitions**: Deklarasi fungsi, kelas, interface, tipe data, dan enum.
* **References**: Pemanggilan fungsi, instansiasi kelas, dan pewarisan interface.
* **Docstrings & Metadata**: Komentar JSDoc/GoDoc/RustDoc yang mendokumentasikan kontrak antarmuka.

#### B. The Dual-Graph Architecture (Symbol Graph + Lexical Inverted Index)
1. **Symbol Graph**: Struktur data *directed acyclic graph* (DAG) yang menghubungkan simpul (*nodes*) berupa entitas kode (misal `UserService.authenticate`) dengan sisi (*edges*) yang merepresentasikan relasi (`CALLS`, `EXTENDS`, `IMPLEMENTS`, `IMPORTS`).
2. **Lexical Inverted Index**: Index berbasis trie atau n-gram (seperti arsitektur `ripgrep` atau SQLite FTS5) untuk penemuan string literal, error log, dan penamaan variabel secara eksak dengan kompleksitas waktu $O(k)$ di mana $k$ adalah panjang string pencarian.

#### C. Context Compaction & Token Budgeting
Ketika Claude Code menerima prompt tugas (misalnya: *"Fix the race condition in the payment reconciliation worker"*), engine melakukan:
1. **Initial Probe (Candidate Selection)**: Pencarian hibrida mengambil 50 kandidat file/simpul terkait.
2. **Relevance Filtering & Reranking**: Menggunakan Cross-Encoder atau BM25 + Vector RRF untuk memilih Top-N kandidat (misal 5 file inti).
3. **AST Skeletization**: Untuk file sekunder (dependensi), engine mereduksi implementasi internal metode menjadi deklarasi antarmuka/stub:
   ```typescript
   // Versi Original (150 token)
   public processPayment(tx: Transaction): Receipt {
       validate(tx);
       auditLog(tx);
       const result = this.gateway.charge(tx);
       persist(result);
       return result;
   }
   
   // Versi Skeletized (35 token)
   public processPayment(tx: Transaction): Receipt; // Stubs injected for callee context
   ```
4. **Hydration**: File utama diinjeksi secara utuh, sedangkan file konteks pendukung diinjeksi dalam bentuk kerangka (skeleton) untuk menghemat hingga 70% kuota token prompt.

---

### 4. Why & What

| Dimensi | Dumb Naive Chunking (RAG Tradisional) | Codebase Navigation Engine (Claude Code) |
| :--- | :--- | :--- |
| **Parsing Unit** | Arbitrary token/line split (e.g., 500 token window) | AST Node / Semantic Boundary (Class, Method, Module) |
| **Hubungan Konteks** | Hilang saat terpotong batas chunk | Utuh via Symbol Graph (Edges: Calls, Instantiates) |
| **Penanganan Update** | Re-embedding massal file, biaya tinggi | AST diffing lokal, re-indexing hanya delta yang berubah |
| **Kapasitas Token** | Cepat penuh oleh boilerplate kode | Hemat via dynamic skeletization & topological context injection |
| **Akurasi Eksekusi** | Rentan halusinasi signature / import hilang | Deterministik: signature valid terjamin dari compiler AST |

#### Mengapa Ini Krusial?
Model AI yang bertindak sebagai software engineer tidak bisa hanya mengandalkan kemiripan semantik teks biasa (*vector similarity*). Pencarian vektor murni sering kali gagal membedakan antara implementasi method dan antarmukanya, atau luput menyertakan definisi tipe parameter yang berada di file terpisah. Codebase Navigation Engine mengubah kode menjadi graf relasional presisi tinggi, memungkinkan agent "berpikir" layaknya IDE (Integrated Development Environment).

---

### 5. How (Workflow Detail)

Alur kerja end-to-end penanganan query oleh Context Engine adalah sebagai berikut:

```
[User Request / Agent Action]
              │
              ▼
[Step 1: Query Analysis] ──> Ekstraksi Intent, Simbol, Identifiers, & Natural Language
              │
              ▼
[Step 2: Dual-Path Retrieval]
       ├── Path A: Fast Inverted Index (BM25/Ripgrep) ──> Leksikal Hits
       └── Path B: Vector Semantic Index (HNSW)       ──> Konseptual Hits
              │
              ▼
[Step 3: Reciprocal Rank Fusion (RRF)] ──> Peringkat gabungan terpadu kandidat
              │
              ▼
[Step 4: Dependency Traversal] ──> Ekspansi graf 1-2 hop (SCIP/AST Definitions)
              │
              ▼
[Step 5: Context Assembly & Budgeting]
       ├── Hitung batas token (Token Budget Evaluator)
       ├── Injeksi Full Text untuk Target Node
       └── Injeksi Skeletized AST untuk 1st-Hop Dependency Nodes
              │
              ▼
[Step 6: Prompt Construction] ──> Kirim XML Context Blocks ke Claude Model
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan Anda seorang arsitek yang dipanggil untuk merenovasi pipa di lantai 14 sebuah gedung pencakar langit. 
* **Pendekatan Naive RAG**: Seseorang memfotokopi 500 halaman acak dari cetak biru bangunan, memotongnya menjadi carik-carik kertas kecil, lalu memberi Anda carik kertas yang memuat kata "pipa". Anda tidak tahu carik kertas itu milik lantai dasar, basement, atau atap.
* **Pendekatan Code Navigation Engine**: Anda diberikan cetak biru skematik gedung secara utuh (AST Outline). Anda dapat langsung membuka direktori instalasi pipa lantai 14, melihat pipa masuk dari mana dan keluar ke mana via skema diagram alir (Symbol Graph), sambil tetap memegang daftar komponen spesifik pipa yang bersangkutan secara lengkap.

#### Diagram Arsitektur Internal Engine

```
+-----------------------------------------------------------------------------+
|                            WORKSPACE FILESYSTEM                             |
+-----------------------------------------------------------------------------+
   │               │                                           ▲
   │ Watch Events  │ Read File                                 │ Write Back
   ▼               ▼                                           │
+----------------------------------------------------+         │
| INCREMENTAL FILE WATCHER & CACHE MANAGER           |         │
| - Merkle Tree Hash Validation                      |         │
| - Inode Invalidation Engine                        |         │
+----------------------------------------------------+         │
   │                                                           │
   ▼                                                           │
+----------------------------------------------------+         │
| PARSER & SYMBOL GRAPH PIPELINE                     |         │
| - Tree-sitter Native Worker Threads                |         │
| - AST Extraction (Def/Ref/Imports)                 |         │
| - SQLite/DuckDB In-Memory Graph Storage            |         │
+----------------------------------------------------+         │
   │                                                           │
   ▼                                                           │
+----------------------------------------------------+         │
| RETRIEVAL & QUERY ENGINE                           |         │
| - BM25 Lexical Scanner + Vector Embeddings Engine  |         │
| - Reciprocal Rank Fusion (k=60)                    |         │
| - Call-Graph Traversal (1-to-N Depth Limit)        |         │
+----------------------------------------------------+         │
   │                                                           │
   ▼                                                           │
+----------------------------------------------------+         │
| CONTEXT WINDOW ALLOCATOR & PACKER                  |         │
| - tiktoken/anthropic Token Estimator               |         │
| - AST Skeletonizer (Strip Body / Preserve Types)   |         │
+----------------------------------------------------+         │
   │                                                           │
   ▼                                                           │
+────────────────────────────────────────────────────+         │
| AGENT RUNTIME EXECUTION LOOP                       |─────────┘
| (Claude 3.5 Sonnet Tool Use: Read, Edit, Terminal) |
+────────────────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Ekstraksi Simbol AST Berbasis Tree-sitter

Skrip minimal di bawah ini menunjukkan bagaimana engine mengekstrak simbol secara terstruktur tanpa membaca file sebagai teks mentah biasa.

```typescript
// simple-ast-extract.ts
import Parser from 'web-tree-sitter';

async function initParser() {
  await Parser.init();
  const parser = new Parser();
  // Asumsi bahasa TypeScript WASM telah dimuat
  const TypeScript = await Parser.Language.load('./tree-sitter-typescript.wasm');
  parser.setLanguage(TypeScript);
  return parser;
}

function extractSymbols(sourceCode: string, parser: Parser) {
  const tree = parser.parse(sourceCode);
  const symbols: Array<{ type: string; name: string; line: number }> = [];

  function traverse(node: Parser.SyntaxNode) {
    if (node.type === 'function_declaration' || node.type === 'method_definition') {
      const nameNode = node.childForFieldName('name');
      if (nameNode) {
        symbols.push({
          type: node.type,
          name: nameNode.text,
          line: node.startPosition.row + 1,
        });
      }
    }
    for (let i = 0; i < node.childCount; i++) {
      const child = node.child(i);
      if (child) traverse(child);
    }
  }

  traverse(tree.rootNode);
  return symbols;
}

// Demo eksekusi
const sampleCode = `
export class OrderService {
  private validate(orderId: string): boolean {
    return orderId.length > 0;
  }
  public executeOrder(orderId: string): void {
    if (this.validate(orderId)) {
      console.log("Processed");
    }
  }
}
`;

(async () => {
  const parser = await initParser();
  const symbols = extractSymbols(sampleCode, parser);
  console.log("Extracted Symbols:", symbols);
})();
```

#### B. Practical Example: Production-Grade Code Context Hydration Engine

Berikut implementasi engine produksi modular yang mencakup:
1. Lexical index berbasis in-memory inverted index.
2. Symbol reference resolver.
3. Token budget manager dengan AST skeletization.

```typescript
// context-engine.ts
import * as crypto from 'crypto';

export interface CodeEntity {
  id: string;
  filePath: string;
  symbolName: string;
  kind: 'class' | 'function' | 'interface' | 'variable';
  rawCode: string;
  skeletonCode: string;
  references: string[]; // Daftar ID entitas yang dipanggil
  tokenCountEstimate: number;
}

export interface SearchResult {
  entity: CodeEntity;
  score: number;
}

export class CodeContextEngine {
  private entities: Map<string, CodeEntity> = new Map();
  private invertedIndex: Map<string, Set<string>> = new Map(); // token -> entityIds
  private tokenRateRatio: number = 3.8; // Estimasi rata-rata karakter per token untuk kode

  /**
   * Menambahkan atau memperbarui entitas kode ke dalam engine
   */
  public registerEntity(entity: CodeEntity): void {
    this.entities.set(entity.id, entity);
    this.indexTerms(entity.id, `${entity.symbolName} ${entity.filePath} ${entity.rawCode}`);
  }

  /**
   * Indexing leksikal sederhana (Tokenizer & Normalizer)
   */
  private indexTerms(entityId: string, text: string): void {
    const tokens = text
      .toLowerCase()
      .split(/[^a-zA-Z0-9_]+/)
      .filter((t) => t.length > 2);

    for (const token of tokens) {
      if (!this.invertedIndex.has(token)) {
        this.invertedIndex.set(token, new Set());
      }
      this.invertedIndex.get(token)!.add(entityId);
    }
  }

  /**
   * Pencarian hybrid leksikal + scoring sederhana
   */
  public search(query: string, limit: number = 10): SearchResult[] {
    const queryTokens = query
      .toLowerCase()
      .split(/[^a-zA-Z0-9_]+/)
      .filter((t) => t.length > 2);

    const matchCounts = new Map<string, number>();

    for (const token of queryTokens) {
      const matchedEntities = this.invertedIndex.get(token);
      if (matchedEntities) {
        for (const entityId of matchedEntities) {
          matchCounts.set(entityId, (matchCounts.get(entityId) || 0) + 1);
        }
      }
    }

    const results: SearchResult[] = [];
    for (const [entityId, count] of matchCounts.entries()) {
      const entity = this.entities.get(entityId)!;
      // Skor dasar BM25-like: frekuensi token cocok dibagi perkiraan token file
      const score = count / (1 + Math.log(entity.tokenCountEstimate || 10));
      results.push({ entity, score });
    }

    return results.sort((a, b) => b.score - a.score).slice(0, limit);
  }

  /**
   * Mengumpulkan konteks yang dioptimalkan sesuai batas token budget
   */
  public hydrateContext(query: string, maxTokenBudget: number): string {
    const searchResults = this.search(query, 5);
    if (searchResults.length === 0) return '<!-- Konteks tidak ditemukan -->';

    let currentTokens = 0;
    const includedEntities = new Set<string>();
    const contextBlocks: string[] = [];

    // Prioritas 1: Node Target Utama (Full Code)
    for (const res of searchResults) {
      const entity = res.entity;
      const estimatedCost = Math.ceil(entity.rawCode.length / this.tokenRateRatio);

      if (currentTokens + estimatedCost <= maxTokenBudget) {
        includedEntities.add(entity.id);
        currentTokens += estimatedCost;
        contextBlocks.push(
          `<!-- Target Simbol: ${entity.symbolName} [Full] -->\n` +
          `File: ${entity.filePath}\n` +
          `\`\`\`typescript\n${entity.rawCode}\n\`\`\``
        );
      } else {
        // Jika tidak muat full, coba masukkan bentuk skeleton
        const skeletonCost = Math.ceil(entity.skeletonCode.length / this.tokenRateRatio);
        if (currentTokens + skeletonCost <= maxTokenBudget) {
          includedEntities.add(entity.id);
          currentTokens += skeletonCost;
          contextBlocks.push(
            `<!-- Target Simbol: ${entity.symbolName} [Skeletonized] -->\n` +
            `File: ${entity.filePath}\n` +
            `\`\`\`typescript\n${entity.skeletonCode}\n\`\`\``
          );
        }
      }
    }

    // Prioritas 2: Relasi Dependensi (Graph Edge Traversal)
    for (const entityId of Array.from(includedEntities)) {
      const parent = this.entities.get(entityId)!;
      for (const refId of parent.references) {
        if (!includedEntities.has(refId) && this.entities.has(refId)) {
          const depEntity = this.entities.get(refId)!;
          const depCost = Math.ceil(depEntity.skeletonCode.length / this.tokenRateRatio);

          if (currentTokens + depCost <= maxTokenBudget) {
            includedEntities.add(refId);
            currentTokens += depCost;
            contextBlocks.push(
              `<!-- Dependensi Terhubung: ${depEntity.symbolName} [Skeleton Only] -->\n` +
              `File: ${depEntity.filePath}\n` +
              `\`\`\`typescript\n${depEntity.skeletonCode}\n\`\`\``
            );
          }
        }
      }
    }

    return (
      `<!-- CONTEXT INJECTION (Budget: ${maxTokenBudget}, Terpakai: ~${currentTokens} Tokens) -->\n` +
      contextBlocks.join('\n\n')
    );
  }
}

// Simulasi Pengujian Produksi
const engine = new CodeContextEngine();

// 1. Definisikan database entity mock
engine.registerEntity({
  id: 'ent_payment_gateway',
  filePath: 'src/gateways/PaymentGateway.ts',
  symbolName: 'PaymentGateway',
  kind: 'interface',
  rawCode: `export interface PaymentGateway {\n  charge(amount: number, token: string): Promise<boolean>;\n  refund(chargeId: string): Promise<boolean>;\n}`,
  skeletonCode: `export interface PaymentGateway { charge(...); refund(...); }`,
  references: [],
  tokenCountEstimate: 30,
});

engine.registerEntity({
  id: 'ent_billing_service',
  filePath: 'src/services/BillingService.ts',
  symbolName: 'BillingService',
  kind: 'class',
  rawCode: `import { PaymentGateway } from '../gateways/PaymentGateway';\n\nexport class BillingService {\n  constructor(private gateway: PaymentGateway) {}\n  public async processBill(userId: string, amount: number) {\n    // Verifikasi saldo pengguna\n    console.log("Memvalidasi user: ", userId);\n    const success = await this.gateway.charge(amount, "tok_verified");\n    if (!success) throw new Error("Gagal memproses tagihan");\n    return { status: "PAID", timestamp: Date.now() };\n  }\n}`,
  skeletonCode: `export class BillingService {\n  constructor(private gateway: PaymentGateway);\n  public async processBill(userId: string, amount: number): Promise<{ status: string; timestamp: number }>;\n}`,
  references: ['ent_payment_gateway'],
  tokenCountEstimate: 120,
});

// Jalankan query dengan batas token ketat
const contextOutput = engine.hydrateContext('processBill BillingService', 150);
console.log(contextOutput);
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Fintech Core Ledger Platform (Monorepo 4.2 Juta LOC)
* **Skala Sistem**:
  * Repository: Monorepo monolitik perbankan (TypeScript, Rust, Go).
  * Ukuran: 4.200.000 lines of code, ~45.000 file.
  * Masalah: Claude Code gagal menyelesaikan perbaikan issue perbankan karena *context timeout* saat melakukan ekspansi globbing file standar (`grep` memakan waktu > 45 detik, dan agent kehabisan 200k context window hanya dari membaca 3 file log tracing).

#### Solusi Arsitektur yang Diterapkan:
1. **SCIP Multi-Language Indexing Daemon**:
   * Menjalankan daemon `scip-typescript` dan `scip-rust` saat startup workspace.
   * Seluruh referensi simbol di-cache dalam database lokal SQLite berkecepatan tinggi dengan ekstensi memory-mapped IO (`mmap`).
2. **Two-Tier Cache Invalidation**:
   * Menggunakan daemon `watchman` dari Meta untuk mendengarkan perubahan filesystem.
   * Saat developer atau agent mengubah satu file, hanya sub-graf AST file tersebut yang diparsing ulang dan di-commit ke SQLite index dalam waktu 18 milidetik.
3. **Graph-Scoped Context Window Assembler**:
   * Agent dibatasi hanya dapat membaca file implementasi utama secara utuh.
   * Seluruh caller dan callee langsung dipadatkan (*skeletized*) menjadi tipe TypeScript/Rust signature.

#### Hasil Metrik Produksi:
* **Penurunan Token Usage per Prompt**: Dari rata-rata 148.000 token menjadi 24.500 token (Penghematan Biaya API sebesar 83.4%).
* **Latency Retrieval**: Dari 45 detik (ripgrep/file read manual) menjadi 140 milidetik (Indexed SQLite Graph Query).
* **Success Rate Perbaikan Bug Otomatis**: Meningkat dari 31% menjadi 89% tanpa halusinasi antarmuka/tipe.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Kerugian & Konsekuensi | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **AST Skeletization Agresif** | Menghemat token hingga 75%, muat banyak konteks terkait. | Menghilangkan logika detail internal method dependensi. | Terapkan *on-demand dynamic expansion*: Agent dapat memanggil tool `expand_symbol` jika memerlukan isi logic implementasi. |
| **Full In-Memory Vector Index** | Pencarian semantik fleksibel pada konsep non-literal. | Konsumsi memori RAM tinggi (>4GB untuk codebase besar); latensi cold-start indexing lama. | Gunakan hybrid search: HNSW berdimensi kecil (384-d) dipadukan dengan disk-backed SQLite FTS5. |
| **Deep Dependency Expansion (> 3 Hops)** | Visibilitas sistem menyeluruh (end-to-end trace). | Rentan *Context Pollution* dan konsumsi token eksponensial ($O(b^d)$). | Batasi traversal maksimal 1 hop secara default; ekspansi hop ke-2 hanya jika ada referensi tipe tak terdefinisi. |
| **Background FS Watching (inotify/FSEvents)** | Index selalu sinkron secara real-time (*zero stale reads*). | Membebani baterai/CPU laptop developer; risiko *file-descriptor exhaustion*. | Pasang debounce window (500ms) dan batasi ignore patterns secara ketat (`node_modules`, `.git`, `dist`). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Context Poisoning akibat Symlink dan Circular Dependency
* **Gejala**: Agent berhenti merespons, memori proses melonjak hingga crash (*OOM - Out of Memory*), token usage mendadak mentok ke batas limit model (200k).
* **Penyebab**: Graph traversal terjebak dalam siklus tak terbatas (*circular reference*: File A -> File B -> File A) atau symlink folder yang melingkar.
* **Solusi**: Gunakan `Set<string>` yang mencatat `visitedNodeIds` dan batasi `maxDepth` traversal. Canonicalize semua path file menggunakan `fs.realpathSync`.

#### 2. Stale AST Cache Saat Pergantian Git Branch
* **Gejala**: Claude Code memberikan perbaikan kode berdasarkan nama fungsi yang sudah di-rename di branch baru, menyebabkan runtime error `TypeError: undefined is not a function`.
* **Penyebab**: File watcher melewatkan event batch git checkout massal, atau cache hash masih merujuk pada commit branch sebelumnya.
* **Solusi**: Validasi indeks dengan memverifikasi header hash Git `HEAD` commit. Jika branch pointer berubah drastis, trigger *fast reconciliation diff* menggunakan `git diff --name-only HEAD@{1} HEAD`.

#### 3. Stripping Context Terlalu Agresif (Under-Hydration)
* **Gejala**: Model mengeluh *"Cannot determine the type of parameter X"* dan mulai mengarang (*halusinasi*) struktur interface sendiri.
* **Penyebab**: AST Skeletonizer membuang blok `import` atau *type aliases* dasar saat mereduksi kode.
* **Solusi**: Pastikan AST extractor memisahkan antara *executable statements* (yang aman dipangkas) dan *declarative type bindings* (yang wajib dipertahankan).

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengintegrasikan Claude Code context engine ke lingkungan CI/CD atau IDE developer:

- [ ] **Path Sanitization**: Semua path file dinormalisasi ke POSIX style (`/`) dan divalidasi tidak keluar dari root project (*path traversal protection*).
- [ ] **Strict Token Guardrail**: Konfigurasi hard limit token konteks per prompt (contoh: maks 40.000 token dari total 200.000 jendela token Sonnet) guna menyisakan ruang untuk *thought chain* dan eksekusi instruksi.
- [ ] **Deterministic Grammar Engine**: Parser Tree-sitter dikompilasi ke native binary atau WASM berkinerja tinggi, bukan parser berbasis Regex.
- [ ] **Ignore Patterns Enforcement**: Mesin indexing mematuhi standar konfigurasi `.gitignore`, `.ignore`, dan custom `.claudeignore`.
- [ ] **Debounced Invalidation Pipeline**: Mutasi file sistem dikelompokkan (*batched*) menggunakan mekanisme debounce minimal 300–500ms sebelum memicu re-indexing parsial.
- [ ] **Graceful Degradation**: Jika parser gagal membaca file sintaks error, engine otomatis beralih (*fallback*) ke pencarian leksikal teks biasa tanpa memutus siklus kerja agent.

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun sebuah Node.js/TypeScript Tooling Engine mini yang memetakan file dependensi, melakukan skeletization kode, dan menyusun context payload untuk Claude.

#### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── indexer.ts
│   ├── skeletonizer.ts
│   └── context-builder.ts
└── test-fixtures/
    ├── math.ts
    └── calculator.ts
```

#### Langkah 1: Inisialisasi Project & Dependencies
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src hands-on/m02/test-fixtures
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node --save-dev
npx tsc --init
```

#### Langkah 2: Buat Test Fixtures
Tulis file `hands-on/m02/test-fixtures/math.ts`:
```typescript
export interface OperationResult {
  value: number;
  timestamp: string;
}

export class AdvancedMath {
  public static add(a: number, b: number): OperationResult {
    const res = a + b;
    return { value: res, timestamp: new Date().toISOString() };
  }

  public static complexInternalFactorial(n: number): number {
    // Logika intensif yang tidak perlu dibaca Claude jika hanya sebagai dependensi
    if (n <= 1) return 1;
    return n * this.complexInternalFactorial(n - 1);
  }
}
```

Tulis file `hands-on/m02/test-fixtures/calculator.ts`:
```typescript
import { AdvancedMath, OperationResult } from './math';

export class Calculator {
  public execute(x: number, y: number): OperationResult {
    console.log("Menghitung kalkulasi...");
    return AdvancedMath.add(x, y);
  }
}
```

#### Langkah 3: Implementasikan Skeletonizer AST Regex Sederhana
Buat file `hands-on/m02/src/skeletonizer.ts`:
```typescript
/**
 * Skeletonizer sederhana berbasis parsing blok kurung kurawal.
 * Pada sistem produksi enterprise, gunakan AST Parser riil (Tree-sitter).
 */
export function skeletonizeTypeScript(sourceCode: string): string {
  const lines = sourceCode.split('\n');
  const result: string[] = [];
  let insideMethod = false;
  let braceDepth = 0;

  for (const line of lines) {
    const trimmed = line.trim();

    // Pertahankan import dan deklarasi interface utuh
    if (trimmed.startsWith('import ') || trimmed.startsWith('export interface')) {
      result.push(line);
      continue;
    }

    // Deteksi deklarasi method
    if ((trimmed.startsWith('public ') || trimmed.startsWith('private ') || trimmed.startsWith('static ')) && trimmed.includes('(')) {
      if (trimmed.endsWith('{')) {
        const signature = line.substring(0, line.lastIndexOf('{')).trimEnd() + '; // [Implementation Hidden]';
        result.push(signature);
        insideMethod = true;
        braceDepth = 1;
        continue;
      }
    }

    if (insideMethod) {
      for (const char of line) {
        if (char === '{') braceDepth++;
        if (char === '}') braceDepth--;
      }
      if (braceDepth <= 0) {
        insideMethod = false;
        braceDepth = 0;
      }
      continue;
    }

    result.push(line);
  }

  return result.join('\n');
}
```

#### Langkah 4: Bangun Context Hydrator CLI
Buat file `hands-on/m02/src/context-builder.ts`:
```typescript
import * as fs from 'fs';
import * as path from 'path';
import { skeletonizeTypeScript } from './skeletonizer';

interface TargetFileContext {
  targetFile: string;
  dependencyFiles: string[];
}

export function buildAgentContext(config: TargetFileContext): string {
  const targetPath = path.resolve(config.targetFile);
  const targetCode = fs.readFileSync(targetPath, 'utf-8');

  let output = `=== TARGET CODEBASE CONTEXT ===\n`;
  output += `TARGET FILE: ${config.targetFile} (FULL IMPLEMENTATION)\n`;
  output += `\`\`\`typescript\n${targetCode}\n\`\`\`\n\n`;

  output += `=== DEPENDENCY SKELETONS (API CONTRACTS ONLY) ===\n`;
  for (const dep of config.dependencyFiles) {
    const depPath = path.resolve(dep);
    const depCode = fs.readFileSync(depPath, 'utf-8');
    const skeleton = skeletonizeTypeScript(depCode);
    output += `DEPENDENCY: ${dep}\n`;
    output += `\`\`\`typescript\n${skeleton}\n\`\`\`\n`;
  }

  return output;
}

// Uji coba manual
const contextPayload = buildAgentContext({
  targetFile: './test-fixtures/calculator.ts',
  dependencyFiles: ['./test-fixtures/math.ts'],
});

console.log(contextPayload);
```

#### Langkah 5: Eksekusi dan Verifikasi
Jalankan program menggunakan `ts-node`:
```bash
npx ts-node src/context-builder.ts
```
*Hasil Verifikasi*: Anda akan melihat bahwa `calculator.ts` dicetak secara penuh, namun `math.ts` diubah menjadi skeleton di mana method `add` dan `complexInternalFactorial` digantikan menjadi deklarasi signature satu baris tanpa implementasi internal tubuh method.

---

### 13. Exercise

#### Level Easy
1. Modifikasi file `skeletonizer.ts` agar komentar satu baris (`//`) dan multi-baris (`/* ... */`) dihapus dari output skeleton guna memangkas token boilerplate tambahan.

#### Level Medium
2. Buat fungsi `detectDependencies(filePath: string): string[]` yang memindai statement `import ... from './path'` secara otomatis menggunakan regular expression/AST, sehingga pengguna tidak perlu lagi mendefinisikan array `dependencyFiles` secara manual di `context-builder.ts`.

#### Level Hard
3. Bangun modul `TokenBudgetLimiter` yang mengintegrasikan perkiraan token. Jika payload context gabungan melebihi batas 1000 token, modul harus memangkas method berkategori `private` terlebih dahulu dari file skeleton, sebelum memotong method `public`.

---

### 14. Challenge

#### Skenario: "Cross-Language Monorepo Broken Context Recovery"
Sebuah monorepo fintech memiliki backend microservices yang berpasangan: Backend inti ditulis menggunakan **Go**, dan adaptor frontend BFF (*Backend for Frontend*) menggunakan **TypeScript**. Kedua service berkomunikasi menggunakan Protocol Buffers (gRPC).

```
repo/
├── proto/
│   └── ledger.proto
├── service-go/
│   ├── main.go
│   └── handler.go
└── bff-ts/
    ├── client.ts
    └── resolver.ts
```

Ketika Claude Code diperintahkan: *"Tambahkan field `tax_id` ke alur transaksi pencatatan buku kas"*, agent mengalami kegagalan beruntun:
1. Agent mengubah `ledger.proto`, namun tidak menyadari file Go dan TypeScript perlu di-generate ulang atau diubah secara serentak.
2. Ketika diarahkan ke `resolver.ts`, agent mengalami kebingungan karena simbol TypeScript dihasilkan oleh compiler proto generator yang file fisiknya berada di direktori `node_modules/@generated/ledger`.

#### Tugas Anda:
Rancang spesifikasi arsitektur context navigation engine tingkat enterprise yang mampu:
1. Mendeteksi dependensi implisit (*codegen bridge*) antara file `.proto`, file `.go`, dan definisi `.d.ts` terkait tanpa hardcoding path file.
2. Mengembangkan skema navigasi multi-bahasa yang menyajikan relasi simbol antar-bahasa secara koheren ke dalam satu urutan konteks prompt Claude.
3. Menuliskan batasan arsitektur (maksimal 2 halaman dokumen teknis konseptual) yang mencakup mekanisme deteksi cache invalidation ketika developer menjalankan command eksternal seperti `buf generate` atau `protoc`.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Mengapa memotong kode (*chunking*) berbasis batasan jumlah karakter tetap (misal: tiap 1000 karakter) sangat buruk untuk LLM coding agent?
   * *Jawaban*: Karena pemotongan sembarangan dapat memutus deklarasi fungsi di tengah sintaks, menghilangkan scope variabel, dan merusak struktur AST yang valid.
2. Apa kepanjangan dari SCIP dan apa perannya dalam codebase navigation?
   * *Jawaban*: Source Code Intelligence Protocol; sebuah protokol standar untuk mengindeks dan mengekspor relasi definisi, referensi, dan dokumentasi simbol kode lintas file secara persisten.
3. Apa perbedaan mendasar antara pencarian leksikal (BM25) dan pencarian semantik (dense vector)?
   * *Jawaban*: BM25 mencari kecocokan kata kunci/string literal secara eksak, sedangkan dense vector mencari kedekatan makna konseptual berdasarkan representasi embedding numerik.
4. Apa fungsi utama teknik *AST Skeletization* pada file dependensi?
   * *Jawaban*: Menghemat token budget dengan hanya menampilkan signature kontrak API publik tanpa memuat implementasi logika tubuh method yang tidak dibutuhkan oleh caller.
5. Mengapa file `.gitignore` harus dipatuhi secara ketat oleh indexing engine?
   * *Jawaban*: Untuk mencegah pembengkakan memori, kehabisan token, dan degradasi performa akibat memproses artefak build (seperti `dist/`, build artifacts) atau dependensi eksternal raksasa (`node_modules/`).

#### Pertanyaan Intermediate
6. Bagaimana Reciprocal Rank Fusion (RRF) menggabungkan hasil peringkat dari pencarian leksikal dan vektor?
   * *Jawaban*: RRF menghitung skor gabungan simpul berdasarkan formula penambahan kebalikan peringkat: $RRF(d) = \sum \frac{1}{k + r_i(d)}$, di mana $k$ adalah konstanta perata (biasanya 60) dan $r_i(d)$ adalah posisi peringkat dokumen pada sistem pencarian masing-masing.
7. Apa risiko utama fenomena *Lost in the Middle* pada LLM dengan context window raksasa (seperti Claude 200k tokens)?
   * *Jawaban*: Model cenderung memberikan perhatian lebih tinggi pada token di awal dan di akhir konteks prompt, sehingga detail instruksi teknis atau definisi interface penting yang terkubur di bagian tengah context window berisiko diabaikan.
8. Bagaimana Merkle Tree digunakan dalam cache invalidation sistem indexing kode?
   * *Jawaban*: Merkle Tree menghitung hash kriptografis pohon direktori dari daun (file) hingga akar. Perubahan pada satu baris kode di sebuah file hanya mengubah hash jalur simpul ke atas, memungkinkan engine menemukan dan memperbarui indeks file yang berubah dalam waktu instan tanpa memindai seluruh repository.
9. Mengapa parser Tree-sitter jauh lebih diunggulkan dibanding compiler native bahasa (seperti `tsc` atau `rustc`) dalam proses live indexing agent?
   * *Jawaban*: Tree-sitter memiliki algoritma *error-tolerant parsing* (mampu menghasilkan AST parsing parsial meskipun kode sedang dalam kondisi error sintaks saat ditulis) dan mendukung pembaruan AST secara inkremental tanpa memicu re-compilation siklus penuh.
10. Kapan representasi implementasi penuh (*Full Body*) suatu file dependensi wajib diinjeksikan menggantikan versi skeleton?
    * *Jawaban*: Ketika prompt tugas secara eksplisit meminta investigasi bug pelacakan error internal (debugging call stack logic), atau ketika kode yang dicurigai sebagai sumber exception berada di dalam badan implementasi callee tersebut.

#### Skenario Kasus Produksi
11. **Skenario A**: Agent Anda mengonsumsi 180.000 token dari kuota 200.000 token hanya untuk menganalisis issue sederhana di repository frontend monorepo. Setelah ditelusuri, sebagian besar token dihabiskan oleh file `package-lock.json` dan bundle `main.js.map`. Bagaimana Anda mengonfigurasi filter context engine secara defensif?
    * *Solusi*: Terapkan rule ekstensi file berbasis blocklist dan size threshold: Abaikan file `.json` struktural berukuran > 50KB, buang seluruh file biner dan source maps (`*.map`), serta terapkan whitelist tipe file source code (`.ts`, `.tsx`, `.js`, dll.).
12. **Skenario B**: Di sebuah repository perbankan, Claude Code sering salah memanggil nama method private yang sudah usang saat diminta menuliskan unit test baru. Penelusuran menunjukkan method lama tersebut masih ada di file backup `UserService.old.ts`. Arsitektur retrieval apa yang bocor?
    * *Solusi*: Terjadi kegagalan *Symbol Scope Isolation*. Retrieval leksikal mencocokkan nama file secara naif tanpa memvalidasi apakah file tersebut masuk ke dalam tree graph kompilasi aktif. Engine harus memprioritaskan traversal via Root Module Graphs (`tsconfig.json` entry points) dan mengesampingkan file yang tidak memiliki referensi impor aktif.
13. **Skenario C**: Pada platform cloud-hosted development environment, 50 kontainer menjalankan indexing engine Tree-sitter secara paralel. Penggunaan CPU melonjak ke 100% dan disk I/O mengalami starvation. Bagaimana merancang arsitektur caching bersama (*shared index*)?
    * *Solusi*: Bangun arsitektur *Decoupled Centralized Indexing*: Proses parsing Tree-sitter dan kalkulasi embedding dieksekusi sekali di level CI/Central Worker per commit Git SHA, kemudian hasilnya disimpan di distributed read-only storage (seperti SQLite db via AWS S3 / network mount). Tiap kontainer workspace hanya perlu mengunduh file snapshot basis data SCIP/SQLite sesuai commit hash yang sedang dicekout.

---

### 16. Summary

* **Codebase Navigation Engine** adalah fondasi utama yang membedakan agent rekayasa perangkat lunak otonom modern (seperti Claude Code) dari chatbot asisten koding biasa berbasis Naive RAG.
* Efisiensi navigasi kode bersandar pada **Tiga Pilar Arsitektur**:
  1. *Structural Indexing* berbasis AST inkremental toleran error (Tree-sitter).
  2. *Symbol Relational Graph* untuk menelusuri definisi, implementasi, dan referensi dependensi (SCIP/LSP).
  3. *Hybrid Information Retrieval* yang memadukan kecepatan leksikal (BM25) dan kedalaman semantik (Embeddings) via *Reciprocal Rank Fusion*.
* **Manajemen Token Budget**: Keberhasilan agent menyelesaikan task bergantung pada kemampuan memadatkan (*compacting*) konteks sekunder via *AST Skeletization* (hanya menyajikan signature dan interface publik), mempertahankan detail penuh hanya untuk target kerja esensial, serta mengeliminasi resiko halusinasi dan kejenuhan memori LLM.