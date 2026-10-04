# Bab 10: API Gateway & Edge Architectures
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Arsitektur Internal Data Plane Gateway:** Membedah siklus hidup *connection thread pool*, *event loop non-blocking I/O*, dan *filter chain execution* pada gateway modern kelas L7 (Envoy Core Engine).
2. **Mengimplementasikan Dynamic Configuration via Control Plane (xDS):** Merancang sinkronisasi konfigurasi routing dinamis tanpa *restarting* atau *packet dropping* menggunakan protokol xDS (LDS, RDS, CDS, EDS).
3. **Membangun Custom Extension & Filter Engine:** Mengembangkan *edge plugin* menggunakan Lua atau WebAssembly (Wasm) untuk *payload inspection*, *header sanitization*, dan *dynamic contextual routing*.
4. **Menerapkan Distributed Rate Limiting & Edge Resilience:** Mengonfigurasi algoritma *Token Bucket/Sliding Window Counter* terdistribusi berbasis Redis Cluster, dipadukan dengan *Outlier Detection* dan *Locality-Prioritized Load Balancing*.
5. **Mengamankan Perimeter Edge dengan Zero-Trust mTLS:** Mengonfigurasi terminasi TLS di Edge, rotasi sertifikat otomatis via Secret Discovery Service (SDS), serta propagasi identitas kriptografis downstream-to-upstream.

---

### 2. Prerequisite
* Pemahaman mendalam tentang Layer 4 (TCP, TLS Handshake) dan Layer 7 (HTTP/1.1, HTTP/2 multiplexing, HTTP/3 QUIC).
* Pengalaman mengoperasikan container orchestration (Kubernetes Networking: CNI, Ingress, ClusterIP, NodePort).
* Pemahaman fundamental konsep konkurensi: I/O Multiplexing (`epoll`/`kqueue`), thread pool, non-blocking I/O.
* Kemahiran dalam konfigurasi declarative (YAML/JSON) dan pemrograman sistem dasar (Go, Rust, atau C++ / Lua untuk penulisan plugin).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur API Gateway modern di tingkat enterprise telah bergeser dari model *monolithic single-threaded/thread-per-connection blocking proxy* (seperti Apache Traffic Server generasi awal atau implementasi berbasis Tomcat/JVM) menuju **Event-Driven, Non-Blocking, Multi-Threaded Asynchronous Architecture** yang dipelopori oleh Envoy Proxy, Nginx core, dan Traefik.

```
       Client Request (HTTP/1.1, H2, H3)
                     │
                     ▼
┌───────────────────────────────────────────────────────────┐
│               ENVOY LISTENER (L4 - TCP)                   │
│   - Socket Allocation (SO_REUSEPORT)                      │
│   - TLS Handshake & Termination (BoringSSL / SDS)         │
│   - Listener Filters (Proxy Protocol, Original Dst)       │
└────────────────────────────┬──────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────┐
│           NETWORK FILTER CHAIN (L4 to L7)                 │
│   - Read/Write Filters                                    │
│   - HTTP Connection Manager (HCM) Filter Engine           │
└────────────────────────────┬──────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────┐
│              HTTP FILTER CHAIN (L7 Engine)                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ 1. Tracing Filter (OpenTelemetry / B3 Injection)    │  │
│  │ 2. Wasm / Lua Filter (AuthN / Token Validation)     │  │
│  │ 3. Distributed Rate Limit Filter (gRPC RLS Engine)  │  │
│  │ 4. Router Filter (Match Path, Header, Weight)       │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────┬──────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────┐
│                   UPSTREAM CLUSTERS                       │
│   - Dynamic Discovery (EDS / DNS)                         │
│   - Load Balancer (Round Robin, Maglev, Ring Hash)        │
│   - Connection Pool (HTTP/2 Multiplexing, Keep-Alive)     │
│   - Outlier Detection & Circuit Breaking (Max Conns, etc) │
└────────────────────────────┬──────────────────────────────┘
                             │
                             ▼
               Upstream Services (Microservices)
```

#### 3.1. Threading Model dan Event Loop
Envoy mengadopsi model *thread-per-core*. Terdapat satu **Main Thread** yang bertanggung jawab atas koordinasi, pembacaan konfigurasi, inisialisasi xDS, dan pemantauan sistem, serta sejumlah **Worker Threads** yang terikat secara independen pada *CPU core* (CPU affinity):
* **Main Thread:** Menghandle Control Plane xDS API, mengompilasi filter chains, dan mendistribusikan konfigurasi immutable ke Worker Threads via RCU (Read-Copy-Update) pointer swaps.
* **Worker Threads:** Masing-masing menjalankan *non-blocking event loop* berbasis `libevent`. Worker thread mendengarkan koneksi masuk menggunakan kernel flag `SO_REUSEPORT`, memungkinkan kernel mendistribusikan koneksi TCP masuk secara merata tanpa *lock contention* antar-worker.
* **Memory & Buffer Management:** Envoy mengalokasikan memori dalam fragmen menggunakan struktur data `Buffer::Instance` (biasanya berbasis *chain of memory slices* / `evbuffer`). Ini mencegah realokasi memori linear yang mahal dan meminimalkan latensi *Zero-Copy streaming proxying*.

#### 3.2. Data Plane vs Control Plane Decoupling (xDS Architecture)
Pemisahan murni antara konfigurasi dan runtime eksekusi diwujudkan melalui protokol xDS (*Any Dynamic Discovery Service*) berbasis gRPC bidirectional streaming:
* **LDS (Listener Discovery Service):** Mengelola listening port, TLS context, dan L4 network filters secara dinamis.
* **RDS (Route Discovery Service):** Mengubah tabel routing L7 (VirtualHosts, Path Regex matching, Header-based routing, direct responses) secara atomik tanpa memutus koneksi aktif.
* **CDS (Cluster Discovery Service):** Mengelola daftar upstream clusters, protokol upstream (misal H2 upstream, TLS context upstream), dan kebijakan load balancing.
* **EDS (Endpoint Discovery Service):** Menyediakan resolusi IP dan port dari instance upstream secara real-time dari registri seperti Kubernetes API Server, Consul, atau AWS Cloud Map.
* **SDS (Secret Discovery Service):** Mentransmisikan sertifikat x509, private keys, dan CA bundles langsung ke worker thread memory tanpa persistensi disk lokal.

---

### 4. Why & What

| Fitur / Karakteristik | Traditional Edge Proxy (Nginx/HAProxy Legacy) | Modern Service-Mesh / Edge Gateway (Envoy/Kong) |
| :--- | :--- | :--- |
| **Model Konfigurasi** | Berbasis file statis (`nginx.conf`), butuh `reload` SIGHUP. | Dynamic API-driven (xDS/gRPC streaming), zero-downtime, sub-second update. |
| **Extensibility** | C modules (harus recompile binary) atau embedding Lua (Nginx OpenResty). | Wasm (WebAssembly) Sandboxed Plugins, Lua, gRPC External Processing (ext_proc). |
| **Observabilitas** | Parsing file log teks, log metric terbatas. | Native OpenTelemetry, Prometheus metrics L4/L7, distributed trace context auto-injection. |
| **Protokol Downstream** | HTTP/1.1, HTTP/2. | HTTP/1.1, HTTP/2, HTTP/3 (QUIC), gRPC-Web, raw TCP/TLS with SNI routing. |
| **Resilience Model** | Max retries dasar, failover pasif. | Outlier detection, circuit breaking per cluster, speculative retries, hedged requests. |

#### Why Deep Architectural Engineering Matters at the Edge:
1. **Mitigasi *Thundering Herd*:** Edge Gateway adalah dinding pertahanan pertama; jika arsitektur I/O memblokir satu thread, antrean TCP SYN backlog akan meluap, memicu *cascade failure* ke upstream.
2. **Deterministic Latency P99/P999:** Edge processing harus selesai dalam rentang sub-milidetik (< 2ms overhead). Implementasi filter yang buruk (misalnya mem-parsing body JSON secara berulang atau pemanggilan sinkronus I/O di filter L7) akan menghancurkan performa P999.
3. **Zero Trust Topology:** Menjamin otentikasi identitas mTLS terjadi di ingress perimeter, mendegradasi trust level downstream yang tidak valid sebelum menyentuh virtual network internal.

---

### 5. How (Workflow Detail)

Alur penanganan paket secara end-to-end dari Downstream Client ke Upstream Service di dalam L7 Gateway Engine:

```
[Downstream Client] 
        │ 
        │ 1. TCP SYN, Handshake, TLS Negotiation (ALPN: h2)
        ▼
[Worker Thread Event Loop]
        │ 
        │ 2. Match Listener by IP/Port & Filter Chain by SNI
        ▼
[HCM (HTTP Connection Manager)]
        │ 
        │ 3. Parse HTTP/2 Frames (HEADERS, DATA) into Memory Slices
        ▼
[HTTP Filter Chain]
        │ ── Step 3a: Tracing Filter injects/extracts traceparent (W3C)
        │ ── Step 3b: Rate Limit Filter calls gRPC RLS Cluster (Check quota)
        │ ── Step 3c: Wasm Filter verifies JWT/PASETO token (Cryptographic validation)
        │ ── Step 3d: Router Filter selects Upstream Cluster via RDS rules
        ▼
[Cluster Manager & Load Balancer]
        │ 
        │ 4. Evaluate Upstream Health (Outlier check)
        │ 5. Select Endpoint via Maglev / Weighted Round Robin
        ▼
[Connection Pool]
        │ 
        │ 6. Reuse warm HTTP/2 stream or initiate new upstream TCP/TLS
        ▼
[Upstream Microservice Instance]
```

1. **Kernel-to-Worker Ingestion:** Paket TCP diterima socket NIC. Kernel mendistribusikan soket ke Worker Thread tertentu via `SO_REUSEPORT`.
2. **TLS Termination & L4 Matching:** BoringSSL melakukan terminasi TLS. SNI dievaluasi untuk memilih sertifikat x509 yang sesuai via SDS.
3. **HTTP Connection Manager (HCM) Entry:** HCM mengubah stream raw byte TCP menjadi stream frame HTTP/2 atau HTTP/1.
4. **Filter Chain Traversal (Iterative Pipeline):**
   * Filter 1 (`envoy.filters.http.jwt_authn`): Memvalidasi tanda tangan kriptografis token di header Authorization.
   * Filter 2 (`envoy.filters.http.ratelimit`): Mengirimkan pesan gRPC *CheckRequest* ke Redis-backed rate-limiter service.
   * Filter 3 (`envoy.filters.http.wasm`): Mengeksekusi logic kustom (misal enkripsi payload parsial, dynamic routing injection).
   * Filter 4 (`envoy.filters.http.router`): Menentukan target cluster berdasarkan kriteria VirtualHost.
5. **Connection Pooling & Upstream Forwarding:** Router Filter berkoordinasi dengan *Cluster Manager*. Target IP dipilih dari EDS table. Jika koneksi HTTP/2 tersedia, request dimultiplexing ke stream upstream baru; jika belum, koneksi baru dibuat secara asinkron.
6. **Response Pipeline:** Data respons dialirkan kembali (*chunked/streamed*) tanpa buffering total (kecuali ada filter eksplisit yang memerlukan buffer penuh).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Super-Sibuk (Terminal Hub)
* **Downstream Client:** Penumpang yang mendarat dari berbagai maskapai (berbagai bahasa/protokol: HTTP/1, HTTP/2, HTTP/3).
* **SO_REUSEPORT:** Beberapa gerbang masuk terminal yang dibuka serentak. Polisi perbatasan mengarahkan bus penumpang secara acak-merata ke masing-masing pintu tanpa terjadi antrean tunggal.
* **Worker Thread Event Loop:** Petugas imigrasi di tiap loket yang bekerja secara non-stop. Jika satu dokumen penumpang membutuhkan verifikasi visa lama (I/O lambat), penumpang dipindahkan ke jalur tunggu asinkron tanpa menahan antrean di belakangnya.
* **Filter Chain:** Jalur pemeriksaan keamanan berurutan: X-Ray barang bawaan (Tracing), validasi paspor (JWT Auth), kuota bagasi (Rate Limiter), dan pengecekan visa khusus (Wasm Filter).
* **Router & Cluster Connection Pool:** Pintu lorong transit menuju pesawat lanjutan (Upstream Microservice). Armada bus internal bandara (Connection Pool) sudah dalam kondisi mesin menyala (*warm keep-alive*), siap mengantar penumpang tanpa menyalakan armada baru dari nol.

```
                          SO_REUSEPORT (Kernel L4 Balance)
                                ┌───────┴───────┐
                                ▼               ▼
                         [Worker 0]          [Worker 1]
                       (Core 0 Event Loop)  (Core 1 Event Loop)
                                │               │
                       ┌────────▼────────┐     ...
                       │ Filter Chain:   │
                       │ 1. Tracing      │
                       │ 2. Rate Limit   │
                       │ 3. Wasm / Auth  │
                       │ 4. Router       │
                       └────────┬────────┘
                                │ (Upstream Stream Acquisition)
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [Upstream Cluster: Order]        [Upstream Cluster: User]
    ┌───────────────────────────┐    ┌───────────────────────────┐
    │ ConnPool: [H2] [H2] [H2]  │    │ ConnPool: [H2] [H2]       │
    │ Endpoints (EDS):          │    │ Endpoints (EDS):          │
    │  - 10.244.1.15:8080 (OK)  │    │  - 10.244.2.11:8080 (OK)  │
    │  - 10.244.1.16:8080 (OK)  │    │  - 10.244.2.12:8080 (OUT) │ (Ejected by Outlier Det)
    └───────────────────────────┘    └───────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Fundamental Envoy Static Configuration
Konfigurasi dasar Envoy (`envoy-simple.yaml`) yang mengimplementasikan HTTP Connection Manager, logging terstruktur, dan cluster routing statis.

```yaml
static_resources:
  listeners:
  - name: listener_ingress_http
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 8080
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          codec_type: AUTO
          route_config:
            name: local_route
            virtual_hosts:
            - name: core_backend
              domains: ["*"]
              routes:
              - match:
                  prefix: "/api/v1/health"
                direct_response:
                  status: 200
                  body:
                    inline_string: '{"status":"UP","gateway":"envoy-edge"}'
              - match:
                  prefix: "/api/v1/orders"
                route:
                  cluster: order_service_cluster
                  timeout: 2.5s
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: order_service_cluster
    connect_timeout: 0.25s
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: order_service_cluster
      endpoints:
      - lb_endpoints:
        