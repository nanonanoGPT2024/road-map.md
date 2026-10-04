# BAB 08 — Evaluasi, Quiz, & Chapter Challenge
## Resiliensi Sistem, Keamanan, & Rate Limiting

---

## 🎯 Ringkasan Bab

Dalam Bab ini, kita telah mengeksplorasi strategi pertahanan dan ketahanan sistem terdistribusi dari level jaringan hingga arsitektur aplikasi:
1. **Rate Limiting & Traffic Shaping**: Token Bucket vs Leaky Bucket vs Sliding Window Counter, penanganan burst, serta distributed atomic rate limiting dengan Redis.
2. **Fault Tolerance & Resiliensi**: Memutus mata rantai *cascading failure* dengan *Circuit Breaker FSM* (Closed, Open, Half-Open), mitigasi *retry storms* dengan *Exponential Backoff & Full Jitter*, serta isolasi resource dengan *Bulkhead Pattern*.
3. **Defensive Security & Zero Trust**: Menggantikan model *Castle-and-Moat* lama dengan *Zero Trust* ("Never Trust, Always Verify"), validasi tanda tangan stateless JWT, mitigasi pencurian token dengan strategi short-lived tokens, dan perlindungan multi-layer terhadap serangan DDoS L3/L4/L7.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Mengapa algoritma Token Bucket lebih disukai untuk API publik dibandingkan Fixed Window (tidak rentan terhadap lonjakan ganda di batas jendela / *boundary burst*).
- [ ] Tiga fase Finite State Machine pada Circuit Breaker: kapan sirkuit *trip* ke OPEN, apa keuntungan *fail-fast*, dan bagaimana uji coba probe pada HALF-OPEN.
- [ ] Mengapa Exponential Backoff tanpa Jitter masih dapat menyebabkan kelumpuhan server (*thundering herd / retry spikes*).
- [ ] Mengapa JWT tidak boleh digunakan untuk menyimpan informasi rahasia (karena payload hanya di-encode Base64, bukan dienkripsi).
- [ ] Perbedaan esensial antara otentikasi standar (Server membuktikan identitas) dan Mutual TLS / mTLS (Klien dan Server saling memverifikasi sertifikat).

### Saya Tidak Perlu Menghafal:
- Rumus matematika eksak turunan integral kurva Poisson untuk traffic shaping.
- Spesifikasi ASN.1 DER encoding struktur sertifikat X.509.

### Saya Harus Bisa Melakukan:
- [ ] Menentukan algoritma rate limiting yang tepat sesuai toleransi burst dan kebutuhan downstream.
- [ ] Mengimplementasikan circuit breaker wrapper di sekitar remote client calls dengan fallback yang aman.
- [ ] Merancang arsitektur rotasi token JWT (Access Token + Refresh Token) dengan skema pencabutan sesi (*revocation*).

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Apa perbedaan mendasar antara perilaku Token Bucket dan Leaky Bucket ketika menerima lonjakan traffic sesaat (*traffic burst*)?**
2. **Mengapa server mengembalikan kode status HTTP `429 Too Many Requests` beserta header `Retry-After` alih-alih sekadar memutus koneksi TCP?**
3. **Pada Circuit Breaker, apa yang terjadi ketika sistem berada dalam state `OPEN` dan sebuah request masuk dari client?**
4. **Apa fungsi dari penambahan 'Jitter' (keacakan) pada algoritma Exponential Backoff?**
5. **Mengapa payload pada JSON Web Token (JWT) dapat dibaca oleh siapa saja yang memiliki token tersebut meskipun token tersebut sah?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Dalam sistem dengan 10 instance API Gateway di balik Load Balancer, mengapa rate limiting lokal di memori masing-masing instance gateway menghasilkan batas kuota yang tidak akurat (*quota leakage*)?**
7. **Bagaimana Bulkhead Pattern melindungi layanan kritis (seperti Pembayaran) agar tidak kehabisan connection pool saat layanan rekomendasi produk sedang mengalami degradasi parah?**
8. **Mengapa menggunakan symmetric key (HS256) pada JWT memiliki risiko keamanan lebih tinggi dalam arsitektur multi-service dibandingkan asymmetric key (RS256)?**
9. **Jelaskan bagaimana serangan Slowloris (L7 DoS) melumpuhkan web server tradisional berbasis thread (seperti Apache HTTPD) tanpa membutuhkan bandwidth besar.**
10. **Jika sebuah token JWT dicuri oleh penyerang, apa saja opsi mitigasi yang dapat dilakukan arsitek sistem mengingat JWT bersifat stateless?**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Payment Gateway Webhook Under Massive Retry Storm**  
   Mitra bank Anda mengalami gangguan selama 30 menit. Setelah sistem bank pulih, server bank secara serempak mengirimkan 2.000.000 webhook notifikasi pembayaran yang tertunda ke endpoint webhook Anda dalam rentang 10 detik.
   - Algoritma traffic shaping apa yang harus Anda pasang di layer terdepan?
   - Bagaimana kombinasi API Gateway + Message Queue menahan lonjakan ini agar database billing Anda tidak kolaps?

12. **Skenario 2: Migrasi Sistem Monolith Lama ke Arsitektur Zero Trust & Service Mesh**  
   Sebuah institusi perbankan memiliki 80 microservices yang sebelumnya berkomunikasi via plain HTTP di jaringan lokal AWS VPC tanpa enkripsi.
   - Jelaskan langkah-langkah transisi menerapkan Mutual TLS (mTLS) tanpa harus mengubah ribuan baris kode aplikasi di masing-masing service.
   - Bagaimana cara mengelola rotasi otomatis sertifikat mTLS setiap 24 jam?

13. **Skenario 3: Multi-Tier Protection pada Tiket Konser Skala Global**  
   Sebuah platform tiket melayani penjualan tiket konser artis dunia: 50.000 tiket habis dalam 2 menit, dengan 5.000.000 pengguna dan ratusan bot scraper menyerbu web secara serempak.
   - Rancang arsitektur keamanan dan traffic filtering berlapis: Edge Anycast/WAF $\rightarrow$ Bot Detection/Captcha $\rightarrow$ Virtual Waiting Room / Queue-it $\rightarrow$ Token Bucket Limiter $\rightarrow$ Core Booking Engine.

---

## 🏆 Chapter Challenge: Resilient Multi-Tenant API Gateway Engine

### Problem Statement
Anda ditugaskan mendesain subsistem keamanan dan resiliensi untuk API Gateway multi-tenant B2B (mirip Kong / AWS API Gateway) yang melayani ribuan perusahaan klien:
- Tier Free: 100 req/menit
- Tier Pro: 5.000 req/menit (Boleh burst hingga 200 req/detik)
- Tier Enterprise: 50.000 req/menit

### Requirements:
1. **Distributed Rate Limiting**: Memanfaatkan Redis cluster dengan atomic sliding window counter atau Lua script untuk menjamin akurasi kuota lintas 20 server gateway.
2. **Circuit Breaker Per Route**: Jika downstream service salah satu tenant mati, gateway harus membuka sirkuit untuk rute tenant tersebut tanpa mempengaruhi rute tenant lainnya.
3. **Zero Trust JWT Validation**: Gateway memvalidasi signature RS256 menggunakan JWKS caching publik, mengekstrak tenant context, dan meneruskan request ke internal pod dengan header terotentikasi via mTLS.
4. **Resilience Test Plan**: Tunjukkan rencana Chaos Engineering (misal simulasi matinya Redis atau matinya auth service) untuk memastikan gateway tetap fail-safe (*graceful degradation*).
