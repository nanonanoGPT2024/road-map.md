# BAB 10 — Quiz, Challenge, & Knowledge Check: SRE & FinOps

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Apa perbedaan mendasar antara SLI, SLO, dan SLA?
2. Jika sebuah layanan menetapkan SLO ketersediaan sebesar $99.9\%$, berapakah persentase Error Budget yang dimilikinya dan apa dampaknya jika budget tersebut habis?
3. Apa perbedaan antara metrik RTO (*Recovery Time Objective*) dan RPO (*Recovery Point Objective*) dalam Disaster Recovery?
4. Mengapa dalam filosofi SRE, investigasi insiden harus bersifat *Blameless* (tanpa menyalahkan individu)?
5. Apa perbedaan antara instans komputasi cloud bertipe *On-Demand* dan *Spot / Preemptible Instances*?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Bagaimana konsep *Burn Rate* membantu tim SRE membedakan antara insiden kritis (yang harus membangunkan engineer di malam hari) dan masalah lambat (yang cukup dicek saat jam kerja normal)?
7. Apa fungsi manifest `PodDisruptionBudget` (PDB) di Kubernetes saat node worker berbasis Spot Instance ditarik kembali (*preempted*) oleh cloud provider?
8. Mengapa mengejar reliabilitas sistem $100\%$ dianggap sebagai keputusan bisnis dan teknis yang buruk dalam Site Reliability Engineering?
9. Jelaskan bagaimana autoscaler **Karpenter** memberikan efisiensi biaya (FinOps) yang jauh lebih unggul dibandingkan Kubernetes Cluster Autoscaler tradisional!
10. Dalam Chaos Engineering, apa yang dimaksud dengan prinsip *Blast Radius* dan mengapa penting membatasinya saat menjalankan eksperimen di sistem produksi?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Pada tanggal 12 setiap bulan, Error Budget dari sebuah microservice pembayaran selalu habis terbakar karena rilis fitur terburu-buru, memicu kebijakan *Feature Freeze*. Namun, Product Manager menolak membekukan deployment dengan alasan target bisnis Q3. Bagaimana Anda sebagai SRE Principal memediasi konflik ini secara objektif menggunakan data?
12. **Skenario 2**: Perusahaan Anda mengalami tagihan AWS EKS membengkak dari $10.000/bulan menjadi $28.000/bulan setelah tim menambah 30 microservices baru. Rancang rencana aksi FinOps 3 tahap (Visibility -> Optimization -> Governance) untuk menurunkan tagihan kembali di bawah $12.000 tanpa menurunkan kapasitas traffic!
13. **Skenario 3**: Sebuah eksperimen Chaos Engineering mematikan instance database PostgreSQL primary di AWS region Singapura. Namun, failover otomatis ke read replica di Jakarta gagal karena DNS TTL disetel 24 jam dan aplikasi tidak menangani retry connection. Tulis ringkasan dokumen Blameless Post-Mortem dan tindakan perbaikan arsitekturnya!

---

## B. Practical Chapter Challenge: Enterprise Resilience & Cost Governance

### Deskripsi Skenario
Rancang sistem manajemen reliabilitas dan penghematan biaya untuk platform e-commerce Black Friday:
1. **SRE SLO Definition**:
   - Tetapkan availability SLO $99.95\%$ dan latency SLO ($p99 < 300\text{ms}$).
   - Buat kalkulasi Error Budget otomatis dan mekanisme blokir CI/CD saat budget habis.
2. **Chaos Engineering Experiment Plan**:
   - Definisikan eksperimen Chaos Mesh: menyuntikkan 15% packet loss dan mematikan 2 pod worker secara acak selama flash sale simulasi.
   - Ukur RTO sistem untuk memulihkan traffic ke kondisi normal.
3. **FinOps Karpenter Spot Architecture**:
   - Konfigurasikan NodePool Karpenter dengan instance Graviton ARM64 Spot.
   - Pasang PodDisruptionBudget dengan `minAvailable: 80%`.
   - Hitung proyeksi penghematan biaya tahunan dibandingkan baseline On-Demand.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Formula kalkulasi SLI, SLO, dan Error Budget.
- [ ] Multi-Burn-Rate alerting model Google SRE.
- [ ] Struktur dokumen Blameless Post-Mortem: Impact, Timeline, Contributing Factors, Action Items.
- [ ] Prinsip Chaos Engineering: Steady State, Hypothesis, Fault Injection, Analysis.
- [ ] Strategi FinOps: Spot Instances, Right-Sizing, Consolidation, Graviton ARM64.

### Saya Tidak Perlu Menghafal:
- [ ] Daftar harga presisi seluruh ratusan tipe instans cloud AWS/GCP (gunakan kalkulator cloud).
- [ ] Menghafal seluruh baris kode CRD Chaos Mesh (cukup pahami konsep `PodChaos` dan `NetworkChaos`).

### Saya Harus Bisa Melakukan:
- [ ] Menghitung sisa Error Budget dan waktu habis berdasarkan Burn Rate.
- [ ] Mengonfigurasi PodDisruptionBudget (PDB) di Kubernetes.
- [ ] Memimpin alur penanganan insiden darurat sebagai Incident Commander.
- [ ] Mengoptimalkan biaya cluster Kubernetes dengan Karpenter dan Spot instances.

```text
Checklist Kesiapan BAB 10:
[ ] Memahami filosofi SRE, SLO, dan FinOps
[ ] Menjalankan hands-on SRE Error Budget engine m01
[ ] Menjalankan hands-on Chaos & FinOps simulator m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
