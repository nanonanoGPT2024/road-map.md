# Modul 01: Layer 2 Switching, Enterprise VLANs, Trunking, dan Spanning Tree

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis struktur biner Ethernet II Frame dan tag IEEE 802.1Q pada tingkat byte/packet capture.
- Menjelaskan siklus hidup entri Forwarding Information Base (FIB) / Content Addressable Memory (CAM) Table, termasuk fenomena flooding, aging out, dan deteksi MAC address flapping.
- Mengonfigurasi dan memvalidasi segmentasi VLAN enterprise, native VLAN security, serta trunking dynamic maupun static.
- Membedakan mekanisme konvergensi antara IEEE 802.1D (STP), IEEE 802.1w (RSTP), dan IEEE 802.1s (MSTP).
- Mengimplementasikan fitur proteksi STP tingkat enterprise: BPDU Guard, Root Guard, dan Loop Guard untuk mengamankan topologi Layer 2 dari anomali loop dan serangan bridge priority hijacking.
- Mendiagnosis dan mengonfigurasi Link Aggregation Control Protocol (LACP IEEE 802.3ad/802.1ax) serta menganalisis efisiensi hash distribution algoritma load balancing.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Model Referensi OSI 7 Layer (fokus pada Layer 1 Physical dan Layer 2 Data Link).
- Representasi biner dan heksadesimal serta manipulasi bitmask.
- Karakteristik media fisik: kabel Twisted Pair (Cat5e/6/6A), fiber optic (Single-Mode dan Multi-Mode), SFP/SFP+ transceiver.
- Penggunaan dasar CLI perangkat jaringan (Cisco IOS/NX-OS, Arista EOS, atau Linux bridge-utils/iproute2).

---

## 3. Concept
Layer 2 Switching adalah fondasi pertukaran data dalam Local Area Network (LAN). Switch bekerja sebagai jembatan multiport yang memisahkan collision domain pada setiap port secara independen, namun secara default tetap berada dalam satu broadcast domain yang sama. 

Untuk membatasi ukuran broadcast domain, mengisolasi departemen kerja, dan menegakkan perimeter keamanan jaringan internal, digunakan Virtual Local Area Network (VLAN). Ketika lalu lintas VLAN harus melintasi batas fisik antar-switch, digunakan mekanisme *Trunking* dengan menambahkan tag IEEE 802.1Q pada Ethernet frame. 

Namun, topologi switch fisik yang memiliki redundansi link untuk toleransi kegagalan (high availability) secara inheren menciptakan risiko terjadinya loop fisik. Tanpa mekanisme pencegahan, frame broadcast/unknown-unicast akan berputar tanpa henti, memicu *Broadcast Storm* dan melumpuhkan jaringan dalam hitungan detik. 

Spanning Tree Protocol (STP) dan evolusinya (RSTP, MSTP) bekerja secara terdistribusi untuk memutus loop tersebut dengan menonaktifkan jalur redundan secara logis (blocking/discarding), sambil tetap mempertahankan kemampuan failover otomatis jika jalur aktif mengalami putus koneksi. Untuk meningkatkan throughput dan redundansi tanpa diblokir oleh STP, beberapa link fisik dapat digabungkan secara logis menggunakan Link Aggregation (LACP).

---

## 4. Why
Mengapa Network Engineer dan Site Reliability Engineer (SRE) harus menguasai detail Layer 2 hingga tingkat frame dan state machine?

1. **Pencegahan Outage Katastropik**: Kesalahan konfigurasi Layer 2 (seperti STP misconfiguration atau kabel loop di switch unmanaged) dapat meruntuhkan seluruh data center melalui broadcast storm, memicu 100% CPU utilization pada switch dan router gateway, serta melumpuhkan control plane.
2. **Kinerja Latensi Rendah**: Pemahaman terhadap CAM table overflow dan unknown unicast flooding sangat krusial; ketika switch kehabisan ruang CAM, switch akan bertindak seperti hub (flooding semua paket ke semua port), yang mengakibatkan degradasi performa drastis dan kebocoran data (security breach).
3. **Efisiensi Inter-Switch Link**: Tanpa trunking dan LACP yang terkalibrasi dengan baik, agregasi bandwidth antar rack (Top-of-Rack ke Spine/Aggregation) akan timpang akibat ketidakseimbangan hashing pada frame Ethernet.
4. **Keamanan Perimeter Internal**: Serangan seperti VLAN Hopping (via Double Tagging atau DTP spoofing) dan Rogue Root Bridge injection dapat membelokkan seluruh alur lalu lintas data center ke node penyerang (Man-in-the-Middle) jika fitur proteksi Layer 2 tidak diaktifkan.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Anatomi Ethernet II Frame & 802.1Q Tagging
Ethernet II frame standar memiliki struktur tanpa tag sebesar minimum 64 byte dan maksimum 1518 byte (tanpa jumbo frame):

```
+----------+--------+-------------------+-------------------+-----------+----------------+----------+
| Preamble |  SFD   | Destination MAC   |    Source MAC     | EtherType |    Payload     |   FCS    |
| (7 Byte) | (1 B)  |     (6 Byte)      |     (6 Byte)      |  (2 Byte) | (46-1500 Byte) | (4 Byte) |
+----------+--------+-------------------+-------------------+-----------+----------------+----------+
```

Ketika frame melewati port 802.1Q trunk, switch menyisipkan header 4-byte (VLAN Tag) tepat di antara *Source MAC* dan *EtherType*:

```
+-----------------------------------+-----------------------------------+
|  TPID (Tag Protocol Identifier)   |     TCI (Tag Control Information) |
|           0x8100 (16-bit)         |               (16-bit)            |
+-----------------------------------+---+---+---------------------------+
|                                   |PCP|DEI|       VID (VLAN ID)       |
|                                   |3 b|1 b|          12-bit           |
+-----------------------------------+---+---+---------------------------+
```
- **TPID (16-bit)**: Bernilai `0x8100`, mengidentifikasi bahwa frame ini diberi tag 802.1Q.
- **PCP (Priority Code Point, 3-bit)**: Menentukan prioritas frame untuk Quality of Service (QoS IEEE 802.1p, nilai 0–7).
- **DEI (Drop Eligible Indicator, 1-bit)**: Mengindikasikan apakah frame boleh didrop jika terjadi kongesti.
- **VID (VLAN Identifier, 12-bit)**: Menentukan identitas VLAN (rentang nilai 0 hingga 4095; VID 0 dan 4095 direservasi, VID 1 adalah default VLAN, 1–4094 usable).

### 5.2 Siklus Hidup CAM Table (MAC Address Table)
Switch membangun tabel relasi antara MAC Address, VLAN ID, dan port fisik menggunakan proses tiga langkah:
1. **Source Learning**: Setiap frame yang masuk diperiksa *Source MAC*-nya. Switch mencatat pasangan `(Source MAC, Ingress VLAN, Ingress Port)` ke CAM Table dengan timer aging (default 300 detik).
2. **Forwarding/Filtering Decision**: Switch memeriksa *Destination MAC (DMAC)*:
   - Jika DMAC ada di CAM table pada VLAN yang sama: frame di-forward **hanya** ke port tujuan.
   - Jika DMAC adalah Unicast tetapi tidak terdaftar (Unknown Unicast): frame di-*flood* ke seluruh port dalam VLAN tersebut, **kecuali** ingress port.
   - Jika DMAC adalah Broadcast (`FF:FF:FF:FF:FF:FF`) atau Multicast: frame di-*flood* ke seluruh port dalam VLAN yang berhak menerimanya.
3. **Aging & Flushing**: Jika tidak ada frame baru dari Source MAC tersebut selama rentang waktu aging time, entri dihapus. Jika terjadi topologi change pada STP (TC-BPDU), aging time diturunkan sementara (misal menjadi forward delay time, 15 detik) untuk mempercepat pembersihan entri stale.

### 5.3 Spanning Tree Protocol: 802.1D vs 802.1w (RSTP) vs 802.1s (MSTP)
STP mencegah loop fisik dengan mengonstruksi topologi pohon logis bebas loop (loop-free tree).

#### Standar STP
1. **IEEE 802.1D (Legacy STP)**:
   - State: *Disabled* -> *Blocking* -> *Listening* -> *Learning* -> *Forwarding*.
   - Waktu konvergensi lambat: 30 hingga 50 detik (2x Forward Delay (15s) + Max Age (20s)).
2. **IEEE 802.1w (Rapid STP / RSTP)**:
   - State disederhanakan: *Discarding*, *Learning*, *Forwarding*.
   - Role port: *Root Port*, *Designated Port*, *Alternate Port* (backup Root Port), *Backup Port* (backup Designated Port).
   - Menggunakan mekanisme handshake **Proposal-Agreement** berbasis sinkronisasi link point-to-point full-duplex; konvergensi berlangsung sub-detik (< 1 detik).
3. **IEEE 802.1s (Multiple STP / MSTP)**:
   - Mengelompokkan ratusan/ribuan VLAN ke dalam beberapa instance STP logis (*MST Instances / MSTI*).
   - Mengatasi isu konsumsi CPU dan memori berlebih pada Per-VLAN Spanning Tree (PVST+ milik Cisco) pada skala enterprise.

#### Pemilihan Root Bridge
Root bridge dipilih berdasarkan **Bridge ID (BID)** terkecil:
$$\text{Bridge ID} = \text{Bridge Priority (4-bit, kelipatan 4096)} + \text{Extended System ID (12-bit VLAN ID)} + \text{MAC Address (48-bit)}$$
Switch dengan BID numerik terendah akan memenangkan pemilihan (*election*).

#### Penentuan Role Port
1. **Root Port (RP)**: Port pada switch non-root dengan akumulasi *Root Path Cost* terendah menuju Root Bridge. Jika cost sama: pilih upstream bridge ID terkecil, port priority terkecil, lalu internal port index terkecil.
2. **Designated Port (DP)**: Port pada segmen LAN yang memiliki Root Path Cost terendah menuju Root Bridge. Setiap segmen fisik hanya memiliki 1 DP. Seluruh port pada Root Bridge adalah DP.
3. **Alternate/Backup Port**: Port yang menerima BPDU superior tetapi tidak menjadi RP atau DP; port ini dialihkan ke state *Discarding* (blocking).

### 5.4 STP Protection Toolkit
- **PortFast / Edge Port**: Mengabaikan fase listening/learning langsung ke forwarding untuk port akses host/server. Tidak mengirim TCN BPDU saat link up/down.
- **BPDU Guard**: Menonaktifkan port (menempatkannya dalam state `err-disable`) secara instan jika menerima BPDU pada port yang dikonfigurasi PortFast. Mencegah penambahan switch unmanaged liar.
- **BPDU Filter**: Mengabaikan transmisi atau penerimaan BPDU pada port. *Peringatan*: Jika disalahgunakan, dapat langsung memicu loop fisik.
- **Root Guard**: Mencegah switch downstream mengambil alih peran Root Bridge. Jika switch menerima superior BPDU pada port yang diproteksi, port tersebut dimasukkan ke status `root-inconsistent` (blocking) hingga superior BPDU berhenti.
- **Loop Guard**: Mencegah Alternate Port atau Root Port berubah menjadi Designated Port saat link unidirectional failure terjadi (kehilangan BPDU secara mendadak tanpa link-down fisik). Menempatkan port ke dalam status `loop-inconsistent`.

### 5.5 Link Aggregation: EtherChannel & LACP (802.3ad / 802.1ax)
LACP menggabungkan hingga 16 link fisik (8 aktif, 8 standby) menjadi satu interface logis (Port-Channel) untuk melipatgandakan throughput dan menyediakan redundansi failover deterministik.
- **Mode LACP**:
  - *Active*: Memulai negosiasi LACP secara proaktif dengan mengirim LACP packet (LACPDU).
  - *Passive*: Hanya merespons paket LACPDU yang diterima, tidak memulai inisiasi.
- **Load Balancing Hash**: Paket didistribusikan ke member port menggunakan fungsi hash terdistribusi. Parameter hashing dapat dikonfigurasi berdasarkan:
  - `src-mac`, `dst-mac`, `src-dst-mac`
  - `src-ip`, `dst-ip`, `src-dst-ip`
  - `src-dst-port` (Layer 4 hash, mendistribusikan TCP/UDP flow secara optimal).

---

## 6. How
Implementasi Layer 2 Enterprise yang tangguh dilakukan melalui tahapan hierarkis:
1. **Perencanaan VLAN & IP Subnet**: Tentukan alokasi VID dan segmen jaringan (Management, Data, Voice, DMZ).
2. **Standardisasi STP**: Terapkan Rapid-PVST+ atau MSTP secara menyeluruh di seluruh domain switching.
3. **Determinisme Root Bridge**: Konfigurasikan Core/Distribution switch secara eksplisit sebagai Primary Root (Priority 4096 atau 0) dan Secondary Root (Priority 8192).
4. **Trunking Hardening**: Nonaktifkan DTP (Dynamic Trunking Protocol), tetapkan trunk secara statis, ganti Default Native VLAN (VLAN 1) ke VLAN transit yang tidak terpakai (misal VLAN 999), dan terapkan VLAN pruning (`allowed vlan`).
5. **Aktivasi Port Protection**: Aktifkan BPDU Guard dan PortFast secara default di seluruh access layer port.
6. **Agregasi Uplink**: Konfigurasi Port-Channel berbasis LACP Active-Active antar Distribution dan Access layer.

---

## 7. Analogy
Bayangkan jaringan Layer 2 sebagai **Gedung Perkantoran Raksasa**:
- **Ethernet Frame**: Dokumen surat resmi yang dikirimkan kurir internal.
- **MAC Address**: Nomor identitas meja kerja unik karyawan.
- **CAM Table**: Buku resepsionis yang mencatat: "Karyawan X berada di Meja Lantai 3, Sayap Kanan".
- **VLAN**: Departemen kantor (VLAN 10 = Keuangan, VLAN 20 = Legal). Meskipun ruangannya bersebelahan di lantai yang sama, karyawan Keuangan tidak dapat melihat dokumen Legal karena dinding kedap suara logis.
- **Trunk Link**: Lift khusus antar lantai. Setiap surat yang masuk ke lift diberi stempel warna stiker (*802.1Q Tag*) agar kurir di lantai tujuan tahu ke departemen mana dokumen tersebut dialokasikan.
- **Spanning Tree Protocol (STP)**: Tim Keselamatan dan Kesiapsiagaan Bencana yang mendeteksi pintu darurat ganda. Untuk mencegah kerumunan orang yang berlari berputar-putar tanpa akhir di lorong memutar (*Broadcast Storm*), tim mengunci sementara satu pintu cadangan (*Blocking*). Pintu cadangan baru dibuka secara otomatis jika pintu utama runtuh (*Failover*).
- **BPDU Guard**: Satpam di pintu ruang kerja pribadi. Jika ada orang asing datang membawa panduan denah gedung baru (mencoba menjadi Root Bridge palsu), satpam langsung mengunci ruangan tersebut dan menyalakan alarm (*err-disable*).
- **LACP**: Menggabungkan 4 jalur tol satu arah menjadi 4 lajur bebas hambatan paralel dengan palang tol otomatis; jika satu lajur ditutup karena perbaikan jalan, kendaraan tetap mengalir mulus melalui tiga lajur lainnya tanpa perlu memutar rute.

---

## 8. Diagram (ASCII)

### Topologi Redundan Enterprise Layer 2 & STP Blocking Logic

```
                     +---------------------------------------+
                     |         DISTRIBUTION SWITCH 1         |
                     |      (STP Root Bridge - Priority 4096)|
                     |      Bridge ID: 1000.00aa.bbcc.0001   |
                     +---------------------------------------+
                        | (DP)                       | (DP)
                        |                            |
       LACP Trunk       |                            |   LACP Trunk
   (Po1: Eth1/1-Eth1/2) |                            |  (Po2: Eth1/1-Eth1/2)
                        |                            |
                        | (RP)                       | (RP)
     +---------------------------+       ISL      +---------------------------+
     |       ACCESS SWITCH 1     |================|       ACCESS SWITCH 2     |
     |                           |  Trunk (Po3)   |                           |
     | Bridge ID:                | (DP)       (BLK| Bridge ID:                |
     | 8000.00aa.bbcc.0002       |             RP)| 8000.00aa.bbcc.0003       |
     +---------------------------+                +---------------------------+
          | (DP)            | (DP)                     | (DP)            | (DP)
       [PortFast]        [PortFast]                 [PortFast]        [PortFast]
     [BPDU Guard]      [BPDU Guard]               [BPDU Guard]      [BPDU Guard]
          |                 |                          |                 |
     +---------+       +---------+                +---------+       +---------+
     | Host A  |       | Host B  |                | Host C  |       | Host D  |
     | VLAN 10 |       | VLAN 20 |                | VLAN 10 |       | VLAN 20 |
     +---------+       +---------+                +---------+       +---------+
```

### Mekanisme 802.1Q Tag Insertion

```
Standard Untagged Frame:
+--------------+-------------+-----------+------------------------+-------+
|  Dest MAC    | Source MAC  | EtherType |        Payload         |  FCS  |
|   (6 Byte)   |  (6 Byte)   |  (2 Byte) |     (46-1500 Byte)     | (4 B) |
+--------------+-------------+-----------+------------------------+-------+
                                  |
               (Disisipkan saat melewati Trunk Port)
                                  v
802.1Q Tagged Frame:
+--------------+-------------+-----------+--------------------+-----------+------------------------+-------+
|  Dest MAC    | Source MAC  | 802.1Q Tag| TPID: 0x8100 (2 B) | EtherType |        Payload         |  FCS  |
|   (6 Byte)   |  (6 Byte)   |  (4 Byte) | TCI : PCP/DEI/VID  |  (2 Byte) |     (46-1500 Byte)     | (4 B) |
+--------------+-------------+-----------+--------------------+-----------+------------------------+-------+
```

---

## 9. Simple Example
Konfigurasi dasar pembuatan VLAN dan penetapan Access Port pada Cisco IOS:

```text
! 1. Membuat Database VLAN
Switch(config)# vlan 10
Switch(config-vlan)# name DATA_CORP
Switch(config-vlan)# exit

! 2. Menetapkan Access Port ke VLAN 10
Switch(config)# interface GigabitEthernet0/1
Switch(config-if)# description End-User_Workstation
Switch(config-if)# switchport mode access
Switch(config-if)# switchport access vlan 10
Switch(config-if)# spanning-tree portfast
Switch(config-if)# spanning-tree bpduguard enable
Switch(config-if)# no shutdown
```

---

## 10. Practical Example (Konfigurasi CLI Enterprise Lengkap)

Berikut adalah konfigurasi lengkap untuk arsitektur switch Distribution dan Access dengan standar enterprise tinggi:

### Switch Distribution (Root Bridge, LACP, RSTP)
```text
! Konfigurasi Spanning Tree Rapid-PVST dan Penentuan Root Bridge Deterministic
hostname DIST-SW-01
spanning-tree mode rapid-pvst
spanning-tree vlan 10,20,99 root primary
spanning-tree vlan 10,20,99 priority 4096
spanning-tree portfast default
spanning-tree portfast bpduguard default

! Definisi VLAN Enterprise
vlan 10
 name APPLICATION_SERVERS
vlan 20
 name DATABASE_SERVERS
vlan 99
 name NATIVE_TRANSIT_ISOLATED
vlan 999
 name SINKHOLE_UNUSED

! Konfigurasi LACP Port-Channel menuju Access Switch 1
interface Range GigabitEthernet1/0/1 - 2
 description UPLINK_TO_ACCESS-SW-01
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 99
 switchport trunk allowed vlan 10,20
 switchport nonegotiate
 channel-group 1 mode active
 no shutdown

interface Port-channel 1
 description AGGREGATED_TRUNK_TO_ACCESS-SW-01
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 99
 switchport trunk allowed vlan 10,20
 switchport nonegotiate
 spanning-tree guard root
```

### Switch Access (Trunking, Hardening, Port Protection, Port-Channel)
```text
hostname ACCESS-SW-01
spanning-tree mode rapid-pvst
spanning-tree vlan 10,20,99 priority 32768

! Global STP Toolkit Hardening
spanning-tree portfast edge default
spanning-tree portfast edge bpduguard default

vlan 10
 name APPLICATION_SERVERS
vlan 20
 name DATABASE_SERVERS
vlan 99
 name NATIVE_TRANSIT_ISOLATED

! Uplink LACP ke Distribution Switch
interface Range GigabitEthernet1/0/47 - 48
 description DUAL_UPLINK_TO_DIST-SW-01
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 99
 switchport trunk allowed vlan 10,20
 switchport nonegotiate
 channel-group 1 mode active
 no shutdown

interface Port-channel 1
 description LOGICAL_TRUNK_DIST-SW-01
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 99
 switchport trunk allowed vlan 10,20
 switchport nonegotiate

! Port Akses Menuju Server Kubernetes Worker Nodes
interface Range GigabitEthernet1/0/1 - 24
 description K8S_NODE_INTERFACES
 switchport mode access
 switchport access vlan 10
 spanning-tree portfast edge
 spanning-tree bpduguard enable
 load-interval 30
 storm-control broadcast level 1.00 0.50
 storm-control action shutdown
 no shutdown
```

---

## 11. Real World Example
Pada sebuah FinTech payment gateway di Singapura, terjadi insiden *Major P1 Outage*. Seluruh transaksi kliring gagal akibat latensi internal melonjak dari 2ms ke 4.500ms, diiringi 80% packet loss. 

**Investigasi Post-Mortem SRE**:
1. Teknisi onsite memasang switch test unmanaged di rack server development untuk pengetesan firmware. Switch test tersebut memiliki kabel loopback (kedua ujung kabel tercolok pada port switch test yang sama).
2. Port switch enterprise tempat perangkat tersebut tercolok dikonfigurasi sebagai port access biasa tanpa fitur `spanning-tree bpduguard enable`. Switch test unmanaged tersebut memantulkan frame broadcast kembali ke fabric data center.
3. Karena switch unmanaged tidak memproses BPDU standar secara benar atau menjatuhkannya, STP di core switch tidak memblokir port tersebut, memicu **Broadcast Storm** tak terkendali.
4. Utilisasi CPU control plane pada seluruh switch aggregation melonjak ke 100% untuk memproses Jutaan ARP Broadcast per detik. CAM table mengalami *MAC address flapping* ekstrem ribuan kali per detik antara interface rack dev dan link inter-switch.

**Resolusi & Mitigasi Pasca-Insiden**:
1. Implementasi **BPDU Guard** secara global pada semua edge port; jika switch asing mendistribusikan frame berbahaya atau paket BPDU, port mati seketika (`err-disable`).
2. Menerapkan **Storm Control** hardware rate-limiting pada level ASIC: broadcast dibatasi maksimum 1% dari kapasitas link; jika dilanggar, port otomatis melakukan self-shutdown.
3. Otomatisasi audit konfigurasi Layer 2 harian melalui pipeline CI/CD untuk memastikan tidak ada port edge yang tertinggal dalam status unprotected.

---

## 12. Trade-offs

| Parameter | Pendekatan A | Pendekatan B | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **STP Flavor** | **PVST+ / Rapid-PVST+** | **MSTP (802.1s)** | Rapid-PVST+ sangat mudah dioperasikan dan optimal untuk VLAN isolation per-VLAN, tetapi menghabiskan CPU & memory switch secara linear seiring bertambahnya jumlah VLAN (1 instance STP per VLAN). MSTP sangat hemat resource karena memetakan ratusan VLAN ke 2-4 MSTI, namun kompleksitas konfigurasi MST Region, revision number, dan instance digest harus sinkron 100% di semua switch. |
| **Link Aggregation** | **Static LAG (Mode ON)** | **Dynamic LACP (802.3ad)** | Mode Static (ON) tidak memiliki overhead protokol dan langsung aktif, namun rentan black-holing jika terjadi kesalahan pasang kabel fisik atau silent failure. Dynamic LACP melakukan negosiasi dua arah (handshake); jika konfigurasi port mismatch atau kabel putus satu arah (unidirectional), port otomatis dicabut dari bundle secara aman. |
| **Port Protection** | **BPDU Guard** | **BPDU Filter** | BPDU Guard aman dan deterministik (mematikan port berbahaya untuk mencegah loop). BPDU Filter mematikan transmisi BPDU; jika salah terpasang pada link yang tidak sengaja terhubung ke switch lain, STP tidak akan berjalan di segmen tersebut dan broadcast storm dijamin akan meledak. |

---

## 13. When To Use
- Gunakan **VLAN Trunking (802.1Q)** saat mendistribusikan lalu lintas berbagai domain keamanan atau multi-tenant melintasi uplink fisik switch yang terbatas.
- Gunakan **RSTP / MSTP** di seluruh topologi switching yang memiliki redundansi jalur fisik (kabel ganda antar switch).
- Gunakan **LACP** ketika server fisik berkepadatan tinggi (VMware ESXi, OpenStack Compute, Kubernetes Bare-metal) membutuhkan link bonding aktif untuk kapasitas agregat >10Gbps dan proteksi failover link fisik tanpa downtime.
- Gunakan **BPDU Guard & PortFast** secara non-negotiable di seluruh port edge yang berhadapan langsung dengan workstation, server, printer, atau perangkat non-switch.

---

## 14. When NOT To Use
- **Jangan gunakan STP** sebagai mekanisme failover utama di arsitektur Data Center modern berskala besar (*Hyperscale Spine-Leaf*). Standar modern menggunakan **Layer 3 Routed Fabric (BGP-to-the-Host/EVPN-VXLAN)**, di mana loop dieliminasi oleh protokol routing Layer 3 (TTL decrementing dan ECMP), bukan dengan memblokir jalur secara boros melalui STP.
- **Jangan gunakan dynamic trunking (DTP)** di lingkungan enterprise karena memperkenalkan celah keamanan VLAN hopping.
- **Jangan gunakan Default VLAN (VLAN 1)** sebagai native VLAN atau data VLAN untuk mengalirkan traffic produksi sensitif.

---

## 15. Common Mistakes
1. **Native VLAN Mismatch**: Mengonfigurasi Native VLAN berbeda di kedua ujung trunk link (misal Switch A native VLAN 10, Switch B native VLAN 20). Hal ini menyebabkan paket dari VLAN 10 bocor secara langsung ke VLAN 20 tanpa melewati router/firewall (security leak & bridging antar VLAN tak sengaja).
2. **Lupa Menentukan Root Bridge Eksplisit**: Mengabaikan STP priority switch. Akibatnya, switch paling lambat atau switch usang yang baru disambungkan dapat menjadi Root Bridge hanya karena memiliki MAC address pabrikan bernilai terkecil.
3. **Mengaktifkan BPDU Filter alih-alih BPDU Guard**: Berpikir bahwa BPDU filter "membersihkan" log error, padahal BPDU filter membuat switch abai terhadap BPDU yang masuk, membuka celah terjadinya loop Layer 2 yang melumpuhkan jaringan.
4. **Asimetri Trunk Allowed List**: Menambahkan VLAN 50 di Switch A, tetapi lupa memasukkannya ke `switchport trunk allowed vlan` di Switch B, menyebabkan packet drop sepihak yang sulit dilacak.
5. **Kesalahan Hash Algorithm pada Port-Channel**: Menggunakan default load-balancing `src-mac` pada Port-Channel yang menghubungkan switch ke router/firewall gateway. Akibatnya, seluruh trafik internet hanya memiliki 1 Destination MAC (MAC firewall), sehingga 100% trafik hanya melewati satu kabel fisik sementara kabel fisik lainnya menganggur (link underutilization).

---

## 16. Best Practices
1. **Explicit Root & Secondary**: Tetapkan `priority 4096` pada Core Switch utama dan `priority 8192` pada Core Switch cadangan. Jangan biarkan priority default 32768.
2. **Pruning Ketat**: Jangan gunakan `switchport trunk allowed vlan all`. Batasi trunk hanya untuk VLAN yang memang dibutuhkan pada switch tujuan.
3. **Terapkan Root Guard**: Pasang Root Guard di semua port Distribution switch yang mengarah ke Access switch untuk memastikan access switch tidak pernah bisa merebut kendali Root.
4. **Aktifkan Storm Control**: Batasi broadcast dan unknown-unicast traffic pada level hardware (misal max 1% atau 500 pps) pada seluruh port access host.
5. **Konfigurasi LACP Load Balancing L4**: Gunakan hashing berbasis layer 4 IP dan port (`port-channel load-balance src-dst-mixed-ip-port` atau `src-dst-ip`) agar distribusi traffic merata.
6. **Dedicated Native VLAN**: Alokasikan VLAN dummy khusus yang tidak membawa traffic host dan tidak dirouting (misal VLAN 999) sebagai Native VLAN pada semua trunk port.

---

## 17. Troubleshooting

### Playbook Ringkas Diagnostik Layer 2

| Gejala Masalah | Kemungkinan Akar Masalah | Perintah Verifikasi / Investigasi | Langkah Resolusi |
| :--- | :--- | :--- | :--- |
| Port mendadak mati, status `err-disabled` | BPDU Guard mendeteksi paket BPDU pada port PortFast/Edge | `show interface status err-disabled`<br>`show log \| include BPDU` | Cabut switch/AP tidak resmi dari port edge, lalu lakukan `shutdown` dilanjutkan `no shutdown` pada interface. |
| MAC Address Flapping di Syslog (`%SW_MATM-4-MACFLAP_ADDR`) | Terjadi Physical Loop Layer 2 atau duplikasi IP/MAC | `show mac address-table notification mac-move`<br>`show spanning-tree detail` | Identifikasi dua port tempat MAC address meloncat; telusuri kabel fisik dan periksa STP blocking state pada port tersebut. |
| Port-Channel tidak aktif / status `suspended` atau `I` (Individual) | Konfigurasi LACP mismatch (misal passive-passive, dupleks/kecepatan beda, allowed vlan beda) | `show etherchannel summary`<br>`show etherchannel port-channel` | Samakan konfigurasi speed, duplex, trunk mode, dan native vlan di seluruh member interface fisik. |
| Host tidak menerima IP DHCP di VLAN tertentu | VLAN belum dibuat di local database switch, atau VLAN di-prune pada trunk uplink | `show vlan brief`<br>`show interfaces trunk` | Buat VLAN pada switch lokal (`vlan X`) dan tambahkan VLAN pada trunk uplink (`switchport trunk allowed vlan add X`). |

---

## 18. Exercise
Skenario: Anda sedang membangun access layer pada data center.
1. Tuliskan urutan CLI commands pada interface range `GigabitEthernet 1/0/1 - 4` untuk menggabungkannya ke dalam LACP bundle Port-Channel 10 dengan mode aktif.
2. Konfigurasikan Port-Channel 10 tersebut sebagai Trunk yang hanya mengizinkan VLAN 100, 200, dan 300, serta menggunakan Native VLAN 888.
3. Pastikan port-channel tersebut tidak akan pernah menerima BPDU superior yang mencoba mengubah root bridge (Terapkan Root Guard).

---

## 19. Challenge
Analisis skenario berikut:
Sebuah perusahaan memiliki 3 switch (SW1, SW2, SW3) yang saling terhubung membentuk topologi segitiga tertutup (*triangle mesh*).
- SW1 Bridge Priority: 4096, Base MAC: `00:11:22:33:44:01`
- SW2 Bridge Priority: 8192, Base MAC: `00:11:22:33:44:02`
- SW3 Bridge Priority: 32768, Base MAC: `00:11:22:33:44:03`
- Semua interface memiliki link speed GigabitEthernet (Cost STP default IEEE 802.1D = 4, IEEE 802.1w = 20.000).

**Tugas Anda:**
1. Tentukan switch mana yang terpilih sebagai Root Bridge.
2. Tentukan Role (Root Port, Designated Port, Alternate Port) pada setiap interface di SW1, SW2, dan SW3.
3. Jika kabel fisik antara SW1 dan SW2 putus total:
   - Jelaskan transisi state port pada SW3 secara step-by-step berdasarkan RSTP Proposal-Agreement handshake.
   - Hitung estimasi waktu pemulihan koneksi dari workstation di SW2 menuju server di SW1.

---

## 20. Summary
- **Layer 2 Data Link Switching** mengandalkan pembelajaran dinamis CAM Table untuk memetakan hardware address ke port fisik, mengisolasi collision domain secara deterministik.
- **IEEE 802.1Q** menyisipkan tag 4-byte yang berisi VID (12-bit) untuk memfasilitasi logis segmentasi broadcast domain pada trunk link.
- **Spanning Tree Protocol (STP)** adalah mekanisme pertahanan esensial melawan loop Layer 2 yang dapat memicu broadcast storm fatal. Evolusinya dari 802.1D ke 802.1w (RSTP) memangkas konvergensi dari 50 detik ke sub-detik melalui sinkronisasi terdistribusi.
- **STP Security Toolkit** (BPDU Guard, Root Guard, Loop Guard) adalah fondasi wajib pada desain jaringan enterprise modern guna memproteksi determinisme topologi dari anomali kabel atau serangan internal.
- **LACP (802.3ad)** menyediakan throughput paralel dan ketersediaan tinggi tanpa memicu pemblokiran STP, dengan catatan algoritma hash didistribusikan secara proporsional.