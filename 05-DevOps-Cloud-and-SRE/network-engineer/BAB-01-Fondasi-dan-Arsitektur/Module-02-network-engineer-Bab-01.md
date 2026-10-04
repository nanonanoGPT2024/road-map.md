# BAB 01: Fondasi dan Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Datapath Kernel Tingkat Lanjut**: Mengidentifikasi titik kritis pemrosesan paket dalam Linux Kernel Subsystem (Netfilter, Conntrack, eBPF/XDP, SoftIRQ, dan Ring Buffer) guna mengeliminasi *packet drop* pada beban lalu lintas tinggi.
2. **Merancang dan Mengimplementasikan Arsitektur Jaringan Modern**: Membangun topologi Clos (*Spine-Leaf*) enterprise menggunakan fondasi BGP Unnumbered (*RFC 5549*) serta mengonfigurasi *Overlay Network* berbasis EVPN-VXLAN (*RFC 8365* / *RFC 7432*) dengan model *Symmetric Integrated Routing and Bridging* (IRB).
3. **Mengoptimalkan Throughput dan Latensi Linux Networking**: Menerapkan konfigurasi *link aggregation* (LACP 802.3ad) dengan *transmit hash policy* tingkat lanjut (`layer3+4`), melakukan *tuning* NIC *offloading* (RSS, RPS, RFS, TSO, GRO), serta mengonfigurasi parameter *TCP Stack* berbasis algoritma kongesti modern (BBRv2/BBRv3).
4. **Mendiagnosis Kegagalan Jaringan Skala Besar**: Melakukan mitigasi insiden kritis produksi seperti *Conntrack table exhaustion*, *Path MTU Discovery (PMTUD) Black Hole*, *TCP SYN flood*, dan *microburst-induced buffer drops* menggunakan observabilitas berbasis `bpftool`, `perf`, `ss`, dan `ethtool`.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
*   **Fondasi OSI & TCP/IP**: Handshake 3 arah TCP, mekanisme *sliding window*, *flow control*, dan *congestion control* dasar.
*   **Linux Networking Dasar**: Penggunaan perintah `iproute2` dasar (`ip addr`, `ip link`, `ip route`), manipulasi *iptables/nftables*, dan konsep *network namespace*.
*   **Protokol Routing Inti**: Pemahaman kerja BGP (eBGP vs iBGP, *autonomous system*, *path attributes*) dan OSPF.
*   **Lingkungan Lab**:
    *   2 unit host/VM Linux berbasis kernel >= 5.15 (Ubuntu 22.04 LTS / Debian 12 / RHEL 9).
    *   Akses `root` / `sudo`.
    *   Tool terpasang: `iproute2`, `ethtool`, `conntrack-tools`, `tcpdump`, `frr` (Free Range Routing), `iperf3`, `bpftool`, `bridge-utils`.
    *   Dukungan virtualisasi hardware (VT-x/AMD-V) direkomendasikan jika menjalankan topologi lab via Vagrant/Containerlab.

---

### 3. Concept & Internal Architecture

#### 3.1. Linux Kernel Networking Subsystem: Dari NIC hingga Socket
Saat frame Ethernet mencapai port fisik Network Interface Card (NIC), alur eksekusi internal berjalan sebagai berikut:

```
[ Ethernet Frame Datang ]
           │
           ▼
[ RX FIFO Buffer (NIC Hardware) ]
           │
           ▼ (DMA Transfer via PCIe)
[ Host Memory: RX Ring Buffer (Descriptors) ]
           │
           ▼ (Hard IRQ / MSI-X)
[ CPU Core Interrupt Handler ] ──> Schedule NAPI Poll
           │
           ▼ (SoftIRQ: NET_RX_SOFTIRQ via ksoftirqd)
[ NAPI Polling Loop (napi_gro_receive) ]
           │
     ┌─────┴─────────────────────────┐
     │ Fitur eBPF / XDP Aktif?       │
     ├───────────────────────────────┤
     │ [YES] ──> XDP Driver/Generic  │ ──> [XDP_DROP / XDP_TX / XDP_REDIRECT]
     │            (Kernel Bypass)    │
     │ [NO]                          │
     └─────┬─────────────────────────┘
           ▼
[ Alokasi sk_buff (Socket Buffer Metadata) ]
           │
           ▼
[ Generic Receive Offload (GRO) Engine ]
           │
           ▼
[ Netfilter: PREROUTING Chain (raw, mangle, nat) ]
           │
           ▼
[ Connection Tracking Engine (nf_conntrack) ]
           │
           ├───> [ Local Delivery? ] ──> PREROUTING Route Lookup
           │            │
           │            ▼
           │     [ Netfilter: INPUT Chain ]
           │            │
           │            ▼
           │     [ IP Protocol Handler (tcp_v4_rcv, udp_rcv) ]
           │            │
           │            ▼
           │     [ Socket Receive Buffer (sk_rcvbuf) ]
           │            │
           │            ▼
           │     [ User Space Application via read() / recv() / epoll ]
           │
           └───> [ Forwarding? ] ──> Netfilter FORWARD Chain ──> POSTROUTING ──> TX Queue
```

1. **DMA Transfer & Ring Buffer**: NIC menulis frame ke memori sistem (RAM) menggunakan *Direct Memory Access* (DMA) tanpa membebani siklus CPU. Data ditempatkan pada *RX Ring Buffer* yang berupa struktur circular queue.
2. **Hard IRQ vs SoftIRQ**: NIC memicu hardware interrupt (MSI-X). CPU mematikan interrupt hardware untuk interface tersebut dan menjadwalkan *SoftIRQ* (`NET_RX_SOFTIRQ`). *ksoftirqd* kemudian mengeksekusi *NAPI (New API) poll loop* untuk mengambil batch paket secara efisien tanpa *interrupt storm*.
3. **eBPF/XDP Hook**: *eXpress Data Path* (XDP) memungkinkan eksekusi kode C sandboxed tepat di layer driver NIC sebelum struktur kernel yang berat (`sk_buff`) dialokasikan. Keputusan seperti *drop* (DDoS mitigation), *redirect*, atau *pass* dapat diambil dengan latensi sub-mikrodetik.
4. **sk_buff & GRO**: Jika lolos, kernel membungkus paket ke dalam `struct sk_buff`. GRO (*Generic Receive Offload*) menggabungkan beberapa paket TCP sekuensial menjadi satu paket raksasa virtual untuk mengurangi overhead traversal stack protokol.
5. **Netfilter & Conntrack**: Paket melewati evaluasi aturan firewall. Di sini, `nf_conntrack` memelihara *state machine* (NEW, ESTABLISHED, RELATED) yang disimpan dalam *hash table global*.

#### 3.2. Data Center Fabric: Underlay vs Overlay & EVPN-VXLAN
Pusat data modern beralih dari arsitektur *Spanning Tree Protocol (STP)* warisan ke fabric *Spine-Leaf* berbasis IP Layer-3 murni (*Underlay*) dengan enkapsulasi Layer-2/Layer-3 (*Overlay*).

```
                      +-------------------+
                      |   Spine Switch 1  | (Underlay IP Fabric)
                      +---------+---------+
                                |
        +-----------------------+-----------------------+
        |                                               |
+-------+-------+                               +-------+-------+
|  Leaf 1 (VTEP)|                               |  Leaf 2 (VTEP)|
+---+-------+---+                               +---+-------+---+
    |       |                                       |       |
+---+---+ +---+---+                           +---+---+ +---+---+
| Server| | Server|                           | Server| | Server|
| Host A| | Host B|                           | Host C| | Host D|
+-------+ +-------+                           +-------+ +-------+
  [ Tenant Red ]                                [ Tenant Red ]
   10.100.1.10                                   10.100.1.20
   (VLAN 100)                                     (VLAN 100)
        │                                               ▲
        └────────────── [ VXLAN Encapsulated ] ─────────┘
                    VNI 10100 (Geneve/VXLAN UDP 4789)
```

*   **Underlay Network**: Jaringan fisik L3 berperforma tinggi, deterministik, dan anti-loop yang menggunakan *Equal-Cost Multi-Pathing* (ECMP) via BGP (RFC 7938).
*   **Overlay Network (VXLAN - RFC 7348)**: Mengenkapsulasi frame Ethernet L2 ke dalam paket UDP port 4789. Memungkinkan mobilitas host L2 (stretch subnet) melintasi batas-batas L3 fisik tanpa risiko broadcast storm STP.
*   **EVPN Control Plane (MP-BGP EVPN - RFC 7432 / RFC 8365)**: Menghilangkan mekanisme *Flood-and-Learn* konvensional VXLAN. BGP EVPN mendistribusikan informasi MAC address host dan IP address host (Type-2 routes) serta Prefix IP (Type-5 routes) secara deterministik menggunakan BGP.
*   **Symmetric vs Asymmetric IRB**:
    *   *Asymmetric IRB*: *Ingress VTEP* melakukan routing ke VNI tujuan dan bridging. *Egress VTEP* hanya melakukan bridging. Membutuhkan konfigurasi seluruh VLAN/VNI tenant di semua leaf switch.
    *   *Symmetric IRB (Enterprise Production Standard)*: *Ingress VTEP* merutekan paket ke dalam *L3 Transit VNI*. *Egress VTEP* menerima paket dari L3 VNI dan merutekannya ke L2 VNI lokal. Pendekatan ini sangat skalabel karena setiap Leaf switch hanya perlu memetakan VNI yang aktif secara lokal.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (L2 Core / STP / Iptables) | Pendekatan Modern Enterprise (Spine-Leaf / EVPN-VXLAN / eBPF) | Mengapa Perlu Beralih? |
| :--- | :--- | :--- | :--- |
| **Pemanfaatan Bandwidth** | Rendah (50%). STP memblokir link redundan secara paksa untuk menghindari loop. | Maksimal (100%). Pemanfaatan seluruh link via ECMP (Spine-Leaf L3 Fabric). | Efisiensi investasi modal hardware jaringan; utilisasi throughput agregat maksimal. |
| **Blast Radius & Skalabilitas** | Tinggi. Kerusakan STP menyebabkan broadcast storm yang melumpuhkan satu DC. Skala L2 terbatas (~4096 VLAN). | Sangat Terisolir. Masalah link lokal diselesaikan via reroute BGP sub-detik. Skala hingga 16 juta segmen (24-bit VNI). | Mengeliminasi *single point of failure* catastrophic; mendukung multi-tenancy skala masif. |
| **Datapath Processing** | Stack kernel standar lambat via sequential iptables rules (kompleksitas linear $O(N)$). | eBPF/XDP bypass atau ipset/nftables dengan evaluasi hash table $O(1)$. | Mengurangi latensi pemrosesan paket dari orde mikrodetik ke nanodetik; resistan terhadap serangan DDoS. |
| **Control Plane Overlay** | Data-plane learning (*Flood and Learn* via IP Multicast underlay). Menghasilkan storm ARP. | Control-plane driven via MP-BGP EVPN. Entri ARP disintesis dan dipropagasi deterministik. | Mengurangi overhead jaringan, memangkas flooding broadcast, dan mempercepat konvergensi topologi. |

---

### 5. How (Workflow Detail)

#### Siklus Hidup Paket Trans-Subnet Symmetric IRB EVPN-VXLAN
Skenario: Host A (IP: `10.100.1.10`, MAC: `M_A`, Subnet L2: VNI 10100) mengirim paket ke Host C (IP: `10.100.2.20`, MAC: `M_C`, Subnet L2: VNI 10200) yang berada di Leaf 2.

```
Host A (10.100.1.10)
   │ 1. Kirim paket IP (Src: 10.100.1.10, Dst: 10.100.2.20)
   ▼
Leaf 1 / VTEP 1 (Ingress Node)
   │ 2. Terima frame pada VLAN 100 access port.
   │ 3. Periksa tabel routing VRF Tenant.
   │    Ditemukan rute Host C via Next-Hop Leaf 2 melalui L3 Transit VNI 50000.
   │ 4. Rewrite L2 Header:
   │    - Inner DMAC diubah menjadi Router MAC Leaf 2 (RMAC_Leaf2).
   │    - Inner SMAC diubah menjadi Router MAC Leaf 1 (RMAC_Leaf1).
   │ 5. Enkapsulasi VXLAN:
   │    - VNI: 50000 (L3 Transit VNI)
   │    - Outer IP Src: IP VTEP 1 (Underlay Loopback)
   │    - Outer IP Dst: IP VTEP 2 (Underlay Loopback)
   │    - Outer UDP Dst Port: 4789, Src Port: Hash L3/L4 payload (untuk ECMP).
   ▼
Underlay Network (Spine Switch)
   │ 6. Melakukan standard IP forwarding berbasis Outer IP Destination (IP VTEP 2).
   │    Tidak ada pembongkaran paket overlay; pemilihan link berbasis hashing UDP Src Port.
   ▼
Leaf 2 / VTEP 2 (Egress Node)
   │ 7. Menerima paket UDP 4789, membongkar outer IP/UDP/VXLAN header.
   │ 8. Memeriksa L3 Transit VNI 50000 -> Dipetakan ke VRF Tenant lokal.
   │ 9. Lookup tabel routing VRF Tenant:
   │    Ditemukan rute Host C terhubung langsung pada L2 VNI 10200 (VLAN 200).
   │ 10. ARP/Neighbor cache hit:
   │     - Rewrite Inner DMAC: MAC Host C (`M_C`)
   │     - Rewrite Inner SMAC: Gateway MAC Leaf 2
   │ 11. Kirim frame Ethernet native ke port interface Host C.
   ▼
Host C (10.100.2.20)
   Menerima frame Ethernet murni tanpa mengetahui adanya proses enkapsulasi VXLAN.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengiriman Logistik Korporat Multi-Gedung
*   **Host Packet**: Dokumen rahasia yang dikirim karyawan Departemen Keuangan (Host A) ke Departemen HRD (Host C).
*   **VTEP Ingress (Leaf 1)**: Resepsionis Gedung 1 yang memeriksa direktori karyawan global (MP-BGP EVPN Table). Mengetahui bahwa HRD berada di Gedung 2, resepsionis memasukkan dokumen tersebut ke dalam amplop pengiriman logistik antar-gedung standar (VXLAN Outer Header) dengan alamat tujuan Gedung 2.
*   **Underlay Network (Spines)**: Supir truk ekspedisi logistik yang hanya membaca alamat gedung luar (Outer IP Header) dan rute tol tercepat (ECMP), tanpa pernah membuka atau mengetahui isi amplop dalam.
*   **VTEP Egress (Leaf 2)**: Resepsionis Gedung 2 yang membuka amplop pengiriman, melihat dokumen untuk HRD, lalu memanggil kurir lokal untuk mengantarkan dokumen asli ke meja karyawan bersangkutan.

#### Diagram Header Enkapsulasi VXLAN (RFC 7348)
```
+-----------------------------------------------------------------------+
| Outer Ethernet Header (14 bytes)                                      |
| DMAC: Next-hop Spine MAC | SMAC: Leaf 1 MAC | EtherType: 0x0800 (IPv4)|
+-----------------------------------------------------------------------+
| Outer IP Header (20 bytes)                                            |
| Protocol: 17 (UDP) | Src IP: VTEP 1 Loopback | Dst IP: VTEP 2 Loopback|
+-----------------------------------------------------------------------+
| Outer UDP Header (8 bytes)                                            |
| Src Port: Entropy Hash (L3/L4) | Dst Port: 4789 (VXLAN standard)      |
+-----------------------------------------------------------------------+
| VXLAN Header (8 bytes)                                                |
| Flags: 0x08 (I flag valid) | Reserved | VNI: 24-bit identifier | Rsvd |
+-----------------------------------------------------------------------+
| Inner Ethernet Frame (Original L2 Frame)                              |
| DMAC: Target MAC / RMAC | SMAC: Sender MAC / RMAC | EtherType: 0x0800 |
+-----------------------------------------------------------------------+
| Original IP Payload & L4 TCP/UDP Segment                              |
| Src IP: 10.100.1.10 | Dst IP: 10.100.2.20 | TCP Data...              |
+-----------------------------------------------------------------------+
| Outer FCS / CRC Checksum (4 bytes)                                    |
+-----------------------------------------------------------------------+
Total Overhead Enkapsulasi VXLAN: 14 + 20 + 8 + 8 = 50 Bytes
(Wajib menaikkan MTU Fisik Underlay minimal 1550 bytes, idealnya 9000 bytes)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Linux Native LACP Bonding dengan Hashing Layer 3+4
Konfigurasi agregasi link dua interface fisik (`eth1` dan `eth2`) menjadi interface virtual `bond0` dengan toleransi kesalahan dan distribusi beban berbasis port TCP/UDP.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Pastikan modul bonding aktif
modprobe bonding

# 2. Buat bond master interface dengan mode 802.3ad (LACP) dan hash layer3+4
ip link add name bond0 type bond mode 802.3ad \
    miimon 100 \
    lacp_rate fast \
    xmit_hash_policy layer3+4

# 3. Masukkan interface fisik (slaves) ke dalam bond
ip link set eth1 down
ip link set eth2 down
ip link set eth1 master bond0
ip link set eth2 master bond0

# 4. Aktifkan interface
ip link set eth1 up
ip link set eth2 up
ip link set bond0 up

# 5. Pasang alamat IP pada bond0
ip addr add 192.168.10.15/24 dev bond0

# Verifikasi status LACP
cat /proc/net/bonding/bond0
```

#### 7.2. Practical Example: Implementasi Point-to-Point VXLAN Manual di Linux
Script konfigurasi untuk menghubungkan dua host Linux secara transparan melalui terowongan VXLAN L2 murni.

```bash
#!/usr/bin/env bash
# Eksekusi pada Node 1 (IP Underlay: 172.16.1.1/24)
set -euo pipefail

NODE_UNDERLAY_IP="172.16.1.1"
REMOTE_UNDERLAY_IP="172.16.1.2"
VNI_ID=100
OVERLAY_IP="10.200.0.1/24"
VXLAN_IF="vxlan100"
BR_IF="br-vxlan"

echo "[+] Menyiapkan antarmuka VXLAN..."
# Buat interface VXLAN dengan UDP destination port standar 4789
ip link add name "${VXLAN_IF}" type vxlan \
    id "${VNI_ID}" \
    local "${NODE_UNDERLAY_IP}" \
    remote "${REMOTE_UNDERLAY_IP}" \
    dstport 4789 \
    learning

echo "[+] Menyiapkan bridge network lokal..."
ip link add name "${BR_IF}" type bridge
ip link set "${VXLAN_IF}" master "${BR_IF}"

echo "[+] Mengonfigurasi MTU (Handling VXLAN Overhead 50 bytes)..."
# Interface underlay diasumsikan MTU 1500; maka overlay disetel 1450 untuk mencegah fragmentasi
ip link set dev "${VXLAN_IF}" mtu 1450
ip link set dev "${BR_IF}" mtu 1450

echo "[+] Menetapkan IP Overlay pada Bridge..."
ip addr add "${OVERLAY_IP}" dev "${BR_IF}"

echo "[+] Mengaktifkan antarmuka..."
ip link set "${VXLAN_IF}" up
ip link set "${BR_IF}" up

echo "[*] Konfigurasi selesai. Status interface:"
ip -d link show "${VXLAN_IF}"
```

#### 7.3. Practical Example: FRRouting (FRR) Configuration untuk Leaf BGP Underlay
File `/etc/frr/frr.conf` pada arsitektur Leaf BGP Unnumbered:

```text
!
frr version 8.4
frr defaults traditional
hostname LEAF-01
log syslog informational
no ipv6 forwarding
service integrated-vtysh-config
!
interface eth1
 description P2P to SPINE-01
 ipv6 enable
!
interface eth2
 description P2P to SPINE-02
 ipv6 enable
!
interface lo
 ip address 10.255.255.1/32
!
router bgp 65101
 bgp router-id 10.255.255.1
 no bgp default ipv4-unicast
 bgp bestpath as-path multipath-relax
 neighbor FABRIC peer-group
 neighbor FABRIC remote-as external
 neighbor FABRIC capability extended-nexthop
 neighbor eth1 interface peer-group FABRIC
 neighbor eth2 interface peer-group FABRIC
 !
 address-family ipv4 unicast
  network 10.255.255.1/32
  neighbor FABRIC activate
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor FABRIC activate
  advertise-all-vni
 exit-address-family
!
line vty
!
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Insiden: Cascading Outage Akibat Conntrack Exhaustion & Asymmetric Routing
*   **Skala Lingkungan**: 4.000 microservices instances, terdistribusi di atas klaster Kubernetes bare-metal dengan 200 nodes worker, throughput rata-rata: 2,5 juta paket per detik (pps).
*   **Gejala**: Seluruh node worker secara acak dan bergantian berhenti merespons traffic eksternal. Load Balancer upstream menandai ratusan node sebagai *unhealthy*. Peningkatan latensi API internal dari 5 ms menjadi 12.000 ms.
*   **Investigasi Awal**:
    *   Penggunaan CPU node hanya berada pada angka 30%. Utilisasi memori aman di 45%. Utilisasi link fisik rata-rata 10 Gbps dari kapasitas 25 Gbps.
    *   Pemeriksaan ring buffer NIC (`ethtool -S <eth>`) tidak menunjukkan kenaikan `rx_dropped`.
*   **Root Cause Analysis**:
    1.  Log kernel (`dmesg -T`) membanjiri pesan:
        ```text
        [Wed Oct 18 14:22:01 2023] nf_conntrack: table full, dropping packet
        [Wed Oct 18 14:22:01 2023] nf_conntrack: table full, dropping packet
        ```
    2.  Penyelidikan mendalam menemukan bahwa klaster Kubernetes menggunakan *Kube-Proxy* mode iptables standar. Setiap koneksi HTTP short-lived (tanpa TCP keep-alive) membuat satu entri di tabel `nf_conntrack`.
    3.  Tabel `nf_conntrack_max` disetel pada nilai default kernel sebesar `262144`. Nilai timeout status `TIME_WAIT` adalah 120 detik.
    4.  Terjadi *burst* traffic microservice gRPC yang di-retry secara agresif karena satu service backend mengalami degradasi. Akibatnya, kapasitas tabel habis dalam kurun waktu 15 detik, menyebabkan kernel mengeksekusi *hard drop* pada setiap paket TCP SYN yang masuk, mengabaikan ketersediaan CPU dan memori.
    5.  Diperburuk dengan konfigurasi *Asymmetric Routing* di mana traffic SYN-ACK kembali melalui node worker yang berbeda akibat ketidaksesuaian hash ECMP spine switch, menyebabkan `nf_conntrack` menandai paket sebagai `INVALID` dan memicu retransmisi tanpa akhir.

#### Langkah Mitigasi & Remediasi Arsitektur Produksi
1.  **Hotfix Langsung**:
    ```bash
    # Naikkan ukuran conntrack table dan hash buckets seketika tanpa reboot
    sysctl -w net.netfilter.nf_conntrack_max=2097152
    echo 524288 > /sys/module/nf_conntrack/parameters/hashsize

    # Pangkas timeout connection tracking untuk membersihkan tabel lebih cepat
    sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=86400
    sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
    sysctl -w net.netfilter.nf_conntrack_tcp_timeout_close_wait=15
    ```
2.  **Arsitektur Permanen**:
    *   Mengganti arsitektur *Kube-Proxy Iptables* dengan *eBPF Datapath* (Cilium CNI) yang mengimplementasikan bypass Netfilter conntrack murni di layer socket dan XDP hook.
    *   Mengonfigurasi Leaf switch Fabric dengan *Symmetric IRB EVPN* untuk memastikan rute bolak-balik deterministik (symmetric pathing), melenyapkan paket berstatus `INVALID` akibat asymmetrical routing.

---

### 9. Trade-offs

```
                  FLEKSIBILITAS & FITUR
                           ▲
                           │   [Netfilter / iptables / conntrack]
                           │   - Stateful inspection lengkap
                           │   - Mudah di-debug (iptables-save)
                           │   - Throughput: Rendah - Sedang
                           │   - Overhead memori: Sangat Tinggi
                           │
                           │                 [DPDK (Data Plane Dev Kit)]
                           │                 - Kernel bypass total (User-space)
                           │                 - Polling mode (100% CPU lock)
                           │                 - Throughput: Maksimum absolut
                           │                 - Kompleksitas kode: Sangat Tinggi
                           │
                           │   [eBPF / XDP]
                           │   - In-kernel programmable datapath
                           │   - Zero sk_buff overhead pada driver level
                           │   - Keamanan terverifikasi oleh kernel
                           │   - Dukungan stateful butuh manajemen BPF maps
                           │
                           └───────────────────────────────────────►
                                     PERFORMANCE & THROUGHPUT
```

| Pendekatan / Komponen | Keuntungan (Pros) | Konsekuensi & Kerugian (Cons) | Rekomendasi Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **XDP / eBPF Kernel Bypass** | Latensi tingkat nanodetik, memproses puluhan juta pps per node, konsumsi memori sangat rendah. | Debugging sulit, membutuhkan compiler toolchain modern (LLVM/Clang), fitur firewall stateful harus dibangun manual via BPF maps. | Edge DDoS Mitigator, CNI Berkinerja Tinggi (Cilium), Load Balancer L4 Skala Masif. |
| **Netfilter / Conntrack** | Fitur enterprise matang (NAT, ALG, connection tracking), konfigurasi standar industri berbasis teks. | Limitasi skalabilitas, $O(N)$ lookup pada iptables lama, overhead alokasi memory per-flow besar. | Firewall enterprise perimeter konvensional, server dengan koneksi simultan moderat (<100k). |
| **Symmetric IRB (EVPN)** | Skalabel; leaf hanya menyimpan MAC/IP lokal & transit routing; sangat menghemat memori TCAM switch. | Desain arsitektur konfigurasi lebih kompleks (membutuhkan penetapan Transit VNI dan L3 VRF per tenant). | Data Center skala menengah hingga hyperscale, multi-tenant cloud environments. |
| **Asymmetric IRB (EVPN)** | Konfigurasi switch lebih sederhana; leaf tujuan langsung mengetahui local bridge mapping. | Konsumsi TCAM masif; semua VLAN/VNI harus di-stretch dan dikonfigurasi ke seluruh Leaf switch secara seragam. | Data center skala kecil (< 4 Leaf switches) dengan kapasitas TCAM berlebih. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Umum Produksi
1.  **PMTUD Black Hole Akibat Enkapsulasi**:
    *   *Penyebab*: Enkapsulasi VXLAN menambahkan overhead 50 byte (atau Geneve 64+ byte). Jika MTU fisik underlay tetap 1500 dan intermediate router memblokir ICMP Type 3 Code 4 (*Destination Unreachable, Fragmentation Needed*), paket berukuran besar (> 1450 bytes) dengan flag `DF=1` (*Don't Fragment*) akan di-drop secara diam-diam (*silent discard*).
    *   *Solusi*: Wajib mengonfigurasi MTU switch fisik minimum 1600 bytes (atau Jumbo Frame 9000/9216 bytes) di seluruh jalur fabric underlay.
2.  **LACP Hash Polarization (Imbalance Traffic)**:
    *   *Penyebab*: Menggunakan default policy `xmit_hash_policy layer2` pada bond interface. Hash hanya menghitung MAC address sumber dan tujuan. Pada lingkungan routed/virtualized di mana semua frame overlay ditujukan ke gateway MAC yang sama, satu link fisik akan jenuh (*saturated*) 100% sementara link fisik lainnya 0%.
    *   *Solusi*: Ubah hash policy ke `layer3+4` atau `encap3+4` (untuk kernel modern yang mengenali inner overlay header).
3.  **Kernel SoftIRQ Bottleneck (Single Core Saturation)**:
    *   *Penyebab*: Hardware interrupts NIC hanya ditangani oleh `Core 0`. Satu CPU core mengalami 100% `si` (SoftIRQ) pada output `top`, sementara core lain menganggur.
    *   *Solusi*: Aktifkan daemon `irqbalance`, alokasikan *Receive Side Scaling* (RSS) multi-queue pada NIC fisik, dan distribusikan pemrosesan paket menggunakan *Receive Packet Steering* (RPS).

#### 10.2. Troubleshooting Playbook

##### Identifikasi Drop pada Driver dan Ring Buffer:
```bash
# Periksa statistik antarmuka fisik untuk mendeteksi ring buffer overrun
ethtool -S eth0 | grep -E "drop|miss|error|fifo"

# Periksa dan naikkan ukuran RX/TX Ring Buffer ke batas maksimum hardware
ethtool -g eth0
ethtool -G eth0 rx 4096 tx 4096
```

##### Audit dan Observabilitas CPU SoftIRQ:
```bash
# Pantau alokasi pemrosesan SoftIRQ antar-core secara real-time
watch -n 1 -d cat /proc/softirqs

# Periksa antrean backlog network layer
cat /proc/net/softnet_stat
# Kolom 1: Total processed frames
# Kolom 2: Squeezed frames (ksoftirqd kehabisan waktu budget -> naikkan net.core.netdev_budget)
# Kolom 3: Dropped frames karena input queue penuh -> naikkan net.core.netdev_max_backlog
```

##### Debugging Latensi & Retransmisi TCP:
```bash
# Pantau socket TCP yang mengalami retransmisi tinggi
ss -ti '( dport = :443 or sport = :443 )'

# Trace paket yang di-drop kernel menggunakan bpftool / tracepoints
perf record -e skb:kfree_skb -a -g -- sleep 5
perf script | c++filt
```

---

### 11. Best Practices (Production Checklist)

#### System Kernel Sysctl Hardening & Tuning (`/etc/sysctl.d/99-network-performance.conf`)
```ini
# Meningkatkan batas antrean frame yang masuk sebelum diteruskan ke socket layer
net.core.netdev_max_backlog = 16384

# Menentukan batas maksimum budget pemrosesan NAPI poll per siklus CPU
net.core.netdev_budget = 600
net.core.netdev_budget_usecs = 6000

# Meningkatkan kapasitas maksimum socket listen queue untuk menahan SYN burst
net.core.somaxconn = 65535

# Kapasitas alokasi memori buffer socket (min, default, max dalam bytes)
net.ipv4.tcp_rmem = 4096 87380 33554432
net.ipv4.tcp_wmem = 4096 65536 33554432

# Algoritma Congestion Control modern berbasis model latensi (BBR)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Mitigasi SYN Flood dan optimasi resource allocation
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 3240000
net.ipv4.tcp_fin_timeout = 15

# Pengelolaan Connection Tracker di skala masif (Sesuaikan dengan RAM)
net.netfilter.nf_conntrack_max = 2097152
net.netfilter.nf_conntrack_tcp_timeout_established = 28800
```

#### Production Verification Checklist:
*   [ ] MTU fisik underlay disetel ke minimal 9000 bytes (Jumbo Frames) end-to-end melintasi spine dan leaf switches.
*   [ ] Bonding interface LACP dikonfigurasi dengan `xmit_hash_policy=layer3+4` dan `lacp_rate=fast`.
*   [ ] NIC multi-queue diverifikasi aktif (`ethtool -l <eth>`) dengan alokasi queue seimbang terhadap jumlah core CPU fisik.
*   [ ] Offloading hardware aktif: `tso on`, `gso on`, `gro on`, `rx on`, `tx on` (validasi via `ethtool -k <eth>`).
*   [ ] Monitoring real-time metrik `node_netstat_Tcp_RetransSegs` dan `node_nf_conntrack_entries` via Prometheus node-exporter terpasang dengan alert threshold 80%.

---

### 12. Hands-on Practice

Simulasi lab ini akan membangun dua node network namespace yang saling terisolasi (`host-alpha` dan `host-beta`) dan menghubungkannya melalui tunnel VXLAN L2 point-to-point terenkapsulasi murni menggunakan Linux kernel primitives.

File skrip otomatisasi ini harus disimpan di path: `hands-on/m02/setup_vxlan_lab.sh`

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: setup_vxlan_lab.sh
# Path: hands-on/m02/setup_vxlan_lab.sh
# Deskripsi: Setup multi-namespace L3 underlay dan L2 VXLAN overlay emulator
# ==============================================================================
set -euo pipefail

log() { echo -e "\033[1;32m[INFO]\033[0m $*"; }
cleanup() {
    log "Membersihkan environment lab lama..."
    ip netns del ns-underlay-1 2>/dev/null || true
    ip netns del ns-underlay-2 2>/dev/null || true
    ip netns del tenant-a 2>/dev/null || true
    ip netns del tenant-b 2>/dev/null || true
    ip link del veth-core1 2>/dev/null || true
}

trap cleanup EXIT
cleanup
trap - EXIT

log "1. Membuat Network Namespaces (Underlay Routers & Tenants)..."
ip netns add ns-underlay-1 # Bertindak sebagai Leaf 1 / VTEP 1
ip netns add ns-underlay-2 # Bertindak sebagai Leaf 2 / VTEP 2
ip netns add tenant-a      # Bertindak sebagai Container/VM di Leaf 1
ip netns add tenant-b      # Bertindak sebagai Container/VM di Leaf 2

log "2. Membangun Link P2P Underlay (Simulasi Spine Switch)..."
ip link add veth-core1 type veth peer name veth-core2
ip link set veth-core1 netns ns-underlay-1
ip link set veth-core2 netns ns-underlay-2

# Konfigurasi IP Underlay Transit
ip -netns ns-underlay-1 addr add 172.16.0.1/30 dev veth-core1
ip -netns ns-underlay-2 addr add 172.16.0.2/30 dev veth-core2
ip -netns ns-underlay-1 link set veth-core1 up
ip -netns ns-underlay-2 link set veth-core2 up
ip -netns ns-underlay-1 link set lo up
ip -netns ns-underlay-2 link set lo up

log "Validasi Underlay Ping antar VTEP:"
ip netns exec ns-underlay-1 ping -c 2 172.16.0.2

log "3. Mengonfigurasi Antarmuka VXLAN di Masing-Masing VTEP..."
# VTEP 1
ip netns exec ns-underlay-1 ip link add name vxlan-vni1000 type vxlan \
    id 1000 \
    local 172.16.0.1 \
    remote 172.16.0.2 \
    dstport 4789
ip netns exec ns-underlay-1 ip link set vxlan-vni1000 up

# VTEP 2
ip netns exec ns-underlay-2 ip link add name vxlan-vni1000 type vxlan \
    id 1000 \
    local 172.16.0.2 \
    remote 172.16.0.1 \
    dstport 4789
ip netns exec ns-underlay-2 ip link set vxlan-vni1000 up

log "4. Menghubungkan Tenant ke VTEP (Simulasi Port Access L2)..."
# Link Tenant A ke VTEP 1
ip link add veth-tA type veth peer name veth-leaf1
ip link set veth-tA netns tenant-a
ip link set veth-leaf1 netns ns-underlay-1

# Link Tenant B ke VTEP 2
ip link add veth-tB type veth peer name veth-leaf2
ip link set veth-tB netns tenant-b
ip link set veth-leaf2 netns ns-underlay-2

# Setup Linux Bridge pada Leaf 1
ip netns exec ns-underlay-1 ip link add name br-vni1000 type bridge
ip netns exec ns-underlay-1 ip link set br-vni1000 up
ip netns exec ns-underlay-1 ip link set vxlan-vni1000 master br-vni1000
ip netns exec ns-underlay-1 ip link set veth-leaf1 master br-vni1000
ip netns exec ns-underlay-1 ip link set veth-leaf1 up

# Setup Linux Bridge pada Leaf 2
ip netns exec ns-underlay-2 ip link add name br-vni1000 type bridge
ip netns exec ns-underlay-2 ip link set br-vni1000 up
ip netns exec ns-underlay-2 ip link set vxlan-vni1000 master br-vni1000
ip netns exec ns-underlay-2 ip link set veth-leaf2 master br-vni1000
ip netns exec ns-underlay-2 ip link set veth-leaf2 up

log "5. Konfigurasi Endpoint IP Tenant (Satu Subnet L2 Overlay: 192.168.100.0/24)..."
ip -netns tenant-a addr add 192.168.100.10/24 dev veth-tA
ip -netns tenant-a link set veth-tA up
ip -netns tenant-a link set lo up

ip -netns tenant-b addr add 192.168.100.20/24 dev veth-tB
ip -netns tenant-b link set veth-tB up
ip -netns tenant-b link set lo up

log "6. Menjalankan Uji Konektivitas Overlay L2..."
ip netns exec tenant-a ping -c 4 192.168.100.20

log "7. Menampilkan Enkapsulasi Header dengan Inspeksi FDB Bridge:"
ip netns exec ns-underlay-1 bridge fdb show dev vxlan-vni1000

log "\033[1;34m[LAB BERHASIL DI-DEPLOY]\033[0m"
echo "Untuk menghapus seluruh lab, jalankan: "
echo "ip netns del ns-underlay-1 && ip netns del ns-underlay-2 && ip netns del tenant-a && ip netns del tenant-b"
```

---

### 13. Exercise

#### Level Easy
1. Dari praktikum di atas, periksa nilai MTU antarmuka `veth-tA`, `br-vni1000`, dan `vxlan-vni1000`.
2. Kirim paket ping dari `tenant-a` ke `tenant-b` dengan payload ukuran penuh tanpa fragmentasi menggunakan perintah:
   ```bash
   ip netns exec tenant-a ping -s 1472 -M do 192.168.100.20
   ```
   Amati apakah ping berhasil. Jika gagal, turunkan parameter `-s` hingga paket tembus, lalu hitung total overhead byte yang hilang!

#### Level Medium
1. Ubah konfigurasi `setup_vxlan_lab.sh` di atas agar tidak lagi menggunakan mode unicast point-to-point (`remote 172.16.0.2`), melainkan menggunakan skema Multicast Underlay (`group 239.1.1.1 dev veth-core1`).
2. Tangkap paket pada interface underlay `veth-core1` menggunakan `tcpdump` saat ping overlay sedang berjalan:
   ```bash
   ip netns exec ns-underlay-1 tcpdump -nn -vv -i veth-core1
   ```
   Tunjukkan field *Outer UDP Destination Port*, *VNI Value*, dan *Inner IP Header*.

#### Level Hard
1. Buat satu namespace tambahan bernama `tenant-c` pada `ns-underlay-2` dengan subnet yang berbeda (`192.168.200.30/24`).
2. Rancang konfigurasi Linux Network Namespace agar `tenant-a` (`192.168.100.10/24`) dapat berkomunikasi dengan `tenant-c` (`192.168.200.30/24`) melalui skema **Symmetric IRB**.
3. Implementasikan *L3 Transit VNI* (misal VNI 50000) dan *VRF definition* di dalam namespace `ns-underlay-1` dan `ns-underlay-2` menggunakan perintah CLI native `iproute2`.

---

### 14. Challenge

**Skenario**:
Sebuah perusahaan e-commerce fintech sedang memigrasikan database transaksi core dari bare-metal cluster lama ke infrastruktur private cloud baru.
*   **Kondisi Awal**: Database lama berada di Subnet L2 `10.50.100.0/24`. Server database tidak boleh mengubah alamat IP karena ribuan legacy microservices meng-hardcode alamat IP database tersebut.
*   **Masalah Arsitektur**: Pusat data baru menggunakan fabric Leaf-Spine IP Clos murni Layer-3 dengan MTU default 1500 bytes. Saat database baru dihidupkan di DC baru dan dihubungkan via VXLAN overlay point-to-point trans-DC:
    *   Query transaksi SQL berukuran kecil (`SELECT 1`) berjalan sukses dan instan.
    *   Query laporan keuangan yang mengembalikan payload transaksi besar (misal batch data 50 MB) langsung mengalami **hang / connection freeze / read timeout**.
    *   Load testing menunjukkan retransmisi TCP melonjak hingga 45%, sementara Utilisasi CPU firewall perimeter melonjak drastis hingga 98% dengan log SoftIRQ tinggi.

**Tugas Rekayasa**:
1. Lakukan audit arsitektural menyeluruh dan dokumentasikan hipotesis ilmiah mengapa query berukuran kecil sukses, namun query payload besar membeku total.
2. Identifikasi potensi masalah spesifik pada interaksi antara MTU, TCP MSS Clamping, dan fragmentasi IP pada paket enkapsulasi.
3. Rancang arsitektur remediasi jaringan produksi tanpa memerlukan reboot server database dan tanpa downtime aplikasi. Berikan urutan instruksi perintah shell, konfigurasi MTU, dan modifikasi kernel sysctl yang harus dieksekusi secara presisi di seluruh interface terkait.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. **Berapa ukuran total byte minimum overhead enkapsulasi standar untuk paket VXLAN (termasuk outer Ethernet, IP, UDP, dan header VXLAN)?**
   * A. 14 bytes
   * B. 32 bytes
   * C. 50 bytes
   * D. 64 bytes
   * *Jawaban:* C
   * *Rasional:* Outer Ethernet (14) + Outer IPv4 (20) + Outer UDP (8) + VXLAN Header (8) = 50 bytes. Jika menggunakan VLAN outer tag, bertambah 4 byte (total 54 bytes).

2. **Subsystem kernel Linux manakah yang bertugas menggabungkan beberapa segmen paket TCP yang masuk menjadi satu payload besar sebelum diproses oleh stack protokol jaringan?**
   * A. TSO (TCP Segmentation Offload)
   * B. GRO (Generic Receive Offload)
   * C. RSS (Receive Side Scaling)
   * D. Netfilter Conntrack
   * *Jawaban:* B
   * *Rasional:* GRO (Generic Receive Offload) beroperasi pada ingress (RX) untuk menggabungkan paket, sedangkan TSO beroperasi pada egress (TX) saat kartu jaringan memecah segmen besar menjadi frame-frame MTU.

3. **Pada penanganan paket tingkat lanjut di Linux, di manakah titik eksekusi program eBPF/XDP berjalan?**
   * A. Di user space di dalam proses aplikasi.
   * B. Tepat pada layer Netfilter POSTROUTING.
   * C. Di layer driver NIC sebelum struktur `sk_buff` dialokasikan oleh kernel.
   * D. Di dalam socket buffer queue aplikasi.
   * *Jawaban:* C
   * *Rasional:* XDP dieksekusi sedini mungkin langsung pada ring buffer driver NIC, memungkinkan pemrosesan paket (termasuk XDP_DROP) sebelum kernel mengalokasikan memori metadata `sk_buff`.

4. **Port UDP standar berapakah yang dialokasikan oleh IANA untuk protokol enkapsulasi VXLAN?**
   * A. 4789
   * B. 8472
   * C. 6081
   * D. 443
   * *Jawaban:* A
   * *Rasional:* RFC 7348 menetapkan port 4789 sebagai port UDP resmi untuk VXLAN. Port 8472 adalah implementasi Linux draft awal sebelum standardisasi IANA. Port 6081 dialokasikan untuk GENEVE.

5. **Apa fungsi utama dari mekanisme `miimon` pada konfigurasi Linux bonding?**
   * A. Menentukan algoritma hash penyeimbang beban link.
   * B. Mengatur interval waktu (dalam milidetik) pengecekan status link fisik menggunakan sinyal carrier MII.
   * C. Menentukan timeout negosiasi LACP PDU.
   * D. Mengatur ukuran buffer antrean ring NIC.
   * *Jawaban:* B
   * *Rasional:* `miimon` (MII link monitoring) menentukan frekuensi inspeksi integritas link hardware oleh kernel dalam satuan milidetik untuk mendeteksi link failure.

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. **Mengapa kebijakan `xmit_hash_policy=layer2` pada Linux LACP bond sangat tidak disarankan untuk antarmuka gateway yang membawa ribuan container via overlay network?**
   * A. Karena enkapsulasi L2 tidak didukung oleh IEEE 802.3ad.
   * B. Karena seluruh paket overlay memiliki MAC tujuan yang sama (MAC gateway), menyebabkan seluruh traffic dialirkan hanya ke satu kabel slave fisik (Polarization).
   * C. Karena layer 2 hashing menyebabkan duplikasi paket IP.
   * D. Karena switch fisik akan memutus session BGP jika MAC address tidak berubah.
   * *Jawaban:* B
   * *Rasional:* Hash `layer2` hanya menghitung XOR dari Source MAC dan Destination MAC. Pada host virtualized di mana traffic keluar menuju next-hop gateway yang sama, nilai hash identik, memicu polarisasi beban 100% pada satu link fisik tunggal.

7. **Dalam arsitektur EVPN-VXLAN, rute BGP EVPN tipe berapakah yang digunakan untuk mempropagasi MAC address dan IP address host secara bersamaan (Host MAC-IP Advertisement)?**
   * A. Type 1 (Ethernet Auto-Discovery)
   * B. Type 2 (MAC/IP Advertisement)
   * C. Type 3 (Inclusive Multicast Ethernet Tag)
   * D. Type 5 (IP Prefix Route)
   * *Jawaban:* B
   * *Rasional:* BGP EVPN Type-2 membawa informasi MAC dan IP host lokal untuk didistribusikan ke seluruh VTEP di fabric. Type-5 digunakan untuk advertensi network prefix L3 murni.

8. **Apa yang terjadi secara internal di Linux kernel saat metrik `/proc/sys/net/netfilter/nf_conntrack_count` mencapai nilai `/proc/sys/net/netfilter/nf_conntrack_max`?**
   * A. Kernel secara otomatis mengalokasikan memori swap untuk menampung koneksi baru.
   * B. Paket data yang tidak terdaftar dalam state table langsung di-drop, dan log kernel mencatat "table full, dropping packet".
   * C. Kernel menghentikan eksekusi BGP daemon seketika.
   * D. Kernel mengalihkan koneksi ke mode promiscuous secara transparan.
   * *Jawaban:* B
   * *Rasional:* Jika tabel conntrack penuh, kernel menolak membuat state baru dan melakukan *hard drop* pada paket koneksi baru (TCP SYN), memicu kegagalan koneksi massal di aplikasi.

9. **Keunggulan arsitektur Symmetric IRB dibandingkan Asymmetric IRB dalam EVPN-VXLAN skala hyperscale adalah:**
   * A. Tidak membutuhkan konfigurasi underlay routing IP murni.
   * B. Menghilangkan kebutuhan alokasi Router MAC pada ingress switch.
   * C. Setiap leaf switch hanya perlu mengonfigurasi dan memetakan L2 VNI lokal yang aktif di switch tersebut, menghemat tabel forwarding TCAM.
   * D. Latensi symmetric IRB selalu 50% lebih rendah dibanding asymmetric IRB.
   * *Jawaban:* C
   * *Rasional:* Pada symmetric IRB, routing antar-VNI dilakukan melalui L3 Transit VNI netral. Leaf tujuan tidak perlu di-provisioning dengan VNI sumber, sehingga tabel MAC dan VNI leaf tidak meledak (*TCAM exhaustion*).

10. **Ketika parameter `net.core.netdev_budget` habis dalam satu loop SoftIRQ NAPI, indikator metrik manakah pada `/proc/net/softnet_stat` yang akan mengalami kenaikan counter?**
    * A. Kolom 1 (Total frames)
    * B. Kolom 2 (Out-of-quota / Squeezed frames)
    * C. Kolom 3 (Dropped frames)
    * D. Kolom 4 (Collision counters)
    * *Jawaban:* B
    * *Rasional:* Kolom ke-2 mencatat status "squeeze", yaitu frekuensi di mana kernel poll loop terpaksa melepaskan CPU sebelum antrean benar-benar kosong karena jatah budget/time-slice habis.

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario 1**: Sebuah cluster server Linux mengalami bottleneck throughput jaringan tinggi (10 Gbps) di mana satu core CPU (`CPU 0`) menunjukkan pemanfaatan 100% pada metrik `%si` (SoftIRQ), sementara core CPU lainnya berada di 0%. Jelaskan akar masalahnya dan tuliskan dua perintah Linux untuk mendistribusikan beban tersebut secara permanen ke seluruh core!
    *   *Analisis Solusi*: Masalah disebabkan oleh pemrosesan hardware interrupts NIC yang terkunci (*pinned*) pada satu core CPU tunggal akibat tidak berjalannya mekanisme RSS (*Receive Side Scaling*) atau daemon irqbalance.
    *   *Remediasi*:
        1. Aktifkan penyeimbangan interrupt multi-queue:
           ```bash
           systemctl enable --now irqbalance
           ```
        2. Alokasikan queue NIC ke seluruh core atau gunakan RPS (*Receive Packet Steering*) jika NIC tidak mendukung multi-queue hardware:
           ```bash
           # Mengaktifkan RPS pada seluruh core (misal 8-core CPU = mask 'ff')
           echo "ff" > /sys/class/net/eth0/queues/rx-0/rps_cpus
           ```

12. **Skenario 2**: Dua VTEP EVPN-VXLAN berhasil membentuk BGP peering, dan rute Type-2 MAC/IP terdistribusi sempurna. Namun, saat dua container di subnet yang sama melakukan ping, transmisi ARP request (`who-has`) tidak pernah mendapatkan jawaban (ARP timeout), meskipun sniffing paket menunjukkan ARP frame keluar dari container sumber. Di manakah titik kegagalan yang paling mungkin terjadi?
    *   *Analisis Solusi*:
        1. Kegagalan propagasi BGP EVPN Type-3 Route (*Inclusive Multicast Ethernet Tag Route*) atau miskonfigurasi ingress replication list pada VTEP ingress. Broadcast ARP membutuhkan replikasi head-end (*ingress replication*) untuk frame BUM (*Broadcast, Unknown Unicast, Multicast*).
        2. Kegagalan isolasi VLAN-to-VNI mapping pada Linux bridge lokal, atau interface VXLAN belum ditambahkan ke bridge domain tempat interface container berada.
        3. Firewall host (iptables/nftables) memblokir traffic UDP masuk port 4789 pada antarmuka underlay VTEP penerima.

13. **Skenario 3**: Sebuah host hypervisor menjalankan 50 VM yang berkomunikasi ke storage cluster Ceph melalui jaringan VXLAN. Saat proses backup berjalan, terjadi *throughput collapse* (kecepatan anjlok dari 10 Gbps ke 50 Kbps) dengan ribuan pesan error *TCP Dup ACK* dan *TCP Fast Retransmission*. Nilai MTU underlay adalah 1500, dan MTU VM disetel 1500. Analisis apa yang terjadi dan solusinya!
    *   *Analisis Solusi*: Terjadi fenomena **Path MTU Discovery (PMTUD) Black Hole**. Enkapsulasi VXLAN menambahkan overhead 50 bytes sehingga ukuran total frame menjadi 1550 bytes. Karena underlay MTU hanya 1500, frame berukuran penuh yang dikirim VM (1500 bytes IP payload) harus difragmentasi. Karena flag DF (*Don't Fragment*) aktif pada paket TCP Ceph dan router underlay memblokir/men-drop paket tanpa fragmentasi tanpa mengirimkan kembali pesan ICMP Type 3 Code 4, VM pengirim tidak pernah tahu bahwa paket di-drop. VM terus mengirimkan segmen besar yang selalu di-drop secara diam-diam.
    *   *Remediasi*:
        1. Solusi ideal: Ubah MTU jaringan underlay (switch, router, physical NIC) menjadi MTU Jumbo (misal 9000 bytes).
        2. Solusi taktis (jika underlay di luar kendali): Ubah MTU vNIC VM menjadi 1450 bytes, ATAU pasang aturan iptables MSS Clamping pada VTEP ingress:
           ```bash
           iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
           ```

---

### 16. Summary

*   Pemrosesan paket modern di Linux telah berevolusi dari model interrupt-driven konvensional menjadi model polling terakselerasi via NAPI, ring buffer tuning, hingga programmable datapath berbasis **XDP/eBPF** yang melewati (*bypass*) overhead Netfilter dan `sk_buff`.
*   Arsitektur pusat data masa kini bertumpu pada topologi **Leaf-Spine L3 Underlay** deterministik yang memanfaatkan BGP Unnumbered dan ECMP, menghilangkan kelemahan mendasar protokol Spanning Tree (STP).
*   **EVPN-VXLAN** berfungsi sebagai standard de-facto untuk overlay network enterprise multi-tenant. Penggunaan **Symmetric IRB** memberikan skalabilitas superior dibanding Asymmetric IRB dengan mengisolasi kebutuhan entri TCAM ke tingkat lokal melalui pemanfaatan L3 Transit VNI.
*   Reliabilitas jaringan berkinerja tinggi mensyaratkan mitigasi terhadap tiga bottleneck utama:
    1.  *Overhead Enkapsulasi* yang menuntut konfigurasi MTU Underlay Jumbo (>= 1600/9000 bytes) guna mencegah PMTUD Black Hole.
    2.  *Connection Tracking Exhaustion* yang menuntut pemangkasan timeout TCP atau migrasi ke socket datapath eBPF.
    3.  *Hash Polarization & CPU Core Imbalance* yang diatasi melalui penerapan LACP `layer3+4` dan tuning RSS/RPS multi-queue.