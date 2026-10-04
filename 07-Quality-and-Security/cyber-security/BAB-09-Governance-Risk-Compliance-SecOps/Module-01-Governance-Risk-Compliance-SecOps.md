# Modul 09.01: Governance, Risk, Compliance & SecOps

---

### 1. Identitas Modul
* **Track:** Cyber Security
* **Kategori:** 07-Quality-and-Security
* **Bab:** 09 - Governance, Risk, Compliance & SecOps
* **Tingkat Kesulitan:** Advanced / Enterprise Architecture
* **Prasyarat:** Pemahaman mendalam tentang TCP/IP, Linux/Windows Internals, Logging Architecture (Syslog, Windows Event Forwarding), Kriptografi Terapan, serta Metodologi Analisis Ancaman (MITRE ATT&CK).
* **Estimasi Waktu:** 180 Menit

---

### 2. Learning Objectives (LO-01 s/d LO-08)
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
* **LO-01:** Merancang arsitektur Enterprise Security Operations Center (SOC) multi-tier yang terintegrasi dengan kapabilitas telemetri modern.
* **LO-02:** Mengoptimalkan ingestion pipeline dan storage tiering pada platform SIEM terdistribusi (Elasticsearch dan Splunk) untuk efisiensi kueri dan reduksi EPS (*Events Per Second*).
* **LO-03:** Mengonstruksi Telemetry Processing Pipelines berlatensi rendah untuk normalisasi data, penyaringan noise, masking data privat, dan routing multi-tujuan.
* **LO-04:** Mengoperasikan dan mengkorelasikan taksonomi kontrol keamanan NIST CSF 2.0 (termasuk fungsi *Govern*), ISO/IEC 27001:2022, dan PCI-DSS v4.0 ke dalam deteksi operasional.
* **LO-05:** Merancang parameter teknis Business Continuity & Disaster Recovery (BC/DR) berbasis RTO, RPO, dan MTD untuk infrastruktur SecOps dan SIEM yang tahan terhadap kegagalan multi-region.
* **LO-06:** Mengidentifikasi attack surface pada rantai pasok telemetri dan memitigasi log injection, parser poisoning, serta credential abuse pada orkestrasi SOAR.
* **LO-07:** Menulis aturan deteksi perilaku (*behavioral detection rules*) berbasis Sigma dan SPL/EQL yang dioptimalkan terhadap performa indeks SIEM.
* **LO-08:** Menguji dan memvalidasi resiliensi arsitektur SecOps terhadap kegagalan jaringan transmisi log berkapasitas tinggi melalui simulasi *backpressure*.

---

### 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                  ENTERPRISE TELEMETRY SOURCES                                     |
|  [Endpoints: EDR/Sysmon]    [Cloud: CloudTrail/K8s Audit]    [Network: Zeek/Suricata/Firewalls]   |
+---------------------------------------------------------------------------------------------------+
                                              │ (TLS 1.3 / mTLS)
                                              ▼
+---------------------------------------------------------------------------------------------------+
|                                TELEMETRY PROCESSING PIPELINE                                      |
|  +---------------------+    +---------------------------+    +---------------------------------+  |
|  | Ingestion Edge      | -> | Stream Processing Engine  | -> | Normalization & Masking Engine  |  |
|  | (Vector / Fluentbit)|    | (Buffer, Deduplication)   |    | (PCI-DSS PAN, PII Redaction)    |  |
|  +---------------------+    +---------------------------+    +---------------------------------+  |
+---------------------------------------------------------------------------------------------------+
             │ (Raw Cold Tier)                           │ (Enriched / Normalized Stream)
             ▼                                           ▼
+--------------------------+    +-------------------------------------------------------------------+
| IMMUTABLE STORAGE (WORM) |    |                   DISTRIBUTED SIEM PLATFORM                       |
| [S3 Glacier / Object Lock|    |  +-----------------------------+ +-----------------------------+  |
|  BC/DR & Audit Retention]|    |  | Hot Tier (Elastic Search)   | | Warm/Cold Tier (Searchable) |  |
+--------------------------+    |  +-----------------------------+ +-----------------------------+  |
                                |  | Correlation Engine (Sigma / EQL / SPL Detection Rules)      |  |
                                +-------------------------------------------------------------------+
                                                                 │
                                                                 ▼
+---------------------------------------------------------------------------------------------------+
|                                SECURITY OPERATIONS CENTER (SOC)                                   |
|  +-----------------------------------+               +-----------------------------------------+  |
|  | Tier 1 / Triage Automation (SOAR) | <-----------> | Tier 2/3 / Threat Hunting & DFIR        |  |
|  +-----------------------------------+               +-----------------------------------------+  |
|                  │                                                         │                      |
|                  ▼                                                         ▼                      |
|  +---------------------------------------------------------------------------------------------+  |
|  | GRC FRAMEWORK ENGINE (NIST CSF 2.0 / ISO 27001:2022 / PCI-DSS v4.0 Continuous Compliance)   |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

### 4. Mengapa Ini Penting (Why & Business / Security Impact)
SecOps dan GRC sering kali beroperasi secara terisolasi. SecOps berfokus pada kecepatan deteksi teknis (*Mean Time to Detect* / MTTD dan *Mean Time to Respond* / MTTR), sementara GRC berfokus pada pemenuhan kontrol regulasi serta mitigasi risiko bisnis. Ketiadaan integrasi struktural menimbulkan celah: log keamanan tidak memenuhi rantai pembuktian hukum (*chain of custody*), audit berkala gagal mendeteksi ancaman dinamis, dan biaya lisensi SIEM membengkak akibat konsumsi log mentah bernilai analitik rendah.

Biaya komputasi log enterprise yang mencapai skala terabyte per hari dapat menekan efisiensi finansial organisasi. Jika telemetri tidak disaring dan diproses pada lapisan *pipeline*, 40–60% kapasitas SIEM terbuang untuk menyimpan *heartbeat* sistem atau data redundan. Dari sudut pandang kepatuhan, kegagalan menerapkan perlindungan data pemegang kartu sesuai PCI-DSS v4.0 atau pelanggaran terhadap mandat ketahanan operasional digital dapat mengakibatkan denda regulasi yang berat, pembatalan izin proses transaksi finansial, serta degradasi reputasi enterprise yang kritis.

---

### 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

#### Enterprise SOC Architecture
Arsitektur SOC modern adalah integrasi terkoordinasi antara manusia, proses, dan teknologi yang bertugas memantau, mendeteksi, menganalisis, serta merespons insiden siber secara kontinu. SOC modern tidak lagi hanya mengandalkan pendekatan reaktif Level 1/2/3 eskalasi linier, melainkan mengadopsi model *fusion center* yang memadukan automasi SOAR (*Security Orchestration, Automation, and Response*), intelijen ancaman (*Cyber Threat Intelligence* / CTI), dan *threat hunting* proaktif.

#### SIEM Optimization
Optimasi SIEM adalah rekayasa performa ingest dan kueri data analitik keamanan. Pada sistem berbasis Lucene seperti Elasticsearch/OpenSearch, ini melibatkan konfigurasi *sharding*, pengaturan *refresh interval*, manajemen siklus hidup indeks (*Index Lifecycle Management* / ILM), serta kompilasi kueri terindeks. Pada Splunk, ini berfokus pada optimasi alokasi *index bucket* (hot, warm, cold, frozen), akselerasi data model (*tsidx*), dan penghindaran sub-kueri yang memicu *full table scan*.

#### Telemetry Pipelines
Pipeline telemetri adalah lapisan abstraksi komputasi perantara (*middleware*) yang memproses data kejadian (*event data*) sebelum didistribusikan ke tujuan akhir. Pipeline ini bertugas melakukan validasi skema, penyaringan (*filtering*), reduksi noise, pengayaan (*enrichment* dengan GeoIP atau CTI), penyamaran (*masking*) data sensitif, dan *conditional routing*.

#### GRC Frameworks
* **NIST CSF 2.0:** Kerangka kerja keamanan siber yang menambahkan fungsi **Govern (GV)** ke dalam lima fungsi intinya (Identify, Protect, Detect, Respond, Recover) untuk menyelaraskan strategi keamanan dengan prioritas bisnis, manajemen risiko pihak ketiga, dan pengawasan eksekutif.
* **ISO/IEC 27001:2022:** Standar internasional untuk *Information Security Management System* (ISMS) yang memuat klausul manajemen risiko sistemik dan Lampiran A (Annex A) yang memadatkan kontrol menjadi 4 tema: *Organizational, People, Physical,* dan *Technological*.
* **PCI-DSS v4.0:** Standar keamanan teknis dan operasional ketat untuk melindungi data akun pembayaran, memperkenalkan fleksibilitas implementasi melalui *Customized Approach* yang menuntut pembuktian efektivitas kontrol berbasis risiko secara berkelanjutan.

#### Business Continuity & Disaster Recovery (BC/DR)
* **RTO (Recovery Time Objective):** Durasi maksimum yang diizinkan untuk memulihkan fungsi sistem dan SecOps setelah insiden sebelum kerugian bisnis yang fatal terjadi.
* **RPO (Recovery Point Objective):** Batas maksimum kehilangan data telemetri atau status sistem yang dapat ditoleransi, diukur dalam satuan waktu.
* **MTD (Maximum Tolerable Downtime):** Ambang batas total waktu sistem boleh tidak beroperasi tanpa memicu kegagalan kelangsungan bisnis permanen.

---

### 6. Bagaimana Cara Kerja (How & Mekanika Internal Arsitektur)

#### Mekanisme Aliran Data Pipeline Telemetri
1. **Ingestion & Buffer:** Agent lokal (misal: Vector, Fluentbit) membaca log dari socket, pipe, atau file kernel. Data disimpan sementara dalam *in-memory ring buffer* atau *disk-backed queue* untuk mengantisipasi lonjakan (*burst*) dan kegagalan jaringan (*backpressure mitigation*).
2. **Transformasi & Parsing:** Log mentah yang tidak terstruktur diuraikan (*parsed*) menggunakan VRL (*Vector Remap Language*) atau filter regex menjadi format terstruktur (ECS - *Elastic Common Schema* atau CIM - *Common Information Model*).
3. **Redaction & Masking:** Sebelum log didistribusikan, fungsi regex deterministik mengeksekusi *hashing* atau *masking* pada data rahasia (seperti nomor kartu kredit, token JWT, nomor identitas kependudukan) untuk menjaga kepatuhan privasi.
4. **Conditional Routing:** Event bernilai deteksi tinggi dikirimkan ke Hot SIEM Index melalui protokol HTTP/JSON terkompresi. Event bervolume tinggi dengan nilai investigasi rendah dialihkan ke cold storage berbasis objek (misalnya AWS S3 dengan *Object Lock*) untuk kepatuhan jangka panjang.

```
Log Source ──> Agent Memory Buffer ──> VRL Parser / Masker ──┬──> [Hot] SIEM Engine (Elastic/Splunk)
                                                             └──> [Cold] Immutable WORM Storage
```

#### Mekanisme Indeks SIEM dan Siklus Hidup Data
Pada platform Elasticsearch:
* Log yang masuk diindeks ke dalam node bertipe *Hot* yang menggunakan media NVMe SSD. Parameter `refresh_interval` dinaikkan (misal: 30 detik) guna meminimalkan I/O overhead saat proses indexing berskala besar.
* Data bertransisi ke *Warm* tier (read-only, *force-merge* segment Lucene menjadi 1 segment per shard guna memangkas penggunaan memory footprint).
* Selanjutnya berpindah ke *Cold* dan *Frozen* tier menggunakan *Searchable Snapshots* pada Object Storage, memisahkan lapisan komputasi dari penyimpanan.

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

#### Tabel Perbandingan Karakteristik Arsitektur SIEM & Data Lake

| Parameter | Platform Elastic (ELK/ECS) | Splunk Enterprise (CIM) | Modern Telemetry Lake (ClickHouse/Vector) |
| :--- | :--- | :--- | :--- |
| **Indexing Model** | Lucene Inverted Index | TSIDX / Raw Compressed Journal | Columnar Store, Sparse Indexing |
| **Skema Data** | Schema-on-Write (ECS) | Schema-on-Read (CIM) | Strict Typed Columnar Schema |
| **Resource Footprint** | Tinggi pada RAM (JVM Heap) | Menengah/Tinggi pada Disk I/O | Rendah hingga Menengah, CPU Vectorization |
| **Model Biaya** | Berbasis Komputasi/Node | Berbasis Volume Ingest Harian / vCPU | Berbasis Komputasi Terbuka / Storage S3 |
| **Query Language** | KQL, EQL, ES|QL | SPL (*Search Processing Language*) | SQL Dialect / ClickHouse SQL |
| **Integrasi SOAR** | Elastic Defend Actions | Splunk SOAR (Phantom) native | API / Webhook Driven External |

#### Matriks Perbandingan Kontrol Framework Keamanan

| Kontrol Kunci | NIST CSF 2.0 | ISO/IEC 27001:2022 | PCI-DSS v4.0 |
| :--- | :--- | :--- | :--- |
| **Tata Kelola / Governance** | Subkategori Fungsi `GV` | Klausul 4 hingga 10 (ISMS Framework) | Requirement 12 (Program Governance) |
| **Manajemen Log & Audit** | Kategori `PR.PS`, `DE.CM` | Kontrol A.8.15 (Logging) | Requirement 10 (Log Review & Security) |
| **Continuous Monitoring** | Fungsi `DE` (Detect) | Kontrol A.8.16 (Monitoring Activities)| Requirement 10.4 & 11.4 |
| **Resiliensi & BC/DR** | Fungsi `RC` (Recover) | Kontrol A.5.29 s/d A.5.30 (ICT Readiness)| Requirement 12.10 (Incident Response) |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

```
Rantai Serangan Pipeline Telemetri:
[Attacker] ──> Inject Payload ──> [Parser Crash] ──> Log Drop / Blind Spot ──> Exploitation Unobserved
```

| Attack Vector | Mekanisme Kerentanan | Dampak Teknis | Strategi Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Log Injection / Splitting** | Penyerang menyisipkan karakter `\r\n` atau format JSON palsu ke dalam input yang tidak divalidasi. | Korupsi data log, manipulasi timeline forensik, pengaburan identitas penyerang (*evasion*). | Terapkan *structured logging* dari level aplikasi; gunakan *framing protocol* berbasis panjang byte pada forwarder. |
| **Parser Denial of Service** | Pengiriman string bersarang (*deeply nested JSON*) atau regex backtracking payloads (ReDoS) ke pipeline. | Pipeline crash, buffer overflow pada agent, kondisi *fail-open* di mana log dihentikan transmisi-nya. | Batasi kedalaman parsing dokumen; implementasikan engine regex berbasis otomata berhingga deterministik (DFA) seperti Rust `regex`. |
| **SIEM Blind Spot Exploitation**| Eksploitasi pengecualian (*tuning exclusion*) rules yang terlalu longgar (misal: mematikan alert untuk user admin tertentu). | Aktivitas malicious penyerang luput dari deteksi (*evasion*) secara penuh. | Audit rules SIEM secara otomatis via CI/CD; lakukan validasi berkala menggunakan platform *Breach and Attack Simulation* (BAS). |
| **SOAR Credential Hijacking**| Penyimpanan token API dengan hak akses mitigasi penuh (misal: Firewall API key) dalam format *plaintext* pada playbook. | Eksekusi perintah lateral traversal, modifikasi aturan firewall oleh musuh untuk memperluas akses. | Simpan secrets dalam external Hardware Security Module (HSM) atau Enterprise Vault dengan prinsip hak istimewa terkecil (*least privilege*). |

---

### 9. Code Example Sederhana: Basic PCI-DSS Log Scrubber (Vector VRL)

Script transformasi Vector Remap Language (VRL) berikut memvalidasi dan menyamarkan nomor kartu kredit (Primary Account Number / PAN) sesuai mandat PCI-DSS v4.0 sebelum diteruskan ke SIEM.

```vrl
# File: /etc/vector/transforms/pci_masker.vrl
# Parsing log mentah berformat JSON
. = parse_json!(string!(.message))

# Definisikan Regex untuk mendeteksi nomor kartu kredit standar (13-16 digit)
pan_regex = r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b'

# Lakukan pemeriksaan dan masking field payload jika ditemukan PAN
if match(string!(.payload), pan_regex) {
    # Ambil 6 digit pertama (BIN) dan 4 digit terakhir, samarkan sisanya
    .payload = replace(.payload, pan_regex) -> |matched| {
        len = length(matched)
        prefix = slice!(matched, 0, 6)
        suffix = slice!(matched, len - 4, len)
        masked_segment = "******"
        prefix + masked_segment + suffix
    }
    .pci_sanitized = true
} else {
    .pci_sanitized = false
}

# Tambahkan metadata audit integritas transmisi
.processed_at = now()
.ingestion_node = get_hostname!()
```

---

### 10. Code Example Lanjutan: Production-ready Pipeline & Detection Rule

#### Bagian A: Pipeline Konfigurasi Vector Lanjutan (`vector.yaml`)
Konfigurasi berikut menangani load balancing ingest, buffering berbasis disk terenkripsi untuk mencegah kehilangan data saat terjadi *outage*, masking otomatis, dan pemisahan tier penyimpanan.

```yaml
sources:
  enterprise_syslog:
    type: syslog
    address: 0.0.0.0:6514
    mode: tcp
    tls:
      enabled: true
      crt_file: /etc/vector/certs/syslog-server.crt
      key_file: /etc/vector/certs/syslog-server.key
      ca_file: /etc/vector/certs/internal-ca.crt
      verify_certificate: true

transforms:
  normalize_and_sanitize:
    type: remap
    inputs:
      - enterprise_syslog
    source: |
      # Normalisasi ke format ECS
      .event.ingested = now()
      .host.hostname = del(.host)
      .log.syslog.facility = del(.facility)
      .log.syslog.severity = del(.severity)
      
      # Redaksi Token Bearer/API Keys
      bearer_regex = r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*'
      if match(string!(.message), bearer_regex) {
        .message = replace(.message, bearer_regex, "Bearer [REDACTED_BY_PIPELINE]")
      }

      # Filter out low-value healthcheck noise
      if match(string!(.message), r'kube-probe|healthcheck|ELB-HealthChecker') {
        abort
      }

sinks:
  siem_hot_storage:
    type: elasticsearch
    inputs:
      - normalize_and_sanitize
    endpoints:
      - "https://es-hot-cluster.internal.net:9200"
    mode: "bulk"
    bulk:
      index: "secops-telemetry-%Y.%m.%d"
    buffer:
      type: disk
      max_size: 107374182400 # 100 GiB Disk-backed buffer jika SIEM offline
      when_full: block
    auth:
      strategy: bearer
      token: "${ES_INGEST_API_TOKEN}"
    tls:
      ca_file: /etc/vector/certs/internal-ca.crt

  immutable_compliance_archive:
    type: aws_s3
    inputs:
      - normalize_and_sanitize
    bucket: "enterprise-secops-wwn-immutable-logs"
    region: "ap-southeast-1"
    key_prefix: "retention-7-years/%Y/%m/%d/"
    compression: "gzip"
    buffer:
      type: memory
      max_events: 10000
    server_side_encryption: "aws:kms"
    ssekms_key_id: "arn:aws:kms:ap-southeast-1:123456789012:key/secops-audit-key"
```

#### Bagian B: Elasticsearch Query Language (EQL) Detection Rule
Aturan korelasi EQL ini mendeteksi upaya manipulasi audit log yang dikuti oleh eksfiltrasi data, memetakan taksonomi MITRE ATT&CK T1070 (Indicator Removal) dan NIST CSF 2.0 `DE.CM`.

```eql
/*
  Title: Log Pipeline Tampering Followed by Suspicious Network Connection
  Severity: Critical
  Frameworks: NIST CSF 2.0 (DE.CM-01), ISO 27001:2022 (A.8.15), PCI-DSS v4.0 (Req 10.3.4)
*/

sequence with maxspan=5m
  [process where event.category == "process" and event.type == "start" and
   process.name in ("systemctl", "service", "net.exe") and
   process.args in ("stop", "disable") and
   process.args in ("auditd", "vector", "fluentd", "filebeat", "SplunkForwarder")]
  [process where event.category == "process" and event.type == "start" and
   process.name in ("curl", "wget", "powershell.exe", "certutil.exe", "nc") and
   process.args : ("*http://*", "*https://*", "*ftp://*") and
   not cidrmatch(destination.ip, "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
```

---

### 11. Diagram Alur Serangan & Mitigasi (Attack & Defense Flow)

```
ATTACK PATH (Log Manipulation & Blind Spot Insertion)
  [1. Threat Actor] 
         │ Mengirim exploit payload via TCP Stream
         ▼
  [2. Unhardened Log Forwarder] 
         │ Gagal menangani malformed character / buffer parsing
         ▼
  [3. Pipeline Denial of Service] ───> Log Forwarder Crash (Zero Visibility Gap)
         │
         ▼
  [4. Lateral Movement & Exfiltration] (Dilakukan tanpa terdeteksi oleh SOC)

───────────────────────────────────────────────────────────────────────────────────

DEFENSE-IN-DEPTH MITIGATION PATH
  [1. Threat Actor] 
         │ Mengirim exploit payload via TCP Stream
         ▼
  [2. Hardened Ingest Pipeline (mTLS + In-flight Stream Validator)]
         │ Validasi skema ketat; karakter non-RFC langsung disanitasi
         ├─────────────────────────────────────────┐
         ▼                                         ▼
  [3A. Disk Buffer Queue Aktif]          [3B. Anomaly Alert Generated]
  (Mencegah OOM & drop data)             (Format mismatch dicatat di SIEM)
         │                                         │
         ▼                                         ▼
  [4. Dual Routing Target]               [5. Automated SOAR Playbook]
  - Hot: SIEM Indexing Engine            Isolasi host pengirim anomali
  - Cold: Object Storage WORM Lock       melalui integrasi API EDR
```

---

### 12. Trade-offs & Security vs Usability / Performance

* **Full Payload Logging vs Throughput Komputasi:**
  * *Pilihan A (Full Payload):* Menyimpan raw packet dan seluruh body request HTTP. Memberikan konteks investigasi absolut, namun menyebabkan beban I/O SIEM meningkat tajam dan biaya lisensi/penyimpanan membengkak.
  * *Pilihan B (Metadata Extracted):* Hanya menyimpan metadata standar (IP, Port, Headers, hashes). Menghasilkan efisiensi penyimpanan hingga 80%, tetapi kehilangan detail forensik serangan level aplikasi kompleks.
* **Aggressive Filtering pada Edge vs SIEM Central Processing:**
  * Menjalankan transformasi kompleks di edge agent menghemat bandwidth jaringan pusat, namun meningkatkan konsumsi vCPU pada server produksi bisnis. 
  * Sebaliknya, pemrosesan terpusat membebani pipeline tengah dan meningkatkan latensi deteksi (*Mean Time To Detect*).
* **Strict Schema Validation vs Zero Log Loss:**
  * Penerapan skema ECS/CIM yang kaku akan membuang (*drop*) log yang tidak sesuai spesifikasi demi integritas kueri SIEM.
  * Solusi seimbang memerlukan *dead-letter queue* (DLQ) ke penyimpanan terpisah untuk log yang gagal diparsing, menghindari log drop tanpa mengorbankan kestabilan indeks utama.

---

### 13. Edge Cases & Complex Failure Modes

* **Network Partition & Backpressure Cascading Failure:** Jika cluster SIEM mengalami degradasi performa atau kehabisan disk space, koneksi ingest menolak data masuk. Forwarder yang tidak dikonfigurasi dengan *bounded persistent queue* akan menggunakan seluruh alokasi memori sistem host hingga memicu kernel *Out-of-Memory (OOM) Killer*, yang dapat mematikan proses forwarder atau layanan bisnis utama pada host tersebut.
* **Timestamp Skew & Causality Violation:** Desinkronisasi protokol NTP antar server log menghasilkan deviasi waktu event (*clock drift*). Hal ini menyebabkan kegagalan fatal pada aturan korelasi temporal SIEM yang mengandalkan jendela waktu berurutan (`sequence with maxspan`), sehingga serangan multi-tahap gagal diidentifikasi.
* **Regex Engine Catastrophic Backtracking:** Penggunaan ekspresi reguler yang buruk dalam masking log dapat dimanfaatkan oleh payload attacker yang dirancang khusus. Ini menyebabkan CPU utilization melonjak hingga 100% pada node transformasi (*ReDoS*), menghentikan pemrosesan telemetri bagi seluruh enterprise.

---

### 14. Anti-Patterns & Common Vulnerabilities

* **The "Ingest Everything, Store Blindly" Anti-Pattern:** Mengirimkan seluruh log debug dan trace langsung ke SIEM berbayar tanpa reduksi. Dampak: Biaya komputasi melonjak tanpa meningkatkan postur deteksi; rasio *signal-to-noise* memburuk secara signifikan.
* **Paper-Driven GRC Compliance Anti-Pattern:** Mengonfigurasi retensi log 365 hari pada storage murah tanpa mekanisme pengujian integritas atau verifikasi berkala (*audit-only compliance*). Saat audit atau insiden nyata terjadi, log tersebut korup, terenkripsi ransomware, atau tidak terbaca akibat ketiadaan parser.
* **Overprivileged SOAR Service Accounts:** Menggunakan kredensial tunggal dengan hak akses administrator penuh domain (*Enterprise Admin*) untuk integrasi SOAR. Kerentanan injeksi perintah pada skrip automasi SOAR dapat memberikan kendali menyeluruh atas seluruh infrastruktur enterprise kepada penyerang.

---

### 15. Best Practices & Enterprise Remediation Guide

1. **Implementasi Data Tiering Menggunakan ILM (Index Lifecycle Management):**
   * *Hot (0–7 hari):* Solid-State Drive (NVMe), primary shards aktif untuk deteksi *real-time*.
   * *Warm (8–30 hari):* Read-only, storage berbasis SSD murah, indeks di-*shrink* dan di-*force-merge*.
   * *Cold (31–90 hari):* Disimpan dalam bentuk searchable snapshot di cloud object storage.
   * *Frozen/Archive (91–2555 hari):* Immutable Object Storage dengan WORM (Write Once, Read Many) compliant terhadap regulasi retensi 7 tahun.
2. **Kriptografis Rantai Integritas Log:** Terapkan penandatanganan kriptografis (*hash chaining*) pada blok log langsung dari node ingest untuk memastikan keaslian bukti digital di depan proses peradilan.
3. **Penyelarasan Kontrol Berkesinambungan (Continuous Control Monitoring):** Gunakan automasi berbasis API untuk memvalidasi bahwa setiap resource cloud yang baru di-*provisioning* langsung mengirimkan telemetri ke pipeline terpusat sebelum izin jaringan diberikan (*policy-as-code*).

---

### 16. Hands-on Lab Step-by-Step

Lab ini memandu implementasi pipeline pemrosesan telemetri menggunakan Vector dan Elasticsearch secara langsung.

#### Langkah 1: Persiapan Environment & Inisialisasi Workspace
```bash
# Buat direktori kerja lab
mkdir -p /opt/secops-lab/{config,data,certs}
cd /opt/secops-lab

# Generate internal testing self-signed certificates untuk mTLS Syslog
openssl req -x509 -newkey rsa:4096 -nodes -sha256 -keyout certs/server.key \
  -out certs/server.crt -days 30 -subj "/CN=telemetry.secops.local"
```

#### Langkah 2: Konstruksi Konfigurasi Vector Telemetry Engine
Simpan file berikut di `/opt/secops-lab/config/vector.toml`:

```toml
[sources.in_syslog]
type = "syslog"
address = "0.0.0.0:5140"
mode = "tcp"

[transforms.sanitize_and_parse]
type = "remap"
inputs = ["in_syslog"]
source = '''
  # Parsing event data
  . = parse_json(.message) ?? {"raw_message": .message}
  
  # Hapus field debug tidak berguna
  del(.debug_payload)
  
  # PCI-DSS Masking: Deteksi 16 digit angka kartu
  if exists(.credit_card) {
    .credit_card = replace(string!(.credit_card), r'([0-9]{6})[0-9]{6}([0-9]{4})', "$1******$2")
  }
  
  .metadata_enriched = true
  .processed_timestamp = now()
'''

[sinks.out_console]
type = "console"
inputs = ["sanitize_and_parse"]
encoding.codec = "json"

[sinks.out_blackhole_audit]
type = "file"
inputs = ["sanitize_and_parse"]
path = "/opt/secops-lab/data/audit_processed.log"
encoding.codec = "ndjson"
```

#### Langkah 3: Eksekusi Engine Vector
Jalankan instance pemrosesan menggunakan container Docker:

```bash
docker run -d --name secops-telemetry-engine \
  -v /opt/secops-lab/config/vector.toml:/etc/vector/vector.toml:ro \
  -v /opt/secops-lab/data:/opt/secops-lab/data \
  -p 5140:5140 \
  timberio/vector:0.35.0-alpine
```

#### Langkah 4: Uji Pengiriman Log Normal dan Payload Kritis
Kirimkan event data simulasi menggunakan `nc` (Netcat):

```bash
# Event 1: Transaksi Keuangan mengandung Data Kartu Kredit
echo '{"user": "alice", "action": "checkout", "credit_card": "4532015588321094", "amount": 150.00}' | nc -w 1 127.0.0.1 5140

# Event 2: Aktivitas Administratif Mencurigakan
echo '{"user": "root", "action": "modify_firewall", "debug_payload": "verbose_debug_dump_data", "rule": "ACCEPT ALL"}' | nc -w 1 127.0.0.1 5140
```

#### Langkah 5: Verifikasi Hasil Sanitasi dan Efisiensi Log
Periksa output yang tersimpan di dalam file audit log:

```bash
cat /opt/secops-lab/data/audit_processed.log | jq .
```

*Expected Verification Output:*
```json
{
  "action": "checkout",
  "amount": 150,
  "credit_card": "453201******1094",
  "metadata_enriched": true,
  "processed_timestamp": "2026-03-31T06:00:00.000000Z",
  "user": "alice"
}
{
  "action": "modify_firewall",
  "metadata_enriched": true,
  "processed_timestamp": "2026-03-31T06:00:01.000000Z",
  "rule": "ACCEPT ALL",
  "user": "root"
}
```
*Analisis:* `debug_payload` berhasil dihilangkan secara permanen guna mereduksi biaya komputasi, dan PAN telah tersanitasi sesuai kepatuhan PCI-DSS v4.0.

---

### 17. Real-world Case Study & Incident Analysis Enterprise

#### Studi Kasus: Kegagalan Arsitektur Logging pada Serangan Ransomware Institusi Finansial Global

* **Konteks:** Sebuah lembaga perbankan investasi multinasional mengoperasikan kluster SIEM terpusat dengan volume ingest sebesar 15 TB/hari. Sistem ini diaudit menggunakan kerangka kerja NIST CSF dan PCI-DSS.
* **Vektor Penetrasi:** Aktor ancaman memperoleh akses kredensial awal melalui supply chain VPN vendor pihak ketiga yang tidak mewajibkan MFA (*NIST CSF PR.AC violation*).
* **Anatomi Insiden & Kegagalan SecOps:**
  1. Setelah masuk ke jaringan internal, aktor meluncurkan teknik *Log Flooding* terdistribusi dari beberapa host yang telah dikuasai, mengirimkan jutaan pesan syslog palsu (*noise injection*) secara terus-menerus.
  2. Arsitektur pipeline SIEM tidak memiliki isolasi resource atau buffer disk-backed terpisah. Lonjakan ini memicu kondisi kehabisan memori (*OOM*) pada ingestion forwarder utama, sehingga SIEM mengalami *drop state* secara masif.
  3. Aktor ancaman memanfaatkan waktu *blind spot* ini (yang berlangsung selama 4 jam tanpa notifikasi ke tim SOC) untuk mengeksekusi script PowerShell guna menonaktifkan cadangan data lokal dan menyebarkan malware ransomware di 400 server produksi.
  4. Penyimpanan cadangan yang tidak menerapkan imutabilitas WORM turut terenkripsi oleh malware penyerang.
* **Akar Masalah (Root Cause):**
  * Tidak adanya rate-limiting per-sumber pada telemetry ingest pipeline.
  * Metrik performa pipeline tidak dimonitor melalui channel *out-of-band* independen.
  * Strategi BC/DR mengandalkan backup yang dapat ditulis ulang (*mutable*), melanggar kontrol pemisahan ISO 27001:2022 A.8.13.
* **Remediasi & Reformulasi Desain:**
  * Implementasi Vector cluster stateless dengan alokasi buffer berbasis disk terisolasi.
  * Penerapan *token-bucket rate limiting* pada ingestion edge.
  * Penyimpanan salinan cadangan sekunder di AWS S3 dengan *Object Lock Compliance Mode* dan konfigurasi multi-region lintas penyedia cloud (*cross-cloud recovery architecture*).
  * Pengurangan RPO sistem penanganan insiden dari 24 jam menjadi < 5 menit.

---

### 18. Quiz Pemahaman & Challenge

#### Soal 1
Pada arsitektur SIEM berskala besar berbasis Lucene, parameter manakah yang paling efektif dinaikkan untuk meningkatkan performa *indexing throughput* pada node Hot dengan konsekuensi peningkatan latensi visibilitas data pencarian secara temporal?
* A. `index.number_of_replicas`
* B. `index.refresh_interval`
* C. `indices.memory.index_buffer_size`
* D. `thread_pool.search.queue_size`

#### Soal 2
Di bawah kerangka kerja NIST CSF 2.0, implementasi kebijakan formal mengenai penilaian risiko rantai pasok siber (*Cybersecurity Supply Chain Risk Management*) secara spesifik dikelompokkan ke dalam fungsi utama:
* A. Identify (ID)
* B. Protect (PR)
* C. Govern (GV)
* D. Detect (DE)

#### Soal 3
Sebuah pipeline telemetri mengalami kondisi di mana volume data log melonjak 5 kali lipat dalam hitungan menit akibat insiden keamanan. Apa kegagalan teknis utama yang akan terjadi jika agent pipeline dikonfigurasi dengan mode buffer memori murni tanpa parameter limitasi batas atas (*unbounded memory queue*)?
* A. Log akan terenkripsi otomatis secara prematur.
* B. Agent akan memicu kernel panic atau dihentikan paksa oleh OS Out-of-Memory (OOM) Killer, menyebabkan blind spot log total.
* C. Port koneksi ingest secara otomatis beralih menggunakan protokol UDP.
* D. Indeks data SIEM terhapus secara permanen.

#### Soal 4
Tindakan manakah yang melanggar mandat perlindungan data akun pada PCI-DSS v4.0 Requirement 3 ketika mentransmisikan event telemetri ke platform SIEM?
* A. Melakukan hashing pada nomor akun utama (PAN) menggunakan algoritma SHA-256 yang diberi salt.
* B. Menghapus nilai *Card Verification Value* (CVV/CVC) sepenuhnya dari payload log secara permanen.
* C. Menyimpan nilai Card Verification Value (CVV/CVC) di penyimpanan indeks Hot SIEM untuk keperluan deteksi fraud transaksi.
* D. Menyamarkan PAN sehingga hanya menyisakan 6 digit pertama dan 4 digit terakhir.

#### Soal 5
Dalam perencanaan Business Continuity & Disaster Recovery (BC/DR) untuk infrastruktur SecOps, parameter yang mendefinisikan batas waktu toleransi maksimum operasional sistem terhenti sebelum timbul kerugian fatal yang menghentikan kelangsungan bisnis organisasi adalah:
* A. Recovery Point Objective (RPO)
* B. Mean Time to Remediate (MTTR)
* C. Maximum Tolerable Downtime (MTD)
* D. Work Recovery Time (WRT)

---

#### Jawaban Quiz & Pembahasan

* **Soal 1: Jawaban B.** Nilai `index.refresh_interval` menentukan seberapa sering segmen Lucene dibuat agar dapat dicari. Menaikkan nilai ini (misal dari default 1 detik ke 30 detik) mengurangi beban I/O secara drastis dan menaikkan indexing throughput, dengan konsekuensi log baru bisa dicari 30 detik setelah ingestion.
* **Soal 2: Jawaban C.** NIST CSF 2.0 secara resmi memperkenalkan fungsi baru yaitu **Govern (GV)** yang mencakup tata kelola menyeluruh, termasuk subkategori C-SCRM (Cybersecurity Supply Chain Risk Management / GV.SC).
* **Soal 3: Jawaban B.** Buffer memori tanpa batas (*unbounded memory queue*) akan terus mengonsumsi alokasi RAM server saat downstream macet (*backpressure*), yang berakibat pada intervensi kernel OOM killer untuk mematikan proses agent pengekspor log secara paksa.
* **Soal 4: Jawaban C.** PCI-DSS v4.0 melarang keras penyimpanan data autentikasi sensitif (*Sensitive Authentication Data* / SAD) seperti CVV/CVC setelah proses otorisasi, bahkan jika data tersebut disimpan dalam sistem pemantauan atau analitik keamanan SIEM.
* **Soal 5: Jawaban C.** Maximum Tolerable Downtime (MTD) adalah metrik payung kelangsungan bisnis yang merepresentasikan total waktu kegagalan sistem yang dapat ditanggung organisasi tanpa kehilangan kelangsungan hidup usahanya ($MTD \ge RTO + WRT$).

---

#### Advanced Engineering Challenge
**Skenario Tantangan:**
Anda bertugas sebagai Principal SecOps Architect. Perusahaan Anda menghadapi tagihan ingest SIEM yang melonjak drastis akibat log dari kluster Kubernetes yang menghasilkan 50.000 events/detik. 70% dari event ini adalah event status HTTP 200 dari ingress controller internal dan kubernetes healthchecks (`/healthz`). Pada saat yang sama, tim GRC mewajibkan pemenuhan ISO/IEC 27001:2022 kontrol A.8.15 yang menuntut bahwa jejak akses administratif dan error server internal (HTTP 5xx) tetap disimpan selama minimal 1 tahun dan keasliannya terjamin secara hukum.

**Tugas Praktik Anda:**
1. Rancang konfigurasi VRL (Vector Remap Language) yang membuang semua HTTP status 200/healthcheck log yang berasal dari user-agent internal.
2. Pastikan log dengan respons HTTP 4xx dan 5xx diekstraksi field utamanya (`source.ip`, `url.path`, `http.response.status_code`) ke format ECS, lalu diteruskan ke sink Hot SIEM.
3. Rute seluruh log administratif yang melibatkan namespace `kube-system` ke sink Immutable Storage yang dikonfigurasi dengan hash chaining SHA-256 untuk pemenuhan klausul pembuktian forensik.

---

### 19. Summary & Key Takeaways
* Arsitektur SOC modern bergeser dari model reaktif eskalasi berjenjang menuju model terintegrasi yang digerakkan oleh pipeline telemetri pintar, otomatisasi SOAR, dan penegakan tata kelola terpadu.
* Ingestion pipeline berfungsi sebagai komponen krusial dalam menyaring noise, mengenkripsi telemetri dalam perjalanan (*in-flight*), memitigasi *backpressure*, dan menjamin masking data sensitif sebelum log masuk ke SIEM.
* Optimasi SIEM menuntut rekayasa data mendalam: penerapan siklus hidup data (ILM) multi-tier dan normalisasi skema data (ECS/CIM) mutlak diperlukan untuk menjaga stabilitas komputasi dan efisiensi biaya penyimpanan.
* Kerangka kerja GRC modern (NIST CSF 2.0, ISO/IEC 27001:2022, PCI-DSS v4.0) harus diintegrasikan langsung ke dalam arsitektur deteksi teknis, bukan sekadar diverifikasi melalui dokumen checklist tahunan.
* Ketahanan arsitektur SecOps bergantung pada perencanaan BC/DR yang matang dengan metrik RTO, RPO, dan MTD yang realistis, serta penerapan penyimpanan cadangan yang bersifat *immutable* guna mengantisipasi serangan ransomware modern.

---

### 20. Referensi Resmi & Standar Keamanan
* **NIST Special Publication 800-61 Rev. 2:** *Computer Security Incident Handling Guide* – Rekomendasi pembentukan struktur dan kapabilitas operasional SOC.
* **NIST CSF 2.0 (2024):** *The Cybersecurity Framework 2.0* – Penambahan fungsi tata kelola keamanan (*Govern*).
* **ISO/IEC 27001:2022:** *Information security, cybersecurity and privacy protection — Information security management systems — Requirements* (Klausul 4-10 dan Annex A Controls).
* **Payment Card Industry Data Security Standard (PCI-DSS):** *Requirements and Testing Procedures Version 4.0* – Requirement 10 (Log Monitoring and Testing Architecture).
* **MITRE ATT&CK Framework:** *Technique T1070 (Indicator Removal on Host)* dan *T1562 (Impair Defenses)*.
* **RFC 5424:** *The Syslog Protocol* – Standar formal transmisi dan struktur log sistem.