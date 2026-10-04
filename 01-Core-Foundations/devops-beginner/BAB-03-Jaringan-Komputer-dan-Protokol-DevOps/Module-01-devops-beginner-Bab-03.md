# MODUL 03-01: JARINGAN KOMPUTER & PROTOKOL INTI DEVOPS

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** DevOps Beginner
* **Kategori:** 01-Core-Foundations
* **Bab:** 03 — Networking Foundations for Infrastructure & Operations
* **Modul:** 01 — Jaringan Komputer & Protokol Inti DevOps
* **Prasyarat:** 
  * Pemahaman dasar sistem operasi Linux (CLI, proses, permission).
  * Pemahaman konsep arsitektur Client-Server.
  * Familiaritas dengan terminal emulator / Bash.
* **Estimasi Waktu Belajar:** 6 - 8 Jam (Termasuk eksperimen hands-on dan packet capture)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1. **Menganalisis dan Memetakan Aliran Data:** Membedakan peran Model OSI 7-Layer dan TCP/IP Stack dalam konteks pemecahan masalah (troubleshooting) sistem terdistribusi dan container networking.
2. **Mengelola Skema IP & Subnetting:** Menghitung alokasi alamat IPv4, subnet mask, dan notasi CIDR untuk perencanaan Virtual Private Cloud (VPC) dan alokasi pod network.
3. **Mendiagnosis Siklus Hidup Koneksi Transport:** Menganalisis mekanisme TCP 3-Way Handshake, TCP Termination (FIN/RST), socket state (`TIME_WAIT`, `CLOSE_WAIT`), serta implikasi performa UDP.
4. **Menelusuri Resolusi DNS & Lapisan Aplikasi:** Mengidentifikasi alur resolusi recursive/authoritative DNS, struktur DNS records (A, AAAA, CNAME, TXT, SRV), serta transisi protokol HTTP/1.1, HTTP/2, HTTP/3, dan TLS/mTLS.
5. **Melakukan Triage Jaringan Tingkat Mahir:** Menggunakan toolkit diagnostik standar industri (`ip`, `ss`, `dig`, `curl`, `tcpdump`, `traceroute`/`mtr`) untuk mengisolasi kegagalan konektivitas antar-layanan (service-to-service).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    [DEVOP'S NETWORKING FOUNDATION]
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
[Addressing & Layering]  [Transport & Routing]   [Application & Security]
  ├─ Model OSI vs TCP/IP   ├─ TCP (Reliable, ACK)   ├─ DNS Resolution & TTL
  ├─ IPv4, IPv6 & CIDR     ├─ UDP (Stateless, Fast) ├─ HTTP/1.1 vs HTTP/2 vs HTTP/3
  └─ Encapsulation / MTU   ├─ Socket States         └─ TLS 1.3 Handshake & mTLS
                           └─ NAT, PAT & Routing
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[Diagnostic & Packet Analysis]                   [DevOps Infrastructure Impact]
  ├─ ip route, ss, netstat                         ├─ Cloud VPC & Subnet Design
  ├─ dig, nslookup, mtr                            ├─ Kubernetes Pod/Service CIDR
  └─ tcpdump, Wireshark (PCAP)                     └─ Reverse Proxy & Load Balancer
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam paradigma modern berbasis Microservices, Cloud Native, dan Kubernetes, infrastruktur tidak lagi bersifat statis. Komponen aplikasi terpecah menjadi puluhan hingga ribuan container yang berkomunikasi melalui jaringan virtual (overlay network). 

Kegagalan sistem di lingkungan produksi sering kali diklasifikasikan secara keliru sebagai "bug aplikasi", padahal akar masalahnya berada pada lapisan jaringan:
* **"It's Always DNS":** Kesalahan konfigurasi recursive resolver, caching TTL yang terlalu lama, atau kehabisan socket port lokal dapat melumpuhkan klaster Kubernetes dalam hitungan detik.
* **Socket Exhaustion & Zombie States:** Lonjakan koneksi HTTP tanpa connection pooling menyebabkan ribuan socket terjebak dalam status `TIME_WAIT`, menghabiskan alokasi ephemeral port Linux kernel.
* **Security & Isolation:** Tanpa pemahaman kalkulasi subnet (CIDR) dan routing table, arsitek infrastruktur berisiko mengekspos database internal ke public internet atau mengalami benturan subnet (*CIDR overlap*) saat peering antar-VPC.

Seorang DevOps Engineer yang tidak memahami dasar-dasar jaringan hanya mampu menebak-nebak di balik dashboard monitoring. Pemahaman mendalam tentang paket jaringan memberikan kemampuan deterministik untuk membaca apa yang sebenarnya terjadi pada infrastruktur.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Model Referensi: OSI 7-Layer vs TCP/IP Stack
Model OSI memecah komunikasi jaringan menjadi 7 lapisan konseptual, sementara model TCP/IP menyederhanakannya menjadi 4/5 lapisan fungsional yang diimplementasikan langsung pada kernel Linux.

| Lapisan OSI | Lapisan TCP/IP | Unit Data Protokol (PDU) | Protokol & Entitas Terkait | Peran DevOps |
| :--- | :--- | :--- | :--- | :--- |
| **7. Application** | Application | Data / Payload | HTTP, DNS, gRPC, SSH | Debugging API, payload status code |
| **6. Presentation** | Application | Data | TLS/SSL, JSON, Protobuf | Sertifikat TLS, enkripsi transit |
| **5. Session** | Application | Data | Sockets, RPC | Manajemen session, connection pool |
| **4. Transport** | Transport | Segment (TCP) / Datagram (UDP) | TCP, UDP, SCTP, QUIC | Port, socket state (`ss`), MTU/MSS |
| **3. Network** | Internet | Packet | IPv4, IPv6, ICMP, BGP | Subnetting, Routing table, VPC |
| **2. Data Link** | Network Access | Frame | Ethernet, ARP, VLAN, VXLAN | CNI (Calico/Cilium), MAC address |
| **1. Physical** | Network Access | Bit | Kabel, Fiber, Radio | Hardware, NIC throughput |

### 2. Pengalamatan IP & Subnetting (CIDR)
* **IPv4:** Alamat numerik 32-bit yang dibagi menjadi 4 oktet (misal: `192.168.1.1`).
* **CIDR (Classless Inter-Domain Routing):** Notasi yang menggantikan pengkelasan lama (Class A, B, C) dengan merepresentasikan network prefix melalui tanda garis miring (slash `/X`), di mana `X` adalah jumlah bit yang dialokasikan untuk Network ID.
* **Kalkulasi Host:** Host yang dapat dialokasikan dihitung dengan rumus:
  $$\text{Jumlah Usable Host} = 2^{(32 - X)} - 2$$
  *(Dua alamat dialokasikan untuk Network Address dan Broadcast Address).*
  *Catatan Cloud (AWS/GCP):* Penyedia cloud umumnya mencadangkan 5 alamat IP pada setiap subnet (Network, Router/Gateway, DNS, Future use, Broadcast).

### 3. Protokol Lapisan Transport: TCP vs UDP
* **TCP (Transmission Control Protocol):** Berorientasi koneksi (*connection-oriented*), menjamin urutan data (*ordered*), dan handal (*reliable* melalui mekanisme retransmisi dan flow control).
* **UDP (User Datagram Protocol):** Nir-koneksi (*connectionless*), tanpa jaminan pengiriman atau urutan (*best-effort*), memiliki latency sangat rendah. Digunakan untuk DNS query, streaming, dan protokol QUIC (HTTP/3).

### 4. Protokol Resolusi Nama: DNS (Domain Name System)
DNS adalah basis data terdistribusi bertingkat hierarkis yang bertugas memetakan nama domain (*Human-readable*) ke alamat IP (*Machine-readable*).
* **Root Domain (`.`):** Puncak hierarki.
* **TLD (Top-Level Domain):** `.com`, `.org`, `.id`, `.internal`.
* **Authoritative Nameserver:** Server yang memegang basis data definitif untuk suatu zona DNS.
* **Recursive Resolver:** Server perantara (misal: `1.1.1.1`, CoreDNS di Kubernetes) yang bertugas menelusuri hierarki DNS atas nama client.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Proses Enkapsulasi dan Dekapsulasi Data
Ketika sebuah payload (misal: HTTP GET request) dikirim dari satu host ke host lain:
1. **Enkapsulasi (Outgoing):**
   * **Application:** Menghasilkan payload data mentah: `GET /healthz HTTP/1.1`.
   * **Transport:** Membungkus data dengan header TCP (Source Port, Destination Port: 443, Sequence Number). PDU menjadi **Segment**.
   * **Network:** Membungkus segment dengan header IP (Source IP, Destination IP, TTL). PDU menjadi **Packet**.
   * **Data Link:** Membungkus packet dengan header Ethernet (Source MAC, Destination MAC) dan trailing Frame Check Sequence (FCS). PDU menjadi **Frame**.
   * **Physical:** Frame diubah menjadi sinyal fisik (bit stream) melalui media transmisi.
2. **Dekapsulasi (Incoming):** Host penerima memvalidasi MAC address, mengupas header Ethernet, memvalidasi IP address, mengupas header IP, merekonstruksi stream TCP, dan menyerahkan payload HTTP ke proses aplikasi.

### 2. TCP 3-Way Handshake & Termination
Sebelum data dapat dikirimkan melalui TCP, koneksi harus dibentuk melalui siklus:
1. **Client -> Server (SYN):** Client memilih *Initial Sequence Number* (ISN) acak dan mengirim paket dengan flag `SYN=1`.
2. **Server -> Client (SYN-ACK):** Server merespons dengan flag `SYN=1`, `ACK=1`, menetapkan ISN miliknya sendiri, dan mengirim nilai `Acknowledgment Number = ISN_Client + 1`.
3. **Client -> Server (ACK):** Client mengirim paket dengan flag `ACK=1`, Sequence Number yang diperbarui, dan `Acknowledgment Number = ISN_Server + 1`. Socket berpindah ke status `ESTABLISHED`.

Untuk terminasi (4-Way Teardown):
1. Pengirim inisiator mengirimkan flag `FIN`.
2. Penerima merespons dengan `ACK` (masuk ke status `CLOSE_WAIT`).
3. Penerima mengirimkan flag `FIN` miliknya sendiri ketika siap menutup soket.
4. Pengirim merespons dengan `ACK` dan masuk ke status `TIME_WAIT` (umumnya bertahan selama $2 \times \text{MSL}$ atau ~60 detik untuk memastikan paket yang tertunda di jaringan tidak mencemari koneksi baru).

### 3. TLS 1.3 Handshake
Pada komunikasi HTTPS modern (TLS 1.3), proses pengamanan transmisi data berjalan dalam 1 round-trip time (1-RTT):
1. **Client Hello:** Mengirim daftar cipher suites yang didukung, versi TLS, ekstensi Server Name Indication (SNI), dan parameter ephemeral Diffie-Hellman key share.
2. **Server Hello & Encrypted Extensions:** Server memilih cipher suite, mengembalikan key share miliknya, mengirimkan sertifikat digital server (X.509), dan signature digital untuk autentikasi. Kunci enkripsi simetris (Session Key) langsung dihitung di kedua sisi.
3. **Finished:** Verifikasi integritas, kanal terenkripsi terbentuk, dan payload HTTP langsung ditransmisikan secara aman.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. TCP 3-Way Handshake, Transfer Data, & Teardown

```
CLIENT (e.g., 10.0.0.5)                                SERVER (e.g., 10.0.0.10:80)
   │                                                               │
   │ ────────────────── [1] SYN (Seq=X) ─────────────────────────> │ LISTEN
   │ <───────────────── [2] SYN-ACK (Seq=Y, Ack=X+1) ───────────── │ SYN-RECEIVED
ESTABLISHED                                                        │
   │ ────────────────── [3] ACK (Seq=X+1, Ack=Y+1) ──────────────> │ ESTABLISHED
   │                                                               │
   │ ══════════════════ DATA TRANSMISSION (HTTP) ═════════════════ │
   │                                                               │
   │ ────────────────── [4] FIN (Seq=X+n, Ack=Y+m) ──────────────> │
FIN-WAIT-1                                                         │
   │ <───────────────── [5] ACK (Ack=X+n+1) ────────────────────── │ CLOSE-WAIT
FIN-WAIT-2                                                         │
   │ <───────────────── [6] FIN (Seq=Y+m) ──────────────────────── │ LAST-ACK
TIME-WAIT (Wait 2*MSL)                                             │
   │ ────────────────── [7] ACK (Ack=Y+m+1) ──────────────────────> │
   │                                                               │ CLOSED
 CLOSED
```

### 2. Alur Resolusi DNS Rekursif dari Sisi Infrastruktur

```
 +---------------------------------------------------------------+
 | Klien DevOps / Workload Pod                                   |
 | (Contoh: Menjalankan 'curl https://api.production.internal')  |
 +-------------------------------+-------------------------------+
                                 │ Query: api.production.internal
                                 ▼
 +---------------------------------------------------------------+
 | Local / Recursive DNS Resolver (CoreDNS / VPC DNS: 10.0.0.2)  |
 +-------+-----------------------+-------------------------------+
         │ 1. Cek Cache Lokal    │
         │    (Miss)             │ 2. Query Root Server (.)
         │                       ▼
         │               +-------------------------------+
         │               | Root DNS Server               |
         │               | (Delegasi ke TLD .internal)   |
         │               +---------------+---------------+
         │                               │
         │ <─────────────────────────────+
         │
         │ 3. Query TLD Server
         ▼
 +-------------------------------+
 | TLD DNS Server (.internal)    |
 | (Delegasi ke Authoritative NS)|
 +-------+-----------------------+
         │
         │ <─────────────────────────────+
         │
         │ 4. Query Authoritative Name Server
         ▼
 +-------------------------------+
 | Authoritative Name Server     |
 | Record: A -> 172.16.50.4      |
 +-------+-----------------------+
         │
         │ 5. Jawaban Resolusi (IP: 172.16.50.4, TTL: 300)
         ▼
 +---------------------------------------------------------------+
 | Resolver menyimpan ke cache & mengembalikan IP ke Klien       |
 +---------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah operasi dasar CLI untuk menginspeksi konfigurasi jaringan lokal pada Linux node:

### 1. Memeriksa Alamat IP dan Interface
Gunakan perintah modern `ip` (menggantikan `ifconfig` yang telah *deprecated*):
```bash
# Menampilkan seluruh interface jaringan beserta IP dan statusnya
ip -br addr show
```
*Output Representatif:*
```text
lo               UNKNOWN        127.0.0.1/8 ::1/128 
eth0             UP             192.168.1.15/24 fe80::a00:27ff:fe4e:66a1/64 
docker0          DOWN           172.17.0.1/16 
```
*Penjelasan:* `eth0` memiliki alamat IP `192.168.1.15` dengan subnet mask `/24` (255.255.255.0).

### 2. Memeriksa Routing Table
Pastikan default gateway dikonfigurasi dengan benar:
```bash
ip route show
```
*Output Representatif:*
```text
default via 192.168.1.1 dev eth0 proto dhcp metric 100 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown 
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.15 metric 100 
```
*Penjelasan:* Semua paket yang tujuannya di luar subnet `192.168.1.0/24` akan dilempar ke default gateway `192.168.1.1` melalui interface `eth0`.

### 3. Menelusuri Resolusi DNS secara Terperinci
Gunakan `dig` untuk menginspeksi catatan DNS:
```bash
dig +noall +answer +stats api.github.com
```
*Output Representatif:*
```text
api.github.com.         60      IN      CNAME   github.com.
github.com.             60      IN      A       140.82.121.4
;; Query time: 14 msec
;; SERVER: 127.0.0.53#53(127.0.0.53)
;; WHEN: Mon Jan 15 10:00:00 UTC 2024
;; MSG SIZE  rcvd: 76
```
*Penjelasan:* Domain `api.github.com` menggunakan alias `CNAME` ke `github.com` dan akhirnya diresolusikan ke alamat IPv4 `140.82.121.4` dengan Time-To-Live (TTL) tersisa 60 detik. Resolusi ditangani oleh local resolver `127.0.0.53` port `53`.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario: Investigasi "HTTP 502 Bad Gateway" Antara Reverse Proxy (Nginx) dan Backend Service (Go Application)

#### 1. Masalah
Nginx bertindak sebagai load balancer internal pada `10.0.10.5`. Client menerima error `502 Bad Gateway` saat memanggil endpoint API yang seharusnya diteruskan ke backend server pada `10.0.10.20:8080`.

#### 2. Langkah Triage Lapangan (Step-by-Step)

**Langkah A: Verifikasi Latensi dan Konfigurasi Port Menggunakan `curl`**
Lakukan pengujian langsung dari instans Nginx menuju backend server secara verbose:
```bash
curl -Iv --connect-timeout 5 http://10.0.10.20:8080/healthz
```
*Output:*
```text
* Trying 10.0.10.20:8080...
* connect to 10.0.10.20 port 8080 failed: Connection refused
* Failed to connect to 10.0.10.20 port 8080: Connection refused
* Closing connection 0
curl: (7) Failed to connect to 10.0.10.20 port 8080: Connection refused
```
*Analisis:* `Connection refused` (bukan *Connection timed out*) berarti paket SYN berhasil mencapai host target, namun host target segera membalas dengan paket TCP berflag `RST` (Reset). Ini mengindikasikan bahwa host hidup, firewall mengizinkan paket lewat, namun **tidak ada proses yang mendengarkan (listen) pada port tersebut**.

**Langkah B: Periksa Socket Binding pada Backend Server (`10.0.10.20`)**
Masuk ke backend host dan periksa socket yang aktif menggunakan utility `ss`:
```bash
# -t (TCP), -u (UDP), -l (Listening), -p (Process), -n (Numeric)
sudo ss -tulpn | grep 8080
```
*Output Kasus Bermasalah:*
```text
tcp   LISTEN 0      128        127.0.0.1:8080       0.0.0.0:*    users:(("app",pid=4213,fd=3))
```
*Root Cause Ditemukan:* Aplikasi backend mendengarkan pada interface loopback (`127.0.0.1:8080`), bukan pada semua interface (`0.0.0.0:8080` atau `10.0.10.20:8080`). Akibatnya, paket yang datang dari interface private network (`eth0`) ditolak secara instan oleh kernel Linux.

**Langkah C: Pembuktian Paket Menggunakan `tcpdump`**
Jalankan packet capture pada backend server saat request dikirim dari Nginx untuk mengonfirmasi respons kernel:
```bash
sudo tcpdump -nnvv -i eth0 port 8080
```
*Capture Output:*
```text
10:15:02.102341 IP (tos 0x0, ttl 64, id 54321, offset 0, flags [DF], proto TCP (6), length 60)
    10.0.10.5.49210 > 10.0.10.20.8080: Flags [S], cksum 0x1f2a (correct), seq 1002345, win 64240, options [mss 1460,sackOK,TS val 214589 ecr 0,nop,wscale 7], length 0
10:15:02.102390 IP (tos 0x0, ttl 64, id 0, offset 0, flags [DF], proto TCP (6), length 40)
    10.0.10.20.8080 > 10.0.10.5.49210: Flags [R.], cksum 0x6b11 (correct), seq 0, ack 1002346, win 0, length 0
```
*Penjelasan:* Nginx mengirim paket `[S]` (SYN). Backend langsung membalas dengan `[R.]` (RST/ACK) karena tidak ada socket listening publik.

**Langkah D: Solusi**
Ubah konfigurasi bind host pada file service backend dari `HOST=127.0.0.1` menjadi `HOST=0.0.0.0`, restart service, dan verifikasi ulang status socket:
```bash
sudo ss -tulpn | grep 8080
```
*Output Normal:*
```text
tcp   LISTEN 0      128          *:8080             *:*    users:(("app",pid=4350,fd=3))
```
Koneksi dari Nginx kini berhasil dan error 502 terselesaikan.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Keputusan Arsitektur | Opsi A | Opsi B | Trade-off / Implikasi |
| :--- | :--- | :--- | :--- |
| **Protokol Lapisan Transport** | **TCP** (Stateful, Guaranteed) | **UDP / QUIC** (Stateless, Fast) | TCP menjamin delivery namun rentan terhadap *head-of-line blocking* dan handshake latency. UDP/QUIC memangkas connection setup time (0-RTT), namun membutuhkan konfigurasi router/firewall yang mengizinkan lalu lintas UDP dinamis. |
| **Pemberhentian Enkripsi (TLS)** | **Edge Termination** (TLS dilepas di Ingress/LB) | **End-to-End TLS / mTLS** (Terenkripsi hingga Pod) | Edge termination menghemat resource CPU backend dan mempermudah inspection, namun lalu lintas internal rentan terhadap serangan sniffing. End-to-End/mTLS memberikan *Zero-Trust Security* maksimal tetapi menambah overhead enkripsi/dekripsi dan kompleksitas manajemen cert lifecycle. |
| **Alokasi Ukuran Subnet (CIDR)** | **Subnet Besar** (misal `/16`, 65K IP) | **Subnet Kecil** (misal `/24`, 254 IP) | Subnet besar mencegah kehabisan IP pod/node, namun memperluas *blast radius* broadcast/ARP storm dan membatasi jumlah peering VPC. Subnet terpecah rapi meningkatkan isolasi keamanan, tetapi berisiko tinggi mengalami kehabisan alamat IP (*IP exhaustion*). |
| **Protokol Aplikasi** | **HTTP/1.1** (Multiplexed by Connection) | **HTTP/2 / gRPC** (Single Connection Multiplex) | HTTP/1.1 sederhana dan kompatibel dengan semua middleware, namun membutuhkan banyak koneksi TCP paralel. HTTP/2 menghemat overhead soket melalui multiplexing, namun jika terjadi packet loss di tingkat TCP, seluruh stream di koneksi tersebut akan tersendat (*TCP Head-of-Line Blocking*). |

---

## SEKSI 11 — BEST PRACTICES

### 1. Connection Management & Ephemeral Ports
* **Aktifkan HTTP Keep-Alive & Connection Pooling:** Jangan biarkan microservices membuka koneksi TCP baru untuk setiap HTTP request. Gunakan persistent connection pool pada HTTP client aplikasi.
* **Optimasi Kernel untuk Beban Tinggi:** Konfigurasi batas ephemeral port range dan reuse socket pada `/etc/sysctl.conf`:
  ```ini
  # Perluas jangkauan port lokal untuk outgoing connection
  net.ipv4.ip_local_port_range = 10240 65535
  # Izinkan kernel mendaur ulang soket TIME_WAIT untuk koneksi keluar yang aman
  net.ipv4.tcp_tw_reuse = 1
  # Atur waktu tunggu FIN timeout dari 60 detik menjadi 30 detik
  net.ipv4.tcp_fin_timeout = 30
  ```

### 2. Konfigurasi DNS di Lingkungan Cloud & Container
* **Hindari DNS TTL = 0:** Menyetel TTL 0 mematikan cache dan menyebabkan kebanjiran trafik (*DNS flood*) ke resolver atau CoreDNS, meningkatkan latency hingga 30-50%.
* **Konfigurasi `ndots` pada Linux/Kubernetes:** Default `ndots:5` pada `/etc/resolv.conf` di Kubernetes dapat memicu 4-5 kali kegagalan query DNS eksternal sebelum mencari domain absolut. Tambahkan trailing dot pada endpoint eksternal (`api.stripe.com.`) untuk mengabaikan search path internal.

### 3. Keamanan Port dan Jaringan Minimalis
* **Terapkan Prinsip Least Privilege:** Tutup seluruh port masuk (ingress) secara default menggunakan Linux firewall (`nftables` / `iptables`) atau Security Group. Hanya buka port aplikasi (misal: 80, 443).
* **Jangan Bind Service ke `0.0.0.0` Tanpa Autentikasi:** Database (seperti Redis, PostgreSQL, ElasticSearch) wajib di-bind ke IP privat lokal atau loopback jika hanya diakses oleh aplikasi lokal pada mesin yang sama.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. MTU Mismatch & Black Hole Connections
* **Gejala:** Ping dengan ukuran kecil (`ping google.com`) berhasil, koneksi SSH awal berhasil, namun saat menjalankan `git clone` atau transfer file via HTTP/HTTPS berukuran besar, koneksi tiba-tiba *hang* / macet tanpa pesan error.
* **Penyebab:** Masalah *Maximum Transmission Unit* (MTU). Jaringan fisik menggunakan standar 1500 byte, namun jaringan overlay (seperti VXLAN di Docker/Kubernetes atau IPSec VPN) membutuhkan header tambahan (misal: 50 byte). Jika MTU interface virtual disetel 1500, paket melebihi batas dan jika ICMP tipe 3 kode 4 (*Fragmentation Needed*) diblokir oleh firewall, mekanisme *Path MTU Discovery (PMTUD)* gagal total.
* **Solusi:** Setel MTU yang sesuai pada interface overlay (contoh: MTU 1450) atau izinkan transit paket ICMP.

### 2. Mengabaikan Perbedaan "Connection Refused" vs "Connection Timed Out"
* **Salah Kaprah:** Mengira kedua pesan error ini memiliki penyebab yang sama (yaitu server mati).
* **Fakta Teknis:**
  * `Connection refused`: Paket mencapai target host, host merespons dengan TCP `RST`. Masalah: Port salah atau daemon aplikasi mati/tidak listening.
  * `Connection timed out`: Paket SYN dikirim tetapi tidak ada respons sama sekali (silent drop). Masalah: Firewall memblokir paket, routing table salah, security group tidak mengizinkan IP pengirim, atau target IP tidak terjangkau.

### 3. Tumpang Tindih Subnet (CIDR Overlap)
* **Gejala:** Setelah mengonfigurasi VPN atau VPC Peering antar dua lingkungan (misal: On-Premise ke AWS VPC), paket dari host internal tidak pernah sampai ke server cloud.
* **Penyebab:** Kedua jaringan menggunakan blok CIDR yang identik, misalnya sama-sama menggunakan `192.168.1.0/24`. Kernel tidak dapat merutekan paket karena tujuan dianggap berada pada jaringan lokal mesin itu sendiri.
* **Solusi:** Rencanakan skema IP Addressing sejak awal. Gunakan segmen RFC 1918 yang berbeda (misal: On-premise menggunakan `10.10.0.0/16`, AWS VPC menggunakan `172.20.0.0/16`).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Kalkulasi Subnet CIDR (Tingkat: Dasar)
Diberikan alokasi IP Cloud VPC `10.100.0.0/22`.
1. Berapa total alamat IP mentah yang tercakup dalam blok CIDR tersebut?
2. Anda diminta membagi blok tersebut menjadi 4 buah subnet dengan ukuran yang sama besar untuk zona ketersediaan (*Availability Zone*) yang berbeda.
   * Berapa subnet mask baru dalam format CIDR?
   * Tuliskan network address, range usable IP, dan broadcast address untuk masing-masing ke-4 subnet tersebut!

### Latihan 2: Packet Capture Analisis Handshake (Tingkat: Menengah)
1. Buka dua jendela terminal pada mesin Linux Anda.
2. Pada Terminal 1, jalankan `tcpdump` untuk menangkap trafik loopback pada port 9999:
   ```bash
   sudo tcpdump -i lo -nnvv "port 9999"
   ```
3. Pada Terminal 2, buat pendengar (*listener*) TCP dummy menggunakan `nc` (Netcat):
   ```bash
   nc -l 127.0.0.1 9999
   ```
4. Pada Terminal 3 (atau tab baru), hubungkan ke listener tersebut:
   ```bash
   nc 127.0.0.1 9999
   ```
5. Ketik pesan `"Halo DevOps"`, lalu tekan `Ctrl+C` pada Terminal 3 untuk menutup koneksi.
6. **Tugas Anda:** Analisis output `tcpdump` pada Terminal 1. Identifikasi baris-baris flag `[S]` (SYN), `[S.]` (SYN-ACK), `[.]` (ACK), `[P.]` (Data Push), dan `[F.]` (FIN) beserta pergerakan sequence number-nya!

### Latihan 3: Mendiagnosis DNS & Latensi Jaringan (Tingkat: Lanjutan)
1. Pasang package `mtr` dan `bind-utils` (atau `dnsutils`).
2. Jalankan perintah diagnostik DNS secara berlapis ke domain eksternal:
   ```bash
   dig +trace google.com
   ```
   Petakan setiap langkah delegasi dari Root Server hingga Authoritative Server yang menjawab query Anda.
3. Jalankan pengujian degradasi rute menggunakan `mtr`:
   ```bash
   mtr --report-cycles 10 --report 1.1.1.1
   ```
   Identifikasi hop mana yang memiliki latency tertinggi atau mengalami packet loss.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

#### 1. Pada model OSI, lapisan manakah yang bertanggung jawab langsung untuk penanganan enkripsi TLS/SSL dan encoding representasi data?
* A. Network Layer (Layer 3)
* B. Transport Layer (Layer 4)
* C. Presentation Layer (Layer 6)
* D. Data Link Layer (Layer 2)

#### 2. Sebuah subnet VPC dikonfigurasi dengan blok `172.16.8.0/21`. Berapakah jumlah alamat IP yang dapat secara valid diberikan kepada instans virtual host (mengabaikan pencadangan cloud provider)?
* A. 2046
* B. 2048
* C. 1022
* D. 510

#### 3. Seorang engineer mendapati aplikasi backend mencetak jutaan error dan socket keluar baru gagal dibuka. Eksekusi `ss -s` menunjukkan ribuan soket berada pada status `TIME_WAIT`. Manakah intervensi kernel sysctl berikut yang paling tepat untuk mengatasi masalah daur ulang socket keluar tersebut tanpa mengorbankan integritas TCP?
* A. `net.ipv4.tcp_syncookies = 0`
* B. `net.ipv4.tcp_tw_reuse = 1`
* C. `net.ipv4.ip_forward = 1`
* D. `net.ipv4.icmp_echo_ignore_all = 1`

#### 4. Klien melaporkan pesan kesalahan `curl: (28) Connection timed out after 5001 milliseconds`. Di antara kemungkinan berikut, manakah skenario yang paling mungkin merepresentasikan akar masalah teknis?
* A. Port backend salah dan server merespons langsung dengan paket `RST`.
* B. Host target tidak menjalankan proses listener pada port yang diminta.
* C. Paket SYN dijatuhkan (*silently dropped*) oleh Network Access Control List (NACL) atau Firewall.
* D. Domain name gagal diresolusikan oleh DNS resolver lokal (*NXDOMAIN*).

#### 5. Apa perbedaan fundamental antara HTTP/1.1 pipelining dan HTTP/2 multiplexing?
* A. HTTP/1.1 membolehkan transmisi request paralel pada satu koneksi TCP tanpa terpengaruh urutan pemrosesan balasan (*out-of-order response*).
* B. HTTP/2 memecah pesan menjadi frame biner independen yang dapat dikirim dan dirangkai kembali secara konkuren melalui satu koneksi TCP tunggal.
* C. HTTP/2 mengharuskan pembuatan koneksi TCP baru untuk setiap transfer file biner.
* D. HTTP/1.1 mengenkripsi seluruh header secara default menggunakan algoritma HPACK.

---

### Kunci Jawaban & Rasionalisasi

1. **Jawaban: C (Presentation Layer).**
   * *Rasional:* Secara teoritis model OSI, Presentation Layer (Layer 6) menangani sintaksis, format enkripsi data (TLS/SSL), kompresi, dan serialisasi objek (seperti JSON/ASN.1).
2. **Jawaban: A (2046).**
   * *Rasional:* Notasi `/21` berarti tersisa $32 - 21 = 11$ bit untuk host. Total IP adalah $2^{11} = 2048$. Usable IP dikurangi Network Address (1) dan Broadcast Address (1): $2048 - 2 = 2046$.
3. **Jawaban: B (`net.ipv4.tcp_tw_reuse = 1`).**
   * *Rasional:* Opsi `tcp_tw_reuse` mengizinkan kernel untuk menggunakan kembali soket berstatus `TIME_WAIT` untuk koneksi outgoing baru jika dinilai aman secara protokol (berdasarkan validasi timestamp TCP).
4. **Jawaban: C (Paket SYN dijatuhkan oleh NACL/Firewall).**
   * *Rasional:* `Connection timed out` terjadi ketika klien mengirim SYN berulang kali tanpa menerima balasan (SYN-ACK ataupun RST), yang merupakan perilaku khas packet dropping oleh firewall. Kegagalan DNS akan memicu error resolusi, sedangkan tidak ada listener akan menghasilkan respons instan `Connection refused` (RST).
5. **Jawaban: B (HTTP/2 memecah pesan menjadi frame biner multiplexed).**
   * *Rasional:* HTTP/2 memperkenalkan Binary Framing Layer yang memungkinkan banyak stream komunikasi berjalan bersamaan di atas satu koneksi TCP tunggal tanpa kendala Head-of-Line blocking pada level HTTP.

---

### Checklist Evaluasi Diri

| Kriteria Kemampuan | Sudah Paham | Butuh Review | Tindakan Lanjutan |
| :--- | :---: | :---: | :--- |
| Saya dapat menghitung usable IP dan broadcast dari sembarang notasi CIDR tanpa kalkulator online. | [ ] | [ ] | Kerjakan ulang Latihan 1 dengan variasi CIDR `/20`, `/27`, `/29`. |
| Saya dapat membedakan secara instan akar masalah antara error "Connection Refused" dan "Connection Timed Out". | [ ] | [ ] | Review diagram alur TCP 3-Way Handshake pada Seksi 07. |
| Saya mampu mengoperasikan `ss`, `ip`, `curl -Iv`, dan `dig` untuk menelusuri kerusakan koneksi antar container. | [ ] | [ ] | Jalankan Latihan Hands-on 2 & 3 di terminal lokal Anda. |
| Saya memahami siklus status socket TCP (`ESTABLISHED`, `TIME_WAIT`, `CLOSE_WAIT`) dan penanganannya pada Linux. | [ ] | [ ] | Eksplorasi isi dari file virtual `/proc/net/tcp`. |

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Standar Protokol IETF (RFC Resmi):**
  * [RFC 793](https://datatracker.ietf.org/doc/html/rfc793) — Transmission Control Protocol (TCP) Specification.
  * [RFC 1035](https://datatracker.ietf.org/doc/html/rfc1035) — Domain Names - Implementation and Specification.
  * [RFC 8446](https://datatracker.ietf.org/doc/html/rfc8446) — The Transport Layer Security (TLS) Protocol Version 1.3.
  * [RFC 9113](https://datatracker.ietf.org/doc/html/rfc9113) — HTTP/2 Specification.
* **Buku Referensi Standar Industri:**
  * *TCP/IP Illustrated, Volume 1: The Protocols* oleh W. Richard Stevens.
  * *High Performance Browser Networking* oleh Ilya Grigorik (Wajib dibaca untuk pemahaman optimasi latency, TLS, TCP, dan HTTP/2).
  * *Systems Performance: Enterprise and the Cloud* oleh Brendan Gregg (Bab Jaringan).
* **Dokumentasi Kernel Linux:**
  * [Linux Kernel IP Sysctl Documentation](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt) — Panduan resmi parameter tuning performa jaringan Linux.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Lapisan Jaringan:** DevOps beroperasi terutama pada Layer 3 (IP/Routing), Layer 4 (TCP/UDP, Ports, Sockets), dan Layer 7 (DNS, HTTP/S, TLS). Pemetaan masalah selalu dimulai dari penentuan lapisan mana yang gagal.
2. **CIDR & Subnetting:** Alamat IP adalah sumber daya berhingga. Menguasai perhitungan biner CIDR bukan sekadar kemampuan administratif, melainkan fondasi dalam mengonfigurasi VPC, firewall rules, dan Pod CIDR pada cluster orchestration.
3. **Karakteristik TCP:** Keandalan TCP datang bersama overhead state machine. Status soket seperti `TIME_WAIT` dan `CLOSE_WAIT` merupakan indikator kesehatan koneksi aplikasi yang kritis dalam lingkungan high-throughput.
4. **Arsitektur DNS:** DNS bukan sekadar "buku telepon internet", melainkan mekanisme inti *service discovery* di cloud native. Memahami alur rekursif dan manajemen TTL mencegah insiden down sistem akibat latensi resolusi.
5. **Tooling Terpadu:** Penguasaan utilitas diagnostik CLI (`ip`, `ss`, `dig`, `curl`, `tcpdump`) memberikan visibilitas mutlak atas transmisi bit dan frame, menjembatani jarak antara kode aplikasi dan platform infrastruktur.

---

## SEKSI 17 — GLOSARIUM

* **CIDR (Classless Inter-Domain Routing):** Skema pengalokasian IP modern yang fleksibel menggunakan format network prefix bit length (misal: `/24`).
* **MTU (Maximum Transmission Unit):** Ukuran paket data terbesar (dalam satuan byte) yang dapat ditransmisikan melalui interface jaringan tanpa fragmentasi.
* **Socket:** Kombinasi unik antara IP Address, Nomor Port, dan Protokol (TCP/UDP) yang membentuk titik akhir komunikasi bidirectional pada sistem operasi.
* **Ephemeral Port:** Jangkauan port sementara berjarak nomor tinggi (biasanya 32768–60999 pada Linux) yang dialokasikan oleh OS untuk koneksi keluar (*client-side*).
* **SNI (Server Name Indication):** Ekstensi protokol TLS yang menyertakan nama domain hostname saat Client Hello, memungkinkan satu IP server menghosting banyak sertifikat SSL/TLS untuk domain berbeda.
* **TTL (Time-To-Live):** 
  * *Pada IP Header:* Counter batas lompatan router (*hop limit*) untuk mencegah paket berputar selamanya dalam jaringan.
  * *Pada DNS:* Durasi waktu (dalam detik) di mana cache DNS diizinkan menyimpan record sebelum meminta pembaruan ke authoritative nameserver.
* **ALPN (Application-Layer Protocol Negotiation):** Ekstensi TLS yang menegosiasikan protokol aplikasi mana yang akan digunakan di dalam tunnel terenkripsi (misal: HTTP/1.1 vs HTTP/2) tanpa memakan RTT tambahan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Kritis Mahasiswa (Common Sticking Points):**
  * Pemula sering kali tertukar antara flag TCP `FIN` dan `RST`. Tegaskan bahwa `FIN` adalah penutupan percakapan secara sopan melalui persetujuan dua arah, sedangkan `RST` adalah pemutusan sepihak secara mendadak karena anomali atau ketiadaan socket target.
  * Konsep `CLOSE_WAIT` vs `TIME_WAIT`: Tekankan bahwa tumpukan soket `CLOSE_WAIT` hampir selalu merupakan **bug pada kode aplikasi** yang lupa menutup stream (`socket.close()`), sedangkan tumpukan `TIME_WAIT` adalah fenomena normal arsitektur TCP yang dapat dioptimasi melalui tuning sysctl atau connection reuse.
* **Metodologi Pengajaran Lab:**
  * Jangan biarkan peserta hanya membaca perintah. Wajibkan penggunaan virtual machine (seperti Ubuntu VM via Multipass / Vagrant) untuk mengeksekusi langsung `tcpdump`.
  * Lakukan demonstrasi langsung dengan memblokir port via `iptables -A INPUT -p tcp --dport 8080 -j DROP` vs `iptables -A INPUT -p tcp --dport 8080 -j REJECT` agar peserta melihat perbedaan nyata output pada sisi client (`timed out` vs `connection refused`).

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 15 Januari 2024 | Senior Technical Curriculum Architect | Rilis awal dokumen kurikulum lengkap dengan format 20 Seksi Standar. |
| **v1.1.0** | 20 Februari 2024 | Core Infrastructure Team | Penambahan diagram handshake TLS 1.3 dan pendalaman kasus MTU Mismatch. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `[Bab 02 Modul 03 — Linux Shell Scripting, Automation & Process Management]`
* **Modul Saat Ini:** `[Bab 03 Modul 01 — Jaringan Komputer & Protokol Inti DevOps]`
* **Modul Berikutnya:** `[Bab 03 Modul 02 — Web Server, Reverse Proxy & Load Balancing Architecture (Nginx & HAProxy)]`