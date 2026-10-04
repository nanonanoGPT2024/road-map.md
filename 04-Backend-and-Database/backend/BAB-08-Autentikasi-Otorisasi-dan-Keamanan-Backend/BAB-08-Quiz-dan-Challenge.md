---
[⬅️ Module 02: OWASP API Security & Rate Limiting](./Module-02-OWASP-API-Security-Top-10-Rate-Limiting-Enkripsi.md) | [📋 Silabus Induk](../README.md) | [BAB 09: Pengujian Backend & CI/CD ➡️](../BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/Module-01-Piramida-Testing-Integration-Testcontainers-Contract.md)
---

# BAB 08: Evaluasi Pemahaman, Quiz, & Tantangan Arsitektur Autentikasi, Otorisasi, & Keamanan Backend

Selamat! Anda telah menyelesaikan **BAB 08: Autentikasi, Otorisasi, & Keamanan Backend (OWASP)**. Lembar evaluasi ini dirancang untuk menguji ketajaman insting keamanan siber (*Defensive Security Mindset*), pemahaman kriptografi, serta penguasaan protokol otorisasi modern Anda.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan perbedaan mendasar antara Autentikasi (AuthN) dan Otorisasi (AuthZ)!** Berikan contoh kode HTTP status code yang tepat untuk merepresentasikan kegagalan masing-masing proses tersebut!
2. **Mengapa menyimpan Access Token JWT di dalam `localStorage` browser sangat tidak disarankan untuk aplikasi enterprise?** Mengapa cookie dengan atribut `HttpOnly; Secure; SameSite=Strict` jauh lebih aman terhadap serangan Cross-Site Scripting (XSS)?
3. **Apa perbedaan antara Role-Based Access Control (RBAC) dan Attribute-Based Access Control (ABAC)?** Berikan skenario di mana RBAC statis gagal memenuhi kebutuhan bisnis yang menuntut evaluasi atribut dinamis!
4. **Mengapa algoritma hashing cepat seperti MD5 dan SHA-256 dilarang keras digunakan untuk menyimpan password pengguna?** Apa keunggulan matematis fungsi memori-berat seperti Argon2id atau bcrypt?
5. **Apa yang dimaksud dengan kerentanan BOLA (Broken Object Level Authorization / IDOR)?** Mengapa BOLA dinobatkan sebagai ancaman nomor 1 dalam OWASP API Security Top 10?

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Kriptografi PKCE (Proof Key for Code Exchange) pada OAuth 2.0:**
   Bagaimana kombinasi `code_verifier` dan `code_challenge` (SHA-256 Base64URL) secara matematis menggagalkan serangan pencurian kode otorisasi oleh aplikasi berbahaya di perangkat mobile?
7. **Timing Attacks pada Verifikasi Tanda Tangan Digital:**
   Mengapa membandingkan dua string signature menggunakan operator perbandingan standar JavaScript (`sig1 === sig2`) membuka celah kerentanan *Side-Channel Timing Attack*? Bagaimana fungsi `crypto.timingSafeEqual()` memitigasi risiko ini?
8. **Anatomi Algoritma Token Bucket Rate Limiting:**
   Jelaskan bagaimana algoritma Token Bucket menghitung isi ulang token secara fraksional tanpa perlu menjalankan proses timer background yang boros CPU! Apa perbedaan perilakunya terhadap lonjakan trafik (*Burst Traffic*) dibanding algoritma Leaky Bucket?
9. **Authenticated Encryption (AES-256-GCM AEAD):**
   Mengapa enkripsi simetris modern wajib menghasilkan **Authentication Tag** (16-byte)? Apa yang terjadi jika peretas memanipulasi 1 bit ciphertext di database saat server mencoba mendekripsi data tersebut?
10. **Bahaya Kerentanan Mass Assignment:**
    Bagaimana pola kode `const user = await User.create(req.body);` dapat dieksploitasi oleh penyerang untuk menaikkan saldo rekening atau mengubah role menjadi administrator? Bagaimana teknik DTO Data Whitelisting mencegahnya?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Kebocoran Data Rekam Medis Pasien Rumah Sakit
Sebuah aplikasi rumah sakit memiliki endpoint untuk mengunduh resume hasil rontgen: `GET /api/v1/radiology/reports/:reportId`.
Seorang pasien bernama Joko login dan mengunduh laporannya dengan ID `REP-1001`. Joko memperhatikan URL tersebut, lalu iseng mengubah nomor menjadi `REP-1002`. Browser Joko seketika menampilkan laporan rekam medis milik pasien lain lengkap dengan nama, NIK, dan diagnosa kanker.
- **Identifikasi Kerentanan:** Kerentanan OWASP apa yang terjadi di sini?
- **Remediasi Kode:** Tuliskan perbaikan kode handler endpoint tersebut (baik di level routing maupun query SQL/ORM) agar Joko hanya diizinkan membaca laporan yang sah miliknya!

### Skenario B: Serangan Brute-Force Login & Distributed Credential Stuffing
Sebuah bank digital mendeteksi serangan botnet yang mencoba mencocokkan jutaan kombinasi email dan password pada endpoint `POST /api/v1/auth/login`. Penyerang menggunakan ribuan alamat IP perumahan yang berbeda (*Residential Proxies*), sehingga Rate Limiter sederhana yang hanya berbasis IP address (`req.ip`) gagal memblokir serangan.
- **Analisis:** Mengapa IP-based rate limiting tidak efektif menghadapi botnet terdistribusi?
- **Rancang Pertahanan Berlapis:** Bagaimana merancang strategi rate limiting komposit (misal: kombinasi IP + Target Email), algoritma CAPTCHA adaptif, deteksi *Account Takeover (ATO)*, dan kebijakan *Account Lockout* sementara?

### Skenario C: Token Revocation Dilemma pada Stateless JWT
Tim keamanan siber perusahaan mendeteksi laptop seorang eksekutif perusahaan hilang dicuri di bandara. Eksekutif tersebut memiliki Access Token JWT yang masih aktif selama 24 jam ke depan.
Karena sistem menggunakan JWT stateless murni tanpa shared session store, admin sistem tidak bisa mematikan sesi token tersebut secara instan dari dashboard.
- **Analisis:** Mengapa arsitektur JWT stateless murni menjadi bumerang dalam skenario darurat ini?
- **Rancang Solusi:** Rancang arsitektur **Token Blacklist / Revocation Store** berbasis Redis dengan TTL otomatis, atau mekanisme *Token Version / Security Stamp* di tabel database pengguna!

---

## 4. Chapter Challenge: Desain Zero-Trust API Security Architecture

### Deskripsi Masalah
Anda adalah Chief Information Security Officer (CISO) untuk platform Open Banking API yang menghubungkan 50 perusahaan Fintech dengan Core Banking perbankan:
1. **Pilar 1 - Identitas & Delegasi:** Terapkan OAuth 2.0 Mutual-TLS (mTLS) atau OAuth 2.0 PKCE dengan JSON Web Key Sets (JWKS) rotasi otomatis.
2. **Pilar 2 - Granular Authorization:** Terapkan ABAC Policy Engine untuk memvalidasi limit transfer nominal harian berdasarkan reputasi IP, waktu transaksi, dan persetujuan user (*Consent Grants*).
3. **Pilar 3 - Kriptografi & Data Privacy:** Seluruh data PII nasabah (NIK, No Rekening, Saldo) wajib dienkripsi di level kolom database (*Field-Level Encryption*) menggunakan AES-256-GCM dengan mekanisme Envelope Encryption AWS KMS / HashiCorp Vault.
4. **Pilar 4 - Rate Limiting & DoS Protection:** Terapkan kuota tiering (Tier Startup: 50 req/menit, Tier Enterprise: 5000 req/menit) dengan algoritma Token Bucket terdistribusi di Redis.

### Format Output
Buat dokumen spesifikasi arsitektur keamanan (*Threat Modeling & Security Blueprint*) yang memuat:
1. Diagram Arsitektur Pertahanan Berlapis (*Defense-in-Depth*).
2. Kebijakan JSON Policy Otorisasi ABAC.
3. Alur Kriptografi Envelope Encryption saat operasi Create dan Read data nasabah.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Perbedaan implementasi dan trade-off antara Stateful Session vs Stateless JWT.
- [ ] Alur kerja OAuth 2.0 Authorization Code Flow with PKCE.
- [ ] 10 kerentanan paling mematikan pada OWASP API Security Top 10 (2023).
- [ ] Mekanisme kerja algoritma Token Bucket Rate Limiting.
- [ ] Mengapa fungsi hash memori-berat (Argon2id/bcrypt) wajib digunakan untuk password.
- [ ] Prinsip Authenticated Encryption (AEAD) pada AES-256-GCM.

### Saya Tidak Perlu Menghafal:
- Rincian matematika polinomial kurva eliptik ECDSA / Galois Field multiplication pada GCM.
- Seluruh ratusan kode heksadesimal RFC standar OAuth 2.0.

### Saya Harus Bisa Melakukan:
- [ ] Menulis middleware verifikasi JWT yang aman dari serangan *timing attack* dan pemalsuan signature.
- [ ] Mengidentifikasi dan memperbaiki celah kerentanan BOLA dan Mass Assignment pada kode backend.
- [ ] Membangun mesin pembatas laju trafik (*Token Bucket Rate Limiter*) yang tangguh menahan burst.
- [ ] Mengenkripsi dan mendekripsi data sensitif PII di database menggunakan AES-256-GCM.

---
[⬅️ Module 02: OWASP API Security & Rate Limiting](./Module-02-OWASP-API-Security-Top-10-Rate-Limiting-Enkripsi.md) | [📋 Silabus Induk](../README.md) | [BAB 09: Pengujian Backend & CI/CD ➡️](../BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/Module-01-Piramida-Testing-Integration-Testcontainers-Contract.md)
---
