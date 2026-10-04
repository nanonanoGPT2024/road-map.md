# BAB 01: Quiz, Challenge, & Knowledge Check
## Fondasi Arsitektur Global Edge Network, Anycast Routing, & Reverse Proxy Pipeline

Dokumen ini berisi instrumen evaluasi komprehensif untuk menguji pemahaman teoritis, analitis, dan kemampuan arsitektur praktis pada **Bab 01: Fondasi dan Arsitektur Cloudflare**.

---

## 1. Basic Questions (5 Soal Pilihan Ganda)

### Soal 1
Bagaimana mekanisme perutean **BGP Anycast** (`AS13335`) pada jaringan Cloudflare mengarahkan traffic paket dari klien ke Edge Datacenter terdekat dibandingkan dengan model **Unicast** tradisional?
- A. Anycast menggunakan server DNS terpusat di San Francisco untuk menghitung koordinat GPS klien dan mengembalikan alamat IP Unicast unik untuk setiap klien.
- B. Anycast mengumumkan blok prefix IP publik yang sama dari ratusan Point of Presence (PoP) di seluruh dunia secara simultan; ISP klien kemudian memilih rute dengan metrik *AS-Path* BGP terpendek menuju PoP terdekat.
- C. Anycast memetakan satu nama domain ke jutaan IP privat melalui tunnel VPN internal yang diinisiasi dari browser pengguna.
- D. Anycast menyalin seluruh database aplikasi origin ke setiap server perbatasan secara instan sebelum koneksi TCP terbentuk.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Pada arsitektur BGP Anycast, prefix IP yang sama (misal `104.16.0.0/12` atau `172.64.0.0/13`) diiklankan (*advertised*) oleh router perbatasan Cloudflare di seluruh PoP global ke Internet Exchange Points (IXP) dan transit provider (Tier 1 ISP). Protokol BGP pada router ISP lokal pengguna akan menentukan jalur routing terpendek (*shortest AS-Path / lowest IGP metric*) sehingga paket secara otomatis mendarat di PoP yang paling efisien secara topologi jaringan.

---

### Soal 2
Apa perbedaan struktural paling fundamental dalam pemrosesan paket jaringan saat DNS record diubah dari status **DNS-Only (Grey-Clouded)** menjadi **Proxied (Orange-Clouded)** di Cloudflare?
- A. Pada status DNS-Only, Cloudflare mengenkripsi database origin; pada Proxied, Cloudflare menghapus SSL certificate.
- B. Pada status DNS-Only, query DNS mengembalikan IP publik Cloudflare Anycast; pada Proxied, query mengembalikan IP fisik origin.
- C. Pada status DNS-Only, traffic klien mengalir langsung secara Layer 4 (TCP/UDP) ke IP origin tanpa intervensi Cloudflare; pada Proxied, Cloudflare bertindak sebagai Layer 7 Reverse Proxy (terminasi TCP/TLS di Edge dan inisiasi sesi baru ke origin).
- D. Status Proxied hanya memengaruhi record berjenis TXT dan MX, sedangkan DNS-Only khusus untuk A record.

**Kunci Jawaban:** **C**  
*Penjelasan Teknis:* Saat berstatus DNS-Only (Grey Cloud), Cloudflare hanya bertindak sebagai Authoritative DNS server murni yang mengembalikan IP asli origin ke resolver klien. Traffic HTTP/HTTPS mengalir langsung antara klien dan origin tanpa melewati proxy. Saat diubah menjadi Proxied (Orange Cloud), query DNS diselesaikan ke IP Anycast Cloudflare, dan seluruh traffic TCP/TLS diintersepsi di Edge (Layer 7 reverse proxy), memungkinkan inspeksi WAF, mitigasi DDoS, caching, dan manipulasi header.

---

### Soal 3
Ketika sebuah web server NGINX berada di belakang reverse proxy Cloudflare (Proxied), variabel bawaan `$remote_addr` pada NGINX akan membaca alamat IP milik siapa, dan header HTTP standar apa yang diinjeksi Cloudflare untuk merepresentasikan alamat IP publik klien sebenarnya?
- A. Membaca IP lokal loopback `127.0.0.1`; header yang diinjeksi adalah `X-Real-IP`.
- B. Membaca IP publik klien; header yang diinjeksi adalah `X-Origin-IP`.
- C. Membaca IP Anycast Egress node Cloudflare; header resmi yang diinjeksi adalah `CF-Connecting-IP` (serta `True-Client-IP` pada paket Enterprise).
- D. Membaca MAC address router gateway ISP; header yang diinjeksi adalah `Client-Public-Address`.

**Kunci Jawaban:** **C**  
*Penjelasan Teknis:* Karena Cloudflare beroperasi sebagai reverse proxy dual-legged, koneksi TCP yang diterima oleh origin server dibuat oleh server Edge Cloudflare, bukan langsung oleh klien. Akibatnya, socket Layer 4 NGINX mencatat IP pengirim (`$remote_addr`) sebagai salah satu IP dari subnet egress Cloudflare. Untuk meneruskan identitas layer 7 klien asli, Cloudflare menyisipkan header HTTP request `CF-Connecting-IP` (dan `True-Client-IP` pada zona Enterprise jika diaktifkan).

---

### Soal 4
Arsitektur proxy modern Cloudflare menggunakan engine bernama **Pingora** yang menggantikan NGINX. Keunggulan teknis utama dari Pingora dalam menangani koneksi *Edge-to-Origin* pada skala triliunan request per hari adalah:
- A. Pingora ditulis dalam C++ dan menggunakan multithreading berbasis POSIX thread blocking.
- B. Pingora ditulis dalam Rust dengan arsitektur asynchronous berbasis *work-stealing thread pool*, memungkinkan penggunaan memori minimal, *connection pooling* HTTP/1.1, HTTP/2, dan HTTP/3 yang jauh lebih efisien, serta eliminasi crash akibat memory-safety bugs.
- C. Pingora sepenuhnya menonaktifkan TLS handshake untuk menghemat latensi komputasi CPU.
- D. Pingora menggantikan protokol TCP dengan UDP murni di seluruh koneksi internal ke origin server.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Cloudflare mendesain Pingora menggunakan bahasa Rust untuk mengatasi limitasi proses-multiplexing NGINX. Pingora beroperasi dengan model multi-threaded asynchronous runtime. Arsitektur ini memungkinkan pooling koneksi HTTP keep-alive lintas thread/proses secara global di setiap mesin edge, meningkatkan connection reuse ratio dari edge ke origin secara dramatis dan menurunkan latensi time-to-first-byte (TTFB) sembari menjamin *memory safety* tanpa overhead garbage collection.

---

### Soal 5
Pada layer mitigasi serangan DDoS volumetrik, komponen arsitektur apa yang digunakan Cloudflare untuk memeriksa dan membuang (*drop*) paket serangan berbahaya (seperti SYN Flood atau UDP Amplification) langsung di level driver kartu jaringan (NIC) sebelum paket dialokasikan ke memori kernel Linux (`sk_buff`)?
- A. Linux `iptables` dengan target `REJECT`.
- B. Apache mod_security.
- C. **XDP (eXtended Data Path)** yang didukung oleh **eBPF (extended Berkeley Packet Filter)** dan subsistem **Unimog/Gatebot**.
- D. DNS Response Policy Zones (RPZ).

**Kunci Jawaban:** **C**  
*Penjelasan Teknis:* Cloudflare mengimplementasikan proteksi DoS L4 (Gatebot / l4drop) menggunakan program eBPF yang dieksekusi langsung pada hook XDP di level driver network interface card (NIC). Hal ini memungkinkan inspeksi dan pembuangan paket berbahaya (*packet dropping*) dalam hitungan nanodetik pada kecepatan line-rate tanpa alokasi memori struktur data kernel `sk_buff`, mencegah CPU origin atau edge mengalami *kernel starvation*.

---

## 2. Intermediate Questions (5 Soal Pilihan Ganda)

### Soal 1
Perhatikan nilai header HTTP respons berikut yang dikembalikan oleh server produksi:
```http
CF-Ray: 8d4b3a1c8f9210e4-CGK
```
Informasi diagnostik apakah yang dapat diekstrak oleh tim SRE secara langsung dari nilai header tersebut?
- A. ID transaksi database origin dengan checksum enkripsi AES-256 yang dieksekusi di Jakarta.
- B. Request tracing identifier unik 64-bit hexadecimal (`8d4b3a1c8f9210e4`) yang diproses di PoP Cloudflare Bandara Internasional Soekarno-Hatta Jakarta (`CGK`), yang dapat dicocokkan dengan log internal Cloudflare (Logpush/Audit) dan origin access logs.
- C. Nomor port TCP yang digunakan oleh klien untuk mengakses server di Cengkareng.
- D. Waktu kedaluwarsa token session autentikasi pengguna dalam milidetik.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Header `CF-Ray` adalah identifier tracing global terdistribusi unik yang dihasilkan oleh Cloudflare untuk setiap request HTTP yang melintasi edgenya. String terdiri dari Ray ID unik dalam format heksadesimal diikuti tanda hubung dan 3 huruf kode bandara IATA yang mengidentifikasi lokasi fisik PoP Cloudflare yang memproses request tersebut (dalam contoh ini, `CGK` = Soekarno-Hatta Airport, Jakarta, Indonesia). Ray ID ini sangat krusial untuk investigasi insiden dan korelasi log antara edge dan backend.

---

### Soal 2
Dalam arsitektur Anycast BGP, router ISP di internet dapat mengalami fenomena **BGP Route Flapping** atau perubahan metric jalur antar-AS. Jika koneksi TCP klien yang berumur panjang (misalnya download file besar atau streaming WebSocket) tiba-tiba diarahkan ke PoP Cloudflare yang berbeda di tengah transfer, bagaimana Cloudflare mencegah putusnya koneksi TCP tersebut?
- A. Cloudflare memaksa klien me-refresh browser secara otomatis menggunakan kode JavaScript tersembunyi.
- B. Cloudflare menggunakan Layer 4 Load Balancer terdistribusi (**Unimog**) dengan mekanisme *consistent hashing* dan enkapsulasi GRE/Geneve inter-PoP untuk meneruskan paket ke server asal yang memegang state TCP socket tersebut.
- C. BGP Anycast secara absolut menjamin tidak akan pernah terjadi perubahan rute selama koneksi internet aktif.
- D. Klien secara otomatis membuat tunneling VPN ganda ke origin server saat terjadi perubahan rute.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Tantangan terbesar BGP Anycast adalah TCP statefulness: jika rute BGP bergeser di tengah transmisi (*route flap*), paket TCP berikutnya dari koneksi yang sama bisa terkirim ke PoP yang berbeda, yang biasanya menyebabkan `TCP RST` karena PoP baru tidak memiliki socket state tersebut. Cloudflare mengatasi ini dengan subsistem Unimog. Jika sebuah node menerima paket untuk TCP session yang tidak dikenali, paket diinspeksi flow hash-nya dan diteruskan (*tunneled/forwarded*) melalui backbone privat Cloudflare ke PoP/node awal yang menginisiasi koneksi tersebut.

---

### Soal 3
Sebuah aplikasi web memublikasikan record DNS berikut:
- `app.corp.com` $\rightarrow$ `A` $\rightarrow$ `103.21.244.15` (Status: **Proxied / Orange-Cloud**)
- `mail.corp.com` $\rightarrow$ `A` $\rightarrow$ `103.21.244.15` (Status: **DNS-Only / Grey-Cloud**)

Vulnerabilitas arsitektur apakah yang terjadi pada skenario tersebut, dan apa dampak keamanannya?
- A. `app.corp.com` tidak dapat diakses melalui browser mobile karena adanya konflik protokol SMTP.
- B. **Origin IP Leakage**: Penyerang dapat melakukan query DNS terhadap `mail.corp.com` untuk mengungkap IP fisik origin server (`103.21.244.15`), lalu melancarkan serangan DDoS L7, SQLi, atau eksploitasi zero-day langsung ke IP origin tanpa melewati proteksi WAF Cloudflare sama sekali.
- C. Cloudflare akan menolak memproksi `app.corp.com` karena mendeteksi duplikasi IP record.
- D. Record `mail.corp.com` otomatis terenkripsi oleh Universal SSL Cloudflare.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Ini adalah salah satu kesalahan arsitektur paling umum. Menyimpan record DNS-Only (seperti subdomain mail, FTP, VPN, atau direct) yang merujuk ke IP fisik yang sama dengan aplikasi yang diproksikan akan membocorkan IP origin ke publik. Penyerang cukup menjalankan `dig mail.corp.com` untuk mengetahui IP asli server, lalu mengonfigurasi header `Host: app.corp.com` saat mengirim request langsung ke IP tersebut, melewati Cloudflare WAF, Rate Limiting, dan DDoS shield secara menyeluruh (*direct-to-origin bypass*).

---

### Soal 4
Perhatikan potongan blok konfigurasi NGINX di origin server berikut:
```nginx
set_real_ip_from 0.0.0.0/0;
real_ip_header X-Forwarded-For;
```
Mengapa konfigurasi di atas digolongkan sebagai **Critical Security Misconfiguration** pada origin server yang berada di belakang Cloudflare?
- A. NGINX akan mengalami crash karena kehabisan alokasi buffer string header.
- B. Menyetel `set_real_ip_from 0.0.0.0/0` membuat NGINX mempercayai header `X-Forwarded-For` dari entitas jaringan mana pun; penyerang dapat memalsukan IP mereka (*IP Spoofing*) dengan menyisipkan header `X-Forwarded-For: 1.1.1.1` sembarang untuk mem-bypass autentikasi berbasis IP atau audit log.
- C. Cloudflare akan memblokir request ke origin karena header `X-Forwarded-For` dilarang oleh RFC 7230.
- D. Konfigurasi tersebut menonaktifkan protokol TLS 1.3 di NGINX origin.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Direktif `set_real_ip_from` mendefinisikan *trusted proxies*. Jika diset ke `0.0.0.0/0` (seluruh internet), NGINX akan mempercayai header `X-Forwarded-For` dari klien mana pun. Jika penyerang mengirimkan request langsung ke origin (atau memanipulasi header sebelum masuk ke proxy yang tidak membersihkan header), mereka dapat memalsukan IP asal sesuka hati. Origin **hanya boleh mempercayai IP resmi Cloudflare** (daftar IPv4 dan IPv6 resmi Cloudflare) dan sebaiknya menggunakan header `CF-Connecting-IP`.

---

### Soal 5
Saat mengintegrasikan Cloudflare dengan origin server di dalam private cloud melalui interface GRE tunnel atau direct VPC peering, pengguna melaporkan beberapa request HTTP POST berukuran payload sedang/besar (seperti file upload >1500 bytes) mengalami **TCP Connection Hang / Timeout**, sedangkan request GET teks kecil berjalan normal. Akar masalah jaringan yang paling mungkin adalah:
- A. Cache TTL Cloudflare diset terlalu rendah.
- B. **Path MTU Discovery (PMTUD) Black Hole / MSS Mismatch**: Overhead enkapsulasi header paket menyebabkan ukuran frame melebihi Maximum Transmission Unit (MTU) link tanpa diizinkannya fragmentasi (flag Don't Fragment / DF aktif), dan pesan ICMP Type 3 Code 4 (Fragmentation Needed) terblokir oleh firewall origin.
- C. Pingora tidak mendukung HTTP POST request.
- D. Sertifikat Universal SSL tidak memiliki cipher suite yang mendukung upload biner.

**Kunci Jawaban:** **B**  
*Penjelasan Teknis:* Masalah ini adalah manifestasi klasik dari *PMTUD Black Hole*. Paket kecil (GET) memiliki ukuran jauh di bawah standar MTU (1500 bytes), sehingga lolos. Paket besar (upload, POST payload) mencapai batas MTU link. Karena tunnel/enkapsulasi menambahkan overhead header 20-50 bytes, ukuran paket efektif melebihi MTU jalur transit. Jika firewall memblokir paket ICMP `Fragmentation Needed` (Type 3, Code 4), router pengirim tidak pernah tahu bahwa paket di-drop, menyebabkan TCP retransmission terus menerus hingga koneksi hang/timeout. Solusinya adalah mengizinkan ICMP PMTUD dan mengonfigurasi `TCP MSS Clamping` di router/origin.

---

## 3. Skenario Kasus Produksi (3 Real-World Scenarios)

### Skenario 1: Insiden Bypass DDoS Layer 7 & Kebocoran IP Fisik Origin

#### Konteks & Gejala
Sebuah perusahaan agregator pembayaran digital (*Fintech*) menggunakan paket Cloudflare Enterprise untuk melindungi domain utama mereka `api.paygateway-corp.net`. Di dashboard Cloudflare, fitur WAF Managed Rulesets, Bot Management, dan Rate Limiting telah aktif.

Pada hari Senin pukul 10:15 WIB, CPU load pada cluster origin server (Kubernetes Ingress VM) melonjak dari 15% menjadi 100%, load average mencapai 140, dan API gateway mengembalikan respons `504 Gateway Timeout` ke seluruh merchant. 

Anehnya:
1. Grafik traffic di dashboard Cloudflare Analytics menunjukkan status normal (stabil di ~3.500 req/sec, 0 blocked requests).
2. Di origin server, log NGINX mencatat lonjakan traffic masif sebesar 95.000 req/sec berupa request acak `POST /v1/checkout/validate`.
3. Seluruh request di log NGINX memiliki `$remote_addr` dari ribuan IP publik residential di seluruh dunia, bukan IP proxy Cloudflare.

#### Pertanyaan Investigasi & Remediasi:
1. **Analisis Akar Masalah:** Bagaimana mungkin traffic serangan mencapai 95.000 req/sec di origin server tanpa tercatat di dashboard Cloudflare? Bagaimana penyerang kemungkinan besar mendapatkan alamat IP publik origin server?
2. **Mitigasi Darurat (<10 Menit):** Langkah jaringan apa yang harus segera dieksekusi tim DevOps/SRE pada layer firewall provider hosting (Security Groups) untuk menghentikan serangan seketika?
3. **Arsitektur Permanen:** Rancang topologi ingress origin modern yang menjamin origin server secara fisik tidak dapat diakses langsung oleh publik di masa mendatang (*Zero Direct Exposure*).

---

#### Panduan Jawaban & Solusi Arsitektural Skenario 1:

**1. Analisis Akar Masalah:**
- Serangan ini merupakan **Direct-to-Origin Attack**. Penyerang tidak mengirim traffic melalui domain `api.paygateway-corp.net` (yang diproteksi Cloudflare), melainkan mengirimkan paket HTTP langsung ke alamat IP publik origin server. Oleh karena itu, Cloudflare Edge tidak pernah melihat paket tersebut, sehingga statistik Cloudflare tetap normal.
- Kebocoran IP origin umumnya bersumber dari:
  - Riwayat DNS publik historis (misal dicatat oleh *SecurityTrails*, *Shodan*, *Censys*, atau *ViewDNS*) sebelum domain dipindahkan ke Cloudflare.
  - Subdomain lain di zona yang sama yang berstatus Grey-Cloud (seperti `origin.paygateway-corp.net`, `ftp.`, `ssh.`, `vpn.`, atau `smtp.`) yang menunjuk ke IP yang sama.
  - Pengiriman email otomatis dari server (misal registrasi user/notifikasi via `sendmail` lokal) di mana IP publik origin tercantum pada header email `Received: from ...`.
  - Endpoint webhook keluar dari origin server yang memanggil URL penyerang sehingga IP keluar (*egress IP*) origin terekam.

**2. Langkah Mitigasi Darurat (<10 Menit):**
- Segera lakukan penguncian pada Network Access Control List (NACL) atau Cloud Provider Security Group (AWS Security Group / GCP Firewall Rules / iptables):
  - **Tolak (DROP)** seluruh traffic inbound ke port 80 dan 443 dari `0.0.0.0/0`.
  - **Izinkan (ALLOW)** traffic inbound port 80 dan 443 **HANYA** dari subnet IP resmi Cloudflare.
- Daftar subnet Cloudflare resmi yang wajib di-whitelist:
  - IPv4: `https://www.cloudflare.com/ips-v4` (misal: `173.245.48.0/20`, `103.21.244.0/22`, `104.16.0.0/13`, dll).
  - IPv6: `https://www.cloudflare.com/ips-v6`.
- Begitu Security Group di-update, seluruh koneksi langsung penyerang ke IP origin akan di-drop seketika di perbatasan cloud provider.

**3. Arsitektur Permanen (Zero Public Exposure):**
Ganti ketergantungan pada IP publik origin dengan salah satu dari dua pendekatan:
1. **Cloudflare Tunnel (`cloudflared`):**
   - Hapus public IP address / public elastic IP dari origin balancer.
   - Jalankan daemon `cloudflared` di dalam cluster private. Daemon membuat koneksi outbound TCP/QUIC terenkripsi ke PoP Cloudflare terdekat. Origin tidak lagi memiliki port ingress publik terbuka sama sekali (`0 open inbound ports`).
2. **Dedicated Cloudflare Magic WAN / Direct Interconnect:**
   - Sambungkan VPC ke Cloudflare via GRE/IPsec tunnel privat dengan otentikasi BGP peering dan blokir rute internet publik.

---

### Skenario 2: Anomali Rate Limiter & Masalah "Semua User Terblokir Error 429"

#### Konteks & Gejala
Sebuah portal media berita nasional memigrasikan arsitektur DNS mereka ke Cloudflare (Proxied). Di server origin NGINX, tim engineer mengaktifkan modul rate limiting bawaan untuk melindungi endpoint login `/api/v1/auth/login` dari serangan brute force dengan konfigurasi berikut:

```nginx
# /etc/nginx/nginx.conf
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/s;

server {
    listen 443 ssl;
    server_name portalberita-indonesia.id;

    location /api/v1/auth/login {
        limit_req zone=login_limit burst=10 nodelay;
        proxy_pass http://backend_upstream;
    }
}
```

Tiga puluh menit pasca migrasi, ratusan ribu pengguna sah dari seluruh Indonesia melaporkan bahwa mereka tidak dapat login dan selalu menerima pesan error `HTTP 429 Too Many Requests`. Padahal, setiap pengguna individu hanya mengklik tombol login satu kali.

#### Pertanyaan Investigasi & Remediasi:
1. **Analisis Mekanisme Kegagalan:** Mengapa modul rate limiter NGINX memicu error 429 secara massal terhadap seluruh pengguna sah?
2. **Koreksi Konfigurasi Origin:** Tuliskan blok konfigurasi NGINX lengkap untuk memulihkan alamat IP asli klien (*Real IP restoration*) menggunakan modul `ngx_http_realip_module` dan pastikan rate limiter menggunakan IP asli klien tersebut.
3. **Potensi Kerentanan Baru:** Mengapa memetakan `limit_req_zone` berdasarkan `$http_cf_connecting_ip` tanpa menyetel direktif `set_real_ip_from` Cloudflare yang valid berisiko dieksploitasi penyerang?

---

#### Panduan Jawaban & Solusi Arsitektural Skenario 2:

**1. Analisis Mekanisme Kegagalan:**
Variabel `$binary_remote_addr` pada NGINX mengambil nilai dari socket address koneksi TCP fisik yang masuk (`$remote_addr`). Karena domain telah di-*proxied* oleh Cloudflare, seluruh ribuan request login dari berbagai pengguna diinternet dikirimkan melalui sejumlah kecil IP Anycast Egress Cloudflare (misal: PoP Jakarta menggunakan rentang IP Cloudflare tertentu). 

Akibatnya, NGINX melihat ribuan request tersebut berasal dari IP yang sama (IP milik Cloudflare). Kuota `rate=5r/s` habis dalam hitungan milidetik, sehingga seluruh request berikutnya dari pengguna lain langsung ditolak dengan status `429 Too Many Requests`.

**2. Koreksi Konfigurasi NGINX yang Benar:**

Pastikan modul `http_realip_module` terpasang, lalu konfigurasi file NGINX sebagai berikut:

```nginx
# /etc/nginx/conf.d/cloudflare_real_ip.conf

# 1. Daftarkan seluruh subnet resmi Cloudflare sebagai Trusted Proxies
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;

# Subnet IPv6 Cloudflare
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;

# 2. Instruksikan NGINX membaca header CF-Connecting-IP
real_ip_header CF-Connecting-IP;
real_ip_recursive on;

# 3. Definisikan rate limit zone menggunakan $binary_remote_addr 
# (yang kini nilainya telah digantikan secara transparan oleh IP asli klien)
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/s;

server {
    listen 443 ssl;
    server_name portalberita-indonesia.id;

    location /api/v1/auth/login {
        limit_req zone=login_limit burst=10 nodelay;
        proxy_pass http://backend_upstream;
        
        # Teruskan IP asli ke backend microservices
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**3. Potensi Kerentanan Jika Menggunakan `$http_cf_connecting_ip` Secara Langsung:**
Jika engineer menggunakan `limit_req_zone $http_cf_connecting_ip zone=...` tanpa memvalidasi sumber paket via `set_real_ip_from`, siapapun yang mengirim request langsung ke origin server dapat memanipulasi header tersebut. Penyerang dapat menyuntikkan header acak seperti `CF-Connecting-IP: 10.0.0.X` pada setiap request untuk mengelabui rate limiter secara sempurna.

---

### Skenario 3: Session Inconsistency & Asymmetric Routing pada Stateful Application

#### Konteks & Gejala
Sebuah institusi perbankan mengoperasikan aplikasi internal berbasis web monolitik yang menyimpan state autentikasi di memori RAM lokal masing-masing web node (*local PHP session store* di `/tmp/sess_*`), tanpa sistem penyimpanan session terpusat seperti Redis. 

Setelah domain diaktifkan fitur Cloudflare Proxied, banyak pengguna di kantor cabang (yang menggunakan koneksi internet multi-ISP load balancing: Indihome dan Biznet) mengeluhkan masalah:
1. Saat sedang mengisi formulir input data transaksi, pengguna tiba-tiba terlempar keluar ke halaman login (*random session invalidation / forced logout*).
2. Di log origin, terlihat bahwa satu sesi pengguna awalnya memiliki cookie session yang valid, namun beberapa detik kemudian request berikutnya tiba dengan ID sesi yang sama pada VM web server yang berbeda atau IP pengirim edge yang berubah drastis dari PoP Jakarta (`CGK`) ke PoP Singapura (`SIN`).

#### Pertanyaan Investigasi & Remediasi:
1. **Analisis Dinamika Routing:** Jelaskan bagaimana interaksi antara multi-ISP di sisi klien, routing BGP Anycast Cloudflare, dan dual-legged reverse proxy menyebabkan request pengguna mendarat di backend yang salah!
2. **Solusi Jangka Pendek di Layer Cloudflare:** Fitur apa di Cloudflare yang dapat dikonfigurasi untuk mempertahankan konsistensi rute request klien ke origin server yang sama (*session stickiness*)?
3. **Rekomendasi Arsitektur SRE Jangka Panjang:** Bagaimana seharusnya arsitektur modern dirancang untuk mengeliminasi ketergantungan pada *server affinity*?

---

#### Panduan Jawaban & Solusi Arsitektural Skenario 3:

**1. Analisis Dinamika Routing:**
- Di sisi klien: Kantor cabang menggunakan dual-WAN (Indihome & Biznet) dengan model load balancing per-koneksi. Request pertama dikirim via Indihome (yang memiliki peering terdekat ke Cloudflare PoP Jakarta/`CGK`), sedangkan request berikutnya dikirim via Biznet (yang memiliki rute BGP peering terpendek ke Cloudflare PoP Singapura/`SIN`).
- Di sisi Edge-to-Origin: Karena request masuk melalui dua PoP yang berbeda (CGK dan SIN), koneksi egress ke origin dibuat oleh dua cluster mesin Cloudflare yang berbeda.
- Jika origin load balancer internal (misal AWS ALB / HAProxy) mendistribusikan traffic berdasarkan hashing IP pengirim (`src_ip`), kedua request tersebut akan dilempar ke VM backend yang berbeda. Karena backend VM A tidak memiliki data session PHP yang disimpan di memori lokal backend VM B, backend VM A menganggap sesi tidak valid dan merespons dengan HTTP redirect ke `/login`.

**2. Solusi Jangka Pendek di Layer Cloudflare:**
- **Cloudflare Session Affinity (Sticky Sessions):**
  - Aktifkan fitur *Session Affinity* pada Cloudflare Load Balancing atau menggunakan Rule Set.
  - Cloudflare akan menyuntikkan cookie khusus (misal: `__cf_bm` atau cookie session affinity `__cfduid`/`cf-lb`) pada respons klien.
  - Setiap request berikutnya yang menyertakan cookie tersebut akan diprioritaskan untuk dirutekan ke origin pool dan backend origin node yang sama, terlepas dari PoP mana request tersebut masuk.
- **Header-Based Routing:**
  - Konfigurasikan Cloudflare Transform Rules untuk membaca cookie `PHPSESSID` dan menetapkan header routing internal khusus yang dipahami oleh reverse proxy origin untuk melakukan sticky balancing.

**3. Rekomendasi Arsitektur SRE Jangka Panjang:**
- **Stateless Application Layer:**
  - Pindahkan seluruh session state dari local filesystem/RAM VM ke distributed in-memory cache terpusat (**Redis Sentinel** atau **Redis Cluster / AWS ElastiCache**). Dengan cara ini, VM backend mana pun yang menerima request dapat membaca dan memvalidasi session token secara instan.
- **Stateless Cryptographic Token:**
  - Migrasikan mekanisme otentikasi dari server-side stateful session ke stateless **JSON Web Tokens (JWT)** yang ditandatangani secara kriptografis (menggunakan asymmetric key RS256/EdDSA). Data identitas pengguna disimpan di dalam payload token yang terverifikasi, mengeliminasi kebutuhan session lookup di backend.

---

## 4. Practical Chapter Challenge: Hardened Edge-to-Origin Perimeter

### Objektif
Sebagai Senior Infrastructure & Security Engineer, Anda ditugaskan untuk merancang dan mengotomasi perimeter keamanan dasar untuk domain `api-perimeter.cloud-enterprise.id`. Anda harus memastikan bahwa origin server tidak dapat diakses langsung oleh publik, seluruh traffic transit melalui Cloudflare Edge, dan logging origin mencatat jejak audit `CF-Ray` secara presisi.

### Deliverables yang Wajib Dibuat:
1. **File Terraform Declarative (`perimeter_edge.tf`)**:
   - Konfigurasi DNS record Proxied untuk apex dan subdomain `api`.
   - Konfigurasi Zone Settings: Minimum TLS 1.3, SSL/TLS Mode Strict, Always Use HTTPS On, HTTP/3 (QUIC) On, WebSockets On.
2. **File Konfigurasi NGINX Origin (`cloudflare_hardened.conf`)**:
   - Blokir akses langsung via IP fisik (hanya layani request yang memiliki header `Host: api-perimeter.cloud-enterprise.id`).
   - Implementasi modul Real-IP resmi Cloudflare.
   - Kustomisasi format log NGINX dalam format **JSON Structured Logging** yang menyertakan field `cf_ray`, `client_ip`, `request_time`, dan `upstream_response_time`.
3. **Skrip Bash Verifikasi Otomatis (`verify_edge_perimeter.sh`)**:
   - Menguji koneksi langsung ke IP fisik origin (harus ditolak/403/dropped).
   - Menguji koneksi via domain Cloudflare (harus 200 OK dengan header respons `CF-Ray` valid).

---

### Solusi Teknis Deliverable 1: Skrip Terraform (`perimeter_edge.tf`)

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
  }
}

variable "cloudflare_api_token" {
  type        = string
  sensitive   = true
  description = "Cloudflare API Token dengan izin Zone.DNS dan Zone.Settings"
}

variable "zone_id" {
  type        = string
  description = "Target Cloudflare Zone ID"
}

variable "origin_ipv4" {
  type        = string
  description = "Alamat IP publik VM Origin Server"
  default     = "203.0.113.195"
}

provider "cloudflare" {
  api_token = variable.cloudflare_api_token
}

# 1. DNS Records (Apex & Subdomain Proxied)
resource "cloudflare_record" "apex" {
  zone_id = variable.zone_id
  name    = "@"
  value   = variable.origin_ipv4
  type    = "A"
  proxied = true
  ttl     = 1 # Auto saat proxied
  comment = "Apex record di-proxy melalui Cloudflare Anycast"
}

resource "cloudflare_record" "api" {
  zone_id = variable.zone_id
  name    = "api-perimeter"
  value   = variable.origin_ipv4
  type    = "A"
  proxied = true
  ttl     = 1
  comment = "API endpoint terlindungi WAF dan Edge Pipeline"
}

# 2. Zone Settings Hardening
resource "cloudflare_zone_settings_override" "hardened_settings" {
  zone_id = variable.zone_id

  settings {
    ssl                      = "strict"
    min_tls_version          = "1.3"
    always_use_https         = "on"
    automatic_https_rewrites = "on"
    http3                    = "on"
    websockets               = "on"
    ip_geolocation           = "on"
    security_header {
      enabled            = true
      preload            = true
      max_age            = 31536000
      include_subdomains = true
      nosniff            = true
    }
  }
}
```

---

### Solusi Teknis Deliverable 2: NGINX Origin Hardening (`cloudflare_hardened.conf`)

```nginx
# /etc/nginx/conf.d/cloudflare_hardened.conf

# 1. Definisi Format Log Terstruktur JSON dengan Atribut Tracing Cloudflare
log_format cf_json_analytics escape=json '{'
    '"timestamp":"$time_iso8601",'
    '"cf_ray":"$http_cf_ray",'
    '"client_real_ip":"$remote_addr",'
    '"cf_connecting_ip":"$http_cf_connecting_ip",'
    '"cf_ip_country":"$http_cf_ipcountry",'
    '"request_method":"$request_method",'
    '"request_uri":"$request_uri",'
    '"status":$status,'
    '"bytes_sent":$bytes_sent,'
    '"request_length":$request_length,'
    '"request_time":$request_time,'
    '"upstream_response_time":"$upstream_response_time",'
    '"http_user_agent":"$http_user_agent"'
'}';

# 2. Whitelist Subnet Resmi Cloudflare untuk Restorasi IP
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;

real_ip_header CF-Connecting-IP;
real_ip_recursive on;

# 3. Default Catch-All Server: Blokir Seluruh Akses Direct-to-IP
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;

    server_name _;

    # Self-signed fallback cert khusus untuk drop connection
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    # Tolak koneksi langsung tanpa SNI atau via direct IP
    access_log /var/log/nginx/direct_ip_blocked.log cf_json_analytics;
    return 444; # NGINX non-standard code: Tutup koneksi tanpa mengembalikan response header
}

# 4. Valid Virtual Host Server Block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;

    server_name api-perimeter.cloud-enterprise.id;

    # Sertifikat Cloudflare Origin CA
    ssl_certificate /etc/ssl/certs/cloudflare_origin_ca.pem;
    ssl_certificate_key /etc/ssl/private/cloudflare_origin_ca.key;

    ssl_protocols TLSv1.3;
    ssl_prefer_server_ciphers on;

    access_log /var/log/nginx/api_access.log cf_json_analytics;
    error_log /var/log/nginx/api_error.log warn;

    # Pastikan header CF-Ray wajib ada (bukti request lewat Cloudflare)
    if ($http_cf_ray = "") {
        return 403 "Forbidden: Direct traffic is not allowed.";
    }

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header CF-Ray $http_cf_ray;

        proxy_pass http://127.0.0.1:8080;
    }
}
```

---

### Solusi Teknis Deliverable 3: Skrip Bash Verifikasi (`verify_edge_perimeter.sh`)

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script Name: verify_edge_perimeter.sh
# Deskripsi  : Otomasi audit dan verifikasi perimeter edge Cloudflare vs Origin
# ==============================================================================
set -euo pipefail

# Variabel Pengujian
DOMAIN="api-perimeter.cloud-enterprise.id"
ORIGIN_IP="203.0.113.195"

COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_NC='\033[0m' # No Color

echo -e "${COLOR_YELLOW}======================================================${COLOR_NC}"
echo -e "${COLOR_YELLOW} Memulai Audit Perimeter Cloudflare Edge vs Origin    ${COLOR_NC}"
echo -e "${COLOR_YELLOW} Target Domain: ${DOMAIN}                             ${COLOR_NC}"
echo -e "${COLOR_YELLOW} Target Origin: ${ORIGIN_IP}                          ${COLOR_NC}"
echo -e "${COLOR_YELLOW}======================================================${COLOR_NC}"

# Uji 1: Verifikasi DNS Resolution (Harus Mengembalikan IP Anycast Cloudflare)
echo -n "[TEST 1] Memeriksa status DNS Proxied (Anycast)... "
RESOLVED_IPS=$(dig +short "${DOMAIN}" A || true)
if [[ -z "${RESOLVED_IPS}" ]]; then
    echo -e "${COLOR_RED}GAGAL: Domain tidak dapat di-resolve.${COLOR_NC}"
    exit 1
fi

IS_DIRECT=false
while read -r ip; do
    if [[ "$ip" == "$ORIGIN_IP" ]]; then
        IS_DIRECT=true
    fi
done <<< "$RESOLVED_IPS"

if [ "$IS_DIRECT" = true ]; then
    echo -e "${COLOR_RED}BAHAYA! DNS mengembalikan IP fisik origin. Record masih Grey-Cloud!${COLOR_NC}"
    exit 1
else
    echo -e "${COLOR_GREEN}SUKSES (DNS terproteksi Anycast Cloudflare).${COLOR_NC}"
    echo "         Resolved IPs:"
    echo "${RESOLVED_IPS}" | sed 's/^/         - /'
fi

# Uji 2: Pengujian Bypass Direct-to-IP Origin
echo -n "[TEST 2] Menguji pemblokiran akses langsung ke IP Origin... "
DIRECT_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://${ORIGIN_IP}/" || echo "000")

if [[ "$DIRECT_STATUS" == "000" || "$DIRECT_STATUS" == "444" || "$DIRECT_STATUS" == "403" ]]; then
    echo -e "${COLOR_GREEN}SUKSES (Status: ${DIRECT_STATUS} - Direct connection ditolak).${COLOR_NC}"
else
    echo -e "${COLOR_RED}GAGAL! Origin dapat diakses langsung tanpa Cloudflare (Status: ${DIRECT_STATUS}).${COLOR_NC}"
    exit 1
fi

# Uji 3: Pengujian Akses Resmi Melalui Edge Cloudflare
echo -n "[TEST 3] Menguji transit request melalui Cloudflare Edge... "
EDGE_RESPONSE=$(curl -s -I --connect-timeout 10 "https://${DOMAIN}/")
HTTP_STATUS=$(echo "$EDGE_RESPONSE" | grep -i "^HTTP" | awk '{print $2}' | tail -n1)
CF_RAY=$(echo "$EDGE_RESPONSE" | grep -i "^cf-ray:" | awk '{print $2}' | tr -d '\r' || true)

if [[ "$HTTP_STATUS" == "200" && -n "$CF_RAY" ]]; then
    echo -e "${COLOR_GREEN}SUKSES (HTTP ${HTTP_STATUS}).${COLOR_NC}"
    echo -e "         CF-Ray Header: ${COLOR_GREEN}${CF_RAY}${COLOR_NC}"
else
    echo -e "${COLOR_RED}GAGAL: Tidak menerima HTTP 200 atau header CF-Ray tidak ditemukan.${COLOR_NC}"
    echo "         Status: ${HTTP_STATUS}"
    exit 1
fi

# Uji 4: Ekstraksi Lokasi PoP Datacenter dari CF-Ray
POP_IATA="${CF_RAY##*-}"
echo -e "[TEST 4] Edge PoP yang melayani request: ${COLOR_YELLOW}${POP_IATA}${COLOR_NC}"

echo -e "\n${COLOR_GREEN}>>> SELURUH VERIFIKASI PERIMETER PERFORMA & KEAMANAN SELESAI DENGAN STATUS VALID. <<<${COLOR_NC}"
```

---

## 5. Production Readiness Checklist

Gunakan matriks checklist berikut sebelum menyatakan arsitektur fondasi Cloudflare siap (*ready for production traffic*):

| Kategori | Item Pemeriksaan | Metode Validasi | Status |
| :--- | :--- | :--- | :---: |
| **DNS & Routing** | Seluruh A/AAAA record aplikasi produksi berstatus **Proxied (Orange Cloud)**. | `dig +short domain.com` tidak boleh mengembalikan IP origin. | [ ] |
| **DNS & Routing** | Subdomain non-HTTP (misal: SSH, FTP, Mail) dipisahkan ke IP server/VPC berbeda agar tidak membocorkan IP origin web. | Audit seluruh record di DNS Management zone. | [ ] |
| **Origin Isolation**| Security Group / Ingress Firewall origin memblokir port 80 & 443 dari `0.0.0.0/0`. | Akses langsung via IP publik menghasilkan `Connection Refused` atau `Timeout`. | [ ] |
| **Origin Isolation**| Hanya subnet IP resmi Cloudflare (IPv4 & IPv6) yang diizinkan masuk ke port 80/443 origin. | Verifikasi allowlist CIDR firewall dengan `https://www.cloudflare.com/ips-v4`. | [ ] |
| **Client Identity** | Origin mengaktifkan `ngx_http_realip_module` (atau ekuivalen di Traefik/Envoy). | Log akses origin mencatat IP publik ISP pengguna, bukan IP Cloudflare. | [ ] |
| **Client Identity** | Header sumber diset ke `CF-Connecting-IP` dengan `real_ip_recursive on`. | Validasi dengan mengirim header `X-Forwarded-For` tiruan dan pastikan tidak ter-spoof. | [ ] |
| **Observability** | Format log web server origin diubah ke JSON terstruktur dan menginjeksi `$http_cf_ray`. | Inspeksi `/var/log/nginx/access.log` memastikan key `cf_ray` terisi data valid. | [ ] |
| **TLS Hardening** | Mode SSL/TLS di dashboard Cloudflare diset ke **Full (Strict)**. | Menolak sertifikat self-signed atau expired di origin server. | [ ] |
| **TLS Hardening** | Minimum TLS version diatur ke **TLS 1.3** (atau 1.2 untuk backward compatibility legacy). | Verifikasi dengan `openssl s_client -tls1_1` (harus gagal handshake). | [ ] |
| **MTU / Network** | Path MTU Discovery (ICMP Type 3 Code 4) diizinkan melintasi firewall origin jika menggunakan tunnel. | Pengujian HTTP POST payload besar (>10MB) tidak mengalami hang/stall. | [ ] |
