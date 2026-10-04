# Module 01: Monitoring & Metrik dengan Prometheus, Alertmanager, & Grafana

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami pilar observabilitas pertama (**Metrics**) dan arsitektur *pull-based time-series monitoring*.
- Menguasai 4 tipe data metrik fundamental Prometheus: **Counter**, **Gauge**, **Histogram**, dan **Summary**.
- Menulis query analisis performa sistem dan aplikasi menggunakan **PromQL** (*Prometheus Query Language*).
- Mengonfigurasi **Prometheus Scraper**, **Node Exporter**, dan aturan evaluasi alert (*Alerting Rules*).
- Merancang alur routing notifikasi insiden menggunakan **Alertmanager** (Grouping, Inhibiting, Silencing).
- Membangun visualisasi dashboard operasional interaktif level enterprise di **Grafana**.

---

## 2. Prerequisite
- Memahami konsep dasar networking: port HTTP, scraping endpoint (`/metrics`), dan DNS (BAB 02).
- Memahami Docker container dan Kubernetes Service discovery (BAB 03 & BAB 04).
- Pengetahuan dasar tentang kalkulasi persentil ($p50, p90, p99$) dan statistik performa sistem.

---

## 3. Concept
Observabilitas sistem modern bertumpu pada kemampuan mengamati status internal sistem berdasarkan output eksternal yang dikeluarkannya. **Prometheus** adalah platform open-source standar industri (CNCF Graduated) untuk *time-series metric collection* dan *alerting*.

Berbeda dengan sistem monitoring tradisional yang menunggu server mengirim data (*push*), Prometheus menggunakan model **pull-based scraping**: Prometheus server secara periodik (misal setiap 15 detik) melakukan HTTP GET ke endpoint `/metrics` dari setiap target (server fisik, database, container, microservices) dan menyimpan data numerik berlabel (*time-series*) ke dalam Time-Series Database (TSDB) lokal.

```
                  ┌───────────────────────────────────────────────────────────┐
                  │                 PROMETHEUS ECOSYSTEM                      │
                  └───────────────────────────────────────────────────────────┘

  [ Microservice App ] ──(/metrics)──┐
  [ Node Exporter    ] ──(/metrics)──┼───(Scrape Poll 15s)───> [ Prometheus Server ]
  [ MySQL Exporter   ] ──(/metrics)──┘                                │     │
                                                                      │     │
                 ┌────────────────────────────────────────────────────┘     │ PromQL Query
                 ▼ (Alert Rules firing)                                     ▼
        [ Alertmanager ]                                              [ Grafana ]
          │        │                                                       │
          ▼        ▼                                                       ▼
      [Slack]  [PagerDuty]                                       [ Operational Dashboards ]
```

---

## 4. Why?
1. **Pendeteksian Degradasi Sebelum Down**: Monitoring black-box (hanya ping "apakah website hidup?") baru berteriak ketika website sudah down. Time-series metrics memberikan sinyal degradasi dini (misal: memory usage perlahan naik mendekati 95%, disk I/O latency naik dari 2ms ke 200ms).
2. **Kekuatan Label Dinamis (Multi-Dimensional Data Model)**: Prometheus tidak sekadar mencatat satu angka. Setiap metrik dapat memiliki label berdimensi tinggi:
   `http_requests_total{method="POST", handler="/checkout", status="500", cluster="prod-sg"}`. Ini memungkinkan slicing & dicing data secara instan di PromQL.
3. **Standar Industri Cloud-Native**: Seluruh ekosistem Kubernetes, Cloud providers, database, dan service mesh memiliki exporter resmi yang kompatibel dengan format Prometheus.

---

## 5. What?
4 Tipe Metrik Inti Prometheus:
1. **Counter**: Nilai numerik kumulatif yang **hanya bisa naik atau direset ke 0** saat restart. Digunakan untuk menghitung jumlah total kejadian (misal: `http_requests_total`, `packet_dropped_total`).
2. **Gauge**: Nilai numerik tunggal yang **bisa naik dan turun**. Digunakan untuk mengukur status sesaat (*snapshot*) (misal: `memory_usage_bytes`, `cpu_temperature_celsius`, `active_user_sessions`).
3. **Histogram**: Menghitung sampel data dan mengelompokkannya ke dalam rentang keranjang (*configurable buckets*). Sangat krusial untuk menghitung **Latency/Duration** dan persentil ($p90, p99$).
4. **Summary**: Serupa dengan histogram, namun menghitung $\phi$-quantiles langsung di sisi client library (memiliki overhead CPU di client dan tidak bisa diagregasi antar-instance).

---

## 6. How?
Alur kerja Prometheus Scrape & Alerting:
1. **Instrumentasi**: Aplikasi menambahkan Prometheus client library (Node.js `prom-client`, Go `client_golang`, Java Micrometer) dan mengekspos endpoint HTTP `/metrics`.
2. **Target Discovery**: Prometheus menemukan alamat IP target secara otomatis melalui Kubernetes Service Discovery, Consul, atau file konfigurasi statis (`prometheus.yml`).
3. **Scrape & TSDB**: Prometheus me-request `/metrics`, mem-parsing data teks, dan menyimpannya ke TSDB on-disk dalam blok data 2 jam.
4. **Rule Evaluation**: Setiap `evaluation_interval` (misal 15 detik), Prometheus mengevaluasi ekspresi PromQL. Jika kondisi alert bernilai `true` selama durasi `for` (misal 5 menit), Prometheus menembakkan alert payload ke **Alertmanager**.
5. **Alertmanager Processing**: Alertmanager menduplikasi, mengelompokkan (*grouping*), meredam (*inhibiting*), dan mengirim notifikasi ke webhook Slack, PagerDuty, atau email.
6. **Grafana Visualization**: Grafana mengeksekusi query PromQL dan me-render visual grafik, heatmap, gauge, dan tabel metrik.

---

## 7. Analogy
Bayangkan **Prometheus** seperti **Dokter Pemeriksa Kesehatan Rumah Sakit**:
- Setiap pasien (microservice) memiliki rekam medis di meja perawat (`/metrics`).
- Dokter berkeliling setiap 15 detik (*scraping*) memeriksa detak jantung, tensi, dan suhu tubuh (*metrics*).
- Jika tensi pasien di atas 180 selama 5 menit berturut-turut (*alert rule evaluation*), dokter menekan tombol bel darurat ke kantor suster (**Alertmanager**).
- Kantor suster tidak langsung berteriak 100 kali jika ada 100 alarm serupa; mereka mengelompokkannya menjadi 1 panggilan terpadu (*grouping & deduplication*) ke speaker ruangan dokter spesialis on-call (**PagerDuty/Slack**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                        PROMETHEUS & METRICS PIPELINE                              |
+-----------------------------------------------------------------------------------+

 [ Microservice A:8080 ]            [ Prometheus Server ]              [ Grafana ]
          │                                  │                              │
          │  HTTP GET /metrics               │                              │
          │ <────────────────────────────────┤                              │
          │                                  │                              │
          │  http_requests_total 48291       │                              │
          │  process_resident_memory 240MB   │                              │
          ├─────────────────────────────────>│                              │
          │                                  │ (Stores into TSDB)           │
          │                                  │                              │
          │                                  │   PromQL Query               │
          │                                  │ <────────────────────────────┤
          │                                  │   rate(http_requests[5m])    │
          │                                  ├─────────────────────────────>│
          │                                  │                              │
          │                                  │                         [ Dashboards ]
          │                                  │
          │                                  ▼ Evaluation Loop
          │                          [ Alert Rules Fired ]
          │                                  │
          │                                  │ POST /api/v2/alerts
          │                                  ▼
          │                          [ Alertmanager ]
          │                                  │
          │                     ┌────────────┴────────────┐
          │                     ▼                         ▼
          │               [ PagerDuty ]               [ Slack ]
          │               (High Severity)           (Warning Info)
```

---

## 9. Simple Example: Format Data Metrik Prometheus
Isi dari respons teks murni saat mengakses `http://localhost:9090/metrics`:

```text
# HELP http_requests_total Total number of HTTP requests made.
# TYPE http_requests_total counter
http_requests_total{method="GET",handler="/api/v1/orders",status="200"} 12450
http_requests_total{method="POST",handler="/api/v1/orders",status="500"} 14

# HELP system_memory_usage_bytes Current resident memory size in bytes.
# TYPE system_memory_usage_bytes gauge
system_memory_usage_bytes 268435456

# HELP http_request_duration_seconds HTTP request latencies in seconds.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.05"} 8400
http_request_duration_seconds_bucket{le="0.1"} 11200
http_request_duration_seconds_bucket{le="0.5"} 12390
http_request_duration_seconds_bucket{le="+Inf"} 12464
http_request_duration_seconds_sum 1420.5
http_request_duration_seconds_count 12464
```

---

## 10. Practical Example: Konfigurasi Scraping & Alerting
File `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - 'alerts/application_rules.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'payment-service'
    scrape_interval: 5s
    static_configs:
      - targets: ['payment-api.prod.svc:8080']
        labels:
          environment: 'production'
          tier: 'backend'
```

File `alerts/application_rules.yml`:

```yaml
groups:
  - name: payment_api_alerts
    rules:
      - alert: HighHttp5xxErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total[5m])) * 100 > 2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Tingginya HTTP 5xx Error Rate pada Payment API"
          description: "Payment API mencatat error rate sebesar {{ $value }}% dalam 5 menit terakhir."

      - alert: MemoryUsageCritical
        expr: process_resident_memory_bytes / 1024 / 1024 > 850
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Penggunaan Memory mendekati limit OOMKilled"
```

---

## 11. Real World Example: Perhitungan Latensi 99th Percentile ($p99$)
Pada aplikasi pembayaran perbankan, rata-rata (*average*) latensi sering menipu. Jika 99 orang mendapat respon 10ms dan 1 orang menunggu 30 detik, rata-rata masih terlihat "bagus" (~310ms), padahal ratusan nasabah penting mengalami *timeout*.

Dengan Prometheus Histogram, tim DevOps menghitung latensi $p99$ menggunakan fungsi PromQL `histogram_quantile`:

$$\text{Quantile}_{99} = \text{histogram\_quantile}(0.99, \text{sum}(\text{rate}(\text{http\_request\_duration\_seconds\_bucket}[5\text{m}])) \text{ by } (\text{le}))$$

Query ini membaca keranjang bucket akumulatif dan melakukan interpolasi linier untuk mengetahui batas waktu maksimum di mana 99% request selesai diproses. Jika metrik $p99 > 800\text{ms}$ selama 3 menit, sistem langsung mengirim alert ke insinyur on-call untuk memeriksa database slow query.

---

## 12. Trade-offs

| Aspek | Pull Model (Prometheus) | Push Model (StatsD / Datadog Agent) |
|---|---|---|
| **Health Detection** | Otomatis tahu jika target mati (Scrape fails) | Sulit mendeteksi target mati vs network hening |
| **Network Traffic** | Terkontrol (Scrape interval ditentukan server) | Rentan membanjiri server (*thundering herd*) |
| **Short-Lived Batch Jobs** | Memerlukan Pushgateway perantara | Alami (Job langsung mengirim metrik saat selesai) |
| **Penyimpanan Jangka Panjang** | TSDB lokal tidak didesain untuk multi-tahun | Perlu remote storage (Thanos, Cortex, Mimir) |
| **Overhead Client** | Sangat rendah (Hanya memori buffer lokal) | Sedang (Perlu thread pengirim background UDP/TCP) |

---

## 13. When To Use
- Monitoring infrastruktur, container Kubernetes, dan microservices jangka panjang.
- Mengukur beban throughput, utilisasi resource (CPU, Memory, Disk, Network I/O).
- Alerting real-time berbasis ambang batas operasional (*threshold*) dan tren degradasi (*rate of change*).

---

## 14. When NOT To Use
- Sebagai audit log peristiwa individual (contoh: "User A mengubah password pada jam 14:02:11"). Gunakan logging terpusat (Loki / ELK).
- Tracing end-to-end pemanggilan HTTP per-transaksi secara mendalam. Gunakan Distributed Tracing (OpenTelemetry / Jaeger).
- Metrik dengan kardinalitas tanpa batas (misal menyematkan User ID atau Email sebagai label metrik), karena akan meledakkan memori TSDB.

---

## 15. Common Mistakes
1. **High Cardinality Bomb**: Menjadikan parameter dinamis seperti `user_id`, `email`, atau `ip_address` sebagai label Prometheus. Setiap kombinasi label menciptakan 1 deret waktu (*time-series*) baru di memori. Jika ada 1 juta pengguna, Prometheus TSDB akan mengalami crash kehabisan RAM (OOM).
2. **Menggunakan `rate()` pada Gauge**: Fungsi `rate()` hanya valid digunakan pada tipe data `Counter`. Menggunakan `rate()` pada `Gauge` (seperti suhu atau persentase RAM) akan menghasilkan perhitungan interpolasi yang salah fatal saat nilai metrik turun.
3. **Alerting Tanpa Durasi `for`**: Membuat alert rule tanpa klausul `for: 2m`. Hal ini akan memicu alarm bising (*alert fatigue*) setiap kali ada spike sesaat selama 1 detik yang tidak berbahaya.

---

## 16. Best Practices
### Must Have
- Gunakan akhiran nama metrik standar: `_total` untuk Counter, `_bytes` atau `_seconds` untuk satuan fisik.
- Pasang Node Exporter pada setiap node Linux untuk metrik CPU, Memory, Disk Space, dan Network Socket.
- Konfigurasikan `inhibit_rules` di Alertmanager: jika sebuah Node down (`NodeDown`), jangan kirim puluhan alert individual bahwa aplikasi di node tersebut mati.

### Recommended
- Gabungkan 4 Golden Signals (Google SRE): **Latency**, **Traffic**, **Errors**, dan **Saturation** pada setiap dashboard Grafana.
- Tentukan Runbook URL di anotasi alert sehingga insinyur on-call dapat langsung mengklik panduan penanganan saat terbangun di malam hari.

### Advanced
- Integrasikan Thanos atau Grafana Mimir untuk horizontal scalability dan cold storage data metrik di AWS S3 selama bertahun-tahun.

---

## 17. Troubleshooting
- **Masalah**: Target berstatus `DOWN` di menu Prometheus `/targets`.
  - *Diagnostik*: Jalankan `curl -Iv http://<target-ip>:<port>/metrics` dari dalam container Prometheus.
  - *Solusi*: Periksa firewall, NetworkPolicy Kubernetes, atau pastikan aplikasi binding ke `0.0.0.0` bukan `127.0.0.1`.
- **Masalah**: Grafana query PromQL sangat lambat hingga timeout.
  - *Solusi*: Hindari subquery yang mengevaluasi jutaan deret waktu sekaligus tanpa filter label; gunakan `recording rules` di Prometheus untuk pra-kalkulasi query berat.

---

## 18. Exercise
1. Tulis query PromQL untuk menghitung persentase penggunaan CPU per-node berdasarkan metrik `node_cpu_seconds_total`.
2. Tulis alert rule untuk mendeteksi kapasitas harddisk yang diprediksi akan penuh dalam waktu kurang dari 4 jam menggunakan fungsi `predict_linear()`.

---

## 19. Challenge
Rancang arsitektur monitoring multi-tier untuk Kubernetes:
- Mengonfigurasi Prometheus Operator (Kube-Prometheus-Stack).
- Menerapkan ServiceMonitor kustom untuk microservice e-commerce.
- Menulis Alertmanager routing tree: Alert severity `critical` dikirim via PagerDuty webhook, severity `warning` dikirim ke channel `#alerts-devops` Slack.
- Membangun dashboard Grafana dengan panel Latency $p95$, Error Rate %, dan Requests Per Second (RPS).

---

## 20. Summary
- **Prometheus** menggunakan model pull-based scraping untuk mengumpulkan metrik time-series numerik.
- 4 tipe metrik esensial: **Counter** (akumulatif naik), **Gauge** (naik-turun), **Histogram** (distribusi bucket untuk latensi), dan **Summary**.
- **PromQL** menyediakan ekspresi komputasi vektor yang sangat kuat untuk mengukur laju perubahan (`rate()`) dan persentil.
- **Alertmanager** bertanggung jawab atas routing, deduplikasi, dan peredaman alarm sebelum dikirim ke channel notifikasi.
- **Grafana** melengkapi ekosistem sebagai visualisasi dashboard visual yang intuitif.
