# Modul 01: Keamanan Jaringan, Firewalling, Segmentasi, dan VPNs

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menganalisis perbedaan mekanis antara Stateless Access Control Lists (ACLs) berbasis TCAM dan Stateful Packet Inspection (SPI) berbasis *connection tracking engine*.
- Merancang dan mengimplementasikan arsitektur Zone-Based Firewall (ZFW) dan segmentasi perimeter Demilitarized Zone (DMZ) multi-tier dengan prinsip *least privilege*.
- Mengonfigurasi dan memecahkan masalah IPsec VPN (IKEv1 dan IKEv2), mengintegrasikan Generic Routing Encapsulation (GRE) over IPsec untuk dynamic routing protocol over encrypted tunnels.
- Membedakan enkripsi hop-by-hop Layer 2 (MACsec / IEEE 802.1AE) dengan enkripsi end-to-end Layer 3 (IPsec), serta mengimplementasikan kontrol akses port berbasis IEEE 802.1X.
- Menghitung kalkulasi *packet overhead*, MTU/MSS clamping, dan mitigasi fragmentasi paket pada enkapsulasi kriptografi jaringan.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **TCP/IP Architecture**: Analisis flag TCP (SYN, ACK, FIN, RST), flow windowing, Three-Way Handshake, dan four-way termination.
- **Routing Protocol**: Dynamic routing (BGP, OSPF) dan pemahaman Forwarding Information Base (FIB) vs Routing Information Base (RIB).
- **Kriptografi Dasar**: Symmetric key encryption (AES-CBC, AES-GCM), Asymmetric key exchange (RSA, Diffie-Hellman), Hashing & Integrity (SHA-256, HMAC).
- **CLI Switching/Routing**: Pengalaman konfigurasi VLAN, Sub-interface, trunking 802.1Q, dan ACL standard/extended pada platform enterprise (Cisco IOS-XE / Linux iptables/nftables).

---

## 3. Concept
Keamanan jaringan modern beroperasi pada model **Defense-in-Depth** dan **Zero Trust Network Architecture (ZTNA)**. Jaringan tidak lagi diasumsikan aman hanya karena berada di dalam perimeter fisik. Fondasi keamanan jaringan modern bertumpu pada empat pilar:
1. **Filtering & Stateful Inspection**: Membedakan paket yang valid sebagai bagian dari sesi komunikasi yang diinisiasi secara sah dari paket anomali atau injeksi liar.
2. **Microsegmentation & Zone Boundary Control**: Membatasi *blast radius* insiden keamanan dengan mengisolasi traffic antar beban kerja (workload) berdasarkan tingkat kepercayaan (*trust level*).
3. **Encrypted Transport Tunnels**: Menjamin aspek *Confidentiality, Integrity, and Authenticity* (CIA triad) data in-transit melintasi domain publik atau untrusted fabric.
4. **Edge Port Access Control**: Menolak akses fisik dan Layer 2 sebelum identitas perangkat/pengguna divalidasi secara kriptografis oleh Authentication Server.

---

## 4. Why
Mengapa mekanisme filtering sederhana tidak lagi memadai di level enterprise dan cloud infrastructure?
- **Keterbatasan Stateless ACL**: Stateless ACL memeriksa setiap paket secara terisolasi tanpa memori status koneksi sebelumnya. Untuk mengizinkan traffic balik TCP dari internet, administrator harus membuka seluruh port dinamik/ephemeral (>1023) tanpa validasi handshake. Ini membuka celah eksploitasi scanning dan port injection.
- **Asymmetric Routing Vulnerability**: Pada infrastruktur redundan multi-homed, stateful firewall akan membuang (drop) traffic jika paket return (SYN-ACK atau ACK) melewati firewall yang berbeda dari firewall yang memproses paket inisiasi (SYN), karena ketiadaan entri *state table*. Engineer wajib memahami state synchronization.
- **Overhead Enkapsulasi Kriptografi**: Penambahan header IPsec, GRE, dan padding mereduksi Maximum Segment Size (MSS). Ketidaktahuan tentang MTU/MSS clamping menyebabkan fenomena *Path MTU Discovery (PMTUD) Black Hole*, di mana paket berukuran besar di-drop diam-diam oleh network hop dengan flag Don't Fragment (DF) aktif.
- **Man-in-the-Middle (MitM) pada Layer 2**: Enkripsi Layer 3 (IPsec) membiarkan frame header L2 terbuka. Serangan ARP poisoning, VLAN hopping, dan sniffing pada link inter-switch datacenter hanya bisa dicegah di level L2 via IEEE 802.1AE (MACsec).

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Stateful Packet Inspection (SPI) vs. Stateless ACLs
- **Stateless ACL**:
  - Diimplementasikan langsung pada *Ternary Content Addressable Memory* (TCAM) switch/router.
  - Memvalidasi paket individual dalam single clock-cycle berdasarkan match criteria statis: Source IP, Destination IP, Protocol, Source Port, Destination Port.
  - Tidak menyimpan riwayat status percakapan. Tidak dapat membedakan paket TCP SYN (inisiasi) dengan paket TCP ACK liar yang dipalsukan jika port target dibuka.
- **Stateful Packet Inspection (SPI)**:
  - Memeriksa paket melalui software connection tracker (`conntrack`) atau hardware flow table.
  - Mengelola *State Table* dengan atribut 5-tuple: `{Src IP, Dst IP, Src Port, Dst Port, Protocol}` ditambah status state machine (misal: `TCP_SYN_SENT`, `TCP_ESTABLISHED`, `TCP_TIME_WAIT`).
  - Return traffic secara otomatis diizinkan melewati firewall selama atribut paket cocok dengan entri yang tercatat di state table.
  - Mencegah serangan TCP Out-of-Window, Christmas Tree attack, dan SYN Flood (melalui mekanisme TCP SYN Cookie / SYN Proxy).

```
Stateless ACL:  [Packet] ---> [TCAM Match: Src/Dst IP/Port] ---> Permit/Deny (No Memory)

Stateful SPI:   [Packet] ---> [Check State Table] 
                                  |-- Match Found? -------> Update Counter & Permit
                                  +-- No Match?
                                        |-- TCP SYN? -----> Match Policy -> Add to State Table -> Permit
                                        +-- Non-SYN? -----> Drop (Invalid State Injection)
```

### 5.2 Zone-Based Firewall (ZFW) Architecture
ZFW mengabstraksi antarmuka fisik/virtual menjadi **Security Zones**. Antarmuka tidak lagi memiliki filter individual yang melekat secara kaku; aturan keamanan ditentukan berdasarkan hubungan antar-zona (*Zone-Pairs*).
- **Aturan Dasar ZFW**:
  1. Dua interface dalam zona yang sama dapat berkomunikasi secara bebas secara default (intra-zone traffic permitted).
  2. Komunikasi antar dua zona berbeda ditolak secara default (inter-zone traffic blocked), kecuali didefinisikan secara eksplisit via `Zone-Pair` dan `Policy-Map`.
  3. Router/Firewall memiliki zona implisit bernama **Self Zone** (traffic yang ditujukan ke IP lokal router atau berasal dari router itu sendiri). Kontrol traffic ke control-plane router (misal: SSH, BGP, SNMP) ditangani via `Zone-Pair <Zone> to self`.
  4. Inspection bersifat *unidirectional*: jika traffic `Zone-A -> Zone-B` di-inspect, traffic kembali `Zone-B -> Zone-A` diizinkan otomatis via state tracking.

### 5.3 DMZ (Demilitarized Zone) Architecture
DMZ adalah subnet logis yang memisahkan layanan publik (Web server, Mail gateway, Reverse Proxy) dari internal corporate network/database.
- **Triangular DMZ**: Firewall tunggal dengan minimal 3 antarmuka jaringan:
  - `INSIDE` (Tingkat Kepercayaan Tinggi: 100)
  - `DMZ` (Tingkat Kepercayaan Menengah: 50)
  - `OUTSIDE` (Tingkat Kepercayaan Rendah: 0)
- **Golden Rule Segmentasi DMZ**:
  - Inisiasi dari `OUTSIDE` hanya diizinkan ke `DMZ` pada port spesifik (misal: TCP 443).
  - Inisiasi dari `DMZ` ke `INSIDE` **DILARANG KERAS**. DMZ tidak boleh membuka koneksi ke internal. Koneksi database harus diinisiasi oleh sistem terisolasi, atau via application pull, atau koneksi API strictly-defined dari worker internal ke DMZ, bukan sebaliknya.

```
       +------------------+
       |     OUTSIDE      | (Internet)
       +--------+---------+
                |
          [ Firewall ]
         /            \
        /              \
+------+----+     +-----+-----+
|    DMZ    |     |  INSIDE   |
| (Web/LB)  |     | (DB/Core) |
+-----------+     +-----------+
* OUTSIDE -> DMZ: Permitted (TCP 443)
* OUTSIDE -> INSIDE: Denied Explicitly
* DMZ -> INSIDE: STRICTLY DENIED (Blast Radius Isolation)
* INSIDE -> DMZ: Permitted (Admin/Management)
```

### 5.4 IPsec Deep-Dive (IKEv1 vs. IKEv2, AH vs. ESP)
IPsec beroperasi di Layer 3 untuk menyediakan kerangka kerja suite protokol kriptografis:

#### Internet Key Exchange (IKE):
- **IKEv1**:
  - *Phase 1* (Membentuk IKE SA / ISAKMP SA): Negosiasi cipher suite dan otentikasi identitas.
    - Main Mode: 6 pesan (identitas terenkripsi, proteksi eavesdropping).
    - Aggressive Mode: 3 pesan (identitas tidak terenkripsi, rentan offline hash cracking, digunakan jika IP statis tidak tersedia).
  - *Phase 2* (Membentuk IPsec SA / Quick Mode): 3 pesan untuk negosiasi symmetric key data-plane (ESP/AH).
- **IKEv2 (RFC 7296)**:
  - Menggantikan kompleksitas IKEv1 dengan reduksi latency dan pesan exchange.
  - Negosiasi IKE SA hanya membutuhkan 4 pesan dasar:
    1. `IKE_SA_INIT` (Exchange pesan 1 & 2): Negosiasi cryptographic proposal, Diffie-Hellman nonce exchange.
    2. `IKE_AUTH` (Exchange pesan 3 & 4): Transmisi identitas terenkripsi, sertifikat/PSK, dan pembentukan Child SA pertama (IPsec SA).
  - Built-in NAT Traversal (NAT-T via UDP port 4500), built-in Dead Peer Detection (DPD), dan resistensi DoS via cookie exchange mekanis.

#### Diffie-Hellman (DH) Key Exchange:
Protokol pembentukan shared secret key melalui saluran publik yang tidak aman.
- DH Group 1 (768-bit), Group 2 (1024-bit), Group 5 (1536-bit): **DEPRECATED & INSECURE**.
- Standard Modern Enterprise:
  - DH Group 14 (2048-bit MODP)
  - DH Group 19 (256-bit Elliptic Curve / ECP256)
  - DH Group 20 (384-bit ECP384)

#### Authentication Header (AH) vs. Encapsulating Security Payload (ESP):
- **AH (IP Protocol 51)**:
  - Memberikan integritas dan otentikasi asal paket terhadap seluruh paket, **termasuk outer IP header**.
  - **Kelemahan Fatal**: Jika paket melewati Network Address Translation (NAT), router NAT akan mengubah IP header (Src/Dst IP). Hal ini menyebabkan kalkulasi integritas hash AH invalid dan paket di-drop. AH tidak mengenkripsi payload (no confidentiality).
- **ESP (IP Protocol 50)**:
  - Memberikan enkripsi (confidentiality), otentikasi asal data, dan anti-replay protection.
  - Melindungi payload IP, bukan outer IP header. Kompatibel dengan NAT melalui enkapsulasi NAT-Traversal (UDP 4500).

```
Transport Mode vs Tunnel Mode ESP:

Transport Mode (Host-to-Host):
[ Orig IP Hdr ] [ ESP Hdr ] [ TCP/UDP Payload ] [ ESP Trailer ] [ ESP Auth ]
|<--- Unencrypted -------->|<------ Encrypted ----------------->|

Tunnel Mode (Gateway-to-Gateway Network Encryption):
[ New IP Hdr ] [ ESP Hdr ] [ Orig IP Hdr ] [ TCP/UDP ] [ ESP Trl ] [ ESP Auth ]
|<-- Clear -->|<-------------- Encrypted ------------------------>|
```

### 5.5 GRE over IPsec
- **Keterbatasan Utama IPsec Murni**: IPsec Tunnel Mode tidak mendukung transmisi paket **Multicast** atau **Broadcast**. Akibatnya, dynamic routing protocol (OSPF hello menggunakan multicast `224.0.0.5`/`224.0.0.6`, BGP peering link-local) tidak dapat berjalan langsung di atas native IPsec tunnel.
- **Solusi Arsitektur**: Membungkus paket Multicast/Routing ke dalam enkapsulasi Generic Routing Encapsulation (GRE - IP Protocol 47), kemudian mengenkripsi paket GRE tersebut menggunakan IPsec Tunnel/Transport Mode.
- **Packet Sizing & Overhead**:
  - Standar MTU: 1500 byte.
  - IPv4 Outer Header: 20 byte.
  - ESP Header + IV: ~16 byte.
  - GRE Header: 4 atau 8 byte.
  - Original IPv4 Header: 20 byte.
  - TCP Header: 20 byte.
  - ESP Trailer + ICV: ~16–24 byte.
  - **Total Overhead**: ~56 hingga 76 byte.
  - **Rekomendasi**: Konfigurasi Tunnel MTU menjadi `1400` dan clamping `ip tcp adjust-mss 1360` untuk mencegah packet fragmentation.

```
+-----------------------------------------------------------------------------------+
| Outer IP (20B) | ESP Hdr (8B) | GRE (4B) | Inner IP (20B) | TCP (20B) | Payload... | ESP Trl/Auth |
+-----------------------------------------------------------------------------------+
|<-------- Encrypted by IPsec ESP ------------------------------------------------->|
```

### 5.6 MACsec (IEEE 802.1AE)
- Bekerja pada Layer 2 (Data Link Layer).
- Berbeda dengan IPsec yang mengenkripsi antar Layer 3 gateway, MACsec mengenkripsi seluruh frame Ethernet (termasuk tag VLAN jika di-strip, kecuali Source/Destination MAC address dan 802.1AE SecTAG header).
- Eksekusi kriptografis line-rate menggunakan hardware switching ASIC khusus tanpa degradasi latency.
- Melindungi inter-switch links dan host-to-switch links dari eavesdropping fisik, Man-in-the-Middle tapping pada fiber optic, dan injection frame berbahaya.

### 5.7 IEEE 802.1X Port Security Architecture
Arsitektur otentikasi port berbasis client-server untuk memblokir port fisik switch sebelum entitas pengguna terotentikasi:
- Tiga Komponen Kunci:
  1. **Supplicant**: Software client pada endpoint (misal: Windows 802.1x service, `wpa_supplicant` di Linux).
  2. **Authenticator**: Network Access Device (NAD) seperti L2 Switch atau Wireless Access Controller. Port ditahan pada kondisi *unauthorized* (hanya memproses frame EAPoL).
  3. **Authentication Server**: Server terpusat (RADIUS/Cisco ISE/FreeRADIUS) yang memverifikasi kredensial atau sertifikat digital (EAP-TLS/EAP-PEAP).

```
[ Supplicant ]                 [ Authenticator (Switch) ]            [ Auth Server (RADIUS) ]
      |                                    |                                    |
      |--- 1. EAPoL-Start ---------------->|                                    |
      |<-- 2. EAP-Request Identity --------|                                    |
      |--- 3. EAP-Response Identity ------>|--- 4. RADIUS Access-Request ------>|
      |                                    |<-- 5. RADIUS Access-Challenge -----|
      |<-- 6. EAP-Request (TLS Neg) -------|                                    |
      |--- 7. EAP-Response (TLS Cert) ---->|--- 8. RADIUS Access-Request ------>|
      |                                    |<-- 9. RADIUS Access-Accept --------|
      |<-- 10. EAP-Success ----------------| (Port Transition: Unauthorized -> Authorized)
```

---

## 6. How
Implementasi keamanan jaringan komprehensif mengikuti tahapan terstruktur:
1. **Zonasi & Segmentasi**: Identifikasi aset, kelaskan ke dalam zona (`trusted`, `dmz`, `untrusted`, `database`).
2. **Definisi Policy Matrix**: Buat matriks lalu lintas yang mengizinkan flow inisiasi secara strictly defined, tolak sisanya dengan default-deny.
3. **Tunneling & Encryption**: Pasang site-to-site GRE over IPsec IKEv2 untuk mengamankan link inter-site WAN/Cloud.
4. **Edge Security**: Pasang 802.1X di access switch port untuk otentikasi perangkat fisik dan MACsec untuk enkripsi backbone switch-to-switch.
5. **Stateful Hardening**: Terapkan rate-limiting, TCP MSS clamping, dan connection tracking tuning pada edge gateway.

---

## 7. Analogy
Bayangkan sebuah **Bandar Udara Internasional Berkeamanan Tinggi**:
- **Stateless ACL**: Penjaga pintu masuk yang hanya memeriksa apakah orang tersebut memakai tiket. Siapa pun bertiket diizinkan lewat, tanpa peduli apakah dia keluar-masuk berulang kali tanpa tujuan atau menyelundupkan barang.
- **Stateful Firewall (SPI)**: Petugas imigrasi yang mencap paspor dan merekam boarding pass di sistem komputer pusat (*state table*). Saat Anda kembali dari gate kedatangan, petugas mencocokkan wajah dan stempel keluar Anda. Jika Anda tiba-tiba muncul di ruang klaim bagasi tanpa pernah melewati imigrasi masuk, Anda langsung ditangkap (*dropped*).
- **DMZ**: Area ruang tunggu transit bandara sebelum imigrasi utama. Penumpang luar (Internet) boleh menunggu dan makan di kafe transit (DMZ Web Server), tetapi mereka tidak dapat melangkah langsung ke kantor pusat otoritas bandara (Internal Database) tanpa jalur keamanan khusus berlapis.
- **IPsec IKEv2**: Mobil lapis baja bersenjata yang membawa dokumen rahasia antar terminal bandara melintasi jalan raya umum. Kunci brankas dinegosiasikan menggunakan kode matematika acak tingkat tinggi (Diffie-Hellman).
- **802.1X**: Pintu putar berputar otomatis di gerbang karyawan yang tidak akan berputar satu milimeter pun sebelum kartu identitas pintar (smartcard EAP-TLS) ditempelkan ke reader dan diverifikasi oleh server pusat bandara.

---

## 8. Diagram (ASCII)

### Arsitektur End-to-End Enterprise Perimeter & Cryptographic Tunneling

```
                     +---------------------------------------+
                     |         WAN / Internet Fabric         |
                     +---------------------------------------+
                                         |
                                         | (Untrusted Public IP)
                                         v
                         +-------------------------------+
                         |   Edge Router (Cisco IOS-XE)  |
                         |   ZFW Zone: "OUTSIDE"         |
                         +---------------+---------------+
                                         |
                 +-----------------------+-----------------------+
                 | (Crypto IPsec IKEv2 Tunnel / GRE Encapsulation)|
                 v                                               v
+---------------------------------+             +---------------------------------+
|  Zone: "DMZ"                    |             |  Zone: "INSIDE"                 |
|  IP Subnet: 192.168.50.0/24     |             |  IP Subnet: 10.10.0.0/16        |
|  - Reverse Proxy (Nginx)        |             |  - Microservices Engine         |
|  - Bastion Host                 |             |  - Enterprise Database          |
+---------------------------------+             +----------------+----------------+
                                                                 |
                                                                 v
                                                +---------------------------------+
                                                | Access Switch (802.1X & MACsec) |
                                                +----------------+----------------+
                                                                 | (EAPoL Port Auth)
                                                                 v
                                                [ Authorized Corporate Workstation]
```

### Zone-Based Policy Direction Matrix

```
Source Zone  \  Destination Zone |  OUTSIDE   |    DMZ     |   INSIDE   |    SELF    |
---------------------------------+------------+------------+------------+------------+
OUTSIDE                          |    DROP    |  INSPECT*  |    DROP    |  INSPECT*  |
                                 |            | (TCP 443)  |            | (IKE/BGP)  |
---------------------------------+------------+------------+------------+------------+
DMZ                              |  INSPECT   |    PASS    |    DROP    |    DROP    |
---------------------------------+------------+------------+------------+------------+
INSIDE                           |  INSPECT   |  INSPECT   |    PASS    |  INSPECT   |
---------------------------------+------------+------------+------------+------------+
SELF                             |    PASS    |    PASS    |    PASS    |    PASS    |
---------------------------------+------------+------------+------------+------------+
* INSPECT: Stateful permit (membuat entri conntrack untuk return flow otomatis).
* PASS: Stateless permit langsung.
* DROP: Implicit/explicit deny.
```

---

## 9. Simple Example

### Stateless ACL vs. Stateful Inspection (Konsep Linux CLI)

**Stateless ACL (Raw Iptables tanpa conntrack):**
```bash
# Mengizinkan traffic keluar HTTP/HTTPS
iptables -A OUTPUT -p tcp -m multiport --dports 80,443 -j ACCEPT

# Bahaya: Anda HARUS membuka SEMUA port masuk tinggi untuk return traffic!
iptables -A INPUT -p tcp --sports 80,443 --dport 1024:65535 -j ACCEPT
# Stateless vulnerability: Penyerang bisa mengirim paket dengan Sport 80 ke Dport 2222 tanpa SYN handshake!
```

**Stateful Packet Inspection (nftables / conntrack):**
```bash
# Membuat table dan base chain stateful
nft add table inet filter
nft add chain inet filter input { type filter hook input priority 0 \; policy drop \; }
nft add chain inet filter output { type filter hook output priority 0 \; policy accept \; }

# Izinkan traffic yang sudah established atau related secara stateful
nft add rule inet filter input ct state established,related accept

# Drop paket state invalid
nft add rule inet filter input ct state invalid drop

# Izinkan inisiasi baru ke web server port 443
nft add rule inet filter input tcp dport 443 ct state new accept
```

---

## 10. Practical Example (Konfigurasi CLI Hands-on)

### Bagian A: Implementasi Cisco IOS-XE Zone-Based Firewall (ZFW)

```cisco
! =======================================================
! 1. DEFINISI ZONA KEAMANAN
! =======================================================
zone security INSIDE
zone security OUTSIDE
zone security DMZ

! =======================================================
! 2. DEFINISI TRAFFIC CLASSIFICATION (CLASS-MAP)
! =======================================================
ip access-list extended ACL-INSIDE-TO-OUTSIDE
 permit ip 10.10.0.0 0.0.255.255 any

ip access-list extended ACL-OUTSIDE-TO-DMZ
 permit tcp any host 192.168.50.10 eq 443

class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match access-group name ACL-INSIDE-TO-OUTSIDE

class-map type inspect match-any CM-OUTSIDE-TO-DMZ
 match access-group name ACL-OUTSIDE-TO-DMZ

! =======================================================
! 3. DEFINISI INSPECTION POLICY (POLICY-MAP)
! =======================================================
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log

policy-map type inspect PM-OUTSIDE-TO-DMZ
 class type inspect CM-OUTSIDE-TO-DMZ
  inspect
 class class-default
  drop log

! =======================================================
! 4. DEFINISI ZONE-PAIRS DAN ASOSIASI POLICY
! =======================================================
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE

zone-pair security ZP-OUTSIDE-DMZ source OUTSIDE destination DMZ
 service-policy type inspect PM-OUTSIDE-TO-DMZ

! =======================================================
! 5. MENETAPKAN INTERFACE KE DALAM ZONA
! =======================================================
interface GigabitEthernet0/0/0
 description UPLINK-INTERNET
 zone-member security OUTSIDE
 ip address 203.0.113.2 255.255.255.252

interface GigabitEthernet0/0/1
 description INTERNAL-LAN
 zone-member security INSIDE
 ip address 10.10.1.1 255.255.0.0

interface GigabitEthernet0/0/2
 description DMZ-SEGMENT
 zone-member security DMZ
 ip address 192.168.50.1 255.255.255.0
```

### Bagian B: GRE over IPsec IKEv2 Configuration (Cisco IOS-XE)

```cisco
! =======================================================
! 1. IKEv2 PROPOSAL & POLICY (PHASE 1)
! =======================================================
crypto ikev2 proposal IKEV2-PROP-ENTERPRISE
 encryption aes-gcm-256
 prf sha384
 group 19

crypto ikev2 policy IKEV2-POL-ENTERPRISE
 proposal IKEV2-PROP-ENTERPRISE

! =======================================================
! 2. IKEv2 KEYRING (PRE-SHARED KEY)
! =======================================================
crypto ikev2 keyring KR-REMOTE-HQ
 peer HQ-GATEWAY
  address 198.51.100.1
  pre-shared-key EnterpriseRobustKey2026!Secured

! =======================================================
! 3. IKEv2 PROFILE
! =======================================================
crypto ikev2 profile IKEV2-PROF-HQ
 match identity remote address 198.51.100.1 255.255.255.255
 identity local address 203.0.113.2
 authentication remote pre-share
 authentication local pre-share
 keyring local KR-REMOTE-HQ
 lifetime 28800

! =======================================================
! 4. IPsec TRANSFORM SET (PHASE 2) & IPsec PROFILE
! =======================================================
crypto ipsec transform-set TS-AES-GCM esp-gcm 256
 mode transport
! Note: Transport mode digunakan karena IPsec membungkus header GRE (menghemat 20-byte IP header)!

crypto ipsec profile IPSEC-PROF-GRE
 set transform-set TS-AES-GCM
 set ikev2-profile IKEV2-PROF-HQ

! =======================================================
! 5. GRE TUNNEL INTERFACE DENGAN IPSEC PROTECTION & MSS CLAMPING
! =======================================================
interface Tunnel100
 description GRE-OVER-IPSEC-TO-HQ
 ip address 172.16.254.2 255.255.255.252
 tunnel source GigabitEthernet0/0/0
 tunnel destination 198.51.100.1
 tunnel protection ipsec profile IPSEC-PROF-GRE
 ip mtu 1400
 ip tcp adjust-mss 1360
```

---

## 11. Real World Example
Sebuah institusi perbankan fintech menghubungkan infrastruktur on-premises core banking dengan AWS Cloud Transit Gateway via dua dedicated link berkecepatan 10 Gbps (AWS Direct Connect).
- **Kebutuhan**: Regulasi moneter mewajibkan semua transmisi transaksi perbankan dienkripsi menggunakan standar kriptografi FIPS 140-2 Level 3 saat melintasi link fisik eksternal, dengan dukungan routing BGP dinamik dan toleransi failover sub-detik.
- **Solusi Arsitektur**:
  1. Di level fisik, dipasang **MACsec (802.1AE)** 256-bit point-to-point antara router on-prem dan switch penyedia Direct Connect untuk mencegah optical tapping.
  2. Di level transport, dibangun dual-tunnel **GRE over IPsec IKEv2 (AES-GCM-256, DH Group 19)** ke AWS Transit Gateway.
  3. Mengaktifkan **BGP over GRE** dengan **BFD (Bidirectional Forwarding Detection)** interval 300ms untuk failover otomatis.
  4. Stateful Firewall ZFW diterapkan di perimeter on-prem untuk memastikan transaksi hanya diizinkan dari subnet Microservices AWS menuju database Core Banking port 5432, dengan *session tracking* dan mitigasi TCP out-of-order injection.

---

## 12. Trade-offs

| Aspek | Stateless ACL | Stateful Inspection (SPI) | IPsec Native Tunnel | GRE over IPsec | MACsec (802.1AE) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Layer Operasi** | L3 / L4 | L3 / L4 / L7 Tracking | Layer 3 | Layer 3 Tunneling | Layer 2 |
| **Performance Overhead** | Hampir 0 (Wire-speed TCAM) | Konsumsi CPU & Memory (State Table) | Enkripsi/Dekripsi CPU Crypto ASIC | Enkripsi + GRE Encapsulation (~76B) | Wire-speed via Dedicated Switching ASIC |
| **Dynamic Routing Support** | N/A | N/A | Tidak (Tidak dukung Multicast) | **Ya** (Mendukung OSPF/BGP) | **Ya** (Transparan di L2) |
| **Security Granularity** | Rendah (Port/IP statis) | Tinggi (State aware, SYN-flood aware) | Tinggi (L3 End-to-End Cryptography) | Tinggi (L3 Dynamic Encrypted) | Menengah/Tinggi (Hop-by-hop link level) |
| **Skalabilitas Sesi** | Tidak terbatas oleh memori state | Dibatasi kapasitas memori RAM (Max Sessions) | Terbatas jumlah Crypto SA Hardware Limits | Terbatas Crypto SA & MTU complexity | Terbatas kesesuaian hardware inter-switch |

---

## 13. When To Use
- **Stateless ACLs**: Di edge backbone core router untuk dropping traffic DDoS/bogon IP dalam skala jutaan paket per detik (Line-Rate scrubbing) tanpa membebani RAM state table.
- **Stateful Firewalls (ZFW/DMZ)**: Di setiap perimeter demarkasi batas kepercayaan (Internet-to-LAN, DMZ-to-Core, Kube-to-DB).
- **IPsec IKEv2**: Menghubungkan branch office ke Data Center atau Cloud VPC melalui Internet umum.
- **GRE over IPsec**: Ketika topologi WAN terenkripsi memerlukan pertukaran rute otomatis via OSPF, EIGRP, atau eBGP/iBGP.
- **MACsec**: Melindungi link inter-datacenter Dark Fiber/DWDM atau link kabel fisik antar-lantai di kampus enterprise terhadap serangan *physical interception*.
- **802.1X**: Seluruh port akses LAN kantor dan Wi-Fi enterprise untuk validasi sertifikat/identitas perangkat sebelum IP dialokasikan via DHCP.

---

## 14. When NOT To Use
- **Jangan gunakan SPI**: Pada high-frequency trading (HFT) core networks yang menuntut latensi sub-mikrodetik, atau edge DDoS mitigation pipeline tahap pertama yang berpotensi melumpuhkan firewall via memory exhaustion (State Table Exhaustion DoS).
- **Jangan gunakan IPsec Native Tunnel**: Jika Anda ingin menjalankan OSPF atau dynamic multi-path routing yang membutuhkan paket broadcast/multicast (gunakan GRE over IPsec atau VTI).
- **Jangan gunakan IPsec AH**: Jika jaringan melewati NAT (Network Address Translation) atau Port Forwarding, karena integritas hash AH akan langsung rusak.
- **Jangan gunakan MACsec**: Pada tautan WAN Layer 3 murni melintasi ISP routed cloud (karena header MACsec di-strip oleh router L3 penyedia ISP).

---

## 15. Common Mistakes
1. **Asymmetric Routing Black Hole**: Traffic inisiasi (SYN) masuk melalui Firewall-A, tetapi link load balancing mengirim return traffic (SYN-ACK) melalui Firewall-B. Firewall-B membuang paket karena tidak memiliki entri state table terkait. Solusi: Gunakan clustering session synchronization protocol (misal: Cisco ASR Cluster / pfSync) atau pastikan routing simetris.
2. **Mengabaikan MTU/MSS Clamping**: Membiarkan default MTU 1500 byte pada interface GRE over IPsec tanpa mengaktifkan MSS clamping. Paket TCP berukuran besar (1460 byte) ditambah overhead IPsec (76 byte) menghasilkan paket 1536 byte. Jika router upstream mengaktifkan Don't Fragment (DF), koneksi HTTP/TLS macet permanen (hang saat transfer data payload besar).
3. **Konfigurasi IKEv1 Aggressive Mode dengan PSK Lemah**: Membuka port UDP 500 dengan Aggressive Mode mengekspos hash Pre-Shared Key dalam bentuk hash yang dapat di-sniff dan di-crack secara offline via dictionary attack.
4. **DMZ Diizinkan Menginisiasi Koneksi ke Internal**: Mengizinkan server web di DMZ melakukan inisiasi koneksi ke database internal port SQL, bukan membatasi DMZ hanya menerima respon. Jika web server dieksploitasi RCE (Remote Code Execution), penyerang memiliki rute inisiasi langsung ke core network.

---

## 16. Best Practices
1. **Standard Cryptographic Blueprint**: Wajibkan IKEv2, IKE SA Proposal menggunakan AES-GCM-256 (Authenticated Encryption), Integrity hashing minimal SHA-384, dan Diffie-Hellman Group 19 (ECP-256) atau Group 20 (ECP-384). Matikan 3DES, MD5, SHA-1, dan DH Group 1, 2, 5.
2. **Aggressive TCP MSS Clamping**: Pasang `ip tcp adjust-mss 1360` pada semua Virtual Tunnel Interfaces (VTI) atau GRE interfaces untuk mengantisipasi overhead kriptografi dan variasi MTU jalur provider WAN.
3. **Explicit Drop & Logging**: Di ZFW, buat policy default drop dengan parameter logging diaktifkan (`drop log`) untuk memfasilitasi SIEM log ingestion dan audit forensik SOC.
4. **Isolasi Self Zone**: Lindungi control plane router dengan menerapkan policy ketat pada zone-pair `OUTSIDE to self`. Hanya izinkan IP peer terdaftar untuk negosiasi IPsec (UDP 500, UDP 4500) dan protokol BGP (TCP 179).

---

## 17. Troubleshooting

### Skenario 1: Terowongan IPsec IKEv2 Gagal Terbentuk (State Down)
- **Gejala**: `show crypto ikev2 sa` kosong atau berstatus `IN-NEG`.
- **Command Diagnostik**:
  ```cisco
  show crypto ikev2 sa
  show crypto ikev2 session
  debug crypto ikev2
  ```
- **Analisis Root Cause**:
  1. Periksa UDP 500 dan UDP 4500 pada upstream firewall intermediate (pastikan tidak terblokir).
  2. Periksa kesesuaian parameter kriptografis: Jika debug menampilkan `NO_PROPOSAL_CHOSEN`, pastikan proposal enkripsi, integritas, dan DH group identik di kedua sisi.
  3. Periksa Pre-Shared Key: Log pesan `AUTHENTICATION_FAILED` mengindikasikan mismatch PSK atau konfigurasi remote address identifier yang salah.

### Skenario 2: Ping Berhasil, tetapi Data Transfer TCP (HTTPS/SSH) Macet
- **Gejala**: ICMP ping 64-byte over tunnel lancar, tetapi curl HTTPS atau download payload besar macet (hanging).
- **Command Diagnostik**:
  ```bash
  # Uji MTU dengan flag Do Not Fragment dari host
  ping -M do -s 1472 172.16.254.1
  # Periksa statistik interface
  show interface Tunnel100 | include MTU
  ```
- **Solusi**: Packet fragmentation terbentur overhead crypto. Terapkan MSS clamping:
  ```cisco
  interface Tunnel100
   ip mtu 1400
   ip tcp adjust-mss 1360
  ```

### Skenario 3: Traffic Di-drop oleh ZFW pada Koneksi yang Valid
- **Gejala**: Log router mencetak `%FW-6-DROP_SUB` atau `%FW-4-TCP_ILLEGAL_STATE`.
- **Command Diagnostik**:
  ```cisco
  show policy-firewall stats
  show policy-firewall session platform
  show zone-pair security
  ```
- **Solusi**: Verifikasi apakah koneksi kembali (return traffic) melewati zone-pair yang salah atau flow mengalami asymmetric routing. Pastikan traffic diklasifikasikan dengan action `inspect`, bukan sekadar `pass` (karena `pass` bersifat stateless dan tidak membuat return state tracking).

---

## 18. Exercise
Sebuah router edge cabang terhubung ke internet via interface GigabitEthernet0/0/0. Anda ditugaskan mengonfigurasi IPsec tunnel ke Data Center. Hitung parameter jaringan berikut:
1. Diketahui MTU path ISP = 1500 byte.
2. Anda menggunakan GRE over IPsec Tunnel Mode dengan suite: ESP-AES-256-GCM (overhead total enkapsulasi + IV + ICV + GRE + outer IP = 76 byte).
3. Berapa nilai maximum safe payload TCP MTU yang dapat dilewatkan tanpa memicu fragmentasi?
4. Berapa nilai `ip tcp adjust-mss` yang harus dikonfigurasi pada tunnel interface jika TCP header standar adalah 20 byte dan IP header adalah 20 byte?

*Petunjuk Jawaban*:
- Tunnel IP MTU = 1500 - 76 = 1424 byte.
- TCP MSS = Tunnel IP MTU - IP Header (20B) - TCP Header (20B) = 1424 - 40 = 1384 byte.
- Nilai konvensional yang aman direkomendasikan adalah 1360 atau 1380 byte.

---

## 19. Challenge
Rancang arsitektur perimeter hybrid cloud untuk perusahaan multinasional dengan spesifikasi teknis berikut:
- **On-Premise Core**: 2 unit Core Firewall active/standby.
- **Multi-Cloud**: VPC Production di AWS dan VNet Production di Azure.
- **Persyaratan Segmentasi**:
  1. Konektivitas inter-cloud (AWS to Azure) dan cloud-to-onprem harus dienkripsi via IPsec IKEv2 dengan dynamic BGP rerouting otomatis saat link AWS Direct Connect terputus ke link cadangan Internet IPsec.
  2. Implementasikan Zone-Based Security Matrix yang mengisolasi database on-prem dari akses langsung Internet, hanya membolehkan traffic HTTPS yang di-reverse proxy oleh DMZ Envoy Cluster.
  3. Konfigurasikan MTU & MSS clamping strategy secara presisi agar tidak terjadi packet fragmentation pada throughput 1 Gbps.
  4. Gambarkan diagram arsitektur interkoneksi dan tuliskan tabel rule zone matrix lengkap.

---

## 20. Summary
1. **Stateless vs Stateful**: Stateless ACL (TCAM) memvalidasi paket secara atomik tanpa memori; Stateful Inspection (SPI) memelihara *conntrack state table* yang melacak siklus hidup koneksi L4 untuk kontrol keamanan dinamis.
2. **Zone-Based Firewalling**: Mengabstraksi perimeter fisik menjadi zona logis. Seluruh komunikasi default-deny kecuali antar interface di zona yang sama atau jika didefinisikan secara eksplisit pada Zone-Pair.
3. **DMZ Boundary Isolation**: Mencegah eskalasi lateral movement dengan melarang keras koneksi yang diinisiasi dari zona DMZ langsung menuju zona Internal yang lebih tepercaya.
4. **Cryptographic Foundations**: IKEv2 mereduksi handshake overhead menjadi 4 paket fundamental. ESP memberikan proteksi otentikasi dan kerahasiaan payload dan kompatibel dengan NAT (via UDP 4500). AH tidak boleh digunakan di belakang NAT.
5. **GRE over IPsec**: Solusi standar enkripsi traffic dynamic routing protocol (OSPF/BGP) yang membutuhkan dukungan multicast di atas terowongan IPsec. Wajib dikombinasikan dengan TCP MSS clamping untuk mencegah PMTUD black hole.
6. **L2 Defense & 802.1X**: Keamanan perimeter dimulai dari port fisik edge switch dengan otentikasi EAPoL 802.1X, dipadukan dengan MACsec (802.1AE) untuk enkripsi fisik data-link line-rate tanpa degradasi latensi.

---