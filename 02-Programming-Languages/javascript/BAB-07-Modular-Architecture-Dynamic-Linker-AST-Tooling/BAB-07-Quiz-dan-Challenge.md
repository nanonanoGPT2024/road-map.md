# BAB 07: Quiz, Challenge, & Knowledge Check
**Modular Architecture, Dynamic Linker & AST Tooling**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Evaluasi: ESM Live Bindings vs CommonJS Value Copy
Jelaskan perbedaan mendasar secara arsitektural dan alokasi memori antara mekanisme *Live Bindings* pada ECMAScript Modules (ESM) dan *Value Copy/Snapshot* pada CommonJS (CJS). Bagaimana engine JavaScript (seperti V8) mengelola referensi variabel yang diekspor ketika terjadi mutasi di modul asal setelah proses evaluasi selesai?

### Soal 1.2: Siklus Hidup Module Record pada ESM
Spesifikasi ECMAScript membagi pemrosesan modul ESM ke dalam tiga fase deterministik: *Construction (Parsing/Loading)*, *Instantiation (Linking)*, dan *Evaluation*. 
1. Uraikan apa yang terjadi pada *Module Record* dan *Module Environment Record* pada masing-masing fase.
2. Mengapa fase *Instantiation* dapat dilakukan secara sinkron dan rekursif menelusuri graf dependensi tanpa mengeksekusi satu baris pun kode JavaScript di dalam modul?

### Soal 1.3: Anatomi Compiler Frontend: CST vs. AST
Dalam rekayasa parser JavaScript:
1. Bedakan secara struktural antara *Concrete Syntax Tree* (Parse Tree) dan *Abstract Syntax Tree* (AST). 
2. Elemen sintaksis apa saja yang secara sengaja dieliminasi saat transformasi dari CST ke AST, dan mengapa eliminasi tersebut krusial bagi efisiensi algoritma traversal (*Visitor Pattern*) pada perkakas seperti Babel, SWC, atau ESLint?

### Soal 1.4: Mekanisme Runtime Dynamic Import
Secara spesifikasi, `import statement` bersifat statis dan dideklarasikan di *top-level*, sedangkan `import()` fungsional bersifat dinamis. 
1. Bagaimana runtime engine memperlakukan `import()` di level event loop dan microtask queue?
2. Mengapa dynamic import selalu mengembalikan instance `Promise<ModuleNamespaceObject>` bahkan jika modul target sudah berada di dalam memory module cache?

### Soal 1.5: Implikasi Top-Level Await (TLA) pada Graf Dependensi
Kehadiran Top-Level Await (TLA) mengubah sifat eksekusi graf dependensi ESM dari evaluasi sinkron *post-order traversal* menjadi asinkron.
1. Bagaimana TLA mempengaruhi urutan eksekusi modul tetangga (*sibling modules*) dan modul pemanggil (*ancestor modules*)?
2. Mekanisme internal apa yang digunakan engine untuk mencegah terjadinya *deadlock* saat dua modul yang saling bergantung tak langsung (indirect dependencies) sama-sama mengeksekusi operasi asinkron yang memblokir evaluasi graf?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Siklik: ESM TDZ vs CommonJS Partial Export
Diberikan skenario siklik di mana Modul A mengimpor Modul B, dan Modul B mengimpor Modul A.
1. Bagaimana V8 menangani *cyclic dependency* pada CJS sehingga tidak menghasilkan infinite recursion, dan mengapa hal ini kerap menghasilkan obyek parsial/kosong (`{}`)?
2. Bagaimana mekanisme penanganan siklik pada ESM melalui alokasi memori *uninitialized binding*, dan kondisi eksak apa yang memicu *ReferenceError* (*Temporal Dead Zone*) saat modul siklik tersebut dievaluasi?

### Soal 2.2: The Dual Package Hazard
Pada ekosistem Node.js modern yang mengizinkan *conditional exports* pada `package.json` (`"import"` dan `"require"`):
1. Jelaskan fenomena *Dual Package Hazard* dan dampak fatalnya terhadap pustaka yang mengandalkan status internal (*singleton state*) atau komparasi identitas via `instanceof`.
2. Bagaimana arsitektur *wrapper pattern* atau mitigasi struktural berbasis symlink/entrypoint dapat menjamin instance modul tetap tunggal terlepas dari cara modul tersebut dikonsumsi?

### Soal 2.3: Manipulasi AST: Scope Tracking & Variable Shadowing
Saat menulis transformasi kustom berbasis AST (misalnya plugin Babel atau SWC) untuk melakukan *injection* variabel baru:
1. Mengapa manipulasi langsung pada AST node (misalnya sekadar menambahkan `Identifier` baru) rentan menyebabkan *variable shadowing* dan *scope pollution*?
2. Bagaimana konsep *Scope Path traversal* dan *UID Identifier Generation* bekerja untuk menjamin *hygienic macro/transformation* pada lingkup leksikal yang kompleks?

### Soal 2.4: Runtime Dynamic Linker & Fallback pada Module Federation
Pada arsitektur Module Federation (Micro-Frontends):
1. Uraikan langkah-langkah *handshake* runtime yang dilakukan oleh Dynamic Linker host ketika menginisialisasi modul *remote* yang berbagi dependensi singleton (misalnya `react`).
2. Apa yang terjadi secara mendalam ketika host dan remote mendefinisikan batas versi semver yang saling menolak (*incompatible semver range*) pada shared configuration, dan bagaimana container runtime mencegah *multiple copies* tanpa memicu fatal crash?

### Soal 2.5: Dekonstruksi Source Map v3 & VLQ Encoding
Source Map memetakan kode terkompilasi/terbundel kembali ke AST asal:
1. Jelaskan struktur internal kolom `mappings` pada spesifikasi Source Map v3 dan bagaimana skema segmentasi 1, 4, atau 5 field bekerja (`[generatedColumn, sourceIndex, originalLine, originalColumn, nameIndex]`).
2. Mengapa format Base64 VLQ (Variable-Length Quantity) dipilih untuk serialisasi data mapping tersebut, dan bagaimana pergeseran offset dihitung secara relatif (*delta-encoding*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Production Outage Akibat Barrel Export & Broken Tree-Shaking
Sebuah aplikasi web enterprise skala besar mengalami degradasi performa drastis setelah pembaruan arsitektur monorepo. Ukuran bundle vendor melonjak dari 450 KB menjadi 8.2 MB. Tim menemukan bahwa seluruh modul internal diakses melalui sebuah barrel file tunggal (`index.ts` yang me-re-export ribuan modul). Meskipun bundler (Webpack/Rollup) telah dikonfigurasi dengan mode produksi dan *tree-shaking* aktif, seluruh kode dari ratusan modul yang tidak pernah dipanggil tetap masuk ke dalam bundle akhir.

```javascript
// packages/core/src/index.ts
export * from './components/Button';
export * from './components/HeavyDataGrid'; // Mengimpor engine chart 5MB
export * from './utils/date';
// ... 400 export lainnya

// apps/dashboard/src/App.ts
import { dateUtils } from '@enterprise/core';
console.log(dateUtils.format(new Date()));
```

**Tugas Diagnostik & Solusi:**
1. Analisis bagaimana keberadaan *module-level side effects* (misalnya eksekusi fungsi di top-level scope modul yang diekspor) melumpuhkan kemampuan Static Analysis pada AST bundler untuk melakukan Dead Code Elimination (DCE).
2. Bagaimana Anda memanfaatkan field `"sideEffects"` pada `package.json` dan transformasi AST via compiler plugin untuk memaksa bundler memotong dependensi graf yang tidak terpakai?
3. Rancang strategi re-arsitektur modular untuk mengeliminasi ketergantungan fatal pada barrel files tanpa merusak developer experience (DX).

---

### Skenario B: Deadlock dan Unhandled Rejection pada Dynamic Lazy-Loading Berantai
Sebuah platform analitik modular memuat modul dashboard pihak ketiga secara dinamis menggunakan runtime `import()`. Modul-modul ini memanfaatkan Top-Level Await untuk melakukan *schema validation* dan fetching metadata konfigurasi dari server sebelum mengekspor komponen mereka. 

Di bawah beban jaringan tinggi dengan *packet loss* parsial, sistem mengalami kondisi *freeze*: UI menampilkan loading state tanpa henti, tidak ada log error pada konsol browser, dan Promise dari dynamic import tidak pernah resolve maupun reject.

```javascript
// Remote Widget: dynamic-widget.js
const schema = await fetch('/api/v1/schema').then(r => r.json()); // Network hang
export const config = parseSchema(schema);
export default function Widget() { /* ... */ }

// Host Application: loader.js
async function loadComponent(name) {
  try {
    const module = await import(`./widgets/${name}.js`);
    return module.default;
  } catch (err) {
    showFallbackUI(err); // Tidak pernah terpanggil saat network hang
  }
}
```

**Tugas Diagnostik & Solusi:**
1. Mengapa evaluasi Top-Level Await pada grafik dependensi modul dapat memblokir eksekusi modul induk tanpa memicu mekanisme *catch block* standar jika koneksi tertahan (*stalled*) tanpa timeout eksplisit?
2. Bedah mekanisme *Module Evaluation State* di runtime engine. Apa status modul tersebut (`kEvaluating`, `kEvaluated`, atau `kErrored`) ketika dependency promise menggantung?
3. Implementasikan sebuah arsitektur Dynamic Linker Wrapper dengan *AbortController*, race conditions protection, dan timeout barrier yang dapat membatalkan evaluasi dynamic import serta membersihkan graf memori yang terisolasi.

---

### Skenario C: Architectural Trade-off: Compile-time AST Transformation vs Runtime Plugin Architecture
Perusahaan Anda sedang membangun platform visualisasi data terdistribusi yang mendukung ratusan ekstensi pihak ketiga. Tim terbagi menjadi dua fraksi arsitektur:
- **Fraksi A:** Mengusulkan sistem berbasis *Static AST Transformation* (menggunakan SWC/Babel plugin saat build-time) yang mengompilasi semua ekstensi langsung ke dalam single hyper-optimized binary/bundle.
- **Fraksi B:** Mengusulkan sistem berbasis *Dynamic Runtime Linker* (menggunakan dynamic imports native ESM + import-maps di browser/runtime) yang memuat ekstensi secara terisolasi saat dibutuhkan (*on-demand*).

**Tugas Evaluasi & Desain:**
1. Susun matriks komparasi teknis yang mendalam antara kedua pendekatan tersebut, mencakup:
   - *Cold-start latency & Memory footprint*
   - *Security boundary & Sandboxing (eval execution hazards)*
   - *Cache invalidation mechanics (CI/CD deployments)*
   - *Debuggability & Stack trace fidelity*
2. Jika Anda harus memilih arsitektur hibrida untuk sistem skala enterprise tersebut, bagaimana Anda memetakan batas arsitektur (*architectural boundary*) antara mana yang harus diselesaikan pada fase AST compile-time dan mana yang dialokasikan ke Dynamic Linker runtime?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Micro-Bundler & Dynamic Linker Berbasis AST

#### Deskripsi Masalah
Sebagai Principal Engineer, Anda dilarang bergantung pada bundler industri (Webpack, Vite, Rollup) untuk memahami cara kerja fundamental integrasi sistem. Anda ditantang untuk membangun sebuah **Micro-Bundler & AST-Driven Static Linker** dari nol menggunakan Node.js dan library parser level rendah (`@babel/parser`, `@babel/traverse`, `@babel/generator` atau `@swc/core`).

#### Persyaratan Fungsional (Requirements)
1. **Dependency Graph Resolution:**
   - Menerima file entry point (misal: `entry.js`).
   - Parsing file ke AST, temukan seluruh deklarasi `import` statis.
   - Telusuri dependensi secara rekursif dan bangun struktur data Dependency Graph lengkap (menggunakan topological sort untuk mendeteksi siklik).
2. **AST Static Tree-Shaking Engine:**
   - Analisis dependensi tingkat *Identifier*: jika `moduleA` mengekspor `foo` dan `bar`, namun `entry.js` hanya mengimpor `foo`, hilangkan node AST untuk deklarasi `bar` dari modul hasil.
   - Hilangkan kode yang tidak memiliki efek samping (*side-effect free dead code*).
3. **Module Packaging & Synthetic Linker:**
   - Ubah modul-modul individual menjadi fungsi terisolasi dalam satu file bundel executable (*IIFE Bundle Wrapper*).
   - Implementasikan custom module runtime registry: fungsi `__custom_require__(moduleId)` yang mengelola eksekusi modul, instansiasi cache, dan resolusi referensi sirkular sederhana.
4. **Export Transpilation:**
   - Transformasikan sintaks ESM (`import`/`export`) ke dalam representasi yang kompatibel dengan runtime registry Anda tanpa menggunakan bundler eksternal.

#### Batasan Teknis (Constraints)
- Tidak boleh menggunakan Webpack, Rollup, Vite, ESBuild, atau Parcel sebagai dependency bundler.
- Hanya diizinkan menggunakan AST Parser, Traverser, dan Generator (misal: ekosistem Babel atau SWC).
- Bundle hasil kompilasi harus murni satu file vanilla JavaScript yang dapat dieksekusi langsung oleh Node.js (`node dist/bundle.js`) tanpa flags experimental dan menghasilkan output yang valid.

#### Expected Output
Diberikan input struktur file berikut:

```javascript
// src/math.js
export function add(a, b) { return a + b; }
export function unusedSubtract(a, b) { return a - b; }

// src/message.js
export const text = "Hasil Penjumlahan: ";

// src/index.js
import { add } from './math.js';
import { text } from './message.js';

console.log(text + add(10, 5));
```

Output kompilasi (`dist/bundle.js`) harus memuat:
1. Kode `unusedSubtract` **tereliminasi sepenuhnya** dari output (AST Dead Code Elimination).
2. Mekanisme module registry yang membungkus `math.js`, `message.js`, dan `index.js`.
3. Menjalankan `node dist/bundle.js` berhasil mencetak: `Hasil Penjumlahan: 15`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan deterministik antara arsitektur ESM (*static compilation*, *live bindings*, asynchronous evaluation) dan CommonJS (*runtime execution*, *value copying*, synchronous loading).
- [ ] Tiga fase pemrosesan modul ESM: *Construction*, *Instantiation*, dan *Evaluation*, beserta state transitions pada *Module Record*.
- [ ] Representasi data internal AST: Token stream, Nodes, Properties (`type`, `loc`, `scope`), Parent-Child relationships, dan implementasi Visitor Pattern.
- [ ] Algoritma penanganan dependensi siklik pada modul ESM (pemanfaatan Memory Location Linking) vs CommonJS (pemanfaatan Cache Objek Terisi Parsial).
- [ ] Dampak arsitektural Top-Level Await pada grafik dependensi sistem, termasuk potensi degradasi cascading waterfall dan runtime blocking.
- [ ] Cara kerja Import Maps dan Dynamic Linker pada Module Federation dalam menegosiasikan shared dependency singletons di runtime.
- [ ] Algoritma Tree-Shaking: Mengapa *LHS/RHS analysis*, *Pure Annotation* (`/*#__PURE__*/`), dan *Scope Analysis* esensial untuk mendeteksi *dead-code* tanpa merusak side-effects.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik integer spesifik dari setiap Token Type pada spesifikasi ESTree atau parser internal V8.
- [ ] Format biner eksak dan algoritma matematika kompresi Base64 VLQ pada Source Map v3 (cukup memahami peran struktural dan cara interpretasinya).
- [ ] Seluruh signature method spesifik dari package parser pihak ketiga (misalnya daftar lengkap visitor methods di `@babel/types`).
- [ ] Ratusan parameter konfigurasi bundler komersial tertentu (Webpack, SWC, Rollup) yang bersifat transien terhadap waktu.

### Saya harus bisa melakukan:
- [ ] Menavigasi, membedah, dan memodifikasi struktur data AST kompleks secara programatis menggunakan parser tools modern.
- [ ] Mendiagnosis dan memperbaiki *Circular Dependency TDZ Errors* pada basis kode modular skala besar.
- [ ] Merancang dan mengonfigurasi arsitektur modul monorepo modern yang bebas dari *Dual Package Hazard* dan *Barrel File Pollution*.
- [ ] Membangun custom compiler/linter plugin sederhana untuk mentransformasi kode sumber JavaScript pada tingkat AST.
- [ ] Menemukan dan menanggulangi memory leak serta unhandled loading state pada modul yang dimuat dinamis melalui `import()`.
- [ ] Mengonfigurasi arsitektur micro-frontend berbasis dynamic module federation dengan pembagian dependency yang deterministik dan aman secara semver.