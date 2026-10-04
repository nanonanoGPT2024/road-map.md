# Evaluasi Pembelajaran Bab 08: Keamanan Jaringan, Firewalling, Segmentasi, dan VPNs

---

## I. Basic Questions (5 Soal)

### Soal 1
Mengapa return traffic dari web server eksternal dapat lolos melewati Stateful Packet Inspection (SPI) firewall meskipun tidak ada aturan (rule) inbound eksplisit yang mengizinkan port web server tersebut?
- A. Karena firewall secara default mengizinkan semua traffic berbasis TCP.
- B. Karena SPI mencatat status inisiasi koneksi outbound di dalam State Table dan secara otomatis mengizinkan paket balik yang cocok dengan 5-tuple koneksi tersebut.
- C. Karena protokol TCP menyematkan public key firewall di dalam header SYN-ACK.
- D. Karena SPI memetakan seluruh port eksternal ke dalam TCAM hardware secara stateless.

### Soal 2
Protokol keamanan IPsec manakah yang memberikan jaminan kerahasiaan (*confidentiality*) payload data dan kompatibel dengan mekanisme Network Address Translation (NAT) melalui NAT-Traversal (UDP 4500)?
- A. Authentication Header (AH)
- B. Internet Group Management Protocol (IGMP)
- C. Encapsulating Security Payload (ESP)
- D. Generic Routing Encapsulation (GRE) stateless

### Soal 3
Pada arsitektur Cisco Zone-Based Firewall (ZFW), apa yang terjadi secara default jika Interface GigabitEthernet0/1 dimasukkan ke dalam Zona `TRUSTED` dan Interface GigabitEthernet0/2 dimasukkan ke dalam Zona `UNTRUSTED`, tanpa adanya konfigurasi `zone-pair`?
- A. Seluruh traffic dari `TRUSTED` ke `UNTRUSTED` diizinkan, tetapi traffic sebaliknya diblokir.
- B. Seluruh traffic antar kedua zona tersebut diblokir secara penuh di kedua arah.
- C. Traffic TCP diizinkan secara stateful, tetapi traffic UDP dan ICMP di-drop.
- D. Traffic akan dikirimkan ke Self Zone untuk diproses oleh routing engine.

### Soal 4
Berapa jumlah pertukaran pesan (messages exchange) dasar yang dibutuhkan oleh protokol IKEv2 untuk membangun terowongan IKE SA operasional dan Child SA (IPsec SA) pertama?
- A. 6 Pesan
- B. 9 Pesan
- C. 4 Pesan
- D. 2 Pesan

### Soal 5
Pada standar pengamanan port fisik IEEE 802.1X, entitas jaringan manakah yang bertindak sebagai **Authenticator**?
- A. Workstation pengguna yang menjalankan software EAP Supplicant.
- B. Central AAA Server (FreeRADIUS atau Cisco ISE).
- C. Network Access Device (L2/L3 Access Switch atau Wireless LAN Controller).
- D. Certificate Authority (CA) Server yang menerbitkan X.509 certificates.

---

## II. Intermediate Questions (5 Soal)

### Soal 6
Jelaskan mengapa konfigurasi terowongan IPsec Native (Tunnel Mode murni) tidak mampu menjalankan protokol routing dinamis OSPFv2 secara langsung antar-cabang, dan bagaimana kombinasi GRE over IPsec memecahkan masalah ini!

### Soal 7
Analisis apa yang akan terjadi pada komunikasi data TCP jika sebuah router tunnel GRE over IPsec memiliki Physical MTU sebesar 1500 byte, total overhead enkapsulasi 76 byte, namun administrator jaringan **TIDAK** mengonfigurasi `ip tcp adjust-mss` pada interface tunnel ketika workstation mengirimkan data dengan ukuran payload TCP maksimum (1460 byte) dengan bit DF (Don't Fragment) aktif!

### Soal 8
Dalam arsitektur DMZ yang aman, mengapa aturan firewall yang memperbolehkan Web Server di DMZ untuk melakukan inisiasi koneksi TCP port 5432 langsung ke Database Server di zona `INSIDE` dianggap sebagai kesalahan arsitektur kritis (*architectural flaw*)? Bagaimana desain interaksi yang benar?

### Soal 9
Bandingkan mekanisme enkripsi IEEE 802.1AE (MACsec) dengan IPsec ESP: Jelaskan pada layer OSI berapa masing-masing beroperasi, bagian frame/paket apa yang dienkripsi oleh keduanya, dan di mana batasan operasional MACsec saat dihadapkan pada WAN multi-hop routed internet!

### Soal 10
Mengapa penggunaan Diffie-Hellman Group 2 dan Group 5 kini dilarang dalam standar kepatuhan keamanan modern (seperti NIST/PCI-DSS), dan kelompok DH Group manakah yang direkomendasikan untuk implementasi enterprise masa kini?

---

## III. Scenario-Based Questions (3 Kasus Nyata)

### Kasus 1: Misteri TCP Connection Hang pada Jaringan Asymmetric Routing
Sebuah perusahaan e-commerce memiliki dua edge firewall stateful (FW-A dan FW-B) yang terhubung ke dua penyedia ISP berbeda menggunakan BGP multihoming. Klien dari internet mengakses website perusahaan (`203.0.113.10`). 
- Trafik TCP SYN dari klien masuk melalui ISP-1 dan diproses oleh **FW-A**. FW-A membuat entri state table `TCP_SYN_SENT/ESTABLISHED` dan meneruskannya ke Web Server internal.
- Saat Web Server merespons dengan paket TCP SYN-ACK, routing tabel internal BGP memilih jalur terbaik keluar melalui **FW-B** (karena metrik path ISP-2 lebih murah).
- Klien tidak pernah berhasil membuka web, koneksi browser mengalami *timeout/hanging*.

**Pertanyaan Analitis:**
1. Mengapa paket SYN-ACK di-drop oleh FW-B?
2. Rekomendasikan dua solusi rekayasa jaringan konkret (pada level routing atau level firewall clustering) untuk mengatasi masalah ini tanpa mematikan stateful inspection!

---

### Kasus 2: Insiden Silent Drop Enkripsi IPsec AH di Belakang NAT
Sebuah cabang remote baru dikonfigurasi menggunakan IPsec Site-to-Site menuju Headquarter. Karena alasan kepatuhan internal terhadap otentikasi integritas menyeluruh, engineer junior memilih menggunakan protokol **Authentication Header (AH - IP Protocol 51)**. 
- Cabang terhubung ke internet menggunakan modem broadband residensial yang melakukan Dynamic Port Address Translation (PAT/NAT).
- Negosiasi IKEv2 Phase 1 berhasil (`ESTABLISHED`).
- Namun, tidak ada satu pun paket data internal (ICMP, HTTP) yang berhasil melintasi tunnel. Seluruh paket di-drop oleh router Headquarter dengan counter IPsec ICV (Integrity Check Value) error meningkat drastis.

**Pertanyaan Analitis:**
1. Secara matematis dan teknis header IP, mengapa paket AH selalu gagal diverifikasi setelah melintasi perangkat NAT?
2. Perubahan arsitektur apa yang wajib dilakukan untuk memulihkan konektivitas tunnel tersebut secara aman?

---

### Kasus 3: Kegagalan Masal Port Otentikasi 802.1X Pasca Upgrade Switch
Sebuah kantor korporat mengaktifkan IEEE 802.1X berbasis EAP-TLS pada seluruh access switch port. Switch lama diganti dengan switch multi-gigabit baru. Segera setelah pemasangan:
- Semua workstation Windows gagal mendapatkan IP address dari DHCP dan status network adapter macet pada *Identifying... (No Internet Access)*.
- Administrator menemukan bahwa port access switch berada dalam status `UNAUTHORIZED`.
- Log server RADIUS menunjukkan tidak ada permintaan otentikasi (`RADIUS Access-Request`) yang pernah diterima dari IP switch baru tersebut.
- Wireshark capture pada workstation mendeteksi frame `EAPoL-Start` dikirimkan secara berulang oleh PC, tetapi tidak ada balasan dari switch.

**Pertanyaan Analitis:**
1. Berdasarkan arsitektur komponen 802.1X (Supplicant - Authenticator - Auth Server), komponen manakah yang mengalami kegagalan konfigurasi?
2. Sebutkan tiga langkah troubleshooting verifikasi CLI pada switch untuk menyelesaikan kendala tersebut!

---

## IV. Practical Chapter Challenge

### Tantangan Arsitektur: Secure Multi-Branch & Multi-Cloud Transit Backbone

#### Deskripsi Skenario:
Anda adalah Principal Network Security Architect untuk korporasi finansial global. Korporasi ini memiliki:
- **Headquarter (HQ)**: Core Data Center di Jakarta (Subnet: `10.1.0.0/16`).
- **Disaster Recovery (DR)**: Data Center di Surabaya (Subnet: `10.2.0.0/16`).
- **Cloud Fabric**: AWS Transit Gateway di region Jakarta (VPC Subnet: `10.100.0.0/16`).
- **Edge Perimeter**: Seluruh koneksi inter-site menggunakan internet publik.

#### Persyaratan Tugas Teknis:
1. **Rancang Blueprint Tunneling**:
   - Rancang topologi dual-hub GRE over IPsec IKEv2 antara HQ, DR, dan AWS TGW.
   - Enkapsulasi wajib menggunakan Suite: `AES-GCM-256`, PRF `SHA384`, Diffie-Hellman `Group 19` (NIST P-256).
   - Tentukan nilai kalkulasi MTU dan TCP MSS Clamping yang presisi untuk semua tunnel.
2. **Zone-Based Firewall (ZFW) Isolation Matrix**:
   - Susun security zone: `Z-HQ-CORE`, `Z-CLOUD`, `Z-DMZ-PUBLIC`, `Z-WAN-UNTRUSTED`.
   - Tetapkan policy matrix:
     - Traffic dari `Z-CLOUD` hanya boleh mengakses subnet database di `Z-HQ-CORE` pada port TCP 5432 (PostgreSQL).
     - Traffic dari `Z-DMZ-PUBLIC` dilarang keras menginisiasi koneksi ke `Z-HQ-CORE` dan `Z-CLOUD`.
     - Inisiasi koneksi BGP routing antar-node diizinkan hanya antar IP tunnel virtual.
3. **Format Deliverable**:
   - Gambar diagram arsitektur interkoneksi (ASCII / Text-based flow).
   - Skrip konfigurasi router Cisco IOS-XE lengkap (Crypto IKEv2, Tunnel Interface, MSS Clamping, ZFW Policy).
   - Rencana pengujian validasi failover dan mitigasi asymmetric routing.

---

## Kunci Jawaban & Panduan Pembahasan

### I. Kunci Jawaban Basic Questions
1. **B**: SPI melacak state lifecycle setiap flow TCP di dalam state table. Ketika workstation lokal menginisiasi koneksi outbound (SYN), firewall mencatat 5-tuple. Paket balasan (SYN-ACK) diverifikasi terhadap tabel tersebut; jika cocok, paket diizinkan lewat otomatis tanpa membutuhkan aturan inbound statis.
2. **C**: ESP mengenkripsi muatan (payload) paket dan mendukung NAT-Traversal (membungkus paket ESP ke dalam header UDP port 4500), sedangkan AH memvalidasi integritas outer header yang rusak saat melewati NAT.
3. **B**: Pada Cisco ZFW, hubungan antar dua interface yang berada pada security zone berbeda secara default adalah *implicit deny all* (seluruh traffic diblokir total) sampai didefinisikan policy eksplisit pada `zone-pair`.
4. **C**: IKEv2 hanya membutuhkan 4 pesan dasar: 2 pesan `IKE_SA_INIT` (negosiasi cryptographic proposal dan DH exchange) dan 2 pesan `IKE_AUTH` (otentikasi identitas, PSK/sertifikat, dan pembuatan Child SA pertama).
5. **C**: Authenticator bertindak sebagai perantara Layer 2; ia adalah Network Access Device (switch fisik atau WLC) yang menerima frame EAPoL dari Supplicant (klien) dan membungkusnya kembali menjadi paket RADIUS ke Authentication Server.

### II. Panduan Jawaban Intermediate
6. **OSPF vs IPsec**: OSPF mengirim paket Hello dan LSA update menggunakan alamat IP Multicast (`224.0.0.5` dan `224.0.0.6`). IPsec native tunnel mode secara fundamental adalah arsitektur Point-to-Point Unicast yang tidak mendukung transmisi paket multicast/broadcast. GRE bertindak sebagai protokol wrapper yang mampu mengenkapsulasi paket multicast ke dalam payload GRE unicast, yang kemudian dienkripsi secara aman oleh IPsec ESP.
7. **Dampak ketiadaan MSS Clamping**: Workstation akan membentuk TCP handshake dengan MSS default 1460 byte. Ketika payload penuh (1460 byte TCP + 40 byte IP/TCP header = 1500 byte) dikirim, router mengenkapsulasinya dengan GRE dan IPsec (menambah 76 byte, total 1576 byte). Karena bit DF (Don't Fragment) aktif, router tidak dapat memecah paket dan wajib membuang paket tersebut seraya mengirim ICMP Type 3 Code 4 (*Fragmentation Needed*). Jika pesan ICMP ini diblokir di tengah jalan (PMTUD black hole), transfer data aplikasi akan macet permanen (*hanging indefinitely*).
8. **Flaw DMZ ke Inside**: Jika DMZ Web Server diizinkan membuka koneksi langsung ke database core di zona Inside, kerentanan RCE pada Web Server (misal via eksploitasi web deserialization atau SQL injection) memungkinkan penyerang menjadikan web server sebagai pivoting jump-box untuk menyerang port lain di core internal. Desain yang benar: Database server atau antrean pesan (Message Queue) di zona inside melakukan polling/pulling data ke DMZ, atau membatasi komunikasi hanya melalui proxy API internal yang terisolasi dengan mutual TLS (mTLS) dan filtering L7 ketat.
9. **MACsec vs IPsec**:
   - *Layer OSI*: MACsec beroperasi di Layer 2 (Data Link); IPsec beroperasi di Layer 3 (Network Layer).
   - *Bagian yang dienkripsi*: MACsec mengenkripsi seluruh Ethernet frame payload (termasuk L2 payload dan tag VLAN), menyisakan MAC Source/Destination dan SecTAG header. IPsec ESP mengenkripsi paket IP Layer 3 ke atas.
   - *Batasan*: MACsec bersifat hop-by-hop point-to-point. Ketika frame melewati router Layer 3 intermediate pada public internet, frame Ethernet L2 di-strip/dibuang dan diganti dengan frame L2 hop berikutnya. Dengan demikian, proteksi MACsec terputus pada L3 boundary, sedangkan IPsec mampu melintasi multi-hop routed WAN tanpa hambatan.
10. **DH Group Deprecation**: DH Group 2 (1024-bit) dan Group 5 (1536-bit) memiliki panjang modulus prime yang rentan didekripsi oleh komputasi modern menggunakan algoritma *Number Field Sieve* (NFS) dan kapabilitas komputasi cloud/nation-state actor. Standar modern mewajibkan minimal DH Group 14 (2048-bit MODP) atau Elliptic Curve Cryptography seperti DH Group 19 (256-bit ECP) dan Group 20 (384-bit ECP) yang menawarkan keamanan eksponensial lebih kuat dengan kalkulasi matematis lebih efisien.

### III. Pembahasan Kasus Nyata
- **Kasus 1 (Asymmetric Routing)**:
  1. FW-B membuang paket SYN-ACK karena FW-B mengoperasikan SPI. Paket SYN-ACK dianggap ilegal (*out-of-state*) karena FW-B tidak pernah melihat paket SYN inisiasi sebelumnya dan tidak memiliki entri koneksi di state table-nya.
  2. *Solusi*:
     - Aktifkan Stateful Session Synchronization antar FW-A dan FW-B menggunakan dedicated link sinkronisasi inter-chassis (Active-Active Clustering dengan dynamic flow sharing).
     - Modifikasi BGP routing policy (misal: BGP Local Preference atau AS-Path Prepending) untuk memastikan routing simetris, di mana traffic inbound dan outbound untuk blok IP publik tertentu selalu dipaksa melewati firewall yang sama.
- **Kasus 2 (IPsec AH & NAT)**:
  1. Header AH memvalidasi integritas seluruh paket menggunakan algoritma HMAC, termasuk IP Source dan IP Destination pada IP header luar. Ketika router PAT/NAT memodifikasi IP header (mengubah IP lokal cabang menjadi IP publik), nilai hash kriptografis yang dihitung ulang oleh penerima di HQ tidak lagi cocok dengan hash ICV original. HQ menganggap paket telah dimodifikasi oleh penyerang (tampered) dan langsung membuangnya.
  2. *Solusi*: Ganti protokol dari AH ke **ESP (Encapsulating Security Payload)** dan aktifkan fitur **NAT-Traversal (NAT-T)**. NAT-T mendeteksi keberadaan NAT selama IKE negotiation dan secara otomatis membungkus paket ESP (Protocol 50) ke dalam UDP port 4500, yang dapat melewati router NAT tanpa merusak validasi kriptografis.
- **Kasus 3 (802.1X Switch Failure)**:
  1. Kegagalan terjadi pada komponen **Authenticator (Switch)**. Switch gagal merespons frame EAPoL lokal dan tidak mengontak RADIUS server.
  2. *Langkah Verifikasi CLI*:
     - Jalankan `show dot1x all` atau `show authentication sessions` untuk memverifikasi apakah service 802.1X globally enabled (`dot1x system-auth-control`).
     - Jalankan `show radius server-group all` untuk memastikan IP server RADIUS, UDP port otentikasi (1812), dan Shared Secret Key telah dikonfigurasi secara identik.
     - Periksa konfigurasi interface: pastikan port dikonfigurasi dengan mode `authentication port-control auto` dan `dot1x pae authenticator`.

---