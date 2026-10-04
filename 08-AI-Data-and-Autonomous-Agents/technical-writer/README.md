# Kurikulum Profesional: Modern Technical Writing & Docs-as-Code Engine

Selamat datang di repositori kurikulum resmi **Technical Writer** berbasis standar industri modern dan roadmap teknis. Silabus ini dirancang untuk mentransformasi praktisi teknis dan penulis dokumentasi menjadi **Technical Curriculum Architect** dan **Enterprise Documentation Engineer** yang mampu merancang, membangun, mengotomatisasi, serta mengelola portal dokumentasi berskala produksi menggunakan paradigma *Docs-as-Code*.

---

## 1. Course Overview & Mindset

### Filosofi Inti: "Documentation is a First-Class Engineering Product"
Dokumentasi teknis modern bukan sekadar catatan pasca-rilis (*afterthought*), melainkan pilar arsitektural yang menentukan keberhasilan adopsi produk perangkat lunak, API, dan infrastruktur cloud. Seorang *Technical Writer* modern beroperasi layaknya *Software Engineer*:
- Menulis konten menggunakan format terstruktur (*Markdown, MDX, AsciiDoc*).
- Mengelola versi menggunakan *Distributed Version Control* (`git`).
- Menerapkan penjaminan mutu otomatis melalui *Continuous Integration* (CI) dengan linter prosa (*Vale*) dan validator skema (*Spectral*).
- Mendesain pengalaman pengguna pengembang (*Developer Experience / DX*) yang intuitif, minim friksi kognitif, dan berorientasi pada penyelesaian masalah.

### Core Tenets
1. **Developer Empathy & User-Centricity:** Dokumentasi disusun berdasarkan model mental audiens (pengembang, DevOps, arsitek sistem, atau pengambil keputusan teknis), bukan sekadar mencerminkan struktur basis kode internal.
2. **Framework Diátaxis:** Konten dipisahkan secara tegas ke dalam empat kuadran fungsional: *Tutorials* (pembelajaran), *How-To Guides* (pemecahan masalah terarah), *Reference* (informasi teoretis/deskriptif), dan *Explanation* (pemahaman arsitektural mendalam).
3. **Automated Governance:** Tidak ada dokumentasi yang masuk ke *production* tanpa melewati pengujian otomatis: validasi tautan rusak, kepatuhan *style guide*, validasi skema OpenAPI, dan uji coba cuplikan kode (*code snippet testing*).
4. **Docs-as-Code System:** Dokumentasi hidup berdampingan dengan kode sumber dalam siklus hidup pengembangan perangkat lunak (*Software Development Life Cycle / SDLC*).

### Target Audiens
- **Software Engineers / DevOps Engineers** yang ingin menguasai spesialisasi *Developer Experience (DX)* dan dokumentasi teknis tingkat lanjut.
- **Technical Writers** konvensional yang ingin bertransisi ke alur kerja *Docs-as-Code*, otomatisasi API, dan *Developer Portals*.
- **API Product Managers & Engineering Leads** yang ingin merancang tata kelola (*governance*) dokumentasi enterprise yang terukur.

---

## 2. Learning Roadmap

```plaintext
Modern Technical Writer & Docs-as-Code Roadmap
│
├── [01] Fondasi Technical Writing & Information Architecture (IA)
│    ├── 01.1 Peran, Mindset & Paradigma Docs-as-Code
│    └── 01.2 Framework Dokumentasi: Diátaxis & DITA
│
├── [02] Riset Rekayasa, Empati Pengembang, & Analisis Audiens
│    ├── 02.1 Teknik SME Interview & Codebase Archaeology
│    └── 02.2 User Persona Engineering & Analisis Beban Kognitif
│
├── [03] Ketetapan Bahasa, Technical Tone, & Style Guides
│    ├── 03.1 Standar Industri: Google Developer & Microsoft Style Guide
│    └── 03.2 Plain Language, Active Voice, & Technical Microcopy
│
├── [04] Ekosistem Docs-as-Code & Alur Kolaborasi Git
│    ├── 04.1 Markup Languages: CommonMark, GFM, MDX, & AsciiDoc
│    └── 04.2 Advanced Git Workflows, Branching Strategies, & Code Reviews
│
├── [05] Dokumentasi API & Spesifikasi Kontrak Mesin
│    ├── 05.1 REST API Architecture & OpenAPI Specification (OAS 3.1)
│    └── 05.2 Dokumentasi Event-Driven API, GraphQL, & gRPC/Protobuf
│
├── [06] Static Site Generators (SSG) & Developer Portals
│    ├── 06.1 Modern SSG Engine: Docusaurus, Starlight (Astro), & Nextra
│    └── 06.2 Information Retrieval: Algolia DocSearch, Pagefind, & UX Docs
│
├── [07] Visual Architecture & Diagrams-as-Code
│    ├── 07.1 Prinsip Komunikasi Visual & Diagram C4 Model
│    └── 07.2 Diagramming-as-Code: Mermaid.js, PlantUML, & Structurizr
│
├── [08] Otomatisasi Kualitas & Continuous Integration (CI)
│    ├── 08.1 Automated Prose Linting: Vale & Custom Style Rules
│    ├── 08.2 API Contract Linting: Spectral & JSON Schema Testing
│    └── 08.3 CI/CD Pipelines: GitHub Actions, Lychee (Link Check), & Previews
│
├── [09] Authoring Code Samples, SDK Docs, & CLI Guides
│    ├── 09.1 Desain Cuplikan Kode Multi-Bahasa yang Testable
│    └── 09.2 Dokumentasi Command Line Interface (CLI) & Man Pages
│
└── [10] Governance, Observability, Metrics, & Content Lifecycle
     ├── 10.1 Content Health: Doc Decay, Deprecation, & Versioning
     └── 10.2 Analytics Dokumentasi, Feedback Loops, & Globalisasi (i18n)
```

---

## 3. Navigasi Detail Modul Kursus

### [Bab 01: Fondasi Technical Writing & Information Architecture (IA)](./01-fondasi-technical-writing-dan-ia/README.md)
*Membangun pemahaman fundamental tentang peran komunikasi teknis modern dan pengorganisasian informasi terstruktur.*
- [Modul 01.1: Peran Modern Technical Writer & Paradigma Docs-as-Code](./01-fondasi-technical-writing-dan-ia/01-peran-dan-mindset.md)
  - Evolusi dokumentasi teknis: Dari PDF manual warisan (*legacy*) ke ekosistem terdistribusi.
  - Peran Technical Writer dalam siklus hidup Agile/DevOps.
  - Definisi, keuntungan, dan batasan implementasi metodologi *Docs-as-Code*.
- [Modul 01.2: Framework Dokumentasi: Diátaxis & DITA](./01-fondasi-technical-writing-dan-ia/02-framework-diataxis-dan-dita.md)
  - Analisis mendalam framework Diátaxis: *Tutorials*, *How-To Guides*, *Reference*, dan *Explanation*.
  - Pemisahan tanggung jawab (*separation of concerns*) dalam struktur folder dokumentasi.
  - Konsep dasar DITA (*Darwin Information Typing Architecture*) dan relevansinya di era modern.

---

### [Bab 02: Riset Rekayasa, Empati Pengembang, & Analisis Audiens](./02-riset-rekayasa-dan-analisis-audiens/README.md)
*Metodologi ekstraksi pengetahuan dari sistem perangkat lunak nyata dan pemetaan model mental pengguna.*
- [Modul 02.1: SME Interview Framework & Codebase Archaeology](./02-riset-rekayasa-dan-analisis-audiens/01-sme-interview-dan-code-archaeology.md)
  - Strategi melakukan wawancara teknis terstruktur dengan *Subject Matter Experts* (SME / Staff Engineers).
  - Melakukan *Codebase Archaeology*: Membaca kode sumber, berkas konfigurasi, `git blame`, dan *Pull Request discussions* untuk menyusun draf dokumentasi.
  - Teknik dekonstruksi *RFC (Request for Comments)* dan ADR (*Architecture Decision Records*).
- [Modul 02.2: User Persona Engineering & Analisis Beban Kognitif](./02-riset-rekayasa-dan-analisis-audiens/02-persona-engineering-dan-beban-kognitif.md)
  - Segmentasi audiens teknis: *Application Developers*, *Platform/Infra Engineers*, *Security Officers*, dan *CTO/Decision Makers*.
  - Meminimalkan *Cognitive Load* (Intrinsic, Germane, Extraneous Load) dalam transfer pengetahuan teknis.
  - Pemetaan skenario: *First Time to Hello World* vs *Enterprise Production Troubleshooting*.

---

### [Bab 03: Ketetapan Bahasa, Technical Tone, & Style Guides](./03-ketetapan-bahasa-dan-style-guides/README.md)
*Standardisasi semantik, nada komunikasi, dan kepatuhan terhadap pedoman penulisan industri.*
- [Modul 03.1: Standar Industri: Google Developer & Microsoft Style Guide](./03-ketetapan-bahasa-dan-style-guides/01-standar-style-guide-industri.md)
  - Analisis komparatif: *Google Developer Documentation Style Guide* vs *Microsoft Writing Style Guide*.
  - Tata kelola kapitalisasi, terminologi teknis, penamaan parameter, kode tombol, dan elemen UI.
  - Menetapkan *Internal Company Engineering Style Guide* berbasis turunan open-source.
- [Modul 03.2: Plain Language, Active Voice, & Technical Microcopy](./03-ketetapan-bahasa-dan-style-guides/02-plain-language-dan-microcopy.md)
  - Transformasi kalimat pasif (*passive voice*) menjadi kalimat imperatif/aktif berorientasi aksi.
  - Mengeliminasi ambiguasi, jargon internal (*insider jargon*), dan kata pengisi (*weasel words*).
  - *Technical Microcopy*: Merancang pesan error (*error messages*), *tooltips*, peringatan (*callouts/admonitions*), dan antarmuka CLI.

---

### [Bab 04: Ekosistem Docs-as-Code & Alur Kolaborasi Git](./04-ekosistem-docs-as-code-dan-git/README.md)
*Penguasaan format penulisan berkas teks mentah (*plain text*) dan manajemen kontrol versi terdistribusi.*
- [Modul 04.1: Format Markup: CommonMark, GFM, MDX, & AsciiDoc](./04-ekosistem-docs-as-code-dan-git/01-format-markup-lanjutan.md)
  - Sintaksis lanjutan CommonMark & *GitHub Flavored Markdown* (GFM): Tabel kompleks, task lists, footnote.
  - Ekosistem *MDX*: Menanamkan komponen interaktif (React) ke dalam alur kerja dokumentasi.
  - *AsciiDoc*: Fitur transklusi (`include::`), conditional attributes, dan penulisan dokumen spesifikasi monolitik.
- [Modul 04.2: Advanced Git Workflows, Branching Strategies, & Code Reviews](./04-ekosistem-docs-as-code-dan-git/02-git-workflow-dan-review.md)
  - Manajemen repository dokumentasi: *Monorepo* vs *Polyrepo (Distributed Docs)*.
  - Strategi branch: *Trunk-Based Development* vs *Feature Branching* untuk sinkronisasi rilis perangkat lunak.
  - Peninjauan konten (*Peer Review*) via Pull Requests: Penggunaan *PR Templates*, *Conventional Commits*, dan etika *editorial feedback*.

---

### [Bab 05: Dokumentasi API & Spesifikasi Kontrak Mesin](./05-dokumentasi-api-dan-spesifikasi-kontrak/README.md)
*Mendokumentasikan antarmuka pemrograman aplikasi berbasis spesifikasi formal standar industri.*
- [Modul 05.1: REST API Architecture & OpenAPI Specification (OAS 3.1)](./05-dokumentasi-api-dan-spesifikasi-kontrak/01-rest-dan-openapi-3.md)
  - Arsitektur REST, semantik HTTP method, format status code, skema autentikasi (Bearer, OAuth2, mTLS).
  - Bedah anatomi berkas OAS 3.1: `info`, `servers`, `paths`, `components/schemas`, `securitySchemes`.
  - Mendesain dokumentasi API interaktif menggunakan Swagger UI, Redoc, dan Stoplight Elements.
- [Modul 05.2: Dokumentasi Event-Driven API, GraphQL, & gRPC/Protobuf](./05-dokumentasi-api-dan-spesifikasi-kontrak/02-asyncapi-graphql-grpc.md)
  - Mengurai skema GraphQL: Query, Mutation, Subscription, dan auto-generasi referensi schema.
  - Dokumentasi Message-Driven & Event-Driven Architecture menggunakan spesifikasi *AsyncAPI*.
  - Arsitektur RPC tingkat tinggi: Mendokumentasikan berkas `.proto` (gRPC/Protocol Buffers) dan metadata service.

---

### [Bab 06: Static Site Generators (SSG) & Developer Portals](./06-static-site-generators-dan-portal/README.md)
*Membangun portal dokumentasi berkemampuan tinggi dengan arsitektur web modern.*
- [Modul 06.1: Modern SSG Engine: Docusaurus, Starlight, & Nextra](./06-static-site-generators-dan-portal/01-arsitektur-ssg-modern.md)
  - Analisis mendalam implementasi: Docusaurus (React), Starlight (Astro - performa ekstrem zero-JS default), dan Nextra (Next.js).
  - Konfigurasi struktur navigasi: Sidebar bertingkat, breadcrumbs, navigasi antarversi (*versioning/doc tags*).
  - Kustomisasi tata letak, theming (CSS Variables/Tailwind), dan penanganan dark/light mode adaptif.
- [Modul 06.2: Information Retrieval: Algolia DocSearch, Pagefind, & DX](./06-static-site-generators-dan-portal/02-pencarian-dan-portal-ux.md)
  - Arsitektur pencarian: Integrasi *Algolia DocSearch* (cloud crawler) vs *Pagefind* (static index pencarian luring/client-side).
  - Mengoptimalkan metadata SEO teknis: Open Graph tags, canonical URLs, dan struktur sitemap.
  - Optimasi aksesibilitas web (WCAG 2.1 AA compliance) pada situs dokumentasi.

---

### [Bab 07: Visual Architecture & Diagrams-as-Code](./07-visual-architecture-dan-diagrams-as-code/README.md)
*Menerjemahkan arsitektur teknis yang rumit menjadi diagram terstandarisasi berbasis teks.*
- [Modul 07.1: Prinsip Komunikasi Visual & Diagram C4 Model](./07-visual-architecture-dan-diagrams-as-code/01-prinsip-visual-dan-c4-model.md)
  - Hierarki visual dan eliminasi ambiguitas dalam diagram alur (*flowchart*) serta topologi jaringan.
  - Paradigma C4 Model: Memetakan perangkat lunak ke dalam level *Context*, *Container*, *Component*, dan *Code*.
  - Kapan menggunakan diagram urutan (*sequence diagram*), *state machine*, atau *entity relationship diagram (ERD)*.
- [Modul 07.2: Diagramming-as-Code: Mermaid.js, PlantUML, & Structurizr](./07-visual-architecture-dan-diagrams-as-code/02-alat-diagrams-as-code.md)
  - Mengintegrasikan Mermaid.js secara native pada Markdown untuk *sequence*, *flowchart*, dan *Git graph*.
  - PlantUML untuk representasi arsitektur kompleks berbasis JVM.
  - Structurizr DSL: Menulis arsitektur C4 sekali dan mengekspornya ke berbagai format visual secara otomatis.

---

### [Bab 08: Otomatisasi Kualitas & Continuous Integration (CI)](./08-otomatisasi-kualitas-dan-ci/README.md)
*Menerapkan teknik otomatisasi linters dan pengujian dokumen pada alur CI/CD.*
- [Modul 08.1: Automated Prose Linting: Vale & Custom Style Rules](./08-otomatisasi-kualitas-dan-ci/01-vale-dan-linting-prosa.md)
  - Instalasi dan konfigurasi `.vale.ini`: Menetapkan *vocabularies*, tingkat keparahan (*warning, suggestion, error*).
  - Mengintegrasikan ruleset industri: `Google`, `Microsoft`, `proselint`, dan `write-good`.
  - Penulisan *custom regex rules* (YAML) untuk memvalidasi istilah spesifik perusahaan dan mendeteksi terminologi usang.
- [Modul 08.2: API Contract Linting: Spectral & JSON Schema Testing](./08-otomatisasi-kualitas-dan-ci/02-spectral-dan-api-testing.md)
  - Linting spesifikasi OpenAPI menggunakan *Spectral*: Memvalidasi kelengkapan parameter, deskripsi, dan response status.
  - Menulis ruleset kustom Spectral untuk memaksakan standardisasi URL API (misal: *kebab-case*, versi semantik pada path).
  - Validasi *JSON Schema* pada contoh muatan (*payload examples*).
- [Modul 08.3: CI/CD Pipelines: GitHub Actions, Lychee, & Deployment](./08-otomatisasi-kualitas-dan-ci/03-ci-pipeline-dan-deployment.md)
  - Membangun GitHub Actions Workflow: Menjalankan Vale, Spectral, dan pengujian tautan (`lychee-action`).
  - Mekanisme *Ephemeral Preview Environments* (menggunakan Vercel, Netlify, atau Cloudflare Pages) untuk setiap Pull Request.
  - Otomatisasi *Release Notes* menggunakan Conventional Commits dan semantic-release.

---

### [Bab 09: Authoring Code Samples, SDK Docs, & CLI Guides](./09-code-samples-sdk-dan-cli/README.md)
*Menyusun panduan penggunaan kode, dokumentasi SDK multi-bahasa, dan petunjuk operasional terminal.*
- [Modul 09.1: Desain Cuplikan Kode Multi-Bahasa yang Testable](./09-code-samples-sdk-dan-cli/01-testable-code-samples.md)
  - Masalah *Rotting Code Snippets*: Mengapa copy-paste dokumentasi sering gagal di tangan pengembang.
  - Pola transklusi cuplikan kode langsung dari repositori contoh uji coba yang melewati *unit tests*.
  - Merancang komponen *tabbed code blocks* yang sinkron (Node.js, Python, Go, cURL, Java).
- [Modul 09.2: Dokumentasi Command Line Interface (CLI) & Man Pages](./09-code-samples-sdk-dan-cli/02-dokumentasi-cli-dan-terminal.md)
  - Anatomi perintah CLI: Positional arguments, flags (`--flag`, `-f`), environment variables, dan subcommands.
  - Auto-generasi dokumentasi CLI dari basis kode menggunakan Cobra/Afero (Go), Click (Python), atau Commander (Node.js).
  - Menyusun panduan instalasi berbasis package manager (Homebrew, APT, NPM, Pip).

---

### [Bab 10: Governance, Observability, Metrics, & Content Lifecycle](./10-governance-metrics-dan-lifecycle/README.md)
*Mengelola operasi siklus hidup konten jangka panjang, analitik kegunaan, dan ekspansi multibahasa.*
- [Modul 10.1: Content Health: Doc Decay, Deprecation, & Versioning](./10-governance-metrics-dan-lifecycle/01-content-health-dan-lifecycle.md)
  - Audit kesegaran dokumen (*Doc Freshness Audits*) dan pelabelan konten *stale* secara otomatis.
  - Protokol *Deprecation Lifecycle*: Cara mendokumentasikan fitur atau API yang usang tanpa merusak alur kerja integrasi eksisting.
  - Strategi pemeliharaan dokumentasi multi-versi (*long-term support / LTS versions vs current*).
- [Modul 10.2: Analytics Dokumentasi, Feedback Loops, & Globalisasi (i18n)](./10-governance-metrics-dan-lifecycle/02-analytics-feedback-dan-i18n.md)
  - Metrik efektivitas dokumentasi: Analisis *Time-to-First-Hello-World (TTFHW)*, rasio defleksi tiket support, dan *Upvote/Downvote CSAT widgets*.
  - Menghubungkan analitik pencarian (kata kunci tanpa hasil) dengan pembuatan *backlog* penulisan.
  - Alur kerja lokalisasi (*i18n/l10n*): Integrasi Crowdin atau Weblate ke dalam repositori berbasis Git.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title
**"NexusPay Global: Enterprise Payment Gateway Developer Portal & Docs-as-Code Engine"**

### Scenario
Anda ditunjuk sebagai *Lead Documentation Engineer* di **NexusPay Global**, sebuah perusahaan *fintech unicorn* yang sedang merilis sistem *Core Payment Engine v2*. Portal pengembang yang ada saat ini tersebar di wiki Confluence internal, berkas README yang usang, serta file Postman yang tidak tersinkronisasi. Tim rekayasa sering menerima komplain bahwa integrasi API memakan waktu berminggu-minggu, tingkat tiket integrasi melonjak 40%, dan cuplikan kode pada dokumentasi sering memunculkan error `401 Unauthorized` atau skema JSON tidak cocok.

### Persyaratan Arsitektur & Deliverables

#### 1. Information Architecture & Diátaxis Matrix
- Buat repositori portal berbasis SSG (**Astro Starlight** atau **Docusaurus v3**).
- Struktur konten portal harus mengimplementasikan framework Diátaxis secara ketat:
  - **1x Tutorial**: "Menerima Pembayaran Pertama Anda dalam 10 Menit menggunakan NexusPay SDK".
  - **2x How-To Guides**: 
    1. "Menangani Webhook Idempotency untuk Mencegah Transaksi Ganda".
    2. "Mengonfigurasi Pembayaran Lintas Batas dengan Protokol 3D-Secure 2.0".
  - **1x Architecture Explanation**: "Memahami Alur Konsensus Settlement dan Model Kegagalan Jaringan NexusPay".
  - **1x Complete API Reference**: Menggunakan OpenAPI 3.1 yang dikompilasi ke dalam tampilan interaktif.

#### 2. OpenAPI 3.1 Contract Specification
- Tuliskan berkas spesifikasi `openapi.yaml` (minimal 4 endpoints):
  - `POST /v2/charges` (Pembuatan transaksi)
  - `GET /v2/charges/{id}` (Cek status)
  - `POST /v2/refunds` (Refund parsial/penuh)
  - `POST /v2/webhooks/subscriptions` (Registrasi webhook endpoint)
- Spesifikasi wajib menyertakan:
  - Komponen skema `components/schemas` yang terperinci dengan tipe data valid, pattern regex, enum, dan deskripsi field.
  - Contoh payload request dan response untuk skenario sukses (`200`/`201`) serta skenario error teknis (`400 Bad Request`, `401 Unauthorized`, `422 Unprocessable Entity`, `429 Rate Limited`).
  - Skema autentikasi `securitySchemes` (Bearer JWT & Signature Header HMAC-SHA256).

#### 3. Visual Architecture (Diagrams-as-Code)
- Minimal 3 diagram yang dibuat sepenuhnya menggunakan kode (**Mermaid.js** atau **PlantUML**):
  - **Diagram C4 Context / Container**: Arsitektur integrasi antara sistem Merchant, Browser Klien, NexusPay Gateway, dan Jaringan Bank.
  - **Diagram Sequence (Alur Kerja)**: Alur jabat tangan transaksi asinkron dari inisiasi pembayaran hingga notifikasi webhook diterima merchant.
  - **Diagram State Machine**: Status siklus hidup transaksi pembayaran (`initiated`, `authorized`, `captured`, `failed`, `refunded`).

#### 4. Automated CI/CD Quality Gate (GitHub Actions)
Konfigurasikan pipeline CI komprehensif pada repository (`.github/workflows/docs-quality.yml`) yang mengeksekusi tahapan:
1. **Vale Prose Linter**:
   - Menerapkan `.vale.ini` kustom dengan vocabulary whitelist industri.
   - Mengaktifkan package `Google` style guide.
   - 1 custom rule: Melarang penggunaan kata non-teknis ambigu (misal: *simply*, *just*, *obviously*, *easy*).
2. **Spectral OpenAPI Linter**:
   - Memvalidasi `openapi.yaml` terhadap ruleset `spectral:oas`.
   - Menambahkan custom rule Spectral: Seluruh property dalam skema JSON wajib memiliki deskripsi (`description`) dan contoh nilai (`example`).
3. **Broken Link Checker**:
   - Menjalankan `lychee` untuk memeriksa setiap URL internal dan eksternal.
4. **Build & Automated Preview**:
   - Kompilasi portal secara headless untuk memastikan tidak ada kesalahan parsing MDX/JSX.

#### 5. Code Sample Harness
- Setiap cuplikan kode (*code sample*) yang muncul pada Tutorial atau How-To Guide harus bersumber dari berkas kode sumber yang nyata dan dapat diuji (*tested snippet*), ditransklusikan secara otomatis atau divalidasi oleh skrip penguji sebelum proses *build* dokumentasi.

### Kriteria Evaluasi Capstone
| Kategori Evaluasi | Bobot | Parameter Keberhasilan |
| :--- | :--- | :--- |
| **Arsitektur Informasi & Diátaxis** | 25% | Pemisahan fungsional jelas; tidak ada pencampuran penjelasan teori ke dalam tutorial aksi. |
| **Presisi Teknis OpenAPI & REST** | 25% | File OAS 3.1 valid 100%, payload error presisi, penggunaan HTTP status code akurat. |
| **Docs-as-Code Automation & CI** | 25% | Pipeline GitHub Actions berjalan hijau, mendeteksi pelanggaran Vale dan Spectral secara konsisten. |
| **Kualitas Komunikasi & Visual** | 15% | Diagram C4 & Sequence mudah dipahami, bebas beban kognitif yang tidak perlu; nada suara aktif (*imperative*). |
| **Developer Experience (DX) & UX** | 10% | Navigasi intuitif, kueri pencarian cepat, cuplikan kode mudah disalin tanpa eror format. |

---

> **Pedoman Pembelajaran:** Mulailah dari **Bab 01** untuk meletakkan pondasi metodologi secara sistematis sebelum melangkah ke otomasi dan penulisan spesifikasi API. Selesaikan seluruh modul mini-lab pada masing-masing subdirektori untuk mempersiapkan implementasi Capstone Project enterprise.