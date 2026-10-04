# BAB 10: Containerization, Kamal Deployment & SRE
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengoptimalkan Docker Runtime Rails**: Mengonfigurasi multi-stage build image berbasis Debian Slim dengan integrasi memory allocator `jemalloc`, optimasi JIT (`YJIT`), dan caching layer kompilasi asset secara deterministik.
- **Merancang Arsitektur Topologi Multi-Server Kamal**: Mengonfigurasi dan mengorkestrasi kluster multi-peran (*web*, *job worker*, *cron*, dan *accessories*) menggunakan Kamal 2 tanpa overhead Kubernetes.
- **Mengimplementasikan Zero-Downtime Deployment**: Menguasai siklus hidup traffic switching melalui `kamal-proxy` (atau Traefik pada arsitektur hybrid), dynamic request buffering, dan rolling updates bertingkat.
- **Mengeksekusi Zero-Downtime Database Migration**: Menerapkan pola *Expand and Contract* untuk perubahan skema database tanpa menyebabkan *table lock* berkepanjangan pada transaksi aktif.
- **Mengintegrasikan Manajemen Rahasia Produksi & SRE Telemetry**: Mengamankan credential dengan integrasi secure key vault/1Password CLI/SOPS, serta mengimplementasikan instrumentasi OpenTelemetry dan Prometheus metrics untuk mengukur SLI/SLO ketersediaan aplikasi.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Rails Internals**: Arsitektur Puma (cluster mode, worker/thread pool), Bootsnap precompilation, dan Propshaft/Sprockets asset pipeline.
- **Linux Fundamentals**: POSIX signal handling (`SIGTERM`, `SIGQUIT`, `SIGINT`), cgroups v2, network namespaces, dan routing socket Unix/TCP.
- **Containerization Basics**: Konsep layer caching Docker, OCI image specification, bind mounts, dan Docker bridge networks.
- **Database Concurrency**: Karakteristik lock PostgreSQL (AccessExclusiveLock vs ShareUpdateExclusiveLock) dan transaksi ACID.

---

### 3. Concept & Internal Architecture

#### A. Evolusi Kamal 2 dan `kamal-proxy`
Kamal (sebelumnya MRSK) dirancang oleh 37signals untuk menghilangkan kompleksitas orkestrasi Kubernetes bagi aplikasi berarsitektur monolith modular. 

Pada Kamal 2, layer routing berevolusi dari Traefik menjadi **`kamal-proxy`**:
- **Zero-Downtime Traffic Buffering**: Saat deploy, `kamal-proxy` menahan (buffer) koneksi HTTP masuk di level socket selama instance kontainer lama dihentikan dan instance baru melewati health-check `/up`. Klien tidak menerima error `502 Bad Gateway` melainkan peningkatan latency beberapa milidetik.
- **Resource Footprint**: `kamal-proxy` ditulis dalam bahasa Go, mengonsumsi memori < 20MB per server (berbanding terbalik dengan Traefik atau Ingress Controller Kubernetes yang membutuhkan ratusan MB).
- **Socket Passing**: Instance aplikasi baru di-boot di port ephemeral, diverifikasi via endpoint health check, lalu dimasukkan ke routing table `kamal-proxy`. Instance lama dikirimi sinyal `SIGTERM` dengan grace period timeout untuk menyelesaikan active request.

```
       Internet / CDN Edge (Cloudflare/Fastly)
                        │
                        ▼ [Port 80/443]
              ┌───────────────────┐
              │    kamal-proxy    │
              └─────────┬─────────┘
                        │
     ┌──────────────────┴──────────────────┐
     │ (Pause incoming HTTP requests)      │
     ▼                                     ▼
┌──────────────┐                     ┌──────────────┐
│  Container   │                     │  Container   │
│  Version N   │ ──[ SIGTERM ]──>    │ Version N+1  │
│  (Port 3001) │   Graceful Drain    │ (Port 3002)  │
│  [DEREGISTER]│                     │   [/up: OK]  │
└──────────────┘                     └──────────────┘
```

#### B. Memory Allocator & Ruby Execution Engine: `jemalloc` & YJIT
Secara default, Ruby menggunakan allocator `glibc malloc`. Pada aplikasi Rails multi-threaded (Puma worker dengan 3-5 thread), `glibc` menghasilkan fragmentasi memori ekstrem (*memory bloat*) karena arena memori tidak dikembalikan ke OS secara efisien.
- **`jemalloc`**: Menggunakan teknik *slab allocation* dan thread-specific cache (tcache), secara drastis mengurangi fragmentasi memori Rails sebesar 20–40%.
- **YJIT (Yet Another Ruby JIT)**: Compiler in-process bawaan Ruby. Mengompilasi Basic Block Chains (BBC) ke native machine code. Memerlukan penyesuaian memory overhead (`--yjit-exec-mem-size=64`) agar tidak memicu Container Out-Of-Memory (OOM) Killer dari Linux Kernel.

#### C. Mekanisme Kunci Orkestrasi Kamal
1. **Locking Mechanism**: Kamal memanfaatkan metadata direktori atau file remote locks pada server target (`kamal-lock`) guna mencegah konkurensi deployment ganda dari CI/CD runner yang berbeda.
2. **Deterministic Pre-checks**: Sebelum eksekusi, Kamal memverifikasi SSH connectivity, versi Docker daemon, ketersediaan port, dan dependensi network bridge.

---

### 4. Why & What

| Dimensi | PaaS (Heroku / Render) | Kubernetes (EKS / GKE) | Kamal 2 on Bare Metal / VPS |
| :--- | :--- | :--- | :--- |
| **Biaya Komputasi** | Sangat Tinggi (Markup 300-500%) | Tinggi (Control plane + Node overhead) | **Optimal (Bare cost server)** |
| **Kompleksitas Operasional** | Nol (Managed) | Ekstrem (CRD, Ingress, CNI, CSI) | **Rendah (Hanya Docker + SSH)** |
| **Vendor Lock-in** | Sangat Tinggi | Rendah (Portable OCI/k8s API) | **Nol (Docker murni di sembarang Linux)** |
| **Zero-Downtime Engine** | Proprietary Router | Ingress Controller + Readiness Probe | **`kamal-proxy` socket hold** |
| **Performa I/O Bare Metal** | Virtualisasi Terbatas | Bergantung instance type cloud | **Maksimal (Native NVMe/CPU access)** |

#### Kapan Menggunakan Kamal?
- Infrastruktur Rails monolithic atau micro-monolith terdistribusi (1 s.d. 100 node) yang membutuhkan performa mentah tanpa ingin mengalokasikan satu departemen khusus untuk maintenance Kubernetes.
- Strategi *Cloud Exit* atau *Hybrid Deployment* (Hetzner, OVH, AWS EC2, on-premise datacenter).

---

### 5. How: Workflow Deployment Detail

```
[ Developer / CI Pipeline ]
             │
             ├─ 1. Git Push / Merge to Main
             │
             ├─ 2. Docker Multi-Arch Buildx (AMD64/ARM64)
             │      └─ Precompile Bootsnap & Assets
             │
             ├─ 3. Push OCI Image to Registry (GHCR/ECR)
             │
             ├─ 4. 'kamal deploy' Triggered
             │      │
             │      ├─ a. Acquire Remote Lock (`kamal-lock`)
             │      ├─ b. Pull Image on Target Hosts (Web, Worker)
             │      ├─ c. Run Migration Hook (Isolated Container)
             │      ├─ d. Start New App Container (Ephemeral Port)
             │      ├─ e. Healthcheck Probe (`GET /up` -> 200 OK)
             │      ├─ f. kamal-proxy: Route Swap & Drain Old Instance
             │      ├─ g. Stop Old Container (SIGTERM -> Timeout -> SIGKILL)
             │      └─ h. Release Remote Lock
             │
[ Production Live State Updated ]
```

---

### 6. Analogy & Architecture Diagram

#### Analogi: Sistem Pengalihan Jalur Kereta Cepat
Bayangkan stasiun kereta api yang mengganti rangkaian gerbong aktif tanpa menghentikan penumpang.
- **Kubernetes**: Membangun stasiun baru di sebelahnya, memasang rel baru otomatis dengan sistem sensor komputer super rumit, lalu meruntuhkan stasiun lama.
- **Kamal 2**: Memasang wesel pengalih jalur (*kamal-proxy*) langsung di stasiun yang ada. Kereta baru (v2) diparkir di jalur cadangan dan dicek kelayakannya. Saat siap, palang penutup gerbang ditahan beberapa detik untuk penumpang berikutnya, wesel diarahkan ke jalur baru, dan kereta lama (v1) diarahkan ke depo secara mulus tanpa penumpang tertinggal atau terluka.

#### Diagram Topologi Multi-Server Enterprise
```
                           [ Cloudflare Anycast CDN ]
                                       │
                                       ▼
                  [ Layer 4 Load Balancer (HAProxy / AWS NLB) ]
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────┐                             ┌───────────────────────┐
│     web-node-01       │                             │     web-node-02       │
│  ┌─────────────────┐  │                             │  ┌─────────────────┐  │
│  │   kamal-proxy   │  │                             │  │   kamal-proxy   │  │
│  └────────┬────────┘  │                             └────────┬────────┘  │
│           │           │                                      │           │
│     ┌─────┴─────┐     │                                ┌─────┴─────┐     │
│     ▼           ▼     │                                ▼           ▼     │
│ [App v1]   [App v2]   │                          [App v1]   [App v2]   │
│ (Active)   (Staging)  │                          (Active)   (Staging)  │
└───────────────────────┘                             └───────────────────────┘
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
│ worker-node-01  │           │ worker-node-02  │           │  db-accessory   │
│ ┌─────────────┐ │           │ ┌─────────────┐ │           │ ┌─────────────┐ │
│ │ Sidekiq     │ │           │ │ Sidekiq     │ │           │ │ Redis 7     │ │
│ │ Critical    │ │           │ │ Default/Mail│ │           │ │ Cluster     │ │
│ └─────────────┘ │           │ └─────────────┘ │           │ └─────────────┘ │
└─────────────────┘           └─────────────────┘           └─────────────────┘
```

---

### 7. Implementation: Production Configurations

#### A. Production Multi-Stage `Dockerfile`
Menghasilkan image minimalis, mengompilasi library non-root, mengintegrasikan `jemalloc`, dan mengaktifkan optimasi YJIT.

```dockerfile
# syntax=docker/dockerfile:1.4
# Base image dengan runtime Ruby konsisten
FROM ruby:3.3.6-slim-bookworm AS base

WORKDIR /rails

# Set environment produksi krusial
ENV RAILS_ENV="production" \
    BUNDLE_DEPLOYMENT="1" \
    BUNDLE_PATH="/usr/local/bundle" \
    BUNDLE_WITHOUT="development:test" \
    LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2" \
    MALLOC_CONF="dirty_decay_ms:1000,narenas:2,background_thread:true" \
    RUBY_YJIT_ENABLE="1"

# Stage build untuk kompilasi native extension & assets
FROM base AS build

# Install build dependencies
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    libyaml-dev \
    pkg-config && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Install gems dengan mount cache untuk mempercepat re-build
COPY Gemfile Gemfile.lock ./
RUN --mount=type=cache,target=/usr/local/bundle/cache \
    bundle install && \
    rm -rf /usr/local/bundle/ruby/*/cache \
           /usr/local/bundle/ruby/*/bundler/gems/*/.git

# Copy source code aplikasi
COPY . .

# Precompile Bootsnap cache untuk optimasi boot loader
RUN bundle exec bootsnap precompile --gemfile app/ lib/

# Precompile Assets tanpa menginisiasi koneksi database nyata
RUN SECRET_KEY_BASE_DUMMY=1 ./bin/rails assets:precompile

# Final stage untuk runtime produksi
FROM base AS runner

# Install runtime dependencies saja (termasuk jemalloc)
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    curl \
    libjemalloc2 \
    libpq5 \
    netcat-traditional \
    tini && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Setup non-privileged user untuk SRE security baseline
RUN groupadd --system --gid 1000 rails && \
    useradd rails --uid 1000 --gid 1000 --create-home --shell /bin/bash && \
    chown -R rails:rails /rails

# Salin artifak dari build stage
COPY --from=build --chown=rails:rails /usr/local/bundle /usr/local/bundle
COPY --from=build --chown=rails:rails /rails /rails

USER rails:rails

EXPOSE 3000

# Gunakan tini sebagai init process untuk mengelola POSIX signals dengan benar
ENTRYPOINT ["/usr/bin/tini", "--", "/rails/bin/docker-entrypoint"]
CMD ["./bin/rails", "server"]
```

#### B. Production Entrypoint (`bin/docker-entrypoint`)
```bash
#!/usr/bin/env bash
set -e

# Eksekusi persiapan jika role adalah web
if [ "$1" = "./bin/rails" ] && [ "$2" = "server" ]; then
  # Verifikasi konektivitas dependency jika diperlukan
  echo "[ENTRYPOINT] Preparing application boot sequence..."
  
  # Hapus file server.pid lama jika tersisa pasca restart paksa
  if [ -f /rails/tmp/pids/server.pid ]; then
    rm -f /rails/tmp/pids/server.pid
  fi
fi

exec "$@"
```

#### C. Production Topologi `config/deploy.yml` (Kamal 2 Specification)
```yaml
service: enterprise-core
image: ghcr.io/enterprise-org/enterprise-core

servers:
  web:
    hosts:
      - 10.0.0.11
      - 10.0.0.12
    labels:
      kamal-proxy-health-check-interval: 3
      kamal-proxy-health-check-timeout: 2
    options:
      network: "private-bridge"
      memory: "4g"
      cpus: "2.0"
  worker:
    hosts:
      - 10.0.0.21
      - 10.0.0.22
    cmd: bundle exec sidekiq -C config/sidekiq.yml
    options:
      network: "private-bridge"
      memory: "8g"
      cpus: "4.0"

proxy:
  ssl: true
  host: api.enterprise.domain
  app_port: 3000
  healthcheck:
    path: /up
    interval: 2
    timeout: 3

registry:
  server: ghcr.io
  username: <%= ENV["KAMAL_REGISTRY_USERNAME"] %>
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  clear:
    RAILS_ENV: production
    RAILS_LOG_TO_STDOUT: "true"
    RAILS_SERVE_STATIC_FILES: "true"
    MALLOC_CONF: "dirty_decay_ms:1000,narenas:2,background_thread:true"
    RUBY_YJIT_ENABLE: "1"
    PORT: "3000"
  secret:
    - RAILS_MASTER_KEY
    - DATABASE_URL
    - REDIS_URL

ssh:
  user: ops-deployer
  keys: ["~/.ssh/id_ed25519_deployer"]

hooks:
  pre-deploy: .kamal/hooks/pre-deploy

accessories:
  redis:
    image: redis:7.2-alpine
    roles:
      - worker
    port: "6379:6379"
    cmd: "redis-server --appendonly yes --requirepass <%= ENV['REDIS_PASSWORD'] %>"
    directories:
      - "redis-data:/data"
    options:
      network: "private-bridge"
```

#### D. Production Pre-Deploy Hook (`.kamal/hooks/pre-deploy`)
Eksekusi migrasi database di kontainer ephemeral terisolasi sebelum rolling deploy dimulai:
```bash
#!/usr/bin/env bash
set -e

echo "=== [PRE-DEPLOY HOOK] Executing Database Migrations ==="
kamal app run --role web --env RAILS_ENV=production bin/rails db:migrate:status
kamal app run --role web --env RAILS_ENV=production bin/rails db:migrate
echo "=== [PRE-DEPLOY HOOK] Migrations successfully finished ==="
```

---

### 8. Real World Case Study: E-Commerce Scale Migration

#### Latar Belakang
**PT Nusantara Digital Market** mengelola platform belanja daring dengan beban 65 juta request/bulan dan lonjakan 12.000 RPM saat kampanye gajian. Arsitektur sebelumnya berada di AWS EKS (Elastic Kubernetes Service) dengan 8 node `c6i.xlarge` + ALB + ECR.
- **Isu**: Biaya AWS tembus $4.200/bulan. Tim engineering sering mengalami kegagalan deployment akibat *readiness probe thrashing* k8s saat Rails me-warmup Rails YJIT dan Bootsnap.

#### Keputusan Desain & Implementasi
1. **Migrasi Infrastruktur**: Pindah ke 4 Node Bare-Metal Hetzner AX52 (AMD Ryzen 7 7700, 64GB DDR5 RAM, 2x 1TB NVMe Gen4) berharga total €380 (~$410)/bulan.
2. **Implementasi Kamal 2**: Node 1 & 2 bertindak sebagai `web`, Node 3 & 4 sebagai `worker` (Sidekiq) dan Redis accessory.
3. **Optimasi Runtime**:
   - Ganti default malloc dengan `jemalloc`.
   - Mengaktifkan `RUBY_YJIT_ENABLE=1` dengan `yjit-exec-mem-size=64`.
   - Konfigurasi `kamal-proxy` buffer dengan interval health check 2 detik ke route `/up`.

#### Hasil & Metrik SRE Pasca Migrasi
```
Indikator Metrik                 AWS EKS (Sebelumnya)     Kamal + Bare Metal (Sesudah)
───────────────────────────────────────────────────────────────────────────────────────
Infrastruktur Spend / Bulan      $4,200                   $410 (-90.2%)
Response Time P50                48 ms                    18 ms
Response Time P99                310 ms                   82 ms (Bebas latency overhead vSwitch)
Memory Bloat per Worker          1.2 GB (Crash loop OOM)  580 MB (Stabil flatline - jemalloc)
Deploy Duration (Zero Downtime)  6 menit 40 detik         1 menit 15 detik
```

---

### 9. Trade-offs Analysis

```
                 PERFORMANCE
                     ▲
                     │        ● Bare Metal + Kamal 2
                     │
                     │                 ● AWS EKS (Enterprise Tuning)
                     │
         ● Kamal VPS │
                     │        ● Heroku / Render
                     │
─────────────────────┼────────────────────────────────► OPERATIONAL COMPLEXITY
                     │
                     │
                     ▼
                 LOW COST
```

1. **Bare Metal + Kamal 2 vs Kubernetes**:
   - *Keuntungan*: I/O disk maksimal, throughput jaringan raw tinggi, tidak ada overhead etcd, arsitektur konfigurasi < 150 baris YAML vs ribuan baris manifest K8s.
   - *Kerugian*: Tidak ada autoscaling otomatis (Horizontal Pod Autoscaler). Penambahan node server membutuhkan instalasi Docker manual via SSH (bisa diatasi dengan Ansible/Terraform).
2. **Kamal Proxy vs Nginx/Traefik**:
   - *Keuntungan*: Didesain khusus untuk siklus hidup kontainer OCI, otomatisasi socket buffering instan saat container exchange.
   - *Kerugian*: Fitur L7 rewrite, Web Application Firewall (WAF), dan plugin ecosystem belum selengkap Traefik atau Nginx (disarankan tetap menggunakan Cloudflare di layer edge terluar).

---

### 10. Common Mistakes & Troubleshooting

#### 1. Deadlock Skema Database saat Deployment
*Gejala*: Pre-deploy hook `kamal app run ... db:migrate` hang selamanya, memicu rollback otomatis atau deploy abort.
*Akar Masalah*: Menjalankan operasi DDL agresif (misal: `ALTER TABLE orders ADD COLUMN status varchar DEFAULT 'pending' NOT NULL;`) pada tabel dengan jutaan baris yang memicu `AccessExclusiveLock`.
*Solusi Enterprise*: Terapkan arsitektur migrasi terpisah dengan library seperti `strong_migrations`. Tambahkan kolom secara nullable dulu, backfill async, lalu beri validasi secara non-blocking.
```ruby
# Skenario Benar (Non-blocking)
class AddStatusToOrders < ActiveRecord::Migration[7.1]
  disable_ddl_transaction!

  def change
    add_column :orders, :status, :string, if_not_exists: true
    add_index :orders, :status, algorithm: :concurrently, if_not_exists: true
  end
end
```

#### 2. Asset 404 pada Dynamic Rolling Updates
*Gejala*: Pengguna yang mengakses browser saat deploy menerima error Javascript `Failed to load module /assets/application-[hash].js` (404).
*Akar Masalah*: Instance Web Node 1 sudah menjalankan versi v2 (kontainer lama telah dihapus beserta file static di dalamnya), namun browser klien yang terhubung ke Web Node 2 masih meminta manifest lama dari link yang di-cache.
*Solusi*: Push compiled assets ke Shared Object Storage (S3 / Cloudflare R2 / GCS) via pipeline CI, lalu konfigurasikan `config.action_controller.asset_host = "https://cdn.perusahaan.com"`.

#### 3. Remote Deployment Stuck Lock
*Gejala*: `kamal deploy` gagal dengan output error: `Can't run concurrent deployments: kamal-lock is already held`.
*Troubleshooting*:
```bash
# Periksa siapa pemegang kunci
kamal lock status

# Lepaskan kunci secara manual jika deployment sebelumnya di-kill di level CI runner
kamal lock release
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Proses OS PID 1**: Container menggunakan `tini` atau dumb-init untuk mencegah zombie processes dari Puma workers/forks.
- [ ] **Memory Tuning**: `libjemalloc2` di-load via `LD_PRELOAD`, parameter `MALLOC_CONF` disetel untuk aggressive background purging.
- [ ] **Telemetry Endpoint**: Route `/up` murni mengembalikan status liveness internal, bukan pemeriksaan berat ke 5 microservice eksternal yang dapat memicu *cascading failure*.
- [ ] **Non-Root Execution**: Container berjalan di bawah UID 1000 (`rails`), bukan `root`.
- [ ] **Puma Worker & Thread Sizing**: Alokasi `WEB_CONCURRENCY = vCPU * 1.5`, thread per worker berkisar antara 3 sampai 5 thread.
- [ ] **Secret Management**: Tidak ada commit file `.env` ke Git repository. Menggunakan injection rahasia via environment runner CI/CD (`KAMAL_REGISTRY_PASSWORD`, `RAILS_MASTER_KEY`).
- [ ] **Log Driver**: Docker log rotation disetel aktif (`json-file` dengan `max-size: 50m`, `max-file: 5`) untuk mencegah disk exhaustion pada VM.

---

### 12. Hands-on Practice

Buat dan simpan seluruh file berikut ke dalam direktori lokal: `hands-on/m02/`

#### Langkah 1: Inisialisasi Struktur Direktori
```bash
mkdir -p hands-on/m02/{config,.kamal/hooks,bin}
cd hands-on/m02
```

#### Langkah 2: Buat Entrypoint Script
Simpan di `bin/docker-entrypoint`:
```bash
#!/usr/bin/env bash
set -e

if [ "$1" = "bundle" ] && [ "$2" = "exec" ] && [ "$3" = "puma" ]; then
  echo "Booting Enterprise Rails Engine..."
fi

exec "$@"
```
Jadikan executable: `chmod +x bin/docker-entrypoint`

#### Langkah 3: Setup Mock Health Check Rails Controller
Simpan di `config/puma.rb`:
```ruby
max_threads_count = ENV.fetch("RAILS_MAX_THREADS") { 5 }
min_threads_count = ENV.fetch("RAILS_MIN_THREADS") { max_threads_count }
threads min_threads_count, max_threads_count

port ENV.fetch("PORT") { 3000 }
environment ENV.fetch("RAILS_ENV") { "production" }
workers ENV.fetch("WEB_CONCURRENCY") { 2 }

preload_app!
```

#### Langkah 4: Setup Kamal Deployment YAML
Simpan di `config/deploy.yml`:
```yaml
service: edge-store
image: my-registry.domain.com/apps/edge-store

servers:
  web:
    hosts:
      - 192.168.10.101
      - 192.168.10.102
  worker:
    hosts:
      - 192.168.10.103
    cmd: bundle exec sidekiq

proxy:
  ssl: false
  host: store.local
  app_port: 3000
  healthcheck:
    path: /up
    interval: 3

env:
  clear:
    RAILS_ENV: production
    RUBY_YJIT_ENABLE: "1"
    LD_PRELOAD: "/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
```

#### Langkah 5: Simulasi Deployment Dry-Run
Jalankan perintah berikut untuk memvalidasi syntax tanpa mengeksekusi koneksi remote:
```bash
docker run --rm -v $(pwd):/workdir -w /workdir ghcr.io/basecamp/kamal:latest config
```

---

### 13. Exercise

#### Level Easy
1. Modifikasi file `Dockerfile` pada seksi 7 agar menyertakan dependensi runtime library `imagemagick` dan `vips` untuk pemrosesan file gambar (ActiveStorage).
2. Tuliskan satu baris konfigurasi environment Puma untuk memastikan Puma mematikan worker yang tidak responsif dalam waktu 30 detik.

#### Level Medium
1. Buat custom hook `.kamal/hooks/post-deploy` menggunakan bash script yang mengirimkan pesan webhook otomatis ke Channel Discord / Slack SRE berisi payload: commit SHA, deployer user, dan status sukses deployment.
2. Tuliskan konfigurasi `config/deploy.yml` untuk accessory PostgreSQL yang memiliki persistent volume di `/var/lib/postgresql/data` dan password rahasia dinamis.

#### Level Hard
1. Buat strategi deployment blue/green zero-downtime untuk migrasi tipe data kolom dari `integer` ke `bigint` pada tabel dengan 100 juta record transaksi aktif. Jelaskan tahapan migrasi, penulisan kueri Rails ActiveRecord, sinkronisasi write ganda, serta deployment checkpoint dengan Kamal.

---

### 14. Challenge

**Skenario**: Sistem Anda mengalami insiden `Kernel OOM Killer` mendadak setiap hari Senin pukul 09:00 ketika traffic melonjak 400%. Server target terdiri dari 2 node Web Kamal dengan RAM masing-masing 8 GB. Puma saat ini berjalan dengan `WEB_CONCURRENCY=6` dan `RAILS_MAX_THREADS=16`.

**Tugas Arsitektur**:
1. Hitung kebutuhan matematis konsumsi memori maksimum teoritis Puma worker di bawah beban penuh jika diketahui satu thread Rails rata-rata mengonsumsi 45 MB memori dan baseline interpreter menyerap 180 MB.
2. Rancang konfigurasi ulang yang deterministik pada `deploy.yml`, parameter alokasi cgroups `options.memory`, Puma thread/worker ratios, serta konfigurasi flags `MALLOC_CONF` untuk mencegah sistem crash tanpa menambah resource node server fisik.
3. Tuliskan runbook langkah mitigasi darurat saat separuh web node masuk dalam kondisi `unhealthy` selama proses deployment berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi utama dari library `libjemalloc` jika diintegrasikan ke dalam container image Ruby on Rails?
2. Mengapa endpoint `/up` tidak disarankan untuk melakukan kueri berat seperti scanning cache seluruh tabel database?
3. Sinyal POSIX apa yang dikirimkan oleh `kamal-proxy` atau Docker daemon ke Puma saat menginisiasi proses graceful shutdown?
4. Apa fungsi dari perintah `disable_ddl_transaction!` pada migrasi ActiveRecord di lingkungan database PostgreSQL?
5. Di direktori server manakah secara default Kamal meletakkan acquisition deployment lock?

#### B. Pertanyaan Intermediate
6. Mengapa pada Dockerfile multi-stage untuk Rails kita perlu menyuntikkan argumen `SECRET_KEY_BASE_DUMMY=1` saat tahapan `assets:precompile`?
7. Bagaimana cara `kamal-proxy` mencegah pengguna menerima respons error `502 Bad Gateway` saat container baru sedang di-boot dan container lama ditutup?
8. Bagaimana pengaruh parameter `dirty_decay_ms:1000` pada `jemalloc` terhadap lifecycle heap memory Ruby di server Linux?
9. Apa perbedaan esensial dalam konfigurasi `config/deploy.yml` antara peran kontainer kategori `web` dan kontainer kategori `worker`?
10. Mengapa `tini` atau init process serupa mutlak diperlukan di dalam container Docker yang menjalankan Puma cluster mode?

#### C. Skenario Kasus Produksi
11. **Kasus 1**: Pada deployment Kamal, proses terhenti di tahap `Waiting for container to become healthy`. Akses langsung ke `http://ip-container:ephemeral-port/up` mengembalikan `curl: (52) Empty reply from server`. Log Docker menunjukkan: `Puma caught SIGTERM before initialization completed`. Apa yang sebenarnya terjadi dan bagaimana penanganannya?
12. **Kasus 2**: Sebuah update aplikasi menyertakan library native C baru. Pipeline build berhasil, namun saat kontainer distart di server target (Host Debian 11 lama), terjadi crash `GLIBC_2.34 not found`. Apa akar masalahnya pada pipeline Docker dan bagaimana solusinya?
13. **Kasus 3**: Anda menjalankan migrasi penambahan kolom berindeks pada tabel berukuran 40 GB. Pre-deploy hook berhasil menyelesaikan `db:migrate`, namun deployment web berikutnya gagal karena response time P99 melonjak hingga timeout ke seluruh user. Analisis apa yang terjadi pada layer PostgreSQL engine!

---

### Kunci Jawaban & Rationale Quiz

#### Basic
1. **Fungsi jemalloc**: Mengurangi fragmentasi memori Ruby secara agresif melalui model chunk/slab memory allocation yang lebih ramah concurrency multi-threading dibanding standar `glibc malloc`.
2. **Healthcheck /up**: Endpoint healthcheck harus bersifat lightweight untuk menguji ketersediaan proses lokal. Jika mengeksekusi operasi berat, healthcheck akan timeout di bawah traffic tinggi dan memicu restart loop palsu (*flapping*).
3. **Sinyal POSIX**: `SIGTERM` (meminta Puma menghentikan penerimaan request baru, menyelesaikan request aktif dalam kurun waktu timeout tertentu sebelum akhirnya `SIGKILL` dikirim).
4. **disable_ddl_transaction!**: Mematikan pembungkusan migrasi dalam transaksi implisit, memungkinkan operasi concurrent database (seperti `add_index algorithm: :concurrently`) dieksekusi tanpa menyebabkan table locking massal.
5. **Lokasi Kamal Lock**: Berada di folder home pengguna target atau folder aplikasi dalam remote file `.kamal/lock-[service]`.

#### Intermediate
6. **SECRET_KEY_BASE_DUMMY**: Rails mewajibkan keberadaan `SECRET_KEY_BASE` untuk menginisialisasi runtime app saat asset precompile, meskipun kompilasi asset murni file assets statis dan tidak memerlukan decrypt kredensial nyata.
7. **Pencegahan 502**: `kamal-proxy` menahan (buffer) koneksi TCP/HTTP pada listen socket di layer proxy hingga kontainer target yang baru dinyatakan sehat via probe `/up`.
8. **dirty_decay_ms**: Menentukan seberapa cepat memori yang tidak lagi terpakai oleh thread Ruby dikembalikan ke kernel OS (1000 ms = 1 detik), menjaga RSS memori kontainer tetap ramping.
9. **Web vs Worker**: Role `web` didaftarkan ke load balancing routing `kamal-proxy` dengan mapping port HTTP dan healthcheck probe. Role `worker` berjalan sebagai autonomous process di background tanpa binding proxy routing table.
10. **Init Process (Tini)**: Rails Puma forks worker process. Jika worker mati mendadak, init process (PID 1) bertugas me-reap *zombie/defunct process* agar process table kernel Linux tidak penuh.

#### Skenario Kasus Produksi
11. **Analisis Kasus 1**: Healthcheck timeout Kamal terlalu agresif (misal 1-2 detik), sementara Rails app butuh waktu 5-8 detik untuk initial warmup (Rails autoloading & database connection pooling). Kamal mengira kontainer hang, lalu mengirim `SIGTERM` sebelum Puma selesai binding port. **Solusi**: Tingkatkan parameter `healthcheck.timeout` dan `healthcheck.interval` pada `config/deploy.yml`.
12. **Analisis Kasus 2**: Container di-build menggunakan Base OS image yang memiliki versi libc lebih baru (misal Debian Bookworm) daripada dependencies arsitektur kernel/system pada Host, atau native gem dikompilasi menggunakan environment dinamis yang tidak match. **Solusi**: Standarisasi base image build dan runner menggunakan OCI image self-contained murni (multi-stage build dengan exact tagging).
13. **Analisis Kasus 3**: Penambahan index dilakukan tanpa opsi `algorithm: :concurrently`. PostgreSQL mengambil `ShareLock` yang memblokir seluruh operasi `INSERT`, `UPDATE`, dan `DELETE` pada tabel 40 GB tersebut hingga indeks selesai dibuat. Akibatnya, request web menumpuk di antrean Puma, thread pool habis, dan server kolaps.

---

### 16. Summary

Implementasi containerization modern untuk Ruby on Rails pada skala enterprise tidak mewajibkan adopsi platform orkestrasi yang rumit seperti Kubernetes. Melalui integrasi **Kamal 2**, rekayasa performa container murni dapat diwujudkan dengan efisiensi maksimal:

1. **Efisiensi Runtime**: Penggunaan `jemalloc` bersamaan dengan `Ruby YJIT` menghasilkan utilisasi memori yang stabil dan respons throughput P99 yang superior pada lingkungan bare-metal atau VM standar.
2. **Zero-Downtime Determinism**: Adopsi `kamal-proxy` menghadirkan zero-downtime deployment berbasis socket holding yang ringan dan tahan banting.
3. **Operational Stability**: Disiplin DDL non-blocking, multi-stage builds non-root, sanitasi PID 1 melalui `tini`, dan observabilitas health check menjadi fondasi ketersediaan tinggi (*High Availability*) yang memenuhi standar Service Level Objective (SLO) enterprise modern.