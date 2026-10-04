Berikut adalah cetak biru silabus kurikulum lengkap `README.md` untuk topik **Cloudflare**, disusun dengan pendekatan *enterprise production-grade engineering* dan standar arsitektur global.

---

# Cloudflare Enterprise Architecture & Edge Engineering Masterclass

Selamat datang di repositori kurikulum resmi **Cloudflare Enterprise Architecture & Edge Engineering**. Kurikulum ini dirancang untuk melatih Network Engineer, DevOps/SRE, SecOps, dan Cloud Architect dalam menguasai seluruh spektrum ekosistem Cloudflare—mulai dari dasar perutean Anycast L3/L4, proteksi ancaman L7, komputasi terdistribusi *serverless edge*, hingga arsitektur *Zero Trust Enterprise*.

---

## 1. Course Overview & Mindset

### Paradigma Edge-First & Zero Trust
Era infrastruktur komputasi telah bergeser dari model *centralized origin-bound architecture* ke arsitektur *edge-native*. Memperlakukan Cloudflare sekadar sebagai "Reverse Proxy" atau "CDN statis" adalah sebuah *antipattern*. Di dalam kurikulum ini, Anda akan membedah dan menerapkan Cloudflare sebagai:

1. **Global Software-Defined Network (SDN)**: Memanfaatkan jaringan BGP Anycast global Cloudflare untuk terminasi koneksi di PoP (*Point of Presence*) terdekat dengan pengguna, mereduksi latensi RTT (*Round-Trip Time*), dan memitigasi serangan volumetrik langsung di batas terluar (*edge network edge*).
2. **Programmable Distributed Compute Plane**: Memindahkan beban komputasi mikro-layanan dari origin server ke ribuan mesin edge V8 isolates menggunakan Cloudflare Workers, Pages, dan Durable Objects tanpa *cold-start penalty*.
3. **Enterprise Defense-in-Depth Enforcer**: Mengintegrasikan SSL/TLS Strict Mode, WAF Engine v2, Advanced Rate Limiting, Enterprise Bot Management, dan mTLS untuk menjamin bahwa origin server Anda tidak pernah terekspos langsung ke internet publik (*dark origin pattern*).
4. **Unified Zero Trust Perimeter**: Menghapus VPN warisan (*legacy split-tunnel VPN*) dan mengamankan akses internal corporate via Cloudflare Access, Cloudflare Tunnels (cloudflared), Gateway, dan Secure Web Gateway (SWG) berbasis prinsip *never trust, always verify*.

---

## 2. Learning Roadmap

```text
Cloudflare Enterprise Engineering Roadmap
│
├── [Bab 01] Fondasi Edge Networking, DNS, & Arsitektur Anycast Cloudflare
├── [Bab 02] SSL/TLS Encryption, Origin CA, & Custom Certificates Lifecycle
├── [Bab 03] Edge Caching, Cache Rules, Tiered Cache, & Cache Purging Strategies
├── [Bab 04] Web Application Firewall (WAF), Managed Rules, & Custom Rulesets
├── [Bab 05] DDoS Mitigation, Advanced Rate Limiting, & Bot Management
├── [Bab 06] Edge Compute Serverless: Cloudflare Workers & Pages
├── [Bab 07] Distributed Edge Storage & State Management (KV, D1, R2, Durable Objects)
├── [Bab 08] Zero Trust Network Access (ZTNA), Cloudflare Tunnels, & Secure Access
├── [Bab 09] Global Traffic Steering, Load Balancing, & Argo Smart Routing
└── [Bab 10] Enterprise Observability, Logpush Pipeline, SIEM, & Capstone Deployment
```

---

## 3. Navigasi Detail Kurikulum

### Bab 01: Fondasi Edge Networking, DNS, & Arsitektur Anycast Cloudflare
Memahami cara kerja jaringan global Anycast L3/L4/L7, propagasi rute BGP, dan manajemen authoritative DNS skala enterprise.
* [Modul 01: Arsitektur Anycast BGP vs Unicast & Topologi Cloudflare PoP](bab-01-fondasi-edge-dns-anycast/modul-01-arsitektur-anycast-bgp-vs-unicast.md)
* [Modul 02: Authoritative DNS, DNSSEC, CNAME Flattening, & Proxy Status (Orange vs Grey Cloud)](bab-01-fondasi-edge-dns-anycast/modul-02-dns-dnssec-cname-flattening-proxy-status.md)
* [Modul 03: DNS Firewall, Custom Nameservers, & Resolusi DNS Berlatensi Rendah](bab-01-fondasi-edge-dns-anycast/modul-03-dns-firewall-custom-nameservers.md)

### Bab 02: SSL/TLS Encryption, Origin CA, & Custom Certificates Lifecycle
Konfigurasi kriptografi end-to-end, penghapusan *man-in-the-middle risks*, dan pengelolaan sertifikat modern.
* [Modul 01: Deep-Dive Mode Enkripsi: Off, Flexible, Full, dan Full (Strict)](bab-02-ssl-tls-origin-ca-certificates/modul-01-deep-dive-mode-enkripsi-ssl-tls.md)
* [Modul 02: Cloudflare Origin CA, Custom Certificate Upload, & Keyless SSL Architecture](bab-02-ssl-tls-origin-ca-certificates/modul-02-origin-ca-custom-cert-keyless-ssl.md)
* [Modul 03: Mutual TLS (mTLS), Universal SSL Lifecycle, HSTS, & TLS 1.3 0-RTT Optimization](bab-02-ssl-tls-origin-ca-certificates/modul-03-mtls-hsts-tls13-zero-rtt.md)

### Bab 03: Edge Caching, Cache Rules, Tiered Cache, & Cache Purging Strategies
Membangun strategi caching agresif, optimasi rasio cache-hit, dan kontrol eviksi presisi di edge.
* [Modul 01: Siklus Hidup Edge Cache, Header Kontrol HTTP (Cache-Control, s-maxage, CDN-Cache-Control)](bab-03-edge-caching-cache-rules-purging/modul-01-siklus-hidup-edge-cache-http-headers.md)
* [Modul 02: Cache Rules Engine, Custom Cache Keys, & Tiered Cache Topology](bab-03-edge-caching-cache-rules-purging/modul-02-cache-rules-custom-cache-keys-tiered-cache.md)
* [Modul 03: Cache Reserve, Strategi Purging Skala Besar (Single URL, Tag, Prefix), & Cache Poisoning Defense](bab-03-edge-caching-cache-rules-purging/modul-03-cache-reserve-purging-cache-poisoning-defense.md)

### Bab 04: Web Application Firewall (WAF), Managed Rules, & Custom Rulesets
Memproteksi origin dari serangan OWASP Top 10 dan eksploitasi zero-day menggunakan Ruleset Engine v2.
* [Modul 01: Anatomi Cloudflare Ruleset Engine & Cloudflare Managed Ruleset Tuning](bab-04-waf-managed-rules-custom-rulesets/modul-01-ruleset-engine-managed-ruleset-tuning.md)
* [Modul 02: Rekayasa Custom WAF Rules: Wireshark-like Expression Syntax & Payload Inspection](bab-04-waf-managed-rules-custom-rulesets/modul-02-rekayasa-custom-waf-rules-syntax.md)
* [Modul 03: OWASP Core Ruleset Mitigation, Anomaly Scoring, & True Client IP Validation](bab-04-waf-managed-rules-custom-rulesets/modul-03-owasp-anomaly-scoring-client-ip-validation.md)

### Bab 05: DDoS Mitigation, Advanced Rate Limiting, & Bot Management
Penanggulangan serangan L3/L4/L7 volumetrik dan orkestrasi pemisahan bot jahat vs legitimate crawler.
* [Modul 01: Mitigasi Serangan L3/L4 Syn-Flood/UDP Amplification & HTTP DDoS Managed Rulesets](bab-05-ddos-rate-limiting-bot-management/modul-01-mitigasi-ddos-l3-l4-l7-protection.md)
* [Modul 02: Advanced Rate Limiting: Heuristik Counting Matrix, Session Tracking, & Leaky Bucket](bab-05-ddos-rate-limiting-bot-management/modul-02-advanced-rate-limiting-heuristik-session.md)
* [Modul 03: Enterprise Bot Management: Machine Learning Bot Score, Super Bot Fight Mode, & Managed Challenges](bab-05-ddos-rate-limiting-bot-management/modul-03-bot-management-ml-bot-score-challenges.md)

### Bab 06: Edge Compute Serverless: Cloudflare Workers & Pages
Membangun mikro-layanan komputasi berlatensi 0ms di edge menggunakan arsitektur V8 Isolate.
* [Modul 01: Arsitektur Cloudflare Workers Runtime (V8 Isolates vs Containerized Node.js)](bab-06-serverless-workers-pages/modul-01-workers-runtime-v8-isolates-vs-containers.md)
* [Modul 02: Rekayasa Edge Handler: Fetch API, Request Mutating, Dynamic Header Injection, & Subrequests](bab-06-serverless-workers-pages/modul-02-edge-handlers-fetch-request-mutation.md)
* [Modul 03: Fullstack Deployment dengan Cloudflare Pages, Edge Functions, & CI/CD Pipeline Integration](bab-06-serverless-workers-pages/modul-03-cloudflare-pages-edge-functions-cicd.md)

### Bab 07: Distributed Edge Storage & State Management (KV, D1, R2, Durable Objects)
Orkestrasi state, penyimpanan objek nir-biaya egress, dan konsistensi data terdistribusi di edge.
* [Modul 01: Workers KV: Eventual Consistency, Cache Eviction, & High-Read Patterns](bab-07-edge-storage-state-management/modul-01-workers-kv-eventual-consistency.md)
* [Modul 02: Cloudflare R2 Object Storage (S3-Compatible, Zero Egress) & Edge Image Resizing Pipeline](bab-07-edge-storage-state-management/modul-02-r2-storage-zero-egress-media-pipeline.md)
* [Modul 03: Relational D1 Database (SQLite Edge) & Strong Consistency via Durable Objects](bab-07-edge-storage-state-management/modul-03-d1-database-durable-objects-strong-consistency.md)

### Bab 08: Zero Trust Network Access (ZTNA), Cloudflare Tunnels, & Secure Access
Mengisolasi origin server dan sistem internal dari serangan eksternal tanpa mengekspos public IP.
* [Modul 01: Dark Origin Architecture: Cloudflare Tunnel (cloudflared) Setup & Ingress Rules](bab-08-zero-trust-tunnels-access/modul-01-dark-origin-cloudflare-tunnel-ingress.md)
* [Modul 02: Cloudflare Access: IdP Integration (OIDC/SAML), Device Posture, & Granular RBAC](bab-08-zero-trust-tunnels-access/modul-02-cloudflare-access-idp-device-posture-rbac.md)
* [Modul 03: Secure Web Gateway (SWG), WARP Client Routing, & DNS Filtering Policy](bab-08-zero-trust-tunnels-access/modul-03-swg-warp-client-dns-filtering.md)

### Bab 09: Global Traffic Steering, Load Balancing, & Argo Smart Routing
Menghantarkan traffic lintas data center multi-region dengan latensi minimal dan failover otomatis.
* [Modul 01: Cloudflare Load Balancer: Origin Pools, Probing Topology, & Geo-Steering Algorithms](bab-09-traffic-steering-load-balancing/modul-01-load-balancer-pools-geo-steering.md)
* [Modul 02: Zero-Downtime Health Checks, Origin Fallbacks, & Session Affinity Engineering](bab-09-traffic-steering-load-balancing/modul-02-health-checks-origin-fallbacks-affinity.md)
* [Modul 03: Argo Smart Routing & Tiered Caching: Optimasi Algoritma Rute Privat Cloudflare](bab-09-traffic-steering-load-balancing/modul-03-argo-smart-routing-private-backbone.md)

### Bab 10: Enterprise Observability, Logpush Pipeline, SIEM, & Capstone Deployment
Monitoring real-time, audit analitik, ekstraksi log edge volumetrik, dan orkestrasi proyek akhir.
* [Modul 01: Cloudflare Analytics Engine, Edge Tracing, & GraphQL Analytics API](bab-10-observability-logpush-siem-capstone/modul-01-analytics-engine-graphql-api.md)
* [Modul 02: Enterprise Logpush Pipeline: Integrasi Real-Time AWS S3, Datadog, & Splunk SIEM](bab-10-observability-logpush-siem-capstone/modul-02-enterprise-logpush-s3-datadog-splunk.md)
* [Modul 03: Capstone Deployment: Panduan Eksekusi, Validasi Arsitektur, & Pengujian Beban](bab-10-observability-logpush-siem-capstone/modul-03-capstone-deployment-validation.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek:
**"Architecting Global Zero-Trust Resilient Microservices with Cloudflare Edge-First Foundation"**

### Ringkasan Eksekutif & Skenario:
Sebuah perusahaan finansial multinasional melayani jutaan transaksi per menit dan sering mengalami serangan credential stuffing, scraping bot terdistribusi, serta serangan DDoS L7 volumetrik pada sistem API gateway mereka. Selain itu, origin server mereka yang berada di multi-cloud (AWS ap-southeast-1 dan GCP us-central1) memiliki biaya *egress traffic* yang membengkak serta dependensi VPN warisan yang rentan terhadap intrusi lateral.

Tugas Anda adalah merancang, mengonfigurasi, dan mengotomasi seluruh infrastruktur Cloudflare di depan sistem finansial ini secara menyeluruh dari scratch menggunakan pendekatan Infrastructure as Code (Terraform) atau implementasi dashboard terstandarisasi.

### Arsitektur yang Wajib Dibangun:

```text
[Global Users] 
       │ (HTTPS / HTTP/3 via BGP Anycast Edge)
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Cloudflare Edge Plane                                       │
│ ├── Edge SSL (Custom Cert / TLS 1.3 / Strict Mode)          │
│ ├── WAF Ruleset Engine (OWASP 942100+ SQLi/XSS Shield)      │
│ ├── Bot Management (Score < 30 -> Managed Challenge)        │
│ ├── Advanced Rate Limiting (/api/v1/auth/login: 5 req/min)  │
│ ├── Edge Worker Gateway (Auth Token Verification / KV Cache)│
│ ├── Media Delivery via Cloudflare R2 (0 Egress Fees)        │
│ └── Cloudflare Load Balancer (Argo Smart Routing Enabled)   │
└──────────────┬───────────────────────────────┬──────────────┘
               │ (Private Cloudflare Tunnel)   │ (Tunnel)
               ▼                               ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ AWS Region (Primary Pool)    │ │ GCP Region (Secondary Pool)  │
│ - Origin Server (Dark Origin)│ │ - Origin Server (Dark Origin)│
│ - cloudflared daemon         │ │ - cloudflared daemon         │
│ - No Public IPv4 Exposed     │ │ - No Public IPv4 Exposed     │
└──────────────────────────────┘ └──────────────────────────────┘
```

### Kriteria Keberhasilan (Acceptance Criteria):
1. **Dark Origin Isolation**: Seluruh *ingress firewall* pada origin server di-set `Deny All` untuk traffic publik internet. Konektivitas hanya diperbolehkan melalui `cloudflared` tunnel aktif.
2. **Kriptografi End-to-End**: Enkripsi disetel ke **Full (Strict)** menggunakan sertifikat yang diterbitkan oleh Cloudflare Origin CA dengan rotasi kunci otomatis.
3. **Advanced Security Perimeter**:
   * Rule WAF khusus menolak seluruh payload dengan skor anomali OWASP > 20.
   * Endpoint autentikasi `/api/v1/auth/*` dilindungi dengan Rate Limiting dinamis berbasis header `CF-Connecting-IP` dan sidik jari TLS (*JA3/JA4 fingerprint*).
   * Request dengan Bot Score < 30 otomatis diarahkan ke Cloudflare Turnstile / Managed Challenge.
4. **Edge Micro-routing (Workers & Storage)**:
   * Worker memvalidasi header JWT di edge PoP; request tidak valid langsung di-drop dengan status HTTP 401 tanpa membebani origin server.
   * Aset statis dan dokumen media di-host pada Cloudflare R2 dengan custom sub-domain serta Edge Cache Rule `Cache-Control: public, max-age=31536000, immutable`.
5. **Global Resiliency & Failover**:
   * Health Check interval 10 detik. Jika origin AWS gagal mengembalikan HTTP 200, trafik dialihkan secara transparan ke pool GCP dalam waktu < 30 detik tanpa *dropped TCP connections* menggunakan Cloudflare Load Balancing.
6. **Enterprise Auditability**:
   * Mengaktifkan Logpush Job untuk men-stream HTTP Requests Log dan Firewall Events secara real-time ke bucket observabilitas atau endpoint webhook SIEM eksternal.

---
*Silabus ini merupakan panduan implementasi resmi. Mulailah pembelajaran Anda dari [Bab 01: Fondasi Edge Networking, DNS, & Arsitektur Anycast Cloudflare](bab-01-fondasi-edge-dns-anycast/modul-01-arsitektur-anycast-bgp-vs-unicast.md).*