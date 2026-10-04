# Kurikulum Terakreditasi: Site Reliability Engineering (SRE) Enterprise

Selamat datang di repositori resmi kurikulum **Site Reliability Engineering (SRE)**. Kurikulum ini dirancang setara dengan standar operasional rekayasa keandalan sistem pada perusahaan skala global (Google, Netflix, Meta). Panduan ini mentransformasi paradigma operasional konvensional menjadi pendekatan rekayasa perangkat lunak (*software-first approach*) untuk mengelola sistem terdistribusi berskala masif, heterogen, dan mission-critical.

---

## 1. Course Overview & Mindset

### Filosofi SRE
Site Reliability Engineering adalah disiplin rekayasa yang lahir ketika operasional sistem diperlakukan sebagai problem perangkat lunak (*what happens when you ask a software engineer to design an operations team*). SRE tidak berfokus pada pencegahan kegagalan absolut (karena kegagalan pada sistem terdistribusi berskala besar adalah keniscayaan probabilistik), melainkan mengelola batas toleransi kegagalan melalui kalkulasi risiko kuantitatif berbasis data.

### Prinsip Inti SRE
1. **Embracing Risk & Error Budgets**: Reliabilitas 100% adalah target yang salah dan tidak ekonomis. Error budget adalah instrumen pengatur kecepatan inovasi vs stabilitas.
2. **Eliminasi Toil Secara Agresif**: Pekerjaan berulang, manual, terautomasi-able, dan tidak memiliki nilai jangka panjang (*toil*) dibatasi maksimal 50% dari waktu rekayasa. Sisa waktu wajib didedikasikan untuk rekayasa sistem (*engineering projects*).
3. **Observabilitas Holistik, Bukan Sekadar Monitoring**: Mengetahui kondisi internal sistem secara *real-time* melalui kombinasi telemetri terpadu (*metrics, distributed traces, structured logs, and continuous profiles*) berbasis open standards (OpenTelemetry).
4. **Blameless Culture & Psychological Safety**: Insiden adalah kegagalan sistem dan desain arsitektur, bukan kelalaian individu. Setiap kegagalan dievaluasi secara konstruktif melalui *Blameless Post-Mortem*.
5. **Simplicity as a Prerequisite for Reliability**: Kompleksitas adalah musuh utama keandalan. Arsitektur harus dipertahankan seminimal dan seringkas mungkin untuk mempersempit *blast radius*.

### Target Audiens & Prasyarat
* **Target Peserta**: Platform Engineers, DevOps Engineers, Senior Backend Engineers, dan Systems/Infrastructure Architects yang ingin menguasai arsitektur dan operasional keandalan tingkat lanjut.
* **Prasyarat Wajib**:
  * Penguasaan bahasa pemrograman sistem (Go, Python, atau Rust).
  * Pemahaman mendalam terkait Linux OS (POSIX syscalls, network stack, I/O model).
  * Familiaritas dengan konsep jaringan komputer (TCP/IP, HTTP/2/3, DNS, TLS).
  * Pengalaman operasional praktis dengan containerization (Docker) dan orkestrasi dasar (Kubernetes).

---

## 2. Learning Roadmap

```plaintext
Site Reliability Engineering (SRE) Master Curriculum
│
├── [Bab 01] Fondasi Paradigma & Prinsip Inti SRE
│   ├── Filosofi, Budaya, dan Metrik SRE
│   ├── Dekonstruksi dan Eliminasi Toil
│   └── Model Respon dan Manajemen Risiko Terdistribusi
│
├── [Bab 02] Arsitektur Sistem Operasi Tingkat Rendah & Linux Internals
│   ├── Kernel Architecture, System Calls, dan I/O Subsystems
│   ├── Linux Namespaces, Cgroups v2, dan Container Runtimes
│   └── Instrumentasi Inti Linux dengan eBPF dan Tracepoints
│
├── [Bab 03] Jaringan Sistem Terdistribusi & Protokol Keandalan
│   ├── Deep-Dive TCP/IP, Socket Lifecycle, dan Tuning Kernel
│   ├── Arsitektur Edge, DNS, BGP, Anycast, dan Load Balancing
│   └── Service Mesh, Envoy Proxy, dan Kontrol Komunikasi mTLS
│
├── [Bab 04] Service Level Engineering: SLI, SLO, SLA, & Error Budget
│   ├── Perancangan Indikator (SLI) Kuantitatif yang Akurat
│   ├── Formulasi Target (SLO), SLA, dan Kontrak Keandalan
│   └── Manajemen Error Budget, Burn-Rate Alerting, dan Kebijakan Rilis
│
├── [Bab 05] Observabilitas Sistem Mendalam (Deep Observability)
│   ├── Arsitektur Telemetri Terpadu dengan OpenTelemetry (OTel)
│   ├── Metrik Skala Masif dengan Prometheus, Thanos, dan Cortex
│   └── Distributed Tracing Lanjutan dan Continuous In-Production Profiling
│
├── [Bab 06] Incident Lifecycle, On-Call, & Blameless Post-Mortem
│   ├── Incident Command System (ICS) dan Desain On-Call Rotations
│   ├── Paging Architecture, Triage Cepat, dan Mitigasi Insiden
│   └── Analisis Akar Masalah (RCA) dan Blameless Post-Mortem Engine
│
├── [Bab 07] Container Orchestration & Resilient Kubernetes Operations
│   ├── Pod Lifecycle, Admission Webhooks, dan Custom Controllers
│   ├── Resource Management, Scheduling Topologies, dan Priority Classes
│   └── Autoscaling Skala Masif (KEDA, HPA/VPA, Karpenter) & Node Stability
│
├── [Bab 08] Otomasi, Infrastructure as Code, & GitOps Engineering
│   ├── Deklaratif Infrastruktur Bebas Drift (Terraform, Crossplane)
│   ├── GitOps Lifecycle, Automated Rollbacks, dan ArgoCD Operations
│   └── Self-Healing Infrastructure dan Automated Remediation Loop
│
├── [Bab 09] Capacity Planning, Performance Engineering, & Chaos Testing
│   ├── Queueing Theory, Pemodelan Kapasitas, dan Saturation Analysis
│   ├── Performance Profiling, Kernel Parameter Tuning, dan Benchmarking
│   └── Chaos Engineering: Fault Injection, Network Partition, dan GameDays
│
└── [Bab 10] Security Reliability Engineering (SRE-Sec) & Disaster Recovery
    ├── Mitigasi Blast Radius, Zero Trust, dan Identity-Based Access
    ├── Multi-Region Active-Active Architectures & Failover Mechanics
    └── Orchestrated Disaster Recovery Drills dan Data Resilience Verification
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Paradigma & Prinsip Inti SRE](01-fondasi-paradigma-dan-prinsip-inti-sre/README.md)
*Membangun pola pikir operasional matematis dan budaya rekayasa yang berfokus pada software-driven operations.*
* [Modul 01: Filosofi, Budaya, dan Metrik SRE](01-fondasi-paradigma-dan-prinsip-inti-sre/01-filosofi-budaya-dan-metrik-sre.md) — Dekonstruksi peran SRE vs DevOps, pilar Google SRE, dan batas toleransi kegagalan.
* [Modul 02: Dekonstruksi dan Eliminasi Toil](01-fondasi-paradigma-dan-prinsip-inti-sre/02-dekonstruksi-dan-eliminasi-toil.md) — Mengidentifikasi, mengukur, dan mengeliminasi toil melalui kalkulasi batas 50% waktu rekayasa.
* [Modul 03: Model Respon dan Manajemen Risiko Terdistribusi](01-fondasi-paradigma-dan-prinsip-inti-sre/03-model-respon-dan-manajemen-risiko-terdistribusi.md) — Mengukur biaya downtime, kalkulasi ketersediaan sistem probabilistik (*nines of availability*), dan limitasi ekonomi reliabilitas.

### [Bab 02: Arsitektur Sistem Operasi Tingkat Rendah & Linux Internals](02-arsitektur-sistem-operasi-dan-linux-internals/README.md)
*Membedah interaksi aplikasi dengan kernel Linux, penanganan resource hardware, dan visibilitas mendalam tingkat OS.*
* [Modul 01: Kernel Architecture, System Calls, dan I/O Subsystems](02-arsitektur-sistem-operasi-dan-linux-internals/01-kernel-architecture-system-calls-dan-io-subsystems.md) — Interupsi, Virtual File System (VFS), epoll/io_uring, disk scheduler, dan page cache.
* [Modul 02: Linux Namespaces, Cgroups v2, dan Container Runtimes](02-arsitektur-sistem-operasi-dan-linux-internals/02-linux-namespaces-cgroups-v2-dan-container-runtimes.md) — Isolasi komputasi mendalam, Memory OOM-killer, CPU throttles via CFS, dan OCI specifications.
* [Modul 03: Instrumentasi Inti Linux dengan eBPF dan Tracepoints](02-arsitektur-sistem-operasi-dan-linux-internals/03-instrumentasi-inti-linux-dengan-ebpf-dan-tracepoints.md) — Kernel observability tanpa overhead, kprobes/uprobes, dan analisa latensi menggunakan BCC serta bpftrace.

### [Bab 03: Jaringan Sistem Terdistribusi & Protokol Keandalan](03-jaringan-sistem-terdistribusi-dan-protokol-keandalan/README.md)
*Menganalisis dependensi jaringan, latensi transmisi, dan mitigasi bottleneck transmisi pada sistem hyperscale.*
* [Modul 01: Deep-Dive TCP/IP, Socket Lifecycle, dan Tuning Kernel](03-jaringan-sistem-terdistribusi-dan-protokol-keandalan/01-deep-dive-tcp-ip-socket-lifecycle-dan-tuning-kernel.md) — Handshake, TCP slow-start, window scaling, TIME_WAIT socket exhaustion, SYN flood defense, dan buffer tuning.
* [Modul 02: Arsitektur Edge, DNS, BGP, Anycast, dan Load Balancing](03-jaringan-sistem-terdistribusi-dan-protokol-keandalan/02-arsitektur-edge-dns-bgp-anycast-dan-load-balancing.md) — Routing Anycast, integrasi Authoritative DNS, Layer 4 (Maglev/IPVS) vs Layer 7 load balancing.
* [Modul 03: Service Mesh, Envoy Proxy, dan Kontrol Komunikasi mTLS](03-jaringan-sistem-terdistribusi-dan-protokol-keandalan/03-service-mesh-envoy-proxy-dan-kontrol-komunikasi-mtls.md) — Manajemen koneksi sidecar, zero-trust cryptographic mTLS, dynamic service discovery, circuit breaking, dan outlier detection.

### [Bab 04: Service Level Engineering: SLI, SLO, SLA, & Error Budget](04-service-level-engineering-sli-slo-sla-error-budget/README.md)
*Standardisasi kuantifikasi keandalan perangkat lunak menggunakan indikator yang berorientasi langsung pada pengalaman pengguna.*
* [Modul 01: Perancangan Indikator (SLI) Kuantitatif yang Akurat](04-service-level-engineering-sli-slo-sla-error-budget/01-perancangan-indikator-sli-kuantitatif-yang-akurat.md) — Good events over valid events, user journeys, latensi terdistribusi, evaluasi throughput, dan synthetic monitoring.
* [Modul 02: Formulasi Target (SLO), SLA, dan Kontrak Keandalan](04-service-level-engineering-sli-slo-sla-error-budget/02-formulasi-target-slo-sla-dan-kontrak-keandalan.md) — Menentukan ambang batas SLO pragmatis, window rollups (rolling vs calendar-aligned), dan konsekuensi kontraktual legal SLA.
* [Modul 03: Manajemen Error Budget, Burn-Rate Alerting, dan Kebijakan Rilis](04-service-level-engineering-sli-slo-sla-error-budget/03-manajemen-error-budget-burn-rate-alerting-dan-kebijakan-rilis.md) — Kalkulasi multi-window multi-burn-rate alerts, freeze policy deployment, dan gatekeeping deployment otomatis.

### [Bab 05: Observabilitas Sistem Mendalam (Deep Observability)](05-observabilitas-sistem-mendalam/README.md)
*Membangun arsitektur telemetri terpadu untuk mengekstrak kondisi internal sistem secara presisi tanpa membebani runtime.*
* [Modul 01: Arsitektur Telemetri Terpadu dengan OpenTelemetry (OTel)](05-observabilitas-sistem-mendalam/01-arsitektur-telemetri-terpadu-dengan-opentelemetry.md) — Standarisasi OTLP, instrumen collector agent vs gateway, sampling tail-based vs head-based.
* [Modul 02: Metrik Skala Masif dengan Prometheus, Thanos, dan Cortex](05-observabilitas-sistem-mendalam/02-metrik-skala-masif-dengan-prometheus-thanos-dan-cortex.md) — TSDB architecture, compaction, federasi global, query evaluation multitenancy, dan long-term storage mechanics.
* [Modul 03: Distributed Tracing Lanjutan dan Continuous In-Production Profiling](05-observabilitas-sistem-mendalam/03-distributed-tracing-dan-continuous-profiling.md) — Propagasi konteks W3C, Jaeger/Tempo, flame graphs, dan profiling real-time di lingkungan produksi (Parca/Pyroscope).

### [Bab 06: Incident Lifecycle, On-Call, & Blameless Post-Mortem](06-incident-lifecycle-on-call-dan-blameless-post-mortem/README.md)
*Membangun tata kelola penanganan degradasi sistem, protokol eskalasi darurat, dan pembelajaran terstruktur dari insiden.*
* [Modul 01: Incident Command System (ICS) dan Desain On-Call Rotations](06-incident-lifecycle-on-call-dan-blameless-post-mortem/01-incident-command-system-dan-desain-on-call.md) — Peran Incident Commander, Scribe, Communications Lead, pencegahan burnout, serta desain rotasi multi-timezone.
* [Modul 02: Paging Architecture, Triage Cepat, dan Mitigasi Insiden](06-incident-lifecycle-on-call-dan-blameless-post-mortem/02-paging-architecture-triage-dan-mitigasi-insiden.md) — Alert de-duplication, automated enrichment runbooks, teknik isolasi parsial (drain, degrade, drop), dan operational triage protocol.
* [Modul 03: Analisis Akar Masalah (RCA) dan Blameless Post-Mortem Engine](06-incident-lifecycle-on-call-dan-blameless-post-mortem/03-analisis-akar-masalah-dan-blameless-post-mortem.md) — 5 Whys analysis yang efektif, identifikasi *systemic factors*, penulisan *actionable prevention items*, dan review kepatuhan perbaikan.

### [Bab 07: Container Orchestration & Resilient Kubernetes Operations](07-container-orchestration-dan-resilient-kubernetes-operations/README.md)
*Mendesain, mengonfigurasi, dan mempertahankan klaster Kubernetes pada beban kerja ekstrem agar tahan terhadap kerusakan parsial.*
* [Modul 01: Pod Lifecycle, Admission Webhooks, dan Custom Controllers](07-container-orchestration-dan-resilient-kubernetes-operations/01-pod-lifecycle-admission-webhooks-custom-controllers.md) — Graceful shutdown (SIGTERM/SIGKILL), pre-stop hooks, Mutating/Validating Webhooks, dan operator reconciliation loops.
* [Modul 02: Resource Management, Scheduling Topologies, dan Priority Classes](07-container-orchestration-dan-resilient-kubernetes-operations/02-resource-management-scheduling-dan-priority-classes.md) — Quality of Service (QoS), affinity/anti-affinity, Pod Disruption Budgets (PDB), dan Topology Spread Constraints.
* [Modul 03: Autoscaling Skala Masif (KEDA, HPA/VPA, Karpenter) & Node Stability](07-container-orchestration-dan-resilient-kubernetes-operations/03-autoscaling-skala-masif-dan-node-stability.md) — Event-driven scaling, desync vCPU/RAM spikes, optimasi cold-start provision node via Karpenter, dan node eviction handling.

### [Bab 08: Otomasi, Infrastructure as Code, & GitOps Engineering](08-otomasi-iac-dan-gitops-engineering/README.md)
*Mengelola siklus hidup infrastruktur dan konfigurasi mutlak melalui kode, audit trail otomatis, dan platform deklaratif.*
* [Modul 01: Deklaratif Infrastruktur Bebas Drift (Terraform, Crossplane)](08-otomasi-iac-dan-gitops-engineering/01-deklaratif-infrastruktur-bebas-drift.md) — Immutability, state lock engines, automated drift detection, reconciliation patterns, dan resource lifecycle constraints.
* [Modul 02: GitOps Lifecycle, Automated Rollbacks, dan ArgoCD Operations](08-otomasi-iac-dan-gitops-engineering/02-gitops-lifecycle-automated-rollbacks-argocd.md) — Progressive delivery (canary, blue-green), automated rollbacks berbasis evaluasi metrik waktu nyata (Argo Rollouts).
* [Modul 03: Self-Healing Infrastructure dan Automated Remediation Loop](08-otomasi-iac-dan-gitops-engineering/03-self-healing-infrastructure-dan-automated-remediation.md) — Alert-driven remediation pipelines, automated dead node replacements, leak detection, dan automated network link re-routing.

### [Bab 09: Capacity Planning, Performance Engineering, & Chaos Testing](09-capacity-planning-performance-dan-chaos-testing/README.md)
*Mengevaluasi batas maksimal arsitektur sistem menggunakan permodelan matematika, benchmarking ketat, dan injeksi kegagalan terencana.*
* [Modul 01: Queueing Theory, Pemodelan Kapasitas, dan Saturation Analysis](09-capacity-planning-performance-dan-chaos-testing/01-queueing-theory-pemodelan-kapasitas-saturation-analysis.md) — Little's Law, Erlang models, USE method (Utilization, Saturation, Errors), and predictive headroom budgeting.
* [Modul 02: Performance Profiling, Kernel Parameter Tuning, dan Benchmarking](09-capacity-planning-performance-dan-chaos-testing/02-performance-profiling-tuning-dan-benchmarking.md) — Load testing skala masif, profiling memory allocs/garbage collection bottlenecks, sysctl optimization, dan context-switch analysis.
* [Modul 03: Chaos Engineering: Fault Injection, Network Partition, dan GameDays](09-capacity-planning-performance-dan-chaos-testing/03-chaos-engineering-fault-injection-dan-gamedays.md) — Injeksi paket drop, latensi artifisial, split-brain scenario validation, Chaos Mesh/LitmusChaos, dan orkestrasi latihan GameDay enterprise.

### [Bab 10: Security Reliability Engineering (SRE-Sec) & Disaster Recovery](10-security-reliability-engineering-dan-disaster-recovery/README.md)
*Menjamin keberlanjutan bisnis dari ancaman serangan eksternal masif, kerentanan sistemik, hingga kehancuran infrastruktur total.*
* [Modul 01: Mitigasi Blast Radius, Zero Trust, dan Identity-Based Access](10-security-reliability-engineering-dan-disaster-recovery/01-mitigasi-blast-radius-zero-trust-identity-access.md) — Network segmentation, Short-lived credential rotation, SPIFFE/SPIRE, least privilege IAM policies, dan automated compromise quarantine.
* [Modul 02: Multi-Region Active-Active Architectures & Failover Mechanics](10-security-reliability-engineering-dan-disaster-recovery/02-multi-region-active-active-dan-failover-mechanics.md) — Database replication topology (CockroachDB/Spanner/Global Aurora), cross-region data consensus, distributed lock contention, dan deterministic global traffic failover.
* [Modul 03: Orchestrated Disaster Recovery Drills dan Data Resilience Verification](10-security-reliability-engineering-dan-disaster-recovery/03-disaster-recovery-drills-dan-resilience-verification.md) — Validasi RTO/RPO matematis, automated snapshot cold-recovery verification, split-datacenter drills, dan data corruption recovery pipelines.

---

## 4. Enterprise Capstone Project

### Judul Proyek
**Global Financial Ledger: High-Throughput, Multi-Region Fault-Tolerant Platform (Tier-0 Infrastructure)**

### Deskripsi Skenario
Peserta ditugaskan merancang, membangun, mengotomasi, dan memvalidasi keandalan infrastruktur backend transaksi finansial global (*Payment Processing & Ledger Platform*) yang melayani **100.000 Request Per Second (RPS)**. Platform wajib menjamin ketersediaan data secara konsisten (ACID compliant) di dua region cloud berbeda (Active-Active), toleran terhadap kehilangan satu region penuh secara tiba-tiba tanpa kehilangan data finansial (*Zero Data Loss*), serta memenuhi target keandalan yang ketat.

### Spesifikasi Teknis & Persyaratan Arsitektur
1. **Target SLA/SLO**:
   * **Availability**: 99.99% sukses dari total transaksi dalam periode evaluasi 30 hari.
   * **Latency**: 99th percentile (p99) latency transaksi < 120ms; 95th percentile (p95) < 40ms.
   * **RPO (Recovery Point Objective)**: 0 detik (tidak ada transaksi sukses yang hilang saat failover).
   * **RTO (Recovery Time Objective)**: < 30 detik untuk full-automated failover antar region.
2. **Komponen Arsitektur Inti**:
   * **Compute**: Multi-cluster Kubernetes didistribusikan di minimal dua AWS/GCP regions dengan Karpenter auto-provisioning.
   * **Routing & Ingress**: Anycast IP / Cloud Global Accelerator diteruskan ke Envoy-based Gateway Fabric dengan integrasi Service Mesh (mTLS + Circuit Breaking).
   * **Database Tier**: Distributed ACID Database (misal: CockroachDB atau TiDB) dengan topology multi-region cluster.
   * **Observability**: OpenTelemetry collector pipeline memancarkan traces ke Tempo/Jaeger, metrik ke Prometheus-Thanos global federation, dan log ingestion berbasis Loki.
   * **Reliability Controls**: Multi-burn rate alerting, automated progressive delivery via Argo Rollouts (integrasi auto-rollback berbasis SLI drop), dan self-healing drift detection.

### Skenario Uji Gangguan (*The Final Gauntlet - Chaos Testing*)
Platform yang telah ter-deploy akan diuji dengan beban puncak lalu dieksekusi skenario kegagalan simultan berikut oleh asesor:
1. **Injeksi Latensi & Packet Loss**: Latensi tambahan sebesar 250ms dan 15% drop-packet diinjeksi pada link antar-region selama 15 menit.
2. **Simulasi Region Outage (Hard Failure)**: Pemutusan mendadak (blackhole routing) pada Region Primer saat lalu lintas beban transaksi mencapai 100.000 RPS.
3. **Misconfiguration Rollout**: Deployment versi aplikasi baru yang memiliki memori leak disengaja dan degradasi p99 latensi 500% ke lingkungan live.

### Rubrik Penilaian Capstone

| Kategori Evaluasi | Bobot | Parameter Keberhasilan |
| :--- | :---: | :--- |
| **SLO & Error Budget Design** | 20% | Formulasi SLI/SLO mencerminkan realita sistem; skema *multi-window multi-burn-rate alerting* terkonfigurasi tanpa memicu alert fatigue; automated deployment-freeze berfungsi saat budget habis. |
| **System Resiliency & Failover** | 25% | Failover multi-region berjalan otomatis < 30 detik (RTO); nol transaksi valid yang hilang (RPO = 0); circuit-breaker mencegah cascading failure ke database ledger. |
| **Deep Observability Implementation** | 20% | End-to-end tracing 100% terkoneksi dari edge gateway ke node storage; metrik dan telemetry pipelines tidak menjadi bottleneck saat peak traffic; continuous profiling aktif di target pods. |
| **Chaos & Blast Radius Containment** | 20% | Platform mampu melewati *The Final Gauntlet* tanpa menyebabkan ketersediaan bulanan tereduksi di bawah 99.99%; Canary deployment via Argo Rollouts sukses melakukan rollback otomatis. |
| **Blameless Incident Management** | 15% | Dokumentasi insiden (Post-Mortem) komprehensif, penyajian timeline yang akurat hingga resolusi microsecond, identifikasi *systemic factors* yang valid, serta ketiadaan *human blame language*. |

---
*Kurikulum ini diverifikasi dan dikelola secara berkelanjutan oleh Principal Reliability Architects. Gunakan sub-modul navigasi di atas untuk memulai pembelajaran terstruktur.*