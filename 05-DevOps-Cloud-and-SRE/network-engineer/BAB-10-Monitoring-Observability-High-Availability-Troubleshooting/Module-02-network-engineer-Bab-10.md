# Kurikulum Enterprise Network Engineering: Bab 10 - Modul 02
## Topik: Monitoring, Observability, High-Availability, & Troubleshooting Lanjutan

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan memiliki kemampuan komprehensif untuk:
1. **Merancang & Mengimplementasikan Arsitektur Telemetri Modern**: Menggantikan paradigma polling legacy (*SNMP polling*) dengan streaming telemetry berbasis *push* (*gNMI/OpenConfig* via gRPC dan protobuf) serta integrasi *eBPF* untuk *packet-level tracing*.
2. **Membangun Sistem High-Availability (HA) Jaringan Berlapis**: Mengonfigurasi dan mengoptimalkan failover *active/active* dan *active/standby* menggunakan kombinasi *VRRP/Keepalived*, *BGP Anycast*, dan *ECMP (Equal-Cost Multi-Path)*.
3. **Mendeteksi & Memitigasi Masalah Kinerja Trancient**: Mengidentifikasi anomali jaringan non-linear seperti *microbursts*, degradasi jitter sub-milidetik, dan *silent packet drops* melalui instrumentasi metrik granular beresolusi tinggi.
4. **Menerapkan *Automated Self-Healing Infrastructure***: Merancang *closed-loop remediation pipeline* yang mengintegrasikan monitoring alert dengan kontrol routing terotomatisasi (misal: penarikan *BGP prefix* berbasis deteksi degradasi tautan transmisi).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
* Fundamental protokol routing dinamis: BGP (eBGP/iBGP), OSPF, dan konsep *Convergence Time*.
* Model transmisi data: TCP/IP Stack, UDP, ICMP, struktur header IPv4/IPv6, dan segmentasi MTU/MSS.
* Sistem operasi Linux tingkat lanjut: Linux network namespaces, routing tables (`iproute2`), iptables/nftables, dan manipulasi socket kernel.
* Pemahaman dasar arsitektur observabilitas: Metrik (Prometheus Exposition Format), Logging (JSON/Structured log), Tracing kontekstual, dan Message Broker (Kafka/NATS).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Evolusi Network Telemetry: SNMP Polling vs. Push-Based gNMI Telemetry
Monitoring jaringan konvensional mengandalkan SNMP (*Simple Network Management Protocol*) dengan metode *pull/polling*. Pada jaringan enterprise skala besar dengan puluhan ribu antarmuka, polling setiap 5 menit memicu fenomena *telemetry debt* dan overhead komputasi CPU switch/router yang signifikan.

```
+-----------------------------------------------------------------------------------+
|                        SNMP Polling (Pull Architecture)                           |
|                                                                                   |
|  [ Collector ]  -- (1) SNMP-GET Request (Interval 5 Min) -->  [ Network Switch ]  |
|                 <-- (2) SNMP-Response (High CPU Context Switch) - [ Control Plane ]|
|                                                                                   |
|  Masalah: Latensi data tinggi, membebani CPU switch, risiko query drop saat peak. |
+-----------------------------------------------------------------------------------+
|                        gNMI Telemetry (Push Architecture)                         |
|                                                                                   |
|  [ Collector ]  <=== (Stream Protobuf via HTTP/2 gRPC) ======  [ Network Switch ]  |
|                        - Sub-second cadence                     [ Datapath / NPU ] |
|                        - Event-driven (On-Change)                                 |
|                                                                                   |
|  Keunggulan: Efisiensi komputasi tinggi, real-time, payload terkompresi biner.  |
+-----------------------------------------------------------------------------------+
```

* **gNMI (gRPC Network Management Interface)**: Dibangun di atas protokol HTTP/2 dengan serialisasi Protobuf (*Protocol Buffers*). Menggunakan koneksi TCP persisten, memungkinkan switch mempublikasikan status antarmuka dan *counter buffer* secara *streamed* langsung dari *Forwarding Engine (NPU/ASIC)* tanpa membebani *Control Plane (Routing Engine)* switch.
* **Subscriptions Model**: Mendukung mode `ON_CHANGE` (hanya mengirim data ketika status berubah, misal: *link down*) dan `SAMPLE` (mengirim data secara berkala, misal: metrik *octets/second* dengan resolusi hingga 10 milidetik).

#### 3.2. Kernel-Level Observability via eBPF (Extended Berkeley Packet Filter)
Pada level host/server yang menjalankan containerisasi dan overlay network (misal: VXLAN, Calico, Cilium), pemantauan jaringan konvensional via `/proc/net/dev` atau *libpcap* (*tcpdump*) menimbulkan *overhead* performa karena context switching antara *kernel space* dan *user space*.

* **eBPF Execution Flow**: Program eBPF di-inject langsung ke dalam hook kernel jaringan, seperti:
  * **XDP (eXpress Data Path)**: Menjalankan eksekusi kode pada level driver kartu jaringan (NIC) sebelum paket dialokasikan ke struktur kernel `sk_buff`. Ideal untuk mitigasi DDoS kecepatan tinggi dan inspeksi metrik awal.
  * **TC (Traffic Control)**: Mencegat paket pada ingress/egress layer network stack kernel.
  * **Sockops / Kprobe**: Mencegat pemanggilan sistem (system calls) seperti `tcp_v4_connect`, mendeteksi latensi *Three-Way Handshake* TCP, dan menangkap *TCP retransmissions* secara *real-time* langsung dari *kernel ring buffer*.

#### 3.3. Arsitektur High-Availability: Multi-Tier Redundancy
Untuk mencapai ketersediaan layanan *four-nines* (99.99%) atau lebih tinggi, redundansi jaringan harus diimplementasikan pada dua layer utama:

1. **Layer 2/Layer 3 Edge: VRRP / Keepalived**:
   * Mengelompokkan dua atau lebih gateway fisik/virtual menjadi satu *Virtual IP (VIP)*.
   * Node *Master* merespons paket ARP untuk VIP tersebut. Jika *Master* gagal mengirimkan frame *heartbeat* secara periodik, node *Backup* mengambil alih kepemilikan VIP melalui *gratuitous ARP*.
2. **Layer 3 Scale-Out: BGP Anycast & ECMP (Equal-Cost Multi-Path)**:
   * Beberapa server load balancer (misal: Envoy, NGINX, HAProxy) mengiklankan IP alamat yang sama (*Anycast IP*) via protokol routing BGP (misal menggunakan ExaBGP/BIRD) ke switch *ToR (Top-of-Rack)*.
   * Switch ToR mendistribusikan beban trafik masuk ke seluruh node load balancer secara merata menggunakan algoritma *ECMP 5-tuple hash* (`Src IP`, `Dst IP`, `Src Port`, `Dst Port`, `Protocol`). Jika salah satu server mati, sesi BGP terputus dan switch otomatis menghapus server tersebut dari tabel forwarding tanpa interupsi global.

---

### 4. Why & What

| Dimensi | Legacy Approach | Modern Enterprise Approach |
| :--- | :--- | :--- |
| **Metode Koleksi** | SNMP v2c/v3 Polling periodik (1-5 menit). | gNMI/Streaming Telemetry (*push*) sub-detik & On-Change events. |
| **Visibilitas Node** | Inspeksi *blackbox* di antarmuka switch saja. | End-to-end tracing: Host kernel (eBPF) + Overlay Network + Underlay ASIC. |
| **Redundansi Edge** | Active/Passive dengan VRRP konvensional (kapasitas server standby menganggur). | Active/Active horizontal scaling berbasis BGP Anycast + ECMP. |
| **Deteksi Problem** | Reaktif berdasarkan keluhan pengguna atau alert statis Ambang Batas 80%. | Proaktif berbasis *synthetic probes* (TWAMP/Blackbox), *p99 latency*, dan *TCP Window clamping*. |
| **Remediasi** | Manual ticketing, SSH login engineer, manual route change. | *Automated Closed-Loop Remediation* (Event-driven controller, auto-drain traffic). |

---

### 5. How (Workflow Detail)

Alur kerja operasional observabilitas dan High-Availability jaringan end-to-end:

```
[ Paket Ingress dari Klien ]
            |
            v
+-----------------------+
|  Switch Spine/Leaf   | ---> [gNMI Stream: Octets, Drops, Queue Depth]
|  (BGP ECMP Hashing)   |                         |
+-----------------------+                         v
      |            |                +---------------------------+
  Server A     Server B             | Telegraf / Vector Agents  |
 (BGP Anycast) (BGP Anycast)        +---------------------------+
      |            |                              |
      +-----+------+                              v
            |                        +--------------------------+
  [ Linux Host Ingress ]             | Prometheus / TimescaleDB |
    - eBPF Hook (TC/Socket) -------->| (Time-Series Database)   |
    - Keepalived State Watcher       +--------------------------+
            |                                     |
            v                                     v
  [ Application Service ]            +--------------------------+
                                     | Alertmanager & Operator  |
                                     | (Automated Remediation)  |
                                     +--------------------------+
```

1. **Ingestion & Metric Scraping**: Router dan switch mempublikasikan *state tree* berbasis model data YANG melalui kanal gRPC streaming ke agregator metrik (*Telegraf* atau *Vector*).
2. **Kernel Telemetry Capture**: Agent eBPF pada setiap worker host mengumpulkan metrik paket per koneksi socket TCP (`RTT`, `Retransmits`, `Zero-Window Size`).
3. **Synthetic Path Probing**: Container penguji terdistribusi meluncurkan paket *TWAMP (Two-Way Active Measurement Protocol)* atau *ICMP/TCP Blackbox probe* setiap 500ms untuk mengukur latensi dan paket loss riil antar availability zone.
4. **Analisis Anomali & Alerting**: Prometheus mengevaluasi ekspresi kuantil (misal: `rate(node_network_transmit_drop_total[1m]) > 0.01`).
5. **Closed-Loop Action**: Jika alert kritis terpicu (misal: jitter melebihi ambang batas SLA pada *Path A*), automated automation runner mengeksekusi BGP prepend script untuk mengalihkan lalu lintas secara mulus ke *Path B*.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan jalan tol antar kota:
* **SNMP Polling**: Petugas loket menelpon pos pengawas setiap 5 menit sekali menanyakan jumlah antrean mobil. Jika ada kecelakaan beruntun di menit ke-1, pengawas baru mengetahuinya di menit ke-5.
* **Streaming Telemetry & eBPF**: Sensor radar kecepatan dan CCTV cerdas dipasang di setiap 50 meter jalan dan di dalam mobil itu sendiri. Begitu mobil melambat drastis atau menabrak pembatas jalan (*packet drop*), notifikasi instan terkirim dalam waktu milidetik ke pusat pengendali lalu lintas.
* **BGP Anycast**: Gerbang tol memiliki 10 pintu masuk yang identik. Pengendara secara otomatis diarahkan ke pintu gerbang terdekat atau yang paling lengang secara dinamis (*ECMP*). Jika pintu nomor 3 rusak, papan penunjuk arah elektronik langsung menghapus pintu nomor 3 dari opsi jalur.

#### Arsitektur Produksi High-Availability Enterprise

```
                                      INTERNET
                                         |
                        +----------------+----------------+
                        |                                 |
                 +--------------+                 +--------------+
                 |  Edge-R1     |                 |  Edge-R2     |
                 |  (BGP eBGP)  |                 |  (BGP eBGP)  |
                 +--------------+                 +--------------+
                        |        \               /        |
                        |         \             /         |
                        |          \           /          |
                 +--------------+  +--------------+  +--------------+
                 |  Spine-01    |  |  Spine-02    |  |  Spine-03    |
                 +--------------+  +--------------+  +--------------+
                        |     \       /       \       /     |
                   (ECMP)      (ECMP)          (ECMP)     (ECMP)
                        |       \   /           \   /       |
                 +--------------+  +--------------+  +--------------+
                 | Leaf-01 (ToR)|  | Leaf-02 (ToR)|  | Leaf-03 (ToR)|
                 +--------------+  +--------------+  +--------------+
                     |        \      /          \      /        |
                     |         \    /            \    /         |
           +---------+--+      +-+--+-------+    +-+--+-------+ |
           | Load Balancer |   | Load Balancer | | Load Balancer|
           | LB-Node-01    |   | LB-Node-02    | | LB-Node-03   |
           | IP: 10.0.0.1  |   | IP: 10.0.0.2  | | IP: 10.0.0.3 |
           | ANYCAST VIP:  |   | ANYCAST VIP:  | | ANYCAST VIP: |
           | 198.51.100.1  |   | 198.51.100.1  | | 198.51.100.1 |
           +---------------+   +---------------+ +--------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Blackbox Exporter Configuration (ICMP & TCP Check)
File konfigurasi `blackbox.yml` untuk mendeteksi *packet loss* dan latensi TCP SYN secara presisi:

```yaml
modules:
  icmp_probe:
    prober: icmp
    timeout: 3s
    icmp:
      preferred_ip_protocol: ip4
  
  tcp_syn_probe:
    prober: tcp
    timeout: 2s
    tcp:
      preferred_ip_protocol: ip4
      query_response: []
```

Prometheus Scrape Job (`prometheus.yml`):

```yaml
scrape_configs:
  - job_name: 'blackbox-latency-mesh'
    metrics_path: /probe
    params:
      module: [icmp_probe]
    static_configs:
      - targets:
        - 198.51.100.1      # Anycast VIP
        - 10.10.10.1        # Core Switch Leaf-01
        - 10.10.20.1        # Core Switch Leaf-02
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: 127.0.0.1:9115  # Blackbox exporter agent
```

#### 7.2. Practical Example (Production Grade)

##### A. Konfigurasi Keepalived Multi-Node dengan Tracking Script & Asymmetric Weight
Implementasi Keepalived pada node Load Balancer Linux dengan tracking socket aktif dan dynamic weight adjustment:

`/etc/keepalived/keepalived.conf` (Node: LB-Node-01 - Master Candidate):

```ini
global_defs {
    router_id LB_NODE_01
    enable_script_security
    script_user root
}

vrrp_script chk_haproxy {
    # Memeriksa port layanan secara lokal dengan timeout ketat
    script "/usr/bin/nc -z -w 1 127.0.0.1 443"
    interval 1   # Eksekusi setiap 1 detik
    fall 2       # Gagal 2 kali berturut-turut untuk menyatakan DOWN
    rise 2       # Berhasil 2 kali untuk pulih
    weight -20   # Kurangi prioritas sebesar 20 jika script exit-code != 0
}

vrrp_instance VI_STATIC_VIP {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 101       # Lebih tinggi dari Node 02 (priority 90)
    advert_int 1
    
    authentication {
        auth_type PASS
        auth_pass Secr3tK3yTr4ffic
    }

    unicast_src_ip 10.0.0.1
    unicast_peer {
        10.0.0.2
    }

    virtual_ipaddress {
        198.51.100.1/32 dev eth0 label eth0:vip
    }

    track_script {
        chk_haproxy
    }

    # Notifikasi transisi state
    notify_master "/usr/local/bin/keepalived_notify.sh MASTER"
    notify_backup "/usr/local/bin/keepalived_notify.sh BACKUP"
    notify_fault  "/usr/local/bin/keepalived_notify.sh FAULT"
}
```

##### B. Deteksi TCP Packet Drops Menggunakan eBPF (bpftrace)
Skrip sistem `tcp_drops.bt` untuk pemantauan tingkat kernel terhadap *TCP drops* dan pelacakan penyebab kernel (*return reason*):

```c
#!/usr/bin/env bpftrace

#include <net/sock.h>
#include <linux/tcp.h>

BEGIN
{
    printf("Menjalankan trace TCP Drops... Tekan Ctrl-C untuk berhenti.\n");
    printf("%-8s %-16s %-20s %-20s %-10s\n", "TIME", "COMM", "SRC", "DST", "STATE");
}

kprobe:tcp_drop
{
    $sk = (struct sock *)arg0;
    $inet_family = $sk->__sk_common.skc_family;

    if ($inet_family == 2) { // AF_INET (IPv4)
        $daddr = ntop(2, $sk->__sk_common.skc_daddr);
        $saddr = ntop(2, $sk->__sk_common.skc_rcv_saddr);
        $dport = $sk->__sk_common.skc_dport;
        $sport = $sk->__sk_common.skc_num;
        $state = $sk->__sk_common.skc_state;

        // Big-endian ke little-endian bitshift untuk port tujuan
        $dport = (($dport >> 8) | (($dport << 8) & 0x00FF00));

        time("%H:%M:%S ");
        printf("%-16s %s:%d -> %s:%d (State: %d)\n", 
               comm, $saddr, $sport, $daddr, $dport, $state);
        
        // Simpan agregasi call stack penyebab kernel drop paket
        @[kstack] = count();
    }
}
```

##### C. Production-Grade Prometheus Alerting Rules
Aturan deteksi anomali jaringan pada `alerts_network.yml`:

```yaml
groups:
  - name: enterprise_network_observability
    rules:
      - alert: NetworkInterfaceDropsHigh
        expr: (sum by (instance, device) (rate(node_network_drop_total[2m])) / 
               sum by (instance, device) (rate(node_network_packets_total[2m]))) * 100 > 0.05
        for: 1m
        labels:
          severity: critical
          tier: networking
        annotations:
          summary: "Tingkat Packet Drop Kritis pada antarmuka {{ $labels.device }} di {{ $labels.instance }}"
          description: "Persentase drop paket melebihi 0.05% selama lebih dari 1 menit. Nilai saat ini: {{ $value | printf \"%.4f\" }}%."

      - alert: KeepalivedNodeStateFault
        expr: keepalived_vrrp_state{state="fault"} == 1
        for: 0s
        labels:
          severity: page
          tier: edge-gateway
        annotations:
          summary: "Node Keepalived {{ $labels.instance }} mengalami status FAULT"
          description: "VRRP Instance {{ $labels.vrrp_instance }} masuk ke status FAULT. Layanan routing dialihkan atau down."
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: Flash Sale "Silent Drops" pada Tier-1 E-Commerce
* **Latar Belakang**: Perusahaan e-commerce multinasional mengalami lonjakan transaksi *Flash Sale* sebesar 300.000 *Requests Per Second (RPS)*.
* **Gejala Insiden**: Selama lonjakan, sistem pelaporan aplikasi mencatat ribuan HTTP 504 (Gateway Timeout), namun utilisasi bandwidth pada seluruh *Spine-Leaf switches* hanya berada di angka 45%, dan metrik CPU switch berada pada ambang aman 30%. Monitoring SNMP konvensional dengan interval 5 menit tidak mencatat adanya anomali atau interface down.
* **Investigasi Mendalam**:
  1. *Telemetry Resolution Gap*: Polling SNMP 5 menit menyembunyikan lonjakan trafik mendadak (*microbursts*) berdurasi 100 milidetik yang melampaui kapasitas buffer port switch (*ASIC Packet Buffer*).
  2. *eBPF Trace Analysis*: Tim Network SRE menjalankan skrip pelacak kernel eBPF dan menemukan ribuan panggilan `tcp_drop` dengan alasan kernel `TCP_OFOMARGIN` (out of order margin exhaustion) dan drop akibat `sk_backlog_rcv`.
  3. *gNMI Telemetry Deployment*: Tim mengaktifkan *gNMI streaming telemetry* dengan resolusi sampling 100ms untuk metrik antarmuka `openconfig-qos:queue-drops`. Hasilnya terlihat jelas bahwa terjadi fenomena *buffer exhaustion* pada *egress buffer* antarmuka switch Leaf yang terhubung ke rack database.
* **Solusi Arsitektur**:
  1. Mengonfigurasi ulang alokasi *Dynamic Buffer Sharing (Alpha Profile)* pada ASIC switch untuk memberikan ruang buffer cadangan yang lebih elastis pada port dengan burst tinggi.
  2. Mengimplementasikan *ECMP Resilient Hashing* dan BGP Anycast pada layer Ingress Gateway untuk menghindari polarisasi hash lalu lintas ke salah satu spine switch.
  3. Memasang pipeline streaming gNMI permanen yang dialirkan ke Kafka dan Prometheus, terhubung dengan modul mitigasi otomatis: jika drop queue rate switch > 500 paket/detik dalam window 5 detik, router edge otomatis mengaktifkan *Explicit Congestion Notification (ECN)* dan mengurangi flow rate melalui *BGP Flowspec*.

---

### 9. Trade-offs

| Pilihan Arsitektur | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- |
| **gNMI Streaming Telemetry** vs **SNMP v3** | Sangat granular (sub-detik), *push-based*, efisien komputasi CPU switch, skema data standar (YANG). | Membutuhkan switch modern, resource penyimpanan metrik membengkak signifikan, setup pipeline data (Kafka/Collectors) lebih rumit. |
| **eBPF-based Tracing** vs **Hardware SPAN/TAP** | Visibilitas software layer mendalam (socket, thread, process), zero-cost hardware tambahan, fleksibel. | Membutuhkan kernel Linux modern (v5.4+), mengonsumsi sebagian kecil CPU host lokal, kompleksitas kompilasi & debugging kode C kernel. |
| **BGP Anycast (L3 HA)** vs **VRRP/Keepalived (L2 HA)** | *Active/Active true load-balancing*, skala kapasitas tak terbatas secara horizontal, tidak ada *single point of failure*. | *Asymmetric routing issues*, penanganan koneksi persisten/stateful (TCP) menjadi sangat menantang jika ECMP hash berubah. |
| **Synthetic Probing Agresif (Setiap 100ms)** vs **Standar (Setiap 5s)** | Deteksi kegagalan transien instan (*failover* lebih cepat), SLA measurement akurat. | Menghasilkan overhead trafik probing artifisial, risiko *false-positive alerts* tinggi akibat noise jitter sesaat. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi (Common Pitfalls)
1. **Split-Brain VRRP**: Konfigurasi firewall memblokir paket protokol IP 112 (VRRP) antar host. Akibatnya, kedua host mengklaim status `MASTER` dan merespons paket ARP secara bersamaan, memicu fenomena *IP collision* dan paket drop acak bagi klien.
2. **ECMP Hash Polarization**: Beberapa layer switch menggunakan algoritma hashing yang identik pada header paket yang sama. Hal ini menyebabkan paket yang didistribusikan pada Hop 1 selalu terkonsentrasi hanya ke salah satu link tertentu pada Hop 2 (*imbalanced traffic distribution*).
3. **SNMP Poller Timeout Cascades**: Meningkatkan interval scraping SNMP menjadi terlalu sering (misal: 10 detik sekali pada switch chassis besar). Control Plane switch kehabisan resource untuk memproses routing updates karena seluruh siklus CPU dialokasikan untuk melayani daemon *snmpd*.

#### Troubleshooting Guide Matrix

| Gejala Masalah | Investigasi Level 1 & 2 | Akar Masalah Potensial | Tindakan Remediasi Teruji |
| :--- | :--- | :--- | :--- |
| VIP VRRP tidak dapat dijangkau berselang-seling. | `tcpdump -nnvv -i any proto 112` | Split-Brain: Host backup tidak menerima VRRP advertisement dari host master. | Izinkan protokol 112 di `iptables`/`nftables` atau perbaiki enkapsulasi VLAN trunking switch. |
| Koneksi TCP terputus mendadak saat routing stabil. | `bpftrace tcp_drops.bt` dan `netstat -s \| grep -i listen` | *Listen backlog queue overflow* pada host akibat rate ingress melebihi batas aplikasi. | Tingkatkan nilai kernel parameter `net.core.somaxconn` dan `net.ipv4.tcp_max_syn_backlog`. |
| Flapping state BGP Anycast antar node. | Cek log BIRD/ExaBGP: `hold timer expired` | Paket BGP Keepalive terhambat karena CPU switch tercekik beban tinggi atau *Control Plane Policing (CoPP)*. | Terapkan QoS prioritas tinggi (DSCP CS6) untuk traffic BGP, atau tingkatkan timer *BGP Hold Time*. |
| Latensi spike setiap 5 menit secara konstan. | Korelasikan waktu spike dengan cronjob atau scrape interval prometheus. | Poller SNMP berat melakukan full table walk (misal: BGP table full dump) secara sinkron. | Pindahkan monitoring ke gNMI sub-path spesifik, hindari *full-table SNMP walks*. |

---

### 11. Best Practices (Production Checklist)

#### Pre-Production Deployment
- [ ] Protokol VRRP (IP 112) telah diisolasi dalam VLAN/Subnet manajemen atau diamankan dengan password otentikasi internal.
- [ ] Konfigurasi `net.ipv4.ip_nonlocal_bind = 1` diaktifkan pada sistem operasi agar Load Balancer dapat bind Anycast VIP sebelum interface resmi up.
- [ ] Konfigurasi MTU jaringan underlay (1500) dan overlay/VXLAN (minimal 1550-9000 bytes Jumbo Frames) telah diselaraskan untuk mencegah fragmentasi paket.
- [ ] Penentuan timer VRRP: `advert_int` diset ke 1 detik dengan toleransi loss 3 interval (`fall 3`) guna mencegah transisi state semu (*flapping*).

#### In-Flight Telemetry & Monitoring Operations
- [ ] Monitoring gNMI switch diatur menggunakan filter sub-tree spesifik (hindari streaming root `/`).
- [ ] *ECN (Explicit Congestion Notification)* diaktifkan di switch edge untuk memberikan sinyal perlambatan ke klien sebelum paket di-drop secara paksa.
- [ ] Probe Blackbox terdistribusi di minimal 3 ketersediaan zona berbeda (*cross-rack / cross-DC*).
- [ ] Ambang batas alert menggunakan dynamic anomaly detection atau perbandingan kuantil (p95/p99) daripada threshold absolut statis.

#### Post-Incident & Continual Validation
- [ ] Menjalankan uji *Chaos Engineering* secara rutin: Matikan paksa antarmuka switch master atau terminate proses `keepalived` secara acak (`kill -9`) untuk memvalidasi zero downtime.
- [ ] Analisis data pasca-insiden menggunakan data retensi log kernel eBPF dan metric history streaming telemetry resolusi tinggi.

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun sistem High-Availability Gateway menggunakan Linux Network Namespaces dan Keepalived, serta mengonfigurasi probe pemantau latensi dan mendeteksi drop paket. Seluruh file disimpan pada direktori target: `hands-on/m02/`.

#### Langkah 1: Setup Struktur Proyek & Namespace Jaringan
Jalankan skrip berikut untuk membuat simulasi dua node load balancer (`node01`, `node02`) dan satu client (`client01`) dalam Linux network namespaces:

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/

cat << 'EOF' > setup_env.sh
#!/bin/bash
set -e

# Bersihkan konfigurasi lama
ip -all netns delete 2>/dev/null || true
ip link delete br-core 2>/dev/null || true

# Buat Bridge Switch Inti
ip link add br-core type bridge
ip link set br-core up

# Buat Namespace
ip netns add node01
ip netns add node02
ip netns add client01

# Hubungkan Node01 ke Bridge
ip link add veth-n1 type veth peer name ceth-n1
ip link set veth-n1 netns node01
ip link set ceth-n1 master br-core up
ip netns exec node01 ip addr add 192.168.100.11/24 dev veth-n1
ip netns exec node01 ip link set veth-n1 up

# Hubungkan Node02 ke Bridge
ip link add veth-n2 type veth peer name ceth-n2
ip link set veth-n2 netns node02
ip link set ceth-n2 master br-core up
ip netns exec node02 ip addr add 192.168.100.12/24 dev veth-n2
ip netns exec node02 ip link set veth-n2 up

# Hubungkan Client ke Bridge
ip link add veth-cl type veth peer name ceth-cl
ip link set veth-cl netns client01
ip link set ceth-cl master br-core up
ip netns exec client01 ip addr add 192.168.100.100/24 dev veth-cl
ip netns exec client01 ip link set veth-cl up

echo "Topology Created Successfully!"
EOF

chmod +x setup_env.sh
sudo ./setup_env.sh
```

#### Langkah 2: Konfigurasi Keepalived Master & Backup
Buat konfigurasi Keepalived untuk `node01` (Master) dan `node02` (Backup).

`hands-on/m02/keepalived-node01.conf`:
```ini
global_defs {
    router_id NODE01
}

vrrp_instance VI_1 {
    state MASTER
    interface veth-n1
    virtual_router_id 50
    priority 100
    advert_int 1
    authentication {
        auth_type PASS
        auth_pass Secret102
    }
    virtual_ipaddress {
        192.168.100.254/24 dev veth-n1
    }
}
```

`hands-on/m02/keepalived-node02.conf`:
```ini
global_defs {
    router_id NODE02
}

vrrp_instance VI_1 {
    state BACKUP
    interface veth-n2
    virtual_router_id 50
    priority 90
    advert_int 1
    authentication {
        auth_type PASS
        auth_pass Secret102
    }
    virtual_ipaddress {
        192.168.100.254/24 dev veth-n2
    }
}
```

#### Langkah 3: Eksekusi Daemons & Uji Failover
Jalankan Keepalived pada masing-masing namespace:

```bash
# Jalankan keepalived di masing-masing namespace
sudo ip netns exec node01 keepalived -f $(pwd)/keepalived-node01.conf -p /run/keepalived-n1.pid -r /run/vrrp-n1.pid
sudo ip netns exec node02 keepalived -f $(pwd)/keepalived-node02.conf -p /run/keepalived-n2.pid -r /run/vrrp-n2.pid

# Verifikasi kepemilikan VIP 192.168.100.254 pada node01
sudo ip netns exec node01 ip addr show dev veth-n1
sudo ip netns exec node02 ip addr show dev veth-n2

# Uji ping berkelanjutan dari client01 ke Virtual IP
sudo ip netns exec client01 ping -c 5 192.168.100.254

# Simulasikan Kegagalan Antarmuka Master Node01
sudo ip netns exec node01 ip link set veth-n1 down

# Verifikasi failover: VIP berpindah ke node02
sleep 2
sudo ip netns exec node02 ip addr show dev veth-n2
sudo ip netns exec client01 ping -c 3 192.168.100.254
```

---

### 13. Exercise

#### Level: Easy
1. Ubah konfigurasi Keepalived pada skenario Hands-on di atas untuk menambahkan tracking script yang memantau file dummy `/tmp/healthcheck.flag`. Jika file tersebut tidak ditemukan, prioritaskan transisi state failover dari `MASTER` ke `BACKUP`.
2. Lakukan verifikasi pergantian VIP dengan perintah `ip monitor` dari sisi klien.

#### Level: Medium
1. Pasang dan jalankan Prometheus Blackbox Exporter di Linux host.
2. Tuliskan skrip konfigurasi prometheus scrape job untuk memantau waktu respons TCP handshake port 443 pada 3 domain cloud publik eksternal yang berbeda secara periodik setiap 1 detik.
3. Buat visualisasi tabel statistik respons latensi menggunakan Prometheus PromQL query `probe_duration_seconds`.

#### Level: Hard
1. Buat program `bpftrace` yang melacak socket call `tcp_retransmit_skb`. Program harus mengekstrak:
   * Alamat IP Sumber dan Tujuan.
   * Port Sumber dan Tujuan.
   * Nilai *Slow Start Threshold* (`snd_ssthresh`) dan *Congestion Window Size* (`snd_cwnd`).
2. Jalankan simulasi traffic buatan menggunakan `iperf3` dengan menambahkan *network latency* dan *loss* buatan via perintah `tc qdisc add dev eth0 root netem loss 5%`, lalu capture hasil mitigasi windowing TCP-nya melalui output program bpftrace Anda.

---

### 14. Challenge

**Judul Studi Kasus:** *The Ghost Microburst & The BGP Anycast Polarization Catastrophe*

**Deskripsi Kasus & Arsitektur Sistem:**
Anda adalah Principal Infrastructure Architect pada perusahaan perbankan terdesentralisasi. Sistem payment gateway Anda terdiri dari 8 server Load Balancer (LB) terdistribusi yang mengiklankan prefix Anycast VIP `198.51.100.50/32` menggunakan routing protokol BIRD (BGP) ke 2 buah switch Spine dan 4 switch Leaf berbasis Arista (Leaf-Spine Underlay architecture).

Secara berkala, setiap hari pada pukul 09:00:00 - 09:02:00 (saat settlement transaksi perbankan dibuka), terjadi keluhan timeout transaksi pembayaran sebesar 8.5% dari total traffic.
Berikut anomali sistem yang berhasil dikumpulkan oleh tim L1/L2:
1. Pengecekan bandwidth utilitas pada dashboard SNMP menunjukkan rata-rata trafik switch Leaf hanya mencapai 380 Mbps dari kapasitas port 10 Gbps (utilisasi < 4%).
2. Monitoring Blackbox konvensional (interval ping 15 detik) tidak menandai adanya node yang down atau RTT spike.
3. Server LB-Node-03 dan LB-Node-07 mengalami lonjakan CPU `softirq` hingga 100%, sementara 6 node LB lainnya memiliki CPU utilitas < 10%.
4. Sesi koneksi database transaksi backend yang melewati LB-Node-03 sering mengalami TCP Reset (`RST`).

**Tugas Anda:**
1. Desain investigasi arsitektur komprehensif: Jelaskan hipotesis struktural mengapa fenomena *hash polarization* pada algoritma ECMP switch dapat memicu kondisi kelebihan beban (*overloading*) hanya pada 2 node tersebut sementara 6 node lainnya *idle*.
2. Rancang strategi pengumpulan telemetri modern untuk membuktikan bahwa terjadi *buffer drop microburst* pada hardware switch ASIC (gNMI vs SNMP) dan buktikan dengan rancangan skrip ekstraksi data yang sesuai.
3. Susun cetak biru (*blueprint*) solusi arsitektur lengkap mencakup:
   * Skema diversifikasi hashing ECMP switch (*symmetric hashing / 5-tuple perturbation*).
   * Konfigurasi mitigasi *active health-checking* dinamis pada daemon routing server LB (BIRD/ExaBGP) untuk secara otomatis menarik (*withdraw*) iklan prefix BGP jika beban CPU softirq melebihi 70%.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual)
1. Apa alasan utama protokol gNMI menggunakan serialisasi Protocol Buffers (Protobuf) dibandingkan format JSON atau XML pada transmisi streaming data switch?
   * A. Karena JSON tidak mendukung tipe data array.
   * B. Karena Protobuf mengompresi payload dalam representasi biner yang ringkas dan didukung oleh kompilasi skema строго (strictly typed) via HTTP/2 multiplexing.
   * C. Karena Protobuf hanya dapat dibaca oleh switch berbasis Cisco IOS-XR.
   * D. Karena JSON menimbulkan kebocoran memori pada kernel Linux.
2. Pada mekanisme High Availability Keepalived/VRRP, apa fungsi utama pengiriman paket *Gratuitous ARP* saat node Backup bertransisi menjadi Master?
   * A. Mengenkripsi tabel routing antar switch.
   * B. Memberitahukan router dan switch layer-2 di sekitarnya untuk memperbarui tabel MAC Address (CAM table) mereka dengan MAC address node Master yang baru.
   * C. Menghapus konfigurasi iptables pada master node yang lama.
   * D. Mereset koneksi TCP aktif yang sedang berjalan.
3. Mengapa metode SNMP Polling tradisional sering kali gagal mendeteksi fenomena *microburst* pada port switch jaringan?
   * A. Karena SNMP tidak mendukung protokol IPv4.
   * B. Karena paket SNMP selalu di-drop secara default oleh switch datapath.
   * C. Karena interval sampling polling (biasanya 1 hingga 5 menit) meratakan (*smoothing/averaging*) lonjakan trafik milidetik yang sebenarnya menyebabkan buffer switch meluap.
   * D. Karena SNMP hanya dapat mengukur metrik temperatur CPU, bukan antarmuka fisik.
4. Hook eBPF manakah yang beroperasi pada lapisan paling awal dari network stack sistem operasi Linux (langsung pada memory buffer driver NIC)?
   * A. Kprobe
   * B. Socket Filter
   * C. TC (Traffic Control)
   * D. XDP (eXpress Data Path)
5. Apa dampak konfigurasi kernel Linux `net.ipv4.ip_nonlocal_bind = 1` terhadap penerapan High-Availability berbasis BGP Anycast atau Keepalived?
   * A. Mematikan seluruh firewall iptables saat failover.
   * B. Memungkinkan aplikasi socket daemon untuk listen/bind pada sebuah IP address virtual sebelum IP tersebut secara fisik terkonfigurasi pada interface lokal host.
   * C. Mengizinkan paket IP lokal keluar tanpa melewati default gateway.
   * D. Mengaktifkan enkripsi IPsec otomatis pada antarmuka fisik.

#### Bagian 2: Intermediate (Analisis Kasus)
6. Sebuah node Load Balancer menggunakan BGP Anycast untuk mengiklankan IP `/32`. Mengapa trafik berbasis protokol TCP stateful berisiko terputus (*broken connection*) ketika terjadi perubahan topologi atau konvergensi rute pada switch ECMP, dan bagaimana solusi modern mengatasinya?
7. Analisis baris log berikut dari sebuah daemon Keepalived:
   `VRRP_Instance(VI_1) Received lower prio advert 90 on veth0, our prio is 100, forcing new election`
   Apa yang sedang terjadi dalam cluster HA Anda dan apa implikasi trafiknya?
8. Dalam arsitektur Spine-Leaf, jelaskan bagaimana utilisasi metrik `queue-depth` via streaming telemetry dapat digunakan untuk memicu mekanisme *Proactive Congestion Avoidance* sebelum *packet tail-drop* terjadi.
9. Apa perbedaan esensial dari cara penanganan paket drop antara antrean drop di layer NIC (*Ring Buffer Exhaustion*) dengan antrean drop di layer socket Linux (*Socket Backlog Exhaustion*), dan perintah diagnostik apa yang membedakan keduanya?
10. Mengapa penerapan VRRP konvensional (Active/Passive) dianggap tidak efisien untuk arsitektur edge cloud modern skala multi-terabit dibandingkan dengan pendekatan BGP Anycast (Active/Active)?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Switch ToR Anda melaporkan bahwa bandwidth link uplink stabil pada angka 60%, namun server aplikasi di bawahnya mengalami *TCP connection timeouts* secara acak. Setelah dicek via eBPF, ditemukan metrik `tcp_drop` meningkat drastis pada fungsi `tcp_v4_rcv`. Di saat yang sama, metrik `/proc/net/snmp` memperlihatkan kolom `TCPBacklogDrop` bertambah ribuan paket per detik. Tentukan root cause dan rancang solusi perbaikan kernel parameter-nya!
12. **Skenario 2**: Dua node Keepalived diset dalam mode Active/Standby. Ketika jaringan backbone mengalami lonjakan trafik parah, kedua node tiba-tiba mengasumsikan state `MASTER` secara bersamaan (Split-Brain) selama 10-15 detik kemudian kembali normal. Investigasi menunjukkan CPU kedua server normal. Apa yang salah pada arsitektur transport heartbeat Keepalived tersebut dan bagaimana memperbaikinya?
13. **Skenario 3**: Sebuah cluster Kubernetes menggunakan BGP (Calico) untuk mengiklankan rute *LoadBalancer Service*. Klien internal di AWS mengalami *intermittent reset connection* saat melakukan request POST berukuran besar (> 1.5MB), namun request GET berukuran kecil (< 1KB) selalu sukses 100%. Tidak ada rule firewall yang memblokir. Identifikasi penyebab berbasis network layer dan bagaimana teknik observabilitas membuktikannya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. **B**: Protobuf mengompresi payload dalam representasi biner yang sangat ringkas dan efisien diurai CPU, dipadukan multiplexing HTTP/2 pada gRPC.
2. **B**: Memberitahukan perangkat L2 jaringan untuk memperbarui tabel CAM/ARP dengan MAC address node Master baru agar frame diarahkan ke node yang benar.
3. **C**: Interval polling SNMP (menit) meratakan data sehingga anomali lonjakan milidetik (*microburst*) tersembunyi dalam nilai rata-rata (*averaging*).
4. **D**: XDP (eXpress Data Path) dieksekusi di level driver kartu jaringan sebelum paket dialokasikan ke struktur kernel sk_buff.
5. **B**: Mengizinkan daemon (HAProxy/Envoy) untuk bind ke IP alamat yang belum aktif di level antarmuka lokal, krusial untuk failover instan.

#### Bagian 2: Intermediate
6. **Analisis**: Perubahan ECMP hash mengalihkan paket dari TCP connection yang sedang aktif ke node fisik yang berbeda. Node baru tidak memiliki tabel *session state* (SYN context) dari TCP tersebut sehingga merespons dengan TCP `RST`. Solusi: Menggunakan algoritma *Consistent Hashing with Maglev/Katran* atau sinkronisasi session table via Conntrackd.
7. **Analisis**: Node Master saat ini mendeteksi paket iklan VRRP dari node lain dengan prioritas lebih rendah (90) dibandingkan dirinya (100). Node Master mempertahankan statusnya dan mengirim paket advert tandingan untuk menegaskan kepemimpinannya atas Virtual IP. Normal saat node backup baru restart/booting.
8. **Analisis**: Metrik `queue-depth` yang meningkat mengindikasikan buffer ASIC mulai terisi sebelum batas ambang drop tercapai. Telemetri ini memungkinkan controller switch untuk mengaktifkan flag ECN (Explicit Congestion Notification) pada header IP atau mengirim instruksi ke ingress router untuk memodifikasi BGP metric (*cost/prepend*).
9. **Analisis**:
   * *Ring Buffer Exhaustion*: Terjadi di layer fisik/driver saat kartu jaringan tidak mampu memindahkan paket ke RAM kernel (Cek: `ethtool -S <eth> | grep rx_dropped` atau `rx_fifo_errors`).
   * *Socket Backlog Exhaustion*: Terjadi saat kernel sudah menerima paket namun thread aplikasi user-space lambat memproses paket dari socket receive queue (Cek: `ss -ntlp` kolom *Recv-Q* dan *Send-Q* atau `netstat -s | grep "buffer errors"`).
10. **Analisis**: VRRP konvensional bersifat *Active/Passive*, artinya kapasitas perangkat pasif (misal: bandwidth link 100G) terbuang percuma tanpa utilisasi komputasi. BGP Anycast bersifat *Active/Active*, seluruh perangkat memproses beban secara paralel (skala horizontal) sehingga efisiensi resource dan biaya mencapai 100%.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Solusi**: Root cause adalah *TCP socket listen backlog exhaustion*. Aplikasi web/service lokal lambat memanggil system call `accept()` sehingga antrean backlog penuh dan kernel me-reject paket TCP yang masuk.
    * Solusi: Tingkatkan parameter kernel via `/etc/sysctl.conf`:
      `net.core.somaxconn = 65535` dan `net.ipv4.tcp_max_syn_backlog = 65535`.
    * Pastikan aplikasi mengonfigurasi opsi `backlog` pada pemanggilan `listen()` (misal: di NGINX `listen 443 backlog=65535`).
12. **Analisis Solusi**: Paket VRRP menggunakan transport IP Multicast (`224.0.0.18`) atau unicast via interface produksi yang sama dengan jalur data utama. Saat terjadi kongesti trafik parah, frame VRRP ikut ter-drop dalam antrean buffer switch (*queue starvation*), sehingga Backup node mengira Master telah mati.
    * Perbaikan:
      1. Konfigurasikan link fisik khusus (*dedicated out-of-band heartbeat crossover cable*) untuk jalur VRRP.
      2. Set QoS priority (CoS/DSCP CS6) pada paket VRRP.
      3. Atur konfigurasi keepalived menggunakan unicast eksplisit dengan peer langsung.
13. **Analisis Solusi**: Gejala klasik **Path MTU Discovery (PMTUD) Black Hole**. Paket kecil (SYN/ACK, GET request) memiliki ukuran di bawah MTU terendah jalur (1500 byte) sehingga lolos. Paket data besar (POST) membutuhkan fragmentasi atau memiliki ukuran pas 1500 byte, namun di suatu hop perantara terdapat enkapsulasi tambahan (seperti tunnel VXLAN/Geneve sebesar 50 byte) yang membuat ukuran total 1550 byte. Jika router di tengah jalan menjatuhkan paket tersebut dan pesan ICMP *Fragmentation Needed (Type 3, Code 4)* terblokir firewall, koneksi akan menggantung (*hang/timeout*).
    * Pembuktian Observabilitas: Jalankan probe `tcpdump 'icmp[0] == 3 and icmp[1] == 4'` untuk melihat drop ICMP, atau periksa metrik kernel `IP: FragFails` dan `TCPRetransFail`.
    * Perbaikan: Terapkan *MSS Clamping* pada router/iptables edge:
      `iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu`.

---

### 16. Summary

1. **Transformasi Paradigma Monitoring**: Era jaringan terdistribusi modern menuntut perpindahan menyeluruh dari *polling reaktif* (SNMP) menuju *streaming telemetri real-time berbasis pendorong* (gNMI/OpenConfig via gRPC). Integrasi ini memberikan visibilitas sub-detik yang sangat esensial untuk menangkap anomali transien seperti *microbursts*.
2. **Kernel-Level Observability via eBPF**: Menjembatani jurang pemisah (*visibility gap*) antara status link antarmuka fisik dengan kinerja aplikasi. Melalui eBPF, teknisi dapat mendiagnosis *TCP drops*, *retransmissions*, dan *latency attribution* langsung dari dalam struktur data socket kernel tanpa overhead context-switching yang masif.
3. **High Availability Berlapis (Layered HA)**: Ketahanan operasional kelas enterprise dicapai bukan melalui satu solusi tunggal, melainkan kombinasi harmonis antara isolasi kegagalan lokal (menggunakan VRRP/Keepalived pada subnet tertentu) dan arsitektur *scale-out* elastis tanpa status (menggunakan BGP Anycast dan ECMP hashing pada tier distribusi).
4. **Closed-Loop Reliability**: Keunggulan observabilitas sejati berada pada kemampuan sistem untuk melakukan *self-healing*. Alert telemetry berkualitas tinggi harus menjadi pemicu otomatis bagi orkestrasi perutean jaringan (seperti *route draining* dan *BGP prefix manipulation*), memitigasi insiden secara otonom sebelum berdampak negatif terhadap SLA pengguna akhir.