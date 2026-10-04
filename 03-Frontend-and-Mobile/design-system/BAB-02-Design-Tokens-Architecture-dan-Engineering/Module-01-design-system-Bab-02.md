# Bab 02 Module 01: Design Tokens Architecture & Engineering

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Mata Kuliah:** Enterprise Design Systems Engineering
*   **Kode Modul:** `DS-ENG-0201`
*   **Topik:** Design Tokens Architecture & Engineering
*   **Level Kompleksitas:** Advanced / Staff Engineer Level
*   **Prasyarat Konseptual:** 
    *   Penguasaan TypeScript tingkat lanjut (Template Literal Types, Type Inference, AST basics).
    *   Pemahaman ekosistem CSS modern (CSS Custom Properties, PostCSS, Sass compilation targets).
    *   Prinsip dasar platform primitives: React/Web, iOS (Swift/SwiftUI), dan Android (Kotlin/Jetpack Compose).
    *   Konsep Abstract Syntax Trees (AST) dan compiler pipeline dasar (Lexing, Parsing, Transforming, Codegen).
*   **Estimasi Waktu Selesai:** 6 Jam Pembelajaran Mandiri + 4 Jam Lab Praktikum

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Merancang Arsitektur Tiering Multi-Layer Design Token:** Mengimplementasikan pola 3-tier (*Global/Primitive*, *Semantic/Alias*, *Component-scoped*) yang memisahkan nilai absolut (*raw values*) dari konteks pemakaian (*intent*).
2.  **Membangun Engine Transformasi Lintas Platform Otomatis:** Mengonfigurasi dan memodifikasi pipeline transformasi (seperti Style Dictionary versi 4+) untuk menghasilkan artefak produksi lintas platform (CSS, SCSS, TypeScript, Swift, Jetpack Compose) tanpa inkonsistensi representasi warna dan ukuran.
3.  **Mengoperasikan Sinkronisasi Figma-to-Code Tanpa Drift:** Mengintegrasikan schema berbasis *W3C Design Tokens Community Group (DTCG)* menggunakan GitHub Actions untuk menangani sinkronisasi dua arah dan validasi otomatis.
4.  **Mencegah dan Mendeteksi Breaking Changes Token:** Menerapkan pengujian regresi visual, pelacakan dependensi token via graph resolution, dan verifikasi rasio kontras warna WCAG 2.1 AAA secara terprogram pada fase CI/CD.
5.  **Mengoptimalkan Runtime CSS Variables:** Menghilangkan overhead render tree, layout recalculation, dan paint phase yang disebabkan oleh injeksi token dinamis yang salah melalui CSS variables scoping yang efisien.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Perubahan Paradigma: Dari "Style File" ke "Data Contract"

Pendekatan konvensional memandang variabel warna, tipografi, dan spasi sebagai konstanta utilitas visual yang ditulis langsung pada stylesheet (`_variables.scss` atau file utilitas Tailwind). Pendekatan ini gagal pada organisasi multi-platform berskala besar karena:
1. Menghasilkan *drift* (deviasi visual) antara desainer dan engineer lintas platform.
2. Memaksa logika bisnis styling ditulis ulang berulang kali untuk setiap platform (Web, iOS, Android).
3. Mengabaikan relasi dependensi antarnilai (misalnya: warna teks harus merujuk pada intensitas kontras latar belakang).

```
PENDEKATAN MONOLITIK (RAPUH):
[Figma] --(Manual Copy-Paste)--> CSS File / SCSS Variables (Hanya Web)
                                  -> Dev iOS buat struct terpisah
                                  -> Dev Android buat XML/Compose terpisah

PENDEKATAN TOKEN KONTRAK DATA (ENTERPRISE):
[Figma Token JSON] (Single Source of Truth)
        │
        ▼
[Validator & Parser Engine] (Schema DTCG, AST Resolution, WCAG Validation)
        │
        ├──► Web Artifacts (CSS Variables, TypeScript Consts, Tailwind Theme)
        ├──► iOS Artifacts (Swift Structs, Color Assets, SwiftUI Modifiers)
        └──► Android Artifacts (Kotlin Objects, Jetpack Compose Material 3)
```

Design Token bukanlah file konfigurasi tampilan; **Design Token adalah protokol kontrak data terdistribusi (Distributed Data Contract)** yang mendefinisikan keputusan desain (*design decisions*) independen terhadap runtime platform. Token merepresentasikan tipe data primitif, relasi, dan aturan semantik yang dikompilasi ke dalam target biner atau teks native masing-masing ekosistem platform.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah alur kompilasi token dari Figma Tokens JSON / DTCG Schema hingga menjadi artefak terdistribusi yang dikonsumsi oleh aplikasi klien:

```
+-----------------------------------------------------------------------------+
|                             AUTHORING PHASE                                 |
|  [Figma Token Studio] / [Hand-written DTCG JSON Repositories]               |
+-----------------------------------------------------------------------------+
                                      │
                                      ▼ (Webhook / GitHub PR)
+-----------------------------------------------------------------------------+
|                       TOKEN COMPILATION PIPELINE                            |
|                                                                             |
|  +--------------------+      +---------------------+                        |
|  |  Schema Validation | ---> | Graph Dependency    |                        |
|  |  (Zod / AJV DTCG)  |      | Resolver & DAG      |                        |
|  +--------------------+      +---------------------+                        |
|                                         │                                   |
|                                         ▼                                   |
|                              +---------------------+                        |
|                              | Cycle Detection     |                        |
|                              | (Tarjan / Kahn Alg) |                        |
|                              +---------------------+                        |
|                                         │                                   |
|                                         ▼                                   |
|  +-----------------------------------------------------------------------+  |
|  | Transformation Engine (Style Dictionary 4.x / Custom Transformer)    |  |
|  +-----------------------------------------------------------------------+  |
|       │ (Transforms: Px->Rem, Hex->Oklch, Kebab->Camel, Swift/Compose)      |
+-------┼─────────────────────────────────────────────────────────────────────+
        │
        ├──► Web Output:
        │    ├── tokens.css       (:root { --color-surface-primary: #fff; })
        │    ├── tokens.d.ts      (export const SurfacePrimary = "var(...)";)
        │    └── tailwind.json    ({ theme: { extend: { ... } } })
        │
        ├──► iOS Output:
        │    ├── DesignTokens.swift (public static let surfacePrimary = Color(...))
        │    └── Assets.xcassets    (Colorsets JSON)
        │
        └──► Android Output:
             ├── DesignTokens.kt  (val SurfacePrimary = Color(0xFFFFFFFF))
             └── values/colors.xml (<color name="surface_primary">#ffffff</color>)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Arsitektur 3-Tier Design Tokens

Struktur design tokens harus diorganisir ke dalam tiga lapisan abstraksi terpisah untuk menjamin skalabilitas, kemampuan rebranding, dan dukungan theming (seperti Dark Mode dan High Contrast):

```
+----------------------------------------------------------------------------+
| TIER 1: GLOBAL / PRIMITIVE TOKENS                                          |
| Nilai mentah tanpa konteks semantik atau intensi pemakaian.               |
| Contoh: "color.palette.blue.600" = "#1D4ED8", "size.dimension.16" = "16px"  |
+----------------------------------------------------------------------------+
                                      │
                                      ▼ Direferensikan oleh
+----------------------------------------------------------------------------+
| TIER 2: SEMANTIC / ALIAS TOKENS                                            |
| Abstraksi konteks pemakaian (intent-based, state, feedback).                |
| Contoh: "color.surface.action.primary.hover" = "{color.palette.blue.600}"  |
+----------------------------------------------------------------------------+
                                      │
                                      ▼ Direferensikan oleh
+----------------------------------------------------------------------------+
| TIER 3: COMPONENT-SCOPED TOKENS                                            |
| Diisolasi secara ketat pada scope komponen tertentu.                       |
| Contoh: "btn.solid.bg.hover" = "{color.surface.action.primary.hover}"      |
+----------------------------------------------------------------------------+
```

### Format Standar DTCG (Design Tokens Community Group)
Sesuai draft spesifikasi W3C DTCG, setiap node token harus memiliki struktur formal berikut:

```json
{
  "color": {
    "background": {
      "interactive": {
        "primary": {
          "$value": "{color.palette.blue.600.value}",
          "$type": "color",
          "$description": "Latar belakang utama untuk tombol dan link aksi utama.",
          "$extensions": {
            "org.enterprise.metadata": {
              "status": "stable",
              "deprecated": false,
              "wcagPair": "{color.text.inverse.value}"
            }
          }
        }
      }
    }
  }
}
```

*   `$value`: Nilai akhir atau alias string yang menunjuk ke token lain dengan notasi kurung kurawal `{path.to.token.value}`.
*   `$type`: Mendefinisikan transformer mana yang harus mengevaluasi nilai tersebut (`color`, `dimension`, `duration`, `fontFamily`, `fontWeight`, `shadow`, `border`).
*   `$description`: Dokumentasi internal yang akan diekstraksi menjadi komentar pada file target (JSDoc, Swift Doc, KDoc).
*   `$extensions`: Metadata ekstensi pihak ketiga atau tooling internal perusahaan.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Representasi Graf Dependensi (Directed Acyclic Graph)
Token yang saling mereferensikan membentuk Graf Berarah (*Directed Graph*). Pipeline kompilasi token harus mengonversi graf tersebut menjadi pohon dependensi non-siklik (*Directed Acyclic Graph* atau DAG).

Misalkan kita memiliki node:
1. $T_1 = \text{blue.500} = \text{\#3B82F6}$ (Root Dependency / In-degree = 0)
2. $T_2 = \text{action.primary.base} \to T_1$
3. $T_3 = \text{button.primary.bg.default} \to T_2$

Jika terdapat kesalahan konfigurasi manusia di mana $T_1$ secara tidak sengaja mereferensikan $T_3$, siklus tak terhingga ($T_1 \to T_3 \to T_2 \to T_1$) terjadi. Engine kompilasi harus mengeksekusi algoritma pendeteksi siklus (seperti Depth-First Search dengan three-color marking atau algoritma Kahn) sebelum mengevaluasi nilai token.

### 2. Resolusi Ruang Warna (Color Space Precision & Transformations)
Di era layar Wide-Gamut (Display P3) dan standar modern, token warna tidak boleh terbatas pada sRGB (format `#RRGGBB`). Warna harus diproses melalui transformasi matematis:

$$E = \text{Oklch}(L, C, h)$$

Dimana:
*   $L$ (Perceptual Lightness): $0.0$ sampai $1.0$ (kecerahan yang dipersepsikan manusia secara seragam).
*   $C$ (Chroma): $0.0$ sampai $\sim 0.4$ (saturasi).
*   $h$ (Hue angle): $0^{\circ}$ sampai $360^{\circ}$ (sudut warna).

Mengonversi Hex/sRGB ke Oklch saat kompilasi Web Token memungkinkan desainer membuat palet adaptif kontras tinggi yang secara matematis mempertahankan rasio kontras saat berganti tema, tanpa distorsi saturasi yang sering terjadi pada model HSL konvensional.

### 3. Layout Recalculation & Runtime Invalidation
Ketika menginjeksi token sebagai CSS Custom Properties (`--token-name`), penempatannya pada DOM tree berdampak langsung pada performa browser rendering pipeline:

*   **Global Variables (`:root`)**: Berada di puncak hirarki. Perubahan dinamis pada runtime menggunakan JavaScript via `document.documentElement.style.setProperty('--color-bg', ...)` memicu Style Invalidation dan Recalculate Style secara rekursif ke **seluruh node DOM**.
*   **Scoped Theme Variables (`.theme-dark`)**: Membatasi Style Invalidation hanya pada subtree yang memiliki class tersebut.
*   **CSS Var Read Costs**: Pemanggilan `getComputedStyle(element).getPropertyValue('--token-name')` di thread utama memaksa browser melakukan *Synchronous Forced Reflow* jika DOM sedang dalam kondisi dirty.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi custom engine resolusi token sederhana berbasis TypeScript yang melakukan *Cycle Detection* dan *Alias Resolution* tanpa dependensi eksternal.

```typescript
// tokenizer-engine.ts

export interface TokenNode {
  $value: string | number;
  $type: string;
  $description?: string;
}

export type TokenDictionary = {
  [key: string]: TokenNode | TokenDictionary;
};

export class TokenResolver {
  private flatTokens = new Map<string, TokenNode>();
  private graph = new Map<string, string[]>();

  constructor(private rawDictionary: TokenDictionary) {
    this.flattenDictionary(this.rawDictionary);
    this.buildGraph();
  }

  // Meratakan hirarki nested object menjadi dot-notation keys
  private flattenDictionary(dict: TokenDictionary, prefix = ''): void {
    for (const [key, value] of Object.entries(dict)) {
      const fullPath = prefix ? `${prefix}.${key}` : key;
      if (value && typeof value === 'object' && '$value' in value) {
        this.flatTokens.set(fullPath, value as TokenNode);
      } else if (value && typeof value === 'object') {
        this.flattenDictionary(value as TokenDictionary, fullPath);
      }
    }
  }

  // Mengekstrak referensi {path.to.token}
  private extractReferences(value: string | number): string[] {
    if (typeof value !== 'string') return [];
    const regex = /\{([^}]+)\}/g;
    const matches: string[] = [];
    let match;
    while ((match = regex.exec(value)) !== null) {
      matches.push(match[1]);
    }
    return matches;
  }

  // Membangun Adjacency List untuk Topological Sort & Cycle Checking
  private buildGraph(): void {
    for (const [key, node] of this.flatTokens.entries()) {
      const deps = this.extractReferences(node.$value);
      this.graph.set(key, deps);
    }
  }

  // Deteksi siklus menggunakan Three-Color Depth-First Search Algorithm
  public detectCycles(): void {
    const visited = new Map<string, 'WHITE' | 'GRAY' | 'BLACK'>();
    for (const key of this.flatTokens.keys()) {
      visited.set(key, 'WHITE');
    }

    const dfs = (node: string, path: string[]) => {
      visited.set(node, 'GRAY');
      const neighbors = this.graph.get(node) || [];

      for (const neighbor of neighbors) {
        if (!this.flatTokens.has(neighbor)) {
          throw new Error(`Unresolved Reference: Token "${neighbor}" dirujuk oleh "${node}" tapi tidak didefinisikan.`);
        }

        const state = visited.get(neighbor);
        if (state === 'GRAY') {
          throw new Error(
            `Circular Dependency Detected: ${[...path, node, neighbor].join(' -> ')}`
          );
        }
        if (state === 'WHITE') {
          dfs(neighbor, [...path, node]);
        }
      }
      visited.set(node, 'BLACK');
    };

    for (const key of this.flatTokens.keys()) {
      if (visited.get(key) === 'WHITE') {
        dfs(key, []);
      }
    }
  }

  // Resolusi nilai akhir secara rekursif
  public resolveToken(key: string, trace = new Set<string>()): string | number {
    const node = this.flatTokens.get(key);
    if (!node) {
      throw new Error(`Token "${key}" tidak ditemukan.`);
    }

    if (trace.has(key)) {
      throw new Error(`Circular dependency pada runtime: ${key}`);
    }

    trace.add(key);

    let val = String(node.$value);
    const regex = /\{([^}]+)\}/g;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(val)) !== null) {
      const targetKey = match[1];
      const resolvedTarget = this.resolveToken(targetKey, new Set(trace));
      val = val.replace(match[0], String(resolvedTarget));
      regex.lastIndex = 0; // Reset regex pointer pasca-substitusi
    }

    trace.delete(key);
    return isNaN(Number(val)) || val.trim() === '' || val.startsWith('#') ? val : Number(val);
  }

  // Transformasi ke Flat Resolved Dictionary
  public resolveAll(): Record<string, string | number> {
    this.detectCycles();
    const result: Record<string, string | number> = {};
    for (const key of this.flatTokens.keys()) {
      result[key] = this.resolveToken(key);
    }
    return result;
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari `tokenizer-engine.ts`:

1.  **Baris 3–7 (`interface TokenNode`)**:
    Menetapkan skema dasar kompatibel DTCG. Node valid harus memiliki atribut `$value` (data primitif atau string referensi) dan `$type` yang membedakan domain transformasi.
2.  **Baris 20–30 (`flattenDictionary`)**:
    Menangani komputasi rekursif untuk mengubah struktur JSON bersarang (*nested arbitrary depth*) menjadi graf kunci berbasis *dot-notation* (`sys.color.primary`). Pendekatan ini memfasilitasi algoritma lookup berbasis peta hash $O(1)$.
3.  **Baris 33–42 (`extractReferences`)**:
    Menggunakan ekspresi reguler `/\{([^}]+)\}/g` untuk mengekstraksi dependensi internal. Pola ini menangkap semua string yang dibungkus kurung kurawal dalam sintaks deklarasi nilai alias DTCG.
4.  **Baris 45–50 (`buildGraph`)**:
    Mengonstruksi *Adjacency List* di mana setiap node token memetakan langsung ke *array* kunci dependensinya, menyiapkan struktur graf untuk analisis DFS.
5.  **Baris 53–87 (`detectCycles`)**:
    Implementasi algoritma deteksi siklus formal:
    *   `WHITE`: Node belum dievaluasi sama sekali.
    *   `GRAY`: Node sedang berada dalam Call Stack aktif rekursi DFS. Jika DFS menemui tetangga yang berstatus `GRAY`, maka **lingkaran dependensi tak terhingga (cycle) terbukti ada**.
    *   `BLACK`: Node dan seluruh turunannya telah sepenuhnya valid dan bebas siklus.
6.  **Baris 90–115 (`resolveToken`)**:
    Fungsi resolusi evaluatif yang melakukan dereferencing token. Baris `regex.lastIndex = 0;` menjamin bahwa parser regex berbasis flag global tidak melompat melebihi batas indeks saat teks sumber diubah secara mutatif selama substitusi string.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Multi-Brand Multi-Platform FinTech (Mega-App)

**Latar Belakang Perusahaan:**
Sebuah korporasi finansial mengoperasikan dua aplikasi consumer:
1. *Brand A (Retail Core Banking)*: Mengedepankan stabilitas, warna biru korporat (#0047AB), sudut tumpul rendah (*border-radius: 4px*), tipografi padat.
2. *Brand B (Digital Millennial Bank)*: Mengedepankan ekspresi, palet neon violet (#7F00FF), sudut dinamis melengkung (*border-radius: 16px*), rasio spasi lega.

Keduanya menggunakan fondasi komponen yang sama pada Web (React + Tailwind CSS), iOS (SwiftUI), dan Android (Jetpack Compose).

**Masalah:**
Tim engineer sebelumnya melakukan *hardcode* branch logika di setiap komponen:
```tsx
// IMPLEMENTASI ANTI-PATTERN (BURUK)
<button className={brand === 'BrandA' ? 'bg-[#0047AB] rounded-sm' : 'bg-[#7F00FF] rounded-xl'}>
```
Hal ini menyebabkan *tech-debt* besar, kegagalan WCAG AAA pada dark mode Brand B, ukuran biner aplikasi yang membengkak, dan *regression bugs* visual setiap kali desainer mengubah skema warna.

**Solusi Arsitektural:**
Membangun *Headless Token Compiler Pipeline* menggunakan Style Dictionary v4 yang membagi lapisan konfigurasi menjadi skema multi-dimensi:
1. `primitives/`: Token global (semua palet warna dari kedua brand).
2. `brands/{brandA,brandB}/`: Semantic layer yang memetakan nama fungsional (`color.interactive.brand`) ke primitive yang dipilih brand tersebut.
3. `themes/{light,dark}/`: Override layer berbasis luminositas.
Pipeline mengekspor:
*   Web: CSS File terisolasi per-theme dan file ekstensi deklarasi Tailwind CSS.
*   iOS: Swift Singleton terkompilasi dan file `.xcassets`.
*   Android: Kotlin Objects dengan `MaterialTheme` color scheme bindings.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur produksi lengkap menggunakan pipeline konfigurasi Style Dictionary v4 dengan format modern JavaScript/TypeScript ESM:

```javascript
// build-tokens.js
import StyleDictionary from 'style-dictionary';
import { register } from '@tokens-studio/sd-transforms';
import path from 'path';

// Daftarkan transformasi standar industri untuk DTCG & Figma Tokens Studio
register(StyleDictionary);

// 1. Custom Action untuk Generasi Tailwind Theme Mapping JSON
StyleDictionary.registerFormat({
  name: 'tailwind/theme-extension',
  format: async ({ dictionary }) => {
    const theme = {};
    for (const token of dictionary.allTokens) {
      if (token.type === 'color') {
        const pathSegments = token.path;
        let current = theme;
        for (let i = 0; i < pathSegments.length - 1; i++) {
          const seg = pathSegments[i];
          current[seg] = current[seg] || {};
          current = current[seg];
        }
        current[pathSegments[pathSegments.length - 1]] = `var(--${token.name})`;
      }
    }
    return JSON.stringify({ theme: { extend: { colors: theme.color || {} } } }, null, 2);
  },
});

// 2. Custom Swift Formatter untuk iOS SwiftUI
StyleDictionary.registerFormat({
  name: 'ios-swift/design-system',
  format: async ({ dictionary }) => {
    const lines = [
      '// AUTO-GENERATED - JANGAN EDIT MANUAL',
      'import SwiftUI',
      '',
      'public struct AppTokens {',
    ];

    for (const token of dictionary.allTokens) {
      if (token.type === 'color') {
        // Asumsi format token value berupa HEX atau RGB string
        lines.push(`    public static let ${token.name} = Color("${token.name}")`);
      } else if (token.type === 'dimension') {
        const numVal = parseFloat(token.value);
        lines.push(`    public static let ${token.name}: CGFloat = ${isNaN(numVal) ? 0 : numVal}`);
      }
    }

    lines.push('}');
    return lines.join('\n');
  },
});

// 3. Custom Android Compose Formatter
StyleDictionary.registerFormat({
  name: 'compose/object-declaration',
  format: async ({ dictionary }) => {
    const lines = [
      '// AUTO-GENERATED - JANGAN EDIT MANUAL',
      'package com.enterprise.designsystem.tokens',
      '',
      'import androidx.compose.ui.graphics.Color',
      'import androidx.compose.ui.unit.dp',
      'import androidx.compose.ui.unit.Dp',
      '',
      'object AppTokens {'
    ];

    for (const token of dictionary.allTokens) {
      if (token.type === 'color') {
        let hex = token.value.replace('#', '');
        if (hex.length === 6) hex = 'FF' + hex; // Tambah Alpha 100% jika RGB
        lines.push(`    val ${token.name}: Color = Color(0x${hex.toUpperCase()})`);
      } else if (token.type === 'dimension') {
        const val = parseFloat(token.value);
        lines.push(`    val ${token.name}: Dp = ${val}.dp`);
      }
    }

    lines.push('}');
    return lines.join('\n');
  }
});

// Konfigurasi Multi-Platform Pipeline Runner
async function runBuild(brand, theme) {
  console.log(`\nCompiling design tokens for [Brand: ${brand}] - [Theme: ${theme}]...`);

  const sd = new StyleDictionary({
    source: [
      'tokens/primitives/**/*.json',
      `tokens/brands/${brand}/**/*.json`,
      `tokens/themes/${theme}/**/*.json`
    ],
    platforms: {
      css: {
        transformGroup: 'tokens-studio',
        prefix: 'ds',
        buildPath: `build/web/${brand}/`,
        files: [
          {
            destination: `tokens-${theme}.css`,
            format: 'css/variables',
            options: {
              selector: theme === 'dark' ? `[data-theme="${theme}"]` : ':root',
              outputReferences: true
            }
          },
          {
            destination: 'tailwind-tokens.json',
            format: 'tailwind/theme-extension'
          }
        ]
      },
      ios: {
        transformGroup: 'tokens-studio',
        buildPath: `build/ios/${brand}/`,
        transforms: ['attribute/cti', 'name/camel'],
        files: [
          {
            destination: 'DesignTokens.swift',
            format: 'ios-swift/design-system'
          }
        ]
      },
      android: {
        transformGroup: 'tokens-studio',
        buildPath: `build/android/${brand}/`,
        transforms: ['attribute/cti', 'name/camel'],
        files: [
          {
            destination: 'AppTokens.kt',
            format: 'compose/object-declaration'
          }
        ]
      }
    }
  });

  await sd.buildAllPlatforms();
}

// Simulasi Pipeline Eksekusi
async function main() {
  const brands = ['brandA', 'brandB'];
  const themes = ['light', 'dark'];

  for (const b of brands) {
    for (const t of themes) {
      await runBuild(b, t);
    }
  }
  console.log('\nToken build complete across all targets.');
}

main().catch(console.error);
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Static CSS Bundles (CSS Modules / Sass) | Runtime Token Injection (`document.style.setProperty`) | Build-Time Compilation (Style Dictionary DTCG) | CSS-in-JS Engine (e.g., Emotion / Styled Components) |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime Performance** | **Optimal** (Terkompilasi statis; peramban mengoptimasi parser CSS). | **Rendah** (Memicu full DOM style invalidation & layout thrashing). | **Sangat Optimal** (Menghasilkan CSS vars natif & static typed types). | **Sedang/Rendah** (CSS serialization di JavaScript execution thread). |
| **Dukungan Multi-Platform**| Tidak ada (Hanya ekosistem Web). | Tidak ada (Hanya Web DOM API). | **Sangat Tinggi** (Web, iOS, Android, Flutter dari JSON tunggal). | Rendah (Web dan React Native via adapter rapuh). |
| **Bundle Size Overhead** | Menengah (Banyak duplikasi styling jika per-brand dibuat file terpisah). | Minimal (Hanya satu payload JSON yang diinjeksikan). | Minimal (Hanya variabel terpakai via tree shaking TS & CSS terisolasi).| Tinggi (Runtime library parser disematkan ke dalam JS bundle). |
| **Type Safety & DX** | Lemah (Rentang typo kelas string CSS). | Sangat Buruk (Key-value loose string casting). | **Kuat** (Dihasilkan `.d.ts`, Swift structs, dan Kotlin val bindings). | Sangat Kuat (Autocompletion native via TypeScript types). |
| **Fleksibilitas Theming** | Rendah (Sulit dinamis on-the-fly tanpa reload stylesheet). | Sangat Tinggi (Bebas ubah warna per instan pada runtime). | Tinggi (Beralih instan melalui manipulasi atribut `data-theme`). | Sangat Tinggi (Berdasarkan evaluasi React Context). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Font Metrics Normalization across OS Engines
*   **Edge Case:** Nilai token ukuran teks `font-size: 16px` dan `line-height: 24px` menghasilkan tinggi elemen fisik yang berbeda di iOS CoreText vs. Android HarfBuzz vs. Browser Blink karena metrik font internal (*cap-height*, *ascender*, *descender*).
*   **Mitigasi:** Standarisasi token tipografi untuk menyertakan rasio koreksi *leading-trim* / *text-box-trim* (CSS level 4) atau sediakan platform-specific line-height offset langsung pada transform step pipeline.

### 2. High-Frequency Theming Updates & Recalculate Styles
*   **Edge Case:** Mengubah nilai token CSS variables pada elemen ancestor tingkat tinggi (`:root` atau `body`) secara berkelanjutan (misalnya mengikat token warna latar ke nilai *scroll progress* atau pergerakan kursor mouse) akan menurunkan frame-rate animasi di bawah 30fps.
*   **Mitigasi:** Pisahkan token statis dari token interaktif dinamis. Gunakan CSS Custom Property yang di-scope eksklusif pada elemen target lokal atau tangani interaksi performa tinggi melalui Canvas/WebGL dan transform property hardware-accelerated (`translate3d`).

### 3. Alpha Transparency Compounding (Sub-Pixel Blending Drift)
*   **Edge Case:** Penggunaan token warna transparan bersarang (`rgba(0,0,0, 0.1)`) yang dirujuk oleh beberapa layer semantik menyebabkan nilai akumulatif alpha berbeda di Web (CSS layer blending) dibanding iOS (sRGB linear blending pada CoreGraphics).
*   **Mitigasi:** Larang penumpukan (*layering*) token warna transparan untuk elemen fungsional. Wajibkan semantic surface token dievaluasi sebagai solid Oklch atau Hex nilai absolut melalui algoritma pre-blending saat proses build time jika latar belakang sudah dapat diprediksi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memberi Nama Semantik dengan Nilai Primitif Fisik
*   *Kesalahan*: Membuat token semantik bernama `--color-text-red: {color.palette.red.500}`.
*   *Dampak*: Ketika sistem membutuhkan varian tema di mana teks peringatan tersebut harus diubah menjadi kuning atau putih untuk mode kontras tinggi, penamaan `--color-text-red` menjadi paradoks.
*   *Perbaikan*: Gunakan penamaan berbasis fungsi dan peruntukan: `--color-text-critical`, `--color-text-warning`, `--color-text-neutral`.

### 2. Menghubungkan Komponen Langsung ke Primitive Tokens
*   *Kesalahan*: `Button.tsx` mengimpor `tokens.palette.blue.600`.
*   *Dampak*: Melewati Semantic Layer menghilangkan skalabilitas theming. Mengubah warna brand blue secara global merusak tombol tanpa disengaja di seluruh aplikasi.
*   *Perbaikan*: Komponen **hanya boleh** mengonsumsi Semantic Tokens (`tokens.surface.action.primary.default`) atau Component-Scoped Tokens (`tokens.button.solid.background.default`).

### 3. Mengabaikan Unit Em/Rem vs Px pada Konversi Multi-Platform
*   *Kesalahan*: Mengompilasi nilai `16px` langsung ke integer `16` tanpa mempertimbangkan aksesibilitas Android (*sp*) dan Web (*rem*).
*   *Dampak*: Pengguna dengan pengaturan *Accessibility Large Text* pada peramban web atau OS Android tidak mengalami pembesaran font, melanggar kriteria WCAG 1.4.4 (Resize Text).
*   *Perbaikan*: Pipeline harus menyediakan transformator berbasis target:
    *   Web: `val_px / 16 = X rem`
    *   Android: `val_px` dikonversi menjadi unit `sp` untuk font dan `dp` untuk dimension.
    *   iOS: `val_px` diskalakan menggunakan `UIFontMetrics.default.scaledFont`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

*   **Format Penamaan Token (CTI Convention):** Terapkan taksonomi *Category-Type-Item-SubItem-State*:
    `color-background-button-primary-hover`
    *   `Category`: `color`
    *   `Type`: `background`
    *   `Item`: `button`
    *   `SubItem`: `primary`
    *   `State`: `hover`
*   **Single Source of Truth (SSOT) via Git Version Control:** Jangan biarkan Figma menjadi storage engine utama data token. Simpan JSON DTCG murni dalam Git repository. Gunakan automated pull-request pipeline ketika desainer melakukan sync dari plugin Tokens Studio.
*   **SemVer untuk Perubahan Token:**
    *   *PATCH*: Mengubah nilai heksadesimal warna semantik tanpa mengubah kontrak nama atau struktur graf (misal: `#0047AB` -> `#0047AC` untuk optimasi WCAG).
    *   *MINOR*: Menambah token baru yang kompatibel secara mundur.
    *   *MAJOR*: Menghapus token lama, mengganti nama hierarki path token, atau memodifikasi fallback type (misal: dari `color` ke `gradient`).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Eliminasi Redundansi Melalui CSS Variable Inheritance Engine
Jangan mencetak ulang variabel tema gelap secara penuh jika sebagian besar bernilai sama. Konfigurasi kompilasi CSS hanya boleh menghasilkan delta (perbedaan) antara base theme dan alternate theme:

```css
/* Base Theme (Light) - Dihasilkan Lengkap: 1,200 Baris */
:root {
  --ds-color-bg-app: #ffffff;
  --ds-color-text-main: #111827;
  --ds-color-