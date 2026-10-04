# BAB 07: Quiz, Challenge, & Knowledge Check
**Continuous Delivery & Automated Deployment (CD)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Continuous Delivery vs. Continuous Deployment:**
   Jelaskan perbedaan fundamental dalam kontrol tata kelola (*governance*), toleransi risiko, dan mekanisme verifikasi antara *Continuous Delivery* dan *Continuous Deployment*. Pada skenario sistem perbankan dengan regulasi ketat (misal: PCI-DSS atau audit OJK), mengapa *Continuous Delivery* sering kali menjadi batas akhir otomasi yang diizinkan dibandingkan *Continuous Deployment*?
2. **Immutable Infrastructure vs. Mutable Deployment:**
   Bandingkan pendekatan deployment *Mutable* (mengupdate binari/konfigurasi langsung di server yang berjalan via SSH/Ansible) dengan paradigma *Immutable Infrastructure* (membangun image kontainer/AMI baru untuk setiap rilis). Analisis keduanya dari sudut pandang *configuration drift*, kemampuan *rollback*, dan auditabilitas forensik pasca-insiden!
3. **Anatomi Strategi Deployment (Blue/Green vs. Canary vs. Rolling):**
   Uraikan mekanisme pemindahan beban trafik (*traffic routing*) pada strategi *Blue/Green*, *Canary*, dan *Rolling Update*. Evaluasi *trade-off* masing-masing strategi terhadap kebutuhan alokasi kapasitas infrastruktur (*compute overhead*), latensi propagasi DNS/routing, dan *blast radius* (radius dampak) saat terjadi kegagalan rilis!
4. **Peran Probes dalam Deployment Orkestrasi:**
   Dalam orkestrasi kontainer (seperti Kubernetes), jelaskan perbedaan mekanisme dan tujuan fungsional antara *Startup Probe*, *Readiness Probe*, dan *Liveness Probe*. Apa dampak fatal pada stabilitas aplikasi yang sedang melayani trafik aktif jika seorang engineer salah mengonfigurasi *Readiness Probe* menjadi identik dengan *Liveness Probe* pada endpoint CPU-heavy?
5. **Anti-pattern Tagging `:latest` dan Prinsip Artifact Determinism:**
   Mengapa penggunaan tag `:latest` atau tag mutabel lainnya pada artifact kontainer dianggap sebagai anti-pattern kritis dalam pipeline CD enterprise? Jelaskan bagaimana penggunaan *immutable digest* (SHA256 hash) menjamin determinisme deployment dan kepatuhan terhadap prinsip *traceability* dari kode sumber ke lingkungan produksi!

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Zero-Downtime Database Migrations (Expand/Contract Pattern):**
   Sebuah rilis CD memerlukan perubahan destruktif pada skema database relasional (misal: memecah kolom `full_name` menjadi `first_name` dan `last_name`). Jika aplikasi harus mempertahankan ketersediaan 100% (*zero-downtime*), jelaskan fase-fase teknis implementasi *Expand and Contract Pattern* (Parallel Run) dalam pipeline CD Anda sebelum kode versi lama sepenuhnya dimatikan!
2. **Graceful Shutdown & Connection Draining:**
   Ketika pipeline CD memerintahkan penghentian instance versi lama untuk digantikan versi baru, jelaskan interaksi sinyal POSIX kernel (`SIGTERM` vs `SIGKILL`), siklus hidup *TCP Keep-Alive*, dan *Reverse Proxy Connection Draining*. Mengapa kegagalan menangani `SIGTERM` secara eksplisit pada kode aplikasi menyebabkan lonjakan HTTP 502/504 Bad Gateway pada klien selama proses deployment berlangsung?
3. **Push-Based CD vs. Pull-Based CD (GitOps Engine):**
   Bedah perbedaan arsitektural antara model *Push-based CD* (contoh: Jenkins/GitLab CI runner mengeksekusi `kubectl apply` langsung ke cluster) dan *Pull-based CD* (contoh: ArgoCD/Flux agent berjalan di dalam cluster). Analisis implikasi keamanan keduanya terhadap *blast radius credential leakage* dan penanganan *out-of-band configuration drift*!
4. **Dynamic Secret Injection & Ephemeral Credentials:**
   Jelaskan risiko keamanan membakar (*hardcoding*) secret ke dalam artifact image atau menyimpannya secara statis di environment variables CI/CD runner. Bagaimana arsitektur *Dynamic Secret Injection* berbasis runtime (misalnya integrasi HashiCorp Vault dengan Kubernetes Service Account via mutating webhook) menyelesaikan masalah rotasi kredensial tanpa memicu restart loop pada aplikasi?
5. **Automated Rollback Detection Metrics:**
   Sebuah automated deployment canary dikonfigurasi untuk mengevaluasi metrik telemetri secara real-time. Metrik apa saja (merujuk pada *Google SRE 4 Golden Signals*) yang wajib dipantau selama periode *bake time* Canary? Jelaskan skenario di mana metrik HTTP status code `200 OK` dapat memberikan *false negative* (lolos uji padahal sistem rusak) dan bagaimana Anda mengatasinya menggunakan verifikasi sintaksis atau log analysis!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The 502 Gateway Dropped-Packets Spike
* **Kondisi:**
  Sebuah microservice berbasis Node.js/Go dengan trafik 15.000 RPS menggunakan Kubernetes Deployment dengan strategi *RollingUpdate* (`maxSurge: 25%`, `maxUnavailable: 0`). Setiap kali tim melakukan merge ke branch `main`, pipeline CD otomatis melakukan deployment. Namun, grafik observabilitas (Datadog/Prometheus) secara konsisten mencatat lonjakan HTTP 502 Bad Gateway sebesar 1.5% - 3% selama 45 detik selama pod lama dihentikan.
* **Pertanyaan Diagnostik:**
  1. Identifikasi *race condition* yang terjadi antara pembaruan rute IP di iptables/IPVS (via Kubernetes Service controller) dan penghancuran (*teardown*) pod oleh Kubelet!
  2. Solusi arsitektur dan konfigurasi apa yang harus diterapkan pada file manifest deployment (hint: `preStop` hook, terminationGracePeriodSeconds) dan kode aplikasi untuk menghilangkan drop trafik ini secara absolut?

### Skenario B: Database Lock Contention & Split-Brain Deployment
* **Kondisi:**
  Tim engineering menerapkan strategi deployment *Blue/Green* untuk memotong waktu rilis. Ketika Environment Green (versi v2.4.0) dinyalakan dan menjalankan migrasi skema database `ALTER TABLE orders ADD COLUMN risk_score INT NOT NULL DEFAULT 0;` pada database PostgreSQL berukuran 800GB, seketika seluruh aplikasi versi v2.3.0 di Environment Blue (yang masih melayani 100% trafik produksi) mengalami *database connection pool exhaustion* dan *thread hanging*.
* **Pertanyaan Diagnostik:**
  1. Mengapa eksekusi DDL tersebut menyebabkan downtime total pada Environment Blue meskipun Environment Green belum menerima trafik sama sekali? Jelaskan level tabel lock yang terjadi pada engine database!
  2. Bagaimana merancang gerbang verifikasi (*deployment gates*) dan pipeline migrasi database agar DDL dijalankan secara non-blocking (*safe schema migrations*) tanpa memicu eksploitasi exclusive locks?

### Skenario C: Canary Blast-Radius Spillover pada Stateful Service
* **Kondisi:**
  Sebuah sistem broker order finansial mengimplementasikan Canary Deployment sebesar 5% menggunakan Istio Service Mesh. Versi v2 Canary memiliki *memory leak* tersembunyi yang baru terpicu ketika sebuah koneksi WebSocket bertahan lebih dari 3 menit. Setelah 10 menit deployment berjalan, pod Canary mengalami OOMKilled (*Out of Memory*), mengakibatkan ribuan koneksi WebSocket terputus seketika dan berpindah (*failover storm*) kembali ke Pod v1, memicu lonjakan beban CPU hingga 100% pada instance v1 yang menyebabkan efek domino (*cascading failure*).
* **Pertanyaan Diagnostik:**
  1. Apa kelemahan fatal dalam validasi kesehatan (*health criteria*) Canary pipeline di atas sebelum mempercayai pod siap menerima koneksi persisten/stateful?
  2. Rancang arsitektur rollback otomatis yang dilengkapi dengan *circuit breaker* dan *backpressure mitigation* agar kegagalan Canary tidak melumpuhkan kluster versi stabil!

---

## 4. Chapter Challenge

### Tantangan Praktis: Merancang Zero-Downtime Automated Canary Pipeline dengan Automated Metric-Based Rollback Engine

#### Problem:
Layanan transaksi pembayaran `payment-api` sering mengalami insiden regresi performa (lonjakan latency P99 dan error HTTP 5xx) pasca deployment. Tim operasional menuntut implementasi mekanisme Continuous Deployment yang mampu mendeteksi anomali pada subset trafik kecil (Canary) dan melakukan *abort & self-healing rollback* otomatis tanpa intervensi manual.

#### Requirements:
1. **Infrastructure & Pipeline Orchestration:**
   * Buat simulasi deployment pipeline (bisa berbasis GitHub Actions / GitLab CI / Scripted Pipeline dengan Bash + Docker/Minikube/Kind).
   * Gunakan strategi **Canary Deployment**:
     * Fase 1: Deploy versi baru dengan alokasi 10% traffic.
     * Fase 2: *Analysis Window* (tunggu selama interval evaluasi).
     * Fase 3: Promosi penuh ke 100% traffic jika metrik valid; ATAU Rollback instan ke versi stabil jika metrik gagal.
2. **Automated Verification Gate (Synthetic/Real Telemetry):**
   * Buat script analisis (Python/Bash) yang bertindak sebagai *Automated Canary Analyzer*.
   * Analyzer wajib mengekstrak metrik performa:
     * Rasio Error: HTTP 5xx harus `< 1%`.
     * Latency P99: Harus `< 200ms`.
   * Jika kriteria dilanggar dalam kurun waktu evaluasi, pipeline harus mengirimkan *signal abort*, mengembalikan routing trafik 100% ke versi *Baseline*, dan mematikan instance Canary.
3. **Application Graceful Teardown:**
   * Aplikasi (bisa berupa mockup server HTTP sederhana menggunakan Go, Node.js, atau Python) wajib menangani `SIGTERM` dengan benar: menyelesaikan request yang sedang berjalan (*in-flight requests*) dan menolak koneksi baru secara anggun sebelum proses mati.

#### Constraints:
* **Zero Dropped Connections:** Tidak boleh ada satupun request bernilai HTTP 502/503/504 selama proses transisi traffic (Canary -> Stable atau Canary -> Abort).
* **Strict Idempotency:** Pipeline harus dapat dijalankan berulang kali (*idempotent*) tanpa meninggalkan state orphan container/service jika terjadi *crash* di tengah jalan.
* **Security:** Kredensial cluster/environment tidak boleh diekspos melalui argumen command line atau logs pipeline.

#### Expected Output:
1. File manifest/konfigurasi infrastruktur (misal: Docker Compose dengan Reverse Proxy Nginx/Envoy, ATAU Kubernetes Manifest / Argo Rollouts CRD).
2. Kode aplikasi mockup yang menyertakan implementasi *Graceful Shutdown*.
3. Script otomatisasi pipeline (`deploy.sh` atau `.github/workflows/cd.yml`) yang mengeksekusi logika Canary shifting dan automated rollback.
4. Log output terminal yang mendemonstrasikan dua skenario:
   * **Skenario Lolos:** Versi baru sehat -> Canary 10% lolos verifikasi -> Promosi 100%.
   * **Skenario Gagal:** Versi baru diinjeksi error rate 10% -> Canary Analyzer mendeteksi pelanggaran SLO -> Pipeline melakukan rollback otomatis ke versi sebelumnya dengan *exit code 1*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara *Continuous Delivery* (verifikasi otomatis, deployment manual) dan *Continuous Deployment* (otomasi penuh end-to-end hingga produksi).
- [ ] Kelemahan dan kelebihan strategi deployment: Recreate, Rolling Update, Blue/Green, dan Canary Deployment.
- [ ] Mekanisme deteksi kesehatan container melalui *Startup*, *Readiness*, dan *Liveness probes*, serta interaksinya dengan Service Endpoints/Load Balancers.
- [ ] Konsep *Expand and Contract Pattern* untuk evolusi skema database relasional tanpa downtime (*Zero-Downtime Database Migration*).
- [ ] Penanganan *Linux Signals* (`SIGTERM`, `SIGKILL`) untuk menjamin *Graceful Shutdown* dan pencegahan request dropping.
- [ ] Prinsip *Artifact Immutability*, penomoran versi SemVer, dan risiko fatal tag mutabel seperti `:latest`.
- [ ] Perbedaan arsitektur *Push-based CD* vs. *Pull-based CD* (*GitOps*) dalam hal keamanan dan drift reconciliation.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter sintaks API spec Kubernetes (`spec.strategy.rollingUpdate.maxSurge`, dsb.) di luar kepala tanpa melihat dokumentasi resmi.
- [ ] Konfigurasi internal baris-per-baris dari third-party ingress controller atau service mesh (Envoy/Istio EnvoyFilter syntax).
- [ ] Spesifikasi syntax command unik dari CLI tools CD spesifik (misal: argocd app sync flags) selama memahami konsep dasarnya.

### Saya harus bisa melakukan:
- [ ] Merancang pipeline CD yang memisahkan tahap *build/artifact generation* dengan tahap *deployment deployment/orchestration*.
- [ ] Mengimplementasikan *Graceful Shutdown* handler di dalam kode aplikasi backend untuk menangani penutupan koneksi secara tertib.
- [ ] Mengonfigurasi strategi *Rolling Update* yang aman dengan kombinasi `readinessProbe` dan `preStop` hook guna mencegah HTTP 502 error.
- [ ] Mengintegrasikan gerbang pengujian kualitas (*quality gates* / *smoke testing*) otomatis pasca-deploy sebelum instance baru dipromosikan.
- [ ] Menulis script rollback otomatis berbasis status kode evaluasi metrik telemetri (SLO validation).
- [ ] Mengelola konfigurasi dan secrets deployment secara aman menggunakan prinsip *Environment Variable Injection* atau Secret Manager tanpa mengotori image container.