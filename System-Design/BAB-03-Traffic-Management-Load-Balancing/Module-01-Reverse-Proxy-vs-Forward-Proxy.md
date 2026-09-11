# MODULE 01: Reverse Proxy vs Forward Proxy

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara arsitektural, fungsi, dan topologi antara **Forward Proxy** dan **Reverse Proxy**.
2. Menjelaskan peran vital Reverse Proxy dalam: **SSL/TLS Termination**, **Gzip/Brotli Compression**, **Security Shielding / IP Masking**, dan **Header Transformation**.
3. Menganalisis risiko keamanan terkait header forwarding: `X-Forwarded-For`, `X-Forwarded-Proto`, dan `X-Real-IP`.
4. Mengonfigurasi dan menjalankan simulasi Reverse Proxy vs Forward Proxy secara langsung menggunakan Node.js script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 02: Edge Computing, DNS, & Jaringan Distribusi](../BAB-02-Edge-DNS-CDN/).
- Memahami konsep dasar protokol HTTP, port, dan socket koneksi TCP.

---

## 3. Concept
Dalam rekayasa jaringan komputer, sebuah **Proxy** adalah perantara (*intermediary*) yang duduk di antara pengirim (*client*) dan penerima (*server*) yang mencegat, memvalidasi, memodifikasi, dan meneruskan paket request/response.

Perbedaan arah perlindungan dan pihak yang diwakili membagi proxy menjadi dua kategori fundamental:
- **Forward Proxy:** Bertindak atas nama dan melindungi **KLIEN** (*Client-side proxy*).
- **Reverse Proxy:** Bertindak atas nama dan melindungi **SERVER** (*Server-side proxy*).

---

## 4. Why? (Mengapa Arsitektur Server Membutuhkan Reverse Proxy?)

### Bahaya Membuka Server Aplikasi Langsung ke Internet
Jika Anda mengekspos server backend (misal aplikasi Node.js Express, Python Django, atau Go) langsung ke internet publik pada port 80/443:
1. **Beban Komputasi TLS/SSL Handshake:** Setiap koneksi baru HTTPS membutuhkan negosiasi kriptografi asimetris yang berat. Node.js atau Python single-thread akan tersedot 30-50% CPU-nya hanya untuk mendekripsi traffic TLS!
2. **Serangan Slowloris & Slow HTTP Attacks:** Hacker sengaja mengirimkan header request sangat lambat (1 byte tiap 10 detik). Server aplikasi kehabisan worker thread/connection pool dan mati seketika.
3. **Penyusupan Struktur Internal:** Client dapat mengetahui bahasa pemrograman, port internal, dan alamat IP asli server Anda.

Dengan **Reverse Proxy** (seperti Nginx, Caddy, Envoy, HAProxy) di depan aplikasi:
- TLS dihentikan di reverse proxy (*SSL Termination*).
- Request lambat diserap oleh event-loop C/Rust milik Nginx (*Buffering*).
- Server backend hanya menerima HTTP plain text yang bersih dan cepat di jaringan lokal (*Private Subnet*).

---

## 5. What? (Forward Proxy vs Reverse Proxy)

```text
               FORWARD PROXY vs REVERSE PROXY
               
  [ FORWARD PROXY: Melindungi & Mengontrol Client ]
  
  [ Klien A ] ──┐
  [ Klien B ] ──┼──▶ [ Forward Proxy ] ───────▶ ( Internet Publik ) ──▶ [ Server Web ]
  [ Klien C ] ──┘     (Kantor/Sekolah)
  
  * Server Web TIDAK TAHU IP asli Klien A/B/C.
  * Server Web hanya melihat IP milik Forward Proxy.
  
  -----------------------------------------------------------------------------------
  
  [ REVERSE PROXY: Melindungi & Mengatur Server ]
  
  ( Internet Publik ) ──▶ [ Reverse Proxy ] ──┬──▶ [ Server API 1 (10.0.1.2:3000) ]
     (Banyak Klien)        (Nginx / Caddy)     ├──▶ [ Server API 2 (10.0.1.3:3000) ]
                                               └──▶ [ Server DB  (10.0.1.4:5432) ]
                                               
  * Klien TIDAK TAHU IP asli Server API 1/2.
  * Klien hanya tahu IP publik Reverse Proxy.
```

### Tabel Perbandingan Arsitektural:

| Parameter | Forward Proxy | Reverse Proxy |
|---|---|---|
| **Pihak yang Diwakili** | Klien (*Users*) | Server (*Backends*) |
| **Lokasi Topologi** | Di depan perangkat klien / jaringan kantor | Di depan cluster server / data center |
| **Tujuan Utama** | Anonimitas klien, bypass sensor, filtering konten | Load balancing, SSL termination, caching, keamanan |
| **Visibilitas Client** | Klien tahu dan sengaja mengonfigurasi proxy | Klien sama sekali tidak tahu (transparan) |
| **Contoh Software** | Squid, Shadowsocks, Charles Proxy, Fiddler | Nginx, HAProxy, Envoy, Traefik, Caddy |

---

## 6. How? (Fitur-Fitur Vital Reverse Proxy)

### 1. SSL / TLS Termination
Reverse Proxy mendekripsi enkripsi HTTPS dari client, lalu meneruskan request sebagai HTTP plain text yang ringan ke backend server di private VPC network.

```text
[ Browser ] ─── HTTPS (Port 443 / Terenkripsi) ───▶ [ Reverse Proxy (Nginx) ]
                                                              │ (Dekripsi)
                                                              ▼
[ Server Backend ] ◄─── HTTP (Port 3000 / Plain Text Cepat) ──┘
```

### 2. Header Transformation & Keamanan
Karena reverse proxy menjadi perantara, server backend akan melihat alamat IP client sebagai IP reverse proxy (`127.0.0.1` atau `10.0.0.1`). Untuk mempertahankan identitas asli pengguna, Reverse Proxy menyematkan header standar:
- `X-Forwarded-For: <IP-Asli-Pengguna>, <Proxy-1>, <Proxy-2>`
- `X-Forwarded-Proto: https` (memberitahu backend bahwa koneksi asli pengguna aman menggunakan HTTPS).
- `X-Real-IP: <IP-Asli-Pengguna>`

---

## 7. Analogy
- **Forward Proxy (Kuasa Hukum Klien):** Anda menyewa seorang pengacara untuk membelikan rumah bagi Anda. Penjual rumah hanya berurusan dan bertatap muka dengan pengacara Anda, tanpa pernah mengetahui identitas asli Anda sebagai pembeli.
- **Reverse Proxy (Resepsionis Gedung Kedutaan):** Anda datang ke kantor Kedutaan Besar. Anda tidak bisa langsung masuk ke ruang kerja Duta Besar di lantai 10. Anda wajib melewati meja resepsionis di lobi. Resepsionis memeriksa tanda pengenal Anda, menyaring orang mencurigakan, dan mengantarkan berkas Anda ke staf yang bertugas di dalam.

---

## 8. Diagram: Alur Request Lengkap Melalui Reverse Proxy

```text
[ HTTP Request: GET /api/users ]
        │
        ▼
[ Reverse Proxy: Nginx ]
        │
        ├── 1. Periksa Rate Limit IP (Apakah melebihi 100 req/mnt?) ──▶ Tolak 429
        │
        ├── 2. TLS Decryption (Sertifikat Let's Encrypt / SSL)
        │
        ├── 3. Apakah path "/static/*"? ──▶ YA ──▶ Sajikan dari Disk Lokal Nginx
        │
        ├── 4. Suntikkan Header:
        │      X-Forwarded-For: 202.152.1.5
        │      X-Request-ID: req_uuid_99812
        │
        └── 5. Teruskan ke Backend Node.js / Go melalui Socket Unix / HTTP Private
```

---

## 9. Simple Example: Konfigurasi Dasar Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name api.perusahaan.com;

    location / {
        proxy_pass http://127.0.0.1:3000; # Forward ke aplikasi Node.js lokal
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 10. Practical Code Example
Lihat demonstrasi perbedaan alur data Forward Proxy vs Reverse Proxy pada:
`System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m01/proxy_comparison.js`

---

## 11. Real World Example: Cloudflare sebagai Global Reverse Proxy
Setiap website yang menggunakan Cloudflare pada dasarnya menempatkan Cloudflare sebagai **Reverse Proxy Raksasa** di depan server aslinya:
- Pengunjung web mengetik `shopee.co.id`.
- DNS mengembalikan IP Cloudflare Reverse Proxy.
- Cloudflare menyaring bot jahat, serangan DDoS, melakukan kompresi Brotli, memvalidasi SSL, dan meng-cache aset statis.
- Hanya request dinamis yang bersih yang diteruskan ke server origin Shopee.

---

## 12. Trade-offs (Menambah Reverse Proxy vs Direct Access)

| Aspek | Direct Connection ke Backend | Melalui Reverse Proxy |
|---|---|---|
| **Latensi Ekstra** | 0 ms | Sangat kecil (0.5 ms - 2 ms per request) |
| **Keamanan Server** | Sangat rentan eksploitasi dan serangan DDoS | Sangat aman (IP backend tersembunyi total) |
| **Pemanfaatan CPU Backend** | Terbebani enkripsi SSL & serving file statis | Murni 100% untuk eksekusi logika bisnis |
| **Kompleksitas Infrastruktur** | Sangat sederhana | Menambah 1 layer konfigurasi yang wajib dirawat |

---

## 13. When To Use What
- **Wajib gunakan Reverse Proxy di SEMUA aplikasi produksi:** Tidak ada server produksi yang boleh mengekspos runtime aplikasi (Node.js/Python/PHP) langsung ke port publik internet.
- **Gunakan Forward Proxy jika:** Anda mengelola jaringan korporasi/kantor untuk memblokir akses malware/situs terlarang bagi karyawan, atau scraper web yang butuh merotasi IP client.

---

## 14. When NOT To Use
- Jangan gunakan Forward Proxy untuk melindungi server web Anda dari serangan luar (karena secara arsitektur itu adalah tugas Reverse Proxy).

---

## 15. Common Mistakes
1. **IP Spoofing via Header `X-Forwarded-For` yang Tidak Divalidasi:** Penyerang sengaja mengirim request dengan header palsu `X-Forwarded-For: 127.0.0.1`. Jika reverse proxy tidak me-rewrite header ini, backend mengira request berasal dari localhost dan memberikan hak akses admin (*Privilege Escalation*)!
2. **Lupa Menyetel `client_max_body_size` di Nginx:** Default batas upload Nginx adalah 1 MB. Akibatnya, pengguna gagal mengunggah foto profil dan mendapat error `413 Request Entity Too Large` tanpa mencapai backend Anda.
3. **Mengabaikan Keep-Alive Antara Proxy dan Backend:** Membuka dan menutup koneksi TCP baru untuk setiap request antara reverse proxy dan backend server membuang ribuan siklus CPU per detik.

---

## 16. Best Practices

- **Must Have:**
  - Lakukan **SSL Termination** di Reverse Proxy.
  - Sembunyikan server token/version header (misal di Nginx: `server_tokens off;` untuk menyembunyikan versi Nginx dari hacker).
- **Recommended:**
  - Aktifkan kompresi gzip / brotli di level reverse proxy untuk seluruh response `text/html`, `application/json`, dan `text/css`.
  - Pasang **Connection Pooling / Keep-Alive** antara proxy ke upstream backend.
- **Advanced:**
  - Gunakan **Envoy Proxy** jika Anda bekerja di lingkungan microservices/Kubernetes untuk mendapatkan observabilitas metrik gRPC dan distributed tracing secara native.
- **Avoid / Overengineering:**
  - Menumpuk 4 lapis reverse proxy berbeda (Nginx -> Traefik -> Kong -> Apache) di arsitektur yang sama tanpa alasan fungsional yang jelas.

---

## 17. Troubleshooting Guide
```text
Gejala: Backend aplikasi mencatat semua IP pengguna sebagai "127.0.0.1".
----------------------------------------------------------------------
Penyebab:
Reverse proxy meneruskan request tanpa menyertakan header X-Forwarded-For atau backend tidak dikonfigurasi untuk membaca header tersebut (misal di Express.js lupa menyetel app.set('trust proxy', true)).

Solusi:
1. Di Nginx tambahkan:
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
2. Di aplikasi backend:
   Express.js: app.set('trust proxy', 1);
```

---

## 18. Hands-on Lab: Simulator Forward Proxy vs Reverse Proxy

File lab sudah disiapkan di:
`System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m01/proxy_comparison.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m01/proxy_comparison.js
```

### Yang Ditampilkan Script Ini:
1. Menjalankan backend server tersembunyi pada port private internal.
2. Menjalankan Reverse Proxy yang melakukan SSL simulation, IP masking, dan penyuntikan header `X-Forwarded-For`.
3. Menjalankan Forward Proxy yang menganonimkan request dari browser client.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 3 perbedaan mendasar antara Forward Proxy dan Reverse Proxy!

### Level 2 (Medium):
Jelaskan konsep **SSL/TLS Termination** pada Reverse Proxy dan sebutkan 2 keuntungan utamanya bagi server backend aplikasi!

### Level 3 (Hard):
Sebuah celah keamanan terjadi pada aplikasi Express.js: Penyerang mengirim HTTP request langsung dengan header `X-Forwarded-For: 192.168.1.1` (IP admin internal). Aplikasi mengizinkan akses ke panel `/admin`. Jelaskan bagaimana penyerang bisa melakukan eksploitasi ini, dan bagaimana konfigurasi reverse proxy yang benar untuk memitigasinya!

---

## 20. Summary & Knowledge Check
- [ ] Memahami perbedaan arah perlindungan Forward Proxy (client) vs Reverse Proxy (server).
- [ ] Menguasai peran vital Reverse Proxy: SSL Termination, Compression, Security Masking.
- [ ] Memahami fungsi header `X-Forwarded-For`, `X-Real-IP`, dan `X-Forwarded-Proto`.
- [ ] Menghindari kesalahan fatal IP Spoofing dan kebocoran versi software server.
