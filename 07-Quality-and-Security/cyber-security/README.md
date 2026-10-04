# Enterprise Cybersecurity Engineering & Defense-in-Depth Architecture

Kurikulum komprehensif ini dirancang berdasarkan standar kurikulum resmi [roadmap.sh/cyber-security](https://roadmap.sh/cyber-security). Program ini membedah ekosistem keamanan siber mulai dari tingkat fundamental sistem operasi dan protokol transmisi hingga post-exploitation, rekayasa deteksi SOC (*Detection Engineering*), arsitektur cloud hybrid nir-kepercayaan (*Zero Trust*), serta kepatuhan tata kelola risiko enterprise.

---

## 1. Course Overview & Mindset

### Paradigma Keamanan
Keamanan siber tingkat enterprise tidak dibangun di atas asumsi bahwa sistem tidak dapat ditembus, melainkan pada prinsip **"Assume Breach"** dan implementasi **Defense-in-Depth**. Pendekatan kurikulum ini mengintegrasikan metodologi ofensif (*Red Team*) dan defensif (*Blue Team*) secara proporsional (*Purple Teaming*).

### Filosofi Rekayasa
* **Mekanika Tingkat Rendah (*Under-the-Hood*):** Pemahaman mendalam tentang *memory management*, struktur kernel, paket mentah (RFC), dan kriptografi primitif mendahului penggunaan perkakas (*tools*).
* **Automasi dan Skalabilitas:** Penanganan insiden dan deteksi ancaman harus dapat diotomasi menggunakan format terstruktur (Sigma, YARA, SOAR) serta pipeline terintegrasi.
* **Resiliensi Berkelanjutan:** Sasaran akhir bukan sekadar pencegahan perimeter, melainkan peminimalan *blast radius*, persistensi visibilitas telemetri, dan percepatan *Mean Time to Detect* (MTTD) serta *Mean Time to Remediate* (MTTR).

---

## 2. Learning Roadmap

```
CYBER SECURITY CURRICULUM
│
├── BAB 01: Foundations & Systems Architecture
│   ├── OS Internals, Syscalls, & Memory Management
│   ├── Networking Deep Dive & Packet Analysis
│   └── Cryptographic Engineering & PKI
│
├── BAB 02: Network Security & Traffic Analysis
│   ├── Perimeter Defense, IDS/IPS, & Micro-segmentation
│   ├── Network Forensics & Deep Packet Inspection
│   └── Zero Trust Network Architecture (ZTNA)
│
├── BAB 03: Identity, Access & Host Hardening
│   ├── Active Directory Architecture & Kerberos Mechanics
│   ├── IAM, PAM, & Privilege Escalation Mitigation
│   └── Linux/Windows Enterprise Baseline Hardening
│
├── BAB 04: Vulnerability Management & Exploit Fundamentals
│   ├── Vulnerability Lifecycle & CVSS v4.0 Scrutiny
│   ├── Memory Corruption, Buffer Overflows, & Binaries
│   └── Reverse Engineering & Static/Dynamic Code Auditing
│
├── BAB 05: Web Application & API Security
│   ├── Modern OWASP Top 10 & Business Logic Exploitation
│   ├── API Security, OAuth2, OpenID Connect, & JWT Flaws
│   └── DevSecOps: SAST, DAST, SCA, & CI/CD Security
│
├── BAB 06: Threat Intelligence & Incident Response
│   ├── Cyber Threat Intelligence (CTI) & MITRE ATT&CK
│   ├── Host & Network Incident Response Playbooks
│   └── Digital Forensics & Volatile Memory Analysis
│
├── BAB 07: Offensive Security & Penetration Testing
│   ├── Advanced Reconnaissance & Weaponization
│   ├── Post-Exploitation, Lateral Movement, & C2
│   └── Defense Evasion & EDR Bypassing Techniques
│
├── BAB 08: Cloud, Container & Virtualization Security
│   ├── AWS/Azure IAM Security & Cloud Trail Telemetry
│   ├── Container Isolation, Docker, & Kubernetes Hardening
│   └── Infrastructure as Code (IaC) Scanning & CSPM
│
├── BAB 09: Governance, Risk, Compliance & SecOps
│   ├── SOC Architecture, SIEM Engineering, & Telemetry Pipelines
│   ├── Risk Assessment Frameworks (NIST CSF, ISO 27001)
│   └── Business Continuity & Disaster Recovery (BC/DR)
│
└── BAB 10: Advanced Detection Engineering & Enterprise Capstone
    ├── Detection-as-Code with Sigma & YARA Rules
    ├── Adversary Emulation using Atomic Red Team
    └── Capstone: Enterprise Multi-Tier Hybrid Intrusion & Defense
```

---

## 3. Navigasi Silabus

### [Bab 01: Foundations & Systems Architecture](./bab-01-foundations-systems-architecture/)
Membedah arsitektur internal sistem komputasi modern dan struktur komunikasi jaringan pada tingkat paling mendasar.
* [Modul 01: OS Internals, Syscalls, & Memory Management](./bab-01-foundations-systems-architecture/01-os-internals-syscalls-memory.md)
* [Modul 02: Networking Deep Dive & Packet Analysis](./bab-01-foundations-systems-architecture/02-networking-deep-dive-packet-analysis.md)
* [Modul 03: Applied Cryptographic Engineering & PKI](./bab-01-foundations-systems-architecture/03-cryptographic-engineering-pki.md)

### [Bab 02: Network Security & Traffic Analysis](./bab-02-network-security-traffic-analysis/)
Penerapan kontrol lalu lintas jaringan berlapis, inspeksi paket mendalam, dan eliminasi model perimeter tradisional.
* [Modul 01: Perimeter Defense, Next-Gen IDS/IPS, & Micro-segmentation](./bab-02-network-security-traffic-analysis/01-perimeter-defense-ids-ips-segmentation.md)
* [Modul 02: Network Forensics, Zeek, & Deep Packet Inspection](./bab-02-network-security-traffic-analysis/02-network-forensics-zeek-dpi.md)
* [Modul 03: Zero Trust Network Architecture (ZTNA) & Software-Defined Perimeters](./bab-02-network-security-traffic-analysis/03-ztna-software-defined-perimeter.md)

### [Bab 03: Identity, Access & Host Hardening](./bab-03-identity-access-host-hardening/)
Pengamanan infrastruktur autentikasi terpusat dan standardisasi konfigurasi pertahanan host enterprise.
* [Modul 01: Active Directory Architecture, Kerberos, & Forests](./bab-03-identity-access-host-hardening/01-active-directory-kerberos-architecture.md)
* [Modul 02: Identity Governance, PAM, & Privilege Management](./bab-03-identity-access-host-hardening/02-identity-governance-pam.md)
* [Modul 03: Linux & Windows Baseline Hardening via CIS Benchmarks](./bab-03-identity-access-host-hardening/03-os-hardening-cis-benchmarks.md)

### [Bab 04: Vulnerability Management & Exploit Fundamentals](./bab-04-vulnerability-management-exploit-fundamentals/)
Pengelolaan siklus kerentanan enterprise dan mekanisme eksploitasi berbasis biner dan sistem.
* [Modul 01: Vulnerability Prioritization Lifecycle & CVSS v4.0 Framework](./bab-04-vulnerability-management-exploit-fundamentals/01-vulnerability-lifecycle-cvss.md)
* [Modul 02: Memory Corruption, Stack/Heap Overflows, & Shellcoding](./bab-04-vulnerability-management-exploit-fundamentals/02-memory-corruption-overflows.md)
* [Modul 03: Reverse Engineering & Binary Decompilation Fundamentals](./bab-04-vulnerability-management-exploit-fundamentals/03-reverse-engineering-binaries.md)

### [Bab 05: Web Application & API Security](./bab-05-web-app-api-security/)
Pengujian penetrasi aplikasi web tingkat lanjut, sanitasi input modern, dan orkestrasi keamanan siklus perangkat lunak.
* [Modul 01: Advanced OWASP Top 10 & Complex Business Logic Flaws](./bab-05-web-app-api-security/01-advanced-owasp-top-10.md)
* [Modul 02: REST/GraphQL API Security, OAuth2, & Token Vulnerabilities](./bab-05-web-app-api-security/02-api-security-oauth2-jwt.md)
* [Modul 03: DevSecOps Pipelines: SAST, DAST, SCA, & Policy-as-Code](./bab-05-web-app-api-security/03-devsecops-sast-dast-sca.md)

### [Bab 06: Threat Intelligence & Incident Response](./bab-06-threat-intelligence-incident-response/)
Operasi mitigasi serangan terarah, pemanfaatan data intelijen ancaman, dan investigasi artefak forensik pascainsiden.
* [Modul 01: Cyber Threat Intelligence (CTI), STIX/TAXII, & MITRE ATT&CK Mapping](./bab-06-threat-intelligence-incident-response/01-cti-stix-taxii-mitre.md)
* [Modul 02: Incident Response Playbooks & Enterprise Triage Automation](./bab-06-threat-intelligence-incident-response/02-ir-playbooks-enterprise-triage.md)
* [Modul 03: Digital Forensics: Volatile Memory & Disk Artifact Carving](./bab-06-threat-intelligence-incident-response/03-dfir-memory-disk-artifacts.md)

### [Bab 07: Offensive Security & Penetration Testing](./bab-07-offensive-security-pentesting/)
Mekanika operasional tim penyerang (*adversary emulation*), pivot lateral melalui jaringan terisolasi, dan teknik penghindaran deteksi.
* [Modul 01: Weaponization, Phishing Payloads, & Initial Access Vectors](./bab-07-offensive-security-pentesting/01-weaponization-initial-access.md)
* [Modul 02: Post-Exploitation, Credential Dumping, & Lateral Movement](./bab-07-offensive-security-pentesting/02-post-exploitation-lateral-movement.md)
* [Modul 03: Defense Evasion: Obfuscation, Living-off-the-Land, & EDR Bypass](./bab-07-offensive-security-pentesting/03-evasion-techniques-edr-bypass.md)

### [Bab 08: Cloud, Container & Virtualization Security](./bab-08-cloud-container-virtualization-security/)
Keamanan ekosistem native cloud, isolasi container runtime, dan audit kepatuhan konfigurasi *cloud-scale*.
* [Modul 01: AWS/Azure Multi-Account Security Architecture & IAM Boundaries](./bab-08-cloud-container-virtualization-security/01-cloud-multi-account-iam-security.md)
* [Modul 02: Container Isolation, Docker Daemon, & Kubernetes Cluster Hardening](./bab-08-cloud-container-virtualization-security/02-container-kubernetes-hardening.md)
* [Modul 03: Cloud Posture Management (CSPM) & IaC Vulnerability Scanning](./bab-08-cloud-container-virtualization-security/03-cspm-iac-security-scanning.md)

### [Bab 09: Governance, Risk, Compliance & SecOps](./bab-09-governance-risk-compliance-secops/)
Tata kelola operasional Security Operations Center (SOC), standardisasi audit internasional, dan kontinuitas bisnis enterprise.
* [Modul 01: Enterprise SOC Architecture, SIEM Optimization, & Telemetry Pipelines](./bab-09-governance-risk-compliance-secops/01-soc-architecture-siem-telemetry.md)
* [Modul 02: GRC Implementation: NIST CSF 2.0, ISO/IEC 27001, & PCI-DSS](./bab-09-governance-risk-compliance-secops/02-grc-frameworks-nist-iso.md)
* [Modul 03: Disaster Recovery, Ransomware Playbooks, & BCP Verification](./bab-09-governance-risk-compliance-secops/03-disaster-recovery-bcp-readiness.md)

### [Bab 10: Advanced Detection Engineering & Enterprise Capstone](./bab-10-detection-engineering-capstone/)
Konvergensi pertahanan dan rekayasa deteksi berbasis kode (*Detection-as-Code*) serta proyek uji akhir terpadu.
* [Modul 01: Detection-as-Code: Sigma Rules, YARA, & Threat Hunting Pipelines](./bab-10-detection-engineering-capstone/01-detection-as-code-sigma-yara.md)
* [Modul 02: Adversary Emulation Frameworks & Purple Team Validation](./bab-10-detection-engineering-capstone/02-adversary-emulation-purple-teaming.md)
* [Modul 03: Final Capstone: Hybrid Enterprise Intrusion & Defensive Engineering](./bab-10-detection-engineering-capstone/03-capstone-project-execution.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek
**"Operasi Simulasi Adversary Multi-Vektor, Respon Insiden Komprehensif, dan Rekayasa Deteksi pada Arsitektur Hybrid Enterprise"**

### Gambaran Lingkungan Uji (Testbed Environment)
Peserta akan diberikan akses ke lab tervirtualisasi yang merefleksikan infrastruktur enterprise menengah:
1. **On-Premise Infrastructure:**
   * 1 Domain Controller (Windows Server 2022) mengelola domain `corp.enterprise.local`.
   * 2 File & Database Server (Ubuntu Server 22.04 LTS & Windows Server).
   * 3 Workstation (Windows 11 Enterprise & Linux Mint).
2. **Cloud Perimeter (AWS VPC Peered ke On-Prem):**
   * 1 Public-facing E-Commerce / API Gateway Microservice running on AWS EKS (Kubernetes).
   * 1 S3 Bucket privat penyimpan data backup terenkripsi KMS.
3. **Defense & Telemetry Stack:**
   * Wazuh SIEM / Splunk Enterprise instance.
   * Suricata IDS & Zeek Network Monitor pada switch SPAN/TAP virtual.
   * Sysmon terkonfigurasi di seluruh endpoint Windows.

### Fase Pelaksanaan Capstone

#### Fase 1: Validasi Audit Postur & Rekayasa Baseline
* Mengidentifikasi miskonfigurasi IAM, segmen jaringan, dan celah kepatuhan CIS Benchmarks pada seluruh host.
* Menerapkan kontrol ZTNA untuk membatasi pergerakan dari DMZ ke domain internal.

#### Fase 2: Injeksi Simulasi Serangan Terarah (Red Team Injection)
* Eksekusi serangan bertingkat:
  1. *Initial Access:* Eksploitasi kerentanan SSRF pada microservice API di klaster EKS.
  2. *Cloud-to-On-Prem Lateral Pivot:* Penarikan kredensial AWS IAM via metadata service untuk mengakses VPN tunnel ke jaringan on-premise.
  3. *Internal Domain Compromise:* Serangan Kerberoasting, penyalahgunaan Active Directory Certificate Services (ADCS), dan ekstraksi database `NTDS.dit`.
  4. *Ransomware Deployment Emulation:* Distribusi payload uji (enkripsi terkontrol via script terisolasi) pada share internal.

#### Fase 3: Operasi Penanganan Insiden & DFIR (Blue Team Response)
* Triage telemetri: Mengidentifikasi IP C2, hash artefak, dan alur eskalasi hak istimewa menggunakan SIEM.
* Analisis memori volatile (`volatility3`) dari mesin Workstation yang menjadi titik infeksi pertama.
* Ekstraksi linimasa serangan lengkap berbasis format MITRE ATT&CK Enterprise Matrix.

#### Fase 4: Detection-as-Code & Hardening Remediasi (Purple Team Closure)
* Merancang 3 aturan **Sigma** khusus untuk mendeteksi *anomalous RPC execution* dan *Kubernetes token theft*.
* Membangun aturan **YARA** untuk mendeteksi biner artefak yang diinjeksi.
* Mempublikasikan repositori Git yang berisi playbooks automasi Ansible untuk memperbaiki celah konfigurasi awal secara instan.

### Deliverables & Kriteria Kelulusan
1. **Executive Incident & Risk Report (PDF):** Ringkasan risiko tingkat eksekutif, perkiraan kerugian finansial hipotesis, dan status kepatuhan pasca insiden.
2. **Technical DFIR Root-Cause Analysis (Markdown):** Dekonstruksi forensik menyeluruh dengan bukti *packet capture*, hash biner, dan log Sysmon/Auditd.
3. **Detection-as-Code Repository:** Kumpulan rule Sigma, YARA, dan script mitigasi yang divalidasi terhadap payload pengujian tanpa menghasilkan *false positive* pada lalu lintas operasional normal.