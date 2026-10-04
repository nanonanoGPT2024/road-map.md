# BAB 04: Specification-Driven Development (SDD) & Prompt Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Mengubah "Vibe-Coding" Menjadi Rekayasa Perangkat Lunak Deterministik

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur SDD (Specification-Driven Development)**: Membangun pipeline translasi spesifikasi teknis (OpenAPI/JSON Schema/Type Definitions) menjadi basis kode terverifikasi secara otonom tanpa degradasi arsitektur.
2. **Mengonstruksi Metaprompt Deterministik**: Menerapkan teknik Context Packets, AST-guided generation, dan constrained decoding untuk mengeliminasi stokastisitas ("vibes") dari proses rekayasa kode berbasis LLM.
3. **Mengembangkan Self-Healing Compilation Loop**: Membangun orkestrator yang mengintegrasikan LLM dengan kompiler/linter (TypeScript Compiler API / Tree-sitter / ESLint) untuk loop validasi sintaksis dan semantik secara *closed-loop*.
4. **Mengelola Token Context Budgeting & Drift Prevention**: Mengoptimalkan jendela konteks model dengan kompresi AST dan Dependency Graph Pruning untuk mencegah regresi logika pada repositori monorepo/enterprise skala besar.
5. **Menegakkan Quality Gate Produksi**: Mengintegrasikan continuous synthesis pipeline ke dalam enterprise CI/CD dengan metrik verifikasi formal, deterministic mocking, dan invariant regression tests.

---

### 2. Prerequisite

Untuk menguasai materi ini secara optimal, peserta wajib memahami:
* **Advanced TypeScript / Python**: Paham dynamic type analysis, metaprogramming, reflection, dan AST (Abstract Syntax Tree).
* **Compiler & Static Analysis Tooling**: Paham cara kerja compiler front-end (Lexer, Parser, AST, Symbol Table) serta linter tooling (`tsc`, `tree-sitter`, `mypy`).
* **API Specification Standards**: Menguasai OpenAPI 3.1, JSON Schema Draft 2020-12, gRPC Protobuf v3.
* **Large Language Model Internals**: Memahami mekanisme attention, constrained decoding (Grammar-guided sampling, GBNF), context window sliding, dan semantic drift.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Anatomi Kegagalan "Vibe-Coding" Tradisional
Fenomena *vibe-coding* merujuk pada praktik pengembang yang memanfaatkan LLM secara intuitif melalui instruksi bahasa alami yang longgar (loose natural language prompting). Di lingkungan enterprise, pendekatan ini runtuh akibat tiga masalah mendasar:
1. **Semantic Entropy & Drift**: Probabilitas model menyimpang dari *invariant* arsitektur meningkat secara eksponensial terhadap ukuran konteks dan kedalaman ketergantungan kode.
2. **Context Window Contamination**: Injeksi kode lengkap mentah membebani model dengan token non-kritis (boilerplate, styling, implementasi dependensi privat), menurunkan *signal-to-noise ratio* (SNR) pada attention layers.
3. **Absence of Closed-Loop Feedback**: Model menghasilkan teks probabilistik, bukan kode deterministik; tanpa loop verifikasi AST dan sistem pengetikan ketat, model tidak menyadari halusinasi kontraktual (misal: memanggil fungsi yang tidak ada atau mengubah struktur signature DTO).

#### Arsitektur Specification-Driven Development (SDD)
SDD menggeser peran LLM: **model bukan perancang sistem, melainkan unit eksekusi sintesis dari spesifikasi formal yang deterministik.**

```
+-----------------------------------------------------------------------------------+
|                           SPECIFICATION LAYER                                     |
|  [ OpenAPI 3.1 / JSON Schema / Domain Invariants (Pydantic / Zod Schemas) ]       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        CONTEXT PACKET COMPILER (CPC)                              |
|  - Dependency Graph Extraction (Tree-sitter AST)                                  |
|  - Token Budget Allocation (Token-level Pruning)                                  |
|  - Dynamic Metaprompt Assembler                                                   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         INFERENCE & DECODING LAYER                                |
|  - Structural Grammar Constraints (GBNF / Regex Constrained Decoding)             |
|  - Base Foundation Model (e.g., Claude 3.5 Sonnet / GPT-4o / DeepSeek-Coder)       |
+-----------------------------------------+-----------------------------------------+
                                          | Code Candidate Output
                                          v
+-----------------------------------------------------------------------------------+
|                    DETERMINISTIC VERIFICATION ENGINE (DVE)                         |
|  +---------------------+  +----------------------+  +---------------------------+ |
|  |  Syntax & AST Parse |  | Static Type Checker  |  | Invariant Unit Validation | |
|  |  (Tree-sitter/Babel)|  | (tsc / mypy / pyright)|  | (Deterministic Ephemeral) | |
|  +----------+----------+  +----------+-----------+  +-------------+-------------+ |
+-------------|------------------------|----------------------------|---------------+
              |                        |                            |
       [ AST Error ]            [ Type Error ]               [ Test Failure ]
              |                        |                            |
              +------------------------+----------------------------+
                                       | Error Feedback Context
                                       v
                     +-----------------------------------+
                     | SELF-HEALING REFLECTION LOOP      |
                     | (Max Retries: N, Backoff & Prune) |
                     +-----------------+-----------------+
                                       |
                         Re-synthesize with Diagnostics
                                       |
                                       v (To Context Packet Compiler)
```

#### Komponen Kunci Arsitektur SDD Produksi:
1. **Deterministic Spec Ingestion**: Spesifikasi sistem ditulis dalam domain modeling deterministik (OpenAPI, JSON Schema, Interface Type Definitions). Spesifikasi ini diperlakukan sebagai *Single Source of Truth* (SSoT).
2. **Context Packet Compiler (CPC)**: Mengurai target repositori ke dalam graf ketergantungan (Dependency Graph). Alih-alih memasukkan seluruh file yang relevan, CPC hanya mengekstrak tipe antarmuka (type signatures) dan *public contracts* menggunakan AST Parser (Tree-sitter).
3. **Structured Grammars / Output Projection**: Output LLM dipaksa secara ketat (*constrained decoding*) untuk menghasilkan blok kode yang valid dan terisolasi atau file diff spesifik, bukan percakapan bebas.
4. **Closed-Loop Verification Engine**: Kode yang dihasilkan langsung diuji di runtime sandbox:
   * **Stage 1**: Parsing pohon sintaksis (AST Validation).
   * **Stage 2**: Pemeriksaan tipe statis (*Static Type Checking*) tanpa emisi runtime.
   * **Stage 3**: Validasi invarian berbasis unit tests yang disintesis dari spesifikasi awal.
5. **Self-Correction & Error Backpropagation**: Log kegagalan kompilator dan diagnostic engine diolah menjadi *error feedback packet* yang terstruktur (berisi: line number, error code, expected interface, received token) lalu diinjeksikan kembali ke LLM untuk sintesis perbaikan.

---

### 4. Why & What

| Dimensi | Raw "Vibe-Coding" | Specification-Driven Development (SDD) |
| :--- | :--- | :--- |
| **Paradigma** | *Conversational generation* (berbasis instruksi natural yang longgar). | *Deterministic synthesis* (berbasis spesifikasi formal dan grammar contract). |
| **Penanganan State** | Memori percakapan LLM (lossy, non-deterministic). | AST-aware repository state & ephemeral dependency context. |
| **Verifikasi** | Manual oleh manusia via review visual (*eyeballing*). | Otomatis via AST, Type-Checkers, Linters, dan Dynamic Invariant Tests. |
| **Regresi** | Sangat tinggi; LLM cenderung mengubah interface publik lain. | Nol; *bounded context* dikunci oleh interface definitions statis. |
| **Biaya Token** | Boros (chat history membengkak seiring iterasi). | Optimal (hanya mengekstrak interface signatures via AST pruning). |
| **Auditability** | Tidak terlacak; histori terfragmentasi di chat UI. | Sempurna; commit history terhubung dengan spec diff & compilation traces. |

#### Definisi Konseptual SDD Enterprise
Specification-Driven Development dalam rekayasa prompt adalah metodologi di mana prompt tidak ditulis sebagai kalimat perintah monolitik, melainkan **dikompilasi dari artefak spesifikasi perangkat lunak.** LLM diposisikan sebagai *transpiler* stokastik tingkat tinggi yang dibatasi oleh aturan formal, sementara mesin eksekusi lokal bertindak sebagai pemfilter deterministik yang memastikan tidak ada kode cacat yang masuk ke repositori.

---

### 5. How (Workflow Detail)

Alur kerja implementasi SDD produksi berjalan melalui 6 tahap berurutan:

```
[Phase 1: Spec Definition] 
       │  Input: OpenAPI 3.1 Spec / Entity Schemas / Contract Interfaces
       ▼
[Phase 2: Context Slicing & AST Extraction]
       │  Tool: Tree-sitter / TypeScript Compiler API
       │  Action: Ekstrak interface dependensi; singkirkan body implementasi
       ▼
[Phase 3: Metaprompt Dynamic Synthesis]
       │  Assembly: System Rules + Spec Contract + Skeleton Interfaces + AST Slices
       ▼
[Phase 4: LLM Constrained Inference]
       │  Execution: Model generate kandidat kode via deterministic temperature (< 0.2)
       ▼
[Phase 5: Local Sandbox Verification Gate]
       ├─ AST Parse Check (Syntax validity)
       ├─ Static Typecheck Check (tsc --noEmit / pyright)
       └─ Invariant Test Check (Unit execution against spec)
       │
   ┌───┴────────────────────────┐
[Pass]                        [Fail]
   │                            │
   ▼                            ▼
[Phase 6: Commit]             [Phase 5b: Diagnostic Extraction & Self-Healing Loop]
                                └─ Loop kembali ke Phase 3 dengan Diagnostic Packet
```

#### Detail Tahap Verifikasi Mandiri (Stage 5b)
Jika static type checker mendeteksi *type mismatch* (misal TS2322):
1. Error diagnostics diekstrak langsung dari compiler output: file target, nomor baris, kolom, kode error, dan pesan error lengkap.
2. Context Packet Compiler membangun prompt koreksi mini yang hanya menyertakan: interface yang dilanggar, kode implementasi yang gagal, dan stack trace compiler.
3. Model hanya meresintesis fungsi atau blok yang rusak, bukan keseluruhan file.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Bangunan vs. Mesin CNC Presisi
* **Vibe-Coding**: Anda menyewa tukang kayu dan berkata, *"Buatkan saya meja makan bergaya Skandinavia yang kokoh dan tampak elegan."* Tukang kayu mulai memotong kayu berdasarkan persepsinya. Hasilnya mungkin indah, tetapi tingginya 85 cm bukannya standar 75 cm, dan kakinya tidak muat di lantai ruang makan Anda.
* **Specification-Driven Development**: Anda merancang cetak biru CAD 3D (Spesifikasi), memprogram mesin pemotong CNC dengan toleransi 0.01 mm (Grammar/Constrained Decoding), lalu memasang sensor laser optik di ujung mesin (Static Compiler/AST Validator). Jika pemotongan melenceng 0.05 mm, mesin otomatis berhenti, mengkalibrasi ulang posisinya, dan melanjutkan pemotongan sesuai koordinat yang telah ditentukan secara matematis.

#### Diagram Kompilasi Context Packet

```
Raw Monorepo File System
┌──────────────────────────────────────────────┐
│  src/                                        │
│  ├── domain/payment.entity.ts (150 lines)    │
│  ├── infra/payment.repository.ts (400 lines) │
│  └── service/payment.service.ts              │
└──────────────────────────────────────────────┘
                       │
                       │ [ Tree-sitter Extraction Engine ]
                       ▼
Pruned Semantic Context (Token Saving: ~85%)
┌──────────────────────────────────────────────┐
│  // payment.entity.ts (AST Sliced)           │
│  export interface IPayment {                 │
│    id: UUID;                                 │
│    amount: Dinero;                           │
│    status: 'PENDING' | 'SETTLED';            │
│  }                                           │
│  // Body functions dropped completely!       │
└──────────────────────────────────────────────┘
                       │
                       │ [ Dynamic Prompt Assembler ]
                       ▼
Structured Context Packet -> Directed to Inference Engine
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Deterministic Invariant Enforcement (Python/Pydantic)
Contoh dasar bagaimana spesifikasi formal memandu LLM dan divalidasi langsung secara programmatic.

```python
# spec.py - The Single Source of Truth
from pydantic import BaseModel, Field, condecimal
from typing import Literal
from uuid import UUID

class TransferRequestSpec(BaseModel):
    transaction_id: UUID
    source_account: str = Field(pattern=r"^ACC-[0-9]{8}$")
    destination_account: str = Field(pattern=r"^ACC-[0-9]{8}$")
    amount: condecimal(gt=0, decimal_places=2)
    currency: Literal["USD", "EUR", "IDR"]

# Generator script utilizing Python runtime to validate synthesis
import json
from pydantic import ValidationError

def verify_generated_payload(raw_llm_json_output: str) -> TransferRequestSpec:
    """Memverifikasi secara deterministik output LLM terhadap spesifikasi formal."""
    try:
        data = json.loads(raw_llm_json_output)
        validated = TransferRequestSpec(**data)
        return validated
    except (ValidationError, json.JSONDecodeError) as e:
        raise ValueError(f"Contract Violation Detected:\n{str(e)}")
```

---

#### B. Practical Enterprise Example: Autonomous SDD Code Synthesis Engine
Berikut adalah sistem orkestrator tingkat produksi dalam TypeScript yang mengonsumsi spesifikasi antarmuka, meminta implementasi dari LLM, dan menjalankan loop verifikasi kompilasi lokal menggunakan TypeScript Compiler API secara in-memory.

##### 1. File Struktur
```
sdd-orchestrator/
├── src/
│   ├── ast-extractor.ts
│   ├── compiler-verifier.ts
│   └── orchestrator.ts
├── package.json
└── tsconfig.json
```

##### 2. `src/compiler-verifier.ts`
Modul untuk memvalidasi kode yang dihasilkan LLM secara *in-memory* menggunakan TypeScript Compiler API tanpa menulis ke disk.

```typescript
import * as ts from 'typescript';

export interface CompilationResult {
  success: boolean;
  diagnostics: string[];
}

export class InMemoryCompilerVerifier {
  private compilerOptions: ts.CompilerOptions = {
    noEmit: true,
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    strict: true,
    esModuleInterop: true,
    skipLibCheck: false,
  };

  /**
   * Mengompilasi string kode TypeScript di memori bersama context dependensi.
   * Mengembalikan hasil status kompilasi beserta daftar error diagnostik terformat.
   */
  public verify(
    candidateSource: string,
    contextDeclarations: Map<string, string>
  ): CompilationResult {
    const candidateFileName = '/virtual/candidate.ts';
    const virtualFiles = new Map<string, string>(contextDeclarations);
    virtualFiles.set(candidateFileName, candidateSource);

    const host = this.createVirtualCompilerHost(virtualFiles);
    const rootNames = Array.from(virtualFiles.keys());
    const program = ts.createProgram(rootNames, this.compilerOptions, host);
    
    // Ambil diagnostics sintaksis dan semantik
    const diagnostics = ts.getPreEmitDiagnostics(program);

    if (diagnostics.length === 0) {
      return { success: true, diagnostics: [] };
    }

    const formattedDiagnostics = diagnostics
      .filter((diag) => diag.file?.fileName === candidateFileName)
      .map((diag) => {
        const message = ts.flattenDiagnosticMessageText(diag.messageText, '\n');
        if (diag.file && diag.start !== undefined) {
          const { line, character } = diag.file.getLineAndCharacterOfPosition(diag.start);
          return `Line ${line + 1}, Col ${character + 1}: [TS${diag.code}] ${message}`;
        }
        return `[TS${diag.code}] ${message}`;
      });

    return {
      success: formattedDiagnostics.length === 0,
      diagnostics: formattedDiagnostics,
    };
  }

  private createVirtualCompilerHost(files: Map<string, string>): ts.CompilerHost {
    const defaultHost = ts.createCompilerHost(this.compilerOptions);

    return {
      ...defaultHost,
      getSourceFile: (fileName, languageVersion) => {
        const content = files.get(fileName);
        if (content !== undefined) {
          return ts.createSourceFile(fileName, content, languageVersion, true);
        }
        return defaultHost.getSourceFile(fileName, languageVersion);
      },
      fileExists: (fileName) => files.has(fileName) || defaultHost.fileExists(fileName),
      readFile: (fileName) => files.get(fileName) ?? defaultHost.readFile(fileName),
      writeFile: () => {}, // No-op, in-memory validation only
      useCaseSensitiveFileNames: () => true,
      getCanonicalFileName: (fileName) => fileName,
      getCurrentDirectory: () => '/',
      getNewLine: () => '\n',
    };
  }
}
```

##### 3. `src/orchestrator.ts`
Orkestrator inti yang mengelola siklus hidup SDD: pembuatan metaprompt, pemanggilan LLM, verifikasi via AST/Compiler, dan *self-healing loop*.

```typescript
import { InMemoryCompilerVerifier } from './compiler-verifier';

// Mock Client Interface (dapat menggunakan @anthropic-ai/sdk atau openai)
export interface ILLMClient {
  complete(prompt: { system: string; user: string }): Promise<string>;
}

export class SDDOrchestrationEngine {
  private verifier: InMemoryCompilerVerifier;

  constructor(private llmClient: ILLMClient) {
    this.verifier = new InMemoryCompilerVerifier();
  }

  /**
   * Menghasilkan implementasi kode dari spesifikasi antarmuka dengan garansi tipe statis.
   */
  public async synthesizeImplementation(
    specificationInterface: string,
    dependencyDeclarations: Map<string, string>,
    maxRetries: number = 3
  ): Promise<string> {
    let attempts = 0;
    let diagnosticsContext: string[] = [];

    // System prompt deterministik untuk spesifikasi ketat
    const systemPrompt = `You are an automated, deterministic TypeScript synthesis engine.
Rules:
1. Implement the requested interface strictly matching all invariants.
2. Emit ONLY the raw TypeScript code block within triple backticks without conversational filler.
3. Do not import unreferenced modules. Respect the provided dependencies.
4. Output must compile with strict TypeScript settings without errors.`;

    while (attempts < maxRetries) {
      attempts++;
      console.log(`[SDD-Engine] Synthesis attempt ${attempts}/${maxRetries}...`);

      const userPrompt = this.constructPrompt(
        specificationInterface,
        dependencyDeclarations,
        diagnosticsContext
      );

      const rawResponse = await this.llmClient.complete({
        system: systemPrompt,
        user: userPrompt,
      });

      const extractedCode = this.extractCodeBlock(rawResponse);

      // Verifikasi Deterministik
      const validationResult = this.verifier.verify(extractedCode, dependencyDeclarations);

      if (validationResult.success) {
        console.log(`[SDD-Engine] Synthesis successfully compiled on attempt ${attempts}.`);
        return extractedCode;
      }

      console.warn(
        `[SDD-Engine] Attempt ${attempts} failed compilation. Diagnostics:\n`,
        validationResult.diagnostics.join('\n')
      );

      // Injeksi error diagnostics untuk iterasi berikutnya (Self-Healing)
      diagnosticsContext = validationResult.diagnostics;
    }

    throw new Error(
      `[SDD-Engine] Failed to synthesize valid implementation after ${maxRetries} attempts.\n` +
      `Final Diagnostics:\n${diagnosticsContext.join('\n')}`
    );
  }

  private constructPrompt(
    spec: string,
    dependencies: Map<string, string>,
    diagnostics: string[]
  ): string {
    let prompt = `### CONTRACT SPECIFICATION TO IMPLEMENT:\n\`\`\`typescript\n${spec}\n\`\`\`\n\n`;

    if (dependencies.size > 0) {
      prompt += `### ENVIRONMENT CONTEXT DECLARATIONS:\n`;
      for (const [file, content] of dependencies.entries()) {
        prompt += `// ${file}\n${content}\n\n`;
      }
    }

    if (diagnostics.length > 0) {
      prompt += `\n### COMPILER DIAGNOSTIC ERRORS FROM PREVIOUS RUN:\n`;
      prompt += `Fix ALL the following compilation errors precisely:\n`;
      prompt += diagnostics.map((d) => `- ${d}`).join('\n');
      prompt += `\n\nReturn the entirely corrected TypeScript code.`;
    } else {
      prompt += `\nProvide the complete production-grade implementation of the specified interface.`;
    }

    return prompt;
  }

  private extractCodeBlock(content: string): string {
    const match = content.match(/```(?:typescript|ts)?\n([\s\S]*?)```/);
    return match ? match[1].trim() : content.trim();
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem: FinTech Core Banking API Migration
* **Institusi**: Perusahaan Neo-Bank Skala Regional (12 Juta Pengguna Aktif).
* **Problem**: Migrasi 250 microservices dari monolithic Java legacy ke TypeScript/Node.js event-driven architecture. Upaya awal menggunakan "vibe-coding" konvensional oleh 40 engineer menghasilkan:
  * 34% *runtime type failure* di production (akibat loose JSON-typing).
  * 28% pelanggaran idempotency keys pada distributed transactions.
  * $45,000 tagihan API OpenAI terbuang dalam sebulan akibat looping prompt manual yang tidak terstruktur.

#### Desain Solusi Berbasis SDD Engine
1. **SSoT Contract Ingestion**: Tim arsitektur mengonversi seluruh skema database dan gRPC Protobuf ke dalam OpenAPI 3.1 & Zod Schemas murni.
2. **Context Packets Pipeline**:
   * Komponen AST-Extractor menyaring seluruh model database internal sehingga model AI hanya menerima representasi DTO publik dan fungsi hashing idempotency.
   * Menggunakan Tree-sitter, *private members* dihilangkan dari konteks, mereduksi token input rata-rata per request sebesar 78% (dari ~14,000 token menjadi ~3,100 token).
3. **Automated Ephemeral Sandbox Verification**:
   * Setiap kode yang di-generate langsung dieksekusi di isolated container (Docker running in-memory tmpfs) untuk validasi unit tests: (a) Validasi schema via Zod, (b) Validasi atomisitas transaksi DB mock.
   * Jika gagal, trace log diumpankan kembali ke engine perbaikan otomatis (maksimal 2x perbaikan).

#### Metrik Hasil Transformasi (6 Bulan Pasca Implementasi)
* **Hallucination / Contract Drift Rate**: Turun dari **31.4%** menjadi **0.00%** (setiap kode yang tidak lolos static check ditolak sebelum masuk pipeline PR Git).
* **Developer Velocity**: Kecepatan migrasi per endpoint meningkat dari **4.5 jam/endpoint** menjadi **11 menit/endpoint**.
* **Total LLM API Cost Savings**: Penghematan sebesar **68%** berkat pemangkasan konteks berbasis AST.
* **Production Incident Severity 1**: Nol (0) insiden terkait *schema mismatches* dalam 180 hari operasional.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                    [DETERMINISM & QUALITY]
                             /\
                            /  \
                           /    \
                          /  *   \  <-- Enterprise SDD Target
                         /        \
                        /__________\
[LOW LATENCY & CHEAP COST]          [CREATIVE GENERATIVE FREEDOM]
```

1. **Latency vs. Accuracy (Compilation Retries)**:
   * *Trade-off*: Menambahkan local compiler check dan dynamic invariant testing memperpanjang durasi siklus generasi dari hitungan detik (~3-5 detik pada vibe-coding) menjadi ~15-45 detik jika melibatkan loop *self-healing* (1-3 kali kompilasi ulang).
   * *Mitigasi*: Jalankan sintesis secara asinkron dalam background worker queue (e.g., BullMQ) terintegrasi dengan GitHub Actions, alih-alih synchronous blocking UI.

2. **Token Cost vs. Context Pruning Complexity**:
   * *Trade-off*: Memotong konteks menggunakan AST Parser menghemat jutaan token LLM, tetapi memerlukan pemeliharaan infrastruktur parser lokal yang harus sinkron dengan setiap update sintaks bahasa pemrograman target.
   * *Mitigasi*: Gunakan *Tree-sitter WASM* bindings yang stabil dan terstandarisasi untuk multi-bahasa.

3. **Constrained Decoding vs. LLM Expressiveness**:
   * *Trade-off*: Memaksa model mematuhi grammar JSON/AST yang sangat ketat terkadang mengurangi performa penalaran tingkat tinggi (*chain-of-thought*) model.
   * *Mitigasi*: Pisahkan fase *Reasoning* (unconstrained CoT scratchpad) dengan fase *Code Synthesis* (strictly constrained extraction).

---

### 10. Common Mistakes & Troubleshooting

#### 1. Context Window Bloat via Whole-File Ingestion
* **Gejala**: LLM mulai melupakan validasi edge-case, respons melambat drastis, biaya token melonjak.
* **Akar Masalah**: Memasukkan file dependensi secara utuh termasuk body function implementasi internal yang tidak ada hubungannya dengan target spesifikasi saat ini.
* **Solusi**: Gunakan AST Slicing. Hanya ambil deklarasi tipe antarmuka publik (`interface`, `type`, `function signature` tanpa block `{ ... }`).

#### 2. Hallucinating Implicit Runtime Invariants
* **Gejala**: Kode berhasil dikompilasi oleh `tsc`, namun mengalami *panic* saat runtime (misal: mengakses array indeks ke-0 yang kosong, atau parsing timestamp non-ISO).
* **Akar Masalah**: TypeScript/Python Type Checkers hanya memvalidasi bentuk tipe data (*shape*), bukan batasan nilai (*value ranges/invariants*).
* **Solusi**: Sertakan runtime assertions (seperti Zod refinement atau Pydantic validators) di dalam file spesifikasi, bukan hanya static interfaces.

#### 3. Infinite Self-Healing Feedback Loops
* **Gejala**: Mesin orkestrator terus berputar meregenerasi kode hingga mencapai batas maksimum *timeout*, menghabiskan biaya API tanpa konvergensi perbaikan.
* **Akar Masalah**: Error feedback packet terlalu abstrak (misal: "This code failed compilation, fix it"), membuat LLM menebak-nebak dan mengulangi kesalahan sintaksis yang sama.
* **Solusi**: Sertakan exact line number, diagnostic code (e.g., `TS2345: Argument of type 'X' is not assignable to parameter of type 'Y'`), dan berikan potongan AST target secara presisi. Tetapkan batas *backoff* maksimum 3 percobaan.

---

### 11. Best Practices (Production Checklist)

#### Pre-Generation Gate
- [ ] Spesifikasi ditulis dalam format formal (OpenAPI 3.1, JSON Schema, atau Strict Zod Interfaces).
- [ ] Parsing AST lokal telah mengabstraksi dependensi eksternal (hanya menyertakan *type definitions*, tanpa implementasi internal).
- [ ] Injeksi instruksi sistem menggunakan *immutable structural rules* (larang komentar informal, larang modifikasi interface publik).

#### Inference Runtime Gate
- [ ] Set `temperature` ke $\le 0.1$ untuk memastikan hasil sintesis mendekati deterministik.
- [ ] Aktifkan *seed parameter* yang stabil (jika didukung oleh provider LLM) untuk reproducibility audit.
- [ ] Terapkan Token Budgeting: Batasi output token maksimum sesuai panjang kode yang diantisipasi (cegah run-away outputs).

#### Post-Generation Verification Gate
- [ ] AST parsing memeriksa keberadaan *syntax errors* secara lokal sebelum kompilasi penuh.
- [ ] Static type analysis dijalankan secara headless di memori (`tsc --noEmit`, `pyright`, dll).
- [ ] Dynamic unit invariant test dijalankan di container terisolasi (sandbox).
- [ ] Mekanisme self-healing dibatasi maksimal 3 kali perulangan dengan pesan error diagnostik terkompresi.
- [ ] Hash output kode dicatat untuk keperluan security auditing dan compliance.

---

### 12. Hands-on Practice

Buat dan simpan struktur project di: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/src hands-on/m02/spec
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node --save-dev
npx tsc --init
```

#### Langkah 1: Buat File Spesifikasi Kontrak
Simpan di `hands-on/m02/spec/user-service.contract.ts`:

```typescript
export interface UserProfile {
  id: string;
  email: string;
  age: number;
  roles: Array<'ADMIN' | 'OPERATOR' | 'VIEWER'>;
}

export interface IUserService {
  /**
   * Mengambil profile berdasarkan ID.
   * Harus melempar error Error('UserNotFound') jika ID tidak ada.
   */
  getUserById(id: string): Promise<UserProfile>;

  /**
   * Menambahkan peran baru ke pengguna.
   * Mencegah duplikasi peran.
   * Melempar Error('InvalidAgeForRole') jika age < 18 dan peran adalah 'ADMIN'.
   */
  assignRole(userId: string, newRole: 'ADMIN' | 'OPERATOR' | 'VIEWER'): Promise<UserProfile>;
}
```

#### Langkah 2: Buat Compiler Diagnostic Harness
Simpan di `hands-on/m02/src/harness.ts`:

```typescript
import * as ts from 'typescript';
import * as fs from 'fs';
import * as path from 'path';

export function runCompilerCheck(sourceCode: string, specPath: string): { success: boolean; errors: string[] } {
  const specContent = fs.readFileSync(specPath, 'utf8');
  const specFileName = '/virtual/spec.ts';
  const implFileName = '/virtual/impl.ts';

  const virtualFiles = new Map<string, string>([
    [specFileName, specContent],
    [implFileName, `import { UserProfile, IUserService } from './spec';\n` + sourceCode]
  ]);

  const options: ts.CompilerOptions = {
    noEmit: true,
    strict: true,
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS
  };

  const host: ts.CompilerHost = {
    ...ts.createCompilerHost(options),
    getSourceFile: (fileName, version) => {
      const content = virtualFiles.get(fileName);
      if (content !== undefined) {
        return ts.createSourceFile(fileName, content, version, true);
      }
      return ts.createCompilerHost(options).getSourceFile(fileName, version);
    },
    fileExists: (fileName) => virtualFiles.has(fileName) || ts.sys.fileExists(fileName),
    readFile: (fileName) => virtualFiles.get(fileName) ?? ts.sys.readFile(fileName),
  };

  const program = ts.createProgram([specFileName, implFileName], options, host);
  const diagnostics = ts.getPreEmitDiagnostics(program);

  const errors = diagnostics
    .filter(d => d.file?.fileName === implFileName)
    .map(d => {
      const msg = ts.flattenDiagnosticMessageText(d.messageText, '\n');
      const { line, character } = d.file!.getLineAndCharacterOfPosition(d.start!);
      return `Line ${line + 1}, Col ${character + 1}: [TS${d.code}] ${msg}`;
    });

  return {
    success: errors.length === 0,
    errors
  };
}

// Simulasi sintesis yang salah (akan memicu error compiler)
const buggyCodeCandidate = `
export class UserServiceImpl implements IUserService {
  private users: Map<string, UserProfile> = new Map();

  async getUserById(id: string): Promise<UserProfile> {
    const user = this.users.get(id);
    if (!user) throw new Error('UserNotFound');
    return user;
  }

  // Sengaja salah: return type void padahal spesifikasi menuntut Promise<UserProfile>
  async assignRole(userId: string, newRole: 'ADMIN' | 'OPERATOR' | 'VIEWER') {
    const user = await this.getUserById(userId);
    user.roles.push(newRole);
  }
}
`;

console.log("=== MENJALANKAN VERIFIKASI DETERMINISTIK PADA KANDIDAT KODE ===");
const result = runCompilerCheck(buggyCodeCandidate, path.join(__dirname, '../spec/user-service.contract.ts'));

if (!result.success) {
  console.log("Status: GAGAL (Kompiler Berhasil Menangkap Bug)");
  console.log("Daftar Diagnostic Error untuk Injeksi Feedback Loop:");
  result.errors.forEach(err => console.error(" -> ", err));
} else {
  console.log("Status: BERHASIL");
}
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan harness:
```bash
npx ts-node hands-on/m02/src/harness.ts
```
Output yang diharapkan:
```
=== MENJALANKAN VERIFIKASI DETERMINISTIK PADA KANDIDAT KODE ===
Status: GAGAL (Kompiler Berhasil Menangkap Bug)
Daftar Diagnostic Error untuk Injeksi Feedback Loop:
 ->  Line 12, Col 9: [TS2420] Class 'UserServiceImpl' incorrectly implements interface 'IUserService'.
  Types of property 'assignRole' are incompatible.
    Type '(userId: string, newRole: "ADMIN" | "OPERATOR" | "VIEWER") => Promise<void>' is not assignable to type '(userId: string, newRole: "ADMIN" | "OPERATOR" | "VIEWER") => Promise<UserProfile>'.
      Type 'Promise<void>' is not assignable to type 'Promise<UserProfile>'.
        Type 'void' is not assignable to type 'UserProfile'.
```

---

### 13. Exercise

#### Level: Easy
* **Tugas**: Perbaiki string implementasi `buggyCodeCandidate` pada `hands-on/m02/src/harness.ts` agar mematuhi seluruh kontrak dan lolos validasi `runCompilerCheck` dengan `success: true`.
* **Kriteria Evaluasi**: Status return bernilai `success: true` tanpa ada diagnostics error tersisa.

#### Level: Medium
* **Tugas**: Modifikasi `harness.ts` agar dapat menguji validasi runtime invariant. Tambahkan suite eksekusi dinamis menggunakan Jest atau fungsi eksekusi *in-memory* yang memverifikasi bahwa `assignRole` benar-benar melempar `Error('InvalidAgeForRole')` jika umur pengguna di bawah 18 tahun dan role yang ditetapkan adalah `ADMIN`.
* **Kriteria Evaluasi**: Validasi menolak kode yang tipe statisnya benar tetapi logika bisnis invariant-nya salah.

#### Level: Hard
* **Tugas**: Bangun CLI tool `sdd-synthesizer` yang membaca file OpenAPI JSON dan menghasilkan:
  1. Zod runtime schemas secara otomatis.
  2. Implementasi Express Route Handler yang diverifikasi secara dinamis via TypeScript Compiler API.
  3. Menggunakan LLM API nyata dengan *self-healing loop* jika hasil sintesis pertama gagal dikompilasi.
* **Kriteria Evaluasi**: CLI dapat menangani spesifikasi berukuran >50KB dengan tingkat keberhasilan kompilasi 100% pada *retry* $\le 2$.

---

### 14. Challenge

#### Skenario Kasus Kompleks: High-Frequency Settlement Ledger Engine
* **Konteks**: Anda memimpin migrasi modul *double-entry balance settlement* yang memproses transaksi bernilai triliunan rupiah per hari. Sistem lama menggunakan stored procedures SQL yang penuh *side-effects*. Anda diminta memimpin tim untuk menggunakan SDD Engine dalam menyintesis core logic baru dalam Rust atau TypeScript.
* **Persyaratan Sistem**:
  1. **Strict Balance Invariant**: Total debit harus selalu sama persis dengan total kredit pada setiap transaksi ledger batch ($\sum \text{debit} - \sum \text{credit} = 0$).
  2. **Zero Floating Point Imprecision**: Tidak boleh menggunakan tipe data float/double primitif. Harus menggunakan implementasi arbitary-precision integer atau Dinero/BigInt pattern.
  3. **Zero Untyped Dynamic Casting**: Dilarang menggunakan `any`, `unknown` tanpa type-guard assertion, atau type-casting berbahaya (`as unknown as TargetType`).
* **Instruksi Tantangan**:
  Rancang arsitektur sistem SDD mencakup skema spesifikasi input, parser dependensi, aturan grammar constrained decoding, dan verifier runner yang menjamin bahwa tidak ada satupun kandidat kode buatan LLM yang lolos verifikasi jika melanggar invariant balance di atas, meskipun kode tersebut valid secara sintaksis TypeScript. Dokumentasikan arsitektur ini dalam diagram interaksi komponen beserta strategi *fail-safe rejection*-nya.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic Questions

**1. Mengapa teknik "vibe-coding" berbasis chat konvensional berbahaya jika diterapkan pada repositori enterprise berskala besar?**
* A. Karena biaya token LLM selalu lebih mahal dibandingkan gaji software engineer.
* B. Karena ketiadaan spesifikasi formal dan *closed-loop verification* memicu *semantic drift*, halusinasi kontrak, dan regresi tersembunyi.
* C. Karena model LLM tidak dilatih untuk memahami bahasa selain Python.
* D. Karena Git tidak dapat melacak commit yang kodenya dihasilkan oleh AI.
> **Jawaban: B** — Tanpa spesifikasi formal dan kompilator deterministik, output LLM bersifat stokastik dan cenderung menghasilkan halusinasi antarmuka yang merusak arsitektur monorepo.

**2. Apa fungsi utama dari Context Packet Compiler (CPC) dalam arsitektur SDD?**
* A. Menghapus semua unit test yang gagal agar pipeline CI/CD tetap hijau.
* B. Menerjemahkan bahasa alami ke dalam format audio.
* C. Mengurai AST repositori untuk memangkas konteks non-esensial dan hanya menyuntikkan type signatures relevan ke LLM.
* D. Menyimpan riwayat percakapan chat ke dalam distributed cache Redis.
> **Jawaban: C** — CPC memaksimalkan SNR (Signal-to-Noise Ratio) pada attention window dengan hanya mengekstrak kontrak tipe dan menyaring detail implementasi privat via AST.

**3. Manakah nilai *temperature* yang paling tepat untuk sintesis kode deterministik dalam kerangka kerja SDD?**
* A. 1.5
* B. 0.8
* C. 0.0 sampai 0.1
* D. -1.0
> **Jawaban: C** — Nilai temperature rendah ($\le 0.1$) meminimalkan keacakan pemilihan token pada sampling probability distribution, memastikan output konsisten dan patuh pada grammar.

**4. Apa yang dimaksud dengan *Constrained Decoding* dalam konteks generasi kode menggunakan LLM?**
* A. Membatasi LLM hanya bekerja selama jam kerja kantor.
* B. Membatasi proses sampling model pada runtime inference menggunakan tata bahasa formal (seperti GBNF atau Regex) sehingga token yang dihasilkan dijamin valid secara struktural.
* C. Memblokir akses internet pada mesin pengembang saat menulis prompt.
* D. Menolak prompt yang mengandung kata kunci terlarang.
> **Jawaban: B** — Constrained decoding secara matematis memodifikasi *logit distribution* saat inference sehingga model tidak dapat menghasilkan token di luar aturan grammar formal (misal: JSON valid atau format kode target).

**5. Manakah artefak yang bertindak sebagai *Single Source of Truth* (SSoT) dalam Specification-Driven Development?**
* A. Slack thread diskusi kebutuhan bisnis.
* B. Komentar inline di dalam file legacy code.
* C. Spesifikasi formal terstruktur seperti OpenAPI, JSON Schema, atau Interface Type Definitions.
* D. Memori sesi percakapan LLM.
> **Jawaban: C** — SDD mensyaratkan spesifikasi formal yang dapat diurai secara terstruktur oleh mesin sebagai acuan tunggal seluruh proses generasi dan verifikasi kode.

---

#### B. Intermediate Questions

**6. Mengapa static type checking saja (seperti `tsc --noEmit`) belum cukup untuk menjamin kebenaran kode hasil sintesis SDD?**
* A. Karena compiler static type checking membutuhkan resource RAM yang terlalu besar.
* B. Karena type checker hanya memverifikasi kompatibilitas bentuk/struktur tipe, bukan invariant logika runtime atau batasan nilai bisnis.
* C. Karena LLM selalu berhasil menipu static type checker.
* D. Karena TypeScript tidak mendukung asynchronous execution.
> **Jawaban: B** — Suatu fungsi bisa saja 100% valid secara tipe data (misal: mengembalikan tipe `number`), namun menghasilkan nilai negatif pada field saldo rekening yang melanggar invariant bisnis perbankan.

**7. Dalam loop *self-healing* SDD, informasi apa yang paling krusial untuk dimasukkan kembali ke context window LLM saat terjadi error?**
* A. Seluruh file log server berukuran puluhan megabyte.
* B. Permintaan maaf dan instruksi umum untuk mencoba kembali.
* C. Diagnostic error code terstruktur, nomor baris/kolom, expected vs received types, dan irisan AST yang rusak.
* D. Seluruh history commit Git dari 6 bulan terakhir.
> **Jawaban: C** — Diagnostic packet yang terarah dan ringkas memungkinkan LLM memahami secara tepat kesalahan sintaksis atau ketidakcocokan tipe tanpa mengalami context pollution.

**8. Bagaimana cara kerja pemangkasan konteks berbasis AST (AST Slicing) dalam menghemat biaya token LLM?**
* A. Menghapus komentar dokumentasi dan mengganti nama variabel menjadi satu huruf.
* B. Mengonversi kode implementasi fungsi menjadi `/* omitted body */` dan hanya mempertahankan tanda tangan tipe publik pada file dependensi.
* C. Mengompres file kode menggunakan algoritma GZIP sebelum dikirimkan ke model.
* D. Menghapus semua file CSS dan HTML dari prompt.
> **Jawaban: B** — Model hanya memerlukan kontrak bentuk interaksi (tanda tangan fungsi dan struktur tipe data) dari file dependensi untuk menulis kode baru, bukan bagaimana file dependensi tersebut diimplementasikan secara internal.

**9. Apa risiko terbesar dari membiarkan model LLM menulis unit test-nya sendiri tanpa dipandu oleh spesifikasi independen?**
* A. LLM akan membuat test suite yang sengaja disesuaikan dengan bug yang dibuatnya (*Tautological Testing*), sehingga semua test selalu pass.
* B. Format file test tidak akan kompatibel dengan runner seperti Jest atau Pytest.
* C. Waktu eksekusi unit test menjadi 100 kali lebih lambat.
* D. Token LLM akan habis sebelum test selesai ditulis.
> **Jawaban: A** — Tautological testing terjadi ketika model mereplikasi halusinasi logikanya ke dalam assertion unit test-nya sendiri, menghasilkan *false confidence* bahwa kode telah berjalan dengan benar.

**10. Pada arsitektur enterprise, di lapisan manakah closed-loop verification paling optimal dieksekusi?**
* A. Di dalam database production menggunakan trigger.
* B. Di sisi frontend browser pengguna sebelum mengirim request.
* C. Di ephemeral execution sandbox lokal (atau worker isolasi CI/CD) sebelum kode di-commit ke source control.
* D. Di dalam prompt pengguna sebagai teks deskripsi tambahan.
> **Jawaban: C** — Verifikasi harus dilakukan secara terisolasi pada lingkungan sandbox lokal deterministik untuk memastikan kode terbukti valid dan aman sebelum menyentuh repositori inti.

---

#### C. Skenario Kasus Produksi

**11. Skenario 1**: Sebuah tim migrasi backend menyadari bahwa orkestrator SDD mereka mengalami kegagalan berulang (*infinite loop retry*) saat mencoba mengimplementasikan controller yang mengimpor pustaka pihak ketiga yang baru dirilis bulan lalu. Apa akar penyebab paling mungkin dan bagaimana tindakan mitigasi arsitekturnya?
* **Analisis & Solusi**:
  * *Akar Masalah*: LLM mengalami halusinasi signature API karena data latihannya memiliki *knowledge cutoff* sebelum rilis pustaka tersebut. Model mencoba menebak method-method yang tidak ada, yang kemudian berulang kali ditolak oleh compiler.
  * *Solusi Arsitektur*: Context Packet Compiler harus mengekstrak deklarasi tipe TypeScript (`.d.ts`) resmi pustaka pihak ketiga tersebut langsung dari `node_modules` lokal, lalu menyuntikkannya secara eksplisit ke dalam *environment context declaration* metaprompt sebelum inference dijalankan.

**12. Skenario 2**: Sistem orkestrator SDD Anda berhasil memvalidasi sintaksis dan tipe static TypeScript dari 100 endpoint API baru, tetapi saat deployment ke *staging environment*, 20% endpoint gagal menangani payload JSON kosong dengan status `500 Internal Server Error` (bukan `400 Bad Request`). Di mana kelemahan arsitektur SDD Anda?
* **Analisis & Solusi**:
  * *Kelemahan*: Verifikasi hanya bersandar pada Static Type Checking (`tsc`) tanpa Runtime Schema Validation (seperti Zod/class-validator) yang terhubung dengan dynamic execution test. TypeScript types terhapus saat kompilasi runtime (*type erasure*), sehingga tidak memvalidasi runtime payload boundary.
  * *Solusi Arsitektur*: Perbarui spesifikasi kontrak dengan schema parser runtime (misal: Zod schemas). Tambahkan tahapan verifikasi ke-3 pada sandbox engine: eksekusi unit test dinamis yang secara otomatis menguji endpoint dengan input mutasi invalid (fuzzing) untuk memverifikasi emisi status HTTP `400`.

**13. Skenario 3**: Sebuah institusi finansial melarang pengiriman kode bisnis internal ke endpoint LLM pihak ketiga publik karena kepatuhan data privasi. Namun, model open-source lokal (on-premise) yang lebih kecil memiliki performa penalaran arsitektur yang lebih rendah dan sering menghasilkan kesalahan sintaksis. Bagaimana Anda mendesain ulang arsitektur SDD untuk mengatasi keterbatasan ini?
* **Analisis & Solusi**:
  * *Desain Ulang Arsitektur*:
    1. **De-anonymization & Isolation**: Gunakan AST engine untuk mengganti nama entitas domain sensitif menjadi identifier generic sebelum dikirim ke model jika memilih jalur masking, ATAU tetap gunakan model on-premise dengan optimasi berikut:
    2. **Constrained Grammar Sampling (GBNF/SGLang/Outlines)**: Kunci model open-source lokal pada level decoding inference menggunakan grammar file kaku. Model tidak diizinkan menghasilkan free text sama sekali, hanya blok AST token yang valid.
    3. **Micro-Task Decomposition**: Pecah tugas pembuatan modul besar menjadi hierarki micro-synthesis: sintesis antarmuka $\rightarrow$ sintesis parsing schema $\rightarrow$ sintesis core logic per fungsi tunggal. Semakin kecil cakupan tugas, semakin tinggi reliabilitas model open-source lokal.

---

### 16. Summary

1. **Transformasi Fundamental**: "Vibe-coding" adalah proses stokastik yang rentan kegagalan arsitektur dan tidak memenuhi standar rekayasa perangkat lunak enterprise. **Specification-Driven Development (SDD)** mengubah dinamika ini dengan memperlakukan LLM sebagai mesin translasi terikat, bukan perancang bebas.
2. **Peran Spesifikasi Formal**: Fondasi determinisme SDD terletak pada *Single Source of Truth* (SSoT) yang tidak ambigu—seperti OpenAPI 3.1, JSON Schema, atau Interface Type Definitions. Spesifikasi mendikte seluruh struktur input dan batasan output.
3. **Efisiensi via AST Context Slicing**: Alih-alih membanjiri *context window* LLM dengan basis kode utuh, compiler konteks cerdas memanfaatkan parser AST untuk mengekstrak tanda tangan tipe dan public interface saja, menghemat token hingga >70% sekaligus menghilangkan halusinasi dependensi internal.
4. **Closed-Loop Feedback Sandbox**: Keandalan kelas industri dicapai bukan dari penulisan prompt yang berbunga-bunga, melainkan dari **loop verifikasi otomatis** (AST Parsing $\rightarrow$ Static Type Checking $\rightarrow$ Dynamic Runtime Invariants) yang dilengkapi dengan mekanisme *self-healing* terukur. Kode yang tidak lolos kompilasi tidak akan pernah masuk ke repositori produksi.