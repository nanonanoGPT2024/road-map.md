# Modul 01: DDoS Mitigation, Advanced Rate Limiting, & Bot Management

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis dan mengonfigurasi arsitektur mitigasi serangan Distributed Denial of Service (DDoS) pada Layer 3, Layer 4, dan Layer 7 di edge network Cloudflare.
- Memahami implementasi dan mekanisme Anycast BGP routing dalam menyerap serta memecah volume serangan terdistribusi secara global tanpa titik kegagalan tunggal (*single point of failure*).
- Mendesain solusi proteksi seluruh infrastruktur on-premises/hybrid IP transit menggunakan Cloudflare Magic Transit (GRE tunnel, BGP prefix hijacking protection, dan autonomous mitigation).
- Mengonfigurasi Advanced Rate Limiting berbasis kriteria komposit (*counting expressions*, *fingerprinting*, status code responses) menggunakan Cloudflare Rulesets Engine.
- Mengimplementasikan Machine Learning Bot Management dan Super Bot Fight Mode (SBFM) dengan parameter Bot Score (1–99) serta integrasi mitigasi interaktif modern menggunakan Cloudflare Turnstile tanpa merusak *user experience* (UX).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Jaringan Komputer & Protokol**: Model OSI/TCP-IP, mekanisme TCP 3-way handshake, UDP stateless delivery, ICMP, DNS resolution flow, dan protokol HTTP/1.1, HTTP/2, serta HTTP/3 (QUIC).
- **Routing & Autonomous Systems**: Konsep Border Gateway Protocol (BGP), Autonomous System Number (ASN), Anycast vs Unicast routing, BGP communities, prefix advertisement (/24 untuk IPv4, /48 untuk IPv6), dan enkapsulasi Generic Routing Encapsulation (GRE) / IPsec.
- **TLS/Cryptographic Handshake**: TLS Client Hello, JA3/JA4 fingerprinting, cipher suites, dan HTTP headers (`User-Agent`, `CF-Connecting-IP`, `X-Forwarded-For`).
- **Infrastruktur Dasar Cloudflare**: DNS Management, Proxy Status (Proxied vs DNS-Only), dan dasar-dasar Cloudflare WAF/Ruleset Engine.

---

## 3. Concept
DDoS Mitigation, Advanced Rate Limiting, dan Bot Management di Cloudflare beroperasi di atas prinsip **Edge-First Autonomous Defense**. Berbeda dengan pendekatan arsitektur *scrubbing center* tradisional—di mana lalu lintas jaringan harus dialihkan secara paksa (*diverted*) melalui rute berputar (*hairpinning*) ke lokasi pembersihan terpusat saat terdeteksi anomali—Cloudflare memanfaatkan jaringan global Anycast di ratusan data center (Point of Presence/PoP).

Pada arsitektur Anycast, satu alamat IP publik diiklankan (advertised) secara bersamaan dari seluruh PoP di seluruh dunia. Ketika serangan DDoS L3/L4 diluncurkan dari jutaan botnet, paket-paket serangan tersebut diserap (*absorbed*) dan dimitigasi langsung di PoP Cloudflare terdekat secara geografis dan topologis.

Mitigasi terbagi ke dalam tiga domain utama:
1. **L3/L4 Infrastructure Protection (Gatebot & dosd)**: Menghentikan serangan volumetrik (SYN flood, UDP amplification, ACK flood) langsung pada kernel/NIC level menggunakan teknologi modern seperti eBPF/XDP di edge, baik untuk lalu lintas HTTP terproksi maupun IP transit privat (Magic Transit).
2. **L7 HTTP Application Protection**: Mengidentifikasi serangan *HTTP request flood* (GET/POST floods, cache-busting, resource exhaustion) menggunakan analisis statistik laju permintaan dan *fingerprint* anomali protokol.
3. **Bot Management & Advanced Heuristics**: Memisahkan lalu lintas otomatis non-manusia (*automated traffic*) dari pengguna sah menggunakan Machine Learning scoring (1-99), integrasi *browser fingerprinting*, verifikasi *behavioral telemetry*, serta validasi non-intrusif berbasis Cloudflare Turnstile.

---

## 4. Why
Kebutuhan mitigasi DDoS modern dan proteksi bot berbasis edge didorong oleh perubahan lanskap ancaman siber:
- **Volume Serangan Multi-Terabit**: Serangan DDoS L3/L4 modern secara rutin melampaui 1 hingga 3+ Tbps menggunakan amplifikasi DNS/NTP/CLDAP atau botnet berbasis IoT (seperti Mirai dan variannya). Pusat data privat atau *appliance hardware* on-premises tidak memiliki kapasitas uplink untuk menerima beban sebesar ini sebelum pipa jaringan ISP jenuh total (*pipe saturation*).
- **Asymmetric L7 Attacks**: Serangan L7 seperti HTTP/2 Rapid Reset (CVE-2023-44487) atau floods query database yang kompleks membutuhkan bandwidth relatif kecil di sisi penyerang, tetapi menghabiskan CPU dan connection pool di sisi origin server secara eksponensial.
- **Sophisticated Automated Bots**: Bot generasi baru (Bot Generasi 4/5) mampu mengeksekusi JavaScript, meniru browser nyata (*headless browsers*), merotasi jutaan residential proxy, dan memalsukan identitas header. Menangani serangan ini dengan *IP blocklisting* statis atau WAF rules berbasis regex menghasilkan tingkat *false positive* yang tinggi dan kegagalan mitigasi.
- **Latency & Scrubbing Penalty**: Pendekatan lama menggunakan rute *On-demand Scrubbing Center* menambahkan *round-trip time* (RTT) ratusan milidetik dan membutuhkan intervensi manual (BGP swing). Anycast Cloudflare menjaga latensi tetap rendah karena mitigasi berjalan *inline* secara terus menerus (*always-on*).

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Mitigasi L3/L4 via Anycast BGP dan dosd/Gatebot
Sistem mitigasi Cloudflare di Layer 3 dan Layer 4 beroperasi menggunakan dua komponen inti utama:

```
[ Incoming Packets ]
         │
         ▼
[ NIC Layer (RX Ring) ]
         │
         ▼
[ eBPF / XDP Filter (dosd: L4 Software Daemon) ]
    ├── Normal Traffic  ──> [ Linux Kernel / Netfilter ] ──> [ NGINX/FL/Pingora Proxy ]
    └── Attack Traffic  ──> [ XDP_DROP (Zero CPU overhead) ]
```

1. **Gatebot**: Sistem analisis data terdistribusi terpusat yang memproses sampel sFlow/NetFlow dari seluruh edge server. Gatebot mengidentifikasi pola anomali global dan mendistribusikan aturan mitigasi dalam hitungan detik.
2. **dosd (Denial of Service Daemon)**: Daemon lokal yang berjalan di setiap server di setiap PoP. `dosd` memantau antrean paket yang masuk secara lokal tanpa membutuhkan koordinasi global. Jika serangan melonjak melampaui ambang batas tertentu:
   - `dosd` menghasilkan program eBPF (Extended Berkeley Packet Filter) bytecode secara dinamis.
   - Program di-attach langsung ke layer XDP (eXpress Data Path) pada *driver network interface card* (NIC).
   - Paket serangan di-drop menggunakan instruksi `XDP_DROP` sebelum kernel Linux mengalokasikan struktur `sk_buff` (socket buffer). Pendekatan ini memungkinkan sebuah edge server membuang puluhan juta paket per detik (Mpps) dengan konsumsi utilitas CPU yang minimal.

### 5.2 Magic Transit: Proteksi IP Transit dan On-Premises
Magic Transit memperluas proteksi DDoS Cloudflare ke seluruh subnet IP milik organisasi (BYOIP - Bring Your Own IP):
- **BGP Announcement**: Cloudflare mengiklankan subnet IP organisasi (minimal prefix `/24` untuk IPv4 dan `/48` untuk IPv6) dari seluruh edge PoP menggunakan Anycast BGP.
- **Ingress Traffic Flow**: Seluruh lalu lintas internet yang ditujukan ke subnet IP publik milik pelanggan akan tiba di edge Cloudflare terdekat.
- **Inline Scrubbing**: Paket dianalisis dan dibersihkan dari serangan L3/L4 secara otomatis menggunakan aturan proteksi `dosd` dan Gatebot.
- **Egress encapsulation via GRE/IPsec**: Paket bersih (*clean traffic*) dibungkus ke dalam terowongan GRE (Generic Routing Encapsulation) atau IPsec tunnel yang terhubung langsung ke router edge data center milik pelanggan.
- **Direct Server Return (DSR)**: Lalu lintas keluar (*outbound/egress*) dari data center pelanggan dapat langsung dikirim ke internet via ISP lokal (asymmetric routing) tanpa harus kembali melewati Cloudflare, sehingga menghemat biaya egress transit dan meminimalkan latensi.

### 5.3 Mitigasi L7 HTTP Flood & Dynamic Engine
Di Layer 7, serangan berbentuk request HTTP/HTTPS valid yang ditujukan untuk melumpuhkan kapasitas pemrosesan aplikasi (compute, memory, database connection pool):
- **HTTP DDoS Protection Engine**: Bekerja secara otomatis di atas sistem Ruleset Engine. Engine ini menganalisis karakteristik HTTP request (path, method, headers, TLS fingerprints, origin response times) secara real-time.
- Serangan dideteksi menggunakan pemodelan deviasi statistik dari *baseline* normal traffic domain yang bersangkutan.
- Tindakan mitigasi dieksekusi secara otonom: `Block`, `Managed Challenge`, `Interactive Challenge`, atau `DDoS Dynamic Mitigation` yang menyesuaikan sensitivitas mitigasi berdasarkan laju keparahan serangan.

### 5.4 Machine Learning Bot Management & Bot Score (1–99)
Cloudflare Bot Management mengklasifikasikan setiap HTTP request dengan sebuah atribut numerik bernama `cf.bot_management.score` yang bernilai antara **1 hingga 99**:

| Rentang Bot Score | Klasifikasi | Karakteristik Lalu Lintas | Tindakan Tipikal |
| :--- | :--- | :--- | :--- |
| **1 – 29** | Automated (Definite Bot) | Dikirim oleh script otomatis, headless browser, scraping tools, atau botnet. Pola navigasi tidak manusiawi, kegagalan cryptographic challenge, fingerprint signature bot. | `Block` / `Managed Challenge` |
| **30 – 99** | Human / Likely Human | Interaksi dari browser standar dengan pola render normal, mouse movement telemetry valid, TLS handshake konsisten dengan native OS/browser client. | `Allow` / `Skip Rate Limit` |

Fitur penentu Bot Score:
- **Machine Learning Engine**: Model dilatih menggunakan ratusan miliar request per hari untuk mengenali korelasi antara header, anomali behavior, dan telemetry client.
- **Heuristic Engine**: Pendekatan berbasis aturan statis dan pola heuristik untuk mendeteksi tools penyerang umum (Curl default, Selenium, Puppeteer, Scrapy).
- **Behavioral Analysis**: Memonitor riwayat interaksi client sepanjang sesi, seperti waktu jeda antar-request (*dwell time*), rute traversal halaman, dan anomali urutan request.
- **JA3 / JA4 Fingerprinting**: Menganalisis parameter dalam TLS Client Hello (Cipher Suites, Extensions, Elliptic Curves). Browser asli seperti Chrome pada macOS memiliki JA4 fingerprint yang berbeda secara drastis dibanding script Python Requests atau bot Go HTTP, meskipun header `User-Agent` dipalsukan menjadi sama persis.

### 5.5 Super Bot Fight Mode (SBFM)
Dirancang untuk paket Pro dan Business, SBFM menyediakan antarmuka proteksi bot cepat dengan klasifikasi biner dan bertingkat:
- **Definitely Automated Traffic**: Ditangani secara independen dengan aksi `Block` atau `Managed Challenge`.
- **Likely Automated Traffic**: Ditujukan untuk bot tingkat menengah; dapat diatur ke `Challenge` atau `Allow`.
- **Verified Bots**: Mengizinkan bot yang sah (seperti Googlebot, Bingbot, monitoring agent resmi) melalui verifikasi Reverse DNS dan ASN list Cloudflare, sehingga SEO dan integrasi API esensial tidak terganggu.

### 5.6 Cloudflare Turnstile: Alternatif Modern CAPTCHA
Turnstile adalah pengganti CAPTCHA tradisional (seperti reCAPTCHA atau hCaptcha) yang dirancang untuk menjaga privasi dan mengeliminasi friksi interaksi visual:
- **Zero-Friction / Non-Interactive**: Sebagian besar pengguna tidak pernah melihat teka-teki visual (*puzzle*). Validasi terjadi di balik layar menggunakan tantangan kriptografis ringan (*proof-of-work* berbasis WebAssembly), validasi status sandbox browser, dan verifikasi Private State Tokens (PST) via Apple/Google hardware ecosystem.
- **Pre-Clearance Support**: Turnstile dapat diintegrasikan dengan Cloudflare WAF/Bot Management. Jika client berhasil memvalidasi widget Turnstile pada form login, Cloudflare mengeluarkan Clearance Cookie (`cf_clearance`), memungkinkan request HTTP POST berikutnya melewati WAF rule tanpa hambatan tantangan berulang.

### 5.7 Advanced Rate Limiting
Advanced Rate Limiting pada Cloudflare beroperasi dengan parameter granular:
- **Counting Expression**: Kriteria request yang akan dihitung lajunya (misal: hanya hitung request ke URI `/api/v1/checkout` dengan method `POST`).
- **Characteristics**: Dimensi identitas penghitungan (*rate limit key*). Tidak terbatas pada alamat IP (`ip.src`), tetapi dapat dikombinasikan dengan:
  - Header tertentu (misal: `http.request.headers["x-api-key"]`)
  - Nilai Session/JWT claim
  - Cookie (misal: `http.request.cookies["session_id"]`)
  - IP + User-Agent composite
  - Parameter URL query
- **Mitigation Action**: Tindakan saat threshold terlewati (`Block`, `Managed Challenge`, `Log`, atau response custom JSON payload).
- **Response Headers / Status Code Matching**: Fitur unik untuk menghitung rate limit berdasarkan respons origin server. Contoh: Jika IP melakukan request ke `/api/login` dan origin merespons dengan status code `HTTP 401`, hitung rate limit untuk *credential stuffing mitigation*.

---

## 6. How
Implementasi proteksi DDoS dan Bot Management mengikuti alur strategi berlapis:

```
[ External Traffic ]
        │
        ▼
[ Layer 3/4 Mitigation: Anycast BGP + dosd/Gatebot (Magic Transit / IP Proxy) ]
        │
        ▼
[ TLS Handshake Inspection: JA3/JA4 Fingerprint & Protocol Checks ]
        │
        ▼
[ Bot Management Evaluation: ML Engine Assigns cf.bot_management.score ]
        │
        ▼
[ Cloudflare WAF & Advanced Rate Limiting Evaluation ]
        ├── Bot Score <= 29? ──> Block / Managed Challenge
        ├── Rate Limit Exceeded? ──> 429 Too Many Requests / Challenge
        └── Valid Traffic? ──> Decrypt & Inspect L7 Rules
                                       │
                                       ▼
                             [ Origin Web Server ]
```

1. **Aktivasi Edge Proxy & TLS Strict**: Arahkan rekaman DNS ke Cloudflare (Orange Cloud) dan aktifkan mode Full (Strict) SSL/TLS untuk memastikan validasi handshake berjalan di edge.
2. **Definisikan Bot Management Policy**:
   - Berikan izin (*bypass*) untuk *Verified Bots* (`cf.bot_management.verified_bot`).
   - Terapkan aksi `Block` untuk Bot Score sangat rendah (`cf.bot_management.score < 10`) pada endpoint sensitif.
   - Terapkan aksi `Managed Challenge` untuk Bot Score menengah-rendah (`cf.bot_management.score >= 10 and cf.bot_management.score <= 29`).
3. **Bangun Advanced Rate Limiting Rulesets**:
   - Bedakan antara API authenticated (`x-api-key`), endpoint autentikasi publik (`/login`), dan aset web biasa.
   - Konfigurasikan tracking berbasis kombinasi token/cookie untuk mencegah bypass via IP rotation (residential proxies).
4. **Implementasikan Turnstile pada Frontend Client**:
   - Sisipkan JavaScript Turnstile ke dalam formulir login/registrasi/transaksi.
   - Lakukan verifikasi server-side token Turnstile sebelum memproses logika bisnis di origin application server.

---

## 7. Analogy
Bayangkan sebuah bandara internasional tersibuk di dunia:
- **Anycast BGP**: Alih-alih seluruh penumpang dari seluruh dunia harus terbang ke satu bandara pusat di Jakarta (Unicast), terdapat 300 kantor imigrasi lokal di setiap kota asal di dunia. Penumpang masuk ke kantor imigrasi terdekat di kotanya masing-masing.
- **dosd & eBPF/XDP (L3/L4)**: Penjaga gerbang perimeter luar yang memeriksa tiket fisik. Jika sekelompok orang membawa senjata atau gerobak liar tanpa tiket (UDP/SYN flood), mereka langsung ditolak di gerbang parkiran luar tanpa pernah diizinkan masuk ke lobi gedung terminal (kernel memory/CPU origin aman).
- **Magic Transit**: Jalur kereta bawah tanah khusus yang membawa kargo yang sudah diperiksa secara ketat dari pos imigrasi bandara langsung ke gudang privat perusahaan Anda melalui terowongan terisolasi (GRE Tunnel).
- **Bot Score & JA4**: Profiler intelijen di lobi bandara. Meskipun seseorang mengenakan seragam pilot resmi (*User-Agent spoofing*), sistem mengenali cara jalannya yang aneh, respons pupil matanya, dan gaya bicaranya (TLS handshake + telemetry) yang cocok dengan karakteristik robot penyusup (Bot Score = 05).
- **Turnstile**: Pintu gerbang otomatis yang melakukan pemindaian biometrik cepat tanpa mengharuskan Anda berhenti untuk memecahkan puzzle matematika yang membingungkan seperti CAPTCHA konvensional.
- **Advanced Rate Limiting**: Batasan pengambilan bagasi: satu orang hanya diizinkan mengambil maksimal 3 koper per 5 menit. Jika ada yang mencoba mengambil 50 koper sekaligus dengan kartu identitas yang sama, orang tersebut langsung diarahkan ke ruang interogasi (*Managed Challenge/Block*).

---

## 8. Diagram (ASCII)

```
                 ========================================================
                               CLOUDFLARE ANYCAST EDGE (POP)
                 ========================================================
                                           │
                                    [ Global Internet ]
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                             │
             [ L3/L4 Flood ]                                [ L7 Flood ]
             (SYN, UDP, ICMP)                            (HTTP GET/POST Flood)
                    │                                             │
                    ▼                                             ▼
          ┌────────────────────┐                        ┌───────────────────┐
          │  eBPF / XDP Engine │                        │  HTTP DDoS Engine │
          │   (dosd daemon)    │                        │  (Traffic Floods) │
          └─────────┬──────────┘                        └─────────┬─────────┘
                    │                                             │
         [ Action: XDP_DROP ]                                     ▼
      (Zero CPU Allocation Drop)                        ┌───────────────────┐
                    │                                   │ Bot Mgmt Engine   │
                    x (Traffic Dead)                    │ (ML Score: 1-99)  │
                                                        └─────────┬─────────┘
                                                                  │
                                            ┌─────────────────────┴─────────────────────┐
                                            │                                           │
                                    Score: 1 - 29                               Score: 30 - 99
                                  (Automated / Bot)                            (Likely Human)
                                            │                                           │
                                            ▼                                           ▼
                                 ┌─────────────────────┐                     ┌─────────────────────┐
                                 │ Managed Challenge / │                     │ Advanced Rate Limit │
                                 │      Block          │                     │      Engine         │
                                 └─────────────────────┘                     └──────────┬──────────┘
                                                                                        │
                                                                           ┌────────────┴────────────┐
                                                                     Within Quota              Exceeded Quota
                                                                           │                         │
                                                                           ▼                         ▼
                                                                 [ GRE / TLS Proxy ]       [ Action: HTTP 429 / ]
                                                                           │               [ Managed Challenge  ]
                                                                           ▼
                                                                  ┌─────────────────┐
                                                                  │  ORIGIN SERVER  │
                                                                  │ (Clean Traffic) │
                                                                  └─────────────────┘
```

---

## 9. Simple Example
Mencegah serangan brute-force atau credential stuffing sederhana pada path `/login` menggunakan antarmuka Cloudflare WAF Expression Rules:

```text
Target: Menantang semua automated bot yang mencoba mengakses path login
Expression:
(http.request.uri.path eq "/login" and cf.bot_management.score lt 30)

Action: Managed Challenge
```

Ekspresi di atas mengevaluasi setiap request ke endpoint `/login`. Jika `cf.bot_management.score` berada di bawah nilai 30 (terdeteksi sebagai bot otomatis oleh machine learning Cloudflare), Cloudflare akan secara otomatis menampilkan Managed Challenge (Turnstile background validation atau interactive check) tanpa membebani origin server Anda.

---

## 10. Practical Example (Konfigurasi CLI / Terraform)

Berikut konfigurasi infrastruktur berbasis kode (IaC) menggunakan Terraform Cloudflare Provider (v4.x) untuk mengimplementasikan:
1. Advanced Rate Limiting pada endpoint API login berdasarkan IP dan respons origin (status 401).
2. Bot Management WAF Ruleset untuk menolak bot jahat pada path sensitif.
3. Konfigurasi Turnstile Widget.

```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.35.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "The Cloudflare Zone ID"
}

variable "account_id" {
  type        = string
  description = "The Cloudflare Account ID"
}

# 1. Konfigurasi Cloudflare Turnstile Widget
resource "cloudflare_turnstile_widget" "login_challenge" {
  account_id     = var.account_id
  name           = "Production Login Turnstile"
  mode           = "managed"
  domains        = ["example.com"]
  region         = "world"
  bot_fight_mode = true
}

# 2. Advanced Rate Limiting Rule: Mitigasi Brute Force (Origin Error 401 Matching)
resource "cloudflare_ruleset" "rate_limiting_ruleset" {
  zone_id     = var.zone_id
  name        = "Enterprise Rate Limiting Ruleset"
  description = "Rate limiting against credential brute force and abuse"
  kind        = "zone"
  phase       = "http_ratelimit"

  rules {
    action      = "block"
    description = "Limit failed login attempts per IP based on 401 responses"
    expression  = "(http.request.uri.path eq \"/api/v1/auth/login\" and http.request.method eq \"POST\")"

    ratelimit {
      characteristics = [
        "cf.unique_visitor_id"
      ]
      period              = 60
      requests_per_period = 5
      mitigation_timeout  = 900 # Blokir selama 15 menit jika gagal 5x berturut-turut

      counting_expression = "(http.response.code eq 401)"
    }
  }

  rules {
    action      = "managed_challenge"
    description = "Rate limit standard API access by API Key header"
    expression  = "(http.request.uri.path.names[0] eq \"api\" and http.request.headers[\"x-api-key\"][0] ne \"\")"

    ratelimit {
      characteristics = [
        "http.request.headers[\"x-api-key\"]"
      ]
      period              = 60
      requests_per_period = 600 # Maks 600 request/menit per API key
      mitigation_timeout  = 60
    }
  }
}

# 3. Machine Learning Bot Management Ruleset
resource "cloudflare_ruleset" "bot_management_waf" {
  zone_id     = var.zone_id
  name        = "Bot Management Policy Ruleset"
  description = "Block or challenge traffic based on Cloudflare Bot Score"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  # Rule A: Allow verified search engine bots (Google, Bing, dll.)
  rules {
    action      = "skip"
    description = "Allow Verified Search Engine and Monitoring Bots"
    expression  = "(cf.bot_management.verified_bot)"
    
    logging {
      status = "enabled"
    }

    action_parameters {
      ruleset = "current"
    }
  }

  # Rule B: Drop Definitely Automated Traffic (Score 1-9) to checkout/payment
  rules {
    action      = "block"
    description = "Drop definitive malicious bots from payment routes"
    expression  = "(http.request.uri.path contains \"/checkout\" and cf.bot_management.score lt 10)"
  }

  # Rule C: Challenge Suspected Bots (Score 10-29) across entire application
  rules {
    action      = "managed_challenge"
    description = "Challenge likely automated bots accessing dynamic endpoints"
    expression  = "(cf.bot_management.score ge 10 and cf.bot_management.score le 29 and not http.request.uri.path contains \"/static/\")"
  }
}

output "turnstile_site_key" {
  value       = cloudflare_turnstile_widget.login_challenge.id
  description = "Turnstile Client-Side Sitekey"
}
```

---

## 11. Real World Example
Sebuah platform E-Commerce berskala nasional mengadakan *Flash Sale* smartphone pada pukul 00:00 WIB.
- **Pola Serangan**:
  - Penyerang meluncurkan botnet scraper terdistribusi (~250.000 IP perumahan/residential proxy) untuk memborong inventaris (*inventory hoarding*) dalam 3 detik pertama.
  - Secara paralel, penyerang mengirimkan UDP amplification flood sebesar 800 Gbps ke IP origin publik aplikasi untuk mendistorsi tim SRE (*distraction attack*).
- **Mitigasi Cloudflare**:
  1. Serangan 800 Gbps UDP diserap secara penuh di level edge Anycast global menggunakan `dosd` via instruksi `XDP_DROP` tanpa sedikit pun membebani bandwidth origin server.
  2. Edge network mengevaluasi request L7 ke endpoint `/api/order/submit`. Meskipun ribuan request berasal dari IP unik yang berbeda (residential proxies), Cloudflare Bot Management mendeteksi pola TLS Fingerprint (JA4) yang seragam dan tidak adanya telemetry interaksi mouse/touch, memberikan Bot Score berkisar antara `01` hingga `08`.
  3. Ruleset mengeksekusi aksi `Block` secara instan pada seluruh request dengan `cf.bot_management.score < 10` pada endpoint `/api/order/submit`.
  4. Pengguna manusia yang sah menyelesaikan verifikasi Cloudflare Turnstile transparan di aplikasi frontend, menerima `cf_clearance`, dan transaksi mereka diproses secara lancar tanpa degradasi performa database origin.

---

## 12. Trade-offs
Memilih tingkat proteksi DDoS, Rate Limiting, dan Bot Management yang agresif menghadirkan trade-off rekayasa:

| Pilihan Arsitektur | Keuntungan | Konsekuensi / Risiko (*Drawback*) |
| :--- | :--- | :--- |
| **Agresif Bot Mitigation (`Score < 30 -> Block`)** | Mencegah hampir 100% web scraping, credential stuffing, dan scalping bots. | Risiko *False Positive* terhadap integrasi B2B API klien lama atau aplikasi mobile kustom dengan engine HTTP non-standar. |
| **Origin Response Rate Limiting (Matching Status 401)** | Menghentikan *distributed brute force* meskipun IP penyerang dirotasi secara acak. | Mengharuskan edge menyimpan state status koneksi origin, menambahkan overhead internal buffering jika session rate sangat tinggi. |
| **Penerapan Turnstile Managed Mode** | Mengeliminasi interaksi puzzle yang menjengkelkan bagi 99% pengguna manusia asli. | Menambahkan dependency JavaScript pihak ketiga pada aplikasi frontend; kegagalan network ke domain Turnstile dapat memblokir submit form. |
| **Magic Transit (BGP Anycast Subnet)** | Mengamankan seluruh infrastruktur on-premise (termasuk email, VPN, database port) dari L3/L4 DDoS. | Kompleksitas pengelolaan BGP peering, MTU clamping issues (karena overhead 24 bytes header GRE), dan biaya komitmen enterprise yang tinggi. |

---

## 13. When To Use
Gunakan strategi mitigasi ini pada kondisi berikut:
- **L3/L4 Anycast / Magic Transit**:
  - Organisasi Anda memiliki subnet IP publik sendiri (minimal IPv4 `/24`) dan mengoperasikan data center on-premise atau private cloud yang rentan terhadap saturasi bandwidth uplink.
  - Infrastruktur Anda menjalankan protokol non-HTTP (VoIP, DNS internal, game server TCP/UDP, Mail Server).
- **L7 Bot Management & Score (1–99)**:
  - Layanan Anda rentan terhadap *credential stuffing*, *ticket scalping*, *price scraping*, dan *account takeover*.
  - Anda memiliki aplikasi publik yang menggunakan Single Page Application (React, Vue) atau mobile apps dengan exposure API luas.
- **Advanced Rate Limiting**:
  - Melindungi endpoint komputasi mahal seperti enkripsi password (`/bcrypt`), ekspor PDF/laporan, proses checkout, dan *SMS OTP dispatching* untuk mencegah financial draining (*SMS pumping fraud*).

---

## 14. When NOT To Use
Hindari atau batasi konfigurasi ini jika:
- **API M2M (Machine-to-Machine) Murni**:
  - Endpoint komunikasi antar-backend server tanpa keterlibatan browser manusia. Mengaktifkan *Bot Score challenge* atau Turnstile di sini akan merusak seluruh integrasi, karena backend worker (misal: microservice via curl/gRPC) akan selalu terdeteksi dengan Bot Score rendah. Solusi: Gunakan **Mutual TLS (mTLS)** atau API Shield Client Certificates.
- **Aplikasi Tanpa JavaScript**:
  - Klien pengguna menggunakan terminal (CLI tools seperti `curl`, `wget`) atau browser minimalis tanpa dukungan JavaScript/WebAssembly. Turnstile dan Managed Challenge tidak dapat diselesaikan pada lingkungan ini.
- **Prefix Subnet Lebih Kecil dari `/24`**:
  - Magic Transit tidak dapat digunakan jika Anda tidak memiliki prefix IP mandiri atau prefix Anda lebih spesifik dari `/24` untuk IPv4 (karena standar BGP internet publik melarang propagasi prefix `/25` ke bawah).

---

## 15. Common Mistakes
1. **Mengabaikan Path Bypassing pada Caching**:
   - Menyetel *Cache Rule* menjadi *Cache Everything* pada path API yang dilindungi Rate Limiting. Jika Cloudflare menyajikan response dari cache edge, counting expression untuk rate limiting origin response code (seperti 401) tidak akan pernah terevaluasi.
2. **Rate Limiting Hanya Berbasis Alamat IP (`ip.src`)**:
   - Di era modern, penyerang memanfaatkan botnet dengan ratusan ribu IP residensial (*rotating residential proxies*). Membatasi 10 request/menit per IP tidak berguna jika botnet mengirim 1 request per IP dari 100.000 IP berbeda. Karakteristik rate limit harus dikombinasikan dengan session cookie, JWT token, atau fingerprint.
3. **Konfigurasi MTU yang Salah pada Magic Transit GRE Tunnel**:
   - Standar internet MTU adalah 1500 bytes. Header GRE membutuhkan 24 bytes. Jika router edge on-premise tidak mengonfigurasi TCP MSS Clamping ke 1436 bytes (1500 - 20 IPv4 header - 20 TCP header - 24 GRE header), paket data berukuran besar akan mengalami fragmentasi (*packet drops*) yang menyebabkan koneksi macet (*hanging connections*).
4. **Memblokir Verified Bots Tanpa Pengecualian**:
   - Menerapkan aturan WAF: `cf.bot_management.score < 30 -> Block` tanpa menyertakan `and not cf.bot_management.verified_bot`. Akibatnya, Googlebot, Bingbot, dan crawler SEO resmi diblokir secara permanen dari website Anda, menghancurkan ranking pencarian.

---

## 16. Best Practices
1. **Gunakan Stratifikasi Bot Response**:
   - `cf.bot_management.score < 10`: **Block** (Bot primitif / tools otomatis murni).
   - `cf.bot_management.score >= 10 and cf.bot_management.score < 30`: **Managed Challenge** (Tantang bot yang mencurigakan tanpa mengganggu false-positive).
   - `cf.bot_management.verified_bot`: **Skip / Allow** (Beri jalan prioritas mesin pencari).
2. **Implementasikan Composite Rate Limiting**:
   - Gabungkan atribut IP dengan header atau session identifier:
     `characteristics = ["ip.src", "http.request.headers[\"authorization\"]"]`
3. **Lindungi Origin IP Asli (Origin IP Cloaking)**:
   - Pastikan firewall di level origin server (AWS Security Group, iptables) HANYA menerima koneksi ingress dari daftar IP resmi Cloudflare (dapat dilihat via API Cloudflare IP ranges). Mengaktifkan proteksi DDoS di Cloudflare tidak berguna jika penyerang dapat langsung menyerang IP publik origin server Anda (*bypassing the edge*).
4. **Terapkan Pre-Clearance Tokens dengan Turnstile**:
   - Saat menggunakan Turnstile pada form SPA (Single Page Application), hubungkan widget dengan session pre-clearance token Cloudflare agar transaksi API internal berikutnya otomatis terbebas dari tantangan WAF sekunder.

---

## 17. Troubleshooting

### Problem 1: Request dari bot scraper lolos mitigasi dengan status HTTP 200
- **Akar Masalah**: Domain belum mengaktifkan proxy Cloudflare (masih status *DNS-Only / Grey Cloud*) atau penyerang mengetahui alamat IP asli origin server dan menembak langsung tanpa melewati edge Cloudflare.
- **Diagnostik**:
  1. Jalankan `dig +short domain.com`. Jika IP yang keluar bukan milik Cloudflare (IP range Cloudflare: misal 104.16.x.x, 172.64.x.x), maka proxy tidak aktif.
  2. Periksa log web server origin. Cek apakah IP pengirim request adalah IP Cloudflare atau IP penyerang langsung.
- **Solusi**: Aktifkan status Proxied (Orange Cloud) pada DNS. Pasang firewall di origin server untuk memblokir seluruh lalu lintas kecuali dari CIDR IP resmi Cloudflare.

### Problem 2: Pengguna asli mengeluhkan perulangan tantangan CAPTCHA tanpa henti (*Challenge Loop*)
- **Akar Masalah**: Cookie domain `cf_clearance` terblokir oleh browser client (misal karena privacy browser extension atau iframe cross-site cookie restriction), atau reverse proxy internal menghapus header `Cookie` sebelum dievaluasi.
- **Diagnostik**: Periksa respons header pada browser Network tab. Amati apakah cookie `cf_clearance` diterima pada header `Set-Cookie` dan dikirimkan kembali pada HTTP request berikutnya.
- **Solusi**: Pastikan SameSite dan domain configuration untuk cookie aplikasi tidak menimpa cookie edge Cloudflare. Pastikan endpoint Turnstile disajikan dari apex domain atau subdomain yang sama dengan aplikasi.

### Problem 3: Throughput paket Magic Transit turun drastis dan sesi SSH/TLS on-premise macet (*freeze*)
- **Akar Masalah**: Terjadi *Path MTU Discovery (PMTUD) Blackhole* akibat enkapsulasi GRE tunnel memotong ukuran paket melebihi batas MTU interface router on-premise tanpa MSS Clamping.
- **Diagnostik**: Jalankan pengujian ping dengan larangan fragmentasi paket dari host lokal melewati tunnel:
  `ping -M do -s 1472 <destination-ip>`
  Jika ping gagal atau *packet loss* terjadi saat ukuran payload dinaikkan, PMTUD terblokir.
- **Solusi**: Konfigurasi TCP MSS Clamping pada interface GRE router pelanggan:
  `ip tcp adjust-mss 1436`

---

## 18. Exercise
Selesaikan skenario konfigurasi berikut secara mandiri:
1. Sebuah endpoint API kritis `/api/v2/reset-password` mengalami serangan *SMS OTP pumping fraud* dari botnet terdistribusi.
2. Tuliskan ekspresi WAF Custom Rule yang memenuhi kriteria:
   - Mengharuskan Managed Challenge jika Bot Score berada di bawah 40.
   - Segera melakukan aksi BLOCK jika Bot Score di bawah 10 ATAU jika request menggunakan metode HTTP selain `POST`.
   - Mengabaikan (bypass) aturan jika request berasal dari IP kantor staging terpercaya: `203.0.113.50`.
3. Tuliskan blok aturan Terraform Ruleset untuk Rate Limiting yang membatasi IP mana pun agar tidak dapat melakukan lebih dari 3 request per 60 detik pada path `/api/v2/reset-password`.

---

## 19. Challenge
Rancang arsitektur mitigasi komprehensif untuk aplikasi perbankan modern yang memiliki:
1. Web Banking Frontend (React SPA).
2. Mobile Banking Native App (iOS & Android).
3. Partner API (Integrasi B2B via REST).

**Tuntutan Tantangan**:
- Bagaimana Anda menyusun WAF Phase Ruleset agar validasi Machine Learning Bot Management tidak memblokir Mobile App yang menggunakan engine HTTP native (yang sering kali tidak memiliki user-agent browser standar)?
- Bagaimana Anda mengisolasi Partner API dari Turnstile challenge tanpa menurunkan postur keamanan dari serangan DDoS L7?
- Susun diagram alir pemrosesan request dan cantumkan Cloudflare Ruleset Expression yang spesifik untuk setiap kategori endpoint tersebut.

---

## 20. Summary
- **Anycast BGP** adalah tulang punggung mitigasi DDoS Cloudflare, menyebarkan beban serangan terdistribusi ke ratusan titik kehadiran edge global secara simultan.
- **dosd dan eBPF/XDP** mengeksekusi mitigasi volumetrik L3/L4 secara otonom di level interface kernel/driver, membuang paket serangan tanpa overhead alokasi memori CPU yang signifikan.
- **Magic Transit** mentransformasikan seluruh edge Cloudflare menjadi pelindung BGP Anycast untuk jaringan on-premise dan private cloud via terowongan GRE/IPsec dengan Direct Server Return.
- **Cloudflare Bot Management** memanfaatkan model Machine Learning untuk menghasilkan **Bot Score (1-99)**. Tindakan mitigasi dapat dipetakan secara presisi: blokir bot pasti (1-9) dan tantang bot yang dicurigai (10-29).
- **Turnstile** mendefinisikan ulang validasi keaslian pengguna (*human verification*) melalui mekanisme kriptografis non-intrusif berbasis browser telemetry, menggantikan CAPTCHA lama.
- **Advanced Rate Limiting** memungkinkan pembuatan perimeter batas laju adaptif berdasarkan identitas komposit (IP, API Key, Cookies) dan pencocokan status kode respons origin (misal: HTTP 401).

---