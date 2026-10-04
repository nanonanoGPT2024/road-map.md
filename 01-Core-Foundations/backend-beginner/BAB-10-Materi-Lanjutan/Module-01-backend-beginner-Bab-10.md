## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** Backend Engineering Core
*   **Kategori:** 01-Core-Foundations
*   **Bab 10:** Containerization, Testing, & Enterprise Deployment
*   **Modul 01:** Dasar Containerization OCI, Multi-Stage Builds, dan Otomasi Pengujian Terisolasi
*   **Tingkat Kesulitan:** Beginner to Intermediate
*   **Prasyarat:** Pemahaman HTTP API dasar, Git version control, Linux CLI dasar (POSIX permissions, sinyal proses OS), dan dasar pengujian unit (Unit Testing).
*   **Estimasi Durasi:** 4 - 6 Jam Pembelajaran Mandiri / Workshop

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis** arsitektur kontainer OCI (*Open Container Initiative*) hingga ke level primitif kernel Linux (*namespaces*, *cgroups*, dan *copy-on-write filesystem*).
2.  **Merancang dan Mengimplementasikan** `Dockerfile` berbasis *multi-stage builds* yang mengisolasi tahapan kompilasi, eksekusi unit test, dan runtime produksi minimal.
3.  **Mengintegrasikan** pengujian otomatis (*unit & integration test*) ke dalam *lifecycle* pembentukan kontainer guna menjamin hanya artifak yang lolos uji yang dapat masuk ke tahap *deployment*.
4.  **Mengonfigurasi** kontainer runtime yang aman dengan menerapkan prinsip *least privilege* (eksekusi *non-root user*), penanganan sinyal POSIX (`SIGTERM`/`SIGKILL`) untuk *graceful shutdown*, dan *health checks*.
5.  **Mendiagnosis** dan mengoptimalkan ukuran image, efisiensi layer caching, serta memitigasi kebocoran rahasia (*build-time secrets*) pada artifak final.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Primitif Kernel Linux]
  ├── Namespaces (Isolasi: PID, NET, MNT, IPC, UTS, USER)
  ├── Control Groups / cgroups (Batasan: CPU, Memory, I/O)
  └── OverlayFS (Layered CoW Filesystem)
           │
           ▼
[OCI Image & Runtime Specification]
  ├── Base Engine (dockerd / containerd / runc)
  ├── Dockerfile DSL & Layer Caching Strategy
  └── Root Filesystem (rootfs)
           │
           ▼
[Multi-Stage Build Pipeline]
  ├── Stage 1: Build & Dependency Resolution
  ├── Stage 2: Automated Testing (Linting, Unit, Static Analysis)
  └── Stage 3: Minimal Production Image (Distroless / Scratch / Alpine)
           │
           ▼
[Enterprise Runtime Readiness]
  ├── Non-Root User Execution
  ├── PID 1 Signal Handling (Tini / dumb-init / Native Init)
  ├── Native Healthchecks (HEALTHCHECK instruction)
  └── Environment & Secret Decoupling (12-Factor App)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Masalah klasik terbesar dalam rekayasa backend enterprise adalah disparitas lingkungan: *"It works on my machine, but it fails in staging/production"*. Ketidakkonsistenan versi library runtime, dependensi sistem operasi tingkat rendah (*glibc*, *libssl*), perbedaan konfigurasi zona waktu, hingga konfigurasi jaringan lokal menyebabkan bug kritis saat aplikasi dirilis ke server produksi.

Containerization menyelesaikan determinisme lingkungan runtime dengan memaketkan aplikasi beserta seluruh pohon dependensinya ke dalam satu unit biner yang terisolasi. Namun, penggunaan kontainer yang salah (seperti menyatukan compiler, toolchain pengujian, dan kredensial ke dalam satu image produksi yang berjalan dengan hak akses `root`) justru menciptakan celah keamanan masif dan ukuran image raksasa yang memperlambat proses *Continuous Integration / Continuous Delivery* (CI/CD).

Mempelajari cara membangun kontainer minimalis yang menggabungkan pengujian otomatis dalam *pipeline multi-stage* memastikan bahwa setiap artifak yang dihasilkan:
1. Terbukti lolos seluruh uji validasi kode.
2. Bebas dari *attack surface* yang tidak perlu (tidak memuat compiler, shell, atau debugging tools di produksi).
3. Dapat diskalakan secara horizontal dalam hitungan detik dengan konsumsi sumber daya CPU dan memori yang optimal.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Kontainer vs Virtual Machine
Virtual Machine (VM) mengabstraksi perangkat keras fisik menggunakan *Hypervisor* (Type 1 atau Type 2). Setiap VM menjalankan *Guest OS* lengkap dengan kernel, memory manager, dan sistem berkasnya sendiri, yang menyebabkan overhead memori tinggi (ratusan megabyte hingga gigabyte) serta waktu *booting* lambat.

Kontainer adalah abstraksi pada lapisan aplikasi (*user-space*). Seluruh kontainer berbagi (*share*) satu kernel dari *Host OS*. Kontainer hanyalah sebuah proses reguler Linux yang diberikan batasan batas pandang (*isolation boundary*) melalui *namespaces* dan kuota penggunaan sumber daya melalui *cgroups*.

### 2. Primitif Kernel Penopang Kontainer
*   **Linux Namespaces:** Membatasi apa yang dapat *dilihat* oleh sebuah proses:
    *   `PID`: Isolasi pohon proses (proses di dalam kontainer melihat dirinya sebagai PID 1).
    *   `NET`: Isolasi antarmuka jaringan, rute, dan port binding.
    *   `MNT`: Isolasi mount point sistem berkas.
    *   `IPC`: Isolasi komunikasi antar-proses (System V IPC, POSIX message queues).
    *   `UTS`: Isolasi hostname dan nama domain.
    *   `USER`: Isolasi pemetaan UID/GID pengguna.
*   **Control Groups (cgroups v1/v2):** Membatasi berapa banyak *sumber daya* yang dapat digunakan (CPU quota, memory hard/soft limits, block I/O throughput).
*   **OverlayFS (Union File System):** Menggabungkan beberapa direktori menjadi satu mount point virtual. Lapisan image kontainer bersifat *read-only* (`lowerdir`), sedangkan kontainer yang berjalan mendapatkan satu lapisan tipis yang bersifat *read-write* (`upperdir`).

### 3. Multi-Stage Builds
Fitur Dockerfile yang memungkinkan pembuatan beberapa *stages* sementara dalam satu file deklaratif. File biner hasil kompilasi atau laporan pengujian dapat disalin dari satu stage ke stage berikutnya, sementara perkakas pembangunan (*build tools*) dibuang, menghasilkan image akhir dengan ukuran sangat kecil.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Lifecycle Pembuatan Image dan Layer Caching
Setiap instruksi dalam `Dockerfile` (`FROM`, `COPY`, `RUN`, `ENV`) menghasilkan layer *read-only* baru di dalam *image storage driver* (seperti `overlay2`). 
Docker menggunakan algoritma *cache invalidation*:
1. Docker memeriksa instruksi yang dieksekusi terhadap cache lokal.
2. Jika instruksi belum berubah dan file yang disalin melalui `COPY` memiliki hash checksum yang identik, Docker menggunakan layer cache yang ada.
3. Begitu satu layer kehilangan cache (misalnya source code berubah), **seluruh layer setelahnya wajib dieksekusi ulang dari awal**.
4. *Aturan Emas:* Letakkan instruksi yang jarang berubah (seperti instalasi dependensi pihak ketiga) di urutan awal, dan letakkan instruksi yang sering berubah (seperti penyalinan source code aplikasi) di urutan paling akhir.

### 2. Eksekusi Pengujian Terintegrasi (Test-Gated Build)
Dengan *multi-stage builds*, kita dapat menyisipkan stage `testrunner` sebelum stage rilis. 
* Target build dapat dipecah menjadi:
  * Stage 1: `base` (resolusi dependensi)
  * Stage 2: `tester` (menjalankan linter, unit test, race detector)
  * Stage 3: `builder` (kompilasi kode ke binary)
  * Stage 4: `production` (penyalinan biner dari `builder`, menggunakan image distroless/scratch)
* Jika unit test pada Stage 2 gagal (mengembalikan exit code non-zero), proses build Docker akan terhenti seketika (*fail-fast*), dan image produksi tidak akan pernah dibuat.

### 3. Penanganan PID 1 dan Sinyal POSIX
Ketika sistem orkestrasi (seperti Kubernetes atau Docker Compose) menghentikan kontainer, sistem akan mengirimkan sinyal `SIGTERM`, menunggu selama *grace period* (default 10-30 detik), lalu mengirimkan `SIGKILL` jika proses belum mati.
* Jika aplikasi backend Anda dieksekusi menggunakan format shell (`CMD node index.js` atau `CMD npm start`), shell (`/bin/sh`) akan berjalan sebagai PID 1.
* Secara default, shell standar Linux **tidak meneruskan sinyal POSIX** ke proses anak (*child process*).
* Akibatnya, koneksi database yang sedang aktif akan diputus secara paksa oleh `SIGKILL`, menyebabkan korupsi data atau *request dropped*.
* *Solusi:* Gunakan format exec (`CMD ["./server"]`) atau perkakas init seperti `tini` / `dumb-init`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Perbandingan Virtual Machine vs Linux Container

```
+------------------------------------+      +------------------------------------+
|         VIRTUAL MACHINE            |      |          LINUX CONTAINER           |
+------------------------------------+      +------------------------------------+
| [App 1]           | [App 2]        |      | [App 1]           | [App 2]        |
| Libs / Binaries   | Libs / Binaries|      | Libs / Binaries   | Libs / Binaries|
+-------------------+----------------+      +-------------------+----------------+
| Guest OS 1        | Guest OS 2     |      | Namespaces & Cgroups Isolation     |
| (Kernel, Drivers) | (Kernel, Driv) |      +------------------------------------+
+-------------------+----------------+      |         Container Engine           |
|         Hypervisor (KVM/ESXi)      |      |      (containerd / runc)           |
+------------------------------------+      +------------------------------------+
|          Host Operating System     |      |        Shared Host Kernel          |
+------------------------------------+      +------------------------------------+
|         Physical Hardware          |      |         Physical Hardware          |
+------------------------------------+      +------------------------------------+
```

### Pipeline Multi-Stage Build & Test-Gated Deployment

```
   Dockerfile Workflow
   ===================
   
   +---------------------------------------+
   | Stage 1: base-deps                    |
   | - Unduh package manager manifests     |
   | - Download vendor dependencies        |
   +---------------------------------------+
                       |
         +-------------+-------------+
         |                           |
         v                           v
+------------------+       +-------------------+
| Stage 2: builder |       | Stage 3: test     |
| - Kompilasi kode |       | - Jalankan Linter |
| - Optimasi biner |       | - Jalankan Test   |
+------------------+       +-------------------+
         |                           |
         |                     [Test Lolos?]
         |                     /           \
         |                YA  /             \  TIDAK
         |                   v               v
         |         +-----------------+   +---------------------+
         +-------->| Stage 4: runner |   | ABORT BUILD!        |
                   | - Scratch/Distro|   | Exit Code != 0      |
                   | - Non-root User |   | Image Batal Dibuat  |
                   | - Binary Saja   |   +---------------------+
                   +-----------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah struktur dasar `Dockerfile` multi-stage untuk aplikasi backend sederhana (menggunakan Go sebagai representasi kompilasi biner statis) yang menerapkan isolasi dan build minimalis.

### Struktur Proyek
```
minimal-app/
├── go.mod
├── main.go
└── Dockerfile
```

### File: `main.go`
```go
package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Enterprise Containerization Baseline"))
	})

	fmt.Printf("Server listening on port %s\n", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		fmt.Printf("Fatal server error: %v\n", err)
		os.Exit(1)
	}
}
```

### File: `Dockerfile`
```dockerfile
# Stage 1: Build stage
FROM golang:1.22-alpine AS builder

WORKDIR /src

# Manfaatkan caching layer dengan menyalin manifes modul terlebih dahulu
COPY go.mod ./
# Jalankan download dependensi (jika ada go.sum)
RUN go mod download

# Salin source code
COPY main.go .

# Kompilasi statis (CGO_ENABLED=0 murni Go, menghapus dependensi glibc)
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -ldflags="-w -s" -o /bin/api-server .

# Stage 2: Runtime stage menggunakan scratch (image kosong 0 MB)
FROM scratch

# Salin file binary dari stage builder
COPY --from=builder /bin/api-server /api-server

# Deklarasi port yang diekspos
EXPOSE 8080

# Jalankan server langsung sebagai PID 1 dalam bentuk exec form
ENTRYPOINT ["/api-server"]
```

### Perintah Build & Eksekusi:
```bash
# Build image
docker build -t minimal-app:v1 .

# Periksa ukuran image (biasanya < 10 Megabyte)
docker images minimal-app:v1

# Jalankan kontainer
docker run -d --rm -p 8080:8080 --name minimal-instance minimal-app:v1

# Verifikasi
curl http://localhost:8080/healthz
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kita akan membangun implementasi enterprise untuk aplikasi backend Node.js / TypeScript. Skenario ini mencakup:
1. Multi-stage build dengan dependensi dev vs prod.
2. Penegakan pengujian otomatis (*unit test*) di dalam pipeline build.
3. Eksekusi menggunakan user non-root kustom (`node` user ID 1000).
4. Penanganan *Graceful Shutdown* menggunakan `dumb-init`.
5. Orkestrasi pengujian integrasi database menggunakan `docker-compose`.

### Struktur Direktori
```
enterprise-backend/
├── .dockerignore
├── docker-compose.test.yml
├── Dockerfile
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts
│   └── math.ts
└── tests/
    └── math.test.ts
```

### File: `package.json`
```json
{
  "name": "enterprise-backend",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "test": "ts-node tests/math.test.ts",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "express": "^4.19.2"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/node": "^20.11.24",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

### File: `src/math.ts`
```typescript
export function calculateTax(amount: number, rate: number): number {
  if (amount < 0 || rate < 0) {
    throw new Error("Invalid parameters: values must be non-negative");
  }
  return amount * rate;
}
```

### File: `tests/math.test.ts`
```typescript
import { calculateTax } from "../src/math";

function runTests() {
  console.log("[TEST] Running automated unit tests...");
  
  const result = calculateTax(100, 0.11);
  if (Math.abs(result - 11) > 0.0001) {
    console.error(`[FAIL] Expected 11, got ${result}`);
    process.exit(1);
  }

  try {
    calculateTax(-10, 0.1);
    console.error("[FAIL] Expected error on negative parameters, but none was thrown");
    process.exit(1);
  } catch (err) {
    // Berhasil jika error terlempar
  }

  console.log("[PASS] All unit tests passed successfully.");
  process.exit(0);
}

runTests();
```

### File: `src/index.ts`
```typescript
import express, { Request, Response } from "express";
import { calculateTax } from "./math";

const app = express();
const PORT = process.env.PORT || 3000;

app.get("/healthz", (_req: Request, res: Response) => {
  res.status(200).json({ status: "healthy", timestamp: new Date().toISOString() });
});

app.get("/tax", (req: Request, res: Response) => {
  const amount = parseFloat(req.query.amount as string || "0");
  const rate = parseFloat(req.query.rate as string || "0.11");
  
  try {
    const tax = calculateTax(amount, rate);
    res.json({ amount, rate, tax });
  } catch (error: any) {
    res.status(400).json({ error: error.message });
  }
});

const server = app.listen(PORT, () => {
  console.log(`[RUNTIME] Process running under PID: ${process.pid}`);
  console.log(`[RUNTIME] Server listening on port ${PORT}`);
});

// Penanganan Graceful Shutdown
function gracefulShutdown(signal: string) {
  console.log(`[SHUTDOWN] Received ${signal}. Closing HTTP server gracefully...`);
  server.close(() => {
    console.log("[SHUTDOWN] HTTP server closed. Releasing resources (DB pools, sockets)...");
    process.exit(0);
  });

  // Force close jika proses cleanup melebihi batas waktu 10 detik
  setTimeout(() => {
    console.error("[SHUTDOWN] Timeout forced termination!");
    process.exit(1);
  }, 10000);
}

process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
process.on("SIGINT", () => gracefulShutdown("SIGINT"));
```

### File: `.dockerignore`
```
node_modules
dist
.git
.gitignore
npm-debug.log
Dockerfile*
docker-compose*
README.md
```

### File: `Dockerfile` (Enterprise Multi-Stage Build)
```dockerfile
# ------------------------------------------------------------------------------
# Stage 1: Dependencies Resolution
# ------------------------------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app

# Memasang libc6-compat jika ada native addons alpine
RUN apk add --no-cache libc6-compat

# Copy manifests terlebih dahulu untuk efisiensi layer caching
COPY package.json package-lock.json* ./
RUN npm ci

# ------------------------------------------------------------------------------
# Stage 2: Testing Phase (Gatekeeper)
# ------------------------------------------------------------------------------
FROM node:20-alpine AS tester
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Jalankan pengujian unit. Jika gagal, build kontainer otomatis dibatalkan!
RUN npm run test

# ------------------------------------------------------------------------------
# Stage 3: Source Compilation
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Kompilasi TypeScript ke JavaScript murni di folder /app/dist
RUN npm run build

# Pangkas node_modules hanya untuk dependensi produksi guna menghemat ukuran
RUN npm prune --production

# ------------------------------------------------------------------------------
# Stage 4: Production Runtime
# ------------------------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

# Konfigurasi Environment Produksi
ENV NODE_ENV=production
ENV PORT=3000

# Install dumb-init untuk menangani PID 1 signal forwarding
RUN apk add --no-cache dumb-init

# Terapkan prinsip Least Privilege: Jalankan proses sebagai non-root
USER node

# Copy artifak runtime yang dibutuhkan saja dari stages sebelumnya
COPY --chown=node:node package.json ./
COPY --chown=node:node --from=builder /app/node_modules ./node_modules
COPY --chown=node:node --from=builder /app/dist ./dist

# Healthcheck bawaan Docker untuk mendeteksi container hang
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/healthz || exit 1

EXPOSE 3000

# Bungkus eksekusi Node.js dengan dumb-init
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["node", "dist/index.js"]
```

### File: `docker-compose.test.yml` (Untuk Otomasi CI Integration Test)
```yaml
version: '3.8'

services:
  # Service yang menguji apakah build target 'tester' sukses dieksekusi
  unit-test-runner:
    build:
      context: .
      dockerfile: Dockerfile
      target: tester
    container_name: test-runner-stage

  # Service production instance hasil akhir
  backend-service:
    build:
      context: .
      dockerfile: Dockerfile
      target: runner
    container_name: production-ready-backend
    ports:
      - "3000:3000"
    environment:
      - PORT=3000
    depends_on:
      unit-test-runner:
        condition: service_completed_successfully
```

### Langkah Pengujian dan Pembuktian Eksekusi:
```bash
# 1. Jalankan pipeline via Docker Compose
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# 2. Uji endpoint runtime (di terminal lain)
curl -i http://localhost:3000/tax?amount=500&rate=0.11

# 3. Uji graceful shutdown
# Kirim sinyal SIGTERM ke kontainer yang berjalan
docker stop --time=5 production-ready-backend
# Amati log: Pesan SIGTERM akan diterima oleh Node.js berkat dumb-init
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektur | Opsi A: Monolithic Single-Stage Image | Opsi B: Multi-Stage (Alpine / Distroless) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Ukuran Image (Disk & Registry Network)** | **Buruk:** Berukuran 800MB - 1.5GB karena memuat compiler, devDependencies, cache OS. | **Sangat Baik:** Berukuran 20MB - 120MB. Sangat cepat didistribusikan ke cluster produksi. | Single-stage memperlambat waktu *scale-out* dan deployment CI/CD secara eksponensial. |
| **Keamanan & Attack Surface** | **Tinggi Risiko:** Mengandung package manager (`apk`, `apt`), build tools (`gcc`, `python`), dan shell (`sh`, `bash`). | **Minimal:** Hanya memuat dependensi biner aplikasi runtime. Tool hacker tidak tersedia. | Jika image ditembus, penyerang tidak memiliki native utility bawaan untuk eskalasi hak akses. |
| **Kemudahan Debugging Lokal** | **Mudah:** Administrator dapat menggunakan `docker exec -it <id> sh` untuk inspect direktori. | **Sulit:** Image Distroless/Scratch tidak memiliki shell sama sekali. | Butuh observabilitas eksternal (tracing, structured logging) atau ephemeral debug container. |
| **Kompatibilitas Library (C-Bindings)** | **Tinggi:** Debian/Ubuntu menggunakan `glibc` standar. Hampir semua modul native langsung jalan. | **Moderat:** Alpine menggunakan `musl-libc`. Beberapa pustaka native (e.g. `sharp`, `grpc`) butuh kompilasi ulang. | Harus memvalidasi kompatibilitas driver native C sebelum memilih Alpine Linux sebagai base. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Format JSON Exec Form pada ENTRYPOINT & CMD:**
    *   *Salah:* `CMD npm start` atau `CMD node index.js` (Membuat subshell `/bin/sh -c`, merusak penerusan sinyal).
    *   *Benar:* `CMD ["node", "dist/index.js"]` atau `ENTRYPOINT ["/usr/bin/dumb-init", "--", "node", "dist/index.js"]`.
2.  **Kunci Versi Base Image secara Deterministik:**
    *   *Salah:* `FROM node:latest` atau `FROM alpine:latest`.
    *   *Benar:* `FROM node:20.11.1-alpine3.19` atau pin menggunakan image SHA256 digest (`node@sha256:abc123...`).
3.  **Wajib Terapkan Non-Root User:**
    Secara default, kontainer berjalan sebagai `root` (UID 0). Jika terjadi *container breakout*, penyerang memiliki hak akses `root` terhadap kernel host. Selalu ganti user menggunakan direktif `USER <non-root-uid>`.
4.  **Optimalkan Penyusunan Layer untuk Caching:**
    Salin file dependensi manifes terlebih dahulu (`package.json`, `go.mod`, `pom.xml`), jalankan proses instalasi dependensi, baru kemudian salin source code aplikasi.
5.  **Gunakan File `.dockerignore` Komprehensif:**
    Cegah folder lokal seperti `node_modules`, `.git`, temporary logs, file `.env` rahasia agar tidak masuk ke context build Docker daemon.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menyematkan Kredensial / Secret di dalam Instruksi RUN atau ENV
```dockerfile
# KESALAHAN FATAL: Secret tetap tersimpan permanen di riwayat layer metadata image!
ENV GITHUB_TOKEN=ghp_secretToken12345
RUN git clone https://$GITHUB_TOKEN@github.com/corp/private-repo.git

# SOLUSI: Gunakan BuildKit Secret Mounts yang tidak meninggalkan jejak layer
# syntax=docker/dockerfile:1.2
RUN --mount=type=secret,id=gh_token \
    GITHUB_TOKEN=$(cat /run/secrets/gh_token) git clone ...
```

### 2. Membiarkan Zombie Processes Berkembang
Ketika kontainer Node.js atau Python mengeksekusi child process dan child tersebut mati, proses anak tersebut berubah menjadi status *zombie*. Proses PID 1 bertanggung jawab melakukan *reaping* (panen) status exit child process. Jika PID 1 dipegang oleh runtime yang tidak didesain sebagai init system (seperti Node.js standar), memori tabel proses OS akan bocor secara perlahan. Gunakan init mini seperti `tini` atau `dumb-init`.

### 3. Menggabungkan Testing Luar Kontainer dengan Asumsi Lingkungan Kontainer
Menjalankan `npm test` di host machine pengembang (macOS/Windows) kemudian langsung mem-build Dockerfile tanpa testing ulang di Linux environment sering memunculkan bug dependensi (seperti *case sensitivity* path sistem berkas Linux vs macOS). Selalu sediakan stage testing langsung di dalam Dockerfile.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Diagnostik Caching Dockerfile (Tingkat: Rendah)
Diberikan sebuah `Dockerfile` yang tidak efisien:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
```
**Tugas Anda:** 
1. Ubah urutan instruksi di atas agar perubahan pada satu baris kode di `app.py` tidak memicu eksekusi ulang perintah `pip install`.
2. Tambahkan deklarasi `.dockerignore` untuk memastikan environment lokal `.venv/` tidak tertimpa ke dalam container.

### Latihan 2: Implementasi Fail-Fast Test Stage (Tingkat: Menengah)
1. Buat sebuah proyek sederhana dengan satu fungsi utilitas dan satu berkas unit test.
2. Buat `Dockerfile` multi-stage yang memiliki stage `test`.
3. Sengaja buat pengujian unit Anda gagal (*intentional assertion failure*).
4. Buktikan melalui command line bahwa perintah `docker build --target runner .` akan mengembalikan error *non-zero* dan image runner tidak tercipta di *local storage*.

### Latihan 3: Signal Interception Verification (Tingkat: Menengah-Tinggi)
1. Tulis skrip backend pendek yang mencetak log `"Proses dibersihkan"` saat menangkap sinyal `SIGTERM`.
2. Bungkus ke dalam kontainer tanpa *init tool* dan jalankan via `CMD node app.js` (exec form vs shell form).
3. Jalankan `docker stop <nama-kontainer>` dan hitung durasi penghentian menggunakan perintah `time`.
4. Jika durasi penghentian tepat 10 detik, berarti aplikasi Anda mengabaikan `SIGTERM` dan dimatikan paksa oleh `SIGKILL`. Perbaiki hingga durasi penghentian menjadi instan (< 1 detik).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa fungsi utama dari kernel primitive *cgroups* dalam teknologi kontainer?**
   * A. Mengisolasi antarmuka jaringan dan port binding.
   * B. Mengatur batasan konsumsi sumber daya fisik seperti CPU quota, alokasi Memory, dan batas I/O.
   * C. Mengizinkan kontainer mengakses filesystem host secara langsung tanpa permission check.
   * D. Menyembunyikan nama user host dari kontainer.
   * *Jawaban:* **B**. *Namespaces* bertugas untuk isolasi batas pandang, sedangkan *cgroups* membatasi utilisasi sumber daya komputasi.

2. **Mengapa instruksi `COPY . .` yang diletakkan sebelum instalasi dependensi dianggap sebagai *anti-pattern*?**
   * A. Karena membuat ukuran image menjadi dua kali lipat lebih besar.
   * B. Karena merusak layer cache Docker; setiap modifikasi kecil pada kode sumber akan memaksa Docker mengunduh ulang seluruh pustaka dependensi.
   * C. Karena dilarang oleh spesifikasi OCI.
   * D. Karena file executable binaries tidak dapat disalin menggunakan instruksi `COPY`.
   * *Jawaban:* **B**. Docker membaca perubahan file berdasarkan checksum; menyalin file yang sering berubah di awal membatalkan cache instruksi berikutnya.

3. **Apa bahaya keamanan utama menjalankan proses kontainer dengan identitas default `root` (UID 0)?**
   * A. Kontainer tidak dapat mengakses jaringan luar.
   * B. Jika terjadi kerentanan *container breakout*, proses jahat akan memperoleh hak istimewa *root* penuh pada kernel Host OS.
   * C. Docker daemon akan menolak menjalankan kontainer tersebut di lingkungan cloud.
   * D. Port di atas 1024 tidak dapat dibuka oleh root.
   * *Jawaban:* **B**. Identitas root di dalam kontainer secara default berkorespondensi dengan UID 0 pada kernel Host kecuali fitur *user namespace remapping* diaktifkan secara spesifik.

4. **Bagaimana format instruksi `CMD` yang benar agar sinyal sistem operasi diteruskan langsung ke proses aplikasi tanpa melalui sub-shell?**
   * A. `CMD ./start.sh`
   * B. `CMD "node index.js"`
   * C. `CMD ["node", "index.js"]`
   * D. `CMD: run node index.js`
   * *Jawaban:* **C**. Format tanda kurung siku (JSON array / *exec form*) menjalankan biner secara langsung sebagai PID 1 tanpa mengeksekusi shell wrapper `/bin/sh -c`.

5. **Apa keuntungan arsitektur dari *Multi-Stage Build* ditinjau dari sisi keamanan perangkat lunak (*software supply chain*)?**
   * A. Menghapus kebutuhan akan image registry.
   * B. Mengeliminasi build tools, package managers, dan header files dari artifak akhir yang dirilis ke produksi, secara signifikan memperkecil luas permukaan serangan (*attack surface*).
   * C. Menghilangkan kebutuhan untuk melakukan penulisan unit testing.
   * D. Mengizinkan kontainer berjalan tanpa kernel Linux.
   * *Jawaban:* **B**. Penyerang tidak dapat memanfaatkan compiler atau build tools untuk mengompilasi exploit jika tool tersebut tidak ada di dalam image runtime produksi.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Spesifikasi Industri & Standar:**
    *   *Open Container Initiative (OCI) Image and Runtime Specification:* [opencontainers.org](https://opencontainers.org/)
    *   *The Twelve-Factor App Principles:* Modul Build, Release, Run & Dev/Prod Parity ([12factor.net](https://12factor.net/))
*   **Buku Standar Backend & DevOps:**
    *   *Docker Deep Dive* oleh Nigel Poulton.
    *   *Container Security: Fundamental Technology Concepts that Protect Containerized Applications* oleh Liz Rice.
*   **Dokumentasi Resmi:**
    *   Docker Engine Documentation: *Dockerfile Best Practices* ([docs.docker.com/develop/develop-images/dockerfile_best-practices/](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/))
    *   Google Container Tools: *Distroless Images Architecture* ([github.com/GoogleContainerTools/distroless](https://github.com/GoogleContainerTools/distroless))

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  Kontainer bukanlah virtual machine; kontainer adalah proses sistem operasi Linux yang diisolasi menggunakan **namespaces** (visibilitas) dan dibatasi oleh **cgroups** (sumber daya), dengan sistem berkas berbasis lapisan bertumpuk (**OverlayFS**).
2.  Penggunaan **Multi-Stage Builds** memungkinkan segregasi tegas antara fase penyusunan dependensi, validasi pengujian (*test gating*), dan runtime akhir. Ini menghasilkan ukuran image minimal dan menghilangkan *toolchain* yang rentan dieksploitasi.
3.  **Eksekusi pengujian otomatis** di dalam tahapan Dockerfile menjamin integritas artifak: proses pembuatan image akan dibatalkan seketika jika kode tidak lolos standardisasi linting atau pengujian unit.
4.  Standarisasi kontainer backend enterprise menuntut penerapan prinsip **Least Privilege** (menggunakan user *non-root*) dan penanganan sinyal terminasi sistem operasi yang tepat via **exec form** atau wrapper init (`dumb-init`/`tini`) demi menjamin siklus *graceful shutdown* yang aman dari korupsi data.

---

## SEKSI 17 — GLOSARIUM

*   **OCI (Open Container Initiative):** Badan standarisasi industri independen yang mengatur format image kontainer dan runtime terpadu.
*   **Namespace:** Fitur kernel Linux yang mengisolasi sumber daya sistem tertentu sehingga sebuah proses hanya dapat melihat alokasi miliknya sendiri (misal PID, Jaringan, Mount).
*   **Control Group (cgroup):** Fitur kernel Linux yang bertugas menghitung dan membatasi konsumsi sumber daya fisik (CPU, Memori, I/O) sekelompok proses.
*   **OverlayFS:** Tipe file system yang mengombinasikan beberapa direktori menjadi satu tampilan terpadu (*union mount*), yang digunakan untuk membentuk layer-layer kontainer.
*   **Multi-Stage Build:** Pola deklarasi Dockerfile yang mendefinisikan beberapa target build sementara guna menyaring hanya artifak penting yang dimasukkan ke image akhir.
*   **Exec Form:** Sintaks penulisan instruksi Dockerfile menggunakan array JSON `["biner", "arg1"]` yang memicu eksekusi langsung tanpa spawning shell wrapper.
*   **Shell Form:** Sintaks penulisan instruksi berupa string biasa `CMD biner arg1`, yang secara implisit dieksekusi sebagai parameter `/bin/sh -c`.
*   **Graceful Shutdown:** Mekanisme penutupan aplikasi secara bersih dengan cara berhenti menerima koneksi baru, menyelesaikan transaksi yang tersisa, dan menutup file descriptor atau koneksi database sebelum proses mati.
*   **Distroless:** Image kontainer minimalis yang hanya berisi aplikasi Anda dan dependensi runtime-nya, tanpa menyertakan package manager, shell, atau utilitas OS Linux standar lainnya.
*   **Zombie Process:** Proses anak yang telah selesai dieksekusi tetapi entri prosesnya masih bertahan di tabel proses OS karena proses induknya (PID 1) belum membaca status keluar (*exit status*) miliknya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Titik Rawan Pemahaman Siswa (Mental Block):**
    *   Banyak pemula menganggap kontainer menyimpan seluruh sistem operasi di dalamnya layaknya Virtual Machine. Berikan analogi proses: *Buka terminal di host, jalankan kontainer, lalu periksa `ps aux | grep node` di host. Tunjukkan bahwa proses kontainer langsung terlihat di task manager OS utama!*
    *   Banyak siswa kesulitan memahami mengapa `CMD npm start` dapat menyebabkan aplikasi mereka lambat mati saat di-stop di production. Lakukan demonstrasi live menggunakan sinyal terminasi (`docker stop` vs `docker kill`) dan bandingkan log keluaran.
*   **Panduan Pedagogi Lab:**
    *   Pastikan siswa menginstal Docker Engine dengan Docker Buildx aktif untuk memanfaatkan kapabilitas BuildKit terbaru.
    *   Tekankan bahwa stage `test` di Dockerfile bukanlah pengganti CI/CD runner sepenuhnya, melainkan gerbang lokal (*local gating mechanism*) yang memastikan developer tidak dapat mem-push image lokal yang rusak ke registry server.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2025):**
    *   Rilis awal kurikulum core foundations untuk *Containerization, Testing, & Enterprise Deployment*.
    *   Penambahan skenario multi-stage enterprise Node.js/TypeScript dengan integrasi unit testing, *dumb-init*, dan isolasi *non-root*.
    *   Integrasi materi primitif kernel tingkat rendah (Linux namespaces, cgroups, OverlayFS).

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** Bab 09 Module 04 — *Database Transaction Isolation, Concurrency Control, and Acid Compliance*
*   **Modul Saat Ini:** Bab 10 Module 01 — *Dasar Containerization OCI, Multi-Stage Builds, dan Otomasi Pengujian Terisolasi*
*   **Modul Berikutnya:** Bab 10 Module 02 — *End-to-End Automated Testing (Integration, Mocking, and Contract Testing with Testcontainers)*