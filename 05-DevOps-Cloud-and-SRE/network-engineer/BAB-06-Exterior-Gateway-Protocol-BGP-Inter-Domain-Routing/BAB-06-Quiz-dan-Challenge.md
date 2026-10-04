# BAB 06: Quiz dan Challenge - Exterior Gateway Protocol (BGP)

## 1. Basic Questions (Pilihan Ganda & Analisis Pendek)

### Q1. Apa tujuan utama dari atribut BGP `AS_PATH` dalam sesi eBGP?
a) Menghitung delay milidetik antar router tetangga.  
b) Mencegah inter-domain routing loops dan mengukur panjang hop otonom.  
c) Mengenkripsi payload paket data saat transit di ISP publik.  
d) Mengatur alokasi bandwidth interface peering secara dinamis.

**Jawaban:** **b**  
**Pembahasan:** Atribut `AS_PATH` adalah *well-known mandatory attribute*. Dalam eBGP, jika router mendeteksi ASN lokalnya sendiri berada di dalam daftar `AS_PATH` dari update yang diterima, router akan langsung membuang rute tersebut untuk mencegah loop perutean. Selain itu, panjang string `AS_PATH` digunakan pada tahap ke-4 algoritma Best Path Selection.

---

### Q2. Manakah nilai BGP Path Attribute berikut yang TIDAK PERNAH dikirimkan ke peer eBGP tetangga?
a) AS-Path  
b) MED  
c) Local Preference  
d) Origin Code  

**Jawaban:** **c**  
**Pembahasan:** Atribut `LOCAL_PREF` adalah *well-known discretionary attribute* yang bersifat non-transitive di luar AS. Nilai ini hanya dikirimkan di dalam batas Autonomous System lokal antar-peer iBGP.

---

### Q3. Secara default, apa yang dilakukan oleh router edge BGP terhadap atribut `NEXT_HOP` saat meneruskan rute yang diterima dari peer eBGP ke peer internal iBGP?
a) Mengubahnya menjadi alamat IP interface loopback lokal.  
b) Menghapus atribut NEXT_HOP dari pesan UPDATE.  
c) Tidak mengubahnya sama sekali (mempertahankan IP address peer eBGP asli).  
d) Menggantinya menjadi `0.0.0.0`.

**Jawaban:** **c**  
**Pembahasan:** Perilaku default iBGP tidak mengubah nilai `NEXT_HOP` yang diterima dari eBGP. Inilah yang mendasari pentingnya perintah `neighbor <ip> next-hop-self` pada edge router agar internal core iBGP router dapat menyelesaikan rute tersebut via IGP.

---

### Q4. Dalam format penulisan BGP Extended Community atau Standard RFC 1997, apa arti dari Community `NO_EXPORT` (`0xFFFFFF01`)?
a) Rute tidak boleh diiklankan ke peer eBGP di luar AS lokal atau confederation.  
b) Rute tidak boleh disimpan di dalam BGP routing table.  
c) Rute tidak boleh diteruskan ke router internal iBGP manapun.  
d) Rute dibuang secara otomatis dari sistem operasi router.

**Jawaban:** **a**  
**Pembahasan:** `NO_EXPORT` menginstruksikan router penerima untuk menyebarkan rute hanya di dalam batas AS lokal (atau sub-AS konfederasi), dan dilarang keras mengumumkannya ke luar ke peer eBGP publik.

---

### Q5. Jika sebuah router menerima rute BGP dengan status validasi RPKI bertanda `Invalid`, apa arti kriptografis dari status tersebut?
a) Router tidak dapat menghubungi RPKI Cache Validator melalui protokol RTR.  
b) Prefix belum pernah didaftarkan ROA-nya oleh pemilik IP di RIR database.  
c) Ditemukan ROA valid untuk prefix tersebut, tetapi diumumkan oleh Origin ASN yang salah, atau mask prefix lebih spesifik dari `MaxLength`.  
d) Kunci publik router lokal telah kedaluwarsa (expired).

**Jawaban:** **c**  
**Pembahasan:** Status `Invalid` menyatakan bahwa ROA definitif ditemukan dalam database RPKI untuk prefix bersangkutan, namun atribut iklan BGP bertentangan dengan isi ROA (baik ASN pengirim tidak cocok maupun panjang prefix melanggar batas `MaxLength`).

---

## 2. Intermediate Questions (Evaluasi Arsitektural)

### Q6. Analisis Best Path Selection
Diberikan tabel BGP untuk prefix `203.0.113.0/24` pada Router Core:

| Jalur Kandidat | Weight | Local Pref | AS-Path | Origin | MED | Neighbor Type | IGP Metric to Next-Hop |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Path 1** | 0 | 150 | 64500 64501 64502 | IGP | 0 | eBGP | 10 |
| **Path 2** | 0 | 150 | 64500 64501 | Incomplete | 0 | eBGP | 20 |
| **Path 3** | 0 | 200 | 64500 64501 64502 64503 | IGP | 100 | iBGP | 5 |

Rute mana yang akan dipilih sebagai BGP Best Path (`*>`)? Tuliskan urutan tie-breaker yang mengeliminasi kandidat lainnya!

**Jawaban & Pembahasan:**  
**Pemenang: Path 3.**  
**Langkah Evaluasi Algoritma:**
1. Evaluasi **Weight**: Path 1, 2, dan 3 imbang (semua bernilai 0).
2. Evaluasi **Local Preference**:
   - Path 1: 150
   - Path 2: 150
   - **Path 3: 200**
3. Karena Path 3 memiliki Local Preference tertinggi (200 > 150), Path 1 dan Path 2 **langsung tereliminasi** pada tahap ini.
4. Parameter AS-Path, Origin, MED, Neighbor Type, dan IGP metric tidak perlu dievaluasi lagi karena pemenang sudah diputuskan secara mutlak di langkah kedua.

---

### Q7. Mekanisme Anti-Loop pada Route Reflector
Ketika Route Reflector (RR) memantulkan rute ke sesama iBGP client, aturan *iBGP Split Horizon* dilonggarkan. Jelaskan secara teknis bagaimana RR menjamin tidak terjadi *routing loop* permanen di dalam AS menggunakan atribut `ORIGINATOR_ID` dan `CLUSTER_LIST`!

**Jawaban & Pembahasan:**  
1. **ORIGINATOR_ID (RFC 4456):** Atribut berukuran 4-byte opsional non-transitif yang dibuat oleh RR pertama saat memantulkan rute. Atribut ini diisi dengan BGP Router ID dari router yang pertama kali menginjeksi rute ke dalam AS. Jika sebuah router menerima update BGP yang mengandung `ORIGINATOR_ID` miliknya sendiri, rute tersebut segera diabaikan dan dibuang.
2. **CLUSTER_LIST (RFC 4456):** Barisan urutan nilai `Cluster ID` dari setiap RR cluster yang dilintasi rute. Sebelum RR memantulkan rute, ia memeriksa `CLUSTER_LIST`. Jika `Cluster ID` lokalnya sudah tercantum di dalam list, RR mendeteksi bahwa paket update tersebut telah berputar kembali ke cluster asalnya (*loop*), sehingga rute langsung ditolak.

---

### Q8. Evaluasi RPKI MaxLength Vulnerability
Sebuah organisasi memegang prefix `192.0.2.0/23`. Network Administrator mendaftarkan ROA dengan:
- `ASN: 65001`
- `Prefix: 192.0.2.0/23`
- `MaxLength: 24`

Penyerang membajak rute dengan mengumumkan `192.0.2.0/24` menggunakan ASN palsu `65666`. Apa status validasi RPKI-nya? Jika penyerang mengumumkan `192.0.2.128/25` dari ASN terdaftar `65001`, apa status validasi RPKI-nya?

**Jawaban & Pembahasan:**  
1. Kasus pertama (`192.0.2.0/24` via ASN `65666`): Status = **INVALID**. Meskipun mask `/24` memenuhi kriteria `MaxLength: 24`, origin ASN pengumum (`65666`) bertentangan dengan ASN yang terotorisasi dalam ROA (`65001`).
2. Kasus kedua (`192.0.2.128/25` via ASN `65001`): Status = **INVALID**. Meskipun Origin ASN cocok (`65001`), panjang prefix `/25` melebihi batas toleransi `MaxLength: 24` yang disahkan.

---

### Q9. BGP Asymmetric Routing & Ingress Traffic Engineering
Mengapa metode *BGP Communities* dinilai jauh lebih superior dan deterministik dibandingkan metode *AS-Path Prepending* ketika melakukan Ingress Traffic Engineering ke Tier-1 Transit Provider global?

**Jawaban & Pembahasan:**  
*AS-Path Prepending* hanya memanipulasi langkah ke-4 algoritma Best Path (panjang AS-Path). Namun, pada arsitektur router ISP upstream (Tier-1/Tier-2), atribut **Local Preference** (langkah ke-2) dievaluasi jauh sebelum AS-Path. Banyak ISP mengonfigurasi Local Preference lebih tinggi pada rute pelanggan (*Customer*) dibanding rute antar rekanan (*Peer*). Akibatnya, seberapa banyak pun kita menambahkan prepend, ISP upstream tetap akan mengalirkan traffic ke jalur prepend tersebut jika Local Preference mereka mengaturnya demikian. Sebaliknya, **BGP Communities** mengirimkan sinyal langsung ke policy engine ISP upstream untuk menurunkan *Local Preference* mereka sendiri terhadap prefix kita (misalnya: tag `64500:80` untuk set Local_Pref ISP ke 80), menjadikannya deterministik mutlak.

---

### Q10. Penyebab Sesi BGP Tertahan pada State "Active"
Apa arti teknis jika output perintah `show ip bgp summary` menunjukkan neighbor BGP Anda berada dalam state `Active`, dan faktor apa saja yang menyebabkannya?

**Jawaban & Pembahasan:**  
State `Active` dalam finite state machine (FSM) BGP **bukan** berarti sesi sedang aktif berjalan lancar, melainkan router sedang **secara aktif mencoba menginisiasi TCP 3-way handshake (port 179)** ke neighbor, namun gagal atau ditolak.  
**Faktor Penyebab:**
1. Masalah konektivitas Layer 3: Router tidak memiliki rute IP menuju alamat tetangga.
2. Firewall/ACL memblokir paket TCP port 179.
3. Alamat IP neighbor yang dikonfigurasi salah ketik (*misconfigured IP*).
4. Sisi lawan belum mengonfigurasi IP router lokal sebagai neighbor atau BGP daemon mati di remote peer.
5. Pada iBGP multihop atau peering loopback, perintah `update-source` lupa dikonfigurasi, sehingga IP sumber TCP handshake menggunakan IP interface fisik yang tidak dikenal oleh peer.

---

## 3. Scenario-Based Questions (Studi Kasus Industri)

### Skenario 1: Insiden BGP Route Leak pada Multi-Homed FinTech
Sebuah perusahaan FinTech (ASN 65200) berlangganan dua ISP: ISP-Indo (AS 64500) dan ISP-Global (AS 64501). Suatu hari, koneksi internet di seluruh Asia Tenggara melambat drastis dan traffic ISP-Indo menuju ISP-Global melonjak 10 Gbps melintasi router edge FinTech, menyebabkan router edge crash (*CPU 100%*).  
1. Identifikasi insiden apa yang terjadi dan mengapa traffic ISP luar bisa melintasi router internal FinTech!
2. Tuliskan blok route-map perbaikan untuk mencegah insiden tersebut terjadi kembali!

**Jawaban Solusi Skenario 1:**
1. **Analisis Insiden:** Terjadi insiden **BGP Route Leak**. Router FinTech menerima full internet routing table dari ISP-Indo, lalu secara tidak sengaja mengiklankan kembali rute-rute internet tersebut ke ISP-Global karena tidak ada *Outbound Route Filter*. Akibatnya, ISP-Global menganggap AS 65200 (FinTech) adalah jalur transit valid untuk menuju rute-rute milik ISP-Indo. Jaringan FinTech berubah menjadi *unintended transit provider*.
2. **Konfigurasi Remediasi:** Pasang filter outbound ketat yang HANYA mengizinkan prefix milik FinTech sendiri yang diumumkan keluar:
```text
ip prefix-list OWN-CIDR permit 198.51.100.0/22 le 24

route-map RM-BGP-OUT-HARDENED permit 10
 match ip address prefix-list OWN-CIDR
! Tolak semua prefix lainnya (Default Deny Implicit)
route-map RM-BGP-OUT-HARDENED deny 99

router bgp 65200
 neighbor 203.0.113.1 route-map RM-BGP-OUT-HARDENED out
 neighbor 198.51.100.254 route-map RM-BGP-OUT-HARDENED out
```

---

### Skenario 2: BGP Hijacking Melalui Subnet Lebih Spesifik
Sebuah institusi perbankan mengumumkan prefix legal `198.18.0.0/15` melalui ASN `65300`. Seorang penyerang di negara lain mengumumkan `198.18.0.0/24` dan `198.18.1.0/24` melalui ASN `65999`. Seketika 100% traffic nasabah bank terarah ke server penyerang.  
1. Mengapa manipulasi atribut seperti AS-Path Prepending atau Local Preference di router bank sama sekali tidak berdaya melawan serangan ini?
2. Bagaimana RPKI Route Origin Validation (ROV) secara teknis dapat melumpuhkan serangan ini pada level ISP upstream?

**Jawaban Solusi Skenario 2:**
1. **Penyebab Kegagalan BGP Attributes:** Aturan fundamental IP routing menetapkan bahwa **Longest Prefix Match (LPM)** dievaluasi di level Forwarding Information Base (FIB) SEBELUM protokol routing mengevaluasi atribut BGP. Prefix `/24` selalu menang mutlak melawan supernet `/15`, tanpa mempedulikan AS-Path yang panjang, Local Preference, maupun metrik BGP lainnya.
2. **Solusi via RPKI ROV:** Bank menerbitkan ROA resmi di RIR untuk prefix `198.18.0.0/15` dengan `ASN: 65300` dan parameter ketat `MaxLength: 15`. Ketika penyerang mengumumkan `/24`, router ISP upstream yang mengaktifkan RPKI ROV mengevaluasi mask `/24` terhadap `MaxLength: 15`. Rute penyerang seketika berstatus **INVALID**. ISP yang patuh pada standar MANRS akan langsung men-drop status `Invalid`, sehingga pengumuman palsu penyerang dieliminasi dari Internet Routing Table global.

---

### Skenario 3: BGP Next-Hop Unreachable pada Peering iBGP Loopback
Sebuah ISP regional mengonfigurasi iBGP antar Router Edge-1 dan Core-RR menggunakan alamat Loopback. Sesi BGP sukses berstatus `Established`, dan rute internet eksternal berhasil diterima oleh Core-RR. Namun, saat host di belakang Core-RR melakukan ping ke destinasi internet, paket langsung dibuang (*packet drop*).
1. Lakukan root cause analysis pada BGP routing table di Core-RR!
2. Solusi konfigurasi apa yang harus diterapkan pada Edge-1?

**Jawaban Solusi Skenario 3:**
1. **Root Cause Analysis:** Edge-1 menerima rute dari peer eBGP eksternal dengan atribut `NEXT_HOP` berupa IP interface point-to-point eBGP ISP eksternal (misal: `203.0.113.1`). Saat Edge-1 meneruskan rute ini ke Core-RR via iBGP, perilaku default iBGP mempertahankan `NEXT_HOP` asli (`203.0.113.1`). Core-RR tidak menjalankan eBGP dan di dalam tabel IGP internal (OSPF/IS-IS) tidak ada rute untuk mencapai subnet peering eksternal `203.0.113.0/30`. Akibatnya, status rute di Core-RR menjadi *Inaccessible Next-Hop*, sehingga rute tidak diinstal ke tabel kernel/FIB.
2. **Solusi Konfigurasi:** Edge-1 wajib mengonfigurasi perintah `next-hop-self` pada sesi iBGP ke Core-RR:
```text
router bgp 65000
 neighbor <IP-LOOPBACK-CORE-RR> next-hop-self
```
Ini memaksa Edge-1 mengubah atribut `NEXT_HOP` rute menjadi alamat Loopback miliknya sendiri, yang dapat dijangkau oleh Core-RR melalui IGP internal.

---

## 4. Practical Chapter Challenge: Enterprise Dual-Homed Internet Gateway

### Objektif Arsitektur
Anda adalah Principal Network Architect untuk e-Commerce Tier-1. Bangun konfigurasi komprehensif pada edge router (`Edge-GW-01`, ASN: `65500`) yang memenuhi persyaratan industri berikut:
1. Peering eBGP ke **ISP-Prime (AS 64600)** pada interface `eth1` (`198.51.100.1/30`) dan **ISP-Secondary (AS 64700)** pada interface `eth2` (`203.0.113.1/30`).
2. Menerapkan skema **RPKI Route Origin Validation** via RTR cache server lokal di IP `10.254.0.10:8282`:
   - Rute bertanda `Invalid` harus di-drop mutlak (`deny`).
   - Rute bertanda `Valid` diberi Local Preference `200` (untuk ISP-Prime) dan `150` (untuk ISP-Secondary).
   - Rute bertanda `NotFound` diberi Local Preference `100` (ISP-Prime) dan `90` (ISP-Secondary).
3. Melakukan **Inbound Traffic Engineering**: Prefix publik perusahaan `198.51.100.0/22` diumumkan ke kedua provider, namun pada ISP-Secondary ditambahkan `AS-Path Prepend` sebanyak 2 kali lipat agar return traffic memprioritaskan ISP-Prime.
4. Melindungi router dari route exhaustion dengan membatasi maksimum rute yang diterima dari ISP-Secondary maksimal 10.000 prefix (peringatan di 80%).

### File Jawaban Template Konfigurasi yang Harus Dihasilkan:
Simpan dan jalankan arsitektur tersebut sesuai template FRR / Arista yang disertakan pada hands-on modul ini.

---