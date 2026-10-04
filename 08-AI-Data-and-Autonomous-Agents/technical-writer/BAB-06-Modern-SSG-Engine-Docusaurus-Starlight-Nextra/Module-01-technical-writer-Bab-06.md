# Bab 06: Modern SSG Engine — Docusaurus, Starlight, & Nextra

## Module 01: Engine Architecture, AST Pipelines, & AI Documentation Workflows

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menganalisis Arsitektur Internal SSG Modern**: Membedah perbedaan fundamental antara arsitektur Single Page Application (SPA) berbasis Webpack pada Docusaurus, Islands Architecture berbasis Vite/Astro pada Starlight, dan React Server Components (RSC) berbasis Next.js App Router pada Nextra.
- **Mengembangkan Custom AST Plugins**: Membangun ekstensi pipeline *Unified* (`remark` dan `rehype`) untuk memvalidasi, mentransformasikan, dan menyuntikkan schema metadata agen AI (seperti manifest Model Context Protocol / MCP) langsung ke dalam Abstract Syntax Tree dokumen.
- **Mengoptimalkan Metrik Runtime Dokumen Skala Enterprise**: Menerapkan strategi pemuatan partial hydration dan zero-JS baseline guna mencapai Time-to-First-Byte (TTFB) < 200ms dan Core Web Vitals (INP, LCP, CLS) bernilai hijau pada repositori dokumentasi berskala > 10.000 halaman.
- **Mendeteksi dan Memitigasi Edge Cases MDX Compilation**: Mengisolasi dan menangani error kompilasi JSX/MDX v3, masalah *hydration mismatch*, circular component resolution, serta memory leaks pada CI/CD runners.
- **Mendesain Workflow Docs-as-Code Terintegrasi AI**: Merancang arsitektur ingest otomatis dari *tool definitions* (OpenAPI/JSON-Schema) agen otonom menjadi dokumentasi interaktif yang *type-safe* dan teruji secara otomatis (*automated linting & twoslash testing*).

---

### 2. Concept Overview

Dokumentasi teknis untuk sistem modern—khususnya pada domain *AI, Data, & Autonomous Agents*—bukan lagi sekadar kumpulan file Markdown statis yang dirender menjadi HTML murni. Dokumentasi agen AI menuntut integrasi interaktif: rendering *tool call payloads*, visualisasi graf eksekusi LangGraph, eksekusi playground sandboxed di browser, dan sinkronisasi real-time terhadap perubahan skema API model. 

Untuk memenuhi kebutuhan ini, industri beralih ke **Modern Static Site Generators (SSG)** berbasis komponen reaktif. Tiga engine utama memimpin paradigma ini dengan model eksekusi yang berbeda:

```
[Markdown / MDX Content] 
           │
           ▼
[Unified Processor Engine]
  ├── MDAST (Markdown AST via remark)
  └── HAST (HTML AST via rehype)
           │
           ▼
┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
│     Docusaurus (Meta)     │     Starlight (Astro)     │       Nextra (Vercel)     │
├───────────────────────────┼───────────────────────────┼───────────────────────────┤
│ • Full React SPA          │ • Islands Architecture    │ • React Server Components │
│ • Client-side Router      │ • Zero-JS by Default      │ • Hybrid SSR / SSG        │
│ • Webpack Bundler         │ • Vite Powered            │ • Turbopack / Next.js     │
│ • Monolithic Hydration    │ • Selective Hydration     │ • Streaming Architecture  │
└───────────────────────────┴───────────────────────────┴───────────────────────────┘
```

#### Mental Model & Teori Inti

1. **Content-as-Data**: Konten Markdown/MDX diperlakukan sebagai kode sumber (*source code*) yang tunduk pada tahap *lexing*, *parsing*, *tree-transformation*, dan *compilation*.
2. **Unified Pipeline**: Pemrosesan dokumen mengandalkan ekosistem **Unified.js**:
   - `remark`: Memetakan Markdown ke **MDAST** (Markdown Abstract Syntax Tree).
   - `rehype`: Mengubah MDAST menjadi **HAST** (HTML Abstract Syntax Tree) dan melakukan manipulasi DOM sebelum rendering.
   - `MDX Compiler`: Mengompilasi tag JSX di dalam HAST menjadi fungsi eksekusi React/Astro.
3. **Hydration Continuum**: 
   - *Full Hydration (Docusaurus)*: Mengunduh bundle React lengkap dan merestorasi seluruh tree komponen pada browser klien.
   - *Partial/Island Hydration (Starlight)*: Seluruh halaman adalah HTML statis murni tanpa JavaScript runtime, kecuali komponen tertentu yang dideklarasikan secara eksplisit (misal: `<AgentPlayground client:visible />`).
   - *Server-Driven (Nextra)*: Struktur halaman dievaluasi di level RSC (React Server Components), meminimalkan client JavaScript untuk markup statis dan hanya mengirim interaktivitas pada daun komponen (*leaf nodes*).

---

### 3. Why It Matters

Pada platform rekayasa AI dan Agen Otonom (misalnya ekosistem multi-agent, inference gateway, dan framework orkestrasi), dokumentasi teknis menghadapi beban sistemik berikut:

- **Kompleksitas Skema API Dinamis**: Agen AI memiliki ratusan *tools* dengan skema input/output JSON-Schema yang berubah seiring update model. Menulis dokumentasi secara manual menyebabkan divergensi antara kode produksi dan dokumentasi (*schema drift*).
- **Scale-Up Bottleneck**: Tool internal korporat dengan ribuan endpoint sering kali menyebabkan kehabisan memori (*Out Of Memory / OOM*) pada static generator tradisional (seperti Gatsby generasi lama atau Docusaurus v1) saat CI/CD pipeline membangun ribuan rute sekaligus.
- **Kebutuhan Komponen Interaktif Terisolasi**: Developer membutuhkan visualizer payload token real-time, canvas state machine, dan OpenAPI testing console langsung di halaman dokumentasi tanpa mengorbankan kecepatan loading halaman bagi pembaca referensi biasa.
- **Searchability untuk LLM (RAG-Ready Documentation)**: Dokumentasi teknis modern harus mengekspos representasi semantik terstruktur (misal: JSON-LD atau Markdown bersih via route `/index.json` / `/llms.txt`) agar dapat diindeks secara akurat oleh sistem Retrieval-Augmented Generation (RAG) internal perusahaan.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan perjalanan dokumen dari raw Markdown/MDX hingga menjadi artefak deployment yang dioptimalkan pada ketiga engine:

```
+-----------------------------------------------------------------------------------+
|                           PHASE 1: INGESTION & PARSING                            |
+-----------------------------------------------------------------------------------+
  [ .md / .mdx Source ] ---> [ unified() / remark-parse ] ---> [ MDAST Tree ]
                                                                     |
                                      +------------------------------+
                                      | [Custom Remark Plugins]
                                      | - MCP Tool Schema Validator
                                      | - Agent Prompt Token Counter
                                      v
                               [ Mutated MDAST ]
                                      |
+-----------------------------------------------------------------------------------+
|                        PHASE 2: HAST COMPILATION & ROUTING                        |
+-----------------------------------------------------------------------------------+
                                      | [remark-rehype]
                                      v
                                 [ HAST Tree ]
                                      |
                                      +------------------------------+
                                      | [Custom Rehype Plugins]
                                      | - Code-block Twoslash Syntax
                                      | - Heading ID Injection
                                      v
                           [ MDX Evaluation Pipeline ]
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+------------------+                                      +------------------+
| Docusaurus Engine|                                      | Starlight Engine |
+------------------+                                      +------------------+
| - Webpack Plugin |                                      | - Vite Pipeline  |
| - Layout Wrapper |                                      | - Static Islands |
| - Client SPA Gen |                                      | - Zero-JS Output |
+------------------+                                      +------------------+
         |                                                         |
         v                                                         v
[ Single Bundle HTML + JS ]                               [ Pure HTML + Target Island ]
(Hydrates whole document)                                 (Hydrates only dynamic widget)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 The Abstract Syntax Tree (AST) Life Cycle

Pipeline dokumen modern digerakkan oleh metamorfosis AST:

```
Code: `# Get Agent Status`
  --> MDAST: { type: 'heading', depth: 1, children: [{ type: 'text', value: 'Get Agent Status' }] }
    --> HAST: { type: 'element', tagName: 'h1', properties: { id: 'get-agent-status' }, children: [...] }
      --> React/JSX: `<h1 id="get-agent-status">Get Agent Status</h1>`
```

Ketika mengeksekusi MDX v3, node yang memiliki sintaks JSX (seperti `<AgentConfigPanel threshold={0.8} />`) diperlakukan sebagai node MDAST bertipe `mdxJsxFlowElement` atau `mdxJsxTextElement`. Jika parser menemukan karakter yang tidak valid menurut spesifikasi XML/JSX (misal: unescaped bracket `<` pada penulisan pseudocode tanpa codeblock), kompilasi akan *crash* saat build time.

#### 5.2 Hydration Strategies: Mengapa Starlight & Nextra Mengungguli Docusaurus di Edge

- **Docusaurus (React SPA)**: Menghasilkan HTML statis untuk SEO, tetapi begitu file JavaScript termuat di klien, seluruh halaman di-mount ulang oleh ReactDOM. Akibatnya, browser mengeksekusi hydration untuk ribuan paragraf teks statis yang sebenarnya tidak memerlukan event listener.
- **Starlight (Astro Islands)**: Menganalisis file dokumen secara komprehensif. Jika sebuah dokumen hanya menggunakan Markdown biasa dan komponen presentasional murni, output akhirnya adalah **0 KB JavaScript**. Jika menyertakan komponen interaktif:
  ```astro
  <InteractiveAgentGraph client:idle />
  ```
  Astro hanya menyuntikkan script runtime kecil yang menunda pemuatan komponen interaktif tersebut hingga thread browser berada pada status idle (`requestIdleCallback`).
- **Nextra (RSC Model)**: Memanfaatkan Next.js React Server Components. Layout sidebar, TOC (Table of Contents), dan konten teks diproses eksklusif di server. Hanya search dialog dan theme toggle yang memuat bundle JavaScript klien.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem dokumentasi AI berbasis plugin AST kustom: sebuah **Remark Plugin** TypeScript berkemampuan tinggi yang mendeteksi metadata agen AI, memvalidasi skema tool agen menggunakan **Zod**, dan mengubahnya menjadi komponen visual interaktif tanpa runtime overhead manual.

#### File: `plugins/remark-agent-schema.ts`

```typescript
import { visit } from 'unist-util-visit';
import { z } from 'zod';
import type { Root, Code, Parent } from 'mdast';
import type { Plugin } from 'unified';

// Skema validasi untuk Tool Definition Agen AI
const AgentToolSchema = z.object({
  name: z.string().min(1),
  description: z.string(),
  parameters: z.object({
    type: z.literal('object'),
    properties: z.record(
      z.object({
        type: z.string(),
        description: z.string(),
        enum: z.array(z.string()).optional(),
      })
    ),
    required: z.array(z.string()).default([]),
  }),
});

export type AgentTool = z.infer<typeof AgentToolSchema>;

export interface RemarkAgentSchemaOptions {
  componentName?: string;
  strictValidation?: boolean;
}

/**
 * Remark Plugin: Mengubah codeblock bertanda ```agent-tool
 * menjadi komponen visual interaktif <AgentToolViewer />
 */
export const remarkAgentSchema: Plugin<[RemarkAgentSchemaOptions?], Root> = (
  options = {}
) => {
  const componentName = options.componentName ?? 'AgentToolViewer';
  const isStrict = options.strictValidation ?? true;

  return (tree: Root, file) => {
    visit(tree, 'code', (node: Code, index: number | undefined, parent: Parent | undefined) => {
      // Hanya intersep code block dengan bahasa 'agent-tool'
      if (node.lang !== 'agent-tool' || index === undefined || !parent) {
        return;
      }

      let parsedPayload: unknown;
      try {
        parsedPayload = JSON.parse(node.value);
      } catch (err) {
        const errorMsg = `Invalid JSON inside agent-tool code block at line ${node.position?.start.line}: ${(err as Error).message}`;
        if (isStrict) {
          file.fail(errorMsg, node);
        } else {
          file.message(errorMsg, node);
          return;
        }
      }

      // Validasi skema tool
      const validationResult = AgentToolSchema.safeParse(parsedPayload);
      if (!validationResult.success) {
        const issues = validationResult.error.issues
          .map((i) => `${i.path.join('.')}: ${i.message}`)
          .join(', ');
        const errorMsg = `Schema validation failed for agent-tool at line ${node.position?.start.line}: ${issues}`;
        
        if (isStrict) {
          file.fail(errorMsg, node);
        } else {
          file.message(errorMsg, node);
          return;
        }
      }

      const validToolData: AgentTool = validationResult.data;

      // Transformasikan node Code menjadi MDX JSX Element
      const mdxNode = {
        type: 'mdxJsxFlowElement',
        name: componentName,
        attributes: [
          {
            type: 'mdxJsxAttribute',
            name: 'name',
            value: validToolData.name,
          },
          {
            type: 'mdxJsxAttribute',
            name: 'description',
            value: validToolData.description,
          },
          {
            type: 'mdxJsxAttribute',
            name: 'schemaPayload',
            value: JSON.stringify(validToolData.parameters),
          },
          {
            type: 'mdxJsxAttribute',
            name: 'rawCode',
            value: node.value,
          },
        ],
        children: [],
        data: { _customParsed: true },
      };

      // Gantikan node Code pada tree induk dengan MDX JSX Node
      parent.children.splice(index, 1, mdxNode as unknown as Code);
    });
  };
};
```

#### File: `components/AgentToolViewer.tsx`

Komponen presentasional pendamping (kompatibel dengan Docusaurus, Starlight React Island, atau Nextra):

```tsx
import React, { useState } from 'react';

interface PropertyDetail {
  type: string;
  description: string;
  enum?: string[];
}

interface SchemaPayload {
  type: 'object';
  properties: Record<string, PropertyDetail>;
  required: string[];
}

export interface AgentToolViewerProps {
  name: string;
  description: string;
  schemaPayload: string;
  rawCode: string;
}

export const AgentToolViewer: React.FC<AgentToolViewerProps> = ({
  name,
  description,
  schemaPayload,
  rawCode,
}) => {
  const [activeTab, setActiveTab] = useState<'ui' | 'json'>('ui');
  const schema: SchemaPayload = JSON.parse(schemaPayload);

  return (
    <div style={{
      border: '1px solid #30363d',
      borderRadius: '8px',
      margin: '1.5rem 0',
      backgroundColor: '#0d1117',
      overflow: 'hidden',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0.75rem 1rem',
        backgroundColor: '#161b22',
        borderBottom: '1px solid #30363d'
      }}>
        <div>
          <span style={{ 
            fontSize: '0.75rem', 
            textTransform: 'uppercase', 
            fontWeight: 700, 
            color: '#58a6ff', 
            marginRight: '0.5rem' 
          }}>
            AI AGENT TOOL
          </span>
          <code style={{ fontSize: '1rem', fontWeight: 600, color: '#f0f6fc' }}>{name}</code>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('ui')}
            style={{
              padding: '0.25rem 0.5rem',
              fontSize: '0.8rem',
              backgroundColor: activeTab === 'ui' ? '#21262d' : 'transparent',
              color: activeTab === 'ui' ? '#58a6ff' : '#8b949e',
              border: '1px solid #30363d',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Interface
          </button>
          <button
            onClick={() => setActiveTab('json')}
            style={{
              padding: '0.25rem 0.5rem',
              fontSize: '0.8rem',
              backgroundColor: activeTab === 'json' ? '#21262d' : 'transparent',
              color: activeTab === 'json' ? '#58a6ff' : '#8b949e',
              border: '1px solid #30363d',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Raw Schema
          </button>
        </div>
      </div>

      <div style={{ padding: '1rem', color: '#c9d1d9' }}>
        <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', color: '#8b949e' }}>
          {description}
        </p>

        {activeTab === 'ui' ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #21262d', textAlign: 'left', color: '#8b949e' }}>
                <th style={{ padding: '0.5rem' }}>Parameter</th>
                <th style={{ padding: '0.5rem' }}>Type</th>
                <th style={{ padding: '0.5rem' }}>Status</th>
                <th style={{ padding: '0.5rem' }}>Description</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(schema.properties).map(([paramName, details]) => {
                const isRequired = schema.required.includes(paramName);
                return (
                  <tr key={paramName} style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: '#79c0ff' }}>
                      {paramName}
                    </td>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: '#ff7b72' }}>
                      {details.type}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <span style={{
                        padding: '0.1rem 0.4rem',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        backgroundColor: isRequired ? 'rgba(248, 81, 73, 0.15)' : 'rgba(110, 118, 129, 0.2)',
                        color: isRequired ? '#f85149' : '#8b949e'
                      }}>
                        {isRequired ? 'required' : 'optional'}
                      </span>
                    </td>
                    <td style={{ padding: '0.5rem', color: '#c9d1d9' }}>
                      {details.description}
                      {details.enum && (
                        <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: '#8b949e' }}>
                          Allowed: {details.enum.map(e => `'${e}'`).join(', ')}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <pre style={{
            margin: 0,
            padding: '0.75rem',
            backgroundColor: '#161b22',
            borderRadius: '4px',
            fontSize: '0.8rem',
            overflowX: 'auto',
            color: '#79c0ff'
          }}>
            {rawCode}
          </pre>
        )}
      </div>
    </div>
  );
};
```

---

### 7. Edge Cases & Failure Modes

#### 7.1 Hydration Mismatch Akibat State Non-Deterministik
- **Gejala**: Muncul peringatan console browser: `Text content does not match server-rendered HTML`. Tampilan berkedip (*flash*) saat halaman selesai dimuat.
- **Penyebab**: Menampilkan informasi dinamis (misal: "Last generated at: {new Date().toLocaleTimeString()}") langsung dalam komponen React tanpa pembungkus. SSR merender waktu server, sedangkan browser mengeksekusi waktu lokal klien.
- **Solusi**: Isolasi akses API non-deterministik di dalam hook `useEffect` atau gunakan pola *suppressHydrationWarning*:
  ```tsx
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <SkeletonLoader />;
  ```

#### 7.2 MDX v3 Strict Parsing Failure
- **Gejala**: Build CI/CD gagal dengan error `Unexpected character `<` (U+003C) in name, expected valid identifier character`.
- **Penyebab**: Karakter komparasi matematis seperti `x < y` atau generic type parameter TypeScript seperti `Record<string, any>` ditulis langsung di dalam teks paragraf Markdown tanpa di-*escape*.
- **Solusi**: Wajib menggunakan *html-entities* (`&lt;`), membungkus teks dalam inline backtick (`` `Record<string, any>` ``), atau menyuntikkan pre-processor sanitasi di pipeline unified sebelum MDX compiler berjalan.

#### 7.3 Out Of Memory (OOM) pada Skala Dokumen > 5.000 Halaman
- **Gejala**: Proses build Node.js terhenti dengan exit code `137` atau error `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`.
- **Penyebab**: Docusaurus/Webpack menahan seluruh instance module tree dalam memori fisik untuk membangun static routing SPA.
- **Solusi**:
  1. Naikkan resource node memory: `NODE_OPTIONS="--max-old-space-size=8192"`.
  2. Alihkan arsitektur ke **Starlight** yang memanfaatkan Vite chunk streaming dan pemrosesan *per-page isolation*, sehingga penggunaan memori bersifat konstan ($O(1)$) terhadap jumlah halaman.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Docusaurus v3 (Meta) | Starlight (Astro) | Nextra v3/v4 (Vercel) |
| :--- | :--- | :--- | :--- |
| **Model Render Dasar** | React SPA (Single Page App) | Multi-Page App (MPA) + Islands | React Server Components (RSC) |
| **Baseline JavaScript** | Tinggi (~150KB - 300KB runtime) | **Nol (0 KB)** secara default | Minimal (~30KB - 80KB) |
| **Kecepatan Build** | Sedang (Tergantung optimasi Webpack) | **Sangat Cepat** (Ditenagai Vite & Rollup/esbuild) | Cepat (Ditenagai Turbopack / Next.js) |
| **Ekosistem Komponen** | Khusus ekosistem React | Agnostik (React, Vue, Svelte, Solid) | Khusus ekosistem React |
| **I18n / Lokalisasi** | Sangat matang (Git translate + Crowdin) | Sangat baik (Built-in path routing) | Menengah (Mengikuti konfigurasi Next.js) |
| **Ideal Use Case** | Portal korporat besar, integrasi penuh versi dokumen multi-release | Dokumentasi dengan performa kritis, zero-JS content, developer-tool docs | Internal apps yang ingin dokumentasi dan dashboard berada dalam 1 monorepo |

---

### 9. Best Practices & Standard Industri

1. **Docs-as-Code Single Source of Truth**: Definisikan parameter agen AI di file YAML/JSON skema yang sama dengan yang dikonsumsi oleh runtime Python/Go agen. Gunakan build script untuk men-generate file `.mdx` secara otomatis sebelum proses SSG compile.
2. **Linting Semantik dengan Vale & Markdownlint**:
   Integrasikan Vale linter ke CI pipeline untuk memverifikasi struktur gramatikal, konsistensi istilah teknis, dan tone voice enterprise:
   ```yaml
   # .vale.ini
   MinStylesPath = .github/styles
   [*.mdx]
   BasedOnStyles = Google, InternalAgentDocs
   Google.Passive = suggestion
   ```
3. **Type-Checking Kode Blok dengan Twoslash**:
   Gunakan plugin `remark-shiki-twoslash` untuk mengevaluasi kode TypeScript di dalam codeblock dokumentasi saat build time. Jika kode contoh di dokumentasi menggunakan method API yang sudah *deprecated* atau tipe data yang salah, proses build dokumen otomatis gagal (*fail the build*).
4. **LLM Ingestion Endpoint**:
   Sediakan route otomatis `/llms.txt` yang berisi ringkasan arsitektur platform dalam bentuk markdown sederhana dan konsisten, dipisahkan berdasarkan token budget agar mudah dikonsumsi oleh autonomous agent external.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membangun prototipe dokumentasi teknis sistem **"Autonomous Multi-Agent Swarm Registry"** menggunakan **Astro Starlight**. Dokumentasi harus mampu:
1. Memvalidasi dan merender spesifikasi Tool Agen interaktif menggunakan plugin unified kustom.
2. Mengisolasi komponen dynamic monitor hanya di browser (*Islands architecture*).

#### Langkah 1: Inisialisasi Proyek Astro Starlight
Jalankan perintah berikut pada terminal:
```bash
npm create astro@latest agent-docs -- --template starlight --typescript strict --no-install
cd agent-docs
npm install
npm install unist-util-visit zod
```

#### Langkah 2: Daftarkan Plugin AST ke Konfigurasi
Buka file `astro.config.mjs` dan integrasikan plugin remark buatan kita:

```javascript
// astro.config.mjs
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import { remarkAgentSchema } from './src/plugins/remark-agent-schema';

export default defineConfig({
  integrations: [
    starlight({
      title: 'Autonomous Swarm Core Documentation',
      social: {
        github: 'https://github.com/enterprise/swarm-engine',
      },
      sidebar: [
        { label: 'Platform Architecture', slug: 'architecture' },
        { label: 'Agent Tools Registry', slug: 'tools/registry' },
      ],
    }),
    react(),
  ],
  markdown: {
    remarkPlugins: [
      [remarkAgentSchema, { strictValidation: true }]
    ],
  },
});
```

#### Langkah 3: Tulis Dokumen dengan Embedded Agent Definition
Buat file `src/content/docs/tools/registry.mdx`:

````mdx
---
title: Agent Tools Registry
description: Katalog spesifikasi tool yang dapat dieksekusi oleh Orchestrator Agent.
---

import { AgentToolViewer } from '../../../components/AgentToolViewer';

Berikut adalah daftar spesifikasi tool yang aktif pada core swarm v1.2:

```agent-tool
{
  "name": "execute_sql_query",
  "description": "Menjalankan query SQL Read-Only terhadap database analitik vector.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "SQL SELECT statement yang aman dan terisolasi."
      },
      "timeout_ms": {
        "type": "number",
        "description": "Batas waktu eksekusi dalam milidetik."
      },
      "isolation_level": {
        "type": "string",
        "description": "Level isolasi database.",
        "enum": ["READ_COMMITTED", "SERIALIZABLE"]
      }
    },
    "required": ["query"]
  }
}
```

:::note
Jika input SQL mengandung mutation (`DROP`, `DELETE`, `UPDATE`), query engine akan secara otomatis memicu abort controller level 1.
:::
````

#### Langkah 4: Build dan Verifikasi Validasi AST
1. Jalankan proses preview lokal:
   ```bash
   npm run dev
   ```
   Buka browser di `http://localhost:4321/tools/registry/`. Komponen `AgentToolViewer` harus muncul menggantikan raw codeblock, lengkap dengan validasi tabel atribut schema.

2. Uji ketahanan (*Failure Mode Test*):
   Ubah `src/content/docs/tools/registry.mdx` dan buat file JSON di dalam blok `agent-tool` menjadi tidak valid (misal: hapus field mandatory `description`).
   Jalankan:
   ```bash
   npm run build
   ```
   *Expected Result*: Build gagal (*compiler exit code 1*) disertai pesan deskriptif dari plugin Zod:
   `Schema validation failed for agent-tool at line X: description: Required`. Hal ini membuktikan bahwa dokumentasi berstatus *type-safe* dan bebas dari anomali data usang sebelum masuk ke fase deployment.