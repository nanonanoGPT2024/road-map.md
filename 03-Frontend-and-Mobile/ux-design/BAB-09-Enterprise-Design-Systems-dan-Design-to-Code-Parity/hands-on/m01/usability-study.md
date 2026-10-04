---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Approach A: Manual Redlining & Inspect | Approach B: Direct Figma-to-Code Codegen Plugins | Approach C: GitOps-Driven Token Architecture (Modul Ini) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Deployment Perubahan** | Lambat (Hari hingga Minggu) | Cepat (Hitungan Menit) | Menengah-Cepat (Sesuai Pipeline CI/CD, 5-15 Menit) |
| **Maintainability Skala Enterprise** | Sangat Buruk (High Entropy) | Buruk (Menghasilkan Spaghetti Code / Dead Props) | Sangat Tinggi (Struktur Terstandarisasi) |
| **Control & Code Quality Gate** | Tinggi (Review Engineer Manual) | Nol (Langsung overwrite tanpa review arsitektur) | Maksimal (Branch PR, Automated Tests, Strict Linting) |
| **Kompatibilitas Multi-platform** | Bergantung pada Engineer per platform | Web-Centric (Umumnya mengabaikan Mobile) | Universal (Style Dictionary compile ke CSS, Swift, Compose) |
| **Human Error Margin** | Sangat Tinggi (>30% inkonsistensi) | Menengah (Engine visual parsing error) | Mendekati Nol (Strict Contract Schemas & AST Linter) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Cycle Dependency Loops dalam Variable Aliasing:**
   * *Problem:* Designer di Figma meng-alias `color-bg-primary` ke `color-fill-base`, sementara desainer lain secara tidak sengaja meng-alias `color-fill-base` ke `color-bg-primary`.
   * *Mitigasi:* Compiler token wajib menyertakan siklus deteksi graf (Topological Sort / Tarjan’s Algorithm) saat resolve reference dan langsung memutus pipeline dengan exit code 1 sebelum men-generate artifact invalid.
2. **Precision Loss pada Nilai Alpha / Decimal Spacing:**
   * *Problem:* Figma menyimpan nilai float RGBA dalam rentang $0.0 - 1.0$ (misal: $0.1234567$). Pembulatan CSS ceroboh menghasilkan rendering banding pada display Retina.
   * *Mitigasi:* Tetapkan presisi deterministik minimum 4 desimal pada math rounding di transformer script.
3. **Ghost Tokens (Orphan Tokens):**
   * *Problem:* Variabel di Figma dihapus, namun token di repo masih ada karena engine hanya melakukan *append*, bukan *reconcile/prune*.
   * *Mitigasi:* Ingestion pipeline harus membersihkan direktori target (`rm -rf tokens/dist/*`) sebelum proses kompilasi fresh dari AST payload Figma.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

* **Mistake 1: Hardcoding Semantic Tokens ke Level Primitif Komponen.**
  * *Contoh Buruk:* `<Button style={{ backgroundColor: tokens.global.palette.blue[500] }} />`
  * *Solusi Parity:* Selalu gunakan Tier 2/3. `<Button style={{ backgroundColor: tokens.semantic.action.background.primary }} />`. Mengakses palette global secara langsung menghancurkan kapabilitas theming dark-mode otomatis.
* **Mistake 2: Memperlakukan Token sebagai Styling Murni (Bukan Design Contract).**
  * *Contoh Buruk:* Desainer mengubah spasi tanpa menyadari bahwa sistem *bounding box* tabel dependensi di production menggunakan fixed-size assumptions.
  * *Solusi Parity:* Validasi token perubahan melalui visual regression suites (Playwright) di level CI/CD sebelum PR di-merge otomatis.
* **Mistake 3: Desinkronisasi Naming Convention (Kebab-case vs CamelCase vs Snake_case).**
  * *Solusi Parity:* Standarisasikan normalizer tunggal di transformer. Apapun naming format yang dibuat di Figma (`Brand/Primary Color`), engine harus memetakannya secara konsisten sesuai platform conventions: `brand-primary-color` (CSS) dan `brandPrimaryColor` (TypeScript).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan W3C DTCG Format:** Jangan menciptakan schema JSON sendiri. Spesifikasi W3C Design Tokens Community Group adalah masa depan interoperabilitas toolings UI/UX global.
2. **Atomic Commits melalui Bot User:** Ekstraksi otomatis dari Figma harus di-commit oleh identity bot khusus (misal: `@omnipre-ds-bot`) dengan semantic commit message: `chore(tokens): sync tokens with figma library v1.4.2 [skip ci]`.
3. **Isolasi Token Package:** Tempatkan token dalam package tersendiri di monorepo (misal: `@enterprise/tokens`) yang tidak memiliki dependensi runtime framework UI apapun (agnostik terhadap React, Vue, maupun Svelte).
4. **Strict Typing via Const Assertions:**
