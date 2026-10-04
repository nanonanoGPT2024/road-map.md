# Quiz & Challenge Bab 05: DDoS Mitigation, Advanced Rate Limiting, & Bot Management

---

## I. Basic Questions (5 Soal)

### Soal 1
Bagaimana mekanisme Anycast BGP membantu memitigasi serangan DDoS volumetrik L3/L4 berukuran multi-gigabit/terabit dibandingkan dengan arsitektur Unicast tradisional?
- **A.** Anycast mengarahkan seluruh lalu lintas serangan ke satu server superkomputer terpusat di data center utama Cloudflare.
- **B.** Anycast memecah paket serangan menjadi potongan-potongan kecil lalu mengenkripsinya dengan enkripsi TLS 1.3.
- **C.** Alamat IP publik yang sama diiklankan secara serentak dari seluruh Point of Presence (PoP) edge global, sehingga lalu lintas serangan diserap dan dieliminasi secara terdistribusi di PoP terdekat secara geografis dan topologis.
- **D.** Anycast secara otomatis mengubah IP origin server pelanggan setiap kali terjadi lonjakan paket TCP SYN.

### Soal 2
Komponen arsitektur kernel Linux apa yang dimanfaatkan oleh daemon `dosd` Cloudflare untuk melakukan *drop* paket serangan L3/L4 dengan konsumsi CPU paling minimal?
- **A.** User Space Memory via IPTables RAW table.
- **B.** eBPF (Extended Berkeley Packet Filter) pada layer XDP (eXpress Data Path) di driver Network Interface Card.
- **C.** TCP Socket Buffer (`sk_buff`) allocation pool di kernel space.
- **D.** Cron job terjadwal yang mengeksekusi command `ip route add blackhole`.

### Soal 3
Berapa rentang nilai Cloudflare Machine Learning `cf.bot_management.score`, dan nilai berapakah yang secara definitif mengindikasikan bahwa lalu lintas berasal dari bot otomatis (*automated traffic*)?
- **A.** 0 hingga 100; di mana nilai di atas 80 adalah bot otomatis.
- **B.** 1 hingga 99; di mana nilai antara 1 hingga 29 mengindikasikan lalu lintas otomatis/bot.
- **C.** -100 hingga +100; di mana nilai negatif mengindikasikan serangan botnet.
- **D.** 1 hingga 10; di mana nilai 5 adalah ambang batas netral manusia.

### Soal 4
Apa fungsi utama dari fitur **Counting Expression** pada Cloudflare Advanced Rate Limiting?
- **A.** Menghitung jumlah byte bandwidth yang digunakan oleh origin server dalam rentang waktu 24 jam.
- **B.** Mengonfigurasi ekspresi kondisi sekunder (seperti respons origin `http.response.code eq 401`) yang menentukan kapan sebuah request dihitung ke dalam kuota rate limit.
- **C.** Menghitung total pengunjung unik harian untuk keperluan penagihan lisensi Cloudflare.
- **D.** Menjalankan algoritma machine learning untuk memprediksi jumlah bot yang akan datang.

### Soal 5
Manakah dari pernyataan berikut yang paling akurat mengenai keunggulan **Cloudflare Turnstile** dibandingkan CAPTCHA tradisional (seperti reCAPTCHA puzzle)?
- **A.** Turnstile mengharuskan pengguna menyelesaikan minimal dua teka-teki visual untuk setiap formulir login.
- **B.** Turnstile mengumpulkan data histori pencarian browser pengguna untuk monetisasi iklan pihak ketiga.
- **C.** Turnstile memanfaatkan tantangan kriptografis non-interaktif di background browser, verifikasi Private State Tokens, dan telemetry hardware untuk memvalidasi kemanusiaan tanpa friksi puzzle visual.
- **D.** Turnstile hanya dapat dijalankan pada browser Google Chrome di sistem operasi Windows.

---

## II. Intermediate Questions (5 Soal)

### Soal 6
Dalam skenario implementasi **Cloudflare Magic Transit**, apa penyebab utama koneksi data besar (seperti unduhan file atau sesi TLS) terputus (*freeze* / *hang*), sementara uji coba ICMP Ping berukuran kecil berjalan lancar?
- **A.** BGP Session antara Cloudflare dan upstream provider mengalami flapping.
- **B.** Penambahan header enkapsulasi GRE sebesar 24 bytes menurunkan Path MTU efektif menjadi 1476 bytes, menyebabkan paket TCP berukuran standar 1500 bytes di-drop karena tidak diterapkannya TCP MSS Clamping pada router on-premise.
- **C.** dosd secara tidak sengaja memblokir seluruh paket TCP ACK pada layer Layer 4.
- **D.** Magic Transit tidak mendukung protokol TCP, melainkan hanya protokol UDP dan ICMP.

### Soal 7
Sebuah aturan WAF dibuat dengan ekspresi:
```text
(cf.bot_management.score lt 30 and http.request.uri.path contains "/api/")
Action: Block
```
Setelah diaktifkan, tim SEO melaporkan bahwa crawler resmi Googlebot tidak dapat mengindeks API dokumentasi publik. Apa modifikasi aturan yang paling tepat untuk mengatasi masalah ini tanpa mengurangi postur keamanan dari bot liar?
- **A.** Menurunkan threshold bot score menjadi `cf.bot_management.score lt 5`.
- **B.** Mengubah ekspresi menjadi: `(cf.bot_management.score lt 30 and http.request.uri.path contains "/api/" and not cf.bot_management.verified_bot)`.
- **C.** Mengganti action `Block` menjadi `Allow`.
- **D.** Menambahkan daftar seluruh IP publik Google secara manual ke dalam IP Access Rule Allowlist.

### Soal 8
Bagaimana cara kerja mitigasi serangan **HTTP/2 Rapid Reset (CVE-2023-44487)** pada layer edge HTTP DDoS protection Cloudflare?
- **A.** Mematikan protokol HTTP/2 secara global dan memaksa seluruh browser menggunakan HTTP/1.0.
- **B.** Mendeteksi anomali transmisi frame `RST_STREAM` yang dikirimkan secara masif oleh client seketika setelah frame request dibuka, kemudian membatalkan stream dan menutup koneksi TCP client pada level edge proxy.
- **C.** Memasang CAPTCHA visual pada setiap frame HTTP/2 yang masuk ke edge server.
- **D.** Meneruskan seluruh frame reset stream ke origin server untuk dianalisis oleh firewall lokal.

### Soal 9
Perhatikan skenario Advanced Rate Limiting berikut: Tim SRE ingin memitigasi serangan *distributed credential stuffing* di mana penyerang merotasi ribuan IP perumahan (*residential proxies*) untuk mencoba kombinasi password pada endpoint `/login`. Mengapa konfigurasi karakteristik rate limit `characteristics = ["ip.src"]` dipastikan **GAGAL** mencegah serangan ini?
- **A.** Karena Cloudflare tidak dapat membaca alamat IP publik pengirim request.
- **B.** Karena setiap IP unik residensial hanya mengirim 1 atau 2 request (di bawah batas ambang rate limit IP), namun akumulasi serangan secara total ke endpoint origin mencapai jutaan request.
- **C.** Karena metode HTTP POST tidak didukung oleh Ruleset Engine Cloudflare.
- **D.** Karena IP residensial selalu memiliki Bot Score 99.

### Soal 10
Apa perbedaan arsitektural mendasar antara **Super Bot Fight Mode (SBFM)** pada paket Pro/Business dengan **Bot Management for Enterprise**?
- **A.** SBFM gratis, sedangkan Enterprise menggunakan lisensi berbayar per-request.
- **B.** SBFM hanya menyediakan toggle konfigurasi global tingkat tinggi berbasis klasifikasi broad (*Definitely Automated* vs *Likely Automated*), sedangkan Enterprise memberikan eksposur variabel granular (`cf.bot_management.score` 1-99, JA4/JA3 fingerprint, detection IDs) yang dapat diintegrasikan secara bebas ke dalam Custom WAF Rules dan Advanced Rate Limiting.
- **C.** SBFM beroperasi di Layer 3, sedangkan Bot Management Enterprise beroperasi di Layer 7.
- **D.** SBFM hanya mampu memeriksa User-Agent string, sedangkan Enterprise menggunakan firewall hardware terpisah.

---

## III. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: Serangan SMS Pumping Fraud Terdistribusi
Sebuah platform fintech mengalami lonjakan biaya vendor SMS Gateway hingga ratusan juta rupiah dalam 2 jam akibat serangan *SMS Pumping Fraud*. Penyerang secara otomatis memicu request OTP ke endpoint `POST /api/v1/otp/send`. Penyerang merotasi ribuan alamat IP dan memalsukan string User-Agent menyerupai browser Chrome asli di perangkat Android. 

**Tugas Anda:**
Rancang strategi mitigasi komposit pada Cloudflare edge yang mencakup:
1. Pemanfaatan Bot Management.
2. Aturan Advanced Rate Limiting dengan karakteristik spesifik.
3. Integrasi client-side mitigation.

Jelaskan arsitektur ruleset yang harus dibangun beserta ekspresi logika dan parameter rate limit-nya.

### Skenario 2: Serangan BGP Prefix Hijacking dan Volumetrik Multi-Vektor ke On-Premises
Sebuah bank memiliki Autonomous System (AS) publik sendiri dengan subnet `/24` IPv4 yang meng-host layanan Internet Banking on-premise. Tiba-tiba, traffic gateway internet mereka mengalami saturasi 100% (uplink 10 Gbps drop total) akibat serangan gabungan:
- 1.2 Tbps DNS Amplification Attack.
- Terindikasi adanya upaya pengumuman BGP prefix palsu (*BGP hijacking*) di internet publik dari entitas liar di negara asing.

**Tugas Anda:**
1. Bagaimana solusi **Cloudflare Magic Transit** menyelesaikan masalah saturasi kapasitas uplink lokal tersebut?
2. Bagaimana mekanisme Magic Transit menangani lalu lintas egress (balasan dari bank ke nasabah) tanpa membebani bandwidth GRE tunnel yang sama (konsep Direct Server Return)?
3. Fitur keamanan routing BGP apa yang wajib diterapkan bersama Cloudflare untuk menghentikan pembajakan prefix IP bank tersebut di level global?

### Skenario 3: False Positive Badai E-Commerce API Mobile App
Setelah tim keamanan mengaktifkan aturan WAF:
`cf.bot_management.score lt 30 -> Action: Managed Challenge`
di seluruh domain platform e-commerce, transaksi pembayaran sukses turun sebesar 40%. Penyelidikan menunjukkan bahwa aplikasi mobile Android native versi lama menggunakan library HTTP kustom (bukan browser web) yang tidak dapat mengeksekusi JavaScript challenge Turnstile, sehingga request checkout dari pengguna Android asli terhenti di edge dengan status HTTP 403 / Challenge.

**Tugas Anda:**
1. Mengapa library HTTP native pada native mobile app mendapatkan skor bot rendah dari Cloudflare ML Bot Engine?
2. Tuliskan perubahan arsitektur WAF Rule yang elegan untuk mengecualikan (bypass) lalu lintas mobile app resmi yang sah tanpa membuka celah bagi botnet penyerang untuk menyamar sebagai mobile app tersebut.

---

## IV. Practical Chapter Challenge: Enterprise Multi-Tier Defense

### Deskripsi Masalah
Anda adalah Principal Security & SRE Architect di sebuah unicorn ticketing platform. Dalam rangka penjualan tiket konser mega-bintang, sistem Anda diperkirakan akan menerima 100.000 request per detik pada endpoint pembelian tiket:
- Endpoint: `POST /api/v3/concerts/{concert_id}/tickets/reserve`
- Host: `checkout.unicorn-tickets.com`

Penyerang dipastikan akan mengerahkan berbagai teknik:
1. Distributed scalper bots berbasis Headless Puppeteer/Playwright dengan rotasi proxy residential.
2. Brute-force token transaksi via L7 HTTP Flood.
3. Upaya bypass challenge menggunakan tool solver CAPTCHA otomatis.

### Kriteria Solusi yang Harus Dikirimkan
Buatlah rancangan konfigurasi arsitektur dan deklarasi kode yang mencakup:
1. **Terraform Ruleset Configuration (`ruleset.tf`)**:
   - Satu aturan mitigasi bot menggunakan Bot Score, JA4 fingerprint anomaly, dan verifikasi Turnstile Pre-clearance.
   - Satu aturan Advanced Rate Limiting komposit yang menghitung request berdasarkan identitas `user_id` yang diekstrak dari Session JWT / Cookie atau HTTP Header, dengan fallback ke IP jika unauthenticated.
2. **Turnstile Integration Flowchart & Origin Verification Logic**:
   - Jelaskan bagaimana payload token Turnstile divalidasi di sisi frontend dan diverifikasi kembali secara asinkron di origin application backend sebelum lock inventory database dieksekusi.
3. **Runbook Operasi Darurat (SOP)**:
   - Langkah teknis SRE jika terjadi lonjakan mendadak pada *false-positive rate* saat tiket mulai dijual (misal: Cloudflare edge mendeteksi lonjakan traffic valid sebagai HTTP DDoS Attack).

---

## Kunci Jawaban & Petunjuk Evaluasi

### Bagian I: Basic
1. **C** - Alamat IP Anycast diiklankan dari seluruh PoP edge global, memecah dan menyerap volume serangan di lokasi terdekat dengan sumber botnet.
2. **B** - eBPF pada layer XDP (eXpress Data Path) mengeksekusi instruksi `XDP_DROP` langsung di level driver NIC tanpa alokasi memori kernel Linux.
3. **B** - Skala Bot Score berkisar antara 1 hingga 99; nilai 1-29 secara definitif diklasifikasikan sebagai traffic otomatis/bot oleh ML Cloudflare.
4. **B** - Counting expression mengevaluasi kondisi spesifik (seperti mencocokkan kode status respons HTTP dari origin) untuk menentukan kapan counter dinaikkan.
5. **C** - Turnstile mengeliminasi puzzle visual melalui tantangan kriptografis latar belakang non-interaktif dan browser integrity telemetry.

### Bagian II: Intermediate
6. **B** - Overhead enkapsulasi header GRE mengurangi ukuran effective MTU. Kegagalan mengatur TCP MSS Clamping pada edge router menyebabkan paket berukuran penuh (1500 bytes) di-drop oleh mekanisme Path MTU Discovery yang terblokir.
7. **B** - Menambahkan kondisi `and not cf.bot_management.verified_bot` mengecualikan mesin pencari resmi yang telah divalidasi oleh Cloudflare via reverse DNS & ASN lookup.
8. **B** - Edge Cloudflare mendeteksi aliran frame `RST_STREAM` masif pada koneksi multiplexing HTTP/2, memotong koneksi TCP di edge sebelum origin server kehabisan resource alokasi stream.
9. **B** - Serangan residential proxy mendistribusikan jutaan request ke jutaan IP unik; membatasi threshold per IP tidak efektif karena setiap IP penyerang hanya membuat sedikit request yang tidak melanggar threshold.
10. **B** - Super Bot Fight Mode hanya memiliki toggle biner sederhana pada antarmuka dashboard, sedangkan Enterprise Bot Management mengekspos skor individual (1-99), JA3/JA4 fingerprinting, dan integrasi penuh dengan Ruleset Engine.

### Bagian III: Scenario Guidance
- **Skenario 1**:
  - Konfigurasikan Turnstile widget pada antarmuka frontend tombol "Kirim OTP".
  - Buat WAF Rule: Jika path `/api/v1/otp/send` dan `cf.bot_management.score < 30`, terapkan aksi `Block`.
  - Buat Advanced Rate Limiting dengan karakteristik komposit: `http.request.headers["x-device-fingerprint"]` dan nomor telepon di body/query. Batasi 1 request per nomor telepon per 60 detik, serta batasi 5 request per subnet IP per 10 menit.
- **Skenario 2**:
  - Magic Transit mengumumkan prefix `/24` bank via Anycast global BGP Cloudflare. Bandwidth 1.2 Tbps diserap oleh edge Cloudflare (kapasitas total >300 Tbps), lalu paket bersih dienkapsulasi lewat GRE tunnel ke router bank.
  - Terapkan Direct Server Return (DSR): Paket outbound dari bank ke nasabah dikirim langsung melalui ISP lokal bank tanpa melewati GRE tunnel Cloudflare, menghindari saturasi tunnel.
  - Implementasikan RPKI (Resource Public Key Infrastructure) dan ROA (Route Origin Authorization) untuk memvalidasi bahwa hanya ASN Cloudflare/Bank yang sah yang berhak mengumumkan prefix tersebut.
- **Skenario 3**:
  - Native mobile app menggunakan HTTP client library (seperti OkHttp atau NSURLSession) yang tidak mengeksekusi engine JS browser web, sehingga tidak menghasilkan browser telemetry yang dibutuhkan ML Bot Engine untuk mendapatkan skor tinggi.
  - Solusi: Terapkan Cloudflare Mobile SDK atau gunakan API Shield dengan Mutual TLS (mTLS) atau cryptographic request signing (HMAC / token pertukaran) untuk memvalidasi keaslian native mobile app, lalu buat WAF Rule:
    `if (http.request.headers["x-app-cert-verified"] eq "true") -> Skip Bot Management Phase`.

---