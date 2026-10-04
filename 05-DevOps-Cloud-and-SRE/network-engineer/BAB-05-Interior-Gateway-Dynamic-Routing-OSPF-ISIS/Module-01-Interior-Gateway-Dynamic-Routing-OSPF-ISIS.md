# Modul 01: Interior Gateway Dynamic Routing: OSPFv2/v3 & IS-IS

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis cara kerja algoritma Link-State Shortest Path First (Dijkstra SPF) dalam membentuk Link-State Database (LSDB) dan menghitung routing table.
- Mengonfigurasi arsitektur multi-area OSPFv2 (IPv4) dan OSPFv3 (IPv6/Address-Families) secara deterministik pada platform Cisco IOS/Arista EOS/FRRouting.
- Menguasai Finite State Machine (FSM) pembentukan OSPF adjacency (Down hingga Full) dan proses pemilihan Designated Router (DR) / Backup Designated Router (BDR).
- Mengimplementasikan varian OSPF Special Area (Stub, Totally Stubby, NSSA, Totally NSSA) untuk mereduksi footprint memory dan CPU pada router resource-constrained.
- Mengeksekusi teknik Route Summarization pada Area Border Router (ABR) dan Autonomous System Boundary Router (ASBR) untuk memitigasi fluktuasi rute (LSA flooding scope control).
- Membandingkan arsitektur operasional, enkapsulasi, skalabilitas, dan extensibility TLV antara OSPF dan IS-IS (Intermediate System to Intermediate System) dalam konteks jaringan Service Provider dan Hyperscale Data Center.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Model Referensi OSI Layer 2 (Data Link - Ethernet, MAC, MTU) dan Layer 3 (IPv4/IPv6 Addressing, Subnetting, VLSM).
- Konsep dasar Static Routing, Administrative Distance (AD), Routing Metric, dan Longest Prefix Match (LPM).
- Mekanisme ICMP dan pengalamatan IP Multicast (khususnya 224.0.0.5, 224.0.0.6, FF02::5, FF02::6).
- Pengalaman dasar navigasi CLI sistem operasi jaringan berbasis Linux (FRR), Cisco IOS/IOS-XE, atau Arista EOS.

---

## 3. Concept
Routing dinamis Interior Gateway Protocol (IGP) terbagi dalam dua filosofi utama: **Distance-Vector** (routing by rumor, e.g., RIP) dan **Link-State** (topologi global berbasis peta komprehensif, e.g., OSPF dan IS-IS).

Dalam routing Link-State:
- Setiap router tidak sekadar mengirimkan daftar tabel routing miliknya kepada tetangga, melainkan mengiklankan status fisik dan logis dari interface lokalnya (link state, metric/cost, connected prefix, status operasional neighbor) ke seluruh router dalam satu area operasional.
- Paket iklan ini disebut **LSA (Link-State Advertisement)** pada OSPF atau **LSP (Link State PDU)** pada IS-IS.
- Seluruh LSA/LSP dikumpulkan dalam sebuah basis data sinkron yang disebut **LSDB (Link-State Database)**. Seluruh router dalam satu area wajib memiliki LSDB yang 100% identik.
- Menggunakan LSDB sebagai representasi graf berbobot (weighted directed graph), setiap router menjalankan algoritma matematika **Dijkstra’s Shortest Path First (SPF)** secara independen dengan dirinya sendiri sebagai *root* dari *Shortest Path Tree (SPT)* untuk menghasilkan jalur bebas loop (*loop-free shortest paths*) menuju setiap network prefix yang diketahui.

---

## 4. Why
Mengapa jaringan skala menengah hingga hyperscale enterprise/telco mengandalkan OSPF dan IS-IS dibanding Distance-Vector atau Static Routing?

1. **Deterministic Fast Convergence**: Begitu terjadi perubahan topologi (misal, link putus), LSA/LSP dikirimkan secara instan (*flooding*) tanpa penundaan kalkulasi hop-by-hop. Router mendeteksi perubahan dalam skala sub-detik (menggunakan Bidirectional Forwarding Detection / BFD) dan menghitung ulang rute melalui SPF.
2. **Loop-Free Guarantee**: Karena setiap router memiliki pemahaman grafis menyeluruh atas topologi jaringan melalui LSDB, pembentukan *routing loops* (seperti count-to-infinity problem pada RIP) secara matematis mustahil terjadi di dalam area link-state.
3. **Hierarchical Scalability**: Penggunaan arsitektur *hierarchical areas* (OSPF Area 0/Backbone dan non-backbone areas; IS-IS Level-1 dan Level-2) membatasi domain propagasi SPF. Fluktuasi link pada satu area tidak memicu eksekusi ulang algoritma Dijkstra pada area lain.
4. **Traffic Engineering & Granular Metrics**: OSPF dan IS-IS mendukung kalkulasi *cost* berbasis bandwidth antarmuka (bukan sekadar jumlah *hop*), mendukung ECMP (*Equal-Cost Multi-Path*), serta dapat diperluas (*extensible*) untuk mendistribusikan parameter MPLS/Segment Routing Traffic Engineering (SR-TE).

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Algoritma Dijkstra SPF (Shortest Path First)
Algoritma Dijkstra beroperasi pada representasi graf:
- $G = (V, E)$ di mana $V$ adalah himpunan router (*nodes*), dan $E$ adalah himpunan link (*edges*) dengan bobot (*cost*).
- Setiap router menghitung biaya kumulatif: 
$$\text{Cost} = \sum \frac{\text{Reference Bandwidth}}{\text{Interface Bandwidth}}$$
- Tiga himpunan data dipelihara selama kalkulasi:
  1. **Candidate List / Tentative (T)**: Rute/node yang terdeteksi beserta cost akumulatifnya tetapi belum diverifikasi sebagai jalur terpendek absolut.
  2. **Shortest Path Tree / Paths (P)**: Node yang telah diverifikasi memiliki cost terendah absolut dari *root*. Begitu node masuk ke $P$, ia tidak akan pernah dievaluasi ulang.
  3. **LSDB**: Basis data graf sumber kalkulasi.

### 5.2 OSPF Packet Types & Finite State Machine (FSM)
OSPF beroperasi langsung di atas protokol IP (IP Protocol number **89**), tanpa menggunakan transport layer TCP atau UDP.

#### Lima Tipe Paket OSPF:
1. **Type 1: Hello** — Digunakan untuk discovery tetangga, negosiasi parameter (timers, area ID, authentication, stub flags), dan keepalive.
2. **Type 2: Database Description (DBD)** — Ringkasan LSA header dalam LSDB router untuk proses sinkronisasi awal.
3. **Type 3: Link-State Request (LSR)** — Meminta salinan LSA lengkap jika terdapat LSA dalam DBD neighbor yang lebih baru atau belum dimiliki.
4. **Type 4: Link-State Update (LSU)** — Mengangkut satu atau lebih LSA payload eksplisit (respons terhadap LSR atau saat ada perubahan topologi/event-triggered).
5. **Type 5: Link-State Acknowledgment (LSAck)** — Konfirmasi penerimaan LSU demi keandalan transfer (reliable transport).

#### 8 Adjacency States (Finite State Machine):
1. **Down**: Tidak ada informasi OSPF yang diterima dari interface.
2. **Attempt**: Khusus jaringan Non-Broadcast Multi-Access (NBMA), router mengirim Hello unicast ke neighbor yang dikonfigurasi statis.
3. **Init**: Router menerima Hello dari neighbor, tetapi Router ID lokal belum tercantum dalam *Active Neighbor List* di dalam paket Hello tersebut (komunikasi satu arah / unidirectional).
4. **2-Way**: Komunikasi bidirectional terjalin (Router ID lokal terlihat di Hello neighbor). Pada tipe jaringan multi-access (broadcast), proses pemilihan **DR/BDR** dieksekusi pada fase ini. Komunikasi antar router DROther berhenti pada state ini.
5. **ExStart**: Memulai proses sinkronisasi LSDB. Penentuan relasi **Master/Slave** dan negosiasi **Initial Database Sequence Number (DD Sequence)** menggunakan paket DBD kosong. Router dengan Router ID tertinggi menjadi Master.
6. **Exchange**: Router saling mengirim paket DBD berisi daftar LSA header dari LSDB masing-masing. Router membandingkan LSA header yang diterima dengan LSDB lokal.
7. **Loading**: Jika ditemukan LSA tetangga yang lebih baru (berdasarkan *Sequence Number*, *Checksum*, dan *Age*), router mengirimkan **LSR**, dan neighbor merespons dengan **LSU**. Penerimaan LSU dikonfirmasi via **LSAck**.
8. **Full**: LSDB antara kedua router telah 100% tersinkronisasi. Router siap memasukkan rute ke routing table via SPF.

```
+------+     Hello Recv      +------+     2-Way Recv     +-------+
| Down | ------------------> | Init | -----------------> | 2-Way |
+------+                     +------+                    +-------+
                                                             |
                                            (DR/BDR or P2P)  |
                                                             v
+------+     DBD Exch. Done  +----------+   Master/Slave +---------+
| Full | <------------------ | Exchange | <------------- | ExStart |
+------+                     +----------+   Negotiated   +---------+
   ^                              |
   | (Loading Done)               | (Needs LSAs)
   |                              v
   +----------------------- +---------+
                            | Loading |
                            +---------+
```

### 5.3 DR dan BDR Election
Pada network tipe **Broadcast Multi-Access** (seperti Ethernet switch di mana $N$ router saling terhubung), hubungan adjacency penuh antar seluruh router akan menciptakan $N(N-1)/2$ sesi adjacency dan badai flooding LSA ($O(N^2)$).
- **Solusi**: OSPF memilih **Designated Router (DR)** dan **Backup Designated Router (BDR)**.
- Seluruh router lain menjadi **DROther**.
- DROther hanya membentuk relasi **FULL** ke DR dan BDR. Antar sesama DROther tetap berada pada state **2-Way**.
- Flooding LSA dari DROther dikirim ke alamat IP multicast **224.0.0.6** (AllDRouters).
- DR mendistribusikan ulang LSA ke seluruh DROther menggunakan alamat IP multicast **224.0.0.5** (AllSPFRouters).
- **Kriteria Pemilihan**:
  1. **OSPF Interface Priority** tertinggi (nilai `0` - `255`). Prioritas `0` mendiskualifikasi router dari pemilihan (tidak akan pernah menjadi DR/BDR). Default priority adalah `1`.
  2. Jika priority sama: **Router ID (RID)** numerik tertinggi.
  3. Proses non-preemptive: Jika DR aktif tidak mati, router baru dengan prioritas lebih tinggi *tidak akan* menggulingkan DR yang sedang berjalan demi stabilitas sistem.

### 5.4 Anatomi LSA (Link-State Advertisements) OSPFv2 & OSPFv3
| Tipe LSA OSPFv2 | Nama LSA OSPFv2 | Pengirim / Generator | Flooding Scope | Deskripsi Isi |
|---|---|---|---|---|
| **Type 1** | Router LSA | Setiap router | Intra-area saja | Daftar interface, IP, cost, dan neighbor adjacency lokal. |
| **Type 2** | Network LSA | DR (Designated Router) | Intra-area saja | Merepresentasikan segment multi-access dan daftar RID router yang terkoneksi ke segmen tersebut. |
| **Type 3** | Summary LSA (Network) | ABR (Area Border Router) | Inter-area (lintas area) | Mengumumkan prefix dari satu area ke area lain tanpa detail topologi internal. |
| **Type 4** | ASBR Summary LSA | ABR | Inter-area | Mengumumkan rute host (/32) menuju router ASBR ke area lain. |
| **Type 5** | AS External LSA | ASBR | Seluruh OSPF AS (kecuali Stub/NSSA) | Berisi rute yang diredistribusikan dari luar domain OSPF (BGP, Static, Direct). |
| **Type 7** | NSSA External LSA | ASBR di dalam NSSA | NSSA area saja | External route di dalam NSSA. Dikonversi menjadi LSA Type 5 oleh ABR sebelum diteruskan ke Area 0. |

*Catatan OSPFv3 (IPv6)*:
Pada OSPFv3, arsitektur LSA dipisahkan dari dependensi IP addressing:
- LSA Type 1 & 2 membawa murni informasi topologi (Node ID, Link ID) tanpa prefiks IPv6.
- **LSA Type 8 (Link LSA)**: Membawa IPv6 Link-Local address dan list IPv6 prefix untuk link lokal.
- **LSA Type 9 (Intra-Area-Prefix LSA)**: Mengasosiasikan IPv6 prefix ke Router atau Network LSA.

### 5.5 Klasifikasi Area OSPF
Arsitektur OSPF bersifat hirarkis dengan **Backbone Area (Area 0 / 0.0.0.0)** sebagai pusat distribusi antar seluruh non-backbone area.

1. **Standard Area**: Menerima seluruh jenis LSA (Type 1, 2, 3, 4, 5).
2. **Stub Area**: Memblokir LSA Type 4 dan 5 (rute eksternal dilarang masuk). ABR secara otomatis menginjeksikan LSA Type 3 default route (`0.0.0.0/0`).
3. **Totally Stubby Area (Cisco Proprietary Extension)**: Memblokir LSA Type 3, 4, dan 5. Router di area ini hanya memiliki LSA Type 1 & 2 lokal, ditambah satu buah LSA Type 3 default route dari ABR.
4. **Not-So-Stubby Area (NSSA - RFC 3101)**: Karakteristik mirip Stub (tidak menerima Type 4 & 5 dari Area 0), namun memperbolehkan router internal bertindak sebagai ASBR. External prefix diinjeksikan sebagai **LSA Type 7**. ABR NSSA menerjemahkan Type 7 menjadi Type 5 (*Type-7-to-5 translation*) saat membanjirkannya ke Area 0.
5. **Totally NSSA**: Karakteristik mirip NSSA, namun memblokir LSA Type 3 summary dari Area 0, hanya mengandalkan default route yang digenerate oleh ABR.

```
+-------------------------------------------------------------------+
|                        OSPF AS DOMAIN                             |
|                                                                   |
|  +-------------------+               +-------------------------+  |
|  |     STUB AREA     |               |        NSSA AREA        |  |
|  | (No Type 4/5 LSA) |               |  (Allows External via   |  |
|  | Default Route LSA3|               |   LSA Type 7 -> 5 Trans)|  |
|  +---------+---------+               +------------+------------+  |
|            |                                      |               |
|         [ ABR 1 ]                              [ ABR 2 ]          |
|            |                                      |               |
|  +---------+--------------------------------------+------------+  |
|  |                     BACKBONE AREA 0                         |  |
|  |               (Transit Core / Full LSDB)                    |  |
|  +-----------------------------+-------------------------------+  |
|                                |                                  |
|                            [ ASBR 1 ]                             |
|                                |                                  |
|                       External Domain                             |
|                     (BGP / Static / DC)                           |
+-------------------------------------------------------------------+
```

### 5.6 Route Summarization
Summarization memadatkan sekumpulan network prefix menjadi satu blok supernet untuk mengecilkan ukuran routing table global dan mengisolasi kegagalan link (*fault isolation*):
1. **ABR Summarization (`area <area-id> range <prefix> <mask>`)**: Meringkas LSA Type 1 & 2 dari area lokal menjadi satu LSA Type 3 sebelum diiklankan ke area lain. Jika salah satu subnet di area lokal flapping, LSA Type 3 summary tidak akan berfluktuasi, menghemat CPU SPF seluruh router di area lain.
2. **ASBR Summarization (`summary-address <prefix> <mask>`)**: Meringkas rute eksternal sebelum diinjeksikan sebagai LSA Type 5 (atau Type 7) ke dalam domain OSPF.
3. **Discard Route / Blackhole Prevention**: Saat summarization dikonfigurasi, router otomatis membuat rute statis lokal ke interface `Null0` untuk prefix summary tersebut guna mencegah packet bouncing (*micro-routing loops*).

### 5.7 Komparasi Mendalam: OSPF vs IS-IS
| Parameter Evaluasi | OSPF (OSPFv2 / OSPFv3) | IS-IS (Intermediate System to Intermediate System) |
|---|---|---|
| **Standar Organisasi** | IETF (RFC 2328 / RFC 5340) | ISO / IEC 10589, IETF (RFC 1195) |
| **Layer Operasional Enkapsulasi** | Layer 3 (IP Protocol 89) | Layer 2 langsung (Data Link - OSI CLNP / LLC Encapsulation) |
| **Konsep Hierarki Batas Wilayah** | **Router Border**: Router (ABR) berada di perbatasan, interfaces bisa berada di area berbeda-beda. | **Link Border**: Seluruh router berada di dalam satu Level. Batas area berada di kabel/link antar router. |
| **Tingkatan Level Hierarki** | Backbone (Area 0) dan Non-Backbone Areas. | **Level 1** (Intra-area), **Level 2** (Inter-area / Backbone Core), **L1/L2** (Transit Routers). |
| **Format Unit Data Pertukaran** | LSA (Link-State Advertisement) kaku dengan tipe fixed. | **TLV (Type-Length-Value)** triplets dalam LSP; arsitektur sangat fleksibel dan modular. |
| **Dukungan Multi-Protocol** | OSPFv2 (hanya IPv4), OSPFv3 (perlu instance terpisah atau Address-Family extension). | Multi-Topology IS-IS natively mendukung IPv4, IPv6, Segment Routing (SRv6, SR-MPLS) via TLVs baru. |
| **Ketahanan Keamanan L2/L3** | Rentan terhadap serangan berbasis IP spoofing jika security ACL miskonfigurasi. | Imun terhadap serangan IP layer 3 murni karena tidak menggunakan IP header untuk transport. |
| **Adopsi Arsitektur Industri** | Sangat dominan di Enterprise Campus, WAN, dan Small-to-Mid Data Center. | Standar de-facto di Tier-1 Telco/ISP Core, Underlay 5G Mobile Backhaul, dan Hyperscale Cloud Fabric. |

---

## 6. How
Prosedur rekayasa konfigurasi dan verifikasi interior gateway dynamic routing:
1. **Perencanaan Router ID & Addressing**: Tetapkan Router ID statis (biasanya menggunakan loopback IP tertinggi, e.g., `10.255.0.x/32`). Jangan pernah membiarkan Router ID dipilih secara otomatis oleh sistem.
2. **Standardisasi Reference Bandwidth**: OSPF default reference bandwidth adalah 100 Mbps (cost GigabitEthernet = 1, cost 100G = 1). Ubah segera ke standar datacenter: `auto-cost reference-bandwidth 1000000` (1 Tbps).
3. **Konfigurasi Interface Level**:
   - Tentukan jenis link secara eksplisit: `ip ospf network point-to-point` pada link inter-router guna mengeliminasi overhead pemilihan DR/BDR dan paket LSA Type 2.
   - Atur `passive-interface default` untuk mengamankan link edge yang mengarah ke end-hosts/server, lalu buka hanya interface inter-router dengan `no passive-interface <interface>`.
4. **Implementasi Special Areas**:
   - Jika router remote/branch memiliki RAM/CPU terbatas, konfigurasikan area tersebut sebagai Stub atau Totally Stubby via perintah `area <id> stub [no-summary]`.
5. **Route Aggregation / Summarization**:
   - Terapkan `area <id> range <summary-prefix> <netmask>` di ABR untuk memangkas LSA Type 3.
6. **Verifikasi Operasional**:
   - Validasi adjacency FSM via `show ip ospf neighbor`.
   - Analisis LSDB via `show ip ospf database`.
   - Periksa SPT cost dan forwarding table via `show ip route ospf`.

---

## 7. Analogy
Bayangkan sistem navigasi GPS kota metropolitan:
- **Distance-Vector (RIP)**: Seperti sopir taksi tua yang hanya bertanya ke sopir taksi di sebelahnya di lampu merah: *"Ke arah bandara belok mana? Berapa persimpangan lagi?"*. Sopir tidak tahu peta kota secara utuh, hanya tahu arah umum dari rumor tetangga.
- **Link-State (OSPF/IS-IS)**: Setiap persimpangan (router) memiliki kamera pengawas yang memantau kondisi jalan lokal (status link & kecepatan jalan). Setiap persimpangan menyiarkan laporan kondisi jalanan tersebut ke seluruh pusat kendali kota. Laporan ini dikompilasi menjadi **Peta Kota Utuh (LSDB)** di dalam unit GPS setiap mobil. Menggunakan peta lengkap tersebut, GPS setiap mobil mengeksekusi algoritma pencari rute terpendek (**Dijkstra**) untuk menentukan jalur paling cepat ke tujuan.
- **Area 0 (Backbone)**: Sistem jalan tol lingkar utama kota. Seluruh jalan distrik lokal (Area 1, Area 2) wajib memiliki pintu gerbang (ABR) yang terhubung langsung ke jalan tol lingkar ini agar lalu lintas antar distrik tidak memotong jalan perumahan sembarangan.

---

## 8. Diagram (ASCII)

### 8.1 Topologi Multi-Area OSPF Enterprise
```
+-----------------------------------------------------------------------------------+
|                               AREA 1 (Campuses)                                   |
|                                                                                   |
|  [ Branch-R1 ] (ID: 10.255.0.11)                                                  |
|        |                                                                          |
|     (p2p link: 10.0.11.0/30, Cost: 10)                                            |
|        |                                                                          |
|  [ Branch-R2 ] (ID: 10.255.0.12)                                                  |
|        |                                                                          |
|     (p2p link: 10.0.12.0/30, Cost: 10)                                            |
|        v                                                                          |
+--------+--------------------------------------------------------------------------+
         |
    +----+----+ [ ABR-01 ] (ID: 10.255.0.1)
    |         | (Interfaces: Area 1 & Area 0)
    |         | Summarizes: 10.1.0.0/16 -> Area 0
    +----+----+
         |
+--------v--------------------------------------------------------------------------+
|        |                  AREA 0 (Backbone Core Transit)                          |
|        +==============+ (100G Backbone Trunk: 10.0.0.0/30, Cost: 1)              |
|                       |                                                           |
|                 +-----+---+ [ ABR-02 / ASBR ] (ID: 10.255.0.2)                    |
+-----------------+---------+-------------------------------------------------------+
                            |
                   (Point-to-Point Transit)
                            |
+---------------------------v-------------------------------------------------------+
|                               AREA 20 (NSSA - Datacenter Edge)                   |
|                                                                                   |
|                 +---------+ [ DC-Border-01 ] (ID: 10.255.20.1)                    |
|                 |                                                                 |
|                 | Injects: 172.16.0.0/12 via Type 7 LSA                           |
|                 | (ABR-02 converts Type 7 -> Type 5 to Area 0)                    |
|                 +-----------------------------------------------------------------+
```

### 8.2 Perbandingan Batas Area: OSPF vs IS-IS
```
         OSPF (Area Border on ROUTER)             IS-IS (Area Border on LINK)
         
          Area 1          Area 0                    Level 1           Level 2
      +------------+  +------------+            +------------+     +------------+
      |            |  |            |            |  [ R1-L1 ] |     |  [ R3-L2 ] |
      |   [ R1 ]   |  |   [ R2 ]   |            |  (Area 49) |     |  (Area 50) |
      |   Area 1   |  |   Area 0   |            +------+-----+     +-----+------+
      |            |  |            |                   |                 |
      +------+-----+  +-----+------+                   |  (L1 adj)       | (L2 adj)
             |              |                          v                 v
             +-------+------+                   +-------------------------------+
                     |                          |       [ R2 - L1/L2 Router ]   |
                 [ ABR ]                        |   (Belongs wholly to Area 49) |
          (Router in BOTH Areas)                +-------------------------------+
```

---

## 9. Simple Example
Skenario minimal konfigurasi OSPFv2 point-to-point antara dua router menggunakan interface modern format (Cisco IOS-XE / Arista EOS syntax style):

**Router-A (ID: 1.1.1.1):**
```text
router ospf 1
 router-id 1.1.1.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/0/0
!
interface GigabitEthernet0/0/0
 description Link to Router-B
 ip address 10.0.0.1 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 no shutdown
!
interface Loopback0
 ip address 10.255.0.1 255.255.255.255
 ip ospf 1 area 0
```

**Router-B (ID: 2.2.2.2):**
```text
router ospf 1
 router-id 2.2.2.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/0/0
!
interface GigabitEthernet0/0/0
 description Link to Router-A
 ip address 10.0.0.2 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 no shutdown
!
interface Loopback0
 ip address 10.255.0.2 255.255.255.255
 ip ospf 1 area 0
```

Hasil verifikasi:
```text
Router-A# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2           0   FULL/  -        00:00:34    10.0.0.2        GigabitEthernet0/0/0
```
*Catatan: Pada status tertulis `FULL/ -`, tanda dash `-` menandakan tidak ada DR/BDR election karena network dikonfigurasi sebagai `point-to-point`.*

---

## 10. Practical Example (Konfigurasi Produksi Multi-Area & Dual-Stack)

Skenario Enterprise Backbone & Branch dengan NSSA dan Route Summarization pada FRRouting (FRR) / Cisco IOS-XE.

### File Konfigurasi ABR-01 (Cisco IOS-XE / Cisco Enterprise Core)
```text
! Definisi Global OSPFv2 (IPv4) dan OSPFv3 (IPv6)
router ospfv3 100
 router-id 10.255.0.1
 !
 address-family ipv4 unicast
  auto-cost reference-bandwidth 1000000
  ! Summarize Branch Area 1 Prefixes ke Area 0
  area 1 range 10.1.0.0 255.255.0.0
  ! Jadikan Area 10 sebagai NSSA Totally Stubby
  area 10 nssa no-summary
 exit-address-family
 !
 address-family ipv6 unicast
  auto-cost reference-bandwidth 1000000
  area 1 range 2001:db8:1::/48
  area 10 nssa no-summary
 exit-address-family
!
interface GigabitEthernet1
 description Core-Backbone-Trunk to Core-R2 (Area 0)
 ip address 10.0.0.1 255.255.255.252
 ipv6 address fe80::1:1 link-local
 ipv6 address 2001:db8:0:1::1/64
 ospfv3 100 ipv4 area 0
 ospfv3 100 ipv6 area 0
 ospfv3 network point-to-point
 ospfv3 authentication ipsec spi 500 sha1 0123456789abcdef0123456789abcdef01234567
 no shutdown
!
interface GigabitEthernet2
 description Aggregation-Link to Campus-Branch (Area 1)
 ip address 10.1.254.1 255.255.255.252
 ipv6 address fe80::1:2 link-local
 ipv6 address 2001:db8:1:fe::1/64
 ospfv3 100 ipv4 area 1
 ospfv3 100 ipv6 area 1
 ospfv3 network point-to-point
 no shutdown
!
interface GigabitEthernet3
 description Datacenter-DMZ-Link (Area 10 - NSSA)
 ip address 10.10.254.1 255.255.255.252
 ipv6 address fe80::1:3 link-local
 ipv6 address 2001:db8:10:fe::1/64
 ospfv3 100 ipv4 area 10
 ospfv3 100 ipv6 area 10
 ospfv3 network point-to-point
 no shutdown
!
interface Loopback0
 ip address 10.255.0.1 255.255.255.255
 ipv6 address 2001:db8:ffff::1/128
 ospfv3 100 ipv4 area 0
 ospfv3 100 ipv6 area 0
```

### Konfigurasi IS-IS Provider Edge (Nokia SR OS / Arista EOS CLI Pattern)
```text
! Konfigurasi Arista EOS untuk Backbone IS-IS Level-2 Multi-Topology
router isis CORE-BACKBONE
 net 49.0001.0102.5500.0001.00
 is-type level-2-only
 metric-style wide
 !
 address-family ipv4 unicast
  multi-topology
 !
 address-family ipv6 unicast
  multi-topology
 !
 interface Ethernet1
  description Backbone link to P1
  isis enable CORE-BACKBONE
  isis circuit-type point-to-point
  isis network point-to-point
  isis metric 10 level-2
  isis authentication mode sha256
  isis authentication key 7 9876543210fedcba
  no shutdown
 !
 interface Loopback0
  isis enable CORE-BACKBONE
  isis passive
  ip address 10.255.0.1/32
  ipv6 address 2001:db8:ffff::1/128
```

---

## 11. Real World Example
Sebuah financial tech payment gateway dengan 2 data center regional (Jakarta dan Surabaya) memiliki arsitektur 150+ microservices di Kubernetes.
- **Problem**: Setiap kali node worker Kubernetes reboot atau node auto-scaling bertambah, IP host route (/32) berfluktuasi. Karena saat itu seluruh jaringan digabung dalam satu OSPF Area 0 flat, setiap flapping link pada server layer memicu kalkulasi Full SPF di router core perbankan. Akibatnya, CPU Core Router melonjak hingga 100%, menyebabkan packet drops transaksi finansial (*jitter & latency spike*).
- **Solution Architectural Fix**:
  1. Melakukan segmentasi: Data Center Jakarta dijadikan **OSPF Area 10 (NSSA)** dan Surabaya dijadikan **OSPF Area 20 (NSSA)**. Core network tetap menjadi Area 0.
  2. Mengaktifkan **ABR Summarization** di router perbatasan: Ribuan rute /32 dari worker node diringkas menjadi rute agregat `10.10.0.0/16` (JKT) dan `10.20.0.0/16` (SBY) sebelum masuk ke Area 0.
  3. Mengonfigurasi `area 10 nssa no-summary` (Totally NSSA) sehingga ABR hanya menginjeksikan 1 buah default route ke arah node distribution.
- **Hasil**: Ketika node server worker reboot di Jakarta, LSA Type 1 & 7 berfluktuasi lokal di Area 10 saja. Area 0 dan Area 20 tidak menerima pembaharuan LSA sama sekali, penggunaan CPU router core stabil di < 5%, dan zero-packet-drop tercapai.

---

## 12. Trade-offs

| Aspek Teknis | OSPF (Multi-Area) | IS-IS (Multi-Level) | EIGRP | eBGP (RFC 7938 Leaf-Spine) |
|---|---|---|---|---|
| **Kompleksitas Desain** | Tinggi (Harus strictly hierarchic via Area 0). | Menengah (Batas area di link; fleksibel membagi level). | Rendah (Fleksibel, namun proprietary logic). | Menengah-Tinggi (ASN allocation dan route filtering ketat). |
| **Kapasitas Skalabilitas** | ~1000 - 3000 router per domain dengan tuning. | >10000 router per domain (sangat dioptimalkan untuk scale). | ~1000 router. | Puluhan ribu (Standar Hyperscale DC Fabric). |
| **Konsumsi Memory & CPU** | Moderat ke Tinggi saat SPF recomputation. | Sangat Rendah (PDU binary framing efisien). | Rendah (Hanya DUAL recomputation saat rute down). | Sangat terprediksi (Incremental update; no SPF). |
| **Fleksibilitas Protokol Baru** | Butuh modifikasi OSPF engine (OSPFv2 vs OSPFv3 terpisah). | Luar biasa fleksibel via TLV baru tanpa ubah core protocol. | Terbatas pada ekosistem Cisco. | Luar biasa tinggi (Multiprotocol BGP Extensions). |

---

## 13. When To Use
- **Gunakan OSPF ketika**:
  - Membangun arsitektur jaringan Enterprise LAN, Campus, atau WAN multi-vendor konvensional.
  - Mayoritas insinyur operasional tim NOC/SRE telah familiar dengan terminologi dan command OSPF.
  - Membutuhkan segmentasi area yang ketat untuk mengisolasi ribuan rute dinamis cabang (Branch/Retail).
- **Gunakan IS-IS ketika**:
  - Menggelar jaringan Tier-1 Internet Service Provider (ISP), Telco Core (4G/5G Backhaul), atau MPLS/Segment Routing Backbone berskala ribuan router.
  - Membangun arsitektur Underlay Data Center Spine-and-Leaf yang mengutamakan kecepatan konvergensi absolut dan efisiensi CPU hardware.
  - Mengoperasikan dual-stack IPv4 dan IPv6 secara masif dengan single control-plane routing protocol.

---

## 14. When NOT To Use
- **Jangan gunakan OSPF/IS-IS untuk**:
  - Routing antar organisasi eksternal / multi-homing Internet (Gunakan **eBGP** karena IGP tidak memiliki mekanisme expressive policy control seperti AS-Path prepend, MED, Communities).
  - Topologi jaringan yang bersifat Dynamic Multipoint VPN (DMVPN) skala besar dengan ribuan spoke node (Karakteristik link-state flooding akan melumpuhkan headend; gunakan **BGP** atau **EIGRP**).
  - Jaringan IoT dengan bandwidth sangat terbatas (misal LoRaWAN, satelit maritim low-bitrate) karena overhead keepalive hello dan LSA synchronization terlalu masif.

---

## 15. Common Mistakes
1. **MTU Mismatch pada Interface**: Terjadi saat interface A memiliki MTU 1500 byte dan interface B memiliki MTU 9000 byte. State OSPF akan stuck permanen di **ExStart/Exchange** karena paket DBD yang besar di-drop oleh interface ber-MTU rendah.
2. **Duplikasi Router ID (RID)**: Mengkloning konfigurasi template tanpa mengubah RID manual. Gejalanya: LSDB saling menimpa (*LSA thrashing*), rute hilang-timbul (*route flapping*), dan SPF loop tanpa akhir.
3. **Mismatched OSPF Timers / Area Types / Subnet Mask**:
   - Hello dan Dead intervals berbeda antara neighbor (neighbor langsung drop).
   - Area ID berbeda atau salah satu diset `stub` sementara tetangganya `standard` (flag $E$-bit mismatch).
   - Pada link Ethernet broadcast, netmask wajib identik; jika berbeda, neighbor tertahan di status `Init`.
4. **Membiarkan Network Type Default pada P2P Link**: Menggunakan tipe network `Broadcast` pada link direct inter-router (`/30` atau `/31`), yang memicu overhead pemilihan DR/BDR dan keterlambatan konvergensi (menunggu Dead Interval penuh saat reload).
5. **Summarization Tanpa Menghitung Subnet Coverage (Blackholing)**: Meringkas `10.0.0.0/16` di ABR sementara ada subnet `10.0.50.0/24` yang berada di area lain di luar kendali ABR tersebut. Paket menuju `10.0.50.0/24` akan terserap dan dibuang oleh discard route (`Null0`) ABR.

---

## 16. Best Practices
1. **Always Hardcode Router ID**: Gunakan loopback interface IP yang stabil dan tetapkan explicit CLI: `router-id 10.255.x.x`.
2. **Explicit Link Types**: Selalu nyatakan `ip ospf network point-to-point` pada interface point-to-point untuk meniadakan DR/BDR election.
3. **Passive-Interface Default Paradigm**: Eksekusi perintah `passive-interface default` secara global di dalam process OSPF, lalu definisikan secara eksplisit `no passive-interface <intf>` hanya pada port transit yang terhubung ke router OSPF lain. Hal ini mencegah security breach di mana host liar menginjeksi rogue LSA.
4. **Tune Reference Bandwidth Globally**: Standarkan seluruh router ke nilai yang relevan untuk generasi modern (misal: `auto-cost reference-bandwidth 1000000` / 1 Tbps). Jika ada satu router yang lupa diubah, kalkulasi cost SPF akan menjadi asimetris dan memicu sub-optimal routing.
5. **Bidirectional Forwarding Detection (BFD)**: Integrasikan OSPF/IS-IS dengan BFD hardware offload (`ip ospf bfd`) untuk mendeteksi link failures dalam level sub-50 milidetik tanpa harus menurunkan timer OSPF Hello/Dead ke nilai ekstrem yang membebani CPU.

---

## 17. Troubleshooting Guide
Panduan terstruktur saat menangani insiden OSPF:

```
[Is Neighbor Up?]
       |
       +---> NO: Periksa Layer 1/2 & Subnet (Ping Link-Local / Unicast IP).
       |         Periksa ACL (Blokir IP Protocol 89?).
       |         Verifikasi Timers (Hello/Dead) & Area ID (`show ip ospf interface`).
       |
       +---> STUCK IN INIT:
       |         Unidirectional traffic. Periksa firewall/switch L2 dropping return Hello.
       |
       +---> STUCK IN 2-WAY:
       |         Normal jika kedua router berstatus DROther pada segment Broadcast.
       |         Jika terjadi pada P2P link: network type mismatch.
       |
       +---> STUCK IN EXSTART / EXCHANGE:
       |         100% akar masalah hampir selalu: MTU MISMATCH!
       |         Verifikasi MTU via: `show ip ospf interface <id> | include MTU`.
       |         Workaround darurat: `ip ospf mtu-ignore` (Hanya sementara!).
       |
       +---> FULL TAPI ROUTE TIDAK MUNCUL DI TABEL ROUTING:
                 Periksa apakah IP Subnet mask identik di kedua ujung.
                 Periksa apakah Forwarding Address (FA) LSA Type 5/7 reachable via OSPF.
                 Verifikasi apakah ada filter `distribute-list in` aktif.
```

Perintah Diagnostik Esensial:
- Cisco/Arista:
  - `show ip ospf neighbor` -> Status adjacency FSM.
  - `show ip ospf database` -> Memeriksa LSDB summary.
  - `show ip ospf database router <router-id>` -> Memeriksa LSA Type 1 detail.
  - `show ip route ospf` -> Menampilkan rute OSPF yang masuk ke RIB.
  - `debug ip ospf adj` / `debug ip ospf packet` -> Debugging real-time handshake.
- Linux (FRR):
  - `vtysh -c "show ip ospf neighbor"`
  - `vtysh -c "show ip ospf database"`

---

## 18. Exercise
Jawablah latihan teknis berikut secara analitis:
1. Sebuah link Ethernet menghubungkan Router A dan Router B. Interface Router A dikonfigurasi dengan MTU 1500, sementara interface Router B dikonfigurasi dengan Jumbo Frame MTU 9000. 
   - Pada state FSM manakah proses pembentukan neighbor OSPF akan terhenti? Jelaskan detail paket yang menyebabkan kebuntuan tersebut!
2. Dalam sebuah OSPF area multi-access dengan 5 router (semua priority default = 1):
   - Berapa jumlah total Full adjacency yang terbentuk pada interface LAN tersebut?
   - Tuliskan formula matematis untuk menghitung jumlah adjacency pada broadcast domain dengan $N$ router!
3. Sebutkan perbedaan perilaku LSA Type 3 antara Stub Area dan Totally Stubby Area!

---

## 19. Challenge
Rancang arsitektur IP Addressing dan Skema Area OSPFv2 untuk enterprise multi-site berikut:
- **Core Transit Backbone (Area 0)**: 4 Core Router terhubung full-mesh point-to-point.
- **Regional Data Center 1 (Area 10)**: Memiliki 40 subnet server (`172.16.0.0/24` hingga `172.16.39.0/24`).
- **Regional Data Center 2 (Area 20)**: Memiliki 40 subnet server (`172.16.64.0/24` hingga `172.16.103.0/24`).
- **Edge Cabang Remote (Area 30)**: Memiliki router cabang dengan RAM/CPU sangat rendah, hanya butuh konektivitas keluar.

Tugas Arsitektur:
1. Tentukan jenis area yang paling optimal untuk masing-masing Area 10, Area 20, dan Area 30!
2. Rancang satu blok CIDR summary yang presisi (paling hemat/tight) untuk Area 10 dan Area 20 agar tabel routing di Backbone Core seminimal mungkin!
3. Tuliskan blok konfigurasi deklarasi summarization dan area type pada ABR!

---

## 20. Summary
- Algoritma **Dijkstra SPF** menghasilkan jalur terpendek bebas loop berbasis kalkulasi matematis terhadap graf lengkap yang tersimpan secara identik dalam **LSDB** seluruh router dalam area yang sama.
- Pembentukan OSPF Adjacency melewati serangkaian **FSM**: *Down -> Init -> 2-Way -> ExStart -> Exchange -> Loading -> Full*. State **2-Way** adalah status sah antar sesama DROther, sedangkan **Full** wajib dicapai pada P2P link dan ke arah DR/BDR.
- **Designated Router (DR)** memitigasi masalah skalabilitas full-mesh LSA flooding pada multi-access network dengan menjadi simpul agregasi pertukaran LSA melalui multicast `224.0.0.5` dan `224.0.0.6`.
- **Special Areas (Stub, Totally Stubby, NSSA)** dan **Route Summarization** adalah tools arsitektural utama untuk mereduksi ukuran LSDB, menahan fluktuasi rute (fault containment), dan membatasi resource footprint CPU/memory pada enterprise berskala besar.
- **IS-IS** beroperasi langsung pada Data Link Layer (L2), menggunakan format **TLV** yang modular dan extensible, menjadikannya arsitektur backbone pilihan utama untuk Telco Core, Segment Routing, dan Hyperscale Cloud Fabric.