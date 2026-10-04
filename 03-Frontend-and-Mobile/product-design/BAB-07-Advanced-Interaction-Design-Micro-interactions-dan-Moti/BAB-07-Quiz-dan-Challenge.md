# BAB 07 — Quiz, Challenge, dan Knowledge Check

## Quiz

### Basic Level (Konsep Inti)
1. Apa definisi dari *micro-interaction* dalam konteks desain produk digital, dan bagaimana perbedaannya dengan *macro-interaction*?
2. Sebutkan dan jelaskan empat komponen utama dari *micro-interaction* (Trigger, Rules, Feedback, Loops & Modes).
3. Mengapa *feedback* visual (seperti perubahan warna tombol saat ditekan) sangat penting bagi pengalaman pengguna?
4. Apa yang dimaksud dengan prinsip *easing* (percepatan/perlambatan) dalam animasi, dan mengapa animasi linear sering kali terlihat kurang natural?
5. Sebutkan tiga manfaat utama dari penggunaan animasi transisi antar halaman (page transitions) pada aplikasi mobile.

### Intermediate Level (Mekanisme Internal & Troubleshooting)
1. Anda merancang animasi *loading spinner* menggunakan CSS/SVG, namun pengguna mengeluh baterai mereka cepat habis. Apa yang mungkin menyebabkan *performance bottleneck* pada animasi tersebut dan bagaimana memperbaikinya?
2. Dalam mendesain *motion*, bagaimana Anda menangani pengguna yang memiliki sensitivitas terhadap gerakan (vestibular disorders) atau memiliki preferensi *Reduced Motion* di sistem operasi mereka?
3. Saat menerapkan animasi transisi *shared element* di frontend (seperti hero image di daftar produk membesar ke halaman detail), apa saja tantangan teknis yang biasa terjadi terkait manipulasi DOM dan *repaint*?
4. Bagaimana cara mengukur keberhasilan (ROI) dari sebuah *micro-interaction* baru (misalnya efek konfeti saat *checkout*) melalui pendekatan analitik produk?
5. Anda mendapati bahwa animasi Lottie yang Anda gunakan di aplikasi *mobile* menyebabkan FPS drop hingga 30fps pada perangkat *low-end*. Langkah-langkah optimasi apa saja yang dapat dilakukan pada aset Lottie tersebut?

### Skenario Kasus Nyata Produksi
1. **Skenario 1: Checkout Experience**
   Aplikasi *e-commerce* klien Anda mengalami tingkat *drop-off* tinggi saat pengguna menekan tombol "Bayar". Sistem membutuhkan waktu 2-3 detik untuk merespons dari *payment gateway*. Rancanglah skema *micro-interaction* dan status state yang dapat mengurangi rasa cemas pengguna dan mencegah mereka menekan tombol "Bayar" dua kali.
2. **Skenario 2: Pull-to-Refresh Inovatif**
   Anda diminta untuk mengganti ikon *spinner default* pada fitur *pull-to-refresh* dengan animasi maskot perusahaan. Jelaskan bagaimana Anda memetakan gerakan jari (scroll offset) dengan *timeline* animasi maskot tersebut agar terasa responsif secara sentuhan (*touch-driven animation*).
3. **Skenario 3: Error Recovery State**
   Ketika koneksi internet pengguna terputus saat mengisi *form* multi-langkah yang panjang, sistem harus memberitahu pengguna tanpa menghilangkan data yang sudah diisi. Rancang urutan *feedback* visual dan interaksi yang tidak *blocking* namun memastikan pengguna menyadari status sistem, serta memberikan cara yang *seamless* untuk mencoba lagi.

---

## Chapter Challenge

**Mendesain Sistem Feedback Multi-State untuk Aksi Destruktif**

**Problem Statement:**
Aplikasi manajemen data Anda memiliki aksi "Delete Project". Karena ini adalah aksi destruktif yang tidak bisa di-undo (irreversible), Anda tidak ingin menggunakan sekadar *confirm dialog default* dari browser yang membosankan.

**Requirements:**
1. Pengguna harus menyadari secara visual bahwa aksi ini berbahaya (sebelum diklik).
2. Mekanisme penghapusan harus mencegah "klik tidak sengaja" (accidental clicks).
3. Harus ada *micro-interaction* yang jelas selama proses penghapusan (loading state).
4. Harus ada konfirmasi akhir (*success state*) dengan transisi elemen keluar layar secara natural.
5. Jika gagal (misalnya karena masalah *server*), *micro-interaction* harus memberikan *error feedback* tanpa harus me-refresh halaman.

**Expected Result:**
Buat *wireflow* interaksi (atau deskripsi langkah per langkah) untuk seluruh state "Delete Project" ini. Identifikasi komponen *Trigger*, *Rules*, *Feedback*, dan *Loops/Modes*. Jelaskan juga parameter *easing* atau durasi yang direkomendasikan untuk animasi *success* dan *error* (misalnya: *shake error*).

---

## Knowledge Check

### Saya harus memahami
- Perbedaan antara animasi dekoratif dan animasi fungsional.
- Anatomi dari *micro-interaction* (Trigger, Rules, Feedback, Loops/Modes).
- Konsep dasar *easing* (Ease-in, Ease-out, Ease-in-out, Spring) dan bagaimana meniru hukum fisika dunia nyata.
- Aksesibilitas dalam animasi (opsi *prefers-reduced-motion*).

### Saya tidak perlu menghafal
- Semua rumus matematis kurva bezier untuk animasi, cukup memahami kapan menggunakan jenis kurva yang mana.
- Spesifikasi teknis setiap *library* animasi di setiap *framework* frontend, cukup pahami konsep dasarnya.

### Saya harus bisa melakukan
- Merancang dan membedah *micro-interaction* berdasarkan anatominya.
- Mengidentifikasi di mana animasi dapat memecahkan masalah UX (misalnya untuk orientasi spasial atau status pemuatan).
- Berkomunikasi secara efektif dengan *developer frontend* menggunakan terminologi *motion* yang tepat (durasi, kurva *easing*, properti yang dianimasikan).

### Checklist
- [ ] Memahami konsep *micro-interaction* dan komponennya.
- [ ] Memahami prinsip dasar *motion design* dalam UI.
- [ ] Bisa merancang *state* dan *feedback* yang komunikatif.
- [ ] Memahami aspek aksesibilitas dan performa dalam *motion design*.
- [ ] Bisa menerapkan *micro-interaction* dalam *real-world case* (contoh: *loading state*, *success state*).
