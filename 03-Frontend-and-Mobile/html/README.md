# Kurikulum Enterprise Modern HTML: Arsitektur Dokumen, Aksesibilitas, dan Performa Web

Selamat datang di kurikulum spesialisasi rekayasa markup dokumen web enterprise. Repositori ini berisi silabus komprehensif 10 Bab yang mengupas tuntas ekosistem **HTML (HyperText Markup Language)** modern—bukan sekadar sebagai sintaks pemformatan visual, melainkan fondasi semantik, representasi struktural *Accessibility Tree*, dan poros utama *Critical Rendering Path* pada browser modern.

---

## 1. Course Overview & Mindset

### Paradigma Rekayasa HTML Modern
Di lingkungan produksi skala besar (*large-scale enterprise*), HTML sering kali diabaikan dan dianggap sekadar *markup* pasif oleh *software engineer* yang terdistraksi oleh ekosistem JavaScript. Paradigma ini adalah kesalahan arsitektural yang fatal. HTML adalah:

1. **Jantung Aksesibilitas & Inklusivitas**: Browser memetakan elemen HTML langsung ke platform-native *Accessibility API* (AOM / Accessibility Object Model). Kesalahan pemilihan elemen semantik memutus aksesibilitas jutaan pengguna disabilitas dan melanggar mandat hukum internasional (seperti EAA dan ADA Title III).
2. **Katalis Utama Performa (*Core Web Vitals*)**: Pengorganisasian elemen `<head>`, *resource hints*, dan strategi deklaratif aset gambar (`srcset`, `sizes`, `fetchpriority`) menentukan metrik kritis seperti *Largest Contentful Paint* (LCP) dan *Cumulative Layout Shift* (CLS).
3. **Garda Terdepan Keamanan Klien**: Atribut keamanan seperti `rel="noopener noreferrer"`, isolasi *sandboxed iframe*, integrasi *Content Security Policy* (CSP), serta *Trusted Types* dieksekusi pertama kali pada lapisan dokumen HTML.
4. **Kontrak Mesin (*Machine-Readable Contract*)**: Algoritma perayap (*crawlers*), mesin pencari, agen AI, dan *social aggregators* mengonsumsi struktur HTML semantik dan *Structured Data* (JSON-LD/Microdata) untuk mengindeks serta mengekstrak entitas data secara deterministik.

> **Mindset Enterprise**: *"Menulis HTML bukan tentang bagaimana tampilan elemen di layar, melainkan tentang apa makna dan peran elemen tersebut terhadap browser engine, assistive technologies, dan pipeline data global."*

---

## 2. Learning Roadmap

Berikut adalah struktur pohon arsitektur pembelajaran 10 BAB silabus HTML Enterprise:

```text
HTML Enterprise Curriculum
├── 01. Fondasi Arsitektur Web, Standar WHATWG, & Parsing Engine
│   ├── 01.1 Anatomi Dokumen & HTML Living Standard
│   ├── 01.2 Tokenization, Tree Construction, & Critical Rendering Path
│   └── 01.3 Strict Mode vs Quirks Mode & Validasi DOCTYPE
├── 02. Semantik Dokumen Tingkat Lanjut & Information Architecture
│   ├── 02.1 Document Outline Algorithm & Landmark Structure
│   ├── 02.2 Structured Microdata & Schema.org Semantic Graphing
│   └── 02.3 Content Chunking: Article, Section, Aside, & Nav Boundaries
├── 03. Text-Level Semantics, Tipografi Teknis, & Lokalisasi
│   ├── 03.1 Precision Phrasing: Time, Data, Mark, Code, & BiDi Processing
│   ├── 03.2 Tipografi Kompleks: Ruby Annotations, Sub/Sup, & Wbr Logic
│   └── 03.3 Ekosistem I18n: Language Tags, Dir Attributes, & CJK Typography
├── 04. Sistem Formulir Enterprise & Validasi Deklaratif
│   ├── 04.1 Anatomi Form Controls Modern & Input Modalities
│   ├── 04.2 Native Constraint Validation API & Custom Error Bubbles
│   └── 04.3 Keamanan Form: Autocomplete Vectors, CSRF Seeds, & Enctype Handling
├── 05. Media Responsif, Resource Hints, & Optimasi Aset
│   ├── 05.1 Picture Element, Srcset Resolution Switching, & Art Direction
│   ├── 05.2 Audio-Video Streaming: WebM, MP4, Tracks, & WebVTT Captions
│   └── 05.3 Critical Resource Hints: Preload, Prefetch, Preconnect, & Fetchpriority
├── 06. Aksesibilitas Web Mendalam (A11y) & Integrasi WAI-ARIA
│   ├── 06.1 Pemetaan DOM ke Accessibility Tree (AOM)
│   ├── 06.2 WAI-ARIA 1.2: Roles, States, Properties, & ARIA Pitfalls
│   └── 06.3 Focus Management, Tabbing Traps, & Skip Navigation Links
├── 07. Web Components & Template Deklaratif
│   ├── 07.1 Declarative Shadow DOM (DSD) & Shadow Boundaries
│   ├── 07.2 Native Templates (<template>) & Dynamic Insertion (<slot>)
│   └── 07.3 Custom Elements Lifecycle Foundation melalui Atribut HTML
├── 08. Interoperabilitas Platform, SEO Teknis, & Metadata
│   ├── 08.1 Metadata Head Optimization: Charset, Viewport, & OpenGraph/Twitter Cards
│   ├── 08.2 PWA Manifest Integration & Web App Meta Configurations
│   └── 08.3 Search Engine Crawlability, Canonicalization, & Robots Directive
├── 09. Keamanan HTML: Sanitasi DOM, CSP, & Isolasi Sandbox
│   ├── 09.1 Isolasi Eksternal: Iframe Security Policies & Sandbox Matrix
│   ├── 09.2 Pertahanan XSS: Sanitizer API, Attribute Hardening, & Trusted Types
│   └── 09.3 Content Security Policy (CSP) Declarative Meta Headers
└── 10. API Browser Modern & Lifecycle Dokumen
    ├── 10.1 Native Dialog Element, Popover API, & Top Layer Management
    ├── 10.2 Drag and Drop API & Native Clipboard Integration
    └── 10.3 Web Storage, Drag/Drop State, & Document Lifecycle State
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Arsitektur Web, Standar WHATWG, dan Parsing Engine](./01-fondasi-arsitektur-web-standar-whatwg-dan-parsing-engine/)
Membedah bagaimana browser mengurai *stream bytes* menjadi dokumen fungsional melalui aturan baku spesifikasi WHATWG Living Standard.
- [Modul 01: Anatomi Dokumen, Encoding (UTF-8), dan Standar WHATWG](./01-fondasi-arsitektur-web-standar-whatwg-dan-parsing-engine/01-anatomi-dokumen-dan-standar-whatwg.md)
- [Modul 02: Mekanisme Parsing Engine: Tokenization, Tree Construction, dan CRP](./01-fondasi-arsitektur-web-standar-whatwg-dan-parsing-engine/02-parsing-engine-dan-critical-rendering-path.md)
- [Modul 03: Quirks Mode, Standards Mode, dan Implikasi DOCTYPE](./01-fondasi-arsitektur-web-standar-whatwg-dan-parsing-engine/03-quirks-mode-dan-implikasi-doctype.md)

### [Bab 02: Semantik Dokumen Tingkat Lanjut & Information Architecture](./02-semantik-dokumen-tingkat-lanjut-dan-information-architecture/)
Membangun struktur hierarki hierarki data web menggunakan elemen struktural murni yang ramah mesin dan terukur.
- [Modul 01: Document Landmark Roles dan Outline Algorithm Modern](./02-semantik-dokumen-tingkat-lanjut-dan-information-architecture/01-document-landmarks-dan-outline-algorithm.md)
- [Modul 02: Demarkasi Semantik: `<article>`, `<section>`, `<aside>`, `<nav>`, dan `<main>`](./02-semantik-dokumen-tingkat-lanjut-dan-information-architecture/02-demarkasi-semantik-dan-content-chunking.md)
- [Modul 03: Microdata dan Integrasi Schema.org untuk Semantic Web](./02-semantik-dokumen-tingkat-lanjut-dan-information-architecture/03-microdata-dan-integrasi-schema-org.md)

### [Bab 03: Text-Level Semantics, Tipografi Teknis, dan Lokalisasi](./03-text-level-semantics-tipografi-teknis-dan-lokalisasi/)
Mengeksplorasi elemen tingkat teks untuk merepresentasikan data kontekstual, tipografi lintas bahasa, dan dukungan internasionalisasi tingkat rendah.
- [Modul 01: Semantik Presisi: `<time>`, `<data>`, `<mark>`, `<abbr>`, dan `<code>`](./03-text-level-semantics-tipografi-teknis-dan-lokalisasi/01-semantik-presisi-dan-data-time.md)
- [Modul 02: Kompleksitas Tipografi: `<ruby>`, `<rt>`, `<rp>`, `<wbr>`, dan Hyphenation](./03-text-level-semantics-tipografi-teknis-dan-lokalisasi/02-tipografi-kompleks-ruby-dan-wbr.md)
- [Modul 03: Fondasi Lokalisasi: Atribut `lang`, `dir`, dan Penanganan Teks BiDi (Bi-directional)](./03-text-level-semantics-tipografi-teknis-dan-lokalisasi/03-lokalisasi-lang-dir-dan-bidi.md)

### [Bab 04: Sistem Formulir Enterprise & Validasi Deklaratif](./04-sistem-formulir-enterprise-dan-validasi-deklaratif/)
Merancang sistem pengumpulan data yang tangguh, aman, dan memiliki kapabilitas validasi bawaan tanpa ketergantungan JavaScript pihak ketiga.
- [Modul 01: Kontrol Formulir Modern: Types, Inputmodes, Data Lists, dan Enctype Matrix](./04-sistem-formulir-enterprise-dan-validasi-deklaratif/01-kontrol-formulir-modern-dan-inputmodes.md)
- [Modul 02: Native Constraint Validation Engine: Patterns, Atribut States, dan Custom Validity](./04-sistem-formulir-enterprise-dan-validasi-deklaratif/02-native-constraint-validation-engine.md)
- [Modul 03: Proteksi Form Klien: Autocomplete Tokens, Mitigasi Phishing, dan Form Security](./04-sistem-formulir-enterprise-dan-validasi-deklaratif/03-autocomplete-tokens-dan-keamanan-form.md)

### [Bab 05: Media Responsif, Resource Hints, dan Optimasi Aset](./05-media-responsif-resource-hints-dan-optimasi-aset/)
Mengoptimalkan pemuatan media resolusi tinggi dan memandu browser dalam mengunduh sumber daya eksternal dengan performa maksimal.
- [Modul 01: Gambar Responsif Enterprise: `<picture>`, `srcset`, `sizes`, dan Format Modern](./05-media-responsif-resource-hints-dan-optimasi-aset/01-gambar-responsif-picture-dan-srcset.md)
- [Modul 02: Penanganan Audio/Video Native: Multi-Source Codecs, Subtitles, dan WebVTT](./05-media-responsif-resource-hints-dan-optimasi-aset/02-audio-video-codecs-dan-webvtt.md)
- [Modul 03: Resource Hints dan Loading Priority: `fetchpriority`, Preload, Prefetch, Preconnect](./05-media-responsif-resource-hints-dan-optimasi-aset/03-resource-hints-dan-loading-priorities.md)

### [Bab 06: Aksesibilitas Web Mendalam (A11y) & Integrasi WAI-ARIA](./06-aksesibilitas-web-mendalam-dan-integrasi-wai-aria/)
Membangun jembatan inklusi digital dengan memahami transformasi markup menjadi Accessibility Tree dan penerapan ARIA secara tepat.
- [Modul 01: Mekanisme Accessibility Object Model (AOM) dan WCAG 2.2 Standards](./06-aksesibilitas-web-mendalam-dan-integrasi-wai-aria/01-mekanisme-aom-dan-wcag-standards.md)
- [Modul 02: WAI-ARIA 1.2: Roles, States, Properties, dan Anti-Patterns Menghindari ARIA Abuse](./06-aksesibilitas-web-mendalam-dan-integrasi-wai-aria/02-wai-aria-roles-states-dan-anti-patterns.md)
- [Modul 03: Navigasi Keyboard Native: Focus Order, Inertness, Tabindex, dan Skip Links](./06-aksesibilitas-web-mendalam-dan-integrasi-wai-aria/03-focus-order-inert-dan-keyboard-navigation.md)

### [Bab 07: Web Components & Template Deklaratif](./07-web-components-dan-template-deklaratif/)
Membangun antarmuka komponen terenkapsulasi secara native langsung di level markup tanpa *framework overhead*.
- [Modul 01: Declarative Shadow DOM (DSD): Server-Side Rendering untuk Web Components](./07-web-components-dan-template-deklaratif/01-declarative-shadow-dom-dsd.md)
- [Modul 02: Template Deklaratif: Primitive Elements `<template>` dan Dynamic Composition `<slot>`](./07-web-components-dan-template-deklaratif/02-primitive-template-dan-slot.md)
- [Modul 03: Deklarasi Custom Elements Berbasis Atribut Standar](./07-web-components-dan-template-deklaratif/03-deklarasi-custom-elements-standar.md)

### [Bab 08: Interoperabilitas Platform, SEO Teknis, dan Metadata](./08-interoperabilitas-platform-seo-teknis-dan-metadata/)
Mengonfigurasi dokumen agar dapat berinteraksi sempurna dengan ekosistem mesin pencari, sistem operasi, dan platform media sosial.
- [Modul 01: Arsitektur Head Komprehensif: Character Encoding, Viewports, dan OpenGraph/Twitter Cards](./08-interoperabilitas-platform-seo-teknis-dan-metadata/01-arsitektur-head-metadata-dan-ogp.md)
- [Modul 02: PWA Web App Manifest, App Icons, dan Standar Penautan Sistem Operasi](./08-interoperabilitas-platform-seo-teknis-dan-metadata/02-web-app-manifest-dan-integrasi-os.md)
- [Modul 03: SEO Teknis Lanjutan: Crawl Instructions, Canonical Rules, dan Hreflang Strategies](./08-interoperabilitas-platform-seo-teknis-dan-metadata/03-crawlability-canonical-dan-hreflang.md)

### [Bab 09: Keamanan HTML: Sanitasi DOM, CSP, dan Isolasi Sandbox](./09-keamanan-html-sanitasi-dom-csp-dan-isolasi-sandbox/)
Mengeliminasi vektor serangan injeksi (*Cross-Site Scripting*), kebocoran konteks navigasi, dan isolasi *third-party embeds*.
- [Modul 01: Eksekusi Iframe Aman: Atribut `sandbox`, Feature Policies, dan Origin Isolation](./09-keamanan-html-sanitasi-dom-csp-dan-isolasi-sandbox/01-iframe-sandbox-dan-origin-isolation.md)
- [Modul 02: Mitigasi XSS pada HTML: Native Sanitizer API, Attribute Escaping, dan Rel Policies](./09-keamanan-html-sanitasi-dom-csp-dan-isolasi-sandbox/02-xss-mitigasi-dan-rel-policies.md)
- [Modul 03: Deklarasi Content Security Policy (CSP) via Meta Tags dan Keamanan Trusted Types](./09-keamanan-html-sanitasi-dom-csp-dan-isolasi-sandbox/03-declarative-csp-dan-trusted-types.md)

### [Bab 10: API Browser Modern & Lifecycle Dokumen](./10-api-browser-modern-dan-lifecycle-dokumen/)
Memanfaatkan kemampuan native peramban mutakhir yang didefinisikan secara langsung melalui struktur markup modern.
- [Modul 01: Dialog Element Native, Popover API, dan Top Layer Mechanics](./10-api-browser-modern-dan-lifecycle-dokumen/01-dialog-element-dan-popover-api.md)
- [Modul 02: Native Drag and Drop HTML5 API dan Clipboard Data Transport](./10-api-browser-modern-dan-lifecycle-dokumen/02-native-drag-and-drop-dan-clipboard.md)
- [Modul 03: Lifecycle Dokumen: `DOMContentLoaded`, `readystatechange`, dan Integrasi Service Worker](./10-api-browser-modern-dan-lifecycle-dokumen/03-lifecycle-dokumen-dan-sw-registration.md)

---

## 4. Enterprise Capstone Project Specification

### Judul Proyek:
**Global Enterprise Fintech Design System & Accessible Self-Service Portal Engine**

### Deskripsi Arsitektural:
Peserta diwajibkan merancang sebuah portal institusi keuangan multi-tenant kelas enterprise yang mengimplementasikan arsitektur HTML secara *pure native*, mematuhi standar internasional WCAG 2.2 AAA, serta dapat beroperasi secara optimal meskipun lingkungan klien menonaktifkan JavaScript (*Graceful Fallback / Progressive Enhancement*).

### Spesifikasi Teknis Minimum:
1. **Document Structure & Semantic Integrity**:
   - Struktur dokumen wajib membagi zona aplikasi menggunakan Landmark Elements (`<header>`, `<main>`, `<aside>`, `<nav>`, `<footer>`) dengan pelabelan ID dan ARIA terpetakan 100%.
   - Mengimplementasikan skema data terstruktur [Schema.org/FinancialProduct](https://schema.org/FinancialProduct) dan [Schema.org/Organization](https://schema.org/Organization) menggunakan format Microdata native di dalam elemen DOM.
2. **Accessible Native Overlay & Interactivity**:
   - Penggunaan elemen native `<dialog>` untuk transaksi transfer dana dengan penanganan fokus native dan pengurungan keyboard (*tab cycle*).
   - Menu navigasi konteks dan dropdown notifikasi wajib menggunakan **HTML Popover API** deklaratif (`popover`, `popovertarget`).
3. **Formulir Transaksi Kompleks**:
   - Multi-step Transaction Form berbasis native constraint validation (`pattern`, `min`, `max`, `step`, `required`).
   - Implementasi deklarasi token `autocomplete` resmi perbankan (e.g., `cc-name`, `cc-number`, `cc-exp`, `transaction-amount`, `one-time-code`).
   - Pemanfaatan `inputmode` presisi (`numeric`, `decimal`, `email`) untuk *virtual keyboard triggering*.
4. **Media Responsif & Performa LCP/CLS**:
   - Dashboard analitik memuat visual grafik dengan elemen `<picture>`, format `AVIF` dan `WebP` fallback, serta kalkulasi `sizes` matematis bebas layout shifts.
   - Resource hints di `<head>`: deklarasi prioritas unduhan font dan critical assets menggunakan `fetchpriority="high"` dan `rel="preload"`.
5. **Keamanan & Isolasi Tingkat Lanjut**:
   - Implementasi modul integrasi analitik pihak ketiga menggunakan `<iframe sandbox="allow-scripts" referrerpolicy="strict-origin-when-cross-origin">`.
   - Penerapan `<meta http-equiv="Content-Security-Policy">` dengan restriksi script dan stylesheet ketat.
   - Seluruh tautan eksternal dilindungi menggunakan `rel="noopener noreferrer"`.

### Acceptance Criteria & Validasi Proyek:
- **W3C Nu HTML Checker**: Nol galat (*Zero Errors*), Nol peringatan (*Zero Warnings*).
- **Lighthouse Score**: Aksesibilitas (100/100), SEO (100/100), Best Practices (100/100), Performance (>95/100).
- **Screen Reader Verification**: Diuji dan diverifikasi menggunakan NVDA (Windows) dan VoiceOver (macOS/iOS) tanpa ambigu navigasi atau informasi yang tertelan.
- **No-JS Audit**: Seluruh alur informasi data portofolio, tabel mutasi rekening, dan formulir pengajuan tetap dapat dibaca dan dikirimkan (*submitted*) secara native tanpa bantuan JavaScript engine.