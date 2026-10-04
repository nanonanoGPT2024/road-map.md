# Kurikulum Silabus: Forward Deployed Engineer (FDE)

Dokumen ini memuat silabus komprehensif 10 Bab jalur pembelajaran **Forward Deployed Engineer (FDE)**. Kurikulum dirancang untuk mencetak insinyur perangkat lunak elit yang mampu beroperasi di garis depan teknis: memadukan keahlian sistem terdistribusi, rekayasa data skala enterprise, penyebaran infrastruktur on-premises/air-gapped, serta diplomasi teknis tingkat tinggi di hadapan eksekutif klien.

---

## 1. Ringkasan Kursus & Pola Pikir (Course Overview & Mindset)

### Definisi dan Peran Forward Deployed Engineer
Forward Deployed Engineer (FDE) adalah varian spesifik insinyur perangkat lunak yang beroperasi langsung di antarmuka antara produk inti perusahaan (*core product*) dan infrastruktur nyata milik klien enterprise skala tier-1 (perbankan, pertahanan, energi, logistik global). Model kerja ini dipelopori oleh perusahaan seperti Palantir dan diadopsi secara luas di industri enterprise B2B modern.

FDE memikul dua peran kritis (*dual-competency paradigm*):
1. **Core Systems Builder**: Mengembangkan ekstensi arsitektur, pipeline integrasi, dan logika komputasi dengan standar rekayasa backend/sistem terdistribusi paling ketat.
2. **Technical Ambassador & Systems Navigator**: Menganalisis topologi sistem klien yang usang (*legacy*), membedah regulasi restriktif, meredakan kekhawatiran arsitek internal klien, dan memastikan *time-to-value* tercapai dalam hitungan minggu, bukan tahun.

```
+-------------------------------------------------------------------------------+
|                       FORWARD DEPLOYED ENGINEER (FDE)                         |
|                                                                               |
|   [ Core Product R&D ] <==== Arsitektur Upstream ====> [ Lingkungan Klien ]   |
|   - Distributed Engines                                - Air-Gapped K8s       |
|   - Reusable SDKs                                      - Legacy RDBMS/Mainframe|
|   - Performance Profiling                              - Strict Zero-Trust    |
|   - Extensibility APIs                                 - Stakeholder Politics |
+-------------------------------------------------------------------------------+
```

### Pola Pikir FDE (The FDE Operating Principles)
* **Embrace Ambient Ambiguity**: Klien jarang mengetahui spesifikasi teknis masalah mereka secara presisi. FDE harus mampu mengonversi keluhan bisnis yang ambigu menjadi dokumen spesifikasi teknis formal (*RFC/Design Docs*).
* **Bias for Working Code over Speculation**: Memvalidasi hipotesis dengan membuat *proof-of-concept* (PoC) berbasis kode nyata di lingkungan klien secara cepat (*rapid prototyping*) daripada terjebak dalam siklus rapat yang tidak produktif.
* **Upstream-First Mentality**: Menolak godaan untuk membuat solusi *one-off hacky patch* yang mengotori *codebase*. Setiap integrasi kustom harus diabstraksikan menjadi komponen atau modul yang dapat diserap kembali ke produk inti (*core product upstreaming*).
* **Extreme Ownership of the Edge**: Bertanggung jawab penuh atas ketersediaan, performa, keamanan, dan kepatuhan sistem sejak hari pertama instalasi hingga serah terima produksi (*production sign-off*).

---

## 2. Peta Pembelajaran (Learning Roadmap)

```text
Forward Deployed Engineering (FDE)
├── Bab 01: Fondasi FDE & Discovery Masalah Enterprise
├── Bab 02: Arsitektur Integrasi & Interoperabilitas Sistem Legacy
├── Bab 03: Data Engineering Lapangan & Data Mesh Skala Besar
├── Bab 04: Infrastruktur Hybrid-Cloud, On-Premises & Air-Gapped Environments
├── Bab 05: Keamanan Enterprise, Zero-Trust & Kepatuhan Regulasi
├── Bab 06: Rapid Prototyping & Bespoke Solution Engineering
├── Bab 07: Observabilitas Lapangan, Incident Triage & Telemetri Terdistribusi
├── Bab 08: Optimasi Performa, Tuning Latensi & Skalabilitas Sistem
├── Bab 09: Manajemen Stakeholder Teknis, Eksekutif & Upstreaming
└── Bab 10: Enterprise Capstone Project: Mission-Critical Deployment
```

---

## 3. Navigasi Detail Modul (Bab 01 s/d Bab 10)

### [Bab 01: Fondasi FDE & Discovery Masalah Enterprise](./01-fondasi-fde-discovery-enterprise/README.md)
Pelajari metodologi dekonstruksi ekosistem klien, pemetaan pemangku kepentingan teknis, dan identifikasi batasan operasional non-fungsional.
* [01.1 Anatomi Peran FDE vs Solutions Architect vs Core SWE](./01-fondasi-fde-discovery-enterprise/01-anatomi-peran-fde.md)
* [01.2 Metodologi Discovery & Rapid Architecture Reverse Engineering](./01-fondasi-fde-discovery-enterprise/02-reverse-engineering-arsitektur-klien.md)
* [01.3 Formulasi Technical Requirement Document (TRD) & Scope Guarding](./01-fondasi-fde-discovery-enterprise/03-formulasi-trd-scope-guarding.md)

### [Bab 02: Arsitektur Integrasi & Interoperabilitas Sistem Legacy](./02-arsitektur-integrasi-sistem-legacy/README.md)
Kuasai pola integrasi enterprise (EIP), strategi parsing protokol lama (SOAP, COBOL copybooks, EDIFACT), dan modernisasi antarmuka legacy ke API modern.
* [02.1 Enterprise Integration Patterns (EIP) & Event Broker Bridging](./02-arsitektur-integrasi-sistem-legacy/01-enterprise-integration-patterns.md)
* [02.2 Integrasi Mainframe, ERP Monolitik (SAP/Oracle), & Proprietary RDBMS](./02-arsitektur-integrasi-sistem-legacy/02-integrasi-mainframe-dan-erp.md)
* [02.3 CDC (Change Data Capture) Multi-Platform via Debezium & Kafka](./02-arsitektur-integrasi-sistem-legacy/03-cdc-debezium-kafka-legacy.md)

### [Bab 03: Data Engineering Lapangan & Data Mesh Skala Besar](./03-data-engineering-lapangan-data-mesh/README.md)
Rancang dan eksekusi ingestion pipeline tangguh menghadapi skema yang berubah acak, data kotor, dan komputasi federasi multi-region.
* [03.1 Penanganan Dirty Data, Schema Drift, & Dynamic Type Coercion](./03-data-engineering-lapangan-data-mesh/01-penanganan-schema-drift-dirty-data.md)
* [03.2 Arsitektur Query Terdistribusi Menggunakan Trino/Presto & Apache Spark](./03-data-engineering-lapangan-data-mesh/02-distributed-query-trino-spark.md)
* [03.3 Implementasi Data Governance & Lineage Metadata Terotomasi](./03-data-engineering-lapangan-data-mesh/03-governance-lineage-openlineage.md)

### [Bab 04: Infrastruktur Hybrid-Cloud, On-Premises & Air-Gapped Environments](./04-infrastruktur-hybrid-onprem-airgapped/README.md)
Deploy aplikasi terdistribusi modern di pusat data klien tanpa akses internet, menggunakan sistem kontainer mandiri dan storage enterprise.
* [04.1 Topologi Air-Gapped: Private Registry, Sneakernet CI/CD, & Zot/Harbor](./04-infrastruktur-hybrid-onprem-airgapped/01-air-gapped-registry-packaging.md)
* [04.2 Kubernetes Bare-Metal Orchestration (RKE2, K3s, OpenShift Deployment)](./04-infrastruktur-hybrid-onprem-airgapped/02-baremetal-k8s-rke2-openshift.md)
* [04.3 Manajemen Jaringan On-Premises: BGP, Proxy Korporat, & egress lockdown](./04-infrastruktur-hybrid-onprem-airgapped/03-enterprise-networking-proxy-storage.md)

### [Bab 05: Keamanan Enterprise, Zero-Trust & Kepatuhan Regulasi](./05-keamanan-enterprise-zero-trust-compliance/README.md)
Terapkan postur keamanan bank/militer: enkripsi end-to-end, rotasi sertifikat mTLS otomatis, RBAC/ABAC granular, dan kesiapan audit.
* [05.1 Arsitektur Zero-Trust, mTLS Istio/Envoy, & Manajemen Identitas (SPIFFE/SPIRE)](./05-keamanan-enterprise-zero-trust-compliance/01-zero-trust-mtls-spiffe-spire.md)
* [05.2 Fine-Grained Authorization: OPA (Open Policy Agent) & Cedar/Zanzibar](./05-keamanan-enterprise-zero-trust-compliance/02-authz-opa-zanzibar-policy.md)
* [05.3 Kepatuhan Standar Industri (SOC2, HIPAA, GDPR) & Sanitasi Audit Trail](./05-keamanan-enterprise-zero-trust-compliance/03-compliance-data-sanitization-audit.md)

### [Bab 06: Rapid Prototyping & Bespoke Solution Engineering](./06-rapid-prototyping-bespoke-engineering/README.md)
Bangun modul kustom berkecepatan tinggi tanpa merusak integritas arsitektur; manfaatkan SDK internal, FFI bindings, dan arsitektur plugin dinamis.
* [06.1 Arsitektur Ekstensibilitas: WebAssembly (Wasm) Plugin Engine & gRPC Plugins](./06-rapid-prototyping-bespoke-engineering/01-plugin-architecture-wasm-grpc.md)
* [06.2 Scaffolding Solusi Custom FDE Berbasis Go/Rust/TypeScript](./06-rapid-prototyping-bespoke-engineering/02-high-velocity-scaffolding-go-rust.md)
* [06.3 Strategi Feature Flagging Terisolasi Klien via OpenFeature](./06-rapid-prototyping-bespoke-engineering/03-feature-flagging-isolated-tenants.md)

### [Bab 07: Observabilitas Lapangan, Incident Triage & Telemetri Terdistribusi](./07-observabilitas-lapangan-incident-triage/README.md)
Lakukan investigasi forensik dan debugging mendalam pada lingkungan tertutup klien menggunakan eBPF, OpenTelemetry terisolasi, dan core dump profiling.
* [07.1 Distributed Tracing & Metric Gathering di Lingkungan Air-Gapped](./07-observabilitas-lapangan-incident-triage/01-airgapped-opentelemetry-grafana.md)
* [07.2 Debugging Kernel & Lapisan Jaringan Menggunakan eBPF (BCC/Cilium)](./07-observabilitas-lapangan-incident-triage/02-ebpf-kernel-network-profiling.md)
* [07.3 Runbook Mitigasi Insiden Kritis Klien P1/SEV0 di Bawah Tekanan SLA](./07-observabilitas-lapangan-incident-triage/03-p1-sev0-incident-management.md)

### [Bab 08: Optimasi Performa, Tuning Latensi & Skalabilitas Sistem](./08-optimasi-performa-tuning-skalabilitas/README.md)
Tingkatkan throughput dan pangkas latensi end-to-end pada kombinasi hardware terbatas milik klien yang tidak optimal.
* [08.1 Linux OS Profiling & Tuning Kernel Param (sysctl, I/O schedulers, NUMA)](./08-optimasi-performa-tuning-skalabilitas/01-os-profiling-numa-io-tuning.md)
* [08.2 Query Optimization, Indexing Terdistribusi, & Remediasi IOPS Bottleneck](./08-optimasi-performa-tuning-skalabilitas/02-database-io-contention-tuning.md)
* [08.3 Benchmarking Real-Time, Load Generation, & Concurrency Engineering](./08-optimasi-performa-tuning-skalabilitas/03-distributed-load-testing-profiling.md)

### [Bab 09: Manajemen Stakeholder Teknis, Eksekutif & Upstreaming](./09-manajemen-stakeholder-upstreaming/README.md)
Kuasai seni diplomasi teknis: presentasi di hadapan C-Suite, peredaman konflik arsitektural internal, serta proses upstreaming fitur klien ke R&D inti.
* [09.1 Berbicara dengan C-Level: Menghubungkan Metrik Teknis ke Nilai Bisnis](./09-manajemen-stakeholder-upstreaming/01-executive-communication-translating-metrics.md)
* [09.2 Resolusi Konflik Arsitektur dengan Tim Infosec & DevOps Internal Klien](./09-manajemen-stakeholder-upstreaming/02-handling-internal-infosec-blockers.md)
* [09.3 Life Cycle Upstreaming: Mengonversi Custom Edge Code Menjadi Core Platform](./09-manajemen-stakeholder-upstreaming/03-core-product-upstreaming-mechanics.md)

### [Bab 10: Enterprise Capstone Project: Mission-Critical Deployment](./10-enterprise-capstone-project/README.md)
Proyek akhir komprehensif: deployment, integrasi, audit, dan pembuktian performa sistem analitik terdistribusi di lingkungan simulasi bank sentral air-gapped.
* [10.1 Spesifikasi Masalah & Arsitektur Capstone: Proyek Ares-Alpha](./10-enterprise-capstone-project/01-capstone-specs-ares-alpha.md)
* [10.2 Milestone Implementasi, Validasi Keamanan, & Stress-Testing](./10-enterprise-capstone-project/02-milestones-and-validation.md)
* [10.3 Dokumen Serah Terima Produksi & Presentasi Akhir ke Dewan Penguji](./10-enterprise-capstone-project/03-production-handover-defense.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Nama Proyek: **Project Ares-Alpha (Autonomous Fraud & AML Settlement Mesh)**

#### Skenario Klien
Klien adalah sebuah konsorsium perbankan multinasional terikat regulasi PCI-DSS 4.0 dan yurisdiksi keuangan ketat yang melarang penggunaan cloud publik secara langsung untuk data transaksi nasabah. Sistem inti mereka mengandalkan kombinasi IBM DB2 Mainframe (transaksi warisan) dan kluster internal Apache Kafka.

Tantangan FDE: Klien membeli produk analitik real-time enterprise berbasis core platform modern milik perusahaan Anda. Core platform Anda dirancang berbasis cloud-native Kubernetes, gRPC streaming, dan Trino federated query.

#### Persyaratan Teknis Capstone
1. **Air-Gapped Deployment**:
   * Deploy kluster Kubernetes berbasis RKE2 atau K3s secara penuh tanpa koneksi keluar (zero egress access).
   * Rancang mekanisme transfer image kontainer, bagan Helm, dan dependensi biner menggunakan registry lokal berbasis Zot/Harbor yang terdistribusi secara luring.
2. **Legacy Interoperability Pipeline**:
   * Bangun integrasi streaming non-blocking yang menyerap data dummy IBM DB2/COBOL records ke platform dengan latensi end-to-end $\le 100\text{ ms}$ untuk $\ge 15.000\text{ TPS}$.
   * Eksekusi parsing skema dinamis dan sanitasi identitas pribadi (PII anonymization) saat proses ingestion berlangsung.
3. **Zero-Trust Security Mesh & Dynamic ABAC**:
   * Konfigurasi Istio Service Mesh dengan mTLS terisolasi, enkripsi strict SPIFFE/SPIRE.
   * Tulis modul autorisasi berbasis Open Policy Agent (OPA) untuk mencegah analis tingkat junior melihat field transaksi sensitif lintas yurisdiksi.
4. **Resilience & Fault Inoculation**:
   * Sistem harus mampu bertahan dalam skenario simulasi pemutusan 50% node worker secara mendadak tanpa kehilangan data (*zero data loss*, RPO = 0) dan RTO $< 30\text{ detik}$.
5. **Upstream PR Proposal**:
   * Tulis sebuah Pull Request (PR) arsitektural lengkap beserta RFC ke repositori produk inti internal, mengusulkan generalisasi driver integrasi legacy yang telah dibuat agar dapat digunakan pada klien perbankan berikutnya.

#### Rubrik Evaluasi & Standar Kelulusan Capstone
| Kategori Evaluasi | Parameter Pengujian | Bobot |
| :--- | :--- | :--- |
| **Arsitektur & Air-gap Isolation** | Kelancaran instalasi dari kondisi cold-start, nihil kebocoran paket keluar (*zero unauthorized outbound packets* via tcpdump/eBPF check). | 25% |
| **Keandalan Integrasi & Data Pipe** | Latensi $\le 100\text{ ms}$ pada peak load $15\text{k TPS}$, tidak ada memory leak pada konektor selama 4 jam continuous load. | 25% |
| **Kepatuhan Keamanan & RBAC/ABAC** | Validasi aturan OPA, sertifikat mTLS tersirkulasi otomatis, audit logging compliance SOC2/PCI-DSS lolos pengujian penetrasi. | 20% |
| **Observabilitas & Triage Lapangan** | Dashboard OpenTelemetry/Grafana berfungsi off-grid, kesiapan runbook, respon triage error sintetis di bawah 15 menit. | 15% |
| **Kualitas Upstream Platform & TRD** | Kebersihan abstraksi kode modul integrasi, kelengkapan Technical Requirement Document (TRD), dan presentasi eksekutif. | 15% |

---

## 5. Prasyarat Kursus (Prerequisites)

Untuk menyelesaikan seluruh kurikulum ini tanpa hambatan teknis yang menghalangi, siswa diharapkan memiliki pemahaman dasar:
1. **Bahasa Pemrograman**: Mahir minimal salah satu bahasa sistem modern (Go, Rust, C++) dan satu bahasa skrip/data (Python).
2. **Sistem Terdistribusi**: Paham mekanisme konsensus (Raft/Paxos), isolasi database (ACID levels), CAP theorem, dan IPC (gRPC/Protobuf).
3. **Linux Internals**: Paham navigasi terminal, interaksi file descriptor, namespace, cgroups, dan dasar manipulasi `iptables`/jaringan.
4. **Containerization**: Paham dasar Docker dan arsitektur kontrol Kubernetes (Pod, Deployment, StatefulSet, DaemonSet, CRD).