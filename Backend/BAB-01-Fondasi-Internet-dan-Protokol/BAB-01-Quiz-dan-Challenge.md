---
[⬅️ Module 02: Evolusi HTTP & Real-Time Protocols](./Module-02-Evolusi-HTTP-WebSockets-dan-Server-Sent-Events.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Module 01: Memory & Concurrency Models ➡️](../BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/Module-01-Manajemen-Memori-dan-Concurrency-Models.md)
---

# BAB 01: Fondasi Internet, HTTP/HTTPS, WebSockets, & DNS — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario arsitektur protokol jaringan, serta tantangan implementasi sistematis untuk BAB 01.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Pada tingkatan manakah protokol HTTP, DNS, dan WebSocket beroperasi dalam model 7-Layer OSI?
- A. Layer 3 (Network Layer)
- B. Layer 4 (Transport Layer)
- C. Layer 7 (Application Layer)
- D. Layer 2 (Data Link Layer)

### Soal 2
Urutan pertukaran paket TCP yang benar dalam pembentukan koneksi andal (*3-Way Handshake*) antara client dan server backend adalah:
- A. `ACK` $\rightarrow$ `SYN` $\rightarrow$ `SYN-ACK`
- B. `SYN` $\rightarrow$ `SYN-ACK` $\rightarrow$ `ACK`
- C. `FIN` $\rightarrow$ `ACK` $\rightarrow$ `FIN-ACK`
- D. `RST` $\rightarrow$ `SYN` $\rightarrow$ `ACK`

### Soal 3
Bagaimana protokol TLS 1.3 memangkas latensi pembentukan koneksi terenkripsi dibandingkan dengan TLS 1.2?
- A. Mengompresi seluruh gambar PNG sebelum handshake dimulai.
- B. Mengeliminasi 1 Round-Trip Time (RTT) dengan menyematkan tebakan kunci publik (*KeyShare ECDHE*) langsung di dalam paket `ClientHello`.
- C. Menghilangkan penggunaan sertifikat digital X.509.
- D. Mengubah enkripsi dari AES-GCM menjadi Base64.

### Soal 4
Apa perbedaan mendasar antara keterbatasan Head-of-Line (HoL) Blocking pada HTTP/1.1 vs HTTP/2?
- A. HTTP/1.1 tidak memiliki HoL Blocking sama sekali.
- B. HTTP/1.1 mengalami HoL Blocking di layer aplikasi (request harus antre bergantian), sedangkan HTTP/2 menyelesaikan HoL aplikasi via multiplexing, namun tetap rentan terhadap HoL Blocking di layer transport TCP jika terjadi kehilangan paket biner (*packet drop*).
- C. HTTP/2 menggunakan UDP, sedangkan HTTP/1.1 menggunakan kabel tembaga.
- D. HTTP/2 hanya mendukung request metode GET.

### Soal 5
Header HTTP manakah yang wajib dikirimkan oleh browser untuk melakukan inisiasi koneksi Server-Sent Events (SSE)?
- A. `Upgrade: websocket`
- B. `Content-Type: text/event-stream`
- C. `Transfer-Encoding: gzip`
- D. `Accept: application/grpc`

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Sebuah aplikasi mobile fintech sering mengalami timeout saat pengguna berpindah dari koneksi Wi-Fi kantor ke koneksi data seluler 5G di tengah proses transfer uang. Protokol modern manakah yang secara arsitektur mampu memecahkan masalah pemutusan koneksi ini via fitur *Connection Migration*?
- A. HTTP/1.0
- B. HTTP/1.1 Keep-Alive
- C. HTTP/3 (QUIC over UDP)
- D. Telnet

### Soal 7
Platform asisten Generative AI perlu mengirimkan token kata hasil inferensi model ke browser pengguna secara mengalir kata per kata. Tim frontend mengusulkan penggunaan WebSocket. Mengapa Senior Backend Architect merekomendasikan **Server-Sent Events (SSE)** alih-alih WebSocket untuk kasus ini?
- A. WebSocket tidak mendukung format teks UTF-8.
- B. Pola interaksi LLM adalah searah (Server ke Client), dan SSE berjalan di atas standar HTTP murni sehingga kompatibel dengan caching CDN, WAF, proxy, serta memiliki kemampuan auto-reconnect bawaan dengan `Last-Event-ID`.
- C. SSE menggunakan enkripsi kuantum yang lebih aman dari WebSocket.
- D. WebSocket membutuhkan izin root di sistem operasi smartphone.

### Soal 8
Server API backend Anda di-load balance oleh NGINX. Saat client mencoba membuka koneksi WebSocket, NGINX mengembalikan error `HTTP 400 Bad Request` atau memutus koneksi seketika. Konfigurasi NGINX apa yang kemungkinan besar terlewatkan?
- A. `proxy_pass http://localhost:3000;`
- B. Header `Upgrade $http_upgrade` dan `Connection "upgrade"` tidak diteruskan ke upstream server.
- C. NGINX belum mengaktifkan modul PHP-FPM.
- D. SSL certificate di NGINX belum menggunakan wildcard domain.

### Soal 9
Banyak koneksi WebSocket di backend server terputus secara misterius setiap 60 detik saat pengguna sedang tidak mengetik pesan. Apa akar penyebab teknis dari fenomena ini dan bagaimana mitigasinya?
- A. Garbage collector bahasa backend menghapus socket; mitigasi: matikan garbage collection.
- B. NAT gateway atau stateful firewall memutus koneksi idle karena ketiadaan traffic; mitigasi: implementasikan *Ping/Pong Heartbeat* berkala setiap 20-30 detik.
- C. Kuota RAM client penuh.
- D. Token JWT client kedaluwarsa tiap 60 milidetik.

### Soal 10
Ketika mengukur latensi API menggunakan `curl`, metrik menunjukkan:
- `time_namelookup`: 0.280s
- `time_connect`: 0.310s
- `time_appconnect`: 0.340s
- `time_starttransfer`: 0.370s
Berdasarkan data di atas, komponen manakah yang menjadi kontributor latency terbesar pada pemanggilan API tersebut?
- A. Eksekusi database backend server.
- B. Negosiasi TLS handshake.
- C. Resolusi nama domain (DNS Lookup) yang memakan waktu 280 milidetik.
- D. Algoritma TCP flow control.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Mitigasi Serangan Replay Attack pada TLS 1.3 0-RTT
Perusahaan perbankan Anda berencana mengaktifkan fitur *TLS 1.3 0-RTT Early Data* untuk mempercepat transaksi mobile banking.
Jelaskan mengapa fitur 0-RTT menimbulkan risiko serangan *Replay Attack* pada transaksi non-idempotent (`POST /transfer`), dan bagaimana Anda merancang arsitektur API Gateway untuk memvalidasi apakah request aman untuk diproses!

### Skenario 2: Migrasi DNS Global Tanpa Downtime
Sebuah sistem backend e-commerce berskala 10 juta pengguna aktif ingin memindahkan infrastruktur dari datacenter lokal ke cloud AWS multi-region.
Rancang strategi migrasi DNS terencana (lengkap dengan manipulasi nilai TTL, DNS weighted routing, dan mitigasi DNS caching pada ISP nakal) agar proses pengalihan traffic berlangsung mulus dengan zero downtime!

### Skenario 3: High-Frequency Stock Trading Dashboard Architecture
Sebuah platform bursa efek melayani 50.000 investor aktif yang memantau pergerakan harga 800 saham secara real-time (1.000 update harga per detik).
Bandingkan trade-off mendalam antara arsitektur berbasis WebSocket (dengan binary protobuf framing) vs SSE (dengan JSON chunks) dalam hal:
- Penggunaan bandwidth jaringan.
- Beban CPU pada backend server.
- Skalabilitas horizontal di balik layer Load Balancer.

---

## Bagian 4: Chapter Challenge — Building a Resilient Duplex Real-Time Engine

### Deskripsi Tantangan
Anda diminta membangun server komunikasi real-time terpadu:
1. **Endpoint SSE (`GET /v1/market/ticker`)**:
   - Menghasilkan stream harga cryptocurrency berkala dalam format `text/event-stream`.
   - Mendukung penanganan header `Last-Event-ID` untuk melanjutkan streaming data yang terputus tanpa ada data yang hilang.
2. **Endpoint WebSocket (`GET /v1/chat`)**:
   - Memvalidasi handshake HTTP Upgrade 101 dengan kalkulasi header `Sec-WebSocket-Accept`.
   - Mengimplementasikan mekanisme framing dengan unmasking payload XOR 4-byte.
   - Mengirimkan frame kontrol Ping setiap 15 detik dan mendeteksi pemutusan koneksi jika Pong tidak diterima dalam 5 detik.
3. **Benchmarking & Latency Verification**:
   - Tulis skrip simulasi benchmark yang membandingkan konsumsi bandwidth antara streaming data menggunakan HTTP/1.1 Short Polling (tiap 1 detik) vs SSE vs WebSocket selama durasi 60 detik!

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Peran setiap layer pada model OSI 7-Layer dan TCP/IP.
- [ ] Alur kerja resolusi hierarki DNS (Root $\rightarrow$ TLD $\rightarrow$ Authoritative).
- [ ] Fase TCP 3-Way Handshake (`SYN`, `SYN-ACK`, `ACK`) dan 4-Way Teardown (`FIN`, `ACK`).
- [ ] Peningkatan performa TLS 1.3 (1-RTT dan 0-RTT) serta pertukaran kunci ECDHE.
- [ ] Perbedaan fundamental HTTP/1.1 vs HTTP/2 vs HTTP/3 (QUIC over UDP).
- [ ] Solusi QUIC terhadap masalah TCP Head-of-Line Blocking.
- [ ] Cara kerja handshake HTTP 101 pada WebSocket.
- [ ] Struktur payload `text/event-stream` dan mekanisme auto-reconnect pada SSE.

### Saya Tidak Perlu Menghafal:
- [ ] Persamaan matematika kurva eliptis Weierstrass pada `secp256r1`.
- [ ] Nilai bitmask heksadesimal dari seluruh field header frame IPv4.

### Saya Harus Bisa Melakukan:
- [ ] Melakukan troubleshooting DNS latency menggunakan `dig` dan `nslookup`.
- [ ] Menganalisis tahapan waktu latency (`time_namelookup`, `time_connect`, `time_appconnect`) via `curl`.
- [ ] Mengimplementasikan endpoint Server-Sent Events (SSE) fungsional di backend.
- [ ] Mengonfigurasi reverse proxy NGINX untuk meneruskan traffic WebSocket dan SSE tanpa buffering.
- [ ] Menangani pemutusan koneksi jaringan dengan mekanisme heartbeat Ping-Pong.

---
[⬅️ Module 02: Evolusi HTTP & Real-Time Protocols](./Module-02-Evolusi-HTTP-WebSockets-dan-Server-Sent-Events.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Module 01: Memory & Concurrency Models ➡️](../BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/Module-01-Manajemen-Memori-dan-Concurrency-Models.md)
---
