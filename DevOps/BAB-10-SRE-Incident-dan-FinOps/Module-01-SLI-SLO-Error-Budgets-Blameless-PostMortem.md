# Module 01: SRE Fundamental: SLI, SLO, Error Budgets, & Blameless Post-Mortem

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami filosofi **Site Reliability Engineering (SRE)**: *Class SRE implements interface DevOps*.
- Mendefinisikan dan membedakan trio metrik keandalan: **SLI** (*Service Level Indicator*), **SLO** (*Service Level Objective*), dan **SLA** (*Service Level Agreement*).
- Menghitung **Error Budget** matematis dan menggunakannya sebagai penyeimbang antara kecepatan rilis fitur (*innovation*) vs stabilitas sistem (*reliability*).
- Mengonfigurasi **Multi-Window Multi-Burn-Rate Alerting** untuk menghindari alarm palsu saat error budget terbakar cepat vs lambat.
- Memimpin alur manajemen insiden (*Incident Commander*, *Communications Lead*) dan menulis dokumen **Blameless Post-Mortem** yang konstruktif.

---

## 2. Prerequisite
- Memahami konsep dasar metrik Prometheus, PromQL, dan Alertmanager (BAB 08 Module 01).
- Memahami arsitektur microservices dan HTTP status code (BAB 02).
- Pemahaman statistik dasar tentang persentase probabilitas dan uptime (*nine nines*).

---

## 3. Concept
Site Reliability Engineering (SRE) diciptakan oleh Google untuk memperlakukan operasi sistem sebagai masalah software engineering. Alih-alih mengejar keandalan 100% yang mustahil dan sangat mahal secara ekonomi, SRE mendefinisikan target keandalan yang realistis yang dapat diterima oleh pengguna (**SLO**).

Selisih antara 100% dan SLO disebut **Error Budget**:
$$\text{Error Budget} = 100\% - \text{SLO}$$

Jika sebuah layanan memiliki SLO ketersediaan $99.9\%$, maka sistem memiliki Error Budget sebesar $0.1\%$. Selama error budget masih tersisa, tim pengembang bebas merilis fitur baru dengan cepat. Namun, jika error budget habis terbakar dalam bulan berjalan, rilis fitur baru **wajib dibekukan (*feature freeze*)** dan seluruh kapasitas tim dialihkan untuk memperbaiki stabilitas, testing, dan ketahanan infrastruktur.

```
                  ┌───────────────────────────────────────────────────────────┐
                  │                 THE SRE BALANCING ACT                     │
                  └───────────────────────────────────────────────────────────┘

           Kecepatan Fitur (Product Team) <─── [ ERROR BUDGET ] ───> Stabilitas Sistem (SRE Team)
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
         Budget Tersisa (> 20%):                                     Budget Habis (<= 0%):
      - Bebas deploy fitur baru                                   - Feature Freeze diaktifkan!
      - Eksperimen & canary rilis                                 - 100% fokus perbaikan bugs,
      - Menerima risiko inovasi                                     arsitektur, & monitoring
```

---

## 4. Why?
1. **Mengakhiri Konflik Abadi Dev vs Ops**: Developer dinilai berdasarkan seberapa cepat mereka merilis fitur baru (*move fast*), sedangkan Sysadmin/Ops dinilai berdasarkan seberapa stabil server (*don't break things*). Error Budget menjadi kontrak objektif kuantitatif yang disepakati bersama oleh manajemen bisnis, produk, dan engineering.
2. **Menghindari Uptime 100% yang Tidak Realistis**: Pengguna ponsel yang tersambung ke jaringan 4G/WiFi yang sering fluktuatif tidak akan bisa membedakan antara server dengan reliabilitas 99.99% dan 100%. Mengejar angka 100% membutuhkan biaya infrastruktur 10x lipat tanpa memberikan nilai tambah nyata (*diminishing returns*).
3. **Budaya Tanpa Menyalahkan (*Blameless Culture*)**: Manusia pasti berbuat salah. Jika insiden diselesaikan dengan memecat developer yang salah ketik, insinyur lain akan takut berinovasi dan menyembunyikan masalah. Blameless post-mortem mengasumsikan setiap orang berniat baik; yang gagal adalah sistem, proses, dan proteksi otomatisnya.

---

## 5. What?
Definisi Trio Keandalan:
- **SLI (Service Level Indicator)**: Ukuran kuantitatif real-time dari performa layanan yang dialami pengguna.
  $$\text{SLI} = \frac{\text{Jumlah Request Baik (Good Events)}}{\text{Total Request (Total Events)}} \times 100\%$$
- **SLO (Service Level Objective)**: Target keandalan internal yang ditetapkan oleh tim bisnis dan teknis (contoh: $99.9\%$ request pembayaran harus sukses dengan latensi $< 500\text{ms}$ selama periode bergulir 30 hari).
- **SLA (Service Level Agreement)**: Perjanjian hukum eksternal dengan pelanggan yang mencantumkan konsekuensi finansial (pengembalian uang / *service credit*) jika keandalan turun di bawah target (contoh: jika uptime $< 99.5\%$, pelanggan mendapat diskon 10%). SLA biasanya disetel lebih rendah daripada SLO internal.
- **Burn Rate**: Kecepatan konsumsi error budget. Burn rate bernilai 1 berarti error budget akan habis tepat dalam periode SLO (misal 30 hari). Burn rate bernilai 14 berarti seluruh budget 30 hari akan habis dalam waktu 2 hari jika tidak segera ditangani.

---

## 6. How?
Alur Kerja Praktik SRE:
1. **Pilih SLI yang Berpusat pada Pengguna**: Alih-alih mengukur utilisasi CPU server, ukur pengalaman pengguna:
   - *Availability SLI*: Persentase HTTP response dengan status bukan 5xx.
   - *Latency SLI*: Persentase response HTTP yang dikembalikan dalam waktu $< 250\text{ms}$.
2. **Definisikan SLO di PromQL**:
   ```promql
   sum(rate(http_requests_total{status!~"5.."}[30d])) 
   / 
   sum(rate(http_requests_total[30d])) >= 0.999
   ```
3. **Pasang Multi-Burn-Rate Alerting**: Gunakan dua jendela waktu (*Short Window* 5 menit & *Long Window* 1 jam) untuk mendeteksi pembakaran budget secara presisi tanpa menghasilkan alarm palsu.
4. **Respon Insiden Terstruktur**:
   - Tunjuk **Incident Commander (IC)** yang memimpin strategi tanpa diganggu urusan teknis mikro.
   - Tunjuk **Communications Lead** yang bertugas mengupdate status page ke manajemen dan pelanggan.
   - Selesaikan insiden secepatnya, jika perlu lakukan rollback instan sebelum mencari akar masalah.
5. **Jalankan Blameless Post-Mortem**: Maksimal 48 jam setelah insiden, kumpulkan seluruh pihak yang terlibat, tulis kronologi menit demi menit, identifikasi faktor pemicu (*contributing factors*), dan buat tiket perbaikan (*action items*) yang memiliki pemilik (*assignee*) dan batas waktu jelas.

---

## 7. Analogy
Bayangkan **SLO & Error Budget** seperti **Limit Poin Pelanggaran Surat Izin Mengemudi (SIM)**:
- Polisi lalu lintas memberikan Anda kuota 10 poin pelanggaran per tahun (**Error Budget**).
- Mengemudi di jalan tol dengan lancar adalah **Good Events** (**SLI**).
- Anda boleh sesekali melakukan kesalahan kecil (misal parkir telat 5 menit) tanpa kehilangan SIM Anda.
- Namun, jika Anda ngebut 180 km/jam dan menghabiskan 10 poin dalam waktu 1 minggu (**High Burn Rate**), SIM Anda langsung dicabut sementara (**Feature Freeze**), dan Anda wajib mengikuti kursus keselamatan berkendara sebelum diizinkan mengemudi kembali (**Post-Mortem Action Items**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               SRE INCIDENT LIFECYCLE & BLAMELESS POST-MORTEM                      |
+-----------------------------------------------------------------------------------+

 1. DETECTION (Prometheus Multi-Burn-Rate Alert fires)
         │
         ▼
 2. TRIAGE & ESCALATION (PagerDuty wakes On-Call Engineer)
         │
         ▼
 3. INCIDENT COMMAND (Declare Incident -> Assign Roles)
    ┌───────────────────────────┬───────────────────────────┐
    │ Incident Commander (Lead) │ Communications Lead       │
    │ (Orchestrates triage)     │ (Updates StatusPage)      │
    └───────────────────────────┴───────────────────────────┘
         │
         ▼
 4. MITIGATION (Prioritize User Relief over Root-Cause finding!)
    ↳ Rollback commit, scale pods, drain unhealthy zone, restart service.
         │
         ▼ (System Recovered -> Incident Closed)
 5. BLAMELESS POST-MORTEM (Within 48 hours)
    ┌────────────────────────────────────────────────────────┐
    │ Document:                                              │
    │ - Executive Summary                                    │
    │ - Impact (Nasabah terdampak, $ kerugian, SLO dropped)  │
    │ - Detailed Timeline (UTC)                              │
    │ - Contributing Factors (Bukan 'siapa yang salah!')    │
    │ - What went well vs What went poorly                   │
    │ - Action Items (P0/P1 JIRA tickets with owners)        │
    └────────────────────────────────────────────────────────┘
```

---

## 9. Simple Example: Perhitungan Error Budget
Tabel kalkulasi toleransi downtime berdasarkan nilai SLO dalam periode 30 hari:

| SLO Availability | Error Budget (%) | Toleransi Downtime per 30 Hari | Toleransi Downtime per Tahun |
|---|---|---|---|
| **99% (Two Nines)** | 1.0% | 7 jam 12 menit | 3.65 hari |
| **99.9% (Three Nines)** | 0.1% | 43 menit 12 detik | 8.76 jam |
| **99.95%** | 0.05% | 21 menit 36 detik | 4.38 jam |
| **99.99% (Four Nines)** | 0.01% | 4 menit 19 detik | 52.6 menit |
| **99.999% (Five Nines)** | 0.001% | 25.9 detik | 5.26 menit |

---

## 10. Practical Example: PromQL Multi-Burn-Rate Alert Rule
Alert rule Prometheus modern berbasis Google SRE Workbook untuk mendeteksi pembakaran 2% budget dalam 1 jam (Burn Rate = 14.4):

```yaml
groups:
  - name: slo_alerts
    rules:
      # Alert PagerDuty (Kritis): Budget terbakar 14.4x lebih cepat
      - alert: HighErrorBudgetBurnRate
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[1h]))
            /
            sum(rate(http_requests_total[1h]))
          ) > (1 - 0.999) * 14.4
          and
          (
            sum(rate(http_requests_total{status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total[5m]))
          ) > (1 - 0.999) * 14.4
        for: 2m
        labels:
          severity: critical
          slo: availability-payment
        annotations:
          summary: "Error Budget Payment API terbakar sangat cepat!"
          description: "Layanan membakar >2% error budget dalam 1 jam terakhir."
```

---

## 11. Real World Example: Format Blameless Post-Mortem Template
Contoh nyata ringkasan dokumen post-mortem saat insiden gateway pembayaran:

```markdown
# Incident Post-Mortem: Payment Gateway Timeout [INC-88192]

**Date**: 2026-09-11 | **Status**: Resolved | **Severity**: SEV-1
**Incident Commander**: Budi S. | **Scribe**: Siti A.

## Impact
- **Durasi Insiden**: 38 menit (10:14 - 10:52 WIB).
- **Dampak Bisnis**: 2.450 transaksi pembayaran checkout gagal diproses (~Rp 450 Juta tertunda).
- **Dampak SLO**: SLI ketersediaan turun ke 98.2% pada hari kejadian, mengonsumsi 62% error budget bulanan.

## Contributing Factors
- Pustaka HTTP client baru tidak memiliki default timeout, menyebabkan koneksi TCP menggantung tak terhingga saat upstream partner bank mengalami perlambatan.
- Thread pool worker kehabisan socket sehingga request baru tertahan di antrean OS.

## What Went Well
- Alert Multi-Burn-Rate Prometheus berhasil membunyikan pager dalam waktu 3 menit setelah lonjakan kegagalan.
- Tim mampu melakukan mitigasi cepat melalui rollback versi via ArgoCD dalam 4 menit setelah instruksi IC.

## Action Items
1. [P0] Tambahkan strict timeout 2500ms dan circuit breaker pada seluruh external HTTP client (Assignee: @budi - Target: 14 Sep).
2. [P1] Buat synthetic healthcheck probing ke partner bank setiap 30 detik (Assignee: @siti - Target: 18 Sep).
3. [P2] Perbarui runbook penanganan degradasi upstream payment di Wiki internal (Assignee: @agus - Target: 20 Sep).
```

---

## 12. Trade-offs

| Aspek | Tanpa SRE (Tradisional) | Menggunakan SRE & Error Budgets |
|---|---|---|
| **Target Reliabilitas** | 100% Uptime (Mustahil & Bikin Frustrasi) | Kuantitatif (Misal 99.9%, terukur & realistis) |
| **Keputusan Rilis Fitur** | Opini subjektif manajer / adu argumen | Objektif berbasis sisa saldo Error Budget |
| **Penyelidikan Insiden** | Mencari "siapa yang salah" (Finger-pointing) | Meneliti kelemahan sistem (Blameless Post-Mortem) |
| **Strategi Alerting** | Threshold statis (CPU > 80% yang bising) | Burn Rate Alerting berbasis dampak nyata pengguna |

---

## 13. When To Use
- Organisasi teknologi skala menengah hingga enterprise dengan tim produk dan engineering yang aktif merilis kode.
- Sistem layanan kritikal di mana downtime berdampak langsung pada reputasi merek dan pendapatan finansial.
- Tim yang mengalami kelelahan alarm (*alert fatigue*) akibat ribuan notifikasi monitoring yang tidak actionable.

---

## 14. When NOT To Use
- Perusahaan rintisan tahap awal (*Early Stage MVP*) yang sedang memvalidasi *product-market fit* (kecepatan belajar dan pivot jauh lebih krusial dibanding menghitung burn rate 30 hari).

---

## 15. Common Mistakes
1. **Menetapkan SLO 100%**: Tidak ada sistem di dunia yang memiliki uptime 100%. Bahkan AWS S3 dan Google Cloud hanya menjamin SLA 99.9% hingga 99.99%. Menetapkan SLO 100% berarti Error Budget Anda adalah 0, sehingga Anda tidak pernah boleh merilis kode baru atau melakukan maintenance.
2. **Post-Mortem yang Menyalahkan Individu**: Menulis dokumen post-mortem dengan kalimat: *"Developer A lalai dan tidak membaca instruksi"*. Ini adalah anti-pattern. Pertanyaan SRE yang benar adalah: *"Mengapa sistem kita mengizinkan satu kesalahan ketik manusia merusak seluruh database tanpa ada validasi otomatis?"*.
3. **Mengabaikan Action Items Pasca Insiden**: Menggelar rapat post-mortem yang hangat dan menulis dokumen yang indah, namun tiket action item di Jira tidak pernah dikerjakan dan ditimbun di backlog. Insiden serupa dijamin akan terulang dalam 3 bulan ke depan.

---

## 16. Best Practices
### Must Have
- Tentukan maksimal 1 hingga 3 SLI utama per layanan (hindari mengukur 20 SLI berbeda yang membingungkan tim).
- Terapkan kebijakan *Feature Freeze* otomatis jika Error Budget bulanan habis.
- Wajibkan pelaksanaan Blameless Post-Mortem untuk setiap insiden berkategori SEV-1 dan SEV-2 dalam waktu maksimal 48 jam.

### Recommended
- Buat dashboard Grafana khusus yang menampilkan sisa persentase Error Budget dan grafik Burn Rate real-time.
- Tunjuk jadwal On-Call rotasi yang adil, dan berikan kompensasi atau waktu istirahat libur (*comp-off*) bagi insinyur yang terbangun menangani insiden di malam hari.

### Advanced
- Hubungkan Error Budget langsung dengan pipeline deployment GitOps: jika Error Budget $< 10\%$, ArgoCD secara otomatis menolak merge release fitur non-urgensi.

---

## 17. Troubleshooting
- **Masalah**: On-Call engineer sering dibangunkan alarm darurat di malam hari, namun saat diperiksa sistem baik-baik saja (False Alarm).
  - *Penyebab*: Menggunakan alert window terlalu pendek (misal 1 menit) dengan threshold statis yang sensitif terhadap lonjakan sesaat.
  - *Solusi*: Migrasi ke Multi-Window Multi-Burn-Rate alerting (butuh pembakaran di jendela 1 jam DAN jendela 5 menit bersamaan sebelum memicu pager).
- **Masalah**: Action items dari post-mortem terus diabaikan oleh Product Manager demi mengejar target peluncuran fitur baru.
  - *Solusi*: Buat kesepakatan level VP Engineering bahwa jika Error Budget terlewati, minimal 50% kapasitas sprint wajib dialokasikan untuk tiket reliabilitas SRE.

---

## 18. Exercise
1. Sebuah layanan memproses $20.000.000$ request per bulan dengan SLO availability $99.95\%$. Hitung berapa jumlah maksimal request gagal yang diperbolehkan sebelum Error Budget habis!
2. Buat draf dokumen Blameless Post-Mortem untuk insiden fiktif di mana sertifikat TLS expired menyebabkan API Gateway tidak bisa diakses selama 45 menit.

---

## 19. Challenge
Bangun mesin kalkulator SLO & Error Budget otomatis:
- Menghitung rasio `Good Requests / Total Requests` secara periodik.
- Menghitung sisa Error Budget dalam persentase.
- Menghitung Burn Rate real-time.
- Memicu status peringatan `ALERT_PAGE` jika burn rate $> 14.4\text{x}$ dan mengubah status kebijakan rilis menjadi `FEATURE_FREEZE_ACTIVATED` saat error budget mencapai $\le 0\%$.

---

## 20. Summary
- **SRE** menyelaraskan kecepatan inovasi dan stabilitas sistem menggunakan instrumen matematis yang terukur.
- **SLI** mengukur performa aktual, **SLO** adalah target keandalan internal, dan **Error Budget** adalah kuota kegagalan yang dapat diterima.
- **Burn Rate Alerting** menyaring kebisingan alarm dan hanya memanggil insinyur saat error budget terancam habis dalam waktu dekat.
- **Blameless Post-Mortem** membangun budaya pembelajaran berkesinambungan untuk memperkuat ketahanan sistem jangka panjang tanpa rasa takut.
