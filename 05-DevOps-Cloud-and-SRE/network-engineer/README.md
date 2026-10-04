# Kurikulum Rekayasa Jaringan Enterprise (Enterprise Network Engineer)

Selamat datang di repositori resmi kurikulum **Enterprise Network Engineer**, sebuah program pembelajaran komprehensif berbasis standar industri yang diselaraskan langsung dengan kurikulum roadmap.sh (*Network Engineer*). Kurikulum ini dirancang untuk mencetak insinyur jaringan tingkat lanjut (*Senior Network/Infrastructure Engineer*) yang mampu merancang, membangun, mengamankan, mengotomatisasi, dan memecahkan masalah infrastruktur jaringan skala enterprise dan *service provider*.

---

## 1. Course Overview & Mindset

### Engineering Mindset
Seorang Network Engineer modern tidak hanya bertugas menghubungkan kabel dan mengonfigurasi CLI secara manual. Mindset yang ditekankan dalam silabus ini bertumpu pada lima pilar utama:
* **Packet-Level Observability:** Memahami apa yang sebenarnya terjadi di balik abstraksi melalui analisis *packet craft*, frame header, dan alur kontrol/data plane.
* **Deterministic & Resilient Architecture:** Merancang jaringan dengan prinsip *No Single Point of Failure* (NSPoF), konvergensi deterministik, dan isolasi domain kegagalan (*blast radius confinement*).
* **Security by Design:** Mengintegrasikan segmentasi ketat (Zero Trust Network Access), enkripsi jalur transmisi data, dan *hardening* bidang kontrol (*Control Plane Policing*).
* **Infrastructure as Code (IaC) & NetDevOps:** Menggantikan konfigurasi ad-hoc CLI manual dengan deklaratif pipeline berbasis Git, sumber kebenaran (*Single Source of Truth* seperti NetBox), dan otomatisasi (Ansible/Python).
* **Vendor-Agnostic Mastery:** Menguasai prinsip standar terbuka (IETF RFC, IEEE) sebelum mengimplementasikannya pada ekosistem multi-vendor (Cisco, Arista, Juniper, Linux Networking).

### Prasyarat Minimum
* Pemahaman dasar sistem komputer dan logika biner/heksadesimal.
* Kemampuan dasar navigasi Command-Line Interface (Linux/Unix shell).
* Akses ke perangkat virtualisasi jaringan (GNS3, EVE-NG, atau Containerlab).

---

## 2. Learning Roadmap

```plaintext
[ENTERPRISE NETWORK ENGINEER ROADMAP]
│
├── BAB 01: Fondasi Jaringan, Model OSI, dan Physical/Data-Link Layer
│   ├── Modul 01: Arsitektur Model OSI vs TCP/IP & Aliran Enkapsulasi Paket
│   ├── Modul 02: Karakteristik Physical Layer, Media Transmisi, & Ethernet Framing
│   └── Modul 03: Analisis Protokol L2 & Frame Inspection Menggunakan Wireshark
│
├── BAB 02: Protokol Internet (IPv4/IPv6), Subnetting, dan IP Addressing
│   ├── Modul 01: Arsitektur IPv4, Subnetting Lanjut, CIDR, dan VLSM
│   ├── Modul 02: Fondasi Arsitektur IPv6, Dual-Stack, dan Transition Mechanisms
│   └── Modul 03: Desain Hierarki Alokasi IP Enterprise & IPAM Management
│
├── BAB 03: Layer 2 Switching, Enterprise VLANs, Trunking, dan Spanning Tree
│   ├── Modul 01: Ethernet Switching Logic, MAC Table Dynamics, & VLAN 802.1Q
│   ├── Modul 02: Trunking, Inter-VLAN Routing (SVI & RoAS), & Link Aggregation (LACP)
│   └── Modul 03: Spanning Tree Protocol (STP, RSTP, MSTP) & Loop Prevention Guards
│
├── BAB 04: Layer 3 Routing Fundamentals, Static Routing, dan FHRP
│   ├── Modul 01: Mekanisme Routing Engine, RIB vs FIB, & Packet Forwarding Logic
│   ├── Modul 02: Advanced Static Routing, Floating Routes, & Policy-Based Routing
│   └── Modul 03: First Hop Redundancy Protocols (HSRP, VRRP, GLBP)
│
├── BAB 05: Interior Gateway Dynamic Routing (OSPFv2/v3 & IS-IS)
│   ├── Modul 01: Link-State Mechanics, Pembentukan Adjacency, & OSPF Packet Types
│   ├── Modul 02: Desain Multi-Area OSPF, Tipe LSA (1-7), & Route Summarization
│   └── Modul 03: OSPFv3 untuk IPv6, Tuning Metrik Konvergensi, & IS-IS Enterprise Core
│
├── BAB 06: Exterior Gateway Protocol: BGP & Inter-Domain Routing
│   ├── Modul 01: Arsitektur BGP, Pembentukan Sesi TCP Port 179, dan Path Vector
│   ├── Modul 02: BGP Attributes, Decision Process Engine, & Policy Filtering
│   └── Modul 03: iBGP vs eBGP, Route Reflectors, BGP Peering, & Multi-Homing
│
├── BAB 07: Layanan Infrastruktur Inti Jaringan (Core Network Services)
│   ├── Modul 01: Dynamic Host Configuration Protocol (DHCP) & Relay Architecture
│   ├── Modul 02: Domain Name System (DNS) Resolution, Anycast, & NTP Synchronisation
│   └── Modul 03: Network Address Translation (SNAT, DNAT, Carrier-Grade NAT)
│
├── BAB 08: Keamanan Jaringan, Firewalling, Segmentation, dan VPNs
│   ├── Modul 01: Stateless Filtering (ACL) vs Stateful Firewall Inspection & ZBFW
│   ├── Modul 02: Site-to-Site IPsec VPN (IKEv1/IKEv2), DMVPN, dan WireGuard
│   └── Modul 03: Layer 2 Attack Mitigation (DAI, DHCP Snooping, Port Security, 802.1X)
│
├── BAB 09: Network Automation, NetDevOps, dan Programmability
│   ├── Modul 01: Otomatisasi Terprogram Menggunakan Python (Netmiko & NAPALM)
│   ├── Modul 02: Model Data Jaringan (YANG), RESTCONF, NETCONF, & Structured Data
│   └── Modul 03: Network Configuration Management Menggunakan Ansible & NetBox SSoT
│
└── BAB 10: Monitoring, Observability, High Availability, dan Troubleshooting
    ├── Modul 01: Protokol Telemetri, SNMP, Syslog, dan Flow Monitoring (NetFlow/IPFIX)
    ├── Modul 02: Metodologi Troubleshooting Sistematis (Layer-by-Layer & Root Cause)
    └── Modul 03: Arsitektur Data Center Modern: Spine-Leaf Fabric & Pengenalan EVPN-VXLAN
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Jaringan, Model OSI, dan Physical/Data-Link Layer](./bab-01-fondasi-jaringan-osi-tcpip/README.md)
*Focus: Dekonstruksi komunikasi paket data dari level bit hingga aplikasi, implementasi media transmisi, dan inspeksi frame Ethernet.*
* [Modul 01: Arsitektur Model OSI vs TCP/IP & Aliran Enkapsulasi Paket](./bab-01-fondasi-jaringan-osi-tcpip/modul-01.md)
* [Modul 02: Karakteristik Physical Layer, Media Transmisi, & Ethernet Framing](./bab-01-fondasi-jaringan-osi-tcpip/modul-02.md)
* [Modul 03: Analisis Protokol L2 & Frame Inspection Menggunakan Wireshark](./bab-01-fondasi-jaringan-osi-tcpip/modul-03.md)

### [Bab 02: Protokol Internet (IPv4/IPv6), Subnetting, dan IP Addressing](./bab-02-ipv4-ipv6-subnetting/README.md)
*Focus: Rekayasa skema pengalamatan IP skala besar, kalkulasi efisiensi subnetting, dan implementasi transisi dual-stack IPv4/IPv6.*
* [Modul 01: Arsitektur IPv4, Subnetting Lanjut, CIDR, dan VLSM](./bab-02-ipv4-ipv6-subnetting/modul-01.md)
* [Modul 02: Fondasi Arsitektur IPv6, Dual-Stack, dan Transition Mechanisms](./bab-02-ipv4-ipv6-subnetting/modul-02.md)
* [Modul 03: Desain Hierarki Alokasi IP Enterprise & IPAM Management](./bab-02-ipv4-ipv6-subnetting/modul-03.md)

### [Bab 03: Layer 2 Switching, Enterprise VLANs, Trunking, dan Spanning Tree](./bab-03-switching-vlan-stp/README.md)
*Focus: Logika bridging tingkat lanjut, isolasi broadcast domain, agregasi kapasitas fisik, dan stabilitas topologi anti-loop.*
* [Modul 01: Ethernet Switching Logic, MAC Table Dynamics, & VLAN 802.1Q](./bab-03-switching-vlan-stp/modul-01.md)
* [Modul 02: Trunking, Inter-VLAN Routing (SVI & RoAS), & Link Aggregation (LACP)](./bab-03-switching-vlan-stp/modul-02.md)
* [Modul 03: Spanning Tree Protocol (STP, RSTP, MSTP) & Loop Prevention Guards](./bab-03-switching-vlan-stp/modul-03.md)

### [Bab 04: Layer 3 Routing Fundamentals, Static Routing, dan FHRP](./bab-04-routing-static-fhrp/README.md)
*Focus: Cara kerja internal forwarding engine router, manajemen jalur statis probabilistik, dan gateway redundancy di sisi end-device.*
* [Modul 01: Mekanisme Routing Engine, RIB vs FIB, & Packet Forwarding Logic](./bab-04-routing-static-fhrp/modul-01.md)
* [Modul 02: Advanced Static Routing, Floating Routes, & Policy-Based Routing](./bab-04-routing-static-fhrp/modul-02.md)
* [Modul 03: First Hop Redundancy Protocols (HSRP, VRRP, GLBP)](./bab-04-routing-static-fhrp/modul-03.md)

### [Bab 05: Interior Gateway Dynamic Routing (OSPFv2/v3 & IS-IS)](./bab-05-interior-dynamic-routing-ospf-isis/README.md)
*Focus: Desain dynamic routing berbasis algoritma Dijkstra/SPF, struktur hierarkis backbone multi-area, dan tuning konvergensi sub-detik.*
* [Modul 01: Link-State Mechanics, Pembentukan Adjacency, & OSPF Packet Types](./bab-05-interior-dynamic-routing-ospf-isis/modul-01.md)
* [Modul 02: Desain Multi-Area OSPF, Tipe LSA (1-7), & Route Summarization](./bab-05-interior-dynamic-routing-ospf-isis/modul-02.md)
* [Modul 03: OSPFv3 untuk IPv6, Tuning Metrik Konvergensi, & IS-IS Enterprise Core](./bab-05-interior-dynamic-routing-ospf-isis/modul-03.md)

### [Bab 06: Exterior Gateway Protocol: BGP & Inter-Domain Routing](./bab-06-exterior-routing-bgp-peering/README.md)
*Focus: Arsitektur routing internet global, manipulasi atribut rute untuk kontrol jalur ingress/egress, dan desain ISP multi-homing.*
* [Modul 01: Arsitektur BGP, Pembentukan Sesi TCP Port 179, dan Path Vector](./bab-06-exterior-routing-bgp-peering/modul-01.md)
* [Modul 02: BGP Attributes, Decision Process Engine, & Policy Filtering](./bab-06-exterior-routing-bgp-peering/modul-02.md)
* [Modul 03: iBGP vs eBGP, Route Reflectors, BGP Peering, & Multi-Homing](./bab-06-exterior-routing-bgp-peering/modul-03.md)

### [Bab 07: Layanan Infrastruktur Inti Jaringan (Core Network Services)](./bab-07-network-services-infrastructure/README.md)
*Focus: Orkestrasi dependensi jaringan krusial, penanganan alokasi IP dinamis lintas subnet, sinkronisasi waktu, dan translasi alamat IP.*
* [Modul 01: Dynamic Host Configuration Protocol (DHCP) & Relay Architecture](./bab-07-network-services-infrastructure/modul-01.md)
* [Modul 02: Domain Name System (DNS) Resolution, Anycast, & NTP Synchronisation](./bab-07-network-services-infrastructure/modul-02.md)
* [Modul 03: Network Address Translation (SNAT, DNAT, Carrier-Grade NAT)](./bab-07-network-services-infrastructure/modul-03.md)

### [Bab 08: Keamanan Jaringan, Firewalling, Segmentation, dan VPNs](./bab-08-network-security-firewall-vpn/README.md)
*Focus: Mitigasi kerentanan protokol lapis bawah, proteksi akses perimeter, dan enkripsi terowongan tunneling site-to-site.*
* [Modul 01: Stateless Filtering (ACL) vs Stateful Firewall Inspection & ZBFW](./bab-08-network-security-firewall-vpn/modul-01.md)
* [Modul 02: Site-to-Site IPsec VPN (IKEv1/IKEv2), DMVPN, dan WireGuard](./bab-08-network-security-firewall-vpn/modul-02.md)
* [Modul 03: Layer 2 Attack Mitigation (DAI, DHCP Snooping, Port Security, 802.1X)](./bab-08-network-security-firewall-vpn/modul-03.md)

### [Bab 09: Network Automation, NetDevOps, dan Programmability](./bab-09-automation-programmability-iac/README.md)
*Focus: Transformasi operasional jaringan via scripting, pemodelan data terstruktur menggunakan YANG, dan pipeline orkestrasi terpadu.*
* [Modul 01: Otomatisasi Terprogram Menggunakan Python (Netmiko & NAPALM)](./bab-09-automation-programmability-iac/modul-01.md)
* [Modul 02: Model Data Jaringan (YANG), RESTCONF, NETCONF, & Structured Data](./bab-09-automation-programmability-iac/modul-02.md)
* [Modul 03: Network Configuration Management Menggunakan Ansible & NetBox SSoT](./bab-09-automation-programmability-iac/modul-03.md)

### [Bab 10: Monitoring, Observability, High Availability, dan Troubleshooting](./bab-10-monitoring-observability-troubleshooting/README.md)
*Focus: Pemantauan proaktif, penegakan arsitektur fabric modern data center, dan metodologi investigasi insiden jaringan kritikal.*
* [Modul 01: Protokol Telemetri, SNMP, Syslog, dan Flow Monitoring (NetFlow/IPFIX)](./bab-10-monitoring-observability-troubleshooting/modul-01.md)
* [Modul 02: Metodologi Troubleshooting Sistematis (Layer-by-Layer & Root Cause)](./bab-10-monitoring-observability-troubleshooting/modul-02.md)
* [Modul 03: Arsitektur Data Center Modern: Spine-Leaf Fabric & Pengenalan EVPN-VXLAN](./bab-10-monitoring-observability-troubleshooting/modul-03.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Capstone
**"Arsitektur Jaringan Enterprise Multi-Site Resilient & Terotomatisasi (Project TITAN-NET)"**

### Skenario Proyek
Sebuah konglomerasi finansial multinasional memerlukan pembaruan total (*network overhaul*) infrastruktur mereka yang mencakup:
1. **Headquarters (HQ) Campus:** Jaringan 3-Tier (Core, Distribution, Access) dengan redundansi tinggi.
2. **Data Center (DC) Fabric:** Topologi Spine-Leaf 2-Tier berbasis EVPN-VXLAN untuk pergerakan beban kerja virtualisasi tanpa hambatan Layer 2.
3. **Dua Kantor Cabang (Branch Offices):** Terhubung ke HQ dan DC melalui dual WAN uplinks menggunakan BGP multi-homing dan Dynamic Multipoint IPsec VPN (DMVPN).
4. **NetDevOps Orchestration Engine:** Seluruh konfigurasi baseline perangkat, alokasi VLAN, dan kebijakan keamanan dikelola otomatis melalui Git repository, NetBox IPAM, dan playbook Ansible.

### Rincian Topologi Teknis
* **Core & Distribution:** 2x Core Switches, 2x Distribution Switches (LACP Port-Channels, MSTP, VRRP/HSRP).
* **Routing Protocol In-Domain (IGP):** OSPFv2 & OSPFv3 Backbone Area 0 pada Core/Campus, IS-IS atau OSPF di Underlay DC Spine-Leaf.
* **Edge & Internet Peering:** Border Routers menjalankan eBGP ke dua ISP berbeda dengan BGP Traffic Engineering (AS-Path Prepending & MED manipulation) serta proteksi BGP Route Filtering.
* **Security & Hardening:** Dynamic ARP Inspection (DAI), DHCP Snooping, 802.1X Access Authentication, IPsec IKEv2 site-to-site VPN failover otomatis.
* **Automation Server:** Mesin Linux terpusat yang menjalankan Ansible, terintegrasi ke REST API NetBox untuk memvalidasi *desired state* vs *actual state*.

### Deliverables Wajib
1. **Repository Kode Sumber Infrastruktur:**
   * Script otomatisasi Python (audit konfigurasi, visualisasi topologi).
   * Playbook Ansible lengkap untuk provisioning router dan switch dari status *zero-touch*.
2. **Dokumen Desain Teknis (LLD/HLD):**
   * High-Level Design (HLD) diagram arsitektur fisik dan logika.
   * Low-Level Design (LLD) menyertakan tabel pemetaan IP (IPv4 & IPv6), peta VLAN, alokasi port switch, dan matriks OSPF/BGP metrics.
3. **Packet Capture & Validation Report:**
   * File `.pcapng` hasil verifikasi *failover* konvergensi FHRP (< 2 detik).
   * File `.pcapng` konvergensi rute failover BGP WAN saat salah satu sirkuit ISP terputus.
   * Log pengujian kepatuhan keamanan L2 (uji coba isolasi serangan DHCP Rogue & ARP Spoofing).

### Kriteria Kelulusan (Evaluation Metrics)
* **Ketersediaan Jaringan (Zero Single-Point-of-Failure):** Pengujian pemutusan link secara sengaja pada backbone atau distribution layer tidak boleh menghasilkan *packet loss* lebih dari 3 detik (sub-second convergence pada link yang dilindungi BFD/RSTP).
* **Integritas Otomatisasi (Idempotency):** Menjalankan pipeline Ansible berulang kali tidak boleh mengubah konfigurasi yang sudah benar (*idempotent verification*), dan seluruh perubahan konfigurasi wajib terekam pada Git commit log.
* **Kerapian Arsitektural:** Skema alokasi IP harus mendukung *summarization* optimal di perimeter area OSPF dan boundary BGP.

---
*Silabus ini disusun untuk pembelajaran mandiri intensif maupun pelatihan korporat berstandar engineering internasional. Mulailah perjalanan dari [Bab 01](./bab-01-fondasi-jaringan-osi-tcpip/README.md).*