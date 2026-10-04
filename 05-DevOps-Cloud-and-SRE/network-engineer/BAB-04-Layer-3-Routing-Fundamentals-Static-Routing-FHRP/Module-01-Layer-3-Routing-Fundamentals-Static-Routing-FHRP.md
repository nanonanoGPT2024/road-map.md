# Modul 01: Layer 3 Routing Fundamentals, Static Routing, dan First Hop Redundancy Protocols (FHRP)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengurai anatomi Forwarding Information Base (FIB) dan Routing Information Base (RIB) pada level kernel dan hardware (TCAM).
- Menganalisis algoritma evaluasi rute berdasarkan **Longest Prefix Match (LPM)**, **Administrative Distance (AD)**, dan **Metric**.
- Mengonfigurasi dan memvalidasi *Static Routing*, *Default Routing*, dan *Floating Static Routing* dengan teknik IP SLA Tracking untuk failover otomatis.
- Mengimplementasikan solusi *Inter-VLAN Routing* menggunakan *Router-on-a-Stick* (802.1Q subinterfaces) dan Layer 3 Switched Virtual Interfaces (SVI).
- Membedakan arsitektur, mekanisme state machine, format paket multicast, dan kalkulasi Virtual MAC pada FHRP (**HSRP**, **VRRPv2/v3**, **GLBP**).
- Mendiagnosis dan memitigasi kegagalan first-hop gateway pada infrastruktur on-premises maupun hybrid cloud environment.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Layer 2 Switching**: VLAN (802.1Q), Frame Tagging, Trunking, Spanning Tree Protocol (STP/RSTP).
- **Pengalamatan IPv4 & IPv6**: Subnetting VLSM, CIDR notation, kalkulasi host/network address, broadcast domain limits.
- **Analisis Paket Dasar**: Penggunaan Wireshark atau `tcpdump` untuk menangkap frame Ethernet, ARP, ICMP, dan enkapsulasi Layer 2/3.
- **Model OSI & TCP/IP**: Khususnya interaksi antara proses enkapsulasi Layer 3 (IP header, TTL, Checksum) dan Layer 2 (ARP resolution, Source/Destination MAC swap).

---

## 3. Concept
Layer 3 Routing adalah proses penentuan jalur (path determination) dan pengalihan paket (packet switching/forwarding) dari network asal (source network) menuju network tujuan (destination network) yang melintasi batasan broadcast domain. 

Pada intinya, router atau Layer 3 switch tidak pernah meneruskan broadcast domain Layer 2; melainkan membongkar frame Layer 2 yang masuk, memeriksa IP header Layer 3, mencocokkan IP tujuan dengan tabel routing, menurunkan nilai *Time to Live* (TTL), menghitung ulang *IP Header Checksum*, dan mengenkapsulasi ulang payload ke dalam frame Layer 2 baru dengan source MAC router pengirim dan destination MAC perangkat hop berikutnya (next-hop IP) atau host tujuan via ARP.

Tiga pilar fundamental yang mengatur routing:
1. **Routing Table Anatomy & Decision Hierarchy**: Pemilihan jalur terbaik berdasarkan *Longest Prefix Match* (prioritas mutlak), disusul oleh *Administrative Distance* (kepercayaan terhadap sumber rute), dan *Metric* (bobot internal protokol).
2. **Deterministic Path Control (Static Routing)**: Penentuan lintasan data secara manual tanpa overhead pertukaran protokol, dilengkapi teknik redundansi deterministik (*Floating Static Routes*).
3. **Gateway Resiliency (FHRP)**: Eliminasi *Single Point of Failure* (SPOF) pada default gateway host akhir melalui virtualisasi IP dan MAC address bersama (HSRP/VRRP/GLBP).

---

## 4. Why
Mengapa Layer 3 Routing dan FHRP mutlak dipahami secara mendalam oleh DevOps, Platform Engineer, dan SRE?

1. **Microsegmentation & Blast Radius Isolation**: Jaringan flat Layer 2 membawa risiko fatal: broadcast storms, bridging loops (STP convergence delay), dan eskalasi lateral movement malware. Layer 3 memecah broadcast domain menjadi sel-sel terisolasi.
2. **High Availability Tanpa Intervensi Klien**: Host akhir (server database, worker node Kubernetes, instance VM) umumnya hanya mengonfigurasi satu alamat Default Gateway. Tanpa FHRP, matinya upstream top-of-rack (ToR) switch atau router fisik akan memutus seluruh cluster dari jaringan luar, meskipun link cadangan tersedia.
3. **Optimasi Throughput Data Center**: Dengan beralih dari Router-on-a-Stick ke hardware Layer 3 Switch berarsitektur CEF (Cisco Express Forwarding) dan TCAM, forwarding paket dieksekusi pada *wire-speed* gigabit/terabit tanpa membebani control-plane CPU.
4. **Hybrid Cloud Integration**: Interkoneksi AWS Direct Connect, Azure ExpressRoute, atau Google Cloud Interconnect selalu berakhir pada Layer 3 router/BGP peer on-premises. Kesalahan konfigurasi rute statis, AD mismatch, atau rute asimetris akan menyebabkan *blackholing* trafik cloud-to-onprem.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Anatomi Routing Table & Arsitektur Forwarding
Secara arsitektur, perangkat Layer 3 modern memisahkan dua domain komputasi:
- **Control Plane (RIB - Routing Information Base)**: Dikelola oleh CPU utama perangkat. Berisi semua rute yang dipelajari dari connected, static, dan dynamic routing protocols (OSPF, BGP, EIGRP). Rute terbaik dari RIB diekspor ke FIB.
- **Data/Forwarding Plane (FIB - Forwarding Information Base & Adjacency Table)**: Dipetakan ke hardware terakselerasi (ASIC/TCAM - *Ternary Content Addressable Memory*). FIB menyimpan mapping IP prefix ke next-hop interface secara langsung, menghilangkan penundaan recursive lookup.

Komponen baris routing table (RIB):
```text
  D    10.240.12.0/24 [90/5632] via 192.168.1.2, 00:12:34, GigabitEthernet0/1
  ^           ^           ^  ^            ^           ^            ^
Protocol  Prefix/Mask    AD Metric     Next-Hop     Uptime      Egress Intf
```

### 5.2 Algoritma Evaluasi Rute: Tiga Aturan Mutlak
Ketika sebuah paket tiba dengan IP tujuan spesifik (misal: `172.16.10.55`), router memproses pemilihan rute dengan hirarki ketat:

1. **Aturan 1: Longest Prefix Match (LPM)**
   Router membandingkan bit alamat tujuan dengan subnet mask dari semua rute yang ada di tabel. Prefix dengan jumlah bit `1` paling banyak (paling spesifik) **SELALU MENANG**, tanpa mempedulikan Administrative Distance atau Metric.
   - Contoh kasus:
     - Rute A: `172.16.0.0/16` (Static, AD: 1)
     - Rute B: `172.16.10.0/24` (OSPF, AD: 110)
     - Rute C: `172.16.10.48/28` (BGP, AD: 20)
     - Rute D: `172.16.10.52/30` (RIP, AD: 120)
   - Paket menuju `172.16.10.55`:
     Rentang `/30` (`172.16.10.52` s/d `172.16.10.55`) mencakup target. Karena `/30` adalah prefix terpanjang yang cocok, **Rute D (RIP, AD 120) yang dipilih**, mengabaikan rute Static dan BGP.

2. **Aturan 2: Administrative Distance (AD)**
   Hanya dievaluasi jika router menerima dua atau lebih rute identik menuju **prefix dan prefix-length yang sama persis** dari sumber yang berbeda. AD merepresentasikan tingkat kepercayaan (*trustworthiness*). Nilai lebih rendah = lebih dipercaya.
   
| Route Source | Default AD | Karakteristik |
| :--- | :--- | :--- |
| Connected Interface | 0 | Interface berstatus `up/up` dengan IP terkonfigurasi |
| Static Route | 1 | Rute eksplisit manual |
| eBGP | 20 | External BGP (antar Autonomous System) |
| EIGRP (Internal) | 90 | Cisco proprietary/open hybrid protocol |
| OSPF | 110 | Open standard Link-State protocol |
| IS-IS | 115 | Link-state interior gateway protocol |
| RIP | 120 | Distance-Vector protocol |
| iBGP | 200 | Internal BGP (dalam Autonomous System) |
| Unreachable / Unknown | 255 | Rute ditolak / tidak akan dipasang di FIB |

3. **Aturan 3: Metric**
   Hanya dievaluasi jika prefix sama, prefix-length sama, dan berasal dari **protokol routing yang sama**.
   - OSPF: Cost (berdasarkan bandwidth: `Reference Bandwidth / Interface Bandwidth`).
   - EIGRP: Composite Metric (Bandwidth minimum + Cumulative Delay).
   - RIP: Hop Count (maksimum 15 hop).

---

### 5.3 Static Routing, Default Routing, dan Floating Static Routes
- **Next-Hop IP vs Exit-Interface**:
  - `ip route 10.0.0.0 255.0.0.0 192.168.1.1`: Next-hop route. Memerlukan recursive lookup untuk menentukan exit-interface, namun aman pada media multi-access (Ethernet) karena router tidak perlu mengirim ARP request untuk seluruh host di network tujuan.
  - `ip route 10.0.0.0 255.0.0.0 GigabitEthernet0/0`: Directly connected static route. Pada interface Ethernet, router mengasumsikan seluruh network tujuan berada pada link Layer 2 lokal, memicu ARP storm (kecuali proxy ARP aktif di seberang).
  - `ip route 10.0.0.0 255.0.0.0 GigabitEthernet0/0 192.168.1.1`: Fully specified static route (Direkomendasikan untuk stabilitas CEF).
- **Floating Static Route**:
  Static route yang dikonfigurasi dengan AD lebih tinggi daripada rute primer (misal AD 115 atau 200). Selama rute primer (misal OSPF atau link langsung) aktif di FIB, rute floating tetap pasif di konfigurasi. Jika link primer putus, rute floating otomatis masuk ke FIB.

---

### 5.4 Inter-VLAN Routing: Arsitektur & Perbandingan

#### A. Router-on-a-Stick (RoaS)
Menggunakan satu physical link trunk (802.1Q) antara Layer 2 Switch dan Router. Router membagi interface fisik menjadi beberapa logical subinterface (misal `Gig0/0.10`, `Gig0/0.20`), masing-masing diikat dengan tag VLAN tertentu dan bertindak sebagai default gateway VLAN tersebut.
- *Bottleneck*: Terjadi *hairpinning* (trafik antar-VLAN harus bolak-balik melintasi link fisik yang sama).

#### B. Layer 3 Switch (Multilayer Switching)
Routing dilakukan langsung di switch core/distribution menggunakan **Switched Virtual Interface (SVI)** atau **Routed Port**.
- SVI (`interface Vlan10`): Interface Layer 3 virtual yang terasosiasi dengan VLAN ID tertentu di switch.
- *Forwarding Mechanism*: Pemrosesan IP packet forwarding dilakukan pada level ASIC melalui **CEF (Cisco Express Forwarding)**. Control-plane CPU tidak terlibat dalam pemindahan paket data harian. Menghilangkan bottleneck RoaS secara menyeluruh.

---

### 5.5 First Hop Redundancy Protocols (FHRP) Deep Dive

FHRP memungkinkan dua atau lebih router fisik bertindak sebagai default gateway tunggal yang virtual bagi host di suatu subnet.

```
       +-----------------------+
       |   Virtual Gateway     |
       | IP: 192.168.1.1       |
       | VMAC: 0000.5e00.01.01 |
       +-----------+-----------+
                   |
         +---------+---------+
         |                   |
+--------+--------+ +--------+--------+
| Router-01       | | Router-02       |
| Role: MASTER    | | Role: BACKUP    |
| Priority: 110   | | Priority: 100   |
| IP: 192.168.1.2 | | IP: 192.168.1.3 |
+-----------------+ +-----------------+
```

#### Komparasi Arsitektural Tiga Protokol FHRP:

| Parameter | HSRP (Hot Standby Router Protocol) | VRRP (Virtual Router Redundancy Protocol) | GLBP (Gateway Load Balancing Protocol) |
| :--- | :--- | :--- | :--- |
| **Standardisasi** | Cisco Proprietary (RFC 2281 v1, RFC 7880 v2) | Open Standard (RFC 3768 v2, RFC 5798 v3) | Cisco Proprietary |
| **Roles** | 1 Active, 1 Standby, Lainnya: Listen | 1 Master, Lainnya: Backup | 1 AVG (Active Virtual Gateway), hingga 4 AVF (Active Virtual Forwarder) |
| **Multicast IP** | `224.0.0.2` (v1), `224.0.0.102` (v2), UDP Port 1985 | `224.0.0.18` (v2/v3 IPv4), `FF02::12` (IPv6), IP Protocol 112 | `224.0.0.102`, UDP Port 3222 |
| **Virtual MAC** | v1: `0000.0c07.acXX`<br>v2: `0000.0c9f.fXXX`<br>*(XX/XXX = Group ID)* | `0000.5e00.01.XX` (v2)<br>`0000.5e00.02.XX` (v3 IPv6)<br>*(XX = VRID)* | `0007.b400.XXYY`<br>*(XX = Group, YY = Forwarder ID)* |
| **Default Timers**| Hello: 3s, Hold: 10s | Advertisement: 1s, Master Down: ~3.6s | Hello: 3s, Hold: 10s |
| **Preemption** | Non-aktif secara default | Aktif secara default | Non-aktif secara default |
| **Load Balancing**| Tidak ada (Aktif/Pasif per grup; load sharing manual via multi-group) | Tidak ada (Aktif/Pasif per grup; load sharing manual via multi-group) | **Bawaan** (Round-robin, Weighted, Host-dependent) via manipulasi ARP reply |

#### Critical Mechanisms:
1. **Preemption**: Mengizinkan router dengan priority lebih tinggi yang baru saja reboot/pulih untuk merebut kembali status Active/Master dari router dengan priority lebih rendah.
2. **Object/Interface Tracking**: Mekanisme monitoring interface WAN atau IP SLA probe. Jika interface uplink WAN mati, router secara dinamis mengurangi (decrement) priority internalnya, memicu preemption agar router sekunder mengambil alih peran Master sebelum trafik downstream mengalami *blackholing*.
3. **Gratuitous ARP (GARP)**: Dikirimkan oleh router yang baru dipromosikan menjadi Active/Master ke broadcast domain lokal untuk memperbarui tabel CAM / MAC address-table pada seluruh switch Layer 2 secara instan.

---

## 6. How
Implementasi dan deployment Layer 3 Routing & FHRP dilakukan melalui alur terstruktur:
1. **Perencanaan CIDR & VLAN Mapping**: Tentukan subnet mask, pool IP, dan alokasi VLAN gateway.
2. **Implementasi Inter-VLAN Routing**:
   - Jika kapasitas throughput < 1 Gbps: Terapkan Router-on-a-Stick via subinterfaces 802.1Q.
   - Jika kapasitas throughput enterprise / data center: Buat VLAN database, definisikan interface trunking antar-switch, dan aktifkan SVI pada core/distribution switch dengan routing engine diaktifkan (`ip routing`).
3. **Konfigurasi Path Resiliency (Static + SLA Tracking)**:
   - Buat IP SLA probe (ICMP echo) ke upstream next-hop.
   - Kaitkan status IP SLA ke tracking object.
   - Bind tracking object ke static route default gateway primer.
   - Pasang floating static route default gateway cadangan dengan AD lebih tinggi (misal: AD 200).
4. **Deploy Virtual Gateway (VRRPv3/HSRPv2)**:
   - Definisikan Virtual IP (VIP) pada interface subnet.
   - Tentukan Active/Master node dengan priority tinggi (misal: 110 vs default 100).
   - Aktifkan `preempt` dengan delay buffer (`delay minimum 30`) untuk memberi waktu stabilisasi routing table setelah reboot.
   - Hubungkan tracking WAN interface ke decrement priority FHRP.

---

## 7. Analogy
Bayangkan sebuah kantor pusat logistik paket internasional:
- **Routing Table** adalah *buku panduan sortir wilayah*.
- **Longest Prefix Match (LPM)**: Jika ada paket dengan alamat "Jl. Sudirman No. 42, RT 01, RW 02, Jakarta Pusat", petugas sortir memiliki beberapa kotak:
  - Kotak 1: "Seluruh Indonesia" (`0.0.0.0/0`)
  - Kotak 2: "DKI Jakarta" (`10.0.0.0/8`)
  - Kotak 3: "Jakarta Pusat" (`10.10.0.0/16`)
  - Kotak 4: "Jl. Sudirman No. 40-50" (`10.10.1.0/24`)
  Meskipun paket tersebut cocok dengan semua kotak, petugas **pasti** memasukkannya ke Kotak 4 karena detailnya paling spesifik (LPM).
- **Administrative Distance**: Jika ada dua kurir (Kurir Internal Terpercaya = Static Route, vs Rekomendasi Teman Luar = RIP) yang memberikan instruksi rute ke Kotak 4, kantor logistik memilih instruksi Kurir Internal (AD 1 vs AD 120).
- **FHRP (VRRP/HSRP)**: Seperti meja resepsionis berlabel "Helpdesk Umum" (Virtual IP). Ada dua staf di belakang meja: Staf A (Master) dan Staf B (Backup). Tamu kantor (Client/Host) hanya tahu mereka berbicara dengan meja Helpdesk. Jika Staf A pingsan mendadak, Staf B langsung duduk di kursi Helpdesk tanpa tamu perlu mengganti nomor telepon atau kartu identitas yang dituju.

---

## 8. Diagram (ASCII)

### A. Inter-VLAN: RoaS vs L3 Switch SVI
```text
           ROUTER-ON-A-STICK (RoaS)                          LAYER 3 SWITCH (SVI)
           
                 +--------+                                    +-----------------------+
                 | Router |                                    |    Layer 3 Switch     |
                 +---+----+                                    | (Hardware ASIC Routing|
                     | Subinterfaces:                          +-----------+-----------+
                     |  - Gi0/0.10 (VLAN 10 GW)                            |
                     |  - Gi0/0.20 (VLAN 20 GW)                +-----------+-----------+
                     | 802.1Q Trunk Link                       | SVI: interface Vlan10 |
                     | (Hairpinning Bottleneck)                | SVI: interface Vlan20 |
                 +---+----+                                    +-----------+-----------+
                 | Switch | (Layer 2 Only)                                 |
                 +---+----+                                    +-----------+-----------+
                     |                                         | Hardware Backplane/ASIC
         +-----------+-----------+                             +-----------+-----------+
         |                       |                                         |
     +---+----+              +---+----+                        +-----------+-----------+
     | VLAN 10|              | VLAN 20|                        | VLAN 10   |   VLAN 20 |
     | Host A |              | Host B |                        | Host A    |   Host B  |
     +--------+              +--------+                        +-----------+-----------+
```

### B. Arsitektur High Availability FHRP (VRRP) dengan WAN Tracking
```text
                           Internet / WAN
                                 |
                     +-----------+-----------+
                     |                       |
                 Uplink-1                Uplink-2
                     |                       |
             +-------+-------+       +-------+-------+
             |   Router-01   |       |   Router-02   |
             |  (VRRP MASTER)|       | (VRRP BACKUP) |
             | Priority: 110 |       | Priority: 100 |
             | Real: .2      |       | Real: .3      |
             +-------+-------+       +-------+-------+
                     | Track Gi0/0           |
                     | (Decrement 20)        |
                     +-----------+-----------+
                                 |
             ====================+====================
                       LAN: 192.168.10.0/24
                       Virtual IP: 192.168.10.1
                    Virtual MAC: 0000.5e00.01.0a
                                 |
                          +------+------+
                          | Client Host |
                          | Gateway: .1 |
                          +-------------+
```

---

## 9. Simple Example
Menambahkan static route standar dan default route pada Cisco IOS-XE:

```bash
# 1. Masuk ke mode konfigurasi global
Router# configure terminal

# 2. Membuat Default Route (Gateway of Last Resort) via next-hop 203.0.113.1
Router(config)# ip route 0.0.0.0 0.0.0.0 203.0.113.1

# 3. Membuat Static Route ke internal microservices subnet melalui interface router internal
Router(config)# ip route 10.200.0.0 255.255.0.0 172.16.1.2

# 4. Verifikasi isi tabel routing
Router(config)# end
Router# show ip route static
```

Output:
```text
Gateway of last resort is 203.0.113.1 to network 0.0.0.0

S*    0.0.0.0/0 [1/0] via 203.0.113.1
S     10.200.0.0/16 [1/0] via 172.16.1.2
```
*Keterangan*: Huruf `S` menandakan Static Route, tanda `*` menandakan candidate default route, dan `[1/0]` menandakan `[Administrative Distance / Metric]`.

---

## 10. Practical Example (Konfigurasi CLI Hands-on)

### Skenario:
Implementasi Enterprise Edge Core dengan 2x Layer 3 Switch (Distribution Switch 01 & 02).
- VLAN 10 (Production Apps): `192.168.10.0/24`, VIP: `192.168.10.1`
- Protokol Redundansi: **VRRPv3**
- Mekanisme Failover: Tracking interface uplink (WAN) menggunakan IP SLA & Enhanced Object Tracking.

#### Konfigurasi Distribution-Switch-01 (Primary Master):
```cisco
! --- 1. Konfigurasi Layer 3 & SVI ---
ip routing

vlan 10
 name Production_App
!
interface Vlan10
 ip address 192.168.10.2 255.255.255.0
 no shutdown
 !
 ! --- 2. Konfigurasi VRRP Group 10 ---
 vrrp 10 address-family ipv4
  address 192.168.10.1 primary
  priority 120
  preempt delay minimum 30
  track 1 decrement 30
 exit-vrrp
!

! --- 3. IP SLA Engine ke Upstream Gateway WAN ---
ip sla 1
 icmp-echo 203.0.113.254 source-interface GigabitEthernet0/0
 frequency 5
 threshold 1000
 timeout 1000
ip sla schedule 1 life forever start-time now

! --- 4. Enhanced Object Tracking ---
track 1 ip sla 1 reachability
 delay down 10 up 15

! --- 5. Uplink Interface & Default Floating Routing ---
interface GigabitEthernet0/0
 description WAN_Primary_Link
 ip address 203.0.113.2 255.255.255.0
 no shutdown
!
! Primary Default Route terikat dengan Track SLA
ip route 0.0.0.0 0.0.0.0 203.0.113.254 track 1
! Floating Static Route via Inter-Switch Link (ISL) jika WAN mati
ip route 0.0.0.0 0.0.0.0 10.255.255.2 200
```

#### Konfigurasi Distribution-Switch-02 (Secondary Backup):
```cisco
ip routing

vlan 10
 name Production_App
!
interface Vlan10
 ip address 192.168.10.3 255.255.255.0
 no shutdown
 !
 ! --- VRRP Group 10 (Backup) ---
 vrrp 10 address-family ipv4
  address 192.168.10.1 primary
  priority 100
  preempt delay minimum 30
 exit-vrrp
!

interface GigabitEthernet0/0
 description WAN_Secondary_Link
 ip address 198.51.100.2 255.255.255.0
 no shutdown
!
! Secondary Default Route ke Provider ISP-2
ip route 0.0.0.0 0.0.0.0 198.51.100.254
```

---

## 11. Real World Example
Pada sebuah platform Financial Technology (Fintech) Payment Gateway, cluster database transactional PostgreSQL on-premises dihubungkan ke sepasang Top-of-Rack (ToR) Cisco Nexus 9000. Setiap server memiliki dua kabel 25Gbps (Active/Standby Linux bonding mode 1) yang masing-masing masuk ke Switch-A dan Switch-B.

**Kasus Nyata**:
Kabel fiber WAN ISP utama pada Switch-A terpotong oleh pekerjaan utilitas kota.
1. Interface physical VLAN lokal Switch-A tetap berstatus `UP/UP` karena kabel server ke switch tidak putus.
2. Jika HSRP/VRRP tidak dikonfigurasi dengan WAN tracking, Switch-A akan **tetap bertindak sebagai FHRP Master**. Paket pembayaran dari ribuan server transaksi akan terus dikirim ke Switch-A, namun Switch-A tidak dapat me-route paket tersebut ke internet (*Blackholing disaster*).
3. **Solusi Lapangan**: IP SLA probe mendeteksi loss ICMP ke edge gateway ISP dalam 3 detik. Track object memicu decrement priority Switch-A dari 120 menjadi 90. Switch-B (priority 100) mendeteksi hello packet dengan priority lebih rendah, langsung mengeksekusi *preemption*, mengirimkan *Gratuitous ARP* untuk IP `192.168.10.1` ke fabric switch. Seluruh trafik dialihkan ke Switch-B dalam waktu < 1 detik tanpa memutus koneksi stateful database clients.

---

## 12. Trade-offs

| Pendekatan / Protokol | Keuntungan | Kerugian / Biaya |
| :--- | :--- | :--- |
| **Router-on-a-Stick (RoaS)** | Hemat biaya perangkat keras; cukup menggunakan satu router murah dan satu manageable L2 switch. | *Throughput bottleneck*; terjadi hairpinning pada trunk link; single point of failure jika router/link down. |
| **L3 Switch (SVI)** | Line-rate packet forwarding via hardware ASIC (TCAM); latensi sub-mikrodetik; tidak membebani inter-switch trunks. | Biaya perangkat (CAPEX) jauh lebih tinggi; keterbatasan fitur routing lanjutan (misal deep MPLS/NAT scale) dibanding dedicated edge router. |
| **Static Routing** | Zero control-plane overhead CPU/RAM; deterministik mutlak; kebal terhadap serangan protokol routing palsu (route injection). | Biaya operasional tinggi (*O(N^2)* administrative complexity); tidak adaptif terhadap topologi dinamis; rawan *routing loops* akibat human-error. |
| **HSRP vs VRRP** | HSRP matang, stabil di ekosistem Cisco; VRRP didukung multi-vendor (Juniper, Arista, Linux Keepalived). | Keduanya bersifat Active/Standby: Bandwidth upstream node standby menganggur (*underutilized link capacity*). |
| **GLBP** | Utilisasi link aktif-aktif simetris (*Per-host load balancing*) secara otomatis tanpa konfigurasi multi-group kompleks. | Cisco proprietary; konsumsi resource ARP yang intensif; kompleksitas troubleshooting tinggi saat menganalisis paket flow asimetris. |

---

## 13. When To Use
- Gunakan **Static Routing**:
  - Pada *Stub Networks* (jaringan cabang yang hanya memiliki satu jalur keluar ke hub).
  - Hubungan peering gateway internet BGP peering (Default static route pointing to ISP next-hop).
  - Sebagai rute out-of-band management interface (IPMI, iDRAC, console server).
- Gunakan **Floating Static Routes**:
  - Sebagai mekanisme failover terakhir (last-resort safety net) jika sesi dynamic routing protocol (OSPF/BGP) runtuh.
- Gunakan **VRRP**:
  - Infrastruktur enterprise multi-vendor (misal: menggabungkan firewall Fortinet/Palo Alto dengan switch Arista/Cisco).
  - High-availability ingress controller pada Bare-Metal Kubernetes (misal: MetalLB atau Keepalived).
- Gunakan **Layer 3 Switch SVI**:
  - Distribusi dan Core jaringan kampus atau Data Center Timur-Barat (East-West traffic) dengan volume transfer > 10Gbps antar-VLAN.

---

## 14. When NOT To Use
- **Jangan gunakan Static Routing**:
  - Jaringan mesh skala medium hingga besar (> 10 router). Perubahan topologi membutuhkan perubahan manual pada seluruh router. Gunakan IGP (OSPF/IS-IS).
  - Jaringan multi-homed ISP BGP routing penuh (Full Internet Routing Table > 900.000 routes).
- **Jangan gunakan Router-on-a-Stick**:
  - Trafik lalu lintas data storage inter-VLAN (iSCSI, NFS), video streaming cluster, atau big data processing (Hadoop/Spark). Gunakan L3 Switch berbasis spine-leaf 40G/100G.
- **Jangan gunakan GLBP**:
  - Jaringan yang menggunakan Stateful Inspection Firewalls di belakang router gateway. GLBP menyebabkan trafik pergi melalui Router A namun balik melalui Router B (*asymmetric routing*), yang akan langsung di-*drop* oleh stateful engine firewall karena TCP sequence mismatch.

---

## 15. Common Mistakes
1. **Mengonfigurasi Static Route Ethernet Menggunakan Exit-Interface Saja**:
   ```cisco
   ! SALAH: Router akan menganggap SEMUA IP host di internet ada di link GigabitEthernet0/0
   ip route 0.0.0.0 0.0.0.0 GigabitEthernet0/0
   ```
   *Dampak*: Router memicu ARP request untuk setiap alamat IP tujuan baru di internet, memenuhi ARP table hingga memory router habis (*memory exhaustion crash*).
   *Solusi*: Selalu cantumkan Next-Hop IP: `ip route 0.0.0.0 0.0.0.0 GigabitEthernet0/0 203.0.113.1`.

2. **Lupa Mengaktifkan Preemption pada Node Primer**:
   Ketika Primary Gateway reboot, status Master diambil alih Secondary. Saat Primary kembali online, tanpa `preempt`, statusnya tetap pasif. Jika Secondary mengalami degradasi performa, trafik tidak akan kembali ke Primary secara otomatis.

3. **Subnet Mask Mismatch pada Interface SVI/FHRP**:
   Router 1 dikonfigurasi `/24` dan Router 2 dikonfigurasi `/25` pada gateway yang sama. Memicu status flapping, duplikasi Virtual IP, dan konflik ARP di switch access.

4. **Salah Menghitung Floating Static AD**:
   Menetapkan AD floating static route di bawah AD protokol routing utama (misal: memasang AD 105 sementara OSPF memiliki AD 110). Akibatnya, rute statis cadangan langsung membunuh rute dinamis OSPF.

---

## 16. Best Practices
1. **Preempt Delay Buffer**:
   Selalu pasang `preempt delay minimum 30` (atau lebih lama) pada node primer FHRP. Ini memastikan protokol dynamic routing internal (OSPF/BGP) telah selesai konvergen (FIB siap seutuhnya) sebelum node tersebut merebut peran Master.
2. **Kombinasikan FHRP dengan Object Tracking**:
   Jangan pernah membiarkan FHRP berjalan tanpa melacak status uplink (WAN/Core link). Kehilangan rute uplink pada Master tanpa decrement priority adalah penyebab utama *traffic blackholing*.
3. **Simetri Pengaturan Timers**:
   Jika mengubah default timer FHRP (misal: VRRP millisecond timers untuk sub-second failover), pastikan seluruh node anggota kelompok memiliki nilai timer yang identik. Perbedaan timer dapat menyebabkan dual-master split-brain.
4. **Hardening Keamanan FHRP**:
   Gunakan otentikasi (MD5/SHA) pada VRRP/HSRP hello packet untuk mencegah serangan host nakal di LAN yang mempromosikan dirinya menjadi FHRP Master (*Man-in-the-Middle Attack*).
5. **Implementasi passive-interface**:
   Pastikan dynamic routing protocol tidak mengirimkan hello advertising ke arah access layer VLAN tempat client dan FHRP berada.

---

## 17. Troubleshooting

### Logika Alur Investigasi Masalah Routing & FHRP:
```text
[Trafik Putus / Gateway Unreachable]
               |
      Periksa Layer 1 & 2
  (Interface UP/UP? VLAN Valid?)
               |
       [CEK ROUTING TABLE]
   (show ip route <destination>)
         /             \
    [No Route]      [Route Exists]
        |                  |
Tambahkan Static    Periksa LPM & Next-Hop
atau Perbaiki IGP          |
                    Ping Next-Hop IP
                     /           \
                 [Sukses]      [Gagal]
                    |              |
              Cek FHRP State   Periksa ARP & L2 CAM Table
             (show vrrp/hsrp)  (show arp / show mac address)
```

### Panduan Perintah Diagnostik:
- **`show ip route`**: Analisis isi RIB keseluruhan.
- **`show ip route <ip-address>`**: Menampilkan rute spesifik yang dipilih router berdasarkan LPM beserta AD dan metric.
  ```text
  Router# show ip route 10.10.15.5
  Routing entry for 10.10.15.0/24
    Known via "ospf 1", distance 110, metric 20, type intra area
    Last update from 172.16.1.1 on GigabitEthernet0/1, 00:04:12 ago
    Routing Descriptor Blocks:
    * 172.16.1.1, from 10.10.15.1, 00:04:12 ago, via GigabitEthernet0/1
  ```
- **`show vrrp brief` / `show standby brief`**: Menampilkan ringkasan status node (Master/Backup, Priority, VIP).
- **`debug vrrp state` / `debug standby events`**: Melacak transisi status FHRP (Init -> Backup -> Master) secara real-time.
- **`traceroute <ip-address> numeric`**: Memvalidasi hop Layer 3 yang dilewati paket tanpa reverse-DNS delay.

---

## 18. Exercise
Selesaikan skenario berikut pada simulator (Packet Tracer / GNS3 / EVE-NG):
1. Bangun topologi dengan 1 buah Layer 3 Switch (Distribution) dan 1 buah Router (Edge).
2. Konfigurasi 2 VLAN pada Switch: VLAN 10 (IP: `172.20.10.0/24`) dan VLAN 20 (IP: `172.20.20.0/24`).
3. Aktifkan routing pada Switch menggunakan SVI sebagai gateway masing-masing VLAN.
4. Buat interface routed transit antara Switch dan Edge Router pada subnet `10.0.0.0/30`.
5. Buat default static route pada L3 Switch yang mengarah ke Edge Router.
6. Buat static summary route pada Edge Router yang mengarah kembali ke L3 Switch untuk kedua subnet VLAN (`172.20.0.0/16`).
7. Uji *ping end-to-end* antar host di VLAN 10 ke loopback interface Edge Router.

---

## 19. Challenge
Rancang arsitektur jaringan *Dual-Homed Data Center Edge* dengan kriteria ketat berikut:
- **High Availability**: Sepasang switch distribution (Dist-01 dan Dist-02) melayani VLAN 100 (`10.100.0.0/23`).
- **Default Gateway Virtual**: Gunakan VRRPv3 dengan Virtual IP `10.100.0.1`.
- **Active-Active Utilization**: Manfaatkan dua VRRP Group:
  - Group 1: Dist-01 sebagai Master (VIP: `10.100.0.1`), melayani Host Pool Ganjil.
  - Group 2: Dist-02 sebagai Master (VIP: `10.100.0.2`), melayani Host Pool Genap.
- **Uplink Failure Protection**:
  - Konfigurasi probe IP SLA ICMP ke ISP gateway masing-masing switch.
  - Jika uplink Dist-01 mengalami *packet loss* > 50% atau latency > 200ms, Group 1 harus otomatis berpindah (failover) ke Dist-02 dalam tempo kurang dari 3 detik.
- **Reversion Guard**: Dist-01 tidak boleh merebut kembali peran Master sebelum koneksi uplink stabil minimal 60 detik.

---

## 20. Summary
- Routing adalah mekanisme deterministic Layer 3 yang mengandalkan **Longest Prefix Match (LPM)** sebagai pemutus mutlak tujuan forwarding paket, diikuti oleh **Administrative Distance (AD)** untuk menentukan prioritas sumber informasi rute, dan **Metric** untuk evaluasi internal protokol.
- **Static Routing** menawarkan efisiensi resource maksimum dan kontrol penuh, namun membutuhkan otomatisasi failover seperti **Floating Static Route** dengan IP SLA tracking untuk mencegah link blackholing.
- **Inter-VLAN Routing** modern mengandalkan **Layer 3 Switch SVI** yang memproses paket via hardware ASIC/TCAM, mengeliminasi bottleneck *hairpinning* yang melekat pada arsitektur legacy *Router-on-a-Stick*.
- **FHRP (HSRP/VRRP/GLBP)** menyediakan virtualisasi gateway transparan bagi host akhir. **VRRP** merupakan standar terbuka de-facto di dunia modern, di mana implementasi produksi wajib menyertakan **preempt delay** dan **uplink tracking** untuk menjamin *zero packet drop* saat terjadi insiden pada jalur upstream.

---