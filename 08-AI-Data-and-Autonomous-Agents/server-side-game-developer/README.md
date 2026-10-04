# Kurikulum Spesialisasi: Server-Side Game Developer

Selamat datang di repositori kurikulum resmi **Server-Side Game Developer**. Silabus ini dirancang sebagai panduan komprehensif berstandar industri (*enterprise-grade*) untuk menguasai arsitektur, rekayasa protokol, sinkronisasi state terdistribusi, optimasi performa *real-time*, dan infrastruktur *dedicated game server* berskala masif.

---

## 1. Course Overview & Mindset

### Filosofi Inti: "The Client is in the Hands of the Enemy"
Mengembangkan arsitektur server game menuntut paradigma komputasi yang fundamental berbeda dari *web backend* konvensional. Di dunia web, arsitektur didominasi oleh protokol *request-response* berbasis *stateless* I/O-bound. Sebaliknya, *server-side game development* beroperasi di ranah:
- **Authoritative Execution & Zero-Trust:** Klien hanyalah terminal input/output visual yang tidak tepercaya. Server memegang kendali penuh atas simulasi fisika, kalkulasi state, validasi pergerakan, dan konsistensi logis dunia game.
- **Latency Budget & Tick-Rate Cadence:** Server game terikat pada siklus pemrosesan diskrit (*game tick loop*). Pada tick rate 64 Hz, server hanya memiliki *budget* waktu **15,625 milidetik** per frame untuk mengeksekusi I/O jaringan, rekonsiliasi state, pembaruan *spatial partition*, evaluasi AI/fisika, dan serialisasi data ke ratusan entitas tanpa deviasi (*tick drift*).
- **Extreme Bandwidth Economy:** Serialisasi JSON/XML diharamkan di jalur pertukaran data *in-game*. Arsitek server game wajib menguasai bit-packing, kuantisasi floating-point, *delta compression*, dan serialisasi skema biner (FlatBuffers, Protobuf, memory-mapped buffers) demi menjaga efisiensi throughput jaringan.
- **Stateful High-Concurrency vs Eventual Consistency:** Mengelola state dinamis dari jutaan entitas spasial yang berinteraksi dalam frekuensi tinggi membutuhkan strategi *in-memory caching*, *actor model*, *sharding*, dan *seamless world handoff* yang presisi tanpa jeda jaringan (*desync*).

```
                      +-----------------------------+
                      |   CLIENT (Untrusted Node)   |
                      |  - Input Sampling           |
                      |  - Client-Side Prediction   |
                      |  - Entity Interpolation     |
                      +--------------+--------------+
                                     |
                         Raw Inputs  |  Snapshots / Deltas
                       (Bit-Packed)  |  (Quantized UDP)
                                     v
                      +-----------------------------+
                      | DEDICATED GAME SERVER (DGS) |
                      |  Authoritative Simulation   |
                      |                             |
                      |  [ Tick Loop: Fixed dt ]    |
                      |  +-- Input Processing       |
                      |  +-- Physics & Spatial Hashing
                      |  +-- Lag Compensation/Rewind|
                      |  +-- Delta Compression      |
                      +--------------+--------------+
                                     |
                      Persistence &  | Session/Match State
                      Internal RPC   | (NATS / gRPC)
                                     v
                      +-----------------------------+
                      |  DISTRIBUTED PLATFORM MESH  |
                      |  - Fleet Manager (Agones)   |
                      |  - Spatial Matchmaking      |
                      |  - Memory Grid (Redis/DB)   |
                      +-----------------------------+
```

---

## 2. Learning Roadmap

```text
Server-Side Game Developer Roadmap
├── Bab 01: Fondasi Jaringan & Protokol Transport Game Rendah Latensi
├── Bab 02: Model Arsitektur Dedicated Game Server & Loop Engine
├── Bab 03: Sinkronisasi State, Interpolasi, & Prediksi Klien
├── Bab 04: Spatial Partitioning & Interest Management (AOI)
├── Bab 05: Sistem Matchmaking, Lobi, & Manajemen Armada Game (Fleet)
├── Bab 06: Pola Persistensi, State Management, & Ekonomi Game
├── Bab 07: Distributed Game Server Clustering & Actor Model
├── Bab 08: Keamanan Server, Validasi Otoritatif, & Anti-Cheat
├── Bab 09: Observabilitas, Telemetri Real-Time, & Profiling Tick
└── Bab 10: Capstone Project: Production-Ready Multiplayer Battle Arena Engine
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Jaringan & Protokol Transport Game Rendah Latensi](./01-network-fundamentals/)
Membedah tumpukan jaringan dari layer transport hingga protokol aplikasi khusus game multiplayer yang mengutamakan kecepatan dan pencegahan *head-of-line blocking*.
* [01-transport-layer-udp-quic.md](./01-network-fundamentals/01-transport-layer-udp-quic.md) — Analisis komparatif TCP, UDP mentah, QUIC, dan WebRTC DataChannels untuk skenario game *real-time*.
* [02-reliable-udp-custom-protocol.md](./01-network-fundamentals/02-reliable-udp-custom-protocol.md) — Rekayasa protokol Reliable-UDP (R-UDP) kustom: mekanisme ACK/NACK, *packet sequencing*, *channeling* (reliable vs unreliable), dan manajemen saturasi *bandwidth*.
* [03-packet-serialization-flatbuffers.md](./01-network-fundamentals/03-packet-serialization-flatbuffers.md) — Serialisasi data biner berkecepatan tinggi: FlatBuffers (zero-copy deserialization), Protocol Buffers, dan teknik *bit-packing* manual.

### [Bab 02: Model Arsitektur Dedicated Game Server & Loop Engine](./02-authoritative-server-architecture/)
Membangun fondasi komputasi server game berbasis otoritas absolut dan eksekusi deterministik dalam ruang waktu diskrit.
* [01-game-loop-tick-rate-cadence.md](./02-authoritative-server-architecture/01-game-loop-tick-rate-cadence.md) — Anatomi *fixed-timestep game loop*, penanganan *tick drift*, akumulator delta-time, dan pencegahan degradasi performa (*spiral of death*).
* [02-authoritative-vs-p2p-topologies.md](./02-authoritative-server-architecture/02-authoritative-vs-p2p-topologies.md) — Komparasi topologi: Peer-to-Peer, Listen Server, Client-Server Otoritatif, dan Relay Architectures beserta matriks trade-off masing-masing.
* [03-headless-runtimes-and-isolation.md](./02-authoritative-server-architecture/03-headless-runtimes-and-isolation.md) — Implementasi server *headless* (C++, Rust, Go) vs runtime komersial (Unreal Server/Unity Dedicated Server) serta isolasi proses.

### [Bab 03: Sinkronisasi State, Interpolasi, & Prediksi Klien](./03-state-sync-and-lag-compensation/)
Mengatasi latensi transmisi fisik (kecepatan cahaya dalam kabel fiber) menggunakan teknik matematis sinkronisasi state tingkat lanjut.
* [01-snapshot-interpolation-delta.md](./03-state-sync-and-lag-compensation/01-snapshot-interpolation-delta.md) — *Snapshot Interpolation* (Hermite/Spline), *Extrapolation/Dead Reckoning*, dan *Delta State Compression*.
* [02-client-prediction-reconciliation.md](./03-state-sync-and-lag-compensation/02-client-prediction-reconciliation.md) — Implementasi algoritma prediksi klien, *input buffer tagging*, *server acknowledgement*, dan koreksi desinkronisasi halus (*soft reconciliation*).
* [03-lag-compensation-hitbox-rewind.md](./03-state-sync-and-lag-compensation/03-lag-compensation-hitbox-rewind.md) — Algoritma *Lag Compensation*: server-side history buffer, *rewind-and-raycast*, determinisme raycast hitbox, dan mitigasi eksploitasi peek-advantage.

### [Bab 04: Spatial Partitioning & Interest Management (AOI)](./04-spatial-partitioning-and-aoi/)
Optimasi kompleksitas komputasi $O(N^2)$ menjadi $O(N \log N)$ atau $O(1)$ untuk distribusi state ribuan entitas di dalam dunia game.
* [01-spatial-indexing-grid-quadtree.md](./04-spatial-partitioning-and-aoi/01-spatial-indexing-grid-quadtree.md) — Struktur data spasial: *Uniform Hash Grids*, *Quadtrees*, *Octrees*, dan *Bounding Volume Hierarchies* (BVH) dinamis.
* [02-interest-management-aoi-filtering.md](./04-spatial-partitioning-and-aoi/02-interest-management-aoi-filtering.md) — Arsitektur *Area of Interest* (AOI): pemfilteran paket berbasis radius pandang, *visibility frustum culling*, dan *publish-subscribe* spasial.
* [03-delta-compression-state-quantization.md](./04-spatial-partitioning-and-aoi/03-delta-compression-state-quantization.md) — Kuantisasi floating-point untuk koordinat transformasi (posisi, rotasi Euler, kuaternion) dan encoding *diff-mask* entitas.

### [Bab 05: Sistem Matchmaking, Lobi, & Manajemen Armada Game (Fleet)](./05-matchmaking-and-session-orchestration/)
Mendesain platform penyeleksi pemain berbasis performa dan orkestrasi siklus hidup instans server game secara dinamis.
* [01-matchmaking-engines-elo-mmr.md](./05-matchmaking-and-session-orchestration/01-matchmaking-engines-elo-mmr.md) — Algoritma matchmaking: ELO, Glicko-2, TrueSkill, dan pengelompokan tiket berbasis kueri multidimensi (latensi, region, skill level).
* [02-session-lifecycle-state-machine.md](./05-matchmaking-and-session-orchestration/02-session-lifecycle-state-machine.md) — Mesin state sesi game (*Finite State Machine*): transisi alur Warm-up, Waiting for Players, In-Game Match, Sudeten Death, hingga Post-Match Teardown.
* [03-game-fleet-management-agones.md](./05-matchmaking-and-session-orchestration/03-game-fleet-management-agones.md) — Orkestrasi armada Dedicated Game Server menggunakan Kubernetes dan Agones: alokasi pod instan, *zero-downtime draining*, dan autoscaling reaktif.

### [Bab 06: Pola Persistensi, State Management, & Ekonomi Game](./06-game-persistence-and-economy/)
Menangani persistensi inventaris, transaksi item, dan status akun yang tahan terhadap latensi tinggi dan lonjakan konkurensi data.
* [01-in-memory-caching-redis-dragonfly.md](./06-game-persistence-and-economy/01-in-memory-caching-redis-dragonfly.md) — Pemanfaatan Redis/Dragonfly untuk *ephemeral state*: session locks, dynamic leaderboards (Sorted Sets), dan pub-sub internal node.
* [02-inventory-virtual-economy-acid.md](./06-game-persistence-and-economy/02-inventory-virtual-economy-acid.md) — Desain transaksi ekonomi virtual anti-duplikasi: pemanfaatan ACID transaksi terdistribusi, isolasi serializable, dan optimasi *pessimistic locking*.
* [03-write-behind-caching-and-event-sourcing.md](./06-game-persistence-and-economy/03-write-behind-caching-and-event-sourcing.md) — Pola arsitektur *Write-Behind Caching*, Event Sourcing untuk audit riwayat ekonomi game, dan rekonsiliasi data *offline*.

### [Bab 07: Distributed Game Server Clustering & Actor Model](./07-distributed-clusters-actor-model/)
Membangun arsitektur server game skala masif (MMO dan Open-World) tanpa batas pemrosesan pada satu mesin komputasi fisik.
* [01-actor-model-orleans-protoactor.md](./07-distributed-clusters-actor-model/01-actor-model-orleans-protoactor.md) — Implementasi Actor Model (ProtoActor/Orleans) untuk mewakili entitas game (Pemain, Guild, Ruangan) sebagai aktor virtual terisolasi.
* [02-seamless-world-cell-sharding.md](./07-distributed-clusters-actor-model/02-seamless-world-cell-sharding.md) — Strategi pemecahan dunia (*Cell Sharding*): *boundary crossing*, transfer entitas mulus (*seamless handoff* antar server), dan sinkronisasi batas zona (*ghost entities*).
* [03-cross-node-rpc-pubsub-nats.md](./07-distributed-clusters-actor-model/03-cross-node-rpc-pubsub-nats.md) — Jaringan komunikasi antar-server (*Inter-Process Communication*): integrasi NATS JetStream dan performa tinggi gRPC streaming.

### [Bab 08: Keamanan Server, Validasi Otoritatif, & Anti-Cheat](./08-anti-cheat-and-server-security/)
Memitigasi eksploitasi, peretasan paket, dan manipulasi memori klien melalui validasi server yang ketat dan deterministik.
* [01-authoritative-physics-validation.md](./08-anti-cheat-and-server-security/01-authoritative-physics-validation.md) — Validasi integritas pergerakan: mitigasi *speed-hack*, *teleport-hack*, *fly-hack*, dan *no-clip* menggunakan simulasi verifikasi berbasis vektor server.
* [02-packet-manipulation-replay-attacks.md](./08-anti-cheat-and-server-security/02-packet-manipulation-replay-attacks.md) — Proteksi protokol: mitigasi *packet replay*, *packet injection*, manipulasi sequence ID, enkripsi payload UDP adaptif, dan proteksi integritas payload (HMAC).
* [03-ddos-mitigation-udp-flood-protection.md](./08-anti-cheat-and-server-security/03-ddos-mitigation-udp-flood-protection.md) — Ketahanan infrastruktur game terhadap serangan DDoS: mitigasi UDP reflection floods, *amplification attack*, token handshake *stateless*, dan integrasi firewall level kernel (eBPF/XDP).

### [Bab 09: Observabilitas, Telemetri Real-Time, & Profiling Tick](./09-observability-profiling-metrics/)
Membedah performa internal mesin server game secara presisi mikrosekon saat ribuan pemain terkoneksi secara simultan.
* [01-tick-time-budgeting-profiling.md](./09-observability-profiling-metrics/01-tick-time-budgeting-profiling.md) — Pengukuran *tick budget*: deteksi *micro-stuttering*, profil alokasi memori, isolasi *garbage collection pause*, dan flamegraph analisis CPU.
* [02-telemetry-opentelemetry-prometheus.md](./09-observability-profiling-metrics/02-telemetry-opentelemetry-prometheus.md) — Metrik telemetri game: pengukuran *network round-trip time* (RTT), *packet loss rate*, *tick drift*, rasio kompresi, dan visualisasi Grafana real-time.
* [03-network-jitter-simulation-packet-replay.md](./09-observability-profiling-metrics/03-network-jitter-simulation-packet-replay.md) — *Chaos engineering* jaringan: simulasi *jitter*, *packet drop*, rekaman sesi paket game (*deterministic replay debugging*), dan audit desinkronisasi.

### [Bab 10: Capstone Project: Production-Ready Multiplayer Battle Arena Engine](./10-capstone-project/)
Sintesis seluruh materi kurikulum ke dalam satu implementasi sistem backend game berskala enterprise yang diuji beban masif.
* [01-architecture-specs-requirements.md](./10-capstone-project/01-architecture-specs-requirements.md) — Spesifikasi arsitektur enterprise, kontrak data paket biner, dan diagram domain sistem battle arena.
* [02-implementation-guide-benchmarking.md](./10-capstone-project/02-implementation-guide-benchmarking.md) — Panduan perakitan server game deterministik, implementasi lag compensation, dan bot stress-test harness.
* [03-production-deployment-verification.md](./10-capstone-project/03-production-deployment-verification.md) — Panduan deployment pada klaster Kubernetes Agones, konfigurasi autoscaling, dan verifikasi batas SLA.

---

## 4. Spesifikasi Capstone Project Enterprise

### Nama Proyek: **Project "Aetheris Arena" (Distributed Authoritative Action Combat Backend)**

#### Deskripsi
Peserta diwajibkan merancang, membangun, menguji, dan mendeploy backend game multiplayer aksi kompetitif (Fast-Paced Arena Shooter/Brawler) berkapasitas 10 pemain per ruangan (*instance*) dengan kemampuan ekspansi multi-wilayah (*multi-region*). Seluruh kalkulasi status proyektil, tabrakan, pergerakan, dan inventaris wajib dikontrol penuh oleh Dedicated Game Server (DGS) tanpa intervensi logika penentu di sisi klien.

#### Arsitektur Sistem Capstone
```
+--------------------------------------------------------------------------+
|                          EDGE & ROUTING INGRESS                          |
|  Global Anycast IP / AWS Route 53 Multi-Region Geolocation Ingress       |
+------------------------------------+-------------------------------------+
                                     |
              +----------------------+----------------------+
              | UDP Traffic                                 | HTTP/Websocket
              v                                             v
+-------------------------------+             +----------------------------+
| AGONES GAME SERVER CLUSTER    |             | PLATFORM SERVICES (K8S)    |
| (Dedicated Game Servers)      |             | - Matchmaking Core         |
| - Custom R-UDP / ENet Socket  |  RPC (gRPC) | - Auth & Player Profiles   |
| - Fixed 60 Hz Tick Loop       |<----------->| - Virtual Economy & Wallet |
| - Spatial Hash AOI            |             | - Redis Session Cache      |
| - History Buffer (Rewind 1s)  |             +--------------+-------------+
| - FlatBuffers Binary Channel  |                            |
+---------------+---------------+                            v
                |                             +----------------------------+
                | Metrics / Traces            | PERSISTENCE LAYER          |
                v                             | - CockroachDB / PostgreSQL |
+-------------------------------+             |   (Strict Serialized ACID) |
| OBSERVABILITY MESH            |             | - Dragonfly / Redis Cluster|
| - Prometheus + OpenTelemetry  |             +----------------------------+
| - Grafana Operational Dash    |
+-------------------------------+
```

#### Persyaratan Teknis Inti (Non-Negotiable Deliverables)
1. **Dedicated Game Server Core:**
   - Dikembangkan menggunakan bahasa pemrograman sistem dengan performa deterministik: **Rust, C++, atau Go** (dengan manajemen alokasi heap nol pada alur tick utama).
   - Menjalankan *authoritative tick loop* stabil pada **60 Hz ($\pm 0.5\text{ ms}$ jitter)**.
   - Mengimplementasikan protokol R-UDP sendiri atau mengintegrasikan library tingkat rendah (seperti libdatachannel, ENet, atau KCP).
   - Seluruh payload jaringan wajib menggunakan serialisasi biner terkompresi (**FlatBuffers** atau **Protocol Buffers**).
2. **Lag Compensation Engine:**
   - Server menyimpan riwayat state hitbox entitas minimum selama 1000 milidetik (*circular history buffer*).
   - Mekanisme verifikasi tembakan/pukulan (*hit registration*) melakukan rekonstruksi posisi target mundur ke waktu lampau (*rewind timestamp*) berdasarkan latensi pemain yang menembak, divalidasi dengan batasan RTT maksimum (maks. clamp 250ms).
3. **Spatial Filtering & Interest Management:**
   - Membagi area peta pertarungan menggunakan *Uniform Grid Spatial Hash*.
   - Server tidak boleh mengirim data entitas yang berada di luar jangkauan sensoris (*AOI*) pemain terkait.
4. **Sistem Matchmaking & Orchestration:**
   - Matchmaker bertugas mengelompokkan 10 pemain berdasarkan parameter ELO/MMR dan kesamaan ping wilayah.
   - Server dialokasikan secara dinamis menggunakan Custom Resource Definitions (CRD) **Agones** di atas klaster Kubernetes.
5. **Keamanan & Validasi Anti-Cheat:**
   - Validasi vektor akselerasi pergerakan (*speed enforcement*). Pergerakan yang melanggar batas fisika (*speed/teleport*) harus langsung dibatalkan (*reverted/snapped back*) oleh server.
   - Mitigasi serangan eksploitasi waktu input (*client clock manipulation*) melalui time-synchronization berbasis paket timestamp.
6. **Stress Testing & SLA Targets:**
   - Menyediakan modul *Headless Bot Client Swarm* yang mampu mensimulasikan minimal **1.000 bot paralel** yang mengirim input acak dengan gangguan jaringan terkontrol (latensi buatan 50–200ms, *packet loss* 5%).
   - **Target Metrik:**
     - Penggunaan CPU Server per instance: $< 40\%$ pada 1 core CPU saat ruangan penuh.
     - Tick Drift: $< 1\%$ deviasi dari target 16.66ms.
     - Alokasi Memori Run-time: Nol alokasi dinamis baru per tick setelah inisialisasi arena selesai (*zero steady-state allocation*).

---

## 5. Standar Kontribusi & Panduan Belajar

- **Praktek Nyata (Hands-On Code First):** Setiap modul dalam kurikulum ini dilengkapi dengan implementasi kode fungsional, pengujian unit, dan skrip *benchmark*. Teori harus selalu dibuktikan dengan data profiler.
- **Reproduksibilitas:** Seluruh dependensi, simulator latensi, dan alat deployment dikemas menggunakan container Docker dan manifest Kubernetes lokal (Kind/Minikube) untuk memastikan keseragaman lingkungan pengembangan.
- **Ketelitian Standar Industri:** Kode yang ditulis harus memperlakukan performa, konkurensi aman (*thread safety*), dan penanganan error jaringan sebagai prioritas kelas satu.

Mulai perjalanan kurikulum dari [Bab 01: Fondasi Jaringan & Protokol Transport Game Rendah Latensi](./01-network-fundamentals/).