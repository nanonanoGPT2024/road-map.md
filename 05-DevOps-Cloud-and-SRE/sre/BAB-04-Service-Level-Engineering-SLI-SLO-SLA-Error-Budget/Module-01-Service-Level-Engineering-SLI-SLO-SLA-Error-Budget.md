# Modul 01: Service Level Engineering (SLI, SLO, SLA, & Error Budget)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Membedakan Service Level Indicator (SLI), Service Level Objective (SLO), dan Service Level Agreement (SLA) secara matematis dan operasional.
- Mengidentifikasi Critical User Journeys (CUJ) dan merumuskan spesifikasi SLI berbasis event yang valid dan reliabel.
- Menghitung target SLO, ketersediaan Error Budget, serta laju pembakaran (*burn rate*) untuk sistem skala besar.
- Merancang dan mengimplementasikan arsitektur alerting berbasis *Multi-Window Multi-Burn-Rate* sesuai standar Google Site Reliability Engineering (SRE).
- Menyusun *Error Budget Policy* yang memiliki kekuatan tata kelola teknis (governance) dalam siklus hidup rekayasa perangkat lunak (*software development life cycle*).

---

## 2. Prerequisite
Untuk memahami materi ini secara komprehensif, Anda memerlukan pemahaman dasar mengenai:
- Arsitektur sistem terdistribusi (HTTP/gRPC request-response model, REST API lifecycle).
- Dasar-dasar metrik observabilitas: *Counter*, *Gauge*, dan *Histogram*.
- Sintaks dasar Prometheus Query Language (PromQL) atau query engine sejenis.
- Konsep dasar probabilitas dan statistik (persentil, rasio, agregasi temporal).

---

## 3. Concept
Service Level Engineering adalah disiplin rekayasa sistem yang memformalkan keandalan (*reliability*) bukan sebagai ketiadaan masalah (100% uptime), melainkan sebagai target empiris yang terikat pada ekspektasi pengguna. Keandalan 100% adalah target yang salah: biayanya sangat mahal secara eksponensial dan menghambat laju inovasi produk tanpa memberikan peningkatan kepuasan pengguna yang terukur.

Empat fondasi Service Level Engineering:
1. **SLI (Service Level Indicator):** Rasio terukur dari kejadian baik (*good events*) terhadap total kejadian yang valid (*valid events*).
2. **SLO (Service Level Objective):** Target numerik spesifik untuk SLI yang disepakati secara internal dalam periode waktu tertentu (misal: rolling window 30 hari).
3. **Error Budget:** Kuota ketidakandalan yang diizinkan sebelum SLO terlanggar ($100\% - \text{SLO}$). Error budget adalah penyangga inovasi dan risiko.
4. **SLA (Service Level Agreement):** Perjanjian hukum atau komersial antara penyedia layanan dan pengguna yang menyertakan konsekuensi finansial atau penalti hukum jika SLO gagal dipenuhi.

---

## 4. Why
Pendekatan tradisional dalam monitoring keandalan memiliki cacat fundamental:
- **Alert Fatigue Akibat Threshold Statis:** Peringatan berbasis ambang batas sederhana (misal: "CPU > 85%" atau "Error rate > 1%") memicu ribuan pager alarm palsu (*false positive*) atau terlambat mendeteksi masalah sistemis (*false negative*).
- **Konflik Kepentingan Product vs. SRE/Ops:** Tim produk ingin meluncurkan fitur secepat mungkin (*velocity*), sedangkan tim operasional ingin sistem tetap stabil (*stability*). Tanpa metrik netral, perdebatan bersifat subjektif.
- **Over-engineering:** Mengejar reliabilitas absolut membuang anggaran infrastruktur secara sia-sia untuk memitigasi kegagalan pada lapisan jaringan lokal pengguna atau edge ISP yang tidak dapat dikontrol oleh provider.

Error Budget bertindak sebagai mata uang objektif untuk menyeimbangkan *velocity* dan *stability*.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 SLI Formulas & Math
Formulasi SLI standar Google SRE didefinisikan sebagai rasio:

$$\text{SLI} = \frac{\sum \text{Good Events}}{\sum \text{Total Valid Events}} \times 100\%$$

Kategori SLI utama:
- **Availability (Ketersediaan Request-Driven):**
  $$\text{SLI}_{\text{avail}} = \frac{\text{Jumlah HTTP request dengan status code } < 500}{\text{Total HTTP request valid}} \times 100\%$$
- **Latency (Kecepatan Pemrosesan):**
  $$\text{SLI}_{\text{latency}} = \frac{\text{Jumlah HTTP request dengan durasi } \le 250\text{ms}}{\text{Total HTTP request valid}} \times 100\%$$
- **Correctness / Freshness (Data Pipeline):**
  $$\text{SLI}_{\text{freshness}} = \frac{\text{Jumlah pipeline execution dengan data delay } \le 10\text{ menit}}{\text{Total pipeline execution}} \times 100\%$$

### 5.2 Error Budget Calculations
Jika SLO availability ditetapkan sebesar $99.9\%$ dalam rolling window 30 hari:
$$\text{Error Budget} = 100\% - 99.9\% = 0.1\%$$

Jika sistem melayani $100.000.000$ request valid dalam 30 hari:
$$\text{Alokasi Request Gagal} = 100.000.000 \times 0.001 = 100.000\text{ request}$$

Jika sistem menggunakan basis waktu (*time-based SLO*, misal untuk ketersediaan infrastruktur/VM):
- 30 hari = $30 \times 24 \times 60 = 43.200\text{ menit}$
- Error Budget ($0.1\%$) = $43.200 \times 0.001 = 43.2\text{ menit downtime}$

### 5.3 Burn Rate Math
*Burn Rate* ($B$) mendefinisikan seberapa cepat sistem menghabiskan Error Budget relatif terhadap periode SLO.
- **$B = 1$:** Error Budget akan habis tepat saat window SLO berakhir (misal: habis $100\%$ dalam 30 hari).
- **$B = 2$:** Error Budget habis 2x lebih cepat (habis dalam 15 hari).
- **$B = 14.4$:** Menghabiskan $2\%$ error budget dalam 1 jam, atau $100\%$ budget dalam 2 hari ($30\text{ hari} / 14.4 \approx 2.08\text{ hari}$).

Perhitungan matematis Burn Rate:
$$B = \frac{\text{Observed Error Rate}}{\text{Allowed Error Rate}} = \frac{1 - \text{SLI}}{1 - \text{SLO}}$$

Contoh: Jika target SLO adalah $99.9\%$ (Allowed Error Rate = $0.001$) dan dalam 1 jam terakhir observed error rate adalah $1.44\%$ ($0.0144$):
$$B = \frac{0.0144}{0.001} = 14.4$$

### 5.4 Multi-Window Multi-Burn-Rate Alerting Strategy
Metode alerting berbasis burn rate tradisional dapat menimbulkan dua masalah:
1. Window pendek (misal: 1 jam) cepat mendeteksi error spike besar, tetapi menghasilkan *alert reset* terlalu cepat setelah spike berhenti, meskipun budget terkuras drastis.
2. Window panjang (misal: 24 jam) tahan terhadap anomali sesaat, namun responnya sangat lambat saat sistem tumbang total.

Solusi Google SRE: **Multi-Window Multi-Burn-Rate Alerting**. Pager hanya dipicu jika laju pembakaran pada **Long Window** dan **Short Window** sama-sama melampaui ambang batas ($B$).

| Severity | Long Window | Short Window | Burn Rate ($B$) | % Budget Terbakar | Waktu Hingga Budget 100% Habis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Page** | 1 Jam | 5 Menit | 14.4 | 2% | 2 Hari |
| **Page** | 6 Jam | 30 Menit | 6.0 | 5% | 5 Hari |
| **Ticket** | 24 Jam | 2 Jam | 3.0 | 10% | 10 Hari |
| **Ticket** | 3 Hari | 6 Jam | 1.0 | 10% | 30 Hari |

Formula Logika Alerting:
$$\text{Trigger Alert} = (\text{BurnRate}_{\text{LongWindow}} \ge B) \land (\text{BurnRate}_{\text{ShortWindow}} \ge B)$$

---

## 6. How
Implementasi Service Level Engineering dilakukan melalui tahapan struktural:
1. **Identifikasi Critical User Journeys (CUJ):** Jangan ukur ribuan endpoint. Identifikasi journey kritis (misal: Checkout, Login, Payment Transfer).
2. **Pilih Tipe SLI:** Tentukan apakah journey tersebut request-driven, batch processing, atau storage-oriented.
3. **Standardisasi Instrumentasi:** Pasang counter/histogram di layer terdekat dengan pengguna (misal: API Gateway / Ingress Controller).
4. **Hitung Metrik di Prometheus:** Tulis PromQL agregasi untuk good events dan valid events.
5. **Bangun Alerting Rule:** Terapkan multi-window multi-burn-rate pada Prometheus Operator / Alertmanager.
6. **Eksekusi Error Budget Policy:** Tetapkan sanksi otomatis saat budget habis (penundaan deployment, alokasi backlog reliability).

---

## 7. Analogy
Bayangkan Error Budget seperti **Saldo Kuota Bensin Bulanan** untuk armada ekspedisi:
- **SLO (99%):** Komitmen bahwa armada Anda harus menyelesaikan $99\%$ perjalanan tepat waktu.
- **Error Budget (1%):** Batas toleransi keterlambatan atau gangguan armada dalam sebulan.
- **Burn Rate 1:** Mobil mengonsumsi jatah toleransi dengan kecepatan normal yang akan habis pas di akhir bulan tanggal 30.
- **Burn Rate 14.4:** Tangki bahan bakar bocor hebat; jatah sebulan akan ludes hanya dalam 2 hari jika mobil tidak segera menepi.
- **Multi-Window Alerting:** Jangan membunyikan alarm evakuasi darurat hanya karena mobil melindas lubang jalan selama 2 detik (short-lived spike), tapi bunyikan alarm jika jarum bensin turun drastis dalam 1 jam terakhir DAN 5 menit terakhir masih menunjukkan kebocoran aktif.

---

## 8. Diagram (ASCII)

```
+-------------------------------------------------------------------------------+
|                       CRITICAL USER JOURNEY (Checkout API)                    |
+-------------------------------------------------------------------------------+
                                        |
                   [Ingress Controller / API Gateway]
                                        |
        +-------------------------------+-------------------------------+
        |                                                               |
 [Good Requests: 2xx, 3xx, 4xx*]                          [Bad Requests: 5xx]
 (*4xx user error kecuali 429)                                          |
        |                                                               |
        +-------------------------------+-------------------------------+
                                        |
                         +-----------------------------+
                         | Prometheus Engine Calculate |
                         | SLI = (Good / Total)        |
                         +-----------------------------+
                                        |
             +--------------------------+--------------------------+
             |                                                     |
    [Long Window: 1h]                                     [Short Window: 5m]
    Burn Rate > 14.4 ?                                    Burn Rate > 14.4 ?
             |                                                     |
             +--------------------------+--------------------------+
                                        |
                               (Logical AND Gate)
                                        |
                          [Kedua Kondisi Terpenuhi?]
                                    /       \
                              YES  /         \  NO
                                  v           v
                    +--------------------+   +-----------------------+
                    | PagerDuty / OnCall |   | Supress Alert         |
                    | (Severity: PAGE)   |   | (Transient/Recovered) |
                    +--------------------+   +-----------------------+
```

---

## 9. Simple Example
Menghitung konsumsi Error Budget ketersediaan web sederhana.

- **Data Operasional:**
  - Rolling Window: 7 Hari ($7 \times 24 \times 60 = 10.080\text{ menit}$)
  - SLO: $99.5\%$
  - Error Budget: $100\% - 99.5\% = 0.5\%$
  - Total Error Budget dalam menit: $10.080 \times 0.005 = 50.4\text{ menit}$

Jika sistem mengalami kegagalan total (*downtime*) selama 15 menit pada hari ke-2:
- Sisa Error Budget dalam menit: $50.4 - 15 = 35.4\text{ menit}$
- Persentase budget terpakai: $(15 / 50.4) \times 100\% = 29.76\%$
- Status: Tim masih memiliki sisa $70.24\%$ error budget untuk 5 hari ke depan.

---

## 10. Practical Example (Prometheus Alerting Rules)

File konfigurasi `prometheus-slo-rules.yaml` yang mengimplementasikan Multi-Window Multi-Burn-Rate untuk service `payment-gateway`:

```yaml
groups:
  - name: payment_gateway_slo_alerts
    rules:
      # Availability SLI Calculation across multiple windows
      - record: job:payment_http_requests:rate5m
        expr: sum(rate(http_requests_total{job="payment-api"}[5m]))
      - record: job:payment_http_errors:rate5m
        expr: sum(rate(http_requests_total{job="payment-api", status=~"5.."}[5m]))

      - record: job:payment_http_requests:rate30m
        expr: sum(rate(http_requests_total{job="payment-api"}[30m]))
      - record: job:payment_http_errors:rate30m
        expr: sum(rate(http_requests_total{job="payment-api", status=~"5.."}[30m]))

      - record: job:payment_http_requests:rate1h
        expr: sum(rate(http_requests_total{job="payment-api"}[1h]))
      - record: job:payment_http_errors:rate1h
        expr: sum(rate(http_requests_total{job="payment-api", status=~"5.."}[1h]))

      - record: job:payment_http_requests:rate6h
        expr: sum(rate(http_requests_total{job="payment-api"}[6h]))
      - record: job:payment_http_errors:rate6h
        expr: sum(rate(http_requests_total{job="payment-api", status=~"5.."}[6h]))

      # Target SLO = 99.9% -> Error Budget Factor (1 - 0.999) = 0.001
      # Burn Rate = error_rate / 0.001

      # Alert 1: 1h Window (BR 14.4) AND 5m Window (BR 14.4) -> Severity: Page
      - alert: PaymentApiHighErrorBudgetBurn_1HourWindow
        expr: |
          (
            job:payment_http_errors:rate1h / job:payment_http_requests:rate1h
          ) / 0.001 > 14.4
          and
          (
            job:payment_http_errors:rate5m / job:payment_http_requests:rate5m
          ) / 0.001 > 14.4
        for: 2m
        labels:
          severity: page
          tier: mission-critical
        annotations:
          summary: "Kehabisan Error Budget Pembayaran Kritis (Burn Rate > 14.4)"
          description: "Service payment-api mengonsumsi >2% error budget dalam 1 jam terakhir dan error rate masih aktif di window 5m."

      # Alert 2: 6h Window (BR 6) AND 30m Window (BR 6) -> Severity: Page
      - alert: PaymentApiHighErrorBudgetBurn_6HourWindow
        expr: |
          (
            job:payment_http_errors:rate6h / job:payment_http_requests:rate6h
          ) / 0.001 > 6.0
          and
          (
            job:payment_http_errors:rate30m / job:payment_http_requests:rate30m
          ) / 0.001 > 6.0
        for: 5m
        labels:
          severity: page
          tier: mission-critical
        annotations:
          summary: "Kehabisan Error Budget Lambat namun Masif (Burn Rate > 6.0)"
          description: "Service payment-api mengonsumsi >5% error budget dalam 6 jam terakhir."
```

---

## 11. Real World Example
Sebuah marketplace e-commerce unicorn di Indonesia mengalami insiden degradasi microservice saat promo *Waktu Indonesia Belanja (WIB)*:
- Service keranjang belanja (*cart-service*) memiliki target SLO ketersediaan $99.95\%$ per 30 hari.
- Pada pukul 00:00, database replica crash, menyebabkan rate error $500$ naik menjadi $2.5\%$.
- Jika menggunakan ambang batas tradisional (*error rate > 5%*), alert tidak akan pernah menyala karena error rate stabil di $2.5\%$.
- Dengan **Burn Rate Math**:
  $$\text{Allowed Error} = 100\% - 99.95\% = 0.05\% = 0.0005$$
  $$\text{Burn Rate} = \frac{0.025}{0.0005} = 50$$
- Sistem membakar error budget dengan faktor **50x lipat** dari batas aman (seluruh budget 30 hari akan habis dalam waktu $\approx 14.4$ jam).
- Sistem multi-burn-rate memicu alert PagerDuty dalam waktu **3 menit** (memenuhi kondisi burn rate $14.4\text{x}$ pada window 5m & 1h), memungkinkan tim SRE melakukan failover ke region sekunder sebelum SLA pelanggan terlanggar.

---

## 12. Trade-offs

| Parameter | Window Pendek Saja (e.g. 5m) | Window Panjang Saja (e.g. 24h) | Multi-Window Multi-Burn-Rate |
| :--- | :--- | :--- | :--- |
| **Kecepatan Deteksi (Detection Speed)** | Sangat Tinggi (<2 min) | Sangat Lambat (Bisa jam-jaman) | Optimal & Adaptif |
| **Resistensi False Alarm (Reset Flapping)** | Sangat Buruk (Bising/Flapping) | Sangat Baik (Stabil) | Sangat Baik (Hanya aktif jika spike persisten) |
| **Kompleksitas Query PromQL** | Sangat Rendah | Rendah | Tinggi (Memerlukan recording rules terstruktur) |
| **Beban Evaluasi Monitoring Engine** | Rendah | Rendah | Sedang-Tinggi (Memerlukan pre-calculated metrics) |

---

## 13. When To Use
- Pada aplikasi dengan arsitektur microservices terdistribusi yang melayani traffic publik bervolume tinggi.
- Ketika tim engineering menghadapi fenomena *alert fatigue* akibat peringatan sistematis yang tidak bernilai operasional.
- Sebagai basis kontrak formal antara Product Management dan Engineering saat menyepakati prioritas pengerjaan refactoring versus fitur baru.
- Pada sistem dengan integrasi B2B API yang memiliki konsekuensi ganti rugi finansial langsung pada kontrak hukum (SLA).

---

## 14. When NOT To Use
- **Sistem Internal Bervolume Sangat Rendah:** Jika service hanya menerima $10$ request per hari, satu request gagal menghasilkan error rate $10\%$, memicu false positive ekstrem pada perhitungan burn rate. Gunakan *heartbeat synthetic monitoring* sebagai gantinya.
- **Sistem Batch Ad-Hoc / ETL Cron:** Pipeline yang berjalan seminggu sekali tidak cocok diukur dengan rolling window request availability. Gunakan SLI tipe Freshness/Completion.
- **Startup Tahap Sangat Awal (Pre-Product Market Fit):** Menerapkan regulasi Error Budget Policy yang kaku dapat mematikan kecepatan pivoting bisnis startup.

---

## 15. Common Mistakes
1. **Mengabaikan Kode HTTP 4xx:** Menghitung HTTP `401 Unauthorized` atau `404 Not Found` sebagai kegagalan sistem. Ini adalah kesalahan pengguna, bukan sistem. (Pengecualian: lonjakan tiba-tiba pada HTTP `429 Too Many Requests` yang dapat mengindikasikan miskonfigurasi rate limiting).
2. **SLO Vanity (99.999% Tanpa Dasar Kebutuhan Bisnis):** Menetapkan target *five-nines* hanya karena terdengar hebat. Reliabilitas $99.999\%$ berarti hanya boleh down 26 detik per bulan, yang membutuhkan multi-region active-active deployment berbiaya jutaan dollar.
3. **Mengukur dari Titik yang Salah:** Mengukur SLI di dalam server internal setelah request berhasil masuk ke application logic, mengabaikan request yang di-*drop* oleh Load Balancer, Ingress, atau WAF.
4. **SLO Tanpa Error Budget Policy:** Memiliki metrik SLO dan dashboard visual grafis, namun tidak ada tindakan yang diambil saat budget bernilai minus. SLO tanpa konsekuensi hanyalah metrik vanity.

---

## 16. Best Practices
- **Implementasikan Recording Rules:** Jangan mengevaluasi window burn rate panjang ($1\text{h}, 6\text{h}, 3\text{d}$) secara langsung di alert query. Gunakan Prometheus Recording Rules untuk menghemat resource CPU Prometheus.
- **Terapkan User Journey Mapping:** Petakan maksimal 3–5 SLI utama per layanan. Terlalu banyak SLI melemahkan fokus operasional tim.
- **Formalisasi Error Budget Policy:** Buat dokumen hukum operasional internal yang disepakati oleh VP of Engineering dan VP of Product. Contoh klausul: *"Jika Error Budget 30 hari tersisa 0%, seluruh rilis fitur baru dibekukan (*deployment freeze*) selama 7 hari berikutnya, dan seluruh kapasitas engineering dialihkan untuk reliability bug fixing."*
- **Konsistensi Window SLO:** Gunakan standard rolling window (misal: 28 hari atau 30 hari) alih-alih calendar month window, agar metrik tidak mengalami bias reset artifisial di tanggal 1 setiap bulannya.

---

## 17. Troubleshooting

### Masalah: False Positive Alert Burn Rate Akibat Traffic Turun Drastis (Low Traffic Anomaly)
- **Gejala:** Alert pembakaran budget menyala pada tengah malam saat traffic sangat rendah, padahal hanya ada 2 request gagal.
- **Akar Masalah:** Formula pembagian burn rate membagi error count dengan total traffic yang sangat kecil.
- **Mitigasi:** Tambahkan klausul *minimum traffic volume threshold* pada PromQL alert rule:
  ```promql
  (job:payment_http_errors:rate1h / job:payment_http_requests:rate1h) / 0.001 > 14.4
  and
  job:payment_http_requests:rate1h > 10 # Mengharuskan minimal 10 req/s
  ```

### Masalah: Alert PagerDuty Menyala lalu Mati Cepat (Alert Flapping)
- **Gejala:** Pager berbunyi pada window 1 jam, lalu berhenti 3 menit kemudian saat short-window kembali normal, membingungkan on-call engineer.
- **Akar Masalah:** Tidak menggunakan Short Window dalam formulasi alert.
- **Mitigasi:** Pastikan alert rule menggabungkan kondisi Long Window AND Short Window secara bersamaan menggunakan operator `and`.

---

## 18. Exercise
Sebuah layanan autentikasi SSO memiliki target SLO ketersediaan $99.9\%$ dengan evaluasi rolling window 30 hari. Dalam 30 hari tersebut, diperkirakan total ada $50.000.000$ request yang masuk.
1. Berapa batas maksimum request gagal yang diizinkan sebelum SLO terlanggar?
2. Jika terjadi insiden sistemik selama 2 jam dengan total request $400.000$ dan jumlah request gagal sebanyak $8.000$, berapa Burn Rate yang terjadi selama insiden 2 jam tersebut?
3. Berapa persentase Error Budget yang hangus akibat insiden 2 jam tersebut?

---

## 19. Challenge
Rancang arsitektur alerting berbasis Multi-Window Multi-Burn-Rate lengkap untuk microservice transfer perbankan yang memiliki SLO Latency: *"99% request harus diselesaikan dalam waktu kurang dari 500ms, diukur dalam rolling window 30 hari"*. 
- Tuliskan Recording Rules Prometheus untuk melacak SLI latency berbasis histogram bucket Prometheus (`http_request_duration_seconds_bucket`).
- Rancang Alerting Rules untuk 2 tingkatan eskalasi: Paging (BR 14.4) dan Ticket (BR 3).

---

## 20. Summary
- **SLI** mengukur realitas performa teknis. **SLO** menetapkan ekspektasi internal yang realistis. **Error Budget** adalah jembatan kuantitatif yang mengizinkan inovasi berbasis risiko terukur. **SLA** adalah konsekuensi legal/finansial jika SLO terlanggar.
- Pengejaran reliabilitas $100\%$ adalah anti-pola finansial dan arsitektural.
- **Multi-Window Multi-Burn-Rate Alerting** memecahkan masalah alert fatigue dan blind spot alerting tradisional dengan mengorelasikan tingkat keparahan degradasi antara long-term budget impact dan short-term ongoing persistence.
- Keberhasilan Service Level Engineering bergantung pada penegakan **Error Budget Policy** yang mengikat antara tim Engineering dan Product Management.

---