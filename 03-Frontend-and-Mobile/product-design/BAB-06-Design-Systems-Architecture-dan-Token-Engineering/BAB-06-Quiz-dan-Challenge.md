# BAB 06 — Design Systems Architecture & Token Engineering: Quiz dan Challenge

## Tujuan Pembelajaran
Dokumen ini berisi kuis dan tantangan untuk menguji pemahaman Anda terkait Arsitektur Design System dan Token Engineering. Silakan kerjakan tanpa melihat langsung jawabannya. Jika membutuhkan validasi, berikan jawaban Anda dan minta sistem untuk mengevaluasi.

---

## A. Basic Quiz (Konsep Inti)
1. Apa perbedaan utama antara Design Variables (biasa) dengan Design Tokens dalam sebuah arsitektur Design System?
2. Sebutkan tiga tiering (tingkatan) standar dari Design Tokens (misalnya: Global/Primitive, Semantic/Alias, Component-specific) dan jelaskan fungsi masing-masing.
3. Mengapa *hardcoding* nilai warna (misal: `#FF0000`) pada komponen UI sangat tidak disarankan dalam sistem berbasis design token?
4. Apa peran format JSON atau YAML dalam penyimpanan Design Tokens secara platform-agnostic?
5. Bagaimana Design System Architecture membantu kolaborasi antara desainer UI/UX dengan software engineers?

---

## B. Intermediate Quiz (Mekanisme Internal & Troubleshooting)
1. Anda memiliki `color.brand.primary` yang nilainya mengarah ke `color.blue.500`. Ketika nilai `color.blue.500` diubah, seluruh komponen berubah kecuali satu komponen `Button` yang masih berwarna lama. Apa saja penyebab potensial dan bagaimana cara mendiagnosisnya?
2. Bagaimana cara kerja tools seperti Style Dictionary dalam mentransformasi Token JSON menjadi format yang bisa digunakan oleh berbagai platform (CSS, iOS Swift, Android XML)?
3. Jelaskan konsep *Theming* (misalnya Dark Mode dan Light Mode) menggunakan Semantic Tokens. Bagaimana arsitekturnya bekerja secara real-time pada aplikasi Frontend?
4. Saat melakukan *scale-up* Design System, mengapa disarankan memisahkan repository Design Tokens dari repository komponen UI utama? Apa *trade-off*-nya?
5. Tim menemukan bahwa bundle size aplikasi membengkak akibat semua token di-*load* sekaligus meskipun tidak terpakai. Strategi optimasi apa yang bisa diterapkan di sisi build-tool (seperti Webpack/Vite)?

---

## C. Scenario-based Questions (Kasus Nyata Produksi)
1. **Skenario Rebranding Skala Besar**: Perusahaan Anda baru saja diakuisisi dan seluruh warna brand, tipografi, serta spacing perlu disesuaikan di 5 aplikasi berbeda (3 Web, 1 iOS, 1 Android). Bagaimana Anda merencanakan peluncuran *update* token ini tanpa merusak UI yang sudah ada (backward compatibility)?
2. **Skenario Multi-Tenant / White-Labeling**: Anda sedang membangun aplikasi SaaS yang digunakan oleh berbagai klien (tenant). Setiap klien dapat mengatur warna utama, logo, dan radius border mereka sendiri. Bagaimana Anda mendesain arsitektur token yang mendukung *dynamic theming* di runtime?
3. **Skenario Sinkronisasi Figma ke Code**: Desainer Anda sering mengubah nilai token di Figma dan langsung meminta *engineer* mengimplementasikannya. Proses manual ini memakan waktu dan rentan error. Desainlah *pipeline* CI/CD sederhana yang dapat mengotomatisasi perubahan dari Figma (menggunakan Figma API) hingga menjadi *Pull Request* di repository Frontend.

---

## D. Chapter Challenge

### Tantangan: Membangun Pipeline Design Token (Design-to-Code)
**Problem:** Tim desain Anda menggunakan Figma Tokens (Tokens Studio). Mereka butuh cara agar setiap kali mereka melakukan "Push to GitHub" dari plugin tersebut, file JSON token tersebut otomatis terkompilasi menjadi CSS Variables dan TypeScript Interfaces.

**Requirements:**
1. Desainlah arsitektur *pipeline* yang menangkap *webhook* atau perubahan file JSON di repo.
2. Jelaskan langkah-langkah mem-parsing JSON yang mengandung Global, Alias, dan Component tokens.
3. Tuliskan contoh struktur JSON mentah dan hasil kompilasi akhirnya dalam bentuk CSS (`:root { ... }`).
4. (Opsional tapi direkomendasikan): Bagaimana Anda akan mendeteksi *breaking changes* (misalnya token dihapus) sebelum di-*merge* ke cabang `main`?

**Catatan:** Anda tidak perlu memberikan solusi instan berupa kode komplit, namun buatlah diagram alur (menggunakan teks/ASCII) dan contoh *snippet* transformasi logikanya.

---

## E. Knowledge Check

Silakan evaluasi diri Anda sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- Konsep dasar dan hirarki Design Tokens (Primitive, Semantic, Component).
- Cara kerja alat kompilasi token (contoh: Style Dictionary).
- Prinsip dasar Arsitektur Design System yang platform-agnostic.
- Pola Theming dan White-labeling.

### Saya tidak perlu menghafal:
- Nilai eksak warna dari palet (misal: hex code spesifik untuk Blue-500).
- Syntax konfigurasi spesifik Style Dictionary secara mendetail (bisa melihat dokumentasi).

### Saya harus bisa melakukan:
- Menganalisis file JSON Design Token dan mengetahui alur *reference*-nya.
- Mendiagnosis bug pada UI terkait token yang tidak sinkron.
- Merancang alur pipeline sederhana untuk distribusi token.

### Checklist Pembelajaran:
- [ ] Memahami konsep tokenisasi UI.
- [ ] Memahami cara kerja hirarki token.
- [ ] Bisa membuat contoh sederhana JSON Token.
- [ ] Bisa melakukan praktik kompilasi atau resolusi token.
- [ ] Bisa melakukan debugging sinkronisasi desain dan kode.
- [ ] Memahami trade-off pemisahan repository token.
- [ ] Bisa menerapkan dalam real-world case (seperti Theming).
