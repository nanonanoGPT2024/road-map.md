# BAB 01: Quiz, Challenge, & Knowledge Check
**Foundations & Architecture of Modern Design Systems**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Arsitektur Tokenisasi Berlapis (Multi-Tier Token Architecture)**  
   Jelaskan secara struktural dan konseptual perbedaan antara *Global/Primitive Tokens*, *Semantic/Alias Tokens*, dan *Component-Specific Tokens*. Mengapa mengabaikan layer *Semantic Tokens* dan langsung memetakan *Component Tokens* ke *Primitive Tokens* dikategorikan sebagai *anti-pattern* yang merusak skalabilitas *multi-brand* dan *theming*?

2. **Single Source of Truth (SSOT) & Token Transformation Pipeline**  
   Gambarkan siklus hidup sebuah token desain dari saat didefinisikan oleh tim UI/UX di *design tools* (misal: Figma Tokens/Variables) hingga dikonsumsi oleh *end-platform* yang heterogen (Web: CSS Variables/TypeScript, Android: Jetpack Compose XML/Kotlin, iOS: Swift/SwiftUI). Komponen komputasi apa saja yang esensial dalam *pipeline* otomatisasi tersebut (misal: Style Dictionary, AST parsing, formatting engines)?

3. **Komparasi Paradigma: Headless UI vs. Styled UI Kits**  
   Bandingkan arsitektur *Headless Component* (seperti Radix UI, React Aria, Ark UI) dengan arsitektur *Opinionated Styled Kits* (seperti Mantine, Material UI legacy). Analisis trade-off keduanya ditinjau dari aspek: *accessibility compliance* (ARIA state machines), beban pemeliharaan jangka panjang (*maintenance overhead*), fleksibilitas kustomisasi visual, dan ukuran *bundle runtime*.

4. **Monorepo Architecture & Package Boundaries**  
   Dalam membangun monorepo enterprise untuk Design System (misal menggunakan Turborepo atau Nx), bagaimana Anda mendefinisikan batasan paket (*package boundaries*) antara `@ds/tokens`, `@ds/primitives`, `@ds/icons`, `@ds/core-react`, dan `@ds/documentation`? Mengapa pencampuran *asset generation* (misal: konversi SVG ke React icon component) ke dalam paket *tokens* dianggap sebagai pelanggaran prinsip *Separation of Concerns*?

5. **Runtime Styling vs. Zero-Runtime / Compile-Time CSS**  
   Analisis dampak performa penggunaan *Runtime CSS-in-JS* (seperti Emotion, Styled-Components) versus *Zero-Runtime/Compile-Time Engine* (seperti Vanilla Extract, Panda CSS, StyleX) dalam konteks Design System skala besar yang diintegrasikan ke arsitektur SSR/RSC (Server-Side Rendering / React Server Components). Fokuskan jawaban pada *Total Blocking Time (TBT)*, *Cumulative Layout Shift (CLS)*, dan deduplikasi *style injection*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resolusi Sirkular dan Resolusi Token Dinamis pada Waktu Kompilasi**  
   Jika sebuah arsitektur token mendukung referensi bersarang (*nested aliases*, misal: `{color.interactive.hover}` -> `{color.interactive.base}` -> `{palette.blue.600}`), jelaskan mekanisme algoritma deteksi siklus (*cycle detection* menggunakan Directed Acyclic Graph / DAG) yang harus diimplementasikan oleh engine transformasi agar *infinite recursion* dapat dicegah sebelum tahap emisi CSS/TypeScript.

2. **Dilema Shadow DOM vs. Light DOM pada Design System Berbasis Web Components**  
   Sebuah tim memutuskan untuk mendistribusikan Design System menggunakan standar W3C Web Components agar bersifat *framework-agnostic*. Namun, mereka menghadapi masalah kebocoran token CSS (*CSS Custom Properties inheritance*) dan kesulitan melakukan *cross-root styling* untuk komponen majemuk (*compound components* seperti Dropdown Menu). Bagaimana cara mengatasi isolasi gaya Shadow DOM tanpa merusak enkapsulasi *native* komponen?

3. **Debugging Tree-Shaking Failure dan Barrel Files Anti-Pattern**  
   Aplikasi konsumen melaporkan bahwa mengimpor satu buah komponen tombol (`import { Button } from '@ds/core'`) menyebabkan seluruh ikon, grafik, dan dependensi komponen berat (seperti DatePicker dan Modal) ikut terbawa ke dalam *production bundle*. Lakukan root-cause analysis terhadap konfigurasi `package.json` (`sideEffects`, `exports`, module formats `CJS` vs `ESM`) dan struktur *barrel file* (`index.ts`). Bagaimana solusi refaktorisasi arsitektur modulnya?

4. **Polymorphic Component Type Safety**  
   Perhatikan implementasi komponen polimorfik berikut:
   ```typescript
   type BoxProps<T extends React.ElementType> = {
     as?: T;
     children: React.ReactNode;
   } & React.ComponentPropsWithoutRef<T>;

   function Box<T extends React.ElementType = 'div'>({ as, ...props }: BoxProps<T>) {
     const Component = as || 'div';
     return <Component {...props} />;
   }
   ```
   Sebutkan dan jelaskan dua kelemahan fatal tipe data di atas, khususnya terkait: penanganan atribut `ref` (*polymorphic ref forwarding* / `ComponentPropsWithRef`) dan *type-widening/property collisions* jika atribut bawaan elemen HTML bertabrakan dengan *custom props* Design System. Bagaimana pola implementasi standar industrinya?

5. **Hydration Mismatch & Flash of Unstyled/Incorrect Theme (FOUT/FOT)**  
   Pada arsitektur Next.js (App Router) dengan tema ganda (Light/Dark/System Preference), jelaskan mengapa pembacaan preferensi tema dari `localStorage` via React `useEffect` selalu menghasilkan *Flash of Incorrect Theme* atau memicu *Hydration Mismatch error*. Rancang alur eksekusi kritis (*critical rendering path*) menggunakan teknik *inline blocking script* atau *cookie-based server injection* untuk mengatasinya secara deterministik.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Performa & Theming Flash pada E-Commerce Skala 50M MAU
Sebuah platform e-commerce meluncurkan *rebranding* multi-brand (mengakomodasi 3 brand anak perusahaan dalam 1 basis kode). Tim menggunakan pendekatan CSS Custom Properties yang di-inject via atribut `data-theme` pada tag `<body>`. Ketika diuji coba pada *peak traffic*, terjadi lonjakan drastis pada metrik First Input Delay (FID) dan Total Blocking Time (TBT) di perangkat *low-end mobile*, disertai *style recalculation* berkepanjangan (Layout Thrashing) setiap kali user berpindah halaman atau berganti varian warna produk.
- **Pertanyaan Diagnostik:**
  1. Mengapa penempatan ribuan *CSS Custom Properties* di level *root* (`:root` atau `body[data-theme="brand-a"]`) dapat memicu overhead komputasi pada *style recalculation engine* di browser Blink/Webkit?
  2. Bagaimana Anda merestrukturisasi hierarki *scoping* token dan teknik *chunking* CSS agar mutasi tema bersifat lokal (*sub-tree invalidation*) alih-alih me-revalidasi seluruh DOM tree?

### Skenario B: Version Skew & Token Collision pada Microfrontends (Module Federation)
Perusahaan fintech mengadopsi arsitektur Microfrontend (MFE) menggunakan Webpack Module Federation, di mana tim Checkout (Remote) dan tim Dashboard (Host) dideploy secara independen. Tim Checkout memperbarui `@ds/tokens` ke versi 3.0.0 (yang mengubah nilai `--ds-space-md` dari `16px` menjadi `12px` dan mengubah format palet warna hex ke HSL), sementara Host masih berjalan di versi 2.4.0. Ketika Remote Checkout dimuat ke dalam Host, terjadi *visual corruption* dan layout yang hancur di seluruh aplikasi Host.
- **Pertanyaan Diagnostik:**
  1. Secara mekanistik, mengapa deklarasi CSS Custom Properties bersifat global dan rentan terhadap tabrakan versi (*race conditions* / *last-write-wins*) dalam arsitektur Module Federation?
  2. Rancang strategi arsitektural untuk isolasi token yang mencakup: isolasi *namespace/scoping*, *shared dependency negotiation* pada bundler, dan *fallback mechanism* tanpa harus memaksa deployment monolitik secara bersamaan (*lockstep deployment*).

### Skenario C: Migrasi Runtime CSS-in-JS Menuju Server Components & Multi-Platform
Sistem perbankan korporat memiliki 120 komponen kompleks yang ditulis menggunakan Emotion (`@emotion/react` dan `@emotion/styled`). Organisasi memutuskan untuk memigrasikan web portal ke Next.js RSC sekaligus bersiap mengekspansi komponen ke aplikasi mobile (React Native via cross-platform library seperti Tamagui atau React Native Web). Namun, anggaran engineering tidak mengizinkan penulisan ulang (*rewrite*) secara sekaligus (Big Bang approach).
- **Pertanyaan Diagnostik:**
  1. Identifikasi *hard-blocker* fundamental arsitektur Runtime CSS-in-JS jika dijalankan di dalam lingkungan React Server Components (RSC) streaming.
  2. Rancang strategi transisi arsitektural bertahap (dual-engine compilation) yang memungkinkan komponen legacy Emotion tetap berjalan berdampingan dengan komponen berbasis zero-runtime/compile-time baru, sambil menjaga konsistensi injeksi design tokens dan memastikan tidak terjadi *double styling bundle overhead*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Multi-Tier Token Engine & Headless Component Contract
**Deskripsi Tantangan:**  
Rancang dan implementasikan sebuah *micro-architecture* fondasi Design System yang mengotomatisasi pipeline token multi-tier hingga menjadi sebuah komponen *headless accessible button* dengan dukungan CSS custom properties yang aman terhadap tipe data (*type-safe*).

#### Requirements:
1. **Token Definition (JSON):**
   - Buat struktur data token yang memisahkan **Primitive** (`color.blue.500`, `spacing.4`), **Semantic** (`color.background.primary`, `color.interactive.default`), dan **Component-tier** (`button.color.background`).
2. **Transform Engine (Node.js/TypeScript Script):**
   - Bangun sebuah script transformasi sederhana (menggunakan TypeScript murni atau memanfaatkan library seperti Style Dictionary) yang membaca JSON tersebut dan mengekstrak:
     - File CSS Variables (`tokens.css`).
     - File definisi tipe TypeScript (`tokens.d.ts` / typed token mapping) yang mengekspos representasi token yang valid.
3. **Headless & Type-Safe Polymorphic Component:**
   - Implementasikan komponen `<Button />` di React/TypeScript yang:
     - Mendukung polimorfisme via prop `as` (default to `'button'`), lengkap dengan *forwarding ref* yang presisi (menggunakan tipe `PolymorphicRef`).
     - Menyediakan *state attributes* untuk aksesibilitas (misal: `aria-disabled`, `data-loading`, `data-variant`).
     - Mengonsumsi variabel token yang di-generate via *data-attributes* atau *scoped classnames* tanpa menyematkan *inline styles* statis yang tidak modular.

#### Constraints:
- Dilarang menggunakan runtime CSS-in-JS (Emotion, Styled-Components). Wajib menggunakan CSS Custom Properties murni atau *compile-time mechanism* (CSS Modules / Vanilla Extract).
- Sistem token wajib memiliki validasi minimal 1 lapis pencegah *broken reference* (contoh: jika semantic token mereferensikan primitive token yang tidak ada, proses build harus melempar `Error` deskriptif).
- Strict TypeScript: Dilarang menggunakan `any` eksplisit maupun implisit.

#### Expected Output:
- Struktur direktori fungsional:
  ```text
  ├── tokens/
  │   ├── primitive.json
  │   ├── semantic.json
  │   └── component.json
  ├── scripts/
  │   └── build-tokens.ts
  ├── src/
  │   ├── components/
  │   │   ├── Button.tsx
  │   │   ├── Button.types.ts
  │   │   └── Button.module.css
  │   └── tokens/
  │       ├── generated.css
  │       └── generated.ts
  ```
- Potongan kode implementasi `build-tokens.ts`, `Button.tsx`, dan `Button.types.ts` yang siap dikompilasi, lengkap dengan pengujian kasus aksesibilitas keyboard (`Enter` & `Space` handling ketika diekspansi sebagai tag non-button).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi formal 3-Tier Design Tokens (Primitive -> Semantic -> Component) beserta rasionalisasi decoupling-nya.
- [ ] Batasan teknis arsitektur Monorepo untuk Design System (kapan memisahkan paket, strategi circular dependency resolution antar-paket internal).
- [ ] Perbedaan kritis antara Runtime CSS-in-JS, Compile-time CSS-in-JS, dan Atomic CSS terhadap pipeline browser rendering (Parse HTML -> Recalculate Styles -> Layout -> Paint -> Composite).
- [ ] Standar WCAG 2.1/2.2 level AA/AAA yang berdampak langsung pada level arsitektur token (rasio kontras warna, skala tipografi non-linier, state focus ring).
- [ ] Strategi SemVer (Semantic Versioning) dan penanganan Breaking Changes pada level API Komponen vs. level Nilai Desain Visual Token.

### Saya tidak perlu menghafal:
- [ ] Sintaks konfigurasi spesifik Style Dictionary untuk seluruh target platform (iOS, Android, Web); cukup memahami paradigma *Parser*, *Transform*, dan *Format*.
- [ ] Seluruh kode heksadesimal atau skala numerik sistem warna tertentu (misal: Tailwind atau Material Design palette).
- [ ] Implementasi manual ARIA design patterns untuk komponen komposit ekstrem (misal: *Data Grid* atau *Date-Range Picker*); serahkan pada state engine *headless* terspesialisasi.

### Saya harus bisa melakukan:
- [ ] Membangun build-pipeline yang mengompilasi raw token JSON/W3C Community Group format ke platform target (CSS Vars, TypeScript object, Tailwind config).
- [ ] Mengonfigurasi `package.json` untuk *modern package publishing* menggunakan field `exports`, `typesVersions`, serta flag `sideEffects: false` guna menjamin *100% Tree-shaking efficiency*.
- [ ] Menulis polymorphic component engine di TypeScript yang aman secara type-checking, mendukung forward-ref, dan bebas dari *type-widening collision*.
- [ ] Menganalisis dan mendiagnosis degradasi performa render web akibat *dynamic style injection* menggunakan Chrome DevTools Performance Profiler.
- [ ] Mengisolasi token scope antar aplikasi di lingkungan microfrontend untuk mencegah kebocoran CSS global.