# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Backend & Arsitektur Internet**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Resolusi DNS & Caching Hierarchy**  
   Jelaskan secara mendalam siklus hidup sebuah query DNS dari saat client mengetikkan URL hingga IP address diterima. Bedakan peran serta mekanisme kerja antara *Recursive Resolver*, *Root Nameserver*, *TLD Nameserver*, dan *Authoritative Nameserver*. Apa dampak teknis dari nilai *Time-to-Live* (TTL) yang diatur terlalu rendah (< 5 detik) versus terlalu tinggi (> 86400 detik) terhadap beban infrastruktur DNS dan fleksibilitas *failover* traffic backend?

2. **Diferensiasi Abstraksi Layer 4 (Transport) vs Layer 7 (Application)**  
   Dalam konteks perancangan *reverse proxy* dan *load balancer*, analisislah perbedaan fundamental antara operasi pada OSI Layer 4 (TCP/UDP) dan Layer 7 (HTTP/HTTPS). Mengapa *L4 Load Balancing* memiliki throughput yang jauh lebih tinggi dan latensi lebih rendah, sementara *L7 Load Balancing* esensial untuk kapabilitas seperti *path-based routing*, *header mutation*, TLS termination, dan *rate limiting* granular?

3. **Lifecycle TCP Connection & State Machine Management**  
   Uraikan proses *TCP 3-Way Handshake* (`SYN`, `SYN-ACK`, `ACK`) dan *TCP 4-Way Teardown* (`FIN`, `ACK`, `FIN`, `ACK`). Secara spesifik, jelaskan fungsi kritis dari state `TIME_WAIT` pada socket TCP di sisi server maupun client. Masalah fatal apa yang terjadi pada kernel sistem operasi jika server backend membuka dan menutup ribuan koneksi per detik tanpa *connection pooling* (*socket exhaustion* vs *ephemeral port exhaustion*)?

4. **Semantik Protokol HTTP, Idempotensi, dan Safety**  
   Definisikan perbedaan formal antara sifat *Safe* dan *Idempotent* pada HTTP methods (RFC 9110). Analisis mengapa method `POST` dikategorikan non-idempotent sedangkan `PUT` dan `DELETE` idempotent. Bagaimana Anda merancang endpoint `POST /api/v1/payments` agar memiliki karakteristik idempotent di level aplikasi untuk mencegah eksekusi transaksi ganda akibat *network retry* dari client?

5. **Dua Pilar Pemrosesan Web: Web Server vs Application Server**  
   Bedakan tanggung jawab arsitektural antara *Web Server* (misal: Nginx, Apache) dan *Application Server/Runtime* (misal: Node.js V8, Go runtime, Python Gunicorn, JVM). Mengapa merupakan *anti-pattern* fatal di lingkungan produksi untuk mengekspos Application Server langsung ke public internet tanpa dilapisi Reverse Proxy Web Server di depannya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Evolusi HTTP: Head-of-Line (HoL) Blocking pada HTTP/1.1 vs HTTP/2 vs HTTP/3**  
   Jelaskan fenomena *Head-of-Line (HoL) Blocking* pada HTTP/1.1 pipelining. Bagaimana mekanisme *binary framing* dan *multiplexing* pada HTTP/2 menyelesaikan masalah tersebut di level aplikasi? Selanjutnya, analisis mengapa HTTP/2 masih rentan terhadap *TCP-level HoL Blocking* pada koneksi dengan packet loss tinggi, dan bagaimana HTTP/3 (QUIC over UDP) mengatasi limitasi transport-layer ini secara tuntas.

2. **TLS 1.3 Handshake Internals & ALPN Negotiation**  
   Bandingkan alur pertukaran kunci (*key exchange*) pada TLS 1.2 (2-RTT) dengan TLS 1.3 (1-RTT dan 0-RTT/Early Data). Jelaskan peran dari ekstensi *Server Name Indication* (SNI) dan *Application-Layer Protocol Negotiation* (ALPN) saat proses *Client Hello*. Apa risiko keamanan fatal dari implementasi 0-RTT Resumption terkait *replay attacks*, dan mitigasi apa yang wajib diterapkan pada level backend?

3. **Analisis Diferensial HTTP Error Status Codes pada Topologi Multi-Tier**  
   Dalam arsitektur *Client -> Nginx (Reverse Proxy) -> Upstream Application Server -> Database*:
   - Apa perbedaan akar masalah (*root cause*) teknis antara response code `500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, dan `504 Gateway Timeout`?
   - Kondisi spesifik apa pada level socket kernel atau OS process Application Server yang memicu Nginx mengembalikan kode `502` versus kode `504`?

4. **Manajemen Socket: Keep-Alive, Epoll/Kqueue, dan File Descriptor Limits**  
   Jelaskan korelasi antara parameter HTTP `Connection: keep-alive`, batas `ulimit -n` (max open files) pada Linux kernel, dan mekanisme I/O Multiplexing (`epoll` di Linux atau `kqueue` di BSD/macOS). Jika sebuah server menerima 100.000 koneksi konkuren dengan aktivitas rendah, mengapa arsitektur berbasis *thread-per-connection* mengalami *crash* karena *OOM (Out-of-Memory)* atau *high context-switching*, sementara arsitektur berbasis *event-driven non-blocking I/O* dapat bertahan stabil?

5. **Deep-Dive DNS Stale Cache, TTL, dan Dual-Stack Network Failures**  
   Anda melakukan migrasi IP backend secara darurat (*emergency failover*). Meskipun TTL pada DNS record telah disetel ke 60 detik, 30% traffic dari ISP tertentu masih mengarah ke IP lama selama lebih dari 6 jam. Jelaskan penyebab fenomena ini dari sudut pandang *ISP DNS Resolver override*, *JVM/Node.js DNS caching behavior*, dan *Happy Eyeballs algorithm* (RFC 8305) pada dual-stack IPv4/IPv6. Bagaimana strategi teknis untuk memitigasi isu tersebut tanpa mengandalkan kepatuhan resolver publik terhadap TTL?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Skala Besar (Flash Sale Meltdown)
Sebuah platform e-commerce menyelenggarakan program penjualan kilat (*Flash Sale*). Pada detik 00:00:00, traffic melonjak dari 5.000 RPS menjadi 150.000 RPS. Infrastruktur terdiri dari Nginx sebagai Load Balancer yang mengarahkan traffic ke 20 node Application Server.
- **Gejala:** CPU load pada Application Server terpantau rendah (< 20%), memori masih tersedia luas (> 60%), database dalam kondisi normal. Namun, lebih dari 60% pengguna menerima pesan timeout (`504 Gateway Timeout` atau koneksi terputus tiba-tiba).
- **Hasil Pemeriksaan Awal Kernel:** Perintah `netstat -s` menunjukkan ribuan `SYNs to LISTEN sockets dropped`, dan `dmesg` mencatat `TCP: request_sock_subqueue: Possible SYN flooding on port 80. Dropping request.`
- **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat parameter Linux kernel networking apa saja yang menjadi *bottleneck* (analisis `somaxconn`, `tcp_max_syn_backlog`, dan *listen backlog* pada Nginx/App Server).
  2. Mengapa Application Server terlihat idle meskipun puluhan ribu koneksi mengalami kegagalan di gerbang masuk?
  3. Rancang rencana mitigasi teknis berlapis (kernel tuning, Nginx buffer configuration, dan load-shedding architecture) untuk menormalkan traffic seketika.

### Skenario B: Kegagalan Integritas Data & Race Condition (Double-Spending via Network Retry)
Sebuah aplikasi dompet digital mengalami anomali saldo negatif pada ratusan akun pengguna setelah terjadi degradasi konektivitas seluler regional.
- **Kronologi Transaksi:** Client melakukan request `POST /api/v1/wallet/transfer`. Karena koneksi seluler tidak stabil, paket `HTTP Response` dari backend hilang di perjalanan (*packet dropped by cell tower*) meskipun server backend telah berhasil mengeksekusi mutasi database dan commit transaction. Karena response timeout (5000ms), aplikasi mobile secara otomatis mengeksekusi logika *retry* dengan payload yang persis sama sebanyak 3 kali.
- **Hasil Akhir:** Server memproses 3 transaksi tersebut sebagai transaksi independen. Saldo pengguna terpotong 3 kali lipat dari nilai yang seharusnya.
- **Pertanyaan Diagnostik:**
  1. Bedah di layer mana saja kegagalan arsitektur ini terjadi (Client layer, Transport layer, Application layer, atau Database layer)?
  2. Rancang solusi arsitektur backend yang tahan banting menggunakan mekanisme **Idempotency Key Engine** berbasis Redis/Database (jelaskan fase validasi key, atomisitas status `PROCESSING` vs `COMPLETED`, TTL key, dan *concurrent lock*).
  3. Bagaimana server harus merespons request retry yang datang ketika request pertama masih berstatus `PROCESSING` di background thread?

### Skenario C: Arsitektur & Trade-off Teknologi (Real-Time Ingestion System)
Perusahaan logistik armada membutuhkan sistem ingest telemetry data dari 100.000 kendaraan aktif. Setiap kendaraan mengirimkan koordinat GPS, kecepatan, dan status mesin setiap 1 detik (total throughput target: ~100.000 RPS write-heavy). Tim engineering berdebat memilih protokol komunikasi antara perangkat IoT di kendaraan dan sistem backend:
- **Opsi 1:** HTTP/1.1 REST API via JSON payload dengan short-lived connections.
- **Opsi 2:** HTTP/2 over TLS dengan persistent connection dan JSON payload.
- **Opsi 3:** Raw TCP Socket / MQTT over TLS dengan serialisasi binary Protocol Buffers (Protobuf).
- **Pertanyaan Diagnostik:**
  1. Lakukan analisis kuantitatif dan kualitatif terhadap ketiga opsi tersebut. Hitung estimasi pemborosan bandwidth (overhead TCP/TLS handshake dan HTTP headers) pada Opsi 1 jika dibandingkan dengan Opsi 3.
  2. Apa dampak Opsi 1 terhadap *ephemeral port exhaustion* pada server ingress load balancer?
  3. Berikan rekomendasi arsitektur final Anda dengan mempertimbangkan konsumsi resource server, efisiensi bandwidth pada jaringan seluler kendaraan yang fluktuatif, serta kompleksitas pemeliharaan infrastruktur backend.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Raw Multi-Threaded HTTP/1.1 Server dari Socket TCP Murni

#### Problem Statement
Sebagian besar engineer menganggap framework web (seperti Express, Gin, FastAPI, atau Spring Boot) sebagai "black box" ajaib. Untuk memahami secara mendalam apa yang terjadi di balik abstraksi framework, Anda ditantang untuk membangun sebuah HTTP/1.1 Web Server fungsional dari nol (*from scratch*) hanya menggunakan primitif **Raw TCP Socket** (standar library socket bahasa pemrograman pilihan Anda: C, Rust, Go, Python, Java, atau C++), tanpa menggunakan modul/pustaka parsing HTTP bawaan (seperti package `net/http` di Go, modul `http` di Node.js, atau modul `http.server` di Python).

#### Requirements
1. **Socket Initialization & Binding:**
   - Server harus melakukan `socket()`, `bind()` ke address `0.0.0.0:8080`, `listen()` dengan backlog queue terkonfigurasi, dan `accept()` incoming connections.
2. **HTTP/1.1 Parsing Engine (Manual State Machine):**
   - Lakukan parsing manual pada raw byte stream TCP untuk membedah:
     - Request Line: *HTTP Method*, *Request Target (URI)*, dan *HTTP Version*.
     - Headers: Key-Value map (dukung case-insensitive header names).
     - Empty Line separator (`\r\n\r\n`).
     - Message Body: Baca body secara presisi berdasarkan parsing nilai header `Content-Length`.
3. **Core Functionality & Routing:**
   - Endpoint `GET /ping`: Mengembalikan response code `200 OK`, header `Content-Type: text/plain`, dan body `pong`.
   - Endpoint `POST /echo`: Membaca request body berbasis teks, kemudian mengembalikannya utuh ke client dengan status `200 OK` dan header `Content-Type: application/json` berisi JSON `{"echo": "<payload_body>"}`.
   - Fallback routing: Mengembalikan `404 Not Found` untuk path yang tidak didefinisikan, dan `405 Method Not Allowed` untuk method yang tidak didukung.
   - Header Handling: Server wajib menyertakan headers standar pada setiap response: `Server`, `Date` (format RFC 7231 / IMF-fixdate), `Content-Length`, dan `Connection`.
4. **Connection Concurrency & Persistence:**
   - Implementasikan pooling (*Worker Thread Pool* atau *Event Loop / Non-blocking I/O*) agar server mampu melayani minimal 100 request konkuren tanpa memblokir connection berikutnya.
   - Dukung persistent connection melalui header `Connection: keep-alive` (koneksi tidak langsung ditutup setelah 1 request, melainkan menunggu request berikutnya hingga timeout 5 detik tercapai).

#### Constraints
- **Zero HTTP Frameworks / Libraries:** Dilarang keras mengimpor pustaka apapun yang mengekspos HTTP parser, router, atau serializer. Hanya diizinkan socket level rendah (misal: `sys/socket.h` di C/C++, `net` di Go, `socket` di Python, `java.net.ServerSocket` di Java).
- **Buffer Safety:** Implementasikan pembacaan buffer secara defensif untuk mencegah *buffer overflow* atau konsumsi memory tak terbatas jika client mengirim data stream raksasa tanpa `\r\n\r\n`.

#### Expected Output
1. File kode sumber server yang dapat dikompilasi/dijalankan secara langsung di lingkungan terminal Linux/macOS.
2. Eksekusi verifikasi via terminal menggunakan tool `curl` dengan flag verbose:
   ```bash
   curl -v -X POST http://localhost:8080/echo -d "Sistem Terdistribusi Enterprise"
   ```
   Terminal harus menampilkan output response HTTP/1.1 valid dengan status `200 OK`, header `Content-Length` yang tepat secara matematis, serta body JSON yang valid.
3. Hasil pengujian beban (*benchmark*) menggunakan tool benchmarking (misal: `wrk` atau `autocannon`):
   ```bash
   wrk -t4 -c100 -d10s http://localhost:8080/ping
   ```
   Server tidak boleh mengalami *segfault*, *crash*, atau *memory leak*, dan mencatatkan `0 failed requests`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan layer dan batasan abstraksi antara Layer 4 (Transport/TCP/UDP) dan Layer 7 (Application/HTTP) pada model OSI/TCP-IP.
- [ ] Siklus hidup lengkap koneksi TCP: 3-Way Handshake, transmission flow control (Windowing), dan Teardown states (`FIN_WAIT`, `TIME_WAIT`, `CLOSE_WAIT`).
- [ ] Alur resolusi DNS end-to-end, format record (A, AAAA, CNAME, ALIAS, MX, TXT), dan implikasi arsitektural dari DNS caching hierarchy serta TTL.
- [ ] Format spesifikasi framing HTTP/1.1 (Request Line, Headers, Delimiter `\r\n`, Message Body) dan semantik methods (Safe vs Idempotent).
- [ ] Mekanisme handshake TLS 1.2 vs TLS 1.3, peran SNI untuk multi-domain hosting, dan ALPN untuk negosiasi protokol transport.
- [ ] Perbedaan mendasar antara *Head-of-Line Blocking* di level HTTP application layer (HTTP/1.1) vs transport layer (TCP pada HTTP/2).
- [ ] Pola kerja *Event-driven I/O Multiplexing* (`epoll`/`kqueue`) versus arsitektur *Multi-threaded blocking I/O*.

### Saya tidak perlu menghafal:
- [ ] Nilai bit exact/binary mask dari setiap flag pada TCP header (cukup pahami fungsi logis flag `SYN`, `ACK`, `FIN`, `RST`).
- [ ] Daftar lengkap seluruh angka cipher suite hex codes pada TLS (cukup pahami konsep symmetric vs asymmetric encryption dan key exchange).
- [ ] Seluruh nomor port IANA yang terdaftar (cukup pahami port standar: 22, 53, 80, 443, serta konsep *ephemeral port range*).
- [ ] Format string exact penulisan regex untuk parsing setiap varian URL spesifikasi RFC.

### Saya harus bisa melakukan:
- [ ] Melakukan debugging konektivitas jaringan backend secara empiris menggunakan tools CLI fundamental (`dig`, `nslookup`, `curl -vvv`, `nc`/`netcat`, `tcpdump`, `lsof`, `ss`/`netstat`).
- [ ] Menganalisis dan menentukan akar masalah (*root cause*) kegagalan sistem web secara presisi dari status code yang dihasilkan (`400`, `401`, `403`, `404`, `405`, `409`, `429`, `500`, `502`, `503`, `504`).
- [ ] Mengonfigurasi Reverse Proxy (seperti Nginx) untuk TLS termination, upstream proxying, dan penyesuaian header `X-Forwarded-For` serta `X-Real-IP`.
- [ ] Mengidentifikasi dan memecahkan masalah performa terkait OS socket exhaustion (`TIME_WAIT` accumulation dan SYN backlog drop).
- [ ] Merancang kontrak API yang menjamin konsistensi data transaksi dengan mengimplementasikan mekanisme idempotency token pada backend.