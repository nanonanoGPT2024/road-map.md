# Kurikulum Rekayasa Jaringan Enterprise: Bab 07 - Modul 02
## Topik: Layanan Infrastruktur Inti Jaringan (DNS, DHCP, NTP)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Anycast BGP DNS**: Membangun topologi recursive and authoritative DNS berlatensi ultra-rendah menggunakan BGP Anycast berbasis FRRouting (FRR) dan PowerDNS/Unbound dengan ketahanan *failover* sub-detik.
- **Mengonfigurasi dan Mengamankan Ekosistem DNS Enterprise**: Menerapkan validasi DNSSEC secara *enforced*, mitigasi *DNS amplification attack* menggunakan *Response Rate Limiting* (RRL), serta implementasi *Split-Horizon DNS* dan *Response Policy Zone* (RPZ) untuk keamanan perimeter.
- **Membangun Infrastruktur DHCP Terdistribusi Skala Enterprise**: Menerapkan ISC Kea DHCP server dalam arsitektur *High Availability* (HA *Hot-Standby* / *Load-Balancing*) berbasis *backend* PostgreSQL, lengkap dengan *DHCP Relay Agent Information* (Option 82) untuk isolasi Layer 2.
- **Mendesain Sinkronisasi Waktu Presisi Tinggi (NTP & PTP)**: Mengonfigurasi Chrony dengan *Network Time Security* (NTS), mengelola agregasi multi-Stratum dengan algoritma seleksi Marzullo/Intersection, serta memitigasi dampak *clock skew* dan *falseticker* pada transaksi finansial terdistribusi.
- **Mengintegrasikan Observabilitas dan Automasi**: Melakukan *monitoring* performa *packet rate*, *lease exhaustion*, dan *root dispersion* menggunakan Prometheus Exporter, serta otomatisasi *provisioning* berbasis API.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- Pengetahuan solid tentang TCP/IP Stack, spesifik pada perilaku soket UDP/TCP port 53 (DNS), UDP port 67/68 (DHCP), dan UDP port 123 (NTP).
- Routing Dinamis: Penguasaan konsep eBGP dan iBGP (peering, ASN, prefix advertisement, route metrics/BGP attributes).
- Linux Systems Engineering: Manipulasi kernel parameters (`sysctl`), konfigurasi network interface (`iproute2`), firewalling (`nftables`/`iptables`), dan manajemen service (`systemd`).
- Pengalaman dasar menggunakan paket DNS legacy (BIND9) dan DHCP legacy (ISC-DHCPd).

---

### 3. Concept & Internal Architecture (Mendalam)

Layanan infrastruktur inti jaringan—DNS, DHCP, dan NTP—membentuk fondasi operasional (Underthe-Hood Subsystem) dari seluruh sistem terdistribusi. Kegagalan pada salah satu komponen ini memicu *cascading failure* sistemik di seluruh datacenter.

#### 3.1 Arsitektur BGP Anycast DNS & Edge Resolution

Anycast mentransmisikan *IP address* yang sama dari beberapa lokasi geografis atau node fisik yang berbeda. Routers di dalam jaringan mengarahkan *traffic* klien ke node terdekat berdasarkan metrik perutean IGP/EGP (OSPF cost, BGP AS-Path, atau Local Preference).

```
                      +-------------------+
                      |   Klien / Host    |
                      +---------+---------+
                                |
                   Query Anycast: 10.100.0.1
                                |
                  +-------------v-------------+
                  |  Enterprise IP Fabric     |
                  |  (Spine/Leaf BGP Core)    |
                  +-----+---------------+-----+
      BGP Metric: 10    |               |    BGP Metric: 20
+-----------------------v---+       +---v-----------------------+
| Anycast POP-A (DC-Primary)|       | Anycast POP-B (DC-Backup) |
| - FRR (BGP Speaker)       |       | - FRR (BGP Speaker)       |
|   Announces: 10.100.0.1/32|       |   Announces: 10.100.0.1/32|
| - Unbound/PowerDNS Engine |       | - Unbound/PowerDNS Engine |
| - Linux Dummy Interface   |       | - Linux Dummy Interface   |
+---------------------------+       +---------------------------+
```

##### Mekanisme Internal Kernel & Socket:
- **Dummy Interface**: IP Anycast (misal: `10.100.0.1/32`) di-*bind* ke antarmuka `dummy0` atau `lo:1` pada OS Linux, bukan pada *physical interface*. Ini mencegah *link flap* fisik menjatuhkan soket aplikasi.
- **Health-Check Route Injection**: Daemon BGP lokal (FRR/BIRD) secara kontinu memverifikasi kesehatan proses DNS melalui script *health-check*. Jika resolver gagal membalas query DNS lokal via loopback, rute /32 ditarik (*withdrawn*) seketika dari tabel BGP leaf, mengalihkan *traffic* ke node Anycast lain tanpa interupsi TCP reset berkepanjangan.
- **UDP Buffer & Memory Tuning**: Resolusi Anycast volume tinggi membutuhkan optimalisasi buffer soket kernel (`rmem_max`, `wmem_max`) dan penggunaan *flag* `SO_REUSEPORT` untuk mendistribusikan penanganan paket UDP ke seluruh core CPU melalui *Receive Side Scaling* (RSS).

#### 3.2 Arsitektur ISC Kea Modern DHCP

Arsitektur tradisional ISC-DHCPd bergantung pada *flat file lease database* (`dhcpd.leases`) yang rentan terhadap *file lock contention* dan ketiadaan kapabilitas *multi-threading*. ISC Kea mengadopsi arsitektur modular:

```
                  +--------------------------------+
                  |        Control Agent           |
                  |     (REST API Port 8000)       |
                  +---------------+----------------+
                                  |
               +------------------v------------------+
               |          KEA DHCPv4 Engine          |
               |       (Hooks & Event Handlers)      |
               +--------+-------------------+--------+
                        |                   |
            +-----------v----+         +----v-----------+
            | HA Hook Library|         | PostgreSQL DB  |
            | (Load-Balance/ |         | (Leases, Host  |
            |  Hot-Standby)  |         |  Reservations) |
            +----------------+         +----------------+
```

##### Subsistem dan Komponen Inti:
- **Core Engine (kea-dhcp4 / kea-dhcp6)**: Berperan menangani pemrosesan paket mentah DHCP (DISCOVER, OFFER, REQUEST, ACK/NAK).
- **Backend Database Abstraction**: Kea memisahkan logika logika pemrosesan DHCP dari penyimpanan status *lease*. Penggunaan *backend* PostgreSQL atau MySQL memungkinkan *horizontal read scalability*, transaksi ACID, dan replikasi multi-node.
- **High-Availability (HA) Hook Engine**: Mekanisme sinkronisasi *in-memory state* antar-peer menggunakan *REST communication channel* internal tanpa melalui *database lock*. Mode *Hot-Standby* membagi node menjadi `primary` dan `standby`, di mana pemindahan *lease allocation control* dilakukan melalui deteksi *heartbeat failover*.
- **DHCP Option 82 Processing**: *Relay Agent Information Option* (sub-option 1: Circuit ID, sub-option 2: Remote ID) disisipkan oleh *Top-of-Rack* (ToR) switch untuk mengidentifikasi port fisik atau VLAN sumber klien. Kea memproses Option 82 ini untuk mengeksekusi penugasan IP pool secara deterministik, memitigasi serangan *DHCP starvation* dari port yang tidak terotorisasi.

#### 3.3 Arsitektur Sinkronisasi Waktu: Chrony, NTS, dan PTP

Presisi sinkronisasi waktu jaringan beroperasi di bawah prinsip *deterministic latency* dan toleransi *drift* osilator kuarsa.

```
       +---------------------------------------------+
       |   Stratum-0: Atomic Clock / GNSS Satellites |
       +----------------------+----------------------+
                              | PPS / NMEA
       +----------------------v----------------------+
       |   Stratum-1: Enterprise Hardware Master     |
       |   (Rubidium Oscillator + GPS Receiver)      |
       +----------------------+----------------------+
                              | NTS / NTP UDP 123
           +------------------+------------------+
           |                                     |
+----------v----------+               +----------v----------+
|  Stratum-2 Node A   |               |  Stratum-2 Node B   |
|  (Chrony Engine)    |               |  (Chrony Engine)    |
+----------+----------+               +----------+----------+
           \                                     /
            \                                   /
             +---------------->+<--------------+
                               | NTP Peering / Client
                    +----------v----------+
                    | Stratum-3 App Hosts |
                    | (Kernel PLL Discip.)|
                    +---------------------+
```

##### Algoritma Seleksi & Disiplin Jam Internal:
- **Algoritma Marzullo & Intersection**: Chrony tidak mempercayai satu sumber waktu tunggal. Chrony mengagregasi beberapa *time sources*, menghitung interval ketidakpastian (*uncertainty interval*: $[offset - dispersion, offset + dispersion]$), mengeliminasi *falseticker* (sumber yang intervalnya tidak bertumpang-tindih dengan mayoritas), dan menentukan *truechimer*.
- **Kernel Phase-Locked Loop (PLL)**: Penyesuaian waktu dilakukan secara bertahap (*slewing*) via syscall `adjtimex()` daripada melompatkan waktu (*stepping*). *Stepping* hanya diizinkan saat inisialisasi awal boot. Hal ini melindungi integritas mesin database transaksional (seperti CockroachDB, Cassandra, Kafka) yang bergantung pada keterurutan monotonik log waktu.
- **Network Time Security (NTS)**: Mengatasi kerentanan man-in-the-middle (MitM) dan *replay attacks* pada NTP standar. NTS menggunakan TLS untuk melakukan pertukaran kunci awal (*Key Exchange* port 4460) dan menghasilkan serangkaian *cookie* AEAD (*Authenticated Encryption with Associated Data*). Setiap request NTP via port 123 diamankan dengan cookie terenkripsi ini, memastikan integritas paket tanpa mengorbankan latensi *time-stamping* hardware.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **DNS Availability** | Unicast Master-Slave statis (klien bergantung pada timeout fallback `resolv.conf`). | BGP Anycast Active-Active terdistribusi dengan *zero client-side failover delay*. |
| **DNS Security** | Plaintext, rentan terhadap cache poisoning dan *forgery*. | DNSSEC mandatory validation, Split-Horizon L3-aware, dan RPZ DNS Firewall. |
| **DHCP State** | Text-based lease file (`dhcpd.leases`), proses *single-threaded*, failover rapuh. | Multi-threaded ISC Kea, HA Hook via REST API, backend DB clustering, Option 82 auto-zoning. |
| **Time Integrity** | Unauthenticated NTPv4 publik over internet, rawan spoofing dan clock step-disruption. | Internal Stratum-1 Hardware Engine + PTP/NTS, pure frequency *slewing*, deteksi otomatis *falseticker*. |

---

### 5. How (Workflow Detail)

#### Resolusi Anycast BGP DNS dengan Validasi DNSSEC
1. Klien mengirimkan UDP/53 query ke IP Anycast `10.100.0.1`.
2. Router Spine/Leaf mengarahkan paket ke Node DNS terdekat melalui rute BGP dengan *lowest AS Path* / IGP cost.
3. Linux kernel menerima paket pada dummy interface `dummy0`, mem-parsing paket melalui sub-sistem eBPF/nftables untuk verifikasi anti-DDoS.
4. Resolver (Unbound/PowerDNS) memverifikasi apakah jawaban ada di *in-memory cache*.
5. Jika cache miss, Resolver melakukan resolusi rekursif iteratif ke Root Nameserver, TLD Nameserver, dan Authoritative Nameserver:
   - Validasi rantai kepercayaan DNSSEC: Resolver menarik *DS Record* dari parent zone, memverifikasi *DNSKEY* dari target zone, lalu memverifikasi signature digital *RRSIG* atas data *RRSET*.
   - Jika signature tidak valid, resolver mengembalikan flag `SERVFAIL` ke klien (mencegah poisoned records).
6. Paket balasan dikirimkan langsung kembali ke klien melalui rute transmisi IP reguler.

#### DHCP Lease Allocation Cycle dengan Option 82 dan Kea HA
1. Host baru memancarkan siaran `DHCPDISCOVER` di Layer 2 broadcast domain.
2. ToR Switch (DHCP Relay Agent) menangkap paket, menyuntikkan *Option 82* (Circuit-ID = "Rack-1-Leaf-2:Slot-4", Remote-ID = "Tenant-VLAN-100"), lalu meneruskan paket secara unicast ke IP Kea Primary dan Kea Backup.
3. Kea Primary memproses paket:
   - Mengekstrak Option 82 untuk memetakan permintaan ke subnet pool spesifik.
   - Mengalokasikan IP yang belum digunakan dari pool.
   - Mengirimkan update JSON state ke Kea Backup via integrasi HA Hook over TCP REST API.
4. Setelah sinkronisasi status direplikasi, Kea Primary merespons klien dengan paket `DHCPOFFER`.
5. Host merespons dengan `DHCPREQUEST`, Kea Primary merespons final dengan `DHCPACK`, dan menyimpan state *lease* di PostgreSQL.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
- **DNS Anycast**: Nomor darurat darurat tunggal nasional (misal: 112). Panggilan Anda secara otomatis disambungkan ke posko pemadam kebakaran yang terdekat secara geografis. Jika posko terdekat kebakaran atau offline, sentral telepon otomatis mengalihkan dering panggilan Anda ke posko terdekat kedua tanpa Anda perlu menekan nomor lain.
- **DHCP Option 82**: Resepsionis hotel yang memeriksa *tag kunci* yang diberikan oleh petugas lift. Petugas lift menyematkan stempel pada formulir tamu: "Tamu ini datang dari lift sayap barat lantai 3". Berdasarkan stempel tersebut, resepsionis langsung memberikan kamar khusus lantai 3 tanpa perlu menanyakan identitas manual.
- **NTP Chimers vs Falsetickers**: Sidang panel hakim beranggotakan lima orang master pembuat jam. Tiga hakim menunjukkan waktu yang hampir identik (10:00:00.001, 10:00:00.002, 09:59:59.999). Satu hakim terlambat 1 jam (falseticker), dan satu lagi jamnya mati. Tiga hakim pertama membentuk konsensus (truechimers), mengabaikan dua sisanya, dan menyesuaikan jarum detik secara sangat perlahan tanpa menghentikan detak jam.

```
       ARSIKTEKTUR KESELURUHAN SISTEM INFRASTRUKTUR INTI ENTERPRISE

   +-------------------------------------------------------------------+
   |                    TOR/Access Layer (Switching)                   |
   |   - DHCP Relay Agent (Inject Option 82: Circuit-ID & Remote-ID)   |
   |   - PTP Boundary Clock (IEEE 1588v2 Hardware Timestamps)          |
   +---------------------------------+---------------------------------+
                                     |
              +----------------------+----------------------+
              |                                             |
+-------------v--------------+               +--------------v-------------+
|    BGP Routing Fabric      |               |     BGP Routing Fabric     |
|         Spine-1            |               |          Spine-2           |
+-------------+--------------+               +--------------+-------------+
              |                                             |
   ===========+=============================================+===========
   IP Anycast Traffic (DNS: 10.100.0.1/32, NTP: 10.200.0.1/32)
   ===========+=============================================+===========
              |                                             |
+-------------v-----------------------------+ +-------------v-----------------------------+
| DNS/NTP ANYCAST NODE 01                   | | DNS/NTP ANYCAST NODE 02                   |
|                                           | |                                           |
| +---------------------------------------+ | | +---------------------------------------+ |
| | FRRouting (BGP Speaker)               | | | | FRRouting (BGP Speaker)               | |
| | - BGP Peering to Spine-1 & 2          | | | | - BGP Peering to Spine-1 & 2          | |
| | - Route Health Checker Daemon (BFD)   | | | | - Route Health Checker Daemon (BFD)   | |
| +-------------------+-------------------+ | | +-------------------+-------------------+ |
|                     | Loopback Bind       | |                     | Loopback Bind       |
| +-------------------v-------------------+ | | +-------------------v-------------------+ |
| | Services Layer:                       | | | | Services Layer:                       | |
| | - Unbound DNS (DNSSEC, RPZ, RRL)      | | | | - Unbound DNS (DNSSEC, RPZ, RRL)      | |
| | - Chrony (NTS Master, Truechimer Node)| | | | - Chrony (NTS Master, Truechimer Node)| |
| +---------------------------------------+ | | +---------------------------------------+ |
+-------------------------------------------+ +-------------------------------------------+
                      ^                                             ^
                      |               PostgreSQL HA Cluster         |
                      +-------------------+-------------------------+
                                          |
                      +-------------------v-------------------------+
                      | ISC KEA DHCP ACTIVE-STANDBY CLUSTER         |
                      |                                             |
                      | Primary Node               Standby Node     |
                      | [ Kea Engine ] <---REST---> [ Kea Engine ]  |
                      |       |                           |         |
                      |       +------------+--------------+         |
                      |                    |                        |
                      |             [ PostgreSQL ]                  |
                      +---------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Routing Anycast DNS via FRRouting (`/etc/frr/frr.conf`)

Konfigurasi berikut menyiarkan prefix Anycast DNS `/32` ke fabric spine router via eBGP, menggunakan mekanisme pemantauan kesehatan layanan.

```ini
frr version 8.5_git
frr defaults traditional
hostname dns-anycast-node01
log syslog informational
no ipv6 forwarding
service integrated-vtysh-config
!
interface dummy0
 ip address 10.100.0.1/32
!
router bgp 65010
 bgp router-id 10.100.0.11
 no bgp ebgp-requires-policy
 neighbor FABRIC peer-group
 neighbor FABRIC remote-as 65000
 neighbor FABRIC bfd
 neighbor 172.16.1.1 peer-group FABRIC
 neighbor 172.16.1.5 peer-group FABRIC
 !
 address-family ipv4 unicast
  network 10.100.0.1/32
  neighbor FABRIC activate
  neighbor FABRIC next-hop-self
  neighbor FABRIC soft-reconfiguration inbound
 exit-address-family
!
bfd
 peer 172.16.1.1
  detect-multiplier 3
  receive-interval 250
  transmit-interval 250
 !
 peer 172.16.1.5
  detect-multiplier 3
  receive-interval 250
  transmit-interval 250
 !
line vty
!
```

#### B. Konfigurasi Unbound DNS Resolver dengan DNSSEC & RPZ (`/etc/unbound/unbound.conf`)

Implementasi resolver hardened dengan performa multi-thread, pembatasan query rate, dan isolasi DNS malang via Response Policy Zone (RPZ).

```yaml
server:
    verbosity: 1
    interface: 10.100.0.1
    interface: 127.0.0.1
    port: 53
    do-ip4: yes
    do-udp: yes
    do-tcp: yes
    
    # Performa Concurrency & Tuning Kernel
    num-threads: 4
    msg-cache-slabs: 4
    rrset-cache-slabs: 4
    infra-cache-slabs: 4
    key-cache-slabs: 4
    rrset-cache-size: 512m
    msg-cache-size: 256m
    so-rcvbuf: 8m
    so-sndbuf: 8m
    so-reuseport: yes

    # Keamanan & DNSSEC Validation
    auto-trust-anchor-file: "/var/lib/unbound/root.key"
    harden-glue: yes
    harden-dnssec-stripped: yes
    harden-below-nxdomain: yes
    harden-referral-path: yes
    qname-minimisation: yes
    use-caps-for-id: no

    # Mitigasi Serangan (RRL & Flood)
    ratelimit: 1000
    ip-ratelimit: 200

    # ACL Akses Jaringan Internal
    access-control: 127.0.0.0/8 allow
    access-control: 10.0.0.0/8 allow
    access-control: 0.0.0.0/0 refuse

    # Custom RPZ Integration
    module-config: "respip validator iterator"

rpz:
    name: "malware-defense.zone"
    zonefile: "/etc/unbound/zones/blocked-malware.zone"
    rpz-action-override: nxdomain
    rpz-log: yes
    rpz-log-name: "MALWARE_DROP"
```

#### C. Konfigurasi Produksi ISC Kea DHCP Server (`/etc/kea/kea-dhcp4.conf`)

Konfigurasi DHCPv4 enterprise dengan failover High-Availability (Hot-Standby), PostgreSQL backend, dan evaluasi paket berbasis Option 82 Circuit ID.

```json
{
  "Dhcp4": {
    "interfaces-config": {
      "interfaces": [ "eth0/172.16.10.10" ],
      "dhcp-socket-type": "raw"
    },
    "lease-database": {
      "type": "postgresql",
      "name": "keadb",
      "user": "keauser",
      "password": "SecureEnterprisePassword123!",
      "host": "postgres-cluster.corp.internal",
      "port": 5432,
      "max-reconnect-tries": 5,
      "reconnect-wait-time": 2000
    },
    "control-socket": {
      "socket-type": "unix",
      "socket-name": "/run/kea/kea4-ctrl-socket"
    },
    "hooks-libraries": [
      {
        "library": "/usr/lib/x86_64-linux-gnu/kea/hooks/libdhcp_lease_cmds.so"
      },
      {
        "library": "/usr/lib/x86_64-linux-gnu/kea/hooks/libdhcp_ha.so",
        "parameters": {
          "high-availability": [
            {
              "this-server-name": "dhcp-node-01",
              "mode": "hot-standby",
              "heartbeat-delay": 10000,
              "max-response-delay": 60000,
              "max-ack-delay": 5000,
              "max-unacked-clients": 10,
              "peers": [
                {
                  "name": "dhcp-node-01",
                  "url": "http://172.16.10.10:8000/",
                  "role": "primary",
                  "auto-failover": true
                },
                {
                  "name": "dhcp-node-02",
                  "url": "http://172.16.10.11:8000/",
                  "role": "standby",
                  "auto-failover": true
                }
              ]
            }
          ]
        }
      }
    ],
    "client-classes": [
      {
        "name": "Floor1_Engineering",
        "test": "substring(relay4[1].hex, 0, 8) == 'FL1-ENG-'"
      }
    ],
    "subnet4": [
      {
        "id": 1001,
        "subnet": "10.20.100.0/24",
        "client-class": "Floor1_Engineering",
        "pools": [ { "pool": "10.20.100.50 - 10.20.100.250" } ],
        "option-data": [
          {
            "name": "routers",
            "data": "10.20.100.1"
          },
          {
            "name": "domain-name-servers",
            "data": "10.100.0.1"
          },
          {
            "name": "ntp-servers",
            "data": "10.200.0.1"
          }
        ]
      }
    ]
  }
}
```

#### D. Konfigurasi Chrony NTP dengan Deteksi Falseticker & NTS (`/etc/chrony/chrony.conf`)

Konfigurasi server NTP Chrony presisi tinggi dengan *hardware time-stamping*, filter chimers, dan proteksi Network Time Security (NTS).

```ini
# Upstream Stratum-1 Servers dengan Autentikasi NTS
server time.cloudflare.com iburst nts maxpoll 6
server nts.ntp.se iburst nts maxpoll 6
server ptbtime1.ptb.de iburst nts maxpoll 6
server time.fu-berlin.de iburst nts maxpoll 6

# Local Hardware Reference Clock (GPS/PPS jika tersedia)
# refclock PPS /dev/pps0 lock NMEA refid PPS precision 1e-9

# Batasan toleransi seleksi: minimal 3 sumber waktu sinkron
minsources 3

# Batasan clock drift (falseticker isolation threshold)
maxdistance 0.05
maxdrift 100

# Terapkan disiplin slewing murni (JANGAN gunakan step di produksi secara reguler)
# Hanya izinkan step jika error > 1 detik pada 3 query pertama setelah daemon start
makestep 1.0 3

# Hardware Timestamping pada NIC
hwtimestamp *

# Sajikan NTS Server ke Klien Enterprise
ntsserverkey /etc/chrony/nts-server.key
ntsservercert /etc/chrony/nts-server.crt
ntsdumpdir /var/lib/chrony

# Jaringan yang diizinkan mengakses pool waktu
allow 10.0.0.0/8
bindaddress 10.200.0.1

# Logging & Drift Persistence
driftfile /var/lib/chrony/chrony.drift
log tracking measurements statistics
logdir /var/log/chrony
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden Sinkronisasi Transaksi Finansial & DNS Blackhole di Bank Skala Regional

**Profil Infrastruktur:**
- Bank FinTech dengan volume transaksi 15.000 TPS.
- Core Database: Multi-region CockroachDB (membutuhkan toleransi deviasi clock < 250ms).
- Datacenter: Active-Active Multi-Zone (DC-Jakarta, DC-Surabaya).

**Akar Masalah (Incident Breakdown):**
1. **Clock Desync Incident**: Operator mengonfigurasi `ntpd` standar mengarah ke single NTP pool publik via ISP upstream. ISP mengalami *BGP route leaking*, mengakibatkan fluktuasi latensi paket NTP dari 5ms melompat ke 480ms secara acak. `ntpd` mengalami ketidakstabilan osilasi lokal, mengakibatkan *clock drift* antar node CockroachDB mencapai 320ms. CockroachDB otomatis menonaktifkan *lease-holder transactions* untuk mencegah korupsi data (*transaction commit wait boundary violated*). Sistem transaksi payment gateway down selama 42 menit.
2. **DNS Outage Simultan**: Upstream ISP mengalami packet loss ke DNS Root, server cache recursive resolver lokal mengalami lonjakan konkurensi koneksi thread pool karena tidak ada limitasi recursive timeout, menyebabkan port exhaustion (semua ephemeral UDP source port 1024-65535 terpakai habis). Server menolak *inbound lookup*.

**Solusi Arsitektural Menyeluruh:**
1. **Remediasi Waktu (NTP/NTS)**:
   - Penghentian `ntpd` legacy, migrasi total ke `chrony`.
   - Penerapan 2 unit hardware NTP Appliance (GNSS/Rubidium atomic clock - Stratum 1) lokal di masing-masing datacenter, dilengkapi antarmuka PPS (*Pulse Per Second*).
   - Pengaktifan NTS dengan cross-peering Stratum-2 server. Jika koneksi satelit putus, osilator Rubidium menjaga stabilitas waktu dengan akurasi mikrodetik hingga 72 jam (*holdover mode*).
   - Penyetelan parameter `makestep 0 0` (hanya *slewing*, tidak ada *clock jump* di sistem operasi database).
2. **Remediasi DNS (Anycast Overhaul)**:
   - Penerapan arsitektur Anycast via BGP menggunakan FRR di setiap ToR switch.
   - Pemanfaatan Unbound dengan mitigasi RRL dan aktivasi fitur `qname-minimisation: yes` untuk mereduksi *unnecessary upstream query*.
   - Deploy modul RPZ untuk mengarahkan permintaan domain yang di-poison langsung ke rute internal status `NXDOMAIN`.

**Hasil Pasca Implementasi:**
- Root dispersion stabil di level $< 0.8\text{ ms}$ di seluruh cluster DB multi-region.
- *Zero single-point-of-failure* pada DNS layer; penarikan rute BGP otomatis memindahkan beban dalam tempo $\le 750\text{ ms}$ saat terjadi degradasi daemon.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan | Kerugian & Konsekuensi | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **DNS Anycast via BGP** | Rute failover sangat cepat, kueri berlatensi minimum (lokal), menyerap serangan DDoS secara merata. | Kompleksitas *routing asymmetry*, *troubleshooting* paket TCP terputus jika konvergensi BGP bergetar (*flapping*). | Resolusi recursive internal enterprise kampus/multi-DC atau authoritative publik. |
| **Kea PostgreSQL Backend** | *Centralized single source of truth*, query analitik transaksional langsung, skalabilitas HA elastis. | *Higher latency* alokasi lease dibanding memory storage murni, ketergantungan pada reliabilitas DB cluster. | Datacenter modern dengan kebutuhan orkestrasi dinamis dan API IPAM sync. |
| **Chrony Slew vs Step** | Tidak pernah memutar balik waktu secara tiba-tiba (*monotonic clock integrity* terlindungi penuh). | Membutuhkan durasi waktu signifikan untuk mengoreksi offset drift yang terlanjur besar (laju slew ~8.33%). | Database transaksional enterprise, node audit PCI-DSS, cluster Kubernetes. |
| **Enforced DNSSEC** | Jaminan integritas kriptografis mutlak atas record yang diselesaikan, anti MitM. | Ukuran paket membesar drastis (fragmentasi UDP $\to$ TCP fallback), dependensi mutlak pada presisi jam sistem lokal. | Seluruh resolver DNS modern yang menangani resource sensitif internal/eksternal. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi:
1. **Clock Desync Mengakibatkan DNSSEC Bogus Validation**: Jika jam server drift lebih dari beberapa menit, validasi DNSSEC menganggap tanda tangan kriptografi `RRSIG` telah *expired* atau *not yet valid*. Akibatnya, resolver melempar `SERVFAIL` massal ke seluruh klien.
2. **Anycast BGP Flapping Tanpa Dampak Health-Check**: Mengonfigurasi penyiaran BGP langsung pada static IP tanpa verifikasi port status DNS lokal (`dig @127.0.0.1 SOA`). Akibatnya, router terus mengirimkan paket ke node Anycast yang aplikasinya sudah crash (Blackholing).
3. **DHCP Option 82 Sub-Option Mismatch**: Switch L2 menyisipkan Option 82 dengan format biner tertentu, namun konfigurasi DHCP server memparsingnya sebagai representasi ASCII murni (atau sebaliknya). Akibatnya, klien gagal mencocokkan *client-class* dan dilempar ke pool default atau tidak mendapat lease sama sekali.

#### Panduan Praktis Perintah Debugging:

##### DNS Debugging & DNSSEC Tracing:
```bash
# Lakukan query iteratif penuh dengan validasi jejak rantai DNSSEC
dig +trace +dnssec api.bank.internal @10.100.0.1

# Analisis pemetaan flag DNSSEC (AD: Authenticated Data, CD: Checking Disabled)
dig api.bank.internal @10.100.0.1 +dnssec +multiline

# Validasi socket buffer drop pada interface network
netstat -su | grep -E "buffer errors|receive errors"
```

##### DHCP Kea HA & State Debugging:
```bash
# Memeriksa status High-Availability Kea via Control Socket
echo '{"command": "ha-status-get"}' | socat - UNIX-CONNECT:/run/kea/kea4-ctrl-socket | jq .

# Memeriksa keterisian lease pada pool tertentu via CLI
echo '{"command": "lease4-get-all", "arguments": {"subnets": [1001]}}' | socat - UNIX-CONNECT:/run/kea/kea4-ctrl-socket | jq .

# Analisis traffic relay Option 82 menggunakan tcpdump
tcpdump -vvv -nn -i eth0 port 67 or port 68
```

##### Chrony & Time Dispersion Debugging:
```bash
# Melihat status tracking osilator sistem lokal
chronyc tracking

# Evaluasi seluruh source upstream (melihat falseticker 'x' vs truechimer '*')
chronyc sources -v

# Memeriksa stabilitas jitter dan dispersi relatif
chronyc sourcestats -v

# Memeriksa konektivitas handshake Network Time Security (NTS)
chronyc -N authdata
```

---

### 11. Best Practices (Production Checklist)

#### Pre-Production Validation Checklist:
- [ ] **DNS**: Dummy interface untuk Anycast IP dikonfigurasi dengan flag `arp_ignore=1` dan `arp_announce=2` pada sysctl Linux untuk mencegah ARP poisoning di Layer 2.
- [ ] **DNS**: `edns-buffer-size` disetel secara proporsional (disarankan 1232 byte sesuai DNS Flag Day) guna meminimalkan fragmentasi paket UDP over Ethernet (MTU 1500).
- [ ] **DHCP**: Parameter failover Kea `max-response-delay` diuji secara empiris di lab untuk memastikan node standby tidak memicu *split-brain lease allocation*.
- [ ] **NTP**: Maksimal jitter upstream diverifikasi $< 5\text{ ms}$, dengan minimal 4 sumber stratum independen dari provider/network path terpisah guna menjamin ketersediaan kuorum seleksi Marzullo.
- [ ] **OS Kernel**: Tuning soket UDP resolusi tinggi diterapkan pada `/etc/sysctl.d/99-network-core.conf`:
  ```ini
  net.core.rmem_max = 16777216
  net.core.wmem_max = 16777216
  net.core.rmem_default = 2097152
  net.core.wmem_default = 2097152
  net.ipv4.udp_rmem_min = 8192
  net.ipv4.udp_wmem_min = 8192
  net.core.netdev_max_backlog = 10000
  ```

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori proyek: `hands-on/m02/`.

#### Task: Mengimplementasikan Edge DNS Anycast dengan BFD Failover Otomatis dan Validasi Waktu Chrony

```
hands-on/m02/
├── config/
│   ├── chrony.conf
│   ├── frr.conf
│   └── unbound.conf
├── scripts/
│   ├── bgp-healthcheck.sh
│   └── setup-environment.sh
└── docker-compose.yml
```

##### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  spine-router:
    image: frrouting/frr:v8.5.2
    container_name: spine-router
    privileged: true
    volumes:
      - ./config/frr-spine.conf:/etc/frr/frr.conf
      - ./config/daemons:/etc/frr/daemons
    networks:
      fabric-net:
        ipv4_address: 172.20.0.2

  dns-node:
    image: frrouting/frr:v8.5.2
    container_name: dns-anycast-srv
    privileged: true
    cap_add:
      - NET_ADMIN
      - SYS_TIME
    volumes:
      - ./config/frr.conf:/etc/frr/frr.conf
      - ./config/daemons:/etc/frr/daemons
      - ./config/unbound.conf:/etc/unbound/unbound.conf
      - ./config/chrony.conf:/etc/chrony/chrony.conf
      - ./scripts/bgp-healthcheck.sh:/usr/local/bin/bgp-healthcheck.sh
    networks:
      fabric-net:
        ipv4_address: 172.20.0.10
    command: /bin/bash -c "chmod +x /usr/local/bin/bgp-healthcheck.sh && /usr/lib/frr/frrinit.sh start && /usr/local/bin/bgp-healthcheck.sh & tail -f /dev/null"

networks:
  fabric-net:
    ipam:
      driver: default
      config:
        - subnet: 172.20.0.0/24
```

##### File: `hands-on/m02/config/daemons`
```ini
zebra=yes
bgpd=yes
ospfd=no
ospf6d=no
ripd=no
ripngd=no
isisd=no
fabricd=no
pimd=no
nhrpd=no
eigrpd=no
babeld=no
sharpd=no
pbrd=no
bfdd=yes
fabricd=no
vrrpd=no
```

##### File: `hands-on/m02/config/frr-spine.conf`
```ini
frr version 8.5_git
frr defaults traditional
hostname spine-router
no ipv6 forwarding
!
router bgp 65000
 bgp router-id 172.20.0.2
 no bgp ebgp-requires-policy
 neighbor 172.20.0.10 remote-as 65010
 neighbor 172.20.0.10 bfd
 !
 address-family ipv4 unicast
  neighbor 172.20.0.10 activate
 exit-address-family
!
bfd
 peer 172.20.0.10
 exit
!
```

##### File: `hands-on/m02/config/frr.conf`
```ini
frr version 8.5_git
frr defaults traditional
hostname dns-anycast-srv
no ipv6 forwarding
!
interface dummy0
 ip address 10.100.0.1/32
!
router bgp 65010
 bgp router-id 172.20.0.10
 no bgp ebgp-requires-policy
 neighbor 172.20.0.2 remote-as 65000
 neighbor 172.20.0.2 bfd
 !
 address-family ipv4 unicast
  neighbor 172.20.0.2 activate
 exit-address-family
!
bfd
 peer 172.20.0.2
 exit
!
```

##### File: `hands-on/m02/scripts/bgp-healthcheck.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

ANYCAST_IP="10.100.0.1/32"
DUMMY_INT="dummy0"

# Inisialisasi dummy interface jika belum tersedia
if ! ip link show "$DUMMY_INT" > /dev/null 2>&1; then
    ip link add "$DUMMY_INT" type dummy
    ip addr add "$ANYCAST_IP" dev "$DUMMY_INT"
    ip link set "$DUMMY_INT" up
fi

echo "Memulai loop pemantauan kesehatan DNS Anycast..."

while true; do
    # Health check sederhana: Memeriksa apakah unbound listen pada port 53
    # Dalam implementasi riil: lakukan query aktif dengan dig/drill
    HEALTH_STATUS=0
    
    # Cek jika port 53 aktif
    if nc -z -u -w1 127.0.0.1 53 2>/dev/null; then
        HEALTH_STATUS=1
    fi

    # Manipulasi pengumuman rute via vtysh dinamis
    if [ "$HEALTH_STATUS" -eq 1 ]; then
        vtysh -c "configure terminal" \
              -c "router bgp 65010" \
              -c "address-family ipv4 unicast" \
              -c "network $ANYCAST_IP" \
              -c "end" > /dev/null 2>&1 || true
    else
        # DNS Service Mati -> Tarik rute Anycast secepat mungkin!
        vtysh -c "configure terminal" \
              -c "router bgp 65010" \
              -c "address-family ipv4 unicast" \
              -c "no network $ANYCAST_IP" \
              -c "end" > /dev/null 2>&1 || true
    fi

    sleep 2
done
```

##### Eksekusi Pengujian Step-by-Step:
1. Inisialisasi lingkungan lab:
   ```bash
   cd hands-on/m02/
   docker compose up -d
   ```
2. Verifikasi status peering BGP pada `spine-router`:
   ```bash
   docker exec -it spine-router vtysh -c "show ip bgp summary"
   docker exec -it spine-router vtysh -c "show ip route"
   ```
   *Ekspektasi Output:* Rute `10.100.0.1/32` muncul via next-hop `172.20.0.10`.
3. Simulasikan kegagalan service DNS:
   ```bash
   # Matikan service Unbound (atau port 53) di dalam container dns-node
   docker exec -it dns-anycast-srv pkill -f unbound || true
   ```
4. Verifikasi penarikan rute pada Spine Router dalam $\le 2$ detik:
   ```bash
   docker exec -it spine-router vtysh -c "show ip route 10.100.0.1"
   ```
   *Ekspektasi Output:* `% Network not in table`. Rute otomatis diisolasi.

---

### 13. Exercise

#### Level Easy
Konfigurasikan sebuah instance Chrony klien yang terhubung ke server waktu lokal `10.200.0.1`. Tuliskan konfigurasi `/etc/chrony/chrony.conf` agar Chrony melakukan sinkronisasi dengan polling interval agresif (antara $2^2$ hingga $2^4$ detik) dan mencegah waktu melompat (*zero stepping*).

#### Level Medium
Sebuah datacenter enterprise menggunakan ISC Kea DHCP. Anda ditugaskan membuat blok konfigurasi `client-classes` di Kea yang mendeteksi Vendor Class Identifier (DHCP Option 60). Jika Option 60 bernilai `"Cisco AP c9120"`, berikan IP dari subnet khusus `10.50.99.0/24` dengan opsi vendor-specific Option 43 diset ke IP kontroler nirkabel `10.10.10.50`. Tuliskan deklarasi format JSON-nya.

#### Level Hard
Sebuah arsitektur recursive DNS berbasis Anycast mengalami serangan *random subdomain attack* (*water torture attack*) yang menguras upstream connection pool. Buatlah rancangan konfigurasi Response Rate Limiting (RRL) dan script mitigasi otomatis eBPF/XDP atau Unbound ratelimit untuk membatasi lookup domain target ke maksimum 50 QPS per client prefix `/24`, sembari tetap mengizinkan traffic resolusi domain valid lainnya berjalan tanpa latency degradation.

---

### 14. Challenge

**Skenario Rekayasa:**
Anda adalah Principal Infrastructure Architect di sebuah bursa perdagangan aset digital (Crypto/Equities Exchange). Sistem *matching engine* Anda tersebar di 3 Datacenter (AWS DirectConnect, Equinix Jakarta, Equinix Singapura). Regulator keuangan memberlakukan aturan baru:
1. Seluruh transaksi wajib memiliki stempel waktu dengan deviasi maksimal $\pm 500\ \mu\text{s}$ (mikrodetik) dari UTC (mengikuti standar referensi akurasi MiFID II RTS 25).
2. DHCP server dilarang menggunakan konfigurasi broadcast Layer-2 murni demi mencegah insiden *rogue DHCP* di lingkungan bare-metal Kubernetes multi-tenant.
3. Seluruh resolusi internal database wajib menggunakan DNSSEC terotentikasi, namun latensi kueri rata-rata tidak boleh melebihi $1.5\text{ ms}$.

**Tugas Arsitektur:**
1. Desainlah arsitektur fisik & logis end-to-end yang memadukan GNSS Stratum-1 Receiver, PTP (IEEE 1588v2) Telecom/Enterprise Profile, ISC Kea DHCP dengan Option 82, dan Anycast Unbound/PowerDNS Resolver.
2. Gambarkan topologi jaringan lengkap (dalam bentuk ASCII diagram) dari physical switch hingga container network namespace.
3. Definisikan analisis matematis batas dispersi waktu (*Time Dispersion Budget*) untuk membuktikan rancangan Anda tidak melanggar batas regulasi $\pm 500\ \mu\text{s}$.
4. Tentukan kebijakan mitigasi komprehensif saat konstelasi satelit GPS mengalami *jamming* atau *spoofing*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa fungsi mendasar penambahan antarmuka `dummy` pada sistem operasi Linux dalam arsitektur routing BGP Anycast?
2. Mengapa protokol NTP default (port UDP 123) rentan terhadap serangan Man-in-the-Middle dibanding Network Time Security (NTS)?
3. Pada pertukaran pesan DHCP DORA, pada tahap manakah DHCP Relay Agent menyuntikkan *Option 82* ke dalam payload paket?
4. Apa arti status `*` (asterisk) dan `+` (plus) pada output kolom pertama perintah `chronyc sources`?
5. Mengapa disarankan menyetel `edns-buffer-size` sebesar 1232 byte pada konfigurasi resolver DNS modern?

#### Bagian 2: Intermediate (5 Pertanyaan)
1. Jelaskan perbedaan mendasar antara mode Kea HA *Load-Balancing* dan *Hot-Standby*. Pada skenario apa *Hot-Standby* mutlak dipilih dibanding *Load-Balancing*?
2. Bagaimana mekanisme *qname-minimisation* pada Unbound meningkatkan privasi kueri dan mengurangi beban rekursif pada Root Nameserver?
3. Dalam perhitungan seleksi waktu Chrony, bagaimana algoritma seleksi mengidentifikasi dan menangani sebuah node upstream yang berstatus *falseticker*?
4. Apa yang menyebabkan fenomena *DNS Amplification Attack*, dan bagaimana mekanisme *Response Rate Limiting* (RRL) memitigasi serangan ini secara efektif?
5. Mengapa manipulasi parameter `sysctl` `arp_ignore` dan `arp_announce` sangat krusial ketika mengonfigurasi IP Anycast yang sama di beberapa server dalam satu Layer-2 broadcast domain?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

##### Kasus A (DNSSEC Cascade Outage):
Sebuah tim NOC melakukan pembaruan sertifikat sistem operasi dan secara tidak sengaja mematikan layanan NTP selama 4 jam. Ketika jam server meleset mundur 48 jam, tiba-tiba seluruh kueri DNS internal berbasis DNSSEC mengembalikan kode status `SERVFAIL`. Klien tidak dapat mengakses API internal gateway.
- *Pertanyaan*: Analisis rantai kausalitas kegagalan ini secara mendalam pada level protokol DNSSEC! Mengapa menonaktifkan validasi DNSSEC sementara (`val-permissive-mode: yes`) menyelesaikan masalah seketika, dan apa risiko keamanan fatalnya?

##### Kasus B (DHCP Starvation & Option 82 Misconfiguration):
Sebuah switch baru ditambahkan ke jaringan tanpa konfigurasi `ip dhcp snooping information option allow-untrusted`. Switch ToR tersebut merelay paket DHCP klien dengan mengosongkan nilai Option 82. Akibatnya, server ISC Kea menolak memberikan *lease* kepada ratusan server bare-metal baru yang sedang melakukan PXE Boot.
- *Pertanyaan*: Bagaimana Kea mengevaluasi ketiadaan opsi ini berdasarkan aturan `client-classes` di atas? Tuliskan langkah remediasi konfigurasi pada switch access dan konfigurasi fallback Kea agar node tetap dapat booting darurat!

##### Kasus C (Anycast BGP Flapping & TCP DNS Failure):
Node DNS Anycast menerima lonjakan kueri berukuran besar yang memaksa klien melakukan fallback ke TCP/53. Namun, banyak klien melaporkan timeout (`Connection reset by peer` atau `ETIMEDOUT`). Investigasi jaringan menunjukkan adanya *route flap* eBGP minor setiap 30 detik antara Spine-1 dan DNS Node-01.
- *Pertanyaan*: Mengapa protokol UDP toleran terhadap Anycast *route flapping*, sedangkan TCP/53 mengalami kegagalan total (*broken connections*) pada skenario tersebut? Bagaimana teknologi BGP BFD dan Multipath ECMP dikonfigurasi untuk mengatasi isu ini?

---

### 16. Summary

1. **DNS Anycast via BGP** menghilangkan kelemahan laten failover berbasis DNS client timeout. Dengan menyiarkan IP /32 yang sama ke fabric BGP Spine/Leaf yang dipadukan dengan daemon health-check lokal, kegagalan node dapat dialihkan dalam skala sub-detik secara mulus.
2. **Validasi DNSSEC** merupakan keharusan mutlak dalam integritas rantai resolusi masa kini, memitigasi serangan DNS cache poisoning dan spoofing. Pemanfaatan buffer DNS yang terstandarisasi (1232 byte) mencegah fragmentasi paket IP di tingkat WAN.
3. **ISC Kea DHCP** menggantikan era ISC-DHCPd legacy dengan menyediakan platform modular berkemampuan mutakhir: arsitektur REST Control API, integrasi status lease ke RDBMS (PostgreSQL) terdistribusi, High Availability Hook Engine, dan klasifikasi klien deterministik berbasis DHCP Option 82.
4. **Sinkronisasi Waktu Enterprise (NTP/NTS/PTP)** adalah tulang punggung konsistensi sistem terdistribusi modern. Chrony mengeliminasi resiko lompatan waktu melalui disiplin slewing murni, melindungi transaksi database transaksional dari korupsi data, dan menyaring anomali *falseticker* menggunakan algoritma seleksi matematis yang ketat. Kunci keberhasilan sinkronisasi terletak pada kombinasi hardware Stratum-1 lokal yang redundan dan autentikasi paket berbasis Network Time Security.