# BAB 04: Quiz dan Challenge - Service Level Engineering

## 1. Basic Questions (5 Soal)

### Q1. Apa perbedaan paling mendasar antara SLO dan SLA?
- **Jawaban & Penjelasan:** 
  **SLO (Service Level Objective)** adalah target keandalan internal yang disepakati oleh tim engineering dan produk untuk memandu operasional dan alokasi sumber daya.
  **SLA (Service Level Agreement)** adalah komitmen eksternal kontraktual/legal dengan pelanggan atau klien bisnis yang memuat klausul konsekuensi hukum atau finansial eksplisit (misal: *service credit refund*) jika target gagal dipenuhi. SLO hampir selalu dibuat lebih ketat daripada SLA untuk memberikan *safety buffer*.

### Q2. Mengapa menargetkan ketersediaan sistem sebesar 100% dipandang sebagai anti-pola dalam SRE?
- **Jawaban & Penjelasan:** 
  Biaya untuk mencapai 100% ketersediaan meningkat secara eksponensial (memerlukan redundansi ekstrem di semua lapisan sistem), sementara jalur koneksi pengguna akhir (ISP, jaringan seluler, browser) memiliki reliabilitas rata-rata di bawah 99.5%. Ketersediaan 100% pada backend tidak akan dirasakan oleh pengguna akhir, namun menghentikan kecepatan deployment fitur baru (*velocity freeze*).

### Q3. Apa definisi matematis dari Burn Rate = 1?
- **Jawaban & Penjelasan:** 
  Burn Rate bernilai 1 ($B = 1$) berarti sistem mengonsumsi kuota Error Budget dengan kecepatan konsisten sedemikian rupa sehingga tepat $100\%$ Error Budget akan habis pada akhir periode rolling window yang telah ditentukan (misal: habis seluruhnya pas dalam 30 hari).

### Q4. Di layer manakah instrumentasi metrik SLI idealnya diambil untuk request-driven architecture?
- **Jawaban & Penjelasan:** 
  Idealnya diukur sedekat mungkin dengan pengguna akhir, yaitu pada layer **Edge Load Balancer, Ingress Controller, atau API Gateway**. Pengukuran langsung di level internal controller microservice berisiko *under-counting*, karena request yang terblokir atau drop akibat network error, routing failure, atau crash pada reverse proxy tidak akan tercatat.

### Q5. Jika target SLO adalah 99% dalam rolling window 30 hari, berapa durasi downtime kumulatif maksimum yang diizinkan (dalam satuan jam/menit)?
- **Jawaban & Penjelasan:** 
  - Durasi 30 hari = $30 \times 24\text{ jam} = 720\text{ jam}$ ($43.200\text{ menit}$).
  - Error Budget = $100\% - 99\% = 1\% = 0.01$.
  - Total durasi kegagalan yang diizinkan = $720\text{ jam} \times 0.01 = 7.2\text{ jam}$ atau $432\text{ menit}$.

---

## 2. Intermediate Questions (5 Soal)

### Q1. Mengapa alerting berbasis ambang batas tunggal (misal: "Error Rate > 1% for 5m") menghasilkan alarm palsu (false positive) dan penanganan terlambat (false negative)?
- **Jawaban & Penjelasan:** 
  - *False Positive:* Lonjakan sesaat selama 6 menit yang hanya menghabiskan $0.05\%$ error budget akan memicu pager on-call bangun di tengah malam, padahal layanan sudah sembuh sendiri dan tidak mengancam SLO bulanan.
  - *False Negative:* Kegagalan sistemik dengan error rate $0.8\%$ (di bawah ambang $1\%$) tidak akan pernah menyalakan alert, namun jika berlangsung terus menerus selama 4 hari, error rate tersebut akan menghabiskan seluruh error budget bulanan tanpa adanya notifikasi.

### Q2. Dalam Multi-Window Multi-Burn-Rate alerting, mengapa kita harus menyertakan Short Window bersamaan dengan Long Window menggunakan operator logika AND?
- **Jawaban & Penjelasan:** 
  Long Window (misal 1 jam) memastikan bahwa sistem telah membakar porsi error budget yang cukup signifikan sebelum alert dipicu. Short Window (misal 5 menit) memverifikasi apakah degradasi sistem **masih berlangsung saat ini**. Tanpa Short Window, jika sistem mengalami spike selama 10 menit lalu pulih total, alert pada Long Window akan tetap aktif berdering selama 50 menit berikutnya meskipun masalah sudah selesai (*alert flappiness*).

### Q3. Bagaimana cara memperlakukan HTTP response code 429 (Too Many Requests) dalam kalkulasi SLI Availability?
- **Jawaban & Penjelasan:** 
  Secara standar, response code 4xx dianggap sebagai *client-side error* dan dihitung sebagai *good event* (atau dikeluarkan dari total *valid events*). Namun, HTTP 429 adalah kasus khusus. Jika HTTP 429 melonjak drastis akibat kesalahan konfigurasi rate limiting pada backend atau kegagalan sinkronisasi token bucket cluster, request tersebut harus dihitung sebagai *bad event* (kegagalan sistem). Best practice menyarankan membuat SLI terpisah khusus untuk Rate Limiting / Quota Throttling.

### Q4. Apa yang dimaksud dengan Rolling Window vs. Calendar-aligned Window dalam pelaporan SLO?
- **Jawaban & Penjelasan:** 
  - *Calendar-aligned Window:* Dihitung berdasarkan batas kalender (misal: 1 Januari hingga 31 Januari). Kelemahannya adalah terjadinya fenomena "reset artifisial": tim engineering dapat membakar seluruh budget di akhir bulan tanpa konsekuensi karena budget kembali 100% pada tanggal 1.
  - *Rolling Window:* Dihitung terus-menerus mundur untuk $N$ hari terakhir (misal: 30 hari ke belakang dari detik ini). Pendekatan ini mencerminkan pengalaman berkelanjutan pengguna tanpa manipulasi tanggal kalender.

### Q5. Sebutkan 3 tindakan konkret yang dapat didefinisikan dalam sebuah Error Budget Policy ketika budget berada pada level < 10%!
- **Jawaban & Penjelasan:** 
  1. *Deployment Gating / Feature Freeze:* Menghentikan peluncuran rilis fitur non-kritis; hanya patch keamanan dan perbaikan reliabilitas darurat yang diizinkan masuk ke pipeline CI/CD.
  2. *Architectural Failover / Load Shedding:* Menurunkan beban non-esensial secara otomatis (misal menonaktifkan fitur rekomendasi AI berbasis real-time dan beralih ke cache statis).
  3. *Sprint Reprioritization:* Pada sprint planning berikutnya, minimal $50\%$ hingga $100\%$ kapasitas engineering tim produk dialokasikan khusus untuk mengatasi technical debt dan perbaikan arsitektur keandalan.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Industri)

### Kasus 1: Fenomena "Traffic Dip" Tengah Malam Membakar Budget Palsu
- **Skenario:** Tim On-Call Payment Gateway terus dibangunkan oleh PagerDuty pada pukul 03:00 - 04:00 dini hari karena alert Multi-Burn-Rate (BR 14.4) menyala. Saat diperiksa, sistem ternyata normal. Traffic di jam tersebut hanya 5 request per detik (dibandingkan 5.000 req/s di siang hari). Terjadi 3 kali timeout akibat network retry pengguna yang sinyalnya buruk, menghasilkan error rate $20\%$ pada window 5 menit.
- **Pertanyaan:** Analisis kegagalan arsitektur monitoring ini dan rancang solusi PromQL definitif untuk menghilangkan alarm palsu tersebut tanpa mengabaikan insiden nyata!
- **Solusi Rekayasa:**
  - *Akar Masalah:* Formula pembagian persentase SLI mengalami distorsi matematis saat penyebut (*traffic volume*) sangat kecil.
  - *Solusi:* Terapkan filtering ambang batas volume traffic minimum (*traffic floor guard*) pada rule alert:
    ```promql
    (
      (job:payment_errors:rate1h / job:payment_requests:rate1h) / 0.001 > 14.4
      and
      (job:payment_errors:rate5m / job:payment_requests:rate5m) / 0.001 > 14.4
    )
    and
    # Traffic guard: hanya aktif jika traffic rate > 50 req/s
    (job:payment_requests:rate5m > 50)
    ```
    Untuk memantau layanan saat traffic rendah, gantikan peran passive metrics dengan **Synthetic Probing (Canary synthetic transactions)** yang mengirimkan traffic konstan setiap 10 detik.

---

### Kasus 2: Perdebatan Metrik Latency: Rata-Rata (Mean) vs Persentil (p95/p99) vs SLO Berbasis Rasio Good Events
- **Skenario:** Tim backend melaporkan bahwa service search mereka sangat sehat karena "Latency rata-rata search API adalah 120ms (Target < 200ms)". Namun, tim customer service menerima ribuan komplain dari pengguna VIP yang menyatakan halaman search sering membeku (*freezing*) lebih dari 3 detik.
- **Pertanyaan:** Tunjukkan kelemahan matematis penggunaan *Average / Mean Latency*, dan jelaskan bagaimana menyusun SLI Latency yang tepat menggunakan pendekatan rasio Google SRE!
- **Solusi Rekayasa:**
  - *Kelemahan:* Nilai mean/rata-rata menyembunyikan ekor distribusi (*long-tail distribution*). Jika 90 pengguna mendapat response 20ms dan 10 pengguna mendapat response 2.000ms, rata-rata latency adalah 218ms, tampak wajar padahal $10\%$ pengguna mengalami pengalaman buruk.
  - *Solusi SRE:* Gunakan formulasi berbasis event rasio histogram:
    $$\text{SLI}_{\text{latency}} = \frac{\text{Jumlah request dengan durasi } \le 300\text{ms}}{\text{Total seluruh request valid}} \ge 99\%$$
  - Di Prometheus:
    ```promql
    sum(rate(http_request_duration_seconds_bucket{le="0.3"}[30d]))
    /
    sum(rate(http_request_duration_seconds_count[30d]))
    >= 0.99
    ```

---

### Kasus 3: Implementasi Konsekuensi Error Budget Policy pada Pipeline CI/CD
- **Skenario:** Anda adalah Lead SRE di platform e-commerce finansial. Tim manajemen menuntut agar rilis fitur baru diblokir secara otomatis di pipeline GitHub Actions jika Error Budget 30 hari telah terpakai lebih dari $95\%$.
- **Pertanyaan:** Rancang arsitektur integrasi sistem antara Prometheus, Thanos/Cortex, API Engine, dan GitHub Actions CI/CD pipeline untuk memberlakukan *Automated Policy Gate* ini!
- **Solusi Rekayasa:**
  1. *Telemetry Engine:* Prometheus menghitung error budget tersisa melalui recording rule:
     ```promql
     1 - (
       sum(increase(http_requests_total{status=~"5.."}[30d]))
       /
       (sum(increase(http_requests_total[30d])) * 0.001)
     )
     ```
  2. *Policy Evaluation Service:* Buat lightweight internal REST endpoint (`GET /api/v1/slo/budget-status?service=order`). Endpoint ini mengeksekusi query Prometheus di atas. Jika nilai $< 0.05$ (budget tersisa $< 5\%$), service mengembalikan status `HTTP 403 Forbidden` dengan payload JSON `{"deploy_allowed": false, "reason": "Error Budget Exceeded (Remaining: 3.2%)"}`.
  3. *CI/CD Integration:* Pada workflow `.github/workflows/deploy.yml`, sisipkan pre-deployment validation step:
     ```yaml
     - name: Validate Error Budget Gate
       run: |
         STATUS=$(curl -s https://slo-gate.internal/api/v1/slo/budget-status?service=order)
         ALLOWED=$(echo $STATUS | jq -r .deploy_allowed)
         if [ "$ALLOWED" != "true" ]; then
           echo "Deployment Blocked by SRE Policy: $(echo $STATUS | jq -r .reason)"
           exit 1
         fi
     ```

---

## 4. Practical Chapter Challenge: Arsitektur SLO Multi-Burn-Rate Terintegrasi

### Konteks Tantangan:
Anda ditunjuk sebagai Principal SRE untuk platform streaming video berkapasitas tinggi. Platform ini memiliki microservice kritis bernama `playback-auth-service`.
- **Target SLO Availability:** $99.95\%$ ketersediaan request dalam rolling window 30 hari.
- **Target SLO Latency:** $98\%$ request otentikasi harus selesai dalam waktu kurang dari $150\text{ms}$ dalam rolling window 30 hari.
- **Traffic Rata-rata:** $20.000$ request per detik.

### Tugas yang Harus Diselesaikan:
1. **Perhitungan Matematis Formal:**
   - Hitung Allowed Error Rate untuk Availability dan Latency.
   - Hitung nilai konsumsi error budget jika terjadi insiden di mana burn rate bernilai $14.4$ berlangsung selama 45 menit.
2. **Implementasi Konfigurasi Prometheus Alerting:**
   - Buat satu berkas konfigurasi lengkap YAML yang mendefinisikan Recording Rules dan Alerting Rules menggunakan skema standar Multi-Window Multi-Burn-Rate (Window 1h/5m dengan BR 14.4 untuk Page, dan Window 6h/30m dengan BR 6 untuk Ticket).
3. **Dokumen Error Budget Policy:**
   - Susun ringkasan matriks kebijakan eskalasi Error Budget yang mengikat antara Divisi Product dan Divisi Engineering saat budget berada di tingkat: $50\%$, $25\%$, dan $0\%$.

---