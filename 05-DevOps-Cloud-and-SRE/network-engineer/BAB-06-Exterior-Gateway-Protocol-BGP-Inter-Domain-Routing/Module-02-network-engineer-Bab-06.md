# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi BGP

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** arsitektur internal BGP engine: struktur *Routing Information Base* (Adj-RIB-In, Loc-RIB, Adj-RIB-Out), *BGP Finite State Machine* (FSM), serta 13 langkah deterministik *Path Selection Algorithm*.
- **Merancang** topologi *Interior BGP* (iBGP) skala enterprise menggunakan pola *Route Reflector* (RR) hierarki ganda dan *BGP Confederation* untuk mengeliminasi keterbatasan *full-mesh* $O(N^2)$.
- **Mengimplementasikan** manipulasi atribut BGP tingkat lanjut (*Local Preference*, *AS-Path Prepending*, *Multi-Exit Discriminator* [MED], *BGP Communities* standar, *extended*, dan *large* RFC 8092) guna merealisasikan rekayasa lalu lintas (*traffic engineering*) deterministik *inbound* dan *outbound*.
- **Mengamankan** infrastruktur inter-domain routing melalui *Resource Public Key Infrastructure* (RPKI) *Route Origin Validation* (ROV), *BGP Prefix-Limit*, *BGP Neighbor Authentication* (TCP-AO/MD5), dan *Route Leaking Prevention* (RFC 9234).
- **Mendiagnosis dan memitigasi** anomali jaringan produksi skala global seperti *blackholing*, *route flapping*, *sub-optimal routing*, dan kegagalan konvergensi menggunakan integrasi BFD (*Bidirectional Forwarding Detection*) serta BGP PIC (*Prefix-Independent Convergence*).

---

## 2. Prerequisite

Peserta wajib menguasai:
- Pengetahuan fundamental BGP (Module 01): pemahaman dasar eBGP vs. iBGP, Autonomous System Numbers (ASN 2-byte dan 4-byte), serta pertukaran prefix sederhana.
- Protokol IGP (*Interior Gateway Protocol*): OSPFv2/OSPFv3 atau IS-IS (pemahaman LSA/LSP, area design, loopback advertisement).
- TCP/IP Stack tingkat lanjut: pemahaman mekanisme TCP 3-way handshake, TCP Sliding Window, port 179, Path MTU Discovery, serta manipulasi TTL (Time-To-Live).
- CLI Jaringan Tingkat Menengah: familiar dengan sintaks konfigurasi perangkat jaringan enterprise (Cisco IOS-XE/XR, Arista EOS, atau FRRouting/FRR di Linux).

---

## 3. Concept & Internal Architecture

### 3.1 BGP Internal Memory Architecture: Tiga Kompartemen RIB

BGP tidak langsung menempatkan rute yang diterima ke dalam tabel routing kernel (*Forwarding Information Base* / FIB). Pemrosesan rute dipisahkan ke dalam tiga kompartemen logis memori:

```
                  +-----------------------------------+
                  |        Adj-RIB-In (Unfiltered)    |
                  +-----------------------------------+
                                    |
                           [ Inbound Route-Map ]
                           [ & Prefix-List     ]
                                    v
                  +-----------------------------------+
                  |         Adj-RIB-In (Filtered)     |
                  +-----------------------------------+
                                    |
                        [ BGP Best-Path Selection ]
                                    v
                  +-----------------------------------+
                  |             Loc-RIB               | ---> [ IP Routing Table / FIB ]
                  +-----------------------------------+
                                    |
                           [ Outbound Route-Map ]
                                    v
                  +-----------------------------------+
                  |           Adj-RIB-Out             |
                  +-----------------------------------+
                                    |
                                    v
                               [ Peer BGP ]
```

1. **Adj-RIB-In (Adjacency Routing Information Base, Incoming)**: Menyimpan update *Network Layer Reachability Information* (NLRI) mentah dari peer sebelum atau sesudah implementasi inbound policy. Jika fitur *soft-reconfiguration inbound* aktif, rute mentah yang belum terfilter disimpan terpisah dalam memori, mengorbankan alokasi RAM demi kemampuan re-evaluasi kebijakan tanpa mengirimkan pesan BGP Route Refresh (RFC 7313).
2. **Loc-RIB (Local Routing Information Base)**: Mengandung seluruh rute BGP yang valid setelah lolos inbound policy. Di dalam Loc-RIB, mesin BGP mengeksekusi algoritma *Best-Path Selection*. Rute pemenang (*best path*) kemudian diajukan ke Routing Table Manager (RTM) sistem operasi untuk dikompilasi ke dalam FIB perangkat keras (*ASIC TCAM*).
3. **Adj-RIB-Out (Adjacency Routing Information Base, Outgoing)**: Menyimpan rute-rute yang dipilih dari Loc-RIB yang telah diproses oleh outbound policy dan siap dikemas ke dalam paket BGP `UPDATE` untuk ditransmisikan ke peer terkait.

### 3.2 BGP Finite State Machine (FSM)

BGP beroperasi di atas TCP port 179 melalui 6 tahapan state machine deterministik:

1. **Idle**: State awal. Router menginisiasi resources BGP, mengabaikan koneksi BGP inbound. Saat event `Start` dipicu (misal: peering diaktifkan), router memulai timer `ConnectRetry`, menginisiasi koneksi TCP transport, dan bertransisi ke state **Connect**.
2. **Connect**: Router menunggu TCP handshake selesai. Jika TCP 3-way handshake berhasil, router mengirim paket `OPEN` dan berpindah ke **OpenSent**. Jika timer `ConnectRetry` habis sebelum koneksi terbentuk, router berpindah ke state **Active** dan me-reset timer.
3. **Active**: Router mencoba menginisiasi TCP 3-way handshake secara agresif. Kegagalan berulang di state ini umumnya mengindikasikan masalah konfigurasi layer 1-3, firewall/ACL memblokir TCP 179, salah IP neighbor, atau ketidaksesuaian nomor ASN. Jika TCP terkoneksi, router mengirim pesan `OPEN` dan berpindah ke **OpenSent**. Jika `ConnectRetry` habis, router kembali ke **Connect**.
4. **OpenSent**: Router telah mengirim paket `OPEN` miliknya dan sedang menunggu pesan balasan `OPEN` dari remote peer. Router memvalidasi isi paket `OPEN` peer (BGP Version, ASN, BGP Identifier/Router-ID, Hold-Time, Capability Negotiation seperti Multiprotocol Extensions, 4-byte ASN, Route Refresh). Jika valid, router merespons dengan paket `KEEPALIVE` dan masuk ke **OpenConfirm**. Jika terjadi negosiasi yang tidak cocok, router mengirim paket `NOTIFICATION` dengan error-code spesifik lalu kembali ke **Idle**.
5. **OpenConfirm**: Router menunggu paket `KEEPALIVE` atau `NOTIFICATION` dari remote peer. Penerimaan `KEEPALIVE` menandakan persetujuan mutual atas parameter peering, memicu transisi ke **Established**.
6. **Established**: Peering BGP aktif secara fungsional. Router mulai mempertukarkan paket `UPDATE` (iklan dan penarikan rute / NLRI), `NOTIFICATION` (jika ada kesalahan fatal), dan `KEEPALIVE` berkala (default: interval 60s, hold time 180s) untuk menjaga sesi peering.

### 3.3 The 13-Step BGP Path Selection Algorithm

Ketika Loc-RIB menerima beberapa jalur menuju prefix yang sama persis (panjang subnet mask identik), BGP mengevaluasi atribut rute secara sekuensial. Jika salah satu atribut menghasilkan pemenang, pemrosesan dihentikan:

```
[Candidate Routes for Prefix X]
       |
       v
1. Weight (Tertinggi, Lokal Router - Cisco/FRR Specific)
       | (Sama)
       v
2. Local Preference (Tertinggi, Berlaku dalam satu AS)
       | (Sama)
       v
3. Locally Originated Path (Route dari network/aggregate lokal dipilih vs dari peer)
       | (Sama)
       v
4. AS-Path Length (Terpendek - Menghitung jumlah ASN)
       | (Sama)
       v
5. Origin Type (IGP [i] < EGP [e] < Incomplete [?])
       | (Sama)
       v
6. Multi-Exit Discriminator / MED (Terendah - Berlaku antar ASN yang sama)
       | (Sama)
       v
7. Peer Type (eBGP path > iBGP path)
       | (Sama)
       v
8. IGP Metric to BGP Next-Hop (Metrik IGP terkecil menuju IP Next-Hop)
       | (Sama)
       v
9. BGP Multipath Check (Jika diaktifkan: ECMP dipasang di FIB, proses berhenti)
       | (Non-Multipath / Tie-Break Lanjutan)
       v
10. Oldest Route (Rute eBGP paling stabil/lama diterima untuk mencegah route flapping)
       | (Sama / Sesi iBGP)
       v
11. Lowest BGP Router-ID (Router-ID tetangga terkecil)
       | (Sama - Melalui Route Reflector)
       v
12. Minimum Cluster-List Length (Rute dari RR dengan path traversal terpendek)
       | (Sama)
       v
13. Lowest Peer Interface IP Address (IP Peering terkecil)
```

### 3.4 BGP Path Attributes Taxonomy

Setiap atribut BGP diklasifikasikan ke dalam 4 kategori fundamental:

| Kategori Atribut | Definisi Operasional | Contoh Atribut |
|---|---|---|
| **Well-Known Mandatory** | Harus dikenali oleh seluruh BGP implementation; wajib disertakan di setiap pesan `UPDATE`. | `ORIGIN`, `AS_PATH`, `NEXT_HOP` |
| **Well-Known Discretionary**| Harus dikenali oleh seluruh BGP implementation; opsional untuk disertakan dalam `UPDATE`. | `LOCAL_PREF`, `ATOMIC_AGGREGATE` |
| **Optional Transitive** | Boleh tidak dikenali router; jika tidak dikenali, router tetap meneruskannya ke peer lain tanpa modifikasi. | `COMMUNITY`, `EXTENDED COMMUNITY`, `LARGE COMMUNITY`, `AGGREGATOR` |
| **Optional Non-Transitive** | Boleh tidak dikenali router; jika tidak dikenali, atribut langsung dibuang (*dropped*) dan tidak diteruskan ke peer lain. | `MED` (Multi-Exit Discriminator), `ORIGINATOR_ID`, `CLUSTER_LIST` |

---

## 4. Why & What

### Mengapa Menggunakan iBGP Skala Lanjut daripada Full-Mesh Standar?

Dalam spesifikasi dasar BGP (RFC 4271), aturan *iBGP Split-Horizon* melarang router iBGP meneruskan rute yang dipelajarinya dari satu peer iBGP ke peer iBGP lainnya. Tujuannya adalah mencegah terjadinya loop routing di dalam Autonomous System karena atribut `AS_PATH` tidak bertambah saat rute melintasi sesi iBGP.

Konsekuensinya, jaringan iBGP klasik mewajibkan topologi *Full-Mesh*. Formula koneksi yang dibutuhkan adalah:

$$N_{sessions} = \frac{N(N - 1)}{2}$$

Untuk jaringan dengan $N = 100$ router, dibutuhkan $\frac{100 \times 99}{2} = 4.950$ sesi iBGP TCP point-to-point. Ini memicu:
- Beban memori dan siklus CPU yang eksponensial untuk memproses *keepalive* dan duplikasi rute.
- Ledakan *BGP Update generation* saat terjadi *link flap*.
- Operasional yang rapuh (*fragile operational state*) saat menambah router baru ke inti jaringan.

Solusi arsitektur enterprise untuk memecahkan limitasi ini adalah **Route Reflection (RFC 4456)** dan **BGP Confederations (RFC 5065)**.

### Apa itu Route Reflector (RR)?

Route Reflector melonggarkan aturan *iBGP Split-Horizon* secara terkontrol. Sebuah router yang dikonfigurasi sebagai RR diperbolehkan membaca rute iBGP dari sebuah kelompok router (*Clients*) dan meneruskannya (*reflect*) ke router lain (*Clients* maupun *Non-Clients*).

Untuk mencegah terjadinya routing loop akibat modifikasi aturan ini, RR menyematkan dua atribut *Optional Non-Transitive* tambahan:
1. `ORIGINATOR_ID`: Router-ID dari pembuat rute pertama di dalam AS lokal. Jika sebuah router menerima rute yang memiliki `ORIGINATOR_ID` sama persis dengan Router-ID miliknya sendiri, rute tersebut langsung dibuang.
2. `CLUSTER_LIST`: Rekaman jejak (*sequence*) dari `CLUSTER_ID` router-router RR yang telah memantulkan rute tersebut. Konsepnya analogis dengan `AS_PATH`, namun beroperasi di dalam domain internal AS. Jika sebuah RR melihat `CLUSTER_ID` miliknya telah tercatat di dalam paket `CLUSTER_LIST`, rute diabaikan untuk mencegah perputaran update di antara RR.

---

## 5. How (Workflow Detail)

### 5.1 Route Reflector Propagation Rules

Saat menerima update rute dari suatu peer, RR menentukan arah refleksi berdasarkan status peering:

```
[Sumber Rute Datang] ──────────► [Route Reflector] ──────────► [Target Distribusi]
       |                                                             |
       ├─────► eBGP Peer ───────────────────────────────────────────► Semua Clients & Non-Clients
       ├─────► iBGP Client Peer ────────────────────────────────────► Semua Clients & Non-Clients
       └─────► iBGP Non-Client Peer ────────────────────────────────► HANYA ke Clients
```

### 5.2 Deterministic Path Convergence Workflow (BFD + BGP PIC Core/Edge)

Proses failover BGP standar memakan waktu beberapa detik hingga menit karena dependensi hold-timer. Pada arsitektur Carrier-Grade & High-Performance Enterprise, alur konvergensi dipercepat secara sub-detik melalui rantai orkestrasi berikut:

1. **Hardware Link Flap / BFD Trigger**: Sesi BFD (Bidirectional Forwarding Detection) beroperasi di layer data link dengan interval transmisi 50-300ms. Jika 3 paket BFD berturut-turut hilang, BFD menyatakan *adjacency failure* dalam < 900ms.
2. **Local Engine Interruption**: BFD langsung memberikan interrupt ke BGP control plane lokal tanpa menunggu BGP Hold-Timer (180 detik) kadaluarsa.
3. **BGP Prefix-Independent Convergence (PIC)**: 
   - Pada arsitektur tradisional, router harus melakukan kalkulasi ulang Best-Path secara sekuensial pada 1.000.000 prefix di Loc-RIB, menghasilkan latensi konvergensi linier $O(N)$ (bisa mencapai 10-30 detik).
   - Dengan BGP PIC Core/Edge, router telah mengompilasi *Primary Next-Hop* dan *Backup Next-Hop* ke dalam struktur pointer hierarkis FIB (*Hierarchical FIB*) di hardware ASIC sebelum kegagalan terjadi.
4. **Sub-second Data Plane Re-route**: Begitu interrupt BFD diterima, router hanya membalik status pointer global dari Primary ke Pre-computed Backup Path dalam satu siklus memori, menghasilkan konvergensi instan sub-50 milidetik untuk jutaan rute ($O(1)$ complexity).
5. **Control Plane Convergence**: Secara asinkron, BGP FSM meregenerasi paket BGP `WITHDRAW` ke seluruh downstream neighbor untuk memperbarui topologi jaringan secara global.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pos dan Rapat Perusahaan

Bayangkan iBGP Full-Mesh seperti sebuah ruang rapat berisi 100 eksekutif. Aturan awalnya adalah: "Jika Anda mendengar memo dari salah satu eksekutif, Anda tidak boleh menceritakan memo itu kepada eksekutif lain, untuk mencegah rumor tak berujung (Split-Horizon)." Akibatnya, setiap eksekutif terpaksa membisikkan memo yang sama ke 99 eksekutif lainnya satu per satu secara langsung (*Full-Mesh*). Ruang rapat kolaps karena kebisingan.

Arsitektur **Route Reflector** mengangkat 2 eksekutif senior menjadi "Sekretaris Direksi" (*Route Reflector*). Para manajer divisi (*Clients*) kini hanya perlu menyerahkan laporan mereka ke Sekretaris Direksi. Sekretaris Direksi bertugas membagikan laporan tersebut kepada semua orang. Untuk memastikan tidak ada rumor ganda, Sekretaris membubuhkan stempel: "Memo ini berasal dari Divisi Finansial (Originator-ID) dan telah diverifikasi oleh Sekretariat Ruang 1 (Cluster-ID)". Jika Sekretariat Ruang 1 menerima dokumen dengan cap miliknya sendiri, dokumen tersebut langsung dimusnahkan.

### Diagram Topologi Arsitektur Enterprise BGP Dual-Homed Dual-Tier

```
                              [ Tier-1 Transit Provider A ]          [ Tier-1 Transit Provider B ]
                                     AS 64500                               AS 64501
                                        |                                      |
                           eBGP Session 1 (Primary)               eBGP Session 2 (Secondary)
                           BGP Communities: 64500:100             BGP Communities: 64501:80
                                        |                                      |
                     +------------------v--------------------------------------v------------------+
                     |                          ENTERPRISE EDGE (AS 65000)                        |
                     |                                                                            |
                     |       +-----------------------+          +-----------------------+         |
                     |       |     WAN-EDGE-01       |<========>|     WAN-EDGE-02       |         |
                     |       | Router-ID: 10.0.0.1   |   iBGP   | Router-ID: 10.0.0.2   |         |
                     |       +-----------------------+  Inter-  +-----------------------+         |
                     |                   |              connect             |                     |
                     +-------------------|----------------------------------|---------------------+
                                         |                                  |
                                 iBGP Session                       iBGP Session
                                 (Client/Server)                    (Client/Server)
                                         |                                  |
                     +-------------------v----------------------------------v---------------------+
                     |                      CAMPUS / DATA CENTER CORE                             |
                     |                                                                            |
                     |       +-----------------------+          +-----------------------+         |
                     |       |       CORE-RR-01      |<========>|       CORE-RR-02      |         |
                     |       | (Route Reflector 1)   |   iBGP   | (Route Reflector 2)   |         |
                     |       | Cluster-ID: 1.1.1.1   | Non-Cli  | Cluster-ID: 1.1.1.1   |         |
                     |       +-----------------------+          +-----------------------+         |
                     |                   ^                                  ^                     |
                     |                   |  iBGP Reflected Sessions         |                     |
                     |         +---------+------------+        +------------+---------+           |
                     |         |                      |        |                      |           |
                     |         v                      v        v                      v           |
                     |   +-----------+          +-----------++-----------+          +-----------+ |
                     |   |  PE-DC-01 |          |  PE-DC-02 ||  PE-DC-03 |          |  PE-DC-04 | |
                     |   | (Client)  |          | (Client)  || (Client)  |          | (Client)  | |
                     |   +-----------+          +-----------++-----------+          +-----------+ |
                     +----------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: BGP Route Reflector Server (FRRouting Syntax)

Contoh dasar implementasi Route Reflector pada router `CORE-RR-01` yang melayani dua buah router client (`PE-DC-01` dan `PE-DC-02`).

```text
! FRRouting configuration: /etc/frr/frr.conf
router bgp 65000
 bgp router-id 10.255.0.1
 no bgp default ipv4-unicast
 neighbor CORE-CLIENTS peer-group
 neighbor CORE-CLIENTS remote-as 65000
 neighbor CORE-CLIENTS update-source Loopback0
 
 ! Definisi Neighbor Clients
 neighbor 10.255.0.11 peer-group CORE-CLIENTS
 neighbor 10.255.0.12 peer-group CORE-CLIENTS

 address-family ipv4 unicast
  neighbor CORE-CLIENTS activate
  ! Menunjuk peer-group sebagai client refleksi
  neighbor CORE-CLIENTS route-reflector-client
  neighbor CORE-CLIENTS next-hop-self
 exit-address-family
!
```

### 7.2 Practical Example: Enterprise Edge Router dengan Dual Multi-homing, RPKI, BFD, & Traffic Engineering

Konfigurasi kelas produksi untuk `WAN-EDGE-01` (AS 65000) yang terhubung ke dua upstream transit provider: Primary ke `ISP-A` (AS 64500) dan Secondary/Backup ke `ISP-B` (AS 64501), lengkap dengan BFD, RPKI Route Origin Validation, filtrasi martian prefix, pemetaan community, dan AS-Path prepending.

```text
! =======================================================================
! ENTERPRISE HIGH-AVAILABILITY BGP CONFIGURATION
! Target Engine: FRRouting / Linux Enterprise Network Appliance
! =======================================================================

! Setup RPKI Validator Cache Server Connection (RTR Protocol)
rpki
 rpki cache 192.168.100.50 8282 preference 1
 rpki cache 192.168.100.51 8282 preference 2
 rpki initial-synchronisation timeout 10
exit

! Akses Kontrol Prefix Internal Perusahaan
ip prefix-list PFX-ENTERPRISE-PUBLIC seq 10 permit 198.51.100.0/22
ip prefix-list PFX-ENTERPRISE-PUBLIC seq 20 permit 198.51.100.0/24
ip prefix-list PFX-ENTERPRISE-PUBLIC seq 30 permit 198.51.101.0/24

! Proteksi Default Route & Bogon/Martians (RFC 6890)
ip prefix-list PL-BOGONS seq 5 permit 0.0.0.0/8 le 32
ip prefix-list PL-BOGONS seq 10 permit 10.0.0.0/8 le 32
ip prefix-list PL-BOGONS seq 15 permit 100.64.0.0/10 le 32
ip prefix-list PL-BOGONS seq 20 permit 127.0.0.0/8 le 32
ip prefix-list PL-BOGONS seq 25 permit 169.254.0.0/16 le 32
ip prefix-list PL-BOGONS seq 30 permit 172.16.0.0/12 le 32
ip prefix-list PL-BOGONS seq 35 permit 192.0.2.0/24 le 32
ip prefix-list PL-BOGONS seq 40 permit 192.168.0.0/16 le 32
ip prefix-list PL-BOGONS seq 45 permit 224.0.0.0/4 le 32
ip prefix-list PL-BOGONS seq 50 permit 240.0.0.0/4 le 32

! -----------------------------------------------------------------------
! ROUTE-MAPS: UPSTREAM POLICY CONTROL
! -----------------------------------------------------------------------

! Inbound Policy ISP-A (Primary Path)
route-map RM-ISP-A-IN deny 10
 match ip address prefix-list PL-BOGONS
exit
route-map RM-ISP-A-IN deny 20
 ! Tolak rute yang berstatus Invalid oleh RPKI ROV
 match rpki invalid
exit
route-map RM-ISP-A-IN permit 30
 ! Validated or Not Found prefixes diizinkan; set Local-Pref tinggi
 match rpki valid
 set local-preference 200
 set community 65000:100 additive
exit
route-map RM-ISP-A-IN permit 40
 match rpki notfound
 set local-preference 150
 set community 65000:100 additive
exit

! Inbound Policy ISP-B (Secondary Path)
route-map RM-ISP-B-IN deny 10
 match ip address prefix-list PL-BOGONS
exit
route-map RM-ISP-B-IN deny 20
 match rpki invalid
exit
route-map RM-ISP-B-IN permit 30
 ! Jalur alternatif diatur dengan Local-Pref lebih rendah
 set local-preference 100
 set community 65000:200 additive
exit

! Outbound Policy ISP-A (Jalur Utama - Tanpa AS-Path Prepend)
route-map RM-ISP-A-OUT permit 10
 match ip address prefix-list PFX-ENTERPRISE-PUBLIC
 set community 64500:100 additive
exit
route-map RM-ISP-A-OUT deny 99
exit

! Outbound Policy ISP-B (Jalur Backup - Prepend ASN 3x)
route-map RM-ISP-B-OUT permit 10
 match ip address prefix-list PFX-ENTERPRISE-PUBLIC
 set as-path prepend 65000 65000 65000
 set community 64501:80 additive
exit
route-map RM-ISP-B-OUT deny 99
exit

! -----------------------------------------------------------------------
! BGP ENGINE CONFIGURATION
! -----------------------------------------------------------------------
router bgp 65000
 bgp router-id 10.0.0.1
 no bgp default ipv4-unicast
 
 ! Graceful-Restart & Konvergensi Cepat
 bgp graceful-restart
 bgp graceful-restart stalepath-time 300
 
 ! Definisi External Neighbor: ISP-A (AS 64500)
 neighbor 203.0.113.1 remote-as 64500
 neighbor 203.0.113.1 description TRANSIT_PROVIDER_A_PRIMARY
 neighbor 203.0.113.1 bfd
 neighbor 203.0.113.1 timers 10 30
 neighbor 203.0.113.1 route-map RM-ISP-A-IN in
 neighbor 203.0.113.1 route-map RM-ISP-A-OUT out

 ! Definisi External Neighbor: ISP-B (AS 64501)
 neighbor 198.51.100.254 remote-as 64501
 neighbor 198.51.100.254 description TRANSIT_PROVIDER_B_BACKUP
 neighbor 198.51.100.254 bfd
 neighbor 198.51.100.254 timers 10 30
 neighbor 198.51.100.254 route-map RM-ISP-B-IN in
 neighbor 198.51.100.254 route-map RM-ISP-B-OUT out

 ! Definisi Core Route Reflector iBGP
 neighbor 10.255.0.1 remote-as 65000
 neighbor 10.255.0.1 update-source Loopback0
 neighbor 10.255.0.1 description CORE-RR-01
 neighbor 10.255.0.1 bfd

 address-family ipv4 unicast
  ! Ekspor Prefix Publik Lokal ke BGP Loc-RIB
  network 198.51.100.0/22
  network 198.51.100.0/24
  network 198.51.101.0/24

  neighbor 203.0.113.1 activate
  neighbor 203.0.113.1 maximum-prefix 900000 80 restart 15
  
  neighbor 198.51.100.254 activate
  neighbor 198.51.100.254 maximum-prefix 900000 80 restart 15

  neighbor 10.255.0.1 activate
  neighbor 10.255.0.1 next-hop-self
  neighbor 10.255.0.1 send-community both
 exit-address-family
!
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden Global Route Leaking & Mitigasi Traffic Asymmetric FinTech Multinasional

#### Latar Belakang
Sebuah perusahaan pembayaran digital (FinTech) multinasional dengan ASN terdaftar `AS 65111` memiliki koneksi multi-homed ke Tier-1 Telco A dan Tier-1 Telco B. Perusahaan menampung volume transaksi harian senilai puluhan juta dolar dengan Service Level Agreement (SLA) latensi payment gateway di bawah 150 milidetik.

#### Masalah (Root-Cause Incident)
1. **Insiden BGP Route Leak**: Akibat kelalaian konfigurasi (*fat-finger*) pada route-map outbound di Edge Router mereka, router FinTech tersebut mengimpor seluruh tabel internet routing (~900.000 prefix) dari Telco A dan mengumumkannya kembali (*readvertised*) ke Telco B tanpa menyaring prefix tersebut. 
2. **Akibat**: FinTech AS 65111 mendadak menjadi jalur perantara (*transit provider*) gratis bagi lalu lintas internet antara Telco A dan Telco B. Bandwidth sirkuit WAN 10 Gbps milik FinTech seketika mengalami saturasi 100%, memicu paket loss 75%, kegagalan transaksi massal, dan sistem crash.
3. **Traffic Asymmetric yang Ekstrem**: Telco B mengirimkan traffic inbound ke FinTech melalui jalur trans-atlantik dengan latensi >300ms, sementara traffic outbound dikirim melalui Telco A via jalur lokal <20ms, merusak penanganan firewall stateful di perimeter.

#### Solusi Arsitektur & Mitigasi Produksi

Perusahaan melakukan perombakan arsitektur BGP komprehensif menggunakan 3 pilar:

1. **Penerapan RFC 9234 (BGP Open Policy) & Atribut Strict Filter**:
   - Menerapkan *Prefix-List Filtering* berbasis *Internet Routing Registry* (IRR) dan RPKI.
   - Mengunci `send-community` dan menerapkan `no-export` community secara tegas pada prefix yang dipelajari secara eksternal.
   - Menyusun outbound filter di mana Edge Router HANYA mengiklankan prefix milik korporat sendiri:

   ```text
   ! Firewalling BGP Outbound: HANYA Iklankan Prefix Sendiri
   ip prefix-list PFX-OWN-PREFIX permit 203.0.113.0/24 le 24
   
   route-map RM-STRICT-TRANSIT-OUT permit 10
    match ip address prefix-list PFX-OWN-PREFIX
   exit
   route-map RM-STRICT-TRANSIT-OUT deny 99
    ! Drop any other routes unconditionally
   exit
   ```

2. **Mitigasi Asymmetric Routing Menggunakan Standardized BGP Communities**:
   - Menggunakan selective *BGP Communities* yang didukung upstream untuk memanipulasi *Local Preference* upstream langsung di router provider mereka.
   - Menginstruksikan Telco B untuk menurunkan Local-Pref traffic inbound ke FinTech dengan menyematkan tag `64501:80` (Telco B Community convention for Low Local-Pref).

3. **Aktivasi BGP Flowspec (RFC 5575) & RTBH (Remote Triggered Black Hole)**:
   - Jika sirkuit terancam saturasi akibat serangan DDoS atau rute bocor, router core dapat mengumumkan host IP `/32` dengan community `65535:666` (Blackhole Community RFC 7999) ke upstream provider guna mematikan rute berbahaya langsung di edge jaringan Tier-1 upstream sebelum membanjiri sirkuit lokal.

---

## 9. Trade-offs

Setiap keputusan rekayasa dalam deployment BGP tingkat tinggi melibatkan kompromi teknis:

```
[Full BGP Tables] <-------------------------------------------> [Default Route Only]
  (+) Kontrol granular traffic path.                             (+) Kebutuhan RAM/CPU sangat minim.
  (+) Kemampuan multi-homing presisi.                           (+) Waktu konvergensi instan (<1 detik).
  (-) Kebutuhan RAM besar (>2GB per peer).                       (-) Jalur sub-optimal tidak terpantau.
  (-) CPU spike saat kalkulasi Best-Path (~1M rute).             (-) Tidak bisa rekayasa egress traffic.

[BGP Route Reflection] <--------------------------------------> [Full-Mesh iBGP]
  (+) Skalabilitas hingga ribuan node: O(N).                    (+) Jalur routing selalu optimal end-to-end.
  (+) Manajemen konfigurasi sentralistik.                        (+) Tidak ada risiko sub-optimal forwarding.
  (-) Potensi persistent route oscillation.                      (-) Skalabilitas buruk: O(N^2).
  (-) Visibilitas rute terbatas (hanya Best-Path dibagikan).     (-) Konsumsi resource peer luar biasa boros.

[Sub-Second BFD Aggressive Timers] <--------------------------> [Standard BGP Timers]
  (+) Konvergensi ultra-cepat (<100ms failover).                (+) Sangat toleran terhadap jitter CPU/Link.
  (-) Risiko false-positive link flap akibat transient spike.   (-) Downtime panjang saat link down (3 menit).
```

### Analisis Finansial vs. Performa
- **Full Internet Routing Table**: Menuntut hardware enterprise dengan alokasi TCAM/RAM besar (misal: Arista 7280R series atau Cisco ASR1000/ASR9000). Penambahan RAM dan ASIC berkapasitas tinggi menaikkan belanja modal (CapEx) hingga 300% per unit router.
- **Partial Tables + Default Route**: Solusi efisien biaya di mana router edge hanya menerima rute domestik/regional (misal: ~50.000 prefix via IXP/Direct Peering) dan rute default `0.0.0.0/0` via Tier-1 transit. Mengurangi kebutuhan memori hingga 90% tanpa menurunkan efisiensi latency lalu lintas lokal.

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Empat Kesalahan Fatal dalam Implementasi BGP Enterprise

1. **iBGP Next-Hop Unreachable**:
   - *Gejala*: Rute BGP muncul di `show ip bgp`, namun tidak dipasang di routing table (`show ip route`) dan traffic di-drop.
   - *Akar Masalah*: Saat rute eBGP dioper ke iBGP, atribut `NEXT_HOP` tidak diubah secara default. Router internal tidak memiliki rute IGP untuk mencapai IP next-hop ISP eksternal tersebut.
   - *Solusi*: Selalu pasang perintah `neighbor <group> next-hop-self` pada sesi iBGP peering yang menghadap router internal.

2. **BGP Route Flapping & Inappropriate Dampening**:
   - *Gejala*: Prefix berfluktuasi antara kondisi terhubung dan terputus secara berkala, atau prefix enterprise di-suppress oleh ISP global selama berjam-jam.
   - *Akar Masalah*: Link WAN fisik tidak stabil atau BFD interval terlalu agresif pada link publik berkualitas rendah. Upstream ISP menerapkan *Route Flap Dampening* (RFC 2439) yang otomatis memblokir prefix yang flapping berulang.
   - *Solusi*: Matikan flap dampening pada rute internal, stabilkan link layer-1/2, dan sesuaikan BFD hold-timers dengan mempertimbangkan jitter latency penyedia transit.

3. **Prefix Filtering Omission (The Transit-Leak Disaster)**:
   - *Gejala*: Penggunaan bandwidth upstream mendadak melonjak melebihi kapasitas kontrak, router freeze akibat CPU 100%.
   - *Akar Masalah*: Lupa mengaitkan `route-map out` atau `prefix-list out` pada neighbor eBGP. Default perilaku beberapa implementasi BGP (sebelum RFC 8212) adalah meneruskan seluruh isi Loc-RIB ke semua peer.
   - *Solusi*: Terapkan arsitektur filter *Default-Deny*: selalu cantumkan deny policy eksplisit di akhir semua route-map dan pastikan perangkat mematuhi RFC 8212 (*Default reject behavior for BGP route exchange without explicit policy*).

4. **MTU Mismatch pada Jalur eBGP Multi-Hop**:
   - *Gejala*: Sesi BGP berhasil mencapai state `Established`, pertukaran keepalive lancar, tetapi saat pengiriman prefix dalam jumlah besar (paket UPDATE ukuran jumbo), peering mendadak putus dan kembali ke state `Active` atau `Idle`.
   - *Akar Masalah*: Sesi BGP melintasi interface dengan nilai MTU berbeda (misal: router 1500 byte, link perantara 1450 byte). Keepalive berukuran kecil lolos, tetapi frame update TCP ukuran maksimal (MSS) di-drop diam-diam karena penolakan fragmentasi (flag DF aktif).
   - *Solusi*: Samakan MTU end-to-end, aktifkan `ip tcp path-mtu-discovery`, atau turunkan `ip tcp mss` pada interface BGP peering.

### 10.2 Workflow Diagnostik BGP

```
                    [ Sesi BGP Tidak Terbentuk ]
                                 |
                                 v
                 Apakah Ping Layer-3 ke IP Neighbor Berhasil?
                       |                        |
                      (No)                     (Yes)
                       |                        |
                       v                        v
        [ Periksa Interface, IP, ]     Apakah TCP Port 179 Terbuka?
        [ Subnet Mask, dan Metrik]     (Gunakan: telnet <IP> 179)
                                                |
                               +----------------+----------------+
                               |                                 |
                              (No)                              (Yes)
                               |                                 |
                               v                                 v
                 [ Periksa ACL/Firewall ]          Apakah BGP State Stuck
                 [ yang Memblokir Port  ]          di Connect/Active?
                                                                 |
                                                +----------------+----------------+
                                                |                                 |
                                               (No)                              (Yes)
                                                |                                 |
                                                v                                 v
                                    [ Periksa State Lain: ]           [ Periksa Konfigurasi: ]
                                    [ OpenSent/OpenConfirm]           - AS Number Cocok?
                                    - Router ID Duplikat?             - Update-Source Sesuai?
                                    - Hold Time Mismatch?             - eBGP Multi-hop Perlu?
                                    - Capability Mismatch?            - Password TCP MD5 Cocok?
```

---

## 11. Best Practices (Production Checklist)

Gunakan tabel checklist verifikasi berikut sebelum merilis konfigurasi BGP ke lingkungan produksi:

| Kategori | Item Checklist | Status Verifikasi |
|---|---|---|
| **Resilience** | Sesi BGP loopback-to-loopback untuk iBGP menggunakan `update-source Loopback0`. | [ ] |
| **Resilience** | `neighbor <IP> next-hop-self` aktif pada semua sesi peering iBGP edge router. | [ ] |
| **Performance** | Integrasi BFD aktif untuk peering inter-chassis dengan timer minimal $3 \times 300\text{ ms}$. | [ ] |
| **Security** | BGP Neighbor Authentication menggunakan TCP-AO (*Authentication Option*) atau TCP MD5. | [ ] |
| **Security** | `maximum-prefix` limit dikonfigurasi pada seluruh sesi eBGP transit dan peering. | [ ] |
| **Security** | RPKI Route Origin Validation (ROV) aktif; rute `Invalid` langsung di-*drop*. | [ ] |
| **Policy** | Aturan pemfilteran *Bogon* dan *Martian* prefix dipasang pada seluruh ingress eBGP. | [ ] |
| **Policy** | Outbound prefix-list dipasang secara ketat untuk mencegah kebocoran rute (Route Leak). | [ ] |
| **Architecture** | Nilai `CLUSTER_ID` yang identik digunakan pada pasangan Redundant Route Reflector. | [ ] |
| **Monitoring** | Event logging BGP FSM state change dan SNMP/Telemetry traps diaktifkan ke SIEM. | [ ] |

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun topologi BGP Multi-Homed Enterprise menggunakan lingkungan emulasi Linux Network Namespace dan **FRRouting (FRR)**.

```
                      +-----------------------------+
                      |         HOST-ISP-A          |
                      |   ASN: 64500 (Upstream)     |
                      |    IP: 203.0.113.1/30       |
                      +-----------------------------+
                                     |
                                (veth-isp)
                                     |
                                (veth-edge)
                      +-----------------------------+
                      |       ENTERPRISE-EDGE       |
                      |   ASN: 65000 (Perusahaan)   |
                      |  Loopback: 10.255.0.1/32    |
                      +-----------------------------+
```

### Langkah 1: Persiapan Environment dan Network Namespaces

Jalankan perintah berikut di terminal Linux (Ubuntu/Debian) dengan privilege `sudo`:

```bash
# 1. Pastikan tools dasar dan FRR terinstall
sudo apt-get update && sudo apt-get install -y frr iproute2 tcpdump

# 2. Buat Network Namespaces untuk isolasi node ISP dan Edge
sudo ip netns add ns-edge
sudo ip netns add ns-isp

# 3. Buat Virtual Ethernet Link (veth pair)
sudo ip link add veth-edge type veth peer name veth-isp

# 4. Asosiasikan link ke namespace masing-masing
sudo ip link set veth-edge netns ns-edge
sudo ip link set veth-isp netns ns-isp

# 5. Konfigurasi Addressing pada link veth
sudo ip netns exec ns-edge ip addr add 203.0.113.2/30 dev veth-edge
sudo ip netns exec ns-edge ip link set veth-edge up
sudo ip netns exec ns-edge ip link add name lo type dummy
sudo ip netns exec ns-edge ip addr add 10.255.0.1/32 dev lo
sudo ip netns exec ns-edge ip link set lo up

sudo ip netns exec ns-isp ip addr add 203.0.113.1/30 dev veth-isp
sudo ip netns exec ns-isp ip link set veth-isp up
sudo ip netns exec ns-isp ip link add name lo type dummy
sudo ip netns exec ns-isp ip addr add 8.8.8.8/32 dev lo
sudo ip netns exec ns-isp ip link set lo up

# Verifikasi konektivitas layer 3
sudo ip netns exec ns-edge ping -c 2 203.0.113.1
```

### Langkah 2: Setup Direktori dan Konfigurasi FRR

Buat struktur folder untuk menyimpan file konfigurasi:

```bash
mkdir -p hands-on/m02/edge hands-on/m02/isp
```

Buat file konfigurasi Edge Router: `hands-on/m02/edge/frr.conf`
```text
! /hands-on/m02/edge/frr.conf
frr version 8.1
frr defaults traditional
hostname ENTERPRISE-EDGE
log stdout

router bgp 65000
 bgp router-id 10.255.0.1
 no bgp default ipv4-unicast
 
 neighbor 203.0.113.1 remote-as 64500
 neighbor 203.0.113.1 description TRANSIT-ISP-A
 
 address-family ipv4 unicast
  neighbor 203.0.113.1 activate
  neighbor 203.0.113.1 route-map RM-IN in
  neighbor 203.0.113.1 route-map RM-OUT out
  network 10.255.0.1/32
 exit-address-family

route-map RM-IN permit 10
 set local-preference 150
 set community 65000:100 additive
exit

route-map RM-OUT permit 10
 match ip address prefix-list PFX-LOCAL
exit
route-map RM-OUT deny 99
exit

ip prefix-list PFX-LOCAL permit 10.255.0.1/32
```

Buat file konfigurasi ISP Router: `hands-on/m02/isp/frr.conf`
```text
! /hands-on/m02/isp/frr.conf
frr version 8.1
frr defaults traditional
hostname HOST-ISP-A
log stdout

router bgp 64500
 bgp router-id 8.8.8.8
 no bgp default ipv4-unicast
 
 neighbor 203.0.113.2 remote-as 65000
 neighbor 203.0.113.2 description CUST-ENTERPRISE
 
 address-family ipv4 unicast
  neighbor 203.0.113.2 activate
  network 8.8.8.8/32
 exit-address-family
```

### Langkah 3: Eksekusi Daemon FRR di Dalam Namespaces

```bash
# Buat file daemons definition
echo "bgpd=yes" > hands-on/m02/daemons

# Eksekusi BGP Daemon di namespace Edge
sudo ip netns exec ns-edge /usr/lib/frr/bgpd -f hands-on/m02/edge/frr.conf -i /tmp/bgpd-edge.pid --vty_socket /tmp/edge-vty &

# Eksekusi BGP Daemon di namespace ISP
sudo ip netns exec ns-isp /usr/lib/frr/bgpd -f hands-on/m02/isp/frr.conf -i /tmp/bgpd-isp.pid --vty_socket /tmp/isp-vty &

sleep 3
```

### Langkah 4: Verifikasi Status Operasional Melalui VTYSH

Buka terminal diagnosa interaktif BGP pada router Edge:

```bash
# Jalankan vtysh khusus namespace Edge
sudo ip netns exec ns-edge vtysh --vty_socket /tmp/edge-vty
```

Jalankan perintah-perintah verifikasi berikut di dalam prompt `ENTERPRISE-EDGE#`:

```text
! 1. Verifikasi Status BGP Peering
show ip bgp summary

! 2. Periksa rute yang berhasil dipelajari di BGP Loc-RIB
show ip bgp

! 3. Analisis rute detail termasuk atribut BGP Community & Local-Preference
show ip bgp 8.8.8.8/32

! 4. Verifikasi prefix yang diiklankan ke upstream ISP
show ip bgp neighbors 203.0.113.1 advertised-routes
```

*Expected Output pada langkah 3 (`show ip bgp 8.8.8.8/32`):*
```text
BGP routing table entry for 8.8.8.8/32
  Paths: (1 available, best #1, table default)
    Advertised to non-peer-group peers:
    64500
      203.0.113.1 from 203.0.113.1 (8.8.8.8)
        Origin IGP, metric 0, localpref 150, valid, external, best (First path received)
        Community: 65000:100
        Last update: Mon Oct 25 10:14:02 2026
```

### Langkah 5: Cleanup Environment

```bash
sudo kill -9 $(cat /tmp/bgpd-edge.pid) $(cat /tmp/bgpd-isp.pid)
sudo rm -rf /tmp/*-vty /tmp/*.pid hands-on/m02/daemons
sudo ip netns del ns-edge
sudo ip netns del ns-isp
```

---

## 13. Exercise

### Level Easy
1. Ubah konfigurasi `ENTERPRISE-EDGE` pada hands-on di atas untuk menambahkan atribut BGP Large Community `65000:10:1` pada semua rute ingress dari ISP-A.
2. Jelaskan output perubahan perintah `show ip bgp 8.8.8.8/32` setelah penambahan konfigurasi tersebut.
   - *Kriteria Selesai*: Output memuat string atribut `Large Community: 65000:10:1`.

### Level Medium
1. Tambahkan router ketiga `HOST-ISP-B` (ASN 64501) dalam topologi hands-on, dan hubungkan ke `ENTERPRISE-EDGE`.
2. Konfigurasikan inbound routing policy:
   - Rute default yang diterima dari `HOST-ISP-A` diberi `local-preference 300`.
   - Rute default yang diterima dari `HOST-ISP-B` diberi `local-preference 200`.
3. Lakukan pengujian simulasi link-down pada interface yang menghadap ISP-A dan buktikan bahwa failover terjadi otomatis ke ISP-B tanpa intervensi manual.
   - *Kriteria Selesai*: Routing table Linux kernel (`ip route`) di namespace `ns-edge` beralih otomatis ke IP gateway ISP-B.

### Level Hard
1. Buat skenario di mana `ENTERPRISE-EDGE` bertindak sebagai iBGP Route Reflector bagi dua router internal (`PE-1` dan `PE-2`).
2. Terapkan arsitektur di mana `PE-1` tidak boleh menerima rute yang berasal dari `PE-2` dengan memanfaatkan filter BGP Community khusus (`no-export` atau community buatan), namun traffic transit dari ISP eksternal tetap terdistribusi penuh ke `PE-1` dan `PE-2`.
   - *Kriteria Selesai*: Output `show ip bgp` pada `PE-1` hanya menampilkan rute external transit dan loopback RR, tanpa memuat prefix lokal milik `PE-2`.

---

## 14. Challenge

### Skenario Kasus Nyata: Migrasi Tanpa Downtime & Rekayasa Asymmetric Multi-Region Data Center

**Deskripsi Tantangan**:
Anda adalah Principal Network Architect di institusi perbankan tier-1. Organisasi Anda sedang melakukan akuisisi entitas finansial lain yang mengoperasikan Autonomous System sendiri (`AS 65200`). Infrastruktur eksisting Anda menggunakan `AS 65100`.

**Persyaratan Desain**:
1. **Peleburan Dua AS**: Satukan kedua sistem routing internal tanpa melakukan re-addressing nomor ASN internal pada ribuan router cabang secara langsung. Implementasikan fitur BGP `local-as` dan `no-prepend replace-as` untuk menyamarkan proses migrasi terhadap seluruh upstream transit global.
2. **Deterministic Dual-Homed Active/Active Traffic Engineering**:
   - Rentang IP Korporat: `198.51.100.0/22`.
   - Pecah prefix menjadi dua blok `/23`: Blok A (`198.51.100.0/23`) dan Blok B (`198.51.102.0/23`).
   - Rancang konfigurasi BGP Policy sedemikian rupa sehingga:
     - Lalu lintas inbound dari seluruh dunia menuju **Blok A** wajib 100% masuk melalui **Provider 1**, dan hanya beralih ke **Provider 2** jika Provider 1 mati total.
     - Lalu lintas inbound menuju **Blok B** wajib 100% masuk melalui **Provider 2**, dan hanya beralih ke **Provider 1** jika Provider 2 mati total.
     - DILARANG mengalami *Sub-optimal De-aggregation routing leak* ke tabel internet global (tidak boleh mengekspos subnet lebih kecil dari `/24`).
3. **Mitigasi Asymmetric Stateful Firewall**:
   - Jika paket keluar (*egress*) melalui Provider 1, paket kembali (*ingress*) WAJIB melalui Provider 1. Jika terpaksa terjadi asimetris akibat routing internet eksternal yang di luar kendali, rancang mekanisme data-plane encapsulation (misal: BGP EVPN over VXLAN / SRv6 inter-DC interconnect) untuk merutekan paket ke firewall asal sebelum di-inspect.

**Deliverable**:
- Gambar diagram topologi detil (format ASCII).
- File konfigurasi lengkap BGP Edge Router (Route-maps, Prefix-lists, BGP Communities, Local-AS).
- Dokumen analisis mitigasi kegagalan (*Failover Matrix Verification Steps*).

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic

1. **Pada BGP finite state machine, state manakah yang menandakan bahwa router telah berhasil membuat TCP 3-way handshake dan sedang menunggu pesan `OPEN` dari remote peer?**
   - A. Connect
   - B. Active
   - C. OpenSent
   - D. OpenConfirm
   - *Jawaban*: C. Di state OpenSent, router telah berhasil mendirikan koneksi TCP dan mengirimkan paket OPEN miliknya, serta sedang menunggu paket OPEN balasan dari tetangga.

2. **Atribut BGP manakah di bawah ini yang dikategorikan sebagai Well-Known Discretionary?**
   - A. AS-Path
   - B. Local Preference
   - C. Multi-Exit Discriminator (MED)
   - D. Origin
   - *Jawaban*: B. Local Preference wajib dipahami oleh setiap implementasi BGP, tetapi penyertaannya dalam paket UPDATE bersifat diskresioner (opsional, default berlaku internal AS).

3. **Mengapa nilai Local Preference yang lebih tinggi lebih diprioritaskan dibandingkan nilai Local Preference yang lebih rendah?**
   - A. Karena Local Preference menentukan metrik IGP terdekat.
   - B. Karena arsitektur BGP mendesain nilai Local Preference yang lebih tinggi sebagai rute preferensial keluar (*outbound egress*) dari suatu Autonomous System.
   - C. Agar menghemat konsumsi memori pada Loc-RIB.
   - D. Karena dispesifikasikan agar kompatibel dengan protokol distance-vector lawas.
   - *Jawaban*: B. Dalam algoritma seleksi BGP, Local Preference tertinggi memenangkan kompetisi untuk mengarahkan lalu lintas egress dari AS lokal.

4. **Apa fungsi utama atribut `ORIGINATOR_ID` pada implementasi iBGP Route Reflector?**
   - A. Menyimpan IP address dari ISP pertama yang mengumumkan prefix.
   - B. Menggantikan atribut BGP Router-ID pada pesan OPEN.
   - C. Mencegah terjadinya routing loop di dalam AS lokal dengan cara mendeteksi dan menolak rute yang kembali ke pembuat asalnya.
   - D. Mempercepat proses negosiasi kemampuan BFD.
   - *Jawaban*: C. Atribut non-transitive `ORIGINATOR_ID` diciptakan oleh Route Reflector untuk menandai pembuat rute awal dalam iBGP mesh, sehingga router pembuat awal dapat langsung membuang rute tersebut jika berputar kembali ke dirinya.

5. **Format representasi standar RFC 8092 untuk BGP Large Communities terdiri dari format angka seperti apa?**
   - A. 16-bit ASN : 16-bit Data
   - B. 32-bit ASN : 16-bit Function : 16-bit Data
   - C. 32-bit Global Administrator : 32-bit Assigned Data 1 : 32-bit Assigned Data 2
   - D. 64-bit Hexadecimal Hash
   - *Jawaban*: C. Large BGP Communities menggunakan struktur 12-byte: 4-byte Global Administrator (ASN 4-byte) dan dua buah field data berukuran 4-byte (Data 1 dan Data 2).

---

### 5 Pertanyaan Intermediate

6. **Dua rute menuju prefix yang sama persis diterima oleh router. Rute A memiliki panjang AS-Path 3 dengan Origin IGP (`i`). Rute B memiliki panjang AS-Path 2 dengan Origin Incomplete (`?`). Asumsikan Weight dan Local-Pref identik. Rute manakah yang dipilih oleh BGP Best-Path Algorithm?**
   - A. Rute A, karena Origin IGP lebih dipercaya dibanding Incomplete.
   - B. Rute B, karena evaluasi panjang AS-Path dilakukan lebih dahulu sebelum evaluasi tipe Origin.
   - C. Rute A, karena BGP tidak mempercayai rute bertanda Incomplete.
   - D. Kedua rute dipasang bersamaan menggunakan ECMP.
   - *Jawaban*: B. Tahapan evaluasi BGP Best-Path memeriksa panjang AS-Path (Langkah 4) SEBELUM memeriksa tipe Origin (Langkah 5). Karena Rute B memiliki AS-Path lebih pendek (2 < 3), Rute B langsung menang.

7. **Pada rancangan redundant dual Route Reflector di dalam satu cluster, mengapa kedua Route Reflector WAJIB dikonfigurasi dengan `cluster-id` yang sama persis?**
   - A. Agar kedua router berbagi IP address loopback yang sama (Anycast BGP).
   - B. Untuk mengizinkan kedua RR saling membuang rute refleksi dari pasangannya sehingga menghemat komputasi dan mencegah loop refleksi internal cluster.
   - C. Karena protokol TCP 179 mewajibkan identitas cluster seragam.
   - D. Agar tabel Adj-RIB-Out dapat disinkronkan secara langsung di tingkat kernel.
   - *Jawaban*: B. Memberikan `cluster-id` yang sama pada kedua RR memastikan bahwa jika RR-1 memantulkan rute ke RR-2, RR-2 melihat Cluster-ID miliknya sendiri telah tertera pada `CLUSTER_LIST` dan tidak memantulkannya kembali ke client, menghindari loop sirkular antar-reflector.

8. **Apa perbedaan operasional mendasar antara atribut MED (Multi-Exit Discriminator) dengan Local Preference?**
   - A. Local Preference disebarkan antar-AS yang berbeda, sedangkan MED hanya beroperasi di dalam internal AS.
   - B. Nilai MED terkecil adalah yang menang, dan nilainya dikirimkan ke remote AS untuk memengaruhi lalu lintas *inbound*, sedangkan Local Preference memengaruhi lalu lintas *outbound* dan tidak disebarkan ke luar AS.
   - C. Nilai MED tertinggi adalah yang menang, dan tidak dapat dimanipulasi dengan route-map.
   - D. MED adalah atribut Well-Known Mandatory, sedangkan Local Preference adalah Optional Transitive.
   - *Jawaban*: B. MED dirancang bagi sebuah AS untuk mengiklankan preferensi ingress ke AS tetangga (nilai terkecil dipilih), dan secara default bersifat non-transitive (tidak diteruskan ke AS ke-3). Sebaliknya, Local Preference mengendalikan arah egress keluar dari dalam AS sendiri.

9. **Ketika fitur RPKI Route Origin Validation (ROV) diaktifkan, status apakah yang diberikan pada rute yang diterima jika prefix tersebut memiliki kecocokan record ROA (Route Origin Authorization) pada database RPKI tetapi originated ASN-nya berbeda dari data ROA?**
   - A. NotFound
   - B. Unknown
   - C. Valid
   - D. Invalid
   - *Jawaban*: D. Jika sebuah ROA mencakup prefix tersebut namun ASN pengumum (origin AS) tidak cocok dengan daftar ASN terotorisasi di ROA, status validasinya secara tegas adalah `Invalid`.

10. **Bagaimana mekanisme teknik BGP Prefix-Independent Convergence (PIC) mampu memangkas waktu pemulihan link failure dari puluhan detik menjadi di bawah 50 milidetik pada router yang menampung 1.000.000 prefix?**
    - A. Dengan cara menyalakan kompresi gzip pada paket BGP UPDATE.
    - B. Dengan menyusun struktur data FIB di level hardware ASIC secara hierarkis (pointer-based), di mana jutaan prefix merujuk pada satu pointer Next-Hop yang sama; saat kegagalan terjadi, hanya satu pointer Next-Hop yang diubah.
    - C. Dengan menonaktifkan algoritma split-horizon sehingga komputasi best-path di-bypass.
    - D. Dengan mendistribusikan Loc-RIB ke router tetangga menggunakan multithreading.
    - *Jawaban*: B. BGP PIC memisahkan entri prefix dengan entri adjacency forwarding di hardware FIB (Hierarchical FIB). Ketika link mati, hardware tidak perlu memperbarui 1 juta prefix satu per satu, melainkan cukup mengubah satu pointer Next-Hop bersama ke jalur backup, menyelesaikannya dalam waktu $O(1)$.

---

### 3 Skenario Kasus Produksi

11. **Skenario Kasus 1**:
    Sebuah Edge Router enterprise menerima rute default `0.0.0.0/0` dari dua ISP yang berbeda (ISP-1 dan ISP-2). Keduanya memiliki konfigurasi Local Preference yang identik (100). Sesi eBGP ke ISP-1 berjalan di atas interface fisik langsung 10 Gbps. Sesi eBGP ke ISP-2 berjalan di atas interface fisik 1 Gbps. Namun, tim operasional mengamati bahwa router secara konsisten memilih rute melalui ISP-2 (1 Gbps) sebagai Best-Path. Tidak ada policy Weight, MED, atau AS-Path prepend yang diterapkan. 
    
    *Mengapa router memilih jalur ISP-2, dan langkah diagnostik apa yang membuktikannya?*
    - *Solusi & Analisis*: 
      BGP secara default **tidak memperhitungkan bandwidth interface fisik** (kecuali fitur non-standar BGP Link Bandwidth DMZ diaktifkan). Jika Weight, Local-Pref, Locally-Originated, AS-Path Length (keduanya panjang 1), Origin, dan MED seri, pemenang ditentukan oleh tie-breaker BGP:
      1. Sesi ke ISP-2 mungkin telah Established lebih lama dibandingkan sesi ISP-1 (Langkah 10: *Oldest Route*).
      2. Atau Router-ID milik ISP-2 bernilai numerik lebih rendah daripada Router-ID ISP-1 (Langkah 11).
      
      *Diagnostik*: Jalankan perintah `show ip bgp 0.0.0.0/0` atau `show ip bgp 0.0.0.0/0 bestpath-reason`. CLI akan secara eksplisit mencetak alasan komparasi, misalnya: *"bestpath tie-break: oldest eBGP route"* atau *"bestpath tie-break: lower Router-ID"*.

12. **Skenario Kasus 2**:
    Dua unit Data Center Router (DC-GW-01 dan DC-GW-02) bertindak sebagai iBGP Route Reflector redundant. Di antara kedua RR ini, rute menuju prefix subnet aplikasi `10.100.0.0/24` mendadak mengalami osilasi tanpa henti (*persistent route oscillation*): rute berganti pemenang setiap beberapa milidetik, memicu utilisasi CPU 100% pada control plane dan hilangnya paket data secara periodik. MED diaktifkan pada peering upstream yang berbeda.
    
    *Apa akar penyebab dari persistent BGP route oscillation ini pada arsitektur Route Reflector, dan bagaimana cara memperbaikinya?*
    - *Solusi & Analisis*:
      Ini adalah masalah klasik *BGP Persistent Route Oscillation in RR Topologies with Non-Transitive MED* (RFC 3345). Terjadi ketika perbandingan MED dilakukan antar rute yang dipelajari dari beberapa AS yang berbeda, sementara komparasi rute BGP lokal diinterupsi oleh preferensi metrik IGP internal menuju RR. Karena RR-1 dan RR-2 memiliki jarak metrik IGP yang berbeda ke exit point, refleksi rute menghasilkan sudut pandang siklis yang saling membatalkan pemilihan best-path di masing-masing RR.
      
      *Perbaikan Arsitektur*:
      1. Mengaktifkan perintah `bgp deterministic-med` dan `bgp always-compare-med` secara seragam pada seluruh router di dalam AS.
      2. Menyelaraskan biaya metrik IGP internal dari kedua RR menuju edge exit point, atau menggunakan arsitektur BGP Add-Path (RFC 7911) sehingga RR tidak hanya mengiklankan 1 rute terbaik, melainkan beberapa alternatif jalur (*multiple paths*) ke client, mematahkan siklus osilasi.

13. **Skenario Kasus 3**:
    Perusahaan Anda baru saja mengaktifkan koneksi Direct-Peering di Internet Exchange Point (IXP). Beberapa menit setelah sesi peering Established dan Anda menerima ~10.000 prefix lokal, tiba-tiba seluruh sesi transit eBGP utama Anda (yang mengangkut Full Internet Route) diputus secara sepihak oleh ISP Transit Tier-1 Anda. Status peering Anda dinonaktifkan dengan pesan log:
    `%BGP-3-NOTIFICATION: sent to