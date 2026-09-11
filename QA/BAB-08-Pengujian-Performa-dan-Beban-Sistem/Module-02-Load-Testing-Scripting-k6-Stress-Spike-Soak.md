---
[⬅️ Module 01: Performance Fundamentals & Percentiles](./Module-01-Fondasi-Performance-Testing-Throughput-Latency-Percentiles.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 08 ➡️](./BAB-08-Quiz-dan-Challenge.md)
---

# Module 02: Otomasi Uji Beban Modern dengan Grafana k6: Stress, Spike, Soak Testing, & Quality Gates (Thresholds)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami arsitektur modern **Grafana k6** (Go-based performance engine dengan JavaScript ES6 runtime) yang sangat hemat memori dibandingkan tool legacy berbasis JVM berat (*Apache JMeter*).
- Menguasai perancangan beban kerja menggunakan **Virtual Users (VUs)** dan tahapan penambahan beban bertahap (**Stages / Ramping VUs**).
- Mengonfigurasi **Thresholds (Performance Quality Gates)** di k6 (misal: `http_req_duration: ['p(95)<300']`, `http_req_failed: ['rate<0.01']`) untuk memblokir deployment otomatis di CI/CD jika SLA performa terlanggar.
- Menulis skrip skenario beban spesifik: **Stress Testing** (mencari batas hancur), **Spike Testing** (lonjakan traffic instan), dan **Soak Testing** (uji ketahanan memori 24 jam).
- Menerapkan custom metrics k6: **Counters**, **Gauges**, **Rates**, dan **Trends** untuk melacak KPI bisnis khusus.
- Melakukan Root Cause Analysis (RCA) pada kemacetan arsitektur: *Database Connection Pool Exhaustion*, *CPU Throttling*, dan *Memory Leaks*.

---

## 2. Prerequisite
- Memahami konsep dasar throughput, latensi persentil ($p90, p95, p99$), dan Hukum Little dari Module 01.
- Pengetahuan dasar tentang sintaks JavaScript modern dan protokol HTTP.

---

## 3. Concept
Selama bertahun-tahun, dunia pengujian beban didominasi oleh Apache JMeter yang membutuhkan konfigurasi XML raksasa dan memakan memori CPU sangat tinggi (setiap thread pengguna membutuhkan memori JVM 1–2 MB). Untuk mensimulasikan 10.000 Virtual Users, Anda membutuhkan cluster server load generator yang sangat mahal.

**Grafana k6** merevolusi industri dengan menghadirkan filosofi **Load Testing as Code**. Ditulis dalam bahasa Go dengan runtime JavaScript modern, satu instance mesin k6 ringan mampu menghasilkan beban puluhan ribu Virtual Users (VUs) secara simultan menggunakan konsumsi memori per-VU yang sangat kecil (~kilobytes). Skrip uji k6 disimpan di Git repository bersama kode aplikasi dan dapat dieksekusi secara otomatis di setiap pipeline CI/CD layaknya unit test biasa.

---

## 4. Why?
Mengapa Grafana k6 menjadi standar industri pengujian beban modern?
1. **Developer & QA Friendly (JavaScript Code, No XML GUI)**: Skrip pengujian ditulis murni dalam JavaScript modern, memungkinkan version control penuh di Git, modularisasi modul, dan integrasi linting.
2. **Built-in Quality Gates (Thresholds)**: k6 dapat langsung menghentikan pipeline CI/CD jika 95% request melebihi ambang batas toleransi (misal $p95 > 200$ ms), mencegah rilis kode yang lambat ke produksi.
3. **Efisiensi Sumber Daya Luar Biasa**: Mesin berbasis Go Goroutines mengeliminasi overhead thread OS yang berat, memungkinkan eksekusi jutaan request dari satu mesin server murah.

---

## 5. What?

### A. Komponen Utama Anatomi Skrip k6

```text
========================================================================================
                          GRAFANA k6 SCRIPT ANATOMY
========================================================================================

 1. INIT CONTEXT (Dijalankan 1x saat inisialisasi script)
    - Import library (http, check, sleep)
    - Definisi custom metrics

 2. CONFIGURATION OPTIONS (export const options = { ... })
    - Jumlah Virtual Users (vus)
    - Durasi atau Tahapan Beban (stages)
    - Syarat Ambang Batas Kelulusan (thresholds)

 3. DEFAULT VU FUNCTION (export default function () { ... })
    - Dieksekusi berulang-ulang oleh setiap Virtual User secara paralel!
    - Mengirim HTTP requests (http.get / http.post)
    - Memeriksa respon (check)
    - Mensimulasikan jeda waktu manusia (sleep / think time)
```

---

### B. 4 Tipe Custom Metrics di k6
Selain metrik bawaan (`http_req_duration`, `http_req_failed`), k6 menyediakan 4 metrik kustom:
1. **Counter**: Nilai kumulatif yang terus bertambah (misal: menghitung total transaksi checkout berhasil).
2. **Gauge**: Menyimpan nilai instan terakhir (misal: penggunaan memory worker saat ini).
3. **Rate**: Menghitung rasio persentase keberhasilan nilai boolean (misal: rasio kupon diskon yang berhasil diterapkan).
4. **Trend**: Menghitung statistik distribusi (min, max, mean, persentil p90/p95/p99) untuk waktu tunggu proses bisnis internal.

---

## 6. How? Konfigurasi Skenario Uji Beban di k6

### 1. Skenario Spike Test (Lonjakan Flash Sale Tiba-Tiba):
```javascript
export const options = {
  stages: [
    { duration: "10s", target: 100 },   // Warm-up beban normal
    { duration: "10s", target: 2000 },  // LONJAKAN INSTAN (SPIKE): Dari 100 ke 2.000 VU dalam 10 detik!
    { duration: "1m",  target: 2000 },  // Tahan beban ekstrem selama 1 menit
    { duration: "10s", target: 100 },   // Penurunan kembali ke normal
    { duration: "10s", target: 0 }      // Cooldown selesai
  ],
  thresholds: {
    // 95% request harus selesai di bawah 500ms bahkan saat terjadi spike
    "http_req_duration": ["p(95)<500"],
    // Error rate tidak boleh melebihi 1%
    "http_req_failed": ["rate<0.01"]
  }
};
```

---

### 2. Skenario Soak Test (Uji Kebocoran Memori Jangka Panjang):
```javascript
export const options = {
  stages: [
    { duration: "5m",  target: 300 },   // Naik bertahap ke 300 VU
    { duration: "12h", target: 300 },  // Tahan beban 300 VU stabil selama 12 JAM NONSTOP!
    { duration: "5m",  target: 0 }      // Selesai
  ],
  thresholds: {
    // Memastikan latensi tidak terdegradasi seiring berjalannya waktu (Memory Leak Indicator)
    "http_req_duration": ["p(99)<400"]
  }
};
```

---

## 7. Analogy
Bayangkan menguji ketahanan jembatan layang baru:
- **Load Test**: Membiarkan 200 mobil melintas teratur di atas jembatan pada kecepatan normal 60 km/jam untuk memverifikasi kelancaran lalu lintas.
- **Stress Test**: Memasukkan 500 truk gandeng bermuatan batu bara ke atas jembatan secara bertahap hingga tiang penyangga jembatan mulai retak (Mengetahui batas beban hancur absolut).
- **Spike Test**: Tiba-tiba ada 1.000 gajah yang dilepaskan berlari serentak menyeberangi jembatan dalam waktu 5 detik (Menguji goncangan instan).
- **Soak Test**: Membiarkan 100 truk kontainer terparkir di atas jembatan selama 3 hari berturut-turut tanpa henti (Memeriksa apakah ada penurunan fondasi tanah atau kelelahan logam struktural jangka panjang).

---

## 8. Diagram

```text
========================================================================================
                          k6 EXECUTION & METRIC PIPELINE
========================================================================================

                 [ k6 CLI / CI/CD Pipeline ]
                             |
                             v
               [ 1.000 Concurrent Goroutine VUs ]
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
     [ VU #001 ]         [ VU #002 ]         [ VU #1000 ]
         |                   |                   |
         +-------------------+-------------------+
                             |
                             | HTTP Request Floods (POST /api/checkout)
                             v
               [ Target System Under Test (SUT) ]
                             |
                             | Response Headers, Status, & Latency Timestamps
                             v
             [ k6 Real-Time Metrics Aggregator ]
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
 [ Grafana / InfluxDB Dashboard ]      [ Threshold Quality Gate Evaluator ]
  (Live TPS, CPU, Memory graphs)                 |
                                        +--------+--------+
                                        |                 |
                                  (Semua SLA Lolos) (SLA Terlanggar)
                                        |                 |
                                        v                 v
                                 [ PASS (Exit 0) ] [ FAIL (Exit 1) ]
                                                    (Block Deployment!)
```

---

## 9. Simple Example: Skrip Pengujian Beban k6 Lengkap dengan Checks

```javascript
import http from "k6/http";
import { check, sleep } from "k6";

// 1. Konfigurasi Quality Gate
export const options = {
  vus: 50,              // 50 Pengguna Simultan
  duration: "30s",      // Uji coba berjalan selama 30 detik
  thresholds: {
    http_req_duration: ["p(95)<200"], // 95% request wajib < 200ms
    http_req_failed: ["rate<0.01"]    // Error wajib < 1%
  }
};

// 2. Alur Pengujian Pengguna
export default function () {
  const url = "https://api.staging.internal/v1/catalog";
  const params = {
    headers: { "Content-Type": "application/json", "Authorization": "Bearer tok_demo" }
  };

  const res = http.get(url, params);

  // Assertion fungsional di dalam uji beban
  check(res, {
    "status is 200 OK": (r) => r.status === 200,
    "response body has products": (r) => r.body.includes("catalogItems")
  });

  // Think time pengguna (mensimulasikan jeda baca manusia 1 detik)
  sleep(1);
}
```

---

## 10. Practical Example: Mendiagnosa Kemacetan Kueri Database (SQL Lock Bottleneck)

Saat uji beban mencapai 500 VU, k6 mencatat lonjakan latensi dramatis dari 50 ms menjadi 3.200 ms:

```text
Langkah Investigasi Sistematis:
1. Periksa Utilisasi CPU Server Backend: CPU hanya 28% (Bukan CPU bottleneck).
2. Periksa Utilisasi Memori: Stabil di 40% (Bukan Out-of-Memory).
3. Periksa Database Server:
   - Metrik PostgreSQL Connection Pool: Active Connections = 100/100 (POOL FULL!).
   - Menjalankan perintah diagnostik:
     SELECT pid, query, wait_event_type, wait_event FROM pg_stat_activity WHERE wait_event IS NOT NULL;
   - Hasil Analisis: 85 koneksi berstatus Lock: transactionid karena kueri:
     UPDATE products SET stock = stock - 1 WHERE id = 'HOT_DEAL_1';
4. Kesimpulan: Terjadi Row-Level Locking Contention pada produk yang sama.
5. Rekomendasi QA & Arsitek: Terapkan in-memory queue (Redis / RabbitMQ) untuk pemotongan stok, jangan mengunci baris database secara sinkron!
```

---

## 11. Real World Example: Tiket Konser Coldplay Jakarta 2023
Saat pembukaan presale tiket konser internasional di Jakarta:
- Lebih dari 1,5 juta pengguna mengantre secara bersamaan di antrean virtual.
- Sistem menggunakan antrean statis yang gagal menahan lonjakan spike traffic di detik pertama.
- Karena platform tidak mengimplementasikan *Adaptive Throttling* dan *CDN Edge Caching*, server API kewalahan memproses request status antrean yang dikirim berulang kali oleh browser pengguna setiap detik (*DDoS dari pengguna sah*).
- Jutaan penggemar mendapatkan error gateway timeout dan tiket habis dalam sekejap tanpa transparansi antrean.

---

## 12. Trade-offs

| Aspek Uji Beban | Grafana k6 | Apache JMeter | Locust (Python) |
|---|---|---|---|
| **Bahasa Scripting** | JavaScript ES6 modern. | GUI berbasis XML (Kompleks). | Python murni. |
| **Konsumsi Memori per VU** | Sangat Rendah (~Puluhan KB per VU). | Sangat Tinggi (1–2 MB per Thread JVM). | Sedang. |
| **Integrasi CI/CD** | Luar biasa (CLI native, exit code 0/1). | Sulit (Perlu plugin Ant/Maven tambahan). | Baik. |
| **Dukungan Protokol** | HTTP/1.1, HTTP/2, WebSocket, gRPC. | Sangat Luas (JMS, JDBC, FTP, SMTP, TCP). | HTTP, kustom via Python. |

---

## 13. When To Use
- Gunakan **Grafana k6** untuk pengujian beban API, microservices, dan situs web modern di pipeline CI/CD otomatis.
- Terapkan **Thresholds** ketat pada setiap branch rilis fitur baru agar regresi performa terdeteksi sedini mungkin (*Shift-Left Performance*).
- Gunakan **Spike Testing** sebelum event promosi flash sale atau pembukaan pendaftaran nasional.

## 14. When NOT To Use
- Jangan menggunakan k6 untuk merender CSS/DOM browser secara penuh untuk ribuan pengguna simultan (k6 dirancang untuk lapisan protokol HTTP jaringan, bukan browser UI rendering). Jika membutuhkan rendering UI, batasi maksimal 5–10 VU menggunakan *k6 browser module*.
- Jangan menjalankan pengujian beban tanpa menyetel *Think Time (`sleep(1)`)* yang realistis; pengguna manusia nyata tidak mengklik tombol 100 kali per detik tanpa jeda.

---

## 15. Common Mistakes

```text
1. MISTAKE: Tidak menyetel batas ambang (Thresholds) di skrip k6.
   WHY IT HAPPENS: QA hanya menjalankan tes dan melihat grafik visual di terminal.
   WHY IT IS BAD: Pipeline CI/CD akan selalu menganggap build SUKSES (Exit 0) meskipun latensi mencapai 10 detik!
   CORRECT APPROACH: Wajib definisikan "thresholds: { http_req_duration: ['p(95)<300'] }" agar pipeline otomatis gagal (Exit 1).

2. MISTAKE: Seluruh Virtual Users menggunakan 1 akun ID yang sama persis (Shared User Contention).
   WHY IT HAPPENS: Menggunakan 1 token autentikasi statis untuk 5.000 VUs.
   WHY IT IS BAD: Menimbulkan row-locking palsu di database pada 1 baris user tersebut, bukan performa sistem riil.
   CORRECT APPROACH: Gunakan dataset pool pengguna unik (misal 5.000 akun berbeda dari file CSV/JSON).
```

---

## 16. Best Practices

### Must Have
- Quality Gates wajib melalui blok `thresholds` (p95 latency, fail rate $< 1\%$).
- Menyertakan jeda waktu acak manusiawi (*Randomized Think Time*, misal `sleep(Math.random() * 2 + 1)`).

### Recommended
- Mengintegrasikan hasil k6 dengan dashboard Grafana dan Prometheus untuk observabilitas grafis real-time saat uji beban berlangsung.
- Menyimpan skrip pengujian k6 di repository yang sama dengan source code backend (*In-repo Performance Testing*).

### Advanced
- Menggunakan *k6 Distributed Execution* (k6 Operator di Kubernetes) untuk menghasilkan beban di atas 100.000 VUs dari berbagai zona wilayah geografis (Multi-Region Load Testing).

### Avoid / Overengineering
- Menulis logika parser data 500 baris di dalam blok default VU function; pemrosesan komputasi berat di sisi VU akan memakan CPU mesin load generator dan menurunkan akurasi hasil uji.

---

## 17. Troubleshooting: Mesin Load Generator Mengalami "Too Many Open Files"
Jika k6 melempar error:
`dial tcp: socket: too many open files`
1. **Penyebab**: Batas ambang batas file descriptor sistem operasi Linux/Mac telah tercapai karena membuka ribuan koneksi soket TCP bersamaan.
2. **Solusi Cepat**:
   - Naikkan batas *ulimit* file descriptor di terminal sebelum menjalankan k6:
     ```bash
     ulimit -n 65535
     ```
   - Gunakan koneksi pooling HTTP keep-alive.

---

## 18. Exercise
1. Tuliskan blok konfigurasi `options` k6 yang mendefinisikan skenario uji beban:
   - 3 tahapan (*Stages*):
     - Menit 1: Naik dari 0 ke 100 VU.
     - Menit 2–4: Tahan stabil di 100 VU.
     - Menit 5: Turun kembali ke 0 VU.
   - Thresholds: 99% request wajib selesai di bawah 300 ms dan error rate kurang dari 0,5%.
2. Jelaskan perbedaan mendasar antara skenario uji **Stress Testing** dan **Soak Testing** dalam hal tujuan dan durasi eksekusinya.

---

## 19. Challenge
Rancang sebuah **Load Testing Automation Suite Lengkap dengan k6** untuk endpoint transaksi e-commerce: `POST /api/v1/orders`.
- Konfigurasikan skenario Spike Test yang mensimulasikan pembukaan flash sale dari 50 VU melonjak ke 1.000 VU dalam waktu 15 detik.
- Terapkan verifikasi status HTTP 201 Created menggunakan fungsi `check()`.
- Tambahkan custom counter metric `successful_orders` dan custom trend metric `payment_gateway_duration`.
- Tetapkan quality gates ketat: jika p95 melebihi 400 ms atau rate kegagalan melebihi 2%, skrip k6 wajib mengembalikan exit code 1 untuk membatalkan rilis di CI/CD.

---

## 20. Summary
- Grafana k6 menyediakan arsitektur pengujian beban modern berbasis kode JavaScript dengan efisiensi memori tingkat tinggi berkat engine bahasa Go.
- Thresholds bertindak sebagai Quality Gates yang memvalidasi SLA performa (p95 latency, error rate) secara otomatis di pipeline CI/CD.
- Skenario Stress, Spike, dan Soak menguji ketahanan aplikasi terhadap kondisi ekstrem dan kebocoran memori jangka panjang.
- Root Cause Analysis performa menghubungkan metrik klien (latency, error rate) dengan metrik server (CPU, Memory, DB Connection Pool Saturation).

---

## Hands-on Practice: Simulator Generator Beban k6 & Evaluator Quality Gates (Thresholds)
Jalankan script simulator yang mereplikasi mesin load generator k6, mensimulasikan ratusan Virtual Users (VUs) dengan tahapan ramping, menghitung metrik persentil real-time, dan mengevaluasi status Pass/Fail Thresholds:

```bash
node QA/BAB-08-Pengujian-Performa-dan-Beban-Sistem/hands-on/m02/k6_load_generator_threshold_sim.js
```

---
[⬅️ Module 01: Performance Fundamentals & Percentiles](./Module-01-Fondasi-Performance-Testing-Throughput-Latency-Percentiles.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 08 ➡️](./BAB-08-Quiz-dan-Challenge.md)
---
