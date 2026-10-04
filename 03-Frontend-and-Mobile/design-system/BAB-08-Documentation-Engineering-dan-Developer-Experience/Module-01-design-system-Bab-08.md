# Bab 08 Module 01: Documentation Engineering & Developer Experience (DX)

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend and Mobile Software Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Track:** Design System Engineering
*   **Kode Modul:** DS-ENG-08-01
*   **Judul:** Documentation Engineering & Developer Experience (DX)
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** TypeScript Compiler API, AST (Abstract Syntax Tree) Manipulation, MDX Compilation Engine, Web Component / React Architecture, CI/CD Pipeline Design.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1.  Membangun sistem dokumentasi otomatis berbasis Abstract Syntax Tree (AST) untuk mengekstrak definisi antarmuka komponen, token, dan metadata tanpa redundansi manual.
2.  Merancang dan mengimplementasikan Interactive Live Playgrounds yang aman, terisolasi, dan berkinerja tinggi menggunakan sandboxing berbasis Web Workers dan iframe terisolasi.
3.  Menghubungkan alur sinkronisasi dua arah antara Figma Tokens API dan repositori kode untuk validasi dokumentasi otomatis dalam pipeline CI/CD.
4.  Mengembangkan Custom ESLint Plugins dan AST Codemods untuk memandu adopsi design system secara real-time di lingkungan IDE engineer konsumen.
5.  Mengukur dan mengoptimalkan metrik Developer Experience (DX) menggunakan instrumentasi telemetri terdistribusi (Search Latency, Time to First Render playground, Documentation Drift Rate).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dokumentasi dalam Design System bukanlah arsip teks statis yang ditulis setelah kode selesai; dokumentasi adalah produk perangkat lunak itu sendiri (*Documentation as Code & Infrastructure*). 

```
Mental Model Tradisional (Rentan Drift):
[Kode Komponen] ----(Salin Manual)----> [Dokumentasi Markdown] ----(Desinkronisasi)----> [Frustrasi Konsumen]

Mental Model Documentation Engineering:
                    ┌─────────────────────────┐
                    │ Sumber Kebenaran Tunggal │
                    │ (TypeScript Source AST) │
                    └────────────┬────────────┘
                                 │
                     [AST Extraction Pipeline]
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌─────────────────┐                             ┌─────────────────┐
│ Machine-Readable│                             │   IDE Tooling   │
│ Component Spec  │                             │ (LSP, Codemods) │
└────────┬────────┘                             └─────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Dynamic Interactive Doc Engine  │
│ (Live Sandboxed Run-time Exec)  │
└─────────────────────────────────┘
```

1.  **Zero-Drift Principle:** Dokumentasi yang membutuhkan intervensi manual untuk menyinkronkan perubahan API adalah dokumentasi yang gagal secara desain. API tables, properti, dan tipe data harus di-generate langsung dari source code melalui AST parser.
2.  **Living Artifact:** Dokumentasi harus dapat dieksekusi (*executable*). Jika sebuah contoh kode tidak dapat dikompilasi atau dijalankan dalam isolasi playground, contoh tersebut dianggap rusak (*broken build*).
3.  **Proactive DX:** Developer experience terbaik meminimalkan context switching. Jika developer harus meninggalkan IDE untuk membaca dokumentasi web, design system memiliki friksi. Dokumentasi harus hadir di dalam editor melalui TypeScript Language Server, hovering docs, inline diagnostics, dan lint-rules dengan autofix.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur Documentation Engineering berskala enterprise memproses *source code* komponen, mengekstrak representasi terstruktur, memvalidasi terhadap design tokens, dan menyajikannya ke platform dokumentasi interaktif.

```
+--------------------------------------------------------------------------------------------------+
|                                CI/CD & BUILD-TIME PIPELINE                                       |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +-----------------------+         +-------------------------+      +-----------------------+   |
|   |   Component Source    |         |   Figma Design Tokens   |      |    MDX Documentation  |   |
|   |  (*.tsx / *.props.ts) |         |     (REST API / Sync)   |      |       (*.doc.mdx)     |   |
|   +-----------+-----------+         +------------+------------+      +-----------+-----------+   |
|               |                                  |                               |               |
|               v                                  v                               |               |
|   +-----------------------+         +-------------------------+                  |               |
|   | TypeScript Compiler   |         | Token Normalizer Engine |                  |               |
|   |   API (AST Walker)    |         |  (Transform to JSON)    |                  |               |
|   +-----------+-----------+         +------------+------------+                  |               |
|               |                                  |                               |               |
|               +-----------------+   +------------+                               |               |
|                                 |   |                                            |               |
|                                 v   v                                            v               |
|                     +---------------------------+                    +-----------------------+   |
|                     | Unified Component Schema  |                    | MDX AST Processor     |   |
|                     |     (JSON Metadata)       |                    | (Unified / Remark)    |   |
|                     +-------------+-------------+                    +-----------+-----------+   |
|                                   |                                              |               |
+-----------------------------------|----------------------------------------------|---------------+
                                    v                                              v
+--------------------------------------------------------------------------------------------------+
|                                RUNTIME CLIENT-SIDE EXECUTION                                     |
+--------------------------------------------------------------------------------------------------+
|                                   |                                              |               |
|                                   +-----------------------+----------------------+               |
|                                                           |                                      |
|                                                           v                                      |
|                                            +-----------------------------+                       |
|                                            | Docsite Orchestrator Engine |                       |
|                                            +--------------+--------------+                       |
|                                                           |                                      |
|                            +------------------------------+------------------------------+       |
|                            v                                                             v       |
|             +------------------------------+                              +--------------------+ |
|             | Static Rendering Layer       |                              | Sandboxed Playpen  | |
|             | (Props Tables, MDX Layout)   |                              | (Live Code Runner) | |
|             +------------------------------+                              +----------+---------+ |
|                                                                                      |           |
|                                                                                      v           |
|                                                                           +--------------------+ |
|                                                                           | Web Worker Transp. | |
|                                                                           | (Babel/Sucrase)    | |
|                                                                           +----------+---------+ |
|                                                                                      |           |
|                                                                                      v           |
|                                                                           +--------------------+ |
|                                                                           | Sandboxed iframe   | |
|                                                                           | (CSP: no-same-orig)| |
|                                                                           +--------------------+ |
+--------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. AST Parser & Introspection Engine
Mesin ekstraksi menggunakan `ts-morph` atau Native TypeScript Compiler API (`ts.createProgram`). Alur kerjanya:
- Parsing file `.tsx` menjadi node `SourceFile`.
- Navigasi AST menuju deklarasi exported interface/type props.
- Mengurai JSDoc Tag (`@deprecated`, `@default`, `@param`) dari node trivia.
- Resolusi *type inheritance* (misal: mengekstrak props bawaan dari `React.HTMLAttributes<HTMLButtonElement>`).

### 2. MDX Transpilation Pipeline
MDX mengombinasikan format Markdown dengan JSX. Di balik layar:
- `remark-parse`: Mengonversi MDX string menjadi mdast (Markdown AST).
- `remark-mdx`: Mengidentifikasi syntax ekstensi JSX di dalam mdast.
- `mdast-util-to-hast`: Mengubah mdast menjadi hast (Hypertext AST).
- Eksekusi runtime: Mengonversi hast ke React element tree yang aman melalui komponen custom renderer.

### 3. Isolated Live Playground Engine
Eksekusi runtime interaktif memerlukan mitigasi terhadap serangan cross-site scripting (XSS) dan infinite loops:
- Kode diedit pengguna di browser (menggunakan Monaco Editor atau CodeMirror).
- Web Worker menerima kode mentah, mengompilasinya via Sucrase/Babel-standalone (mengubah JSX/TSX ke ES6 murni).
- Transpiled bundle diinjeksikan ke dalam `<iframe>` dengan atribut `sandbox="allow-scripts"` (meniadakan `allow-same-origin` untuk mencegah pencurian token/cookie sesi aplikasi induk).
- Komunikasi antara parent docsite dan iframe playground berlangsung strictly lewat asynchronous `postMessage` protocol dengan format JSON-RPC envelope.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### AST Parsing & Type Resolution Pipeline
Ketika TypeScript mem-parsing sebuah komponen, ia membentuk hierarki graph. Komponen antarmuka sederhana menghasilkan graf berikut:

```
SourceFile
 └── InterfaceDeclaration (ButtonProps)
      ├── PropertySignature (variant)
      │    └── UnionTypeNode
      │         ├── LiteralType ('primary')
      │         └── LiteralType ('secondary')
      └── PropertySignature (isLoading)
           └── BooleanKeyword
```

Tantangan arsitektur terbesar adalah **Type Flattening**. Jika antarmuka mengekstensi antarmuka pihak ketiga:
```typescript
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
}
```
Jika parser tidak melakukan evaluasi secara rekursif menggunakan `TypeChecker`, tabel dokumentasi akan dibanjiri ratusan props bawaan DOM HTML (`aria-*`, `onCopy`, `onCut`, dll.), yang mengaburkan esensi prop yang benar-benar dirancang khusus untuk design system tersebut. Oleh karena itu, kita memfilter properti berdasarkan `symbol.declarations[0].getSourceFile().fileName`, memisahkan antara *core proprietary props* dan *inherited standard HTML attributes*.

### Isolasi Keamanan Playground (Threat Model)
Menjalankan arbitrary user-generated JavaScript di browser membawa risiko:
1. Akses Token/Cookie: Potensi pencurian data sesi docsite.
2. Resource Exhaustion: Infinite loop (`while(true) {}`) yang membekukan browser main-thread.
3. DOM Hijacking: Manipulasi layout dokumentasi di luar viewport playground.

Mitigasi wajib:
- **`sandbox` attribute:** `iframe` harus memiliki `sandbox="allow-scripts"`. Hindari penambahan `allow-same-origin`. Dengan aturan ini, iframe berada pada origin unik (`null`), mengisolasi `localStorage`, `sessionStorage`, dan `cookie` dari domain root dokumentasi.
- **Worker-Driven Compilation:** Kompilasi JSX yang berat dieksekusi di Web Worker terpisah agar UI main-thread mempertahankan 60 FPS.
- **Heartbeat Timeout:** Eksekusi kode di dalam iframe dipantau dengan heartbeat loop. Jika script tidak merespons tick selama kurun waktu tertentu (misalnya 2000ms), container iframe di-terminate secara paksa dan me-render fallback error UI.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi CLI-ready tool yang menggunakan TypeScript Compiler API untuk mengekstrak props interface komponen, tipe data, nilai default, dan anotasi JSDoc ke JSON metadata terstruktur.

```typescript
// scripts/extract-props.ts
import * as ts from 'typescript';
import * as fs from 'fs';
import * as path from 'path';

export interface PropMetadata {
  name: string;
  type: string;
  required: boolean;
  defaultValue?: string;
  description: string;
  deprecated?: boolean;
}

export interface ComponentMetadata {
  displayName: string;
  description: string;
  props: Record<string, PropMetadata>;
}

export class ComponentDocExtractor {
  private program: ts.Program;
  private checker: ts.TypeChecker;

  constructor(filePaths: string[], compilerOptions: ts.CompilerOptions = {}) {
    this.program = ts.createProgram(filePaths, {
      target: ts.ScriptTarget.ESNext,
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React,
      ...compilerOptions,
    });
    this.checker = this.program.getTypeChecker();
  }

  public extract(filePath: string): ComponentMetadata | null {
    const sourceFile = this.program.getSourceFile(filePath);
    if (!sourceFile) {
      throw new Error(`Source file not found: ${filePath}`);
    }

    let componentMeta: ComponentMetadata | null = null;

    ts.forEachChild(sourceFile, (node) => {
      // Menangkap ekspresi komponen: export const Component = (props: Props) => { ... }
      if (ts.isVariableStatement(node) && this.isNodeExported(node)) {
        for (const declaration of node.declarationList.declarations) {
          if (ts.isIdentifier(declaration.name) && declaration.initializer) {
            const componentName = declaration.name.text;
            const type = this.checker.getTypeAtLocation(declaration);
            
            // Periksa call signatures untuk komponen fungsional
            const callSignatures = type.getCallSignatures();
            if (callSignatures.length > 0) {
              const signature = callSignatures[0];
              const param = signature.parameters[0];
              
              if (param) {
                const paramType = this.checker.getTypeOfSymbolAtLocation(param, declaration);
                const props = this.extractPropsFromType(paramType);
                const description = ts.displayPartsToString(
                  declaration.symbol?.getDocumentationComment(this.checker) ?? []
                );

                componentMeta = {
                  displayName: componentName,
                  description,
                  props,
                };
              }
            }
          }
        }
      }
    });

    return componentMeta;
  }

  private extractPropsFromType(type: ts.Type): Record<string, PropMetadata> {
    const props: Record<string, PropMetadata> = {};
    const properties = type.getProperties();

    for (const prop of properties) {
      const propName = prop.getName();
      
      // Filter out internal React attributes jika diperlukan
      if (propName.startsWith('aria-') || propName === 'children' || propName === 'key') {
        // Logika selektif dapat disesuaikan kebutuhan
      }

      const propType = this.checker.getTypeOfSymbolAtLocation(prop, prop.valueDeclaration!);
      const typeString = this.checker.typeToString(
        propType,
        undefined,
        ts.TypeFormatFlags.NoTruncation
      );

      const isOptional = (prop.getFlags() & ts.SymbolFlags.Optional) !== 0;
      const documentation = ts.displayPartsToString(
        prop.getDocumentationComment(this.checker)
      );

      const jsDocTags = prop.getJsDocTags(this.checker);
      const defaultTag = jsDocTags.find((tag) => tag.name === 'default');
      const deprecatedTag = jsDocTags.find((tag) => tag.name === 'deprecated');

      props[propName] = {
        name: propName,
        type: typeString,
        required: !isOptional,
        defaultValue: defaultTag ? defaultTag.text?.[0]?.text : undefined,
        description: documentation,
        deprecated: !!deprecatedTag,
      };
    }

    return props;
  }

  private isNodeExported(node: ts.Node): boolean {
    return (
      (ts.getCombinedModifierFlags(node as ts.Declaration) & ts.ModifierFlags.Export) !== 0 ||
      (!!node.parent && node.parent.kind === ts.SyntaxKind.SourceFile)
    );
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanika logika dari implementasi `extract-props.ts` di atas:

- **Baris 23–29:** Instansiasi `ts.createProgram`. Membentuk dependency graph penuh dari *entry files*. Ini memastikan bahwa tipe-tipe eksternal yang diimpor dari module lain (seperti type definitions generic atau tokens) dapat diselesaikan (*resolved*) dengan benar oleh `TypeChecker`.
- **Baris 30:** Mengambil instance `ts.TypeChecker`. Engine internal ini bertanggung jawab menghitung relasi antar tipe data, inferensi tipe, resolusi Union types, dan pembacaan metadata simbol.
- **Baris 40–43:** `ts.forEachChild` menelusuri top-level AST nodes dari file sumber. Kita memfilter node yang bertipe `VariableStatement` dan memiliki modifier `export`, menandakan variabel tersebut diekspos keluar module.
- **Baris 48–52:** Identifikasi komponen via `callSignatures`. Komponen functional React pada hakikatnya adalah fungsi yang menerima parameter pertama berupa `props`. Kita mengambil signature pemanggilan fungsi untuk mengekstrak definisi parameter tersebut.
- **Baris 54–57:** Membaca tipe dari parameter `props` melalui `this.checker.getTypeOfSymbolAtLocation`. Ini mengabstraksi properti apakah ia dideklarasikan sebagai `interface`, inline object literal, maupun `type` alias.
- **Baris 78–82:** `type.getProperties()` mengekstrak seluruh simbol properti yang membentuk tipe objek tersebut, termasuk properti yang diwariskan melalui `extends`.
- **Baris 85–89:** `checker.typeToString` mentranslasikan representasi memori internal type checker ke format teks yang dibaca manusia (misal: `"sm" | "md" | "lg"`). Bendera `NoTruncation` mencegah TypeScript memotong output tipe yang panjang dengan elipsis (`...`).
- **Baris 91:** Pengecekan flag bitwise `ts.SymbolFlags.Optional` untuk menentukan apakah prop bersifat opsional (`?`) atau wajib (*mandatory*).
- **Baris 97–100:** Ekstraksi spesifik JSDoc tags (`@default`, `@deprecated`). Anotasi ini memungkinkan desainer/developer menulis metadata langsung di dalam komentar kode yang langsung terefleksi ke UI dokumentasi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Skala Besar FinTech Platform
Sebuah platform perbankan digital memiliki design system bernama **Nexus UI** yang dikonsumsi oleh lebih dari 120 insinyur frontend di 14 squad berbeda. 

**Permasalahan:**
1. **Documentation Drift:** Komponen `AccountTransferCard` memperbarui API props untuk validasi Biometrik, namun dokumentasi web masih mencantumkan API versi lama selama 2 bulan. Mengakibatkan 3 squad salah mengimplementasikan error-handling.
2. **Sandbox Crash & Vulnerability:** Dokumentasi yang lama menggunakan package `react-live` standar yang mengeksekusi kode langsung di root frame. Seorang insinyur secara tidak sengaja menjalankan kode playground yang mengakses `window.localStorage.getItem('auth_token')`, mendemonstrasikan kerentanan isolasi DOM tingkat kritis.
3. **High Documentation Friction:** Rata-rata waktu adaptasi breaking-change token baru (migrasi dari hardcoded hex ke Semantic Token) memakan waktu 4 bulan per squad karena tidak adanya integrasi linting proaktif di IDE.

**Solusi Terintegrasi:**
1. Membangun Documentation Automation Engine yang menolak Pull Request (via CI Check) jika ada perbedaan antara TypeScript AST exports dan skema metadata JSON.
2. Merancang Sandbox Renderer terisolasi total menggunakan MessageChannel, Web Worker Sucrase transpiler, dan `iframe` berbasis origin terpisah dengan kebijakan Content Security Policy (CSP) ketat.
3. Menulis Custom ESLint Rule dan AST Codemod untuk memigrasikan propusang secara otomatis saat proses build atau on-save di VS Code konsumen.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi end-to-end: Sandboxed Live Playground Runner lengkap dengan Transpilation Worker dan secure iframe host bridge.

### 1. Web Worker: Transpilation Worker (`playground.worker.ts`)
```typescript
// workers/playground.worker.ts
import { transform } from 'sucrase';

export interface TranspileRequest {
  id: string;
  code: string;
}

export interface TranspileResponse {
  id: string;
  transpiledCode?: string;
  error?: string;
}

self.onmessage = (event: MessageEvent<TranspileRequest>) => {
  const { id, code } = event.data;

  try {
    const result = transform(code, {
      transforms: ['jsx', 'typescript', 'imports'],
      production: false,
      jsxRuntime: 'classic', // Kompatibel dengan wrapping evaluasi manual
    });

    const response: TranspileResponse = {
      id,
      transpiledCode: result.code,
    };
    self.postMessage(response);
  } catch (err: unknown) {
    const error = err instanceof Error ? err.message : 'Unknown compilation error';
    self.postMessage({ id, error });
  }
};
```

### 2. Client-Side Sandboxed Runner Component (`LivePlayground.tsx`)
```tsx
// components/LivePlayground.tsx
import React, { useEffect, useRef, useState, useCallback } from 'react';

interface LivePlaygroundProps {
  initialCode: string;
  height?: string;
}

const IFRAME_TEMPLATE = `
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-eval' 'inline'; style-src 'unsafe-inline'; img-src data: https:;">
    <style>
      body { margin: 0; padding: 16px; font-family: system-ui, -apple-system, sans-serif; background: #ffffff; }
      #error-boundary { color: #dc2626; background: #fee2e2; padding: 8px; border-radius: 4px; font-family: monospace; display: none; white-space: pre-wrap; }
    </style>
  </head>
  <body>
    <div id="error-boundary"></div>
    <div id="root"></div>
    <script>
      const errorContainer = document.getElementById('error-boundary');
      
      window.onerror = function(message, source, lineno, colno, error) {
        errorContainer.style.display = 'block';
        errorContainer.textContent = (error && error.stack) ? error.stack : message;
      };

      window.addEventListener('message', (event) => {
        // Validasi struktur event
        if (!event.data || event.data.type !== 'EVAL_CODE') return;
        
        errorContainer.style.display = 'none';
        errorContainer.textContent = '';
        
        try {
          // Bersihkan render tree sebelumnya
          const root = document.getElementById('root');
          root.innerHTML = '';
          
          // Environment runtime minimal
          const exports = {};
          const module = { exports };
          
          // Function constructor untuk isolasi variabel lokal
          const executeCode = new Function('module', 'exports', 'React', event.data.code);
          executeCode(module, exports, window.parentReactContext);
          
          // Bila kode me-render via React runner internal
          if (typeof exports.default === 'function') {
             // Opsional: Mount ke React engine yang di-expose ke iframe
          }
        } catch (err) {
          errorContainer.style.display = 'block';
          errorContainer.textContent = err.stack || err.toString();
        }
      });
    </script>
  </body>
</html>
`;

export const LivePlayground: React.FC<LivePlaygroundProps> = ({ initialCode, height = '300px' }) => {
  const [code, setCode] = useState(initialCode);
  const [compilationError, setCompilationError] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const workerRef = useRef<Worker | null>(null);
  const pendingRequestId = useRef<string | null>(null);

  // Inisialisasi Transpilation Worker
  useEffect(() => {
    workerRef.current = new Worker(new URL('../workers/playground.worker.ts', import.meta.url), {
      type: 'module',
    });

    workerRef.current.onmessage = (event: MessageEvent) => {
      const { id, transpiledCode, error } = event.data;
      if (id !== pendingRequestId.current) return; // Drop stale compilations

      if (error) {
        setCompilationError(error);
      } else if (transpiledCode && iframeRef.current?.contentWindow) {
        setCompilationError(null);
        iframeRef.current.contentWindow.postMessage(
          {
            type: 'EVAL_CODE',
            code: transpiledCode,
          },
          '*' // Valid karena sandbox origin bernilai "null"
        );
      }
    };

    return () => {
      workerRef.current?.terminate();
    };
  }, []);

  const triggerCompilation = useCallback((srcCode: string) => {
    const requestId = crypto.randomUUID();
    pendingRequestId.current = requestId;
    workerRef.current?.postMessage({ id: requestId, code: srcCode });
  }, []);

  useEffect(() => {
    triggerCompilation(code);
  }, [code, triggerCompilation]);

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
      <div style={{ background: '#1e293b', padding: '8px' }}>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck={false}
          style={{
            width: '100%',
            height: '120px',
            background: 'transparent',
            color: '#f8fafc',
            fontFamily: 'monospace',
            border: 'none',
            outline: 'none',
            resize: 'vertical',
          }}
        />
      </div>

      {compilationError && (
        <div style={{ background: '#fee2e2', color: '#dc2626', padding: '8px', fontFamily: 'monospace', fontSize: '12px' }}>
          {compilationError}
        </div>
      )}

      {/* Frame Sandboxing: Tanpa 'allow-same-origin' menjamin zero-access ke context docsite */}
      <iframe
        ref={iframeRef}
        title="Live Playground Runner"
        sandbox="allow-scripts"
        srcDoc={IFRAME_TEMPLATE}
        style={{ width: '100%', height, border: 'none' }}
      />
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Memilih arsitektur dokumentasi memerlukan pemahaman trade-off performa, keamanan, dan skalabilitas.

| Pendekatan Runtime Playground | Arsitektur Teknis | Tingkat Isolasi Keamanan | Kompleksitas Build & Runtime | Performa Main-Thread |
| :--- | :--- | :--- | :--- | :--- |
| **In-Memory Dynamic Eval (e.g., react-live)** | `eval()` atau `new Function()` langsung pada root DOM tree aplikasi. | **Sangat Rendah.** Eksekusi kode memiliki akses penuh ke Document, `window`, `localStorage`, cookie, dan credential parent. | Rendah. Zero dependency worker/iframe. | **Rentan Bottleneck.** Transpilasi memblokir UI thread; memory leaks mudah terjadi. |
| **Sandboxed Iframe + Worker (Pendekatan Modul Ini)** | Transpilasi kode di Web Worker; render dilakukan di dalam `iframe` dengan `sandbox="allow-scripts"`. | **Tinggi.** Strict isolation. Origin sandboxed bernilai `null`, CSP menolak pembacaan data credential parent. | Menengah-Tinggi. Memerlukan IPC (Inter-Process Communication) message passing. | **Optimal.** Offloaded compilation tidak mengorbankan framerate aplikasi host. |
| **Remote Sandboxed Container (e.g., CodeSandbox Engine)** | Virtual container yang di-host di micro-VM eksternal, di-embed via client iframe. | **Ekstrem.** Terisolasi total pada level operating system micro-virtualization. | Sangat Tinggi. Membutuhkan infrastruktur server backend khusus dan latency network. | **Bergantung Jaringan.** Loading time lambat; memerlukan koneksi online persisten. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Complex TypeScript Types: Generics & Recursive Types
- **Skenario:** Komponen Tree atau Form Field menggunakan conditional/mapped generic types:
  ```typescript
  type FormFieldProps<T> = T extends string ? TextInputProps : SelectProps<T>;
  ```
- **Failure Mode:** Parser AST bawaan akan mengekstrak type string mentah `"FormFieldProps<T>"` yang tidak bermakna bagi pembaca dokumentasi tanpa konteks resolusi generic.
- **Mitigasi:** Gunakan `checker.getBaseConstraintOfType(type)` untuk mengekstrak constraint fallback, atau lakukan *spec-level mocking* dengan menulis interface contoh yang ter-resolusi khusus untuk keperluan dokumentasi.

### 2. Memory Leaks pada Sandboxed Iframe Lifecycle
- **Skenario:** Pengguna mengetik secara cepat di live code editor (misal: 10 karakter per detik).
- **Failure Mode:** Setiap karakter memicu update `srcDoc` pada iframe atau menginjeksi node baru ke dalam iframe tanpa melepaskan referensi event listener dan DOM elements sebelumnya. Menyebabkan browser tab crash akibat Out-of-Memory (OOM).
- **Mitigasi:** Terapkan teknik *Debounce Compilation* (misal: jeda 300ms sebelum transpilasi dikirim ke worker), dan di dalam iframe, lakukan reuse DOM root dengan memanggil `unmountComponentAtNode` atau membersihkan inner HTML secara teratur.

### 3. Infinite Loops di User Live Code
- **Skenario:** Pengguna menulis bug pada editor playground:
  ```javascript
  while(true) { /* blocking */ }
  ```
- **Failure Mode:** Iframe membeku. Meskipun terisolasi secara data, thread JavaScript browser bersifat tunggal untuk domain frame bersangkutan, mengakibatkan seluruh tab docsite unresponsive.
- **Mitigasi:** Konfigurasi worker/transpiler Babel untuk menginjeksi loop-protection transform plugin (seperti `babel-plugin-loop-timeout`), yang secara otomatis menyuntikkan pengecekan waktu batas maksimal (`Date.now()`) pada setiap block iterasi AST.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menulis Tabel Props secara Manual di File Markdown
*   **Kesalahan:** Mengisi properti, tipe data, dan keterangan secara manual dalam tabel markdown (`| propName | type | default |`).
*   **Dampak:** Desinkronisasi tak terhindarkan (*documentation drift*). Saat prop diubah di file source TypeScript, developer sering kali lupa memperbarui tabel di markdown.
*   **Solusi:** Larang tabel prop manual di MDX. Gunakan custom MDX tag seperti `<PropsTable component="Button" />` yang merujuk langsung ke JSON schema yang diekstrak saat proses build.

### 2. Mengabaikan Tipe Union Literals yang Terlalu Luas
*   **Kesalahan:** Menggunakan tipe data `string` longgar alih-alih strict literal union (`variant: string` alih-alih `variant: 'primary' | 'secondary' | 'danger'`).
*   **Dampak:** Dokumentasi props table hanya menampilkan kata "string", memaksa engineer konsumen membuka file implementasi komponen untuk mencari tahu opsi yang valid.
*   **Solusi:** Gunakan Type Linter (`@typescript-eslint`) yang mewajibkan literal typing pada props komponen design system.

### 3. Menggunakan `allow-same-origin` bersamaan dengan `allow-scripts`
*   **Kesalahan:** Konfigurasi iframe:
    ```html
    <iframe sandbox="allow-scripts allow-same-origin" ... />
    ```
*   **Dampak:** Membuka celah keamanan fatal. Halaman di dalam iframe dapat mengeksekusi script yang memanipulasi attribute sandbox-nya sendiri dan mengakses seluruh memori context host, meniadakan fungsi isolasi sepenuhnya.
*   **Solusi:** Pertahankan HANYA `sandbox="allow-scripts"`. Komunikasi data wajib dilakukan melalui `postMessage`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Semantic Versioning for Documentation:** Dokumentasikan *deprecation timeline* dengan menyertakan versi rilis dan versi target pemusnahan (contoh: `@deprecated Sejak v4.2.0, akan dihapus pada v5.0.0. Gunakan <Badge variant="neutral">`).
2.  **Monorepo Shared Typings:** Tempatkan skema metadata komponen (`ComponentMetadata`) pada package core utilitas monorepo agar dapat dikonsumsi bersama oleh engine dokumentasi, automated test runner, dan ESLint custom rules.
3.  **Visual Regression Playground Snapshots:** Manfaatkan contoh kode playground interaktif sebagai automated test-cases untuk visual regression testing (misalnya mengintegrasikan Playwright untuk me-render playground examples secara headless dan membandingkan pixel-diff).
4.  **Codemod Companion:** Setiap kali merilis breaking changes pada component props yang tertera di dokumentasi, sediakan perintah CLI jscodeshift yang tertaut langsung di halaman panduan migrasi.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Offloading Compiler dari Main Thread
Memindahkan parsing dan transpiling JSX/TSX dari UI Main-Thread ke Web Worker terpisah memotong Total Blocking Time (TBT) hingga ~85% saat rendering halaman dokumentasi yang memuat banyak live playground components.

### 2. Lazy Compilation of Interactive Playgrounds
Jangan mengompilasi seluruh interactive playground sekaligus saat halaman dimuat:
- Gunakan `IntersectionObserver` pada wrapper playground.
- Sebelum komponen masuk ke dalam viewport (misalnya `rootMargin: '200px'`), render preview gambar statis atau syntactically-highlighted code block biasa.
- Lakukan instansiasi iframe dan worker transpilasi hanya ketika komponen playground mendekati viewport pembaca.

### 3. Build-Time Static Prop Schema Generation
Alih-alih menjalankan TypeScript Compiler API di level runtime client, jalankan ekstraksi props AST secara statis pada saat tahapan CI/CD build. Kompilasikan hasilnya menjadi file `.json` chunk individual per komponen. Client hanya mengunduh potongan JSON spesifik komponen yang sedang dibuka.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Content Security Policy (CSP) pada Sandbox Template:**
    Inject meta tag ketat di dalam sandboxed frame template:
    ```html
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-eval' 'inline'; style-src 'unsafe-inline'; font-src data:; img-src data: https:;">
    ```
    Mencegah live script melakukan unauthorized network request (`fetch`/`xhr`) ke resource backend internal, membatasi akses eksfiltrasi data.
2.  