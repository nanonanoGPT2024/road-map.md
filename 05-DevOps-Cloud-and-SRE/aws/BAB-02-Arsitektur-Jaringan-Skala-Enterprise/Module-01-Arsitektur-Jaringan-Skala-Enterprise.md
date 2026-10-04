# Modul 01: Arsitektur Jaringan Skala Enterprise di AWS

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mendesain topologi jaringan multi-VPC dan multi-account yang scalable, fault-tolerant, dan secure sesuai standar AWS Well-Architected Framework.
- Mengonfigurasi dan mengoptimalkan segmentasi VPC, kalkulasi subnetting (CIDR allocation), Route Tables, Internet Gateway (IGW), dan NAT Gateway dengan prinsip high availability.
- Mengimplementasikan routing skala enterprise menggunakan AWS Transit Gateway (TGW) dengan isolasi domain (route table association & propagation) dan membedakannya secara arsitektural dari VPC Peering.
- Mengintegrasikan konektivitas hybrid on-premises menggunakan AWS Direct Connect (DX), Direct Connect Gateway (DXGW), dan VPN Backup.
- Membangun arsitektur hybrid DNS yang andal menggunakan Amazon Route 53 Resolver (Inbound/Outbound Endpoints) dan Private Hosted Zones.
- Mengamankan traffic jaringan lapis dalam (defense-in-depth) menggunakan kombinasi Security Groups, Network ACLs, AWS Network Firewall, dan Gateway Load Balancer (GWLB) untuk inspeksi traffic East-West dan North-South secara inline tanpa asimetris routing.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Model referensi OSI 7-Layer dan protokol TCP/IP dasar (khususnya Layer 3 Network, Layer 4 Transport, dan Layer 7 Application).
- Notasi CIDR (Classless Inter-Domain Routing) dan alokasi IPv4 privat berdasarkan RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- Konsep dasar cloud computing: Region, Availability Zone (AZ), IAM policies, serta pengoperasian AWS Management Console dan AWS CLI dasar.
- Pemahaman dasar Infrastructure as Code (IaC) menggunakan HashiCorp Terraform syntax HCL.

---

## 3. Concept
Arsitektur jaringan enterprise di AWS bukan sekadar menghubungkan EC2 ke internet, melainkan mendesain fondasi komunikasi data terisolasi, terkontrol, terenkripsi, dan auditable antar ribuan workload yang tersebar di puluhan akun AWS dan data center on-premises.

Komponen inti meliputi:
1. **Virtual Private Cloud (VPC)**: Jaringan virtual privat yang terisolasi secara logis pada AWS cloud.
2. **Subnetting & Reserved IPs**: Pemotongan blok CIDR ke dalam subnet per Availability Zone. AWS mereservasi 5 IP address pada setiap subnet (Host ID .0, .1, .2, .3, dan .255).
3. **Route Tables & Gateways**: Pengaturan forwarding table deterministik untuk mengarahkan rute traffic keluar/masuk via IGW, NAT Gateway, Egress-Only IGW, VPC Endpoints, atau Peering/TGW.
4. **Transit Gateway (TGW)**: Hub router regional Layer 3 yang menghubungkan ribuan VPC dan on-premises networks melalui model arsitektur hub-and-spoke.
5. **Direct Connect (DX)**: Koneksi fisik dedicated dari on-premises ke AWS bypass internet publik dengan latensi deterministik dan throughput konsisten.
6. **Route 53 Resolver**: Komponen conditional forwarder DNS untuk menjembatani resolusi nama domain antara Active Directory / BIND on-premises dan AWS Route 53 Private Hosted Zones.
7. **Security Layering (SG, NACL, Network Firewall, GWLB)**: Pertahanan berlapis dari stateless filtering (NACL), stateful instance filtering (Security Groups), hingga deep packet inspection (DPI) Layer 7 dan intrusion prevention system (IPS) menggunakan AWS Network Firewall yang diinjeksi via GWLB (Geneve encapsulation).

---

## 4. Why
Mengapa arsitektur jaringan tingkat enterprise di AWS memerlukan pendekatan TGW, Centralized Inspection, dan Dedicated Hybrid Connectivity daripada sekadar VPC Peering sederhana?

- **Pencegahan Mesh Explosion**: VPC Peering memiliki batasan *non-transitive routing*. Jika terdapat 50 VPC yang saling terhubung, diperlukan $\frac{n(n-1)}{2} = \frac{50 \times 49}{2} = 1.225$ koneksi peering. Pengelolaan routing table pada skala ini mustahil dilakukan secara manual tanpa inkonsistensi rute. TGW mengubah kompleksitas $O(n^2)$ menjadi hub-and-spoke $O(n)$ dengan hanya 50 attachment.
- **Kepatuhan Regulasi & Security Compliance**: Standar industri (PCI-DSS, ISO 27001, HIPAA) mewajibkan seluruh traffic lintas zona (East-West) maupun keluar ke internet (North-South) melewati Deep Packet Inspection (DPI) dan IDS/IPS tersentralisasi.
- **IP Address Exhaustion**: Tanpa perencanaan IP Address Management (IPAM) dan CIDR carving yang ketat, perusahaan rentan mengalami kehabisan IP privat atau tumpang tindih (overlapping CIDRs) saat akuisisi/merger entitas bisnis lain.
- **Biaya & Redundansi**: Penggunaan NAT Gateway di setiap VPC menguras biaya operational base per jam ($0.045/hour + data transfer fee). Mengonsolidasikan egress point melalui Inspection/Egress VPC terpusat via TGW menekan TCO secara drastis pada skala ratusan VPC.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Subnetting dan AWS Reserved IP Addresses
Ketika Anda mengalokasikan subnet, misalnya `10.100.1.0/24` (total 256 alamat IP), AWS mereservasi secara permanen 5 IP address pertama dan terakhir yang tidak dapat digunakan oleh instance atau load balancer:
- `10.100.1.0`: Network address.
- `10.100.1.1`: Direservasi oleh AWS untuk VPC router default gateway.
- `10.100.1.2`: Direservasi oleh AWS untuk pemetaan DNS server (AmazonProvidedDNS / Route 53 Resolver IP di base CIDR + 2).
- `10.100.1.3`: Direservasi oleh AWS untuk kebutuhan masa depan (future use).
- `10.100.1.255`: Network broadcast address (AWS VPC tidak mendukung broadcast fisik, traffic dialihkan secara virtual unicast).
*Jumlah IP usable pada CIDR /24 adalah $256 - 5 = 251$ alamat IP.*

### 5.2 Stateful vs Stateless: Security Groups vs NACLs
Perbedaan mendasar arsitektur filtering di AWS:
- **Security Groups (Stateful)**:
  - Beroperasi pada level Network Interface (ENI).
  - Jika inbound request diizinkan (misal TCP 443), response return traffic otomatis diizinkan keluar kembali tanpa memedulikan outbound rules.
  - Tidak memiliki rule `DENY` eksplisit; semua traffic di-drop secara implisit kecuali didefinisikan `ALLOW`.
  - Evaluasi seluruh rules dilakukan secara komprehensif sebelum mengambil keputusan.
- **Network Access Control Lists / NACLs (Stateless)**:
  - Beroperasi pada boundary Subnet.
  - Memproses traffic dua arah secara independen. Jika inbound rule mengizinkan port 80/443, outbound rule **wajib** secara eksplisit mengizinkan return traffic pada rentang **ephemeral ports** (Linux: `32768-60999`, Windows/AWS default: `1024-65535`).
  - Mendukung eksplisit `ALLOW` dan `DENY`.
  - Aturan dievaluasi secara sekuensial berdasarkan nomor urut (Rule Number terkecil dieksekusi lebih dulu).

### 5.3 AWS Transit Gateway (TGW) Architecture
AWS Transit Gateway beroperasi sebagai Regional Virtual Router Layer 3:
- **Attachment**: TGW dihubungkan ke VPC menggunakan Transit Gateway Elastic Network Interface (TGW-ENI) pada setiap AZ yang dipilih.
- **Association**: Setiap attachment (VPC/DXGW/VPN) diasosiasikan secara eksklusif ke tepat **satu** TGW Route Table untuk menentukan tabel mana yang dipakai saat paket datang dari VPC tersebut.
- **Propagation**: Rute dari suatu attachment dapat dipropagasi (didaftarkan) ke **satu atau lebih** TGW Route Table.
- **Isolasi Domain**: Dengan memisahkan TGW Route Table, kita dapat membuat segmentasi ketat:
  - *Prod Route Table*: Tidak memiliki rute ke Dev VPC.
  - *Dev Route Table*: Terisolasi dari Prod VPC.
  - *Inspection Route Table*: Mengarahkan `0.0.0.0/0` dan CIDR internal ke Network Firewall / GWLB.

### 5.4 AWS Direct Connect (DX) & Hybrid Routing
Direct Connect menyediakan pipa fisik 1Gbps, 10Gbps, atau 100Gbps:
- **Dedicated Connection**: Port fisik dedicated langsung dialokasikan ke pelanggan.
- **Hosted Connection**: Port dialokasikan melalui partner AWS APN.
- **Virtual Interfaces (VIF)**:
  - *Private VIF*: Menghubungkan ke single VPC (via VGW). Tidak mendukung koneksi multi-VPC atau multi-region secara langsung.
  - *Transit VIF*: Menghubungkan ke AWS Direct Connect Gateway (DXGW) yang selanjutnya dihubungkan ke Transit Gateway (TGW). Solusi standar enterprise untuk hybrid multi-VPC.
  - *Public VIF*: Mengakses layanan publik AWS (S3, DynamoDB, API endpoint publik) via rute BGP peering publik tanpa internet publik.

### 5.5 Amazon Route 53 Resolver (Hybrid DNS)
- Menggunakan IP virtual VPC Resolver (`base_ip + 2`).
- **Inbound Endpoints**: Menyediakan IP privat di VPC yang dapat ditarget oleh on-premises DNS forwarder (misal: Windows DNS / BIND) untuk meresolusi domain internal AWS (`*.internal.corp`).
- **Outbound Endpoints & Rules**: Meneruskan query DNS dari VPC untuk nama domain on-premises (`*.corp.local`) langsung ke target IP DNS Server on-premises melalui VPN atau Direct Connect.

### 5.6 Gateway Load Balancer (GWLB) & AWS Network Firewall
- **GWLB**: Menggunakan protokol **Geneve (port 6081)** pada Layer 3/4. GWLB bertindak sebagai bump-in-the-wire yang meneruskan seluruh flow paket original tanpa mengubah header IP sumber/tujuan (menghindari source NAT), menjaga visibilitas paket murni saat masuk ke appliance pihak ketiga (Palo Alto, Fortinet, Check Point).
- **AWS Network Firewall**: Layanan firewall managed stateful dan stateless berbasis Suricata engine. Diintegrasikan secara inline di Egress/Inspection VPC untuk inspeksi Layer 3 hingga Layer 7 (SNI inspection, TLS fingerprinting, IPS signatures).

---

## 6. How
Implementasi enterprise network architecture mengikuti alur deterministik:
1. **IPAM & CIDR Planning**: Alokasikan non-overlapping CIDR block (contoh: Production `10.10.0.0/16`, Non-Prod `10.20.0.0/16`, Shared Services `10.30.0.0/16`, Security/Inspection `10.40.0.0/16`).
2. **Subnet Topology**: Buat minimal 3 tier subnet per AZ (Public/Egress, Private Workload, Database/Isolated, plus Dedicated Subnet untuk TGW ENI).
3. **Core Routing Setup**: Pasang IGW pada Egress/Public VPC, pasang NAT Gateway redundant per AZ (hindari cross-AZ NAT dependency).
4. **Deploy Transit Gateway**: Aktifkan TGW dengan opsi `Default Route Table Association = Disable` dan `Default Route Table Propagation = Disable` untuk kontrol manual granular.
5. **Create TGW Route Tables**:
   - `Prod_RT`, `Dev_RT`, `Shared_RT`, `Sec_Inspection_RT`.
6. **Implement Centralized Egress & Inspection**: Arahkan default route `0.0.0.0/0` pada Workload VPCs ke TGW. TGW meneruskan traffic ke Security VPC via GWLB / AWS Network Firewall sebelum dilempar ke Internet Gateway.
7. **Deploy Route 53 Hybrid Endpoints**: Pasang Inbound Endpoint pada Shared Services VPC, pasang Outbound Resolver Rules menuju IP on-premises.
8. **Enforce Security Layering**: Terapkan Security Groups dengan referensi antar-SG (Security Group ID reference), perketat NACL sebagai secondary defense perimeter untuk blocking IP addresses berbahaya.

---

## 7. Analogy
Bayangkan jaringan enterprise AWS sebagai **Sistem Transportasi Kota Metropolitan Modern**:
- **VPC** adalah sebuah kompleks distrik perkantoran otonom yang dipagari tembok perimeter.
- **Subnet** adalah blok-blok gedung spesifik di dalam distrik: Lobi luar (Public Subnet), Ruang Kantor (Private Subnet), dan Ruang Brankas Tertutup (Isolated DB Subnet).
- **Route Table** adalah rambu-rambu petunjuk jalan wajib di persimpangan jalan distrik.
- **Internet Gateway (IGW)** adalah pelabuhan internasional terbuka yang menghubungkan kota dengan dunia luar secara langsung.
- **NAT Gateway** adalah kantor kurir dengan alamat samaran; pegawai kantor dapat mengirim surat keluar distrik, namun penerima di luar tidak pernah mengetahui nomor meja atau ruang kerja pengirim yang sebenarnya.
- **Transit Gateway (TGW)** adalah stasiun sentral transit kereta cepat (Central Grand Hub) di pusat kota. Semua kompleks distrik cukup membangun satu jalur rel menuju stasiun sentral ini, bukan membangun ratusan jalan layang khusus ke masing-masing kompleks lainnya.
- **AWS Direct Connect (DX)** adalah jalur rel kereta bawah tanah eksklusif pribadi berkecepatan tinggi yang menghubungkan kantor pusat lama di kota lain langsung ke stasiun sentral tanpa terkena macet di jalan raya publik.
- **GWLB & Network Firewall** adalah gerbang pemeriksaan bea cukai dan scanner sinar-X berkecepatan tinggi di stasiun sentral; semua kargo diperiksa isinya tanpa merusak label alamat asli pengirim maupun penerima.

---

## 8. Diagram (ASCII)

```text
===================================================================================================
                       ENTERPRISE CENTRALIZED INSPECTION & HYBRID ARCHITECTURE
===================================================================================================

     ON-PREMISES DC                                     AWS REGION (ap-southeast-1)
 +--------------------+                       +-------------------------------------------------+
 | Data Center        |   Direct Connect      |                Direct Connect Gateway           |
 | Router / DNS       |<=====================>|                        (DXGW)                   |
 | 192.168.0.0/16     |     Transit VIF       +-----------------------+-------------------------+
 +--------------------+                                               |
                                                                      | Transit Attachment
                                                                      v
 +----------------------------------------------------------------------------------------------+
 |                                  AWS TRANSIT GATEWAY (TGW)                                   |
 |  [ Route Tables: Spoke_RT | Inspection_RT | Egress_RT | SharedServices_RT ]                  |
 +------------------+------------------------------+---------------------------+----------------+
                    | TGW-Attachment               | TGW-Attachment            | TGW-Attachment
                    v                              v                           v
 +----------------------------------+ +-------------------------+ +-----------------------------+
 |      SPOKE VPC A: PROD           | |    SPOKE VPC B: DEV     | |   CENTRAL INSPECTION &      |
 |      CIDR: 10.10.0.0/16          | |    CIDR: 10.20.0.0/16   | |   EGRESS VPC                |
 |                                  | |                         | |   CIDR: 10.40.0.0/16        |
 | +------------------------------+ | | +---------------------+ | |                             |
 | | Private Workload Subnet      | | | | Dev Workload Subnet | | | +-------------------------+ |
 | | 10.10.1.0/24 (AZ-a)          | | | | 10.20.1.0/24        | | | | Firewall Subnet (GWLB / | |
 | | App Instances [SG Protected] | | | +---------------------+ | | | AWS Network Firewall)   | |
 | +--------------+---------------+ | +-------------------------+ | | 10.40.1.0/24            | |
 |                |                                               | +------------+------------+ |
 |                v default 0.0.0.0/0                             |              ^              |
 |         [Route Table]                                          |              | Inline       |
 |         Dest: 0.0.0.0/0 -> Target: TGW                         |              v Inspection   |
 +----------------------------------+                             | +-------------------------+ |
                                                                  | | Public NAT Subnet       | |
                                                                  | | 10.40.2.0/24            | |
                                                                  | | [ NAT GW ]              | |
                                                                  | +------------+------------+ |
                                                                  |              |              |
                                                                  |              v              |
                                                                  |         [  IGW  ]           |
                                                                  +--------------+--------------+
                                                                                 |
                                                                                 v Internet
```

---

## 9. Simple Example
Konfigurasi sederhana: Membuat VPC dengan 1 Public Subnet, 1 Private Subnet, Route Tables, Internet Gateway, dan Elastic IP untuk NAT Gateway menggunakan AWS CLI:

```bash
# 1. Buat VPC
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 --output text --query 'Vpc.VpcId')
aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=Enterprise-Base-VPC

# 2. Buat Internet Gateway dan attach ke VPC
IGW_ID=$(aws ec2 create-internet-gateway --output text --query 'InternetGateway.InternetGatewayId')
aws ec2 attach-internet-gateway --vpc-id $VPC_ID --internet-gateway-id $IGW_ID

# 3. Buat Public Subnet (/24) dan Private Subnet (/24) di AZ ap-southeast-1a
PUB_SUB=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone ap-southeast-1a --output text --query 'Subnet.SubnetId')
PRIV_SUB=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone ap-southeast-1a --output text --query 'Subnet.SubnetId')

# 4. Alokasikan Elastic IP dan buat NAT Gateway di Public Subnet
EIP_ALLOC=$(aws ec2 allocate-address --domain vpc --output text --query 'AllocationId')
NAT_GW_ID=$(aws ec2 create-nat-gateway --subnet-id $PUB_SUB --allocation-id $EIP_ALLOC --output text --query 'NatGateway.NatGatewayId')

# Tunggu NAT Gateway berstatus 'available' sebelum membuat routing
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_GW_ID

# 5. Konfigurasi Route Table Public (arah 0.0.0.0/0 ke IGW)
PUB_RT=$(aws ec2 create-route-table --vpc-id $VPC_ID --output text --query 'RouteTable.RouteTableId')
aws ec2 create-route --route-table-id $PUB_RT --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --subnet-id $PUB_SUB --route-table-id $PUB_RT

# 6. Konfigurasi Route Table Private (arah 0.0.0.0/0 ke NAT Gateway)
PRIV_RT=$(aws ec2 create-route-table --vpc-id $VPC_ID --output text --query 'RouteTable.RouteTableId')
aws ec2 create-route --route-table-id $PRIV_RT --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_GW_ID
aws ec2 associate-route-table --subnet-id $PRIV_SUB --route-table-id $PRIV_RT
```

---

## 10. Practical Example (Terraform HCL Production Grade)
Berikut adalah konfigurasi Terraform production-grade yang mendefinisikan Transit Gateway, Spoke VPC (Prod), Security Inspection VPC, Route Tables terisolasi, serta mekanisme routing antar-domain:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

# =========================================================================
# 1. AWS TRANSIT GATEWAY INSTANTIATION (MANUAL ROUTING TABLES)
# =========================================================================
resource "aws_ec2_transit_gateway" "central_tgw" {
  description                     = "Core Transit Gateway Enterprise"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  auto_accept_shared_attachments  = "enable"
  dns_support                     = "enable"

  tags = {
    Name        = "tgw-core-enterprise-prod"
    Environment = "Production"
  }
}

# Route Tables pada TGW
resource "aws_ec2_transit_gateway_route_table" "tgw_spoke_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  tags = { Name = "TGW-Spoke-Workload-RT" }
}

resource "aws_ec2_transit_gateway_route_table" "tgw_inspection_rt" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  tags = { Name = "TGW-Inspection-RT" }
}

# =========================================================================
# 2. SPOKE VPC: PRODUCTION (WORKLOAD)
# =========================================================================
resource "aws_vpc" "spoke_prod" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "vpc-prod-workload" }
}

resource "aws_subnet" "prod_workload_az1" {
  vpc_id            = aws_vpc.spoke_prod.id
  cidr_block        = "10.10.1.0/24"
  availability_zone = "ap-southeast-1a"
  tags              = { Name = "subnet-prod-app-az1" }
}

resource "aws_subnet" "prod_tgw_attachment_az1" {
  vpc_id            = aws_vpc.spoke_prod.id
  cidr_block        = "10.10.254.0/28"
  availability_zone = "ap-southeast-1a"
  tags              = { Name = "subnet-prod-tgw-attachment-az1" }
}

# Attachment Spoke Prod ke TGW
resource "aws_ec2_transit_gateway_vpc_attachment" "tgw_att_spoke_prod" {
  transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  vpc_id             = aws_vpc.spoke_prod.id
  subnet_ids         = [aws_subnet.prod_tgw_attachment_az1.id]

  transit_gateway_default_route_table_association = false
  transit_gateway_default_route_table_propagation = false

  tags = { Name = "tgw-att-spoke-prod" }
}

# Associate Spoke Prod Attachment ke Spoke Route Table
resource "aws_ec2_transit_gateway_route_table_association" "assoc_spoke_prod" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.tgw_att_spoke_prod.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.tgw_spoke_rt.id
}

# Routing di dalam Spoke VPC: Seluruh traffic 0.0.0.0/0 diarahkan ke TGW
resource "aws_route_table" "spoke_prod_app_rt" {
  vpc_id = aws_vpc.spoke_prod.id

  route {
    cidr_block         = "0.0.0.0/0"
    transit_gateway_id = aws_ec2_transit_gateway.central_tgw.id
  }

  tags = { Name = "rt-spoke-prod-application" }
}

resource "aws_route_table_association" "spoke_prod_app_assoc" {
  subnet_id      = aws_subnet.prod_workload_az1.id
  route_table_id = aws_route_table.spoke_prod_app_rt.id
}

# =========================================================================
# 3. CENTRAL SECURITY / INSPECTION VPC
# =========================================================================
resource "aws_vpc" "sec_vpc" {
  cidr_block           = "10.40.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "vpc-security-inspection" }
}

resource "aws_subnet" "sec_tgw_az1" {
  vpc_id            = aws_vpc.sec_vpc.id
  cidr_block        = "10.40.254.0/28"
  availability_zone = "ap-southeast-1a"
  tags              = { Name = "subnet-sec-tgw-attachment-az1" }
}

resource "aws_subnet" "sec_fw_az1" {
  vpc_id            = aws_vpc.sec_vpc.id
  cidr_block        = "10.40.1.0/24"
  availability_zone = "ap-southeast-1a"
  tags              = { Name = "subnet-sec-firewall-az1" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "tgw_att_sec_vpc" {
  transit_gateway_id                              = aws_ec2_transit_gateway.central_tgw.id
  vpc_id                                          = aws_vpc.sec_vpc.id
  subnet_ids                                      = [aws_subnet.sec_tgw_az1.id]
  appliance_mode_support                          = "enable" # KRUSIAL untuk menjaga flow simetris FW
  transit_gateway_default_route_table_association = false
  transit_gateway_default_route_table_propagation = false

  tags = { Name = "tgw-att-security-vpc" }
}

# Associate Inspection VPC Attachment ke Inspection Route Table
resource "aws_ec2_transit_gateway_route_table_association" "assoc_sec_vpc" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.tgw_att_sec_vpc.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.tgw_inspection_rt.id
}

# Propagasi rute Prod ke Route Table Inspection TGW (Inspection harus tahu cara kembali ke Prod)
resource "aws_ec2_transit_gateway_route_table_propagation" "propagate_prod_to_inspection" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.tgw_att_spoke_prod.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.tgw_inspection_rt.id
}

# Default Route pada Spoke RT di TGW dilempar ke Security Attachment
resource "aws_ec2_transit_gateway_route" "default_to_security" {
  destination_cidr_block         = "0.0.0.0/0"
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.tgw_att_sec_vpc.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.tgw_spoke_rt.id
}
```

---

## 11. Real World Example
Kasus nyata pada institusi perbankan tier-1:
- **Tantangan**: Memiliki 120 akun AWS dengan VPC masing-masing untuk mikroservis. Regulasi moneter mengharuskan inspeksi IPS/IDS mendalam pada seluruh outbound HTTP/S call ke partner fintech, serta komunikasi internal antar mikroservis prod tidak boleh bocor ke dev.
- **Solusi Arsitektur**:
  1. Dibangun sebuah **Egress-Inspection Shared Services Hub** menggunakan TGW.
  2. Implementasi **AWS Network Firewall** di Egress VPC.
  3. Mengaktifkan **Appliance Mode** pada TGW Attachment Egress VPC untuk memastikan traffic inbound dan return outbound selalu melewati Availability Zone yang identik guna mencegah stateful packet dropping pada firewall.
  4. Seluruh DNS resolusi dipusatkan menggunakan Amazon Route 53 Resolver Endpoints, meneruskan query domain internal on-premises banking (`*.corp.bank`) ke Core Data Center via AWS Direct Connect 10 Gbps Transit VIF.
- **Hasil**: Zero unauthorized data exfiltration, latensi inter-VPC terprediksi di bawah 2ms, dan menghemat biaya NAT Gateway sebesar $65.000 USD per tahun melalui konsolidasi gateway.

---

## 12. Trade-offs

| Parameter | VPC Peering | Transit Gateway (TGW) | PrivateLink |
| :--- | :--- | :--- | :--- |
| **Model Topologi** | Mesh point-to-point | Hub-and-Spoke terpusat | Service consumer-to-service |
| **Routing Transitivity** | Tidak (Non-transitive) | Ya (Transitive routing didukung) | N/A (Port level Layer 4 mapping) |
| **Max Connections** | Skala praktis < 50 VPCs | Hingga 5.000 attachment per Region | Ribuan VPC endpoints |
| **Throughput / Bottleneck**| No aggregate bottleneck (Line-rate) | 50 Gbps per VPC attachment burst | Hingga 40 Gbps per ENI |
| **Biaya Jaringan** | Hanya Cross-AZ transfer ($0.01/GB) | Biaya per attachment ($0.05/jam) + Data processing fee ($0.02/GB) | Biaya per interface endpoint ($0.01/jam) + Processing fee |
| **Kemudahan Manajemen**| Kompleks pada skala besar | Sangat mudah dikontrol tersentralisasi | Sangat tinggi, tidak perlu route table routing |

---

## 13. When To Use
- Gunakan **AWS Transit Gateway** ketika mengelola lebih dari 5-10 VPC lintas banyak akun AWS yang memerlukan konektivitas inter-workload, inspeksi terpusat, dan integrasi Direct Connect hybrid.
- Gunakan **VPC Peering** hanya untuk koneksi berkinerja ekstrem antar 2-3 VPC spesifik (misal: cluster database analitik performa tinggi) di mana biaya pemrosesan TGW per GB menjadi deal-breaker dan latensi absolut terendah menjadi prioritas.
- Gunakan **Gateway Load Balancer (GWLB)** ketika Anda wajib menempatkan virtual appliance pihak ketiga (firewall vendor) secara elastis dan horizontal scalable tanpa memodifikasi topologi alamat IP paket asli.
- Gunakan **Route 53 Resolver Inbound/Outbound Endpoints** saat lingkungan hybrid aktif memerlukan resolusi nama DNS dua arah secara transparan antara data center lokal dan AWS.

---

## 14. When NOT To Use
- Jangan gunakan **Transit Gateway** jika arsitektur Anda hanya terdiri dari 1 akun dengan 2 VPC monolitik. Penggunaan TGW akan menambah biaya per jam dan latensi mikro-detik yang tidak perlu.
- Jangan gunakan **Public NAT Gateway** untuk menjangkau layanan internal AWS seperti Amazon S3 atau Amazon DynamoDB; gunakan **VPC Gateway Endpoints** (gratis) untuk mencegah bandwidth throttling dan pemborosan biaya NAT processing.
- Jangan gunakan **Security Groups** jika tujuannya adalah memblokir IP address jahat tertentu (contoh: ribuan botnet IP); Security Groups memiliki batas kuota rules (default 60 inbound/outbound rules). Gunakan **Network ACLs** atau **AWS WAF / Network Firewall**.

---

## 15. Common Mistakes
1. **Lupa Menambahkan Ephemeral Ports pada Custom Inbound/Outbound NACL**: Membuka inbound port 80/443 namun memblokir outbound port `1024-65535` pada NACL menyebabkan respon paket HTTP/S gagal kembali ke client.
2. **Asymmetric Routing pada Centralized Firewall**: Traffic masuk via AZ-a, namun paket kembali diarahkan via AZ-b karena salah konfigurasi routing atau kelupaan mengaktifkan opsi `Appliance Mode` pada Transit Gateway Attachment. Stateless firewall mungkin lolos, tetapi stateful firewall akan langsung men-drop paket tersebut (`TCP RST` / invalid session).
3. **Mengabaikan 5 AWS Reserved IPs**: Melakukan sizing subnet terlalu ketat (misal `/29` yang hanya menyediakan 8 IP address, terpotong 5 reserved IP, menyisakan hanya 3 IP usable). Akibatnya, deployment EKS nodes atau Application Load Balancers langsung gagal karena kehabisan IP.
4. **Overlapping CIDR Blocks**: Memberikan subnet `10.0.0.0/16` di on-premises dan membuat VPC dengan CIDR yang sama `10.0.0.0/16`. Routing via Direct Connect atau VPN akan konflik total (BGP flap atau silent routing discard).

---

## 16. Best Practices
1. **IPAM Automation**: Gunakan AWS VPC IP Address Manager (IPAM) untuk mengotomatisasi alokasi hierarki CIDR non-overlapping antar region dan business unit.
2. **Dedicated TGW Subnets**: Selalu alokasikan subnet berukuran kecil (contoh: `/28`) khusus untuk menampung TGW ENI attachment di setiap AZ, terpisah dari subnet workload aplikasi, guna mencegah konsumsi IP yang tidak sengaja.
3. **Redundan Multi-AZ Egress**: Jangan pernah meletakkan satu NAT Gateway di satu AZ lalu membagikannya ke private subnet di AZ lain untuk production. Jika AZ penampung NAT Gateway mati, seluruh AZ kehilangan akses internet (Single Point of Failure), plus timbul biaya cross-AZ data transfer.
4. **VPC Flow Logs Enabled**: Aktifkan VPC Flow Logs pada level ENI/VPC ke CloudWatch Logs atau S3 dengan format custom mencakup `pkt-srcaddr`, `pkt-dstaddr`, `tcp-flags`, dan `action` (ACCEPT/REJECT) untuk audit investigasi forensik.
5. **Least Privilege Security Groups**: Terapkan referensi Security Group ID ketimbang IP CIDR untuk komunikasi antar-tier (contoh: App-SG hanya mengizinkan inbound dari Web-SG pada port 8080).

---

## 17. Troubleshooting
Panduan terstruktur saat terjadi insiden jaringan:

```text
[MASALAH: Workload di Private Subnet Tidak Dapat Mengakses Endpoint Publik / Inter-VPC]
                               |
                               v
                     Cek Security Group (L4)
   Apakah outbound rule mengizinkan traffic? (Default: Allow all)
   Apakah return traffic diizinkan? (Stateful: Ya)
                               |
                [Lolos]        v       [Gagal] -> Perbaiki SG Rules
                     Cek Subnet NACL (L4)
   Inbound & Outbound rules terdefinisi?
   Apakah Ephemeral Ports (1024-65535) diizinkan pada Outbound?
                               |
                [Lolos]        v       [Gagal] -> Tambahkan rule permit Ephemeral
                   Cek VPC Route Table (L3)
   Apakah terdapat rute 0.0.0.0/0 menuju NAT GW / TGW?
   Apakah target gateway dalam status "active" (bukan blackhole)?
                               |
                [Lolos]        v       [Gagal] -> Perbaiki Route Table / ganti target
               Cek TGW Route Tables & Policies
   Attachment Prod ter-associate ke TGW Route Table yang benar?
   Apakah rute return ke subnet asal ter-propagasi di TGW?
   Apakah Appliance Mode aktif pada TGW jika melewati Firewall?
                               |
                [Lolos]        v       [Gagal] -> Perbaiki TGW Assoc/Propagations
                Analisis VPC Flow Logs / Reachability Analyzer
   Jalankan: AWS VPC Reachability Analyzer dari Source ENI ke Dst ENI.
   Filter VPC Flow Logs: ACTION = "REJECT" untuk identifikasi drop point.
```

---

## 18. Exercise
Selesaikan instruksi berikut:
1. Rancang arsitektur CIDR menggunakan RFC 1918 untuk perusahaan yang membutuhkan 3 environment:
   - Development (estimasi 200 host per AZ, 2 AZ).
   - Staging (estimasi 500 host per AZ, 2 AZ).
   - Production (estimasi 2000 host per AZ, 3 AZ).
   Tentukan subnetting, prefix length (/xx), dan buktikan tidak ada CIDR yang tumpang tindih.
2. Tuliskan satu file konfigurasi NACL inbound dan outbound rule yang secara eksplisit hanya mengizinkan server backend menerima request HTTPS (TCP 443) dari reverse proxy publik (`10.0.1.0/24`), dan mengirim response balik ke reverse proxy tersebut, sambil memblokir seluruh traffic lainnya.

---

## 19. Challenge
Rancang arsitektur jaringan skala multi-region (Singapura `ap-southeast-1` dan Jakarta `ap-southeast-3`):
- Kedua region memiliki Workload VPCs masing-masing.
- Komunikasi inter-region harus melalui **Transit Gateway Inter-Region Peering**.
- Seluruh outbound traffic internet dari kedua region harus diinspeksi secara terpusat HANYA di Egress VPC Region Singapura sebelum keluar ke internet publik.
- Buat dokumen spesifikasi rute (Route Table entries pada Workload VPCs, TGW Route Tables di kedua region, dan NAT/Firewall VPC di Singapura). Sertakan mitigasi terhadap skenario asimetris routing saat traffic kembali dari internet menuju workload di Jakarta.

---

## 20. Summary
- **Arsitektur Jaringan Skala Enterprise** membutuhkan pemisahan kontrol (control plane) dan penerusan data (data plane) yang ketat melalui VPC, Subnetting, dan Route Tables deterministik.
- **TGW** adalah standar de-facto untuk topologi hub-and-spoke skala menengah hingga besar, meniadakan limitasi routing non-transitif VPC Peering.
- **Isolasi Domain TGW** dicapai melalui pemisahan Transit Gateway Route Tables antara Production, Non-Production, dan Core Services.
- **Security Layering** yang efektif memadukan stateful granularitas Security Groups pada level instance, NACL stateless filtering pada boundary subnet, serta deep packet inspection (DPI) menggunakan AWS Network Firewall / GWLB dengan mengaktifkan TGW *Appliance Mode*.
- **Konektivitas Hybrid yang Kokoh** menuntut integrasi Direct Connect Gateway dengan Transit VIF untuk bandwidth terdedikasi serta Amazon Route 53 Resolver Endpoints untuk hybrid domain name lookup yang seamless.

---