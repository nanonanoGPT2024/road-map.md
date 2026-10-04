# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Global Traffic Steering, Load Balancing & Argo Smart Routing**  
**Kategori: 05-DevOps-Cloud-and-SRE**

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah Internalitas** mekanisme *Anycast BGP*, L4/L7 *reverse proxy* (Pingora), serta *telemetry engine* Cloudflare Load Balancing (CFLB) dan Argo Smart Routing.
- **Merancang Arsitektur Global Traffic Steering** berbasis latensi (*dynamic steering*), geolokasi (*geo steering*), dan *proximity* dengan topologi *Multi-Region Active-Active* serta *hybrid cloud/on-premise*.
- **Mengimplementasikan dan Mengotomatisasi** *origin pools*, *health check monitors*, *session affinity*, serta *traffic steering policies* menggunakan Terraform/OpenTofu sesuai standar enterprise.
- **Mengoptimalkan Jalur Transmisi L7 & L4** memanfaatkan *Argo Smart Routing* dan *Tiered Caching* guna mereduksi *Packet Loss*, *Time to First Byte* (TTFB), dan beban *egress* origin.
- **Mendiagnosis, Memitigasi, dan Menangani Masalah Produksi** seperti *failover flapping*, *health check false positives*, *split-brain routing*, dan *cache coherency degradation* menggunakan *tracing headers* dan metrik analitik edge.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
1. **Networking Fondasional L3–L7**:
   - Prinsip kerja BGP (Border Gateway Protocol), Anycast vs. Unicast routing.
   - TCP 3-way handshake, TLS 1.3 termination, HTTP/2 dan HTTP/3 (QUIC) multiplexing.
   - Konsep DNS hierarkis: Authoritative DNS, recursive resolvers, TTL propagation, EDNS Client Subnet (ECS).
2. **Infrastruktur & Cloud**:
   - Pemahaman arsitektur *high availability* (Active-Active, Active-Passive, Multi-AZ, Multi-Region).
   - Pengetahuan praktis konfigurasi reverse proxy (Nginx, Envoy, atau HAProxy).
3. **IaC & Automation**:
   - Kemahiran sintaksis Terraform/OpenTofu (HCL), pengelolaan *state*, dan pemanfaatan Cloudflare Provider (v4.x/v5.x).
4. **Alat Debugging & Analisis Jaringan**:
   - Penggunaan `curl`, `dig`, `traceroute`, `tcpdump`, serta inspeksi HTTP headers via terminal.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur traffic steering Cloudflare beroperasi pada lapisan abstraksi jaringan terdistribusi yang memadukan Anycast L3/L4 dengan pemrosesan request L7 berbasis software proxy bernama **Pingora** (arsitektur berbasis Rust pengganti Nginx).

```
[ Klien Global ]
       │ (DNS Query / Anycast IP 1.1.1.1, etc.)
       ▼
┌───────────────────────────────────────────────────────────┐
│              Cloudflare Edge PoP (Anycast BGP)            │
│  ┌───────────────────────┐     ┌───────────────────────┐  │
│  │ L4 Maglev/Katran (XDP)│ ──> │ L7 Pingora Proxy Core │  │
│  └───────────────────────┘     └──────────┬────────────┘  │
│                                           │               │
│                        ┌──────────────────┴─────────────┐ │
│                        ▼                                │ │
│            ┌──────────────────────┐                     │ │
│            │ CFLB Decision Engine │                     │ │
│            └──────────┬───────────┘                     │ │
└───────────────────────┼─────────────────────────────────┼─┘
                        │
       ┌────────────────┴─────────────────────────┐
       ▼ (Argo Smart Routing / Private Backbone)  ▼ (Direct Internet)
┌──────────────┐                          ┌──────────────┐
│ Origin A     │                          │ Origin B     │
│ (Jakarta-ID) │                          │ (Frankfurt)  │
└──────────────┘                          └──────────────┘
```

#### A. Edge Ingress: Anycast BGP & L4 Flow Balancing
Ketika klien melakukan query DNS untuk domain terproteksi CFLB, Cloudflare mengembalikan alamat Anycast IP yang sama ke seluruh dunia. Router ISP terdekat mengarahkan paket ke Data Center (PoP) Cloudflare terdekat secara topologis berdasarkan BGP AS-Path terpendek.
- Di level PoP, packet filter L4 berbasis eBPF/XDP (*Unimog* / turunan Katran) mendistribusikan traffic ke node server worker tanpa mempertahankan state TCP terpusat.
- TLS di-terminasi di edge PoP terdekat dengan klien (Zero-RTT jika session resumption aktif).

#### B. Pingora L7 Proxy Core & Decision Engine
Setelah koneksi didekripsi di L7, modul **Pingora** mengeksekusi routing logic:
1. **Identification**: Memeriksa hostname, path, dan header request.
2. **Session Affinity Check**: Memeriksa keberadaan cookie session (misal: `__cf_bm` atau custom cookie seperti `CFLB_AFFINITY`). Jika valid dan origin target sehat, traffic langsung dialirkan ke origin tersebut.
3. **Load Balancing Engine Evaluation**: Jika tidak ada affinity atau session telah kadaluwarsa, engine memilih pool berdasarkan kebijakan:
   - *Geo Steering*: Memetakan kode negara/benua klien (berdasarkan IP database Cloudflare) ke pool spesifik.
   - *Dynamic Steering (Latency-based)*: Memilih pool dengan RTT (Round Trip Time) terendah yang diukur secara periodik dari edge PoP ke origin pools.
   - *Proximity Steering*: Berdasarkan jarak geografis GPS (koordinat PoP vs koordinat origin).
   - *Random / Weighted Round Robin*: Berdasarkan rasio bobot (*weight*) origin pool.

#### C. Argo Smart Routing & Tiered Caching Internals
Ketika Pingora memutuskan paket harus dikirim ke upstream origin:
- **Public Transit vs. Argo Private Backbone**: Secara default, edge PoP berkomunikasi dengan origin melalui internet publik multi-hop. Jalur ini rentan terhadap *packet loss*, BGP route flapping, dan kongesti inter-domain.
- **Telemetry Matrix Argo**: Setiap request yang melintasi jaringan Cloudflare mengumpulkan metrik performa real-time (RTT, bandwidth, packet drop rate) antar-PoP Cloudflare di seluruh dunia.
- **Smart Pathing**: Jika rute langsung dari Edge PoP (misal: London) ke Origin (misal: Jakarta) terdeteksi mengalami degradasi latensi > 15%, Argo mengalihkan traffic secara internal melalui PoP transit (misal: London -> Singapura -> Jakarta) melalui backbone fiber optic teroptimasi milik Cloudflare.
- **Tiered Caching Topology**: Menggunakan hierarki Upper-tier PoP yang dekat dengan origin untuk mengonsolidasi cache miss, mencegah *thundering herd* langsung menghantam origin infrastructure.

#### D. Distributed Health Check Probing System
Health check Cloudflare **bukan** probe terpusat.
- Monitor probe dijalankan secara paralel dari puluhan Edge PoP global yang didistribusikan ke region yang ditentukan.
- Konsensus kesehatan dihitung menggunakan algoritma quorum edge-to-origin: Jika pool didefinisikan membutuhkan 3 PoP konfirmasi gagal, status pool otomatis dialihkan ke *Unhealthy*, dan *failover sequence* dieksekusi secara instan (< 3-5 detik) pada control plane edge di seluruh dunia tanpa perlu menunggu TTL DNS kedaluwarsa.

---

### 4. Why & What

| Dimensi | DNS Round Robin Tradisional / GSLB | Cloudflare Load Balancing (L7) + Argo |
| :--- | :--- | :--- |
| **Failover Convergence Time** | Sangat Lambat (300s – 86400s) karena caching pada ISP Recursive Resolver (*TTL Hell*). | Instan (< 3–5 detik). Anycast IP tetap sama; pengalihan dilakukan pada L7 Edge Proxy. |
| **Health Checking Fidelity** | Cek sederhana dari 1 atau 2 datacenter terpusat; sering timbul *false positive*. | Terdistribusi multi-PoP global; deteksi kegagalan berbasis respons kode HTTP/L4 TCP nyata. |
| **Granularitas Routing** | Terbatas pada domain level (A/AAAA record). Tidak sadar URI/Path. | Sadar protokol L7: Routing berdasarkan URI Path, Header, Method, Cookie, dan Geolocation. |
| **Optimasi Jalur Jaringan** | Mengikuti *best-effort routing* dari BGP publik ISP transit. | **Argo Smart Routing**: Menggunakan deteksi kongesti real-time via Cloudflare global network. |
| **Session Persistence** | Berbasis Client IP hash (rawan gagal jika klien berada di balik CGNAT/ISP mobile). | Berbasis enkripsi cookie signed L7 (presisi tinggi per browser session). |

---

### 5. How (Workflow Detail)

Alur eksekusi komprehensif saat request masuk:

```
[Klien] 
   │ 1. HTTP GET https://api.enterprise.com/v1/checkout
   ▼
[Cloudflare Edge PoP (Anycast)]
   │ 2. Terminasi TLS 1.3 & Parsing HTTP Request
   │ 3. Cek Cookie Session Affinity
   ├───(Cookie Valid & Origin Sehat)───> [Forward ke Origin Terpilih]
   │
   └───(Cookie Tidak Ada / Expired)
         │ 4. Eksekusi Load Balancer Steering Rule
         │    - Evaluasi Region/Geo Klien
         │    - Evaluasi Latensi Pool (Dynamic Steering Table)
         │ 5. Filter Origin Pool (Eliminasi origin Unhealthy via Health Probe Monitor)
         │ 6. Kalkulasi Weighted Selection pada origin yang tersisa
         │ 7. Tentukan Jalur Pengiriman via Argo Engine:
         │    - Bandingkan: Direct Internet vs. Argo Optimized Transit PoP
         │ 8. Inject Header Pelacakan (`cf-ray`, `CF-Connecting-IP`)
         ▼
[Argo Backbone / Transit Edge PoP] (Opsional, jika rute direct suboptimal)
         │ 9. TCP Connection Re-use (Keep-Alive Pool Pingora)
         ▼
[Target Origin Server (Jakarta / Frankfurt / Virginia)]
         │ 10. Origin Memproses & Mengembalikan HTTP Response 200 OK
         ▼
[Cloudflare Edge PoP]
         │ 11. Enkripsi Header Cookie Affinity Baru (bila diaktifkan)
         │ 12. Streaming Response ke Klien
         ▼
[Klien] (Menerima respons dengan latensi terendah)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Navigasi GPS Real-Time (Waze) vs. Peta Kertas Statis
- **DNS Tradisional (Peta Kertas)**: Sebelum berangkat, Anda melihat rute dari peta. Jika jembatan di tengah jalan ambruk 5 menit kemudian, Anda tidak tahu sampai mobil Anda terjebak di depan reruntuhan, menunggu peta baru dicetak dan dikirimkan ke rumah Anda (TTL DNS).
- **Cloudflare Load Balancing + Argo (Waze Global)**: Setiap mobil (paket data) dipandu secara real-time. Jika jalan di depan macet atau jembatan putus (origin down), sistem navigasi langsung membelokkan setir Anda ke jalan layang alternatif tercepat (failover pool) dan memilih jalan tikus beraspal mulus tanpa lampu merah (Argo Smart Backbone) dalam hitungan detik.

#### Arsitektur Failover Multi-Region & Dynamic Steering
```
                                 [ Internet Client ]
                                          │
                   ───────────────────────────────────────────────
                   Anycast IP Edge: 104.16.x.x / 2606:4700::
                   ───────────────────────────────────────────────
                                          │
                         ┌────────────────┴────────────────┐
                         ▼                                 ▼
                 [ PoP Singapore ]                 [ PoP Frankfurt ]
                         │                                 │
            ┌────────────┴────────────┐                    │
            │ Dynamic Steering Probe  │                    │
            │ Evaluasi RTT Origin     │                    │
            └────────────┬────────────┘                    │
                         │                                 │
       ┌─────────────────┴─────────────────┐               │
(RTT = 15ms)                          (RTT = 180ms)        │
       ▼                                   ▼               ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│ Primary Pool: apse-origin │         │ Failover Pool: eu-origin  │
│  - Origin 1 (Jakarta)     │         │  - Origin 1 (Frankfurt)   │
│  - Origin 2 (Singapore)   │         │  - Origin 2 (Amsterdam)   │
│ Status: HEALTHY           │         │ Status: STANDBY / HEALTHY │
└───────────────────────────┘         └───────────────────────────┘
       │                                                   ▲
       │ (Jika apse-origin DROP > 50% Healthy threshold)   │
       └──────────────── Failover Instan ──────────────────┘
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi deklaratif level produksi menggunakan **Terraform (Cloudflare Provider v4.x/v5.x standard syntax)** untuk mengonfigurasi multi-region active-active pools, health monitor berbasis HTTP response body verification, session affinity, dan dynamic traffic steering.

```hcl
# main.tf

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
  description = "Cloudflare Zone ID"
}

variable "domain_name" {
  type        = string
  default     = "api.enterprise-arch.internal"
  description = "Hostname FQDN untuk Load Balancer"
}

# 1. Health Monitor L7
# Melakukan deep probe dengan interval 30s ke path /healthz, memvalidasi return code 200 dan JSON payload
resource "cloudflare_load_balancer_monitor" "api_health_monitor" {
  account_id     = var.account_id
  type           = "http"
  expected_codes = "200"
  method         = "GET"
  path           = "/healthz"
  interval       = 15
  timeout        = 5
  retries        = 2
  description    = "Health check monitor L7 untuk API enterprise service"
  
  header {
    header = "Host"
    values = [var.domain_name]
  }
  header {
    header = "X-Probe-Source"
    values = ["Cloudflare-Edge-Healthcheck"]
  }

  expected_body        = "{\"status\":\"healthy\"}"
  follow_redirects     = false
  allow_insecure       = false
  probe_zone           = "" # Global distributed probing
}

# 2. Origin Pools (Asia-Pacific Primary & Europe Secondary)
resource "cloudflare_load_balancer_pool" "pool_apac" {
  account_id = var.account_id
  name       = "pool-apac-production"
  monitor    = cloudflare_load_balancer_monitor.api_health_monitor.id
  enabled    = true
  minimum_origins = 1

  origins {
    name    = "origin-jkt-01"
    address = "103.150.x.10"
    enabled = true
    weight  = 0.6
  }

  origins {
    name    = "origin-sgp-01"
    address = "139.180.x.20"
    enabled = true
    weight  = 0.4
  }

  latitude  = -6.2088
  longitude = 106.8456
  
  notification_email = "sre-alerts@enterprise-arch.internal"
}

resource "cloudflare_load_balancer_pool" "pool_eu" {
  account_id = var.account_id
  name       = "pool-eu-production"
  monitor    = cloudflare_load_balancer_monitor.api_health_monitor.id
  enabled    = true
  minimum_origins = 1

  origins {
    name    = "origin-fra-01"
    address = "159.69.x.30"
    enabled = true
    weight  = 1.0
  }

  latitude  = 50.1109
  longitude = 8.6821

  notification_email = "sre-alerts@enterprise-arch.internal"
}

# 3. Global Load Balancer Resource
resource "cloudflare_load_balancer" "enterprise_lb" {
  zone_id          = var.zone_id
  name             = var.domain_name
  fallback_pool_id = cloudflare_load_balancer_pool.pool_apac.id
  default_pool_ids = [
    cloudflare_load_balancer_pool.pool_apac.id,
    cloudflare_load_balancer_pool.pool_eu.id
  ]
  description      = "Global Load Balancer dengan Dynamic RTT Steering dan Session Affinity"
  proxied          = true
  
  # Dynamic Steering mengarahkan traffic ke pool dengan response time (RTT) terendah
  steering_policy  = "dynamic_latency"

  # Konfigurasi Session Affinity L7 (Cookie-based)
  session_affinity = "cookie"
  session_affinity_ttl = 1800 # 30 menit
  session_affinity_attributes = {
    samesite = "Auto"
    secure   = "Always"
    zero_downtime_failover = "sticky"
  }

  # Region Pool Steering Override (Opsional: Memaksa Region Oseania & Asia ke pool APAC)
  region_pools {
    region   = "WNAM"
    pool_ids = [cloudflare_load_balancer_pool.pool_eu.id]
  }
  region_pools {
    region   = "SEAS"
    pool_ids = [cloudflare_load_balancer_pool.pool_apac.id]
  }

  rules {
    name      = "Path Routing to EU for Compliance Reports"
    condition = "http.request.uri.path contains \"/compliance/\""
    fixed_response = {
      message_body = "Forbidden by Regional Policy"
      status_code  = 403
      content_type = "text/plain"
    }
    priority  = 1
    disabled  = false
  }
}

# 4. Mengaktifkan Argo Smart Routing & Tiered Caching via Zone Settings
resource "cloudflare_argo" "argo_routing" {
  zone_id        = var.zone_id
  smart_routing  = "on"
  tiered_caching = "on"
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: E-Commerce Mega Flash Sale & Database Replication Lag Mitigation
- **Skala**: 120.000 Request Per Second (RPS) puncak, database cluster multi-region (Aurora Global Database: Primary di Singapura, Read Replica di Jakarta dan Tokyo).
- **Permasalahan**: 
  1. *Flash Sale* menghasilkan *read/write split traffic*. Jika traffic diarahkan purely round-robin atau raw dynamic steering, query read yang langsung mengikuti write sering kali mengalami *stale data* akibat replication lag antar-region sebesar 80–200ms.
  2. Ketika ISP Tier-1 di Indonesia mengalami fiber cut di kabel bawah laut Jawa-Singapura, RTT melonjak dari 18ms menjadi 160ms dengan packet loss 8%, menyebabkan timeouts di tingkat aplikasi mobile client.
- **Solusi Arsitektur**:
  1. **Dual Hostname Steering Architecture**:
     - Hostname `checkout.api.com` menggunakan **Session Affinity (Cookie-based) + Sticky Failover**, dipasangi steering policy *Proximity*, memaksa transaksi selalu berada di region Singapura tempat DB Writer berada.
     - Hostname `catalog.api.com` dikonfigurasi dengan **Dynamic Latency Steering** yang terdistribusi ke ketiga region (Singapura, Jakarta, Tokyo) dengan probe `/healthz` yang menyertakan pengecekan status metrik lag database lokal.
  2. **Aktivasi Argo Smart Routing**:
     - Saat terjadi degradasi kabel bawah laut Jawa-Singapura, Argo Smart Routing secara otomatis mengalihkan 65% request via Cloudflare transit PoP di Perth/Hong Kong melalui internal direct leased lines Cloudflare yang tidak terdampak fiber cut, menjaga packet loss tetap 0.1% dan latensi rata-rata stabil di bawah 45ms.
- **Hasil**: Zero-downtime selama 4 jam flash sale, zero customer complaints akibat stale checkout, dan 38% reduksi TTFB global.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Konsekuensi Negatif | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **Dynamic Latency Steering** | Menghantarkan user ke pool dengan latensi terendah secara adaptif terhadap variasi routing ISP. | Beban komputasi analitik probe edge lebih tinggi; rawan *traffic oscillation* jika latency gap antar-origin sangat tipis (<5ms). | API publik global, gaming services, situs berita. |
| **Geo / Regional Steering** | Menjamin kedaulatan data (GDPR/data residency) dan deterministik dalam prediksi pembebanan server. | Kurang adaptif jika seluruh ISP di sebuah negara mengalami degradasi ke origin lokal padahal origin lintas batas lebih optimal. | Sektor perbankan, kepatuhan finansial, sistem healthcare. |
| **Session Affinity (Sticky Cookie)** | Mencegah inkonsistensi cache lokal pada stateful app; meminimalkan auth cache miss di origin. | *Traffic Skew*: Beban server bisa menjadi tidak seimbang jika ada pengguna enterprise (misal: proxy kantor besar) dengan volume traffic masif. | Transaksi perbankan, sesi e-commerce checkout. |
| **Argo Smart Routing** | Reduksi latensi signifikan (20-40%), pemulihan rute instan saat BGP internet publik kolaps. | Penambahan biaya operasional per gigabyte bandwidth egress yang melewati jalur Argo. | Aplikasi misi kritis, sistem transaksi real-time, high-value conversion funnel. |
| **Aggressive Health Checks (Interval 5s)** | Failover super cepat (<10s) saat origin crash. | Ribuan PoP edge mengirim probe kontinu; dapat membebani CPU origin web server jika tidak dioptimalkan. | Sistem mission-critical dengan origin berkapasitas compute tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Split-Brain Health Checking & Flapping
- **Gejala**: Origin pool status bergonta-ganti antara Healthy dan Unhealthy setiap beberapa menit (*flapping*), menyebabkan cache purge atau hilangnya session affinity.
- **Penyebab**: Probe interval terlalu pendek (5s) dengan threshold retry 1, sementara origin memiliki background garbage collection (GC) pause periodik atau rate limiter edge yang memblokir probe IP Cloudflare sendiri.
- **Solusi**: Atur `retries` ke minimal 2 atau 3, naikkan `timeout` ke 3-5 detik, dan pastikan IP Range Cloudflare di-*allowlist* sepenuhnya pada firewall lokal origin tanpa limitasi HTTP 429.

#### 2. Session Affinity Broken by Client Cookie Dropping
- **Gejala**: Pengguna mobile app terus-menerus terlempar antar datacenter Jakarta dan Singapura saat login.
- **Penyebab**: Mobile application developer menggunakan HTTP client library yang mengabaikan header `Set-Cookie`, atau atribut cookie `SameSite=Strict` terblokir pada webview embed cross-origin.
- **Solusi**: Gunakan `SameSite=None; Secure` jika aplikasi memanggil API lintas domain, atau beralih ke Header-based affinity jika didukung, serta audit log mobile network client.

#### 3. Diagnostik CFLB dan Argo Menggunakan Edge Headers
Gunakan `curl` dengan flag verbose untuk membedah decision path Cloudflare:
```bash
curl -svo /dev/null https://api.enterprise-arch.internal/v1/healthz \
  -H "Cache-Control: no-cache" \
  --connect-to api.enterprise-arch.internal:443:104.16.80.1:443
```
Periksa header respons krusial:
- `cf-ray`: Mengidentifikasi PoP edge penerima (misal: `867a123bc45d-SIN` berarti Edge Singapore).
- `cf-cache-status`: Menunjukkan `DYNAMIC` (menandakan L7 LB memproses bypass cache).
- `cf-bgj`: Memberikan informasi pemrosesan background Argo atau Tiered Cache (`img`, `minify`, atau jalur internal routing).
- `cf-load-balancer`: Menampilkan nama pool atau ID yang melayani request (hanya terlihat jika diaktifkan pada log enterprise atau enterprise debug mode).

---

### 11. Best Practices (Production Checklist)

- [ ] **Probe Isolation**: Sediakan endpoint `/healthz` khusus yang ringan. Hindari query DB berat di setiap probe, tetapi pastikan probe memvalidasi konektivitas dasar thread pool dan memory.
- [ ] **Payload Sanitization**: Monitor wajib memeriksa `expected_body` (misal JSON `{"status":"ok"}`), bukan hanya status 200, guna mencegah skenario server origin me-return custom error page 200 (soft-404/maintenance).
- [ ] **Failover Pool (Fallback)**: Konfigurasikan fallback pool yang selalu siaga (misal static disaster recovery bucket di R2 atau S3) jika seluruh origin utama mati.
- [ ] **Connection Keep-Alive Optimization**: Set `keep-alive` timeout di web server origin (Nginx/Envoy) minimal 65-75 detik agar tidak memutus pooling connection Pingora secara prematur.
- [ ] **Mutual TLS (mTLS) / Authenticated Origin Pulls**: Pasang sertifikat mTLS antara Cloudflare Edge dan Origin untuk memastikan traffic load balancing tidak disadap atau di-*spoofing* oleh penyerang yang mengetahui direct IP origin.
- [ ] **Argo Tiered Caching Region Alignment**: Pastikan region upper-tier cache berada dekat secara geografis dan jaringan dengan pool primary origin database.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum berikut di dalam folder: `hands-on/m02/`

#### Langkah 1: Persiapan Environment
Pastikan Terraform terinstal dan siapkan token API Cloudflare dengan permission `Zone.Load Balancing: Edit` dan `Zone.Zone Settings: Edit`.

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
export CLOUDFLARE_API_TOKEN="your-api-token-here"
```

#### Langkah 2: Buat Mock Origin Menggunakan Nginx Lokal / Cloud Instance
Jalankan dua instance HTTP server sederhana (bisa menggunakan Docker) untuk mensimulasikan dua origin server:

```bash
# Terminal 1 - Origin Jakarta Mock
docker run -d --name origin-jkt -p 8081:80 nginx:alpine
docker exec -i origin-jkt sh -c 'echo "{\"status\":\"healthy\",\"origin\":\"jakarta\"}" > /usr/share/nginx/html/healthz'

# Terminal 2 - Origin Singapore Mock
docker run -d --name origin-sgp -p 8082:80 nginx:alpine
docker exec -i origin-sgp sh -c 'echo "{\"status\":\"healthy\",\"origin\":\"singapore\"}" > /usr/share/nginx/html/healthz'
```

#### Langkah 3: Konfigurasi Terraform
Tuliskan file `hands-on/m02/load_balancer.tf`:

```hcl
variable "account_id" {
  type    = string
  default = "YOUR_ACCOUNT_ID"
}

variable "zone_id" {
  type    = string
  default = "YOUR_ZONE_ID"
}

variable "domain_test" {
  type    = string
  default = "cflb-test.yourdomain.com"
}

resource "cloudflare_load_balancer_monitor" "http_monitor" {
  account_id     = var.account_id
  type           = "http"
  expected_codes = "200"
  method         = "GET"
  path           = "/healthz"
  interval       = 30
  timeout        = 5
  retries        = 2
  expected_body  = "healthy"
}

resource "cloudflare_load_balancer_pool" "pool_primary" {
  account_id = var.account_id
  name       = "primary-mock-pool"
  monitor    = cloudflare_load_balancer_monitor.http_monitor.id

  origins {
    name    = "mock-origin-01"
    address = "203.0.113.10" # Ganti dengan Public IP/Tunnel Anda
    enabled = true
    weight  = 0.5
  }

  origins {
    name    = "mock-origin-02"
    address = "203.0.113.20" # Ganti dengan Public IP/Tunnel Anda
    enabled = true
    weight  = 0.5
  }
}

resource "cloudflare_load_balancer" "lb_demo" {
  zone_id          = var.zone_id
  name             = var.domain_test
  fallback_pool_id = cloudflare_load_balancer_pool.pool_primary.id
  default_pool_ids = [cloudflare_load_balancer_pool.pool_primary.id]
  proxied          = true
  steering_policy  = "dynamic_latency"

  session_affinity = "cookie"
  session_affinity_ttl = 1200
}
```

#### Langkah 4: Deployment & Validasi
Jalankan deployment Terraform dan uji perilakunya:

```bash
terraform init
terraform plan
terraform apply -auto-approve

# Validasi traffic routing & Affinity Cookie
curl -I https://cflb-test.yourdomain.com/healthz

# Uji failover simulasi: Matikan mock service primary
docker stop origin-jkt
# Lakukan query looping untuk melihat transisi traffic dalam hitungan detik
for i in {1..20}; do curl -s https://cflb-test.yourdomain.com/healthz; echo ""; sleep 2; done
```

---

### 13. Exercise

#### Level: Easy
Konfigurasikan sebuah monitor Cloudflare LB bertipe `tcp` yang memeriksa port 443 pada dua origin server berbeda dengan interval pengecekan 60 detik. Tuliskan blok resource Terraform-nya.

#### Level: Medium
Buat arsitektur Load Balancer yang memiliki dua origin pool: `pool-indonesia` dan `pool-global`. Gunakan Cloudflare Terraform provider untuk mengonfigurasi **Geo Steering Rules** di mana seluruh user dari benua Asia (`OC`, `AS`) diarahkan ke `pool-indonesia`, sedangkan seluruh benua lain diarahkan ke `pool-global`. Jika `pool-indonesia` gagal memenuhi batas minimal origin sehat (`minimum_origins = 1`), sistem harus otomatis mengalihkan traffic Asia ke `pool-global`.

#### Level: Hard
Tuliskan konfigurasi Cloudflare Load Balancer Custom Rule menggunakan ekspresi HTTP Request (Ruleset Engine) yang menerapkan arsitektur *Canary Release*:
- Arahkan request yang memiliki HTTP Header `X-Canary-Release: NextGen` ke pool khusus bernama `pool-canary-experimental`.
- Sediakan fallback transparan jika pool canary mati tanpa mengganggu regular pool.
- Pastikan Session Affinity dipertahankan pada canary user pool tersebut menggunakan cookie terenkripsi dengan atribut `SameSite=None`.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Infrastructure Architect untuk lembaga kliring keuangan internasional. Sistem memproses transaksi REST API dengan SLA ketersediaan 99.999% (latensi sub-100ms global). Sistem memiliki 3 Datacenter:
- DC-1: Jakarta (On-Premise Bare-Metal)
- DC-2: Singapura (AWS Region `ap-southeast-1`)
- DC-3: Frankfurt (GCP Region `europe-west3`)

**Batasan & Regulasi**:
1. Seluruh transaksi dari IP Indonesia **wajib** diproses di DC-1 Jakarta karena undang-undang residensi data finansial, *kecuali* jika DC-1 down total.
2. Jika DC-1 down total, traffic Indonesia hanya boleh dialihkan ke DC-2 Singapura (tidak boleh ke Frankfurt karena faktor hukum dan latensi).
3. Traffic non-Indonesia harus menggunakan Dynamic Latency Steering antara Singapura dan Frankfurt.
4. Latensi koneksi antar origin sangat rentan terhadap BGP peering flaps internet publik.

**Instruksi Penugasan**:
Rancang arsitektur menyeluruh:
- Buat diagram arsitektur lengkap beserta skema alur failover state.
- Tuliskan file konfigurasi Terraform Cloudflare yang mendefinisikan Pools, Steering Policies, Fallback Pools, Custom Rules, Health Monitors, serta konfigurasi Argo Smart Routing.
- Dokumentasikan skenario disaster recovery saat kabel laut Jakarta-Singapura putus total. Sertakan matriks risiko terkait enkripsi payload dan kepatuhan kedaulatan data.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa Cloudflare Load Balancing mampu melakukan failover lebih cepat dibandingkan failover berbasis Dynamic DNS konvensional?
2. Komponen engine software apa di Cloudflare yang menggantikan Nginx dan bertanggung jawab menangani koneksi masuk serta routing L7?
3. Apa fungsi dari atribut `proxied = true` pada resource DNS atau Load Balancer di Cloudflare?
4. Manakah steering policy yang mendasarkan rutenya pada pengukuran Round Trip Time (RTT) pool secara real-time dari edge PoP?
5. Mengapa health check monitor L7 Cloudflare memerlukan konfigurasi `expected_codes` dan `expected_body` secara bersamaan?

#### B. Pertanyaan Intermediate
6. Bagaimana cara Argo Smart Routing menentukan bahwa paket HTTP harus dikirimkan melalui Edge Transit Cloudflare alih-alih langsung melalui internet publik?
7. Apa risiko teknis mengaktifkan Session Affinity L7 (Cookie-based) pada aplikasi yang mayoritas penggunanya mengakses dari satu IP proxy gateway kantor besar (NAT)?
8. Bagaimana Cloudflare Load Balancing mencegah *false positive* saat suatu Edge PoP mengalami masalah jaringan lokal ke origin, padahal origin server sebenarnya dalam kondisi prima?
9. Apa perbedaan esensial antara *Proximity Steering* dan *Dynamic Steering* pada Cloudflare LB?
10. Pada kondisi apa Argo Tiered Caching dapat menurunkan biaya egress cloud provider secara drastis?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim SRE mendapati bahwa setelah mengaktifkan Dynamic Latency Steering, server origin di region US menerima 70% traffic dari user Eropa selama 10 menit setiap harinya pada jam 03.00 UTC. Analisis apa yang perlu dilakukan untuk menemukan akar masalah?
12. **Skenario 2**: API checkout Anda mengalami loop redirection HTTP 521 atau HTTP 522 secara berkala saat failover dieksekusi dari Primary Pool ke Disaster Recovery Pool. Investigasi langkah-demi-langkah apa yang harus dilakukan di level header dan origin configuration?
13. **Skenario 3**: Anda ingin menguji zero-downtime deployment pool baru tanpa memindahkan production traffic user sebenarnya. Bagaimana cara memanfaatkan Cloudflare Custom LB Rules dan Health Checks untuk melakukan pengujian end-to-end secara aman di production edge?

---

### 16. Summary

- **Global Anycast Foundation**: Cloudflare Load Balancing bekerja di atas Anycast L3/L4, mengeliminasi ketergantungan pada DNS TTL cache browser/ISP dan memungkinkan pengalihan L7 instan.
- **L7 Steering Versatility**: Melalui engine Pingora, load balancing dapat dikendalikan tidak hanya secara round-robin, melainkan melalui analitik latensi riil (*Dynamic Latency*), Geolocation, GPS Proximity, dan manipulasi L7 ruleset (Path, Header, Cookie).
- **Argo Smart Routing Superiority**: Argo mendeteksi kemacetan internet publik secara real-time dan mengarahkan paket melalui jalur privat berkinerja tinggi pada jaringan global Cloudflare, mereduksi packet loss dan TTFB secara dramatis.
- **Failover Precision**: Penggunaan monitor probe terdistribusi dari multi-PoP global mencegah *false failover*, sekaligus menjamin pemulihan cepat ketika backend origin mengalami degradasi perangkat keras atau jaringan lokal.
- **Enterprise Readiness**: Arsitektur produksi mensyaratkan otomatisasi via IaC (Terraform), isolasi endpoint probe, sanitasi body health check, pengamanan jalur via mTLS, serta pemisahan stateful affinity agar aplikasi tetap memiliki ketersediaan tinggi tanpa melanggar kedaulatan data.