# Module 01: Web Application Firewall (WAF), Managed Rules, & Custom Rulesets

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan mengoptimasi Cloudflare Managed Ruleset serta OWASP ModSecurity Core Ruleset (CRS) menggunakan Ruleset Engine v2.
- Mengimplementasikan sistem skoring anomali (Anomaly Scoring Detection) OWASP CRS dengan tuning *Paranoia Level* dan *Anomaly Threshold* yang presisi untuk meminimalkan *false positive*.
- Mendesain Custom Firewall Rules menggunakan Cloudflare Rules Language (berbasis sintaks Wireshark/PCRE) untuk inspeksi payload HTTP (URI, Headers, Body, Cookies).
- Mengintegrasikan WAF dengan mitigasi Bot Management (Bot Score, Verified Bots, Super Bot Fight Mode) dan Rate Limiting Rules canggih berbasis *sliding-window tracking*.
- Menyusun otomasi Infrastructure as Code (IaC) via Terraform untuk mengelola deployment WAF Ruleset secara deterministik pada level enterprise.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Protokol HTTP/1.1, HTTP/2, dan HTTP/3: Lifecycle request-response, method semantics, header parsing, body encoding (`multipart/form-data`, `application/json`, `application/x-www-form-urlencoded`).
- Fundamental OWASP Top 10 (Injection, Broken Access Control, SSRF, XSS, Deserialization).
- Regular Expression (PCRE standard) untuk string matching dan parsing ekspresi biner/teks.
- Arsitektur Reverse Proxy dan CDN Edge Delivery Network.
- Pengalaman dasar menggunakan Cloudflare Dashboard/API v4 dan HashiCorp Terraform syntax (HCL).

---

### 3. Concept
Cloudflare Web Application Firewall (WAF) adalah sistem inspeksi stateful berbasis *edge computing* yang berada di jalur data (in-line) antara client eksternal dan origin server. Dibangun di atas Ruleset Engine generasi kedua (v2), Cloudflare WAF mengevaluasi setiap paket layer 7 HTTP/HTTPS yang masuk ke jaringan anycast global secara real-time dengan latensi sub-milidetik.

WAF Cloudflare tidak beroperasi secara monolitik, melainkan menerapkan sistem pertahanan berlapis (defense-in-depth) yang menggabungkan:
1. **Cloudflare Managed Ruleset:** Kumpulan aturan berbasis tanda tangan (signature-based) yang diperbarui secara dinamis oleh tim threat intelligence Cloudflare untuk menangkal eksploitasi zero-day (seperti Log4Shell, Spring4Shell, CVE platform populer).
2. **Cloudflare OWASP Core Ruleset:** Implementasi standar OWASP CRS yang menggunakan evaluasi berbasis skor (anomaly scoring engine), bukan sekadar blokir biner langsung (*immediate trigger*).
3. **Custom Expression Ruleset:** Aturan kustom berbasis bahasa filter Wireshark yang memungkinkan rekayasa logika boolean multi-kondisi yang kompleks.
4. **Rate Limiting Engine:** Penghitung kuota request adaptif berbasis atribut spesifik (IP, session cookie, API token, fingerprint) dengan jendela waktu bergerak (*sliding window*).
5. **Bot Management Framework:** Heuristik machine learning yang menghasilkan `cf.bot_management.score` (1-99) untuk membedakan manusia, automated tools legitimate, dan malicious scraper.

---

### 4. Why
Serangan siber Layer 7 modern tidak lagi bergantung pada serangan volumetrik mentah; penyerang memanfaatkan targeted attack, credential stuffing, API abuse, dan exploit zero-day yang lolos dari perimeter jaringan L3/L4 (seperti firewall router standar atau network ACL).

1. **Proteksi Asimetris di Origin:** Membebankan inspeksi regular expression yang berat atau parsing payload JSON yang besar langsung pada origin backend (seperti Django, Rails, Spring Boot, atau Node.js) akan memicu exhaust CPU dan Memory, berujung pada Denial of Service sekunder (*ReDoS / Resource Exhaustion*). Cloudflare mengeksekusi inspeksi ini di 330+ PoP edge location secara terdistribusi.
2. **Zero-Day Patching Latency:** Ketika suatu CVE kritis ditemukan di public domain (misalnya CVE-2021-44228 Log4j), waktu yang dibutuhkan engineering team untuk patching, testing, build container, dan deploy ke production rata-rata mencapai hitungan hari hingga minggu. Managed WAF di edge memungkinkan pengaktifan proteksi virtual patching dalam skala global dalam waktu kurang dari 5 menit tanpa mengubah satu baris pun kode aplikasi backend.
3. **Kontekstual Machine Learning vs Signature:** Serangan bot modern menggunakan rotasi proxy residensial IP. Blacklisting IP tradisional menjadi tidak efektif. Integrasi Bot Intelligence dengan Ruleset WAF memungkinkan mitigasi berdasarkan behavior (perilaku navigasi dan TLS fingerprinting) alih-alih IP reputasi statis.

---

### 5. What (Deep-Dive Teknis Lengkap)

#### A. Ruleset Engine Architecture
Ruleset Engine Cloudflare memproses request menggunakan pohon fase (*phases execution pipeline*). Setiap fase dieksekusi secara berurutan sesuai urutan pemrosesan internal:
1. `http_request_firewall_custom`: Custom Rules yang didefinisikan user.
2. `http_ratelimit`: Rate Limiting Rules.
3. `http_request_firewall_managed`: Cloudflare Managed Rulesets dan OWASP Core Ruleset.

Dalam setiap fase, sebuah aturan terdiri dari dua komponen inti: **Expression** (kapan rule harus trigger) dan **Action** (apa yang harus dilakukan: `block`, `challenge`, `js_challenge`, `managed_challenge`, `log`, `skip`).

#### B. OWASP Core Ruleset & Anomaly Scoring Engine
Berbeda dari signature rules sederhana yang langsung memblokir saat mencocokkan satu pola, OWASP CRS menggunakan model *Anomaly Scoring*. Setiap rule yang cocok tidak langsung menghentikan request, melainkan menambahkan nilai (*anomaly score*) ke variabel akumulatif.

1. **Paranoia Levels (PL 1 - 4):**
   - **PL1:** Baseline rules. Tingkat *false positive* sangat rendah, memvalidasi request HTTP dasar dan serangan umum berisiko tinggi.
   - **PL2:** Proteksi tambahan terhadap serangan injeksi yang lebih ambigu, validasi karakter URI encoding ketat.
   - **PL3:** Memeriksa karakter non-ASCII, variasi regex lanjutan, dan validasi header HTTP yang ketat. Risiko *false positive* moderat.
   - **PL4:** Mode proteksi ekstrem. Membatasi hampir seluruh karakter khusus pada URI/Header. Ditujukan untuk lingkungan militer/keuangan berisiko tinggi, membutuhkan custom bypass rule yang masif.

2. **Anomaly Thresholds:**
   Di akhir inspeksi fase OWASP, Cloudflare membandingkan total akumulasi skor anomali dengan ambang batas (*threshold*):
   - **Low (Skor >= 60):** Hanya request dengan pola serangan yang sangat masif/banyak yang diblokir.
   - **Medium (Skor >= 40):** Rekomendasi standar production untuk aplikasi umum.
   - **High (Skor >= 25):** Rekomendasi untuk endpoint sensitif (Auth, Payment).
   - **Critical (Skor >= 5):** Sekali mencocokkan single high-confidence attack signature, request langsung dicegat.

#### C. Wirefilter Expression Engine & Payload Inspection
Cloudflare mengompilasi Custom Rules menggunakan mesin eksekusi berbasis Rust (*wirefilter*). Aturan didefinisikan dalam sintaks logis dengan field primitif L7:
- `http.request.uri.path`: Path target (contoh: `/api/v1/checkout`).
- `http.request.body.raw`: Unparsed payload body.
- `http.request.headers`: HTTP headers map.
- `cf.threat_score`: Skor ancaman reputasi IP Cloudflare (0-100).
- `cf.bot_management.score`: Skor kecerdasan buatan Cloudflare untuk memprediksi bot (1-29: automated malicious/bad bot, 30-99: human/legitimate).
- `cf.bot_management.verified_bot`: Boolean (`true` untuk bot mesin pencari resmi seperti Googlebot, Bingbot).

Fungsi transformatif diterapkan sebelum evaluasi untuk membatalkan teknik obfuscation penyerang:
- `lower()`: Menghindari bypass case-sensitivity (`sElEcT * fRoM`).
- `url_decode()`: Mendekode hex encoding (`%20`, `%27`).

#### D. Dynamic Rate Limiting Execution
Rate Limiting v2 Cloudflare beroperasi berbasis token bucket sliding-window. Karakteristik teknis:
- **Counting Expression:** Kriteria request mana yang harus menambah counter (misal: `http.request.uri.path eq "/login" and http.request.method eq "POST"`).
- **Matching Characteristics:** Kunci diferensiasi counter. Dapat berupa `ip.src`, header unik (`http.request.headers["x-api-key"]`), session cookie, atau kombinasi multivariat.
- **Period & Requests:** Jumlah request diizinkan per satuan waktu (contoh: 5 request per 60 detik).
- **Mitigation Action & Timeout:** Aksi yang diambil setelah threshold terlampaui (`block` atau `managed_challenge`) dan durasi aksi tersebut berlaku (misal: isolate selama 300 detik).

---

### 6. How
Proses deployment arsitektur WAF enterprise mengikuti metodologi staging terstruktur guna mencegah pemadaman layanan akibat *false positive*:

1. **Audit & Endpoint Categorization:** Petakan endpoint aplikasi menjadi beberapa kelas risiko: Public Static Content, Public Dynamic Content, Authenticated APIs, Administrative Panels, dan Authentication Endpoints (`/login`, `/register`, `/reset-password`).
2. **Deploy Managed Ruleset in Simulation (Log Mode):**
   Deploy Cloudflare Managed Ruleset dan OWASP CRS dalam mode `Log` (*Action Override* set to `Log`). Hal ini memungkinkan seluruh traffic diinspeksi dan dicatat di WAF Security Analytics tanpa mendisrupsi traffic user asli.
3. **Data Ingestion & Log Baseline Review:**
   Analisis data selama minimal 7-14 hari kerja. Cari pola legitimate traffic yang memicu rule OWASP PL2/PL3 (seperti request API yang mengirim format Markdown, XML payload, atau karakter base64 yang kerap terdeteksi sebagai SQLi/XSS).
4. **Deploy Exception / Skip Rules:**
   Buat custom rule dengan aksi `Skip` untuk rule ID atau tag CRS tertentu pada path spesifik yang terbukti memicu *false positive*.
5. **Enforce Mitigation (Block/Challenge Mode):**
   Ubah Action Override Managed Ruleset menjadi `Managed Challenge` atau `Block`.
6. **Implement Custom WAF & Rate Limiting Rules:**
   Terapkan aturan perimeter kustom (misal: blokir akses ke `/wp-admin` jika bukan dari VPN range, batasi login 5 request/menit).

---

### 7. Analogy
Bayangkan sebuah bandara internasional kelas satu:
- **Cloudflare Managed Ruleset** adalah daftar DPO (Daftar Pencarian Orang) dari Interpol yang ditempel di gerbang masuk. Jika wajah atau paspor seseorang persis dengan daftar penjahat internasional (known signature CVE), mereka langsung ditolak masuk.
- **OWASP Anomaly Scoring** adalah petugas bea cukai dengan formulir penilaian risiko. Jika Anda membawa cairan berlebih (PL1, +5 skor), tidak memiliki tiket pulang (PL2, +10 skor), dan berbicara dengan identitas mencurigakan (PL3, +15 skor), skor anomali Anda terakumulasi mencapai 30. Karena threshold bandara adalah 25, Anda ditarik ke ruang interogasi (*Managed Challenge*) atau dideportasi (*Block*), meskipun tidak ada satu aturan tunggal yang secara eksplisit melarang Anda secara mutlak.
- **Custom Expression Rules** adalah aturan internal khusus bandara: "Siapa pun yang ingin masuk ke ruang VIP operasional (Admin Panel) harus mengenakan seragam maskapai dan kartu identitas terverifikasi (IP VPN / Mutual TLS Header), jika tidak, ditolak seketika."
- **Rate Limiting** adalah sistem palang pintu otomatis di loket pengambilan bagasi: Anda hanya boleh menempelkan kartu parkir maksimal 3 kali per menit. Jika menempelkan kartu 50 kali dalam satu detik, palang pintu akan mengunci Anda selama 15 menit karena terdeteksi sebagai anomali mesin.

---

### 8. Diagram (ASCII)

```text
                  Incoming HTTP/HTTPS Request
                              |
                              v
   +------------------------------------------------------+
   |          Cloudflare Edge Network Anycast PoP         |
   |                                                      |
   |   [ PHASE 1: Custom Ruleset Execution ]              |
   |   - IP Whitelist / Blacklist                         |
   |   - Geo-blocking & ASN Filtering                     |
   |   - Header & URI Path Verification                   |
   |             | MATCH ACTION = BLOCK                   |
   |             +-------------------------------------> [ DROP 403 ]
   |             | PASSED / NEXT                          |
   |             v                                        |
   |   [ PHASE 2: Bot Management & Rate Limiting ]        |
   |   - Token Bucket Check (e.g. 5 req/min on /api)      |
   |   - Machine Learning Score (cf.bot_management.score) |
   |             | RATE EXCEEDED / BAD BOT                |
   |             +-------------------------------------> [ CHALLENGE/BLOCK ]
   |             | PASSED / NEXT                          |
   |             v                                        |
   |   [ PHASE 3: Managed Ruleset & OWASP CRS ]           |
   |   +----------------------------------------------+   |
   |   | Evaluasi Signature: Cloudflare Managed       |   |
   |   | (Zero-Days, Known Exploits, CVE Virtual Pat.)|   |
   |   +----------------------------------------------+   |
   |   | Evaluasi Anomaly: OWASP CRS (PL1 - PL4)      |   |
   |   | Rule A Triggered -> Anomaly Score += 5       |   |
   |   | Rule B Triggered -> Anomaly Score += 10      |   |
   |   | TOTAL ANOMALY SCORE vs THRESHOLD (e.g. 25)   |   |
   |   +----------------------------------------------+   |
   |             | SCORE >= THRESHOLD / MATCH SIGNATURE   |
   |             +-------------------------------------> [ ACTION ENFORCED ]
   |             |                                        |
   |             v ALL PHASES PASSED                      |
   +------------------------------------------------------+
                              |
                              v
     (Encrypted TLS Tunnel to Backend Infrastructure)
                              |
                              v
                  [ Origin Application Server ]
```

---

### 9. Simple Example
Sebuah Custom Rule sederhana untuk memblokir seluruh akses ke URI path WordPress administrative endpoints, kecuali request berasal dari alamat IP kantor operasional (`203.0.113.50`):

```text
(http.request.uri.path contains "/wp-admin" or http.request.uri.path eq "/wp-login.php") and ip.src ne 203.0.113.50
```
- **Aksi:** `Block`
- **Hasil:** Setiap client yang mencoba mengakses `/wp-admin/` atau `/wp-login.php` dari IP selain `203.0.113.50` akan langsung menerima HTTP 403 Forbidden di Edge Cloudflare. Server Origin tidak akan pernah menerima request tersebut.

---

### 10. Practical Example (Terraform HCL Production Setup)

Berikut konfigurasi production-grade menggunakan Terraform Cloudflare Provider (v4.x) untuk mendefinisikan Custom WAF, OWASP Managed Ruleset dengan Anomaly Scoring, serta Rate Limiting Ruleset.

```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "The Cloudflare Zone ID"
}

# 1. CUSTOM WAF RULESET PHASE: http_request_firewall_custom
resource "cloudflare_ruleset" "custom_waf_rules" {
  zone_id     = var.zone_id
  name        = "Enterprise Edge Security Custom Rules"
  description = "Custom rules for admin protection, payload checking, and bad bot blocking"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  # Rule A: Isolasi Admin Path dengan mTLS / IP Restriction
  rules {
    action      = "block"
    expression  = "(http.request.uri.path wildcard \"/admin*\" or http.request.uri.path wildcard \"/api/v1/internal*\") and not (ip.src in {198.51.100.0/24 203.0.113.0/24})"
    description = "Block unauthorized access to internal administrative endpoints"
    enabled     = true
  }

  # Rule B: Deteksi Eksploitasi Payload pada Body Request
  rules {
    action      = "managed_challenge"
    expression  = "http.request.method in {\"POST\" \"PUT\" \"PATCH\"} and (http.request.body.raw contains \"${jndi:\" or http.request.body.raw contains \"<?php\" or http.request.body.raw contains \"/etc/passwd\")"
    description = "Challenge malicious payload patterns in request body"
    enabled     = true
  }

  # Rule C: Mitigasi Scraping berbasis Bot Score & Verified Bot Bypass
  rules {
    action      = "managed_challenge"
    expression  = "(cf.bot_management.score < 20 and not cf.bot_management.verified_bot) and http.request.uri.path wildcard \"/catalog/*\""
    description = "Protect product catalog from aggressive scraping"
    enabled     = true
  }
}

# 2. MANAGED RULESET PHASE: http_request_firewall_managed (OWASP & Cloudflare Managed)
resource "cloudflare_ruleset" "managed_waf_rules" {
  zone_id     = var.zone_id
  name        = "Managed Rulesets Deployment"
  description = "Enforcing Cloudflare Managed Ruleset and OWASP CRS with Paranoia Tuning"
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  # Cloudflare Managed Ruleset
  rules {
    action = "execute"
    action_parameters {
      id = "efb79d4499904235e846d3d70ab7390e" # Cloudflare Managed Ruleset ID
    }
    expression  = "true"
    description = "Execute Cloudflare Managed Ruleset globally"
    enabled     = true
  }

  # Cloudflare OWASP Core Ruleset with Anomaly Scoring Configuration
  rules {
    action = "execute"
    action_parameters {
      id = "4814384a9e5d4991ba98123d11c44c91" # Cloudflare OWASP Core Ruleset ID
      matched_data {
        public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"
      }
      overrides {
        # Menentukan Ambang Batas Anomali (Anomaly Threshold)
        # Nilai skor CRS: 60 (Low), 40 (Medium), 25 (High), 5 (Critical)
        categories {
          category = "paranoia-level-3"
          enabled  = false # Nonaktifkan PL3 untuk menghindari false positive pada tahap awal
        }
        categories {
          category = "paranoia-level-4"
          enabled  = false # Nonaktifkan PL4
        }
        # Terapkan Anomaly Score Medium (Score >= 40 akan di-block)
        rules {
          id     = "6179ae15870a4bb7b2d480d4842ef999" # OWASP Score Evaluation Rule ID
          action = "block"
          score_threshold = 40
        }
      }
    }
    expression  = "true"
    description = "Execute OWASP Core Ruleset with Paranoia Level 2 and Medium Threshold"
    enabled     = true
  }
}

# 3. RATE LIMITING PHASE: http_ratelimit
resource "cloudflare_ruleset" "rate_limiting_rules" {
  zone_id     = var.zone_id
  name        = "API and Auth Rate Limiting"
  description = "Sliding window rate limit rules on authentication surfaces"
  kind        = "zone"
  phase       = "http_ratelimit"

  rules {
    action      = "block"
    expression  = "http.request.uri.path eq \"/api/v1/auth/login\" and http.request.method eq \"POST\""
    description = "Throttle authentication attempts: max 5 requests per minute per IP"
    enabled     = true

    action_parameters {
      response {
        content_type = "application/json"
        content      = "{\"error\": \"Too many login attempts. Isolated for 10 minutes.\"}"
        status_code  = 429
      }
    }

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 5
      mitigation_timeout  = 600 # Isolate IP during 10 minutes
      counting_expression = "http.request.method eq \"POST\" and http.request.uri.path eq \"/api/v1/auth/login\""
    }
  }
}
```

---

### 11. Real World Example
Sebuah platform fintech unicorn di Asia Tenggara mengalami serangan *Account Takeover* (ATO) dan serangan *zero-day exploitation* pada endpoint pembayaran API backend mereka. Penyerang menggunakan jaringan bot terdistribusi dengan jutaan residential IP berotasi, menyuntikkan payload SQL Injection kompleks yang dienkode dengan URL multi-layer, serta membanjiri endpoint login (`/api/v2/customer/token`).

**Arsitektur Mitigasi yang Diterapkan:**
1. **OWASP CRS Deployment:** Diimplementasikan dengan Paranoia Level 2, Anomaly Score Threshold diatur ke `25` (High Sensitivity) khusus untuk path `/api/*`. Request yang mengandung malformed JSON atau ekspresi SQL unik terdeteksi secara agregat, menghasilkan skor anomali rata-rata 35, sehingga request di-block di edge.
2. **Payload Inspection & Skip Exception:** Ditemukan bahwa mitra bank pihak ketiga mengirim callback pembayaran dengan payload XML terenkripsi yang memicu rule `OWASP Generic SQLi Detection` (Rule ID: `942100`). Alih-alih menurunkan paranoia level secara global, tim SRE membuat **Custom Skip Rule**:
   ```text
   http.request.uri.path eq "/api/v2/callback/bank-partner" and ip.src in $BANK_PARTNER_CIDR
   ```
   Aksi: `Skip -> Disable OWASP Rule 942100`.
3. **Advanced Rate Limiting Berbasis Session Token:** Mengingat penyerang merotasi IP residensial, rate limiting berbasis `ip.src` tidak efektif. Tim beralih menggunakan karakteristik `http.request.headers["x-device-fingerprint"]`. Limit ditetapkan: 3 request per 60 detik. Serangan ATO berhasil diredam 99.8% tanpa mendegradasi performa user sah.

---

### 12. Trade-offs
1. **Paranoia Level vs False Positive Rate:**
   - *Trade-off:* Meningkatkan Paranoia Level ke PL3 atau PL4 memberikan visibilitas dan proteksi maksimal terhadap ancaman zero-day dan payload tersembunyi.
   - *Downside:* Tingkat false positive melonjak drastis. Validasi karakter seperti tanda titik koma (`;`), tanda hubung ganda (`--`), atau string JSON kompleks dalam parameter API akan dicegat, berisiko menghentikan transaksi bisnis yang sah (*lost revenue*).
2. **Body Inspection Engine Limits:**
   - *Trade-off:* Menginspeksi request body memastikan penyerang tidak menyembunyikan payload di dalam `POST` payload data.
   - *Downside:* Cloudflare memiliki batasan ukuran inspeksi payload (128 KB standard; hingga 500 KB / 32 MB pada Enterprise plan dengan custom limit). Payload yang dikirimkan melebihi batas inspeksi akan diteruskan ke origin tanpa evaluasi body penuh, membuka risiko *payload chunking evasion* jika origin tidak membatasi ukuran request.
3. **Managed Challenge vs Immediate Block:**
   - *Trade-off:* `Block` sepenuhnya menghentikan transmisi paket; menghemat bandwidth dan kapasitas komputasi origin secara instan.
   - *Downside:* Jika aturan memiliki margin kesalahan (false positive), legitimate user terblokir total tanpa pemulihan. Sebaliknya, `Managed Challenge` memberikan kesempatan pada browser user untuk membuktikan integritas via invisible cryptographic challenge, namun menambah latensi akses awal bagi client.

---

### 13. When To Use
- Aplikasi web yang mengekspos endpoint publik yang memproses data sensitif (PII, sistem autentikasi, transaksi finansial).
- Aplikasi monolitik warisan (*legacy applications*) yang sulit atau membutuhkan waktu lama untuk diperbaiki celah keamanannya di level kode sumber (*virtual patching*).
- Sistem API publik yang menjadi sasaran empuk serangan brute-force, web scraping, dan automated bot abuse.
- Kebutuhan kepatuhan regulasi keamanan data tingkat enterprise (misalnya PCI-DSS Requirement 6.6, ISO 27001, SOC 2).

---

### 14. When NOT To Use
- **Internal Microservices East-West Traffic:** Komunikasi RPC/gRPC privat antar-kontainer di dalam private cluster internal (gunakan Service Mesh seperti Istio / Cilium mTLS; jangan melewatkan traffic internal private ke public edge network).
- **High-Throughput Binary Streaming:** Endpoint streaming raw binary murni atau video chunk UDP/TCP non-HTTP berukuran gigabyte di mana inspeksi WAF layer-7 berbasis teks tidak relevan dan justru memicu latency overhead signifikan.
- **Static Content pada Storage Bucket:** File statis murni (`.png`, `.css`, `.mp4`) yang di-serve dari storage origin publik tidak membutuhkan inspeksi OWASP CRS yang kompleks (cukup gunakan caching layer dan security header dasar).

---

### 15. Common Mistakes
1. **Langsung Mengaktifkan OWASP CRS Mode "Block" di Production:** Mengaktifkan OWASP Core Ruleset langsung ke aksi `Block` tanpa tahap baseline logging (`Log Mode`) dapat merusak integrasi API klien yang menggunakan karakter khusus.
2. **Mengevaluasi Rate Limiting Hanya Berdasarkan IP Tunggal:** Mengasumsikan penyerang selalu datang dari 1 IP. Penyerang profesional memanfaatkan ribuan proxy bot. Mengandalkan `ip.src` tanpa kombinasi Cookie, Fingerprint Header, atau Bot Score membuat rate limit mudah di-bypass.
3. **Urutan Evaluasi Ruleset (Rules Priority) yang Salah:** Menempatkan aturan general blocking di atas aturan bypass/allowlist khusus, sehingga traffic legitimate dari internal monitoring/healthcheck atau integrasi API partner ikut terblokir sebelum sempat di-*skip*.
4. **Tidak Menggunakan `lower()` pada Custom String Matching:** Menggunakan ekspresi `http.request.uri.path contains "admin"` tanpa normalisasi. Penyerang dapat mengirimkan request ke `/AdMiN/` atau `/ADMIN/` untuk mengecoh aturan pada server origin yang case-insensitive (misal: Windows IIS atau konfigurasi routing tertentu).

---

### 16. Best Practices
1. **Lakukan Staging Rule Deployment Menggunakan Log Action:** Selalu gunakan action `Log` saat meluncurkan aturan baru minimal 7 hari. Analisis log event menggunakan Cloudflare Security Analytics atau kirimkan via Logpush ke SIEM (Datadog/Splunk) untuk memastikan zero false positive.
2. **Kombinasikan Anomaly Scoring dengan Paranoia Level Bertingkat:** Gunakan PL1 untuk rute aplikasi umum, dan naikkan ke PL2 atau PL3 secara bersyarat hanya pada endpoint berisiko tinggi (misalnya: `(http.request.uri.path wildcard "/api/v*/auth*")`).
3. **Optimalkan Normalisasi Ekspresi WAF:** Selalu gunakan transformer function seperti `url_decode()` dan `lower()` pada inspeksi string untuk mengeliminasi bypass teknik evasif.
4. **Gunakan Granular Exception Handling:** Jangan pernah mematikan seluruh OWASP CRS secara global saat terjadi false positive. Gunakan mekanisme WAF Exception (Skip Action) spesifik untuk Rule ID tertentu pada URI tertentu yang terisolasi.
5. **Enforce IaC dan Version Control:** Kelola seluruh Ruleset WAF menggunakan Terraform atau Cloudflare CLI/API yang terintegrasi dengan GitOps pipeline, lengkapi dengan automated syntax and semantic linting.

---

### 17. Troubleshooting

| Masalah / Gejala | Root Cause Teknis | Solusi / Resolusi SRE |
| :--- | :--- | :--- |
| **HTTP 403 Forbidden** masif pada client legitimate setelah OWASP CRS aktif. | Akumulasi Anomaly Score melebihi threshold akibat karakter legal pada request payload (misal: payload JSON berisi syntax code). | Buka **Security Events**, cari Request ID terkait. Identifikasi Rule ID spesifik penyumbang skor terbesar (misal: Rule ID `942100`). Buat WAF Exception (`Skip`) untuk Rule ID tersebut khusus pada endpoint URI yang terdampak. |
| Serangan Brute Force terus tembus origin meskipun Rate Limiting aktif. | Penyerang menggunakan residential proxy network, merotasi ribuan IP berbeda setiap hitungan detik. Karakteristik `ip.src` tidak pernah mencapai limit. | Ubah karakteristik rate limiting ke stateful token lain: Session Token Header, JSON Web Token (JWT) claim, atau gunakan `cf.bot_management.score` untuk melempar Managed Challenge kepada request mencurigakan. |
| Request Body Injection lolos dari inspeksi WAF. | Ukuran request body melebihi batas buffer inspeksi Cloudflare (128 KB default buffer size) sehingga payload berada di luar offset inspeksi. | Aktifkan mitigasi payload limit di WAF, atau terapkan Custom Rule untuk me-reject HTTP POST request dengan `http.request.headers["content-length"]` yang melebihi batas aman jika endpoint tidak dirancang untuk file upload. |
| Partner API sah terblokir oleh Bot Management. | User-Agent partner tidak terdaftar sebagai verified bot dan client request tidak menjalankan JavaScript sehingga gagal saat menerima challenge. | Daftarkan ASN atau IP range resmi partner ke dalam Custom Bypass Rule dengan kriteria `ip.src in $PARTNER_IPS` dan set Action ke `Skip -> All remaining security rules`. |

---

### 18. Exercise
1. Tulis ekspresi Cloudflare Wirefilter yang melakukan tugas berikut:
   - Target request dengan method `POST` atau `PUT`.
   - Mengakses URI `/api/v1/user/profile`.
   - Memiliki ukuran header `User-Agent` kurang dari 10 karakter ATAU tidak memiliki header `User-Agent` sama sekali.
   - Tidak memiliki skor Bot Management resmi (Bot Score < 30).
   - Tentukan Action yang paling tepat antara `Block`, `Log`, atau `Managed Challenge`.
2. Jelaskan perbedaan mendasar mekanisme evaluasi antara Cloudflare Managed Ruleset (Traditional Rule Matching) dengan Cloudflare OWASP Core Ruleset (Score-based Matching) ketika menangani request HTTP tunggal.

---

### 19. Challenge
Anda ditugaskan mengamankan sistem perbankan terbuka (Open Banking API). API ini memiliki endpoint transfer dana: `POST /api/v3/banking/transfers`.
Spesifikasi skenario:
1. Endpoint menerima payload berformat JSON dengan volume transaksi tinggi.
2. Penyerang mencoba melakukan targeted SQLi dan command injection di dalam payload JSON.
3. Klien transaksi sah berasal dari perbankan lain dan mobile app consumer.
4. Partner Bank mengakses dari IP range statis, sedangkan Mobile App consumer mengakses dari IP dinamis di seluruh dunia.
5. Anda ditugaskan membuat arsitektur Cloudflare Ruleset (Terraform) yang mencakup:
   - Skip inspeksi OWASP tertentu untuk IP Partner Bank yang tersertifikasi.
   - Enforce OWASP CRS Paranoia Level 3 dengan Anomaly Threshold High (Skor 25) untuk endpoint tersebut bagi traffic publik mobile app.
   - Rate limiting adaptif: 10 request per 60 detik per unique access token header (`Authorization`), dengan respon custom JSON 429 ketika limit terlampaui.

Rancang arsitektur HCL dan susun rationale mitigasi resiko jika terjadi zero-day exploit!

---

### 20. Summary
Cloudflare Web Application Firewall berbasis Ruleset Engine v2 menghadirkan ekosistem inspeksi Layer 7 yang elastis dan terdesentralisasi di level global edge. Fondasi keamanan enterprise dibangun atas pemahaman menyeluruh terhadap:
- **Cloudflare Managed Ruleset** yang berfungsi sebagai mitigasi instan terhadap CVE global tanpa sentuhan kode.
- **OWASP CRS Anomaly Scoring** yang memberikan pertahanan adaptif berlapis dengan penyeimbangan presisi antara Paranoia Level dan skor ambang batas untuk menekan false positive.
- **Custom Expression Engine** yang memberikan kapabilitas granular kepada SRE untuk menyusun parameter keamanan sesuai model ancaman spesifik aplikasi.
- **Rate Limiting & Bot Intelligence** yang mengonversi perimeter WAF dari sekadar pemindai signature statis menjadi sistem pertahanan perilaku adaptif berbasis data-driven edge security.

---