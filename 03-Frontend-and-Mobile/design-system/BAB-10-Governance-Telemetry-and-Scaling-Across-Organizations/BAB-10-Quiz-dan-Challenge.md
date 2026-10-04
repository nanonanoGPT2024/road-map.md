# BAB 10: Quiz, Challenge, & Knowledge Check
**Governance, Telemetry, and Scaling Across Organizations**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Federated Governance vs. Centralized Core Team**
   Dalam skala organisasi *enterprise* (>100 insinyur, >10 lini produk), model tata kelola *Centralized* murni kerap mengalami *throughput bottleneck*, sementara model *Federated* murni berisiko memicu *design drift* dan fragmentasi arsitektur. Jelaskan analisis komparatif mendalam mengenai kedua model tata kelola ini, dan deskripsikan bagaimana model hibrida (*Federated with a Central Clearinghouse*) menyeimbangkan antara otonomi tim produk dan integritas sistem desain.

2. **Taksonomi Telemetri: Static AST Analysis vs. Runtime Telemetry**
   Evaluasi efektivitas pengukuran adopsi *design system* menggunakan dua pendekatan:
   * **Static Code Analysis** (misal: ekstraksi AST melalui *custom ESLint rules* atau *Babel/TypeScript compiler API*).
   * **Runtime Instrumentation** (misal: pelaporan berbasis *PerformanceObserver*, React `Profiler`, atau *custom mount hooks*).
   Jelaskan kelebihan, kekurangan, *margin of error* (false positive/negative), serta dampak performa (*overhead*) dari masing-masing pendekatan dalam lingkungan produksi.

3. **Anatomi SemVer pada Design System Multi-Platform**
   Berbeda dengan *utility library* biasa, *design system* mencakup antarmuka visual, token, dan perilaku aksesibilitas. Berikan definisi operasional yang presisi mengenai apa yang dikategorikan sebagai **Major (Breaking)**, **Minor**, dan **Patch** pada level:
   * Komponen UI (*props interface*, DOM structure, ARIA roles).
   * Design Tokens (perubahan nilai warna, penghapusan token, *aliasing* semantik).
   Mengapa perubahan DOM tree yang tampak sepele (misal: membungkus teks dengan `<span>` ekstra) dapat menjadi *breaking change* katastropik bagi aplikasi konsumen?

4. **Siklus Hidup RFC (Request for Comments) dan Gatekeeping Komponen**
   Rancang arsitektur alur kerja RFC untuk penambahan komponen baru atau perubahan arsitektural berskala besar pada *design system*. Tentukan kriteria ambang batas (*threshold criteria*) yang harus dipenuhi sebuah komponen sebelum diizinkan bermigrasi dari *local product codebase* (inkubasi) menuju *core design system package* (stabilitas sistemik).

5. **Mekanika Deprecations dan Sunsetting Strategy**
   Jelaskan tahapan eksekusi strategi *graceful deprecation* untuk sebuah komponen inti (*core component*) yang digunakan oleh ribuan *call sites*. Deskripsikan fase transisi dari *Soft Deprecation* (compile-time warning), *Hard Deprecation* (lint-error dengan opt-out sementara), hingga *Decommissioning* (penghapusan permanen paket). Bagaimana cara memitigasi *alert fatigue* pada tim pengembang produk?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Edge-Case Parsing AST untuk Analisis Adopsi Komponen**
   Ketika menganalisis repositori konsumen menggunakan AST parser, developer sering kali melakukan *re-aliasing*, *wrapping*, atau *dynamic composition*, contohnya:
   ```tsx
   import { Button as CoreButton } from '@enterprise/ds';
   const SubmitButton = (props) => <CoreButton {...props} variant="primary" />;
   const DynamicComponent = React.lazy(() => import('@enterprise/ds').then(m => ({ default: m.Modal })));
   ```
   Bagaimana Anda merancang algoritma penelusuran AST (menggunakan TypeScript Compiler API atau Babel Traverse) yang mampu melacak penggunaan riil komponen ini tanpa menghasilkan bias *false negative* atau *double-counting*?

2. **Mitigasi Runtime Telemetry Overhead dan Performance Bottlenecks**
   Sebuah tim mengimplementasikan telemetri *runtime* dengan mengirimkan *payload* analitik setiap kali komponen atomik (`<Button>`, `<Input>`, `<Badge>`) di-*mount*. Dalam aplikasi berarsitektur *infinite scroll* atau tabel data padat, terjadi *frame drops* (jank) yang parah dan *network saturation*. Rancang arsitektur telemetri *runtime* sisi klien yang menggunakan teknik *batching*, *sampling rates*, dan API asynchronous non-blocking (seperti `requestIdleCallback` atau `navigator.sendBeacon`) untuk mengeliminasi dampak negatif terhadap *Main Thread* dan *Core Web Vitals* (khususnya INP).

3. **Resolusi Versioning Deadlock pada Multi-Repo Micro-Frontends**
   Dalam ekosistem Micro-Frontend (MFE) yang menggunakan Module Federation, aplikasi *Shell* memuat Design System `v2.4.0`, sementara Remote MFE A memerlukan `v3.1.0` (breaking visual and API changes), dan Remote MFE B mengonsumsi `v2.1.0`. Analisis bagaimana runtime CSS collisions, singleton context conflicts (seperti `ThemeProvider`), dan *React synthetic events bubbling* dapat rusak dalam skenario ini. Bagaimana arsitektur *scoped token namespaces* dan *federation shared dependencies configuration* memecahkan masalah ini?

4. **Automated Codemod Architecture dengan JSCodeshift**
   Komponen `<Modal>` mengubah API-nya dari:
   ```tsx
   // Old API
   <Modal isOpen={open} onClose={handleClose} title="Warning">Body content</Modal>
   ```
   Menjadi arsitektur *Compound Component*:
   ```tsx
   // New API
   <Modal.Root open={open} onOpenChange={handleClose}>
     <Modal.Header>Warning</Modal.Header>
     <Modal.Body>Body content</Modal.Body>
   </Modal.Root>
   ```
   Tuliskan logika transformasi AST tingkat arsitektur menggunakan *JSCodeshift*. Jelaskan bagaimana skrip Anda mendeteksi impor yang valid, memvalidasi keberadaan *children*, memetakan *props*, dan mempertahankan *inline comments* serta *code formatting* yang ada pada kode konsumen.

5. **Token Drift Prevention dalam Pipeline GitOps Multi-Platform**
   Dalam pipeline CI/CD yang mengintegrasikan Figma Tokens via Tokens Studio/Figma API ke repositori kode:
   * Desainer mengubah token warna `$semantic.color.background.critical` di Figma.
   * Style Dictionary mengompilasi token menjadi CSS custom properties, SCSS vars, iOS Swift, dan Android Compose tokens.
   Bagaimana Anda merancang *automated drift-detection pipeline* yang mampu mendeteksi *breaking changes* pada token semantik (misalnya penghapusan token atau perubahan tipe data variabel), memvalidasi kontras warna WCAG AAA secara otomatis di level PR, dan mencegah token hasil *export* merusak *downstream builds* lintas platform?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Silent Production Crash & Token Transformation Desynchronization
Perusahaan FinTech berskala global mengoperasikan platform web (React) dan aplikasi *native* (React Native/iOS). Sistem desain mereka mengandalkan repositori token sentral. Pada rilis `v4.2.0`, tim inti mengganti nama token semantik `$color.surface.elevation-0` menjadi `$color.surface.canvas.base` dan menambahkan sistem *fallback* pada paket web. 

Namun, skrip transformasi platform Android/iOS berbasis *Style Dictionary* mengalami kegagalan parsing diam-diam (*silent failure*) karena kesalahan penanganan tipe data JSON referensial. Skrip menghasilkan nilai `undefined` pada output XML/Swift tanpa menghentikan proses *build* CI/CD. 

Ketika aplikasi *mobile* dirilis ke *store*, lebih dari 45% pengguna mengalami *fatal null-pointer exception* saat membuka halaman beranda, dan tim web melaporkan beberapa modul MFE mengalami *styling regression* di mana latar belakang komponen menjadi transparan.

* **Pertanyaan Diagnostik:**
  1. Identifikasi *single point of failure* (SPOF) pada pipeline integrasi dan pengujian token lintas platform di atas.
  2. Rancang struktur verifikasi skema token (*contract testing*) berbasis JSON Schema/Zod dalam pipeline CI/CD untuk memastikan integritas data sebelum proses kompilasi multi-target dijalankan.
  3. Bagaimana strategi arsitektur *fallback token* (pada level CSS custom properties dan native bridges) untuk memastikan bahwa aplikasi tidak pernah mengalami *crash* atau *blank screen* meskipun token bernilai `undefined`?

---

### Skenario B: "Phantom Adoption" dan Rogue CSS Overrides
Dashboard telemetri statis *design system* di sebuah perusahaan e-commerce SaaS menunjukkan angka adopsi komponen yang spektakuler: **94% komponen UI di seluruh repositori frontend diimpor dari `@enterprise/core-ui`**. Namun, audit manual dari *Head of Experience Design* mengungkapkan bahwa antarmuka produksi tetap tampak tidak konsisten, terfragmentasi, dan sering melanggar pedoman *accessibility*.

Setelah dilakukan investigasi mendalam terhadap *codebase* tim-tim produk, tim arsitek menemukan fenomena **"Phantom Adoption"**:
1. Tim produk mengimpor komponen core, namun melakukan *hard-override* gaya visual menggunakan *scoped CSS Modules*, Tailwind utilities dengan operator `!important`, atau *deep descendant selectors* (`.ds-button > span { font-size: 8px !important; }`).
2. Komponen atomik dibungkus (*wrapper components*) sedemikian rupa sehingga *accessibility attributes* bawaan tertutup atau di-reset (`aria-hidden="true"` ditambahkan untuk membungkam pesan error).
3. Tim produk membuat "klon lokal" dari komponen kompleks (seperti DatePicker dan Datagrid) karena komponen inti dinilai terlalu kaku (*inflexible*).

* **Pertanyaan Diagnostik:**
  1. Mengapa metrik adopsi berbasis jumlah baris impor (`import { ... } from '@enterprise/core-ui'`) adalah sebuah *vanity metric* yang menyesatkan?
  2. Rancang sistem telemetri berbasis AST dan analisis CSS (misal: Stylelint custom plugin + PostCSS AST parser) yang mampu mengukur **"Styling Detraction Index"** (rasio antara komponen DS murni vs komponen yang di-override secara agresif).
  3. Dari perspektif tata kelola (*governance*), arsitektur komponen apa yang salah sehingga mendorong developer produk melakukan *hacking* visual melalui CSS override? Bagaimana Anda mengubah API kontrak komponen untuk mengakomodasi fleksibilitas tanpa mengorbankan kepatuhan desain?

---

### Skenario C: Monorepo Scale & Versioning Cascade Deadlock
Sebuah korporasi telekomunikasi memiliki monorepo raksasa (500+ paket, 40+ aplikasi produk) yang dikelola dengan Nx dan Changesets. Komponen inti Design System berada di direktori `packages/ui-core`. 

Ketika sebuah *patch fix* keamanan diterapkan pada komponen `<FormInput>`, skrip rilis otomatis memicu evaluasi graf ketergantungan (*dependency graph*). Akibat konfigurasi penataan versi yang mengunci *internal dependencies* secara ketat (`workspace:*` dengan pinning versi eksplisit), rilis patch ini memicu proses *rebuild* dan *re-test* terhadap 38 aplikasi produk sekaligus.

Hasilnya:
* 14 aplikasi produk gagal dalam tahap E2E testing (Playwright/Cypress) karena *visual regression tests* mendeteksi pergeseran piksel sebesar 1.5px pada batas input.
* Antrean CI/CD monorepo terblokir selama 16 jam, mencegah rilis darurat (*hotfix*) dari lini bisnis lain yang tidak terkait.
* Beberapa tim produk mulai memberontak dan meminta izin untuk memisahkan diri (*forking*) dari monorepo atau membuat komponen form independen.

* **Pertanyaan Diagnostik:**
  1. Lakukan audit arsitektural: apa kesalahan fundamental dalam strategi *dependency locking*, pengujian visual, dan arsitektur *release boundary* di monorepo tersebut?
  2. Rancang strategi pemisahan versi (*decoupled versioning*) menggunakan pola *Lerna/Changesets independent versioning* yang meminimalkan *blast radius* pembaruan paket core.
  3. Bagaimana Anda merancang *automated visual regression policy* di CI/CD yang mampu membedakan antara pergeseran piksel yang disengaja (*intentional design update*) dengan *true regression*, tanpa memblokir seluruh rantai pengiriman (*delivery pipeline*) organisasi?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Design System Telemetry & Governance Engine

#### Problem Statement
Organisasi Anda kekurangan visibilitas faktual mengenai bagaimana *Design System* digunakan di 50+ aplikasi *frontend*. Data adopsi saat ini hanya berbasis asumsi. Anda ditugaskan untuk membangun **Governance & Telemetry CLI Tool** mandiri yang mampu menganalisis repositori konsumen, menghitung skor adopsi teknis riil, mendeteksi *rogue overrides*, serta menyediakan *Codemod migrator* otomatis untuk memfasilitasi deprecation.

#### Requirements
1. **Engine Analisis Statis (AST Crawler):**
   * Bangun skrip Node.js/TypeScript menggunakan Babel Parser (`@babel/parser`, `@babel/traverse`) atau TypeScript Compiler API.
   * Mampu memindai direktori proyek target dan mendeteksi:
     * Seluruh impor dari package mock `@enterprise/ds`.
     * Menangani kasus *aliasing* (misal: `import { Button as CoreButton }`).
     * Menghitung total pemanggilan komponen (*call sites*), distribusi penggunaan varian props (misal: berapa kali `variant="primary"` vs `variant="danger"` digunakan).
2. **Override & Anti-Pattern Detection:**
   * Menganalisis keberadaan *props* terlarang seperti `style={{ ... }}` atau `className="override-..."` yang disematkan langsung pada komponen `@enterprise/ds`.
   * Mendeteksi pemanggilan selektor *hack* global berbasis CSS/SCSS (misal regex/PostCSS untuk mencari selektor yang menargetkan kelas internal `.eds-*` dengan `!important`).
3. **Automated Migration Engine (Codemod):**
   * Buat transformator *JSCodeshift* yang membaca kode sumber konsumen dan secara otomatis memigrasikan prop yang didepresiasi:
     * Ubah prop `isDestructive={true}` pada komponen `<Button>` menjadi `variant="danger"`.
     * Jika `isDestructive` bernilai false, hapus prop tersebut.
     * Pastikan perubahan tidak merusak komentar kode atau gaya indentasi file.
4. **Scoring & Reporting Matrix:**
   * Menghasilkan laporan berformat JSON dan tabel konsol terstruktur yang memuat:
     * **System Adoption Score (%)**: Persentase komponen UI yang menggunakan `@enterprise/ds` dibanding elemen HTML native (`<button>`, `<input>`, dll.).
     * **System Health Score (%)**: `(Adopsi Murni - Rogue Overrides) / Total Pemanggilan * 100`.
     * Daftar file pelanggar (*actionable debt log*).

#### Constraints
* Tidak boleh mengeksekusi kode klien (*zero runtime execution / purely static analysis*).
* Waktu pemindaian (*parsing time*) harus efisien: mampu memproses minimal 500 file sumber TypeScript/TSX dalam waktu < 10 detik.
* Arsitektur kode CLI harus modular: modul pemindai (*parser*), modul penilai (*metric calculator*), dan modul transformasi (*codemod*) harus terisolasi rapi.

#### Expected Deliverables
1. File `telemetry-engine.ts`: Skrip parser AST yang mengekstraksi data pemanggilan komponen dan prop.
2. File `codemod-v2-migration.ts`: Transformator JSCodeshift untuk migrasi otomatis prop `isDestructive`.
3. File `report-generator.ts`: Modul kalkulator metrik dan formatter output terminal.
4. File `README.md` mini: Instruksi eksekusi CLI, spesifikasi skema JSON yang dihasilkan, dan batasan teknis dari skrip tersebut.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan teknis Anda dalam mengelola dan menskalakan *Design System* di tingkat enterprise.

### Saya harus memahami:
- [ ] Arsitektur tata kelola *Centralized*, *Federated*, dan *Hybrid*, serta kalkulasi *Return on Investment* (ROI) dari sistem desain skala enterprise.
- [ ] Perbedaan fundamental, batas toleransi, dan reliabilitas antara *Static Code Telemetry* (AST) vs. *Runtime Profiling Telemetry*.
- [ ] Aturan SemVer yang ketat ketika diterapkan pada *visual styles*, tokens, DOM hierarchy, dan spesifikasi ARIA, bukan hanya pada API JavaScript.
- [ ] Siklus hidup RFC: dari proposal konsep, evaluasi komite, masa inkubasi lokal, hingga stabilisasi global.
- [ ] Metodologi *deprecation*: tahapan *grace period*, *runtime warning throttles*, linter deprecation rules, dan *codemod-assisted migration*.
- [ ] Mekanisme propagasi token dari platform desain (Figma) hingga artefak biner multi-platform via Style Dictionary dan GitOps CI/CD.
- [ ] Dampak arsitektur Micro-Frontend terhadap isolasi gaya, CSS variable scoping, dan *singleton dependencies collision*.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama fungsi visitor internal AST Babel/TypeScript (cukup memahami konsep *AST Node types*, *traversal patterns*, dan struktur *visitor*).
- [ ] Syntax spesifik dari konfigurasi Style Dictionary untuk platform yang tidak digunakan (cukup pahami konsep *Design Token Specification format*, *transforms*, dan *formatters*).
- [ ] Pola ekspresi reguler (Regex) kompleks untuk parsing file teks CSS mentah (AST traversal melalui PostCSS/Stylelint jauh lebih diutamakan daripada Regex).

### Saya harus bisa melakukan:
- [ ] Membangun *custom AST parser* menggunakan TypeScript Compiler API atau Babel untuk mengaudit penggunaan dependensi di seluruh organisasi.
- [ ] Menulis skrip automasi migrasi kode (*Codemod*) dengan JSCodeshift untuk mengubah antarmuka komponen yang mengalami *breaking change*.
- [ ] Mengonfigurasi arsitektur monorepo (misal: Nx, Turborepo, Changesets) yang mengisolasi siklus rilis dan membatasi *blast radius* dari pembaruan komponen core.
- [ ] Menerapkan *linter rules* khusus (ESLint/Stylelint custom plugins) yang secara aktif memblokir *rogue CSS overrides* dan anti-patterns di level *pre-commit* dan PR validation.
- [ ] Menghitung metrik performa telemetri (Adoption Rate, Detraction Index, Component Velocity) dan menyajikannya dalam format yang dapat dipahami oleh *engineering leads* maupun *executive stakeholders*.