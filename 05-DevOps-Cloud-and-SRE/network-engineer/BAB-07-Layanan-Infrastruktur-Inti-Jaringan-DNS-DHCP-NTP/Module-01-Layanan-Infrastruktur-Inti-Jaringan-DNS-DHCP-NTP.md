# Modul 01: Layanan Infrastruktur Inti Jaringan (DNS, DHCP, NTP, SNMP, Syslog)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengonfigurasi, menganalisis, dan memecahkan masalah (troubleshoot) siklus resolusi hierarkis DNS (Recursive vs Authoritative) beserta rantai validasi DNSSEC (*Chain of Trust*).
- Membedah dan mendiagnosis pertukaran paket DHCP DORA serta mekanisme injeksi field `giaddr` dan Option 82 pada DHCP Relay Agent (*ip helper-address*).
- Merancang dan mengevaluasi topologi sinkronisasi waktu jaringan berbasis NTP Stratum Clock Hierarchy untuk meminimalkan *jitter*, *offset*, dan *drift*.
- Mengimplementasikan manajemen perangkat aman berbasis SNMPv3 dengan enkripsi *User-Based Security Model* (USM) dan arsitektur MIB OID.
- Mengonfigurasi sentralisasi logging berbasis RFC 5424 Syslog dengan kalkulasi manual nilai `PRI` berdasarkan *Facility* dan *Severity*.

---

## 2. Prerequisite
Untuk memahami materi ini secara optimal, pembaca wajib menguasai:
- Model OSI dan TCP/IP: Pemahaman mendalam tentang header Layer 3 (IPv4/IPv6) dan Layer 4 (UDP/TCP).
- Pengalamatan IP & Subnetting: Mekanisme Unicast, Broadcast, dan Anycast.
- Dasar CLI Jaringan: Pengoperasian Cisco IOS XE atau Junos OS, serta shell Linux (Bash, `iproute2`, `systemd`).
- Protokol Keamanan Kriptografi Dasar: Hashing (SHA-256), Asymmetric Cryptography (RSA/ECDSA), dan Symmetric Encryption (AES-CFB/GCM).

---

## 3. Concept
Layanan Infrastruktur Inti Jaringan (*Core Network Infrastructure Services*) adalah fondasi *control plane* dan *management plane* yang memungkinkan jaringan komputer berfungsi secara dinamis, terotomasi, konsisten, dan dapat diamati (*observable*). Layanan ini terdiri dari:
1. **DNS (Domain Name System)**: Mengabstraksi pengalamatan numerik (IP) menjadi penamaan hierarkis yang dapat dibaca manusia serta memvalidasi integritas data melalui tanda tangan digital (DNSSEC).
2. **DHCP (Dynamic Host Configuration Protocol)**: Mengotomatisasi distribusi konfigurasi IP host, gateway, DNS resolver, dan parameter jaringan tingkat lanjut secara terpusat.
3. **NTP (Network Time Protocol)**: Menyinkronkan basis waktu (*clock temporal*) seluruh sistem komputasi dan elemen jaringan untuk menjamin integritas urutan peristiwa (*event sequencing*).
4. **SNMPv3 (Simple Network Management Protocol version 3)**: Menyediakan mekanisme *polling* metrik performa dan *asynchronous alerting* (Traps/Informs) dengan jaminan *Confidentiality*, *Integrity*, dan *Authentication*.
5. **Syslog**: Protokol pengiriman log sistem standar industri untuk mengonsolidasikan audit jejak eksekusi dan anomali perangkat keras/lunak ke sistem SIEM/log collector.

---

## 4. Why
Tanpa standarisasi dan determinisme pada layanan inti:
- **Kegagalan Resolusi DNS** melumpuhkan penemuan layanan (*service discovery*) pada aplikasi modern dan microservices, mengakibatkan *cascading outage*.
- **Ketiadaan DHCP/Relay yang Tepat** mengharuskan alokasi IP manual yang memicu *IP conflict*, kelelahan operasional (*operational toil*), dan fragmentasi subnetting.
- **Waktu Jam Desinkronisasi (NTP Drift)** mematahkan otentikasi berbasis tiket (Kerberos), menggagalkan validasi sertifikat TLS/X.509, serta merusak analisis forensik insiden keamanan lintas perangkat.
- **SNMPv1/v2c Tanpa Enkripsi** membocorkan informasi topologi melalui *community string* plaintext yang rentan terhadap *sniffing* dan modifikasi konfigurasi berbahaya.
- **Syslog Tanpa Struktur** membuat deteksi dini insiden kolaps karena ketiadaan *single source of truth* mengenai kondisi kesehatan perangkat secara *real-time*.

---

## 5. What (Deep-Dive Teknis Lengkap)

### A. Domain Name System (DNS) & DNSSEC
DNS bekerja di atas port UDP 53 (dan fallback ke TCP 53 bila ukuran respons > 512 bytes pada standar RFC 1035, atau menggunakan ekstensi EDNS0/RFC 6891).

#### 1. Recursive vs Authoritative Resolver
- **Recursive Resolver**: Bertindak atas nama klien (*stub resolver*). Ia mencari jawaban dengan menanyakan hierarki DNS dari Root Nameserver (`.`), TLD Nameserver (`.com`), hingga Authoritative Nameserver yang memegang *Zone File* target. Recursive resolver menyimpan hasil di lokal cache sesuai nilai TTL (*Time to Live*).
- **Authoritative Nameserver**: Server yang memiliki hak resmi (*authoritative*) atas suatu domain dan menyimpan rekaman DNS asli (A, AAAA, CNAME, MX, PTR, TXT, SOA, NS). Server ini tidak melakukan iterasi keluar; ia hanya merespons apakah domain ada di zonanya atau mengembalikan delegasi (referral) ke nameserver lain.

#### 2. Root Hints
Daftar statis 13 kluster logis Root Nameserver (`a.root-servers.net` hingga `m.root-servers.net`) yang dioperasikan oleh institusi global (ICANN, NASA, Verisign, WIDE, dll.) menggunakan *BGP Anycast* pada ratusan lokasi fisik untuk merespons query awal resolver rekursif.

#### 3. DNSSEC (DNS Security Extensions - RFC 4033, 4034, 4035)
DNS murni rentan terhadap *DNS Spoofing* dan *Cache Poisoning* (Kaminsky Attack). DNSSEC menambahkan kriptografi asimetris untuk memvalidasi keaslian sumber dan integritas record tanpa mengenkripsi isi payload query.
- **RRSIG (Resource Record Signature)**: Tanda tangan digital atas kumpulan record DNS (*RRset*) menggunakan *Zone Signing Key* (ZSK) privat.
- **DNSKEY**: Kunci publik yang dipublikasikan dalam zona untuk memverifikasi RRSIG. Terdiri dari ZSK (menandatangani record) dan KSK (*Key Signing Key*, menandatangani ZSK).
- **DS (Delegation Signer)**: Hash SHA-256 dari KSK yang diletakkan pada parent zone (misal: domain `.com` menampung DS record untuk `example.com`), membentuk rantai validasi (*Chain of Trust*) hingga ke Root Zone KSK Trust Anchor.
- **NSEC / NSEC3**: Membuktikan ketiadaan record (*Authenticated Denial of Existence*) secara kriptografis tanpa mengekspos seluruh isi zona (*zone walking prevention* via hashing pada NSEC3).

---

### B. Dynamic Host Configuration Protocol (DHCP) & Relay Agent

#### 1. Siklus DORA (RFC 2131)
Beroperasi pada UDP port 67 (Server) dan UDP port 68 (Client).
1. **Discover**: Klien mengirimkan paket broadcast Layer 2 (`FF:FF:FF:FF:FF:FF`) dan Layer 3 (`255.255.255.255`) dengan source IP `0.0.0.0:68` dan destination IP `255.255.255.255:67`. Payload berisi MAC address klien (`chaddr`) dan Transaction ID (`xid`).
2. **Offer**: DHCP Server yang mendengar request menawarkan konfigurasi IP via unicast atau broadcast. Paket berisi `yiaddr` (*Your IP Address*), subnet mask, lease duration, dan IP server (`siaddr`).
3. **Request**: Klien merespons penawaran secara broadcast (untuk memberi sinyal ke server DHCP lain bahwa penawarannya ditolak) yang mengonfirmasi bahwa klien memilih IP dari server tertentu via Option 54 (Server Identifier).
4. **Acknowledge (ACK)**: Server memvalidasi alokasi final, mencatat *binding*, dan mengirimkan parameter DNS, Default Gateway (Option 3), dan Subnet Mask (Option 1). Klien melakukan pemeriksaan ARP defensif (*Gratuitous ARP*) sebelum mengikat IP ke antarmuka.

```
       Client (UDP:68)              DHCP Server (UDP:67)
              |                              |
              |------ DHCPDISCOVER --------->| (Broadcast L2/L3)
              |<----- DHCPOFFER -------------| (Unicast/Broadcast)
              |------ DHCPREQUEST ---------->| (Broadcast L2/L3)
              |<----- DHCPACK ---------------| (Unicast/Broadcast)
              |                              |
```

#### 2. DHCP Relay Agent & Option 82 (RFC 3046)
Broadcast Layer 2 tidak dapat melintasi router boundary. Router bertindak sebagai **Relay Agent** (`ip helper-address` pada Cisco):
- Mengintersepsi paket broadcast DHCPDISCOVER pada port 68/67.
- Mengubah paket broadcast menjadi unicast menuju IP DHCP Server terpusat.
- Menyisipkan IP interface ingress router tempat paket diterima ke dalam field header DHCP `giaddr` (*Gateway IP Address*).
- DHCP Server membaca `giaddr` untuk menentukan *Subnet Scope/Pool* mana yang harus dialokasikan untuk klien tersebut.
- Menyisipkan **Option 82 (Relay Agent Information Option)**:
  - *Circuit ID Sub-option*: Mengidentifikasi interface fisik/VLAN spesifik klien (contoh: GigabitEthernet0/1:VLAN10).
  - *Remote ID Sub-option*: Mengidentifikasi identitas router (contoh: MAC base router atau Hostname).

---

### C. Network Time Protocol (NTP)

NTP (RFC 5905) beroperasi pada Layer 4 UDP port 123. Sinkronisasi menggunakan algoritma Marzullo dan filter persimpangan clock (*intersection algorithm*) untuk menolak server waktu penipu (*falsetickers*).

#### Hierarki Stratum
- **Stratum 0**: Sumber waktu referensi presisi tinggi non-jaringan (*Reference Clocks*), seperti Cesium Atomic Clocks, GPS, Galileo, atau CDMA signals. Tidak terhubung langsung ke jaringan komputer.
- **Stratum 1**: Komputer/server jaringan yang terhubung langsung secara fisik (via serial, USB, PCIe, PPS) ke perangkat Stratum 0. Menjadi *Primary Time Server*.
- **Stratum 2**: Server yang meminta waktu kepada server Stratum 1 melalui protokol NTP over network. Menjalankan *peer-to-peer checks* untuk akurasi.
- **Stratum 3-15**: Server/host yang menginduk pada Stratum di atasnya.
- **Stratum 16**: Menandakan jam tidak tersinkronisasi (*unsynchronized / invalid*).

#### Formula Kalkulasi Jaringan NTP
NTP menghitung *Round-Trip Delay* ($\delta$) dan *Clock Offset* ($\theta$) berdasarkan empat timestamp:
- $T_1$: Waktu pengiriman paket request dari Client.
- $T_2$: Waktu penerimaan paket request di Server.
- $T_3$: Waktu pengiriman paket respons dari Server.
- $T_4$: Waktu penerimaan paket respons di Client.

$$\text{Round-Trip Delay } (\delta) = (T_4 - T_1) - (T_3 - T_2)$$

$$\text{Clock Offset } (\theta) = \frac{(T_2 - T_1) + (T_3 - T_4)}{2}$$

---

### D. Simple Network Management Protocol Version 3 (SNMPv3)

SNMPv3 (RFC 3411-3418) menggantikan SNMPv1/v2c yang menggunakan *Community String* tanpa enkripsi. SNMP beroperasi pada UDP port 161 (Polling: Get/Set/GetBulk) dan UDP port 162 (Notification: Trap/Inform).

#### 1. Security Levels (USM - User-based Security Model)
- **noAuthNoPriv**: Tanpa otentikasi, tanpa enkripsi (hanya pencocokan username, identik kerentanannya dengan SNMPv2c).
- **authNoPriv**: Menggunakan otentikasi berbasis hash kriptografi (HMAC-MD5, HMAC-SHA-1, SHA-224, SHA-256, SHA-384, SHA-512) untuk validasi integritas dan identitas; payload tidak dienkripsi.
- **authPriv**: Level paling aman. Menambahkan enkripsi simetris (DES, 3DES, AES-128, AES-192, AES-256) pada payload data selain hashing otentikasi.

#### 2. MIB (Management Information Base) & OID (Object Identifier)
MIB adalah struktur data hierarkis berbentuk pohon terbalik (*tree*) yang mendefinisikan variabel instrumentasi perangkat. Setiap node diidentifikasi dengan nomor OID.
Contoh OID Standar:
- `1.3.6.1.2.1` (`iso.org.dod.internet.mgmt.mib-2`): Node dasar informasi sistem.
- `1.3.6.1.2.1.1.1` (`sysDescr`): Deskripsi hardware dan OS.
- `1.3.6.1.2.1.2.2.1.10` (`ifInOctets`): Jumlah byte inbound interface.
- `1.3.6.1.4.1` (`iso.org.dod.internet.private.enterprises`): Cabang khusus vendor (Private Enterprise Numbers / PEN, misal: Cisco = `9`, Juniper = `2636`).

#### 3. Polling vs Asynchronous Notifications
- **Polling (SNMP Get / GetBulk)**: NMS secara berkala merequest data OID ke agen. Stateless, menggunakan port 161.
- **Trap**: Agen mengirim notifikasi peristiwa kritis ke NMS tanpa konfirmasi balik (unreliable UDP 162).
- **Inform**: Serupa dengan Trap, namun NMS **wajib** mengirimkan paket *Response ACK* balik ke agen. Agen akan melakukan retransmisi jika ACK tidak diterima.

---

### E. Syslog Protocol (RFC 5424 vs RFC 3164)

Syslog mentransmisikan pesan log peristiwa perangkat melalui UDP/TCP port 514 (atau TLS port 6514).

#### 1. Rumus Kalkulasi Nilai PRI
Setiap pesan syslog diawali oleh field `<PRI>` (*Priority Value*) di dalam kurung siku. PRI dihitung secara matematis menggunakan rumus:

$$\mathbf{PRI = (Facility \times 8) + Severity}$$

#### 2. Tabel Facility (Kategori Penghasil Pesan)
| Kode | Deskripsi | Kode | Deskripsi |
| :--- | :--- | :--- | :--- |
| **0** | kernel messages | **16** | local use 0 (`local0`) |
| **1** | user-level messages | **17** | local use 1 (`local1`) |
| **2** | mail system | **18** | local use 2 (`local2`) |
| **3** | system daemons | **19** | local use 3 (`local3`) |
| **4** | security/authorization | **20** | local use 4 (`local4`) |
| **5** | messages generated by syslogd | **21** | local use 5 (`local5`) |
| **10** | security/authorization | **22** | local use 6 (`local6`) |
| **11** | FTP daemon | **23** | local use 7 (`local7`) |

#### 3. Tabel Severity Level
| Severity | Deskripsi | Makna Operasional |
| :---: | :--- | :--- |
| **0** | Emergency (`emerg`) | Sistem hancur / unbootable / panic |
| **1** | Alert (`alert`) | Harus segera ditangani (misal: korupsi database) |
| **2** | Critical (`crit`) | Kondisi kritis hardware/software (misal: PSU fail) |
| **3** | Error (`err`) | Kondisi error non-fatal |
| **4** | Warning (`warning`) | Peringatan indikasi anomali |
| **5** | Notice (`notice`) | Normal tapi kejadian signifikan (misal: link up/down) |
| **6** | Informational (`info`) | Pesan operasional normal |
| **7** | Debug (`debug`) | Diagnostik mendalam tingkat thread/paket |

*Contoh Perhitungan PRI*:
Sebuah router Cisco memproduksi pesan antarmuka link flap pada facility `local7` (23) dengan tingkat keparahan `Notice` (5).
$$\text{PRI} = (23 \times 8) + 5 = 184 + 5 = 189 \implies \text{Header: } \mathbf{<189>}$$

---

## 6. How
Implementasi dan orkestrasi kelima layanan dilakukan dengan metodologi berikut:
1. **Perencanaan Topologi Pengkabelan & Subnetting**: Alokasikan subnet manajemen khusus (Out-of-Band / OOBM) untuk NTP, SNMP, dan Syslog terpisah dari Data Plane.
2. **Implementasi Otoritatif dan Relaying**:
   - Pasang DHCP relay agent sedekat mungkin dengan klien (pada First-Hop Redundancy Protocol/SVI Layer 3 Core-Distribution).
   - Injeksi Option 82 untuk memetakan alokasi alamat IP terhadap port fisik access-switch.
3. **Penyusunan Rantai Kepercayaan DNSSEC**:
   - Generate KSK dan ZSK menggunakan algoritma kriptografi modern (misal: ECDSAP256SHA256).
   - Upload Hash DS Record ke domain registrar (parent zone).
4. **Pengerasan Waktu (NTP Hardening)**:
   - Buat minimal 4 sumber Stratum 1/2 upstream independen untuk mendeteksi *falsetickers*.
   - Terapkan Symmetric Key Authentication (`SHA1` atau `AES-128-CMAC`) antar peer.
5. **Enkripsi Telemetri**:
   - Nonaktifkan SNMP v1 dan v2c (`no snmp-server`).
   - Buat SNMPv3 USM group dengan hak akses View (`VACM`) berbasis prinsip *least privilege*.
   - Forward Syslog menggunakan transport Layer 4 TCP dengan enkripsi TLS (RFC 5425) port 6514.

---

## 7. Analogy
Bayangkan operasional sebuah **Bandara Internasional Modern**:
- **DNS** adalah **Sistem Informasi Penerbangan & Rambu Petunjuk Arah**: Penumpang tidak mengingat koordinat GPS landasan (IP Address); mereka mencari "Terminal 3 Gate 12" (FQDN). DNSSEC adalah cap segel hologram resmi maskapai pada *boarding pass* yang mencegah sindikat kriminal mencetak tiket palsu.
- **DHCP & Relay** adalah **Meja Imigrasi & Check-in Dinamis**: Penumpang tidak memilih nomor kursi sendiri secara permanen dari rumah. Mereka tiba, meminta alokasi nomor identitas tempat duduk temporal (*DHCP Lease*). Jika penumpang berada di satelit terminal terpencil, petugas perantara (*Relay Agent*) membawa formulir penumpang ke server pusat dengan catatan stempel "Berasal dari Gate B" (*Option 82 / giaddr*).
- **NTP** adalah **Sistem Jam Master Bandara (Master Clock Network)**: Menara pengawas (ATC), radar kokpit pesawat, dan sistem bagasi harus mengacu pada satu detik atomik yang sama. Perbedaan waktu 2 detik saja pada radar dapat menyebabkan tabrakan landasan.
- **SNMPv3** adalah **Petugas Inspeksi Khusus Berkamar Rahasia**: Menggunakan kunci brankas terenkripsi (*authPriv*) untuk memeriksa tekanan hidrolik pipa dan suhu generator genset secara berkala (*polling*) tanpa risiko disadap mata-mata.
- **Syslog** adalah **Perekam Kotak Hitam (Flight Data Recorder) & Log Menara Kontrol**: Setiap peristiwa (pintu dibuka = Notice, rem overheat = Critical) diberi cap waktu NTP dan nomor identitas divisi pembuat log untuk analisis pasca-insiden.

---

## 8. Diagram (ASCII)

### A. Resolusi DNS Hierarkis & Validasi DNSSEC
```
 Client               Recursive Resolver       Root DNS (.)         .COM TLD DNS        Example.com DNS
   |                          |                     |                     |                     |
   |--- Query example.com --->|                     |                     |                     |
   |                          |--- Root Hint (?) -->|                     |                     |
   |                          |<-- Referral to .com |                     |                     |
   |                          |    + DS (.com)      |                     |                     |
   |                          |------------------------------------------>|                     |
   |                          |<-- Referral to example.com + DS (example)-|                     |
   |                          |---------------------------------------------------------------->|
   |                          |<-- A Record + RRSIG(A) + DNSKEY + RRSIG(DNSKEY) ----------------|
   |                          |
   |                          | [DNSSEC Cryptographic Validation Check]
   |                          | 1. Verify RRSIG(A) using ZSK
   |                          | 2. Verify ZSK using KSK
   |                          | 3. Hash KSK and verify match with DS record from .COM TLD
   |                          | 4. Validate .COM DS against Root Anchor
   |<-- Validated IP: 1.2.3.4-|
```

### B. DHCP DORA Melalui Relay Agent (ip helper-address)
```
[ DHCP Client ]                  [ L3 Switch / Relay ]                 [ Central DHCP Server ]
(VLAN 10: 10.10.10.50)           (SVI 10: 10.10.10.1)                  (IP: 192.168.100.10)
      |                                    |                                     |
      |=== 1. DHCPDISCOVER ===============>|                                     |
      |    Src: 0.0.0.0 (L2 Broadcast)     |                                     |
      |    Dst: 255.255.255.255            |=== 2. DHCPDISCOVER (Unicast) ======>|
      |                                    |    Src: 10.10.10.1                  |
      |                                    |    Dst: 192.168.100.10              |
      |                                    |    giaddr: 10.10.10.1               |
      |                                    |    Option 82: Sub-opt 1 (VLAN10)    |
      |                                    |                                     |
      |                                    |<== 3. DHCPOFFER (Unicast) ==========|
      |                                    |    yiaddr: 10.10.10.50              |
      |<== 4. DHCPOFFER (Unicast/Bcast) ===|    giaddr: 10.10.10.1               |
      |    yiaddr: 10.10.10.50             |                                     |
      |                                    |                                     |
      |=== 5. DHCPREQUEST ================>|=== 6. DHCPREQUEST (Unicast) =======>|
      |    giaddr: 0.0.0.0                 |    giaddr: 10.10.10.1               |
      |                                    |                                     |
      |                                    |<== 7. DHCPACK (Unicast) ============|
      |<== 8. DHCPACK =====================|    yiaddr: 10.10.10.50              |
```

### C. Struktur Pesan Syslog RFC 5424
```
+-----------------------------------------------------------------------------------------+
|                                    SYSLOG FRAME                                         |
+-------+--------------------+------------------------------------------------------------+
| <PRI> |   HEADER           | STRUCTURED-DATA (SD)       | MSG                           |
+-------+--------------------+------------------------------------------------------------+
| <189> | 1 2026-03-31T...   | [originator@9 enterpriseId | Interface GigabitEthernet0/1  |
|       | core-sw01          | ="9" ip="10.0.0.1"]        | changed state to down         |
|       | BGP 4242 ID42      |                            |                               |
+-------+--------------------+------------------------------------------------------------+
   |            |                                              |
   |            +--> VERSION, TIMESTAMP, HOSTNAME, APP-NAME,   +--> Free-text human payload
   |                 PROCID, MSGID
   |
   +--> Calculated: PRI = (Facility * 8) + Severity
        Example: local7 (23) * 8 + Notice (5) = 189
```

---

## 9. Simple Example

### Uji Resolusi Manual DNS (dig)
```bash
# Menampilkan penelusuran hierarkis dari root ke leaf record
dig +trace +dnssec api.infra.internal
```

### Kalkulasi Syslog PRI Sederhana
Jika sebuah daemon keamanan (*authpriv* - Facility `10`) mencatat error otentikasi login (*Warning* - Severity `4`):
$$\text{PRI} = (10 \times 8) + 4 = 84$$
Representasi data mentah Syslog yang keluar dari soket UDP:
`<84>1 2026-03-31T10:00:00.000Z srv-auth01 sshd 1240 - - Failed password for invalid user admin`

---

## 10. Practical Example (Konfigurasi CLI & Kode Hands-on)

### A. Konfigurasi Cisco IOS XE: DHCP Relay Agent & NTP
```cisco
! === 1. Konfigurasi DHCP Relay Agent (ip helper) ===
interface GigabitEthernet0/0/1.100
 description DATA-USERS-VLAN100
 encapsulation dot1Q 100
 ip address 10.100.0.1 255.255.255.0
 ! Injeksi giaddr dan konversi L2 broadcast ke L3 unicast:
 ip helper-address 192.168.10.50
 ip helper-address 192.168.10.51
 ! Mengaktifkan Option 82
 ip dhcp relay information option
 ip dhcp relay information trust-all
 exit

! === 2. Konfigurasi NTP Client Aman ===
ntp authenticate
ntp authentication-key 1 sha1 C1sc0NtpK3yS3cur3! 7
ntp trusted-key 1
! Mengarah ke Stratum 2 Servers
ntp server 192.168.1.10 key 1 prefer
ntp server 192.168.2.10 key 1
! Bind source NTP ke Loopback interface agar stabil
ntp source Loopback0
ntp access-group peer 10
!
access-list 10 permit 192.168.1.10
access-list 10 permit 192.168.2.10
```

### B. Konfigurasi Cisco IOS XE: SNMPv3 (authPriv) & Syslog RFC 5424
```cisco
! === 3. Konfigurasi SNMPv3 USM authPriv ===
snmp-server view VIEW-MONITOR iso included
snmp-server group GRP-ENTERPRISE-SRE v3 priv read VIEW-MONITOR

! User: sre-admin, Auth: SHA-256, Priv: AES-256
snmp-server user sre-admin GRP-ENTERPRISE-SRE v3 auth sha S3cur3AuthP@ssw0rd! priv aes 256 S3cur3Pr1v@cyK3y#

! Konfigurasi Trap Destination menggunakan SNMPv3
snmp-server enable traps
snmp-server host 192.168.200.150 version 3 priv sre-admin

! === 4. Konfigurasi Syslog Client Terpusat ===
service timestamps log datetime msec show-timezone
service sequence-numbers
logging origin-id hostname
logging facility local6
logging host 192.168.200.200 transport tcp port 514
logging trap informational
```

### C. Konfigurasi Linux Enterprise Chrony NTP Server (`/etc/chrony/chrony.conf`)
```ini
# Sinkronisasi ke upstream Stratum 1 NTP servers publik
server time1.google.com iburst minpoll 4 maxpoll 8
server time2.google.com iburst minpoll 4 maxpoll 8
server time3.google.com iburst minpoll 4 maxpoll 8

# Drift file untuk mencatat kompensasi clock skew hardware
driftfile /var/lib/chrony/drift

# Koreksi clock skew secara bertahap (slew) jika perbedaan < 1 detik,
# lakukan 'makestep' (step jump) hanya pada 3 update pertama
makestep 1.0 3

# Batasan subnet lokal yang diizinkan query ke server ini (Menjadi Stratum 2/3)
allow 10.0.0.0/8
allow 172.16.0.0/12

# Port operasional NTP standar
port 123

# Log pengukuran
log tracking measurements statistics
logdir /var/log/chrony
```

---

## 11. Real World Example
**Insiden Outage Multi-Layanan pada Perusahaan Finansial Multi-Branch**:
- **Gejala**: Ribuan workstation di kantor cabang gagal login domain Active Directory, transaksi trading tertolak karena kegagalan token Kerberos, dan NMS kehilangan visibilitas metrik.
- **Akar Masalah (Root Cause)**:
  1. *Time Drift*: Server NTP upstream publik diblokir oleh pembaruan firewall baru (*perimeter dropped UDP 123*). Jam DC internal bergeser (*drift*) sebesar 340 detik (> 5 menit, ambang batas default Kerberos skew). Tiket otentikasi AD ditolak seketika.
  2. *DHCP Failure*: Router core cabang di-reboot, konfigurasi `ip helper-address` hilang karena belum dieksekusi `write memory`. Klien di VLAN 20 tidak menerima penawaran DHCP dan mendapatkan *APIPA* (`169.254.x.x`).
  3. *DNS Poisoning*: Tanpa validasi DNSSEC, record gateway internal dimanipulasi oleh rogue ARP/DNS caching proxy.
- **Resolusi SRE**:
  - Merekonfigurasi `chrony` mengarah ke internal GPS Stratum 1 appliance dengan sinkronisasi statis.
  - Memasang CI/CD pipeline validasi konfigurasi (GitOps for Network) untuk mengunci persistensi `ip helper-address` dan konfigurasi Option 82.
  - Mengaktifkan `dnssec-validation auto` di seluruh Recursive BIND Resolver korporat.

---

## 12. Trade-offs

| Aspek | Pilihan A | Pilihan B | Trade-off / Implikasi Teknis |
| :--- | :--- | :--- | :--- |
| **DNS Resolusi** | Low TTL (misal: 30 detik) | High TTL (misal: 86400 detik) | **Low TTL**: *Failover* cepat, namun melipatgandakan *load* CPU/kueri ke authoritative server.<br>**High TTL**: Hemat beban & bandwidth, respon cepat dari cache, namun proses migrasi server/IP lambat terpropagasi. |
| **DHCP Lease Time** | Short Lease (1 Jam) | Long Lease (7-14 Hari) | **Short Lease**: Reklamasi alokasi IP cepat pada jaringan dinamis (*Guest Wi-Fi*), namun beban broadcast/DORA tinggi.<br>**Long Lease**: Menurunkan noise jaringan kabel korporat, namun berisiko *pool exhaustion* jika banyak perangkat transien. |
| **NTP Synchronization**| Step Adjustment | Slew Adjustment | **Step**: Melompatkan jam langsung ke waktu target. Menghilangkan offset instan, tapi berisiko merusak database transaksional.<br>**Slew**: Menyesuaikan frekuensi tick jam secara perlahan (slewing). Aman bagi sistem file/DB, namun memerlukan waktu lama untuk konvergensi. |
| **Monitoring Telemetri**| SNMPv2c | SNMPv3 authPriv | **SNMPv2c**: Ringan di CPU perangkat router/switch lawas, namun data plaintext (*community string*) rentan sadap.<br>**SNMPv3**: Aman secara kriptografis (AES/SHA), tetapi konsumsi utilisasi CPU control-plane meningkat signifikan saat pooling skala masif (*high churn*). |
| **Syslog Transport** | UDP 514 | TCP 514 / TLS 6514 | **UDP**: Ringan, *fire-and-forget*, namun rentan *packet loss* saat buffer jenuh.<br>**TCP/TLS**: *Guaranteed delivery* dan terenkripsi, tetapi memakan resource handshake dan berpotensi membebani kernel buffer jika log collector macet. |

---

## 13. When To Use
- **DNSSEC**: Wajib diimplementasikan pada domain publik organisasi, endpoint API perbankan, dan portal SSO untuk mencegah serangan man-in-the-middle (*cache poisoning*).
- **DHCP Relay Agent**: Wajib diaktifkan pada semua layer 3 switch/router yang melayani segmen endpoint pengguna akhir (VLAN access) ketika DHCP Server berada pada VLAN/Subnet terpusat atau Data Center.
- **NTP Chrony**: Digunakan pada infrastruktur Linux modern, container host, dan virtual machine yang mengalami fluktuasi clock frekuensi dinamis.
- **SNMPv3 authPriv**: Standar wajib untuk monitoring perangkat jaringan enterprise di industri finansial, telekomunikasi, dan instansi bersertifikasi compliance ISO 27001/PCI-DSS.

---

## 14. When NOT To Use
- **DNSSEC**: Jangan aktifkan DNSSEC pada *zone forwarding* lokal privat murni internal jika root zone privat lokal tidak memiliki Trust Anchor resmi yang terawat (berisiko memicu validasi `SERVFAIL` pada seluruh lookup internal).
- **DHCP Broadcast**: Jangan biarkan DHCP DORA berjalan tanpa Relay pada jaringan enterprise skala besar (hindari flat network L2 broadcast domain > 500 host).
- **SNMP Polling Interval < 5 detik**: Jangan lakukan polling OID tabular berat (seperti BGP Routing Table `1.3.6.1.2.1.15.3`) menggunakan interval agresif; gunakan *Streaming Telemetry* (gRPC/gNMI) sebagai penggantinya.
- **Syslog UDP pada Jaringan Wan/Internet Terbuka**: Hindari pengiriman Syslog plaintext melalui jaringan publik tanpa IPsec atau TLS encapsulation.

---

## 15. Common Mistakes
1. **Lupa Menentukan Interface Sumber (Source Binding)**: Mengonfigurasi NTP/SNMP/Syslog tanpa mengunci bind address ke `Loopback0`. Akibatnya, IP source paket berubah-ubah mengikuti tabel *routing egress*, menyebabkan NMS atau server NTP menolak paket karena ACL mismatch.
2. **Ketiadaan Konfigurasi `trust-all` atau Option 82 Subnet Mismatch**: Switch Layer 2 menyisipkan Option 82, tetapi Relay Agent berikutnya membuang paket (*dropped*) karena default setting menganggap paket yang sudah memiliki Option 82 dari switch sebelumnya adalah paket ilegal (*untrusted*).
3. **Miskonfigurasi Firewall UDP 123 Asimetris**: NTP client mengirim query dari source port acak (atau UDP 123) ke destination UDP 123. Stateful firewall kerap memblokir respons balik jika aturan inspeksi UDP stateful tidak diatur dengan benar.
4. **SNMPv3 EngineID Duplikat**: Meng-clone konfigurasi virtual switch/router beserta EngineID yang sama. Mengakibatkan NMS menolak komunikasi SNMPv3 karena kegagalan sinkronisasi *reboot engine boot counter* (*usmStatsNotInTimeWindows*).
5. **DNS Glue Record Hilang**: Mendelegasikan subdomain nameserver ke IP anak tanpa mendefinisikan *Glue Record* di parent zone, menghasilkan kondisi *circular dependency loop*.

---

## 16. Best Practices
1. **Konfigurasi Minimal Empat Sumber NTP Upstream**: Berdasarkan RFC 5905, butuh minimal 4 sumber waktu independen untuk mentoleransi 1 *falseticker* (server pembohong) dan mempertahankan konsensus kuorum ($n = 2f + 1$).
2. **Terapkan Dynamic ARP Inspection (DAI) & DHCP Snooping**:
   - Aktifkan `ip dhcp snooping` di switch access untuk mengeliminasi serangan *Rogue DHCP Server*.
   - Tetapkan port uplink menuju router/relay sebagai *trusted*, dan seluruh port akses pengguna sebagai *untrusted*.
3. **Standarisasi Penggunaan Syslog RFC 5424**: Gunakan format terstruktur dengan penanda ISO-8601 high-resolution timestamp (`YYYY-MM-DDTHH:MM:SS.mmmmmm+00:00`) untuk presisi audit mikrodetik.
4. **Isolasi Management Plane (OOBM)**: Salurkan seluruh trafik DNS resolving internal, NTP, SNMP, dan Syslog melalui VRF terisolasi (misal: `vrf MGMT`) agar tidak terganggu lonjakan trafik Data Plane.
5. **Gunakan DNSSEC Automasi (Auto-KASP)**: Manfaatkan tools otomatisasi penandatanganan zona (seperti BIND9 DNSSEC Key and Signing Policy) untuk menghindari kelalaian kedaluwarsa signature RRSIG.

---

## 17. Troubleshooting

### A. Alur Diagnosis Sistematis DNS
```
[ Masalah Resolusi Domain ]
           |
           v
[ 1. Uji Validasi DNSSEC ] ------( SERVFAIL? )-----> Jalankan: dig domain.com +cd (Checking Disabled)
           |                                         - Jika +cd sukses -> Broken DNSSEC Chain of Trust
           v (Status NOERROR)                        - Evaluasi expiration date RRSIG / DS mismatch.
[ 2. Uji Direct Authoritative ] 
           |
           +---> Jalankan: dig @auth-ns.domain.com domain.com
                 - Jika Authoritative timeout -> Network/Firewall issue pada UDP/TCP 53.
                 - Jika Authoritative merespons -> Masalah ada di intermediate Caching/Resolver.
```

### B. Diagnostik DHCP Relay
Jika host gagal memperoleh alamat IP:
1. Periksa statistik relay pada router/switch Layer 3:
   ```bash
   show ip dhcp relay information trusted-sources
   show ip dhcp binding
   ```
2. Tangkap paket DORA pada antarmuka router:
   ```bash
   # Linux / Cumulus
   tcpdump -envvn -i eth1 port 67 or port 68
   ```
3. Verifikasi apakah field `giaddr` terisi dengan IP interface gateway segmen tersebut. Jika `giaddr = 0.0.0.0`, paket belum diproses oleh Relay Agent.

### C. Diagnostik NTP
Verifikasi offset dan status peer NTP:
```bash
# Untuk Chrony
chronyc sources -v
chronyc sourcestats -v
chronyc tracking
```
- Tanda polaritas `*` berarti sumber terpilih (*current best sync*).
- Tanda `?` berarti konektivitas hilang/unreachable.
- Tanda `x` (*falseticker*) berarti jam server tersebut menyimpang jauh dari konsensus sumber lainnya.

### D. Diagnostik SNMPv3
```bash
# Debug kueri SNMPv3 dari NMS
snmpwalk -v3 -l authPriv -u sre-admin -a SHA-256 -A "S3cur3AuthP@ssw0rd!" \
  -x AES-256 -X "S3cur3Pr1v@cyK3y#" 192.168.1.1 1.3.6.1.2.1.1.1
```
Jika return: `Unknown user name` atau `SnmpEngineID mismatch`, hapus kredensial lama pada NMS engine cache dan verifikasi sinkronisasi waktu engine boots perangkat target.

---

## 18. Exercise
1. Sebuah pesan Syslog diterima oleh log collector dengan format mentah:
   `<134>1 2026-03-31T12:00:00Z spine01 bgp - - Neighbor 10.0.0.2 Down`
   **Tugas**: Hitung dan tentukan berapakah nilai numerik *Facility* dan *Severity* dari pesan tersebut, serta sebutkan nama kategori log dan tingkat keparahannya!
2. Gambarkan alur pertukaran paket DHCP DORA lengkap dengan perubahan source IP, destination IP, source MAC, destination MAC, dan status field `giaddr` ketika klien berada pada VLAN 10 dan DHCP Server berada pada subnet manajemen yang berbeda melalui Relay Agent!

---

## 19. Challenge
Sebuah enterprise telekomunikasi mengalami insiden: Ketika link antar-datacenter mengalami fluktuasi (*jitter* tinggi ~400ms), kluster Kubernetes mereka mulai mematikan pod secara massal dengan error `node lease renewal expired`. Pada saat yang sama, query DNS antar-pod menghasilkan respon `SERVFAIL`.

**Tantangan Arsitektur Anda**:
1. Rancang topologi sinkronisasi waktu jaringan berstandar Stratum 1 hingga Stratum 3 yang tahan terhadap pemutusan koneksi WAN secara berkepanjangan (*holdover mode*) dan bebas dari serangan spoofing.
2. Desain arsitektur DHCP Relay dan DNS Resolver lokal (*caching-forwarder*) yang memastikan sistem lokal dapat terus melakukan resolusi dan perpanjangan lease secara otonom meskipun koneksi ke Data Center pusat terputus secara total (*WAN partition*).

---

## 20. Summary
- **DNS** menyediakan translasi nama ke IP; **DNSSEC** melengkapinya dengan verifikasi kriptografis berbasis hierarki *Root Trust Anchor* -> *DS* -> *DNSKEY* -> *RRSIG*.
- **DHCP DORA** mentransisikan konfigurasi host dari broadcast lokal ke unicast lintas segmen menggunakan **DHCP Relay Agent**, yang menyisipkan IP ingress ke field `giaddr` dan menyematkan metadata lokasi fisik port klien via **Option 82**.
- **NTP** membentuk hierarki hierarkis pohon *Stratum* untuk menjamin konsensus temporal; integrasi algoritma interseksi mengeliminasi anomali jam dengan parameter *delay*, *offset*, dan *jitter*.
- **SNMPv3** mengamankan telemetri monitoring melalui model keamanan USM level `authPriv` (Otentikasi SHA + Privasi AES) atas struktur pohon MIB OID.
- **Syslog** mengonsolidasikan catatan telemetri berbasis standardisasi formula deterministik `PRI = (Facility * 8) + Severity`, menyokong observabilitas operasional menyeluruh bagi SRE dan Network Engineer.