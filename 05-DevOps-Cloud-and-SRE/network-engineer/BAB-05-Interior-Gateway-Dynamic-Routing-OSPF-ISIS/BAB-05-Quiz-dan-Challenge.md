# Evaluasi Pembelajaran Bab 05: Interior Gateway Dynamic Routing (OSPF & IS-IS)

---

## I. Basic Questions (5 Soal)

### Soal 1
Protokol transport apa dan nomor port/protokol berapa yang digunakan oleh OSPFv2 untuk mengirimkan paket-paket komunikasinya antar router?
- A. TCP Port 179
- B. UDP Port 520
- C. Raw IP Protocol 89
- D. UDP Port 646

**Kunci Jawaban:** C  
**Pembahasan:** OSPF tidak menggunakan protokol transport Layer 4 (seperti TCP atau UDP). OSPF dienkapsulasi langsung di dalam header IP (Layer 3) dengan Protocol Number 89. (Sebagai referensi: TCP 179 digunakan oleh BGP, UDP 520 oleh RIP, dan UDP 646 oleh LDP).

---

### Soal 2
Pada segmen jaringan Ethernet Broadcast, dua router DROther saling bertukar paket Hello dan mendeteksi Router ID satu sama lain di dalam paket tersebut. Adjacency state akhir yang stabil dan valid di antara kedua router DROther tersebut adalah:
- A. Down
- B. 2-Way
- C. Exchange
- D. Full

**Kunci Jawaban:** B  
**Pembahasan:** Pada network broadcast multi-access, router DROther hanya membentuk relasi `Full` dengan DR dan BDR. Komunikasi antar sesama router DROther berhenti pada state `2-Way`. Ini merupakan mekanisme OSPF by-design untuk mencegah full-mesh adjacency.

---

### Soal 3
Berapakah nilai default OSPF Reference Bandwidth pada implementasi standar Cisco IOS, dan apa konsekuensinya terhadap interface GigabitEthernet (1 Gbps) dan 10-GigabitEthernet (10 Gbps)?
- A. 1 Gbps; Cost GigE = 1, Cost 10GigE = 1
- B. 100 Mbps; Cost GigE = 1, Cost 10GigE = 1
- C. 10 Gbps; Cost GigE = 10, Cost 10GigE = 1
- D. 100 Gbps; Cost GigE = 100, Cost 10GigE = 10

**Kunci Jawaban:** B  
**Pembahasan:** Default reference bandwidth standar adalah 100 Mbps ($10^8$ bps). Rumus cost adalah $\text{Reference Bandwidth} / \text{Interface Bandwidth}$. Nilai cost minimum adalah bilangan bulat 1. Sehingga:
- FastEthernet (100M) = 100M / 100M = Cost 1
- GigabitEthernet (1000M) = 100M / 1000M = Cost 0.1 (dibulatkan menjadi 1)
- 10-GigabitEthernet (10000M) = Cost 1.  
Hal ini menyebabkan OSPF menganggap interface 100M, 1G, dan 10G memiliki beban/biaya yang sama persis jika reference bandwidth tidak diubah.

---

### Soal 4
Tipe LSA OSPFv2 manakah yang digunakan untuk mengiklankan rute eksternal di dalam area Not-So-Stubby Area (NSSA), dan tipe LSA apakah hasil konversinya saat diteruskan ke Area 0 oleh ABR?
- A. Type 5 dikonversi menjadi Type 3
- B. Type 7 dikonversi menjadi Type 5
- C. Type 1 dikonversi menjadi Type 2
- D. Type 7 dikonversi menjadi Type 3

**Kunci Jawaban:** B  
**Pembahasan:** NSSA melarang LSA Type 5 (AS External). Oleh karena itu, ASBR internal NSSA mengiklankan rute eksternal menggunakan LSA Type 7. Begitu LSA Type 7 mencapai router ABR, ABR menerjemahkannya (*Type-7-to-5 translation*) menjadi LSA Type 5 sebelum membanjirkannya ke Backbone Area 0.

---

### Soal 5
Pada layer manakah protokol IS-IS (Intermediate System to Intermediate System) beroperasi dalam model referensi OSI?
- A. Di atas Layer 3 IP Protocol 89
- B. Di atas Layer 4 TCP Port 500
- C. Langsung di atas Layer 2 Data Link (menggunakan encapsulation LLC/SNAP OSI CLNP)
- D. Di atas UDP Port 3784

**Kunci Jawaban:** C  
**Pembahasan:** Berbeda dengan OSPF yang berada di atas Layer 3 IP, IS-IS adalah protokol berbasis OSI Connectionless Network Protocol (CLNP) yang berjalan langsung di atas Layer 2 (Data Link encapsulation, SAP 0xFEFE). Hal ini menjadikan IS-IS independen dari layer IP itu sendiri.

---

## II. Intermediate Questions (5 Soal)

### Soal 1
Perhatikan skenario berikut:
Router A (RID: 1.1.1.1) terhubung ke Router B (RID: 2.2.2.2) via interface GigabitEthernet0/0.
Keduanya berada di OSPF Area 0.
Pada Router A, MTU interface disetel ke 1500 byte.
Pada Router B, MTU interface diubah menjadi 9000 byte (Jumbo Frame).
Perintah `ip ospf mtu-ignore` TIDAK diaktifkan.
Apa yang akan terjadi pada status OSPF Adjacency kedua router? Jelaskan alur kegagalannya!

**Kunci Jawaban & Pembahasan:**
Status adjacency akan terhenti (*stuck*) di **ExStart/Exchange**.
- Alur kegagalan:
  1. Router A dan Router B berhasil melewati fase `Down -> Init -> 2-Way` karena paket OSPF Hello berukuran kecil (< 1500 byte) sehingga dapat lewat dua arah.
  2. Masuk ke state `ExStart`, kedua router menegosiasikan Master/Slave via paket DBD kosong.
  3. Saat masuk ke fase pertukaran data LSDB (state `Exchange`), Router B (MTU 9000) mengirimkan paket DBD yang berisi daftar LSA header dengan ukuran paket melebihi 1500 byte (misal 4000 byte).
  4. Interface Router A (MTU 1500) akan secara fisik me-reject/drop paket DBD tersebut karena *oversized* (melebihi MTU fisik ingress).
  5. Router A tidak pernah menerima DBD utuh, sehingga tidak bisa membalas dengan ack/LSR. Akibatnya Router B akan melakukan retransmisi terus-menerus hingga batas dead timer, atau kedua router tertahan abadi di ExStart/Exchange.

---

### Soal 2
Jelaskan perbedaan mendasar fungsi perintah route summarization berikut pada router Cisco/FRR:
1. `area 1 range 10.1.0.0 255.255.0.0`
2. `summary-address 10.1.0.0 255.255.0.0`

**Kunci Jawaban & Pembahasan:**
- `area <id> range`: Dikonfigurasikan di **ABR (Area Border Router)** untuk meringkas rute internal OSPF (LSA Type 1 dan Type 2 yang berasal dari Area `<id>`) menjadi satu LSA Type 3 Summary sebelum diteruskan ke area OSPF lainnya.
- `summary-address`: Dikonfigurasikan di **ASBR (Autonomous System Boundary Router)** untuk meringkas rute eksternal hasil redistribusi (misal dari BGP, Static, atau protokol lain) sebelum diinjeksikan sebagai satu LSA Type 5 (atau Type 7 pada NSSA) ke dalam domain OSPF. Perintah ini tidak memiliki pengaruh terhadap LSA Type 1, 2, atau 3.

---

### Soal 3
Bagaimana algoritma pemilihan Designated Router (DR) menangani router baru yang masuk ke jaringan (*preemption mechanism*)? Jika sebuah router OSPF baru dengan prioritas interface `255` dinyalakan pada switch LAN yang sudah memiliki DR aktif (prioritas `1`) dan BDR aktif (prioritas `1`), apakah router baru tersebut akan langsung merebut posisi DR? Mengapa?

**Kunci Jawaban & Pembahasan:**
**TIDAK**, router baru tersebut tidak akan merebut posisi DR (*OSPF DR election is strictly non-preemptive*).
- **Alasan**: OSPF memprioritaskan stabilitas jaringan di atas determinasi prioritas numerik. Mengganti DR pada production network akan memaksa seluruh router di LAN mereset sesi adjacency mereka dari `Full` menjadi `2-Way` lalu negosiasi ulang ke `Full` dengan DR baru. Hal ini akan memicu LSA flooding massal dan SPF calculation ulang yang dapat menimbulkan interupsi forwarding traffic (*micro-outage*).
- Router baru tersebut hanya akan menjadi DROther. Router baru baru bisa menjadi DR jika DR dan BDR eksisting keduanya di-restart, dimatikan (*shutdown*), atau proses OSPF-nya di-clear secara manual.

---

### Soal 4
Sebutkan 3 alasan teknis mengapa arsitektur Tier-1 ISP Backbone dan Hyperscale Cloud Provider lebih memilih **IS-IS** dibanding OSPF sebagai Underlay Routing Protocol!

**Kunci Jawaban & Pembahasan:**
1. **Extensibility Berbasis TLV (Type-Length-Value)**: Format paket IS-IS tersusun atas modul-modul TLV. Penambahan fitur mutakhir (seperti IPv6 Multi-Topology, Segment Routing SR-MPLS/SRv6, dan Traffic Engineering) dapat diimplementasikan hanya dengan mendefinisikan TLV baru tanpa merombak core protocol. Sementara pada OSPF, penambahan IPv6 mengharuskan pembuatan protokol baru dari nol (OSPFv3).
2. **Enkapsulasi Layer 2 (Bukan IP)**: IS-IS dienkapsulasi langsung di Layer 2 (Data Link). Hal ini membuat IS-IS sepenuhnya kebal terhadap serangan IP spoofing, serangan denial of service berbasis IP Layer 3, dan tidak terpengaruh oleh miskonfigurasi IP routing/filtering di kontrol router.
3. **Efisiensi Skalabilitas & CPU**: Desain area IS-IS menempatkan perbatasan area pada link, bukan di dalam router. Router IS-IS Level-2 murni memiliki LSDB yang ringkas dan algoritma PRS (Partial Route Calculation) yang sangat efisien untuk memproses puluhan ribu rute tanpa membebani kontrol memori dan CPU router backbone.

---

### Soal 5
Pada OSPFv3 (RFC 5340 untuk IPv6), mengapa LSA Type 1 dan Type 2 tidak lagi membawa alamat network/prefix seperti halnya pada OSPFv2? Mekanisme apa yang digunakan OSPFv3 untuk membawa prefix tersebut?

**Kunci Jawaban & Pembahasan:**
- Pada OSPFv3, arsitektur protokol dirancang dengan memisahkan secara ketat antara **Topologi Graf Jaringan** dan **Addressing Information (Prefix)** (*Topology and Addressing decoupling*).
- LSA Type 1 (Router) dan Type 2 (Network) pada OSPFv3 murni hanya membawa topologi node ID (Router ID 32-bit), status link, dan metric antar router untuk kalkulasi Shortest Path Tree.
- Pengumuman IPv6 Prefix dialihkan sepenuhnya ke tipe LSA baru:
  - **LSA Type 9 (Intra-Area-Prefix LSA)**: Mengasosiasikan daftar prefix IPv6 ke Router LSA atau Network LSA.
  - **LSA Type 8 (Link LSA)**: Mengumumkan IPv6 Link-Local address milik router kepada neighbor langsung di link tersebut.
- **Tujuan Arsitektur**: Jika sebuah interface menambah, menghapus, atau mengubah subnet IP-nya, router hanya perlu meng-update dan membanjiri LSA Type 9 (kalkulasi *Partial Route Calculation* sederhana tanpa menghitung ulang Dijkstra SPF graf). Full SPF hanya dijalankan jika fisik topologi (LSA 1/2) benar-benar putus atau berubah.

---

## III. Scenario-Based Questions (3 Kasus Nyata)

### Kasus 1: "The Ghost Subnet and Micro-Loop Outage"
- **Konteks**: Sebuah perusahaan e-commerce memiliki ABR yang menghubungkan Area 1 (Branch Stores) ke Area 0 (Data Center Core). ABR dikonfigurasi perintah:
  `area 1 range 10.1.0.0 255.255.0.0`
- **Insiden**: Di dalam Area 1, subnet fisik yang ada hanyalah `10.1.1.0/24`, `10.1.2.0/24`, dan `10.1.3.0/24`. Suatu hari, sistem monitoring melaporkan lonjakan utilisasi link trunk Core-to-ABR hingga 100% dan ribuan paket drop. Analisis packet capture menunjukkan ribuan paket UDP serangan diarahkan ke alamat IP acak yang tidak pernah ada: `10.1.99.55`.
- Paket dari Core dikirim ke ABR (mengikuti rute summary `10.1.0.0/16`). Namun, sesampainya di ABR, paket tersebut justru dikirimkan kembali ke Core Router, lalu dikembalikan lagi ke ABR hingga TTL bernilai 0 (*Micro-routing Loop*).
- **Pertanyaan**:
  1. Mengapa micro-loop tersebut dapat terbentuk antara Core Router dan ABR?
  2. Mekanisme pengaman apa pada OSPF yang seharusnya secara otomatis aktif untuk mencegah skenario ini, dan apa kemungkinan penyebab mekanisme ini tidak berfungsi?
  3. Tuliskan langkah perbaikan deterministik untuk mengeliminasi loop tersebut secara permanen!

**Solusi & Analisis Rekayasa:**
1. **Penyebab Micro-Loop**:
   Core Router memiliki rute summary `10.1.0.0/16` dengan next-hop ABR. Ketika Core menerima paket untuk `10.1.99.55`, Core meneruskannya ke ABR. ABR memeriksa routing table lokalnya. Karena subnet `10.1.99.0/24` tidak ada di Area 1, ABR mencocokkan paket tersebut dengan **Default Route (`0.0.0.0/0`)** miliknya yang mengarah kembali ke Core Router. Core Router kembali mencocokkan paket dengan rute summary `10.1.0.0/16` (karena *Longest Prefix Match*: /16 lebih spesifik dari /0) dan melemparkannya kembali ke ABR. Terjadilah loop bolak-balik hingga IP TTL habis.
2. **Mekanisme Pengaman yang Hilang**:
   Secara default, saat perintah `area range` dieksekusi, OSPF akan secara otomatis menginjeksi sebuah rute lokal ke interface penampung sampah: `Null0` (Discard Route):
   `S 10.1.0.0/16 is directly connected, Null0`
   Penyebab mekanisme ini gagal biasanya adalah administrator mematikan discard-route secara eksplisit via perintah:
   `no discard-route internal` atau router OS memiliki bug/miskonfigurasi administrative distance rute default statis yang meng-override discard route.
3. **Langkah Perbaikan**:
   - Pastikan discard-route aktif di ABR:
     ```text
     router ospf 1
      discard-route internal
     ```
   - Atau pasang route statis pengaman manual ber-metric tinggi ke Null0:
     ```text
     ip route 10.1.0.0 255.255.0.0 Null0 254
     ```
   Dengan adanya rute ke `Null0`, ketika paket menuju IP hantu `10.1.99.55` masuk ke ABR, paket langsung di-drop seketika di memory hardware (*blackholed*), mencegah paket mental kembali ke Core Router.

---

### Kasus 2: "The Flapping Backbone & Stuck Adjacency Crisis"
- **Konteks**: Di sebuah Core ISP, dua router Arista EOS (Core-1 dan Core-2) dihubungkan melalui Metro-Ethernet link 10Gbps. Router mengaktifkan OSPFv2.
- **Gejala**: Setiap kali dilakukan backup data besar-besaran antar Data Center pada tengah malam, OSPF neighbor antara Core-1 dan Core-2 mendadak reset (*flapping*), status router berulang-ulang: `FULL -> DOWN -> INIT -> EXSTART -> DOWN`. Traffic pelanggan mengalami RTT melonjak dan packet loss parah.
- **Investigasi Log**:
  Log mencatat: `%OSPF-5-ADJCHANGE: Process 1, Nbr 10.255.0.2 on Ethernet1 from FULL to DOWN, Neighbor Down: Dead timer expired`
- **Pertanyaan**:
  1. Mengapa link saturation akibat traffic data pelanggan dapat menyebabkan OSPF Dead Timer expired padahal interface fisik tidak pernah putus (*link state remained UP*)?
  2. Solusi arsitektur dan kontrol QoS apa yang wajib diterapkan pada Control Plane untuk menjamin stabilitas adjacency OSPF dalam kondisi link terutilisasi 100%?

**Solusi & Analisis Rekayasa:**
1. **Analisis Akar Masalah**:
   Ketika link 10Gbps jenuh (congested 100%), antrean buffer egress pada interface fisik mengalami *tail drop*. OSPF Hello packet dikirimkan sebagai paket IP standar (Differentiated Services Code Point / DSCP default CS0 atau tidak diprioritaskan). Paket OSPF Hello ikut terbuang di antrean buffer port bersama traffic file transfer raksasa tersebut. Karena 4 paket Hello berturut-turut (Dead Interval = 40 detik) di-drop oleh switch/interface buffer, Dead Timer pada neighbor habis (*expired*), memicu penutupan paksa status OSPF.
2. **Solusi Arsitektur**:
   - **Control Plane Policing (CoPP) & Egress QoS Shaping**:
     Konfigurasikan queue khusus berprioritas tinggi (*Strict Priority Queue*) untuk control-plane traffic. Tandai paket OSPF (IP Protocol 89) dengan nilai DSCP **CS6** (Network Control) atau **DSCP 48**:
     ```text
     ip access-list CONTROL-PLANE-TRAFFIC
      permit ospf any any
     !
     class-map match-any CRITICAL-ROUTING
      match access-group name CONTROL-PLANE-TRAFFIC
     !
     policy-map EGRESS-EDGE-QOS
      class CRITICAL-ROUTING
       priority level 1
     ```
   - **Gunakan BFD Hardware Offload**: Aktifkan BFD (Bidirectional Forwarding Detection) yang berjalan langsung pada hardware ASIC/Network Processing Unit (NPU), independen dari utilisasi CPU router.

---

### Kasus 3: "The OSPF-to-BGP Redundancy Asymmetry"
- **Konteks**: Kantor Pusat Enterprise memiliki 2 ABR/ASBR (Border-1 dan Border-2) yang terhubung ke MPLS Provider via eBGP (AS 65000), dan terhubung ke internal Core via OSPF Area 0.
- Kedua router Border menerima rute default `0.0.0.0/0` via eBGP dari ISP dan menginjeksikannya ke dalam OSPF menggunakan perintah:
  `default-information originate metric-type 1` pada Border-1
  `default-information originate metric-type 2` pada Border-2
- **Masalah**: Seluruh traffic keluar Internet dari 50 router cabang di Area 1 selalu melewati Border-1. Bahkan ketika link Internet di Border-1 mengalami degradasi tinggi (namun belum mati total), traffic tetap tidak pernah beralih ke Border-2.
- **Pertanyaan**:
  1. Jelaskan perbedaan esensial antara OSPF External Metric **Type 1 (E1)** dan **Type 2 (E2)**!
  2. Mengapa Border-2 tidak pernah dipilih