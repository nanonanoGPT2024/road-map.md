# Modul 01: Network Monitoring, Observability, High Availability, dan Troubleshooting

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur observabilitas jaringan end-to-end berbasis *pull* (SNMP/Prometheus exporter), *flow* (NetFlow v9, IPFIX, sFlow), dan *push-based streaming telemetry* (gNMI/gRPC berbasis OpenConfig).
- Melakukan investigasi paket mendalam (*deep packet inspection*) menggunakan `tcpdump` dan Wireshark pada skenario anomali performa jaringan (TCP retransmission, zero window, asymmetric routing, dan MTU black hole).
- Menyusun dan mengeksekusi *Network Triage Runbooks* terstruktur guna memangkas *Mean Time to Detect* (MTTD) dan *Mean Time to Resolve* (MTTR) pada insiden skala *tier-1/tier-2*.
- Mengaplikasikan prinsip *Chaos Engineering* khusus infrastruktur jaringan menggunakan Linux Traffic Control (`tc-netem`) dan Chaos Mesh untuk menguji ketahanan protokol routing dinamis (BGP/OSPF convergence) dan *failover multi-homing*.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- Fundamental TCP/IP model: kalkulasi subnetting, 3-way handshake, flow control, TCP congestion control algorithms (Cubic, BBR).
- Protokol Routing Dinamis: Operasional BGP (iBGP/eBGP peering, timers, path attributes) dan OSPF (LSA types, states).
- Administrasi Linux Lanjut: Penggunaan shell scripting, manipulasi namespace jaringan (`ip netns`), konfigurasi `iptables`/`nftables`, dan Linux kernel socket tuning.
- Dasar RPC dan Serialisasi Data: Protocol Buffers (Protobuf) dan REST API.

---

## 3. Concept
Observabilitas jaringan (*Network Observability*) adalah kemampuan menyimpulkan kondisi internal (*internal state*) infrastruktur jaringan—mulai dari transit fabrics, load balancer, hingga network interfaces di host—hanya berdasarkan output eksternal (*telemetry signals*) yang dihasilkan.

Tiga pilar observabilitas jaringan modern melampaui paradigma monitoring tradisional:
1. **Metrics & Counters**: Data kuantitatif teragregasi secara berkala (interface packet drop, interface errors, BGP prefix count, CPU/Memory switch).
2. **Flow & Transit Metadata**: Rekaman metadata koneksi (5-tuple: Source IP, Dest IP, Source Port, Dest Port, Protocol) disertai bytes, packets, TCP flags, dan AS-Path yang melewati router/switch secara agregat atau sampling.
3. **Deep Telemetry & Packet Traces**: Streaming real-time berbasis event/interval internal ASIC/state change via gNMI, dipadukan dengan packet payload capture untuk analisis akar masalah (*root cause analysis/RCA*) forensik.

High Availability (HA) dan Resiliency jaringan bukan sekadar redundansi hardware (seperti dual PSU atau dual supervisor), melainkan kapabilitas data path dan control plane untuk pulih secara deterministik terhadap kegagalan komponen (link flap, transreceiver degradations, brain-split) tanpa intervensi manual.

---

## 4. Why
Monitoring konvensional mengandalkan SNMP polling (`snmpwalk`/`snmpget`) interval 5 menit. Paradigma ini telah **usang dan berbahaya** pada skala cloud-scale dan hyperscaler modern:
- **Blind Spots & Microbursts**: Buffer overrun pada switch ASIC yang berlangsung selama 15 milidetik dan mengakibatkan tail-drop ribuan paket TCP tidak akan pernah terdeteksi oleh SNMP polling 300 detik.
- **High CPU Overhead**: SNMP agent memproses request dengan model serial single-threaded CPU interrupt di switch control-plane, berisiko melumpuhkan proses routing saat switch sedang mengalami traffic stress.
- **Tingginya MTTR**: Tanpa data granularitas tinggi, tim network engineering menghabiskan 80% waktu insiden pada fase deteksi dan isolasi komponen (*blamestorming* antara tim aplikasi, platform, dan network).
- **Asumsi Keandalan Tanpa Uji**: Redundansi failover sering kali gagal berfungsi saat kondisi nyata (misal: BGP *keepalive timeout* terlalu lambat dibandingkan *application timeout*), yang seharusnya dapat diverifikasi melalui Chaos Engineering terukur.

---

## 5. What (Deep-Dive Teknis Lengkap)

### A. Flow Monitoring Protocols
| Fitur / Parameter | NetFlow v9 | IPFIX (RFC 7011) | sFlow v5 |
| :--- | :--- | :--- | :--- |
| **Arsitektur Dasar** | Cache-based / Flow aggregation | Cache-based (IETF standard NetFlow v10) | Statistical packet sampling (No cache) |
| **Header Format** | Proprietary Cisco (Template-based) | Extensible Template-based | Fixed format, payload sampling + counters |
| **Transport Layer** | UDP (umumnya port 2055) | UDP / TCP / SCTP (port 4739) | UDP (port 6343) |
| **Variable-Length Fields** | Terbatas | Mendukung (Enterprise Bit / Private IE) | Tidak mendukung (Fixed raw bytes slice) |
| **CPU Overhead Switch** | Sedang-Tinggi (Membuat flow cache) | Sedang-Tinggi (Membuat flow cache) | Sangat Rendah (Stateless ASIC sampling) |
| **Akurasi Volume** | Deterministik agregasi flow | Deterministik agregasi flow | Probabilistik (Estimasi matematika x Sampling Rate) |
| **Use Case Utama** | Capacity planning, billing, WAN traffic | Flow monitoring multi-vendor, enterprise tracing | Core backbone hyperscale, DDoS realtime detection |

- **NetFlow v9 / IPFIX Flow Record Engine**: Router mengumpulkan paket ke dalam *Flow Cache* berdasarkan kesamaan 7-key properties (Source IP, Destination IP, Source Port, Destination Port, Layer 3 Protocol, ToS/DSCP, Input Interface). Flow diekspor ke collector saat:
  - Inactive timeout tercapai (contoh: tidak ada traffic selama 15 detik).
  - Active timeout tercapai (contoh: koneksi streaming berjalan terus menerus hingga batas 1800 detik untuk mencegah flow counter overflow).
  - TCP Flag FIN atau RST terdeteksi.

### B. Streaming Telemetry (gNMI/gRPC)
gNMI (gRPC Network Management Interface) menggunakan HTTP/2 melalui TLS dengan payload yang diserialisasi via Protocol Buffers.
- **Model Data**: Memetakan struktur device menggunakan standar OpenConfig atau YANG data model vendor (Cisco IOS-XR, Arista EOS, Juniper JunOS).
- **Subscription Modes**:
  - `ON_CHANGE`: Switch hanya mengirim paket telemetri saat terjadi perubahan state (misal: BGP state berpindah dari `Established` ke `Idle`, atau port link down). Latensi deteksi mendekati 0 milidetik.
  - `SAMPLE`: Switch mengirim data secara periodik dengan interval sangat rendah (hingga 10-100 milidetik) langsung disalurkan oleh line-card processor tanpa membebani Main Routing Engine CPU.
  - `POLL`: On-demand synchronous telemetry retrieval.

### C. Packet Analysis: TCP Dissections
1. **TCP Retransmission Analysis**:
   - Terjadi akibat *packet loss* di intermediate path atau buffer queue drop.
   - Analisis via Wireshark: Evaluasi field `tcp.analysis.retransmission`, `tcp.analysis.fast_retransmission`, dan `tcp.analysis.spurious_retransmission`.
2. **TCP Window Problems**:
   - `TCP ZeroWindow`: Receiver mengiklankan Receive Window size = 0 (`tcp.window_size == 0`). Buffer socket OS aplikasi penuh (aplikasi mengalami bottleneck I/O atau blocking process). Pengirim wajib menahan transmisi data (*Zero Window Probe*).
   - `TCP Window Full`: Pengirim telah membanjiri data hingga batas buffer penerima yang diiklankan sebelum menerima ACK (`tcp.analysis.window_full`).
3. **MTU Mismatch & ICMP Black Hole**:
   - Jika paket berukuran 1500 byte dengan flag DF (*Don't Fragment*) diset melewati link dengan MTU 1400 (misal: tunnel GRE/IPsec), router harus merespons dengan *ICMP Type 3, Code 4 (Destination Unreachable, Fragmentation Needed and DF set)*.
   - Jika firewall memblokir seluruh ICMP transit, klien tidak akan pernah menurunkan MSS, mengakibatkan koneksi TLS handshake menggantung (*hang*) selamanya (MTU Black Hole).

### D. Chaos Engineering on Network Path
Memanipulasi karakteristik kernel queuing disciplines (`qdisc`) menggunakan Linux Traffic Control (`tc`):
- Injeksi packet loss probabilistik / burst loss (Gilbert-Elliott model).
- Injeksi latency jitter terdistribusi normal.
- Injeksi packet reordering dan corruption.

---

## 6. How
Implementasi stack observabilitas dan mitigasi jaringan dilakukan melalui alur integrasi:
1. **Konfigurasi Export Data Plane**:
   - Mengaktifkan IPFIX/NetFlow pada interface router core/edge.
   - Mengaktifkan gNMI daemon pada Network OS (NOS) dengan autentikasi mTLS.
2. **Pipeline Aggregation & Ingestion**:
   - Mengarahkan UDP NetFlow/sFlow ke collector (e.g., Logstash, Filebeat NetFlow module, FastNetMon, atau custom collector).
   - Menjalankan gNMI collector (e.g., Telegraf gNMI plugin) untuk mengumpulkan OpenConfig telemetri metrics dan mengirimkannya ke Prometheus/TimescaleDB.
3. **Dashboarding & Alerting**:
   - Membangun visualisasi di Grafana (p99 interface utilization, dropped packets delta, BGP session flap alerts).
4. **Triage & Deep Packet Inspection**:
   - Menggunakan automated script capture `tcpdump` ring-buffer pada host/gateway saat error rate melampaui *Service Level Objective* (SLO).
5. **Continuous Verification via Chaos**:
   - Mengeksekusi skenario kegagalan jaringan secara terjadwal di staging/canary infrastructure menggunakan script `tc` atau Chaos Mesh.

---

## 7. Analogy
Bayangkan jaringan enterprise sebagai sistem jalan tol antar-kota yang padat:
- **SNMP Polling (5 menit)**: Petugas tol menghitung jumlah mobil manual setiap 5 menit sekali. Jika ada kecelakaan beruntun selama 20 detik yang langsung terurai, petugas tidak melihat apa pun kecuali rata-rata hitungan kendaraan yang sedikit menurun.
- **Flow Monitoring (IPFIX/NetFlow)**: Kamera CCTV di gerbang tol mencatat struk tiket: *Mobil A masuk gerbang 1 pukul 08:00, keluar gerbang 4 pukul 08:15, membawa muatan 2 ton*. Anda tahu rute asal-tujuan dan volume beban tanpa melihat isi bagasi mobil.
- **sFlow**: Mengambil foto secara acak pada 1 dari setiap 1000 mobil yang melintas. Cepat, murah secara komputasi, dan secara statistik akurat memprediksi kepadatan truk gandeng vs mobil pribadi.
- **Streaming Telemetry (gNMI)**: Sensor IoT pada setiap aspal jalan dan palang pintu tol yang mengirimkan data getaran dan status buka/tutup secara instan via radio frekuensi tepat pada milidetik sensor tersebut terpicu.
- **Wireshark/tcpdump**: Petugas forensik membongkar isi bagasi setiap mobil di tempat kejadian perkara untuk memeriksa segel dokumen dan membuktikan kenapa barang bawaan rusak.

---

## 8. Diagram (ASCII)

### Arsitektur Observabilitas Jaringan Enterprise
```
  +-------------------------------------------------------------------------+
  |                             NETWORK FABRIC                              |
  |  +-----------------------+                   +-----------------------+  |
  |  |    Spine Switch 01    |                   |    Spine Switch 02    |  |
  |  |  (gNMI OpenConfig)    |                   |     (sFlow Agent)     |  |
  |  +-----------+-----------+                   +-----------+-----------+  |
  |              |                                           |              |
  |              +-------------------+   +-------------------+              |
  |                                  |   |                                  |
  |  +-------------------------------+---+-------------------------------+  |
  |  |                     Leaf Switch 01 (Border)                       |  |
  |  |                   IPFIX Exporter / gNMI Agent                     |  |
  |  +-------------------------------+-----------------------------------+  |
  +----------------------------------|--------------------------------------+
                 | (gRPC/gNMI Stream)|                   | (UDP Flow Export)
                 | TCP 57400         |                   | Port 2055/4739
                 v                   |                   v
  +------------------------------+   |   +----------------------------------+
  |    Telemetry Collector       |   |   |      Flow Collector Cluster      |
  |   (Telegraf / gnmic)         |   |   |      (FastNetMon / Logstash)     |
  +--------------+---------------+   |   +------------------+---------------+
                 |                   |                      |
                 v (Write Metrics)   |                      v (Store Documents)
  +------------------------------+   |   +----------------------------------+
  |      Time-Series DB          |   |   |        Search / Storage          |
  |   (Prometheus / Victoria)    |   |   |       (OpenSearch / ClickHouse)  |
  +--------------+---------------+   |   +------------------+---------------+
                 |                   |                      |
                 +-------------------+----------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |    Grafana Visualization & Alerting   |
                 |     Unified Network NOC Dashboard     |
                 +---------------------------------------+
```

### TCP Troubleshooting State Flowchart
```
                [ Packet Drop / Performance Degraded ]
                                  |
                                  v
              Capture Traffic: tcpdump -i any -nnvv
                                  |
        +-------------------------+-------------------------+
        |                                                   |
        v                                                   v
[ TCP Retransmissions? ]                            [ Zero Window Advertised? ]
        |                                                   |
   +----+----+                                         +----+----+
   |         |                                         |         |
 (YES)      (NO)                                     (YES)      (NO)
   |         |                                         |         |
   |         v                                         |         v
   |   [ MTU / Blackhole? ]                            |    Cek TCP Window
   |   ICMP Type 3 Code 4                              |    Full / BDP Limit
   v   blocked?                                        v
Cek Intermediate Link:                           Aplikasi penerima
- Hardware CRC Errors                            mengalami CPU Starvation /
- Switch ASIC Microburst                         I/O Hang (Kernel buffer
- Duplex mismatch / Cable                        penuh, app tidak read())
```

---

## 9. Simple Example
Menjalankan packet capture spesifik untuk mendeteksi *TCP SYN packet loss* dan *Reset* pada interface Linux gateway:
```bash
# Capture hanya TCP handshake failure (SYN tanpa ACK atau immediate RST)
sudo tcpdump -i eth0 -nn -ttt "tcp[tcpflags] & (tcp-syn|tcp-rst) != 0"
```
Filter Wireshark instan untuk isolasi anomali performa:
```text
tcp.analysis.retransmission || tcp.analysis.zero_window || tcp.flags.reset == 1
```

---

## 10. Practical Example

### A. Konfigurasi IPFIX pada Cisco IOS-XE / Enterprise Router
```text
! 1. Definisikan Flow Record
flow record FLOW-RECORD-INGRESS-ANALYTICS
 match ipv4 tos
 match ipv4 protocol
 match ipv4 source address
 match ipv4 destination address
 match transport source-port
 match transport destination-port
 match interface input
 collect interface output
 collect counter bytes long
 collect counter packets long
 collect timestamp sys-uptime first
 collect timestamp sys-uptime last
 collect transport tcp flags

! 2. Definisikan Flow Exporter
flow exporter EXPORTER-CENTRAL-COLLECTOR
 destination 192.168.100.50
 transport udp 4739
 source GigabitEthernet0/0/0
 template data timeout 60
 export-protocol ipfix

! 3. Definisikan Flow Monitor
flow monitor MONITOR-PERIMETER-TRAFFIC
 record FLOW-RECORD-INGRESS-ANALYTICS
 exporter EXPORTER-CENTRAL-COLLECTOR
 cache timeout active 60
 cache timeout inactive 15

! 4. Terapkan pada Interface
interface GigabitEthernet0/0/1
 ip flow monitor MONITOR-PERIMETER-TRAFFIC input
```

### B. Konfigurasi Telegraf untuk Ingestion gNMI Streaming Telemetry
File: `/etc/telegraf/telegraf.d/gnmi.conf`
```toml
[[inputs.gnmi]]
  addresses = ["leaf-router01.prod.infra:57400"]
  subscriptions = [
    { path = "/interfaces/interface/state/counters", subscription_mode = "sample", sample_interval = "5s" },
    { path = "/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state", subscription_mode = "on_change" }
  ]
  encoding = "proto"
  [inputs.gnmi.tls]
    tls_ca = "/etc/telegraf/certs/ca.pem"
    tls_cert = "/etc/telegraf/certs/client.crt"
    tls_key = "/etc/telegraf/certs/client.key"
    insecure_skip_verify = false

[[outputs.prometheus_client]]
  listen = ":9273"
  metric_version = 2
  path = "/metrics"
```

### C. Chaos Engineering via Linux Traffic Control (`tc`)
Simulasi degradasi jaringan terkendali pada link egress interface `eth1`:
```bash
# Tambahkan root netem qdisc: Packet loss 5% berdistribusi normal, latency 50ms +- 10ms
sudo tc qdisc add dev eth1 root netem delay 50ms 10ms loss 5%

# Tampilkan status aktif
tc -s qdisc show dev eth1

# Hapus injeksi chaos untuk memulihkan link
sudo tc qdisc del dev eth1 root
```

---

## 11. Real World Example
**Insiden FinTech Payment Gateway: Kasus TCP MTU Black Hole Pasca Migrasi Cloud Interconnect.**
- **Gejala**: Transaksi pembayaran berukuran kecil (koneksi API JSON < 1 KB) berhasil 100%. Transaksi invoice PDF terenkripsi TLS (ukuran > 4 KB) mengalami *timeout* 30 detik secara random.
- **Investigasi**:
  1. Eksekusi `tcpdump -i eth0 -nnvv 'tcp port 443'` pada web application gateway.
  2. Ditemukan TLS Handshake berhasil menyelesaikan *Client Hello*, *Server Hello*, dan *Key Exchange*.
  3. Namun, ketika Application Server mengirim paket *Application Data* berukuran 1514 bytes dengan flag `DF=1`, klien tidak merespons dengan `ACK`.
  4. Server melakukan `TCP Retransmission` berulang kali dengan ukuran segmen yang sama hingga link mati (*connection reset by peer*).
  5. Pengecekan route path menunjukkan penambahan overlay IPsec tunnel baru dengan MTU interface 1436 bytes di cloud router. Router intermediate mencoba mengirimkan `ICMP Type 3, Code 4`, namun diblokir oleh upstream security group rule: `Deny ICMP Any`.
- **Resolusi**:
  1. *Immediate mitigation*: Mengaktifkan TCP MSS Clamping pada core firewall/router:
     ```text
     iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
     ```
  2. *Permanent fix*: Memperbaiki ingress security group untuk mengizinkan `ICMP Fragmentation Needed` (Type 3, Code 4) dan menyamakan MTU standar Jumbo Frame pada internal interconnect. MTTR berhasil ditekan dari potensi 2 hari menjadi 35 menit.

---

## 12. Trade-offs

| Pendekatan | Keunggulan Utama | Konsekuensi / Kerugian |
| :--- | :--- | :--- |
| **sFlow vs IPFIX** | sFlow tidak memerlukan resource RAM router untuk tracking state table flow. Ideal untuk 100G/400G spine switches. | Kehilangan visibilitas transaksi mikro (low-volume single transaction attacks/anomalies terlewat dari sampling). |
| **gNMI Streaming vs SNMP Polling** | Resolusi real-time (sub-detik), on-change notifications, schema berbasis Protobuf yang deterministik. | Membutuhkan arsitektur collector modern, konsumsi storage time-series jauh lebih masif, kompleksitas konfigurasi TLS/PKI. |
| **Always-on Deep Packet Capture vs Flow-only Monitoring** | Forensik 100% akurat hingga payload level per paket. | Biaya storage I/O sangat ekstrem, potensi pelanggaran kepatuhan/privasi data (PII exposure), latency capture processing. |

---

## 13. When To Use
- Gunakan **IPFIX/NetFlow**: Untuk audit jejak koneksi WAN, penagihan bandwidth antardepartemen, pelacakan pergerakan lateral traffic (East-West security inspection), dan capacity planning link backbone.
- Gunakan **gNMI Streaming Telemetry**: Untuk mission-critical monitoring, validasi otomatis SLA jalur routing BGP, dan zero-latency alerting pada interface hardware flap.
- Gunakan **tcpdump/Wireshark**: Saat debugging kegagalan handshake TCP, performa lambat aplikasi berbasis protokol RPC/HTTP/TLS, dan investigasi anomali packet drop.
- Gunakan **Chaos Engineering**: Pada siklus CI/CD pipeline infrastruktur atau staging environment sebelum migrasi arsitektur data center baru.

---

## 14. When NOT To Use
- **JANGAN** gunakan *IPFIX full-caching* pada switch access berbiaya rendah dengan control-plane CPU terbatas di bawah traffic DDoS ratusan ribu pps—switch akan mengalami crash (*out of memory*). Gunakan sFlow pada skenario ini.
- **JANGAN** menggunakan *packet capture* tanpa filter (`tcpdump -i any -w dump.pcap`) langsung pada production router berkepanjangan; disk I/O akan tersaturasi dan memicu kernel packet dropping.
- **JANGAN** menjalankan Chaos Engineering di production tanpa *automated abort/kill-switch* dan observabilitas baseline yang matang.

---

## 15. Common Mistakes
1. **Mengabaikan Sampling Rate pada sFlow**: Menghitung absolute throughput sFlow langsung dari counter byte tanpa mengalikan rasio sampling (contoh: 1:2048), menghasilkan laporan kapasitas bandwidth 2000x lebih rendah dari fakta fisik.
2. **Memblokir Seluruh ICMP demi "Keamanan"**: Mengakibatkan pecahnya mekanisme Path MTU Discovery (PMTUD), menciptakan bug MTU blackhole yang sangat sulit dilacak oleh tim aplikasi.
3. **Mengabaikan Active Timeout Flow Monitoring**: Membiarkan default active timeout router pada 30 menit. Dampaknya, traffic stream panjang baru diekspor ke dashboard 30 menit setelah koneksi dimulai, menciptakan spike grafis artifisial yang keliru.
4. **BGP Keepalive Timers Default di Cloud**: Menggunakan timer BGP standar (Keepalive 60s, Hold-time 180s) pada failover multihomed connection, menyebabkan downtime 3 menit sebelum traffic dialihkan secara otomatis.

---

## 16. Best Practices
1. **Standarisasi Timers Flow Export**: Konfigurasi `active timeout` ke 60 detik dan `inactive timeout` ke 15 detik pada seluruh router fabric guna memastikan keseragaman visualisasi time-series data.
2. **Terapkan BFD (Bidirectional Forwarding Detection)**: Pasangkan protokol routing OSPF/BGP dengan BFD sub-second timer (misal: `interval 300 min_rx 300 multiplier 3`) untuk mendeteksi link down fisik/logis dalam kurun < 1 detik.
3. **Rolling Ring Buffer Capture**: Saat mengisolasi intermittent bugs dengan `tcpdump`, gunakan rolling buffer file terbatas:
   ```bash
   tcpdump -i eth0 -C 100 -W 10 -w /var/log/triage_capture.pcap
   ```
   *(Membatasi capture maksimal 10 file @ 100MB, mencegah hard drive server penuh).*
4. **Automated Triage Runbooks**: Integrasikan output telemetri alerts langsung ke script triage otomatis (misal: auto-capture diagnostic commands saat alert PagerDuty terpicu).

---

## 17. Troubleshooting

### Runbook Diagnostik Cepat Masalah Latensi / Packet Drop
```
Langkah 1: Identifikasi Titik Drop (Host vs Jaringan)
  CMD Host: netstat -s | grep -i retrans
  CMD Host: tc -s qdisc show
  CMD Switch: show interfaces counters errors | include [non-zero]
  -> Jika error counter di switch bertambah: Periksa Physical Layer / SFP optics (show interfaces transceiver).
  -> Jika tidak ada error di switch: Lanjut ke Langkah 2.

Langkah 2: Cek Indikasi Buffer Microburst
  CMD Switch: show hardware profile drop-counters / show platform packet-drop
  -> Evaluasi apakah Egress Queue tail drops bertambah tanpa peningkatan utilisasi interface 5-menitan.

Langkah 3: Trace TCP Path dengan Deep Inspection
  Jalankan tcpdump di kedua sisi (Source dan Destination host):
  CMD: tcpdump -nntt -c 1000 -i eth0 host <target_ip> and port <target_port> -w trace.pcap
  Analisis Trace:
  - Bandingkan Delta Timestamps.
  - Cari flag `tcp.analysis.duplicate_ack` berurutan (indikasi packet loss out-of-order di path).
```

---

## 18. Exercise
1. Buat filter `tcpdump` untuk menangkap hanya paket TCP dengan flag RST (Reset) aktif, tidak termasuk handshake RST-ACK biasa.
2. Buat konfigurasi Linux Traffic Control (`tc`) yang menyimulasikan link satelit: Delay 600ms, jitter 50ms, dan packet loss 2%.
3. Tuliskan analisis perintah Wireshark yang digunakan untuk menemukan sesi TCP yang mengalami bottleneck kapasitas buffer pengirim (*Send Buffer Exhaustion*).

---

## 19. Challenge
Rancang arsitektur telemetri jaringan untuk sistem data center multi-region (3 Region, masing-masing memiliki 4 Spine dan 16 Leaf switch). Sistem wajib:
- Mendeteksi anomali route flap BGP di bawah 1 detik.
- Menyimpan metadata 100% flow jaringan untuk kebutuhan kepatuhan PCI-DSS selama 90 hari tanpa membebani storage secara eksponensial.
- Menyediakan automated fallback circuit breaker berbasis traffic drop telemetri.
Tuliskan cetak biru teknis komponen yang Anda pilih (Collector, Storage, Bus, Visualization) beserta justifikasi matematis rasio kompresi data flow.

---

## 20. Summary
- Observabilitas jaringan modern bergeser dari passive SNMP polling menuju real-time streaming telemetry (gNMI) dan granular flow analysis (IPFIX/sFlow).
- Kegagalan performa TCP umumnya berakar pada tiga hal: *Packet Loss / Microburst Drops*, *Receive Window Bottlenecks (Zero Window)*, dan *Path MTU Discrepancies (Black Hole)*.
- High Availability tidak hanya membutuhkan link ganda, tetapi juga integrasi sub-second failure detection (BFD) dan validasi agresif berkelanjutan via Chaos Engineering (`tc-netem`).
- Kedisiplinan Network Triage berbasis Runbook terstruktur secara radikal memangkas MTTR dari hitungan jam ke menit.