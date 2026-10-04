# BAB 02: Quiz, Challenge, & Knowledge Check
**Design Tokens Architecture & Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Token Taxonomy & Tiering System**  
   Jelaskan secara arsitektural perbedaan antara *Global/Primitive Tokens*, *Semantic/Alias Tokens*, dan *Component-Specific Tokens*. Mengapa *direct binding* dari UI Component langsung ke *Primitive Tokens* dianggap sebagai *anti-pattern* fatal dalam arsitektur design system skala enterprise?

2. **DTCG (Design Tokens Community Group) Specification**  
   Standar W3C DTCG memperkenalkan format `$value`, `$type`, dan `$description`. Bagaimana format formal ini menangani interoperabilitas tipe data kompleks (*composite tokens*) seperti `typography` dan `shadow` saat ditranspilasikan ke platform yang tidak memiliki konsep native 1:1 terhadap CSS (misalnya Jetpack Compose di Android atau Swift/SwiftUI di iOS)?

3. **Graph Resolution & Token Referencing**  
   Dalam engine resolusi token (misalnya Style Dictionary), bagaimana mekanisme traversal dilakukan ketika sebuah *Component Token* mereferensikan *Semantic Token*, yang kemudian mereferensikan *Primitive Token*? Jelaskan implikasi kompleksitas waktu komputasi jika dependency graph token dimodelkan sebagai Directed Acyclic Graph (DAG).

4. **Static Compilation vs Dynamic Runtime Tokens**  
   Bandingkan arsitektur *build-time token compilation* (menghasilkan static Sass/CSS variables, TS constants, XML, Swift files) dengan *runtime token injection* (menggunakan dynamic CSS Custom Properties yang dimutasi via JavaScript/DOM API). Analisis trade-off keduanya ditinjau dari sisi:
   * First Contentful Paint (FCP) & layout shift.
   * Runtime memory footprint pada aplikasi mobile/web view.

5. **Color Space & Perceptual Uniformity dalam Primitive Tokens**  
   Mengapa sistem penamaan token warna berbasis sRGB heksadesimal tradisional mulai ditinggalkan untuk token primitif enterprise, dan digantikan oleh perceptual color spaces seperti Oklch atau Display P3? Hubungkan jawaban Anda dengan matematisasi kontras warna (APCA) dan konsistensi visual saat melakukan programmatic shading/tinting via design tokens.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Circular Dependency Detection dalam AST Engine**  
   Bayangkan Anda mengimplementasikan custom token engine parser. Berikan representasi algoritma atau pseudocode untuk mendeteksi *circular references* (misalnya: `{color.brand.primary}` mereferensikan `{color.alias.interactive}`, yang secara tidak sengaja kembali mereferensikan `{color.brand.primary}`) sebelum fase emisi artifact dilakukan. Bagaimana strategi reporting error yang ideal bagi UI engineer?

2. **CSS Custom Properties Scope & Inheritance Leaks**  
   Diberikan skenario di mana token diterapkan melalui CSS Variables pada root:
   ```css
   :root {
     --sys-color-surface: #ffffff;
     --sys-color-on-surface: #111111;
   }
   [data-theme="dark"] {
     --sys-color-surface: #121212;
     --sys-color-on-surface: #eeeeee;
   }
   ```
   Jika terdapat micro-frontend atau isolated Web Component (Shadow DOM) yang dirender di dalam DOM tree, jelaskan mengapa mekanisme inheritance CSS variable di atas dapat pecah (*style leaking* atau *unresolved variables*), dan bagaimana solusi arsitektur CSS containment untuk mengatasinya tanpa runtime overhead.

3. **Composite Token Flattening untuk Non-Web Platforms**  
   Sebuah token tipografi didefinisikan sebagai composite object:
   ```json
   {
     "fontFamily": { "$value": "Inter" },
     "fontSize": { "$value": "16px" },
     "lineHeight": { "$value": "1.5" },
     "fontWeight": { "$value": "600" }
   }
   ```
   Jelaskan transformasi AST yang harus dilakukan transformer engine untuk memetakan token ini ke:
   * **iOS (UIKit / SwiftUI):** Objek `UIFont` / `Font` + dynamic type tracking.
   * **Android (Jetpack Compose):** `TextStyle` dengan `sp` units dan platform-safe font weight mapping.

4. **Tree-Shaking & Bundle Size Elimination pada Typescript Token Output**  
   Banyak design system mengekspor token sebagai single nested JavaScript object raksasa:
   ```typescript
   export const tokens = { color: { ... }, spacing: { ... }, ... };
   ```
   Mengapa pendekatan ini merusak mekanisme tree-shaking pada Webpack/Rollup/ESBuild? Rancang struktur ekspor dan konfigurasi target modul TypeScript yang menjamin aplikasi konsumen hanya membayar byte cost untuk token yang benar-benar di-import.

5. **Debugging Token Transform Pipeline Failure**  
   Saat menjalankan CI build untuk kompilasi token, tim Android melaporkan build error karena token `elevation-level-3` menghasilkan nilai `box-shadow` CSS (`0px 4px 8px rgba(0,0,0,0.15)`), bukan format dimensional `elevation` (dp) yang valid untuk Android XML/Compose. Di layer pipeline mana (Filter, Transformer, Format) bug ini harus diisolasi, dan bagaimana unit test untuk mencegah regresi ini ditulis?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: White-Label Multi-Brand Token Explosion & Performance Degradation
Anda adalah Principal Architect di perusahaan FinTech unicorn yang memiliki 1 core engine web application yang di-whitelabel untuk 35 bank rekanan. Setiap bank memiliki identitas visual (brand primitives), dark/light mode, dan regulasi aksesibilitas sendiri-sendiri. 
Saat ini, build pipeline mengompilasi CSS variables untuk ke-35 brand sekaligus ke dalam satu bundle monolithic CSS sebesar 8.5 MB, menyebabkan degradasi drastis pada Core Web Vitals (FCP naik dari 0.8s menjadi 3.9s) dan terjadi FOUC (*Flash of Unstyled Content*) saat user berganti tenant.

* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda merestrukturisasi token storage (DAG) dan pipeline build agar kompilasi bersifat decoupled per brand?
  2. Rancang strategi pengiriman (delivery strategy) token ke runtime browser: Bagaimana mekanisme dynamic injection dilakukan secara zero-runtime-cost tanpa menyebabkan FOUC ataupun bundle bloat?

### Skenario B: Race Condition & Stale Cache pada Hybrid Super-App (Web-Native Bridge)
Sebuah super-app e-commerce mengombinasikan Native Shell (Kotlin/Swift) dan puluhan micro-frontends (React/Next.js) via WebView. Design token dikelola secara dinamis via remote configuration service agar tim visual dapat mengubah campaign theme secara real-time tanpa app-store release.
Namun, di lapangan terjadi insiden: Saat user berpindah dari native home screen ke checkout page (WebView), terjadi *split-theme rendering*—warna primary pada Native sudah berubah menjadi warna campaign (misal: Merah), namun micro-frontend checkout masih menggunakan cached tokens lama (Biru). Lebih buruk lagi, terjadi micro-stuttering karena runtime script di WebView mengeksekusi blocking DOM injection untuk ribuan CSS variables.

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi *single point of failure* dari sinkronisasi state token antara native context dan webview runtime.
  2. Rancang arsitektur sinkronisasi token hybrid yang deterministik, memanfaatkan IPC/Bridge yang thread-safe, lengkap dengan strategi caching (fallback offline) dan non-blocking theme mutation.

### Skenario C: Systemic Breaking Changes Migration (Deprecation & Alias Re-mapping)
Design System v1 menggunakan semantic token yang tidak konsisten: `{ "color-background-cta": "#0052CC" }`. Pada Design System v2, arsitektur diubah mengikuti strict role-based taxonomy: `{ "color-surface-action-primary-default": "#0052CC" }`.
Terdapat lebih dari 450 repositori downstream mikro-frontend yang masih mengonsumsi token v1. Melakukan direct break akan melumpuhkan deployment harian perusahaan.

* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda mendesain *Alias Redirection Layer* pada level token schema untuk mempertahankan backward compatibility tanpa menduplikasi ukuran output artifact?
  2. Rancang ekosistem tooling (misalnya AST codemod script & automated linting deprecation warning) yang memungkinkan migrasi bertahap secara self-healing bagi 450 tim downstream.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multi-Platform Token Engine Architecture
**Deskripsi Tantangan:**  
Rancang dan bangun sebuah prototype *Design Token Build Engine* modular berbasis Node.js/TypeScript yang memproses W3C DTCG-compliant JSON tokens dan mendistribusikannya ke multi-platform target dengan proteksi integritas arsitektural.

#### Requirements:
1. **DAG Graph Validation:**
   * Engine harus membaca direktori berisi file JSON token: `primitives/`, `semantics/`, dan `components/`.
   * Harus mampu mendeteksi dan melempar exception fatal jika terjadi *circular dependency* antar token dengan visualisasi dependency path yang bermasalah (contoh: `a -> b -> c -> a`).
   * Harus melempar exception jika semantic/component token mereferensikan alias yang *undefined* (dead reference).
2. **Multi-Brand Theming Matrix:**
   * Mampu menerima parameter context: `Brand` (misal: `BrandA`, `BrandB`) dan `Mode` (misal: `Light`, `Dark`).
   * Engine melakukan *deep-merge* deterministik: `Primitives -> Semantic Base -> Brand Overrides -> Mode Overrides`.
3. **Multi-Target Exporters:**
   * **Web:** CSS Custom Properties file (`tokens.css`) yang ter-scope rapi dan TypeScript definitions (`tokens.d.ts`) dengan *const assertions* yang strictly-typed.
   * **Mobile Primitive Export:** JSON ter-flatten yang memvalidasi bahwa seluruh ukuran `px` dikonversi ke unit native (`rem` untuk Web, `pt` untuk iOS, `dp` untuk Android).
4. **Contrast Ratio Auditing Gate (Accessibility CI):**
   * Buat transform step yang secara otomatis menghitung contrast ratio antara token pasangan (misal: `{color.surface.default}` vs `{color.on-surface.default}`).
   * Jika rasio kontras < 4.5:1 (WCAG AA standard untuk normal text), build harus melempar warning atau fail (configurable via CLI flag `--strict-a11y`).

#### Constraints:
* Tidak boleh menggunakan dependensi Style Dictionary core secara langsung (Anda diminta mengimplementasikan pipeline resolver dan transformer core sendiri untuk memahami mekanika internalnya).
* Format input wajib 100% compliant terhadap spesifikasi W3C Design Tokens Community Group (menggunakan prefix `$` untuk `$value`, `$type`, dll).

#### Expected Output:
1. Direktori repositori script engine (clean code, fully typed TypeScript).
2. Sample data tokens: `primitives.json`, `semantic.json`, `brands/brand-a.json`, `brands/brand-b.json`.
3. CLI runner script: `npm run build:tokens -- --brand=brand-a --mode=dark --strict-a11y`.
4. Artifacts ter-generate di folder `/dist` yang mencakup CSS, TS declarations, dan Accessibility Validation Report dalam format JSON.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi token berjenjang: Global/Primitive -> Semantic/Alias -> Component-Specific, dan konsekuensi coupling bila tiering dilanggar.
- [ ] Format spesifikasi W3C Design Tokens Community Group (DTCG), termasuk properti `$value`, `$type`, `$description`, dan composite tokens.
- [ ] Algoritma traversal Directed Acyclic Graph (DAG) untuk resolving deep alias references serta deteksi circular dependency.
- [ ] Perbedaan implementasi teknis token di Web (CSS variables), iOS (Asset Catalogs/Swift constants), dan Android (XML/Compose theme).
- [ ] Strategi theming multi-brand dan dynamic mode switching (Dark/Light) pada skala enterprise tanpa FOUC.
- [ ] Trade-off performa antara static token emission (compile-time) dan dynamic CSS injection (run-time).
- [ ] Evaluasi mathematical color spaces (RGB vs HSL vs Oklch/Display-P3) dan kepatuhan a11y (WCAG / APCA) dalam token generation.

### Saya tidak perlu menghafal:
- [ ] Sintaks exact file konfigurasi internal tool pihak ketiga (misalnya syntax regex parser config internal Style Dictionary v3/v4).
- [ ] Nilai hex atau string token individual perusahaan tertentu.
- [ ] Seluruh formula kalkulasi matematika luminansi Oklch/APCA secara detail di luar pemahaman konsep persepsi kontras visualnya.

### Saya harus bisa melakukan:
- [ ] Menulis arsitektur JSON tokens yang valid sesuai spesifikasi DTCG untuk primitive, semantic, dan component tiers.
- [ ] Mengonfigurasi dan meng-extend pipeline Style Dictionary (atau custom token engine) dengan Custom Actions, Filters, Transforms, dan Formats.
- [ ] Mendiagnosis dan memperbaiki masalah *circular references* dan *unresolved token aliases* pada build pipeline design system.
- [ ] Menghasilkan output tipografi dan shadow tokens yang kompatibel lintas platform (Web, iOS, Android) secara otomatis.
- [ ] Mengimplementasikan script codemod/AST untuk migrasi otomatis token deprecated di codebase aplikasi konsumen.
- [ ] Membangun automated contrast-ratio checker pada CI pipeline kompilasi design tokens untuk menjamin standard accessibility sebelum rilis.