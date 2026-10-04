# BAB 06: Quiz, Challenge, & Knowledge Check
**Jaringan Sistem Operasi, Arsitektur Socket, dan TCP/IP Stack**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Abstraksi VFS dan Pemetaan Socket:**
   Jelaskan bagaimana Linux mengabstraksikan network socket melalui Virtual File System (VFS). Secara spesifik, bagaimana relasi struktural di dalam kernel antara `struct file`, `struct socket` (BSD socket layer), dan `struct sock` (inet layer)? Mengapa pemisahan hierarki antara `struct socket` dan `struct sock` ini krusial dalam desain kernel Linux?

2. **Dinamika TCP Connection Queues:**
   Dalam siklus hidup koneksi TCP di Linux, jelaskan perbedaan arsitektural dan fungsional antara **SYN Queue (Incomplete Connection Queue)** dan **Accept Queue (Completed Connection Queue)**. Parameter kernel (`sysctl`) apa yang mengontrol batas kapasitas masing-masing antrean tersebut, dan apa yang terjadi pada paket SYN berikutnya jika salah satu dari kedua antrean tersebut penuh?

3. **Struktur Data Inti Kernel: `sk_buff`:**
   Struktur `sk_buff` (socket buffer) adalah elemen fundamental manipulasi paket di Linux. Jelaskan peran pointer `head`, `data`, `tail`, dan `end` di dalam `sk_buff`. Bagaimana manipulasi pointer ini (`skb_push`, `skb_pull`, `skb_reserve`, `skb_put`) memungkinkan Linux mengimplementasikan enkapsulasi dan dekapsulasi protokol jaringan tanpa memerlukan alokasi memori berulang (*zero allocation overhead*)?

4. **Patologi State Koneksi TCP: `TIME_WAIT` vs `CLOSE_WAIT`:**
   Uraikan signifikansi teknis dari state `TIME_WAIT` dan `CLOSE_WAIT` berdasarkan Finite State Machine (FSM) TCP. Mengapa state `TIME_WAIT` diwajibkan oleh RFC 793 (jelaskan dua alasan intinya), dan apa dampak bahayanya mematikan durasi ini secara agresif? Sebaliknya, mengapa akumulasi koneksi pada state `CLOSE_WAIT` selalu mengindikasikan bug pada level aplikasi dan bukan pada kernel stack?

5. **Jalur Eksekusi Paket Masuk (*Ingress Packet Path*):**
   Gambarkan alur lengkap sebuah paket Ethernet sejak menyentuh Physical Layer (PHY/MAC) pada NIC hingga data payload tersedia untuk dibaca oleh aplikasi via system call `read()`/`recv()`. Alur harus mencakup: DMA transfer ke Rx Ring Buffer, Hardware Interrupt (IRQ), penjadwalan NAPI/SoftIRQ (`NET_RX_SOFTIRQ`), eksekusi `ksoftirqd`, pemrosesan protokol layer 3/4, hingga penempatan di socket receive buffer.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme I/O Multiplexing: `epoll` Internals:**
   Mengapa `epoll` memiliki performa $O(1)$ untuk event readiness polling dibandingkan dengan $O(N)$ pada `select()` atau `poll()`? Jelaskan struktur data internal (Red-Black Tree vs Ready List) yang digunakan kernel untuk mengelola file descriptor yang diawasi. Bedakan pula mekanisme notifikasi **Edge-Triggered (ET)** dan **Level-Triggered (LT)** serta potensi jebakan *starvation* atau *blocking* yang dapat terjadi pada mode ET.

2. **TCP Dynamic Buffer Autotuning & Memory Accounting:**
   Bagaimana Linux mengelola memori transmisi dan penerimaan TCP melalui mekanisme *TCP Autotuning*? Jelaskan arti ketiga nilai tuple pada `net.ipv4.tcp_rmem` dan `net.ipv4.tcp_wmem` (`min`, `default`, `max`). Apa dampaknya jika parameter `net.ipv4.tcp_moderate_rcvbuf` dimatikan, dan bagaimana Linux menghitung *Bandwidth-Delay Product* (BDP) untuk menyesuaikan *Receive Window* (RWIN) secara dinamis?

3. **Mitigasi DoS via TCP SYN Cookies:**
   Ketika `net.ipv4.tcp_syncookies = 1` aktif dan SYN Queue penuh, jelaskan secara matematis dan kriptografis bagaimana kernel menghasilkan *Initial Sequence Number* (ISN) untuk SYN-ACK tanpa menyimpan state koneksi di memori. Apa trade-off struktural terhadap performa koneksi (misalnya terhadap TCP Options seperti Window Scaling, SACK, dan Timestamp) ketika SYN Cookie aktif?

4. **Penanganan Out-of-Order Packet & TCP SACK:**
   Ketika terjadi *packet reordering* di jaringan, bagaimana kernel Linux memanfaatkan Selective Acknowledgment (SACK) via struktur `tcp_sack_block` untuk menghindari retransmisi data secara membabi buta (*Go-Back-N*)? Apa beban komputasi internal kernel (terkait manipulasi RB-tree pada *Out-of-Order Queue*) ketika sebuah TCP flow menerima paket berantakan dengan intensitas tinggi pada throughput 40Gbps+?

5. **Kernel-Bypass vs In-Kernel Fast Path:**
   Bandingkan jalur throughput paket antara arsitektur soket standar Linux, **eBPF/XDP (eXpress Data Path)**, dan **Kernel-Bypass (DPDK / AF_XDP)**. Pada titik layer mana XDP memotong eksekusi paket sebelum `sk_buff` dialokasikan, dan apa batasan fungsional dari program XDP jika dibandingkan dengan soket TCP kernel konvensional?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Skala Besar pada API Gateway
Sebuah cluster reverse-proxy API Gateway berbasis Linux yang menangani $150.000$ request per detik mulai mengalami lonjakan latensi p99 dari $5\text{ ms}$ menjadi $1.200\text{ ms}$, disertai penurunan drastis pada *established connections*. Metrik monitoring menunjukkan utilisasi CPU per-core tidak merata: core 0 dan core 1 berada di $100\%$ sementara core lain di bawah $20\%$. Perintah `top` menunjukkan `ksoftirqd/0` dan `ksoftirqd/1` mengonsumsi sebagian besar CPU. Output `netstat -s` mencatat peningkatan pesat pada metrik:
`XXX times the listen queue of a socket overflowed` dan `XXX SYNs to LISTEN sockets dropped`.

*   **Pertanyaan Diagnostik & Solusi:**
    1. Apa akar penyebab ketidakseimbangan CPU di tingkat hardware/driver, dan bagaimana Anda mengonfigurasi Receive Side Scaling (RSS) atau Receive Packet Steering (RPS) untuk mendistribusikan beban interrupt?
    2. Periksa parameter kernel apa saja yang menyebabkan metrik *listen queue overflow* bertambah, dan bagaimana Anda melakukan kalkulasi penyesuaian untuk `somaxconn`, `backlog` aplikasi, dan `tcp_max_syn_backlog`?
    3. Perintah CLI tingkat lanjut apa (misalnya `ss`, `bpftrace`, atau `ethtool`) yang akan Anda jalankan secara real-time untuk membuktikan bahwa queue overflow terjadi sebelum atau sesudah handshake TCP selesai?

---

### Skenario B: Ephemeral Port Exhaustion & Saturated Outbound Proxy
Sebuah cluster service *payment aggregator* melakukan pemanggilan HTTP outbound (REST API) secara masif ke berbagai bank mitra. Tiba-tiba, aplikasi mulai melempar error sistem `java.net.NoRouteToHostException: Cannot assign requested address` (atau kode error `EADDRNOTAVAIL`). Saat dicek menggunakan `ss -ant`, ditemukan lebih dari $60.000$ koneksi berada pada state `TIME_WAIT` menuju ke sekelompok IP gateway bank yang sama.

*   **Pertanyaan Diagnostik & Solusi:**
    1. Mengapa `EADDRNOTAVAIL` muncul pada system call `connect()` dalam kaitannya dengan quintuple (5-tuple) socket TCP?
    2. Evaluasi risiko arsitektural dan teknis jika tim operasional secara terburu-buru mengaktifkan `net.ipv4.tcp_tw_reuse`. Dalam kondisi jaringan seperti apa `tcp_tw_reuse` aman digunakan, dan opsi TCP apa (`TCP Timestamps`) yang wajib aktif agar fitur ini tidak menyebabkan korupsi data?
    3. Selain manipulasi kernel parameter `net.ipv4.ip_local_port_range`, solusi fundamental apa pada level arsitektur aplikasi (client-side) yang harus diimplementasikan untuk mengeliminasi masalah ini secara permanen?

---

### Skenario C: Socket Buffer Bloat vs High-Throughput Packet Drops
Platform ingest data analitik terdistribusi mentransfer file multi-gigabyte antar-datacenter via link 10Gbps dengan RTT $80\text{ ms}$. Tim infrastruktur mengeluhkan bahwa throughput transfer tidak pernah menembus lebih dari $120\text{ Mbps}$ per TCP stream, padahal link fisik memiliki sisa bandwidth melimpah. Seorang engineer mencoba menaikkan nilai `net.core.rmem_max` dan `net.core.wmem_max` menjadi $1\text{ GB}$. Hasilnya, throughput naik sementara, namun jika terjadi packet loss sebesar $0.1\%$, sistem mengalami fenomena *Bufferbloat*, TCP window collapse, dan koneksi drop secara serentak karena OOM (*Out Of Memory*) killer membunuh proses database ingest.

*   **Pertanyaan Diagnostik & Solusi:**
    1. Hitung kebutuhan teoritis *Bandwidth-Delay Product* (BDP) untuk link 10Gbps dengan RTT $80\text{ ms}$. Berapa ukuran window buffer ideal yang seharusnya dikonfigurasi pada `tcp_rmem` dan `tcp_wmem`?
    2. Mengapa menaikkan buffer soket hingga $1\text{ GB}$ menyebabkan instabilitas fatal pada memory kernel (ingat batas `tcp_mem`), dan apa beda perhitungan alokasi satuan nilai pada `tcp_mem` (pages) dengan `tcp_rmem` (bytes)?
    3. Algoritma TCP Congestion Control apa (misalnya Cubic vs BBR) yang paling tepat untuk karakteristik link berlatensi tinggi dengan probabilitas loss non-kongesti, dan jelaskan mengapa algoritma tersebut mampu mencegah *window collapse* dibandingkan TCP Reno/Cubic standar?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance TCP Socket Health Profiler & Drop Detector

#### Problem Statement
Dalam infrastruktur *high-concurrency*, dropped packets dan antrean soket yang jenuh kerap kali luput dari monitoring standar (Prometheus polling interval $15\text{–}60\text{ detik}$) karena fenomena *microburst*. Anda ditugaskan membangun pipeline diagnosa performa jaringan real-time pada host Linux produksi untuk mengidentifikasi *TCP drops*, *Accept queue full*, dan memvalidasi latensi pemrosesan paket di kernel stack secara deterministik.

#### Requirements
1. **Tooling / Scripting:** Buat sebuah tool berbasis Bash + Python atau skrip instrumentasi eBPF (menggunakan `bpftrace` atau BCC) yang dapat dieksekusi di Linux kernel modern (v5.x/6.x).
2. **Monitoring Kernel Events:**
   * Deteksi pemanggilan fungsi kernel `tcp_drop` dan ekstrak 5-tuple (src IP, dst IP, src port, dst port) beserta status/alasan drop (*drop reason*).
   * Pantau pertambahan ukuran Accept Queue pada port listening tertentu (misalnya port 80 atau 443) dan picu alarm jika kedalaman antrean (*queue depth*) melampaui $80\%$ dari kapasitas `backlog`.
3. **Reproduksi Masalah (Load Generation Test):**
   * Tulis sebuah program server socket sederhana (bahasa bebas: C, Python, atau Go) dengan backlog sengaja diset sangat kecil (`backlog=2`).
   * Gunakan tools benchmarking (seperti `wrk`, `hping3`, atau custom multi-thread client) untuk memicu kondisi *Listen Queue Overflow*.
4. **Koleksi Metrik Kernel:**
   * Ekstrak secara periodik metrik `/proc/net/netstat` dan `/proc/net/snmp` terkait `ListenOverflows`, `ListenDrops`, dan `TCPTimeouts`.

#### Constraints
* Tidak boleh menggunakan modul kernel kustom (out-of-tree kernel modules).
* Overhead monitoring tidak boleh mengonsumsi lebih dari $2\%$ total CPU saat traffic menyentuh $50.000\text{ RPS}$.
* Tidak boleh mengandalkan `tcpdump` secara kontinu pada mode promiscuous karena risiko packet drop pada libpcap.

#### Expected Output
1. Output terminal terstruktur (JSON line atau formatted table) yang mencetak warning seketika saat terjadi socket drop atau queue overflow.
2. Analisis tertulis yang memvalidasi korelasi antara parameter:
   * `net.core.somaxconn`
   * Nilai parameter kedua dari `listen(int sockfd, int backlog)`
   * Output kolom `Send-Q` dan `Recv-Q` pada perintah `ss -lnt`
3. Bukti log deterministik hasil reproduksi yang menunjukkan transisi paket SYN yang diabaikan (*ignored/dropped*) saat Accept Queue penuh.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi struktur data `sk_buff` dan siklus hidupnya dari layer physical hingga userspace memory.
- [ ] Perbedaan implementasi soket non-blocking berbasis event notification (`epoll`) dengan model thread-per-connection.
- [ ] Detail arsitektur antrean kernel: skema kerja SYN Queue vs Accept Queue dan pengaruhnya terhadap TCP 3-way handshake.
- [ ] Mekanisme penanganan interrupt hardware/software: Hard IRQ, NAPI polling cycle, dan alokasi budget `net.core.netdev_budget`.
- [ ] State machine TCP lengkap, khususnya lifecycle perpindahan dari `FIN_WAIT_1`, `FIN_WAIT_2`, `TIME_WAIT` hingga `CLOSED`.
- [ ] Konsekuensi TCP window scaling dan perhitungan *Bandwidth-Delay Product* (BDP) pada throughput network berkecepatan tinggi.
- [ ] Peran dan batasan TCP SYN Cookies dalam mengatasi ancaman serangan SYN Flood.
- [ ] Matriks alokasi memori buffer TCP (`tcp_rmem`, `tcp_wmem`, `tcp_mem`) dan pengaruhnya terhadap Kernel Slab Allocator.

### Saya tidak perlu menghafal:
- [ ] Nilai hex spesifik dari setiap bit flag TCP header (misal: URG, ACK, PSH, RST, SYN, FIN bitmask) di tingkat biner.
- [ ] Nomor pasti dari RFC historis TCP/IP di luar RFC fundamental (RFC 793, RFC 1323/7323).
- [ ] Seluruh offset byte dari field internal pada `struct sock` atau `struct tcp_sock` pada source code kernel C.
- [ ] Konfigurasi parameter vendor-specific driver NIC (misal: register internal chipset Intel e1000 atau Broadcom bnxt).

### Saya harus bisa melakukan:
- [ ] Menganalisis kondisi antrean socket (`Recv-Q`, `Send-Q`) pada socket berstatus LISTEN maupun ESTABLISHED menggunakan `ss -lnt` dan `ss -nt`.
- [ ] Mengidentifikasi masalah *packet drops* di berbagai level stack menggunakan `ip -s link`, `ethtool -S <ethX>`, `netstat -s`, dan `/proc/net/snmp`.
- [ ] Melakukan tuning parameter sysctl TCP/IP secara aman dan terukur pada environment high-throughput / low-latency.
- [ ] Menggunakan `tcpdump` dengan filter ekspresi BPF yang efisien untuk menangkap anomali TCP flags (RST, zero window, retransmissions) tanpa membebani CPU sistem.
- [ ] Mengonfigurasi mitigasi *ephemeral port exhaustion* dengan benar menggunakan kombinasi pooling layer aplikasi dan fine-tuning network stack Linux.
- [ ] Menggunakan tools diagnosa Linux modern (`bpftrace` / BCC tools seperti `tcplife`, `tcptracer`, `tcpdrop`) untuk menginspeksi event network stack secara real-time.