# Kurikulum Enterprise: Design System Engineering

## Kategori: 03-Frontend-and-Mobile
## Bab 08: Documentation Engineering dan Developer Experience (DX)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Senior/Staff Engineer diharapkan mampu:

1. **Membangun Metadata Extraction Engine**: Mengembangkan pipeline ekstraksi Abstract Syntax Tree (AST) berbasis TypeScript Compiler API untuk mengekstrak definisi tipe, JSDoc metadata, component props, dan design token metadata secara nir-deviasi (*zero-drift*).
2. **Merancang Dynamic In-Browser Sandbox Architecture**: Mengimplementasikan arsitektur *isolated runtime execution* berbasis virtual file system (VFS) dan `<iframe>` *postMessage* protocol (atau Web Workers) yang mengeksekusi kode komponen secara dinamis tanpa mengorbankan performa *main thread* atau keamanan dokumentasi utama.
3. **Mengotomatisasi Zero-Drift CI/CD Verification**: Membangun mekanisme verifikasi dokumen di dalam continuous integration (CI) untuk menguji keabsahan contoh kode (*type-checking executable code blocks* dalam markdown/MDX) dan mendeteksi perubahan API yang memecah kompatibilitas (*breaking changes*) pada level komponen.
4. **Mengintegrasikan Contextual DX & Multi-Brand Dynamic Previews**: Menyediakan sistem dokumentasi dengan kontrol varian reaktif (props matrix playground), *live telemetry feedback*, serta *token-swapping* antar-brand dengan waktu render sub-100 milidetik.

---

### 2. Prerequisite

Peserta didik wajib menguasai kompetensi tingkat lanjut berikut:
* **TypeScript Metaprogramming & Compiler API**: Pemahaman mendalam tentang `ts.createProgram`, `ts.TypeChecker`, `ts.Symbol`, traversal AST via `ts.forEachChild`, dan resolusi tipe kondisional/generik.
* **Component Architecture & Runtime Internals**: Siklus hidup React (v18/v19 concurrent features), virtual DOM lifecycle, dynamically imported modules (`React.lazy`, dynamic `import()`), dan Error Boundaries.
* **Web Security Contexts**: Cross-Origin Resource Sharing (CORS), Content Security Policy (CSP), `sandbox` attribute flags pada `<iframe>`, serta mitigasi eksekusi kode arbitrer (XSS).
* **Modern Build Toolchains**: Arsitektur internal Vite, Rollup plugins, SWC/Babel transformations, dan Virtual File System (VFS) abstractions.

---

### 3. Concept & Internal Architecture

Dokumentasi design system enterprise bukan sekadar situs web statis berbasis Markdown, melainkan platform perangkat lunak terintegrasi yang berfungsi sebagai *single source of truth* bagi desainer, teknisi, dan produk. 

```
                                  ARSIKTEKTUR ZERO-DRIFT DOC ENGINE
                                  
  [ Design Tokens ]     [ UI Components (TSX) ]     [ MDX Spec & Guides ]
         │                        │                           │
         ▼                        ▼                           ▼
┌──────────────────┐    ┌────────────────────┐     ┌──────────────────────┐
│ Token Parser API │    │ TS Compiler API    │     │ Unified / Remark AST │
│ (Style Dictionary│    │ (AST Type Checker  │     │ (Code block parser & │
│  Metadata Extr.) │    │  & JSDoc Extractor)│     │  validation engine)  │
└────────┬─────────┘    └─────────┬──────────┘     └──────────┬───────────┘
         │                        │                           │
         └────────────────┐       │      ┌────────────────────┘
                          ▼       ▼      ▼
                ┌───────────────────────────────────┐
                │ Component Metadata Manifest (JSON)│
                └─────────────────┬─────────────────┘
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │ Production Doc Engine (Next/Astro)│
                │ ├─ Static Content Pre-rendering   │
                │ ├─ Algolia DocSearch Indexer      │
                │ └─ Zero-Drift Type-Check Verifier │
                └─────────────────┬─────────────────┘
                                  │ (Embeds Isolated Sandbox)
                                  ▼
                ┌───────────────────────────────────┐
                │ In-Browser Virtual Sandbox Engine │
                │ ├─ Sandpack / WebContainer Worker │
                │ ├─ Dynamic Bundler (ESBuild WASM) │
                │ └─ Cross-Frame RPC (postMessage)  │
                └───────────────────────────────────┘
```

#### A. The AST Extraction Pipeline
Pendekatan konvensional yang mengandalkan penulisan dokumentasi manual untuk props dan types selalu berakhir dengan inkonsistensi (*documentation drift*). Arsitektur modern mengekstrak metadata langsung dari source code menggunakan TypeScript Compiler API.
1. **Source Loading**: Engine memuat source code dan membentuk file graph menggunakan konfigurasi `tsconfig.json`.
2. **Type Checking & Resolution**: Menggunakan `ts.TypeChecker` untuk mengevaluasi tipe turunan (misal: `Pick<ButtonProps, 'variant'>`, discriminated unions, kompleks generic templates).
3. **Symbol Table Traversal**: Memetakan setiap antarmuka publik komponen, membedakan props internal vs. props publik via tag JSDoc (`@internal`, `@deprecated`, `@alpha`).
4. **Manifest Generation**: Data serial diubah menjadi schema JSON deterministik (JSON Schema/OpenAPI spec untuk UI) yang dikonsumsi oleh UI renderer.

#### B. Dynamic Sandbox & Isolation Engine
Menjalankan kode contoh interaktif pengguna secara langsung di window utama dokumentasi membawa risiko:
* **Style Leakage**: CSS global dari contoh kode dapat merusak layout dokumentasi (dan sebaliknya).
* **State Pollution**: Mutasi window globals, history API, atau event listener liar akan mengotori runtime dokumen.
* **Security & Crash Propagation**: Infinite loops, unhandled rejections, atau eksekusi kode berbahaya dapat melumpuhkan keseluruhan antarmuka.

Arsitektur produksi mengisolasi execution context ke dalam sandboxed `<iframe>` dengan atribut ketat (`sandbox="allow-scripts allow-same-origin"` jika dibutuhkan isolated domain) atau menggunakan browser worker thread dengan WebAssembly-based bundler (seperti ESBuild WASM) yang disalurkan melalui Virtual File System (VFS).

#### C. Zero-Drift CI Gating
Dokumentasi harus diperlakukan setara dengan *unit tests*. Dokumentasi dinyatakan *broken* jika kode di dalam Markdown/MDX:
1. Gagal melewati `tsc` verification.
2. Menggunakan komponen/props yang sudah didegradasi (*deprecated*) tanpa anotasi yang sesuai.
3. Menghasilkan visual error saat di-*mount*.

---

### 4. Why & What

| Fitur / Karakteristik | Static Documentation (Docusaurus/Basic Storybook) | Enterprise Doc Platform (Engineered Platform) |
| :--- | :--- | :--- |
| **Pembaruan Tipe Props** | Manual atau semi-otomatis saat build statis sederhana. | Ekstraksi AST real-time atau via pipeline manifest; zero-drift. |
| **Eksekusi Kode** | Live preview terbatas; rentan tabrakan CSS/DOM. | Web Worker + Sandboxed Virtual Bundler berbasis WASM. |
| **Multi-Brand Theming** | Terbatas pada stylesheet global swapping; sering lag. | Dynamic CSS Variable re-scoping dan real-time AST token injection. |
| **Validasi Snippet** | Kode di MDX sering kali tidak diuji (sering rusak). | Snippet diekstraksi ke *virtual test suite* dan divalidasi di CI. |
| **Skalabilitas Kontributor** | Rentan human error saat ada ratusan developer. | Kontrak tipe eksplisit; CI menggagalkan PR jika doc tidak valid. |

---

### 5. How (Workflow Detail)

Alur kerja (end-to-end) integrasi dokumentasi enterprise:

```
[ Git Push / PR Opened ]
           │
           ▼
[ Step 1: CI Pipeline Triggered ]
           │
           ├─► [ AST Extractor CLI ]
           │        │ Mengekstrak Props, Types, & JSDoc tags
           │        ▼
           │   Generates: `metadata.json`
           │
           ├─► [ MDX Code Block Type-Checker ]
           │        │ Mengekstrak semua ```tsx blocks dari docs
           │        │ Mengonversi ke Virtual TS Files dengan virtual imports
           │        ▼
           │   Menjalankan: `tsc --noEmit` pada snippets
           │
           └─► [ Breaking Change Detector ]
                    │ Membandingkan `metadata.json` lama vs baru
                    ▼
               Mendeteksi props yang hilang / tipe yang berubah secara breaking
           │
           ▼
[ Step 2: Build Documentation Application ]
           │
           ├─► Menginjeksi `metadata.json` ke SSR Engine (Next.js/Astro)
           ├─► Melakukan kompilasi MDX via unified/remark pipeline
           └─► Membangun static assets + runtime dynamic client bundle
           │
           ▼
[ Step 3: Deploy & Telemetry Sync ]
           │
           ├─► Deploy Preview Environment (Vercel/Cloudflare Pages/AWS)
           └─► Push metadata ke Algolia DocSearch & internal DX portal
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem dokumentasi konvensional seperti **buku panduan manual perakitan mobil yang dicetak secara konvensional**. Jika insinyur pabrik mengubah ukuran baut dari 10mm ke 12mm pada lini produksi, buku manual tersebut langsung usang kecuali seseorang mengingat untuk mencetak ulang manual tersebut.

Enterprise Documentation Engineering bekerja seperti **simulator hologram interaktif yang terhubung langsung secara telemetris ke cetak biru CAD (Computer-Aided Design)**. Ketika blueprint diubah di sistem pusat, model hologram, simulasi kekuatan mekanik baut, dan parameter interaktifnya langsung terbarui seketika. Jika ada komponen baru yang tidak pas dengan bagian yang lama, sistem simulasi langsung memicu alarm bahaya di pabrik secara otomatis.

#### Sandbox Cross-Frame Communication Architecture

```
┌────────────────────────────────────────────────────────┐
│ Host Documentation Window (Parent)                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ MDX Documentation Page Content                   │  │
│  │                                                  │  │
│  │ ┌──────────────────────────────────────────────┐ │  │
│  │ │ Live Code Editor (Monaco / CodeMirror)       │ │  │
│  │ └──────────────────────┬───────────────────────┘ │  │
│  │                        │ Code Change Event       │  │
│  │                        ▼                         │  │
│  │ ┌──────────────────────────────────────────────┐ │  │
│  │ │ Dynamic Props Control Matrix (React State)   │ │  │
│  │ └──────────────────────┬───────────────────────┘ │  │
│  └────────────────────────┼─────────────────────────┘  │
│                           │                             │
│                           │ postMessage({               │
│                           │   type: 'COMPILE_AND_MOUNT',│
│                           │   code: '...',              │
│                           │   props: { ... }            │
│                           │ })                          │
│                           ▼                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Sandboxed <iframe> (isolated-preview.domain.tld)  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ Message Listener (RPC Manager)              │  │  │
│  │  │  │                                          │  │  │
│  │  │  ▼                                          │  │  │
│  │  │ [ESBuild WASM / QuickJS / In-Memory Bundle] │  │  │
│  │  │  │                                          │  │  │
│  │  │  ▼                                          │  │  │
│  │  │ Virtual DOM Mountpoint                      │  │  │
│  │  │  └─► <ErrorBoundary>                        │  │  │
│  │  │        └─► <EvaluatedComponent {...props} />│  │  │
│  │  │      </ErrorBoundary>                       │  │  │
│  │  │                                             │  │  │
│  │  │ Runtime Errors / Telemetry                  │  │  │
│  │  └─────────────────────┬───────────────────────┘  │  │
│  │                        │                             │
│  └────────────────────────┼─────────────────────────────┘
│                           │ postMessage({
│                           │   type: 'RUNTIME_REPORT',
│                           │   status: 'ERROR' | 'SUCCESS'
│                           │ })
│                           ▼
│  ┌───────────────────────────────────────────────────┐
│  │ Parent Error Reporter / Profiler Panel            │
│  └───────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Ekstraksi AST Programatik Sederhana dengan TS Compiler API
Skrip Node.js ini mem-parsing file TypeScript, membaca antarmuka `ButtonProps`, dan mencetak props beserta metadata tipe dan dokumentasi JSDoc-nya.

```typescript
// scripts/extract-simple-props.ts
import * as ts from 'typescript';
import * as path from 'path';

function getComponentProps(filePath: string, targetInterface: string) {
  const program = ts.createProgram([filePath], {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
  });

  const checker = program.getTypeChecker();
  const sourceFile = program.getSourceFile(filePath);

  if (!sourceFile) {
    throw new Error(`File tidak ditemukan: ${filePath}`);
  }

  const propsMetadata: Record<string, { type: string; documentation: string; optional: boolean }> = {};

  function visit(node: ts.Node) {
    if (ts.isInterfaceDeclaration(node) && node.name.text === targetInterface) {
      const type = checker.getTypeAtLocation(node);
      const properties = type.getProperties();

      for (const prop of properties) {
        const propType = checker.getTypeOfSymbolAtLocation(prop, node);
        const propName = prop.getName();
        const docComment = ts.displayPartsToString(prop.getDocumentationComment(checker));
        const isOptional = (prop.flags & ts.SymbolFlags.Optional) !== 0;

        propsMetadata[propName] = {
          type: checker.typeToString(propType),
          documentation: docComment,
          optional: isOptional,
        };
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return propsMetadata;
}

// Dummy run (asumsi file Button.tsx ada)
// console.log(JSON.stringify(getComponentProps('./Button.tsx', 'ButtonProps'), null, 2));
```

#### B. Practical Example: Production-Grade AST Extractor & Isolated Live Playground Runtime

##### 1. Production AST Component Inspector (Metadata Generator)
Modul ini mengeksekusi analisis tipe yang lebih dalam, menangani union literals, complex signatures, dan mengekstrak JSDoc tags spesifik (misal: `@default`, `@deprecated`).

```typescript
// infrastructure/ast-engine/ComponentInspector.ts
import * as ts from 'typescript';
import * as fs from 'fs';
import * as path from 'path';

export interface PropDocMeta {
  name: string;
  type: string;
  required: boolean;
  defaultValue?: string;
  description: string;
  deprecated: boolean;
  deprecationReason?: string;
}

export interface ComponentDocManifest {
  componentName: string;
  props: PropDocMeta[];
}

export class ComponentInspector {
  private program: ts.Program;
  private checker: ts.TypeChecker;

  constructor(private rootFiles: string[], private configPath: string) {
    const configFile = ts.readConfigFile(configPath, ts.sys.readFile);
    const parsedCommandLine = ts.parseJsonConfigFileContent(
      configFile.config,
      ts.sys,
      path.dirname(configPath)
    );

    this.program = ts.createProgram({
      rootNames: rootFiles,
      options: parsedCommandLine.options,
    });
    this.checker = this.program.getTypeChecker();
  }

  public inspectComponent(sourceFilePath: string, componentExportName: string): ComponentDocManifest {
    const sourceFile = this.program.getSourceFile(sourceFilePath);
    if (!sourceFile) {
      throw new Error(`Source file tidak ditemukan di compiler context: ${sourceFilePath}`);
    }

    const fileSymbol = this.checker.getSymbolAtLocation(sourceFile);
    let targetComponentSymbol: ts.Symbol | undefined;

    const exports = this.checker.getExportsOfModule(fileSymbol!);
    for (const exp of exports) {
      if (exp.getName() === componentExportName) {
        targetComponentSymbol = exp;
        break;
      }
    }

    if (!targetComponentSymbol) {
      throw new Error(`Export '${componentExportName}' tidak ditemukan pada ${sourceFilePath}`);
    }

    // Resolusi function signature / component declaration
    const componentType = this.checker.getTypeOfSymbolAtLocation(
      targetComponentSymbol,
      targetComponentSymbol.valueDeclaration!
    );

    const callSignatures = componentType.getCallSignatures();
    if (callSignatures.length === 0) {
      throw new Error(`Symbol '${componentExportName}' bukan functional component atau callable element.`);
    }

    const firstSignature = callSignatures[0];
    const propsParameter = firstSignature.parameters[0];

    if (!propsParameter) {
      return { componentName: componentExportName, props: [] };
    }

    const propsType = this.checker.getTypeOfSymbolAtLocation(propsParameter, propsParameter.valueDeclaration!);
    const propsList: PropDocMeta[] = [];

    for (const prop of propsType.getProperties()) {
      const propDeclaration = prop.valueDeclaration || (prop.declarations && prop.declarations[0]);
      if (!propDeclaration) continue;

      const propActualType = this.checker.getTypeOfSymbolAtLocation(prop, propDeclaration);
      const isOptional = (prop.flags & ts.SymbolFlags.Optional) !== 0;

      // Extract JSDoc tags
      let defaultValue: string | undefined;
      let deprecated = false;
      let deprecationReason: string | undefined;

      const jsDocTags = prop.getJsDocTags();
      for (const tag of jsDocTags) {
        if (tag.name === 'default') {
          defaultValue = tag.text?.[0]?.text;
        }
        if (tag.name === 'deprecated') {
          deprecated = true;
          deprecationReason = tag.text?.[0]?.text;
        }
      }

      propsList.push({
        name: prop.getName(),
        type: this.checker.typeToString(propActualType, undefined, ts.TypeFormatFlags.NoTruncation),
        required: !isOptional,
        defaultValue,
        description: ts.displayPartsToString(prop.getDocumentationComment(this.checker)),
        deprecated,
        deprecationReason,
      });
    }

    return {
      componentName: componentExportName,
      props: propsList.sort((a, b) => a.name.localeCompare(b.name)),
    };
  }
}
```

##### 2. Isolated Sandboxed Iframe Runtime Bridge
Berikut adalah protokol komunikasi dua arah antara Host Documentation System dan Sandboxed Execution Frame untuk *live rendering* bebas tabrakan.

```typescript
// components/sandbox/SandboxedSandboxRunner.tsx
import React, { useEffect, useRef, useState, useCallback } from 'react';

export interface SandboxMessagePayload {
  type: 'EXECUTE_CODE' | 'THEME_UPDATE' | 'FRAME_READY' | 'EXECUTION_SUCCESS' | 'EXECUTION_ERROR';
  code?: string;
  themeContext?: Record<string, string>;
  error?: string;
}

interface SandboxedPreviewProps {
  code: string;
  themeTokens: Record<string, string>;
  sandboxOrigin: string; // Misal: "https://sandbox.designsystem.enterprise.internal"
}

export const SandboxedPreview: React.FC<SandboxedPreviewProps> = ({
  code,
  themeTokens,
  sandboxOrigin,
}) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isFrameReady, setIsFrameReady] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  // Inbound Message Handler
  useEffect(() => {
    const handleMessage = (event: MessageEvent<SandboxMessagePayload>) => {
      // Keamanan Enterprise: Wajib memverifikasi origin frame
      if (event.origin !== sandboxOrigin) return;

      const { data } = event;
      switch (data.type) {
        case 'FRAME_READY':
          setIsFrameReady(true);
          break;
        case 'EXECUTION_SUCCESS':
          setRuntimeError(null);
          break;
        case 'EXECUTION_ERROR':
          setRuntimeError(data.error || 'Terjadi kesalahan eksekusi runtime.');
          break;
        default:
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [sandboxOrigin]);

  // Outbound Sender: Sync code updates
  const dispatchCodeExecution = useCallback(() => {
    if (!iframeRef.current || !iframeRef.current.contentWindow || !isFrameReady) return;

    const payload: SandboxMessagePayload = {
      type: 'EXECUTE_CODE',
      code,
      themeContext: themeTokens,
    };

    iframeRef.current.contentWindow.postMessage(payload, sandboxOrigin);
  }, [code, themeTokens, sandboxOrigin, isFrameReady]);

  useEffect(() => {
    dispatchCodeExecution();
  }, [dispatchCodeExecution]);

  return (
    <div className="enterprise-sandbox-container" style={{ border: '1px solid #e2e8f0', borderRadius: '8px' }}>
      <div className="sandbox-header" style={{ padding: '8px 12px', background: '#f8fafc', display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '12px', fontWeight: 600 }}>LIVE PREVIEW RUNTIME (SANDBOXED)</span>
        <span style={{ fontSize: '12px', color: isFrameReady ? 'green' : 'orange' }}>
          {isFrameReady ? '● System Ready' : '○ Initializing Worker...'}
        </span>
      </div>

      {runtimeError && (
        <div style={{ background: '#fee2e2', color: '#991b1b', padding: '12px', fontSize: '13px', fontFamily: 'monospace' }}>
          <strong>Runtime Exception:</strong> {runtimeError}
        </div>
      )}

      <iframe
        ref={iframeRef}
        src={`${sandboxOrigin}/runtime-frame.html`}
        sandbox="allow-scripts"
        title="Component Playground Sandbox"
        style={{ width: '100%', height: '400px', border: 'none', background: '#ffffff' }}
      />
    </div>
  );
};
```

##### 3. Script Inside Sandboxed Frame (`runtime-frame.html`)
Script yang dijalankan di domain sandbox yang terisolasi. Mengompilasi dan me-mount React code secara real-time.

```html
<!-- public/runtime-frame.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <style id="theme-injector"></style>
</head>
<body style="margin: 0; padding: 16px; font-family: sans-serif;">
  <div id="root"></div>

  <script>
    const PARENT_ORIGIN = "https://docs.designsystem.enterprise.internal";
    const rootElement = document.getElementById('root');
    const reactRoot = ReactDOM.createRoot(rootElement);

    function reportParent(type, error = null) {
      window.parent.postMessage({ type, error }, PARENT_ORIGIN);
    }

    window.addEventListener('message', (event) => {
      // Validasi Origin
      if (event.origin !== PARENT_ORIGIN) return;

      const { type, code, themeContext } = event.data;

      if (type === 'EXECUTE_CODE') {
        try {
          // Update Theme Injection Variables
          if (themeContext) {
            const styleTag = document.getElementById('theme-injector');
            const cssVars = Object.entries(themeContext)
              .map(([k, v]) => `${k}: ${v};`)
              .join(' ');
            styleTag.innerHTML = `:root { ${cssVars} }`;
          }

          // Transpile JSX ke executable vanilla JavaScript via Babel Standalone
          const transpiledCode = Babel.transform(code, {
            presets: ['react'],
            filename: 'playground.tsx',
          }).code;

          // Scope execution di dalam dynamic function wrapper
          // Menyuntikkan runtime React & Design System globals
          const executeComponent = new Function('React', 'exports', transpiledCode);
          const moduleExports = {};
          
          executeComponent(React, moduleExports);

          const ComponentToRender = moduleExports.default || moduleExports.App;

          if (!ComponentToRender) {
            throw new Error("Snippet tidak mengekspor 'default' atau 'App' component.");
          }

          // Mount ke root
          reactRoot.render(React.createElement(ComponentToRender));
          reportParent('EXECUTION_SUCCESS');
        } catch (err) {
          reportParent('EXECUTION_ERROR', err.message);
        }
      }
    });

    // Notify Parent bahwa frame siap menerima instruksi
    reportParent('FRAME_READY');
  </script>
</body>
</html>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Masalah
Sebuah Decacorn Fintech SuperApp memiliki **84 UI Feature Squads**, dengan **6 sub-brand** berbeda (Payment, Wealth, P2P Lending, Merchant App, Insurtech, dan Logistik) yang berbagi core library yang sama: `@enterprise-ds/core`.
* **Issue 1 (Drift Disaster)**: 45% implementasi Button, Modal, dan FormField di aplikasi produksi menggunakan props usang atau salah konfigurasi karena dokumentasi tidak diperbarui selama 9 bulan oleh core UI team.
* **Issue 2 (Memory Leak & CI Freeze)**: Build site dokumentasi lama (berbasis static doc engine umum) memakan waktu 48 menit di pipeline CI/CD dan sering *Out of Memory* (OOM) saat memvalidasi 1.200 komponen MDX.
* **Issue 3 (Cross-Brand Breakdown)**: Developer di squad Wealth salah menerapkan styling token squad Payment karena playground dokumentasi tidak dapat menguji dynamic token injection berbasis multi-tenant context.

#### Arsitektur Solusi
1. **Pemisahan Build Pipeline (Two-Tier AST Engine)**:
   * **Stage 1 (Pre-commit / Pre-publish)**: Menjalankan custom `AST Prop Generator CLI` berbasis TypeScript Compiler API. Output berupa `metadata.manifest.json` terkompresi berukuran hanya 1.2 MB.
   * **Stage 2 (Docs Web App)**: Engine dokumentasi berbasis Next.js App Router mengonsumsi `metadata.manifest.json` sebagai data static murni. Halaman props table di-render secara SSR tanpa memanggil TypeScript runtime saat build docs berlangsung.
2. **Zero-Drift CI Gating (`mdx-test-runner`)**:
   Setiap pull request di repositori core design system memicu automated test yang mengekstrak semua kode TypeScript di dalam file `.mdx` menggunakan regex/AST unified, membungkusnya ke dalam memory-virtual project, lalu mengeksekusi `tsc --noEmit`. PR otomatis ditolak jika ada kode di dokumentasi yang menghasilkan error tipe atau menggunakan atribut bertanda `@deprecated`.
3. **Cross-Origin Multi-Brand Isolation Frame**:
   Playground di-hosting di bucket S3/CloudFront terpisah (`preview-sandbox.enterprise.net`), memisahkan cookie, CSP, dan session utama. Dynamic switcher memungkinkan squad berganti variabel CSS token 6 brand secara instan (0 reload time) via postMessage bus.

#### Metrik Keberhasilan (Hasil Pasca-Implementasi)
* **Build Time**: Turun dari **48 menit** menjadi **3 menit 12 detik** (efisiensi 93%).
* **Documentation Drift**: **0%** reported API drift dalam 12 bulan berturut-turut.
* **Dev Adoption & Broken PRs**: Deteksi otomatis 118 *breaking changes* sebelum dirilis ke staging; menurunkan tiket keluhan internal UI bugs sebesar **67%**.

---

### 9. Trade-offs

Setiap keputusan arsitektur dalam documentation engineering memiliki konsekuensi teknis:

| Desain Arsitektural | Keuntungan (Pros) | Biaya & Batasan (Cons / Trade-offs) |
| :--- | :--- | :--- |
| **In-Browser Babel Transpilation (Client-Side)** | Setup sederhana; tidak memerlukan backend compute; interaktivitas instan tanpa server latency. | Beban memori browser besar (Babel standalone ~2-4MB); execution speed lebih lambat dibanding compiled WASM; baterai mobile cepat habis. |
| **WASM-Based Virtual File System (WebContainers / ESBuild WASM)** | Mendukung dependensi NPM utuh; hot-module replacement (HMR) nyata di dalam browser. | Membutuhkan shared cross-origin isolation headers (`COOP`/`COEP`); rendering gagal di embedded webview aplikasi native jika header tidak terpenuhi. |
| **Strict Sandboxed Iframe (Domain Terpisah)** | Isolasi keamanan maksimal; CSS leak prevention mutlak; zero contamination dari runtime host. | Overhead serialization `postMessage`; DOM elements tidak bisa di-inspect secara menyatu di master devtools; layout synchronization lebih rumit. |
| **Strict CI Zero-Drift MDX Compilation** | Dokumentasi 100% akurat; kode snippet dijamin selalu *copy-pasteable* dan bebas error. | Menambah waktu durasi CI check (+1-3 menit); developer frustrasi jika hanya ingin memperbaiki *typo teks*, namun PR diblokir karena code block usang. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Ekstraksi Tipe Prop yang Terpotong (Type Truncation)
* **Masalah**: Tipe kompleks yang diekstrak oleh TypeScript compiler API keluar sebagai `... 24 more ...` atau `any`.
* **Akar Penyebab**: TS Compiler API membatasi panjang string representasi tipe secara default guna menghindari memory explosion pada rekursi tak berhingga.
* **Solusi**: Pastikan selalu menyertakan `ts.TypeFormatFlags.NoTruncation` saat memanggil method `typeToString`:
  ```typescript
  const typeStr = checker.typeToString(
    propType,
    declarationNode,
    ts.TypeFormatFlags.NoTruncation | ts.TypeFormatFlags.UseFullyQualifiedType
  );
  ```

#### Kesalahan 2: Memory Leak pada PostMessage Event Listeners
* **Masalah**: Setelah bernavigasi bolak-balik di antara 10 halaman komponen di dokumentasi, browser menjadi lambat (*lagging*), dan input lag mencapai >500ms.
* **Akar Penyebab**: Komponen React Host mendaftarkan `window.addEventListener('message', handler)` tanpa memanggil `window.removeEventListener` pada teardown phase (`useEffect cleanup`), menghasilkan ribuan duplicate listener aktif yang memproses event yang sama.
* **Solusi**: Wajib menyediakan fungsi pembersih pada hooks, dan pastikan membatalkan asynchronous RAF/timeouts saat iframe di-*unmount*.

#### Kesalahan 3: Tabrakan CSS Token (Global Pollution di Docs Frame)
* **Masalah**: Dokumentasi menyertakan library eksternal (misal: Tailwind atau Bootstrap) untuk salah satu contoh kasus, namun layout navigasi dokumen ikut berubah rusak.
* **Akar Penyebab**: Mengeksekusi kode komponen di DOM parent window yang sama menggunakan `dangerouslySetInnerHTML` atau dynamic React portals tanpa Shadow DOM atau Iframe isolation.
* **Solusi**: Jangan pernah me-render dynamic client code di document body utama. Bungkus dalam *Shadow DOM root* (`element.attachShadow({ mode: 'open' })`) atau letakkan di dalam sandboxed iframe.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis sistem dokumentasi enterprise ke production:

- [ ] **AST Extraction Determinism**: Pastikan hasil `metadata.manifest.json` selalu deterministik (keys di-sort secara alfabetis) agar tidak memicu git diff palsu.
- [ ] **TSDoc Standards Enforced**: Setiap interface prop komponen wajib memiliki anotasi TSDoc minimal satu baris deskripsi.
- [ ] **Type Gating di CI**: Validasi semua code snippet di dalam Markdown/MDX menggunakan static runner (`tsc --noEmit`) pada pull request pipeline.
- [ ] **CSP Hardening**: Halaman sandboxed runtime iframe disajikan dengan CSP ketat: `default-src 'none'; script-src 'self' 'unsafe-eval' https://unpkg.com; style-src 'self' 'unsafe-inline';`.
- [ ] **Cross-Origin Framing Restrictions**: Master documentation site memiliki header `X-Frame-Options: SAMEORIGIN` untuk mencegah clickjacking, sementara isolated playground memiliki `Content-Security-Policy: frame-ancestors https://docs.yourcompany.com`.
- [ ] **Graceful Degradation Error Boundaries**: Setiap preview block dibungkus oleh React Error Boundary khusus yang menangkap parsing error dan runtime crash tanpa melumpuhkan seluruh halaman doc.
- [ ] **Algolia / Search Metadata Export**: Pipeline ekstraksi mengekspor schema terindeks (component name, props, description, tag) untuk mesin pencari internal tim.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun mini-pipeline ekstraksi AST dan validasi MDX di direktori `hands-on/m02/`.

#### Langkah 1: Setup Proyek & Inisialisasi
Jalankan perintah berikut di terminal Anda:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node glob @types/glob --save-dev
npx tsc --init
```

#### Langkah 2: Buat Dummy Design System Component
Buat file `hands-on/m02/Badge.tsx`:
```tsx
// hands-on/m02/Badge.tsx
import React from 'react';

export interface BadgeProps {
  /** Label teks utama yang ditampilkan di dalam badge */
  label: string;
  /** Varian visual badge sesuai peruntukan fungsional */
  variant?: 'primary' | 'secondary' | 'danger' | 'warning';
  /** Ukuran tinggi dan font dari badge */
  size?: 'sm' | 'md' | 'lg';
  /**
   * Status disable interaktivitas
   * @default false
   */
  disabled?: boolean;
  /**
   * Jangan gunakan prop ini. Akan dihapus di rilis v3.0.
   * @deprecated Gunakan custom icon wrapper
   */
  legacyIcon?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  variant = 'primary',
  size = 'md',
  disabled = false,
}) => {
  return (
    <span className={`badge badge-${variant} badge-${size} ${disabled ? 'disabled' : ''}`}>
      {label}
    </span>
  );
};
```

#### Langkah 3: Implementasikan AST Extractor Script
Buat file `hands-on/m02/extract.ts`:
```typescript
// hands-on/m02/extract.ts
import * as ts from 'typescript';
import * as fs from 'fs';
import * as path from 'path';

function runExtraction() {
  const filePath = path.resolve(__dirname, 'Badge.tsx');
  const program = ts.createProgram([filePath], {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.React,
  });

  const checker = program.getTypeChecker();
  const sourceFile = program.getSourceFile(filePath);

  if (!sourceFile) throw new Error('File tidak ditemukan');

  const output: any = { component: 'Badge', props: [] };

  ts.forEachChild(sourceFile, (node) => {
    if (ts.isInterfaceDeclaration(node) && node.name.text === 'BadgeProps') {
      const type = checker.getTypeAtLocation(node);
      for (const prop of type.getProperties()) {
        const propDeclaration = prop.valueDeclaration || prop.declarations?.[0];
        if (!propDeclaration) continue;

        const propType = checker.getTypeOfSymbolAtLocation(prop, propDeclaration);
        
        let defaultValue;
        let isDeprecated = false;

        for (const tag of prop.getJsDocTags()) {
          if (tag.name === 'default') defaultValue = tag.text?.[0]?.text;
          if (tag.name === 'deprecated') isDeprecated = true;
        }

        output.props.push({
          name: prop.getName(),
          type: checker.typeToString(propType),
          optional: (prop.flags & ts.SymbolFlags.Optional) !== 0,
          description: ts.displayPartsToString(prop.getDocumentationComment(checker)),
          defaultValue,
          isDeprecated,
        });
      }
    }
  });

  fs.writeFileSync(
    path.resolve(__dirname, 'badge.manifest.json'),
    JSON.stringify(output, null, 2)
  );
  console.log('✅ Ekstraksi metadata berhasil: badge.manifest.json dibuat.');
}

runExtraction();
```

#### Langkah 4: Jalankan dan Verifikasi Output
Eksekusi skrip menggunakan `ts-node`:
```bash
npx ts-node extract.ts
cat badge.manifest.json
```
Periksa apakah output JSON memuat representasi akurat dari `label`, `variant`, `disabled` (termasuk tag `@default`), dan `legacyIcon` (termasuk tag `isDeprecated: true`).

---

### 13. Exercise

Kerjakan latihan berikut secara mandiri pada repository lokal Anda:

#### Level Easy
Ubah file `extract.ts` agar dapat mendeteksi apakah suatu komponen diekspor sebagai `export default` atau `named export` (misal: `export const Badge`), kemudian simpan tipe ekspor tersebut ke dalam manifest JSON di bawah atribut `exportType: 'named' | 'default'`.

#### Level Medium
Buat validator command-line interface (CLI) `verify-docs.ts` yang membaca file markdown dummy `Badge.md`:
```markdown
# Badge Doc
Berikut contoh penggunaan yang salah:
```tsx
import { Badge } from './Badge';
<Badge label="Test" variant="ultra-neon-glow" />
```
```
CLI Anda harus mengekstrak blok kode di atas, membuat virtual file TypeScript sementara di memori, memanggil `tsc`, dan mengembalikan exit code `1` (gagal) karena prop value `"ultra-neon-glow"` tidak terdaftar di union types `variant`.

#### Level Hard
Kembangkan custom Vite plugin (`vite-plugin-doc-ast.ts`) yang mencegat import berakhiran `?docmeta` (misal: `import meta from './Badge.tsx?docmeta';`). Plugin ini harus secara otomatis mem-parsing AST target file pada saat kompilasi Vite dan mengembalikan modul JSON murni ke client bundle tanpa mengikutsertakan source code asli komponen ke browser bundle.

---

### 14. Challenge

**Skenario**: Perusahaan Anda sedang membangun platform dokumentasi headless yang mendukung rendering multi-framework (React, Vue 3, dan Svelte) dari satu single source of truth Design System.

**Tantangan Arsitektur**:
1. Buat arsitektur Unified Token & Component AST Collector yang mengekstrak prop definition dari komponen React (`.tsx`), Vue (`.vue` via `@vue/compiler-sfc`), dan Svelte (`.svelte` via `svelte/compiler`).
2. Satukan metadata ketiga framework tersebut ke dalam standard schema universal: `UniversalComponentManifest`.
3. Rancang protokol dynamic sandbox yang dapat menerima *string template* dari framework mana pun, menginstansiasi web worker runtime yang sesuai, dan menyajikan preview interaktif dalam satu single interface sandbox.
4. **Batasan**: Tidak boleh menggunakan backend server untuk kompilasi kode runtime (semua transpilation wajib terjadi di in-browser client context menggunakan WebAssembly atau lightweight evaluators).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa pendekatan scraping Regex mentah tidak direkomendasikan untuk mengekstrak props dan tipe dari file TypeScript?
2. Apa fungsi utama `ts.TypeChecker` dibandingkan hanya membaca node AST secara langsung pada TypeScript Compiler API?
3. Sebutkan risiko keamanan terbesar saat mengeksekusi kode kustom dari pengguna di dalam live component editor dokumentasi!
4. Apa fungsi dari atribut HTML `sandbox="allow-scripts"` pada elemen `<iframe>`?
5. Mengapa tag `@deprecated` pada JSDoc perlu diekstrak ke dalam manifest JSON dokumentasi?

#### B. Pertanyaan Intermediate
6. Bagaimana cara menangani tipe props yang diturunkan dari antarmuka eksternal (misal: `React.HTMLAttributes<HTMLButtonElement>`) agar tidak membanjiri manifest dengan ratusan atribut HTML native?
7. Dalam arsitektur Sandboxed Iframe, mengapa pengiriman payload instance React Element via `postMessage` akan memicu `DataCloneError`?
8. Bagaimana strategi zero-drift documentation memverifikasi kode snippet yang sengaja ditulis untuk menggambarkan skenario error (intentional compile-fail example)?
9. Mengapa arsitektur dokumentasi enterprise memisahkan fase AST extraction ke build/pre-commit time daripada menjalankannya on-the-fly saat user membuka halaman dokumen?
10. Bagaimana cara me-resolve dynamic CSS theme variables di dalam isolated iframe tanpa me-reload iframe tersebut?

#### C. Skenario Kasus Produksi
11. **Skenario Kasus 1**: Pada pull request pembaruan komponen `Select`, seorang engineer mengubah tipe prop `value?: string` menjadi `value?: string | string[]` (untuk mendukung multi-select). Namun, pipeline verifikasi dokumen gagal di CI pada 4 halaman dokumentasi lain yang tidak disentuh oleh PR tersebut. Analisis penyebabnya dan tentukan mitigasinya!
12. **Skenario Kasus 2**: Situs dokumentasi Anda mulai mengalami crash "Out of Memory" di browser pengguna ketika membuka halaman komponen `DataTable` yang memuat live playground dengan 500 baris mock data. Identifikasi akar masalah pada runtime live code evaluator dan rancang solusinya!
13. **Skenario Kasus 3**: Sebuah design system enterprise melayani 3 brand dengan design token yang berbeda. Di dokumentasi, saat pengguna mengubah switcher brand dari "Brand A" ke "Brand B", terjadi visual layout shift dan beberapa komponen mempertahankan warna Brand A selama 2 detik sebelum berganti. Analisis penyebab latency sinkronisasi ini pada arsitektur iframe bridge dan berikan arsitektur perbaikannya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic
1. **Regex Parsing Fragility**: Regex tidak memahami konteks sintaksis, type aliases, nested generic types, namespace re-exports, conditional types, atau komentar yang menonaktifkan kode. AST menjamin keabsahan representasi struktur grammar bahasa.
2. **TypeChecker vs Raw AST**: AST murni hanya merepresentasikan bentuk teks kode (syntax). `ts.TypeChecker` merepresentasikan makna semantik (semantics), menyelesaikan referensi silang antar file, mengevaluasi tipe turunan/union, dan inferensi nilai.
3. **Arbitrary Code Execution (XSS)**: Pengguna (atau penyerang via URL injection) dapat menyisipkan kode berbahaya seperti `window.parent.document.cookie` atau skrip pencurian token autentikasi jika kode dieksekusi tanpa isolasi origin.
4. **Iframe Isolation**: Mengizinkan eksekusi JavaScript di dalam frame tetapi memblokir akses ke popups, modals, top-navigation, dan memperlakukan frame sebagai strictly distinct unique origin (kecuali jika flag `allow-same-origin` disertakan).
5. **Developer Guidance & Gating**: Agar UI dokumentasi dapat memberikan visual warning badge (pemberitahuan degradasi) dan CI pipeline dapat mendeteksi serta memperingatkan jika komponen usang masih digunakan pada contoh kode baru.

#### Jawaban Intermediate
6. **Filtering Heritage Clauses**: Gunakan filter simbolik AST. Periksa apakah simbol deklarasi berasal dari file di dalam `node_modules/@types/react`. Jika ya, kelompokkan props tersebut ke dalam accordion terpisah bernama "Standard HTML Attributes" atau abaikan dari tabel props utama.
7. **Structured Clone Algorithm Limitation**: Method `window.postMessage` menggunakan algoritma *Structured Clone*, yang tidak dapat mengkloning fungsi, closures, atau circular DOM references yang terkandung di dalam virtual node React (seperti `$$typeof: Symbol(react.element)`). Solusinya: Kirimkan kode dalam bentuk *string murni*, lalu parse dan mount di dalam konteks iframe target.
8. **Annotation Flags / Codeblock Meta**: Tambahkan directive khusus pada markdown code block, misalnya ````tsx compile-error=TS2322````. Runner CI akan memeriksa apakah `tsc` memang menghasilkan error code `TS2322`. Jika kode berhasil di-compile tanpa error tersebut, build justru digagalkan.
9. **Performance & Scalability**: TypeScript Compiler API memiliki startup cost tinggi (membaca puluhan ribu baris types definisi DOM dan React). Menjalankan compiler di browser client akan menambah bundle size sebesar >10MB dan waktu muat >5 detik.
10. **Dynamic Stylesheet Injection via PostMessage**: Iframe menyediakan listener pesan. Ketika host mengirimkan message `THEME_UPDATE` beserta payload token JSON, iframe memperbarui isi tag `<style id="theme-root">` secara langsung dengan variabel CSS baru tanpa merusak DOM tree yang sudah di-mount.

#### Panduan Kasus Produksi
11. **Analisis Skenario 1**:
    * *Penyebab*: Halaman dokumentasi lain memuat custom snippet yang mengasumsikan `value` selalu berupa `string` (misal memanggil `.toLowerCase()` langsung tanpa runtime type guard `Array.isArray(value)`). Saat tipe diubah menjadi union `string | string[]`, compiler mendeteksi potensi runtime exception pada snippet di halaman lain tersebut.
    * *Mitigasi*: Perbaiki snippet di dokumentasi terkait dengan menambahkan type narrowing (`typeof value === 'string' ? value.toLowerCase() : ...`), atau perbarui type definition komponen agar backwards-compatible jika breaking change tersebut tidak disengaja.
12. **Analisis Skenario 2**:
    * *Penyebab*: Editor live preview melakukan re-render dan re-evaluasi skrip di setiap keystroke tanpa debounce/cleanup, memicu memory leak di mana ribuan instance DOM table virtual tertahan di memori browser tanpa dibersihkan oleh Garbage Collector.
    * *Solusi*: Terapkan *debounce* minimal 300-500ms pada editor input, panggil `root.unmount()` sebelum me-mount evaluasi kode baru di target container, dan batasi ukuran dataset mock di live code preview dengan menyediakan virtualized list wrapper.
13. **Analisis Skenario 3**:
    * *Penyebab*: Terjadi *race condition* dan *blocking paint*. Host doc site mengirimkan perubahan tema secara asynchronous via postMessage, tetapi CSS file brand baru dimuat via dynamic `<link rel="stylesheet">` dari remote CDN di dalam iframe yang memakan waktu network latency (2 detik), sementara JavaScript komponen sudah ter-render ulang duluan.
    * *Perbaikan Arsitektur*: Konversi seluruh token brand menjadi CSS variables yang disuntikkan secara *inlined* di memory frame (zero network request). Host window mengirimkan raw CSS variable dictionary, dan iframe mengaplikasikannya serentak via `document.documentElement.style.setProperty()` dalam satu synchronous animation frame (`requestAnimationFrame`).

---

### 16. Summary

1. **Automated Documentation Engineering**: Dokumentasi tingkat enterprise mengeliminasi *human maintenance error* dengan menggunakan TypeScript Compiler API untuk mengekstrak definisi antarmuka secara programatik.
2. **Runtime Isolation is Mandatory**: Mengeksekusi kode komponen interaktif memerlukan pemisahan konteks yang ketat (menggunakan isolated `<iframe>`, worker sandboxes, atau VFS) untuk menjamin keamanan dari XSS, integritas CSS, dan stabilitas runtime platform dokumen.
3. **Zero-Drift CI Gating**: Memperlakukan blok kode dokumentasi sebagai artefak yang dapat diuji (*testable artifacts*) mencegah regresi API dan memastikan bahwa setiap contoh kode yang disajikan kepada engineer selalu valid dan dapat dieksekusi.
4. **Architectural Decoupling**: Memisahkan ekstraksi AST berat ke fase build/CI dan menyajikan static metadata manifest ke frontend dokumentasi menghasilkan performa rendering sub-detik pada skala ribuan komponen.