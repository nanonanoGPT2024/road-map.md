# Evaluasi Bab 10: Enterprise Observability, Logpush Pipeline, & SIEM

---

## I. Basic Questions (5 Soal)

### Soal 1
Format default apa yang digunakan oleh Cloudflare Logpush untuk mengirimkan kumpulan record log ke storage bucket atau endpoint SIEM?
* A. XML terkompresi TAR
* B. Newline Delimited JSON (NDJSON) terkompresi GZIP
* C. CSV terkompresi BZIP2
* D. Parquet binary terkompresi Snappy

### Soal 2
Dataset Logpush manakah yang secara spesifik mencatat aksi pemblokiran oleh Web Application Firewall (WAF) dan Rate Limiting?
* A. `http_requests`
* B. `spectrum_events`
* C. `firewall_events`
* D. `audit_logs`

### Soal 3
Sebelum Cloudflare Logpush mulai mengirim log ke AWS S3, tahapan verifikasi apa yang wajib diselesaikan oleh administrator infrastruktur?
* A. Mengirim email konfirmasi ke tim support Cloudflare.
* B. Mengunggah sertifikat SSL kustom ke Cloudflare Dashboard.
* C. Menyelesaikan Ownership Challenge dengan membaca token validasi di destination target.
* D. Membuat instance EC2 sebagai proxy logging Cloudflare.

### Soal 4
Tipe data apa saja yang didukung oleh Cloudflare Workers Analytics Engine untuk penulisan data telemetry (`writeDataPoint`)?
* A. Hanya format string dan integer.
* B. `blobs` (strings), `doubles` (numbers), dan `indexes` (primary string keys).
* C. Nested JSON objects dan array arbitrary.
* D. binary buffers dan raw pointers.

### Soal 5
Apa perbedaan mendasar antara Cloudflare `audit_logs` dan `http_requests`?
* A. `audit_logs` mencatat transaksi traffic pengunjung website; `http_requests` mencatat login admin.
* B. `audit_logs` merekam aktivitas perubahan konfigurasi akun oleh pengguna/token; `http_requests` merekam lalu lintas HTTP yang melintasi edge network.
* C. `audit_logs` hanya tersedia di akun Free; `http_requests` hanya tersedia di Enterprise.
* D. Tidak ada perbedaan, keduanya dataset yang identik.

---

## II. Intermediate Questions (5 Soal)

### Soal 6
Dalam implementasi enterprise, mengirimkan 100% log HTTP `200 OK` ke vendor SIEM berbasis volume ingest (seperti Datadog atau Sumo Logic) dianggap sebagai anti-pattern karena memicu pembengkakan biaya. Fitur Logpush apa yang paling tepat dikonfigurasi untuk membatasi traffic sukses namun tetap mempertahankan visibilitas statistik performa?
* A. Menonaktifkan Logpush dan beralih ke snapshot manual.
* B. Mengonfigurasi parameter `sample` (misalnya `0.02` untuk sampling 2%) dan menyaring field non-esensial via `field_names`.
* C. Mengubah format output menjadi plain text.
* D. Menunda pengiriman log menjadi mingguan.

### Soal 7
Perhatikan blok konfigurasi filter Logpush berikut:
```json
{
  "where": {
    "and": [
      { "key": "EdgeResponseStatus", "operator": "greaterThan", "value": 499 },
      { "key": "ClientRequestPath", "operator": "startsWith", "value": "/api/v1/" }
    ]
  }
}
```
Log request manakah yang **akan** dikirimkan oleh Logpush ke endpoint SIEM?
* A. GET `/api/v1/users` dengan status code `200`
* B. POST `/api/v2/orders` dengan status code `500`
* C. POST `/api/v1/checkout` dengan status code `502`
* D. GET `/static/app.js` dengan status code `500`

### Soal 8
Saat mengeksekusi Workers Analytics Engine via SQL API, Anda ingin melihat endpoint mana yang memiliki p99 latency tertinggi. Mengapa data point Analytics Engine mampu menangani jutaan URL unik tanpa mengalami *cardinality explosion* seperti yang umum terjadi pada database time-series tradisional (misalnya Prometheus)?
* A. Analytics Engine menghapus semua URL yang tidak berulang.
* B. Arsitektur Analytics Engine menggunakan columnar storage berbasis sampling terdistribusi yang memisahkan index string (`blobs`) dari engine metrik, dioptimalkan untuk kueri agregasi OLAP.
* C. Analytics Engine mengompresi setiap URL menjadi 1-byte hash sebelum disimpan.
* D. Analytics Engine membatasi penyimpanan hanya untuk 100 data point per jam.

### Soal 9
Jika sebuah job Logpush mendadak berstatus `failing` selama beberapa jam, apa yang akan terjadi pada data log Cloudflare selama jendela waktu kegagalan tersebut?
* A. Cloudflare menyimpan log dalam antrean tak terbatas hingga target online kembali.
* B. Log akan dibuang secara permanen setelah buffer sementara di edge kedaluwarsa (retensi retry drop window ~24 jam).
* C. Cloudflare menghentikan seluruh lalu lintas web yang masuk ke website.
* D. Log dikirimkan otomatis ke alamat email owner akun.

### Soal 10
Pada arsitektur AWS S3 cold storage untuk Logpush, mengapa bucket policy wajib memberikan izin kepada AWS Principal ARN `arn:aws:iam::395540211218:root`?
* A. Itu adalah ARN root account milik AWS Security Team untuk validasi malware.
* B. Itu adalah IAM identity resmi milik sistem worker Logpush Cloudflare global untuk operasi `s3:PutObject`.
* C. Itu adalah akun dummy yang disediakan AWS untuk testing Terraform.
* D. Itu adalah ARN dari instance EC2 administrator lokal.

---

## III. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: Deteksi Serangan Credential Stuffing & Cost Management
**Kasus:**
Perusahaan e-commerce Anda mengalami serangan Credential Stuffing masif yang menargetkan endpoint `/auth/login`. Serangan tersebut menghasilkan 50 juta request blocked per hari. Akibatnya, tagihan ingest Datadog SIEM membengkak 400% dalam 3 hari pertama karena seluruh raw payload log dikirimkan ke Datadog.

**Pertanyaan:**
Bagaimana Anda menyusun arsitektur telemetri Logpush ganda (multi-pipeline) untuk memecahkan masalah visibilitas keamanan tanpa memicu kebangkrutan biaya ingest SIEM? Rinci dataset, filtering, dan storage destination yang digunakan!

### Skenario 2: Investigasi Insiden Insider Threat & Audit Log Forensics
**Kasus:**
Pada hari Minggu pukul 02:00 dini hari, sebuah rule WAF kritis yang melindungi database pembayaran dinonaktifkan, mengakibatkan injeksi SQL berhasil menembus origin. Tidak ada engineer yang mengaku melakukan perubahan tersebut.

**Pertanyaan:**
Langkah-langkah terstruktur apa yang harus diambil oleh tim Security Incident Response menggunakan Cloudflare Audit Logs API dan SIEM untuk membuktikan:
1. Siapa aktor (User/API Token) yang mengubah konfigurasi?
2. Dari IP mana perubahan diinisiasi?
3. Rule ID mana yang diubah serta nilai konfigurasi *before vs after*?

### Skenario 3: Edge Metric Observability Tanpa SIEM External
**Kasus:**
Tim SRE Anda memerlukan dashboard real-time yang memantau performa cold-start dan upstream response time dari Cloudflare Worker di 250+ data center (Colo) global dengan granularitas per customer ID. Tim FinOps melarang pengiriman data ini ke vendor observabilitas eksternal karena kendala regulasi data sovereignty dan biaya.

**Pertanyaan:**
Rancang arsitektur telemetri berbasis **Cloudflare Workers Analytics Engine** murni untuk menyelesaikan kebutuhan ini, mencakup penulisan data (`writeDataPoint`) di Worker code dan visualisasi metrik menggunakan kueri SQL.

---

## IV. Practical Chapter Challenge (Arsitektur Capstone)

### Deskripsi Tantangan
Anda ditunjuk sebagai Principal Infrastructure & Edge Architect untuk membangun platform *Secure Edge Ingress Pipeline* yang sepenuhnya dikelola via Terraform/OpenTofu dan Worker code mandiri. 

### Kriteria Kebutuhan Capstone:
1. **Terraform IaC:**
   * Konfigurasi AWS S3 Bucket dengan enkripsi default, lifecycle policy (30 hari Standard -> 60 hari Glacier -> 365 hari Expire).
   * Konfigurasi bucket policy untuk Cloudflare Logpush.
   * Dua buah job `cloudflare_logpush_job`:
     * **Job 1 (Compliance):** HTTP Requests lengkap ke S3 Bucket.
     * **Job 2 (SecOps Hot SIEM):** Firewall Events dengan filter aksi `block`, `challenge`, atau `managed_challenge` dialirkan langsung ke generic webhook / SIEM receiver.
2. **Workers Instrumentation:**
   * Script Cloudflare Worker (`edge-router.ts` / `edge-router.js`) yang mengintercept seluruh request, menyuntikkan header trace `X-Edge-Origin-Latency`, dan menuliskan data point Analytics Engine yang mencatat: `RayID`, `Colo`, `Path`, `Status Code`, dan `OriginDurationMs`.
3. **Simulasi Monitoring & Alerting Script:**
   * Buat skrip simulasi penerima SIEM mandiri (Python) yang dapat menerima payload NDJSON GZIP dari Logpush, mendekompresi, memparsing, dan mendeteksi anomali spike error HTTP 5xx secara real-time.

---

## Kunci Jawaban & Panduan Solusi

### I. Basic Questions
1. **B** - Newline Delimited JSON (NDJSON) terkompresi GZIP adalah format baku Logpush untuk memaksimalkan efisiensi kompresi dan kecepatan streaming data berukuran gigabyte.
2. **C** - Dataset `firewall_events` secara spesifik mencatat seluruh evaluasi security engine (WAF, Rate Limiting, Bot Management, Security Level).
3. **C** - Ownership Challenge membuktikan bahwa pemohon job Logpush memang memiliki hak akses tulis ke direktori target storage bucket.
4. **B** - Workers Analytics Engine membatasi input ke dalam 3 struktur array: `blobs` (teks), `doubles` (angka kuantitatif), dan `indexes` (primary string partition key).
5. **B** - `audit_logs` adalah log kontrol plane (siapa mengubah apa di setting Cloudflare), sedangkan `http_requests` adalah log data plane (siapa mengakses website apa di edge).

### II. Intermediate Questions
6. **B** - Menggunakan sampling (misal 1-2%) dan melakukan eliminasi field non-kritis secara drastis memotong volume megabyte yang di-ingest oleh SIEM komersial tanpa menghilangkan tren representatif.
7. **C** - Filter mensyaratkan `EdgeResponseStatus > 499` (yaitu 500 ke atas) DAN `ClientRequestPath` berawalan `/api/v1/`. Opsi C (`/api/v1/checkout` status 502) memenuhi kedua kriteria tersebut.
8. **B** - Analytics Engine dibangun di atas arsitektur data OLAP columnar terdistribusi internal Cloudflare, di mana field string diperlakukan sebagai dimensi columnar, bukan index time-series berbasis memory map seperti Prometheus.
9. **B** - Buffer edge Cloudflare memiliki batas retensi sementara (~24 jam). Jika tujuan gagal merespons secara terus-menerus, data log selama jeda tersebut akan dibuang permanen (dropped) untuk mencegah crash memori edge.
10. **B** - `395540211218` adalah AWS Account ID resmi yang terdaftar secara publik milik Cloudflare untuk layanan streaming Logpush.

### III. Scenario-Based Questions
* **Skenario 1 (Credential Stuffing):**
  Pisahkan pipeline menjadi dua jalur:
  1. *Jalur Cold Storage (AWS S3):* Logpush dataset `http_requests` dan `firewall_events` 100% tanpa filter diarahkan ke S3 Bucket dengan storage class Infrequent Access. Ini menjaga data compliance tanpa biaya ingest analitik mahal.
  2. *Jalur Hot SIEM (Datadog):* Logpush dataset `firewall_events` terfilter hanya untuk endpoint `/auth/login` dengan sampling rate 5% untuk event blokir massal, atau hanya mengirim agregat status via metric summary, serta membuang field payload besar seperti `ClientRequestHeaders`.
* **Skenario 2 (Insider Threat):**
  1. Kueri Cloudflare Audit Logs API: `GET /accounts/{account_id}/audit_logs?action.type=update&since=2023-10-XXT00:00:00Z`.
  2. Parse output JSON pada field `actor.email` atau `actor.id` untuk membuktikan entitas yang menandatangani token API/sesi login.
  3. Periksa field `actor.ip` untuk mencatat alamat IP sumber penyerang.
  4. Analisis field `old_value` dan `new_value` pada sub-objek target resource WAF Rule untuk melihat perbedaan rule sebelum dan sesudah dimatikan.
* **Skenario 3 (Analytics Engine):**
  1. Binding Analytics Engine diinisialisasi pada `wrangler.toml`: `analytics_engine_datasets = [{ binding = "PERF_METRICS" }]`.
  2. Worker Worker fetch handler memanggil `PERF_METRICS.writeDataPoint({ blobs: [colo, customerId, path], doubles: [originDurationMs, coldStartFlag], indexes: [customerId] })`.
  3. Buat microservice internal atau Grafana dashboard yang mengeksekusi REST API kueri SQL Cloudflare:
     `SELECT blob1 as Colo, AVG(double1) as LatencyP99 FROM PERF_METRICS WHERE timestamp > NOW() - INTERVAL '1' HOUR GROUP BY Colo`.

---