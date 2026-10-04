# Module 02: Distributed Tracing, Structured Logging, & Metrik (OpenTelemetry & Prometheus)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Menguasai **Tiga Pilar Observabilitas**: **Metrik (Metrics)**, **Log Terstruktur (Structured Logs)**, dan **Pelacakan Terdistribusi (Distributed Traces)**.
- Menerapkan metodologi pengukuran: **RED Method** (untuk microservices) dan **USE Method** (untuk infrastruktur).
- Memahami arsitektur **OpenTelemetry (OTel)** dan standar **W3C Trace Context** (`traceparent`).
- Melacak perjalanan satu request pengguna yang melintasi puluhan microservices independen (*Trace propagation & Span hierarchy*).

## 2. Prerequisite
- Memahami konsep microservices, HTTP headers, dan Latency p50/p95/p99 dari BAB 01 & BAB 06.

## 3. Concept
Dalam monolit klasik, mencari bug cukup dengan membuka satu berkas log server (`tail -f app.log`). Namun dalam arsitektur sistem terdistribusi modern dengan 50 microservices di Kubernetes, satu klik tombol "Beli" oleh pengguna dapat memicu rantai 20 panggilan RPC lintas service.

Jika pengguna mengeluh: *"Proses checkout saya lambat, butuh 8 detik!"*, bagaimana Anda tahu di service mana waktu 8 detik itu terbuang? Apakah di Payment Service? Database lock? Atau antrian message queue?

Inilah esensi **Observabilitas (Observability)**: kemampuan untuk menyimpulkan kondisi internal suatu sistem berdasarkan output eksternal yang dihasilkannya. Tiga instrumen utamanya adalah:
1. **Metrics**: Data numerik teragregasi sepanjang waktu (Menjawab: *"Apakah ada masalah sekarang?"*).
2. **Logs**: Rekaman peristiwa diskrit berformat JSON (Menjawab: *"Apa detail peristiwa error tersebut?"*).
3. **Traces**: Peta perjalanan request end-to-end melintasi batas jaringan (Menjawab: *"Di mana letak bottleneck waktu dan dependensi yang rusak?"*).

## 4. Why?
- **Mean Time to Detection (MTTD) & Resolution (MTTR)**: Menemukan akar masalah dalam 2 menit alih-alih 6 jam debat antar tim backend.
- **Deteksi Latency Tail (p99)**: Membedakan apakah kelambatan terjadi di kode aplikasi atau query database downstream.
- **Korelasi Data Holistik**: Menghubungkan log error tertentu langsung ke visualisasi flame graph trace-nya melalui `trace_id`.

## 5. What?
### Metodologi Pemantauan Metrik:
1. **RED Method (Tom Wilkie - Untuk Request-Driven Services)**:
   - **Rate**: Jumlah request per detik (QPS).
   - **Errors**: Jumlah request yang gagal (HTTP 5xx).
   - **Duration**: Berapa lama waktu yang dibutuhkan request (Latency Histogram: p50, p90, p99).
2. **USE Method (Brendan Gregg - Untuk Resource & Hardware)**:
   - **Utilization**: Berapa persen resource sibuk (misal: CPU 85%).
   - **Saturation**: Berapa banyak pekerjaan antri yang tertahan (misal: Linux Load Average > Core count).
   - **Errors**: Jumlah error perangkat keras/koneksi (misal: Network packet drops).

### Anatomi Distributed Tracing (OpenTelemetry Standard):
- **Trace**: Mewakili perjalanan menyeluruh satu request pengguna dari awal hingga selesai. Memiliki `Trace ID` unik (128-bit hex string).
- **Span**: Satu unit kerja tunggal di dalam satu service (misal: eksekusi query SQL atau panggilan HTTP client). Memiliki `Span ID`, `Parent Span ID`, `Name`, `Start Time`, `End Time`, dan `Attributes`.
- **W3C Trace Context Header**: Header HTTP standar (`traceparent`) yang dioper antar-service:
  `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  *(Version - TraceID - ParentSpanID - TraceFlags)*.

## 6. How?
### Alur Propagasi Konteks (Context Propagation):
```text
[Browser User]
      │
      ├── 1. POST /checkout ──> [API Gateway]
      │                         (Generate TraceID: T1, SpanID: S1)
      │                                │
      │                                ├── 2. HTTP Call + Header [traceparent: T1-S1]
      │                                ▼
      │                         [Order Service]
      │                         (Buat Child Span S2, Parent: S1)
      │                                │
      │                                ├── 3. HTTP Call + Header [traceparent: T1-S2]
      │                                ▼
      │                         [Payment Service]
      │                         (Buat Child Span S3, Parent: S2)
      │                                │
      │                                └── 4. DB Query: SELECT balance (Child Span S4)
```
Semua span diekspor (*OpenTelemetry OTLP Collector*) ke backend visualisasi seperti **Jaeger** atau **Grafana Tempo**, yang merekonstruksinya menjadi grafik batang waktu hierarkis (*Waterfall / Gantt chart*).

## 7. Analogy
- **Metrics = Dashboard Mobil**: Spedometer (Rate), Lampu Check Engine (Errors), Indikator Bensin (Utilization). Memberitahu Anda ada yang salah, tapi tidak memberitahu mur mana yang copot di dalam mesin.
- **Logs = Buku Harian Kapal (Ship's Logbook)**: Catatan kronologis: *"Pukul 14:02 mesin kiri mati karena pipa bahan bakar tersumbat"*.
- **Distributed Trace = Paket Pengiriman JNE dengan Resi Global**: Anda melacak paket dari toko $\rightarrow$ gudang transit A (1 hari) $\rightarrow$ bandara (2 jam) $\rightarrow$ kurir lokal (3 hari). Anda langsung tahu bahwa kurir lokal yang menyebabkan keterlambatan!

## 8. Diagram

```text
================ DISTRIBUTED TRACE WATERFALL VIEW ================
Trace ID: 7f8a9b... Total Duration: 820ms

[API Gateway: /checkout]               |====================================| 820ms
  ├── [Auth: Verify JWT]               |===| 40ms
  └── [Order Service: Create]              |================================| 760ms
        ├── [Stock Service: Reserve]       |====| 60ms
        └── [Payment Service: Charge]           |===========================| 680ms
              └── [Postgres: UPDATE balance]         |======================| 550ms (BOTTLENECK!)
```

## 9. Simple Example
Perbandingan Plain Text Log vs Structured JSON Log:
- **Plain Text (Buruk & Sulit Di-parse)**:
  `2026-09-11 10:45:00 ERROR Order 99 failed for user 55: timeout`
- **Structured JSON Log (Mudah Di-filter & Di-query di Elasticsearch / Loki)**:
  ```json
  {
    "timestamp": "2026-09-11T10:45:00.123Z",
    "level": "ERROR",
    "service": "order-service",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "user_id": 55,
    "order_id": 99,
    "error_type": "DatabaseTimeoutException",
    "duration_ms": 3004
  }
  ```

## 10. Practical Example: Logging Correlation di Production
Ketika pengguna melapor error dengan menyertakan pesan: *"Error ID: 4bf92f3577b3"*, engineer cukup memasukkan ID tersebut ke Grafana / Datadog:
Sistem seketika menampilkan seluruh baris log dari 8 microservice berbeda yang memiliki `trace_id` yang sama, beserta grafik latensi masing-masing langkah!

## 11. Real World Example
- **Uber (Jaeger Tracing)**: Uber memproses miliaran panggilan RPC antar ribuan microservices mereka. Mereka menciptakan platform *Jaeger* (kini proyek open source CNCF) untuk memvisualisasikan ketergantungan antar-layanan (*Service Dependency Graph*) dan mendeteksi microservices zombie yang tidak efisien.
- **Stripe**: Menggunakan Prometheus alerts berbasis SLO Error Budget Burn Rate: alih-alih panik jika ada 1 error sesaat, alarm hanya berbunyi jika laju kegagalan akan menghabiskan kuota downtime bulanan dalam 1 jam ke depan.

## 12. Trade-offs

| Aspek Observabilitas | Kelebihan | Kerugian / Biaya |
|---|---|---|
| **Metrics (Prometheus)** | Sangat ringan, retensi data panjang (bulan/tahun), alert cepat | Nol informasi konteks detail individual transaksi |
| **Structured Logs** | Konteks sangat kaya untuk debugging akar masalah | Membutuhkan storage disk raksasa (TB/hari), butuh log sampling |
| **Distributed Traces** | Visualisasi end-to-end latensi & peta dependensi microservices | Overhead jaringan untuk passing header & storage collector |

## 13. When To Use
- Wajib untuk setiap sistem microservices, service mesh, dan arsitektur multi-service terdistribusi.
- Sistem dengan SLA ketat (Fintech, Core Banking, E-Commerce checkout).

## 14. When NOT To Use Full Tracing (100% Sampling)
- Jangan merekam 100% trace pada sistem dengan volume jutaan QPS. Gunakan **Trace Sampling Rate** (misal: rekam 1% dari transaksi normal, dan 100% dari transaksi yang menghasilkan status HTTP 5xx atau latensi > 1 detik / *Tail-based sampling*).

## 15. Common Mistakes
1. **Logging Data Sensitif (PII Leakage)**: Mencetak nomor kartu kredit, password mentah, atau token JWT ke berkas log. Ini pelanggaran hukum GDPR dan PCI-DSS! Selalu pasang regex sanitizer/masking.
2. **Tracing Tanpa Context Propagation**: Service A memanggil Service B via message queue, tetapi developer lupa memasukkan header `traceparent` ke metadata pesan broker, sehingga rantai trace terputus di tengah jalan (*broken trace*).
3. **Kardinalitas Metrik Terlalu Tinggi (High Cardinality Explosion)**: Memasukkan `user_id` atau `email` sebagai label metrik Prometheus (`http_requests_total{user_id="123"}`). Prometheus akan kehabisan RAM karena menghasilkan jutaan timeseries baru! Label metrik hanya boleh memiliki variasi kecil (misal: `status_code`, `method`, `endpoint`).

## 16. Best Practices
- **Adopsi OpenTelemetry (OTel)**: Gunakan standar open-source OTel SDK netral agar tidak terkunci (*vendor lock-in*) ke vendor APM komersial tertentu (Datadog, Dynatrace, New Relic).
- **Semua Log Wajib Memiliki Trace ID**: Pastikan middleware logging otomatis menyuntikkan `trace_id` ke setiap baris log.
- **Alerting Berbasis SLO, Bukan Threshold Statis**: Jangan kirim SMS ke engineer tiap kali CPU mencapai 80%. Kirim alert jika User-Facing Latency p99 melanggar SLO perjanjian pelanggan!

## 17. Troubleshooting
- **Masalah: Trace muncul terpecah menjadi beberapa trace terpisah di Jaeger**.
  - *Sebab*: Async background task atau HTTP client me-reset context dan tidak meneruskan header `traceparent` ke downstream.
  - *Solusi*: Gunakan OTel Auto-Instrumentation atau pastikan manual context injector dijalankan sebelum remote call.

## 18. Hands-on Practice
Mari kita jalankan simulasi distributed tracing lengkap dari awal: membuat Trace ID, propagasi context via header HTTP virtual, perekaman span hierarkis, dan pembuatan flame graph ASCII di `hands-on/m02/distributed_tracer_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Tulis format header string W3C `traceparent` yang valid untuk Version 00, Trace ID `4bf92f3577b34da6a3ce929d0e0e4736`, Span ID `00f067aa0ba902b7`, dan Sampled flag aktif (`01`).
- **Challenge**: Rancang arsitektur *Tail-Based Sampling Collector* yang menahan trace di memori buffer selama 10 detik, lalu hanya menyimpan trace ke disk jika durasi total > 1000ms atau jika salah satu span memiliki status code >= 500.

## 20. Summary
Observabilitas adalah mata dan telinga dari sistem terdistribusi modern. Dengan mengombinasikan **Metrics** (RED/USE) untuk deteksi instan, **Distributed Tracing** (OpenTelemetry) untuk visualisasi bottleneck latensi, dan **Structured Logging** dengan korelasi `trace_id` untuk forensik error, arsitek sistem dapat mendiagnosis dan menyelesaikan insiden dalam hitungan menit.
