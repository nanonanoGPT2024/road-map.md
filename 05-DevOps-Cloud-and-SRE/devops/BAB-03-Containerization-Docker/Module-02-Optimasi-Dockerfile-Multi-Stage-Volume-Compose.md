# Module 02: Optimasi Dockerfile Multi-Stage, Volume Persistence, & Docker Compose

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Menulis Dockerfile standar produksi menggunakan **Multi-Stage Builds** untuk memangkas ukuran image hingga 90%.
2. Mengoptimalkan **Layer Caching** Docker untuk mempercepat waktu build pipeline CI/CD dari menit ke detik.
3. Memilih strategi persistensi data yang tepat: **Named Volumes**, **Bind Mounts**, dan **tmpfs**.
4. Mengorkestrasi aplikasi multi-container di lingkungan lokal/staging menggunakan **Docker Compose v2** (Networks, Volumes, Healthchecks, dan Environment variables).

---

## 2. Prerequisite
- Memahami konsep dasar isolasi Namespaces dan Cgroups dari [BAB 03 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-03-Containerization-Docker/Module-01-Arsitektur-Container-Namespaces-Cgroups-Runtime.md).
- Mengetahui perintah dasar CLI Docker (`docker build`, `docker run`, `docker ps`).

---

## 3. Concept
Banyak pemula membuat image Docker dengan cara menaruh compiler, SDK pengembang, dan tool build berat ke dalam image final production. Akibatnya:
- Ukuran image membengkak hingga 1.5 GB.
- Proses download (`docker pull`) di server production sangat lambat.
- Celah keamanan meningkat drastis karena paket build (gcc, npm, git) tertinggal di dalam container yang terekspos.

**Multi-Stage Build** memecahkan masalah ini dengan memisahkan proses menjadi beberapa tahap:
1. **Stage 1 (Builder)**: Menggunakan image lengkap dengan compiler/tool untuk meng-compile source code atau menginstal dependencies.
2. **Stage 2 (Production Runner)**: Menggunakan base image minimal (seperti `alpine` atau `distroless`), lalu **hanya menyalin binari/asset hasil kompilasi dari Stage 1**. Seluruh file mentah, compiler, dan build tools ditinggalkan.

Hasilnya: Image production mengecil dari 1.2 GB menjadi 45 MB, aman, dan dapat di-deploy dalam hitungan detik.

---

## 4. Why?
Mengapa optimasi Dockerfile dan Compose sangat penting?
1. **Waktu Rilis CI/CD Cepat**: Image berukuran 50 MB menghemat bandwidth jaringan dan mempersingkat waktu deployment cluster dari 10 menit menjadi 30 detik.
2. **Keamanan DevSecOps**: Image minimal yang tidak memuat shell (`/bin/sh`) atau package manager (`apt`/`apk`) membuat peretas sulit menyuntikkan script berbahaya saat terjadi eksploitasi.
3. **Integritas Data Persisten**: Tanpa Docker Volumes, data database PostgreSQL atau upload user akan musnah seketika saat container di-upgrade atau di-recreate.

---

## 5. What?
Komponen penting dalam ekosistem Docker lanjutan:
- **Multi-Stage Syntax**: Penggunaan beberapa instruksi `FROM` dengan alias `AS builder`, diikuti oleh `COPY --from=builder ...`.
- **Layer Caching Rule**: Docker mengeksekusi instruksi dari atas ke bawah. Jika satu layer berubah, seluruh layer di bawahnya harus di-rebuild. **Aturan baku**: Letakkan instruksi yang jarang berubah (`COPY package*.json` -> `RUN npm ci`) **sebelum** instruksi yang sering berubah (`COPY . .`).
- **Tiga Tipe Penyimpanan Data**:
  - *Named Volume*: Dikelola sepenuhnya oleh Docker daemon di `/var/lib/docker/volumes/` (Pilihan terbaik untuk database di production).
  - *Bind Mount*: Memetakan folder host fisik tertentu (misal `./src:/app/src`) ke container (Pilihan terbaik untuk live-reload development).
  - *tmpfs Mount*: Disimpan murni di RAM host tanpa ditulis ke disk fisik (Pilihan terbaik untuk data sensitif/kunci rahasia sementara).
- **Docker Compose**: Tool deklaratif YAML untuk mendefinisikan hubungan multi-service, isolated network bridge, dependency ordering (`depends_on`), dan liveness healthchecks.

---

## 6. How?
Perbandingan Single-Stage vs Multi-Stage Build:

```text
[ SINGLE-STAGE BUILD (BURUK) ]
Dockerfile:
FROM node:20 (1.1 GB)
COPY . .
RUN npm install && npm run build
CMD ["node", "dist/index.js"]
-> Ukuran Image Akhir: 1.2 GB (Berisi node_modules dev, TypeScript compiler, git, dll)

----------------------------------------------------------------------

[ MULTI-STAGE BUILD (BEST PRACTICE) ]
Stage 1: AS builder
FROM node:20-alpine AS builder
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build  --> Menghasilkan folder dist/

Stage 2: AS runner
FROM node:20-alpine AS runner
USER node
COPY --from=builder /app/package*.json .
RUN npm ci --omit=dev  --> Hanya install production dependencies!
COPY --from=builder /app/dist ./dist
CMD ["node", "dist/index.js"]
-> Ukuran Image Akhir: 85 MB (Kompak, Bersih, Aman!)
```

---

## 7. Analogy
Bayangkan **Multi-Stage Build** seperti **Membangun Rumah dengan Scaffolding (Perancah Baja)**:
- Saat tukang membangun dinding rumah lantai dua, mereka mendirikan perancah baja, tangga, molen semen, dan truk crane (Builder Stage).
- Saat rumah selesai dan siap dihuni oleh pemilik (Production Runner), semua perancah, molen semen, dan truk crane dibawa pulang. Anda tidak membiarkan truk crane dan molen semen tetap diparkir di ruang tamu Anda!

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|             DOCKER COMPOSE MULTI-CONTAINER STACK            |
|                                                             |
|  +-------------------+              +--------------------+  |
|  | Nginx Reverse     |              | Express API Backend|  |
|  | Proxy Container   | --(HTTP)-->  | Container          |  |
|  | Port 80:80        |              | Port 3000 (Internal|  |
|  +-------------------+              +--------------------+  |
|                                                |            |
|                                          (TCP:5432)         |
|                                                v            |
|  +-------------------------------------------------------+  |
|  | PostgreSQL Database Container                         |  |
|  | Volume: postgres_data -> /var/lib/postgresql/data     |  |
|  +-------------------------------------------------------+  |
|                                                             |
|         [ Isolated Docker Bridge Network: app-net ]         |
+-------------------------------------------------------------+
```

---

## 9. Simple Example
Contoh template produksi `Dockerfile` (Go App):

```dockerfile
# Stage 1: Build binary
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o server .

# Stage 2: Minimal Distroless / Scratch Runtime
FROM scratch
WORKDIR /
COPY --from=builder /app/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```
*Ukuran image Go di atas hanya sekitar 12 MB!*

---

## 10. Practical Example
File `docker-compose.yml` multi-service siap produksi:

```yaml
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: web-api
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgres://dbuser:secret123@postgres:5432/proddb
      - NODE_ENV=production
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - backend-network

  postgres:
    image: postgres:16-alpine
    container_name: postgres-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: dbuser
      POSTGRES_PASSWORD: secret123
      POSTGRES_DB: proddb
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dbuser -d proddb"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
    driver: local

networks:
  backend-network:
    driver: bridge
```

---

## 11. Real World Example
### Kasus: Pipeline CI/CD Membengkak 20 Menit Menjadi 45 Detik
1. Sebuah tim engineering mengeluh waktu pipeline build Docker di GitHub Actions memakan 20 menit setiap ada commit baru.
2. Penyebab: Dockerfile mereka menyalin seluruh source code (`COPY . .`) **sebelum** menjalankan `npm install`.
3. Akibatnya, perubahan kecil 1 karakter pada file Markdown membatalkan cache `npm install`, memaksa runner mendownload ulang 800MB dependensi setiap saat.
4. **Solusi**: 
   - Ubah urutan: Salin `package*.json` terlebih dahulu, jalankan `npm ci`, baru salin source code `COPY . .`.
   - Gunakan cache backend GitHub Actions (`cache-from: type=gha`).
   - Terapkan Multi-Stage build.
5. **Hasil**: Waktu build terpangkas dari 20 menit menjadi 45 detik!

---

## 12. Trade-offs
| Pendekatan Penyimpanan | Named Volumes | Bind Mounts | tmpfs Mounts |
|---|---|---|---|
| **Lokasi Penyimpanan** | Dikelola Docker di `/var/lib/docker/volumes/` | Path absolut di filesystem Host OS | Memori RAM host (Volatile) |
| **Kemudahan Akses Host** | Memerlukan Docker CLI | Mudah diedit langsung oleh IDE developer | Tidak terlihat di filesystem disk |
| **Performa I/O** | Native Linux speed | Sedikit overhead pada macOS/Windows | Sangat cepat (Kecepatan RAM) |
| **Use Case Utama** | Database & stateful production data | Source code saat development lokal | Secret sementara, session cache |

---

## 13. When To Use
- Gunakan **Multi-Stage Build**: Untuk semua aplikasi yang memerlukan kompilasi atau dependensi dev (TypeScript, React, Go, Java, Rust).
- Gunakan **Named Volume**: Untuk database (PostgreSQL, MySQL, Redis) agar data tidak terhapus saat container di-redeploy.
- Gunakan **Docker Compose**: Untuk menyatukan service frontend, backend, database, dan cache dalam 1 environment yang dapat dijalankan dengan 1 perintah (`docker compose up -d`).

---

## 14. When NOT To Use
- Jangan gunakan `docker commit` untuk membuat image produksi; selalu gunakan `Dockerfile` versi Git untuk keterlacakan (*reproducibility*).

---

## 15. Common Mistakes
1. **Lupa Menambahkan `.dockerignore`**: Tidak membuat `.dockerignore` sehingga folder `node_modules`, `.git`, dan file `.env` rahasia ikut ter-copy ke dalam image build context.
2. **Tag Image Selalu `:latest`**: Menggunakan tag `:latest` di production membuat rollback mustahil dilakukan saat terjadi bug. Selalu beri tag dengan Git Commit SHA atau Semantic Versioning (`:v1.4.2`).
3. **Menggunakan `ADD` daripada `COPY`**: Instruksi `ADD` memiliki fitur mengekstrak file tar otomatis dan mendownload URL yang dapat memicu risiko keamanan. Gunakan `COPY` kecuali secara eksplisit butuh auto-extract tar lokal.

---

## 16. Best Practices
### Must Have
- Sertakan file `.dockerignore` (abaikan `.git`, `node_modules`, `*.log`, `.env`).
- Manfaatkan Multi-Stage build untuk memisahkan dependency compiler dari image runtime.
- Urutkan layer Dockerfile dari yang paling jarang berubah ke yang paling sering berubah untuk memaksimalkan layer cache.

### Recommended
- Gunakan instruksi `HEALTHCHECK` di Dockerfile atau Compose agar orchestrator mengetahui jika aplikasi hang.
- Gunakan base image bertag spesifik (misal `node:20.11-alpine3.19`, hindari `node:latest`).

### Avoid / Overengineering
- Jangan menjalankan Docker Compose di production cluster multi-server jika Anda membutuhkan kemampuan auto-healing dan auto-scaling multi-node (gunakan Kubernetes).

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Perubahan kode tidak tercermin di container development | Volume bind mount tidak terpasang atau caching layer lama dipakai | Periksa path di `volumes:` dan jalankan `docker compose up --build` |
| Web service tidak bisa connect ke database di Compose | Service web start sebelum database siap menerima koneksi | Gunakan `depends_on` dengan `condition: service_healthy` dan healthcheck |
| Build Docker context sangat lama (> 2 menit) sebelum step 1 dimulai | Folder `.git` atau direktori raksasa ikut terkirim sebagai context | Buat file `.dockerignore` dan masukkan folder-folder besar tersebut |

---

## 18. Exercise
1. Tulis sebuah file `.dockerignore` komprehensif untuk project Node.js atau Python.
2. Buat file `docker-compose.yml` yang menghubungkan service aplikasi web dengan database Redis menggunakan isolated network.

---

## 19. Challenge
Rancang arsitektur simulasi **Docker Build Cache & Layer Optimizer**:
- Simulasikan parser instruksi Dockerfile (`FROM`, `COPY package.json`, `RUN npm ci`, `COPY . .`).
- Hitung checksum dari setiap layer. Jika isi file layer tidak berubah, kembalikan status `CACHED` (0 detik); jika berubah, tandai sebagai `DIRTY` dan invalidasi seluruh layer berikutnya.

---

## 20. Summary
- Multi-Stage build menghasilkan image yang ramping, cepat di-deploy, dan aman dari celah perkakas kompilasi.
- Mengatur urutan instruksi Dockerfile dengan cermat memaksimalkan *layer caching* dan mempercepat pipeline build CI/CD secara signifikan.
- Docker Compose menyediakan otomasi orkestrasi lokal yang andal untuk pengembangan multi-container.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/docker_build_compose_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-03-Containerization-Docker/hands-on/m02/docker_build_compose_sim.js).
