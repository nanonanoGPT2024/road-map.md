# Modul 01: Exterior Gateway Protocol: BGP & Inter-Domain Routing

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menganalisis dan mengonfigurasi interkoneksi Autonomous System (AS) menggunakan Border Gateway Protocol (BGP-4) baik dalam mode eBGP (External) maupun iBGP (Internal).
- Menguasai hierarki manipulasi path vector melalui BGP Path Attributes: *Weight*, *Local Preference*, *AS-Path*, *Origin Code*, *Multi-Exit Discriminator (MED)*, serta *BGP Communities* (Standard & Large).
- Merekonstruksi dan memprediksi hasil dari *BGP Best Path Selection Algorithm* secara deterministik pada skenario multi-homing.
- Merancang dan mengimplementasikan arsitektur *Route Reflector* (RR) untuk mengeliminasi kebutuhan *iBGP full-mesh* tanpa memicu routing loops.
- Mengamankan inter-domain routing menggunakan *Resource Public Key Infrastructure* (RPKI) dan memvalidasi *Route Origin Validation* (ROV) guna mencegah insiden *BGP Route Hijacking* dan *Route Leaks*.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Protokol Interior Gateway Protocol (IGP) berbasis link-state (OSPF atau IS-IS) secara mendalam, khususnya konsep shortest path calculation dan redistribution.
- Model TCP/IP Layer 4: Cara kerja TCP three-way handshake, acknowledgment, dan flow control (BGP beroperasi di atas TCP port 179).
- Konsep IP Subnetting, VLSM, dan Classless Inter-Domain Routing (CIDR) supernetting/prefix aggregation.
- Dasar-dasar Public Key Infrastructure (PKI): Sertifikat X.509, cryptographic signatures, dan trust chain.

---

## 3. Concept
Border Gateway Protocol (BGP-4, didefinisikan dalam RFC 4271) adalah protokol routing standar de facto yang menggerakkan internet global. Berbeda dengan IGP yang memprioritaskan konvergensi cepat dan metrik biaya terkecil dalam satu domain administrasi, BGP adalah protokol *Path-Vector* yang dirancang untuk menegakkan kebijakan perutean (*routing policy*), kontrol skala besar, stabilitas, dan keamanan antar-domain administrasi independen yang disebut Autonomous System (AS).

---

## 4. Why
Protokol IGP (seperti OSPF atau IS-IS) mengharuskan setiap router memahami topologi jaringan secara keseluruhan. Pendekatan ini memiliki batasan:
- **Skalabilitas:** Database link-state global akan meledakkan memori router jika harus menampung ratusan ribu rute internet (Global Internet Routing Table saat ini melampaui 950.000+ rute IPv4 dan 200.000+ rute IPv6).
- **Ketiadaan Kontrol Kebijakan Bisnis:** IGP hanya mengenal *shortest path* berdasarkan metrik teknis (bandwidth/delay). Dalam skala global, lalu lintas data diatur oleh kontrak finansial, kesepakatan *transit*, *peering* bilateral, dan regulasi yurisdiksi geopolitik.
- **Isolasi Domain Kegagalan (*Failure Domain Isolation*):** Flapping interface di sebuah ISP di Tokyo tidak boleh memicu kalkulasi SPF ulang di ISP di London. BGP mengisolasi dinamika topologi internal melalui abstraksi AS-Path dan mekanisme dampening.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Autonomous System Numbers (ASN)
Autonomous System (AS) adalah kumpulan jaringan IP yang berada di bawah satu kendali administrasi teknis dengan kebijakan routing tunggal dan terdefinisi jelas terhadap internet.
- **2-Byte (16-bit) ASN:** Rentang 1 – 65535.
  - Public ASN: 1 – 64495
  - Documentation (RFC 5398): 64496 – 64511
  - Private ASN (RFC 6996): 64512 – 65534
  - Reserved: 0 dan 65535
- **4-Byte (32-bit) ASN (RFC 6793):** Rentang 1 – 4294967295.
  - Diperkenalkan karena penipisan 2-byte ASN. Ditulis dalam format *asplain* (contoh: `139782`) atau *asdot* (contoh: `2.8454`).
  - Private ASN: 4200000000 – 4294967294.
  - Kompatibilitas mundur menggunakan penanda transisional `AS_TRANS` (ASN 23456).

### 5.2 eBGP vs iBGP Architecture
BGP beroperasi dalam dua mode fundamental berdasarkan relasi administratif ASN:

| Parameter | External BGP (eBGP) | Internal BGP (iBGP) |
| :--- | :--- | :--- |
| **Relasi ASN** | Antara AS yang berbeda ($AS_A \neq AS_B$) | Dalam AS yang sama ($AS_A == AS_B$) |
| **Default IP TTL** | TTL = 1 (harus direct-connected, kecuali `ebgp-multihop`) | TTL = 64 (dapat melintasi beberapa hop IGP) |
| **Next-Hop Processing** | IP interface lokal pengirim otomatis dijadikan `Next-Hop` | Menjaga `Next-Hop` eBGP asli (*default* tidak diubah, kecuali diatur `next-hop-self`) |
| **Loop Prevention** | **AS-Path Loop Detection**: Tolak prefix jika ASN lokal ada di atribut `AS_PATH` | **iBGP Split Horizon**: Rute yang dipelajari dari satu peer iBGP *tidak boleh* diiklankan ke peer iBGP lain |
| **Topologi Persyaratan** | Point-to-point / direct peering | Full Mesh secara logis, atau menggunakan Route Reflector / Confederation |

```
    +------------------------------------+
    |         Autonomous System 65001    |
    |                                    |
    |   [Router A] <--(iBGP)--> [Router B] |
    |      (PE1)                   (PE2) |
    +--------|-----------------------|---+
             | (eBGP)                | (eBGP)
             v                       v
      +-------------+         +-------------+
      | AS 65002    |         | AS 65003    |
      | Transit ISP |         | IXP Peering |
      +-------------+         +-------------+
```

### 5.3 BGP Path Attributes (PA)
BGP tidak menggunakan metrik tunggal. Jalur dievaluasi berdasarkan urutan atribut (RFC 4271):
1. **Well-Known Mandatory:** Harus dikenali oleh semua implementasi BGP dan wajib disertakan dalam setiap pesan `UPDATE`.
   - `ORIGIN`: Sumber informasi rute (`IGP` [0], `EGP` [1], `INCOMPLETE` [2]).
   - `AS_PATH`: Urutan ASN yang dilintasi oleh rute.
   - `NEXT_HOP`: Alamat IP hop berikutnya menuju destinasi rute.
2. **Well-Known Discretionary:** Harus dikenali semua router, namun opsional ada di `UPDATE`.
   - `LOCAL_PREF`: Menentukan jalur keluar (*egress policy*) dalam AS lokal. Nilai tertinggi menang. Ditransmisikan hanya di iBGP.
   - `ATOMIC_AGGREGATE`: Memberi tahu bahwa prefix telah di-agregasi dan kehilangan path detail.
3. **Optional Transitive:** Router boleh tidak mengenali, tetapi wajib diteruskan ke peer lain.
   - `COMMUNITY`: Nilai penanda numerik untuk manajemen kebijakan rute.
   - `AGGREGATOR`: ASN dan IP dari router yang melakukan agregasi.
4. **Optional Non-Transitive:** Router boleh tidak mengenali, dan jika tidak dikenal atau dikonfigurasi demikian, atribut dibuang (tidak diteruskan ke peer lain).
   - `MED (Multi-Exit Discriminator)`: Menyarankan AS eksternal jalur mana yang harus dipilih untuk masuk (*ingress policy*) ke dalam AS lokal. Nilai terendah menang.

### 5.4 Algoritma BGP Best Path Selection (Urutan Eksekusi Deterministik)
BGP mengevaluasi seluruh rute yang valid untuk prefix yang sama secara terurut. Rute pertama yang gagal dalam komparasi langsung tereliminasi:
1. **Weight** (Tertinggi menang; khusus Cisco/ekstensi vendor, skop router lokal).
2. **Local Preference** (Tertinggi menang; default 100, skop AS lokal).
3. **Locally Originated** (Rute lokal hasil deklarasi command `network` atau `aggregate-address` lebih diutamakan daripada rute yang diimpor dari peer).
4. **AS_PATH Length** (Jalur dengan jumlah hop ASN terpendek menang; `AS_SET` dihitung 1, prepending memperpanjang jalur).
5. **Origin Code** (`IGP` < `EGP` < `INCOMPLETE`).
6. **Multi-Exit Discriminator (MED)** (Terendah menang; default hanya dibandingkan jika AS tetangganya sama, kecuali `bgp always-compare-med` aktif).
7. **Neighbor Type** (Rute yang dipelajari dari **eBGP** lebih dipilih dibanding **iBGP**).
8. **Lowest IGP Metric to Next-Hop** (Biaya internal link-state terendah untuk mencapai alamat IP `NEXT_HOP`).
9. **BGP Multipath (Optional)** (Jika ECMP aktif, install jalur seimbang ke routing table, jika tidak lanjut ke tie-breaker berikutnya).
10. **Oldest Path** (Rute eBGP yang paling stabil/paling lama aktif dipilih untuk meminimalkan route flap).
11. **Lowest Router ID** (BGP Neighbor RID numerik terendah).
12. **Lowest Neighbor IP Address** (Alamat IP peer terendah).

### 5.5 Route Reflectors (RR)
Untuk mengatasi masalah skalabilitas $N(N-1)/2$ koneksi pada iBGP Full-Mesh, Route Reflector (RFC 4456) melonggarkan aturan *iBGP Split Horizon*:
- **Aturan Propagasi Rute RR:**
  - Rute dari **Client** dipantulkan ke **Client** lain dan **Non-Client**.
  - Rute dari **Non-Client** hanya dipantulkan ke **Client**.
  - Rute dari **eBGP** diteruskan ke **Client** dan **Non-Client**.
- **Loop Prevention Mechanisms:**
  - `ORIGINATOR_ID`: Berisi Router ID dari pembuat rute pertama kali di AS tersebut. Jika pembuat menerima kembali rute dengan ID miliknya, rute diabaikan.
  - `CLUSTER_LIST`: Berisi daftar `Cluster ID` yang dilalui rute. Jika RR melihat `Cluster ID` miliknya dalam daftar, loop terdeteksi dan rute dibuang.

### 5.6 BGP Communities
Atribut `COMMUNITY` (RFC 1997) adalah label 32-bit yang ditautkan ke prefix rute untuk menandai tindakan routing:
- **Format Tradisional:** `AA:NN` (16-bit ASN : 16-bit tag value).
- **Well-Known Communities:**
  - `NO_EXPORT` (`0xFFFFFF01`): Jangan iklankan ke luar AS konfederasi atau peer eBGP.
  - `NO_ADVERTISE` (`0xFFFFFF02`): Jangan iklankan ke peer manapun (baik iBGP maupun eBGP).
  - `INTERNET` (`0x00000000`): Iklankan ke seluruh jaringan internet.
- **Large Communities (RFC 8092):** Format 12-byte `Global-Administrator:Data-1:Data-2` (contoh: `65001:100:10`), dirancang khusus untuk mendukung 4-Byte ASN secara natif.

### 5.7 RPKI Route Origin Validation (ROV)
Resource Public Key Infrastructure (RPKI) adalah kerangka kerja kriptografi publik (RFC 6480) yang mengotentikasi hak kepemilikan prefix internet:
- **Route Origin Authorization (ROA):** Objek bertanda tangan kriptografis dari Regional Internet Registry (RIR seperti APNIC, RIPE, ARIN) yang memetakan prefix IP ke ASN terotorisasi beserta panjang mask maksimum (`MaxLength`).
- **Status Evaluasi ROV:**
  - `Valid`: Prefix dan origin ASN cocok dengan ROA, serta prefix length $\le$ `MaxLength`.
  - `Invalid`: Terdeteksi pembajakan rute (Origin ASN salah, atau prefix length melebihi `MaxLength`). **Harus dibuang (dropped) pada eBGP edge!**
  - `NotFound` (Unknown): Tidak ada ROA terdaftar untuk prefix tersebut. Rute tetap diproses dengan preferensi standar.

---

## 6. How
Implementasi dan tuning BGP dilakukan dengan metodologi berikut:
1. **Perencanaan Pengalamatan dan ASN:** Alokasikan ASN public dari RIR atau private ASN (rentang 64512-65534 / 4200000000+).
2. **Underlay IGP Konfigurasi:** Bangun routing IGP (OSPF/IS-IS) di dalam AS untuk menjamin reachability antar loopback address router BGP.
3. **Establisment iBGP Peering:** Bangun iBGP antar-loopback router internal menggunakan `update-source Loopback0` dan pastikan `next-hop-self` aktif di ingress edge router.
4. **Establishment eBGP Peering:** Bangun eBGP dengan operator transit/IXP menggunakan IP point-to-point interface.
5. **Penerapan RPKI ROV:** Integrasikan BGP router dengan RPKI Validator cache (RTR protocol) seperti Routinator, Oktuda, atau StayRTR.
6. **Filtering Kebijakan:** Gunakan Route-Map/Policy-Statement, Prefix-List, dan AS-Path ACL untuk menegakkan kontrol perutean masuk (inbound) dan keluar (outbound).

---

## 7. Analogy
Bayangkan sistem pengiriman pos internasional:
- **IGP** adalah kurir lokal dalam satu kota. Dia tahu persis setiap gang, nomor rumah, dan jalan tikus tercepat (SPF calculation).
- **BGP** adalah konsorsium pelabuhan kargo dan bandara internasional. Mereka tidak memedulikan jalan tikus di dalam kota tujuan. Mereka hanya membaca daftar paspor dan stempel negara transit pada dokumen kargo (**AS-Path**).
- **AS-Path Prepending** seperti menempelkan perangko cadangan negara sendiri berulang-ulang agar bea cukai menganggap paket tersebut menempuh birokrasi yang panjang, sehingga kapal memilih bersandar di pelabuhan lain yang stempelnya lebih sedikit.
- **RPKI** adalah sertifikat digital terverifikasi dari kementerian luar negeri yang membuktikan bahwa kargo tersebut benar-benar milik perusahaan yang sah, bukan paket gelap selundupan (mencegah BGP hijacking).

---

## 8. Diagram (ASCII)

### Topology: Multi-Homed Edge Network with Route Reflector & RPKI
```
               +-------------------------------------------+
               |              Internet Core                |
               +-------------------------------------------+
                     |                               |
           eBGP Peer |                               | eBGP Peer
        AS 64500 (ISP-A)                     AS 64501 (ISP-B)
                     |                               |
                     v                               v
             +---------------+               +---------------+
             | Edge Router 1 |               | Edge Router 2 |
             |    (eBGP/PE)  |               |    (eBGP/PE)  |
             +---------------+               +---------------+
                     \                               /
                      \                             /
              iBGP Peering                   iBGP Peering
             (next-hop-self)                (next-hop-self)
                        \                         /
                         v                       v
                     +-------------------------------+
                     |     Route Reflector (RR)      |
                     |           (AS 65001)          |
                     |   RPKI Client (RTR Protocol)  |
                     +-------------------------------+
                                     ^
                                     | RTR (TCP 8282)
                     +-------------------------------+
                     |     RPKI Cache Validator      |
                     |        (e.g., Routinator)     |
                     +-------------------------------+
```

### RPKI Validation State Machine
```
   [BGP Route Announced via eBGP]
                 |
                 v
   +-----------------------------+
   | Query Local RPKI Cache Table|
   +-----------------------------+
                 |
         +-------+-------+
         |               |
     [Found]        [Not Found] ---> Status: NOT_FOUND (Allowed)
         |
         v
   Match Origin ASN & MaxLength?
         |
    +----+----+
    |         |
  [Yes]      [No]
    |         |
    v         v
  VALID    INVALID (Drop Announcement / Reject)
(Allowed)
```

---

## 9. Simple Example
Deklarasi eBGP peering minimalis antara Router edge lokal (AS 65001) dan ISP upstream (AS 64500) menggunakan sintaks industri modern (FRRouting / Cisco-like syntax).

```text
! Konfigurasi Router Edge AS 65001
router bgp 65001
 bgp router-id 192.0.2.1
 neighbor 203.0.113.1 remote-as 64500
 neighbor 203.0.113.1 description PEERING_TO_ISP_A
 !
 address-family ipv4 unicast
  network 198.51.100.0/24
  neighbor 203.0.113.1 activate
  neighbor 203.0.113.1 send-community extended
 exit-address-family
```

---

## 10. Practical Example (Konfigurasi Produksi Multi-Vendor & Modern Edge)

### Skenario:
Router Edge Arista EOS / FRRouting dengan Dual Upstream (ISP-A AS 64500 & ISP-B AS 64501), implementasi Route Reflector internal, RPKI validation via RTR protocol, dan modifikasi path selection via BGP Communities dan Local Preference.

```text
! ========================================================
! FRRouting / Cisco IOS-XR Style Enterprise Edge Router
! Node: Edge-R1 (ASN: 65100, Router-ID: 10.100.0.1)
! ========================================================

! 1. Definisi Route-map dan Filter Kebijakan
ip prefix-list OWN-PREFIXES seq 10 permit 198.51.100.0/22 le 24
ip prefix-list DEFAULT-ROUTE seq 10 permit 0.0.0.0/0

bgp community-list standard COMM-PREFER-ISP-A permit 65100:100
bgp community-list standard COMM-BACKUP-ISP-B permit 65100:200

route-map RM-IN-ISP-A permit 10
 match rpki invalid
 set local-preference 10
 ! Praktik zero-trust: Drop invalid rute langsung atau assign preference terendah
 ! Di level enterprise modern: directly drop invalid
route-map RM-IN-ISP-A deny 20
 match rpki invalid
!
route-map RM-IN-ISP-A permit 30
 match rpki valid
 set local-preference 200
 set community 65100:100 additive
!
route-map RM-IN-ISP-A permit 40
 match rpki notfound
 set local-preference 100
!
route-map RM-IN-ISP-B permit 10
 match rpki invalid
!
route-map RM-IN-ISP-B deny 10
 match rpki invalid
!
route-map RM-IN-ISP-B permit 20
 match rpki valid
 set local-preference 150
 set community 65100:200 additive
!
route-map RM-IN-ISP-B permit 30
 match rpki notfound
 set local-preference 90

! Manipulasi Outbound: Prepending untuk cadangan di ISP-B
route-map RM-OUT-ISP-A permit 10
 match ip address prefix-list OWN-PREFIXES
!
route-map RM-OUT-ISP-B permit 10
 match ip address prefix-list OWN-PREFIXES
 set as-path prepend 65100 65100

! 2. Konfigurasi RPKI Server (RTR Client)
rpki
 rpki cache 10.100.254.50 8282 preference 1
 rpki initial-synchronization
exit

! 3. Instansiasi Daemon BGP
router bgp 65100
 bgp router-id 10.100.0.1
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 
 ! Neighbors iBGP (Route Reflector Client)
 neighbor 10.100.0.2 remote-as 65100
 neighbor 10.100.0.2 update-source Loopback0
 neighbor 10.100.0.2 description CORE-RR-CLIENT
 
 ! Neighbors eBGP Upstream
 neighbor 203.0.113.1 remote-as 64500
 neighbor 203.0.113.1 description TRANSIT-ISP-A
 
 neighbor 198.51.100.254 remote-as 64501
 neighbor 198.51.100.254 description TRANSIT-ISP-B

 address-family ipv4 unicast
  ! Iklankan subnet sendiri
  network 198.51.100.0/22
  
  ! Aktivasi iBGP Internal
  neighbor 10.100.0.2 activate
  neighbor 10.100.0.2 next-hop-self
  neighbor 10.100.0.2 send-community both
  
  ! Aktivasi Upstream ISP-A (Primary)
  neighbor 203.0.113.1 activate
  neighbor 203.0.113.1 route-map RM-IN-ISP-A in
  neighbor 203.0.113.1 route-map RM-OUT-ISP-A out
  neighbor 203.0.113.1 send-community
  
  ! Aktivasi Upstream ISP-B (Secondary Backup via Prepend)
  neighbor 198.51.100.254 activate
  neighbor 198.51.100.254 route-map RM-IN-ISP-B in
  neighbor 198.51.100.254 route-map RM-OUT-ISP-B out
  neighbor 198.51.100.254 send-community
 exit-address-family
!
```

---

## 11. Real World Example
Pada kasus industri berskala hyperscale (misalnya interkoneksi hybrid enterprise menuju AWS Direct Connect dan Google Cloud Interconnect):
- Enterprise memiliki ASN publik `139782`.
- Jalur 1: AWS Direct Connect via Equinix Singapore (Latency: 4ms).
- Jalur 2: Google Cloud via Megaport Singapore (Latency: 5ms).
- **Permasalahan:** Terjadi *asymmetric routing* parah di mana egress traffic melewati AWS, tetapi return traffic masuk melalui Google Cloud, memicu firewall stateful memutus koneksi (TCP out-of-order drop).
- **Solusi:**
  1. Implementasi **BGP Communities RFC 1997**: Menandai prefix egress dengan community tag spesifik provider untuk mengatur local preference upstream.
  2. Implementasi **AS-Path Prepending**: Mengirimkan 3x ASN prepend ke jalur GCP untuk rute spesifik agar inbound traffic global konsisten masuk melalui interface AWS Direct Connect.
  3. Konfigurasi **RPKI ROV**: Menolak prefix palsu saat ISP upstream mengalami *BGP route leak* dari tier-3 provider.

---

## 12. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian / Biaya Komputasi |
| :--- | :--- | :--- |
| **iBGP Full Mesh** | Topologi logis sederhana, tidak ada modifikasi header loop prevention | Kompleksitas koneksi $O(N^2)$. Sangat membebani CPU dan memori saat router > 20 node. |
| **Route Reflector** | Skalabilitas tinggi ($O(N)$), manajemen konfigurasi tersentralisasi | Potensi suboptimal routing (meddling next-hop) dan risiko *routing loop* jika manipulasi `Originator-ID`/`Cluster-List` salah. |
| **AS-Path Prepending** | Mengontrol arus traffic masuk (*inbound traffic engineering*) secara universal tanpa kesepakatan BGP community | Kurang deterministik; ISP upstream dapat menimpa (*override*) kebijakan menggunakan Local Preference lokal mereka. |
| **Full Internet Table** | Seleksi egress rute paling presisi dan optimal langsung ke destination AS terdekat | Membutuhkan RAM minimal 2-4 GB per instance per peer (1M+ routes), konvergensi lambat saat reload session. |
| **Default Route Only (0.0.0.0/0)** | Konsumsi memori sangat minim, konvergensi instan | Kehilangan visibilitas granular; egress traffic dapat mengambil rute internasional yang suboptimal. |

---

## 13. When To Use
- Saat enterprise terkoneksi ke lebih dari satu ISP (Multi-homing) untuk redundansi dan performa failover otomatis.
- Saat berpartisipasi dalam Internet Exchange Point (IXP) bilateral atau multilateral peering publik.
- Arsitektur Data Center modern berbasis Underlay-Overlay (BGP EVPN VXLAN Leaf-Spine Architecture).
- Jaringan Tier-1, Tier-2 Telco, dan Content Delivery Network (CDN) global.

---

## 14. When NOT To Use
- **Single-homed Enterprise:** Kantor cabang yang hanya memiliki satu koneksi uplink statis ke ISP tunggal. Cukup gunakan **Static Route** atau **Default Route**. Menjalankan BGP di sini menambah overhead CPU dan risiko human error tanpa manfaat teknis.
- **Small-to-Medium Campus Network Internal:** Distribusi traffic antar gedung kampus lebih efisien, responsif, dan konvergen cepat menggunakan IGP link-state murni (OSPF/IS-IS).

---

## 15. Common Mistakes
1. **Lupa Perintah `next-hop-self` pada iBGP:**
   Edge router menerima rute dari eBGP dan meneruskannya ke iBGP peer tanpa mengubah next-hop. Core router internal tidak memiliki rute IGP menuju IP eksternal eBGP next-hop tersebut, menyebabkan paket di-drop di core (BGP blackhole).
2. **Tidak Melakukan Route Filtering Outbound (Route Leak):**
   Meneruskan rute yang dipelajari dari ISP-A ke ISP-B. Akibatnya, jaringan enterprise Anda mendadak menjadi jalur transit publik gratis antara dua provider besar, menenggelamkan bandwidth internal hingga link lumpuh total.
3. **Mengabaikan Konfigurasi RPKI Invalid Drop:**
   Menerapkan RPKI validator namun tidak menambahkan filter drop pada route-map untuk status `invalid`, sehingga BGP hijacking tetap terjadi.
4. **Salah Mengartikan Lingkup Atribut:**
   Mencoba mengirimkan atribut `Local Preference` atau `Weight` ke router di luar AS (eBGP). Kedua atribut ini tidak akan dikirimkan oleh router ke peer eBGP (Local Preference terisolasi di dalam AS; Weight hanya berada dalam memori lokal satu router).

---

## 16. Best Practices
- **Terapkan BCP 38 / MANRS (Mutually Agreed Norms for Routing Security):** Validasi prefix dan origin ASN, jangan pernah mengiklankan prefix bogon/private (`RFC 1918`, `RFC 6598`) ke publik.
- **Filter Ketat Menggunakan Prefix-List dan AS-Path:** Pasang inbound dan outbound filter eksplisit pada setiap sesi eBGP. Terapkan prinsip *default-deny*.
- **Enforce RPKI ROV Secara Ketat:** Konfigurasi router untuk mendrop semua status `Invalid` secara langsung tanpa exception.
- **Batasi Maksimum Prefix (`maximum-prefix`):** Pasang `neighbor <ip> maximum-prefix <limit> <threshold-warning> restart <minutes>` untuk mencegah kehabisan memori router jika upstream mengalami route leak masif.
- **Amankan Kontrol Plane:** Pasang BGP TTL Security Mechanism (BTSM / RFC 5082) dan otentikasi TCP-AO (TCP Authentication Option) atau MD5 signature.

---

## 17. Troubleshooting

### Command Dasar Validasi BGP:
- `show ip bgp summary`: Memeriksa status session BGP (Pastikan state adalah angka prefix yang diterima, bukan teks seperti `Active` atau `Idle` yang mengindikasikan koneksi TCP gagal).
- `show ip bgp <prefix>/<maskLength>`: Menampilkan detail atribut seluruh jalur kandidat rute dan melihat tanda path terpilih (`*>`).
- `show ip bgp neighbors <ip> advertised-routes`: Memverifikasi prefix apa yang dikirim router lokal ke tetangga.
- `show ip bgp neighbors <ip> routes`: Memverifikasi rute yang diterima setelah proses inbound policy filter.
- `show ip bgp rpki table`: Menampilkan basis data validasi ROA dari validator.

### Algoritma Diagnosa Masalah:
```
           +-----------------------------+
           | BGP State BUKAN Established |
           +-----------------------------+
                          |
                          v
           TCP Port 179 Terbuka & Reached?
                     /          \
                (Tidak)         (Ya)
                  /                \
        Cek Firewall/ACL,     Cek ASN Mismatch,
        Routing IGP Underlay, MD5 Secret Key,
        atau eBGP Multihop    BGP Identifier Clash
```

---

## 18. Exercise
1. Sebuah router menerima 2 jalur rute untuk prefix `103.20.10.0/24`:
   - Path A: Local_Pref: 100, AS-Path: `64500 64501` (length 2), Origin: `IGP`, MED: 50.
   - Path B: Local_Pref: 100, AS-Path: `64502` (length 1), Origin: `Incomplete`, MED: 100.
   Jalur mana yang dipilih sebagai *Best Path*? Jelaskan langkah evaluasi algoritmanya!
2. Mengapa protokol iBGP membutuhkan topologi *Full-Mesh* secara logis, dan bagaimana *Route Reflector* mematahkan limitasi tersebut tanpa menciptakan loop?
3. Sebuah prefix `198.51.100.0/24` terdaftar di RPKI ROA dengan:
   - `Authorized ASN: 65001`
   - `MaxLength: 24`
   Router Anda menerima iklan rute `198.51.100.0/25` dari ASN `65001`. Tentukan status validasi RPKI-nya (`Valid`, `Invalid`, atau `NotFound`) beserta justifikasi teknisnya!

---

## 19. Challenge
Rancang arsitektur peering multi-homed BGP dengan dua upstream provider transit (ISP-Alpha dan ISP-Bravo). Buat aturan konfigurasi route-map di mana:
1. Seluruh outgoing traffic secara default memilih ISP-Alpha.
2. Jika ISP-Alpha down, seluruh outbound beralih instan ke ISP-Bravo.
3. Seluruh incoming traffic internet dipaksa masuk via ISP-Alpha dengan cara melakukan AS-Path Prepending sebanyak 3 kali lipat pada pengumuman prefix ke ISP-Bravo.
4. Rute RPKI berstatus `Invalid` harus dibuang langsung tanpa dialokasikan ke tabel BGP.

---

## 20. Summary
- BGP adalah perekat inter-domain internet global berbasis protokol path-vector yang mengedepankan penegakan kebijakan (*policy enforcement*), bukan sekadar metrik kecepatan teknis.
- eBGP mencegah loop menggunakan pemeriksaan `AS_PATH`, sedangkan iBGP menggunakan aturan `Split Horizon` yang dapat dioptimalkan skalabilitasnya menggunakan `Route Reflector`.
- Algoritma seleksi BGP bersifat deterministik dengan hierarki kunci: **Weight $\to$ Local Preference $\to$ Locally Originated $\to$ AS-Path Length $\to$ Origin $\to$ MED $\to$ eBGP vs iBGP $\to$ IGP Metric $\to$ Router-ID**.
- RPKI Route Origin Validation (ROV) memberikan landasan integritas inter-domain routing dengan memvalidasi kepemilikan origin ASN secara kriptografis guna mengeliminasi ancaman route hijacking global.

---