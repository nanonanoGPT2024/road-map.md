# Evaluasi Bab 07: Layanan Infrastruktur Inti Jaringan

---

## 1. Basic Questions (5 Soal)

### Soal 1
Pada format transmisi protokol Syslog, jika nilai integer field `<PRI>` adalah **165**, berapakah nilai numerik *Facility* dan *Severity* pesan tersebut? Tunjukkan langkah kalkulasi matematisnya!

### Soal 2
Sebutkan port transport Layer 4 (UDP/TCP) default beserta peruntukannya untuk kelima protokol berikut:
1. DNS (Standard Client Query)
2. DHCP (Client to Server & Server to Client)
3. NTP
4. SNMPv3 (Manager Polling vs Agent Notification/Trap)
5. Secure Syslog (TLS)

### Soal 3
Jelaskan perbedaan mendasar antara **Recursive DNS Resolver** dan **Authoritative DNS Nameserver** dalam siklus penemuan IP address!

### Soal 4
Apa peran field `giaddr` (Gateway IP Address) di dalam header paket DHCP ketika paket tersebut diproses oleh DHCP Relay Agent?

### Soal 5
Pada protokol SNMPv3 USM (*User-based Security Model*), sebutkan dan jelaskan 3 level keamanan (*Security Levels*) yang tersedia!

---

## Jawaban Basic Questions

### Jawaban 1
- Rumus dasar Syslog PRI: $\text{PRI} = (\text{Facility} \times 8) + \text{Severity}$
- Hitung Facility: $\text{Facility} = \lfloor 165 / 8 \rfloor = \mathbf{20}$ (berkaitan dengan `local4`).
- Hitung Severity: $\text{Severity} = 165 - (20 \times 8) = 165 - 160 = \mathbf{5}$ (berkaitan dengan `Notice`).
- **Hasil**: Facility = **20 (local4)**, Severity = **5 (Notice)**.

### Jawaban 2
1. **DNS**: UDP port 53 (kueri default) dan TCP port 53 (transfer zona / respons > 512 bytes).
2. **DHCP**: UDP port 68 (Client) dan UDP port 67 (Server/Relay).
3. **NTP**: UDP port 123.
4. **SNMPv3**: UDP port 161 (Polling: Get/Set) dan UDP port 162 (Trap/Inform).
5. **Secure Syslog**: TCP port 6514 (Syslog over TLS).

### Jawaban 3
- **Recursive Resolver**: Bertindak sebagai agen pencari atas nama klien. Resolver ini tidak memiliki rekaman zona target secara lokal, melainkan menelusuri hierarki internet (Root -> TLD -> Authoritative) hingga menemukan jawaban akhir dan menyimpannya di cache lokal.
- **Authoritative Nameserver**: Server target akhir yang secara resmi memegang file zona (*Zone File*) domain tersebut. Server ini memegang jawaban pasti (*A, AAAA, MX, dll.*) dan tidak melakukan kueri lanjutan ke server lain.

### Jawaban 4
Ketika host membroadcast DHCPDISCOVER, field `giaddr` bernilai `0.0.0.0`. Saat DHCP Relay Agent (router) meneruskan paket tersebut sebagai unicast ke DHCP Server, Relay Agent memasukkan alamat IP antarmuka ingress-nya ke dalam field `giaddr`. DHCP Server menggunakan nilai `giaddr` ini untuk menentukan subnet pool alamat IP mana yang harus dialokasikan kepada klien yang meminta.

### Jawaban 5
1. `noAuthNoPriv`: Tanpa mekanisme otentikasi identitas pengirim dan tanpa enkripsi data (komunikasi dikirim dalam teks biasa/plaintext).
2. `authNoPriv`: Menggunakan hashing kriptografi (MD5/SHA) untuk memvalidasi integritas data dan otentikasi identitas pengirim, namun data muatan (*payload*) tidak dienkripsi.
3. `authPriv`: Menyediakan tingkat keamanan penuh; otentikasi pengirim diverifikasi menggunakan hashing (SHA), dan muatan data dienkripsi menggunakan algoritma simetris (AES atau DES).

---

## 2. Intermediate Questions (5 Soal)

### Soal 1
Dalam rantai validasi DNSSEC (*Chain of Trust*), jelaskan secara detail korelasi teknis dan hierarki fungsional antara record **RRSIG**, **DNSKEY** (ZSK dan KSK), serta record **DS** (Delegation Signer)!

### Soal 2
Jelaskan mekanisme kerja **DHCP Option 82** (Relay Agent Information Option)! Apa fungsi dari sub-option *Circuit ID* dan *Remote ID*, serta bagaimana mekanisme ini mencegah serangan spoofing IP/MAC pada layer akses?

### Soal 3
Bagaimana algoritma NTP mengatasi kondisi **Clock Slew** versus **Clock Step**? Dalam kondisi infrastruktur seperti apa teknik *Clock Step* berbahaya jika dieksekusi secara tiba-tiba?

### Soal 4
Pada arsitektur SNMPv3, jelaskan fungsi dari **EngineID** dan apa dampak teknis yang terjadi pada sistem monitoring (NMS) jika dua perangkat switch jaringan yang berbeda memiliki nilai *EngineID* yang identik?

### Soal 5
Bandingkan karakteristik transmisi Syslog menggunakan **UDP port 514** versus **TCP/TLS port 6514** dalam skenario jaringan WAN yang mengalami fluktuasi paket loss dan kongesti tinggi. Sebutkan kelemahan sistemik masing-masing transport!

---

## Jawaban Intermediate Questions

### Jawaban 1
- **RRSIG**: Memuat tanda tangan digital atas kumpulan data DNS (*RRSet* seperti A record) yang di-generate menggunakan kunci privat ZSK (*Zone Signing Key*).
- **DNSKEY (ZSK & KSK)**: Berisi kunci publik. Klien memverifikasi RRSIG dari RRSet menggunakan ZSK publik. Sementara itu, ZSK publik itu sendiri ditandatangani menggunakan KSK (*Key Signing Key*) privat, menghasilkan RRSIG untuk DNSKEY.
- **DS Record**: Merupakan hash kriptografis dari KSK publik yang diunggah dan disimpan pada *parent zone* (misal: zona `.id` menyimpan DS milik `perusahaan.co.id`). Rantai ini membuktikan bahwa KSK yang digunakan oleh zona anak valid dan diakui secara sah oleh zona induk, membentuk rantai tak terputus hingga Root Trust Anchor.

### Jawaban 2
- DHCP Option 82 disisipkan oleh switch/relay perantara ke dalam frame DHCP sebelum mencapai server.
  - **Circuit ID**: Menyimpan data identitas port fisik dan VLAN tempat klien terhubung (contoh: `Port GigabitEthernet 0/1, VLAN 100`).
  - **Remote ID**: Menyimpan identifikasi unik switch fisik (misalnya Base MAC address switch atau Hostname).
- **Pencegahan Spoofing**: Server DHCP dapat mencocokkan apakah permintaan IP tertentu berasal dari port switch yang sah. Digabungkan dengan *DHCP Snooping* dan *IP Source Guard*, switch memblokir trafik IP dari port tersebut jika paket Layer 3 yang lewat tidak sesuai dengan IP/MAC/Port binding yang tercatat di tabel snooping.

### Jawaban 3
- **Clock Step**: Jam sistem diubah secara instan (*melompat*) langsung ke waktu baru.
- **Clock Slew**: NTP mempercepat atau memperlambat laju clock OS secara bertahap (maksimum penyesuaian lazimnya 0.5 ms per detik) hingga sinkron dengan referensi upstream.
- **Bahaya Step**: Pada sistem database relasional transaksional (seperti PostgreSQL/Oracle/Spanner), platform messaging (Kafka), atau sistem otentikasi, lompatan waktu ke belakang (*negative jump*) akan merusak konsistensi transaksi ACID, memicu eksekusi log commit yang korup, dan membuat timer leasing terpicu sebelum waktunya.

### Jawaban 4
- **EngineID** adalah string heksadesimal unik yang menjadi pengenal identitas administratif SNMP entitas (SNMP agent). EngineID digunakan sebagai *seed* kunci untuk hashing enkripsi otentikasi serta mengelola parameter *engine boots* dan *engine time* untuk menangkal serangan *replay attack*.
- **Dampak Duplikasi EngineID**: NMS akan menganggap komunikasi dari agen kedua sebagai percobaan *replay attack* atau *out-of-window packet* karena urutan nomor counter boot/time tidak sinkron, mengakibatkan NMS secara acak menjatuhkan (*dropping*) paket respons atau metrik dari salah satu perangkat.

### Jawaban 5
- **Syslog UDP 514**:
  - *Karakteristik*: Tidak ada connection state, overhead minim.
  - *Kelemahan*: *Unreliable delivery*. Saat terjadi kongesti/loss, pesan log hilang selamanya tanpa notifikasi, dan urutan log bisa teracak (*out-of-order*). Rawan serangan manipulasi payload karena ketiadaan enkripsi.
- **Syslog TCP/TLS 6514**:
  - *Karakteristik*: Koneksi berorientasi stream, handshaking, retensi integritas via TLS.
  - *Kelemahan*: Saat terjadi loss/kongesti parah, mekanisme *TCP backpressure* dan retransmisi membebani buffer perangkat pengirim. Jika antrean lokal penuh, daemon logging dapat menyebabkan aplikasi sistem mengalami *blocking* (*I/O hang*) atau menjatuhkan log baru.

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: Badai SERVFAIL Pasca Rotasi Kunci DNSSEC
**Konteks**: Tim SecOps sebuah institusi perbankan melakukan rotasi KSK (*Key Signing Key*) tahunan pada zona authoritative DNS mereka `bankkripto.id`. Lima belas menit setelah rotasi, pelanggan dari berbagai ISP besar (seperti Telkom, Indosat, Biznet) mengeluhkan tidak bisa membuka aplikasi mobile banking dengan indikasi error resolusi nama, sementara jika diakses dari dalam kantor pusat yang menggunakan resolver internal tanpa DNSSEC, aplikasi berjalan normal.

**Tugas Analisis**:
1. Apa akar permasalahan kriptografis DNSSEC yang memicu terjadinya status kueri `SERVFAIL` pada resolver ISP publik?
2. Bagaimana langkah sistematis untuk mendiagnosis masalah ini dari terminal menggunakan utilitas CLI?
3. Langkah mitigasi darurat apa yang harus segera dieksekusi oleh tim Network & SecOps?

### Solusi Skenario 1
1. **Akar Masalah**: Ketidaksinkronan rantai kepercayaan (*broken chain of trust*). Tim SecOps memperbarui KSK di Authoritative Server internal dan menerbitkan DNSKEY baru, namun **belum memperbarui atau terlambat mengunggah DS Record baru yang sesuai ke registri induk TLD** (`.id`). Akibatnya, Recursive Resolver publik (ISP) memvalidasi RRSIG yang dibuat dengan KSK baru terhadap hash DS Record lama milik parent zone, menghasilkan validasi gagal (*Cryptographic Verification Failure*), sehingga resolver mengembalikan status `SERVFAIL`.
2. **Diagnosis CLI**:
   ```bash
   # Uji dengan validasi DNSSEC aktif (menghasilkan SERVFAIL)
   dig @8.8.8.8 bankkripto.id A
   
   # Uji dengan mematikan validasi DNSSEC (+cd = Checking Disabled)
   dig @8.8.8.8 bankkripto.id A +cd
   # Jika kueri +cd menghasilkan status NOERROR beserta record IP yang benar, masalah dipastikan 100% pada DNSSEC.

   # Periksa DNSKEY lokal vs DS Record di parent zone
   dig bankkripto.id DNSKEY +multiline
   dig id. DS bankkripto.id +multiline
   ```
3. **Mitigasi Darurat**:
   - Jika DS lama sudah terhapus di parent zone: Rollback Authoritative Server untuk sementara menggunakan KSK lama yang cocok dengan DS Record yang masih aktif di registrar TLD `.id`.
   - Jika KSK baru harus dipertahankan: Segera akses portal registrar TLD `.id`, masukkan hash DS record dari KSK baru, dan turunkan TTL zona untuk mempercepat konvergensi cache DS yang kedaluwarsa.

---

### Skenario 2: Rogue DHCP Server Melumpuhkan Akses Kantor Cabang
**Konteks**: Pada kantor cabang regional, beberapa karyawan melaporkan kehilangan koneksi ke server intranet ERP secara acak. Saat dilakukan pemeriksaan konfigurasi pada laptop karyawan yang bermasalah, ditemukan alamat IP yang didapat berada pada subnet `192.168.1.0/24` dengan gateway `192.168.1.1`, padahal standar korporat kantor cabang tersebut seharusnya menggunakan subnet `10.240.30.0/24` yang dialokasikan oleh DHCP Server terpusat melalui switch Cisco Catalyst 3850 (`ip helper-address`).

**Tugas Analisis**:
1. Identifikasi serangan atau anomali operasional apa yang sedang berlangsung di jaringan lokal cabang tersebut!
2. Jelaskan mengapa klien bisa menerima IP dari gateway liar tersebut mendahului server pusat!
3. Susun konfigurasi hardening Layer 2 komprehensif pada Cisco Catalyst switch untuk mematikan anomali tersebut secara permanen!

### Solusi Skenario 2
1. **Identifikasi**: Terdapat **Rogue DHCP Server** di dalam jaringan lokal (kemungkinan router nirkabel rumahan yang salah dicolokkan ke port switch kantor oleh karyawan, atau serangan *DHCP Spoofing/Man-in-the-Middle*).
2. **Alasan Klien Menerima IP Liar**: DHCP Discover dipancarkan via broadcast Layer 2. Rogue DHCP server berada di segmen collision/broadcast domain lokal yang sama dengan klien, sedangkan DHCP server legal berada di Data Center terpusat yang memerlukan konversi unicast relay oleh switch L3. Respons `DHCPOFFER` dari Rogue DHCP lokal tiba lebih cepat (*lower latency*) ke klien dibandingkan respons dari server terpusat. Berdasarkan spesifikasi DHCP, klien memilih tawaran pertama yang diterimanya.
3. **Konfigurasi Hardening Cisco**:
   Aktifkan **DHCP Snooping** secara global dan pada VLAN terkait, lalu konfigurasikan *trust boundary*:
   ```cisco
   ! 1. Aktifkan DHCP Snooping secara global
   ip dhcp snooping
   ip dhcp snooping vlan 30

   ! 2. Nonaktifkan penambahan Option 82 jika switch L2 terhubung ke Relay upstream yang menolak paket
   no ip dhcp snooping information option

   ! 3. Tentukan Uplink interface (menuju Core/DHCP Server legal) sebagai TRUSTED
   interface TenGigabitEthernet1/0/1
    description UPLINK-TO-CORE
    ip dhcp snooping trust
    exit

   ! 4. Seluruh port akses (port klien) secara default adalah UNTRUSTED.
   ! Batasi laju paket DHCP untuk menangkal DHCP Starvation Attack:
   interface range GigabitEthernet1/0/2 - 48
    description ACCESS-CLIENTS
    ip dhcp snooping limit rate 15
    exit
   ```

---

### Skenario 3: Kerberos Authentication Failure Akibat Desinkronisasi Jam Hypervisor
**Konteks**: Sebuah farm virtualisasi private cloud menjalankan 50 VM worker database dan worker nodes Active Directory. Setelah pemeliharaan berkala infrastruktur server fisik (bare-metal ESXi host), VM AD Domain Controller mulai menolak otentikasi login pengguna dengan pesan error `KDC_ERR_SKEW_REV_KEY: Clock skew too great`. Setelah diselidiki, waktu jam pada DC melenceng 8 menit ke depan dari waktu riil dunia.

**Tugas Analisis**:
1. Apa kaitan toleransi waktu Kerberos terhadap NTP dan mengapa batas toleransi default bernilai 5 menit (300 detik)?
2. Mengapa sinkronisasi jam VM bisa rusak setelah restart host virtualisasi meskipun konfigurasi NTP di dalam guest OS telah diatur?
3. Rancang arsitektur sinkronisasi waktu presisi tinggi yang mengombinasikan hardware clock, host virtualization settings, dan guest OS configuration!

### Solusi Skenario 3
1. **Analisis Toleransi Kerberos**: Protokol Kerberos menggunakan timestamp di dalam tiket otentikasi (*authenticator*) untuk mencegah serangan *Replay Attack* (peretas menangkap tiket otentikasi valid dari kabel lalu mengirimkannya ulang untuk mendapatkan akses). Batas *clock skew* default 5 menit adalah kompromi keamanan: jendela waktu cukup sempit untuk membatasi ruang eksploitasi, namun cukup fleksibel untuk mentolerir drift minor antar host.
2. **Penyebab Kerusakan Sinkronisasi Waktu VM**:
   - Terjadi persaingan sinkronisasi waktu (*dual-source time synchronization conflict*).
   - Saat boot, Guest OS VM menyinkronkan waktu dari jam virtual hardware yang disediakan oleh ESXi hypervisor (*VMware Tools Periodic Time Sync*).
   - Jika jam host fisik (BIOS/CMOS/ESXi) sendiri melenceng dan tidak tersinkronisasi ke NTP, maka setiap kali VM reboot atau mengalami proses vMotion, hypervisor memaksakan jam fisiknya yang salah ke VM guest, menimpa (*overriding*) penyesuaian yang sedang dilakukan oleh daemon NTP internal guest OS.
3. **Desain Arsitektur Rekomendasi**:
   - **Tingkat Fisik (Host Hypervisor)**:
     - Konfigurasi seluruh physical host (ESXi/KVM) mengarah ke NTP Server terpusat yang sama (Stratum 1 GPS Appliance di Data Center).
     - Aktifkan NTP daemon pada level boot ESXi.
   - **Tingkat Virtualisasi (VM Integration Tools)**:
     - Nonaktifkan sinkronisasi waktu periodik dari host hypervisor ke guest VM (`tools.syncTime = "FALSE"` pada berkas VMX).
   - **Tingkat Guest OS (Domain Controller & VM)**:
     - Gunakan `chrony` di Linux atau `w32tm` di Windows.
     - Atur Domain Controller induk (PDC Emulator) untuk menyinkronkan langsung waktu ke NTP server korporat via antarmuka jaringan terdedikasi.
     - Seluruh node worker dan client menyinkronkan waktu secara hierarkis ke PDC Emulator.

---

## 4. Practical Chapter Challenge: Arsitektur Infrastruktur Inti DC

### Deskripsi Masalah
Sebagai Principal Network Architect, Anda ditugaskan merancang spesifikasi konfigurasi otomasi untuk infrastruktur Data Center baru yang mencakup 2 Spine Switch, 4 Leaf Switch, dan 2 Virtualized Firewall/Core Router.

### Persyaratan Desain:
1. **DHCP Relay & Option 82**:
   - SVI di Leaf Switch harus mengonversi broadcast DHCP klien pada VLAN 101-104 menuju Central DHCP Server (`172.16.50.10` dan `172.16.50.11`).
   - Switch harus menyisipkan sub-option Circuit-ID yang mencakup nama VLAN dan ID port interface.
2. **Hierarki Sinkronisasi NTP**:
   - Kedua Spine Switch bertindak sebagai NTP Stratum 2 Server, menyinkronkan diri ke Stratum 1 upstream (`192.0.2.1` dan `198.51.100.1`) dengan otentikasi SHA1 Key ID 42.
   - Seluruh Leaf Switch hanya diizinkan mengambil waktu dari kedua Spine Switch tersebut.
3. **Manajemen SNMPv3 Terenkripsi**:
   - Seluruh perangkat hanya boleh diekspos melalui SNMPv3 dengan level keamanan `authPriv`.
   - Menggunakan hashing SHA-256 untuk otentikasi dan AES-256 untuk privasi data payload.
   - Polling terbatas pada MIB-2 System (`1.3.6.1.2.1.1`) dan Interface (`1.3.6.1.2.1.2`).
4. **Syslog Centralization**:
   - Seluruh event dengan severity `Warning` hingga `Emergency` (Severity 0-4) pada Facility `local5` harus diforward ke SIEM Server (`172.16.99.100`) via protokol TCP port 514 secara reliable.

### Deliverable:
Tuliskan blok konfigurasi deklaratif (gaya Cisco IOS XE / Arista EOS) yang merefleksikan implementasi persyaratan di atas secara lengkap dan siap dideploy!

---

### Solusi Practical Chapter Challenge

Berikut adalah template konfigurasi produksi standar enterprise (Cisco IOS XE format):

```cisco
! ====================================================================
! 1. SINKRONISASI WAKTU NTP (SPINE & LEAF SPECIFICATION)
! ====================================================================
! [Konfigurasi pada Spine Switch (Bertindak sbg Stratum 2 Peer)]
ntp authenticate
ntp authentication-key 42 sha1 c7a9e3f1b0a884cd90ef762a4d7c1e5f8841bc6e 7
ntp trusted-key 42
ntp server 192.0.2.1 key 42 prefer
ntp server 198.51.100.1 key 42
ntp source Loopback0
ntp master 2

! Batasi akses NTP hanya untuk Leaf switch internal
ip access-list standard ACL-NTP-CLIENTS
 permit 10