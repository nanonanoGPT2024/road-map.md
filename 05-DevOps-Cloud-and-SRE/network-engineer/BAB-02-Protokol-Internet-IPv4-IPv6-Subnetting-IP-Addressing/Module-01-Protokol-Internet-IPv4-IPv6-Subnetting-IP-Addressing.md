# Modul 01: Protokol Internet (IPv4/IPv6), Subnetting, dan IP Addressing

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Network/Cloud/SRE Engineer diharapkan mampu:
- Mengidentifikasi, mengurai, dan menganalisis setiap field pada IPv4 Header dan IPv6 Header hingga level bit/oktet menggunakan Packet Analyzer (`tcpdump`/`wireshark`).
- Mendesain skema alokasi IP Address skala enterprise berbasis **Classless Inter-Domain Routing (CIDR)** dan **Variable Length Subnet Masking (VLSM)** tanpa pemborosan *address space*.
- Membedakan alokasi Public IP, Private IP (RFC 1918), Carrier-Grade NAT (RFC 6598), dan *Link-Local address*.
- Mengonfigurasi dan memecahkan masalah Network Address Translation (**NAT**), Port Address Translation (**PAT**), Static NAT, Dynamic NAT, dan Source/Destination NAT pada Linux kernel (`iptables`/`nftables`).
- Mengonfigurasi IPv6 addressing, memahami notasi heksadesimal, kompresi nol, subnetting IPv6 (`/64`, `/56`, `/48`), serta mengoperasikan mekanisme autokonfigurasi: **SLAAC** (*Stateless Address Autoconfiguration*) vs **DHCPv6** (Stateful & Stateless).
- Merancang dan mengeksekusi strategi migrasi **Dual-Stack** serta mekanisme transisi (NAT64/DNS64) pada infrastruktur on-premises, Hybrid Cloud, dan containerized network (Kubernetes CNI).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Model OSI (Layer 2 Data Link & Layer 3 Network) dan Model TCP/IP.
- Operasi logika biner: AND, OR, XOR, NOT, shift register, serta konversi bilangan Biner-Desimal-Heksadesimal.
- Operasional dasar Linux CLI: manajemen shell, manipulasi file teks, dan utilitas jaringan dasar (`ping`, `traceroute`, `iproute2` / perintah `ip`).
- Dasar switching: Frame Ethernet, MAC Address, dan Address Resolution Protocol (ARP / NDP).

---

## 3. Concept
Layer 3 (Network Layer) bertanggung jawab untuk *end-to-end host addressing*, *packet encapsulation*, dan *routing* melintasi batasan jaringan heterogen. Inti dari Layer 3 adalah Internet Protocol (IP). 

1. **IPv4 (Internet Protocol version 4)** menggunakan skema pengalamatan 32-bit (total theoretical space: $2^{32} \approx 4.29 \times 10^9$ alamat).
2. **Subnetting (CIDR & VLSM)** adalah teknik segmentasi ruang alamat IP secara matematis ke dalam domain broadcast yang lebih kecil dan efisien untuk mencegah broadcast storm, menghemat alamat, dan menegakkan segmentasi keamanan.
3. **NAT/PAT** meregangkan siklus hidup IPv4 dengan memetakan ribuan IP privat ke satu atau sedikit IP publik menggunakan multiplexing Layer 4 Transport Layer Ports.
4. **IPv6 (Internet Protocol version 6)** menggunakan skema pengalamatan 128-bit (total space: $2^{128} \approx 3.4 \times 10^{38}$ alamat), menghapus kebutuhan akan NAT pada level arsitektur, mendesain ulang format header agar lebih efisien diproses oleh hardware router (Fixed-length header 40 bytes), serta mengintegrasikan keamanan dan autokonfigurasi secara *native*.

---

## 4. Why
Sebagai Site Reliability Engineer (SRE) atau Cloud/Network Architect:
- **Exhaustion of IPv4**: Alokasi IPv4 IANA telah habis. Cloud provider seperti AWS kini membebankan biaya per jam untuk setiap public IPv4 address yang diasosiasikan dengan instance. Efisiensi subnetting dan transisi IPv6 berdampak langsung pada *finops* dan arsitektur biaya.
- **Microservices & Kubernetes Scaling**: Pod IP exhaustion adalah salah satu insiden SRE paling umum di Amazon EKS (`aws-vpc-cni`) atau on-premise Kubernetes clusters. Tanpa pemahaman mendalam tentang VLSM dan secondary CIDR, cluster tidak dapat melakukan auto-scaling node atau pod.
- **Overlapping Subnets**: Dalam skenario M&A (Merger & Acquisition) enterprise atau Multi-Cloud Peering, insiden collision IP RFC 1918 menuntut perancangan re-IPing, Complex NAT (Twice NAT/Overload), atau implementasi Dual-Stack IPv6.
- **Performance & Latency**: Header processing overhead dan fragmentasi paket (MTU mismatch) menyebabkan packet drop, CPU degradation pada core router, dan TCP throughput collapse.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Struktur Header IPv4
Header IPv4 memiliki panjang dinamis (minimum 20 bytes hingga 60 bytes jika menyertakan field Options).

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version|  IHL  |Type of Service|          Total Length         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Identification        |Flags|      Fragment Offset    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Time to Live |    Protocol   |        Header Checksum        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Source Address                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Destination Address                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Options                    |    Padding    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Detail Komponen Header IPv4:
- **Version (4 bits)**: Selalu bernilai `4` (`0100`).
- **Internet Header Length / IHL (4 bits)**: Panjang header dalam unit 32-bit word. Nilai minimum = `5` ($5 \times 4\text{ bytes} = 20\text{ bytes}$). Jika ada opsi, nilainya bisa sampai `15` (60 bytes).
- **Type of Service / ToS / DSCP & ECN (8 bits)**: 
  - 6-bit Differentiated Services Code Point (DSCP) untuk Quality of Service (QoS).
  - 2-bit Explicit Congestion Notification (ECN) untuk memberi sinyal kongesti tanpa menjatuhkan paket (drop).
- **Total Length (16 bits)**: Ukuran total paket (header + payload) dalam bytes. Nilai teoritis maksimum = $2^{16} - 1 = 65.535\text{ bytes}$.
- **Identification (16 bits)**: ID unik untuk mengidentifikasi fragmen dari satu paket IP asli.
- **Flags (3 bits)**:
  - Bit 0: Reserved (harus 0).
  - Bit 1: **DF** (*Don't Fragment*). Jika bernilai 1 dan paket lebih besar dari MTU interface keluar, router membuang paket dan mengirim ICMP Type 3 Code 4 (*Fragmentation Needed*).
  - Bit 2: **MF** (*More Fragments*). Bernilai 1 untuk semua paket hasil fragmentasi kecuali fragmen terakhir.
- **Fragment Offset (13 bits)**: Posisi payload fragmen relatif terhadap paket data asli, dihitung dalam satuan kelipatan 8 bytes (64 bits).
- **Time to Live / TTL (8 bits)**: Counter hop maksimal untuk mencegah paket looping tanpa batas. Nilai dikurangi 1 oleh setiap router (L3 hop). Jika TTL = 0, paket didrop dan dikirimkan ICMP Type 11 Code 0 (*Time to Live Exceeded*).
- **Protocol (8 bits)**: Mengidentifikasi protokol payload Layer 4 (e.g., `1` untuk ICMP, `6` untuk TCP, `17` untuk UDP).
- **Header Checksum (16 bits)**: Verifikasi integritas header IPv4 saja (payload tidak di-checksum di sini). Harus dihitung ulang di setiap hop karena TTL berubah.
- **Source & Destination Address (masing-masing 32 bits)**: IP asal dan IP tujuan.

---

### 5.2 Subnetting: CIDR & VLSM Mathematics
Subnet mask adalah bitmask 32-bit yang membagi IP address menjadi **Network ID** dan **Host ID**.

Operasi Boolean Penentuan Network ID:
$$\text{Network ID} = \text{IP Address} \;\mathbf{AND}\; \text{Subnet Mask}$$

Formula Perhitungan Host dan Subnet:
- Jumlah Subnet baru dari $n$ bit yang dipinjam dari host: $2^n$
- Jumlah Total IP Address per subnet dengan prefix length $/P$: $N_{total} = 2^{32 - P}$
- Jumlah Usable Host Address: $N_{usable} = 2^{32 - P} - 2$ (dikurangi 1 Network ID dan 1 Broadcast Address).
  - *Pengecualian*: RFC 3021 mengizinkan subnet `/31` untuk point-to-point links (2 host, 0 broadcast, keduanya usable). Subnet `/32` digunakan untuk loopback atau host route (1 host address).

#### Variable Length Subnet Masking (VLSM)
VLSM adalah alokasi subnet mask dinamis sesuai kebutuhan spesifik setiap segmen jaringan, menghindari pemborosan Classless default.

Contoh Algoritma Alokasi VLSM:
Diberikan blok jaringan `10.100.0.0/22` (Total: $2^{(32-22)} = 1024$ IP).
Kebutuhan:
1. VPC Production: 400 hosts
2. VPC Staging: 200 hosts
3. VPC Management: 50 hosts
4. Inter-DC Point-to-Point Link: 2 hosts

Urutkan alokasi dari kebutuhan TERBESAR ke TERKECIL:
1. **Prod (400 hosts)**: Butuh IP $\ge 400 + 2 = 402$. $2^9 = 512$. Dibutuhkan prefix $32 - 9 = \mathbf{/23}$.
   - Subnet: `10.100.0.0/23`
   - Range: `10.100.0.0` s/d `10.100.1.255`
   - Network: `10.100.0.0`, Broadcast: `10.100.1.255`
   - Usable: `10.100.0.1` - `10.100.1.254` (510 hosts).
2. **Staging (200 hosts)**: Butuh IP $\ge 202$. $2^8 = 256$. Dibutuhkan prefix $32 - 8 = \mathbf{/24}$.
   - Subnet: Blok berikutnya `10.100.2.0/24`
   - Range: `10.100.2.0` s/d `10.100.2.255`
   - Usable: `10.100.2.1` - `10.100.2.254` (254 hosts).
3. **Management (50 hosts)**: Butuh IP $\ge 52$. $2^6 = 64$. Dibutuhkan prefix $32 - 6 = \mathbf{/26}$.
   - Subnet: Blok berikutnya `10.100.3.0/26`
   - Range: `10.100.3.0` s/d `10.100.3.63`
   - Usable: `10.100.3.1` - `10.100.3.62` (62 hosts).
4. **Point-to-Point (2 hosts)**: RFC 3021 `/31` ($2^1 = 2$ IP, usable keduanya) atau `/30` ($2^2 = 4$ IP). Jika menggunakan standard `/30`:
   - Subnet: Blok berikutnya `10.100.3.64/30`
   - Range: `10.100.3.64` s/d `10.100.3.67`
   - Usable: `10.100.3.65` - `10.100.3.66` (2 hosts).
- **Sisa Alokasi Kosong**: `10.100.3.68` s/d `10.100.3.255` (dapat digunakan ekspansi di masa mendatang).

---

### 5.3 Public, Private, dan CGNAT IP Address Spaces

| Kategori | Standar RFC | Range Alokasi | Keterangan Arsitektural |
|---|---|---|---|
| **Class A Private** | RFC 1918 | `10.0.0.0/8` (`10.0.0.0` - `10.255.255.255`) | Skala enterprise, Multi-AZ VPC, On-Premises Core |
| **Class B Private** | RFC 1918 | `172.16.0.0/12` (`172.16.0.0` - `172.31.255.255`) | Default Docker networks, Medium-scale VPCs |
| **Class C Private** | RFC 1918 | `192.168.0.0/16` (`192.168.0.0` - `192.168.255.255`)| Local office LAN, Edge networks, Home router |
| **Carrier-Grade NAT**| RFC 6598 | `100.64.0.0/10` (`100.64.0.0` - `100.127.255.255`)| ISP Shared Address Space, Kubernetes Pod CIDR (AWS CNI) |
| **Link-Local** | RFC 3927 | `169.254.0.0/16` (`169.254.0.0` - `169.254.255.255`)| APIPA (No DHCP response), Cloud Instance Metadata Service (IMDS) |
| **Loopback** | RFC 1122 | `127.0.0.0/8` | Localhost internal communication |
| **Public IP** | IANA Global | Sisanya (di luar Multicast `224.0.0.0/4`, Experimental `240.0.0.0/4`) | Globally routable across public internet |

---

### 5.4 Network Address Translation (NAT) & Port Address Translation (PAT)
NAT mengubah field Layer 3 IP Address (dan Layer 4 Port untuk PAT) saat paket melintasi router boundary. State pemetaan disimpan pada memory kernel (**conntrack table**).

1. **SNAT (Source NAT)**:
   - Mengubah source IP paket internal menjadi IP publik interface gateway sebelum keluar ke internet.
   - Digunakan saat host internal memprakarsai koneksi ke external service.
2. **PAT / NAT Overload (Masquerade)**:
   - Subkategori dari SNAT di mana ribuan private IP berbagi satu Public IP menggunakan dynamic Layer 4 Ephemeral Ports (Port 1024 - 65535).
   - Formulasi Connection State Tuple: `(Proto, Private_IP, Private_Port, Dest_IP, Dest_Port) <--> (Proto, Public_NAT_IP, NAT_Port, Dest_IP, Dest_Port)`
3. **DNAT (Destination NAT / Port Forwarding)**:
   - Mengubah destination IP (dan optional port) paket yang datang dari luar ke IP privat host internal.
   - Digunakan untuk expose web server di DMZ internal ke internet publik.
4. **Conntrack Exhaustion**:
   - Jika sistem menjalankan terlalu banyak concurrent connection melampaui `nf_conntrack_max`, kernel menolak state baru dan menjatuhkan paket (`table full, dropping packet`).

---

### 5.5 Struktur Header IPv6 & Hexadecimal Addressing
IPv6 didesain ulang untuk meminimalkan beban komputasi router. Header berukuran tetap (**Fixed 40 Bytes**). Header Options dipindahkan ke dalam rantai **Extension Headers**.

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version| Traffic Class |           Flow Label                  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Payload Length        |  Next Header  |   Hop Limit   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                                                               +
|                                                               |
+                         Source Address                        +
|                           (128 bits)                          |
+                                                               +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                                                               +
|                                                               |
+                      Destination Address                      +
|                           (128 bits)                          |
+                                                               +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Perbedaan Krusial dengan IPv4:
- **No Header Checksum**: Checksum dihapus karena Layer 2 (Ethernet CRC) dan Layer 4 (TCP/UDP checksum) sudah memvalidasi integritas data. Performa router melonjak drastis.
- **Fixed Size (40 Bytes)**: Router memproses header pada fixed hardware pipeline tanpa perlu parsing variabel IHL.
- **Flow Label (20 bits)**: Memungkinkan hardware forwarding engine menandai packet stream yang sama untuk load balancing (ECMP) tanpa perlu membuka payload Layer 4 (Deep Packet Inspection).
- **Next Header (8 bits)**: Menggantikan field `Protocol` IPv4. Menunjuk ke protokol Layer 4 langsung (TCP: 6, UDP: 17) ATAU Extension Header berikutnya (misal: Hop-by-Hop Options, Routing, Fragment, ESP/AH Security).
- **Hop Limit (8 bits)**: Identik secara fungsional dengan TTL pada IPv4.

#### Notasi Heksadesimal & Aturan Kompresi (RFC 5952)
Alamat IPv6 terdiri dari 128 bit yang dibagi menjadi 8 grup (hextet) masing-masing 16 bit, dipisahkan oleh tanda titik dua (`:`).
Contoh: `2001:0db8:0000:0000:0000:ff00:0042:8329`

Aturan Kompresi Wajib:
1. **Omit Leading Zeros**: Nol di depan setiap hextet harus dihilangkan.
   `2001:db8:0:0:0:ff00:42:8329`
2. **Double Colon (`::`)**: Runtutan hextet bernilai nol yang bersebelahan dapat diganti dengan `::` hanya satu kali dalam satu alamat.
   `2001:db8::ff00:42:8329`

Skema Tipe Alamat IPv6:
- **Global Unicast Address (GUA)**: `2000::/3` (Globally routable di internet).
- **Unique Local Address (ULA)**: `fc00::/7` (Identik dengan RFC 1918 Private IP). Dibagi menjadi `fd00::/8` untuk alokasi lokal yang digenerasi secara pseudorandom.
- **Link-Local Address (LLA)**: `fe80::/10` (Hanya valid pada physical link layer yang sama, tidak di-forward router).
- **Multicast**: `ff00::/8` (Tidak ada broadcast di IPv6, semua broadcast digantikan oleh multicast, misal: `ff02::1` untuk all-nodes, `ff02::2` untuk all-routers).
- **Loopback**: `::1/128`.
- **Unspecified**: `::/128`.

---

### 5.6 SLAAC vs DHCPv6
IPv6 tidak mengandalkan ARP. IPv6 menggunakan **Neighbor Discovery Protocol (NDP)** yang beroperasi via ICMPv6.

#### 1. SLAAC (Stateless Address Autoconfiguration - RFC 4862)
- Host mengirim **ICMPv6 Router Solicitation (RS - Type 133)** ke multicast `ff02::2` (All-Routers).
- Router merespons dengan **ICMPv6 Router Advertisement (RA - Type 134)** ke `ff02::1` (All-Nodes).
- RA berisi Prefix jaringan (`/64`), Default Gateway, MTU, dan Flag konfig:
  - **A-Flag (Autonomous)**: Jika `1`, host membuat Interface Identifier (IID) 64-bit sendiri (via EUI-64 atau RFC 7217 Stable Privacy) dan menggabungkannya dengan prefix jaringan.
  - **M-Flag (Managed Address Configuration)**: Jika `1`, host WAJIB menggunakan Stateful DHCPv6 untuk mendapatkan IP.
  - **O-Flag (Other Configuration)**: Jika `1`, host menggunakan SLAAC untuk IP, tetapi meminta opsi tambahan (seperti Recursive DNS Server/RDNSS atau NTP) ke Stateless DHCPv6 server.
- Host menjalankan **Duplicate Address Detection (DAD)** via Neighbor Solicitation (NS) sebelum menetapkan IP tersebut.

#### 2. Stateful vs Stateless DHCPv6
- **Stateful DHCPv6**: Server mengontrol penuh alokasi address, mencatat lease state di database (seperti DHCP IPv4). Membutuhkan DORA-like sequence via UDP port 546/547 (`Solicit`, `Advertise`, `Request`, `Reply`).
- **Stateless DHCPv6**: Server tidak mengelola IP address (IP dibuat via SLAAC). Server hanya membagikan parameter DNS, NTP, domain search list.

---

### 5.7 Dual-Stack Architecture & Migration Transition
Migrasi IPv4 ke IPv6 tidak terjadi dalam semalam. Tiga mekanisme transisi utama:
1. **Dual-Stack (Recommended Standard)**: Interface router, server, dan container berjalan dengan IPv4 dan IPv6 stack secara simultan. OS memilih IPv6 secara preferensial jika DNS record `AAAA` tersedia (RFC 6724 - *Happy Eyeballs* algorithm).
2. **NAT64 / DNS64**:
   - Host murni IPv6 ingin mengakses server yang hanya memiliki IPv4.
   - **DNS64** mensintesis record IPv6 palsu (Prefix `64:ff9b::/96` + IPv4 hex) saat host meminta DNS AAAA tapi authoritative server hanya memiliki A record.
   - Gateway **NAT64** mengekstrak IPv4 asli dari synthetic prefix lalu mentranslasikannya ke target IPv4 menggunakan Stateful NAT.
3. **Tunneling (6in4, GRE, WireGuard)**: Membungkus paket IPv6 di dalam payload IPv4 untuk melintasi transit network yang belum mendukung native IPv6.

---

## 6. How

### 6.1 Menerapkan Desain Subnetting CIDR di Linux
Menambahkan secondary IP dan custom route pada antarmuka Linux via `iproute2`:

```bash
# Tambahkan alamat IPv4 dengan CIDR /26
sudo ip addr add 10.100.3.1/26 dev eth0

# Tambahkan alamat IPv6 Global Unicast (/64)
sudo ip -6 addr add 2001:db8:acad:1::1/64 dev eth0

# Verifikasi konfigurasi
ip -4 addr show dev eth0
ip -6 addr show dev eth0
```

### 6.2 Konfigurasi Stateful NAT/PAT Menggunakan `iptables` & `nftables`

#### Menggunakan Modern `nftables` (Recommended):
```bash
# 1. Aktifkan IP Forwarding pada kernel
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.ipv6.conf.all.forwarding=1

# 2. Buat table NAT pada nftables
sudo nft add table ip nat

# 3. Buat chain postrouting dan prerouting
sudo nft add chain ip nat prerouting { type nat hook prerouting priority -100 \; }
sudo nft add chain ip nat postrouting { type nat hook postrouting priority 100 \; }

# 4. Tambahkan aturan SNAT (Masquerade pada WAN eth0)
sudo nft add rule ip nat postrouting oifname "eth0" masquerade

# 5. Tambahkan aturan DNAT (Port forwarding port 80/tcp publik ke internal IP 10.100.3.50:8080)
sudo nft add rule ip nat prerouting iifname "eth0" tcp dport 80 dnat to 10.100.3.50:8080
```

---

## 7. Analogy
Bayangkan sistem pengiriman logistik internasional:
- **IPv4 Address**: Nomor telepon 7 digit era 1980-an di suatu kota. Awalnya cukup, namun ketika populasi meledak, kapasitas nomor habis.
- **NAT / PAT**: Seperti operator sentral kantor besar (PABX). Kantor hanya memiliki 1 nomor telepon publik (Public IP). Setiap pegawai memiliki nomor ekstensi internal (Private IP). Jika pegawai menelepon ke luar, sistem mencatat saluran keluar mana yang digunakan (NAT Table). Jika ada telepon masuk ke nomor utama dengan nomor ekstensi tertentu, operator meneruskannya ke meja yang tepat (DNAT).
- **Subnetting (VLSM)**: Memotong satu gedung perkantoran besar (Blok Jaringan) menjadi beberapa lantai, sekat ruangan, dan bilik kerja sesuai jumlah tim secara presisi, sehingga tidak ada ruang kosong yang mubazir sementara tim lain berdesakan.
- **IPv6 Address**: Sistem pengalamatan GPS presisi tinggi yang mampu memberikan koordinat spesifik hingga ke setiap butir pasir di muka bumi. Setiap perangkat di bumi memiliki alamat publik uniknya sendiri tanpa perlu perantara PABX/NAT.

---

## 8. Diagram (ASCII)

### 8.1 Alur Transaksi NAT/PAT (Stateful Connection Tracking)
```
[ Host Internal ]                                  [ Linux NAT Gateway ]                             [ External Server ]
IP: 10.100.1.50                                      Public IP: 203.0.113.5                             IP: 198.51.100.2
Private Port: 54321                                  Outbound Port: 40001                               Listening Port: 443
        |                                                     |                                                  |
        |--- 1. PKT: SRC=10.100.1.50:54321 ------------------>|                                                  |
        |       DST=198.51.100.2:443                          |                                                  |
        |                                             [ CONNTRACK INSERT ]                                       |
        |                                      (10.100.1.50:54321 <-> 203.0.113.5:40001)                         |
        |                                                     |                                                  |
        |                                                     |--- 2. RE-WRITTEN PKT: SRC=203.0.113.5:40001 ---->|
        |                                                     |       DST=198.51.100.2:443                       |
        |                                                     |                                                  |
        |                                                     |<-- 3. INBOUND RESP: SRC=198.51.100.2:443 --------|
        |                                                     |       DST=203.0.113.5:40001                      |
        |                                             [ CONNTRACK LOOKUP ]                                       |
        |                                      Match: 203.0.113.5:40001 -> 10.100.1.50:54321                    |
        |<-- 4. TRANSLATED PKT: SRC=198.51.100.2:443 --------|                                                  |
        |       DST=10.100.1.50:54321                         |                                                  |
```

### 8.2 Dekonstruksi Hirarki Alamat IPv6
```
 2001 : 0db8 : acad : 0001 : 0250 : 56ff : fe89 : abcd /64
|                          |      |                         |
+-------------+------------+------+------------+------------+
              |                   |            |
   Global Routing Prefix      Subnet ID    Interface ID (Host)
        (48 bits)             (16 bits)        (64 bits)
|<------- Network Prefix (64 bits) ------->|<-- Host ID (64 bits) ->|
```

---

## 9. Simple Example
Diberikan IP `192.168.10.130/27`.
1. Konversi Mask `/27` ke Biner:
   `11111111.11111111.11111111.11100000` = `255.255.255.224`
2. Konversi Oktet Terakhir IP (130) ke Biner:
   $130 = 128 + 2 = \mathbf{10000010}_2$
3. Bitwise AND dengan Mask Oktet Terakhir (224):
   ```
     10000010  (130)
     11100000  (224)
     --------  AND
     10000000  (128)
   ```
4. **Network Address**: `192.168.10.128`
5. Host bits = $32 - 27 = 5$ bit. Total host per subnet = $2^5 = 32$.
6. **Broadcast Address**: Network Address + 31 = `192.168.10.159`.
7. **Usable IP Range**: `192.168.10.129` - `192.168.10.158` (Total: 30 host usable).

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Hands-on)

### 10.1 Otomasi Desain AWS Dual-Stack VPC Menggunakan HashiCorp Terraform
File: `vpc_dualstack.tf`

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

# 1. Alokasi VPC dengan IPv4 CIDR dan Amazon-provided IPv6 CIDR (/56)
resource "aws_vpc" "production_vpc" {
  cidr_block                       = "10.50.0.0/16"
  assign_generated_ipv6_cidr_block = true
  enable_dns_hostnames             = true
  enable_dns_support               = true

  tags = {
    Name        = "prod-dualstack-vpc"
    Environment = "production"
  }
}

# 2. Public Subnet (IPv4 /24 + IPv6 /64)
resource "aws_subnet" "public_subnet_az1" {
  vpc_id                          = aws_vpc.production_vpc.id
  cidr_block                      = "10.50.1.0/24"
  ipv6_cidr_block                 = cidrsubnet(aws_vpc.production_vpc.ipv6_cidr_block, 8, 1) # Menghasilkan /64
  map_public_ip_on_launch         = true
  assign_ipv6_address_on_creation = true
  availability_zone               = "ap-southeast-1a"

  tags = {
    Name = "prod-public-subnet-1a"
  }
}

# 3. Internet Gateway untuk Inbound/Outbound IPv4 & IPv6
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.production_vpc.id

  tags = {
    Name = "prod-main-igw"
  }
}

# 4. Route Table Public (Dual-Stack Default Routes)
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.production_vpc.id

  # Default Route IPv4
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  # Default Route IPv6 (All-traffic out via IGW)
  route {
    ipv6_cidr_block = "::/0"
    gateway_id      = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "prod-public-rt"
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public_subnet_az1.id
  route_table_id = aws_route_table.public_rt.id
}
```

---

## 11. Real World Example
**Studi Kasus**: FinTech Payment Gateway berskala jutaan Request Per Second (RPS) mengalami kegagalan transmisi ke third-party payment partner saat peak event Flash Sale.

**Indikasi Masalah**:
- Host internal di Kubernetes Cluster melontarkan error: `connect: cannot assign requested address` atau `connection timed out`.
- Tidak ada response dari target upstream server.

**Root-Cause Analysis (RCA)**:
1. SRE memeriksa metrik NAT Gateway / Conntrack table pada edge router Linux:
   ```bash
   sudo sysctl net.netfilter.nf_conntrack_count
   # Output: 262144
   sudo sysctl net.netfilter.nf_conntrack_max
   # Output: 262144
   ```
   Conntrack table penuh (`table full, dropping packet` terlihat di `dmesg`).
2. SRE mengamati utilisasi port SNAT: Ribuan pod mikroservis melakukan HTTP/1.1 polling (tanpa Keep-Alive connection pooling) ke IP publik vendor yang sama pada port `443`.
3. Kombinasi 5-tuple: `(TCP, NAT_Public_IP, NAT_Port, Vendor_IP, 443)` kehabisan source ephemeral ports (hanya tersedia $\approx 64.000$ ports per target IP). Ini dikenal sebagai **SNAT Port Exhaustion**.

**Solusi Arsitektur**:
1. Implementasi HTTP Connection Pooling (Keep-Alive) pada sisi aplikasi microservices.
2. Penambahan secondary public IP address pada NAT Gateway pool untuk memperluas kapasitas port ($N \times 64.000$).
3. Akselerasi migrasi endpoint integrasi ke **IPv6 Native Peering**. Karena partner dan cloud provider mendukung IPv6, komunikasi langsung point-to-point tanpa NAT, secara permanen meniadakan limitasi state table conntrack.

---

## 12. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Risiko |
|---|---|---|
| **IPv4 Subnetting Agresif (Micro-subnetting /29, /30)** | Konservasi IP address yang sangat ketat; alokasi hemat. | Fragmentasi routing table; jika beban membesar, subnet kehabisan host dan re-IPing sangat mahal secara operasional. |
| **Carrier-Grade NAT (CGNAT) / Large Scale PAT** | Menghemat ribuan public IP address; hanya butuh satu IP publik untuk satu klaster. | Titik kegagalan tunggal (Single Point of Failure); conntrack memory overhead; menghancurkan transparansi audit log (IP logging kehilangan konteks tanpa pencatatan source port log). |
| **Pure IPv6 Implementation** | Tidak ada NAT; header processing cepat; ruang alokasi tak terbatas; native auto-configuration. | Legacy equipment & third-party SaaS vendors banyak yang belum siap; inspeksi keamanan & filtering tool lama sering kali bypass IPv6 (blind-spot). |
| **Dual-Stack Topology** | Kompatibilitas 100% dengan ekosistem lama dan baru; transisi bertahap tanpa downtime. | Kompleksitas operasional ganda: wajib maintain dua firewall ruleset, dua routing table, dua monitoring pipeline. |

---

## 13. When To Use
- Gunakan **Subnetting VLSM** saat merancang fondasi Data Center fisik, Cloud Virtual Private Cloud (VPC), dan alokasi container overlay network.
- Gunakan **RFC 6598 (`100.64.0.0/10`)** ketika ruang RFC 1918 internal mengalami tabrakan (*overlap*) akibat merger perusahaan atau alokasi IP Pod Kubernetes berskala raksasa.
- Gunakan **SLAAC** untuk segmen end-user devices, workstation kantor, IoT, dan instance cloud yang hanya memerlukan konektivitas internet standar tanpa audit jejak IP terpusat.
- Gunakan **Dual-Stack** sebagai standar baseline arsitektur edge gateway, load balancer publik, dan API ingress untuk melayani klien modern dan legacy.

---

## 14. When NOT To Use
- **JANGAN** gunakan alokasi subnet yang lebih besar dari `/64` untuk end-node subnet pada IPv6 (misal: `/80` atau `/112`). Arsitektur standar IPv6 merusak SLAAC dan Neighbor Discovery jika prefix bukan `/64`.
- **JANGAN** gunakan NAT sebagai mekanisme security/firewall utama. NAT adalah *routing and address translation mechanism*, bukan security control. Keamanan harus ditegakkan dengan Layer 3/4/7 Stateful Firewall rules.
- **JANGAN** gunakan Stateful DHCPv6 jika environment Anda memerlukan performa auto-discovery cepat pada ribuan microservice ephemeral, gunakan static IP assignment atau SLAAC/cloud-init.

---

## 15. Common Mistakes
1. **Off-by-One Calculation pada Usable IP**: Mengabaikan pengurangan 2 alamat (Network ID dan Broadcast ID) dalam IPv4, atau lupa bahwa AWS memotong 5 alamat pertama pada setiap subnet VPC (Network, VPC Router, DNS, Future Reserve, Broadcast).
2. **Kekeliruan Nilai Wildcard Mask vs Subnet Mask**: Menuliskan subnet mask terbalik pada firewall access-lists (`0.0.0.255` alih-alih `255.255.255.0`).
3. **Mengabaikan Path MTU Discovery (PMTUD) pada IPv6**: Karena IPv6 router tidak melakukan fragmentasi paket (fragmentasi HANYA dilakukan oleh source host), memblokir ICMPv6 Packet Too Big (Type 2) secara agresif di firewall menyebabkan *Black Hole Routing* (koneksi TCP macet saat transfer data besar/TLS handshake).
4. **Salah Menghitung Batas Oktet pada VLSM**: Mengabaikan batas perpangkatan 2 sehingga subnet melintasi boundary network lain (*overlapping subnets*).

---

## 16. Best Practices
1. **Standar Desain IPv6 /64**: Selalu alokasikan subnet `/64` per broadcast domain/VLAN/Subnet dalam IPv6 tanpa kecuali.
2. **Hierarki Alokasi Alamat**: Terapkan hierarki *Summarizable Addressing* (misal: semua workload Asia Tenggara di bawah `10.10.0.0/16`, Non-Prod di `10.10.0.0/18`, Prod di `10.10.64.0/18`) untuk meminimalisir entri routing table via route aggregation.
3. **Conntrack Tuning**: Pada server Linux NAT Gateway throughput tinggi, tingkatkan nilai `nf_conntrack_max` dan turunkan `nf_conntrack_tcp_timeout_established`:
   ```bash
   sudo sysctl -w net.netfilter.nf_conntrack_max=1048576
   sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=600
   ```
4. **Log Source Port pada Proxy/NAT**: Wajibkan pencatatan *Source Port* di reverse proxy / NAT gateway logs untuk keperluan investigasi forensik kejahatan siber (Incident Response).

---

## 17. Troubleshooting

### Playbook: Debugging NAT Packet Drop & Subnet Reachability

#### Gejala: Host internal `10.100.1.20` tidak dapat mengakses internet publik via Linux NAT Gateway.

**Langkah 1: Verifikasi Layer 3 Routing Lokal Host**
```bash
# Periksa Default Gateway
ip route show
# Output harus memiliki: default via 10.100.1.1 dev eth0
```

**Langkah 2: Verifikasi IP Forwarding pada Gateway**
Masuk ke Linux NAT Gateway:
```bash
sysctl net.ipv4.ip_forward
# Jika nilainya 0, aktifkan segera:
sudo sysctl -w net.ipv4.ip_forward=1
```

**Langkah 3: Trace Aliran Paket dengan `tcpdump`**
Buka dua terminal pada NAT Gateway:
```bash
# Terminal A (Interface Internal / LAN):
sudo tcpdump -nni eth1 icmp

# Terminal B (Interface External / WAN):
sudo tcpdump -nni eth0 icmp
```
Kirim ping dari Host Internal: `ping 8.8.8.8`
- Jika paket terlihat di `eth1` tetapi tidak di `eth0`, masalah berada pada **iptables/nftables FORWARD chain drop** atau **aturan SNAT/Masquerade hilang**.
- Jika paket terlihat di `eth0` dengan Source IP masih `10.100.1.20` (bukan Public IP Gateway), maka **aturan NAT gagal match**.

**Langkah 4: Inspeksi Table & Rules NAT**
```bash
# Cek hit counter pada nftables
sudo nft list table ip nat -a

# Atau jika masih menggunakan legacy iptables:
sudo iptables -t nat -L -n -v
```
Pastikan counter paket pada rule MASQUERADE/SNAT bertambah.

---

## 18. Exercise
1. **Latihan Subnetting Dasar**:
   Diberikan blok IP `172.20.0.0/19`.
   - Berapa total IP address yang tersedia?
   - Berapa subnet mask dalam format desimal bertitik (*dotted decimal*)?
   - Jika kita membaginya menjadi subnet-subnet berukuran `/23`, berapa banyak subnet baru yang tercipta?
2. **Latihan Analisis Header**:
   Sebuah sniffer menangkap heksadesimal 4 byte pertama dari paket IP: `45 00 00 3c`.
   - Tentukan nilai Version, IHL, Total Length paket tersebut!
   - Apakah header tersebut memiliki field Options? Jelaskan buktinya dari nilai IHL!
3. **Latihan Dekomposisi IPv6**:
   Lakukan ekspansi penuh (tuliskan 32 digit hex tanpa kompresi) dari alamat:
   `2001:db8:0:1::a`

---

## 19. Challenge
**Scenario**: Anda ditugaskan merancang ulang skema pengalamatan IP sebuah tech unicorn yang baru saja mengakuisisi perusahaan logistik.
- Jaringan Eksisting Unicorn: `10.0.0.0/12` (sudah terpakai padat).
- Jaringan Perusahaan Logistik: `10.8.0.0/13` (overlap langsung dengan alokasi Unicorn).
- Kebutuhan: Hubungkan kedua VPC antar-perusahaan via AWS Direct Connect / Cloud Interconnect tanpa melakukan re-IPing massal pada ribuan container logistik dalam jangka pendek, sembari menyiapkan arsitektur *Zero-Collision Dual-Stack* jangka panjang.

**Tugas Anda**: Buat proposal arsitektur 1 halaman yang merinci implementasi **Twice NAT (Bidirectional NAT)** sementara, alokasi blok **RFC 6598 CGNAT** sebagai transfer network, serta roadmap migrasi penuh ke **IPv6-Only overlay** dengan encapsulation/SLAAC.

---

## 20. Summary
- Header IPv4 berukuran fleksibel (20-60 bytes), sarat overhead komputasi checksum per hop, dan mengalami fragmentasi dinamis di level router.
- Subnetting CIDR dan VLSM adalah disiplin matematika vital dalam meminimalisir pemborosan ruang alamat IPv4 32-bit.
- NAT/PAT memfasilitasi multiplexing koneksi privat ke publik melalui pelacakan conntrack stateful Layer 4, namun memperkenalkan batas konkurensi (SNAT Exhaustion) dan kompleksitas audit.
- IPv6 menyederhanakan header ke ukuran tetap (40 bytes), memperluas ruang alamat ke 128 bit, menggantikan broadcast dengan multicast, menghapus kebutuhan NAT, serta mengadopsi SLAAC/DHCPv6 terstandarisasi.
- Dual-Stack tetap menjadi standar de facto strategi transisi modern, memastikan interoperabilitas penuh antara sistem lama dan arsitektur cloud masa depan.