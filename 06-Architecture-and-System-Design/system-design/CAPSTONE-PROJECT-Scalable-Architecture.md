# CAPSTONE PROJECT: End-to-End Scalable Platform Architecture
## "NusantaraStream" — Global On-Demand Video Streaming & Live Interactive Platform

---

## 📌 Executive Summary & Project Vision
Selamat datang di **Capstone Project: System Design Mastery**. Ini adalah puncak evaluasi dari seluruh kurikulum roadmap System Design yang telah Anda pelajari dari BAB 01 hingga BAB 10.

Dalam proyek ini, Anda bertindak sebagai **Chief Enterprise Architect** untuk merancang platform hiburan multimedia skala global bernama **NusantaraStream**. Platform ini menggabungkan layanan Video On-Demand (VoD mirip Netflix), Live Interactive Broadcast (mirip Twitch/YouTube Live), dan Sistem Sosial/Chat interaktif real-time.

---

## 🎯 1. Requirements Engineering

### Functional Requirements (FR)
1. **Video Catalog & Discovery**: Pengguna dapat mencari, memfilter, dan melihat katalog film/video beresolusi 4K dengan rekomendasi personal.
2. **Video Streaming (Adaptive Bitrate)**: Pengguna dapat memutar video dengan mulus tanpa buffering menggunakan Adaptive Bitrate Streaming (HLS / DASH).
3. **Live Streaming Ingestion & Broadcast**: Kreator dapat menyiarkan video live via RTMP/WebRTC, dan jutaan penonton dapat menonton siaran dengan latensi < 2 detik.
4. **Real-Time Live Chat**: Jutaan penonton dalam satu siaran langsung dapat berinteraksi melalui live chat interaktif dan mengirimkan animasi donasi/gift.
5. **Subscription & Billing**: Pengguna dapat berlangganan paket bulanan melalui berbagai metode pembayaran (Kartu Kredit, E-Wallet, QRIS) dengan jaminan zero double-billing.

### Non-Functional Requirements (NFR)
1. **High Availability (HA)**: 99.99% Uptime (Maksimal downtime tidak terencana < 52.6 menit per tahun).
2. **Low Latency**:
   - API Metadata Catalog: p99 < 50 milidetik.
   - Video Start Time (Time-to-First-Frame / TTFF): < 800 milidetik di jaringan seluler 4G/5G.
   - Live Chat Message Delivery: < 100 milidetik.
3. **Extreme Scalability**:
   - Mampu melayani **25 Juta Daily Active Users (DAU)**.
   - Menahan lonjakan trafik saat siaran langsung final piala dunia (Peak Concurrency: **3 Juta penonton simultan**).
4. **Data Consistency**:
   - Strong Consistency untuk transaksi keuangan dan saldo langganan.
   - Eventual Consistency untuk analitik penonton, rekomendasi video, dan counter viewers.
5. **Security & Compliance**:
   - Zero Trust Architecture, mTLS inter-service, enkripsi AES-256 in-transit & at-rest, Digital Rights Management (DRM - Widevine/FairPlay), dan perlindungan WAF terhadap DDoS L3/L4/L7.

---

## 📐 2. Back-of-the-Envelope Capacity Estimation

```text
PARAMETER ESTIMASI NUSANTARASTREAM:
- DAU: 25.000.000 Pengguna
- Rata-rata waktu tonton: 1.5 jam per user per hari
- Bitrate rata-rata (1080p ABR): 3.0 Mbps
- Peak Live Stream Concurrency: 3.000.000 Penonton Simultan

1. THROUGHPUT BANDWIDTH KELUAR (EGRESS CDN):
   Peak Bandwidth = 3.000.000 penonton x 3.0 Mbps = 9.000.000 Mbps = 9 Terabit per detik (Tbps)!
   -> Keputusan: Wajib Multi-CDN Strategy (Cloudflare + Akamai + Fastly) + ISP Edge Caching.

2. STORAGE ESTIMATION (CATALOG VOD):
   - 50.000 Judul Film & Serial (Rata-rata 2 jam per judul).
   - Setiap judul di-encode ke 5 profile resolusi (4K, 1080p, 720p, 480p, 360p) = total ~15 GB per jam film.
   - Total Storage Video Master = 50.000 x 2 jam x 15 GB = 1.500.000 GB = 1.5 Petabyte (Disimpan di AWS S3 Glacier & S3 Standard).

3. DATABASE & CACHE CAPACITY:
   - Catalog Metadata: ~2 KB per judul x 50.000 = 100 MB (Sangat kecil, muat 100% di RAM Redis!).
   - User State & Watch History: 25M users x 100 riwayat tontonan x 50 bytes = 125 GB (Sharded MongoDB / Cassandra).
```

---

## 🏛️ 3. High-Level Architecture Blueprint

```text
                                  [GLOBAL USERS / CLIENTS]
                          (Mobile Apps, Web Browsers, Smart TVs)
                                             │
               ┌─────────────────────────────┴─────────────────────────────┐
               ▼                                                           ▼
    [DNS Geo-Routing / Anycast]                               [Multi-CDN Edge Network]
    (Cloudflare / Route 53)                                  (HLS Video Segments Caching)
               │                                                           │
               ▼                                                           │
    [DDoS Shield & Edge WAF]                                               │
               │                                                           │
               ▼                                                           │
     [API Gateway / Envoy] <──(Token Bucket Rate Limiting / RS256 JWT)     │
               │                                                           │
  ┌────────────┼───────────────────────────┬───────────────────────────────┤
  │            │                           │                               │
  ▼            ▼                           ▼                               ▼
[Auth &    [Catalog &                [Streaming Ingest              [Real-Time Live
 User Svc]  Discovery Svc]            & Transcoding]                 Chat Gateway]
  │            │                           │                               │
  ├── JWT      ├── Redis Cache             ├── S3 Blob Storage             ├── WebSocket Cluster
  └── Postgres └── Elasticsearch           └── Kafka Media Pipeline        └── Redis Pub/Sub Bus
                                                                                   │
                                                                           [ScyllaDB History]
```

---

## 🧩 4. Detailed Component Breakdown

### Milestone 1: Video Ingestion & Adaptive Transcoding Pipeline
- **Input**: Kreator mengunggah master video ProRes/MP4 4K.
- **Workflow**:
  1. API mengembalikan *Pre-signed S3 URL* agar klien mengunggah file langsung ke bucket S3 (tidak membebani API Gateway).
  2. S3 Event Notification memicu pesan ke **Apache Kafka** (`topic: video-uploaded`).
  3. **Transcoding Worker Pool** (FFmpeg pods di Kubernetes autoscaling spot instances) memecah video menjadi chunk durasi 4 detik (.ts / .m4s).
  4. File di-encode ke berbagai profil bitrate (240p hingga 4K) dan menghasilkan playlist manifest `.m3u8` (HLS) dan `.mpd` (DASH).
  5. File manifest dan chunk video disimpan ke S3 dan otomatis di-cache oleh Multi-CDN Edge.

### Milestone 2: Video Delivery & Multi-CDN Strategy
- **Edge CDN Optimization**:
  - Video manifest `.m3u8` memiliki TTL pendek (2-4 detik untuk live stream).
  - Video chunk data `.ts` bersifat immutable, memiliki TTL panjang (30 hari di browser & CDN cache).
  - Algoritma **Smart Dynamic DNS Routing** memantau latensi dan packet drop antar vendor CDN (Cloudflare vs Akamai) dan otomatis mengalihkan penonton ke CDN paling sehat di regionalnya.

### Milestone 3: Real-Time Live Chat & Interactive Donasi Engine
- **Scalability Challenge**: 3 Juta orang berada di satu ruang siaran langsung yang sama.
- **Solusi Arsitektur**:
  - **WebSocket Gateway Fleet**: 60 server gateway (masing-masing menampung 50.000 koneksi concurrent).
  - **Message Conflation & Sampling**: Pada traffic > 10.000 pesan/detik, server gateway melakukan agregasi lokal: menggabungkan pesan dan hanya mem-push maksimal 25 pesan per detik ke layar klien agar browser/ponsel tidak crash.
  - **Animasi Gift / Donasi**: Transaksi uang dipisahkan ke *Priority High-Reliability Channel* (Kafka $\rightarrow$ Payment Ledger $\rightarrow$ WebSocket Broadcast khusus animasi VIP).

### Milestone 4: Resiliensi Finansial & Langganan
- **Idempotent Payment Webhook**: Memproses notifikasi kartu kredit/e-wallet dengan `idempotency_key` di PostgreSQL.
- **Circuit Breaker**: Memasang circuit breaker wrapper di sekitar API bank pihak ketiga dengan fallback graceful degradation (alih-alih error, izinkan pengguna menonton dengan masa tenggang *grace period* 24 jam jika sistem verifikasi bank sedang maintenance).

---

## 🔒 5. Defensive Security & Zero Trust Implementation
1. **Perimeter Defense**: Proteksi DDoS volumetrik L3/L4 menggunakan Anycast BGP Routing dan WAF rules untuk menangkis SQLi, XSS, dan bot scraping.
2. **Internal Mesh Security**: Komunikasi antar microservice di dalam Kubernetes cluster dienkripsi penuh menggunakan **mTLS** yang dikelola oleh Istio Service Mesh.
3. **Digital Rights Management (DRM)**: Video stream dilindungi enkripsi AES-128 berbasis lisensi DRM (Google Widevine Modular, Apple FairPlay, Microsoft PlayReady) untuk mencegah pembajakan rekaman layar.

---

## 📊 6. Observability, SLO, & Chaos Engineering
- **Tiga Pilar Observabilitas**:
  - **Metrics**: Prometheus mengikis metrik RED (Rate, Errors, Duration) dari seluruh pod gateway dan microservices.
  - **Logs**: FluentBit mengumpulkan JSON structured log dengan korelasi `trace_id` ke Elasticsearch / Loki.
  - **Tracing**: OpenTelemetry SDK menyuntikkan header W3C `traceparent` di setiap panggilan HTTP dan gRPC.
- **SLO & SLI Kritis**:
  - **Video Playback Success Rate**: $\ge 99.9\%$ dari percobaan memutar video harus berhasil memunculkan frame pertama dalam $< 1.5$ detik.
  - **API Error Budget**: Maksimal 0.05% error HTTP 5xx per bulan.
- **Chaos Engineering (Chaos Mesh / Gremlin)**:
  - Uji matinya 1 Availability Zone AWS secara tiba-tiba: DNS failover harus mengalihkan trafik dalam waktu $< 30$ detik.
  - Uji hilangnya cluster Redis cache: Database harus dilindungi oleh Circuit Breaker dan Semaphore Bulkhead agar tidak terjadi cascading collapse.

---

## 🚀 7. Step-by-Step Implementation Roadmap

| Milestone | Target Output | Waktu Estimasi |
|---|---|---|
| **Milestone 1: Fondasi & Schema** | Definisi protobuf gRPC, skema PostgreSQL, dan skema Cassandra chat | Minggu 1 |
| **Milestone 2: Ingestion & Transcoding** | FFmpeg chunking pipeline, S3 integration, HLS playlist generator | Minggu 2 |
| **Milestone 3: WebSocket Live Engine** | WS Gateway cluster, Redis session presence, chat conflation | Minggu 3 |
| **Milestone 4: Caching & CDN Layer** | CloudFront/Cloudflare multi-origin routing, Cache-aside catalog | Minggu 4 |
| **Milestone 5: Resilience & Observability**| Circuit breaker resilience4j, OTel tracing, Prometheus Grafana dashboard | Minggu 5 |
| **Milestone 6: Load Testing & Launch** | Simulasi uji beban k6 (100k virtual users), chaos injection, prod deployment | Minggu 6 |

---

## 🏆 Capstone Submission Deliverables

Untuk menyelesaikan Capstone Project ini secara paripurna, buat dokumen desain teknis dan repository kode yang mencakup:
1. **Arsitektur Lengkap (Architecture Decision Records / ADR)**: Alasan pemilihan Cassandra vs PostgreSQL vs Redis.
2. **Kalkulasi Kapasitas Realistis**: Sheet kalkulasi QPS, IOPS, Storage, dan Bandwidth.
3. **Kode Implementasi Inti**:
   - Minimal 1 prototipe working worker HLS video chunking.
   - Minimal 1 cluster WebSocket Gateway dengan Redis Pub/Sub message broker.
   - Minimal 1 distributed rate limiter Lua script.
4. **Disaster Recovery Playbook**: Prosedur langkah-demi-langkah saat datacenter utama mengalami pemadaman listrik total.
