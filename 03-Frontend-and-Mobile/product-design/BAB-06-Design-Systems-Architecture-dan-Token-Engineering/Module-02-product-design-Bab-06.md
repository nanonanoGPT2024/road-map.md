# BAB 06: Design Systems Architecture dan Token Engineering
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan merancang** arsitektur token bertingkat (*Tiered Token Architecture*: Global $\rightarrow$ Semantic $\rightarrow$ Component-Scoped) berbasis spesifikasi resmi *Design Tokens Community Group* (DTCG).
- **Mengimplementasikan** *token processing pipeline* mandiri menggunakan Style Dictionary v4 dan TypeScript yang mengompilasi representasi data abstrak (AST/JSON) menjadi artefak produksi multi-platform (CSS Variables, TypeScript Types, Tailwind Config, iOS Swift Structs, Android Compose Theme).
- **Mendeteksi dan menyelesaikan** dependensi siklik (*circular dependencies*) dan anomali resolusi referensi token menggunakan algoritma *Directed Acyclic Graph* (DAG) dan *Topological Sorting*.
- **Membangun** pipeline integrasi berkelanjutan (*CI/CD Token Pipeline*) terotomasi yang menghubungkan *design tool source-of-truth* (Figma Tokens API / Tokens Studio) ke downstream repositori kode melalui semantic versioning dan AST codemod migrations.
- **Mengoptimalkan** performa runtime distribusi tema pada aplikasi skala enterprise, memitigasi *Flash of Unstyled Content* (FOUC), *style re-computation*, dan memori overhead pada arsitektur *micro-frontend*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Arsitektur CSS Modern**: CSS Custom Properties (`var(--...)`), CSS Cascade Layers (`@layer`), CSS Module, dan mekanisme layout engine rendering browser.
- **TypeScript Tingkat Lanjut**: Generic types, template literal types, conditional types, dan manipulasi abstract syntax tree (AST).
- **Graf & Struktur Data Dasar**: Struktur Directed Acyclic Graph (DAG), rekursi, topological sorting (Kahn's Algorithm).
- **Sistem Build & Package Management**: Node.js ecosystem, ESM/CJS dual-packaging, NPM Workspaces/Turborepo, CI/CD pipelines (GitHub Actions).

---

### 3. Concept & Internal Architecture

#### 3.1 Taksonomi Token Multi-Tier (DTCG Standard)
Arsitektur token enterprise modern tidak memetakan nilai heksadesimal warna secara langsung ke komponen. Sebaliknya, sistem menggunakan pemisahan tanggung jawab (*separation of concerns*) melalui tiga atau empat layer abstraksi:

```
[ Tier 1: Global / Primitives ]
       │  (e.g., color.blue.500: #0070F3)
       ▼
[ Tier 2: Semantic / System ]
       │  (e.g., color.surface.action.primary: {color.blue.500})
       ▼
[ Tier 3: Component-Scoped ]
       │  (e.g., button.primary.background.default: {color.surface.action.primary})
       ▼
[ Tier 4: Contextual / State Overrides ]
          (e.g., button.primary.background.hover: {color.blue.600})
```

1. **Global Tokens (Primitives)**: Mewakili spektrum mentah brand. Tidak membawa makna semantik konteks antarmuka. Bersifat statis lintas tema (contoh: `blue.500: #1d72fe`, `spacing.4: 16px`).
2. **Semantic Tokens (System/Alias)**: Memberikan arti peran fungsional pada primitive token. Di sinilah konteks tema (*Light*, *Dark*, *High Contrast*, *Brand A*, *Brand B*) disuntikkan (contoh: `color.bg.canvas: {color.neutral.50}`, `color.text.interactive: {color.blue.500}`).
3. **Component Tokens**: Menerapkan batas semantik secara eksklusif ke dalam kontrak isolasi sebuah komponen. Mengisolasi komponen dari perubahan global tanpa memecah konsistensi (contoh: `btn.primary.bg: {color.bg.canvas.action}`).

#### 3.2 Token Compilation Engine & DAG Resolution
Compiler token (seperti Style Dictionary) beroperasi mirip dengan compiler bahasa pemrograman standar:
1. **Source Discovery**: Membaca file token berbasis DTCG (JSON/JSON5).
2. **Parsing & AST Construction**: Mengurai setiap node token (`$value`, `$type`, `$description`, `$extensions`).
3. **Reference Resolution via DAG**: Jika token bernilai `{color.brand.primary}`, compiler harus mengarahkan referensi ini ke node target. Resolver membangun graf dependensi berarah (Directed Graph).
4. **Validation & Cycle Checking**: Node token divalidasi dari referensi berputar ($A \rightarrow B \rightarrow C \rightarrow A$). Jika ditemukan siklus, compiler melempar exception fatal sebelum memasuki tahap emisi.
5. **Transformation**: Pipeline transformasi data (misal: mengubah unit `px` ke `rem`, resolusi HSL ke Hex, penamaan case format: `kebab-case`, `camelCase`, `PascalCase`).
6. **Formatting / Code Emission**: Merender artefak akhir melalui template engine ke target output (CSS, SCSS, TS, JSON, Swift, Kotlin XML).

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Naif (Hardcoded Variables) | Headless Token Architecture (Multi-Brand / Multi-Platform) |
| :--- | :--- | :--- |
| **Sumber Kebenaran (*Single Source of Truth*)** | Terduplikasi di Figma, CSS repo web, resource file Android, dan Asset iOS. Sinkronisasi manual via spreadsheet/chat. | Repositori Token terpusat atau Figma Studio Tokens yang mengekspor DTCG spec via Git Webhooks. |
| **Dukungan Multi-Brand** | Duplikasi stylesheet atau CSS preprocessor override yang rapuh (`brand-a.css`, `brand-b.css`). | Dynamic alias injection; primitif tetap stabil, layer semantik memetakan ulang token target saat waktu kompilasi/runtime. |
| **Type Safety** | Nihil; string typos pada CSS variables baru terdeteksi saat runtime di browser. | Full TypeScript validation dengan strictly-typed token paths (`ButtonColorVariants = "action.primary" \| "action.danger"`). |
| **Pembaruan Desain** | Waktu rilis memakan waktu mingguan; risiko regresi tinggi pada platform native mobile. | Pembaruan deterministik melalui pipeline CI/CD otomatis, compile target lintas platform dalam hitungan detik. |

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup token industri enterprise dirancang melalui pipeline berikut:

```
[Design Tool: Figma + Tokens Studio]
                │
                │ 1. Git Push / Webhook Event
                ▼
[Token Source Repository (JSON DTCG Format)]
                │
                │ 2. CI Trigger: Validate Lint & DAG Cyclic Check
                ▼
[Compiler Engine: Style Dictionary 4.x + Custom AST Transpilers]
                │
   ┌────────────┼─────────────┬─────────────┐
   │            │             │             │
   ▼            ▼             ▼             ▼
[Web: CSS]  [Web: TS/ESM]  [iOS: Swift]  [Android: Compose]
(:root vars) (Theme Types)  (Codable/Ext) (Material ColorScheme)
   │            │             │             │
   └────────────┴──────┬──────┴─────────────┘
                       │
                       │ 3. Automated Release (Changesets / Semantic Release)
                       ▼
    [Distribution: NPM Registry + Swift PM + Maven Local]
```

#### Alur Eksekusi:
1. **Authorship**: Product Designer memodifikasi semantik token di Figma Token Studio dan memicu *sync* via GitHub Pull Request.
2. **Schema & Cycle Validation**: Action CI memicu linter JSON schema DTCG dan mengeksekusi Topological Sort script untuk mendeteksi `null references` dan `infinite reference loops`.
3. **AST Transpilation**: Custom parser mengeksekusi pipeline transform:
   - Warna ditranslasikan ke format target masing-masing (`OKLCH` / sRGB CSS, `UIColor` iOS, `androidx.compose.ui.graphics.Color`).
   - Ukuran (Dimension) dikonversi: Web $\rightarrow$ `rem` (basis `16px`), Android $\rightarrow$ `dp`/`sp`, iOS $\rightarrow$ `points` (pt).
4. **Versioning & Publishing**: GitHub Action menandai rilis dengan Semantic Versioning (`fix`: patch, `token added`: minor, `token removed/renamed`: major).
5. **Consumption**: Repositori UI Component Library mengonsumsi package baru, memicu visual regression testing otomatis (Playwright/Storybook).

---

### 6. Analogy & Diagram ASCII

#### Analogi Kompilator Kode (LLVM Framework)
Sistem arsitektur token modern analog dengan arsitektur kompilator modern seperti LLVM:
- **Frontend Compiler**: Mengonversi kode sumber Figma/JSON ke Abstract Syntax Tree (AST) terstandar (DTCG).
- **Intermediate Representation (IR)**: Token dependency tree yang dinormalisasi di dalam memori engine, bebas dari paradigma platform apa pun.
- **Backend Optimization & Code Generation**: Mengonversi IR ke dalam target assembly masing-masing ekosistem: CSS Variable untuk Browser Engine, Swift Structs untuk LLVM iOS, Kotlin Classes untuk JVM Android.

#### Diagram Arsitektur Token Graph DAG

```
                      [Global Tokens]
                     /               \
       {blue.600: #1d72fe}      {neutral.900: #111827}
               │                          │
               ▼                          ▼
    [Semantic: Action-Primary]   [Semantic: Text-Primary]
          /          \                    │
         │            │                   │
         ▼            ▼                   ▼
   [Component]   [Component]         [Component]
   {btn.bg}      {link.fg}           {card.title.color}
```

Jika terjadi mutasi:
$$\text{btn.bg} \rightarrow \text{link.fg} \rightarrow \text{btn.bg}$$
Compiler akan mendeteksi directed cycle dan membatalkan build secara deterministik.

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Format Standar DTCG Token File
File: `tokens/primitives.json`
```json
{
  "color": {
    "brand": {
      "primary": {
        "$value": "#0284c7",
        "$type": "color",
        "$description": "Warna dasar korporat aplikasi"
      }
    },
    "neutral": {
      "0": { "$value": "#ffffff", "$type": "color" },
      "900": { "$value": "#0f172a", "$type": "color" }
    }
  }
}
```

File: `tokens/semantic.json`
```json
{
  "semantic": {
    "color": {
      "background": {
        "action": {
          "$value": "{color.brand.primary}",
          "$type": "color",
          "$description": "Background untuk elemen interaktif primer"
        }
      }
    }
  }
}
```

#### 7.2 Practical Example: Custom Token Engine & Cyclic Dependency Resolver (TypeScript)
Implementasi kustom compiler token engine yang memiliki pendeteksi *cyclic dependency* berbasis Topological Sort (Kahn's Algorithm), disusul translasi ke CSS Custom Properties dan TypeScript Definition:

```typescript
// scripts/token-engine.ts
import * as fs from 'fs';
import * as path from 'path';

interface TokenNode {
  $value: string | number;
  $type: string;
  $description?: string;
}

interface NestedTokenTree {
  [key: string]: NestedTokenTree | TokenNode;
}

interface FlattenedTokens {
  [pathKey: string]: {
    value: string;
    type: string;
    rawReference?: string;
  };
}

export class EnterpriseTokenEngine {
  private rawTokens: NestedTokenTree = {};
  private flattened: FlattenedTokens = {};
  private dependencyGraph: Map<string, Set<string>> = new Map();
  private inDegree: Map<string, number> = new Map();

  public loadTokensFromJSON(filePath: string): void {
    const rawContent = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawContent) as NestedTokenTree;
    this.rawTokens = this.deepMerge(this.rawTokens, parsed);
  }

  private deepMerge(target: any, source: any): any {
    for (const key of Object.keys(source)) {
      if (source[key] instanceof Object && !('$value' in source[key])) {
        Object.assign(source[key], this.deepMerge(target[key] || {}, source[key]));
      }
    }
    return Object.assign(target || {}, source);
  }

  public flattenAndBuildGraph(): void {
    const traverse = (node: any, currentPath: string[] = []) => {
      for (const key of Object.keys(node)) {
        const valueObj = node[key];
        const nextPath = [...currentPath, key];
        const tokenKey = nextPath.join('.');

        if (valueObj && typeof valueObj === 'object' && '$value' in valueObj) {
          const rawVal = String(valueObj.$value);
          this.flattened[tokenKey] = {
            value: rawVal,
            type: valueObj.$type || 'unknown',
          };

          // Inisialisasi graf dependensi
          if (!this.dependencyGraph.has(tokenKey)) {
            this.dependencyGraph.set(tokenKey, new Set());
          }
          if (!this.inDegree.has(tokenKey)) {
            this.inDegree.set(tokenKey, 0);
          }

          // Deteksi referensi dengan syntax {path.to.token}
          const refMatches = rawVal.match(/\{([^}]+)\}/g);
          if (refMatches) {
            for (const ref of refMatches) {
              const targetKey = ref.replace(/[{}]/g, '');
              this.flattened[tokenKey].rawReference = targetKey;

              if (!this.dependencyGraph.has(targetKey)) {
                this.dependencyGraph.set(targetKey, new Set());
              }
              // Dependency edge: targetKey -> tokenKey (targetKey harus di-resolve duluan)
              this.dependencyGraph.get(targetKey)!.add(tokenKey);
              this.inDegree.set(tokenKey, (this.inDegree.get(tokenKey) || 0) + 1);
            }
          }
        } else if (valueObj && typeof valueObj === 'object') {
          traverse(valueObj, nextPath);
        }
      }
    };

    traverse(this.rawTokens);
  }

  public resolveReferences(): void {
    // Topological Sort menggunakan Kahn's Algorithm
    const zeroQueue: string[] = [];
    for (const [key, degree] of this.inDegree.entries()) {
      if (degree === 0) {
        zeroQueue.push(key);
      }
    }

    const resolvedOrder: string[] = [];

    while (zeroQueue.length > 0) {
      const current = zeroQueue.shift()!;
      resolvedOrder.push(current);

      const dependents = this.dependencyGraph.get(current);
      if (dependents) {
        for (const dependent of dependents) {
          // Resolve dependency value
          const targetNode = this.flattened[current];
          const dependentNode = this.flattened[dependent];

          dependentNode.value = dependentNode.value.replace(`{${current}}`, targetNode.value);

          // Kurangi degree
          const updatedDegree = (this.inDegree.get(dependent) || 1) - 1;
          this.inDegree.set(dependent, updatedDegree);
          if (updatedDegree === 0) {
            zeroQueue.push(dependent);
          }
        }
      }
    }

    if (resolvedOrder.length !== Object.keys(this.flattened).length) {
      const unresolvedNodes = Object.keys(this.flattened).filter(
        (key) => (this.inDegree.get(key) || 0) > 0
      );
      throw new Error(
        `[Fatal: Circular Dependency Detected]. Periksa token berikut: ${unresolvedNodes.join(', ')}`
      );
    }
  }

  public generateCSSVariables(): string {
    const lines: string[] = [':root {'];
    for (const [key, node] of Object.entries(this.flattened)) {
      const cssVarName = `--${key.replace(/\./g, '-')}`;
      lines.push(`  ${cssVarName}: ${node.value};`);
    }
    lines.push('}\n');
    return lines.join('\n');
  }

  public generateTypeScriptBindings(): string {
    const typeDefinitions: string[] = [
      'export interface GeneratedDesignTokens {',
    ];
    for (const [key, node] of Object.entries(this.flattened)) {
      const safeKey = `'${key}'`;
      typeDefinitions.push(`  ${safeKey}: string; // Raw resolved: ${node.value}`);
    }
    typeDefinitions.push('}\n');

    typeDefinitions.push('export const designTokens = {');
    for (const [key, node] of Object.entries(this.flattened)) {
      const safeKey = `'${key}'`;
      typeDefinitions.push(`  ${safeKey}: 'var(--${key.replace(/\./g, '-')})',`);
    }
    typeDefinitions.push('} as const;');
    return typeDefinitions.join('\n');
  }
}

// Driver Execution Script
const runPipeline = () => {
  const engine = new EnterpriseTokenEngine();
  
  // Simulasi penulisan input DTCG
  const mockTokens = {
    color: {
      base: {
        blue: { $value: "#1068EB", $type: "color" }
      },
      action: {
        primary: { $value: "{color.base.blue}", $type: "color" }
      }
    },
    component: {
      btn: {
        bg: { $value: "{color.action.primary}", $type: "color" }
      }
    }
  };

  const tempFilePath = path.join(process.cwd(), 'temp-tokens.json');
  fs.writeFileSync(tempFilePath, JSON.stringify(mockTokens, null, 2));

  try {
    engine.loadTokensFromJSON(tempFilePath);
    engine.flattenAndBuildGraph();
    engine.resolveReferences();

    const cssOutput = engine.generateCSSVariables();
    const tsOutput = engine.generateTypeScriptBindings();

    console.log('--- GENERATED CSS ---');
    console.log(cssOutput);

    console.log('--- GENERATED TYPESCRIPT ---');
    console.log(tsOutput);
  } finally {
    if (fs.existsSync(tempFilePath)) fs.unlinkSync(tempFilePath);
  }
};

runPipeline();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: SuperApp Financial Services (Digital Bank, Merchant Portal, & Consumer Wallet)
- **Kondisi Awal**: 
  - Terdapat 3 tim produk terpisah di bawah 1 organisasi.
  - Tim Merchant menggunakan Tailwind CSS; Tim Consumer Web menggunakan Vanilla Extract (CSS-in-JS Zero-runtime); Tim Mobile Native menggunakan Swift (iOS) dan Jetpack Compose (Android).
  - Terdapat 2 Sub-Brand yang diakuisisi secara legal, wajib mengadopsi fungsionalitas aplikasi yang sama persis namun mempertahankan *corporate identity* palet warna dan radius sudut.
- **Isu Performa & Skalabilitas**:
  - Peluncuran tema *Dark Mode* di Web Consumer menyebabkan FOUC (*Flash of Unstyled Content*) selama 150-300ms saat *hydration*.
  - Bundle size web membengkak 42KB karena pengembang menyertakan runtime styling JavaScript yang memproses token heksadesimal on-the-fly.
  - Perubahan nama warna brand dari Figma sering kali merusak komponen produksi mobile karena tidak ada validasi skema di level CI.

#### Arsitektur Solusi Terapan:
1. **Core Token Registry**: Membuat monorepo privat `@enterprise/design-tokens` yang didukung GitHub Actions.
2. **Deterministic Scoping Token Hierarchy**:
   - `core-tokens.json`: Menyimpan kurva interpolasi warna OKLCH dan skala spasi.
   - `brand-bank.json`, `brand-wallet.json`: Berisi semantic mapping.
3. **Optimasi Runtime Zero-Cost Web**:
   - Menghapus dynamic CSS-in-JS runtime. Semua token diekspor menjadi CSS Custom Properties mentah yang dibundel di tahap static generation (`@enterprise/design-tokens/dist/theme.css`).
   - Theme switching (Light/Dark/Sub-brand) dilakukan murni via HTML root attribute: `<html data-brand="wallet" data-theme="dark">`.
   - Menggunakan `@layer tokens, components, utilities;` untuk mencegah *specificity fighting*.
4. **Validasi Pipeline CI/CD**:
   - GitHub Action menjalankan *Visual Breaking Change Gate*: Jika ada semantic token yang dihapus dari skema, bot otomatis mengecek AST dari repositori downstream via GitHub Code Search API dan menolak Pull Request jika token tersebut masih dikonsumsi.

#### Hasil Metrik:
- **0ms Layout Shift/FOUC**: CSS variables diinjeksi via inline layout blocker script sebelum DOM parsing runtime.
- **Bundle Size**: Pengurangan 42KB JS runtime overhead menjadi 0KB (karena murni menggunakan native CSS custom properties).
- **Rilis Multi-Platform**: Lead time dari approval desain hingga ketersediaan di NPM dan CocoaPods turun dari 12 hari menjadi 8 menit.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan Utama | Biaya / Konsekuensi Negatif | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **CSS Variables Runtime Switching** | Ukuran bundle sangat minimal; tema berganti secara dinamis instan tanpa perlu download asset JS tambahan. | Tidak mendukung dynamic tree-shaking CSS yang tidak dipakai; CSS variables dapat bocor ke shadow DOM jika tidak di-scope. | Web application dengan banyak interaksi dinamis tema (Dark Mode, high-contrast user toggle). |
| **Zero-Runtime (Tailwind / Vanilla Extract Compile-time Static Output)** | Type-safety level kompilasi mutlak, dead-code elimination maksimum, performa render browser paling cepat. | Multi-brand dynamic switching memerlukan pemuatan stylesheet ganda atau kompilasi bundel terpisah untuk tiap brand. | Landing page dengan target Web Vitals ekstrem (LCP < 1.0s) dengan satu brand identitas. |
| **Component-Scoped Tokens (Tier 3 Lengkap)** | Fleksibilitas pemeliharaan tinggi; insinyur dapat mengubah warna tombol tanpa risiko merusak komponen lain. | Kompleksitas manajemen grafik meningkat tajam; jumlah token dapat melonjak hingga ribuan file JSON. | Enterprise Design System dengan >100 downstream insinyur dan >50 komponen atomik kompleks. |
| **Semantic Only Tokens (Hanya Tier 1 & Tier 2)** | Sederhana, mudah diadopsi tim, learning curve rendah, file token kecil. | Jika sebuah tombol membutuhkan pengecualian margin/warna spesifik, arsitektur dipaksa memecah semantik umum atau memakai CSS override lokal yang merusak sistem. | Startup atau produk skala menengah dengan komponen di bawah 30 jenis dan brand identitas tunggal. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Reference Cycles Pada Layer Semantik
- **Gejala**: CPU CI/CD 100%, memory leak, compiler error `Maximum call stack size exceeded`.
- **Penyebab**: Seseorang di Figma Tokens Studio salah menghubungkan referensi secara melingkar:
  ```json
  "color.bg.action": "{color.bg.interactive}",
  "color.bg.interactive": "{color.bg.action}"
  ```
- **Solusi Troubleshooting**:
  Selalu implementasikan Kahn's Algorithm atau Depth-First Search dengan status state node: `UNVISITED`, `VISITING`, `VISITED`. Jika saat traversal node berstatus `VISITING` kembali dikunjungi, lempar error fatal dengan jalur siklus lengkap:

```typescript
function detectCycle(graph: Map<string, string[]>): void {
  const visited = new Set<string>();
  const inStack = new Set<string>();

  function dfs(node: string, path: string[]): void {
    visited.add(node);
    inStack.add(node);
    path.push(node);

    const neighbors = graph.get(node) || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        dfs(neighbor, [...path]);
      } else if (inStack.has(neighbor)) {
        throw new Error(`Circularity: ${[...path, neighbor].join(' -> ')}`);
      }
    }
    inStack.delete(node);
  }

  for (const node of graph.keys()) {
    if (!visited.has(node)) dfs(node, []);
  }
}
```

#### 2. Flash of Unstyled Content (FOUC) saat Dynamic Hydration
- **Gejala**: Layar berkedip putih sebelum berubah menjadi gelap saat pengguna yang mengaktifkan Dark Mode me-refresh halaman pada arsitektur SSR (Next.js / Remix).
- **Penyebab**: Class atau atribut token (`data-theme="dark"`) disematkan lewat JavaScript `useEffect` di sisi client setelah browser melakukan First Contentful Paint (FCP).
- **Solusi Troubleshooting**:
  Suntikkan *render-blocking inline critical script* langsung di bagian paling atas `<head>`:
  ```html
  <head>
    <script>
      (function() {
        try {
          const theme = localStorage.getItem('theme') || 
            (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
          document.documentElement.setAttribute('data-theme', theme);
        } catch (e) {}
      })();
    </script>
  </head>
  ```

#### 3. Specificity Leakage pada Web Micro-Frontend
- **Gejala**: Token dari Micro-Frontend A (misal: Checkout) menimpa token di Micro-Frontend B (misal: Header/Nav) karena deklarasi `:root` global bertabrakan.
- **Solusi**: Gunakan *Scoping Container Class* atau CSS Cascading Layers (`@layer`) daripada mendefinisikan seluruh variabel di `:root`:
  ```css
  /* Hindari deklarasi telanjang tanpa boundary */
  @layer tokens.mfe-checkout {
    .mfe-checkout-boundary {
      --color-brand-primary: #ff0055;
    }
  }
  ```

---

### 11. Best Practices (Production Checklist)

#### Token Taxonomy & Structure
- [ ] Terapkan format case yang konsisten pada key: `category-type-item-variant-state` (misal: `color-surface-danger-bold-hover`).
- [ ] Semua dimensi ukuran font **wajib** menggunakan unit `rem` untuk Web guna menjaga aksesibilitas (*screen reader / accessibility zooming*).
- [ ] Seluruh token warna harus diekspresikan minimal dalam standard CSS Color Module Level 4 (`oklch` atau `p3`) untuk jangkauan *wide-gamut displays*.

#### Continuous Integration & Engine
- [ ] Linting skema DTCG terintegrasi ke dalam *pre-commit hook* dan *GitHub Action*.
- [ ] Compiler wajib menjalankan deteksi referensi kosong (*null dangling references*) dan referensi siklik (*cyclic dependencies*).
- [ ] Setup script automated deprecation notices: Jika token dihapus, masukkan ke dalam array `deprecated-tokens.json` dan berikan warning di konsol saat kompilasi.

#### Downstream Integration
- [ ] Ekspor type definition TypeScript yang immutable (`as const`) dan sediakan mapping template literal types.
- [ ] Distribusikan token dalam multi-format bundles: ESM (`index.mjs`), CJS (`index.cjs`), raw CSS (`tokens.css`), dan JSON AST (`tokens.ast.json`).
- [ ] Integrasikan visual regression test (misal: Playwright) yang mencakup mode: Light, Dark, High-Contrast, dan Seluruh Sub-brand.

---

### 12. Hands-on Practice: Membangun Multi-Platform Production Token Compiler

Mari membangun pipeline kompilasi token enterprise di workspace: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek dan Instalasi Dependensi
Jalankan di terminal:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install --save-dev typescript @types/node style-dictionary@^4.0.0-prerelease.29 tsx
npx tsc --init
```

#### Langkah 2: Buat Skema Token DTCG Mentah
Buat file `hands-on/m02/tokens/primitives.json`:
```json
{
  "color": {
    "palette": {
      "neutral-100": { "$value": "#f3f4f6", "$type": "color" },
      "neutral-900": { "$value": "#111827", "$type": "color" },
      "emerald-500": { "$value": "#10b981", "$type": "color" },
      "rose-500": { "$value": "#f43f5e", "$type": "color" }
    }
  },
  "dimension": {
    "spacing": {
      "sm": { "$value": "8px", "$type": "dimension" },
      "md": { "$value": "16px", "$type": "dimension" },
      "lg": { "$value": "24px", "$type": "dimension" }
    },
    "radius": {
      "sm": { "$value": "4px", "$type": "dimension" },
      "full": { "$value": "9999px", "$type": "dimension" }
    }
  }
}
```

Buat file `hands-on/m02/tokens/semantic-light.json`:
```json
{
  "semantic": {
    "surface": {
      "background": { "$value": "{color.palette.neutral-100}", "$type": "color" },
      "foreground": { "$value": "{color.palette.neutral-900}", "$type": "color" }
    },
    "status": {
      "success": { "$value": "{color.palette.emerald-500}", "$type": "color" },
      "danger": { "$value": "{color.palette.rose-500}", "$type": "color" }
    }
  }
}
```

Buat file `hands-on/m02/tokens/semantic-dark.json`:
```json
{
  "semantic": {
    "surface": {
      "background": { "$value": "{color.palette.neutral-900}", "$type": "color" },
      "foreground": { "$value": "{color.palette.neutral-100}", "$type": "color" }
    }
  }
}
```

#### Langkah 3: Konfigurasi Compiler Engine Lanjutan
Buat file pipeline kompilasi `hands-on/m02/build-tokens.ts`:
```typescript
import StyleDictionary from 'style-dictionary';
import type { Config, TransformedToken } from 'style-dictionary/types';
import * as fs from 'fs';
import * as path from 'path';

// 1. Daftarkan Custom Transform: Konversi px ke rem
StyleDictionary.registerTransform({
  name: 'size/pxToRem',
  type: 'value',
  matcher: (token: TransformedToken) => token.$type === 'dimension' && String(token.$value).endsWith('px'),
  transform: (token: TransformedToken) => {
    const rawVal = parseFloat(String(token.$value));
    if (isNaN(rawVal)) return token.$value;
    if (rawVal === 0) return '0';
    return `${rawVal / 16}rem`;
  }
});

// 2. Custom Format: Tailwind CSS Theme Config Partial
StyleDictionary.registerFormat({
  name: 'custom/tailwind-theme',
  format: ({ dictionary }) => {
    const themeTree: Record<string, Record<string, string>> = {
      colors: {},
      spacing: {},
      borderRadius: {}
    };

    dictionary.allTokens.forEach((token) => {
      const parts = token.path;
      if (token.$type === 'color') {
        const key = parts.slice(parts.indexOf('palette') + 1).join('-');
        if (key) themeTree.colors[key] = token.value;
      } else if (parts.includes('spacing')) {
        themeTree.spacing[parts[parts.length - 1]] = token.value;
      } else if (parts.includes('radius')) {
        themeTree.borderRadius[parts[parts.length - 1]] = token.value;
      }
    });

    return `// Auto-generated. Do not edit directly.\nmodule.exports = ${JSON.stringify(themeTree, null, 2)};\n`;
  }
});

// 3. Konfigurasi Multi-Platform Pipeline
function getStyleDictionaryConfig(theme: 'light' | 'dark'): Config {
  const semanticSource = theme === 'light' 
    ? 'tokens/semantic-light.json' 
    : 'tokens/semantic-dark.json';

  const selector = theme === 'light' ? ':root, [data-theme="light"]' : '[data-theme="dark"]';

  return {
    source: ['tokens/primitives.json', semanticSource],
    platforms: {
      css: {
        transforms: ['attribute/cti', 'name/kebab', 'size/pxToRem'],
        buildPath: 'dist/css/',
        files: [
          {
            destination: `theme-${theme}.css`,
            format: 'css/variables',
            options: {
              selector: selector,
              outputReferences: true
            }
          }
        ]
      },
      tailwind: {
        transforms: ['attribute/cti', 'name/kebab', 'size/pxToRem'],
        buildPath: 'dist/tailwind/',
        files: [
          {
            destination: 'theme.cjs',
            format: 'custom/tailwind-theme'
          }
        ]
      },
      ts: {
        transforms: ['attribute/cti', 'name/camel'],
        buildPath: 'dist/ts/',
        files: [
          {
            destination: `tokens-${theme}.ts`,
            format: 'javascript/es6'
          },
          {
            destination: `tokens-${theme}.d.ts`,
            format: 'typescript/es6-declarations'
          }
        ]
      }
    }
  };
}

async function run() {
  console.log('🚀 Memulai Kompilasi Multi-Platform Token Engine...');
  
  // Clean dist directory
  const distPath = path.join(process.cwd(), 'dist');
  if (fs.existsSync(distPath)) {
    fs.rmSync(distPath, { recursive: true });
  }

  // Compile Light Theme
  const sdLight = new StyleDictionary(getStyleDictionaryConfig('light'));
  await sdLight.buildAllPlatforms();
  console.log('✔ Light Theme selesai di-build.');

  // Compile Dark Theme
  const sdDark = new StyleDictionary(getStyleDictionaryConfig('dark'));
  await sdDark.buildAllPlatforms();
  console.log('✔ Dark Theme selesai di-build.');

  console.log('✨ Build Sukses! Cek folder hands-on/m02/dist/');
}

run().catch((err) => {
  console.error('❌ Build Gagal:', err);
  process.exit(1);
});
```

#### Langkah 4: Eksekusi dan Verifikasi Output
Update `package.json` untuk menambahkan build script:
```json
{
  "scripts": {
    "build:tokens": "tsx build-tokens.ts"
  }
}
```

Jalankan perintah build:
```bash
npm run build:tokens
```

Periksa hasil artefak yang terbentuk pada direktori:
- `dist/css/theme-light.css` & `dist/css/theme-dark.css`
- `dist/tailwind/theme.cjs`
- `dist/ts/tokens-light.ts` & `dist/ts/tokens-light.d.ts`

---

### 13. Exercises

#### 13.1 Level Easy: Menambahkan Skala Tipografi DTCG
- **Tugas**: Tambahkan kelompok token tipografi pada `tokens/primitives.json` yang berisi properti `$type: "fontFamilies"`, `$type: "fontSizes"`, dan `$type: "lineHeights"`.
- **Spesifikasi**:
  - Font families: `sans` bernilai `"Inter", sans-serif` dan `mono` bernilai `"Fira Code", monospace`.
  - Font sizes: `body-sm` (`14px`), `body-md` (`16px`), `display-lg` (`32px`).
- **Petunjuk**: Pastikan transform `size/pxToRem` yang dibuat pada *hands-on* dapat secara otomatis mengonversi `fontSizes` ke `rem`.

#### 13.2 Level Medium: Custom Transformer untuk Jetpack Compose (Android)
- **Tugas**: Daftarkan format kustom Style Dictionary bernama `custom/android-compose` yang mengubah token warna menjadi class file Kotlin: `dist/android/ColorTokens.kt`.
- **Spesifikasi Format File Output**:
  ```kotlin
  package com.enterprise.designsystem.tokens

  import androidx.compose.ui.graphics.Color

  object ColorTokens {
      val paletteNeutral100 = Color(0xFFF3F4F6)
      val paletteNeutral900 = Color(0xFF111827)
  }
  ```
- **Petunjuk**: Gunakan parser warna untuk mengonversi Hex 6 karakter (`#RRGGBB`) menjadi format ARGB 8 karakter Kotlin (`0xFFRRGGBB`).

#### 13.3 Level Hard: AST Codemod untuk Migrasi Token yang Terdeprecasi
- **Tugas**: Buat script migrasi menggunakan `jscodeshift` atau TypeScript Compiler API (`ts-morph`) di folder `scripts/migrate-tokens.ts`.
- **Kasus**: Tim desain mengubah semantik token dari `semantic.surface.background` menjadi `semantic.surface.canvas.primary`.
- **Ekspektasi Kode**: Script harus mampu memindai direktori file komponen `.tsx` konsumen, menemukan referensi lama, dan me-replace AST node secara otomatis tanpa merusak formatting kode lainnya:
  ```typescript
  // Sebelum migrasi
  const Card = styled.div`
    background-color: var(--semantic-surface-background);
  `;

  // Sesudah dieksekusi codemod
  const Card = styled.div`
    background-color: var(--semantic-surface-canvas-primary);
  `;
  ```

---

### 14. Challenge: Arsitektur Token Multi-Tenant Dinamis Tanpa FOUC & Tanpa CSS Re-computation

#### Deskripsi Tantangan:
Anda adalah Principal Design System Architect di sebuah platform SaaS B2B Enterprise yang melayani 200+ penyewa (*tenants*). Setiap *tenant* memiliki skema warnanya sendiri (*custom whitelabeling*). Tenant dapat mengubah warna primer, sekunder, dan radius komponen mereka secara instan melalui dashboard pengaturan admin.

#### Batasan Rekayasa & Persyaratan Sistem:
1. **Zero FOUC**: Halaman yang diakses oleh customer tenant tidak boleh mengalami kedipan warna asal (*default brand*) sedetik pun saat pemuatan pertama.
2. **Zero Client-side Runtime Overhead**: Anda dilarang menggunakan CSS-in-JS berbasis runtime (seperti runtime Emotion atau styled-components) karena menghambat Largest Contentful Paint (LCP).
3. **No Infinite CSS Bloat**: Anda dilarang membundel 200 file CSS statis milik masing-masing tenant ke dalam aplikasi client.
4. **Security Hardening**: Sistem harus mencegah eksploitasi CSS Injection (misal: penyerang mencoba menutup deklarasi variabel dengan `; } body { display: none; }` melalui input tenant admin API).

#### Output yang Diharapkan:
Tuliskan cetak biru desain teknis (*Technical Architecture RFC*) dan prototipe kode lengkap yang mencakup:
- Strategi penyimpanan dan sanitasi token tenant di sisi database.
- Dynamic Edge-Injection Pipeline (menggunakan Next.js Edge Middleware / Cloudflare Workers) untuk menyuntikkan tokens via HTTP Response Streaming sebelum parsing DOM client dimulai.
- Skema isolasi scope token untuk memastikan konfigurasi Tenant A tidak dapat membocorkan state gaya ke Tenant B.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama pemisahan antara *Global/Primitive Tokens* dan *Semantic Tokens*?
   - A. Menambah kompleksitas agar file CSS lebih panjang.
   - B. Memisahkan nilai heksadesimal mentah dari peran fungsionalnya sehingga penggantian tema (misal: Light ke Dark) dapat dilakukan tanpa menduplikasi primitif.
   - C. Memastikan desainer grafis tidak dapat mengubah format JSON.
   - D. Meniadakan perlunya unit test styling di repositori frontend.
   *Jawaban*: **B**

2. Pada format spesifikasi resmi *Design Tokens Community Group* (DTCG), properti mana yang wajib digunakan untuk mendefinisikan nilai konkret dari token?
   - A. `value`
   - B. `val`
   - C. `$value`
   - D. `data`
   *Jawaban*: **C**

3. Mengapa token dimensi untuk ukuran font di web disarankan dikompilasi ke unit `rem` daripada `px` statis?
   - A. Supaya ukuran file CSS lebih kecil beberapa byte.
   - B. Browser tidak memahami unit `px` pada layar Retina.
   - C. Untuk menghormati pengaturan *root font size* preferensi pengguna pada browser demi standar aksesibilitas (a11y).
   - D. `rem` mencegah layout shift saat halaman di-scroll.
   *Jawaban*: **C**

4. Dalam struktur graf dependensi token, apa yang dimaksud dengan node yang memiliki *In-Degree = 0*?
   - A. Token yang tidak memiliki referensi ke token lain (Token Primitif/Akar).
   - B. Token yang terhapus dan menjadi sampah (Dead token).
   - C. Token yang menyebabkan *circular error*.
   - D. Komponen scoped token yang sangat kompleks.
   *Jawaban*: **A**

5. Cara paling efektif untuk mengeliminasi Flash of Unstyled Content (FOUC) saat menerapkan tema gelap/terang berbasis SSR adalah:
   - A. Menggunakan `useEffect` di React untuk membaca `localStorage`.
   - B. Menaruh inline blocking script di dalam tag `<head>` sebelum CSS utama dan DOM diparsing.
   - C. Menunggu proses hidrasi selesai baru memunculkan halaman (menampilkan blank page).
   - D. Memaksa pengguna selalu berada di tema Light mode.
   *Jawaban*: **B**

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)
6. Manakah dari graph berikut yang **PASTI** menyebabkan infinite loop pada token pipeline compiler?
   - A. $A \rightarrow B \rightarrow C \rightarrow D$
   - B. $A \rightarrow B$; $A \rightarrow C$; $B \rightarrow D$; $C \rightarrow D$
   - C. $A \rightarrow B \rightarrow C \rightarrow A$
   - D. $A \rightarrow B$; $C \rightarrow D$
   *Jawaban*: **C**. Karena membentuk siklus tertutup di mana $A$ bergantung pada dirinya sendiri secara transitif melalui $B$ dan $C$.

7. Apa tujuan arsitektur menggunakan CSS `@layer tokens, components, utilities;`?
   - A. Menjamin deklarasi utilities selalu memiliki prioritas specificity lebih tinggi daripada tokens dan components tanpa membutuhkan manipulasi `!important`.
   - B. Mengompres file CSS menjadi format Gzip lebih cepat.
   - C. Membaca variabel dari framework React secara native.
   - D. Menghubungkan Figma REST API langsung ke runtime browser.
   *Jawaban*: **A**

8. Jika token `{ "size": { "$value": "16px", "$type": "dimension" } }` dikompilasi untuk target Android Native, representasi output terbaik di Jetpack Compose adalah:
   - A. `val size = 16.px`
   - B. `val size = 16.dp`
   - C. `val size = "16px"`
   - D. `val size = 16.pt`
   *Jawaban*: **B**. Pada ekosistem Android Native, ukuran dimensi non-teks wajib dikonversi menjadi Density-independent Pixels (`dp`).

9. Mengapa penggunaan library CSS-in-JS berbasis runtime (seperti legacy Styled Components) mulai ditinggalkan dalam arsitektur token modern skala enterprise?
   - A. Karena tidak mendukung bahasa pemrograman TypeScript.
   - B. Menyebabkan overhead CPU berupa serialization, dynamic CSS injection ke `<head>`, dan memperburuk metrik web vitals (INP dan LCP).
   - C. Library tersebut tidak kompatibel dengan Figma Token Studio.
   - D. Styled Components tidak mendukung penulisan CSS hex warna.
   *Jawaban*: **B**

10. Apa kelemahan utama dari strategi "Component-Scoped Tokens" jika diterapkan terlalu dini pada startup berukuran kecil?
    - A. Desain aplikasi menjadi lambat di-render oleh GPU browser.
    - B. Overhead pemeliharaan (*maintenance surface*) membengkak drastis akibat ribuan variabel duplikatif sebelum abstraksi desain benar-benar matang.
    - C. Tidak didukung oleh compiler Style Dictionary.
    - D. Memerlukan server khusus berbasis Rust atau Go.
    *Jawaban*: **B**

---

#### Bagian 3: Production Scenarios (Analisis Kasus Nyata)

**Skenario Kasus 1**:
Sebuah tim mengintegrasikan 4 brand turunan ke dalam 1 repositori e-commerce. Desainer mengubah nilai dari semantik `color.brand.interactive` khusus untuk Brand B. Namun, setelah di-deploy ke staging, komponen pada Brand A dan Brand C ikut berubah warnanya.
- **Pertanyaan**: Di manakah letak kesalahan arsitektur token ini dan bagaimana mekanisme perbaikannya?
- **Analisis Jawaban**:
  Kesalahan terjadi karena pelanggaran isolasi hirarki token (*Coupling Violation*). Tim memetakan token Semantic Brand A, B, dan C ke satu node Primitif yang sama, atau Brand B salah meng-override layer Primitif global alih-alih me-remap layer Semantic khusus miliknya. Solusinya:
  1. Pisahkan berkas semantic per brand: `tokens/brands/brand-a/semantic.json`, `tokens/brands/brand-b/semantic.json`.
  2. Compiler Style Dictionary harus memproses setiap brand dengan jalur target build terpisah (*isolated platform passes*) atau menggunakan CSS Custom Property Scoping berbasis attribute tenant (`[data-brand="brand-b"] { --color-interactive: ... }`).

**Skenario Kasus 2**:
Pipeline CI token Anda melempar error `Topological Sort Failed: Cyclic Dependency Detected`. Namun, repositori Anda memiliki lebih dari 3.000 baris file JSON token, sehingga sangat sulit untuk mencari file mana yang bermasalah secara manual.
- **Pertanyaan**: Rancang strategi algoritma langkah demi langkah untuk melacak dan menampilkan rute siklus tersebut ke log konsol developer secara instan!
- **Analisis Jawaban**:
  1. Bangun Adjacency List (Directed Graph) dari file token di memori.
  2. Jalankan algoritma Depth First Search (DFS) dengan pewarnaan node (*Three-Color Marking*):
     - Putih: Node belum dikunjungi (*Unvisited*).
     - Abu-abu: Node sedang dalam stack eksplorasi rekursif saat ini (*In-Progress/Visiting*).
     - Hitam: Node selesai dieksplorasi (*Finished/Visited*).
  3. Simpan rekaman jejak path traversal dalam sebuah array (`currentPath: string[]`).
  4. Ketika fungsi mendatangi node tetangga yang sedang berwarna **Abu-abu**, ambil indeks node tersebut dari `currentPath`. Iris array dari titik tersebut ke akhir: `cycleTrace = currentPath.slice(indexOfNeighbor).concat(neighbor)`.
  5. Cetak log string informatif: `Fatal Cycle: button.bg -> action.primary -> button.bg` dan hentikan eksekusi via `process.exit(1)`.

**Skenario Kasus 3**:
Saat melakukan transisi Micro-Frontend dari Webpack Module Federation lama ke arsitektur mandiri, ditemukan bahwa micro-app "Payments" memiliki ukuran font Button yang 4px lebih kecil dibanding micro-app "Dashboard", padahal keduanya menggunakan token yang sama: `font.size.button: 1rem`.
- **Pertanyaan**: Apa akar masalah arsitektur CSS di tingkat browser yang menyebabkan anomali ini dan bagaimana cara mengatasinya?
- **Analisis Jawaban**:
  Akar masalahnya adalah manipulasi elemen `:root` / `html` font-size global yang berbeda antar host aplikasi. Satuan `rem` bergantung secara mutlak pada nilai `font-size` yang disetel pada tag `<html>`. Micro-app "Dashboard" kemungkinan menyetel `html { font-size: 16px; }` (1rem = 16px), sedangkan micro-app "Payments" menyetel `html { font-size: 12px; }` atau `62.5%` (1rem = 10px / 12px).
  Solusi Enterprise:
  1. Larang micro-app anak menyentuh root base font-size browser. Standarkan root font-size ke default native browser (100% atau 16px).
  2. Jika integrasi host tidak dapat dihindari, isolasi scope token micro-app anak dengan mendefinisikan skala menggunakan satuan mutlak terisolasi, atau gunakan *CSS Custom Property Calculation Isolation*: `--base-rem: 16px; font-size: calc(var(--base-rem) * 1);`.

---

### 16. Summary

1. **Multi-Tier Token Taxonomy**: Pondasi kokoh design system enterprise bertumpu pada pemisahan layer yang ketat: Global Tokens (Primitif tanpa semantik) $\rightarrow$ Semantic Tokens (Kontekstual fungsional & identitas tema) $\rightarrow$ Component-Scoped Tokens (Isolasi boundary internal komponen).
2. **DAG Compilation Pipeline**: Pemrosesan token skala produksi identik dengan mekanisme kerja compiler modern. Seluruh token wajib divalidasi sebagai *Directed Acyclic Graph* (DAG). Siklus dependensi diselesaikan via *Topological Sort* sebelum diterjemahkan ke format target.
3. **Cross-Platform Delivery**: Format DTCG ($value, $type) adalah representasi abstrak tunggal (*Single Source of Truth*). Compiler bertugas memproyeksikannya menjadi native constructs yang idiomatik: CSS Variables untuk Web, Jetpack Compose untuk Android, dan Swift Types untuk iOS.
4. **Zero-Runtime & Performance**: Arsitektur token terbaik beroperasi pada fase *build-time* atau memanfaatkan *native platform primitives* (seperti CSS custom properties dan CSS layers). Hindari komputasi runtime JS styling untuk memastikan First Contentful Paint (FCP) dan Interaction to Next Paint (INP) yang optimal.