# Module 02: Multi-Stage Builds, Distroless, & Minimal Base Images

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami paradigma **Multi-Stage Builds** untuk memisahkan lingkungan kompilasi (*build-time*) dari lingkungan eksekusi (*runtime*).
- Menggunakan sintaks `FROM ... AS <stage>` dan `COPY --from=<stage>` untuk mentransfer artefak biner bersih.
- Membandingkan spektrum base image: **Ubuntu/Debian**, **Alpine Linux** (`musl` libc), **Google Distroless**, dan **`scratch`**.
- Memangkas ukuran container image secara dramatis dari $>1\text{GB}$ menjadi $<25\text{MB}$.
- Meningkatkan postur keamanan container dengan mengeliminasi package manager (`apt`/`apk`) dan shell interpreter (`/bin/sh`, `/bin/bash`) di production runtime.

---

## 2. Prerequisite
- Memahami konsep anatomi layer image dan caching (BAB 03 Module 01).
- Pengetahuan dasar tentang proses kompilasi kode (Go, Rust, Java, atau bundler frontend TypeScript/Vite).
- Memahami konsep static linking vs dynamic linking library di Linux.

---

## 3. Concept
Dalam pengembangan software modern, kita membutuhkan compiler, SDK, toolchain, dan library pengujian berukuran ratusan megabyte hingga gigabyte:
- Go / Rust: butuh compiler `go`/`rustc`, tool git, dan file header Linux.
- Node.js / React: butuh `devDependencies`, TypeScript compiler (`tsc`), Webpack/Vite, dan test runner Jest.
- Java: butuh JDK (Java Development Kit) dan Maven/Gradle.

Namun, di lingkungan produksi, kita **hanya membutuhkan satu file biner hasil kompilasi** atau file HTML/JS statis yang sudah di-minify.

**Multi-Stage Build** memungkinkan Anda mendefinisikan beberapa instruksi `FROM` dalam satu file `Dockerfile`. Setiap stage dapat menggunakan base image yang berbeda. Anda dapat mengompilasi kode di stage pertama (yang kaya alat), lalu menyalin **hanya artefak akhirnya** ke stage kedua yang berukuran minimalis, meninggalkan seluruh compiler dan sampah build di belakang.

```
       MULTI-STAGE BUILD ARCHITECTURE
 ┌─────────────────────────────────────────────────────────────┐
 │ STAGE 1: BUILD ENVIRONMENT (golang:1.22-alpine ~350MB)      │
 │  - Installs git, gcc, make                                  │
 │  - Downloads dependencies & compiles Go source code         │
 │  - Produces static compiled binary: /app/web-server         │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                   COPY --from=builder /app/web-server
                                │ (Hanya binary 12MB yang disalin!)
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ STAGE 2: PRODUCTION RUNTIME (gcr.io/distroless/static ~2MB) │
 │  - NO shell (/bin/sh tidak ada)                             │
 │  - NO package manager (apk/apt tidak ada)                   │
 │  - Only contains: ca-certificates, tzdata, & /web-server    │
 └─────────────────────────────────────────────────────────────┘
  TOTAL FINAL PRODUCTION IMAGE SIZE: 14 MB (Hemat 96%!)
```

---

## 4. Why?
1. **Penciutan Ukuran Image 90-98%**: Menurunkan ukuran image dari 1.2GB menjadi 15MB mempercepat transfer jaringan di pipeline CI/CD dan registry pull di cluster Kubernetes saat autoscaling dari hitungan menit menjadi hitungan detik.
2. **Minimasi Attack Surface Keamanan (Zero CVE)**: Base image lengkap (seperti `ubuntu` atau `node:latest`) membawa ribuan utilitas Linux (`curl`, `wget`, `nc`, `tar`, `python`) dan puluhan celah keamanan (*vulnerabilities/CVE*). Jika penyerang berhasil mengeksekusi Remote Code Execution (RCE) pada image **Distroless**, mereka tidak bisa mendownload malware atau membuka reverse shell karena **tidak ada shell `/bin/sh` sama sekali** di dalam container.
3. **Pemisahan Kepentingan Build vs Run**: Source code rahasia, kunci SSH privat untuk clone repo, dan token NPM tidak akan pernah tersimpan di layer image produksi final.

---

## 5. What?
### Spektrum Karakteristik Base Image:

| Base Image | Ukuran Base | Komponen C-Library | Shell (`sh`) | Package Manager | Rekomendasi Penggunaan |
|---|---|---|---|---|---|
| **Ubuntu / Debian** | 80 - 140 MB | `glibc` (Standar GNU) | Tersedia (`bash`) | `apt-get` | Aplikasi legacy / library C rumit |
| **Alpine Linux** | ~5 MB | `musl-libc` (Ringan) | Tersedia (`busybox sh`) | `apk` | Aplikasi scripting, Python, Node.js sederhana |
| **Google Distroless** | 15 - 30 MB | `glibc` / static | **TIDAK ADA** | **TIDAK ADA** | Microservices produksi (Node.js, Java, Python, Go) |
| **`scratch`** | **0 Bytes** | None (Wajib static binary) | **TIDAK ADA** | **TIDAK ADA** | Biner murni Go, Rust, atau C yang di-link statis |

> **Perhatian Glbc vs Musl**: Alpine Linux menggunakan `musl-libc`, bukan `glibc`. Beberapa modul native Node.js (seperti `sharp` atau `grpc`) atau library Python data science (`numpy`, `scipy`) mungkin harus dikompilasi ulang dari source code di Alpine, yang dapat memperlambat build time. Distroless berbasis Debian menyediakan `glibc` tanpa overhead OS penuh!

---

## 6. How?
Langkah Merancang Multi-Stage Build:
1. **Stage 1 (Builder)**: Beri nama stage dengan klausul `AS <nama>` (contoh: `FROM golang:1.22 AS builder`).
2. **Compile**: Jalankan instalasi dependensi dan perintah kompilasi (misal `go build -o /app/server`).
3. **Stage 2 (Final)**: Mulai stage baru yang bersih dengan base image minimal (misal `FROM gcr.io/distroless/static-debian12:nonroot`).
4. **Artifact Transfer**: Salin biner dari stage builder:
   `COPY --from=builder /app/server /server`.
5. **Runtime Directives**: Pasang `USER nonroot` dan `ENTRYPOINT ["/server"]`.

---

## 7. Analogy
Bayangkan **Multi-Stage Build** seperti **Membangun Rumah dengan Pabrik Beton Modular**:
- **Stage 1 (Pabrik)** memiliki alat-alat berat, truk derek, mesin giling semen, serbuk gergaji, dan puluhan kuli bangunan (**Compiler, Git, Headers, devDependencies**).
- Setelah dinding dan pilar beton rumah selesai dicetak rapi (**Artefak Biner**), Anda tidak perlu membawa truk molen semen dan tumpukan pasir kotor ke kavling tanah perumahan Anda!
- Anda hanya memindahkan pilar beton yang sudah bersih ke kavling tanah perumahan baru yang hijau dan asri (**Stage 2: Distroless Production Image**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               SINGLE-STAGE VS MULTI-STAGE DOCKERFILE COMPARISON                   |
+-----------------------------------------------------------------------------------+

 SINGLE-STAGE BUILD (ANTI-PATTERN):
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ FROM node:20 (1.1 GB)                                                       │
 │  ├── Source Code (TypeScript)                                               │
 │  ├── devDependencies (Jest, Webpack, Babel, ESLint - 450 MB)                │
 │  ├── npm cache & temporary files                                            │
 │  └── dist/ production bundle (2 MB)                                         │
 └─────────────────────────────────────────────────────────────────────────────┘
  Production Image Size: 1.15 GB  ──> Rentan 42 CVEs, Lambat di-deploy!

 MULTI-STAGE BUILD (BEST PRACTICE):
 ┌──────────────────────────────────────┐
 │ STAGE 1: AS builder (node:20)        │
 │  - Compiles TS to JS bundle          │
 └──────────────────┬───────────────────┘
                    │ COPY --from=builder /app/dist /usr/share/nginx/html
                    ▼
 ┌──────────────────────────────────────┐
 │ STAGE 2: nginx:alpine-slim (12 MB)   │
 │  - Only Nginx + dist/ bundle         │
 └──────────────────────────────────────┘
  Production Image Size: 14 MB (Penyusutan 98.8%!)  ──> 0 CVEs Kritis!
```

---

## 9. Simple Example: Multi-Stage Build untuk Go Application
Dockerfile lengkap dari source code hingga image `scratch` 0-byte base:

```dockerfile
# ==========================================
# STAGE 1: Build Environment
# ==========================================
FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Kompilasi static binary: CGO_ENABLED=0 mematikan dependensi dinamis glibc
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /bin/api-server .

# ==========================================
# STAGE 2: Ultra-Minimal Production Runtime
# ==========================================
FROM scratch

# Salin sertifikat CA agar aplikasi Go bisa memanggil HTTPS eksternal
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Salin binary yang telah dikompilasi
COPY --from=builder /bin/api-server /api-server

# Dokumentasikan port
EXPOSE 8080

# Jalankan biner langsung sebagai PID 1
ENTRYPOINT ["/api-server"]
```

---

## 10. Practical Example: Multi-Stage Build untuk React / Vite Frontend
Mengompilasi frontend modern dan menyajikannya menggunakan Nginx Alpine:

```dockerfile
# ==========================================
# STAGE 1: Dependency & Build
# ==========================================
FROM node:20-alpine AS build-stage

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build # Menghasilkan static folder /app/dist

# ==========================================
# STAGE 2: Lightweight Production Web Server
# ==========================================
FROM nginx:1.25-alpine-slim

# Salin konfigurasi Nginx kustom untuk Single Page Application (SPA)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Salin hanya static HTML/JS/CSS dari stage build
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Hardening: Jalankan dengan user non-root nginx
USER nginx

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

---

## 11. Real World Example: Migrasi FinTech Microservice ke Google Distroless
Sebuah gateway pembayaran perbankan sebelumnya menggunakan image tunggal `node:18` biasa:
- **Kondisi Awal**: Ukuran image 1.1GB. Pemindaian kerentanan Trivy mendeteksi 31 kerentanan OS (4 `HIGH`, 1 `CRITICAL` pada paket `openssl` dan `systemd`). Auditor keamanan perbankan menolak rilis ke produksi.
- **Implementasi Multi-Stage Distroless**:
  1. Stage 1: `node:18-alpine` menginstall seluruh dependensi dan me-run TypeScript build.
  2. Stage 2: `gcr.io/distroless/nodejs20-debian12:nonroot` hanya menyalin folder `/app/dist` dan `node_modules` produksi.
- **Hasil**:
  - Ukuran image turun dari 1.1GB menjadi 148MB (termasuk runtime Node.js v20).
  - Pemindaian Trivy: **0 CRITICAL, 0 HIGH**.
  - Auditor PCI-DSS menyetujui rilis produksi karena penyerang tidak memiliki shell interpreter untuk eksploitasi privilege escalation.

---

## 12. Trade-offs

| Aspek | Base Image Ubuntu/Debian | Multi-Stage Distroless / Scratch |
|---|---|---|
| **Ukuran Image** | Besar (100MB - 1.5GB) | Sangat Ramping (10MB - 150MB) |
| **Kemudahan Debugging Manual** | Sangat Mudah (Bisa `docker exec -it sh`, pasang curl/nano) | Menantang (Tidak ada shell, harus pakai Ephemeral Containers) |
| **Jumlah Celah Keamanan (CVE)** | Banyak (Membawa puluhan utilitas OS bawaan) | Hampir Nol (Hanya membawa runtime aplikasi) |
| **Waktu Transfer CI/CD & Pull** | Lambat (Memakan bandwidth registry) | Instan (Download hitungan detik) |

---

## 13. When To Use
- Wajib digunakan pada seluruh layanan produksi microservices (Go, Rust, Node.js, Java, Python).
- Wajib pada aplikasi frontend SPA (React, Vue, Angular) yang disajikan via Nginx.
- Wajib pada sistem yang terikat kepatuhan keamanan tinggi (SOC2, PCI-DSS, ISO 27001).

---

## 14. When NOT To Use
- Jangan gunakan `scratch` untuk aplikasi yang membutuhkan dynamic runtime library C (*dynamically linked binaries*) tanpa menyalin library `.so` yang bersangkutan.
- Jangan gunakan Distroless pada lingkungan local development di mana developer membutuhkan kemampuan `docker exec` untuk menginspeksi file atau menguji perintah curl manual secara interaktif (gunakan Alpine untuk dev, Distroless untuk prod).

---

## 15. Common Mistakes
1. **Lupa Flag `CGO_ENABLED=0` pada Go Build**: Membangun aplikasi Go dengan CGO aktif lalu menyalinnya ke `scratch`. Biner Go akan gagal berjalan saat container start dengan error ambigu: `standard_init_linux.go: exec user process caused: no such file or directory` (karena dinamic linker `/lib64/ld-linux-x86-64.so.2` tidak ada di scratch!).
2. **Menyalin Seluruh Folder `node_modules` Termasuk DevDependencies**: Menggunakan `npm install` biasa di stage builder lalu menyalin seluruh folder `node_modules` ke stage final. Gunakan `npm ci --only=production` atau `npm prune --production` sebelum menyalin ke stage runtime.
3. **Lupa Sertifikat SSL/TLS Root di Image Scratch**: Biner Go di image `scratch` mencoba memanggil API eksternal via HTTPS dan melempar error `x509: certificate signed by unknown authority` karena image `scratch` tidak memiliki file CA root certificates `/etc/ssl/certs/ca-certificates.crt`.

---

## 16. Best Practices
### Must Have
- Selalu gunakan Multi-Stage Builds untuk seluruh aplikasi yang memerlukan langkah kompilasi atau transpiling.
- Berikan label deskriptif pada setiap stage: `AS builder`, `AS tester`, `AS release`.
- Salin file sertifikat CA root (`ca-certificates.crt`) jika menggunakan base image `scratch`.

### Recommended
- Gunakan tag `gcr.io/distroless/static-debian12:nonroot` untuk menjalankan container sebagai user non-root secara otomatis tanpa perlu deklarasi manual.
- Gabungkan dengan BuildKit cache mounts (`--mount=type=cache`) di stage builder untuk mempercepat download modul Go atau NPM.

### Advanced
- Gunakan fitur multi-target build (`docker build --target tester .`) untuk menjalankan unit tests di pipeline CI tanpa menghasilkan image produksi.

---

## 17. Troubleshooting
- **Masalah**: Container berbasis `scratch` atau `distroless` gagal start: `exec /app: no such file or directory`.
  - *Penyebab*: File binary dikompilasi secara dinamis (*dynamically linked*) dan mencari shared library host yang tidak tersedia di scratch.
  - *Solusi*: Kompilasi biner secara statis dengan flag `CGO_ENABLED=0 -ldflags="-extldflags=-static"` (pada Go) atau gunakan target `x86_64-unknown-linux-musl` (pada Rust).
- **Masalah**: Anda perlu melakukan troubleshooting live pada container Distroless yang tidak memiliki shell.
  - *Solusi*: Gunakan fitur Docker debug: `docker debug <container-id>` atau gunakan Kubernetes Ephemeral Debug Containers (`kubectl debug`).

---

## 18. Exercise
1. Tulis Dockerfile multi-stage untuk aplikasi Go HTTP API: stage 1 menggunakan `golang:1.22-alpine` dan stage 2 menggunakan `scratch`. Buktikan bahwa ukuran image final di bawah 20MB!
2. Tulis Dockerfile multi-stage untuk aplikasi frontend React Vite yang menyajikan hasil build `dist` menggunakan Nginx Alpine.

---

## 19. Challenge
Rancang pipeline kompresi image ekstrem:
- Buat microservice REST API.
- Bandingkan ukuran image dari pendekatan Single-Stage (berbasis `node:20` standar) vs Multi-Stage (berbasis Distroless non-root).
- Jalankan scanner Trivy pada kedua image dan buktikan bahwa image Multi-Stage Distroless berhasil mengeliminasi seluruh kerentanan CVE tingkat `CRITICAL` dan `HIGH`.

---

## 20. Summary
- **Multi-Stage Builds** secara bersih memisahkan alat kompilasi dari lingkungan eksekusi produksi.
- Pendekatan ini memangkas ukuran image hingga lebih dari 90% dan memangkas waktu transfer deployment.
- **Distroless** dan **`scratch`** meniadakan shell interpreter dan package manager, meminimalkan attack surface keamanan ke tingkat paling absolut.
