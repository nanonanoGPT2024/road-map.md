# BAB 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengotomasi** tata kelola akun AWS skala enterprise berbasis *Multi-Account Framework* menggunakan AWS Organizations, Service Control Policies (SCP), dan AWS Resource Access Manager (RAM).
- **Merancang & Mengimplementasikan** topologi jaringan hybrid *Hub-and-Spoke* menggunakan AWS Transit Gateway (TGW) dengan isolasi *Route Table*, *Equal-Cost Multi-Path* (ECMP), dan terminasi VPN/Direct Connect.
- **Mengonfigurasi Arsitektur Keamanan Jaringan Terpusat** (*Centralized Egress/Ingress Inspection*) menggunakan AWS Network Firewall dan Gateway Load Balancer (GWLB) untuk mencegah *asymmetric routing* dan menginspeksi trafik *East-West* serta *North-South*.
- **Mengevaluasi & Mengeliminasi *Data Transfer Cost Overheads*** melalui desain VPC Endpoints (Interface vs. Gateway) dan arsitektur AWS PrivateLink multi-region.
- **Menulis Infrastruktur Produksi Deklaratif** berbasis HashiCorp Terraform untuk memvalidasi *zero-trust network boundary* pada level paket data dan IAM permissions boundary.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Konsep Jaringan Lanjutan**: Subnetting VLSM, CIDR aggregation, protokol routing BGP (Border Gateway Protocol, ASN, path prepending), TCP/IP handshake, MTU sizing (Standard 1500 vs. Jumbo Frame 9001 bytes).
- **AWS Fundamental**: VPC, Subnetting, Security Groups, Network ACLs, IAM Core (Role, Policy Evaluation Engine, AssumeRole).
- **Tooling & IaC**: Terraform (HCL v1.5+) sintaks lanjutan (*loops*, dynamic blocks, state management), AWS CLI v2, dan `jq`.
- **Operating System**: Linux networking (`iptables`, `ip route`, `ip link`, `traceroute`, `tcpdump`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Enterprise Multi-Account Architecture Engine
Dalam arsitektur enterprise, satu akun AWS (*single account*) adalah anti-pattern yang melanggar prinsip *least privilege* dan *blast radius containment*. AWS Organizations mengimplementasikan model pohon hierarki berbasis *Organizational Units* (OU).

```
                      +-------------------+
                      |   Root Account    |
                      +---------+---------+
                                |
          +---------------------+---------------------+
          |                                           |
+---------v---------+                       +---------v---------+
|    Core OU        |                       |   Workloads OU    |
+----+----+----+----+                       +----+----+----+----+
     |    |    |                                 |    |    |
     |    |    +-> Network Core                  |    |    +-> Production
     |    +------> Security/Audit                |    +------> Staging
     +-----------> Shared Services               +-----------> Sandbox
```

*Service Control Policies* (SCP) beroperasi sebagai *filter guardrail* terluar sebelum IAM policy dievaluasi di level akun. SCP tidak pernah memberikan izin (*allow*), melainkan menetapkan batas otorisasi maksimum (*permission boundary*).
- Algoritma evaluasi SCP:
  $$\text{Final Permission} = \text{Explicit Allow (SCP)} \cap \text{Explicit Allow (IAM)} - \text{Explicit Deny (SCP/IAM)}$$
- Jika sebuah aksi diblokir oleh SCP di level OU Root, tidak ada IAM Role se-powerful apapun (termasuk `AdministratorAccess`) di akun anak yang dapat mengeksekusinya.

#### B. AWS Transit Gateway (TGW) Core Mechanics
TGW bertindak sebagai *Regional Virtual Router* layer 3 yang menghubungkan ratusan VPC, VPN, dan AWS Direct Connect.
- **Attachment Architecture**: Saat VPC di-*attach* ke TGW, AWS secara internal menyuntikkan ENI (*Elastic Network Interface*) khusus ke dalam satu subnet per Availability Zone (AZ) yang ditentukan.
- **Routing Isolation**: TGW mendukung *multiple route tables*. VPC *Attachment* diasosiasikan (*association*) dengan tepat **satu** TGW Route Table, namun rutenya dapat disebarkan (*propagation*) ke **banyak** TGW Route Table.
- **Inter-VPC Traffic Flow**: Paket data yang meninggalkan EC2 di VPC-A melintasi VPC Route Table $\rightarrow$ TGW Attachment ENI $\rightarrow$ TGW Route Table (lookup) $\rightarrow$ TGW Attachment ENI tujuan $\rightarrow$ VPC-B Route Table $\rightarrow$ Target EC2.

#### C. Gateway Load Balancer (GWLB) & Centralized Packet Inspection
Arsitektur lama *bump-in-the-wire* berbasis SNAT/DNAT pada Virtual Appliance (misal: Palo Alto, Fortinet) menghancurkan visibilitas *Source IP* dan menciptakan bottleneck ketersediaan tinggi. GWLB mengatasi limitasi ini menggunakan:
1. **Geneve Encapsulation (RFC 8926)**: GWLB membungkus paket IP asli ke dalam paket UDP Geneve (port 6081) dengan menambahkan metadata (VPC Endpoint ID, Attachment ID, Flow Cookie). Ini mempertahankan Source IP dan Destination IP asli tanpa perlu SNAT.
2. **GWLB Endpoints (GWLBe)**: Bertindak sebagai target rute dalam VPC Route Table menggunakan teknologi AWS Hyperplane (komponen terdistribusi ultra-low-latency yang sama dengan NLB dan NAT Gateway).

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Hub-Mesh Tradisional | Modern Enterprise Hub-and-Spoke (TGW + GWLB) |
| :--- | :--- | :--- |
| **Batas Isolasi (*Blast Radius*)** | VPC peering jenuh ($N \times (N-1)/2$ peering limits). Akses lateral sulit dibendung. | Akun AWS terpisah per domain bisnis. SCP keras. Isolasi level TGW Route Table. |
| **Inspeksi Lalu Lintas** | Terdistribusi (firewall dipasang di tiap VPC). Biaya lisensi NVA (*Network Virtual Appliance*) membengkak. | Terpusat (*Centralized Egress/Ingress Inspection VPC*). 1 pool firewall menginspeksi seluruh domain. |
| **Interkoneksi On-Premises** | VPN IPsec/VIF Direct Connect ditarik ke masing-masing VPC. Kompleksitas BGP tinggi. | Direct Connect Gateway (DXGW) dan Transit VIF dihubungkan terpusat langsung ke TGW. |
| **Kepatuhan Regulasi** | Audit log terdistribusi, risiko manipulasi oleh engineer lokal akun sangat tinggi. | Akun Log Archive dan Security Tooling tersentralisasi; log dikirim via rute terisolasi tanpa lewat internet. |

---

### 5. How (Workflow Detail Inspeksi Terpusat)

Berikut adalah mekanisme siklus hidup routing paket data *East-West* (Spoke VPC A ke Spoke VPC B) melalui Central Inspection VPC:

```
[Spoke-A (10.1.0.0/16)]      [AWS Transit Gateway]      [Inspection-VPC (10.0.0.0/16)]      [Spoke-B (10.2.0.0/16)]
        |                              |                              |                              |
  1. Kirim paket (Dst: 10.2.10.5)      |                              |                              |
        +----------------------------->+                              |                              |
        |  Route to TGW Attachment     |                              |                              |
        |                              | 2. Lookup TGW Spoke RT       |                              |
        |                              |    Match 10.2.0.0/16 -> Insp |                              |
        |                              +----------------------------->+                              |
        |                              |    Forward ke Insp Attachment|                              |
        |                              |                              | 3. Subnet RT:                |
        |                              |                              |    Dst 10.2.0.0/16 -> GWLBe  |
        |                              |                              |    Encapsulate GENEVE        |
        |                              |                              | 4. Forward to Firewall App   |
        |                              |                              | 5. Inspection: ALLOW         |
        |                              |                              | 6. Firewall returns packet   |
        |                              |                              | 7. Return to TGW via subnet  |
        |                              |                              |    RT (0.0.0.0/0 -> TGW)     |
        |                              |                              +----------------------------->+
        |                              |                              | Forward to TGW Attachment    |
        |                              | 8. Lookup TGW Post-Insp RT   |                              |
        |                              |    Match 10.2.0.0/16 -> Spk-B|                              |
        |                              +------------------------------------------------------------>|
        |                              |                              | 9. Kirim ke target ENI       |
        |                              |                              |    Dst: 10.2.10.5            |
```

1. **Egress Spoke-A**: Subnet Route Table di Spoke-A memiliki target rute `10.2.0.0/16` mengarah ke `tgw-xxxx`.
2. **TGW Ingress**: TGW menerima paket di *Spoke Route Table*. Rute default atau rute spesifik mengarahkan trafik tersebut ke *Inspection VPC Attachment*.
3. **Inspection Subnet Processing**: Trafik masuk di subnet attachment Inspection VPC. Subnet Route Table mengarahkan trafik menuju GWLB Endpoint (`vpce-xxxx`).
4. **Geneve Forwarding**: GWLBe membungkus paket IP asli ke dalam UDP port 6081 dan mengirimkannya ke armada Firewall Appliance.
5. **DPI (*Deep Packet Inspection*)**: Firewall mendekapsulasi paket, memeriksa IDPS, signature, dan state. Bila lolos, paket dienkapsulasi kembali dan dikirim balik ke GWLBe.
6. **Re-routing to TGW**: Dari GWLBe, subnet routing table mengarahkan trafik kembali ke TGW Attachment.
7. **TGW Egress Routing**: Paket masuk kembali ke TGW, kali ini diasosiasikan dengan *Post-Inspection Route Table* yang memiliki rute propagasi dari Spoke-B (`10.2.0.0/16`).
8. **Final Delivery**: TGW meneruskan paket ke Spoke-B Attachment hingga mendarat di instance tujuan.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Logistik & Otoritas Pabean
Bayangkan arsitektur multi-akun enterprise sebagai sistem logistik negara bagian:
- **Akun AWS**: Kota-kota otonom yang mandiri (Spoke-A, Spoke-B, Core).
- **Service Control Policy (SCP)**: Undang-Undang Konstitusi Negara Bagian. Walikota kota otonom (Admin Akun) tidak bisa mencabut undang-undang ini sekalipun memiliki otoritas tertinggi di kotanya.
- **AWS Transit Gateway (TGW)**: Sistem Jalan Tol Nasional Lingkar Luar. Mengeliminasi kebutuhan membangun jembatan flyover khusus antar setiap perumahan (VPC Peering).
- **Gateway Load Balancer & Inspection VPC**: Pos Pabean dan Karantina Pusat di gerbang tol. Semua truk (paket data) antar wilayah industri wajib masuk ke *Inspection Bay* (Firewall) untuk di-X-ray (Geneve Decapsulation & Deep Packet Inspection) sebelum diizinkan masuk ke jalan tol menuju kota target.

```
       +---------------------------------------------------------------------------------------+
       |                                AWS TRANSIT GATEWAY                                    |
       |                                                                                       |
       |   +----------------------------+                     +----------------------------+   |
       |   |   Spoke Route Table        |                     | Post-Inspection Route Table|   |
       |   | 10.0.0.0/8 -> Insp_Attach  |                     | 10.1.0.0/16 -> Spoke_A     |   |
       |   | 0.0.0.0/0  -> Insp_Attach  |                     | 10.2.0.0/16 -> Spoke_B     |   |
       |   +----------------------------+                     +----------------------------+   |
       +-------^--------------------+---------------------------------------^------------------+
               |                    |                                       |
    [Attachment Spoke-A]     [Attachment Insp]                      [Attachment Spoke-B]
               |                    |                                       |
+--------------v-------+    +-------v-------------------------+     +-------v------------------+
| Spoke-A VPC          |    | Central Inspection VPC          |     | Spoke-B VPC              |
| CIDR: 10.1.0.0/16    |    | CIDR: 10.0.0.0/16               |     | CIDR: 10.2.0.0/16        |
|                      |    |                                 |     |                          |
|  +----------------+  |    |  +------------+   +-----------+ |     |  +----------------+      |
|  | Workload EC2   |  |    |  | GWLB Endpt |-->| GWLB & NVA| |     |  | Workload EC2   |      |
|  | 10.1.10.20     |  |    |  | Subnet     |   | Subnet    | |     |  | 10.2.10.50     |      |
|  +--------+-------+  |    |  +-----+------+   +-----+-----+ |     |  +--------^-------+      |
|           |          |    |        ^                |       |     |           |              |
|           v          |    |        |  (GENEVE 6081) |       |     |           |              |
|     [Subnet RT]      |    |        +----------------+       |     |     [Subnet RT]          |
|  0.0.0.0/0 -> TGW    |    |                                 |     |  0.0.0.0/0 -> TGW        |
+----------------------+    +---------------------------------+     +--------------------------+
```

---

### 7. Practical Implementation Code (Production Standards)

Implementasi arsitektur jaringan Hub-and-Spoke berbasis Terraform modular. Konfigurasi ini membangun AWS Transit Gateway, isolasi route table, attachment, dan RAM sharing.

#### `main.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------------------------------------------------------------
# TRANSIT GATEWAY
# -----------------------------------------------------------------------------------
resource "aws_ec2_transit_gateway" "central_tgw" {
  description                     = "Enterprise-Hub-Transit-Gateway"
  amazon_side_asn                 = 64512
  auto_accept_shared_attachments  = "disable"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"

  tags = {
    Name        = "tgw-central-hub-prod"
    Environment = "Production"
    ManagedBy   = "Terraform"
  }
}

# -----------------------------------------------------------------------------------
# TGW ROUTE TABLES (ISOLATION LAYER)
# -----------------------------------------------------------------------------------
resource "aws_ec2_transit_gateway_route_table" "spoke_tgw_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id

  tags = {
    Name = "tgw-rt-spoke-traffic"
  }
}

resource "aws_ec2_transit_gateway_route_table" "post_inspection_tgw_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id

  tags = {
    Name = "tgw-rt-post-inspection"
  }
}

# -----------------------------------------------------------------------------------
# NETWORKING RESOURCE ACCESS MANAGER (RAM) UNTUK SHARING MULTI-ACCOUNT
# -----------------------------------------------------------------------------------
resource "aws_ram_resource_share" "tgw_share" {
  name                      = "ram-share-central-tgw"
  allow_external_principals = false

  tags = {
    Environment = "Production"
  }
}

resource "aws_ram_resource_association" "tgw_ram_association" {
  resource_arn       = aws_ec2_transit_gateway.central_tgw.arn
  resource_share_arn = aws_ram_resource_share.tgw_share.arn
}

resource "aws_ram_principal_association" "org_principal_association" {
  principal          = var.aws_organization_arn
  resource_share_arn = aws_ram_resource_share.tgw_share.arn
}

# -----------------------------------------------------------------------------------
# SPOKE VPC INFRASTRUCTURE SAMPLE (Spoke A)
# -----------------------------------------------------------------------------------
resource "aws_vpc" "spoke_a" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "vpc-spoke-a-prod"
  }
}

resource "aws_subnet" "spoke_a_tgw" {
  count             = 2
  vpc_id            = aws_vpc.spoke_a.id
  cidr_block        = cidrsubnet(aws_vpc.spoke_a.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "subnet-spoke-a-tgw-attachment-${count.index + 1}"
  }
}

resource "aws_subnet" "spoke_a_workload" {
  count             = 2
  vpc_id            = aws_vpc.spoke_a.id
  cidr_block        = cidrsubnet(aws_vpc.spoke_a.cidr_block, 4, count.index + 1)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "subnet-spoke-a-workload-${count.index + 1}"
  }
}

# -----------------------------------------------------------------------------------
# TGW ATTACHMENT SPOKE A
# -----------------------------------------------------------------------------------
resource "aws_ec2_transit_gateway_vpc_attachment" "spoke_a_attachment" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  vpc_id             = aws_vpc.spoke_a.id
  subnet_ids         = aws_subnet.spoke_a_tgw[*].id

  dns_support  = true
  ipv6_support = false

  transit_gateway_default_route_table_association = false
  transit_gateway_default_route_table_propagation = false

  tags = {
    Name = "tgw-attachment-spoke-a"
  }
}

# Asosiasi Attachment Spoke-A ke Spoke TGW Route Table
resource "aws_ec2_transit_gateway_route_table_association" "spoke_a_association" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.spoke_a_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.spoke_tgw_rt.id
}

# Propagasi Spoke-A ke Post-Inspection TGW Route Table
resource "aws_ec2_transit_gateway_route_table_propagation" "spoke_a_to_post_inspection" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.spoke_a_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.post_inspection_tgw_rt.id
}

# -----------------------------------------------------------------------------------
# ROUTING DI LEVEL VPC SPOKE-A MENUJU TGW
# -----------------------------------------------------------------------------------
resource "aws_route_table" "spoke_a_workload_rt" {
  vpc_id = aws_vpc.spoke_a.id

  route {
    cidr_block         = "0.0.0.0/0"
    transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  }

  tags = {
    Name = "rt-spoke-a-workload"
  }
}

resource "aws_route_table_association" "spoke_a_workload_assoc" {
  count          = 2
  subnet_id      = aws_subnet.spoke_a_workload[count.index].id
  route_table_id = aws_route_table.spoke_a_workload_rt.id
}

data "aws_availability_zones" "available" {
  state = "available"
}
```

#### `scp-enforce-guardrails.json`
Kebijakan Service Control Policy untuk mengunci *configuration drift* pada level akun Spoke:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyDisablingSecurityHubAndGuardDuty",
      "Effect": "Deny",
      "Action": [
        "securityhub:DisableSecurityHub",
        "securityhub:DeleteMembers",
        "guardduty:DeleteDetector",
        "guardduty:DisassociateFromMasterAccount",
        "guardduty:StopMonitoringMembers"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyDirectInternetAccessInSpokes",
      "Effect": "Deny",
      "Action": [
        "ec2:AttachInternetGateway",
        "ec2:CreateInternetGateway",
        "ec2:CreateNatGateway"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:PrincipalARN": "arn:aws:iam::*:role/aws-service-role/organizations.amazonaws.com/AWSServiceRoleForOrganizations"
        }
      }
    },
    {
      "Sid": "DenyLeavingOrganization",
      "Effect": "Deny",
      "Action": [
        "organizations:LeaveOrganization"
      ],
      "Resource": "*"
    }
  ]
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Konteks
Sebuah institusi perbankan digital Tier-1 di Asia Tenggara mengalami akselerasi migrasi microservices dari 4 monolit On-Premises ke AWS. Total akun mencapai 140+ akun AWS dengan kebutuhan transaksi rata-rata 45.000 TPS (*Transactions Per Second*) dan kewajiban audit PCI-DSS Level 1 serta OJK/BI.

#### Masalah Utama
1. **Network Sprawl**: Menggunakan 380+ VPC Peering connections yang tidak terdokumentasi rapi. Batas limit route table VPC (100 rute non-propagated) terlampaui.
2. **Security Compliance Blindspot**: Tidak ada inspeksi trafik *East-West* antar-layanan (misal: core banking payment microservice ke reporting service), yang mengakibatkan temuan kegagalan audit PCI-DSS Requirement 1.3.
3. **Data Exfiltration Risk**: Pengembang memasang NAT Gateway di setiap Spoke VPC, menimbulkan celah kebocoran data (*data exfiltration*) langsung ke internet publik tanpa proxy atau IPS.

#### Solusi Arsitektur
1. **Penerapan Multi-Account Landing Zone**: Menstrukturkan AWS Organizations menjadi OU `Core-Network`, `Security-Tooling`, `Core-Banking`, dan `Digital-Channels`.
2. **Transit Gateway dengan Central Inspection Hub**:
   - Membangun *Central Inspection VPC* dengan 3 pasang active-active AWS Network Firewall lintas Availability Zone.
   - Semua VPC Spoke dicabut NAT Gateway dan Internet Gateway-nya menggunakan SCP (`DenyDirectInternetAccessInSpokes`).
   - Rute default `0.0.0.0/0` dari seluruh akun kerja diarahkan ke TGW Attachment, lalu dipaksa masuk ke AWS Network Firewall untuk filtering IDS/IPS SNORT-compatible.
3. **Optimasi Route 53 Resolver & Endpoints**:
   - Menerapkan PrivateLink terpusat pada *Shared Services VPC* untuk mengakses AWS Secrets Manager, S3, dan DynamoDB, memangkas *NAT Gateway data processing charges*.

#### Hasil Pasca-Implementasi
- Biaya NAT Gateway terpangkas **68%** karena konsolidasi NAT dan perutean endpoint privat.
- Lolos audit PCI-DSS Level 1 tanpa temuan kepatuhan perimeter jaringan.
- Waktu *onboarding* akun AWS microservices baru turun dari 3 minggu menjadi 25 menit menggunakan automasi Terraform via pipeline CI/CD.

---

### 9. Trade-offs (Analisis Kompromi Teknis)

| Pola Arsitektur | Keunggulan (*Pros*) | Kelemahan (*Cons*) | Latensi Rata-rata | Estimasi Biaya | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **VPC Peering Penuh** | Zero hourly charge; tidak ada bandwidth bottle-neck (skala AWS backbone). | Kompleksitas mesh $O(N^2)$; tidak ada transitive routing; manajemen route table berantakan. | Sub-millisecond ($< 1\text{ ms}$) | Sangat Rendah (Hanya charge intra-AZ/inter-AZ data transfer) | Komunikasi intensif antar 2-3 VPC berkecepatan ultra-tinggi (Big Data/ML training). |
| **AWS Transit Gateway (Direct)** | Hub tersentralisasi; isolasi route table mudah; integrasi Hybrid Cloud BGP mulus. | Biaya per attachment ($0.05/jam) + biaya data processing ($0.02/GB); MTU 1500 bytes ke internet. | $\sim 1 - 2\text{ ms}$ | Menengah | Arsitektur multi-account standar skala medium hingga enterprise (> 5 VPC). |
| **TGW + GWLB / Network Firewall** | Stateful Deep Packet Inspection (DPI); isolasi ancaman East-West & North-South maksimal; PCI-DSS compliant. | Kompleksitas perutean route table sangat tinggi; rawan *asymmetric routing*; bottleneck performa NVA jika underspecified. | $\sim 3 - 5\text{ ms}$ | Tinggi (TGW fees + GWLB fees + Firewall hourly & processing fees) | Enterprise regulated (FinTech, Perbankan, Pemerintahan, Layanan Kesehatan). |
| **AWS PrivateLink (Interface Endpoints)** | Mengisolasi akses API/Service ke level layer-4 (TCP); tidak butuh routing TGW; IP privat di subnet lokal. | Biaya per-ENI endpoint per-AZ per-bulan ($0.01/jam/AZ) membengkak jika dibuat di tiap Spoke VPC tanpa strategi sentralisasi. | Sangat Rendah ($< 1\text{ ms}$) | Menengah hingga Tinggi (berdasarkan jumlah VPC dan Service) | Konsumsi SaaS eksternal atau microservices internal lintas VPC independen secara strictly isolated. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Asymmetric Routing pada Central Inspection
- **Gejala**: Koneksi TCP antar Spoke VPC terputus secara acak setelah *SYN-ACK*, atau transfer payload besar langsung mengalami hang (*connection timeout*).
- **Penyebab**: Paket `SYN` masuk melalui Firewall Node di AZ-a, tetapi paket balasan `ACK` dari Spoke tujuan dialihkan oleh TGW ke Firewall Node di AZ-b. Firewall stateful membuang paket karena tidak memiliki state tabel TCP flow tersebut.
- **Solusi**: Pastikan *Transit Gateway Appliance Mode* diaktifkan pada attachment Inspection VPC:
  ```bash
  aws ec2 modify-transit-gateway-vpc-attachment \
      --transit-gateway-attachment-id tgw-attach-0123456789abcdef0 \
      --options ApplianceModeSupport=enable
  ```

#### Kesalahan 2: Path MTU Discovery (PMTUD) Black Hole
- **Gejala**: Ping dengan paket kecil lolos, namun handshake TLS / transmisi HTTPS gagal secara diam-diam (*silent drop*).
- **Penyebab**: TGW mendukung MTU 8500 (Jumbo Frames) antar-VPC, namun koneksi menuju Internet Gateway atau Direct Connect dibatasi ke MTU 1500. ICMP Type 3 Code 4 (*Fragmentation Needed*) diblokir oleh Security Group yang terlalu ketat, mematikan mekanisme PMTUD.
- **Solusi**: Selalu izinkan ICMP Type 3 Code 4 pada Security Group workload dan firewall:
  ```hcl
  resource "aws_security_group_rule" "allow_pmtud" {
    type              = "ingress"
    from_port         = 3
    to_port           = 4
    protocol          = "icmp"
    cidr_blocks       = ["0.0.0.0/0"]
    security_group_id = aws_security_group.workload.id
  }
  ```

#### Panduan Troubleshooting Langkah-demi-Langkah
1. **Validasi VPC Flow Logs**:
   Gunakan query CloudWatch Logs Insights untuk mendeteksi *packet drops* di level interface ENI TGW:
   ```sql
   fields @timestamp, srcAddr, dstAddr, srcPort, dstPort, protocol, packets, bytes, action
   | filter action = 'REJECT'
   | filter srcAddr = '10.1.10.20'
   | sort @timestamp desc
   | limit 50
   ```
2. **Analisis Rute Simetris Menggunakan AWS Reachability Analyzer**:
   Eksekusi CLI Reachability Analyzer untuk memverifikasi hop network secara deterministik:
   ```bash
   aws ec2-network-path create-route-analysis \
       --source i-01a2b3c4d5e6f7g8h \
       --destination i-09h8g7f6e5d4c3b2a
   ```

---

### 11. Best Practices (Production Checklist)

| Kategori | Parameter Validasi | Standar Implementasi | Status |
| :--- | :--- | :--- | :--- |
| **Governance** | Service Control Policies | Root OU menerapkan `DenyRootUserAccess` dan `DenyDisablingCloudTrail`. | [ ] |
| **Governance** | IAM Boundaries | Seluruh developer IAM Role memiliki `PermissionsBoundary` wajib. | [ ] |
| **Networking** | CIDR Strategy | Skema CIDR non-overlapping teralokasi via AWS IPAM (IP Address Manager). | [ ] |
| **Networking** | TGW Design | Matikan `auto_accept_shared_attachments` & `default_route_table_association`. | [ ] |
| **High Availability** | Cross-AZ Redundancy | Minimal 2 AZ untuk TGW attachments, GWLB, dan NAT Gateway. | [ ] |
| **High Availability** | Appliance Mode | `ApplianceModeSupport` aktif pada semua attachment security VPC. | [ ] |
| **Security** | Central Inspection | Seluruh Egress ke publik wajib melintasi Network Firewall IPS stateful engine. | [ ] |
| **Security** | VPC Endpoints | S3 dan DynamoDB menggunakan Gateway Endpoints (bebas biaya transfer). | [ ] |
| **Observability** | Flow Logging | VPC Flow Logs aktif di level VPC (bukan subnet) dengan format custom agregasi latency. | [ ] |
| **FinOps** | Data Transfer Audit | Alert CloudWatch terpasang jika akumulasi data transfer inter-AZ melebihi ambang batas. | [ ] |

---

### 12. Hands-on Practice: Membangun Multi-VPC Transit Hub dengan Centralized Inspection

Simpan seluruh file berikut dalam folder direktori: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── versions.tf
├── variables.tf
├── main.tf
├── outputs.tf
└── terraform.tfvars
```

#### Langkah-langkah Implementasi

##### Langkah 1: Inisialisasi Definisi Variabel
Tulis file `variables.tf`:
```hcl
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}
```

##### Langkah 2: Kode Topologi Jaringan Lengkap
Tulis file `main.tf` untuk mengeksekusi pembangunan Spoke VPC, Transit Gateway, dan verifikasi rute:
```hcl
# 1. AWS Transit Gateway
resource "aws_ec2_transit_gateway" "tgw" {
  description                     = "Core-Hub-TGW"
  amazon_side_asn                 = 64512
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  tags = {
    Name = "tgw-core-prod"
  }
}

# 2. Spoke VPC 1 (Order Service)
resource "aws_vpc" "spoke_order" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name = "vpc-order-service"
  }
}

resource "aws_subnet" "spoke_order_workload" {
  vpc_id            = aws_vpc.spoke_order.id
  cidr_block        = "10.10.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "subnet-order-workload-a" }
}

resource "aws_subnet" "spoke_order_tgw" {
  vpc_id            = aws_vpc.spoke_order.id
  cidr_block        = "10.10.250.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "subnet-order-tgw-attachment-a" }
}

# 3. Spoke VPC 2 (Payment Service)
resource "aws_vpc" "spoke_payment" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name = "vpc-payment-service"
  }
}

resource "aws_subnet" "spoke_payment_workload" {
  vpc_id            = aws_vpc.spoke_payment.id
  cidr_block        = "10.20.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "subnet-payment-workload-a" }
}

resource "aws_subnet" "spoke_payment_tgw" {
  vpc_id            = aws_vpc.spoke_payment.id
  cidr_block        = "10.20.250.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "subnet-payment-tgw-attachment-a" }
}

# 4. Attachments
resource "aws_ec2_transit_gateway_vpc_attachment" "order_attachment" {
  transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  vpc_id             = aws_vpc.spoke_order.id
  subnet_ids         = [aws_subnet.spoke_order_tgw.id]
  tags               = { Name = "attach-order-vpc" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "payment_attachment" {
  transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  vpc_id             = aws_vpc.spoke_payment.id
  subnet_ids         = [aws_subnet.spoke_payment_tgw.id]
  tags               = { Name = "attach-payment-vpc" }
}

# 5. Routing Engine TGW
resource "aws_ec2_transit_gateway_route_table" "common_spoke_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  tags               = { Name = "tgw-rt-common-spokes" }
}

resource "aws_ec2_transit_gateway_route_table_association" "order_assoc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.order_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.common_spoke_rt.id
}

resource "aws_ec2_transit_gateway_route_table_association" "payment_assoc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.payment_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.common_spoke_rt.id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "order_prop" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.order_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.common_spoke_rt.id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "payment_prop" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.payment_attachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.common_spoke_rt.id
}

# 6. VPC Route Table Updates
resource "aws_route_table" "order_workload_rt" {
  vpc_id = aws_vpc.spoke_order.id
  route {
    cidr_block         = "10.0.0.0/8"
    transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  }
  tags = { Name = "rt-order-workload" }
}

resource "aws_route_table_association" "order_workload_assoc" {
  subnet_id      = aws_subnet.spoke_order_workload.id
  route_table_id = aws_route_table.order_workload_rt.id
}

resource "aws_route_table" "payment_workload_rt" {
  vpc_id = aws_vpc.spoke_payment.id
  route {
    cidr_block         = "10.0.0.0/8"
    transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  }
  tags = { Name = "rt-payment-workload" }
}

resource "aws_route_table_association" "payment_workload_assoc" {
  subnet_id      = aws_subnet.spoke_payment_workload.id
  route_table_id = aws_route_table.payment_workload_rt.id
}
```

##### Langkah 3: Eksekusi Perintah Deployment
Jalankan di shell terminal:
```bash
cd hands-on/m02/
terraform init
terraform validate
terraform plan -out=tfplan.binary
terraform apply tfplan.binary
```

##### Langkah 4: Validasi & Pengujian Routing TGW
Verifikasi bahwa rute Order VPC dan Payment VPC terpropagasi sempurna di dalam TGW:
```bash
TGW_RT_ID=$(terraform output -raw tgw_route_table_id 2>/dev/null || aws ec2 describe-transit-gateway-route-tables --filters "Name=tag:Name,Values=tgw-rt-common-spokes" --query "TransitGatewayRouteTables[0].TransitGatewayRouteTableId" --output text)

aws ec2 search-transit-gateway-routes \
    --transit-gateway-route-table-id $TGW_RT_ID \
    --filters "Name=state,Values=active"
```
Output yang diharapkan harus menunjukkan rute CIDR `10.10.0.0/16` dan `10.20.0.0/16` dengan status `propagated`.

---

### 13. Exercises

#### Level Easy
Buat Terraform resource untuk mengonfigurasi AWS VPC Gateway Endpoint untuk Amazon S3 pada `spoke_order` VPC. Buktikan melalui rute lokal bahwa trafik menuju S3 (`pl-xxxxxxx`) tidak melintasi TGW.

#### Level Medium
Ubah arsitektur jaringan pada `hands-on/m02/` sehingga trafik antara Spoke Order dan Spoke Payment **tidak diizinkan berkomunikasi langsung** (Isolasi antar spoke), namun keduanya hanya boleh berkomunikasi ke subnet `Shared-Services-VPC` (`10.50.0.0/16`). Rancang pemisahan TGW Route Table untuk mencapai tujuan ini tanpa Security Group.

#### Level Hard
Rancang dan tulis modul Terraform untuk *Centralized Egress Architecture* yang menyertakan auto-scaled NAT Gateway pool di Inspection VPC. Seluruh trafik `0.0.0.0/0` dari Spoke A dan Spoke B harus dirutekan melintasi TGW $\rightarrow$ Inspection VPC $\rightarrow$ Network Firewall $\rightarrow$ NAT Gateway $\rightarrow$ Internet Gateway. Tangani skenario failover Multi-AZ secara deterministik untuk menjamin *zero asymmetric drop*.

---

### 14. Challenge: Arsitektur Stateful Failover Lintas Region

#### Deskripsi Masalah
Perusahaan Anda memiliki footprint multi-region (`ap-southeast-1` Utama dan `ap-southeast-3` Disaster Recovery). Anda diwajibkan menyusun topologi interkoneksi transit menggunakan TGW Peering.

#### Batasan Operasional
1. Seluruh trafik Egress dari Region Jakarta (`ap-southeast-3`) harus diinspeksi secara terpusat oleh Network Firewall yang berada di Region Singapura (`ap-southeast-1`) melalui TGW Inter-Region Peering secara privat.
2. Latensi inter-region tidak boleh menyebabkan koneksi putus akibat packet reordering atau MTU degradation.
3. Apabila jalur TGW Peering putus total, Region Jakarta harus secara otomatis mengalihkan (*failover*) rute ke *Local Egress VPC* di Jakarta dalam waktu $\le 30$ detik tanpa intervensi manual engineer.
4. Tuliskan arsitektur perutean, kalkulasi overhead Geneve/MTU sizing, dan failover automation logic (menggunakan Route 53 Application Recovery Controller atau TGW Dynamic BGP Route Injection).

---

### 15. Evaluasi Pemahaman (Quiz)

#### Skenario Dasar (5 Soal)

1. **Apa perbedaan mendasar antara Service Control Policy (SCP) dan IAM Policy biasa?**
   - A. SCP memberikan izin spesifik pada resources, IAM membatasi.
   - B. SCP bertindak sebagai guardrail batas izin maksimum di level organisasi/OU, bukan pemberi izin langsung.
   - C. SCP hanya bisa diterapkan ke resource Amazon S3.
   - D. IAM policy selalu meng-override apapun yang didefinisikan di SCP.
   *Jawaban yang benar: B. Penjelasan: SCP membatasi batas kewenangan maksimum (permission boundary). Tanpa adanya allow di IAM, akses tetap tertolak; jika SCP menolak (Deny), IAM tidak bisa memberikan izin.*

2. **Berapa batas kapasitas MTU default saat paket melintasi AWS Transit Gateway menuju Internet Gateway eksternal?**
   - A. 9001 bytes
   - B. 8500 bytes
   - C. 1500 bytes
   - D. 65535 bytes
   *Jawaban yang benar: C. Penjelasan: Meskipun TGW mendukung Jumbo Frame hingga 8500 bytes untuk trafik intra-VPC/Direct Connect, trafik yang melintasi internet publik selalu dibatasi oleh MTU standar 1500 bytes.*

3. **Komponen TGW manakah yang menentukan ke mana paket diteruskan setelah diterima dari VPC Attachment?**
   - A. TGW Attachment Subnet
   - B. TGW Route Table Association
   - C. TGW Route Table Propagation
   - D. VPC DHCP Options Set
   *Jawaban yang benar: B. Penjelasan: Association menentukan Route Table TGW mana yang digunakan untuk lookup rute saat paket datang dari attachment tersebut.*

4. **Protokol enkapsulasi apa yang digunakan oleh AWS Gateway Load Balancer untuk menyematkan metadata paket asli menuju target appliances?**
   - A. VXLAN (Port 4789)
   - B. GENEVE (UDP Port 6081)
   - C. GRE (IP Protocol 47)
   - D. IPsec (ESP Port 50)
   *Jawaban yang benar: B. Penjelasan: AWS GWLB menggunakan protokol enkapsulasi GENEVE pada UDP port 6081 untuk menyematkan metadata konteks (seperti Elastic Network Interface target).*

5. **Manakah VPC Endpoint berikut yang TIDAK memakan biaya per jam dan diimplementasikan via entri rute tabel VPC secara langsung?**
   - A. S3 Interface Endpoint
   - B. DynamoDB Gateway Endpoint
   - C. EC2 Messages Interface Endpoint
   - D. Secrets Manager Interface Endpoint
   *Jawaban yang benar: B. Penjelasan: Gateway Endpoints (hanya tersedia untuk S3 dan DynamoDB) gratis dan dikonfigurasi langsung sebagai target rute di VPC Route Table.*

---

#### Skenario Menengah (5 Soal)

6. **Sebuah Spoke VPC A ingin berkomunikasi dengan Spoke VPC B melalui TGW. Rute pada Spoke VPC A sudah mengarah ke TGW. TGW Route Table Association sudah benar, namun koneksi tetap timeout. Penyebab paling logis pada arsitektur TGW adalah:**
   - A. Spoke VPC B belum diasosiasikan dengan IAM Role yang sesuai.
   - B. CIDR Spoke VPC B belum dipropagasikan (*propagation*) ke dalam TGW Route Table yang diasosiasikan dengan Spoke VPC A.
   - C. Security Group Spoke VPC A secara otomatis memblokir TGW ID.
   - D. VPC Peering belum diaktifkan di dalam TGW.
   *Jawaban yang benar: B. Penjelasan: Agar TGW tahu jalur menuju VPC B, rute VPC B harus dipropagasikan atau ditambahkan secara statis ke TGW Route Table milik Spoke VPC A.*

7. **Fitur apa yang wajib diaktifkan pada Transit Gateway VPC Attachment menuju Central Inspection VPC untuk mencegah putusnya koneksi TCP stateful akibat asymmetric return traffic?**
   - A. DNS Support
   - B. Equal-Cost Multi-Path (ECMP)
   - C. Appliance Mode Support
   - D. Flow Logs
   *Jawaban yang benar: C. Penjelasan: TGW Appliance Mode menjamin bahwa paket bolak-balik (request & response) dalam satu koneksi TCP selalu diproses oleh ENI attachment di Availability Zone yang sama.*

8. **Organisasi Anda memiliki SCP di level Root OU: `Deny ec2:RunInstances with Condition: Region != ap-southeast-1`. Admin di akun anak membuat IAM Policy dengan `Allow ec2:* on *`. Apa yang terjadi ketika user menjalankan EC2 di `us-east-1`?**
   - A. Instance berhasil dibuat karena IAM Policy akun anak memiliki hak Administrator.
   - B. Permintaan ditolak (*Implicit Deny*).
   - C. Permintaan ditolak (*Explicit Deny* dari SCP).
   - D. Instansiasi tertunda menunggu approval AWS Support.
   *Jawaban yang benar: C. Penjelasan: Explicit deny pada SCP di level Root mengevaluasi sebelum IAM dan membatalkan semua allow yang ada di akun anak.*

9. **Jika Anda mendesain transfer data ultra-high throughput (100 Gbps+) antar-aplikasi di dua VPC dalam satu AZ yang sama, solusi manakah yang memberikan performa tertinggi dengan latensi dan biaya paling rendah?**
   - A. AWS Transit Gateway
   - B. Gateway Load Balancer
   - C. Local VPC Peering
   - D. Site-to-Site VPN dengan ECMP
   *Jawaban yang benar: C. Penjelasan: VPC Peering beroperasi pada layer routing jaringan fisik AWS tanpa intermediary device (seperti TGW/VPN), menghasilkan latensi terendah, bandwidth tertinggi, dan tanpa biaya processing per GB jika dalam AZ yang sama.*

10. **Bagaimana cara mencegah DNS split-horizon issues saat Spoke VPC perlu me-resolve private domain internal yang dikelola terpusat di Shared Services VPC?**
    - A. Memasang file `/etc/hosts` di seluruh EC2 via Ansible.
    - B. Menggunakan Amazon Route 53 Resolver Rules (Outbound/Inbound) yang di-share via AWS RAM ke seluruh organisasi.
    - C. Membuka port DNS 53 langsung ke internet melalui Internet Gateway.
    - D. Mengaktifkan IGW di seluruh VPC spoke.
    *Jawaban yang benar: B. Penjelasan: Route 53 Resolver Rules yang dibagikan melalui RAM memungkinkan seluruh Spoke VPC meneruskan request lookup internal secara deterministik ke central DNS Resolver.*

---

#### Analisis Kasus Produksi Mendalam (3 Skenario)

11. **Skenario Kasus 1: Blackhole Trafik Pasca-Migrasi Firewall**
    *Insiden*: Tim DevOps memigrasikan pool Network Firewall dari VPC lokal ke Central Inspection Hub menggunakan TGW. Setelah rute default Spoke diubah ke TGW, semua trafik HTTPS keluar ke internet mengalami intermittent connection failure (sebagian website external drop, sebagian berhasil).
    *Data Analisis*: `traceroute` menunjukkan paket berhasil mencapai firewall, namun respons terpotong pada payload berukuran di atas 1460 bytes.
    *Pertanyaan*: Apa root cause dari kegagalan ini dan bagaimana langkah remediasinya di level enterprise?
    *Jawaban Komprehensif*:
    - **Akar Masalah (Root Cause)**: Masalah terjadi akibat *Path MTU Discovery (PMTUD) Black Hole*. Jaringan lokal Spoke menggunakan MTU 9001 (Jumbo Frames). Saat paket besar melintasi TGW menuju firewall dan hendak diteruskan ke Internet Gateway (yang dibatasi MTU 1500), router mencoba mengirimkan ICMP Type 3, Code 4 ("Fragmentation Needed and DF set"). Firewall atau Security Group memblokir trafik inbound ICMP tersebut, sehingga source instance tidak pernah menurunkan TCP MSS (*Maximum Segment Size*).
    - **Remediasi**:
      1. Buka aturan ingress Security Group pada seluruh instance dan appliance untuk memperbolehkan ICMP Type 3 Code 4 dari `0.0.0.0/0`.
      2. Terapkan konfigurasi *MSS Clamping* (TCP Maximum Segment Size) pada level Network Firewall / NVA ke nilai 1360 atau 1420 bytes untuk mengantisipasi overhead GENEVE tunnel (64 bytes).

12. **Skenario Kasus 2: Lonjakan Biaya Misterius (Data Transfer Cost Explosion)**
    *Insiden*: FinOps mendeteksi lonjakan biaya tagihan sebesar $14,000 per bulan pada kategori *AWS Data Transfer* setelah arsitektur microservices dideploy di 15 VPC Spoke yang terhubung ke TGW.
    *Data Analisis*: 80% volume data adalah penulisan event streaming dari aplikasi Spoke menuju cluster Amazon Kinesis Data Streams dan Amazon S3 yang berada di region yang sama.
    *Pertanyaan*: Mengapa biaya TGW melonjak drastis dan bagaimana arsitektur yang benar untuk mengeliminasi beban biaya tersebut tanpa mengorbankan keamanan?
    *Jawaban Komprehensif*:
    - **Akar Masalah (Root Cause)**: Seluruh trafik SDK AWS menuju S3 dan Kinesis dirutekan melalui rute default TGW Attachment ($0.02 per GB transit data processing charge) dan kemudian diproses lagi keluar via Central NAT Gateway ($0.045 per GB). Ini menciptakan *double data processing penalty* untuk trafik internal AWS.
    - **Remediasi**:
      1. Deploy **VPC Gateway Endpoint** untuk Amazon S3 langsung di setiap Spoke VPC (gratis pemrosesan, rute langsung di-inject ke Spoke Route Table tanpa lewat TGW).
      2. Buat **Interface VPC Endpoint (AWS PrivateLink)** terpusat di Shared Services VPC untuk Kinesis, atau deploy langsung di VPC Spoke jika data throughput masif, untuk memotong jalur trafik agar tidak bolak-balik melintasi TGW data processing engine.

13. **Skenario Kasus 3: Kebocoran Routing Antar-Tenant (Cross-Tenant Route Leak)**
    *Insiden*: Pada arsitektur Multi-Tenant SaaS, Tenant A (VPC 10.100.0.0/16) berhasil mengirim paket ping dan mengakses endpoint database privat milik Tenant B (VPC 10.200.0.0/16). Keduanya terhubung ke TGW yang sama. Tim audit keamanan membekukan status rilis produksi.
    *Data Analisis*: TGW dibuat menggunakan konfigurasi default AWS Management Console.
    *Pertanyaan*: Kesalahan fundamental apa yang dilakukan saat provisioning TGW dan bagaimana restrukturisasi Terraform untuk menjamin isolasi mutlak (*complete segment isolation*)?
    *Jawaban Komprehensif*:
    - **Akar Masalah (Root Cause)**: TGW dibuat dengan opsi `default_route_table_association = "enable"` dan `default_route_table_propagation = "enable"`. Akibatnya, TGW hanya memiliki 1 default flat route table di mana setiap VPC yang di-attach akan saling mempropagasi rute CIDR-nya secara otomatis ke VPC lain (menciptakan full mesh routing tanpa batas isolasi).
    - **Remediasi**:
      1. Matikan opsi default route table association dan propagation (`disable`).
      2. Buat pola *Dedicated TGW Route Table per Tenant Domain* (misal: `tgw-rt-tenant-a`, `tgw-rt-tenant-b`).
      3. Asosiasikan attachment Tenant A hanya ke `tgw-rt-tenant-a`. Jangan pernah lakukan propagasi rute Tenant B ke dalam route table Tenant A.
      4. Kedua route table tenant hanya boleh mengarah ke *Shared Egress/Services Attachment*, menjamin *Zero Trust Lateral Movement* antar-tenant.

---

### 16. Summary
Arsitektur fondasi AWS skala enterprise menuntut pergeseran paradigma dari *single-account sprawl* menuju *governed multi-account mesh*. 
1. **Tata Kelola SCP**: AWS Organizations dan SCP bertindak sebagai guardrail non-negotiable yang berada di luar kendali administrator lokal akun anak.
2. **Sentralisasi Hub Jaringan**: AWS Transit Gateway (TGW) menyediakan kapabilitas routing layer-3 multi-VPC yang fleksibel dengan isolasi komprehensif melalui segregasi TGW Route Tables.
3. **Inspeksi Simetris**: Pemanfaatan GWLB dan Network Firewall menyelesaikan kendala inspeksi paket *East-West* dan *North-South* dengan mempertahankan source IP utuh melalui enkapsulasi GENEVE dan penegakan *Appliance Mode* untuk menjamin simetri koneksi TCP.
4. **FinOps & Performansi**: Skema peering, endpoint interface/gateway, dan alokasi rute harus dirancang cermat untuk meminimalkan latensi jaringan dan mencegah lonjakan biaya *Data Transfer Processing* yang tidak perlu di lingkungan produksi skala besar.