# Kurikulum Enterprise: Technical Writer & Docs-as-Code Architecture
## Bab 04: Markup Languages (CommonMark, GFM, MDX, AsciiDoc)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Document Architect / Lead Technical Writer diharapkan mampu:
- **Menganalisis & Memilih Format Markup**: Menerapkan evaluasi berbasis kapabilitas teknis antara CommonMark, GitHub Flavored Markdown (GFM), MDX (v3), dan AsciiDoc sesuai kebutuhan sistem dokumentasi modern, developer portal, dan AI ingest pipeline.
- **Menguasai AST (Abstract Syntax Tree) Pipelines**: Mengimplementasikan custom AST visitor dan transformer menggunakan ekosistem `unified` (`remark`, `rehype`, `unist`) untuk MDX/Markdown, serta Ruby/Node.js Extensions untuk Asciidoctor.
- **Membangun Arsitektur Docs-as-Code Multi-Repository**: Mendesain dan mengoperasikan pipeline dokumentasi enterprise skala besar menggunakan Antora (AsciiDoc) dan Next.js/Contentlayer/MDX Bundler dengan zero-trust security isolation.
- **Optimasi AI/RAG Document Ingestion**: Mengekstraksi, memvalidasi, dan melakukan semantic chunking berbasis node AST untuk ingestion ke Vector Database tanpa kehilangan konteks metadata, tabel relasional, atau blok kode.
- **Mitigasi Keamanan Injeksi**: Mengeliminasi celah Cross-Site Scripting (XSS), Arbitrary Code Execution (ACE), dan Local File Inclusion (LFI) pada build time maupun runtime MDX serta AsciiDoc dynamic include.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Dasar Parser & Lexer**: Konsep *lexical analysis*, tokenisasi, dan pohon sintaks abstrak (AST).
- **TypeScript/Node.js Lanjut**: Manipulasi Object, Streams, Asynchronous Programming, serta sistem modul ESM (ECMAScript Modules).
- **Tooling Web & Bundler**: Pemahaman mendalam mengenai Webpack, Vite, esbuild, dan bagaimana SSR/SSG/Hydration bekerja di framework modern (Next.js, Astro).
- **Git & CI/CD**: Workflow monorepo/polyrepo, submodule, artifacts management, dan GitHub Actions/GitLab CI.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi markup di level enterprise bukan sekadar merender HTML statis dari file teks, melainkan memproses data semi-terstruktur melalui pipeline kompilasi deterministik.

```
+---------------+     +-------------+     +---------------+     +---------------+     +---------------+
| Raw Document  | --> | Lexer /     | --> | MDAST /       | --> | Transformation| --> | Target Engine |
| (.md, .mdx,   |     | Tokenizer   |     | Asciidoctor   |     | Plugins (AST) |     | (HTML, JSON,  |
|  .adoc)       |     |             |     | Object Model  |     |               |     |  Vector Chunks|
+---------------+     +-------------+     +---------------+     +---------------+     +---------------+
```

#### 3.1. Spesifikasi CommonMark vs GFM
- **CommonMark**: Standar formal tanpa ambiguitas untuk Markdown. Memecahkan masalah parsing inkonsisten dengan mendefinisikan algoritma parsing 2-fase:
  1. *Block Structure*: Identifikasi baris demi baris menggunakan leaf blocks dan container blocks (blok kutipan, list item).
  2. *Inline Structure*: Parsing karakter demi karakter untuk memproses penekanan (emphasis), tautan, dan HTML entities.
- **GFM (GitHub Flavored Markdown)**: *Strict superset* dari CommonMark. Menambahkan formalitas sintaksis untuk:
  - Tables (GFM extension spec 4.10)
  - Task List Items
  - Autolinks (`www.*`, email, protocol-prefixed)
  - Strikethrough (`~text~`)
  - Disallowed Raw HTML (tag `<script>`, `<iframe>`, `<style>`, `<xmp>` di-escape pada tahap parsing AST).

#### 3.2. Anatomi Internal MDX v3
MDX bukan sekadar Markdown dengan JSX; MDX adalah dialek yang mengombinasikan parser CommonMark/GFM (`micromark`) dengan parser JavaScript (Acorn).

```
 Raw .mdx Source
       |
       v
 [micromark + micromark-extension-mdxjs]
       |
       +---> Acorn Parser (Parse expression inside { } & ESM import/export)
       |
       v
 mdast (Markdown Abstract Syntax Tree)
       |
  (mdast-util-mdx)
       |
       v
 hast (Hypertext Abstract Syntax Tree)
       |
  (esast generation via Recast/Babel)
       |
       v
 Executable JavaScript Module (Component Function)
```

1. **Parser Execution**: Karakter parsing Markdown didelegasikan ke `micromark`. Ketika karakter penanda JS ditemukan (misal `{`, `<`, `import`, `export`), kontrol parser diserahkan ke **Acorn**.
2. **AST Representations**:
   - `mdast`: Merepresentasikan struktur semantik dokumen (Nodes: `root`, `paragraph`, `heading`, `mdxJsxFlowElement`, `mdxjsEsm`).
   - `hast`: Mengubah node Markdown menjadi elemen HTML virtual (Nodes: `element`, `text`, `comment`).
   - `esast`: Node AST JavaScript (ESTree) yang merepresentasikan kode komponen fungsional yang siap dibundel oleh esbuild/Webpack.

#### 3.3. Arsitektur Objek AsciiDoc (Asciidoctor Internal Model)
Berbeda dengan ekosistem JavaScript AST yang bertumpu pada JSON primitives (`unist`), Asciidoctor diimplementasikan di atas Document Object Model (DOM) berorientasi objek yang sangat ketat:
- **`Document`**: Unit root kompilasi yang menyimpan metadata global, atribut sistem/pengguna, dan *catalog of references*.
- **`Section`**: Node struktural hierarkis (Level 0 - Level 5) yang secara otomatis menghitung ID dan nomor bagian.
- **`Block`**: Wadah konten atomik (Paragraph, Listing, Table, Open Block, Quote, Example). Setiap blok membawa atribut: `id`, `title`, `roles`, `attributes` (key-value hash).
- **Sistem Preprocessor, Reader, dan Includer**: Asciidoctor membaca dokumen baris demi baris menggunakan stack-based reader. Directive `include::target.adoc[]` ditangani pada fase *preprocessing line-stream*, memungkinkan rekursi bersyarat berbasis deklarasi `ifdef::[]`, `ifndef::[]`, dan `ifeval::[]`.

---

### 4. Why & What

| Fitur / Dimensi | CommonMark | GFM | MDX v3 | AsciiDoc (Asciidoctor) |
| :--- | :--- | :--- | :--- | :--- |
| **Spesifikasi Formal** | Sangat Ketat (IETF draft level) | Ketat (GFM Spec) | Bergantung versi compiler | Spesifikasi de facto (Asciidoctor) & Eclipse Spec |
| **Kemampuan Ekstensi** | Sangat Rendah (Intentionally Minimal) | Rendah (Fixed extensions) | Ekstrem (Melalui JSX/React/Vue/Svelte) | Sangat Tinggi (Macro, BlockProcessor, Postprocessor) |
| **Ekosistem Tooling** | Multi-bahasa (C, JS, Rust, Go) | GitHub Native, Multi-bahasa | Node.js / JavaScript Bundler | Ruby, Java (AsciidoctorJ), Node (Asciidoctor.js) |
| **Dukungan Multi-Repo** | Tidak Ada (Perlu custom tooling) | Tidak Ada | Perlu Orchestration Engine | Bawaan (Native via Antora) |
| **Kompleksitas Inklusi** | Tidak Mendukung Inklusi | Tidak Mendukung Inklusi | ESM (`import Component from './...'`) | Direktif Asli (`include::target.adoc[]`) |
| **Model Keamanan** | Aman (Bergantung HTML sanitizer) | Moderat (Disallowed tags filter) | **Kritis** (Dapat mengeksekusi Arbitrary JS jika tidak disanitasi) | Moderat (Risiko LFI jika *include* tidak dibatasi) |
| **Kesesuaian Penggunaan** | README, Komentar Kode, Chat | Dokumentasi Repo GitHub | Design Systems, Interactive API Playgrounds | Manual Enterprise, Spesifikasi Standar, Multi-repo Docs |

---

### 5. How (Workflow Detail)

Arsitektur produksi modern membutuhkan pemrosesan konten melalui sistem validasi dan transformasi otomatis. Berikut adalah alur pipeline transformasi Docs-as-Code enterprise:

```
               Pipeline Arsitektur Docs-as-Code Enterprise
               ===========================================

 [Content Sources]
   ├── Repo A: core-api-docs (AsciiDoc)
   ├── Repo B: ui-components (MDX)
   └── Repo C: release-notes (GFM)
           │
           │ (Git Subtree / Antora Collector / Webhooks)
           ▼
 [Stage 1: Ingestion & Linting]
   ├── Vale (Prose & Style Consistency Linter)
   ├── Markdownlint / AsciiDoc syntax validator
   └── Secret Scanning (Detect private keys, tokens)
           │
           ▼
 [Stage 2: AST Processing & Transformation]
   ├── AST Ingestion (unified / asciidoctor pipeline)
   ├── Dynamic Path Canonicalization
   ├── Callout Insertion & Syntax Highlighting via Shiki/Prism
   └── Metadata Extraction & Enrichment (reading time, word count)
           │
           ├───► [Branch A: Static / SSR Portal Production]
           │        ├── esbuild / Next.js Static Export
           │        ├── Content Delivery Network (CDN) Deployment
           │        └── WAF & Edge Cache Invalidation
           │
           └───► [Branch B: AI / RAG Ingestion Pipeline]
                    ├── Semantic Chunking (Node-preserving: Headings/Code/Tables)
                    ├── Vector Embedding Generator (OpenAI / Cohere)
                    └── Vector Database Upsert (Qdrant / Pinecone / Milvus)
```

#### Alur Eksekusi:
1. **Source Synchronization**: CI Pipeline mendeteksi commit di berbagai repositori layanan dan memicu orkestrasi build.
2. **Syntax & Style Enforcement**: Mesin *Vale* memvalidasi konsistensi tata bahasa, *markdownlint* memastikan standardisasi CommonMark/GFM.
3. **AST Traversal**: Parsing file mentah menjadi AST. Plugin custom mengintervensi pohon sintaks untuk memvalidasi broken link, menghapus elemen sensitif, dan menginjeksi token otentikasi sampel.
4. **Bifurkasi Target**:
   - **Target Web UI**: Dikompilasi menjadi artefak HTML/CSS/JS siap saji.
   - **Target AI RAG**: Struktur pohon dipecah berdasarkan section boundary, mempertahankan konteks parent-child hingga disimpan dalam basis data vektor.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
- **CommonMark**: *Bata Standar*. Kuat, seragam, tidak fleksibel, tetapi dijamin cocok di setiap bangunan di seluruh dunia.
- **GFM**: *Bata Berongga Berpengunci*. Bata standar yang ditambahkan alur untuk memasang kabel (tabel, task list) khusus ekosistem konstruksi GitHub.
- **MDX**: *Smart Wall Panel*. Dinding yang di dalamnya tertanam panel layar sentuh, sensor, dan sirkuit listrik interaktif (React Component). Indah dan fleksibel, tetapi jika instalasi kabel buruk, dapat menyebabkan korsleting fatal (XSS / Runtime Crashes).
- **AsciiDoc**: *Sistem Rangka Baja Pabrikan (Industrial Steel Frame)*. Dirancang untuk gedung pencakar langit ribuan halaman; memiliki slot pengait modular (`include::[]`), mampu menahan beban berat, dan didukung standar cetak teknis industri militer/penerbangan (DocBook/PDF).

#### Diagram Transformasi AST pada MDX
```
Source MDX:
  # Title
  <Alert type="warning">Notice</Alert>

Parsing:
  [Root]
    ├── [Heading (depth: 1)]
    │      └── [Text (value: "Title")]
    └── [mdxJsxFlowElement (name: "Alert", attributes: [{type: "mdxJsxAttribute", name: "type", value: "warning"}])]
           └── [Text (value: "Notice")]

Compilation to JavaScript AST (ESTree):
  import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
  export default function MDXContent(props) {
    return _jsxs("div", {
      children: [
        _jsx("h1", { children: "Title" }),
        _jsx(Alert, { type: "warning", children: "Notice" })
      ]
    });
  }
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: AsciiDoc Attribute Substitution & Conditional Directives
Contoh penggunaan modularitas dasar pada AsciiDoc yang tidak dapat dilakukan oleh CommonMark native tanpa external template engine.

File: `service-definition.adoc`
```asciidoc
= User Authentication API
:version: v2.4.0
:environment: production
:client_type: enterprise

API Version: {version}
Current Environment: {environment}

ifeval::["{client_type}" == "enterprise"]
[WARNING]
====
Dokumentasi ini berisi endpoint mTLS khusus untuk lisensi enterprise. Jangan distribusikan secara publik.
====
include::mtls-auth-spec.adoc[leveloffset=+1]
endif::[]

ifeval::["{client_type}" == "community"]
include::basic-auth-spec.adoc[leveloffset=+1]
endif::[]
```

---

#### 7.2. Practical Example (Production-Grade): Custom Unified MDX AST Pipeline
Implementasi pipeline transformasi berbasis TypeScript dengan validasi keamanan AST, pencegahan eksekusi tag berbahaya, penambahan ID heading otomatis, dan ekstraksi metadata untuk index pencarian.

```typescript
// File: src/pipeline/mdx-compiler.ts

import { compile } from '@mdx-js/mdx';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { visit } from 'unist-util-visit';
import type { Root as MdastRoot, Code as MdastCode } from 'mdast';
import type { Root as HastRoot, Element as HastElement } from 'hast';
import type { Plugin } from 'unified';

// Interface untuk metadata hasil ekstraksi
export interface ExtractionMetadata {
  headings: Array<{ depth: number; text: string; id?: string }>;
  codeLanguages: string[];
  readingTimeMinutes: number;
}

// Custom Remark Plugin: Ekstraksi Heading & Telemetri Konten
export function remarkExtractMetadata(metadata: ExtractionMetadata): Plugin<[], MdastRoot> {
  return () => (tree: MdastRoot) => {
    let wordCount = 0;

    visit(tree, (node) => {
      if (node.type === 'heading') {
        const textNode = node.children.find((c) => c.type === 'text');
        if (textNode && 'value' in textNode) {
          metadata.headings.push({
            depth: node.depth,
            text: textNode.value,
          });
        }
      }

      if (node.type === 'code') {
        const codeNode = node as MdastCode;
        if (codeNode.lang && !metadata.codeLanguages.includes(codeNode.lang)) {
          metadata.codeLanguages.push(codeNode.lang);
        }
      }

      if (node.type === 'text' && 'value' in node) {
        const words = (node.value as string).trim().split(/\s+/).filter(Boolean);
        wordCount += words.length;
      }
    });

    metadata.readingTimeMinutes = Math.ceil(wordCount / 200);
  };
}

// Custom AST Plugin: Mencegah eksekusi script injection via Raw HTML nodes
export function rehypeSecurityEnforcer(): Plugin<[], HastRoot> {
  return () => (tree: HastRoot) => {
    visit(tree, 'element', (node: HastElement, index, parent) => {
      const dangerousTags = ['script', 'iframe', 'object', 'embed', 'style'];
      if (dangerousTags.includes(node.tagName.toLowerCase())) {
        if (parent && typeof index === 'number') {
          // Ganti dangerous node dengan warning comment
          parent.children[index] = {
            type: 'comment',
            value: `REMOVED_UNAUTHORIZED_NODE: ${node.tagName}`,
          };
        }
      }
    });
  };
}

// Skema sanitasi khusus untuk komponen MDX
const customSanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    'callout',
    'apireference',
    'interactiveplayground',
  ],
  attributes: {
    ...defaultSchema.attributes,
    callout: ['type', 'title'],
    apireference: ['endpoint', 'method'],
    interactiveplayground: ['initialCode', 'language'],
    div: [...(defaultSchema.attributes?.div || []), 'className'],
    code: [...(defaultSchema.attributes?.code || []), 'className'],
  },
};

// Fungsi Kompilasi Produksi
export async function compileEnterpriseMdx(
  source: string,
  allowedComponents: string[] = ['Callout', 'ApiReference', 'InteractivePlayground']
): Promise<{ compiledJs: string; metadata: ExtractionMetadata }> {
  const metadata: ExtractionMetadata = {
    headings: [],
    codeLanguages: [],
    readingTimeMinutes: 0,
  };

  const compiledFile = await compile(source, {
    outputFormat: 'function-body',
    development: false,
    remarkPlugins: [
      remarkGfm,
      [remarkExtractMetadata, metadata],
    ],
    rehypePlugins: [
      rehypeSlug,
      [rehypeAutolinkHeadings, { behavior: 'wrap' }],
      rehypeSecurityEnforcer,
      [rehypeSanitize, customSanitizeSchema],
    ],
  });

  return {
    compiledJs: String(compiledFile),
    metadata,
  };
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Unifikasi Dokumentasi Multi-Cloud Enterprise (NexusCloud Technologies)
- **Kondisi Awal**: NexusCloud memiliki 180 microservices yang tersebar di 40 repository Git terpisah. Format dokumentasi terfragmentasi antara CommonMark standar, wiki Confluence, dan Markdown informal.
  - Masalah: Patahnya tautan referensi silang (cross-repo), kebocoran kode rahasia di dalam Markdown, dan rendering dokumentasi publik memakan waktu CI/CD hingga 42 menit.
- **Arsitektur Solusi**:
  1. **Standardisasi Format Dual-Tier**:
     - *AsciiDoc & Antora* diwajibkan untuk Architecture Manuals, Platform Governance, dan Deployment Guides. Memungkinkan validasi skema multi-repo tanpa duplikasi data.
     - *MDX v3* digunakan khusus untuk API Portal Publik yang memerlukan komponen interaktif (interactive token inject, run-in-sandbox API playground).
  2. **Pipeline Orkestrasi CI/CD**:
     - Engine Antora memetakan repositori melalui file manifest `antora-playbook.yml`.
     - AST Link Validator menelusuri seluruh link antar-repo pada level parsing AST. Jika ada ID referensi yang hilang, CI otomatis *fail-fast* sebelum deployment CDN.
  3. **Hasil Metrik Produksi**:
     - Waktu kompilasi turun dari 42 menit ke 3 menit 12 detik melalui caching build stage AST.
     - Broken links di documentation portal turun menjadi 0% (sebelumnya rata-rata 14% dari total halaman setelah rilis microservice baru).
     - RAG Ingestion latency untuk technical support bot dipercepat 85% karena dokumen telah terspesifikasi dalam bentuk semantik block yang rapi tanpa perlu regex parsing manual.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Markdown (CommonMark/GFM) | MDX (v3 Engine) | AsciiDoc (Asciidoctor) |
| :--- | :--- | :--- | :--- |
| **Parsing & Build Speed** | **Sangat Cepat** (Native C/Rust parsers mencapai >100k lines/sec). | **Lambat** (Transpilasi Acorn + ESTree generation + esbuild bundling). | **Sedang - Cepat** (Ruby engine sedang; Node/Java engine scalable). |
| **Memory Footprint** | Rendah (~10-30 MB per 10k pages). | Sangat Tinggi (~500 MB - 2 GB per 10k pages karena V8 memory overhead). | Moderat (~150-300 MB per 10k pages). |
| **Architectural Complexity** | Sangat Rendah. Perlu sedikit konfigurasi. | Sangat Tinggi. Menuntut sinkronisasi antara dependencies JS/React dengan pipeline docs. | Moderat ke Tinggi. Memerlukan kepatuhan skema Antora atau pipeline toolchain DocBook. |
| **Attack Surface (Security)** | Minimal. Terbatas pada unescaped raw HTML. | **Kritis**. Eksekusi modul kustom JS, SSR injection, component pollution. | Moderat. Jalur LFI via unbounded `include::` attributes. |
| **TCO (Total Cost of Ownership)** | Rendah. Siapa pun dapat menulis; tidak butuh engineer spesialis. | Tinggi. Membutuhkan Frontend Platform Engineer untuk merawat ekosistem komponen docs. | Moderat. Membutuhkan kurva belajar sintaksis khusus untuk penulis teknis. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1. **Mengabaikan Sanitasi pada MDX Dynamic Runtime**: Mengambil konten MDX dari database atau user-generated input dan langsung mengeksekusinya via `@mdx-js/mdx` tanpa sandbox. Ini membuka celah Remote Code Execution (RCE) / XSS pada runtime SSR.
2. **Infinite Recursion pada AsciiDoc Inclusions**: File A menyertakan File B, dan File B menyertakan File A tanpa penjaga kondisi `ifdef::[]`. Asciidoctor akan mengalami *stack overflow exception*.
3. **Mencampuradukkan Semantik Block**: Menggunakan indentasi spasi sembarangan pada GFM untuk menulis nested list di dalam tabel, yang menyebabkan *lexer state desynchronization* dan merusak AST.
4. **Hydration Mismatch pada MDX Component**: Menggunakan tag HTML native di dalam MDX yang menghasilkan nested `<p>` di dalam `<p>` saat dikonversi ke React element, merusak Virtual DOM client.

#### 10.2. Troubleshooting Guide
- **Gejala: "MDX compilation fails with 'Unexpected token / Cannot parse expression'"**
  - *Root Cause*: Penulis menggunakan tanda kurung kurawal ganda murni `{{ key: value }}` atau karakter `<` tanpa di-escape, yang dianggap sebagai ekspresi JavaScript/JSX oleh parser Acorn.
  - *Solusi*: Terapkan plugin remark untuk meng-escape karakter kurawal di luar blok kode, atau konversi ekspresi literal menjadi string template.
- **Gejala: "Asciidoctor: include file not found / target outside base_dir"**
  - *Root Cause*: Keamanan internal Asciidoctor berjalan di level mode `SECURE` atau `SERVER`, melarang pembacaan path relatif di luar direktori kerja eksekusi.
  - *Solusi*: Konfigurasikan opsi `safe` level di engine (`safe: 'server'`) dan definisikan parameter `base_dir` secara absolut pada konfigurasi runtime processor.

---

### 11. Best Practices (Production Checklist)

#### Pre-commit & CI Validation
- [ ] Terapkan linter sintaks otomatis (`markdownlint-cli2` untuk GFM/MDX, `asciidoctor-lint` untuk AsciiDoc).
- [ ] Jalankan security audit pada semua custom MDX components menggunakan static analysis (ESLint AST rules).
- [ ] Validasi integritas tautan anchor (`lychee` atau custom AST cross-reference validator) pada CI gate.

#### Parsing & Performance Architecture
- [ ] Hindari transpilasi MDX on-the-fly pada saat runtime request SSR; wajib lakukan pre-compilation saat build phase atau simpan output ESTree ke database/cache storage.
- [ ] Batasi kedalaman rekursi direktif include (`max_include_depth = 5`) untuk mencegah serangan denial-of-service (DoS) via *cyclic document expansion*.
- [ ] Implementasikan memory profiling pada Node.js heap jika memproses lebih dari 5,000 file Markdown per build batch.

#### Docs-as-Code Infrastructure
- [ ] Kunci (lock) versi dependensi compiler (`@mdx-js/mdx`, `unified`, `asciidoctor`) pada `package.json` untuk mencegah breaking changes pada parser grammar.
- [ ] Gunakan custom schema pada `rehype-sanitize` untuk membersihkan tag berbahaya tanpa merusak custom web components.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah Node.js semantic parser utility yang memecah file dokumen teknis (Markdown/GFM) menjadi unit-unit JSON semantik berdasarkan *Header Node Boundary* untuk keperluan AI Vector Search Ingestion.

#### Setup Struktur Direktori
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node unist-util-visit unified remark-parse remark-gfm --save
npx tsc --init
```

Perbarui `tsconfig.json` agar mengaktifkan target ESM:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

Perbarui `package.json` untuk menambahkan `"type": "module"`.

#### File: `hands-on/m02/src/semantic-chunker.ts`
```typescript
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import type { Root, Content, Heading, Text } from 'mdast';
import * as fs from 'fs';

export interface DocumentationChunk {
  id: string;
  sectionTitle: string;
  depth: number;
  content: string;
  metadata: {
    hasCodeBlock: boolean;
    hasTable: boolean;
    characterCount: number;
  };
}

export function chunkMarkdownByHeadings(markdownSource: string): DocumentationChunk[] {
  const processor = unified().use(remarkParse).use(remarkGfm);
  const ast = processor.parse(markdownSource) as Root;

  const chunks: DocumentationChunk[] = [];
  let currentChunk: DocumentationChunk | null = null;

  function flushCurrentChunk() {
    if (currentChunk && currentChunk.content.trim().length > 0) {
      currentChunk.metadata.characterCount = currentChunk.content.length;
      chunks.push(currentChunk);
    }
  }

  for (const node of ast.children) {
    if (node.type === 'heading') {
      // Selesaikan blok sebelum membuka blok baru
      flushCurrentChunk();

      const headingNode = node as Heading;
      const headingText = headingNode.children
        .filter((child): child is Text => child.type === 'text')
        .map((child) => child.value)
        .join(' ');

      currentChunk = {
        id: `chunk-${chunks.length + 1}-${headingText.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
        sectionTitle: headingText,
        depth: headingNode.depth,
        content: '',
        metadata: {
          hasCodeBlock: false,
          hasTable: false,
          characterCount: 0,
        },
      };
    } else {
      // Jika belum menemukan heading awal, buat root fallback
      if (!currentChunk) {
        currentChunk = {
          id: 'chunk-0-intro',
          sectionTitle: 'Introduction',
          depth: 0,
          content: '',
          metadata: {
            hasCodeBlock: false,
            hasTable: false,
            characterCount: 0,
          },
        };
      }

      // Tandai metadata blok
      if (node.type === 'code') {
        currentChunk.metadata.hasCodeBlock = true;
      }
      if (node.type === 'table') {
        currentChunk.metadata.hasTable = true;
      }

      // Serialisasi sederhana dari node content (bisa dikembangkan menggunakan remark-stringify)
      // Untuk kepraktisan ekstraksi teks:
      currentChunk.content += JSON.stringify(node) + '\n';
    }
  }

  flushCurrentChunk();
  return chunks;
}

// Simulasi Pipeline Execution
const sampleContent = `
# Platform Architecture Specification

Selamat datang di dokumentasi internal platform arsitektur.

## 1. Gateway Security Engine

API Gateway menerapkan validasi JWT otomatis pada setiap ingress traffic.

\`\`\`yaml
security:
  jwt:
    issuer: https://auth.enterprise.internal
\`\`\`

## 2. Distributed Database Schema

Tabel berikut menunjukkan konfigurasi shard cluster:

| Region | Shard Count | Replication Factor |
| :--- | :--- | :--- |
| AP-SOUTHEAST-1 | 16 | 3 |
| US-EAST-1 | 32 | 3 |
`;

const result = chunkMarkdownByHeadings(sampleContent);
console.log('HASIL SEMANTIC CHUNKING UNTUK INGESTION:');
console.log(JSON.stringify(result, null, 2));
```

#### Langkah Uji Coba:
```bash
npx tsc
node dist/semantic-chunker.js
```

---

### 13. Exercise

#### Level Easy
Tuliskan konfigurasi file Vale (`.vale.ini`) yang membatasi penggunaan kalimat pasif (passive voice) dan mendeteksi kesalahan penulisan nama brand (contoh: "Github" seharusnya "GitHub", "asciidoc" seharusnya "AsciiDoc") pada file Markdown.

#### Level Medium
Buatlah sebuah *Remark Plugin* kustom (`remark-external-links.ts`) menggunakan ekosistem `unist-util-visit` yang secara otomatis mendeteksi semua link Markdown (`node.type === 'link'`). Jika URL diawali dengan `http://` atau `https://` (eksternal), tambahkan atribut HTML `target="_blank"` dan `rel="noopener noreferrer"` saat dikonversi ke HAST.

#### Level Hard
Rancang pipeline validasi AsciiDoc menggunakan JavaScript API (`asciidoctor.js`) yang memverifikasi bahwa:
1. Tidak ada dokumen yang memiliki kedalaman heading level melompat (misal: dari Level 1 langsung ke Level 3 tanpa Level 2).
2. Semua direktif `include::[]` harus berada dalam root repository dan tidak boleh merujuk ke direktori parent (`../`).
3. Output validasi harus menghasilkan file laporan `audit-report.json` yang berisi detail line number, error code, dan severity.

---

### 14. Challenge

**Studi Kasus Konseptual: The Sovereign Cloud Offline Documentation Engine**

Sebuah konsorsium industri pertahanan memerlukan sistem dokumentasi teknis *air-gapped* (tanpa akses internet sama sekali) yang menggabungkan:
1. Ribuan manual operasi berspesifikasi MIL-STD dalam format AsciiDoc.
2. Dashboard visualisasi telemetri hardware interaktif yang ditulis menggunakan React/MDX.
3. Mesin AI pencarian semantik lokal yang berjalan di server fisik terisolasi.

**Instruksi Masalah:**
- Anda bertindak sebagai Principal Technical Document Architect. Rancang arsitektur pipeline build deterministik terpadu yang dapat mengompilasi kedua format tersebut ke dalam satu single-page application (SPA) yang aman tanpa mengeksekusi unsafe JS injection dari penulis manual pihak ketiga.
- Jelaskan strategi Anda dalam mengurai dan memetakan dokumen AsciiDoc multi-level ke dalam Vector Database semantik lokal (Chunking boundary, attribute scoping, table linearization).
- Bagaimana Anda menangani dependensi aset gambar, skema interaktif, dan penomoran halaman yang konsisten saat dokumen diekspor ke PDF standar percetakan dan ke Web Portal secara simultan?

*Format Jawaban: Dokumen Architecture RFC (Request for Comments) mencakup System Topology Diagram, Ingestion Flow, Security Model, dan Failure Recovery Mechanism.*

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (1 - 5)
1. **Apa perbedaan struktural utama antara parser CommonMark murni dengan parser GitHub Flavored Markdown (GFM)?**
   - *Jawaban*: CommonMark hanya mendefinisikan sintaksis inti Markdown tanpa ekstensi tabel, strikethrough, autolink, dan task lists. GFM adalah strict superset dari CommonMark yang membakukan ekstensi tersebut dan menambahkan mekanisme sanitasi disallowed HTML tags pada fase parsing.
2. **Pada ekosistem `unified`, apa peran dari MDAST dan HAST?**
   - *Jawaban*: MDAST (*Markdown Abstract Syntax Tree*) adalah representasi pohon sintaks abstrak berbasis Markdown semantik (heading, list, code), sedangkan HAST (*Hypertext Abstract Syntax Tree*) merepresentasikan struktur dokumen HTML virtual (element, properties, children) sebelum diserialisasi menjadi string HTML atau JSX.
3. **Mengapa direktif `include::[]` pada AsciiDoc dieksekusi pada tahap Preprocessor, bukan pada tahap AST Traversal?**
   - *Jawaban*: Karena `include::[]` beroperasi pada stream baris mentah (*raw line streams*). Hal ini memungkinkan parser menyisipkan konten dokumen lain secara kontekstual sebelum parsing tokenisasi struktural (seperti headings, block containers, dan ifdef conditions) dimulai.
4. **Apa fungsi dari parser Acorn di dalam siklus kompilasi MDX v3?**
   - *Jawaban*: Acorn bertindak sebagai parser JavaScript (ECMAScript) yang membedah sintaks ekspresi di dalam kurung kurawal `{ ... }` dan statemen ESM (`import` / `export`) yang disematkan di dalam dokumen Markdown.
5. **Bagaimana format CommonMark menangani karakter spasi di akhir baris untuk hard line breaks?**
   - *Jawaban*: Sesuai spesifikasi CommonMark, hard line break dibentuk dengan menambahkan dua atau lebih spasi di akhir baris sebelum newline, atau dengan menggunakan karakter backslash (`\`) langsung sebelum newline.

#### Soal Intermediate (6 - 10)
6. **Sebutkan celah keamanan yang paling berbahaya ketika mengeksekusi MDX di lingkungan server-side rendering (SSR) dengan konten tidak tepercaya (untrusted source), dan sebutkan teknik pencegahannya!**
   - *Jawaban*: Celah Remote Code Execution (RCE) dan Cross-Site Scripting (XSS). Karena MDX mengevaluasi komponen dan ekspresi JS, penyerang dapat menyisipkan kode berbahaya seperti `import { exec } from 'child_process'`. Pencegahannya meliputi: melarang ESM imports melalui konfigurasi compiler, menerapkan runtime sanitasi via `rehype-sanitize`, dan mengeksekusi evaluasi fungsi di dalam sandbox terisolasi (misal: isolated-vm atau WebAssembly sandbox).
7. **Dalam arsitektur Antora untuk AsciiDoc, jelaskan konsep `component-version-module`!**
   - *Jawaban*: Ini adalah struktur hierarki pengalamatan konten terdistribusi. *Component* mewakili unit fungsional (misal: API Gateway), *Version* mewakili cabang rilis (misal: v2.0), dan *Module* adalah namespace dalam komponen (misal: `ROOT` atau modul fitur). Struktur ini memungkinkan resolusi tautan absolut antar-repositori yang independen dari struktur direktori fisik Git.
8. **Mengapa pemotongan teks secara acak (misal: chunking per 500 kata) tidak disarankan untuk dokumen Markdown teknis yang akan di-ingest ke Vector Database AI?**
   - *Jawaban*: Karena teknik pemotongan mentah dapat membelah node struktural penting di tengah jalan (memotong blok kode sintaksis, memutus baris tabel relasional, atau memisahkan penjelasan teknis dari heading utamanya), sehingga menghilangkan konteks semantik yang krusial bagi AI embeddings.
9. **Jelaskan apa yang terjadi jika plugin HAST mengubah sebuah node menjadi tagName yang tidak terdaftar dalam skema sanitasi `rehype-sanitize`!**
   - *Jawaban*: Sanitizer akan menghapus tag tersebut atau mencopot atribut yang tidak diizinkan sesuai aturan whitelist. Jika konfigurasi sanitasi mengharuskan unwrap, konten teks di dalamnya tetap dipertahankan tetapi wrapper pembungkusnya dibuang dari pohon HAST.
10. **Bagaimana cara kerja mekanisme *attribute substitution* pada AsciiDoc dan apa bedanya dengan dynamic templating pada MDX?**
    - *Jawaban*: Pada AsciiDoc, attribute substitution adalah substitusi berbasis referensi teks statis/kondisional (`{variable_name}`) yang diselesaikan secara deterministik pada fase pra-kompilasi. Pada MDX, templating adalah eksekusi dinamis JavaScript ekspresi (`{variableName}`) yang dievaluasi pada saat eksekusi runtime komponen React/JSX.

#### Soal Skenario Kasus Produksi (11 - 13)
11. **Skenario A**: CI/CD pipeline dokumentasi enterprise Anda yang memproses 12,000 dokumen MDX mengalami *Out of Memory (JavaScript Heap OOM)* saat menjalankan perintah static export. Profiling menunjukkan masalah berada pada tahapan kompilasi esbuild dan Webpack. Solusi arsitektural apa yang harus Anda terapkan tanpa mengurangi jumlah dokumen?
    - *Solusi Rekayasa*:
      1. Matikan transpilasi komponen dinamis serentak dalam memori; terapkan strategi *chunked batch processing* (pisahkan kompilasi per sub-path dokumentasi).
      2. Ganti `outputFormat: 'program'` dengan `outputFormat: 'function-body'` pada compiler MDX untuk mengekspor fungsi evaluasi serializable murni tanpa membundel ulang runtime framework di setiap halaman.
      3. Terapkan AST caching berbasis hashing konten (content hash check SHA-256). CI hanya mengompilasi ulang dokumen MDX yang mengalami mutasi git diff.
12. **Skenario B**: Tim Technical Writer menemukan bahwa setelah memigrasikan dokumen arsitektur dari GFM ke AsciiDoc, build pipeline Antora gagal me-resolve tautan `xref:services:auth.adoc[]` dan menghasilkan status broken references secara acak saat dijalankan di branch CI multirepo. Di mana titik kegagalan sistematis ini biasanya terjadi?
    - *Solusi Rekayasa*:
      1. Periksa sinkronisasi file manifest `antora.yml` di setiap repository target. Inkonsistensi nama modul atau versi komponen pada `antora.yml` menyebabkan parser Antora gagal mendaftarkan namespace ke dalam Content Catalog internal.
      2. Periksa definisi branch/tag pada playbook file (`antora-playbook.yml`). Jika branch tracking tidak didefinisikan secara eksplisit, pipeline dapat mengambil commit lama dari cache lokal runner CI.
      3. Pastikan format path referensi silang menyertakan komponen dan modul secara absolut jika target berada di luar modul yang sedang diproses (`xref:component:module:page.adoc[]`).
13. **Skenario C**: Perusahaan Anda membangun developer portal yang memungkinkan komunitas menyumbang ekstensi dokumentasi open-source via Markdown. Namun, portal menggunakan renderer MDX terpadu. Bagaimana Anda memisahkan boundary rendering antara dokumen internal yang memiliki privilege akses komponen interaktif dan dokumen komunitas eksternal yang rawan script injection?
    - *Solusi Rekayasa*:
      1. Buat sistem *Dual Compilation Pipeline Boundary*: Dokumen internal dialirkan ke `EnterpriseMdxPipeline` dengan hak impor komponen JSX dan Acorn parsing penuh.
      2. Dokumen komunitas dialirkan ke `StrictCommonMarkPipeline` menggunakan compiler terisolasi yang menonaktifkan parsing MDX ekspresi sepenuhnya (`micromark-extension-mdxjs` dimatikan), meng-escape semua raw HTML, dan menerapkan `rehype-sanitize` dengan aturan ketat (*Strict Whitelist*).
      3. Jalankan pipeline dokumen komunitas di bawah isolation container sandbox atau Web Worker terpisah sebelum artefak digabungkan ke web portal utama.

---

### 16. Summary
- Pemilihan bahasa markup untuk enterprise bukanlah masalah preferensi sintaksis, melainkan kecocokan arsitektural: **CommonMark/GFM** untuk standardisasi teks universal dan keamanan tinggi; **MDX** untuk dokumentasi berbasis antarmuka reaktif dan developer portal kaya interaksi; **AsciiDoc** untuk penerbitan teknis skala masif, multi-repository, dan dokumentasi yang membutuhkan modularitas sistemik tinggi (*include & conditional engines*).
- Memahami struktur internal parser melalui pemrosesan AST (**MDAST, HAST, ESTree, Asciidoctor DOM**) adalah kunci untuk membangun tooling custom, otomatisasi Docs-as-Code, enforcement keamanan konten, dan ekstraksi chunk semantik untuk integrasi sistem Artificial Intelligence (AI/RAG).
- Pada tataran produksi, dokumentasi harus diperlakukan setara dengan kode software: wajib melewati static analysis, linting integritas, AST validation, security sanitization, dan build optimization berbasis caching deterministik.