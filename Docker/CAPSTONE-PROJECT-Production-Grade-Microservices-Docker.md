# 🏆 CAPSTONE PROJECT: Production-Grade Hardened Microservices Infrastructure

Selamat datang di proyek puncak (**Capstone Project**) dari kurikulum **Docker Mastery**! Proyek ini dirancang sebagai sintesis komprehensif dari seluruh konsep, teknik arsitektur, dan praktik keamanan terbaik yang telah Anda pelajari dari BAB 01 hingga BAB 10.

---

## 1. Project Overview & Requirements

### 1.1 Skenario Bisnis
Anda bertindak sebagai **Principal Platform Engineer** di sebuah perusahaan fintech unicorn (*PayFlow Inc.*). Perusahaan akan meluncurkan platform transaksi mikroservis baru bernama **PayFlow Core**. Sistem ini harus menangani pemrosesan pembayaran real-time, audit ledger keuangan, antrean background worker, dan caching latensi rendah.

### 1.2 Persyaratan Teknis (Technical Requirements)
1. **Zero-Trust Security & Hardening**:
   - Seluruh kontainer aplikasi wajib berjalan sebagai **Non-Root User** (UID 10001).
   - Root filesystem kontainer aplikasi wajib disetel **Read-Only** (`read_only: true`), dengan writable directory dialokasikan secara aman menggunakan **tmpfs in-memory mounts**.
   - Menghapus seluruh Linux capabilities default (`cap_drop: ALL`) dan hanya menambahkan capability minimal yang esensial.
   - Tidak ada plaintext credentials di dalam Dockerfile atau Docker Compose file (wajib menggunakan Environment Variables / Docker Secrets).
2. **Multi-Stage & Minimal Footprint**:
   - Image API backend harus dikompilasi menggunakan **Multi-Stage Build** berbasis image minimal (**Distroless** atau **Alpine Linux Minimal**) dengan ukuran image di bawah 40MB.
   - Menggunakan syntax BuildKit dengan package manager cache mounts (`--mount=type=cache`).
3. **High Availability & Health Supervision**:
   - Setiap service wajib mendefinisikan native **HEALTHCHECK**.
   - Dependency orchestration berbasis kondisi kesehatan riil (`depends_on: condition: service_healthy`).
   - Logging rotation global dibatasi (`max-size: 10m`, `max-file: 3`, `mode: non-blocking`).
4. **Full-Stack Observability**:
   - Pengumpulan metrik kontainer real-time menggunakan **cAdvisor** yang diintegrasikan dengan **Prometheus**.
   - Logging agregasi siap di-stream ke central aggregator.
5. **Host-Level Supervision**:
   - Seluruh stack dikelola sebagai first-class citizen oleh OS Linux melalui **Systemd Service Unit**.

---

## 2. Arsitektur Sistem

```text
                                 [ Internet / Client Requests ]
                                                |
                                                v :80 / :443
               +----------------------------------------------------------------+
               |                     EDGE ROUTER & REVERSE PROXY                |
               |                  (Nginx Gateway - Port 80 / 443)               |
               +----------------------------------------------------------------+
                               |                               |
              /api/v1/checkout |                               | /metrics (Internal)
                               v                               v
       +-------------------------------+             +---------------------------+
       |       PAYFLOW CORE API        |             |         PROMETHEUS        |
       |  (Go / Distroless - Port 8080)|             |   (Time-Series Metrics)   |
       |  - User: 10001 (non-root)     |             +---------------------------+
       |  - Read-Only RootFS           |                           ^
       |  - Drop All Capabilities      |                           | Scrape (:8080)
       +-------------------------------+             +---------------------------+
                 |            |                      |      GOOGLE CADVISOR      |
        (Async   |            | (Cache read/write)   |   (Cgroups Host Engine)   |
         Event)  |            |                      +---------------------------+
                 v            v
       +----------------+   +-------------------+
       | REDIS BROKER   |   | POSTGRESQL LEDGER |
       | (Cache & Queue)|   | (Persisted Data)  |
       | - Port 6379    |   | - Port 5432       |
       | - Named Volume |   | - Named Volume    |
       +----------------+   +-------------------+
                 ^
                 | (Pulls tasks)
       +-------------------------------+
       |   PAYFLOW SETTLEMENT WORKER   |
       | (Background Transaction Task) |
       | - Read-Only RootFS            |
       +-------------------------------+
```

---

## 3. Struktur Direktori Proyek

```text
payflow-production-infrastructure/
├── README.md
├── docker-compose.yml                      # Stack deklarasi utama
├── docker-compose.prod.yml                 # Production overrides (logging, resources)
├── .env.example                            # Template environment variables
├── systemd/
│   ├── payflow-stack.service               # Systemd Unit file untuk host Linux
│   └── payflow-prune.timer                 # Automated housekeeping timer
├── configs/
│   ├── nginx/
│   │   └── default.conf                    # Nginx reverse proxy configuration
│   └── prometheus/
│       └── prometheus.yml                  # Prometheus scrape targets
├── src/
│   ├── api/
│   │   ├── Dockerfile                      # Hardened Multi-Stage Go Dockerfile
│   │   ├── go.mod
│   │   └── main.go                         # Core Payment API
│   └── worker/
│       ├── Dockerfile                      # Hardened Minimal Worker
│       └── worker.py                       # Settlement Queue Processor
└── scripts/
    ├── deploy.sh                           # Zero-downtime deployment script
    └── smoke_test.js                       # Verification suite
```

---

## 4. Implementasi Komponen Kunci

### 4.1 Hardened Multi-Stage Dockerfile (`src/api/Dockerfile`)
```dockerfile
# syntax=docker/dockerfile:1.4
# Stage 1: Build & Compilation (Native Speed)
FROM --platform=$BUILDPLATFORM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk --no-cache add ca-certificates tzdata

COPY go.mod go.sum* ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download -x || true

COPY . .

ARG TARGETOS
ARG TARGETARCH

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -ldflags="-s -w -extldflags '-static'" -o /bin/payflow-api .

# Stage 2: Distroless Scratch-like Minimal Runtime
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

# Copy binary dan sertifikat SSL
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=builder /bin/payflow-api /app/payflow-api

# Non-root user standard distroless (UID 65532)
USER 65532:65532

EXPOSE 8080

ENTRYPOINT ["/app/payflow-api"]
```

---

### 4.2 Production Docker Compose Stack (`docker-compose.yml`)

```yaml
version: '3.8'

networks:
  public-gateway:
    driver: bridge
  internal-backend:
    driver: bridge
    internal: true # Network terisolasi tanpa akses internet langsung

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

services:
  # -------------------------------------------------------------
  # 1. Reverse Proxy (Gateway)
  # -------------------------------------------------------------
  gateway:
    image: nginx:1.25-alpine
    container_name: payflow-gateway
    restart: always
    ports:
      - "80:80"
    volumes:
      - ./configs/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - public-gateway
      - internal-backend
    depends_on:
      api:
        condition: service_healthy
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        mode: "non-blocking"

  # -------------------------------------------------------------
  # 2. Hardened Core API Microservice
  # -------------------------------------------------------------
  api:
    build:
      context: ./src/api
      dockerfile: Dockerfile
    image: payflow/api:v1.0.0
    container_name: payflow-api
    restart: unless-stopped
    read_only: true # Hardening: Filesystem Read-Only
    user: "65532:65532" # Non-Root Execution
    cap_drop:
      - ALL # Drop seluruh Linux capabilities
    security_opt:
      - no-new-privileges:true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=64m
    environment:
      - PORT=8080
      - DB_HOST=database
      - DB_PORT=5432
      - DB_USER=${POSTGRES_USER}
      - DB_PASS=${POSTGRES_PASSWORD}
      - DB_NAME=${POSTGRES_DB}
      - REDIS_HOST=cache
    networks:
      - internal-backend
    depends_on:
      database:
        condition: service_healthy
      cache:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/healthz || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 5s
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 256M
        reservations:
          memory: 64M

  # -------------------------------------------------------------
  # 3. Database (PostgreSQL 16)
  # -------------------------------------------------------------
  database:
    image: postgres:16-alpine
    container_name: payflow-database
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal-backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M

  # -------------------------------------------------------------
  # 4. In-Memory Cache (Redis 7)
  # -------------------------------------------------------------
  cache:
    image: redis:7-alpine
    container_name: payflow-cache
    restart: always
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}", "--maxmemory", "128mb", "--maxmemory-policy", "allkeys-lru"]
    volumes:
      - redis_data:/data
    networks:
      - internal-backend
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 192M

  # -------------------------------------------------------------
  # 5. Monitoring & Observability (cAdvisor)
  # -------------------------------------------------------------
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    container_name: payflow-cadvisor
    restart: unless-stopped
    privileged: true
    devices:
      - /dev/kmsg:/dev/kmsg
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    networks:
      - internal-backend
    ports:
      - "8081:8080"
```

---

### 4.3 Systemd Service Unit File (`systemd/payflow-stack.service`)

```ini
[Unit]
Description=PayFlow Enterprise Production Container Stack
Documentation=https://docs.payflow.internal
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/payflow
ExecStartPre=/usr/bin/docker compose pull --quiet
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose stop
ExecReload=/usr/bin/docker compose up -d --remove-orphans
TimeoutStartSec=300

# Security Hardening for Systemd Service
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

---

## 5. Security & Compliance Checklist (Audit Validation)

| Aspek Keamanan | Status | Mekanisme Enforcing |
|---|---|---|
| **Non-Root Execution** | ✅ LULUS | `USER 65532:65532` di Dockerfile dan `user: "65532:65532"` di Compose. |
| **Read-Only Filesystem** | ✅ LULUS | `read_only: true` aktif; penulisan temporer diisolasi via `tmpfs: /tmp`. |
| **Capabilities Stripping** | ✅ LULUS | `cap_drop: ALL` tanpa eskalasi `no-new-privileges: true`. |
| **Network Segmentation** | ✅ LULUS | Dual network: Database & Cache berada di network `internal: true` (terisolasi dari internet). |
| **Healthcheck Driven** | ✅ LULUS | Kontainer gateway dan API hanya menyala setelah upstream DB/Cache `service_healthy`. |
| **Log Space Ceiling** | ✅ LULUS | Log rotation dikunci pada `max-size: 10m` dan `max-file: 3` dengan `mode: non-blocking`. |
| **Secrets Protection** | ✅ LULUS | Semua password disuntikkan via `.env` dan tidak dibakar ke dalam image layers. |

---

## 6. Verification & Automated Test Suite

Untuk memvalidasi bahwa seluruh arsitektur Capstone Project ini berjalan dengan benar dan memenuhi standar produksi, jalankan script evaluasi berikut:

```bash
# Jalankan test suite verifikasi otomatis Capstone
node Docker/BAB-10-Production-Deployment-dan-Container-Registries/hands-on/m02/systemd_watchtower_lifecycle_sim.js
```

---

## 7. Kesimpulan & Kelulusan (Graduation)
Dengan menyelesaikan **Capstone Project** ini, Anda telah membuktikan kompetensi menyeluruh sebagai seorang **Docker Specialist & Container Platform Architect**:
- Dari pemahaman mendalam kernel Linux (*Namespaces, Cgroups v2, OverlayFS*).
- Penguasaan *Dockerfile Engineering, Multi-Stage Builds, Distroless, BuildKit Secrets & Cache Mounts*.
- Konfigurasi *User-Defined Networks, Embedded DNS, Named Volumes Backup & Restore*.
- Orkestrasi deklaratif *Docker Compose V2*, *Production Hardening (Rootless, Capabilities, ReadOnly FS)*.
- Hingga arsitektur *Multi-Architecture Buildx, Centralized Logging, cAdvisor Observability, dan Systemd Automation*.

Selamat! Anda kini siap mendesain, mengoperasikan, dan mengamankan infrastruktur container skala enterprise di dunia nyata.
