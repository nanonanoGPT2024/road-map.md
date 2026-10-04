---
[⬅️ Silabus Induk](../README.md) | [📋 Silabus Induk](../README.md) | [Module 02: Evolusi HTTP & Real-Time Protocols ➡️](./Module-02-Evolusi-HTTP-WebSockets-dan-Server-Sent-Events.md)
---

# Module 01: Bagaimana Internet Bekerja: IP, DNS, TCP/UDP, & TLS 1.3 Handshake

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengurai model berlapis jaringan komputer (**OSI 7-Layer** vs **TCP/IP 4-Layer**) dan perannya dalam pemrosesan request backend.
- Menjelaskan mekanisme pengalamatan **IPv4** (Subnetting, CIDR, NAT, Private vs Public IP) dan perbedaannya dengan **IPv6**.
- Menelusuri hierarki sistem resolusi nama domain (**DNS Resolution Hierarchy**): Resolver, Root Nameserver, TLD Nameserver, Authoritative Nameserver, dan jenis record (`A`, `AAAA`, `CNAME`, `MX`, `TXT`).
- Menguasai cara kerja protokol Transport Layer: **TCP 3-Way Handshake** (`SYN`, `SYN-ACK`, `ACK`), mekanisme *Flow Control* (Sliding Window), *Congestion Control*, dan termination 4-Way (`FIN`/`ACK`) dibandingkan **UDP**.
- Memahami protokol keamanan transport modern: **TLS 1.3 Handshake** (eliminasi round-trip latency menjadi 1-RTT, 0-RTT Resumption), pertukaran kunci asimetris (ECDHE), dan rantai kepercayaan sertifikat X.509 (*CA Chain of Trust*).

---

## 2. Prerequisite
- Pengetahuan dasar tentang sistem operasi (Linux/Windows/macOS).
- Pemahaman konseptual tentang Client dan Server.
- Familiaritas dengan terminal command-line interface.

---

## 3. Concept
Setiap kali seorang pengguna membuka browser atau aplikasi mobile dan mengetik `https://api.perusahaan.com/v1/checkout`, serangkaian protokol jaringan yang dirancang secara presisi dieksekusi dalam hitungan milidetik sebelum baris pertama kode backend (seperti Go, Node.js, Python, atau Java) menerima request tersebut:
1. **DNS Lookup**: Komputer mengubah nama host yang mudah dibaca manusia (`api.perusahaan.com`) menjadi alamat numerik yang dipahami router (**IP Address**).
2. **Network Routing**: Paket data dikemas dan dilewatkan melalui ribuan router internet global (*Autonomous Systems / BGP*).
3. **Transport Handshake**: Client dan Server membentuk koneksi logis yang andal menggunakan **TCP 3-Way Handshake**.
4. **Cryptographic Negotiation**: Kanal komunikasi dienkripsi secara end-to-end melalui negosiasi kriptografi **TLS 1.3 Handshake**.
5. **Application Payload**: Data HTTP dikirimkan dengan aman ke proses backend.

```
+-----------------------------------------------------------------------------------+
|                        THE INTERNET REQUEST LIFECYCLE                             |
|                                                                                   |
|  [ Client Browser / Mobile App ]                                                  |
|       |                                                                           |
|       | 1. DNS Resolution (Resolves "api.company.com" -> 104.21.58.12)            |
|       v                                                                           |
|  [ DNS Hierarchy: Resolver -> Root (.) -> TLD (.com) -> Authoritative ]           |
|       |                                                                           |
|       | 2. TCP 3-Way Handshake (SYN -> SYN-ACK -> ACK)                            |
|       v                                                                           |
|  [ Transport Layer: Reliable connection established ]                             |
|       |                                                                           |
|       | 3. TLS 1.3 Handshake (ClientHello + Keys -> ServerHello + Cert -> Finished)|
|       v                                                                           |
|  [ Cryptographic Layer: AES-GCM Encrypted Channel ]                               |
|       |                                                                           |
|       | 4. HTTP/1.1 or HTTP/2 Request: GET /v1/checkout                           |
|       v                                                                           |
|  [ BACKEND RUNTIME ENGINE (Go / Node.js / Java Server Socket) ]                   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa seorang Backend Engineer harus memahami arsitektur internet hingga level paket jaringan?
1. **Diagnosa Masalah Performa (Latency Debugging)**: Banyak engineer menyalahkan lambatnya database ketika API merespons dalam 500ms, padahal 350ms di antaranya habis untuk DNS lookup yang tidak ter-cache atau negosiasi TLS handshake lintas benua (*round-trip time / RTT overhead*).
2. **Desain Sistem Terdistribusi Skala Global**: Memahami cara kerja BGP Anycast, CDN, dan NAT memungkinkan backend architect merancang topologi multi-region yang tahan banting.
3. **Keamanan & Kepatuhan Regulasi**: Memahami sertifikat SSL/TLS, cipher suites, dan proteksi DNS spoofing adalah syarat mutlak sistem transaksi finansial.

---

## 5. What?

### A. Model Jaringan: OSI 7-Layer vs TCP/IP
- **Layer 7 (Application)**: HTTP, HTTPS, WebSocket, DNS, gRPC, SMTP.
- **Layer 4 (Transport)**: TCP (Connection-oriented, Reliable, Ordered), UDP (Connectionless, Unreliable, Fast).
- **Layer 3 (Network)**: IP (IPv4/IPv6), ICMP, Routing (BGP, OSPF).
- **Layer 2 (Data Link)**: Ethernet, MAC Address, Switch.
- **Layer 1 (Physical)**: Kabel serat optik, radio Wi-Fi/5G, sinyal listrik.

### B. DNS Resolution Hierarchy (Langkah Demi Langkah)
Ketika client mencari IP dari `api.bank.co.id`:
1. **DNS Cache Lokal**: Browser dan OS memeriksa cache internal.
2. **Recursive Resolver**: Resolver ISP atau Public DNS (`8.8.8.8` / `1.1.1.1`) menerima query.
3. **Root Nameserver (`.`)**: Mengarahkan resolver ke TLD nameserver `.id`.
4. **TLD Nameserver (`.id` / `.co.id`)**: Mengarahkan resolver ke Authoritative Nameserver `bank.co.id`.
5. **Authoritative Nameserver**: Mengembalikan jawaban definitif: `api.bank.co.id IN A 103.12.44.2` dengan nilai **TTL (Time to Live)**.

### C. TCP vs UDP
| Karakteristik | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
|---|---|---|
| **Koneksi** | Connection-oriented (Wajib handshake) | Connectionless (Kirim langsung) |
| **Keandalan** | 100% Reliable (Retransmisi otomatis jika paket hilang) | Unreliable (Best-effort, paket bisa hilang/acak) |
| **Urutan Data** | Terjamin (Packet sequence numbering) | Tidak ada jaminan urutan |
| **Flow & Congestion Control**| Ada (Sliding window & window scaling) | Tidak ada |
| **Use Case** | REST API, Web, Transaksi Bank, SSH, Database | Video Streaming, Gaming, Voice over IP (VoIP), DNS |

### D. TLS 1.2 vs TLS 1.3 Handshake
- **TLS 1.2 (Legacy)**: Membutuhkan **2 Round-Trip Times (2-RTT)** sebelum data HTTP pertama dapat dikirimkan. Masih mendukung cipher lama yang rentan terhadap serangan downgrade (*CBC mode, RSA key exchange*).
- **TLS 1.3 (Modern)**: Memangkas handshake menjadi hanya **1 Round-Trip Time (1-RTT)**!
  - Client langsung menyematkan tebakan kunci publik (*Key Share ECDHE*) di dalam paket `ClientHello`.
  - Server langsung merespons dengan `ServerHello`, sertifikat, dan kunci publiknya, lalu enkripsi langsung aktif.
  - Mendukung **0-RTT Resumption** (*Early Data*): Client yang pernah terhubung sebelumnya dapat langsung mengirimkan HTTP request terenkripsi pada paket handshake pertama.

---

## 6. How?

### Alur Kerja TCP 3-Way Handshake
```
CLIENT                                              SERVER
  |                                                    |
  | -------- 1. SYN (Seq = 100) ---------------------> | (Server receives SYN)
  |                                                    |
  | <------- 2. SYN-ACK (Seq = 300, Ack = 101) ------- | (Client receives SYN-ACK)
  |                                                    |
  | -------- 3. ACK (Seq = 101, Ack = 301) ----------> | (Server receives ACK)
  |                                                    |
  [ KONEKSI TCP RESMI TERBENTUK (ESTABLISHED) ]
```

### Alur Kerja TLS 1.3 (1-RTT Handshake)
```
CLIENT                                              SERVER
  |                                                    |
  | -- 1. ClientHello                                  |
  |       + Supported Cipher Suites (AES-256-GCM)      |
  |       + KeyShare (Client ECDHE Public Key) ------> |
  |                                                    |
  | <------------------------------------------------- |
  |    2. ServerHello                                  |
  |       + Selected Cipher Suite                      |
  |       + KeyShare (Server ECDHE Public Key)         |
  |       + {EncryptedExtensions}                      |
  |       + {Certificate & Verify Signature}           |
  |       + {Finished}                                 |
  |                                                    |
  [ SHARED SECRET COMPUTED SECURELY ON BOTH SIDES ]    |
  |                                                    |
  | -- 3. [Encrypted HTTP Data: GET /api/v1] --------> |
```

---

## 7. Analogy
Bayangkan **Mengirimkan Dokumen Rahasia Antar Kantor Cabang**:
- **IP Address**: Alamat jalan fisik dan nomor gedung kantor penerima.
- **DNS**: Buku telepon kuning (Yellow Pages) yang mengubah nama "PT Finansial Jaya" menjadi "Jl. Sudirman Kav 45".
- **TCP 3-Way Handshake**: Prosedur telepon awal:
  1. Anda menelepon: *"Halo, apakah ini kantor penerima dokumen?"* (`SYN`)
  2. Penerima menjawab: *"Ya benar, saya siap menerima, apakah Anda siap mengirim?"* (`SYN-ACK`)
  3. Anda mengonfirmasi: *"Baik, saya kirimkan kurir sekarang."* (`ACK`)
- **TLS 1.3**: Kurir tidak membawa dokumen terbuka, melainkan membawa **Brankas Baja Khusus**. Anda dan penerima bertukar kode gembok kombinasi secara rahasia di telepon dalam satu putaran singkat, sehingga kurir atau penyadap di jalan tidak akan pernah bisa membaca isi dokumen di dalam brankas.

---

## 8. Diagram

```
+---------------------------------------------------------------------------------+
|                       NETWORK ENCAPSULATION (PACKET TRAVEL)                     |
+---------------------------------------------------------------------------------+

Layer 7 (Application)  : [ HTTP Payload: {"amount": 50000} ]
                                   | Encapsulated into
Layer 4 (Transport)    : [ TCP Header | Source Port: 54122, Dest Port: 443 | Payload ]
                                   | Encapsulated into
Layer 3 (Network)      : [ IP Header  | Src: 192.168.1.5, Dst: 104.21.58.12 | TCP Pkt ]
                                   | Encapsulated into
Layer 2 (Data Link)    : [ Ethernet   | Src MAC: aa:bb:.., Dst MAC: router | IP Pkt | FCS ]
                                   | Encoded into
Layer 1 (Physical)     : [ 01101001011011100111010001100101011100100110111001100101... ]
```

---

## 9. Simple Example: Membedah DNS Record via CLI

Menggunakan utilitas bawaan `dig` atau `nslookup`:

```bash
# 1. Query A Record (IPv4)
dig A api.github.com +short
# Output: 20.205.243.166

# 2. Query AAAA Record (IPv6)
dig AAAA google.com +short
# Output: 2607:f8b0:4005:809::200e

# 3. Query MX Record (Mail Server)
dig MX google.com +short
# Output: 10 smtp.google.com.

# 4. Melacak seluruh rantai resolusi DNS dari root server (+trace)
dig api.github.com +trace
```

---

## 10. Practical Example: Mengukur Latensi TCP & TLS Handshake via `curl`

Gunakan format metrik canggih `curl` untuk mengisolasi di mana bottleneck waktu terjadi:

```bash
curl -w "\
Lookup DNS Time     :  %{time_namelookup} s\n\
TCP Connect Time    :  %{time_connect} s\n\
TLS Handshake Time  :  %{time_appconnect} s\n\
Pre-transfer Time   :  %{time_pretransfer} s\n\
Start-transfer (TTFB): %{time_starttransfer} s\n\
Total Time          :  %{time_total} s\n" \
-o /dev/null -s https://httpbin.org/get
```

*Interpretasi Output*:
- `time_namelookup`: Waktu yang dihabiskan untuk DNS query.
- `time_connect - time_namelookup`: Durasi TCP 3-Way Handshake murni.
- `time_appconnect - time_connect`: Durasi TLS Handshake murni.
- `time_starttransfer - time_appconnect`: Time to First Byte (**TTFB**) — waktu yang dibutuhkan proses backend memproses request sebelum mengirimkan respon pertama.

---

## 11. Real World Example: Migrasi ke TLS 1.3 Memangkas 150ms Latensi E-Commerce
Sebuah platform marketplace global melayani jutaan pengguna di wilayah Asia Tenggara. Pengguna mobile yang terhubung lewat jaringan 3G/4G memiliki latency RTT jaringan fisik yang tinggi (~80ms per round trip).
- Pada **TLS 1.2**: Pembentukan koneksi membutuhkan:
  - 1 RTT untuk TCP (`80ms`)
  - 2 RTT untuk TLS (`160ms`)
  - Total sebelum request pertama terkirim = **240ms**!
- Setelah di-upgrade ke **TLS 1.3**:
  - 1 RTT untuk TCP (`80ms`)
  - 1 RTT untuk TLS (`80ms`)
  - Total = **160ms** (Penghematan instan **80ms / 33%** tanpa mengubah 1 baris kode aplikasi pun!).
- Dengan **0-RTT Resumption**, untuk pengguna yang kembali (*returning visitors*), data HTTP dikirim bersamaan dengan paket handshake pertama, memangkas latency menjadi hanya **80ms**!

---

## 12. Trade-offs

| Fitur | Keuntungan | Pertimbangan / Risiko |
|---|---|---|
| **TCP** | Menjamin integritas data 100%, bebas korupsi | Overhead header (20-60 byte), latency handshake, rentan Head-of-Line blocking |
| **UDP** | Latency terendah, header sangat kecil (8 byte) | Aplikasi harus menangani sendiri deteksi paket hilang atau duplikat |
| **TLS 1.3 0-RTT** | Waktu koneksi tercepat di dunia | Rentan terhadap serangan **Replay Attack** jika request non-idempotent (misal POST transfer dana) |
| **DNS TTL Panjang (86400s)** | Mengurangi beban server DNS, response client instan | Jika IP server berubah, butuh waktu hingga 24 jam untuk propagasi global |

---

## 13. When To Use
- Gunakan **TCP** untuk seluruh API transaksi, transfer data, autentikasi, dan komunikasi database yang membutuhkan jaminan integritas biner mutlak.
- Gunakan **UDP** untuk streaming audio/video langsung, game multiplayer online, atau metrik telemetri bervolume raksasa (StatsD/OpenTelemetry metrics) di mana kehilangan 1 sampel data tidak merusak sistem.
- Selalu wajibkan **TLS 1.3** dan nonaktifkan cipher lawas (SSLv3, TLS 1.0, TLS 1.1) pada seluruh server API produksi.

---

## 14. When NOT To Use
- **JANGAN** menggunakan mode **TLS 1.3 0-RTT Early Data** untuk endpoint HTTP non-idempotent (seperti `POST /api/v1/payments`), karena penyerang dapat menangkap paket terenkripsi tersebut di jaringan Wi-Fi publik dan mengirimkannya ulang (*Replay Attack*) sehingga saldo korban terdebit berkali-kali.
- Jangan menggunakan UDP jika Anda tidak memiliki lapisan aplikasi yang memvalidasi integritas paket (*checksum validation*).

---

## 15. Common Mistakes
1. **Mengabaikan DNS TTL Saat Migrasi Server**: Mengubah DNS A record di server hosting tanpa menurunkan TTL terlebih dahulu. Akibatnya, jutaan client masih mengakses server lama selama berhari-hari.
2. **Tidak Menggunakan Keep-Alive**: Membuka koneksi TCP dan TLS baru untuk setiap request HTTP individual, menghabiskan 80% CPU server hanya untuk negosiasi kriptografi handshake.
3. **Membagikan Private Key Sertifikat TLS**: Menganggap file `.key` sertifikat boleh di-commit ke repositori Git publik. Private key harus disimpan di HSM atau Secret Manager.

---

## 16. Best Practices
- **Must Have**: Pasang header **HTTP Strict Transport Security (HSTS)**:
  `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- **Recommended**: Turunkan DNS TTL menjadi `300` detik (5 menit) setidaknya 48 jam sebelum jadwal migrasi IP server produksi.
- **Advanced**: Implementasikan **OCSP Stapling** pada server web/load balancer untuk mempercepat verifikasi status pencabutan sertifikat TLS tanpa membuat client bertanya ke CA server.
- **Avoid**: Menjalankan API backend publik menggunakan HTTP port 80 tanpa redirect otomatis ke HTTPS port 443.

---

## 17. Troubleshooting Guide
```
Masalah: Client mendapatkan error "SSL: CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate".
Penyebab : Server web hanya mengirimkan sertifikat domain daun (leaf certificate) dan lupa menyertakan sertifikat perantara (Intermediate CA bundle).
Diagnosa : openssl s_client -connect api.perusahaan.com:443 -showcerts
Solusi   : Gabungkan full chain certificate (domain cert + intermediate certs) ke dalam file 'fullchain.pem' di konfigurasi NGINX/Caddy.

Masalah: Backend server melempar error "TCP Connection Reset by Peer" (ECONNRESET).
Penyebab : Server penerima menutup socket secara paksa karena timeout idle, atau firewall stateful di tengah jalan memutuskan sesi TCP.
Solusi   : Sesuaikan parameter TCP keepalive (SO_KEEPALIVE) dan selaraskan idle timeout antara load balancer dan backend service.
```

---

## 18. Exercise
1. Jalankan perintah `dig` atau `nslookup` untuk domain `wikipedia.org`. Catat seluruh record `A`, `AAAA`, dan `NS` yang dihasilkan beserta nilai TTL-nya.
2. Gunakan perintah `curl` dengan flag `-w` (seperti pada bagian Practical Example) untuk membedah waktu DNS, TCP Connect, dan TLS Handshake dari sebuah API publik.
3. Hitung persentase waktu yang dihabiskan untuk handshake jaringan dibandingkan waktu pemrosesan server backend (TTFB).

---

## 19. Challenge
Rancang arsitektur jaringan API gateway backend yang mampu melayani pengguna global dengan latensi TCP/TLS di bawah 50ms di seluruh dunia:
1. Rekomendasikan kombinasi Anycast DNS, CDN Edge Termination, dan protokol TLS yang tepat.
2. Jelaskan bagaimana koneksi TCP antara Edge CDN dan Origin Server dioptimalkan menggunakan persistent connection pooling.
3. Tuliskan analisis perbandingan matematis latency jika client mengakses origin server langsung di Frankfurt vs melalui Edge PoP di Jakarta!

---

## 20. Summary
Memahami fondasi internet—mulai dari resolusi DNS, keandalan koneksi TCP 3-Way Handshake, hingga efisiensi kriptografi TLS 1.3—merupakan pembeda utama antara coder biasa dan Senior Backend Engineer sejati. Fondasi ini menjadi pijakan kokoh untuk memahami evolusi protokol HTTP modern dan teknologi streaming real-time pada modul berikutnya.

---
[⬅️ Silabus Induk](../README.md) | [📋 Silabus Induk](../README.md) | [Module 02: Evolusi HTTP & Real-Time Protocols ➡️](./Module-02-Evolusi-HTTP-WebSockets-dan-Server-Sent-Events.md)
---
