# BAB 05: Interior Gateway Dynamic Routing (OSPF & IS-IS)
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Merancang** arsitektur *hierarchical link-state routing* (OSPFv2/OSPFv3 multi-area dan IS-IS multi-level) untuk jaringan skala *Enterprise Core* dan *Service Provider Backbone*.
- **Mengimplementasikan** mekanisme *Fast Convergence* tingkat lanjut: BFD (*Bidirectional Forwarding Detection*), *LSA/SPF Throttling*, serta *Loop-Free Alternates* (LFA & TI-LFA / *Topology-Independent LFA*).
- **Mengeksekusi** redistribusi rute (*mutual route redistribution*) dua arah antara OSPF dan IS-IS secara deterministik menggunakan *route tagging*, *prefix-lists*, dan manipulasi *Administrative Distance* tanpa menimbulkan *routing loop* atau *sub-optimal routing*.
- **Mengisolasi dan Memitigasi** anomali protokol *link-state*: MTU *mismatch*, *database corruption*, *split-horizon violation* pada redistribusi, serta *micro-loops* selama rekonvergensi jaringan.
- **Mengoperasikan** strategi pemeliharaan nir-henti (*zero-downtime maintenance*) memanfaatkan *OSPF Stub Router Advertisement* (*Max-Metric Router LSA*) dan *IS-IS Overload Bit* (OL-bit).

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Konsep Fundamental Link-State**: Operasi dasar OSPF (Area 0, Router ID, pembentukan *Neighbor Adjacency*, DR/BDR) dan IS-IS (*System ID*, NET, DIS).
- **Format Paket LSA OSPF & PDU IS-IS**: Memahami struktur Hello, DBD, LSR, LSU, LSAck (OSPF) serta IIH, CSNP, PSNP, LSP (IS-IS).
- **Model Pengalamatan IP**: IPv4 subnetting lanjutan (VLSM) dan arsitektur pengalamatan IPv6 (GUA, Link-Local).
- **Penguasaan Linux & CLI Jaringan**: Operasional dasar CLI Cisco IOS-XE/Arista EOS dan Linux Networking Stack (FRRouting/IPRoute2).

---

### 3. Concept & Internal Architecture

#### A. Algoritma Dijkstra (Shortest Path First) & Optimasi Komputasi
Protokol *link-state* mendistribusikan salinan topologi jaringan yang identik ke setiap *node* di dalam satu *flooding domain*. Setiap *node* menyimpan informasi ini di dalam *Link-State Database* (LSDB untuk OSPF, Link-State Packet Database / LSPDB untuk IS-IS) dan mengeksekusi algoritma Dijkstra Shortest Path First (SPF) dengan kompleksitas waktu standar $O(E + V \log V)$, di mana $V$ adalah jumlah *node* (router) dan $E$ adalah jumlah *link*.

```
   [ Topology Change Detected ]
                │
                ▼
   [ LSA / LSP Generation Throttling ]
   (Hold-down / Exponential Backoff)
                │
                ▼
   [ Flooding to Neighbors ] ──> (Bypass local SPF wait)
                │
                ▼
   [ SPF Run Throttling ]
   (Initial Delay -> Hold Time -> Max Wait)
                │
                ▼
   ┌────────────────────────────────────────┐
   │ Full SPF vs Incremental SPF (iSPF)     │
   │ vs Partial Route Computation (PRC)     │
   └────────────────────────────────────────┘
                │
                ▼
   [ Route Installation to RIB -> FIB ]
```

Dalam jaringan produksi skala besar, eksekusi *Full SPF* untuk setiap perubahan rute adalah anti-pola. Optimasi dilakukan melalui:
1. **Full SPF**: Menghitung ulang seluruh graf topologi dari *root node*. Dijalankan hanya saat terjadi perubahan *transit link* (koneksi antar-router).
2. **Incremental SPF (iSPF)**: Hanya menghitung ulang cabang dari *Shortest Path Tree* (SPT) yang terpengaruh tanpa merombak seluruh topologi.
3. **Partial Route Computation (PRC)**: Digunakan ketika hanya terjadi perubahan *leaf network* (prefix internal/stub, bukan perubahan topologi *transit*). IS-IS secara arsitektural memisahkan informasi topologi dari informasi prefix (*IP Reachability TLV*), membuat PRC berjalan secara *native* dan jauh lebih efisien dibanding OSPFv2 (yang membutuhkan Type-1/Type-2 LSA parsing).

#### B. Anatomi LSA OSPFv2/v3 vs TLV IS-IS
Arsitektur OSPF terikat erat pada tipe-tipe LSA yang kaku, sementara IS-IS bersifat modular berbasis *Type-Length-Value* (TLV) yang memungkinkan perluasan protokol (*extensibility*) tanpa mengubah *core state machine*.

| Fungsi Arsitektural | OSPFv2 (IPv4) | OSPFv3 (IPv6 / Multi-AF) | IS-IS (Dual-Stack) |
| :--- | :--- | :--- | :--- |
| **Deskripsi Router/Node** | Type 1 (Router LSA) | Type 1 (Router LSA) | TLV 1024 (IS Neighbor), TLV 22 (Extended IS Reachability) |
| **Transit Network / Pseudo-node** | Type 2 (Network LSA) | Type 2 (Network LSA) | TLV 22 (Extended IS Reachability to Pseudo-node) |
| **Inter-Area Prefix Reachability** | Type 3 (Summary LSA) | Type 3 (Inter-Area-Prefix) | TLV 135 (Extended IP Reachability), TLV 236 (IPv6 IP Reachability) |
| **Inter-Area Router Reachability** | Type 4 (ASBR Summary) | Type 4 (Inter-Area-Router) | Terintegrasi dalam TLV 22/135 |
| **External Routes** | Type 5 (AS-External) | Type 5 (AS-External) | TLV 135 / TLV 236 dengan External Bit flag |
| **NSSA External Routes** | Type 7 (NSSA-External) | Type 7 (NSSA-External) | Tidak ada konsep NSSA; menggunakan Level-1 routing policy |
| **Router Capability / TE** | Type 9/10/11 (Opaque) | Type 9/10/11 (Opaque) | TLV 242 (Router Capability) |

#### C. OSPF Non-Backbone Area Types
Untuk menekan ukuran LSDB dan batas propagasi *flooding*, OSPF membagi hierarki area:
- **Stub Area**: Menolak LSA Type 4 dan 5 (eksternal). Keluar area mengandalkan rute *default* (LSA Type 3) yang di-generate oleh ABR.
- **Totally Stubby Area (Cisco Proprietary)**: Menolak LSA Type 3, 4, dan 5. Hanya menyisakan satu LSA Type 3 yang bertindak sebagai *default route*.
- **Not-So-Stubby Area (NSSA)**: Menolak LSA Type 4 dan 5 dari area luar, tetapi mengizinkan ASBR internal menginjeksi rute eksternal menggunakan LSA Type 7. ABR kemudian mentranslasikan LSA Type 7 menjadi LSA Type 5 (P-bit / *Propagate bit* = 1) sebelum diteruskan ke Area 0.
- **NSSA Totally Stubby**: Menolak LSA Type 3, 4, 5 eksternal, mengizinkan redistribusi lokal via LSA Type 7, dan menginjeksi rute *default* tunggal via LSA Type 3.

#### D. IS-IS Hierarchical Architecture: Level-1 vs Level-2
IS-IS mengadopsi segmentasi hierarki berbasis *node*, bukan berbasis *interface* seperti OSPF:
- **Level-1 (L1)**: Merutekan trafik intra-area (mirip OSPF Non-Backbone Stub). L1 router tidak mengenal prefix di luar areanya; mereka mengandalkan bit ATT (*Attached Bit*) yang dipasang oleh router L1/L2 pada LSP untuk membentuk *default route* terdekat.
- **Level-2 (L2)**: Merutekan trafik inter-area dan membentuk *backbone transit*.
- **Level-1-2 (L1/L2)**: Berperan sebagai router batas (analog dengan ABR pada OSPF). Memiliki dua LSPDB terpisah: LSPDB L1 dan LSPDB L2.
- **Wide Metrics (TLV 135)**: Menggantikan metrik lama (6-bit, max interface cost 63) menjadi metrik 24-bit (max interface cost 16.777.215), wajib diaktifkan pada jaringan modern untuk mendukung Traffic Engineering dan Segment Routing.

---

### 4. Why & What

| Problem Domain | Tanpa Desain Lanjutan (Flat/Default) | Dengan Implementasi Lanjutan (Enterprise Standard) |
| :--- | :--- | :--- |
| **Skalabilitas LSDB** | LSDB datar membengkak; satu perubahan link memicu kalkulasi SPF global ke ribuan router. | Segmentasi Area/Level, LSA Filtering, Summary Prefix, dan Stub/NSSA membatasi *blast radius* kegagalan. |
| **Waktu Rekonvergensi** | Konvergensi rute memakan waktu 5-10 detik (menunggu hilangnya paket Hello & pemrosesan SPF serial). | Deteksi sub-50ms via BFD, SPF Throttling dinamis, dan TI-LFA *pre-computed backup path* sub-50ms. |
| **Redistribusi Rute** | Risiko tinggi *routing loops*, *route flapping*, dan *sub-optimal paths* akibat perbedaan metrik & *Administrative Distance*. | Isolasi deterministik via *Route Tagging*, *Prefix-List Filtering*, dan rekayasa AD/Metric. |
| **Downtime Pemeliharaan** | Router reboot memicu *blackhole traffic* selama transisi dan re-establishment *adjacency*. | Graceful degradation menggunakan *Max-Metric LSA* (OSPF) atau *Overload Bit* (IS-IS) sebelum proses reboot. |

---

### 5. How (Workflow Detail)

#### Mekanisme Sub-Second Convergence: BFD ke TI-LFA Pipeline
```
[ Hardware Link Failure ]
          │
          ▼ (< 10ms via BFD Asynchronous Mode)
[ BFD Session State: DOWN ]
          │
          ▼ (Fast-Path Interrupt to IGP)
[ IGP Adjacency Torn Down ]
          │
          ▼ (< 1ms via Line-Card Hardware)
[ Switchover to TI-LFA / LFA Backup Next-Hop in FIB ]
  ==> TRAFFIC CONTINUES TO FLOW (Packet loss < 50ms)
          │
          ▼ (Control Plane Processing)
[ LSA/LSP Generation (Throttled via Exponential Backoff) ]
          │
          ▼
[ Flood Updated LSA/LSP to Core ]
          │
          ▼
[ Run SPF Tree Recalculation (Hold-timer delayed) ]
          │
          ▼
[ Update RIB -> Re-program Primary Paths in FIB ]
```

1. **Deteksi**: Hardware/transceiver mendeteksi hilangnya sinyal (LOS) atau BFD mendeteksi *keepalive timeout* (misal $3 \times 50\text{ ms} = 150\text{ ms}$).
2. **Local Repair**: Data plane langsung membelokkan *egress traffic* ke rute proteksi (*Repair Path*) yang telah dihitung sebelumnya (*pre-computed*) melalui **Topology-Independent Loop-Free Alternate (TI-LFA)** tanpa menunggu konvergensi SPF selesai.
3. **Flooding**: Control plane membangkitkan LSA/LSP update dan menyebarkannya dengan mekanisme *generation throttling* untuk mencegah *LSA storming*.
4. **Delayed Global SPF**: Setiap router menunda komputasi SPF menggunakan algoritma penundaan eksponensial (*SPF throttling*) guna mengumpulkan seluruh update topologi yang terkait (*event dampening*).
5. **Convergence**: SPF selesai, rute optimal baru dipasang ke Routing Information Base (RIB) dan Forwarding Information Base (FIB), menggantikan rute TI-LFA sementara.

---

### 6. Analogy & Diagram ASCII

#### A. Analogi Sistem Jalan Raya (OSPF Multi-Area vs IS-IS Hierarki)
- **OSPF Multi-Area**: Seperti sebuah negara di mana **seluruh** jalan antar-wilayah wajib melewati **Ibu Kota Negara (Area 0)**. Kota-kota satelit (Non-Backbone Area) tidak boleh memiliki jalan tol langsung ke kota satelit lain tanpa izin/melewati ring road Ibu Kota.
- **IS-IS Multi-Level**: Seperti jaringan jalan tol di mana kendaraan di jalan arteri lokal (Level-1) tinggal diarahkan ke gerbang tol keluar terdekat (Level-1-2 Router via *default route*), dan seluruh sistem jalan bebas hambatan (Level-2) membentuk koridor terhubung secara fleksibel tanpa harus terkonsentrasi pada satu nomor zona kaku.

#### B. Diagram Arsitektur Enterprise Core Dual-IGP dengan Boundary ABR/ASBR

```
    [ DATA CENTER REGION ]                   [ ENTERPRISE WAN BACKBONE ]
       (IS-IS Level-1)                             (OSPF Multi-Area)

   +--------------------+                       +--------------------+
   | Leaf-101  Leaf-102|                       | Branch-A  Branch-B |
   +---------┬──────────+                       +─────────┬──────────+
             │                                            │
   +---------┴──────────+                       +---------┴──────────+
   |  Spine-01/Spine-02 │                       |  WAN ABR-01 / 02   |
   |   (IS-IS Level-1)  |                       |   (OSPF Area 10)   |
   +---------┬──────────+                       +---------┬──────────+
             │                                            │
      ===============                              ===============
      IS-IS Level-1/2                              OSPF Area 0
      ===============                              ===============
             │                                            │
   +---------┴────────────────────────────────────────────┴──────────+
   |                    CORE-BORDER-01 / CORE-BORDER-02             |
   |  - IS-IS L2 Engine (NET: 49.0001.0000.0000.0001.00)            |
   |  - OSPFv2 Area 0 Engine (Router-ID: 10.255.255.1)               |
   |  - Mutual Redistribution Engine with Tagging:                  |
   |      * ISIS -> OSPF: Tag 110 (Source: ISIS)                     |
   |      * OSPF -> ISIS: Tag 120 (Source: OSPF)                     |
   |      * Loop Prevention: Deny incoming routes with matched tag   |
   +-----------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Practical Example: Konfigurasi OSPF Advanced (Arista EOS / Cisco IOS-XE Style)
Contoh berikut menerapkan OSPFv2 multi-area, *Area NSSA Totally Stubby*, *Fast Timers*, *BFD*, dan *Authentication*:

```text
! Konfigurasi pada Edge-Aggregation-01 (ABR)
router ospf 1
 router-id 10.255.255.10
 ! Mengaktifkan BFD secara global pada seluruh interface OSPF
 bfd all-interfaces
 ! Optimasi Timer SPF: init-delay 50ms, min-hold 200ms, max-wait 2000ms
 timers throttle spf 50 200 2000
 ! Optimasi LSA Generation Throttling
 timers throttle lsa all 50 200 2000
 ! Transmisi LSA cepat tanpa batasan default 1 detik
 timers lsa arrival 100
 ! Mengonfigurasi Area 20 sebagai NSSA Totally Stubby (no-summary)
 area 20 nssa no-summary
 ! Agregasi/Summarization prefix dari Area 20 menuju Area 0
 area 20 range 10.20.0.0 255.255.0.0
 ! Hardening: Mengamankan inter-area link dengan HMAC-SHA-256
 area 0 authentication message-digest
!
interface Ethernet1/1
 description UPLINK-TO-CORE-01 (Area 0)
 ip address 10.0.0.1 255.255.255.252
 ip ospf network point-to-point
 ip ospf authentication message-digest
 ip ospf message-digest-key 1 md5 c38f90a98d3e6f2120e8b2
 ip ospf bfd
!
interface Ethernet1/2
 description DOWNLINK-TO-BRANCH-AGG (Area 20)
 ip address 10.20.255.1 255.255.255.252
 ip ospf network point-to-point
 ip ospf cost 10
!
```

#### B. Practical Example: Konfigurasi Produksi IS-IS Dual-Stack (IPv4/IPv6) dengan Wide Metrics
Implementasi IS-IS pada Spine Router menggunakan FRRouting (`frr.conf`):

```text
! File: /etc/frr/frr.conf
frr version 8.5_git
frr defaults traditional
hostname SPINE-01
!
interface eth1
 description P2P-LINK-TO-LEAF-01
 ip address 10.100.0.1/31
 ipv6 address 2001:db8:100::1/127
 ip router isis PROD-FABRIC
 ipv6 router isis PROD-FABRIC
 isis circuit-type level-1
 isis network point-to-point
 isis metric 100 level-1
 isis bfd
!
router isis PROD-FABRIC
 is-type level-1
 net 49.0001.0102.5525.5001.00
 ! Wajib: Mengaktifkan Wide Metrics untuk 32-bit/24-bit metric support
 metric-style wide
 ! Multi-topology routing untuk separasi rute IPv4 dan IPv6
 topology ipv6-unicast
 ! Optimasi konvergensi LSP
 lsp-gen-interval 1
 spf-interval 1
!
```

---

### 8. Real World Case Study: Enterprise Backbone Migration & Loop Prevention

#### Latar Belakang
Sebuah institusi perbankan berskala multinasional mengakuisisi perusahaan *fintech*. Jaringan Bank menggunakan **IS-IS** sebagai backbone data center mereka, sedangkan *fintech* menggunakan arsitektur **OSPFv2 Multi-Area**. Kedua entitas harus diinterkoneksikan pada dua titik *Edge Border Router* independen (Dual-Homed ABR/ASBR) untuk menjaga ketersediaan tinggi (*high availability*).

#### Masalah Kritis
Redistribusi timbal balik secara naif (*mutual redistribution without route filtering*) menyebabkan kondisi:
1. Rute yang berasal dari IS-IS diinjeksi ke OSPF oleh Border-01.
2. Border-02 menerima rute OSPF tersebut, dan karena *Administrative Distance* OSPF (110) lebih disukai daripada IS-IS Level-2 External di platform tertentu, Border-02 menginjeksi rute itu kembali ke IS-IS.
3. Terjadi **Micro-Looping**, **Sub-Optimal Routing** (trafik memutar melalui link inter-border alih-alih jalur internal terpendek), dan **Route Flapping** yang menenggelamkan CPU router.

#### Solusi Arsitektur: Route Tagging Deterministic Policy
Menerapkan skema *Tag-Based Mutual Redistribution*:
- Rute asal IS-IS saat masuk ke OSPF diberi tanda `Tag 110`.
- Rute asal OSPF saat masuk ke IS-IS diberi tanda `Tag 120`.
- Border-01 dan Border-02 dilarang menginjeksi rute kembali jika rute tersebut membawa tag kepemilikan aslinya.

```text
! Konfigurasi di CORE-BORDER-01 (Cisco IOS-XE)
!
ip prefix-list RFC1918-ONLY permit 10.0.0.0/8 le 24
ip prefix-list RFC1918-ONLY permit 172.16.0.0/12 le 24
ip prefix-list RFC1918-ONLY permit 192.168.0.0/16 le 24
!
route-map ISIS_TO_OSPF deny 10
 description Drop routes originating from OSPF to prevent loop
 match tag 120
!
route-map ISIS_TO_OSPF permit 20
 description Tag routes originating from ISIS
 match ip address prefix-list RFC1918-ONLY
 set tag 110
 set metric 20
 set metric-type type-2
!
route-map OSPF_TO_ISIS deny 10
 description Drop routes originating from ISIS to prevent loop
 match tag 110
!
route-map OSPF_TO_ISIS permit 20
 description Tag routes originating from OSPF
 match ip address prefix-list RFC1918-ONLY
 set tag 120
 set metric 50
!
router ospf 100
 router-id 10.255.255.1
 redistribute isis PROD-CORE route-map ISIS_TO_OSPF subnets
!
router isis PROD-CORE
 net 49.0001.0000.0000.0001.00
 metric-style wide
 redistribute ospf 100 route-map OSPF_TO_ISIS metric 50
!
```

---

### 9. Trade-offs

| Pendekatan Desain | Keuntungan | Kerugian / Risiko | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Aggressive BFD (3 x 10ms)** | Deteksi kegagalan link super cepat (30ms). | Beban CPU tinggi pada router tanpa *hardware-offloaded BFD*; rentan *false-positive flap* akibat *control-plane congestion*. | Core Links antar spine/core router dengan *hardware ASIC offloading*. |
| **Single Flat Area (OSPF Area 0 / IS-IS L2)** | Desain sederhana, konfigurasi minimal, tidak memerlukan perancangan boundary ABR/L1L2. | Skalabilitas buruk. Setiap perubahan antarmuka memicu komputasi SPF penuh di seluruh router domain. | Lingkungan skala menengah (< 100 router total). |
| **Aggressive Summarization pada ABR** | Menekan ukuran routing table secara drastis; mengisolasi *link flap* dalam area lokal. | Mengeliminasi visibilitas metrik spesifik; berpotensi menimbulkan *blackholing* jika ada *hole* di subnet internal (*discard route requirement*). | Skala Enterprise Besar (> 300 router) & Multi-Region DC. |
| **Topology-Independent LFA (TI-LFA)** | Garansi proteksi jalur 100% dari *single point of failure* dengan konvergensi sub-50ms. | Mengonsumsi resource memori FIB lebih besar (menyimpan rute *primary* dan *repair* bersamaan); kompleksitas komputasi label path (Segment Routing). | Jaringan Mission-Critical, Financial Services, Telco Core Backhaul. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: OSPF Neighbor Macet di State `EXSTART/EXCHANGE`
- **Gejala**: Perintah `show ip ospf neighbor` menunjukkan status tetangga macet di `EXSTART/EXCHANGE` dan tidak pernah mencapai `FULL`.
- **Akar Masalah**: Ketidakcocokan nilai MTU pada *link point-to-point*. Router yang mengirim paket DBD berukuran lebih besar dari MTU interface tetangganya akan di-*drop*, sehingga negosiasi *Master/Slave* gagal diselesaikan.
- **Langkah Remediasi**:
  1. Jalankan `show interfaces <if-name> | include MTU`.
  2. Samakan MTU di kedua sisi link (misal: 1500 atau 9000 untuk Jumbo Frames).
  3. Workaround darurat jika MTU di luar kendali operator (misal: melewati transparent L2 provider): Masukkan perintah `ip ospf mtu-ignore` pada interface yang terdampak.

#### Skenario 2: IS-IS Neighbor Tidak Mau Membentuk Adjacency
- **Akar Masalah Umum**:
  - *System ID* bentrok (duplikat).
  - *Area Address* berbeda pada pembentukan adjasensi Level-1 (Level-1 mengharuskan Area Address identik, sedangkan Level-2 mengizinkan Area Address berbeda).
  - Ketidakcocokan MTU LSP (*LSP MTU sizing* default IS-IS adalah 1492 byte; jika link memiliki MTU < 1492 dan padding diaktifkan, Hello packet akan didrop).
- **Langkah Troubleshooting**:
  ```bash
  # Verifikasi state adjacency dan alasan kegagalan
  show isis neighbors detail
  
  # Cek konsistensi MTU dan Level pembentukan
  show isis interface detail
  
  # Nonaktifkan padding hello packet jika MTU terbatas
  ! Cisco IOS-XE / Arista EOS:
  interface Ethernet1
   isis hello-padding disable
  ```

#### Skenario 3: Routing Loop Akibat Pengubahan Administrative Distance (AD)
- **Gejala**: Traceroute antar-cabang berputar tanpa akhir (*looping*), lonjakan *CPU load* router hingga 100%, terjadi penurunan packet secara massal (*TTL expired*).
- **Akar Masalah**: Operator mengubah nilai *Administrative Distance* OSPF External (default 110) lebih rendah daripada internal protokol lain untuk mengarahkan trafik, memicu *race condition* di mana rute redistribusi diakui sebagai rute terbaik di router yang salah.
- **SOP Troubleshooting Loop IGP**:
  1. Temukan router dengan beban antrian interface tinggi via `show ip route summary`.
  2. Lacak riwayat perubahan tabel routing dengan `show ip route track` atau cek log `OSPF-4-ROUTER_ID_DUPLICATE` / `ROUTING-FLAP`.
  3. Lacak *prefix tag* yang berputar menggunakan `show ip route <prefix>`.
  4. Bersihkan rute eksternal dan terapkan `deny match tag <tag>` secara tegas pada semua batas redistribusi.

---

### 11. Best Practices (Production Checklist)

1. **Gunakan Point-to-Point Network Type pada Link Transit**:
   Hindari tipe *broadcast* pada link yang hanya menghubungkan 2 router:
   ```text
   interface GigabitEthernet0/0/1
    ip ospf network point-to-point
   ```
   *Alasan*: Meniadakan kebutuhan pemilihan DR/BDR, menghemat 2 Hello interval delay saat pembentukan adjasensi, dan menyederhanakan SPT.

2. **Isolasi Node Pemeliharaan Tanpa Downtime**:
   - Untuk OSPF: Terapkan *Max-Metric LSA* agar router tetangga mengalihkan trafik tanpa memutus adjasensi:
     ```text
     router ospf 1
      max-metric router-lsa on-startup wait-for-bgp
      ! Saat maintenance darurat:
      max-metric router-lsa
     ```
   - Untuk IS-IS: Set bit overload (OL-bit):
     ```text
     router isis PROD
      set-overload-bit on-startup 300
      ! Saat maintenance:
      set-overload-bit
     ```

3. **Terapkan Prefix Summarization di ABR/L1-L2**:
   - Selalu generate *discard route* ke `Null0` secara otomatis untuk meredam potensi *packet bouncing loop* saat downstream subnet tidak dapat dijangkau.

4. **Wajibkan Autentikasi Kriptografis Kuat**:
   - Tinggalkan Simple Password dan MD5 yang rentan tabrakan (*hash collision*). Gunakan `HMAC-SHA-256` atau `IPsec-based authentication` (OSPFv3).

5. **Optimasi Reference Bandwidth**:
   - Default reference bandwidth OSPF adalah 100 Mbps (interface 1 Gbps, 10 Gbps, 100 Gbps memiliki cost yang sama: 1). Konfigurasikan pada core:
     ```text
     router ospf 1
      auto-cost reference-bandwidth 1000000  ! Mendukung hingga 1 Tbps link
     ```

---

### 12. Hands-on Practice: Multi-Area OSPF & IS-IS Redistribution Lab

Struktur direktori praktikum:
```text
hands-on/m02/
├── topology.clab.yml
├── configs/
│   ├── core-r1/
│   │   └── frr.conf
│   ├── core-r2/
│   │   └── frr.conf
│   └── branch-r1/
│       └── frr.conf
└── verify.sh
```

#### Langkah 1: Siapkan Definisi Topologi Containerlab (`topology.clab.yml`)
```yaml
name: igp-advanced-lab
topology:
  nodes:
    branch-r1:
      kind: linux
      image: frrouting/frr:v8.5.2
      binds:
        - configs/branch-r1/frr.conf:/etc/frr/frr.conf
        - configs/daemons:/etc/frr/daemons
    core-r1:
      kind: linux
      image: frrouting/frr:v8.5.2
      binds:
        - configs/core-r1/frr.conf:/etc/frr/frr.conf
        - configs/daemons:/etc/frr/daemons
    core-r2:
      kind: linux
      image: frrouting/frr:v8.5.2
      binds:
        - configs/core-r2/frr.conf:/etc/frr/frr.conf
        - configs/daemons:/etc/frr/daemons

  links:
    - endpoints: ["branch-r1:eth1", "core-r1:eth1"]
    - endpoints: ["core-r1:eth2", "core-r2:eth2"]
```

#### Langkah 2: Buat Konfigurasi Daemons FRR (`configs/daemons`)
```ini
zebra=yes
ospfd=yes
isisd=yes
bfdd=yes
```

#### Langkah 3: Konfigurasi Boundary Router CORE-R1 (`configs/core-r1/frr.conf`)
```text
frr version 8.5.2
hostname CORE-R1
password zebra
enable password zebra
!
interface eth1
 description OSPF-TO-BRANCH
 ip address 10.0.12.1/30
 ip ospf network point-to-point
 ip ospf area 10
!
interface eth2
 description ISIS-TO-CORE-R2
 ip address 10.0.23.1/30
 ip router isis FABRIC
 isis circuit-type level-2
 isis network point-to-point
!
interface lo
 ip address 10.255.255.1/32
 ip ospf area 0
 ip router isis FABRIC
!
route-map RM_ISIS_TO_OSPF permit 10
 match tag 200
!
route-map RM_OSPF_TO_ISIS permit 10
 set tag 100
!
router ospf
 ospf router-id 10.255.255.1
 area 10 nssa
 timers throttle spf 50 100 1000
 timers throttle lsa 50 100 1000
!
router isis FABRIC
 net 49.0001.0102.5525.5001.00
 is-type level-2
 metric-style wide
!
```

#### Langkah 4: Script Verifikasi (`verify.sh`)
```bash
#!/bin/bash
set -e

echo "=== Memeriksa Tetangga OSPF pada CORE-R1 ==="
docker exec -it clab-igp-advanced-lab-core-r1 vtysh -c "show ip ospf neighbor"

echo "=== Memeriksa Database IS-IS pada CORE-R1 ==="
docker exec -it clab-igp-advanced-lab-core-r1 vtysh -c "show isis database detail"

echo "=== Memeriksa FIB Rute Aktif pada CORE-R2 ==="
docker exec -it clab-igp-advanced-lab-core-r2 vtysh -c "show ip route"

echo "=== Validasi Sukses: Seluruh Status Neighbor Konvergen ==="
```

---

### 13. Exercise

#### Level 1 (Easy)
1. Tentukan status dari router OSPF yang berada di dalam NSSA jika menerima LSA Type 7 dengan Flag `P=0`. Apakah rute tersebut akan ditranslasikan menjadi LSA Type 5 oleh ABR? Jelaskan mekanismenya!
2. Mengapa protokol IS-IS secara arsitektur tidak membutuhkan pembentukan *Router ID* berbasis IPv4 untuk melakukan kalkulasi SPF?

#### Level 2 (Medium)
1. Sebuah topologi IS-IS Level-1-2 memiliki dua router batas (L1/L2) yang terhubung ke backbone Level-2. Secara default, router Level-1 di dalam area akan mengirim trafik ke router L1/L2 terdekat berdasarkan `ATT-bit`. Analisis skenario di mana situasi ini menyebabkan *asymmetric routing* dan jelaskan bagaimana implementasi *Route Leaking* (Level-2 ke Level-1) via extended IP reachability TLV dapat menyelesaikan masalah tersebut.
2. Anda diminta mengonfigurasi OSPFv3 untuk mendukung dual-stack (IPv4 dan IPv6 AF). Jelaskan bagaimana OSPFv3 merepresentasikan link lokal dalam LSA dan bandingkan mekanismenya dengan format TLV multi-topology pada IS-IS.

#### Level 3 (Hard)
1. Rancang arsitektur konvergensi ultra-cepat (*Ultra-Fast Convergence*) pada jaringan transit spine-leaf data center yang mengalami kendala *micro-loops* saat link flap terjadi. Formulasikan kriteria evaluasi kondisi ketidaksamaan matematis untuk TI-LFA (Q-space dan P-space calculation), lalu buat diagram kalkulasi rute proteksi jika salah satu Core Link putus.

---

### 14. Challenge
**Studi Kasus Desain: Migrasi Tanpa Downtime Jaringan Telekomunikasi Nasional**

Sebuah operator seluler Tier-1 memiliki 1.200 router backbone yang menjalankan OSPFv2 flat Area 0 yang sudah mengalami degradasi performa: CPU router tertekan saat terjadi fiber cut, dan alokasi memori LSDB melampaui batas batas aman pada hardware lawas. Manajemen memutuskan untuk memigrasikan seluruh *underlay network* ke **IS-IS Level-2 Single Flat Area dengan Metric-Style Wide** sebagai fondasi integrasi Segment Routing (SR-MPLS).

**Ketentuan Tantangan:**
1. **Zero Blackhole & Zero Loop**: Selama proses migrasi yang diproyeksikan memakan waktu 3 minggu, kedua protokol routing (OSPF dan IS-IS) harus berjalan berdampingan (*Ships in the Night*).
2. **Deterministic Forwarding**: Seluruh router harus tetap memprioritaskan rute OSPF hingga verifikasi migrasi area selesai, kemudian serentak beralih ke IS-IS tanpa *traffic interruption*.
3. **Hardware Heterogen**: Backbone terdiri dari 60% router Cisco IOS-XR, 30% Juniper JunOS, dan 10% Nokia SR-OS.
4. **Tugas Anda**:
   - Susun matriks *Administrative Distance* / *Route Preference* bertahap untuk ketiga vendor tersebut selama masa migrasi.
   - Formulasikan strategi mitigasi jika terjadi divergensi keputusan forwarding antar-vendor akibat perbedaan default internal preference.
   - Buat skenario pengujian *rollback plan* terotomatisasi berbasis script validasi metrik state.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa fungsi utama dari LSA Type 4 pada OSPFv2?**
   - A. Menyediakan informasi prefix rute internal area.
   - B. Mengiklankan rute default ke Totally Stubby Area.
   - C. Mengumumkan lokasi alamat host ASBR ke router di luar area tempat ASBR berada.
   - D. Mentranslasikan LSA Type 7 menjadi Type 5.
   *Jawaban*: C. LSA Type 4 (ASBR Summary) di-generate oleh ABR untuk memberitahukan router di area lain cara mencapai ASBR yang menginjeksi rute eksternal.

2. **Berapa ukuran default metric maksimum untuk antarmuka IS-IS versi lama (Narrow Metric)?**
   - A. 255
   - B. 63
   - C. 1024
   - D. 16.777.215
   *Jawaban*: B. Narrow metrics menggunakan 6-bit per antarmuka, sehingga nilai metrik maksimum hanya 63.

3. **Bit apa yang diatur oleh router IS-IS Level-1-2 pada paket LSP-nya untuk mengindikasikan kepada router Level-1 bahwa ia terhubung ke backbone?**
   - A. Overload (OL) Bit
   - B. Partition Repair (P) Bit
   - C. Attached (ATT) Bit
   - D. Down (D) Bit
   *Jawaban*: C. ATT-bit dipasang oleh router L1/L2 dalam LSP Level-1 untuk memicu pembentukan rute default otomatis pada router Level-1 internal.

4. **Karakteristik utama dari OSPF Totally Stubby Area adalah:**
   - A. Menerima rute eksternal (Type 5) tetapi memblokir Summary LSA (Type 3).
   - B. Memblokir seluruh LSA Type 3, 4, dan 5, kecuali satu rute default LSA Type 3.
   - C. Mengizinkan redistribusi lokal menggunakan LSA Type 7.
   - D. Memerlukan Virtual Link untuk terhubung ke Area 0.
   *Jawaban*: B. Totally Stubby Area membersihkan tabel routing dari seluruh LSA Type 3, 4, dan 5 eksternal, hanya menyisakan sebuah LSA Type 3 default route dari ABR.

5. **Protokol BFD beroperasi pada layer apa untuk mendeteksi kegagalan link forwarding path?**
   - A. Data Link Layer (Layer 2)
   - B. Network Layer / Transport Layer (Encapsulated di UDP port 3784/3785)
   - C. Application Layer (Layer 7)
   - D. Physical Layer (Layer 1)
   *Jawaban*: B. Paket single-hop BFD dienkapsulasi menggunakan protokol UDP pada port 3784.

#### Intermediate (5 Soal)
6. **Pada redistribusi OSPF ke IS-IS, mengapa parameter `metric-style wide` mutlak diperlukan di lingkungan modern?**
   - A. Agar IS-IS dapat membaca nilai Router ID OSPF secara tepat.
   - B. Agar IS-IS mampu membawa metrik rute lebih dari 63 serta mendukung atribut traffic engineering / Segment Routing TLV.
   - C. Menghindari pembentukan Pseudo-node pada interface Ethernet.
   - D. Untuk menaikkan Administrative Distance IS-IS menjadi 115.
   *Jawaban*: B. Wide metrics memperbesar kapasitas field metrik menjadi 24-bit (dan 32-bit untuk total path metric), memungkinkan rekayasa metrik granular yang dibutuhkan oleh redistribusi skala besar.

7. **Ketika terjadi event link flap pada jaringan OSPF, mekanisme apa yang mencegah router dari eksekusi komputasi algoritma SPF secara berulang tanpa henti (*thrashing*)?**
   - A. Dead Interval Timers
   - B. SPF Throttling (timers throttle spf) dengan algoritma Exponential Backoff
   - C. LSA Retransmission Limit
   - D. BFD Dampening Mechanism
   *Jawaban*: B. `timers throttle spf` mengatur delay awal, delay penahanan inkremental (hold interval), dan batas delay maksimum untuk mengisolasi osilasi komputasi selama topologi tidak stabil.

8. **Apa perbedaan operasional mendasar antara *Designated Router* (DR) pada OSPF dan *Designated Intermediate System* (DIS) pada IS-IS?**
   - A. OSPF memiliki Backup DR (BDR), sedangkan IS-IS tidak memiliki Backup DIS (*preemption* bersifat langsung jika muncul prioritas lebih tinggi).
   - B. OSPF DR tidak dapat digantikan (*non-preemptive*), sedangkan IS-IS DIS tidak dapat digantikan (*preemptive*).
   - C. IS-IS DIS memancarkan paket Hello setiap 30 detik, sedangkan OSPF DR setiap 10 detik.
   - D. OSPF DR membentuk adjacency hanya ke BDR, sedangkan DIS membentuk adjacency ke semua node.
   *Jawaban*: A. IS-IS tidak mengenal konsep Backup DIS. Jika sebuah router baru aktif dengan prioritas antarmuka lebih tinggi, ia akan langsung mengambil alih peran DIS (*preemptive*).

9. **Kondisi apa yang memicu ABR OSPF bertindak sebagai NSSA Translator (Type-7 to Type-5)?**
   - A. Router dengan IP antarmuka terendah di Area 0.
   - B. Router NSSA ABR yang memiliki Router ID paling tinggi di antara ABR yang terhubung ke area tersebut.
   - C. Router yang pertama kali menerima LSA Type 7 dari ASBR.
   - D. Ditentukan secara acak menggunakan algoritma hash flow.
   *Jawaban*: B. Standar OSPF (RFC 3101) menetapkan bahwa jika terdapat lebih dari satu ABR di NSSA, ABR dengan Router ID tertinggi yang dipilih untuk mengeksekusi translasi LSA 7-ke-5.

10. **Bagaimana cara kerja OSPF Max-Metric Router LSA dalam meminimalisir packet loss saat pemeliharaan sistem (maintenance)?**
    - A. Memutuskan sesi BFD secara graceful untuk memaksa failover.
    - B. Mengiklankan metrik 65535 untuk semua link transit dalam Router LSA-nya, membuat algoritma SPF mengalihkan seluruh rute transit menjauhi router tersebut.
    - C. Mengirimkan sinyal ICMP Destination Unreachable kepada seluruh host pengirim.
    - D. Mematikan interface fisik setelah waktu tunda 100 detik.
    *Jawaban*: B. Dengan menyetel metrik ke 65535 ($2^{16} - 1$), router tetap dapat diakses untuk tujuannya sendiri (stub reachability), namun trafik transit akan diarahkan ke jalur alternatif oleh seluruh tetangganya.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1: Blackhole Trafik Pasca-Maintenance OSPF-to-BGP Sync**
    - *Kasus*: Tim Network Engineer menyelesaikan update firmware pada Core-01. Segera setelah OSPF aktif kembali, router tersebut mulai menerima jutaan paket per detik, namun sebagian besar paket ter-drop (*blackholed*) selama kurang lebih 90 detik sebelum aliran kembali normal. Mengapa ini terjadi dan bagaimana solusinya?
    - *Solusi & Analisis*: OSPF konvergen dalam hitungan detik dan langsung mempromosikan rute transit melalui Core-01, padahal sesi iBGP internal belum selesai men-download jutaan rute Full Internet Routing Table ke FIB/TCAM. Solusinya: Implementasikan `max-metric router-lsa on-startup wait-for-bgp <timer>`. Perintah ini menahan metrik OSPF pada nilai maksimal hingga BGP selesai konvergen secara penuh.

12. **Skenario Kasus 2: Micro-Loops Selama Fase Rekonvergensi IGP Backbone**
    - *Kasus*: Ketika Core Link $A-B$ putus mendadak, terjadi lonjakan *packet drop* selama 250ms meskipun BFD mendeteksi kegagalan dalam 30ms. Analisis packet capture menunjukkan paket melompat bolak-balik antara Router $A$ dan Router $C$ sebelum akhirnya stabil melewati Router $D$. Masalah apa yang sedang terjadi?
    - *Solusi & Analisis*: Ini adalah fenomena klasik **IGP Micro-Looping**. Router $A$ mendeteksi link putus dan langsung mengalihkan rute ke Router $C$. Namun, Router $C$ belum selesai menjalankan kalkulasi SPF lokalnya, sehingga FIB-nya masih menganggap jalur terbaik menuju destinasi adalah melalui Router $A$. Router $C$ memantulkan kembali paket tersebut ke $A$, menimbulkan loop hingga SPF di seluruh node selesai. Solusinya: Aktifkan **Topology-Independent LFA (TI-LFA)** dengan *segment routing path binding* atau implementasikan *Micro-loop Avoidance Timers* (menunda instalasi FIB baru sampai tetangga dipastikan selesai konvergen).

13. **Skenario Kasus 3: Kegagalan Pembentukan Adjasensi IS-IS pada Link Antarmuka Jumbo MTU**
    - *Kasus*: Dua router core Cisco ASR dan Arista 7280 dihubungkan via 100GbE link. Interface dikonfigurasi MTU 9216. Adjasensi IS-IS Level-2 gagal terbentuk (status macet di `INIT`). Ketika perintah `isis hello-padding disable` diaktifkan di sisi Cisco, adjasensi seketika berubah menjadi `UP`, namun trafik paket data berukuran 8000 byte mengalami packet loss 100%. Apa kesimpulan audit teknis Anda?
    - *Solusi & Analisis*: Kegagalan pembentukan awal terjadi karena paket IIH (IS-IS Hello) secara default di-*pad* (diberi bantalan) hingga ukuran penuh LSP MTU. Kegagalan ini mengindikasikan bahwa jalur fisik/underlying L2 switch/transport carrier di antara kedua router memiliki batasan MTU yang lebih kecil dari yang dikonfigurasi (misal: transport membatasi MTU pada 1500 byte). Menonaktifkan padding hanya menyamarkan masalah (*bypassing hello check*), akibatnya paket data besar yang lewat tetap ter-drop (*silent drop*). Solusi: Lakukan uji *path MTU discovery* (sweep ping tanpa fragmentasi) dan sesuaikan MTU interface fisik serta LSP-MTU IS-IS agar sesuai dengan kapasitas nyata transport layer.

---

### 16. Summary

Mengoperasikan dynamic link-state routing protocols (OSPF dan IS-IS) pada skala Enterprise Core dan Provider Backbone membutuhkan pergeseran paradigma dari *sekadar pembentukan tetangga* menuju **rekayasa kestabilan data path dan konvergensi deterministik**:

1. **Modularitas Arsitektur**: IS-IS menawarkan fleksibilitas yang lebih unggul dibandingkan OSPFv2 berkat struktur data berbasis TLV dan pemisahan topologi transit dari prefix data, menjadikannya standar de-facto untuk Segment Routing dan backbone skala masif.
2. **Hierarki Mengisolasi Kerusakan**: Penggunaan Stub, NSSA, dan segmentasi Level-1/Level-2 bukan hanya untuk menghemat memori, melainkan membatasi propagasi komputasi SPF saat terjadi kegagalan link di tepi jaringan (*blast radius reduction*).
3. **Sub-50ms Resilience**: Kombinasi **BFD** (deteksi cepat), **TI-LFA** (perbaikan data plane instan tanpa loop), serta **SPF Throttling** (stabilisasi control plane) wajib diterapkan untuk menjamin kontinuitas trafik kelas *carrier-grade*.
4. **Disiplin Boundary Control**: Redistribusi rute antar-protokol tanpa *tagging deterministic policy* merupakan sumber utama bencana jaringan (*routing loop* & *sub-optimal paths*). Filter berbasis tag pada batas perimeter menjamin integritas alur kendali rute secara permanen.