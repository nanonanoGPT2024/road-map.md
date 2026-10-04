## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** DevOps Beginner
* **Kategori:** 01-Core-Foundations
* **Bab:** 05 — Kontainerisasi Modern & Runtime Isolation
* **Modul:** 01 — Kontainerisasi Aplikasi Modern Menggunakan Docker
* **Tingkat Kesulitan:** Dasar hingga Menengah (Beginner to Intermediate)
* **Estimasi Waktu Penyelesaian:** 120 – 180 Menit
* **Prasyarat:** 
  * Pemahaman dasar Command Line Interface (CLI) Linux (POSIX shell).
  * Pemahaman dasar arsitektur OS (proses, memori, I/O, file system).
  * Konsep dasar jaringan komputer (IP address, port, DNS, subnetting).
* **Target Pembaca:** Junior DevOps Engineers, Software Developers, Cloud/System Administrators yang ingin memodernisasi cara deployment dan standardisasi runtime aplikasi.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Membedakan (C4)** perbedaan arsitektural antara isolasi berbasis Virtual Machine (Hypervisor) dengan isolasi berbasis Kontainer (Kernel Sharing).
2. **Mengurai Komponen Internal Linux (C4)** yang membentuk kontainer, khususnya peranan *Linux Namespaces*, *Control Groups (cgroups)*, dan *Union File System (UnionFS)*.
3. **Mengembangkan dan Mengoptimalkan (C6)** berkas `Dockerfile` tingkat produksi menggunakan pendekatan *multi-stage builds*, implementasi *non-root user*, dan optimasi *layer caching*.
4. **Mengoperasikan dan Mengelola (C3)** *lifecycle* kontainer, penyimpanan data persisten (*Docker Volumes* dan *Bind Mounts*), serta komunikasi antar-kontainer melalui *user-defined bridge networks*.
5. **Mengevaluasi dan Memperbaiki (C5)** isu keamanan dan performa umum pada kontainer, seperti kebocoran kredensial (*leaked secrets*), *image bloat*, dan kegagalan penanganan sinyal terminasi OS (PID 1 issue).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                                  DOCKER ECOSYSTEM
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
         Linux Kernel Primitives                          Docker Engine Architecture
         ├─ Namespaces (Isolasi)                          ├─ Docker CLI (Client)
         │  ├─ PID, NET, MNT, IPC, UTS, USER              ├─ dockerd (Daemon)
         ├─ Control Groups (Limitasi)                     ├─ containerd (Runtime Manager)
         │  └─ CPU, Memory, I/O, PIDs                     └─ runc (OCI Runtime)
         └─ UnionFS / Storage Drivers
            └─ Overlay2 (Image Layers & CoW)
                 │
                 ▼
         Docker Workflow Artifacts
         ├─ Dockerfile (Instruksi Blueprint)
         │  ├─ Multi-stage Builds
         │  ├─ Layer Caching Mechanics
         │  └─ Security & Non-root Execution
         ├─ Docker Image (Immutable Read-Only Layers)
         └─ Docker Container (Ephemeral Read-Write Layer)
                 │
                 ▼
         Runtime Orchestration (Host Level)
         ├─ Storage Management (Volumes vs. Bind Mounts vs. tmpfs)
         └─ Networking (Host, Bridge, None, Overlay)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebelum kontainerisasi diadopsi secara massal, industri perangkat lunak menghadapi krisis reproducibility yang dikenal secara informal sebagai sindrom: *"It works on my machine, why not in production?"*.

1. **Environmental Drift:** Tim pengembang menggunakan versi pustaka runtime (misal: Node.js 18.x di macOS), tim QA menguji pada sistem operasi yang berbeda (Ubuntu 22.04 dengan Node.js 18.y), sementara server produksi menjalankan CentOS 7 yang mengompilasi dependensi C++ berbeda. Inkonsistensi ini memicu *bug runtime* yang sulit direproduksi dan diperbaiki.
2. **Resource Inefficiency pada Virtual Machines (VM):** VM menyelesaikan masalah isolasi dengan menyertakan seluruh Guest Operating System (kernel, system binaries, systemd), yang menghabiskan gigabyte memori dan memakan waktu menit untuk proses booting. Kontainerisasi menghilangkan Guest OS ini; semua kontainer berbagi Host Kernel secara aman, menghasilkan overhead CPU/RAM mendekati nol dan waktu start dalam hitungan milidetik.
3. **Immutable Infrastructure Paradigm:** Kontainer memaksa aplikasi dikemas menjadi artefak statis (*immutable image*). Begitu sebuah image lolos tahap automated testing, image yang identik secara biner (berdasarkan *SHA256 digest*) akan didorong ke staging dan produksi, mengeliminasi ketidakpastian konfigurasi.

---

## SEKSI 05 — APA ITU (WHAT)

Docker adalah platform perangkat lunak open-source yang memfasilitasi pembuatan (*building*), pengiriman (*shipping*), dan eksekusi (*running*) aplikasi dalam lingkungan yang terisolasi secara logis, yang disebut **kontainer**.

### Kontainer vs Virtual Machine

| Parameter | Virtual Machine (VM) | Container (Docker) |
| :--- | :--- | :--- |
| **Tingkat Abstraksi** | Abstraksi Hardware (Hypervisor: KVM, ESXi) | Abstraksi OS Kernel (User Space Isolation) |
| **Guest OS** | Wajib ada (lengkap dengan kernel sendiri) | Tidak ada (menggunakan kernel milik Host OS) |
| **Waktu Booting** | Menit (30 – 120 detik) | Sub-detik hingga beberapa detik |
| **Penggunaan Resource** | Tinggi (RAM & CPU dialokasikan secara kaku) | Sangat Ringan (sesuai kebutuhan proses aktual) |
| **Portabilitas** | Terbatas oleh format hypervisor (OVA/VMDK) | Standar Terbuka Universal (OCI Compliant) |
| **Isolasi Keamanan** | Sangat kuat (isolasi berbasis modul hardware) | Kuat (bergantung pada konfigurasi kernel namespace & seccomp) |

### Terminologi Inti Docker
* **Dockerfile:** Dokumen teks berisi urutan instruksi deklaratif yang dibaca oleh Docker daemon untuk membangun sebuah *image*.
* **Image:** Paket perangkat lunak statis, *read-only*, dan *executable* yang mencakup kode sumber, runtime, pustaka sistem, variabel lingkungan, dan konfigurasi default. Image tersusun atas lapisan-lapisan (*layers*).
* **Container:** Instance yang berjalan (*instantiated runtime*) dari sebuah image. Secara fisik, kontainer adalah proses Linux standar yang diberikan batasan visibilitas dan kuota resource oleh kernel.
* **Registry:** Layanan terpusat untuk menyimpan dan mendistribusikan Docker Images (contoh: Docker Hub, GitHub Packages (GHCR), AWS ECR).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Di balik layar sistem operasi Linux, kontainer **bukanlah** sebuah entitas mesin fisik buatan, melainkan sekadar proses komputasi biasa yang dibatasi oleh tiga mekanisme inti kernel:

```text
Docker Container = Namespaces + Control Groups + chroot/pivot_root + Storage Driver
```

### 1. Linux Namespaces (Isolasi Visibilitas)
Namespaces membatasi apa yang **dapat dilihat** oleh sebuah proses:
* **PID (Process ID):** Memberikan isolasi pohon proses. Proses di dalam kontainer melihat dirinya sendiri sebagai PID 1, padahal di Host OS ia berjalan pada PID biasa (misal: PID 45231).
* **NET (Network):** Mengisolasi controller jaringan, tabel routing, antarmuka (`eth0`, `lo`), dan port firewall.
* **MNT (Mount):** Mengisolasi direktori mount filesystem. Kontainer tidak dapat melihat root filesystem Host (`/`) kecuali secara eksplisit diekspos.
* **IPC (Inter-Process Communication):** Mengisolasi memori bersama (shared memory segments) dan message queues.
* **UTS (UNIX Timesharing System):** Mengizinkan kontainer memiliki *hostname* dan nama domain sendiri yang independen dari Host.
* **USER:** Memetakan UID/GID di dalam kontainer ke UID/GID yang berbeda di Host (contoh: `root` UID 0 di kontainer dipetakan ke UID 10001 di Host).

### 2. Control Groups / cgroups (Limitasi Resource)
Jika Namespaces membatasi *apa yang dilihat*, cgroups membatasi seberapa banyak resource yang **dapat digunakan** oleh proses:
* **CPU:** Membatasi kuota eksekusi CPU cycle (menggunakan CFS - Completely Fair Scheduler).
* **Memory:** Menentukan batas maksimum RAM dan swap. Jika batas terlampaui, kernel memicu mekanisme *Out-Of-Memory (OOM) Killer* untuk menghentikan proses tersebut.
* **blkio:** Membatasi kecepatan baca/tulis (*I/O throttling*) ke block storage disk.
* **pids:** Membatasi jumlah maksimum anak-proses yang dapat di-spawn guna mencegah *fork bomb*.

### 3. OverlayFS dan Mekanisme Copy-on-Write (CoW)
Docker menggunakan filesystem berlapis (umumnya `overlay2`). Image tersusun dari sekumpulan *read-only layers*. Ketika kontainer dijalankan, Docker menambahkan satu layer tipis bernama **Container Read-Write Layer** di atas tumpukan layer tersebut.
* **Operasi Baca:** Jika berkas dibaca dan belum pernah dimodifikasi, Docker mengambilnya langsung dari layer image di bawahnya.
* **Operasi Tulis:** Jika berkas yang berasal dari image dimodifikasi, berkas tersebut disalin terlebih dahulu ke *Container Read-Write Layer*, lalu modifikasi diterapkan di sana (**Copy-on-Write**). Layer image asli tetap utuh (*immutable*).

### 4. Docker Engine Architecture
Docker menggunakan arsitektur client-server:
1. **Docker CLI (`docker`):** Antarmuka terminal tempat operator memasukkan perintah. Berkomunikasi dengan daemon melalui Unix Domain Socket (`/var/run/docker.sock`) atau REST API via TCP.
2. **Docker Daemon (`dockerd`):** Proses latar belakang yang mengelola image, kontainer, jaringan, dan volume storage.
3. **containerd:** Daemon runtime kontainer independen yang menangani siklus hidup kontainer tingkat rendah (download image, attach console, panggil runtime).
4. **runc:** Implementasi referensi spesifikasi OCI (Open Container Initiative) yang secara langsung mengeksekusi panggilan sistem Linux (*syscalls*) untuk membangun namespaces dan cgroups sebelum menjalankan aplikasi.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Arsitektur Runtime Docker & Layering Storage

```text
+-------------------------------------------------------------------------------+
| HOST OPERATING SYSTEM (Linux Kernel)                                          |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | KERNEL SPACE: Namespaces | Cgroups | Seccomp | Netfilter (iptables)      |  |
|  +-------------------------------------------------------------------------+  |
|         ▲                                                     ▲               |
|         │ (Syscalls)                                          │               |
|  +--------------+                                      +--------------+       |
|  | runc runtime |                                      | runc runtime |       |
|  +--------------+                                      +--------------+       |
|         ▲                                                     ▲               |
|         │ (gRPC)                                              │               |
|  +-------------------------------------------------------------------------+  |
|  | containerd (Container Runtime Supervisor)                               |  |
|  +-------------------------------------------------------------------------+  |
|         ▲                                                                     |
|         │ (Internal Engine Calls)                                             |
|  +-------------------------------------------------------------------------+  |
|  | dockerd (Docker Daemon: REST Engine, Network Management, Build Engine)  |  |
|  +-------------------------------------------------------------------------+  |
|         ▲                                                                     |
|         │ (Unix Socket: /var/run/docker.sock)                                 |
|  +---------------+                                                            |
|  |  Docker CLI   | <--- Operator Execution (e.g. docker run / docker build)   |
|  +---------------+                                                            |
|                                                                               |
|  ==================== OVERLAY2 STORAGE LAYER MODEL =========================  |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | Container RW Layer (R/W)  <-- Changes, logs, temp data live here        |  |
|  +-------------------------------------------------------------------------+  |
|  | Layer 3: CMD ["node", "server.js"]                     (RO)             |  |
|  +-------------------------------------------------------------------------+  |
|  | Layer 2: COPY . /app                                    (RO)            |  |
|  +-------------------------------------------------------------------------+  |
|  | Layer 1: RUN npm ci --omit=dev                         (RO)             |  |
|  +-------------------------------------------------------------------------+  |
|  | Layer 0: Base Image (node:20-alpine / rootfs)          (RO)             |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut demonstrasi pembuatan, pembangunan, dan eksekusi kontainer minimal menggunakan web server Alpine Linux.

### 1. Direktori Proyek
```bash
mkdir hello-docker && cd hello-docker
```

### 2. Berkas Konfigurasi `index.html`
```html
<!DOCTYPE html>
<html>
<head><title>Sistem Kontainer</title></head>
<body>
  <h1>Modul 05: Docker Berjalan Sukses!</h1>
</body>
</html>
```

### 3. Pembuatan `Dockerfile`
```dockerfile
# Menggunakan base image seminimal mungkin
FROM alpine:3.19

# Pasang web server 'lighttpd'
RUN apk add --no-cache lighttpd

# Salin aset statis ke direktori default web server
COPY index.html /var/www/localhost/htdocs/index.html

# Buka akses port 80
EXPOSE 80

# Jalankan lighttpd di foreground (PID 1)
CMD ["lighttpd", "-D", "-f", "/etc/lighttpd/lighttpd.conf"]
```

### 4. Perintah Build dan Run
```bash
# 1. Bangun image dengan tag 'hello-docker:v1'
docker build -t hello-docker:v1 .

# 2. Jalankan kontainer di background (detached) dengan port forwarding 8080:80
docker run -d --name web-sederhana -p 8080:80 hello-docker:v1

# 3. Uji koneksi via curl
curl http://localhost:8080

# 4. Hentikan dan hapus kontainer
docker stop web-sederhana
docker rm web-sederhana
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kita akan membuat arsitektur kontainer aplikasi web REST API berbasis **Node.js + Express** yang terhubung ke basis data **PostgreSQL**. Struktur ini mengimplementasikan teknik **Multi-stage Build**, **Non-root user execution**, dan **User-defined Bridge Networking**.

### 1. Struktur Direktori Proyek
```text
api-production/
├── .dockerignore
├── Dockerfile
├── package.json
└── src/
    └── server.js
```

### 2. Berkas `.dockerignore`
Memastikan dependensi lokal, berkas development, dan secrets tidak masuk ke dalam context build.
```text
node_modules
npm-debug.log
.git
.gitignore
.env
Dockerfile
README.md
```

### 3. Berkas `package.json`
```json
{
  "name": "docker-api-service",
  "version": "1.0.0",
  "description": "Enterprise Grade Container Architecture",
  "main": "src/server.js",
  "scripts": {
    "start": "node src/server.js"
  },
  "dependencies": {
    "express": "^4.19.2",
    "pg": "^8.11.5"
  }
}
```

### 4. Berkas `src/server.js`
Menyediakan HTTP listener dengan *Graceful Shutdown* untuk menangani `SIGTERM` secara benar.
```javascript
const express = require('express');
const { Pool } = require('pg');

const app = express();
const port = process.env.PORT || 3000;

// Konfigurasi koneksi PostgreSQL via Environment Variables
const pool = new Pool({
  host: process.env.DB_HOST || 'db',
  port: parseInt(process.env.DB_PORT || '5432', 10),
  user: process.env.DB_USER || 'appuser',
  password: process.env.DB_PASSWORD || 'secretpassword',
  database: process.env.DB_NAME || 'appdb',
});

app.get('/healthz', async (req, res) => {
  try {
    // Validasi konektivitas DB
    await pool.query('SELECT 1');
    res.status(200).json({ status: 'UP', database: 'CONNECTED' });
  } catch (err) {
    res.status(503).json({ status: 'DOWN', error: err.message });
  }
});

const server = app.listen(port, () => {
  console.log(`[INFO] Server running on port ${port}`);
});

// Penanganan Graceful Shutdown (Krusial untuk PID 1 di Docker)
const handleShutdown = (signal) => {
  console.log(`[INFO] Received ${signal}. Initiating graceful termination...`);
  server.close(() => {
    console.log('[INFO] HTTP listener closed.');
    pool.end().then(() => {
      console.log('[INFO] Database pool disconnected. Exiting.');
      process.exit(0);
    });
  });

  // Paksa keluar jika tidak selesai dalam 10 detik
  setTimeout(() => {
    console.error('[FATAL] Force shutdown timed out. Terminating.');
    process.exit(1);
  }, 10000);
};

process.on('SIGTERM', () => handleShutdown('SIGTERM'));
process.on('SIGINT', () => handleShutdown('SIGINT'));
```

### 5. Berkas `Dockerfile` Tingkat Produksi (Multi-Stage)
```dockerfile
# ==============================================================================
# TAHAP 1: Dependensi & Pembangunan (Builder Stage)
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /usr/src/app

# Salin manifest dependensi terlebih dahulu untuk utilisasi Docker Layer Caching
COPY package*.json ./

# Pasang dependensi secara terisolasi dan bersih
RUN npm ci --omit=dev

# ==============================================================================
# TAHAP 2: Runtime Ramping (Runner Stage)
# ==============================================================================
FROM node:20-alpine AS runner

# Terapkan environment produksi
ENV NODE_ENV=production
ENV PORT=3000

WORKDIR /usr/src/app

# Isolasi Keamanan: Menggunakan user non-root bawaan Alpine (node)
# Jangan pernah mengeksekusi aplikasi sebagai 'root' di lingkungan produksi!
USER node

# Salin pustaka dependensi dari tahap builder dengan kepemilikan user yang tepat
COPY --chown=node:node --from=builder /usr/src/app/node_modules ./node_modules
COPY --chown=node:node package*.json ./
COPY --chown=node:node src/ ./src/

# Dokumentasi port servis
EXPOSE 3000

# Healthcheck internal Docker engine
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/healthz || exit 1

# Eksekusi server langsung tanpa membungkus via 'npm start' agar Node menerima PID 1
CMD ["node", "src/server.js"]
```

### 6. Orkestrasi Eksekusi Manual (CLI Deployment)

Langkah-langkah menyiapkan basis data persisten dan API dalam satu private network:

```bash
# Langkah 1: Buat User-Defined Bridge Network
docker network create internal-prod-net

# Langkah 2: Buat Named Volume untuk Persistensi Data PostgreSQL
docker volume create pgdata-prod

# Langkah 3: Jalankan Kontainer Database PostgreSQL
docker run -d \
  --name postgres-db \
  --network internal-prod-net \
  --volume pgdata-prod:/var/lib/postgresql/data \
  -e POSTGRES_USER=appuser \
  -e POSTGRES_PASSWORD=secretpassword \
  -e POSTGRES_DB=appdb \
  --restart unless-stopped \
  postgres:16-alpine

# Langkah 4: Bangun Image Aplikasi
docker build -t enterprise-api:1.0.0 .

# Langkah 5: Jalankan Kontainer Aplikasi API
docker run -d \
  --name enterprise-api-service \
  --network internal-prod-net \
  -p 3000:3000 \
  -e DB_HOST=postgres-db \
  -e DB_USER=appuser \
  -e DB_PASSWORD=secretpassword \
  -e DB_NAME=appdb \
  --memory=512m \
  --cpus=1.0 \
  --restart unless-stopped \
  enterprise-api:1.0.0

# Langkah 6: Validasi Operasional
docker ps
curl http://localhost:3000/healthz
```

Respons yang diharapkan:
```json
{"status":"UP","database":"CONNECTED"}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Teknologi | Keuntungan (Pros) | Konsekuensi / Kerugian (Cons) | Rekomendasi Kontekstual |
| :--- | :--- | :--- | :--- |
| **Alpine Base Images** (`alpine`) | Ukuran image sangat kecil (< 10MB), jejak serangan (*attack surface*) minimal. | Menggunakan implementasi pustaka `musl libc` bukan `glibc`. Pustaka C/C++ tertentu (misal: gRPC, Sharp, Python scientific libraries) dapat mengalami bug performa atau kompilasi lambat. | Gunakan untuk Node.js dasar, Go, atau aplikasi tanpa ketergantungan native binding C/C++ yang kompleks. |
| **Debian Slim** (`debian-slim`) | Kompatibilitas library `glibc` 100%, stabilitas tinggi untuk runtime C++, Java, dan Python kompleks. | Ukuran image dasar lebih besar (~80MB – 150MB) dibandingkan Alpine. | Gunakan saat aplikasi membutuhkan binary extensions pihak ketiga yang menargetkan Linux standar (glibc). |
| **Distroless Images** (Google) | Tidak memiliki package manager (`apt`, `apk`), dan tidak memiliki interactive shell (`/bin/sh`). Sangat aman dari eskalasi hacker. | Debugging langsung di dalam kontainer sangat sulit (tidak ada terminal). Memerlukan proses integrasi observabilitas/logging eksternal. | Standar emas untuk fase akhir produksi aplikasi berkeamanan tinggi (*zero-trust*). |
| **Bind Mounts vs Named Volumes** | **Bind Mounts:** File lokal langsung terhubung, memudahkan debugging lokal.<br>**Volumes:** Dikelola penuh oleh Docker daemon, performa tinggi di non-Linux OS, portabel antar host. | **Bind Mounts:** Merusak isolasi sistem, rentan konflik permission host UID/GID.<br>**Volumes:** Tidak dapat diedit secara langsung menggunakan teks editor Host tanpa tool bantu. | Gunakan *Bind Mounts* untuk development lokal saja. Gunakan *Named Volumes* untuk data persisten produksi (DB, static files). |

---

## SEKSI 11 — BEST PRACTICES

1. **Jalankan Aplikasi sebagai Non-Root User:** Secara default, kontainer berjalan sebagai user `root` (UID 0). Jika terjadi celah kerentanan *container breakout*, penyerang langsung memiliki hak akses `root` atas kernel Host OS. Selalu gunakan direktif `USER <nama/UID>` di Dockerfile.
2. **Optimasi Urutan Lapisan (Layer Caching Strategy):**
   * Docker menguji cache dari atas ke bawah.
   * Tempatkan instruksi yang **paling jarang berubah** (misal: instalasi package manager, file manifest dependencies `package.json`, `pom.xml`, `go.mod`) di bagian atas.
   * Tempatkan file yang **paling sering berubah** (`COPY . .` atau kode sumber aktual) di bagian paling bawah.
3. **Satu Kontainer, Satu Tanggung Jawab (Single Concern):** Jangan pernah menggabungkan database, Nginx, dan aplikasi web ke dalam satu kontainer Docker yang sama menggunakan supervisor/systemd. Ini merusak model penskalaan horizontal dan healthcheck.
4. **Implementasikan Multi-Stage Builds:** Pisahkan antara *Build Time dependencies* (compiler, SDK, toolings berukuran besar) dengan *Runtime dependencies*. Hasil akhir image produksi hanya boleh berisi runtime minimal dan binary aplikasi.
5. **Gunakan Explicit Base Image Tags:** Hindari penggunaan tag mutable seperti `:latest`. Tag `:latest` menyebabkan build tidak deterministik karena dependensi dasar dapat berubah sewaktu-waktu. Gunakan SHA pinning atau semantic versioning yang presisi (contoh: `node:20.12.2-alpine3.19`).
6. **Tangani Sinyal Terminasi (PID 1 Signals):** Pastikan proses utama di kontainer siap menerima sinyal `SIGTERM` dan `SIGINT`. Jika membungkus aplikasi dengan script Bash (`CMD ["./start.sh"]`), gunakan perintah `exec` di dalam shell script (`exec node app.js`) agar proses aplikasi mengambil alih PID 1.
7. **Batasi Resource Kontainer (Guardrails):** Di lingkungan produksi, selalu sertakan flag batasan memori dan CPU (`--memory`, `--cpus`) guna mencegah satu kontainer nakal menghabiskan seluruh memori Host OS (menghindari crash fatal sistem).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menyertakan Direktori `node_modules` atau Vendor Lokal ke Build Context
* **Kesalahan:** Menjalankan `COPY . .` tanpa mendefinisikan `.dockerignore`, sehingga pustaka yang terkompilasi di mesin lokal (misal: macOS M-series arm64) ikut tersalin ke dalam image kontainer yang berbasis Linux x86_64.
* **Gejala:** Error `Segmentation fault`, arsitektur biner tidak cocok, atau build context memakan waktu transfer berpuluh-puluh gigabyte.
* **Solusi:** Wajib membuat berkas `.dockerignore` dan masukkan `node_modules`, `target/`, `.git`, dan temporary files lainnya.

### 2. Hardcoding Secrets & Credentials di Dockerfile
* **Kesalahan:** Menyematkan token, API key, atau password langsung pada instruksi Dockerfile (`ENV DB_PASSWORD=mysecret123` atau `ARG AWS_KEY=...`).
* **Gejala:** Siapapun yang memiliki akses membaca image (`docker history <image>`) dapat membaca kredensial tersebut secara polos, meskipun file tersebut telah dihapus pada instruksi layer berikutnya.
* **Solusi:** Gunakan Docker BuildKit Secret Mounts (`RUN --mount=type=secret...`) untuk fase build, atau inject secrets via Environment Variables/Vault saat runtime (`docker run -e`).

### 3. Menggunakan `CMD` dalam Bentuk Shell Form
* **Kesalahan:** Menuliskan `CMD node server.js` (Shell Form).
* **Gejala:** Docker akan mengeksekusi instruksi tersebut sebagai subproses dari shell: `/bin/sh -c "node server.js"`. Akibatnya, `/bin/sh` menempati PID 1 dan **tidak meneruskan sinyal** `SIGTERM` ke runtime Node.js. Kontainer akan macet selama 10 detik saat di-stop sebelum dimatikan paksa dengan `SIGKILL`.
* **Solusi:** Gunakan format **Exec Form**: `CMD ["node", "server.js"]`.

### 4. Mengabaikan Zombie Process (PID 1 Problem)
* **Kesalahan:** Menjalankan aplikasi yang sering memunculkan sub-proses (*child processes*) tanpa menggunakan init system.
* **Gejala:** Proses anak yang mati tidak pernah di-*reap* (dibersihkan statusnya) oleh PID 1, menyebabkan akumulasi proses zombie hingga tabel proses OS penuh (`out of pids`).
* **Solusi:** Jalankan kontainer dengan flag `--init` (Docker akan menyisipkan utilitas `tini` sebagai PID 1 untuk me-reap zombie processes secara otomatis).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Anda ditugaskan oleh tim arsitektur untuk memvalidasi pemahaman isolasi filesystem, debugging kontainer tanpa downtime, serta melakukan optimasi layer caching pada aplikasi microservice.

### Tugas 1: Observasi Isolasi Namespace & Ekstraksi Metadata
1. Jalankan sebuah kontainer `nginx:alpine` di latar belakang dengan batasan memori 128MB.
2. Identifikasi PID asli kontainer tersebut pada Host Linux menggunakan perintah `docker inspect`.
3. Masuk ke dalam network namespace kontainer tersebut menggunakan perintah `nsenter` (jika menggunakan Linux native) atau bandingkan antarmuka network via `docker exec`.

**Perintah Acuan:**
```bash
# Jalankan kontainer
docker run -d --name lab-nginx -m 128m nginx:alpine

# Ekstraksi PID Host
CONTAINER_PID=$(docker inspect --format '{{.State.Pid}}' lab-nginx)
echo "PID Host dari kontainer: $CONTAINER_PID"

# Buktikan pohon proses dari sudut pandang host
ps aux | grep $CONTAINER_PID
```

### Tugas 2: Debugging Aplikasi Bermasalah (Network Connection Failure)
Diberikan situasi di mana kontainer backend API tidak dapat memanggil kontainer database.
1. Buat network tersendiri: `docker network create debug-net`.
2. Jalankan database: `docker run -d --name db-target --network debug-net redis:alpine`.
3. Buat kontainer ephemeral penguji jaringan:
```bash
docker run --rm -it --network debug-net nicolaka/netshoot
```
4. Di dalam prompt `netshoot`, lakukan verifikasi DNS dan konektivitas port:
```bash
dig db-target
nc -zv db-target 6379
```
5. Keluar dari shell dan pastikan kontainer netshoot terhapus otomatis secara bersih.

### Tugas 3: Refactoring Dockerfile (Optimasi Caching & Keamanan)
Diberikan `Dockerfile` buruk di bawah ini:
```dockerfile
# BAD DOCKERFILE
FROM ubuntu:latest
RUN apt-get update
RUN apt-get install -y python3 python3-pip
COPY . /app
WORKDIR /app
RUN pip3 install -r requirements.txt
CMD python3 /app/main.py
```

**Tugas Anda:** 
1. Ubah ke Python slim image dengan versi eksplisit (`python:3.11-slim`).
2. Gabungkan `apt-get update` dan instalasi (jika diperlukan) dalam 1 instruksi `RUN` dan bersihkan cache (`rm -rf /var/lib/apt/lists/*`).
3. Pisahkan penyalinan `requirements.txt` sebelum penyalinan kode aplikasi demi memanfaatkan cache.
4. Buat user non-root dan gunakan user tersebut.
5. Ganti `CMD` menjadi *Exec Form*.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan di bawah ini untuk menguji pemahaman Anda:

1. **Komponen kernel Linux apa yang bertanggung jawab membatasi penggunaan kapasitas memori kontainer agar tidak melebihi 256MB?**
   * A. Namespaces
   * B. Control Groups (cgroups)
   * C. OverlayFS
   * D. Seccomp

2. **Mengapa instruksi `COPY package*.json ./` diletakkan sebelum instruksi `COPY . .` pada Dockerfile multi-stage?**
   * A. Untuk mencegah file binary luar tertimpa.
   * B. Karena perintah `npm install` membutuhkan akses root.
   * C. Memaksimalkan layer caching Docker agar tidak perlu mengunduh ulang dependensi jika kode sumber aplikasi berubah namun dependensi tetap.
   * D. Untuk menyamakan checksum SHA256 pada stage berikutnya.

3. **Perhatikan instruksi berikut pada `Dockerfile`:**
   ```dockerfile
   RUN apt-get update
   RUN apt-get install -y curl
   ```
   **Apa kelemahan utama dari pendekatan dua layer terpisah di atas?**
   * A. Menghasilkan error permission denied.
   * B. Lapisan cache `apt-get update` dapat menjadi kadaluwarsa (*stale cache*), sehingga saat menambah paket baru di kemudian hari, instalasi dapat gagal atau mengambil versi usang.
   * C. Direktori `/var/run/docker.sock` akan otomatis terkunci.
   * D. File binary `curl` tidak dapat dieksekusi oleh non-root user.

4. **Kapan Anda HARUS menggunakan `Bind Mount` dibandingkan `Named Volume`?**
   * A. Menyimpan data persisten basis data produksi.
   * B. Mengalirkan log audit transaksi keuangan dengan enkripsi otomatis.
   * C. Memetakan direktori kode sumber di komputer pengembang lokal ke dalam kontainer untuk kebutuhan *live reloading / hot swapping*.
   * D. Mengamankan password dan secrets API.

5. **Apa yang terjadi ketika kontainer dieksekusi menggunakan format `CMD npm start` dan menerima instruksi `docker stop`?**
   * A. Node.js langsung mati dalam tempo 1 milidetik secara aman.
   * B. Sinyal `SIGTERM` ditangkap oleh shell `/bin/sh`, tidak diteruskan ke proses Node.js, aplikasi macet hingga batas timeout tercapai, lalu dimatikan paksa melalui `SIGKILL`.
   * C. Docker daemon mengembalikan error status 127.
   * D. Storage driver `overlay2` mengalami *corruption lock*.

---

### Kunci Jawaban & Rasional

1. **Jawaban: B**  
   *Rasional:* Namespaces mengisolasi visibilitas (pandangan proses), sedangkan *cgroups* mengatur batasan alokasi resource komputasi fisik (CPU, RAM, disk I/O).
2. **Jawaban: C**  
   *Rasional:* Docker memverifikasi cache secara bertahap. Jika file manifest dependensi tidak berubah, Docker menggunakan cache layer dependensi yang telah ada, mempercepat waktu kompilasi build dari menit menjadi hitungan detik.
3. **Jawaban: B**  
   *Rasional:* Teknik yang benar adalah menggabungkan perintah instalasi menjadi satu baris (*chaining*): `RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*`. Jika dipisah, instruksi `apt-get update` akan selalu di-cache dan tidak pernah dieksekusi ulang saat nama paket di layer kedua ditambahkan.
4. **Jawaban: C**  
   *Rasional:* Bind Mount mengizinkan pengembang merefleksikan perubahan berkas lokal ke dalam kontainer runtime secara instan tanpa perlu rebuild image.
5. **Jawaban: B**  
   *Rasional:* Penggunaan *Shell Form* membungkus proses dengan shell sh. Shell secara default menolak mendistribusikan sinyal termination POSIX ke *child process*, menyebabkan aplikasi gagal melakukan *graceful exit*.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi:**
  * [Docker Documentation — Best practices for writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
  * [Open Container Initiative (OCI) Image & Runtime Specifications](https://opencontainers.org/)
* **Buku & Manual Teknis:**
  * *"Docker Deep Dive"* oleh Nigel Poulton.
  * *"Container Security: Fundamental Technology Concepts that Protect Containerized Applications"* oleh Liz Rice (O'Reilly Media).
* **Linux Kernel Internals:**
  * Linux Programmer's Manual: `man 7 namespaces`
  * Linux Programmer's Manual: `man 7 cgroups`
* **Tools Ekosistem Penunjang:**
  * [Hadolint](https://github.com/hadolint/hadolint): Linter untuk validasi Dockerfile sesuai standar best practice.
  * [Trivy](https://github.com/aquasecurity/trivy): Scanner vulnerability komprehensif untuk kontainer image.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Hakikat Kontainer:** Kontainer adalah proses Linux terisolasi yang diatur oleh **Namespaces** (isolasi visibilitas) dan **Control Groups / cgroups** (kuota batas resource), membedakannya secara fundamental dari Virtual Machine yang menggunakan hypervisor hardware.
2. **Lapisan Image (Image Layers):** Docker Image tersusun atas lapisan *immutable read-only* yang dipersatukan oleh storage driver (seperti `overlay2`). Kontainer menambahkan satu *thin read-write layer* di bagian paling atas dengan mekanisme Copy-on-Write (CoW).
3. **Standar Dockerfile Produksi:** Dockerfile enterprise wajib mengadopsi pola **Multi-stage Build** untuk meminimalisasi ukuran image dan attack surface, menggunakan **Non-Root User** demi keamanan hak akses, dan memanfaatkan urutan instruksi yang memicu efisiensi **Layer Caching**.
4. **Persistensi & Jaringan:** Data stateful aplikasi disimpan secara persisten di luar lifecycle kontainer menggunakan **Docker Named Volumes**. Komunikasi antar-kontainer harus diisolasi menggunakan **User-defined Bridge Networks**, memanfaatkan fitur bawaan service discovery internal DNS Docker.

---

## SEKSI 17 — GLOSARIUM

* **Copy-on-Write (CoW):** Strategi optimasi penyimpanan di mana sistem hanya menyalin resource saat proses mencoba memodifikasinya, menjaga file layer dasar tetap tidak berubah (*immutable*).
* **OCI (Open Container Initiative):** Badan standar industri terbuka yang menetapkan format spesifikasi kontainer runtime (`runc`) dan distribusi kontainer image.
* **Multi-Stage Build:** Metode pembuatan image Docker yang membagi proses pembangunan ke dalam beberapa tahap (*stages*) berbeda, sehingga artefak kompilasi development tidak masuk ke image akhir produksi.
* **PID 1 Problem:** Tantangan dalam Unix di mana proses yang menempati Process ID 1 memikul tanggung jawab khusus (menangani sinyal OS seperti `SIGTERM` dan membersihkan zombie child processes).
* **Daemon (`dockerd`):** Proses background persisten yang mengontrol dan mengelola seluruh siklus hidup objek Docker di Host OS.
* **Bridge Network:** Jaringan perangkat lunak internal default pada host yang memungkinkan kontainer-kontainer yang terhubung saling bertukar paket IP secara privat.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Petunjuk Pengajaran
* **Visualisasi Konsep:** Saat menjelaskan Namespaces dan cgroups, jangan langsung masuk ke sintaks Dockerfile. Buka terminal Linux, tunjukkan output perintah `ls -l /proc/$$/ns` untuk mendemonstrasikan bahwa konsep isolasi tersebut merupakan fitur natif kernel Linux, bukan "sihir" buatan Docker.
* **Penekanan PID 1:** Sering kali pengembang bingung mengapa aplikasi Node/Python/Java mereka membutuhkan waktu 10 detik penuh saat dieksekusi `docker stop`. Demonstrasikan perbedaan antara `CMD ["node", "app.js"]` vs `CMD node app.js` menggunakan perintah `docker logs` dan amati proses penangkapan sinyal `SIGTERM`.
* **Demonstrasi Cache Invalidation:** Lakukan demonstrasi langsung dengan mengedit sebaris komentar pada file aplikasi. Tunjukkan bagaimana letak instruksi `COPY` mempengaruhi cepat/lambatnya proses pembangunan image.

### Lingkungan Lab yang Dibutuhkan
* Host OS: Ubuntu 22.04 LTS atau Linux Environment dengan Kernel >= 5.15 (atau Docker Desktop pada macOS/Windows dengan WSL2 backend aktif).
* Docker Engine CE versi 24.x atau lebih baru terpasang dan dapat dieksekusi tanpa hak sudo (terdaftar di grup `docker`).
* Akses terminal dengan utilitas `curl`, `git`, dan network utilities.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **1.0.0** | 2024-03-30 | Senior Curriculum Architect | Rilis awal kurikulum standar Foundation Containerization Docker. |
| **1.1.0** | 2024-04-15 | DevOps Engineering Reviewer | Penambahan skenario Graceful Shutdown handling di Section 09 dan integrasi tabel trade-offs base image. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* ⬅️ **Modul Sebelumnya:** [Bab 04 — Dasar-Dasar Shell Scripting & Otomasi Linux System](../04-linux-scripting/01-shell-automation.md)
* ➡️ **Modul Berikutnya:** [Bab 05 Modul 02 — Multi-Container Orchestration Menggunakan Docker Compose](./02-docker-compose-orchestration.md)