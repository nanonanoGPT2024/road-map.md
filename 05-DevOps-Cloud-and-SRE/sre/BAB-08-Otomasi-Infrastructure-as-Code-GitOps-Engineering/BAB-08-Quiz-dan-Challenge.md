# Evaluasi Bab 08: Otomasi, Infrastructure as Code, & GitOps Engineering

---

## I. Basic Questions (Pilihan Ganda & Konseptual Ringkas)

1. Menurut filosofi standar Google Site Reliability Engineering (SRE), berapa batas alokasi waktu maksimal yang diizinkan untuk aktivitas operasional (*toil*) bagi seorang SRE?
   - A. 20%
   - B. 35%
   - C. 50%
   - D. 80%

2. Manakah dari karakteristik berikut yang **TIDAK** termasuk dalam klasifikasi Toil?
   - A. Pekerjaan manual yang diulang berkali-kali secara rutin.
   - B. Desain arsitektur untuk memigrasikan monolitik ke microservice.
   - C. Intervensi manual me-restart instance cache setiap server kehabisan memori.
   - D. Tugas yang tidak memberikan nilai perbaikan jangka panjang pada keandalan sistem.

3. Konsep dasar GitOps mensyaratkan status infrastruktur didefinisikan secara deklaratif di Git. Mekanisme utama yang dilakukan engine GitOps untuk menangani perbedaan antara Git dan infrastruktur runtime disebut:
   - A. Three-Way Handshake
   - B. Continuous Integration Rebase
   - C. Drift Detection and Reconciliation Loop
   - D. Dynamic DNS Shifting

4. Dalam deployment strategi *Blue/Green*, apa kerugian utama yang harus dipertimbangkan dari perspektif arsitektur resource?
   - A. Downtime rilis aplikasi yang mencapai puluhan menit.
   - B. Diperlukannya kapasitas compute ekstra hingga 100% (2x kapasitas) saat proses transisi berjalan.
   - C. Tidak dimungkinkannya proses instant rollback jika terjadi insiden.
   - D. Memerlukan service mesh yang sangat rumit untuk membagi traffic pada layer 7.

5. Algoritma GitOps reconciler menggunakan teknik *Three-Way Merge Patch* untuk menghitung delta perubahan. Tiga representasi state yang dievaluasi adalah:
   - A. Staging State, Production State, dan Backup State.
   - B. Original Desired State, Modified Actual State, dan New Desired State.
   - C. Git HEAD, Git Master, dan Git Remote.
   - D. Client Config, Server Binary, dan Database Schema.

---

## II. Intermediate Questions (Analisis Kasus & Algoritmik)

1. Jelaskan bahaya fenomena *Remediation Cascading Loop* pada sistem self-healing otomatis! Sebutkan dua mekanisme pengaman (*safety guards*) yang wajib ditambahkan pada auto-remediator untuk mencegah kehancuran cluster total!
2. Bagaimana cara kerja GitOps Engine (seperti ArgoCD) membedakan antara *Intentional Drift* (perubahan sah yang dilakukan controller in-cluster seperti Kubernetes HPA) dan *Unintentional Drift* (perubahan manual ilegal via `kubectl edit`)?
3. Pada Canary Deployment berbasis automated metric analysis, mengapa evaluasi metrik menggunakan window rate 10 detik (`rate(...[10s])`) dianggap sebagai anti-pattern dibandingkan window rate 1 atau 5 menit pada evaluasi SLO produksi?
4. Suatu tim SRE mengoperasikan layanan microservice dengan target SLO Latency P99 < 200ms. Tuliskan logika query PromQL yang mengukur rasio keberhasilan latency ini untuk digunakan dalam `AnalysisTemplate` rilis canary!
5. Sebutkan perbedaan fundamental antara *In-Place Deployment*, *Blue/Green Deployment*, dan *Canary Rollout* dari segi alokasi traffic, risiko blast radius, dan kompleksitas rollback!

---

## III. Scenario-Based Questions (Studi Kasus Nyata)

### Skenario 1: Flapping Reconciler pada Kluster Skala Besar
Sebuah tim SRE mengonfigurasi GitOps ArgoCD dengan fitur `selfHeal: true`. Pada cluster mereka, terdapat aplikasi pihak ketiga yang memasang Validating & Mutating Admission Webhook. Webhook ini otomatis menginjeksi timestamp deployment ke dalam annotation pod setiap kali pod dibuat. Akibatnya, ArgoCD mendeteksi bahwa metadata pod di runtime berbeda dengan manifes Git, lalu melakukan sync ulang. Sync ulang memicu webhook berjalan kembali dan memperbarui timestamp lagi. Loop ini terjadi tanpa henti, membanjiri Kube API Server dengan 2.000 request per detik dan membekukan cluster.
- **Pertanyaan**: Identifikasi titik kegagalan arsitektur ini dan susun solusi terperinci (beserta konfigurasi cuplikan YAML) untuk menghentikan loop mutasi tanpa mematikan fitur auto-heal GitOps secara global!

### Skenario 2: Tragedi OOMKilled Auto-Remediation Storm
Sebuah backend worker pemrosesan video memiliki bug memory leak. Saat beban traffic naik, memori pod terisi hingga batas limit cgroup dan dihentikan oleh OS (`OOMKilled`). Sebuah auto-remediation controller internal mendeteksi status fail ini dan langsung mengeksekusi penghapusan pod agar pod baru di-spawn seketika. Karena bug berada di level kode inti, setiap pod baru langsung OOMKilled dalam tempo 15 detik. Remediator terus me-recreate pod ribuan kali dalam 10 menit, menghabiskan IP address subnet pool cluster (VPC CNI IP exhaustion) dan memicu down total pada seluruh microservice lain di node yang sama.
- **Pertanyaan**: Rancang arsitektur perbaikan remediator tersebut! Parameter proteksi apa saja (seperti error budget throttling, sliding window rate limits, dan circuit breaker) yang harus diimplementasikan?

### Skenario 3: False-Positive Rollback pada Canary Traffic Rendah
Layanan otentikasi internal memiliki traffic yang fluktuatif: 5.000 RPS pada siang hari dan hanya 2 RPS pada jam 04:00 pagi. Deployment Canary versi baru dilakukan secara otomatis oleh pipeline CD pada jam 04:15 pagi dengan traffic step 5% (hanya menangani ~0.1 RPS). Tiba-tiba pipeline menandai Canary *Failed* dan memicu automatic rollback karena satu request gagal akibat network timeout client, menghasilkan kegagalan 100% pada interval evaluasi tersebut.
- **Pertanyaan**: Evaluasi kelemahan desain strategi rollout tersebut. Bagaimana cara merekayasa ulang `AnalysisTemplate` dan conditional rules agar canary system tangguh terhadap anomali statistik pada volume traffic rendah (*low sample size anomaly*)?

---

## IV. Practical Chapter Challenge: Resilient Self-Healing & Drift Guard Engine

Rancang dan bangun sistem engine self-healing dan drift mitigation terdistribusi sederhana namun tangguh menggunakan Python yang mampu:
1. **Memantau Desired vs Actual State**: Membaca representasi JSON/YAML Desired State dan Actual State dari infrastruktur.
2. **Drift Detection**: Mendeteksi jika atribut runtime penting (misal: image tag, replica count, atau resource limit) berubah di luar Git.
3. **Safety Circuit Breaker**: Jika auto-remediation dipanggil lebih dari 3 kali dalam sliding window 30 detik untuk target yang sama, sistem harus membuka sirkuit (*Trip Circuit Breaker*), menghentikan intervensi destruktif, dan menerbitkan alert eskalasi kritis ke engineer.
4. **Idempotent Reconciliation**: Menerapkan patch koreksi hanya pada atribut yang bermutasi tanpa me-restart komponen jika tidak diperlukan.

Petunjuk implementasi lengkap untuk tantangan ini terdapat pada direktori file hands-on: `hands-on/m01/self_healing_auto_remediation.py`.