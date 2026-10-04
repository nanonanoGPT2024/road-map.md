# BAB 10: Quiz, Challenge, & Knowledge Check
**Containerization, Kamal Deployment & SRE**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Multi-Stage Dockerfile untuk Rails Production**
   Jelaskan secara mendalam mengapa pattern *multi-stage build* sangat krusial dalam pembuatan *image* Docker Rails production. Bedah layer apa saja yang harus diisolasi pada *builder stage* (misalnya build tools seperti `build-essential`, `libpq-dev`, Node.js/Yarn jika ada) dan bagaimana memastikan artefak akhir (final stage) memiliki attack surface minimal serta ukuran image seringkas mungkin tanpa menyertakan gem cache, compilers, atau source code file yang tidak dibutuhkan runtime.

2. **Mekanisme Zero-Downtime Deployment Kamal via Traefik**
   Bagaimana Kamal mengorkestrasi *rolling deployment* tanpa downtime (*zero-downtime*)? Jelaskan interaksi antara Docker daemon di host, Kamal engine, dan Traefik reverse proxy ketika *new container* diluncurkan, health check diverifikasi, traffic dialihkan, hingga *old container* dikirimi sinyal penghentian.

3. **Graceful Shutdown dan Lifecycle Signal Linux (`SIGTERM` vs `SIGKILL`)**
   Ketika container Puma atau background worker (Solid Queue / Sidekiq) dihentikan oleh Kamal saat deployment, kernel mengirimkan sinyal `SIGTERM`. Jelaskan siklus hidup penanganan sinyal ini di dalam Puma dan Sidekiq/Solid Queue. Apa yang terjadi jika aplikasi mengabaikan sinyal tersebut, dan bagaimana parameter `stop_timeout` di Docker/Kamal mencegah terjadinya request drop atau *half-executed jobs*?

4. **Isolasi Environment Variables & Secret Management pada Kamal**
   Jelaskan perbedaan mendasar antara build-time environment variables (`ARG`) dan runtime environment variables (`ENV`) dalam konteks container Rails. Bagaimana Kamal v1/v2 mengamankan secrets (seperti `RAILS_MASTER_KEY` atau credentials database) melalui integrasi password manager (1Password, Bitwarden, atau generic CLI/ENV) agar secret tersebut tidak pernah bocor atau tersimpan secara permanen (*baked*) ke dalam image layer registry Docker?

5. **Rails Asset Precompilation tanpa Database Connection**
   Dalam stage pembangunan Docker image, command `rails assets:precompile` wajib dijalankan. Mengapa proses ini sering gagal jika Rails mencoba menginisialisasi database adapter, dan bagaimana konfigurasi standard Rails (seperti `SECRET_KEY_BASE_DUMMY=1` atau stubbing configurations) mengatasi dependensi database saat kompilasi asset di pipeline container build?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Diagnosis Out-Of-Memory (OOM) Killer & cgroup Allocation**
   Sebuah container Rails secara berkala mengalami *restart* mendadak tanpa ada stack trace di `production.log`.
   * Bagaimana Anda memvalidasi via `dmesg`, `docker inspect`, atau metrik Linux cgroup (v1/v2) bahwa proses tersebut dieksekusi oleh Linux OOM Killer?
   * Jelaskan korelasi antara alokasi memori Ruby heap (`RUBY_GC_HEAP_GROWTH_FACTOR`, `MALLOC_ARENA_MAX`) dengan batas memori container Docker (`mem_limit`), serta mitigasi apa yang harus diterapkan pada glibc memory fragmentation.

2. **Routing & Healthcheck Flapping pada Kamal & Traefik**
   Ketika melakukan `kamal deploy`, proses berhenti (*hung*) pada step "Waiting for new container to become healthy" lalu melakukan rollback otomatis. 
   * Uraikan seluruh kriteria yang harus dipenuhi oleh endpoint `/up` (Rails 7.1+) agar Traefik menandainya sebagai *healthy*.
   * Mengapa pengecekan koneksi database dan Redis/Cache di dalam endpoint health check `/up` dapat memicu insiden *cascading failure* (thundering herd/flapping), dan bagaimana arsitektur probe yang benar memisahkan *Liveness probe* vs *Readiness probe*?

3. **Database Migration Synchronization dalam Konteks Multi-Server Kamal**
   Jika Anda mendeploy Rails ke cluster yang terdiri dari 5 virtual machine menggunakan Kamal, bagaimana Kamal memastikan bahwa task `db:migrate` hanya dieksekusi tepat **satu kali** sebelum container baru di semua host menerima traffic? Apa risiko arsitektural jika terjadi skema migrasi yang lambat (*long-running lock*), dan bagaimana Kamal mengisolasi proses runner migrasi dari host web biasa?

4. **Container PID 1 Zombie Reaping Problem**
   Jika container Rails dijalankan tanpa init system (seperti `tini`, `dumb-init`, atau fitur Docker `--init`), proses Rails (PID 1) bertanggung jawab me-*reap* child processes yang menjadi yatim (*orphaned child processes*). Jelaskan skenario di mana Rails (misalnya melalui gem yang menjalankan subshell seperti `system()` atau `Open3.capture3`) dapat menyebabkan resource starvation akibat akumulasi *zombie processes* jika PID 1 tidak dikelola dengan benar.

5. **Volume Mounting, Persistence, dan File Permission pada Rootless/Non-Root Container**
   Docker best practice mewajibkan container Rails dijalankan sebagai non-root user (misalnya user `rails` dengan UID/GID 1000). Ketika aplikasi membutuhkan shared persistent volume (misalnya storage Active Storage lokal, tmp sockets, atau cache directory) yang di-mount dari host Linux, jelaskan mekanisme permission mismatch (`EACCES - Permission Denied`) yang sering terjadi dan bagaimana mengatasinya menggunakan init container, entrypoint wrapper script, atau host ownership alignment.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Thread Contention & CPU Starvation saat Rolling Deploy
* **Konteks:** Perusahaan fintech mendeploy micro-monolith Rails via Kamal pada 3 host bare-metal (masing-masing 32 vCPU, 64 GB RAM). Aplikasi berjalan dengan Puma cluster mode (4 workers, 16 threads per worker = 64 threads per host).
* **Insiden:** Setiap kali `kamal deploy` dijalankan pada jam sibuk (traffic 15,000 RPM), latensi API p99 melonjak dari 45ms ke 12,000ms selama 90 detik. Host CPU utilization melonjak ke 100% dengan load average mencapai 120+, dan Traefik mulai melempar respon `502 Bad Gateway` secara sporadis.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah arsitektural terkait *co-existence* antara container lama dan container baru di host yang sama selama transisi rolling deploy Kamal.
  2. Bagaimana perhitungan resource allocation (vCPU/RAM ceiling) dan Puma process thread pool harus diatur untuk mencegah saturasi core processor saat kedua container berjalan simultan?
  3. Konfigurasi apa di `config/deploy.yml` milik Kamal yang dapat digunakan untuk mengatur *boot delay*, *drain timeout*, dan pembatasan konkurensi deployment antar host?

### Skenario B: Race Condition Skema Database (Destructive Migration Deploy)
* **Konteks:** Tim developer melakukan refactoring pada modul billing. Kolom `card_token` pada tabel `payments` diubah namanya menjadi `stripe_token`. Developer membuat migrasi Rails tunggal: `rename_column :payments, :card_token, :stripe_token`.
* **Insiden:** Kamal menjalankan migrasi database dengan sukses. Container baru mulai di-boot secara bertahap di 4 server. Namun, selama jendela deploy 2 menit (saat container lama masih melayani traffic publik), 8% transaksi checkout gagal dengan error `ActiveModel::MissingAttributeError: can't write unknown attribute 'card_token'` pada container lama, dan error `PG::UndefinedColumn` pada query background job yang masih membaca kolom lama.
* **Pertanyaan Diagnostik:**
  1. Mengapa teknik migrasi single-step tersebut secara fatal melanggar prinsip *backward-compatible continuous deployment*?
  2. Rancang strategi migrasi multi-fase (*expand-and-contract pattern*) yang lengkap dan aman untuk skenario ini menggunakan fitur `ignored_columns` di ActiveRecord, sehingga rolling deploy zero-downtime dapat dieksekusi tanpa satu pun request gagal.

### Skenario C: Trade-off Arsitektur Stateful Accessories vs Managed Infrastructure
* **Konteks:** Perusahaan SaaS rintisan mengadopsi Kamal untuk seluruh infrastrukturnya demi menekan biaya cloud AWS. Mereka menggunakan fitur `accessories` di Kamal untuk menjalankan PostgreSQL, Redis, dan Solid Queue di dalam container Docker pada VPS single host yang sama dengan server web.
* **Insiden:** Ketika trafik naik 10x lipat dalam waktu 3 bulan, tim SRE menghadapi masalah kritis:
  * Backup database via container accessory lockup mengganggu latensi web.
  * Update konfigurasi PostgreSQL via Kamal accessory membutuhkan recreate container yang memicu downtime singkat.
  * Terjadi disk I/O bottleneck parah (IOPS saturation) antara volume write PostgreSQL dan logging web container.
* **Pertanyaan Diagnostik:**
  1. Analisis batasan arsitektural dari fitur `accessories` pada Kamal. Kapan sebuah service layak dijadikan Kamal accessory, dan kapan service tersebut *wajib* dialihkan ke Managed Service (seperti AWS RDS / Cloud Databases)?
  2. Buat matriks evaluasi trade-off (Reliability, Scalability, Operational Overhead, Cost) antara menjalankan PostgreSQL/Redis via Kamal Accessories vs Managed Services.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Kamal Deployment Pipeline dengan Hardened Container & Observability Stack

#### Problem Statement
Anda ditunjuk sebagai Lead Platform Engineer untuk merancang dan mengimplementasikan pipeline containerization dan automated deployment dari awal (*zero to production*) untuk aplikasi Rails 8 multi-role (Web API & Solid Queue Worker). Infrastruktur target adalah 2 unit Linux Ubuntu Server bare-metal/VPS (1 staging, 1 production). Sistem harus memiliki proteksi zero-downtime, non-root user execution, memory-leak guard, dan automated health verification.

#### Requirements
1. **Hardened Multi-Stage Dockerfile:**
   * Stage 1 (`base`): Berbasis `ruby:3.3-slim`, setting essential packages, bundler, dan user setup non-root (`rails` UID 1000).
   * Stage 2 (`build`): Instalasi build-dependencies, instalasi gem (`bundle install` deployment mode), asset precompilation dengan dummy credentials.
   * Stage 3 (`runtime`): Hanya menyalin runtime libraries, gems yang sudah terkompilasi, dan source code aplikasi. Pastikan direktori `storage`, `tmp`, dan `log` memiliki write access bagi user `rails`.
   * Integrasikan `jemalloc` untuk menekan alokasi memory leak & fragmentasi glibc pada Ruby.
2. **Kamal Configuration (`config/deploy.yml`):**
   * Pisahkan host/role untuk `web` dan `workers` (Solid Queue). Role worker tidak boleh diekspos ke Traefik.
   * Definisikan accessories untuk Redis/Solid Cache jika diperlukan.
   * Konfigurasikan dynamic environment injection dan secrets via command builder.
   * Definisikan zero-downtime rolling deploy rules: `readiness_delay`, buffer timeout, dan Puma graceful healthcheck via endpoint `/up`.
3. **Puma & Graceful Handling Configuration:**
   * Konfigurasi `config/puma.rb` yang mendeteksi core CPU secara dinamis dan memiliki graceful termination timeout yang sinkron dengan Docker `stop_timeout`.
4. **Automated Smoke Test Script:**
   * Buat bash/ruby operational script pasca-deploy (`bin/deploy-verify`) yang memverifikasi HTTP response, latency threshold (< 200ms), ketiadaan zombie process di host, dan integrasi log output Traefik.

#### Constraints
* **Security:** Container dilarang keras dijalankan sebagai user `root`. Tidak boleh ada API keys atau Rails credentials yang terekspos di Docker image layer history (`docker history <image>`).
* **Availability:** Selama eksekusi deploy, curl loop pada port publik (Traefik) harus menghasilkan status code `200 OK` secara kontinu tanpa satu pun status code `502`, `503`, atau `Connection Refused`.
* **Zero Custom Orchestrator:** Dilarang menggunakan Kubernetes; seluruh arsitektur murni menggunakan Kamal, Traefik, dan Docker Engine.

#### Expected Output
1. File `Dockerfile` lengkap, ter-benchmark, dan ber-komentar arsitektural.
2. File `config/deploy.yml` Kamal yang production-ready dengan isolasi role (web & background worker).
3. File `config/puma.rb` yang dioptimasi untuk environment containerized.
4. Shell script / pipeline verification `bin/deploy-verify` yang menguji integritas zero-downtime deploy.
5. Dokumen post-mortem runbook singkat (1 halaman markdown) yang menjelaskan mitigasi: *Apa yang harus dilakukan engineer jika proses deployment macet di tengah jalan pada tahap "Acquiring deployment lock" atau "Traefik routing freeze".*

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi internal multi-stage Dockerfile dan cara kerja layer caching di Docker Engine.
- [ ] Peran Traefik reverse proxy dalam arsitektur Kamal serta siklus dynamic routing via Docker labels.
- [ ] Urutan pengiriman Linux signals (`SIGTERM`, `SIGINT`, `SIGKILL`) ke process manager Puma dan background workers.
- [ ] Dampak fragmentasi memori glibc pada Ruby runtime dan implementasi mitigasi menggunakan `jemalloc`.
- [ ] Pola database migration zero-downtime (*Expand and Contract pattern*) dan isolasi task migrasi pada deployment cluster.
- [ ] Batasan, kelebihan, dan risiko arsitektural penggunaan Kamal accessories dibandingkan Cloud Managed Services.
- [ ] Perbedaan implementasi probe: Readiness (apakah traffic boleh masuk) vs Liveness (apakah container harus di-restart).

### Saya tidak perlu menghafal:
- [ ] Seluruh baris sintaks default `docker run` flags yang diabstraksi secara otomatis oleh Kamal.
- [ ] Sintaks konfigurasi file TOML Traefik tingkat rendah yang telah di-generate melalui Docker container labels oleh Kamal.
- [ ] Flag command-line dari compiler gcc/make yang dijalankan saat `bundle install` native extension (c-extensions).

### Saya harus bisa melakukan:
- [ ] Menulis Dockerfile Rails production-ready yang aman, berbasis non-root user, dan berukuran di bawah 300MB.
- [ ] Mengonfigurasi dan mengeksekusi deployment multi-server, multi-role (Web & Worker) menggunakan Kamal.
- [ ] Melakukan troubleshooting kegagalan deploy Kamal menggunakan command internal (`kamal app logs`, `kamal app details`, `kamal traefik logs`).
- [ ] Mengonfigurasi endpoint healthcheck `/up` di Rails agar mengevaluasi subsistem esensial tanpa memicu false-positive unhealthiness.
- [ ] Menganalisis log kernel Linux (`dmesg`) untuk mendeteksi event OOM Killer pada container yang crash di server production.
- [ ] Mengatur injection credentials dan secrets ke dalam container Rails tanpa menyimpannya ke image registry.