# Bab 02 Module 01: Network Security & Traffic Analysis

---

### 1. Identitas Modul

| Parameter | Nilai |
| :--- | :--- |
| **Track** | Cyber Security |
| **Kategori** | 07-Quality-and-Security |
| **Bab** | 02 - Network Security & Traffic Analysis |
| **Modul** | 01 - Core Infrastructure Defense & Deep Telemetry Analysis |
| **Tingkat Kesulitan** | Lanjutan (Advanced) |
| **Prasyarat** | Pemahaman mendalam tentang Model OSI/TCP-IP, Subnetting, TCP 3-Way Handshake & Teardown, Dasar Kriptografi Kunci Publik (PKI/TLS), serta Kemahiran Linux CLI |
| **Estimasi Waktu** | 12 - 16 Jam Pembelajaran Mandiri / Praktikum Terbimbing |

---

### 2. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

*   **LO-01:** Menganalisis dan merancang arsitektur pertahanan perimeter berlapis dengan mengintegrasikan Next-Generation Firewall (NGFW), IDS/IPS, dan proksi dekripsi TLS.
*   **LO-02:** Menulis, menguji, dan mengoptimalkan signature deteksi intrusi berbasis Suricata/Snort menggunakan ekspresi reguler dan engine Hyperscan untuk mitigasi ancaman Layer 7.
*   **LO-03:** Mengoperasikan Zeek Network Security Monitor untuk mengekstraksi metadata koneksi, membedah protokol aplikasi (DNS, HTTP, SSL/TLS), dan membangun skrip otomasi deteksi anomali real-time.
*   **LO-04:** Menerapkan teknik Deep Packet Inspection (DPI) untuk mengenali protokol terselubung (*protocol obfuscation*), tunneling terlarang (misal: DNS/ICMP exfiltration), dan anomali alur TCP.
*   **LO-05:** Mengimplementasikan prinsip Zero Trust Network Architecture (ZTNA) sesuai standar NIST SP 800-207 melalui pendekatan micro-segmentation berbasis eBPF dan Policy Enforcement Points (PEP).
*   **LO-06:** Mengisolasi dan memitigasi teknik penghindaran inspeksi jaringan (*evasion techniques*), seperti fragmentasi TCP/IP, out-of-order delivery, dan enkripsi payload.
*   **LO-07:** Merekonstruksi artefak serangan siber menggunakan PCAP forensik untuk mengidentifikasi Command and Control (C2) beaconing, eksfiltrasi data, dan pergerakan lateral (*lateral movement*).
*   **LO-08:** Mengevaluasi kompromi performa (*trade-offs*) antara throughput jaringan, latensi transmisi, pemrosesan memori, dan kedalaman inspeksi keamanan pada throughput multi-gigabit.

---

### 3. Concept Map & Architecture Diagram

Diagram berikut mengilustrasikan alur inspeksi paket jaringan tingkat enterprise, mulai dari ingress perimeter, pemrosesan inline dan out-of-band (TAP/SPAN), hingga penegakan micro-segmentation di tingkat beban kerja (workload):

```text
                                [ WAN / INTERNET ]
                                        |
                             +----------v----------+
                             | Edge Router / Anti  |
                             |   DDoS Mitigation   |
                             +----------+----------+
                                        |
                             +----------v----------+
                             |   SSL/TLS Break &   | <--- TLS Decryption Proxy
                             | Inspect Appliance   |      (Forward/Reverse)
                             +----------+----------+
                                        | Decrypted Flow
                             +----------v----------+
                             | Next-Gen Firewall   | <--- Layer 7 App-ID, User-ID,
                             |      (NGFW)         |      Stateful Inspection
                             +----+-----------+----+
           Inline IPS Drop        |           |
           [Inline Engine] <------+           +-----> [Mirror/SPAN Port]
                                                      | (Raw Decrypted Packets)
                                            +---------+---------+
                                            |                   |
                                   +--------v--------+ +--------v--------+
                                   | Suricata (IDS)  | |  Zeek Monitor   |
                                   | (Hyperscan Sig) | | (Event Engines) |
                                   +--------+--------+ +--------+--------+
                                            |                   |
                                   +--------v-------------------v--------+
                                   |    SIEM / XDR / Data Lake           |
                                   +-------------------------------------+
                                        |
                          [ INTERNAL TRUST BOUNDARY ]
                                        |
                             +----------v----------+
                             |  ZTNA Core / Policy | <--- Identity Provider (IdP)
                             |  Enforcement Point  |      Device Posture Check
                             +----+-----------+----+
                                  |           |
        Micro-segmentation Policy |           | Software-Defined Perimeter
                                  |           |
    +-----------------------------v-+       +-v-----------------------------+
    | Workload Segment A (eBPF)     |       | Workload Segment B (eBPF)     |
    |  +---------+     +---------+  |       |  +---------+     +---------+  |
    |  | Pod/VM1 |<--->| Pod/VM2 |  |       |  | App Svc |<--->| DB Clust|  |
    |  +---------+     +---------+  |       |  +---------+     +---------+  |
    +-------------------------------+       +-------------------------------+
```

---

### 4. Mengapa Ini Penting

Pada arsitektur jaringan lama, perimeter diasumsikan sebagai batas absolut: semua entitas di luar batas bersifat berbahaya, sedangkan entitas di dalam jaringan bersifat tepercaya (*castle-and-moat architecture*). Paradigma ini telah runtuh seiring meluasnya adopsi cloud, pola kerja remote, dan vektor serangan rantai pasok (*supply chain*).

1.  **Kegagalan Total Perimeter Statis:** Aktor ancaman masa kini jarang menembus perimeter secara langsung menggunakan kekerasan (*brute-force*). Mereka mengeksploitasi identitas yang terkompromi, kerentanan VPN, atau file payload berbahaya via phishing. Sekali penyerang melewati perimeter, ketiadaan segmentasi internal memungkinkan mereka mengeksekusi pergerakan lateral tanpa hambatan (*unrestricted lateral movement*).
2.  **Kebutuhan Visibilitas dan Telemetri:** Tanpa inspeksi mendalam (Deep Packet Inspection) dan analisis metadata (Zeek), tim keamanan beroperasi secara buta terhadap komunikasi Command and Control (C2) yang disamarkan dalam protokol standar seperti HTTPS, DNS-over-HTTPS (DoH), atau WebSocket.
3.  **Dampak Regulasi dan Kepatuhan Finansial:** Standar global seperti PCI-DSS 4.0 (Requirement 1 & 10), HIPAA Security Rule, dan ISO/IEC 27001 mewajibkan isolasi data sensitif, logging aliran data jaringan secara terperinci, dan pembatasan transmisi data pemegang kartu melalui micro-segmentation yang dapat dibuktikan secara matematis.

---

### 5. Apa Itu Konsep

Berikut definisi formal dan mendalam dari elemen-elemen fundamental pertahanan jaringan modern:

*   **Perimeter Defense:** Kumpulan mekanisme kontrol akses terkoordinasi (firewall, proksi, sistem anti-DDoS) yang diletakkan pada batas perimeter antara domain tepercaya (*trusted network*) dan domain yang tidak tepercaya (*untrusted network*).
*   **Next-Generation Firewall (NGFW):** Perangkat inspeksi paket stateful yang melampaui filtering berbasis IP dan Port (Layer 3/4). NGFW membedah payload hingga Layer 7 untuk memetakan aplikasi secara pasti (*Application Identification / App-ID*), mengintegrasikan otentikasi identitas pengguna (*User-ID*), dan menyaring konten secara aktif.
*   **Intrusion Detection/Prevention System (IDS/IPS):** 
    *   *IDS:* Sistem pasif pemantau lalu lintas jaringan (via SPAN/TAP) yang membandingkan traffic dengan signature serangan atau baseline perilaku, kemudian membangkitkan alert peringatan.
    *   *IPS:* Sistem inline yang berada langsung pada jalur transmisi paket data, memiliki wewenang untuk menjatuhkan (*drop*), memotong sesi (*TCP Reset*), atau merekayasa paket yang terindikasi eksploitasi secara otomatis.
*   **Deep Packet Inspection (DPI):** Pemrosesan komputasi tingkat lanjut yang memvalidasi header dan data payload paket di atas Layer 4. DPI mencakup de-enkapsulasi protokol, rekonstruksi stream byte, dan evaluasi konten terhadap pola biner yang mencurigakan.
*   **Zeek (sebelumnya Bro):** Kerangka kerja analisis jaringan berbasis open-source yang beroperasi secara pasif. Berbeda dengan signature engine tradisional, Zeek mengurai (*parse*) lalu lintas jaringan menjadi event terstruktur dan menghasilkan log semantik beranotasi tinggi (misalnya: detail handshake TLS, riwayat query DNS, pertukaran file MIME).
*   **Micro-segmentation:** Metode isolasi keamanan yang memecah pusat data dan lingkungan multi-cloud menjadi zona-zona granular yang sangat terisolasi hingga ke level beban kerja individual (VM, kontainer, proses), membatasi komunikasi horizontal (*east-west traffic*).
*   **Zero Trust Network Architecture (ZTNA):** Model arsitektur keamanan berdasarkan filosofi "never trust, always verify". Akses ke aplikasi atau resource jaringan tidak pernah diberikan berdasarkan lokasi fisik atau alamat IP; akses diberikan secara kontekstual, terenkripsi, berbasis identitas, dan terus-menerus diverifikasi (*continuous evaluation*).

---

### 6. Bagaimana Cara Kerjanya

#### 6.1 State Engine & Deep Packet Inspection (DPI)
Pada packet-filtering tradisional, setiap paket dievaluasi secara independen (*stateless*). Pada firewall modern dan DPI:
1.  **Flow Reassembly:** Paket yang terfragmentasi diasosiasikan menggunakan tuple: `Src IP, Dst IP, Src Port, Dst Port, IP Protocol`.
2.  **TCP Normalization:** Mengeliminasi celah manipulasi flag TCP (seperti serangan out-of-order fragment). Sistem mempertahankan State Table (misalnya `conntrack` pada Linux atau proprietary memory-hash tables pada NGFW) untuk memvalidasi nomor sequence dan acknowledgment (`SYN -> SYN-ACK -> ACK -> ESTABLISHED`).
3.  **Pattern Matching Acceleration:** Pencocokan signature payload (misalnya pada Suricata) menggunakan pustaka algoritma pencocokan multi-pola seperti *Hyperscan* (berbasis Finite Automata: NFA/DFA). Ini memungkinkan evaluasi ribuan pola regular expression secara bersamaan dalam satu lintasan memori (*single-pass streaming processing*).

#### 6.2 Mekanisme Ekstraksi Telemetri Zeek
Zeek tidak mengandalkan pencocokan signature statis untuk alert; ia bekerja melalui arsitektur modular berlapis:
*   **Event Engine (Core):** Menerima stream raw packet, melakukan parsing protokol (misalnya memisahkan ASN.1, decoding Base64, parsing TLS Client/Server Hello), lalu menghasilkan *Events* (contoh: `dns_request`, `http_reply`, `ssl_established`).
*   **Policy Script Interpreter:** Menjalankan skrip berbasis event yang ditulis dalam bahasa Zeek Turing-complete. Jika sebuah event dibangkitkan, fungsi handler yang relevan dieksekusi. Skrip mengelola state stateful untuk mendeteksi anomali (misalnya menghitung frekuensi koneksi unik per unit waktu untuk mendeteksi scanning atau eksfiltrasi).

#### 6.3 Paradigma Micro-segmentation & Zero Trust Architecture (ZTNA)
*   **NIST SP 800-207 Architecture:** Terdiri dari *Policy Engine (PE)*, *Policy Administrator (PA)*—bersama-sama disebut *Policy Decision Point (PDP)*—dan *Policy Enforcement Point (PEP)*. PEP berada di depan resource target. Klien meminta akses; PDP memverifikasi identitas, postur keamanan perangkat (*device posture*), dan konteks (waktu, lokasi); jika valid, PEP membuka saluran mTLS (*mutual TLS*) terisolasi langsung ke aplikasi spesifik, bukan ke seluruh subnet.
*   **Penegakan di Tingkat Kernel (eBPF):** Pada lingkungan cloud-native, micro-segmentation diterapkan menggunakan Extended Berkeley Packet Filter (eBPF). Daripada melintasi stack jaringan Linux standar (`netfilter/iptables`) yang memicu latensi tinggi melalui traversing linear rule list, program eBPF dilekatkan langsung pada socket interface (`sockops`) atau tingkat antarmuka pengemudi (`XDP - eXpress Data Path`), memungkinkan packet drop dalam skala sub-mikrodetik.

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

| Kriteria | Stateful L4 Firewall | Next-Generation Firewall (NGFW) | Signature IDS/IPS (Suricata) | Network Analysis Framework (Zeek) | Zero Trust Network Arch (ZTNA) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lapisan OSI Utama** | Layer 3 - 4 | Layer 3 - 7 | Layer 3 - 7 | Layer 3 - 7 | Layer 7 (Identity-centric) |
| **Metode Penegakan** | Inline (Blocking) | Inline (Blocking, Shaping) | Inline (IPS) atau Passive SPAN (IDS) | Mayoritas Passive Monitoring | Inline (Broker / Reverse Proxy) |
| **Dasar Pengambilan Keputusan** | IP 5-tuple, Flag TCP/UDP | App-ID, User-ID, Content, Context | Signatures, Rule Matches, Heuristics | Anomali Stateful, Korelasi Metadata | Identitas Terautentikasi, Postur Perangkat |
| **Kinerja & Latensi** | Ekstrem Tinggi (Latensi Sangat Rendah) | Menengah-Tinggi (Kenaikan beban CPU akibat DPI) | Menengah (Tergantung jumlah rule) | Pasif (Tidak menambah latensi jaringan) | Bergantung lokasi broker/PEP |
| **Inspeksi Enkripsi (TLS)** | Buta Payload | Memerlukan SSL/TLS Ingress/Egress Proxy | Memerlukan Decrypted Feed / SPAN | Menganalisis metadata TLS handshake | Native mTLS End-to-End |
| **Visibilitas East-West** | Rendah (Hanya antar VLAN/Subnet) | Menengah (Tergantung desain routing) | Menengah (Tergantung lokasi sensor) | Sangat Tinggi (Jika sensor disebar tepat) | Ekstrem Tinggi (Setiap workload terisolasi) |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

| Taktik MITRE ATT&CK | Teknik ID | Vektor Serangan | Mekanisme Bypass Perimeter Tradisional | Strategi Deteksi & Mitigasi Modern |
| :--- | :--- | :--- | :--- | :--- |
| **Command and Control** | T1071.001 | Web Protocols (HTTPS/WebSocket Beaconing) | Menyembunyikan payload di dalam HTTPS terenkripsi pada port standar 443. | DPI + Forward Proxy TLS Decryption; Zeek JA3/JA4 TLS Client Fingerprint tracking. |
| **Command and Control** | T1071.004 | DNS Exfiltration & Tunneling | Menggunakan server DNS otoritatif penyerang; request melewati internal DNS resolver tanpa terblokir. | Inspeksi anomali panjang string subdomain (DPI), rasio entropi Shannon pada query DNS, dan Suricata DNS rules. |
| **Lateral Movement** | T1021.002 | SMB/Windows Admin Shares | Menyerang host internal melalui subnet flat yang tidak memiliki filtering internal (East-West). | Micro-segmentation berbasis identitas; memblokir TCP 445 antar workstation; IDS deteksi DCE/RPC binding abnormal. |
| **Defense Evasion** | T1572 | Protocol Tunneling (SSH over HTTP / DNS) | Membungkus protokol terlarang di dalam protokol yang diizinkan firewall (misal: SSH di port 80/443). | Layer 7 App-ID validation. NGFW/DPI mengabaikan nomor port dan memeriksa kesesuaian magic byte protokol. |
| **Defense Evasion** | T1036 | Masquerading (Port/Service Mismatch) | Menjalankan trojan/shellcode listener pada port terkenal (misal port 53 UDP) padahal bukan DNS. | Protokol enforcement engine; menolak paket yang tidak mematuhi RFC struktural dari port terkait. |
| **Exfiltration** | T1048 | Exfiltration Over Alternative Protocol (ICMP) | Menyisipkan payload data rahasia pada field `data` paket ICMP Echo Request. | DPI memeriksa ukuran muatan ICMP; alerting bila payload byte melebihi padding standar sistem operasi (misal > 64 bytes). |

---

### 9. Code Example Sederhana

#### 9.1 Deteksi Upaya DNS Exfiltration Menggunakan Rule Suricata
Rule berikut mendeteksi query DNS ke subdomain yang mencurigakan panjangnya (> 50 karakter), yang sering mengindikasikan tunneling atau eksfiltrasi data terenkode:

```suricata
# File: /etc/suricata/rules/detect_dns_exfil.rules
# Deteksi DNS Query Subdomain Entropi/Panjang Abnormal
alert dns any any -> any 53 ( \
    msg:"SEC-NET: Terdeteksi Anomali Query DNS Panjang (Potensi Tunneling/Eksfiltrasi)"; \
    dns.query; \
    pcre:"/^[a-zA-Z0-9_-]{50,}\.[a-zA-Z0-9_.-]+\.[a-zA-Z]{2,}$/"; \
    threshold: type both, track by_src, count 5, seconds 60; \
    classtype:bad-unknown; \
    sid:1000001; \
    rev:1; \
    metadata:mitre_attack_id T1071_004, attack_target Internal_Network; \
)
```

#### 9.2 Skrip Zeek Sederhana untuk Monitoring Port Mismatch
Skrip Zeek berikut memicu alert peringatan ketika koneksi keluar non-HTTP menggunakan port 80:

```zeek
# File: detect_port_mismatch.zeek
event connection_state_remove(c: connection) {
    # Periksa apakah koneksi menggunakan Port 80
    if ( c$id$resp_p == 80/tcp ) {
        # Jika koneksi ditutup tanpa pernah terdeteksi sebagai protokol HTTP oleh Zeek Analyzer
        if ( ! c?$http && c$orig$num_bytes_ip > 0 ) {
            print fmt("[PERINGATAN] Anomali Port 80 Terdeteksi! Sumber: %s -> Tujuan: %s. Total Bytes: %d. Protokol bukan HTTP.", 
                      c$id$orig_h, c$id$resp_h, c$orig$num_bytes_ip);
        }
    }
}
```

---

### 10. Code Example Lanjutan

#### 10.1 Skrip Zeek Lanjutan: Deteksi C2 Beaconing Melalui Analisis Jitter Koneksi TLS
Skrip produksi ini memantau koneksi periodik (beaconing) terenkripsi TLS dengan menghitung deviasi interval waktu koneksi (*jitter*) antara host internal dan server eksternal:

```zeek
# File: /opt/zeek/share/zeek/site/c2_beacon_detector.zeek
@load base/frameworks/notice
@load base/protocols/ssl

module C2Detection;

export {
    redef enum Notice::Type += {
        C2_Beaconing_Suspected
    };

    # Threshold: Deteksi jika terdapat minimal 10 koneksi berulang dengan variasi interval < 2.0 detik
    const MIN_CONNECTIONS: count = 10;
    const MAX_INTERVAL_JITTER: interval = 2.0sec;
}

type BeaconTracker: record {
    last_timestamp: time;
    intervals: vector of interval;
    connection_count: count;
};

global beacon_table: table[addr, addr] of BeaconTracker;

event ssl_established(c: connection) {
    local src = c$id$orig_h;
    local dst = c$id$resp_h;
    local current_time = network_time();

    # Abaikan alamat IP non-lokal sebagai sumber
    if ( ! Site::is_local_addr(src) )
        return;

    local tracker_key = [src, dst];

    if ( tracker_key !in beacon_table ) {
        beacon_table[tracker_key] = [
            $last_timestamp = current_time,
            $intervals = vector(),
            $connection_count = 1
        ];
        return;
    }

    local tracker = beacon_table[tracker_key];
    local delta = current_time - tracker$last_timestamp;
    tracker$last_timestamp = current_time;
    tracker$intervals += delta;
    tracker$connection_count += 1;

    if ( tracker$connection_count >= MIN_CONNECTIONS ) {
        local sum = 0.0;
        local count_intervals = |tracker$intervals|;

        for ( i in tracker$intervals ) {
            sum += interval_to_double(tracker$intervals[i]);
        }
        local avg = sum / count_intervals;

        # Hitung Mean Absolute Deviation (MAD) untuk mendeteksi low jitter
        local variance_sum = 0.0;
        for ( i in tracker$intervals ) {
            local diff = interval_to_double(tracker$intervals[i]) - avg;
            if ( diff < 0.0 ) diff = -diff;
            variance_sum += diff;
        }
        local mad = double_to_interval(variance_sum / count_intervals);

        if ( mad < MAX_INTERVAL_JITTER ) {
            NOTICE([
                $note=C2_Beaconing_Suspected,
                $msg=fmt("Pola C2 Beaconing TLS terdeteksi dari %s ke %s. Interval Rata-rata: %s, Jitter (MAD): %s", 
                         src, dst, double_to_interval(avg), mad),
                $conn=c,
                $identifier=cat(src, dst)
            ]);
            # Reset tracking untuk siklus observasi berikutnya
            delete beacon_table[tracker_key];
        }
    }
}
```

#### 10.2 Deklarasi Cilium Network Policy (eBPF Micro-segmentation)
Kebijakan keamanan berbasis Cilium (eBPF) yang mengamankan komunikasi antar-layanan di Kubernetes. Layanan `payment-processor` hanya boleh diakses oleh `frontend` melalui port aman 8443, dengan pemblokiran absolut terhadap semua koneksi keluar (*egress*) ke internet terbuka, kecuali ke server database terautentikasi:

```yaml
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "harden-payment-processor"
  namespace: "production-finance"
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: "payment-processor"
  
  # Penegakan Ingress: Hanya izinkan Frontend
  ingress:
  - fromEndpoints:
    - matchLabels:
        app.kubernetes.io/name: "frontend"
    toPorts:
    - ports:
      - port: "8443"
        protocol: TCP
      rules:
        http:
          - method: "POST"
            path: "/api/v1/charge"

  # Penegakan Egress: Batasi ketat East-West dan tolak semua koneksi WAN
  egress:
  # Izinkan DNS resolution lokal via kube-dns internal
  - toEndpoints:
    - matchLabels:
        k8s-app: "kube-dns"
    toPorts:
    - ports:
      - port: "53"
        protocol: ANY
      rules:
        dns:
          - matchPattern: "*"
  # Izinkan koneksi ke database internal yang didefinisikan secara spesifik
  - toEndpoints:
    - matchLabels:
        app.kubernetes.io/name: "vault-core"
    toPorts:
    - ports:
      - port: "8200"
        protocol: TCP
```

---

### 11. Diagram Alur Serangan & Mitigasi

Berikut siklus hidup intrusi (*Intrusion Lifecycle*) saat penyerang berusaha melakukan infiltrasi, bypass kontrol port, dan bagaimana pipeline keamanan berlapis menggagalkan serangan tersebut:

```text
PENYERANG (WAN)               PERIMETER / FIREWALL                 IDS/IPS & ZEEK             INTERNAL TARGET
      |                                |                                  |                          |
      | 1. SYN ke Port 443 (HTTPS)      |                                  |                          |
      |------------------------------->|                                  |                          |
      |                                | [State Valid: SYN-ACK diteruskan]|                          |
      | 2. TLS Handshake Inisiasi      |                                  |                          |
      |------------------------------->|                                  |                          |
      |                                | 3. Decrypt TLS Session (Proxy)   |                          |
      |                                |----+                             |                          |
      |                                |    | Parsing Decrypted Payload   |                          |
      |                                |<---+                             |                          |
      |                                | 4. Mirroring decrypted stream    |                          |
      |                                |--------------------------------->|                          |
      | 5. Mengirim Obfuscated C2      |                                  |                          |
      |    Shell Payload over HTTP/2   |                                  |                          |
      |------------------------------->|                                  |                          |
      |                                | 6. Inspeksi L7 DPI Pipeline      |                          |
      |                                |                                  |                          |
      |                                |                                  | [Suricata Hyperscan Rule]|
      |                                |                                  | Terdeteksi Match C2 Sig! |
      |                                |                                  | [Zeek: Ekstrak JA3/TLS]  |
      |                                | 7. Alert Drop Event Dikirimkan   |                          |
      |                                |<---------------------------------|                          |
      |                                |                                  |                          |
      |                                | 8. Paket Didrop Inline           |                          |
      |                                |    Kirim TCP RST ke Aktor        |                          |
      | 9. [Koneksi Diputus / RST]     |                                  |                          |
      |<-------------------------------|                                  |                          |
      |                                |                                  |                          |
      |                                                                   X [Tidak Ada Payload yang] |
      |                                                                     [Mencapai Server Target] |
```

---

### 12. Trade-offs & Security vs Usability / Performance

#### 12.1 Throughput vs Kedalaman Inspeksi DPI
Penerapan DPI dan regex parsing (Hyperscan) memerlukan komputasi intensif. Setiap paket yang masuk harus ditampung di ring buffer kernel, direkonstruksi dalam memory stream, lalu dianalisis.
*   *Dampak Kinerja:* Pengaktifan inspeksi L7 penuh pada perangkat hardware dapat memangkas throughput dari line-rate (misalnya 40 Gbps pada switching L3/L4 murni) turun drastis menjadi 5–8 Gbps pada evaluasi paket Layer 7 secara aktif.
*   *Mitigasi:* Gunakan hardware offloading seperti Single Root I/O Virtualization (SR-IOV), kartu SmartNIC, atau DPDK (Data Plane Development Kit) untuk memproses paket bypass kernel.

#### 12.2 SSL/TLS Decryption vs Privasi & Kompleksitas
*   *Kompromi Privasi:* Melakukan dekripsi SSL/TLS (Break and Inspect) memungkinkan organisasi memeriksa eksfiltrasi data, tetapi berisiko melanggar undang-undang privasi (seperti GDPR / UU PDP) jika data pribadi karyawan (misalnya traffic perbankan atau medis) terinspeksi.
*   *Kompromi Teknis:* Inspeksi TLS 1.3 mematahkan session-resumption dan membutuhkan instalasi sertifikat root CA kustom di setiap perangkat endpoint. Ini sering kali menyebabkan kerusakan fungsional pada aplikasi modern yang menggunakan HTTP/2 multiplexing atau TLS Certificate Pinning (misal: mobile client API).

#### 12.3 IPS Blocking vs Risiko False-Positive
*   *Inline Drop Mode:* Menjatuhkan paket secara otomatis melindungi aset dari zero-day payload. Namun, jika rule memiliki false positive sebesar 0.01% saja pada jaringan enterprise dengan 10 juta koneksi per hari, ribuan transaksi bisnis yang sah akan terblokir (*denial of service mandiri*).
*   *Rekomendasi:* Jalankan rule signature baru dalam mode IDS non-blocking (*alert-only*) selama minimal 14–30 hari untuk verifikasi stabilitas (*burn-in period*) sebelum mengubah aksinya menjadi `drop/reject`.

---

### 13. Edge Cases & Complex Failure Modes

#### 13.1 TCP Segment Reassembly & Evasion Attacks
Penyerang berpengalaman dapat memanipulasi pengiriman paket di tingkat transport untuk mengelabui engine IDS/IPS:
*   *Overlapping Fragments:* Penyerang mengirimkan dua paket IP fragment: fragmen pertama membawa muatan valid yang menimpa fragmen kedua saat reassembly di host tujuan, namun IPS menyusunnya secara berbeda. Perbedaan ini terjadi karena implementasi TCP/IP stack bervariasi (misal: Windows menganut *First* fragment policy, sedangkan Linux modern menganut *Last* fragment policy).
*   *Solusi Hardware:* IPS harus dikonfigurasi dengan *Target-Based TCP Normalization*, yakni sistem inspeksi harus mengetahui sistem operasi dari server target dan menyesuaikan algoritma reassembly sesuai OS target.

#### 13.2 Asymmetric Routing
Pada infrastruktur modern dengan redundansi multi-homed ISP atau load balancing:
*   Paket *outbound* (SYN, HTTP GET) melewati Router A dan NGFW A, sedangkan paket *inbound* (SYN-ACK, HTTP Response) dialihkan melalui Router B dan NGFW B.
*   *Kegagalan:* NGFW B akan menganggap paket inbound sebagai transaksi ilegal karena State Table-nya tidak pernah mencatat paket inisiasi SYN. Akibatnya, paket di-drop sepihak (*broken state*).
*   *Mitigasi:* Konfigurasi state synchronization link (HA sync) antar-firewall cluster dengan interkoneksi serat optik berkecepatan tinggi atau terapkan policy-based routing berbasis flow-hash untuk menjamin simetri transmisi paket.

#### 13.3 Out-of-Memory Saturation via State Table Flooding
Aktor ancaman melancarkan serangan non-volumetrik terkoordinasi berupa pengiriman puluhan ribu paket TCP SYN lambat dengan parameter payload acak dari ratusan ribu IP spoofed.
*   *Failure Mode:* State table pada NGFW atau modul `nf_conntrack` Linux mengalami kejenuhan (*exhaustion*). Setelah tabel kapasitas state penuh (misal: `sysctl net.netfilter.nf_conntrack_max` terlampaui), firewall akan secara otomatis menjatuhkan seluruh koneksi baru, melumpuhkan seluruh lalu lintas sah jaringan enterprise.

---

### 14. Anti-Patterns & Common Vulnerabilities

#### Anti-Pattern 1: Egress "Any-Any" Assumption
*   *Deskripsi:* Administrator mengamankan Ingress (lalu lintas masuk) dengan sangat ketat, tetapi membiarkan konfigurasi Egress (lalu lintas keluar) terbuka sepenuhnya (`allow any any`).
*   *Kerentanan:* Sekali host internal terkompromi (misal melalui link phishing atau macro file), payload trojan dapat dengan mudah membuka Reverse Shell ke server C2 publik penyerang di luar perimeter via port mana pun (misal port TCP 4444 atau port 80).

#### Anti-Pattern 2: Subnet-Level Flat Trust (Implicit East-West Trust)
*   *Deskripsi:* Mengelompokkan semua server aplikasi, database, dan workstation admin ke dalam satu blok IP subnet besar (misal `/16` atau `/24`) tanpa batasan akses antar-host.
*   *Kerentanan:* Jika workstation administrator terkena malware, penyerang dapat menjalankan pivoting lateral tanpa hambatan ke database menggunakan protokol SMB, SSH, atau RDP secara langsung tanpa pernah melewati firewall gateway.

#### Anti-Pattern 3: SPAN Port Buffer Overflow & Packet Dropping
*   *Deskripsi:* Mengarahkan traffic gabungan dari switch port berkapasitas 10 Gbps ke dedicated SPAN/Mirror port yang hanya berkapasitas 1 Gbps untuk dibaca oleh sensor IDS (Suricata/Zeek).
*   *Kerentanan:* Terjadi frame dropping masif di tingkat switchport ASIC. IDS kehilangan hingga 70% stream paket. Aktor penyerang dapat mengeksekusi serangan yang tidak akan pernah tertangkap oleh signature sensor karena paket auditnya tereliminasi sebelum terbaca (*blind spotting*).

---

### 15. Best Practices & Enterprise Remediation Guide

1.  **Arsitektur Egress Filtering Granular:** Terapkan pemblokiran total untuk semua port outbound. Izinkan koneksi keluar hanya ke subset port yang disetujui (misal TCP 80/443) melalui proxy forwarder terpusat yang memverifikasi reputasi Domain dan sertifikat TLS.
2.  **Transisi Menuju Model ZTNA Terpadu (NIST SP 800-207):**
    *   Hapuskan ketergantungan pada koneksi Full-Tunnel Network VPN warisan.
    *   Terapkan Software-Defined Perimeter (SDP) berbasis otentikasi identitas kontekstual sebelum mengizinkan konektivitas socket TCP/UDP.
3.  **Audit dan Pembersihan Rulebase Firewall Secara Berkala (CIS Benchmark):**
    *   Hapus rule yang tidak lagi memiliki hit-count selama 60 hari.
    *   Pastikan seluruh rule memiliki masa kedaluwarsa eksplisit (*time-bound exceptions*).
    *   Setiap rule wajib memiliki logging aktif (*Log every connection session end*).
4.  **Isolasi Lalu Lintas Administratif Jaringan (Out-of-Band Management):**
    *   Pisahkan jalur manajemen sistem (SSH, IPMI, iLO, ESXi Management Portal) dari jaringan operasional produksi menggunakan Virtual Routing and Forwarding (VRF) terpisah atau jaringan fisik yang sepenuhnya terputus (*air-gapped management network*).

---

### 16. Hands-on Lab Step-by-Step

Dalam lab praktikum ini, Anda akan membedah trace PCAP terinfeksi, memvalidasinya dengan Suricata, mengekstrak artefak lalu lintas dengan Zeek, dan memblokir IP penyerang secara otomatis di kernel Linux menggunakan iptables.

#### Langkah 1: Persiapan Environment dan Tooling
Pastikan Anda menggunakan mesin Linux (Ubuntu 22.04 LTS / Debian 12) dengan akses root:

```bash
# Update repository dan instal paket yang dibutuhkan
sudo apt-get update && sudo apt-get install -y suricata zeek tshark tcpdump
```

#### Langkah 2: Simulasi Capturing / Unduh File PCAP Malicious
Kita akan mensimulasikan capture aktivitas C2 beaconing sederhana ke file lokal:

```bash
# Buat direktori kerja
mkdir -p ~/netsec_lab && cd ~/netsec_lab

# Buat simulasi PCAP yang merefleksikan trafik DNS mencurigakan
python3 -c '
from scapy.all import *
pkt = IP(src="192.168.10.50", dst="8.8.8.8")/UDP(sport=53212, dport=53)/DNS(rd=1, qd=DNSQR(qname="a"*55 + ".attacker-c2.com"))
wrpcap("suspicious_dns.pcap", [pkt]*10)
'
```

#### Langkah 3: Eksekusi Deteksi Menggunakan Suricata
Gunakan rule yang telah kita buat pada Bab 9 untuk memindai PCAP tersebut:

```bash
# Buat file rule Suricata
cat << 'EOF' > local.rules
alert dns any any -> any 53 (msg:"LAB DETECT: C2 Long Subdomain Detected"; dns.query; pcre:"/^[a-zA-Z0-9_-]{50,}\.[a-zA-Z0-9_.-]+\.[a-zA-Z]{2,}$/"; sid:9000001; rev:1;)
EOF

# Jalankan Suricata terhadap file pcap
suricata -r suspicious_dns.pcap -S local.rules -l ./suricata_logs/

# Tinjau output peringatan
cat ./suricata_logs/fast.log
```
*Output yang Diharapkan:*
```text
[**] [1:9000001:1] LAB DETECT: C2 Long Subdomain Detected [**] [Classification: (null)] [Priority: 3] {UDP} 192.168.10.50:53212 -> 8.8.8.8:53
```

#### Langkah 4: Ekstraksi Metadata Forensik Menggunakan Zeek
Analisis file PCAP yang sama dengan Zeek untuk memproduksi log semantik:

```bash
# Jalankan Zeek dalam mode offline processing
zeek -r suspicious_dns.pcap

# Tinjau artefak log DNS terstruktur yang dihasilkan oleh Zeek
cat dns.log | zeek-cut ts uid id.orig_h id.resp_h proto query answers
```
*Output yang Diharapkan:*
```text
1711234567.89   Cabcde12345   192.168.10.50   8.8.8.8   udp   aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.attacker-c2.com   -
```

#### Langkah 5: Otomasi Respons Mitigasi (Penegakan Rule Kernel)
Ekstrak IP penyerang dari alert Suricata dan terapkan blokade langsung ke firewall kernel:

```bash
# Ekstraksi IP Sumber yang melanggar dari log fast.log dan injeksikan ke iptables
BAD_IP=$(grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' ./suricata_logs/fast.log | head -n 1)

echo "[*] Mengisolasi Host Terinfeksi: $BAD_IP"
sudo iptables -I FORWARD 1 -s $BAD_IP -j DROP
sudo iptables -I INPUT 1 -s $BAD_IP -j DROP

# Verifikasi keberadaan rule pemblokiran di kernel
sudo iptables -L -v -n | grep $BAD_IP
```

---

### 17. Real-world Case Study & Incident Analysis Enterprise

#### 17.1 Deskripsi Insiden: Kampanye Ransomware "FinSector-Alpha"
Sebuah lembaga perbankan regional mengalami insiden enkripsi ransomware yang mengunci 45% server virtual dalam cluster internal mereka. 

#### 17.2 Analisis Post-Mortem Vektor Intrusi
1.  **Titik Masuk (Initial Access):** Penyerang memanfaatkan kredensial VPN yang bocor milik kontraktor pihak ketiga. VPN tidak menerapkan inspeksi postur perangkat (ketiadaan ZTNA).
2.  **Pivoting & Pergerakan Lateral:** Setelah terhubung ke jaringan internal melalui VPN, koneksi diarahkan ke subnet data center flat (ketiadaan Micro-segmentation). Penyerang menggunakan credential dumping lokal via Mimikatz, lalu menyebarkan binary ransomware ke host lain melalui SMB (Port 445) dan WMI.
3.  **Kegagalan Deteksi Perimeter Tradisional:** Firewall perimeter tidak pernah membunyikan alarm karena seluruh komunikasi lateral berjalan murni di jaringan internal (East-West), tanpa melintasi perimeter fisik gateway sama sekali.
4.  **Eksfiltrasi Tersembunyi:** Sebelum fase enkripsi, penyerang mengeksfiltrasi 200 GB basis data nasabah melalui protokol HTTPS menggunakan TLS 1.3 ke alamat IP VPS publik yang baru didaftarkan. Forward Proxy internal tidak melakukan inspeksi SSL/TLS Decryption, sehingga seluruh proses transfer data tampak sah di traffic log firewall konvensional.

#### 17.3 Tindakan Remediasi Terukur
*   **Fase 1 (Isolasi Darurat):** Mengisolasi seluruh server menggunakan network segmentation policy dinamis via eBPF untuk menghentikan propagasi port 445/135 di seluruh layer data center.
*   **Fase 2 (Arsitektur Jangka Panjang):**
    *   Mengganti koneksi Direct VPN dengan ZTNA Solution yang mewajibkan Device Health Attestation dan verifikasi identitas berbasis FIDO2 WebAuthn.
    *   Menerapkan TLS Forward Proxy dengan sertifikat enterprise untuk menjalankan Deep Packet Inspection pada seluruh sesi lalu lintas web keluar.
    *   Menempatkan sensor Zeek di seluruh core-switch SPAN port untuk memetakan traffic baseline East-West dan mendeteksi anomali transfer data masif.

---

### 18. Quiz Pemahaman & Challenge

Uji pemahaman teknis Anda terhadap konsep yang dipaparkan dalam modul ini:

#### Pertanyaan 1:
Mengapa teknik *Target-Based TCP Normalization* sangat krusial diimplementasikan pada sistem IPS modern yang memproses lalu lintas inline?
*   A. Agar IPS dapat mempercepat proses enkripsi SSL/TLS secara paralel.
*   B. Untuk mencegah penyerang memanfaatkan perbedaan implementasi reassembly fragmen paket TCP/IP antara IPS dan OS target guna meloloskan payload berbahaya (*evasion*).
*   C. Untuk menggantikan fungsi routing OSPF dan BGP pada Layer 3.
*   D. Agar sistem dapat memblokir serangan DoS volumetrik berbasis UDP Flood tanpa menggunakan memori RAM.

#### Pertanyaan 2:
Perhatikan potongan skrip konfigurasi Suricata berikut:
```suricata
alert tcp $HOME_NET any -> $EXTERNAL_NET 443 (msg:"SUSPICIOUS JA3 HASH"; tls.ja3_hash; content:"e7d705a3286e19ea42f587b344ee6865"; sid:2000002; rev:1;)
```
Bagaimana engine Suricata dapat mengekstraksi dan mencocokkan `tls.ja3_hash` padahal paket mengarah ke port 443 yang terenkripsi?
*   A. Suricata secara otomatis memecahkan enkripsi AES-GCM secara brute-force.
*   B. Hash JA3 dihasilkan secara eksklusif dari paket payload terenkripsi setelah handshake selesai.
*   C. Hash JA3 diekstraksi murni dari paket unencrypted `Client Hello` saat proses negosiasi TLS handshake awal berlangsung sebelum enkripsi aktif.
*   D. Suricata mewajibkan private key server tujuan dimasukkan ke dalam konfigurasi rule.

#### Pertanyaan 3:
Dalam kerangka kerja Zero Trust (NIST SP 800-207), entitas mana yang bertindak langsung memutuskan apakah sebuah sesi komunikasi jaringan diizinkan atau ditolak berdasarkan analisis kebijakan identitas dan postur?
*   A. Policy Enforcement Point (PEP)
*   B. Policy Decision Point (PDP)
*   C. Data plane load balancer
*   D. Certificate Authority internal

#### Hands-on Challenge Teknis:
Sebuah server mencurigakan di jaringan internal mengirimkan paket HTTP POST berukuran 200 bytes secara berulang setiap tepat 60 detik (tanpa variasi/jitter) ke alamat IP antah berantah. 
*Tugas Anda:* Tuliskan satu file rule Suricata lengkap (dengan `content`, `flow`, `threshold` atau deteksi header HTTP yang presisi) untuk membunyikan alert dan memutus koneksi (`drop`) pada event transmisi HTTP beaconing tersebut!

---

### Kunci Jawaban & Pembahasan Quiz

*   **Jawaban Pertanyaan 1: B.** Jika IPS menyusun ulang paket fragmentasi secara berbeda dengan cara OS host target (misal OS Linux vs Windows) menyusunnya, penyerang dapat menyisipkan byte padding kosong pada fragmen yang hanya dibaca oleh IPS tetapi diabaikan oleh host target. Ini memungkinkan eksploitasi lolos dari deteksi tanpa memicu signature match pada IPS.
*   **Jawaban Pertanyaan 2: C.** JA3 mengumpulkan field Client Hello plaintext (versi SSL/TLS, Ciphersuite yang diterima, ekstensi TLS, Elliptic Curve, dan format kurva) yang dikirimkan secara terbuka sebelum sesi negosiasi kriptografi diselesaikan. Oleh karena itu, inspeksi JA3 tidak membutuhkan dekripsi payload private key.
*   **Jawaban Pertanyaan 3: B.** Policy Decision Point (PDP)—yang terdiri dari Policy Engine dan Policy Administrator—merupakan otak logis arsitektur Zero Trust yang memproses kebijakan dan mengeluarkan keputusan otorisasi, sedangkan Policy Enforcement Point (PEP) hanyalah pelaksana teknis yang mengeksekusi perintah blokir/izinkan dari PDP.

*   **Solusi Challenge Teknis:**
```suricata
drop http $HOME_NET any -> $EXTERNAL_NET any ( \
    msg:"SEC-IPS: Dropping Synchronous Malicious HTTP Beaconing"; \
    flow:established,to_server; \
    http.method; content:"POST"; \
    http.header_names; content:"Host"; \
    threshold: type both, track by_src, count 5, seconds 300; \
    classtype:trojan-activity; \
    sid:9000101; \
    rev:1; \
)
```

---

### 19. Summary & Key Takeaways

*   Konsep perimeter statis (*castle-and-moat*) tidak lagi relevan dalam lanskap ancaman modern; pertahanan harus diturunkan langsung ke level host melalui arsitektur micro-segmentation dan prinsip Zero Trust ("never trust, always verify").
*   Deep Packet Inspection (DPI) melampaui filtering IP/Port Layer 4 dengan melakukan reassembly TCP stateful dan inspeksi semantik payload Layer 7 menggunakan mesin akselerasi seperti Hyperscan.
*   Suricata unggul dalam penegakan kebijakan perlindungan intrusi secara inline berbasis signature, sementara Zeek melengkapi kapabilitas defensif dengan memproduksi telemetri struktural dan metadata perilaku protokol jaringan secara ekstensif.
*   Inspeksi TLS terenkripsi menjadi syarat mutlak untuk mendeteksi ancaman modern; pendekatan hibrida antara Forward Proxy Decryption dan analisis Fingerprinting pasif (JA3/JA4) merupakan strategi paling efektif dalam menjaga visibilitas trafik tanpa melumpuhkan infrastruktur.
*   Implementasi micro-segmentation modern berbasis kernel (eBPF) meminimalisir overhead performa dan latensi jika dibandingkan dengan traversing firewall tables tradisional, sekaligus menyediakan isolasi granular hingga ke level container socket.

---

### 20. Referensi Resmi & Standar Keamanan

1.  **NIST Special Publication 800-207:** *Zero Trust Architecture* (National Institute of Standards and Technology).
2.  **NIST Special Publication 800-94 Revision 1:** *Guide to Intrusion Detection and Prevention Systems (IDPS)*.
3.  **MITRE ATT&CK Framework:** Matriks Taktik & Teknik *Command and Control (TA0011)* dan *Lateral Movement (TA0008)*.
4.  **CIS Benchmarks for Network Devices:** Center for Internet Security Standards (Cisco, Palo Alto Networks, Checkpoint).
5.  **Suricata Documentation & Rule Specification Engine:** `https://docs.suricata.io/`
6.  **Zeek Network Security Monitor Reference Manual:** `https://docs.zeek.org/`
7.  **RFC 8446:** *The Transport Layer Security (TLS) Protocol Version 1.3*, Internet Engineering Task Force (IETF).