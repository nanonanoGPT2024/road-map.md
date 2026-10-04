# BAB 07: Quiz, Challenge, & Knowledge Check
**Testing Strategies & Quality Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Paradigma: Testing Pyramid vs. Testing Trophy pada Design System**
   Jelaskan mengapa pendekatan *Testing Pyramid* konvensional (yang menekankan dominasi *unit testing* terisolasi) kerap gagal memberikan jaminan kualitas yang optimal pada sebuah *Design System*, dan mengapa *Testing Trophy* (Kent C. Dodds) yang berpusat pada *Integration* dan *Visual Regression* dianggap lebih representatif. Uraikan argumen Anda dari sudut pandang *return on investment* (ROI) pengujian komponen antarmuka murni (*stateless UI components*).

2. **Diferensiasi Mekanisme: Visual Regression vs. DOM Snapshot Testing**
   Banyak tim keliru menganggap *Jest DOM Snapshot Testing* (yang menyimpan struktur serialisasi HTML/JSON) dapat menggantikan *Pixel-based Visual Regression Testing*. Analisis secara teknis kelemahan fatal *DOM snapshotting* dalam mendeteksi regresi visual riil (seperti CSS *overflow*, *z-index collision*, *font rasterization*, atau kesalahan *cascading*), serta jelaskan kapan *DOM snapshotting* masih relevan digunakan.

3. **Limitasi Pengujian Aksesibilitas Otomatis (a11y)**
   Mesin audit aksesibilitas terautomasi seperti `axe-core` atau `lighthouse` umumnya hanya mampu mendeteksi sekitar 30% hingga 40% dari total potensi pelanggaran WCAG 2.1/2.2 AA. Jelaskan faktor-faktor fundamental yang menyebabkan defisit deteksi ini, serta kategorikan jenis-jenis defek aksesibilitas yang *mustahil* divalidasi tanpa pengujian manual atau *assistive technology emulation* (misalnya pembaca layar / *screen reader*).

4. **Karakteristik Determinisme dalam Pengujian Antarmuka**
   Apa yang dimaksud dengan *Deterministic Rendering* dalam eksekusi pengujian komponen UI? Identifikasi 4 (empat) faktor nondeterministik (*side effects*) yang paling sering memicu kondisi *flaky tests* pada pipeline visual/integrasi, serta bagaimana strategi isolasi yang baku untuk menanganinya pada level *test runner*.

5. **Component API Contract Testing & Breaking Changes**
   Dalam konteks pemeliharaan *library* komponen yang dikonsumsi oleh puluhan tim produk, bagaimana strategi pengujian memverifikasi kontrak API komponen (tipe Props, Slots/Children, Custom Events, dan CSS Variables token)? Jelaskan perbedaan validasi kontrak pada level kompilasi statis (AST / TypeScript Compiler API) versus level *runtime assertion*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Root-Cause Analysis Antialiasing & Subpixel Rendering pada Multi-OS Headless Runner**
   Sebuah *baseline snapshot* visual yang dibuat pada lingkungan macOS lokal (Apple Silicon) selalu menghasilkan *pixel diff failure* (rata-rata 1.2% - 3.5% *mismatch*) ketika dieksekusi di dalam container Linux Docker (CI/CD GitHub Actions / GitLab CI), meskipun ukuran viewport, resolusi, dan versi browser Chromium identik. Bedah mekanisme internal *font rasterization* (FreeType vs. DirectWrite vs. CoreText), akselerasi perangkat keras GPU, dan subpixel rendering yang menyebabkan anomali ini, serta rumuskan arsitektur pipeline untuk mengatasinya secara permanen.

2. **Mekanisme Sintesis Event: `fireEvent` vs. `userEvent` pada Custom Component**
   Pada pengujian komponen kompleks seperti `MultiSelectCombobox` yang mengimplementasikan ARIA 1.2 pattern, jelaskan perbedaan fundamental cara kerja `@testing-library/react` (`fireEvent`) dengan `@testing-library/user-event`. Mengapa penggunaan `fireEvent` kerap meloloskan bug yang sebenarnya memblokir pengguna nyata (misalnya event bubbling, pointer-events cancellation, *focus-trap*, dan siklus penekanan tombol keyboard riil)?

3. **Optimasi Alokasi Resource & Concurrency pada Visual Runner Skala Besar**
   Jika sebuah Design System memiliki 200 komponen dengan total 1.500 *stories* (Storybook) yang harus diuji melintasi 4 *breakpoints* (Mobile, Tablet, Desktop, Wide) dan 2 *color schemes* (Light/Dark)—menghasilkan 12.000 kombinasi tangkapan visual—eksekusi Playwright/Puppeteer secara naif memicu kebocoran memori (*memory leak* / OOM crash) dan waktu tunggu hingga 60 menit. Rancang arsitektur eksekusi pengujian paralel yang mengoptimalkan *browser context reuse*, *page pooling*, dan alokasi resource CPU/RAM di lingkungan CI terbatas.

4. **Debugging Hydration Mismatch & Asynchronous Tokens pada SSR/RSC Test Harness**
   Komponen `ThemeProvider` mendistribusikan token desain menggunakan kombinasi *CSS Custom Properties* dan injeksi runtime via React Context. Saat diuji dalam test environment yang mensimulasikan Server-Side Rendering (Next.js App Router / SSR), terjadi *hydration error* intermiten yang hanya muncul pada mode *headless test*, bukan di browser nyata. Jelaskan langkah diagnostik sistematis untuk melacak apakah kegagalan ini berakar dari *microtask queue timing*, inkonsistensi eksekusi *layout effect* (`useLayoutEffect` vs. `useEffect`), atau *CSS-in-JS style injection order*.

5. **State Synchronization Flakiness pada Virtualized Infinite-Scroll Component**
   Sebuah komponen `DataTable` dengan kemampuan *virtual scrolling* (hanya me-render baris DOM yang terlihat di viewport) gagal secara berkala (*flaky* pada tingkat 15%) saat diuji menggunakan Playwright dengan assertion: `expect(page.getByRole('row', { name: 'Item 500' })).toBeVisible()`. Telusuri bagaimana *scroll throttling/debouncing*, siklus *requestAnimationFrame*, dan latensi virtualisasi DOM menciptakan *race condition* terhadap engine selector Playwright. Tuliskan koreksi kode implementasi assertion-nya secara deterministik.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck CI/CD Pipeline & Flaky Test Paralysis
* **Kasus:** Design System monorepo skala enterprise (digunakan oleh 45 micro-frontend tim) mengalami krisis produktivitas. Pipeline CI/CD membutuhkan waktu 58 menit untuk menyelesaikan satu lintasan validasi PR. Tingkat kegagalan *false-positive* visual regression mencapai 28%, yang mayoritas disebabkan oleh:
  1. Web font kustom (`Inter` & `Fira Code`) yang terlambat dirender (FOUT/FOIT).
  2. Animasi mikro (CSS transitions pada modal dan dropdown) yang status penyelesaiannya (*transitionend*) bervariasi beberapa milidetik antar-runner runner CI.
  3. Logika rendering dinamis berbasis tanggal (komponen `DatePicker` selalu menampilkan tanggal hari ini).
  *Developer velocity* anjlok drastis; tim mulai secara rutin menggunakan flag `--skip-tests` untuk bypass merge.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana arsitektur solusi rekayasa Anda untuk menstabilkan dan men-determinasi lingkungan pengujian (font, animasi, waktu) tanpa merusak kode sumber murni komponen?
  2. Rancang strategi pemotongan waktu eksekusi CI hingga < 10 menit menggunakan teknik *Smart Test Selection* / *Change Impact Analysis* (menguji hanya komponen yang terdampak oleh perubahan file pada Git diff/AST graph).

### Skenario B: Race Condition & Keyboard Navigation Breakdown pada Floating UI
* **Kasus:** Pasca merilis versi minor komponen `DropdownMenu` (yang menggunakan Floating UI / Popper.js dan React Portals), tim produk melaporkan insiden kritis: pengguna dengan keyboard/screen-reader terjebak dalam *infinite focus trap* atau kehilangan fokus sepenuhnya ke `document.body` saat menavigasi sub-menu bertingkat (*nested flyout*). Pengujian unit yang ada (berbasis Jest + JSDOM) lulus 100% dengan status *green*, namun pengujian manual di browser produksi menunjukkan kegagalan total navigasi keyboard.
* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa JSDOM gagal total dalam mereplikasi dan mendeteksi bug navigasi keyboard, tab index, dan kalkulasi koordinat geometris pada komponen *floating portal* ini?
  2. Rancang pengujian *End-to-End Component Test* menggunakan Playwright/Cypress Component Testing yang secara spesifik menguji perpindahan fokus, validasi atribut `aria-activedescendant` atau `aria-expanded`, serta timing transisi fokus antar-portal tanpa meninggalkan celah *race condition*.

### Skenario C: Arsitektur Transisi Style Engine & Cross-Framework Regression
* **Kasus:** Organisasi Anda memutuskan untuk memigrasikan fondasi CSS Design System dari runtime CSS-in-JS (misalnya Emotion/Styled Components) ke Zero-Runtime CSS (Tailwind CSS v4 / Vanilla Extract) untuk memangkas *Total Blocking Time* (TBT) di aplikasi konsumen. Terdapat 95 komponen kompleks yang harus dimigrasi secara bertahap dalam kurun waktu 3 bulan. Target utamanya adalah menjamin *Zero Visual Regression* dan *Zero Accessibility Regression* bagi ribuan modul UI yang mengonsumsi Design System ini.
* **Pertanyaan Diagnostik & Solusi:**
  1. Rancang arsitektur pengujian komparatif (*A/B Differential Testing Harness*) yang mampu mengeksekusi kedua implementasi komponen (legacy vs. modern) secara berdampingan dalam viewport dan state interaksi yang identik untuk menghitung delta regresi.
  2. Bagaimana Anda memvalidasi bahwa migrasi ini tidak merusak kemampuan konsumsi antarmuka oleh framework wrapper lain (misalnya React wrapper vs. Vue wrapper vs. Web Components) dalam ekosistem monorepo?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Custom Visual & A11y Automated Quality Gate Engine

#### 1. Problem Statement
Sebagian besar tim Design System bergantung pada platform visual regression pihak ketiga berbasis cloud (SaaS) yang sangat mahal, atau menggunakan setup lokal yang *flaky* dan lambat. Anda ditugaskan untuk membangun sebuah **Core Quality Assurance Engine mandiri** berbasis Playwright Test Runner yang mengeksekusi audit Visual Regression (Pixel Diff) dan Automated Accessibility (via `axe-core`) secara terintegrasi, deterministik, dan dapat dijalankan secara seragam pada mesin lokal developer maupun Linux CI container.

#### 2. Requirements & Specification
Engine yang Anda bangun harus mencakup:
* **Deterministic Environment Setup:**
  * Injeksi CSS global saat test runner dijalankan untuk mematikan semua CSS transitions/animations (`* { transition: none !important; animation: none !important; }`).
  * Mekanisme sinkronisasi *Font Loading API* (`document.fonts.ready`) sebelum tangkapan layar diambil.
  * Mocking waktu/jam sistem pada browser context agar komponen berbasis kalender/waktu bersifat deterministik.
* **Dual-Axis Quality Gate Harness (Playwright Test Fixture):**
  * Buat custom fixture Playwright yang secara otomatis mengekstrak *story* dari Storybook/lokal komponen.
  * *Axis 1: Visual Comparison:* Tangkap screenshot per viewport matrix (Mobile: 375x667, Desktop: 1280x720) dengan ambang batas toleransi ketat (*pixel-match threshold* <= 0.05%).
  * *Axis 2: Accessibility Scan:* Jalankan `@axe-core/playwright` pada state komponen yang sama, pastikan aturan WCAG 2.1 Level A & AA terpenuhi (zero critical / zero serious violations).
* **CLI Reporter / Failure Artifacts:**
  * Jika terjadi kegagalan visual, buat visual diff image (Actual vs Expected vs Diff mask).
  * Jika terjadi pelanggaran a11y, cetak laporan terminal yang merinci node target selector HTML, ID aturan WCAG yang dilanggar, panduan remediasi, dan tautan dokumentasi resmi.

#### 3. Constraints
* Dilarang menggunakan tool SaaS berbayar (seperti Percy, Chromatic, Applitools).
* Pipeline harus berbasis TypeScript murni.
* Seluruh test harus berjalan di lingkungan headless browser Chromium dengan resolusi dan *Device Pixel Ratio* (DPR) yang dikunci secara deterministik (`deviceScaleFactor: 2`).

#### 4. Expected Output
1. File konfigurasi dan *custom fixture* TypeScript: `quality-gate.fixture.ts`.
2. Implementasi pengujian terintegrasi pada minimal satu komponen kompleks: `interactive-dialog.spec.ts` (menguji state: *closed*, *open*, *focused on destructive action*).
3. Kode script mocking determinisme lingkungan: `test-deterministic-setup.ts`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batas kapabilitas dan trade-off antara unit testing (JSDOM), component testing (Playwright/Cypress Component Test), dan visual regression testing.
- [ ] Anatomi kegagalan pengujian visual: font loading race conditions, anti-aliasing cross-OS, GPU software rendering vs. hardware rendering.
- [ ] Prinsip kerja Accessibility Tree (AOM) pada browser, bagaimana `axe-core` mengevaluasi DOM tree, serta limitasi evaluasi otomatisnya.
- [ ] Perbedaan pengiriman event sintetis (synthetic events) vs. raw OS input events dalam pengujian interaksi keyboard/mouse/touch.
- [ ] Strategi eksekusi pengujian deterministik: CSS animation disabling, fake timers/clocks, dynamic data virtualization synchronization.
- [ ] Konsep *Change Impact Analysis* (CIA) berbasis Git diff dan dependency graph monorepo untuk memangkas durasi testing pipeline.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor indeks aturan spesifikasi WCAG (misal: 1.4.3, 2.1.2) di luar kepala; rujuk dokumentasi W3C atau output rule ID axe-core.
- [ ] Sintaks konfigurasi spesifik dari berbagai platform visual SaaS proprietary (Percy, Chromatic, dll.).
- [ ] Algoritma internal pixel-by-pixel comparison (misal: algoritma exact pixelmatch math); manfaatkan library yang sudah teruji standar industri.

### Saya harus bisa melakukan:
- [ ] Membangun dan mengonfigurasi pipeline Visual Regression mandiri menggunakan Playwright/Puppeteer dengan zero-flakiness guarantee.
- [ ] Mengintegrasikan `@axe-core/playwright` ke dalam test lifecycle dan mengustomisasi violation rule sets sesuai standar kepatuhan enterprise.
- [ ] Mengisolasi komponen dari dependensi eksternal tak menentu (waktu, random generator, external web-fonts, animasi) pada saat pengujian dirender.
- [ ] Menulis integration test navigation keyboard yang kompleks (tab trapping, roving tabindex, ARIA state updates) pada komponen headless/accessible UI.
- [ ] Menganalisis dan men-debug memory leaks serta flakiness pada browser runner multi-threaded di CI/CD container.