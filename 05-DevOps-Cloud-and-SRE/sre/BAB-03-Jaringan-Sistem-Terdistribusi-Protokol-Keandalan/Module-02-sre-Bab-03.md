# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Jaringan Sistem Terdistribusi & Protokol Keandalan**
**Kategori: 05-DevOps-Cloud-and-SRE**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menganalisis dan memitigasi anomali performa jaringan pada Layer 4 (Transport) dan Layer 7 (Application) dalam ekosistem sistem terdistribusi skala besar.
- Mengonfigurasi dan membedah internal transport stack (HTTP/2, gRPC multiplexing, dan HTTP/3 QUIC) untuk mengeliminasi fenomena *Head-of-Line (HoL) Blocking*.
- Mengimplementasikan pola keandalan komunikasi tingkat lanjut (*Tail-Tolerance Pattern*): *Hedged Requests*, *Adaptive Concurrency Limits*, *Dynamic Connection Pooling*, dan *Outlier Detection* menggunakan Envoy Proxy dan Go.
- Melakukan isolasi dan troubleshooting degradasi performa jaringan kernel-space (socket buffer exhaustion, TCP slow-start, TIME_WAIT saturation, epoll event starvation) menggunakan *eBPF* dan utilitas jaringan modern.
- Menghitung dampak amplifikasi *tail latency* ($p99$ fan-out problem) secara matematis dan merancang arsitektur jaringan yang berdaya tahan tinggi terhadap degradasi parsial (*graceful degradation*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
1. **Model Jaringan OSI/TCP-IP**: Siklus hidup 3-way handshake TCP, segmentasi paket, mekanisme *Flow Control* (Sliding Window), dan *Congestion Control* dasar (CUBIC, Reno).
2. **Dasar Sistem Terdistribusi**: Karakteristik RPC (*Remote Procedure Call*), fallacies of distributed computing, dan sinkronisasi clock.
3. **Sistem Operasi Tingkat Menengah**: File descriptor, abstraksi socket Linux, I/O multiplexing (`select`, `poll`, `epoll`).
4. **Bahasa Pemrograman**: Pemrograman Go tingkat menengah (Goroutines, Channels, Context, sync primitives).
5. **Observabilitas**: Konsep Golden Signals (Latency, Traffic, Errors, Saturation) dan Distributed Tracing (OpenTelemetry/W3C Trace Context).

---

## 3. Concept & Internal Architecture

Keandalan jaringan dalam sistem terdistribusi enterprise bukan sekadar memastikan kabel atau rute virtual terhubung, melainkan bagaimana sistem mengelola ketidakpastian (*non-determinism*) dari transmisi data L4 hingga L7.

### 3.1 Anatomi L4 vs L7 Transport Dynamics

```
+-------------------------------------------------------------------------+
| L7: Application Layer                                                   |
| - Protokol: HTTP/1.1 vs HTTP/2 vs gRPC (HTTP/2) vs HTTP/3 (QUIC)        |
| - Multiplexing: Virtual Streams dalam 1 TCP/UDP Connection             |
| - Flow Control: HTTP/2 Stream-level Window vs Connection-level Window   |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| L4: Transport Layer (Linux Kernel Space)                                |
| - State Machine: ESTABLISHED, TIME_WAIT, CLOSE_WAIT                     |
| - Socket Buffers: SO_SNDBUF, SO_RCVBUF, sk_buff Queues                  |
| - Congestion Control: Reno, CUBIC, BBR (Bandwidth & RTT)                |
| - Queue Discipline: qdisc, CoDel, fq (Fair Queueing)                    |
+-------------------------------------------------------------------------+
```

#### 3.1.1 Head-of-Line (HoL) Blocking: TCP vs HTTP/2 vs QUIC
- **HTTP/1.1**: Menggunakan 1 koneksi TCP untuk 1 request-response pada satu waktu (kecuali *pipelining* yang sering gagal implementasi). HoL blocking terjadi di level L7: Request B harus menunggu Request A selesai diproses server.
- **HTTP/2**: Mengatasi L7 HoL blocking dengan memperkenalkan konsep **Streams** dan **Frames**. Beberapa request/response dipecah menjadi frame-frame biner dan dikirim melalui **satu koneksi TCP yang sama**. Namun, HTTP/2 melahirkan kerentanan baru: **L4 HoL Blocking**. Jika satu paket TCP hilang (*packet loss*), TCP stack di kernel penerima menahan semua paket berikutnya di socket buffer hingga paket yang hilang dikirim ulang (*retransmitted*), membekukan *seluruh* HTTP/2 stream yang ada di dalam koneksi tersebut.
- **HTTP/3 (QUIC)**: Dibangun di atas UDP. QUIC mengimplementasikan mekanisme keandalan (*loss recovery* dan *congestion control*) di *userspace* pada level stream individual. Jika paket yang membawa frame untuk Stream A hilang, hanya Stream A yang terhenti; Stream B, C, dan D terus berjalan tanpa terinterupsi.

### 3.2 Linux Kernel Socket Subsystem & I/O Multiplexing

Ketika aplikasi Go atau Envoy membaca data dari socket, alur internal kernel Linux melibatkan struktur data berikut:

```
[ NIC Hardware ]
      │ (DMA Transfer)
      ▼
[ Ring Buffer (rx_ring) ] ──(Hard IRQ)──> [ CPU Core Scheduler ]
                                                  │
                                                  ▼ (ksoftirqd / NAPI Poll)
                                         [ sk_buff Allocation ]
                                                  │
                                                  ▼
                                      [ Protocol Layer: TCP/IP ]
                                                  │
                                                  ▼
                                         [ Socket Receive Buffer ]
                                         (tcp_rmem: min/default/max)
                                                  │
                                                  ▼ (epoll_wait wake-up)
                                          [ Userspace: Envoy/Go ]
```

1. **Ingress Path**: NIC menerima sinyal fisik, mentransfer frame ke memori host melalui *Direct Memory Access* (DMA) ke dalam `rx_ring buffer`. NIC memicu Hardware Interrupt (IRQ).
2. **NAPI Subsystem**: Kernel menonaktifkan IRQ NIC dan beralih ke mode polling menggunakan `ksoftirqd` via NAPI subsystem untuk mencegah CPU *livelock* saat traffic tinggi.
3. **sk_buff Allocation**: Kernel membungkus data ke dalam struct `sk_buff`, memverifikasi checksum IP, merakit kembali fragmentasi TCP, dan memasukkan data ke `Socket Receive Buffer` (`SO_RCVBUF`).
4. **Epoll Notification**: Thread userspace (misal: Envoy Worker atau Go Netpoller) yang tertidur di sistem call `epoll_wait` akan dibangunkan oleh event `EPOLLIN` menggunakan *edge-triggered* flag (`EPOLLET`), menandakan data siap di-*consume* ke memori userspace via `read()`/`recv()`.

### 3.3 Envoy Proxy Threading Architecture & L7 Filter Engine

Arsitektur Envoy berbasis **Event-Driven, Non-Blocking, Multi-Threaded Model**:

```
+-------------------------------------------------------------+
|                         Envoy Main Thread                   |
| - Control Plane (xDS API) Client                           |
| - Lifecycle Management & Stats Flusher                     |
+-------------------------------------------------------------+
         │                         │                        │
         ▼                         ▼                        ▼
+-----------------+       +-----------------+      +-----------------+
| Worker Thread 1 |       | Worker Thread 2 |      | Worker Thread N |
| - libevent loop |       | - libevent loop |      | - libevent loop |
| - epoll_wait    |       | - epoll_wait    |      | - epoll_wait    |
| - Filter Chain  |       | - Filter Chain  |      | - Filter Chain  |
| - Upstream Pool |       | - Upstream Pool |      | - Upstream Pool |
+-----------------+       +-----------------+      +-----------------+
        ▲                         ▲                        ▲
        └─────────────────────────┼────────────────────────┘
                                  │ SO_REUSEPORT
                          [ Kernel Socket Listen ]
```

- **Thread-Local Architecture**: Setiap Worker Thread berjalan independen pada satu core CPU. Setelah koneksi di-*accept* (dibagi antar worker via kernel flag `SO_REUSEPORT`), semua operasi I/O, eksekusi HTTP Filter Chain, TLS processing, dan routing dilakukan secara eksklusif oleh worker tersebut tanpa locking antar-thread (*shared-nothing architecture*).
- **Upstream Connection Pooling**: Tiap worker memelihara connection pool tersendiri ke upstream cluster. Hal ini meminimalkan *thread contention*, namun berarti jumlah total koneksi ke upstream adalah:
  $$\text{Total Connections} = \text{Workers} \times \text{Connections per Worker}$$
  SRE wajib memperhitungkan ini agar tidak memicu *file descriptor exhaustion* di sisi server upstream.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
Pada sistem monolitik, interaksi antar-modul berlangsung di in-memory bus dengan latensi sub-mikrodetik dan keandalan $\approx 100\%$. Pada arsitektur microservices terdistribusi, interaksi bermutasi menjadi panggilan jaringan L4/L7 yang melewati router, switch, NAT gateways, firewall, dan software proxies.

### The Tail Latency Amplification Problem ($p99$ Fan-Out)
Misalkan sebuah request masuk ke API Gateway dan memerlukan panggilan konkuren ke 100 microservices di backend untuk merakit response. Jika tiap microservice memiliki performa $p99 = 100\text{ ms}$ (artinya hanya 1% request yang melebihi 100 ms):

Peluang bahwa API Gateway mengalami latensi $> 100\text{ ms}$ adalah:
$$P(\text{Delayed Request}) = 1 - (1 - p)^N$$
$$P(\text{Delayed Request}) = 1 - (1 - 0.01)^{100} = 1 - (0.99)^{100} \approx 1 - 0.366 = 0.634 \implies \mathbf{63.4\%}$$

Meskipun setiap service individu memiliki SLA $99\%$, dari kacamata user, **63.4% dari total request akan terkena dampak lambat**. Tanpa mekanisme keandalan jaringan tingkat lanjut, sistem terdistribusi dengan fan-out tinggi secara inheren dijamin lambat.

### Karakteristik Protokol Keandalan Modern
1. **Adaptive Concurrency Limit (ACL)**: Menggantikan static rate-limiting dengan algoritma dinamik berbasis latensi (misal: TCP Vegas atau Gradient Concurrency Limit) untuk mendeteksi saturasi upstream secara preventif.
2. **Hedged Requests**: Mengirim request duplikat ke replika upstream yang berbeda setelah melewati ambang batas latensi tertentu ($p95$), mengambil respons yang kembali lebih dulu, dan membatalkan request lainnya.
3. **Active Outlier Detection**: Mengeluarkan instance upstream dari load balancing pool secara instan jika mengalami error L5-L7 berturut-turut (*e.g.* 502/503/504 status codes atau TCP reset).

---

## 5. How (Workflow Detail)

Berikut adalah workflow end-to-end penanganan traffic service-to-service menggunakan Envoy L7 Engine dengan mitigasi latensi:

```
[Client SDK]        [Envoy Ingress]         [Envoy Egress]       [Upstream Svc A]  [Upstream Svc B]
     │                     │                       │                     │                 │
     │── 1. gRPC Call ────>│                       │                     │                 │
     │   (H2 Multiplex)    │                       │                     │                 │
     │                     │── 2. Run Filters ────>│                     │                 │
     │                     │   (RBAC, RateLimit)   │                     │                 │
     │                     │                       │── 3. Route & Select │                 │
     │                     │                       │   LoadBalancer Pool │                 │
     │                     │                       │                     │                 │
     │                     │                       │── 4. Dispatch Req ─>│                 │
     │                     │                       │      (To Replica A) │                 │
     │                     │                       │                     │ (Processing...  │
     │                     │                       │                     │  Slow: > p95)   │
     │                     │                       │── 5. Hedged Req ─────────────────────>│
     │                     │                       │      (Timer Expiry) │                 │ (Processing...
     │                     │                       │                     │                 │  Fast)
     │                     │                       │<── 6. First Response ─────────────────│
     │                     │                       │                       (HTTP 200 OK)
     │                     │                       │── 7. Cancel Context ──x
     │                     │                       │      (Stream Reset)
     │                     │<── 8. Return Frame ───│
     │<── 9. Return Stream─│
```

### Penjelasan Tahapan:
1. **Inbound Multiplexing**: Client mengirim gRPC call melalui satu HTTP/2 connection. Frame data dialokasikan Stream ID tertentu.
2. **Filter Processing**: Envoy worker mengeksekusi HTTP connection manager filters (Trace propagation, JWT validation, local circuit breaker checks).
3. **Router Filter & Concurrency Validation**: Router memilih cluster upstream. Envoy memeriksa Concurrency Limit engine; jika kapasitas queue penuh, request langsung ditolak dengan status code `503 Service Unavailable / CircuitBreakerTripped` untuk memproteksi ketersediaan cluster.
4. **Primary Dispatch**: Envoy memilih instance Upstream Svc A berdasarkan algoritma Maglev atau Round Robin, lalu mengalokasikan stream pada koneksi yang sudah tersedia dalam connection pool.
5. **Hedged Timer & Speculative Execution**: Jika Upstream Svc A tidak merespons dalam target waktu (misal: $p95 = 20\text{ ms}$), timer hedging lokal memicu pengiriman duplikat request ke Upstream Svc B tanpa menghentikan request pertama.
6. **Race Resolution**: Upstream Svc B merespons lebih cepat dengan HTTP 200.
7. **Stream Cancellation**: Envoy segera mengirim HTTP/2 `RST_STREAM` frame ke Upstream Svc A untuk membatalkan eksekusi upstream dan menghemat resource pemrosesan.
8. **Downstream Delivery**: Envoy memproses respons dari B melalui filter chain kembali ke ingress, lalu meneruskannya ke Client.

---

## 6. Analogy & Diagram ASCII

### Analogi: Gerbang Tol vs Rel Kereta vs Jalan Tol Multi-Jalur

- **HTTP/1.1 (Gerbang Tol Tunggal)**: Satu mobil (request) harus lewat, membayar tol, dan keluar dari pos sebelum mobil berikutnya boleh maju. Jika satu mobil kehilangan dompet (*slow server processing*), seluruh antrean di belakangnya lumpuh.
- **HTTP/2 (Rel Kereta Api - Multiplexing)**: Semua barang dari berbagai pemilik dibungkus dalam kontainer-kontainer terpisah (Frames) dan dimuat ke dalam satu rangkaian kereta panjang (TCP Connection). Sangat efisien, namun jika rel kereta mengalami satu titik patah/longsor (*L4 TCP Packet Loss*), seluruh rangkaian kereta harus berhenti total di tengah jalan hingga rel diperbaiki. Tak ada satu pun kontainer yang bisa sampai tujuan.
- **HTTP/3 QUIC (Jalan Tol Berjalur Banyak / Multi-Lane Motorway)**: Tiap kontainer dimuat ke dalam truk independen berkecepatan tinggi yang bergerak di atas jalan tol tanpa rel (UDP). Jika Truk #3 bannya bocor (*packet loss pada Stream #3*), Truk #1, #2, dan #4 menyalip dari jalur kiri dan kanan tanpa terpengaruh sedikit pun.

```
HTTP/1.1: [Req 1] ───> [Wait Response 1] ───> [Req 2] ───> [Wait Response 2]

HTTP/2:   TCP Connection
          ┌─────────────────────────────────────────────────────────────┐
          │ [Stream 1, Frame A] [Stream 2, Frame A] [Stream 1, Frame B] │
          └─────────────────────────────────────────────────────────────┘
          (Jika Frame A Stream 1 hilang di transit -> Seluruh TCP pipeline freeze)

HTTP/3:   UDP Datagrams (QUIC)
          ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
          │  Stream 1 Frame A  │   │  Stream 2 Frame A  │   │  Stream 1 Frame B  │
          └────────────────────┘   └────────────────────┘   └────────────────────┘
          (Stream 1 loss TIDAK berdampak pada decoding Stream 2)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Connection Pool & TCP KeepAlive di Go
Contoh implementasi HTTP transport layer yang benar untuk mencegah socket leak dan tail latency akibat TCP Handshake ulang terus-menerus.

```go
package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"time"
)

func NewResilientHTTPClient() *http.Client {
	dialer := &net.Dialer{
		Timeout:   2 * time.Second,  // Batas waktu koneksi TCP terbentuk
		KeepAlive: 30 * time.Second, // Interval probe TCP keepalive
	}

	transport := &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           dialer.DialContext,
		ForceAttemptHTTP2:     true, // Mengizinkan multiplexing HTTP/2
		MaxIdleConns:          500,  // Total idle connection pool global
		MaxIdleConnsPerHost:   100,  // CRITICAL: Default Go adalah 2, memicu socket thrashing!
		MaxConnsPerHost:       200,  // Proteksi agar tidak membanjiri target upstream
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   2 * time.Second,
		ExpectContinueTimeout: 1 * time.Second,
		ResponseHeaderTimeout: 3 * time.Second, // Proteksi dari upstream yang menggantung
	}

	return &http.Client{
		Transport: transport,
		Timeout:   5 * time.Second, // End-to-end call timeout budget
	}
}

func main() {
	client := NewResilientHTTPClient()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, "https://httpbin.org/get", nil)
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Request failed: %v\n", err)
		return
	}
	defer resp.Body.Close()

	fmt.Printf("Response Status: %s\n", resp.Status)
}
```

### 7.2 Practical Enterprise Example: Concurrent Hedged Requests Engine di Go
Implementasi *Tail-Tolerance* Hedged Request client yang memanggil replika sekunder jika instance primer tidak merespons dalam durasi tertentu, dengan penanganan context cancellation yang aman untuk mencegah resource leak.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

type HedgedClient struct {
	client     *http.Client
	hedgeDelay time.Duration
}

func NewHedgedClient(client *http.Client, hedgeDelay time.Duration) *HedgedClient {
	return &HedgedClient{
		client:     client,
		hedgeDelay: hedgeDelay,
	}
}

type callResult struct {
	resp *http.Response
	err  error
}

// DoHedged mengeksekusi request ke target URLs secara bertahap (hedging)
func (h *HedgedClient) DoHedged(ctx context.Context, targets []string) (*http.Response, error) {
	if len(targets) == 0 {
		return nil, errors.New("tidak ada upstream target yang tersedia")
	}

	// Channel buffer sesuai jumlah target agar goroutine worker tidak pernah hanging
	resChan := make(chan callResult, len(targets))
	childCtx, cancelChild := context.WithCancel(ctx)
	defer cancelChild()

	var wg sync.WaitGroup

	executeCall := func(url string) {
		defer wg.Done()
		req, err := http.NewRequestWithContext(childCtx, http.MethodGet, url, nil)
		if err != nil {
			select {
			case resChan <- callResult{resp: nil, err: err}:
			case <-childCtx.Done():
			}
			return
		}

		resp, err := h.client.Do(req)
		select {
		case resChan <- callResult{resp: resp, err: err}:
		case <-childCtx.Done():
			if resp != nil {
				resp.Body.Close()
			}
		}
	}

	// 1. Eksekusi Request Pertama
	wg.Add(1)
	go executeCall(targets[0])

	// 2. Setup Hedging Timer
	hedgeTimer := time.NewTimer(h.hedgeDelay)
	defer hedgeTimer.Stop()

	targetIdx := 1
	var firstErr error

	for {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()

		case <-hedgeTimer.C:
			// Jika timer habis dan masih ada upstream lain, jalankan hedged request
			if targetIdx < len(targets) {
				wg.Add(1)
				go executeCall(targets[targetIdx])
				targetIdx++
				hedgeTimer.Reset(h.hedgeDelay)
			}

		case res := <-resChan:
			if res.err == nil && res.resp.StatusCode < 500 {
				// Berhasil mendapatkan respons yang valid!
				// Batalkan request sekunder yang masih berjalan via child context
				cancelChild()
				return res.resp, nil
			}

			// Simpan error pertama jika ada kegagalan
			if firstErr == nil && res.err != nil {
				firstErr = res.err
			}

			// Jika semua target gagal
			targetIdx--
			if targetIdx <= 0 && len(resChan) == 0 {
				if firstErr != nil {
					return nil, fmt.Errorf("semua hedged request gagal, last error: %w", firstErr)
				}
				return nil, errors.New("seluruh downstream mengembalikan status code error (>= 500)")
			}
		}
	}
}

func main() {
	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	hedger := NewHedgedClient(client, 20*time.Millisecond)

	// Simulasi pemanggilan ke 3 endpoint (bisa berupa endpoint di host berbeda atau pod replika)
	endpoints := []string{
		"http://10.0.1.10:8080/api/v1/data", // Lambat (misal terkena GC pause)
		"http://10.0.1.11:8080/api/v1/data", // Cepat
		"http://10.0.1.12:8080/api/v1/data", // Cadangan
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	resp, err := hedger.DoHedged(ctx, endpoints)
	if err != nil {
		fmt.Printf("Gagal: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	fmt.Printf("Sukses menerima respons: %s\n", string(body[:50]))
}
```

### 7.3 Practical Enterprise Example: Konfigurasi Envoy L7 Circuit Breaker & Outlier Detection
Konfigurasi produksi Envoy v3 API untuk proteksi saturasi upstream connection dan degradasi jaringan.

```yaml
static_resources:
  listeners:
  - name: ingress_listener
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 10000
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          codec_type: AUTO
          route_config:
            name: local_route
            virtual_hosts:
            - name: backend_service
              domains: ["*"]
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: payment_backend_cluster
                  timeout: 1.5s
                  hedging:
                    hedge_on_per_try_timeout: true
                  retry_policy:
                    retry_on: "5xx,connect-failure,reset"
                    num_retries: 2
                    per_try_timeout: 400ms
                    retry_back_off:
                      base_interval: 25ms
                      max_interval: 200ms
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: payment_backend_cluster
    connect_timeout: 0.25s
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    http2_protocol_options: {} # Aktifkan HTTP/2 upstream
    load_assignment:
      cluster_name: payment_backend_cluster
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: backend-service.internal
                port_value: 8080
    
    # 1. L7 Circuit Breakers (Threshold proteksi lokal)
    circuit_breakers:
      thresholds:
      - priority: DEFAULT
        max_connections: 1024        # Max TCP connection L4
        max_pending_requests: 100    # Max queue jika connection pool jenuh
        max_requests: 4096           # Max concurrent L7 streams
        max_retries: 3               # Max retry serentak secara cluster-wide

    # 2. Outlier Detection (Ejection instance bermasalah)
    outlier_detection:
      consecutive_5xx: 3             # Keluarkan host jika gagal berturut-turut 3 kali
      interval: 10s                  # Evaluasi tiap 10 detik
      base_ejection_time: 30s        # Durasi isolasi dari LB pool
      max_ejection_percent: 50       # Jangan keluarkan lebih dari 50% armada (mencegah cascading crash)
      enforcing_consecutive_5xx: 100 # 100% enforce logic ini
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Insiden: "The Black Swan Flash Sale Thundering Herd"
- **Entitas**: Platform E-Commerce Pembayaran Terdistribusi (350.000 Transaksi / Detik).
- **Gejala**: Ketika event Flash Sale dimulai pada pukul 00:00, seluruh armada Kubernetes API Gateway (200 Pod) mengalami lonjakan drastis latensi CPU throttling, diiringi error `504 Gateway Timeout` hingga 48%. Sebaliknya, CPU utilization pod payment backend core hanya berada pada kisaran 12%.

### Root Cause Analysis (RCA) Deep Dive:
1. **L4 Socket Exhaustion & Concurrency Bottleneck**:
   Klien internal Go pada Gateway tidak menonaktifkan batas default `DefaultMaxIdleConnsPerHost = 2`. Ketika load melonjak hingga 40.000 RPS per pod Gateway, Go HTTP client secara agresif menutup koneksi TCP yang telah selesai (`close()`), lalu membuka koneksi TCP baru untuk setiap request berikutnya.
2. **Kernel State Collapse**:
   Kernel Linux pada worker node kehabisan alokasi connection tracking (`nf_conntrack`) akibat ratusan ribu socket masuk ke state `TIME_WAIT`. Kernel mulai menolak paket SYN baru secara acak (`kernel: nf_conntrack: table full, dropping packet`).
3. **HTTP/2 HOL Multiplexing Misconfiguration**:
   Beberapa downstream gRPC service dikonfigurasi untuk hanya menggunakan satu koneksi TCP tunggal ke setiap upstream backend pod. Saat jaringan mengalami paket loss sebesar 0.8% akibat kongesti switch ToR (Top-of-Rack), fenomena TCP HoL Blocking membekukan ribuan multiplexed gRPC stream secara serentak, melipatgandakan $p99$ tail latency dari 15ms menjadi 4.8 detik.

```
Grafik Dampak Latensi vs Packet Loss (TCP HTTP/2 vs Multi-Connection/QUIC)
Latensi (ms)
  ^
5000│                                  /─── [HTTP/2 Single TCP Connection - HoL Saturation]
4000│                                 /
3000│                                /
2000│                               /
1000│                              /
 100│───────────/─────────────────/──────── [HTTP/2 Multi-Conn Pool / QUIC]
   0└───────────┴─────────────────┴─────────>
     0%        0.2%             0.8%         Packet Loss Ratio
```

### Remediasi Terpadu SRE:
1. **Penerapan Connection Balancing Pool**: Mengubah konfigurasi client Go gRPC untuk memelihara *sub-channel connection pool* (misal: 8 koneksi TCP independen per endpoint backend) alih-alih koneksi tunggal, memecah saturasi stream per-connection.
2. **Kernel Network Parameter Tuning**: Menerapkan konfigurasi `sysctl` pada cluster node pool:
   ```bash
   sysctl -w net.ipv4.tcp_tw_reuse=1
   sysctl -w net.ipv4.tcp_fin_timeout=15
   sysctl -w net.netfilter.nf_conntrack_max=2097152
   ```
3. **Penerapan Envoy Adaptive Concurrency**: Menggantikan static timeout dengan Envoy Adaptive Concurrency Filter berbasis algoritma MinRTT untuk secara presisi mendeteksi kapasitas antrean downstream tanpa memicu penumpukan connection backlog.

---

## 9. Trade-offs

Setiap keputusan arsitektur jaringan keandalan selalu membawa kompromi sistemik:

| Pendekatan / Fitur | Keuntungan (+)| Konsekuensi Negatif / Kerugian (-) | Mitigasi SRE |
| :--- | :--- | :--- | :--- |
| **Hedged Requests** | Memangkas p99 tail latency hingga 80% pada downstream multi-replica. | Meningkatkan beban komputasi & network traffic upstream secara spekulatif (+15-30% extra QPS). | Berikan trigger hanya pada $p95$ latency threshold dan batasi max hedged quota $\le 5\%$. |
| **Aggressive Connection Reuse (Keep-Alive)** | Mengeliminasi latensi 3-way handshake dan TLS negotiation CPU overhead. | Berisiko memicu ketidakseimbangan beban (*imbalanced load*) pada backend pod saat auto-scaling (koneksi lama terkunci di pod lama). | Terapkan `max_connection_duration` di Envoy/client untuk memaksa *draining* dan rekoneksi berkala. |
| **HTTP/2 Multiplexing** | Menghemat memori kernel (satu socket untuk ribuan request), bebas L7 HoL. | Sangat sensitif terhadap *packet loss* di level transport L4. Satu paket hilang membekukan semua stream. | Gunakan multiple TCP connection per backend atau migrasi ke HTTP/3 (QUIC) pada link dengan loss tinggi. |
| **Circuit Breaking (Aggressive Outlier Detection)** | Melindungi cluster backend dari kegagalan total akibat efek domino cascading failure. | Risiko *false positive*: Host sehat dapat ter-eject jika traffic spike terjadi serentak, mempercepat kehancuran armada tersisa. | Batasi `max_ejection_percent` (maksimal 30-50%) dan gunakan consecutive 5xx error alih-alih persentase instan. |

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: Go `http.DefaultTransport` di Level Produksi
Banyak engineer menggunakan `http.Get()` atau instance `&http.Client{}` tanpa konfigurasi kustom.
- **Masalah**: `DefaultTransport` memiliki `MaxIdleConnsPerHost: 2`. Jika Anda menembakkan 1.000 concurrent request ke satu host upstream, 998 koneksi akan dihancurkan dan dibuat ulang setiap detiknya, memicu lonjakan CPU (TLS Handshake) dan starvation port TCP `TIME_WAIT`.

### Anti-Pattern 2: Infinite Socket Read & Missing Deadlines
Tidak mengonfigurasi `ResponseHeaderTimeout` atau `context.WithTimeout()`.
- **Masalah**: Jika TCP connection di sisi upstream terputus di level kabel atau middlebox (misal: AWS NAT Gateway state timeout setelah 350 detik) tanpa mengirimkan paket `FIN` atau `RST`, client akan menggantung selamanya (*socket leak*), memakan file descriptor hingga mencapai batas `ulimit -n`.

### Toolkit Diagnostik SRE:
Jika terjadi anomali transmisi jaringan di server produksi, jalankan langkah berikut:

```bash
# 1. Cek jumlah socket di tiap state secara instan
ss -s

# 2. Pantau socket buffer drops dan overflow pada kernel
netstat -s | grep -E "buffer errors|overflowed"

# 3. Analisis connection distribution pada specific port (misal: 8080)
ss -tan state established '( dport = :8080 or sport = :8080 )' | wc -l

# 4. Melacak durasi system call epoll_wait yang memblokir Event Loop (via bpftrace)
bpftrace -e '
tracepoint:syscalls:sys_enter_epoll_wait { @start[tid] = nsecs; }
tracepoint:syscalls:sys_exit_epoll_wait /@start[tid]/ {
  @dur_us = hist((nsecs - @start[tid]) / 1000);
  delete(@start[tid]);
}'
```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis microservice ke lingkungan multi-cluster berkapasitas tinggi:

### Kernel Level
- [ ] Ubah default Congestion Control ke BBR: `sysctl -w net.ipv4.tcp_congestion_control=bbr`.
- [ ] Naikkan alokasi SYN backlog: `sysctl -w net.ipv4.tcp_max_syn_backlog=16384`.
- [ ] Naikkan batas pendengar socket: `sysctl -w net.core.somaxconn=16384`.
- [ ] Aktifkan TCP TIME_WAIT recycling: `sysctl -w net.ipv4.tcp_tw_reuse=1`.

### Application / Client Layer
- [ ] Pastikan seluruh HTTP/gRPC call terikat pada `context.Context` dengan deadline eksplisit.
- [ ] Konfigurasi `MaxIdleConnsPerHost` minimum 50-100 per target instance upstream.
- [ ] Implementasikan gRPC KeepAlive Client Parameters:
  - `Time: 20s` (Kirim PING jika tidak ada aktivitas).
  - `Timeout: 5s` (Batas waktu PING ACK diterima sebelum socket dianggap putus).
  - `PermitWithoutStream: true`.
- [ ] Selalu drain dan tutup body response: `io.Copy(io.Discard, resp.Body); resp.Body.Close()`.

### Envoy / Service Mesh Layer
- [ ] Aktifkan L7 Retry Budget (jangan gunakan retry statis tak terbatas).
- [ ] Pasang Outlier Detection dengan batas maksimum pengeluaran node (`max_ejection_percent <= 50%`).
- [ ] Aktifkan rotasi stream koneksi HTTP/2 (`max_concurrent_streams: 100`, `max_requests_per_connection: 10000`).

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun skenario simulasi: Client Go $\to$ Envoy Proxy $\to$ Backend Cluster (2 Node: 1 Sehat, 1 Mengalami Degradasi Injeksi Latensi). Anda akan memverifikasi bagaimana Envoy Outlier Detection dan Retry Policy memitigasi tail latency secara otomatis.

Struktur folder yang akan dibuat:
```
hands-on/m02/
├── docker-compose.yaml
├── envoy.yaml
├── upstream/
│   ├── Dockerfile
│   └── main.go
└── test-client/
    └── client.go
```

### Langkah 1: Buat Direktori Praktikum
```bash
mkdir -p hands-on/m02/upstream hands-on/m02/test-client
cd hands-on/m02
```

### Langkah 2: Kode Upstream Mock Service (`upstream/main.go`)
Service ini dapat disetel untuk memberikan latensi buatan lewat environment variable `CHAOS_DELAY_MS`.

```go
package main

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"
)

func main() {
	instanceName := os.Getenv("INSTANCE_NAME")
	delayMs, _ := strconv.Atoi(os.Getenv("CHAOS_DELAY_MS"))

	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	http.HandleFunc("/api/v1/resource", func(w http.ResponseWriter, r *http.Request) {
		if delayMs > 0 {
			time.Sleep(time.Duration(delayMs) * time.Millisecond)
		}
		w.Header().Set("X-Served-By", instanceName)
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "Response from instance: %s (Injected Delay: %dms)\n", instanceName, delayMs)
	})

	port := ":8080"
	fmt.Printf("[%s] Server running on port %s (Delay: %dms)...\n", instanceName, port, delayMs)
	if err := http.ListenAndServe(port, nil); err != nil {
		panic(err)
	}
}
```

### Langkah 3: Dockerfile Upstream (`upstream/Dockerfile`)
```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -o server main.go

FROM alpine:latest
WORKDIR /root/
COPY --from=builder /app/server .
EXPOSE 8080
CMD ["./server"]
```

### Langkah 4: Konfigurasi Envoy Proxy (`envoy.yaml`)
```yaml
static_resources:
  listeners:
  - name: ingress_listener
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 10000
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          route_config:
            name: local_route
            virtual_hosts:
            - name: backend_vhost
              domains: ["*"]
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: target_cluster
                  timeout: 2s
                  retry_policy:
                    retry_on: "5xx,connect-failure,refused-stream"
                    num_retries: 2
                    per_try_timeout: 100ms # Timeout agresif untuk mitigasi tail latency
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: target_cluster
    connect_timeout: 0.25s
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: target_cluster
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: upstream-healthy
                port_value: 8080
        - endpoint:
            address:
              socket_address:
                address: upstream-degraded
                port_value: 8080
    outlier_detection:
      consecutive_5xx: 3
      interval: 5s
      base_ejection_time: 15s
      max_ejection_percent: 50
```

### Langkah 5: Buat Manifest Docker Compose (`docker-compose.yaml`)
```yaml
version: '3.8'

services:
  envoy:
    image: envoyproxy/envoy:v1.30.1
    volumes:
      - ./envoy.yaml:/etc/envoy/envoy.yaml
    ports:
      - "10000:10000"
      - "9901:9901" # Envoy Admin Interface
    depends_on:
      - upstream-healthy
      - upstream-degraded

  upstream-healthy:
    build:
      context: ./upstream
    environment:
      - INSTANCE_NAME=healthy-node
      - CHAOS_DELAY_MS=5

  upstream-degraded:
    build:
      context: ./upstream
    environment:
      - INSTANCE_NAME=degraded-node
      - CHAOS_DELAY_MS=2000 # Injeksi delay 2 detik (melebihi per_try_timeout 100ms)
```

### Langkah 6: Kode Client Pengetes Load (`test-client/client.go`)
```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

func main() {
	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	totalRequests := 50
	var wg sync.WaitGroup
	wg.Add(totalRequests)

	start := time.Now()

	for i := 0; i < totalRequests; i++ {
		go func(id int) {
			defer wg.Done()
			reqStart := time.Now()
			resp, err := client.Get("http://localhost:10000/api/v1/resource")
			duration := time.Since(reqStart)

			if err != nil {
				fmt.Printf("[Req #%d] ERROR: %v (took %v)\n", id, err, duration)
				return
			}
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()

			fmt.Printf("[Req #%d] Status: %d | Time: %v | Node: %s", id, resp.StatusCode, duration, string(body))
		}(i)
		time.Sleep(50 * time.Millisecond) // Staggered incoming requests
	}

	wg.Wait()
	fmt.Printf("\nSemua request selesai dalam: %v\n", time.Since(start))
}
```

### Langkah 7: Eksekusi dan Verifikasi
1. Jalankan cluster menggunakan Docker Compose:
   ```bash
   docker-compose up --build -d
   ```
2. Jalankan test client untuk melihat Envoy memotong latency degraded node:
   ```bash
   cd test-client
   go run client.go
   ```
3. Amati log: Request yang dialihkan ke `upstream-degraded` akan dipotong otomatis setelah `100ms` oleh konfigurasi `per_try_timeout`, lalu di-retry secara instan ke `upstream-healthy`. Klien tidak pernah menunggu selama 2000ms.
4. Buka admin panel Envoy di `http://localhost:9901/stats` dan cari metrik retry:
   ```bash
   curl -s http://localhost:9901/stats | grep "retry"
   ```

---

## 13. Exercise

### Level Easy
Modifikasi file `test-client/client.go` untuk menghitung $p50$, $p90$, dan $p99$ end-to-end latency secara manual dari 100 eksekusi request dan cetak statistiknya ke terminal.

### Level Medium
Perbarui `envoy.yaml` untuk menambahkan konfigurasi **Adaptive Concurrency Limit (ACL)** filter. Simulasikan beban traffic menggunakan tool load generator (`hey` atau `k6`) dan tunjukkan metrik Envoy yang merefleksikan penolakan traffic secara preventif saat latensi mulai meningkat.

### Level Hard
Buat program Go berstandar produksi yang mengimplementasikan **Gradient Concurrency Limit** algorithm (berbasis model Netflix Concurrency Limits). Program harus:
1. Menghitung `inflight_requests`.
2. Mengukur latensi rata-rata jangka pendek ($RTT_{\text{current}}$) dibandingkan dengan baseline moving minimum ($RTT_{\text{min}}$).
3. Secara dinamis menyusutkan kapasitas limit request jika $RTT_{\text{current}} / RTT_{\text{min}} > 1.1$, dan mengekspos metrik Prometheus gauge `current_limit_capacity`.

---

## 14. Challenge

### Studi Kasus: "The Cross-Region Intermittent Blackhole"
Anda adalah Principal SRE pada sistem core banking global. Terdapat cluster API Kubernetes di Region `us-east-1` yang berkomunikasi via Dedicated Cloud Interconnect (Private WAN) ke Region `eu-central-1`. 

**Kondisi Gangguan:**
- Pada interval acak setiap 15-45 menit, terjadi packet loss transien sebesar 3% selama durasi 60 detik di jalur backbone antar-benua tersebut.
- Latensi baseline normal $RTT = 85\text{ ms}$. Namun saat packet loss terjadi, koneksi gRPC (HTTP/2) mengalami $p99$ latency spike hingga 12 detik, memicu penumpukan antrean message broker dan kegagalan massal otentikasi transaksi.
- Anda tidak diizinkan menduplikasi database cross-region karena batasan regulasi kedaulatan data (Data Sovereignty/GDPR).

**Tantangan Arsitektur Anda:**
1. Rancang arsitektur jaringan L4/L7 toleran kegagalan lengkap yang mengeliminasi spike latensi tanpa merusak konsistensi data.
2. Jelaskan konfigurasi transport apa yang harus diterapkan pada kernel OS, proxy mesh (Envoy), dan application SDK layer.
3. Berikan justifikasi teknis apakah sistem harus beralih ke HTTP/3 (QUIC-based mesh), Hedging Multi-Pathing, atau Dynamic TCP Window Shrinking, beserta analisis mendalam risiko trade-off konsumsi CPU/bandwith-nya.

*(Dokumentasikan rencana mitigasi Anda dalam bentuk proposal desain arsitektur teknis tertulis lengkap tanpa solusi instan)*.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic

1. **Apa perbedaan mendasar antara HTTP/2 Head-of-Line (HoL) Blocking dan HTTP/1.1 HoL Blocking?**
   - *Jawaban*: HTTP/1.1 mengalami HoL blocking di Layer 7 (aplikasi), di mana satu transaksi request/response memblokir antrean request berikutnya pada koneksi TCP yang sama. HTTP/2 mengeliminasi L7 HoL via multiplexing frame pada stream terpisah, namun memperkenalkan L4 HoL blocking di level TCP: jika satu paket TCP hilang, seluruh HTTP/2 stream pada koneksi tersebut dibekukan oleh kernel TCP receive buffer sampai retransmisi berhasil.

2. **Mengapa pengaturan `MaxIdleConnsPerHost` default pada Go HTTP Client (`DefaultMaxIdleConnsPerHost = 2`) berbahaya bagi microservice dengan beban tinggi?**
   - *Jawaban*: Nilai default `2` berarti client hanya menyimpan maksimal 2 koneksi idle per host upstream. Jika terdapat beban paralel besar (misal 500 RPS), Go akan secara konstan membuka socket baru dan menghancurkan socket yang selesai dipakai, memicu TCP handshake overhead berulang-ulang, saturasi port, dan TIME_WAIT connection table exhaustion pada kernel.

3. **Bagaimana HTTP/3 (QUIC) mengeliminasi fenomena Transport-layer HoL Blocking?**
   - *Jawaban*: QUIC berjalan di atas UDP dan mengimplementasikan nomor urut paket, kontrol kongesti, dan mekanisme loss recovery di tingkat userspace per-stream. Kehilangan paket UDP pada Stream X hanya menunda pembacaan Stream X, sementara Stream Y dan Z terus diproses tanpa interupsi.

4. **Apa fungsi dari sistem call `epoll_wait` dalam arsitektur I/O non-blocking Linux seperti Envoy?**
   - *Jawaban*: `epoll_wait` memantau sekumpulan file descriptor (socket) secara efisien dengan kompleksitas $O(1)$ untuk mendeteksi event I/O (seperti data masuk atau socket siap ditulis). Thread tidak perlu melakukan busy-polling; thread tertidur hingga kernel membangunkannya hanya ketika ada event aktif.

5. **Apa yang diindikasikan oleh state koneksi TCP `CLOSE_WAIT` yang tinggi pada server backend?**
   - *Jawaban*: Menandakan bahwa sisi remote (klien) telah mengirimkan paket `FIN` untuk menutup koneksi, dan kernel server telah membalas dengan `ACK`, namun proses/aplikasi di server lokal belum memanggil `close()` pada file descriptor socket tersebut (indikasi aplikasi macet atau resource leak).

---

### 15.2 Pertanyaan Intermediate

1. **Jelaskan secara matematis mengapa fan-out panggilan service terdistribusi memperparah latensi tail ($p99$) secara dramatis!**
   - *Jawaban*: Jika sebuah request bergantung pada $N$ pemanggilan microservice secara paralel yang masing-masing memiliki probabilitas $p$ untuk berada di bawah ambang latensi yang ditargetkan, maka probabilitas bahwa *seluruh* $N$ panggilan sukses tanpa satupun yang terlambat adalah $p^N$. Peluang terjadinya minimal satu panggilan lambat (tail latency amplification) adalah $1 - p^N$. Ketika $N=100$ dan $p=0.99$, peluang mengalami latensi lambat melonjak drastis menjadi $1 - (0.99)^{100} \approx 63.4\%$.

2. **Mengapa algoritma TCP BBR (Bottleneck Bandwidth and RTT) umumnya memberikan performa latensi yang jauh lebih stabil dibandingkan TCP CUBIC pada jaringan cloud modern?**
   - *Jawaban*: TCP CUBIC adalah algoritma berbasis *loss-based congestion control* yang sengaja membanjiri antrean paket hingga terjadi *packet drop* (*bufferbloat*) untuk mendeteksi kapasitas rute. Sebaliknya, BBR adalah algoritma berbasis *model-based congestion control* yang terus-menerus mengukur bandwidth pengiriman maksimum dan RTT minimum secara riil, membatasi inflight data tepat pada kapasitas pipa tanpa sengaja mengisi penuh buffer router, sehingga meminimalkan antrean dan latensi tail.

3. **Bagaimana mekanisme *Hedged Requests* bekerja, dan mengapa harus dibatasi kuotanya secara ketat?**
   - *Jawaban*: Hedged requests mendeteksi jika sebuah panggilan RPC membutuhkan waktu lebih lama dari batas waktu tertentu (misal $p95$), lalu memicu request kedua yang identik ke instance backend yang berbeda secara konkuren. Respons yang kembali lebih dulu digunakan dan yang terlambat dibatalkan. Kuotanya harus dibatasi ketat (misal maks 5% dari total traffic) karena jika seluruh sistem sedang kelebihan beban (*overloaded*), melipatgandakan request secara spekulatif akan memicu badai traffic sekunder yang dapat meruntuhkan seluruh armada backend secara total.

4. **Apa implikasi penggunaan Linux kernel parameter `net.ipv4.tcp_tw_reuse = 1` dalam arsitektur microservices?**
   - *Jawaban*: Parameter ini mengizinkan kernel untuk menggunakan kembali socket yang berada dalam state `TIME_WAIT` untuk koneksi keluar (*outgoing connections*) baru jika waktu timestamp TCP aman secara matematis (`TCP Timestamps` aktif). Ini mencegah kehabisan local ephemeral port range ketika service bertindak sebagai client yang melakukan ribuan outbound RPC/detik ke upstream.

5. **Dalam Envoy Proxy, apa perbedaan mekanisme proteksi antara *Circuit Breaking* (`max_connections`, `max_pending_requests`) dan *Outlier Detection*?**
   - *Jawaban*: *Circuit Breaking* bersifat reaktif-struktural lokal terhadap volume traffic: membatasi batas absolut konkurensi koneksi atau antrean pending request agar worker proxy tidak kehabisan memori. Sedangkan *Outlier Detection* bersifat kualitatif-dinamis: memantau rasio error (seperti 5xx berturut-turut atau connection refusal) dari masing-masing node backend dan secara otomatis mengekstrak (mengisolasi) instance yang sakit dari daftar load balancing pool cluster.

---

### 15.3 Skenario Kasus Produksi

1. **Skenario 1**: Setelah migrasi cluster microservice dari AWS ke Bare-Metal Private Kubernetes, metrik menunjukkan latensi antarservice stabil pada throughput rendah. Namun ketika throughput dinaikkan ke level produksi, terjadi ribuan log error `connection reset by peer` instan di sisi Envoy, sementara CPU dan memori backend masih berada di bawah 25%. Metrik OS menunjukkan nilai drop count pada queue listening socket naik tajam. Apa akar masalahnya dan bagaimana memperbaikinya?
   - *Solusi & Analisis*: 
     Akar masalahnya adalah ukuran backlog queue TCP kernel yang terlalu kecil di tingkat node bare-metal (sering kali default `net.core.somaxconn` dan `net.ipv4.tcp_max_syn_backlog` bernilai 128 atau 4096). Ketika gelombang koneksi masuk serentak (*SYN burst*), antrean socket listen penuh (*accept queue overflow*), memaksa kernel menolak koneksi dengan mengirimkan TCP RST.
     **Langkah Remediasi**:
     1. Naikkan buffer backlog OS di semua node:
        ```bash
        sysctl -w net.core.somaxconn=16384
        sysctl -w net.ipv4.tcp_max_syn_backlog=16384
        ```
     2. Pastikan konfigurasi aplikasi backend/Envoy listener mengalokasikan parameter listen backlog yang sesuai (misal: setting `backlog = 16384` pada syscall `listen(fd, backlog)`).

2. **Skenario 2**: Anda mengamati bahwa pod Gateway Envoy yang melayani traffic eksternal menggunakan 100% dari 4 Core CPU yang dialokasikan, namun throughput jaringan sangat rendah (kurang dari 2.000 RPS). Setelah dieksplorasi via thread dump, worker threads Envoy menghabiskan 85% waktunya di crypto routine OpenSSL handshake. Klien eksternal didominasi oleh perangkat IoT yang menggunakan koneksi non-keep-alive (HTTP/1.0 atau HTTP/1.1 tanpa `Connection: keep-alive`). Bagaimana strategi mitigasi arsitektur Anda tanpa memaksa jutaan perangkat IoT untuk update firmware?
   - *Solusi & Analisis*:
     Perangkat IoT membuka koneksi TCP baru dan melakukan proses negosiasi TLS handshake lengkap (*Full TLS Handshake*) yang sangat mahal secara komputasi CPU untuk setiap pengiriman data tunggal.
     **Langkah Remediasi**:
     1. **Aktifkan TLS Session Resumption**: Konfigurasikan TLS Session Tickets (RFC 5077) dan TLS Session IDs pada Envoy listener. Ini memungkinkan client melakukan handshake singkat (*abbreviated handshake* 1-RTT) tanpa kalkulasi asymmetric key exchange kriptografi yang berat:
        ```yaml
        tls_context:
          common_tls_context:
            session_ticket_keys:
              # Rotasi keys secara dinamis
        ```
     2. **Edge TLS Termination Architecture**: Pasang L4 proxy atau Cloud Edge (seperti Cloudflare/AWS CloudFront) di depan Envoy untuk memutus TCP/TLS handshake dekat dengan perimeter klien, dan lakukan connection multiplexing/pooling dari Edge ke armada Envoy internal.

3. **Skenario 3**: Sebuah upstream payment gateway mengekspos endpoint via domain DNS dinamis yang instance IP-nya berubah secara teratur setiap 5 menit (menggunakan DNS multi-record dinamis). Go application client Anda menggunakan connection pool HTTP default. Selama periode rotasi IP oleh vendor, aplikasi Anda terus mengirimkan traffic ke IP lama yang sudah dimatikan sehingga memicu lonjakan error `I/O timeout` selama 30 menit, meskipun verifikasi via `nslookup` dari shell server menunjukkan bahwa DNS record sudah diperbarui ke IP baru. Mengapa Go client gagal meresolusi IP baru dan bagaimana memperbaikinya?
   - *Solusi & Analisis*:
     Go `http.Transport` secara default menggunakan koneksi TCP yang ada di connection pool selama koneksi tersebut dianggap idle dan belum ditutup oleh server (`KeepAlive`). Go HTTP Client tidak melakukan re-resolusi DNS selama koneksi TCP yang ada masih hidup dalam pool (*DNS pinning to existing connections*). Meskipun record DNS berubah, client terus memompa traffic melalui socket lama yang terbuka sampai koneksi tersebut drop secara kasar oleh firewall vendor.
     **Langkah Remediasi**:
     1. Konfigurasi `MaxIdleConnDuration` atau batasi umur hidup maksimum koneksi pada client transport agar pool secara teratur melakukan rotasi:
        ```go
        transport := &http.Transport{
            IdleConnTimeout: 30 * time.Second,
            // Bungkus DialContext dengan Custom Resolver yang menghormati DNS TTL
        }
        ```
     2. Delegasikan resolusi L7 upstream ke sidecar proxy seperti Envoy menggunakan cluster type `STRICT_DNS` atau `LOGICAL_DNS` dengan parameter `dns_refresh_rate: 15s`. Envoy akan memperbarui pool IP secara asinkron tanpa memutus aliran data yang sedang berjalan.

---

## 16. Summary

1. **Jaringan Terdistribusi Selalu Tidak Deterministik**: Keandalan L4 hingga L7 tidak bisa diasumsikan secara pasif. Latensi jaringan berekor panjang (*tail latency*) diperkuat secara eksponensial oleh kedalaman pemanggilan service (*fan-out factor*).
2. **Karakteristik Protokol Sangat Menentukan**: HTTP/1.1 terhambat oleh L7 HoL blocking; HTTP/2 memecahkan L7 HoL tetapi rentan terhadap L4 HoL akibat hilangnya paket TCP; HTTP/3 (QUIC) memindahkan state mesin reliabilitas ke userspace di atas UDP, menyediakan isolasi stream independen.
3. **Pola Keandalan L7 Adalah Keharusan**: Penggunaan *Hedged Requests*, *Dynamic Connection Pooling*, *Adaptive Concurrency*, dan *Active Outlier Detection* wajib dirancang sejak awal arsitektur dibuat untuk mencegah fenomena *cascading collapse*.
4. **Penyelarasan Kernel dan Aplikasi**: Keandalan sistem mikroservice skala enterprise membutuhkan harmoni konfigurasi dari *kernel socket buffers* (`somaxconn`, `tcp_tw_reuse`, Congestion BBR), *proxy threading engine* (Envoy libevent/worker-per-core), hingga *language runtime networking stack* (Go Netpoller dan Transport tuning).