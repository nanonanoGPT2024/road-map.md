# Bab 01: Fondasi Arsitektur Cloudflare Edge Network
## Modul 01: Arsitektur Global Edge Network, Anycast Routing, dan Reverse Proxy Pipeline

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis (C4)** perbedaan mendasar antara *Unicast routing* tradisional dan *BGP Anycast routing* yang digunakan pada jaringan global Cloudflare.
*   **Menguraikan (C4)** siklus hidup paket HTTP/HTTPS dari klien, melewati lapisan *Edge Proxy* (Pingora/Nginx lineage), hingga diteruskan ke *Origin Server*.
*   **Mengonfigurasi (C3)** zona Cloudflare dasar dan *DNS records* menggunakan Terraform (Cloudflare Provider v4) dengan status *Proxied* (`orange-clouded`).
*   **Mendiagnosis (C4)** anomali rute jaringan dan inspeksi header transit (*CF-Ray*, *CF-Connecting-IP*, *True-Client-IP*) pada *traffic ingress*.
*   **Mengevaluasi (C5)** trade-off latensi, *session affinity*, dan risiko *asymmetric routing* pada arsitektur berbasis Anycast edge.

---

### 2. Introduction & Conceptual Hook
Dalam arsitektur *web hosting* konvensional, alamat IP publik terikat secara statis pada antarmuka jaringan fisik di pusat data tunggal (*Unicast*). Jika server Anda berada di Frankfurt dan pengguna mengakses dari Jakarta, paket harus melintasi belasan *autonomous systems* (AS) transit antarbenua dengan *round-trip time* (RTT) mencapai 200–300 ms sebelum proses komputasi pertama dieksekusi.

Cloudflare mengubah paradigma ini dengan memetakan satu blok IP publik yang identik ke ratusan pusat data di seluruh dunia secara simultan melalui **BGP Anycast**. 

Bayangkan Anycast seperti nomor darurat darurat universal: di mana pun Anda menelepon, panggilan dialihkan ke kantor operator terdekat secara otomatis berdasarkan topologi jaringan jalan raya, bukan dikirim ke satu kantor pusat nasional. Di balik alamat IP tersebut, berjalan mesin *Reverse Proxy* performa tinggi yang memutus koneksi TCP/TLS langsung ke origin Anda dan menggantikannya dengan arsitektur dua kaki (*dual-legged connection architecture*).

---

### 3. Why This Matters
Dalam lingkungan produksi skala enterprise:
*   **Absorpsi Serangan DDoS Terdistribusi:** Kapasitas jaringan terdistribusi (>300 Tbps) menyerap serangan *volumetric* (misal: SYN flood, DNS amplification) langsung di *edge node* terdekat dari sumber botnet, mencegah saturasi *bandwidth* pada link *upstream* origin.
*   **Optimasi Latensi TLS Handshake:** Penghentian (*termination*) sesi TCP dan negosiasi TLS (TLS 1.3 / QUIC) dilakukan pada server edge yang berjarak fisik <50 ms dari pengguna akhir. Handshake tidak perlu menunggu round-trip interkontinental ke server origin.
*   **Isolasi Origin Server:** IP asli origin server tidak pernah dipublikasikan ke internet publik (*zero public exposure*), memitigasi serangan layer 3 dan layer 4 yang langsung menargetkan infrastruktur komputasi internal Anda.

---

### 4. Core Concept Explained
Ada tiga pilar yang menopang operasi Cloudflare di layer fundamental:

1.  **BGP Anycast:** Berbeda dengan Unicast (1 IP $\rightarrow$ 1 Node) atau Multicast (1 IP $\rightarrow$ Banyak Node spesifik), Anycast mengumumkan rute BGP (*Border Gateway Protocol*) untuk prefix IP yang sama dari semua PoP (*Point of Presence*) Cloudflare di bawah `AS13335`. ISP lokal pengguna memilih rute terpendek (*shortest AS-Path*) ke PoP Cloudflare terdekat.
2.  **Reverse Proxy Architecture:** Cloudflare beroperasi sebagai *dual-legged proxy*. Klien membuat koneksi TCP/TLS independen ke Cloudflare Edge (*Client-to-Edge*), lalu Cloudflare mengevaluasi aturan keamanan/caching, dan jika diperlukan, membuat koneksi baru atau menggunakan kembali *connection pool* yang ada ke server backend Anda (*Edge-to-Origin*).
3.  **Edge Execution Pipeline (Pingora Core):** Ditulis dalam bahasa Rust, Pingora menggantikan arsitektur lama berbasis Nginx. Pingora menangani jutaan *concurrent requests* per mesin dengan model *asynchronous multi-threaded architecture*, mengelola connection pooling HTTP/1.1, HTTP/2, dan HTTP/3 secara hemat memori.

---

### 5. Deep Technical Dive
Mari bedah siklus hidup request dari layer 3 hingga layer 7:

```
[Klien] 
   │ 
   │ 1. DNS Query (A/AAAA) via Resolver
   ▼
[Cloudflare Authoritative DNS (Anycast)] ──> Mengembalikan Anycast IP Cloudflare
   │
   │ 2. TCP SYN (Port 443)
   ▼
[L4 BGP Anycast Router (PoP Terdekat)]
   │
   │ 3. Unimog / Maglev (L4 Load Balancer)
   ▼
[Edge Metal: Pingora Proxy Engine]
   ├── TLS Termination (BoringSSL/quiche)
   ├── DDoS Mitigation (Gatebot/dosd via eBPF/XDP)
   ├── WAF Engine (Core Ruleset evaluation)
   ├── Caching Layer (Tiered Cache / Cache Reserve)
   └── Worker / Routing Rules Evaluation
   │
   │ 4. HTTP/2 or HTTP/3 Connection Pool (Origin Keep-Alive)
   ▼
[Origin Firewall / Load Balancer]
   │
   │ 5. Upstream Application (K8s Ingress / VM)
   ▼
[Origin Server Application]
```

#### A. Layer 4 Ingress: Unimog dan eBPF/XDP
Ketika paket TCP SYN tiba di router perbatasan PoP Cloudflare, paket tersebut didistribusikan ke cluster server menggunakan *Layer 4 Load Balancer* internal bernama **Unimog**. 
Unimog menggunakan program **XDP (eXtended Data Path)** di dalam kernel Linux untuk memeriksa paket langsung di level *network interface card* (NIC) driver sebelum alokasi memori kernel (`sk_buff`) terjadi. Jika paket teridentifikasi sebagai bagian dari serangan DDoS volumetrik, paket akan di-*drop* seketika (*zero-CPU overhead drop*).

#### B. Layer 7 Termination & Pingora Pipeline
Jika paket sah, koneksi dialihkan ke thread **Pingora**:
1.  **TLS Termination:** Pingora menyelesaikan negosiasi TLS menggunakan pustaka kriptografi teroptimasi. Sertifikat SSL/TLS tepi (Universal, Dedicated, atau Custom) disajikan ke klien.
2.  **Request Normalization & Context Initialization:** URI diuraikan, query parameter dipetakan, dan header klien dibaca ke dalam struktur data internal.
3.  **Header Injection:** Cloudflare menyuntikkan metadata operasional krusial:
    *   `CF-Ray`: Pengenal unik 16-karakter heksadesimal per request beserta kode bandara PoP pemroses (misal: `8675309abcde1234-CGK`).
    *   `CF-Connecting-IP`: Alamat IP publik asli dari klien.
    *   `X-Forwarded-Proto`: Protokol asli yang digunakan klien (`http` atau `https`).
4.  **Cache Lookup:** Pingora memeriksa memori lokal dan *Cache Reserve* (SSD NVMe) untuk mencocokkan *Cache Key* (default: `${scheme}${host}${request_uri}`). Jika *HIT*, payload disajikan langsung tanpa menyentuh origin.
5.  **Upstream Multiplexing:** Jika *MISS*, Pingora mengambil koneksi terbuka dari pool HTTP/2 yang sudah dipelihara ke arah origin IP, meminimalkan penundaan negosiasi ulang TCP/TLS ke backend.

---

### 6. Architectural Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                      GLOBAL INTERNET                                               |
+----------------------------------------------------------------------------------------------------+
       |                                                                            |
       | Client (Jakarta) -> Anycast IP                                            | Client (London) -> Anycast IP
       v                                                                            v
+------------------------------------+                      +------------------------------------+
| Cloudflare Edge PoP (CGK - Jakarta)|                      | Cloudflare Edge PoP (LHR - London) |
|  - BGP AS13335 Advertisement       |                      |  - BGP AS13335 Advertisement       |
|  - eBPF/XDP Filter (DDoS drop)     |                      |  - eBPF/XDP Filter (DDoS drop)     |
|  - Pingora L7 Engine:              |                      |  - Pingora L7 Engine:              |
|    * Edge TLS Termination          |                      |    * Edge TLS Termination          |
|    * Edge Cache Engine             |                      |    * Edge Cache Engine             |
+------------------------------------+                      +------------------------------------+
       |                                                                            |
       |  Encrypted Overlay Backhaul                                                |  Encrypted Overlay Backhaul
       |  (Argo Smart Routing / mTLS)                                               |  (Argo Smart Routing / mTLS)
       +───────────────────────────────────┬────────────────────────────────────────+
                                           │
                                           v
                        +------------------------------------+
                        |       ORIGIN INFRASTRUCTURE        |
                        |                                    |
                        |   [Origin Edge: Nginx / ALB]       |
                        |    - Enforce IP Restriction        |
                        |      (Allow ONLY Cloudflare CIDRs) |
                        |    - Authenticated Origin Pulls    |
                        |    - Parse CF-Connecting-IP        |
                        |                                    |
                        |   [Internal Microservices / DB]    |
                        +------------------------------------+
```

---

### 7. Step-by-Step Implementation Guide
Langkah-langkah menyiapkan zona Cloudflare dengan pola proxying deklaratif via Terraform:

#### Langkah 1: Persiapan Environment
Pasang Terraform CLI ($\ge$ 1.5.0) dan tentukan kredensial API Token Cloudflare Anda. Jangan gunakan Global API Key untuk kebutuhan otomatisasi sistem.

```bash
export CLOUDFLARE_API_TOKEN="v_s2...your-scoped-api-token...9aB"
```

#### Langkah 2: Buat Konfigurasi Dasar Terraform (`main.tf`)
Definisikan provider, zona domain, dan DNS record dengan atribut `proxied = true`.

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

variable "zone_name" {
  type        = string
  description = "Apex domain registered in Cloudflare"
  default     = "example-corp.internal"
}

variable "origin_server_ip" {
  type        = string
  description = "Public IP of the upstream origin server"
  default     = "203.0.113.50"
}

# Lookup existing Zone ID or manage it
resource "cloudflare_zone" "primary_zone" {
  account_id = "f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5"
  zone       = var.zone_name
  plan       = "enterprise"
  type       = "full"
}

# Apex Record A (Proxied through Cloudflare Anycast)
resource "cloudflare_record" "apex_a" {
  zone_id = cloudflare_zone.primary_zone.id
  name    = "@"
  content = var.origin_server_ip
  type    = "A"
  proxied = true
  ttl     = 1 # Automatic TTL when proxied
}

# Subdomain CNAME Record
resource "cloudflare_record" "api_subdomain" {
  zone_id = cloudflare_zone.primary_zone.id
  name    = "api"
  content = var.origin_server_ip
  type    = "A"
  proxied = true
  ttl     = 1
}

# SSL/TLS Configuration: Strict mode is mandatory in production
resource "cloudflare_zone_settings_override" "zone_security" {
  zone_id = cloudflare_zone.primary_zone.id
  settings {
    ssl                      = "strict"
    always_use_https         = "on"
    min_tls_version          = "1.2"
    opportunistic_encryption = "on"
    tls_1_3                  = "on"
    automatic_https_rewrites = "on"
  }
}
```

#### Langkah 3: Validasi dan Deploy
Eksekusi instruksi terraform standar:

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

---

### 8. Working Code Examples

#### A. Origin Web Server (Nginx) Configuration
Untuk memastikan server origin hanya menerima traffic dari Cloudflare dan dapat memetakan IP asli klien dengan benar:

Simpan file berikut di `/etc/nginx/conf.d/cloudflare-proxy.conf`:

```nginx
# Update real IP from Cloudflare IP Ranges (IPv4 and IPv6)
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;

set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;

# Directive to use Cloudflare header for remote client IP
real_ip_header CF-Connecting-IP;

server {
    listen 443 ssl http2;
    server_name example-corp.internal api.example-corp.internal;

    ssl_certificate     /etc/ssl/certs/origin-cert.pem;
    ssl_certificate_key /etc/ssl/private/origin-key.pem;

    # Drop any direct request not originating from Cloudflare
    # In production, enforce this at AWS SG / iptables level.
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header CF-Ray $http_cf_ray;
        
        # Application Upstream
        proxy_pass http://127.0.0.1:8080;
    }
}
```

---

### 9. Practical Production Example
Berikut adalah skenario produksi: Sebuah REST API perbankan menerima traffic global dan memerlukan enkripsi *end-to-end* yang ketat serta validasi header identitas request secara terprogram pada aplikasi backend.

#### Implementasi Middleware (Go) untuk Ekstraksi Context Request
Kode berikut menangani validasi request yang masuk melewati Cloudflare:

```go
package main

import (
	"context"
	"log"
	"net"
	"net/http"
	"strings"
)

type contextKey string

const (
	ClientIPKey contextKey = "ClientRealIP"
	RayIDKey    contextKey = "CFRayID"
)

// CloudflareContextMiddleware memvalidasi dan mengekstrak metadata Cloudflare
func CloudflareContextMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 1. Ekstrak CF-Ray
		cfRay := r.Header.Get("CF-Ray")
		if cfRay == "" {
			// Jika kosong, request ini melewati batas keamanan (bypassed proxy)
			log.Println("WARNING: Request rejected: Missing CF-Ray header")
			http.Error(w, "Access Denied: Direct origin access prohibited", http.StatusForbidden)
			return
		}

		// 2. Ekstrak CF-Connecting-IP
		clientIPStr := r.Header.Get("CF-Connecting-IP")
		if clientIPStr == "" {
			clientIPStr = r.Header.Get("X-Forwarded-For")
		}

		parsedIP := net.ParseIP(strings.TrimSpace(clientIPStr))
		if parsedIP == nil {
			log.Printf("ERROR: Malformed IP in CF-Connecting-IP: %s", clientIPStr)
			http.Error(w, "Invalid Client IP", http.StatusBadRequest)
			return
		}

		// Inject ke context request untuk logging internal / auditing
		ctx := context.WithValue(r.Context(), ClientIPKey, parsedIP.String())
		ctx = context.WithValue(ctx, RayIDKey, cfRay)

		// Teruskan context ke handler selanjutnya
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	clientIP := r.Context().Value(ClientIPKey).(string)
	rayID := r.Context().Value(RayIDKey).(string)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"OK","client_ip":"` + clientIP + `","ray_id":"` + rayID + `"}`))
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/health", healthCheckHandler)

	server := &http.Server{
		Addr:    ":8080",
		Handler: CloudflareContextMiddleware(mux),
	}

	log.Println("Starting Origin Application on :8080...")
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("Server startup failed: %v", err)
	}
}
```

---

### 10. Edge Cases & Failure Modes

#### A. BGP Flapping dan Anycast Route Churn
*Mekanisme Kegagalan:* Jika link peering upstream di sebuah PoP berfluktuasi (*flapping*), router ISP lokal klien dapat mengalihkan rute Anycast ke PoP alternatif di tengah jalan.
*Dampak:* State TCP putus mendadak (*TCP Reset / RST*) karena PoP baru tidak memiliki sesi socket kernel yang sama dari PoP sebelumnya, menghasilkan error `Error 522: Connection timed out` atau `TCP Connection Closed`.

#### B. Asymmetric Routing
*Mekanisme Kegagalan:* Terjadi ketika paket egress dari origin server menuju klien tidak melalui Cloudflare, melainkan langsung keluar via gateway internet lokal ISP origin server (karena kesalahan gateway routing default di host origin).
*Dampak:* Klien menolak paket dari origin secara instan via `TCP RST` karena IP pengirim tidak cocok dengan Anycast IP Cloudflare yang diajak berkomunikasi di awal.

#### C. Exhaustion of Origin Ephemeral Ports
*Mekanisme Kegagalan:* Karena jutaan request dialihkan dari rentang IP Cloudflare yang terbatas ke satu IP origin, origin server dapat kehabisan *ephemeral ports* pada local NAT table jika connection pooling HTTP/1.1 tidak diaktifkan (`TIME_WAIT` saturation).

---

### 11. Trade-offs & Limitations

| Pendekatan / Fitur | Trade-off Positif | Trade-off Negatif / Limitasi |
| :--- | :--- | :--- |
| **BGP Anycast** | Latensi ingress rendah secara global; mitigasi DDoS terdistribusi masif. | Tidak ada kontrol absolut atas PoP mana yang dipilih klien (ditentukan metrik BGP ISP klien). |
| **Reverse Proxy (Dual-Legged)** | Modifikasi header, pemfilteran WAF, dan *response caching* di edge. | Menambah hop komputasi L7 (~2-10 ms overhead) jika request berstatus *Cache-MISS*. |
| **Orange Clouded (Proxied)** | Menyembunyikan IP origin sepenuhnya; proteksi L3/L4/L7 gratis. | Hanya mendukung protokol berbasis web standar (HTTP/HTTPS, WebSockets). Non-HTTP butuh *Cloudflare Spectrum*. |
| **HTTP/3 (QUIC) di Edge** | Eliminasi *head-of-line blocking* pada layer transport seluler. | Konsumsi CPU lebih tinggi pada enkripsi paket UDP di lingkungan *client-side* tertentu. |

---

### 12. Security & Compliance Implications
*   **Enkripsi Transit (SSL/TLS):** Penggunaan mode **SSL: Flexible** sangat dilarang (*antipattern kritis*). Mode ini mengenkripsi klien-ke-edge, namun mengirim plaintext (HTTP) dari edge-ke-origin melintasi internet terbuka, melanggar standar PCI-DSS 4.0 dan GDPR Art. 32. Mode **Strict** adalah kepatuhan wajib.
*   **Sertifikat Origin CA:** Untuk mencegah serangan *Man-in-the-Middle* (MitM) jika DNS di-spoof, origin server harus menggunakan sertifikat internal yang divalidasi oleh Cloudflare Origin CA dengan masa kedaluwarsa ketat.
*   **Data Residency:** Karena Anycast secara otomatis memilih rute tercepat, data in-transit pengguna di Uni Eropa berpotensi diproses di PoP non-EU jika terjadi failover routing peering internasional, kecuali jika fitur *Data Localization Suite* (DLS) diaktifkan pada tingkat organisasi enterprise.

---

### 13. Performance & Optimization Strategies
*   **Keep-Alive Tuning:** Set upstream keep-alive timeout pada Origin minimal 60-120 detik. Ini mencegah *Pingora* mengulang *three-way handshake* TCP dan negosiasi TLS berulang-ulang untuk request berturutan dari PoP yang sama:
    ```nginx
    keepalive_timeout 75s;
    keepalive_requests 10000;
    ```
*   **Argo Smart Routing:** Memanfaatkan data analitik jaringan real-time untuk merutekan traffic *Edge-to-Origin* melalui jalur privat teroptimasi milik Cloudflare alih-alih jalur internet publik yang rawan kongesti, memangkas waktu TTFB (Time to First Byte) hingga rata-rata 30%.
*   **TCP Optimizations di Origin:** Tingkatkan limit antrean socket SYN pada kernel Linux origin untuk menerima lonjakan burst koneksi dari Cloudflare Edge:
    ```bash
    sysctl -w net.ipv4.tcp_max_syn_backlog=8192
    sysctl -w net.core.somaxconn=8192
    ```

---

### 14. Cost & Resource Optimization
*   **Reduksi Bandwidth Egress Origin:** Mengaktifkan *caching* untuk aset statis (gambar, berkas JS/CSS) di edge memangkas biaya keluar (*outbound transfer*) penyedia cloud publik (AWS Data Transfer Out, GCP Egress) hingga 80-95%.
*   **Tiered Cache Architecture:** Aktifkan *Tiered Cache* di Cloudflare Dashboard. Fitur ini menunjuk beberapa PoP super-regional besar sebagai layer cache perantara antara PoP lokal dan Origin, mengeliminasi query berulang ke origin dari puluhan PoP regional independen.
*   **Cloudflare Tunnel (`cloudflared`):** Menggunakan Tunnel meniadakan kebutuhan menyewa *Public IPv4 Address* statis berbayar di cloud provider dan memangkas biaya alokasi Application Load Balancer publik.

---

### 15. Common Pitfalls & Antipatterns

#### 1. "Flexible" SSL Configuration
*Antipattern:* Mengaktifkan mode "Flexible" karena origin tidak memiliki sertifikat SSL.
*Dampak:* Terjadi loop redireksi `HTTP 301/302 Redirect Loop` tanpa henti jika origin secara otomatis me-redirect HTTP ke HTTPS, atau kredensial pengguna terkirim tanpa enkripsi di segmen *Edge-to-Origin*.
*Solusi:* Pasang *self-signed certificate* atau *Cloudflare Origin Certificate* gratis pada origin, lalu ubah mode SSL ke **Strict**.

#### 2. Logging Cloudflare IP Alih-alih Client IP
*Antipattern:* Langsung membaca `$remote_addr` pada web server origin tanpa modul `ngx_http_realip_module`.
*Dampak:* Semua pengguna di seluruh dunia dicatat di file log aplikasi sebagai salah satu dari 15 rentang IP Cloudflare. Sistem *rate limiter* internal origin mengira seluruh dunia berasal dari satu user dan melakukan pemblokiran massal.
*Solusi:* Gunakan modul restore real-IP via `CF-Connecting-IP`.

#### 3. Kebocoran IP Origin via DNS Record (Direct Origin Exposure)
*Antipattern:* Membiarkan record non-proxied seperti `mail.example.com` atau `ftp.example.com` menunjuk ke IP yang sama persis dengan origin web server `example.com`.
*Dampak:* Penyerang mengekstrak IP fisik server via lookup sederhana, lalu melancarkan serangan volumetrik layer 4 langsung ke IP tersebut, melewati seluruh layer pertahanan Cloudflare.
*Solusi:* Pisahkan IP origin web dengan server mail/FTP, atau isolasi origin menggunakan *Security Group* yang hanya menerima whitelist IP Cloudflare.

---

### 16. Debugging & Troubleshooting Guide

#### Diagnostik Header Menggunakan `curl`
Gunakan perintah ini untuk membedah rute request:

```bash
curl -svo /dev/null https://example-corp.internal/api/v1/health \
  -H "Pragma: no-cache" \
  -H "Cache-Control: no-cache"
```

Output penting yang harus dianalisis:
*   `< cf-ray: 8e847c1b1c674cb9-SIN`: Menunjukkan request diproses di PoP Singapura (`SIN`).
*   `< cf-cache-status: DYNAMIC`: Request dieksekusi langsung ke origin (tidak disajikan dari cache). Jika nilainya `HIT`, file dilayani dari cache PoP.
*   `< server: cloudflare`: Memastikan respons melewati engine Cloudflare.

#### Matriks Diagnostik Status HTTP Cloudflare

| Kode HTTP | Penjelasan Teknis | Tindakan Korektif Administrator |
| :--- | :--- | :--- |
| **Error 520: Web Server Returned an Unknown Error** | Origin mengembalikan respons kosong, reset koneksi tak terduga, atau header origin melebihi 16KB. | Periksa crash log di web server backend; evaluasi ukuran header HTTP upstream. |
| **Error 521: Web Server Is Down** | Edge mencoba melakukan handshake TCP ke IP origin pada port 80/443, namun menerima respons `ECONNREFUSED`. | Pastikan process Nginx/Apache berjalan; periksa firewall Security Group origin apakah memblokir IP Edge. |
| **Error 522: Connection Timed Out** | Handshake TCP antara Cloudflare edge dan IP origin melewati batas waktu timeout (>15 detik). | Terjadi routing blackhole di ISP origin, saturasi bandwidth link server, atau packet loss masif. |
| **Error 524: A Timeout Occurred** | TCP handshake berhasil, namun edge tidak menerima respons HTTP dari origin dalam batas timeout Cloudflare (default: 100s). | Optimasi database query origin yang berjalan terlalu lama (long-polling/heavy computation). |

---

### 17. Comparison / Alternative Approaches

| Dimensi | Cloudflare Anycast Reverse Proxy | AWS CloudFront + ALB | Fastly Edge Cloud | Traditional On-Premise ADC (F5 BIG-IP) |
| :--- | :--- | :--- | :--- | :--- |
| **Routing Method** | BGP Anycast Global | Latency-based DNS routing | BGP Anycast | BGP Unicast |
| **Arsitektur Inti** | Proprietary Rust (Pingora) | Nginx/Envoy lineage | Custom Varnish Cache (VCL) | Proprietary TMOS (Hardware/VM) |
| **DDoS Mitigation** | Otomatis di edge (eBPF/XDP Unimog) | AWS Shield Standard/Advanced | Terdistribusi via VCL logic | Butuh modul dedicated (ASM/AFM) |
| **Origin Isolation** | Sangat Tinggi via Cloudflare Tunnel | Sangat Tinggi jika dalam AWS VPC | Tinggi via IP ACL | Terbatas pada kapasitas pipa uplink datacenter |
| **Kurva Pembelajaran** | Cepat (Dashboard/Terraform intuitif) | Menengah (IAM, VPC, Route53, ALB) | Curam (Memerlukan kemahiran sintaks VCL) | Sangat Kompleks (Network engineering berat) |

---

### 18. Real-World Case Studies
Sebuah platform e-commerce fintech berskala nasional meluncurkan flash sale berskala masif. 

*   *Kondisi Awal:* Arsitektur menggunakan DNS Unicast tradisional langsung ke tiga server Nginx di AWS Jakarta.
*   *Insiden:* Menjelang flash sale, terjadi serangan DDoS Layer 7 HTTP flood sebesar 450.000 RPS yang dikombinasikan dengan 80.000 RPS pengguna sah. Load balancer origin mengalami kegagalan kernel *out-of-memory* (OOM) akibat kehabisan memori TCP connection tracking.
*   *Mitigasi:* Tim teknis memigrasikan nameserver ke Cloudflare dalam 15 menit, menyalakan mode *Proxied*, dan menerapkan aturan WAF *Managed Challenge*.
*   *Hasil:* Traffic flood Anycast secara instan diserap oleh PoP regional terdekat (Jakarta, Singapura, Kuala Lumpur, Hong Kong). Volume traffic yang menembus ke server origin turun dari 530.000 RPS menjadi hanya 4.200 RPS (hanya traffic sah yang belum di-cache). Utilisasi CPU origin turun dari 100% ke 18%, dan event flash sale berjalan tanpa *downtime*.

---

### 19. Exercises & Hands-on Challenges

#### Latihan 1: Analisis Routing Trace (Inspeksi Anycast)
1.  Jalankan perintah `traceroute` (atau `tracert` di Windows) ke domain proxied Anda:
    ```bash
    traceroute api.example-corp.internal
    ```
2.  Bandingkan output hop rute tersebut jika dijalankan dari dua koneksi berbeda (misal: koneksi ISP Fiber optik rumah vs seluler).
3.  *Pertanyaan:* Mengapa IP tujuan yang dicapai sama persis, namun hop intermediate jaringan berbeda jauh secara geografis? Jelaskan peran BGP Anycast pada fenomena ini.

#### Latihan 2: Implementasi Script Origin Firewall Otomatis
Tuliskan shell script (`bash`) yang secara dinamis mengambil rentang IPv4 resmi Cloudflare dari API publik (`https://www.cloudflare.com/ips-v4`) dan mengonfigurasi `iptables` lokal untuk memblokir seluruh koneksi port 80/443 kecuali dari IP Cloudflare tersebut.

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Mengambil IP Cloudflare..."
CF_IPS=$(curl -s https://www.cloudflare.com/ips-v4)

# 1. Buat chain khusus di iptables
iptables -N CLOUDFLARE_ONLY || iptables -F CLOUDFLARE_ONLY

# 2. Loop dan allow IP Cloudflare
for ip in $CF_IPS; do
    iptables -A CLOUDFLARE_ONLY -p tcp -s "$ip" -m multiport --dports 80,443 -j ACCEPT
done

# 3. Drop traffic lainnya pada port 80/443
iptables -A CLOUDFLARE_ONLY -p tcp -m multiport --dports 80,443 -j DROP

# 4. Tautkan chain ke INPUT
iptables -C INPUT -j CLOUDFLARE_ONLY 2>/dev/null || iptables -I INPUT -j CLOUDFLARE_ONLY

echo "Firewall rule Cloudflare-only berhasil diterapkan!"
```

---

### 20. Summary & Key Takeaways
*   **Anycast Fundamental:** Cloudflare mengumumkan satu blok alamat IP publik yang sama dari ratusan edge data center global melalui BGP, merutekan pengguna ke edge terdekat tanpa rekayasa geolokasi DNS yang lambat.
*   **Dual-Legged Architecture:** Cloudflare adalah L7 Reverse Proxy. Sesi TLS klien berhenti di edge (*Client-to-Edge*), lalu dimediasi sebelum koneksi aman kedua diarahkan ke backend Anda (*Edge-to-Origin*).
*   **Security by Obscurity Disempurnakan:** Jangan pernah mempublikasikan alamat IP origin asli Anda. Amankan origin dengan memblokir semua traffic kecuali prefix resmi Cloudflare atau gunakan koneksi virtual berbasis *Cloudflare Tunnel*.
*   **SSL Strict Adalah Mandatori:** Penggunaan SSL Flexible meninggalkan celah keamanan kritis pada segmen transit backend dan menimbulkan potensi loop tak berujung. Selalu gunakan mode enkripsi *Full (Strict)*.