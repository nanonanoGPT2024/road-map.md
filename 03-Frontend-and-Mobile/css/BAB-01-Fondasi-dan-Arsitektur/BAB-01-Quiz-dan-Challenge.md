# BAB 01: Quiz, Challenge, & Knowledge Check
**CSS Engine Internals, Parsing, dan Cascade Mathematics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Fault-Tolerant Parsing & Core Grammar
Berdasarkan spesifikasi *CSS Syntax Module Level 3*, mesin peramban (*browser engine*) menerapkan prinsip *error recovery* yang sangat agresif saat mengurai token CSS. Jelaskan mekanisme parser ketika mendeteksi token ilegal atau malformed declaration (misalnya: salah penulisan properti, unclosed strings, atau blok kurung kurawal yang tidak seimbang). Mengapa CSS engine tidak melempar eksepsi fatal (*throw error*) seperti parser JavaScript, dan bagaimana parser menentukan titik *resynchronization* untuk parsing rule berikutnya?

### Soal 1.2: Vektor Spesifisitas Bukan Bilangan Basis-10
Seringkali spesifisitas disederhanakan dalam bentuk angka seperti `0, 1, 0, 0` atau ditulis `100`. Jelaskan secara matematis mengapa representasi nilai tunggal berbasis 10 (atau basis desimal apa pun) adalah cacat arsitektur secara fundamental. Bagaimanakah peramban menyimpan dan membandingkan *specificity tuple* $(A, B, C)$ secara internal, dan apa konsekuensinya terhadap selector dengan ratusan *class selector* dibandingkan dengan satu *ID selector*?

### Soal 1.3: Enam Tahap Pemrosesan Nilai CSS (Value Processing Pipeline)
Sebuah deklarasi CSS melewati siklus komputasi yang ketat sebelum nilai piksel absolut dirender ke layar: *Declared Value*, *Cascaded Value*, *Specified Value*, *Computed Value*, *Used Value*, dan *Actual Value*. Uraikan transformasi nilai properti `width: calc(50% + 20px)` dan properti `font-size: 1.5em` di setiap tahap dari keenam fase tersebut. Pada tahap manakah *inheritance* dieksekusi?

### Soal 1.4: Evaluasi Selector: Mengapa Right-to-Left (R-to-L)?
Mesin render modern (seperti Blink dan Gecko) mengevaluasi selector majemuk (contoh: `.layout-container .sidebar ul li a`) dari kanan ke kiri (*Right-to-Left* / *Subject-to-Root*). Jelaskan rationale algoritma di balik keputusan desain ini. Hubungkan penjelasan Anda dengan struktur pohon DOM dan konsep *Candidate Element Filtering* untuk meminimalkan kompleksitas traversal.

### Soal 1.5: Matriks Urutan Cascade (The Cascade Sorting Algorithm)
Sebutkan urutan prioritas deterministik dalam *Cascade Sorting Algorithm* dari prioritas tertinggi ke terendah berdasarkan CSS Cascading and Inheritance Level 5. Mengapa aturan `!important` pada deklarasi *User-Agent* memiliki posisi yang berbeda secara dramatis dibandingkan dengan `!important` pada *Author Style Sheets*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Spesifisitas Dinamis pada `:is()`, `:where()`, dan `:has()`
Pseudo-class fungsional modern memperkenalkan komputasi spesifisitas dinamis. Analisis bagaimana browser engine menghitung spesifisitas untuk:
1. `:where(.nav, #primary-menu, [data-active="true"])`
2. `:is(.nav, #primary-menu, [data-active="true"])`
3. `article:has(> .featured:not([hidden]))`

Bagaimana engine mengevaluasi kompleksitas komputasi saat mengeksekusi `:has()` jika selector tersebut menargetkan ancestor yang sangat tinggi pada pohon DOM besar (DOM depth > 32)?

### Soal 2.2: Inversi Prioritas pada Cascade Layers (`@layer`) dan `!important`
Spesifikasi CSS `@layer` menetapkan bahwa layer yang didefinisikan terakhir (*last declared layer*) memiliki prioritas lebih tinggi untuk deklarasi normal. Namun, mekanisme ini berbalik (*inverted*) secara total ketika melibatkan deklarasi `!important`. Jelaskan arsitektur internal di balik pembalikan ini (*layer ordering inversion*). Sertakan tabel perbandingan prioritas untuk membuktikan mengapa arsitektur ini dirancang sedemikian rupa untuk melindungi konsistensi encapsulation.

### Soal 2.3: RuleSet Indexing dan Bloom Filter Matching pada Engine
Blink dan Gecko tidak memeriksa setiap CSS Rule terhadap setiap DOM Node secara linier ($O(N \times M)$). Sebaliknya, mereka memecah CSSOM ke dalam *RuleSet Buckets* dan menggunakan *Bloom Filter* atau *Fast Reject Filter*. Jelaskan bagaimana engine mengindeks RuleSet (berdasarkan ID, Class, Tag, dan Universal/Attributes) dan bagaimana *Bloom Filter* digunakan untuk mempercepat rejection pada ancestor selector tanpa harus melintasi rantai DOM secara penuh.

### Soal 2.4: Parser Blocking vs Script Execution Interlock
File CSS eksternal (`<link rel="stylesheet">`) dianggap sebagai sumber daya *render-blocking*. Namun, bagaimana interaksi internal antara CSSOM construction dengan *HTML Parser* dan *JavaScript Execution*? Jelaskan kondisi *interlock* spesifik di mana parser HTML terpaksa berhenti memproses token DOM ketika menghadapi script inline yang berada tepat setelah link CSS eksternal yang masih berstatus *pending download*.

### Soal 2.5: Siklus Hidup CSS Custom Properties (`var()`)
CSS Custom Properties tidak bertindak seperti variabel bahasa pemrograman biasa, melainkan seperti *dynamic token substitution*. Jelaskan mengapa properti yang mengandung `var(--custom-prop)` tidak dapat di-resolve pada fase parsing CSS awal dan harus ditunda hingga fase *Computed Value*. Apa yang terjadi jika terjadi *dependency cycle* (misal: `--a: var(--b); --b: var(--a);`) dan bagaimana fallback value dievaluasi berdasarkan status *invalid at computed-value time*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Production Bottleneck
**Konteks Insiden:** Sebuah platform web trading enterprise mengalami degradasi performa drastis (*severe frame drops* hingga < 15 FPS) setiap kali ada data streaming frekuensi tinggi (50 tick/detik) yang memperbarui status transaksi pada tabel interaktif berisi 8.000 baris DOM.

Hasil profiling via Chrome DevTools Performance panel menunjukkan:
*   Aktivitas utama didominasi oleh **Recalculate Style** (rata-rata 38ms per frame).
*   Metrik CSS Selector Stats menunjukkan selector berikut memiliki rasio *Match Attempts to Match Count* sebesar 1.200.000 : 8.000:
    ```css
    div.trading-grid > div[data-row] table tr:has(td.badge-negative) span:not([aria-hidden="true"]) {
      color: var(--loss-color, #e53e3e);
    }
    ```

**Pertanyaan Diagnostik:**
1. Bedah secara mekanistik mengapa selector tersebut menyebabkan lonjakan drastis pada waktu eksekusi *Recalculate Style* mesin render! Identifikasi titik kegagalan (*invalidation scope* dan *selector right-to-left scanning cost*).
2. Rancang strategi refaktorisasi arsitektur CSS tersebut untuk menurunkan waktu *Recalculate Style* menjadi < 2ms tanpa mengubah fungsionalitas UI, memanfaatkan indexing internal browser engine (*class-based targeting* dan eliminasi *cross-subtree mutation invalidation*).

---

### Skenario B: Cascade Integrity & Micro-Frontend Collision
**Konteks Insiden:** Sebuah portal SaaS enterprise memadukan tiga aplikasi *Micro-Frontend* (MFE-A, MFE-B, MFE-C) ke dalam satu *Shell Application*. MFE-A menggunakan Tailwind CSS via `@layer utilities`, MFE-B menggunakan framework warisan berbasis Bootstrap dengan ratusan `!important`, dan MFE-C menyuntikkan (*inject*) CSS-in-JS via runtime `<style>` injection di akhir `<head>`.

Tiba-tiba, dialog modal dari MFE-A mengalami kerusakan tata letak:
*   Ukuran tombol berubah acak tergantung urutan navigasi user antar rute (MFE-A dibuka duluan vs MFE-B dibuka duluan).
*   Rule resetting di Tailwind (`preflight`) menimpa komponen dropdown MFE-B.
*   Tim developer merespons dengan saling menaikkan spesifisitas menggunakan chaining ID dan hacking selector: `#app #root div.modal-body button.btn-primary.btn-primary.btn-primary`.

**Pertanyaan Diagnostik:**
1. Analisis akar masalah inkonsistensi rendering tersebut berdasarkan prinsip *Order of Appearance*, *Tree-scoped Styles*, dan ketiadaan *Layer Boundary Architecture*.
2. Buat skema arsitektur integrasi cascade berbasis `@layer` (Cascade Layers) yang komprehensif untuk menstandardisasi hierarki prioritas style ketiga MFE tersebut, sehingga konflik terselesaikan secara deterministik tanpa bergantung pada waktu injeksi tag `<style>` ataupun perang spesifisitas. Tuliskan blueprint deklarasi `@layer`-nya!

---

### Skenario C: CSS Custom Property Memory & Recalculation Explosion
**Konteks Insiden:** Tim arsitektur frontend mendesain sistem "Theming Dinamis" dengan menempatkan lebih dari 400 CSS Custom Properties pada node global:
```css
:root {
  --primary-100: #e0f2fe;
  /* ... 400 token warna dan skala layout ... */
  --card-padding: 16px;
}
```
Ketika pengguna berganti tema (Dark Mode/Light Mode), JavaScript menjalankan:
```javascript
document.documentElement.style.setProperty('--card-padding', '20px');
document.documentElement.setAttribute('data-theme', newTheme);
```
Meskipun hanya 5 komponen yang menggunakan properti `--card-padding`, pengujian menunjukkan bahwa browser menjalankan *full tree invalidation* (seluruh pohon DOM dari root ke 45.000 elemen terdampak *recalculate style*). 

**Pertanyaan Diagnostik:**
1. Mengapa mutasi CSS Custom Property di `:root` menyebabkan propagasi invalidasi gaya yang jauh lebih masif dibandingkan memutasi kelas biasa pada sub-tree? Jelaskan bagaimana *inheritance boundary* bekerja pada properti kustom.
2. Bagaimana Anda merestrukturisasi sistem theming ini menggunakan `@property` (CSS Properties and Values API) dan pembatasan *containment / scope* untuk memastikan browser engine dapat melakukan *localized recalculation* dan mengisolasi tree traversal?

---

## 4. Chapter Challenge

### Tantangan Praktis: Deterministic Cascade & Specificity Engine (TypeScript)

#### Problem Statement
Anda ditugaskan oleh tim Core Platform Infrastructure untuk membangun prototipe modul resolver CSS Engine headless mini bernama `DeterministicCascadeEngine`. Modul ini harus dapat mem-parsing array of rule deklaratif, menghitung vektor spesifisitas absolut, dan mengurutkan deklarasi secara deterministik mengikuti aturan resmi *CSS Cascading Level 5*.

#### Requirements
1. **Specificity Evaluator:**
   * Buat fungsi `calculateSpecificity(selector: string): [number, number, number]` yang menghitung:
     * $A$: ID selectors (`#id`).
     * $B$: Class selectors (`.class`), attribute selectors (`[attr]`), pseudo-classes (`:hover`, dll.).
     * $C$: Type selectors (`div`, `span`) dan pseudo-elements (`::before`, dll.).
   * Mendukung handling spesifisitas dinamis untuk pseudo-class `:is()`, `:not()`, dan `:where()`.
2. **Cascade Comparator:**
   * Buat fungsi pembanding `sortDeclarations(declarations: CSSDeclaration[]): CSSDeclaration[]` yang menyelesaikan konflik deklarasi berdasarkan matriks resmi:
     1. Origin & Importance (Normal vs `!important` dari User Agent, User, dan Author).
     2. Context (Normal context vs Shadow DOM).
     3. Cascade Layers (`@layer` priority array; ingat aturan inversi untuk `!important`!).
     4. Specificity Tuple.
     5. Order of Appearance (Indeks posisi deklarasi).
3. **Value Resolution Pipeline (Mini-Engine):**
   * Buat fungsi `resolveValue(declarations: CSSDeclaration[], property: string): string` yang mengembalikan deklarasi pemenang (*Cascaded Value*).

#### Constraints
* Implementasikan dalam bahasa **TypeScript** murni.
* Dilarang menggunakan *CSS Parser library* eksternal (PostCSS, CSSTree, dll). Gunakan RegEx minimal atau manual string tokenizer untuk ekstraksi selector.
* Modul harus mampu menangani inversi layer pada aturan `!important` secara tepat.

#### Data Model Template
```typescript
type CascadeOrigin = 'user-agent' | 'user' | 'author';

interface CSSDeclaration {
  id: string;
  selector: string;
  property: string;
  value: string;
  important: boolean;
  origin: CascadeOrigin;
  layer?: string; // Optional layer name (e.g., 'base', 'components', 'utilities')
  sourceOrder: number; // Incrementing integer indicating physical document order
}

interface EngineConfig {
  layerOrder: string[]; // e.g., ['base', 'components', 'utilities']
}
```

#### Expected Output
Program demonstrasi (test harness) yang menerima set input berikut:
* Rule 1: Author, Normal, Layer 'utilities', Selector `.p-4`, Property `padding: 16px`, Order 1
* Rule 2: Author, Normal, Layer 'base', Selector `#main-card`, Property `padding: 32px`, Order 2
* Rule 3: Author, Important, Layer 'base', Selector `.box`, Property `padding: 8px`, Order 3
* Rule 4: Author, Important, Layer 'utilities', Selector `.p-4`, Property `padding: 24px`, Order 4

Harus mengembalikan output resolusi pemenang:
* **Pemenang deklarasi normal:** Dipecahkan oleh *Layer Priority* (Utilities menang atas Base) atau *Specificity* tergantung struktur layer.
* **Pemenang deklarasi important:** Harus secara akurat mendemonstrasikan bahwa deklarasi `!important` pada layer **'base'** mengalahkan deklarasi `!important` pada layer **'utilities'** (Layer Inversion rule).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme *Tokenizer* dan *Parser state machine* CSS (karakterisasi token, sinkronisasi titik henti parsing pada error).
- [ ] Vektor spesifisitas absolut $3$-tuple $(A, B, C)$ dan aturan evaluasi pseudo-class `:is()`, `:where()`, `:not()`, dan `:has()`.
- [ ] 6 Fase *Value Processing Pipeline* (Declared, Cascaded, Specified, Computed, Used, Actual Value) serta kapan inheritance berlangsung.
- [ ] Alasan matematis dan arsitektural di balik pemilihan arah matching *Right-to-Left* (R-to-L).
- [ ] Algoritma penyusunan Cascade: Origin & Importance, Shadow Tree context, Cascade Layers, Specificity, dan Order of Appearance.
- [ ] Mekanisme pembalikan urutan prioritas (*inversion*) pada Cascade Layers (`@layer`) saat flag `!important` aktif.
- [ ] Pola kerja peramban mengindeks CSSOM ke dalam RuleSet buckets untuk optimasi query DOM.
- [ ] Hubungan kritis antara blocking CSS, interupsi HTML Parser, dan eksekusi Script.

### Saya tidak perlu menghafal:
- [ ] Seluruh nilai bawaan (*default styles*) dari User-Agent Stylesheet vendor peramban spesifik.
- [ ] Rincian kode assembly atau C++ internal implementasi Blink/Gecko RuleProcessor.
- [ ] Angka Unicode presisi untuk karakter escape hexadecimal CSS (cukup pahami konsep parsing escape sequence).

### Saya harus bisa melakukan:
- [ ] Melakukan isolasi dan profiling bottleneck performa pada fase *Recalculate Style* menggunakan Chrome DevTools Performance Profiler & CSS Selector Stats.
- [ ] Merancang arsitektur CSS berskala enterprise bebas *specificity wars* menggunakan Cascade Layers (`@layer`).
- [ ] Menulis selector berperforma tinggi dengan meminimalkan non-indexed matching dan menghindari expensive invalidation chains.
- [ ] Mengonstruksi integrasi CSS multi-framework (Tailwind, CSS-in-JS, Legacy) tanpa kebocoran style menggunakan Layer Boundary.
- [ ] Men-debug kalkulasi nilai CSS properti (mengidentifikasi perbedaan *computed value* vs *used value* pada layout dinamis).