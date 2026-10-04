# BAB 05: Multimodal Prototyping: Visual-to-Code Workflow
## MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Merancang & Mengimplementasikan Enterprise Visual-to-Code Pipeline**: Membangun orkestrasi otomatis dari artefak visual (Figma nodes, wireframe wire-protocol, visual screenshots) ke *production-grade, typed UI components* (React 19, Next.js App Router, Tailwind CSS, Shadcn/UI).
*   **Menguasai Hybrid Ingestion Architecture**: Menggabungkan kapabilitas Vision-Language Models (VLMs) dengan deterministic Abstract Syntax Tree (AST) parsing dan *Design System Token Engines* guna meminimalkan halusinasi tata letak.
*   **Membangun Closed-Loop Self-Healing Visual Regression Engine**: Mengotomatisasi siklus koreksi kode melalui *headless visual testing* (Playwright + Pixelmatch), kalkulasi *structural visual drift*, dan *iterative prompt patching*.
*   **Menerapkan Production Governance & Zero-Drift Synchronization**: Mengelola konkurensi, context window limits, token optimization, dan isolasi microfrontend pada lingkungan enterprise.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
*   **Lanjutan TypeScript & React Architecture**: State machines, generic type constraints, custom hooks, dan Server/Client Component paradigms (React Server Components).
*   **Visual Engineering Tools**: Pemahaman mendalam tentang Figma REST API (Nodes, Vectors, Computed Styles, Component Sets) dan Design Tokens (W3C Design Token Community Group format).
*   **AST Manipulation**: Pengalaman menggunakan Babel Core (`@babel/parser`, `@babel/traverse`, `@babel/generator`) atau Tree-sitter untuk transformasi kode statis.
*   **VLM Mechanics**: Parameter inferensi multimodal (Temperature, Top_P, Vision Token Patching via ViT, High-Resolution Image Tiling).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi enterprise dari *Visual-to-Code* tidak dapat bergantung semata-mata pada "screenshot-to-prompt" naif. Pendekatan primitif tersebut rentan terhadap *layout hallucination*, ketidakcocokan design tokens, dan hilangnya aksesibilitas (a11y). 

Arsitektur produksi menerapkan pola **Hybrid Neuro-Symbolic Ingestion**:

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE INGESTION LAYER                                      |
+----------------------------------------------------------------------------------------------------+
       |                                                                           |
       v                                                                           v
 [Visual Artifacts]                                                      [Structured Artifacts]
 High-Res Raster (PNG/WebP)                                              Figma Node Graph (JSON)
       |                                                                           |
       v                                                                           v
+------------------------+                                              +------------------------+
| VLM Spatial Reasoning  |                                              | Deterministic Extractor|
| (Claude 3.5 Sonnet /   |                                              | - Bounding Boxes       |
|  Gemini 1.5 Pro)       |                                              | - Exact Typography     |
| Extract:               |                                              | - Hex / Alpha Values   |
| - Layout Intent        |                                              | - Flex / Grid Props    |
| - Dynamic States       |                                              +------------------------+
| - Semantic Roles       |                                                         |
+------------------------+                                                         |
       |                                                                           |
       +------------------------------------+--------------------------------------+
                                            |
                                            v
                         +-------------------------------------+
                         |      Semantic Alignment Layer       |
                         |  (Token Normalizer & Component Map) |
                         +-------------------------------------+
                                            |
                                            v
                         +-------------------------------------+
                         |   AST Synthesis Engine (TypeScript) |
                         |   Generates Clean TSX + Tailwind    |
                         +-------------------------------------+
                                            |
                                            v
                         +-------------------------------------+
                         |      Closed-Loop Verification       |
                         |   Playwright Render + Pixelmatch    |
                         +-------------------------------------+
                                            |
               +----------------------------+----------------------------+
               | If Drift > Threshold                                    | If Drift <= Threshold
               v                                                         v
    [Iterative Fix Loop]                                       [Production Deployment]
```

#### Layer 1: Ingestion & Dual-Path Parsing
1.  **Visual Processing Path (Neural)**: Citra visual diproses via Vision Transformer (ViT) patch slicing. Model multimodal mengevaluasi hierarki visual global, kedalaman kontras (*z-index visual cues*), serta pola komponen mikro yang tersembunyi (misal: *states* hover, disabled, active).
2.  **Structural Processing Path (Symbolic)**: API desain (seperti Figma REST API) mengekstrak *Document Object Model* (DOM) versi desain secara deterministik. Di sini, nilai eksplisit seperti `layoutMode: HORIZONTAL`, `itemSpacing: 16`, `fills: [...]` ditangkap tanpa inferensi probabilistik.

#### Layer 2: Semantic Alignment & Design Token Mapping
Data dari kedua *path* dinormalisasi ke dalam *Intermediate Representation* (IR). Token extractor memeriksa *hardcoded color/spacing* terhadap *Design Tokens Dictionary* resmi organisasi:
$$\text{Color Match} = \min_{t \in \text{Tokens}} \Delta E^*_{00}(\text{ExtractedColor}, \text{TokenColor})$$
Jika ditemukan nilai HEX `#1E40AF` dan sistem memiliki token `colors.brand.primary = #1E40AF`, AST synthesizer dipaksa menginjeksikan token semantic alih-alih hardcoded Tailwind arbitrary values (`bg-[#1e40af]`).

#### Layer 3: Deterministic AST Synthesis
Model tidak menulis string teks mentah yang rentan terhadap syntax error. Sebaliknya, agen menggunakan LLM untuk merekomendasikan struktur hirarkis komponen, yang kemudian divalidasi dan diubah menjadi *Babel Abstract Syntax Tree*. Transformasi ini memastikan:
*   Impor dependensi yang valid.
*   Type safety penuh via TypeScript compiler interface.
*   Penegakan atribut Accessibility (ARIA) wajib.

#### Layer 4: Self-Healing Closed-Loop Verification
Kode yang dihasilkan di-render secara *headless* menggunakan Playwright. Komponen visual hasil render di-screenshot dan dibandingkan langsung dengan desain visual target menggunakan algoritma *Structural Similarity Index Measure* (SSIM) dan *Perceptual Color Difference* (Pixelmatch). Jika ditemukan delta ($\Delta > 0.02$ atau 2%), sistem memicu siklus *iterative auto-remediation* dengan melampirkan diff image mask ke VLM.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Vibe-Coding Naif) | Pendekatan Enterprise Multimodal Pipeline |
| :--- | :--- | :--- |
| **Input Source** | Screenshot resolusi rendah via chat interface | High-res visual crops + JSON Node Graph + Design Token Manifest |
| **Output Type** | Single-file HTML/CSS mentah, arbitrary values | Moduler, Typescript-strict, Shadcn-compliant, decoupled state & logic |
| **Design Consistency**| Menghasilkan visual "mirip" tetapi nilai HEX dan padding melenceng | Strict zero-drift enforcement terhadap core design tokens |
| **Reliability** | Rentan compile-error dan broken layout pada responsive sizes | Terverifikasi via Headless Browser AST validation loop sebelum PR dibuat |
| **Scalability** | Skala throwaway prototype (hanya usable 1-2 kali) | Micro-frontend ready, terintegrasi dengan CI/CD Design Ops |

#### Mengapa Pipeline Ini Mutlak Dibutuhkan?
Dalam siklus rekayasa perangkat lunak enterprise, friksi terbesar berada pada fase *handoff* desain ke frontend engineer. Sekitar 40-60% waktu frontend dihabiskan untuk menerjemahkan tata letak visual Figma ke dalam JSX sembari memastikan konsistensi token. Vibe-coding tanpa arsitektur kontrol yang ketat hanya memindahkan beban kerja: prototipe cepat selesai dalam 5 menit, namun membutuhkan waktu 3 hari untuk membersihkan technical debt, a11y defect, dan standardisasi kode. 

Dengan memadukan VLM dengan validasi AST dan visual regression testing, waktu *handoff-to-production* dapat dipangkas hingga 80% dengan jaminan kualitas enterprise.

---

### 5. How (Workflow Detail)

Alur kerja integrasi *Visual-to-Code Enterprise* beroperasi secara linear dengan feedback loop internal:

```
[Designer Updates Figma]
          │
          ▼
[Webhook: Figma File Changed]
          │
          ▼
[Worker Ingests Nodes & Exports High-Res WebP]
          │
          ▼
[VLM Prompt Assembly: Visual + JSON Subtree + Token Context]
          │
          ▼
[LLM Synthesizes TSX Blueprint]
          │
          ▼
[AST Engine Validates & Injects Design Tokens]
          │
          ▼
[Vite Dev Server (In-Memory) Compiles Component]
          │
          ▼
[Playwright Takes Target Snapshot]
          │
          ├── [Diff > 2%] ──► [Auto-Remediation Loop: Inject Diff Mask to VLM]
          │
          └── [Diff <= 2%] ──► [Create GitHub PR with Storybook Link]
```

#### Langkah-langkah Operasional:
1.  **Event Capture & Asset Extraction**:
    *   Figma webhook mentrigger job worker saat frame diberi tag status `#ready-for-dev`.
    *   Worker mengunduh image vector/raster dan mengekstrak sub-tree JSON node spesifik via Figma REST API (`/v1/files/{file_key}/nodes?ids={node_id}`).
2.  **Context Construction & LLM Orchestration**:
    *   Agen mengumpulkan: (a) Gambar frame, (b) JSON bounding layout (tanpa noise metadata), (c) Daftar design tokens yang tersedia dalam sistem (Tailwind config, CSS variables), (d) Metadata a11y spec.
    *   Prompt dirancang menggunakan model *Chain-of-Thought (CoT)*: Model pertama-tama mendeskripsikan tata letak, lalu mengidentifikasi interaktivitas, dan akhirnya menghasilkan payload AST/kode.
3.  **Local Compilation & Sandboxing**:
    *   Kode yang dihasilkan disimpan ke direktori temporer terisolasi.
    *   Vite/Next.js dev server yang berjalan di background langsung mengompilasi kode tersebut.
    *   Jika compile error terjadi, stack trace ditangkap dan di-feed balik ke model untuk perbaikan sintaks seketika (*zero-human loop*).
4.  **Visual Differential Auditing**:
    *   Playwright mengeksekusi browser headless, memuat instance komponen, dan mengambil tangkapan layar dengan resolusi kanvas yang sama persis dengan Figma node origin.
    *   Engine Pixelmatch membandingkan kedua gambar. Jika *diff pixel count* melampaui batas toleransi (misal 2%), visual diff mask digenerate (area kesalahan ditandai dengan warna merah terang) dan dikirim kembali ke LLM bersama prompt: *"Perbaiki padding dan alignment pada area yang ditandai merah pada mask ini"*.
5.  **Git Ingestion**:
    *   Setelah melewati audit visual dan typecheck (`tsc --noEmit`), Git agent membuat branch baru, menulis storybook stories, unit tests, dan membuka Pull Request.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan Anda merestorasi lukisan klasik menggunakan dua orang spesialis:
1.  **Seniman Multimodal (VLM)**: Memiliki pemahaman holistik tentang estetika, mood, bayangan, dan emosi lukisan, tetapi tangannya terkadang gemetar sehingga proporsi milimeter bisa meleset.
2.  **Juru Ukur Arsitektur (Deterministic AST & Token Engine)**: Menggunakan jangka sorong dan laser digital untuk mengukur koordinat absolut, ketebalan kanvas, dan komposisi pigmen warna yang tepat secara matematis.

Jika hanya mengandalkan Seniman, lukisan tampak indah tetapi tidak presisi. Jika hanya mengandalkan Juru Ukur, struktur presisi tetapi kehilangan esensi seni. **Hybrid Architecture** menggabungkan keduanya: Seniman memandu tata letak dan hierarki, sementara Juru Ukur memastikan setiap garis terkunci tepat pada grid sistem.

#### Diagram Interaksi Komponen AST & Remediasi Loop

```
+-------------------------------------------------------------------------+
|                        ORCHESTRATION PIPELINE                           |
+-------------------------------------------------------------------------+
 FIGMA CANVAS              NODE EXTRACTION                LLM REASONING
+------------+          +-------------------+         +-------------------+
|  [Button]  |          | {                 |         | Inputs:           |
|  "Submit"  | -------> |   type: "FRAME",  | ------> | - Visual PNG      |
|  Bg: Blue  |          |   layout: "AUTO", |         | - Context JSON    |
+------------+          |   fills: [#0066FF]|         | - Token Table     |
                        +-------------------+         +---------+---------+
                                                                |
                                                                v
+-------------------------------------------------------------------------+
|                         SYNTHESIS & COMPLIANCE                          |
+-------------------------------------------------------------------------+
     AST SANITIZER               TOKEN INJECTOR              GENERATED CODE
+---------------------+      +--------------------+      +----------------+
| Parsed via Babel    |      | Token Mapping:     |      | export const   |
| Disallow arbitrary  | ---> | #0066FF            | ---> | PrimaryButton =|
| styles (bg-[...])   |      |   => 'bg-primary'  |      | () => (...)    |
+---------------------+      +--------------------+      +--------+-------+
                                                                  |
                                                                  v
+-------------------------------------------------------------------------+
|                      CLOSED-LOOP VISUAL HEALING                         |
+-------------------------------------------------------------------------+
  RENDER IN PLAYWRIGHT          PIXEL COMPARISON               FEEDBACK
+---------------------+      +--------------------+      +----------------+
| Headless Browser    |      | Raw vs Generated   | FAIL | Send Visual    |
| Port: 3000          | ---> | Diff: 4.8%         | ---> | Diff Mask to   |
| Resolution: 1:1     |      | Threshold: 2.0%    |      | LLM for Repass |
+---------------------+      +---------+----------+      +----------------+
                                       | PASS
                                       v
                             +--------------------+
                             | Git PR & Deployment|
                             +--------------------+
```

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

#### A. Simple Example: Node to Strict Tailwind AST Transformer
Berikut adalah implementasi minimalis Node.js/TypeScript untuk mentransformasikan raw visual layout JSON menjadi Tailwind class yang valid tanpa halusinasi warna.

```typescript
// scripts/simple-transformer.ts
import { z } from 'zod';

// Skema untuk input layout node
const LayoutNodeSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.enum(['FRAME', 'TEXT', 'RECTANGLE']),
  layoutMode: z.enum(['NONE', 'HORIZONTAL', 'VERTICAL']).default('NONE'),
  paddingLeft: z.number().default(0),
  paddingTop: z.number().default(0),
  backgroundColor: z.string().regex(/^#([A-Fa-f0-9]{6})$/),
  children: z.array(z.lazy(() => LayoutNodeSchema)).optional(),
});

type LayoutNode = z.infer<typeof LayoutNodeSchema>;

// Token mapping enterprise yang diizinkan (Strict Token Dictionary)
const COLOR_TOKEN_MAP: Record<string, string> = {
  '#FFFFFF': 'bg-white',
  '#0F172A': 'bg-slate-900',
  '#2563EB': 'bg-blue-600',
  '#DC2626': 'bg-red-600',
};

export function compileNodeToTailwind(node: LayoutNode): string {
  const classes: string[] = [];

  // 1. Flex Layout Mapping
  if (node.layoutMode === 'HORIZONTAL') {
    classes.push('flex flex-row');
  } else if (node.layoutMode === 'VERTICAL') {
    classes.push('flex flex-col');
  }

  // 2. Padding Normalization (Scale base-4)
  if (node.paddingLeft > 0) {
    const pVal = Math.round(node.paddingLeft / 4);
    classes.push(`pl-${pVal}`);
  }
  if (node.paddingTop > 0) {
    const pVal = Math.round(node.paddingTop / 4);
    classes.push(`pt-${pVal}`);
  }

  // 3. Deterministic Color Token Ingestion
  const tokenClass = COLOR_TOKEN_MAP[node.backgroundColor.toUpperCase()];
  if (!tokenClass) {
    throw new Error(`VIOLATION: Color ${node.backgroundColor} is not an authorized design token.`);
  }
  classes.push(tokenClass);

  return classes.join(' ');
}

// Uji Coba Sederhana
const sampleNode: LayoutNode = {
  id: 'node_1',
  name: 'Container',
  type: 'FRAME',
  layoutMode: 'HORIZONTAL',
  paddingLeft: 16,
  paddingTop: 8,
  backgroundColor: '#2563EB',
};

console.log('Compiled Tailwind Classes:', compileNodeToTailwind(sampleNode));
// Output: "flex flex-row pl-4 pt-2 bg-blue-600"
```

#### B. Practical Enterprise Example: Self-Healing Pipeline Orchestrator
Contoh produksi berikut menunjukkan bagaimana VLM pipeline berintegrasi dengan Playwright dan Pixelmatch untuk mendeteksi deviasi visual secara real-time dan memicu loop perbaikan.

```typescript
// pipeline/visual-healer.ts
import { chromium, Page } from 'playwright';
import PNG from 'pngjs';
import pixelmatch from 'pixelmatch';
import * as fs from 'fs';
import * as path from 'path';

interface HealingResult {
  success: boolean;
  mismatchPercentage: number;
  diffImagePath?: string;
  sourceCode: string;
}

export class VisualHealingEngine {
  private threshold: number;
  private maxRetries: number;

  constructor(thresholdPercent: number = 2.0, maxRetries: number = 3) {
    this.threshold = thresholdPercent;
    this.maxRetries = maxRetries;
  }

  /**
   * Closed-loop runner yang memvalidasi komponen web terhadap baseline visual target
   */
  public async executeHealingLoop(
    componentUrl: string,
    targetImagePath: string,
    currentCode: string,
    codePatcherCallback: (code: string, diffImageBase64: string) => Promise<string>
  ): Promise<HealingResult> {
    const browser = await chromium.launch({ headless: true });
    let code = currentCode;

    try {
      const page = await browser.newPage();
      await page.setViewportSize({ width: 1200, height: 800 });

      for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
        console.log(`[Validation] Running verification attempt ${attempt}/${this.maxRetries}...`);
        
        await page.goto(componentUrl, { waitUntil: 'networkidle' });
        const renderedBuffer = await page.screenshot({ fullPage: false });

        const { mismatchPercentage, diffBuffer } = this.calculateDiff(
          targetImagePath,
          renderedBuffer
        );

        console.log(`[Audit] Current visual mismatch: ${mismatchPercentage.toFixed(2)}%`);

        if (mismatchPercentage <= this.threshold) {
          return { success: true, mismatchPercentage, sourceCode: code };
        }

        if (attempt === this.maxRetries) {
          const finalDiffPath = path.resolve(`./artifacts/failed-diff-${Date.now()}.png`);
          fs.writeFileSync(finalDiffPath, diffBuffer);
          return {
            success: false,
            mismatchPercentage,
            diffImagePath: finalDiffPath,
            sourceCode: code,
          };
        }

        // Generate base64 diff mask untuk dikirim kembali ke VLM
        const base64Diff = diffBuffer.toString('base64');
        console.warn(`[Self-Healing] Triggering LLM auto-remediation with visual diff mask...`);
        code = await codePatcherCallback(code, base64Diff);

        // Simulasi penulisan file komponen lokal agar live reload terpicu
        fs.writeFileSync(path.resolve('./src/components/DynamicComponent.tsx'), code, 'utf-8');
        await page.waitForTimeout(1000); // Buffer untuk HMR compilation
      }

      return { success: false, mismatchPercentage: 100, sourceCode: code };
    } finally {
      await browser.close();
    }
  }

  private calculateDiff(
    baselinePath: string,
    renderedBuffer: Buffer
  ): { mismatchPercentage: number; diffBuffer: Buffer } {
    const imgBaseline = PNG.PNG.sync.read(fs.readFileSync(baselinePath));
    const imgRendered = PNG.PNG.sync.read(renderedBuffer);

    const { width, height } = imgBaseline;
    const diff = new PNG.PNG({ width, height });

    const totalPixels = width * height;
    const mismatchedPixels = pixelmatch(
      imgBaseline.data,
      imgRendered.data,
      diff.data,
      width,
      height,
      { threshold: 0.1, includeAA: false }
    );

    const mismatchPercentage = (mismatchedPixels / totalPixels) * 100;
    const diffBuffer = PNG.PNG.sync.write(diff);

    return { mismatchPercentage, diffBuffer };
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Global Financial Platform: Automated Design-to-Design System Pipeline
*   **Konteks**: Lembaga perbankan multinasional memiliki lebih dari 300 UI/UX designer di Figma dan 450 frontend engineer yang mengelola 12 core banking apps.
*   **Problem Statement**:
    *   Setiap rilis fitur baru mengalami *UI Drift* sebesar 22% dari spesifikasi design token.
    *   Waktu siklus *ticket ready-for-dev* hingga *QA approved UI* mencapai rata-rata 14 hari kerja per modul.
    *   Pengembang sering melakukan *copy-paste* Tailwind arbitrary classes (`w-[317px]`, `text-[#1b2234]`) yang melanggar standar WCAG 2.1 AA.
*   **Arsitektur Solusi**:
    1.  Membangun service middleware berbasis Node.js yang mendengarkan event webhook Figma.
    2.  Menggunakan **Claude 3.5 Sonnet** yang disuplai dengan sistem skema AST custom, definisi token Tailwind internal, dan referensi komponen internal dari Storybook JSON Docs.
    3.  Mengimplementasikan **Deterministic Sanitizer Engine**:
        ```typescript
        // Rule: Hapus semua inline arbitrary Tailwind & fallback ke class terdekat
        if (cls.includes('[')) {
          return sanitizeArbitraryToDesignSystemToken(cls);
        }
        ```
    4.  Visual Regression Pipeline berjalan otomatis di GitHub Actions runner menggunakan Playwright.
*   **Hasil Metrik**:
    *   **Kecepatan Pengiriman**: Waktu delivery frontend berkurang dari 14 hari menjadi 2.5 hari.
    *   **Konsistensi Token**: Nol pelanggaran arbitrary CSS (`0% custom hex in PRs`).
    *   **Visual Regression Pass Rate**: 98.4% lolos pada iterasi pertama, 1.6% sisanya diselesaikan otomatis oleh visual self-healing loop.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

Dalam merancang pipeline multimodal visual-to-code enterprise, trade-offs berikut harus dipertimbangkan secara matang:

| Sektor | Pendekatan Direct VLM Ingestion | Pendekatan Hybrid Ingestion (VLM + AST) | Implikasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Latency** | Cepat (1 kali API Call, ~5-15 detik) | Lambat (20 - 90 detik karena looping browser & AST check) | Pipeline hybrid tidak cocok untuk *live interactive editor*, namun sangat ideal untuk *Asynchronous CI/CD Pipelines*. |
| **Token Cost** | Rendah (~$0.02 per view) | Moderat - Tinggi ($0.10 - $0.45 per view jika memicu self-healing loop) | Memerlukan caching layer untuk image patch & hash node token Figma agar tidak memanggil model secara berulang. |
| **Precision** | Rendah (60-75% visual match). Sering terjadi *misalignment* padding/margin 2-8px. | Sangat Tinggi (>98% match). Nilai absolut disubstitusi oleh representasi bounding box asli. | Mencegah bug regressions di production dan memangkas waktu code review teknis. |
| **Compute Overhead** | Minimal (Stateless REST call) | Tinggi (Memerlukan runner Docker berkapasitas browser headless & compilation memory) | Membutuhkan worker queue (BullMQ/Redis) terisolasi agar render Playwright tidak membebani core server. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Mengirimkan Full Figma JSON Tree ke Context Window LLM
*   *Penyebab*: Ukuran payload node Figma untuk satu screen kompleks bisa mencapai 15MB JSON, memicu token context exhaust dan latensi masif.
*   *Solusi*: Buat Tree Pruner yang membuang properti internal yang tidak relevan (seperti `guid`, `version`, `author`, `transitionNodeID`) dan hanya menyisakan parameter geometri serta gaya (`layoutMode`, `fills`, `strokes`, `padding`, `itemSpacing`).

#### Kesalahan 2: Hallucinated Imports pada Shadcn/Tailwind
*   *Penyebab*: Model mengimpor komponen yang tidak ada di direktori lokal (misal: `@/components/ui/super-date-picker`).
*   *Solusi*: Sediakan *Component Registry Manifest* pada system prompt yang membatasi impor hanya pada daftar file yang diekspor oleh repository:
    ```typescript
    const ALLOWED_COMPONENTS = ['Button', 'Card', 'Dialog', 'Input', 'Select'];
    // Validasi via Babel AST Visitor: Throw error jika import specifier tidak terdaftar
    ```

#### Kesalahan 3: Browser Rendering Font-Mismatch pada Visual Diff
*   *Penyebab*: Playwright di environment container Linux (CI) me-render teks menggunakan fallback fonts (seperti DejaVu Sans alih-alih Inter), menghasilkan false positive diff 40%.
*   *Solusi*: Pasang font biner yang sama persis di Docker runner image:
    ```dockerfile
    COPY fonts/Inter-*.ttf /usr/share/fonts/truetype/
    RUN fc-cache -f -v
    ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengintegrasikan automated visual workflow ke repository production:

- [ ] **Type Safety Enforcement**: Semua output komponen UI harus di-*typecheck* via `tsc --noEmit` tanpa flag `any`.
- [ ] **Accessibility Primitives**: Pastikan elemen interaktif non-semantik (seperti icon button) secara otomatis menginjeksi `aria-label`, `role`, dan focus states (`focus-visible:ring-2`).
- [ ] **Token Whitelist Only**: Tidak ada arbitrary style syntax (misal `w-[32.5px]`). Semua dimensi harus dinormalisasi ke *design token base spacing*.
- [ ] **Deterministic Image Crop**: Potong gambar aset ke rasio aspek WebP 1x/2x/3x otomatis dan simpan ke CDN sebelum sintaks kode dibuat.
- [ ] **Visual Diff Threshold Cap**: Tetapkan batasan ketat threshold regression test pada max `2.0%` (pixel difference) pada mode headless chromium.
- [ ] **Security Sandbox Execution**: Eksekusi runtime komponen yang dihasilkan AI pada lingkungan terisolasi (Node sandbox / Docker scratch) untuk memitigasi eksekusi kode berbahaya (*Prompt Injection / SSRF*).
- [ ] **Context Window Pruning**: Maksimal payload JSON untuk representasi layout dibatasi $< 30.000$ tokens per komponen atomik.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini pada sub-direktori: `hands-on/m02/`

#### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── schema/
│   └── visual-node.ts
├── compiler/
│   └── ast-generator.ts
└── index.ts
```

#### Langkah 1: Inisialisasi Environment
Buat file `hands-on/m02/package.json`:
```json
{
  "name": "m02-visual-to-code-pipeline",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "start": "ts-node index.ts"
  },
  "dependencies": {
    "@babel/generator": "^7.24.0",
    "@babel/parser": "^7.24.0",
    "@babel/traverse": "^7.24.0",
    "@babel/types": "^7.24.0",
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "@types/babel__generator": "^7.6.8",
    "@types/babel__traverse": "^7.20.5",
    "@types/node": "^20.11.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

#### Langkah 2: Definisikan Kontrak Data Skema Layout
Buat file `hands-on/m02/schema/visual-node.ts`:
```typescript
import { z } from 'zod';

export const VisualPropertySchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.enum(['button', 'container', 'text', 'card']),
  text: z.string().optional(),
  styles: z.object({
    padding: z.number().default(0),
    gap: z.number().default(0),
    isFlexRow: z.boolean().default(false),
    backgroundColor: z.string(),
    textColor: z.string().optional(),
    rounded: z.boolean().default(false),
  }),
});

export type VisualProperty = z.infer<typeof VisualPropertySchema>;
```

#### Langkah 3: Implementasi AST Synthesizer Engine
Buat file `hands-on/m02/compiler/ast-generator.ts`:
```typescript
import * as t from '@babel/types';
import generate from '@babel/generator';
import { VisualProperty } from '../schema/visual-node';

export class ASTComponentSynthesizer {
  public static createJSXComponent(componentName: string, spec: VisualProperty): string {
    // 1. Resolve Tailwind Classes deterministically
    const classNames: string[] = [];
    if (spec.styles.isFlexRow) classNames.push('flex flex-row');
    if (spec.styles.padding) classNames.push(`p-${Math.round(spec.styles.padding / 4)}`);
    if (spec.styles.gap) classNames.push(`gap-${Math.round(spec.styles.gap / 4)}`);
    if (spec.styles.backgroundColor) classNames.push(spec.styles.backgroundColor);
    if (spec.styles.textColor) classNames.push(spec.styles.textColor);
    if (spec.styles.rounded) classNames.push('rounded-lg');

    const classNameAttr = t.jsxAttribute(
      t.jsxIdentifier('className'),
      t.stringLiteral(classNames.join(' '))
    );

    // 2. Resolve HTML Tag based on Semantic Role
    const tagName = spec.role === 'button' ? 'button' : 'div';
    
    // 3. Assemble Children Elements
    const childrenElements: t.JSXText[] = [];
    if (spec.text) {
      childrenElements.push(t.jsxText(spec.text));
    }

    // 4. Construct JSX Element AST Node
    const jsxOpening = t.jsxOpeningElement(t.jsxIdentifier(tagName), [classNameAttr], false);
    const jsxClosing = t.jsxClosingElement(t.jsxIdentifier(tagName));
    const jsxElement = t.jsxElement(jsxOpening, jsxClosing, childrenElements, false);

    // 5. Build Functional Component Declaration: export const ComponentName = () => ( ... );
    const componentDeclaration = t.exportNamedDeclaration(
      t.variableDeclaration('const', [
        t.variableDeclarator(
          t.jsxIdentifier(componentName),
          t.arrowFunctionExpression([], jsxElement)
        ),
      ])
    );

    const astProgram = t.program([componentDeclaration]);
    const output = generate(astProgram, { retainLines: false, compact: false });

    return output.code;
  }
}
```

#### Langkah 4: Pipeline Execution Runner
Buat file `hands-on/m02/index.ts`:
```typescript
import { VisualPropertySchema } from './schema/visual-node';
import { ASTComponentSynthesizer } from './compiler/ast-generator';

function runPipeline() {
  console.log('[Pipeline] Ingesting multimodal-inferred layout payload...');
  
  const rawInferredPayload = {
    id: 'btn-action-primary',
    name: 'ActionButton',
    role: 'button',
    text: 'Confirm Transfer',
    styles: {
      padding: 16,
      gap: 8,
      isFlexRow: true,
      backgroundColor: 'bg-emerald-600',
      textColor: 'text-white',
      rounded: true,
    },
  };

  // Validasi input runtime
  const validatedSpec = VisualPropertySchema.parse(rawInferredPayload);
  console.log('[Pipeline] Spec validation: SUCCESS');

  // Sintesis AST
  console.log('[Pipeline] Compiling to React TSX Component via Babel AST...');
  const compiledCode = ASTComponentSynthesizer.createJSXComponent(
    validatedSpec.name,
    validatedSpec
  );

  console.log('\n--- COMPILED PRODUCTION TSX OUTPUT ---');
  console.log(compiledCode);
  console.log('--------------------------------------\n');
}

runPipeline();
```

---

### 13. Exercises

#### Level: Easy
*   **Tugas**: Modifikasi `ASTComponentSynthesizer` pada file praktikum agar menangani properti `role: 'card'`. Tambahkan border bawaan (`border border-slate-200`) dan drop shadow (`shadow-sm`) jika role tersebut digunakan.
*   **Target File**: `hands-on/m02/compiler/ast-generator.ts`

#### Level: Medium
*   **Tugas**: Implementasikan recursive AST compilation. Buat fungsi compiler mampu menerima payload node yang memiliki properti `children: VisualProperty[]` dan menyusunnya menjadi nested JSX layout yang valid secara hierarkis.
*   **Validasi**: Buat Card komponen yang memiliki anak berupa 1 Text heading dan 1 Button.

#### Level: Hard
*   **Tugas**: Bangun plugin validasi berbasis Babel Visitor yang melakukan audit keamanan: Tolak (throw compile error) jika ditemukan atribut dangerouslySetInnerHTML atau teks anak mengandung sintaks ekspresi script (`javascript:`, `<script>`).
*   **Constraint**: Gunakan `@babel/traverse` API untuk menginspeksi AST sebelum dicetak oleh Babel Generator.

---

### 14. Challenges

#### Skenario Kasus Kompleks: Multi-Theme Figma Dynamic AST Reconciliation
Sebuah platform SaaS enterprise memiliki sistem Multi-Tenant di mana 1 Frame Figma yang sama dapat di-render ke dalam 3 tema berbeda (Default Light, Dark Mode, High Contrast). 

*   **Spesifikasi Tantangan**:
    1.  Rancang arsitektur pipeline yang menerima input 3 citra rendering visual (Light, Dark, High Contrast) dari Frame yang identik beserta metadata CSS Custom Properties Dictionary organisasi.
    2.  Model VLM tidak boleh menghasilkan 3 file komponen yang berbeda. Model harus menghasilkan **SATU** file React Server Component yang memanfaatkan CSS Variable-driven Tailwind class (contoh: `bg-[var(--surface-primary)]` yang dialiaskan ke token semantic).
    3.  Implementasikan automated drift checker yang memverifikasi kecocokan kontras WCAG AAA (rasio kontras 7:1) untuk state *High Contrast* secara terprogram menggunakan formula luminansi standar.
*   **Kriteria Keberhasilan**:
    *   Satu file kode TSX valid.
    *   Zero hardcoded Tailwind color class.
    *   Kompilasi lolos verifikasi Playwright untuk ketiga tema tanpa visual drift $> 1.5\%$.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa risiko utama dari pendekatan "screenshot-to-code" naif tanpa menggunakan Design Token Dictionary?
   * A. Waktu kompilasi Vite menjadi lambat.
   * B. Penggunaan Tailwind arbitrary classes (`bg-[#hex]`) yang memecah konsistensi design system.
   * C. Browser tidak dapat mengeksekusi tag JSX.
   * D. API rate limit pada Git provider cepat habis.

2. Mengapa output model multimodal sebaiknya dialirkan melalui engine AST (Abstract Syntax Tree)?
   * A. Agar CSS dapat dikonversi menjadi gambar.
   * B. Untuk memastikan type safety, validitas sintaksis, dan semantic structure sebelum eksekusi.
   * C. Karena VLM tidak bisa menghasilkan teks string secara langsung.
   * D. Untuk memperkecil ukuran bundle React runtime secara runtime.

3. Komponen utama apa yang digunakan untuk mengukur deviasi visual antara target visual asli dan hasil render kode web?
   * A. Webpack bundler.
   * B. Headless browser (Playwright) + Pixel-difference algorithm (Pixelmatch).
   * C. Redux state manager.
   * D. Node.js cluster module.

4. Algoritma apa yang direkomendasikan untuk mencocokkan nilai warna hex yang diekstrak dengan token warna yang tersedia dalam design system?
   * A. Levenshtein Distance.
   * B. CIEDE2000 ($\Delta E^*_{00}$) Color Difference.
   * C. Binary Search Tree.
   * D. SHA-256 Hashing.

5. Dalam workflow multimodal enterprise, apa peran dari "Tree Pruning" pada Figma JSON payload?
   * A. Mengurangi konsumsi token pada context window LLM dengan membuang metadata non-layout.
   * B. Menghapus layer desain yang tidak disukai developer.
   * C. Mengubah warna layer secara acak.
   * D. Mengompresi file SVG menjadi PNG.

#### Bagian 2: Intermediate (Analisis Singkat)
1. Jelaskan bagaimana *Visual Diff Mask* dapat mempercepat konvergensi self-healing code pada VLM dibandingkan hanya mengirimkan error log teks!
2. Mengapa penggunaan Server Components (RSC) lebih disukai daripada Client Components saat mendesain layout hasil visual-to-code synthesis?
3. Sebutkan kelemahan utama dari pemanfaatan threshold per-pixel (Pixelmatch) pada dynamic-content web components (misal tabel dengan data acak)!
4. Bagaimana cara menangani variasi *responsive layout* (Mobile, Tablet, Desktop) saat mengekstrak satu desain Figma frame?
5. Mengapa Babel/Tree-sitter validation layer wajib bertindak sebagai *gatekeeper* sebelum kode masuk ke Git automated staging?

#### Bagian 3: Skenario Kasus Produksi
1. **Skenario A**: Pipeline Anda mengalami loop auto-remediation terus menerus (mencapai max retries) pada komponen typography tertentu karena Playwright mendeteksi visual drift sebesar 5.2%. Padahal, secara visual manusia teks tersebut tampak identik. Apa akar masalah teknisnya dan bagaimana solusinya?
2. **Skenario B**: Tim sekuritas perusahaan menemukan kerentanan di mana seorang desainer memasukkan payload string pada nama layer Figma yang mengecoh LLM untuk menginjeksi script external (`<script src="malicious.io">`) ke dalam file JSX yang diekspor. Arsitektur kontrol apa yang harus dipasang untuk memitigasi serangan ini secara deterministik?
3. **Skenario C**: Pada skala 1000 pembaruan frame per hari, biaya API inference LLM multimodal Anda membengkak hingga $12,000/bulan. Bagaimana Anda merancang arsitektur caching dan differential triggering untuk memangkas biaya operasional ini minimal 70%?

---

### 16. Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **B** — Pendekatan naif menghasilkan nilai *arbitrary* yang merusak sistem standarisasi warna, ukuran, dan tema enterprise.
2. **B** — AST memastikan kode bukan sekadar string acak, tetapi pohon sintaksis terstruktur yang valid secara gramatikal dan bebas cacat sintaksis.
3. **B** — Headless browser merender halaman secara nyata, lalu engine perbandingan piksel mendeteksi deviasi visual secara spasial.
4. **B** — CIEDE2000 adalah formula standar industri untuk mengukur disparitas perseptual warna manusia pada ruang warna LAB.
5. **A** — Raw JSON Figma mengandung ribuan metadata internal aplikasi yang tidak relevan untuk pembuatan kode CSS/JSX, sehingga harus dipangkas guna efisiensi token.

#### Bagian 2: Intermediate
1. *Visual Diff Mask* memberikan koordinat spasial visual secara presisi kepada VLM (area kesalahan ditandai dengan warna kontras), memungkinkan model mengoreksi spesifik properti CSS (misal `padding-top` atau `gap`) tanpa merusak bagian layout yang sudah presisi.
2. RSC mereduksi pengiriman bundle JavaScript ke browser client, meningkatkan Web Vitals (FCP & LCP), dan memisahkan static UI rendering dari stateful logic components.
3. Konten dinamis menghasilkan data yang bervariasi pada tiap render, sehingga perbandingan per-piksel akan selalu menandai area tersebut sebagai *mismatch* meskipun strukturnya benar. Solusinya adalah melakukan *mocking* statis data atau melakukan masking pada dynamic zones.
4. Pipeline harus mengekstrak constraints atau breakpoint frames dari Figma secara modular, lalu menyusun responsive utility classes Tailwind (`sm:`, `md:`, `lg:`) ke dalam satu AST node tunggal.
5. Menghindari polusi git history dengan broken commits, syntax errors, atau insecure dynamic execution yang dapat mematahkan build pipeline staging utama.

#### Bagian 3: Skenario Kasus Produksi
1. **Akar Masalah**: Font rendering mismatch antara host Figma (misal macOS antialiasing) dan headless browser Linux di container (FreeType subpixel rendering / missing webfont). **Solusi**: Pastikan container Playwright menginstal binary font yang identik, matikan subpixel antialiasing via CSS (`-webkit-font-smoothing: antialiased`), dan gunakan parameter `threshold: 0.2` pada Pixelmatch untuk mengabaikan deviasi micro-aliasing.
2. **Solusi**: Terapkan AST Sanitizer Barrier menggunakan Babel. Tolak seluruh string literal yang memuat elemen HTML mentah di luar spec design system. Larang evaluasi string bebas ke dalam JSX, enforce escape sequence, dan lakukan sanitasi skema input menggunakan Zod regex validation sebelum payload diserahkan ke AST Generator.
3. **Solusi**: Implementasikan **Structural Layout Hashing**:
   *   Buat hash deterministik (misal SHA-256) dari kombinasi properti struktural Figma node (posisi, ukuran, warna, token).
   *   Jika hash tidak berubah dari versi sebelumnya, lewati tahapan inferensi LLM dan gunakan AST yang sudah tersimpan di cache.
   *   Terapkan *Visual Slicing*: Hanya kirim frame parsial yang mengalami perubahan ke VLM, bukan seluruh kanvas halaman aplikasi.

---

### 17. Summary
Modul ini menggarisbawahi transformasi dari paradigma *vibe-coding* primitif menuju **Enterprise-Grade Multimodal Visual-to-Code Engineering**. Kunci keberhasilan implementasi produksi bukan terletak pada seberapa besar model VLM yang digunakan, melainkan pada **orkestrasi sistem kontrol di sekitarnya**: integrasi *Figma DOM parsing*, normalisasi *Design Tokens*, sanitasi kode berbasis *Abstract Syntax Tree (AST)*, serta pengujian ketat menggunakan *Playwright Closed-Loop Visual Healing*. Melalui arsitektur ini, kecepatan iterasi prototipe dapat dipercepat secara radikal tanpa mengorbankan type safety, performa, maupun konsistensi design system korporat.