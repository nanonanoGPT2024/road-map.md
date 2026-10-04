# Bab 01 Module 01: Fondasi Site Reliability Engineering (SRE) — Anatomi SLI, SLO, SLA, dan Manajemen Error Budget

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis dan membedakan batasan operasional serta tanggung jawab teknis antara Software Engineering, Traditional SysAdmin, DevOps, dan Site Reliability Engineering (SRE).
*   Merumuskan Service Level Indicators (SLI) berbasis data telemetri yang representatif terhadap *user experience*.
*   Menghitung, menetapkan, dan menegosiasikan Service Level Objectives (SLO) serta Service Level Agreements (SLA) yang realistis secara matematis.
*   Mengimplementasikan mekanisme kalkulasi *Error Budget* dan *Burn Rate* (Single-Window & Multi-Window Multi-Burn-Rate).
*   Membangun sistem *Release Gating* otomatis berbasis sisa *Error Budget* untuk menyeimbangkan kecepatan rilis fitur (*velocity*) dan stabilitas sistem (*reliability*).

---

### 2. Fundamental Concepts (Konsep Fundamental)
Site Reliability Engineering (SRE) lahir dari paradigma yang dicetuskan oleh Ben Treynor Sloss di Google: *"What happens when a software engineer is tasked with what used to be called operations."* Fondasi SRE bertumpu pada sejumlah konsep inti:

*   **Embracing Risk (Penerimaan Risiko):** Keandalan 100% (*100% reliability*) adalah target yang salah dan kontraproduktif. Biaya teknis dan finansial untuk melompat dari 99.9% ke 99.99% tumbuh secara eksponensial, sementara persepsi pengguna dibatasi oleh keandalan jaringan seluler/ISP mereka sendiri (yang rata-rata berada di 95–99%).
*   **Service Level Indicators (SLI):** Ukuran kuantitatif terukur dari performa layanan yang diberikan pada titik waktu tertentu. Formula dasarnya:
    $$\text{SLI} = \frac{\text{Jumlah Kejadian Baik (Good Events)}}{\text{Total Kejadian (Total Events)}} \times 100\%$$
*   **Service Level Objective (SLO):** Target keandalan yang disepakati secara internal oleh tim engineering dan produk (misal: 99.9% request harus berhasil dan disajikan dalam waktu $< 200\text{ms}$ selama periode rolling 30 hari).
*   **Service Level Agreement (SLA):** Perjanjian hukum/kontraktual eksplisit dengan pengguna luar yang memuat sanksi finansial atau penalti (restitusi/kredit tagihan) jika SLO spesifik dilanggar. SLA umumnya selalu dirancang lebih longgar daripada SLO ($\text{SLA} < \text{SLO}$).
*   **Error Budget:** Kuota ketidakandalan (*unreliability*) yang diizinkan untuk sebuah sistem dalam satu periode jendela waktu (misalnya 30 hari).
    $$\text{Error Budget} = 100\% - \text{SLO}$$
*   **Toil Management:** Pekerjaan operasional yang berulang, manual, tidak bernilai jangka panjang, dan berkembang linier terhadap skala layanan. Standar SRE membatasi toil maksimal 50% dari alokasi waktu engineer; sisanya dialokasikan untuk rekayasa perangkat lunak sistem (*engineering project work*).

---

### 3. Why It Matters (Mengapa Ini Penting)
Secara historis, terdapat konflik struktural tak terelakkan di organisasi IT:
*   **Tim Developer:** Diberi insentif untuk meluncurkan fitur secepat mungkin (*Velocity*).
*   **Tim Operasional (SysAdmin):** Diberi insentif untuk menjaga kestabilan infrastruktur, yang berarti meminimalisasi perubahan (*Stability*).

Konflik insentif ini menciptakan dinding isolasi (*silos*), saling tuduh saat terjadi insiden, dan penumpukan *technical debt*. SRE menyelesaikan disonansi kognitif dan organisasional ini secara matematis melalui **Error Budget**.

Ketika *Error Budget* masih melimpah, tim produk bebas mengambil risiko: deploy arsitektur baru, Canary releases, dan eksperimen fitur. Namun, ketika *Error Budget* habis terbakar (*exhausted*), rem otomatis ditarik: *deploy feature freeze* diberlakukan, dan kapasitas engineering dialihkan secara eksklusif untuk perbaikan keandalan, refactoring, mitigasi bug, serta perbaikan observabilitas. 

Keputusan ini bersifat deterministik, berbasis metrik objektif, bukan emosi politik antar-departemen.

---

### 4. What It Is (Apa Itu Sebenarnya)

#### 4.1 Hubungan SRE dan DevOps
Secara formal dinyatakan: `class SRE implements DevOps`. 
DevOps mendefinisikan filosofi kerja sama, otomatisasi delivery, dan continuous feedback. SRE mendefinisikan implementasi konkret, metrik, toolkit, dan rekayasa algoritma operasional untuk mewujudkan filosofi tersebut.

| Aspek | Tradisional SysAdmin | DevOps | Site Reliability Engineering (SRE) |
| :--- | :--- | :--- | :--- |
| **Fokus Utama** | Menjaga server tetap menyala (*uptime*). | Kolaborasi Dev & Ops, CI/CD, kultur. | Mengeliminasi toil dengan software, manajemen risiko probabilistik. |
| **Metrik Kunci** | Uptime server (MTBF, MTTR). | Lead time for changes, deployment frequency. | SLI, SLO, Error Budget Burn Rate, Toil Budget. |
| **Penerimaan Kegagalan** | Dihindari sekuat tenaga (0% failure target). | Diakui sebagai bagian dari iterasi. | Diterima dan dianggarkan secara matematis (*Error Budget*). |
| **Pendekatan Operasi** | Manual execution, ticketing, scripts ad-hoc. | Infrastruktur sebagai Kode (IaC), pipeline otomatis. | Sistem otonom, auto-remediation, Chaos Engineering. |

#### 4.2 Triad SLI, SLO, dan SLA
```
+-------------------------------------------------------------+
| SLA: Perjanjian Eksternal (Legal/Bisnis) -> Misal: 99.5%   |
|   +-------------------------------------------------------+ |
|   | SLO: Target Internal Engineering -> Misal: 99.9%      | |
|   |   +-------------------------------------------------+ | |
|   |   | SLI: Pengukuran Riil Saat Ini -> Misal: 99.94% | | |
|   |   +-------------------------------------------------+ | |
|   +-------------------------------------------------------+ |
+-------------------------------------------------------------+
```
Jika $\text{SLI} < \text{SLO}$, tim engineering internal bertindak secara agresif (menghentikan rilis). Pengguna eksternal belum tentu merasakan dampak kontraktual karena SLA berada di bawah SLO (ada bantalan pengaman sebesar $0.4\%$).

---

### 5. How It Works (Bagaimana Cara Kerjanya)

#### 5.1 Siklus Hidup Error Budget
1.  **Pengukuran Telemetri:** Agen pemantauan (seperti Prometheus) mengumpulkan indikator (misalnya metrik HTTP: total request, response code, latensi).
2.  **Kalkulasi SLI:** Metrik dievaluasi menggunakan filter predikat biner (*Good Events* vs *Total Events*).
3.  **Evaluasi SLO:** Agregasi SLI dihitung sepanjang jendela evaluasi bergulir (*rolling window*, misal 30 hari).
4.  **Kalkulasi Burn Rate:** Mengukur kecepatan konsumsi error budget.
    *   *Burn Rate 1:* Error budget akan habis tepat pada akhir periode jendela waktu (normal).
    *   *Burn Rate 14.4:* Menghabiskan 2% error budget dalam 1 jam, atau 100% budget dalam 2 hari (insiden kritis).
5.  **Aksi Korektif Kebijakan (Policy Enforcement):**
    *   Burn Rate tinggi memicu *pager alert* ke engineer yang sedang on-call.
    *   Error budget $< 0\%$ memicu webhook pemblokiran pipeline deployment di sistem CI/CD.

---

### 6. System Architecture / Flow Diagram (Diagram Arsitektur / Alur Kerja ASCII)

```
                            TRAFFIC MASUK (INBOUND TRAFFIC)
                                         |
                                         v
                         +-------------------------------+
                         |   Ingress / API Gateway       |
                         |   (Envoy / NGINX / Traefik)   |
                         +---------------+---------------+
                                         |
                                         | Inisiasi Metrik Telemetri
                                         v
                         +-------------------------------+
                         | Time-Series Database (TSDB)   |
                         | (Prometheus / Cortex / Thanos)|
                         +---------------+---------------+
                                         |
                       Query SLI (Good vs Total Events)
                                         |
                                         v
                         +---------------+---------------+
                         |      SRE SLO Calculator       |
                         |     & Burn-Rate Evaluator     |
                         +---------------+---------------+
                                         |
                   +---------------------+---------------------+
                   |                                           |
    [Burn Rate Mengancam SLO]                     [Budget Habis: Budget <= 0%]
                   |                                           |
                   v                                           v
    +-------------------------------+           +-------------------------------+
    | Multi-Window Multi-Burn-Rate  |           |     CI/CD Deployment Gate     |
    | Alerting Engine (Alertmanager)|           |   (GitLab CI / ArgoCD / GH)   |
    +---------------+---------------+           +---------------+---------------+
                   |                                           |
                   v                                           v
       Paging On-Call Engineer                        BLOKIR SEMUA RILIS FITUR
     (Opsgenie / PagerDuty / Slack)                   Hanya Patch Keandalan & Bug
```

---

### 7. Step-by-Step Implementation Guide (Panduan Implementasi)

Berikut adalah panduan menetapkan sistem SLO untuk API Service:

#### Langkah 1: Tentukan Batas Layanan (Service Boundaries) dan User Journeys
Identifikasi fungsi kritis sistem. Contoh: Untuk layanan E-Commerce, User Journey kritis adalah *Checkout Process*, bukan sekadar ketersediaan server secara raw.

#### Langkah 2: Pilih Kategori SLI yang Tepat (Spesifikasi Google SRE)
Pilih aspek yang relevan:
*   **Availability (Ketersediaan):** Proporsi request yang berhasil mengembalikan HTTP status $\ne 5xx$.
*   **Latency (Latensi):** Proporsi request yang diselesaikan lebih cepat dari batas ambang (threshold), misal: $\le 300\text{ms}$.
*   **Freshness / Correctness / Throughput:** Jika menangani pipeline data asynchronous/stream.

#### Langkah 3: Formalisasi Formula SLI
Tentukan query matematis di atas time series.
*Contoh Availability SLI:*
$$\text{SLI}_{\text{avail}} = \frac{\sum \text{rate(http\_requests\_total}\{\text{status} ! \sim "5.."\} [30d])}{\sum \text{rate(http\_requests\_total}[30d])}$$

#### Langkah 4: Tentukan Target SLO
Hindari angka emosional seperti 99.999%. Gunakan performa historis. Jika sistem selama ini berjalan pada 99.2%, pasang target realistis berikutnya di 99.5%, evaluasi cost vs benefit-nya.

#### Langkah 5: Dokumentasikan Error Budget Policy
Tulis kesepakatan hitam-di-atas-putih antara Product Management dan Engineering:
*   Apa yang terjadi jika sisa budget mencapai 25%? (Peringatan, investigasi backlog).
*   Apa yang terjadi jika budget habis ($0\%$)? (Deploy freeze, cancel feature rollout, cancel all high-risk changes).

---

### 8. Minimal Working Example (Contoh Minimal yang Berfungsi)

Skrip Python independen berikut menghitung SLI ketersediaan, sisa *Error Budget*, dan *Burn Rate* dari data simulasi request, lalu menentukan apakah deployment harus diizinkan atau diblokir.

```python
#!/usr/bin/env python3
"""
SLO and Error Budget Burn Rate Calculator
Implementasi logika inti evaluasi kelayakan rilis otomatis.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class HTTPRequestLog:
    timestamp_epoch: int
    status_code: int
    latency_ms: float


class SREBudgetEngine:
    def __init__(self, target_slo: float, window_hours: int = 720):
        """
        :param target_slo: SLO target dalam desimal (misal 0.999 untuk 99.9%)
        :param window_hours: Jendela bergulir (default: 720 jam / 30 hari)
        """
        self.target_slo = target_slo
        self.window_hours = window_hours
        self.total_budget = 1.0 - target_slo

    def calculate_sli(self, logs: List[HTTPRequestLog]) -> float:
        if not logs:
            return 1.0

        # Good event: HTTP status bukan 5xx dan latensi <= 500ms
        good_events = sum(
            1 for log in logs 
            if log.status_code < 500 and log.latency_ms <= 500.0
        )
        return good_events / len(logs)

    def evaluate_release_gate(self, logs: List[HTTPRequestLog]) -> dict:
        sli = self.calculate_sli(logs)
        total_requests = len(logs)
        bad_events = sum(
            1 for log in logs 
            if log.status_code >= 500 or log.latency_ms > 500.0
        )
        
        # Anggaran error yang dialokasikan (maksimum kegagalan diizinkan)
        allowed_failures = total_requests * self.total_budget
        remaining_budget = allowed_failures - bad_events
        error_budget_burn_percentage = (bad_events / allowed_failures) * 100 if allowed_failures > 0 else 0.0

        # Burn rate = Kecepatan kegagalan aktual dibanding tingkat kegagalan yang diizinkan SLO
        actual_failure_rate = (bad_events / total_requests) if total_requests > 0 else 0.0
        budget_failure_rate = self.total_budget
        burn_rate = actual_failure_rate / budget_failure_rate if budget_failure_rate > 0 else 0.0

        deployment_allowed = remaining_budget > 0 and burn_rate < 2.0

        return {
            "sli_achieved": round(sli * 100, 3),
            "target_slo": round(self.target_slo * 100, 3),
            "total_requests": total_requests,
            "failed_requests": bad_events,
            "remaining_error_budget_events": max(0, int(remaining_budget)),
            "budget_consumed_pct": round(error_budget_burn_percentage, 2),
            "burn_rate": round(burn_rate, 2),
            "deployment_allowed": deployment_allowed
        }


if __name__ == "__main__":
    # Inisialisasi engine dengan SLO 99.5%
    engine = SREBudgetEngine(target_slo=0.995)

    # 1. Skenario Normal: 10,000 request dengan 20 kegagalan (0.2% kegagalan)
    normal_traffic = (
        [HTTPRequestLog(1609459200, 200, 120.0) for _ in range(9980)] +
        [HTTPRequestLog(1609459200, 500, 600.0) for _ in range(20)]
    )

    result_normal = engine.evaluate_release_gate(normal_traffic)
    print("--- SKENARIO TRAFFIC SEHAT ---")
    for k, v in result_normal.items():
        print(f"{k}: {v}")

    # 2. Skenario Anomali: 10,000 request dengan 80 kegagalan (0.8% kegagalan -> melebihi 0.5% budget)
    degraded_traffic = (
        [HTTPRequestLog(1609459200, 200, 120.0) for _ in range(9920)] +
        [HTTPRequestLog(1609459200, 503, 1200.0) for _ in range(80)]
    )

    result_degraded = engine.evaluate_release_gate(degraded_traffic)
    print("\n--- SKENARIO TRAFFIC DEGRADED ---")
    for k, v in result_degraded.items():
        print(f"{k}: {v}")
```

---

### 9. Real-World Practical Example (Contoh Praktis Dunia Nyata)

Berikut adalah konfigurasi implementasi multi-window multi-burn-rate alerting di **Prometheus** (`prometheus.rules.yaml`) berbasis standar Google SRE Handbook.

Model ini mengecek konsumsi Error Budget menggunakan dua rentang waktu simultan (Short-window & Long-window) untuk mendeteksi lonjakan tajam secara cepat tanpa memicu alarm palsu (*false positives*).

```yaml
groups:
  - name: service_slo_alerts
    rules:
      # Definisi Metrik Intermediate: Error Rate 
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total{job="checkout-api"}[5m]))
      
      - record: job:http_errors:rate5m
        expr: sum(rate(http_requests_total{job="checkout-api", status=~"5.."}[5m]))

      - record: job:http_requests:rate30m
        expr: sum(rate(http_requests_total{job="checkout-api"}[30m]))

      - record: job:http_errors:rate30m
        expr: sum(rate(http_requests_total{job="checkout-api", status=~"5.."}[30m]))

      - record: job:http_requests:rate1h
        expr: sum(rate(http_requests_total{job="checkout-api"}[1h]))

      - record: job:http_errors:rate1h
        expr: sum(rate(http_requests_total{job="checkout-api", status=~"5.."}[1h]))

      - record: job:http_requests:rate6h
        expr: sum(rate(http_requests_total{job="checkout-api"}[6h]))

      - record: job:http_errors:rate6h
        expr: sum(rate(http_requests_total{job="checkout-api", status=~"5.."}[6h]))

      # ALERT KRITIS 1: Menghabiskan 2% Error Budget dalam 1 Jam (Burn Rate = 14.4)
      # Menggunakan kombinasi Long Window (1h) dan Short Window (5m) untuk reset cepat
      - alert: CheckoutServiceHighErrorBudgetBurn_Critical
        expr: |
          (
            job:http_errors:rate1h / job:http_requests:rate1h > (14.4 * (1 - 0.999))
          )
          and
          (
            job:http_errors:rate5m / job:http_requests:rate5m > (14.4 * (1 - 0.999))
          )
        for: 2m
        labels:
          severity: page
          tier: tier-1
        annotations:
          summary: "Kehilangan error budget kritis pada service Checkout"
          description: "Burn rate saat ini > 14.4x. 2% error budget habis dalam 1 jam terakhir. SRE on-call segera tangani."

      # ALERT SLOW-BURN: Menghabiskan 10% Error Budget dalam 6 Jam (Burn Rate = 6)
      - alert: CheckoutServiceSlowErrorBudgetBurn_Warning
        expr: |
          (
            job:http_errors:rate6h / job:http_requests:rate6h > (6 * (1 - 0.999))
          )
          and
          (
            job:http_errors:rate30m / job:http_requests:rate30m > (6 * (1 - 0.999))
          )
        for: 15m
        labels:
          severity: ticket
          tier: tier-1
        annotations:
          summary: "Slow burn rate terdeteksi pada Checkout API"
          description: "Burn rate berada pada 6x lipat selama 6 jam terakhir. Sisa error budget berisiko habis sebelum akhir bulan."
```

---

### 10. Edge Cases and Pitfalls (Kasus Khusus dan Jebakan Implementasi)

1.  **Low Traffic Services:** 
    *   *Masalah:* Pada service internal dengan hanya 10 request/jam, satu response error 500 langsung merusak SLI menjadi 90%, langsung menghabiskan 100% Error Budget bulanan secara tidak representatif.
    *   *Mitigasi:* Tambahkan operator kondisi ambang batas minimum (*minimum request threshold gating*) atau lakukan agregasi batch mingguan/bulanan alih-alih alerting bernilai tinggi.
2.  **Client-Side Abort (HTTP 499 / Connection Reset):**
    *   *Masalah:* Client memutus koneksi karena user refresh browser saat halaman lambat. Ingress mencatat status 499 atau 400.
    *   *Analisis:* Apakah ini kegagalan infrastruktur atau murni user drop? SRE harus mengaudit apakah timeout gateway server yang memicu user putus asa.
3.  **Third-Party Dependency Failure:**
    *   *Masalah:* SLI Anda hancur karena payment gateway eksternal sedang down.
    *   *Mitigasi:* Definisikan SLI berbasis bounded context. Error dari upstream vendor eksternal harus ditangkap di Circuit Breaker, mengembalikan graceful response (misal: HTTP 202 Queued atau pesan informatif HTTP 424 Failed Dependency yang dikecualikan dari SLI sistem internal Anda jika diizinkan oleh kesepakatan produk).

---

### 11. Trade-offs and Alternatives (Kompromi Teknis dan Alternatif)

| Pendekatan Metrik | Kelebihan | Kelemahan / Konsekuensi |
| :--- | :--- | :--- |
| **Traditional Host-based Metrics** (CPU, Memori, Disk I/O) | Sangat mudah dikumpulkan melalui agent OS (Node Exporter). | **Tidak mencerminkan UX.** CPU 98% tidak berarti user mengalami error jika throughput aplikasi masih normal dan response cepat. |
| **Time-based Availability** (Menghitung menit down vs menit total) | Sederhana dipahami manajemen non-teknis. | **Tidak adil terhadap volume traffic.** Down 5 menit jam 3 pagi (10 user terdampak) dihukum sama beratnya dengan down 5 menit saat Black Friday (1.000.000 user terdampak). |
| **Event-based SLI** (Google SRE Standard) | **Akurat terhadap persepsi user.** Menghitung proporsi request spesifik yang sukses terhadap total request. | Kompleksitas tinggi dalam pemrosesan TSDB. Butuh instrumentasi kode aplikasi yang presisi. |

---

### 12. Best Practices and Industry Standards (Praktik Terbaik dan Standar Industri)

*   **Pemberlakuan Standar HTTP Status:** Standarisasi internal: Jangan pernah menyembunyikan kegagalan sistem di balik HTTP 200 dengan payload `{"status": "error"}`. Ini merusak kemampuan reverse proxy dalam menghitung SLI ketersediaan secara netral.
*   **The Four Golden Signals (Google SRE):**
    1.  *Latency:* Waktu melayani request. Bedakan latensi request sukses vs gagal.
    2.  *Traffic:* Volume demand pada sistem (QPS, throughput byte/sec).
    3.  *Errors:* Laju request yang gagal secara fungsional.
    4.  *Saturation:* Fraksi utilisasi sumber daya komputasi yang paling tertekan (memory pool, thread pool, network queue).
*   **Rolling Window vs Calendar Window:** Gunakan Rolling Window (misal: 30 hari bergulir, bukan 1 Januari - 31 Januari). Rolling window mencegah fenomena anomali di mana tanggal 1 setiap bulan menjadi zona "bebas resiko ceroboh" karena budget di-reset ke nol.

---

### 13. Failure Scenarios and Recovery (Skenario Kegagalan dan Pemulihan)

#### Skenario: "Alert Storming" Akibat Evaluasi SLO Single-Window Sederhana
*   **Akar Masalah:** Sistem menggunakan query tunggal `rate(http_errors_total[5m]) > 0.001` untuk mengirim SMS/Pager ke tim on-call. Saat ada micro-spike 10 detik akibat restart node, alarm berdering di tengah malam, namun saat engineer membuka laptop, sistem sudah pulih.
*   **Dampak:** Kelelahan on-call (*Alert Fatigue*), berujung pada pengabaian alarm (*alarm apathy*) saat insiden nyata skala besar terjadi.
*   **Langkah Pemulihan:**
    1.  Ganti arsitektur alerting dengan **Multi-Window Multi-Burn-Rate**.
    2.  Terapkan logika korelasi: Pager hanya berbunyi jika window 14.4x burn rate aktif di time window 1 jam DAN didukung konsistensi error rate pada 5 menit terakhir.
    3.  Arahkan anomali minor (burn rate rendah tapi persisten) ke kanal asynchronous (Jira Ticket / Slack Notification), bukan paging PagerDuty.

---

### 14. Security and Compliance Considerations (Pertimbangan Keamanan dan Kepatuhan)

*   **Audit Trail Pembatalan Deployment Freeze:** Jika Error Budget habis namun pimpinan bisnis menuntut "Emergency Feature Release", aksi *override* ini harus dicatat di immutable compliance audit log (misal: AWS CloudTrail, SIEM) dengan tanda tangan digital penanggung jawab risiko.
*   **Data Sanitization pada Metrik SLI:** Label metric Prometheus tidak boleh mengandung PII (Personally Identifiable Information) seperti User ID, Token, Email, atau NIK. Hal ini melanggar GDPR/UU PDP dan mengakibatkan meledaknya kardinalitas metrik TSDB (*cardinality explosion*), yang dapat melumpuhkan sistem monitoring utama saat terjadi serangan DoS.

---

### 15. Observability and Monitoring (Observabilitas dan Pemantauan)

Untuk mengeksekusi perhitungan SLI/SLO secara presisi, gunakan konfigurasi export metrik Prometheus dengan histogram bucket yang dirancang menggunakan skala logaritmik eksponensial di layer reverse proxy/aplikasi:

```python
# Contoh implementasi instrumentasi Prometheus Python Client
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests processed',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'Latency HTTP requests in seconds',
    ['method', 'endpoint'],
    # Pemilihan bucket latensi penting untuk SLI granular
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)
```

Query Prometheus (PromQL) untuk menghitung Latency SLI (% request di bawah 250ms):
```promql
sum(rate(http_request_duration_seconds_bucket{endpoint="/api/v1/order", le="0.25"}[30d]))
/
sum(rate(http_request_duration_seconds_count{endpoint="/api/v1/order"}[30d]))
* 100
```

---

### 16. Performance and Scalability (Kinerja dan Skalabilitas)

*   **Penyimpanan dan Agregasi Metrik Jarak Panjang:** Menghitung query SLI 30 hari secara real-time (`[30d]`) langsung di Prometheus vanilla akan memicu I/O thrashing dan OOM (*Out-of-Memory*) crash karena TSDB harus menelusuri miliaran raw samples.
*   **Strategi Skalabilitas:**
    *   Wajib gunakan **Recording Rules** di Prometheus untuk mengakumulasi raw metrics menjadi data rate 5-menitan terlebih dahulu (`record: job:http_requests:rate5m`).
    *   Gunakan engine federasi seperti **Thanos**, **Cortex**, atau **M3DB** dengan downsampling data (resolusi 5m dan 1h) untuk evaluasi SLO multi-bulan tanpa membebani performa scraping realtime.

---

### 17. Testing and Verification (Pengujian dan Verifikasi)

Bagaimana menguji validitas alerting SLO Anda? Lakukan simulasi pembakaran budget menggunakan Chaos Engineering framework atau load tester sederhana (seperti `k6`):

```javascript
// Script K6: simulate_burn_rate.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 50 },  // Traffic normal
    { duration: '3m', target: 200 }, // Injeksi overload traffic
  ],
};

export default function () {
  // Hit route yang secara sengaja melempar status 503 untuk membakar budget
  const res = http.get('http://api.staging.internal/checkout?inject_fault=503');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.1);
}
```

Verifikasi:
1.  Jalankan skrip di staging.
2.  Pantau apakah alert `CheckoutServiceHighErrorBudgetBurn_Critical` menyala tepat pada waktu kalkulasi teoritis ($< 5\text{ menit}$).
3.  Pastikan alert kembali padam (*auto-resolve*) saat pengujian dihentikan.

---

### 18. Common Anti-Patterns (Anti-Pattern Umum)

1.  **"Target 100% Reliability":** Tidak realistis secara hukum fisika jaringan data, membunuh inovasi developer, dan menghabiskan biaya infrastruktur secara mubazir.
2.  **SLO Vanity Metrics (Target SLO Tanpa Konsekuensi):** SLO disusun dan dipasang di dashboard dinding kantor, tetapi saat budget habis, tim tetap diizinkan deploy fitur baru yang belum stabil. Ini mereduksi SLO hanya menjadi pajangan visual (*vanity*).
3.  **Terlalu Banyak SLO:** Menetapkan 50 SLO berbeda untuk 1 microservice. Akibatnya tim bingung merespons alarm yang bertolak belakang. 
    *   *Solusi:* Fokus maksimal pada 3–5 SLI representatif per user journey kritis.
4.  **Menjadikan SLA Sebagai SLO:** Jika SLA kontrak bernilai 99.5%, jangan gunakan 99.5% sebagai SLO internal. Tetapkan SLO di 99.9%. Gap $0.4\%$ adalah zona penyangga keselamatan finansial (*safety margin*).

---

### 19. Summary and Key Takeaways (Ringkasan dan Poin Kunci)

*   SRE mentransformasikan manajemen operasional menjadi disiplin rekayasa perangkat lunak probabilistik.
*   **SLI** mengukur performa riil, **SLO** menetapkan target internal sistem, dan **SLA** memberikan proteksi kontraktual hukum.
*   **Error Budget** adalah mekanisme rekonsiliasi matematis antara kecepatan rilis software (*Product Velocity*) dan ketahanan infrastruktur (*Operational Stability*).
*   Gunakan pendekatan **Multi-Window Multi-Burn-Rate** berbasis Recording Rules untuk memangkas *alert fatigue* tanpa menurunkan kepekaan sistem terhadap down-time fatal.
*   Reliabilitas adalah fitur nomor satu produk: jika sistem Anda tidak dapat diakses, fitur secanggih apapun yang ada di dalamnya tidak memiliki nilai bagi pengguna.

---

### 20. Self-Assessment Exercises (Latihan Penilaian Mandiri)

1.  **Kalkulasi Downtime Error Budget:**
    Sebuah sistem Payment Gateway memiliki SLO Availability sebesar $99.95\%$ per jendela waktu rolling 30 hari.
    *   *Pertanyaan:* Berapa menit total downtime maksimal yang diizinkan sebelum Error Budget habis terbakar?
    *   *Jawaban Teknis:* 
        Total menit dalam 30 hari = $30 \times 24 \times 60 = 43.200\text{ menit}$.
        Toleransi error = $100\% - 99.95\% = 0.05\% = 0.0005$.
        Downtime diizinkan = $43.200 \times 0.0005 = \mathbf{21.6\text{ menit}}$.

2.  **Kalkulasi Burn Rate:**
    Jika dalam waktu 1 jam sistem Anda mengalami kegagalan penuh ($100\%$ failure rate) pada layanan yang memiliki target SLO $99.9\%$ untuk periode 30 hari:
    *   *Pertanyaan:* Berapa Burn Rate yang sedang berjalan? Berapa persen total Error Budget bulanan yang hangus dalam durasi 1 jam tersebut?
    *   *Jawaban Teknis:*
        Total toleransi error bulanan = $0.1\%$.
        Total jam per 30 hari = 720 jam.
        Kegagalan 100% selama 1 jam berarti menghabiskan:
        $$\frac{1}{720 \times 0.001} = \frac{1}{0.72} \approx 1.3888 \text{ atau } 138.8\% \text{ dari total Error Budget}$$
        Burn rate = $\mathbf{720x}$. Seluruh budget bulanan Anda musnah dalam waktu sekitar 43 menit jika degradasi berlanjut.

3.  **Tugas Analisis Desain:**
    *Rancang satu set definisi SLI (Formula & Metrik Input) untuk sistem Streaming Video (seperti Netflix/YouTube). Pertimbangkan parameter apa saja selain HTTP Availability yang merefleksikan kegagalan streaming secara langsung bagi pengguna akhir!*