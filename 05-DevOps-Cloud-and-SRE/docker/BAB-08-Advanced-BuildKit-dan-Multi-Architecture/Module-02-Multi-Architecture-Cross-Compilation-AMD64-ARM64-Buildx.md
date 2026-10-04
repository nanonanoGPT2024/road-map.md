# Module 02: Multi-Architecture Builds, Cross-Compilation (AMD64/ARM64), dan Docker Buildx

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami konsep OCI Multi-Architecture Manifest List (`index.json` / image manifest list) dan bagaimana Docker Engine memilih binary layer yang tepat secara otomatis sesuai arsitektur CPU host.
2. Mengonfigurasi dan mengoperasikan Docker Buildx dengan builder instance berbasis driver `docker-container`.
3. Membedakan mekanisme **QEMU Emulation** (`binfmt_misc`) vs **Native Cross-Compilation** menggunakan build arguments otomatis BuildKit (`TARGETPLATFORM`, `BUILDPLATFORM`, `TARGETOS`, `TARGETARCH`).
4. Mengompilasi dan memublikasikan image multi-arch (`linux/amd64`, `linux/arm64`) ke remote container registry dalam satu perintah eksekusi.
5. Melakukan inspeksi manifest list menggunakan `docker buildx imagetools inspect` dan men-debug galat klasik `exec /app: exec format error`.

---

## 2. Prerequisite
- Memahami konsep Image Layer dan instruksi Dockerfile ([Module 01 BAB 03](../BAB-03-Dockerfile-Engineering-dan-Image-Optimization/Module-01-Anatomi-Image-Layer-Caching-Strategy-dan-Instruksi-Fundamental.md)).
- Memahami arsitektur BuildKit dan paralelisme LLB ([Module 01 BAB 08](Module-01-BuildKit-Engine-Secret-Mounts-Cache-Mounts-dan-SSH-Forwarding.md)).
- Pemahaman dasar arsitektur CPU (x86_64 / Intel / AMD vs aarch64 / ARM64 / Apple Silicon / AWS Graviton).

---

## 3. Concept
Dalam ekosistem cloud modern saat ini, beban kerja (workload) komputasi berjalan di atas lingkungan CPU yang sangat heterogen:
- **Developer Workstation**: Banyak developer menggunakan laptop Apple Silicon (M1/M2/M3/M4) yang berbasis arsitektur **ARM64** (`aarch64`).
- **Cloud Virtual Machines**: Sebagian besar server cloud konvensional (AWS EC2 c5, Google Cloud N2, Azure D-series) berbasis arsitektur **AMD64** (`x86_64`).
- **Cost-Optimized Cloud Instances**: Server modern berbasis ARM seperti AWS Graviton3/4, Ampere Altra di OCI, dan GCP Tau T2A menawarkan rasio *price-performance* hingga 40% lebih efisien dibanding x86_64.

Jika Anda membangun image Docker hanya di laptop ARM64 (`docker build -t myapp .`) lalu mendorongnya ke Kubernetes cluster x86_64 di AWS, pod akan langsung mengalami `CrashLoopBackOff` dengan pesan error:
```text
standard_init_linux.go:228: exec user process caused: exec format error
```
Galat ini terjadi karena kernel Linux x86 menolak mengeksekusi instruksi biner assembly berformat ARM64. **Multi-Architecture Images** menyelesaikan problem ini dengan membundel beberapa binary arsitektur ke dalam satu identifier tag yang sama (misal `repo/app:v1.0.0`) melalui **OCI Manifest List**.

---

## 4. Why?
Mengapa multi-architecture build menjadi standar industri wajib?
1. **Developer Experience yang Mulus**: Developer macOS ARM64 dan developer Linux/Windows AMD64 dapat menarik tag image yang sama (`docker pull postgres:16-alpine`) tanpa perlu mencari tag khusus arsitektur seperti `postgres:16-alpine-arm64`.
2. **Penghematan Biaya Cloud (Cloud FinOps)**: Tim DevOps dapat memigrasikan production worker ke node AWS Graviton (ARM64) atau cluster hybrid tanpa harus mengubah manifest deployment aplikasi.
3. **IoT & Edge Computing**: Aplikasi yang sama dapat di-deploy ke edge gateway (Raspberry Pi 4 / 5 berbasis ARM64/ARMv7) dan ke centralized data center (AMD64).

---

## 5. What?
### Komponen Kunci Multi-Architecture Docker:
1. **OCI Image Index / Manifest List**: Sebuah dokumen JSON metadata di registry yang memetakan tuple `(os, architecture, variant)` ke digest SHA256 image manifest spesifik untuk arsitektur tersebut.
2. **Docker Buildx**: CLI plugin resmi Docker yang memperluas fungsionalitas `docker build` dengan kapabilitas penuh BuildKit backend, builders pool, dan multi-platform building.
3. **QEMU User Space Emulation**: Library emulator CPU yang memungkinkan kernel host mengeksekusi instruksi CPU non-native melalui modul kernel Linux `binfmt_misc`.
4. **Native Cross-Compilation**: Teknik kompilasi di mana compiler (seperti Go, Rust, atau Zig) berjalan di arsitektur CPU host (native speed), namun menghasilkan target executable biner untuk arsitektur CPU lain.

---

## 6. How? Arsitektur & Alur Kerja Buildx

### ASCII Diagram: OCI Manifest List Resolution
```text
                                 [ Client / Host ]
               +---------------------------------------------------+
               |  Host: AWS EC2 (linux/amd64)                      |
               |  Command: docker run mycompany/api:v1.0.0         |
               +---------------------------------------------------+
                                         |
                                         v (1. Query Tag Manifest List)
               +---------------------------------------------------+
               |              Container Registry                   |
               |         (Docker Hub / GitHub Packages / ECR)      |
               |                                                   |
               |  Tag: "mycompany/api:v1.0.0" -> Manifest List:    |
               |  +---------------------------------------------+  |
               |  | Platform: linux/amd64 -> sha256:aaaa1111... |  |
               |  | Platform: linux/arm64 -> sha256:bbbb2222... |  |
               |  | Platform: linux/arm/v7 -> sha256:cccc3333... |  |
               |  +---------------------------------------------+  |
               +---------------------------------------------------+
                                         |
               (2. Docker Engine detects host CPU is "amd64")
                                         |
                                         v
                         Downloads SHA256:aaaa1111 Layers
                                         |
                                         v
               +---------------------------------------------------+
               |        Local Docker Engine (Execution)            |
               |  Kernel AMD64 runs AMD64 native binary cleanly!   |
               +---------------------------------------------------+
```

---

## 7. Analogy
Bayangkan Anda menerbitkan sebuah buku teknis internasional. 
- Alih-alih membuat tiga toko buku terpisah (`toko-bahasa-inggris`, `toko-bahasa-jepang`, `toko-bahasa-indonesia`), Anda membuat satu etalase buku dengan satu ISBN tunggal.
- Ketika pembaca dari Jepang memindai barcode ISBN tersebut, rak display pintar secara otomatis menyodorkan buku versi teks bahasa Jepang ke tangannya.
- Pembaca dari Indonesia menerima buku teks bahasa Indonesia.
- ISBN tunggal tersebut adalah **Manifest List**, dan masing-masing buku fisik yang disodorkan adalah **Architecture-Specific Image Layers**.

---

## 8. Diagram: QEMU Emulation vs Native Cross-Compilation

```text
Pendekatan A: QEMU User-Mode Emulation (Lambat untuk CPU Heavy)
Host (AMD64)
+------------------------------------------------------------------------+
| BuildKit Host -> QEMU CPU Interpreter (aarch64 -> x86_64 translation)  |
|                  -> Emulated Node.js / Python compiler                 |
|                  (Overhead 5x - 10x lebih lambat, rawan timeout)       |
+------------------------------------------------------------------------+

Pendekatan B: Native Cross-Compilation via BuildKit Args (Super Cepat!)
Host (AMD64)
+------------------------------------------------------------------------+
| BuildKit Host -> Native AMD64 Go Compiler (Kecepatan 100% Native)      |
|                  Env: GOOS=linux GOARCH=arm64 go build -o /app/api     |
|                  (Hanya 3 detik! Menghasilkan biner ARM64 langsung)    |
+------------------------------------------------------------------------+
```

---

## 9. Simple Example: Menyiapkan Docker Buildx Builder
Driver default `docker` tidak mendukung ekspor multi-platform langsung ke local image cache. Kita harus membuat builder instance dengan driver `docker-container`:

```bash
# 1. Cek builder yang sedang aktif
docker buildx ls

# 2. Buat instance builder baru berbasis container BuildKit
docker buildx create --name multiarch-builder --driver docker-container --use

# 3. Inisialisasi dan bootstrap builder instance
docker buildx inspect --bootstrap

# 4. Verifikasi platform yang didukung oleh builder
# Output akan menampilkan: Platforms: linux/amd64, linux/arm64, linux/riscv64, linux/arm/v7, dll.
```

---

## 10. Practical Example: Dockerfile Multi-Arch dengan Native Cross-Compilation (Go)

Gunakan variabel bawaan BuildKit (`BUILDPLATFORM`, `TARGETOS`, `TARGETARCH`):

```dockerfile
# syntax=docker/dockerfile:1.4
# Stage 1: Build binary menggunakan native host architecture (BUILDPLATFORM)
FROM --platform=$BUILDPLATFORM golang:1.22-alpine AS builder

WORKDIR /src

# Download dependencies (Cache Mount dioptimalkan)
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .

# Target arguments otomatis di-inject oleh BuildKit saat flag --platform dipanggil
ARG TARGETOS
ARG TARGETARCH

# Kompilasi native cross-compile tanpa QEMU
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -ldflags="-s -w" -o /bin/server ./cmd/server

# Stage 2: Runtime image sesuai TARGETPLATFORM
FROM alpine:3.19 AS runtime

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app
COPY --from=builder /bin/server /app/server

USER 10001:10001
ENTRYPOINT ["/app/server"]
```

### Eksekusi Build Multi-Architecture & Push ke Registry:
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/myorg/cloud-microservice:v1.0.0 \
  --push .
```

---

## 11. Real World Example: CI/CD Pipeline GitHub Actions Multi-Arch
Di pipeline enterprise, image di-build untuk AMD64 (server lawas) dan ARM64 (AWS Graviton cost-effective clusters):

```yaml
# .github/workflows/docker-publish.yml
name: Build and Push Multi-Arch Docker Image

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  docker-release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      # Set up QEMU untuk platform non-native jika dibutuhkan
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      # Set up Docker Buildx dengan engine container
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and Push Multi-Arch
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            myorg/enterprise-api:latest
            myorg/enterprise-api:${{ github.ref_name }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 12. Trade-offs: QEMU Emulation vs Native Cross-Compilation

| Dimensi | QEMU User Emulation (`binfmt_misc`) | Native Cross-Compilation (Go/Rust/Zig) |
|---|---|---|
| **Kemudahan Konfigurasi** | Sangat mudah (tidak perlu ubah Dockerfile) | Butuh modifikasi Dockerfile (`--platform=$BUILDPLATFORM`) |
| **Kecepatan Build** | Sangat lambat (bisa 10x lebih lama pada CPU tasks) | Kecepatan 100% native (secepat arsitektur host) |
| **Dukungan C/C++ (CGO)** | Bekerja transparan tanpa cross-toolchain rumit | Butuh cross-compiler toolchain (misal `musl-cross`, Zig cc) |
| **Stabilitas Pipeline** | Terkadang mengalami race conditions atau crash QEMU | Sangat stabil dan deterministik |
| **Konsumsi Resource CI** | Memakan CPU tinggi (runner bisa kehabisan kredit) | Hemat CPU dan memori runner |

---

## 13. When To Use
- Saat aplikasi Anda didistribusikan ke publik (Open Source, SaaS, atau Docker Hub Library).
- Saat tim engineering menggunakan perangkat Apple Silicon (M1/M2/M3), sedangkan target production cluster berjalan di AMD64 (atau sebaliknya).
- Saat merencanakan migrasi ke cluster komputasi hemat biaya berbasis ARM64 (AWS Graviton, Google Tau T2A).

---

## 14. When NOT To Use
- **Local Rapid Inner-Loop Development**: Jangan gunakan `--platform linux/amd64,linux/arm64` saat Anda hanya ingin mengetes hot-reloading di laptop lokal. Build hanya untuk arsitektur native laptop Anda (`docker build .`) agar proses instan.
- **Sistem Monolitik Legacy CGO Kompleks**: Jika aplikasi C++ Anda memiliki ratusan dependensi pustaka sistem lokal x86 yang tidak memiliki cross-toolchain, gunakan *native builder nodes* (menjalankan runner native AMD64 dan ARM64 terpisah lalu menggabungkannya dengan `docker manifest create`).

---

## 15. Common Mistakes
1. **Mencoba me-load image multi-arch ke local Docker daemon**:
   ```bash
   # SALAH: Ini akan error karena docker daemon lokal tidak bisa menyimpan 2 arsitektur berbeda di 1 tag lokal
   docker buildx build --platform linux/amd64,linux/arm64 -t myapp:v1 --load .
   ```
   *Perbaikan*: Gunakan `--push` untuk langsung mengirim ke registry, ATAU tentukan satu platform saja jika ingin `--load` ke lokal (`--platform linux/arm64 --load`).
2. **Tidak mengaktifkan binfmt / QEMU saat build non-native tanpa cross-compilation**:
   Mencoba build ARM64 di mesin Linux AMD64 tanpa `setup-qemu-action` atau `tonistiigi/binfmt` menyebabkan error: `exec format error` di tengah tahapan `RUN`.
3. **Mengabaikan layer cache per arsitektur**:
   Menyimpan cache tanpa isolasi arsitektur dapat merusak binary cache jika arsitektur tertukar.

---

## 16. Best Practices
### Must Have
- Selalu gunakan `docker buildx` untuk seluruh build pipeline modern.
- Gunakan bahasa yang mendukung cross-compilation native (Go, Rust) dengan memanfaatkan `--platform=$BUILDPLATFORM` di stage builder.
- Buat builder instance khusus `docker-container` agar fitur modern (cache mount, secret mount, multi-platform) dapat berjalan optimal.

### Recommended
- Gunakan `docker buildx imagetools inspect <image-tag>` pada tahap smoke testing CI/CD untuk memastikan semua manifest platform terdaftar dengan benar.
- Terapkan GitHub Actions Cache (`type=gha`) atau Registry Cache (`type=registry`) untuk mempercepat build antar arsitektur.

### Advanced
- Siapkan hybrid Buildx cluster dengan multi-node builders: satu node AMD64 dan satu node native ARM64 terhubung via SSH/TCP, sehingga BuildKit mendelegasikan build AMD64 ke node x86 dan ARM64 ke node ARM secara native 100% tanpa QEMU.

---

## 17. Troubleshooting Guide
### Problem 1: `exec format error` saat menjalankan container
- **Gejala**: Container langsung exit dengan status `code 139` atau log `exec user process caused: exec format error`.
- **Penyebab**: Biner di dalam image dikompilasi untuk arsitektur berbeda dengan arsitektur CPU host container runtime.
- **Diagnosa**:
  ```bash
  docker inspect <image-name> --format '{{.Architecture}}'
  uname -m
  ```
- **Solusi**: Re-build image dengan `--platform` yang sesuai dengan `uname -m` host target, atau gunakan builder multi-arch dengan manifest list.

### Problem 2: Multi-platform build gagal dengan error `exporting to image: cannot export multiple platforms to the docker daemon`
- **Penyebab**: Docker daemon lokal (standar moby) tidak memiliki dukungan native multi-arch OCI image storage terpadu untuk satu tag.
- **Solusi**: Tambahkan `--push` untuk mengekspor ke remote registry, atau pilih satu platform spesifik jika ingin di-load ke Docker lokal (`--platform linux/arm64 --load`).

---

## 18. Exercises
### Level: Easy
1. Buka terminal Anda dan jalankan perintah untuk memeriksa arsitektur CPU laptop/mesin Anda (`uname -m` atau di Windows PowerShell: `$env:PROCESSOR_ARCHITECTURE`).
2. Jalankan perintah `docker buildx ls` dan periksa driver serta platform apa saja yang didukung oleh builder aktif Anda.

### Level: Medium
1. Buat instance builder Buildx baru dengan nama `my-test-builder` menggunakan driver `docker-container`.
2. Bootstrap builder tersebut dan verifikasi bahwa statusnya berubah menjadi `running`.
3. Hapus builder tersebut setelah selesai pengujian.

### Level: Hard
1. Buat Dockerfile multi-stage untuk aplikasi Go sederhana.
2. Gunakan instruksi `FROM --platform=$BUILDPLATFORM golang:1.22-alpine AS builder` dan manfaatkan `TARGETOS` serta `TARGETARCH`.
3. Lakukan build simulasi untuk platform `linux/amd64` dan `linux/arm64`.

---

## 19. Challenge
Rancang arsitektur CI/CD multi-architecture untuk startup yang memiliki:
- 10 developer dengan MacBook M2 (ARM64).
- Staging server di AWS t4g.medium (AWS Graviton ARM64).
- Production cluster di Kubernetes AWS EKS dengan armada node mix (spot instance c5.large x86_64 dan c6g.large ARM64).
Tuliskan strategi build Dockerfile, konfigurasi Buildx, dan mekanisme verifikasi manifest image sebelum rolling deployment dimulai.

---

## 20. Summary
- **Multi-Architecture Images** memastikan aplikasi dapat berjalan mulus di arsitektur heterogen (AMD64 dan ARM64) tanpa perubahan kode aplikasi atau modifikasi tag manifest deployment.
- **OCI Image Index / Manifest List** berperan sebagai pointer registry yang mengarahkan Docker Engine lokal untuk menarik biner yang sesuai dengan CPU host secara transparan.
- **Docker Buildx** dengan driver `docker-container` membuka kapabilitas penuh multi-platform compilation.
- Menggunakan **Native Cross-Compilation** via variabel otomatis BuildKit (`BUILDPLATFORM`, `TARGETARCH`, `TARGETOS`) adalah praktik standar industri tercepat dibandingkan QEMU user emulation yang memiliki overhead CPU tinggi.
