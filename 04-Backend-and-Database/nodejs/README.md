# Kurikulum Enterprise Engineering: Node.js Architecture & Performance Engineering

Selamat datang di kurikulum spesialisasi rekayasa perangkat lunak berbasis **Node.js**. Repositori ini menyajikan jalur akselerasi intensif berskala industri untuk mentransformasi pemahaman konseptual JavaScript menjadi kapabilitas teknis tingkat lanjut dalam merancang sistem terdistribusi, *high-throughput*, *low-latency*, dan *production-hardened*.

---

## 1. Course Overview & Mindset

### Target Audience
Kurikulum ini dirancang khusus untuk:
* **Senior Backend Engineer & Systems Developer** yang ingin menguasai abstraksi tingkat rendah runtime Node.js.
* **Software Architect** yang bertanggung jawab atas throughput, latensi p99, efisiensi resource memory/CPU, dan ketahanan sistem produksi berskala enterprise.
* **DevOps & Platform Engineer** yang membutuhkan pemahaman mendalam tentang profiling, diagnostik memory dump, dan observabilitas runtime V8.

### Mindset & Engineering Philosophy
Banyak pengembang menganggap Node.js sekadar ekosistem untuk membuat REST API cepat menggunakan Express atau framework sejenis. Paradigma tersebut mengabaikan esensi sejati runtime ini:
1. **Asynchronous Non-Blocking I/O Adalah Fondasi Kritis**: Menjalankan operasi komputasi intensif (*CPU-bound*) secara naif di atas thread tunggal JavaScript akan melumpuhkan seluruh siklus event loop. Menguasai Node.js berarti memahami batas tegas antara I/O non-blocking libuv dan alokasi resource CPU.
2. **Memory Safety & Garbage Collection Bukan Masalah Teoretis**: V8 mengelola alokasi memori secara agresif. Kesalahan penggunaan closure, event emitter tanpa listener cleanup, atau buffer retention yang serampangan akan memicu memory leak katastropik saat sistem menerima beban tinggi.
3. **Produksi Nyata vs. "Tutorial Hype"**: Kode di lingkungan produksi diukur dari latensi P99, stabilitas alokasi heap, efisiensi penanganan backpressure pada streams, zero-downtime lifecycle, serta integrasi native APM (*Application Performance Monitoring*), bukan sekadar respons kode `200 OK` lokal.

---

## 2. Learning Roadmap

```plaintext
Node.js Enterprise Architecture Roadmap
│
├── [Bab 01] V8 Engine & Libuv Architecture Internals
│   ├── Modul 01: V8 Memory Layout & Garbage Collection Lifecycles
│   ├── Modul 02: Libuv Thread Pool & Event Loop Execution Phases
│   └── Modul 03: Event Loop Starvation & Phase Microbenchmarking
│
├── [Bab 02] Advanced Asynchronous Programming & Concurrency
│   ├── Modul 01: Microtasks, Macrotasks, & NextTick Scheduling
│   ├── Modul 02: AsyncLocalStorage & Distributed Context Propagation
│   └── Modul 03: AbortController, Cancellation, & Resource Cleanup
│
├── [Bab 03] High-Performance I/O: Buffers, Streams, & File Systems
│   ├── Modul 01: Buffer Internals, Memory Allocation, & Zero-Copy Ops
│   ├── Modul 02: Stream Pipelines, Custom Transforms, & Backpressure
│   └── Modul 03: High-Throughput POSIX File System & Direct I/O
│
├── [Bab 04] Enterprise Networking: HTTP/S, HTTP/2, WebSockets, & gRPC
│   ├── Modul 01: Low-Level TCP/UDP Sockets & TLS Termination
│   ├── Modul 02: HTTP/2 Multiplexing & SSE Transport Layer
│   └── Modul 03: High-Performance gRPC Services with Protocol Buffers
│
├── [Bab 05] Multi-Threading, Clustering, & IPC
│   ├── Modul 01: Master-Worker Cluster Architecture & SO_REUSEPORT
│   ├── Modul 02: Worker Threads, SharedArrayBuffer, & Atomics
│   └── Modul 03: High-Throughput IPC & Custom Thread Pool Implementation
│
├── [Bab 06] Data Persistence & Distributed Cache Strategies
│   ├── Modul 01: Connection Pooling Mechanics & Transaction Isolation
│   ├── Modul 02: Distributed Caching, Cache Invalidation, & Stampede
│   └── Modul 03: Low-Latency Serialization (JSON vs Protobuf/MsgPack)
│
├── [Bab 07] Enterprise Security, Cryptography, & Hardening
│   ├── Modul 01: OpenSSL Integration, Node Crypto, & Constant-Time Ops
│   ├── Modul 02: Prototype Pollution, ReDoS, & Supply-Chain Auditing
│   └── Modul 03: OS Process Sandboxing & Node Permission Model
│
├── [Bab 08] Observability, Diagnostics, & Runtime Profiling
│   ├── Modul 01: Heap Profiling, Allocation Tracing, & Leak Analysis
│   ├── Modul 02: Clinic.js, Flamegraphs, & Event Loop Delay Metrics
│   └── Modul 03: Distributed Tracing with OpenTelemetry & Core Dumps
│
├── [Bab 09] Native Addons & Low-Level Interoperability
│   ├── Modul 01: Node-API (N-API) C++ Addon Development
│   ├── Modul 02: Rust Integration with Neon & NAPI-RS
│   └── Modul 03: WebAssembly (WASI) Runtime Integration
│
└── [Bab 10] Production Readiness & Resilient Microservice Architecture
    ├── Modul 01: Graceful Shutdown, Zombie Process & Signal Handling
    ├── Modul 02: Health Checks, Kubernetes Probes, & OOM Management
    └── Modul 03: Circuit Breakers, Bulkheading, & Chaos Resilience
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: V8 Engine & Libuv Architecture Internals](./01-v8-and-libuv-internals/README.md)
*Pondasi arsitektur internal runtime Node.js, pengelolaan memori V8, dan siklus loop event.*
* [Modul 01: V8 Memory Layout & Garbage Collection Lifecycles](./01-v8-and-libuv-internals/01-v8-memory-layout-and-gc.md)
* [Modul 02: Libuv Thread Pool & Event Loop Execution Phases](./01-v8-and-libuv-internals/02-libuv-threadpool-and-event-loop-phases.md)
* [Modul 03: Event Loop Starvation & Phase Microbenchmarking](./01-v8-and-libuv-internals/03-starvation-and-microbenchmarking.md)

### [Bab 02: Advanced Asynchronous Programming & Concurrency](./02-advanced-asynchronous-patterns/README.md)
*Mekanisme async tingkat lanjut, kontrol urutan eksekusi tugas, dan mitigasi kebocoran context.*
* [Modul 01: Microtasks, Macrotasks, & NextTick Scheduling](./02-advanced-asynchronous-patterns/01-microtasks-macrotasks-and-nexttick.md)
* [Modul 02: AsyncLocalStorage & Distributed Context Propagation](./02-advanced-asynchronous-patterns/02-asynclocalstorage-context-tracking.md)
* [Modul 03: AbortController, Cancellation, & Resource Cleanup](./02-advanced-asynchronous-patterns/03-abortcontroller-and-cleanup.md)

### [Bab 03: High-Performance I/O: Buffers, Streams, & File Systems](./03-streams-buffers-and-io/README.md)
*Teknik I/O berkecepatan tinggi, manipulasi biner di luar heap JS, dan eliminasi buffer bloat.*
* [Modul 01: Buffer Internals, Memory Allocation, & Zero-Copy Ops](./03-streams-buffers-and-io/01-buffer-internals-and-zero-copy.md)
* [Modul 02: Stream Pipelines, Custom Transforms, & Backpressure](./03-streams-buffers-and-io/02-streams-pipelines-and-backpressure.md)
* [Modul 03: High-Throughput POSIX File System & Direct I/O](./03-streams-buffers-and-io/03-posix-filesystem-and-direct-io.md)

### [Bab 04: Enterprise Networking: HTTP/S, HTTP/2, WebSockets, & gRPC](./04-enterprise-networking/README.md)
*Protokol jaringan, low-level socket handling, dan arsitektur komunikasi sinkron/asinkron.*
* [Modul 01: Low-Level TCP/UDP Sockets & TLS Termination](./04-enterprise-networking/01-tcp-udp-and-tls-sockets.md)
* [Modul 02: HTTP/2 Multiplexing & SSE Transport Layer](./04-enterprise-networking/02-http2-multiplexing-and-sse.md)
* [Modul 03: High-Performance gRPC Services with Protocol Buffers](./04-enterprise-networking/03-grpc-services-protobuf.md)

### [Bab 05: Multi-Threading, Clustering, & IPC](./05-multithreading-and-clustering/README.md)
*Optimalisasi hardware multi-core, pemanfaatan shared memory, dan komunikasi antar proses.*
* [Modul 01: Master-Worker Cluster Architecture & SO_REUSEPORT](./05-multithreading-and-clustering/01-cluster-architecture-and-reuseport.md)
* [Modul 02: Worker Threads, SharedArrayBuffer, & Atomics](./05-multithreading-and-clustering/02-worker-threads-and-sharedarraybuffer.md)
* [Modul 03: High-Throughput IPC & Custom Thread Pool Implementation](./05-multithreading-and-clustering/03-ipc-and-custom-threadpools.md)

### [Bab 06: Data Persistence & Distributed Cache Strategies](./06-data-persistence-and-caching/README.md)
*Pola interaksi database berperforma tinggi, serialisasi efisien, dan distributed state.*
* [Modul 01: Connection Pooling Mechanics & Transaction Isolation](./06-data-persistence-and-caching/01-connection-pools-and-transactions.md)
* [Modul 02: Distributed Caching, Cache Invalidation, & Stampede](./06-data-persistence-and-caching/02-distributed-cache-and-stampede.md)
* [Modul 03: Low-Latency Serialization (JSON vs Protobuf/MsgPack)](./06-data-persistence-and-caching/03-serialization-benchmarking.md)

### [Bab 07: Enterprise Security, Cryptography, & Hardening](./07-security-and-hardening/README.md)
*Proteksi sistem produksi, isolasi runtime, mitigasi kerentanan memori, dan kriptografi tepat guna.*
* [Modul 01: OpenSSL Integration, Node Crypto, & Constant-Time Ops](./07-security-and-hardening/01-openssl-crypto-and-timing-attacks.md)
* [Modul 02: Prototype Pollution, ReDoS, & Supply-Chain Auditing](./07-security-and-hardening/02-prototype-pollution-and-redos.md)
* [Modul 03: OS Process Sandboxing & Node Permission Model](./07-security-and-hardening/03-sandboxing-and-permissions.md)

### [Bab 08: Observability, Diagnostics, & Runtime Profiling](./08-observability-and-profiling/README.md)
*Monitoring mendalam kondisi runtime, mitigasi insiden produksi, dan tracing terdistribusi.*
* [Modul 01: Heap Profiling, Allocation Tracing, & Leak Analysis](./08-observability-and-profiling/01-heap-profiling-and-leak-analysis.md)
* [Modul 02: Clinic.js, Flamegraphs, & Event Loop Delay Metrics](./08-observability-and-profiling/02-flamegraphs-and-event-loop-delay.md)
* [Modul 03: Distributed Tracing with OpenTelemetry & Core Dumps](./08-observability-and-profiling/03-opentelemetry-and-core-dumps.md)

### [Bab 09: Native Addons & Low-Level Interoperability](./09-native-addons-and-interop/README.md)
*Eksploitasi performa C++ dan Rust di dalam ekosistem Node.js melalui Node-API.*
* [Modul 01: Node-API (N-API) C++ Addon Development](./09-native-addons-and-interop/01-napi-cpp-addon-development.md)
* [Modul 02: Rust Integration with Neon & NAPI-RS](./09-native-addons-and-interop/02-rust-integration-with-napi-rs.md)
* [Modul 03: WebAssembly (WASI) Runtime Integration](./09-native-addons-and-interop/03-webassembly-wasi-runtime.md)

### [Bab 10: Production Readiness & Resilient Microservice Architecture](./10-production-readiness-and-architecture/README.md)
*Standarisasi zero-downtime deployment, resilience pattern, dan kontrol kontainerisasi.*
* [Modul 01: Graceful Shutdown, Zombie Process & Signal Handling](./10-production-readiness-and-architecture/01-graceful-shutdown-and-signals.md)
* [Modul 02: Health Checks, Kubernetes Probes, & OOM Management](./10-production-readiness-and-architecture/02-k8s-probes-and-oom-management.md)
* [Modul 03: Circuit Breakers, Bulkheading, & Chaos Resilience](./10-production-readiness-and-architecture/03-circuit-breakers-and-resilience.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek
**ApexEngine: Distributed Low-Latency Financial Order Matching & Telemetry Gateway**

### Gambaran Umum
Peserta diwajibkan membangun gateway pencatatan dan matching order finansial terdistribusi secara *real-time* yang mampu menangani ribuan transaksi per detik dengan latensi konsisten sub-15ms pada P99. Proyek ini memadukan seluruh pilar kurikulum mulai dari integrasi networking tingkat rendah, manipulasi buffer biner, pemrosesan multi-threading, hingga observabilitas mutlak.

### Persyaratan Arsitektural & Fungsional
1. **Ingestion & Protocol Interface Layer**:
   * Dual-interface: gRPC (untuk microservice backend internal) dan WebSockets (untuk streaming order book ke client publik).
   * Parsing payload menggunakan format binary biner kustom atau Protocol Buffers untuk meminimalkan beban overhead JSON parsing V8.
2. **Core Matching Engine Execution**:
   * Order matching dieksekusi di dalam **Worker Threads** terpisah menggunakan `SharedArrayBuffer` dan `Atomics` untuk sinkronisasi state order book tanpa jeda I/O.
   * Modul kriptografi native (C++ via Node-API atau Rust via NAPI-RS) bertugas memvalidasi tanda tangan transaksi finansial secara paralel guna mencegah blocking pada main event loop.
3. **Data Streaming & Persistence**:
   * Implementasi Node.js Transform Streams dengan penanganan *backpressure* adaptif saat melakukan piping data ledger audit ke sistem storage.
   * Koneksi database berbasis PostgreSQL dengan connection pooler manual/tertuning yang menerapkan distributed locking via Redis (Redlock pattern) untuk mencegah *double-spending*.
4. **Resilience, Observability, & Hardening**:
   * Instrumentasi menyeluruh menggunakan OpenTelemetry SDK (traces, metrics, and logs) yang dipropagasi menggunakan `AsyncLocalStorage`.
   * Integrasi endpoint diagnostik untuk dump profiler V8 (heap dan CPU) secara aman saat runtime tanpa me-restart container.
   * Mekanisme graceful shutdown absolut: Menutup listener network, menyelesaikan proses transaksi aktif dalam rentang batas timeout tertentu, flush buffer logs, dan disconnect pool secara deterministik.

### Non-Functional Requirements (NFR) & Quality Gates
* **Throughput & Latency Target**: Mampu memproses minimal **25.000 Request Per Second (RPS)** pada stress test (Autocannon / k6) dengan **P99 Latency < 15ms**.
* **Memory Stability**: Zero memory leak. Grafik memory heap V8 harus menunjukkan pola gergaji (*sawtooth profile*) yang stabil di bawah pengujian beban berkelanjutan selama 60 menit.
* **Resilience**: Lolos pengujian *Chaos Engineering* (mematikan downstream worker secara acak tanpa menyebabkan kegagalan sistem global atau korupsi state data transaksi).

---
*Silabus ini disusun untuk mendorong standar keunggulan teknis tingkat tinggi. Silakan buka modul bab untuk memulai implementasi.*