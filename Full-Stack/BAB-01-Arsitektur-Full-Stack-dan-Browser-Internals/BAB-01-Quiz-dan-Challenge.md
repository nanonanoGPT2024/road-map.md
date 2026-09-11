---
[⬅️ Module 02: Browser Rendering Pipeline](./Module-02-Browser-Rendering-Pipeline-DOM-Layout-Composite.md) | [📋 Silabus Induk](../README.md) | [BAB 02: React Internals & State ➡️](../BAB-02-React-Internals-dan-State-Management/Module-01-React-Fiber-Reconciler-Diffing-dan-Concurrent.md)
---

# BAB 01: Evaluasi Pemahaman, Quiz, & Tantangan Arsitektur Full-Stack & Browser Internals

Selamat! Anda telah menyelesaikan **BAB 01: Arsitektur Full-Stack Modern, Web Standards, & DOM/CSS Internals**. Lembar evaluasi ini menguji pemahaman konseptual dan ketajaman teknis Anda mengenai paradigma rendering web modern, proses hidrasi, arsitektur pipeline browser, serta optimasi Core Web Vitals.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan perbedaan mendasar antara Client-Side Rendering (CSR) dan Server-Side Rendering (SSR)!** Mengapa CSR murni sangat rentan terhadap penurunan peringkat SEO Google?
2. **Apa yang dimaksud dengan proses Hydration dalam arsitektur SSR modern?** Mengapa halaman yang sudah selesai dirender secara visual (FCP tercapai) belum tentu bisa langsung merespons klik tombol pengguna?
3. **Sebutkan dan jelaskan 3 metrik inti dalam Google Core Web Vitals (2024+)!** Berapa batas nilai (*Good Threshold*) untuk masing-masing metrik: LCP, INP, dan CLS?
4. **Jelaskan tahapan Critical Rendering Path (CRP) dari pembacaan byte mentah HTML hingga piksel muncul di monitor pengguna!**
5. **Apa perbedaan antara elemen HTML dengan `display: none` dan `visibility: hidden` dalam konstruksi Render Tree browser?**

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Mekanisme Terjadinya Hydration Mismatch:**
   Mengapa merender waktu saat ini menggunakan `new Date().toLocaleTimeString()` di dalam komponen React SSR memicu *Hydration Mismatch Warning*? Bagaimana pola *Two-Pass Rendering (useEffect Mount Guard)* memecahkan masalah ini secara elegan?
7. **Bahaya Forced Synchronous Layout (Layout Thrashing):**
   Perhatikan potongan kode berikut:
   ```javascript
   for (let i = 0; i < cards.length; i++) {
     const h = cards[i].offsetHeight;
     cards[i].style.height = (h + 10) + 'px';
   }
   ```
   Jelaskan secara mendalam mengapa perulangan di atas memicu puluhan kali reflow paksa (*Reflow Loop*) pada Main Thread! Bagaimana cara merefaktor kode tersebut menggunakan teknik *DOM Batching*?
8. **Analisis Biaya Properti CSS (Reflow vs Repaint vs Composite):**
   Mengapa menganimasikan menu dropdown menggunakan `transform: translateY(300px)` mampu menghasilkan 120 FPS mulus di GPU, sedangkan menganimasikan `top: 300px` sering memicu *Jank / Frame Drops*?
9. **Incremental Static Regeneration (ISR) vs Pure Static Site Generation (SSG):**
   Jika sebuah toko online memiliki 2.000.000 halaman produk, mengapa SSG murni tidak mungkin diterapkan pada proses build CI/CD? Bagaimana ISR memungkinkan halaman diperbarui secara inkremental di latar belakang tanpa me-rebuild seluruh situs?
10. **Aksesibilitas Web (WCAG a11y) & SEO:**
    Mengapa menggunakan tag `<button onClick={...}>` jauh lebih unggul dibandingkan `<div onClick={...}>` dari sudut pandang pembaca layar tunanetra (*Screen Readers*), navigasi keyboard tabulasi, dan ranking mesin pencari?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Lonjakan Bounce Rate pada Pengguna Mobile E-Commerce
Sebuah platform e-commerce fesyen memigrasikan website mereka ke SPA React murni (CSR). Setelah migrasi, tim pemasaran melaporkan lonjakan *Bounce Rate* sebesar 45% dari pengguna smartphone di luar kota besar yang menggunakan koneksi 4G/3G.
Setelah diaudit, ukuran bundle JavaScript utama mencapai 4.2 Megabyte, dan waktu rata-rata kemunculan konten pertama (*First Contentful Paint*) adalah **6.8 detik**.
- **Analisis:** Mengapa CSR murni menjadi malapetaka pada skenario ini?
- **Rekomendasi Arsitektur:** Rancang strategi migrasi ke SSR / ISR menggunakan Next.js, lengkap dengan teknik *Code Splitting*, *Dynamic Imports*, dan kompresi aset gambar modern (AVIF/WebP) untuk memangkas FCP di bawah 1.5 detik!

### Skenario B: Kasus Salah Klik Pengguna Akibat Cumulative Layout Shift (CLS)
Aplikasi portal berita online menayangkan banner iklan dinamis dari pihak ketiga di bagian atas artikel. Banner tersebut dimuat secara asinkron setelah 2 detik.
Ketika pembaca sedang membaca paragraf pertama dan hendak mengklik tautan artikel terkait, banner iklan tiba-tiba selesai dimuat dan mendorong seluruh teks ke bawah sejauh 250 piksel. Pembaca secara tidak sengaja mengklik iklan banner tersebut (*Accidental Click*). Nilai CLS halaman melonjak ke angka **0.42** (Sangat Buruk).
- **Identifikasi Kerusakan:** Pelanggaran Core Web Vitals apa yang terjadi di sini?
- **Solusi CSS & HTML:** Tuliskan deklarasi CSS (menggunakan `min-height`, `aspect-ratio`, atau layout skeleton reservation) agar browser mengunci ruang fisik banner sebelum iklannya selesai diunduh!

### Skenario C: Animasi Sidebar yang Macet pada Layar 120 Hz
Sebuah aplikasi web kolaboratif memiliki menu sidebar yang meluncur keluar saat tombol hamburger ditekan. Pada monitor developer (MacBook Pro ProMotion 120 Hz), animasi terasa patah-patah (*Stuttering*).
Saat dicek di Chrome DevTools Performance Profiler, CPU mengalami beban 100% pada fungsi kalkulasi layout style.
- **Investigasi Kode:** Ternyata developer menganimasikan CSS `left: -300px` ke `left: 0px` dengan `box-shadow` dinamis.
- **Remediasi 120 FPS:** Ubah implementasi CSS menjadi murni GPU Composited menggunakan `transform: translateX()`, `will-change`, dan pseudo-element opacity untuk bayangan!

---

## 4. Chapter Challenge: Desain Arsitektur Render High-Performance Media Portal

### Deskripsi Masalah
Anda ditunjuk sebagai Lead Frontend & Full-Stack Architect untuk portal berita olahraga nasional yang melayani 30.000.000 pengunjung unik bulanan:
1. **Halaman Beranda (Homepage):** Menampilkan berita utama terpanas dan widget skor pertandingan langsung (*Live Score*).
2. **Halaman Artikel Berita (2.000.000 Halaman):** Teks artikel statis dengan komentar pembaca di bagian bawah.
3. **Halaman Profil Pengguna (Private Dashboard):** Menampilkan status langganan koran digital dan riwayat bookmark.

### Instruksi Pengerjaan
Buat laporan arsitektur performa web yang memuat:
1. **Pemilihan Paradigma Render:** Tentukan paradigma terbaik (SSG, ISR, SSR Dinamis, atau CSR) untuk masing-masing dari 3 jenis halaman di atas, lengkap dengan justifikasi teknis dan analisis biaya komputasi server.
2. **Strategi Core Web Vitals Optimization:** Rancang arsitektur aset untuk menjamin:
   - $LCP \le 1.8 \text{ detik}$ (preload banner font & hero image).
   - $CLS \le 0.05$ (font display fallback swap & image aspect-ratio).
   - $INP \le 100 \text{ ms}$ (pemecahan long tasks via web worker).
3. **Solusi Hydration Mismatch:** Rancang pola sinkronisasi data server dan client untuk widget "Waktu Terakhir Diperbarui" yang aman dari mismatch.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Perbedaan trade-off antara CSR, SSR, SSG, ISR, dan Partial Prerendering (PPR).
- [ ] Siklus hidup Hydration dari `renderToString` server hingga `hydrateRoot` klien.
- [ ] 3 pilar Core Web Vitals (LCP, INP, CLS) dan dampaknya terhadap SEO Google.
- [ ] Setiap tahapan Critical Rendering Path (DOM -> CSSOM -> Render Tree -> Layout -> Paint -> Composite).
- [ ] Penyebab dan bahaya Forced Synchronous Layout (Layout Thrashing).
- [ ] Mengapa animasi berbasis GPU (`transform`, `opacity`) jauh lebih efisien daripada CPU Layout (`top`, `width`).

### Saya Tidak Perlu Menghafal:
- Rincian implementasi mesin C++ Blink layout engine (cukup pahami konsep tree dan lifecycle-nya).
- Seluruh spesifikasi biner parser token HTML5.

### Saya Harus Bisa Melakukan:
- [ ] Mengidentifikasi dan memperbaiki celah Hydration Mismatch pada aplikasi React SSR.
- [ ] Melakukan batching operasi baca dan tulis DOM untuk mengeliminasi Layout Thrashing.
- [ ] Mengoptimalkan aset web untuk mencapai skor hijau di Google PageSpeed Insights.
- [ ] Menulis animasi antarmuka 60-120 FPS bebas jank menggunakan akselerasi GPU.

---
[⬅️ Module 02: Browser Rendering Pipeline](./Module-02-Browser-Rendering-Pipeline-DOM-Layout-Composite.md) | [📋 Silabus Induk](../README.md) | [BAB 02: React Internals & State ➡️](../BAB-02-React-Internals-dan-State-Management/Module-01-React-Fiber-Reconciler-Diffing-dan-Concurrent.md)
---
