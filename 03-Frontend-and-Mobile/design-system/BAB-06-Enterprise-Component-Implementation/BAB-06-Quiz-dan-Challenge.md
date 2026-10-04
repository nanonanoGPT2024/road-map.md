# BAB 06: Quiz, Challenge, & Knowledge Check
**Enterprise Component Implementation (React & Web Components)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Event Retargeting & Synthetic Event Bridge
Jelaskan secara mekanistik bagaimana *Event Retargeting* bekerja ketika sebuah `CustomEvent` di-dispatch dari dalam Shadow Root suatu Web Component (dengan mode `{ bubbles: true, composed: true }`) menuju React Synthetic Event System (React 17/18). Mengapa `event.target` pada React root listener bernilai berbeda dibandingkan dengan `event.composedPath()[0]`, dan apa implikasi arsitekturalnya terhadap implementasi event delegation pada custom design system?

### Soal 1.2: Headless UI vs Polymorphic Component Architecture
Bandingkan pola arsitektur **Headless Component** (state & logic abstraction, seperti React Aria atau Radix UI primitive) dengan **Polymorphic Component** (menggunakan prop `as` atau `asChild` via Radix Slot). Analisis trade-off keduanya dalam konteks:
1. *Bundle size cost* dan *runtime execution overhead*.
2. Kemudahan audit kepatuhan aksesibilitas (WAI-ARIA APG pattern compliance).
3. Kompleksitas penanganan TypeScript types (terutama *discriminated unions* dan *prop forwarding*).

### Soal 1.3: Atribut vs Properti pada Web Components
Dalam siklus hidup Custom Elements v1, jelaskan perbedaan mendasar antara *HTML Attributes* dan *DOM Object Properties*. Mengapa *primitive values* (string, boolean) dapat disinkronisasi melalui `observedAttributes` dan `attributeChangedCallback`, sementara *complex objects* (seperti array data, config functions, atau complex nested state) wajib di-pass melalui properties? Tunjukkan bagaimana mekanisme getter/setter internal mencegah *infinite loop reflection* antar atribut dan properti.

### Soal 1.4: Batasan Shadow DOM Encapsulation terhadap Design Tokens
Shadow DOM memberikan *style scoping* yang ketat sehingga mencegah *leakage* CSS global. Namun, batasan ini menciptakan friksi besar dalam distribusi Design Tokens enterprise. Jelaskan bagaimana CSS Custom Properties (CSS Variables) dan pseudoelement `::part()` menembus batas enkapsulasi Shadow DOM. Mengapa CSS Variables mampu menembus Shadow Boundary secara default sedangkan selector class (`.btn-primary`) terblokir total?

### Soal 1.5: Ref Forwarding dan Imperative Handle pada Enterprise React Components
Jelaskan perbedaan mendasar antara meneruskan native DOM element via `React.forwardRef` dengan memaparkan API terbatas menggunakan `React.useImperativeHandle`. Dalam skenario enterprise design system, kapan sebuah komponen form primitive (seperti `Select` atau `Modal`) **dilarang** mengekspos seluruh native DOM node dan **diwajibkan** hanya mengekspos kontrak imperatif yang terkontrol?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: SSR Hydration Mismatch pada Shadow DOM (Declarative Shadow DOM)
Sebuah enterprise web application menggunakan Next.js (React 18 SSR) dan mengintegrasikan Web Components dari core design system. Ketika me-render komponen secara server-side menggunakan Declarative Shadow DOM (`<template shadowrootmode="open">`), browser melempar error *Hydration Mismatch* dan Shadow DOM ter-duplikasi atau terhapus saat client-side hydration berjalan. 
1. Bedah akar penyebab teknis kegagalan rekonsiliasi Virtual DOM React terhadap Declarative Shadow DOM template.
2. Rancang solusi arsitektural untuk memastikan *seamless hydration* tanpa menyebabkan layout shift (CLS).

### Soal 2.2: Cross-Boundary ARIA ID Referencing
Di dalam Shadow DOM, isolasi ID adalah fitur bawaan (`document.getElementById` tidak dapat melihat ID di dalam shadow root). Namun, atribut ARIA relasional seperti `aria-labelledby`, `aria-describedby`, dan `aria-controls` bergantung pada kecocokan ID string global. 
1. Mengapa pola cross-boundary ARIA referencing gagal ketika trigger button berada di Light DOM sedangkan popover/dialog konten berada di dalam Shadow DOM?
2. Bagaimana Anda mengatasi limitasi ini menggunakan *Accessibility Object Model (AOM)* atau pola arsitektur *Slotting & ElementInternals*?

### Soal 2.3: Context Re-render Cascade pada Compound Components
Sebuah komponen `DataTable` diimplementasikan menggunakan pola React Compound Component (`DataTable`, `DataTable.Header`, `DataTable.Row`, `DataTable.Cell`) yang berbagi internal state (sorting, row selection, pagination) melalui `React.createContext`. Ketika pengguna mengklik checkbox pada satu baris di tabel dengan 1.000 baris, seluruh tabel mengalami freeze selama 400ms.
1. Analisis alur eksekusi internal React yang menyebabkan re-render cascade tersebut.
2. Bagaimana Anda merestrukturisasi state management komponen tersebut tanpa merusak DX declarative Compound Component (misal: Context splitting, Zustand vanilla store bridge, atau reactive state isolation)?

### Soal 2.4: Memory Leak pada Custom Element Lifecycle di Micro-Frontend
Dalam platform Micro-Frontend, host React application me-mount dan me-unmount Web Components secara dinamis. Tim SRE mendeteksi kebocoran memori (memory leak) yang signifikan setelah pengguna bernavigasi selama 30 menit. Hasil heap snapshot menunjukkan ribuan detached DOM nodes dan event listeners yang tertinggal.
Identifikasi 3 titik kegagalan (*failure vectors*) di dalam implementasi `connectedCallback`, `disconnectedCallback`, dan binding event listener pada Web Component wrapper yang menyebabkan Garbage Collector gagal mereclaim memori tersebut.

### Soal 2.5: Dynamic CSS Injection vs CSS Constructable Stylesheets
Ketika membangun Web Component library berkinerja tinggi, injeksi tag `<style>` secara dinamis ke dalam setiap shadow root instance mengakibatkan degradasi memori dan parsing overhead yang signifikan (O(N) stylesheet memory allocation).
Jelaskan secara teknis bagaimana **CSS Constructable Stylesheets** (`CSSStyleSheet()` dan `adoptedStyleSheets`) menyelesaikan masalah ini. Analisis dampaknya terhadap *runtime performance*, *style sharing across instances*, dan bagaimana cara kerjanya jika diintegrasikan dengan CSS-in-JS atau compiled Tailwind token streams.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Performa pada Design System Data Grid
* **Konteks:** Sebuah platform FinTech enterprise memiliki modul transaksi dengan `DataGrid` yang menampilkan 5.000 baris data keuangan real-time (update rate: 10 update/detik via WebSocket). Komponen `DataGrid` dibangun menggunakan React Design System internal yang mengandalkan runtime polymorphic CSS-in-JS (Emotion) dan React Context untuk theming dan cell formatting.
* **Gejala:** Browser mengalami dropped frames parah (FPS anjlok ke < 10 FPS), CPU core 100%, dan latency interaksi input filter mencapai 1.200ms (INP gagal total). Profiling menunjukkan runtime overhead terbesar berasal dari `style recalculation`, context propagation, dan runtime dynamic CSS hash generation pada level baris/sel.
* **Pertanyaan Diagnostik:**
  1. Identifikasi *architectural anti-patterns* pada implementasi komponen design system tersebut.
  2. Susun rencana mitigasi sistemik multi-tier (virtualization strategy, zero-runtime CSS/CSS variable compilation, structural state segregation) untuk membawa performa kembali ke 60 FPS stabil dan INP < 100ms tanpa merusak integritas Design Token.

### Skenario B: Race Condition dan State Divergence pada Form Hybrid (React Hook Form + Web Component)
* **Konteks:** Tim Enterprise meluncurkan sistem registrasi nasabah baru. Form validation engine menggunakan `react-hook-form` (RHF), namun kontrol form input (`<enterprise-text-field>`, `<enterprise-date-picker>`) adalah Web Components yang di-bundle dari Core UI library framework-agnostic.
* **Gejala:** Pada koneksi jaringan lambat atau input berkecepatan tinggi, nasabah mengalami form submission dengan payload kosong atau data yang tidak valid. Terjadi inkonsistensi (*state drift*) di mana visual text field menampilkan teks yang diketik, namun internal state RHF menganggap field masih `undefined` atau me-reject validasi secara asinkron. Selain itu, form reset (`form.reset()`) mengosongkan state RHF namun tidak me-reset tampilan internal Web Component.
* **Pertanyaan Diagnostik:**
  1. Uraikan mismatch mekanistik antara *uncontrolled component lifecycle* di React Hook Form, Custom Event dispatching di Web Component, dan DOM property mutator.
  2. Rancang arsitektur implementasi custom **Bridge Adapter / Custom Controller** yang menjamin *two-way state reconciliation*, synchronization of form reset lifecycle, serta propagasi validation attributes (`setCustomValidity`, `aria-invalid`) secara atomik.

### Skenario C: Migrasi Multi-Framework UI Suite: Native Web Components vs Headless Core Multi-Adapter
* **Konteks:** Sebuah konglomerat SaaS multinasional memiliki 14 produk terpisah yang dibangun menggunakan berbagai framework: 6 aplikasi di React 18, 4 di Vue 3, 2 di Angular 16, dan 2 di vanilla SSR/Legacy. Manajemen menginstruksikan tim arsitektur untuk menyatukan semua UI ke dalam satu Design System tunggal guna memangkas redundansi maintenance dan memastikan visual parity absolut.
* **Dilema Arsitektur:** Tim terbelah menjadi dua kubu:
  * **Kubu 1:** Membangun seluruh komponen (Visual + Logic + Structure) sebagai **100% Native Web Components (Lit-based)** dengan Custom Elements & Shadow DOM, lalu di-consume langsung oleh semua framework.
  * **Kubu 2:** Membangun **Core Headless State Machine** (framework-agnostic state/a11y engine menggunakan State Machines/XState/Zag.js), kemudian menyediakan *thin adapter wrappers* spesifik untuk masing-masing framework (React wrappers, Vue wrappers, Angular wrappers).
* **Pertanyaan Diagnostik:**
  1. Buat matriks evaluasi trade-off mendalam yang membandingkan kedua arsitektur tersebut berdasarkan kriteria: (a) Kinerja SSR & Hydration, (b) Aksesibilitas kompleks (seperti floating elements, comboboxes, modals), (c) Developer Experience (DX) masing-masing framework, dan (d) Biaya pemeliharaan jangka panjang.
  2. Sebagai Principal Architect, tentukan keputusan arsitektur mana yang paling layak dipilih untuk skala enterprise ini, sertakan *contingency plan* teknis untuk mengatasi kelemahan dari opsi yang Anda pilih.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Polymorphic & Virtualized Combobox Bridge

#### 1. Problem Statement
Banyak design system enterprise gagal menjembatani performa Web Components dengan idiomatic React patterns. Anda ditugaskan untuk mengimplementasikan sebuah komponen enterprise **`Combobox`** (Autocomplete/Selectable Dropdown) yang harus berfungsi secara framework-agnostic di intinya, namun terekspos ke ekosistem React melalui sebuah thin, highly-optimized React Adapter yang *idiomatic*, *accessible*, dan *performant*.

#### 2. Requirements & Capabilities
1. **Core Web Component (`<enterprise-combobox>`):**
   * Menggunakan Custom Elements API dan Shadow DOM.
   * Mendukung navigasi keyboard penuh sesuai spesifikasi **WAI-ARIA Combobox Pattern 1.2** (`ArrowDown`, `ArrowUp`, `Enter`, `Escape`, `Home`, `End`).
   * Menggunakan CSS Custom Properties untuk dynamic theming (mengacu pada design tokens: `--eds-color-bg`, `--eds-color-border`, `--eds-radius-md`, dll.).
   * Mengekspos `::part(input)`, `::part(listbox)`, dan `::part(option)` untuk penyesuaian gaya eksternal yang terkontrol.
   * Mendukung virtualisasi rendering internal untuk menangani hingga 20.000 items tanpa degradasi FPS.
2. **React Bridge Component (`<Combobox>`):**
   * Menyediakan React API yang idiomatic dengan dukungan `forwardRef`.
   * Mendukung prop `asChild` (polymorphic slot pattern) untuk trigger element.
   * Sinkronisasi dua arah yang seamless dengan library form eksternal (terintegrasi dengan `onChange`, `onBlur`, `value`, dan `defaultValue`).
   * Event wrapper: Mengonversi custom native events (`eds-change`, `eds-select`) menjadi standard React Synthetic event handlers (`onValueChange`, `onSelect`).
   * Type-safe: Strict TypeScript generic typing `<TData>` untuk opsi item.

#### 3. Constraints
* **Zero Layout Shift & Hydration Safe:** Komponen tidak boleh melempar warning hydration mismatch jika dijalankan di Next.js (Node SSR environment).
* **Zero External Component Libs:** Dilarang menggunakan UI primitives siap pakai (misal: dilarang memakai Radix, Headless UI, atau Material UI). Implementasi internal virtual scroll dan state machine harus murni ditulis sendiri atau menggunakan lightweight native primitives.
* **Performa:** Interaksi pembukaan listbox dan pemfilteran input dengan dataset 10.000 items harus memiliki input delay < 50ms pada CPU 4x slowdown.

#### 4. Expected Output
1. File implementasi Web Component: `enterprise-combobox.ts` (Core logic, Shadow DOM setup, Keyboard navigation, Virtual scroll viewport calculation).
2. File implementasi React Wrapper: `Combobox.tsx` (React integration bridge, ref forwarding, synthetic event handling, slot handling).
3. File deklarasi tipe: `enterprise-combobox.d.ts` (IntrinsicElements expansion untuk JSX, types definition).
4. Unit/Integration Test suite (menggunakan Vitest/Playwright): Memvalidasi kepatuhan keyboard ARIA, event dispatching, dan memory cleanup pada unmount.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda dalam arsitektur implementasi komponen tingkat enterprise.

### Saya harus memahami:
- [ ] Mekanisme propagasi event native melintasi Shadow Boundary (*retargeting*, *composed path*, dan bubbling behavior).
- [ ] Batasan CSS cascading pada Shadow DOM dan cara orkestrasi design tokens menggunakan kombinasi CSS Custom Properties dan CSS Shadow Parts (`::part`).
- [ ] Siklus hidup Custom Elements (`connectedCallback`, `disconnectedCallback`, `attributeChangedCallback`, `adoptedCallback`) beserta *timing* eksekusinya relatif terhadap framework mounting.
- [ ] Dampak Declarative Shadow DOM (DSD) terhadap Server-Side Rendering (SSR) dan arsitektur Client-Side Hydration.
- [ ] Perbedaan performa antara Runtime CSS-in-JS, Zero-Runtime/Compiled CSS, dan CSS Constructable Stylesheets pada skala jutaan elemen DOM.
- [ ] Pola WAI-ARIA Accessible Rich Internet Applications (APG) untuk komponen interaktif kompleks (Dialog, Combobox, Menu, Tabs).
- [ ] Mekanisme reconciler React terhadap Custom Elements (Property vs Attribute mapping quirks).

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor kode ASCII atau nama string *deprecated* dari keyboard event (`e.keyCode` atau `e.which`; cukup gunakan `e.key` standar W3C).
- [ ] Setiap variasi browser prefix vendor CSS legacy (fokus pada standar modern evergreen browser).
- [ ] Seluruh implementasi spesifikasi internal browser untuk styling user-agent Shadow DOM bawaan browser (misal: Shadow DOM native `<input type="date">`).

### Saya harus bisa melakukan:
- [ ] Membangun custom React bridge/wrapper yang membungkus Web Component dengan dukungan *two-way data binding*, ref forwarding, dan pembersihan event listener tanpa memory leak.
- [ ] Mendiagnosis dan mengeliminasi *re-render cascade* pada React Compound Components menggunakan advanced state decoupling patterns.
- [ ] Menulis arsitektur *polymorphic component* yang fully type-safe di TypeScript (mencegah kompilasi tipe ilegal saat prop `as` diganti).
- [ ] Mengimplementasikan *accessible keyboard navigation* yang compliant dengan WAI-ARIA 1.2 tanpa bergantung pada library pihak ketiga.
- [ ] Menganalisis *Heap Snapshot* di Chrome DevTools untuk menemukan deteksi *detached DOM nodes* yang disebabkan oleh Web Component lifecycle hooks yang tidak bersih.
- [ ] Mengonfigurasi arsitektur bundling (Rollup/ESBuild/Vite) untuk mendistribusikan design system components dengan dukungan penuh terhadap *tree-shaking* (ESM) dan declarative typings.