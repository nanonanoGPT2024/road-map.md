# BAB 05 - Quiz, Challenge, & Knowledge Check: Visual Systems, Typography, dan Color Science

Selamat! Anda telah menyelesaikan materi utama pada BAB 05 mengenai Visual Systems, Typography, dan Color Science.
Untuk memastikan pemahaman yang mendalam, silakan kerjakan kuis, challenge, dan evaluasi diri di bawah ini.

---

## A. Quiz

### Basic (Konsep Inti)
1. **Apakah perbedaan utama antara warna RGB dan CMYK, dan kapan masing-masing sebaiknya digunakan dalam Product Design?**
2. **Jelaskan konsep "Typeface" vs "Font"! Mengapa perbedaan istilah ini penting secara teknis dan historis?**
3. **Sebutkan dan jelaskan 3 properti utama dalam sistem warna HSL (Hue, Saturation, Lightness)!**
4. **Apa yang dimaksud dengan "Line Height" (Leading) dalam tipografi digital, dan bagaimana aturan umum dalam menentukannya agar teks nyaman dibaca?**
5. **Mengapa penggunaan warna absolut murni (seperti #000000 murni atau #FFFFFF murni) seringkali dihindari dalam desain UI modern?**

### Intermediate (Mekanisme Internal & Troubleshooting)
6. **Dalam mendesain sistem tipografi (Typography Scale), mengapa pendekatan berbasis rasio modular (Modular Scale seperti 1.250 Major Third) lebih disarankan daripada menetapkan ukuran font secara acak (misal 14px, 17px, 25px)?**
7. **Bagaimana Anda membedakan dan memilih antara format font WOFF, WOFF2, TTF, dan OTF untuk aplikasi web, dan bagaimana pengaruhnya terhadap performa (web performance)?**
8. **Ketika merancang dark mode (mode gelap), mengapa kita tidak bisa sekadar membalikkan (invert) nilai warna (dari putih ke hitam)? Bagaimana pendekatan sistematis yang benar untuk warna di dark mode?**
9. **Apa itu WCAG Color Contrast Ratio, dan bagaimana cara memastikannya memenuhi standar AA atau AAA (terutama pada teks di atas latar belakang warna tertentu)?**
10. **Anda menyadari bahwa render teks pada perangkat macOS (Retina display) dan Windows terlihat berbeda. Mengapa hal ini bisa terjadi (hint: subpixel antialiasing) dan bagaimana cara memitigasinya dari sisi frontend CSS?**

### Skenario Kasus Nyata Produksi
11. **Skenario 1:** Tim frontend mengeluh karena desainer UI seringkali menggunakan warna abu-abu (grey) yang tidak konsisten (terdapat lebih dari 35 jenis abu-abu di dalam codebase CSS). Sebagai Product Designer yang merancang Visual System, bagaimana langkah Anda dalam mengaudit dan menstandarisasi palet warna netral (neutral palette) agar mudah diimplementasikan melalui Design Token?
12. **Skenario 2:** Anda diminta merancang sistem tipografi untuk sebuah Dashboard SaaS yang padat data (data-heavy). Teks harus terbaca jelas pada ukuran kecil, dan angka pada tabel data tidak boleh bergeser saat nilainya berubah dari 99 ke 100. Karakteristik tipografi dan fitur CSS apa (seperti *tabular nums*) yang akan Anda pastikan hadir pada font yang dipilih?
13. **Skenario 3:** Aplikasi E-Commerce Anda sedang berekspansi ke pasar Timur Tengah, yang berarti akan mendukung bahasa Arab (Right-to-Left / RTL) di mana anatomi hurufnya berbeda dari huruf Latin. Bagaimana Anda menyesuaikan skala tipografi (line height, letter spacing) agar teks tetap optimal secara visual tanpa merusak layout komponen yang sudah ada?

---

## B. Chapter Challenge

### Tantangan: Membangun "Color & Typography Token System" untuk Multi-Brand
Anda diminta untuk membangun pondasi Design System untuk sebuah perusahaan yang memiliki dua produk (Brand A dan Brand B).
Masing-masing memiliki identitas brand yang berbeda, namun harus menggunakan arsitektur komponen kode yang sama di frontend.

**Kebutuhan:**
1. Desain hierarki *Design Token* untuk warna primer dan warna status (Sukses, Peringatan, Error). Token tidak boleh dinamakan dengan nama warnanya langsung (misal: `color-red`), melainkan berorientasi pada fungsi (misal: `color-danger`).
2. Rancang skala tipografi mulai dari `Heading 1` hingga `Caption` menggunakan Base Size 16px dan ratio *Perfect Fourth* (1.333).
3. Buatkan simulasi objek JSON yang mendefinisikan *Design Token* (Warna & Tipografi) tersebut yang bisa dikonsumsi oleh tim Frontend, mencakup varian Light dan Dark theme.

*Petunjuk:* Pertimbangkan struktur semantic tokens, global tokens, dan component tokens.

---

## C. Knowledge Check & Checklist

Gunakan bagian ini untuk mengevaluasi kesiapan Anda sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- Cara mata dan layar memproses cahaya/warna, serta keterbatasan color space (sRGB vs Display P3).
- Anatomi huruf dan prinsip dasar tata letak tipografi (kerning, tracking, leading, alignment).
- Aksesibilitas visual dasar, khususnya rasio kontras warna untuk teks.
- Konsep skalabilitas desain sistem (Design Tokens).

### Saya tidak perlu menghafal:
- Nilai eksak rasio *modular scale* hingga ke angka desimal terakhir (cukup pahami konsep rasionya).
- Semua nama standar WCAG dari memori (bisa menggunakan tools pemeriksa rasio).
- Seluruh kode warna heksadesimal.

### Saya harus bisa melakukan:
- Membuat sistem palet warna monokromatik dan komplementer dari satu warna *base*.
- Menghitung skala tipografi menggunakan base size dan rasio tertentu.
- Mengeksekusi pengecekan warna untuk memastikan lolos uji aksesibilitas (kontras).
- Menyusun panduan dasar (style guide) sederhana.

### Checklist Pembelajaran:
- [ ] Memahami konsep dasar Color Science (RGB, HSL, Color Gamut).
- [ ] Memahami perbedaan dan penerapan Typeface, Font, Serif, Sans-serif, dan Monospace.
- [ ] Bisa membuat palet warna sistematis menggunakan Hue, Saturation, dan Lightness scaling.
- [ ] Bisa membuat dan menghitung skala tipografi berbasis ratio modular.
- [ ] Bisa mendefinisikan Design Tokens sederhana dalam format terstruktur.
- [ ] Memahami trade-off dalam pemilihan web font (performa web vs estetika brand).
- [ ] Bisa melakukan debugging pada isu aksesibilitas kontras visual.
- [ ] Memahami implementasi sistem desain visual ini pada skenario nyata production.

Jika semua checklist sudah terpenuhi, Anda siap melangkah ke materi **BAB 06**!
