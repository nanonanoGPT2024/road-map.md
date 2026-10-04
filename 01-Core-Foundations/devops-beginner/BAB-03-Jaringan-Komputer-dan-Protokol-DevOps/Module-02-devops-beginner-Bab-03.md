# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengoperasikan Pipeline CI/CD Produksi**: Mengonstruksi pipeline multi-stage dengan prinsip immutability, automated gating, security scanning (SAST/SCA/Container Linting), dan artifact provenance.
- **Mengimplementasikan Strategi Zero-Downtime Deployment**: Mengonfigurasi dan membedah mekanisme internal dari *Rolling Update*, *Blue/Green Deployment*, dan *Canary Release* pada level routing jaringan dan orchestrator.
- **Mengelola Konfigurasi & Rahasia (Secrets Engine)**: Menerapkan zero-trust configuration management menggunakan pattern *External Secrets/Vault* tanpa hardcoded credentials pada environment produksi.
- **Menganalisis Internal Runtime Kontainer**: Memahami interaksi Linux kernel primitives (*cgroups v2*, *namespaces*, *seccomp*, *OverlayFS2*) terhadap kestabilan sistem di bawah beban konkurensi tinggi.
- **Membangun Telemetri Dasar Terintegrasi**: Mengintegrasikan three pillars of observability (Metrics, Logs, Traces) langsung ke dalam release lifecycle untuk automated rollback.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta **wajib** menguasai:
1. **Linux System Administration**: Pemahaman proses OS (`systemd`, signal handling `SIGTERM`/`SIGKILL`), networking dasar (TCP/IP, iptables, DNS resolution), dan file permission.
2. **Containerization Fundamentals**: Mampu menulis multi-stage `Dockerfile`, memahami layer caching, dan pengoperasian Docker CLI.
3. **Version Control System**: Git branching strategies (GitFlow, Trunk-Based Development) dan Git internals (commit trees, tags, SHA hashes).
4. **Basic Scripting**: Shell scripting (Bash/POSIX-compliant) untuk task automation dan manipulasi output JSON/YAML menggunakan `jq` atau `yq`.

---

## 3. Concept & Internal Architecture

Dalam arsitektur enterprise, produksi bukan sekadar "menjalankan kode di server publik", melainkan membangun sistem deterministik yang tahan terhadap kegagalan (*fault-tolerant*), dapat diaudit (*auditable*), dan dapat dipulihkan secara instan (*reproducible*).

### A. Immutable Infrastructure & Artifact Provenance
Filosofi produksi modern menolak modifikasi server secara *in-place*. Setiap pembaruan kode menghasilkan artifak immutable (Image OCI) yang diberi label unik berbasis Git Commit SHA, bukan tag mutable seperti `latest`. 

```
[Git Commit SHA: 4f8a1c9] 
       │
       ▼
[CI Builder: Multi-Stage] ──► [OCI Image: registry.corp.internal/app:4f8a1c9]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
        [Deploy to Staging]                     [Promote to Production]
     (Checksum Verification)                 (Zero Mutation / Identical Bin)
```

Artifak yang lolos dari tahap integrasi tidak pernah di-build ulang untuk staging atau production; artifak yang sama dipromosikan melintasi environment dengan konfigurasi yang disuntikkan secara dinamis (*Twelve-Factor App: Config via Environment Variables*).

### B. Linux Kernel Primitives: Di Balik Abstraksi Kontainer
Orchestrator mengandalkan kernel Linux untuk mengisolasi beban kerja produksi:
- **Namespaces**: Mengisolasi pandangan sistem terhadap resource (`pid` untuk pohon proses, `net` untuk routing tabel/antarmuka virtual `veth`, `mnt` untuk mount points, `ipc`, `uts`, `user`).
- **Control Groups (cgroups v2)**: Membatasi, mencatat, dan mengisolasi penggunaan resource fisik (CPU, Memori, Disk I/O, Network pids). OOM (*Out Of Memory*) Killer bekerja di layer ini ketika limit dilanggar.
- **OverlayFS2**: Union mount filesystem yang memisahkan base read-only layer (image) dari ephemeral read-write layer (container diff), mengoptimalkan storage I/O dan startup latency.

### C. Deployment Mechanics & Traffic Routing
Transisi versi aplikasi diatur pada level layer 4/7 reverse proxy atau service mesh:

```
                          Client Traffic
                                │
                                ▼
                       [Ingress / Gateway]
                                │
        ┌───────────────────────┴───────────────────────┐
        │ Route: Weight 90%                             │ Route: Weight 10%
        ▼                                               ▼
[Service v1.0.0 (Stable)]                       [Service v1.1.0 (Canary)]
 ├─ Pod/Instance A                               ├─ Pod/Instance C (New)
 └─ Pod/Instance B                               └─ Telemetry: Error Rate?
                                                    ├─ > 0.5% ──► Rollback (0%)
                                                    └─ < 0.5% ──► Promote (100%)
```

- **Rolling Updates**: Mengganti instance lama secara bertahap menggunakan parameter `maxSurge` dan `maxUnavailable`.
- **Blue/Green**: Menyediakan dua environment identik penuh. Pengalihan dilakukan instan pada level router pointer.
- **Canary Deployments**: Mengalihkan persentase kecil traffic pengguna nyata (misal: 5-10%) ke versi baru untuk validasi telemetri real-time sebelum ekspansi penuh.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional / Pemula | Pendekatan Enterprise Production |
| :--- | :--- | :--- |
| **Pembaruan Kode** | SSH manual ke server, `git pull`, restart service. | CI/CD automated pipeline, ephemeral runner, zero-downtime orchestrator. |
| **Manajemen Tag** | Menggunakan image tag `:latest`. | Menggunakan tag immutable berbasis Git Commit SHA + Cosign Signature. |
| **Konfigurasi** | File `.env` disalin manual ke server produksi. | Secrets Engine terpusat (HashiCorp Vault, AWS Secrets Manager) via sidecar. |
| **Failure Recovery** | Debugging manual di live server, re-patching langsung. | Automated rollback berbasis health-check metric failures; redeploy image sebelumnya. |
| **Deploy Windows** | Menunggu jam sepi (tengah malam) karena butuh downtime. | Deployment kapan saja (siang hari) tanpa interupsi traffic (*Zero Downtime*). |

---

## 5. How (Workflow Detail)

Alur kerja delivery enterprise end-to-end:

```
[Developer]
    │  1. Push Feature Branch
    ▼
[Source Control (Git)]
    │  2. Open Pull Request to 'main'
    ▼
[CI Pipeline (Automated Gating)]
    ├─ Step A: Static Code Analysis & Linting
    ├─ Step B: Security Scanning (Trivy / Snyk: Secret Leaks, SAST)
    ├─ Step C: Automated Unit & Integration Tests
    ├─ Step D: Multi-stage Docker Build (Distroless / Non-root)
    └─ Step E: Vulnerability Scan pada OCI Image
    │
    ▼
[Artifact Registry]
    │  3. Push Signed Image (SHA Tagged)
    ▼
[Continuous Delivery Controller / GitOps]
    │  4. Detect New Release Manifest
    ▼
[Staging Environment]
    │  5. Automated Smoke Testing & Acceptance Check
    ▼
[Production Deployment Trigger]
    │  6. Manual Approval / Automated Policy Gate
    ▼
[Zero-Downtime Deployment (Canary/Blue-Green)]
    ├─ Initialize New Pods/Instances
    ├─ Readiness Probe Check (HTTP 200 OK)
    ├─ Shift Traffic: 10% ──► 50% ──► 100%
    └─ Drain Connections from Old Instances (Graceful SIGTERM Handling)
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem produksi sebagai **Sistem Pergantian Lokomotif Kereta Api Cepat**:

- **Cara Konvensional (Downtime)**: Kereta berhenti di tengah rel, semua penumpang diminta menunggu, lokomotif lama dicabut paksa, lokomotif baru dipasang, mesin distart, kereta kembali jalan. Jika lokomotif baru mogok, kereta terjebak di tengah jalan.
- **Cara Enterprise (Blue/Green & Canary)**: 
  Terdapat dua jalur rel paralel sebelum stasiun transfer. Kereta versi baru (Green) dipersiapkan dan diuji mesinnya di jalur cadangan hingga mencapai kecepatan sinkron. Wesel rel (Traffic Router) dialihkan secara mulus tanpa menghentikan laju gerbong. Penumpang tidak merasakan adanya sentakan atau penghentian transfer daya.

```
Rel Utama (Router/Ingress)
───────────────────┬───────────────────────────────
                   │
                   ├─ Wesel (90%) ──► [Rel Biru: App v1.0.0 (Aktif)]
                   │                  └─ Load: Normal
                   │
                   └─ Wesel (10%) ──► [Rel Hijau: App v1.1.0 (Canary)]
                                      └─ Telemetri: Engine Nominal
                                      (Jika mesin rusak ──► Wesel ditutup instan)
```

---

## 7. Simple Example & Practical Example

### Simple Example: Graceful Shutdown pada Node.js/Express
Aplikasi produksi wajib menangani signal `SIGTERM` dari orchestrator agar koneksi yang sedang diproses tidak terputus secara tiba-tiba (*dropped connection*).

```javascript
// server.js
const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

let isShuttingDown = false;

// Health check endpoint yang sadar lifecycle
app.get('/healthz', (req, res) => {
  if (isShuttingDown) {
    return res.status(503).json({ status: 'SHUTTING_DOWN' });
  }
  return res.status(200).json({ status: 'UP' });
});

app.get('/api/work', async (req, res) => {
  // Simulasi beban I/O
  setTimeout(() => {
    res.json({ result: 'success', timestamp: Date.now() });
  }, 2000);
});

const server = app.listen(PORT, () => {
  console.log(`Application started on port ${PORT}`);
});

// Handling termination signal dari orchestrator (Docker/Kubernetes)
process.on('SIGTERM', () => {
  console.warn('SIGTERM signal received: closing HTTP server gracefully.');
  isShuttingDown = true;

  // Stop accepting new connections, wait for existing connections to close
  server.close(() => {
    console.log('HTTP server closed. Exiting process.');
    process.exit(0);
  });

  // Force shutdown jika request menggantung melebihi grace period
  setTimeout(() => {
    console.error('Forced shutdown due to timeout.');
    process.exit(1);
  }, 10000);
});
```

### Practical Example: Enterprise Multi-Stage Dockerfile & CI/CD Pipeline

#### Production-Grade Dockerfile (`Dockerfile`)
Menggunakan distroless pattern, multi-stage caching, dan non-root security context.

```dockerfile
# ==========================================
# Stage 1: Build Dependencies & Binary
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /usr/src/app

# Leverage docker cache layers
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit

COPY . .
# Kompilasi TypeScript / asset bundling jika ada
# RUN npm run build

# Prune non-production dependencies
RUN npm prune --production

# ==========================================
# Stage 2: Minimalist Attack Surface Runtime
# ==========================================
FROM gcr.io/distroless/nodejs20-debian12:nonroot

WORKDIR /app

# Salin dependencies yang sudah dipangkas dan source code
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/package.json ./package.json
COPY --from=builder /usr/src/app/server.js ./server.js

# Metadata dokumentasi internal
EXPOSE 3000
ENV NODE_ENV=production

# Jalankan sebagai non-root user bawaan distroless (UID 65532)
USER nonroot

CMD ["server.js"]
```

#### Enterprise GitHub Actions CI Pipeline (`.github/workflows/production-pipeline.yml`)

```yaml
name: Enterprise Delivery Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

permissions:
  contents: read
  security-events: write
  packages: write

jobs:
  validate:
    name: Lint, Test & SAST Scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Runtime
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Execute Static Linting
        run: npm run lint --if-present

      - name: Execute Automated Unit Tests
        run: npm test --if-present

      - name: Run Secret Leak Scanning (TruffleHog)
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD

  build-and-scan:
    name: Build & Container Vulnerability Scan
    needs: validate
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.vars.outputs.sha_short }}
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Extract Short SHA
        id: vars
        run: echo "sha_short=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Container Image Locally
        uses: docker/build-push-action@v5
        with:
          context: .
          load: true
          tags: internal-registry.corp/app:${{ steps.vars.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Vulnerability Scanning (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: internal-registry.corp/app:${{ steps.vars.outputs.sha_short }}
          format: 'table'
          exit-code: '1' # Gagal jika ditemukan severity HIGH / CRITICAL
          ignore-unfixed: true
          severity: 'HIGH,CRITICAL'
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden Kegagalan Deployment FinTech Gateway (Black Friday)
- **Konteks**: Sebuah payment gateway memproses ~45.000 transaksi per detik (TPS). Pada saat event belanja tahunan, tim engineering merilis patch untuk optimalisasi koneksi database.
- **Masalah/Insiden**:
  1. Pipeline menggunakan tag `:latest` untuk update pod.
  2. Begitu container baru online, ia langsung menerima traffic sebelum koneksi database pool siap (*Readiness Probe tidak diimplementasikan dengan benar*).
  3. Signal handling diabaikan: Container lama langsung dimatikan secara paksa via `SIGKILL`, memutus ~12.000 transaksi in-flight yang sedang menunggu webhook dari bank provider.
  4. Muncul kaskade *database connection starvation*, memicu HTTP 502/504 secara global selama 14 menit.
- **Akar Masalah (Root Cause Analysis)**:
  - Tidak ada masa *preStop hook* dan penanganan `SIGTERM` secara graceful.
  - Ingress router mengarahkan traffic seketika ke pod baru tanpa health check berbasis verifikasi integrasi (*deep health check*).
  - Skema deployment menggunakan strategi *All-at-Once (Recreate)* alih-alih *Rolling Update/Canary*.
- **Solusi Rekayasa Berkelanjutan**:
  - Mengimplementasikan `readinessProbe` terpisah dari `livenessProbe`. Liveness hanya mengecek server hidup; Readiness mengecek kesiapan pool database.
  - Menambahkan `terminationGracePeriodSeconds: 60` pada orchestrator dan menyisipkan `preStop` sleep 5 detik untuk memberi waktu Ingress controller mencabut IP Pod dari daftar upstream routing sebelum aplikasi memproses termination.
  - Menetapkan strategi deployment Canary otomatis dengan batasan metrics: jika error rate HTTP 5xx naik > 0.05% selama 3 menit pertama, traffic otomatis diarahkan kembali ke versi sebelumnya (Automated Rollback).

---

## 9. Trade-offs

| Strategi Deployment | Keuntungan | Kerugian & Konsekuensi Teknis | Skenario Pemakaian Optimal |
| :--- | :--- | :--- | :--- |
| **Recreate (Downtime)** | Sederhana, tidak ada masalah kompatibilitas skema database antar-versi. | Terdapat service interruption (downtime); SLA availability turun. | Internal tooling, development environment, batch jobs. |
| **Rolling Update** | Zero downtime, konsumsi resource hemat (hanya butuh resource tambahan sesuai `maxSurge`). | Terdapat jeda waktu di mana versi lama (N) dan versi baru (N+1) berjalan berbarengan (skema DB harus backward-compatible). | API stateless standar, web microservices umum. |
| **Blue/Green** | Rollback instan (hanya toggle routing), isolasi pengujian versi Green di lingkungan produksi penuh sebelum live. | Menggandakan biaya infrastruktur (2x capacity saat fase transisi); stateful persistence rumit. | Sistem kritikal perbankan, aplikasi core monolith yang sulit berjalan multi-versi. |
| **Canary Release** | Mengurangi blast radius dampak bug pada user asli; validasi performa real-time dengan metrik empiris. | Kompleksitas tinggi pada routing mesh (Envoy/Traefik); tracing terdistribusi wajib aktif. | Sistem skala besar, payment switch, platform streaming. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Masalah: Pod/Container Terbunuh Tanpa Menyelesaikan Request (`Connection Dropped`)
- **Gejala**: Klien menerima HTTP 502 Bad Gateway saat proses deployment berjalan.
- **Penyebab**: Node.js/Go/Java process menerima `SIGTERM` dan langsung keluar (`process.exit(0)`), sementara Ingress/Load Balancer masih mengirimkan sisa traffic karena latensi sinkronisasi iptables/endpoint controller.
- **Solusi**:
  Gunakan lifecycle hook `preStop` untuk menunda penghentian proses selama beberapa detik hingga Ingress berhenti mengirim koneksi baru:
  ```yaml
  lifecycle:
    preStop:
      exec:
        command: ["/bin/sh", "-c", "sleep 5"]
  ```

### 2. Masalah: CrashLoopBackOff Akibat Salah Konfigurasi Probe
- **Gejala**: Aplikasi terus menerus restart segera setelah deploy.
- **Penyebab**: `livenessProbe` diarahkan ke endpoint yang terhubung ke database atau third-party API. Ketika database mengalami lonjakan beban sesaat, health check timeout dan orchestrator salah mengira aplikasi hang, lalu membunuh aplikasi secara berulang-ulang.
- **Solusi**:
  - `livenessProbe`: Verifikasi internal proses lokal saja (apakah runtime macet/deadlock). Jangan menyertakan downstream dependencies.
  - `readinessProbe`: Boleh memverifikasi dependensi downstream untuk menentukan apakah pod siap menerima traffic eksternal.

### 3. Masalah: Zombie Process dalam Kontainer
- **Gejala**: Memory usage perlahan naik (*leak*), jumlah PID pada host meningkat drastis.
- **Penyebab**: Aplikasi dijalankan sebagai PID 1 via shell form (`CMD npm start`) alih-alih exec form (`CMD ["node", "server.js"]`). Shell tidak mem-forward sinyal OS (seperti `SIGTERM`) ke child processes dan tidak melakukan reaping pada zombie processes.
- **Solusi**:
  Gunakan *Tini* sebagai init system mini atau jalankan biner aplikasi langsung menggunakan Exec syntax:
  ```dockerfile
  ENTRYPOINT ["/usr/bin/tini", "--"]
  CMD ["node", "server.js"]
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai kontrol gerbang rilis produksi:

- [ ] **Immutability**: Tag image container menggunakan Git SHA unik, dilarang keras menggunakan `:latest` di manifes produksi.
- [ ] **Least Privilege Access**: Container berjalan sebagai non-root (`USER 10001` atau `nonroot`), read-only root filesystem jika memungkinkan.
- [ ] **Resource Guardrails**: Wajib mendefinisikan *CPU Request/Limit* dan *Memory Request/Limit* untuk mencegah OOM cascade ke pod tetangga.
- [ ] **Probes Independence**: Pisahkan antara `livenessProbe` (proses internal) dan `readinessProbe` (konektivitas downstream).
- [ ] **Dual Signal Handling**: Aplikasi mengimplementasikan graceful drain untuk `SIGTERM` dengan limit waktu (*timeout guard*).
- [ ] **Secret Decoupling**: Tidak ada file credentials, token API, atau private key di dalam Dockerfile, image layer, maupun repositori Git.
- [ ] **Security Scanning**: Pipeline CI otomatis memblokir build jika Trivy mendeteksi CVE severity `CRITICAL` dengan exploit yang sudah tersedia.
- [ ] **Automated Observability**: Metrik golden signals (Latency, Traffic, Errors, Saturation) dipantau secara otomatis saat deployment berjalan.

---

## 12. Hands-on Practice

Buat direktori latihan lokal pada path: `hands-on/m02/`

### Struktur Direktori yang Dibuat
```
hands-on/m02/
├── app/
│   ├── package.json
│   └── server.js
├── nginx/
│   └── nginx.conf
├── Dockerfile
└── docker-compose.prod.yml
```

### Langkah 1: Siapkan File Aplikasi
Buat file `hands-on/m02/app/package.json`:
```json
{
  "name": "prod-ready-app",
  "version": "1.0.0",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.19.2"
  }
}
```

Buat file `hands-on/m02/app/server.js`:
```javascript
const express = require('express');
const app = express();
const PORT = 3000;
const VERSION = process.env.APP_VERSION || 'v1.0.0';

let isReady = false;

// Simulasi startup time (misal: inisialisasi koneksi DB)
setTimeout(() => {
  isReady = true;
  console.log(`[${VERSION}] Application is fully initialized and ready.`);
}, 4000);

app.get('/', (req, res) => {
  res.json({
    message: "Handled by production instance",
    version: VERSION,
    pid: process.pid
  });
});

app.get('/health/live', (req, res) => {
  res.status(200).send('OK');
});

app.get('/health/ready', (req, res) => {
  if (isReady) {
    return res.status(200).send('READY');
  }
  return res.status(503).send('INITIALIZING');
});

const server = app.listen(PORT, () => {
  console.log(`[${VERSION}] Listening on port ${PORT}`);
});

process.on('SIGTERM', () => {
  console.log(`[${VERSION}] SIGTERM received. Initiating graceful drain...`);
  isReady = false; // Gagalkan readiness probe segera
  server.close(() => {
    console.log(`[${VERSION}] All active requests resolved. Exiting.`);
    process.exit(0);
  });
});
```

### Langkah 2: Buat Production Dockerfile
Simpan pada `hands-on/m02/Dockerfile`:
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY app/package.json ./
RUN npm install --only=production

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/node_modules ./node_modules
COPY app/server.js app/package.json ./

USER node
EXPOSE 3000
CMD ["node", "server.js"]
```

### Langkah 3: Konfigurasi Dynamic Load Balancer (Nginx)
Simpan pada `hands-on/m02/nginx/nginx.conf`:
```nginx
events { worker_connections 1024; }

http {
    upstream backend_nodes {
        # Weighted routing untuk canary release
        server app_blue:3000 weight=9;
        server app_green:3000 weight=1;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend_nodes;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_connect_timeout 1s;
            proxy_read_timeout 2s;
        }
    }
}
```

### Langkah 4: Simulasikan Blue/Green Canary via Docker Compose
Simpan pada `hands-on/m02/docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  app_blue:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - APP_VERSION=BLUE-STABLE-v1.0.0
    restart: always

  app_green:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - APP_VERSION=GREEN-CANARY-v1.1.0
    restart: always

  gateway:
    image: nginx:alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "8080:80"
    depends_on:
      - app_blue
      - app_green
```

### Langkah 5: Eksekusi dan Verifikasi Traffic Shifting
Jalankan perintah berikut pada terminal:
```bash
cd hands-on/m02/
docker compose -f docker-compose.prod.yml up -d --build

# Uji loop traffic selama 10 request untuk membuktikan pembagian beban canary
for i in {1..10}; do
  curl -s http://localhost:8080/ | grep -o '"version":[^}]*'
done
```
*Ekspektasi Hasil*: Mayoritas respon berasal dari `BLUE-STABLE-v1.0.0` dan sesekali muncul respon dari `GREEN-CANARY-v1.1.0` (rasio 9:1).

---

## 13. Exercise

### Level Easy
Modifikasi file `hands-on/m02/nginx/nginx.conf` agar sistem beralih penuh (100%) ke `app_green` tanpa mematikan container `app_blue`, lalu jalankan `docker compose -f docker-compose.prod.yml exec gateway nginx -s reload`. Verifikasi tidak ada request yang gagal saat konfigurasi di-reload secara live.

### Level Medium
Tambahkan step vulnerability scanner lokal pada pipeline testing Anda menggunakan Docker CLI. Tuliskan command manual berbasis command line menggunakan container image `aquasec/trivy:latest` untuk memindai image aplikasi `hands-on/m02/Dockerfile` dan set output-nya agar mengembalikan *non-zero exit code* jika ditemukan kerentanan berstatus CRITICAL.

### Level Hard
Implementasikan skema *graceful database disconnection* pada `hands-on/m02/app/server.js`. Simulasikan koneksi database yang membutuhkan waktu 3 detik untuk flushing transaksi memori ke disk saat `SIGTERM` diterima. Pastikan endpoint `/health/ready` langsung mengembalikan `503` tepat saat sinyal masuk, namun proses HTTP server tetap melayani transaksi in-flight sampai batas maksimal 5 detik sebelum memanggil `process.exit(0)`.

---

## 14. Challenge

**Skenario Kasus Kompleks (Sistem Settlement Kliring E-Commerce)**:
Anda diminta merancang deployment workflow untuk aplikasi mikroservis backend finansial yang memproses rekonsiliasi database transaksi:
1. Layanan backend ini memiliki dependensi ketat terhadap schema database PostgreSQL.
2. Perubahan versi baru (v2.0.0) memecah kolom `full_name` menjadi dua kolom terpisah: `first_name` dan `last_name` (breaking schema migration).
3. Layanan tidak boleh mengalami downtime sedetik pun karena melayani API mitra 24/7.
4. Anda **tidak dapat** langsung menerapkan Blue/Green secara naif karena jika v1 dan v2 berjalan bersamaan pada satu database tanpa adaptasi, v1 akan error saat melakukan query database yang sudah diubah oleh migrasi v2.

**Tugas Anda**:
Rancang strategi deployment lengkap (dalam bentuk dokumen arsitektur dan urutan operasional/step-by-step) menggunakan metodologi **Expand and Contract (Parallel Run Database Refactoring)** yang mencakup:
- Strategi abstraksi skema database di level view/triggers atau dual-writing.
- Mekanisme Traffic Shifting bertahap di level API gateway.
- Prosedur rollback instan tanpa merusak data yang telah ditulis oleh versi v2 jika fase validasi canary gagal.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa penggunaan tag `:latest` pada kontainer dilarang keras di lingkungan produksi enterprise?
   - A. Karena ukuran image dengan tag latest selalu lebih besar.
   - B. Karena tag latest menghilangkan sifat deterministik dan reproduktibilitas rilis (*non-deterministic deployments*).
   - C. Karena Docker daemon menolak menjalankan image latest dalam mode swarm.
   - D. Karena tag latest otomatis menghapus layer cache pada Docker registry.

2. Sinyal sistem operasi standar yang dikirimkan oleh orchestrator (seperti Kubernetes atau Docker) ke proses kontainer untuk meminta terminasi secara halus adalah:
   - A. `SIGKILL` (Signal 9)
   - B. `SIGHUP` (Signal 1)
   - C. `SIGTERM` (Signal 15)
   - D. `SIGSTOP` (Signal 19)

3. Fitur kernel Linux yang bertugas membatasi konsumsi memori dan CPU agar sebuah kontainer tidak menghabiskan seluruh resource host server adalah:
   - A. Namespaces
   - B. Control Groups (cgroups)
   - C. AppArmor
   - D. OverlayFS

4. Apa fungsi dari endpoint `readinessProbe` yang membedakannya secara fungsional dari `livenessProbe`?
   - A. Memeriksa apakah kontainer harus segera di-restart oleh daemon.
   - B. Menentukan apakah kontainer sudah siap menerima aliran traffic dari load balancer/service.
   - C. Menghitung penggunaan I/O disk secara real-time.
   - D. Memeriksa integritas SHA checksum dari biner aplikasi.

5. Manakah format eksekusi instruksi `CMD` dalam Dockerfile yang benar agar aplikasi berjalan langsung sebagai PID 1 tanpa wrapper shell?
   - A. `CMD "node server.js"`
   - B. `CMD node server.js`
   - C. `CMD ["node", "server.js"]`
   - D. `CMD run ["node", "server.js"]`

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)

6. Apa bahaya utama menjalankan kontainer produksi menggunakan akun default `root` (UID 0)?
   - A. Aplikasi tidak dapat menulis log ke direktori `/var/log`.
   - B. Jika terjadi *container breakout* (eksploitasi celah runtime), penyerang langsung memiliki privilege root pada host OS.
   - C. Proses build kontainer akan memakan waktu dua kali lebih lama.
   - D. Memory allocation limit cgroups tidak dapat diterapkan pada UID 0.

7. Dalam strategi deployment **Canary**, metrik awal apa yang paling kritikal untuk dipantau secara otomatis sebelum memutuskan menaikkan traffic weight dari 5% ke 50%?
   - A. Durasi compile kode pada pipeline CI.
   - B. Utilisasi harddisk storage pada container registry.
   - C. HTTP 5xx error rate dan p99 latency regression pada target canary node.
   - D. Jumlah baris kode yang diubah pada commit git terkait.

8. Perhatikan konfigurasi lifecycle berikut:
   ```yaml
   lifecycle:
     preStop:
       exec:
         command: ["/bin/sh", "-c", "sleep 15"]
   ```
   Apa tujuan penyisipan perintah `sleep 15` tersebut saat fase terminasi pod?
   - A. Memberikan waktu bagi CPU untuk mendinginkan temperatur hardware host.
   - B. Menunda pengiriman sinyal SIGTERM ke aplikasi agar ingress router sempat memperbarui daftar routing dan tidak lagi mengirim traffic baru ke pod ini.
   - C. Memastikan cache memori RAM terhapus secara otomatis oleh kernel.
   - D. Mengulur waktu agar log tersinkronisasi ke server monitoring secara batch.

9. Teknik kompilasi multi-stage build pada Dockerfile enterprise terutama bertujuan untuk:
   - A. Mempercepat koneksi internet runner saat proses download.
   - B. Mengisolasi dependensi kompilasi/SDK berukuran besar agar tidak terbawa ke final runtime image yang minimalis dan aman.
   - C. Menghindari pembuatan commit git baru saat build gagal.
   - D. Mengubah aplikasi single-threaded menjadi multi-threaded secara otomatis.

10. Jika container log menunjukkan pesan `Killed` dan proses berhenti seketika dengan Exit Code `137`, penyebab paling mungkin adalah:
    - A. Aplikasi mengalami unhandled exception JavaScript/Go.
    - B. Kontainer dimatikan oleh OOM (Out Of Memory) Killer kernel karena melanggar batasan `memory limit`.
    - C. Pipeline CI menolak signature image Cosign.
    - D. Harddisk host penuh dan tidak dapat mengalokasikan inode.

---

### Bagian 3: Skenario Kasus Produksi (Analisis & Solusi)

#### Skenario 1: The Cascading Connection Pool Collapse
Setelah melakukan deploy rolling update pada mikroservis Authentication, tim DevOps mengamati bahwa pod baru gagal start secara acak, dan pod lama yang masih hidup mendadak ikut crash. Log aplikasi menunjukkan: `FATAL: remaining connection slots are reserved for non-replication superuser connections`. 

*Pertanyaan Skenario 1*:
Identifikasi kegagalan konfigurasi pada parameter deployment rolling update dan konfigurasi connection pool aplikasi tersebut. Bagaimana solusi teknis untuk memperbaikinya tanpa menambah kapasitas RAM database?

#### Skenario 2: The Stale Ingress Endpoint Bug
Sebuah aplikasi web e-commerce beralih dari container v1 ke v2 menggunakan strategi blue-green. Switch dilakukan via modifikasi DNS domain publik. Sebanyak 30% pelanggan dari penyedia ISP tertentu terus menerus melaporkan kegagalan login selama 4 jam pasca deployment, sementara pelanggan lain normal.

*Pertanyaan Skenario 2*:
Mengapa pendekatan blue/green via DNS routing rentan terhadap masalah ini, dan bagaimana arsitektur load balancer layer 7 yang seharusnya diterapkan untuk mitigasi insiden tersebut?

#### Skenario 3: The Untracked Supply-Chain Contamination
Sebuah vulnerability scan mendeteksi bahwa image container yang berjalan di cluster produksi mengandung malware kripto miner tersembunyi, padahal kode sumber di Git repo bersih dari kode mencurigakan. Setelah ditelusuri, image di-build menggunakan base image: `FROM node:alpine` tanpa hash SHA spesifik pada pipeline build yang berjalan otomatis 2 hari lalu.

*Pertanyaan Skenario 3*:
Jelaskan vektor kerentanan dari instruksi Dockerfile tersebut dan sebutkan 2 mekanisme preventif standar industri (supply chain security) yang wajib diterapkan pada pipeline CI/CD untuk mencegah masuknya compromised upstream dependencies.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Jawaban Basic
1. **B** — Tag `latest` bersifat mutable; image di baliknya dapat berubah sewaktu-waktu tanpa perubahan baris kode pada manifes deployment, merusak determinisme pelacakan bug dan rollback.
2. **C** — `SIGTERM` meminta proses melakukan cleanup secara tertib sebelum batas grace period habis dan dipaksa via `SIGKILL`.
3. **B** — `cgroups` (control groups) bertugas mengalokasikan dan membatasi resource perangkat keras (CPU, RAM, I/O) antar kumpulan proses.
4. **B** — `readinessProbe` mengontrol apakah pod menerima routing traffic jaringan. `livenessProbe` hanya mengontrol siklus hidup (restart) kontainer.
5. **C** — Syntax exec `["node", "server.js"]` menjalankan binary langsung tanpa perantara `/bin/sh`, sehingga aplikasi langsung menerima signal OS.

#### Kunci Jawaban Intermediate
6. **B** — Namespace isolasi kernel memiliki batasan; privilege root pada container memudahkan penyerang mengeksploitasi celah kernel untuk mengambil kendali host OS secara penuh.
7. **C** — Peningkatan error rate HTTP 5xx dan p99 latency adalah indikator empiris paling akurat adanya degradasi fungsional atau bottleneck performa pada rilis baru.
8. **B** — Propagasi pencabutan IP pod dari Ingress/Service endpoint butuh jeda waktu beberapa detik di layer jaringan. `preStop sleep` menjaga aplikasi tetap melayani request lama dan menolak koneksi baru sebelum aplikasi benar-benar exit.
9. **B** — Multi-stage builds memisahkan build environment (compiler, development headers) dari runtime minimal (hanya runtime engine dan binary), mereduksi ukuran attack surface dan CVE.
10. **B** — Exit Code 137 adalah `128 + 9 (SIGKILL)`. Umumnya dipicu oleh Linux OOM Killer ketika kontainer melanggar batasan `limits.memory`.

#### Panduan Jawaban Skenario Produksi

- **Solusi Skenario 1**:
  - *Akar Masalah*: Konfigurasi `maxSurge` pada rolling update memicu pembuatan instance pod baru sebelum instance lama dimatikan. Jika setiap pod mengalokasikan connection pool statis (misal 50 koneksi ke PostgreSQL) dan pod surge naik 50%, total koneksi serentak melampaui `max_connections` database.
  - *Perbaikan*: Terapkan connection pooling layer terpusat (seperti PgBouncer/ProxySQL) di depan database. Kurangi ukuran static connection pool per pod, atau set parameter rolling update dengan `maxSurge: 25%` dan `maxUnavailable: 25%` dengan memastikan kalkulasi batas maksimum koneksi seluruh instance pod tidak pernah melampaui kapasitas database connection pool.

- **Solusi Skenario 2**:
  - *Akar Masalah*: DNS-based traffic switching bergantung pada TTL (Time-To-Live). Sejumlah ISP atau recursive resolver publik mengabaikan setting TTL rendah dan melakukan caching DNS record selama berjam-jam (*DNS Stale Cache*).
  - *Perbaikan*: Jangan gunakan DNS record publik untuk beralih environment produksi. Gunakan reverse proxy statis layer 7 (seperti Envoy, HAProxy, AWS ALB, atau Cloudflare Load Balancing) di mana IP publik/DNS record tetap sama persis, dan proses perpindahan rute (switching upstream backend) dilakukan di layer reverse proxy secara internal via API atau configuration reload.

- **Solusi Skenario 3**:
  - *Akar Masalah*: Menggunakan tag mutable tanpa pinning hash (`node:alpine`) membuat build rentan terhadap *upstream poison attack* jika tag upstream di Docker Hub disusupi atau dimutasi oleh penyerang.
  - *Perbaikan*:
    1. Pinning Base Image menggunakan immutable digest SHA256 (contoh: `node:alpine@sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
    2. Implementasikan verifikasi tanda tangan digital artifak (seperti Cosign / Sigstore) pada pipeline CI/CD untuk memastikan hanya base image terverifikasi dari private mirror internal yang diizinkan untuk di-build.

---

## 16. Summary

1. **Prinsip Immutability**: Di lingkungan enterprise, software tidak pernah di-update secara live di target machine. Setiap perubahan menghasilkan artifak immutable yang ditandai dengan Git SHA unik dan dipromosikan melalui pipeline verifikasi otomatis.
2. **Graceful Degradation & Termination**: Aplikasi modern wajib menghormati siklus hidup OS. Penanganan sinyal `SIGTERM`, penyisipan lifecycle `preStop`, dan pemisahan logika `liveness` vs `readiness` adalah pondasi utama deployment tanpa downtime (*zero-downtime*).
3. **Isolasi Runtime**: Kontainer bukanlah VM independen, melainkan proses biasa yang diisolasi via Linux kernel *namespaces* dan dibatasi oleh *cgroups*. Menjalankan kontainer sebagai non-root dan membatasi attack surface via Distroless image adalah keharusan mutlak dalam keamanan platform.
4. **Traffic Gating Real-Time**: Menggunakan strategi deployment modern (Rolling Update, Blue/Green, Canary) membutuhkan observabilitas mendalam. Pilihan strategi harus mempertimbangkan konsekuensi kompatibilitas backward skema database dan overhead biaya infrastruktur.