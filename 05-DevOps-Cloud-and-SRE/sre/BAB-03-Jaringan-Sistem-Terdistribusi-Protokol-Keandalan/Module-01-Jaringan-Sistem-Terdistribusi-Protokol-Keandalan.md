# Bab 03: Jaringan Sistem Terdistribusi & Protokol Keandalan

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis dan mengonfigurasi algoritma TCP Congestion Control (CUBIC vs. BBR) pada Linux kernel untuk mengoptimalkan throughput dan meminimalkan bufferbloat pada link berlatensi tinggi.
- Mengidentifikasi, memitigasi, dan mengotomatisasi pembersihan socket leaks (`CLOSE_WAIT`, `TIME_WAIT`) menggunakan tuning TCP Keepalive dan manajemen connection pool.
- Merancang arsitektur resolusi DNS tangguh pada Kubernetes/CoreDNS untuk mencegah kegagalan kaskade akibat TTL expiration dan cache poisoning/stale entries.
- Mendiagnosis degradasi performa pada HTTP/2 dan gRPC multiplexing akibat Head-of-Line (HoL) blocking pada layer L4 transport.
- Mengimplementasikan pola ketahanan terdistribusi: Circuit Breaking state machine, Exponential Backoff with Full Jitter, dan Request Hedging guna memangkas tail latency ($p99$/$p99.9$).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **OSI & TCP/IP Model**: Pemahaman mendalam mengenai Layer 4 (Transport: TCP/UDP) dan Layer 7 (Application: HTTP/1.1, HTTP/2, gRPC).
- **Linux Networking Fundamentals**: Konsep socket, file descriptor limits (`ulimit`), serta manipulasi parameter kernel via `sysctl`.
- **Dasar Pemrograman Sistem**: Pemahaman arsitektur asinkron (*event loop*, thread pool) dan networking I/O dalam bahasa Go atau Python.

---

## 3. Concept
Dalam komputasi terdistribusi, *Fallacies of Distributed Computing* pertama menyatakan bahwa *"The network is reliable"*. Pada skala produksi, jaringan fisik dan virtual adalah medium yang inheren tidak andal: paket mengalami *drop*, latensi berfluktuasi secara non-deterministik, dan rute mengalami kegagalan partisi (*split-brain/network partition*).

Keandalan sistem terdistribusi (Site Reliability Engineering) bukan dibangun dengan mengharapkan jaringan selalu sempurna, melainkan dengan merancang protokol perangkat lunak yang **tahan terhadap degradasi parsial**. Fondasi keandalan ini dibangun di dua lapisan:
1. **Lapisan Transport & OS Kernel (L4)**: TCP Congestion Control, State Machine Socket, dan DNS Resolution.
2. **Lapisan Aplikasi & RPC (L7)**: Multiplexing, Circuit Breaking, Adaptive Retries, dan Request Hedging.

---

## 4. Why
Tanpa pemahaman mendalam tentang jaringan dan protokol keandalan:
- **Bufferbloat & Throughput Collapse**: Algoritma congestion control loss-based konvensional (seperti Reno/CUBIC) mengartikan *dropped packet* sebagai indikator tunggal kongesti, memicu retransmisi berlebihan dan lonjakan latensi RTT (*Round Trip Time*).
- **Cascading Failures**: Layanan hilir (*downstream*) yang lambat menyebabkan kehabisan koneksi (*connection pool exhaustion*) pada layanan hulu (*upstream*), menjatuhkan seluruh kluster dependensi dalam hitungan detik.
- **Thundering Herd Problem**: Mekanisme retry tanpa *exponential backoff* dan *jitter* akan menghantam sistem yang baru pulih dengan beban ribuan kali lipat dari kapasitas normalnya.
- **Tail Latency Amplification**: Dalam arsitektur microservices dengan puluhan fan-out RPC, latensi $p99$ dari satu komponen kecil akan menjadi batas bawah latensi keseluruhan pengguna.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 TCP Congestion Control: CUBIC vs. BBR
Kongesti jaringan terjadi ketika laju data yang dikirim melampaui kapasitas buffer router transit.

```
+-----------------------------------------------------------------------+
| TCP CUBIC (Loss-Based)                                                |
| Mengisi buffer router hingga penuh -> Packet Drop -> Window Halved    |
| Mengakibatkan: Bufferbloat, RTT berfluktuasi tinggi                   |
+-----------------------------------------------------------------------+
                                  VS
+-----------------------------------------------------------------------+
| TCP BBR (Bottleneck Bandwidth and RTT - Model-Based)                   |
| Mengukur laju transfer maksimum (BtlBw) dan propagasi minimum (RTprop)|
| Mengakibatkan: Antrian buffer kosong, latensi stabil, throughput max  |
+-----------------------------------------------------------------------+
```

- **TCP CUBIC**: Menggunakan fungsi kubik untuk mengatur Congestion Window ($cwnd$). Pertumbuhan window sangat agresif hingga terjadi packet drop. Pada link modern dengan buffer router yang besar, CUBIC memicu fenomena **Bufferbloat** (paket mengantre di buffer router, RTT melonjak dari 10ms menjadi 1200ms sebelum paket di-drop).
- **TCP BBR (v1/v2/v3)**: Dikembangkan oleh Google. BBR tidak menggunakan packet drop sebagai sinyal utama kongesti. BBR secara kontinyu mengestimasi dua parameter fisik:
  1. $\text{BtlBw}$ (*Bottleneck Bandwidth*): Kapasitas pipa transmisi aktual.
  2. $\text{RTprop}$ (*Round-Trip Propagation Time*): Waktu tempuh murni tanpa antrean.
  BBR mengirim data tepat pada laju $\text{BtlBw} \times \text{RTprop}$ (*Bandwidth-Delay Product* / BDP), menjaga pipa transmisi penuh tanpa mengisi buffer antrian router.

### 5.2 TCP Keepalive & Connection Leaks
Socket lifecycle pada TCP melibatkan status koneksi:
- **`TIME_WAIT`**: Sisi yang melakukan *active close* memasuki status ini selama $2 \times \text{MSL}$ (Maximum Segment Lifetime, default Linux: 60 detik) untuk memastikan ACK penutupan diterima remote peer dan paket lama di jaringan kadaluwarsa. Penumpukan socket `TIME_WAIT` menghabiskan ephemeral ports (port exhaustion: `net.ipv4.ip_local_port_range`).
- **`CLOSE_WAIT`**: Sisi penerima FIN lokal yang belum mengeksekusi penutupan socket (`close()`). Ini adalah indikator pasti adanya **resource leak di level aplikasi** (aplikasi tidak menutup koneksi HTTP/TCP setelah stream selesai).
- **Half-Open Connections**: Terjadi ketika node remote mati tiba-tiba tanpa mengirim paket FIN/RST (misal: kabel putus, crash hypervisor). Tanpa TCP Keepalive aktif, OS lokal akan mempertahankan socket tersebut terbuka selamanya, menghabiskan alokasi file descriptor.

Parameter TCP Keepalive kernel:
- `tcp_keepalive_time`: Waktu inaktivitas sebelum probe pertama dikirim (default: 7200s -> wajib dituning ke 60-300s).
- `tcp_keepalive_intvl`: Interval antar probe jika tidak ada respons (default: 75s -> 10-15s).
- `tcp_keepalive_probes`: Jumlah kegagalan probe sebelum koneksi diputus paksa (default: 9 -> 3-5).

### 5.3 DNS Caching & Stale DNS in Distributed Systems
Resolusi DNS pada arsitektur microservices adalah critical path:
- **TTL (Time to Live) Expiration**: Nilai TTL yang terlalu rendah membebani upstream resolver (CoreDNS/Bind9) dengan request query UDP/TCP berlebih. Nilai TTL yang terlalu tinggi menunda failover IP ketika service berpindah pod/node.
- **JVM DNS Caching Caveat**: Java Virtual Machine (JVM) secara historis melakukan caching IP selamanya (*cache forever*) jika security manager aktif, mengabaikan perubahan DNS record saat pod Kubernetes di-redeploy. Diperlukan konfigurasi eksplisit `networkaddress.cache.ttl`.
- **Negative Caching (SOA MINIMUM)**: Kegagalan query (NXDOMAIN) disimpan dalam cache resolver sesuai dengan nilai minimum TTL di record SOA, menyebabkan jeda pemulihan meskipun endpoint target telah aktif kembali.

### 5.4 HTTP/2 & gRPC Multiplexing
HTTP/2 mengeliminasi masalah *head-of-line blocking* di layer aplikasi HTTP/1.1 dengan membagi pesan menjadi beberapa frame independen yang ditransmisikan secara interleaved dalam satu koneksi TCP tunggal.
- **Masalah L4 HoL Blocking**: Karena semua stream HTTP/2 dan gRPC berjalan di atas satu koneksi TCP, jika terjadi *single packet drop* pada jaringan fisik, TCP kernel akan menahan seluruh frame dari stream lain di socket buffer sampai segmen yang hilang berhasil diretransmisi.
- **Connection Churn vs. Multiplexing**: Berbagi satu koneksi TCP untuk ratusan RPC konkuren menghemat TCP handshake dan TLS overhead, namun memusatkan risiko bottleneck pada satu core CPU dan satu TCP window.

### 5.5 Circuit Breaking (Netflix Hystrix Pattern)
Pola Circuit Breaker mencegah aplikasi mengeksekusi operasi yang diprediksi akan gagal.

```
       +---------+
       |         |  Failure Rate > Threshold
       | CLOSED  |----------------------------+
       |         |                            |
       +---------+                            v
            ^                            +----------+
            | Success Rate > Threshold   |          |
            +----------------------------|   OPEN   |
            |                            |          |
       +-----------+                     +----------+
       |           |   Sleep Window Expires   |
       | HALF-OPEN |<-------------------------+
       |           |   (Canary/Probe Request)
       +-----------+
```

1. **Closed**: Permintaan diteruskan ke layanan downstream. Metrik kegagalan (error rate/timeout) dicatat dalam sliding time window.
2. **Open**: Error rate melampaui batas ambang (*failure threshold*, misal 50% dalam 10 detik). Permintaan langsung digagalkan secara instan (*fast-fail*) tanpa membebani downstream atau memblokir thread client.
3. **Half-Open**: Setelah periode tidur (*sleep window*) terlewati, sistem mengizinkan sejumlah kecil request uji (*canary/probe*) lewat. Jika sukses, breaker kembali ke status **Closed**; jika gagal, status kembali ke **Open**.

### 5.6 Exponential Backoff with Jitter
Saat melakukan retry terhadap dependensi yang gagal, interval retry statis akan mengakibatkan korelasi waktu pengiriman request dari ribuan client secara bersamaan (*Thundering Herd*).

Rumus Exponential Backoff:
$$T_{\text{backoff}} = \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}})$$

Penambahan **Full Jitter** mendistribusikan beban secara seragam (*uniform distribution*):
$$T_{\text{sleep}} = \text{random\_between}(0, T_{\text{backoff}})$$

Penambahan **Decorrelated Jitter** (AWS Algorithm):
$$T_{\text{sleep}} = \min(T_{\text{max}}, \text{random\_between}(T_{\text{base}}, T_{\text{previous}} \times 3))$$

### 5.7 Request Hedging
Request Hedging adalah teknik reduksi tail latency ($p95$, $p99$) dengan mengirimkan duplikat request identik ke replika layanan downstream yang berbeda jika request pertama tidak memberikan respons dalam ambang batas waktu tertentu (misal: persentil 95 dari baseline latensi).
- Client mengeksekusi Request A ke Pod 1.
- Jika dalam $N$ milidetik Pod 1 belum merespons, Client mengeksekusi Request B (hedged) ke Pod 2.
- Client memproses respons mana saja yang tiba lebih dahulu dan membatalkan (cancel) request yang masih berjalan.
- **Risiko**: Meningkatkan total beban server (*traffic amplification*). Hanya aman digunakan untuk operasi yang bersifat **idempotent** (GET, PUT idempotent, read-only queries).

---

## 6. How
Implementasi keandalan jaringan dilakukan dengan strategi multi-tier:
1. **Host/Node Level**: Tuning TCP socket limits, buffer sizes, dan algoritma BBR via Linux kernel parameters.
2. **Cluster/Mesh Level**: Konfigurasi envoy proxy atau CoreDNS untuk tuning connection pool, keepalive probe, dan upstream timeouts.
3. **Application Level**: Integrasi library ketahanan client (Circuit Breaker, Hedging, Jittered Retries) pada HTTP client dan gRPC interceptors.

---

## 7. Analogy
Bayangkan jalan raya distribusi logistik:
- **TCP CUBIC** seperti sopir truk yang terus menambah kecepatan sampai menabrak pembatas jalan (packet drop), lalu panik mengerem mendadak setengah kecepatan, lalu memacu truk kembali.
- **TCP BBR** seperti sistem radar pintar pada truk yang mendeteksi kepadatan jalan di depan dan kapasitas aspal, mengunci kecepatan tepat pada laju aliran maksimum tanpa memicu rem mendadak.
- **Circuit Breaker** adalah sekring listrik di rumah Anda. Ketika terjadi korsleting pada mesin pemanas air, sekring putus seketika untuk mencegah kebakaran merembet ke seluruh jaringan kabel rumah.
- **Jitter** seperti jam pulang kantor buruh pabrik yang diacak dalam rentang 15 menit agar jalan keluar tidak langsung macet total secara serentak.

---

## 8. Diagram (ASCII)

### TCP Socket State Machine (Termination & Leaks)
```
       Client (Active Close)                        Server (Passive Close)
                 |                                             |
           [ESTABLISHED]                                 [ESTABLISHED]
                 |                                             |
   close()       |                                             |
  -------------> |                                             |
                 |--- FIN ------------------------------------>|
           [FIN_WAIT_1]                                        |  OS acknowledges
                 |                                       [CLOSE_WAIT] (Leak here if app
                 |<-- ACK -------------------------------------|             fails to close)
           [FIN_WAIT_2]                                        |
                 |                                             |  close() called
                 |                                             |  by server app
                 |<-- FIN -------------------------------------|
                 |                                        [LAST_ACK]
           [TIME_WAIT]                                         |
 (Waits 2*MSL    |--- ACK ------------------------------------>|
  e.g., 60s)     |                                          [CLOSED]
                 |
              [CLOSED]
```

### Request Hedging Latency Optimization
```
Client                      Downstream Pod-1              Downstream Pod-2
  |                                |                             |
  |--- Send Request 1 ------------>| (Experiencing GC Pause/I/O) |
  |                                |                             |
  | (Wait p95 threshold: 45ms)     |                             |
  | Timer expired!                 |                             |
  |--- Send Hedged Request 2 ----------------------------------->|
  |                                |                             |--- (Processing: 8ms)
  |<-- Return Response 2 ----------------------------------------|
  |                                |                             |
  |--- Cancel Request 1 ---------->| (Aborted)                   |
  v                                v                             v
Total Latency: 53ms (instead of waiting >500ms for Pod-1)
```

---

## 9. Simple Example
Implementasi Exponential Backoff dengan Full Jitter dalam Python native:

```python
import random
import time

def execute_with_jitter(action, max_attempts=5, base_delay=0.1, max_delay=3.0):
    for attempt in range(max_attempts):
        try:
            return action()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise e
            # Formula: min(max_delay, base_delay * 2^attempt)
            calculated_backoff = min(max_delay, base_delay * (2 ** attempt))
            # Full Jitter: Sleep between 0 and calculated_backoff
            sleep_duration = random.uniform(0, calculated_backoff)
            print(f"[Attempt {attempt+1}] Gagal: {e}. Backoff: {sleep_duration:.3f}s")
            time.sleep(sleep_duration)
```

---

## 10. Practical Example (Konfigurasi CLI / Kernel / Code)

### 10.1 Linux Kernel Tuning (`/etc/sysctl.d/99-sre-network.conf`)
Konfigurasi produksi untuk high-throughput microservices node:

```ini
# Aktifkan BBR Congestion Control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Mitigasi Penumpukan Socket TIME_WAIT & Port Exhaustion
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10240 65535

# TCP Keepalive Aggressive Tuning (Mendeteksi dead peers dalam ~60 detik)
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 3

# Buffer Sizes Optimization (Auto-tuning window limits)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Socket backlog untuk menahan burst connections
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192
```
Terapkan dengan:
```bash
sudo sysctl -p /etc/sysctl.d/99-sre-network.conf
```

### 10.2 Verifikasi Congestion Control & Socket State di Linux
```bash
# Cek algoritma congestion control yang aktif pada koneksi yang berjalan
ss -tih '( dport = :https or dport = :http )'

# Hitung jumlah socket per status
ss -ant | awk '{print $1}' | sort | uniq -c | sort -n
```

### 10.3 CoreDNS Tuning ConfigMap (Kubernetes)
Mencegah kelebihan beban UDP dan stale records pada resolusi upstream:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
            lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf {
            max_concurrent 1000
            prefer_udp
        }
        cache 30 {
            success 10000 30
            denial 5000 5
        }
        loop
        reload
        loadbalance
    }
```

---

## 11. Real World Example
Pada kasus pemadaman sistem perbankan skala besar (misal insiden *monolithic-to-microservices migration*):
- **Akar Masalah**: Sebuah microservice otentikasi mengalami degradasi respons dari 15ms menjadi 4000ms akibat database lock.
- **Dampak Kaskade**: Layanan API Gateway dan Payment Service memiliki connection pool timeout default 30 detik tanpa Circuit Breaker. Client web dan mobile melakukan auto-retry instan setiap 500ms secara paralel.
- **Eskalasi Jaringan**: Socket pada API Gateway menyentuh batas `ulimit` (open file descriptors). Socket memasuki status `CLOSE_WAIT` ribuan kali karena thread gateway mati mendadak (*OOMKilled* / *Thread Starvation*) sebelum membaca data dari pipe. Seluruh kluster Kubernetes gateway kolaps.
- **Resolusi SRE**:
  1. Menerapkan Circuit Breaker pada Envoy proxy dengan ambang 50% timeout langsung fast-fail status HTTP 503 dalam 20ms.
  2. Mengaktifkan exponential backoff dengan full jitter pada SDK mobile/frontend.
  3. Mengubah Linux congestion control node worker dari CUBIC ke BBR, memotong tail latency $p99$ akibat drop TCP packet di AWS NAT Gateway sebesar 42%.

---

## 12. Trade-offs

| Pilihan Solusi | Keuntungan | Kerugian / Biaya Operasional |
| :--- | :--- | :--- |
| **TCP BBR** | Throughput maksimal pada packet-loss rate tinggi, RTT stabil rendah. | Pada jaringan dengan loss sangat tinggi (>20%), BBRv1 dapat menjadi terlalu agresif dan memonopoli bandwidth terhadap traffic CUBIC (*unfairness*). |
| **Circuit Breaker** | Mengisolasi kegagalan, melindungi downstream, memotong latency starvation. | Menambah kompleksitas state tracking; potensi false-positive memutus traffic valid jika threshold terlalu sensitif. |
| **Request Hedging** | Menghancurkan tail latency $p99$ secara dramatis. | Meningkatkan beban CPU, jaringan, dan memory hingga 20-30% karena request spekulatif yang akhirnya dibatalkan. |
| **Aggressive Keepalive** | Cepat mendeteksi dead nodes dan mereklamasi socket hang. | Konsumsi bandwidth dan wake-up CPU kecil terus menerus, risiko memutus koneksi lambat yang sah di jaringan mobile berlatensi tinggi. |

---

## 13. When To Use
- **TCP BBR**: Pada komunikasi inter-region, cluster multi-cloud, atau service yang melayani aset statis/streaming ke client publik dengan koneksi bervariasi.
- **Circuit Breaker**: Pada setiap RPC keluar (outbound) yang melintasi batasan proses, thread pool, atau network boundary (L7 API calls, database connectors).
- **Request Hedging**: Pada operasi read-only yang idempotent dengan SLA p99 ketat (misal: sistem search indexing, ad-bidding, retrieval cache).

---

## 14. When NOT To Use
- **Request Hedging**: **Dilarang keras** untuk operasi non-idempotent (misal: `POST /api/v1/charge-credit-card` atau mutasi inventori) karena memicu duplicate write transactions.
- **Circuit Breaker Agresif**: Pada pipeline pemrosesan batch asynchronously (Kafka consumers, batch cron jobs) di mana latensi bukan prioritas utama dan backpressure queue lebih diutamakan daripada fast-fail.
- **Penurunan TTL DNS ke 0s**: Menyebabkan query lookup pada setiap koneksi baru, melumpuhkan CoreDNS/DNS Server dengan beban query raksasa.

---

## 15. Common Mistakes
1. **Mengabaikan Idempotensi pada Retry**: Menjalankan retry otomatis pada panggilan API mutating (POST) tanpa idempotency key di sisi server, memicu eksekusi ganda.
2. **Koneksi HTTP/1.1 Leaks**: Membaca respons HTTP di aplikasi (misal: Go `resp.Body` atau Python `requests.get()`) tanpa memanggil `.Close()` di dalam blok `finally`/`defer`. Hal ini membiarkan koneksi menggantung pada status `CLOSE_WAIT` di sisi OS.
3. **Retrying on 4xx Errors**: Melakukan retry pada HTTP status code 400 (Bad Request), 401 (Unauthorized), atau 404 (Not Found). Error level 4xx bersifat definitif dari sisi client dan tidak akan pernah berhasil tanpa perubahan payload.
4. **Menggunakan TCP Keepalive untuk Deteksi Aplikasi**: Mengira TCP Keepalive dapat mendeteksi aplikasi downstream yang hang. TCP Keepalive ditangani oleh Linux kernel; jika proses aplikasi mengalami deadlock namun kernel OS masih hidup, kernel tetap merespons TCP ACK Keepalive. L7 Application Heartbeat tetap mutlak diperlukan.

---

## 16. Best Practices
1. **Gunakan Standard Jitter**: Gunakan formula AWS Full Jitter atau Decorrelated Jitter pada seluruh retry logic.
2. **Set Timeout Berlapis**:
   - `Connect Timeout`: Sangat ketat (misal: 500ms - 1s).
   - `Read/Write Timeout`: Disesuaikan dengan SLA (misal: 2s - 5s).
   - `Global Request Deadline / Context Propagation`: Menyebarkan batas waktu total dari ingress ke microservice terdalam (menggunakan OpenTelemetry / gRPC metadata `grpc-timeout`).
3. **Standarisasi Connection Pool**: Konfigurasi ukuran pool koneksi HTTP/gRPC (`MaxIdleConns`, `MaxIdleConnsPerHost`, `IdleConnTimeout`) untuk mencegah reconnect storm saat lonjakan trafik.
4. **Aktifkan TCP `tw_reuse`**: Di level kernel Linux untuk proxy/load balancer guna mereklamasi socket `TIME_WAIT` untuk outgoing connection baru secara aman.

---

## 17. Troubleshooting

| Gejala Masalah | Metrik / Indikator Kernel | Investigasi / Perintah Debugging | Solusi Perbaikan |
| :--- | :--- | :--- | :--- |
| **`connection refused` / Socket Exhaustion** | Lonjakan status `TIME_WAIT` pada `ss` | `ss -s`<br>`netstat -nat \| grep TIME_WAIT \| wc -l` | Aktifkan `net.ipv4.tcp_tw_reuse = 1`; implementasikan connection pooling di sisi client/proxy. |
| **Aplikasi kehabisan File Descriptors** | Lonjakan status `CLOSE_WAIT` | `lsof -p <PID> \| grep TCP`<br>`ss -tap \| grep CLOSE_WAIT` | Perbaiki bug software: pastikan `response.body.close()` dieksekusi di blok pembersihan memory. |
| **Throughput drop tajam pada link jauh** | Packet drops + window collapse | `ss -ti dst <IP>` (Cek `cwnd`, `rtt`, `retrans`) | Ganti congestion control ke BBR: `sysctl -w net.ipv4.tcp_congestion_control=bbr`. |
| **P99 Latency membengkak secara periodik** | CoreDNS cache misses / high latency | `kubectl logs -n kube-system -l k8s-app=kube-dns`<br>`dig @CoreDNS_IP my-service +trace` | Konfigurasi NodeLocal DNSCache pada Kubernetes; naikkan TTL cache DNS internal. |

---

## 18. Exercise
1. Lakukan audit pada mesin Linux lokal atau VM Anda:
   - Identifikasi algoritma congestion control yang sedang aktif menggunakan perintah `sysctl`.
   - Gunakan `ss -s` untuk melihat ringkasan socket saat ini.
2. Hitung backoff delay menggunakan bahasa pemrograman pilihan Anda untuk percobaan ke-4 dengan $T_{\text{base}} = 200\text{ms}$, $T_{\text{max}} = 5000\text{ms}$ di bawah mode **Full Jitter**. Tuliskan rentang nilai delay yang mungkin muncul.

---

## 19. Challenge
Rancang arsitektur RPC gRPC resilient antara dua microservices lintas region (US-East ke EU-West) yang melintasi koneksi internet publik dengan RTT rata-rata 110ms dan packet loss 1.5%.
- Formulasikan konfigurasi TCP kernel yang optimal pada kedua VM.
- Tentukan kebijakan retry, circuit breaker thresholds, dan parameter request hedging (persentil latency threshold).
- Jelaskan mekanisme pertahanan agar request hedging tidak mengakibatkan kelebihan beban (amplification attack) jika EU-West mengalami degradasi komputasi internal.

---

## 20. Summary
Keandalan jaringan terdistribusi bukanlah atribut alami perangkat keras, melainkan hasil rekayasa protokol defensif yang proaktif:
- Algoritma **TCP BBR** memisahkan kongesti dari kehilangan paket murni, mengoptimalkan throughput modern tanpa memicu bufferbloat.
- Penanganan **TCP Socket & Keepalive** yang tepat membersihkan sumber daya sistem sebelum terjadi port dan file descriptor exhaustion.
- **Circuit Breaker** menghentikan propagasi kegagalan kaskade (*fail fast*).
- **Exponential Backoff dengan Jitter** memecah sinkronisasi retry yang merusak (*thundering herd*).
- **Request Hedging** secara terukur memangkas *long-tail latency* pada critical path read-only operations.