# Evaluasi Bab 02: SSL/TLS Encryption, Origin CA, & Custom Certificates Lifecycle

## 1. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan mendasar antara mode enkripsi **Full** dan **Full (Strict)** pada Cloudflare?
- A. Mode *Full* tidak mengenkripsi traffic antara Cloudflare dan Origin, sedangkan *Full (Strict)* mengenkripsinya.
- B. Mode *Full* memvalidasi masa berlaku sertifikat origin, sedangkan *Full (Strict)* mengabaikannya.
- C. Mode *Full* mengenkripsi traffic ke origin tetapi menerima sertifikat yang tidak tepercaya/self-signed, sedangkan *Full (Strict)* mewajibkan sertifikat yang valid dan tepercaya.
- D. Mode *Full* hanya mendukung protokol HTTP/2, sedangkan *Full (Strict)* mendukung HTTP/3.

### Soal 2
Mengapa penggunaan mode enkripsi **Flexible** dapat memicu browser menampilkan error `ERR_TOO_MANY_REDIRECTS`?
- A. Karena Cloudflare kehabisan kuota sertifikat Universal SSL.
- B. Karena edge Cloudflare meminta traffic ke origin via HTTP port 80, sementara origin dikonfigurasi untuk me-redirect seluruh traffic HTTP ke HTTPS secara permanen.
- C. Karena sertifikat di origin server kedaluwarsa.
- D. Karena DNS record diset ke mode DNS-Only (Grey-clouded).

### Soal 3
Berapa lama masa berlaku maksimum yang dapat dipilih saat menerbitkan sertifikat menggunakan **Cloudflare Origin CA**?
- A. 90 hari.
- B. 1 tahun.
- C. 5 tahun.
- D. 15 tahun.

### Soal 4
Apa fungsi utama dari fitur **Authenticated Origin Pulls (AOP)**?
- A. Mempercepat proses kompresi Brotli di origin server.
- B. Memastikan origin server memvalidasi bahwa koneksi HTTPS yang masuk berasal secara eksklusif dari edge Cloudflare via otentikasi client certificate.
- C. Mengizinkan origin server mengambil resource cache langsung dari Edge NVMe storage.
- D. Mengganti kebutuhan DNS Anycast pada zone Enterprise.

### Soal 5
Manakah dari cipher suite berikut yang **HARUS** dihindari dalam audit keamanan modern (PCI-DSS) karena kerentanan terhadap serangan CBC padding oracle?
- A. `TLS_AES_128_GCM_SHA256`
- B. `ECDHE-ECDSA-AES128-GCM-SHA256`
- C. `ECDHE-RSA-AES256-SHA384` (CBC Mode)
- D. `ECDHE-ECDSA-CHACHA20-POLY1305`

---

## 2. Intermediate Questions (5 Soal)

### Soal 1
Sebuah institusi perbankan mengaktifkan TLS 1.3 dengan fitur **0-RTT (Early Data)** di Cloudflare. Serangan siber apakah yang berpotensi mengeksploitasi fitur ini pada endpoint API transaksi perbankan (`POST /api/v1/transfer`), dan bagaimana langkah mitigasinya?
- A. Serangan POODLE; mitigasi dengan mengaktifkan Fallback SCSV.
- B. Serangan Replay Attack; mitigasi dengan menonaktifkan 0-RTT di Cloudflare atau menolak Early Data header (`Early-Data: 1`) pada HTTP method non-idempoten di layer origin/worker.
- C. Serangan Heartbleed; mitigasi dengan memperbarui OpenSSL ke versi LTS terbaru.
- D. Serangan SYN Flood; mitigasi dengan mengaktifkan Magic Transit.

### Soal 2
Ketika beralih dari Universal SSL ke **Advanced Certificate Manager (ACM)**, kapabilitas apa yang terbuka bagi arsitektur multi-tenant dengan subdomain bersarang (misal: `tenant1.app.asia.domain.com`)?
- A. Kemampuan otomatisasi BGP Anycast routing.
- B. Kemampuan menerbitkan wildcard certificate multi-level yang disesuaikan secara granular tanpa batas single-level subdomain.
- C. Kemampuan mem-bypass WAF Cloudflare untuk subdomain tepercaya.
- D. Penghapusan kewajiban terminasi TLS di Edge.

### Soal 3
Pada arsitektur **Keyless SSL**, data kriptografi apakah yang dikirimkan oleh Cloudflare Edge ke on-premise Keyless Server milik pelanggan selama TLS Handshake berlangsung?
- A. Seluruh plain-text HTTP payload request dari user.
- B. Private Key pelanggan yang disimpan di edge memory.
- C. Cryptographic challenge / ephemeral session data yang membutuhkan operasi dekripsi atau penandatanganan private key oleh HSM on-premise.
- D. Session database cookie pelanggan.

### Soal 4
Origin server Anda menampilkan pesan error **Cloudflare Error 526: Invalid SSL Certificate**. Apa urutan diagnosa paling logis yang harus Anda lakukan via terminal?
- A. Restart NGINX -> Ubah DNS ke grey-cloud -> Hapus cache Cloudflare.
- B. Periksa DNS TTL -> Jalankan `traceroute` ke IP origin -> Buka port 80 di firewall origin.
- C. Eksekusi `openssl s_client -connect <ORIGIN_IP>:443 -servername <DOMAIN>` -> Periksa tanggal kedaluwarsa sertifikat, Subject Alternative Name (SAN), dan Root Issuer -> Pastikan CA ditandatangani oleh publik tepercaya atau Cloudflare Origin CA.
- D. Turunkan mode Cloudflare ke `Off` -> Verifikasi apakah website dapat dibuka melalui HTTP port 80.

### Soal 5
Apa implikasi teknis mengaktifkan **HSTS Preload** pada domain organisasi Anda?
- A. Domain akan langsung di-cache di seluruh recursive DNS milik ISP global.
- B. Browser modern (Chrome, Firefox, Safari) mengompilasi domain ke dalam hardcoded list internal mereka, menolak semua koneksi HTTP non-aman bahkan sebelum network connection pertama dibuat, dan penolakan ini tidak dapat di-bypass oleh end-user jika terjadi sertifikat invalid.
- C. Seluruh traffic HTTP port 80 akan diproxy menggunakan UDP port 443 via QUIC.
- D. Cloudflare secara otomatis memperbarui sertifikat origin 30 hari sebelum kedaluwarsa.

---

## 3. Scenario-Based Questions (3 Soal Kasus Nyata)

### Skenario 1: The Migration Disaster
Sebuah perusahaan e-commerce unicorn bermigrasi dari legacy CDN ke Cloudflare. Mereka memiliki 10.000 customer aktif per menit. Administrator mengaktifkan mode enkripsi **Full** dan menyalakan fitur **Automatic HTTPS Rewrites**. 
Dua jam setelah migrasi, tim Network Security menemukan bahwa seorang penyerang berhasil melakukan *Man-in-the-Middle (MitM)* attack di jaringan ISP lokal tempat Origin Server berada dengan merutekan IP origin ke server perantara yang memiliki sertifikat self-signed palsu.
1. Mengapa Cloudflare Edge tidak memutus koneksi dan tetap menyajikan halaman ke pengguna?
2. Bagaimana cara menghentikan serangan tersebut dalam waktu kurang dari 5 menit menggunakan konfigurasi Cloudflare?
3. Langkah pencegahan struktural apa yang harus diotomasi pada pipeline CI/CD infrastruktur mereka?

### Skenario 2: The Enterprise Regulated FinTech & Hardware Security Modules (HSM)
FinTech "PaySecure" diwajibkan oleh regulator moneter nasional untuk mematuhi regulasi di mana *Private Key* untuk sertifikat EV (Extended Validation) bank `paysecure.com` dilarang keras disimpan pada server berbasis cloud pihak ketiga, termasuk memory server Cloudflare. Namun, tim IT PaySecure tetap menuntut akselerasi CDN Anycast Cloudflare, proteksi DDoS 150+ Tbps, dan WAF edge rules.
1. Rancang arsitektur enkripsi yang memenuhi seluruh batasan regulasi di atas tanpa mengecualikan proteksi WAF Cloudflare!
2. Jelaskan komponen infrastruktur internal apa yang wajib disediakan tim infrastruktur PaySecure di datacenter on-premise mereka.
3. Analisis dampak latensi dari arsitektur ini terhadap handshake pertama (cold connection) vs resume handshake (session resumption).

### Skenario 3: Broken API Outage pasca Update AOP
Tim DevOps mengaktifkan fitur **Authenticated Origin Pulls (AOP)** pada level zone di dashboard Cloudflare untuk domain `api.enterprise.com`. Seketika itu juga, 100% request API yang menuju ke origin cluster NGINX menghasilkan respons **Cloudflare Error 525**.
Setelah diselidiki, cluster NGINX origin mereka belum dikonfigurasi direktif `ssl_client_certificate`.
1. Mengapa Error 525 terjadi pada skenario ini? Jelaskan apa yang terjadi di level TLS protocol handshake.
2. Tuliskan blok konfigurasi NGINX yang tepat untuk menyelesaikan krisis ini dengan memverifikasi client certificate Cloudflare secara benar.
3. Jika domain tersebut berbagi server upstream yang sama dengan subdomain internal lain yang tidak melewati Cloudflare, pendekatan AOP tingkat apa yang seharusnya digunakan (Zone-level vs Per-Hostname AOP)?

---

## 4. Practical Chapter Challenge
### Objective: Hardened Zero-Trust Edge-to-Origin Pipeline with Custom Mutual TLS Validation
Anda ditunjuk sebagai Lead SRE untuk merancang implementasi zero-trust TLS end-to-end pada arsitektur hybrid cloud berikut:
- **FQDN**: `vault.fintech-kolektif.id`
- **Edge Layer**: Cloudflare Enterprise dengan DNS ter-proxy (Orange Cloud).
- **Origin Layer**: Virtual Machine di Private Cloud dengan NGINX reverse-proxy di IP `203.0.113.50`.

### Syarat Teknis:
1. **Edge Hardening**:
   - Enforce **Full (Strict)**.
   - Minimum TLS Version 1.3 (fallback TLS 1.2 hanya diizinkan untuk cipher AEAD).
   - Enforce HSTS: 1 tahun, includeSubDomains, Preload.
   - Nonaktifkan TLS 1.3 Early Data (0-RTT).
2. **Origin Protection (Two-Way TLS Authentication)**:
   - Terbitkan sertifikat Cloudflare Origin CA validitas 3 tahun untuk `vault.fintech-kolektif.id`.
   - Konfigurasi **Per-Hostname Authenticated Origin Pulls (AOP)** dengan Custom CA milik perusahaan (bukan Shared CF Pull Cert).
3. **Automasi Terraform**:
   - Tuliskan skrip Terraform lengkap deklaratif untuk memprovisi seluruh konfigurasi Edge di atas.
4. **NGINX Production Config**:
   - Sediakan file `nginx.conf` origin yang memblokir akses jika client certificate Cloudflare tidak valid atau jika koneksi diakses langsung via IP bypass tanpa SNI yang sesuai.

---

## Kunci Jawaban & Panduan Pembahasan

### Bagian 1: Basic
1. **C** - Mode Full tidak memverifikasi validitas rantai sertifikat origin (menerima self-signed), sementara Full (Strict) mewajibkan sertifikat yang valid dan tepercaya.
2. **B** - Mode Flexible memanggil origin via HTTP (port 80). Jika origin mengembalikan respons redirect (301/302) ke HTTPS, siklus berulang tanpa henti antara browser dan Cloudflare edge.
3. **D** - Cloudflare Origin CA dapat menerbitkan sertifikat dengan masa berlaku hingga 15 tahun (5475 hari).
4. **B** - Authenticated Origin Pulls (AOP) menggunakan otentikasi client certificate TLS dua arah (mTLS) di mana origin memvalidasi sertifikat edge Cloudflare.
5. **C** - Cipher berbasis mode CBC (Cipher Block Chaining) seperti `ECDHE-RSA-AES256-SHA384` rentan terhadap serangan padding oracle dan tidak memenuhi standar hardened modern.

### Bagian 2: Intermediate
1. **B** - Serangan *Replay Attack*. Karena Early Data TLS 1.3 dikirim sebelum handshake selesai, penyerang yang meng-intercept paket data dapat memutar ulang (replay) payload HTTP POST tanpa perlu mendekripsinya. Mitigasi: Nonaktifkan 0-RTT atau tolak request ber-header `Early-Data: 1` pada endpoint mutasi data.
2. **B** - Universal SSL terbatas pada sertifikat fixed level (`example.com` dan `*.example.com`). ACM memungkinkan wildcard multi-tingkat seperti `*.app.asia.domain.com`.
3. **C** - Cloudflare Edge hanya mengirimkan cryptographic handshake challenge yang membutuhkan operasi penandatanganan/dekripsi private key ke Keyless Server/HSM.
4. **C** - Melakukan inspeksi TLS handshake langsung ke origin menggunakan `openssl s_client` untuk memeriksa masa berlaku, kecocokan SAN, dan validitas Root CA.
5. **B** - HSTS Preload menginstruksikan browser vendor untuk memasukkan domain ke hardcoded browser list sehingga browser tidak akan pernah mengizinkan komunikasi HTTP cleartext, memitigasi serangan SSL-stripping secara permanen.

### Bagian 3: Skenario Kasus Nyata
- **Skenario 1**:
  1. *Akar Masalah*: Mode *Full* menerima sertifikat apa pun di origin, termasuk sertifikat self-signed palsu dari penyerang MitM.
  2. *Solusi Cepat*: Segera ubah mode enkripsi di dashboard Cloudflare ke **Full (Strict)**. Edge Cloudflare akan seketika menolak sertifikat self-signed penyerang dan memutus aliran data (Error 526) sebelum data bocor.
  3. *Pencegahan CI/CD*: Terapkan arsitektur Terraform yang mengunci parameter `ssl = "strict"` dan lakukan validasi policy menggunakan Terraform Sentinel atau OPA Conftest.
- **Skenario 2**:
  1. *Arsitektur*: Implementasikan **Cloudflare Keyless SSL**. Kunci privat tetap berada di dalam HSM on-premise PaySecure.
  2. *Komponen*: Datacenter PaySecure harus menjalankan instance **Cloudflare Keyless Server daemon** yang terhubung secara lokal melalui antarmuka PKCS#11 ke Hardware Security Module (HSM) FIPS 140-2 Level 3, serta terhubung ke edge Cloudflare via koneksi mTLS yang aman.
  3. *Latensi*: Handshake baru (cold start) akan mengalami tambahan round-trip time (RTT) setara latensi jaringan antara Cloudflare Edge dan datacenter Keyless HSM. Namun, untuk koneksi yang menggunakan TLS Session Resumption atau HTTP/2 & HTTP/3 multiplexing, latensi tambahan dapat diminimalisir mendekati 0 ms.
- **Skenario 3**:
  1. *Akar Masalah*: Ketika AOP aktif di level Cloudflare Zone, Edge Cloudflare menyajikan client certificate saat handshake ke origin. Jika NGINX origin tidak disiapkan untuk merespons atau salah dalam handshake mTLS negotiation, koneksi TLS origin leg gagal total pada tahap *CertificateVerify* atau *ClientHello*, memicu Error 525.
  2. *Konfigurasi NGINX*: Pasang direktif `ssl_client_certificate /etc/nginx/certs/cloudflare_aop.crt;` dan `ssl_verify_client on;`.
  3. *Pendekatan*: Gunakan **Per-Hostname Authenticated Origin Pulls** menggunakan certificate custom agar enforcement hanya diterapkan pada hostname `api.enterprise.com` tanpa merusak subdomain internal lain pada origin server yang sama.