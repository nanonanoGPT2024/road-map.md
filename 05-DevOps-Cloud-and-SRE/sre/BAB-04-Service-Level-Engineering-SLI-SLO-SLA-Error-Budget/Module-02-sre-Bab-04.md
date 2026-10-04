# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Service-Level Engineering (SLI, SLO, SLA, Error Budget)**
**Jalur Pembelajaran: 05-DevOps-Cloud-and-SRE**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur SLI Pipeline:** Membangun pipeline pengukuran *Service Level Indicator* (SLI) end-to-end dengan presisi tinggi menggunakan Prometheus, OpenTelemetry, dan engine agregasi metrik terdistribusi (Thanos/Cortex/M3DB).
2. **Memformulasikan Multi-Window Multi-Burn-Rate Alerting:** Menghitung dan mengonfigurasi algoritma deteksi konsumsi *Error Budget* berbasis jendela waktu ganda (*short-window* vs. *long-window*) untuk mengeliminasi *alert fatigue* sekaligus memitigasi risiko degradasi laten.
3. **Mengotomatisasi Kebijakan Error Budget (Governance-as-Code):** Mengintegrasikan status konsumsi *Error Budget* ke dalam pipeline CI/CD (misalnya Argo Rollouts atau Keptn) untuk memblokir rilis secara otomatis (*deployment freeze*) saat SLO terlanggar.
4. **Mengatasi Distorsi Matematika pada Metrik Agregasi:** Menghindari bias statistik akibat *histogram quantile averaging*, *sampling error*, dan anomali kardinalitas tinggi pada komputasi persentil ($p90, p99, p99.9$).
5. **Menerapkan Standar OpenSLO dan Sloth:** Mengabstraksikan definisi keandalan ke dalam format deklaratif *GitOps-ready* yang otomatis dikompilasi menjadi Prometheus alerting and recording rules.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **Prinsip Dasar SRE (Bab 04 Modul 01):** Konsep fundamental SLI, SLO, SLA, dan formula dasar *Error Budget* ($\text{Error Budget} = 100\% - \text{SLO}$).
* **PromQL Lanjutan:** Memahami operasi vektor (*instant* dan *range vectors*), fungsi `rate()`, `increase()`, `histogram_quantile()`, manipulasi label, dan agregator `sum() without/by()`.
* **Arsitektur Kubernetes & Observability:** Pemahaman mengenai Kubernetes CRD, Service Mesh (Envoy/Istio), ingress telemetry, dan stack Prometheus Operator.
* **Statistika Dasar Sistem Terdistribusi:** Pengetahuan tentang distribusi probabilitas, hukum *Little's Law*, konsep *heavy-tailed distribution*, dan bahaya metrik rata-rata (*mean average trap*).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Landasan Matematika SLI dan Error Budget

Dalam sistem produksi modern berkecepatan tinggi, pengukuran keandalan mengandalkan model berbasis rasio kejadian (*event-based ratio model*):

$$\text{SLI} = \frac{\sum \text{Good Events}}{\sum \text{Valid Events}} = 1 - \frac{\sum \text{Bad Events}}{\sum \text{Valid Events}}$$

Jika target SLO ditetapkan sebesar $L$ (misal $99.9\%$), maka rasio kegagalan maksimum yang diizinkan (*Unreliability Target*) adalah:

$$E = 1 - L = 1 - 0.999 = 0.001 \quad (0.1\%)$$

*Error Budget* merepresentasikan total unit kegagalan yang dapat ditoleransi dalam suatu jendela waktu kepatuhan $T$ (misal 30 hari atau 720 jam).

### 3.2 Burn Rate Dynamics

*Burn Rate* ($B$) mendefinisikan kecepatan konsumsi *Error Budget* relatif terhadap laju konsumsi normal yang menghabiskan tepat 100% budget dalam periode $T$:

$$B = \frac{\text{Laju Konsumsi Aktual}}{\text{Laju Konsumsi Normal}}$$

* $B = 1$: Menghabiskan 100% Error Budget tepat dalam durasi $T$.
* $B > 1$: Menghabiskan Error Budget lebih cepat daripada periode target.
* $B = 14.4$: Menghabiskan 100% Error Budget (30 hari) hanya dalam waktu **2 hari** (5% budget habis dalam 1 jam).

Hubungan antara Burn Rate ($B$), persentase budget yang dikonsumsi ($P$), durasi insiden ($t$), dan periode kepatuhan ($T$) didefinisikan sebagai:

$$P = B \times \frac{t}{T} \iff B = \frac{P \times T}{t}$$

Contoh: Jika target konsumsi adalah 2% ($P=0.02$) dari total periode 30 hari ($T=720\text{ jam}$) dalam waktu 1 jam ($t=1\text{ jam}$):

$$B = \frac{0.02 \times 720}{1} = 14.4$$

### 3.3 Multi-Window Multi-Burn-Rate Alerting Architecture

Alerting konvensional (misal CPU > 80% atau Error > 1%) menghasilkan *false positive* tinggi atau terlambat mendeteksi degradasi sistem. Standar industri enterprise mengadopsi algoritma **Multi-Window Multi-Burn-Rate Alerting** (Google SRE Standard):

```
       Jendela Panjang (Long Window)
+-----------------------------------------------------------+
|                                                           |
|       Jendela Pendek (Short Window)                       |
|   +-----------------------+                               |
|   |                       |                               |
+---+-----------------------+-------------------------------+--> Waktu
0  t_short                 t_long
```

Sebuah notifikasi kritis (halaman on-call) **hanya ditembakkan** jika dua kondisi terpenuhi secara simultan:
1. **Long Window Condition:** Rata-rata laju error rate selama jendela panjang ($t_{long}$) melebihi $B \times (1 - \text{SLO})$.
2. **Short Window Condition:** Rata-rata laju error rate selama jendela pendek ($t_{short}$, umumnya $\frac{1}{12}$ dari $t_{long}$) juga melebihi $B \times (1 - \text{SLO})$.

Tujuan jendela pendek adalah memastikan bahwa insiden **masih berlangsung saat ini**, sehingga sistem tidak mengirimkan alert untuk *spike* singkat yang sudah terisolasi dan selesai.

#### Standar Matriks Alerting (Google SRE Framework untuk Periode 30 Hari)

| Severity / Channel | Burn Rate ($B$) | % Budget Terkonsumsi | Jendela Panjang ($t_{long}$) | Jendela Pendek ($t_{short}$) | Waktu Habis Total Budget |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Critical (Page/SMS)** | 14.4 | 2% | 1 jam | 5 menit | 2 hari (50 jam) |
| **Critical (Page/SMS)** | 6.0 | 5% | 6 jam | 30 menit | 5 hari (120 jam) |
| **High (Ticket/Chat)** | 3.0 | 10% | 3 hari (72 jam) | 6 jam | 10 hari (240 jam) |
| **Medium (Ticket/Dashboard)** | 1.0 | 10% | 3 hari (72 jam) | 6 jam | 30 hari (720 jam) |

### 3.4 Arsitektur Telemetri & Ingestion Engine

```
[ Clients ] 
     │
     ▼
[ Ingress / API Gateway (Envoy/Kong) ] ──(Raw Traces/Logs)──► [ OTel Collector ]
     │                                                               │
     ├─(HTTP Metrics: status, latency)                               │
     ▼                                                               ▼
[ Kubernetes Microservices (App Engine) ]                      [ Long-term TSDB ]
     │                                                         (Thanos / Cortex)
     ├─(Internal Business SLI Counters)                              ▲
     ▼                                                               │
[ Prometheus Operator Scrape Pool ] ─────────────────────────────────┘
     │
     ├─► [ Sloth / Pyrra (SLO CRD Controller) ]
     │        │
     │        ▼
     ├─► [ PrometheusRules (Generated Recording & Alerting Rules) ]
     │        │
     │        ▼
     └─► [ Alertmanager ] ──► [ PagerDuty / Webhook Enforcement ]
                                       │
                                       ▼
                       [ CI/CD Engine (Argo Rollouts) ]
```

Pipeline di atas menjamin decoupling antara kode aplikasi, deklarasi SLO, dan mesin kalkulasi rules. Operator tidak perlu menulis kueri PromQL raw ribuan baris secara manual; operator mendefinisikan *SLO Specification*, lalu compiler otomatis menghasilkan *PrometheusRule* yang memonitor jendela pendek dan jendela panjang.

---

## 4. Why & What

### Mengapa Pendekatan Statis Tradisional Gagal di Produksi Enterprise?

1. **Threshold Fallacy:** Threshold statis (misal: "kirim alert jika HTTP 5xx > 10 req/s") mengabaikan dinamika throughput. Saat *traffic surge* 100.000 req/s, 10 error/s merepresentasikan availability 99.99% (normal). Saat *traffic drop* malam hari ke 20 req/s, 10 error/s berarti availability terjun ke 50% (krisis fatal).
2. **Deteksi Laten (Slow Leaks):** Kebocoran memori atau degradasi performa kecil (error 0.2% pada SLO 99.9%) tidak akan pernah memicu alert statis, namun secara bertahap menghabiskan seluruh error budget dalam kurun waktu dua minggu tanpa terdeteksi.
3. **Alert Fatigue:** Alert berbasis single window berdurasi pendek memicu "badai alert" dari transient errors (seperti restart pod sementara atau timeout periodik). Sebaliknya, window terlalu panjang terlambat membangunkan tim saat terjadi outage total.

### Apa Solusi Service-Level Engineering Lanjutan?

* **OpenSLO Specification:** Format standar terbuka (*vendor-agnostic*) untuk mendefinisikan Service Level Objective secara deklaratif dalam ekosistem GitOps.
* **Recording Rules Agregasi Bertingkat:** Menghitung SLI menggunakan PromQL yang diproses secara *pre-computed* melalui Prometheus recording rules, mencegah kelebihan beban query engine TSDB saat evaluasi multi-window.
* **Automated Circuit-Breaking Deployments:** Menghubungkan Error Budget Burn Rate secara langsung dengan controller deployment Kubernetes untuk membatalkan canary rollouts secara instan saat terjadi degradasi metrik.

---

## 5. How (Workflow Detail)

Berikut adalah tahapan implementasi Service-Level Engineering dari instrumen hingga otomasi governance:

```
[ Tahap 1: Kategorisasi SLI ]
  - Filter Synthetic vs Real-User traffic
  - Klasifikasi status code (Client Error vs Server Error)
               │
               ▼
[ Tahap 2: Definisi Indikator (Instrumentation) ]
  - Instrumentasi Prometheus Counter & Histogram
  - Atur bucket latensi secara eksponensial dekat ambang batas SLO
               │
               ▼
[ Tahap 3: Deklarasi SLI/SLO via Sloth/OpenSLO CRD ]
  - Definisikan Service, SLO target, dan Time Window
  - Sloth men-generate Alerting & Recording Rules otomatis
               │
               ▼
[ Tahap 4: Pre-computation via Prometheus Recording Rules ]
  - Hitung rate(bad_events[window]) & rate(valid_events[window])
  - Simpan ke metric TSDB baru: sli:error_rate:ratio_rate*
               │
               ▼
[ Tahap 5: Multi-Burn-Rate Alert Evaluation ]
  - Alertmanager mengevaluasi kombinasi short-window & long-window
  - Notifikasi dialirkan ke PagerDuty, Slack, atau Webhook API
               │
               ▼
[ Tahap 6: Error Budget Gatekeeper Enforcement ]
  - Webhook memicu freeze policy di CI/CD
  - Membatalkan pipeline canary atau rollout cluster
```

### Mekanisme Pengukuran Quantile vs Histogram

Untuk latency SLI ($p99 < 200\text{ms}$):
1. **Jangan Gunakan Summary:** `summary` Prometheus tidak dapat diagregasikan antar-pod atau cluster.
2. **Gunakan Histogram dengan Bucket Terkalibrasi:** Tentukan bucket yang rapat di sekitar target (misal: `[0.05, 0.1, 0.15, 0.18, 0.2, 0.25, 0.5, 1.0]`).
3. **Formulasi Rasio:** Hindari fungsi lambat `histogram_quantile()`. Alihkan penghitungan ke model event ratio:

$$\text{SLI}_{\text{latency}} = \frac{\sum \text{rate}(http\_request\_duration\_seconds\_bucket\{le="0.2"\}[window])}{\sum \text{rate}(http\_request\_duration\_seconds\_count[window])}$$

Formulasi rasio ini secara komputasi jauh lebih ringan bagi Prometheus TSDB dan linear untuk diagregasikan di multi-cluster.

---

## 6. Analogy & Diagram ASCII

### Analogi: Mobil Balap Formula 1 & Tangki Bahan Bakar

Bayangkan sebuah mobil balap Formula 1 yang harus menyelesaikan 60 lap:
* **Error Budget:** Kapasitas bahan bakar cadangan yang boleh dikonsumsi tanpa merusak mesin.
* **SLO (99.9%):** Aturan bahwa mobil harus melaju pada batas aman bahan bakar tersebut.
* **Burn Rate = 1.0:** Kecepatan konsumsi bahan bakar standar. Mobil akan kehabisan bahan bakar cadangan tepat saat melewati garis finish di lap 60.
* **Burn Rate = 14.4:** Injektor bahan bakar bocor hebat! Bahan bakar cadangan akan ludes dalam 4 lap pertama balapan. Mekanik harus membunyikan alarm radio darurat (*Page/SMS Alert*) agar pembalap segera masuk pit stop.
* **Burn Rate = 3.0:** Konsumsi bahan bakar sedikit terlalu boros, akan habis di lap 20. Mekanik cukup mengirim instruksi lewat dashboard kokpit (*Ticket Alert*) untuk menyesuaikan gaya mengemudi.
* **Dual-Window System:** Memastikan bahwa mekanik tidak memanggil pit stop hanya karena pembalap menekan gas penuh (*spike*) selama 2 detik saat menyalip musuh.

### Diagram Arsitektur Multi-Window Multi-Burn-Rate Engine

```
                             +--------------------------------------------+
                             |       Incoming Requests (Traffic)         |
                             +--------------------------------------------+
                                                    │
                                                    ▼
                             +--------------------------------------------+
                             | API Gateway: Envoy / NGINX / Kong          |
                             |  - Exposes: http_requests_total            |
                             +--------------------------------------------+
                                                    │
                                                    ▼
                             +--------------------------------------------+
                             | Prometheus TSDB Scrape Engine              |
                             +--------------------------------------------+
                                                    │
                   ┌────────────────────────────────┴────────────────────────────────┐
                   ▼                                                                 ▼
+------------------------------------+                             +------------------------------------+
| Recording Rule (Window Pendek)     |                             | Recording Rule (Window Panjang)    |
| sli:error:ratio_rate5m             |                             | sli:error:ratio_rate1h             |
| Evaluasi interval: 30 detik        |                             | Evaluasi interval: 30 detik        |
+------------------------------------+                             +------------------------------------+
                   │                                                                 │
                   └────────────────────────────────┬────────────────────────────────┘
                                                    │
                                                    ▼
                                   +---------------------------------+
                                   | Logical AND Condition           |
                                   |  (ratio_rate1h > Target * Burn) |
                                   |               AND               |
                                   |  (ratio_rate5m > Target * Burn) |
                                   +---------------------------------+
                                                    │
                                          Alert State = FIRING
                                                    │
                                                    ▼
                                   +---------------------------------+
                                   | Alertmanager Dispatcher         |
                                   +---------------------------------+
                                        │                       │
                       Severity: Critical                       Severity: Warning
                                        │                       │
                                        ▼                       ▼
                           [ PagerDuty On-Call ]      [ Jira Ticket / Slack ]
                                        │
                                        ▼
                        [ Argo Rollouts Abort Hook ]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: PromQL Native Multi-Burn-Rate Query

Berikut adalah contoh raw PromQL alert untuk availability $99.9\%$ dengan window $1\text{ jam}$ (short: $5\text{ menit}$) pada Burn Rate $14.4$:

Target error rate ($1 - 0.999 = 0.001$).
Ambang batas: $14.4 \times 0.001 = 0.0144$ ($1.44\%$ error).

```promql
# Long window (1 jam) melebihi batas 1.44%
(
  sum(rate(http_requests_total{job="payment-service", status=~"5.."}[1h]))
  /
  sum(rate(http_requests_total{job="payment-service"}[1h]))
) > (14.4 * (1 - 0.999))
and
# Short window (5 menit) juga melebihi batas 1.44%
(
  sum(rate(http_requests_total{job="payment-service", status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{job="payment-service"}[5m]))
) > (14.4 * (1 - 0.999))
```

### 7.2 Practical Example: Deklarasi SLI/SLO Enterprise Menggunakan Sloth

Simpan manifest berikut sebagai `sloth-payment-slo.yaml`. Sloth akan meng-compile file ini menjadi `PrometheusRule` Kubernetes resource yang lengkap dengan recording rules multi-window multi-burn-rate.

```yaml
version: "prometheus/v1"
service: "payment-gateway"
labels:
  team: "core-banking"
  tier: "tier-0"

slos:
  - name: "requests-availability"
    objective: 99.95
    description: "Memastikan ketersediaan transaksi pembayaran API Gateway HTTP 5xx di bawah 0.05%."
    sli:
      events:
        error_query: >-
          sum(rate(http_requests_total{job="payment-api", status=~"5.."}[{{.window}}]))
          OR on() vector(0)
        total_query: >-
          sum(rate(http_requests_total{job="payment-api"}[{{.window}}]))
    alerting:
      name: "PaymentGatewayAvailabilityAlert"
      labels:
        category: "availability"
      annotations:
        summary: "Tingkat error HTTP pembayaran melebihi ambang batas Error Budget."
        runbook: "https://wiki.internal.enterprise/ops/runbooks/payment-sli-breach"
      page_alert:
        labels:
          severity: "critical"
          pager: "pagerduty-core-oncall"
      ticket_alert:
        labels:
          severity: "warning"
          pager: "jira-automation"

  - name: "requests-latency"
    objective: 99.0
    description: "99% transaksi pembayaran harus dieksekusi di bawah 250ms."
    sli:
      events:
        error_query: >-
          (
            sum(rate(http_request_duration_seconds_count{job="payment-api"}[{{.window}}]))
            -
            sum(rate(http_request_duration_seconds_bucket{job="payment-api", le="0.25"}[{{.window}}]))
          ) OR on() vector(0)
        total_query: >-
          sum(rate(http_request_duration_seconds_count{job="payment-api"}[{{.window}}]))
    alerting:
      name: "PaymentGatewayLatencyAlert"
      page_alert:
        labels:
          severity: "critical"
```

### 7.3 Hasil Kompilasi PrometheusRule (Cuplikan Otomatis Sloth)

Potongan rules berikut menunjukkan komputasi efisien yang dihasilkan compiler:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: sloth-slo-payment-gateway-requests-availability
  labels:
    role: alert-rules
    team: core-banking
spec:
  groups:
  - name: sloth-slo-sli-recordings-payment-gateway-requests-availability
    rules:
    - record: "slo:sli_error:ratio_rate5m"
      expr: >-
        (sum(rate(http_requests_total{job="payment-api", status=~"5.."}[5m])) OR on() vector(0))
        /
        sum(rate(http_requests_total{job="payment-api"}[5m]))
      labels:
        sloth_id: payment-gateway-requests-availability
        sloth_service: payment-gateway
    - record: "slo:sli_error:ratio_rate1h"
      expr: >-
        (sum(rate(http_requests_total{job="payment-api", status=~"5.."}[1h])) OR on() vector(0))
        /
        sum(rate(http_requests_total{job="payment-api"}[1h]))
      labels:
        sloth_id: payment-gateway-requests-availability
        sloth_service: payment-gateway

  - name: sloth-slo-alerts-payment-gateway-requests-availability
    rules:
    - alert: PaymentGatewayAvailabilityAlertCritical
      expr: >-
        (
          slo:sli_error:ratio_rate5m{sloth_id="payment-gateway-requests-availability"} > (14.4 * (1 - 0.9995))
          and
          slo:sli_error:ratio_rate1h{sloth_id="payment-gateway-requests-availability"} > (14.4 * (1 - 0.9995))
        )
      for: 2m
      labels:
        severity: critical
        pager: pagerduty-core-oncall
      annotations:
        summary: "Critical budget burn rate (14.4) on payment gateway!"
```

---

## 8. Real World Case Study: Enterprise Core Banking Payment Engine

### Konteks Kasus
Sebuah bank digital memproses rata-rata 35.000 transaksi/detik (TPS) pada sistem pembayaran QRIS & RTGS. Mereka terikat regulasi kepatuhan finansial dengan SLA $99.99\%$ ketersediaan bulanan. Total downtime yang diizinkan hanya **4.32 menit per bulan**.

### Permasalahan
* Tim Core Banking menerapkan threshold alert sederhana: `sum(rate(errors[1m])) > 10`.
* Saat terjadi gangguan parsial pada database connection pool di salah satu Availability Zone (AZ), laju error naik tipis sebesar $0.1\%$ ($35\text{ TPS}$ gagal dari $35.000\text{ TPS}$).
* Alert statis gagal mendeteksi insiden ini karena rasio kegagalan dianggap kecil.
* Namun, dalam durasi 72 jam, insiden tak terdeteksi tersebut telah menghabiskan **720% dari seluruh Error Budget bulanan**, melanggar regulasi SLA regulator nasional dan memicu denda finansial senilai ratusan juta rupiah.

### Solusi Arsitektur SRE

```
                                  [ Ingress Traffic ]
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
         [ Zone-A Gateway ]                              [ Zone-B Gateway ]
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          │
                                  [ Metrics Scrape ]
                                          │
                                          ▼
                             [ Thanos Multi-Cluster TSDB ]
                                          │
                                          ▼
                            [ Sloth SLO Computation Engine ]
                                          │
                ┌─────────────────────────┴─────────────────────────┐
                ▼                                                   ▼
   [ Burn Rate = 14.4 (1h/5m) ]                         [ Burn Rate = 3.0 (72h/6h) ]
                │                                                   │
                ▼                                                   ▼
     [ Critical Pager Alert ]                              [ Ticket Automation ]
                │                                                   │
                ▼                                                   ▼
   [ PagerDuty On-Call Paged ]                             [ Automated Policy ]
                │                                                   │
                ▼                                                   ▼
   [ Argo Rollouts Block Deploy ]                         [ Drain Degraded AZ Pods ]
```

1. **Implementasi Multi-Burn-Rate Alerts:**
   * Ditambahkan deteksi burn rate bertingkat: $14.4\times$ ($2\%$ budget dalam 1 jam), $6\times$ ($5\%$ budget dalam 6 jam), dan $3\times$ ($10\%$ budget dalam 3 hari).
   * Alert Burn Rate $3\times$ berhasil mendeteksi kebocoran error $0.1\%$ dalam waktu **36 menit** sejak anomali connection pool muncul.
2. **Automated Error Budget Policy Enforcement:**
   * Script webhook otomatis dipasang pada Alertmanager.
   * Saat `Burn Rate >= 6` menyala, webhook memanggil Argo Rollouts API untuk mengeksekusi perintah `abort` pada semua pipeline deployment yang sedang berjalan di production.
   * Traffic router otomatis mengisolasi koneksi database di AZ yang terdegradasi.

### Hasil Kuantitatif (Post-Implementation)
* **MTTD (Mean Time to Detect):** Turun drastis dari **72 jam** menjadi **36 menit** untuk insiden berkategori *slow leak*.
* **SLA Breach Prevention:** Tidak ada pelanggaran SLA regulasi selama 4 kuartal berturut-turut.
* **Alert Noise Reduction:** Penurunan *false positive pages* on-call engineer sebesar **84%**.

---

## 9. Trade-offs: Analisis Komparasi Arsitektur

| Pendekatan | Kelebihan | Kelemahan | Trade-off Utama |
| :--- | :--- | :--- | :--- |
| **Rolling Window vs Calendar Window** | *Rolling Window* (30 hari terakhir) mencerminkan pengalaman riil user terkini tanpa *cliff-edge* di akhir bulan. | *Calendar Window* (1-30 bulan berjalan) lebih mudah disesuaikan dengan kontrak SLA legal bisnis. | **Engineering Precision vs Business/Legal Compliance.** Praktik terbaik: Gunakan Rolling Window untuk Alerting internal & Calendar Window untuk pelaporan SLA eksternal. |
| **High Frequency Evaluation (10s vs 60s)** | Mendeteksi degradasi instan (MTTD lebih cepat beberapa detik). | Beban CPU dan IOPS pada TSDB (Prometheus/Thanos) membengkak signifikan hingga 600%. | **Detection Speed vs TSDB Compute Cost.** Standar optimal enterprise: 30s - 60s untuk evaluasi rules. |
| **Histogram Quantiles vs Good/Bad Ratio** | Memberikan gambaran sebaran latensi penuh ($p50, p90, p99$). | Operasi `histogram_quantile()` di PromQL sangat berat (*expensive scan*), rawan bias interpolasi bucket. | **Flexibility vs Scalability.** Gunakan ratio events ($le="ambang\_batas"$) untuk SLO, simpan histogram quantiles hanya untuk dashboard debugging. |
| **Aggressive Automated Freeze vs Manual Approvals** | Menghentikan *human error* dan mencegah degradasi meluas saat budget habis. | Dapat memblokir hotfix/patch penting jika policy gatekeeper tidak dirancang dengan jalur *bypass emergency*. | **Reliability Guardrails vs Engineering Velocity.** Wajib menyediakan label `emergency-hotfix-bypass` pada pipeline. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Percentile Averaging Fallacy (Dosa Besar SRE)
* **Kesalahan Fatal:** Menghitung rata-rata dari metrik persentil pod.
  ```promql
  # SALAH BESAR - TIDAK VALID SECARA STATISTIK
  avg(histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, pod)))
  ```
* **Dampak:** Nilai rata-rata dari p99 secara matematis mematikan pembacaan lonjakan ekstrem (outliers). Sistem tampak normal, padahal $1\%$ pengguna mengalami outage parah.
* **Perbaikan:** Lakukan agregasi bucket mentah terlebih dahulu di tingkat cluster sebelum memanggil fungsi quantile:
  ```promql
  # BENAR
  histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
  ```

### 2. Missing Short-Window Guardrail pada Alerting
* **Kesalahan:** Alerting hanya memonitor jendela 1 jam tanpa menyandingkan jendela 5 menit.
* **Dampak:** Saat terjadi spike error 100% selama 1 menit (misal akibat restart database pod), sistem pulih di menit ke-2. Namun, alert 1 jam akan terus berstatus `FIRING` selama 59 menit berikutnya. Engineer on-call terbangun jam 3 pagi untuk insiden yang sudah lama selesai.
* **Perbaikan:** Wajib gunakan klausa `AND` dengan *short window* ($t_{short} = t_{long} / 12$).

### 3. Salah Menangani Downstream Client Errors (4xx vs 5xx)
* **Kesalahan:** Menganggap semua HTTP 4xx murni kesalahan klien sehingga diabaikan total dari SLI.
* **Dampak:** Jika engineer meluncurkan rilis aplikasi yang secara keliru mengubah skema auth dan menyebabkan semua permintaan valid ditolak dengan HTTP 401 Unauthorized atau 403 Forbidden, SLI availability 5xx tetap hijau 100%, menyembunyikan outage masif.
* **Perbaikan:** Pisahkan SLI: Bedakan HTTP 400/404 umum dengan HTTP 401/403/429. Masukkan HTTP 401/403/429 ke dalam *Bad Events* jika anomali melompat di atas baseline historis normal.

---

## 11. Best Practices (Production Checklist)

### Perancangan SLI/SLO
- [ ] SLI dihitung berdasarkan perspektif pengguna akhir (*user-centric*), diposisikan di level ingress atau load balancer.
- [ ] Ambang batas latensi menggunakan penghitungan rasio berbasis bucket tetap, bukan quantile run-time.
- [ ] Pengecualian lalu lintas non-user (health checks, scraping Prometheus, canary probes sintesis) dari kueri SLI.

### Alerting & Multi-Burn-Rate
- [ ] Seluruh alert kritis (halaman PagerDuty) menggunakan multi-window multi-burn-rate ($14.4\times$ dan $6.0\times$).
- [ ] Jendela pendek dikonfigurasi tepat $\frac{1}{12}$ dari durasi jendela panjang.
- [ ] Setiap alert terikat langsung dengan runbook URL yang valid dan teruji.
- [ ] Tidak ada alert berbasis ambang batas statis single-metric untuk service Tier-0 dan Tier-1.

### Governance & Error Budget
- [ ] Definisi SLO dikelola secara deklaratif menggunakan GitOps (misal: Sloth atau Pyrra CRDs).
- [ ] Pipeline CI/CD membaca status Error Budget sebelum memulai *progressive rollouts*.
- [ ] Dokumen Error Budget Policy ditandatangani bersama oleh Product Owner, Engineering Lead, dan tim SRE.
- [ ] Mekanisme bypass darurat terdokumentasi dan diaudit ketat saat kebijakan deployment freeze aktif.

---

## 12. Hands-on Practice: Implementasi Multi-Burn-Rate Alert Engine Menggunakan Sloth & Prometheus

Praktik ini mensimulasikan penerapan SLO end-to-end pada lingkungan lokal/sandbox. Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`.

### Struktur Direktori
```
hands-on/m02/
├── docker-compose.yaml
├── prometheus/
│   └── prometheus.yml
├── sloth/
│   └── slo-definition.yaml
├── traffic-generator/
│   └── simulate.sh
└── app/
    └── main.go
```

### Langkah 1: Siapkan Sampel Microservice (Target Aplikasi)
Simpan di `hands-on/m02/app/main.go`:
```go
package main

import (
	"math/rand"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	httpRequests = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests processed",
		},
		[]string{"code", "method"},
	)
)

func init() {
	prometheus.MustRegister(httpRequests)
}

func handler(w http.ResponseWriter, r *http.Request) {
	// Simulasi injeksi kegagalan via query param ?fail=true
	if r.URL.Query().Get("fail") == "true" || rand.Float64() < 0.05 { // default 5% error
		httpRequests.WithLabelValues("500", r.Method).Inc()
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Server Error"))
		return
	}
	httpRequests.WithLabelValues("200", r.Method).Inc()
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func main() {
	rand.Seed(time.Now().UnixNano())
	http.HandleFunc("/api/v1/checkout", handler)
	http.Handle("/metrics", promhttp.Handler())
	http.ListenAndServe(":8080", nil)
}
```

### Langkah 2: Buat Definisi Sloth SLO
Simpan di `hands-on/m02/sloth/slo-definition.yaml`:
```yaml
version: "prometheus/v1"
service: "order-service"
labels:
  tier: "tier-1"
slos:
  - name: "checkout-availability"
    objective: 99.5
    description: "99.5% dari checkout requests harus menghasilkan respons sukses (Non-5xx)."
    sli:
      events:
        error_query: sum(rate(http_requests_total{job="order-app", code=~"5.."}[{{.window}}])) OR on() vector(0)
        total_query: sum(rate(http_requests_total{job="order-app"}[{{.window}}]))
    alerting:
      name: "CheckoutAvailabilityBurnRateExhaustion"
      page_alert:
        labels:
          severity: "critical"
      ticket_alert:
        labels:
          severity: "warning"
```

### Langkah 3: Konfigurasi Docker Compose Stack
Simpan di `hands-on/m02/docker-compose.yaml`:
```yaml
services:
  app:
    build:
      context: ./app
      dockerfile: Dockerfile
    ports:
      - "8080:8080"

  prometheus:
    image: prom/prometheus:v2.45.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./generated-rules:/etc/prometheus/rules
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --web.enable-lifecycle

  sloth:
    image: slok/sloth:v0.11.0
    volumes:
      - ./sloth:/sloth-input
      - ./generated-rules:/sloth-output
    command:
      - generate
      - -i=/sloth-input/slo-definition.yaml
      - -o=/sloth-output/slo-rules.yaml
```

*Dockerfile untuk app (`hands-on/m02/app/Dockerfile`):*
```dockerfile
FROM golang:1.20-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 go build -o /app main.go

FROM alpine:latest
COPY --from=builder /app /app
EXPOSE 8080
ENTRYPOINT ["/app"]
```

*Config Prometheus (`hands-on/m02/prometheus/prometheus.yml`):*
```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

rule_files:
  - /etc/prometheus/rules/*.yaml

scrape_configs:
  - job_name: "order-app"
    static_configs:
      - targets: ["app:8080"]
```

### Langkah 4: Eksekusi dan Verifikasi
1. Jalankan compiler Sloth untuk memproduksi Prometheus Rule:
   ```bash
   mkdir -p generated-rules
   docker run --rm -v $(pwd)/sloth:/in -v $(pwd)/generated-rules:/out \
     slok/sloth:v0.11.0 generate -i /in/slo-definition.yaml -o /out/slo-rules.yaml
   ```
2. Nyalakan infrastruktur:
   ```bash
   docker compose up -d app prometheus
   ```
3. Kirim beban traffic normal (success traffic):
   ```bash
   for i in {1..500}; do curl -s "http://localhost:8080/api/v1/checkout" > /dev/null; sleep 0.05; done
   ```
4. Simulasikan outage dengan laju error tinggi (memicu Burn Rate 14.4x):
   ```bash
   for i in {1..200}; do curl -s "http://localhost:8080/api/v1/checkout?fail=true" > /dev/null; sleep 0.02; done
   ```
5. Akses Prometheus UI di `http://localhost:9090/alerts` dan amati alert `CheckoutAvailabilityBurnRateExhaustion` bertransisi dari status `PENDING` ke `FIRING`.

---

## 13. Exercise

### Latihan 1: Level Easy
Diberikan SLO Availability sebesar $99.9\%$ untuk periode kepatuhan 30 hari. 
1. Hitung rasio toleransi error ($E$).
2. Hitung persentase Error Budget yang terkonsumsi jika sistem mengalami downtime total ($100\%$ failure) selama tepat 14.4 menit.
3. Tentukan nilai Burn Rate ($B$) selama periode insiden 14.4 menit tersebut.

### Latihan 2: Level Medium
Tuliskan Prometheus Alerting Rule (`expr`) secara manual tanpa framework compiler untuk mendeteksi kondisi berikut:
* **Service:** `cart-service`
* **Target SLO:** $99.0\%$
* **Metrik:** `checkout_requests_total{status=~"5.."}` dan `checkout_requests_total`
* **Jendela:** Long Window $6\text{ jam}$ dan Short Window $30\text{ menit}$.
* **Burn Rate:** $6.0$.

### Latihan 3: Level Hard
Buat script Go atau Python yang berfungsi sebagai Webhook Admission Controller / CI-CD Gatekeeper. 
Script ini harus:
1. Menerima query request dari pipeline CI/CD sebelum deployment dimulai.
2. Melakukan query ke API Prometheus untuk mengambil nilai metrik recording rule `slo:sli_error:ratio_rate1h{sloth_id="payment-gateway-requests-availability"}`.
3. Menghitung sisa error budget bulan berjalan. Jika sisa budget $< 10\%$, script harus mengembalikan HTTP exit code `1` (Reject Deployment). Jika sisa budget $\ge 10\%$, kembalikan HTTP exit code `0` (Allow Deployment).

---

## 14. Challenge: Zero-Downtime Multi-Cluster Failover under Budget Depletion

### Skenario Nyata:
Anda bertindak sebagai Principal SRE di platform e-commerce Tier-0. Sistem Anda tersebar di dua region Kubernetes active-active: `region-us-east` dan `region-us-west`.

Target SLO Availability transaksi: **99.99% (Rolling 30 hari)**.
Alokasi toleransi downtime per bulan: **4.32 menit**.

Pada hari flash sale, region `region-us-east` mengalami degradasi performa mikro akibat kegagalan storage IOPS cloud provider:
* Error rate di `us-east` melompat ke $2.5\%$.
* Error rate global melompat ke $1.25\%$.
* Burn Rate melonjak drastis ke angka **125x** dari ambang batas normal.

### Tantangan:
Rancang arsitektur governance dan script otomatisasi (*orchestrated failover*) yang:
1. Mengidentifikasi lonjakan burn rate melalui alert webhook dalam waktu $< 60\text{ detik}$.
2. Memverifikasi apakah region penerima (`region-us-west`) memiliki kapasitas *headroom* pod autoscaling (HPA) yang cukup sebelum dialihkan.
3. Menggeser bobot DNS (*Weighted Routing*) atau BGP Anycast secara bertahap (canary traffic shift: 10% -> 50% -> 100%) dalam kurun waktu 3 menit tanpa membuat region tujuan mengalami *cascading collapse*.
4. Menjalankan *circuit breaker* otomatis yang membekukan (*freeze*) semua rilis deployment di seluruh cluster global hingga Error Budget kembali stabil di atas ambang batas $50\%$.

*Kirimkan arsitektur dalam bentuk dokumen teknis komprehensif, flowchart logika failover, konfigurasi rule, dan mock code webhook orchestrator.*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda & Singkat)
1. **Apa perbedaan mendasar antara SLI dan SLO?**
2. **Jika sebuah layanan memiliki target SLO 99% dalam jangka waktu 30 hari, berapa durasi maksimal downtime yang diizinkan?**
   * A. 43.2 menit
   * B. 7.2 jam
   * C. 3.6 jam
   * D. 14.4 jam
3. **Mengapa metrik rata-rata (mean/average) dilarang digunakan sebagai dasar penentuan SLI latency?**
4. **Apa arti nilai Burn Rate sebesar 1.0 pada jendela evaluasi 30 hari?**
5. **Mengapa alert multi-burn-rate membutuhkan jendela pendek (short window) di samping jendela panjang (long window)?**

### 15.2 Pertanyaan Intermediate (Pilihan Ganda & Analisis)
6. **Sebuah service memiliki SLO ketersediaan 99.9%. Jika terjadi insiden dengan laju kegagalan 100% (total outage), berapakah Burn Rate aktual sistem tersebut?**
   * A. 10
   * B. 100
   * C. 1000
   * D. 14.4
7. **Mengapa penghitungan SLI latensi menggunakan rasio event bucket histogram (`le`) lebih disukai di Prometheus dibandingkan fungsi `histogram_quantile()`?**
8. **Kapan kondisi yang tepat untuk memberlakukan 'Deployment Freeze' pada tim rekayasa perangkat lunak berdasarkan prinsip Error Budget?**
9. **Manakah konfigurasi jendela pendek yang paling proporsional untuk jendela panjang 6 jam pada matriks Multi-Burn-Rate standard Google SRE?**
   * A. 1 jam
   * B. 30 menit
   * C. 5 menit
   * D. 2 jam
10. **Bagaimana cara mencegah bot scraping atau health-check pod mengaburkan data SLI availability?**

### 15.3 Skenario Kasus Produksi
11. **Skenario A:** Pipeline Prometheus Anda mengalami lonjakan penggunaan RAM secara ekstrem (OOMKilled) setelah Anda menerapkan recording rules untuk menghitung persentil 99 latensi per endpoint API individual. Apa penyebab arsitekturalnya dan bagaimana solusinya?
12. **Skenario B:** Tim security merilis rule WAF baru yang secara keliru memblokir ribuan pengguna sah dan mengembalikan status `HTTP 403 Forbidden`. SLI availability tim backend yang hanya menghitung `HTTP 5xx` tetap menunjukkan 100% reliabel, namun customer komplain tidak bisa belanja. Bagaimana Anda mendesain ulang SLI definition tersebut?
13. **Skenario C:** On-call engineer menerima pager di jam 02.00 pagi karena Burn Rate 14.4x menyala. Saat dicek di dashboard, error rate sudah 0% dan sistem normal. Investigasi menunjukkan error 100% sempat terjadi selama 45 detik saja. Bagian konfigurasi multi-burn rate mana yang cacat?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Basic
1. **SLI (Service Level Indicator)** adalah metrik aktual terukur secara real-time yang menunjukkan kinerja layanan (misal: rasio request sukses). **SLO (Service Level Objective)** adalah target keandalan yang disepakati secara internal oleh tim engineering dan produk (misal: target SLI harus $\ge 99.9\%$).
2. **B. 7.2 jam.** (Perhitungan: $30\text{ hari} \times 24\text{ jam/hari} \times (1 - 0.99) = 720\text{ jam} \times 0.01 = 7.2\text{ jam}$).
3. Karena nilai rata-rata menyamarkan lonjakan laten ekstrem (*outliers*). Nilai rata-rata bisa tampak baik padahal $5\%$ atau $1\%$ pengguna mengalami degradasi fatal (*the tyranny of the averages*).
4. Menghabiskan tepat 100% Error Budget dalam periode window yang ditentukan (laju konsumsi normal dan ideal tanpa melanggar batas).
5. Untuk memastikan bahwa insiden **masih aktif berlangsung** saat alert dievaluasi, sehingga mencegah alert palsu (*spurious alerts*) dari spike singkat yang sudah pulih sendiri.

#### Kunci Intermediate
6. **C. 1000.** (Perhitungan: $E = 1 - 0.999 = 0.001$. Outage 100% berarti error rate = $1.0$. Nilai Burn Rate $B = \frac{\text{Laju Error Aktual}}{E} = \frac{1.0}{0.001} = 1000$).
7. Karena rasio event bucket histogram dapat diagregasikan secara linear di berbagai dimensi pod/node secara presisi menggunakan `sum()`, dan memakan beban CPU/memori TSDB yang jauh lebih kecil dibandingkan kalkulasi non-linear pada fungsi `histogram_quantile()`.
8. Saat alokasi Error Budget untuk periode kepatuhan telah habis ($0\%$) atau terdegradasi di bawah ambang batas kesepakatan tata kelola, yang mewajibkan tim menghentikan peluncuran fitur baru dan memprioritaskan perbaikan keandalan.
9. **B. 30 menit.** (Rasio standard Google SRE adalah $\frac{1}{12}$ dari long window: $\frac{6\text{ jam} \times 60\text{ menit}}{12} = 30\text{ menit}$).
10. Dengan melakukan segregasi label pada layer ingress/gateway (misal menambahkan filter label `traffic_type!="synthetic"` atau mengecualikan rute path `/healthz` dan `/metrics` pada query PromQL SLI).

#### Pembahasan Skenario Kasus Produksi
11. **Penyebab:** Masalah *High Cardinality Explosion*. Menghitung histogram quantile pada kombinasi dimensi unik yang tak terbatas (misal path URL dengan parameter dynamic ID) melipatgandakan jumlah *time-series* di TSDB.  
    **Solusi:** Normalisasi path HTTP (hilangkan path parameter unik menjadi pattern misal `/users/:id`), buang dimensi label yang tidak esensial dari recording rule, atau alihkan penghitungan ke SLI berbasis ambang bucket spesifik.
12. **Solusi Desain Ulang:** SLI availability harus diperbarui untuk mengklasifikasikan respons HTTP. Tambahkan pengecualian: HTTP 401 dan 403 dimasukkan ke dalam metrik *Bad Events* jika lonjakannya melebihi threshold tertentu, atau bangun SLI terpisah: *Authentication Success Ratio* yang mengukur persentase valid requests yang berhasil lolos WAF/Auth.
13. **Penyebab Cacat:** Alerting rule tidak mengimplementasikan validasi **Short Window** secara simultan, atau durasi parameter `for:` pada rule terlalu singkat atau tidak disetel. Akibatnya, spike transient error 45 detik langsung memicu alert dari window panjang 1 jam. Rule wajib direvisi menggunakan klausa `AND` yang mengevaluasi jendela pendek (5 menit) dan menambahkan durasi penahanan `for: 2m`.

---

## 16. Summary

* **Service-Level Engineering Modern** berfokus pada pengalaman pengguna nyata dan memandang keandalan bukan sebagai ketiadaan bug secara absolut, melainkan sebagai optimalisasi tingkat kegagalan yang dapat diterima (*Error Budget*).
* **Multi-Window Multi-Burn-Rate Alerting** adalah standar baku industri untuk sistem enterprise. Algoritma ini menyelesaikan paradoks antara kecepatan deteksi insiden (*low MTTD*) dan eliminasi *alert fatigue* (*zero false alarms*).
* Penggunaan **Recording Rules** yang efisien dan adopsi alat bantu deklaratif seperti **Sloth** atau **OpenSLO** memungkinkan otomasi pembuatan rules tanpa beban tinggi pada mesin TSDB.
* **Error Budget Governance** bukanlah sekadar laporan statistik, melainkan fondasi bagi otomasi CI/CD, canary analysis, dan kebijakan operasional (*governance-as-code*) yang menjembatani kecepatan inovasi produk dengan stabilitas platform.