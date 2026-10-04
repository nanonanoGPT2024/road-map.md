# Kurikulum Rekayasa Jaringan Enterprise
## Kategori: 05-DevOps-Cloud-and-SRE
### BAB 03: Layer 2 Switching, VLANs, Trunking, dan Spanning Tree
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Hardware Switching**: Membedakan arsitektur packet traversal berbasis ASIC (Application-Specific Integrated Circuit), TCAM (Ternary Content-Addressable Memory), MAC address table engine, dan ingress/egress pipeline.
2. **Menguasai Protokol Spanning Tree Lanjutan**: Merancang, mengonfigurasi, dan melakukan *troubleshooting* implementasi RSTP (IEEE 802.1w) dan MSTP (IEEE 802.1s) pada topologi *multi-vendor* skala enterprise.
3. **Mengimplementasikan Layer 2 Resiliency & Multi-Chassis Link Aggregation**: Membangun arsitektur loop-free aktif-aktif menggunakan MLAG (Multi-Chassis Link Aggregation) atau vPC (Virtual Port Channel) untuk mengeliminasi ketergantungan pada port-blocking STP.
4. **Mengeksekusi L2 Security Hardening & Blast Radius Containment**: Menerapkan pertahanan deterministik terhadap L2 attack vector menggunakan Root Guard, BPDU Guard, Loop Guard, Storm Control, Private VLANs (PVLAN), dan 802.1Q-in-Q (QinQ).
5. **Mendiagnosis Kegagalan Jaringan L2 Tingkat Lanjut**: Mengidentifikasi *silent failures*, *unidirectional links*, *MAC flapping*, dan *STP topology change storms* menggunakan analisis telemetri dan packet inspection.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Fundamental framing Ethernet IEEE 802.3 dan encapsulation tagging IEEE 802.1Q.
* Konfigurasi dasar VLAN, static trunking, dan dynamic trunking protocol (DTP) risks.
* Konsep dasar Spanning Tree Protocol (IEEE 802.1D: states, timers, root bridge election).
* Pengoperasian Network Operating System (NOS) enterprise (Cisco NX-OS / Arista EOS) via Command Line Interface (CLI).
* Pemahaman dasar tentang Linux network namespaces dan Containerlab/GNS3 untuk simulasi lab.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Hardware Ethernet Switch: Forwarding Engine & TCAM
Switch enterprise modern tidak memproses frame L2 via General-Purpose CPU. CPU (*Control Plane*) hanya menangani routing protocol, STP BPDU generation, SSH/SNMP, dan update FIB/MAC table. Jalur transmisi paket (*Data Plane* atau *Forwarding Plane*) dieksekusi sepenuhnya pada silicon switch ASIC.

```
       +-----------------------------------------------------------+
       |                  Control Plane (CPU)                      |
       |  [STP Engine]   [LACP Daemon]   [MAC Learning Control]   |
       +-----------------------------+-----------------------------+
                                     | PCI-e Bus / Interconnect
       +-----------------------------v-----------------------------+
       |                 Switching ASIC (Data Plane)               |
       |                                                           |
Ingress| +-----------+   +---------------+   +-------------------+ |Egress
Ports  | |  Ingress  |-->|  TCAM & MAC   |-->|   Packet Buffer   | |Ports
======>| |  Parser   |   | Table Lookup  |   |    (VoQ / SRAM)   |=====>
       | +-----------+   +---------------+   +-------------------+ |
       |       |                 |                     ^           |
       |       v                 v                     |           |
       | [Ingress ACL]    [VLAN VFP/IFP]---------------+           |
       +-----------------------------------------------------------+
```

1. **Ingress Pipeline Parser**: Saat frame tiba di PHY interface, parser mengekstrak L2 header (Preamble, DMAC, SMAC, 802.1Q tag, EtherType).
2. **MAC Table Lookups via Exact Match Engine**: SMAC dipelajari dan dicocokkan ke dalam Hash-based MAC Table. Jika SMAC belum ada atau port berubah, interrupt dikirim ke learning engine. DMAC dievaluasi untuk menentukan port tujuan egress. Jika DMAC berupa broadcast/unknown unicast, frame dikirim ke *Replication Engine* untuk *flooding*.
3. **TCAM (Ternary Content-Addressable Memory)**: Berbeda dengan RAM standar (yang hanya mencocokkan nilai biner `0` dan `1`), TCAM mendukung evaluasi state ketiga: *Don't Care* (`X`). TCAM digunakan untuk evaluasi Ingress/Egress ACL, VLAN translation, QoS classification, dan Private VLAN mapping secara paralel dalam 1 clock cycle (deterministic single-cycle latency, ~200-800 nanodetik).
4. **Virtual Output Queuing (VoQ) & Shared Memory**: Untuk mencegah *Head-of-Line (HoL) Blocking*, switch modern mengarahkan paket ke VoQ pada sisi ingress sebelum mentransfer frame melintasi *Switch Fabric* menuju egress port buffer.

#### 3.2. Spanning Tree Internals: 802.1D vs. 802.1w (RSTP) vs. 802.1s (MSTP)

##### IEEE 802.1w (Rapid Spanning Tree Protocol) State Machine
802.1D menggunakan timer-based convergence (MaxAge 20s + Listening 15s + Learning 15s = 50s). 802.1w memotong delay ini menggunakan **Proposal/Agreement Handshake** eksplisit berbasis sinkronisasi point-to-point.

* Port Roles di RSTP: Root Port, Designated Port, Alternate Port (backup untuk Root Port), Backup Port (backup untuk Designated Port pada shared collision domain).
* Port States di RSTP disederhanakan:
  * **Discarding** (menggabungkan Disabled, Blocking, Listening dari 802.1D)
  * **Learning** (membaca MAC address, belum meneruskan data)
  * **Forwarding** (operasional penuh)

```
Switch A (Root)                                Switch B (Non-Root)
   [Designated]                                    [Root Port]
        |                                               |
        |--- (1) Proposal (Role: Desg, State: Disc) --->|
        |                                               |
        |                                         [Block all non-edge]
        |                                         [ports (Sync Phase)]
        |                                               |
        |<-- (2) Agreement (Role: Root, State: Fwd) ----|
        |                                               |
   [Transitions                                    [Transitions
   immediately to                                  immediately to
    FORWARDING]                                     FORWARDING]
```

##### IEEE 802.1s (Multiple Spanning Tree Protocol - MSTP)
PVST+ (Cisco proprietary) menjalankan 1 instance STP per VLAN. Jika jaringan memiliki 1000 VLAN, switch harus mengirim dan memproses 1000 instance BPDU per interval `hello_time` (2 detik), yang menyebabkan CPU exhaustion pada scale-out infrastructure.
MSTP memisahkan VLAN dari STP instance dengan memetakan $N$ VLAN ke dalam $M$ **Spanning Tree Instances (MSTI)**, yang dilingkupi oleh sebuah **Common and Internal Spanning Tree (CIST)**:
$$\text{VLAN}_{1 \dots k} \longrightarrow \text{MSTI}_1$$
$$\text{VLAN}_{k+1 \dots n} \longrightarrow \text{MSTI}_2$$
MSTP Region didefinisikan secara identik di setiap switch melalui 3 atribut:
1. Region Name (karakter string hingga 32-byte).
2. Revision Number (integer 16-bit).
3. VLAN-to-Instance Mapping Hash Table (digest MD5 16-byte dari tabel konfigurasi).

#### 3.3. Multi-Chassis Link Aggregation (MLAG / vPC) vs. STP
Meskipun RSTP/MSTP mencegah loop, kedua protokol tersebut mematikan link redundan (membuat 50% link capacity menganggur/blocking). MLAG/vPC menghadirkan arsitektur aktif-aktif L2 tanpa blocking link dengan memvirtualisasikan Control Plane dari dua switch independen agar tampak sebagai satu *Logical Switch* di mata downstream client LACP (IEEE 802.1AX).

```
               +---------------------------------------+
               |         Keepalive Link (L3 UDP)       |
               +---------------------------------------+
               |                                       |
        +------v------+                         +------v------+
        |             |   Peer-Link (L2 Trunk)  |             |
        | MLAG Node A <=========================> MLAG Node B |
        |             |                         |             |
        +------+------+                         +------+------+
               \                                       /
                \   Port-Channel Member Links (Active)/
                 \                                   /
               +--v---------------------------------v--+
               |        Downstream Access Switch       |
               +---------------------------------------+
```

* **Peer-Link**: Membawa traffic sinkronisasi state kontrol (CFS - Cisco Fabric Services atau MLAG Control Protocol) serta data plane encapsulation jika terjadi *single-homed link failure*.
* **Peer-Keepalive Link**: Heartbeat Layer 3 (out-of-band) beroperasi via UDP untuk mendeteksi *Dual-Active/Split-Brain condition* ketika Peer-Link terputus total.
* **Loop Prevention Rule di MLAG**: Frame yang masuk dari Peer-Link **dilarang keras** diteruskan keluar melalui port aggregation yang terhubung ke MLAG peer yang sama, kecuali jika link downstream fisik pada peer tersebut mati. Aturan ini dieksekusi di level hardware switching ASIC.

#### 3.4. Advanced Isolation: Private VLANs (PVLAN) & 802.1Q-in-Q (QinQ)
* **Private VLANs**: Mempartisi broadcast domain Layer 2 primer menjadi sub-domain yang terisolasi tanpa memerlukan alokasi subnet IP tambahan.
  * **Primary VLAN**: Membawa traffic downstream dari Promiscuous port ke semua secondary ports.
  * **Isolated VLAN**: Interface di dalam VLAN ini sama sekali tidak dapat berkomunikasi satu sama lain di Layer 2; hanya dapat berkomunikasi dengan Promiscuous port.
  * **Community VLAN**: Interface di dalam VLAN ini dapat saling berkomunikasi satu sama lain, dan dapat berkomunikasi dengan Promiscuous port, namun terisolasi total dari Community VLAN lain.
  * **Promiscuous Port**: Terhubung ke router default gateway, firewall, atau core switch; dapat mengirim/menerima paket ke/dari semua port di Primary, Isolated, maupun Community VLAN.
* **802.1ad (QinQ)**: Menyediakan encapsulation *double-tagging*. Tag terluar (Service Tag / S-Tag, EtherType `0x88A8`) digunakan oleh network provider/backbone, sedangkan tag terdalam (Customer Tag / C-Tag, EtherType `0x8100`) mempertahankan isolasi VLAN kustomer secara transparan di atas shared core network.

---

### 4. Why & What

| Kebutuhan Enterprise | Teknologi Tradisional | Pendekatan Modern Enterprise | Mengapa Berubah? |
| :--- | :--- | :--- | :--- |
| **Pencegahan Loop L2** | 802.1D STP | RSTP (802.1w) / MSTP (802.1s) | Konvergensi 802.1D (30-50s) memicu TCP session drop dan database failure. RSTP/MSTP konvergen dalam sub-detik (<50-200ms). |
| **Pemanfaatan Link (Uplink Utilization)** | Active/Standby via STP | MLAG / Cisco vPC / LACP Min-Links | STP membuang 50% kapasitas bandwidth uplink karena status port *blocking*. MLAG menyajikan 100% throughput aktif-aktif. |
| **Skalabilitas STP di Data Center** | Per-VLAN STP (PVST+) | MSTP / EVPN-VXLAN Bridge Domains | PVST+ menghabiskan TCAM dan CPU control plane switch saat VLAN mencapai ratusan atau ribuan. MSTP mengelompokkannya secara ringkas. |
| **Isolasi Multi-Tenant L2** | Individual Subnetting /29 atau /30 | Private VLANs (PVLANs) | Menghemat alokasi IPv4 dan mengeliminasi kebutuhan inter-VLAN routing firewall overhead pada DMZ berskala besar. |
| **Proteksi Topologi Root** | Default Dynamic Negotiation | Root Guard + BPDU Guard + Loop Guard | Switch liar (*rogue switch*) atau salah colok kabel dapat membajak status Root Bridge dan menyebabkan denial-of-service instan. |

---

### 5. How (Workflow Detail)

#### Workflow 1: RSTP Synchronization & Rapid Transition Sequence
```
Edge Node                    Downstream Switch                      Root Bridge
   |                                 |                                    |
   |                                 |<--- BPDU with Proposal Flag -------|
   |                                 |     (Role: Designated, State: Discarding)
   |                                 |                                    |
   |                          [SYNC PROCESS]                              |
   |                          Semua non-edge ports                        |
   |                          ditempatkan ke DISCARDING                   |
   |                                 |                                    |
   |                                 |--- BPDU with Agreement Flag ------>|
   |                                 |    (Root port confirms Sync)       |
   |                                 |                                    |
   |                                 |<-- Transitions to FORWARDING ------|
   |                                 |    Root Bridge unblocks interface  |
   |                                 |                                    |
   |                          Downstream interface                        |
   |                          beralih ke FORWARDING                       |
```

#### Workflow 2: Penanganan TCN (Topology Change Notification) pada RSTP
1. Topologi berubah: Hanya switch yang mengalami *loss of connectivity* pada non-edge port yang berstatus Forwarding yang menginisiasi TC.
2. Switch tersebut menyalakan timer `tcWhile` ($2 \times \text{Hello Time}$) pada seluruh Designated port dan Root port-nya.
3. Switch langsung mem-flush MAC addresses yang terasosiasi dengan port-port tersebut dari MAC Address Table (hanya interface non-edge yang terdampak).
4. Switch mengirim BPDU dengan flag `TC` (*Topology Change*) aktif ke seluruh tetangganya.
5. Switch tetangga yang menerima paket ini langsung melakukan flush pada MAC table-nya (kecuali untuk MAC dari port penerima) dan menyebarkan TC ke port lainnya. Tidak ada lagi penundaan via TCN ke Root Bridge seperti era 802.1D.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengendalian Lalu Lintas Darurat
* **STP Tradisional (802.1D)**: Seperti jembatan putar yang ditutup selama 50 detik setiap kali ada insiden kecil untuk memastikan tidak ada mobil yang tabrakan.
* **RSTP (802.1w)**: Polisi lalu lintas di kedua sisi jembatan berkomunikasi langsung via radio dua arah (*Proposal/Agreement*). Jembatan hanya ditutup selama 50 milidetik saat konfirmasi visual tercapai.
* **MLAG / vPC**: Membangun jembatan layang ganda dua jalur independen yang beroperasi bersamaan. Truk tidak perlu berhenti; jika jalur kiri retak, rambu digital langsung mengarahkan seluruh beban ke jalur kanan secara otomatis tanpa menutup jembatan.
* **BPDU Guard**: Palang otomatis yang langsung menghancurkan kendaraan apa pun yang mencoba masuk melalui pintu darurat keluar.

```
       +-------------------------------------------------------------+
       |                  Root Bridge (Distribution-01)              |
       |                   Bridge Priority: 4096                     |
       +--------------+-------------------------------+--------------+
                      | Designated                     | Designated
                      | Port (Forwarding)              | Port (Forwarding)
                      |                                |
                      |                                |
                      v                                v
       +--------------+--------------+  Alternate/ +---+--------------+
       |   Access Switch 01          |  Discarding |   Access Switch 02  |
       |   Priority: 32768           |< - - - - - -|   Priority: 32768   |
       |   Root Port (Forwarding)    |  [BLOCKED]  |   Root Port (Fwd)   |
       +--------------+--------------+             +---+-------------+
                      |                                |
         BPDU Guard   | Edge Port (PortFast)           | Edge Port (PortFast)
           Enabled    |                                |   Enabled
                      v                                v
              [ Server Host A ]                [ Server Host B ]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Hardening Edge Port (Cisco NX-OS Syntax)
Konfigurasi dasar interface host-facing untuk mengamankan spanning tree:

```text
interface Ethernet1/10
  description SRV-APP-PROD-01
  switchport mode access
  switchport access vlan 100
  spanning-tree port type edge
  spanning-tree bpduguard enable
  no shutdown
```

#### 7.2. Practical Example: Advanced MSTP & MLAG Implementation (Arista EOS Syntax)

##### Konfigurasi Switch Arista 01 (MLAG Primary & MSTP Regional Master)
```text
!
vlan 10,20,30,4094
!
vlan 4094
   name MLAG_PEER_SYNC
   trunk group MLAG_CONTROL
!
spanning-tree mode mstp
spanning-tree mst configuration
   name REGION_PROD_DC1
   revision 1
   instance 1 vlan 10,20
   instance 2 vlan 30
!
spanning-tree mst 0-2 priority 4096
!
interface Port-Channel1000
   description MLAG_PEER_LINK_TO_SW02
   switchport mode trunk
   switchport trunk group MLAG_CONTROL
   switchport trunk allowed vlan 10,20,30,4094
   spanning-tree mst 0-2 cost 500
!
interface Ethernet49/1
   description PHY_INTERCONNECT_PEER_LINK_1
   channel-group 1000 mode active
!
interface Ethernet50/1
   description PHY_INTERCONNECT_PEER_LINK_2
   channel-group 1000 mode active
!
interface Vlan4094
   description MLAG_CONTROL_SVI
   ip address 10.255.255.1/30
   no autostate
!
mlag configuration
   domain-id DC1_AGG_CLUSTER
   local-interface Vlan4094
   peer-address 10.255.255.2
   peer-link Port-Channel1000
   reload-delay mlag 300
   reload-delay non-mlag 330
!
interface Port-Channel10
   description DOWNLINK_TO_ACCESS_SW03
   switchport mode trunk
   switchport trunk allowed vlan 10,20,30
   mlag 10
!
interface Ethernet1/1
   channel-group 10 mode active
!
interface Ethernet10/1
   description CORE_ROUTER_UPLINK
   switchport mode trunk
   spanning-tree guard root
!
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: "The Phantom Storm" pada Core Payment Processing Switch
* **Profil Infrastruktur**: Payment Gateway FinTech, 4 pair switch core & distribution (Cisco Nexus 9000), 120 switch access. Protokol L2: Cisco Rapid-PVST+.
* **Insiden**: Setiap hari Selasa pukul 03.00 WIB, terjadi degradasi transaksi selama 3 menit. Latensi melesat dari 5ms menjadi 2400ms, packet drop 42% pada VLAN payment (VLAN 500). CPU core switch melonjak ke 99%.
* **Investigasi Root-Cause**:
  1. Analisis Syslog menemukan pesan: `%STP-2-BRIDGE_ASSURANCE_UNIDIRECTIONAL_FAIL` dan `%ETH_PORT_CHANNEL-5-PORT_DOWN`.
  2. Ditemukan bahwa tim backup menjalankan automated SAN/NAS image synchronization besar-besaran tiap Selasa jam 03.00 via VLAN 500.
  3. Salah satu access switch lama (legacy) mengalami *software-driven control plane saturation* akibat buffer overrun.
  4. Karena CPU access switch kewalahan memproses frame backup, switch tersebut gagal mengirimkan BPDU selama rentang waktu $3 \times \text{Hello Interval}$ (6 detik).
  5. Switch distribution mengasumsikan port tetangga mati, mengubah state port blocking menjadi forwarding, dan memicu **Layer 2 Forwarding Loop** transien.
  6. Terjadi badai *broadcast storm* dan *MAC Address Table Thrashing (MAC Flapping)* ribuan kali per detik.
* **Mitigasi & Resolusi Arsitektur**:
  1. **Immediate Action**: Mengaktifkan `spanning-tree loopguard default` pada distribution switches. Loop Guard mencegah port alternate/backup bertransisi ke forwarding state jika BPDU berhenti diterima secara mendadak (memindahkan port ke *Loop-Inconsistent* state alih-alih Forwarding).
  2. **Architectural Redesign**:
     * Memigrasikan topologi distribusi dari L2 spanning-tree loop mesh menjadi **Routed Access (L3 down to Distribution/Access)**, mengisolasi boundary L2 hanya di lingkup top-of-rack switch.
     * Mengganti PVST+ ke **MSTP** untuk mengurangi utilisasi alokasi BPDU processing CPU switch hingga 80%.
     * Menerapkan **Storm Control** pada seluruh edge access ports:
       `storm-control broadcast level 0.5 0.2`
       `storm-control action trap`

---

### 9. Trade-offs

```
                                  L2 Architecture Matrix
      
            High +------------------------------------+
                 |                                    |
                 |                       [MLAG / vPC] |
                 |                       * Active/Active
                 |                       * Sub-50ms failover
                 |                       * High operational complexity
       Bandwidth |                                    |
      Efficiency |  [RSTP / MSTP]                     |
                 |  * 50% link blocked                |
                 |  * Simple Control Plane            |
                 |  * Vendor Interoperable            |
                 |                                    |
             Low +------------------------------------+
                 Low                             High
                           Complexity & Hardware Cost
```

| Kriteria | STP / RSTP (802.1w) | MSTP (802.1s) | MLAG / vPC | L3 Routed Access (No L2 Loop) |
| :--- | :--- | :--- | :--- | :--- |
| **Pemanfaatan Link** | Rendah (Active/Standby, 50% idle) | Menengah (Manual Traffic Engineering) | Maksimum (Aktif/Aktif 100%) | Maksimum (ECMP L3 load sharing) |
| **Waktu Konvergensi** | 1-2 detik (RSTP) | Sub-detik (~200ms - 1s) | Sub-50ms (LACP Link Aggregation) | Sub-200ms (BFD + OSPF/BGP) |
| **Kompleksitas Desain** | Sangat Rendah | Menengah (Region & Digest mapping) | Tinggi (Sync state, dual-active guard) | Tinggi (Subnet sprawl, no L2 adjacency) |
| **Beban Control Plane CPU** | Tinggi pada Skala Besar (PVST+) | Sangat Rendah | Menengah | Sangat Rendah |
| **Ketergantungan Vendor** | Tidak Ada (Standard IEEE) | Rendah (Standar IEEE) | Sangat Tinggi (Proprietary per vendor) | Tidak Ada (IETF IP standard) |
| **Kebutuhan Lisensi/Biaya** | Nol (Semua hardware mendukung) | Nol | Mahal (Perlu enterprise hardware switch) | Menengah/Tinggi |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi:
1. **BPDU Filter Aktif di Port Edge yang Terhubung ke Switch Lain**:
   * *Problem*: `spanning-tree bpdufilter enable` mematikan pengiriman dan penerimaan BPDU secara total. Jika dua switch tidak sengaja terhubung via interface ini, loop L2 katastropik langsung terjadi tanpa mitigasi otomatis.
   * *Fix*: Gunakan `spanning-tree bpduguard enable`, bukan BPDU Filter pada port yang ditujukan untuk end-host.
2. **Native VLAN Mismatch pada 802.1Q Trunk**:
   * *Problem*: Switch A memiliki Native VLAN 1, Switch B memiliki Native VLAN 99. Traffic tanpa tag dari VLAN 1 dialihkan masuk ke VLAN 99 pada Switch B. Hal ini mengakibatkan kebocoran security boundary dan spanning tree inconsistently blocked states.
3. **PVID (Port VLAN ID) Leakage pada MSTP**:
   * *Problem*: Konfigurasi digest MSTI tidak sinkron (misal: Region Name typo pada 1 node). Switch langsung menurunkan mode interaksinya ke CIST/802.1D boundary mode, memblokir seluruh VLAN di dalam instance tersebut secara acak.

#### Prosedur Troubleshooting Terstruktur

##### Langkah 1: Deteksi MAC Flapping
Jika traffic terasa lambat dan intermiten, periksa syslog untuk mengidentifikasi osilasi loop L2:
```bash
# Cisco IOS/NX-OS
show logging | grep -i "flapping"
# Output tipikal:
# %SW_MATM-4-MACFLAP_NOTIF: Host 0050.56a1.2b3c in vlan 10 is flapping between port Eth1/2 and port Eth1/5
```

##### Langkah 2: Audit Perubahan Topologi Spanning Tree
Identifikasi switch mana yang terus-menerus memicu Topology Change Notification (TCN):
```text
Arista-EOS# show spanning-tree detail | grep -E "(from|occurs|is currently)"
  The Root is 4096.001c.7321.89ab
  Port 1 (Ethernet1/1) of MST0 is designated forwarding
  Number of topology changes 1482 last seen 12s ago
  Topology change flag is set, flag counter is 3
```
*Jika counter topology changes terus bertambah setiap beberapa detik, jalankan trace ke interface yang melaporkan `last topology change received`.*

##### Langkah 3: Menggunakan Packet Capture untuk Analisis BPDU
Verifikasi apakah BPDU dikirim secara konsisten pada link trunk bermasalah menggunakan utility internal switch (Ethanalyzer di NX-OS atau TCPDump di EOS):
```bash
# NX-OS Packet Capture khusus BPDU Frame
ethanalyzer local interface inband display-filter "eth.dst == 01:80:c2:00:00:00" limit-captured-frames 5
```

---

### 11. Best Practices (Production Checklist)

#### Pre-Deployment Architecture Checklist
- [ ] Nonaktifkan Dynamic Trunking Protocol (`switchport nonegotiate`) di seluruh port trunk.
- [ ] Ubah default native VLAN dari VLAN 1 ke VLAN non-fungsional khusus (misal: VLAN 999).
- [ ] Tentukan Root Bridge dan Secondary Root Bridge secara eksplisit menggunakan priority value manual (`spanning-tree mst 0 priority 4096`, `priority 8192`). Jangan pernah bergantung pada random low MAC address election!
- [ ] Lakukan explicit VLAN pruning pada seluruh link trunk (`switchport trunk allowed vlan 10,20`). Jangan pernah membuka akses `1-4094` pada trunk produksi.

#### Hardening Configuration Checklist
- [ ] **BPDU Guard**: Diaktifkan secara global atau per-interface di seluruh access ports (`spanning-tree portfast bpduguard default`).
- [ ] **Root Guard**: Diaktifkan di seluruh switch distribution/access port yang mengarah ke switch downstream (`spanning-tree guard root`).
- [ ] **Loop Guard**: Diaktifkan pada link point-to-point inter-switch non-designated (`spanning-tree loopguard default`).
- [ ] **Storm Control**: Batasi broadcast dan multicast thresholds hingga maksimal 1% - 5% dari total link speed capacity di edge switches:
  ```text
  interface range GigabitEthernet1/0/1-48
    storm-control broadcast level 1.0 0.5
    storm-control multicast level 2.0 1.0
    storm-control action trap
  ```
- [ ] **UDLD (Unidirectional Link Detection)**: Aktifkan mode `aggressive` pada interface fiber optik untuk mencegah link L1 half-dead memicu forwarding loop.

---

### 12. Hands-on Practice

Simulasi ini dirancang untuk dijalankan menggunakan arsitektur modular yang kompatibel dengan Arista cEOS atau Cisco IOL di Containerlab / EVE-NG.

Simpan seluruh file praktikum pada path: `hands-on/m02/`

#### 12.1. File Topologi: `hands-on/m02/topology.clab.yml`
```yaml
name: enterprise-l2-lab
topology:
  nodes:
    dist-sw01:
      kind: arista_ceos
      image: ceos:4.30.0F
    dist-sw02:
      kind: arista_ceos
      image: ceos:4.30.0F
    access-sw01:
      kind: arista_ceos
      image: ceos:4.30.0F
    srv-host01:
      kind: linux
      image: alpine:latest

  links:
    - endpoints: ["dist-sw01:eth1", "dist-sw02:eth1"]
    - endpoints: ["dist-sw01:eth2", "dist-sw02:eth2"]
    - endpoints: ["dist-sw01:eth3", "access-sw01:eth1"]
    - endpoints: ["dist-sw02:eth3", "access-sw01:eth2"]
    - endpoints: ["access-sw01:eth10", "srv-host01:eth1"]
```

#### 12.2. Langkah Implementasi Terpandu

##### Langkah 1: Bangun Lab
```bash
cd hands-on/m02/
sudo containerlab deploy -t topology.clab.yml
```

##### Langkah 2: Konfigurasi MSTP di Access Switch 01
Eksekusi konfigurasi berikut pada console `access-sw01`:
```text
enable
configure terminal
vlan 10,20
!
spanning-tree mode mstp
spanning-tree mst configuration
   name REGION_CORP
   revision 1
   instance 1 vlan 10
   instance 2 vlan 20
!
interface Ethernet1
   description UPLINK_DIST_01
   switchport mode trunk
   switchport trunk allowed vlan 10,20
!
interface Ethernet2
   description UPLINK_DIST_02
   switchport mode trunk
   switchport trunk allowed vlan 10,20
!
interface Ethernet10
   description HOST_PORT
   switchport mode access
   switchport access vlan 10
   spanning-tree portfast
   spanning-tree bpduguard enable
exit
```

##### Langkah 3: Konfigurasi Primary dan Secondary Root pada Switch Distribution
Pada `dist-sw01`:
```text
enable
configure terminal
spanning-tree mode mstp
spanning-tree mst configuration
   name REGION_CORP
   revision 1
   instance 1 vlan 10
   instance 2 vlan 20
!
spanning-tree mst 0-2 priority 4096
```

Pada `dist-sw02`:
```text
enable
configure terminal
spanning-tree mode mstp
spanning-tree mst configuration
   name REGION_CORP
   revision 1
   instance 1 vlan 10
   instance 2 vlan 20
!
spanning-tree mst 0-2 priority 8192
```

##### Langkah 4: Uji Proteksi BPDU Guard
Simulasikan serangan rogue switch yang mengirim BPDU ke host port:
1. Akses terminal `srv-host01`:
```bash
docker exec -it enterprise-l2-lab-srv-host01 sh
apk add scapy python3
```
2. Jalankan script injeksi raw BPDU frame:
```python
# Save as inject_bpdu.py inside container
from scapy.all import *
pkt = Ether(dst="01:80:c2:00:00:00", src="00:11:22:33:44:55")/LLC(dsap=0x42, ssap=0x42, ctrl=3)/STP(rootid=0, bridgeid=0)
sendp(pkt, iface="eth1", count=5)
```
```bash
python3 inject_bpdu.py
```
3. Amati log di `access-sw01`:
```text
show log
! Expected verification output:
! %SPANTREE-2-BPDUGUARD_TRIGGERED: BPDU received on port Ethernet10 with BPDU Guard enabled. Disabling port.
show interfaces Ethernet10 status
! Port must be in 'errdisabled' state
```

---

### 13. Exercise

#### Level Easy
Terdapat switch yang baru diinstalasi. Port trunk antar switch mengalami kondisi di mana seluruh traffic pada VLAN 50 tidak dapat lewat, padahal konfigurasi interface trunk sudah `switchport mode trunk`.
* **Tugas**: Tuliskan langkah diagnosis menggunakan perintah CLI EOS/IOS untuk mengecek status operasional VLAN, spanning tree state pada VLAN tersebut, dan trunk allowed list.

#### Level Medium
Sebuah perusahaan menggunakan MSTP dengan 2 instance:
* MSTI 1 melayani VLAN 100-199
* MSTI 2 melayani VLAN 200-299
* **Tugas**: Rancang konfigurasi switch Arista/Cisco untuk membuat `Core-01` menjadi Root Bridge untuk MSTI 1 dan Secondary untuk MSTI 2, sementara `Core-02` menjadi Root Bridge untuk MSTI 2 dan Secondary untuk MSTI 1. Pastikan kedua switch berbagi *configuration digest* yang identik.

#### Level Hard
Dua switch MLAG peer terhubung melalui port-channel dual 40GbE. Link L3 Keepalive terputus (*cable fault*), namun Peer-Link 40GbE tetap menyala normal. Lima menit kemudian, kabel optik Peer-Link tidak sengaja terputus total oleh teknisi data center.
* **Tugas**: Analisis kondisi failure mode yang terjadi. Tentukan status interface pada Secondary Peer jika fitur auto-isolation terpicu, dan jelaskan langkah recovery secara urut agar tidak terjadi pemutusan koneksi total pada downstream server (*Dual-Active prevention breakdown*).

---

### 14. Challenge

#### Skenario Kasus Kompleks: "The Silent Asymmetric Inter-DC Loop"
Anda bertindak sebagai Principal Network Infrastructure Engineer di bank multinasional. Dua data center (DC-A dan DC-B) dihubungkan menggunakan Dark Fiber L2 DCI (Data Center Interconnect).
* **Kondisi Awal**:
  * Kedua DC mengoperasikan MLAG pada access-distribution layer.
  * DCI Trunk membawa ratusan VLAN, termasuk VLAN database sync (VLAN 300).
  * Tim Network melakukan integrasi dengan cloud provider melalui colocation edge switch pihak ketiga yang tidak mendukung protokol STP vendor Anda secara langsung (beroperasi dalam mode STP Transparent / 802.1D PVST fallback).
* **Insiden**:
  * Tiba-tiba terjadi *Asymmetric Forwarding Failure*: Sebuah transceiver optik pada trunk inter-DC mengalami kerusakan laser Tx, namun receiver Rx masih membaca light level normal (-9 dBm).
  * Switch DC-A tetap menganggap link menyala (Port Up/Down), sementara Switch DC-B menyatakan port down.
  * STP BPDU dari DC-A berhenti masuk ke DC-B, namun data frame satu arah masih membanjiri link.
  * Mekanisme STP normal gagal memblokir port, memicu broadcast radiation yang melumpuhkan storage cluster di kedua data center secara simultan.
* **Tantangan**:
  1. Rancang arsitektur L2 hardening pertahanan berlapis tanpa mematikan link DCI.
  2. Susun konfigurasi konkrit yang mengintegrasikan kombinasi **UDLD Aggressive**, **Loop Guard**, **STP Dispute Mechanism**, dan **LACP Standby timers**.
  3. Buktikan secara matematis dan teoritis state machine mengapa UDLD Aggressive dikombinasikan dengan Loop Guard dapat mendeteksi kondisi ini di bawah rentang waktu 7 detik sebelum broadcast storm merusak buffer memory hardware ASIC switch.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic
1. Apa fungsi utama dari nilai *Bridge Priority* dalam pemilihan Root Bridge pada Spanning Tree Protocol?
   * A. Menentukan kecepatan transmisi interface switch.
   * B. Menentukan switch mana yang memiliki hak administratif tertinggi untuk menjadi pusat pohon topologi L2.
   * C. Mengatur bandwidth maksimum LACP.
   * D. Mengidentifikasi port mana yang akan menerapkan enkapsulasi 802.1Q.
   *(Jawaban: B - Bridge Priority dikombinasikan dengan MAC Address membentuk Bridge ID. Nilai numerik terkecil terpilih menjadi Root Bridge).*

2. State Spanning Tree standar IEEE 802.1D yang dihilangkan dan fungsinya diserap oleh state "Discarding" pada IEEE 802.1w (RSTP) adalah:
   * A. Listening, Learning, Blocking
   * B. Disabled, Blocking, Listening
   * C. Listening, Learning, Forwarding
   * D. Forwarding, Blocking, Disabled
   *(Jawaban: B - RSTP merampingkan Disabled, Blocking, dan Listening menjadi satu state tunggal: Discarding).*

3. Berapakah batas default interval timer *Topology Change Notification (tcWhile)* pada protokol RSTP?
   * A. $2 \times \text{Hello Time}$
   * B. 30 detik
   * C. MaxAge + Forward Delay
   * D. 15 detik
   *(Jawaban: A - Di RSTP, timer `tcWhile` didefinisikan sebesar dua kali Hello Time).*

4. Manakah fitur L2 protection yang berfungsi untuk mematikan interface secara otomatis jika menerima BPDU pada port yang dikonfigurasikan sebagai port host?
   * A. Root Guard
   * B. Loop Guard
   * C. BPDU Guard
   * D. Storm Control
   *(Jawaban: C - BPDU Guard segera menempatkan port ke status `errdisable` bila menerima frame BPDU).*

5. Berapakah panjang bit field VLAN Identifier (VID) standar yang dialokasikan di dalam encapsulation header IEEE 802.1Q?
   * A. 8 bit
   * B. 12 bit
   * C. 16 bit
   * D. 32 bit
   *(Jawaban: B - 12 bit menghasilkan rentang $2^{12} = 4096$ VLAN ID).*

#### Soal Intermediate
6. Pada saat implementasi Multiple Spanning Tree Protocol (MSTP), apa yang menyebabkan dua switch yang terhubung fisik gagal membentuk Region yang sama dan justru terpecah menjadi boundary yang berbeda?
   * A. Nilai Bridge Priority MST instance 0 berbeda antar kedua switch.
   * B. Salah satu switch memiliki IP management yang berada di subnet yang berbeda.
   * C. Ketidakcocokan salah satu atribut: Region Name, Revision Number, atau Digest MD5 dari VLAN mapping table.
   * D. Menggunakan interface optic multi-mode alih-alih single-mode.
   *(Jawaban: C - MST Region didefinisikan secara identik hanya jika Region Name, Revision, dan VLAN-instance mapping table hash persis sama).*

7. Dalam arsitektur MLAG/vPC, mengapa downstream traffic yang masuk ke Switch Peer B melalui Peer-Link dicegah untuk diteruskan ke downstream port-channel menuju access switch?
   * A. Karena downstream port-channel pada Switch B otomatis berstatus blocking oleh STP.
   * B. Untuk mematuhi MLAG Data-Plane Loop Prevention Rule, karena frame diasumsikan telah direplikasi/diteruskan oleh Switch Peer A.
   * C. Karena MTU pada Peer-Link selalu lebih kecil dibanding downlink interface.
   * D. Karena CPU switch B tidak dapat membaca frame enkapsulasi LACP.
   *(Jawaban: B - Switch ASIC MLAG memiliki aturan isolasi lokal untuk mencegah duplikasi frame atau L2 loop).*

8. Apa perbedaan teknis fundamental antara peran port *Alternate* dan *Backup* pada IEEE 802.1w?
   * A. Alternate port mencadangkan Root Port; Backup port mencadangkan Designated port pada shared multi-access segment yang sama.
   * B. Alternate port digunakan untuk VLAN ganjil; Backup port digunakan untuk VLAN genap.
   * C. Alternate port berada dalam kondisi Forwarding; Backup port berada dalam status Discarding.
   * D. Alternate port hanya berfungsi di kabel fiber; Backup port hanya di twisted-pair.
   *(Jawaban: A - Alternate port bertindak sebagai path alternatif menuju Root Bridge, sedangkan Backup port mencadangkan interface designated pada media shared collision/hub domain).*

9. Apa yang terjadi jika fitur *Root Guard* dikonfigurasi pada sebuah interface dan interface tersebut menerima BPDU superior dari switch tetangga?
   * A. Interface langsung mengalami `errdisable` permanen dan membutuhkan manual recovery.
   * B. Interface bertransisi ke kondisi `root-inconsistent` dan memblokir seluruh traffic data hingga BPDU superior berhenti dikirim.
   * C. Interface secara paksa mengubah dirinya menjadi Root Port.
   * D. Switch langsung melakukan reload operating system untuk proteksi memori.
   *(Jawaban: B - Root Guard menaruh port ke mode *root-inconsistent* (blocking L2 traffic) secara otomatis tanpa me-nonaktifkan layer fisik link).*

10. Mengapa fitur Private VLAN (PVLAN) jenis *Isolated* sangat efisien dalam arsitektur hosting multi-tenant dibanding regular VLAN?
    * A. Karena isolated port mengenkripsi seluruh payload layer 2 via hardware AES.
    * B. Memungkinkan ratusan server berbagi satu subnet IP dan default gateway yang sama tanpa kemampuan saling membajak (*sniffing/spoofing*) satu sama lain di Layer 2.
    * C. Isolated port mematikan pengecekan ARP request oleh router.
    * D. Mempercepat throughput interface menjadi dua kali lipat.
    *(Jawaban: B - Menghemat alokasi subnet IP secara drastis seraya mempertahankan isolasi broadcast domain antar server).*

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah switch access Cisco Catalyst terhubung ke workstation pengguna. Administrator jaringan mengaktifkan perintah `spanning-tree portfast` dan `spanning-tree bpdufilter enable` pada interface tersebut. Pengguna kemudian membawa switch rumahan 5-port tanpa konfigurasi dan menghubungkan dua port switch access tersebut menggunakan switch rumahan tersebut. Mengapa broadcast storm tetap terjadi dan melumpuhkan distribution switch?
    * *Analisis*: `spanning-tree bpdufilter enable` yang dikonfigurasi secara manual pada tingkat interface menghentikan port dari mengirimkan DAN memproses BPDU masuk. Karena tidak ada BPDU yang didengarkan, mekanisme spanning tree lumpuh total pada port tersebut, dan BPDU Guard tidak dapat mendeteksi adanya switch liar. Loop fisik tercipta dan broadcast traffic meledak seketika tanpa ada mekanisme proteksi yang memblokir link.

12. **Skenario 2**: Dua core switch Arista terhubung via MLAG. Operator jaringan melakukan migrasi penambahan VLAN 400. Operator menambahkan VLAN 400 pada `switchport trunk allowed vlan` di switch MLAG-01, namun lupa mengeksekusinya di switch MLAG-02. Apa dampak teknis yang akan dialami oleh server downstream yang terhubung via dual-homed LACP active-active?
    * *Analisis*: Traffic downstream dari server yang di-hashing oleh algoritma LACP (misal: src-dst IP hash) menuju MLAG-02 akan di-drop secara silent pada VLAN 400 karena interface MLAG-02 tidak mengizinkan VLAN tersebut. Akibatnya, konektivitas server mengalami *intermittent packet loss 50%* tergantung pada jalur port-channel hashing member mana yang dipilih untuk melewatkan frame data.

13. **Skenario 3**: Sebuah link fiber antar-gedung 10Gbps menggunakan single-mode optic mengalami penurunan kualitas fisik di mana serat kabel penerima (Rx) mengalami degradation bend loss yang parah, sehingga switch lokal sering mendeteksi *loss of signal* intermiten mikrodetik (flapping). Fitur keamanan L2 apa saja yang wajib dirangkai bersama untuk mencegah fluktuasi topologi STP yang merusak performa core network?
    * *Analisis*: Solusinya adalah merangkai tiga fitur:
      1. **UDLD Mode Aggressive**: Untuk mendeteksi kondisi koneksi satu arah atau intermiten loss of handshake dan mematikan port secara deterministik.
      2. **Loop Guard**: Mencegah port alternate/backup mengambil alih status designated forwarding saat BPDU hilang secara semu akibat link flapped.
      3. **Carrier-delay / Link Debounce Timer**: Menunda deklarasi link-up/down di level kernel interface driver selama ~1-2 detik untuk meredam osilasi fluktuasi optik transien sebelum diteruskan ke spanning tree engine.

---

### 16. Summary

Implementasi Layer 2 enterprise modern telah bergeser dari sekadar mencegah loop secara reaktif menggunakan legacy STP 802.1D menuju arsitektur resilien berperforma tinggi dan berlatensi deterministik:
* **ASIC Forwarding**: Memahami bahwa data plane diproses via hardware pipeline (TCAM & Exact-Match tables) sedangkan control plane STP/LACP dijalankan via switch CPU.
* **Protokol Standar Modern**: Penggunaan **MSTP (802.1s)** menyelesaikan masalah resource exhaustion pada skala ribuan VLAN dengan mengelompokkan VLAN ke dalam instance-instance independen secara efisien.
* **Active-Active Forwarding**: **MLAG / vPC** mengeliminasi kelemahan klasik STP yang mematikan link redundan, memaksimalkan throughput agregat uplink hingga 100%, serta membatasi waktu *failover recovery* hingga ke level sub-50 milidetik.
* **Defense-in-Depth L2 Hardening**: Jaringan enterprise wajib menerapkan **Root Guard** (arah core-to-access), **BPDU Guard** (arah access-to-host), **Loop Guard** (pada internal blocking links), serta **Storm Control** untuk meminimalisasi *blast radius* dan mencegah insiden broadcast storm yang berpotensi melumpuhkan data center.