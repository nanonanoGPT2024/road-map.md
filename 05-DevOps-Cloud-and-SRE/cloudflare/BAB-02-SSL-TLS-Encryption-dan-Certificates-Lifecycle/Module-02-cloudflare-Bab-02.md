# Bab 02: SSL/TLS Encryption & Certificates Lifecycle
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengonfigurasi dan Mengamankan Topologi Enkripsi Edge-to-Origin**: Memahami, mendesain, dan mengimplementasikan mode enkripsi Cloudflare dari *Edge* ke *Origin* secara mutlak (*Full Strict*) guna mengeliminasi celah *Man-in-the-Middle* (MitM) dan *SSL Strip attack*.
2. **Mengelola Siklus Hidup Sertifikat Digital (PKI Lifecycle)**: Mengorkestrasi provisioning, validasi, rotasi otomatis, dan pencabutan sertifikat untuk *Universal SSL*, *Advanced Certificate Manager* (ACM), *Custom Certificates*, serta *Cloudflare Origin CA*.
3. **Mengimplementasikan dan Mengamankan Protokol Lanjutan**: Menerapkan TLS 1.3, *0-RTT (Early Data)* dengan mitigasi *Replay Attack*, *Encrypted Client Hello* (ECH), dan kriptografi pasca-kuantum (*Hybrid Post-Quantum Cryptography - X25519Kyber768*).
4. **Menerapkan Zero-Trust Edge Security**: Mengonfigurasi *Mutual TLS* (mTLS) menggunakan Cloudflare API Shield dan *Authenticated Origin Pulls* (AOP) untuk menjamin otentikasi dua arah (*cryptographic identity assertion*).
5. **Mendesain Arsitektur *Keyless SSL***: Mengonfigurasi terminasi TLS di Cloudflare Edge tanpa membagikan *private key* perusahaan, mengintegrasikan Cloudflare Key Server dengan *Hardware Security Module* (HSM) on-premise untuk kepatuhan regulasi finansial (PCI-DSS 4.0 / FIPS 140-2 Level 3).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Fondasi Kriptografi Asimetris & PKI**: Public/Private Key, X.509 standard, Certificate Authority (CA) hierarchical trust path, Intermediate CAs, OCSP Stapling, dan CRL.
*   **Protokol Transport Security**: Alur jabat tangan (handshake flow) TLS 1.2 vs TLS 1.3, Diffie-Hellman Ephemeral (DHE/ECDHE), ALPN (Application-Layer Protocol Negotiation), dan Cipher Suites (AES-GCM, ChaCha20-Poly1305).
*   **Jaringan & DNS Lanjutan**: DNS Record types (A, AAAA, CNAME, CAA, TLSA), TCP 3-way handshake, routing BGP Anycast, serta konsep Reverse Proxy.
*   **Administrasi Sistem & Web Server**: Konfigurasi Nginx/Envoy proxy, OpenSSL CLI, dan implementasi otomasi via cURL/Bash/Terraform.

---

### 3. Concept & Internal Architecture

Cloudflare beroperasi sebagai *Reverse Proxy* berbasis **BGP Anycast**. Arsitektur ini membagi koneksi TLS end-to-end menjadi dua segmen jaringan yang sepenuhnya terisolasi:
1. **Segmen Eyeball-to-Edge**: Koneksi antara *Client/Browser* menuju Cloudflare Edge Server terdekat (Anycast Node).
2. **Segmen Edge-to-Origin**: Koneksi antara Cloudflare Edge Server menuju *Origin Server* milik infrastruktur aplikasi.

```
+---------------+              +-------------------------+              +---------------+
|    Eyeball    |   TLS Leg 1  |     Cloudflare Edge     |   TLS Leg 2  |    Origin     |
|   (Client)    |<============>| (Anycast Terminating    |<============>|  Web Server/  |
|               |  (Universal/ |  Proxy & Inspection)    | (Origin CA/  | Load Balancer |
|               |   ACM/Custom)|                         | Full Strict) |               |
+---------------+              +-------------------------+              +---------------+
```

#### A. Taksonomi Mode Enkripsi Edge-to-Origin Cloudflare

Koneksi TLS Leg 2 mendefinisikan postur keamanan origin secara fundamental:
*   **Off**: Lalu lintas dari Cloudflare Edge ke Origin dialirkan secara *plaintext* (HTTP port 80). Jika client meminta HTTPS, Cloudflare mendegradasi paket di Leg 2.
*   **Flexible**: Komunikasi Eyeball-to-Edge terenkripsi (HTTPS), namun komunikasi Edge-to-Origin tetap menggunakan *plaintext* (HTTP port 80). 
    *   *Security Risk*: Lalu lintas melintasi jaringan publik tanpa enkripsi. Rentan terhadap sniffing oleh ISP/transitory backbone, packet injection, dan berpotensi memicu *infinite redirect loop* jika origin melakukan *force-HTTPS*.
*   **Full**: Edge-to-Origin menggunakan enkripsi TLS (HTTPS port 443), tetapi Cloudflare **tidak memvalidasi validitas sertifikat origin**. Sertifikat *self-signed*, sertifikat kedaluwarsa, atau sertifikat dengan Subject Alternative Name (SAN) yang salah akan tetap diterima.
    *   *Security Risk*: Rentan terhadap active Man-in-the-Middle (MitM) jika DNS/IP origin dibajak via BGP spoofing atau DNS poisoning.
*   **Full (Strict)**: Cloudflare memverifikasi rantai sertifikat (*certificate chain*) pada origin server secara ketat. Validasi mencakup:
    *   Sertifikat ditandatangani oleh Public CA tepercaya atau Cloudflare Origin CA.
    *   Sertifikat belum kedaluwarsa.
    *   Hostname pada request (`Host` header atau `SNI`) cocok dengan SAN yang tercantum dalam sertifikat origin.
*   **Strict (SSL-Only Origin Pull)**: Mengunci seluruh konektivitas upstream hanya melalui protokol TLS dengan port yang ditentukan, menolak fallback ke port HTTP/80 secara eksplisit.

#### B. Anatomi Arsitektur Keyless SSL

Bagi institusi finansial atau industri dengan regulasi ketat, menyimpan *private key* di infrastruktur pihak ketiga (termasuk Cloudflare Edge) dilarang oleh regulasi kepatuhan internal. Cloudflare mengatasi dilema ini melalui **Keyless SSL**.

```
Client                         Cloudflare Edge                          Origin Server
  |                                   |                                       |
  |-------- 1. ClientHello ---------->|                                       |
  |                                   |                                       |
  |                                   |--- Lookup Session / Cert              |
  |                                   |    (Public Key Only)                  |
  |<------- 2. ServerHello, ----------|                                       |
  |         Certificate, Parameters   |                                       |
  |                                   |                                       |
  |-- 3. Key Exchange (ECDHE/RSA) --->|                                       |
  |                                   |                                       |
  |                                   |==== 4. Cryptographic Sign/Decrypt ===>| [Key Server]
  |                                   |     Mutual TLS Connection (mTLS)      |      |
  |                                   |                                       | (Internal HSM
  |                                   |<=== 5. Cryptographic Signature =======|  Holds Private
  |                                   |                                       |      Key)
  |                                   |--- Complete Session Secret            |
  |<------- 6. Finished (Encrypted) --|    Derivation                         |
  |                                   |                                       |
  |<======= 7. Application Data =====>|<====== 8. Application Data ==========>|
  |         (Standard HTTPS)          |        (Upstream TLS)                 |
```

1. Edge Server memegang sertifikat publik klien, tetapi **tidak memiliki private key**.
2. Selama fase handshake (misal ECDHE), Edge Server membutuhkan operasi penandatanganan kriptografis (*cryptographic signature*) menggunakan private key untuk membuktikan kepemilikan sertifikat kepada Client.
3. Edge Server membungkus payload penandatanganan dan mengirimkannya secara aman via mTLS tunnel ke **Key Server** yang di-host di datacenter on-premise klien.
4. Key Server meneruskan permintaan ke Hardware Security Module (HSM) lokal, mengeksekusi operasi kriptografi `Sign`, dan mengembalikan hasilnya ke Edge Server.
5. Edge Server menyelesaikan TLS handshake dengan Client. Komunikasi data aplikasi selanjutnya didekripsi secara lokal di memori volatile Edge menggunakan *ephemeral symmetric key* (AES-GCM/ChaCha20) tanpa mengekspos master private key origin.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Fungsinya (What) |
| :--- | :--- | :--- |
| **Full (Strict) Mode** | Mencegah interceptor jaringan melakukan spoofing IP upstream dan mendekripsi traffic produksi antara CDN dan Origin. | Enkripsi end-to-end dengan validasi chain of trust X.509 penuh di kedua leg. |
| **Origin CA Certificates** | Public CA komersial berbiaya mahal dan memiliki masa berlaku pendek (90 hari). Self-signed certs tidak aman dari MitM. | Sertifikat gratis berdurasi hingga 15 tahun yang diterbitkan Cloudflare, khusus divalidasi oleh Edge Cloudflare. |
| **Authenticated Origin Pulls (AOP)** | Origin publik dapat di-bypass oleh attacker jika IP asli (*Origin IP leak*) diketahui, menghindari WAF Cloudflare. | Otentikasi mTLS di mana Origin hanya menerima koneksi TLS jika Cloudflare menyajikan sertifikat klien resmi Cloudflare. |
| **Advanced Certificate Manager (ACM)** | Universal SSL hanya mencakup sub-domain level satu (`*.domain.tld`) dan tidak mengizinkan custom SAN bertingkat. | Fasilitas penerbitan sertifikat kustom multi-tier, multi-SAN, pemilihan CA (Let's Encrypt / DigiCert / Google Trust), dan kontrol masa berlaku. |
| **TLS 1.3 0-RTT** | Memangkas latensi koneksi ulang (*round-trip time*) menjadi 0 ms untuk client berulang pada jaringan mobile. | Pengiriman payload HTTP pertama bersamaan dengan TLS handshake message (`ClientHello Early Data`). |
| **Hybrid Post-Quantum TLS** | Komputer kuantum di masa depan dapat memecahkan rekaman traffic masa kini yang dienkripsi RSA/ECC (*Harvest Now, Decrypt Later*). | Menggabungkan pertukaran kunci klasik (X25519) dengan algoritma post-quantum lattice-based (Kyber768/ML-KEM). |

---

### 5. How (Workflow Detail)

#### Siklus Hidup Sertifikat Origin CA & Cloudflare Full Strict

1. **Inisiasi Kunci**: Origin Administrator membuat *Private Key* (256-bit ECDSA atau 2048/4096-bit RSA) dan *Certificate Signing Request* (CSR) secara lokal di dalam server origin.
2. **Penerbitan via Cloudflare API**: CSR dikirimkan ke Cloudflare Origin CA API. Cloudflare menandatangani CSR tersebut menggunakan *Cloudflare Origin Intermediate CA* dan mengembalikan sertifikat X.509 (durasi 7 hari s.d. 15 tahun).
3. **Pemasangan di Web Server**: Sertifikat dipasang pada Nginx/Envoy bersama dengan Cloudflare Origin CA Root Bundle.
4. **Konfigurasi Edge Rule**:
   * Mode enkripsi zone diatur ke `strict`.
   * Minimum TLS Version di-lock ke `TLS 1.2` atau `TLS 1.3`.
   * Strict SNI & TLS Cipher Suites disematkan.
5. **Otentikasi Dua Arah (AOP)**: Mengaktifkan Authenticated Origin Pulls tingkat zona atau per-hostname menggunakan sertifikat klien kustom.
6. **Handshake Execution**: Saat request masuk:
   * Client mengeksekusi TLS 1.3 handshake dengan Cloudflare Edge.
   * Edge menginisiasi TLS connection ke Origin IP dengan menyertakan Client Certificate (AOP).
   * Origin memvalidasi sertifikat Edge via Cloudflare Root Certificate.
   * Edge memvalidasi sertifikat Origin via Origin CA trust store.
   * Terowongan kriptografis aman terbentuk.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengawalan Dokumen Diplomatik
*   **Flexible SSL**: Anda mengirim koper terkunci (HTTPS) dari Jakarta ke pos konsulat Singapura (Edge). Namun, dari konsulat ke markas pusat di Jenewa (Origin), dokumen dikeluarkan dan dibawa dengan tas belanja kresek terbuka (HTTP). Siapa pun di rute transit dapat membaca dan mengganti isinya.
*   **Full SSL**: Dokumen dibawa dari konsulat ke markas pusat dalam koper terkunci, tetapi penjaga markas pusat mengenakan seragam palsu yang dibeli di pasar gelap (Self-signed cert). Kurir konsulat tidak memeriksa identitasnya dan langsung menyerahkan koper tersebut ke pihak yang salah.
*   **Full (Strict) SSL**: Kurir konsulat hanya akan menyerahkan koper jika penerima di markas pusat menunjukkan tanda pengenal biometrik resmi dari markas besar (Valid Public/Origin CA + Valid SAN).
*   **Authenticated Origin Pulls (AOP)**: Penjaga pintu markas pusat hanya mau membuka gerbang jika kurir konsulat juga menunjukkan tanda pengenal resmi bertanda tangan direktur jenderal (Client Certificate Validation).

#### Diagram Validasi Arsitektur Dual-Leg TLS & AOP

```
CLIENT (Browser)                                CLOUDFLARE EDGE                                  ORIGIN SERVER
      |                                                |                                                |
      |=== 1. TLS Handshake (Universal/ACM) ==========>|                                                |
      |    - SNI: api.enterprise.internal              |                                                |
      |    - TLS 1.3 Negotiation                       |                                                |
      |<== 2. Handshake Completed =====================|                                                |
      |                                                |                                                |
      |                                                |=== 3. Inisiasi TLS Handshake (Leg 2) =========>|
      |                                                |    - Menyajikan SNI: api.enterprise.internal   |
      |                                                |    - Menyajikan AOP Client Certificate ------->|--+ [Validasi AOP]
      |                                                |                                                |  | Verifikasi
      |                                                |<-- 4. Kirim Origin Certificate ----------------|<-+ Client Cert
      |                                                |       (Cloudflare Origin CA Signed)            |    via CF CA
      |                                                |--+                                             |
      |                                                |  | [Validasi Full Strict]                      |
      |                                                |  | 1. Issuer == Cloudflare Origin CA           |
      |                                                |  | 2. Hostname matches SAN                     |
      |                                                |  | 3. Expiry date valid                        |
      |                                                |<-+                                             |
      |                                                |<== 5. Leg 2 Handshake Completed ==============>|
      |                                                |                                                |
      |=== 6. HTTP GET /v1/transactions ==============>|=== 7. Proxied GET /v1/transactions ===========>|
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Terraform: Otomasi TLS Hardening & Provisioning Sertifikat

```hcl
# main.tf
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "Target Cloudflare Zone ID"
}

# 1. Konfigurasi Setting TLS Tingkat Enterprise
resource "cloudflare_zone_settings_override" "tls_hardening" {
  zone_id = var.zone_id

  settings {
    ssl                      = "strict"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    zero_rtt                 = "off" # Dinonaktifkan untuk mitigasi Replay Attack pada endpoint transaksional
    always_use_https         = "on"
    http2                    = "on"
    http3                    = "on"
    opportunistic_encryption = "on"
    automatic_https_rewrites = "on"
    universal_ssl            = "on"
    security_header {
      enabled            = true
      preload            = true
      max_age            = 31536000 # 1 Tahun HSTS
      include_subdomains = true
      nosniff            = true
    }
  }
}

# 2. Pembuatan Kunci Privat Asimetris (ECDSA P-256)
resource "tls_private_key" "origin_key" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

# 3. Pembuatan CSR untuk Origin Server
resource "tls_cert_request" "origin_csr" {
  private_key_pem = tls_private_key.origin_key.private_key_pem

  subject {
    common_name  = "api.enterprise-domain.internal"
    organization = "Enterprise Core Infrastructure"
  }

  dns_names = [
    "api.enterprise-domain.internal",
    "*.enterprise-domain.internal"
  ]
}

# 4. Penerbitan Sertifikat Cloudflare Origin CA via API
resource "cloudflare_origin_ca_certificate" "origin_cert" {
  csr                = tls_cert_request.origin_csr.cert_request_pem
  hostnames          = ["api.enterprise-domain.internal", "*.enterprise-domain.internal"]
  request_type       = "origin-ecc"
  requested_validity = 5475 # 15 Tahun
}

# 5. Output sertifikat dan kunci untuk provisioning Nginx/Secret Manager
output "origin_certificate_pem" {
  value       = cloudflare_origin_ca_certificate.origin_cert.certificate
  sensitive   = false
}

output "origin_private_key_pem" {
  value       = tls_private_key.origin_key.private_key_pem
  sensitive   = true
}
```

#### B. Konfigurasi Produksi Nginx: Origin CA, Authenticated Origin Pulls, dan IP Whitelisting

```nginx
# /etc/nginx/conf.d/secure-origin.conf

# Definisikan rate limit zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;

# Ambil Cloudflare Client IP asli dari CF-Connecting-IP
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
set_real_ip_