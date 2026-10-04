# BAB 03: Quiz, Challenge, & Knowledge Check
**Jaringan Komputer & Protokol Inti DevOps**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Enkapsulasi dan Overhead Jaringan Overlay**  
   Jelaskan alur perjalanan paket data dari layer aplikasi hingga layer fisik berdasarkan model TCP/IP. Dalam konteks container networking (misalnya overlay network berbasis VXLAN pada Kubernetes), jelaskan di layer mana enkapsulasi ganda terjadi dan bagaimana penambahan header tersebut memengaruhi ukuran payload efektif serta kinerja throughput jaringan.

2. **Mekanisme TCP Handshake dan Siklus Hidup Koneksi**  
   Uraikan secara detail alur *3-Way Handshake* (SYN, SYN-ACK, ACK) saat inisiasi koneksi dan *4-Way Handshake* (FIN, ACK, FIN, ACK) saat terminasi koneksi TCP. Mengapa TCP mengimplementasikan status `TIME_WAIT` pada pihak yang menginisiasi penutupan koneksi, dan mengapa durasinya standarnya diatur sebesar $2 \times \text{MSL}$ (Maximum Segment Lifetime)?

3. **Hierarki dan Alur Resolusi DNS**  
   Bedah alur resolusi DNS dari perspektif klien (aplikasi/server) saat mengakses domain fully qualified (`api.production.internal` atau `app.example.com`). Jelaskan perbedaan mendasar antara *Recursive Resolver* dan *Authoritative Name Server*, serta bagaimana mekanisme *Time-To-Live* (TTL) dan layer caching (OS cache, resolver cache, application-level cache) memengaruhi propagasi perubahan IP record.

4. **Evolusi Protokol: HTTP/1.1 vs HTTP/2 vs HTTP/3**  
   Bandingkan arsitektur transfer data antara HTTP/1.1 (dengan *keep-alive* dan *pipelining*), HTTP/2 (berbasis binary framing dan stream multiplexing di atas TCP), dan HTTP/3 (berbasis QUIC di atas UDP). Fokuskan analisis Anda pada fenomena *Head-of-Line (HoL) Blocking*—jelaskan bagaimana HTTP/2 menyelesaikan HoL blocking di layer aplikasi namun masih rentan terhadap HoL blocking di layer transport, serta bagaimana HTTP/3 mengeliminasi keduanya secara permanen.

5. **Load Balancing: Karakteristik L4 vs L7**  
   Jelaskan perbedaan fundamental dalam pemrosesan paket antara Layer 4 (Transport Level, mis. IP Hash/TCP stream balancing) dan Layer 7 (Application Level, mis. Reverse Proxy HTTP/gRPC). Apa konsekuensi operasional pemilihan L4 vs L7 terhadap kebutuhan *TLS Termination*, latensi pemrosesan CPU, kemampuan routing berbasis konten (URL path, header, cookie), dan visibilitas IP asli klien (*client IP preservation* via PROXY protocol vs `X-Forwarded-For`)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Ephemeral Port Exhaustion dan Kernel Socket Tuning**  
   Sebuah microservice yang bertindak sebagai API Gateway memanggil ratusan service hilir via HTTP/1.1 tanpa menggunakan *HTTP Connection Pooling*. Dalam kondisi *traffic spike*, API Gateway mulai memunculkan eror `Cannot assign requested address` (EADDRNOTAVAIL).  
   * Analisis akar penyebab insiden ini dari perspektif alokasi port efemeral dan siklus socket state.
   * Parameter kernel Linux apa (`sysctl`) yang mengontrol batas port efemeral dan daur ulang socket `TIME_WAIT`?
   * Apa risiko arsitektural jika Anda mengaktifkan `net.ipv4.tcp_tw_reuse` di lingkungan NAT publik?

2. **Path MTU Discovery (PMTUD) Failure & "Black Hole" Connections**  
   Klien melaporkan bahwa koneksi ke server via VPN/tunneling mengalami fenomena aneh: koneksi SSH atau HTTP awal (handshake) berhasil secara instan, namun ketika klien meminta payload data besar (misalnya respons JSON berukuran > 2 KB atau transfer file), koneksi mengalami *hang* atau *timeout* tanpa pesan eror yang jelas.  
   * Jelaskan patologi masalah ini dari sudut pandang *Maximum Transmission Unit* (MTU), *Maximum Segment Size* (MSS), dan ICMP Type 3 Code 4 (*Destination Unreachable, Fragmentation Needed*).
   * Bagaimana drop paket ICMP oleh firewall pihak ketiga menyebabkan terbentuknya *PMTU Black Hole*?
   * Langkah konfigurasi mitigasi apa yang dapat diterapkan pada level router/proxy (misalnya TCP MSS Clamping)?

3. **Anomali Resolusi DNS pada Runtimes & Container Orchestration**  
   Dalam kluster microservices, sebuah service berbasis Node.js atau Java (JVM) mengalami kegagalan komunikasi ke service dependensi setelah dependensi tersebut di-*redeploy* dan mendapatkan IP Pod baru, padahal CoreDNS kluster berjalan normal dan mengembalikan IP baru secara akurat.  
   * Mengapa JVM secara default mengunci (*cache forever*) DNS lookup dan bagaimana cara mengonfigurasi `networkaddress.cache.ttl`?
   * Bagaimana implementasi opsi `ndots:5` pada `/etc/resolv.conf` di lingkungan Linux/Kubernetes dapat melipatgandakan latensi DNS query dan membebani upstream DNS server?

4. **Mekanisme TLS Handshake, ALPN, dan SNI**  
   Bedah alur negosiasi enkripsi TLS 1.3 dibandingkan dengan TLS 1.2 dalam konteks pengurangan *Round Trip Time* (1-RTT vs 2-RTT dan 0-RTT Resumption). Jelaskan fungsi dari:
   * **SNI (Server Name Indication)**: Mengapa SNI krusial dalam lingkungan multi-tenant/virtual hosting modern?
   * **ALPN (Application-Layer Protocol Negotiation)**: Bagaimana ALPN memungkinkan client dan server menegosiasikan upgrade ke protokol HTTP/2 atau gRPC sebelum transmisi data aplikasi dimulai?

5. **Saturasi Linux Conntrack Table pada High-Throughput Cluster**  
   Host Kubernetes yang menangani ribuan koneksi per detik tiba-tiba mulai menolak paket baru secara sporadis, dengan log kernel memunculkan pesan: `nf_conntrack: table full, dropping packet`.  
   * Jelaskan peran modul `netfilter conntrack` dalam arsitektur Linux networking dan implementasi iptables/IPVS.
   * Mengapa operasi NAT (SNAT/DNAT) membutuhkan pelacakan koneksi (*connection tracking*)?
   * Rumuskan langkah-langkah mitigasi teknis, mulai dari kalkulasi penyesuaian nilai `nf_conntrack_max` dan `nf_conntrack_buckets` hingga optimasi socket timeout.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Skala Besar: Latensi Spiking & HTTP 504 pada Flash Sale
* **Latar Belakang**: Sebuah platform e-commerce meluncurkan flash sale. Arsitektur terdiri dari AWS ALB (Layer 7) yang mendistribusikan traffic ke kumpulan Nginx reverse proxy, yang kemudian meneruskannya ke backend application server (Go). Tiga menit setelah sale dibuka, traffic melonjak dari 10.000 RPS menjadi 95.000 RPS. ALB mulai mengembalikan eror `HTTP 504 Gateway Timeout` secara masif ke pengguna.
* **Gejala Sistem**:
  * Metrik CPU dan Memory pada Nginx proxy berada pada batas aman (CPU ~35%, Memory ~40%).
  * Backend Application Server Go memiliki utilisasi CPU yang sangat rendah (~10%).
  * Output `netstat -s | grep -i listen` pada server Nginx menunjukkan angka `times the listen queue of a socket overflowed` yang terus bertambah cepat.
  * Log error Nginx mencatat: `connect() to backend failed (110: Connection timed out)`.
* **Tugas Diagnostik**:
  1. Analisis titik kegagalan (*bottleneck*) utama dalam rantai koneksi TCP antara ALB, Nginx, dan Backend.
  2. Jelaskan korelasi antara parameter kernel Linux `net.core.somaxconn`, `tcp_max_syn_backlog`, dan direktif `listen backlog` pada Nginx dalam memicu insiden antrean socket (*SYN drop*) ini.
  3. Berikan rencana remediasi komprehensif, mencakup kernel sysctl, konfigurasi `keepalive` pada Nginx upstream, dan scaling architecture.

---

### Skenario B: Connection Exhaustion & Data Inconsistency akibat Half-Open Sockets
* **Latar Belakang**: Sebuah pipeline sistem pemrosesan finansial memproses event transaksi dari ratusan client eksternal menggunakan raw TCP socket yang persisten (long-lived stateful connection). Koneksi melewati cloud firewall/NAT gateway sebelum mencapai cluster backend ingestor.
* **Gejala Sistem**:
  * Backend ingestor mengindikasikan ratusan socket klien berstatus `ESTABLISHED` di memori dan thread pool tetap teralokasi untuk memproses data dari koneksi tersebut.
  * Dari sisi klien, mereka melaporkan bahwa koneksi mereka terputus tanpa pesan penutupan (`FIN`), dan ketika mencoba reconnect, transaksi tertunda atau ditolak karena terdeteksi session duplikat.
  * Analisis jaringan mengungkap bahwa intermediate NAT Gateway secara diam-diam (*silent drop*) memutuskan koneksi idle yang tidak memiliki aktivitas selama 350 detik untuk mengosongkan tabel state-nya, tanpa mengirim paket `RST` atau `FIN` ke client maupun backend.
* **Tugas Diagnostik**:
  1. Identifikasi status koneksi pada backend server dan jelaskan mekanisme yang menyebabkan terbentuknya *TCP Half-Open Connection*.
  2. Bagaimana ketiadaan protokol pendeteksi keaktifan koneksi dapat memicu *resource leak* dan kegagalan integritas konkurensi (race condition pada session locking)?
  3. Rancang arsitektur pertahanan menggunakan parameter native TCP Keepalive Linux (`tcp_keepalive_time`, `tcp_keepalive_intvl`, `tcp_keepalive_probes`) versus implementasi *Application-level Heartbeat* (Ping/Pong framing). Evaluasi trade-off keduanya.

---

### Skenario C: Arsitektur & Trade-Off: Desain Zero-Trust Service Mesh Ingress
* **Latar Belakang**: Perusahaan SaaS skala global sedang merancang ulang arsitektur ingress untuk edge network mereka. Sistem melayani perpaduan traffic publik: HTTP/1.1 API legacy, HTTP/2 REST API, dan internal gRPC microservices streaming berlatensi sangat rendah (sub-millisecond SLA). Sistem harus mematuhi standar Zero-Trust, yang mewajibkan mutual TLS (mTLS) hingga ke level pod internal, end-to-end distributed tracing, dan Web Application Firewall (WAF) inspection.
* **Dilema Desain**:
  * **Opsi 1**: Memasang *L4 Load Balancer* (NLB/IPVS) di tepi jaringan, melakukan *TCP Passthrough* langsung ke Ingress Gateway (Envoy) di dalam kluster, lalu terminasi mTLS dilakukan di level gateway atau langsung di service proxy sidecar.
  * **Opsi 2**: Menggunakan *L7 Cloud Load Balancer* dengan WAF terintegrasi di edge untuk melakukan terminasi TLS publik, memeriksa payload HTTP/2 dan gRPC, lalu membuka koneksi TLS baru (re-encryption) ke internal kluster Ingress Gateway.
* **Tugas Diagnostik**:
  1. Bedah trade-off antara Opsi 1 dan Opsi 2 dalam aspek: Latensi jaringan (RTT), utilisasi CPU untuk enkripsi/dekripsi TLS ganda, dan efektivitas inspeksi keamanan layer aplikasi (DDoS mitigation & L7 WAF).
  2. Dalam Opsi 1, bagaimana Anda memecahkan masalah identifikasi IP asli klien (Client Source IP Preservation) saat paket melewati NAT, tanpa memutus enkripsi TCP payload?
  3. Jika gRPC streaming berlatensi rendah menjadi prioritas utama, opsi arsitektur mana yang paling layak? Justifikasi jawaban Anda dengan menganalisis dampak multiplexing gRPC terhadap L4 vs L7 load balancing.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa & Diagnosis High-Performance Resilient Ingress Stack

#### Problem
Anda ditugaskan untuk mendesain, mengonfigurasi, dan memvalidasi edge ingress proxy stack menggunakan Nginx/Envoy di lingkungan Linux. Lingkungan tersebut harus mampu menangani latensi rendah, throughput tinggi, serta tetap tangguh (*resilient*) terhadap anomali jaringan seperti packet loss, MTU mismatch, dan lonjakan koneksi HTTP/2.

#### Requirements
1. **Infrastruktur & Topologi**:
   * Gunakan lingkungan Docker Compose atau Virtual Machine berbasis Linux (Ubuntu/Debian/RHEL).
   * Deploy 1 Edge Proxy (Nginx atau Envoy), 2 Mock Upstream Backend HTTP Services, dan 1 Client Test Container.
2. **Hardening & Kernel Tuning**:
   * Konfigurasikan file sysctl pada host/container untuk memaksimalkan handling TCP:
     * Alokasi port efemeral minimum 30.000 port.
     * Optimalisasi buffer TCP socket (`rmem`, `wmem`).
     * Konfigurasi backlog antrean listen (`somaxconn`, `tcp_max_syn_backlog`).
3. **Konfigurasi Edge Proxy**:
   * Wajib mengimplementasikan **TLS 1.3** dengan cipher modern (ChaCha20-Poly1305 / AES-GCM).
   * Konfigurasi dukungan **HTTP/2** end-to-end pada proxy.
   * Implementasikan **Upstream Connection Pooling** (Keepalive) ke backend service untuk mengeliminasi overhead 3-way handshake berulang.
   * Konfigurasi *Health Check* aktif dan failover otomatis jika salah satu backend dimatikan.
4. **Simulasi Anomali & Failure Injection**:
   * Gunakan Linux Traffic Control (`tc` / `netem`) atau manipulasi iptables pada client container untuk:
     * Menyuntikkan packet loss sebesar 5%.
     * Membatasi MTU interface client menjadi 1200 bytes untuk memvalidasi penanganan fragmentasi/MSS.

#### Constraints
* Tidak boleh menggunakan mode `network_mode: host` pada container untuk membuktikan pemahaman packet traversal pada bridge/virtual network.
* Pengujian throughput tidak boleh menghasilkan socket error `TIME_WAIT` lebih dari 1% dari total koneksi.
* Seluruh konfigurasi harus dibuat menggunakan pendekatan *Infrastructure-as-Code* (berupa file konfigurasi declarative dan shell provision script, bukan manipulasi manual ad-hoc).

#### Expected Output
1. **Konfigurasi Deklaratif**:
   * File `sysctl.conf` yang terdokumentasi dengan rasional teknis di setiap baris parameter.
   * File konfigurasi proxy (`nginx.conf` atau `envoy.yaml`) yang valid dan lolos uji sintaks.
   * File `docker-compose.yml` yang merefleksikan topologi jaringan terisolasi.
2. **Laporan Diagnostik & Analisis Jaringan**:
   * Hasil benchmarking load testing menggunakan tool seperti `wrk`, `hey`, atau `k6` (mengukur Latency P95/P99, RPS, dan Connection Errors) sebelum dan sesudah tuning sysctl & keepalive.
   * Bukti tangkapan paket (`tcpdump` / `.pcap`) yang dibuka menggunakan Wireshark/Tshark yang menunjukkan:
     * Negosiasi TLS 1.3 Handshake (1-RTT).
     * Terjadinya HTTP/2 Stream Multiplexing pada satu koneksi TCP.
     * Tidak adanya overhead handshake berulang ke upstream backend berkat connection pooling.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum melangkah ke bab containerization dan cloud architecture.

### Saya harus memahami:
- [ ] Perbedaan layer dan tanggung jawab pada model OSI vs model TCP/IP.
- [ ] Siklus hidup koneksi TCP (Handshake, Data Transfer, Termination) dan status transisi socket (`LISTEN`, `SYN_SENT`, `ESTABLISHED`, `FIN_WAIT`, `TIME_WAIT`, `CLOSE_WAIT`).
- [ ] Dampak overhead MTU, MSS, dan mekanisme enkapsulasi paket pada jaringan overlay (VXLAN/Geneve).
- [ ] Prinsip kerja protokol DNS (A, AAAA, CNAME, PTR, SRV, SOA, TTL) dan mitigasi DNS caching bottleneck pada container.
- [ ] Perbedaan fundamental antara HTTP/1.1, HTTP/2 (Multiplexing), dan HTTP/3 (QUIC over UDP).
- [ ] Karakteristik, performa, dan batasan operasional antara Load Balancing Layer 4 (Transport) dan Layer 7 (Application).
- [ ] Mekanisme handshake TLS 1.2 vs TLS 1.3, fungsi SNI, dan peran ALPN dalam penentuan protokol.
- [ ] Cara kerja Linux Conntrack, IP Masquerading (SNAT), Port Forwarding (DNAT), dan implikasinya pada performa jaringan throughput tinggi.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor port IANA yang terdaftar di luar well-known ports umum (port 22, 53, 80, 443, dll.). Cukup pahami konsep alokasi *privileged* vs *ephemeral ports*.
- [ ] Nilai bit exact dari header binary packet (misal: posisi pasti byte *Flags* TCP atau *Window Size*). Cukup pahami fungsinya dan cara membaca representasinya di Wireshark/tcpdump.
- [ ] Sintaks exact dari cipher suite cryptographic string TLS. Cukup ketahui cara merujuk ke Mozilla SSL Configuration Generator standar enterprise.
- [ ] Nilai limit absolut kernel Linux untuk setiap platform OS. Cukup pahami logika penyesuaian parameter berdasarkan rasio RAM dan CPU.

### Saya harus bisa melakukan:
- [ ] Melakukan packet capture langsung pada terminal Linux produksi menggunakan perintah `tcpdump` dengan filter spesifik (host, port, flag SYN/RST).
- [ ] Membaca dan menganalisis file `.pcap` menggunakan CLI (`tshark`) atau GUI (Wireshark) untuk mengidentifikasi retransmisi TCP, latensi handshake, dan TLS errors.
- [ ] Mendiagnosis status soket sistem secara komprehensif menggunakan utilitas modern seperti `ss` (Socket Statistics) dan membedakan backlog overflow vs connection starvation.
- [ ] Melakukan troubleshooting kegagalan resolusi DNS end-to-end menggunakan `dig`, `nslookup`, atau `delv`, termasuk memeriksa tracing delegasi DNS (`dig +trace`).
- [ ] Melacak rute paket dan mengidentifikasi titik packet loss menggunakan `traceroute`, `tracepath` (untuk deteksi MTU path), dan `mtr`.
- [ ] Mengonfigurasi parameter kernel jaringan runtime Linux secara dinamis via `/proc/sys/net/` dan permanen via `/etc/sysctl.d/`.
- [ ] Menguji latensi, throughput, dan performa socket menggunakan tools validasi jaringan seperti `iperf3`, `curl` (dengan profiling waktu koneksi), dan HTTP benchmarker (`k6`/`wrk`).