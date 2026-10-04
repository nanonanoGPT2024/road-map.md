# Evaluasi Bab 02: Arsitektur Jaringan Skala Enterprise

---

## A. Basic Questions (5 Soal)

### Soal 1
Berapa jumlah alamat IP yang dapat digunakan oleh host/instance jika Anda membuat subnet dengan blok CIDR `10.0.5.0/28` di dalam sebuah AWS VPC?
A. 16  
B. 14  
C. 11  
D. 13  

### Soal 2
Manakah pernyataan yang BENAR mengenai karakteristik Security Groups di AWS?
A. Security Groups beroperasi pada level subnet dan bersifat stateless.  
B. Security Groups mengevaluasi rules secara sekuensial berdasarkan nomor urut rule.  
C. Security Groups bersifat stateful; return traffic otomatis diizinkan meskipun tidak ada outbound rule eksplisit.  
D. Security Groups secara native mendukung explicit DENY rule untuk memblokir IP tertentu.  

### Soal 3
Sebuah EC2 instance pada private subnet berhasil mengirim request HTTP ke server publik melalui NAT Gateway, namun ketika Anda mengubah Network ACL inbound untuk subnet tersebut dan menghapus aturan ephemeral ports (`1024-65535`), koneksi menjadi time out. Mengapa hal ini terjadi?
A. NAT Gateway berhenti berfungsi jika NACL diubah.  
B. NACL bersifat stateless, sehingga paket respons dari internet di-drop pada sisi inbound subnet karena port ephemeral tidak dibuka.  
C. Security Group instance tersebut secara otomatis ikut terhapus.  
D. AWS Route Table kehilangan default route ke NAT Gateway.  

### Soal 4
Apa fungsi utama dari parameter `Appliance Mode` yang diaktifkan pada attachment AWS Transit Gateway?
A. Meningkatkan throughput bandwidth attachment menjadi 100 Gbps secara otomatis.  
B. Memastikan traffic dua arah (inbound dan outbound/return) diproses oleh Network Interface pada Availability Zone yang sama guna menghindari asymmetric routing pada stateful firewall.  
C. Mengompresi paket payload sebelum dikirimkan melalui inter-region peering.  
D. Mengenkripsi payload paket menggunakan protokol IPsec secara default.  

### Soal 5
Pada arsitektur hybrid DNS, komponen apakah yang harus dibuat di AWS agar server DNS lokal on-premises dapat meresolusi domain Private Hosted Zone di AWS?
A. Route 53 Outbound Endpoint  
B. Route 53 Inbound Endpoint  
C. Route 53 Public Hosted Zone  
D. Transit Gateway Multicast Domain  

---

## B. Intermediate Questions (5 Soal)

### Soal 6
Anda memiliki 3 buah VPC: VPC A, VPC B, dan VPC C. Anda membuat VPC Peering antara VPC A - VPC B, dan VPC B - VPC C. Anda ingin instance di VPC A dapat berkomunikasi dengan instance di VPC C melalui VPC B. Hasil pengujian menunjukkan koneksi gagal (unreachable). Solusi teknis dan alasan arsitektural yang paling tepat adalah:
A. Cukup tambahkan rute `CIDR VPC C` di route table VPC A dengan target Peering Connection A-B; koneksi gagal karena route table belum di-update.  
B. Koneksi tidak akan pernah berhasil melalui peering tersebut karena VPC Peering bersifat *non-transitive*. Anda harus membuat VPC Peering langsung antara VPC A dan VPC C atau beralih ke AWS Transit Gateway.  
C. Anda harus mengaktifkan BGP routing pada Virtual Private Gateway di VPC B.  
D. Ganti subnet masking pada VPC B agar mencakup CIDR VPC A dan VPC C.  

### Soal 7
Sebuah perusahaan menggunakan AWS Direct Connect (DX) 10 Gbps dengan Direct Connect Gateway (DXGW) untuk menghubungkan on-premises DC dengan AWS Transit Gateway di multi-VPC. Virtual Interface jenis apa yang WAJIB digunakan pada koneksi DX tersebut?
A. Public VIF  
B. Private VIF  
C. Transit VIF  
D. Direct VIF  

### Soal 8
Anda mendesain Egress VPC tersentralisasi menggunakan AWS Network Firewall dan Gateway Load Balancer. Protokol tunneling apa yang digunakan oleh Gateway Load Balancer untuk membungkus (encapsulate) traffic IP asli beserta metadata port-nya sebelum dikirimkan ke firewall appliances?
A. VXLAN pada UDP port 4789  
B. GRE pada IP protocol 47  
C. Geneve pada UDP port 6081  
D. IPsec ESP pada UDP port 500  

### Soal 9
Sebuah workload pada EC2 instance perlu mengunduh file berukuran multi-terabyte setiap harinya dari Amazon S3 bucket di Region yang sama. Workload berada di private subnet yang memiliki rute default `0.0.0.0/0` ke NAT Gateway. Bagaimana cara paling hemat biaya dan berkinerja tinggi untuk mengalirkan traffic tersebut?
A. Perbanyak jumlah NAT Gateway di seluruh AZ.  
B. Buat S3 Gateway Endpoint dan kaitkan ke Route Table private subnet (gratis tanpa biaya data processing).  
C. Pasang S3 Interface Endpoint (PrivateLink) di setiap subnet.  
D. Berikan Public Elastic IP pada EC2 instance dan routing langsung via IGW.  

### Soal 10
Ketika mengonfigurasi AWS Route 53 Resolver Outbound Rules untuk hybrid DNS forwarding ke on-premises:
Manakah skenario konfigurasi yang benar agar query DNS `internal.corp.com` diarahkan ke DNS Server on-premises `192.168.10.50`?
A. Buat Forward Rule untuk domain `internal.corp.com`, tentukan Target IP `192.168.10.50`, kaitkan Rule ke VPC yang bersangkutan via Outbound Resolver Endpoint.  
B. Buat System Rule pada Inbound Resolver Endpoint dengan target IP `192.168.10.50`.  
C. Tambahkan CNAME record di Route 53 Public Hosted Zone yang mengarah ke IP `192.168.10.50`.  
D. Buat VPC Peering ke on-premises DNS Server dan ubah DHCP Option Sets VPC.  

---

## C. Scenario-Based Questions (3 Soal Kasus Nyata)

### Skenario 1: The Egress Bottleneck & High Latency Incident
Sebuah platform e-commerce finansial berskala besar mengalami lonjakan latensi dramatis pada layanan payment gateway saat promo tanggal kembar (11.11). Analisis awal menunjukkan:
- Workload aplikasi berada di VPC Prod pada 3 Availability Zone (`ap-southeast-1a`, `1b`, `1c`).
- Seluruh subnet privat di ketiga AZ mengarahkan default route `0.0.0.0/0` hanya ke **satu** NAT Gateway yang berada di Public Subnet AZ `ap-southeast-1a`.
- Metrik CloudWatch NAT Gateway menunjukkan parameter `ErrorPortAllocation` melonjak tinggi, dan `PacketsDropCount` meningkat tajam.
- Analisis finansial pasca insiden juga menemukan lonjakan biaya *Data Transfer Regional (Cross-AZ)* yang sangat besar.

**Tugas Anda**:
1. Jelaskan secara teknis akar penyebab (root cause) dari error `ErrorPortAllocation` dan latensi tinggi tersebut!
2. Rancang solusi arsitektur perbaikan lengkap (high availability & cost-effective) untuk mengeliminasi single point of failure dan cross-AZ transfer cost!

### Skenario 2: Asymmetric Routing Packet Drop on Next-Gen Firewall
Perusahaan Anda mengonsolidasikan arsitektur inspeksi traffic East-West antar ratusan VPC menggunakan AWS Transit Gateway dan sekelompok Virtual Firewall Appliance (Palo Alto VM-Series) di dalam Inspection VPC.
- Flow traffic yang direncanakan: `VPC-A (Source)` -> `TGW` -> `Inspection VPC (Firewall)` -> `TGW` -> `VPC-B (Destination)`.
- Saat dilakukan validasi pengujian koneksi TCP (contoh: curl via HTTP/S), koneksi selalu time-out atau terputus secara acak (intermittent).
- Log pada Firewall Appliance di AZ-a menunjukkan paket `TCP SYN` diterima dan diproses, namun paket balasan `TCP SYN-ACK` tidak pernah tercatat di firewall AZ-a tersebut, melainkan muncul di log firewall AZ-b dengan status dropped: `Invalid TCP state / Out of sequence packet`.

**Tugas Anda**:
1. Identifikasi mekanisme routing default TGW yang menyebabkan anomali tersebut!
2. Sebutkan konfigurasi spesifik pada AWS Transit Gateway Attachment dan Subnet Routing Table yang wajib diaktifkan untuk menyelesaikan masalah ini secara permanen!

### Skenario 3: Overlapping CIDR Post-Merger Crisis
Perusahaan Anda baru saja mengakuisisi startup fintech kompetitor. Anda diinstruksikan untuk segera menghubungkan Core Banking VPC (`10.100.0.0/16`) dengan sistem analitik startup (`10.100.0.0/16`). 
- Kedua entitas menggunakan blok CIDR yang persis sama.
- Manajemen menolak opsi pengalihan IP (re-IP-ing) seluruh instance startup karena akan memakan waktu 6 bulan dan mengganggu operasional sistem.
- Kebutuhan bisnis saat ini: Instance analitik tertentu di startup (`10.100.50.10`) harus dapat mengakses endpoint database MySQL (`10.100.20.5`) di Core Banking VPC secara aman dan real-time.

**Tugas Anda**:
1. Mengapa TGW atau VPC Peering langsung tidak dapat mengatasi masalah ini?
2. Rancang arsitektur solusi menggunakan **AWS PrivateLink** atau **Bidirectional NAT via AWS Managed NAT Gateway / Cloud Router** untuk memungkinkan konektivitas tersebut tanpa mengubah CIDR pada kedua VPC!

---

## D. Practical Chapter Challenge: Enterprise Multi-Tier Hub-Spoke Network

### Deskripsi Skenario:
Rancang dan implementasikan cetak biru jaringan komprehensif untuk perusahaan multi-nasional dengan arsitektur berikut:
1. **Hub VPC (Inspection & Egress)**:
   - Terdiri dari 2 AZ.
   - Memiliki Public Subnets dengan Multi-AZ NAT Gateways dan Internet Gateway.
   - Memiliki Firewall/Inspection Subnets yang siap diintegrasikan dengan AWS Network Firewall / appliances.
2. **Spoke VPC 1 (Production Workload)**:
   - CIDR: `10.10.0.0/16`.
   - Subnet Private Workload & Subnet Database Isolated.
3. **Spoke VPC 2 (Shared Services & DNS Resolver)**:
   - CIDR: `10.30.0.0/16`.
   - Menampung Route 53 Inbound Endpoint untuk melayani query resolusi DNS hybrid on-premises.
4. **AWS Transit Gateway Routing Requirements**:
   - Workload Production **TIDAK BOLEH** langsung menjangkau internet tanpa melewati Firewall di Hub VPC.
   - Workload Production **DAPAT** menjangkau Shared Services VPC secara langsung melalui rute privat TGW.
   - Seluruh default route `0.0.0.0/0` dari Spoke VPCs harus bermuara di Hub Inspection VPC.

### Deliverables:
Kirimkan solusi rancangan berupa:
1. Skema alokasi IP CIDR lengkap untuk seluruh subnet di semua VPC (lengkap dengan perhitungan host capacity per subnet).
2. Tabel routing mendalam untuk setiap Route Table:
   - Spoke VPC Prod Route Tables (Workload & DB).
   - Hub VPC Route Tables (TGW Attachment Subnet, FW Subnet, dan NAT Subnet).
   - TGW Route Tables (Association & Propagation Matrix).
3. Kode Infrastructure as Code (Terraform) deklaratif yang menginstansiasi struktur core TGW, Route Tables, dan Association/Propagation sesuai spesifikasi.

---

## Kunci Jawaban & Panduan Solusi

### A. Kunci Jawaban Basic Questions
1. **C (11 IP)**: Kalkulasi: Blok `/28` memiliki total $2^{(32-28)} = 16$ alamat IP. AWS mereservasi 5 IP address di setiap subnet (.0, .1, .2, .3, .255). Maka usable IP = $16 - 5 = 11$ IP.
2. **C**: Security Groups beroperasi pada level ENI/instance, bersifat stateful (return traffic otomatis diizinkan), dan tidak mendukung rule explicit DENY.
3. **B**: NACL bersifat stateless. Saat traffic outbound dari EC2 kembali dari internet melalui NAT GW, paket masuk kembali ke subnet menggunakan range ephemeral client port (`1024-65535`). Jika rule inbound NACL memblokirnya, return handshake di-drop.
4. **B**: `Appliance Mode` pada Transit Gateway VPC Attachment memastikan bahwa paket flow bolak-balik (request & reply) dijamin diarahkan ke Availability Zone dan ENI yang sama, mencegah koneksi di-drop oleh stateful inspection firewall.
5. **B**: Route 53 Inbound Endpoint menyediakan IP address privat di dalam VPC yang dapat menerima forwarding query DNS dari server on-premises.

### B. Kunci Jawaban Intermediate Questions
6. **B**: VPC Peering memiliki batasan *non-transitive routing*. VPC A tidak dapat melintasi VPC B untuk mencapai VPC C. Solusinya adalah direct peering A ke C atau hub-and-spoke via AWS Transit Gateway.
7. **C**: Transit VIF adalah satu-satunya tipe Virtual Interface Direct Connect yang dapat dihubungkan ke Direct Connect Gateway (DXGW) untuk menjangkau Transit Gateway (TGW) multi-VPC.
8. **C**: Gateway Load Balancer menggunakan Geneve encapsulation (UDP port 6081) untuk membungkus layer IP asli dan menyematkan metadata flow ID.
9. **B**: Gateway Endpoint untuk S3 di-attach langsung ke VPC route table secara gratis tanpa batasan bandwidth dan tanpa biaya pemrosesan per GB seperti pada NAT Gateway atau Interface Endpoint.
10. **A**: Route 53 Outbound Resolver Rule bertipe "Forward" akan menangkap query untuk domain yang ditentukan (`internal.corp.com`), lalu mengirimkannya melalui Outbound Endpoint ENI ke DNS IP on-premises.

### C. Panduan Solusi Scenario-Based Questions

#### Skenario 1 (Egress Bottleneck & High Latency):
1. **Root Cause**:
   - Single NAT Gateway di AZ-a melayani traffic outbound dari instance di 3 AZ (`1a`, `1b`, `1c`). 
   - Sebuah NAT Gateway mendukung maksimal 55.000 concurrent connection per IP destination. Lonjakan koneksi simultan ke payment gateway publik menyebabkan source port exhaustion (SNAT port pool habis), memicu metric `ErrorPortAllocation` dan packet drop.
   - Traffic lintas AZ dari `1b` dan `1c` menuju `1a` menimbulkan latency penalti serta lonjakan tagihan cross-AZ data transfer ($0.01 per GB setiap arah).
2. **Solusi Perbaikan**:
   - Implementasikan arsitektur **Multi-AZ Multi-NAT Gateway**: Deploy 1 NAT Gateway di Public Subnet masing-masing AZ (`1a`, `1b`, `1c`).
   - Pisahkan Route Table untuk Private Subnet di masing-masing AZ. Private Subnet AZ-a mengarahkan `0.0.0.0/0` ke NAT GW AZ-a, AZ-b ke NAT GW AZ-b, dan AZ-c ke NAT GW AZ-c.
   - Hasil: Mengeliminasi cross-AZ charge, mengalokasikan total $55.000 \times 3 = 165.000$ concurrent connection capacity, dan menghapus single point of failure.

#### Skenario 2 (Asymmetric Routing Packet Drop):
1. **Identifikasi Masalah**:
   - Secara default, Transit Gateway menggunakan algoritma hash flow independen saat meneruskan paket antar-AZ. Traffic dari `VPC-A (AZ-a)` menuju `Inspection VPC` masuk ke firewall di AZ-a. Namun saat paket kembali dari `VPC-B (AZ-b)`, TGW melempar paket return ke ENI Inspection VPC di AZ-b.
   - Karena Palo Alto Firewall bersifat stateful, firewall di AZ-b tidak memiliki context connection tracking (`SYN` tidak pernah terlihat di AZ-b), sehingga firewall AZ-b menolak paket return `SYN-ACK` tersebut (*TCP reset / invalid state drop*).
2. **Solusi Spesifik**:
   - Aktifkan opsi **Appliance Mode** pada Transit Gateway VPC Attachment milik `Inspection VPC`:
     `aws ec2 modify-transit-gateway-vpc-attachment --transit-gateway-attachment-id <att-id> --options ApplianceModeSupport=enable`
   - Hal ini memaksa TGW mempertahankan affinity traffic dua arah pada AZ yang sama di Inspection VPC selama durasi connection session.

#### Skenario 3 (Overlapping CIDR Post-Merger):
1. **Mengapa TGW/Peering Gagal**:
   - Routing table Layer 3 tidak dapat memiliki rute deterministik jika prefix destinasi dan lokal identik (`10.100.0.0/16`). Router tidak dapat membedakan apakah paket ditujukan untuk host lokal atau host remote (ambiguous routing).
2. **Solusi Menggunakan AWS PrivateLink**:
   - Di Core Banking VPC (`10.100.0.0/16`), letakkan Database di belakang Network Load Balancer (NLB) privat.
   - Buat **VPC Endpoint Service** yang terhubung ke NLB tersebut.
   - Pada Startup VPC (`10.100.0.0/16`), buat **Interface VPC Endpoint** yang mereferensikan Service Name dari Endpoint Service Core Banking.
   - AWS PrivateLink akan mengalokasikan alamat IP privat lokal dari subnet startup (misal: `10.100.50.215`) untuk endpoint tersebut.
   - Server analitik startup cukup menghubungi IP lokal `10.100.50.215` pada port database. PrivateLink secara otomatis menjembatani koneksi melalui AWS Hyperplane SDN tanpa peering L3 dan tanpa konflik routing CIDR.

---