# BAB 03 - Quiz dan Challenge: Arsitektur Informasi & Mental Models

## Tujuan
Dokumen ini dirancang untuk menguji pemahaman teoritis dan kemampuan praktis Anda mengenai Arsitektur Informasi (Information Architecture - IA) dan Mental Model pengguna dalam desain produk.

---

## A. Quiz Basic (Konsep Inti)

1. **Definisi Arsitektur Informasi**: Jelaskan apa yang dimaksud dengan Arsitektur Informasi (IA) dalam konteks desain produk digital, dan mengapa ini bukan sekadar "membuat menu navigasi"?
2. **Komponen IA**: Sebutkan dan jelaskan secara singkat 4 komponen utama dari Arsitektur Informasi (Sistem Organisasi, Sistem Pelabelan, Sistem Navigasi, dan Sistem Pencarian).
3. **Definisi Mental Model**: Apa yang dimaksud dengan "Mental Model" pengguna? Berikan satu contoh sederhana dari dunia nyata (fisik) dan satu contoh dari antarmuka digital.
4. **Keselarasan Desain**: Mengapa sangat krusial bagi seorang Product Designer untuk menyelaraskan Arsitektur Informasi aplikasi dengan Mental Model penggunanya? Apa risiko utama jika terjadi ketidakselarasan (mismatch)?
5. **Card Sorting**: Jelaskan perbedaan mendasar antara *Open Card Sorting* dan *Closed Card Sorting*. Kapan Anda akan menggunakan masing-masing metode tersebut?

---

## B. Quiz Intermediate (Mekanisme Internal & Troubleshooting)

1. **Pengukuran Efektivitas**: Bagaimana cara objektif untuk mengukur apakah suatu Arsitektur Informasi sudah efektif? Metrik apa saja yang biasanya dianalisis (contoh: *success rate*, *time on task*)?
2. **Tree Testing**: Jelaskan apa itu *Tree Testing*. Bagaimana metode ini berbeda dengan *Card Sorting*, dan di tahap mana dalam proses desain *Tree Testing* paling efektif untuk dilakukan?
3. **Cognitive Overload**: Apa hubungan antara Arsitektur Informasi yang buruk dengan *cognitive overload*? Sebutkan dua teknik IA untuk memitigasi *cognitive overload* pada antarmuka yang sangat kompleks.
4. **Pola Navigasi & Mental Model**: Bagaimana elemen seperti *Breadcrumbs* dan *Mega Menus* bekerja dalam memperkuat atau memandu Mental Model pengguna mengenai hierarki sebuah sistem?
5. **Polyhierarchy**: Dalam merancang taksonomi untuk platform dengan banyak item (seperti e-commerce atau perpustakaan digital), bagaimana Anda menangani item yang secara logis masuk ke dalam beberapa kategori sekaligus (*polyhierarchy*) tanpa membingungkan pengguna?

---

## C. Skenario Kasus Nyata Produksi

### Skenario 1: SaaS B2B "Menu Labyrinth"
Sebuah platform SaaS B2B untuk manajemen HR memiliki lebih dari 100 fitur dan sub-menu yang terus bertambah selama 5 tahun terakhir. Tim Data melaporkan bahwa pengguna baru membutuhkan waktu rata-rata 3 menit hanya untuk mencari menu "Pengaturan Notifikasi", dan tiket *customer support* terkait navigasi sangat tinggi.
**Pertanyaan**: Bagaimana strategi langkah demi langkah Anda untuk merancang ulang (revamp) Information Architecture platform ini tanpa mengasingkan pengguna lama yang sudah terbiasa dengan struktur lama?

### Skenario 2: Merging Mental Models (Super App)
Perusahaan Anda memutuskan untuk menyatukan dua aplikasi menjadi satu "Super App". Aplikasi A adalah aplikasi Edukasi (mental model: belajar linear, silabus berurutan). Aplikasi B adalah Komunitas/Forum (mental model: eksplorasi bebas, diskusi asinkron, trending topic).
**Pertanyaan**: Bagaimana Anda menjembatani kedua mental model yang saling bertolak belakang ini dalam satu Arsitektur Informasi tingkat atas (Top-Level Navigation)? Apa trade-off dari solusi Anda?

### Skenario 3: Perbedaan Generasi (Demographic Mismatch)
Saat melakukan riset pengguna untuk portal berita nasional, Anda menemukan pola unik: Generasi Z mengkategorikan berita berdasarkan "Trending", "Viral", dan "Format (Video/Shorts/Teks)". Sementara itu, Generasi X dan Boomers sangat bergantung pada kategori tradisional (Politik, Ekonomi, Olahraga).
**Pertanyaan**: Sebagai Lead Product Designer, bagaimana Anda merancang sistem navigasi dan pencarian untuk mengakomodasi kedua kelompok demografi ini tanpa membuat antarmuka utama terlihat berantakan?

---

## D. Chapter Challenge

**Tantangan: Merancang IA Aplikasi "Keuangan Pintar"**

**Konteks**: Anda merancang aplikasi "Manajemen Keuangan Pribadi & Investasi" untuk target pengguna milenial yang secara finansial masih awam (pemula).

**Tugas Anda**:
1. Buat visualisasi struktur navigasi dan taksonomi (minimal 3 level kedalaman) menggunakan ASCII Tree (teks).
2. Tuliskan asumsi Mental Model pengguna yang mendasari struktur yang Anda buat.
3. Sebutkan satu atau dua titik di mana pengguna mungkin bingung (potensi *friction*), dan jelaskan *trade-off* mengapa Anda tetap memilih desain struktur tersebut.

*(Catatan: Tidak ada satu jawaban benar, solusi Anda akan dievaluasi berdasarkan logika, empati terhadap mental model pemula, dan struktur taksonominya.)*

---

## E. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Beda antara Information Architecture dan UI Design.
- [ ] Pentingnya Mental Model dalam menentukan ekspektasi pengguna.
- [ ] Empat sistem utama IA (Organisasi, Labeling, Navigasi, Pencarian).
- [ ] Konsep hierarki, sekuensial, dan struktur matriks dalam IA.

### Saya harus bisa melakukan:
- [ ] Merancang dan menjalankan sesi *Card Sorting* (Open/Closed).
- [ ] Membaca dan menganalisis hasil *Tree Testing*.
- [ ] Menerjemahkan kebutuhan bisnis dan mental model pengguna ke dalam Sitemap yang koheren.
- [ ] Mengevaluasi dan melakukan *troubleshooting* pada sistem navigasi yang memiliki *bounce rate* tinggi atau *findability* rendah.
