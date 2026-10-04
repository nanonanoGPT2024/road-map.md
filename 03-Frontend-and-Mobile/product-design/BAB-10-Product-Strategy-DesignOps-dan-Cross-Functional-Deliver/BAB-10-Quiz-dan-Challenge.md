# BAB 10 — Quiz dan Challenge (Product Strategy, DesignOps & Cross-Functional Delivery)

## A. Quiz

### 1. Basic (Konsep Inti)
1. Apa definisi utama dari DesignOps dalam konteks pengembangan produk skala besar?
2. Bagaimana peran Product Strategy dalam menentukan prioritas fitur yang akan didesain dan di-develop?
3. Sebutkan tiga komponen utama dalam sebuah Design System yang efektif.
4. Apa perbedaan mendasar antara *agile design* dan pendekatan *waterfall* tradisional dalam cross-functional delivery?
5. Mengapa kolaborasi awal antara desainer, engineer, dan product manager (PM) (sering disebut konsep *the three amigos*) sangat penting?

### 2. Intermediate (Mekanisme Internal & Troubleshooting)
1. Jika tingkat adopsi Design System di kalangan engineer rendah, langkah strategis apa yang harus dilakukan oleh tim DesignOps?
2. Bagaimana cara mengukur ROI (Return of Investment) dari implementasi DesignOps di sebuah perusahaan?
3. Dalam proses handoff desain ke engineer, sering terjadi miskomunikasi terkait *state* (misal: hover, active, error). Bagaimana DesignOps dapat memitigasi masalah ini?
4. Jelaskan bagaimana mekanisme versioning (misal menggunakan Semantic Versioning) dapat diterapkan pada aset desain (seperti library Figma).
5. Ketika Product Strategy berubah di tengah sprint, bagaimana tim lintas fungsi (cross-functional) harus beradaptasi agar tidak terjadi bottleneck di sisi desain?

### 3. Skenario Kasus Nyata Produksi
1. **Skenario Scaling**: Perusahaan Anda baru saja mengakuisisi startup lain. Anda ditugaskan untuk menggabungkan dua Design System yang berbeda secara visual dan teknis tanpa mengganggu delivery fitur yang sedang berjalan. Bagaimana strategi eksekusi Anda?
2. **Skenario Handoff Bottleneck**: Lead Engineer melaporkan bahwa desain yang diserahkan sering kali tidak feasible untuk diimplementasikan dalam waktu 2 minggu sprint, menyebabkan banyak penundaan. Sebagai DesignOps Manager, audit proses apa yang akan Anda lakukan?
3. **Skenario Alignment**: Product Manager menginginkan peluncuran fitur baru secepatnya untuk mengejar momentum pasar, sementara tim Desain bersikeras untuk melakukan user research komprehensif terlebih dahulu. Bagaimana Anda memfasilitasi kompromi cross-functional ini?

---

## B. Chapter Challenge

### Kasus: "The Silo Breaker"
**Konteks**: Anda adalah Head of DesignOps di sebuah perusahaan e-commerce (SaaS) dengan 50+ desainer dan 200+ engineer. Saat ini, setiap squad (tim kecil) bekerja dalam silo. Mereka membuat komponen UI sendiri-sendiri, menyebabkan inkonsistensi desain dan duplikasi kode yang parah.

**Tugas Anda**:
Rancang sebuah proposal strategi *Cross-Functional Delivery* dan *DesignOps* selama 90 hari pertama yang mencakup:
1. **Audit & Discovery**: Bagaimana Anda mengidentifikasi skala masalah inkonsistensi.
2. **Governance Model**: Siapa yang berhak menyumbangkan komponen ke Design System pusat (Centralized, Federated, atau Cyclical).
3. **Workflow Otomatisasi**: Rancang pipeline otomatisasi dari Figma ke Code (misal menggunakan Design Tokens).
4. **Metrics**: Tentukan 3 Key Performance Indicators (KPI) untuk mengukur keberhasilan inisiatif Anda.

*(Jangan mencari solusi instan, buatlah dokumen terstruktur untuk dipresentasikan ke C-Level)*

---

## C. Knowledge Check

### Saya Harus Memahami:
- [ ] Peran strategis DesignOps dalam efisiensi operasional tim desain.
- [ ] Pentingnya penyelarasan (alignment) antara Product Strategy dengan eksekusi desain.
- [ ] Metodologi handoff desain yang meminimalisir gesekan (friction) antara desainer dan engineer.
- [ ] Metrik-metrik yang relevan untuk mengukur kesuksesan operasional desain.

### Saya Tidak Perlu Menghafal:
- [ ] Detail implementasi setiap plugin Figma untuk DesignOps (namun perlu tahu fungsinya).
- [ ] Rumus kompleks ROI (cukup pahami konsep cost saving vs time saving).

### Saya Harus Bisa Melakukan:
- [ ] Membangun workflow komunikasi lintas divisi (Desain, Tech, Product).
- [ ] Mendiagnosa penyebab lambatnya proses delivery desain.
- [ ] Menginisiasi sistem dokumentasi komponen yang dapat dipahami engineer.

---

## D. Checklist Pemahaman
- [ ] Memahami konsep DesignOps.
- [ ] Memahami cara kerja Design System Governance.
- [ ] Bisa membuat contoh workflow handoff sederhana.
- [ ] Bisa melakukan praktik penyusunan metrik efisiensi desain.
- [ ] Bisa melakukan troubleshooting masalah komunikasi cross-functional.
- [ ] Memahami trade-off antara kecepatan delivery dan kualitas desain.
- [ ] Bisa menerapkan dalam real-world case (misal menyatukan proses desain di 2 squad berbeda).
