# Module 03: Defensive Security — Authentication, Authorization, & Zero Trust

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Menerapkan prinsip **Defense in Depth** dan **Zero Trust Architecture** ("Never Trust, Always Verify") pada arsitektur sistem terdistribusi.
- Memahami protokol identitas modern: **OAuth 2.0**, **OpenID Connect (OIDC)**, dan anatomi token **JWT (JSON Web Token)**.
- Mengidentifikasi mitigasi serangan **DDoS Layer 3/4** (SYN Flood, UDP Amplification) dan **Layer 7** (HTTP Flood, Slowloris) menggunakan Anycast WAF.
- Memahami konsep otentikasi antar-layanan terenkripsi dengan **mTLS (Mutual TLS)** dan identitas kriptografis (SPIFFE).

## 2. Prerequisite
- Memahami konsep dasar kriptografi asimetris (Public Key / Private Key) dan HTTPS/TLS Handshake.
- Memahami peran API Gateway dari BAB 03.

## 3. Concept
Arsitektur keamanan lama mengandalkan model benteng pertahanan perimeter (*Castle-and-Moat Model*): segala sesuatu di luar firewall dianggap berbahaya, tetapi segala sesuatu di dalam jaringan internal dianggap terpercaya (*Trusted Internal Network*). Jika seorang penyerang berhasil menembus satu server (misal melalui celah RCE pada server upload foto), penyerang dapat bebas bergerak lateral (*lateral movement*) membajak database internal tanpa hambatan.

**Zero Trust Architecture (ZTA)** menolak asumsi tersebut:
> *"Asumsikan jaringan selalu dalam keadaan breached. Jangan pernah percaya siapapun (internal maupun eksternal), selalu verifikasi secara eksplisit."*

Setiap request antar microservice harus diotentikasi, diotorisasi, dan dienkripsi secara timbal balik menggunakan **Mutual TLS (mTLS)** dan token berumur pendek (*short-lived cryptographic credentials*).

## 4. Why?
- **Kebocoran Data Internal (Insider Threat & Lateral Movement)**: 80% pelanggaran data korporat terjadi setelah penyerang menyusupi jaringan lokal kantor atau VPN.
- **Stateless Verification at Scale**: Layanan mikro tidak boleh membebani database auth dengan ribuan query per detik hanya untuk mengecek validitas sesi pengguna.
- **Kepatuhan Regulasi (Compliance)**: Standar PCI-DSS (kartu kredit), HIPAA (kesehatan), dan GDPR mewajibkan enkripsi in-transit di seluruh jaringan internal.

## 5. What?
### 1. Autentikasi vs Otorisasi:
- **Authentication (AuthN)**: *Siapa Anda?* (Membuktikan identitas, misal via kata sandi, biometrik, SMS OTP).
- **Authorization (AuthZ)**: *Apa yang boleh Anda lakukan?* (Mengecek hak akses / RBAC / ABAC, misal: "User ID 5 hanya boleh mengedit artikel miliknya sendiri").

### 2. Standar Protokol Modern:
- **OAuth 2.0**: Kerangka kerja **Otorisasi** terdelegasi (misal: "Izinkan aplikasi Canva mengakses foto di Google Drive saya tanpa memberikan password Google saya").
- **OpenID Connect (OIDC)**: Lapisan **Autentikasi** di atas OAuth 2.0 yang menerbitkan `id_token` (JWT) terverifikasi.
- **JWT (JSON Web Token)**: Token stateless mandiri yang terdiri dari 3 bagian:
  `Header.Payload.Signature` (Base64URL encoded).
  - *HS256 (Symmetric)*: Menggunakan shared secret yang sama untuk sign dan verify. (Bahaya: jika service verifier bocor, attacker bisa membuat token palsu).
  - *RS256 / ES256 (Asymmetric)*: Auth Server memegang Private Key untuk sign token; semua API Gateway memegang Public Key (JWKS) untuk verifikasi tanpa bisa memalsukan token.

### 3. Layer DDoS Defense:
- **L3/L4 DDoS (Network / Transport Layer)**: Serangan volumetrik (SYN Flood, UDP Reflection) membanjiri pipa bandwidth ISP. Mitigasi: BGP Anycast Scrubbing Center (Cloudflare, AWS Shield).
- **L7 DDoS (Application Layer)**: Serangan kompleks (HTTP GET Flood, Slowloris, GraphQL query exhaustion). Mitigasi: Web Application Firewall (WAF), IP Reputation, Captcha Challenge, Token Bucket Rate Limiting.

### 4. Mutual TLS (mTLS):
Pada TLS standar (browsing web), hanya server yang membuktikan identitas sertifikatnya ke browser.  
Pada **mTLS**, kedua belah pihak saling memverifikasi sertifikat digital:
Client membuktikan identitasnya ke Server, dan Server membuktikan identitasnya ke Client.

## 6. How?
### Alur Otentikasi Stateless dengan API Gateway & JWT:
```text
[Mobile Client] ── 1. POST /login (User + Pass) ──> [Auth Service]
                                                           │
                                                           ├── 2. Validasi Kredensial
                                                           └── 3. Sign JWT dgn RS256 Private Key
                                                                 (Expire: 15 menit)
                                                                   │
 [Client] <────── 4. Kirim Access Token + Refresh Token ───────────┘
    │
    ├── 5. GET /orders (Header: Bearer eyJhbGciOi...) ──> [API Gateway]
                                                                │
                                                                ├── 6. Verifikasi Signature dgn Public Key (JWKS)
                                                                ├── 7. Cek Expire & Rate Limit
                                                                └── 8. Teruskan request mTLS + Header X-User-Id
                                                                      │
                                                                      ▼
                                                             [Order Microservice]
```

## 7. Analogy
- **Castle & Moat (Model Lama)**: Benteng dengan parit buaya. Jika ada penyusup berpakaian badut yang berhasil masuk lewat pintu gerbang, dia bebas masuk ke kamar tidur raja dan ruang brankas emas.
- **Zero Trust = Gedung Markas Intelijen (CIA / Pentagon)**: Tidak peduli Anda sudah berada di dalam lobi lantai 3, setiap kali Anda ingin membuka pintu toilet, pintu lift, atau ruang server, Anda wajib menempelkan kartu RFID ID card dan melakukan scan sidik jari lagi.
- **mTLS = Agen Rahasia Bertemu Informan**: Kedua pihak saling menanyakan kata sandi rahasia sebelum berbicara. Jika salah satu pihak tidak bisa membuktikan identitasnya, percakapan dibatalkan seketika.

## 8. Diagram

```text
================ STANDARD TLS vs MUTUAL TLS (mTLS) ================

Standard TLS (One-Way):
[Client / Browser] ──── 1. Kamu siapa? Mana sertifikatmu? ────> [Server]
[Client / Browser] <─── 2. Ini sertifikat saya (Verisign) ────── [Server]
(Server tidak memverifikasi identitas kriptografis client!)

Mutual TLS (mTLS - Two-Way Verification):
[Service A (Client)] ─── 1. Ini Sertifikat Kriptografis Saya ──> [Service B (Server)]
[Service A (Client)] <── 2. Ini Sertifikat Kriptografis Saya ─── [Service B (Server)]
             (Keduanya saling memvalidasi Root CA internal!)
```

## 9. Simple Example
Struktur Payload JWT (Claims):
```json
{
  "sub": "usr_998877",
  "name": "Siti Rahma",
  "role": "admin",
  "iss": "https://auth.company.com",
  "aud": "https://api.company.com",
  "iat": 1789099000,
  "exp": 1789099900
}
```
Signature dihitung dari:
`HMACSHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), secret)`

## 10. Practical Example: Masalah Token Revocation pada JWT
Karena JWT bersifat *stateless*, jika token dicuri sebelum masa `exp` habis (misal sisa 10 menit), server tidak bisa membatalkan token tersebut kecuali server menyimpan blacklist di Redis.
**Solusi Arsitektur Best Practice**:
Gunakan **Short-Lived Access Token** (masa berlaku 5 - 15 menit) dipadukan dengan **Long-Lived Refresh Token** (masa berlaku 7 - 30 hari) yang disimpan di database / Redis. Jika akun di-hack, admin cukup mencabut (*revoke*) Refresh Token di database. Dalam 15 menit, Access Token yang dicuri akan kedaluwarsa selamanya!

## 11. Real World Example
- **Google BeyondCorp**: Pelopor Zero Trust komersial terbesar di dunia. Seluruh karyawan Google tidak menggunakan VPN korporat tradisional untuk bekerja; setiap perangkat laptop dan smartphone memiliki sertifikat hardware (TPM) yang terus-menerus diverifikasi oleh access proxy kontekstual setiap kali mengakses aplikasi internal Google.
- **Cloudflare**: Menangani serangan DDoS L3/L4 terbesar dalam sejarah internet (> 71 juta request per detik) dengan menyerap trafik di edge Anycast network yang tersebar di 330 kota dunia.

## 12. Trade-offs

| Aspek | Symmetric JWT (HS256) | Asymmetric JWT (RS256) | Stateful Session (Redis) |
|---|---|---|---|
| **Verifikasi** | Butuh shared secret di semua service | Hanya butuh Public Key (Aman didistribusi) | Query round-trip ke Redis |
| **Keamanan Kunci** | Sangat rentan jika 1 service bocor | Sangat tinggi (Private key aman di Auth Server)| Sangat tinggi |
| **Pencabutan Instan** | Tidak bisa tanpa Redis denylist | Tidak bisa tanpa Redis denylist | **Bisa seketika (Hapus session di Redis)** |
| **Throughput & Skala**| Ekstrem tinggi (In-memory CPU) | Sangat tinggi (In-memory crypto verify) | Terbatas throughput cluster Redis |

## 13. When To Use Zero Trust & mTLS
- Setiap arsitektur microservices dan Kubernetes cluster yang menangani data sensitif.
- Komunikasi lintas datacenter atau hybrid cloud (On-premise ke AWS/GCP).
- Layanan yang tunduk pada regulasi perbankan, fintech, dan medis.

## 14. When NOT To Use
- Prototipe awal (MVP) skala startup kecil beranggotakan 2 orang di mana overhead mengelola certificate authority (CA) dan PKI akan memperlambat iterasi produk secara berlebihan.

## 15. Common Mistakes
1. **Menyimpan Secret Sensitif di Payload JWT**: Ingat bahwa payload JWT hanya di-encode Base64, BUKAN dienkripsi! Siapapun yang melihat token dapat membaca isinya (`jwt.io`). Jangan pernah menyimpan password, nomor KTP, atau CVV kartu kredit di JWT!
2. **Mengabaikan Validasi Algoritma `alg: none` (JWT None Attack)**: Beberapa pustaka lawas mengizinkan token dengan header `{"alg": "none"}` melewati verifikasi tanpa tanda tangan. Selalu tentukan algoritma eksplisit di validator (`algorithms: ['RS256']`).
3. **Masa Berlaku Access Token Terlalu Panjang**: Menetapkan expire token selama 30 hari adalah lubang keamanan fatal jika token bocor di browser client.

## 16. Best Practices
- **Rotasi Kunci Otomatis (JWKS)**: Sediakan endpoint `/.well-known/jwks.json` agar client/gateway dapat mengambil public key terbaru secara berkala tanpa redeploy aplikasi.
- **Service Mesh untuk Otomasi mTLS**: Jangan implementasikan mTLS manual di kode aplikasi; gunakan Service Mesh (Istio/Linkerd) dengan sidecar proxy (Envoy) yang secara otomatis merotasi sertifikat x509 setiap 24 jam via SPIFFE/SPIRE.
- **Sanitize & Validate Input di WAF & Gateway**: Cegah SQL Injection, XSS, dan Path Traversal sebelum mencapai service internal.

## 17. Troubleshooting
- **Masalah: Panggilan antar microservices gagal dengan error `SSL Handshake Failed: Certificate Expired`**.
  - *Sebab*: Sertifikat internal TLS kedaluwarsa dan tidak ada mekanisme otomatisasi rotasi.
  - *Solusi*: Pasang cert-manager di Kubernetes dengan Let's Encrypt atau HashiCorp Vault untuk memperbarui sertifikat secara otomatis 30 hari sebelum kedaluwarsa.

## 18. Hands-on Practice
Mari kita buktikan secara langsung cara kerja pembuatan token JWT, validasi signature kriptografis, pencegahan token tampering (pemalsuan role admin), dan mitigasi DDoS HTTP flood di `hands-on/m03/security_defense_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung berapa ukuran overhead payload HTTP jika sebuah JWT berukuran 1.2 KB dikirim pada setiap request ke sistem dengan volume 10.000 request per detik. (Jawaban: $10.000 \times 1.2\text{ KB} = 12\text{ MB/detik} = 96\text{ Mbps}$ bandwidth terbuang hanya untuk header auth!).
- **Challenge**: Rancang skema *OAuth 2.0 PKCE (Proof Key for Code Exchange)* untuk aplikasi Single Page Application (React) yang tidak dapat menyimpan Client Secret dengan aman di browser.

## 20. Summary
Keamanan sistem terdistribusi modern berpijak pada prinsip **Zero Trust**: jangan pernah berasumsi jaringan internal aman. Dengan memadukan verifikasi stateless berbasis **JWT Asimetris (RS256)** di API Gateway, enkripsi dan otentikasi timbal balik dengan **mTLS**, serta perlindungan perimeter multi-layer terhadap serangan DDoS, sistem terdistribusi Anda terlindungi secara menyeluruh (*Defense in Depth*).
