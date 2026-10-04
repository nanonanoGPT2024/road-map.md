# Bab 04: Evaluasi & Uji Kompetensi WAF, Managed Rules, & Custom Rulesets

---

### 1. Basic Questions (Pilihan Ganda & Analisis Pendek)

#### Soal 1
Manakah urutan fase eksekusi (*phases execution pipeline*) yang benar dalam Cloudflare Ruleset Engine?
A. `http_ratelimit` -> `http_request_firewall_custom` -> `http_request_firewall_managed`  
B. `http_request_firewall_custom` -> `http_ratelimit` -> `http_request_firewall_managed`  
C. `http_request_firewall_managed` -> `http_request_firewall_custom` -> `http_ratelimit`  
D. `http_ratelimit` -> `http_request_firewall_managed` -> `http_request_firewall_custom`  

#### Soal 2
Pada OWASP Core Ruleset (CRS), apa yang membedakan pendekatan *Anomaly Scoring* dibandingkan dengan pendekatan *Traditional Direct Blocking*?
A. Request langsung di-drop seketika saat ada satu pola regex rule yang cocok.  
B. Setiap rule yang cocok menambahkan skor numerik; request baru diambil tindakan jika total skor akumulasi melampaui batas (*threshold*).  
C. Anomaly Scoring hanya mengevaluasi header HTTP, tidak memeriksa isi payload body request.  
D. Traditional Direct Blocking memerlukan Cloudflare Workers, sedangkan Anomaly Scoring tidak.  

#### Soal 3
Fungsi transformatif manakah yang harus digunakan dalam Cloudflare Custom Expression Language untuk mencegah teknik bypass penyerang yang memanfaatkan manipulasi huruf kapital dan karakter hex encoded?
A. `concat()` dan `matches()`  
B. `url_decode()` dan `lower()`  
C. `lookup_json_string()` dan `encode()`  
D. `to_string()` dan `upper()`  

#### Soal 4
Berapa skor bawaan Cloudflare Bot Management (`cf.bot_management.score`) yang mengindikasikan bahwa request hampir pasti berasal dari entitas otomatis berbahaya / *malicious automated bot*?
A. Antara 80 hingga 99  
B. Tepat 50  
C. Antara 1 hingga 29  
D. Nilai negatif  

#### Soal 5
Apa dampak teknis menaikkan OWASP Paranoia Level langsung dari PL1 ke PL4 pada aplikasi web production yang kompleks?
A. Request latency Cloudflare meningkat lebih dari 5 detik per request.  
B. Tingkat *false positive* melonjak tajam karena karakter khusus legal pada URL/Body akan ditandai sebagai anomali.  
C. Cloudflare akan otomatis mengalihkan seluruh traffic ke status Under Attack Mode.  
D. Sertifikat SSL origin server menjadi tidak valid secara otomatis.  

---

### 2. Intermediate Questions

#### Soal 1: Payload Chunking Limit Evasion
Jelaskan batasan inspeksi ukuran body payload default pada Cloudflare WAF. Jika penyerang menyuntikkan payload SQL injection atau Web Shell di akhir payload POST berukuran 2 MB pada domain dengan konfigurasi standard inspection buffer (128 KB), bagaimana perilaku Cloudflare WAF, dan mitigasi Custom Rule apa yang wajib dipasang oleh SRE di edge?

#### Soal 2: False Positive Handling vs Security Degradation
Sebuah endpoint REST API `/api/v1/reports/export` menerima parameter filter JSON yang mengandung karakter SQL kompleks (misalnya klausa filter analitik). Hal ini memicu rule OWASP CRS SQLi Anomaly Detection secara berulang. Jelaskan langkah arsitektural yang benar untuk menyelesaikan false positive ini tanpa menonaktifkan OWASP CRS secara global atau menurunkan Paranoia Level di seluruh domain!

#### Soal 3: Stateless vs Stateful Rate Limiting Evasion
Mengapa rate limiting berbasis `ip.src` sering kali tidak berdaya menangkal serangan Credential Stuffing modern yang terdistribusi? Sebutkan minimal 2 karakteristik alternatif yang dapat dikonfigurasi pada Ruleset Engine Rate Limiting v2 Cloudflare untuk mitigasi yang lebih akurat!

#### Soal 4: Log4j CVE Mitigasi & Virtual Patching
Analisis ekspresi Cloudflare WAF berikut:
```text
http.request.uri.path contains "login" and http.request.body.raw contains "${jndi:"
```
Identifikasi 2 kelemahan dari rule di atas dalam mendeteksi serangan Log4Shell (CVE-2021-44228) dan tuliskan perbaikannya agar tahan terhadap teknik *evasion obfuscation* (seperti nested syntax `${lower:j}ndi` atau URL encoding).

#### Soal 5: Action Comparison: Block vs Managed Challenge
Dalam arsitektur proteksi scraping e-commerce, bandingkan implikasi teknis dan *user experience* antara aksi `Block` dan `Managed Challenge` ketika diterapkan pada request dengan skor bot mencurigakan (`cf.bot_management.score < 30`). Kapan SRE harus memilih `Managed Challenge` daripada `Block`?

---

### 3. Scenario-Based Questions (Studi Kasus Industri Nyata)

#### Skenario 1: Mitigasi Serangan Zero-Day & Critical False Positive di Financial Core
Anda adalah Principal SRE pada bank digital terkemuka. Pada hari Jumat pukul 21:00, tim Threat Intelligence mendeteksi eksploitasi zero-day baru pada framework Java Spring yang digunakan oleh core-banking API (`/api/v2/transfers/process`). 
- Cloudflare Managed Ruleset belum merilis CVE signature resmi.
- Vektor serangan mengeksploitasi serialization bug melalui header `X-Consumer-Meta` yang membawa string diawali `base64;`.
- Namun demikian, ada sekitar 3% klien mobile lama yang secara legal mengirim string metadata berawalan `base64;` tetapi payload mereka selalu berakhiran format valid hash UUID: `|uuid:[a-f0-9-]{36}$`.

**Tugas Anda:**
Tuliskan satu Custom Rule Cloudflare WAF expression yang lengkap dan aman untuk:
1. Memblokir seluruh request eksploitasi ke path transfer tersebut.
2. Mengecualikan (bypass) 3% klien legal tersebut berdasarkan validasi ekspresi regex.
3. Tetap memvalidasi bahwa IP pemanggil bukan IP berbahaya (`cf.threat_score < 40`).

#### Skenario 2: Serangan Bot Terdistribusi pada Flash-Sale Ticket
Sebuah perusahaan ticketing menggelar konser internasional. Dalam 10 detik pertama pembukaan tiket di path `/checkout/reserve`, backend origin langsung lumpuh akibat 150.000 request/detik.
Dari analisis log Cloudflare didapatkan indikasi:
- Penyerang menyewa botnet residential IP (skor IP reputasi terlihat bersih / Threat Score = 0).
- Penyerang merotasi IP setiap kali melakukan hit HTTP POST.
- Request tidak membawa cookie sesi browser valid (`PHPSESSID` atau `__Secure-Session`).
- Nilai `cf.bot_management.score` berkisar di angka 1 hingga 15.

**Tugas Anda:**
Rancang strategi perimeter terpadu menggunakan kombinasi Ruleset Engine (Custom Rules, Bot Management, dan Rate Limiting). Definisikan logika ekspresi dan urutan evaluasi rule-nya!

#### Skenario 3: Penyelamatan Integrasi Webhook Enterprise yang Tercegat CRS
Aplikasi SaaS B2B Anda menerima webhook data sinkronisasi dari sistem klien enterprise (seperti Salesforce dan ServiceNow) ke rute `/webhooks/incoming`.
Setelah Anda menaikkan OWASP Paranoia Level ke PL2 dengan Anomaly Threshold Medium (Skor 40), integrasi webhook klien Enterprise tersebut mengalami kegagalan 100% dengan status HTTP 403. Log menunjukkan webhook mengirim data XML mentah dengan tag yang dianggap oleh OWASP CRS sebagai ancaman *XSS Injection* dan *Remote File Inclusion* (RFI), mendongkrak skor anomali hingga 75.

**Tugas Anda:**
Rancang struktur WAF Exception Terraform (`cloudflare_ruleset`) yang:
1. Menghilangkan inspeksi Rule OWASP spesifik penyebab trigger false positive HANYA untuk path `/webhooks/incoming`.
2. Memverifikasi bahwa request tersebut benar-benar otentik dari Salesforce/ServiceNow (menggunakan validasi kombinasi shared secret token pada custom header `X-Webhook-Secret` dan ASN klien).
3. Memastikan payload webhook yang melewati jalur bypass ini tetap aman dari SQL Injection.

---

### 4. Practical Chapter Challenge: Arsitektur Keamanan Edge Zero-Trust WAF

#### Deskripsi Tantangan:
Anda diminta membangun arsitektur keamanan edge Cloudflare komprehensif untuk startup Unicorn e-Commerce via kode Terraform yang modular dan runnable.

#### Kriteria Arsitektur & Spesifikasi Wajib:
1. **Perimeter Custom WAF:**
   - Blokir akses publik ke seluruh path berawalan `/ops/` dan `/internal/` kecuali datang dari Corporate Gateway CIDR (`198.51.100.0/24`).
   - Berikan HTTP 400 Bad Request / Block pada setiap request `POST` atau `PUT` yang tidak menyertakan header `Content-Type` atau jika `Content-Length` melebihi 256 KB pada path autentikasi `/auth/*`.
2. **Managed Rulesets & Anomaly Tuning:**
   - Terapkan Cloudflare Managed Ruleset (Default Action).
   - Terapkan OWASP Core Ruleset dengan ketentuan:
     - Global baseline: Paranoia Level 1.
     - Ambang batas anomali (Threshold): Score >= 40 (Block).
     - Override khusus: Nonaktifkan Rule ID `942100` (SQLi generic) dan `941100` (XSS generic) HANYA untuk path `/api/v1/content/articles` yang diakses oleh editor terautentikasi (memiliki header `Authorization: Bearer editor-*`).
3. **Multi-Variate Rate Limiting:**
   - Lindungi rute `/api/v1/auth/login`: Batasi 5 request per 60 detik berbasiskan kombinasi `ip.src` dan value header `User-Agent`. Jika terlampaui, mitigasi dengan `managed_challenge` selama 5 menit.
   - Lindungi rute pengiriman voucher `/api/v1/discounts/claim`: Batasi 2 request per 10 detik per `http.request.headers["x-user-id"]`. Jika terlampaui, kirim response JSON 429 kustom.

Kirimkan deliverable berupa dokumen implementasi Terraform (`.tf`), rationale desain keamanan, dan SOP tanggap darurat jika tim development mendeteksi false positive kritis saat rilis fitur baru.

---