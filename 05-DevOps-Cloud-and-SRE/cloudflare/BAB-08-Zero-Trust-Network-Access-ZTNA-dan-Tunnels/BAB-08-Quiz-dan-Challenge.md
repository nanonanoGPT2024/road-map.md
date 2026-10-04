# Evaluasi Pembelajaran Bab 08: Zero Trust Network Access (ZTNA) & Cloudflare Tunnels

---

## Bagian 1: Basic Questions (Pilihan Ganda & Analisis Singkat)

### Soal 1
Mengapa arsitektur Cloudflare Tunnel dianggap menghilangkan risiko serangan pemindaian port publik (port scanning)?
- A. Karena Cloudflare Tunnel mengenkripsi port scanner menggunakan SSL/TLS.
- B. Karena daemon `cloudflared` hanya membuat koneksi keluar (outbound-only) ke edge Cloudflare, sehingga firewall origin dapat menutup seluruh port masuk (inbound: 0).
- C. Karena Cloudflare secara otomatis mengubah port internal origin menjadi port dinamis setiap 5 detik.
- D. Karena Cloudflare memalsukan IP origin menjadi IP multicast global.

### Soal 2
Protokol transport default yang digunakan oleh daemon `cloudflared` modern untuk menghubungkan origin ke edge Cloudflare adalah:
- A. IPsec ESP
- B. GRE Tunneling
- C. QUIC (berbasis UDP port 7844)
- D. PPTP

### Soal 3
Bagian token HTTP Header apa yang disematkan oleh Cloudflare Access setelah pengguna berhasil melakukan autentikasi login via IdP untuk divalidasi oleh web server origin?
- A. `X-Auth-Basic-Token`
- B. `Cf-Access-Jwt-Assertion`
- C. `Authorization: Bearer static-admin-key`
- D. `X-Origin-WireGuard-Secret`

### Soal 4
Apa perbedaan mendasar antara Cloudflare Access dan Cloudflare Gateway?
- A. Access beroperasi mengamankan traffic inbound menuju aplikasi internal; Gateway beroperasi mengamankan traffic outbound pengguna menuju web/internet.
- B. Access hanya mendukung DNS; Gateway hanya mendukung HTTP.
- C. Access membutuhkan agen WARP di semua skenario; Gateway sama sekali tidak dapat bekerja dengan WARP.
- D. Access khusus untuk AWS; Gateway khusus untuk Google Cloud.

### Soal 5
Pada file konfigurasi `config.yml` milik `cloudflared`, baris terbawah wajib diisi dengan ingress rule catch-all berupa:
- A. `- service: drop`
- B. `- service: http://localhost:80`
- C. `- service: http_status:404`
- D. `- service: reject_unauthorized`

---

## Bagian 2: Intermediate Questions

### Soal 6
Jelaskan peran algoritma **JSON Web Key Set (JWKS)** dalam arsitektur Cloudflare Access. Bagaimana origin server memverifikasi keabsahan request tanpa harus memanggil API Cloudflare secara tersinkronisasi pada setiap HTTP hit?

### Soal 7
Dalam implementasi **Split Tunneling** pada Cloudflare WARP Client, jelaskan perbedaan konsekuensi teknis dan risiko keamanan antara pendekatan **Exclude Mode** versus **Include Mode** untuk jaringan korporat!

### Soal 8
Sebuah origin backend menggunakan sertifikat SSL internal yang ditandatangani oleh internal private CA milik perusahaan (self-signed). Saat dihubungkan ke `cloudflared` dengan target `https://192.168.1.100:443`, browser memunculkan status `502 Bad Gateway`. Konfigurasi apa yang harus disematkan pada parameter `originRequest` di `cloudflared` untuk mengatasi hal ini secara terisolasi tanpa mematikan enkripsi lokal?

### Soal 9
Bagaimana Cloudflare Gateway melakukan **TLS Decryption (HTTPS Inspection)** terhadap perangkat pengguna, dan mengapa sertifikat root CA Cloudflare harus diinstal pada *System Trusted Root Store* di perangkat klien?

### Soal 10
Jelaskan mekanisme kerja **Device Posture Check** pada Cloudflare Zero Trust saat mendeteksi bahwa disk enkripsi workstation (misal: FileVault pada macOS atau BitLocker pada Windows) dinonaktifkan oleh pengguna! Apa urutan event dari WARP client hingga edge memutuskan koneksi?

---

## Bagian 3: Scenario-Based Questions (Kasus Nyata Industri)

### Skenario 1: Insiden Kerentanan Zero-Day pada Web Service Warisan
PT Finansial Sejahtera memiliki aplikasi internal administrasi nasabah berbasis web warisan (legacy Java framework) yang rentan terhadap eksekusi remote code execution (RCE). Aplikasi ini berjalan di on-premise datacenter dan membutuhkan waktu 2 bulan untuk pembaruan kode. 
Sebagai Lead SRE, Anda diminta menerapkan Cloudflare ZTNA secara darurat untuk mengamankan aplikasi tersebut hari ini juga tanpa mengubah kode aplikasi.
- **Pertanyaan**: Susun rencana arsitektur langkah demi langkah (konfigurasi firewall, instalasi tunnel, Access policy, dan Device posture) agar aplikasi ini sepenuhnya terisolasi dan hanya staf compliance dengan laptop korporat resmi yang dapat mengaksesnya!

### Skenario 2: Masalah Fallback Protokol Jaringan pada Koneksi ISP Korporat
Cabang kantor cabang baru di remote area menggunakan koneksi satelit/ISP lokal yang memberlakukan *UDP traffic throttling / blocking* ketat pada port non-standar. Tim devops melaporkan bahwa service `cloudflared` gagal online dan terus menerus berada pada status *crash-loop backoff*, sehingga sistem logistik internal tidak bisa diakses dari kantor pusat.
- **Pertanyaan**: Jelaskan akar penyebab masalah teknis ini berdasarkan arsitektur default `cloudflared`. Berikan parameter konfigurasi command-line atau systemd override file spesifik untuk memaksa daemon beroperasi secara stabil melintasi ISP tersebut!

### Skenario 3: Penyelundupan Data (Data Exfiltration) melalui Kueri DNS
Tim Keamanan Siber mendeteksi adanya anomali DNS Tunneling dari mesin developer internal, di mana malware mengekstrak data sensitif dengan menyematkan payload base64 ke dalam subdomain query (misal: `data-chunk-01.a83bf82.attacker-domain.com`).
- **Pertanyaan**: Bagaimana Anda mengonfigurasi Cloudflare Gateway (DNS Filtering & HTTP Filtering) dan profil klien WARP untuk mendeteksi, mencegat, dan menghentikan metode kebocoran data semacam ini secara otomatis di edge?

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**"Perancangan Arsitektur ZTNA Perusahaan Finansial Multi-Environment dengan Automated Provisioning & Posture Validation"**

### Target Spesifikasi:
Anda diminta merancang cetak biru konfigurasi lengkap (Terraform HCL + Cloudflared YAML + Skrip Posture Validation) dengan kriteria:
1. **Dua Komponen Layanan**:
   - `admin-api.corp.internal` -> Meneruskan traffic ke service lokal port `8080`.
   - `metrics.corp.internal` -> Meneruskan traffic ke Prometheus monitoring internal port `9090`.
2. **Access Security Rules**:
   - Hanya pengguna dengan domain email `@fintech.internal` yang diizinkan login.
   - Autentikasi multi-faktor wajib aktif melalui penyedia identitas.
   - Wajib lolos Posture Check: Sistem Operasi wajib Linux atau macOS, client WARP aktif, dan Country asal adalah Indonesia (`ID`).
3. **High Availability Daemon**:
   - Konfigurasi `config.yml` harus siap mendukung multi-daemon clustering (redundansi 2 node).
4. **JWT Verification Snippet**:
   - Sertakan kode program (Python/Node/Go) mini reverse-proxy atau middleware yang memvalidasi header `Cf-Access-Jwt-Assertion` menggunakan public key Cloudflare sebelum memproses request ke origin.

---

## Kunci Jawaban Singkat & Panduan Penilaian

### Kunci Bagian 1:
1. **B** - Daemon menginisiasi koneksi keluar (outbound) ke edge; origin firewall dapat menutup total port inbound (`deny all incoming`).
2. **C** - QUIC (UDP port 7844) adalah protokol bawaan utama, dengan fallback ke HTTP/2.
3. **B** - Header `Cf-Access-Jwt-Assertion` disematkan dan berisi data identitas pengguna bertanda tangan kriptografis.
4. **A** - Access berfokus pada gerbang masuk inbound aplikasi private; Gateway berfokus pada pengawasan outbound pengguna ke web.
5. **C** - Ingress rule wajib diakhiri dengan `- service: http_status:404`.

### Kunci Bagian 2 (Poin Kunci Penilaian):
6. **JWKS**: Cloudflare mempublikasikan public key di endpoint certs. Origin mendownload dan mencache public key ini. Saat request datang dengan JWT, origin memverifikasi tanda tangan RSA/ECDSA secara offline tanpa memanggil API Cloudflare, memastikan integritas klaim tanpa menambah overhead latensi jaringan.
7. **Split Tunneling**:
   - *Exclude Mode*: Default semua masuk WARP. Risiko: Latensi tinggi untuk traffic streaming/gaming umum, beban bandwidth tinggi pada gateway.
   - *Include Mode*: Hanya IP/CIDR privat yang dialihkan ke WARP. Keamanan: Traffic umum langsung ke ISP lokal tanpa inspeksi korporat, namun latensi publik lebih optimal dan privasi personal pengguna non-kerja terjaga.
8. **Origin SSL Self-Signed**:
   Tambahkan blok berikut pada rule ingress:
   ```yaml
   originRequest:
     noTLSVerify: true
     # atau sematkan custom CA certificate:
     # caPool: /etc/ssl/certs/internal-ca.pem
   ```
9. **TLS Decryption**: Cloudflare Edge bertindak sebagai man-in-the-middle resmi. Browser klien membuka sesi TLS ke Cloudflare, Cloudflare mendekripsi untuk inspeksi L7, lalu Cloudflare membuka sesi TLS terpisah ke web tujuan. Tanpa instalasi Root CA Cloudflare di OS/Browser klien, browser akan membunyikan alarm keamanan `Untrusted Certificate Authority / SSL Interception Alert`.
10. **Posture Event Lifecycle**:
    Client WARP lokal memindai status BitLocker/FileVault -> Mengirim telemetri terenkripsi ke Cloudflare Edge secara periodik -> Edge Policy Engine mendeteksi flag `encryption: false` -> Token sesi ZTNA dicabut/di-blacklist -> Request HTTP/TCP berikutnya dari klien langsung di-drop dengan halaman penolakan (*Access Denied: Non-compliant device*).

---