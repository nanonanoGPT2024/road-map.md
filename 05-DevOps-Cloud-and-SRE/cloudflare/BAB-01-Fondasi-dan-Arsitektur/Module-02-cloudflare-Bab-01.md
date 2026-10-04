# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Cloudflare

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (Analyze - C4)** alur internal paket jaringan pada edge infrastructure Cloudflare dari layer L4 (eBPF/XDP/Unimog) hingga L7 proxy engine (*Pingora*).
- **Mendesain (Create - C6)** topologi edge enterprise berkinerja tinggi menggunakan pola arsitektur *Zero Trust Origin Connectivity* (Cloudflare Tunnel), *Full (Strict) TLS*, dan *Tiered Cache*.
- **Mengimplementasikan (Apply - C3)** konfigurasi *Infrastructure as Code* (IaC) produksi menggunakan Terraform untuk mengelola zone settings, custom WAF rulesets, origin pools, dan health checks.
- **Mengevaluasi & Melakukan Troubleshooting (Evaluate - C5)** anomali trafik edge, kegagalan SSL handshake (Error 520–526), serta mendiagnosis bottle-neck latensi origin menggunakan *CF-Ray tracing* dan metrik telemetri enterprise.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
1. **Dasar Jaringan Komputer**: Model OSI 7 Layer, TCP 3-Way Handshake, terminasi TLS 1.3, DNS resolution (A, CNAME, NS, ALIAS), dan routing BGP Anycast.
2. **Fondasi Cloudflare (Modul 01)**: Konsep DNS proxy (*Orange Cloud* vs *Grey Cloud*), SSL modes dasar, dan konfigurasi Web GUI dasar.
3. **Tooling & Operasional**:
   - `curl`, `dig`, `openssl s_client`, dan `tcpdump`.
   - Terraform CLI (v1.5+) terinstal.
   - Akun Cloudflare Enterprise/Pro/Business dengan API Token bervalidasi least-privilege.
   - Docker Engine untuk deployment daemon `cloudflared`.

---

## 3. Concept & Internal Architecture (Mendalam)

Arsitektur Cloudflare tidak beroperasi seperti CDN tradisional yang menempatkan reverse-proxy terisolasi per region geografi (misal: AWS CloudFront atau Akamai legacy). Cloudflare mengimplementasikan **BGP Anycast** global di mana lebih dari 330 data center mengumumkan blok IP publik yang identik ke Internet Exchange Points (IXPs) dan transit providers (Tier 1 ISP).

```
                      INTERNET CLIENT
                            │
               [BGP Anycast IP Announcement]
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
       Edge DC: Jakarta              Edge DC: Singapore
 ┌───────────────────────────┐ ┌───────────────────────────┐
 │ 1. L4 LB: Unimog (XDP/eBPF)│ │ 1. L4 LB: Unimog (XDP/eBPF)│
 ├───────────────────────────┤ ├───────────────────────────┤
 │ 2. DoS Mitigation: Gatebot│ │ 2. DoS Mitigation: Gatebot│
 ├───────────────────────────┤ ├───────────────────────────┤
 │ 3. L7 Engine: Pingora     │ │ 3. L7 Engine: Pingora     │
 │    - TLS Termination      │ │    - TLS Termination      │
 │    - WAF Engine           │ │    - WAF Engine           │
 │    - V8 Worker Runtime    │ │    - V8 Worker Runtime    │
 │    - Cache (RocksDB/SSD)  │ │    - Cache (RocksDB/SSD)  │
 └─────────────┬─────────────┘ └─────────────┬─────────────┘
               │ (Cloudflare Backbone / Argo)│
               └──────────────┬──────────────┘
                              ▼
                     ENTERPRISE ORIGIN
               (Cloudflare Tunnel / mTLS)
```

### Pipeline Internal Layer 4 hingga Layer 7

1. **Ingress L4 (Unimog Load Balancer & XDP/eBPF)**:
   - Paket TCP SYN masuk ke Network Interface Card (NIC) server edge.
   - Program **XDP (eXpress Data Path)** yang berjalan langsung di driver level memproses paket sebelum menyentuh alokasi memori kernel Linux sk_buff.
   - **Unimog** mengeksekusi routing L4 connection tracking secara *stateless*. Jika satu server di dalam kluster mengalami restart atau pemeliharaan, Unimog mengarahkan paket ke server tetangga via IP-in-IP encapsulation tanpa memutus koneksi TCP yang sedang aktif.
   - **Gatebot** dan **dos-chassis** menginspeksi pola serangan volumetrik (SYN Flood, UDP Reflection) secara inline dan me-drop paket berbahaya dalam orde sub-mikrodetik.

2. **Terminasi TLS & L7 Proxy Engine (Pingora)**:
   - Pingora adalah proxy HTTP multi-threaded asinkron berbasis **Rust** yang menggantikan NGINX di arsitektur Cloudflare.
   - Pingora mengimplementasikan thread architecture berbasis *work-stealing* runtime (Tokio), memangkas *CPU lock contention*, dan menghemat konsumsi memori hingga 70% dibanding NGINX saat menangani jutaan koneksi bersamaan.
   - Pingora mengeksekusi terminasi TLS 1.3 (0-RTT), negosiasi ALPN (HTTP/2, HTTP/3 QUIC), dan dekompresi data.

3. **Rules Engine & WAF Pipeline**:
   - Paket yang telah didekripsi dievaluasi terhadap serangkaian ruleset yang dikompilasi ke bytecode via format ekspresi `wirefilter` (sintaks Wireshark-like).
   - Rules dieksekusi berurutan: Normalisasi URL -> IP Access Rules -> Security Custom Rules (WAF) -> Rate Limiting -> Transform Rules -> Cache Rules.

4. **Cache Subsystem & Tiered Cache**:
   - Cache metadata disimpan di RAM; payload biner disimpan di NVMe flash array menggunakan format penyimpanan terindeks performa tinggi.
   - **Tiered Cache**: Jika terjadi *cache miss* pada Edge POP lokal (misal: Jakarta), edge lokal tidak langsung menghubungi origin. Edge lokal akan me-route permintaan ke **Upper-Tier POP** terdekat (misal: Singapore) melalui backbone internal Cloudflare berlatensi rendah. Origin hanya dihubungi jika Upper-Tier POP juga mengalami *cache miss*.

5. **Egress ke Origin via Argo Smart Routing**:
   - Jika permintaan harus diteruskan ke origin, algoritma **Argo Smart Routing** mendeteksi latensi real-time, packet loss, dan network congestion di jalur internet publik. Argo kemudian merutekan trafik melalui rute optimal di jaringan backbone privat Cloudflare.

---

## 4. Why & What

| Dimensi | CDN Tradisional / Reverse Proxy Standar | Cloudflare Enterprise Edge |
| :--- | :--- | :--- |
| **Routing Architecture** | DNS-based Geo-IP routing (sering bias karena caching resolver pihak ketiga). | BGP Anycast murni (paket dirutekan ke POP terdekat secara topologi BGP). |
| **L7 Execution Engine** | NGINX fork / Apache / HAProxy (process/event per core). | **Pingora (Rust)** async multi-thread + **V8 Isolates** serverless compute. |
| **DDoS Mitigation** | Dialihkan ke "Scrubbing Center" eksternal via BGP Swing (latensi melonjak saat insiden). | *Always-on, inline mitigation* di setiap server, di setiap POP global tanpa degradasi routing. |
| **Origin Connectivity** | Mengandalkan IP publik origin yang dilindungi firewall IP whitelist (rentan port scan). | **Cloudflare Tunnel (cloudflared)**: Origin hanya menginisiasi koneksi *outbound* (zero open inbound ports). |
| **TLS Topology** | Seringkali "Flexible" (Client-Edge terenkripsi, Edge-Origin plain HTTP). | **Full (Strict) TLS** + **Origin CA** + **mTLS** autentikasi mutual kriptografis dua arah. |

---

## 5. How (Workflow Detail)

Berikut alur detail dari eksekusi request HTTPS hingga diteruskan ke origin enterprise:

```
[Client] 
   │ 
   ├── 1. DNS Resolution (Returns Anycast IP) ──────────────────────────┐
   ├── 2. TCP SYN / QUIC Initial ───────────────────────────────────────┤
   │                                                                    ▼
[Edge DC: Jakarta] ◄────────────────────────────────────────────────────┘
   │
   ├── 3. Unimog (eBPF/XDP): L4 Load Balancing
   ├── 4. Gatebot: Stateless volumetric DDoS check
   ├── 5. Pingora (Rust L7 Engine):
   │      a. TLS Handshake (Edge Certificate, 0-RTT/Session Resumption)
   │      b. HTTP Parsing (H2/H3 stream demultiplexing)
   │      c. WAF/Rules Engine evaluation (Phase: Ingress)
   │      d. Edge Cache Lookup (Local NVMe)
   │         ├── HIT  ──► Return 200 OK ke Client
   │         └── MISS ──┐
   │                    ▼
   ├── 6. Tiered Cache Engine:
   │      Query Upper-Tier POP (Singapore) via Internal Backbone
   │      ├── HIT  ──► Store to Local Cache ──► Return to Client
   │      └── MISS ──┐
   │                 ▼
   ├── 7. Egress Engine (Argo Smart Routing):
   │      a. WAF/Rules Engine evaluation (Phase: Pre-Origin)
   │      b. SNI and Host Header Mutation
   │      c. Encapsulation: HTTP/2 over gRPC via Cloudflare Tunnel
   │         (Atau direct mTLS IP-to-IP jika menggunakan Direct Egress)
   │                 │
   └─────────────────┼──────────────────────────────────────────────────┐
                     ▼                                                  ▼
          [Internet / Backbone]                               [Private Network]
                     │                                                  │
                     ▼                                                  ▼
             [Enterprise Origin]                                [cloudflared Agent]
         (Terminasi mTLS Origin CA)                         (Reverse Proxy internal)
                     │                                                  │
                     └───────────────── Origin App ◄────────────────────┘
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pos Terdesentralisasi vs Sentralisasi

- **CDN Konvensional**: Seperti memiliki kantor cabang pos yang hanya menyimpan brosur umum. Jika paket yang dicari tidak ada, kantor cabang menghubungi gudang pusat via kurir reguler jalan raya yang macet. Jika ada badai (DDoS), kantor cabang ditutup dan Anda dialihkan ke pos pemeriksaan militer di luar kota (Scrubbing Center).
- **Cloudflare Anycast & Pingora**: Seperti ribuan loket identik di setiap sudut kota yang langsung terhubung ke jaringan terowongan bawah tanah pribadi (*Backbone*). Setiap loket dijaga oleh robot penyaring ultra-cepat (*eBPF/XDP*) yang membuang sampah dalam hitungan milidetik sebelum barang diletakkan di meja loket (*Pingora*). Anda tidak perlu membuka pintu rumah Anda (*Origin*) kepada publik; Anda cukup menempatkan agen kurir rahasia (*Cloudflare Tunnel*) yang mengambil paket dari terowongan tersebut.

```
+-------------------------------------------------------------------------------+
|                        CLOUDFLARE EDGE INTERNAL PIPELINE                      |
+-------------------------------------------------------------------------------+
| [ L4 INGRESS ]                                                                |
|  Physical NIC -> XDP Driver -> eBPF (Gatebot / DDoS) -> Unimog Routing        |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| [ L7 PROCESSING - PINGORA ENGINE ]                                            |
|  +--------------------+     +---------------------+     +-------------------+ |
|  | TLS Termination    | --> | Wirefilter Engine   | --> | Cache Subsystem   | |
|  | - BoringSSL/Rust   |     | - WAF Rulesets      |     | - Local SSD       | |
|  | - Session Tickets  |     | - Bot Management    |     | - Tiered Cache    | |
|  +--------------------+     +---------------------+     +-------------------+ |
+-------------------------------------------------------------------------------+
                                      | Cache Miss
                                      v
+-------------------------------------------------------------------------------+
| [ SECURE ORIGIN EGRESS ]                                                      |
|  Option A: Cloudflare Tunnel (cloudflared via outbound TLS/QUIC tunnel)      |
|  Option B: Strict Direct mTLS (Argo Smart Routing Backbone -> Origin Gateway) |
+-------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Deklarasi Zone dan TLS Strict via Terraform

Menghilangkan konfigurasi GUI manual dan memaksakan *Full (Strict) TLS* dan HTTP/3:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

variable "zone_id" {
  type        = string
  description = "Target Zone ID"
}

# Paksa TLS 1.3 dan Full Strict Mode
resource "cloudflare_zone_settings_override" "production_security" {
  zone_id = var.zone_id

  settings {
    ssl                      = "strict"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    automatic_https_rewrites = "on"
    always_use_https         = "on"
    http2                    = "on"
    http3                    = "on"
    brotli                   = "on"
    zero_rtt                 = "off" # Nonaktifkan 0-RTT untuk mencegah TLS replay attack pada API mutatif
    security_header {
      enabled            = true
      preload            = true
      max_age            = 31536000 # 1 Tahun HSTS
      include_subdomains = true
      nosniff            = true
    }
  }
}
```

### Practical Example: Production WAF Ruleset & Cloudflare Tunnel

Berikut adalah arsitektur produksi menggunakan Cloudflare Tunnel terenkripsi dan Custom WAF Ruleset untuk proteksi API Enterprise:

#### 1. Terraform Definition (`waf_and_tunnel.tf`)

```hcl
# 1. Definisi Custom WAF Ruleset (Engine Fase HTTP Request)
resource "cloudflare_ruleset" "waf_api_protection" {
  zone_id     = var.zone_id
  name        = "Production API Protection Ruleset"
  description = "Block malicious scans, enforce JWT header presence, rate limit critical endpoints"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  # Aturan 1: Blokir bad bots dan SQL injection signature pada parameter API
  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/v1/\" and cf.threat_score gt 30) or (http.request.uri.query contains \"union select\")"
    description = "Block API abuse and SQLi patterns"
    enabled     = true
  }

  # Aturan 2: Wajibkan keberadaan Header Authorization pada private endpoints
  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/v1/internal/\") and not (http.request.headers[\"authorization\"][0] matches \"^Bearer \")"
    description = "Drop unauthorized internal API requests at edge"
    enabled     = true
  }
}

# 2. Definisi Cloudflare Zero Trust Tunnel
resource "cloudflare_tunnel" "enterprise_origin_tunnel" {
  account_id = var.account_id
  name       = "prod-core-banking-tunnel"
  secret     = var.tunnel_secret # Base64 32-byte secret
}

# 3. DNS CNAME memetakan traffic zone ke Tunnel ID
resource "cloudflare_record" "api_tunnel_cname" {
  zone_id = var.zone_id
  name    = "api"
  content = "${cloudflare_tunnel.enterprise_origin_tunnel.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

# 4. Ingress Rules Cloudflare Tunnel Configuration
resource "cloudflare_tunnel_config" "tunnel_routing" {
  account_id = var.account_id
  tunnel_id  = cloudflare_tunnel.enterprise_origin_tunnel.id

  config {
    warp_routing {
      enabled = false
    }
    origin_request_handler {
      connect_timeout = "10s"
      no_tls_verify   = false
      keep_alive_timeout = "60s"
    }

    ingress_rule {
      hostname = "api.enterprise.domain.com"
      service  = "https://internal-alb.internal.corp:443"
      origin_request {
        origin_server_name = "internal-alb.internal.corp"
        http2_origin       = true
      }
    }

    # Catch-all rule (wajib ada di Cloudflare Tunnel)
    ingress_rule {
      service = "http_status:404"
    }
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario
Sebuah platform fintech *Core Banking API* memproses rata-rata 80.000 Request Per Second (RPS) dengan lonjakan hingga 180.000 RPS saat tanggal gajian. 

### Masalah
1. Origin diserang *DDoS Application-Layer (L7)* yang menargetkan endpoint otentikasi (`/oauth/token`), menyebabkan CPU exhausted pada reverse proxy internal (NGINX bare-metal).
2. Latensi rata-rata inter-region di Asia Tenggara melonjak hingga 480ms karena rute peering ISP publik yang buruk (*BGP sub-optimal routing*).
3. Audit kepatuhan PCI-DSS melarang eksposur IP publik origin ke internet.

### Solusi Arsitektur
1. **Penutupan Total Port Inbound Origin**:
   - Seluruh IP publik origin dihapus dari DNS eksternal. Origin diletakkan di Private VPC.
   - Menggelar armada kontainer `cloudflared` redundan (Active-Active) di Amazon ECS multi-AZ yang terhubung langsung ke edge Cloudflare menggunakan protokol QUIC.
2. **Implementasi WAF + Rate Limiting di Edge Engine**:
   - Menerapkan Rate Limiting Rule: Maksimal 10 requests / 10 detik per individual IP untuk endpoint `/oauth/token`.
   - Mengaktifkan Cloudflare Bot Management dengan Machine Learning Score: me-mitigasi request dengan `cf.bot_management.score lt 20` via Managed Challenge.
3. **Optimasi Latensi dengan Tiered Cache & Argo**:
   - Mengaktifkan **Argo Smart Routing**: Paket data dialihkan melewati jaringan backbone serat optik privat Cloudflare, bukan internet publik.
   - Mengaktifkan **Tiered Cache** dengan Singapore sebagai Tiered Cache Hub untuk seluruh origin query di Asia Tenggara.

### Metrik Hasil
```
+------------------------------------+----------------+----------------+
| Metrik Produksi                    | Sebelum        | Sesudah        |
+------------------------------------+----------------+----------------+
| P95 Ingress Latency (SEA)          | 480 ms         | 65 ms          |
| Origin Peak CPU Load (L7 DDoS)     | 98% (Down)     | 18% (Stabil)   |
| Threat Drop Ratio at Edge          | 0%             | 99.98%         |
| Exposed Inbound Origin Ports       | 80, 443 terbuka| 0 (Zero Trust) |
| PCI-DSS Boundary Audit Compliance  | Non-Compliant  | 100% Passed    |
+------------------------------------+----------------+----------------+
```

---

## 9. Trade-offs

Menggunakan Cloudflare pada skala enterprise melibatkan pertimbangan arsitektural yang ketat:

```
                  KEUNTUNGAN                             KONSEKUENSI
       ┌───────────────────────────────┐      ┌──────────────────────────────┐
       │ - Anycast CDN global          │      │ - Vendor Lock-in tinggi      │
       │ - L4/L7 DDoS terintegrasi     │ vs   │   (Ruleset Engine spesifik)  │
       │ - Zero exposed ports (Tunnel) │      │ - Latensi bertambah jika     │
       │ - Out-of-the-box WAF & mTLS   │      │   origin dekat & cache miss  │
       └───────────────────────────────┘      └──────────────────────────────┘
```

1. **Latensi Cache-Miss vs Cache-Hit**:
   - *Hit*: Latensi ultra-rendah (<10ms) karena dilayani langsung dari memory/NVMe Edge POP terdekat.
   - *Miss*: Penambahan satu *hop* ekstra (Client -> Cloudflare Edge -> Pingora Pipeline -> Origin). Untuk payload non-cacheable dengan user yang berlokasi sama persis dengan origin server, menggunakan Cloudflare dapat menambah latensi sekitar 5–25ms dibanding koneksi direct peering murni.
2. **Zero-RTT TLS vs Replay Attacks**:
   - Mengaktifkan `0-RTT Connection Resumption` memangkas 1 RTT waktu negosiasi TLS.
   - **Trade-off**: Data early application request (`GET` requests tertentu) rentan terhadap *TLS replay attack* jika penyerang menangkap paket TLS awal dan memutarnya kembali. **Rekomendasi**: Nonaktifkan 0-RTT untuk API mutatif perbankan/fintech (`POST`, `PUT`, `DELETE`).
3. **Biaya Operasional vs Kompleksitas**:
   - Menggunakan Enterprise plan dengan Cloudflare Tunnel dan Argo Smart Routing mengeliminasi kebutuhan hardware L4/L7 load balancer on-premise yang mahal.
   - **Trade-off**: Biaya Argo dihitung berdasarkan bandwidth egress terkirim. Implementasi caching ruleset yang buruk dapat melipatgandakan tagihan Cloudflare secara tak terduga.

---

## 10. Common Mistakes & Troubleshooting

### 1. Kesalahan Fatal Mode SSL: "Flexible" vs "Full (Strict)"
- **Gejala**: Error `ERR_TOO_MANY_REDIRECTS` di browser atau keamanan rentan Man-in-the-Middle (MitM) di jalur Edge ke Origin.
- **Penyebab**: Mode "Flexible" mengenkripsi browser ke Cloudflare dengan HTTPS, tetapi Cloudflare menghubungi origin menggunakan HTTP (port 80). Jika origin memiliki redirect paksa HTTP-to-HTTPS, terbentuk infinite redirect loop.
- **Solusi**: Gunakan **Full (Strict)**. Pasang sertifikat yang valid di origin (seperti *Cloudflare Origin CA Certificate*) dan paksa koneksi port 443.

### 2. Kegagalan Handshake Origin (Cloudflare Error Codes 52x)

```
[Client] ---> HTTPS ---> [Cloudflare Edge] --X (Error 52x) X--> [Origin]
```

- **Error 521 (Web Server Is Down)**: Origin menolak koneksi TCP pada port 443/80. Cek apakah firewall origin memblokir blok IP Anycast Cloudflare.
- **Error 522 (Connection Timed Out)**: TCP 3-way handshake antara Cloudflare dan origin melebihi batas waktu (timeout 15 detik). Umumnya akibat *routing blackhole* atau firewall origin men-drop paket TCP SYN tanpa mengirim SYN-ACK/RST.
- **Error 525 (SSL Handshake Failed)**: Cloudflare tidak dapat menyelesaikan negosiasi TLS dengan origin. Biasanya karena ciphersuite origin tidak kompatibel, SNI mismatch, atau protokol SSLv3/TLS 1.0 yang sudah di-deprecate oleh Pingora.
- **Error 526 (Invalid SSL Certificate)**: Terjadi pada mode **Full (Strict)** jika sertifikat origin expired, nama domain tidak cocok dengan parameter SNI yang dikirimkan Cloudflare, atau sertifikat ditandatangani oleh CA yang tidak dipercaya dan bukan Cloudflare Origin CA.

### Matriks Debugging via CLI Enterprise

Gunakan `curl` dengan custom headers dan bypass resolver:

```bash
# 1. Analisis headers edge response dan eksekusi tracing CF-Ray
curl -Iv https://api.enterprise.domain.com/healthz \
  -H "Pragma: no-cache" \
  -H "Cache-Control: no-cache"

# Inspeksi nilai header krusial:
# cf-ray: 86b1c43f7a1b4d21-CGK (ID transaksi tracing unik + kode IATA POP: CGK = Jakarta)
# cf-cache-status: DYNAMIC / HIT / MISS / BYPASS
# server: cloudflare

# 2. Uji langsung origin dengan menyamakan parameter SNI Cloudflare
curl -Iv https://<ORIGIN_IP>:443/healthz \
  --resolve api.enterprise.domain.com:443:<ORIGIN_IP> \
  -H "Host: api.enterprise.domain.com" \
  --cacert /path/to/origin-ca-root.pem
```

---

## 11. Best Practices (Production Checklist)

### Security Checklist
- [ ] Mode SSL/TLS diatur ke **Full (Strict)** di seluruh zone tanpa pengecualian.
- [ ] Minimum TLS Version dikunci pada **TLS 1.2** (atau TLS 1.3 only untuk high-security API).
- [ ] **HSTS (HTTP Strict Transport Security)** diaktifkan dengan `max-age=31536000`, `includeSubDomains`, dan `preload`.
- [ ] Semua port ingress origin diblokir total menggunakan Cloudflare Tunnel atau Origin mTLS.
- [ ] **WebSockets** dinonaktifkan secara global jika aplikasi tidak menggunakannya untuk meminimalisir vector long-lived TCP tunnel abuse.

### Reliability & Resilience Checklist
- [ ] Deploy minimal **2 instance replica** `cloudflared` tunnel agent per zone secara multi-AZ untuk menjamin high availability (HA).
- [ ] Konfigurasi **Health Checks** terintegrasi dengan Cloudflare Load Balancer untuk otomatisasi failover antar origin pool.
- [ ] Aktifkan fitur **Always Online** sehingga Cloudflare dapat melayani static snapshot dari cache jika origin mengalami downtime total.

### Caching & Performance Checklist
- [ ] Implementasikan **Tiered Cache** untuk meningkatkan cache hit ratio dan mengurangi beban langsung ke origin.
- [ ] Pisahkan konfigurasi caching dynamic API menggunakan **Cache Rules** (Rule Phase: HTTP Cache) dengan bypass eksplisit pada cookie otentikasi.
- [ ] Aktifkan kompresi modern: **Brotli** dan **HTTP/3 (QUIC)**.

---

## 12. Hands-on Practice: Zero-Trust Origin & IaC Automation

Praktikum ini akan mengonfigurasi arsitektur origin privat dengan Cloudflare Tunnel via Docker Compose dan Terraform. Seluruh artefak disimpan di direktori `hands-on/m02/`.

### Langkah 1: Struktur Proyek
Buat struktur direktori di mesin lokal Anda:
```bash
mkdir -p hands-on/m02/{terraform,docker}
cd hands-on/m02
```

### Langkah 2: Konfigurasi Mock Origin Service & Cloudflare Tunnel Agent
Buat file `docker/docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Internal enterprise mock origin
  origin-app:
    image: hashicorp/http-echo:latest
    command: ["-text=Halo dari Origin Privat Terenkripsi Cloudflare Tunnel!"]
    networks:
      - internal-net
    expose:
      - "5678"

  # Cloudflare Tunnel Daemon (Zero inbound connection required)
  cloudflared:
    image: cloudflare/cloudflared:2024.4.0
    restart: always
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    command: tunnel --no-autoupdate run
    networks:
      - internal-net
    depends_on:
      - origin-app

networks:
  internal-net:
    driver: bridge
```

### Langkah 3: Konfigurasi Terraform Otomasi (`terraform/main.tf`)
Buat file `terraform/main.tf`:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.0"
    }
  }
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "account_id" {
  type = string
}

variable "zone_id" {
  type = string
}

variable "subdomain" {
  type    = string
  default = "tunnel-lab"
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# Generate random string untuk tunnel secret
resource "random_id" "tunnel_secret" {
  byte_length = 32
}

# 1. Buat Cloudflare Tunnel
resource "cloudflare_tunnel" "auto_lab_tunnel" {
  account_id = var.account_id
  name       = "lab-m02-tunnel"
  secret     = random_id.tunnel_secret.b64_std
}

# 2. Binding Ingress Rule Tunnel
resource "cloudflare_tunnel_config" "auto_lab_config" {
  account_id = var.account_id
  tunnel_id  = cloudflare_tunnel.auto_lab_tunnel.id

  config {
    ingress_rule {
      hostname = "${var.subdomain}.${data.cloudflare_zone.selected.name}"
      service  = "http://origin-app:5678"
    }
    ingress_rule {
      service = "http_status:404"
    }
  }
}

data "cloudflare_zone" "selected" {
  zone_id = var.zone_id
}

# 3. DNS CNAME Record
resource "cloudflare_record" "tunnel_dns" {
  zone_id = var.zone_id
  name    = var.subdomain
  content = "${cloudflare_tunnel.auto_lab_tunnel.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

output "tunnel_token" {
  value     = cloudflare_tunnel.auto_lab_tunnel.tunnel_token
  sensitive = true
}

output "access_url" {
  value = "https://${var.subdomain}.${data.cloudflare_zone.selected.name}"
}
```

### Langkah 4: Eksekusi Deployment
1. Jalankan Terraform:
   ```bash
   cd terraform
   terraform init
   terraform apply -var="cloudflare_api_token=<YOUR_TOKEN>" \
                   -var="account_id=<YOUR_ACCOUNT_ID>" \
                   -var="zone_id=<YOUR_ZONE_ID>"
   ```
2. Ekstrak output token tunnel dan jalankan stack origin Docker:
   ```bash
   export TUNNEL_TOKEN=$(terraform output -raw tunnel_token)
   cd ../docker
   docker compose up -d
   ```
3. Validasi koneksi Zero Trust dari terminal Anda:
   ```bash
   curl -I https://tunnel-lab.yourdomain.com
   ```
   *Verifikasi header `cf-ray`, `server: cloudflare`, dan pastikan response body bertuliskan pesan rahasia tanpa membuka port apapun pada router/firewall host Anda.*

---

## 13. Exercises

### Level: Easy
1. Ubah konfigurasi Terraform di langkah hands-on untuk menambahkan setting minimum TLS ke versi `1.3` saja. Lakukan verifikasi via `openssl s_client -connect <domain>:443 -tls1_2` dan pastikan handshake ditolak (handshake failure).
2. Periksa header response curl dan jelaskan perbedaan antara status `cf-cache-status: DYNAMIC` dan `cf-cache-status: HIT`.

### Level: Medium
1. Buat **Cache Ruleset** via Terraform yang memaksa Cloudflare untuk meng-cache ekstensi gambar (`.png`, `.jpg`, `.webp`) selama 7 hari di edge, tetapi secara eksplisit melakukan bypass cache (`BYPASS`) apabila request membawa header `Authorization` atau cookie `session_id`.
2. Konfigurasikan Custom WAF Rule untuk men-challenge (`managed_challenge`) setiap request yang berasal dari Autonomous System Number (ASN) provider hosting publik (AWS, DigitalOcean, GCP) yang mengakses root path `/`.

### Level: Hard
1. Implementasikan arsitektur **Mutual TLS (mTLS)** antara Cloudflare Edge dan origin server. Anda harus membuat Cloudflare Authenticated Origin Pull CA, men-deploy sertifikat client ke Cloudflare, dan menyusun konfigurasi reverse proxy (misal: NGINX atau Envoy) di origin yang menolak setiap koneksi yang tidak memiliki sertifikat client yang divalidasi oleh CA Cloudflare.

---

## 14. Challenge

### Studi Kasus: Disaster Recovery & Geofencing Zero-Downtime Origin Architecture

**Deskripsi Tantangan**:
Sebuah unicorn e-commerce global mengharuskan Anda membangun sistem Ingress Traffic Management dengan kriteria arsitektur berikut:
1. Origin beroperasi secara *Active-Active* di dua region cloud yang berbeda: Region Primary (AWS Singapura) dan Region Secondary (GCP Jakarta).
2. Data kedaulatan finansial mengharuskan seluruh pengguna dari IP Indonesia (`cf.ip.geoip.country == "ID"`) diarahkan secara eksklusif ke Region Secondary (Jakarta), KECUALI jika Region Secondary mengalami penurunan performa (P90 latency > 300ms atau status 5xx > 2%).
3. Jika Region Secondary gagal, traffic Indonesia harus dialihkan (*automatic fallback*) ke Region Primary secara instan tanpa intervensi manual (RTO < 10 detik).
4. Penyerang yang terindikasi menggunakan VPN/Tor Proxy yang mencoba mengakses endpoint checkout (`/checkout/pay`) harus di-*block* total, sementara pengguna umum dari IP beresiko moderat dialihkan ke *Turnstile / Managed Challenge*.
5. Seluruh infrastruktur harus didefinisikan secara deklaratif menggunakan Terraform (HCL), mencakup Ruleset Engine, Load Balancer Pool, Health Monitors, dan Origin Tunnel.

**Deliverable**:
- Script arsitektur Terraform lengkap dan modular (`main.tf`, `load_balancer.tf`, `waf.tf`).
- Diagram dependensi alur penanganan kegagalan (*failover path state machine*).
- Rancangan pengujian simulasi chaos engineering untuk mematikan salah satu tunnel pool secara terprogram.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)

1. **Bagaimana Cloudflare Anycast merutekan request pengguna ke Edge Data Center?**
   - A. Melalui query DNS berkala yang mengevaluasi lokasi geolokasi IP pengguna.
   - B. Seluruh POP mengumumkan blok IP yang sama melalui protokol BGP; router internet mengarahkan paket ke rute terpendek secara topologi BGP.
   - C. Menggunakan master load balancer tunggal di pusat data Cloudflare San Francisco yang mendistribusikan traffic.
   - D. Melalui instruksi redirect HTTP 302 di layer aplikasi.

2. **Apa fungsi utama dari arsitektur Unimog pada Layer 4 Cloudflare?**
   - A. Melakukan render engine JavaScript V8.
   - B. Menangani sertifikat SSL Let's Encrypt.
   - C. Stateless connection tracking dan L4 load balancing berbasis eBPF/XDP di level NIC kernel.
   - D. Menyimpan database cache RocksDB di memori NVMe.

3. **Mengapa mode SSL/TLS "Flexible" sangat dilarang dalam standar produksi enterprise?**
   - A. Karena memerlukan instalasi agen cloudflared di origin.
   - B. Karena koneksi antara Cloudflare Edge dan Origin tidak dienkripsi (Plain HTTP/Port 80), membuka celah sniffing traffic dan MitM.
   - C. Karena "Flexible" memblokir protokol HTTP/2 dan HTTP/3.
   - D. Karena "Flexible" mengenkripsi traffic dua kali sehingga menambah latensi CPU origin.

4. **Komponen apa yang menggantikan NGINX sebagai L7 Reverse Proxy Engine utama di Cloudflare?**
   - A. Envoy
   - B. HAProxy
   - C. Pingora (berbasis Rust)
   - D. Traefik

5. **Header response HTTP mana yang menunjukkan identifikasi data center Cloudflare spesifik yang memproses permintaan?**
   - A. `X-Cache-Lookup`
   - B. `cf-ray`
   - C. `X-Powered-By: Cloudflare-Unimog`
   - D. `Server-Timing`

---

### Bagian B: Intermediate (Pilihan Ganda)

6. **Apa yang menyebabkan browser mengalami error loop `ERR_TOO_MANY_REDIRECTS` saat sebuah zone Cloudflare diaktifkan?**
   - A. Sertifikat Origin CA telah expired lebih dari 24 jam.
   - B. Pengaturan SSL zone diatur ke "Flexible", sementara server origin memiliki aturan rewrite internal yang memaksa traffic HTTP ke HTTPS.
   - C. Rate limiting WAF memblokir permintaan client secara agresif.
   - D. Tunnel agent cloudflared gagal melakukan proses handshake QUIC.

7. **Dalam pipeline eksekusi Pingora, manakah urutan evaluasi L7 yang benar sebelum request menyentuh origin?**
   - A. Origin Egress -> Edge Cache -> TLS Termination -> WAF Ruleset.
   - B. TLS Termination -> Ingress Normalization & WAF Rules -> Cache Evaluation -> (jika miss) Tiered Cache / Origin Egress.
   - C. Cache Lookup -> TLS Handshake -> Bot Management -> Rate Limiting.
   - D. Argo Routing -> Unimog -> XDP -> DNS Lookup.

8. **Fitur "Tiered Cache" Cloudflare memangkas beban origin (*Origin Shielding*) dengan cara...**
   - A. Menyimpan seluruh database SQL origin di edge memory.
   - B. Membatasi koneksi TCP origin hanya maksimal 100 request bersamaan.
   - C. Mengorganisir Edge POP lokal agar meminta file cache yang hilang (*cache miss*) ke kumpulan POP regional tingkat atas (*Upper-Tier POP*) sebelum menghubungi origin.
   - D. Mengubah format gambar PNG menjadi format WebP secara dinamis.

9. **Apa risiko keamanan utama dari pengaktifan fitur 0-RTT Connection Resumption pada protokol TLS 1.3 untuk API transaksional?**
   - A. Penyerang dapat membaca private key origin server.
   - B. Data pada `early data packet` dapat direkam dan dikirim ulang oleh attacker (*Replay Attack*), menyebabkan eksekusi idempotensi ganda pada transaksi mutatif.
   - C. Terjadinya memory leak pada alokasi Tokio worker di Pingora engine.
   - D. Cloudflare Tunnel secara otomatis menurunkan versi enkripsi menjadi TLS 1.0.

10. **Bila Anda melihat status HTTP 526 dari edge Cloudflare, tindakan perbaikan apa yang tepat di sisi origin?**
    - A. Memastikan web server origin menyala dan port 80 terbuka.
    - B. Mengganti nama instance tunnel pada konfigurasi daemon Docker compose.
    - C. Menginstal sertifikat SSL valid yang ditandatangani oleh CA publik atau Cloudflare Origin CA dan memastikan nama domain cocok dengan SNI yang diminta.
    - D. Menambahkan IP Unimog ke dalam iptables whitelist di origin.

---

### Bagian C: Kasus Skenario Produksi

11. **Skenario 1**: 
    Tim DevOps Anda baru saja melakukan migrasi sebuah domain enterprise ke Cloudflare. Seketika itu juga, monitoring origin melaporkan bahwa nilai header `X-Forwarded-For` pada log aplikasi mencatat IP yang seragam (hanya menampilkan blok IP Cloudflare) dan bukan IP asli client pengguna, sehingga sistem antifraud internal mengalami kegagalan deteksi. Bagaimana arsitektur perbaikannya di layer edge dan origin?

12. **Skenario 2**:
    Aplikasi microservice checkout Anda mengalami error berkala `HTTP 502 Bad Gateway` dan `HTTP 522 Connection Timed Out` hanya pada jam sibuk puncak (*peak hours* 12:00 - 13:00). Pemeriksaan metrik menunjukkan utilisasi CPU origin server hanya 30%, namun origin berada di balik firewall stateful on-premise. Apa akar masalah arsitekturalnya dan bagaimana solusinya?

13. **Skenario 3**:
    Perusahaan Anda meluncurkan API publik baru di bawah zone Cloudflare. Security Auditor menemukan bahwa attacker dapat melakukan bypass proteksi Cloudflare WAF secara menyeluruh hanya dengan mengirimkan request langsung ke IP publik origin (Origin IP Direct Exposure). Langkah mitigasi arsitektur komprehensif apa yang harus dieksekusi untuk menutup celah ini secara permanen tanpa mengganggu integrasi partner?

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian A (Basic)
1. **Jawaban: B**. BGP Anycast mempublikasikan prefix IP yang sama secara serentak ke ISP global; tabel routing BGP di internet secara otomatis mengalirkan paket ke hop/POP terdekat secara topologi.
2. **Jawaban: C**. Unimog adalah load balancer layer-4 internal Cloudflare yang bekerja di Linux kernel space melalui XDP/eBPF secara stateless untuk membagi beban traffic ke cluster server fisik.
3. **Jawaban: B**. Mode Flexible mengirimkan traffic dari Edge Cloudflare ke origin server via plain HTTP tanpa enkripsi, sehingga rentan disadap di internet publik.
4. **Jawaban: C**. Pingora adalah HTTP proxy engine asinkron berbasis Rust yang dikembangkan sendiri oleh Cloudflare untuk menggantikan keterbatasan NGINX.
5. **Jawaban: B**. Header `cf-ray` menyertakan ID penelusuran unik per request beserta IATA airport code (misal: `-CGK` untuk Jakarta, `-SIN` untuk Singapura) yang merepresentasikan POP pemroses.

#### Bagian B (Intermediate)
6. **Jawaban: B**. Cloudflare Flexible mengirim request HTTP port 80 ke origin. Origin yang memiliki directive redirect HTTPS mengirimkan HTTP 301 ke browser. Browser meminta HTTPS kembali ke Cloudflare, dan Cloudflare kembali memanggil HTTP ke origin, memicu loop tak berujung.
7. **Jawaban: B**. Pingora pertama kali menyelesaikan negosiasi TLS, mengurai dan memvalidasi HTTP request melalui WAF/bot rules, mengecek local SSD cache, baru mengevaluasi Tiered Cache/Origin jika terjadi cache miss.
8. **Jawaban: C**. Tiered Cache mengonsolidasikan POP-POP kecil lokal ke Upper-Tier POP raksasa, sehingga puluhan data center lokal tidak menghujani origin server secara independen saat cache expired.
9. **Jawaban: B**. Data TLS 0-RTT awal dikirim sebelum negosiasi cryptographic handshake selesai sempurna, sehingga request tersebut dapat ditangkap oleh passive eavesdropper dan diputar ulang (*replay*) ke server.
10. **Jawaban: C**. HTTP 526 secara spesifik menandakan Cloudflare diatur pada mode SSL "Full (Strict)", namun sertifikat yang disajikan oleh origin invalid, self-signed tanpa trusted store, expired, atau SNI-nya tidak cocok.

#### Bagian C (Kasus Skenario Produksi)
11. **Solusi Skenario 1**:
    - **Akar Masalah**: Cloudflare bertindak sebagai reverse proxy L7; TCP packet source IP yang sampai di origin adalah IP Anycast Cloudflare.
    - **Solusi**: Origin web server/reverse proxy harus dikonfigurasi untuk membaca header `CF-Connecting-IP` (atau `True-Client-IP` pada paket Enterprise) dan me-restore header tersebut menjadi IP client asli (misalnya menggunakan modul `ngx_http_realip_module` di NGINX dengan mendaftarkan IP range resmi Cloudflare sebagai `set_real_ip_from`).
12. **Solusi Skenario 2**:
    - **Akar Masalah**: Firewall stateful on-premise origin mengalami *State Table Exhaustion*. Karena Cloudflare memusatkan ratusan ribu koneksi pengguna ke sejumlah kecil alamat IP Anycast, firewall origin menganggap jutaan koneksi masuk dari IP yang sama sebagai serangan SYN-flood atau melebihi batas penampungan tabel koneksi stateful-nya, lalu secara acak men-drop paket TCP SYN (memicu error 522).
    - **Solusi**: Ubah konektivitas ingress origin menggunakan **Cloudflare Tunnel (cloudflared)**. Tunnel ini menginisiasi koneksi murni *outbound* (Stateful TCP/QUIC keluar dari origin ke edge Cloudflare). Stateful table firewall origin tidak akan overload oleh paket inbound baru, dan port inbound publik firewall dapat dinonaktifkan sepenuhnya.
13. **Solusi Skenario 3**:
    - **Solusi Komprehensif**:
      1. *Rotasi IP Origin*: Ubah IP publik origin lama karena telah terkompromi/terekspos di internet scanning history (seperti Shodan/Censys).
      2. *Network Level Quarantine*: Blokir seluruh traffic ingress di firewall ISP/Cloud Provider origin, KECUALI IP Prefix resmi Cloudflare.
      3. *Cryptographic Enforcement*: Terapkan **Authenticated Origin Pulls (mTLS)**. Konfigurasikan origin web server untuk memvalidasi client certificate yang dikirimkan oleh Cloudflare. Request langsung dari attacker yang menembak IP origin tanpa sertifikat client CA Cloudflare akan langsung di-reject pada layer TLS handshake level origin.
      4. *Solusi Paling Ideal*: Singkirkan IP publik secara total dan terapkan **Cloudflare Tunnel**, mengeliminasi rute bypass langsung ke origin server.

---

## 16. Summary

Arsitektur produksi Cloudflare modern merepresentasikan evolusi mendasar dari paradigma CDN berbasis cache statis menuju edge computing terdistribusi penuh. Komponen intinya—dimulai dari mitigasi volumetrik L4 via **eBPF/XDP**, routing L4 stateless via **Unimog**, processing engine L7 berkinerja tinggi via **Pingora (Rust)**, hingga optimalisasi routing origin via **Argo** dan **Cloudflare Tunnel**—memungkinkan rekayasa infrastruktur internet enterprise mencapai ketersediaan tinggi, latensi minimal, dan keamanan Zero-Trust.

Penerapan standar produksi Cloudflare wajib memprioritaskan keamanan kriptografis melalui mode **Full (Strict) TLS**, perlindungan terpadu via deklarasi **IaC (Terraform)**, isolasi origin total tanpa open port inbound, serta pemantauan visibilitas request mendalam menggunakan metrik **CF-Ray** dan telemetri edge real-time.