# BAB 02: Quiz, Challenge, & Knowledge Check
**Protokol HTTP/HTTPS & Web Communication**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Evolusi Protokol: HTTP/1.1 vs HTTP/2**
   Jelaskan secara mendalam bagaimana HTTP/2 menyelesaikan masalah *Application-Layer Head-of-Line (HoL) Blocking* yang melekat pada HTTP/1.1. Dalam jawaban Anda, bedah konsep *Binary Framing Layer*, *Streams*, *Messages*, dan *Frames*, serta jelaskan mengapa HTTP/2 tetap rentan terhadap *Transport-Layer HoL Blocking* di level TCP saat terjadi *packet loss*.

2. **Semantika Metode HTTP: Safety vs Idempotency**
   Bedakan secara matematis dan arsitektural antara konsep *Safe Method* dan *Idempotent Method*. Mengapa `PUT` didefinisikan sebagai *idempotent* sedangkan `POST` tidak, dan apa konsekuensi praktis dari perbedaan ini terhadap mekanisme *automatic retry* pada reverse proxy, API gateway, atau HTTP client libraries ketika terjadi network timeout?

3. **Kriptografi & Siklus TLS 1.3 Handshake**
   Uraikan langkah-langkah komputasi dan pertukaran data yang terjadi pada proses *TLS 1.3 Handshake* (1-RTT). Jelaskan peran *Ephemeral Diffie-Hellman (ECDHE)* dalam menjamin *Forward Secrecy*, serta bedah alasan keamanan mengapa algoritma RSA key exchange dan cipher suites berbasis static key exchange didepresiasi sepenuhnya pada TLS 1.3.

4. **Semantika HTTP Caching & Validasi Kondisional**
   Jelaskan perbedaan mendasar antara direktif `Cache-Control: no-cache` dan `Cache-Control: no-store`. Bagaimana mekanisme validasi kondisional bekerja menggunakan pasangan header `ETag` / `If-None-Match` versus `Last-Modified` / `If-Modified-Since`? Mengapa *Strong ETag* lebih superior dibandingkan timestamp dalam sistem terdistribusi?

5. **State Management pada Protokol Stateless**
   HTTP didesain secara fundamental sebagai protokol yang *stateless*. Bandingkan tiga pendekatan implementasi *state management*:
   - *Stateful Session Store* (Session ID di Cookie + In-Memory DB/Redis)
   - *Stateless Client-Side Token* (Self-contained JWT)
   - *Client-Side Encrypted Cookies*
   
   Evaluasi ketiganya dari sudut pandang *horizontal scalability*, *revocation capability*, dan risiko keamanan (*replay attack* serta *token size overhead* pada bandwidth).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Persistent Connection, Keep-Alive, dan Port Exhaustion**
   Jelaskan perbedaan antara TCP Keep-Alive (SO_KEEPALIVE socket option) dan HTTP Persistent Connections (`Connection: keep-alive`). Apa dampak sistemik yang terjadi pada backend OS kernel (khususnya status socket `TIME_WAIT` dan alokasi *ephemeral ports*) jika backend service melakukan panggilan HTTP keluar (HTTP outbound) ke downstream microservice tanpa menggunakan *Connection Pooling*?

2. **Anatomi dan Debugging Cross-Origin Resource Sharing (CORS)**
   Sebuah *Single Page Application* (SPA) pada domain `https://app.corp.com` melakukan request `PUT` dengan custom header `X-Trace-Id` dan `Content-Type: application/json` ke API di `https://api.corp.com`.
   - Mengapa browser memicu *Preflight Request* (`OPTIONS`)?
   - Mengapa konfigurasi header `Access-Control-Allow-Origin: *` akan ditolak oleh browser jika request tersebut menyertakan kredensial (`withCredentials = true`)?
   - Bagaimana mekanisme backend merespons preflight tersebut secara aman dan compliant?

3. **Streaming & Chunked Transfer Encoding**
   Bagaimana mekanisme `Transfer-Encoding: chunked` bekerja di tingkat byte stream? Mengapa header `Content-Length` dilarang hadir saat header ini aktif? Identifikasi potensi kerentanan keamanan (*HTTP Request Smuggling*) yang dapat timbul jika sebuah reverse proxy dan upstream server memiliki interpretasi yang berbeda terhadap request yang memuat kedua header (`Transfer-Encoding` dan `Content-Length`) secara bersamaan (CL.TE / TE.CL vulnerabilities).

4. **Reverse Proxy Headers & Trust Boundary**
   Ketika backend menerima request dari reverse proxy (seperti NGINX, Cloudflare, atau AWS ALB), client IP address asli berada di header seperti `X-Forwarded-For` atau `X-Real-IP`. Jelaskan bahaya keamanan dari implementasi naïf `req.headers['x-forwarded-for'].split(',')[0]` untuk sistem *Rate Limiting*. Bagaimana arsitektur *Rightmost-Trust* atau konfigurasi *Trusted Proxies CIDR* memitigasi *header spoofing attack* ini?

5. **HTTP Content Negotiation & Kompresi Data**
   Jelaskan alur *Proactive Content Negotiation* untuk encoding data payload (`Accept-Encoding: gzip, br, zstd` vs `Content-Encoding`). Dari perspektif konsumsi CPU vs ukuran payload, pada skenario payload seperti apa kompresi HTTP justru menimbulkan degradasi performa (*negative performance return*), dan bagaimana backend server harus mengaturnya menggunakan header `Vary`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi - 504 Gateway Timeout pada Flash Sale (Skala Besar)
Sebuah platform e-commerce mengalami lonjakan trafik ekstrem saat *flash sale*. Pola arsitektur: Client -> NGINX Reverse Proxy -> Golang Backend API. 
Setelah 3 menit flash sale berjalan, NGINX mulai mengembalikan jutaan respon `504 Gateway Timeout` ke pengguna. Metrik pada instance Golang menunjukkan penggunaan CPU berada di angka 15% dan memori di angka 30% (tidak saturasi compute). Namun, log NGINX dipenuhi error:
`connect() failed (110: Connection timed out) while connecting to upstream` dan `connect() failed (99: Cannot assign requested address) while connecting to upstream`.

**Pertanyaan Diagnostik:**
1. Analisis akar masalah (root cause) sistemik yang terjadi di tingkat kernel TCP antara NGINX dan Golang backend terkait error `Cannot assign requested address`.
2. Jelaskan parameter socket, kernel tuning (`sysctl`), dan konfigurasi NGINX *upstream block* apa yang wajib dimodifikasi untuk menstabilkan pipeline koneksi tersebut.
3. Bagaimana mitigasi arsitektur jaringan dilakukan jika NGINX dan backend berada dalam private network yang sama (misalnya beralih ke Domain Sockets, Keep-Alive Upstreams, atau penambahan egress IP)?

---

### Skenario B: Data Integrity & Race Condition - Insiden Double-Debiting Akibat Retry Storm
Sistem perbankan digital memiliki microservice transaksi finansial. Endpoint pembayaran adalah:
`POST /api/v1/payments/transfer`
Ketika terjadi penurunan performa jaringan selama 45 detik, koneksi antara Mobile Client / API Gateway dan Microservice Pembayaran sering kali terputus akibat client-side timeout (5 detik). 
Banyak pengguna menekan tombol "Transfer" berulang kali karena mendapati pesan "Network Timeout". Akibatnya, saldo puluhan ribu nasabah terpotong 2 hingga 4 kali untuk satu transaksi yang sama, meskipun database backend menggunakan *ACID Transactions* standar.

**Pertanyaan Diagnostik:**
1. Mengapa transaksi database ACID lokal tidak mampu mencegah *double-debiting* dalam skenario hilangnya respons HTTP di tengah jalan (split-brain/network partition antara client dan server)?
2. Rancanglah solusi arsitektur end-to-end berbasis **Idempotency Key Engine** menggunakan protokol HTTP. Spesifikasikan header apa yang wajib digunakan, siklus hidup *idempotency record*, serta penanganan *in-flight requests* jika ada dua request ber-ID sama yang masuk bersamaan (*concurrent execution*).
3. Status code HTTP apa yang harus dikembalikan server jika request kedua dengan ID yang sama datang saat request pertama:
   - Masih dalam proses eksekusi (*processing*).
   - Telah selesai dieksekusi dengan sukses (*success*).
   - Telah selesai dieksekusi namun menghasilkan error bisnis (*failed*).

---

### Skenario C: Arsitektur & Trade-off - Pemilihan Protokol Real-Time Notification Engine
Anda diminta merancang subsistem backend yang bertugas mendorong update harga saham secara real-time (100–500 pembaruan harga per detik per instrumen) kepada 500.000 pengguna aktif yang terhubung bersamaan via web dan mobile. Sistem ini bersifat unidireksional (data didorong secara strictly dari server ke client; client tidak perlu mengirim data balik melalui kanal real-time tersebut).

Arsitektur yang dipertimbangkan:
- **Opsi 1**: HTTP Short Polling (interval 1 detik).
- **Opsi 2**: HTTP Long Polling.
- **Opsi 3**: Server-Sent Events (SSE) di atas HTTP/2.
- **Opsi 4**: Full-Duplex WebSockets (di atas TCP).

**Pertanyaan Diagnostik:**
1. Lakukan analisis kuantitatif dan kualitatif atas kelemahan fatal Opsi 1 dan 2 terkait *HTTP header overhead* dan utilisasi bandwidth backend.
2. Bandingkan trade-off mendalam antara **Opsi 3 (SSE via HTTP/2)** dan **Opsi 4 (WebSockets)** dalam konteks kebutuhan sistem:
   - Efisiensi resource server (memory footprint & thread management).
   - Kemampuan menembus corporate proxy, firewall, dan WAF layer-7.
   - Kompleksitas *load balancing* dan *connection multiplexing*.
3. Tentukan pilihan arsitektur paling optimal dan berikan justifikasi teknis tingkat *Principal Engineer* atas keputusan Anda.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa HTTP/1.1 Engine dari Scratch Menggunakan Raw TCP Sockets

#### Problem Statement
Sebagian besar engineer hanya mengonsumsi HTTP melalui *high-level frameworks* (Express, Spring, Gin, Fastify) tanpa memahami mekanika state-machine di tingkat byte stream. Untuk memahami protokol secara mendalam, Anda ditugaskan membangun sebuah **HTTP/1.1 Server Engine** minimalis dari nol hanya menggunakan abstraksi *Raw TCP Sockets* (misalnya package `net` di Go, module `net` di Node.js, atau socket library di C/Rust/Python), **tanpa menggunakan library HTTP bawaan bahasa ataupun third-party**.

#### Functional Requirements
1. **RFC 7230 Compliant Parsing**:
   - Membaca dan mem-parsing *Request Line* (`Method`, `Request-URI`, `HTTP-Version`).
   - Mem-parsing multi-line *Headers* menjadi struktur key-value yang case-insensitive.
   - Mendeteksi batas akhir header via CRLF ganda (`\r\n\r\n`).
2. **Body Extraction Engine**:
   - Mampu menangani request dengan `Content-Length` (baca sejumlah byte tertentu secara presisi).
   - Mampu menangani streaming payload dengan `Transfer-Encoding: chunked` (membaca hex chunk size, payload, hingga terminating zero chunk `0\r\n\r\n`).
3. **Connection State Management**:
   - Mengimplementasikan HTTP/1.1 *Persistent Connection* (`Connection: keep-alive`) secara default.
   - Menutup koneksi TCP jika client menyertakan `Connection: close`.
   - Mengimplementasikan *Keep-Alive Idle Timeout*: jika client tidak mengirim byte baru dalam waktu 5 detik pada koneksi yang terbuka, server wajib menutup koneksi TCP secara graceful.
4. **Deterministic Response Generation**:
   - Menghasilkan respon HTTP yang valid lengkap dengan *Status Line*, header wajib (`Date`, `Content-Type`, `Content-Length` atau `Transfer-Encoding`), dan body.
   - Menyertakan validasi status codes: `200 OK`, `400 Bad Request` (jika parsing gagal), `404 Not Found`, `408 Request Timeout`, dan `500 Internal Server Error`.

#### Constraints
- Dilarang keras menggunakan package `http`, `express`, `fastify`, `axum`, `actix-web`, `aiohttp`, `servlet`, atau parser HTTP berbasis library seperti `llhttp`.
- Harus mengelola buffer stream secara manual; dilarang berasumsi bahwa satu TCP packet berisikan satu HTTP request utuh (*TCP packet fragmentation & aggregation must be handled*).
- Server harus bersifat non-blocking atau multi-threaded/concurrent sehingga dapat melayani setidaknya 100 concurrent persistent TCP connections tanpa deadlock.

#### Expected Output
1. Script / repository kode mandiri yang dapat dijalankan secara lokal.
2. Demonstrasi sukses pengujian eksternal:
   - Server dapat di-request menggunakan `curl -v http://localhost:<port>/test`.
   - Server merespons benchmarking via tool seperti `wrk` atau `autocannon` dengan 0 socket/parsing errors:
     ```bash
     wrk -t4 -c100 -d10s http://localhost:<port>/
     ```
   - Log server menampilkan transisi state: Socket Open -> Request Parsed -> Response Dispatched -> Socket Idle -> Socket Closed.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan layer arsitektural OSI model antara TCP (Layer 4) dan HTTP (Layer 7).
- [ ] Siklus hidup lengkap HTTP/1.1, HTTP/2, dan HTTP/3 (QUIC via UDP).
- [ ] Perbedaan esensial serta implikasi operasional antara *Safe methods* (`GET`, `HEAD`) dan *Idempotent methods* (`PUT`, `DELETE`).
- [ ] Mekanika jabat tangan kriptografi TLS 1.3, termasuk negosiasi symmetric key melalui ECDHE.
- [ ] Mekanisme Browser Security Model: CORS, Same-Origin Policy (SOP), Preflight requests, dan kredensial cookies.
- [ ] Semantika HTTP Caching, prioritas direktif `Cache-Control`, serta peran `ETag` dan `Last-Modified`.
- [ ] Konsekuensi TCP socket state (`TIME_WAIT`, `CLOSE_WAIT`) terhadap ketahanan sistem backend saat menangani traffic tinggi.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor port IANA yang terdaftar di luar port web standar (80, 443, 8080, 8443).
- [ ] Seluruh tabel biner detail dari framing format HTTP/2 atau spesifikasi byte-by-byte QUIC packets (cukup pahami cara kerjanya secara konseptual).
- [ ] Seluruh ratusan cipher suite strings OpenSSL TLS secara verbatim (cukup pahami perbedaan cipher modern seperti AES-GCM vs ChaCha20-Poly1305 dan depresiasi cipher usang seperti RC4/CBC/RSA exchange).
- [ ] Seluruh daftar status code HTTP non-standar atau vendor-specific (misalnya Cloudflare 52x codes).

### Saya harus bisa melakukan:
- [ ] Melakukan inspeksi dan debugging HTTP traffic mentah secara interaktif menggunakan command-line tools (`curl -v`, `openssl s_client`, `tcpdump`, atau `Wireshark`).
- [ ] Mendiagnosis dan memperbaiki konfigurasi CORS yang rusak di production tanpa mengambil jalan pintas berbahaya (`Access-Control-Allow-Origin: *` pada secure endpoints).
- [ ] Menganalisis dan mengidentifikasi bottleneck koneksi (misal: DNS resolution latency, TLS handshake delay, TTFB, transfer time) melalui output timing `curl` (`%{time_namelookup}`, `%{time_connect}`, `%{time_appconnect}`, `%{time_starttransfer}`).
- [ ] Merancang kontrak API yang tangguh dengan mematuhi semantika status codes, idempotency headers, dan caching tags yang tepat.
- [ ] Mengonfigurasi parameter *HTTP Connection Pooling* yang optimal (Keep-Alive timeout, Max Idle Connections, Max Conns Per Host) pada HTTP Client maupun Reverse Proxy.