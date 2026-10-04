# Evaluasi Pembelajaran Bab 04: Layer 3 Routing & FHRP

---

## 1. Basic Questions (Pilihan Ganda & Konseptual Singkat)

### Soal 1
Sebuah router memiliki entri rute berikut di dalam routing table-nya:
- Rute 1: `10.0.0.0/8` via `192.168.1.1` [AD: 1]
- Rute 2: `10.1.0.0/16` via `192.168.2.1` [AD: 110]
- Rute 3: `10.1.1.0/24` via `192.168.3.1` [AD: 90]
- Rute 4: `0.0.0.0/0` via `192.168.4.1` [AD: 1]

Ketika sebuah paket dengan alamat IP tujuan `10.1.1.150` tiba di router, rute manakah yang akan digunakan oleh router untuk meneruskan paket tersebut? Jelaskan alasannya.

### Soal 2
Berapa nilai default Administrative Distance (AD) untuk rute:
a) Directly Connected Interface
b) Static Route
c) OSPF
d) eBGP
e) RIP

### Soal 3
Apa perbedaan utama antara implementasi Static Route dengan *Next-Hop IP Address* dibandingkan dengan *Exit Interface* saja pada media multi-access Ethernet? Masalah teknis apa yang dapat terjadi jika hanya menentukan Exit Interface?

### Soal 4
Tuliskan alamat Virtual MAC yang dihasilkan oleh protokol:
a) VRRPv2 untuk Virtual Router ID (VRID) 10 (dalam heksadesimal).
b) HSRPv1 untuk Group ID 1.

### Soal 5
Apa fungsi utama dari perintah `preempt delay minimum 30` pada konfigurasi router FHRP primer? Mengapa delay tersebut sangat krusial saat router baru saja booting ulang?

---

## 2. Intermediate Questions (Analisis Kasus & Algoritma)

### Soal 6
Sebuah router menerima dua rute OSPF menuju destinasi subnet yang sama persis: `192.168.50.0/24`.
- Rute A dipelajari melalui interface dengan cost total 45.
- Rute B dipelajari melalui interface dengan cost total 20.
Router juga memiliki konfigurasi static route: `ip route 192.168.50.0 255.255.255.0 10.10.10.1 115`.
Tentukan rute mana yang akan dipasang ke dalam tabel FIB (Forwarding Information Base) dan jelaskan tahap eliminasinya.

### Soal 7
Jelaskan proses pertukaran frame Layer 2 (ARP resolution) saat sebuah PC klien di subnet `192.168.1.0/24` hendak mengirim data ke Web Server di `10.50.1.10` melalui Virtual Default Gateway VRRP (`192.168.1.1`). Apa MAC address tujuan yang tertulis pada frame Ethernet yang keluar dari Network Interface Card (NIC) PC klien?

### Soal 8
Pada skenario Router-on-a-Stick, sebuah switch terhubung ke interface router `GigabitEthernet0/0`. Terdapat dua VLAN: VLAN 100 dan VLAN 200. Tuliskan blok sintaks konfigurasi lengkap pada subinterface router tersebut agar host pada kedua VLAN dapat saling berkomunikasi, dengan gateway masing-masing adalah IP host pertama dari subnet `/24`.

### Soal 9
Mengapa protokol GLBP (Gateway Load Balancing Protocol) tidak cocok diimplementasikan di depan cluster Firewall yang beroperasi secara *Stateful Inspection*? Jelaskan konsekuensi teknis pada koneksi TCP (SYN, SYN-ACK, ACK).

### Soal 10
Sebuah floating static route dikonfigurasi sebagai berikut:
`ip route 0.0.0.0 0.0.0.0 198.51.100.1 200`
Sementara itu, rute primer dipelajari melalui OSPF (`0.0.0.0/0` via external type 2, AD 110). Jika interface uplink OSPF mengalami kondisi *flapping* (hidup-mati bergantian setiap 2 detik), jelaskan dampak yang terjadi pada Routing Table dan CPU router, serta bagaimana solusi arsitektural untuk menstabilkannya.

---

## 3. Scenario-Based Questions (Studi Kasus Industri)

### Kasus 1: Insiden Blackholing Pasca Putusnya Fiber Optic ISP
**Latar Belakang**:
Perusahaan E-Commerce menjalankan dua router edge: R1 (Primary Gateway) dan R2 (Secondary Gateway).
- Host LAN menggunakan default gateway virtual HSRP: `10.0.0.1`.
- R1 memiliki priority 110 dengan preemption aktif.
- R2 memiliki priority 100 dengan preemption aktif.
R1 terhubung ke ISP-A via switch perantara Layer 2 milik penyedia gedung.

**Insiden**:
Kabel fiber ISP-A putus 5 kilometer di luar gedung. Namun, link Ethernet fisik antara R1 dan switch perantara gedung tetap berstatus `UP/UP`. Trafik produksi dari seluruh kantor cabang mengalami timeout total (100% packet loss) selama 4 jam hingga engineer datang ke data center.
1. Analisis mengapa mekanisme failover HSRP gagal berjalan secara otomatis.
2. Rancang solusi teknis preskriptif pada konfigurasi R1 (termasuk fitur dan sintaks Cisco IOS) untuk mencegah terulangnya insiden tersebut.

---

### Kasus 2: Duplicate Master Alert pada VRRP di Multi-Switch Core
**Latar Belakang**:
Sebuah tim Platform Engineering mengoperasikan dua Core Switch (CS-01 dan CS-02) yang menjalankan VRRPv3 untuk subnet Kubernetes Node `10.240.0.0/22`. Masing-masing switch terhubung melalui dua link trunk 40Gbps yang di-bundle dalam Port-Channel (LACP).

**Insiden**:
Sistem monitoring Prometheus memicu alarm critical:
`VRRP_DUPLICATE_MASTER_DETECTED: Multiple nodes claiming Master role for VIP 10.240.0.1`.
Host di jaringan mengalami degradasi paket rontok (intermittent packet drops) sebesar 30-50%. Log switch menunjukkan MAC address flapping pada switch access downstream.

1. Identifikasi akar penyebab (root cause) yang paling memungkinkan yang menyebabkan kedua switch merasa dirinya adalah Master.
2. Jelaskan mengapa hal ini memicu MAC address flapping di switch downstream.
3. Tuliskan langkah investigasi berurutan (troubleshooting steps) untuk mengisolasi dan menyelesaikan masalah ini.

---

### Kasus 3: Migrasi Router-on-a-Stick ke Layer 3 Core Switching
**Latar Belakang**:
Sebuah fasilitas riset bioteknologi mengalami lonjakan trafik transfer data citra mikroskopis antar-VLAN (VLAN 10: Alat Lab, VLAN 20: Storage Server NAS). Saat ini arsitektur jaringan masih menggunakan Router-on-a-Stick dengan router Cisco ISR 4331 (link trunk 1Gbps). 

**Masalah**:
Kecepatan transfer data antar-VLAN mentok di angka 400-500 Mbps, utilitas CPU router mencapai 98%, dan terjadi banyak frame drop pada interface router. Pimpinan IT menyetujui pembelian satu unit Switch Layer 3 Cisco Catalyst 9300 48-port Full-PoE dengan backplane capacity 480 Gbps.

1. Jelaskan secara teknis mengapa arsitektur Router-on-a-Stick lama mengalami *bottleneck* parah pada skenario transfer data masif ini.
2. Buat rencana migrasi langkah demi langkah (migration execution plan) dari RoaS ke Switch Layer 3 SVI tanpa menyebabkan *downtime* lebih dari 5 menit.
3. Berikan konfigurasi baru yang harus diterapkan pada Switch Layer 3 tersebut.

---

## 4. Practical Chapter Challenge: Arsitektur Resilient Multi-Homed Campus Core

### Ringkasan Tantangan:
Anda adalah Principal Network Architect yang ditugaskan untuk merancang dan memvalidasi konfigurasi high-availability gateway untuk Data Center Tier-3 mini.

### Spesifikasi Teknis:
1. **Addressing & VLAN**:
   - VLAN 50 (Server Farm): `172.28.50.0/24`
   - Virtual Gateway (VRRP Group 50): `172.28.50.1`
   - Node Alpha (Primary): Real IP `172.28.50.2`
   - Node Bravo (Backup): Real IP `172.28.50.3`
2. **Path Optimization**:
   - Node Alpha harus menjadi Master dalam kondisi normal (Priority: 115).
   - Node Bravo menjadi Backup (Priority: 100).
   - Preemption diaktifkan pada kedua node, dengan preemption delay 60 detik pada Node Alpha.
3. **Uplink Protection**:
   - Node Alpha memiliki interface uplink WAN `GigabitEthernet0/0` (IP: `203.0.113.2/30`) ke ISP-A (Gateway: `203.0.113.1`).
   - Buat IP SLA probe (ICMP) ke `203.0.113.1` dengan interval frekuensi 3 detik, timeout 1 detik.
   - Kaitkan status SLA ke tracking object ID 50.
   - Jika tracking object 50 down, kurangi priority VRRP Node Alpha sebesar 25 poin (sehingga turun menjadi 90, lebih rendah dari Node Bravo).
4. **Inter-Switch Heartbeat & Routing**:
   - Interface `GigabitEthernet0/1` pada kedua node bertindak sebagai link L3 Point-to-Point transit (`10.255.255.0/30`).
   - Sediakan konfigurasi static default route dengan AD normal pointing ke ISP masing-masing, dan floating static route (AD 210) melintasi link Point-to-Point transit untuk saling mem-backup jika uplink salah satu router terputus tetapi link FHRP LAN masih hidup.

### Output yang Diharapkan:
Tuliskan script konfigurasi lengkap (Cisco IOS-XE compliant) untuk:
1. **Node Alpha (Master Configuration Script)**
2. **Node Bravo (Backup Configuration Script)**
3. **Verifikasi & Acceptance Testing Checklist**: Tuliskan tabel uji validasi pengujian failover dan failback beserta ekspektasi output CLI-nya.

---