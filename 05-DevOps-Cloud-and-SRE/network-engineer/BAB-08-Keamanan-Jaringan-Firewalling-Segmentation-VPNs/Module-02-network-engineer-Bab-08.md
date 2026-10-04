# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Keamanan Jaringan, Segmentasi, & Enterprise VPN

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal/Senior Network Engineer dan SRE diharapkan mampu:
- **Menganalisis & Mengoptimalkan Kernel Conntrack**: Menjelaskan siklus hidup *state tracking* TCP/UDP pada subsistem Netfilter Linux dan mengeliminasi bottleneck tabel *connection tracking* pada skala $10^6+$ konkurensi.
- **Merancang Arsitektur Zero Trust & Mikrosegmentasi**: Mengonstruksi kebijakan segmentasi granular pada *Data Center Fabric* menggunakan kombinasi EVPN-VXLAN Group-Based Policies (GBP) dan Kubernetes CNI berbasis eBPF (Cilium NetworkPolicy).
- **Mengimplementasikan Route-Based IPSec & WireGuard Berskala Enterprise**: Membangun topologi *High-Availability Site-to-Site VPN* aktif/aktif menggunakan Route-Based IPSec (Virtual Tunnel Interface/VTI) yang diintegrasikan dengan BGP (*Border Gateway Protocol*) dan BFD (*Bidirectional Forwarding Detection*), serta arsitektur modern WireGuard *mesh*.
- **Memitigasi Masalah Kriptografi & MTU/MSS**: Melakukan kalkulasi matematis terhadap *packet overhead* (IPSec ESP, WireGuard, VXLAN) dan menerapkan teknik *dynamic MSS clamping* serta *path MTU discovery* (PMTUD) untuk mencegah fragmentasi paket.
- **Mengaudit & Mengatasi Stateful Firewall Failures**: Mendiagnosis degradasi performa akibat *asymmetric routing*, *out-of-window packet drops*, dan kegagalan sinkronisasi *state* pada klaster *Next-Generation Firewall* (NGFW).

---

## 2. Prerequisites
Sebelum mendalami modul ini, peserta diwajibkan memiliki pemahaman mendalam pada:
- **Protokol Inti TCP/IP**: Analisis *header* L3/L4, *TCP 3-way handshake*, penutupan koneksi (`FIN`/`RST`), *windowing*, dan *sequence numbers*.
- **Routing Dinamis Lanjut**: Konfigurasi dan konvergensi BGP (eBGP, iBGP, *address families*, *route-reflectors*).
- **Dasar Linux Networking & Kernel**: Penggunaan `iproute2`, `iptables`/`nftables`, serta kompilasi dasar modul kernel Linux.
- **Kriptografi Terapan**: Konsep *symmetric encryption* (AES-GCM, ChaCha20-Poly1305), *asymmetric key exchange* (Diffie-Hellman, ECDH/Curve25519), dan PKI (X.509 certificates).

---

## 3. Concept & Internal Architecture

### 3.1. Netfilter & Connection Tracking (`nf_conntrack`) Deep Dive
Subsistem `nf_conntrack` pada kernel Linux bertugas memantau status koneksi L3/L4 secara *stateful*. Paket yang melintasi *network stack* diklasifikasikan ke dalam tuple identitas 5-elemen (5-tuple): 

$$\text{Tuple} = \{\text{Src IP}, \text{Dst IP}, \text{Src Port}, \text{Dst Port}, \text{Protocol}\}$$

```
+-----------------------------------------------------------------------------+
|                               Linux Kernel                                  |
|                                                                             |
| [Ingress: eth0]                                                             |
|        |                                                                    |
|        v                                                                    |
|  +-----------+     +-------------------+     +---------------------------+  |
|  |  PREROUTE | --> |  nf_conntrack_in  | --> | Routing Decision (L3 FIB) |  |
|  +-----------+     +-------------------+     +---------------------------+  |
|                             |                              |                |
|                    [Tuple Hash Lookup]                     |                |
|                             |                              v                |
|                 +-----------v-----------+         +-----------------+       |
|                 | conntrack Hash Table  |         |      INPUT      |       |
|                 |   (Double-linked list)|         +-----------------+       |
|                 +-----------------------+                  |                |
|                                                            v                |
|                                                   +-----------------+       |
|                                                   |   Local Process |       |
|                                                   +-----------------+       |
|                                                            |                |
|  +------------+     +------------------+                   v                |
|  | POSTROUTE  | <-- | conntrack_confirm| <-------- +-----------------+       |
|  +------------+     +------------------+          |     OUTPUT      |       |
|        |                                           +-----------------+       |
|        v                                                   |                |
|  [Egress: eth1] <------------------+-----------------------+                |
|                                    | (Forward path)                         |
|                             +------v------+                                 |
|                             |   FORWARD   |                                 |
|                             +-------------+                                 |
+-----------------------------------------------------------------------------+
```

#### Struktur Data Hash Table Conntrack
Kernel mengalokasikan tabel hash berukuran tetap yang ditentukan oleh `net.netfilter.nf_conntrack_buckets`. Setiap *bucket* berisi *doubly-linked list* dari struktur `struct nf_conn`.

```c
struct nf_conntrack_tuple {
    struct nf_conntrack_man src;
    struct {
        union nf_inet_addr u3;
        union {
            __be16 all;
            struct { __be16 port; } tcp;
            struct { __be16 port; } udp;
            // ...
        } u;
        u_int8_t protonum;
        u_int8_t dir;
    } dst;
};

struct nf_conn {
    struct nf_conntrack_tuple_hash tuplehash[IP_CT_DIR_MAX]; // 0: Original, 1: Reply
    unsigned long status;
    possible_net_t ct_net;
    struct timer_list timeout;
    // Layer 4 specific state (e.g., TCP state machine)
    union nf_conntrack_proto proto;
};
```

#### State Machine TCP pada Conntrack
Conntrack melacak *finite state machine* (FSM) TCP secara independen dari stack socket lokal:
1. **`SYN_SENT`**: Paket TCP pertama dengan flag `SYN` diterima. Conntrack mencatat arah *ORIGINAL*. Timeout: ~120 detik.
2. **`SYN_RECV`**: Paket balasan `SYN-ACK` diterima dari arah *REPLY*.
3. **`ESTABLISHED`**: Paket `ACK` final dari handshake diterima. Timeout default: 432.000 detik (5 hari).
4. **`FIN_WAIT` / `CLOSE_WAIT` / `TIME_WAIT`**: Transisi penutupan koneksi. Pada status `TIME_WAIT`, timeout diatur ketat (default 120 detik) untuk mencegah penggunaan ulang tuple sebelum paket lawas musnah (*linger removal*).

---

### 3.2. Route-Based IPSec Architecture (VTI/XFRM)
Model IPSec terbagi menjadi dua paradigma: **Policy-Based** dan **Route-Based**.

```
[Policy-Based IPSec (SPDB Matching)]
Packet Ingress -> L3 Routing -> Policy Match (XFRM SPD) -> ESP Encapsulation -> Interface Egress
*Kelemahan: Tidak ada interface logis, routing dinamis (BGP/OSPF) mustahil tanpa GRE over IPSec.*

[Route-Based IPSec (VTI / XFRM Interfaces)]
Packet Ingress -> L3 Routing -> Route to "vti0" / "xfrm0" -> Driver xfrm_output() -> ESP Encapsulation -> Egress
*Keunggulan: Interface virtual L3 murni, dapat dipasangi IP, MTU mandiri, dan integrasi penuh dengan BGP/BFD.*
```

#### Komponen Kriptografi & Transformasi Paket IPSec
- **IKEv2 (Internet Key Exchange v2)**: Bekerja pada port UDP 500/4500. Menggunakan protokol Diffie-Hellman berbasis kurva eliptis (misal Curve25519 / Group 31) untuk menghasilkan *Security Association* (SA) berorientasi *ephemeral*.
- **ESP (Encapsulating Security Payload - IP Protocol 50)**:
  - Header ESP: SPI (Security Parameters Index - 32 bit), Sequence Number (32/64 bit).
  - Payload: Data terenkripsi (L4 Header + Data).
  - ESP Trailer: Padding, Pad Length, Next Header.
  - ESP ICV (Integrity Check Value): Otentikasi kriptografis menggunakan algoritma AEAD (Authenticated Encryption with Associated Data) seperti AES-256-GCM.

---

### 3.3. WireGuard Cryptokey Routing & Kernel Path
WireGuard beroperasi langsung di dalam kernel space Linux (`drivers/net/wireguard/`) menggunakan konsep **Cryptokey Routing**.
- Setiap *interface* WireGuard memiliki *private key* dan *listening port* (UDP).
- Setiap *peer* didefinisikan oleh *public key* (Curve25519) dan daftar prefiks jaringan yang diizinkan (`AllowedIPs`).
- **Asosiasi Kriptografis Statis**: Ketika paket dikirim ke interface `wg0`, kernel mencari kecocokan alamat IP tujuan pada tabel prefiks `AllowedIPs`. Jika cocok, paket dienkripsi langsung menggunakan *shared key* peer tersebut via Noise Protocol Framework (Noise_IKpsk2).

```
Kernel Routing Table           WireGuard Interface (wg0)           Physical NIC
[Dst: 10.200.0.5] ----> (Dev: wg0) ----> [Cryptokey Table Lookup] 
                                                  |
                                                  v
                                     Matched Peer: Public Key "X"
                                     AllowedIPs: 10.200.0.0/24
                                     Endpoint: 203.0.113.10:51820
                                                  |
                                                  v
                                     Noise Encapsulation (ChaCha20-Poly1305)
                                                  |
                                                  v
                                     Outer UDP Packet Egress ----> [Physical Network]
```

---

## 4. Why & What

### 4.1. Perbandingan Paradigma Keamanan Jaringan

| Parameter | Traditional Perimeter Firewall (Perimeter-only) | Microsegmentation (Overlay / EVPN / eBPF) | Zero Trust Network Access (ZTNA) |
| :--- | :--- | :--- | :--- |
| **Trust Model** | Implisit (*Trust Inside, Untrust Outside*) | Eksplisit per *Workload* / *Pod* | Eksplisit per Sesi, Identitas, & Perangkat |
| **Enforcement Point** | L3 Edge/Perimeter Gateway | Virtual Switch (vSwitch), Kernel eBPF, ToR Switch | Application Gateway / Client Agent |
| **Skalabilitas State** | Sentralisasi, rentan *conntrack exhaustion* | Terdistribusi di host kernel masing-masing | Terdistribusi via Edge Proxies |
| **Visibilitas** | Terbatas pada arus *North-South* | Menyeluruh (*North-South* & *East-West*) | Layer 7 konteks pengguna & resource |
| **Blast Radius** | Sangat besar saat terjadi *lateral movement* | Terisolasi pada level mikro (*pod/container*) | Terisolasi pada spesifik API endpoint |

### 4.2. Mengapa Menggantikan Policy-Based IPSec dengan Route-Based VTI/WireGuard?
1. **Konvergensi Dinamis**: Policy-Based IPSec mengandalkan Security Policy Database (SPD) statis. Menambahkan subnet baru menuntut negosiasi ulang IKE SA pada kedua belah pihak. Route-Based hanya membutuhkan pengumuman rute via BGP.
2. **Ketersediaan Jalur Ganda (ECMP & Failover)**: Dengan VTI, kita dapat menjalankan protokol BFD dengan interval milidetik ($3 \times 100\text{ ms} = 300\text{ ms}$ failover time), mendeteksi *silent blackhole* secara instan.
3. **Reduksi Kompleksitas Aturan**: Routing engine menangani pemilihan jalur; kripto engine hanya menangani enkapsulasi/dekapsulasi.

---

## 5. How: Workflow Detail

### 5.1. Alur Pemrosesan Paket pada Route-Based IPSec (VTI)

```
             PACKET TRANSMISSION (TX) PATH
             ==============================
                      [Application]
                            |
                            v
                      [TCP/UDP Stack]
                            |
                            v
              [FIB Routing: Dst matches vti0]
                            |
                            v
                     [Interface: vti0]
                            |
              (Assign xfrm state based on VTI-Key)
                            |
                            v
                     [XFRM Output Path]
        - Lookup Security Association (SA)
        - Encrypt Payload (AES-256-GCM)
        - Append ESP Header & Trailer
        - Generate Authentication Tag (ICV)
                            |
                            v
               [Encapsulated IP Packet: ESP]
               (Src: Ext_IP_A, Dst: Ext_IP_B)
                            |
                            v
          [Outer Routing Lookup -> Physical NIC]
                            |
                            v
                    [Physical Wire Out]
```

### 5.2. Handshake NoiseIK pada WireGuard

```
Initiator (Client)                                   Responder (Gateway)
==================                                   ===================
Generates ephemeral key (e_i)
Calculates DH ratchet with Responder static (s_r)
Symmetric AEAD encrypts timestamp
                               msg 1: Type 1
               --------------------------------------------->
               ephemeral (e_i) || unencrypted auth tag
                                                     Generates ephemeral key (e_r)
                                                     Calculates DH ratchet with e_i and s_i
                                                     Symmetric AEAD encrypts empty payload
                               msg 2: Type 2
               <---------------------------------------------
               ephemeral (e_r) || auth tag
Derives Transmit/Receive Keys                         Derives Transmit/Receive Keys
(No further handshake required for bidirectional encrypted traffic)
```

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi Conntrack vs Stateless
Bayangkan sebuah bandara internasional:
- **Stateless Firewall**: Satpam yang hanya memeriksa dokumen identitas setiap orang yang lewat di setiap pintu secara terisolasi tanpa mengingat siapa yang sudah masuk. Jika pintu masuk diizinkan tapi pintu keluar tidak memiliki aturan tertulis yang sama persis, orang tersebut tidak bisa kembali.
- **Stateful (Conntrack)**: Petugas imigrasi yang mencatat data paspor di buku induk ketika Anda berangkat (*ORIGINAL*), memberi cap status visa aktif (*ESTABLISHED*), dan ketika Anda kembali (*REPLY*), ia hanya mencocokkan nomor paspor dengan data kepulangan tanpa perlu memverifikasi ulang dari nol.

### 6.2. Topologi Arsitektur Produksi Hybrid-Cloud High-Availability

```
   ====================== ON-PREMISE ENTERPRISE DC ======================
   +-------------------------------------------------------------------+
   |                    Core Layer-3 Switch Fabric                     |
   +-------------------------------------------------------------------+
         | (10G Trunk)                                   | (10G Trunk)
   +-----v----------------------+                 +------v---------------------+
   | Edge-GW-01 (strongSwan/FRR)|                 | Edge-GW-02 (strongSwan/FRR)|
   | Public IP: 198.51.100.1    |                 | Public IP: 198.51.100.2    |
   | Local VTI: 10.254.0.1/30   |                 | Local VTI: 10.254.0.5/30   |
   +----------------------------+                 +----------------------------+
         |                                               |
         | IPSec Tunnel A (BGP ASN 65001)                | IPSec Tunnel B (BGP ASN 65001)
         |                                               |
~~~~~~~~~v~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~v~~~~~~~~~~~~~~~~~~~~~~~~
                                  INTERNET / WAN
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
         |                                               |
         | BGP Session over VTI                          | BGP Session over VTI
         |                                               |
   +-----v----------------------+                 +------v---------------------+
   | AWS VGW / Transit Gateway  |                 | AWS VGW / Transit Gateway  |
   | Endpoint A: 203.0.113.10   |                 | Endpoint B: 203.0.113.11   |
   | Remote VTI: 10.254.0.2/30  |                 | Remote VTI: 10.254.0.6/30  |
   | BGP ASN: 64512             |                 | BGP ASN: 64512             |
   +----------------------------+                 +----------------------------+
   |                        AWS TRANSIT GATEWAY (TGW)                          |
   +---------------------------------------------------------------------------+
                                  | Attachment
                    +-------------v-------------+
                    | VPC Production (EKS Core) |
                    | CIDR: 172.24.0.0/16       |
                    +---------------------------+
```

---

## 7. Practical Implementation

### 7.1. Kernel Tuning untuk High-Throughput Stateful Inspection
Simpan pada `/etc/sysctl.d/99-network-security-perf.conf`:

```ini
# Meningkatkan batas maksimum tabel conntrack (2 Juta Koneksi)
net.netfilter.nf_conntrack_max = 2097152

# Menyesuaikan ukuran bucket hash table conntrack (nf_conntrack_max / 4)
# Harus diinjeksikan lewat modprobe: options nf_conntrack hashsize=524288
net.netfilter.nf_conntrack_buckets = 524288

# Reduksi TCP Timeout untuk mempercepat daur ulang memory table
net.netfilter.nf_conntrack_tcp_timeout_established = 43200
net.netfilter.nf_conntrack_tcp_timeout_syn_recv = 15
net.netfilter.nf_conntrack_tcp_timeout_fin_wait = 30
net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30
net.netfilter.nf_conntrack_tcp_timeout_close_wait = 15

# Aktifkan penolakan paket TCP Out-of-Window
net.netfilter.nf_conntrack_tcp_be_liberal = 0

# Proteksi terhadap SYN Flood (Cookie activation)
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 16384

# Hindari MTU blackhole dengan Dynamic Path MTU Discovery
net.ipv4.ip_no_pmtu_disc = 0

# Aktifkan IP Forwarding untuk router/firewall
net.ipv4.ip_forward = 1
```

### 7.2. Enterprise Stateful Firewall dengan `nftables`
Konfigurasi file `/etc/nftables.conf`:

```nftables
#!/usr/sbin/nft -f

flush ruleset

table inet filter {
    # Definisi Set untuk Jaringan Tepercaya
    set corporate_management {
        type ipv4_addr
        flags interval
        elements = { 10.100.0.0/16, 172.16.50.0/24 }
    }

    # Definisi Dynamic Set untuk Rate Limiting ICMP
    set ratelimit_icmp {
        type ipv4_addr
        size 65535
        flags dynamic
    }

    chain input {
        type filter hook input priority filter; policy drop;

        # 1. Loopback Interface
        iif "lo" accept

        # 2. Connection Tracking: Status Valid
        ct state established,related accept
        ct state invalid log prefix "[NFT-INVALID-IN]: " drop

        # 3. Mitigasi TCP Flag Anomali
        tcp flags & (fin|syn) == fin|syn drop
        tcp flags & (syn|rst) == syn|rst drop
        tcp flags & (fin|rst) == fin|rst drop
        tcp flags & (fin|syn|rst|psh|ack|urg) == 0 drop

        # 4. ICMP Handling yang aman dengan Rate Limit
        icmp type { echo-request, destination-unreachable, time-exceeded } \
            meter flood_icmp { ip saddr limit rate 5/second } accept
        icmp type echo-request drop

        # 5. Layanan Infrastruktur Terbuka
        # BGP: Hanya diizinkan dari Peer Terdaftar
        ip saddr { 198.51.100.2, 203.0.113.10 } tcp dport 179 accept

        # IPSec IKE/NAT-T
        udp dport { 500, 4500 } accept
        ip protocol esp accept

        # WireGuard
        udp dport 51820 accept

        # SSH Management dari Subnet Khusus
        ip saddr @corporate_management tcp dport 22 accept

        # Log & Counter untuk observabilitas sebelum drop
        counter log prefix "[NFT-INPUT-REJECT]: " level warn drop
    }

    chain forward {
        type filter hook forward priority filter; policy drop;

        # Izinkan paket yang telah tervalidasi state-nya
        ct state established,related accept
        ct state invalid log prefix "[NFT-INVALID-FWD]: " drop

        # Clamp TCP MSS ke Path MTU pada segment terenkripsi (Tunneling Overhead)
        tcp flags syn tcp option maxseg size set rt mtu

        # Microsegmentation Policy: DC App -> Database
        ip saddr 10.200.10.0/24 ip daddr 10.200.20.0/24 tcp dport 5432 accept

        # Drop & Log sisanya
        counter drop
    }

    chain postrouting {
        type filter hook postrouting priority srcnat; policy accept;
    }
}
```

### 7.3. Konfigurasi Route-Based IPSec (strongSwan + VTI Script)
File `/etc/strongswan/swanctl/conf.d/ipsec-aws-tgw.conf`:

```ini
connections {
    aws-tgw-tunnel1 {
        local_addrs = 198.51.100.1
        remote_addrs = 203.0.113.10
        version = 2
        proposals = aes256gcm128-prfsha256-ecp256
        rekey_time = 28800s
        dpd_delay = 10s
        dpd_timeout = 30s

        local {
            auth = psk
            id = 198.51.100.1
        }
        remote {
            auth = psk
            id = 203.0.113.10
        }

        children {
            vti-tunnel1 {
                # 0.0.0.0/0 mencakup semua lalu lintas untuk perutean berbasis VTI
                local_ts = 0.0.0.0/0
                remote_ts = 0.0.0.0/0
                esp_proposals = aes256gcm128-ecp256
                rekey_time = 3600s
                # Mark VTI diikat dengan fwmark kernel
                mark_in = 42
                mark_out = 42
                updown = /usr/local/sbin/ipsec-vti.sh vti1 10.254.0.1 10.254.0.2 42
                mode = tunnel
            }
        }
    }
}

secrets {
    ike-aws-1 {
        id-1 = 203.0.113.10
        secret = "K7s#fL9v!xQ2rZ@4mP9wE8jT3yB1uN6o"
    }
}
```

Script otomasi inisialisasi interface VTI `/usr/local/sbin/ipsec-vti.sh`:

```bash
#!/bin/bash
set -euo pipefail

VTI_IF="${1}"
LOCAL_TUN_IP="${2}"
REMOTE_TUN_IP="${3}"
VTI_MARK="${4}"

case "${PLUTO_VERB}" in
    up-client)
        # Hapus interface lama bila eksis akibat renegosiasi parsial
        ip link delete "${VTI_IF}" 2>/dev/null || true
        
        # Buat interface VTI dengan encapsulation GRE-less IPSec
        ip link add "${VTI_IF}" type vti key "${VTI_MARK}"
        ip addr add "${LOCAL_TUN_IP}/30" peer "${REMOTE_TUN_IP}" dev "${VTI_IF}"
        
        # Perhitungan MTU: 1500 - 20 (IP Outer) - 8 (UDP-NAT-T) - 32 (ESP) - 16 (IV/ICV) = 1424
        ip link set "${VTI_IF}" mtu 1424
        ip link set "${VTI_IF}" up
        
        # Nonaktifkan rp_filter pada VTI untuk mencegah drop asymmetric routing
        sysctl -w "net.ipv4.conf.${VTI_IF}.rp_filter=0"
        sysctl -w "net.ipv4.conf.${VTI_IF}.disable_policy=1"
        ;;
    down-client)
        ip link delete "${VTI_IF}" || true
        ;;
esac
```

### 7.4. Integrasi BGP & BFD via FRRouting (`/etc/frr/frr.conf`)
Menjalankan failover sub-detik antar tunnel VTI:

```frr
frr version 8.5_git
frr defaults traditional
hostname enterprise-core-edge01
log syslog informational
service integrated-vtysh-config
!
interface vti1
 ip router openfabric 1
 bfd interval 100 min_rx 100 multiplier 3
!
router bgp 65001
 bgp router-id 198.51.100.1
 neighbor 10.254.0.2 remote-as 64512
 neighbor 10.254.0.2 bfd
 neighbor 10.254.0.2 timers 3 9
 neighbor 10.254.0.2 description "AWS-Transit-Gateway-Tunnel1"
 !
 address-family ipv4 unicast
  network 10.100.0.0/16
  neighbor 10.254.0.2 activate
  neighbor 10.254.0.2 soft-reconfiguration inbound
 exit-address-family
!
line vty
!
```

---

## 8. Real World Case Study: PCI-DSS Segmented Hybrid Infrastructure

### 8.1. Arsitektur Masalah
Institusi Financial Payment Gateway memproses jutaan transaksi harian. Arsitektur hybrid menghubungkan *On-Prem Bare Metal Data Center* dengan *AWS Cloud Infrastructure*.
- **Kendala Kritis**:
  1. Audit PCI-DSS v4.0 mewajibkan ruang lingkup Cardholder Data Environment (CDE) diisolasi secara kriptografis dan jaringan (mikrosegmentasi total).
  2. Firewall perimeter lama mengalami *state exhaustion* (conntrack drop) saat lonjakan transaksi e-commerce, menyebabkan *TCP resets* pada payment gateway.
  3. Failover IPSec lama memakan waktu 40-60 detik (mengandalkan DPD timeout standar), melanggar SLA ketersediaan 99.999%.

```
                        [PCI-DSS SCOPE DIVISION]
                      
         +----------------------------------------------------+
         |                 Non-CDE Zone (VPC)                 |
         |         Corporate Management, Reporting Tools      |
         +----------------------------------------------------+
                                   |
         ================== FIREWALL ENFORCEMENT ============= (Drop Lateral Traffic)
                                   |
         +----------------------------------------------------+
         |                   CDE Zone (EKS)                   |
         |         Cardholder Data & Tokenizer Engines        |
         +----------------------------------------------------+
                                   |
               [eBPF Cilium Strict Ingress/Egress Isolation]
                                   |
         [Dual Active-Active VTI IPSec Tunnel with BGP + BFD]
                                   |
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~v~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                          AWS Transit Gateway
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                                   |
               [VTI-1: Sub-sec BFD] [VTI-2: Standby ECMP]
                                   |
         +-------------------------v--------------------------+
         |     On-Premises Dedicated Hardware HSM Cluster     |
         +----------------------------------------------------+
```

### 8.2. Solusi Rekayasa
1. **Mikrosegmentasi In-Cluster (Cilium eBPF)**: Menerapkan parsing Layer 7 (HTTP/gRPC) langsung di kernel tanpa iptables. Menghapus ketergantungan `nf_conntrack` untuk komunikasi East-West antar pod CDE.
2. **Kompensasi Stateful Exhaustion**: Mengalihkan NAT stateful di perimeter menjadi *Stateless ECMP Routing* menggunakan eBGP, mengarahkan lalu lintas ke *farm* NGFW berkapasitas 8-node.
3. **Sub-second Tunnel Convergence**: Implementasi BGP dengan BFD over dual-active IPSec VTI, menurunkan failover window dari 60 detik menjadi 300 milidetik ($3 \times 100\text{ ms}$).

### 8.3. Spesifikasi Policy Cilium NetworkPolicy (L7 CDE Isolation)
File `cde-microsegmentation-policy.yaml`:

```yaml
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "enforce-cde-tokenizer-isolation"
  namespace: "pci-cde"
spec:
  endpointSelector:
    matchLabels:
      app: "tokenizer-engine"
  ingress:
    - fromEndpoints:
        - matchLabels:
            app: "payment-api-gateway"
      toPorts:
        - ports:
            - port: "8443"
              protocol: TCP
          rules:
            http:
              - method: "POST"
                path: "^/v2/tokens/tokenize$"
  egress:
    - toEndpoints:
        - matchLabels:
            app: "vault-transit-service"
      toPorts:
        - ports:
            - port: "8200"
              protocol: TCP
    - toCIDR:
        - 10.250.0.10/32 # Dedicated On-Prem Physical HSM IP
      toPorts:
        - ports:
            - port: "1999" # HSM Proprietary RPC
              protocol: TCP
```

---

## 9. Trade-offs: Analisis Karakteristik Performa

```
                     LATENCY VS SECURITY COMPUTATION
Low Latency                                                        High Overhead
<------------------------------------------------------------------------------>
[Raw Routing (No Sec)]   [Stateless ACL]   [WireGuard / eBPF]   [IPSec AES-GCM]   [NGFW DPI + TLS Intercept]
~5 microseconds          ~8 microseconds   ~15 microseconds     ~25 microseconds  ~1.2 miliseconds
0% CPU Overhead          1% CPU Overhead   5% CPU Overhead      12% CPU Overhead  65% CPU Overhead
```

### Analisis Komparasi Kinerja

| Metrik | eBPF XDP Stateless Filter | Netfilter conntrack (Stateful) | WireGuard Tunnel | IPSec (VTI AES-256-GCM) | NGFW Deep Packet Inspection |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Throughput (10Gbps link)** | ~9.8 Gbps (Line Rate) | ~4.2 Gbps | ~7.8 Gbps | ~6.5 Gbps | ~1.1 Gbps |
| **Packets Per Second (PPS)** | 14.2 Mpps | 1.8 Mpps | 3.5 Mpps | 2.1 Mpps | 0.4 Mpps |
| **Enkapsulasi Overhead** | 0 bytes | 0 bytes | 32 bytes (Outer UDP) | 56-72 bytes (ESP/UDP) | 0 bytes (Non-tunneling) |
| **Kerentanan Fragmentasi** | Tidak Ada | Rendah | Sedang (Perlu MTU 1420) | Tinggi (Perlu Clamping) | Sangat Rendah |
| **Biaya Hardware/Compute** | Sangat Rendah | Rendah - Sedang | Rendah | Sedang (AES-NI HW Accel)| Tinggi (CPU Intensive)|

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Conntrack Table Full (`table full, dropping packet`)
- **Gejala**: Kernel log memunculkan pesan kesalahan berulang:
  ```text
  kernel: nf_conntrack: table full, dropping packet
  ```
  Koneksi TCP baru gagal melakukan *handshake* (`SYN` di-drop), koneksi lama terputus mendadak.
- **Investigasi Root-Cause**:
  Periksa kapasitas maksimum dan jumlah entry aktif saat ini:
  ```bash
  cat /proc/sys/net/netfilter/nf_conntrack_count
  cat /proc/sys/net/netfilter/nf_conntrack_max
  ```
  Identifikasi koneksi yang mendominasi tabel (misal serangan DoS atau pooling aplikasi yang cacat):
  ```bash
  conntrack -L -o extended | awk '{print $3, $5}' | sort | uniq -c | sort -nr | head -n 20
  ```
- **Solusi Rekayasa**:
  1. Terapkan flag `NOTRACK` pada `nftables`/`iptables` untuk traffic stateless bervolume raksasa (misal traffic streaming video UDP atau healthcheck internal load balancer).
  2. Naikkan `nf_conntrack_max` dan sesuaikan ukuran hash buckets (`hashsize = nf_conntrack_max / 4`).

### 10.2. MTU Blackhole & Path MTU Discovery Failure
- **Gejala**: Handshake TCP berhasil, curl dengan payload kecil (header-only) berjalan lancar, namun transfer data berukuran besar (misal HTTP POST body besar atau SCP) mengalami *hanging* permanen.
- **Root-Cause**: Tunneling (IPSec/WireGuard/VXLAN) menambahkan header tambahan pada paket IP. Jika paket berukuran 1500 byte ditandai dengan flag `DF=1` (*Don't Fragment*), router tunnel akan membuang paket dan mengirimkan pesan ICMP Type 3 Code 4 (*Destination Unreachable, Fragmentation Needed*). Jika ICMP ini diblokir oleh firewall stateless yang terlalu protektif, pengirim tidak akan pernah menurunkan ukuran paket.
- **Kalkulasi Overhead**:

  $$\text{MTU}_{\text{eff}} = \text{MTU}_{\text{phys}} - (\text{IP}_{\text{outer}} + \text{UDP}_{\text{nat-t}} + \text{ESP}_{\text{header}} + \text{IV} + \text{ICV} + \text{Padding})$$

  $$\text{MTU}_{\text{eff}} = 1500 - (20 + 8 + 8 + 8 + 16 + 16) = 1424 \text{ bytes}$$

- **Solusi**:
  Terapkan MSS Clamping dinamis pada rantai FORWARD firewall gateway:
  ```bash
  nft add rule inet filter forward tcp flags syn tcp option maxseg size set 1384
  ```

### 10.3. Asymmetric Routing Menggagalkan Stateful Inspection
- **Gejala**: Paket masuk melalui `Tunnel A`, namun balasan dikirimkan ISP melalui `Tunnel B`. Firewall pada `Tunnel B` menolak paket dengan tanda status `ct state invalid`.
- **Root-Cause**: `nf_conntrack` pada Node B tidak pernah melihat urutan *SYN ACK* yang sah, sehingga menganggap paket data lanjutan sebagai anomali.
- **Solusi Rekayasa**:
  1. Konfigurasi manipulasi BGP path: Implementasikan *BGP AS Path Prepending* atau *MED* (Multi-Exit Discriminator) agar rute ingress dan egress dipaksa simetris.
  2. Gunakan *conntrackd* untuk sinkronisasi state table real-time antar firewall node secara out-of-band:
     ```text
     Node A conntrackd <---- Dedicated Sync Link (10GbE) ----> Node B conntrackd
     ```

---

## 11. Best Practices & Production Checklist

### Pre-Production Validation Checklist
- [ ] **Kalkulasi & Uji MTU End-to-End**: Pastikan nilai MTU tunnel disetel maksimal 1420 (WireGuard) atau 1424 (IPSec), dan verifikasi uji ping menggunakan flag `ping -M do -s 1396 <destination>`.
- [ ] **Kapasitas Memory Conntrack**: Pastikan kapasitas RAM mencukupi kebutuhan tabel hash. Satu record `nf_conn` memakan sekitar 320 byte pada sistem x86_64.
  
  $$\text{RAM Requirements} = 2.000.000 \times 320 \text{ bytes} \approx 640 \text{ MB dedicated kernel slab}$$

- [ ] **Konfigurasi Reverse Path Forwarding (RPF)**: Ubah dari Strict Mode (`rp_filter=1`) ke Loose Mode (`rp_filter=2`) pada interface yang menjalankan dynamic routing multihome untuk mencegah *false-positive drops*.
- [ ] **Enkripsi Keras & Modern**: Matikan modul cipher usang (3DES, MD5, SHA1, Diffie-Hellman Groups < 14). Gunakan proposal standar industri: AES-256-GCM, SHA2-384, Curve25519 (Group 31).
- [ ] **Dead Peer Detection (DPD) & Keepalives**: Konfigurasi DPD dengan agresivitas terukur pada IPSec, atau pasang keepalive 25 detik pada WireGuard di balik Stateful NAT:
  ```ini
  PersistentKeepalive = 25
  ```

---

## 12. Hands-on Practice: Membangun Enterprise Route-Based IPSec dengan FRR & BGP

Simpan artefak praktikum pada direktori: `hands-on/m02/`

### Topologi Praktikum
- **Router-A (Site Alpha)**:
  - Loopback IP: `10.10.10.1/32`
  - WAN IP: `192.168.100.10/24`
  - VTI IP: `10.255.255.1/30`
  - BGP ASN: `65100`
- **Router-B (Site Beta)**:
  - Loopback IP: `10.20.20.1/32`
  - WAN IP: `192.168.100.20/24`
  - VTI IP: `10.255.255.2/30`
  - BGP ASN: `65200`

### Langkah 1: Persiapan Environment Jaringan (Network Namespaces)
Eksekusi script `hands-on/m02/setup-env.sh`:

```bash
#!/bin/bash
set -xeuo pipefail

# Hapus namespace jika sebelumnya sudah dibuat
ip netns del site-a 2>/dev/null || true
ip netns del site-b 2>/dev/null || true
ip netns del wan-core 2>/dev/null || true

# Buat Isolated Namespaces
ip netns add site-a
ip netns add site-b
ip netns add wan-core

# Buat Interkoneksi veth pairs simulasi WAN
ip link add veth-a-wan type veth peer name veth-wan-a
ip link add veth-b-wan type veth peer name veth-wan-b

# Pasang veth ke namespace masing-masing
ip link set veth-a-wan netns site-a
ip link set veth-wan-a netns wan-core
ip link set veth-b-wan netns site-b
ip link set veth-wan-b netns wan-core

# Konfigurasi WAN Core Switch (Stateless Transit)
ip netns exec wan-core ip addr add 192.168.100.254/24 dev veth-wan-a
ip netns exec wan-core ip addr add 192.168.100.253/24 dev veth-wan-b
ip netns exec wan-core ip link set veth-wan-a up
ip netns exec wan-core ip link set veth-wan-b up
ip netns exec wan-core sysctl -w net.ipv4.ip_forward=1

# Konfigurasi Interface WAN Site A
ip netns exec site-a ip addr add 192.168.100.10/24 dev veth-a-wan
ip netns exec site-a ip link set veth-a-wan up
ip netns exec site-a ip route add default via 192.168.100.254
ip netns exec site-a ip addr add 10.10.10.1/32 dev lo
ip netns exec site-a ip link set lo up

# Konfigurasi Interface WAN Site B
ip netns exec site-b ip addr add 192.168.100.20/24 dev veth-b-wan
ip netns exec site-b ip link set veth-b-wan up
ip netns exec site-b ip route add default via 192.168.100.253
ip netns exec site-b ip addr add 10.20.20.1/32 dev lo
ip netns exec site-b ip link set lo up

echo "[+] WAN Environment & Endpoints Initialized Successfully."
```

### Langkah 2: Provisioning Virtual Tunnel Interface (VTI) Manual
Eksekusi script `hands-on/m02/setup-vti.sh`:

```bash
#!/bin/bash
set -xeuo pipefail

# Inisialisasi VTI Interface pada Site-A
ip netns exec site-a ip tunnel add vti0 mode vti local 192.168.100.10 remote 192.168.100.20 key 100
ip netns exec site-a ip addr add 10.255.255.1/30 peer 10.255.255.2/30 dev vti0
ip netns exec site-a ip link set vti0 mtu 1424
ip netns exec site-a ip link set vti0 up
ip netns exec site-a sysctl -w net.ipv4.conf.vti0.rp_filter=0
ip netns exec site-a sysctl -w net.ipv4.conf.vti0.disable_policy=1

# Inisialisasi VTI Interface pada Site-B
ip netns exec site-b ip tunnel add vti0 mode vti local 192.168.100.20 remote 192.168.100.10 key 100
ip netns exec site-b ip addr add 10.255.255.2/30 peer 10.255.255.1/30 dev vti0
ip netns exec site-b ip link set vti0 mtu 1424
ip netns exec site-b ip link set vti0 up
ip netns exec site-b sysctl -w net.ipv4.conf.vti0.rp_filter=0
ip netns exec site-b sysctl -w net.ipv4.conf.vti0.disable_policy=1

echo "[+] VTI Interconnect Configuration Complete."
```

### Langkah 3: Konfigurasi Manual XFRM Transform Engine (Simulasi IPSec Manual SA)
Gunakan `hands-on/m02/setup-xfrm.sh` untuk membentuk SA secara deterministik:

```bash
#!/bin/bash
set -xeuo pipefail

KEY_AUTH="0x1111111111111111111111111111111111111111"
KEY_ENC="0x22222222222222222222222222222222"

# Security Associations (SA) Site-A -> Site-B
ip netns exec site-a ip xfrm state add src 192.168.100.10 dst 192.168.100.20 proto esp spi 0x1000 \
    mode tunnel auth sha1 "${KEY_AUTH}" enc aes "${KEY_ENC}"
ip netns exec site-a ip xfrm state add src 192.168.100.20 dst 192.168.100.10 proto esp spi 0x2000 \
    mode tunnel auth sha1 "${KEY_AUTH}" enc aes "${KEY_ENC}"

# Policy Site-A: Kaitkan dengan mark 100 milik interface VTI
ip netns exec site-a ip xfrm policy add dir out mark 100 tmpl src 192.168.100.10 dst 192.168.100.20 proto esp mode tunnel
ip netns exec site-a ip xfrm policy add dir in mark 100 tmpl src 192.168.100.20 dst 192.168.100.10 proto esp mode tunnel

# Security Associations (SA) Site-B -> Site-A
ip netns exec site-b ip xfrm state add src 192.168.100.20 dst 192.168.100.10 proto esp spi 0x2000 \
    mode tunnel auth sha1 "${KEY_AUTH}" enc aes "${KEY_ENC}"
ip netns exec site-b ip xfrm state add src 192.168.100.10 dst 192.168.100.20 proto esp spi 0x1000 \
    mode tunnel auth sha1 "${KEY_AUTH}" enc aes "${KEY_ENC}"

# Policy Site-B: Kaitkan dengan mark 100 milik interface VTI
ip netns exec site-b ip xfrm policy add dir out mark 100 tmpl src 192.168.100.20 dst 192.168.100.10 proto esp mode tunnel
ip netns exec site-b ip xfrm policy add dir in mark 100 tmpl src 192.168.100.10 dst 192.168.100.20 proto esp mode tunnel

echo "[+] XFRM Manual State and Policies Injected."
```

### Langkah 4: Validasi & Troubleshooting
Verifikasi konektivitas tunnel terenkripsi:

```bash
# Uji ping عبر tunnel VTI
ip netns exec site-a ping -c 3 10.255.255.2

# Uji enkapsulasi paket pada layer fisik WAN
# Harap pastikan hanya protokol ESP (IP proto 50) yang terlihat di veth-a-wan, BUKAN paket ICMP polos
ip netns exec wan-core tcpdump -nn -i veth-wan-a -c 4
```

---

## 13. Exercises

### Level Easy
Tuliskan satu set aturan `nftables` yang membatasi traffic SSH masuk ke port 22 hanya dari subnet `192.168.1.0/24`, mengizinkan response traffic yang sudah establish, dan mencatat (*log*) paket yang ditolak dengan rate limit maksimal 3 log per menit untuk mencegah kehabisan ruang disk (*log disk saturation*).

### Level Medium
Kalkulasikan Maximum Segment Size (MSS) optimal untuk konfigurasi TCP di mana frame Ethernet asli berjalan melewati topologi berikut:
`Client (MTU 1500) -> VXLAN Overlay (Header 50 byte) -> Route-based IPSec Tunnel (ESP Overhead 56 byte) -> WAN Internet`.
Jelaskan langkah kalkulasi matematisnya dan tuliskan perintah kernel untuk menerapkan nilai MSS tersebut secara imperatif pada interface terkait.

### Level Hard
Sebuah klaster Kubernetes memproses pembayaran transaksi. Anda diminta menyusun file `CiliumNetworkPolicy` yang menerapkan isolasi Zero Trust ketat pada namespace `payment-core`:
1. Izinkan pod dengan label `role: checkout` hanya mengakses pod `role: fraud-detector` pada port TCP 9000 dengan batasan Layer 7: hanya method `POST` ke path `/check`.
2. Izinkan pod `role: checkout` mengakses database PostgreSQL eksternal pada IP `192.168.50.15/32` di port 5432.
3. Blokir total egress akses internet publik langsung, namun izinkan resolusi DNS internal CoreDNS di kube-system via port UDP 53.

---

## 14. Real-World Architectural Challenge

### Konteks Skenario:
Sebuah bank multinasional sedang mengalihkan sistem core banking dari On-Prem Mainframe ke Multi-Region Cloud (AWS dan GCP). Sistem ini mentransfer $40 miliar volume harian.
- **Topologi Eksisting**:
  - AWS Direct Connect 10 Gbps (Private VIF) terhubung ke Data Center Utama.
  - Backup link mengandalkan Internet Public menggunakan IPsec IKEv2.
- **Problem Produksi**:
  Terjadi insiden di mana fiber optik fisik provider Direct Connect mengalami degradasi parsial (*flapping* / *packet loss* 15% secara acak, bukan *total down*). 
  - Interface fisik Direct Connect tetap `UP/UP`, sehingga BGP session di Direct Connect tidak putus.
  - Akibatnya, traffic tetap melewati Direct Connect yang mengalami *packet loss* parah, alih-alih beralih ke link backup IPSec. 
  - Aplikasi core banking mengalami connection timeout massal, sementara firewall state table di kedua sisi dipenuhi status `SYN_RECV` dan `FIN_WAIT_1`.

### Instruksi Penugasan:
Sebagai Principal Network Architect:
1. Rancang arsitektur failover otomatis menggunakan BGP yang dipadukan dengan **Bidirectional Forwarding Detection (BFD)** dengan nilai interval agresif tanpa memicu *false-positive failover*. Berikan justifikasi kalkulasi timernya!
2. Definisikan arsitektur routing hybrid (menggunakan *BGP Local Preference*, *AS-Path Prepending*, dan *Community Tags*) agar traffic tidak mengalami *asymmetric routing* saat failover parsial berlangsung.
3. Rancang strategi pencegahan *conntrack exhaustion* pada firewall transit saat kondisi jaringan berosilasi (*route flapping*) dengan memanfaatkan mekanisme eBPF atau firewall bypass architecture.
4. Buat dokumen arsitektur komprehensif dalam bentuk diagram alur ASCII dan pseudocode/konfigurasi nyata (Cisco IOS-XE/Arista EOS atau Linux FRR).

---

## 15. Evaluasi Pemahaman (Quiz)

### 15.1. Basic Questions
1. **Apa perbedaan mendasar antara status koneksi `INVALID` dan penolakan paket akibat aturan `DROP` pada firewall stateful?**
   - *Jawaban*: Paket berstatus `INVALID` adalah paket yang tidak dapat diidentifikasi oleh subsistem conntrack atau tidak mematuhi status FSM protokol (misal: TCP sequence number di luar window yang valid, atau flag TCP ilegal). Aturan `DROP` adalah keputusan kebijakan (*policy decision*) yang membuang paket secara eksplisit meskipun paket tersebut secara struktural valid.

2. **Mengapa enkapsulasi ESP (IP Protocol 50) sering kali harus dibungkus kembali dengan header UDP Port 4500 (NAT-Traversal)?**
   - *Jawaban*: Karena perangkat NAT komersial umumnya memetakan Layer 4 port (PAT/NAPT). Header asli ESP tidak memiliki port TCP/UDP, sehingga perangkat NAT di tengah jalur publik tidak dapat memetakan paket balasan ke IP privat internal tanpa pembungkusan UDP NAT-T.

3. **Berapa nilai default timeout untuk koneksi TCP yang telah mencapai status `ESTABLISHED` pada Linux `nf_conntrack` standar?**
   - *Jawaban*: Nilai defaultnya adalah 432.000 detik (5 hari).

4. **Sebutkan struktur 5-tuple yang digunakan conntrack untuk mengidentifikasi sebuah koneksi secara unik.**
   - *Jawaban*: IP Asal (Source IP), IP Tujuan (Destination IP), Port Asal (Source Port), Port Tujuan (Destination Port), dan Nomor Protokol L4 (Protocol).

5. **Apa fungsi utama dari utilitas `conntrackd` dalam arsitektur High-Availability Firewall aktif/pasif?**
   - *Jawaban*: `conntrackd` berfungsi mereplikasi status tabel koneksi kernel (`nf_conntrack`) dari node firewall aktif ke node siaga (standby) secara real-time. Hal ini memastikan koneksi TCP klien yang sudah berjalan tidak terputus (*seamless failover*) saat firewall primer mati.

### 15.2. Intermediate Questions
1. **Bagaimana mekanisme eBPF memproses aturan firewall lebih cepat dibandingkan `iptables` klasik pada beban 10 juta paket per detik?**
   - *Jawaban*: `iptables` memproses paket secara sekuensial melalui traversal rantai aturan linier ($O(N)$) yang membutuhkan traversal memory context kernel yang besar dan pemanggilan memory `sk_buff`. eBPF (khususnya XDP) berjalan langsung pada ring-buffer driver network card sebelum alokasi `sk_buff`, mengeksekusi bytecode termodifikasi langsung via JIT compilation dengan lookup tabel hash $O(1)$.

2. **Mengapa asymmetric routing dapat merusak komunikasi TCP pada jaringan yang dilindungi Stateful Firewall, meskipun aturan firewall di kedua sisi mengizinkan port tersebut?**
   - *Jawaban*: Stateful firewall mengharapkan melihat seluruh fase komunikasi (SYN, SYN-ACK, ACK, dan sequence numbers yang berurutan). Jika rute pergi melewati Firewall-A dan rute pulang melewati Firewall-B, Firewall-B akan menerima paket balasan (ACK atau Data) tanpa pernah mencatat handshake inisiasi (SYN), menandai paket tersebut sebagai status `INVALID`, lalu membuangnya (*dropping*).

3. **Jelaskan risiko keamanan dari menaikkan batas `net.netfilter.nf_conntrack_tcp_be_liberal = 1` di lingkungan data center produksi.**
   - *Jawaban*: Mengaktifkan `be_liberal` menonaktifkan validasi TCP window tracking. Ini membuka celah serangan *blind in-window packet injection* dan *TCP reset attacks*, di mana penyerang dapat menyuntikkan data palsu atau memutus sesi TCP legal tanpa perlu menebak sequence number yang presisi.

4. **Dalam konteks WireGuard, apa yang terjadi jika paket IP keluar menuju alamat tujuan yang tidak tercantum dalam konfigurasi `AllowedIPs` pada peer mana pun?**
   - *Jawaban*: Paket tersebut akan di-drop secara instan oleh interface driver WireGuard pada level kernel (*No route to host / cryptokey routing lookup failure*), karena WireGuard tidak menemukan entitas kunci publik yang bertanggung jawab atas subnet tujuan tersebut.

5. **Mengapa penerapan Path MTU Discovery (PMTUD) sering kali gagal pada jalur WAN publik, dan bagaimana MSS Clamping mengatasi hal tersebut?**
   - *Jawaban*: PMTUD bergantung pada pesan ICMP Type 3 Code 4. Banyak administrator jaringan publik memblokir seluruh pesan ICMP tanpa pengecualian, memicu hilangnya ICMP tersebut (*ICMP Blackhole*). MSS Clamping mengatasinya secara proaktif dengan menginspeksi header TCP SYN dan menurunkan parameter *Maximum Segment Size* secara paksa di tingkat gateway saat handshake berlangsung.

### 15.3. Production Scenario Questions
1. **Skenario Kasus 1**:
   Sebuah klaster microservices mendadak mengalami kelambatan ekstrem. Pada node gateway Linux, output perintah `dmesg` menunjukkan:
   `nf_conntrack: falling back to vmalloc()`. Penggunaan RAM node melonjak dan utilisasi CPU pada core yang melayani *softirq* (*ksoftirqd*) mencapai 100%.
   - *Diagnosa Masalah*: Hash bucket conntrack (`hashsize`) terlalu kecil dibandingkan dengan lonjakan entitas koneksi, menyebabkan panjang *linked list* pada setiap bucket hash menjadi sangat panjang. CPU overhead melonjak karena kernel harus melintasi linked list yang masif dalam memori yang dialokasikan lewat `vmalloc` (non-contiguous physical memory) untuk setiap paket masuk.
   - *Solusi Remediasi*: Ubah ukuran hash table conntrack menjadi seimbang dengan memori fisik kontigu (*slab cache* via `kmalloc`), sesuaikan parameter `hashsize = nf_conntrack_max / 4`, dan percepat timeout `ESTABLISHED` serta `TIME_WAIT`.

2. **Skenario Kasus 2**:
   Dua router terkoneksi via Route-Based IPSec VTI. BGP session berhasil terbentuk (`Established`). Namun, saat host di balik Router A mengirimkan file berukuran 100 MB via HTTP ke host di balik Router B, transmisi berhenti di 3% dan mengalami timeout. Ping kecil (`ping -c 5 <IP>`) berhasil dengan respons latensi rendah.
   - *Diagnosa Masalah*: Terjadi fenomena *MTU Blackhole*. Ping default menggunakan ukuran paket kecil (64 bytes), sehingga sukses terkirim. Pengiriman file HTTP memanfaatkan segmentasi maksimal (1500 bytes), yang setelah ditambah overhead IPSec melebihi MTU fisik, memicu fragmentasi sementara flag *Don't Fragment* (DF) aktif.
   - *Solusi Remediasi*: Turunkan MTU interface VTI ke 1420 dan pasang aturan MSS Clamping pada nftables gateway: `tcp flags syn tcp option maxseg size set 1380`.

3. **Skenario Kasus 3**:
   Perusahaan menghubungkan Kubernetes Cluster di Google Cloud dengan Private Data Center melalui IPSec VPN. Developer mengeluh bahwa sesekali koneksi database JDBC dari pod ke Oracle DB on-premise mengalami error *Connection reset by peer* setiap tepat 60 menit sekali secara reguler.
   - *Diagnosa Masalah*: Terjadi proses *IPSec Phase 2 (Child SA) Rekeying* setiap 3600 detik (1 jam). Jika parameter rekeying pada kedua gateway tidak identik (misal perbedaan implementasi PFS/Perfect Forward Secrecy atau penanganan *make-before-break*), SA yang lama akan dihapus sebelum SA baru terpasang sempurna. Hal ini menyebabkan paket data in-flight di-drop dan koneksi stateful TCP di-reset.
   - *Solusi Remediasi*: Konfigurasikan *make-before-break* rekeying pada konfigurasi IKEv2 daemon (seperti strongSwan `rekey_time` dan `margin`), dan pastikan kedua belah pihak menyepakati algoritma Diffie-Hellman group yang seragam untuk fase PFS.

---

## 16. Summary
- **Conntrack Engine**: Fondasi dari stateful firewall Linux terletak pada pemetaan 5-tuple di tabel hash kernel. Performa firewall skala enterprise bergantung mutlak pada kalibrasi ukuran `nf_conntrack_buckets`, penyesuaian durasi timer koneksi, dan pemanfaatan offloading stateless (seperti `NOTRACK` atau eBPF bypass) untuk alur data berskala raksasa.
- **Route-Based VPN (VTI/WireGuard)**: Menggantikan batasan kaku arsitektur policy-based lawas. Dengan memetakan enkripsi ke dalam interface virtual L3 murni, sistem memperoleh kemampuan routing dinamis via BGP, pemantauan status tautan ultra-cepat melalui BFD, dan isolasi kegagalan transmisi secara instan.
- **Microsegmentation vs Traditional Perimeter**: Pendekatan keamanan modern menolak konsep trust implisit internal. Penerapan Zero Trust Network Architecture menuntut isolasi lalu lintas *East-West* hingga tingkat workload individu memanfaatkan teknologi modern seperti EVPN-VXLAN GBP atau Cilium NetworkPolicy berbasis kernel eBPF.
- **MTU/MSS Engineering**: Pengabaian terhadap kalkulasi penambahan byte header (enkapsulasi IPSec, WireGuard, GRE, atau VXLAN) merupakan akar utama kegagalan performa transfer data pada hybrid cloud. Otomasi MSS Clamping di tingkat ingress tunnel merupakan mitigasi wajib di lingkungan produksi.