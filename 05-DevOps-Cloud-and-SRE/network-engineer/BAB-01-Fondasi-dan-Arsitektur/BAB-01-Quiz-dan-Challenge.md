# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Arsitektur Jaringan, Model Referensi, & Datapath Produksi**

---

## 1. Basic Questions (5 Soal)

### Soal 1.1: Pemetaan Layer OSI vs TCP/IP & Mekanisme PDU Enkapsulasi
Jelaskan pemetaan antara model 7-Layer OSI (ISO/IEC 7498-1) dengan model 4-Layer TCP/IP (RFC 1122), sebutkan nama *Protocol Data Unit* (PDU) pada masing-masing layer (L2 hingga L7), dan uraikan urutan metadata (header dan trailer) yang disematkan saat data bergerak dari *Application Layer* menuju kabel fisik (*Physical Media*)!

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Pemetaan Layer OSI ke TCP/IP**:
  - **OSI Layer 7 (Application), Layer 6 (Presentation), Layer 5 (Session)** dikonsolidasikan menjadi **Application Layer** pada model TCP/IP. Menangani logika aplikasi, representasi data/enkripsi (TLS), dan abstraksi sesi koneksi.
  - **OSI Layer 4 (Transport)** dipetakan secara identik ke **Transport Layer** (TCP, UDP, SCTP). Bertanggung jawab atas *process-to-process delivery*, *port multiplexing*, *flow control*, dan *reliability*.
  - **OSI Layer 3 (Network)** dipetakan ke **Internet Layer** (IPv4, IPv6, ICMP). Bertanggung jawab atas *logical addressing*, *host-to-host routing*, dan fragmentasi.
  - **OSI Layer 2 (Data Link) & Layer 1 (Physical)** dikonsolidasikan menjadi **Link / Network Interface Layer** (Ethernet, 802.1Q, Wi-Fi, PHY transceiver). Menangani *media access control* (MAC), *framing*, *error detection* (CRC), dan transmisi sinyal biner.

- **Nomenklatur PDU (Protocol Data Unit)**:
  - Layer 7-5: **Data / Message / Payload / Stream**
  - Layer 4: **Segment** (TCP) atau **Datagram** (UDP)
  - Layer 3: **Packet** (IP)
  - Layer 2: **Frame** (Ethernet)
  - Layer 1: **Bits / Symbols** (Physical signalling)

- **Urutan Enkapsulasi (*Outbound Datapath*)**:
  1. *Application* menghasilkan raw bytes (misal: HTTP/2 request payload).
  2. *Transport Layer* menambahkan TCP Header (minimum 20 byte: Source/Destination Port, Sequence/Ack Number, Flags, Window Size, Checksum). Menghasilkan **TCP Segment**.
  3. *Internet Layer* menambahkan IPv4 Header (minimum 20 byte: Source/Destination IP, TTL, Protocol ID 6 untuk TCP, Total Length, Flags DF/MF). Menghasilkan **IP Packet**.
  4. *Data Link Layer* menambahkan Ethernet II Header di bagian depan (14 byte: Preamble/SFD ditangani PHY, Destination MAC, Source MAC, EtherType `0x0800` untuk IPv4) serta menyematkan **Frame Check Sequence (FCS)** 4 byte di bagian ekor (trailer CRC-32). Menghasilkan **Ethernet Frame**.
  5. *Physical Layer* mengonversi seluruh frame menjadi modulasi tegangan listrik, pulsa cahaya (fiber), atau gelombang elektromagnetik.
</details>

---

### Soal 1.2: Anatomi Header TCP & TCP 3-Way Handshake
Uraikan urutan pertukaran flag dan kalkulasi *Sequence/Acknowledgment Number* pada proses pembentukan koneksi TCP (*TCP 3-Way Handshake*). Mengapa inisiasi nomor urut (*Initial Sequence Number* / ISN) harus diacak secara kriptografis (*pseudo-random*) alih-alih dimulai dari angka nol (`0`)?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Urutan 3-Way Handshake**:
  1. **Langkah 1 (SYN dari Client ke Server)**:
     - Client memilih Initial Sequence Number acak: $ISN_C$.
     - Client mengirim segment TCP dengan flag `SYN = 1`, `ACK = 0`.
     - Header: `Seq = ISN_C`, `Ack = 0`. Status Client berubah menjadi `SYN-SENT`.
  2. **Langkah 2 (SYN-ACK dari Server ke Client)**:
     - Server menerima SYN, mengalokasikan Transmission Control Block (TCB), dan memilih Initial Sequence Number server: $ISN_S$.
     - Server membalas dengan flag `SYN = 1`, `ACK = 1`.
     - Header: `Seq = ISN_S`, `Ack = ISN_C + 1` (mengkonsumsi 1 phantom byte dari SYN). Status Server berubah menjadi `SYN-RECEIVED`.
  3. **Langkah 3 (ACK dari Client ke Server)**:
     - Client menerima SYN-ACK dan mengirim konfirmasi akhir dengan flag `ACK = 1`, `SYN = 0`.
     - Header: `Seq = ISN_C + 1`, `Ack = ISN_S + 1`.
     - Status Client dan Server berubah menjadi `ESTABLISHED`. Data payload sudah dapat dikirimkan bersamaan dengan segmen ini.

- **Alasan Pengacakan ISN (RFC 6528)**:
  - **Mitigasi Serangan TCP Sequence Number Prediction & Blind Hijacking**: Jika ISN dapat diprediksi (misal: increment statis berbasis waktu atau selalu mulai dari 0), penyerang off-path dapat memalsukan (*spoof*) IP address pengirim terpercaya, menebak nilai `Seq` dan `Ack` yang tepat, lalu menyuntikkan perintah berbahaya (*data injection*) atau memutus koneksi via RST tanpa perlu melihat paket asli.
  - **Mencegah Tabrakan Segmen Lama (*Stale/Ghost Segments*)**: Jika port TCP yang sama digunakan kembali segera setelah koneksi ditutup (*fast-recycled 4-tuple*), paket lama yang terlambat di internet (*delayed duplicate packets*) tidak akan dianggap sebagai data valid pada koneksi baru jika ISN-nya berada di luar window transmisi saat ini.
</details>

---

### Soal 1.3: Formula Kalkulasi MTU, MSS, dan Overhead Enkapsulasi
Sebuah host terhubung ke jaringan Ethernet standar dengan Maximum Transmission Unit (MTU) sebesar 1500 byte. Hitung nilai Maximum Segment Size (MSS) efektif TCP untuk dua kondisi berikut:
1. Koneksi standar IPv4 murni tanpa opsi IP/TCP tambahan.
2. Koneksi yang melintasi enkapsulasi tag IEEE 802.1Q (VLAN tunggal) dan tunnel VXLAN standar (Header: Outer Ethernet 14 byte, Outer IPv4 20 byte, UDP 8 byte, VXLAN 8 byte).

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Definisi Dasar**:
  - $\text{MTU}$ adalah ukuran maksimal payload Layer 3 (IP Packet termasuk header IP dan payload L4) yang dapat ditransmisikan tanpa fragmentasi pada antarmuka L2 fisik.
  - $\text{MSS} = \text{MTU} - (\text{Panjang Header IP} + \text{Panjang Header TCP})$.

- **Kasus 1: IPv4 Standar Tanpa Opsi Tambahan**:
  - Header IPv4 dasar = 20 byte.
  - Header TCP dasar = 20 byte.
  - $\text{Overhead L3/L4} = 20 + 20 = 40 \text{ byte}$.
  - $\text{MSS Efektif} = 1500 - 40 = \mathbf{1460 \text{ byte}}$.

- **Kasus 2: Enkapsulasi 802.1Q dan VXLAN**:
  - **Analisis 802.1Q**: Tag VLAN 802.1Q (4 byte) berada pada Layer 2 (antara Source MAC dan EtherType). Tag ini menambah ukuran Ethernet Frame fisik (menjadi 1522 byte jika mendukung baby giant frames) dan **tidak mengurangi** kapasitas payload L3 MTU 1500 byte jika switch dikonfigurasi dengan MTU L2 1504/1522 byte. Namun, jika uplink fisik terkunci ketat di 1500 byte total L2: MTU L3 terpangkas 4 byte (1496 byte).
  - **Overhead Tunnel VXLAN**:
    - Outer IP Header: 20 byte
    - Outer UDP Header (Port 4789): 8 byte
    - VXLAN Header (termasuk VNI 24-bit): 8 byte
    - Inner Ethernet Header (Host payload frame): 14 byte
    - Total Overhead Enkapsulasi VXLAN pada paket IP asli = $20 + 8 + 8 + 14 = \mathbf{50 \text{ byte}}$.
  - **Kalkulasi MTU & MSS Inner/Host**:
    - Jika physical transport underlay memiliki MTU 1500 byte:
      - $\text{Inner MTU Maksimal} = 1500 - 50 = 1450 \text{ byte}$.
      - $\text{MSS Efektif Inner TCP} = 1450 - (\text{Inner IPv4 20 byte} + \text{Inner TCP 20 byte}) = \mathbf{1410 \text{ byte}}$.
    - *Catatan Produksi*: Inilah alasan jaringan Datacenter underlay yang menjalankan EVPN-VXLAN wajib mengaktifkan **Jumbo Frames** (MTU $\ge 1600$ byte, umumnya 9000 atau 9216 byte) agar inner frame host tetap dapat memanfaatkan MTU penuh 1500 byte ($\text{MSS } 1460$) tanpa fragmentasi.
</details>

---

### Soal 1.4: Fungsi ARP dan Siklus Resolusi L2/L3 pada Komunikasi Antar-Subnet
Host A (`192.168.10.5/24`, MAC `00:50:56:AA:01:01`) ingin mengirim data ke Host B (`192.168.20.10/24`, MAC `00:50:56:BB:02:02`) melalui Default Gateway Router R1 (Interface LAN A: `192.168.10.1`, MAC `00:50:56:FF:11:11`; Interface LAN B: `192.168.20.1`, MAC `00:50:56:FF:22:22`).
Jelaskan frame Ethernet yang keluar dari Host A: alamat IP asal/tujuan apa yang tertulis di Header IP, dan alamat MAC asal/tujuan apa yang tertulis di Header Ethernet? Kapan protokol ARP dipanggil dan terhadap alamat IP mana?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Logika Keputusan Routing Host A**:
  1. Host A mengevaluasi IP tujuan `192.168.20.10` terhadap subnet mask lokalnya (`/24` atau `255.255.255.0`).
  2. Hasil operasi bitwise: `(192.168.10.5 & 255.255.255.0) != (192.168.20.10 & 255.255.255.0)`.
  3. Host A menyimpulkan bahwa Host B berada di **luar subnet lokal** (remote network).
  4. Berdasarkan routing table Host A, paket harus diarahkan ke *Next-Hop Gateway*, yaitu `192.168.10.1`.

- **Pemanggilan Protokol ARP**:
  - Host A **tidak melakukan ARP request** untuk IP Host B (`192.168.20.10`) karena broadcast L2 tidak melintasi router.
  - Host A memeriksa ARP Cache lokal untuk IP Default Gateway (`192.168.10.1`).
  - Jika belum ada, Host A mengirimkan *ARP Request Broadcast* (`FF:FF:FF:FF:FF:FF`) menanyakan: *"Who has 192.168.10.1? Tell 192.168.10.5"*.
  - Router R1 merespons dengan *ARP Reply Unicast* berisi MAC `00:50:56:FF:11:11`.

- **Anatomi Paket & Frame yang Keluar dari Interface Host A**:
  - **Layer 3 (IP Header)**:
    - *Source IP*: `192.168.10.5` (IP asli Host A)
    - *Destination IP*: `192.168.20.10` (IP akhir Host B)
    - *Kaidah*: IP Header bersifat end-to-end dan **tidak berubah** saat melintasi router standar (non-NAT).
  - **Layer 2 (Ethernet Header)**:
    - *Source MAC*: `00:50:56:AA:01:01` (MAC interface Host A)
    - *Destination MAC*: `00:50:56:FF:11:11` (**MAC Gateway R1**, BUKAN MAC Host B)
    - *EtherType*: `0x0800` (IPv4)
    - *Kaidah*: MAC Header bersifat hop-by-hop dan di-*rewrite* oleh setiap router transit sepanjang jalur.
</details>

---

### Soal 1.5: Perbedaan NIC Offloading TSO dan GRO
Jelaskan perbedaan mendasar antara mekanisme akselerasi hardware NIC: **TCP Segmentation Offload (TSO)** pada sisi transmisi (TX) dan **Generic Receive Offload (GRO)** pada sisi penerimaan (RX). Apa keuntungan pengaktifan kedua fitur ini terhadap utilisasi CPU host pada throughput 10 Gbps ke atas?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **TCP Segmentation Offload (TSO) - TX Path**:
  - *Mekanisme*: Kernel TCP stack tidak memecah payload besar menjadi paket-paket berukuran MTU (1500 byte). Sebaliknya, kernel membuat satu unit buffer data besar (*super-packet* hingga 64 KB) beserta template header TCP/IP, lalu menyerahkannya langsung ke Network Interface Card (NIC).
  - *Peran Hardware*: ASIC pada NIC memotong data tersebut menjadi segment-segment kecil ($\le \text{MSS}$), menghitung checksum IP dan TCP secara mandiri di hardware, menambahkan nomor sequence TCP yang sesuai untuk tiap segment, dan mengirimkannya ke kabel fisik.

- **Generic Receive Offload (GRO) - RX Path**:
  - *Mekanisme*: Ketika rentetan paket dari aliran (*flow*) TCP yang sama masuk secara berurutan pada ring buffer, driver jaringan/NAPI menggabungkan (*coalesce*) payload dari segment-segment tersebut ke dalam satu struktur `sk_buff` besar sebelum dioperasikan ke sub-sistem IP/TCP kernel.
  - *Peran Perangkat Lunak/Driver*: Menyerahkan satu paket berukuran besar ke layer transport daripada puluhan paket kecil, sehingga pemrosesan header, traversal routing table, dan firewall rules hanya terjadi sekali untuk aliran byte tersebut.

- **Keuntungan Performa pada Throughput Tinggi ($\ge 10\text{ Gbps}$)**:
  - **Reduksi Beban CPU & Interupsi**: Pada kecepatan 10 Gbps (sekitar 812.000 frame per detik untuk paket 1500 byte), overhead pemrosesan alokasi memori `sk_buff`, context switching, dan eksekusi stack TCP/IP per-paket dapat menghabiskan 100% utilisasi satu core CPU hanya untuk networking.
  - **Efisiensi Cache CPU (L1/L2/L3)**: Dengan TSO dan GRO, jumlah traversal `sk_buff` melewati fungsi kernel berkurang hingga $10\times - 40\times$. Hal ini menjaga instruction cache dan data cache CPU tetap optimal, melipatgandakan throughput efektif per socket.
</details>

---

## 2. Intermediate Questions (5 Soal)

### Soal 2.1: Datapath Kernel Linux dari Hard IRQ, NAPI, SoftIRQ, hingga `sk_buff`
Uraikan secara kronologis datapath pemrosesan paket pada Linux Kernel saat sebuah frame Ethernet tiba pada port fisik NIC hingga data siap dibaca oleh aplikasi via `recv()` socket. Mengapa transisi dari *Interrupt-driven* ke *NAPI Polling Loop* via `NET_RX_SOFTIRQ` diperlukan untuk mencegah fenomena *Receive Livelock*?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Kronologi Eksekusi Datapath**:
  1. **NIC RX FIFO & DMA Transfer**: Frame fisik tiba di port NIC, divalidasi integritas FCS-nya, lalu disalin secara asinkron via PCI Express bus (Direct Memory Access / DMA) ke area memori host yang dipetakan oleh *RX Ring Buffer Descriptors*.
  2. **Hard IRQ (Hardware Interrupt)**: NIC memicu interupsi hardware (MSI-X) ke CPU core yang ditugaskan oleh IRQ affinity.
  3. **Interrupt Handler & Penjadwalan NAPI**: CPU menghentikan instruksi thread pengguna saat ini, mengeksekusi top-half ISR. Top-half menonaktifkan interupsi hardware untuk queue tersebut guna menghindari badai interupsi (*interrupt storm*), memanggil fungsi `napi_schedule()`, menyisipkan struktur NAPI ke antrean `poll_list` CPU lokal, lalu membangkitkan software interrupt `NET_RX_SOFTIRQ`.
  4. **Bottom-Half Execution (`ksoftirqd` / SoftIRQ)**: Sub-sistem kernel mengeksekusi fungsi polling driver (misal: `napi_gro_receive` atau `napi_poll`).
  5. **eBPF/XDP Hook**: Jika ada program XDP (eXpress Data Path) terpasang di driver, program dieksekusi langsung pada raw packet descriptor. Paket dapat segera di-drop (`XDP_DROP`), dikirim balik (`XDP_TX`), dialihkan (`XDP_REDIRECT`), atau dilanjutkan ke kernel stack (`XDP_PASS`).
  6. **Alokasi `sk_buff`**: Driver mengalokasikan Socket Buffer (`sk_buff`), memetakan pointer data, dan memanggil `netif_receive_skb()`.
  7. **Netfilter / Conntrack**: Paket melewati hook `PREROUTING`, dimonitor oleh stateful connection tracker (`nf_conntrack`), dan dievaluasi terhadap tabel routing L3 (`ip_route_input_noref`).
  8. **Transport Layer & Socket Queue**: Jika paket ditujukan untuk host lokal (`LOCAL_IN`), fungsi `ip_local_deliver()` mengevaluasi hook `INPUT` dan memanggil handler L4 (`tcp_v4_rcv`). TCP memverifikasi checksum, memeriksa sequence number, mengirimkan ACK, dan menyisipkan data payload ke *Socket Receive Queue*.
  9. **Userspace Wakeup**: Kernel membangunkan proses aplikasi pengguna yang sedang blocking di syscall `epoll_wait()`, `read()`, atau `recv()`.

- **Pencegahan Receive Livelock melalui NAPI**:
  - *Definisi Receive Livelock*: Kondisi di mana CPU menghabiskan 100% siklus instruksinya hanya untuk menangani interupsi hardware (top-half) akibat banjir jutaan paket per detik. Akibatnya, CPU tidak pernah memiliki sisa waktu untuk mengeksekusi bottom-half (SoftIRQ) apalagi proses pengguna di userspace. Seluruh paket yang masuk akhirnya tetap di-drop di buffer sementara sistem hang total.
  - *Solusi NAPI (New API)*: NAPI mengubah model pemrosesan dari reaktif (*interrupt-driven*) menjadi periodik (*polling-driven*) saat lalu lintas padat. Sekali interupsi diterima, interupsi dimatikan dan kernel mengambil batch paket (default: `budget = 64` paket per poll) secara terkontrol hingga ring buffer kosong, baru kemudian mengaktifkan kembali interupsi hardware.
</details>

---

### Soal 2.2: Mekanisme Path MTU Discovery (PMTUD) dan Fenomena *PMTUD Black Hole*
Jelaskan cara kerja protokol *Path MTU Discovery* (RFC 1191 / RFC 8201) dalam menentukan ukuran transmisi paket maksimum antara dua host di internet. Mengapa konfigurasi firewall yang memblokir seluruh pesan ICMP secara membabi buta dapat menciptakan anomali *PMTUD Black Hole*, dan bagaimana mitigasi daruratnya di layer network/firewall?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Mekanisme Path MTU Discovery (PMTUD)**:
  1. Host pengirim menginisiasi koneksi TCP dan menyetel bit **Don't Fragment (DF = 1)** pada header IPv4 di setiap paket yang dikirim.
  2. Host pengirim menggunakan MTU interface lokalnya (misal: 1500 byte) sebagai estimasi awal Path MTU (PMTU).
  3. Jika paket melintasi router perantara yang memiliki link keluar dengan MTU lebih kecil (misal: tunnel GRE/IPsec/PPPoE dengan MTU 1420 byte), router tidak dapat memfragmentasi paket karena `DF = 1`.
  4. Router transit terpaksa men-drop paket tersebut dan menghasilkan pesan balasan kontrol **ICMP Type 3, Code 4** (*Destination Unreachable: Fragmentation Needed and DF set*). Pesan ICMP ini memuat ukuran *Next-Hop MTU* link tersebut (misal: 1420 byte).
  5. Host pengirim menerima pesan ICMP tersebut, memperbarui routing cache lokal untuk tujuan tersebut dengan PMTU baru (1420 byte), dan mengirim ulang paket dengan ukuran yang telah disesuaikan ($\text{MSS} = 1420 - 40 = 1380$).

- **Penyebab PMTUD Black Hole**:
  - Banyak administrator jaringan atau ISP menerapkan aturan firewall defensif paranoid: `iptables -A INPUT -p icmp -j DROP` tanpa filter tipe.
  - Ketika pesan ICMP Type 3 Code 4 di-drop oleh firewall di sepanjang jalur kembali, host pengirim **tidak pernah tahu** bahwa paketnya berukuran terlalu besar.
  - *Gejala Anomali*: Sesi koneksi TCP 3-Way Handshake berhasil terbentuk dengan sempurna karena paket SYN/ACK berukuran kecil (< 100 byte). Namun, begitu transaksi data besar dimulai (misal: TLS Client Hello dengan certificate chain besar, query SQL panjang, atau HTTP POST/GET response), paket tertahan di router perantara. Klien mengalami *connection freeze / timeout* tanpa respons, sementara server terus melakukan retransmisi segment besar hingga connection reset (`ETIMEDOUT`).

- **Mitigasi Teknis di Layer Firewall / Gateway**:
  - **Solusi Benar (Izinkan ICMP Spesifik)**: Membuka secara eksplisit pesan ICMP kontrol fragmentasi:
    ```bash
    iptables -A INPUT -p icmp --icmp-type fragmentation-needed -j ACCEPT
    ```
  - **Mitigasi Darurat: TCP MSS Clamping**: Memanipulasi nilai MSS di dalam segmen SYN TCP yang melintasi router/gateway sebelum mencapai host, memaksa kedua endpoint bernegosiasi pada batas aman:
    ```bash
    iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
      -j TCPMSS --clamp-mss-to-pmtu
    # Atau set MSS manual ke nilai aman (misal 1360 untuk tunnel over internet):
    iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
      -j TCPMSS --set-mss 1360
    ```
</details>

---

### Soal 2.3: Arsitektur Datacenter Spine-Leaf Menggunakan BGP Unnumbered (RFC 5549)
Bandingkan arsitektur jaringan tradisional berbasis 3-Tier (Core-Aggregation-Access) dengan arsitektur 2-Tier Modern Spine-Leaf (Clos Network). Jelaskan bagaimana protokol **BGP Unnumbered** (RFC 5549 / RFC 8950) mengeliminasi kebutuhan alokasi ribuan subnet point-to-point `/30` atau `/31` IPv4 pada fabric datacenter skala masif!

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Perbandingan Arsitektur**:
  - **Tradisional 3-Tier (Core-Aggregation-Access)**:
    - Dirancang untuk dominasi lalu lintas *North-South* (klien eksternal ke server).
    - Sangat bergantung pada Spanning Tree Protocol (STP) di layer akses/agregasi untuk mencegah loop Layer 2. STP memblokir jalur redundan (mematikan hingga 50% kapasitas bandwidth link).
    - Bottleneck besar pada lalu lintas *East-West* (komunikasi antar microservices/database di dalam DC) karena harus melintasi aggregation/core layer berkali-kali.
  - **Spine-Leaf (Clos Arsitektur 2-Tier)**:
    - Topologi non-blocking yang dioptimalkan untuk lalu lintas *East-West*.
    - Setiap Leaf switch terhubung langsung ke **setiap** Spine switch. Tidak ada koneksi antar sesama Leaf atau sesama Spine.
    - Menghilangkan STP: Seluruh fabric berjalan murni pada Layer 3. Redundansi dan load balancing link ditangani oleh **Equal-Cost Multi-Path (ECMP)**, sehingga 100% bandwidth link aktif secara paralel dengan latensi deterministik (maksimal 3 hop intra-DC: Leaf1 $\to$ Spine $\to$ Leaf2).

- **Mekanisme BGP Unnumbered (RFC 5549 / RFC 8950)**:
  - *Masalah pada BGP Tradisional*: Pada fabric dengan 32 Spine dan 128 Leaf, terdapat $32 \times 128 = 4096$ link fisik point-to-point. Setiap link membutuhkan alokasi subnet IPv4 `/31` (8192 alamat IP unik), konfigurasi IP manual per interface, dan mapping peer IP BGP yang rawan kesalahan manusia (*IP address exhaustion* dan *management overhead*).
  - *Solusi RFC 5549*: BGP Unnumbered memanfaatkan kapabilitas BGP Multiprotocol Extensions (MP-BGP) untuk mengumumkan prefix IPv4 Network Layer Reachability Information (NLRI) dengan Next-Hop berupa alamat **IPv6 Link-Local** (`fe80::/64`).
  - *Operasional Praktis*:
    1. Interface fisik antar switch tidak diberi alamat IPv4 point-to-point statis sama sekali.
    2. IPv6 Link-Local address dikonfigurasi secara otomatis oleh kernel/switch berbasis EUI-64 atau acak pada setiap interface saat link UP.
    3. Switch saling bertukar router advertismen (IPv6 Neighbor Discovery Protocol) dan membentuk peering eBGP secara otomatis via interface name (misal: `neighbor swp1 interface remote-as external`).
    4. Seluruh rute IPv4 datacenter dialirkan melintasi peering tersebut dengan next-hop IPv6 Link-Local interface lokal. Kebutuhan alokasi subnet p2p IPv4 menjadi **nol**.
</details>

---

### Soal 2.4: EVPN-VXLAN: Perbedaan Symmetric IRB vs Asymmetric IRB
Dalam implementasi overlay network berbasis EVPN-VXLAN (RFC 7432 / RFC 8365), jelaskan perbedaan mekanisme routing dan bridging antar-subnet (inter-VLAN) antara model **Asymmetric Integrated Routing and Bridging (IRB)** dan **Symmetric IRB**. Mengapa arsitektur datacenter modern enterprise menstandardisasi Symmetric IRB dengan L3VNI?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Asymmetric Integrated Routing and Bridging (IRB)**:
  - *Mekanisme Transmisi*:
    - **Ingress Leaf (VTEP Asal)**: Melakukan proses *Routing* dari Subnet Sumber (VNI-A) ke Subnet Tujuan (VNI-B), lalu meng-enkapsulasi paket ke dalam frame VXLAN dengan VNI tujuan (VNI-B).
    - **Egress Leaf (VTEP Tujuan)**: Hanya bertindak sebagai bridge Layer 2 murni. Mendekapsulasi frame VXLAN dan langsung mem-forward frame ke interface lokal berdasarkan MAC address pada VNI-B.
  - *Karakteristik Jalur Balik*: Menggunakan jalur asimetris, di mana routing kembali terjadi di VTEP seberang dari VNI-B ke VNI-A.
  - *Kelemahan Fatal*: Setiap Leaf switch wajib mengonfigurasi dan menyimpan *state* seluruh VNI (L2VNI), seluruh ARP entry, dan seluruh MAC address dari semua tenant yang ada di seluruh fabric, bahkan jika Leaf tersebut tidak memiliki host yang tergabung dalam subnet tersebut. Hal ini menyebabkan ledakan memori TCAM/FIB (*FIB scale limit exhaustion*).

- **Symmetric Integrated Routing and Bridging (IRB)**:
  - *Mekanisme Transmisi*:
    - **Ingress Leaf (VTEP Asal)**: Melakukan routing dari Subnet Lokal (L2VNI-A) ke sebuah VNI khusus bernama **L3VNI (Tenant VRF Routed VNI)**. Frame dienkapsulasi dengan L3VNI dan dikirim melintasi underlay.
    - **Egress Leaf (VTEP Tujuan)**: Mendekapsulasi paket dari L3VNI, membaca routing table VRF internal, dan melakukan routing kedua dari L3VNI ke subnet tujuan lokal (L2VNI-B).
  - *Karakteristik*: Kedua VTEP sama-sama melakukan proses *Routing* dan *Bridging* secara simetris melalui perantara transit L3VNI.

- **Alasan Standardisasi Enterprise Menggunakan Symmetric IRB**:
  1. **Skalabilitas TCAM Optimal**: Leaf switch hanya perlu mengonfigurasi L2VNI yang aktif secara lokal di port-port fisiknya. Leaf tidak perlu mengetahui MAC/ARP dari subnet yang tidak terpasang padanya. Komunikasi antar-subnet cukup mengetahui rute IP prefix via L3VNI.
  2. **Isolasi Multi-Tenancy Bersih**: Setiap tenant dipetakan secara eksklusif ke satu L3VNI / VRF terisolasi di seluruh fabric datacenter, menyederhanakan segmentasi keamanan zero-trust dan microsegmentation.
  3. **Konfigurasi Deterministik**: Menghilangkan dependensi konfigurasi VLAN global yang rapuh, memungkinkan otomatisasi fabric berbasis NetDevOps/GitOps yang homogen.
</details>

---

### Soal 2.5: Transmit Hash Policy pada LACP (802.3ad) dan Fenomena *Hash Polarization*
Sebuah server database membagikan beban traffic-nya melalui Link Aggregation (LACP bonding mode 4) menggunakan dua interface fisik 10 Gbps. Jelaskan perbedaan *transmit hash policy* antara `layer2`, `layer2+3`, dan `layer3+4`. Apa yang dimaksud dengan fenomena **Hash Polarization** (juga dikenal sebagai *Traffic Skewing/Imbalance*) dan bagaimana cara mencegahnya?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Pilihan Transmit Hash Policy (`xmit_hash_policy`) di Linux Bonding**:
  - **`layer2` (Default)**:
    - *Formula*: $\text{Hash} = (\text{Source MAC} \oplus \text{Destination MAC}) \pmod N$
    - *Karakteristik*: Seluruh traffic yang menuju Default Gateway yang sama akan menghasilkan nilai hash yang **identik** karena Destination MAC-nya selalu MAC router. Akibatnya, seluruh traffic keluar hanya melewati satu kabel slave link, sementara slave link lainnya 0% utilisasi (sia-sia).
  - **`layer2+3`**:
    - *Formula*: $\text{Hash} = ((\text{Source MAC} \oplus \text{Destination MAC}) \oplus (\text{Source IP} \oplus \text{Destination IP})) \pmod N$
    - *Karakteristik*: Lebih baik untuk lingkungan routed karena memperhitungkan variasi IP klien tujuan. Namun, koneksi berulang ke server tujuan tunggal (misal: replikasi database ke satu host) tetap akan terkunci di satu link.
  - **`layer3+4`**:
    - *Formula*: Memperhitungkan IP Source/Destination dan TCP/UDP Source/Destination Port (RFC-compliant).
    - *Karakteristik*: Menyebarkan beban per-*flow* / per-koneksi soket individual. Sangat optimal untuk server web atau database yang menangani ribuan sesi konkuren simultan.

- **Fenomena Hash Polarization (Traffic Skewing)**:
  - *Penyebab*: Terjadi ketika beberapa tingkat perangkat jaringan berurutan dalam topologi (misal: Host Bond $\to$ ToR Leaf Switch LAG $\to$ Spine Switch ECMP) menggunakan algoritma hashing, seed matematika, dan input tuple yang persis sama.
  - *Dampak*: Pada switch tingkat pertama, traffic terbagi 50:50. Namun saat traffic mencapai switch tingkat kedua, fungsi hash yang identik memetakan seluruh paket yang tersisa hanya ke satu sisi link output (misal: link genap selalu terpilih, link ganjil kosong). Hal ini menciptakan kemacetan parah (*congested hot-spot link*) pada link tertentu, sementara link redundan lainnya menganggur.
  - *Solusi Pencegahan*:
    1. Menggunakan algoritma hash modern dengan penambahan *random salt / hash seed* yang berbeda pada setiap switch/host dalam jaringan.
    2. Menggunakan algoritma hashing berbasis CRC-16 atau universal hashing alih-alih operasi XOR sederhana.
    3. Mengaktifkan *Resilient Hashing* atau *Dynamic Load Balancing* (DLB) pada switch hardware ASIC (Broadcom Tomahawk/Trident).
</details>

---

## 3. Skenario Kasus Produksi (3 Kasus Nyata)

### Skenario A: The Silent TLS Handshake Freeze (PMTUD Black Hole saat Migrasi ke Overlay VXLAN)

#### 1. Konteks Masalah
Sebuah platform perbankan digital baru saja memigrasikan cluster microservices pembayaran mereka dari arsitektur VM tradisional (VLAN L2 murni) ke cluster Kubernetes bare-metal modern yang berjalan di atas overlay network EVPN-VXLAN. Antarmuka jaringan fisik server terhubung ke ToR Switch dengan MTU fisik standar 1500 byte. CNI plugin Kubernetes dikonfigurasi menggunakan mode enkapsulasi VXLAN.

#### 2. Gejala & Anomali
- Tim DevOps mengamati bahwa perintah `curl http://api.bank.internal/healthz` (payload kecil 120 byte) selalu sukses dengan status `HTTP 200 OK` secara instan.
- Pengujian koneksi dasar via `ping -c 4` antar Pod berjalan mulus tanpa paket hilang (0% loss, RTT 0.2 ms).
- Namun, ketika service klien melakukan transmisi data nyata menggunakan mutual TLS (mTLS) dengan payload JSON besar (10 KB) atau mengunggah payload settlement transaksi perbankan, koneksi tiba-tiba membeku (*hung indefinitely*). Klien tidak menerima data apa pun hingga timeout 60 detik (`504 Gateway Timeout` atau `SSL_ERROR_SYSCALL`).
- Hasil inspeksi `tcpdump` di interface virtual Pod menunjukkan segmen TCP SYN, SYN-ACK, ACK berhasil dipertukarkan, namun setelah segmen `TLS Client Hello` besar dikirimkan, tidak ada respons lanjutan dan server terus melakukan retransmisi TCP (*Spurious Retransmission*).

```
[Pod A (Client)] ─── SYN (len=0) ───────────────────> [Pod B (Service)] (OK)
[Pod A (Client)] <── SYN-ACK (len=0) ──────────────── [Pod B (Service)] (OK)
[Pod A (Client)] ─── ACK (len=0) ───────────────────> [Pod B (Service)] (OK)
[Pod A (Client)] ─── TLS Client Hello (len=1460) ───> [ToR / VTEP] ──x (DROPPED: Size=1550 > MTU 1500, DF=1)
[Pod A (Client)] ... Menunggu ACK (Freeze & Timeout) ...
```

#### 3. Pertanyaan Investigasi
1. Mengapa paket `ping` dan endpoint `/healthz` berfungsi normal, sedangkan transaksi mTLS membeku total?
2. Mengapa router transit/switch menjatuhkan (*drop*) paket data mTLS tersebut secara diam-diam tanpa memecahnya menjadi paket yang lebih kecil?
3. Rancang dua skenario solusi teknis: solusi arsitektur permanen pada underlay network dan solusi mitigasi segera di level Linux kernel/iptables!

<details>
<summary>Analisis Akar Masalah & Solusi Produksi</summary>

- **Akar Masalah (Root Cause Analysis)**:
  1. **Analisis Selektivitas Paket**: Paket `ping` (ICMP Echo) dan health check HTTP payload kecil memiliki ukuran frame L3 di bawah 300 byte. Setelah ditambah overhead enkapsulasi VXLAN sebesar 50 byte (Outer IP 20B + Outer UDP 8B + VXLAN 8B + Inner Eth 14B), total ukuran frame pada jaringan underlay hanya sekitar 350 byte, jauh di bawah MTU fisik 1500 byte, sehingga lolos tanpa hambatan.
  2. **Pelanggaran Batas MTU**: mTLS payload berukuran besar memaksa TCP memotong data pada batas MSS standar host (1460 byte), menghasilkan IP packet inner berukuran 1500 byte dengan bit Don't Fragment (`DF = 1`) aktif secara default oleh TCP stack Linux.
  3. Saat VTEP meng-enkapsulasi inner packet 1500 byte tersebut, outer packet membengkak menjadi **1550 byte**.
  4. Interface fisik underlay hanya memiliki MTU 1500 byte. Karena paket memiliki flag `DF = 1`, switch underlay men-drop paket tersebut. Jika switch underlay memblokir ICMP Type 3 Code 4 atau virtual tunnel interface tidak meneruskan pesan tersebut ke namespace Pod, Pod pengirim tidak pernah tahu bahwa paketnya terlalu besar (**PMTUD Black Hole**). Pod terus menunggu ACK yang tidak akan pernah datang.

- **Solusi 1: Solusi Arsitektur Permanen (Rekomendasi Industri)**:
  - Mengonfigurasi **Jumbo Frames** pada seluruh interface underlay network fisik (server NIC, ToR Leaf switches, dan Spine switches).
  - Ubah MTU fisik switch dan host interface menjadi minimal **9000 atau 9216 byte**:
    ```bash
    # Di server Linux Host Underlay:
    ip link set dev eth0 mtu 9000
    ```
  - Dengan underlay MTU 9000 byte, inner packet 1500 byte milik Pod yang ditambah enkapsulasi 50 byte VXLAN (total 1550 byte) dapat melintasi jaringan underlay dengan sangat lega tanpa risiko fragmentasi maupun drop.

- **Solusi 2: Solusi Mitigasi Cepat (Tanpa Mengubah Switch Fisik)**:
  - **Opsi A: Tuning MTU Interface CNI / Pod**:
    Ubah konfigurasi CNI plugin (misal: Calico, Cilium, Flannel) agar MTU interface virtual Pod (`veth` / `eth0`) diset ke **1450 byte** ($1500 - 50$ overhead VXLAN). Dengan demikian, TCP MSS Pod otomatis turun menjadi 1410 byte.
  - **Opsi B: TCP MSS Clamping via Netfilter/Iptables**:
    Pasang aturan MSS clamping pada node host/gateway untuk memotong nilai MSS negosiasi secara dinamis:
    ```bash
    iptables -t mangle -A POSTROUTING -p tcp --tcp-flags SYN,RST SYN \
      -o vxlan.calico -j TCPMSS --set-mss 1410
    ```
</details>

---

### Skenario B: The 100% CPU SoftIRQ Core Collapse & Conntrack Table Full saat DDoS / Flash Traffic

#### 1. Konteks Masalah
Sebuah gateway ingress API edge enterprise yang melayani traffic publik (berbasis reverse proxy Envoy pada bare-metal Linux Ubuntu 22.04 LTS, 64 Core CPU, 128 GB RAM) tiba-tiba mengalami lonjakan latency dari 2 ms menjadi lebih dari 15.000 ms. Laporan monitoring menunjukkan 90% request klien ditolak dengan pesan `Connection Refused` atau `Network is Unreachable`.

#### 2. Gejala & Temuan Forensik
- Perintah `top` atau `htop` menunjukkan indikasi aneh: Utilisasi CPU *userspace* (`%us`) mendekati 0%, namun CPU core 0 dan core 1 menunjukkan utilisasi 100% pada status **`%si` (Software Interrupt / SoftIRQ)**.
- Kernel log (`dmesg -T` atau `journalctl -k`) dipenuhi jutaan baris error kritis:
  ```text
  [Mon Oct 05 02:14:22 2026] nf_conntrack: table full, dropping packet
  [Mon Oct 05 02:14:23 2026] nf_conntrack: table full, dropping packet
  [Mon Oct 05 02:14:24 2026] net_ratelimit: 45892 callbacks suppressed
  ```
- Pemeriksaan counter hardware NIC melalui `ethtool -S eth0 | grep -E "drop|miss"` menunjukkan kenaikan pesat pada nilai `rx_dropped` dan `rx_missed_errors`.
- Pemeriksaan file proc `cat /proc/sys/net/netfilter/nf_conntrack_count` bernilai persis sama dengan `/proc/sys/net/netfilter/nf_conntrack_max` (yaitu `262144`).

#### 3. Pertanyaan Investigasi
1. Mengapa kehabisan tabel conntrack (`nf_conntrack`) menyebabkan kernel Linux langsung men-drop paket baru yang masuk, bahkan sebelum paket diperiksa oleh firewall/Envoy?
2. Mengapa hanya core 0 dan core 1 yang mengalami saturasi SoftIRQ 100%, sementara 62 core lainnya menganggur? Konfigurasi apa di level NIC/Kernel yang belum terkonfigurasi?
3. Tuliskan panduan tindakan mitigasi komprehensif: parameter sysctl yang harus di-tuning, arsitektur rule Netfilter (`NOTRACK`), dan konfigurasi IRQ distribution!

<details>
<summary>Analisis Akar Masalah & Solusi Produksi</summary>

- **Akar Masalah (Root Cause Analysis)**:
  1. **Conntrack Table Exhaustion**: Modul `nf_conntrack` bertugas melacak status koneksi stateful (TCP state machine, NAT). Kapasitas maksimal tabel default (`262144`) tidak dirancang untuk edge gateway yang menangani ratusan ribu koneksi TCP baru per detik (SYN flood atau legitimate flash-crowd). Ketika limit tercapai, fungsi `__nf_conntrack_alloc()` gagal dan kernel secara deterministik langsung membuang paket baru (*drop at ingress*).
  2. **IRQ Affinity & RSS Misconfiguration**: NIC hardware tidak mengaktifkan multi-queue Receive Side Scaling (RSS) secara optimal, atau layanan `irqbalance` mati sehingga seluruh hardware interrupt (MSI-X) diarahkan secara kaku (*pinned*) hanya ke Core 0 dan Core 1. Core tersebut kehabisan siklus instruksi karena harus memproses jutaan panggilan SoftIRQ (`ksoftirqd`), menciptakan antrean raksasa dan buffer overflow pada RX ring buffer.

- **Langkah Remediasi & Tuning Produksi**:
  1. **Eliminasi Overhead Conntrack untuk Traffic Proxy Murni (Bypass via `raw` Table)**:
     Untuk traffic load balancer/reverse proxy stateless berkecepatan tinggi, nonaktifkan conntrack tracking menggunakan target `NOTRACK` pada iptables:
     ```bash
     # Bypass conntrack untuk traffic ingress port 80 dan 443
     iptables -t raw -A PREROUTING -p tcp -m multiport --dports 80,443 -j NOTRACK
     iptables -t raw -A OUTPUT -p tcp -m multiport --sports 80,443 -j NOTRACK
     ```

  2. **Tuning Skala Besar Tabel Conntrack (Jika Masih Diperlukan untuk NAT)**:
     Tingkatkan ukuran hash bucket dan limit conntrack agar mampu menampung 2 juta koneksi:
     ```bash
     # Alokasikan bucket hash conntrack (nf_conntrack_buckets = max / 4)
     echo 524288 > /sys/module/nf_conntrack/parameters/hashsize

     # Konfigurasi via sysctl
     sysctl -w net.netfilter.nf_conntrack_max=2097152
     sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=600 # Turunkan dari default 432000 detik (5 hari) ke 10 menit
     sysctl -w net.netfilter.nf_conntrack_tcp_timeout_close_wait=10
     sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
     ```

  3. **Distribusi IRQ & Multiqueue RSS Tuning**:
     Pastikan NIC multi-queue aktif dan didistribusikan merata ke seluruh CPU core:
     ```bash
     # Pastikan jumlah queue NIC sesuai dengan jumlah CPU core (misal 16 queue):
     ethtool -L eth0 combined 16

     # Aktifkan dan jalankan irqbalance daemon
     systemctl enable --now irqbalance

     # Aktifkan Receive Packet Steering (RPS) pada seluruh core jika NIC queue terbatas:
     for rx_queue in /sys/class/net/eth0/queues/rx-*; do
       echo "ffffffff,ffffffff" > "$rx_queue/rps_cpus"
     done
     ```
</details>

---

### Skenario C: The 10 Gbps Interface Dropping Packets saat Rata-rata Bandwidth Hanya 2 Gbps (Microburst & Ring Buffer Exhaustion)

#### 1. Konteks Masalah
Sebuah platform broker pesan Apache Kafka (bare-metal server dengan dual-port 10G NIC `ixgbe`) mengalami anomali serius: produser pesan sering mengalami error timeout pengiriman dan metadata fetch failure. Tim network monitoring (grafana/Prometheus) menyatakan bahwa jaringan dalam kondisi sangat sehat karena rata-rata pemakaian bandwidth link 10 Gbps hanya berada pada angka **1.8 Gbps hingga 2.2 Gbps** (sekitar 20% kapasitas link).

#### 2. Gejala & Bukti Forensik
- Monitoring SNMP/Prometheus dengan interval polling 1 menit menunjukkan kurva grafik bandwidth sangat landai dan hijau aman.
- Namun, output perintah `ip -s link show dev eth1` menunjukkan angka *RX errors/dropped* yang terus bertambah ribuan paket per detik:
  ```text
  3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
      link/ether 00:25:90:c8:31:42 brd ff:ff:ff:ff:ff:ff
      RX:  bytes  tokens    packets  errors  dropped  overrun mcast   
      1892182910       0 2190812901       0    89421        0 12891
  ```
- Pemeriksaan ukuran buffer hardware via `ethtool -g eth1` memberikan data berikut:
  ```text
  Ring parameters for eth1:
  Pre-set maximums:
  RX:             4096
  RX Mini:           0
  RX Jumbo:          0
  TX:             4096
  Current hardware settings:
  RX:              256
  RX Mini:           0
  RX Jumbo:          0
  TX:              256
  ```

#### 3. Pertanyaan Investigasi
1. Mengapa monitoring berbasis polling 1 menit (SNMP/Prometheus) gagal mendeteksi lonjakan lalu lintas yang menyebabkan packet drop? Jelaskan konsep **Microburst** dalam jaringan paket berkecepatan tinggi!
2. Mengapa pengaturan ukuran *Current hardware settings* RX sebesar `256` descriptor menjadi titik kegagalan utama?
3. Tuliskan serangkaian perintah CLI untuk memaksimalkan ukuran ring buffer, mengoptimalkan queue budget kernel, dan memvalidasi hasil remediasi!

<details>
<summary>Analisis Akar Masalah & Solusi Produksi</summary>

- **Akar Masalah (Root Cause Analysis)**:
  1. **Fenomena Microburst**:
     - SNMP dan monitoring modern umumnya mengumpulkan metrik rata-rata per 15, 30, atau 60 detik. Rata-rata 2 Gbps selama 60 detik dapat menyamarkan ledakan data ekstrem (*burst*) di mana puluhan produser Kafka mengirim data secara sinkron selama 2 milidetik pada kecepatan penuh **10 Gbps kawat fisik (line-rate)**.
     - Pada kecepatan 10 Gbps, 1 paket MTU 1500 byte tiba setiap **1.2 mikrodetik**. 256 paket akan memenuhi buffer hanya dalam waktu **0.3 milidetik (300 mikrodetik)**!
  2. **RX Ring Buffer Under-provisioning**:
     - *Ring Buffer* adalah antrean sirkular descriptor memori DMA di mana NIC meletakkan frame sebelum CPU/NAPI sempat memindahkannya ke `sk_buff`.
     - Pengaturan default `RX: 256` sangat kecil. Begitu microburst terjadi, buffer 256 slot tersebut terisi penuh dalam sekejap sebelum CPU core sempat merespons interupsi SoftIRQ dan menjalankan NAPI poll. Setiap paket yang tiba saat ring buffer penuh langsung dibuang di level ASIC hardware (*tail-drop at hardware interface*), tercatat sebagai counter `rx_dropped`.

- **Langkah Remediasi & Perintah Eksekusi**:
  1. **Maksimalkan RX dan TX Ring Buffer ke Kapasitas Hardware (4096 Descriptors)**:
     ```bash
     # Tingkatkan kapasitas descriptor hardware NIC
     ethtool -G eth1 rx 4096 tx 4096

     # Validasi perubahan
     ethtool -g eth1
     ```

  2. **Tuning Kernel NAPI & Socket Backlog Buffer**:
     Beri CPU kelonggaran waktu dan kapasitas antrean lebih besar untuk menguras ring buffer saat terjadi microburst:
     ```bash
     # Tingkatkan jumlah paket maksimum yang dapat di-poll kernel dalam satu loop SoftIRQ
     sysctl -w net.core.netdev_budget=600
     sysctl -w net.core.netdev_budget_usecs=4000

     # Perbesar antrean input perangkat (backlog) sebelum paket diserahkan ke soket
     sysctl -w net.core.netdev_max_backlog=100000

     # Perbesar buffer socket receiver Linux
     sysctl -w net.core.rmem_default=262144
     sysctl -w net.core.rmem_max=67108864
     sysctl -w net.ipv4.tcp_rmem="4096 87380 67108864"
     ```

  3. **Verifikasi Eliminasi Drop secara Real-Time**:
     Gunakan watch pada counter `ethtool` untuk memastikan tidak ada lagi increment pada error register:
     ```bash
     watch -d -n 1 "ethtool -S eth1 | grep -iE 'drop|miss|overrun|discards'"
     ```
</details>

---

## 4. Practical Chapter Challenge: Resilient Enterprise Spine-Leaf Datapath & Linux Host Tuning Engine

### Deskripsi Skenario
Sebagai *Lead Network Infrastructure & Platform Engineer*, Anda ditugaskan untuk merancang arsitektur jaringan underlay dan tuning kernel host untuk datacenter baru yang menjalankan workload mission-critical (Kubernetes CNI Overlay + Multi-Tenant Databases). 

Tugas Anda adalah membuat dokumen arsitektur teknis dan blueprint skrip automasi yang dapat dieksekusi untuk mengonfigurasi host Linux agar tahan terhadap microburst, mengoptimalkan throughput LACP bonding, mengamankan host dari TCP SYN flood, serta mengonfigurasi routing fabric modern berbasis BGP Unnumbered.

---

### Spesifikasi Persyaratan Teknis

1. **Host Network Datapath & Ring Buffer Hardening**:
   - Skrip harus mendeteksi batas maksimal RX/TX ring buffer antarmuka jaringan fisik (`eth0`, `eth1`) dan menaikkannya ke batas maksimal hardware (4096).
   - Mengaktifkan akselerasi hardware NIC: TSO, GSO, GRO, dan RSS.
   - Mengonfigurasi `irqbalance` atau binding IRQ affinity agar terdistribusi merata ke seluruh NUMA node.

2. **Enterprise Link Aggregation (LACP 802.3ad)**:
   - Buat konfigurasi interface LACP bonding (`bond0`) yang menggabungkan `eth0` dan `eth1`.
   - Gunakan `xmit_hash_policy = layer3+4` untuk memastikan load balancing merata per TCP/UDP session.
   - Konfigurasi `miimon = 100` ms dan `lacp_rate = fast` (interval 1 detik).

3. **Kernel TCP/IP Stack & Congestion Control Tuning**:
   - Konfigurasi algoritma TCP Congestion Control modern **BBRv2 / BBR** dengan queuing discipline `fq` (Fair Queueing).
   - Aktifkan proteksi **TCP SYN Cookies** (`net.ipv4.tcp_syncookies = 1`) dan perbesar ukuran `tcp_max_syn_backlog` menjadi minimal `65535` untuk mitigasi serangan SYN Flood.
   - Atur batas memori buffer TCP (`tcp_rmem` dan `tcp_wmem`) hingga maksimal 32MB/64MB guna mendukung transmisi BDP (*Bandwidth-Delay Product*) tinggi.

4. **Fabric Routing Blueprint (FRRouting BGP Unnumbered)**:
   - Tuliskan draf konfigurasi `frr.conf` untuk Leaf Switch / Gateway Host yang membentuk peering eBGP Unnumbered dengan dua Spine Switch (`spine1` pada port `swp1`, `spine2` pada port `swp2`) memanfaatkan IPv6 Link-Local peering sesuai standar RFC 5549.
   - Konfigurasi Autonomous System Number (ASN): Leaf menggunakan `65101`, Spine 1 menggunakan `65001`, Spine 2 menggunakan `65002`.
   - Aktifkan Equal-Cost Multi-Path (ECMP) BGP maksimal 64 jalur (`maximum-paths 64`).

---

### Solusi & Implementasi Lengkap

#### Bagian 1: Skrip Automasi Host Datapath & Sysctl Hardening (`apply-network-hardening.sh`)

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: apply-network-hardening.sh
# Deskripsi: Hardening Datapath Jaringan Linux, Ring Buffer, dan TCP Stack
# Target: Ubuntu 22.04 LTS / Debian 12 / RHEL 9 (Kernel >= 5.15)
# ==============================================================================

set -euo pipefail

log_info() {
    echo -e "\033[1;32m[INFO]\033[0m $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "\033[1;33m[WARN]\033[0m $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

if [[ $EUID -ne 0 ]]; then
   echo "Skrip ini wajib dijalankan sebagai root / sudo!" 
   exit 1
fi

INTERFACES=("eth0" "eth1")

log_info "1. Mengoptimalkan Hardware Ring Buffer & Offload NIC..."
for IFACE in "${INTERFACES[@]}"; do
    if ip link show "$IFACE" > /dev/null 2>&1; then
        log_info "Memproses interface: $IFACE"
        
        # Baca batas maksimal RX/TX dari hardware
        MAX_RX=$(ethtool -g "$IFACE" | awk '/Pre-set maximums:/,/Current hardware settings:/' | awk '/RX:/{print $2}' | head -n 1)
        MAX_TX=$(ethtool -g "$IFACE" | awk '/Pre-set maximums:/,/Current hardware settings:/' | awk '/TX:/{print $2}' | head -n 1)

        if [[ -n "$MAX_RX" && "$MAX_RX" -gt 0 ]]; then
            log_info "Menyetel $IFACE RX Ring Buffer ke: $MAX_RX"
            ethtool -G "$IFACE" rx "$MAX_RX" || log_warn "Gagal menyetel RX ring buffer di $IFACE"
        fi

        if [[ -n "$MAX_TX" && "$MAX_TX" -gt 0 ]]; then
            log_info "Menyetel $IFACE TX Ring Buffer ke: $MAX_TX"
            ethtool -G "$IFACE" tx "$MAX_TX" || log_warn "Gagal menyetel TX ring buffer di $IFACE"
        fi

        # Aktifkan Offloading
        log_info "Mengaktifkan TSO, GSO, GRO di $IFACE"
        ethtool -K "$IFACE" tso on gso on gro on rxhash on || log_warn "Sebagian offload tidak didukung hardware"
    else
        log_warn "Interface $IFACE tidak ditemukan di sistem, melewati..."
    fi
done

log_info "2. Menulis Konfigurasi Kernel Network Tuning (/etc/sysctl.d/99-network-production.conf)..."
cat << 'EOF' > /etc/sysctl.d/99-network-production.conf
# ==============================================================================
# Linux Kernel Network Performance & Security Hardening
# ==============================================================================

# --- Queue & NAPI Scheduling ---
net.core.netdev_max_backlog = 250000
net.core.netdev_budget = 600
net.core.netdev_budget_usecs = 4000

# --- Socket Buffers (BDP Tuning untuk 10G/25G/100G) ---
net.core.rmem_default = 262144
net.core.rmem_max = 67108864
net.core.wmem_default = 262144
net.core.wmem_max = 67108864
net.core.optmem_max = 2048576

# Buffer TCP: min default max (hingga 64 MB untuk High-BDP link)
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# --- TCP Connection State & Congestion Control ---
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 1
net.ipv4.tcp_sack = 1
net.ipv4.tcp_fastopen = 3

# --- Proteksi DoS / SYN Flood & Connection Backlog ---
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_syn_retries = 2
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_max_syn_backlog = 65535
net.core.somaxconn = 65535

# --- Pengelolaan Socket TIME_WAIT & Port Ephemeral ---
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535

# --- Path MTU Discovery ---
net.ipv4.ip_no_pmtu_disc = 0

# --- Virtual Memory & Swapping ---
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF

log_info "Menerapkan konfigurasi sysctl..."
sysctl --system

log_info "3. Memastikan modul BBR aktif..."
if sysctl net.ipv4.tcp_congestion_control | grep -q "bbr"; then
    log_info "TCP BBR berhasil diaktifkan!"
else
    log_warn "BBR gagal dimuat, memuat modul kernel tcp_bbr..."
    modprobe tcp_bbr
    echo "tcp_bbr" >> /etc/modules-load.d/bbr.conf
    sysctl -w net.ipv4.tcp_congestion_control=bbr
fi

log_info "Hardening datapath selesai!"
```

---

#### Bagian 2: Konfigurasi Netplan Enterprise LACP Bonding (`/etc/netplan/01-bonding.yaml`)

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: no
      dhcp6: no
    eth1:
      dhcp4: no
      dhcp6: no
  bonds:
    bond0:
      interfaces:
        - eth0
        - eth1
      addresses:
        - 10.250.10.15/24
      routes:
        - to: default
          via: 10.250.10.1
      nameservers:
        addresses:
          - 1.1.1.1
          - 8.8.8.8
      parameters:
        mode: 802.3ad
        lacp-rate: fast
        mii-monitor-interval: 100
        transmit-hash-policy: layer3+4
        min-links: 1
        up-delay: 200
        down-delay: 200
```

*Verifikasi bonding*:
```bash
netplan apply
cat /proc/net/bonding/bond0
```

---

#### Bagian 3: Blueprint Routing Datacenter BGP Unnumbered (`/etc/frr/frr.conf`)

```text
frr version 8.5
frr defaults traditional
hostname leaf01.dc1.internal
log syslog informational
no ip forwarding
no ipv6 forwarding
service integrated-vtysh-config
!
ip forwarding
ipv6 forwarding
!
interface swp1
 description UPLINK-TO-SPINE01
 no ipv6 nd suppress-ra
 ipv6 nd ra-interval 3
!
interface swp2
 description UPLINK-TO-SPINE02
 no ipv6 nd suppress-ra
 ipv6 nd ra-interval 3
!
router bgp 65101
 bgp router-id 10.255.1.1
 no bgp default ipv4-unicast
 bgp bestpath as-path multipath-relax
 neighbor SPINE-FABRIC peer-group
 neighbor SPINE-FABRIC remote-as external
 neighbor SPINE-FABRIC capability extended-nexthop
 neighbor swp1 interface peer-group SPINE-FABRIC
 neighbor swp2 interface peer-group SPINE-FABRIC
 !
 address-family ipv4 unicast
  network 10.255.1.1/32
  network 10.250.10.0/24
  neighbor SPINE-FABRIC activate
  maximum-paths 64
 exit-address-family
 !
 address-family ipv6 unicast
  neighbor SPINE-FABRIC activate
 exit-address-family
!
line vty
!
```

*Verifikasi status BGP Unnumbered*:
```bash
vtysh -c "show ip bgp summary"
vtysh -c "show ip route"
```

---

## 5. Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Perbedaan model OSI 7-Layer vs TCP/IP 4-Layer dan pemetaan PDU (Data, Segment, Packet, Frame, Bits).
- [ ] Struktur header frame Ethernet II (14 byte) dan flag bit kontrol TCP (SYN, ACK, FIN, RST, PSH, URG).
- [ ] Kalkulasi batas transmisi: Formula MTU, MSS, dan pembengkakan overhead akibat enkapsulasi (802.1Q VLAN 4B, VXLAN 50B).
- [ ] Datapath penerimaan paket internal Linux: Alur dari Port NIC $\to$ RX Ring Buffer (DMA) $\to$ Hard IRQ $\to$ NAPI Poll $\to$ SoftIRQ (`NET_RX_SOFTIRQ`) $\to$ `sk_buff` $\to$ Netfilter/Conntrack $\to$ Socket Queue.
- [ ] Cara kerja Path MTU Discovery (PMTUD), penyebab PMTUD Black Hole saat ICMP Type 3 Code 4 diblokir, serta mitigasi via MSS Clamping.
- [ ] Arsitektur Datacenter Clos (Spine-Leaf) 2-Tier dan eliminasi STP menggunakan L3 ECMP.
- [ ] Konsep BGP Unnumbered (RFC 5549) yang memanfaatkan IPv6 Link-Local untuk menukar rute IPv4 tanpa subnet point-to-point `/31`.
- [ ] Perbedaan mendasar EVPN-VXLAN Symmetric IRB (menggunakan L3VNI per tenant VRF) dibandingkan Asymmetric IRB dalam hal skalabilitas TCAM.
- [ ] Perilaku LACP bonding `xmit_hash_policy`: `layer2` vs `layer2+3` vs `layer3+4`, serta risiko Hash Polarization.

### Saya Tidak Perlu Menghafal:
- [ ] Nilai bitmask heksadesimal lengkap dari seluruh opsi TCP (cukup gunakan parser `tcpdump` / Wireshark).
- [ ] Seluruh nomor port IANA (cukup pahami port standar industri: 22, 53, 80, 179/BGP, 443, 4789/VXLAN, 6443/K8s).
- [ ] Struktur internal kode bahasa C dari struct kernel `sk_buff` (cukup pahami semantiknya dalam alokasi memori buffer).

### Saya Harus Bisa Melakukan:
- [ ] Menganalisis alur paket (*packet capture analysis*) secara langsung di terminal menggunakan `tcpdump -nnvv -i <iface>`.
- [ ] Memeriksa dan memperbesar hardware ring buffer menggunakan `ethtool -g` dan `ethtool -G`.
- [ ] Menginspeksi saturasi antrean dan performa soket secara granular menggunakan `ss -tin` dan `ip -s link`.
- [ ] Mendiagnosis dan memitigasi conntrack overflow menggunakan `conntrack -S` dan rule `iptables -t raw -j NOTRACK`.
- [ ] Mengonfigurasi LACP bonding 802.3ad berkinerja tinggi dengan Netplan/Linux systemd-networkd.
- [ ] Mengonfigurasi dan memvalidasi peering BGP Unnumbered pada Linux Host menggunakan Free Range Routing (FRR).

---

```text
Checklist Kesiapan Penguasaan Bab 01:
[ ] 5/5 Pertanyaan Tingkat Dasar dijawab dengan benar
[ ] 5/5 Pertanyaan Tingkat Menengah dipahami secara komprehensif
[ ] 3/3 Skenario Kasus Produksi dianalisis hingga ke level root-cause dan langkah mitigasi
[ ] Seluruh konfigurasi Practical Chapter Challenge dipahami dan siap diimplementasikan
[ ] Seluruh checklist pemahaman telah terpenuhi
```

---
*Ketik **LANJUT** untuk berpindah ke BAB 02: Routing Protokol, Dynamic Routing (BGP/OSPF), & Datacenter Fabrics.*
