# Modul 01: SSL/TLS Encryption, Origin CA, & Custom Certificates Lifecycle

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengidentifikasi dan mengonfigurasi spektrum mode enkripsi edge-to-origin Cloudflare (Off, Flexible, Full, Full Strict) secara tepat guna mencegah kerentanan *man-in-the-middle* (MitM) dan *infinite redirect loops*.
- Mengimplementasikan automasi penerbitan dan rotasi sertifikat menggunakan Universal SSL, Advanced Certificate Manager (ACM), Cloudflare Origin CA, dan Custom Certificates.
- Membedah arsitektur Keyless SSL untuk memenuhi mandat kepatuhan regulasi (FIPS/PCI-DSS/HSM on-premise) tanpa mengorbankan performa terminasi edge.
- Merancang dan mengeksekusi arsitektur Zero Trust API protection berbasis mutual TLS (mTLS) di layer Edge dan Origin.
- Mengonfigurasi hardening protokol TLS mencakup Minimum TLS Version, Cipher Suite tailoring, TLS 1.3 0-RTT handling, dan HTTP Strict Transport Security (HSTS).

---

## 2. Prerequisite
- Pemahaman mendalam tentang TCP 3-way handshake dan cryptographic handshake TLS 1.2 vs TLS 1.3 (ClientHello, ServerHello, Key Exchange, Finished).
- Familiaritas dengan Public Key Infrastructure (PKI), format sertifikat X.509 (PEM, DER, PKCS#12), Certificate Authority (CA), intermediate certificates, dan CRL/OCSP stapling.
- Pengalaman administrasi web server (NGINX/Apache/Envoy) dan CLI tooling (`openssl`, `curl`, `cfssl`).
- Akses ke akun Cloudflare tingkat Enterprise/Business (atau pemahaman fungsionalitas fiturnya) serta Terraform CLI v1.5+.

---

## 3. Concept
Dalam topologi reverse-proxy terdistribusi Cloudflare, koneksi terbagi menjadi dua segmen jaringan yang independen:
1. **Edge/Client Leg**: Koneksi antara klien (browser/mobile app) dan Edge Server terdekat Cloudflare Anycast.
2. **Origin Leg**: Koneksi antara Edge Server Cloudflare dan upstream web server (Origin Infrastructure).

```
[ Client / Browser ] <--- (Client Leg: TLS 1.2/1.3) ---> [ Cloudflare Edge ] <--- (Origin Leg: TLS) ---> [ Origin Server ]
```

Manajemen sertifikat Cloudflare mengabstraksi kompleksitas Client Leg melalui sertifikat tepi otomatis (Universal SSL / ACM) atau sertifikat kustom yang diunggah enterprise. Di sisi lain, keamanan Origin Leg sepenuhnya ditentukan oleh mode enkripsi yang dipilih serta sertifikat yang dipasang di origin (Origin CA atau Public CA). Kegagalan memetakan kriptografi pada kedua leg ini menyebabkan degradasi keamanan kritis, pembajakan sesi, atau kegagalan koneksi total (*downtime*).

---

## 4. Why
Mayoritas insiden keamanan di layer reverse proxy bermula dari kesalahpahaman mode enkripsi:
- **Ilusi Keamanan (The "Flexible" Illusion)**: Mode `Flexible` hanya mengenkripsi leg klien, sementara leg origin menggunakan HTTP cleartext. Paket data melintasi internet publik tanpa proteksi, rentan terhadap intercept ISP, manipulasi BGP, dan sniffing.
- **Kepatuhan dan Audit Regulasi**: Standar PCI-DSS 4.0 dan HIPAA mewajibkan enkripsi end-to-end dengan verifikasi sertifikat yang valid dan cipher modern. Menggunakan mode yang tidak memvalidasi identitas server (seperti `Full` non-strict) melanggar mandat integritas origin.
- **Operasional dan Manajemen Sertifikat**: Sertifikat publik di origin memerlukan siklus perpanjangan ACME (Let's Encrypt) yang sering kali gagal akibat tantangan HTTP-01 terblokir firewall atau routing Anycast. Penggunaan Cloudflare Origin CA menyelesaikan kendala ini dengan masa berlaku hingga 15 tahun dan proteksi otomatis.
- **Zero Trust API Auth**: Otentikasi berbasis token (JWT/API Key) rentan terhadap kebocoran di level aplikasi. Menggabungkan otentikasi kriptografis mTLS di layer transport mengeliminasi akses unauthorized sebelum request mencapai komputasi backend.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Cloudflare SSL/TLS Modes
Cloudflare menyediakan 4 mode utama yang mendefinisikan perilaku Origin Leg:

| Mode | Enkripsi Client Leg | Enkripsi Origin Leg | Validasi Sertifikat Origin | Risiko Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| **Off** | Tidak (HTTP) | Tidak (HTTP) | Tidak ada | Data transit terbuka total. |
| **Flexible** | Ya (HTTPS) | Tidak (HTTP port 80) | Tidak ada | Intersepsi MitM pada Origin Leg; potensi *redirect loop*. |
| **Full** | Ya (HTTPS) | Ya (HTTPS port 443) | **TIDAK** (menerima self-signed / expired / mismatch) | MitM via ARP spoofing / DNS hijacking pada koneksi origin. |
| **Full (Strict)** | Ya (HTTPS) | Ya (HTTPS port 443) | **YA** (Valid CA publik atau Cloudflare Origin CA) | Enkripsi Zero-Trust end-to-end yang aman. |

#### Full vs Full (Strict) Handshake Mechanics
Pada mode **Full**, Cloudflare menginisiasi TLS handshake ke origin, namun mengabaikan validitas rantai kepercayaan (chain of trust) X.509. Edge menerima sertifikat self-signed, CN/SAN mismatch, atau sertifikat kedaluwarsa.
Pada mode **Full (Strict)**, Cloudflare bertindak sebagai client TLS yang ketat:
1. Memverifikasi bahwa Subject Alternative Name (SAN) cocok dengan domain origin yang dituju.
2. Memverifikasi bahwa sertifikat ditandatangani oleh CA publik tepercaya atau Cloudflare Origin CA.
3. Memastikan masa berlaku sertifikat (Not Before / Not After) valid.
Jika validasi gagal, Cloudflare memutus koneksi dan menampilkan **Error 526: Invalid SSL Certificate**.

### 5.2 Universal SSL vs Advanced Certificate Manager (ACM) vs Custom Certificates
- **Universal SSL**: Disediakan secara gratis untuk setiap domain di Cloudflare. Menerbitkan sertifikat multi-domain (SAN bersama pelanggan lain pada domain gratis, atau dedicated pada Business/Enterprise) dari CA publik (Let's Encrypt, Google Trust Services, SSL.com). Tidak mendukung kustomisasi masa berlaku atau sub-domain bertingkat banyak (`*.corp.staging.example.com`).
- **Advanced Certificate Manager (ACM)**: Fitur berbayar yang memberikan kontrol fleksibel:
  - Penerbitan sertifikat dedicated untuk satu domain/subdomain.
  - Dukungan wildcard multi-level (`*.*.example.com`).
  - Pemilihan CA penerbit spesifik (misal: Let's Encrypt, DigiCert, Google Trust Services).
  - Kontrol masa berlaku sertifikat (30, 90, atau 365 hari) dan algoritma Private Key (ECDSA P-256 vs RSA 2048).
- **Custom Certificates (Business & Enterprise)**: Memungkinkan upload sertifikat X.509 dan private key milik organisasi sendiri (misal: Extended Validation/EV certificates atau sertifikat yang dikeluarkan oleh CA korporat komersial). Cloudflare menangani terminasi edge menggunakan key tersebut.

### 5.3 Cloudflare Origin CA
Cloudflare Origin CA adalah Internal CA privat yang dioperasikan oleh Cloudflare untuk menandatangani sertifikat origin secara gratis.
- **Kelebihan**: Masa aktif fleksibel (7 hari hingga 15 tahun), format SAN otomatis, tidak bergantung pada tantangan ACME publik.
- **Trust Anchor**: Sertifikat Origin CA hanya dipercaya oleh Edge Proxy Cloudflare. Klien publik yang mengakses origin secara langsung via IP akan menerima peringatan *untrusted certificate*. Hal ini secara inheren memaksa trafik harus melewati Cloudflare Edge (menghalau *origin bypass*).

### 5.4 Keyless SSL (Enterprise)
Dirancang untuk industri finansial, telekomunikasi, dan perbankan yang terikat regulasi penyimpanan Private Key (misal: FIPS 140-2 Level 3 HSM on-premise) dan dilarang mengunggah private key ke cloud.
- **Alur Kerja**:
  1. Klien mengirim `ClientHello` ke Cloudflare Edge.
  2. Cloudflare mengirim `ServerHello` dan sertifikat publik enterprise ke Klien.
  3. Klien membalas dengan cryptographic challenge (misal: enkripsi pre-master secret via RSA atau pertukaran kunci ephemeral ECDHE yang memerlukan tanda tangan private key).
  4. Cloudflare Edge mengirimkan payload cryptographic challenge tersebut ke **Keyless Server** internal pelanggan melalui terowongan terenkripsi (mTLS).
  5. Keyless Server meminta HSM on-premise melakukan operasi penandatanganan kriptografis dengan private key lokal.
  6. Hasil tanda tangan dikembalikan ke Cloudflare Edge untuk menyelesaikan TLS Handshake dengan klien.
  7. Private Key tidak pernah meninggalkan infrastruktur pelanggan.

```
+--------+                 +-----------------+                 +-----------------------+
| Client |                 | Cloudflare Edge |                 | Customer Keyless/HSM  |
+---+----+                 +--------+--------+                 +-----------+-----------+
    |                               |                                      |
    |---- 1. ClientHello ---------->|                                      |
    |<--- 2. ServerHello + Cert ----|                                      |
    |                               |                                      |
    |---- 3. Key Exchange Challenge>|                                      |
    |    (Requires PrivKey Sign)    |---- 4. Forward Op (mTLS) ----------->|
    |                               |                                      | Perform Decrypt/
    |                               |                                      | Sign inside HSM
    |                               |<--- 5. Signature Result -------------|
    |                               |                                      |
    |<--- 6. Finished (Session Key)-|                                      |
    |<===> 7. Symmetric Encrypted Traffic <===============================>|
```

### 5.5 Mutual TLS (mTLS) for API Protection
Berbeda dengan standard TLS (one-way authentication di mana hanya server yang membuktikan identitasnya), mTLS mewajibkan kedua pihak saling membuktikan identitas kriptografis:
1. **Edge-to-Origin mTLS (Authenticated Origin Pulls / AOP)**: Origin memvalidasi bahwa setiap koneksi HTTPS yang masuk benar-benar berasal dari Cloudflare Edge, bukan penyerang yang mengetahui alamat IP origin.
2. **Client-to-Edge mTLS (API Shield)**: Klien API (mobile app, IoT device, server B2B) wajib menyertakan X.509 client certificate yang valid. Edge Cloudflare memvalidasi client cert terhadap Root/Intermediate CA internal pelanggan sebelum memproses request ke WAF/Origin.

### 5.6 Minimum TLS Version & Cipher Suite Tailoring
- **Minimum TLS Version**: Membatasi negosiasi protokol paling rendah yang diterima Edge (TLS 1.0, 1.1, 1.2, atau 1.3). Deprekasi TLS 1.0 dan 1.1 wajib dilakukan untuk kepatuhan PCI-DSS v4.0.
- **Cipher Suite Selection**: Administrator Enterprise dapat secara eksplisit membatasi daftar cipher yang didukung, mengeliminasi cipher CBC yang rentan (seperti dalam serangan POODLE/BEAST) dan memprioritaskan authenticated ciphers seperti `AEAD` (AES-GCM, ChaCha20-Poly1305).

---

## 6. How
Implementasi enkripsi end-to-end zero trust dilakukan dengan tahapan:
1. **Konfigurasi Origin Web Server**: Buat pasangan kunci dan CSR, lalu terbitkan sertifikat Cloudflare Origin CA.
2. **Pasang Sertifikat Origin**: Pasang sertifikat dan root certificate Cloudflare Origin CA pada NGINX/Envoy/Apache.
3. **Hardening Mode SSL/TLS di Cloudflare**: Alihkan pengaturan mode SSL/TLS dari `Flexible` / `Full` ke `Full (Strict)`.
4. **Aktifkan Authenticated Origin Pulls (AOP)**: Konfigurasi Cloudflare dan web server agar origin hanya menerima TLS connection yang menyajikan sertifikat klien Cloudflare.
5. **Hardening Edge TLS Parameter**: Tetapkan Minimum TLS ke versi 1.2/1.3, aktifkan HTTP Strict Transport Security (HSTS), dan nonaktifkan cipher yang usang.

---

## 7. Analogy
Bayangkan sistem pengiriman logistik brankas berharga:
- **Off Mode**: Dokumen dikirim menggunakan amplop terbuka transparan di seluruh rute. Siapa pun di jalan bisa membaca dan menyalinnya.
- **Flexible Mode**: Dokumen dibawa dari tangan pengirim ke pos Cloudflare di dalam mobil lapis baja (Client HTTPS). Namun, dari pos Cloudflare ke gudang tujuan (Origin), dokumen dikeluarkan dari brankas dan dibawa oleh kurir bersepeda motor menggunakan map plastik biasa (HTTP port 80).
- **Full Mode**: Dari pos Cloudflare ke gudang tujuan digunakan mobil lapis baja, tetapi penjaga gudang Cloudflare tidak memeriksa apakah gudang penerima adalah gudang resmi atau gudang palsu milik sindikat kriminal yang menggunakan plang nama palsu (Self-signed/invalid certificate diterima).
- **Full (Strict) Mode**: Mobil lapis baja digunakan di seluruh rute perjalanan, dan satpam di kedua pos memeriksa paspor, stempel verifikasi negara, serta biometrik resmi penerima sebelum dokumen diserahkan.
- **mTLS**: Bukan hanya penerima yang harus menunjukkan identitasnya, kurir pengirim pun wajib menunjukkan kartu identitas berkode khusus untuk membuka gerbang gudang.

---

## 8. Diagram (ASCII)

### Detailed Origin Connection Negotiation & AOP Handshake

```
+----------------------------------------------------------------------------------------------------+
|                                    CLOUDFLARE EDGE TO ORIGIN HANDSHAKE                             |
+----------------------------------------------------------------------------------------------------+

   Cloudflare Edge                                                                 Origin Server
          |                                                                               |
          |  1. TCP SYN (Port 443)                                                        |
          |------------------------------------------------------------------------------>|
          |  2. TCP SYN-ACK                                                               |
          |<- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - |
          |  3. TCP ACK                                                                   |
          |------------------------------------------------------------------------------>|
          |                                                                               |
          |  4. TLS ClientHello (SNI: api.enterprise.internal, Supported Ciphers)        |
          |------------------------------------------------------------------------------>|
          |                                                                               |
          |  5. TLS ServerHello + Server Certificate (Origin CA)                          |
          |     + [Optional AOP] CertificateRequest (Ask CF for Client Cert)              |
          |<- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - |
          |                                                                               |
  [Verifies Server Cert:]                                                                 |
  - Matches SAN? YES                                                                      |
  - Issued by CF Origin CA? YES                                                           |
  - Expired? NO                                                                           |
          |                                                                               |
          |  6. [If AOP enabled] Client Certificate (CF Pull Cert) + Key Exchange         |
          |------------------------------------------------------------------------------>|
          |                                                                               |
          |                                                         [Verifies Client Cert:]
          |                                                         - Signed by CF Root CA? YES
          |                                                         - Handshake Authorized? YES
          |                                                                               |
          |  7. TLS Finished (Encrypted Session Established)                              |
          |<=============================================================================>|
          |                                                                               |
          |  8. Encrypted HTTP Request (GET /api/v1/settlement)                          |
          |------------------------------------------------------------------------------>|
```

---

## 9. Simple Example
Memvalidasi cipher suites dan TLS version yang didukung oleh edge domain menggunakan OpenSSL:

```bash
# Uji coba apakah domain mendukung koneksi TLS 1.0 (Harus ditolak jika di-hardened)
openssl s_client -connect example.com:443 -tls1 -servername example.com

# Verifikasi koneksi TLS 1.3 dengan Cipher Suite AES-256-GCM
openssl s_client -connect example.com:443 -tls1_3 -ciphersuites TLS_AES_256_GCM_SHA384 -servername example.com
```

Output kegagalan jika hardening berhasil:
```text
CONNECTED(00000003)
140735234123008:error:1409442E:SSL routines:ssl3_read_bytes:tlsv1 alert protocol version:../ssl/record/rec_layer_s3.c:1544:SSL alert number 70
---
no peer certificate available
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

### 10.1 Automasi Terraform: ACM, Zone Settings, HSTS, dan Custom Ciphers

```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "Target Zone ID Cloudflare"
}

# 1. Enforcement Mode Full (Strict) & Minimum TLS 1.2
resource "cloudflare_zone_settings_override" "security_hardening" {
  zone_id = var.zone_id

  settings {
    ssl                      = "strict"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    zero_rtt                 = "off" # Mitigasi serangan Replay Attack untuk stateful API
    always_use_https         = "on"
    opportunistic_encryption = "on"
    automatic_https_rewrites = "on"

    # HTTP Strict Transport Security (HSTS)
    security_header {
      enabled            = true
      max_age            = 31536000 # 1 Tahun
      include_subdomains = true
      preload            = true
      nosniff            = true
    }

    # Restriksi Cipher Suite Modern (Modern Ciphers Only)
    ciphers = [
      "ECDHE-ECDSA-AES128-GCM-SHA256",
      "ECDHE-ECDSA-AES256-GCM-SHA384",
      "ECDHE-RSA-AES128-GCM-SHA256",
      "ECDHE-RSA-AES256-GCM-SHA384",
      "ECDHE-ECDSA-CHACHA20-POLY1305",
      "ECDHE-RSA-CHACHA20-POLY1305"
    ]
  }
}

# 2. Advanced Certificate Manager (ACM) Dedicated Multi-Domain
resource "cloudflare_certificate_pack" "dedicated_pack" {
  zone_id               = var.zone_id
  type                  = "advanced"
  hosts                 = ["example.com", "*.example.com", "secure.internal.example.com"]
  validation_method     = "txt"
  validity_days         = 90
  certificate_authority = "lets_encrypt"
  cloudflare_branding   = false
}

# 3. Authenticated Origin Pulls (AOP) Global Enforcement
resource "cloudflare_authenticated_origin_pulls" "aop_zone" {
  zone_id = var.zone_id
  enabled = true
}
```

### 10.2 Pembuatan Sertifikat Cloudflare Origin CA via Cloudflare API

```bash
# Request CSR signing ke Cloudflare Origin CA API
curl -s -X POST "https://api.cloudflare.com/client/v4/certificates" \
     -H "X-Auth-Email: ops@example.com" \
     -H "X-Auth-Key: ${CLOUDFLARE_GLOBAL_API_KEY}" \
     -H "Content-Type: application/json" \
     -d '{
       "hostnames": ["example.com", "*.example.com"],
       "requested_validity": 5475,
       "request_type": "origin-rsa",
       "csr": "-----BEGIN CERTIFICATE REQUEST-----\nMIICvDCCAaQCAQAwdzELMAkGA1UEBhMCVVM...[TRUNCATED CSR]...==\n-----END CERTIFICATE REQUEST-----"
     }' | jq -r '.result.certificate' > /etc/ssl/certs/origin_ca.pem
```

### 10.3 Konfigurasi Origin NGINX (Strict Origin CA + Authenticated Origin Pulls)

```nginx
# Unduh Cloudflare AOP Public Certificate:
# curl -s https://developers.cloudflare.com/ssl/static/authenticated_origin_pull_ca.pem -o /etc/nginx/certs/cf-aop.pem

server {
    listen 443 ssl http2;
    server_name example.com *.example.com;

    # Sertifikat Cloudflare Origin CA dan Private Key Lokal
    ssl_certificate         /etc/ssl/certs/origin_ca.pem;
    ssl_certificate_key     /etc/ssl/private/origin_key.key;

    # Enforce Authenticated Origin Pulls (mTLS)
    # Memverifikasi bahwa request dibawa oleh Cloudflare Client Cert
    ssl_client_certificate  /etc/nginx/certs/cf-aop.pem;
    ssl_verify_client       on;

    # TLS Engine Hardening
    ssl_protocols           TLSv1.2 TLSv1.3;
    ssl_ciphers             ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache       shared:SSL:10m;
    ssl_session_timeout     1d;
    ssl_session_tickets     off;

    location / {
        # Validasi header kustom atau teruskan traffic
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_pass http://internal_backend_upstream;
    }
}

# Blokir koneksi port 80 langsung
server {
    listen 80;
    server_name example.com *.example.com;
    return 301 https://$host$request_uri;
}
```

---

## 11. Real World Example
Sebuah institusi neobank ("Bank X") memiliki endpoint otorisasi core transaction: `https://api.bankx.co.id/v1/transfer`.
- **Kondisi Awal**: Menggunakan mode *Flexible*. Penyerang melakukan *BGP prefix hijacking* terhadap IP blok upstream cloud origin Bank X, mengarahkan koneksi port 80 dari edge Cloudflare ke server penyerang (karena Origin Leg adalah HTTP tanpa verifikasi). Akibatnya, payload otentikasi API dieksfiltrasi.
- **Solusi Arsitektur**:
  1. Diterapkan **Full (Strict)** menggunakan Cloudflare Origin CA dengan validasi SAN eksplisit.
  2. Implementasi **Client-to-Edge mTLS** via API Shield: Aplikasi mobile native Bank X menyimpan private key di Secure Enclave iOS / Android Keystore dan menyajikan client certificate saat handshake ke Edge.
  3. Implementasi **Zone-level Authenticated Origin Pulls**: Origin Firewall hanya menerima koneksi TLS dari Cloudflare Anycast IP range, dan NGINX di origin memvalidasi client cert Cloudflare.
  4. Menonaktifkan TLS 1.0, TLS 1.1, dan TLS 1.3 **0-RTT** guna mencegah mitigasi serangan *replay attack* pada endpoint finansial non-idempoten.

---

## 12. Trade-offs

| Parameter | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Origin Encryption** | *Flexible SSL* | *Full (Strict) SSL* | *Flexible* mempermudah deployment awal tanpa sertifikat di origin, namun membuka celah sniffing kritis dan memicu infinite redirect loops. *Full (Strict)* mewajibkan administrasi sertifikat di origin tetapi menjamin integritas data zero-trust. |
| **Client TLS Profile** | Mengizinkan TLS 1.0 - 1.1 | Enforce TLS 1.2+ Only | Kompatibilitas browser legacy/perangkat embedded tua vs Kepatuhan keamanan modern (PCI-DSS 4.0, NIST 800-52r2). Mematikan < TLS 1.2 memutuskan <0.1% traffic usang demi proteksi dari eksploitasi kriptografi. |
| **0-RTT (Early Data)** | *Enabled* | *Disabled* | *Enabled* mempercepat TLS 1.3 handshake (0 round trip time latency untuk request lanjutan), tetapi membuka kerentanan **Replay Attacks** terhadap HTTP POST request yang memproses mutasi state / transaksi pembayaran. |
| **Edge Certificates** | Universal SSL (Shared SAN) | Custom / Dedicated ACM | Universal gratis dan zero-touch, namun domain organisasi muncul berdampingan dengan domain publik lain di SAN list yang sama (berdampak pada persepsi brand enterprise) serta tidak bisa kustomisasi CA. |
| **Keyless SSL** | Keyless SSL (HSM On-Prem) | Cloud-Terminated Key | Keyless memberikan kontrol mutlak atas private key di hardware sendiri namun menambah *handshake latency overhead* (karena hop edge-ke-HSM saat handshake baru) dan kompleksitas infrastruktur terowongan key server. |

---

## 13. When To Use
- Gunakan **Full (Strict)** secara default pada seluruh domain dan production zone tanpa pengecualian.
- Gunakan **Cloudflare Origin CA** saat Anda membutuhkan sertifikat origin gratis jangka panjang (hingga 15 tahun) yang otomatis dipercaya oleh edge Cloudflare tanpa risiko limitasi ACME Let's Encrypt.
- Gunakan **Authenticated Origin Pulls (AOP)** jika backend server Anda terekspos ke internet publik dan Anda tidak dapat membatasi akses hanya melalui IP ACL/Firewall.
- Gunakan **Keyless SSL** saat divisi regulasi/legal atau klien enterprise mewajibkan bahwa Private Key cryptographic tidak boleh keluar dari On-Premises Hardware Security Module (HSM).
- Gunakan **Client-to-Edge mTLS (API Shield)** untuk komunikasi Machine-to-Machine (M2M), Microservice-to-Microservice, atau perlindungan native mobile client API.

---

## 14. When NOT To Use
- Jangan gunakan **Flexible SSL** dalam kondisi apa pun di sistem produksi modern. Mode ini hanya ditoleransi sementara saat pengujian migrasi awal pada origin server purba yang sama sekali tidak mampu menjalankan stack TLS.
- Jangan mengaktifkan **TLS 1.3 0-RTT Connection Resumption** pada endpoint yang menerima request non-idempoten (POST, PUT, DELETE) seperti sistem pembayaran atau checkout e-commerce tanpa proteksi replay di level aplikasi.
- Jangan gunakan **Cloudflare Origin CA** jika domain tersebut ditujukan untuk menerima koneksi langsung dari publik tanpa melalui proxy Cloudflare (misal: DNS records bypass / status "Grey Clouded"), karena browser akan mendeteksi *Untrusted CA*.

---

## 15. Common Mistakes
- **Redirect Loop Trap (ERR_TOO_MANY_REDIRECTS)**:
  Konfigurasi di Cloudflare diset ke `Flexible`, tetapi Origin NGINX dikonfigurasi `return 301 https://$host$request_uri;`.
  *Alur error*: Klien memanggil HTTPS -> Edge Cloudflare meneruskan via HTTP port 80 ke Origin -> Origin melihat HTTP dan membalas 301 Redirect ke HTTPS -> Klien memanggil HTTPS ke Edge kembali -> Loop tak berujung.
- **Origin Bypass dengan Mode Full Non-Strict**:
  Menganggap mode `Full` sudah aman padahal tidak memvalidasi identitas upstream. Penyerang dapat melakukan ARP Poisoning di datacenter upstream atau memanfaatkan poisoned internal DNS untuk menyajikan sertifikat self-signed palsu tanpa memicu alert.
- **Missing Root/Intermediate CA Bundle pada Custom Certificate**:
  Mengunggah leaf certificate ke Cloudflare Custom Certificate tanpa intermediate chain. Klien dengan trust-store ketat (seperti runtime Java atau perangkat Android versi tertentu) akan gagal melakukan handshake dengan error `SSLHandshakeException: PKIX path building failed`.
- **AOP Diaktifkan di Edge tetapi Belum Dikonfigurasi di Origin**:
  Ketika AOP diaktifkan di dashboard Cloudflare, edge akan mulai menyajikan sertifikat klien. Jika origin belum disiapkan atau salah memverifikasi CA, handshake origin akan gagal seketika, menyebabkan **Error 525 (SSL Handshake Failed)** massal.

---

## 16. Best Practices
1. **Zero-Tolerance Flexible Mode**: Kunci konfigurasi zone ke `Full (Strict)` sejak provisi pertama kali menggunakan Terraform guardrails.
2. **Kombinasikan Origin CA + AOP**: Pasang sertifikat Origin CA untuk Server Authentication dan aktifkan Authenticated Origin Pulls (AOP) untuk Client Authentication dua arah antara Cloudflare Edge dan Origin.
3. **Standarisasi Minimum TLS 1.2**: Nonaktifkan TLS 1.0 dan TLS 1.1 secara global.
4. **Implementasikan HSTS dengan Preload**: Terapkan konfigurasi header `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` setelah memastikan seluruh subdomain sudah berjalan di atas HTTPS.
5. **Rotasi Rutin & Automasi ACM**: Jika menggunakan Custom Certificate, integrasikan webhook/alerting notifikasi kedaluwarsa 30 hari sebelum masa berlaku habis, atau gunakan ACM dengan auto-renewal.

---

## 17. Troubleshooting

### Matrix Troubleshooting Error SSL/TLS Cloudflare

| Gejala / Error Code | Root Cause Teknis | Langkah Investigasi & Mitigasi |
| :--- | :--- | :--- |
| **Error 525: SSL Handshake Failed** | Handshake TLS antara Cloudflare Edge dan Origin Server gagal pada network/crypto layer. | 1. Verifikasi origin mendukung SNI.<br>2. Pastikan origin mendengarkan di port 443.<br>3. Pastikan origin mendukung cipher suites yang kompatibel dengan Cloudflare.<br>4. Uji langsung origin: `curl -kv https://<ORIGIN_IP> --resolve <DOMAIN>:443:<ORIGIN_IP>`. |
| **Error 526: Invalid SSL Certificate** | Mode enkripsi disetel ke `Full (Strict)`, namun sertifikat origin tidak valid (self-signed, mismatch SAN, atau expired). | 1. Periksa validity: `echo \| openssl s_client -connect <ORIGIN_IP>:443 -servername <DOMAIN> 2>/dev/null \| openssl x509 -noout -dates -subject -ext subjectAltName`.<br>2. Terbitkan ulang Cloudflare Origin CA cert atau perbarui sertifikat CA publik. |
| **ERR_SSL_VERSION_OR_CIPHER_MISMATCH** | Klien dan Cloudflare Edge tidak memiliki protokol TLS atau Cipher Suite yang sama (intersection kosong). | 1. Periksa batas Minimum TLS Version di Cloudflare dashboard.<br>2. Pastikan Universal SSL / ACM pack status sudah `active` bukan `pending_validation`.<br>3. Periksa kustomisasi cipher suites di Cloudflare API. |
| **ERR_TOO_MANY_REDIRECTS** | Pengaturan SSL di dashboard Cloudflare adalah `Flexible`, tetapi Origin memaksa redirect ke HTTPS. | Ubah pengaturan SSL/TLS di dashboard Cloudflare dari `Flexible` menjadi `Full` atau `Full (Strict)`. |

---

## 18. Exercise
1. **Analisis Handshake**: Gunakan perintah `openssl s_client` untuk memeriksa detail cipher suite, parameter ALPN, dan rantai sertifikat dari suatu domain produksi Cloudflare.
2. **Identifikasi Redirect Loop**: Simulasikan secara lokal pada container NGINX skenario `Flexible SSL Redirect Loop` dan perbaiki konfigurasi tersebut dengan beralih ke validasi mode `Strict`.
3. **Generasi CSR Origin**: Buat kunci privat RSA 2048-bit dan CSR untuk domain `*.internal-corp.net` menggunakan OpenSSL CLI yang memenuhi standar Cloudflare Origin CA.

---

## 19. Challenge
Rancang arsitektur keamanan Transport Layer untuk arsitektur microservices e-commerce dengan persyaratan ketat:
- Subdomain `api.shop.com` melayani traffic pembayaran dan wajib menerapkan PCI-DSS 4.0 compliant profile (No TLS < 1.3, strict AEAD ciphers).
- Origin server berada di AWS EKS private subnet di belakang AWS ALB.
- Koneksi antara Cloudflare Edge dan ALB harus terotentikasi dua arah (Origin hanya menerima traffic dari Edge Cloudflare, dilarang dibuka untuk 0.0.0.0/0).
- Klien mobile Android/iOS berkomunikasi via mTLS ke edge Cloudflare.
Buat dokumen spesifikasi arsitektur yang mencakup diagram flow, konfigurasi Cloudflare Terraform, dan policy verifikasi sertifikat di ingress ALB/NGINX.

---

## 20. Summary
- Memilih mode SSL/TLS yang tepat adalah fondasi perimeter keamanan reverse-proxy Cloudflare. Penggunaan mode di bawah **Full (Strict)** meninggalkan celah keamanan kritis pada Origin Leg.
- **Cloudflare Origin CA** memfasilitasi enkripsi origin yang aman, valid, dan berjangka panjang tanpa kompleksitas siklus perpanjangan Let's Encrypt standar.
- **mTLS** mengubah paradigma keamanan dari proteksi pasif (enkripsi data in transit) menjadi mekanisme otentikasi aktif Zero Trust, baik di layer Edge (API Shield) maupun Origin (Authenticated Origin Pulls).
- Hardening menyeluruh membutuhkan sinergi antara Minimum TLS 1.2/1.3, kurasi Cipher Suite, nonaktifnya TLS 1.3 0-RTT pada stateful endpoint, dan penegakan HSTS Preload.