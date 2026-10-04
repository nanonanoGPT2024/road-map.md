# BAB 02: Protokol Internet (IPv4 & IPv6), Subnetting, dan IP Addressing
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis struktur internal header IPv4 dan IPv6 hingga tingkat bit/oktet, termasuk implikasi performa dari *hop-by-hop extension headers* dan fragmentasi paket.
- Menguasai kalkulasi biner, Variable Length Subnet Masking (VLSM), Classless Inter-Domain Routing (CIDR), serta optimasi agregasi rute (*supernetting*) untuk efisiensi tabel routing kernel.
- Mengimplementasikan dan mengonfigurasi skema pengalamatan *dual-stack* (IPv4/IPv6), transisi stateful/stateless (NAT64/DNS64, SLAAC, DHCPv6) pada infrastruktur bare-metal, Linux Server, dan containerized network (Kubernetes CNI).
- Mendiagnosis dan menyelesaikan anomali jaringan tingkat lanjut seperti Path MTU Discovery (PMTUD) black holes, ekskavasi *asymmetric routing*, overlapping IP subnets, dan NDP/ARP cache table starvation.
- Mendesain arsitektur IP Addressing skala enterprise yang mendukung multi-region datacenter, zero-trust overlay network, dan kepatuhan standar RFC 1918, RFC 6598 (CGNAT), serta RFC 4291/7381.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada domain berikut:
- **Model OSI & TCP/IP Layering:** Khususnya Layer 2 (Data Link: Ethernet Framing, MAC Address) dan Layer 3 (Network).
- **Sistem Operasi Linux Lanjutan:** Familiaritas dengan Linux Network Namespace (`ip netns`), konfigurasi `sysctl` untuk networking stack, serta utilitas `iproute2` (`ip addr`, `ip route`, `ip link`).
- **Sistem Bilangan Biner & Heksadesimal:** Konversi cepat antara basis-2, basis-10, dan basis-16.
- **Konsep Routing Dasar:** Next-hop forwarding, static routing, dan fungsi dasar Gateway.

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi Header IPv4 vs IPv6
Protokol Internet (IP) bertanggung jawab atas transmisi data *connectionless* dan *best-effort* lintas batas jaringan heterogen. Perbedaan mendasar antara IPv4 (RFC 791) dan IPv6 (RFC 8200) terletak pada kompleksitas pemrosesan header pada router/forwarding plane.

```
IPv4 Header Structure:
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version|  IHL  |Type of Service|          Total Length         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Identification        |Flags|      Fragment Offset    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Time to Live |    Protocol   |         Header Checksum       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Source Address                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Destination Address                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Options                    |    Padding    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

IPv6 Base Header Structure (Fixed 40 Bytes):
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

##### Analisis Perbedaan Struktural Kritis:
1. **Ukuran Header:** IPv4 memiliki ukuran dinamis 20–60 byte (tergantung *Options* dan *IHL* / *Internet Header Length*). IPv6 memiliki ukuran tetap 40 byte, yang memungkinkan optimasi pipeline pemrosesan berbasis hardware (ASIC/NPUs) secara konstan tanpa perlu kalkulasi offset field.
2. **Eliminasi Checksum pada IPv6:** IPv4 mewajibkan kalkulasi ulang *Header Checksum* pada setiap hop karena nilai TTL (*Time to Live*) berkurang. IPv6 meniadakan *Header Checksum* untuk mengeliminasi latensi CPU pada layer router; keandalan integritas data didelegasikan sepenuhnya ke Layer 2 (CRC) dan Layer 4 (UDP/TCP checksum).
3. **Fragmentasi:** Pada IPv4, router perantara dapat melakukan fragmentasi paket jika ukuran paket melebihi MTU (*Maximum Transmission Unit*) dari link keluar. Pada IPv6, **router tidak pernah memecah paket**. Fragmentasi hanya dilakukan oleh *Source Host* menggunakan *IPv6 Fragment Extension Header*. Jika router menerima paket IPv6 yang lebih besar dari egress MTU, router akan menjatuhkan (*drop*) paket tersebut dan mengirimkan ICMPv6 *Packet Too Big* (Type 2, Code 0) kembali ke source.
4. **Flow Label:** IPv6 memperkenalkan 20-bit *Flow Label* yang memungkinkan layer switching/routing mengenali aliran paket (*flow*) tanpa harus mengevaluasi L4 TCP/UDP port numbers, mempermudah konfigurasi ECMP (*Equal-Cost Multi-Path*) dan QoS.

#### 3.2 Dynamic IP Allocation: SLAAC, DHCPv6, dan DAD
Pada IPv6, resolusi dan penetapan IP dilakukan secara otomatis melalui ICMPv6:
- **Neighbor Discovery Protocol (NDP):** Menggantikan ARP IPv4. Menggunakan *ICMPv6 Type 135 (Neighbor Solicitation)* dan *Type 136 (Neighbor Advertisement)* berbasis multicast (`ff02::1:ff00:0/104` - Solicited-Node Multicast Address).
- **Stateless Address Autoconfiguration (SLAAC):** Host mengirimkan *Router Solicitation* (RS - Type 133). Router merespons dengan *Router Advertisement* (RA - Type 134) membawa prefix `/64`. Host menghasilkan Interface Identifier (IID) via EUI-64 (berbasis MAC address) atau RFC 7217 (opaque/privacy extension).
- **Duplicate Address Detection (DAD):** Proses wajib sebelum IP digunakan. Host mengirim NS untuk calon alamat IP-nya sendiri. Jika ada NA yang menjawab, terjadi konflik IP dan antarmuka akan ditandai *tentative/failed*.

#### 3.3 Linux Kernel Routing Lookup: Radix Tree & FIB Trie
Di dalam Linux Network Stack, pencarian rute IPv4/IPv6 dilakukan pada *Forwarding Information Base* (FIB).
- Linux menggunakan implementasi **LC-trie (Level-Compressed Trie)** untuk IPv4.
- IPv6 menggunakan **Radix Tree** dengan sistem pemilahan *Longest Prefix Match (LPM)*.
- Ketika paket masuk melalui NIC, driver memicu interrupt (NAPI) -> Linux network stack memproses sk_buff -> pemanggilan fungsi kernel `fib_lookup()` -> evaluasi routing rule database (RPDB via `ip rule`) -> traversal pada LPM trie -> penentuan next-hop L2 address via Neighbor Table (`arp_tbl` atau `nd_tbl`).

---

### 4. Why & What

#### 4.1 Exhaustion IPv4 dan Realitas Dual-Stack
Ketersediaan pool IPv4 publik IANA telah habis sejak 2011. Ruang alamat 32-bit ($2^{32} \approx 4.29 \times 10^9$) tidak mampu menopang densitas perangkat IoT, microservices, container networks, dan telekomunikasi seluler global.

Solusi transisi melibatkan:
- **Carrier-Grade NAT (CGNAT) / RFC 6598 (`100.64.0.0/10`):** Menyebabkan masalah NAT traversal ganda (*Double NAT*), degradasi latensi, serta keterbatasan kapasitas *Stateful Connection Tracking* pada firewall core.
- **Dual-Stack (RFC 4213):** Arsitektur di mana node jaringan mengeksekusi stack IPv4 dan IPv6 secara bersamaan. Merupakan standar defacto transisi enterprise saat ini.
- **NAT64 / DNS64 (RFC 6146 / RFC 6147):** Solusi untuk jaringan *IPv6-Only* internal yang tetap harus mengakses sistem eksternal berbasis IPv4 murni.

#### 4.2 Alokasi Alamat Terstandar
Tabel alokasi ruang lingkup IPv4 & IPv6 enterprise:

| Jenis Alokasi | IPv4 (RFC 1918 / RFC 6598) | IPv6 (RFC 4193 / RFC 4291) |
| :--- | :--- | :--- |
| **Private / Local Scope** | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` | `fc00::/7` (Unique Local Address - ULA, praktis: `fd00::/8`) |
| **Carrier / Shared** | `100.64.0.0/10` (CGNAT) | N/A (IPv6 tidak membutuhkan CGNAT) |
| **Loopback** | `127.0.0.1/8` | `::1/128` |
| **Link-Local Scope** | `169.254.0.0/16` (APIPA) | `fe80::/10` (Komunikasi wajib lokal L2 domain) |
| **Global Unicast** | Alokasi Public RIR (APNIC, ARIN, RIPE) | `2000::/3` (RIR Public Allocation) |
| **Multicast** | `224.0.0.0/4` | `ff00::/8` |

---

### 5. How (Workflow Detail)

Alur transmisi paket IPv4/IPv6 dari source container/host ke destination server pada jaringan terdistribusi:

```
[Aplikasi User Space] (Socket connect: AF_INET / AF_INET6)
          │
          ▼
[Linux Kernel VFS / Socket Layer] (Membangun sk_buff)
          │
          ▼
[Routing Decision 1 (FIB Lookup)] ---> Tentukan output device & source IP
          │
          ▼
[Netfilter / iptables / nftables] (Hook: PREROUTING / OUTPUT)
          │
          ▼
[Fragmentasi Engine] (Hanya IPv4 jika paket > Interface MTU; IPv6 drop jika > MTU)
          │
          ▼
[L3-to-L2 Resolution]
   ├── IPv4: ARP Cache hit? ──No──> Send ARP Request (Broadcast)
   └── IPv6: Neighbor Table hit? ──No──> Send ICMPv6 NS (Multicast)
          │
          ▼
[NIC Ring Buffer / Driver Queuing Disciplines (qdisc)]
          │
          ▼
[Physical Medium Transmission]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengiriman Pos Logistik Internasional
- **IPv4:** Seperti sistem pos kuno dengan batas 4 digit kode pos. Ketika populasi melonjak, dinas pos membuat sistem perumahan komunal (NAT/Private IP). Resepsionis utama gedung (Router NAT) harus membuka paket, mencatat siapa penyewa aslinya dalam buku besar (*conntrack table*), dan mengganti amplop surat. Ini memakan waktu, rawan kesalahan jika buku hilang, dan membatasi ukuran paket (fragmentasi di jalan oleh sopir truk pengantar).
- **IPv6:** Setiap butir pasir dan setiap ruangan di seluruh dunia memiliki koordinat GPS unik 16-oktet yang terstandardisasi secara global. Sopir truk tidak boleh merusak/membagi paket di jalan; jika paket terlalu besar untuk jembatan (MTU), sopir mengirim balik drone peringatan ke pengirim untuk mengecilkan paket dari rumah (*PMTUD*).

#### Diagram Transisi NAT64 / DNS64

```
IPv6-Only Client                 DNS64 Server                 NAT64 Gateway              IPv4-Only Server
   (fd00::10)                    (fd00::53)                  (Prefix: 64:ff9b::/96)        (93.184.216.34)
       │                              │                            │                            │
       ├─1. Query AAAA ipv4only.com ─>│                            │                            │
       │  (Tidak ada record AAAA)     ├─2. Query A ipv4only.com───>│                            │
       │                              │<─3. Return 93.184.216.34───┤                            │
       │                              │                            │                            │
       │                              │ [Sintesis IPv6:]           │                            │
       │                              │ 64:ff9b::5db8:d822         │                            │
       │<─4. Return Synthetic AAAA────┤                            │                            │
       │                              │                            │                            │
       ├─5. Packet to 64:ff9b::5db8:d822──────────────────────────>│                            │
       │   (IPv6 Src: fd00::10, Dst: 64:ff9b::5db8:d822)           │                            │
       │                                                           │ [Translasi Header L3/L4]   │
       │                                                           ├─6. Packet to 93.184.216.34─>
       │                                                           │    (IPv4 Src: Public NAT44)│
       │                                                           │<─7. Return IPv4 Traffic────┤
       │<─8. Translated to IPv6 Traffic────────────────────────────┤                            │
```

---

### 7. Simple Example & Practical Example

#### 7.1 Kalkulasi Subnetting (Biner & VLSM)
Misalkan perusahaan diberikan alokasi subnet IPv4: `172.16.0.0/22`.
Total host address: $2^{(32 - 22)} = 2^{10} = 1024$ IP ($1022$ usable).

Kebutuhan VLSM:
1. **Core Database Cluster:** 120 host $\rightarrow$ Dibutuhkan /25 ($2^7 = 128 - 2 = 126$ usable).
2. **Kubernetes Worker Nodes:** 500 host $\rightarrow$ Dibutuhkan /23 ($2^9 = 512 - 2 = 510$ usable).
3. **DMZ Ingress Gateway:** 60 host $\rightarrow$ Dibutuhkan /26 ($2^6 = 64 - 2 = 62$ usable).
4. **Point-to-Point Uplinks:** 2 host $\rightarrow$ Dibutuhkan /30 ($2^2 = 4 - 2 = 2$ usable) atau /31 (RFC 3021).

**Alokasi Optimal (VLSM):**
1. Kubernetes Nodes: `172.16.0.0/23` (Rentang: `172.16.0.1` - `172.16.1.254`, Broadcast: `172.16.1.255`)
2. Database Cluster: `172.16.2.0/25` (Rentang: `172.16.2.1` - `172.16.2.126`, Broadcast: `172.16.2.127`)
3. DMZ Ingress: `172.16.2.128/26` (Rentang: `172.16.2.129` - `172.16.2.190`, Broadcast: `172.16.2.191`)
4. Point-to-Point 1: `172.16.2.192/31` (Alamat: `172.16.2.192` dan `172.16.2.193` - RFC 3021)
5. Sisa: `172.16.2.194/31`, `172.16.2.196/30`, `172.16.2.200/29`, `172.16.2.208/28`, `172.16.2.224/27`, `172.16.3.0/24` (Unallocated reserve pool).

#### 7.2 Implementasi Dual-Stack Linux Server Menggunakan Netplan
File konfigurasi: `/etc/netplan/01-netcfg.yaml`

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: no
      dhcp6: no
      addresses:
        - 198.51.100.10/24
        - 2001:db8:acad:1::10/64
        - fe80::dead:beef:0001/64
      routes:
        - to: default
          via: 198.51.100.1
          metric: 100
        - to: default
          via: 2001:db8:acad:1::1
          metric: 100
      nameservers:
        addresses:
          - 1.1.1.1
          - 8.8.8.8
          - 2606:4700:4700::1111
          - 2001:4860:4860::8888
      routing-policy:
        - from: 198.51.100.10
          table: 100
        - from: 2001:db8:acad:1::10
          table: 101
```

#### 7.3 Konfigurasi Linux IP Forwarding, PMTUD, dan Antispoofing Kernel Parameter
File konfigurasi: `/etc/sysctl.d/99-networking-production.conf`

```ini
# IPv4 Forwarding & Tuning
net.ipv4.ip_forward = 1
net.ipv4.ip_no_pmtu_disc = 0
net.ipv4.tcp_mtu_probing = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# IPv6 Forwarding & Autoconfig Hardening
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.default.forwarding = 1
net.ipv6.conf.all.accept_ra = 0
net.ipv6.conf.default.accept_ra = 0
net.ipv6.conf.all.autoconf = 0
net.ipv6.conf.default.autoconf = 0

# Limit ICMPv6 Rate (DDoS mitigation on NDP)
net.ipv6.icmp.ratelimit = 500
net.ipv4.icmp_ratelimit = 500

# ARP & NDP Cache Tuning for High Density Nodes
net.ipv4.neigh.default.gc_thresh1 = 2048
net.ipv4.neigh.default.gc_thresh2 = 4096
net.ipv4.neigh.default.gc_thresh3 = 8192
net.ipv6.neigh.default.gc_thresh1 = 2048
net.ipv6.neigh.default.gc_thresh2 = 4096
net.ipv6.neigh.default.gc_thresh3 = 8192
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Latar Belakang Masalah
Sebuah platform E-Commerce Unicorn mengakuisisi perusahaan logistik regional. Terjadi masalah kritis:
- VPC E-Commerce: `10.100.0.0/16`
- VPC Logistik: `10.100.0.0/16` (Overlapping Subnet mutlak).
- Terdapat kebutuhan integrasi langsung database order processing via private backbone tanpa eksposur ke public internet.
- Keterbatasan alokasi sisa RFC 1918 internal mencegah re-addressing seluruh cluster logistik yang memiliki 4000+ container aktif.

#### Solusi Arsitektur
1. **Transisi Jangka Pendek:** Implementasi Non-Overlapping Inter-VPC Transit Hub dengan **Bidirectional Static 1:1 Carrier-Grade NAT (RFC 6598)**.
   - VPC Logistik dipetakan secara virtual ke pool `100.64.10.0/24`.
   - VPC E-Commerce dipetakan secara virtual ke pool `100.64.20.0/24`.
2. **Transisi Jangka Panjang (Greenfield Native Dual-Stack / IPv6-First Migration):**
   - Mengalokasikan blok IPv6 ULA `fd00:ec01::/48` untuk E-Commerce dan `fd00:log1::/48` untuk Logistik.
   - Mengonfigurasi Cilium CNI pada cluster Kubernetes untuk beroperasi dalam mode Dual-Stack dengan IPv6 native direct-routing via BGP EVPN peering.
   - Service-to-Service communication antar kedua entitas diarahkan secara eksklusif menggunakan IPv6 endpoint AAAA record, sehingga bypass sepenuhnya keterbatasan alamat IPv4 dan overhead NAT.

#### Hasil Produksi
- Beban CPU NAT Gateway berkurang sebesar 74% setelah 80% traffic antar-layanan bermigrasi ke IPv6 murni.
- Masalah connection tracking table saturation (`nf_conntrack: table full, dropping packet`) terselesaikan.
- End-to-end latency microservices terpangkas sebesar 3.2 ms karena tidak ada translasi IP L3/L4 berulang kali.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Biaya |
| :--- | :--- | :--- |
| **Pure IPv4 (Single Stack)** | Sederhana, kompatibel universal dengan semua legacy appliance/software. | Address exhaustion parah, biaya sewa IP publik mahal, dependensi berat pada NAT/CGNAT, keterbatasan skalabilitas K8s IP per node. |
| **Dual-Stack (IPv4 + IPv6)** | Jalur migrasi paling aman, reliabilitas tinggi (fallback via RFC 6724 Happy Eyeballs). | *Double memory overhead* pada kernel (FIB, ARP/NDP tables), kompleksitas konfigurasi firewall ganda (iptables + ip6tables / nftables), monitoring overhead 2x lipat. |
| **IPv6-Only with NAT64/DNS64** | Arsitektur modern, tidak ada limitasi IP internal, konsumsi memori single routing table, zero NAT antar sistem modern. | Inkompatibilitas dengan aplikasi hardcoded IPv4 literals, dependensi tunggal pada keandalan Stateful NAT64 Gateway, kompleksitas troubleshooting DNS64 TTL. |
| **RFC 3021 (/31 Subnetting pada P2P)** | Menghemat 50% ruang alamat point-to-point link (tanpa reserved Network & Broadcast). | Harus diverifikasi ke kompatibilitas perangkat hardware lawas (beberapa switch Layer 3 kuno menolak `/31`). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 PMTUD Black Hole (Path MTU Discovery)
- **Gejala:** Koneksi TCP terbentuk sukses (SYN/ACK 3-way handshake selesai karena ukuran paket kecil), namun saat transfer payload besar (seperti curl HTTP GET request besar, SQL dumping, atau SCP file transfer), koneksi mendadak *hang* / *freeze* dan timeout.
- **Root Cause:** Ada intermediate link dengan MTU lebih rendah (misal: 1420 bytes akibat tunnel VXLAN/GRE/WireGuard), router mengirim *ICMP Type 3, Code 4 (IPv4 Fragmentation Needed)* atau *ICMPv6 Type 2 (Packet Too Big)*, tetapi diblokir oleh firewall border security yang menerapkan "Drop all ICMP blindly". Host pengirim tidak pernah tahu harus mengecilkan ukuran paket (MSS).
- **Resolusi Produksi:**
  1. Jangan pernah memblokir ICMP tipe diagnostik esensial.
  2. Implementasikan TCP MSS Clamping pada gateway edge/router:
     ```bash
     # IPv4 MSS Clamping
     iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
     # IPv6 MSS Clamping
     ip6tables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
     ```

#### 10.2 Asymmetric Routing & Reverse Path Forwarding (uRPF) Drop
- **Gejala:** Server menerima paket tetapi respon tidak pernah sampai ke klien, atau kernel melepaskan (*drop*) paket secara diam-diam.
- **Root Cause:** Paket ingress masuk via `eth0`, tetapi routing table kernel mengirim balasan via `eth1`. Jika `net.ipv4.conf.all.rp_filter = 1` (Strict Mode), kernel akan memverifikasi apakah interface kedatangan adalah interface terbaik untuk mencapai IP pengirim. Jika tidak, kernel langsung men-drop paket tersebut.
- **Investigasi:**
  ```bash
  # Cek counter drop kernel
  netstat -s | grep -i "IPReversePathFilter"
  # Atau menggunakan nstat
  nstat -az IPReversePathFilter
  ```
- **Resolusi:** Ubah rp_filter ke mode Loose (`2`) jika arsitektur jaringan mewajibkan asymmetric routing multi-homed:
  ```bash
  sysctl -w net.ipv4.conf.all.rp_filter=2
  sysctl -w net.ipv4.conf.default.rp_filter=2
  ```

#### 10.3 NDP Cache Exhaustion Denial of Service
- **Gejala:** Pada interface subnet IPv6 `/64`, penyerang memindai jutaan alamat acak secara masif. Host router mengalami crash out-of-memory atau CPU spike 100%.
- **Root Cause:** Subnet `/64` memiliki $1.8 \times 10^{19}$ alamat. Setiap paket yang menuju host fiktif memaksa router menyimpan entri status *INCOMPLETE* pada Neighbor Cache Table Linux.
- **Resolusi:** Batasi tuning `gc_thresh` kernel dan terapkan ingress rate-limiting pada paket ICMPv6 NS.

---

### 11. Best Practices (Production Checklist)

#### Perencanaan IP Address Management (IPAM)
- [ ] Alokasikan subnetting IPv4 berbasis hierarki modular geospasial/fungsi (misal: Pods, Services, Out-of-band/IPMI, Storage).
- [ ] Subnet minimal untuk link point-to-point IPv4 adalah `/31` (RFC 3021); jangan pernah menyia-nyiakan `/30`.
- [ ] Subnet standar interface LAN/Access IPv6 mutlak `/64` (untuk menjamin kompatibilitas SLAAC dan integrasi hardware).
- [ ] Tetapkan alokasi IPv6 global enterprise minimal `/48` dari RIR, pecah menjadi `/52` atau `/56` per datacenter/region, dan `/64` per VLAN/subnet.

#### Kernel & Keamanan Sistem
- [ ] Pastikan ICMP PMTUD diizinkan: ICMPv4 Type 3 Code 4 dan ICMPv6 Type 2 Code 0.
- [ ] Matikan IPv6 Source Routing (`net.ipv6.conf.all.accept_source_route = 0`).
- [ ] Matikan ICMP Redirect acceptance (`net.ipv4.conf.all.accept_redirects = 0`, `net.ipv6.conf.all.accept_redirects = 0`).
- [ ] Terapkan RFC 7217 Stable Privacy Address untuk konfigurasi klien dinamis alih-alih EUI-64 MAC embedded untuk mencegah tracking hardware.

---

### 12. Hands-on Practice: Simulasi Arsitektur Dual-Stack, Routing Namespace & NAT64

Simulasi lengkap lab produksi ini akan membuat topology virtual enterprise menggunakan Linux Network Namespaces (`ip netns`), routing dual-stack, dan translasi traffic.

Simpan seluruh instruksi dan script automasi ini pada direktori: `hands-on/m02/dualstack_lab.sh`.

```bash
#!/usr/bin/env bash
# hands-on/m02/dualstack_lab.sh
# Enterprise Dual-Stack & PMTUD Emulation Lab
set -euo pipefail

echo "[+] Initializing Lab: Dual-Stack Namespaces..."

# 1. Bersihkan namespace lawas jika ada
ip netns del client-ns 2>/dev/null || true
ip netns del router-ns 2>/dev/null || true
ip netns del server-ns 2>/dev/null || true

# 2. Buat Network Namespaces
ip netns add client-ns
ip netns add router-ns
ip netns add server-ns

echo "[+] Creating Veth Interfaces..."
# Client to Router link
ip link add veth-c type veth peer name veth-cr
ip link set veth-c netns client-ns
ip link set veth-cr netns router-ns

# Router to Server link
ip link add veth-sr type veth peer name veth-s
ip link set veth-sr netns router-ns
ip link set veth-s netns server-ns

echo "[+] Configuring IP Addressing (Dual-Stack)..."
# Configure Client (IPv4: 192.168.10.2/24, IPv6: 2001:db8:10::2/64)
ip netns exec client-ns ip link set lo up
ip netns exec client-ns ip link set veth-c up
ip netns exec client-ns ip addr add 192.168.10.2/24 dev veth-c
ip netns exec client-ns ip addr add 2001:db8:10::2/64 dev veth-c
ip netns exec client-ns ip route add default via 192.168.10.1
ip netns exec client-ns ip -6 route add default via 2001:db8:10::1

# Configure Router
ip netns exec router-ns ip link set lo up
ip netns exec router-ns ip link set veth-cr up
ip netns exec router-ns ip link set veth-sr up
# Gateway Subnet 10
ip netns exec router-ns ip addr add 192.168.10.1/24 dev veth-cr
ip netns exec router-ns ip addr add 2001:db8:10::1/64 dev veth-cr
# Gateway Subnet 20 (Dengan Link MTU 1400 untuk tes PMTUD)
ip netns exec router-ns ip addr add 192.168.20.1/24 dev veth-sr
ip netns exec router-ns ip addr add 2001:db8:20::1/64 dev veth-sr
ip netns exec router-ns ip link set dev veth-sr mtu 1400

# Aktifkan L3 Forwarding di Router
ip netns exec router-ns sysctl -w net.ipv4.ip_forward=1 > /dev/null
ip netns exec router-ns sysctl -w net.ipv6.conf.all.forwarding=1 > /dev/null

# Configure Server (IPv4: 192.168.20.2/24, IPv6: 2001:db8:20::2/64, MTU 1400)
ip netns exec server-ns ip link set lo up
ip netns exec server-ns ip link set veth-s up
ip netns exec server-ns ip link set dev veth-s mtu 1400
ip netns exec server-ns ip addr add 192.168.20.2/24 dev veth-s
ip netns exec server-ns ip addr add 2001:db8:20::2/64 dev veth-s
ip netns exec server-ns ip route add default via 192.168.20.1
ip netns exec server-ns ip -6 route add default via 2001:db8:20::1

echo "[+] Menjalankan Verifikasi Konektivitas..."
echo "--- Test 1: IPv4 Ping ---"
ip netns exec client-ns ping -c 2 192.168.20.2

echo "--- Test 2: IPv6 Ping ---"
ip netns exec client-ns ping6 -c 2 2001:db8:20::2

echo "--- Test 3: Path MTU Discovery Verification (DF-Bit Set) ---"
# Ping paket 1450 bytes dengan flag DF (Don't Fragment) dari Client (MTU 1500) melewati Router MTU 1400
set +e
ip netns exec client-ns ping -c 2 -M do -s 1450 192.168.20.2
if [ $? -ne 0 ]; then
    echo "[!] Ping gagal secara expected karena ukuran paket melampaui MTU 1400 router tanpa fragmentasi."
fi
set -e

echo "[+] Verifikasi tabel Neighbor (NDP) & ARP:"
echo "--- IPv4 ARP Table (Client) ---"
ip netns exec client-ns ip neigh show
echo "--- IPv6 Neighbor Table (Client) ---"
ip netns exec client-ns ip -6 neigh show

echo "[SUCCESS] Lab Dual-Stack Enterprise siap digunakan untuk investigasi lebih lanjut."
```

#### Langkah Eksekusi & Pengujian:
1. Simpan script di atas ke `hands-on/m02/dualstack_lab.sh`.
2. Berikan izin eksekusi dan jalankan:
   ```bash
   chmod +x hands-on/m02/dualstack_lab.sh
   sudo ./hands-on/m02/dualstack_lab.sh
   ```
3. Lakukan packet sniffing menggunakan `tcpdump` secara paralel pada console terminal kedua untuk melihat pergantian frame ARP dan NDP:
   ```bash
   sudo ip netns exec router-ns tcpdump -nn -i any icmp or icmp6
   ```

---

### 13. Exercise

#### Level Easy
Diberikan blok IP: `192.168.50.0/24`. Rancang pembagian subnet identik untuk 4 departemen berbeda.
- **Kebutuhan:** Tentukan Subnet Mask (CIDR), Network Address, Rentang Host yang valid, dan Broadcast Address untuk masing-masing departemen.

#### Level Medium
Sebuah node Linux dengan IP `10.0.5.10/24` gagal mengakses server `10.0.8.50/24`. Tabel routing lokal menunjukkan:
```
default via 10.0.5.1 dev eth0
10.0.0.0/21 dev eth1 proto kernel scope link src 10.0.5.10
```
- Analisis mengapa koneksi menuju `10.0.8.50` keluar melalui `eth1` alih-alih default gateway `eth0`. Jelaskan mekanisme LPM (*Longest Prefix Match*) yang menyebabkan anomali ini dan berikan perintah modifikasi routing table perbaikannya.

#### Level Hard
Sebuah cluster database terdistribusi mentransfer backup 100GB antar datacenter melalui overlay GRE Tunnel. Sesi TCP sering mengalami degradasi bandwidth masif hingga terputus (stall) pada interval waktu tertentu, sementara traffic ping (ICMP 64 bytes) stabil dengan packet loss 0%.
- Buat file bash reproduksi otomatis menggunakan `ip netns` yang mensimulasikan kegagalan PMTUD ini dengan iptables packet dropping pada ICMP Type 3 Code 4. Selesaikan problem tersebut menggunakan dynamic TCP MSS Clamping pada antarmuka tunnel router.

---

### 14. Challenge

#### Skenario Kasus Arsitektur (Zero-Downtime Migration under IPv4 Starvation)
Anda adalah Lead Infrastructure Architect di sebuah Bank Digital skala enterprise.
Kondisi saat ini:
- Core banking Anda beroperasi pada subnet on-premise private `10.50.0.0/16`.
- Seluruh IP usable pada pool tersebut telah habis terpakai ($65534$ IP) akibat lonjakan deployment microservices containerized.
- Anda memiliki 3 Datacenter baru yang harus online dalam tempo 30 hari. Perusahaan induk menolak memperluas alokasi RFC 1918 karena bentrok dengan entitas anak perusahaan lainnya di seluruh grup.
- Vendor regulasi pembayaran mewajibkan integrasi jaringan menggunakan alamat yang dapat diaudit secara deterministik.

#### Misi Anda:
1. Rancang arsitektur pengalamatan jaringan menyeluruh menggunakan pendekatan kombinasi **RFC 6598 (CGNAT)** dan **IPv6 Native Backbone (RFC 4193 / ULA & RFC 4291 Global Aggregatable)**.
2. Tentukan bagaimana komunikasi inter-service service mesh (misal: Istio/Envoy) dapat dialihkan ke IPv6 murni tanpa mengubah kode sumber aplikasi yang masih mengasumsikan database IP berbasis IPv4.
3. Rancang fallback disaster-recovery routing blueprint ketika edge NAT64 gateway mengalami crash redundansi hardware.
4. Buat dokumen arsitektur komprehensif mencakup:
   - Skema IP addressing per region/datacenter.
   - Peta routing FIB (tabel rute edge dan core).
   - Firewall perimeter filter matrix.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Berapa ukuran byte tetap (*fixed size*) dari Base Header IPv6, dan sebutkan 2 field IPv4 yang dihilangkan secara permanen pada base header tersebut!
2. Jika sebuah interface memiliki alamat IPv4 `192.168.1.135/27`, tentukan:
   - Network ID
   - Usable Host Range
   - Directed Broadcast Address
3. Apa fungsi fundamental dari bit *Don't Fragment (DF)* pada header IPv4, dan apa respons router pengirim jika ukuran paket melebihi interface MTU ketika bit ini bernilai 1?
4. Mengapa subnet `/31` diizinkan untuk point-to-point link pada RFC 3021, padahal secara konvensional subnetting membutuhkan 2 alamat cadangan (Network & Broadcast)?
5. Apa format scope multicast address untuk memanggil seluruh node IPv6 pada link lokal (*All-Nodes Multicast*)?

#### 5 Pertanyaan Intermediate
1. Jelaskan bagaimana protokol SLAAC (Stateless Address Autoconfiguration) pada IPv6 mendeteksi alamat IP yang duplikat (DAD) di segmen layer-2 tanpa menggunakan ARP!
2. Bagaimana algoritma *Longest Prefix Match (LPM)* bekerja di dalam kernel routing table jika paket memiliki destinasi `172.16.5.33` dan tabel memiliki entri untuk `172.16.0.0/16`, `172.16.5.0/24`, dan `172.16.5.32/28`?
3. Pada kondisi apa TCP MSS Clamping wajib diimplementasikan, dan bagaimana perhitungannya jika sebuah interface memiliki MTU 1500 byte yang dibungkus enkapsulasi WireGuard (overhead 60 byte) dan standar TCP/IPv4 header?
4. Terangkan perbedaan mendasar dalam resolusi DNS antara fungsi **A Record**, **AAAA Record**, dan sintesis alamat oleh **DNS64** ketika klien IPv6-only mengakses web server legacy IPv4!
5. Apa dampak performa pada Linux Kernel jika nilai sysctl `net.ipv4.neigh.default.gc_thresh3` terlampaui pada server gateway Kubernetes yang melayani puluhan ribu pod?

#### 3 Skenario Kasus Produksi
1. **Skenario A (Asymmetric Routing Dropout):**
   Sebuah gateway cluster firewall memiliki dua interface WAN: ISP-A (`eth1`) dan ISP-B (`eth2`). Host di internet mengirim traffic via IP publik ISP-B, namun router merespons melalui default gateway yang mengarah ke ISP-A. Klien di internet mengeluhkan kegagalan koneksi TCP handshake. Jelaskan mengapa TCP handshake gagal dan opsi perbaikan kernel networking apa yang harus diatur pada firewall tersebut!
2. **Skenario B (IPv6 Routing Extension Header Security):**
   Security Operations Center (SOC) mendeteksi lonjakan traffic IPv6 abnormal yang melewati firewall tanpa tercatat di IDS/IPS rules, memanfaatkan *Routing Extension Header Type 0 (RH0)*. Mengapa RFC 5095 mendeprekasi RH0 dan tindakan pengamanan apa yang wajib diambil pada kernel router border?
3. **Skenario C (K8s Dual-Stack Subnet Exhaustion):**
   Sebuah cluster Kubernetes berjalan dalam mode dual-stack di cloud provider. Alokasi IPv4 node subnet `/24` mengalami kehabisan alamat IP (*IP starvation*) saat auto-scaler memicu lonjakan 100 node baru, meskipun ketersediaan alamat IPv6 `/64` masih sangat berlimpah. Tentukan solusi arsitektural mitigasi tanpa melakukan rebuild ulang seluruh VPC/cluster yang sedang melayani traffic live!

---

### 16. Summary
- **IPv4 vs IPv6:** IPv6 bukan sekadar penambahan digit alamat dari 32-bit ke 128-bit, melainkan restrukturisasi fundamental layer network. Penghapusan *Header Checksum* dan pelarangan fragmentasi di intermediate router mentransformasi forwarding plane router menjadi jauh lebih efisien pada throughput multi-gigabit.
- **Subnetting & Routing:** Efisiensi routing tabel ditentukan oleh pemahaman mutlak terhadap CIDR, VLSM, dan agregasi rute. Algoritma *Longest Prefix Match* (LPM) memproses paket secara hierarkis; ketidaktelitian alokasi prefix mask dapat memicu insiden *asymmetric routing* dan *black hole packet drop*.
- **Transisi Jaringan:** Arsitektur modern saat ini beroperasi pada fase *Dual-Stack*, dengan dorongan kuat menuju infrastruktur internal *IPv6-Only* memanfaatkan bridging teknologi seperti NAT64/DNS64 untuk efisiensi alokasi resource IP, eliminasi kompleksitas state table NAT44, dan kesiapan skalabilitas sistem cloud-native masa depan.