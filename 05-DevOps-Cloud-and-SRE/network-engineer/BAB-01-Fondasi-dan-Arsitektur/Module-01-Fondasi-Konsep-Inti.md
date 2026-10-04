# Bab 01: Fondasi Arsitektur Jaringan Komputer & Model Referensi
## Module 01: Model Referensi OSI & TCP/IP serta Mekanisme Enkapsulasi Paket

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** aliran data end-to-end melalui model 7-Layer OSI dan 4-Layer TCP/IP hingga tingkat *bit-level* dan *byte boundary*.
- **Mengevaluasi** proses enkapsulasi dan dekapsulasi Protocol Data Unit (PDU) saat melintasi batas Kernel OS, Network Interface Card (NIC), dan perangkat transit (Switch/Router).
- **Mendiagnosis** anomali transmisi data akibat ketidaksesuaian ukuran *Maximum Transmission Unit* (MTU) dan *Maximum Segment Size* (MSS) menggunakan *packet analyzer*.
- **Mengimplementasikan** konfigurasi jaringan L2/L3 pada Linux Kernel dan Network Operating System (NOS) enterprise yang selaras dengan batas-batas model referensi.

---

### 2. Conceptual Foundation
Model referensi jaringan komputer distandarisasi untuk memisahkan fungsi komputasi, transmisi, dan serialisasi data menjadi abstraksi modular yang independen. Dua model utama yang mendasari seluruh rekayasa jaringan modern adalah:

1. **Model OSI (Open Systems Interconnection - ISO/IEC 7498-1):** Model konseptual 7 lapis yang mendefinisikan pemisahan fungsi abstrak jaringan secara ketat:
   - Layer 7: *Application* (HTTP, DNS, BGP, SSH)
   - Layer 6: *Presentation* (Enkripsi TLS/SSL, representasi format data/ASN.1)
   - Layer 5: *Session* (Manajemen koneksi logika/RPC socket)
   - Layer 4: *Transport* (Port addressing, flow control, reliability - TCP, UDP)
   - Layer 3: *Network* (Logical addressing, routing, path selection - IPv4, IPv6)
   - Layer 2: *Data Link* (Framing, physical addressing, media access - Ethernet, 802.1Q)
   - Layer 1: *Physical* (Encoding, bit transmission, electrical/optical signaling)

2. **Model TCP/IP (RFC 1122 / RFC 791 / RFC 793):** Model implementasi praktis 4 lapis yang digunakan pada arsitektur internet:
   - *Application Layer* (Menggabungkan Layer 5-7 OSI)
   - *Transport Layer* (Host-to-Host)
   - *Internet Layer* (Antar-jaringan/Inter-network)
   - *Link / Network Access Layer* (Menggabungkan Layer 1-2 OSI)

```
+--------------------------+---------------------------+
|      OSI Reference       |      TCP/IP Protocol      |
|          Model           |           Suite           |
+--------------------------+---------------------------+
| 7. Application           |                           |
| 6. Presentation          | Application               |
| 5. Session               |                           |
+--------------------------+---------------------------+
| 4. Transport             | Transport (TCP / UDP)     |
+--------------------------+---------------------------+
| 3. Network               | Internet (IPv4 / IPv6)    |
+--------------------------+---------------------------+
| 2. Data Link             | Link / Network Interface  |
| 1. Physical              | (Ethernet / PHY / MAC)    |
+--------------------------+---------------------------+
```

Pemisahan ini memungkinkan decoupling fungsional: Application Layer tidak perlu mengetahui apakah media transmisi menggunakan kabel *Fiber Optic Single-Mode* (100GBASE-LR4) atau tembaga *Cat6A* (10GBASE-T), selama Layer 2 dan Layer 1 menangani framing dan modulasi sinyal.

---

### 3. Why It Matters
Ketidakmampuan memetakan masalah teknis ke layer model referensi yang tepat menyebabkan inefisiensi diagnostik sistemik:
- **Kegagalan Skala Mikro:** Kesalahan konfigurasi MTU sebesar 4 byte akibat enkapsulasi tambahan (misalnya penambahan tag VLAN 802.1Q atau tunnel GRE/IPsec) dapat menyebabkan fragmentasi paket berlebihan (*packet serialization delay*) atau *black-hole packet dropping* saat bit Don't Fragment (DF) diset.
- **Dampak Finansial & Operasional:** Pada sistem *high-frequency trading* atau arsitektur *low-latency microservices*, kegagalan memahami pemrosesan Layer 2 (MAC learning, CAM table overflow) dapat memicu *flooding uncast traffic*, menurunkan throughput dari 40 Gbps menjadi puluhan megabit per detik dalam hitungan milidetik.
- **RCA Presisi:** Troubleshooting sistem modern memerlukan korelasi cepat antara Layer 4 *TCP Reset* (RST), Layer 3 *ICMP Unreachable*, Layer 2 *ARP Resolution Failure*, dan Layer 1 *Bit Error Rate* (BER).

---

### 4. What It Is
Secara teknis, komunikasi jaringan adalah proses manipulasi buffer data di memori melalui penambahan (*encapsulation*) atau pelepasan (*decapsulation*) metadata struktural (header dan trailer). 

Satuan unit transmisi disebut **Protocol Data Unit (PDU)**:
- **Layer 7-5:** Data / Payload / Stream
- **Layer 4:** Segment (TCP) atau Datagram (UDP)
- **Layer 3:** Packet (IPv4/IPv6)
- **Layer 2:** Frame (Ethernet II, IEEE 802.3)
- **Layer 1:** Bits / Symbols

#### Anatomi PDU Ethernet II + IPv4 + TCP:
```
+-------------------------------------------------------------------------------------------------+
| Ethernet Frame Header (14 Bytes)                                                                |
| [Dest MAC: 6B] [Src MAC: 6B] [EtherType: 2B (0x0800)]                                           |
+-------------------------------------------------------------------------------------------------+
| IPv4 Header (Min 20 Bytes)                                                                      |
| [Ver/IHL: 1B] [DSCP/ECN: 1B] [Total Length: 2B] [Ident: 2B] [Flags/FragOffset: 2B]             |
| [TTL: 1B] [Protocol: 1B (0x06=TCP)] [Checksum: 2B] [Src IP: 4B] [Dest IP: 4B]                   |
+-------------------------------------------------------------------------------------------------+
| TCP Header (Min 20 Bytes)                                                                       |
| [Src Port: 2B] [Dest Port: 2B] [Sequence Number: 4B] [Ack Number: 4B]                          |
| [Data Offset/Reserved/Flags: 2B] [Window Size: 2B] [Checksum: 2B] [Urgent Pointer: 2B]          |
+-------------------------------------------------------------------------------------------------+
| Payload / Application Data (e.g., HTTP GET, TLS Client Hello)                                   |
+-------------------------------------------------------------------------------------------------+
| Ethernet Trailer (4 Bytes)                                                                      |
| [Frame Check Sequence (FCS / CRC32): 4 Bytes]                                                   |
+-------------------------------------------------------------------------------------------------+
```

---

### 5. How It Works
Aliran data dari User-space Application pada Host A menuju Application pada Host B melintasi tahapan deterministik berikut:

```
[Host A (Sender)]                                       [Host B (Receiver)]
+----------------------+                                 +----------------------+
| User Space App       |                                 | User Space App       |
| write(fd, buf, len)  |                                 | read(fd, buf, len)   |
+----------+-----------+                                 +----------^-----------+
           |                                                        |
[Kernel Space]                                           [Kernel Space]
+----------v-----------+                                 +----------+-----------+
| Socket Buffer (sk_buff)                                | Socket Buffer        |
| Layer 4: TCP Segment |                                 | L4 Verification      |
| (Add TCP Port Header)|                                 | (Port, Seq, Ack, Win)|
+----------+-----------+                                 +----------^-----------+
           |                                                        |
+----------v-----------+                                 +----------+-----------+
| Layer 3: IP Packet   |                                 | L3 Verification      |
| (Route lookup, IP Hdr|                                 | (Checksum, Dest IP,  |
| TTL, Checksum calc)  |                                 | Decr TTL)            |
+----------+-----------+                                 +----------^-----------+
           |                                                        |
+----------v-----------+                                 +----------+-----------+
| Layer 2: Eth Frame   |                                 | L2 Parsing           |
| (ARP table lookup,   |                                 | (MAC check, strip    |
| Add MAC Header)      |                                 | header, verify FCS)  |
+----------+-----------+                                 +----------^-----------+
           |                                                        |
[Hardware / NIC]                                         [Hardware / NIC]
+----------v-----------+     Physical Transmission       +----------+-----------+
| Layer 1: PHY         |-------------------------------->| Layer 1: PHY         |
| (DMA Ring, Preamble, |       (Pulses, Photons,         | (Clock sync, SFD,    |
| CRC32, Serialization)|        RF Modulation)           | Receive Ring Buffer) |
+----------------------+                                 +----------------------+
```

#### Siklus Pemrosesan Transmisi (Egress Flow):
1. **Application Layer:** Aplikasi mengeksekusi *system call* (misal: `send()` atau `write()`) memindahkan buffer data dari *User Space* ke *Kernel Space Socket Buffer* (`struct sk_buff` di Linux).
2. **Transport Layer:** Kernel mengalokasikan nomor port sumber ephemeral, menambahkan header TCP (20 byte) atau UDP (8 byte), mengatur *Sequence/Acknowledgment Number*, serta menghitung L4 Checksum (mencakup pseudo-header IP).
3. **Network Layer:** Kernel memeriksa *Routing Information Base* (FIB/RIB) untuk menentukan antarmuka keluar (*egress interface*) dan IP *Next-Hop*. Header IP (20 byte) disisipkan; bidang TTL diset (umumnya 64 pada Linux), dan *Total Length* dihitung.
4. **Data Link Layer:** Kernel/Driver memeriksa tabel ARP/Neighbor Cache (`ip neigh`). Jika alamat MAC *Next-Hop* ditemukan, Ethernet Header (14 byte) ditambahkan. Jika belum, paket ditahan dalam antrean sementara paket ARP Request dibroadcast.
5. **Physical Layer (NIC):** Driver menyalin deskriptor paket ke *Transmit Ring Buffer* (TX Ring). Melalui *Direct Memory Access* (DMA), kartu jaringan (NIC) mengambil data dari RAM host, menambahkan 8-byte Preamble + SFD (*Start Frame Delimiter*), menghitung CRC-32 dan menaruhnya di FCS (4 byte), lalu mengubah bit stream digital menjadi sinyal fisik (tegangan listrik atau pulsa laser).

#### Siklus Pemrosesan Penerimaan (Ingress Flow):
1. **NIC (PHY/MAC):** Mendeteksi sinyal, sinkronisasi bit clock via preamble, memvalidasi integritas frame via FCS/CRC32. Jika CRC tidak valid, frame didrop secara diam-diam (*interface input drops/CRC error*).
2. **DMA Transfer:** Frame yang valid disalin via DMA ke *Receive Ring Buffer* (RX Ring) host. NIC memicu *Hardware Interrupt* (IRQ) atau membiarkan mekanisme NAPI (*New API poll mode*) membaca ring buffer.
3. **L2 Verification:** Driver memeriksa Destination MAC. Jika sesuai dengan MAC NIC atau berupa *multicast/broadcast*, payload diarahkan ke network stack. Header Ethernet dilepas.
4. **L3 Verification:** Kernel memvalidasi IPv4 Checksum, memeriksa kecocokan Destination IP atau izin forwarding (jika difungsikan sebagai router), serta memvalidasi TTL > 1. Header IP dilepas.
5. **L4 Verification & Socket Delivery:** Kernel membaca protokol L4 (0x06 untuk TCP), mengarahkan payload ke *TCP Control Block* yang cocok dengan 4-tuple (`Src IP, Src Port, Dst IP, Dst Port`), memvalidasi TCP Checksum & urutan sequence, mengirim sinyal *ACK*, lalu memicu *wake-up event* ke aplikasi user-space untuk membaca data via `read()`.

---

### 6. Architecture & Data Flow Diagram

Diagram berikut mengilustrasikan perpindahan status struktural data saat melintasi batas Kernel OS Host Pengirim, Perangkat Transit (Switch L2 dan Router L3), hingga Kernel OS Host Penerima:

```
HOST A (192.168.10.10/24)                                                        ROUTER R1                                                        HOST B (10.0.0.20/24)
+-----------------------+                                               +-------------------------+                                              +-----------------------+
| App: Data Buffer      |                                               |                         |                                              | App: Data Buffer      |
+-----------+-----------+                                               |                         |                                              +-----------^-----------+
            | Encapsulate                                               |                         |                                                          | Decapsulate
+-----------v-----------+                                               |                         |                                              +-----------+-----------+
| L4: [TCP|Data]        |                                               |                         |                                              | L4: [TCP|Data]        |
+-----------+-----------+                                               |                         |                                              +-----------^-----------+
            | Encapsulate                                               | L3 Routing Engine       |                                                          | Decapsulate
+-----------v-----------+                                               | [Route Lookup: FIB]     |                                              +-----------+-----------+
| L3: [IP|TCP|Data]     |                                               | [Decr TTL, Recalc Chksum|                                              | L3: [IP|TCP|Data]     |
+-----------+-----------+                                               +------------^------------+                                              +-----------^-----------+
            | Encapsulate                                                            |                                                                       | Decapsulate
+-----------v-----------+             SWITCH L1/L2                                   | Decap/Re-encap                                            +-----------+-----------+
| L2: [EthA|IP|TCP|Data]|        +--------------------+                              |                                                           | L2: [EthB|IP|TCP|Data]|
+-----------+-----------+        | Forward based only |                 +------------+------------+                              +-----------+   +-----------^-----------+
            |                    | on Destination MAC |                 | Ingress L2 | Egress L2  |                              | Egress SW |               |
+-----------v-----------+        | (No IP inspection) |                 | Strip EthA | Add EthB   |                              | L2 Fwd    |   +-----------+-----------+
| L1: Physical Bitstream+------->| MAC Table Lookup   +---------------->| Port eth0  | Port eth1  +----------------------------->| MAC Lookup+-->| L1: Physical Bitstream|
+-----------------------+        +--------------------+                 +-------------------------+                              +-----------+   +-----------------------+

Frame Snapshot on Wire 1:                                              Frame Snapshot on Wire 2:
+----------+----------+-------------+---------+                        +----------+----------+-------------+---------+
| DMAC: R1 | SMAC: HA | IP: HA->HB  | TCP+Data|                        | DMAC: HB | SMAC: R1 | IP: HA->HB  | TCP+Data|
+----------+----------+-------------+---------+                        +----------+----------+-------------+---------+
```

---

### 7. Simple Example
Melihat representasi pemrosesan L2/L3/L4 secara langsung pada Linux host:

```bash
# 1. Menampilkan Interface L1/L2 status dan MAC address
ip -d link show eth0

# Output analitis:
# 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
#    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff promiscuity 0 minmtu 68 maxmtu 9216

# 2. Menampilkan Pemetaan L3-ke-L2 (Neighbor/ARP Cache)
ip neigh show

# Output analitis:
# 192.168.10.1 dev eth0 lladdr 00:1c:73:aa:bb:cc REACHABLE

# 3. Mengirimkan single probe ICMP (L3) dan melacak enkapsulasi
ping -c 1 192.168.10.1

# 4. Inspeksi paket real-time menggunakan tcpdump dalam format hex dan ASCII
sudo tcpdump -n -e -vvv -c 1 -XX -i eth0 icmp
```

---

### 8. Practical Production-Grade Implementation

Berikut implementasi validasi enkapsulasi jaringan pada arsitektur server multi-homed Linux (Ubuntu Server / RHEL) yang terkoneksi ke Switch Enterprise Trunk/Access Port, termasuk segmentasi VLAN (L2 Tagging IEEE 802.1Q).

#### A. Konfigurasi Linux Network Stack (`/etc/netplan/01-netcfg.yaml`)
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp3s0f0:
      dhcp4: no
      dhcp6: no
  vlans:
    vlan100:
      id: 100
      link: enp3s0f0
      addresses:
        - 198.51.100.10/24
      routes:
        - to: default
          via: 198.51.100.1
      mtu: 1500
```
Terapkan perubahan konfigurasi:
```bash
sudo netplan generate
sudo netplan apply
```

#### B. Konfigurasi Cisco IOS-XE Switch (Access/Trunk Edge)
```cisco
! Interface konfigurasi menghadap Linux Server
interface TenGigabitEthernet1/0/1
 description TRUNK-TO-LINUX-SERVER-01
 switchport mode trunk
 switchport trunk allowed vlan 100
 switchport trunk encapsulation dot1q
 switchport nonegotiate
 spanning-tree portfast trunk
 spanning-tree bpduguard enable
 no shutdown
exit

! SVI Interface (L3 Gateway)
interface Vlan100
 description GATEWAY-VLAN100
 ip address 198.51.100.1 255.255.255.0
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no shutdown
exit
```

#### C. Skrip Python Scapy untuk Verifikasi Header & PDU Injection
Skrip tingkat rendah untuk menguji transmisi paket tanpa bergantung pada abstraction socket OS standar, membedah setiap layer PDU:

```python
#!/usr/bin/env python3
"""
PDU Injection & Parsing Engine
Deskripsi: Mengirimkan kustom Ethernet/VLAN/IP/TCP packet untuk menguji batas L2/L3.
"""
import sys
from scapy.all import Ether, Dot1Q, IP, TCP, Raw, sendp

def transmit_custom_pdu(interface: str):
    # Layer 2: Ethernet Header
    dst_mac = "00:1c:73:aa:bb:cc"  # MAC Gateway
    src_mac = "52:54:00:12:34:56"  # MAC Lokal

    # Membangun Paket Multi-Layer
    # L2 -> L2 Tagging (802.1Q) -> L3 -> L4 -> L7 Payload
    packet = (
        Ether(dst=dst_mac, src=src_mac, type=0x8100) /
        Dot1Q(vlan=100) /
        IP(src="198.51.100.10", dst="198.51.100.1", ttl=64, proto=6) /
        TCP(sport=49152, dport=80, seq=1000, flags="S", window=64240) /
        Raw(load=b"SYN-PROBE-L2-L3-L4")
    )

    print(f"[*] Mengirim frame via antarmuka: {interface}")
    print("[*] Detail PDU:")
    packet.show()

    # Transmisi pada Layer 2 Raw Socket
    sendp(packet, iface=interface, verbose=False)
    print("[+] Transmisi berhasil dieksekusi.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <physical_interface>")
        sys.exit(1)
    transmit_custom_pdu(sys.argv[1])
```

---

### 9. Trade-offs & Alternatives

Perancangan proses enkapsulasi pada infrastruktur jaringan melibatkan kompromi antara modularitas, performa, dan pemanfaatan bandwidth (*overhead*):

| Pendekatan / Protokol | Keuntungan | Kerugian | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Standard Ethernet Frame (MTU 1500)** | Kompatibilitas universal; tidak ada risiko MTU black hole di internet publik. | Overhead header tinggi (~3% payload terbuang); utilisasi CPU server tinggi akibat pemrosesan packet-per-second (PPS) berlebih. | Akses internet publik, WAN, interaksi multi-vendor heterogeneous. |
| **Jumbo Frames (MTU 9000)** | Mengurangi interupsi interrupt CPU (interrupt coalescing); meningkatkan throughput hingga 20-30% pada transfer data besar. | Harus diaktifkan seragam secara end-to-end; jika satu switch gagal mendukung MTU 9000, frame akan didrop (*silent discard*). | Storage Networks (iSCSI, NFS), Backup links, Data Center Fabric (East-West traffic). |
| **Network Overlay (VXLAN, Geneve - L2 over L3)** | Memperluas domain L2 melintasi core routed L3; abstraksi multi-tenant hingga 16 juta segmen (VNI). | Tambahan 50-byte header overhead; mengharuskan konfigurasi MTU jaringan transit minimal 1550-1600; potensi degradasi hardware hashing. | Software-Defined Data Centers (SDDC), VMware NSX, Kubernetes CNI (Cilium/Calico). |
| **Kernel Bypass (DPDK / SR-IOV)** | Melewati TCP/IP stack OS konvensional; memangkas latency hingga hitungan mikrodetik; jutaan PPS. | Kompleksitas debugging; memotong utilitas monitoring OS (`netstat`, `tcpdump`, `iptables` menjadi tidak berfungsi). | High-Frequency Trading (HFT), Core Telecom (5G UPF), High-Capacity DDoS Scrubbing. |

---

### 10. Best Practices & Operational Nuances
1. **Penerapan Batas MSS Clamping:**
   Pada jaringan yang menggunakan enkapsulasi terowongan (PPPoE, GRE, IPsec), MTU efektif Layer 3 akan tereduksi di bawah 1500 byte. Selalu aktifkan mekanisme MSS clamping pada router perimeter untuk memodifikasi field MSS saat TCP Three-Way Handshake:
   $$\text{MSS} = \text{MTU} - (\text{IP Header Size} + \text{TCP Header Size})$$
   Pada MTU 1400: $\text{MSS} = 1400 - (20 + 20) = 1360 \text{ byte}$.
2. **Kesesuaian Interface Speed dan Duplex:**
   Jangan pernah menggunakan *auto-negotiation* di salah satu ujung dan *hardcoded static speed/duplex* di ujung lainnya. Hal ini memicu *duplex mismatch* (satu sisi Full-Duplex, sisi lain Half-Duplex) yang menyebabkan runtuhnya performa jaringan akibat *late collisions* pada Layer 2 saat utilitas trafik tinggi.
3. **Penyelarasan MTU Transmit Path:**
   Pastikan nilai MTU pada link trunk switched selalu lebih besar atau sama dengan MTU host yang terhubung. Jika Host mengonfigurasi MTU 9000 (Jumbo Frame), semua switch intermediate port harus mendukung MTU minimal 9216 byte (Layer 2 frame overhead).

---

### 11. Anti-patterns & Common Pitfalls

#### Anti-Pattern: Mengabaikan Jalur ICMP Type 3 Code 4 (Fragmentation Needed)
- **Implementasi Rusak:** Memblokir seluruh paket ICMP secara agresif pada firewall dengan anggapan meningkatkan keamanan (*security through obscurity*).
- **Konsekuensi:** Rusaknya mekanisme *Path MTU Discovery* (PMTUD, RFC 1191). Klien dapat membuka koneksi TCP (paket SYN/ACK kecil berhasil lewat), tetapi koneksi mengalami *freeze* (*hang*) tanpa respons seketika payload besar dikirim. Hal ini disebut fenomena **MTU Black Hole**.

```
[Klien (MTU 1500)] ----> [Router A] -- (MTU 1400 Link) --> [Firewall (Drop ICMP)] ----> [Server (MTU 1500)]
   Klien mengirim TCP Segment Data (Len=1460, DF=1)
   Router A tidak dapat memfragmentasi karena DF bit aktif.
   Router A men-drop paket dan mengirim ICMP Type 3 Code 4 ke Pengirim.
   Firewall memblokir ICMP tersebut!
   HASIL: Host pengirim terus melakukan retransmit data, tidak menyadari MTU terlalu besar.
```

- **Perbaikan yang Tepat:** Jangan memblokir ICMP tipe esensial secara menyeluruh pada `iptables`/`nftables`:
  ```bash
  sudo iptables -A INPUT -p icmp --icmp-type destination-unreachable -j ACCEPT
  sudo iptables -A FORWARD -p icmp --icmp-type fragmentation-needed -j ACCEPT
  ```

---

### 12. Edge Cases, Failure Modes & Resilience

#### 1. Path MTU Discovery Failure (Silent Drop)
- **Gejala:** Ping dengan ukuran default bekerja normal, akses SSH via terminal berhasil autentikasi, namun sesi *hang* seketika mengeksekusi perintah output besar (seperti `cat /var/log/syslog` atau transfer file via SCP).
- **Mekanisme Kegagalan:** Header data besar melebihi MTU jalur transit terkecil, dan pengirim mengaktifkan flag Don't Fragment (DF=1). Perangkat yang membuang paket gagal mengirim kembali paket kendali `ICMP Type 3, Code 4 (Destination Unreachable, Fragmentation Needed and DF was Set)` ke host asal, atau paket kendali tersebut dibuang oleh firewall intermediate.
- **Solusi Mitigasi Otomatis (Linux):** Aktifkan PLPMTUD (*Packetization Layer Path MTU Discovery* - RFC 4821) yang menggunakan probe TCP alih-alih bergantung pada ICMP:
  ```bash
  sudo sysctl -w net.ipv4.tcp_mtu_probing=1
  ```

#### 2. L2 Asymmetric Routing & Unicast Flooding
- **Gejala:** Switch mengonsumsi utilisasi CPU tinggi, utilisasi link port melonjak drastis dengan trafik yang tidak ditujukan ke host yang tersambung pada port tersebut.
- **Mekanisme Kegagalan:** Terjadi ketika jalur egress dan ingress berbeda (*asymmetric path*). Switch L2 tidak pernah melihat trafik ingress dari host target untuk memetakan alamat MAC ke port (*CAM table aging out*), sehingga switch memperlakukan trafik unicast yang ditujukan ke host tersebut seperti broadcast, mengirimkannya (*flooding*) ke seluruh port dalam VLAN yang sama.

---

### 13. Security Considerations
Setiap layer dalam model referensi memiliki permukaan serangan (*attack surface*) spesifik yang harus dimitigasi secara terisolasi:

```
+-------+-----------------------------+----------------------------------------------+
| Layer | Threat Vector               | Industry Standard Mitigation                 |
+-------+-----------------------------+----------------------------------------------+
| L2    | ARP Poisoning / Spoofing    | Dynamic ARP Inspection (DAI)                 |
| L2    | Rogue DHCP Server           | DHCP Snooping (Trusted vs Untrusted ports)   |
| L2    | CAM Table Overflow          | Port Security (Limit MAC address count)      |
| L2    | VLAN Hopping (Double Tag)   | Explicit Native VLAN tagging, disabled DTP   |
| L3    | IP Spoofing                 | Unicast Reverse Path Forwarding (uRPF)       |
| L4    | TCP SYN Flood               | SYN Cookies, Aggressive Connection Aging     |
| L7    | Protocol-level exploit      | WAF, Deep Packet Inspection (DPI), mTLS      |
+-------+-----------------------------+----------------------------------------------+
```

Contoh penerapan mitigasi L2 pada interface Switch:
```cisco
interface GigabitEthernet1/0/5
 description USER-ACCESS-STATION
 switchport mode access
 switchport access vlan 10
 switchport port-security
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security aging time 2
 ip verify source
 ip dhcp snooping limit rate 20
 spanning-tree bpduguard enable
!
```

---

### 14. Observability & Debugging

#### Analisis Frame Byte-by-Byte menggunakan Wireshark/Tshark
Eksekusi inspeksi paket pada interface produksi untuk mengamati struktur enkapsulasi:

```bash
# Menangkap paket TCP SYN dan menampilkan breakdown layer secara terperinci
sudo tshark -i eth0 -f "tcp[tcpflags] & tcp-syn != 0" -c 1 -V
```

Output terurai menunjukkan representasi model referensi secara nyata:
```text
Frame 1: 74 bytes on wire (592 bits), 74 bytes captured (592 bits)
    [Protocols in frame: eth:ethertype:ip:tcp]
Ethernet II, Src: 52:54:00:12:34:56, Dst: 00:1c:73:aa:bb:cc      <-- Layer 2
    Destination: 00:1c:73:aa:bb:cc
    Source: 52:54:00:12:34:56
    Type: IPv4 (0x0800)
Internet Protocol Version 4, Src: 198.51.100.10, Dst: 203.0.113.5  <-- Layer 3
    0100 .... = Version: 4
    .... 0101 = Header Length: 20 bytes (5)
    Total Length: 60
    Flags: 0x4000, Don't fragment (DF)
    Time to Live: 64
    Protocol: TCP (6)
Transmission Control Protocol, Src Port: 54321, Dst Port: 443      <-- Layer 4
    Sequence Number: 0
    Header Length: 40 bytes
    Flags: 0x002 (SYN)
    Window: 64240
    Options: (20 bytes) MSS, SACK, Timestamp, NOP, Window Scale
```

#### Diagnostic Metrics Pipeline (CLI Reference Commands)
```bash
# 1. Mendeteksi drop di NIC Layer 1/Layer 2 (Buffer & Ring overrun)
ethtool -S eth0 | grep -E "rx_dropped|tx_dropped|rx_crc_errors|rx_missed_errors"

# 2. Mendeteksi drop di Kernel IP Stack (Layer 3)
netstat -s --numeric --ip

# 3. Mendeteksi retransmisi TCP dan reset (Layer 4)
netstat -s --numeric --tcp | grep -E "segments retransmited|resets sent"

# 4. Melacak perubahan MTU jalur secara real-time via Traceroute PMTU
traceroute --mtu 203.0.113.5
```

---

### 15. Real-World Case Study

#### Insiden: Downtime Layanan API Gateway Pasca-Aktivasi Tunnel IPSec
- **Deskripsi Insiden:** Sebuah institusi finansial menambahkan terowongan IPsec Site-to-Site berbasis rute (VTI) antara pusat data *on-premise* dan *public cloud*. Segera setelah lalu lintas dialihkan ke tunnel tersebut, transaksi payload kecil (<1200 byte) berhasil diproses, namun transaksi payload besar (upload dokumen/pembayaran batch JSON > 2KB) gagal secara terus-menerus dengan status error *Connection Timeout*.
- **Investigasi Sistem:**
  1. *Layer 1/2 Check:* Link optik stabil, interface error counter bernilai 0.
  2. *Layer 3 Diagnostic:* Ping `198.51.100.10` sukses dengan latensi 12ms. Ping dengan parameter buffer besar:
     ```bash
     ping -s 1472 -M do 198.51.100.10
     # Hasil: Frag needed and DF set (mtu = 1438)
     ```
  3. *Packet Capture Analysis:* Ditemukan bahwa payload aplikasi dienkapsulasi dengan header IPsec ESP (penambahan 56 byte) dan header GRE luar (24 byte). MTU interface fisik adalah 1500, sehingga MTU efektif interface tunnel turun menjadi:
     $$\text{MTU Tunnel} = 1500 - (56 + 24) = 1420 \text{ Byte}$$
     Aplikasi web mengirimkan segmen data TCP standar dengan MSS 1460 byte (total packet 1500 byte) dengan flag DF=1. Router gateway mencoba mengirimkan *ICMP Frag Needed*, namun paket ICMP tersebut didrop oleh firewall intermediate enterprise yang terlalu restriktif.
- **Resolusi Masalah:**
  1. Mengaktifkan MSS Clamping pada antarmuka tunnel router perbatasan:
     ```cisco
     interface Tunnel1
      ip tcp adjust-mss 1360
     ```
  2. Membuka aturan firewall untuk mengizinkan ICMP Type 3 Code 4. Transaksi normal seketika setelah nilai MSS dinegosiasikan ulang ke 1360 byte pada level handshake TCP.

---

### 16. Cross-Platform / Tooling Variations

Pemeriksaan dan manipulasi parameter L2/L3 pada berbagai implementasi sistem operasi jaringan:

```bash
# -------------------------------------------------------------
# Linux Kernel Stack
# -------------------------------------------------------------
# Mengubah MTU:
ip link set dev eth0 mtu 9000

# Menampilkan statistik interface L1/L2:
ip -s link show dev eth0

# Menampilkan FIB (L3 Forwarding Table):
ip route show table main

# -------------------------------------------------------------
# Cisco IOS-XE
# -------------------------------------------------------------
# Mengubah MTU L2/L3:
configure terminal
 interface GigabitEthernet0/0/1
  mtu 9000                   ! MTU L3
  ip mtu 9000
exit
system mtu 9216             ! Global L2 MTU Switch

# Menampilkan tabel L2 (CAM Table):
show mac address-table dynamic

# Menampilkan tabel L3 (CEF Table):
show ip cef

# -------------------------------------------------------------
# Arista EOS
# -------------------------------------------------------------
# Mengubah MTU:
configure
 interface Ethernet1
  mtu 9214
exit

# Menampilkan counter drop L2/L3:
show interfaces Ethernet1 | grep -E "errors|drops"

# -------------------------------------------------------------
# Junos OS (Juniper)
# -------------------------------------------------------------
# Mengubah MTU:
set interfaces ge-0/0/0 mtu 9216
set interfaces ge-0/0/0 unit 0 family inet mtu 9000

# Verifikasi:
show interfaces ge-0/0/0 extensive | match MTU
```

---

### 17. Exercises & Hands-on Challenges

#### Lab 1: Analisis Header Enkapsulasi Dasar (Guided)
- **Tugas:** Buat satu antarmuka dummy di Linux, tetapkan alamat IP `10.99.99.1/24`, aktifkan tangkapan layar `tcpdump` secara terisolasi, dan kirimkan satu paket UDP menggunakan `netcat`.
- **Instruksi Eksekusi:**
  ```bash
  sudo ip link add dummy0 type dummy
  sudo ip link set dummy0 up
  sudo ip addr add 10.99.99.1/24 dev dummy0
  sudo tcpdump -XX -vv -i dummy0 -w lab1_capture.pcap &
  echo -n "LAYER_VERIFICATION" | nc -u -w1 10.99.99.2 9999
  sudo killall tcpdump
  ```
- **Kriteria Keberhasilan:** Ekstrak byte MAC tujuan, Source IP, Destination IP, Source Port, Destination Port, dan data string payload dari file `.pcap` menggunakan perintah `tshark` atau Wireshark.

#### Lab 2: Investigasi MTU Black Hole Simulatif (Semi-Guided)
- **Tugas:** Simulasikan skenario *Path MTU Black Hole* menggunakan Linux Network Namespaces.
- **Konfigurasi Lingkungan:**
  1. Buat 2 network namespace: `ns_client` dan `ns_server`.
  2. Sambungkan menggunakan veth pair dengan MTU link 1500 byte.
  3. Konfigurasi `iptables` di sisi bridge atau namespace penerima untuk menjatuhkan (*drop*) seluruh paket `ICMP destination-unreachable`.
  4. Ubah MTU antarmuka transit menjadi 1400 byte secara sepihak.
  5. Jalankan server HTTP (misal: `python3 -m http.server 8080`) di `ns_server` dan download berkas berukuran 5MB dari `ns_client`.
- **Kriteria Keberhasilan:** Buktikan transfer file mengalami kegagalan/hang via `curl`. Terapkan `tcp adjust-mss` atau turunkan MTU client secara tepat hingga proses transfer kembali bekerja 100%.

#### Lab 3: Rekonstruksi Custom Raw Frame (Open-Ended)
- **Tugas:** Gunakan bahasa pemrograman pilihan Anda (Python dengan Scapy, atau C menggunakan RAW Sockets `AF_PACKET`) untuk membuat dan mengirimkan paket valid yang lolos inspeksi switch:
  - Header L2: Ethernet II dengan tag 802.1Q (VLAN ID 50).
  - Header L3: IPv4 dengan TTL ganjil (misal 37) dan bit Don't Fragment (DF) diaktifkan.
  - Header L4: UDP dengan port asal 12345 dan port tujuan 54321.
  - Payload: SHA-256 hash dari hostname Anda saat ini.
- **Kriteria Keberhasilan:** Tangkap paket pada interface tujuan, buktikan validitas seluruh checksum (IP Checksum dan UDP Checksum) berstatus `Good` tanpa ada tanda komputasi `Incorrect`.

---

### 18. Verification Checklist
Gunakan checklist ini untuk validasi kesiapan teknis terkait pemrosesan layer sebelum mempromosikan perubahan jaringan ke lingkungan produksi:

- [ ] Nilai MTU diselaraskan secara konsisten dari server (NIC driver), switch fabric L2, hingga router gateway L3.
- [ ] Interface switch trunking yang dilewati payload memiliki ukuran minimum `MTU Host + 18 byte (Ethernet + Dot1Q)` atau `MTU Host + 22 byte (QinQ)`.
- [ ] Aturan firewall/access-list (ACL) tidak memblokir paket kendali esensial `ICMP Type 3, Code 4`.
- [ ] Fitur *TCP MSS Clamping* terkonfigurasi pada interface enkapsulasi (VPN, PPPoE, GRE, atau IPsec).
- [ ] Pengaturan Speed dan Duplex telah dinegosiasikan secara konsisten (`Auto-Negotiation` aktif di kedua ujung, atau `Hardcoded Full-Duplex` di kedua ujung).
- [ ] Counter L1/L2 interface (`CRC error`, `Frame runts`, `Giants`, `FCS errors`) pada router dan switch berada pada angka nol absolut selama proses uji beban.
- [ ] Mekanisme isolasi Layer 2 (seperti *Port Security* dan *BPDU Guard*) telah diaktifkan pada seluruh *edge access ports* server.

---

### 19. Key Takeaways
- Model OSI dan TCP/IP bukanlah teori statis, melainkan arsitektur penempatan batas komputasi dan pemrosesan data nyata di dalam CPU, memori (sk_buff), sistem bus (PCIe DMA), dan silikon jaringan (ASIC).
- Enkapsulasi adalah penambahan konteks/metadata yang dikonsumsi secara independen oleh entitas yang beroperasi pada layer bersangkutan: Switch transit memproses frame berdasarkan L2 header tanpa memodifikasi L3 header (kecuali saat menjalankan routing atau inter-VLAN traversal).
- Ketidakcocokan konfigurasi MTU antar-layer memicu degradasi tersembunyi (*silent drop*) yang sering kali menembus uji konektivitas dasar (ping kecil lolos, TCP connection establishment lolos, namun transmisi data produksi gagal).
- Troubleshooting presisi mengharuskan pemecahan simtoma dari layer fisik (L1) naik ke atas secara terstruktur (bottom-up), atau pembuktian hipotesis berbasis data inspeksi paket (*Packet-Never-Lies*).

---

### 20. Next Steps & Recommended Reading
- Lanjutkan ke **Bab 01 - Module 02: Physical Layer, Media Standards, Bit Synchronization, and Hardware Interfaces**.
- **RFC 791:** Internet Protocol Specification (Pelajari detail IP header structure dan mekanisme fragmentasi).
- **RFC 793:** Transmission Control Protocol Specification (Pelajari segmentasi data, Sequence numbers, dan flow control).
- **RFC 1191 & RFC 4821:** Path MTU Discovery and Packetization Layer Path MTU Discovery.
- Buku Referensi Inti: *"TCP/IP Illustrated, Volume 1: The Protocols"* oleh W. Richard Stevens.