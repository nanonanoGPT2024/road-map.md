# BAB 02 — Evaluasi, Quiz, & Chapter Challenge
## Konfigurasi Provider AI & Model Routing

---

## 🎯 Ringkasan Bab

Dalam Bab ini, kita telah membedah bagaimana OpenClaw mengelola kecerdasan komputasi multi-model secara cerdas, andal, dan hemat biaya:
1. **Integrasi Multi-Provider**: Menghubungkan Anthropic Claude, OpenAI, Google Gemini, dan Ollama lokal melalui lapisan *Universal Adapter* yang menormalisasi perbedaan skema request dan tool calling.
2. **Model Routing, Failover, & Optimasi Biaya**: Mengarahkan tugas berdasarkan intent dan privasi, menangani *Rate Limit 429* dengan failover transparan, serta mengunci pengeluaran harian menggunakan *Budget Ceiling Guardrails*.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Perbedaan format API antara OpenAI Chat Completions (`/v1/chat/completions`) dan Anthropic Messages (`/v1/messages`).
- [ ] Mengapa Ollama lokal sangat krusial untuk kedaulatan privasi data dan operasi zero-cost.
- [ ] Bagaimana cara kerja failover otomatis saat provider cloud utama mengalami error HTTP 429 atau 503.
- [ ] Mengapa context compaction penting untuk menjaga ukuran context window agar tidak membengkakkan tagihan API.
- [ ] Bagaimana cara kerja Prompt Caching dalam memangkas biaya input hingga 90% pada prompt sistem berulang.

### Saya Tidak Perlu Menghafal:
- Daftar lengkap seluruh harga per juta token tiap model (karena harga cloud AI berubah secara berkala).
- Struktur biner internal dari quantized GGUF weights pada Ollama.

### Saya Harus Bisa Melakukan:
- [ ] Mengonfigurasi file `config.json` dan `.env` untuk mendaftarkan multi-provider.
- [ ] Menjalankan model lokal dengan Ollama dan menghubungkannya ke gateway OpenClaw.
- [ ] Mendesain rantai failover model dan menyetel batas anggaran harian.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Apa fungsi dari lapisan "Adapter" dalam arsitektur provider OpenClaw?**
2. **Mengapa Google Gemini Flash sering direkomendasikan sebagai model default untuk percakapan santai di OpenClaw?**
3. **Bagaimana cara kerja Ollama dalam menjalankan model AI tanpa memerlukan koneksi internet?**
4. **Apa yang terjadi ketika provider utama mengembalikan status error HTTP `429 Too Many Requests` jika fitur Failover Chain diaktifkan?**
5. **Apa keuntungan dari fitur Prompt Caching pada model seperti Claude 3.5 Sonnet?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Dalam integrasi Tool Calling, mengapa skema parameter fungsi pada Anthropic (`input_schema`) harus dinormalisasi jika agen sewaktu-waktu beralih ke OpenAI (`parameters`)?**
7. **Jika Anda memiliki kuota gratis harian Google Gemini, bagaimana strategi routing terbaik untuk meminimalkan pengeluaran saldo kartu kredit Anda?**
8. **Jelaskan perbedaan antara Privacy Gate Routing dan Intent-Based Routing.**
9. **Mengapa riwayat percakapan yang tidak pernah dirangkum (uncompacted) dapat menyebabkan degradasi performa model seiring berjalannya waktu?**
10. **Bagaimana Budget Ceiling Guardrail mencegah skenario "infinite loop bug" pada background task yang dapat menguras ribuan dolar dalam semalam?**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Asisten Pribadi Pengacara (Kerahasiaan Klien Mutlak)**  
   Firma hukum ingin menggunakan OpenClaw untuk merangkum berkas perkara dan draft gugatan. Regulasi hukum melarang data perkara diunggah ke server pihak ketiga manapun.
   - Provider dan model apa yang wajib Anda gunakan?
   - Spesifikasi hardware server lokal minimal apa yang Anda rekomendasikan untuk menjalankan model open-weight 14B atau 32B secara mulus?

12. **Skenario 2: Penanganan Lonjakan Trafik Black Friday**  
   Agen OpenClaw bertugas merespons pertanyaan pembeli di Telegram toko e-commerce Anda. Saat promo Black Friday, akun OpenAI Anda mendadak terkena Rate Limit 429 karena lonjakan 500 pesan/menit.
   - Tunjukkan bagaimana arsitektur failover OpenClaw mencegah customer support Anda mati total.
   - Urutkan rantai provider cadangan yang paling masuk akal dari segi kapasitas dan kecepatan.

13. **Skenario 3: Cost Engineering untuk Mahasiswa**  
   Seorang mahasiswa ingin asisten OpenClaw-nya selalu aktif 24/7 di server VPS murah seharga \$4/bulan dengan budget token AI maksimal hanya \$2/bulan.
   - Rancang strategi alokasi model: kapan menggunakan Ollama, kapan menggunakan Gemini Flash, dan kapan mengizinkan Claude Sonnet.

---

## 🏆 Chapter Challenge: Dynamic Cost & Latency Balancer

### Problem Statement
Rancang modul router cerdas (*Adaptive Provider Balancer*) yang memperhitungkan 3 variabel dinamis sebelum memilih model:
1. **Kompleksitas Prompt**: Jumlah kata dan ada/tidaknya blok kode.
2. **Saldo Anggaran Harian**: Berapa dolar yang tersisa hari ini.
3. **Latensi Riil Terakhir (P95)**: Jika latensi provider cloud A sedang melonjak > 3 detik, otomatis alihkan sementara ke provider B selama 15 menit.

### Deliverables:
- Logika pemilihan model dengan bobot skor (*Weighted Decision Matrix*).
- Mekanisme cooldown otomatis saat provider cadangan dipicu.
- Laporan metrik penghematan biaya dan latensi rata-rata.
