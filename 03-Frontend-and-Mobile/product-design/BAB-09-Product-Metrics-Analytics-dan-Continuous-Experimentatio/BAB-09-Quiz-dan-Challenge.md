# BAB 09 — Quiz, Challenge, & Knowledge Check: Product Metrics, Analytics, dan Continuous Experimentation

## A. Quiz

*(Instruksi: Jawablah pertanyaan berikut tanpa melihat materi sebelumnya. Jika ada keraguan, catat dan tinjau kembali module terkait.)*

### Basic (Pemahaman Konsep Inti)
1. Apa perbedaan utama antara Vanity Metrics dan Actionable Metrics? Berikan masing-masing satu contoh!
2. Mengapa framework AARRR (Pirate Metrics) penting dalam product design dan analytics?
3. Apa yang dimaksud dengan North Star Metric dan mengapa sebuah produk idealnya hanya memiliki satu atau dua North Star Metric?
4. Dalam konteks A/B Testing, apa yang dimaksud dengan Control Group dan Variant Group?
5. Jelaskan secara singkat apa itu Retention Rate dan mengapa metrik ini sering dianggap lebih penting daripada Acquisition (pendaftaran pengguna baru)!

### Intermediate (Mekanisme & Troubleshooting)
1. Anda menjalankan A/B testing selama 2 hari dan melihat Variant B memberikan peningkatan conversion rate sebesar 50%. Apakah Anda langsung menghentikan eksperimen dan meluncurkan Variant B? Mengapa? (Petunjuk: Pikirkan tentang *Statistical Significance* dan *Sample Size*).
2. Anda menyadari bahwa DAU (Daily Active Users) aplikasi naik secara signifikan, tetapi Revenue (Pendapatan) tetap stagnan. Bagaimana Anda menggunakan Cohort Analysis untuk menginvestigasi fenomena ini?
3. Saat melakukan tracking event, apa perbedaan pendekatan antara *Client-side tracking* dan *Server-side tracking*? Kapan Anda harus menggunakan masing-masing?
4. Sebuah event 'Checkout Button Clicked' tercatat 10,000 kali di analytics, tetapi data di database backend hanya menunjukkan 8,500 transaksi sukses. Sebutkan minimal 3 kemungkinan penyebab perbedaan ini (data discrepancy)!
5. Bagaimana konsep *Simpson's Paradox* dapat memberikan kesimpulan yang salah dalam analisis data eksperimen, dan bagaimana cara mencegahnya?

### Skenario Kasus Nyata Produksi
1. **Skenario E-Commerce Drop-off:**
   Tim data melaporkan bahwa terjadi drop-off sebesar 60% pada halaman "Payment Selection" di aplikasi e-commerce Anda. Sebagai Product Designer, langkah-langkah analitis apa yang akan Anda lakukan untuk menemukan akar masalah sebelum mulai mendesain ulang halaman tersebut?
   
2. **Skenario Feature Rollout:**
   Anda baru saja merilis fitur "Dark Mode". Beberapa hari kemudian, metrik *session duration* turun. Apakah ini hal yang buruk? Bagaimana Anda memvalidasi apakah penurunan *session duration* ini mengindikasikan masalah usability atau justru fitur tersebut membuat user menemukan informasi lebih cepat?

3. **Skenario Cannibalization dalam Eksperimen:**
   Eksperimen fitur "One-Click Checkout" meningkatkan rasio konversi pada halaman produk, tetapi secara mengejutkan *Average Order Value* (AOV) atau nilai rata-rata keranjang menurun tajam. Metrik sekunder mana yang Anda lupa pantau, dan bagaimana Anda memutuskan apakah fitur ini sukses atau gagal?

---

## B. Chapter Challenge

### Tantangan: Merancang Experimentation Plan (A/B Test)

**Konteks:**
Anda adalah Product Designer untuk aplikasi layanan pesan antar makanan (Food Delivery). Saat ini, pengguna seringkali "nyasar" di daftar restoran dan memakan waktu rata-rata 4 menit sebelum memutuskan untuk memesan, atau malah keluar dari aplikasi tanpa memesan (*bounce*). Anda memiliki hipotesis bahwa menampilkan "Top 3 Rekomendasi Personal" di bagian paling atas halaman beranda (Home) akan mempercepat keputusan dan meningkatkan konversi.

**Tugas Anda:**
Buatlah dokumen *Experimentation Plan* ringkas dengan struktur berikut:
1. **Hypothesis Statement:** (Jika kita [X], maka [Y] akan terjadi, yang dapat diukur dengan [Z]).
2. **Primary Metric (Success Metric):** Metrik utama penentu kesuksesan.
3. **Secondary Metrics:** Metrik pendukung untuk memberikan konteks.
4. **Guardrail / Counter Metrics:** Metrik negatif yang tidak boleh memburuk (misal: memantau agar fitur baru tidak merusak hal lain).
5. **Target Audience & Traffic Split:** Siapa yang akan diikutsertakan dan berapa persentase pembagian traffic?
6. **Minimum Detectable Effect (MDE) & Duration:** Asumsi secara kualitatif berapa lama eksperimen perlu dijalankan.

*(Catatan: Tidak ada jawaban "sempurna". Tantangan ini melatih Anda untuk berpikir sistematis sebelum meminta resource engineering untuk membangun sebuah fitur).*

---

## C. Knowledge Check & Checklist

### Saya harus memahami:
- Perbedaan metrik vanity vs actionable.
- Framework analitik populer (AARRR, HEART).
- Dasar-dasar merumuskan hipotesis yang valid dan dapat diuji.
- Konsep dasar A/B testing, statistical significance, dan sample size.
- Jenis-jenis metrik: Primary, Secondary, dan Guardrail.

### Saya tidak perlu menghafal:
- Rumus matematika statistik mendetail untuk p-value (cukup pahami konsepnya).
- Syntax spesifik dari setiap tools analytics (Google Analytics, Mixpanel, Amplitude), karena UI/UX tools akan terus berubah.

### Saya harus bisa melakukan:
- Menerjemahkan masalah desain/user ke dalam metrik yang terukur.
- Merancang skenario A/B testing sederhana.
- Membaca dan menafsirkan funnel atau cohort analysis untuk menemukan bottleneck dalam user journey.
- Berkolaborasi dengan Data Analyst/Engineer untuk mendefinisikan *event tracking plan*.

### Checklist Penyelesaian Bab:
- [ ] Memahami konsep metrik produk dan framework analytics.
- [ ] Mampu membedakan metrik yang baik dan buruk.
- [ ] Memahami alur Continuous Experimentation (Build-Measure-Learn).
- [ ] Bisa membuat rancangan A/B Test sederhana.
- [ ] Bisa melakukan identifikasi masalah lewat funnel/cohort secara konseptual.
- [ ] Memahami trade-off dari setiap keputusan eksperimen (misal kecepatan inovasi vs resiko error).
- [ ] Menyelesaikan Quiz dan Chapter Challenge.

---
*Lanjutkan ke materi berikutnya atau gunakan command `SOLUTION` jika Anda ingin mendiskusikan jawaban dari Quiz dan Challenge ini.*
