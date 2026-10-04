# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 05: DDoS Mitigation, Rate Limiting, dan Bot Management**  
**Kategori: 05-DevOps-Cloud-and-SRE**

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengidentifikasi arsitektur internal mitigasi Cloudflare: dari layer L3/L4 (*Gatekeeper*, *dosd*, eBPF/XDP) hingga layer L7 (*Frontline*, *WAF Engine*, *Wirefilter*).
- Merancang dan mengimplementasikan aturan *Advanced Rate Limiting* berbasis multi-karakteristik (IP, Token/Header, JA4, Query Param) menggunakan Ruleset Engine v2 dan Terraform.
- Menerapkan *Enterprise Bot Management* dengan memadukan *Machine Learning Bot Score*, *Behavioral Analysis*, deteksi anomali sesi, serta sidik jari TLS (*JA3/JA4 Fingerprints*).
- Menghubungkan mitigasi bot dan DDoS ke dalam strategi *defense-in-depth* tanpa memicu *false positive* pada mobile API client, corporate NAT, dan search engine crawler resmi.
- Melakukan diagnostik, pengujian penetrasi beban terkontrol, dan analisis forensik insiden menggunakan Cloudflare GraphQL Analytics, Logpush, dan Ray ID tracing.

---

### 2. Prerequisite
Untuk memahami materi ini secara mendalam, peserta wajib menguasai:
- Pengetahuan dasar protokol jaringan: TCP/IP 3-Way Handshake, TLS 1.2/1.3 Handshake (Client Hello, Cipher Suites, Extensions), HTTP/2 dan HTTP/3 Frame Spec.
- Pemahaman konfigurasi dasar Cloudflare DNS, Proxied Mode (Orange Cloud), dan Cloudflare Edge Ruleset syntax.
- Pengalaman menulis kode *Infrastructure-as-Code* menggunakan Terraform (Cloudflare Provider v4.x).
- Pemahaman mengenai konsep dasar mitigasi keamanan web: Token Bucket Algorithm, Leaky Bucket, Sliding Window Counter, serta OWASP Top 10 API Security Risks.

---

### 3. Concept & Internal Architecture

Mitigasi DDoS, Rate Limiting, dan Bot Management di Cloudflare bukanlah satu proses sekuensial monolitik, melainkan *pipeline* multi-layer terdistribusi yang dijalankan di setiap server edge pada ribuan PoP (*Points of Presence*) global.

```
                    Internet Ingress (Anycast BGP)
                                  │
                                  ▼
                     [ L4 Load Balancer: Unimog ]
                                  │
                                  ▼
               [ L3/L4 Mitigation: XDP/eBPF + Gatekeeper ]
                                  │
                                  ▼
                   [ Layer 4 Daemon: dosd (L4 Drop) ]
                                  │
                                  ▼
                [ L7 Proxy Core: Frontline (FL/NGINX) ]
                                  │
                   ┌──────────────┴──────────────┐
                   │   TLS Decryption Engine     │
                   │   - JA3 / JA4 Extraction    │
                   │   - HTTP/2 Frame Fingerprint│
                   └──────────────┬──────────────┘
                                  │
                                  ▼
                   [ Bot Management Pipeline ]
                   ├─ Heuristics & Static Signatures
                   ├─ Machine Learning Score Engine (1-99)
                   ├─ Behavioral & Anomaly Detection
                   └─ Verified Bot Directory Match
                                  │
                                  ▼
                 [ WAF Ruleset Engine v2 (Wirefilter) ]
                   ├─ Managed Rulesets (OWASP, Core)
                   ├─ Custom Firewall Rules
                   └─ Advanced Rate Limiting Engine
                        (Memcached Sliding Window Cluster)
                                  │
                                  ▼
                  Mitigation Action: Allow / Log /
                     Managed Challenge / Block
                                  │ (Jika lolos)
                                  ▼
                    To Origin Server / Cloudflare Worker
```

#### A. Layer 3/Layer 4: Unimog, eBPF/XDP, Gatekeeper, dan `dosd`
1. **Unimog**: Load balancer L4 internal Cloudflare yang merutekan paket dari antarmuka jaringan fisik ke core server melalui protokol UDP-in-UDP encapsulation.
2. **eBPF/XDP (eXpress Data Path)**: Filter berbasis kernel Linux yang mengeksekusi inspeksi paket langsung pada network driver ring buffer sebelum alokasi `sk_buff` dilakukan oleh kernel.
3. **Gatekeeper**: Komponen mitigasi DDoS L3/L4 terdistribusi. Gatekeeper mengecek kuota paket per detik (pps) dan bit per detik (bps) terhadap baseline normal jaringan. Serangan volumetrik (SYN Flood, UDP Amplification, ICMP Flood) di-drop langsung di layer ini dalam hitungan mikrodetik.
4. **`dosd` (Denial of Service Daemon)**: Daemon user-space yang bertugas mengagregasi sampel sFlow/NetFlow, mendeteksi pola serangan baru secara otonom, dan menginjeksikan aturan penolakan (drop rules) langsung ke dalam kernel driver via eBPF maps secara real-time tanpa intervensi manusia.

#### B. Layer 7 Proxy Core & Fingerprinting
Ketika koneksi TCP dan TLS selesai di-terminate pada L7 Proxy (*Frontline*):
1. **JA3/JA4 Fingerprint Extraction**: Karakteristik TLS Client Hello diurai: versi TLS, daftar cipher suite yang didukung, daftar extensions, elliptic curves, dan format point. Pada JA4, representasi hash 36 karakter dipetakan ke profil client (browser modern, Node.js script, Python `urllib`, Go-http-client).
2. **HTTP/2 Frame & Header Order Fingerprint**: Urutan header HTTP (`:method`, `:authority`, `:scheme`, `:path`, `user-agent`, `accept`) dan parameter WINDOW_UPDATE diuji. Library bot otomatis sering mengekspos struktur frame HTTP/2 yang kaku dan berbeda dari browser Chromium/WebKit asli.

#### C. Machine Learning Bot Management Architecture
Cloudflare Bot Management memproses setiap request melalui model inferensi berbobot rendah (*low-latency inference model*) yang menghasilkan nilai integer `cf.bot_management.score` berjarak 1 hingga 99:
- **Score 1**: Terkonfirmasi berbahaya (*Automated Malicious Bot* / Scraper / Credential Stuffer).
- **Score 2 - 29**: Probabilitas tinggi bot (*Likely Automated*).
- **Score 30 - 99**: Probabilitas tinggi manusia (*Likely Human*).
- **Verified Bots**: Bot mesin pencari resmi (Googlebot, Bingbot) diidentifikasi melalui Reverse DNS lookup yang divalidasi secara kriptografis dan ASN IP whitelisting terpusat, memetakan variabel `cf.bot_management.verified_bot == true`.

#### D. Advanced Rate Limiting Core Engine
Tidak seperti rate limiter klasik yang hanya mengandalkan IP address tunggal, *Advanced Rate Limiting* (Ruleset Engine v2) mengimplementasikan:
- **Characteristics Hashing**: Hash komposit dibentuk dari beberapa variabel: `hash(IP, Authorization Header)` atau `hash(Cookie Session, Endpoint)`.
- **Distributed Sliding Window Counter**: Edge node menggunakan cluster in-memory cache lokal (berbasis memcached/shared memory) yang disinkronisasi secara asinkronus ke edge node tetangga dalam colocation yang sama. Jendela waktu (60 detik, 10 detik) dihitung menggunakan interpolasi bobot linear (*weighted sliding window counter*) untuk mencegah burst pada pergantian window boundary.

---

### 4. Why & What

| Paradigma | Implementasi Tradisional (Origin-based / IPTables) | Cloudflare Edge Engine (Enterprise) |
| :--- | :--- | :--- |
| **Kapasitas Mitigasi** | Dibatasi oleh upstream link data center (1 Gbps - 40 Gbps). Rentan *bandwidth saturation*. | Kapasitas Anycast Global (>300 Tbps). Mitigasi diserap langsung di PoP terdekat dari penyerang. |
| **Beban Komputasi TLS** | CPU origin server habis untuk TLS termination serangan ribuan request HTTPS/detik. | TLS di-terminate di Edge. Origin hanya menerima lalu lintas valid atau koneksi tunnel terenkripsi. |
| **Rate Limiting Basis** | Hanya `client_ip`. Rentan memblokir seluruh kantor/kampus di balik satu CGNAT. | Multi-karakteristik: JA4 Fingerprint, API Token, Session Cookie, Header custom. |
| **Deteksi Bot** | User-Agent matching & IP Blacklist statis (Sangat mudah dipalsukan dengan rotating proxy). | Machine learning berbasis TLS fingerprint, behavioral inter-request timing, proof-of-work challenge. |
| **Respons Mitigasi** | TCP Reset atau 429 Too Many Requests statis. | Managed Challenge (Cloudflare Turnstile tanpa interaksi captcha visual), Block, atau Log. |

---

### 5. How (Workflow Detail)

Berikut alur eksekusi saat request masuk dari internet hingga diteruskan ke origin:

```
[Request Masuk] 
       │
       ▼
1. L3/L4 Inspection: Apakah paket bagian dari SYN/UDP flood terdistribusi?
       ├─ YA  ──> Drop pada level network card (XDP driver level via eBPF). Selesai.
       └─ TIDAK
       ▼
2. TLS Termination & Fingerprinting: Frontline mengekstrak JA4, HTTP/2 Stream attributes.
       │
       ▼
3. Bot Management Evaluation: Model inferensi edge menghitung score (1-99).
       │
       ▼
4. Ruleset Engine Execution Phase (Custom WAF & Advanced Rate Limiting):
       │
       ├─ Apakah request cocok dengan ekspresi filter (URI, Method, Headers)?
       │    ├─ TIDAK ──> Lanjut ke fase routing origin.
       │    └─ YA
       │         ▼
       ├─ Hitung hash komposit karakteristik (e.g. Client IP + JA4 + API Key).
       │         ▼
       ├─ Query in-memory sliding window counter pada local PoP memory.
       │         ▼
       ├─ Apakah nilai hitungan > Threshold dalam periode waktu N?
       │    ├─ TIDAK ──> Increment counter. Lolos ke origin.
       │    └─ YA
       │         ▼
       └─ Jalankan Action Mitigasi yang dikonfigurasi:
            ├─ action = "block" -> Kembalikan HTTP 403 / 429 instan.
            ├─ action = "managed_challenge" -> Sajikan challenge non-intrusif.
            │    ├─ Lolos challenge -> Set clearance cookie, izinkan request.
            │    └─ Gagal challenge -> Tolak akses.
            └─ action = "log" -> Tambahkan tag telemetri, lanjutkan ke origin.
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah bandara internasional yang sangat sibuk:
- **L3/L4 Gatekeeper (XDP/eBPF)**: Pagar perimeter luar bandara. Truk atau kendaraan berat tak dikenal yang mencoba menabrak pagar langsung dihancurkan di batas luar sebelum mencapai gedung terminal.
- **JA3/JA4 Fingerprinting**: Pemeriksaan jenis dan model koper serta pakaian penumpang. Meskipun penipu mengenakan seragam pramugari (User-Agent palsu), sepatu dan resleting kopernya (TLS Handshake & Cipher) menunjukkan ia bukan kru pesawat resmi.
- **Bot Score**: Petugas intelijen bandara yang memindai gerak-gerik penumpang secara real-time. Jika seseorang berjalan mondar-mandir menatap pintu darurat (credential stuffing), skor kecurigaan naik menjadi 99 (pasti ancaman).
- **Advanced Rate Limiting**: Pintu putar otomatis di pintu boarding. Penumpang hanya diizinkan memindai boarding pass (API Token) 1 kali per 10 detik. Jika memindai 20 kali dalam semenit, pintu terkunci otomatis untuk orang tersebut, tanpa menghalangi antrean orang lain yang berdiri di baris yang sama (CGNAT safe).

```
                           ARSITEKTUR INSPEKSI EDGE
+-------------------------------------------------------------------------+
| Cloudflare Global Anycast Edge Node                                     |
|                                                                         |
|  [ Ingress Packet ]                                                     |
|         |                                                               |
|         +---> [ XDP Filter ] ---> (Drop L3/L4 Flood: 100M pps)          |
|                    | (Paket valid TCP)                                  |
|                    v                                                    |
|         [ NGINX/Frontline L7 Proxy ]                                    |
|                    |                                                    |
|                    +---> JA4 Digest: "t13d1516h2_8daaf6156415_..."     |
|                    +---> Bot Engine: Score = 05 (Likely Scraper)        |
|                    |                                                    |
|                    v                                                    |
|         [ Ruleset Engine Evaluation ]                                   |
|         +-------------------------------------------------------------+ |
|         | Kondisi: uri.path eq "/v1/auth" && cf.bot_mgmt.score < 30   | |
|         | Aksi   : Managed Challenge                                  | |
|         +-------------------------------------------------------------+ |
|                    | (Tantangan Kriptografis / Turnstile)               |
|                    +---[ Gagal / Non-browser ]---> (Drop: HTTP 403)     |
|                    | (Lolos / Valid Token)                              |
|                    v                                                    |
|         [ Sliding Window Counter ]                                      |
|         +-------------------------------------------------------------+ |
|         | Karakteristik : ip.src + http.request.headers["x-api-key"]  | |
|         | Batas         : > 100 req / 60 detik                        | |
|         +-------------------------------------------------------------+ |
|                    | (Counter = 101)                                    |
|                    +-----------------------------> (Response: HTTP 429) |
+-------------------------------------------------------------------------+
                     | (Counter <= 100)
                     v
             [ Upstream ke Origin ]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Custom Expression Rule Melindungi Endpoint Login
Aturan WAF sederhana menggunakan bahasa Cloudflare Expression Engine untuk memblokir bot dengan skor rendah yang menyerang path login:

```text
(http.request.uri.path eq "/api/v1/auth/login" and 
 http.request.method eq "POST" and 
 cf.bot_management.score lt 20)
```
*Action*: `Managed Challenge`

#### B. Practical Example: Terraform Production Ruleset (Advanced Rate Limiting + Bot Shield)
Implementasi Infrastructure-as-Code menggunakan Provider Cloudflare v4.x untuk API berskala enterprise. Kode ini menerapkan multi-karakteristik rate limiting berdasarkan gabungan IP dan API-Key header, serta membedakan bot terverifikasi.

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.35.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "Target Cloudflare Zone ID"
}

# 1. Advanced Rate Limiting Ruleset untuk Sensitive Transaction Endpoint
resource "cloudflare_ruleset" "advanced_rate_limiting" {
  zone_id     = var.zone_id
  name        = "Production Tier Rate Limiting Policy"
  description = "Mitigasi abusive API client dan credential abuse"
  kind        = "zone"
  phase       = "http_ratelimit"

  rules {
    action      = "block"
    description = "Limit checkout request rate per API Token & IP"
    expression  = <<-EOT
      (http.request.uri.path eq "/api/v2/checkout" and 
       http.request.method eq "POST" and 
       not cf.bot_management.verified_bot)
    EOT

    ratelimit {
      # Hitung berdasarkan kombinasi IP Address dan Custom Header X-User-ID
      characteristics = [
        "ip.src",
        "http.request.headers[\"x-user-id\"]"
      ]
      
      # Window waktu counter (dalam detik)
      period              = 60
      requests_per_period = 30
      
      # Periode mitigasi saat threshold terlampaui
      mitigation_timeout = 600

      counting_expression = "http.request.method eq \"POST\""
    }

    action_parameters {
      response {
        content_type = "application/json"
        content      = "{\"error\": \"RATE_LIMIT_EXCEEDED\", \"message\": \"Terlalu banyak permintaan transaksi. Coba lagi dalam 10 menit.\", \"status\": 429}"
        status_code  = 429
      }
    }
    enabled = true
  }

  rules {
    action      = "managed_challenge"
    description = "Challenge agresif untuk low-score bot pada GraphQL query"
    expression  = <<-EOT
      (http.request.uri.path eq "/graphql" and 
       cf.bot_management.score le 15 and 
       not cf.bot_management.verified_bot)
    EOT
    enabled     = true
  }
}

# 2. Custom WAF Rule untuk Memblokir Fingerprint Scanner Otomatis
resource "cloudflare_ruleset" "waf_custom_bot_defense" {
  zone_id     = var.zone_id
  name        = "Production Advanced Bot Defense"
  description = "Enforce JA4 fingerprinting & anomaly blocks"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  rules {
    action      = "block"
    description = "Block known illicit scrapers using JA4 TLS Fingerprint"
    # Contoh JA4 hash yang diasosiasikan dengan library automation tools standar (e.g., Python requests default tanpa modified ciphers)
    expression  = <<-EOT
      (cf.bot_management.ja4 in {"t13d1516h2_8daaf6156415_a0f5a7b7a8d5"} and 
       not cf.bot_management.verified_bot and 
       http.request.uri.path contains "/api/")
    EOT
    enabled     = true
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Serangan Distributed Credential Stuffing & L7 HTTP Flood pada Marketplace Unicorn saat Flash Sale

- **Profil Beban**: 
  - Normal traffic: 85.000 RPS (Requests Per Second).
  - Puncak serangan: 1.400.000 RPS terdistribusi dari 450.000 residential IP proxy yang disewa penyerang.
  - Vektor Serangan: POST request ke `/api/v3/auth/token` menggunakan User-Agent acak meniru Chrome Mobile, payload JSON valid, tapi credential didapat dari kebocoran data external.
- **Dampak Awal**:
  - Origin database auth (PostgreSQL/Redis) mengalami saturasi CPU 100% akibat operasi hash `bcrypt`.
  - Rate limiting standar berbasis IP tunggal gagal total karena setiap IP penyerang hanya mengirim 1 request setiap 3-5 menit (low-and-slow per IP, tapi masif secara agregat).
- **Arsitektur Mitigasi & Resolusi**:
  1. **Aktivasi JA4 Fingerprint Baselining**: Analisis Logpush menunjukkan 92% request serangan menghasilkan JA4 fingerprint yang identik: `t13d3112h2_e8f1e7e783de_...` (dikompilasi dari tool headless berbasis Go). Klien valid asli mayoritas berasal dari aplikasi mobile Android (JA4: `t13d190900_...`) dan iOS (JA4: `t13d201300_...`).
  2. **Penerapan Tiered Bot Score Filtering**:
     - Skor 1 - 10: Di-drop instan (`Action: Block`) pada Edge tanpa menyentuh origin.
     - Skor 11 - 40: Diberikan `Managed Challenge` via Cloudflare Turnstile token verification di background aplikasi web.
  3. **Composite Rate Limiting**:
     Menerapkan Advanced Rate Limiting dengan karakteristik:
     `[cf.bot_management.ja4, http.request.headers["cf-ipcountry"]]`
     dengan batas 1.000 req/menit per JA4+Country pair untuk endpoint otentikasi.
- **Hasil**:
  - 1,32 juta RPS malicious traffic diserap langsung di edge PoP Cloudflare.
  - Beban RPS pada origin auth cluster turun kembali ke 88.000 RPS.
  - False positive rate pada customer asli terukur di bawah **0.002%**.

---

### 9. Trade-offs

| Parameter Desain | Opsi Agresif (High Strictness) | Opsi Seimbang (Balanced Protection) | Opsi Longgar (Permissive/Observe) |
| :--- | :--- | :--- | :--- |
| **Aksi Bot Rendah** | `Block` langsung untuk score < 30. | `Managed Challenge` untuk score < 30, `Block` < 5. | `Log` atau inject header `cf-bot-score` ke origin. |
| **Resiko False Positive** | **Tinggi**. Pengguna dengan browser lawas, korporat VPN, atau embedded browser akan terblokir. | **Sangat Rendah**. Browser manusia menyelesaikan JS challenge secara transparan. | **Nol**. Tidak ada request pengguna yang diblokir di Edge. |
| **Latensi Edge** | Tercepat (Request di-drop di edge sebelum processing komputasi berat). | Bertambah ~15-50ms jika terjadi eksekusi JavaScript Turnstile. | Tidak ada penambahan latensi mitigasi, beban dilempar ke origin. |
| **Beban Origin** | Minimum. Origin hanya melayani user terverifikasi. | Rendah. Hanya request yang lolos challenge yang sampai origin. | Maksimum. Origin berisiko crash jika terjadi lonjakan traffic bot. |
| **Kompatibilitas API (M2M)** | Berisiko merusak integrasi B2B API jika klien tidak mendukung penanganan challenge. | Memerlukan bypass rules khusus (mTLS / Pre-Shared Token) untuk partner API. | B2B API aman berjalan tanpa kendala teknis mitigasi. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Common Mistakes)
1. **Memblokir Endpoint API Mobile Menggunakan Action Managed Challenge**:
   - Mobile app native (iOS/Android) yang mengonsumsi JSON REST API tidak memiliki DOM browser engine penuh untuk menjalankan Cloudflare JavaScript Challenge. Menghasilkan response 403 HTML challenge page ke aplikasi, menyebabkan kegagalan parsing JSON (*parse error*).
   - *Solusi*: Gunakan mTLS, Cloudflare App Attestation, atau gunakan `Block` terarah hanya jika Bot Score < 5 didukung verifikasi signature request.
2. **Rate Limiting Hanya Berbasis Single Header `X-Forwarded-For`**:
   - Penyerang dapat menyuntikkan header `X-Forwarded-For: 127.0.0.1` palsu jika Cloudflare tidak dikonfigurasi untuk menimpa header tersebut.
   - *Solusi*: Selalu gunakan karakteristik native `ip.src` atau field Cloudflare `cf.ray` / token session internal.
3. **Mengabaikan Search Engine Crawler (SEO Suicide)**:
   - Membuat rule WAF: `cf.bot_management.score lt 30 -> Block` tanpa mengecualikan `cf.bot_management.verified_bot`. Akibatnya Googlebot, Bingbot, dan Applebot diblokir total, menghancurkan ranking SEO dalam beberapa jam.
   - *Solusi*: Selalu sertakan `and not cf.bot_management.verified_bot` pada ekspresi WAF.

#### Panduan Troubleshooting Langkah demi Langkah (Edge Debugging)
Jika request klien legitimate terblokir (false positive):
1. **Dapatkan Ray ID**: Minta nilai header `CF-RAY` dari klien yang bermasalah (contoh: `87a1b2c3d4e5f6-CGK`).
2. **Kueri Log via GraphQL Analytics / Cloudflare Dashboard**:
   Filter log berdasarkan `rayName: "87a1b2c3d4e5f6-CGK"`.
3. **Analisis Metadata Eksekusi**:
   - Periksa field `EdgePathingStatus`: Apakah `nr` (no rule), `mon` (monitored), atau `rw` (rule match)?
   - Periksa `FirewallRuleID` dan `ActionTaken`: Aturan mana yang aktif?
   - Cek `ClientRequestPath`, `BotScore`, dan `JA4`: Berapa skor bot yang terhitung?
4. **Reproduksi Curl Menggunakan Spesifik JA4/Cipher**:
   ```bash
   # Test akses endpoint menggunakan cipher suite spesifik untuk mengamati perilaku bot engine
   curl -svo /dev/null -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
     --ciphers 'ECDHE-RSA-AES128-GCM-SHA256' \
     https://api.domain.com/v1/health \
     -w "HTTP Code: %{http_code}\nCF-Ray: %{header_json}\n"
   ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Baseline Profiling**: Jalankan aturan baru dalam mode `Action: Log` minimal selama 7 hari sebelum mengubah aksi menjadi `Managed Challenge` atau `Block`.
- [ ] **Kombinasikan Bot Score dengan Karakteristik Kontekstual**: Jangan gunakan `cf.bot_management.score` berdiri sendiri. Kombinasikan dengan `http.request.uri.path`, `http.request.method`, dan status login pengguna.
- [ ] **Proteksi API B2B Terpisah**: Buat ruleset terpisah untuk API Machine-to-Machine. Autentikasi menggunakan mTLS (Mutual TLS) dan kecualikan path tersebut dari rule Bot Management berbasis browser.
- [ ] **Karakteristik Rate Limiter Majemuk**: Hindari rate limit murni `ip.src`. Gunakan kombinasi: `ip.src` + `http.request.headers["authorization"]` atau `ip.src` + `http.request.cookies["session_id"]`.
- [ ] **Kompensasi Jendela Waktu (Sliding Window)**: Tentukan `period` yang realistis. Batas 60-120 detik lebih stabil dibandingkan window 10 detik yang rentan terhadap false positive saat burst transaksi normal.
- [ ] **Whitelisting Terverifikasi Statis**: Selalu cantumkan `not cf.bot_management.verified_bot` pada semua blocking rules yang berkaitan dengan L7 Rate Limiting dan Bot Protection.
- [ ] **Custom JSON Responses**: Untuk semua rate limit API, kembalikan body format JSON standar dengan atribut `Retry-After` header dan kode status HTTP 429 yang informatif bagi klien.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Task 1: Setup Terraform Manifest untuk Advanced Rate Limiting
Buat file `hands-on/m02/main.tf`:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.35.0"
    }
  }
}

provider "cloudflare" {
  # CLOUDFLARE_API_TOKEN dibaca otomatis dari environment variable
}

variable "zone_id" {
  type        = string
  description = "Zone ID Cloudflare domain target"
}

# Advanced Rate Limiting: Password Spraying & Brute Force Shield
resource "cloudflare_ruleset" "auth_rate_limiting" {
  zone_id     = var.zone_id
  name        = "Auth Brute Force Protection"
  description = "Proteksi endpoint /login menggunakan karakteristik komposit"
  kind        = "zone"
  phase       = "http_ratelimit"

  rules {
    action      = "block"
    description = "Limit Login attempts to 5 per minute per IP"
    expression  = <<-EOT
      (http.request.uri.path eq "/login" and 
       http.request.method eq "POST" and 
       not cf.bot_management.verified_bot)
    EOT

    ratelimit {
      characteristics = [
        "ip.src"
      ]
      period              = 60
      requests_per_period = 5
      mitigation_timeout = 300 # Block selama 5 menit jika melanggar

      counting_expression = "http.request.method eq \"POST\""
    }

    action_parameters {
      response {
        content_type = "application/json"
        content      = "{\"error\": \"TOO_MANY_LOGIN_ATTEMPTS\", \"status\": 429}"
        status_code  = 429
      }
    }
    enabled = true
  }
}
```

#### Task 2: Deployment via CLI
Eksekusi instruksi bash berikut:

```bash
cd hands-on/m02/

# Set token Cloudflare Anda
export CLOUDFLARE_API_TOKEN="secret-api-token-anda"
export TF_VAR_zone_id="your-cloudflare-zone-id"

# Inisialisasi dan terapkan infrastruktur
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

#### Task 3: Simulasi Penyerangan dan Verifikasi (Triggering Mitigation)
Uji apakah rate limit berfungsi dengan melakukan bash loop request ke endpoint:

```bash
# Kirim 7 request berturut-turut untuk memicu limit (Threshold = 5)
for i in {1..7}; do
  echo "Mengirim request ke-$i:"
  curl -s -i -X POST "https://subdomain.domainanda.com/login" \
    -H "Content-Type: application/json" \
    -d '{"user":"admin","pass":"secret"}' \
    | grep -E "HTTP/|error|cf-ray"
  sleep 1
done
```
*Ekspektasi Output*: Request 1 sampai 5 mengembalikan respon normal origin (atau 404/401 jika endpoint belum ada), request ke-6 dan ke-7 menghasilkan `HTTP/2 429` dengan payload JSON `{"error": "TOO_MANY_LOGIN_ATTEMPTS", "status": 429}`.

---

### 13. Exercise

#### Level: Easy
Buat WAF Custom Rule expression untuk memblokir semua request yang memiliki `cf.bot_management.score` di bawah 10 yang mengakses path `/admin/*`, namun pastikan verified bot tetap lolos jika terjadi proses crawling oleh mesin pencari.
- Tuliskan sintaks ekspresi WAF Ruleset.

#### Level: Medium
Rancang konfigurasi Cloudflare Rate Limiting yang menargetkan endpoint API transaksi `/api/v1/transfer`. 
- Kriteria:
  - Karakteristik counting: Berdasarkan HTTP Header `X-Device-Fingerprint`.
  - Ambang batas: Maksimal 10 request per 60 detik.
  - Aksi mitigasi: Managed Challenge (bukan drop/block) selama 120 detik.
- Tuliskan blok HCL resource Terraform `cloudflare_ruleset`.

#### Level: Hard
Terdapat skenario di mana ribuan bot terdistribusi melakukan scraping pada endpoint `/products/*`. Bot menggunakan dynamic IP dari residential subnet sehingga IP-based rate limiting tidak bekerja. Seluruh bot menggunakan TLS fingerprint JA4 yang sama: `t13d1517h2_5daec3516086_...`. Namun, sebagian browser pengguna lama (legitimate edge case) memiliki JA4 fingerprint yang sama persis.
- Rancang strategi arsitektur multi-layer (kombinasi ekspresi WAF, Bot Score, dan Cookie Injection) untuk membedakan scraper otomatis dengan browser manusia asli tersebut tanpa menyebabkan blocking permanen pada legitimate user.
- Tuliskan pseudocode/HCL ruleset untuk pipeline mitigasi ini.

---

### 14. Challenge

**Skenario**:
Perusahaan perbankan digital skala global menghadapi serangan DDoS Layer 7 masif tipe *Random URI Query Flood* dan *Distributed Token Invalidation Attack* yang menargetkan API Gateway (`api.bankdigital.com`). 

**Karakteristik Serangan**:
1. Trafik mencapai 500.000 RPS.
2. Penyerang mengeksploitasi endpoint `/oauth/v2/introspect` dengan menyuntikkan token acak, membebani database Redis sentral origin hingga kehabisan memory.
3. Penyerang menggunakan headless browser cluster nyata (Puppeteer/Playwright) yang mampu merender JavaScript, sehingga lolos dari Managed JS Challenge standar.
4. Nilai `cf.bot_management.score` berada di rentang abu-abu (rentang 35 - 50) karena sidik jari TLS dan perilaku browser terlihat otentik menyerupai Chrome asli.
5. Klien sah adalah kombinasi antara pengguna Web Browser (React SPA) dan Native Mobile App (iOS/Android).

**Tugas Arsitektur**:
Rancang dokumen arsitektur komprehensif yang mencakup:
1. Skema segregasi lalu lintas (Traffic Partitioning) antara Mobile Client vs Web Client pada Cloudflare Edge.
2. Strategi validasi cryptographic proof / attestation di Edge sebelum request diizinkan menyentuh origin.
3. Desain Advanced Rate Limiting multi-dimensi untuk mencegah kehabisan sumber daya Redis tanpa menolak pengguna login yang sah.
4. Skema integrasi Cloudflare Workers KV / Worker Rate Limiting Engine jika Ruleset Engine standar tidak mencukupi untuk mendeteksi anomali token invalidation flood.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Pada arsitektur internal Cloudflare, komponen mana yang bertugas mengeksekusi mitigasi serangan volumetrik L3/L4 langsung pada Linux kernel driver interface?**
   - A. Frontline Proxy
   - B. eBPF / XDP Driver Filter
   - C. Wirefilter Engine
   - D. Workers Runtime
   *Kunci*: B.

2. **Rentang skor yang dihasilkan oleh Cloudflare Enterprise Bot Management adalah...**
   - A. 0.0 hingga 1.0
   - B. 1 hingga 99
   - C. -100 hingga +100
   - D. 0 hingga 255
   *Kunci*: B.

3. **Apa arti skor `cf.bot_management.score` bernilai 1?**
   - A. Request dipastikan berasal dari browser manusia asli yang telah lolos validasi Turnstile.
   - B. Request terkonfirmasi sebagai bot otomatis berbahaya (malicious bot/automated attack).
   - C. Koneksi menggunakan protokol HTTP/1.0 usang.
   - D. Request berasal dari Googlebot atau Bingbot resmi.
   *Kunci*: B.

4. **Karakteristik TLS handshake apa saja yang digunakan untuk mengalkulasi JA4 Fingerprint?**
   - A. IP Address, User-Agent, dan Accept-Language.
   - B. Protokol TCP Window Size, IP TTL, dan MSS.
   - C. Protokol TLS version, Cipher Suites, Extensions, dan ALPN.
   - D. Isi HTTP Request Body dan Cookie payload.
   *Kunci*: C.

5. **Mengapa aturan blocking bot harus selalu mengecualikan `cf.bot_management.verified_bot`?**
   - A. Agar origin server tidak kehabisan CPU.
   - B. Mencegah search engine crawler resmi (Googlebot, Bingbot) terblokir yang dapat merusak indeks SEO situs.
   - C. Verified bot secara otomatis membayar biaya bandwidth Cloudflare.
   - D. Supaya rate limit counter tidak mengalami *race condition*.
   *Kunci*: B.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Apa perbedaan mendasar antara aksi mitigasi `Block` dan `Managed Challenge` pada Ruleset Engine?**
   - A. `Block` memutuskan koneksi pada L4 (TCP Reset), sedangkan `Managed Challenge` mengembalikan HTTP 500.
   - B. `Block` menghentikan request dengan status 403/429, sedangkan `Managed Challenge` menyajikan tantangan browser interaktif/non-interaktif untuk memverifikasi humanitas klien sebelum mengizinkan akses.
   - C. `Block` hanya berlaku untuk 1 menit, sedangkan `Managed Challenge` berlaku permanen.
   - D. `Managed Challenge` hanya dapat digunakan jika klien menggunakan koneksi HTTP/3.
   *Kunci*: B.

7. **Mengapa rate limiting murni berbasis `ip.src` sangat berisiko bagi endpoint transaksi B2C di Indonesia?**
   - A. Seluruh ISP di Indonesia memblokir protokol Cloudflare.
   - B. Penggunaan Carrier-Grade NAT (CGNAT) masif oleh ISP mobile menyebabkan ribuan pengguna seluler sah berbagi satu IP publik yang sama.
   - C. IP di Indonesia tidak didukung oleh database geolokasi Cloudflare.
   - D. Karakteristik `ip.src` membutuhkan lisensi Enterprise tambahan.
   *Kunci*: B.

8. **Manakah ekspresi Cloudflare Ruleset yang paling tepat untuk mendeteksi request API yang menggunakan token bearer namun dieksekusi oleh library bot Python standar?**
   - A. `http.request.uri.path contains "/api/" and http.user_agent contains "Python"`
   - B. `http.request.uri.path contains "/api/" and cf.bot_management.ja4 in {"t13d1516h2_8daaf6156415_a0f5a7b7a8d5"} and not cf.bot_management.verified_bot`
   - C. `http.request.method eq "GET" and ip.geoip.asnum eq 13335`
   - D. `cf.bot_management.score gt 90 and http.request.headers["authorization"] ne ""`
   *Kunci*: B. (Mendeteksi via JA4 TLS fingerprint jauh lebih akurat dan anti-tampering dibandingkan mengandalkan string header User-Agent).

9. **Pada algoritma Advanced Rate Limiting Cloudflare, apa fungsi dari parameter `mitigation_timeout`?**
   - A. Durasi waktu yang dibutuhkan server edge untuk mereset counter memori ke nol.
   - B. Lama waktu tindakan mitigasi (misal status 429 atau Block) tetap diberlakukan kepada klien setelah melampaui ambang batas request.
   - C. Waktu tunggu DNS time-to-live sebelum IP klien dihapus dari database.
   - D. Batas timeout koneksi socket TCP upstream ke origin server.
   *Kunci*: B.

10. **Bagaimana cara menangani mobile client native (iOS/Android) agar tidak terganggu oleh proteksi Anti-Bot saat mengakses REST API backend?**
    - A. Mengubah User-Agent mobile app menjadi persis string Google Chrome Desktop.
    - B. Menerapkan autentikasi mutual TLS (mTLS) atau implementasi Cloudflare Turnstile Native Mobile SDK / App Attestation untuk memvalidasi integritas aplikasi.
    - C. Membuka seluruh port firewall untuk subnet IP perangkat mobile.
    - D. Mematikan fitur WAF secara berkala setiap 5 menit.
    *Kunci*: B.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: Sebuah platform e-commerce menerapkan rate limit: *Maksimal 100 request per menit per `ip.src`*. Saat peluncuran promo produk, ribuan karyawan dari satu gedung kantor multinasional (menggunakan single corporate NAT IP) mengakses situs secara bersamaan. Seluruh kantor tersebut menerima HTTP 429 dalam hitungan detik.
    *Pertanyaan*: Konfigurasi karakteristik rate limit manakah yang harus diubah untuk menyelesaikan insiden ini tanpa menurunkan efektivitas mitigasi penyerang?
    - **Solusi & Analisis**: Karakteristik tunggal `ip.src` harus diganti menjadi kombinasi komposit: `ip.src` + `http.request.cookies["session_id"]` (untuk web terotentikasi) atau `ip.src` + `http.request.headers["x-client-device-id"]`. Dengan begitu, counter dihitung independen untuk setiap sesi pengguna individual di balik IP NAT yang sama.

12. **Skenario 2**: Log security mendapati adanya lonjakan traffic credential stuffing pada `/api/v1/auth`. Penyerang memutar jutaan IP proxy residential, masing-masing IP hanya memanggil endpoint 1 kali per jam (low-frequency). Bot Score menunjukkan angka bervariasi antara 20 dan 45. 
    *Pertanyaan*: Mengapa IP-based rate limiting gagal mendeteksi serangan ini, dan mekanisme apa pada Cloudflare Enterprise yang dapat memitigasi serangan ini secara efektif?
    - **Solusi & Analisis**: IP-based rate limiting gagal karena frekuensi serangan per IP berada jauh di bawah ambang batas deteksi (*distributed low-and-slow*). Solusinya adalah menerapkan *Global Rate Limiting / Behavioral Counting Expression* pada endpoint `/api/v1/auth`:
      1. Menghitung laju kegagalan HTTP status 401 yang dikembalikan origin.
      2. Menerapkan Advanced Rate Limiting dengan karakteristik non-IP, seperti `cf.bot_management.ja4` atau TLS cipher fingerprint gabungan.
      3. Mengharuskan eksekusi Managed Challenge (Cloudflare Turnstile Invisible) sebelum endpoint otentikasi diproses.

13. **Skenario 3**: Sebuah API Gateway melayani partner B2B dan pengguna publik. SRE mengaktifkan Custom WAF rule: `cf.bot_management.score lt 30 -> Action: Managed Challenge`. Sesaat kemudian, seluruh sistem pembayaran dari partner B2B terhenti dengan status error timeout atau connection reset.
    *Pertanyaan*: Analisis akar penyebab (*root cause*) masalah ini dan rancang solusi perbaikan ruleset WAF-nya!
    - **Solusi & Analisis**:
      - *Root Cause*: Script integrasi partner B2B (misal: backend daemon berbasis Python, Java, atau Go) berjalan otomatis (Machine-to-Machine) tanpa rendering engine browser. Model Bot Cloudflare secara tepat mengklasifikasikan request tersebut sebagai script/bot (score < 30). Karena aksinya `Managed Challenge`, Cloudflare merespons dengan halaman HTML challenge JavaScript, yang tidak dapat diproses oleh daemon partner, menyebabkan transaksi B2B terputus total.
      - *Solusi Perbaikan*: 
        Kecualikan trafik partner B2B menggunakan mTLS (Client Certificate Authentication), IP Whitelisting khusus korporat partner, atau validasi HMAC Signature header sebelum evaluasi Bot Management dilakukan:
        ```text
        (http.request.uri.path contains "/api/b2b/" and cf.tls_client_auth.cert_verified) 
        -> Action: Skip (Bypass Bot Management)
        ```

---

### 16. Summary

- **Layered Defense Architecture**: Keberhasilan Cloudflare menahan serangan skala multi-terabit didasarkan pada separasi mitigasi: L3/L4 volumetrik dimatikan pada boundary hardware via eBPF/XDP (`dosd` dan Gatekeeper), sementara L7 di-terminate dan dianalisis pada proxy engine (`Frontline`).
- **Modern Fingerprinting Beyond User-Agent**: User-Agent adalah artefak yang sangat mudah dipalsukan. Deteksi modern bergantung pada integritas kriptografis TLS Client Hello (JA3/JA4) dan anomali urutan HTTP/2 frame multiplexing.
- **Advanced Rate Limiting**: Beralih dari penghitungan berbasis IP mentah ke penghitungan berbasis karakteristik komposit (*multi-attribute characteristics*) yang memperhitungkan status otentikasi, session token, serta device fingerprint guna meminimalisir dampak buruk NAT traversal.
- **Bot Management Optimization**: Skor bot ($1 \le score \le 99$) bukan sakelar on/off biner. Strategi enterprise mengimplementasikan segmentasi bertingkat: *hard block* pada score ekstrem rendah, *managed challenge* pada rentang abu-abu, dan *bypass mTLS* untuk ekosistem integrasi mesin-ke-mesin (*M2M*).