# Module 01: Zero Trust Network Access (ZTNA), Cloudflare Tunnels, & Secure Access

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengonfigurasi arsitektur **Zero Trust Network Access (ZTNA)** berbasis Cloudflare One tanpa membuka port publik (Zero Inbound Ports).
- Menerapkan **Cloudflare Tunnel (`cloudflared`)** secara terkelola (Locally Managed & Remote/Dashboard Managed) untuk mengamankan komunikasi layanan privat ke edge Cloudflare.
- Mengintegrasikan **Identity Providers (IdP)** modern (seperti Okta, Azure AD/Entra ID, atau Google Workspace) dan menerapkan evaluasi **Device Posture** untuk dynamic access control.
- Mengonfigurasi dan mendistribusikan **Cloudflare WARP client** guna mengamankan traffic Layer 3/Layer 4 serta mengenkripsi jalur komputasi edge.
- Merancang dan mengeksekusi kebijakan **Secure Web Gateway (SWG)** mencakup inspeksi Layer 7 HTTP/HTTPS (TLS Decryption/Inspection) dan mitigasi ancaman Layer 7/DNS Filtering.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- Pengetahuan solid mengenai protokol jaringan: TCP/IP, UDP, DNS (A/AAAA, CNAME), dan TLS 1.3 handshake.
- Pemahaman tentang model autentikasi modern: OAuth 2.0, OpenID Connect (OIDC), SAML 2.0, serta JSON Web Tokens (JWT).
- Pengalaman dasar menggunakan Linux CLI (`systemd`, networking namespace, `curl`, `dig`).
- Akun Cloudflare aktif dengan domain terdelegasi pada Cloudflare Nameservers dan langganan Zero Trust (Free/Enterprise tier).
- Terraform/OpenTofu CLI terpasang pada workstation lokal (opsional untuk automated provisioning).

---

## 3. Concept
Secara konvensional, keamanan jaringan korporat dibangun di atas perimeter model ("Castle-and-Moat"). VPN tradisional memberikan akses jaringan penuh (Layer 3 network-level access) setelah pengguna berhasil melakukan autentikasi kredensial. Jika perimeter berhasil ditembus atau mesin pengguna terkompromi, penyerang dapat melakukan pergerakan lateral (*lateral movement*) melintasi subnet internal.

**Zero Trust Network Access (ZTNA)** membalik paradigma ini melalui prinsip:
> *"Never Trust, Always Verify, Assume Breach."*

Pada Cloudflare Zero Trust (Cloudflare One):
1. **Aplikasi tersembunyi sepenuhnya dari internet publik**: Tidak ada IP publik, tidak ada firewall rules inbound (`0.0.0.0/0 -> ACCEPT`).
2. **Koneksi inisiasi keluar (Outbound-only)**: Daemon internal (`cloudflared`) membuat koneksi keluar melalui HTTP/2 atau QUIC ke PoP (Point of Presence) Cloudflare terdekat.
3. **Autentikasi Mikro Per-Permintaan (Micro-segmentation & Continuous Verification)**: Setiap paket dan sesi diverifikasi terhadap identitas pengguna, status kepatuhan perangkat (*device posture*), dan konteks lokasi sebelum diproksikan ke origin.

---

## 4. Why
Mengapa meninggalkan arsitektur VPN tradisional dan beralih ke ZTNA + Cloudflare Tunnel?

1. **Eliminasi Attack Surface Publik**: Port terbuka seperti SSH (22), RDP (3389), atau HTTP internal (80/8080) adalah target utama bot scanner, zero-day exploit web servers, dan brute-force attacks. Cloudflare Tunnel menutup seluruh port inbound.
2. **Mencegah Lateral Movement**: VPN memberikan alamat IP pada subnet privat internal. Cloudflare Access menerapkan isolasi aplikasi granular (App-level microsegmentation). Pengguna hanya mengakses aplikasi `app.internal.domain`, tanpa visibilitas ke mesin di sebelahnya (`db.internal.domain`).
3. **Performa Anycast Global**: Pengguna terhubung ke edge Cloudflare terdekat (>330 kota di dunia) melalui protokol Argo Smart Routing dan QUIC/HTTP-3, menghindari latency hairpinning (backhauling) khas VPN konsentrator terpusat.
4. **Context-Aware Enforcement**: Tidak hanya mengecek username/password, edge memeriksa apakah OS terupdate, sertifikat mTLS terpasang, disk terenkripsi (BitLocker/FileVault), dan EDR (CrowdStrike/SentinelOne) aktif.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Cloudflare Tunnel & `cloudflared` Architecture
`cloudflared` adalah daemon open-source berbasis Go yang dijalankan di dekat origin server (host bare-metal, VM, atau container).
- **Protokol Transportasi**: Secara default menggunakan **QUIC** (UDP port 7844) atau **HTTP/2** (TCP port 7844). Daemon menginisiasi 4 koneksi paralel keluar (*outbound-only*) ke edge Cloudflare terdistribusi.
- **Virtual Network Socket**: Edge Cloudflare menerima permintaan eksternal dari klien yang terotorisasi, mengenkapsulasinya, dan mengirimkannya ke `cloudflared` melalui terowongan yang sudah terbentuk. `cloudflared` bertindak sebagai reverse proxy lokal yang meneruskan traffic ke `localhost` atau IP subnet LAN privat.

```
[Klien / Browser]
       │
       ▼ (HTTPS / Port 443)
[Cloudflare Global Edge] ──(Edge Policy Engine: Access + SWG)
       │
       ▼ (QUIC / Outbound UDP 7844 - Established Tunnel)
[cloudflared daemon]
       │
       ▼ (Local Network / Unix Socket / Loopback)
[Origin Service (e.g., http://localhost:8080, SSH, SMB)]
```

### 5.2 Cloudflare Access Policy Evaluation Engine
Cloudflare Access menyisipkan lapisan autentikasi di edge sebelum request menyentuh tunnel. 
- **OIDC/SAML Exchange**: Saat request masuk tanpa token valid, pengguna diredireksi ke IdP. Setelah berhasil login, Cloudflare memvalidasi IdP response dan menerbitkan signed token `CF_Authorization` (JWT).
- **JWT Validation**: Origin service dapat memvalidasi signature token menggunakan public JWKS endpoint Cloudflare (`https://<team-name>.cloudflareaccess.com/cdn-cgi/access/certs`) untuk mencegah request spoofing.
- **Policy Hierarchy**:
  - `Allow`: Akses diizinkan jika kondisi terpenuhi.
  - `Block`: Akses ditolak secara eksplisit jika kondisi terpenuhi.
  - `Bypass`: Melewati Access (biasanya untuk endpoint webhook publik atau monitoring ping tertentu).
  - `Service Auth`: Digunakan untuk integrasi machine-to-machine menggunakan Service Tokens (`CF-Access-Client-Id` dan `CF-Access-Client-Secret`).

### 5.3 WARP Client & Tunneling Layer 3/4
Cloudflare WARP adalah client berbasis WireGuard yang dimodifikasi (BoringTun - Rust).
- Berjalan di level network adapter (TUN interface).
- Mengarahkan traffic IP (IPv4/IPv6) dari perangkat pengguna secara terenkripsi ke Cloudflare Edge.
- Menerapkan **Split Tunneling**:
  - *Exclude Mode*: Semua traffic masuk WARP kecuali IP/domain internal tertentu.
  - *Include Mode*: Hanya subnet privat tertentu (misal: `10.0.0.0/8`, `172.16.0.0/12`) yang diarahkan ke WARP; traffic publik langsung ke internet lokal.
- Bekerja berdampingan dengan Cloudflare Gateway untuk inspeksi keamanan.

### 5.4 Secure Web Gateway (SWG): DNS & HTTP Filtering
- **DNS Filtering**: Resolver WARP menangkap query port 53 / DoH. Cloudflare Edge memblokir domain berbahaya berdasarkan threat intelligence (Phishing, Malware, C2) dan Domain Category blocking sebelum handshake IP terjadi.
- **HTTP Filtering & TLS Inspection**:
  - Cloudflare mendistribusikan root CA sertifikat privat ke perangkat terkelola via MDM.
  - Edge Cloudflare melakukan terminasi TLS (*forward proxy interception*), mendekripsi payload HTTPS, memindai konten terhadap Antivirus/DLP (Data Loss Prevention), memeriksa header HTTP, dan mengenkripsi kembali payload menuju tujuan akhir.

---

## 6. How
Implementasi Zero Trust mencakup 4 pilar operasional:
1. **Penyusunan Identity Provider**: Integrasi tenant OIDC/SAML ke dashboard Zero Trust.
2. **Pemasangan `cloudflared`**: Instalasi binary, pembuatan UUID tunnel, mapping file `config.yml`, dan instalasi service `systemd`.
3. **Penerapan Device Posture via WARP**: Pemasangan WARP client dengan enrollment token, validasi serial number atau keberadaan file/registry key spesifik.
4. **Pemberlakuan Kebijakan Gateway**: Mengaktifkan TLS Decryption dan menyusun rule DNS/HTTP untuk memblokir zero-day data exfiltration.

---

## 7. Analogy
Bayangkan kantor pusat perbankan dengan brankas uang (Origin Server).
- **Pendekatan Tradisional (VPN)**: Gerbang utama gedung dijaga satpam. Jika Anda memiliki ID Card (kredensial VPN), Anda dipersilakan masuk gedung. Setelah berada di dalam gedung, Anda bebas berjalan di koridor, mengintip setiap pintu, dan mencoba membuka brankas.
- **Pendekatan Cloudflare Zero Trust**: Gedung tersebut sama sekali **tidak memiliki pintu, jendela, atau jalan masuk dari luar**. Tidak ada seorang pun yang bisa melihat gedung tersebut dari jalan raya.
  - Brankas di dalam memiliki kurir internal (`cloudflared`) yang menggali terowongan satu arah keluar langsung ke pos komando terpadu Cloudflare.
  - Saat staf bank ingin mengakses brankas, mereka melapor ke pos komando Cloudflare. Di sana, Cloudflare memverifikasi KTP (IdP), memeriksa apakah staf membawa tas berlubang atau virus (Device Posture/Antivirus), dan mengawal staf secara spesifik hanya ke kotak deposit miliknya, tanpa mengizinkannya melihat ruangan lain.

---

## 8. Diagram (ASCII)

```
                       ARSHITEKTUR ZTNA END-TO-END
                       ===========================

[ Managed Device ]
 (WARP Client /
  mTLS Cert Installed)
       │
       │ Encrypted WireGuard/HTTPS Tunnel (Outbound)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE EDGE NETWORK                      │
│                                                                 │
│  ┌────────────────────────┐         ┌────────────────────────┐  │
│  │   Cloudflare Access    │         │ Cloudflare Gateway     │  │
│  │  - Identity (IdP)      │         │  - DNS Inspection      │  │
│  │  - Device Posture      │         │  - TLS Proxy Decryption│  │
│  │  - Geo/IP Restrictions │         │  - DLP / AV Scanning   │  │
│  └───────────┬────────────┘         └───────────┬────────────┘  │
│              │ (Pass)                           │ (Pass)        │
└──────────────┼──────────────────────────────────┼───────────────┘
               │                                  │
               │ QUIC Multiplexed Tunnel          │ Outbound Web
               │ (No Inbound Ports Opened)        │ Traffic Filtered
               ▼                                  ▼
┌──────────────────────────────┐       ┌────────────────────────┐
│     Private Infrastructure   │       │     Public Internet    │
│                              │       │                        │
│   ┌──────────────────────┐   │       │  [SaaS Tools / Web]    │
│   │ cloudflared daemon   │   │       └────────────────────────┘
│   └──────────┬───────────┘   │
│              │ Local Proxy   │
│              ▼               │
│   ┌──────────────────────┐   │
│   │ Origin Applications  │   │
│   │ (K8s, DB, SSH, Web)  │   │
│   └──────────────────────┘   │
└──────────────────────────────┘
```

---

## 9. Simple Example
Menjalankan tunnel ad-hoc cepat (*quick tunnel*) untuk mengekspos aplikasi pengembangan lokal tanpa konfigurasi domain:

```bash
# Menjalankan web server lokal sederhana pada port 8000
python3 -m http.server 8000 &

# Menjalankan cloudflared trycloudflare (quick tunnel otomatis)
cloudflared tunnel --url http://localhost:8000
```
Output terminal akan menampilkan URL sementara yang aman, seperti `https://random-words.trycloudflare.com`. Traffic eksternal diarahkan via edge Cloudflare langsung ke web server lokal Anda tanpa memerlukan port forwarding pada router NAT.

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Hands-on)

### 10.1 Konfigurasi Cloudflare Tunnel Terkelola (Locally Managed)

#### 1. Login dan Buat Tunnel via CLI
```bash
# Otentikasi CLI terhadap domain Cloudflare
cloudflared tunnel login

# Membuat tunnel bernama 'production-core'
cloudflared tunnel create production-core
# Output akan menampilkan UUID tunnel, misal: 4e7d825c-b17a-4db3-98fe-e39535bfd3cb
```

#### 2. Buat File Konfigurasi Ingress: `/etc/cloudflared/config.yml`
```yaml
tunnel: 4e7d825c-b17a-4db3-98fe-e39535bfd3cb
credentials-file: /etc/cloudflared/4e7d825c-b17a-4db3-98fe-e39535bfd3cb.json
protocol: quic

ingress:
  # Rute 1: Dashboard Internal Web
  - hostname: internal-dashboard.corp.example.com
    service: http://10.0.10.15:80
    originRequest:
      connectTimeout: 10s
      noTLSVerify: false

  # Rute 2: Internal Secure SSH bastion
  - hostname: bastion.corp.example.com
    service: ssh://localhost:22

  # Rute 3: Catch-all rule (Wajib disertakan di akhir)
  - service: http_status:404
```

#### 3. Routing DNS dan Menjalankan Service
```bash
# Menambahkan record CNAME DNS secara otomatis ke Cloudflare Edge
cloudflared tunnel route dns production-core internal-dashboard.corp.example.com
cloudflared tunnel route dns production-core bastion.corp.example.com

# Instalasi dan jalankan sebagai daemon systemd
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

---

### 10.2 Implementasi Deklaratif Menggunakan Terraform (ZTNA Stack)

```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30"
    }
  }
}

variable "cloudflare_account_id" {
  type = string
}

variable "cloudflare_zone_id" {
  type = string
}

# 1. Definisikan Secret Tunnel
resource "random_id" "tunnel_secret" {
  byte_length = 35
}

# 2. Buat Cloudflare Tunnel
resource "cloudflare_tunnel" "k8s_private_tunnel" {
  account_id = var.cloudflare_account_id
  name       = "k8s-cluster-tunnel"
  secret     = random_id.tunnel_secret.b64_std
}

# 3. DNS CNAME Record yang mengarah ke Tunnel
resource "cloudflare_record" "app_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "k8s-app"
  value   = "${cloudflare_tunnel.k8s_private_tunnel.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

# 4. Access Application Configuration
resource "cloudflare_access_application" "private_k8s_app" {
  account_id       = var.cloudflare_account_id
  name             = "Kubernetes Core App"
  domain           = "k8s-app.corp.example.com"
  session_duration = "8h"
  auto_redirect_to_identity = true
}

# 5. Access Policy (Hanya grup SRE dan Device Posture Aktif)
resource "cloudflare_access_policy" "sre_only_policy" {
  application_id = cloudflare_access_application.private_k8s_app.id
  account_id     = var.cloudflare_account_id
  name           = "Enforce Corporate SRE with Compliant Device"
  decision       = "allow"
  precedence     = 1

  include {
    email_domain = ["example.com"]
  }

  require {
    # Memerlukan koneksi client WARP aktif
    warp = true
  }
}

# 6. Gateway HTTP Rule: TLS Decryption & AV Inspection
resource "cloudflare_teams_rule" "block_malware_and_threats" {
  account_id  = var.cloudflare_account_id
  name        = "Security: Block Malicious Domains & Antivirus Scan"
  description = "Mencegah eksekusi payload malware dan command-and-control"
  precedence  = 100
  action      = "block"
  enabled     = true
  filters     = ["http"]
  traffic     = "any(http.request.uri.content_categories[*] in {99 101 103}) or http.download.virus.present"
}
```

---

## 11. Real World Example
Sebuah institusi fintech skala nasional memiliki kluster database analitik PostgreSQL dan portal audit compliance internal yang berjalan di dalam AWS VPC privat (tanpa Internet Gateway, hanya memiliki NAT Gateway outbound). 

**Masalah**: 
Sebelumnya, insinyur data dan auditor eksternal menggunakan OpenVPN server bastion. Kunci privat VPN kerap tertinggal di laptop kontraktor, dan satu pengguna VPN yang terinfeksi ransomware sempat menyebabkan pemindaian port internal (reconnaissance) di seluruh subnet analitik.

**Solusi Arsitektur**:
1. Menghapus Bastion Host dan OpenVPN server secara permanen. Menghapus seluruh Security Group inbound rule (`0.0.0.0/0`) pada AWS VPC.
2. Memasang container `cloudflared` di dalam Amazon ECS Fargate di private subnet dengan role egress-only via NAT Gateway.
3. Portal analitik diikat ke domain `audit.internal.fintech.id`.
4. Mengintegrasikan Cloudflare Access dengan Okta SAML (SSO korporat) dan Azure AD (untuk auditor tamu via B2B guest account).
5. Menetapkan aturan Device Posture: Laptop harus menjalankan CrowdStrike Falcon Falcon Agent (Zero Trust Assessment score >= 80) dan sertifikat mTLS korporat harus valid.
6. Akses SSH/DB diamankan via Cloudflare WARP with Access for Infrastructure. Kueri audit dicatat secara terpusat di Cloudflare Logpush dan dialirkan ke Datadog/Splunk secara real-time.

**Hasil**: Serangan lateral movement tereduksi menjadi 0%, latensi berkurang 45% dibandingkan transit VPN terpusat, dan waktu onboarding auditor eksternal turun dari 3 hari menjadi 5 menit melalui delegasi IdP berbasis grup.

---

## 12. Trade-offs
Memilih arsitektur ZTNA Cloudflare memiliki konsekuensi operasional yang harus diperhitungkan:

| Parameter | Cloudflare ZTNA & Tunnels | Solusi Tradisional (VPN / Bastion) |
| :--- | :--- | :--- |
| **Inbound Security** | **Sangat Baik**: 0 Inbound ports terbuka. Resiko pemindaian port publik nol. | **Rentan**: Port publik VPN/SSH harus terekspos ke internet. |
| **Vendor Lock-in** | **Tinggi**: Sangat terikat pada ekosistem edge, API, dan kontrol Cloudflare. | **Rendah**: Protokol standar (OpenVPN, WireGuard, IPsec) dapat dipindah antar server. |
| **Throughput & UDP Heavy** | **Tergantung Protokol**: Optimal untuk TCP, HTTP/2, SSH. Traffic UDP non-standar (e.g., custom streaming) memerlukan konfigurasi WARP routing khusus. | **Sangat Fleksibel**: Layer-3 VPN membungkus seluruh traffic IP (TCP/UDP/ICMP) secara default. |
| **Inspeksi Privasi (SWG)** | **Kompleks**: TLS Inspection membutuhkan distribusi Root CA internal ke seluruh endpoint melalui MDM. | **Sederhana**: Traffic VPN di-tunnel tanpa dekripsi L7 internal (kecuali menggunakan dedicated proxy appliance). |
| **Biaya Skalabilitas** | **Prediktif per-user/seat**: Lisensi dihitung per identitas aktif bulanan. | **Infrastruktur Mandiri**: Dihitung dari compute VM dan egress data transfer cloud provider. |

---

## 13. When To Use
- Mengamankan dashboard operasional internal (Grafana, ArgoCD, Jenkins, Kubernetes Dashboard) tanpa eksposur publik.
- Menggantikan VPN korporat warisan untuk tenaga kerja remote / Work-From-Anywhere (WFA).
- Mengontrol akses kontraktor eksternal dengan prinsip *Least Privilege* tanpa memberikan akses ke seluruh subnet internal.
- Melindungi server internal on-premise di belakang Carrier-Grade NAT (CGNAT) atau koneksi ISP tanpa IP statis publik.
- Memenuhi kepatuhan regulasi keamanan finansial (PCI-DSS v4.0, SOC2 Type II, ISO 27001) yang menuntut pencatatan audit akses dan autentikasi multi-faktor adaptif.

---

## 14. When NOT To Use
- Lingkungan tertutup total (*Air-Gapped Network*) tanpa akses internet keluar (outbound access). `cloudflared` membutuhkan koneksi outbound permanen ke edge Cloudflare.
- Traffic jaringan yang sangat bergantung pada protokol Layer 2 (seperti broadcast/multicast mDNS, PXE boot, atau ARP discovery lokal).
- Aplikasi legacy non-IP (misal: serial interface atau protokol industri proprietary SCADA yang tidak dapat dibungkus TCP/UDP).
- Beban transfer data sangat besar yang dijalankan antar-server internal dalam data center yang sama (East-West traffic lokal; menggunakan Cloudflare Tunnel akan memicu latency dan bandwidth loop yang tidak perlu).

---

## 15. Common Mistakes
1. **Lupa Menambahkan Catch-All Ingress Rule**: Pada `config.yml`, tidak menyertakan `- service: http_status:404` di baris terakhir. Hal ini menyebabkan crash saat `cloudflared` membaca konfigurasi.
2. **Double Compression & MTU Clashing**: Mengaktifkan kompresi Gzip/Brotli berat di origin saat Cloudflare Edge juga mengompresinya, atau masalah packet drop MTU pada WARP interface (default WireGuard 1280-1420 MTU) akibat router ISP memotong paket tanpa PMTU Discovery.
3. **Mengabaikan Validasi JWT di Origin**: Menganggap traffic dari `cloudflared` sudah 100% aman tanpa memvalidasi token JWT (`Cf-Access-Jwt-Assertion`) pada web backend. Jika tunnel diubah secara lokal oleh engineer lain untuk mem-bypass Access, origin akan rentan terhadap SSRF/Unauthorized call.
4. **Origin SSL Mismatch**: Menetapkan `service: https://localhost:443` di konfigurasi tunnel tanpa menambahkan `originRequest: noTLSVerify: true` ketika backend menggunakan self-signed TLS certificate internal, mengakibatkan error `502 Bad Gateway`.
5. **Konflik Split-Tunneling**: Memasukkan rute DNS korporat ke dalam *WARP Exclude List*, sehingga query dialihkan ke DNS ISP lokal yang tidak mengenali rekaman nama internal.

---

## 16. Best Practices
1. **High Availability (HA) Tunnels**: Selalu jalankan minimal dua instance daemon `cloudflared` pada host/VM/Availability Zone yang berbeda menggunakan token tunnel UUID yang sama. Cloudflare akan secara otomatis melakukan round-robin dan active-failover.
2. **Kombinasikan Posture Check dengan IdP Claims**: Buat Access Policy dengan logika kondisional ganda: `Require corporate email` AND `Require Device Posture Compliant` AND `Require Geo-IP IN (Allowed Countries)`.
3. **Aktifkan Short-Lived Certificates untuk SSH**: Daripada mendistribusikan SSH keys statis, gunakan Cloudflare Access SSH CA generator untuk menerbitkan sertifikat SSH sementara berbasis sesi token ID.
4. **Gunakan Logpush untuk SIEM**: Ekspor log HTTP Requests, Audit Logs, dan Gateway DNS Logs ke storage bucket (S3/GCS) atau SIEM untuk forensik audit keamanan.
5. **Gunakan Remote-Managed Tunnels untuk Tim Skala Besar**: Kelola tunnel dan routing melalui Terraform atau Cloudflare Zero Trust Dashboard, bukan melalui konfigurasi file lokal manual di tiap server, guna mencegah konfigurasi usang (*configuration drift*).

---

## 17. Troubleshooting
Panduan langkah taktis ketika menghadapi kegagalan operasional:

### Masalah 1: `cloudflared` Gagal Membentuk Koneksi (Retrying connection in backoff mode)
- **Diagnosis**: Port UDP 7844 diblokir oleh firewall perimeter lokal / router ISP (QUIC connection failure).
- **Solusi**: Paksa daemon menggunakan protokol HTTP/2 berbasis TCP:
  ```bash
  cloudflared tunnel --protocol http2 run <TUNNEL_NAME_OR_ID>
  ```
  Pastikan firewall outbound mengizinkan TCP port 7844 atau TCP port 443 ke subnet IP Cloudflare Anycast.

### Masalah 2: Error 530 / Error 1033 (Cloudflare Tunnel Error)
- **Diagnosis**: Edge Cloudflare menerima traffic publik, namun daemon `cloudflared` yang terdaftar untuk tunnel tersebut sedang offline, kehilangan koneksi, atau origin service mati.
- **Langkah Investigasi**:
  ```bash
  # 1. Periksa status unit systemd
  sudo systemctl status cloudflared
  
  # 2. Periksa log daemon
  journalctl -u cloudflared -n 50 --no-pager
  
  # 3. Verifikasi apakah service lokal mendengarkan pada target port
  ss -tulpn | grep :8080
  curl -I http://127.0.0.1:8080
  ```

### Masalah 3: User Ditendang Berulang Kali / Access Login Loop
- **Diagnosis**: Masalah validasi cookie pada browser, domain cookie samesite mismatch, atau ketidakcocokan jam sistem origin/klien (Clock Skew) lebih dari 300 detik saat memverifikasi klaim JWT `exp` dan `iat`.
- **Solusi**: Sinkronisasi NTP pada host origin dan workstation klien (`chrony` / `systemd-timesyncd`). Pastikan browser tidak memblokir Third-Party Storage partitioning untuk domain auth.

---

## 18. Exercise
Selesaikan skenario praktikum berikut secara mandiri:
1. Jalankan sebuah Nginx container lokal di port `8085` dengan pesan kustom *"Environment Test ZTNA"*.
2. Buat Cloudflare Tunnel via CLI bernama `lab-exercise-tunnel`.
3. Hubungkan domain publik pengujian Anda (misal: `test-ztna.domainanda.com`) ke instance Nginx lokal tersebut.
4. Terapkan Cloudflare Access Policy:
   - Akses hanya diberikan untuk alamat email pribadi Anda.
   - Akses harus meminta One-Time PIN (OTP).
5. Buktikan bahwa:
   - Mengakses langsung via IP publik mesin Anda gagal/ditolak router.
   - Mengakses via `https://test-ztna.domainanda.com` memunculkan halaman Cloudflare Access login screen.
   - Setelah input OTP, halaman Nginx berhasil tampil.

---

## 19. Challenge
**Tantangan Arsitektur Multi-Tier Zero Trust**:
Rancang dan implementasikan infrastruktur menggunakan Terraform yang mengekspos:
1. **Aplikasi Web Admin (Port 3000)** via Cloudflare Tunnel.
2. **Aplikasi Database PostgreSQL (Port 5432)** yang berada di private network yang sama.
3. Klien hanya boleh mengakses database menggunakan perintah `psql` lokal melalui pembungkus Cloudflare WARP with Private Routing (IP Virtual Subnet `10.50.0.0/24`), **BUKAN** melalui koneksi TCP publik.
4. Buat rule Gateway Network Policy yang memblokir semua koneksi `psql` di luar jam kerja (Senin-Jumat, 08:00 - 18:00 WIB) atau jika antivirus klien terdeteksi mati.

Dokumentasikan file Terraform dan capture log audit verifikasi koneksinya.

---

## 20. Summary
- **Cloudflare Zero Trust** mengubah model keamanan dari proteksi perimeter luar menjadi evaluasi identitas dan konteks perangkat secara berkelanjutan di level edge.
- **Cloudflare Tunnel (`cloudflared`)** meniadakan keharusan membuka port inbound, bertindak sebagai *egress-only secure proxy* yang menghubungkan infrastruktur privat ke edge Anycast global.
- **Cloudflare Access** menyaring pengguna melalui IdP integration dan menginspeksi Device Posture sebelum koneksi diteruskan ke origin.
- **WARP & Secure Web Gateway** melengkapi ekosistem dengan mengenkripsi traffic Layer 3/4 perangkat klien, menyaring resolusi DNS berbahaya, dan mendekripsi inspeksi L7 HTTP/HTTPS secara real-time guna mencegah kebocoran data.

---