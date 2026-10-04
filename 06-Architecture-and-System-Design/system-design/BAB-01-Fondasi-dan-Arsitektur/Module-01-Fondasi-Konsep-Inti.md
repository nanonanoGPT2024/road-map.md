# Bab 01: Fondasi Desain Sistem & Karakteristik Arsitektur Skala Besar
## Module 01: Skalabilitas, Ketersediaan (High Availability), dan Karakteristik Performa (Latency & Throughput)

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** metrik performa sistem terdistribusi melalui dekonstruksi kuantitatif antara *throughput* (RPS/QPS) dan distribusi *latency* (*percentiles* p50, p95, p99, p99.9).
- **Merancang** strategi skalabilitas elastis (*vertical scaling* vs. *horizontal scaling*) dengan memperhitungkan batasan *Amdahl’s Law* dan *Universal Scalability Law* (USL).
- **Mengevaluasi** metrik *High Availability* (HA) menggunakan pemodelan ketersediaan matematis (*nines of availability*, MTBF, MTTR) dan mengidentifikasi *Single Point of Failure* (SPOF).
- **Mengimplementasikan** mekanisme penyeimbang beban (*Load Balancer*) sederhana berbasis Go yang thread-safe dengan *active health-checking* dan pelacakan metrik latency.
- **Mengidentifikasi** *tail latency amplification* pada sistem berbasis *microservices* dan merumuskan mitigasi berbasis *hedged requests* dan *timeout budgets*.

---

### 2. Introduction & Conceptual Hook
Bayangkan sistem pembayaran jalan tol. Jika Anda menambah gardu tol dari 2 menjadi 20 tanpa memperlebar jalan raya sebelum dan sesudah gardu tersebut, Anda tidak menyelesaikan kemacetan; Anda hanya memindahkan titik kemacetan (*bottleneck*) beberapa ratus meter ke depan.

Dalam rekayasa perangkat lunak skala masif, analogi ini merefleksikan kegagalan pemahaman mendasar atas sistem terdistribusi. Pada tahun 2012, saat peluncuran platform perawatan kesehatan federal AS (Healthcare.gov), sistem mengalami kolaps fatal bukan karena basis datanya tidak mampu menyimpan data pengguna, melainkan karena arsitekturnya mengasumsikan transaksi synchronous monolitik bertingkat tinggi dengan dependensi berantai tanpa isolasi kegagalan (*fault isolation*). Lonjakan trafik awal sebesar 250.000 pengguna bersamaan (*concurrent users*) mengekspos *resource contention* di mana waktu respons meningkat secara eksponensial hingga ribuan *thread worker* mengalami *starvation*. Modul ini membedah fondasi mekanis sistem: bagaimana sistem menerima, mengolah, dan mentoleransi beban kerja ekstrem tanpa degradasi katastropik.

---

### 3. Why It Matters
Dalam arsitektur *production-grade*, kegagalan dalam mendesain untuk skala dan ketersediaan berdampak langsung secara finansial dan reputasional:
- **Dampak Finansial Downtime:** Bagi platform e-commerce seperti Amazon, downtime bernilai jutaan dolar per menit. *Service Level Agreement* (SLA) 99.9% ("three nines") mengizinkan downtime hingga 8.76 jam per tahun, sementara SLA 99.999% ("five nines") hanya mentolerir 5.26 menit per tahun. Transisi antar tingkat ketersediaan ini membutuhkan perombakan radikal dari redundansi aktif-pasif menjadi arsitektur multi-wilayah aktif-aktif (*active-active multi-region*).
- **Tail Latency Amplification:** Dalam arsitektur microservices modern, pemanggilan satu API publik dapat memicu 100 sub-panggilan RPC paralel ke berbagai *backend microservices*. Jika p99 latency setiap sub-layanan adalah 10 milidetik, kemungkinan pengguna mengalami keterlambatan keseluruhan melonjak secara probabilistik ($1 - 0.99^{100} = 63.4\%$). Tanpa pemahaman p99/p99.9, lebih dari setengah basis pengguna Anda akan merasakan performa sistem yang lambat meskipun metrik rata-rata (*mean*) terlihat normal.

---

### 4. Core Concept & Mental Model
Desain sistem beroperasi di atas hubungan tarik-ulur (*trade-offs*) yang diatur oleh hukum fisik dan matematis komputasi.

```
                    ┌─────────────────────────┐
                    │ Beban Masuk (Offered    │
                    │ Load: Throughput (RPS)) │
                    └────────────┬────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │     Kapasitas &       │
                     │ Concurrency Limit (C) │
                     └───────────┬───────────┘
                                 │
        ┌────────────────────────┴────────────────────────┐
        ▼                                                 ▼
[Load <= Capacity]                                [Load > Capacity]
- Queue Size: Konstan/Nol                         - Queue Size: Eksponensial (Little's Law)
- Latency: Datar (Processing Time)                - Latency: Skyrocketing (Queuing Delay)
- Throughput: Linear naik                         - Throughput: Runtuh (Contention/Thrashing)
```

#### Throughput vs. Latency
- **Latency:** Waktu yang dibutuhkan suatu request untuk menempuh perjalanan bolak-balik (Round Trip Time - RTT) ditambah waktu eksekusi server.
- **Throughput:** Jumlah unit kerja (request, byte, transaksi) yang dapat diproses sistem per satuan waktu (contoh: Requests Per Second / RPS).
- **Hukum Little (Little’s Law):** 
  $$L = \lambda \times W$$
  Di mana $L$ adalah jumlah rata-rata request di dalam sistem (*concurrency/queue depth*), $\lambda$ adalah throughput kedatangan request, dan $W$ adalah rata-rata latency per request. Ketika server mencapai batas konkurensinya ($L_{max}$), setiap kenaikan $\lambda$ secara matematis memaksa $W$ (latency) meningkat melalui antrean (*queuing delay*).

#### Skalabilitas: USL (Universal Scalability Law)
Skalabilitas horizontal dibatasi bukan hanya oleh paralelisasi (Amdahl's Law), melainkan oleh *contention* dan *coherency delay*:
$$C(N) = \frac{N}{1 + \alpha(N - 1) + \beta N(N - 1)}$$
- $N$: Jumlah node/pekerja.
- $\alpha$: Parameter konkurensi/serialisasi (antrean resource bersama seperti lock database).
- $\beta$: Parameter koherensi (overhead komunikasi antar-node untuk menjaga konsistensi state).
- Jika $\beta > 0$, penambahan node di atas ambang tertentu justru akan **menurunkan** throughput keseluruhan (retrograde scalability).

---

### 5. Deep-Dive Architecture & Component Breakdown

```
[Klien Eksternal]
       │
       ▼ (HTTPS / DNS Anycast)
[Global Load Balancer / Geo-DNS]
       │
       ▼
[Edge Layer: CDN & DDoS Protection / Reverse Proxy]
       │
       ▼ (mTLS)
[Regional L7 Load Balancer (Envoy / NGINX)]
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[Stateless App Node 1]          [Stateless App Node 2]
  - Concurrency Pool (Workers)    - Concurrency Pool (Workers)
  - Circuit Breakers              - Circuit Breakers
       │                                 │
       └────────────────┬────────────────┘
                        │
                        ▼ (gRPC / Connection Pooling)
               [Internal L4 LB]
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
[Data Cache Layer (Redis)]     [Primary Distributed Storage]
(Read Throughput Accelerator)  (Write Primary & Read Replicas)
```

#### Komponen Utama:
1. **Edge/Reverse Proxy (L7):** Memutus koneksi TCP dari klien (TCP termination), memvalidasi sertifikat TLS, dan melakukan *rate limiting* awal untuk mencegah *resource exhaustion*.
2. **Dynamic Stateless Worker Nodes:** Menjalankan logika bisnis murni tanpa menyimpan state sesi di memori lokal. Skalabilitas horizontal dapat dicapai dengan menambah/mengurangi container di balik *load balancer*.
3. **Connection Pooling & L4 Load Balancers:** Mempertahankan koneksi TCP *keep-alive* ke subsistem internal untuk mengeliminasi latensi *3-way handshake* pada setiap transaksi.
4. **Data Partitioning Tier:** Memisahkan data path untuk beban baca (*Read-heavy via Cache*) dan tulis (*Write-heavy via Sharded DB*), mencegah tabrakan I/O pada disk storage.

---

### 6. Visual Architecture / ASCII Diagram
Berikut adalah diagram alur siklus hidup request dari kedatangan paket hingga eksekusi backend, mengilustrasikan transisi latensi:

```
CLIENT                REVERSE PROXY           APP WORKER             DATABASE
  │                         │                     │                     │
  │─── 1. SYN (RTT 1) ────>│                     │                     │
  │<── 2. SYN-ACK ─────────│                     │                     │
  │─── 3. ACK + TLS Hello ─>│                     │                     │
  │<── 4. TLS Handshake ───│                     │                     │
  │                         │                     │                     │
  │─── 5. HTTP GET /data ──>│                     │                     │
  │    (Latency Network)    │── 6. Reuse Conn ───>│                     │
  │                         │   (Keep-Alive TCP)  │                     │
  │                         │                     │── 7. Query Cache ──>│
  │                         │                     │<── Cache Miss ──────│
  │                         │                     │                     │
  │                         │                     │── 8. Query Disk ───>│
  │                         │                     │<── Data Engine ─────│
  │                         │<── 9. JSON Stream ──│                     │
  │<── 10. HTTP 200 OK ─────│                     │                     │
  │    (P99 Spike Risk!)    │                     │                     │
```

---

### 7. Step-by-Step Implementation Guide
Untuk mendemonstrasikan fondasi penyeimbangan beban (*load balancing*) dan pelacakan metrik ketersediaan (*availability*), kita akan membangun *Layer 7 Load Balancer* berbasis Go yang mengimplementasikan:
1. Algoritma Round-Robin dinamis.
2. Background Active Health Checking untuk mendeteksi *node failure* dan mencegah degradasi ketersediaan.
3. Thread-safe Mutex locks untuk menangani *race condition* pada pembaruan status backend.
4. Metrik latensi request menggunakan rolling latency buffer sederhana.

---

### 8. Production Code Example

```go
// main.go
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"sync"
	"sync/atomic"
	"time"
)

// Backend merepresentasikan server aplikasi di downstream layer
type Backend struct {
	URL          *url.URL
	Alive        bool
	mux          sync.RWMutex
	ReverseProxy *httputil.ReverseProxy
	TotalLatency int64 // Akumulasi latensi dalam nanodetik (Atomic)
	RequestCount int64 // Jumlah request yang sukses (Atomic)
}

func (b *Backend) SetAlive(alive bool) {
	b.mux.Lock()
	defer b.mux.Unlock()
	b.Alive = alive
}

func (b *Backend) IsAlive() bool {
	b.mux.RLock()
	defer b.mux.RUnlock()
	return b.Alive
}

func (b *Backend) RecordMetrics(latency time.Duration) {
	atomic.AddInt64(&b.TotalLatency, int64(latency))
	atomic.AddInt64(&b.RequestCount, 1)
}

func (b *Backend) GetAverageLatencyMs() float64 {
	count := atomic.LoadInt64(&b.RequestCount)
	if count == 0 {
		return 0
	}
	total := atomic.LoadInt64(&b.TotalLatency)
	return (float64(total) / float64(count)) / float64(time.Millisecond)
}

// ServerPool mengelola daftar seluruh backend target
type ServerPool struct {
	backends []*Backend
	current  uint64
}

func (s *ServerPool) AddBackend(b *Backend) {
	s.backends = append(s.backends, b)
}

// NextIndex melakukan increment atomik berbasis modulo untuk Round-Robin
func (s *ServerPool) NextIndex() int {
	return int(atomic.AddUint64(&s.current, uint64(1)) % uint64(len(s.backends)))
}

// GetNextPeer memilih backend berikutnya yang berstatus Alive
func (s *ServerPool) GetNextPeer() *Backend {
	loop := len(s.backends)
	for i := 0; i < loop; i++ {
		idx := s.NextIndex()
		if s.backends[idx].IsAlive() {
			return s.backends[idx]
		}
	}
	return nil
}

// HealthCheck memindai seluruh node backend secara berkala
func (s *ServerPool) HealthCheck(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			for _, b := range s.backends {
				go func(backend *Backend) {
					pingURL := fmt.Sprintf("%s/healthz", backend.URL.String())
					client := http.Client{Timeout: 2 * time.Second}
					resp, err := client.Get(pingURL)
					alive := err == nil && resp.StatusCode == http.StatusOK
					backend.SetAlive(alive)
					if resp != nil {
						_ = resp.Body.Close()
					}
				}(b)
			}
		}
	}
}

func main() {
	rawServers := []string{
		"http://127.0.0.1:8081",
		"http://127.0.0.1:8082",
		"http://127.0.0.1:8083",
	}

	serverPool := &ServerPool{}

	for _, raw := range rawServers {
		parsedURL, err := url.Parse(raw)
		if err != nil {
			log.Fatalf("URL Backend tidak valid: %v", err)
		}

		proxy := httputil.NewSingleHostReverseProxy(parsedURL)
		
		// Custom Director/Transport untuk pelacakan performa
		backend := &Backend{
			URL:          parsedURL,
			Alive:        true,
			ReverseProxy: proxy,
		}

		originalDirector := proxy.Director
		proxy.Director = func(req *http.Request) {
			originalDirector(req)
			req.Header.Set("X-Forwarded-By", "Go-System-Design-LB")
		}

		serverPool.AddBackend(backend)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go serverPool.HealthCheck(ctx, 5*time.Second)

	frontendHandler := func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		peer := serverPool.GetNextPeer()
		if peer == nil {
			http.Error(w, "Service Unavailable: Tidak ada backend yang aktif", http.StatusServiceUnavailable)
			return
		}

		// Delegasikan pemrosesan ke reverse proxy target
		peer.ReverseProxy.ServeHTTP(w, r)

		duration := time.Since(start)
		peer.RecordMetrics(duration)
		
		log.Printf("[METRICS] Target: %s | Latency: %v | Avg Backend Latency: %.2fms",
			peer.URL.Host, duration, peer.GetAverageLatencyMs())
	}

	server := http.Server{
		Addr:    ":8080",
		Handler: http.HandlerFunc(frontendHandler),
	}

	log.Println("Edge Load Balancer aktif di port :8080...")
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("Server shutdown: %v", err)
	}
}
```

---

### 9. Practical Edge Cases & Failure Modes
Pada implementasi skalabilitas dan throughput tinggi di lingkungan produksi:
1. **Thundering Herd Problem (Cache Invalidation):** Ketika sebuah kunci cache terdistribusi (misal: Redis) kadaluwarsa pada detik yang sama dengan datangnya 10.000 RPS, seluruh worker akan secara bersamaan menembus database primer. *Mitigasi:* Implementasikan *mutex locks* pada worker cache retrieval (*singleflight pattern*) atau berikan *TTL jitter* (randomisasi waktu expirasi 5-10%).
2. **Tail Latency Amplification:** Jika request klien bergantung pada 10 backend parallel workers, server yang mengalami *Garbage Collection pause* (stop-the-world) akan memperlambat response total. *Mitigasi:* Gunakan pola *Hedged Requests* (kirim request kedua ke replika cadangan jika respon belum diterima dalam rentang p95 time).
3. **Cascading Failure akibat Health Check Aggressive:** Jika sistem kelebihan beban dan respons time memanjang, *active health check* dapat mengalami timeout palsu. LB akan menandai worker sehat sebagai 'mati', memotong kapasitas klaster, melimpahkan beban ke worker yang tersisa, dan merobohkan seluruh klaster secara beruntun (*thundering herd collapse*).

---

### 10. Verification & Testing

Gunakan testing script berikut untuk menguji performa load balancing dan mekanisme failover secara deterministik.

```go
// lb_test.go
package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"
)

func TestServerPool_Failover(t *testing.T) {
	// 1. Setup Backend Mock 1 (Sehat)
	mockBackendHealthy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer mockBackendHealthy.Close()

	// 2. Setup Backend Mock 2 (Gagal)
	mockBackendDead := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer mockBackendDead.Close()

	u1, _ := url.Parse(mockBackendHealthy.URL)
	u2, _ := url.Parse(mockBackendDead.URL)

	b1 := &Backend{URL: u1, Alive: true}
	b2 := &Backend{URL: u2, Alive: false} // Diinisiasi sebagai dead

	pool := &ServerPool{}
	pool.AddBackend(b1)
	pool.AddBackend(b2)

	// Pastikan peer berikutnya SELALU b1 karena b2 mati
	for i := 0; i < 5; i++ {
		peer := pool.GetNextPeer()
		if peer == nil || peer.URL.String() != b1.URL.String() {
			t.Fatalf("Ekspektasi backend %s, tetapi mendapatkan %v", b1.URL.String(), peer)
		}
	}
}

func BenchmarkServerPool_NextIndex(b *testing.B) {
	pool := &ServerPool{
		backends: make([]*Backend, 16),
	}
	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = pool.NextIndex()
		}
	})
}
```

Eksekusi verifikasi via terminal:
```bash
go test -v -race -run TestServerPool_Failover
go test -bench=BenchmarkServerPool_NextIndex -benchmem
```

---

### 11. Trade-off Analysis & Engineering Decisions

| Strategi Skalabilitas | Kompleksitas Arsitektural | Batasan Maksimal Fisik / USL | Biaya Finansial Overhead | Toleransi Kegagalan (HA) |
| :--- | :--- | :--- | :--- | :--- |
| **Vertical Scaling (Scale-Up)** | Sangat Rendah (Monolitik, zero distributed sync) | Dibatasi batas hardware (CPU cores, RAM bus width, motherboard limit) | Eksponensial (Server kelas enterprise high-end sangat mahal) | Buruk (Tunggal; Hardware failure = Total Downtime / SPOF) |
| **Horizontal Scaling (Scale-Out)** | Tinggi (Butuh LB, Service Discovery, State Externalization) | Dibatasi oleh hukum USL ($\beta$-coherency & $\alpha$-contention) | Linear (Bisa memanfaatkan komoditas node murah / spot instances) | Sangat Tinggi (Satu node mati, traffic dialihkan secara dinamis) |
| **Active-Passive Redundancy** | Menengah (Membutuhkan heartbeat & mekanisme virtual IP/failover) | Identik dengan 1 node kapasitas aktif | 100% idle capacity waste pada node cadangan | Menengah (Ada *failover lag* beberapa detik saat transisi) |
| **Active-Active Redundancy** | Sangat Tinggi (Konsistensi data terdistribusi multi-leader/Paxos/Raft) | Skala kapasitas kumulatif dari seluruh node | Maksimal (utilisasi resource 100% efisien) | Superior (Zero downtime saat degradasi salah satu node) |

---

### 12. Anti-patterns & Common Pitfalls

#### Anti-Pattern: Blocking In-Memory State pada Horizontally Scaled Node
Menyimpan data sesi pengguna di memori lokal (*in-memory sticky session*) pada server aplikasi web. Jika node mati, sesi pengguna musnah. Jika load balancer menggunakan algoritma Round-Robin standar, request berikutnya akan terlempar ke server berbeda dan memicu error autentikasi.

#### Perbaikan Arsitektur (State Externalization)
Pindahkan seluruh status stateful keluar dari lifecycle aplikasi menuju subsistem yang dirancang khusus untuk persistensi dan konkurensi (misal: Redis Cluster atau Distributed Database).

```go
// BURUK: Local in-memory session mapping (Stateful Node)
var sessionStore = make(map[string]*UserSession) // Race condition & tidak tersinkronisasi antar-node!

func handleLoginBad(w http.ResponseWriter, r *http.Request) {
    sessionStore["session_id_123"] = &UserSession{UserID: "usr_42"} // Terkunci di node fisik ini saja!
}

// BAIK: Stateless Worker dengan Remote Distributed Store (External State)
type SessionManager struct {
    redisClient *redis.Client
}

func (s *SessionManager) HandleLoginGood(ctx context.Context, sessionID string, userID string) error {
    // Session state dieksternalisasi dengan TTL otomatis
    return s.redisClient.Set(ctx, fmt.Sprintf("session:%s", sessionID), userID, 24*time.Hour).Err()
}
```

---

### 13. Performance Tuning & Optimization
1. **Linux Kernel TCP Tuning (`/etc/sysctl.conf`):**
   - Naikan antrean koneksi: `net.core.somaxconn = 65535` (mencegah SYN drop saat request membanjir mendadak).
   - Perluas range ephemeral port: `net.ipv4.ip_local_port_range = 1024 65535` (mencegah *port exhaustion* pada Reverse Proxy).
   - Optimalkan penggunaan socket TIME_WAIT: `net.ipv4.tcp_tw_reuse = 1`.
2. **Buffer Allocation & Memory Pooling:**
   - Gunakan `sync.Pool` di Go untuk mereuse buffer serialization/deserialization JSON atau gRPC frame guna mengeliminasi alokasi berulang di heap memory dan mereduksi overhead *Garbage Collector*.
3. **Connection Multiplexing (HTTP/2 / HTTP/3):**
   - Gantikan koneksi HTTP/1.1 yang *head-of-line blocking* dengan HTTP/2 multi-stream atau QUIC (HTTP/3 berbasis UDP) untuk memangkas *handshake latency* pada network loss tinggi.

---

### 14. Security & Compliance Checklist
- [ ] **Rate Limiting & Threat Shielding:** Terapkan pembatasan rate pada layer L7 (misal: token-bucket di NGINX/Cloudflare) untuk menangkal degradasi performa akibat Layer 7 DDoS.
- [ ] **mTLS (Mutual TLS):** Komunikasi antar *Load Balancer* dan internal *Worker Nodes* wajib terenkripsi menggunakan mTLS guna memenuhi standar Zero-Trust Network dan regulasi PCI-DSS/HIPAA.
- [ ] **Safe Degradation / Shedding Injection:** Pastikan endpoint `/healthz` tidak membocorkan data infrastruktur sistem internal (misalnya versi runtime, IP privat, dsb.) ke jaringan publik.
- [ ] **Graceful Timeout Enforcement:** Wajib mengonfigurasi batas waktu timeout baca/tulis (`ReadTimeout`, `WriteTimeout`, `IdleTimeout`) pada semua reverse proxy dan worker agar koneksi lambat yang disengaja (*Slowloris attack*) tidak menghabiskan descriptor soket OS.

---

### 15. Observability, Metrics & Alerting
Gunakan metodologi **RED (Rate, Errors, Duration)** untuk mengukur performa sistem.

#### Metrik Kunci (Prometheus format):
- `http_requests_total{status=~"5.."}` : Menghitung Error rate.
- `http_request_duration_seconds_bucket` : Menghitung Latency percentiles ($p50, p95, p99$).
- `http_current_connections` : Menghitung concurrency aktual pada sistem.

#### Contoh Prometheus Alert Rule:
```yaml
groups:
  - name: system_design_core_alerts
    rules:
      - alert: HighP99LatencyBreach
        expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 0.500
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "P99 Latency terdeteksi di atas 500ms selama lebih dari 2 menit"
          description: "Throughput saat ini berpotensi memicu antrean sistemik (Little's Law saturation)."

      - alert: ServiceAvailabilityDrop
        expr: (sum(rate(http_requests_total{status=~"2.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100 < 99.9
        for: 1m
        labels:
          severity: page
        annotations:
          summary: "Availability SLA jatuh di bawah target 99.9%"
```

---

### 16. Disaster Recovery & Rollback Strategies
Untuk mempertahankan target ketersediaan saat deployment atau kegagalan infrastruktur total:
1. **RTO (Recovery Time Objective) & RPO (Recovery Point Objective):** Tetapkan ambang batas. Misalnya RTO < 5 menit, RPO = 0 (zero data loss).
2. **Blue-Green Deployments:** Sediakan dua klaster lingkungan fisik yang terpisah identik. Arahkan traffic balancer secara instan ke lingkungan Green saat versi baru diuji. Jika terdeteksi peningkatan $p99$ latency atau $5xx$ status code, balikkan router virtual IP ke klaster Blue dalam rentang milidetik.
3. **Automated Circuit Breaking:** Integrasikan circuit breaker (misal via Netflix Hystrix pattern). Jika pemanggilan dependensi downstream menghasilkan error rate > 50% dalam interval 10 detik, *trip the circuit* segera dan kembalikan fallback respons terdegradasi (*stale cache data*) alih-alih menahan thread klien.

---

### 17. Real-World Case Study
**Insiden:** Roblox 73-Hour Outage (Oktober 2021).
- **Akar Masalah:** Sistem perutean backend berbasis HashiCorp Consul mengalami masalah latensi yang melumpuhkan ribuan backend worker. Saat kapasitas klaster bertambah, parameter konkurensi dan komunikasi internal antar-node meledak secara geometris ($O(N^2)$ tracking overhead - relevan dengan variabel $\beta$ pada *Universal Scalability Law*).
- **Dampak:** Terjadi kebuntuan total (*deadlock* pada layer sinkronisasi internal). Ketersediaan anjlok ke 0% selama 3 hari berturut-turut.
- **Pelajaran Rekayasa:** Skalabilitas horizontal tanpa segmentasi topologi (*fault domains / cell-based architecture*) akan menciptakan batas USL di mana penambahan worker komputasi justru merusak kestabilan klaster secara keseluruhan.

---

### 18. Guided Hands-On Exercise / Challenge
**Tantangan:** Modifikasi kode Go Load Balancer pada Seksi 8 agar memiliki algoritma **Least Connections**.

#### Instruksi:
1. Tambahkan metrik penanda koneksi aktif (`ActiveConnections int64`) pada struct `Backend`.
2. Gunakan `atomic.AddInt64(&peer.ActiveConnections, 1)` saat request masuk ke proxy, dan kurangi dengan `atomic.AddInt64(&peer.ActiveConnections, -1)` menggunakan `defer` setelah pemrosesan selesai.
3. Ubah metode `GetNextPeer()`: Gantikan round-robin loop dengan perulangan yang memindai seluruh backend berstatus `Alive`, lalu kembalikan backend yang memiliki `ActiveConnections` paling sedikit.
4. Simulasikan skenario di mana Backend A memiliki pemrosesan lambat (misal: inject `time.Sleep(1 * time.Second)`) sementara Backend B instan. Buktikan bahwa metode Least Connection mengalokasikan mayoritas request ke Backend B.

---

### 19. Self-Reflection & Conceptual Quiz
1. Sebuah sistem microservices terdiri dari 20 layanan independen yang dipanggil berurutan secara sinkronus (*serial pipeline*). Masing-masing layanan memiliki SLA availability 99.9%. Berapakah kalkulasi ketersediaan akhir dari sistem tersebut secara matematis? Apakah masih memenuhi standar "three nines"?
2. Jelaskan perbedaan struktural antara peningkatan latency yang disebabkan oleh *Processing Delay* (CPU bounded) vs *Queuing Delay* (ketersediaan thread habis). Bagaimana Anda mendeteksinya menggunakan metrik USE (*Utilization, Saturation, Errors*)?
3. Mengapa metrik "Rata-rata Latensi" (*Mean Latency*) dianggap sebagai indikator performa yang menyesatkan (*misleading*) dalam sistem terdistribusi skala besar?

---

### 20. Applied Knowledge / Mini-Project Assignment
**Spesifikasi Mini-Proyek:**
Bangunlah sebuah **CLI Distributed Latency Profiler** menggunakan bahasa pilihan Anda (Go/Rust/Python/Node.js) yang mengeksekusi pengujian stres pada target HTTP Server:
- **Spesifikasi Teknis:**
  - Terima input parameter: Target URL, Concurrency Level ($C$), Total Requests ($N$).
  - Gunakan HTTP connection pooling secara benar tanpa resource leak.
  - Kumpulkan durasi response dari seluruh request yang sukses.
  - Urutkan dan hitung secara akurat nilai distribusi latensi: Minimum, Rata-rata, $p50$, $p90$, $p99$, dan Maximum.
  - Tampilkan ringkasan metrik dalam bentuk tabel terminal format rapi bersama dengan throughput aktual ($RPS = N / Total\_Time$).
- **Uji Validasi:** Jalankan profiler Anda ke mock-server lokal dengan latency sintetis berdistribusi Poisson. Tunjukkan bukti bahwa distribusi $p99$ mampu mendeteksi *tail latency spikes* yang tidak terlihat pada data metrik *mean* (rata-rata).