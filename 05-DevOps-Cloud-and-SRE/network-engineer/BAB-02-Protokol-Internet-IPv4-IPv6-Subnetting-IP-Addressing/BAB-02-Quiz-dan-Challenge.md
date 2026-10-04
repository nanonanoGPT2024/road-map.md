# Evaluasi Bab 02: Protokol Internet (IPv4/IPv6), Subnetting, dan IP Addressing

---

## I. Basic Questions (5 Soal Pilihan Ganda)

### Soal 1
Berapa panjang byte minimum dari sebuah header IPv4 standar tanpa Options, dan field apa yang menentukan keberadaan opsi tambahan tersebut?
- A. 24 bytes, field Total Length
- B. 20 bytes, field Internet Header Length (IHL)
- C. 40 bytes, field Payload Length
- D. 20 bytes, field Type of Service (ToS)

### Soal 2
Berapa jumlah host address yang usable (dapat dialokasikan ke mesin) pada subnet IPv4 dengan notasi prefix `/28`?
- A. 16
- B. 14
- C. 30
- D. 6

### Soal 3
Manakah dari rentang IP address berikut yang termasuk dalam alokasi Carrier-Grade NAT (CGNAT) sesuai RFC 6598?
- A. `172.16.0.0/12`
- B. `192.168.0.0/16`
- C. `100.64.0.0/10`
- D. `169.254.0.0/16`

### Soal 4
Bagaimana bentuk kompresi paling valid dan standar (RFC 5952) dari alamat IPv6 `2001:0db8:0000:0000:0008:0000:0000:0001`?
- A. `2001:db8::8:0:0:1`
- B. `2001:db8::8::1`
- C. `2001:0db8::8::1`
- D. `2001:db8:0:0:8::1`

### Soal 5
Pada protokol autokonfigurasi IPv6 (SLAAC), pesan ICMPv6 apa yang dikirimkan oleh router secara periodik atau sebagai balasan dari Router Solicitation untuk mengumumkan prefix subnet ke host?
- A. Neighbor Advertisement (Type 136)
- B. Router Advertisement (Type 134)
- C. Echo Reply (Type 129)
- D. Redirect Message (Type 137)

---

## II. Intermediate Questions (5 Soal Pilihan Ganda / Singkat)

### Soal 6
Sebuah paket IPv4 memiliki ukuran Total Length 1500 bytes dan melewati router dengan MTU interface keluar sebesar 600 bytes. Header IP standar adalah 20 bytes. Jika router memecah paket ini ke dalam beberapa fragmen:
Berapa nilai **Fragment Offset** (dalam unit desimal) pada fragmen KEDUA?
- A. 72
- B. 74
- C. 576
- D. 580

### Soal 7
Sebutkan perbedaan mendasar antara bit flag **M (Managed Address Configuration)** dan bit flag **O (Other Configuration)** yang terkandung dalam paket ICMPv6 Router Advertisement (RA)!

### Soal 8
Jika sebuah gateway NAT Linux memiliki tabel conntrack dengan status koneksi berikut:
`tcp 6 431999 ESTABLISHED src=192.168.1.100 dst=93.184.216.34 sport=51234 dport=443 src=93.184.216.34 dst=203.0.113.10 sport=443 dport=10555`
Jelaskan arti dari alamat `203.0.113.10:10555` dalam tuple pemetaan tersebut!

### Soal 9
Mengapa header IPv6 menghilangkan field **Header Checksum** yang sebelumnya selalu ada di IPv4? Jelaskan dampaknya terhadap throughput router core!

### Soal 10
Mengapa subnetting dengan prefix lebih spesifik dari `/64` (seperti `/80` atau `/112`) sangat tidak dianjurkan di jaringan end-host local area IPv6 standar?

---

## III. Scenario-Based Questions (3 Kasus Nyata)

### Kasus 1: "The Vanishing EKS Subnet Space"
Sebuah perusahaan e-commerce menjalankan Amazon Elastic Kubernetes Service (EKS) dengan AWS VPC CNI. VPC dialokasikan pada subnet `10.20.0.0/22`. Cluster memiliki 10 worker node jenis c5.4xlarge (masing-masing mendukung hingga 234 secondary IPv4 Pod IP).
Dalam waktu 2 minggu setelah kampanye marketing berjalan, penambahan node baru gagal diluncurkan (*Deployment stuck in Pending*), dan autoscaler melaporkan: `InsufficientFreeAddressesInSubnet`.

1. Analisis mengapa subnet `/22` gagal menampung kebutuhan cluster tersebut!
2. Tanpa menghancurkan (*destroy*) VPC yang sedang aktif berproduksi, solusi mitigasi arsitektur apa yang dapat Anda terapkan pada level VPC dan Kubernetes CNI?

### Kasus 2: "The Mystery of Truncated Large File Uploads (MTU/ICMPv6 Black Hole)"
Setelah mengaktifkan native IPv6 pada edge API gateway, ratusan pengguna ISP seluler tertentu mengeluhkan bahwa mereka dapat melakukan login (request HTTP GET kecil), tetapi aplikasi mereka *freeze* atau *timeout* saat mencoba mengunggah payload gambar (POST besar berukuran > 2MB). Pada pengguna IPv4, keluhan ini tidak pernah terjadi.
Tim security mengonfirmasi bahwa mereka baru saja menerapkan aturan firewall edge:
`ip6tables -A INPUT -p icmpv6 --icmpv6-type echo-request -j ACCEPT`
`ip6tables -A INPUT -p icmpv6 -j DROP`

Identifikasi akar permasalahan teknis Layer 3/4 dari kasus tersebut dan jelaskan perbaikan aturan firewall yang presisi!

### Kasus 3: "Overlapping Mergers NAT Hell"
Perusahaan Alpha (`172.16.0.0/16`) mengakuisisi Perusahaan Beta (`172.16.0.0/16`). Kedua pihak memiliki service krusial di database internal masing-masing yang harus saling berkomunikasi secara direct TCP socket:
- DB Alpha: `172.16.10.5:5432`
- Client Beta: `172.16.10.5` (IP persis sama!)
Rancang arsitektur **Twice-NAT** atau Stateful Translation Gateway di antara kedua jaringan agar Client Beta dapat mengakses DB Alpha secara transparan tanpa benturan IP!

---

## IV. Practical Chapter Challenge

### Judul Tantangan
**"Enterprise Dual-Stack Transition & High-Availability NAT Fabric Architecture"**

### Skenario & Tugas Proyek
Anda diangkat sebagai Lead Infrastructure Architect untuk merancang skema pengalamatan IP komprehensif pada arsitektur hybrid multi-region cloud platform.

#### Spesifikasi Kebutuhan:
1. **IPv4 Subnet Planning**:
   - Diberikan induk alokasi: `10.240.0.0/14`.
   - Rancang pembagian subnet menggunakan prinsip **VLSM** untuk 3 Availability Zone (AZ). Masing-masing AZ harus memiliki:
     - Tier Public (Web/Load Balancer): 1000 hosts per AZ
     - Tier Private Application: 4000 hosts per AZ
     - Tier Database/DataStore: 500 hosts per AZ
     - Tier Management & Out-of-band: 100 hosts per AZ
   - Dokumentasikan tabel alokasi lengkap: Network Address, Subnet Mask, Usable Host Range, dan Broadcast Address. Tunjukkan bahwa alokasi bersifat summarizable per AZ!

2. **IPv6 Addressing Plan**:
   - Diberikan Prefix RIR: `2001:db8:abcd::/48`.
   - Alokasikan hierarki `/64` untuk setiap tier di atas pada masing-masing AZ.
   - Tetapkan skema segmentasi bit pada Hextet ke-4 (`abcd:<HEX>`) untuk membedakan Region, AZ, dan Tier secara konsisten.

3. **Linux Kernel NAT & Routing Configuration Artifact**:
   - Tuliskan skrip bash mandiri yang mengonfigurasi mesin Linux dual-homed router (`eth0` = WAN, `eth1` = LAN):
     - Mengaktifkan kernel forwarding untuk IPv4 dan IPv6.
     - Mengonfigurasi `nftables` stateful NAT masquerading pada `eth0`.
     - Mengonfigurasi Port Forwarding (DNAT) dari WAN port `8443` ke App Server internal `10.240.X.Y:443`.
     - Menyetel parameter sysctl conntrack untuk menangani minimal 500.000 concurrent sessions.

---

## Kunci Jawaban & Panduan Evaluasi

### Kunci Soal I (Basic)
1. **B** - Minimum 20 bytes. Field IHL (4 bit) menentukan panjang header dalam kelipatan 32-bit word. Nilai default 5 (20 bytes). Jika IHL > 5, terdapat Options.
2. **B** - Notasi `/28` menyisakan $32 - 28 = 4$ bit host. $2^4 - 2 = 16 - 2 = 14$ usable hosts.
3. **C** - RFC 6598 menetapkan `100.64.0.0/10` khusus untuk Shared Address Space / CGNAT.
4. **A** - Sesuai RFC 5952: kompresi `::` hanya boleh dilakukan satu kali pada blok nol terpanjang. Blok pertama memiliki dua hextet nol bersebelahan, blok kedua memiliki dua hextet nol bersebelahan. Standar memilih run pertama yang terpanjang atau paling kiri jika seri: `2001:db8::8:0:0:1`.
5. **B** - Router Advertisement (ICMPv6 Type 134).

### Kunci Soal II (Intermediate)
6. **B. 74**.
   *Perhitungan*:
   - MTU = 600 bytes. Dikurangi header IP (20 bytes) = max payload per fragmen = 580 bytes.
   - Namun, fragmen IPv4 (kecuali fragmen terakhir) HARUS merupakan kelipatan 8 bytes.
   - $580 / 8 = 72.5$ (tidak bulat). Maka payload fragmen pertama dibulatkan ke bawah ke kelipatan 8 terdekat: $72 \times 8 = 576$ bytes.
   - Fragmen 1 membawa payload byte 0 s/d 575. Offset fragmen 2 adalah posisi byte data dimulai dibagi 8: $576 / 8 = \mathbf{72}$? Tunggu: jika 576 bytes payload, offset fragmen kedua adalah $576 / 8 = 72$. Pilihan A adalah 72. *(Koreksi: Pilihan A adalah 72).*
7. **Flag M vs Flag O**:
   - **M (Managed)**: Menginstruksikan client untuk mengabaikan penomoran IP dari prefix SLAAC dan meminta seluruh alokasi IP ke Stateful DHCPv6 server.
   - **O (Other)**: Menginstruksikan client untuk tetap membuat IP address sendiri menggunakan prefix SLAAC, namun mengontak DHCPv6 server (Stateless DHCPv6) untuk mendapatkan konfigurasi tambahan seperti DNS server dan Search Domain.
8. `203.0.113.10:10555` adalah **Public Translated Socket** dari gateway NAT. Ketika host internal `192.168.1.100:51234` mengirim paket keluar, gateway mengubah source socket menjadi `203.0.113.10` port `10555`. Jawaban respons dari server eksternal dikirim kembali ke socket publik ini.
9. Router di setiap hop tidak perlu lagi membuang siklus CPU untuk memvalidasi dan menghitung ulang (*recalculate*) checksum setiap kali nilai hop limit (TTL) berkurang. Integritas data didelegasikan ke Layer 2 Frame Check Sequence (CRC32) dan Layer 4 End-to-End Checksum (TCP/UDP checksum mandatory pada IPv6). Hal ini meningkatkan packet-forwarding rate (pps) core router secara eksponensial.
10. Subnetting `/64` adalah dependensi mutlak standar arsitektur IPv6 (RFC 4291 & RFC 4862). Jika prefix lebih panjang dari `/64` digunakan, autokonfigurasi SLAAC akan rusak total karena SLAAC membutuhkan tepat 64 bit untuk menampung Interface Identifier (IID). Selain itu, banyak hardware chip router (ASIC/TCAM) dioptimasi secara spesifik hanya untuk routing table `/64`.

### Panduan Penilaian Kasus (Scenario-Based)
- **Kasus 1**: Subnet `/22` hanya memiliki 1022 IP. 10 node $\times$ 234 pod = 2340 IP yang dibutuhkan. Solusi: Hubungkan secondary CIDR range (misal dari blok RFC 6598 `100.64.0.0/16`) ke AWS VPC, lalu konfigurasikan AWS VPC CNI custom networking untuk mengalokasikan secondary CIDR khusus untuk IP pod pod, memisahkan Pod subnet dari Node subnet.
- **Kasus 2**: Aturan firewall memblokir semua ICMPv6 selain Type 128 (Echo Request). Pada IPv6, fragmentasi router ditiadakan; router bergantung pada **ICMPv6 Type 2 (Packet Too Big)** untuk Path MTU Discovery (PMTUD). Ketika file besar dikirim, frame melebihi MTU jalur transit seluler, router menjatuhkan paket dan mengirim ICMPv6 Type 2. Karena firewall memblokirnya, sender tidak pernah tahu paketnya terlalu besar dan terus melakukan retransmisi (Black Hole). Solusi: Tambahkan aturan eksplisit `ip6tables -A INPUT -p icmpv6 --icmpv6-type packet-too-big -j ACCEPT` dan `accept established related`.
- **Kasus 3**: Bangun gateway penengah dengan Twice-NAT (Source NAT dan Destination NAT simultan). Petakan DB Alpha ke Virtual IP unik (misal `192.168.200.5`) dan petakan Client Beta ke Virtual IP unik saat melintasi transit gateway. Client Beta menghubungi `192.168.200.5`. Gateway mentranslasikan destination IP ke `172.16.10.5` dan mentranslasikan source IP Client Beta ke IP proxy lokal Alpha sehingga paket balasan dapat dirutekan kembali tanpa overlap.