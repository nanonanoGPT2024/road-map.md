# Module 01: Jaringan Komputer untuk DevOps (OSI, TCP/UDP, DNS, & TLS/SSL)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami arsitektur hierarki model OSI 7-Layer dan pemetaannya pada stack TCP/IP nyata di cloud.
2. Membedakan karakteristik transmisi data connection-oriented (TCP 3-Way Handshake, Flow Control, Congestion Control) vs connectionless (UDP).
3. Menguasai alur resolusi DNS (*Recursive vs Authoritative Nameservers*, TTL, dan record tipe A, CNAME, TXT, MX).
4. Menganalisis mekanisme keamanan enkripsi TLS 1.3 Handshake, sertifikasi X.509, dan proses termination SSL di level proxy.

---

## 2. Prerequisite
- Memahami konsep dasar soket proses Linux dan port jaringan dari [BAB 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-01-Sistem-Operasi-dan-Linux-Automation/Module-01-Arsitektur-Kernel-Linux-Manajemen-Proses-dan-Konkurensi.md).
- Mengetahui penggunaan dasar utilitas command line (`curl`, `ping`).

---

## 3. Concept
Dalam dunia DevOps dan SRE, ada lelucon terkenal di industri: *"It's always DNS!"* (Setiap kali sistem down, kemungkinan besar penyebabnya adalah DNS atau jaringan).

Aplikasi microservices modern tidak berdiri sendiri di satu mesin fisik. Mereka berkomunikasi melintasi jaringan lokal (VPC), antar subnet, hingga ke internet publik:
- **Layer Jaringan**: Memahami di layer mana sebuah masalah terjadi (apakah layer 3 IP routing, layer 4 port firewall, atau layer 7 HTTP payload) adalah kunci troubleshooting.
- **TCP (Transmission Control Protocol)**: Protokol andal yang menjamin setiap paket data tiba secara utuh dan berurutan melalui *Three-Way Handshake* (`SYN` -> `SYN-ACK` -> `ACK`).
- **DNS (Domain Name System)**: Buku telepon internet yang menerjemahkan hostname manusiawi (`api.example.com`) menjadi alamat IP mesin (`192.0.2.1`).
- **TLS/SSL (Transport Layer Security)**: Lapisan enkripsi kriptografis yang melindungi integritas dan kerahasiaan data di atas TCP menggunakan sertifikat digital publik/privat.

---

## 4. Why?
Mengapa pemahaman jaringan mutlak bagi DevOps?
1. **Diagnosis Cepat Latensi & Timeout**: Memahami TCP slow-start, time-wait sockets, dan MTU overhead membantu Anda mendiagnosis bottleneck koneksi antar microservices.
2. **Keamanan & Kepatuhan**: Mengonfigurasi enkripsi data in-transit (TLS 1.3 wajib) dan pengelolaan rotasi sertifikat (Let's Encrypt / Cert-Manager di Kubernetes).
3. **Infrastruktur Multi-Region**: Merancang arsitektur failover DNS (Route 53 latency routing / geo-routing) untuk menjamin uptime global.

---

## 5. What?
Konsep jaringan fundamental:
- **Model OSI vs TCP/IP**:
  - *Layer 7 (Application)*: HTTP, HTTPS, gRPC, DNS, SSH.
  - *Layer 4 (Transport)*: TCP, UDP (Port numbers, socket connections).
  - *Layer 3 (Network)*: IP (IPv4, IPv6, routing, ICMP ping).
  - *Layer 2 (Data Link)*: Ethernet, MAC address, ARP.
- **TCP 3-Way Handshake & Teardown**:
  - Membuka koneksi: `SYN` -> `SYN-ACK` -> `ACK`.
  - Menutup koneksi: `FIN` -> `ACK` -> `FIN` -> `ACK`.
- **Anatomi DNS Query**:
  - Root Nameservers (`.`) -> TLD Nameservers (`.com`) -> Authoritative Nameservers (`ns1.awsdns.com`).
  - Cache resolver (Local ISP / `8.8.8.8`) berdasar TTL (Time-to-Live).
- **TLS 1.3 Cryptography**:
  - Asymmetric encryption untuk pertukaran key (ECDHE), symmetric encryption untuk transmisi data (AES-GCM).

---

## 6. How?
Alur lengkap ketika browser atau client mengirim request ke `https://api.myapp.com`:

```text
[ Client (Browser / cURL) ]
             │
             │ 1. DNS Resolution: "Berapa IP api.myapp.com?"
             ▼
[ DNS Resolver Cache -> Authoritative Nameserver ]
             │
             │ Kembalikan Record A: 203.0.113.50 (TTL: 300s)
             ▼
[ Client Melakukan TCP 3-Way Handshake ke 203.0.113.50:443 ]
   Client  ─── SYN ───────────>  Server
   Client  <── SYN-ACK ───────  Server
   Client  ─── ACK ───────────>  Server  (Koneksi TCP Terbuka!)
             │
             │ 2. TLS 1.3 Handshake (1 RTT)
             ▼
   Client  ─── ClientHello (Supported Ciphers + Key Share) ───> Server
   Client  <── ServerHello + Certificate + Finished ──────────  Server
   Client  ─── Finished ─────────────────────────────────────> Server
             │
             │ 3. Saluran Terenkripsi Aktif!
             ▼
[ HTTP/2 GET /v1/users (Payload Terenkripsi) Mengalir Aman ]
```

---

## 7. Analogy
Bayangkan alur jaringan seperti **Kirim Dokumen Rahasia via Kurir Berangkai**:
- **DNS**: Buku telepon kantor pusat untuk mencari alamat gedung target berdasarkan nama perusahaan.
- **IP Address**: Alamat jalan dan nomor gedung fisik kantor target.
- **Port (Layer 4)**: Nomor ruangan spesifik di gedung tersebut (misal: Ruang 443 untuk Departemen Rahasia).
- **TCP**: Telepon konfirmasi di awal: *"Halo, berkas mau dikirim? Ya siap. Oke saya berangkat!"* untuk memastikan kurir tidak sia-sia.
- **TLS/SSL**: Memasukkan dokumen ke dalam koper baja antipeluru bersegel digital yang hanya bisa dibuka dengan kunci khusus milik penerima.

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|                      OSI 7-LAYER STACK                      |
|                                                             |
|  [ Layer 7: Application ]  --> HTTP / HTTPS / DNS / gRPC    |
|  [ Layer 6: Presentation ] --> TLS Enkripsi / JSON Serialization
|  [ Layer 5: Session ]      --> RPC / Session state          |
|  [ Layer 4: Transport ]    --> TCP (Reliable) / UDP (Fast)  |
|  [ Layer 3: Network ]      --> IP Packets & Routers         |
|  [ Layer 2: Data Link ]    --> Switch & Ethernet Frames     |
|  [ Layer 1: Physical ]     --> Fiber Optik, Kabel Cat6, Radio
+-------------------------------------------------------------+
```

---

## 9. Simple Example
Perintah CLI diagnostik jaringan wajib bagi DevOps:

```bash
# 1. Menguji konektivitas resolusi DNS dan melihat rincian authority
dig +trace api.github.com

# 2. Menguji koneksi TCP port spesifik (apakah firewall terbuka?)
nc -zv 192.168.1.10 443

# 3. Memeriksa sertifikat SSL dan masa kedaluwarsanya via OpenSSL
openssl s_client -connect google.com:443 -servername google.com | openssl x509 -noout -dates

# 4. Melacak lompatan rute paket router (Hop-by-hop latency)
traceroute -T -p 443 api.stripe.com

# 5. Memeriksa status port listening lokal
ss -tulpn | grep :80
```

---

## 10. Practical Example
Simulasi inspeksi koneksi soket TCP dan status DNS di Node.js:

```javascript
const dns = require('dns').promises;
const net = require('net');

async function testNetworkEndpoint(domain, port) {
  console.log(`[DNS] Melakukan lookup record A untuk: ${domain}...`);
  const addresses = await dns.resolve4(domain);
  const targetIp = addresses[0];
  console.log(`[DNS OK] IP Terpilih: ${targetIp}`);

  return new Promise((resolve, reject) => {
    const start = Date.now();
    const socket = net.createConnection({ host: targetIp, port }, () => {
      const latency = Date.now() - start;
      console.log(`[TCP OK] Handshake ke ${targetIp}:${port} berhasil dalam ${latency}ms!`);
      socket.end();
      resolve({ success: true, latency });
    });

    socket.on('error', reject);
    socket.setTimeout(3000, () => {
      socket.destroy();
      reject(new Error('Connection Timeout (3000ms)'));
    });
  });
}
```

---

## 11. Real World Example
### Kasus: Outage Global Akibat Sertifikat TLS Kedaluwarsa & Caching DNS
1. Sertifikat wildcard `*.prod.company.com` kedaluwarsa pada jam 00:00 UTC.
2. Seluruh client mobile app menerima pesan `SSL Certificate Expired` dan transaksi terhenti total.
3. Tim infrastruktur segera merilis sertifikat baru dan memperbarui DNS record di Cloudflare.
4. Namun, puluhan ISP telekomunikasi lokal masih meng-cache DNS lama karena konfigurasi TTL sebelumnya dipasang 86.400 detik (24 jam)!
5. **Solusi SRE**: 
   - Turunkan TTL DNS menjadi 300 detik (5 menit) sebelum rencana pemeliharaan.
   - Otomatiskan rotasi sertifikat menggunakan `cert-manager` Let's Encrypt dengan alarm pembaruan pada H-30 hari sebelum kedaluwarsa.

---

## 12. Trade-offs
| Protokol Transmisi | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
|---|---|---|
| **Reliability** | Sangat tinggi (Retransmission jika paket hilang) | Rendah (*Best-effort*, paket bisa hilang tanpa pesan) |
| **Ordering** | Paket dijamin tiba berurutan | Paket bisa tiba acak (*out-of-order*) |
| **Latency / Overhead** | Ada overhead handshake & ACK tracking | Sangat rendah (zero connection handshake) |
| **Use Cases** | HTTP/1.1, HTTP/2, Database, SSH, File Transfer | DNS query, VoIP, Live Video Streaming, HTTP/3 (QUIC) |

---

## 13. When To Use
- Gunakan **TCP / TLS**: Untuk semua transaksi data penting yang tidak boleh kehilangan 1 byte pun (REST API, pembayaran, database sync).
- Gunakan **UDP**: Untuk streaming telemetri dengan volume jutaan event/detik (seperti metrik StatsD) atau transmisi suara/video real-time di mana kecepatan lebih penting dibanding kelengkapan.

---

## 14. When NOT To Use
- Jangan menggunakan protokol unencrypted (HTTP port 80 / FTP port 21) di jaringan publik tanpa terowongan VPN/TLS.

---

## 15. Common Mistakes
1. **Mengabaikan TTL DNS**: Memasang TTL DNS 7 hari saat domain baru diluncurkan. Ketika server harus dipindah IP darurat karena DDoS, migrasi tertahan selama 7 hari di resolver ISP pengguna.
2. **Tidak Mengaktifkan HTTP/2 atau HTTP/3**: Masih mengandalkan HTTP/1.1 di production yang membatasi konkruensi koneksi browser (*head-of-line blocking*).
3. **Lupa SNI (Server Name Indication)**: Mengonfigurasi beberapa domain SSL di satu IP address proxy yang sama tanpa SNI, menyebabkan client menerima sertifikat domain yang salah.

---

## 16. Best Practices
### Must Have
- Wajibkan TLS 1.2 minimum, prioritaskan TLS 1.3. Nonaktifkan cipher usang (seperti SSLv3, RC4, DES, 3DES).
- Atur default TTL DNS ke 300 detik (5 menit) untuk endpoint API yang dinamis.
- Pasang monitoring peringatan sertifikat kedaluwarsa minimal 30 hari sebelumnya.

### Recommended
- Gunakan HTTP/3 (QUIC berbasis UDP) pada CDN / Edge untuk memangkas latency mobile client yang sering berganti jaringan.
- Implementasikan HSTS (*HTTP Strict Transport Security*) untuk memaksa browser selalu menggunakan HTTPS.

### Avoid / Overengineering
- Jangan memasang TTL 1 detik pada DNS karena akan membebani authoritative nameserver Anda dengan jutaan query berulang.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| cURL mengembalikan `Could not resolve host` | DNS resolver gagal atau domain belum terdaftar di nameserver | Uji dengan resolver publik: `dig @8.8.8.8 mydomain.com` |
| cURL mengembalikan `Connection refused` | Tidak ada aplikasi yang mendengarkan di port target | Periksa dengan `ss -tulpn` apakah service sedang berjalan di port tersebut |
| cURL mengembalikan `Connection timed out` | Paket di-drop oleh Firewall (UFW / AWS Security Group / iptables) | Periksa aturan ingress security group dan network ACL |

---

## 18. Exercise
1. Gunakan perintah `dig` untuk memeriksa daftar nameserver (`NS`) dan mail server (`MX`) dari sebuah domain publik.
2. Lakukan koneksi socket mentah ke web server publik menggunakan `nc` (netcat), lalu kirimkan payload HTTP manual `GET / HTTP/1.1\r\nHost: example.com\r\n\r\n`.

---

## 19. Challenge
Rancang arsitektur simulasi **DNS Resolver & TCP Handshake Engine**:
- Simulasikan tabel cache DNS lokal dengan expiry timestamp (TTL).
- Jika domain ada di cache dan belum expired, gunakan IP cache; jika expired, lakukan query simulasi ke upstream authoritative nameserver.
- Simulasikan 3-way handshake (`SYN`, `SYN-ACK`, `ACK`) dengan pengukuran Round-Trip Time (RTT).

---

## 20. Summary
- Pemahaman layer OSI dan TCP/IP adalah peta navigasi utama dalam memecahkan masalah konektivitas infrastruktur.
- DNS menerjemahkan domain ke IP dengan sistem caching bertingkat berbasis TTL.
- TLS 1.3 mengamankan transmisi data dengan pertukaran kunci kriptografis yang efisien dan aman.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/network_socket_dns_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/hands-on/m01/network_socket_dns_sim.js).
