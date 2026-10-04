# BAB 07: Quiz, Challenge, & Knowledge Check
**Bab 07: Jaringan Komputer, Protokol Transport, Sockets, & IPC**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Enkapsulasi dan Overhead Framing Paket Jaringan**  
   Jelaskan secara deterministik proses enkapsulasi data dari Application Layer hingga Physical Layer saat sebuah payload HTTP/1.1 berukuran 100 byte dikirimkan melalui stack TCP/IP di atas interface Ethernet standar (MTU 1500 byte). Hitung total byte overhead protokol (Ethernet Frame header/trailer, IPv4 header minimum, dan TCP header minimum) serta jelaskan bagaimana perbedaan antara Maximum Transmission Unit (MTU) dan Maximum Segment Size (MSS) ditentukan secara matematis.

2. **State Machine TCP: Siklus Hidup dan Rationale Status `TIME_WAIT`**  
   Gambarkan dan urutkan transisi TCP finite state machine (FSM) selama proses *graceful teardown* (Four-Way Handshake) dari sisi pengirim inisiator (Active Closer). Mengapa kernel Linux mewajibkan koneksi menetap pada status `TIME_WAIT` selama durasi $2 \times \text{MSL}$ (Maximum Segment Life)? Jelaskan dua anomali fatal pada level protokol transport yang akan terjadi di layer jaringan jika status `TIME_WAIT` diabaikan atau disetel bernilai 0.

3. **Demultiplexing Koneksi dan Representasi Socket Descriptor**  
   Bagaimana sistem operasi (khususnya kernel Linux) memetakan sebuah paket TCP yang tiba di Network Interface Card (NIC) ke *file descriptor* socket tertentu di Userspace? Jelaskan peran 4-tuple (atau 5-tuple) dalam struktur lookup tabel kernel hash socket (`tcp_hashinfo`), serta jelaskan perbedaan semantik internal antara socket yang berada dalam status `LISTEN` (passive socket) dan socket hasil dari `accept()` (connected socket).

4. **Head-of-Line (HoL) Blocking: Layer 4 vs. Layer 7**  
   Bedakan mekanisme terjadinya *Head-of-Line (HoL) Blocking* pada Layer 4 (Transport Layer - TCP) versus Layer 7 (Application Layer - HTTP/1.1 pipelining dan HTTP/2 multiplexing). Mengapa implementasi HTTP/2 di atas TCP tidak menyelesaikan HoL blocking ketika terjadi kehilangan paket (*packet loss*) pada jaringan fisik, dan bagaimana protokol HTTP/3 (QUIC di atas UDP) menyelesaikan masalah fundamental ini?

5. **Mekanisme Domain Name System (DNS) & Fallback Transport**  
   DNS secara default berjalan di atas UDP port 53, namun memiliki mekanisme fallback otomatis ke TCP port 53. Terangkan alur deterministik resolusi DNS rekursif (termasuk interaksi dengan Root Server, TLD Server, dan Authoritative Server), peranan Record TTL, serta kondisi teknis presisi apa (seperti respon *truncated* dengan flag `TC = 1` atau implementasi DNSSEC) yang memaksa DNS Client menginisiasi TCP Handshake untuk resolusi query.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Patologi Performa: Interaksi Nagle’s Algorithm dengan Delayed ACK**  
   Jelaskan mekanisme interaksi destruktif antara *Nagle’s Algorithm* (`RFC 896`) pada sisi pengirim dan *Delayed Acknowledgement* (`RFC 1122`) pada sisi penerima dalam arsitektur request-response RPC berbasis TCP. Mengapa kombinasi kedua algoritma ini dapat mengintroduksi latensi buatan sebesar 40ms hingga 200ms pada penulisan paket kecil berturut-turut, dan bagaimana manipulasi socket option `TCP_NODELAY` serta `TCP_CORK` mengeliminasi *deadlock* latensi tersebut?

2. **Evolusi I/O Multiplexing: `select()`, `poll()`, versus `epoll()`**  
   Analisis secara mendalam perbedaan arsitektural dan kompleksitas algoritma antara `select()` ($O(N)$), `poll()` ($O(N)$), dan `epoll()` ($O(1)$) dalam kernel Linux saat menangani 100.000 concurrent sockets aktif. Jelaskan secara teknis implementasi internal `epoll` menggunakan struktur data *Red-Black Tree* dan *Ready List (Doubly Linked List)*, serta bedakan implikasi pemanggilan `epoll_wait()` dalam mode *Level-Triggered* (LT) versus *Edge-Triggered* (ET) terhadap penanganan *spurious wakeups* dan pengurasan buffer socket.

3. **TCP Socket Exhaustion, Port Ephemeral, dan `SO_REUSEADDR` vs. `SO_REUSEPORT`**  
   Sebuah *high-throughput reverse proxy* mengalami error `EADDRNOTAVAIL` (*Cannot assign requested address*) saat membuka outbound connection ke upstream server. Bedakan secara struktural perbedaan alokasi kernel antara opsi `SO_REUSEADDR` dan `SO_REUSEPORT`. Bagaimana parameter `ip_local_port_range`, keberadaan socket dalam status `TIME_WAIT`, dan flag `tcp_tw_reuse` mempengaruhi utilisasi ephemeral port?

4. **TCP Congestion Control: CUBIC vs. BBR dan Fenomena Bufferbloat**  
   Bandingkan filosofi deteksi kongesti antara *loss-based congestion control* (seperti TCP CUBIC) dan *model-based congestion control* (BBR - Bottleneck Bandwidth and Round-trip propagation time). Jelaskan bagaimana fenomena *Bufferbloat* pada router perantara merusak estimasi Congestion Window (`cwnd`) pada algoritma CUBIC, dan bagaimana BBR menghitung pacing rate menggunakan tracking eksplisit terhadap *Bottleneck Bandwidth* (`BtlBw`) dan *Minimum RTT* (`RTprop`).

5. **Path MTU Discovery (PMTUD) dan Fenomena ICMP Black Hole**  
   Jelaskan cara kerja Path MTU Discovery menggunakan bit `DF` (Don't Fragment) pada header IPv4. Jika sebuah paket berukuran 1500 byte melintasi tunnel VPN (misalnya GRE atau WireGuard) dengan MTU 1420 byte, namun firewall perantara salah konfigurasi dengan memblokir semua paket *ICMP Type 3 Code 4 (Destination Unreachable, Fragmentation Needed)*, apa yang terjadi pada koneksi TCP klien? Bagaimana teknik *TCP MSS Clamping* (`iptables -j TCPMSS --clamp-mss-to-pmtu`) memitigasi masalah ini tanpa mengubah konfigurasi client?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latensi Misterius p99 40ms pada Microservices API Gateway
Sebuah e-commerce berskala besar mengimplementasikan arsitektur Microservices internal yang berkomunikasi menggunakan custom binary protocol di atas TCP mentah. API Gateway bertindak sebagai client yang melakukan request berturut-turut ke Auth Service:
- Paket 1: Header otentikasi (32 byte).
- Paket 2: Payload body JSON metadata user (variabel: 120 - 512 byte).
Kedua paket dikirim menggunakan dua operasi syscall `write()` terpisah secara sekuensial pada socket yang sama.

Tim infrastruktur mendeteksi bahwa metrik p50 latensi jaringan tercatat < 1ms, namun p99 melonjak drastis dan stabil di angka tepat **40ms**. Saat dianalisa melalui `tcpdump`, paket kedua selalu tertunda pengirimannya dari host Gateway hingga ACK dari Paket 1 tiba dari host Auth Service. Auth Service tidak merespon sampai Paket 2 selesai diproses.

```
Client (Gateway)                          Server (Auth)
      |                                         |
      |--- write(Header: 32B) [Pkt 1] --------->| (ACK ditahan oleh Delayed ACK timer)
      |    write(Body: 200B)  [Pkt 2]           |
      |    (TERTAHAN DI LOCAL KERNEL BUFFER!)   |
      |                                         |
      |                 ... 40ms Hening ...     |
      |                                         |
      |                                         | (Timer 40ms expired)
      |<-- ACK untuk Pkt 1 ---------------------|
      |--- Pkt 2 Baru Meluncur ---------------->|
```

* **Tugas Diagnostik:**
  1. Identifikasi akar penyebab latensi 40ms ini berdasarkan interaksi algoritma transport layer bawaan OS.
  2. Jelaskan mengapa latency bottleneck tidak terjadi jika kedua `write()` digabungkan menjadi satu buffer atau menggunakan `writev()`.
  3. Berikan dua solusi teknis berbeda pada level konfigurasi socket programming C/Go/Rust (beserta kode syscall/socket option-nya) untuk mengeliminasi latensi 40ms tersebut secara permanen.

---

### Skenario B: Silent Connection Drop & Half-Open Socket Leak pada Sistem FinTech
Sistem transaksi perbankan inti (*Core Banking Engine*) mempertahankan ribuan koneksi TCP persisten jangka panjang (long-lived stateful TCP connections) ke mesin payment gateway mitra eksternal. Sistem dirancang tanpa heartbeat di layer aplikasi (*application-level ping*) untuk alasan efisiensi payload, hanya bergantung pada layer transport.

Saat terjadi gangguan jaringan bawah laut (*fiber cut*) sementara selama 3 menit di level ISP antar negara:
- Firewall stateful di perantara me-reset state tabel koneksinya dan menghapus *translation mapping*.
- Core Banking Engine di sisi pengirim tidak menerima paket reset (`RST`) maupun `FIN` dari sisi mitra.
- Setelah rute internet pulih, Core Banking Engine tetap mempertahankan status socket sebagai `ESTABLISHED`.
- Transaksi nasabah yang dikirim melalui socket tersebut mengalami *hang* tanpa batas waktu (*infinite block*), mengakibatkan thread pool exhaustion dan sistem crash secara kaskade (*cascading failure*).

```
Core Banking (Host A)                  Mitra Gateway (Host B)
      |                                         |
      |<========= Long-Lived TCP [ESTABLISHED] ========>|
      |                                         |
      |          x--- [Fiber Cut / ISP Drop] ---x
      |                                         |
      | (Tidak ada RST/FIN terkirim karena kabel fisik putus)
      |                                         |
      | (OS Host A tetap mengira status masih: ESTABLISHED)
      | write(Transaksi_Baru)                   |
      |---> (Paket hilang tanpa ada rute)       |
      | [Thread Terblokir Menunggu Respon...]   |
```

* **Tugas Diagnostik:**
  1. Jelaskan mengapa status TCP dapat tetap `ESTABLISHED` pada salah satu host meskipun link fisik telah terputus total (*Half-Open Connection state*).
  2. Tentukan parameter TCP Keepalive bawaan kernel Linux (`tcp_keepalive_time`, `tcp_keepalive_intvl`, `tcp_keepalive_probes`) dan hitung berapa lama waktu default kernel Linux mendeteksi putusnya koneksi jika parameter ini tidak di-tuning.
  3. Rancang strategi mitigasi komprehensif, mencakup kombinasi socket option level kernel (`SO_KEEPALIVE`, `TCP_USER_TIMEOUT`) dan implementasi heartbeat di Application Layer untuk mendeteksi *dead connection* dalam waktu sub-detik tanpa membebani overhead bandwidth.

---

### Skenario C: Dilema Arsitektur High-Frequency Ingestion (TCP vs. UDP vs. QUIC)
Perusahaan *Autonomous Vehicle Fleet Management* sedang mendesain sistem telemetri untuk menerima data telemetri real-time dari 500.000 armada mobil pintar di seluruh dunia. Karakteristik sistem:
- Setiap mobil memancarkan data sensor GPS, kecepatan, dan status mesin setiap 100 milidetik (frekuensi 10Hz, ukuran payload 256 byte).
- Mobil bergerak melintasi koneksi seluler (4G/5G) dengan fluktuasi sinyal tinggi: *packet loss rate* rata-rata 3% hingga 7%, sering terjadi perpindahan *base station* (*handover / IP migration*), dan latensi berfluktuasi dari 20ms hingga 300ms.
- Tim engineering terbagi menjadi tiga kubu:
  - **Kubu 1:** Mengusulkan **TCP murni** dengan connection pool dan TLS 1.3 (reliabilitas terjamin, data utuh).
  - **Kubu 2:** Mengusulkan **UDP murni** dengan enkripsi DTLS (kecepatan maksimal, no-overhead).
  - **Kubu 3:** Mengusulkan **QUIC (HTTP/3)** (multiplexing tanpa transport HoL, connection migration via Connection ID).

* **Tugas Diagnostik:**
  1. Analisis kegagalan arsitektur Kubu 1 (TCP): Apa dampak dari packet loss 7% terhadap Congestion Window (`cwnd`) dan latensi p99 pengiriman data akibat mekanisme retransmisi TCP? Apa konsekuensi teknis bagi TCP jika mobil berganti alamat IP saat roaming seluler?
  2. Analisis risiko arsitektur Kubu 2 (UDP): Apa kelemahan utama ketiadaan congestion control bawaan di UDP terhadap infrastruktur server ingestion saat terjadi lonjakan jaringan? Bagaimana risiko paket *out-of-order* dan mitigasinya?
  3. Lakukan evaluasi trade-off arsitektural untuk Kubu 3 (QUIC). Buktikan mengapa fitur *Connection ID* (CID) pada QUIC secara spesifik memecahkan tantangan migrasi IP seluler tanpa perlu re-handshake TLS, dan jelaskan trade-off konsumsi CPU/memori di sisi server untuk menangani QUIC di userspace dibandingkan kernel-space TCP.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent TCP Event Loop & Telemetry Ingestion Engine

#### Problem Statement
Anda ditugaskan oleh tim Core Platform Infrastructure untuk membangun prototipe *High-Throughput Concurrent TCP Telemetry Collector* dari nol menggunakan bahasa pemrograman tingkat rendah berbasis System Call (disarankan: **C**, **Rust**, atau library low-level **Go via syscall/epoll** / **Node.js low-level C++ addon**). Engine ini bertugas meng-ingest stream pesan biner bervolume tinggi dari ribuan klien simultan tanpa crash, tanpa memory leak, dan mempertahankan footprint memori yang konstan.

#### Requirements
1. **Non-blocking Network I/O dengan Event Loop:**
   - Inisialisasi TCP Socket Server pada port `9000` dengan opsi socket `SO_REUSEADDR` dan `SO_REUSEPORT`.
   - Ubah socket descriptor ke mode *Non-blocking* (`O_NONBLOCK` via `fcntl`).
   - Gunakan mekanisme I/O Multiplexing bawaan sistem operasi: **`epoll`** (Linux, mode Edge-Triggered `EPOLLET`) atau **`kqueue`** (macOS/BSD). Dilarang keras menggunakan model thread-per-connection atau synchronous blocking I/O!
2. **Protokol Binary Framing Sederhana:**
   - Engine harus memparsing stream byte dengan format TLV (Type-Length-Value) mini:
     - `Magic Byte` (1 byte): `0xAA`
     - `Payload Length` (2 byte, Big-Endian / Network Byte Order): Ukuran payload ($N$).
     - `Payload Data` ($N$ byte): String teks ASCII/UTF-8.
   - Harus mampu menangani fenomena pemotongan paket TCP: *Fragmentation* (pesan tiba separuh) dan *Coalescing / Sticking* (beberapa pesan tiba dalam satu syscall `read()`). Buffer parsial client harus disimpan di Userspace Connection State per-client.
3. **Backpressure & Concurrency Control:**
   - Implementasikan limitasi koneksi serentak (Max Clients: 10.000). Jika limit tercapai, tolak koneksi baru secara elegan atau drop.
   - Tangani error `EAGAIN` / `EWOULDBLOCK` secara presisi saat membaca (`read`) dan menulis (`write`).
4. **Graceful Teardown & Signal Handling:**
   - Tangkap sinyal `SIGINT` (Ctrl+C) dan `SIGTERM`.
   - Lakukan penutupan seluruh socket aktif secara graceful, bersihkan resource memori (bebas memory leak di Valgrind / AddressSanitizer), dan tutup listening socket sebelum proses exit.

#### Constraints
- **Alokasi Dinamis:** Dilarang melakukan alokasi memori berulang (*malloc/free* atau *heap allocation*) pada *hot-path* pemrosesan paket per-koneksi. Gunakan teknik *Pre-allocated Ring Buffer* atau *Memory Pool* per-worker.
- **Robustness:** Koneksi client yang ditutup secara tiba-tiba (*broken pipe*, `ECONNRESET`) tidak boleh memicu *panic* atau *crash* pada server (tangkap sinyal `SIGPIPE`!).

#### Expected Output & Verification
- Server mengoutput log saat startup:
  ```text
  [INFO] Engine running on port 9000 using epoll (Edge-Triggered).
  [INFO] Pre-allocated connection slots: 10000.
  ```
- Saat diuji beban menggunakan *tool* seperti `tcpkali` atau script stress-test Python concurrency tinggi (minimal 2.000 concurrent client memompa pesan TLV kontinu):
  ```bash
  # Output metrik server setiap 1 detik:
  [METRICS] Active Conns: 2000 | Ingest Rate: 125,400 msgs/sec | Throughput: 32.4 MB/s | Dropped: 0
  ```
- Tidak terjadi *segmentation fault*, tidak ada file descriptor leak (verifikasi dengan `lsof -p <PID> | wc -l`), dan pemakaian RAM stabil flat (verifikasi dengan `top` atau `valgrind --leak-check=full`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi struktur paket: Ethernet Header, IPv4 Header (TTL, DF flag, Protocol), dan TCP Header (Flags, Sequence Number, Ack Number, Window Size).
- [ ] Mekanisme handshake TCP: Three-Way Handshake (SYN, SYN-ACK, ACK) dan Four-Way Teardown (FIN, ACK, FIN, ACK).
- [ ] Makna teknis status TCP: `LISTEN`, `SYN_SENT`, `ESTABLISHED`, `CLOSE_WAIT`, `LAST_ACK`, `FIN_WAIT_1`, `FIN_WAIT_2`, dan `TIME_WAIT`.
- [ ] Perbedaan fundamental model I/O: Synchronous Blocking, Synchronous Non-blocking, I/O Multiplexing (`select`/`poll`/`epoll`), dan Asynchronous I/O (AIO/`io_uring`).
- [ ] Alasan matematis dan arsitektural mengapa `epoll` Edge-Triggered (`EPOLLET`) membutuhkan *looping read* hingga `EAGAIN` serta socket non-blocking.
- [ ] Algoritma Flow Control (Sliding Window, Receive Window / `rwnd`) vs Congestion Control (Congestion Window / `cwnd`).
- [ ] Siklus kerja TCP Congestion Control: Slow Start, Congestion Avoidance, Fast Retransmit, dan Fast Recovery.
- [ ] Domain Name System: Alur resolusi iteratif vs rekursif, format Record (A, AAAA, CNAME, PTR, TXT), dan mekanisme caching berbasis TTL.
- [ ] Peran IPC (Inter-Process Communication): Unix Domain Sockets (UDS), Named Pipes (FIFO), Shared Memory, dan Message Queues.

### Saya tidak perlu menghafal:
- [ ] Nilai eksak hexadesimal bitmask TCP flags di memori (misalnya nilai hex bit FIN, SYN, RST di RFC) — serahkan pada library header kernel seperti `<netinet/tcp.h>`.
- [ ] Angka pasti nilai default setiap parameter kernel Linux di `/proc/sys/net/ipv4/` (seperti default byte size eksak untuk `tcp_rmem` atau `tcp_wmem`) — cukup pahami cara membaca dan men-tuning via `sysctl`.
- [ ] Tabel nomor port IANA lengkap di luar port umum standar (HTTP: 80, HTTPS: 443, DNS: 53, SSH: 22).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis trafik jaringan secara interaktif di terminal menggunakan `tcpdump` dan membaca file pcap menggunakan Wireshark untuk menelusuri paket drop, retransmisi, atau flag RST.
- [ ] Menemukan status koneksi socket bermasalah, port exhaustion, atau antrean socket buffer penuh (`Recv-Q` / `Send-Q`) menggunakan utility `ss -taunp` atau `netstat`.
- [ ] Mengonfigurasi dan memanipulasi atribut socket via `setsockopt()` pada kode program: `SO_REUSEADDR`, `SO_REUSEPORT`, `SO_KEEPALIVE`, `TCP_NODELAY`, dan `TCP_USER_TIMEOUT`.
- [ ] Mengidentifikasi dan menyelesaikan MTU mismatch / ICMP Black Hole menggunakan utility CLI `ping -M do -s <packet_size> <destination_ip>`.
- [ ] Membangun program networking client-server dasar berbasis non-blocking I/O event loop yang tahan terhadap TCP packet fragmentation dan boundary issues.