# Bab 02: Arsitektur Jaringan Skala Enterprise
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan topologi jaringan *multi-account*, *multi-region* berbasis **AWS Transit Gateway (TGW)**, **AWS Network Firewall**, dan **Direct Connect (DX)** dengan redundansi tingkat tinggi (Active/Active atau Active/Passive BGP).
- Menganalisis *packet life cycle* dan pola *traffic flow* (North-South, East-West) melalui *Centralized Inspection Architecture* dengan *bump-in-the-wire* packet inspection.
- Mengonfigurasi resolusi DNS skala enterprise hybrid menggunakan **Amazon Route 53 Resolver Endpoints** (Inbound & Outbound rules) terintegrasi dengan Active Directory/DNS On-Premises.
- Mengisolasi dan mengamankan pertukaran API antar-layanan menggunakan **AWS PrivateLink** (VPC Endpoint Services) guna memitigasi risiko eksposur ke *public internet*.
- Mengotomatisasi deployment infrastruktur jaringan produksi menggunakan **Terraform** dengan prinsip modularitas, idempotensi, dan kepatuhan terhadap standar keamanan CIS AWS Foundations Benchmark.
- Melakukan diagnostik *networking anomalies* (asymmetric routing, MTU black hole, route table exhaustion) secara terstruktur menggunakan VPC Flow Logs, Athena, dan CloudWatch Network Monitor.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam dan pengalaman langsung dalam:
- Konsep fundamental TCP/IP: Subnetting VLSM, CIDR notation (RFC 1918 & RFC 6598), dynamic routing protocols (khususnya Border Gateway Protocol/BGP, AS-Path prepending, BGP communities, MED).
- Fondasi AWS Networking: VPC primitives (Subnets, Internet Gateways, NAT Gateways, Route Tables, Network ACLs, Security Groups).
- Tooling: Terraform CLI (>= v1.5.0), AWS CLI v2 terkonfigurasi dengan profil multi-akun (AssumeRole), dan basic networking tools (`dig`, `mtr`, `traceroute`, `tcpdump`, `iperf3`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. AWS Transit Gateway (TGW) Internals & Elastic Network Interface (ENI) Datapath
AWS Transit Gateway beroperasi sebagai distributed Layer 3 router yang dibangun di atas **Hyperplane**—sistem SDN terdistribusi internal AWS yang juga menggerakkan Network Load Balancer (NLB) dan NAT Gateway. 

Ketika sebuah VPC di-*attach* ke TGW:
1. TGW meletakkan *Attachment ENI* di setiap Availability Zone (AZ) yang dipilih di dalam subnet khusus (biasanya berukuran `/28`).
2. Tidak seperti ENI standar EC2, TGW attachment ENI tidak memiliki IP address yang terlihat di OS routing table instance. ENI ini berfungsi sebagai *anchor point* tunnel cross-account/cross-VPC ke Hyperplane data plane.
3. **Penyelarasan AZ ID**: Komunikasi antar-AZ melalui TGW tetap berada di local AZ fabrics secara logis jika AZ ID (misal: `ap-southeast-1-az1`) cocok antar-akun. Jika mapping AZ berbeda (misal `ap-southeast-1a` pada Akun A menunjuk ke AZ ID 1, sedangkan di Akun B menunjuk ke AZ ID 2), paket akan menyeberang physical inter-AZ links yang menambah latensi mikrodetik dan biaya transfer data inter-AZ.

```
+-----------------------------------------------------------------------------------+
| AWS Hyperplane Distributed Data Plane (TGW Core)                                  |
|                                                                                   |
|  +--------------------+   +--------------------+   +--------------------+         |
|  | Route Table: Ingress|   | Route Table: Shared|   | Route Table: Spoke |         |
|  +--------------------+   +--------------------+   +--------------------+         |
+------------^------------------------^------------------------^--------------------+
             |                        |                        |
     [Attachment ENI]         [Attachment ENI]         [Attachment ENI]
      (AZ-1: Subnet-A)         (AZ-1: Subnet-B)         (AZ-1: Subnet-C)
+------------v-----------+ +----------v-----------+ +----------v-----------+
| Spoke VPC-01 (Prod)    | | Shared Services VPC  | | Inspection VPC       |
| CIDR: 10.100.0.0/16    | | CIDR: 10.200.0.0/16  | | CIDR: 10.250.0.0/16  |
+------------------------+ +----------------------+ +----------------------+
```

#### B. Centralized Egress & Inspection VPC Routing Patterns
Dalam enterprise network, *traffic flow* diklasifikasikan menjadi tiga:
1. **East-West (VPC-to-VPC / VPC-to-On-Premises)**: Melintasi TGW, dialihkan secara paksa (*appliance routing*) melewati fleet AWS Network Firewall atau third-party Next-Gen Firewall (Palo Alto VM-Series, Fortinet FortiGate) di Inspection VPC.
2. **North-South Egress (VPC-to-Internet)**: Spoke VPC -> TGW -> Inspection/Egress VPC -> NAT Gateway -> Internet Gateway.
3. **North-South Ingress (Internet-to-VPC)**: Public traffic -> Internet Gateway -> Network Firewall Subnet -> Public NLB/ALB -> App Subnet di Spoke VPC via TGW.

*Stateful Routing Requirement*: Fitur **Appliance Mode** pada TGW VPC Attachment wajib diaktifkan (`appliance_mode_support = "enable"`). Tanpa Appliance Mode, *symmetric return traffic* tidak dijamin; paket SYN dari AZ-1 bisa kembali melalui AZ-2 saat keluar dari appliance, yang menyebabkan paket di-drop secara sepihak oleh stateful firewall session tracking (*Connection Reset / TCP RST*).

#### C. Hybrid DNS Resolution Pipeline
Resolusi DNS multi-lingkungan bergantung pada **Route 53 Resolver** (Amazon Provided DNS di VPC base IP `x.x.x.2`):
- **Outbound Endpoints**: Instance di AWS menanyakan domain internal on-prem (misal: `corp.internal`). Route 53 Resolver Rule mencocokkan pattern ini dan memforward query via Outbound Endpoint ENI ke DNS Resolver On-Premises melewati Direct Connect/VPN.
- **Inbound Endpoints**: Server on-premise menanyakan Private Hosted Zone (PHZ) AWS (misal: `aws.enterprise.internal`). Server On-Premise mengarahkan forwarder ke IP Inbound Endpoint ENI di AWS.

---

### 4. Why & What

| Kebutuhan Enterprise | Pendekatan Konvensional (Anti-pattern) | Pendekatan Skala Enterprise (Standard) | Alasan Teknis & Bisnis |
| :--- | :--- | :--- | :--- |
| **Interkoneksi Antar-VPC** | VPC Peering Mesh ($N(N-1)/2$ koneksi) | AWS Transit Gateway Hub-and-Spoke terpusat | Skalabilitas batas route peering (maks. 125 peering), *route table management overhead*, dan audit jalur data terpusat. |
| **Inspeksi Keamanan** | NAT Gateway & Egress Firewall di setiap VPC | Centralized Egress & Inspection VPC via TGW | Menghemat biaya NAT GW per AZ di tiap VPC ($0.045/jam + data charge), konsolidasi policy firewall tunggal, audit compliance (PCI-DSS, ISO 27001). |
| **Koneksi On-Premises** | Site-to-Site IPsec VPN via Internet | AWS Direct Connect (DX) + Transit VIF + Backup IPsec VPN | Menghilangkan jitter dan packet loss via public internet, kapasitas throughput deterministik (1 Gbps - 100 Gbps), enkripsi end-to-end dengan failover otomatis BGP. |
| **Akses Layanan Shared/SaaS** | Membuka rute routing lintas VPC atau via Public IP | AWS PrivateLink (Interface Endpoints) | Mencegah tereksposnya CIDR spoke, menghindari tumpang tindih CIDR (overlapping IP), isolasi Level 4 (TCP), dan enkripsi dalam AWS backbone. |

---

### 5. How (Workflow Detail)

#### Algoritma Pemrosesan Paket di Centralized Inspection (East-West Flow)
1. **Source Node**: Workload di `Spoke VPC-A` (`10.100.1.50`) menginisiasi TCP SYN ke `Spoke VPC-B` (`10.200.1.50`).
2. **Subnet Route Table VPC-A**: Destination `10.200.0.0/16` diarahkan ke `tgw-xxxx`.
3. **TGW Route Table Ingress (Spoke Table)**: Rute `10.200.0.0/16` tidak mengarah langsung ke VPC-B, melainkan di-*blackhole* atau dialihkan ke rute default `0.0.0.0/0` yang memiliki *target attachment* Inspection VPC.
4. **Inspection VPC ENI**: Paket masuk via Attachment ENI di AZ-1.
5. **Subnet Route Table TGW-Attachment di Inspection VPC**: Rute `10.200.0.0/16` diarahkan ke endpoint AWS Network Firewall (VPCE).
6. **AWS Network Firewall Engine**: Stateful/Stateless engine memeriksa paket terhadap IPS/IDS signature dan domain whitelist/Suricata rules.
7. **Subnet Route Table Firewall di Inspection VPC**: Setelah lolos, rute `10.200.0.0/16` memiliki target `tgw-xxxx`.
8. **TGW Route Table Post-Inspection**: Attachment Inspection VPC terasosiasi dengan TGW Post-Inspection Route Table, yang memiliki rute spesifik `10.200.0.0/16` diarahkan ke VPC-B Attachment.
9. **Destination Delivery**: TGW meneruskan paket ke Attachment ENI VPC-B dan dialihkan ke instance tujuan (`10.200.1.50`).
10. **Reverse Flow (SYN-ACK)**: Mengikuti pola simetris identik karena `appliance_mode_support` menjamin paket kembali ke stateful firewall instance yang sama di AZ-1.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan Transit Gateway sebagai **Bandara Hub Internasional (Transit Hub)**, VPC-VPC Spoke sebagai **Kota Regional**, dan Inspection VPC sebagai **Area Pabean & Imigrasi Terpadu**.
- Penumpang (Paket Data) dari Kota A tidak bisa langsung terbang ke Kota B.
- Semua penerbangan diwajibkan mendarat di Terminal Transit (TGW), digiring melalui Gerbang Pabean Khusus (Inspection VPC / Network Firewall) untuk pemindaian bagasi (Deep Packet Inspection), baru kemudian diizinkan transfer ke gerbang penerbangan menuju Kota B.

#### Diagram Arsitektur Enterprise Hub-and-Spoke
```
                              +---------------------------------------+
                              |         On-Premises Datacenter        |
                              |               172.16.0.0/12           |
                              +-------------------+-------------------+
                                                  |
                                   Direct Connect | (DX) + VPN Backup
                                                  |
+-------------------------------------------------v-------------------------------------------------+
|                                          AWS REGION                                               |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |                                  AWS TRANSIT GATEWAY                                        |  |
|  |     +-------------------------+                     +---------------------------------+     |  |
|  |     | Spoke Route Table       |                     | Post-Inspection Route Table     |     |  |
|  |     | 0.0.0.0/0 -> Inspect-Att|                     | 10.100.0.0/16 -> Spoke-A-Att    |     |  |
|  |     |                         |                     | 10.200.0.0/16 -> Spoke-B-Att    |     |  |
|  |     |                         |                     | 172.16.0.0/12 -> DX-GW-Att       |     |  |
|  |     +-------------------------+                     +---------------------------------+     |  |
|  +-------------------+---------------------------------------------------+---------------------+  |
|                      |                                                   |                        |
|                      v                                                   v                        v
|   +------------------------------------+              +--------------------+    +--------------------+
|   |         INSPECTION VPC             |              |    SPOKE VPC-A     |    |    SPOKE VPC-B     |
|   |         10.250.0.0/16              |              | (Production App)   |    | (Shared Database)  |
|   |                                    |              |   10.100.0.0/16    |    |   10.200.0.0/16    |
|   |  +------------------------------+  |              +--------------------+    +--------------------+
|   |  | TGW Attachment Subnet        |  |              | Private Subnet     |    | Private Subnet     |
|   |  | Route to: Firewall VPCEndpoint  |              | 10.100.1.0/24      |    | 10.200.1.0/24      |
|   |  +--------------+---------------+  |              |                    |    |                    |
|   |                 |                  |              | App Workload       |    | RDS Cluster        |
|   |  +--------------v---------------+  |              +--------------------+    +--------------------+
|   |  | AWS Network Firewall Subnet  |  |                                                             
|   |  | Stateful & Stateless Rules   |  |                                                             
|   |  +--------------+---------------+  |                                                             
|   |                 |                  |                                                             
|   |  +--------------v---------------+  |                                                             
|   |  | Public / NAT Gateway Subnet  |  |                                                             
|   |  | (For North-South Egress)     |  |                                                             
|   |  +--------------+---------------+  |                                                             
|   +-----------------|------------------+                                                             
|                     v                                                                                
|             Internet Gateway                                                                         
+---------------------|-----------------------------------------------------------------------------+
                      v                                                                                
                  INTERNET                                                                             
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengaktifkan Appliance Mode via AWS CLI
Saat menghubungkan VPC Firewall/Inspection ke TGW, default routing AWS tidak simetris. Perintah berikut memaksakan TGW memilih attachment ENI dalam AZ yang sama untuk seluruh lifecycle flow TCP tersebut:

```bash
aws ec2 modify-transit-gateway-vpc-attachment \
    --transit-gateway-attachment-id tgwa-0123456789abcdef0 \
    --options ApplianceModeSupport=enable
```

#### Practical Example: Production-Ready Terraform HCL
Infrastruktur Hub-and-Spoke dengan isolasi Route Table dan Transit Gateway Route Table Association/Propagation.

```hcl
# network_core.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

# 1. Transit Gateway Utama
resource "aws_ec2_transit_gateway" "central_tgw" {
  description                     = "Enterprise Transit Gateway Hub"
  amazon_side_asn                 = 64512
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  auto_accept_shared_attachments  = "enable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"

  tags = {
    Name        = "tgw-core-prod-01"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

# 2. TGW Route Tables Terpisah untuk Microsegmentation
resource "aws_ec2_transit_gateway_route_table" "spoke_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  tags = { Name = "tgw-rt-spoke-traffic" }
}

resource "aws_ec2_transit_gateway_route_table" "post_inspection_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  tags = { Name = "tgw-rt-post-inspection" }
}

# 3. Spoke VPC Production
resource "aws_vpc" "spoke_prod" {
  cidr_block           = "10.100.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "vpc-prod-app-ap-southeast-1" }
}

resource "aws_subnet" "spoke_prod_tgw_attachment" {
  count             = 2
  vpc_id            = aws_vpc.spoke_prod.id
  cidr_block        = "10.100.${count.index}.0/28"
  availability_zone = count.index == 0 ? "ap-southeast-1a" : "ap-southeast-1b"
  tags              = { Name = "subnet-prod-tgw-attachment-az${count.index + 1}" }
}

# 4. Attachment Spoke VPC ke TGW
resource "aws_ec2_transit_gateway_vpc_attachment" "spoke_prod_attachment" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  vpc_id             = aws_vpc.spoke_prod.id
  subnet_ids         = aws_subnet.spoke_prod_tgw_attachment[*].id

  # Appliance Mode dimatikan di Spoke VPC (Hanya aktif di Inspection VPC)
  appliance_mode_support = "disable"

  tags = { Name = "tgw-attach-spoke-prod" }
}

# Asosiasi Spoke VPC ke Spoke Route Table
resource "aws_ec2_transit_gateway_route_table_association" "spoke_assoc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.spoke_prod_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.spoke_rt.id
}

# 5. Inspection VPC
resource "aws_vpc" "inspection_vpc" {
  cidr_block           = "10.250.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "vpc-sec-inspection-ap-southeast-1" }
}

resource "aws_subnet" "inspection_tgw_attachment" {
  count             = 2
  vpc_id            = aws_vpc.inspection_vpc.id
  cidr_block        = "10.250.${count.index}.0/28"
  availability_zone = count.index == 0 ? "ap-southeast-1a" : "ap-southeast-1b"
  tags              = { Name = "subnet-inspect-tgw-attachment-az${count.index + 1}" }
}

# Attachment Inspection VPC ke TGW dengan APPLIANCE MODE AKTIF
resource "aws_ec2_transit_gateway_vpc_attachment" "inspection_attachment" {
  transit_gateway_id     = aws_ec2_transit_gateway.central_tgw.id
  vpc_id                 = aws_vpc.inspection_vpc.id
  subnet_ids             = aws_subnet.inspection_tgw_attachment[*].id
  appliance_mode_support = "enable" # KRITIKAL: Menjamin symmetric routing untuk Firewall

  tags = { Name = "tgw-attach-inspection" }
}

resource "aws_ec2_transit_gateway_route_table_association" "inspection_assoc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.post_inspection_rt.id
}

# 6. Routing Rule: Paksa seluruh traffic dari Spoke Route Table masuk ke Inspection VPC
resource "aws_ec2_transit_gateway_route" "default_to_inspection" {
  destination_cidr_block         = "0.0.0.0/0"
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.spoke_rt.id
}

# Propagasi Spoke CIDR ke Post-Inspection Route Table
resource "aws_ec2_transit_gateway_route_table_propagation" "spoke_to_post_inspection" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.spoke_prod_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.post_inspection_rt.id
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Tier-1 FinTech Bank Digital
Institusi perbankan mengoperasikan 85 akun AWS (*multi-account strategy* via AWS Organizations) yang memproses transaksi bernilai triliunan Rupiah. Mereka wajib memenuhi regulasi PCI-DSS 4.0 dan Bank Indonesia mengenai inspeksi paket, pemisahan lingkungan, dan enkripsi in-transit.

#### Permasalahan Awal:
1. **Routing Chaos**: Menggunakan VPC Peering ad-hoc antar 85 VPC (ratusan peering connections), batas *route table limit* tercapai (100 routes/table).
2. **Security Blind Spot**: Tiap VPC memiliki NAT Gateway sendiri. Tidak ada visibilitas terhadap outbound egress traffic ke domain eksternal. Potensi kebocoran data (*data exfiltration*) via port 443 tidak terdeteksi.
3. **Hybrid DNS Mismatch**: Resolusi domain on-premise Active Directory dan AWS Route 53 saling menimpa (*split-brain resolution failure*), menyebabkan intermiten koneksi API Core Banking.

#### Solusi Arsitektur yang Diterapkan:
1. **Network Hub Terpusat**: Membangun 1 Dedicated Network Core Account yang memiliki AWS Transit Gateway dan AWS Direct Connect Gateway (DX-GW).
2. **Centralized Inspection & Egress**:
   - Membangun Inspection VPC menggunakan **AWS Network Firewall** multi-AZ.
   - Semua Spoke VPC ditarik NAT Gateway-nya, menghemat biaya ~$15,000/bulan.
   - Mengalihkan rute default `0.0.0.0/0` seluruh Spoke VPC melalui TGW menuju Inspection VPC.
   - Aturan Stateful Firewall Suricata diterapkan: Blokir seluruh direct-IP outgoing HTTPS traffic; izinkan hanya FQDN terdaftar via TLS SNI filtering.
3. **Split DNS System Terintegrasi**:
   - Deploy Route 53 Resolver Inbound Endpoint di 3 AZ Network Account. DNS On-Premise mengarahkan conditional forwarder `*.aws.bank.id` ke IP inbound ini.
   - Deploy Route 53 Resolver Outbound Endpoint. Rule forwarder dikonfigurasi: Query `*.corp.bank.id` diteruskan ke On-Premise Domain Controllers. Rule ini di-*share* ke 85 akun via AWS Resource Access Manager (RAM).

#### Hasil Eksekusi:
- **Zero Data Exfiltration Incident**: 100% outbound traffic terekam dan terinspeksi secara real-time.
- **Reduksi Biaya Operasional Jaringan**: Penurunan tagihan bulanan AWS sebesar 38% melalui konsolidasi NAT Gateway dan eliminasi redundant data-transfer.
- **Waktu Provisioning Environment**: Berkurang dari 5 hari kerja menjadi 20 menit menggunakan pipeline Terraform Service Catalog otomatis.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                         [Centralized Architecture]
                                    |
            +-----------------------+-----------------------+
            |                                               |
     KEUNTUNGAN                                         KERUGIAN
  - Inspeksi Terpusat (Security)                   - Tambahan Hop (+1 - 2ms Latency)
  - Biaya NAT Gateway Rendah                       - Biaya Pemrosesan TGW ($0.02/GB)
  - Simplifikasi Operasional                       - Limit Throughput Bandwidth
    (Single Point of Policy)                         (50 Gbps/AZ burst limit TGW)
```

| Parameter | Centralized Inspection (Hub-and-Spoke via TGW) | Decentralized / Distributed (Per-VPC Security) |
| :--- | :--- | :--- |
| **Network Latency** | Tambahan **1.0 - 2.5 milidetik** karena traverse Hyperplane engine dan firewalls. Tidak cocok untuk ultra-low latency trading HFT. | **Minimal (<1 ms)**, traffic tetap berada di VPC lokal. |
| **Throughput / Bandwidth** | Attachment TGW membatasi hingga **50 Gbps per AZ**. Traffic masif memerlukan multi-attachment atau partitioning. | Skala mengikuti arsitektur instance internal VPC (hingga **100-200 Gbps** via ENA Express). |
| **Kompleksitas Biaya** | Hemat pada NAT GW instances. Namun dikenakan biaya **$0.02 per GB processed** oleh TGW + **$0.065 per GB** firewall processing charge. | Biaya tinggi pada *idle fixed cost* (banyak NAT Gateway & Firewall appliances per VPC), namun hemat pada inter-VPC transit charge. |
| **Operasional & Tata Kelola**| Sangat Terpusat. Tim SecOps memiliki kendali penuh di Inspection VPC tanpa intervensi tim dev. | Terdesentralisasi. Tim DevOps rentan membuat Security Group/NACL permissive secara tidak sengaja. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: Asymmetric Routing Drop pada Stateful Appliances
* **Gejala**: Ping (ICMP) antar Spoke VPC berhasil, tetapi koneksi HTTP/TLS (TCP) mengalami `Connection Timeout` setelah handshake SYN dimulai.
* **Akar Masalah**: TGW mendistribusikan traffic secara ECMP/Flow-hash di across AZs. Paket SYN masuk ke Firewall melalui AZ-1, tetapi SYN-ACK kembali dari Spoke B melalui AZ-2. Firewall di AZ-2 me-reject paket karena tidak memiliki state session di conntrack table-nya.
* **Solusi**: Aktifkan Appliance Mode pada attachment Inspection VPC:
  ```bash
  aws ec2 modify-transit-gateway-vpc-attachment \
    --transit-gateway-attachment-id tgwa-xxxxxx \
    --options ApplianceModeSupport=enable
  ```

#### Skenario 2: Path MTU Discovery (PMTUD) Black Hole
* **Gejala**: SSH interaktif berjalan normal, namun command output panjang (seperti `cat large-file.txt`) atau `git push` payload besar hang tanpa error.
* **Akar Masalah**: AWS VPC mendukung Jumbo Frame (MTU 9001). Namun, Transit Gateway peering antar-region, AWS Direct Connect virtual interfaces tertentu, atau VPN hanya mendukung MTU 1500 (atau 1446 pada GRE/IPsec). Jika Security Group atau NACL memblokir ICMP Type 3 Code 4 (*Destination Unreachable, Fragmentation Needed*), paket berukuran besar di-drop tanpa memberi tahu pengirim (*MTU Black Hole*).
* **Solusi**: 
  1. Pastikan Security Group dan stateless NACL mengizinkan *ICMP Inbound*: Type 3, Code 4.
  2. Modifikasi MTU pada network interface instance host jika melintasi link hybrid:
     ```bash
     sudo ip link set dev eth0 mtu 1500
     ```
  3. Konfigurasikan TCP MSS Clamping pada edge router/firewall:
     ```text
     iptables -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
     ```

#### Skenario 3: BGP Route Table Exhaustion pada DX-Gateway
* **Gejala**: Rute baru dari AWS VPC tidak muncul di on-premise routing table via Direct Connect.
* **Akar Masalah**: Direct Connect Gateway memiliki *hard limit* maksimum 100 rute advertised dari AWS ke on-premise via BGP. Menambahkan terlalu banyak subnet individual melampaui limit ini secara silent.
* **Solusi**: Lakukan CIDR summarization (aggregasi rute) pada setting *Allowed Prefixes* di Virtual Private Gateway / DX-Gateway association:
  - Gunakan `10.0.0.0/8` atau `10.100.0.0/14`, hindari mengekspos individual `/24` subnet.

---

### 11. Best Practices (Production Checklist)

- [ ] **Subnet Ukuran /28 Khusus TGW**: Buat subnet kecil khusus (`/28`) di setiap AZ hanya untuk menampung TGW Attachment ENI. Jangan letakkan instance atau workload apapun di subnet ini guna mencegah kehabisan IP dan routing loop.
- [ ] **Appliance Mode Divalidasi**: Aktifkan Appliance Mode secara eksklusif pada inspection/firewall attachment; biarkan non-aktif pada spoke biasa untuk menghindari overhead distribusi hash yang tidak perlu.
- [ ] **Dynamic Routing via BGP Over Static**: Gunakan BGP dynamic peering untuk Direct Connect dan VPN. Manfaatkan BGP Communities untuk segmentasi dan ASN Private yang terencana (RFC 6996: `64512` - `65534`).
- [ ] **VPC Flow Logs Aktif pada Seluruh Interkoneksi**: Format log diperluas (*Custom Format*) untuk menangkap metadata esensial:
  ```text
  ${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status} ${tcp-flags} ${pkt-srcaddr} ${pkt-dstaddr}
  ```
- [ ] **DNS Conditional Forwarding Tidak Melingkar**: Pastikan tidak ada circular forwarding antara Route 53 Resolver Rules dan Active Directory DNS forwarders yang dapat memicu query amplification loop (*infinite DNS loop*).
- [ ] **Egress FQDN Filtering**: Larang wildcard rule `*` pada HTTP/HTTPS inspection firewall. Terapkan prinsip least privilege untuk outward APIs integration (misal: hanya izinkan `api.stripe.com`, `repo.almalinux.org`).
- [ ] **AWS RAM Isolation**: Gunakan AWS Resource Access Manager (RAM) dari Network Core Account untuk membagikan TGW dan Outbound Resolver Rules. Jangan izinkan dev account memodifikasi infrastruktur backbone.

---

### 12. Hands-on Practice: Implementasi Centralized Architecture

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### File 1: `hands-on/m02/variables.tf`
```hcl
variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "spoke_a_cidr" {
  type    = string
  default = "10.10.0.0/16"
}

variable "inspection_cidr" {
  type    = string
  default = "10.99.0.0/16"
}
```

#### File 2: `hands-on/m02/main.tf`
```hcl
provider "aws" {
  region = var.aws_region
}

# 1. Hub Transit Gateway
resource "aws_ec2_transit_gateway" "hub" {
  description                     = "Lab Hub TGW"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  tags                            = { Name = "lab-tgw-hub" }
}

# TGW Route Tables
resource "aws_ec2_transit_gateway_route_table" "spoke_in_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  tags               = { Name = "lab-tgw-spoke-ingress-rt" }
}

resource "aws_ec2_transit_gateway_route_table" "firewall_out_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  tags               = { Name = "lab-tgw-firewall-egress-rt" }
}

# 2. Spoke VPC-A
resource "aws_vpc" "spoke_a" {
  cidr_block           = var.spoke_a_cidr
  enable_dns_hostnames = true
  tags                 = { Name = "lab-spoke-a-vpc" }
}

resource "aws_subnet" "spoke_a_workload" {
  vpc_id            = aws_vpc.spoke_a.id
  cidr_block        = "10.10.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "lab-spoke-a-workload" }
}

resource "aws_subnet" "spoke_a_tgw_attachment" {
  vpc_id            = aws_vpc.spoke_a.id
  cidr_block        = "10.10.254.0/28"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "lab-spoke-a-tgw-att" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "spoke_a_attach" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  vpc_id             = aws_vpc.spoke_a.id
  subnet_ids         = [aws_subnet.spoke_a_tgw_attachment.id]
  tags               = { Name = "lab-spoke-a-attachment" }
}

resource "aws_ec2_transit_gateway_route_table_association" "spoke_a_assoc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.spoke_a_attach.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.spoke_in_rt.id
}

# 3. Central Inspection VPC
resource "aws_vpc" "inspection" {
  cidr_block           = var.inspection_cidr
  enable_dns_hostnames = true
  tags                 = { Name = "lab-inspection-vpc" }
}

resource "aws_subnet" "inspection_tgw_attachment" {
  vpc_id            = aws_vpc.inspection_vpc_id
  cidr_block        = "10.99.254.0/28"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "lab-inspect-tgw-att" }
}

resource "aws_subnet" "inspection_firewall" {
  vpc_id            = aws_vpc.inspection.id
  cidr_block        = "10.99.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "lab-inspect-firewall-subnet" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "inspection_attach" {
  transit_gateway_id     = aws_ec2_transit_gateway.hub.id
  vpc_id                 = aws_vpc.inspection.id
  subnet_ids             = [aws_subnet.inspection_tgw_attachment.id]
  appliance_mode_support = "enable"
  tags                   = { Name = "lab-inspection-attachment" }
}

resource "aws_ec2_transit_gateway_route_table_association" "inspection_assoc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection_attach.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.firewall_out_rt.id
}

# 4. Hub Routing Setup
resource "aws_ec2_transit_gateway_route" "default_spoke_to_fw" {
  destination_cidr_block         = "0.0.0.0/0"
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection_attach.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.spoke_in_rt.id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "propagate_spoke_to_fw_egress" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.spoke_a_attach.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.firewall_out_rt.id
}
```

#### File 3: `hands-on/m02/verify.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[+] Memeriksa status attachment TGW..."
aws ec2 describe-transit-gateway-vpc-attachments \
  --filters "Name=state,Values=available" \
  --query "TransitGatewayVpcAttachments[*].{ID:TransitGatewayAttachmentId,VPC:VpcId,ApplianceMode:Options.ApplianceModeSupport}" \
  --output table

echo "[+] Memverifikasi Appliance Mode pada Inspection Attachment..."
INSPECT_ATT=$(aws ec2 describe-transit-gateway-vpc-attachments \
  --filters "Name=tag:Name,Values=lab-inspection-attachment" \
  --query "TransitGatewayVpcAttachments[0].TransitGatewayAttachmentId" --output text)

APPLIANCE_STATUS=$(aws ec2 describe-transit-gateway-vpc-attachments \
  --transit-gateway-attachment-ids "${INSPECT_ATT}" \
  --query "TransitGatewayVpcAttachments[0].Options.ApplianceModeSupport" --output text)

if [ "${APPLIANCE_STATUS}" == "enable" ]; then
    echo "[SUCCESS] Appliance mode aktif pada Inspection Attachment (${INSPECT_ATT})."
else
    echo "[ERROR] Appliance mode TIDAK AKTIF pada Inspection Attachment!"
    exit 1
fi

echo "[+] Memeriksa rute 0.0.0.0/0 di Spoke Ingress Route Table..."
TGW_RT_ID=$(aws ec2 describe-transit-gateway-route-tables \
  --filters "Name=tag:Name,Values=lab-tgw-spoke-ingress-rt" \
  --query "TransitGatewayRouteTables[0].TransitGatewayRouteTableId" --output text)

aws ec2 search-transit-gateway-routes \
  --transit-gateway-route-table-id "${TGW_RT_ID}" \
  --filters "Name=state,Values=active" \
  --output table
```

#### Eksekusi:
```bash
terraform init
terraform apply -auto-approve
chmod +x verify.sh
./verify.sh
```

---

### 13. Exercise

#### Tingkat Easy
1. Modifikasi file `main.tf` di modul lab untuk menambahkan Availability Zone kedua (`ap-southeast-1b`) pada `spoke_a` dan `inspection` VPC, lengkap dengan subnet attachment dan alokasi CIDR yang valid.
2. Buat CloudWatch Log Group untuk menampung VPC Flow Logs dari `spoke_a` dengan rentang retensi 7 hari.

#### Tingkat Medium
1. Implementasikan Private VPC Endpoint (AWS PrivateLink) untuk AWS S3 (`com.amazonaws.ap-southeast-1.s3` tipe Interface) di dalam subnet privat `spoke_a`.
2. Buat Security Group pada Interface Endpoint tersebut yang membatasi akses: hanya membolehkan ingress TCP port 443 dari CIDR `10.10.1.0/24`.
3. Verifikasi dengan query DNS resolver bahwa hostname S3 merefleksikan IP private endpoint di dalam VPC.

#### Tingkat Hard
1. Buat arsitektur hub terpisah untuk skenario *Multi-Region Disaster Recovery* (`ap-southeast-1` dan `ap-southeast-2`).
2. Konfigurasikan **Transit Gateway Peering Attachment** antar kedua region tersebut via Terraform.
3. Terapkan rute statis pada TGW Route Table masing-masing region untuk memastikan subnet `10.10.0.0/16` (Region 1) dapat berkomunikasi dua arah dengan subnet `10.20.0.0/16` (Region 2).
4. Buat script pengujian packet loss dengan variasi ukuran MTU (1500 vs 9001 bytes) melalui `ping -M do -s <packet_size>` untuk mendeteksi batas MTU peering secara empiris.

---

### 14. Challenge (Tantangan Produksi Kompleks)
**Arsitektur Zero-Trust B2B Extranet dengan Overlapping CIDR & Stateful Deep Packet Inspection**

#### Konteks & Skenario:
Sebuah perusahaan logistik skala global baru saja mengakuisisi 3 vendor regional. Ketiga vendor tersebut harus mengakses cluster shared-services Elasticsearch di pusat data AWS Anda (`10.50.0.0/16`). Namun, ketiga vendor tersebut memiliki skema IP yang saling bertabrakan: ketiganya menggunakan `192.168.1.0/24` pada local subnet mereka.

#### Kebutuhan Teknis:
1. **Tidak Ada Rekonfigurasi IP Vendor**: Vendor tidak boleh dipaksa mengubah CIDR subnet on-premise mereka.
2. **Centralized IPS**: Semua panggilan API dari vendor ke Elasticsearch harus diinspeksi terhadap ancaman CVE menggunakan payload inspection (Snort/Suricata rules).
3. **Isolasi Mutlak**: Vendor A tidak boleh dapat berkomunikasi dengan Vendor B dalam kondisi apapun.
4. **Skalabilitas**: Sistem harus mampu menerima tambahan vendor baru dengan collision CIDR yang sama tanpa downtime pada vendor yang sedang berjalan.

#### Tugas Rekayasa:
Rancang arsitektur lengkap beserta blueprint Terraform yang menyelesaikan masalah overlapping IP ini (Petunjuk: Padukan kombinasi **PrivateLink Endpoint Services**, atau **Bidirectional Algorithmic NAT via AWS Private NAT Gateway**, terhubung ke Transit Gateway Core). Berikan dokumen arsitektur teknis mencakup:
- Diagram alir paket terperinci (beserta transformasi header Source IP & Destination IP di setiap checkpoint).
- Konfigurasi Terraform untuk mengimplementasikan NAT/PrivateLink abstraction layer tersebut.
- Penjelasan skema DNS private resolution yang digunakan oleh client di sisi vendor.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda)

1. Apa fungsi utama dari parameter `ApplianceModeSupport = "enable"` pada Transit Gateway VPC Attachment?
   - A. Meningkatkan bandwidth attachment dari 50 Gbps menjadi 100 Gbps.
   - B. Memastikan traffic request dan response melintasi Availability Zone yang sama secara simetris untuk menjaga stateful inspection.
   - C. Mengenkripsi seluruh paket data di layer 2 secara otomatis menggunakan protokol MACsec.
   - D. Mengubah VPC attachment agar dapat berfungsi sebagai Hardware Security Module (HSM).
   *Jawaban & Penjelasan*: **B**. Appliance Mode memaksa TGW memilih network interface attachment secara konsisten di AZ yang sama selama lifecycle session TCP tersebut, mencegah asymmetric routing yang merusak state table firewall.

2. Di arsitektur VPC, di manakah posisi network address default untuk AWS Provided DNS (AmazonRoute53Resolver)?
   - A. CIDR Block Base IP + 1
   - B. CIDR Block Base IP + 2
   - C. Broadcast Address (IP terakhir dari subnet)
   - D. 169.254.169.254
   *Jawaban & Penjelasan*: **B**. Amazon cadangkan IP kedua dari network CIDR VPC (contoh: pada `10.0.0.0/16`, IP DNS adalah `10.0.0.2`) untuk Route 53 Resolver Core.

3. Berapa batas maksimum Maximum Transmission Unit (MTU) yang didukung untuk traffic yang melintasi Transit Gateway antar-VPC dalam satu AWS Region?
   - A. 1500 bytes
   - B. 9001 bytes (Jumbo Frame)
   - C. 8500 bytes
   - D. 1446 bytes
   *Jawaban & Penjelasan*: **C**. TGW mendukung hingga 8500 bytes untuk intra-region traffic antar-VPC (berbeda dari EC2-to-EC2 VPC lokal yang bisa mencapai 9001 bytes, dan inter-region peering yang terbatas pada 1500 bytes).

4. Manakah komponen yang diperlukan jika server di on-premises ingin me-resolve Private Hosted Zone yang berada di dalam AWS VPC?
   - A. Route 53 Resolver Outbound Endpoint
   - B. Route 53 Resolver Inbound Endpoint
   - C. Route 53 Public Hosted Zone Delegation
   - D. NAT Gateway Port Forwarding
   *Jawaban & Penjelasan*: **B**. Inbound Endpoint menyediakan IP address lokal di dalam VPC yang bertindak sebagai target DNS forwarding bagi server DNS On-Premises.

5. Berapakah subnet mask minimum yang direkomendasikan AWS untuk dedicated TGW Attachment Subnet?
   - A. `/30`
   - B. `/29`
   - C. `/28`
   - D. `/24`
   *Jawaban & Penjelasan*: **C**. AWS mensyaratkan subnet attachment TGW memiliki setidaknya satu IP per AZ untuk Hyperplane interface, dan merekomendasikan mask minimum `/28` (16 IP addresses) guna mengakomodasi ekspansi internal routing AWS.

---

#### Soal Intermediate (Pilihan Ganda & Analisis Kasus)

6. Tim DevOps mengeluhkan bahwa throughput koneksi Direct Connect (DX) 10 Gbps mereka mentok di ~4.5 Gbps saat memindahkan data antar single pair EC2 instances. Fitur AWS networking apa yang harus diaktifkan pada instance untuk mengatasi kendala single-flow TCP hash limit?
   - A. Enhanced Networking (SR-IOV)
   - B. ENA Express (Elastic Network Adapter Express berbasis SRD)
   - C. VPC Peering mesh
   - D. Appliance Mode pada DX Gateway
   *Jawaban & Penjelasan*: **B**. ENA Express memanfaatkan protokol Scalable Reliable Datagram (SRD) berbasis AWS Nitro System untuk menyebarkan single stream transfer ke multipath channels, melampaui batas single-flow 5 Gbps EC2.

7. Perhatikan konfigurasi Route Table berikut:
   - Route A: `10.0.0.0/16` -> Target: `local`
   - Route B: `0.0.0.0/0` -> Target: `tgw-11111`
   - Route C: `10.100.0.0/14` -> Target: `tgw-22222`
   - Route D: `10.100.10.0/24` -> Target: `nat-33333`
   Jika instance mengirimkan paket ke IP tujuan `10.100.10.55`, rute manakah yang akan dieksekusi oleh VPC routing engine?
   - A. Route A
   - B. Route B
   - C. Route C
   - D. Route D
   *Jawaban & Penjelasan*: **D**. VPC Route Table bekerja mutlak berdasarkan prinsip *Longest Prefix Match* (LPM). `/24` adalah prefix yang paling spesifik dibanding `/14`, `/16`, atau `/0`.

8. Pada implementasi AWS Network Firewall di Inspection VPC, tipe rule group manakah yang harus dikonfigurasi untuk membatasi akses outbound HTTPS hanya ke domain `*.github.com` berdasarkan TLS Server Name Indication (SNI)?
   - A. Stateless Rule Group dengan 5-tuple matching
   - B. Stateful Rule Group dengan Domain List inspection
   - C. Security Group Egress Rule
   - D. Network ACL Deny Rule
   *Jawaban & Penjelasan*: **B**. Stateless engine hanya bekerja di Layer 3/4 (IP, Port, Protocol). Untuk memeriksa TLS Client Hello (SNI) di Layer 7, diperlukan Stateful Rule Group dengan inspeksi Domain List atau Suricata Rules.

9. Dua buah VPC (VPC A: `10.1.0.0/16` dan VPC B: `10.2.0.0/16`) dihubungkan melalui AWS Transit Gateway. Workload di VPC A tidak dapat melakukan ping ke VPC B. Saat dicek via VPC Flow Logs di VPC B, terlihat status action: `REJECT OK`. Di manakah letak kesalahan konfigurasinya?
   - A. Route Table pada VPC A belum memiliki target rute ke VPC B.
   - B. Security Group pada target instance di VPC B tidak mengizinkan ICMP ingress dari CIDR VPC A.
   - C. TGW Route Table association hilang.
   - D. Transit Gateway mengalami packet corruption.
   *Jawaban & Penjelasan*: **B**. Log `REJECT OK` pada VPC Flow Logs mengindikasikan bahwa paket telah mencapai interface jaringan tujuan (artinya seluruh routing TGW & VPC sukses), namun ditolak secara lokal oleh Security Group target instance atau local OS firewall.

10. Ketika menghubungkan AWS Direct Connect (DX) ke beberapa VPC di region yang berbeda menggunakan Direct Connect Gateway (DX-GW), batasan komunikasi apa yang secara inheren terjadi di DX-GW?
    - A. Tidak mendukung traffic IPv6.
    - B. Traffic Cloud-to-Cloud (VPC-to-VPC) tidak dapat ditransmisikan secara langsung melintasi DX-GW.
    - C. Kecepatan bandwidth diturunkan otomatis ke 1 Gbps.
    - D. BGP Peering harus direset setiap 24 jam.
    *Jawaban & Penjelasan*: **B**. Direct Connect Gateway dirancang murni untuk traffic on-premise-to-AWS. DX-GW secara teknis memblokir bridging atau routing antar-VPC yang terhubung kepadanya (traffic hairpinning prevention). Komunikasi VPC-to-VPC harus lewat TGW atau Peering.

---

#### Skenario Kasus Produksi (Analisis Troubleshooting Tingkat Mahir)

11. **Skenario Kasus 1: Intermittent Connection Drop saat Deploy Auto Scaling Group**
    * **Insiden**: Sebuah aplikasi web di Spoke VPC-A berkomunikasi dengan microservice di Spoke VPC-B melalui Transit Gateway. Selama jam sibuk, Auto Scaling Group di Spoke VPC-B meluncurkan puluhan instance baru di Availability Zone 3 (`ap-southeast-1c`). Seketika itu juga, 33% transaksi request HTTP dari Spoke VPC-A menghasilkan error `504 Gateway Timeout` secara acak.
    * **Pertanyaan**: Apa akar masalah arsitektur pada TGW attachment Spoke VPC-B dan bagaimana resolusi permanennya?
    * **Jawaban & Analisis Teknis**:
      - *Akar Masalah*: TGW VPC Attachment pada Spoke VPC-B awalnya hanya dikonfigurasi pada dua AZ (`ap-southeast-1a` dan `ap-southeast-1b`). Ketika instance baru lahir di `ap-southeast-1c`, instance tersebut tidak memiliki anchor point TGW Attachment ENI lokal di AZ tersebut. Hyperplane TGW tidak dapat merutekan traffic lintas AZ dari Spoke-A yang mengarah ke AZ-C tanpa attachment cross-wiring yang valid, menghasilkan packet drop (*cross-AZ routing hole*).
      - *Solusi Permanen*: Modifikasi subnet coverage attachment Spoke VPC-B menggunakan Terraform/CLI untuk menyertakan subnet di Availability Zone `ap-southeast-1c`. Pastikan seluruh AZ yang berpotensi digunakan oleh Auto Scaling Group telah terpetakan di TGW Attachment configuration.

12. **Skenario Kasus 2: DNS Poisoning & Resolution Loop Post-Migration**
    * **Insiden**: Setelah deploy Route 53 Outbound Resolver Rule untuk domain on-premise `corp.internal`, CPU utilization pada Domain Controller DNS on-premise melonjak 100% dan seluruh VPC DNS queries mengalami failure total.
    * **Pertanyaan**: Bagaimana loop ini bisa terjadi secara struktural dan langkah mitigasi darurat apa yang harus diambil?
    * **Jawaban & Analisis Teknis**:
      - *Akar Masalah*: Terjadi *Forwarding Loop* (amplifikasi rekursif). Admin mengonfigurasi forwarder di DNS on-premise: domain root `.` atau broad domain dialihkan ke IP Route 53 Inbound Endpoint. Di saat yang sama, Route 53 Outbound Rule memforward query domain `corp.internal` ke DNS On-Premise. Ketika sebuah query unresolved masuk (misal `bad-host.corp.internal`), DNS on-premise memforward query tersebut ke AWS, dan AWS memforwardnya kembali ke On-Premise, menciptakan infinite packet cycle sampai resource memory/CPU exhaustion.
      - *Solusi Darurat*:
        1. Hapus sementara association rule pada Route 53 Outbound Resolver ke VPC terkait.
        2. Perbaiki conditional forwarder di DNS on-premise agar *hanya* menargetkan subdomain spesifik AWS (misal `*.aws.corp.internal`) ke Inbound Endpoint AWS, bukan parent domain `.` atau circular namespace.
        3. Konfigurasikan negative caching TTL (SOA Minimum TTL) pada hosted zone untuk meredam amplifikasi query NXDOMAIN.

13. **Skenario Kasus 3: Latensi Tinggi dan Packet Loss pada Link BGP Direct Connect Failover**
    * **Insiden**: Perusahaan memiliki dua sirkuit Direct Connect: Link-1 (Primary, 10G) dan Link-2 (Secondary, 1G). Ketika Link-1 mengalami degradasi performa (bukan total down, melainkan 15% intermittent packet loss), traffic produksi tetap mengalir ke Link-1 dan tidak beralih ke Link-2. Ketika tim jaringan mencoba memaksa failover dengan menambahkan BGP AS-Path Prepending pada router on-premise untuk Link-1, traffic return dari AWS tetap memilih Link-1.
    * **Pertanyaan**: Mengapa AS-Path Prepending diabaikan oleh AWS Direct Connect dan mekanisme BGP apa yang wajib digunakan untuk memanipulasi ingress routing AWS?
    * **Jawaban & Analisis Teknis**:
      - *Akar Masalah*: AWS Direct Connect Routing Policy mengevaluasi atribut routing dengan hierarki ketat. Urutan prioritas rute AWS untuk outbound traffic menuju on-premises adalah:
        1. Longest Prefix Match (CIDR spesifik).
        2. BGP Local Preference (dikontrol melalui BGP Communities).
        3. AS-Path Length (AS-Path Prepending).
        Jika on-premise router mengirimkan BGP advertisement pada kedua link dengan Local Preference default yang sama atau tidak menggunakan AWS BGP communities, AWS tetap memprioritaskan link tertentu berdasarkan lowest router ID atau DX interface internal priority sebelum mengevaluasi AS-Path jika path length pendek. Lebih jauh, jika sirkuit Link-1 tidak putus di layer fisik BGP (flapping/loss), BGP session tidak down, sehingga route withdrawal tidak terpicu.
      - *Solusi*:
        1. Gunakan **AWS BGP Communities** untuk mengontrol Local Preference secara deterministik di core AWS router:
           - Tag Link-1 dengan Community `7224:7300` (High Local Preference: 900).
           - Tag Link-2 dengan Community `7224:7100` (Low Local Preference: 700).
           - Saat degradasi terdeteksi di Link-1, router on-premise secara otomatis (via SLA tracker) menurunkan community Link-1 ke `7224:7100` dan menaikkan Link-2 ke `7224:7300`.
        2. Aktifkan **Bidirectional Forwarding Detection (BFD)** pada session BGP Direct Connect dengan interval agresif (misal: 300ms x 3 detection multiplier = 900ms) untuk memaksa BGP session drop seketika saat packet loss melampaui ambang batas toleransi.

---

### 16. Summary

1. **Arsitektur Jaringan Skala Enterprise Modern**: Standar enterprise memisahkan concern routing (*data plane*) dan security inspection (*enforcement plane*) menggunakan AWS Transit Gateway dan Centralized Inspection VPC.
2. **Kunci Sukses Firewall Terpusat**: Fitur `ApplianceModeSupport` pada TGW attachment wajib aktif untuk memaksakan simetri AZ pada aliran stateful traffic; tanpa fitur ini, firewall akan me-reset koneksi secara acak.
3. **Isolasi Menggunakan Multiple Route Tables**: Gunakan teknik pemisahan TGW Route Table (Spoke Route Table vs Post-Inspection Route Table) guna memastikan microsegmentation dan perutean wajib melalui security appliance (*bump-in-the-wire*).
4. **Prinsip Hybrid DNS**: Resolusi DNS hybrid yang reliabel membutuhkan pemisahan jalur: Inbound Endpoints untuk melayani request dari On-Premises, dan Outbound Endpoints bersama Resolver Rules untuk resolusi namespace on-premise dari AWS.
5. **Operational Excellence**: Arsitektur jaringan tidak boleh bergantung pada manual clickops di console. Gunakan Terraform modular berstandar industri dengan parameter naming, tagging, dan variable boundary yang ketat demi menjamin reproduktibilitas infrastruktur dan pencegahan human-error pada level backbone enterprise.