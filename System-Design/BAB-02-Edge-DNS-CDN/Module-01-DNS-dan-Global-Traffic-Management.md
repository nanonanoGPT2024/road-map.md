# MODULE 01: DNS & Global Traffic Management

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Menjelaskan hierarki dan alur resolusi **Domain Name System (DNS)** dari browser hingga *Authoritative Nameserver*.
2. Mengonfigurasi dan membedakan jenis DNS Record: **A, AAAA, CNAME, ALIAS/ANAME, MX, TXT, dan NS**.
3. Menganalisis trade-off pengaturan **Time-To-Live (TTL)** terhadap kecepatan migrasi server vs beban query.
4. Menerapkan strategi routing lalu lintas global: **GeoDNS**, **Latency-Based Routing**, **Weighted Round-Robin**, dan **Anycast BGP Routing**.
5. Menjalankan simulasi resolusi DNS berjenjang dan mitigasi kegagalan DNS menggunakan hands-on script.

---

## 2. Prerequisite
- Memahami konsep dasar protokol IP (IPv4 & IPv6) dan port jaringan (UDP Port 53).
- Telah menyelesaikan seluruh modul pada [BAB 01: Fondasi Skalabilitas & Metrik Sistem](../BAB-01-Fondasi-Skalabilitas/).

---

## 3. Concept
**Domain Name System (DNS)** adalah "buku telepon" dari internet. Manusia mengingat nama host yang mudah dibaca (seperti `api.tokopedia.com`), sedangkan mesin jaringan komputer hanya dapat berkomunikasi menggunakan alamat biner numerik IP (*Internet Protocol*, seperti `103.24.56.78` atau `2404:6800:4003::200e`).

Dalam System Design tingkat lanjut, DNS bukan sekadar penerjemah nama ke angka, melainkan **garis pertahanan pertama arsitektur routing lalu lintas global (*Global Server Load Balancing / GSLB*)**.

---

## 4. Why? (Mengapa Memahami DNS Krusial Bagi Arsitek?)

### 1. Titik Kontak Pertama (*First Point of Contact*)
Setiap HTTP request, koneksi WebSocket, atau streaming video dimulai dengan DNS lookup. Jika DNS lookup Anda lambat (misal memakan waktu 300 ms karena cache miss dan jarak nameserver yang jauh), maka seluruh optimasi kode microservices Anda yang secepat 10 ms akan terasa sia-sia bagi pengguna.

### 2. Bencana Perubahan IP & Cache TTL
Jika server backend Anda mengalami insiden peretasan atau serangan DDoS dan Anda harus memindahkan traffic ke IP baru, sementara Anda memasang DNS TTL = 86.400 detik (24 jam), maka selama 24 jam ke depan sebagian besar pengguna Anda di seluruh dunia akan tetap diarahkan ke server yang rusak tersebut!

---

## 5. What? (Hierarki DNS & Jenis DNS Record)

### A. Hierarki Server DNS

```text
                               [ Root DNS Servers ]
                             (13 Logikal: a.root-servers.net s/d m)
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
             [ .com TLD Server ]                   [ .id TLD Server ]
                    │                                     │
                    ▼                                     ▼
        [ Authoritative Nameserver ]          [ Authoritative Nameserver ]
          (ns1.cloudflare.com)                  (ns1.idcloudhost.com)
                    │                                     │
                    ▼                                     ▼
             api.example.com                       layanan.co.id
           IP: 104.21.44.120                     IP: 103.11.22.33
```

1. **DNS Recursive Resolver (ISP / 1.1.1.1 / 8.8.8.8):** Server yang bertugas melakukan pencarian keliling (*recursive query*) atas nama browser Anda.
2. **Root Nameserver:** Mengarahkan query ke Top-Level Domain (TLD) yang sesuai berdasarkan akhiran domain.
3. **TLD Nameserver:** Mengelola domain berakhiran tertentu (`.com`, `.org`, `.id`, `.io`).
4. **Authoritative Nameserver:** Pemegang buku catatan asli (*source of truth*) dari domain Anda yang menyimpan file zona (*zone file*).

### B. Jenis-Jenis DNS Records Fundamental

| Record Type | Fungsi Utama | Contoh Value |
|---|---|---|
| **A** | Memetakan nama hostname ke alamat **IPv4** (32-bit) | `api.app.com -> 104.18.2.5` |
| **AAAA** | Memetakan nama hostname ke alamat **IPv6** (128-bit) | `app.com -> 2606:4700::6812:205` |
| **CNAME** | Membuat nama alias ke hostname lain (*Canonical Name*) | `www.app.com -> app.com` |
| **ALIAS / ANAME** | Memetakan root/apex domain (`app.com`) ke hostname lain tanpa melanggar RFC | `app.com -> my-elb-123.amazonaws.com` |
| **NS** | Menyatakan nameserver otoritatif yang berwenang untuk zona domain | `app.com -> ns1.aws.com` |
| **MX** | Menentukan server penerima email untuk domain | `app.com -> mail.google.com (Priority 10)` |
| **TXT** | Menyimpan teks arbitrer (validasi kepemilikan domain, SPF, DKIM) | `"v=spf1 include:_spf.google.com ~all"` |

---

## 6. How? (Alur Resolusi DNS Langkah-demi-Langkah)

```text
[ Browser ] ──(1. Cek Cache Lokal: Browser -> OS -> Hosts File)──▶ [ Ada? Gunakan Langsung ]
    │
    ▼ (Jika Cache Miss)
[ Recursive Resolver (ISP / Cloudflare 1.1.1.1) ]
    │
    ├──(2. Tanya: Siapa yang pegang ".com"?)──▶ [ Root Nameserver ]
    │◀──(Jawaban: TLD Server IP untuk .com)────┘
    │
    ├──(3. Tanya: Siapa yang pegang "tokopedia.com"?)──▶ [ .com TLD Server ]
    │◀──(Jawaban: Authoritative Nameserver IP)──────────┘
    │
    ├──(4. Tanya: Berapa IP "api.tokopedia.com"?)──────▶ [ Authoritative Nameserver ]
    │◀──(Jawaban: 103.24.56.78, TTL = 300)──────────────┘
    │
    ▼ (5. Simpan di Resolver Cache & Kembalikan ke OS)
[ Browser memulai koneksi TCP Handshake ke IP 103.24.56.78:443 ]
```

---

## 7. Analogy: Mencari Alamat Kantor Perusahaan
- **Browser:** Anda ingin mengirim dokumen ke kantor "PT Maju Terus".
- **OS Cache:** Anda memeriksa buku agenda pribadi Anda (apakah alamat sudah dicatat?).
- **Recursive Resolver:** Anda menyewa kurir pribadi dan memintanya: *"Tolong carikan alamat PT Maju Terus sampai ketemu."*
- **Root Nameserver:** Kurir pergi ke Departemen Perizinan Pusat. Resepsionis pusat berkata: *"Untuk perusahaan di Indonesia berakhiran PT, tanyakan ke Gedung Kementerian Hukum."*
- **TLD Nameserver:** Kurir ke Gedung Kemenkum. Petugas berkata: *"Berkas PT Maju Terus dipegang oleh Notaris Handoko di Jalan Sudirman."*
- **Authoritative Nameserver:** Kurir mendatangi kantor Notaris Handoko. Notaris membuka arsip resmi dan memberikan alamat persisnya: *"Gedung Wisma Mulia Lantai 15, Jakarta."*

---

## 8. Diagram: Mekanisme Global Traffic Routing

### A. GeoDNS (Geolocation Routing)
DNS mengidentifikasi lokasi geografis IP dari Recursive Resolver pengguna, lalu mengembalikan IP data center terdekat.

```text
                       [ Authoritative GeoDNS ]
                                  │
                 ┌────────────────┴────────────────┐
                 ▼ (User dari Asia)                ▼ (User dari Eropa)
         IP: 103.24.56.10                  IP: 185.12.34.88
       [ Data Center Singapore ]         [ Data Center Frankfurt ]
```

### B. Anycast DNS Routing
Alih-alih mengandalkan software DNS untuk memilih IP, **Anycast** mengumumkan **SATU ALAMAT IP YANG SAMA** dari puluhan data center di seluruh penjuru dunia menggunakan protokol routing BGP (*Border Gateway Protocol*).

```text
          Pengguna di Tokyo ────────▶ [ IP: 1.1.1.1 di PoP Tokyo ]
          Pengguna di Sydney ───────▶ [ IP: 1.1.1.1 di PoP Sydney ]
          Pengguna di Frankfurt ────▶ [ IP: 1.1.1.1 di PoP Frankfurt ]
```
Router internet secara otomatis mengirimkan paket ke node data center terdekat secara topologi jaringan fisik. Inilah teknologi yang membuat DNS Cloudflare (`1.1.1.1`) dan Google (`8.8.8.8`) merespon dalam waktu < 5 milidetik di seluruh dunia.

---

## 9. Simple Example: Trade-off Pengaturan TTL

```text
+-------------------------------------------------------------------------------+
| SHORT TTL (misal: 60 detik)                                                   |
| - Kelebihan: Sangat lincah. Jika IP server diubah, user akan beralih dalam 1  |
|              menit (cocok untuk migrasi, blue-green deployment, dan DR).      |
| - Kekurangan: Cache cepat hangus, beban query DNS naik drastis.               |
+-------------------------------------------------------------------------------+
| LONG TTL (misal: 86.400 detik / 24 jam)                                       |
| - Kelebihan: Latensi super cepat (selalu cache hit), beban DNS server nol.   |
| - Kekurangan: Sangat kaku. Jika server down dan IP diganti, user tetap nyasar |
|               ke IP lama hingga 24 jam ke depan.                              |
+-------------------------------------------------------------------------------+
```

---

## 10. Practical Code Example
Lihat demonstrasi pelacakan alur hierarki DNS dan kalkulasi waktu kadaluwarsa cache TTL pada:
`System-Design/BAB-02-Edge-DNS-CDN/hands-on/m01/dns_lookup_tracer.js`

---

## 11. Real World Example: Migrasi Zero Downtime Spotify & Kasus Dyn DDoS (2016)
- **Strategi Migrasi Spotify:** Sebelum memindahkan jutaan pengguna antar-cloud provider, 7 hari sebelumnya tim engineer menurunkan nilai TTL dari 24 jam menjadi **60 detik**. Saat hari-H migrasi, perubahan IP diarahkan secara bertahap, dan dalam waktu 60 detik seluruh traffic global berpindah dengan mulus tanpa downtime. Setelah stabil, TTL dinaikkan kembali ke 24 jam.
- **Serangan DDoS Dyn DNS (2016):** Hacker membombardir server Authoritative DNS provider Dyn menggunakan botnet Mirai (ratusan ribu perangkat CCTV/IoT). Akibatnya: Twitter, Netflix, Reddit, dan GitHub lumpuh bersamaan di seluruh pantai timur AS, **bukan karena server Twitter/Netflix mati**, melainkan karena browser pengguna tidak bisa menemukan IP address mereka!

---

## 12. Trade-offs (GeoDNS vs Anycast BGP)

| Karakteristik | GeoDNS Routing | Anycast BGP Routing |
|---|---|---|
| **Lapisan Pengoperasian** | Application Layer (DNS Level) | Network Layer (BGP Routing / IP Level) |
| **Akurasi Lokasi** | Mengikuti IP resolver (bisa meleset jika user pakai VPN) | Alami mengikuti topologi routing internet terdekat |
| **Mitigasi DDoS** | Rentan overload jika nameserver ditarget | Menyerap traffic serangan secara terdistribusi di ratusan edge node |
| **Kompleksitas Biaya** | Murah (bisa diatur di AWS Route 53 / Cloudflare) | Sangat mahal (butuh ASN sendiri dan blok IP /24) |
| **Penyimpanan State** | Cocok untuk mengarahkan ke origin spesifik | Sulit untuk protokol stateful TCP jangka panjang |

---

## 13. When To Use What
- **Gunakan CNAME:** Untuk mengarahkan subdomain (seperti `blog.perusahaan.com` ke platform hosted seperti `perusahaan.hashnode.dev`).
- **Gunakan ALIAS / ANAME:** Jika Anda menggunakan Cloud Load Balancer (seperti AWS ALB) pada apex/root domain (`perusahaan.com`), karena spesifikasi RFC 1034 melarang CNAME pada root domain.
- **Gunakan Multi-Record A (DNS Round-Robin):** Sebagai bentuk load balancing paling primitif dan murah untuk membagi beban ke beberapa server web tanpa hardware load balancer terpisah.

---

## 14. When NOT To Use
- **Jangan gunakan DNS Round-Robin sebagai satu-satunya Load Balancer produksi:** DNS tidak memiliki mekanisme *Health Checking* real-time. Jika Server 1 crash, DNS server tetap akan membagikan IP Server 1 ke 50% pengguna Anda sampai Anda menghapus record tersebut secara manual!

---

## 15. Common Mistakes
1. **CNAME Flattening Violation:** Mencoba menambahkan CNAME pada root apex domain (`example.com`) yang memiliki MX record. Ini akan merusak penerimaan email perusahaan!
2. **Tidak Mengurangi TTL Sebelum Migrasi:** Mengubah IP server produksi saat TTL masih bernilai 86.400 detik.
3. **Mengabaikan EDNS Client Subnet (ECS):** Pengguna di Jakarta menggunakan Public DNS Google `8.8.8.8` yang resolver pusatnya berada di Singapura. Tanpa ekstensi ECS, GeoDNS akan mengira pengguna berada di Singapura dan mengarahkannya ke server data center Singapura alih-alih data center lokal Jakarta!

---

## 16. Best Practices

- **Must Have:**
  - Gunakan minimal **2 Authoritative Nameserver independen** di zona/provider jaringan berbeda.
  - Setel TTL rendah (300 detik / 5 menit) untuk service yang sering diperbarui, dan TTL tinggi (86.400 detik) untuk domain statis.
- **Recommended:**
  - Pasang proteksi **DNSSEC** (*DNS Security Extensions*) untuk mencegah serangan pemalsuan alamat (*DNS Cache Poisoning / Spoofing*).
  - Manfaatkan Managed DNS Provider global yang mendukung Anycast (Cloudflare, AWS Route 53, NS1).
- **Advanced:**
  - Terapkan **Weighted Latency-Based Routing** untuk pengujian rilis Canary (95% traffic ke IP cluster v1, 5% traffic ke IP cluster v2).
- **Avoid / Overengineering:**
  - Membangun dan mengelola server BIND DNS sendiri di VPS Linux untuk production enterprise, alih-alih menggunakan Cloud Managed DNS berkeandalan 100% SLA.

---

## 17. Troubleshooting Guide
```text
Gejala: Record DNS sudah diganti di dashboard, tetapi sebagian komputer masih mengakses IP lama.
--------------------------------------------------------------------------------------------
Kemungkinan Akar Masalah:
1. Cache OS Lokal masih menyimpan record lama sesuai sisa TTL.
2. ISP Lokal (Telkom/FirstMedia) melakukan "DNS Cache Overriding" (mengabaikan TTL pendek).
3. Browser memiliki internal DNS cache sendiri (seperti Chrome chrome://net-internals/#dns).

Cara Diagnosa:
- Cek langsung ke Authoritative Nameserver (bypass cache ISP):
  dig @ns1.cloudflare.com api.domain.com +nocmd +noall +answer
- Cek apa yang dilihat oleh Resolver ISP Anda:
  nslookup api.domain.com

Solusi:
- Flush cache OS:
  - Windows: ipconfig /flushdns
  - macOS: sudo killall -HUP mDNSResponder
- Flush socket pool pada browser.
```

---

## 18. Hands-on Lab: Simulator Resolusi DNS & Perhitungan Cache TTL

File lab sudah disiapkan di:
`System-Design/BAB-02-Edge-DNS-CDN/hands-on/m01/dns_lookup_tracer.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-02-Edge-DNS-CDN/hands-on/m01/dns_lookup_tracer.js
```

### Yang Ditampilkan Script Ini:
1. Menyimulasikan siklus pencarian 4 lapis: Browser Cache -> OS Cache -> Recursive Resolver -> Authoritative Nameserver.
2. Menghitung penalti latensi saat terjadi *Cold Cache Miss* (~150ms) vs *Hot Cache Hit* (0ms).
3. Menyimulasikan pergantian IP dengan masa transisi *TTL Expiration Countdown*.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan fungsi dari A Record dan CNAME Record, serta jelaskan mengapa kita tidak boleh memasang CNAME pada root apex domain (`domainanda.com`)!

### Level 2 (Medium):
Sebuah startup e-commerce berencana melakukan migrasi server dari Provider A (IP: `1.2.3.4`) ke Provider B (IP: `5.6.7.8`) pada hari Sabtu pukul 00:00. Nilai TTL domain saat ini adalah 86.400 detik (24 jam).
1. Langkah apa yang wajib dilakukan tim DevOps pada hari Kamis (2 hari sebelum migrasi)?
2. Mengapa langkah tersebut krusial untuk mencegah downtime?

### Level 3 (Hard):
Jelaskan cara kerja **Anycast BGP Routing** dalam menangani serangan DDoS volumetric 1 Terabit/detik pada infrastruktur DNS global seperti Cloudflare atau Root DNS! Mengapa arsitektur Unicast konvensional akan langsung tumbang menerima volume serangan sebesar itu?

---

## 20. Summary & Knowledge Check
- [ ] Memahami hierarki DNS: Root Servers -> TLD Servers -> Authoritative Nameservers.
- [ ] Memahami fungsi A, AAAA, CNAME, ALIAS, MX, dan TXT Record.
- [ ] Menguasai trade-off matematis dan operasional pemilihan nilai **TTL**.
- [ ] Mampu membedakan strategi routing **GeoDNS** vs **Anycast BGP**.
- [ ] Mampu melakukan diagnosa masalah DNS menggunakan tools CLI (`dig`, `nslookup`, `flushdns`).
