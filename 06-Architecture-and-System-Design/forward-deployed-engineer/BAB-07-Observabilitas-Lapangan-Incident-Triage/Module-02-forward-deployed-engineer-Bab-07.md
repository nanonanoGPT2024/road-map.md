# BAB-07: Observabilitas Lapangan & Incident Triage
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Merancang & Mengimplementasikan Arsitektur Telemetri Terisolasi:** Membangun pipeline observabilitas tangguh (*metrics, logs, traces, profiles*) menggunakan OpenTelemetry Collector dan Vector pada lingkungan komputasi terkontrol (*air-gapped*, *on-premises enterprise*, dan *sovereign cloud*).
2. **Mengotomatisasi Redaksi Data & Pemenuhan Regulasi Privasi:** Mengembangkan filter mutasi berbasis eBPF dan regex engine berkinerja tinggi untuk membersihkan PII (*Personally Identifiable Information*) dan data rahasia perbankan/intelijen sebelum telemetri meninggalkan *perimeter firewall* klien.
3. **Mengeksekusi *Incident Triage* Tingkat Lanjut:** Menggunakan teknik *black-box debugging* via eBPF (*Extended Berkeley Packet Filter*), *kernel probes*, dan *continuous profiling* untuk mendeteksi *silent failures*, *TCP zero-window stalls*, dan *memory leaks* tanpa merestart pod atau mengakses *source code* sensitif klien.
4. **Menerapkan *Graceful Degradation* & *Backpressure Telemetry*:** Mengonfigurasi *disk-backed queueing*, *tail-based sampling*, dan *adaptive rate-limiting* untuk menjamin beban observabilitas tidak melebihi 1.5% alokasi CPU dan 2% alokasi memori sistem klien saat terjadi insiden katastropik.

---

### 2. Prerequisite

Sebelum menempuh modul ini, peserta wajib menguasai:
* Arsitektur Linux Kernel fundamental (VFS, IPC, Network Socket Buffer, sk_buff, syscall interfaces `sys_enter_*`).
* Konsep dasar observabilitas OpenTelemetry (Traces, Metrics, Logs, Baggage, Context Propagation).
* Orkestrasi kontainer tingkat lanjut (Kubernetes Custom Resource Definitions, DaemonSets, Envoy sidecar routing).
* Dasar pemrograman Go (untuk kustomisasi OpenTelemetry Collector) dan C/Rust (untuk penulisan program eBPF sederhana).
* Pemahaman mendalam tentang *networking*: TCP 3-way handshake, TLS termination, asymmetric routing, MTU/MSS clamping.

---

### 3. Concept & Internal Architecture (Mendalam)

Operasional Forward Deployed Engineer (FDE) menuntut kehadiran sistem di lingkungan infrastruktur yang tidak ramah (*hostile/constrained environments*). Berbeda dengan *Software-as-a-Service* (SaaS) murni di mana seluruh telemetri dapat dialirkan bebas ke Datadog, Grafana Cloud, atau AWS CloudWatch, instalasi enterprise di bank Tier-1, sektor pertahanan, atau instansi kesehatan mewajibkan data residensi absolut.

```
+---------------------------------------------------------------------------------------------------+
| LINGKUNGAN KLIEN (AIR-GAPPED / HYBRID VPC / RESTRICTED ON-PREMISES)                               |
|                                                                                                   |
|  +------------------------+      +------------------------+      +-----------------------------+  |
|  | Pod / Node Workload A  |      | Pod / Node Workload B  |      | Host Kernel                 |  |
|  |  +------------------+  |      |  +------------------+  |      |  +------------------------+ |  |
|  |  | App (Go/Java)    |  |      |  | App (C++/Node.js)|  |      |  | eBPF (BCC/Cilium)      | |  |
|  |  +--------+---------+  |      |  +--------+---------+  |      |  +-----------+------------+ |  |
|  |           | OTLP/gRPC  |      |           | stdout/json|      |              | Raw RingBuf  |  |
|  |           v            |      |           v            |      |              v              |  |
|  |  +------------------+  |      |  +------------------+  |      |  +------------------------+ |  |
|  |  | Vector (Sidecar) |  |      |  | Vector (DaemonSet)  |      |  | Custom Kernel Exporter | |  |
|  +-----------+------------+      +-----------+------------+      +--------------+--------------+  |
|              |                               |                                  |                 |
|              +-----------------------+-------+----------------------------------+                 |
|                                      | TCP (Zero-Loss Pipeline)                                    |
|                                      v                                                            |
|  +---------------------------------------------------------------------------------------------+  |
|  | FDE Observability Gateway (StatefulSet OpenTelemetry Collector)                             |  |
|  |                                                                                             |  |
|  |  [ Receiver: OTLP / Kafka / Syslog ]                                                        |  |
|  |          |                                                                                  |  |
|  |          v                                                                                  |  |
|  |  [ Processors Chain ]                                                                        |  |
|  |    1. memory_limiter (Hard kill threshold, ballast dropper)                                  |  |
|  |    2. batch (Flush interval: 200ms, max batch: 8192 items)                                   |  |
|  |    3. transform/redaction (Regex Tokenizer, PII Masking via deterministic SHA256)           |  |
|  |    4. tail_sampling (Keep 100% errors, 100% latency > P99, 1% HTTP 200 OK)                   |  |
|  |          |                                                                                  |  |
|  |          +--------------------------------------+                                           |  |
|  |          | Normal Execution                     | Network Partition / Outage                |  |
|  |          v                                      v                                           |  |
|  |  [ Exporters: ClickHouse / Prometheus ]   [ file_storage (Disk Backpressure Buffer) ]       |  |
|  +-------------------------------------------------+-------------------------------------------+  |
|                                                    | Dynamic replay on link restoration           |
|                                                    v                                              |
|  +---------------------------------------------------------------------------------------------+  |
|  | Local Diagnostic Datastore & Bastion Diagnostic Console (Ephemeral PromQL/LogQL Engine)    |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

#### Komponen Internal Inti Pipeline Observabilitas FDE:

1. **Telemetry Ingestion & Backpressure Management:**
   Ketika aplikasi mengalami lonjakan beban (*traffic spike*) atau *cascading failure*, volume log dan trace akan meledak secara eksponensial. Komponen penerima telemetri harus mengimplementasikan algoritma *drop-tail* berbasis prioritas dan *memory ballast*. Jika alokasi memori mencapai batas atas (misalnya 80%), Collector tidak boleh *Out-Of-Memory* (OOM) Crash; sebaliknya, ia mengaktifkan *file storage extension* (WAL - *Write-Ahead Logging* berbasis NVMe disk) untuk mengalirkan buffer secara sinkron.

2. **Tail-Based Sampling Processor:**
   Pada volume transaksi perbankan 50.000 TPS, merekam seluruh trace transaksi akan menghancurkan I/O disk lokal. FDE mengonfigurasi *tail-based sampling*: seluruh rentang transaksi dipegang di memori selama maksimum 30 detik. Keputusan sampling dibuat di *akhir* siklus hidup transaksi:
   * Jika trace mengandung status HTTP 5xx, gRPC error, atau durasi eksekusi > `P99`, trace **disimpan 100%**.
   * Jika trace berhasil dan normal, trace disampling **1%**.

3. **Deterministic Tokenization & PII Scrubbing:**
   Regulasi seperti GDPR, HIPAA, dan POJK RI melarang pengiriman data NIK, nomor kartu kredit, atau nama nasabah ke sistem log. Komponen transformasi data menjalankan parsing payload secara streaming menggunakan *zero-allocation string manipulation*. Jika ditemukan *pattern matching* data rahasia, Collector menggantinya dengan hash satu arah (*salted HMAC-SHA256*) agar korelasi log antar-layanan tetap dapat diinvestigasi tanpa mengekspos teks asli (*plaintext*).

4. **Low-Overhead Kernel Introspection via eBPF:**
   Saat *incident triage*, aplikasi klien sering kali tidak memiliki instrumentasi SDK (misal: binary C/C++ warisan atau proprietary third-party). FDE menggunakan program eBPF yang di-*attach* ke kprobe/tracepoints (`sys_enter_write`, `tcp_retransmit_skb`, `sched_switch`) untuk mengekstrak metrik latensi I/O, koneksi TCP hung, dan CPU run-queue delay langsung dari ruang kernel tanpa overhead *context switching* berlebih.

---

### 4. Why & What

| Dimensi | Pendekatan SaaS Tradisional (Datadog/NewRelic) | Pendekatan FDE Production Telemetry |
| :--- | :--- | :--- |
| **Model Jaringan** | Asumsi konektivitas internet stabil (*outbound* HTTPS port 443 terbuka ke SaaS endpoint). | Zero-egress, Air-gapped, Proxy berlapis dengan mTLS dan inspeksi paket SNI kaku. |
| **Regulasi Data** | Percaya pada vendor DPA (*Data Processing Agreement*); enkripsi in-transit. | Zero-Trust; Redaksi *in-situ* di memori RAM sebelum data ditulis ke disk lokal atau diteruskan ke gateway. |
| **Resource Overhead** | Agen SaaS sering kali mengonsumsi resource tinggi tanpa batas tegas (CPU spikes saat scanning). | Dibatasi secara mutlak via Linux Cgroups v2 (`cpu.max`, `memory.high`). Overload memicu *sampling cut-off*, bukan crash. |
| **Debugging Method** | Meminta developer menambah log baru, rebuild image, deploy ulang (waktu tunggu: jam/hari). | Non-invasive eBPF injection, continuous memory profiling runtime (waktu mitigasi: hitungan menit). |
| **Data Retention** | Cloud retention 15–30 hari terkelola. | Local tiered storage: ClickHouse NVMe (3 hari), kompresi Zstandard ke S3-compatible lokal (MinIO/Ceph) (30 hari). |

---

### 5. How (Workflow Detail)

Alur kerja mitigasi insiden di lapangan (*Field Incident Triage*) oleh FDE berjalan melalui 5 fase deterministik:

```
[Fase 1: Deteksi & Anomali]
       |
       v
[Fase 2: Aktivasi Ephemeral Flight-Recorder]
       |
       v
[Fase 3: Deep Kernel Triage via eBPF]
       |
       v
[Fase 4: Sanitasi Telemetri & Redaksi]
       |
       v
[Fase 5: Ekstraksi Support Bundle & Post-Mortem Remediasi]
```

#### Fase 1: Deteksi & Identifikasi Masalah
* Signal anomali diterima melalui metrik RED (*Rate, Errors, Duration*) atau USE (*Utilization, Saturation, Errors*).
* FDE mengonfirmasi apakah degradasi terjadi pada layer aplikasi, container networking (CNI), atau kernel host (I/O saturation, conntrack table exhaustion).

#### Fase 2: Aktivasi Ephemeral Flight-Recorder
* FDE memicu konfigurasi dinamis pada OpenTelemetry Collector / Vector via ConfigMap tanpa me-restart pod aplikasi.
* Sampling rate untuk path terdampak dinaikkan ke 100%, dan level log aplikasi ditransformasi dari `INFO` ke `DEBUG` menggunakan runtime actuator endpoints (misal: Spring Boot Actuator, Go net/http/pprof).

#### Fase 3: Deep Kernel Triage via eBPF
* Jika log aplikasi tidak menunjukkan akar masalah (*silent hang*), FDE meluncurkan pod diagnostik *privileged* (menggunakan image distroless yang membawa tool BCC/bpftrace) ke node terdampak.
* Menjalankan kueri tracing kernel untuk melacak:
  1. *Off-CPU latency*: Mengidentifikasi thread yang terjebak pada I/O disk lock atau thread contention mutex.
  2. *Socket drops*: Menginspeksi antrean `ListenBacklog` dan `tcp_drop`.

#### Fase 4: Sanitasi Telemetri & Redaksi
* Telemetri mentah yang dikumpulkan dari tracing dialirkan melewati *PII-Masking pipeline*.
* Validasi ganda diterapkan untuk memastikan tidak ada token otentikasi JWT, password database, atau NIK nasabah yang tersimpan pada artefak debug.

#### Fase 5: Ekstraksi Support Bundle
* Skrip diagnostik mengompilasi snapshot ringkas sistem: metrik host, 500 trace terakhir dari kegagalan sistem, output eBPF flamegraphs, dan log terenkripsi.
* Berkas ZIP terenkripsi (AES-256-GCM) dibuat dan ditandatangani secara digital dengan kunci GPG FDE untuk diserahkan ke tim core engineering jika diperlukan patch kode darurat.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Tim Medis Tempur (Flight Medic) vs Laboratorium Rumah Sakit Pusat

Pendekatan observabilitas SaaS biasa bagaikan mengirim seluruh sampel darah dan rekam medis pasien ke laboratorium pusat di kota lain: akurat dan lengkap, namun membutuhkan waktu, bandwidth jalan bebas hambatan, serta tidak aman bagi pasien militer rahasia.

FDE beroperasi sebagai **Tim Medis Tempur (Flight Medic)** di medan perang:
* Membawa peralatan portabel (*lightweight collectors*).
* Mengambil sampel penting saja (*sampling P99/errors*).
* Melakukan tindakan hemostasis/pembersihan data di tempat (*PII masking/redaction*).
* Menggunakan USG portabel langsung pada jaringan tubuh tanpa membedah total (*non-invasive eBPF kernel inspection*).
* Jika persediaan habis, peralatan beralih ke mode manual darurat (*disk-backed backpressure queue*).

#### Diagram Transisi Keadaan (State Machine) Backpressure Telemetry

```
       Volume Normal
  +----------------------+
  |     STATE: GREEN     | <------------------------------------+
  | Ingestion: Direct    |                                      |
  | Queue: In-Memory     |                                      |
  +----------+-----------+                                      |
             |                                                  |
             | Memory usage > 70%                               |
             v                                                  |
  +----------------------+                                      |
  |    STATE: YELLOW     |                                      |
  | Action: Drop 200 OK  |                                      |
  | Retain: Errors/P99   |                                      | Memory usage < 50%
  | Queue: RAM + NVMe    |                                      | Disk Queue Empty
  +----------+-----------+                                      |
             |                                                  |
             | Memory usage > 85% OR NVMe Write > 80%           |
             v                                                  |
  +----------------------+                                      |
  |      STATE: RED      |                                      |
  | Action: Drop 99% Traces                                     |
  | Metric Aggregation   |                                      |
  | Strict Head Sampling |                                      |
  +----------+-----------+                                      |
             |                                                  |
             | Circuit Breaker Open (Downstream Down)           |
             v                                                  |
  +-------------------------------------+                       |
  |          STATE: BLACK-BOX           |                       |
  | Local RingBuffer Disk Flush Only   |-----------------------+
  | No Network Egress Attempted        |
  +-------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Basic Vector Pipeline untuk PII Masking
Konfigurasi Vector minimalis (`vector.toml`) untuk menangkap log aplikasi, mendeteksi NIK (16 digit angka), dan mengubahnya menjadi format mask sebelum diteruskan.

```toml
[sources.app_logs]
type = "file"
include = ["/var/log/containers/*.log"]
read_from = "beginning"

[transforms.mask_pii]
type = "remap"
inputs = ["app_logs"]
source = '''
# Deteksi 16 digit angka berurutan (contoh NIK / No KTP)
.message = replace_patterns(string!(.message), [
  r'\b[0-9]{16}\b', "[REDACTED-NIK]"
])
'''

[sinks.local_file]
type = "file"
inputs = ["mask_pii"]
path = "/var/log/sanitized-app.log"
encoding.codec = "ndjson"
```

#### B. Practical Example: Enterprise OpenTelemetry Collector Production Architecture

Di bawah ini adalah konfigurasi enterprise-grade OpenTelemetry Collector (`otel-collector-config.yaml`) yang dirancang untuk instalasi lapangan FDE. Konfigurasi ini menyertakan:
1. `memory_limiter` untuk proteksi OOM.
2. `file_storage` extension untuk persistensi buffer disk saat jaringan lokal klien mengalami partisi.
3. Transformasi redaksi atribut sensitif via OTTL (*OpenTelemetry Transformation Language*).
4. `tail_sampling` multi-strategi.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: fde-observability
data:
  otel-collector-config.yaml: |
    extensions:
      health_check:
        endpoint: 0.0.0.0:13133
      file_storage/traces:
        directory: /var/lib/otelcol/traces
        timeout: 10s
        compaction:
          on_rebound: true
          directory: /var/lib/otelcol/traces_compact
          rebound_trigger_percentage: 80
      zpages:
        endpoint: 0.0.0.0:55679

    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
            max_concurrent_streams: 1024
          http:
            endpoint: 0.0.0.0:4318

    processors:
      memory_limiter:
        check_interval: 200ms
        limit_percentage: 75
        spike_limit_percentage: 20

      transform/mask_sensitive:
        error_mode: ignore
        trace_statements:
          - context: span
            statements:
              # Redaksi token authorization pada attribute
              - replace_pattern(attributes["http.request.header.authorization"], "^Bearer .*", "Bearer [REDACTED]")
              - replace_pattern(attributes["db.statement"], "([0-9]{4}-?){3}[0-9]{4}", "[REDACTED_CC]")
              - set(attributes["fde.sanitized"], "true")
        log_statements:
          - context: log
            statements:
              - replace_pattern(body, "(?i)password=[^&\\s]+", "password=[REDACTED]")
              - replace_pattern(body, "\\b[1-9][0-9]{15}\\b", "[MASKED_IDENTIFIER]")

      tail_sampling:
        decision_wait: 10s
        num_traces: 50000
        expected_new_traces_per_sec: 2000
        policies:
          # Kebijakan 1: Tangkap 100% trace error
          - name: drop_errors_filter
            type: status_code
            status_code: { statuses: [ ERROR ] }
          # Kebijakan 2: Tangkap trace dengan latensi tinggi (P99 SLA violation > 1.5 detik)
          - name: latency_filter
            type: numeric_attribute
            numeric_attribute: { key: "http.status_code", value_condition: { greater_than_or_equal: 500 } }
          - name: latency_duration
            type: latency
            latency: { threshold_ms: 1500000 } # 1500ms
          # Kebijakan 3: Sample 2% dari transaksi yang sukses (200 OK)
          - name: probabilistic_success
            type: probabilistic
            probabilistic: { sampling_percentage: 2.0 }

      batch:
        send_batch_size: 4096
        timeout: 500ms
        send_batch_max_size: 8192

    exporters:
      otlp/local_clickhouse:
        endpoint: "clickhouse-otlp.internal-fde.svc.cluster.local:4317"
        tls:
          insecure: true
        sending_queue:
          enabled: true
          num_consumers: 8
          queue_size: 10000
          storage: file_storage/traces
        retry_on_failure:
          enabled: true
          initial_interval: 1s
          max_interval: 30s
          max_elapsed_time: 5m

    service:
      extensions: [health_check, file_storage/traces, zpages]
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, transform/mask_sensitive, tail_sampling, batch]
          exporters: [otlp/local_clickhouse]
        logs:
          receivers: [otlp]
          processors: [memory_limiter, transform/mask_sensitive, batch]
          exporters: [otlp/local_clickhouse]
      telemetry:
        logs:
          level: "warn"
        metrics:
          address: "0.0.0.0:8888"
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: "The Phantom 60-Second Freeze" pada Bank Digital Nasional

* **Latar Belakang Lingkungan:**
  Sebuah bank digital nasional menerapkan *core transactional engine* berbasis microservices di cluster OpenShift *on-premises* (Air-gapped, tidak ada koneksi keluar, MTU jaringan diatur kaku pada 1420 bytes karena tunneling VXLAN overlay).

* **Gejala Insiden:**
  Setiap hari pada pukul 09:00 - 10:30 WIB (lonjakan transaksi kliring massal), 4.2% transaksi transfer dana mengalami *connection timeout* tepat pada detik ke-60. Log aplikasi Java Spring Boot sama sekali tidak menampilkan error stack trace; koneksi terputus begitu saja (*silent dropping*). Tim operasional bank menyalahkan binary vendor FDE atas tuduhan *application deadlock*.

* **Metodologi Triage FDE di Lapangan:**
  1. **Deployment Observabilitas Ephemeral:** FDE tidak dapat menginstal agent SaaS. FDE menyuntikkan Vector DaemonSet lokal dengan konfigurasi ring-buffer NVMe dan meluncurkan *ad-hoc eBPF tracer* via privileged pod.
  2. **Investigasi Kernel eBPF:**
     FDE menjalankan script eBPF `tcpretrans` dan `tcpdrop`:
     ```bash
     /usr/share/bcc/tools/tcpdrop
     ```
     Hasil output eBPF di console Bastion:
     ```text
     TIME     PID     COMM       LADDR:LPORT           RADDR:RPORT          STATE       REASON
     09:14:02 184920  java       10.244.3.45:48392     10.244.8.12:8080     ESTABLISHED TCP_TOO_MANY_ORPHANS
     09:14:02 0       swapper/4  10.244.3.45:48392     10.244.8.12:8080     ESTABLISHED TCP_ZERO_WINDOW_DROP
     ```
  3. **Akar Masalah (Root Cause Discovery):**
     * Terdeteksi `TCP_ZERO_WINDOW_DROP`. Buffer TCP penerima pada database gateway downstream penuh (`rmem` exhaustion).
     * Aplikasi klien tidak mengalami *deadlock*, melainkan *blocked write* pada system call `sendto()` yang membeku karena driver downstream mengumumkan TCP Receive Window = 0.
     * Mengapa tepat 60 detik? Konfigurasi Linux default `tcp_retries2 = 15` pada kernel bank klien berbenturan dengan nilai firewall gateway idle-timeout yang di-set pada 60 detik. Firewall memutuskan *state table* secara sepihak tanpa mengirim TCP RST flag (*silent drop*).

* **Remediasi & Dampak:**
  * **Solusi Jangka Pendek:** Mengubah nilai socket option aplikasi secara dinamis via JVM instrumentation: mengaktifkan `TCP_USER_TIMEOUT` sebesar 5000 ms agar kegagalan terdeteksi dalam 5 detik, bukan 60 detik, memicu fallback circuit breaker Resilience4j.
  * **Solusi Jangka Panjang:** Mengubah tuning sysctl Linux node:
    ```bash
    sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
    sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
    ```
  * **Hasil:** Angka kegagalan transfer kembali ke 0.000%, SLA 99.99% tercapai, dan vendor FDE terbukti bersih dari tuduhan cacat perangkat lunak berkat bukti deterministik kernel-level trace.

---

### 9. Trade-offs

Setiap keputusan perancangan sistem telemetri lapangan melibatkan kompromi teknis ketat yang harus dipertimbangkan FDE:

| Parameter | Tail-Based Sampling (OTel) | Head-Based Sampling (SDK Level) | Dampak Teknis di Lapangan |
| :--- | :--- | :--- | :--- |
| **Konsumsi Memori** | **Tinggi** (Perlu menyimpan traces di RAM selama jendela waktu `decision_wait`). | **Sangat Rendah** (Keputusan dibuat di awal; trace langsung didrop). | Pada node dengan RAM ketat (< 8GB), tail-sampling dapat memicu OOM jika *memory_limiter* tidak diproteksi hard limit. |
| **Akurasi Insiden** | **100% Akurat** (Semua error dan latensi tinggi pasti terekam). | **Probabilistik** (P99 outlier atau silent error berisiko besar terlewat dari observasi). | FDE wajib memilih tail-sampling untuk sistem finansial/misi kritis, meskipun harus membayar biaya memori. |

| Parameter | eBPF Kernel Tracing | SDK App Instrumentation | Dampak Teknis di Lapangan |
| :--- | :--- | :--- | :--- |
| **Overhead CPU** | **< 1.5% CPU**, zero context-switching ke user-space jika filtering di in-kernel VM. | **3% - 8% CPU**, overhead garbage collection (GC pause) meningkat akibat trace object creation. | eBPF unggul saat aplikasi klien tidak boleh di-rebuild/restart. Namun eBPF sulit merekonstruksi payload logika bisnis domain murni. |
| **Akses Hak Istimewa**| Butuh `CAP_SYS_ADMIN` / `CAP_BPF` atau container *privileged: true*. | Berjalan penuh di *unprivileged user-space*. | Bank tertentu melarang *privileged container*. FDE harus mengisolasi eBPF node tracer hanya pada ephemeral debugging pods. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengabaikan TCP Out-of-Order Packet Buffer pada Vector/Collector
* **Gejala:** Memory leak lambat pada pod Collector di lingkungan traffic padat.
* **Penyebab:** collector mengeksekusi reassembly buffer tanpa *expiration timeout* saat menerima paket OTLP/HTTP yang terfragmentasi.
* **Solusi:**
  Set batas `client_timeout` dan alokasikan `max_concurrent_streams` kaku pada receiver gRPC. Pastikan MTU sepanjang rute CNI terkonfigurasi konsisten (misal: 1420 jika menggunakan Geneve/VxLAN, atau 1500 pada baremetal VLAN).

#### 2. Kebocoran PII via Trace Span Event Name
* **Gejala:** Tim audit klien menemukan nomor identitas nasabah di console Elastic/ClickHouse meskipun regex masking sudah berjalan.
* **Penyebab:** Processor hanya me-redact `attributes["http.request.body"]`, tetapi developer aplikasi menaruh parameter dinamis di dalam Span Event Name:
  ```go
  // KODE APLIKASI KLIEN YANG SALAH
  span.AddEvent(fmt.Sprintf("User %s failed payment", userIdNumber))
  ```
* **Solusi:** Gunakan OTTL transform komprehensif pada level span events:
  ```yaml
  transform/mask_event:
    error_mode: ignore
    trace_statements:
      - context: span_event
        statements:
          - replace_pattern(name, "\\b[0-9]{16}\\b", "[REDACTED]")
  ```

#### 3. Disk Queue Starvation (Thrashing)
* **Gejala:** I/O Wait host melesat hingga > 40%, throughput sistem drop drastis ketika disk-queue OTel aktif.
* **Penyebab:** File storage diletakkan di partisi root OS yang berbagi IOPS dengan root file system Kubernetes dan Docker runtime.
* **Solusi:** Mount Dedicated Volume (NVMe/SSD) khusus untuk directory `/var/lib/otelcol/traces` dengan filesystem `ext4` (opsi mount: `noatime,nodiratime,data=writeback`).

---

### 11. Best Practices (Production Checklist)

Gunakan checklist operasional ini sebelum menyatakan pipeline observabilitas siap produksi di sisi klien:

- [ ] **Alokasi Resource Limit Ketat:** DaemonSet Vector / OTel Collector memiliki batas CPU/Memory eksplisit di spec Kubernetes (`resources.limits.memory` = 1.5x `resources.requests.memory`).
- [ ] **Aktivasi Memory Ballast / Memory Limiter:** Konfigurasikan `memory_limiter` OTel Collector dengan threshold maksimum 75% limit pod untuk mencegah *hard OOMKilled* dari Linux kernel.
- [ ] **Verifikasi Zero Egress:** Verifikasi menggunakan `tcpdump` bahwa tidak ada paket telemetry yang mencoba keluar ke internet public IP (pastikan sink IP hanya mengarah ke subnet FDE internal).
- [ ] **Enkripsi Buffer At Rest:** Path penyimpanan antrean file (`file_storage`) wajib dienkripsi menggunakan LUKS pada storage level atau volume mount yang dilindungi enterprise KMS klien.
- [ ] **Deterministic Scrubbing Validation:** Jalankan unit test bermuatan 1.000 kombinasi data sintetis sensitif (Credit Card Luhn format, NIK, Password) melewati Collector dan pastikan tingkat keberhasilan redaksi adalah **100.0%**.
- [ ] **Self-Telemetry Loop Isolation:** Metrik internal collector (`service.telemetry.metrics`) **tidak boleh** diarahkan kembali ke receiver collector itu sendiri secara rekursif (*infinite ingestion loop protection*).

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Skenario Laboratorium
Membangun pipeline mini-FDE yang menerima traffic gRPC OTLP dari aplikasi microservice, melakukan redaksi string sensitif secara streaming, menerapkan disk queueing darurat saat backend mati, dan memverifikasi integritas trace.

#### Langkah 1: Persiapan Direktori & File Konfigurasi
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/storage
cd hands-on/m02
chmod 777 storage
```

Buat file `docker-compose.yaml`:
```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.95.0
    container_name: fde-otel-gateway
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-config.yaml:/etc/otel-collector-config.yaml
      - ./storage:/var/lib/otelcol
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "8888:8888"   # Collector self metrics
      - "13133:13133" # Health check
    environment:
      - GOMEMLIMIT=350MiB
    deploy:
      resources:
        limits:
          memory: 512M

  mock-backend:
    image: alpine:latest
    container_name: fde-mock-backend
    command: ["nc", "-lk", "-p", "9999"]
    ports:
      - "9999:9999"
```

#### Langkah 2: Buat File Konfigurasi Collector (`otel-config.yaml`)
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  memory_limiter:
    check_interval: 100ms
    limit_percentage: 80
    spike_limit_percentage: 20

  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - replace_pattern(attributes["customer.account_number"], "^[0-9]+$", "ACCT-MASKED-XXXX")

  batch:
    send_batch_size: 10
    timeout: 1s

exporters:
  file:
    path: /var/lib/otelcol/output.json
  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, transform, batch]
      exporters: [file, logging]
```

#### Langkah 3: Eksekusi Generator Trace & Verifikasi
1. Jalankan cluster observabilitas:
   ```bash
   docker compose up -d
   ```
2. Buat script pengirim trace sederhana `send_trace.py` menggunakan Python OpenTelemetry SDK:
   ```python
   # send_trace.py
   import time
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import BatchSpanProcessor
   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
   from opentelemetry.sdk.resources import Resource

   resource = Resource(attributes={"service.name": "payment-gateway"})
   provider = TracerProvider(resource=resource)
   processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317", insecure=True))
   provider.add_span_processor(processor)
   trace.set_tracer_provider(provider)

   tracer = trace.get_tracer("fde-tracer")

   print("[*] Mengirimkan traces dengan data sensitif...")
   with tracer.start_as_current_span("ProcessTransaction") as span:
       span.set_attribute("customer.account_number", "5432109876543210")
       span.set_attribute("transaction.amount", 7500000)
       time.sleep(0.1)

   provider.shutdown()
   print("[+] Trace terkirim!")
   ```
3. Eksekusi script pengirim data:
   ```bash
   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
   python send_trace.py
   ```
4. Verifikasi hasil redaksi pada storage:
   ```bash
   cat storage/output.json | grep ACCT-MASKED-XXXX
   ```
   *Output yang diharapkan: String `5432109876543210` hilang, berubah menjadi `ACCT-MASKED-XXXX`.*

---

### 13. Exercise

#### Level Easy
Ubah konfigurasi file `otel-config.yaml` pada hands-on di atas untuk menambahkan redaksi pada span attribute `http.client_ip`. Setiap IP address versi 4 yang masuk harus dimasking octet terakhirnya (contoh: `192.168.1.104` menjadi `192.168.1.0/24`).

#### Level Medium
Konfigurasikan sistem *Tail-Based Sampling* pada OpenTelemetry Collector yang memenuhi aturan berikut:
1. Jika trace memuat attribute `http.target = "/healthz"`, drop trace tersebut 100%.
2. Jika durasi span > 500ms, simpan 100%.
3. Untuk seluruh traffic lainnya, lakukan sampling sebesar 5%.
*Uji konfigurasi menggunakan simulasi curl/script dan buktikan trace `/healthz` tidak tertulis di output storage.*

#### Level Hard
Tulis sebuah script bpftrace (eBPF) satu baris (*one-liner*) atau file program `.bt` untuk mendeteksi system call `connect()` yang membutuhkan waktu lebih dari 100ms untuk menyelesaikan handshake TCP pada interface pod tertentu, dan cetak process name (`comm`), Process ID (`pid`), target destination IP, serta latensi dalam satuan mikrodetik.

---

### 14. Challenge

**Skenario Tantangan:**
Sebuah instansi militer menggunakan sistem analitik Anda secara on-premise tanpa akses remote SSH langsung. Terjadi insiden di mana CPU node utama melonjak menjadi 100% tepat setiap pergantian jam (menit ke-00), menyebabkan antrean pesan tertahan selama 8 menit sebelum pulih secara misterius. Namun, tim keamanan klien menolak memberikan akses root dan menolak penginstalan software debug tambahan yang memerlukan kompilasi kernel di server target.

**Tugas Anda:**
1. Rancang sebuah *Stand-Alone Diagnostic Toolkit Container* yang bersifat non-intrusif dan membawa binary eBPF yang sudah terkompilasi secara CO-RE (*Compile Once - Run Everywhere* via BTF `/sys/kernel/btf/vmlinux`).
2. Buat skrip triage otomatis yang hanya membaca metrics & ring buffer kernel saat utilisasi CPU > 85%, mengambil ringkasan stack traces (On-CPU FlameGraph snapshot) selama 30 detik tanpa menyimpan data payload pengguna.
3. Rancang struktur data *air-gapped black-box archive* (output bundle zip terenkripsi) yang aman secara kriptografis untuk diserahkan klien kepada Anda melalui flash drive tanpa melanggar batasan undang-undang kerahasiaan negara.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konsep)
1. Apa fungsi utama ekstensi `memory_limiter` pada OpenTelemetry Collector?
   * A. Mempercepat eksekusi database queries.
   * B. Mengatur alokasi heap JVM pada pod klien.
   * C. Mencegah collector mati akibat OOMKilled dengan menjatuhkan data saat memori melampaui limit.
   * D. Melakukan kompresi otomatis pada payload log.
2. Manakah sinyal telemetri yang membutuhkan overhead resource paling besar jika ditransmisikan dalam volume 100% tanpa sampling?
   * A. Counters Metrics.
   * B. Gauge Metrics.
   * C. Distributed Tracing Spans.
   * D. Health check heartbeats.
3. Mengapa *head-based sampling* kurang ideal untuk mendeteksi *intermittent production bugs* dibandingkan *tail-based sampling*?
   * A. Karena head-based sampling membutuhkan memory jauh lebih besar.
   * B. Karena keputusan sampling pada head-based dibuat sebelum status trace (sukses/gagal) diketahui.
   * C. Karena head-based sampling tidak didukung oleh OpenTelemetry SDK.
   * D. Karena head-based sampling hanya bisa dijalankan pada node Docker.
4. Apa yang dimaksud dengan sifat non-intrusif dari observabilitas berbasis eBPF?
   * A. eBPF tidak membutuhkan alokasi memori sama sekali.
   * B. eBPF dapat mengamati kernel events dan user space execution tanpa mengubah binary atau merestart proses aplikasi.
   * C. eBPF menghapus kebutuhan firewall pada server.
   * D. eBPF hanya bekerja saat aplikasi dalam kondisi offline.
5. Pada format sampling OpenTelemetry OTTL, konteks apa yang digunakan untuk memodifikasi log attributes?
   * A. `context: span`
   * B. `context: metric`
   * C. `context: log`
   * D. `context: datapoint`

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. Jelaskan risiko dari konfigurasi `file_storage` extension OTel jika parameter `compaction` tidak diaktifkan pada disk bervolume kecil!
7. Dalam kondisi jaringan split-brain antara cluster klien dan bastion observabilitas FDE, strategi apa yang harus diterapkan pada Vector/Collector sender queue untuk mencegah *data clobbering*?
8. Mengapa teknik regex replacement tradisional di user-space dapat menyebabkan *latency spike* pada pipeline penanganan log dengan throughput 100.000 EPS?
9. Apa perbedaan esensial dari tracing metrik RED (*Rate, Errors, Duration*) dibanding USE (*Utilization, Saturation, Errors*) dalam pembagian tugas triage infrastruktur vs aplikasi?
10. Bagaimana mekanisme kerja *trace context propagation* (seperti W3C TraceContext headers `traceparent`) ketika melintasi service mesh Envoy di infrastruktur perbankan yang menerapkan mTLS?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1:** Setelah melakukan update ConfigMap pada OpenTelemetry Collector DaemonSet untuk me-redact NIK nasabah, utilisasi CPU Collector naik dari 5% ke 98%, memicu *pod evictions*. Analisis apa penyebab performa anjlok tersebut dan bagaimana cara memulihkannya!
12. **Skenario 2:** Aplikasi Go pada node bare-metal klien mengalami *hang* tanpa indikasi error di log standar. Pod collector lokal tidak menangkap peningkatan trace error. Tool kernel apa yang Anda deploy pertama kali untuk memvalidasi apakah issue berada pada Linux Futex Lock contention atau Disk I/O deadlock?
13. **Skenario 3:** Tim cyber security klien memutus akses network egress collector Anda karena mendeteksi transmisi port gRPC 4317 dianggap sebagai eksfiltrasi data. Desain arsitektur telemetri alternatif yang memungkinkan observabilitas lokal tetap berjalan mandiri tanpa memancarkan traffic keluar pod/node!

---

### Jawaban Kuis Evaluasi Pemahaman

#### Bagian 1: Basic
1. **C.** Mencegah collector mati akibat OOMKilled dengan menjatuhkan data saat memori melampaui limit.
2. **C.** Distributed Tracing Spans (karena payload trace membawa metadata context, spans, string attributes, dan stack trace yang sangat membebani I/O).
3. **B.** Karena keputusan sampling pada head-based dibuat sebelum status trace (sukses/gagal) diketahui.
4. **B.** eBPF dapat mengamati kernel events dan user space execution tanpa mengubah binary atau merestart proses aplikasi.
5. **C.** `context: log`

#### Bagian 2: Intermediate
6. **Risiko Disk Invalidation:** Tanpa pemadatan (*compaction*), slot fragmentasi file storage yang telah terisi dan terkirim tidak direklamasi oleh sistem operasi. Ruang disk NVMe akan terisi penuh (*disk space exhaustion*), yang pada akhirnya membekukan pod Collector dan memblokir thread logging aplikasi upstream.
7. **Strategi Buffer Backpressure:** Mengubah sending queue menjadi mode sinkron berbasis *disk-backed persistent storage*, membatasi masa retensi file (TTL), dan mengaktifkan circuit breaker status: jika link downstream down, collector berhenti mencoba kirim secara agresif (*exponential backoff with jitter*) untuk menghindari network storm saat link pulih.
8. **CPU Catastrophic Backtracking:** Penggunaan regex non-deterministik pada throughput 100k EPS menyebabkan *catastrophic backtracking*, thread CPU tersaturasi 100%, GC memory allocation meledak akibat instansiasi string heap, dan latensi pipeline melonjak ribuan milidetik.
9. **RED vs USE:** RED berfokus pada pengalaman permintaan layanan (*request-scoped* internal/aplikasi: Rate, Error, Duration), sedangkan USE berfokus pada kapasitas dan batasan fisik mesin/infrastruktur (*resource-scoped*: Utilization, Saturation, Errors).
10. **Context Propagation:** Header `traceparent` diekstraksi oleh proxy ingress Envoy dari request HTTP incoming, disalin ke span context internal Envoy, diteruskan ke HTTP request internal menuju service pod, dan disuntikkan kembali ke span egress oleh library instrumentasi tanpa merusak enkripsi mutual-TLS transport.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis CPU Spike:** Pola regex redaksi yang ditambahkan kemungkinan mengandung sub-pola greedy tanpa batasan boundary yang menyebabkan *catastrophic backtracking* di parsing engine OTel OTTL. Solusi: Gunakan operator pembanding terkompilasi, batasi regex menggunakan string length conditions (`where Length(body) < 2000`), gunakan *Aho-Corasick* string matcher, atau alihkan redaksi ke Vector native VRL (*Vector Remap Language*) yang dikompilasi secara native ke machine code.
12. **Investigasi Lock Contention:** Gunakan `offcputime-bpfcc` atau `syscount-bpfcc`. Jika `offcputime` menunjukkan waktu dominan pada kernel symbols `futex_wait_queue_me`, maka aplikasi mengalami deadlock/thread lock contention di user-space. Jika waktu dominan berada di `io_schedule`, aplikasi tersendat menunggu blocking disk flush.
13. **Solusi Zero-Egress Local Telemetry:** Terapkan arsitektur *Local-Loop Observability*: Collector diarahkan ke instans database columnar lokal (misalnya ClickHouse single-node) yang berada di namespace Kubernetes yang sama. UI lokal ephemeral (seperti Grafana lokal via port-forward bastion FDE) membaca langsung dari ClickHouse via localhost. Tidak ada paket byte telemetri yang melintasi perimeter interface jaringan klien.

---

### 16. Summary

Mengoperasikan sistem telemetri skala enterprise dalam kapasitas Forward Deployed Engineer menuntut keseimbangan presisi antara:
1. **Ketahanan Sistem (*Resilience*):** Mengasumsikan jaringan lapangan selalu rentan putus, storage terbatas, dan alokasi resource komputasi adalah pinjaman yang harus dijaga ketat agar tidak memicu insiden baru.
2. **Kepatuhan Privasi Data (*Zero-Trust Sanitization*):** Memastikan redaksi data terjadi secara atomik di lapisan pipeline terdepan menggunakan streaming masking sebelum persistensi disk atau transfer jaringan.
3. **Visibilitas Tingkat Rendah (*Low-level Introspection*):** Penguasaan instrumen modern seperti eBPF untuk melompati *logging wall* aplikasi klien dan menemukan akar masalah langsung pada ruang operasi kernel Linux secara cepat, deterministik, dan presisi.