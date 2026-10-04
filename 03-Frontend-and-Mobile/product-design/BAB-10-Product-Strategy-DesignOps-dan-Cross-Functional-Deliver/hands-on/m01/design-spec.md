---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter | Manual Handoff (Figma Inspect) | Monorepo Shared Constants | Automated DesignOps Pipeline (DTCG + Style Dictionary) |
| :--- | :--- | :--- | :--- |
| **Integrasi Multi-Platform** | Sangat Buruk (Manual re-typing) | Sedang (Hanya mencakup TypeScript) | Unggul (Native Web, iOS, Android serentak) |
| **Siklus Update Design** | Hari hingga Minggu | 2–3 Hari | Menit (< 30 Menit via automated PR) |
| **Beban Infrastruktur** | Nol (Mengandalkan disiplin manusia) | Rendah (Hanya Node.js package) | Tinggi (Setup CI/CD, Parser, Transpiler, Repo Sync) |
| **Akurasi & Konsistensi** | Rendah (Rentan Human Error) | Tinggi untuk Web, Rentan Drift di Mobile | Sangat Tinggi (Determinik 100%) |
| **Skalabilitas Organisasi** | Terhambat pada > 2 Squad | Efektif sampai 5 Squad | Mampu mengelola puluhan Tim Skala Enterprise |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Circular Aliasing pada Token Resolving:**
   * *Bahaya:* Token A merujuk Token B, dan Token B merujuk Token A (`color-primary: {color-brand}`, `color-brand: {color-primary}`). Compiler akan mengalami *infinite recursion* / stack overflow.
   * *Mitigasi:* Jalankan algoritma *Cycle Detection* menggunakan representasi Directed Graph berbasis algoritma Tarjan atau DFS sebelum pemrosesan token dilakukan.

2. **Perbedaan Color Space Antar Platform:**
   * *Bahaya:* Hex `#FF0000` di Figma (Display P3) menghasilkan visual yang berbeda saat di-render pada CSS (secara default sRGB) atau Swift (`UIColor(displayP3Red:...)`).
   * *Mitigasi:* Konversi eksplisit semua nilai ke color-space target spesifik menggunakan CSS Color Module Level 4 `color(display-p3 r g b)` dan penyesuaian transform group native mobile.

3. **Inkompatibilitas Font Rendering Engine:**
   * *Bahaya:* Ukuran `line-height` dalam pixel absolut menyebabkan pemotongan teks (*clipping*) pada Dynamic Type iOS dan Android Text Magnification jika pengguna mengubah preferensi aksesibilitas perangkat.
   * *Mitigasi:* Jangan pernah mengompilasi `line-height` menjadi nilai absolut pixel untuk mobile. Gunakan *unitless ratio* (misalnya: `1.5` bukan `24px`).

---

## SEKSI 13 — COMMON MISTAKES

### 1. Menghubungkan Figma Langsung ke Repositori Produksi Tanpa Staging
* *Kesalahan:* Menggunakan webhook langsung yang melakukan trigger rilis package production tanpa fase testing dan peninjauan Pull Request.
* *Solusi:* Webhook Figma hanya boleh membuka **Draft Pull Request** di repository tokens. Pipeline CI wajib memvalidasi linting dan unit testing sebelum disetujui oleh Design Lead dan Tech Lead.

### 2. Menggunakan Nilai Arbitrer Tanpa Semantic Indirection
* *Kesalahan:* Menggunakan token seperti `blue-500` langsung di styling komponen tombol (`background: var(--blue-500)`).
* *Solusi:* Buat layer semantik: `blue-500` $\rightarrow$ `color-interactive-primary` $\rightarrow$ `button-primary-bg`. Ketika terjadi rebranding, layer komponen tidak perlu disentuh.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

* **W3C Design Token Community Group (DTCG) Standard:** Selalu gunakan format metadata standar industri terbaru (`$value`, `$type`, `$description`).
* **Semantic Versioning Sembrono:** Perubahan nilai token yang sudah ada (misalnya: warna primer berubah dari biru ke hijau) adalah **Minor Version**. Penghapusan atau pengubahan nama kunci token adalah **Breaking Change (Major Version)**.
* **Component-Level Scoping:** Batasi cakupan token ke level terkecil. Komponen kompleks (misal: Data Grid Table) harus memiliki variabel lokal yang merujuk ke token semantik, bukan memodifikasi token semantik global.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI

1. **Tree-Shaking Output TypeScript:** Jangan mengekspor satu object raksasa jika aplikasi hanya menggunakan sebagian token. Gunakan modular export per kategori domain (misalnya: `colors.ts`, `spacing.ts`, `typography.ts`).
2. **CSS Variable Footprint:** Hindari menghasilkan puluhan ribu CSS variable jika tidak digunakan. Pisahkan token global primitif dari artefak CSS akhir; kompilasi **hanya** token semantik dan token komponen ke dalam `:root`.
3. **Build Caching:** Manfaatkan hash-based caching pada pipeline CI. Jika isi direktori `tokens/*.json` tidak mengalami perubahan hash MD5/SHA256, *skip* seluruh tahapan Style Dictionary build.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Token Value Injection:**
   * *Vektor Serangan:* Nilai string pada token Figma disisipi payload malicious CSS/JS (misalnya: `url('javascript:alert(1)')` atau unescaped quotes).
   * *Hardening:* Jalankan parser regex validasi ketat sebelum kompilasi:
