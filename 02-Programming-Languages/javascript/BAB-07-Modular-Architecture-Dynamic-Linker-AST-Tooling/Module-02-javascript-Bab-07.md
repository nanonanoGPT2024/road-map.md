# BAB 07: Modular Architecture, Dynamic Linker & AST Tooling
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Membedah siklus hidup *ECMAScript Module* (ESM) di tingkat *runtime engine* (V8/SpiderMonkey): *Phase Construction*, *Instantiation* (*Live Bindings*), dan *Evaluation*.
- Mengimplementasikan *Dynamic Linker* dan *Custom Module Loader* kustom menggunakan API tingkat rendah (`node:vm`, `SourceTextModule`, dan `SyntheticModule`).
- Merancang dan mengeksekusi transformasi kode berbasis *Abstract Syntax Tree* (AST) menggunakan Babel/SWC Core API untuk keperluan *dead-code elimination*, instrumentasi performa, dan penegakan tata kelola arsitektur.
- Menguasai arsitektur *Module Federation* pada lingkungan *runtime hybrid* (Client & Server/Edge Node.js).
- Mengeliminasi *Dual Package Hazard* serta anomali sirkularitas modul pada sistem skala *enterprise*.

---

### 2. Prerequisite
Untuk mencerna materi ini secara optimal, Anda wajib menguasai:
- **Internal JavaScript Engine**: Memahami alokasi memori *Heap*, *Call Stack*, *Microtask Queue*, dan *Lexical Environment*.
- **Dasar Modularitas**: Perbedaan mendasar spesifikasi CommonJS (CJS) vs ECMAScript Modules (ESM).
- **Teori Kompilator Dasar**: Alur kerja *Lexer* (Tokenisasi), *Parser*, *AST Nodes*, dan *Code Generation*.
- **Node.js System Level**: Penggunaan *Buffer*, *Stream*, dan manipulasi *context execution* dasar.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Siklus Hidup ESM pada Engine V8 (*The 3-Phase Lifecycle*)
Berbeda dari CommonJS yang bersifat *synchronous*, *runtime-evaluated*, dan menyalin nilai (*value-copying*), ESM diproses secara asinkron dalam tiga fase terpisah dan deterministik:

```
[ Parse Entry Point ]
        |
        v
+-------------------------------------------------------------+
| 1. CONSTRUCTION (Fetching, Parsing, Module Record Creation) |
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| 2. INSTANTIATION (Allocate Memory Slots, Link Live Bindings)|
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| 3. EVALUATION (Execute Top-Level Code, Fill Memory Slots)   |
+-------------------------------------------------------------+
```

1. **Construction (Pencarian & Parsing)**:
   - Engine membaca berkas JavaScript mentah, menganalisis token sintaksis, dan mengubahnya menjadi `SourceTextModuleRecord`.
   - Engine menelusuri seluruh deklarasi `import` secara rekursif dan membentuk struktur pohon dependensi (*Module Graph*).
   - Seluruh modul pada graf ini dicatat dalam *Module Map* terpadu untuk memastikan modul yang sama tidak pernah diunduh atau diparsing ulang (*deduplication*).

2. **Instantiation (Penautan / Linking & Live Bindings)**:
   - Engine mengalokasikan ruang memori (*memory locations*) untuk semua *exported identifiers*.
   - Engine tidak mengeksekusi kode apa pun pada fase ini. Alih-alih mengeksekusi, engine menautkan pointer ekspor dan impor ke slot memori yang sama. Fenomena ini disebut **Live Bindings**: mutasi pada nilai ekspor oleh modul induk akan langsung terrefleksikan pada modul pengimpor tanpa mekanisme *polling* atau *re-fetching*.

3. **Evaluation (Eksekusi Kode)**:
   - Engine mengeksekusi kode baris demi baris pada *Call Stack*.
   - Nilai riil dihitung dan dimasukkan ke dalam slot memori yang telah dialokasikan pada fase *Instantiation*.
   - Modul yang mendukung *Top-Level Await* (TLA) akan mengubah proses evaluasi pohon modul menjadi rantai *Promise* asinkron.

#### 3.2 Dual Package Hazard & Interop Shim
Ketika ekosistem bertransisi dari CJS ke ESM, terjadi anomali kritis: **Dual Package Hazard**. 
Jika modul yang sama dimuat melalui rantai dependensi ganda (satu via `require()` dan satu via `import`), modul tersebut akan diinstansiasi **dua kali** ke dalam dua ruang memori berbeda:

```
[ Consumer Application ]
      |                 \
 (ESM import)      (CJS require)
      |                   \
      v                    v
[ Module Map (ESM) ]  [ require.cache (CJS) ]
      |                    |
      v                    v
[ Instance A (State 1) ] [ Instance B (State 2) ]  <-- STATE DIVERGENCE!
```
Hal ini menyebabkan rusaknya *singleton state*, kegagalan operator `instanceof`, dan kebocoran memori.

#### 3.3 Dynamic Linker & Runtime Module Loader
Pada skenario tingkat lanjut seperti *Micro-frontend* atau *Server-side Plugin Architecture*, kita tidak bisa mengandalkan berkas statis lokal. Kita membutuhkan *Dynamic Linker* yang mampu:
- Menangkap panggilan `import(specifier)` secara dinamis.
- Mengunduh artefak modul dari memori, jaringan (CDN), atau *database*.
- Melakukan kompilasi bytecode *in-memory*.
- Menyediakan *linking context* terisolasi menggunakan `node:vm`.

#### 3.4 AST Transformation Architecture
Transformasi kode (seperti Babel atau SWC) beroperasi pada struktur pohon berbasis spesifikasi ESTree. Alur kerja internal:
1. **Lexical Analysis**: Memecah aliran karakter teks menjadi aliran *Tokens*.
2. **Syntactic Analysis**: Mengubah token menjadi representasi pohon objek bersarang (*Abstract Syntax Tree*).
3. **AST Traversal (Visitor Pattern)**: Mengunjungi setiap simpul (*Node*), melakukan inspeksi tipe simpul (misalnya `ImportDeclaration`, `CallExpression`), dan memanipulasinya secara atomik.
4. **Code Generation**: Menghasilkan kembali kode JavaScript dari AST yang telah dimodifikasi beserta pemetaan baris/kolom (*Source Maps*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Static Bundling / Monolithic CJS) | Pendekatan Enterprise (Dynamic Linking, AST Governance, Pure ESM) |
| :--- | :--- | :--- |
| **Penyusunan Kode** | Seluruh kode digabungkan (*bundled*) menjadi satu atau beberapa artefak statis raksasa pada saat *build-time*. | Kode dipecah menjadi modul-modul independen yang dapat ditautkan secara *dynamic runtime* via *Module Federation* / *Import Maps*. |
| **Siklus Rilis** | Perubahan satu modul mikro memerlukan kompilasi ulang dan *re-deploy* aplikasi monolitik. | Rilis terdesentralisasi: Modul dinamis diperbarui di CDN/Storage; aplikasi induk memuat versi baru saat *runtime* tanpa *downtime*. |
| **Tata Kelola Kode** | Mengandalkan *linter* berbasis teks biasa yang sering meloloskan kebocoran arsitektur (*anti-pattern*). | Enkapsulasi berbasis AST: Memvalidasi, mengubah, atau memblokir dependensi ilegal langsung pada level kompilasi AST. |
| **Konsumsi Memori** | Duplikasi pustaka (CJS *copy-value* / *Dual Package Hazard*) memboroskan RAM server dan browser. | Penggunaan *Live Bindings* dan deduplikasi berbasis *Module Map* memangkas jejak memori secara radikal. |

---

### 5. How (Workflow Detail)

Alur eksekusi saat sebuah aplikasi enterprise memanggil dynamic import:

```
[ Application Code: import('tenantA/Widget') ]
                       |
                       v
         [ Dynamic Import Interceptor ]
                       |
        +--------------+--------------+
        |                             |
 (Specifier resolved           (Specifier eksternal /
    secara lokal)               Federated specifier)
        |                             |
        v                             v
[ Node.js/Browser Loader ]     [ Remote Module Resolver ]
        |                             |
        |                             v
        |                     [ Unduh Payload via Network/CDN ]
        |                             |
        |                             v
        |                     [ Validasi Integritas Hash & SRI ]
        |                             |
        |                             v
        |                     [ Parsing SourceText ke AST ]
        |                             |
        |                             v
        |                     [ AST Sanitizer & Policy Injection ]
        |                             |
        |                             v
        +------------> <--------------+
                       |
                       v
       [ Engine Instantiate: vm.SourceTextModule ]
                       |
                       v
    [ Link Phase: Hubungkan Export/Import References ]
                       |
                       v
           [ Evaluate Module Graph ]
                       |
                       v
       [ Return Module Namespace Object ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Cetak Buku vs Jaringan Perpustakaan Digital Berlangganan
- **CJS / Bundling Konvensional (Buku Fisik Dicetak Ulang)**: Setiap kali ada bab atau catatan kaki baru, seluruh buku harus dicetak ulang dari awal. Jika Anda mengutip bab dari buku lain, Anda memfotokopi halaman tersebut (*copy-value*). Jika buku aslinya direvisi, fotokopi Anda tetap usang.
- **ESM & Dynamic Linker (Koleksi Digital Berlangganan)**: Anda hanya menyimpan tautan hiperteks langsung ke lembar perpustakaan pusat (*Live Bindings*). Saat perpustakaan memperbarui kontennya, detik itu juga pembaca melihat nilai yang baru. Jika Anda butuh bab baru, modul itu diunduh secara asinkron di latar belakang (*Dynamic Linking*) hanya saat halaman dibuka.

#### Arsitektur V8 Module Linking Internal
```
MEMORY HEAP
+-------------------------------------------------------+
|  Module A (Exporter)                                  |
|  let counter = 10;                                    |
|                                                       |
|  [Slot: 0xDEADBEEF] --------> Holds Value: 10         |
|  export { counter };                                  |
+-------------------------------------------------------+
          ^
          | (Live Binding Pointer via Module Environment Record)
          |
+-------------------------------------------------------+
|  Module B (Consumer)                                  |
|  import { counter } from './moduleA.js';              |
|                                                       |
|  Identifier 'counter' points directly to: 0xDEADBEEF  |
|  (No local copy is made!)                             |
+-------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic ESM Linking Menggunakan `node:vm`
Contoh ini mendemonstrasikan bagaimana runtime V8 membentuk *Live Bindings* dan menautkan dua modul independen di dalam memori tanpa menyentuh *filesystem*.

```javascript
// dynamic-link-basic.mjs
import vm from 'node:vm';

// 1. Definisikan source code untuk modul dependen dan modul utama
const exporterCode = `
  export let telemetryCount = 0;
  export function increment() {
    telemetryCount++;
  }
`;

const consumerCode = `
  import { telemetryCount, increment } from 'metrics';
  
  export function runTest() {
    const before = telemetryCount;
    increment();
    const after = telemetryCount;
    return { before, after };
  }
`;

async function main() {
  // 2. Buat context eksekusi terisolasi
  const context = vm.createContext({ console });

  // 3. Inisialisasi SourceTextModule untuk Exporter
  const exporterModule = new vm.SourceTextModule(exporterCode, {
    identifier: 'metrics',
    context
  });

  // 4. Inisialisasi SourceTextModule untuk Consumer
  const consumerModule = new vm.SourceTextModule(consumerCode, {
    identifier: 'consumer',
    context
  });

  // 5. Definisikan Linker Callback untuk menjembatani specifier 'metrics'
  const linker = async (specifier, referencingModule) => {
    if (specifier === 'metrics') {
      return exporterModule;
    }
    throw new Error(`Modul tidak ditemukan: ${specifier}`);
  };

  // 6. Jalankan fase Linking
  await exporterModule.link(linker);
  await consumerModule.link(linker);

  // 7. Jalankan fase Evaluation
  await exporterModule.evaluate();
  await consumerModule.evaluate();

  // 8. Akses Namespace Object dari Consumer
  const { runTest } = consumerModule.namespace;
  const result = runTest();

  console.log('Hasil Eksekusi Live Binding:', result);
  // Output: { before: 0, after: 1 } -> Membuktikan live memory pointer bekerja!
}

main().catch(console.error);
```

#### 7.2 Practical Example: AST Transformer Plugin Berstandar Industri
Transformasi AST tingkat produksi untuk mengubah semua *Dynamic Imports* agar disematkan *cache-busting query*, validasi protokol aman, dan injeksi *performance marker*.

```javascript
// ast-optimizer-plugin.mjs
import { parse } from '@babel/parser';
import traversePkg from '@babel/traverse';
import generatePkg from '@babel/generator';
import * as t from '@babel/types';

// Handle CJS/ESM interop untuk Babel packages
const traverse = traversePkg.default || traversePkg;
const generate = generatePkg.default || generatePkg;

/**
 * Memproses source code JavaScript, menganalisis dan memodifikasi
 * Dynamic Import AST nodes secara deterministik.
 * 
 * @param {string} sourceCode - Kode mentah aplikasi
 * @param {string} buildHash - Hash rilis produksi untuk versioning
 * @returns {string} - Hasil transformasi kode
 */
export function transformDynamicImports(sourceCode, buildHash) {
  // 1. Parsing kode menjadi AST
  const ast = parse(sourceCode, {
    sourceType: 'module',
    plugins: ['topLevelAwait']
  });

  // 2. Linting & Modifikasi menggunakan Visitor Pattern
  traverse(ast, {
    Import(path) {
      // Pastikan node ini adalah CallExpression: import(arg)
      const parent = path.parentPath;
      if (!parent.isCallExpression() || parent.node.callee !== path.node) {
        return;
      }

      const argument = parent.node.arguments[0];

      // Skenario A: String Literal statis (misal: import('./module.js'))
      if (t.isStringLiteral(argument)) {
        const specifier = argument.value;

        // Blokir dependensi yang melanggar aturan keamanan arsitektur
        if (specifier.startsWith('http://')) {
          throw new Error(
            `[Security Violation] Dilarang mengimpor modul tidak terenkripsi: ${specifier}`
          );
        }

        // Tulis ulang URL dengan metadata build hash untuk cache bursting deterministik
        const updatedSpecifier = specifier.includes('?')
          ? `${specifier}&v=${buildHash}`
          : `${specifier}?v=${buildHash}`;

        parent.node.arguments[0] = t.stringLiteral(updatedSpecifier);

        // Bungkus import dengan Performance Timing API
        const instrumentedCall = t.callExpression(
          t.arrowFunctionExpression(
            [],
            t.blockStatement([
              t.variableDeclaration('const', [
                t.variableDeclarator(
                  t.identifier('__start'),
                  t.callExpression(
                    t.memberExpression(t.identifier('performance'), t.identifier('now')),
                    []
                  )
                )
              ]),
              t.returnStatement(
                t.callExpression(
                  t.memberExpression(parent.node, t.identifier('then')),
                  [
                    t.arrowFunctionExpression(
                      [t.identifier('mod')],
                      t.blockStatement([
                        t.variableDeclaration('const', [
                          t.variableDeclarator(
                            t.identifier('__duration'),
                            t.binaryExpression(
                              '-',
                              t.callExpression(
                                t.memberExpression(t.identifier('performance'), t.identifier('now')),
                                []
                              ),
                              t.identifier('__start')
                            )
                          )
                        ]),
                        t.expressionStatement(
                          t.callExpression(
                            t.memberExpression(t.identifier('console'), t.identifier('info')),
                            [
                              t.stringLiteral(`[DynamicLinker] Module loaded in:`),
                              t.identifier('__duration'),
                              t.stringLiteral('ms')
                            ]
                          )
                        ),
                        t.returnStatement(t.identifier('mod'))
                      ])
                    )
                  ]
                )
              )
            ])
          ),
          []
        );

        parent.replaceWith(instrumentedCall);
      }
    }
  });

  // 3. Regenerasi source code dari modified AST
  const output = generate(ast, {
    retainLines: false,
    compact: false
  }, sourceCode);

  return output.code;
}

// Simulasi Penggunaan di Pipeline Build Enterprise:
const inputCode = `
  async function loadPaymentEngine() {
    console.log("Memulai pemuatan modul...");
    const payment = await import('https://cdn.enterprise.com/modules/payment.js');
    return payment.init();
  }
`;

try {
  const transformed = transformDynamicImports(inputCode, 'v2.4.11-rc1');
  console.log("=== TRANSFORMED SOURCE CODE ===");
  console.log(transformed);
} catch (err) {
  console.error("Pipeline Kompilasi Gagal:", err.message);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Core Banking Global dengan lebih dari 60 tim independen yang mengelola portal keuangan berbasis mikro-frontend dan *Edge Node.js middleware*.

#### Problem Statement
- **Monolithic Build Jam**: Build pipeline memakan waktu 52 menit karena *bundler* harus membaca ulang jutaan berkas untuk memastikan referensi *tree-shaking*.
- **Runtime Conflict**: Tim Kartu Kredit memperbarui pustaka enkripsi internal ke format ESM murni, sedangkan Tim Tabungan masih menggunakan CJS. Terjadi *Dual Package Hazard*: dependensi `crypto-core` terinstansiasi dua kali, menyebabkan kegagalan pencocokan `instanceof SessionToken` saat transfer saldo lintas domain.
- **Downtime Risiko Tinggi**: Setiap pembaruan *widget* mikro membutuhkan rilis ulang container orkestrator utama.

#### Solusi Arsitektur
1. **Dynamic Remote Federation**: Mengubah seluruh *sub-domain* menjadi kontainer independen yang mengekspor modul berbasis ESM standar via Cloudflare Workers CDN.
2. **Custom Edge Dynamic Linker**: Membangun linker berbasis `node:vm` pada middleware Edge untuk memuat dan menautkan *Synthetic Modules* secara *on-demand*.
3. **AST Governance Pipeline**: Mengintegrasikan transformasi AST kustom pada *pre-commit* dan CI/CD pipeline yang secara otomatis membedah berkas biner/output untuk menjamin tidak ada duplikasi versi *singleton package*.

#### Arsitektur Sistem Baru
```
[ User Browser / API Gateway ]
              |
              v
[ Edge Dynamic Linker Node.js Engine ]
              |
     +--------+--------+
     |                 |
     v                 v
[ Micro-App:       [ Micro-App:
  Credit Card ]      Savings ]
     \                 /
      \               /
   (Dynamic Link via Shared Linker)
              |
              v
   [ Shared Engine Instance ]
    -> Crypto Engine Singleton
    -> Live Bindings Global State
```

#### Hasil Metrik Produksi
- **Waktu Build**: Turun 92% (dari 52 menit menjadi 4,1 menit) karena masing-masing domain membangun artefaknya secara terisolasi.
- **Incident Severity-1**: Berkurang menjadi 0 kasus terkait *instance mismatch* (*Dual Package Hazard* lenyap total berkat standarisasi ESM *runtime linking*).
- **Time to Market**: Tim produk dapat meluncurkan modul mikro baru secara independen dalam hitungan detik tanpa *restart* pod/server utama.

---

### 9. Trade-offs (Analisis Arsitektur)

Menerapkan *Dynamic Linker* dan *Runtime AST Manipulation* memerlukan kompromi rekayasa yang mendalam:

```
                  FLEKSIBILITAS RUNTIME
                          /\
                         /  \
                        /    \
                       /      \
                      /   *    \  <-- Dynamic Module Federation (Vite/Node Linker)
                     /          \
                    /            \
                   /______________\
LATENSI INITIAL                   PREDIKTIBILITAS SYSTEM
(Cold Start)                      (Build-Time Static Bundling)
```

| Parameter | Static Ahead-of-Time (AOT) Bundling | Dynamic Linker / Federated ESM |
| :--- | :--- | :--- |
| **Initial Latency (Cold Start)** | **Rendah**: Seluruh graf telah ditautkan dan dioptimasi dalam berkas monolitik sebelum eksekusi dimulai. | **Tinggi**: Terjadi *network overhead* dan *parsing overhead* saat modul dinamis pertama kali diunduh dan ditautkan di memori. |
| **Memory Consumption** | Menengah ke Tinggi: Kode yang belum digunakan mungkin ikut termuat ke memori karena *false-positive* pada *side-effects*. | **Sangat Rendah**: Memori hanya dialokasikan untuk modul yang benar-benar dieksekusi (*Lazy Instantiation*). |
| **Operational & Debugging** | **Mudah**: *Stack traces* mudah dipetakan kembali ke source code melalui berkas *source map* statis tunggal. | **Kompleks**: Modul yang ditautkan di memori (`node:vm`) membutuhkan pelacakan *source map in-memory* khusus; kegagalan *network* menyebabkan *runtime error*. |
| **Infrastruktur & Biaya CDN** | Biaya *storage* tinggi karena artefak besar harus disimpan ulang di setiap rilis. | **Hemat Biaya**: Artefak kecil terdistribusi; modifikasi modular hanya mengunggah artefak yang berubah (*differential deployments*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Temporal Dead Zone (TDZ) pada Sirkularitas ESM
- **Gejala**: Muncul pesan galat runtime: `ReferenceError: Cannot access 'X' before initialization`.
- **Akar Masalah**: Siklus impor antar modul ESM diperbolehkan, tetapi eksekusi nilai awal tetap bersifat sekuensial. Jika Modul A mengakses variabel dari Modul B saat Modul B masih berada dalam fase evaluasi, variabel tersebut masih berada dalam TDZ.
- **Penyelesaian**: Pisahkan deklarasi nilai global ke dalam modul atomik level ketiga (*Extract Dependency Pattern*), atau gunakan fungsi *getter/factory* untuk menunda akses variabel hingga fase evaluasi tuntas.

```javascript
// BAD: Circular Direct Access
// a.mjs:
import { b } from './b.mjs';
export const a = b + 1; // Jika b belum dievaluasi -> ReferenceError!

// GOOD: Function Encapsulation
// a.mjs:
import { getB } from './b.mjs';
export const getA = () => getB() + 1;
```

#### 2. Dual Package Hazard Akibat Resolusi Ekstensi
- **Gejala**: Objek tunggal (*singleton*) terinstansiasi ganda. Mutasi konfigurasi pada satu berkas tidak mempengaruhi bagian lain aplikasi.
- **Akar Masalah**: Konfigurasi `package.json` yang ceroboh pada bidang `exports`, di mana impor ESM mengarah ke berkas `./index.mjs` dan CJS mengarah ke `./index.cjs` yang memuat logika terduplikasi secara independen.
- **Penyelesaian**: Terapkan arsitektur *Wrapper Pattern*. Jadikan implementasi utama sepenuhnya berbasis CJS atau ESM, lalu sediakan berkas jembatan (*bridge shim*) tipis yang hanya mengekspos instance yang sama.

```json
// package.json yang benar
{
  "exports": {
    "import": {
      "types": "./dist/index.d.ts",
      "default": "./dist/esm/index.js"
    },
    "require": {
      "types": "./dist/index.d.ts",
      "default": "./dist/cjs-shim.cjs"
    }
  }
}
```

#### 3. Kebocoran Memori pada Dynamic Module Compilation
- **Gejala**: Penggunaan RAM server terus meningkat tajam hingga V8 mengalami *Fatal Process OOM (Out of Memory)*.
- **Akar Masalah**: Memanggil `new vm.SourceTextModule()` atau `new Function()` di dalam *request lifecycle* tanpa membersihkan cache atau tanpa mendaur ulang *Execution Context*. Setiap instansiasi menciptakan referensi permanen pada graf memori V8.
- **Penyelesaian**: Bangun mekanisme LRU (*Least Recently Used*) Cache untuk modul dinamis dan hapus referensi modul yang sudah kedaluwarsa secara eksplisit. Gunakan `node --inspect` dan ambil *Heap Snapshot* untuk mendeteksi simpul `ModuleEnvironmentRecord` yang menggantung.

---

### 11. Best Practices (Production Checklist)

- [ ] **Pemberian Tanda Bebas Efek Samping (`sideEffects: false`)**: Konfigurasikan `package.json` secara akurat agar *tree-shaking* pada bundler/linker dapat membuang simpul deklarasi yang tidak terpakai tanpa risiko menghapus inisialisasi kritis.
- [ ] **Validasi Subresource Integrity (SRI)**: Selalu verifikasi hash kriptografis (*SHA-256/384*) modul dinamis sebelum ditautkan ke dalam *runtime memory* untuk mencegah *Supply Chain Attacks*.
- [ ] **Deterministik Context Sandboxing**: Saat menggunakan `node:vm`, jangan pernah mengekspos objek global mentah (`globalThis`, `process`). Berikan proksi terbatas yang hanya memiliki akses ke primitif aman.
- [ ] **Pencegahan Barrel-File Anti-Pattern**: Hindari mengekspor ratusan modul mikro dari satu berkas `index.js`. Ini memaksa engine memparsing seluruh dependensi anak meskipun yang dipanggil hanya satu fungsi kecil.
- [ ] **Graceful Linker Failure Recovery**: Selalu bungkus logika *dynamic linker* dengan strategi *fallback*. Jika CDN remote gagal merespons, alihkan resolusi ke artefak lokal (*cached fallback*).

---

### 12. Hands-on Practice

Mari kita bangun arsitektur *Dynamic Linker* dengan kemampuan validasi AST terintegrasi. 
Direktori kerja yang wajib disiapkan: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install @babel/parser @babel/traverse @babel/generator @babel/types
```

#### File 1: `hands-on/m02/src/ast-guard.mjs`
Modul ini bertindak sebagai gerbang keamanan AST yang memvalidasi dan mentransformasi kode sebelum dieksekusi oleh engine.

```javascript
import { parse } from '@babel/parser';
import traversePkg from '@babel/traverse';
import generatePkg from '@babel/generator';

const traverse = traversePkg.default || traversePkg;
const generate = generatePkg.default || generatePkg;

export function sanitizeAndTransform(code, allowedModules = []) {
  const ast = parse(code, {
    sourceType: 'module'
  });

  traverse(ast, {
    ImportDeclaration(path) {
      const source = path.node.source.value;
      if (!allowedModules.includes(source)) {
        throw new Error(`[AST Guard] Akses impor dilarang: ${source}`);
      }
    },
    // Blokir akses destruktif ke debugger atau eval
    DebuggerStatement(path) {
      path.remove();
    },
    CallExpression(path) {
      if (path.node.callee.name === 'eval') {
        throw new Error('[AST Guard] Deteksi penggunaan eval() ilegal!');
      }
    }
  });

  return generate(ast, {}, code).code;
}
```

#### File 2: `hands-on/m02/src/runtime-linker.mjs`
Implementasi *Dynamic Linker Engine* menggunakan Node.js Native VM.

```javascript
import vm from 'node:vm';
import { sanitizeAndTransform } from './ast-guard.mjs';

export class EnterpriseDynamicLinker {
  constructor() {
    this.moduleRegistry = new Map();
    this.sandboxContext = vm.createContext({
      console: Object.freeze({
        log: (...args) => console.log('[Sandbox Log]:', ...args),
        error: (...args) => console.error('[Sandbox Error]:', ...args)
      })
    });
  }

  registerStaticModule(name, sourceCode) {
    const sanitized = sanitizeAndTransform(sourceCode, Array.from(this.moduleRegistry.keys()));
    const mod = new vm.SourceTextModule(sanitized, {
      identifier: name,
      context: this.sandboxContext
    });
    this.moduleRegistry.set(name, mod);
    return mod;
  }

  async linkAndExecute(entryCode) {
    const allowed = Array.from(this.moduleRegistry.keys());
    const sanitized = sanitizeAndTransform(entryCode, allowed);

    const entryModule = new vm.SourceTextModule(sanitized, {
      identifier: 'entry-point',
      context: this.sandboxContext
    });

    const linker = async (specifier) => {
      if (this.moduleRegistry.has(specifier)) {
        const targetMod = this.moduleRegistry.get(specifier);
        // Pastikan dependensi target ditautkan secara rekursif
        if (targetMod.status === 'unlinked') {
          await targetMod.link(linker);
        }
        return targetMod;
      }
      throw new Error(`[Dynamic Linker] Gagal me-resolve: ${specifier}`);
    };

    // 1. Link phase
    await entryModule.link(linker);

    // 2. Evaluate dependencies
    for (const [name, mod] of this.moduleRegistry) {
      if (mod.status === 'linked') {
        await mod.evaluate();
      }
    }

    // 3. Evaluate entry
    await entryModule.evaluate();

    return entryModule.namespace;
  }
}
```

#### File 3: `hands-on/m02/src/main.mjs`
Uji eksekusi dan validasi skenario pengujian.

```javascript
import { EnterpriseDynamicLinker } from './runtime-linker.mjs';

async function bootstrap() {
  const linker = new EnterpriseDynamicLinker();

  console.log('1. Mendaftarkan modul dependensi internal...');
  linker.registerStaticModule('auth-service', `
    export const token = "BEARER_PRODUCTION_SECRET_KEY";
    export function validateRole(role) {
      return role === 'ADMIN';
    }
  `);

  console.log('2. Mengeksekusi modul consumer yang valid...');
  const validEntry = `
    import { token, validateRole } from 'auth-service';
    
    export function run() {
      console.log("Token terdeteksi:", token);
      const isAllowed = validateRole('ADMIN');
      console.log("Otorisasi:", isAllowed);
      return isAllowed;
    }
  `;

  const validResult = await linker.linkAndExecute(validEntry);
  validResult.run();

  console.log('\n3. Menjalankan pengujian pelanggaran keamanan AST...');
  const maliciousEntry = `
    import { token } from 'auth-service';
    import fs from 'node:fs'; // Harusnya diblokir oleh AST Guard!
    
    export function exploit() {
      eval("console.log('exploit')");
    }
  `;

  try {
    await linker.linkAndExecute(maliciousEntry);
  } catch (err) {
    console.error('Eksploitasi berhasil digagalkan oleh arsitektur guard:', err.message);
  }
}

bootstrap().catch(console.error);
```

#### Jalankan Praktikum
```bash
node --experimental-vm-modules src/main.mjs
```
*(Catatan: Bendera `--experimental-vm-modules` wajib diikutsertakan karena `SourceTextModule` adalah API native tingkat rendah V8 yang mengekspos kapabilitas linker internal).*

---

### 13. Exercise

#### Level Easy
Buat sebuah fungsi berbasis Babel AST traversal yang mencari semua pemanggilan fungsi matematika `Math.pow(x, y)` dan mengubahnya menjadi operator eksponensial ES2016 yang setara: `x ** y`.

#### Level Medium
Buat skrip dynamic linker yang mampu mendeteksi secara programatis apakah terdapat dependensi sirkular sebelum tahap `link()` dipanggil pada `SourceTextModule`, dan laporkan rantai siklusnya dalam bentuk *Array* (misal: `['A.js', 'B.js', 'A.js']`).

#### Level Hard
Rancang sebuah *Custom Import Map Resolver* di Node.js menggunakan `node:vm` yang mendukung alias wildcard (seperti `"@features/*": "./src/features/*"`) dan resolusi fallback berlapis (*Cascading Fallbacks*): jika pemuatan modul dari server primer timeout dalam 250ms, linker harus otomatis beralih memuat dari server sekunder tanpa menggugurkan *module graph*.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Architect di perusahaan platform SaaS multi-tenant. Pengguna dapat mengunggah skrip kustom (modul berekstensi `.js`) yang dieksekusi di edge server Anda untuk memproses transaksi penjualan secara *real-time*.

**Objektif**:
Rancang arsitektur eksekusi modul *in-memory* yang:
1. Menerima string kode mentah dari penyewa (*tenant*).
2. Membedah dan mentransformasi AST untuk memastikan:
   - Tidak ada loop tak berujung (injeksikan *AST execution step counter* yang memutus proses jika melebihi 10.000 iterasi).
   - Mengubah deklarasi variabel global menjadi properti lokal terisolasi.
3. Melakukan dynamic linking modul tersebut ke API internal platform Anda (`PlatformDatabase`, `Logger`).
4. Eksekusi dilakukan menggunakan `node:vm` dengan memori terbatas (maksimal 32MB) dan *timeout* total 50ms.
5. Jika kode penyewa melempar *unhandled promise rejection*, engine tidak boleh merusak proses Node.js utama (*Process Isolation Guarantee*).

*Tuliskan arsitektur desain, diagram alur eksekusi, serta kode implementasi Proof-of-Concept (PoC) lengkap tanpa menggunakan framework pihak ketiga di luar `@babel/parser`, `@babel/traverse`, `@babel/generator`, dan pustaka bawaan `node:*`.*

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan mendasar antara perilaku nilai ekspor pada CommonJS vs ECMAScript Modules saat nilai tersebut diperbarui oleh modul pengekspor?
   - *Jawaban*: CommonJS menyalin nilai saat diimpor (*value-copying / snapshot*), sehingga perubahan berikutnya pada modul asal tidak mengubah nilai yang telah disalin. ESM menggunakan *Live Bindings* di mana pengimpor memegang referensi pointer memori yang sama ke lokasi data pengekspor, sehingga pembaruan nilai langsung terlihat seketika.

2. Sebutkan dan jelaskan secara singkat 3 fase utama siklus hidup pemuatan ESM pada JavaScript Engine!
   - *Jawaban*:
     1. **Construction**: Mengunduh, membaca, memparsing kode sumber menjadi AST, dan membentuk *Module Record*.
     2. **Instantiation**: Mengalokasikan slot memori untuk seluruh referensi ekspor dan impor serta menautkannya (*linking*).
     3. **Evaluation**: Mengeksekusi kode baris demi baris dan mengisi slot memori dengan nilai riil.

3. Mengapa `import(specifier)` dinamis mengembalikan objek bertipe `Promise`, sedangkan deklarasi `import ... from ...` statis tidak?
   - *Jawaban*: Karena pemanggilan dinamis dapat dipicu kapan saja saat runtime, mengharuskan engine untuk mengunduh, memparsing, dan menautkan modul baru secara asinkron di latar belakang tanpa memblokir *Main Thread* atau antrean *Event Loop*.

4. Apa peran dari *Visitor Pattern* dalam traversal AST?
   - *Jawaban*: Pola desain yang memungkinkan pemisahan antara algoritma navigasi struktur pohon hierarkis AST dengan logika inspeksi/manipulasi node. Setiap kali parser menemukan tipe simpul yang terdaftar di objek visitor, fungsi callback yang relevan akan dieksekusi secara otomatis.

5. Apa fungsi dari anotasi komentar `/*#__PURE__*/` bagi bundler dan alat kompilasi modern?
   - *Jawaban*: Memberikan petunjuk kepada minifier/bundler (seperti Rollup, Terser, atau Webpack) bahwa pemanggilan fungsi atau pembuatan objek tersebut tidak memiliki *side-effects*, sehingga dapat dihapus dengan aman (*dead-code elimination*) jika nilai kembaliannya tidak digunakan.

#### Pertanyaan Intermediate
6. Jelaskan bagaimana anomali *Dual Package Hazard* dapat merusak integritas evaluasi tipe data dengan operator `instanceof`!
   - *Jawaban*: Jika sebuah pustaka diinstansiasi secara simultan via ESM dan CJS, engine membuat dua modul terpisah dengan alokasi memori konstruktor class yang berbeda. Ketika instance yang dibuat oleh modul CJS dibandingkan menggunakan `instanceof` dengan referensi class dari modul ESM, engine mengevaluasi referensi memori purwarupa (*prototype identity*) yang berbeda, menghasilkan nilai `false` meskipun keduanya memiliki struktur class yang identik.

7. Mengapa penempatan *Top-Level Await* (TLA) pada modul anak dapat menyebabkan *bottleneck* performa pada arsitektur modular yang kompleks?
   - *Jawaban*: TLA menunda evaluasi modul pengekspor hingga *Promise* selesai (*settled*). Modul induk yang mengimpornya akan otomatis tertahan fase evaluasinya. Jika graf modular mengandung banyak rantai TLA yang saling bergantung secara serial (*waterfall*), waktu inisialisasi aplikasi dapat membengkak secara drastis karena memblokir rantai modul di atasnya.

8. Dalam transformasi AST, apa perbedaan mendasar antara node `Identifier` dan node `StringLiteral` pada ekspresi `import { a } from 'b'`?
   - *Jawaban*: `a` direpresentasikan sebagai `Identifier` karena merujuk pada nama variabel simbolik dalam ruang lingkup kode (*binding reference*), sedangkan `'b'` direpresentasikan sebagai `StringLiteral` karena merupakan nilai teks murni (*specifier URL/path*) yang digunakan oleh subsistem resolusi modul untuk menemukan berkas fisik.

9. Bagaimana V8 menangani masalah *Circular Dependency* pada ESM tanpa menyebabkan *Infinite Loop* saat proses resolving?
   - *Jawaban*: V8 menggunakan *Module Map* terpadu sebagai cache global. Saat modul mulai diproses pada fase *Construction*, entri modul tersebut langsung didaftarkan dengan status *unlinked/linking*. Ketika modul anak mencoba mengimpor kembali modul induk, V8 mendeteksi bahwa modul tersebut sudah ada di *Module Map*, memutus siklus rekursi, dan mengembalikan referensi record yang sama.

10. Apa kegunaan utama dari kelas `vm.SyntheticModule` yang disediakan oleh modul `node:vm`?
    - *Jawaban*: Untuk membuat modul ESM buatan secara langsung dari memori tanpa melalui proses parsing teks atau berkas JavaScript. Ini sangat penting untuk menjembatani interoperabilitas dengan CommonJS, data mentah JSON, atau mengimpor pustaka native C++ ke dalam graf modul ESM.

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah layanan finansial berbasis micro-frontend mengalami crash berkala di sisi klien: `Uncaught TypeError: Assignment to constant variable` yang terjadi pada modul transaksi saat jam sibuk. Investigasi menunjukkan masalah terjadi setelah salah satu modul eksternal menambahkan penulisan ulang pada nilai ekspor impor.
    - *Analisis Root Cause*: Developer salah memahami konsep *Live Bindings*. Pada ESM, variabel yang diimpor melalui sintaks `import { data } from 'mod'` bersifat *immutable binding* (hanya-baca) bagi modul yang mengonsumsinya. Setiap upaya menulis ulang secara langsung (`data = 123`) di modul pengimpor akan melempar TypeError oleh engine.
    - *Solusi Perbaikan*: Refactor modul pengekspor agar menyediakan fungsi mutator (misal: `setData(newValue)`), atau ubah data menjadi properti di dalam objek referensial yang diizinkan untuk dimutasi properti internalnya (*interior mutability*).

12. **Skenario 2**: Pada sistem SSR (*Server-Side Rendering*) berbasis Node.js, pemuatan plugin dinamis penyewa menggunakan `import()` menyebabkan performa server melorot secara kumulatif. Setelah berjalan 6 jam, waktu respons server melonjak dari 40ms menjadi 1800ms. Heap snapshot mengungkap adanya ratusan ribu objek `ModuleRecord` yang tidak terlepas dari memori.
    - *Analisis Root Cause*: Pemanggilan `import()` bawaan Node.js menyimpan seluruh modul yang pernah dimuat ke dalam *internal module map cache* runtime secara permanen selama proses masih hidup. Karena URL atau query parameter yang digunakan bersifat dinamis (misal: `import('./plugin.js?tenant=' + tenantId + '&time=' + Date.now())`), engine mencatat setiap URL unik sebagai modul baru yang berdiri sendiri, memicu kebocoran memori tak terkendali.
    - *Solusi Perbaikan*: Hentikan penggunaan dynamic import bawaan dengan query acak. Beralihlah ke arsitektur *Dynamic Linker* terisolasi berbasis `node:vm` yang dilengkapi penampung cache terbatas (*LRU Cache*), di mana context dan modul yang telah usang dibersihkan secara periodik dan referensinya dilepas dari objek global agar dapat didaur ulang oleh *Garbage Collector*.

13. **Skenario 3**: Tim DevOps mendapati bahwa sebuah library utilitas internal berukuran 12KB yang diimpor oleh aplikasi web modern menyebabkan bundle akhir membengkak sebesar 850KB. Library internal tersebut diekspor menggunakan konfigurasi bundler lama dengan target format CommonJS.
    - *Analisis Root Cause*: Algoritma *Tree-Shaking* bundler modern (seperti Webpack, Rollup, atau esbuild) sangat bergantung pada sifat analisis statis deklarasi `import/export` ESM murni. Ketika library dikompilasi ke format CJS (`module.exports = { ... }`), objek ekspor dievaluasi sebagai objek dinamis tunggal saat runtime. Bundler tidak dapat memverifikasi properti mana yang aman untuk dibuang secara statis, sehingga terpaksa memasukkan seluruh kode pustaka beserta seluruh dependensi transisinya ke dalam bundle final.
    - *Solusi Perbaikan*: Terbitkan library dalam format ESM murni (*Dual Package* jika CJS masih dibutuhkan) dengan menyertakan konfigurasi `"sideEffects": false` di `package.json`-nya. Pastikan bundler mengarah ke modul ESM yang mempertahankan deklarasi *named exports* atomik.

---

### 16. Summary

1. **Model Eksekusi ESM Bersifat Deterministik Tiga Tahap**: Pemisahan yang ketat antara *Construction*, *Instantiation*, dan *Evaluation* memungkinkan analisis statis menyeluruh, penautan graf rekursif yang aman, dan terciptanya mekanisme *Live Bindings* yang jauh lebih efisien dalam jejak memori dibandingkan pola penyalinan nilai CommonJS.
2. **Dynamic Linking Membuka Skalabilitas Enterprise**: Dengan memanfaatkan API runtime tingkat rendah seperti `node:vm` (`SourceTextModule` dan `SyntheticModule`), arsitektur perangkat lunak dapat melampaui batasan sistem file lokal, memungkinkan terwujudnya *Module Federation*, pembaruan modul mikro tanpa *downtime*, dan pemuatan kode berbasis jaringan terenkapsulasi.
3. **AST Adalah Fondasi Tata Kelola Kode Skala Masif**: Transformasi kode melalui AST bukan sekadar perkakas kompilasi, melainkan instrumen penegak arsitektur, keamanan (*sandboxing*), dan optimasi performa otomatis yang beroperasi langsung pada struktur bahasa pemrograman sebelum runtime dieksekusi.
4. **Pencegahan Anomali Modul Memerlukan Desain Disiplin**: Bahaya seperti *Dual Package Hazard*, *Temporal Dead Zone* pada ketergantungan sirkular, dan kebocoran memori modul dinamis hanya dapat diatasi secara tuntas jika arsitek perangkat lunak memahami secara presisi bagaimana JavaScript Engine mengelola modul di tingkat struktur internal memori heap.