# BAB 04: Layer 3 Routing Fundamentals, Static Routing & FHRP
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Siklus Forwarding Hardware:** Mengartikulasikan mekanisme internal *Longest Prefix Match* (LPM), translasi dari *Routing Information Base* (RIB) ke *Forwarding Information Base* (FIB), serta struktur data Cisco Express Forwarding (CEF) / Arista Hash-based MTrie dan pemetaan TCAM (*Ternary Content Addressable Memory*).
2. **Merancang Deterministic Static Failover:** Mengonfigurasi dan memvalidasi *Floating Static Routing* terakselerasi dengan *Bidirectional Forwarding Detection* (BFD) sub-second timer dan IP SLA tracking untuk mencapai *failover* deterministik di bawah 100 milidetik.
3. **Mengimplementasikan Advanced First Hop Redundancy Protocol (FHRP):** Merancang arsitektur redundansi gateway enterprise-grade menggunakan VRRPv3 (Dual-Stack IPv4/IPv6) dan HSRPv2, mencakup tuning *sub-second timers*, *hierarchical object tracking*, serta mitigasi *split-brain*.
4. **Mencegah dan Memecahkan Masalah Routing Anomali:** Mengidentifikasi, mengisolasi, dan merekayasa ulang topologi bermasalah seperti *asymmetric routing* pada inspeksi stateful firewall, fenomena *blackholing* akibat *unverified reachability*, dan kelelahan kapasitas TCAM.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
* Fundamental Layer 2: Switching, VLAN, IEEE 802.1Q Trunking, Spanning Tree Protocol (RSTP/MSTP).
* Fundamental IPv4 & IPv6: Struktur subnetting VLSM, CIDR, format paket IP (TTL, Next-Hop, Checksum).
* Mekanisme resolusi Layer 2 ke Layer 3: Protokol Address Resolution Protocol (ARP), Gratuitous ARP (GARP), dan IPv6 Neighbor Discovery Protocol (NDP).
* Operasional dasar command-line interface (CLI) Linux networking (`iproute2`, sysctl) dan Network Operating System berbasis EOS/IOS-XE.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Kontrol vs. Forwarding Plane: Dari RIB ke FIB dan TCAM

Dalam arsitektur switch/router enterprise modern, terdapat pemisahan absolut antara *Control Plane* dan *Data Plane* (Forwarding Plane).

```
   +--------------------------------------------------------+
   |                     CONTROL PLANE                      |
   |                                                        |
   |   [ BGP ]   [ OSPF ]   [ Static Routes ]   [ Connected]|
   |      \         |              /                 /      |
   |       v        v             v                 v       |
   |  +--------------------------------------------------+  |
   |  |        RIB (Routing Information Base)            |  |
   |  |          - Administrative Distance               |  |
   |  |          - Metrik Protokol                       |  |
   |  +--------------------------------------------------+  |
   |                           |                            |
   |                           v (Kompilasi Jalur Terbaik)   |
   |  +--------------------------------------------------+  |
   |  |        FIB (Forwarding Information Base)         |  |
   |  |          - Prefix -> Next-Hop Resolution         |  |
   |  +--------------------------------------------------+  |
   |                           |                            |
   +---------------------------|----------------------------+
                               | IPC / DMA Synchronization
   +---------------------------|----------------------------+
   | DATA PLANE (ASIC Hardware)|                            |
   |                           v                            |
   |  +--------------------------------------------------+  |
   |  |     TCAM (Ternary Content Addressable Memory)    |  |
   |  |     LPM Lookup (0, 1, Don't Care) 1 Clock Cycle  |  |
   |  +--------------------------------------------------+  |
   |  |         Adjacency Table / Rewrite Engine         |  |
   |  |         - Dest MAC, Src MAC, Egress Interface    |  |
   |  +--------------------------------------------------+  |
   +--------------------------------------------------------+
```

1. **Routing Information Base (RIB):** 
   Database berbasis memori software (RAM) yang dikelola oleh proses sistem operasi (misalnya, `sysdb`, `routed`, atau zebra/frr). RIB menampung seluruh kandidat rute dari setiap protokol routing, jalur statik, dan interface lokal. Ketika beberapa protokol menawarkan rute ke prefix yang identik, rute dengan *Administrative Distance* (AD) terendah diinjeksi ke tabel rute aktif.
2. **Forwarding Information Base (FIB):** 
   Cerminan terkompresi dari RIB yang mengeliminasi rekursi rute. Jika suatu static route menunjuk ke IP next-hop yang membutuhkan lookup lanjutan, kontrol plane menyelesaikan rekursi tersebut secara tuntas sebelum mengompilasi entri ke dalam FIB. Setiap entri FIB memetakan prefix secara langsung ke *egress interface* dan pointer *adjacency*.
3. **TCAM & MTrie Hardware Lookup:** 
   Pada platform forwarding perangkat keras (misal: Broadcom Trident/Tomahawk, Cisco Silicon One), proses LPM tidak dapat menggunakan algoritma software linear $O(N)$ atau binary tree standar karena latency yang tidak menentu. Lookup diimplementasikan pada:
   * **TCAM:** Menggunakan cell memori dengan 3 kondisi: `0`, `1`, dan `X` (*Don't Care* / Wildcard). TCAM memungkinkan evaluasi jutaan entri secara paralel dalam satu siklus clock clocking ASIC.
   * **Multi-bit Trie (MTrie):** Representasi tree yang dikelompokkan dalam langkah tetap (misal: skema 8-8-8-8 bit). Forwarding engine menavigasi tabel pointer memori berkecepatan tinggi (SRAM) untuk menemukan entri adjacency dalam jumlah siklus yang deterministik.

#### 3.2 Longest Prefix Match (LPM) Processing Logic

Ketika paket IPv4 masuk ke ingress pipeline ASIC:
1. Header paket diekstraksi oleh *Parser*.
2. IP tujuan (misalnya `192.168.1.130`) diuji secara bersamaan terhadap seluruh entri tabel rute.
3. Asumsikan entri berikut ada di FIB:
   * `0.0.0.0/0` (Default Gateway)
   * `192.168.0.0/16` (Enterprise Supernet)
   * `192.168.1.128/25` (Subnet Spesifik)
   * `192.168.1.130/32` (Host Route)
4. Hardware memilih prefix dengan panjang mask terpanjang (`/32` mengalahkan `/25`, `/25` mengalahkan `/16`, dan `/16` mengalahkan `/0`).
5. Pointer adjacency yang diasosiasikan dengan prefix `/32` langsung diakses untuk mengidentifikasi interface keluar dan format enkapsulasi Layer 2.

#### 3.3 Anatomi Operasional First Hop Redundancy Protocols

FHRP menyediakan abstraksi gateway Layer 3 tunggal yang tangguh untuk host yang berada di segmen broadcast Layer 2 yang sama, menggunakan kombinasi Virtual IP (VIP) dan Virtual MAC (VMAC).

##### VRRPv2 vs. VRRPv3 vs. HSRPv2

| Parameter | VRRPv2 (RFC 3768) | VRRPv3 (RFC 5798) | HSRPv2 (Cisco Proprietary) |
| :--- | :--- | :--- | :--- |
| **Dukungan Protokol** | IPv4 saja | Dual-Stack (IPv4 & IPv6) | Dual-Stack (IPv4 & IPv6) |
| **Alamat Multicast** | `224.0.0.18` | `224.0.0.18` (v4), `FF02::12` (v6) | `224.0.0.102` (v4), `FF02::66` (v6) |
| **Format Virtual MAC** | `00:00:5E:00:01:{VRID}` | `00:00:5E:00:01:{VRID}` (v4)<br>`00:00:5E:00:02:{VRID}` (v6) | `00:00:0C:9F:F{Group}` (v4)<br>`00:05:73:A0:0{Group}` (v6) |
| **Timer Standar** | Advertisement: 1 detik | Advertisement: 1 detik (Mendukung milidetik natif) | Hello: 3 detik, Hold: 10 detik (Sub-second configurable) |
| **State Machine** | Initialize, Backup, Master | Initialize, Backup, Master | Disabled, Init, Listen, Speak, Standby, Active |

##### Mekanisme Master Failover & Gratuitous ARP (GARP)
1. **Master Election:** Router dengan prioritas tertinggi (default: 100, range: 1–254) terpilih sebagai *Master* (atau *Active* pada terminologi HSRP). Jika prioritas identik, alamat IP fisik interface tertinggi menang.
2. **Keepalive Signal:** Master mengirimkan packet advertisement periodik ke alamat multicast FHRP. Router Backup mendengarkan advertisement ini dan mereset `Master_Down_Timer`.
3. **Dead-Interval Detection:** Jika Backup tidak menerima advertisement dalam durasi:
   $$\text{Master\_Down\_Timer} = (3 \times \text{Advertisement\_Interval}) + \text{Skew\_Time}$$
   $$\text{Skew\_Time} = \frac{256 - \text{Priority}}{256} \times \text{Advertisement\_Interval}$$
   maka Backup memicu transisi state ke *Master*.
4. **GARP Flood & MAC-Table Refresh:** Seketika berpindah menjadi Master, router baru memancarkan paket broadcast Gratuitous ARP (GARP) ke segmen Layer 2. Frame ini menggunakan VMAC sebagai Source MAC. Switch perantara memperbarui tabel CAM (*Content Addressable Memory*) mereka, memindahkan pemetaan VMAC dari port router lama ke port router baru tanpa membutuhkan perubahan konfigurasi ARP cache pada end-host.

---

### 4. Why & What

#### Mengapa Tidak Mengandalkan Dynamic Routing Protocol di Tingkat Host?
Meskipun OSPF atau BGP dapat dijalankan langsung di server/host, hal ini:
* Memperbesar beban CPU control-plane pada switch distribusi/access.
* Meningkatkan radius *blast domain* routing jika ada host yang terkompromi atau mengalami bug flapping.
* Menambah kompleksitas administrasi konfigurasi jaringan di ribuan virtual machine (VM) atau container node.

Oleh karena itu, host end-system umumnya bergantung pada *Static Default Gateway*. Di sinilah FHRP dan static edge routing menjadi fondasi availabilitas jaringan.

#### Keterbatasan Arsitektur Tradisional FHRP
* **Pemanfaatan Kapasitas Asimetris (Active/Standby):** Pada konfigurasi standar, router standby membiarkan hardware interface-nya menganggur sementara link active menanggung 100% beban trafik.
* **Tromboning / Hairpinning:** Dalam topologi virtualisasi modern multi-chassis, host dapat mengirimkan trafik ke switch yang bukan merupakan Master aktif untuk VMAC tersebut, memaksa paket menyeberangi link inter-switch (misal: vPC peer-link atau MLAG link) sebelum di-route ke upstream. Solusi modern mengombinasikan FHRP dengan *Anycast Gateway* (EVPN-VXLAN), namun pemahaman mendalam tentang FHRP tetap wajib untuk border leaf, firewall edge, dan enterprise branch topologies.

---

### 5. How (Workflow Detail)

#### 5.1 Siklus Forwarding Paket Layer 3 di Data Plane

```
[Ingress Port]
      |
      v
[L2 De-encapsulation] -> Cocokkan Destination MAC dengan Router Interface MAC / VMAC
      |
      +--> Jika MAC Tidak Cocok -> Drop / L2 Switch
      |
      v (Cocok)
[L3 Verification] -> Validasi IP Checksum & Cek TTL > 1 (Jika TTL <= 1 -> Send ICMP Time Exceeded)
      |
      v
[TCAM / FIB Lookup] -> Evaluasi Longest Prefix Match (LPM)
      |
      v
[Adjacency Lookup] -> Dapatkan Next-Hop IP, Egress Interface, dan Dest MAC via ARP Table
      |
      v
[Packet Rewrite]
      * Kurangi TTL (TTL = TTL - 1)
      * Rekalkulasi IP Checksum
      * Tulis ulang Source MAC (Interface Egress MAC)
      * Tulis ulang Destination MAC (Next-Hop Router / Destination Host MAC)
      |
      v
[Egress Queue / Transmission] -> Keluar melalui Egress Interface
```

#### 5.2 Alur Transisi State Machine VRRPv3

```
+-------------------------------------------------------------+
|                         INITIALIZE                          |
+-------------------------------------------------------------+
        |                                             ^
        | Interface Up / Priority = 255 (Address Owner)| Interface Down
        v                                             |
+-------------------------------------------------------------+
|                           BACKUP                            |
+-------------------------------------------------------------+
        |                                             ^
        | Master_Down_Timer Expired                   | Terima Advertisement
        | ATAU Menerima Preempt dengan Priority Lebih | dengan Priority Lebih
        | Rendah                                      | Tinggi
        v                                             |
+-------------------------------------------------------------+
|                           MASTER                            |
|  * Pancarkan Gratuitous ARP untuk VMAC                      |
|  * Kirim Advertisement periodik ke 224.0.0.18               |
|  * Forward trafik yang ditujukan ke VMAC                    |
+-------------------------------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pos dan Loket Layanan Terpadu
Bayangkan sebuah kantor pos (Router) yang memiliki **Buku Panduan Wilayah** (RIB) tebal berisi semua alternatif rute antar kota. Namun, petugas sortir di jalur ban berjalan tidak membaca buku tersebut; mereka merujuk ke **Papan Petunjuk Cepat** (FIB) yang sudah ditempel ringkas di dinding: *Setiap kode pos berawalan 40 langsung masukkan ke truk Jalur 2*.

**FHRP** dianalogikan sebagai **Loket Layanan Bersama**. Dua petugas (Router Primer dan Router Sekunder) duduk berdampingan di belakang satu nomor meja resmi (Virtual IP `10.0.0.1`) dengan kartu identitas seragam (Virtual MAC). Pelanggan (Host) hanya tahu mereka harus datang ke meja tersebut. Jika Petugas Primer pingsan, Petugas Sekunder langsung menarik stempel dan merespons antrean seketika tanpa pelanggan perlu tahu bahwa individu yang melayani mereka telah berganti.

#### Topologi Enterprise High-Availability Edge Gateway

```
                             +-------------------+
                             |   WAN / Transit   |
                             +-------------------+
                               /               \
                  e0/0 (198.51.100.1/30)    e0/0 (198.51.100.5/30)
                             /                   \
                   +---------------+       +---------------+
                   | Edge Router 1 |       | Edge Router 2 |
                   |  (DIST-R01)   |       |  (DIST-R02)   |
                   +---------------+       +---------------+
                           | e0/1                 | e0/1
                    (10.10.10.2/24)        (10.10.10.3/24)
                           |                      |
             +-------------+----------------------+-------------+
             |             VLAN 10: 10.10.10.0/24               |
             |             VRRP Group 10 VIP: 10.10.10.1        |
             |             BFD Session Peering e0/1 <-> e0/1    |
             +--------------------------------------------------+
                                      |
                              +---------------+
                              | Access Switch |
                              +---------------+
                               /             \
                        +--------+         +--------+
                        | Host A |         | Host B |
                        +--------+         +--------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Linux Enterprise Host/Router Gateway (Keepalived & IPRoute2)

Berikut adalah konfigurasi produksi untuk dua node gateway Linux redundan menggunakan `keepalived` dengan VRRPv3 dan health-check script.

##### Node A (Master Candidate) - `/etc/keepalived/keepalived.conf`
```ini
global_defs {
    router_id DIST-LNX-01
    vrrp_version 3
    script_user root
    enable_script_security
}

vrrp_script check_upstream_gate {
    script "/usr/local/bin/check_upstream.sh"
    interval 1       # Deteksi setiap 1 detik
    fall 2           # 2 kali gagal berturut-turut untuk trigger failure
    rise 2           # 2 kali sukses untuk kembali normal
    weight -30       # Penurunan prioritas jika gagal
}

vrrp_instance VI_VLAN10 {
    state MASTER
    interface eth1
    virtual_router_id 10
    priority 120
    advert_int 1

    virtual_ipaddress {
        10.10.10.1/24 dev eth1
    }

    track_script {
        check_upstream_gate
    }

    authentication {
        auth_type PASS
        auth_pass Secr3tP@ss10
    }

    # Delay preempt agar routing/BGP convergence tuntas sebelum mengambil alih
    preempt_delay 30
}
```

##### Node B (Backup Candidate) - `/etc/keepalived/keepalived.conf`
```ini
global_defs {
    router_id DIST-LNX-02
    vrrp_version 3
}

vrrp_instance VI_VLAN10 {
    state BACKUP
    interface eth1
    virtual_router_id 10
    priority 100
    advert_int 1

    virtual_ipaddress {
        10.10.10.1/24 dev eth1
    }

    authentication {
        auth_type PASS
        auth_pass Secr3tP@ss10
    }
}
```

##### Script Pemantau Upstream - `/usr/local/bin/check_upstream.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

# Verifikasi reachability ke ISP gateway via interface WAN (eth0)
TARGET_IP="198.51.100.1"

if ping -c 1 -W 1 -I eth0 "${TARGET_IP}" > /dev/null 2>&1; then
    exit 0
else
    exit 1
fi
```

#### 7.2 Cisco IOS-XE / Arista EOS: Advanced Static Routing + BFD + VRRPv3

Implementasi deterministik failover pada switch core/distribution layer enterprise.

##### Konfigurasi Router Primer (DIST-R01)
```cisco
! Definisikan BFD Template untuk Timer Presisi
bfd-template single-hop BFD_SUB_SECOND
 interval min-tx 100 min-rx 100 multiplier 3
!
interface GigabitEthernet0/0
 description WAN-UPLINK-PRIMARY
 ip address 198.51.100.2 255.255.255.252
 bfd template BFD_SUB_SECOND
!
interface GigabitEthernet0/1
 description LAN-VLAN-10
 ip address 10.10.10.2 255.255.255.0
 no shutdown
 !
 fhrp version vrrp v3
 fhrp vrrp 10
  address-family ipv4
   priority 120
   timers advertise 1000
   preempt delay minimum 60
   track 1 decrement 30
   address 10.10.10.1 primary
!
! Tracking Object terikat pada BFD upstream transit gateway
track 1 interface GigabitEthernet0/0 line-protocol
!
! Static Route dengan dependensi BFD untuk sub-100ms path failure detection
ip route 0.0.0.0 0.0.0.0 198.51.100.1
ip route static bfd GigabitEthernet0/0 198.51.100.1
```

##### Konfigurasi Router Sekunder (DIST-R02 - Floating Gateway)
```cisco
interface GigabitEthernet0/0
 description WAN-UPLINK-SECONDARY
 ip address 198.51.100.6 255.255.255.252
!
interface GigabitEthernet0/1
 description LAN-VLAN-10
 ip address 10.10.10.3 255.255.255.0
 no shutdown
 !
 fhrp version vrrp v3
 fhrp vrrp 10
  address-family ipv4
   priority 100
   timers advertise 1000
   address 10.10.10.1 primary
!
! Floating Static Route: Hanya aktif jika IGP/Egress primer kolaps (AD = 200)
ip route 0.0.0.0 0.0.0.0 198.51.100.5 200
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Blackholing Akibat "Silent Failure" & Flapping di Edge Data Center Finansial
* **Latar Belakang:** Platform transaksi derivatif mengalami insiden downtime intermiten selama 42 menit. Dua edge router (`DC-EDGE-01` dan `DC-EDGE-02`) terhubung ke upstream MPLS provider berbeda. Redundansi internal LAN mengandalkan HSRP default timer (Hello 3s, Hold 10s). Default route dikonfigurasi secara statik: `ip route 0.0.0.0 0.0.0.0 203.0.113.1`.
* **Akar Masalah (Root Cause Analysis):**
  1. Link fiber optik fisik antara `DC-EDGE-01` dan switch penyedia MPLS tetap `UP` (Layer 1/2 stabil). Namun, perangkat provider di ujung mengalami *packet-drop silang* (Layer 3 forwarding plane macet pada provider PE).
  2. Router `DC-EDGE-01` tetap memegang state HSRP Active karena interface LAN `e0/1` aktif dan tidak ada mekanisme pelacakan status transit end-to-end.
  3. Ribuan server terus mengarahkan paket transaksi ke HSRP Virtual MAC di `DC-EDGE-01`, yang kemudian membuang paket tersebut ke blackhole interface WAN.
  4. Ketika tim operasi mereboot router primer, terjadi fenomena *preempt race condition*. Saat router menyala kembali, ia langsung mengambil alih status HSRP Active sebelum interface uplink dan sesi routing BGP upstream-nya fully converged. Akibatnya, terjadi pemadaman transaksi tambahan selama 180 detik.

#### Solusi Rekayasa Infrastruktur:
1. **Implementasi BFD Multi-hop / Tracked IP SLA:**
   Alih-alih mengasumsikan interface UP sama dengan traffic forwarding, integrasikan `IP SLA` dengan tracking ICMP/UDP Echo yang digabungkan ke HSRP/VRRP priority decrement.
2. **Konfigurasi Preempt Delay:**
   Menerapkan `preempt delay minimum 300` detik untuk memberikan jeda bagi router yang baru reboot agar menstabilkan routing table dan FIB sebelum mengambil peran Master.
3. **Migrasi ke Sub-Second VRRPv3 dengan Object Tracking:**
   Mereduksi RTO (*Recovery Time Objective*) dari 10 detik menjadi 300 milidetik saat upstream failure terjadi.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian / Risiko | Biaya Operasional / Hardware |
| :--- | :--- | :--- | :--- |
| **VRRP Sub-Second Timers (misal: 100ms)** | Konvergensi failover mendekati instan (< 300ms) tanpa intervensi manual. | Rentan *false-positive failover* jika control plane CPU spike sesaat; meningkatkan utilisasi CPU. | Membutuhkan switch/router dengan hardware-offloaded FHRP engine. |
| **Floating Static Routes vs. Dynamic Routing (OSPF/eBGP)** | Nol overhead CPU/RAM routing protocol; sangat mudah diprediksi dan diamankan. | Skalabilitas buruk ($O(N)$ konfigurasi manual); rentan blackhole jika terjadi silent failure tanpa BFD. | Biaya konfigurasi dan maintenance tinggi seiring pertumbuhan node edge. |
| **Dual-Active ECMP Gateway vs. FHRP Active/Standby** | Kapasitas throughput LAN berlipat ganda; utilisasi link seimbang (100% aktif). | Potensi *asymmetric routing* yang merusak session firewall stateful tanpa inter-chassis clustering (Sync). | Membutuhkan arsitektur L3 ke Access Layer (routed access) atau EVPN Anycast Gateway. |
| **Aggressive BFD Timers (3 x 50ms)** | Deteksi kegagalan link Layer 3 hardware/software dalam 150 milidetik. | Flapping link WAN jarak jauh akibat jitter periodik, memicu flapping rute secara beruntun. | Rendah biaya lisensi, tetapi memerlukan kontrol ASIC data plane yang presisi. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kesalahan Fatal yang Sering Terjadi
1. **Asymmetric Routing pada Stateful Firewall:**
   Trafik egress keluar melalui `Master Router 1`, tetapi paket balik (ingress) masuk melalui `Backup Router 2`. Jika kedua router menjalankan NAT atau Stateful Inspection (misal: Palo Alto, Fortinet) tanpa session syncing (*High Availability Cluster*), paket balik akan di-drop dengan status `TCP Out-of-State / Invalid ACK`.
2. **Tidak Mengaktifkan Preempt Delay:**
   Ketika Master router mengalami crash dan reboot, ia langsung memicu claim Master seketika link fisik LAN `UP`, padahal link WAN dan tabel FIB belum terisi rute lengkap. Seluruh trafik internal terputus selama proses booting kontrol plane.
3. **Mismatched Authentication & Subnet Mask:**
   VRRP/HSRP mengabaikan paket advertisement dari peer jika panjang subnet mask atau tipe otentikasi string tidak identik, menyebabkan kedua router mendeklarasikan diri sebagai *Master* (**Split-Brain Incident**).
4. **TCAM Exhaustion Akibat Penolakan Route Summarization:**
   Menyuntikkan ribuan static route host `/32` langsung ke edge-switch lama, menyebabkan memori TCAM penuh. Router secara diam-diam memindahkan forwarding ke *software slow-path* (CPU), menaikkan latensi dari mikrodetik ke ratusan milidetik.

#### 10.2 Workflow Diagnostik

```
[Mulai Investigasi Gateway Terputus / Flapping]
     |
     v
[Periksa State FHRP di Kedua Node]
     Command: `show vrrp brief` / `show standby brief` / `ip link show`
     |
     +--> Apakah Kedua Node Berada pada Status MASTER/ACTIVE? (Split-Brain)
     |    |
     |    +--> [YA] -> Analisis L2 Multicast / VLAN:
     |    |            1. Cek VLAN trunk: Apakah VLAN membawa multicast 224.0.0.18?
     |    |            2. Cek IGMP Snooping: Apakah switch memblokir paket FHRP?
     |    |            3. Cek Access-List: Apakah ada ACL yang mendrop traffic IP protocol 112 (VRRP)?
     |    |
     |    +--> [TIDAK]
     |
     v
[Periksa Status Synchronization Hardware FIB]
     Command: `show ip cef <IP_Tujuan>` / `ip route get <IP>`
     |
     +--> Apakah Next-Hop di FIB berbeda dengan RIB?
          |
          +--> [YA] -> Kemungkinan Defective IPC atau Alokasi Adjacency TCAM Gagal.
          |            Lakukan CEF table rebuild: `clear ip cef *`
          |
          +--> [TIDAK] -> Verifikasi Adjacency & ARP:
                          1. Jalankan `show ip arp <Next_Hop_IP>`
                          2. Pastikan Status: Resolving vs Incomplete
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan FHRP Version Modern:** Terapkan VRRPv3 atau HSRPv2 untuk mendukung native sub-second precision dan kesiapan IPv6.
- [ ] **Explicit Priority & Preempt Delay:** Tetapkan priority yang jelas (misal: Node-01 = 120, Node-02 = 100) dan selalu pasang `preempt delay minimum 60` (disesuaikan dengan rata-rata waktu boot upstream routing).
- [ ] **Sandarkan Static Route pada Health-Check Deterministic:** Larang penggunaan static route mengambang tanpa asosiasi objek BFD atau IP SLA tracking.
- [ ] **Standardisasi Virtual MAC Filtering:** Pastikan fitur *Port Security* pada switch downstream mengizinkan Virtual MAC dari FHRP yang bersangkutan (`0000.5E00.01xx` untuk VRRP).
- [ ] **Amankan Protokol Kontrol L3:** Terapkan otentikasi bila didukung platform, atau amankan segmen kontrol FHRP menggunakan VACL/Control Plane Policing (CoPP) agar host liar tidak bisa menginjeksi advertisement prioritas 255.
- [ ] **Mitigasi Asymmetric Routing:** Pastikan path cost menuju core upstream simetris dengan router yang memegang status active FHRP pada downstream LAN.

---

### 12. Hands-on Practice

Dalam simulasi ini, Anda akan membangun lingkungan lab menggunakan **Linux Network Namespaces** untuk merekayasa skenario L3 Routing, VRRP Failover menggunakan `keepalived`, dan Floating Route.

#### Langkah 1: Persiapan Environment Jaringan Virtual
Simpan script berikut sebagai `hands-on/m02/setup_topology.sh` dan jalankan dengan hak akses root (`sudo`):

```bash
#!/usr/bin/env bash
set -xeuo pipefail

# 1. Bersihkan namespace lama jika ada
ip -all netns delete || true

# 2. Buat Namespace untuk Client, R1, R2, dan Internet Upstream
ip netns add CLIENT
ip netns add ROUTER-01
ip netns add ROUTER-02
ip netns add UPSTREAM

# 3. Buat Virtual Ethernet Pair dan Bridge untuk Segmen LAN
ip link add br-lan type bridge
ip link set br-lan up

# Hubungkan CLIENT ke Bridge LAN
ip link add veth-c type veth peer name veth-c-br
ip link set veth-c netns CLIENT
ip link set veth-c-br master br-lan
ip link set veth-c-br up

# Hubungkan ROUTER-01 ke Bridge LAN
ip link add veth-r1-lan type veth peer name veth-r1-br
ip link set veth-r1-lan netns ROUTER-01
ip link set veth-r1-br master br-lan
ip link set veth-r1-br up

# Hubungkan ROUTER-02 ke Bridge LAN
ip link add veth-r2-lan type veth peer name veth-r2-br
ip link set veth-r2-lan netns ROUTER-02
ip link set veth-r2-br master br-lan
ip link set veth-r2-br up

# 4. Hubungkan ROUTER-01 dan ROUTER-02 ke UPSTREAM
ip link add veth-r1-wan type veth peer name veth-up-r1
ip link set veth-r1-wan netns ROUTER-01
ip link set veth-up-r1 netns UPSTREAM

ip link add veth-r2-wan type veth peer name veth-up-r2
ip link set veth-r2-wan netns ROUTER-02
ip link set veth-up-r2 netns UPSTREAM

# 5. Konfigurasi Pengalamatan IP
# UPSTREAM
ip netns exec UPSTREAM ip link set lo up
ip netns exec UPSTREAM ip addr add 198.51.100.1/30 dev veth-up-r1
ip netns exec UPSTREAM ip addr add 198.51.100.5/30 dev veth-up-r2
ip netns exec UPSTREAM ip link set veth-up-r1 up
ip netns exec UPSTREAM ip link set veth-up-r2 up
ip netns exec UPSTREAM sysctl -w net.ipv4.ip_forward=1

# ROUTER-01
ip netns exec ROUTER-01 ip link set lo up
ip netns exec ROUTER-01 ip addr add 10.10.10.2/24 dev veth-r1-lan
ip netns exec ROUTER-01 ip addr add 198.51.100.2/30 dev veth-r1-wan
ip netns exec ROUTER-01 ip link set veth-r1-lan up
ip netns exec ROUTER-01 ip link set veth-r1-wan up
ip netns exec ROUTER-01 sysctl -w net.ipv4.ip_forward=1

# ROUTER-02
ip netns exec ROUTER-02 ip link set lo up
ip netns exec ROUTER-02 ip addr add 10.10.10.3/24 dev veth-r2-lan
ip netns exec ROUTER-02 ip addr add 198.51.100.6/30 dev veth-r2-wan
ip netns exec ROUTER-02 ip link set veth-r2-lan up
ip netns exec ROUTER-02 ip link set veth-r2-wan up
ip netns exec ROUTER-02 sysctl -w net.ipv4.ip_forward=1

# CLIENT
ip netns exec CLIENT ip link set lo up
ip netns exec CLIENT ip addr add 10.10.10.50/24 dev veth-c
ip netns exec CLIENT ip link set veth-c up
# Set Gateway ke Virtual IP VRRP nantinya
ip netns exec CLIENT ip route add default via 10.10.10.1

echo "[+] Topologi Berhasil Dibuat."
```

#### Langkah 2: Mengonfigurasi Keepalived (VRRP Engine)
Buat konfigurasi file untuk masing-masing router di folder kerja.

*File: `hands-on/m02/r1-keepalived.conf`*
```ini
vrrp_instance VI_1 {
    state MASTER
    interface veth-r1-lan
    virtual_router_id 51
    priority 120
    advert_int 1
    virtual_ipaddress {
        10.10.10.1/24 dev veth-r1-lan
    }
}
```

*File: `hands-on/m02/r2-keepalived.conf`*
```ini
vrrp_instance VI_1 {
    state BACKUP
    interface veth-r2-lan
    virtual_router_id 51
    priority 100
    advert_int 1
    virtual_ipaddress {
        10.10.10.1/24 dev veth-r2-lan
    }
}
```

Jalankan proses keepalived di dalam masing-masing namespace:
```bash
sudo ip netns exec ROUTER-01 keepalived -f $(pwd)/hands-on/m02/r1-keepalived.conf -p /run/r1-keepalived.pid -r /run/r1-vrrp.pid
sudo ip netns exec ROUTER-02 keepalived -f $(pwd)/hands-on/m02/r2-keepalived.conf -p /run/r2-keepalived.pid -r /run/r2-vrrp.pid
```

#### Langkah 3: Menguji Konvergensi dan Trigger Failover
1. Pantau traffic dari namespace CLIENT menuju virtual IP:
   ```bash
   sudo ip netns exec CLIENT ping 10.10.10.1
   ```
2. Amati ARP Table pada CLIENT:
   ```bash
   sudo ip netns exec CLIENT ip neigh show
   ```
   *Ekspektasi:* Alamat `10.10.10.1` terasosiasi dengan Virtual MAC format `00:00:5e:00:01:33` (Hexadecimal 33 = Desimal 51).
3. Matikan interface LAN pada ROUTER-01 untuk mensimulasikan failure:
   ```bash
   sudo ip netns exec ROUTER-01 ip link set veth-r1-lan down
   ```
4. Verifikasi bahwa ROUTER-02 mengambil alih VIP secara instan tanpa ada host packet drop berkepanjangan:
   ```bash
   sudo ip netns exec ROUTER-02 ip addr show veth-r2-lan
   ```
   VIP `10.10.10.1/24` sekarang terpasang di interface `veth-r2-lan`.

---

### 13. Exercise

#### Tingkat Kesulitan: Easy
1. **Soal:** Suatu router menerima paket IP menuju `172.16.5.40`. Tabel rute memiliki tiga entri berikut:
   * A: `172.16.0.0/16 via 10.0.0.1`
   * B: `172.16.4.0/22 via 10.0.0.2`
   * C: `172.16.5.32/28 via 10.0.0.3`
   Tentukan entri mana yang dipilih router, jelaskan dasar perhitungannya, dan sebutkan panjang prefix bit yang cocok.
2. **Kriteria Keberhasilan:** Jawaban harus mendemonstrasikan perhitungan representasi biner dari IP tujuan terhadap ketiga subnet mask, dan secara tepat mengidentifikasi pemenang LPM.

#### Tingkat Kesulitan: Medium
1. **Soal:** Konfigurasikan sepasang router (Linux atau Cisco syntax) dengan Floating Static Route. Skenario: Default route primer melewati interface ISP-A dengan Next-Hop `198.51.100.1` dan Floating Static Route melewati ISP-B dengan Next-Hop `203.0.113.1`. Syarat: Route ISP-B hanya boleh masuk ke FIB jika ISP-A tidak merespons ICMP SLA (loss > 50% selama 3 probe). Tuliskan blok konfigurasi lengkapnya.
2. **Kriteria Keberhasilan:** Script atau file konfigurasi mencakup pembentukan SLA monitor, tracking object, asosiasi track ke rute statik, dan penetapan nilai Administrative Distance yang berbeda.

#### Tingkat Kesulitan: Hard
1. **Soal:** Anda memiliki arsitektur dual-homed firewall yang terhubung ke switch distribusi menggunakan VRRP. Terjadi *asymmetric routing* di mana paket TCP SYN dari client keluar lewat Switch-01 (VRRP Master) ke Firewall-01, namun paket SYN-ACK kembali dari upstream internet masuk via Switch-02 (VRRP Backup) yang langsung di-drop oleh Firewall-02 karena state TCP tidak sinkron. Rancang arsitektur L3/VRRP tracking lengkap (lengkap dengan diagram dan snippet konfigurasi) untuk memaksakan jalur routing keluar-masuk simetris secara deterministik tanpa menonaktifkan mekanisme inspeksi stateful firewall.
2. **Kriteria Keberhasilan:** Solusi mengintegrasikan VRRP object tracking terkoordinasi (misal: VRRP sync groups / Conntrackd / HA sync link) dan manipulasi metrik rute statik balik ke core switch.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Sebuah bursa perdagangan komoditas multi-tenant beroperasi dengan toleransi downtime maksimum (RTO) di bawah 50 milidetik. Jaringan perimeter mereka menggunakan dua router border edge berkecepatan 100 Gbps yang menjalankan eBGP ke dua transit provider berbeda. Antara edge router dan firewall farm internal terdapat segmen transit L3 yang menggunakan static routing dan VRRPv3.

**Kondisi Kendala:**
1. Switch upstream transit sesekali mengalami fenomena "micro-looping" dan degradasi performa di mana packet loss mencapai 15%, namun status link optik (PHY) tetap berstatus UP.
2. Protokol dinamis (OSPF/BGP) **dilarang keras** diaktifkan pada interface internal yang menghadap firewall farm karena kepatuhan regulasi isolasi audit pihak ketiga.
3. Kapasitas TCAM pada switch border edge terbatas; dilarang mengimpor Full Internet BGP Route ke dalam hardware forwarding table.

**Tantangan Anda:**
1. Rancang arsitektur rute statik dan FHRP yang mampu mendeteksi degradasi parsial (15% packet loss) dan melakukan failover deterministik dalam kurun waktu kurang dari 50 milidetik.
2. Tentukan bagaimana pemfilteran rute dan mekanisme summarization dilakukan sebelum dikompilasi ke FIB/TCAM switch perimeter untuk mencegah luapan TCAM (*TCAM exhaustion*).
3. Buat dokumen arsitektur komprehensif yang mencakup arsitektur failover tracking, mitigasi *hairpinning*, pemeliharaan simetri trafik, dan mitigasi *split-brain*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konsep Fondasi)

1. Apa perbedaan utama antara Routing Information Base (RIB) dan Forwarding Information Base (FIB)?
   * A. RIB berada di data plane ASIC, sedangkan FIB berada di CPU control plane.
   * B. RIB menampung seluruh rute yang dipelajari dan memproses metrik protokol; FIB dikompilasi dari rute terbaik RIB untuk hardware lookup cepat tanpa rekursi rute.
   * C. FIB memiliki Administrative Distance, sedangkan RIB tidak memilikinya.
   * D. FIB hanya digunakan untuk routing dinamis, sedangkan RIB khusus untuk routing statik.

2. Mengapa algoritma Longest Prefix Match (LPM) memilih prefix `/28` dibandingkan `/24` untuk alamat host yang valid di kedua subnet tersebut?
   * A. Karena `/28` memiliki Administrative Distance lebih rendah.
   * B. Karena `/28` memiliki nilai metrik biaya (cost) lebih tinggi.
   * C. Karena `/28` merepresentasikan rentang alamat yang lebih spesifik (mask lebih panjang), mencocokkan lebih banyak bit identik dari alamat tujuan.
   * D. Karena router selalu mengeksekusi pencarian rute secara alfabetis.

3. Alamat MAC virtual standar yang digunakan oleh VRRPv2 untuk grup ID 10 (desimal) pada IPv4 adalah:
   * A. `00:00:0C:07:AC:0A`
   * B. `00:00:5E:00:01:0A`
   * C. `01:00:5E:00:00:12`
   * D. `00:00:5E:00:02:0A`

4. Apa fungsi dari frame Gratuitous ARP (GARP) yang dipancarkan oleh router yang baru saja menjadi VRRP Master?
   * A. Menghapus tabel routing di semua router tetangga.
   * B. Memperbarui tabel MAC address (CAM table) pada switch Layer 2 perantara agar port mapping untuk Virtual MAC diarahkan ke port router yang baru.
   * C. Mengalokasikan alamat IP baru secara otomatis untuk seluruh host di LAN.
   * D. Menguji apakah ada konflik alamat IP di control plane.

5. Nilai default Administrative Distance untuk Static Route yang menunjuk langsung ke IP Next-Hop pada Cisco IOS-XE adalah:
   * A. 0
   * B. 1
   * C. 5
   * D. 110

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Teknis)

6. Apa peran dari *Skew Time* dalam perhitungan Master Down Interval pada VRRP?
   * A. Menjamin router dengan IP fisik lebih tinggi selalu menang dalam pemilihan master.
   * B. Memberikan rentang waktu acak untuk menghindari tabrakan paket (collision) pada media shared Ethernet.
   * C. Memastikan router cadangan dengan prioritas lebih tinggi memiliki jeda timer yang sedikit lebih pendek, sehingga mengambil alih state Master lebih cepat dibandingkan router cadangan dengan prioritas lebih rendah.
   * D. Menyinkronkan clock NTP internal antar router secara real-time.

7. Jika dua router dalam satu LAN dikonfigurasi dengan VRRPv3 grup yang sama, namun keduanya berada dalam status `MASTER`, parameter manakah di bawah ini yang **bukan** merupakan penyebab utama kegagalan tersebut?
   * A. Firewall memblokir paket dengan IP protocol number 112 (VRRP).
   * B. Interface kedua router dikonfigurasi pada VLAN yang terisolasi satu sama lain.
   * C. Parameter `preempt delay` pada router primer bernilai lebih tinggi dari router cadangan.
   * D. Fitur IGMP/Multicast Snooping pada switch downstream membuang frame yang ditujukan ke `224.0.0.18`.

8. Dalam implementasi *Floating Static Route*, mekanisme apa yang paling tepat untuk mendeteksi kegagalan link jika kabel fisik antara switch upstream dan router lokal tetap berstatus "UP" namun gateway di sisi ISP mati?
   * A. Mengandalkan Layer 2 Carrier Detect (`carrier-delay`).
   * B. Menggabungkan static route dengan Object Tracking berbasis BFD (Bidirectional Forwarding Detection) atau probe IP SLA periodik.
   * C. Menurunkan nilai MTU interface LAN.
   * D. Mengonfigurasi Spanning Tree PortFast pada uplink router.

9. Manakah pernyataan yang paling tepat mengenai perbedaan antara TCAM dan RAM standar dalam operasi forwarding paket?
   * A. RAM standar mencari data berdasarkan alamat memori secara paralel, sedangkan TCAM membaca baris per baris.
   * B. TCAM mengevaluasi pola bit `0`, `1`, dan `X` (Don't Care) secara paralel dalam satu siklus instruksi, membuatnya sangat efisien untuk LPM IP mask fleksibel.
   * C. TCAM memiliki konsumsi daya yang jauh lebih rendah daripada RAM standar.
   * D. TCAM digunakan untuk menyimpan database kontrol OSPF/BGP, sedangkan RAM digunakan untuk lookup ASIC data plane.

10. Ketika mengonfigurasi VRRP tracking terhadap interface WAN, router primer memiliki prioritas 110, router sekunder 100, dan parameter `decrement` diatur sebesar 15. Apa yang terjadi jika interface WAN pada router primer down?
    * A. Prioritas router primer turun menjadi 95; router sekunder mengambil alih peran Master jika preempt diaktifkan.
    * B. Router primer langsung mengirim pesan VRRP Shutdown; router sekunder tidak terpengaruh.
    * C. Router sekunder menaikkan prioritasnya menjadi 115 secara otomatis.
    * D. Prioritas router primer tetap 110, namun ia melepaskan Virtual IP.

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario Kasus A:**
    Setelah pemadaman listrik di datacenter, kedua edge router menyala kembali. Namun, seluruh konektivitas internet dari host LAN terputus selama 4 menit pertama pasca-reboot, meskipun kedua router sudah berada dalam status running. Pemeriksaan log menunjukkan Router 1 langsung menjadi VRRP Master seketika port ethernet LAN aktif. Sementara itu, sesi BGP WAN Router 1 membutuhkan waktu 3 menit untuk mencapai state *Established* dan mengunduh rute. 
    *Pertanyaan:* Perubahan konfigurasi apa yang harus diterapkan pada VRRP Router 1 untuk meniadakan masa blackout tersebut pada insiden reboot di masa depan?

12. **Skenario Kasus B:**
    Sebuah switch aggregation Layer 3 menampilkan utilisasi CPU 99% secara mendadak. Setelah diinspeksi, trafik jaringan tidak mengalami kenaikan volume Mbps yang signifikan, namun command `show ip cef switching statistics` menunjukkan bahwa jutaan paket dialihkan dari hardware switching (CEF) ke software-punting (`Punt to CPU`). Log sistem menunjukkan pesan: `%FIB-3-FIB_TCAM_FULL: TCAM table full, forwarding in software`.
    *Pertanyaan:* Mengapa peristiwa ini terjadi dan langkah arsitektural jangka pendek apa yang harus segera dieksekusi oleh network engineer untuk menstabilkan kembali switch tersebut tanpa restart?

13. **Skenario Kasus C:**
    Sebuah bank mengonfigurasi dua router edge untuk active/active ECMP gateway menuju Core Network menggunakan equal-cost static route:
    * `ip route 0.0.0.0 0.0.0.0 10.0.0.2`
    * `ip route 0.0.0.0 0.0.0.0 10.0.0.3`
    Di balik kedua router terdapat firewall kluster stateful. Para pengguna melaporkan bahwa sesi SSH dan transfer file SFTP sering terputus tiba-tiba di tengah jalan (*Connection reset by peer*), sementara akses web sederhana (HTTP) tampak berjalan normal.
    *Pertanyaan:* Analisis secara struktural mengapa sesi berbasis koneksi persisten lama (seperti SSH/SFTP) mengalami drop di lingkungan jaringan dengan konfigurasi di atas.

---

### Kunci Jawaban & Pembahasan Singkat Kuis

#### Bagian 1
1. **B** — RIB adalah software database terlengkap di CPU; FIB adalah data forwarding terkompilasi yang dioptimalkan untuk eksekusi data plane.
2. **C** — LPM mengevaluasi spesifisitas subnet mask secara deterministik. Prefix `/28` memiliki 28 bit biner pasti yang cocok, mengungguli `/24`.
3. **B** — Format standar VMAC VRRPv2 adalah `00:00:5E:00:01:{VRID}`. Nilai 10 dalam format heksadesimal adalah `0A`.
4. **B** — GARP memicu switch L2 memperbarui tabel CAM mereka sehingga frame yang ditujukan ke Virtual MAC langsung diarahkan ke port router baru.
5. **B** — Rute statis dengan next-hop IP memiliki nilai default AD = 1 pada platform Cisco.

#### Bagian 2
6. **C** — Skew time membedakan durasi tunggu antar-router cadangan berdasarkan prioritasnya, memitigasi perebutan status master secara serentak.
7. **C** — `preempt delay` hanya mengatur jeda waktu sebelum router mengambil alih; parameter ini tidak memicu pemisahan state menjadi dual-master (split-brain).
8. **B** — BFD atau IP SLA menyediakan verifikasi bidireksional Layer 3 end-to-end tanpa bergantung pada status fisik interface lokal.
9. **B** — Arsitektur TCAM memiliki keunggulan mengevaluasi kondisi wildcard secara hardware paralel dalam 1 clock cycle.
10. **A** — Prioritas baru = 110 - 15 = 95. Karena 95 < 100 (prioritas router sekunder), maka router sekunder memicu preemption dan menjadi Master.

#### Bagian 3
11. **Pembahasan Skenario A:** Konfigurasikan `preempt delay minimum <detik>` (contoh: 240–300 detik) pada instance VRRP Router 1. Hal ini memaksa Router 1 menunda pengambilan alih status Master, memberikan waktu yang cukup bagi sesi BGP upstream dan FIB untuk konvergen secara penuh sebelum ia mulai menarik trafik dari LAN.
12. **Pembahasan Skenario B:** Kapasitas baris TCAM telah terlampaui sehingga rute baru tidak dapat diprogram ke hardware ASIC, memaksa paket diproses oleh CPU (*punt to software*). Solusi cepat: Lakukan agregasi rute statik (*Route Summarization*) pada router upstream atau terapkan filter prefix (`ip prefix-list`) untuk menolak rute host `/32` yang tidak esensial, membebaskan ruang entri TCAM seketika.
13. **Pembahasan Skenario C:** ECMP melakukan hashing per-paket atau per-flow. Jika terjadi hashing asimetris atau rute berubah di tengah jalan, paket segmen TCP yang sama diarahkan menyeberangi unit firewall yang berbeda dalam kluster. Karena firewall bersifat stateful dan sesi belum tentu disinkronkan tepat waktu antar unit, paket yang datang tanpa status *handshake* valid langsung dibuang (TCP reset). Solusi: Terapkan *flow pinning* simetris atau ubah model gateway menjadi failover deterministik (Active/Standby).

---

### 16. Summary

1. **Pemisahan Control Plane & Data Plane:** Efisiensi routing enterprise bergantung pada kompilasi rute dari RIB (software kontrol) ke FIB (hardware execution) yang dipetakan ke dalam memori berkecepatan tinggi seperti TCAM menggunakan struktur data multi-bit trie.
2. **Prinsip Longest Prefix Match (LPM):** Pemilihan rute pada forwarding engine hardware mutlak ditentukan oleh panjang bit subnet mask terpanjang (`/32` hingga `/0`), mengabaikan metrik atau AD setelah tahap kompilasi FIB selesai.
3. **Resiliensi First Hop Redundancy:** FHRP (VRRP/HSRP) menstandardisasi ketersediaan gateway tunggal bagi host melalui penggunaan Virtual IP dan Virtual MAC yang dimigrasikan secara mulus antar perangkat via broadcast Gratuitous ARP (GARP).
4. **Konvergensi Statik Deterministik:** Static routing tanpa pelacakan jalur berisiko fatal terhadap pemadaman senyap (*blackholing*). Mengintegrasikan static routing dan FHRP dengan BFD (*Bidirectional Forwarding Detection*) serta IP SLA adalah prasyarat mutlak untuk mencapai konvergensi sub-second di level enterprise.