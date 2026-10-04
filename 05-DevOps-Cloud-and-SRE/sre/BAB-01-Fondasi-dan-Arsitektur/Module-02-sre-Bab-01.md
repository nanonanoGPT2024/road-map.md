# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (SRE)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur sistem berskala enterprise dengan prinsip dasar *Zero Trust*, *High Availability* ($99.99\%+$), dan *Fault Isolation*.
- Mengimplementasikan formulasi matematis untuk Service Level Indicators (SLI), Service Level Objectives (SLO), dan Error Budget berbasis *Multi-Window Multi-Burn-Rate Alerting* (MWMRA).
- Mengintegrasikan mekanisme ketahanan sistem modern (*resilience patterns*): *Adaptive Concurrency Limiting*, *Circuit Breaking*, *Load Shedding*, dan *Bulkheading* pada layer aplikasi dan service mesh.
- Mengotomatisasi tata kelola deployment menggunakan *Error Budget Policy* yang terhubung langsung ke pipeline CI/CD (Canary Analysis otomatis).
- Mendiagnosis dan memitigasi kegagalan kaskade (*cascading failures*) pada lingkungan multi-region terdistribusi secara sistematis.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Konsep dasar networking: OSI Layer, TCP/IP handshake, HTTP/2, HTTP/3, TLS 1.3 termination, DNS resolution latency.
- Pengetahuan operasional Linux kernel dasar: cgroups, namespaces, epoll, I/O bottlenecks, sinyal proses POSIX.
- Kemampuan dasar instrumentasi metrik: Prometheus (PromQL), Grafana, dan OpenTelemetry SDK.
- Konsep dasar konkurensi (goroutine, event-loop, worker pool, thread contention).
- Penyelesaian Modul 01: Pengantar Prinsip SRE vs DevOps, Dasar-dasar SLI/SLO/SLA.

---

## 3. Concept & Internal Architecture (Mendalam)

### A. Anatomi Matematika SLI, SLO, dan Error Budget

Keandalan sistem (*reliability*) bukanlah konsep biner ("nyala" atau "mati"), melainkan distribusi probabilitas waktu kerja terhadap ekspektasi pengguna.

#### 1. Formulasi Dasar SLI
SLI didefinisikan sebagai rasio kejadian valid yang memenuhi kriteria terhadap total kejadian valid:

$$\text{SLI} = \frac{\sum \text{Good Events}}{\sum \text{Total Valid Events}} \times 100\%$$

*Good Events* harus diukur sedekat mungkin dengan pengguna akhir (misal: HTTP status code non-5xx dan latensi $\le 200\text{ms}$ yang diukur pada reverse-proxy/edge layer).

#### 2. Dinamika Error Budget
Error Budget ($EB$) adalah toleransi ketidakandalan (*unreliability*) sistem dalam periode bergulir (*rolling window*) $T$ (misal: 30 hari).

$$EB = 1 - \text{SLO}$$

Jika sebuah service memproses $10.000.000$ request per bulan dengan target SLO ketersediaan sebesar $99.9\%$, maka kuota error budget yang diizinkan adalah:

$$EB_{\text{count}} = 10.000.000 \times (1 - 0.999) = 10.000 \text{ bad requests}$$

#### 3. Teori Multi-Window Multi-Burn-Rate Alerting (MWMRA)
Mekanisme alerting tradisional berbasis ambang batas tunggal (misal: "kirim alert jika error rate $> 1\%$ selama 5 menit") memiliki kelemahan mendasar: rentan terhadap *false alarm* pada volume trafik rendah dan gagal mendeteksi kebocoran error lambat (*slow burn*) yang mengikis budget sebelum akhir siklus.

Google SRE merekomendasikan pendekatan *Multi-Window Multi-Burn-Rate*. Tingkat pembakaran (*Burn Rate* / $BR$) mengukur seberapa cepat Error Budget dihabiskan relatif terhadap target SLO:

$$BR = \frac{1 - \text{SLI}}{1 - \text{SLO}}$$

- $BR = 1$: Budget habis tepat pada akhir periode (30 hari).
- $BR = 14.4$: $2\%$ budget habis dalam 1 jam (Kritis: Butuh PagerDuty/On-Call segera).
- $BR = 6$: $5\%$ budget habis dalam 6 jam.

MWMRA memvalidasi kondisi error menggunakan dua jendela waktu simultan (*long window* dan *short window*) untuk meminimalisasi noise dan memastikan anomali masih berlangsung:

```
Alert Terpicu JIKA:
  (Error Rate pada Long Window [cth: 1 Jam] > BR_Threshold * (1 - SLO))
  DAN
  (Error Rate pada Short Window [cth: 5 Menit] > BR_Threshold * (1 - SLO))
```

```
+-----------------------------------------------------------------------+
| Window Evaluasi MWMRA                                                |
|                                                                       |
| Long Window (1 Jam):    [=========== ERROR PERSISTEN ===========]     |
|                                 AND                                   |
| Short Window (5 Menit):                   [==== MASIH TERJADI ====]   |
|                                                                       |
| Output -> TRIGGER PAGER (P1)                                          |
+-----------------------------------------------------------------------+
| Spike Transien (Bukan Insiden Sistemik):                             |
|                                                                       |
| Long Window (1 Jam):    [== Spike == ............................]    |
|                                 AND                                   |
| Short Window (5 Menit):                   [...... NORMAL ........]    |
|                                                                       |
| Output -> SUPPRESS ALERT (Noise Redirection)                         |
+-----------------------------------------------------------------------+
```

---

### B. Mekanisme Mitigasi Kegagalan Kaskade (*Cascading Failure Resilience*)

Arsitektur produksi modern wajib mengasumsikan dependensi downstream pasti akan gagal secara parsial atau mengalami degradasi latensi (*tail latency amplification*).

```
[Client] ---> [API Gateway] ---> [Service A] ---> [Service B (Degraded)]
                    |                 |                   |
                    |                 +-- [Circuit Open] -+
                    |                 |   (Fallback to Redis/Cache)
                    +-- [Adaptive Concurrency Limit]
                        (Shedding non-critical load)
```

#### 1. Adaptive Concurrency Limiting (Algoritma Vegas / Little's Law)
Pembatasan statis menggunakan static hard-limits (misal: max 200 concurrent connection) tidak efisien karena throughput server bergantung pada response time downstream. Sesuai **Hukum Little**:

$$L = \lambda \times W$$

*Dimana:*
- $L$ = Concurrency (jumlah in-flight request).
- $\lambda$ = Arrival rate / Throughput (request per detik).
- $W$ = Latensi rata-rata (durasi eksekusi).

Jika latensi downstream naik dari $50\text{ms}$ ke $2\text{s}$, kapasitas concurrency lokal akan tersaturasi secara eksponensial. Algoritma *TCP Vegas* mengukur *Queueing Delay* internal untuk menentukan limit secara adaptif:

$$\text{Queue Delay} = \text{RTT}_{\text{actual}} - \text{RTT}_{\text{min}}$$

Bila $\text{Queue Delay} > \alpha$, sistem menurunkan nilai *concurrency limit* sebelum terjadi *Out-of-Memory* (OOM) atau CPU thrashing.

#### 2. Distributed Load Shedding dengan Priority Tiers
Ketika sistem mendeteksi saturasi (CPU $> 85\%$, GC pause $> 100\text{ms}$, atau in-flight queue penuh), request diklasifikasikan ke dalam bucket prioritas:
1. **CRITICAL**: Checkout transaksi, autentikasi sesi, token exchange.
2. **DEGRADABLE**: Rekomendasi homepage, feed updates.
3. **BEST_EFFORT**: Tracking analitik, pre-fetching, sinkronisasi data asinkron.

Algoritma *CoDel* (Controlled Delay) atau *Tail Drop Token Bucket* langsung mengeksekusi *early rejection* (HTTP 503 dengan header `Retry-After`) pada bucket `BEST_EFFORT` dan `DEGRADABLE`, mengalokasikan seluruh resource core untuk memproses bucket `CRITICAL`.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (IT Ops) | Pendekatan SRE Modern |
| :--- | :--- | :--- |
| **Metrik Keberhasilan** | Target Uptime Server 100% (Unrealistic). | Optimalisasi batas keandalan via SLO dan Error Budget. |
| **Penanganan Insiden** | Penanganan reaktif pasca notifikasi server *down*. | Deteksi deviasi burn rate prediktif sebelum SLA terlanggar. |
| **Stabilitas Rilis** | Deployment dihentikan manual atas persetujuan manual CAB (*Change Advisory Board*). | *Automated Policy Gatekeeping*: Deployment diblokir otomatis jika Error Budget menipis. |
| **Respon Kegagalan** | Retry tanpa batas (*retry storm*), scaling vertikal instan. | Graceful degradation, circuit breaking, dan adaptive load shedding. |
| **Post-Incident** | Mencari kesalahan individu (*Root Cause Analysis* konvensional). | *Blameless Post-Mortem*, perbaikan struktural sistemik (*Action Items*). |

---

## 5. How (Workflow Detail)

Siklus penegakan kendali keandalan produksi diimplementasikan melalui tahapan terstruktur berikut:

```
+---------------------------------------------------------------------------------------+
| ALUR OPERASIONAL KENDALI KEANDALAN SRE                                                |
+---------------------------------------------------------------------------------------+
    |
    v
[1. Definisi & Instrumentasi]
    * Petakan "User Journey" kritis.
    * Tentukan SLI berbasis metrik RED (Rate, Errors, Duration).
    * Emit metrik via OpenTelemetry / Prometheus client library.
    |
    v
[2. Validasi SLO & Budgeting]
    * Tetapkan SLO (misal: 99.9% Latensi P99 < 300ms, Error Rate < 0.1%).
    * Hitung alokasi error budget harian, mingguan, dan bulanan.
    |
    v
[3. Real-Time Telemetry & Alerting]
    * Monitor burn rate menggunakan multi-window evaluation.
    * Jika BR > 14.4x (2% budget habis dalam 1 jam) -> Trigger Pager Duty (P1).
    * Jika BR > 3x (10% budget habis dalam 1 hari) -> Trigger Jira Ticket (P3).
    |
    v
[4. Automated Circuit Breaking & Load Shedding]
    * Runtime application memantau error downstream.
    * Eksekusi degradasi parsial jika SLO breach terdeteksi.
    |
    v
[5. Error Budget Policy Enforcement (CI/CD Gates)]
    * CD Pipeline menginspeksi sisa Error Budget via API Prometheus.
    * Jika sisa Error Budget < 0% -> Bekukan release non-patch; fokus perbaikan stabilitas.
    * Jalankan *Automated Canary Analysis* (ACA) untuk rilis baru.
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Katup Pengaman & Rem Hidrolik Pesawat Komersial
Pesawat terbang tidak dirancang dengan asumsi komponen mekanikalnya tidak akan pernah mengalami deformasi atau keausan. Sebaliknya, pesawat dirancang dengan redundansi jalur hidrolik dan katup pelepasan tekanan (*pressure relief valves*). 

- **SLO** adalah batas operasional aman (kecepatan jelajah struktural).
- **Error Budget** adalah margin toleransi getaran turbulensi sebelum airframe mengalami stres struktural.
- **Load Shedding** setara dengan prosedur standar pembuangan bahan bakar (*fuel dumping*) saat pendaratan darurat: mengorbankan sebagian muatan untuk memastikan keselamatan komponen paling kritis (badan utama dan penumpang).

```
                      ARSITEKTUR ERROR BUDGET GATEKEEPER
                      
[Git Push / Commit] 
         |
         v
+------------------+
| CI/CD Pipeline   |
| (ArgoCD / Drone) |
+--------+---------+
         |
         | (1) Pre-deployment Check: GET /api/v1/error-budget
         v
+------------------+      Return: Current EB Balance
| Prometheus / SRE | ------------------------------------+
| Metrics Engine   |                                     |
+------------------+                                     v
                                              +---------------------+
                                              | Is Budget >= 20%?   |
                                              +----------+----------+
                                                         |
                                  +----------------------+----------------------+
                                  | YES                                         | NO
                                  v                                             v
                      +-----------------------+                     +-----------------------+
                      | Deploy to Canary      |                     | BLOCK RELEASE         |
                      | Traffic: 5% -> 25%    |                     | Alihkan sprint ke     |
                      +-----------+-----------+                     | Tech Debt & Stability |
                                  |                                 +-----------------------+
                                  v
                      +-----------------------+
                      | ACA (Automated Canary |
                      | Analysis) P99 SLI OK? |
                      +-----------+-----------+
                                  |
                   +--------------+--------------+
                   | YES                         | NO
                   v                             v
       +-----------------------+     +-----------------------+
       | Promote to 100% Prod  |     | Rollback Canary       |
       +-----------------------+     | Log Incident Trace    |
                                     +-----------------------+
```

---

## 7. Simple Example & Practical Example

### Implementasi Multi-Burn-Rate Alerting Rules (Prometheus PromQL)

Berikut adalah konfigurasi alerting standar industri untuk service HTTP dengan target SLO ketersediaan **99.9%** pada jendela waktu 30 hari.

```yaml
# prometheus-slo-rules.yaml
groups:
  - name: slo-http-availability-alerting
    rules:
      # Metrik dasar rate error dan request
      - record: job:http_requests_total:rate1h
        expr: sum(rate(http_requests_total{job="payment-service"}[1h]))
      - record: job:http_requests_errors_total:rate1h
        expr: sum(rate(http_requests_total{job="payment-service", status=~"5.."}[1h]))

      - record: job:http_requests_total:rate5m
        expr: sum(rate(http_requests_total{job="payment-service"}[5m]))
      - record: job:http_requests_errors_total:rate5m
        expr: sum(rate(http_requests_total{job="payment-service", status=~"5.."}[5m]))

      - record: job:http_requests_total:rate6h
        expr: sum(rate(http_requests_total{job="payment-service"}[6h]))
      - record: job:http_requests_errors_total:rate6h
        expr: sum(rate(http_requests_total{job="payment-service", status=~"5.."}[6h]))

      - record: job:http_requests_total:rate30m
        expr: sum(rate(http_requests_total{job="payment-service"}[30m]))
      - record: job:http_requests_errors_total:rate30m
        expr: sum(rate(http_requests_total{job="payment-service", status=~"5.."}[30m]))

      # ALERT 1: Kritis (Page / P1) - 2% budget dikonsumsi dalam 1 jam (Burn Rate = 14.4)
      # Window: 1h dan 5m
      - alert: PaymentServiceAvailabilityP1BurnRate
        expr: |
          (
            job:http_requests_errors_total:rate1h / job:http_requests_total:rate1h
            > (14.4 * (1 - 0.999))
          )
          and
          (
            job:http_requests_errors_total:rate5m / job:http_requests_total:rate5m
            > (14.4 * (1 - 0.999))
          )
        for: 2m
        labels:
          severity: critical
          tier: tier-1
          pager: pagerduty
        annotations:
          summary: "Kehabisan Error Budget Sangat Cepat pada payment-service (Burn Rate 14.4x)"
          description: "Payment-service mengalami kegagalan rate > 1.44% selama 1 jam dan berlanjut di 5 menit terakhir. Error budget terkuras 2% per jam."

      # ALERT 2: Warning (Ticket / P3) - 5% budget dikonsumsi dalam 6 jam (Burn Rate = 6)
      # Window: 6h dan 30m
      - alert: PaymentServiceAvailabilityP3BurnRate
        expr: |
          (
            job:http_requests_errors_total:rate6h / job:http_requests_total:rate6h
            > (6 * (1 - 0.999))
          )
          and
          (
            job:http_requests_errors_total:rate30m / job:http_requests_total:rate30m
            > (6 * (1 - 0.999))
          )
        for: 15m
        labels:
          severity: warning
          tier: tier-1
          channel: slack-sre-tickets
        annotations:
          summary: "Error Budgetpayment-service mengalami penipisan stabil (Burn Rate 6x)"
          description: "Payment-service mengonsumsi 5% error budget dalam 6 jam terakhir. Lakukan investigasi sebelum menjadi insiden kritis."
```

### Implementasi Resilience: Adaptive Concurrency Limiter Middleware (Go)

Contoh implementasi production-grade di Golang menggunakan algoritma *Additive Increase Multiplicative Decrease (AIMD)* berbasis pelacakan latency percentile lokal.

```go
// middleware/concurrency_limiter.go
package middleware

import (
	"errors"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

var (
	ErrServerOverloaded = errors.New("server overloaded: concurrency limit reached")
)

type AdaptiveLimiter struct {
	mu             sync.RWMutex
	concurrencyCap int64
	inFlight       int64
	minRTT         time.Duration
	targetRTT      time.Duration
}

func NewAdaptiveLimiter(initialCap int64, targetRTT time.Duration) *AdaptiveLimiter {
	return &AdaptiveLimiter{
		concurrencyCap: initialCap,
		targetRTT:      targetRTT,
		minRTT:         time.Hour,
	}
}

func (l *AdaptiveLimiter) Handle(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		currentInFlight := atomic.AddInt64(&l.inFlight, 1)
		defer atomic.AddInt64(&l.inFlight, -1)

		l.mu.RLock()
		maxCap := l.concurrencyCap
		l.mu.RUnlock()

		// Load Shedding jika melewati kapasitas adaptif
		if currentInFlight > maxCap {
			w.Header().Set("Retry-After", "5")
			http.Error(w, ErrServerOverloaded.Error(), http.StatusServiceUnavailable)
			return
		}

		startTime := time.Now()
		next.ServeHTTP(w, r)
		duration := time.Since(startTime)

		l.recalculateLimits(duration)
	})
}

func (l *AdaptiveLimiter) recalculateLimits(sample time.Duration) {
	l.mu.Lock()
	defer l.mu.Unlock()

	// Update base RTT minimum sistem
	if sample < l.minRTT {
		l.minRTT = sample
	}

	// Dynamic adjustment berdasarkan target RTT threshold
	if sample > l.targetRTT {
		// Multiplicative Decrease: Terjadi antrean, pangkas limit agresif
		newCap := int64(float64(l.concurrencyCap) * 0.85)
		if newCap < 5 {
			newCap = 5 // Floor limit minimum
		}
		l.concurrencyCap = newCap
	} else {
		// Additive Increase: Sistem sehat, naikkan kapasitas perlahan
		l.concurrencyCap += 1
	}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden Cascading Latency Collapse pada Core Checkout Platform E-Commerce Global

#### Arsitektur Awal
Sebuah platform marketplace global melayani $120.000$ request per detik (RPS) pada saat festival belanja kuartalan (*flash-sale*). Topologi sistem terdiri dari:
- `Edge Cloudflare Worker` $\to$ `Ingress Envoy Controller`
- `Order Orchestrator Service` $\to$ memanggil `Inventory Engine`, `Discount Service`, dan `Payment Core`.

```
                    +-----------------------------+
                    | Ingress Envoy (120,000 RPS) |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Order Orchestrator Service  |
                    +----+------------------+-----+
                         |                  |
           (Sync Call)   v                  v   (Sync Call)
           +--------------------+     +--------------------+
           |  Inventory Engine  |     |   Payment Core     |
           +--------------------+     +--------------------+
                                                |
                                                v (Slow DB Lock)
                                      +--------------------+
                                      | PostgreSQL Cluster |
                                      +--------------------+
```

#### Kronologi Kegagalan (*Sequence of Failure*)
1. **00:01:00 UTC**: Terjadi *row-level locking contention* parah pada PostgreSQL Payment Core akibat update konkuren saldo voucher promo tertentu.
2. **00:01:30 UTC**: Response time P99 `Payment Core` melesat dari $45\text{ms}$ menjadi $8.200\text{ms}$.
3. **00:02:00 UTC**: Connection pool Tomcat pada `Order Orchestrator` habis terpakai menunggu respon downstream `Payment Core`.
4. **00:02:15 UTC**: Fitur standard Go/Java HTTP client pada `Order Orchestrator` melakukan *automatic retry 3x* tanpa backoff jitter. Trafik internal ke `Payment Core` meledak menjadi $360.000$ RPS (**Self-Inflicted Retry Storm**).
5. **00:03:00 UTC**: CPU host ingress gateway mencapai $100\%$, memory memory swapping terpicu, dan seluruh cluster `Order Orchestrator` OOM-Killed secara serentak. Uptime global drop ke $0\%$.

#### Analisis SRE & Root Cause
- Ketiadaan Circuit Breaker: Layanan terus meneruskan panggilan synchronous ke dependensi yang sudah kolaps.
- Retry Amplification Factor = 3x tanpa exponential backoff dan jitter.
- Tidak adanya deadline/timeout propagation (gRPC metadata context tidak dihormati).

#### Solusi & Arsitektur Remediasi yang Diterapkan
1. **Penerapan Context Deadline Propagation**: Header request diinjeksikan deadline absolut $1500\text{ms}$. Jika $1000\text{ms}$ telah terpakai di orchestration layer, downstream `Payment Core` hanya memiliki sisa waktu eksekusi $500\text{ms}$. Jika lewat, request di-*abort* segera tanpa membuang siklus CPU database.
2. **Envoy Outlier Detection & Circuit Breaker**:
   ```yaml
   circuit_breakers:
     thresholds:
       - priority: DEFAULT
         max_connections: 5000
         max_pending_requests: 100
         max_requests: 6000
   outlier_detection:
     consecutive_5xx: 3
     interval: 5s
     base_ejection_time: 30s
     max_ejection_percent: 50
   ```
3. **Fail-Open pada Path Non-Critical**: Jika `Discount Service` mengalami degradasi, orkestrator menerapkan *graceful degradation* dengan mengabaikan promo dan tetap memproses order dengan harga normal (disertai asynchronous compensatory credit wallet belakangan).

---

## 9. Trade-offs

Setiap keputusan arsitektur keandalan memiliki konsekuensi biaya dan performa yang harus dihitung cermat:

| Pola Arsitektur | Keuntungan | Kompensasi / Kerugian (*Trade-off*) |
| :--- | :--- | :--- |
| **Active-Active Multi-Region** | RTO $\approx 0$, RPO near-zero. Tahan terhadap *datacenter-level outage*. | Biaya infrastruktur naik $>100\%$. Kompleksitas konsistensi data tinggi (*CAP theorem*: wajib memilih eventual consistency via CRDT atau menderita cross-region write latency). |
| **Aggressive Load Shedding** | Core system bertahan hidup saat terjadi lonjakan trafik ekstrem. | Sebagian user mengalami kegagalan request secara eksplisit (penurunan rasio konversi bisnis jangka pendek). |
| **High Tracing Sampling Rate (100%)** | Diagnostik latensi granularitas tinggi untuk tail latency debugging. | Overhead CPU pada network stack melonjak drastis; biaya *ingestion* dan penyimpanan log OTel/Datadog naik ribuan dolar per bulan. |
| **Tight Burn-Rate Alerting (MWMRA)** | Zero missed alerts; deteksi insiden sangat presisi sebelum SLA habis. | Kompleksitas tinggi dalam merancang dan memelihara ratusan baris query PromQL; potensi kurva belajar tim operasional lebih curam. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum dalam Eksekusi SRE

1. **SLO Defined Without Business Context**:
   - *Anti-Pattern*: SRE menetapkan SLO Availability $99.999\%$ (hanya boleh down 5 menit setahun) pada internal reporting dashboard batch yang hanya dibuka staf internal di jam kerja.
   - *Remediasi*: SLO harus mencerminkan titik di mana pengguna mulai merasa tidak puas (*user pain threshold*).

2. **Averaging Latencies (The Mean Fallacy)**:
   - *Anti-Pattern*: Melaporkan *Average Latency = 120ms*.
   - *Masalah*: Rata-rata menyembunyikan ekor distribusi (*tail latency*). Jika 95% user merespons 20ms, namun 5% user mengalami 20.000ms (akibat database lock), rata-rata tetap menunjukkan angka "sehat" ~1000ms, padahal 1 dari 20 user mengalami *timeout*.
   - *Solusi*: Wajib gunakan persentil: P90, P99, dan P99.9.

3. **Retry Storm Tanpa Jitter**:
   - *Anti-Pattern*: Semua pod melakukan retry serentak setiap detik secara presisi ($t=1\text{s}, 2\text{s}, 3\text{s}$).
   - *Solusi*: Gunakan **Full Jitter Exponential Backoff**:
     
     $$T_{\text{sleep}} = \text{random}(0, \, \min(M, \, B \cdot 2^{\text{attempt}}))$$

### Troubleshooting Playbook: Menghadapi P1 Burn Rate Alert

Jika Anda menerima notifikasi P1 Burn Rate Alert ($BR \ge 14.4$), eksekusi protokol triase darurat berikut:

```
[ALERT TRIGGERED: BurnRate > 14.4x]
                 |
                 v
[Step 1: Identifikasi Blast Radius]
- Cek dashboard Grafana SLI: Apakah terjadi global atau spesifik tenant/region?
- Ambil sampel P99 latency & error distribution per HTTP status code (500 vs 502/503/504).
                 |
                 +-----> [Jika 502/504 Bad Gateway / Gateway Timeout]
                 |       Downstream mati total / saturasi worker connection pool.
                 |       Tindakan: Scale horizontal downstream atau aktifkan circuit-breaker bypass.
                 |
                 +-----> [Jika 503 Service Unavailable]
                 |       Load Shedding / Rate Limiter aktif memblokir request.
                 |       Tindakan: Cek metrik CPU/Memory underlying node host; mitigasi spike trafik.
                 |
                 +-----> [Jika 500 Internal Server Error]
                         Bug aplikasi pasca deployment baru.
                         Tindakan: SEGERA ROLLBACK release terakhir (Canary abort). JANGAN debug kode di stage ini!
```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mendeklarasikan sebuah service siap (*production-ready*):

- [ ] **Definisi SLI/SLO**:
  - SLI latency diukur menggunakan persentil (P95/P99), bukan rata-rata.
  - Formulasi error budget didokumentasikan dan disepakati oleh tim Product Manager dan Engineering.
- [ ] **Observabilitas**:
  - Metrik Prometheus diekspos dengan label kardinalitas terkontrol (hindari memasukkan `user_id` atau `email` sebagai label Prometheus).
  - Trace context (TraceParent/W3C) diinjeksikan melintasi semua boundary network eksternal dan internal.
- [ ] **Resilience Engineering**:
  - Timeout dikonfigurasi secara eksplisit di setiap HTTP/gRPC client call (tidak boleh menggunakan default unlimited/0).
  - Retry logic dilengkapi dengan *exponential backoff* dan *full jitter*.
  - Circuit Breaker dipasang di semua integrasi dependensi Tier-2/Third-Party.
  - Health check endpoint mendiferensiasikan `/livez` (proses runtime berjalan) dan `/readyz` (dependensi database siap memproses transaksi).
- [ ] **Automasi Rilis**:
  - Pipeline CD mengimplementasikan Canary Deployment bertahap (5% $\to$ 25% $\to$ 100%) dengan auto-rollback berbasis SLI evaluation.
  - Sisa Error Budget diintegrasikan sebagai parameter evaluasi release gate.

---

## 12. Hands-on Practice

Praktikum ini mensimulasikan lingkungan mikroservis yang dilengkapi Prometheus, simulasi degradasi latensi downstream, dan mekanisme pertahanan load shedding.

### Struktur Direktori Praktikum
Siapkan workspace Anda di `hands-on/m02/`:
```text
hands-on/m02/
├── docker-compose.yaml
├── prometheus/
│   ├── alert.rules.yml
│   └── prometheus.yml
├── downstream/
│   ├── Dockerfile
│   └── main.go
└── gateway/
    ├── Dockerfile
    └── main.go
```

### File 1: `hands-on/m02/downstream/main.go`
Service yang mensimulasikan tail latency acak dan kegagalan downstream.

```go
package main

import (
	"math/rand"
	"net/http"
	"time"
)

func main() {
	http.HandleFunc("/process", func(w http.ResponseWriter, r *http.Request) {
		// Simulasikan latency spike: 20% request memakan waktu 2 detik (bottleneck)
		if rand.Float32() < 0.20 {
			time.Sleep(2000 * time.Millisecond)
		} else {
			time.Sleep(50 * time.Millisecond)
		}

		// Simulasikan error rate 5%
		if rand.Float32() < 0.05 {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"status":"error","detail":"database deadlock"}`))
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"success"}`))
	})

	http.ListenAndServe(":8081", nil)
}
```

### File 2: `hands-on/m02/gateway/main.go`
Edge gateway dengan instrumentasi SLI Prometheus bawaan dan proteksi Concurrency Limiting.

```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"sync/atomic"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests yang diproses gateway",
		},
		[]string{"path", "status"},
	)

	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Distribusi latensi request",
			Buckets: []float64{0.05, 0.1, 0.25, 0.5, 1.0, 2.5},
		},
		[]string{"path"},
	)

	inFlightRequests int64
	maxConcurrent    int64 = 15 // Limit beban serentak
)

func init() {
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
}

func handleCheckout(w http.ResponseWriter, r *http.Request) {
	current := atomic.AddInt64(&inFlightRequests, 1)
	defer atomic.AddInt64(&inFlightRequests, -1)

	timer := prometheus.NewTimer(httpRequestDuration.WithLabelValues("/checkout"))
	defer timer.ObserveDuration()

	// Implementasi Load Shedding sederhana jika pool tersaturasi
	if current > maxConcurrent {
		httpRequestsTotal.WithLabelValues("/checkout", "503").Inc()
		w.Header().Set("Retry-After", "2")
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error":"Shedding load: gateway saturated"}`))
		return
	}

	client := http.Client{Timeout: 1 * time.Second}
	resp, err := client.Get("http://downstream:8081/process")
	if err != nil {
		httpRequestsTotal.WithLabelValues("/checkout", "504").Inc()
		w.WriteHeader(http.StatusGatewayTimeout)
		w.Write([]byte(`{"error":"Downstream timeout"}`))
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	statusStr := fmt.Sprintf("%d", resp.StatusCode)
	httpRequestsTotal.WithLabelValues("/checkout", statusStr).Inc()

	w.WriteHeader(resp.StatusCode)
	w.Write(body)
}

func main() {
	http.HandleFunc("/checkout", handleCheckout)
	http.Handle("/metrics", promhttp.Handler())
	http.ListenAndServe(":8080", nil)
}
```

### File 3: `hands-on/m02/prometheus/prometheus.yml`
```yaml
global:
  scrape_interval: 2s
  evaluation_interval: 2s

rule_files:
  - "alert.rules.yml"

scrape_configs:
  - job_name: "gateway-service"
    static_configs:
      - targets: ["gateway:8080"]
```

### File 4: `hands-on/m02/prometheus/alert.rules.yml`
```yaml
groups:
  - name: gateway-slo-alerts
    rules:
      - alert: GatewayHighLatencyBurnRate
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[30s]))
            /
            sum(rate(http_requests_total[30s]))
          ) > 0.05
        for: 10s
        labels:
          severity: critical
        annotations:
          summary: "Error rate kritis terdeteksi pada Gateway API (>5%)"
```

### File 5: `hands-on/m02/docker-compose.yaml`
```yaml
version: '3.8'

services:
  downstream:
    build:
      context: ./downstream
    ports:
      - "8081:8081"

  gateway:
    build:
      context: ./gateway
    ports:
      - "8080:8080"
    depends_on:
      - downstream

  prometheus:
    image: prom/prometheus:v2.45.0
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alert.rules.yml:/etc/prometheus/alert.rules.yml
    ports:
      - "9090:9090"
    depends_on:
      - gateway
```

### File 6: `hands-on/m02/gateway/Dockerfile` & `downstream/Dockerfile`
```dockerfile
# Gunakan syntax yang sama untuk keduanya (ganti port dan source file sesuai target)
FROM golang:1.21-alpine as builder
WORKDIR /app
COPY main.go .
RUN go mod init example.com/service && \
    go get github.com/prometheus/client_golang/prometheus && \
    go get github.com/prometheus/client_golang/prometheus/promhttp && \
    go build -o service main.go

FROM alpine:3.18
WORKDIR /root/
COPY --from=builder /app/service .
EXPOSE 8080 8081
CMD ["./service"]
```

### Panduan Eksekusi Praktikum
1. **Jalankan Cluster**:
   ```bash
   cd hands-on/m02/
   docker compose up --build -d
   ```
2. **Kirim Beban Normal (Smoke Test)**:
   ```bash
   curl -i http://localhost:8080/checkout
   ```
3. **Simulasikan Lonjakan Trafik Ekstrem (Traffic Flood Test)**:
   Gunakan tool benchmark seperti `hey` (atau `ab` / ApacheBench):
   ```bash
   # 50 workers secara paralel mengirim 2.000 requests
   hey -n 2000 -c 50 http://localhost:8080/checkout
   ```
4. **Verifikasi Respon Sistem**:
   - Buka Prometheus di `http://localhost:9090`.
   - Cek ekspresi query PromQL:
     ```promql
     sum by (status) (rate(http_requests_total[1m]))
     ```
   - Amati bagaimana response `503` (*Load Shedding*) dan `504` (*Downstream Timeout*) terbentuk untuk menjaga gateway tetap responsif dan tidak mengalami OOM-crash.
   - Amati tab **Alerts** pada antarmuka web Prometheus untuk melihat rule `GatewayHighLatencyBurnRate` berpindah status dari `PENDING` ke `FIRING`.

---

## 13. Exercise

### Level Easy
Tuliskan PromQL alert rule tunggal untuk menghitung persentase ketersediaan (*availability*) aplikasi dalam 15 menit terakhir. Alert wajib bernilai benar (*true*) jika rasio error status code 5xx melebihi ambang batas toleransi error budget $0.1\%$ ($SLO = 99.9\%$).

### Level Medium
Sebuah sistem memiliki baseline latensi rata-rata $40\text{ms}$. Secara tiba-tiba, latensi P99 meningkat tajam menjadi $1.200\text{ms}$ sementara rata-rata latensi (*mean*) hanya bergeser tipis menjadi $48\text{ms}$.
1. Jelaskan secara matematis bagaimana skenario ini mungkin terjadi.
2. Identifikasi potensi dampaknya terhadap thread pool sistem upstream yang mengonsumsi API tersebut.

### Level Hard
Rancang pseudocode arsitektur client-side circuit breaker di level service mesh (atau proxy application) yang mengimplementasikan 3 state standard: `CLOSED`, `OPEN`, dan `HALF-OPEN`. 
- Sistem harus membuka sirkuit jika rasio kegagalan mencapai $>50\%$ dalam sliding window 10 detik.
- Wajib memiliki cooldown period 30 detik sebelum berpindah ke `HALF-OPEN`.
- Hanya boleh meloloskan $5\%$ sampel trafik secara acak pada fase `HALF-OPEN` untuk menguji kesiapan recovery downstream sebelum sirkuit ditutup kembali secara penuh.

---

## 14. Challenge

### Konteks Skenario: "The Black Friday Thundering Herd Catastrophe"
Anda adalah Principal Site Reliability Engineer pada bank digital enterprise. Arsitektur Anda mengelola sistem otorisasi kartu debit pembayaran instan. 

#### Kondisi Lapangan:
1. Sistem multi-region: `ap-southeast-1` (Primary Core) dan `ap-southeast-3` (Secondary Hot-Standby).
2. Tiba-tiba link inter-region private backbone fiber optic terputus (*partitioned*).
3. Latensi sinkronisasi database state global melonjak dari $12\text{ms}$ ke $1.800\text{ms}$ akibat failover routing ke public internet transit.
4. Di saat bersamaan, partner e-commerce terbesar meluncurkan promo tengah malam dengan surge request otorisasi kartu naik $400\%$ di atas kapasitas nominal cluster.
5. Cache cluster (Redis) di region secondary mengalami penggusuran memori (*cache evictions cascade*) sehingga $90\%$ read queries langsung menghantam disk storage database primer.

#### Misi Tantangan:
Rancang **Emergency Incident Architecture Mitigation Plan** komprehensif tanpa boleh mematikan sistem secara total:
1. Definisikan strategi *Data Consistency Trade-off* yang dipilih (apakah membiarkan write loss sementara atau menolak transaksi baru, sertakan justifikasi finansial/operasional).
2. Tentukan algoritma *Load Shedding* dan *Degradation Hierarchy* pada API Gateway Anda: parameter bisnis mana yang dikorbankan pertama kali, dan bagaimana mendistribusikan kuota resource tersisa hanya untuk pengguna premium/transaksi prioritas.
3. Rancang prosedur cold-start/recovery tanpa memicu *Thundering Herd* ke database saat inter-region link kembali online.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Apa definisi dasar dari Service Level Indicator (SLI)?
   - A. Perjanjian kontrak hukum antara vendor dan klien yang disertai penalti finansial.
   - B. Tolok ukur kuantitatif terhadap performa dan keandalan layanan yang diobservasi secara aktual.
   - C. Persentase uptime tahunan yang ditargetkan oleh tim arsitek bisnis.
   - D. Batas toleransi maksimal sistem boleh dimatikan untuk proses maintenance terjadwal.

2. Jika suatu sistem menetapkan target SLO Availability $99.9\%$ dalam kurun waktu 30 hari (dengan total $43.200$ menit), berapakah durasi kumulatif maksimal sistem tersebut boleh mengalami insiden downtime (*Error Budget*)?
   - A. 4,32 menit
   - B. 43,2 menit
   - C. 432 menit
   - D. 4.320 menit

3. Manakah metrik latensi yang paling representatif untuk mengidentifikasi degradasi performa yang dirasakan oleh sebagian kecil segmen pengguna pada distribusi long-tail?
   - A. Arithmetic Mean (Rata-rata)
   - B. Median (P50)
   - C. Modus
   - D. P99 / P99.9 Percentile

4. Apa fungsi utama penerapan mekanisme *Jitter* pada algoritma Exponential Backoff saat client melakukan *retry*?
   - A. Mengompresi ukuran payload HTTP body agar transmisi network lebih cepat.
   - B. Menyebarkan distribusi waktu panggilan client untuk mencegah *thundering herd* dan penumpukan beban sinkron di server downstream.
   - C. Memastikan seluruh paket data terenkripsi ganda di lapisan TLS.
   - D. Menurunkan nilai time-to-live (TTL) paket IP pada level router.

5. Pada arsitektur Circuit Breaker pattern, kondisi di mana sistem mulai mengizinkan sebagian kecil trafik percobaan masuk untuk memverifikasi apakah downstream sudah pulih disebut fase:
   - A. CLOSED
   - B. OPEN
   - C. HALF-OPEN
   - D. BYPASS

---

### Bagian 2: Intermediate (Pilihan Ganda)

6. Pada konsep *Multi-Window Multi-Burn-Rate Alerting*, mengapa evaluasi harus menggabungkan *long-window* dan *short-window* secara simultan?
   - A. Untuk menghemat konsumsi memori Time-Series Database (TSDB).
   - B. Agar alert langsung teresolusi otomatis tanpa campur tangan teknisi on-call.
   - C. Untuk mencegah pengiriman notifikasi palsu (*false alert*) dari spike transien sesaat serta menjamin alert segera berhenti berbunyi begitu masalah downstream selesai.
   - D. Mengubah notifikasi kritis P1 secara instan menjadi notifikasi email non-kritis.

7. Jika burn rate terukur berada pada angka $BR = 14.4$, berapa persen Error Budget bulanan yang akan terkuras habis jika kondisi anomali tersebut dibiarkan berlangsung selama 1 jam?
   - A. $0.5\%$
   - B. $1.0\%$
   - C. $2.0\%$
   - D. $10.0\%$

8. Pendekatan *Adaptive Concurrency Limiting* berbasis delay (seperti Vegas algorithm) mengukur saturasi server internal dengan memantau:
   - A. Total kapasitas RAM yang dialokasikan pada container engine.
   - B. Deviasi antara Round Trip Time aktual ($\text{RTT}_{\text{actual}}$) terhadap batas minimum dasar ($\text{RTT}_{\text{min}}$).
   - C. Jumlah commit code baru pada pipeline continuous deployment.
   - D. Utilisasi storage hard disk pada node logging.

9. Apa risiko arsitektural fatal jika sebuah HTTP reverse proxy/gateway menerapkan timeout nilai besar (misal: 60 detik) pada upstream client connection, namun downstream connection ke database memiliki timeout 3 detik?
   - A. Request akan diblokir oleh sistem firewall upstream.
   - B. Upstream gateway menahan idle thread/koneksi secara berlebihan yang berisiko menguras file descriptor OS saat downstream database melambat.
   - C. Log Prometheus akan mengalami data corruption.
   - D. Database pool secara otomatis menggandakan instance replica.

10. Penerapan *Error Budget Policy* yang ketat di level organisasi menyatakan bahwa jika Error Budget telah habis ($0\%$), maka:
    - A. Gaji tim pengembang dipotong sesuai sisa SLA.
    - B. Semua rilis fungsionalitas/fitur baru dibekukan sementara; kapasitas engineering dialihkan sepenuhnya untuk stabilitas, refactoring, dan perbaikan infrastruktur.
    - C. Semua monitoring dashboard dinonaktifkan sementara agar tim fokus bekerja.
    - D. Target SLO diturunkan secara sepihak agar sistem kembali berada di status aman (*green*).

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario 1**: Tim Anda mengelola microservice `Auth-Token`. Pada pukul 14:00, service downstream Redis cluster mengalami restart otomatis karena upgrade kernel. Grafana mendeteksi lonjakan error $500$ selama 45 detik, menghabiskan $0.3\%$ Error Budget, setelah itu error kembali normal ke baseline $0.001\%$. Namun, teknisi On-Call terbangun karena PagerDuty membunyikan alarm P1 kritis berbasis single-window 1 jam. Evaluasilah penyebab ketidakakuratan alerting tersebut dan rancang solusi arsitekturnya.

12. **Skenario 2**: Service `Catalog-Search` mendadak mengalami *cascading degradation*. CPU utilization melonjak ke $98\%$, latensi meningkat dari $80\text{ms}$ ke $4.500\text{ms}$, sementara downstream Elasticsearch cluster berada dalam kondisi utilisasi rendah ($15\%$). Thread dump profiling menunjukkan ribuan worker thread terhenti (*blocked*) pada status `sync.Mutex.Lock()` di middleware tracking analitik lokal. Bagaimana Anda mengeksekusi mitigasi langsung pada traffic layer untuk memulihkan ketersediaan search engine?

13. **Skenario 3**: Sebuah API endpoint `/process-payroll` memiliki karakteristik transaksi komputasi intensif dan lambat (rata-rata 1,5 detik per proses). Tim Developer mengusulkan penambahan circuit breaker dan retry policy dengan batas retry 5 kali jika terjadi koneksi putus ke database engine. Sebagai SRE, berikan evaluasi kritis Anda terhadap rancangan tersebut ditinjau dari stabilitas database dan *good engineering practices*.

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian 1: Basic
1. **B** — SLI adalah pengukuran aktual kuantitatif terhadap metrik layanan (seperti rasio error atau durasi latensi). Kontrak legal dengan penalti finansial adalah SLA.
2. **B** — Total waktu = $43.200$ menit. Error budget $100\% - 99.9\% = 0.1\%$. Toleransi downtime = $43.200 \times 0.001 = 43,2$ menit.
3. **D** — P99/P99.9 mengisolasi ekor distribusi ekstrem ($1\%$ atau $0.1\%$ transaksi terburuk), di mana rata-rata (mean) menyamarkan masalah tersebut.
4. **B** — Jitter memperkenalkan interval keacakan waktu tunggu pada client sehingga jutaan client tidak membanjiri server pada detik yang persis sama secara sinkron.
5. **C** — HALF-OPEN adalah status evaluasi uji coba pada Circuit Breaker untuk menguji stabilitas dependensi downstream sebelum menutup kembali circuit ke mode operasional penuh (CLOSED).

#### Bagian 2: Intermediate
6. **C** — Long-window menjamin anomali memiliki konsumsi volume yang bermakna (bukan false alarm sesaat), sementara short-window memastikan error masih aktif terjadi saat alert dievaluasi.
7. **C** — Burn rate 1 mengonsumsi $100\%$ budget dalam 720 jam (30 hari). Maka dalam 1 jam, $BR = 1$ mengonsumsi $1/720 = 0.1388\%$ budget. Pada $BR = 14.4$, konsumsi per jam adalah $14.4 \times (100\% / 720) = 2\%$.
8. **B** — Algoritma Vegas mendeteksi antrean paket data (*queue buffer build-up*) dengan mengukur selisih antara waktu respon real-time terhadap batas bawah baseline RTT.
9. **B** — Ketimpangan konfigurasi timeout menyebabkan reverse proxy menahan soket TCP dan pool memory terbuka jauh lebih lama daripada waktu downstream mati, memicu *resource starvation* dan kegagalan kaskade pada edge layer.
10. **B** — Error budget policy adalah kesepakatan tata kelola: menghentikan delivery resiko baru (fitur) dan mengalihkan fokus resource untuk melunasi technical debt yang mengancam keandalan sistem.

#### Bagian 3: Pembahasan Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    - *Akar Masalah*: Sistem alerting menggunakan metode usang: *Single Long-Window Alerting* (1 jam). Spike singkat (45 detik) memiliki area kesalahan cukup tinggi untuk mendongkrak rata-rata error 1 jam ke atas ambang batas, namun sistem sebenarnya telah sehat kembali secara otomatis.
    - *Solusi*: Migrasikan rule ke sistem **Multi-Window Multi-Burn-Rate (MWMRA)**. Konfigurasikan alert agar hanya berbunyi jika error rate melebihi threshold pada window 1 jam DAN window 5 menit secara simultan. Karena window 5 menit segera bersih sesaat pasca Redis pulih, short-window bernilai false dan alert P1 otomatis dibatalkan (*auto-suppressed*).

12. **Analisis Skenario 2**:
    - *Akar Masalah*: Bottleneck terjadi di aplikasi lokal akibat *thread contention lock* pada middleware non-kritis (analitik). Elasticsearch tidak bersalah.
    - *Mitigasi Cepat*:
      1. Eksekusi runtime config dynamic update: Nonaktifkan (bypass) middleware analitik secara hot-reload (atau alihkan ke asynchronous in-memory channel dengan strategi *drop-on-full*).
      2. Jika dynamic flag tidak tersedia, deploy patch darurat atau bypass via edge proxy routing rule untuk mengabaikan path/pipeline analitik tersebut. Sistem core search akan langsung terbebas dari mutex lock contention.

13. **Analisis Skenario 3**:
    - *Kritik SRE*: Usulan developer berbahaya bagi sistem produksi (*catastrophic design*).
    - *Alasan*: Menambahkan policy retry 5x pada transaksi lambat (1,5 detik) yang sedang menghadapi masalah database akan memperbesar volume beban trafik database sebesar **$500\%$ ($6\times$ total request)** pada saat database justru sedang tertekan (*retry storm*). Ini akan mempercepat degradasi DB menjadi *unrecoverable crash*.
    - *Rekomendasi*:
      1. Retry harus dibatasi maksimal 1-2 kali dengan algoritma *Full Jitter Exponential Backoff*.
      2. Wajib menerapkan *Idempotency-Key* untuk mencegah penggajian ganda (*duplicate payroll execution*).
      3. Jika database overload, terapkan *Fail-Fast* dengan Circuit Breaker dan kembalikan response 503 dengan header `Retry-After`.

---

## 16. Summary

Fondasi keandalan sistem (*reliability*) dalam rekayasa SRE tingkat lanjut bertumpu pada keyakinan bahwa seluruh infrastruktur, dependensi, dan perangkat keras rentan mengalami kegagalan kapan saja. Keandalan tercapai bukan melalui penolakan terhadap kegagalan, melainkan melalui desain toleransi kegagalan yang adaptif dan terukur.

Empat pilar utama implementasi arsitektur SRE produksi meliputi:
1. **Mathematical SLO & Error Budget Governance**: Menerapkan metrik terukur berbasis persentil (P99/P99.9) dan sistem Multi-Window Multi-Burn-Rate Alerting untuk memotong noise operasional, serta menjadikan sisa Error Budget sebagai kontrol otomatis pada rilis CI/CD.
2. **Defensive Structural Resilience**: Melindungi service runtime dari degradasi downstream melalui kombinasi *Adaptive Concurrency Limiting*, *Circuit Breaking*, *Timeouts & Context Deadline Propagation*, dan *Load Shedding* berbasis prioritas muatan data.
3. **Prevention of Cascading Failures**: Menghilangkan fenomena *Retry Storms* menggunakan Exponential Backoff dan Jitter, serta mendesain sistem dengan prinsip *Graceful Degradation* (*Fail-Open* pada komponen Tier-2/non-kritis).
4. **Data-Driven Incident Feedback Loop**: Mengonversi setiap kegagalan infrastruktur produksi menjadi peningkatan sistematis lewat *Blameless Post-Mortem* dan penutupan celah ketahanan sistem secara berkelanjutan.