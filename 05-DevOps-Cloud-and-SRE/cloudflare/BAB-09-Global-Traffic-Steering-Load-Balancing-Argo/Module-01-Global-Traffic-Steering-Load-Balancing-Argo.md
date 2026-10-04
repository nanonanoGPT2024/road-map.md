# Modul 01: Global Traffic Steering, Load Balancing, & Argo Smart Routing

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan mengonfigurasi Cloudflare Global Load Balancer (GLB) di atas jaringan anycast global Cloudflare.
- Mengonfigurasi Origin Pools dengan bobot (*weights*), batas toleransi kegagalan (*thresholds*), dan fallback architecture.
- Mengimplementasikan Active Health Monitors dengan probe sintetis terdistribusi dari multiple edge colos secara presisi.
- Menguasai perbedaan teknis dan use-case antara Geo-Steering, Dynamic Latency Steering, dan Proximity Steering.
- Mengonfigurasi Session Affinity berbasis cookie/header dengan pemahaman mendalam tentang *drain behavior* saat origin failover.
- Mengoptimalkan transmisi dynamic content dan static caching menggunakan kombinasi Argo Smart Routing dan Argo Tiered Caching.
- Mengotomatisasikan infrastruktur traffic steering multi-cloud menggunakan HashiCorp Terraform Cloudflare Provider v4+.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Konsep dasar Cloudflare DNS, Proxied Mode (Orange Cloud vs Grey Cloud), dan Anycast Routing (BGP).
- Model OSI Layer 4 (TCP/UDP) dan Layer 7 (HTTP/1.1, HTTP/2, HTTP/3, TLS Termination).
- Dasar-dasar HTTP status codes, keep-alive connections, dan mekanisme load balancing standar (Round Robin, Weighted, Least Connections).
- Sintaks dasar Terraform HCL untuk provision cloud infrastructure.

---

## 3. Concept
Cloudflare Global Load Balancing (GLB) beroperasi pada Layer 7 reverse-proxy di lapisan edge Cloudflare (330+ kota di seluruh dunia). Berbeda dengan DNS Load Balancer tradisional yang memiliki kelemahan TTL caching pada ISP/resolver klien, Cloudflare GLB memanfaatkan jaringan Anycast BGP. 

Satu Anycast IP yang sama diiklankan ke seluruh dunia. Request pengguna diarahkan ke Point of Presence (PoP) Cloudflare terdekat secara otomatis oleh routing internet (BGP). Di dalam PoP Cloudflare tersebut, Layer 7 proxy mengevaluasi aturan Load Balancing, status kesehatan Origin Pool, latency round-trip time (RTT), atau lokasi geografis klien untuk meneruskan HTTP/S request ke origin server backend yang paling optimal.

Melengkapi GLB, **Argo Smart Routing** mendeteksi kongesti internet publik secara real-time dan mengarahkan traffic antar-PoP Cloudflare melalui backbone privat Cloudflare yang teroptimasi, menghindari packet loss dan jitter. Sementara itu, **Argo Tiered Caching** menunjuk PoP regional tertentu sebagai "Upper-Tier" cache untuk meminimalkan beban koneksi langsung ke origin server.

---

## 4. Why
Tantangan arsitektur multi-region dan multi-cloud tradisional meliputi:
1. **DNS Caching & Slow Convergence**: DNS round-robin konvensional mengandalkan TTL rendah. ISP resolver sering mengabaikan TTL ini, menyebabkan klien tetap mengirim request ke server yang telah mati (*downtime leakage*).
2. **Sub-optimal Pathing**: Internet publik menggunakan BGP standar yang memilih rute berbasis *Autonomous System (AS) path length*, bukan latency atau packet loss terendah. Akibatnya, traffic antar benua sering melewati link yang padat (*sub-optimal routing*).
3. **Thundering Herd di Origin**: Tanpa arsitektur caching bertingkat, ribuan edge cache server di seluruh dunia akan melakukan *cache miss request* langsung ke origin secara simultan, menumbangkan origin database backend.
4. **Disaster Recovery Otomatis**: Memindahkan ribuan request per detik antar benua secara manual membutuhkan waktu puluhan menit. Cloudflare GLB mengeksekusi failover dalam hitungan detik tanpa modifikasi record DNS klien.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Arsitektur Komponen Cloudflare Load Balancing
Arsitektur GLB terdiri dari empat komponen hierarkis utama:
1. **Load Balancer (Hostname)**: Objek L7 yang dipetakan ke FQDN publik (misal: `api.example.com`). Mengatur steering policy, session affinity, dan aturan fallback.
2. **Pools (Origin Groups)**: Grup logis yang membawahi satu atau lebih origin endpoints (misal: `pool-us-east`, `pool-eu-central`). Memiliki nilai `minimum_origins` yang harus sehat agar pool dinyatakan UP.
3. **Origins**: Alamat target backend aktual (IP publik atau FQDN privat/Cloudflare Tunnel) beserta parameter `weight` (0.00 hingga 1.00) dan port HTTP/HTTPS.
4. **Monitors**: Daemon probe independen yang dikirimkan oleh Edge Colos secara periodik untuk memverifikasi kesehatan origin L7 (status code, response body regex, header checks).

### 5.2 Algoritma Traffic Steering
Cloudflare menyediakan beberapa strategi steering:
- **Off (Standard Failover)**: Traffic selalu dikirim ke Pool prioritas tertinggi (berdasarkan urutan daftar pool). Jika pool 1 jatuh di bawah threshold, traffic beralih ke pool 2.
- **Geo-Steering**: Pemetaan eksplisit berdasarkan Region (misal: WNAM, EEUR, OC) atau Country Code (ISO 3166-1 alpha-2). Request dari klien Indonesia (ID) selalu diarahkan ke Pool SG/Jakarta.
- **Dynamic Latency Steering**: Cloudflare mengukur latency RTT secara berkala dari setiap Edge PoP ke setiap Origin Pool melalui monitor probe. Edge PoP secara dinamis memilih pool dengan RTT terendah untuk PoP tersebut.
- **Proximity Steering**: Mengarahkan traffic ke pool dengan jarak geografis (koordinat GPS origin) terdekat dengan PoP Cloudflare yang menerima request.
- **Random Steering**: Mengalokasikan traffic secara acak berdasarkan persentase weight antar pool (berguna untuk blue/green canary rollout).

### 5.3 Active Health Monitors & Consensus
Cloudflare menjalankan probe dari multiple data center di seluruh dunia.
- **Probe Interval & Timeout**: Interval pengecekan (misal: 10s–60s) dan timeout sebelum request dianggap gagal (misal: 5s).
- **Consecutive Probes**: Butuh sejumlah kegagalan berturut-turut (misal: `consecutive_fails = 3`) untuk menandai origin *Down*, dan sejumlah sukses berturut-turut (misal: `consecutive_success = 2`) untuk memulihkan (*Up*).
- **Simulated Health Probe Isolation**: Probe dikirimkan langsung dari IP Cloudflare ke Origin IP/Tunnel, memverifikasi port asli tanpa melalui CDN cache layer.

### 5.4 Session Affinity
Mekanisme yang memastikan seorang user tetap terhubung ke origin server yang sama selama durasi sesi:
- **Cookie-Based**: Cloudflare menyisipkan cookie bertanda tangan (misal: `__cf_bm` atau custom cookie nama `CFLB`) ke browser klien.
- **Zero-Downtime Drain Behavior**: Ketika origin server masuk status pemeliharaan (*drain mode*), request baru dialihkan ke origin lain, tetapi request yang membawa session cookie lama tetap diizinkan menyelesaikan transaksi sampai TTL expired.
- **Failover Handling**: Jika origin terpilih mati, session affinity otomatis diabaikan, dan request dipindahkan ke healthy origin berikutnya secara transparan tanpa melempar error 502/503 ke user.

### 5.5 Argo Smart Routing & Argo Tiered Caching
- **Argo Smart Routing**: Beroperasi menggunakan algoritma pathfinding berbasis RUM (Real User Measurement) dan synthetic data antar PoP Cloudflare. Paket ditransmisikan melalui internal virtual overlay network milik Cloudflare, memotong jalur transit internet publik yang lambat (menghasilkan rata-rata 30-40% penurunan latency).
- **Argo Tiered Caching**: Membentuk hierarki dua tingkat (*Lower-tier PoP* dan *Upper-tier PoP*). Saat request mengalami cache miss di PoP lokal (Lower-tier), request tidak langsung dilempar ke Origin, melainkan diteruskan ke Hub regional Cloudflare (Upper-tier). Jika Upper-tier memiliki objek tersebut di cache-nya, response dikembalikan ke Lower-tier. Ini mengurangi *Origin Offload load* hingga 80-95%.

---

## 6. How
Implementasi traffic management Cloudflare dilakukan secara bertahap:
1. Mendefinisikan **Health Monitor** L7 spesifik (endpoint `/healthz`, expect status 200, string verifikasi `"status": "healthy"`).
2. Membentuk **Origin Pools** regional (misal: `ap-southeast` dan `us-east`), melampirkan Health Monitor yang sudah dibuat, dan menetapkan `minimum_origins = 1`.
3. Menetapkan pool fallback darurat (`pool-static-maintenance` atau static error response) yang selalu aktif jika semua pool utama down.
4. Mengonfigurasi objek **Load Balancer** dengan policy `dynamic_latency` atau `geo`, melampirkan Session Affinity cookie, serta mengaktifkan fallback pool.
5. Mengaktifkan **Argo Smart Routing** dan **Tiered Caching** pada level zone/domain untuk optimasi transport layer.

---

## 7. Analogy
Bayangkan sebuah maskapai penerbangan internasional:
- **Anycast BGP** adalah bandara terdekat dari rumah penumpang: setiap penumpang di seluruh dunia menuju ke bandara terdekat mereka (Cloudflare PoP).
- **Global Load Balancer** adalah staf pengatur penerbangan (Air Traffic Controller) di bandara tersebut. Mereka memeriksa kondisi cuaca dan ketersediaan landasan di destinasi (Health Checks).
- **Geo / Latency Steering**: ATC memutuskan: penumpang yang ingin ke Asia Tenggara diberangkatkan ke Hub Changi (Geo), atau jika jalur Tokyo lebih lowong dan cepat, dikirim via Tokyo (Dynamic Latency).
- **Session Affinity**: Setiap penumpang diberi boarding pass dengan nomor bagasi unik. Seluruh bagasi transit dipastikan selalu dimuat ke pesawat yang sama dengan penumpangnya sampai tiba di tujuan akhir.
- **Argo Smart Routing**: Alih-alih terbang di jalur udara umum yang macet karena badai, maskapai memiliki koridor udara privat bebas hambatan (*dedicated flight corridor*) antar bandara transit.

---

## 8. Diagram (ASCII)

```
[ Klien di Jakarta ]           [ Klien di London ]
         │                              │
         ▼ (Anycast BGP)                ▼ (Anycast BGP)
┌──────────────────┐           ┌──────────────────┐
│ Cloudflare Edge  │           │ Cloudflare Edge  │
│   PoP (CGK)      │           │   PoP (LHR)      │
└────────┬─────────┘           └────────┬─────────┘
         │                              │
         ├────── Argo Smart Routing ────┤ (Overlay Backbone)
         │                              │
         ▼                              ▼
┌────────────────────────────────────────────────────────┐
│             Cloudflare Load Balancer Logic             │
│   (Evaluasi Session Cookie -> Dynamic Latency / Geo)   │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
        (Latency: 15ms)            (Latency: 180ms)
               │                          │
               ▼                          ▼
    ┌──────────────────────┐   ┌──────────────────────┐
    │  Pool AP-Southeast   │   │     Pool EU-West     │
    │  (Healthy: 2/2)      │   │     (Healthy: 2/2)   │
    │                      │   │                      │
    │  ┌────────────────┐  │   │  ┌────────────────┐  │
    │  │ Origin SG-01   │  │   │  │ Origin LON-01  │  │
    │  └────────────────┘  │   │  └────────────────┘  │
    │  ┌────────────────┐  │   │  ┌────────────────┐  │
    │  │ Origin JKT-01  │  │   │  │ Origin LON-02  │  │
    │  └────────────────┘  │   │  └────────────────┘  │
    └──────────────────────┘   └──────────────────────┘
               ▲                          ▲
               │                          │
         [Health Check]             [Health Check]
      (Probe dari SG, US, EU)    (Probe dari SG, US, EU)
```

---

## 9. Simple Example
Mengaktifkan Argo Smart Routing dan Tiered Caching menggunakan Cloudflare API via `curl`:

```bash
# 1. Enable Argo Smart Routing pada Zone
curl -X PATCH "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/argo/smart_routing" \
     -H "Authorization: Bearer <API_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"value": "on"}'

# 2. Enable Tiered Caching (Topology: Generic Smart Tiered Caching)
curl -X PATCH "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/cache/tiered_cache_smart_topology_enable" \
     -H "Authorization: Bearer <API_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"value": "on"}'
```

---

## 10. Practical Example (Terraform HCL)
Berikut adalah konfigurasi Terraform production-grade yang menerapkan Health Monitor, Dua Pool Regional (Asia & US), Fallback Pool, Session Affinity, dan Dynamic Steering.

```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "Cloudflare Target Zone ID"
}

# 1. Health Monitor L7
resource "cloudflare_load_balancer_monitor" "api_monitor" {
  account_id     = var.zone_id
  type           = "http"
  path           = "/healthz"
  method         = "GET"
  port           = 443
  expected_codes = "2xx"
  expected_body  = "{\"status\":\"UP\"}"
  interval       = 15
  timeout        = 5
  retries        = 2
  probe_zone     = "" # Probe dari seluruh region Cloudflare
  follow_redirects = false
  allow_insecure   = false

  header {
    header = "User-Agent"
    values = ["Cloudflare-HealthCheck-Monitor/1.0"]
  }
}

# 2. Origin Pool: AP-Southeast (Singapore & Jakarta)
resource "cloudflare_load_balancer_pool" "pool_ap_southeast" {
  account_id         = var.zone_id
  name               = "pool-ap-southeast"
  monitor            = cloudflare_load_balancer_monitor.api_monitor.id
  minimum_origins    = 1
  check_regions      = ["SEAS", "EA"]

  origins {
    name    = "origin-sin-01"
    address = "192.0.2.10"
    enabled = true
    weight  = 0.6
  }

  origins {
    name    = "origin-jkt-01"
    address = "192.0.2.11"
    enabled = true
    weight  = 0.4
  }
}

# 3. Origin Pool: US-East (Virginia)
resource "cloudflare_load_balancer_pool" "pool_us_east" {
  account_id         = var.zone_id
  name               = "pool-us-east"
  monitor            = cloudflare_load_balancer_monitor.api_monitor.id
  minimum_origins    = 1
  check_regions      = ["ENAM", "WNAM"]

  origins {
    name    = "origin-iad-01"
    address = "198.51.100.10"
    enabled = true
    weight  = 1.0
  }
}

# 4. Fallback Pool (Maintenance Static Page Origin)
resource "cloudflare_load_balancer_pool" "pool_fallback" {
  account_id      = var.zone_id
  name            = "pool-fallback-static"
  minimum_origins = 1

  origins {
    name    = "origin-static-s3"
    address = "maintenance-failover.storage.example.com"
    enabled = true
    weight  = 1.0
  }
}

# 5. Global Load Balancer Resource
resource "cloudflare_load_balancer" "global_api_lb" {
  zone_id          = var.zone_id
  name             = "api.example.com"
  fallback_pool_id = cloudflare_load_balancer_pool.pool_fallback.id
  default_pool_ids = [
    cloudflare_load_balancer_pool.pool_ap_southeast.id,
    cloudflare_load_balancer_pool.pool_us_east.id
  ]
  description      = "Global LB with Dynamic Latency Steering and Cookie Affinity"
  proxied          = true
  steering_policy  = "dynamic_latency"

  # Session Affinity
  session_affinity     = "cookie"
  session_affinity_ttl = 3600
  session_affinity_attributes {
    samesite = "Lax"
    secure   = "Always"
    drain_duration = 300
  }

  # Geo Steering Fallback Mapping (Overrides for specific regions)
  country_pools {
    country = "ID"
    pool_ids = [cloudflare_load_balancer_pool.pool_ap_southeast.id]
  }

  country_pools {
    country = "US"
    pool_ids = [cloudflare_load_balancer_pool.pool_us_east.id]
  }

  rules {
    name      = "Route Mobile API to AP"
    condition = "http.request.uri.path contains \"/v1/mobile\""
    overrides {
      session_affinity = "none"
      default_pool_ids = [cloudflare_load_balancer_pool.pool_ap_southeast.id]
    }
  }
}

# 6. Argo Smart Routing & Tiered Caching Settings
resource "cloudflare_argo" "argo_settings" {
  zone_id        = var.zone_id
  smart_routing  = "on"
  tiered_caching = "on"
}
```

---

## 11. Real World Example
Sebuah platform E-Commerce Multi-Regional (Asia dan Amerika Utara) sering mengalami *cart drops* ketika server US mengalami lonjakan traffic saat event Black Friday. 
- **Implementasi**: Perusahaan mengonfigurasi Cloudflare GLB dengan `dynamic_latency` steering, cookie-based session affinity (`drain_duration = 300`), dan health check interval 10 detik.
- **Skenario Insiden**: Instance database di US mengalami degradasi parsial sehingga endpoint `/healthz` di pool US me-return HTTP 500.
- **Dampak Penanganan**: Dalam tempo 20 detik (2 interval x 10s), Cloudflare secara otomatis mengalihkan request baru pengguna pantai barat Amerika ke Pool Asia Tenggara atau instance cadangan terdekat tanpa terjadi downtime (0 HTTP 502 dilempar ke pengguna). Pengguna yang sedang dalam alur checkout aktif tetap dihabiskan transaksinya via session drain hingga tuntas.

---

## 12. Trade-offs

| Pendekatan / Fitur | Kelebihan | Biaya / Limitasi / Kekurangan |
| :--- | :--- | :--- |
| **Dynamic Latency Steering** | Mengoptimalkan RTT secara adaptif terhadap degradasi rute ISP global | Membutuhkan monitor probe terus-menerus; biaya billing bertambah seiring jumlah pool & interval probe. |
| **Geo-Steering** | Kepatuhan data sovereignty (GDPR, POJK) dan latensi deterministik berbasis negara | Tidak memperhitungkan beban CPU origin atau ISP undersea cable cut yang mempengaruhi latency. |
| **Session Affinity** | Menjaga stateful server / shopping cart yang belum terpusat di Redis | Dapat menyebabkan ketidakseimbangan beban (*pool hotspot*) jika ada heavy user di balik Mega-Proxy / NAT. |
| **Argo Smart Routing** | Menurunkan TTFB dynamic API hingga 30-40% via Cloudflare private backbone | Biaya operasional berbasis volume transfer data ($0.10/GB egress traffic). |

---

## 13. When To Use
- Aplikasi yang beroperasi di arsitektur multi-region atau multi-cloud (misal: AWS Jakarta + GCP Singapore + On-Premise DC).
- Sistem kritis yang mewajibkan zero-downtime automated disaster recovery.
- Aplikasi API global dengan payload dinamis (non-cacheable) yang membutuhkan response time cepat via Argo Smart Routing.
- Arsitektur berbasis read-heavy microservices yang membutuhkan pengurangan egress cost origin menggunakan Tiered Caching.

---

## 14. When NOT To Use
- Single-region monolithic architecture dengan budget minimal (gunakan Cloudflare DNS standar proxied mode secara gratis).
- Traffic murni non-HTTP/S Layer 4 yang tidak menggunakan Cloudflare Spectrum (Cloudflare GLB default beroperasi pada L7 HTTP/HTTPS).
- Sistem stateful yang membutuhkan direct persistent TCP socket murni tanpa reverse proxy buffer (misal: real-time low latency video stream RTSP mentah).

---

## 15. Common Mistakes
1. **Health Check Terhalang Firewall Origin**: Lupa melakukan whitelist IP range Cloudflare di Security Group / iptables origin backend, menyebabkan monitor menganggap origin *Down* padahal origin sehat.
2. **False Positive Threshold yang Terlalu Agresif**: Menetapkan timeout probe terlalu pendek (misal: 1 detik dengan `consecutive_fails = 1`) di jaringan publik, memicu failover *flapping* setiap kali terjadi transient network hiccup.
3. **Session Affinity Mengabaikan CDN Cache**: Mengaktifkan Session Affinity pada static assets yang di-cache, menyebabkan Cloudflare Bypass Cache secara tidak disengaja jika tidak dipisahkan path routing-nya.
4. **Fallback Pool Tidak Didefinisikan**: Mengandalkan pool default tanpa fallback pool statis; ketika seluruh pool regional kolaps bersamaan, Cloudflare melempar raw Error 521/523 alih-alih maintenance page yang informatif.

---

## 16. Best Practices
1. **Endpoint Health Check Ringan**: Pastikan `/healthz` tidak menjalankan query SQL `SELECT *` yang berat. Jalankan query `SELECT 1` atau pemeriksaan shallow memory untuk menghindari monitor menenggelamkan database origin.
2. **Dedicated Fallback Pool**: Selalu definisikan Fallback Pool yang mengarah ke Object Storage statis (misal: Cloudflare R2 atau AWS S3) yang menyajikan response JSON maintenance error terstandar.
3. **Monitor dari Multiple Regions**: Selalu konfigurasi monitor untuk memeriksa dari minimal 3 region (`check_regions = ["WEU", "ENAM", "SEAS"]`) guna menghindari kegagalan lokal satu region Cloudflare memicu false-alarm.
4. **Optimalkan Tiered Caching Sebelum Scale Origin**: Aktifkan Argo Tiered Caching untuk menyerap hingga 90% traffic statis/semi-dinamis pada tier Cloudflare sebelum memutuskan menambah node backend origin.

---

## 17. Troubleshooting

### Kasus: Origin Berstatus "Unhealthy" Padahal Server Aktif
- **Identifikasi**: Jalankan `curl` langsung ke origin dari luar Cloudflare:
  ```bash
  curl -Iv -H "Host: api.example.com" https://<ORIGIN_IP>/healthz --resolve api.example.com:443:<ORIGIN_IP>
  ```
- **Inspeksi Status Code & Body**: Periksa apakah ada redirect (HTTP 301/302). Cloudflare Health Check secara default **tidak** mengikuti redirect kecuali diizinkan (`follow_redirects = true`).
- **Verifikasi TLS Handshake**: Jika origin menggunakan self-signed cert di staging, pastikan `allow_insecure = true` pada monitor atau pasang Cloudflare Origin CA Certificate yang valid.

### Kasus: Pool Flapping (Up dan Down Berulang-ulang)
- **Analisis Root Cause**: Probe interval terlalu cepat dan origin mengalami spike CPU load akibat konkurensi probe dari ratusan Edge Colos.
- **Solusi**: Atur `probe_zone` ke region origin terdekat saja atau naikkan `interval` ke 30-60 detik dengan `consecutive_fails = 3`.

---

## 18. Exercise
1. Tuliskan skrip Terraform untuk membuat Health Check monitor yang mengirimkan probe HTTP POST membawa payload JSON `{"ping": true}` dan memverifikasi HTTP 200 OK.
2. Buat simulasi routing rule yang mengecualikan traffic `/internal/*` agar tidak melewati Geo-Steering melainkan dipaksa ke pool On-Premises.
3. Uji Session Affinity menggunakan `curl` dengan mengekstrak cookie `CFLB` dan mengirimkan kembali request berikutnya menggunakan opsi `-b`.

---

## 19. Challenge
Rancang arsitektur High-Availability Disaster Recovery Global untuk platform finansial:
- Memiliki 2 Origin Aktif: AWS Jakarta (Region Utama) dan GCP Singapura (Region Sekunder).
- Memiliki 1 Origin Fallback: Static Maintenance di Cloudflare Pages.
- Kriteria Failover: Jika latency AWS Jakarta > 150ms selama 1 menit atau tingkat kegagalan HTTP > 5%, alihkan 70% traffic ke GCP Singapura secara dinamis tanpa memutuskan user yang sedang login di AWS Jakarta (gunakan Session Drain).
- Dokumentasikan arsitektur ini dalam diagram alur lengkap dan blok Terraform HCL.

---

## 20. Summary
- Cloudflare Global Load Balancer beroperasi di Layer 7 Anycast Edge, menghilangkan kelemahan DNS caching TTL konvensional.
- Strategi Steering (Geo, Latency, Proximity) memberikan kontrol penuh terhadap regulasi data residency dan optimalisasi performa user.
- Active Health Monitors dengan isolasi probe regional mencegah routing traffic ke origin yang terdegradasi.
- Argo Smart Routing dan Argo Tiered Caching meminimalkan latency dynamic payload dan memangkas origin load secara signifikan via Cloudflare private backbone transit.