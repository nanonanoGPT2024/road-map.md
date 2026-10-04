# SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Track / Kategori** | 02-Programming-Languages / JavaScript |
| **Bab / Modul** | Bab 07 / Modul 01 |
| **Judul Modul** | Modular Architecture, Dynamic Linker & AST Tooling |
| **Level Kemahiran** | Advanced / Principal Engineer |
| **Prasyarat Pengetahuan** | V8 Execution Pipeline, Event Loop internals, Scope Chain & Closures, ES6+ Syntax, Lexical Grammar |
| **Dependencies / Stack** | Node.js (v20+ LTS runtime), Acorn / `@babel/parser`, `@babel/traverse`, `@babel/generator` |
| **Target Ekosistem** | V8 Runtime, Node.js Module Subsystem, Modern Bundler Engines (Vite, Rollup, Webpack) |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:
1. **Mendekonstruksi** siklus hidup ECMAScript Modules (ESM) ke dalam tiga fase deterministik: *Construction (Parsing/Loading)*, *Instantiation (Linking)*, dan *Evaluation*.
2. **Menganalisis** disparitas struktural antara mekanisme *dynamic runtime evaluation & value copying* milik CommonJS (CJS) dengan model *static topological graph & live bindings* milik ESM.
3. **Mengimplementasikan** *custom dynamic module linker* runtime yang mampu menangani resolusi dependensi siklik (*cyclic dependencies*) tanpa memicu dereferensi variabel tak terdefinisi (*Temporal Dead Zone*).
4. **Memanipulasi** Abstract Syntax Tree (AST) berbasis spesifikasi ESTree menggunakan pola desain *Visitor* untuk melakukan analisis statis, instrumentasi runtime, dan transformasi kode mutakhir.
5. **Membangun** pipeline modular compiler/bundler mandiri berdaya guna tinggi yang mengintegrasikan leksikalisasi, *dependency graph traversal*, rewriting spesifikasi impor dinamis, dan *code emission*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Runtime Execution vs Static Graph Linker

Untuk menguasai ekosistem modul modern dan tooling JavaScript, seorang *runtime architect* harus beralih dari model mental "menjalankan berkas kode baris demi baris" menuju model mental **"konstruksi graf terarah mendahului eksekusi"**.

```
Mental Model Tradisional (CommonJS / Script-based):
[File A Entry] ---> [Eksekusi Baris 1..N] ---> require('./B') ---> [Lompat ke File B & Jalankan] ---> Kembalikan exports object
                    * Imperatif, sinkron, evaluasi runtime, module exports adalah objek mutabel biasa.

Mental Model Arsitektur Modern (ESM & Compiler Linker):
Fase 1: Static Graph Construction (Parser membedah sintaks, membangun Directed Acyclic/Cyclic Graph)
Fase 2: Instantiation (Linker mengalokasikan slot memori untuk live bindings; nilai BELUM dihitung)
Fase 3: Evaluation (V8 mengeksekusi byte-code dari daun graf ke akar; slot memori terisi nilai final)
```

### AST Sebagai Representasi Logika Murni
Source code JavaScript hanyalah string berurutan yang dirancang untuk keterbacaan manusia. Bagi V8 dan toolchain modern (seperti Babel, SWC, Rollup), source code adalah **pohon semantik hirarkis** (*Abstract Syntax Tree*). 
* Jangan menganggap kode sebagai teks; pandang kode sebagai struktur data pohon yang terdiri dari *Node*, *Property*, dan *Binding Scope*. 
* Transformasi kode bukanlah pencarian string dengan Regex (yang rentan terhadap konteks sintaksis), melainkan operasi graf rekursif berbasis *tree mutation* dan *type-checked visitors*.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup ESM: Tiga Fase V8 Module Lifecycle

```
[Entry Point Specifier]
         |
========================================================================================
FASE 1: CONSTRUCTION / LOADING (Asynchronous Fetching & Parsing)
========================================================================================
         |
         v
+------------------+       Acorn / V8 Parser      +-----------------------------+
| Fetch / Read     | ---------------------------> | Parse Source Text           |
| Source File Text |                              | Validasi Grammar & Syntax   |
+------------------+                              +-----------------------------+
                                                                 |
                                                                 v
                                                  +-----------------------------+
                                                  | Construct Source Text       |
                                                  | Module Record (STMR)        |
                                                  | - Identifikasi Imports      |
                                                  | - Identifikasi Exports      |
                                                  +-----------------------------+
                                                                 |
               +-------------------------------------------------+
               |
               v (Rekursif untuk semua specifier impor)
+-----------------------------+
| Module Map (Cache Check)    |
| Status: [unlinked]          |
+-----------------------------+
         |
========================================================================================
FASE 2: INSTANTIATION (Topological Linking & Live Bindings Allocation)
========================================================================================
         |
         v
+---------------------------------------------------------------------------------------+
| Traversal Depth-First Post-Order (Daun ke Root)                                       |
| - Alokasikan Module Environment Record (ruang memori khusus).                         |
| - Sambungkan Export Identifier langsung ke Import Identifier via Pointer Memori.      |
| - Binding belum memiliki nilai (TDZ diterapkan), BUKAN duplikasi nilai.               |
| Status: [linking] -> [linked]                                                         |
+---------------------------------------------------------------------------------------+
         |
========================================================================================
FASE 3: EVALUATION (Execution of Bytecode)
========================================================================================
         |
         v
+---------------------------------------------------------------------------------------+
| Eksekusi Top-Level Code dari daun graf (Bottom-Up)                                    |
| - Mengisi ruang memori yang telah dialokasikan pada Fase 2.                           |
| - Side-effects dieksekusi tepat satu kali.                                            |
| Status: [evaluating] -> [evaluated]                                                   |
+---------------------------------------------------------------------------------------+
         |
         v
[Instance Modul Siap Digunakan Runtime]
```

### Pipeline Arsitektur Transformasi AST

```
+-------------------+
| Raw JS Source Code|
+-------------------+
          |
          v [Lexer: Tokenization]
+-------------------+
|   Stream Token    |
+-------------------+
          |
          v [Parser: Syntactic Analysis]
+-------------------+
| AST (ESTree Spec) | <----------------+
+-------------------+                  |
          |                            |
          v [Traverser: Visitor Pattern]
+-------------------+                  | (AST Mutations / Injections)
|  Node Visitors    | -----------------+
|  - Scope Checking |
|  - Spec Rewriter  |
+-------------------+
          |
          v [Code Generator]
+-------------------+
| Transformed JS    | + Source Map
+-------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur `Source Text Module Record` (STMR)
Berdasarkan spesifikasi ECMAScript (ECMA-262), runtime merepresentasikan berkas ESM internal melalui `Source Text Module Record`, yang memiliki bidang-bidang kritis berikut:

*   `[[Status]]`: Status siklus hidup modul (`unlinked`, `linking`, `linked`, `evaluating`, `evaluated`).
*   `[[Environment]]`: `Module Environment Record` khusus yang menampung binding leksikal modul.
*   `[[ECMAScriptCode]]`: Parse tree lengkap dari berkas kode sumber.
*   `[[RequestedModules]]`: Daftar string literal dari specifier yang diimpor (misal: `['./utils.js', 'node:crypto']`).
*   `[[ImportEntries]]`: Koleksi record yang mendefinisikan kaitan antara nama lokal dan identifier yang diminta dari modul eksternal.
*   `[[ExportEntries]]`: Koleksi record yang mendefinisikan binding lokal yang diekspos keluar beserta alias publiknya.
*   `[[DFSIndex]]` & `[[DFSAncestorIndex]]`: Integer yang digunakan oleh algoritma Tarjan untuk mendeteksi siklus dependensi pada fase *Instantiation* dan *Evaluation*.

### 2. Live Bindings vs Copy-on-Export
Perbedaan mekanis fundamental antara CJS dan ESM terletak pada representasi referensi memori:

*   **CommonJS**:
    ```javascript
    // CJS: Mengekspor salinan nilai primitif saat baris dieksekusi.
    // Module A
    let count = 1;
    module.exports = { count, inc: () => count++ };
    // Module B
    const { count, inc } = require('./A');
    inc();
    console.log(count); // Tetap 1! Objek 'exports' menduplikasi nilai primitif count.
    ```
*   **ECMAScript Modules (Live Bindings)**:
    ```javascript
    // ESM: Mengikat identifier lokal ke slot memori Environment Record modul target.
    // Module A
    export let count = 1;
    export const inc = () => count++;
    // Module B
    import { count, inc } from './A.js';
    inc();
    console.log(count); // Menjadi 2! 'count' di Module B adalah live reference (pointer)
                        // ke Module Environment Record milik Module A.
    ```
    *Konsekuensi Arsitektural*: Binding impor bersifat *read-only view*. Mencoba melakukan mutasi langsung (`count = 3` di Module B) akan memicu runtime `TypeError: Assignment to constant variable` di level engine.

### 3. Anatomi Pohon AST (ESTree Node Structure)
Dalam parser berbasis standar ESTree (Acorn, Babel, ESPree), setiap konstruksi sintaksis direpresentasikan sebagai antarmuka `Node`:

```typescript
interface Node {
  type: string;           // Identifikasi tipe semantik (e.g., 'ImportDeclaration', 'BinaryExpression')
  loc: SourceLocation;    // Baris dan kolom awal/akhir pada source code mentah
  start: number;          // Indeks offset karakter awal (0-indexed)
  end: number;            // Indeks offset karakter akhir
}

// Representasi pemanggilan modul dinamis: import(specifier)
interface ImportExpression extends Node {
  type: "ImportExpression";
  source: Expression;     // AST Node ekspresi specifier (e.g., Literal atau BinaryExpression)
  options?: Expression;   // Parameter opsional import attributes (assert/with)
}
```

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Resolusi Graf Siklik dan Algoritma Tarjan pada ESM Linker
Ketika Modul A mengimpor Modul B, dan Modul B mengimpor kembali Modul A (*cyclic dependency*), CommonJS sering kali menghasilkan *partial exports object* yang memicu bug tak terduga (*undefined imports*). 

ESM menangani siklus dependensi secara deterministik menggunakan **Algoritma DFS (Depth-First Search) Post-Order** terindeks:
1. Linker menelusuri graf dependensi secara rekursif hingga menemukan daun dependensi.
2. Setiap modul diberikan indeks numerik urut (`[[DFSIndex]]`). Modul yang sama tidak akan diparse atau diinstansiasi dua kali karena tersimpan di `HostDefined Module Map`.
3. Pada fase **Instantiation**, referensi pointer dialokasikan di Environment Record untuk kedua modul tanpa mengeksekusi kode apa pun. Export bindings belum memiliki nilai.
4. Pada fase **Evaluation**, eksekusi dilakukan secara bottom-up. Jika Modul A memanggil fungsi di Modul B sebelum Modul A selesai dievaluasi, Modul B dapat mengakses variabel Modul A *asalkan* eksekusi tersebut terjadi setelah assignment nilai dilakukan di memori. Jika diakses saat berada di Temporal Dead Zone (TDZ), V8 langsung melemparkan `ReferenceError: Cannot access 'X' before initialization`.

### Resolusi Modul Dinamis vs Statis
Pernyataan `import x from 'y'` bersifat statis:
* Harus diletakkan di top-level scope.
* Parsing specifier string dilakukan murni saat fase *Construction* sebelum instruksi JS pertama dieksekusi.
* Memungkinkan optimasi kompilator: *Tree-shaking (Dead Code Elimination)* dan *Scope Hoisting*.

Operator `import(specifier)` bersifat dinamis:
* Mengembalikan `Promise<ModuleNamespaceObject>`.
* Diperlakukan di AST sebagai `ImportExpression`, bukan `ImportDeclaration`.
* Menginisiasi siklus Parsing -> Instantiation -> Evaluation baru secara mikro-task di Event Loop untuk sub-graf yang dituju secara runtime.

### Mekanika Visitor Pattern pada AST Traversal
Traversal AST menggunakan konsep rekursi ganda (*double dispatch*):
1. **Traverser** menelusuri setiap simpul pohon (*Depth-First Search*).
2. Setiap simpul memicu dua event: `enter` (saat pertama kali simpul dikunjungi sebelum anak-anaknya) dan `exit` (setelah semua anak simpul selesai diproses).
3. **Scope Management**: Visitor tingkat lanjut memanfaatkan pelacakan *Lexical Scope ScopeStack* untuk mengetahui apakah suatu `Identifier` merujuk pada deklarasi lokal, closure luar, atau global variabel tanpa mengeksekusi kode tersebut.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Berikut adalah implementasi **Miniature Dynamic ESM-like Linker & Execution Sandbox** menggunakan Node.js Runtime primitif (`vm` context) untuk mendemonstrasikan secara presisi cara kerja alokasi memori dua fase (Link -> Evaluate) serta Live Bindings.

```javascript
// core-linker.js
import vm from 'node:vm';

class VirtualModuleLinker {
  constructor() {
    // Host Module Map: Menyimpan Module Record yang terdaftar berdasarkan path/ID
    this.moduleRegistry = new Map();
    // Sandbox Global Context
    this.context = vm.createContext({
      console: { log: (...args) => console.log('[Sandbox Engine]:', ...args) }
    });
  }

  // Mendaftarkan modul berupa string source code mentah
  registerModule(specifier, sourceCode) {
    // Membangun SourceTextModule menggunakan API vm Node.js
    const moduleRecord = new vm.SourceTextModule(sourceCode, {
      identifier: specifier,
      context: this.context,
      initializeImportMeta: (meta) => {
        meta.url = `virtual://app/${specifier}`;
      }
    });

    this.moduleRegistry.set(specifier, moduleRecord);
    return moduleRecord;
  }

  // Linker Callback: Menghubungkan binding antar modul
  async #linkerCallback(specifier, referencingModule) {
    if (!this.moduleRegistry.has(specifier)) {
      throw new Error(
        `Dynamic Link Error: Modul '${specifier}' diminta oleh '${referencingModule.identifier}' tidak ditemukan.`
      );
    }
    return this.moduleRegistry.get(specifier);
  }

  // Eksekusi pipeline penuh: Link lalu Evaluate
  async runPipeline(entrySpecifier) {
    const entryModule = this.moduleRegistry.get(entrySpecifier);
    if (!entryModule) {
      throw new Error(`Entry module '${entrySpecifier}' belum terdaftar.`);
    }

    console.log(`\n--- FASE 2: INSTANTIATION (LINKING) [${entrySpecifier}] ---`);
    // Menghubungkan seluruh graf import/export secara topological
    await entryModule.link(this.#linkerCallback.bind(this));

    console.log(`--- FASE 3: EVALUATION [${entrySpecifier}] ---`);
    // Mengeksekusi bytecode bottom-up
    await entryModule.evaluate();

    return entryModule.namespace;
  }
}

// Simulasi Kasus Kode: Live Bindings & Evaluasi Siklik
const linker = new VirtualModuleLinker();

// Modul A: Counter dengan mutation method
linker.registerModule(
  'counter.js',
  `
  export let count = 0;
  export function increment() {
    count++;
  }
  `
);

// Modul B: Consumer yang memodifikasi dan membaca live pointer
linker.registerModule(
  'main.js',
  `
  import { count, increment } from 'counter.js';

  console.log('Nilai awal count:', count);
  increment();
  console.log('Nilai setelah increment():', count);
  
  export const finalCount = count;
  `
);

// Jalankan runtime
(async () => {
  try {
    const ns = await linker.runPipeline('main.js');
    console.log('\nPipeline Selesai. Hasil Namespace Ekspor:', ns);
  } catch (err) {
    console.error('Runtime Linker Failure:', err);
  }
})();
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut dekonstruksi struktural dari implementasi `core-linker.js` pada Seksi 07:

1. `import vm from 'node:vm';`: Mengimpor modul virtual machine internal Node.js. Modul ini menyediakan implementasi level engine V8 terhadap `SourceTextModule` yang merefleksikan spesifikasi formal ECMAScript.
2. `this.moduleRegistry = new Map();`: Menginisialisasi *Host-defined Module Map*. Berperan sebagai sistem caching internal V8 untuk memastikan modul dengan specifier yang sama hanya dibuatkan satu instance `SourceTextModule`.
3. `vm.createContext({...})`: Mengisolasi *V8 Execution Context* (Global Object dan Scope Environment terpisah). Mencegah kebocoran runtime virtual ke dalam proses utama Node.js.
4. `new vm.SourceTextModule(sourceCode, { ... })`: **Fase 1 (Construction)**. Engine melakukan parse sintaksis leksikal terhadap `sourceCode`. Jika terdapat sintaks error, eksekusi gagal di titik ini. Bidang `identifier` ditetapkan untuk penelusuran call-stack.
5. `async #linkerCallback(specifier, referencingModule)`: Implementasi interface host dynamic linker. Ketika compiler menemukan token impor (misal `import ... from 'counter.js'`), engine menginterupsi eksekusi dan memanggil method ini untuk mengambil referensi `SourceTextModule` anak.
6. `await entryModule.link(...)`: **Fase 2 (Instantiation)**. Membangun topological map graf dependensi. V8 mengalokasikan slot memori untuk variabel `export let count` di dalam Environment Record `counter.js`, lalu mengikat `import { count }` di `main.js` langsung ke pointer alamat memori tersebut. Nilai belum diinisialisasi secara operasional.
7. `await entryModule.evaluate()`: **Fase 3 (Evaluation)**. V8 mengeksekusi bytecode `counter.js` terlebih dahulu (daun), menginisialisasi `count = 0`, lalu mengeksekusi bytecode `main.js` (root).
8. `increment(); console.log(count);`: Memverifikasi mekanisme *live binding*. Saat fungsi `increment()` dieksekusi di context `counter.js`, slot memori diubah. Modul `main.js` yang membaca variabel `count` langsung melihat perubahan nilai ke `1` karena ia memegang pointer langsung ke memori `counter.js`, bukan nilai salinan statis.

---

# SEKSI 09 — STUDI KASUS NYATA (PRODUCTION SCENARIO)

### Arsitektur Micro-Frontend Dynamic Plugin Engine dengan AST Sandboxing & Module Rewriting

**Konteks Masalah**:
Sebuah platform analitik finansial enterprise skala besar memperbolehkan pihak ketiga mengunggah ekstensi modul (plugin) secara dinamis tanpa proses deploy ulang host system.

**Tantangan Arsitektur**:
1. **Keamanan & Isolasi Global**: Plugin pihak ketiga tidak boleh memanggil global scope berbahaya (misal `window.localStorage`, `process.env`, `eval`, atau modul internal `node:child_process`).
2. **Dynamic Specifier Virtualization**: Pengembang plugin menulis kode dengan standar ES Module (`import { chart } from '@core/visualizer'`), namun modul `@core/visualizer` tidak tersedia di disk plugin melainkan disuntikkan secara dinamis oleh host runtime via in-memory Module Linker.
3. **AST Tooling Requirement**: Host harus memvalidasi integritas AST sebelum eksekusi. Jika plugin mencoba mengakses AST Node berbahaya, build ditolak. Jika lolos, specifier impor dinamis harus di-*rewrite* ke URL CDN yang telah di-checksum secara otomatis.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini merupakan implementasi utuh **Security AST Guard & Dynamic Module Virtualizer Engine** menggunakan parser `@babel/parser`, traverser `@babel/traverse`, dan generator `@babel/generator`.

```javascript
// dynamic-plugin-engine.js
import * as parser from '@babel/parser';
import traverseModule from '@babel/traverse';
import generateModule from '@babel/generator';
import vm from 'node:vm';

// Workaround interop untuk paket Babel ESM/CJS dual builds
const traverse = traverseModule.default || traverseModule;
const generate = generateModule.default || generateModule;

/**
 * Enterprise Plugin Compiler & Virtual Security Sandbox
 */
class PluginEngine {
  constructor(allowedDependenciesMap) {
    this.allowedDependencies = allowedDependenciesMap; // Specifier -> Internal In-Memory Module
    this.forbiddenGlobals = new Set(['process', 'eval', 'Function', 'WebAssembly']);
    this.isolatedContext = vm.createContext({
      Object, Array, String, Number, Boolean, Math, Date,
      console: { log: (...args) => console.log('[Plugin Runtime]:', ...args) }
    });
  }

  /**
   * Langkah 1: AST Tooling Pipeline
   * Parse -> Validasi Keamanan (AST Inspection) -> Rewriting Path
   */
  transformAndSecure(sourceCode, pluginId) {
    // 1. Parsing Source Code menjadi Abstract Syntax Tree (ESTree compliant)
    const ast = parser.parse(sourceCode, {
      sourceType: 'module',
      plugins: ['topLevelAwait']
    });

    const forbiddenGlobals = this.forbiddenGlobals;
    const allowedDeps = this.allowedDependencies;

    // 2. Traversal AST dengan Visitor Pattern
    traverse(ast, {
      // Deteksi akses ke Identifier terlarang (Global Scope Protection)
      Identifier(path) {
        if (
          forbiddenGlobals.has(path.node.name) &&
          !path.scope.hasBinding(path.node.name) // Hanya tangkap jika BUKAN variabel lokal
        ) {
          throw new SecurityError(
            `[Security Violation] Akses ke global token '${path.node.name}' dilarang pada plugin '${pluginId}'. Baris: ${path.node.loc?.start.line}`
          );
        }
      },

      // Deteksi evaluasi kode tak aman via AST call expression
      CallExpression(path) {
        const callee = path.node.callee;
        if (callee.type === 'Identifier' && callee.name === 'eval') {
          throw new SecurityError(`[Security Violation] Penggunaan eval() dilarang pada plugin '${pluginId}'.`);
        }
      },

      // Rewriting Import Declaration Specifier
      ImportDeclaration(path) {
        const importSource = path.node.source.value;
        if (!allowedDeps.has(importSource)) {
          throw new SecurityError(
            `[Import Violation] Modul '${importSource}' tidak diizinkan dalam daftar dependensi plugin.`
          );
        }
        // Rewrite import specifier ke domain virtual host
        path.node.source.value = `virtual://host-registry/${importSource}`;
      }
    });

    // 3. Code Generation: Mengembalikan source code bersih hasil transformasi
    const output = generate(ast, { retainLines: true });
    return output.code;
  }

  /**
   * Langkah 2: Dynamic Linker & Instantiation
   */
  async executePlugin(pluginId, rawCode) {
    console.log(`\n=== MEMPROSES PLUGIN: ${pluginId} ===`);
    
    // Transformasi dan Amankan AST
    const securedCode = this.transformAndSecure(rawCode, pluginId);
    console.log('[AST Engine] Validasi Aman & Specifier Berhasil Diformat:');
    console.log(securedCode.trim());

    // Inisialisasi Root SourceTextModule
    const pluginModule = new vm.SourceTextModule(securedCode, {
      identifier: `plugin-${pluginId}.js`,
      context: this.isolatedContext
    });

    // Linker dinamis: memetakan 'virtual://host-registry/X' ke Host Module Record
    const dynamicLinker = async (specifier, referencingModule) => {
      const prefix = 'virtual://host-registry/';
      if (specifier.startsWith(prefix)) {
        const originalSpecifier = specifier.replace(prefix, '');
        const hostSource = this.allowedDependencies.get(originalSpecifier);
        
        return new vm.SourceTextModule(hostSource, {
          identifier: specifier,
          context: this.isolatedContext
        });
      }
      throw new Error(`Resolusi modul gagal: ${specifier}`);
    };

    // Linking graf modul & Evaluasi bytecode
    await pluginModule.link(dynamicLinker);
    await pluginModule.evaluate();

    // Jalankan entry point default jika ada
    if (pluginModule.namespace.default) {
      await pluginModule.namespace.default();
    }
    
    return pluginModule.namespace;
  }
}

class SecurityError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SecurityError';
  }
}

// ==========================================
// TEST IMPLEMENTASI PRODUKSI
// ==========================================
(async () => {
  // Mock Host Internal Modules
  const hostDependencies = new Map();
  hostDependencies.set(
    'metrics-reporter',
    `export function send(metric) { console.log('Metric Sent to Host Server:', metric); }`
  );

  const engine = new PluginEngine(hostDependencies);

  // Kasus 1: Plugin Sah (Valid)
  const validPluginCode = `
    import { send } from 'metrics-reporter';

    export default async function run() {
      send({ event: 'latency', value: 42 });
    }
  `;

  try {
    await engine.executePlugin('valid-analytics', validPluginCode);
  } catch (err) {
    console.error('Eksekusi Plugin Sah Gagal:', err);
  }

  // Kasus 2: Plugin Berbahaya (Mencoba Bypass via Global Scope Process)
  const maliciousPluginCode = `
    import { send } from 'metrics-reporter';

    export default function exploit() {
      // Upaya eksfiltrasi environment host
      const env = process.env; 
      send({ leak: env });
    }
  `;

  try {
    await engine.executePlugin('malicious-plugin', maliciousPluginCode);
  } catch (err) {
    console.error(`DITOLAK OLEH AST SECURITY GUARD: -> ${err.message}`);
  }
})();
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur Modul: CJS vs ESM vs Dynamic Module Federation

| Parameter Evaluasi | CommonJS (CJS) | ECMAScript Modules (ESM) | Dynamic Module Federation (Vite/Webpack) |
| :--- | :--- | :--- | :--- |
| **Model Resolusi** | Runtime Dinamis Sinkron (`require()`). | Statis Asinkron (Fase Parsing terpisah) + Dinamis `import()`. | Network Asynchronous Chunk Resolution via Host Shell. |
| **Binding Karakter** | Value Copying (Objek dievaluasi dan dicopy). | Live Bindings (Pointer memori statis). | Live Bindings / Proxy Wrapper. |
| **Cyclic Dependency Handling** | Mengembalikan objek ekspor parsial/inkomplet. | Dikelola via 2-phase Linking; aman selama TDZ tidak dilanggar. | Bergantung pada build resolution tree federasi. |
| **Tree-Shaking Support** | Sangat Buruk (Membutuhkan static analysis tebakan heuristic). | Luar Biasa (Statis dan deterministik dari deklarasi impor). | Efektif di boundary shared libraries. |
| **Eksekusi di Browser** | Butuh runtime wrapper bundler (e.g., Browserify). | Native di browser via `<script type="module">`. | Memerlukan runtime federasi khusus. |
| **AST Parsing Overhead** | Nol pada build time jika tanpa bundler. | Parsing specifier statis cepat sebelum eksekusi. | AST parsing kompleks saat runtime split & linking. |

### Pendekatan Modifikasi Kode: Regex vs AST Visitors

| Kriteria | String Regex Replacement | AST Transformation (Visitor) |
| :--- | :--- | :--- |
| **Keamanan Semantik** | Sangat Rendah. Rawan salah ubah string literal/komentar. | Mutlak. Membedakan scope, variable binding, dan token literal. |
| **Kinerja CPU & Memori** | Sangat Cepat ($O(N)$ karakter string). | Lebih lambat ($O(N)$ parsing ke tree + alokasi node AST). |
| **Ketahanan Refactoring** | Rentan pecah oleh perubahan whitespace/gaya penulisan. | Sangat Kebal. Menjaga struktur semantik terlepas dari style kode. |
| **Kasus Penggunaan** | String replacer sepele (e.g., ganti flag versi build). | Bundling, Transpilasi, Linters, Security Guards, Dead Code Removal. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Top-Level Await Deadlock Waterfall
Pada ESM, jika sebuah leaf node modul mengeksekusi Top-Level Await (TLA) yang bergantung pada Event atau Promise yang tidak pernah diselesaikan (*unsettled Promise*), seluruh proses evaluasi dependensi ke atas (*ancestor tree*) akan terhenti selamanya:

```javascript
// bad-leaf.js
const res = await new Promise(() => {}); // Tidak pernah resolve
export const data = res;

// entry.js
import { data } from './bad-leaf.js'; // entry.js AKAN MENGALAMI HANG SELAMANYA
console.log('Aplikasi berjalan'); // Baris ini tidak pernah dieksekusi!
```

### 2. Temporal Dead Zone (TDZ) pada Cyclic ESM
Meskipun ESM mendukung resolusi siklik, mengakses nilai variabel sebelum modul pendefinisinya menyelesaikan *Evaluation Phase* akan memicu runtime crash:

```javascript
// a.js
import { bVal } from './b.js';
export const aVal = 'Nilai A';
console.log('Evaluasi B di dalam A:', bVal);

// b.js
import { aVal } from './a.js';
console.log('Evaluasi A di dalam B:', aVal); // CRASH: ReferenceError: Cannot access 'aVal' before initialization
export const bVal = 'Nilai B';
```
*Akar Masalah*: Graf dievaluasi dari `b.js` terlebih dahulu. Saat `b.js` mengakses `aVal`, alokasi memori `aVal` sudah ada (Fase Instantiation selesai), namun bytecodenya belum dievaluasi (TDZ aktif).

### 3. Mutasi Node AST Berujung Infinite Traversal Loop
Pada *AST Tooling*, jika seorang engineer menyisipkan node baru dengan tipe yang sama di dalam visitor tanpa mematikan propagasi traversal:

```javascript
// BAD VISITOR: Memperluas pemanggilan beralih tanpa stop-flag
traverse(ast, {
  CallExpression(path) {
    // Membungkus foo() dengan wrapper(foo())
    const newNode = t.callExpression(t.identifier('wrapper'), [path.node]);
    path.replaceWith(newNode); // RECURSION ERROR: Traverser akan mengunjungi CallExpression baru ini lagi!
  }
});

// FIX: Gunakan path.skip() untuk mencegah traversal masuk ke simpul baru
CallExpression(path) {
  if (path.node.callee.name === 'wrapper') return;
  const newNode = t.callExpression(t.identifier('wrapper'), [path.node]);
  path.replaceWith(newNode);
  path.skip(); // Mencegah evaluasi simpul pengganti
}
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengubah Impor ESM Secara Langsung (Immutable Import Violation)
*Pola Salah*:
```javascript
// consumer.js
import { config } from './config.js';
config.endpoint = 'https://api.internal'; // Jika config di-reassign:
config = {}; // Error: TypeError: Assignment to constant variable.
```
*Solusi*: ESM import binding selalu di-*freeze* di tingkat namespace referensi. Gunakan setter method yang diekspor langsung oleh pemilik modul sumber:
```javascript
// config.js
export let config = { endpoint: 'default' };
export function updateConfig(newConf) { config = newConf; }
```

### Kesalahan 2: Dual Package Hazard (CJS-ESM Mismatch)
*Pola Salah*: Memuat package yang sama melalui `require()` di modul CJS dan melalui `import` di modul ESM dalam satu project Node.js.
*Dampak*: Node.js akan mengalokasikan **DUA INSTANCE** berbeda dari package tersebut di memori karena resolusi specifier yang berbeda. Singletons (seperti database pool connection) akan rusak karena inisialisasi ganda.
*Solusi*: Gunakan field `exports` modern di `package.json` dengan conditional exports terisolasi atau wrapper seragam:
```json
{
  "exports": {
    "import": "./dist/esm/index.js",
    "require": "./dist/cjs/index.cjs"
  }
}
```

### Kesalahan 3: Tidak Mengisolasi Scope Saat Mengubah Nama Variabel AST
*Pola Salah*: Mengganti `node.name` pada simpul `Identifier` tanpa memeriksa apakah simpul tersebut adalah deklarasi variabel atau referensi bebas (*free variable*):
```javascript
// SALAH: Mengubah semua teks identifier 'data' menjadi 'transformedData'
Identifier(path) {
  if (path.node.name === 'data') {
    path.node.name = 'transformedData'; // Merusak properti objek { data: 1 } dan variabel lokal lain
  }
}
```
*Solusi*: Gunakan API Scope Binding Babel untuk merename secara akurat:
```javascript
// BENAR: Menggunakan Babel Scope API
Identifier(path) {
  if (path.isBindingIdentifier() && path.node.name === 'data') {
    path.scope.rename('data', 'transformedData'); // Mengubah deklarasi DAN seluruh referensi terkait secara semantik aman
  }
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Idempotensi Visitor AST**: Seluruh manipulasi AST harus bersifat idempotent. Memproses kode sumber dua kali berturut-turut harus menghasilkan struktur AST yang identik tanpa efek samping liar.
2. **Explicit File Extensions pada Node.js ESM**: Dalam kode native ESM server-side, selalu tuliskan ekstensi file secara eksplisit (`import './service.js'`, BUKAN `import './service'`). Ini meniadakan latency *file-system guessing* (`fs.stat`) yang memperlambat startup runtime.
3. **Immutability pada Token Impor**: Perlakukan semua modul yang diimpor sebagai objek immutable. Jika status global modul harus dimutasi, sediakan event bus atau state manager terdesentralisasi daripada mengandalkan mutasi live-binding lintas modul.
4. **AST Visitor Guarding**: Selalu buat guard clauses di awal visitor handler. Verifikasi tipe node dan struktur parent sebelum melakukan operasi mutasi:
   ```javascript
   MemberExpression(path) {
     if (!path.get('object').isIdentifier({ name: 'process' })) return;
     if (!path.get('property').isIdentifier({ name: 'env' })) return;
     // Lakukan operasi dengan aman
   }
   ```
5. **Zero Side-Effects pada Modul Library**: Tambahkan `sideEffects: false` di `package.json` untuk modul utilitas library murni. Ini menginstruksikan modul linker kompilator (Rollup/Webpack) bahwa modul aman untuk di-prune (tree-shaken) secara agresif.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Single-Pass AST Traversal
Membuat beberapa pemanggilan `traverse(ast, ...)` secara berurutan akan melintasi jutaan node AST berulang kali ($O(K \times N)$).
*Optimasi*: Gabungkan multi-pass visitors menjadi satu visitor universal (*Single Pass Traversal*):

```javascript
// BURUK: Traversal 2 kali
traverse(ast, visitorA);
traverse(ast, visitorB);

// OPTIMAL: Traversal 1 kali (Mengurangi traversal overhead hingga 50%)
traverse(ast, traverseModule.visitors.merge([visitorA, visitorB]));
```

### 2. Module Graph Caching & Serialization
Hindari parsing ulang modul statis pihak ketiga (`node_modules`). Toolchain berkinerja tinggi mengimplementasikan hashing berbasis konten (misal: SHA-256 dari source code):
* Simpan representasi serialisasi AST dari modul yang tidak berubah di dalam buffer / LevelDB cache.
* Pada build berikutnya, lakukan komparasi hash; jika cocok, lewati fase Lexing & Parsing dan langsung inject AST terserialisasi ke dalam Memory Linker.

### 3. Worker Threads Parallel Graph Parsing
Fase 1 ESM (Construction/Parsing) bersifat murni I/O dan CPU bound tanpa memerlukan state global.
* Pecah daftar *Requested Modules* ke dalam kumpulan thread via Node.js `worker_threads`.
* Setiap worker thread mengeksekusi parsing Acorn ke raw source text dan mengembalikan daftar `ImportEntries` dan `ExportEntries`. Thread utama hanya bertugas merangkai graf topological bindings.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Prototype Pollution pada Modul AST
Ketika menerima representasi AST dalam bentuk JSON dari proses eksternal (misal: RPC antar proses micro-compiler), waspadai eksploitasi prototype injection:
* Penyerang menyisipkan properti `__proto__` atau `constructor.prototype` di dalam payload serialisasi AST.
* *Mitigasi*: Validasi skema AST menggunakan `Object.freeze` dan lakukan deep validation dengan skema ketat (misal via JSON Schema validator atau Zod) sebelum pohon AST disuntikkan ke traverser engine.

### 2. Dynamic Import URL Poisoning
Penggunaan variabel tak divalidasi pada ekspresi impor dinamis dapat dimanfaatkan penyerang untuk melakukan Local File Inclusion (LFI) atau Remote Module Injection:

```javascript
// RENTAN:
const modulePath = req.query.moduleName;
const mod = await import(modulePath); // Penyerang dapat mengoper 'data:text/javascript,...' atau path absolut sistem

// AMAN: Whitelisting & Sandboxed Resolver
const ALLOWED_MODULES = new Map([
  ['analytics', './plugins/analytics.js'],
  ['billing', './plugins/billing.js']
]);

if (!ALLOWED_MODULES.has(modulePath)) {
  throw new UnauthorizedModuleException('Akses modul tidak diizinkan');
}
const mod = await import(ALLOWED_MODULES.get(modulePath));
```

### 3. Isolasi Eksekusi VM (V8 Escape Prevention)
Modul `node:vm` bawaan Node.js **bukanlah sandbox keamanan mutlak** secara default. Kode di dalam context virtual dapat mengakses prototype luar melalui constructor fungsi jika tidak diisolasi secara cermat:
* Selalu oper objek global yang bersih (`Object.create(null)`).
* Putuskan rantai constructor function:
  ```javascript
  const context = vm.createContext(Object.create(null));
  // Cegah context lari ke process utama via Function constructor
  vm.runInContext('delete this.constructor.constructor', context);
  ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Pelacakan Native Node.js Module Linker
Node.js menyediakan environment variable internal untuk melacak mekanisme resolusi modul secara langsung:

```bash
# Debug resolusi dan parsing CJS & ESM Module Loader
NODE_DEBUG=module node app.js

# Melacak peringatan modul spesifik (misal: siklus dependensi atau dual package)
node --trace-warnings --trace-uncaught app.js
```

### 2. Debugging Struktur AST secara Real-Time
Untuk memeriksa secara visual hierarki AST saat menulis visitor transformator, buat helper logging terstruktur berikut:

```javascript
export function inspectAstNode(path) {
  console.log(`[AST Path Debug]`);
  console.log(`Type:       ${path.node.type}`);
  console.log(`Parent:     ${path.parent?.type}`);
  console.log(`Scope:      Block '${path.scope.block.type}', UID: ${path.scope.uid}`);
  console.log(`Loc:        Line ${path.node.loc?.start.line}:${path.node.loc?.start.column}`);
  console.log(`Code Chunk: ${generateModule.default(path.node).code}`);
  console.log('--------------------------------------------------');
}
```

Gunakan [ASTExplorer.net](https://astexplorer.net/) untuk melakukan inspeksi visual interaktif struktur node ESTree vs Babel AST secara berdampingan.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### ESM Lifecycle Cheatsheet
1. **Construction**: Ambil text -> Tokenize -> Parse AST -> Bangun `SourceTextModule` -> Simpan di Module Map.
2. **Instantiation**: Alokasikan memori untuk live bindings -> Tautkan `export` identifier ke `import` identifier (Topological DFS). Eksekusi kode = 0%.
3. **Evaluation**: Eksekusi bytecode aktual -> Isi slot memori -> Selesaikan Top-Level Promises. Eksekusi bottom-up (daun ke root).

### ESTree / AST Core Node Types

| Node Type | Representasi Sintaksis JavaScript |
| :--- | :--- |
| `ImportDeclaration` | `import { x } from 'mod'` |
| `ImportSpecifier` | Penunjuk token `{ x }` di dalam deklarasi impor |
| `ImportDefaultSpecifier` | Penunjuk token `x` pada `import x from 'mod'` |
| `ExportNamedDeclaration`| `export const a = 1;` atau `export { a }` |
| `ExportDefaultDeclaration` | `export default function() {}` |
| `ImportExpression` | Pemanggilan modul dinamis: `import(path)` |
| `CallExpression` | Pemanggilan fungsi umum: `foo()` |
| `Identifier` | Nama variabel, fungsi, atau parameter (misal: `myVar`) |
| `MemberExpression` | Akses properti objek: `object.property` |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan.

### Bagian A: Basic Knowledge

**Q1. Pada siklus hidup ESM, kapan pemetaan memori untuk "live bindings" dibentuk?**
- A. Saat kompilasi source code ke bytecode oleh TurboFan.
- B. Pada Fase 2 (Instantiation / Linking), sebelum kode dieksekusi.
- C. Pada Fase 3 (Evaluation), bersamaan dengan evaluasi baris pertama file entry.
- D. Hanya saat fungsi `require()` dipanggil oleh V8 runtime.
*Jawaban & Penjelasan*: **B**. Pada fase Instantiation, memory records untuk live bindings dibentuk dan ditautkan tanpa mengeksekusi bytecode.

**Q2. Mengapa mutasi langsung terhadap imported binding (misal: `import { x } from './a'; x = 10;`) menghasilkan TypeError?**
- A. Karena Babel secara otomatis menyisipkan instruksi `Object.freeze()` ke semua file.
- B. Karena spesifikasi ECMAScript menyatakan bahwa import binding bersifat read-only pointer view.
- C. Karena variabel yang diimpor selalu dikonversi menjadi tipe data `const` primitif secara implisit.
- D. Karena modul belum selesai melalui fase Evaluation.
*Jawaban & Penjelasan*: **B**. Spesifikasi resmi ECMAScript mengatur bahwa import identifier bertindak sebagai read-only alias terhadap environment record modul target.

**Q3. Tipe AST node manakah yang merepresentasikan sintaks dynamic import `import('./plugin.js')`?**
- A. `ImportDeclaration`
- B. `DynamicImportStatement`
- C. `ImportExpression`
- D. `CallExpression` dengan specifier flag
*Jawaban & Penjelasan*: **C**. Berdasarkan spesifikasi ESTree modern, `import(...)` direpresentasikan oleh node bertipe `ImportExpression`.

**Q4. Bagaimana perilaku CommonJS ketika terjadi cyclic dependency antara Module A dan Module B?**
- A. Runtime melemparkan error fatal `CyclicDependencyException`.
- B. Modul A akan menunggu Modul B hingga seluruh eksekusi kodenya selesai secara paralel.
- C. Modul yang siklik akan menerima objek `exports` parsial yang sudah dievaluasi sejauh titik siklus terjadi.
- D. CommonJS secara otomatis mengonversi kode tersebut menjadi live binding.
*Jawaban & Penjelasan*: **C**. CommonJS mengevaluasi berkas secara imperatif seketika; pemanggilan melingkar akan mengambil snapshot `module.exports` yang ada pada saat kejadian, seringkali berupa objek kosong `{}`.

**Q5. Apa kegunaan utama dari metode `path.skip()` saat melakukan traversal AST menggunakan Babel?**
- A. Menghapus simpul AST yang sedang dikunjungi dari memori.
- B. Menghentikan proses parsing leksikal terhadap file yang bersangkutan.
- C. Menginstruksikan traverser agar tidak mengunjungi anak-anak (*descendant nodes*) dari simpul yang sedang aktif.
- D. Melemparkan exception untuk keluar dari proses kompilasi.
*Jawaban & Penjelasan*: **C**. `path.skip()` mencegah traverser menyelami cabang turunan dari node saat ini, sangat penting guna menghindari rekursi tak berujung saat menyisipkan node baru bertipe sama.

---

### Bagian B: Intermediate & Advanced Scenarios

**Q6. Diberikan dua berkas ESM berikut:**
```javascript
// file: a.js
import { b } from './b.js';
export const a = 'ALPHA';
export function getB() { return b; }

// file: b.js
import { a, getB } from './a.js';
export const b = 'BETA';
console.log(a);
```
**Apa yang terjadi saat `node a.js` dieksekusi?**
- A. Mencetak `ALPHA`, program selesai dengan sukses.
- B. Mencetak `undefined`.
- C. Melemparkan `ReferenceError: Cannot access 'a' before initialization`.
- D. Terjadi infinite loop antara `a.js` dan `b.js`.
*Jawaban & Penjelasan*: **C**. Urutan evaluasi DFS menyebabkan daun dependensi (`b.js`) dievaluasi terlebih dahulu sebelum kode top-level `a.js` dijalankan. Mengakses `a` pada `b.js` melanggar Temporal Dead Zone (TDZ) karena variabel `a` belum terinisialisasi.

**Q7. Apa kelemahan utama melakukan isolasi kode menggunakan `vm.runInContext(code, context)` murni di Node.js untuk mengeksekusi plugin pihak ketiga yang tidak tepercaya?**
- A. Modul `vm` tidak mendukung sintaks modern JavaScript (ES2022+).
- B. Kode guest dapat keluar dari sandbox (*escape*) melalui rantai prototype constructor (misal `this.constructor.constructor('return process')()`).
- C. Modul `vm` secara drastis memperlambat kinerja V8 JIT compiler hingga 100 kali lipat.
- D. Modul `vm` tidak dapat mengeksekusi kode yang mengandung asynchronous Promises.
*Jawaban & Penjelasan*: **B**. Context `vm` bawaan Node.js bukan batasan keamanan hard-boundary; penyerang dapat menelusuri rantai prototipe objek standar menuju constructor host execution context.

**Q8. Dalam perancangan plugin bundler berbasis Babel AST, manakah pendekatan yang paling aman untuk mengubah nama variabel lokal `apiKey` menjadi `obfuscatedKey` tanpa merusak properti objek eksternal `{ apiKey: "secret" }`?**
- A. Menggunakan regex global replace `code.replace(/apiKey/g, 'obfuscatedKey')`.
- B. Memeriksa node bertipe `Identifier` dan memutasi `node.name` jika nilainya sama dengan 'apiKey'.
- C. Mencari binding deklarasi via `path.scope.getBinding('apiKey')` lalu memanggil `binding.scope.rename('apiKey', 'obfuscatedKey')`.
- D. Menghapus node `VariableDeclarator` dan menyisipkan identifier baru.
*Jawaban & Penjelasan*: **C**. Menggunakan Scope Binding API bawaan AST menjamin hanya deklarasi leksikal lokal dan referensi pemanggilnya yang diubah, tanpa menyentuh key properti pada objek literal.

**Q9. Fitur "Top-Level Await" pada modul ESM mengubah karakteristik evaluasi graf modul menjadi...**
- A. Multithreaded: Modul dievaluasi secara paralel di thread terpisah.
- B. Asynchronous Event-driven: Modul yang memiliki TLA dan modul-modul induk yang bergantung padanya dievaluasi sebagai microtask Promise.
- C. Non-deterministic: Urutan evaluasi dependensi daun tidak lagi mengikuti topological post-order.
- D. Synchronous Blocking: Menghentikan eksekusi seluruh thread Node.js hingga Promise selesai.
*Jawaban & Penjelasan*: **B**. TLA mengubah eksekusi pohon modul menjadi eksekusi berbasis Promise asinkron di mana node-node ancestor menunggu resolusi leaf node tanpa memblokir event-loop secara keseluruhan.

**Q10. Mengapa `sideEffects: false` pada `package.json` memfasilitasi algoritma tree-shaking pada Rollup/Webpack secara lebih optimal?**
- A. Menginstruksikan compiller untuk tidak mem-parse file ke dalam AST.
- B. Memberitahu bundler bahwa file modul tidak melakukan mutasi global window/scope, sehingga modul dapat dihapus seutuhnya jika ekspornya tidak di-referensikan.
- C. Memaksa compiler untuk mengekspor modul sebagai format CommonJS murni.
- D. Menjamin modul tidak memiliki siklus dependensi (cyclic dependency).
*Jawaban & Penjelasan*: **B**. Tanpa deklarasi `sideEffects: false`, bundler wajib mengikutsertakan modul utuh meski ekspornya tidak dipakai, karena bundler khawatir kode level teratas memodifikasi status global (misal polyfill atau mutasi prototipe).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Micro-Pack": In-Memory Dependency Graph Compiler & Static Dead-Code Pruner

### Deskripsi Spesifikasi Proyek:
Anda ditugaskan oleh tim Core Platform Infrastructure untuk membangun prototipe bundler sederhana tanpa bergantung pada Webpack, Vite, atau Rollup. Sistem harus membaca entry point, mengekstraksi seluruh dependensi graf, memvalidasi keamanan AST, dan menghasilkan satu berkas *Single-File Executable Sandbox*.

### Kebutuhan Teknis (Spesifikasi Wajib):
1. **Parser & Graph Traversal**:
   * Gunakan `@babel/parser` untuk membedah kode sumber.
   * Gunakan `@babel/traverse` untuk mencari simpul `ImportDeclaration`.
   * Bangun struktur data graf modul (*Directed Graph*) yang menyimpan ID modul, path absolut, AST, dan daftar dependensi modul anak.
2. **AST Static Pruning (Dead Code Elimination Sederhana)**:
   * Buat visitor yang memeriksa deklarasi fungsi lokal (`FunctionDeclaration`).
   * Jika nama fungsi tersebut tidak diekspor (`ExportNamedDeclaration`) DAN tidak pernah dipanggil di dalam file (`path.scope.getBinding(fnName).referenced === false`), hapus simpul fungsi tersebut dari AST (`path.remove()`).
3. **In-Memory Bundling & Specifier Linker**:
   * Transformasikan deklarasi impor statis menjadi struktur registri fungsi lokal berparameter runtime: `function(require, module, exports) { ... }`.
   * Sediakan custom runtime linker kecil di dalam bundle output yang mengevaluasi modul secara terurut (bottom-up execution).
4. **Output Verification**:
   * Output akhir harus berupa satu string JavaScript yang dapat dieksekusi langsung oleh Node.js tanpa dependensi pihak ketiga, mengeksekusi logika fungsional, dan membuktikan bahwa fungsi yang tidak terpakai telah dibuang dari berkas akhir.

### Verifikasi Keberhasilan:
* Uji coba bundler Anda terhadap 3 berkas mock:
  1. `math.js`: Memiliki fungsi `add(a, b)` (digunakan) dan `unusedSub(a, b)` (tidak digunakan dan tidak diekspor).
  2. `logger.js`: Memiliki fungsi `logResult(val)` yang mengimpor `add` dari `math.js`.
  3. `index.js`: Entry point yang mengimpor `logger.js`.
* Buktikan via inspeksi teks output bundle bahwa string `unusedSub` **tidak ditemukan sama sekali**, dan eksekusi bundle mencetak hasil kalkulasi matematis dengan benar.